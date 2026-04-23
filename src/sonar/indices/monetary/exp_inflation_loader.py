"""Live expected-inflation loader — Sprint Q CAL-EXPINF-LIVE-ASSEMBLER-WIRING.

Closes the wiring gap at `src/sonar/overlays/live_assemblers.py:625`
where the daily-overlays `OverlayBundle.expected_inflation` has been
hard-coded to ``None`` since Sprint 7F. Assembles kwargs for
:func:`sonar.overlays.expected_inflation.build_canonical` from live
connector surfaces so the overlay pipeline emits the canonical
``EXPINF_CANONICAL`` `IndexValue` row the M3 classifier reads.

Scope (Sprint Q revised, per audit
`docs/backlog/audits/sprint-q-expinf-wiring-audit.md`):

- **US**: FRED BEI (``T5YIE`` / ``T10YIE``) + FRED survey (Michigan 1Y
  + Cleveland Fed model 10Y). Promotes US M3 from DEGRADED→FULL.
- **Non-US**: returns ``None`` — no live BEI/survey source exists in
  the connector surface today (Bundesbank / BoE / BoJ / BoC / ECB SDW
  have no live inflation endpoints; country-native linker fetchers are
  stubs). DE/EA/GB/JP/CA/IT/ES/FR therefore stay DEGRADED with the
  existing ``M3_EXPINF_MISSING`` flag until per-country connector CALs
  land (``CAL-EXPINF-DE-BUNDESBANK-LINKER`` / ``CAL-EXPINF-EA-ECB-SPF``
  / ``CAL-EXPINF-GB-BOE-ILG-SPF`` / ``CAL-EXPINF-FR-BDF-OATI-LINKER``).

Returns ``dict[str, Any] | None`` — the shape expected by
:attr:`sonar.pipelines.daily_overlays.OverlayBundle.expected_inflation`
(kwargs dict passed via ``**bundle.expected_inflation`` into
``build_canonical``). Graceful fallback on connector errors: logs at
``info`` / ``warning`` and returns ``None`` so the overlay pipeline
routes a structured skip rather than crashing the run.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
import structlog

from sonar.overlays.exceptions import OverlayError
from sonar.overlays.expected_inflation import compute_bei_us, compute_survey_us

if TYPE_CHECKING:
    from datetime import date

    from sonar.connectors.base import Observation
    from sonar.connectors.fred import FredConnector


__all__ = ["load_live_exp_inflation_kwargs"]


log = structlog.get_logger()


# US Fed long-run inflation target (FOMC Statement on Longer-Run Goals).
# Used as ``bc_target_pct`` input to :func:`build_canonical` anchor
# computation. Non-US country targets land via future per-country wiring.
_US_BC_TARGET_PCT: float = 0.02


_TRANSIENT_ERRORS: tuple[type[Exception], ...] = (
    OverlayError,
    httpx.HTTPError,
    httpx.TimeoutException,
    ValueError,
)


def _observations_to_decimal(
    obs_map: dict[str, Observation],
) -> dict[str, float]:
    """Convert ``{tenor: Observation}`` to ``{tenor: decimal_yield}``.

    FRED ``yield_bps`` stores ``percent * 100``; decimal yield =
    ``bps / 10_000``. Empty inputs produce empty output (caller guards).
    """
    return {tenor: obs.yield_bps / 10_000.0 for tenor, obs in obs_map.items()}


def _latest_observation_date(obs_map: dict[str, Observation]) -> date | None:
    """Pick the freshest ``observation_date`` across the map (used for survey release)."""
    if not obs_map:
        return None
    return max(obs.observation_date for obs in obs_map.values())


async def load_live_exp_inflation_kwargs(
    country_code: str,
    observation_date: date,
    *,
    fred: FredConnector | None,
) -> dict[str, Any] | None:
    """Return kwargs for :func:`build_canonical`, or ``None`` if no live source.

    ``country_code == "US"`` + ``fred`` non-None is the only path that
    returns a populated dict today. Any connector error → ``None``
    (logged). Any non-US code → ``None`` (no log; expected).
    """
    if country_code != "US":
        return None
    if fred is None:
        log.info(
            "expinf_loader.fred_unavailable",
            country=country_code,
            observation_date=observation_date.isoformat(),
        )
        return None

    # BEI leg — FRED ``T5YIE`` / ``T10YIE`` (market-published breakeven).
    bei_obj = None
    try:
        nominal_map = await fred.fetch_yield_curve_nominal("US", observation_date)
        bei_map = await fred.fetch_bei_series("US", observation_date)
    except _TRANSIENT_ERRORS as exc:
        log.warning(
            "expinf_loader.bei_fetch_error",
            country=country_code,
            observation_date=observation_date.isoformat(),
            error=str(exc),
        )
        nominal_map, bei_map = {}, {}

    if bei_map:
        try:
            bei_obj = compute_bei_us(
                nominal_yields=_observations_to_decimal(nominal_map),
                bei_market=_observations_to_decimal(bei_map),
                observation_date=observation_date,
                linker_connector="fred",
            )
        except _TRANSIENT_ERRORS as exc:
            log.warning(
                "expinf_loader.bei_compose_error",
                country=country_code,
                error=str(exc),
            )
            bei_obj = None

    # Survey leg — FRED Michigan 1Y + Cleveland Fed model 10Y.
    survey_obj = None
    try:
        survey_map = await fred.fetch_survey_inflation("US", observation_date)
    except _TRANSIENT_ERRORS as exc:
        log.warning(
            "expinf_loader.survey_fetch_error",
            country=country_code,
            observation_date=observation_date.isoformat(),
            error=str(exc),
        )
        survey_map = {}

    if survey_map:
        horizons = {
            "1Y": survey_map["MICH_1Y"].yield_bps / 10_000.0 if "MICH_1Y" in survey_map else None,
            "10Y": survey_map["SPF_10Y"].yield_bps / 10_000.0 if "SPF_10Y" in survey_map else None,
        }
        horizons_clean = {k: v for k, v in horizons.items() if v is not None}
        release_date = _latest_observation_date(survey_map)
        if horizons_clean and release_date is not None:
            try:
                survey_obj = compute_survey_us(
                    survey_horizons=horizons_clean,
                    observation_date=observation_date,
                    survey_release_date=release_date,
                )
            except _TRANSIENT_ERRORS as exc:
                log.warning(
                    "expinf_loader.survey_compose_error",
                    country=country_code,
                    error=str(exc),
                )
                survey_obj = None

    if bei_obj is None and survey_obj is None:
        log.info(
            "expinf_loader.no_sources",
            country=country_code,
            observation_date=observation_date.isoformat(),
        )
        return None

    return {
        "country_code": country_code,
        "observation_date": observation_date,
        "bei": bei_obj,
        "survey": survey_obj,
        "bc_target_pct": _US_BC_TARGET_PCT,
    }
