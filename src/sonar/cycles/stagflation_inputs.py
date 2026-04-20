"""Stagflation overlay input resolver for ECS compute.

Fetches the three inputs the ECS stagflation overlay (spec §4)
depends on — CPI YoY, Sahm trigger, unemployment-rate delta — and
packages them as :class:`StagflationInputs` for ``compute_ecs``.

Sources per country family:

- **US**: ``cpi_yoy`` via FRED CPIAUCSL monthly YoY; ``sahm_triggered``
  via the existing E3 Labor row passthrough; ``unemp_delta`` derived
  from the same FRED UNRATE series (current vs 12-month-prior).
- **EA (DE/PT/IT/ES/FR/NL)**: ``cpi_yoy`` via FRED CPALTT01*M*659N
  (OECD CPI growth YoY) or Eurostat HICP (Phase 2+); ``sahm_triggered``
  is US-only per spec §2 so this path returns ``None`` (unemp_delta
  alone feeds the labor-weakness check if present).
- **Fallback**: any missing input returns ``None`` on that slot;
  compute path emits ``STAGFLATION_INPUT_MISSING`` + -0.05 confidence
  penalty per spec §6.

Phase 0-1 design: the resolver is side-effect-free (pure fetch +
transform) so it can be called synchronously from compute pipelines
without reshaping the broader ingestion flow.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import structlog

from sonar.cycles.economic_ecs import StagflationInputs
from sonar.db.models import E3Labor
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from datetime import date

    from sqlalchemy.orm import Session

    from sonar.connectors.fred import FredConnector

log = structlog.get_logger()

# FRED CPI series ids.
FRED_CPI_US = "CPIAUCSL"  # headline CPI, seasonally adjusted, monthly.
FRED_CPI_OECD_TEMPLATE = "CPALTT01{iso}M659N"  # OECD CPI growth YoY by ISO alpha-2.
FRED_UNRATE_US = "UNRATE"

SUPPORTED_EA_COUNTRIES: frozenset[str] = frozenset({"DE", "PT", "IT", "ES", "FR", "NL"})


async def _fetch_cpi_yoy_us(fred: FredConnector, observation_date: date) -> float | None:
    """Pull CPIAUCSL over the last ~14 months and compute YoY.

    Returns ``None`` if FRED errors out or < 13 monthly points in the
    window.
    """
    start = observation_date - timedelta(days=14 * 31)
    try:
        obs = await fred.fetch_economic_series(FRED_CPI_US, start, observation_date)
    except DataUnavailableError as e:
        log.info("stagflation.cpi_us.unavailable", reason=str(e))
        return None
    # Sort by date ascending and take the last 13 months.
    obs.sort(key=lambda o: o.observation_date)
    if len(obs) < 13:
        return None
    latest = obs[-1].value
    yoy_base = obs[-13].value
    if yoy_base == 0:
        return None
    return (latest - yoy_base) / yoy_base


async def _fetch_cpi_yoy_oecd(
    fred: FredConnector, country: str, observation_date: date
) -> float | None:
    """OECD CPI growth YoY via FRED's CPALTT01{ISO}M659N series family."""
    series = FRED_CPI_OECD_TEMPLATE.format(iso=country.upper())
    start = observation_date - timedelta(days=14 * 31)
    try:
        obs = await fred.fetch_economic_series(series, start, observation_date)
    except DataUnavailableError as e:
        log.info(
            "stagflation.cpi_oecd.unavailable",
            country=country,
            series=series,
            reason=str(e),
        )
        return None
    obs.sort(key=lambda o: o.observation_date)
    if not obs:
        return None
    # Series already expresses YoY growth — spec §2 expects decimal
    # (e.g. 0.031 = 3.1%) while FRED delivers percent (3.1). Convert.
    return obs[-1].value / 100.0


async def _fetch_unemp_delta_us(fred: FredConnector, observation_date: date) -> float | None:
    """UNRATE current vs 12-month-prior (decimal delta, e.g. 0.005 = 0.5pp)."""
    start = observation_date - timedelta(days=14 * 31)
    try:
        obs = await fred.fetch_economic_series(FRED_UNRATE_US, start, observation_date)
    except DataUnavailableError as e:
        log.info("stagflation.unrate_us.unavailable", reason=str(e))
        return None
    obs.sort(key=lambda o: o.observation_date)
    if len(obs) < 13:
        return None
    latest_pct = obs[-1].value  # UNRATE is in percent (e.g. 4.1)
    prior_pct = obs[-13].value
    return (latest_pct - prior_pct) / 100.0


def _latest_sahm_triggered(
    session: Session, country_code: str, observation_date: date
) -> int | None:
    """Read sahm_triggered from the latest E3 Labor row (US-only passthrough)."""
    row = (
        session.query(E3Labor)
        .filter(
            E3Labor.country_code == country_code,
            E3Labor.date <= observation_date,
        )
        .order_by(E3Labor.date.desc())
        .first()
    )
    if row is None:
        return None
    return int(row.sahm_triggered)


async def resolve_stagflation_inputs(
    country_code: str,
    observation_date: date,
    *,
    fred: FredConnector,
    session: Session,
) -> StagflationInputs:
    """Resolve (cpi_yoy, sahm_triggered, unemp_delta) for ``(country, date)``.

    US gets the full trio; EA countries get ``cpi_yoy`` via OECD
    proxy, ``sahm_triggered = None`` (spec §2 SAHM_US_ONLY), and
    ``unemp_delta = None`` because EA unemployment is already a
    component of the E3 Labor row (not a stagflation-specific
    series).

    Missing inputs are returned as ``None``; the caller
    (``compute_ecs``) emits ``STAGFLATION_INPUT_MISSING`` + penalty.
    """
    country = country_code.upper()
    if country == "US":
        cpi = await _fetch_cpi_yoy_us(fred, observation_date)
        sahm = _latest_sahm_triggered(session, country, observation_date)
        unemp = await _fetch_unemp_delta_us(fred, observation_date)
        return StagflationInputs(cpi_yoy=cpi, sahm_triggered=sahm, unemp_delta=unemp)

    if country in SUPPORTED_EA_COUNTRIES:
        cpi = await _fetch_cpi_yoy_oecd(fred, country, observation_date)
        # Sahm is US-only per spec; EA countries have no analogue here.
        return StagflationInputs(cpi_yoy=cpi, sahm_triggered=None, unemp_delta=None)

    log.info(
        "stagflation.unsupported_country",
        country=country,
        date=observation_date.isoformat(),
    )
    return StagflationInputs(cpi_yoy=None, sahm_triggered=None, unemp_delta=None)


__all__ = [
    "FRED_CPI_OECD_TEMPLATE",
    "FRED_CPI_US",
    "FRED_UNRATE_US",
    "SUPPORTED_EA_COUNTRIES",
    "resolve_stagflation_inputs",
]
