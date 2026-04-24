"""Live expected-inflation loader — Sprint Q CAL-EXPINF-LIVE-ASSEMBLER-WIRING.

Closes the wiring gap at `src/sonar/overlays/live_assemblers.py:625`
where the daily-overlays `OverlayBundle.expected_inflation` has been
hard-coded to ``None`` since Sprint 7F. Assembles kwargs for
:func:`sonar.overlays.expected_inflation.build_canonical` from live
connector surfaces so the overlay pipeline emits the canonical
``EXPINF_CANONICAL`` `IndexValue` row the M3 classifier reads.

Scope (Sprint Q + Sprint Q.1, 2026-04-24):

- **US**: FRED BEI (``T5YIE`` / ``T10YIE``) + FRED survey (Michigan 1Y
  + Cleveland Fed model 10Y). Sprint Q → M3 DEGRADED → FULL.
- **EA cohort** (``EA`` + ``DE`` / ``FR`` / ``IT`` / ``ES`` / ``PT`` /
  ``NL``): ECB SDW SPF HICP point forecasts (1Y + 2Y + LT horizons).
  Sprint Q.1 → M3 DEGRADED → FULL. Non-``EA`` members carry
  ``SPF_AREA_PROXY`` flag per probe finding §3.1
  (``docs/backlog/probe-results/sprint-q-1-ecb-spf-probe.md``).
- **Other** (GB / JP / CA): returns ``None`` — country-specific CALs
  open (``CAL-EXPINF-GB-BOE-ILG-SPF`` / ``CAL-EXPINF-SURVEY-JP-CA``).

Returns ``dict[str, Any] | None`` — the shape expected by
:attr:`sonar.pipelines.daily_overlays.OverlayBundle.expected_inflation`
(kwargs dict passed via ``**bundle.expected_inflation`` into
``build_canonical``). Graceful fallback on connector errors: logs at
``info`` / ``warning`` and returns ``None`` so the overlay pipeline
routes a structured skip rather than crashing the run.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

import httpx
import structlog

from sonar.connectors.ecb_sdw import ECB_SPF_COHORT, ExpInflationSurveyObservation
from sonar.indices.monetary.exp_inflation_writers import persist_survey_row
from sonar.overlays.exceptions import OverlayError
from sonar.overlays.expected_inflation import (
    METHODOLOGY_VERSION_SURVEY,
    compute_bei_us,
    compute_survey_spf,
    compute_survey_us,
)

if TYPE_CHECKING:
    from datetime import date

    from sqlalchemy.orm import Session

    from sonar.connectors.base import Observation
    from sonar.connectors.ecb_sdw import EcbSdwConnector
    from sonar.connectors.fred import FredConnector


__all__ = ["load_live_exp_inflation_kwargs"]


log = structlog.get_logger()


# US Fed long-run inflation target (FOMC Statement on Longer-Run Goals).
# Used as ``bc_target_pct`` input to :func:`build_canonical` anchor
# computation. Non-US country targets land via future per-country wiring.
_US_BC_TARGET_PCT: float = 0.02

# ECB 2% HICP symmetric target (post-2021 strategy review). Applies to
# the euro-area aggregate and every EA member. Non-EA targets live in
# ``config/bc_targets.yaml`` but Sprint Q.1 keeps the constant local
# to avoid pulling the YAML loader into the overlays hot path — M3
# persists its own copy via ``_resolve_bc_target_pct`` independently.
_EA_BC_TARGET_PCT: float = 0.02

# Look-back window for the most recent SPF quarterly release. SPF
# publishes 4 times per year (P3M periods in SDW) with a release lag of
# up to ~6 weeks after the quarter starts. 210 days (≈ 7 months) guarantees
# at least one fully-published quarterly release regardless of calendar
# alignment between ``observation_date`` and the nearest quarter start —
# SDW's ``startPeriod`` is compared to ``TIME_PERIOD`` (quarter anchor),
# so a lookback shorter than ~95 days around a quarter boundary drops
# the latest quarter.
_SPF_LOOKBACK_DAYS: int = 210


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
    ecb_sdw: EcbSdwConnector | None = None,
    session: Session | None = None,
) -> dict[str, Any] | None:
    """Return kwargs for :func:`build_canonical`, or ``None`` if no live source.

    ``country_code == "US"`` + ``fred`` non-None routes US through
    FRED BEI + FRED survey (Sprint Q).

    ``country_code`` in the EA SPF cohort + ``ecb_sdw`` non-None routes
    through the ECB SDW SPF survey leg (Sprint Q.1). Non-``EA`` members
    of the cohort carry the ``SPF_AREA_PROXY`` flag. When ``session``
    is also provided, the composed :class:`~sonar.overlays.
    expected_inflation.ExpInfSurvey` is persisted to
    ``exp_inflation_survey`` (idempotent; duplicates skipped).

    Any connector error → ``None`` (logged). Any unsupported
    country → ``None`` (no log; expected).
    """
    if country_code == "US":
        return await _load_us_kwargs(country_code, observation_date, fred=fred)
    if country_code in ECB_SPF_COHORT:
        return await _load_ea_spf_kwargs(
            country_code,
            observation_date,
            ecb_sdw=ecb_sdw,
            session=session,
        )
    return None


async def _load_us_kwargs(
    country_code: str,
    observation_date: date,
    *,
    fred: FredConnector | None,
) -> dict[str, Any] | None:
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


async def _load_ea_spf_kwargs(
    country_code: str,
    observation_date: date,
    *,
    ecb_sdw: EcbSdwConnector | None,
    session: Session | None = None,
) -> dict[str, Any] | None:
    """Build kwargs for the EA cohort via ECB SDW SPF (Sprint Q.1).

    ``EA`` → direct EA-aggregate survey; DE/FR/IT/ES/PT/NL → same data
    tagged with the ``SPF_AREA_PROXY`` flag. Returns ``None`` on
    connector absence, transient error, or an SPF window that produced
    no usable observations (caller logs at info / warning).
    """
    if ecb_sdw is None:
        log.info(
            "expinf_loader.ecb_sdw_unavailable",
            country=country_code,
            observation_date=observation_date.isoformat(),
        )
        return None

    window_start = observation_date - timedelta(days=_SPF_LOOKBACK_DAYS)
    try:
        observations = await ecb_sdw.fetch_survey_expected_inflation(
            country=country_code,
            start=window_start,
            end=observation_date,
        )
    except _TRANSIENT_ERRORS as exc:
        log.warning(
            "expinf_loader.spf_fetch_error",
            country=country_code,
            observation_date=observation_date.isoformat(),
            error=str(exc),
        )
        return None

    survey_horizons, survey_release_date = _select_latest_spf_horizons(observations)
    if not survey_horizons or survey_release_date is None:
        log.info(
            "expinf_loader.spf_no_usable_observations",
            country=country_code,
            observation_date=observation_date.isoformat(),
            n_observations=len(observations),
        )
        return None

    is_area_proxy = country_code != "EA"
    try:
        survey_obj = compute_survey_spf(
            country_code=country_code,
            survey_horizons=survey_horizons,
            observation_date=observation_date,
            survey_release_date=survey_release_date,
            is_area_proxy=is_area_proxy,
        )
    except _TRANSIENT_ERRORS as exc:
        log.warning(
            "expinf_loader.spf_compose_error",
            country=country_code,
            error=str(exc),
        )
        return None

    if session is not None:
        try:
            persist_survey_row(
                session,
                survey_obj,
                methodology_version=METHODOLOGY_VERSION_SURVEY,
            )
        except Exception as exc:
            log.warning(
                "expinf_loader.spf_persist_error",
                country=country_code,
                error=str(exc),
            )

    return {
        "country_code": country_code,
        "observation_date": observation_date,
        "bei": None,
        "survey": survey_obj,
        "bc_target_pct": _EA_BC_TARGET_PCT,
    }


def _select_latest_spf_horizons(
    observations: list[ExpInflationSurveyObservation],
) -> tuple[dict[str, float], date | None]:
    """Extract the freshest SPF survey quarter's canonical horizons.

    SPF emits one observation per (survey_quarter, horizon_year). We
    keep only the latest quarter with data, map the derived tenors
    (``1Y`` / ``2Y`` / ``LTE``) to decimal yields, and return them
    alongside the survey release date (the Monday of the survey
    quarter, per ECB convention).

    Canonical units: SDW publishes ``PCPA`` (% per annum); we divide by
    100 to reach decimal (units.md §Yields). Horizons without a derived
    tenor (e.g. 0Y current-year, or back-fill target-year rows) are
    skipped.
    """
    if not observations:
        return {}, None
    latest_date = max(obs.survey_date for obs in observations)
    horizons: dict[str, float] = {}
    for obs in observations:
        if obs.survey_date != latest_date:
            continue
        if obs.tenor in {"1Y", "2Y", "LTE"}:
            horizons[obs.tenor] = obs.value_pct / 100.0
    return horizons, latest_date
