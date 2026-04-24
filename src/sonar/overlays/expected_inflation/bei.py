"""US BEI builder + country dispatcher (Sprint 1.1).

Spec: ``docs/specs/overlays/expected-inflation.md`` §2 (US hierarchy:
BEI primary 5Y/10Y/30Y) + §4 (BEI branch + 5y5y compounded forward) +
§8 (storage with ``nss_fit_id`` FK).

Methodology version: ``EXP_INF_BEI_v0.1`` (spec target).

Country coverage shipped here:

* ``US`` — FRED ``T5YIE`` / ``T10YIE`` direct breakeven series for
  5Y/10Y; ``DGS30 - DFII30`` fallback for 30Y (FRED publishes
  ``T30YIEM`` monthly only — skipped for daily storage). 5y5y forward
  computed compounded per spec §4.

* ``GB`` — out of scope for this dispatcher: GB BEI continues to
  ship via :mod:`sonar.scripts.backfill_boe_bei` under the legacy
  ``EXPINF_BEI_v1.0`` tag pending ``CAL-BEI-METHODOLOGY-UNIFY``.

Cross-validation: when ``T5YIFR`` (FRED 5y5y forward breakeven) is
available, emit ``XVAL_DRIFT`` per
:doc:`docs/specs/conventions/flags.md` when
``|BEI_5y5y - T5YIFR| > 10 bps``.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from sonar.config import settings
from sonar.connectors.fred import FredConnector
from sonar.db.models import NSSYieldCurveSpot
from sonar.overlays.exceptions import DataUnavailableError
from sonar.overlays.expected_inflation import ExpInfBEI, compute_5y5y

if TYPE_CHECKING:
    from datetime import date as date_t

    from sqlalchemy.orm import Session

    from sonar.connectors.base import Observation

log = structlog.get_logger()

__all__ = [
    "EXPECTED_PRIMARY_TENORS",
    "US_XVAL_DRIFT_THRESHOLD_BPS",
    "build_bei_row",
    "build_us_bei_row",
]


# Spec §2 hierarchy: US BEI primary tenors are 5Y/10Y/30Y. 20Y is not
# in the spec hierarchy for US (and FRED doesn't publish a daily T20YIE
# anyway), so its absence is by-design — no flag needed.
EXPECTED_PRIMARY_TENORS: tuple[str, ...] = ("5Y", "10Y", "30Y")

# Direct FRED breakeven series — preferred over component subtraction.
_US_BEI_DIRECT_TENORS: dict[str, str] = {"5Y": "T5YIE", "10Y": "T10YIE"}

# Cross-validation series (FRED 5y5y forward breakeven) and threshold
# matching the BEI 5y5y compounded value.
_US_XVAL_SERIES: str = "T5YIFR"
US_XVAL_DRIFT_THRESHOLD_BPS: float = 10.0


async def build_bei_row(
    session: Session,
    country_code: str,
    observation_date: date_t,
    *,
    fred_connector: FredConnector | None = None,
) -> ExpInfBEI:
    """Country-dispatched BEI builder per spec §4.

    GB BEI lives in :mod:`sonar.scripts.backfill_boe_bei` under the
    legacy ``EXPINF_BEI_v1.0`` tag — migration to this dispatcher is
    deferred to ``CAL-BEI-METHODOLOGY-UNIFY``.
    """
    if country_code == "US":
        return await build_us_bei_row(session, observation_date, fred_connector=fred_connector)
    if country_code == "GB":
        msg = (
            "GB BEI lives in sonar.scripts.backfill_boe_bei under the legacy "
            "EXPINF_BEI_v1.0 tag — migration deferred (CAL-BEI-METHODOLOGY-UNIFY)."
        )
        raise NotImplementedError(msg)
    msg = f"BEI builder not shipped for country={country_code!r}"
    raise NotImplementedError(msg)


async def build_us_bei_row(  # noqa: PLR0912 — branch count tracks tenor cases + xval + connector lifecycle, splitting hides the spec §4 step 2 pipeline.
    session: Session,
    observation_date: date_t,
    *,
    fred_connector: FredConnector | None = None,
) -> ExpInfBEI:
    """Build a US BEI row per spec §4 step 2.

    Strategy:

    * 5Y / 10Y — FRED ``T{N}YIE`` direct breakeven series.
    * 30Y — ``DGS30 - DFII30`` component subtraction (FRED publishes
      ``T30YIEM`` monthly only; daily storage uses the components).
    * ``5y5y`` — compounded ``[(1 + r10)^10 / (1 + r5)^5]^(1/5) - 1``
      per spec §4 (never the linear approximation).
    * ``nss_fit_id`` — looked up from
      :class:`~sonar.db.models.NSSYieldCurveSpot` for ``(US, date)``.
      Spec §8 marks the FK mandatory; raise
      :class:`~sonar.overlays.exceptions.DataUnavailableError` when no
      spot row exists for the date so the orchestrator can skip cleanly.
    * Confidence — 0.90 base, ``-0.10`` per missing primary tenor,
      floored at 0.50.
    * Flags — propagate ``yield_curves_spot.flags`` upstream (spec §4
      step 2 inheritance) plus ``XVAL_DRIFT`` when
      ``|BEI_5y5y - T5YIFR| > 10 bps``.

    The ``fred_connector`` parameter lets pipelines reuse a long-lived
    client; when ``None`` we instantiate one from
    :data:`sonar.config.settings` and ``aclose`` it on exit.
    """
    owns_connector = fred_connector is None
    if fred_connector is None:
        fred_connector = FredConnector(
            api_key=settings.fred_api_key,
            cache_dir=str(settings.cache_dir / "fred"),
        )

    try:
        bei_obs = await fred_connector.fetch_bei_series("US", observation_date)
        nominal_obs = await fred_connector.fetch_yield_curve_nominal("US", observation_date)
        linker_obs = await fred_connector.fetch_yield_curve_linker("US", observation_date)
        xval_obs = await _fetch_xval_5y5y(fred_connector, observation_date)
    finally:
        if owns_connector:
            await fred_connector.aclose()

    bei_tenors: dict[str, float] = {}
    nominal_yields: dict[str, float] = {}
    linker_real_yields: dict[str, float] = {}

    for tenor in _US_BEI_DIRECT_TENORS:
        if tenor in bei_obs:
            bei_tenors[tenor] = _to_decimal(bei_obs[tenor])

    if "30Y" in nominal_obs and "30Y" in linker_obs:
        n30 = _to_decimal(nominal_obs["30Y"])
        l30 = _to_decimal(linker_obs["30Y"])
        bei_tenors["30Y"] = n30 - l30
        nominal_yields["30Y"] = n30
        linker_real_yields["30Y"] = l30

    # Audit trail for 5Y/10Y nominal/linker components even when BEI
    # came from the direct series (consumers can verify against the
    # subtraction).
    for tenor in ("5Y", "10Y"):
        if tenor in nominal_obs:
            nominal_yields[tenor] = _to_decimal(nominal_obs[tenor])
        if tenor in linker_obs:
            linker_real_yields[tenor] = _to_decimal(linker_obs[tenor])

    if not bei_tenors:
        msg = f"US BEI: no tenors fetched from FRED for {observation_date.isoformat()}"
        raise DataUnavailableError(msg)

    if "5Y" in bei_tenors and "10Y" in bei_tenors:
        bei_tenors["5y5y"] = compute_5y5y(bei_tenors["5Y"], bei_tenors["10Y"])

    spot_row = (
        session.query(NSSYieldCurveSpot)
        .filter(
            NSSYieldCurveSpot.country_code == "US",
            NSSYieldCurveSpot.date == observation_date,
        )
        .order_by(NSSYieldCurveSpot.id.desc())
        .first()
    )
    if spot_row is None:
        msg = (
            f"US BEI: no yield_curves_spot row for "
            f"{observation_date.isoformat()} — nss_fit_id FK required (spec §8)"
        )
        raise DataUnavailableError(msg)

    fit_id = UUID(spot_row.fit_id)
    spot_flags = tuple(f for f in (spot_row.flags or "").split(",") if f)

    present = sum(1 for t in EXPECTED_PRIMARY_TENORS if t in bei_tenors)
    missing = len(EXPECTED_PRIMARY_TENORS) - present
    confidence = max(0.50, 0.90 - 0.10 * missing)

    flags_set: set[str] = set(spot_flags)
    if xval_obs is not None and "5y5y" in bei_tenors:
        xval_decimal = _to_decimal(xval_obs)
        delta_bps = abs(bei_tenors["5y5y"] - xval_decimal) * 10_000.0
        if delta_bps > US_XVAL_DRIFT_THRESHOLD_BPS:
            flags_set.add("XVAL_DRIFT")
            log.info(
                "bei.us.xval_drift",
                date=observation_date.isoformat(),
                bei_5y5y=bei_tenors["5y5y"],
                t5yifr=xval_decimal,
                delta_bps=round(delta_bps, 2),
            )

    return ExpInfBEI(
        country_code="US",
        observation_date=observation_date,
        nominal_yields=nominal_yields,
        linker_real_yields=linker_real_yields,
        bei_tenors=bei_tenors,
        linker_connector="fred",
        nss_fit_id=fit_id,
        confidence=confidence,
        flags=tuple(sorted(flags_set)),
    )


async def _fetch_xval_5y5y(
    connector: FredConnector, observation_date: date_t
) -> Observation | None:
    """Fetch the most recent ``T5YIFR`` observation on-or-before the date.

    Returns ``None`` when the series has no observations in the 7-day
    look-back window (e.g. weekends without prior weekday hit) or when
    the upstream call fails — cross-val is best-effort, not blocking.
    """
    window_days = 7
    start = observation_date - timedelta(days=window_days)
    try:
        obs = await connector.fetch_series(_US_XVAL_SERIES, start, observation_date)
    except Exception as exc:
        log.debug(
            "bei.us.xval_unavailable",
            date=observation_date.isoformat(),
            reason=str(exc),
        )
        return None
    usable = [o for o in obs if o.observation_date <= observation_date]
    if not usable:
        return None
    usable.sort(key=lambda o: o.observation_date)
    return usable[-1]


def _to_decimal(observation: Observation) -> float:
    """``Observation.yield_bps`` (bps integer) → decimal (``0.0245`` =
    2.45%) per units.md §Yields.
    """
    return observation.yield_bps / 10_000.0
