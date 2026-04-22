"""Monetary input builders (CAL-100, week6 sprint 2b).

Wires L0 connectors → M1/M2/M4 Inputs dataclasses so L3 compute modules
receive fully-populated inputs for a given ``(country, observation_date)``.

Design constraints:

- Shadow rate: spec §2 precondition allows ``shadow_rate := policy_rate``
  when policy is above the 0.5 % ZLB cutoff. Both US and EA currently
  sit above; the Krippner/Wu-Xia connector stays deferred (CAL-099).
- r* + central-bank inflation target: YAML workaround per
  :mod:`sonar.indices.monetary._config`; staleness flag emitted by the
  consumer when appropriate.
- Coverage this sprint: **US** for M1/M2/M4 and **EA** for M1. M2/M4 EA
  require OECD EO / AMECO / VSTOXX wiring deferred to Week 7. Calls for
  those country/index combinations raise ``NotImplementedError`` with a
  pointer to the outstanding CAL items.
- Histories: monthly cadence samples over ``history_years`` (30Y
  canonical, 15Y Tier-4 fallback). The builder resamples daily/weekly
  level series to end-of-month observations using the most-recent prior
  point per month.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

import structlog

from sonar.indices.monetary._config import (
    resolve_inflation_target,
    resolve_inflation_target_convention,
    resolve_r_star,
)
from sonar.indices.monetary.m1_effective_rates import (
    DEFAULT_LOOKBACK_YEARS as M1_DEFAULT_LOOKBACK_YEARS,
    ZLB_THRESHOLD_PCT,
    M1EffectiveRatesInputs,
)
from sonar.indices.monetary.m2_taylor_gaps import (
    DEFAULT_LOOKBACK_YEARS as M2_DEFAULT_LOOKBACK_YEARS,
    M2TaylorGapsInputs,
)
from sonar.indices.monetary.m4_fci import (
    DEFAULT_LOOKBACK_YEARS as M4_DEFAULT_LOOKBACK_YEARS,
    M4FciInputs,
)
from sonar.overlays.exceptions import InsufficientDataError

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from sonar.connectors.boc import BoCConnector
    from sonar.connectors.boe_database import BoEDatabaseConnector
    from sonar.connectors.boj import BoJConnector
    from sonar.connectors.cbo import CboConnector
    from sonar.connectors.ecb_sdw import EcbSdwConnector
    from sonar.connectors.fred import FredConnector
    from sonar.connectors.nationalbanken import NationalbankenConnector
    from sonar.connectors.norgesbank import NorgesBankConnector
    from sonar.connectors.oecd_eo import OECDEOConnector
    from sonar.connectors.rba import RBAConnector
    from sonar.connectors.rbnz import RBNZConnector
    from sonar.connectors.riksbank import RiksbankConnector
    from sonar.connectors.snb import SNBConnector
    from sonar.connectors.te import TEConnector


log = structlog.get_logger()


__all__ = [
    "MonetaryInputsBuilder",
    "build_m1_au_inputs",
    "build_m1_ca_inputs",
    "build_m1_ch_inputs",
    "build_m1_dk_inputs",
    "build_m1_ea_inputs",
    "build_m1_gb_inputs",
    "build_m1_jp_inputs",
    "build_m1_no_inputs",
    "build_m1_nz_inputs",
    "build_m1_se_inputs",
    "build_m1_uk_inputs",
    "build_m1_us_inputs",
    "build_m2_au_inputs",
    "build_m2_ca_inputs",
    "build_m2_ch_inputs",
    "build_m2_dk_inputs",
    "build_m2_ea_inputs",
    "build_m2_gb_inputs",
    "build_m2_jp_inputs",
    "build_m2_no_inputs",
    "build_m2_nz_inputs",
    "build_m2_se_inputs",
    "build_m2_us_inputs",
    "build_m4_au_inputs",
    "build_m4_ca_inputs",
    "build_m4_ch_inputs",
    "build_m4_dk_inputs",
    "build_m4_jp_inputs",
    "build_m4_no_inputs",
    "build_m4_nz_inputs",
    "build_m4_se_inputs",
    "build_m4_us_inputs",
]

# GB OECD-mirror series on FRED — monthly, reliable backfill for BoE IADB
# which is currently gated by Akamai anti-bot (Sprint I empirical probe).
FRED_GB_BANK_RATE_SERIES: str = "IRSTCI01GBM156N"
FRED_GB_GILT_10Y_SERIES: str = "IRLTLT01GBM156N"

# Deprecated UK-named aliases per ADR-0007. Preserved so external callers
# (and test fakes) that still import the UK names keep functioning during
# the transition window. Removal planned Week 10 Day 1.
FRED_UK_BANK_RATE_SERIES: str = FRED_GB_BANK_RATE_SERIES
FRED_UK_GILT_10Y_SERIES: str = FRED_GB_GILT_10Y_SERIES

# JP OECD-mirror series on FRED — monthly, last-resort backfill when the
# TE primary + BoJ native paths are both unavailable (Sprint L cascade).
FRED_JP_BANK_RATE_SERIES: str = "IRSTCI01JPM156N"
FRED_JP_JGB_10Y_SERIES: str = "IRLTLT01JPM156N"

# CA OECD-mirror series on FRED — monthly, last-resort backfill when both
# TE primary and BoC Valet native are unavailable (Sprint S cascade).
FRED_CA_BANK_RATE_SERIES: str = "IRSTCI01CAM156N"
FRED_CA_GOC_10Y_SERIES: str = "IRLTLT01CAM156N"

# AU OECD-mirror series on FRED — monthly, last-resort backfill when both
# TE primary and RBA F1 native are unavailable (Sprint T cascade).
FRED_AU_CASH_RATE_SERIES: str = "IRSTCI01AUM156N"
FRED_AU_AGB_10Y_SERIES: str = "IRLTLT01AUM156N"

# NZ OECD-mirror series on FRED — monthly, last-resort backfill when both
# TE primary and RBNZ B2 native are unavailable (Sprint U cascade; RBNZ
# ships as a wire-ready scaffold pending CAL-NZ-RBNZ-TABLES).
FRED_NZ_OCR_SERIES: str = "IRSTCI01NZM156N"
FRED_NZ_GOVT_10Y_SERIES: str = "IRLTLT01NZM156N"

# CH OECD-mirror series on FRED — monthly, last-resort backfill when both
# TE primary and SNB native are unavailable (Sprint V cascade). The
# IRSTCI01CHM156N mirror is monthly-lagged (Sprint V probe observed the
# last update on 2024-03) so the stale-flag cost is explicit.
FRED_CH_POLICY_RATE_SERIES: str = "IRSTCI01CHM156N"
FRED_CH_CONFED_10Y_SERIES: str = "IRLTLT01CHM156N"

# NO OECD-mirror series on FRED — monthly, last-resort backfill when
# both TE primary and Norges Bank DataAPI native are unavailable
# (Sprint X-NO cascade). The IRSTCI01NOM156N mirror tracks real-time
# within ~1 month at Sprint X-NO probe (2026-04-22 saw 2026-03 as the
# latest observation — freshest OECD mirror of any Tier-1 country).
FRED_NO_POLICY_RATE_SERIES: str = "IRSTCI01NOM156N"
FRED_NO_GOVT_10Y_SERIES: str = "IRLTLT01NOM156N"

# SE OECD-mirror series on FRED — monthly, last-resort backfill when
# both TE primary and Riksbank Swea native are unavailable (Sprint W-SE
# cascade). The IRSTCI01SEM156N call-money mirror was **discontinued at
# 2020-10-01** — Sprint W-SE probe 2026-04-22 confirmed the series has
# been frozen for ~5.5 years, so the stale-flag pair
# (SE_POLICY_RATE_FRED_FALLBACK_STALE + CALIBRATION_STALE) fires on
# virtually every realistic window. The companion 10Y mirror
# IRLTLT01SEM156N remains live (monthly, last observation 2026-03 at
# probe). Keeping the policy-rate series wired anyway preserves the
# cascade shape across countries so a future OECD restart / pivot is
# transparently covered.
FRED_SE_POLICY_RATE_SERIES: str = "IRSTCI01SEM156N"
FRED_SE_GOVT_10Y_SERIES: str = "IRLTLT01SEM156N"

# DK OECD-mirror series on FRED — monthly, last-resort backfill when
# both TE primary and Nationalbanken Statbank native are unavailable
# (Sprint Y-DK cascade). The IRSTCI01DKM156N call-money mirror is
# fresh at probe (2026-04-22 saw 2025-12 as the latest observation —
# ~4-month lag, comparable to the NO mirror's freshness; substantially
# better than the SE mirror's 5.5-year discontinuation). The cascade
# still pairs it with CALIBRATION_STALE so the monthly-vs-daily
# cadence delta surfaces explicitly. The companion 10Y mirror
# IRLTLT01DKM156N tracks similarly fresh (2026-02 latest obs at
# probe).
FRED_DK_POLICY_RATE_SERIES: str = "IRSTCI01DKM156N"
FRED_DK_GOVT_10Y_SERIES: str = "IRLTLT01DKM156N"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _DatedValue:
    """Minimal (date, value) pair used by the resampler."""

    observation_date: date
    value: float


def _latest_on_or_before(obs: Sequence[_DatedValue], anchor: date) -> _DatedValue | None:
    """Return the most-recent observation at or before ``anchor``."""
    usable = [o for o in obs if o.observation_date <= anchor]
    if not usable:
        return None
    return max(usable, key=lambda o: o.observation_date)


def _resample_monthly(obs: Sequence[_DatedValue], anchor: date, n_months: int) -> list[float]:
    """Sample ``obs`` at the last day of each month up to ``anchor``.

    Returns a list of length ≤ ``n_months`` (shorter when history starts
    inside the window). Uses forward-fill semantics: month M's sample is
    the most recent observation on or before the last day of M.
    """
    if not obs:
        return []
    sorted_obs = sorted(obs, key=lambda o: o.observation_date)
    year = anchor.year
    month = anchor.month
    out_rev: list[float] = []
    for _ in range(n_months):
        month_end = _last_day_of_month(year, month)
        cutoff = min(month_end, anchor)
        latest = _latest_on_or_before(sorted_obs, cutoff)
        if latest is None:
            break
        out_rev.append(latest.value)
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    out_rev.reverse()
    return out_rev


def _last_day_of_month(year: int, month: int) -> date:
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - timedelta(days=1)


def _to_dated(obs_iter: Sequence[object], value_attr: str = "value") -> list[_DatedValue]:
    """Convert connector observations to ``_DatedValue`` rows.

    Supports any record with ``observation_date`` + a value attribute
    (``value`` by default; pass ``"yield_bps"``, ``"gap"``, etc. when
    different).
    """
    out: list[_DatedValue] = []
    for o in obs_iter:
        d = getattr(o, "observation_date")  # noqa: B009 - attribute name is dynamic here
        v = getattr(o, value_attr)
        out.append(_DatedValue(observation_date=d, value=float(v)))
    return out


def _m2_blocked_msg(
    *,
    country_code: str,
    sprint_label: str,
    cpi_cal_item: str,
    forecast_cal_item: str,
    output_gap_wired: bool,
    extra_tail: str = "",
) -> str:
    """Build the narrowed ``InsufficientDataError`` message for a T1 M2 scaffold.

    Sprint C (Week 10) delivered the output-gap half of
    ``CAL-M2-T1-OUTPUT-GAP-EXPANSION``. The raise message per country
    now reflects which components remain blockers: when OECD EO
    successfully returned a value for the anchor date, the message
    explicitly acknowledges that output-gap is wired and limits the
    blocker to CPI + inflation-forecast.
    """
    if output_gap_wired:
        core = (
            f"M2 {country_code} builder (scaffold shipped {sprint_label}; "
            f"output-gap live via OECD EO per Sprint C Week 10 — "
            f"CAL-M2-T1-OUTPUT-GAP-EXPANSION) still requires CPI YoY + "
            f"inflation-forecast {country_code} connectors that are not "
            f"yet wired (see {cpi_cal_item} / {forecast_cal_item})."
        )
    else:
        core = (
            f"M2 {country_code} builder (scaffold shipped {sprint_label}) "
            f"still requires CPI YoY + output-gap + inflation-forecast "
            f"{country_code} connectors (see {cpi_cal_item} / "
            f"CAL-M2-T1-OUTPUT-GAP-EXPANSION / {forecast_cal_item}) — "
            f"OECD EO unavailable or connector not injected at this "
            f"call site, so output-gap is not wired for this invocation."
        )
    tail = f"{extra_tail} " if extra_tail else ""
    return f"{core} {tail}Raises so the pipeline skips M2 {country_code} cleanly."


async def _assemble_m2_full_compute(
    *,
    country_code: str,
    observation_date: date,
    policy_hist: Sequence[_DatedValue],
    cascade_flags: tuple[str, ...],
    cascade_sources: tuple[str, ...],
    cpi_observations: Sequence[object],  # list[TEIndicatorObservation] — runtime dep
    forecast_12m_pct: float | None,
    forecast_flags: tuple[str, ...],
    output_gap_pct: float | None,
    history_years: int,
    extra_flags: tuple[str, ...] = (),
) -> M2TaylorGapsInputs:
    """Assemble M2 inputs for a non-US T1 country in full-compute mode.

    Week 10 Sprint F helper. All four Taylor-rule components
    (policy_rate, inflation_yoy, output_gap, inflation_target + r* from
    YAML) must be present; forecast + prev_policy are optional (the
    Taylor-forward and Taylor-inertia variants degrade gracefully in
    :mod:`m2_taylor_gaps`).

    Raises :class:`InsufficientDataError` when any of the four required
    components is missing — callers' per-country M2 scaffold raises
    pass through unchanged.

    Flags composition:

    - ``cascade_flags`` from the M1 policy-rate cascade (e.g.
      ``CA_BANK_RATE_TE_PRIMARY``) propagate to M2 so operators can
      trace the policy-rate source without re-querying.
    - ``{COUNTRY_CODE}_M2_CPI_TE_LIVE`` / ``CPI_UNAVAILABLE`` tracks
      the TE CPI path.
    - ``{COUNTRY_CODE}_M2_INFLATION_FORECAST_TE_LIVE`` /
      ``FORECAST_UNAVAILABLE`` tracks the forecast wiring.
    - ``{COUNTRY_CODE}_M2_OUTPUT_GAP_OECD_EO_LIVE`` /
      ``OUTPUT_GAP_UNAVAILABLE`` tracks the OECD EO path.
    - ``{COUNTRY_CODE}_M2_FULL_COMPUTE_LIVE`` emitted when all four
      optional observability flags are on the LIVE branch.
    - ``extra_flags`` appended last for country-specific
      deviations (e.g. NZ quarterly CPI, AU sparse monthly,
      DK imported EUR-peg inflation target).

    Unit convention matches :func:`build_m2_us_inputs`:
    ``inflation_yoy_pct`` + ``inflation_forecast_2y_pct`` in decimal
    (``0.024`` = 2.4%); ``output_gap_pct`` in percentage points
    (``-0.5`` = -0.5%); ``policy_rate_pct`` in decimal
    (``0.025`` = 2.5%); ``inflation_target_pct`` + ``r_star_pct`` in
    decimal per the YAML.
    """
    flags: list[str] = list(cascade_flags)

    latest_policy = _latest_on_or_before(policy_hist, observation_date)
    if latest_policy is None:
        msg = f"{country_code} policy rate: no observation at or before anchor"
        raise InsufficientDataError(msg)
    policy_rate_pct = latest_policy.value / 100.0

    prior_anchor = observation_date - timedelta(days=30)
    prev_policy_obs = _latest_on_or_before(policy_hist, prior_anchor)
    prev_policy_rate_pct = prev_policy_obs.value / 100.0 if prev_policy_obs is not None else None

    cpi_list = list(cpi_observations)
    if not cpi_list:
        flags.append(f"{country_code}_M2_CPI_UNAVAILABLE")
        msg = (
            f"M2 {country_code} builder (Sprint F full compute) — CPI YoY "
            f"unavailable from TE. Cannot compute Taylor gap."
        )
        raise InsufficientDataError(msg)
    latest_cpi = cpi_list[-1]
    cpi_raw_value = getattr(latest_cpi, "value", None)
    if cpi_raw_value is None:
        msg = (
            f"M2 {country_code} builder: latest TE CPI observation is missing "
            f"a .value attribute — connector contract violated."
        )
        raise InsufficientDataError(msg)
    inflation_yoy_pct = float(cpi_raw_value) / 100.0  # TE value is %; to decimal
    flags.append(f"{country_code}_M2_CPI_TE_LIVE")

    if output_gap_pct is None:
        flags.append(f"{country_code}_M2_OUTPUT_GAP_UNAVAILABLE")
        msg = (
            f"M2 {country_code} builder (Sprint F full compute) — OECD EO "
            f"output gap unavailable. Cannot compute Taylor gap."
        )
        raise InsufficientDataError(msg)
    flags.append(f"{country_code}_M2_OUTPUT_GAP_OECD_EO_LIVE")

    r_star_pct, is_proxy = resolve_r_star(country_code)
    if is_proxy:
        flags.append("R_STAR_PROXY")
    inflation_target_pct = resolve_inflation_target(country_code)
    target_convention = resolve_inflation_target_convention(country_code)
    if target_convention == "imported_eur_peg":
        flags.append(f"{country_code}_INFLATION_TARGET_IMPORTED_FROM_EA")

    flags.extend(forecast_flags)
    inflation_forecast_2y_pct = forecast_12m_pct / 100.0 if forecast_12m_pct is not None else None

    source_connector = tuple(dict.fromkeys([*cascade_sources, "te", "oecd_eo"]))

    if inflation_forecast_2y_pct is not None:
        flags.append(f"{country_code}_M2_FULL_COMPUTE_LIVE")
    else:
        flags.append(f"{country_code}_M2_PARTIAL_COMPUTE")

    flags.extend(extra_flags)

    return M2TaylorGapsInputs(
        country_code=country_code,
        observation_date=observation_date,
        policy_rate_pct=policy_rate_pct,
        inflation_yoy_pct=inflation_yoy_pct,
        inflation_target_pct=inflation_target_pct,
        output_gap_pct=output_gap_pct,
        r_star_pct=r_star_pct,
        prev_policy_rate_pct=prev_policy_rate_pct,
        inflation_forecast_2y_pct=inflation_forecast_2y_pct,
        lookback_years=history_years,
        source_connector=source_connector,
        upstream_flags=tuple(flags),
        output_gap_source="OECD_EO",
    )


async def _try_fetch_inflation_forecast_12m(
    te: TEConnector | None,
    country_code: str,
    observation_date: date,
    fetch_method_name: str,
) -> tuple[float | None, tuple[str, ...]]:
    """Fetch the 12m-ahead inflation forecast via ``te.fetch_*_inflation_forecast``.

    Soft-fails to ``(None, ("{COUNTRY}_M2_INFLATION_FORECAST_UNAVAILABLE",))``
    when the TE connector is absent or the forecast endpoint raises.
    Otherwise returns ``(forecast_12m_pct_as_percent,
    ("{COUNTRY}_M2_INFLATION_FORECAST_TE_LIVE",))`` with ``forecast_12m_pct``
    still in percent (caller does the /100 conversion once at the
    :class:`M2TaylorGapsInputs` boundary).
    """
    if te is None:
        return None, (f"{country_code}_M2_INFLATION_FORECAST_UNAVAILABLE",)
    from sonar.overlays.exceptions import DataUnavailableError  # noqa: PLC0415

    fetch = getattr(te, fetch_method_name, None)
    if fetch is None:
        return None, (f"{country_code}_M2_INFLATION_FORECAST_UNAVAILABLE",)
    try:
        fcst = await fetch(observation_date)
    except DataUnavailableError:
        return None, (f"{country_code}_M2_INFLATION_FORECAST_UNAVAILABLE",)
    return fcst.forecast_12m_pct, (f"{country_code}_M2_INFLATION_FORECAST_TE_LIVE",)


async def _try_fetch_cpi_yoy(
    te: TEConnector | None,
    start: date,
    end: date,
    fetch_method_name: str,
) -> Sequence[object]:
    """Fetch the TE CPI YoY window via ``te.fetch_*_cpi_yoy``. Soft-fail on absence."""
    if te is None:
        return ()
    from sonar.overlays.exceptions import DataUnavailableError  # noqa: PLC0415

    fetch = getattr(te, fetch_method_name, None)
    if fetch is None:
        return ()
    try:
        result: Sequence[object] = await fetch(start, end)
    except DataUnavailableError:
        return ()
    return result


async def _try_fetch_oecd_output_gap_pct(
    oecd_eo: OECDEOConnector | None,
    country_code: str,
    observation_date: date,
) -> float | None:
    """Fetch the latest OECD EO output gap (%) — soft-fail on anything.

    Sprint C wires OECD EO as the canonical output-gap source for every
    T1 country that lacks a native quarterly potential-GDP feed (i.e.
    all T1 except US, which keeps CBO GDPPOT). Callers in the per-
    country M2 builders use this helper to:

    - confirm the output-gap component is wired end-to-end (log a
      structured ``monetary_builder.m2.output_gap_wired`` info line);
    - leave the ``InsufficientDataError`` raise in place with a
      narrower message, since CPI + inflation-forecast are tracked
      separately under per-country CAL items.

    Returns ``None`` when either the connector is not supplied, the
    country is not mapped, or the OECD EO endpoint soft-fails.
    """
    if oecd_eo is None:
        return None
    from sonar.connectors.oecd_eo import is_t1_covered  # noqa: PLC0415

    if not is_t1_covered(country_code):
        return None
    obs = await oecd_eo.fetch_latest_output_gap(country_code, observation_date)
    if obs is None:
        return None
    log.info(
        "monetary_builder.m2.output_gap_wired",
        country=country_code,
        observation_year=obs.observation_date.year,
        gap_pct=round(obs.gap_pct, 3),
        source="OECD_EO",
    )
    return obs.gap_pct


# ---------------------------------------------------------------------------
# M1 — US
# ---------------------------------------------------------------------------


async def build_m1_us_inputs(
    fred: FredConnector,
    observation_date: date,
    *,
    history_years: int = M1_DEFAULT_LOOKBACK_YEARS,
) -> M1EffectiveRatesInputs:
    """Assemble M1 US inputs from FRED connectors + r* YAML."""
    start = observation_date - timedelta(days=history_years * 366)

    upper = _to_dated(await fred.fetch_fed_funds_target_upper_us(start, observation_date))
    lower = _to_dated(await fred.fetch_fed_funds_target_lower_us(start, observation_date))
    policy_rate_pct = _us_policy_rate_pct(upper, lower, observation_date)

    exp_infl = _to_dated(await fred.fetch_umich_5y_inflation_us(start, observation_date))
    expected_inflation = _latest_on_or_before(exp_infl, observation_date)
    if expected_inflation is None:
        msg = "No UMich 5Y inflation-expectation observation at or before anchor"
        raise ValueError(msg)
    expected_inflation_5y_pct = expected_inflation.value / 100.0  # series in %, convert to decimal

    walcl = _to_dated(await fred.fetch_fed_balance_sheet_us(start, observation_date))
    gdp = _to_dated(await fred.fetch_real_gdp_us(start, observation_date))
    bs_now = _latest_on_or_before(walcl, observation_date)
    gdp_now = _latest_on_or_before(gdp, observation_date)
    bs_12m_ago = _latest_on_or_before(walcl, observation_date - timedelta(days=365))
    gdp_12m_ago = _latest_on_or_before(gdp, observation_date - timedelta(days=365))
    if None in (bs_now, gdp_now, bs_12m_ago, gdp_12m_ago):
        msg = "Missing WALCL/GDPC1 coverage for BS/GDP ratio construction"
        raise ValueError(msg)
    # WALCL is in $mn, GDPC1 in $bn (chained 2017) → multiply WALCL by 1e-3.
    assert bs_now is not None  # narrowed by the None check above
    assert gdp_now is not None
    assert bs_12m_ago is not None
    assert gdp_12m_ago is not None
    bs_gdp_current = (bs_now.value / 1_000.0) / gdp_now.value
    bs_gdp_prior = (bs_12m_ago.value / 1_000.0) / gdp_12m_ago.value

    r_star_pct, _is_proxy = resolve_r_star("US")

    real_shadow_hist = [
        p - expected_inflation_5y_pct
        for p in _resample_monthly(
            _us_policy_rate_history(upper, lower),
            observation_date,
            n_months=history_years * 12,
        )
    ]
    stance_hist = [r - r_star_pct for r in real_shadow_hist]
    bs_signal_hist = _balance_sheet_signal_history(walcl, gdp, observation_date, history_years * 12)

    return M1EffectiveRatesInputs(
        country_code="US",
        observation_date=observation_date,
        policy_rate_pct=policy_rate_pct,
        expected_inflation_5y_pct=expected_inflation_5y_pct,
        r_star_pct=r_star_pct,
        balance_sheet_pct_gdp_current=bs_gdp_current,
        balance_sheet_pct_gdp_12m_ago=bs_gdp_prior,
        real_shadow_rate_history=tuple(real_shadow_hist),
        stance_vs_neutral_history=tuple(stance_hist),
        balance_sheet_signal_history=tuple(bs_signal_hist),
        lookback_years=history_years,
        source_connector=("fred",),
    )


def _us_policy_rate_pct(
    upper: Sequence[_DatedValue], lower: Sequence[_DatedValue], anchor: date
) -> float:
    """Latest Fed funds target midpoint (decimal) at or before anchor."""
    u = _latest_on_or_before(upper, anchor)
    loader = _latest_on_or_before(lower, anchor)
    if u is None or loader is None:
        msg = "No Fed funds target (DFEDTARU/DFEDTARL) coverage at or before anchor"
        raise ValueError(msg)
    return (u.value + loader.value) / 2.0 / 100.0


def _us_policy_rate_history(
    upper: Sequence[_DatedValue], lower: Sequence[_DatedValue]
) -> list[_DatedValue]:
    """Midpoint series aligned on DFEDTARU dates."""
    lower_by_date = {o.observation_date: o.value for o in lower}
    out: list[_DatedValue] = []
    for u in upper:
        lo = lower_by_date.get(u.observation_date)
        if lo is None:
            continue
        out.append(
            _DatedValue(
                observation_date=u.observation_date,
                value=(u.value + lo) / 2.0 / 100.0,
            )
        )
    return out


def _balance_sheet_signal_history(
    walcl: Sequence[_DatedValue],
    gdp: Sequence[_DatedValue],
    anchor: date,
    n_months: int,
) -> list[float]:
    """Monthly YoY BS/GDP signal history, sign-flipped per M1 spec §4."""

    # Build BS/GDP ratio series at monthly cadence, then YoY-diff.
    def _ratio_at(d: date) -> float | None:
        b = _latest_on_or_before(walcl, d)
        g = _latest_on_or_before(gdp, d)
        if b is None or g is None or g.value == 0:
            return None
        return (b.value / 1_000.0) / g.value

    ratios: list[tuple[date, float]] = []
    year, month = anchor.year, anchor.month
    for _ in range(n_months + 12):  # +12 so we have room for YoY diff
        me = _last_day_of_month(year, month)
        r = _ratio_at(min(me, anchor))
        if r is None:
            break
        ratios.append((me, r))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    ratios.reverse()

    out: list[float] = []
    for i in range(12, len(ratios)):
        prior = ratios[i - 12][1]
        current = ratios[i][1]
        out.append(-(current - prior))
    return out[-n_months:]


# ---------------------------------------------------------------------------
# M1 — EA
# ---------------------------------------------------------------------------


async def build_m1_ea_inputs(
    ecb_sdw: EcbSdwConnector,
    observation_date: date,
    *,
    ea_gdp_eur_mn_resolver: Callable[[date], float] | None = None,
    history_years: int = M1_DEFAULT_LOOKBACK_YEARS,
) -> M1EffectiveRatesInputs:
    """Assemble M1 EA inputs from ECB SDW + r* YAML.

    ``ea_gdp_eur_mn_resolver`` is an injected resolver returning EA GDP
    in EUR millions for a given month-end date; defaults to a stationary
    ≈14_000_000 EUR mn placeholder so BS/GDP ratios are finite during
    Phase 1. Week 7 wires Eurostat ``namq_10_gdp`` for proper history.
    """
    start = observation_date - timedelta(days=history_years * 366)

    dfr = _to_dated(await ecb_sdw.fetch_dfr_rate(start, observation_date))
    policy = _latest_on_or_before(dfr, observation_date)
    if policy is None:
        msg = "No ECB DFR observation at or before anchor"
        raise ValueError(msg)
    policy_rate_pct = policy.value / 100.0

    bs = _to_dated(await ecb_sdw.fetch_eurosystem_balance_sheet(start, observation_date))
    bs_now = _latest_on_or_before(bs, observation_date)
    bs_12m_ago = _latest_on_or_before(bs, observation_date - timedelta(days=365))
    if bs_now is None or bs_12m_ago is None:
        msg = "Missing Eurosystem balance-sheet coverage for 12m window"
        raise ValueError(msg)

    if ea_gdp_eur_mn_resolver is None:

        def ea_gdp_eur_mn_resolver(_d: date) -> float:
            return 14_000_000.0

    bs_gdp_current = bs_now.value / ea_gdp_eur_mn_resolver(observation_date)
    bs_gdp_prior = bs_12m_ago.value / ea_gdp_eur_mn_resolver(observation_date - timedelta(days=365))

    r_star_pct, _is_proxy = resolve_r_star("EA")

    # Phase 1 workaround: expected 5Y inflation EA not wired — use ECB 2 %
    # target as a stationary proxy. Consumer emits
    # EXPECTED_INFLATION_PROXY. Swap to SPF/Consensus in Week 7+.
    expected_inflation_5y_pct = 0.02

    # Monthly DFR history (daily → month-end).
    dfr_monthly = _resample_monthly(dfr, observation_date, n_months=history_years * 12)
    real_shadow_hist = [p / 100.0 - expected_inflation_5y_pct for p in dfr_monthly]
    stance_hist = [r - r_star_pct for r in real_shadow_hist]

    # BS/GDP signal history with the same resolver-based GDP.
    bs_signal_hist = _ea_balance_sheet_signal_history(
        bs, ea_gdp_eur_mn_resolver, observation_date, history_years * 12
    )

    return M1EffectiveRatesInputs(
        country_code="EA",
        observation_date=observation_date,
        policy_rate_pct=policy_rate_pct,
        expected_inflation_5y_pct=expected_inflation_5y_pct,
        r_star_pct=r_star_pct,
        balance_sheet_pct_gdp_current=bs_gdp_current,
        balance_sheet_pct_gdp_12m_ago=bs_gdp_prior,
        real_shadow_rate_history=tuple(real_shadow_hist),
        stance_vs_neutral_history=tuple(stance_hist),
        balance_sheet_signal_history=tuple(bs_signal_hist),
        lookback_years=history_years,
        source_connector=("ecb_sdw",),
        upstream_flags=("EXPECTED_INFLATION_PROXY",),
    )


# ---------------------------------------------------------------------------
# M2 — EA aggregate (Week 10 Sprint L — CAL-M2-EA-AGGREGATE)
# ---------------------------------------------------------------------------


async def build_m2_ea_inputs(
    ecb_sdw: EcbSdwConnector,
    observation_date: date,
    *,
    te: TEConnector | None = None,
    oecd_eo: OECDEOConnector | None = None,
    history_years: int = M2_DEFAULT_LOOKBACK_YEARS,
) -> M2TaylorGapsInputs:
    """Assemble M2 EA aggregate inputs — full compute live (Sprint L).

    Week 10 Sprint L (CAL-M2-EA-AGGREGATE) wires the EA aggregate M2
    Taylor-gap compute on top of the Sprint F full-compute helper.
    Composition:

    1. **Policy rate** — ECB Deposit Facility Rate via
       :meth:`EcbSdwConnector.fetch_dfr_rate`. No cascade (DFR is the
       canonical ECB instrument — no fallback source wires into the
       Taylor rule). Cascade flag is a single-source marker
       ``EA_M2_POLICY_RATE_ECB_DFR_LIVE``.
    2. **HICP YoY** — Eurostat Monetary Union HICP via the Sprint L
       :meth:`TEConnector.fetch_ea_hicp_yoy` wrapper (symbol
       ``ECCPEMUY``, monthly cadence from 1991-01-31). Semantically
       HICP rather than per-country CPI; the helper's flag naming
       (``EA_M2_CPI_TE_LIVE``) is retained for uniformity with the 9
       Sprint F per-country builders — the methodology distinction is
       captured in the wrapper's docstring, not the flag.
    3. **Output gap** — OECD EO aggregate via
       :meth:`OECDEOConnector.fetch_latest_output_gap` with the EA →
       EA17 mapping established in Sprint C (EA19 / EA20 return
       ``NoRecordsFound`` for the GAP measure as of EO118).
    4. **Inflation forecast** — TE projection via the Sprint L
       :meth:`TEConnector.fetch_ea_inflation_forecast` wrapper (q4 ≈
       12m-ahead horizon, same ``ECCPEMUY`` symbol).

    ECB 2 % HICP medium-term target anchors ``inflation_target_pct``
    (via ``bc_targets.yaml:EA → ECB``). ``r_star_pct`` is -0.5 % from
    ``r_star_values.yaml:EA`` (Holston-Laubach-Williams EA equivalent
    Q4 2024; non-proxy — no ``R_STAR_PROXY`` flag).

    Fallback path (ECB SDW ICP + SPF) was pre-specified in the Sprint
    L brief §4 Commit 2 but **not shipped** per HALT-1 inversion: the
    2026-04-22 pre-flight probe confirmed TE coverage is complete for
    the EA aggregate (423 observations back to 1991-01-31), so the
    ECB SDW HICP / SPF extension remains Phase 2+ scope. If TE ever
    drifts or goes dark the cascade can be extended at the top of
    this builder without touching the ``_assemble_m2_full_compute``
    contract.
    """
    start = observation_date - timedelta(days=history_years * 366)

    dfr = _to_dated(await ecb_sdw.fetch_dfr_rate(start, observation_date))
    if not dfr:
        msg = (
            "M2 EA builder (Sprint L) — ECB DFR unavailable at or before "
            f"observation_date={observation_date.isoformat()}. Cannot "
            "compute Taylor gap without the policy-rate instrument."
        )
        raise InsufficientDataError(msg)

    cascade_flags: tuple[str, ...] = ("EA_M2_POLICY_RATE_ECB_DFR_LIVE",)
    cascade_sources: tuple[str, ...] = ("ecb_sdw",)

    cpi_obs = await _try_fetch_cpi_yoy(te, start, observation_date, "fetch_ea_hicp_yoy")
    forecast_12m_pct, forecast_flags = await _try_fetch_inflation_forecast_12m(
        te, "EA", observation_date, "fetch_ea_inflation_forecast"
    )
    gap_pct = await _try_fetch_oecd_output_gap_pct(oecd_eo, "EA", observation_date)

    return await _assemble_m2_full_compute(
        country_code="EA",
        observation_date=observation_date,
        policy_hist=dfr,
        cascade_flags=cascade_flags,
        cascade_sources=cascade_sources,
        cpi_observations=cpi_obs,
        forecast_12m_pct=forecast_12m_pct,
        forecast_flags=forecast_flags,
        output_gap_pct=gap_pct,
        history_years=history_years,
    )


# ---------------------------------------------------------------------------
# M1 — GB (Sprint I-patch — TE primary → BoE native → FRED stale-flagged)
# ---------------------------------------------------------------------------


async def _gb_bank_rate_cascade(
    start: date,
    end: date,
    *,
    te: TEConnector | None,
    boe: BoEDatabaseConnector | None,
    fred: FredConnector,
) -> tuple[list[_DatedValue], tuple[str, ...], tuple[str, ...]]:
    """Fetch GB Bank Rate via TE → BoE → FRED priority-first-wins cascade.

    Returns ``(series_pct, cascade_flags, source_connector_tuple)``.

    Priority ordering (first success wins):

    1. **TE primary** (``fetch_gb_bank_rate`` — daily, BoE-sourced via
       ``UKBRBASE``). Emits ``GB_BANK_RATE_TE_PRIMARY`` on success.
    2. **BoE native** (``fetch_bank_rate`` on the IADB CSV endpoint).
       Currently gated by Akamai anti-bot — wire-ready for future
       bypass. Emits ``GB_BANK_RATE_BOE_NATIVE`` on success.
    3. **FRED OECD mirror** (``IRSTCI01GBM156N`` — monthly lag).
       Last-resort fallback emitting both
       ``GB_BANK_RATE_FRED_FALLBACK_STALE`` and ``CALIBRATION_STALE`` to
       make the degradation auditable downstream.

    All three branches fail-open to the next source on
    :class:`DataUnavailableError` or empty payload. If all three return
    empty the cascade raises ``ValueError``.
    """
    from sonar.overlays.exceptions import DataUnavailableError  # noqa: PLC0415

    if te is not None:
        try:
            te_obs = await te.fetch_gb_bank_rate(start, end)
        except DataUnavailableError:
            te_obs = []
        if te_obs:
            return (
                [_DatedValue(o.observation_date, o.value) for o in te_obs],
                ("GB_BANK_RATE_TE_PRIMARY",),
                ("te",),
            )

    if boe is not None:
        try:
            boe_obs = await boe.fetch_bank_rate(start, end)
        except DataUnavailableError:
            boe_obs = []
        if boe_obs:
            return (
                [_DatedValue(o.observation_date, o.yield_bps / 100.0) for o in boe_obs],
                ("GB_BANK_RATE_BOE_NATIVE",),
                ("boe",),
            )

    fred_obs = await fred.fetch_series(FRED_GB_BANK_RATE_SERIES, start, end)
    if fred_obs:
        return (
            [_DatedValue(o.observation_date, o.yield_bps / 100.0) for o in fred_obs],
            ("GB_BANK_RATE_FRED_FALLBACK_STALE", "CALIBRATION_STALE"),
            ("fred",),
        )

    msg = "GB Bank Rate unavailable from TE, BoE, and FRED"
    raise ValueError(msg)


async def build_m1_gb_inputs(
    fred: FredConnector,
    observation_date: date,
    *,
    te: TEConnector | None = None,
    boe: BoEDatabaseConnector | None = None,
    history_years: int = M1_DEFAULT_LOOKBACK_YEARS,
) -> M1EffectiveRatesInputs:
    """Assemble M1 GB inputs via TE → BoE → FRED cascade + YAML r*/target.

    Sprint I-patch re-prioritised the cascade: TE primary (daily
    BoE-sourced via ``UKBRBASE``) fixes the signal-quality regression
    introduced by Sprint I Day 1 — where the FRED OECD mirror's monthly
    cadence lagged BoE's daily policy decisions. BoE IADB stays as the
    wire-ready secondary for post-Akamai unblock; FRED is the
    last-resort fallback that emits ``GB_BANK_RATE_FRED_FALLBACK_STALE``
    + ``CALIBRATION_STALE`` so downstream consumers can surface the
    degradation.

    GB-specific degradations (Phase 1):

    - ``expected_inflation_5y_pct`` defaults to the BoE CPI target (2 %)
      because no BoE breakeven-inflation mirror exists at this scope;
      emits ``EXPECTED_INFLATION_CB_TARGET`` flag.
    - ``balance_sheet_pct_gdp_*`` zero-seeded with ``GB_BS_GDP_PROXY_ZERO``
      flag — GB balance-sheet ratios require the BoE weekly bank-return
      aggregate which is not FRED-mirrored. Lands when IADB becomes
      reachable or when we wire an ONS-sourced GDP+APF composite.
    """
    start = observation_date - timedelta(days=history_years * 366)

    policy_hist, cascade_flags, cascade_sources = await _gb_bank_rate_cascade(
        start, observation_date, te=te, boe=boe, fred=fred
    )
    latest_policy = _latest_on_or_before(policy_hist, observation_date)
    if latest_policy is None:
        msg = "GB Bank Rate: no observation at or before anchor"
        raise ValueError(msg)
    policy_rate_pct = latest_policy.value / 100.0

    r_star_pct, _is_proxy = resolve_r_star("GB")  # is_proxy always True for GB
    expected_inflation_5y_pct = 0.02  # BoE CPI target; proxy

    policy_monthly_pct = _resample_monthly(
        policy_hist, observation_date, n_months=history_years * 12
    )
    real_shadow_hist = [p / 100.0 - expected_inflation_5y_pct for p in policy_monthly_pct]
    stance_hist = [r - r_star_pct for r in real_shadow_hist]

    flags: list[str] = [
        *cascade_flags,
        "R_STAR_PROXY",
        "EXPECTED_INFLATION_CB_TARGET",
        "GB_BS_GDP_PROXY_ZERO",
    ]

    return M1EffectiveRatesInputs(
        country_code="GB",
        observation_date=observation_date,
        policy_rate_pct=policy_rate_pct,
        expected_inflation_5y_pct=expected_inflation_5y_pct,
        r_star_pct=r_star_pct,
        balance_sheet_pct_gdp_current=0.0,
        balance_sheet_pct_gdp_12m_ago=0.0,
        real_shadow_rate_history=tuple(real_shadow_hist),
        stance_vs_neutral_history=tuple(stance_hist),
        balance_sheet_signal_history=tuple([0.0] * len(real_shadow_hist)),
        lookback_years=history_years,
        source_connector=cascade_sources,
        upstream_flags=tuple(flags),
    )


# ---------------------------------------------------------------------------
# M2 — GB (Week 10 Sprint F — full compute; scaffold-less — first-ship)
# ---------------------------------------------------------------------------


async def build_m2_gb_inputs(
    fred: FredConnector,
    observation_date: date,
    *,
    te: TEConnector | None = None,
    boe: BoEDatabaseConnector | None = None,
    oecd_eo: OECDEOConnector | None = None,
    history_years: int = M2_DEFAULT_LOOKBACK_YEARS,
) -> M2TaylorGapsInputs:
    """Assemble M2 GB inputs — full compute live (Week 10 Sprint F).

    GB has never had a Sprint C / Sprint T-style scaffold — this is
    the first-ship M2 GB builder. Composes:

    1. Bank Rate via :func:`_gb_bank_rate_cascade` (TE primary → BoE
       IADB native → FRED ``BOERUKA`` staleness fallback).
    2. CPI YoY via :meth:`TEConnector.fetch_gb_cpi_yoy` (ONS
       ``UKRPCJYR`` symbol — note: modern CPI under legacy TE code).
    3. 12m forecast via :meth:`TEConnector.fetch_gb_inflation_forecast`
       (BoE MPR projections inform the TE forecast blend).
    4. Output gap via OECD EO (``ref_area=GBR``).

    BoE's 2 % CPI target anchors ``inflation_target_pct``;
    ``r_star_pct`` is 0.5 % from ``r_star_values.yaml`` (BoE MPR +
    DMP Q4 2024 synthesis) with ``R_STAR_PROXY`` flag propagated.

    ``boe`` kwarg accepted for signature parity with
    :func:`build_m1_gb_inputs`; reserved for Phase 2+ when the BoE
    IADB-based CPI or forecast path lands.
    """
    start = observation_date - timedelta(days=history_years * 366)
    policy_hist, cascade_flags, cascade_sources = await _gb_bank_rate_cascade(
        start, observation_date, te=te, boe=boe, fred=fred
    )
    cpi_obs = await _try_fetch_cpi_yoy(te, start, observation_date, "fetch_gb_cpi_yoy")
    forecast_12m_pct, forecast_flags = await _try_fetch_inflation_forecast_12m(
        te, "GB", observation_date, "fetch_gb_inflation_forecast"
    )
    gap_pct = await _try_fetch_oecd_output_gap_pct(oecd_eo, "GB", observation_date)
    return await _assemble_m2_full_compute(
        country_code="GB",
        observation_date=observation_date,
        policy_hist=policy_hist,
        cascade_flags=cascade_flags,
        cascade_sources=cascade_sources,
        cpi_observations=cpi_obs,
        forecast_12m_pct=forecast_12m_pct,
        forecast_flags=forecast_flags,
        output_gap_pct=gap_pct,
        history_years=history_years,
    )


# ---------------------------------------------------------------------------
# M1 — JP (Sprint L — TE primary → BoJ native → FRED stale-flagged)
# ---------------------------------------------------------------------------


async def _jp_bank_rate_cascade(
    start: date,
    end: date,
    *,
    te: TEConnector | None,
    boj: BoJConnector | None,
    fred: FredConnector,
) -> tuple[list[_DatedValue], tuple[str, ...], tuple[str, ...]]:
    """Fetch JP Bank Rate via TE → BoJ → FRED priority-first-wins cascade.

    Returns ``(series_pct, cascade_flags, source_connector_tuple)``.

    Priority ordering mirrors the Sprint I-patch GB cascade (first
    success wins):

    1. **TE primary** (``fetch_jp_bank_rate`` — daily, BoJ-sourced via
       ``BOJDTR``). Emits ``JP_BANK_RATE_TE_PRIMARY`` on success.
    2. **BoJ native** (``fetch_bank_rate`` on the TSD FAME endpoint).
       Currently browser-gated per Sprint L probe — wire-ready for
       future unblock. Emits ``JP_BANK_RATE_BOJ_NATIVE`` on success.
    3. **FRED OECD mirror** (``IRSTCI01JPM156N`` — monthly lag).
       Last-resort fallback emitting both
       ``JP_BANK_RATE_FRED_FALLBACK_STALE`` and ``CALIBRATION_STALE``
       so downstream consumers can surface the degradation.

    All three branches fail-open to the next source on
    :class:`DataUnavailableError` or empty payload. If all three return
    empty the cascade raises ``ValueError``.
    """
    from sonar.overlays.exceptions import DataUnavailableError  # noqa: PLC0415

    if te is not None:
        try:
            te_obs = await te.fetch_jp_bank_rate(start, end)
        except DataUnavailableError:
            te_obs = []
        if te_obs:
            return (
                [_DatedValue(o.observation_date, o.value) for o in te_obs],
                ("JP_BANK_RATE_TE_PRIMARY",),
                ("te",),
            )

    if boj is not None:
        try:
            boj_obs = await boj.fetch_bank_rate(start, end)
        except DataUnavailableError:
            boj_obs = []
        if boj_obs:
            return (
                [_DatedValue(o.observation_date, o.yield_bps / 100.0) for o in boj_obs],
                ("JP_BANK_RATE_BOJ_NATIVE",),
                ("boj",),
            )

    fred_obs = await fred.fetch_series(FRED_JP_BANK_RATE_SERIES, start, end)
    if fred_obs:
        return (
            [_DatedValue(o.observation_date, o.yield_bps / 100.0) for o in fred_obs],
            ("JP_BANK_RATE_FRED_FALLBACK_STALE", "CALIBRATION_STALE"),
            ("fred",),
        )

    msg = "JP Bank Rate unavailable from TE, BoJ, and FRED"
    raise ValueError(msg)


async def build_m1_jp_inputs(
    fred: FredConnector,
    observation_date: date,
    *,
    te: TEConnector | None = None,
    boj: BoJConnector | None = None,
    history_years: int = M1_DEFAULT_LOOKBACK_YEARS,
) -> M1EffectiveRatesInputs:
    """Assemble M1 JP inputs via TE → BoJ → FRED cascade + YAML r*/target.

    Sprint L introduces the JP country path using the canonical cascade
    pattern established by Sprint I-patch for GB. TE's ``interest rate``
    indicator for Japan back-fills the full BoJ policy-rate history
    (``BOJDTR``) at daily cadence and is the empirically preferred
    source — Bank rate decisions propagate into TE within hours of the
    BoJ press conference, whereas the FRED OECD mirror
    (``IRSTCI01JPM156N``) only updates once a month. BoJ TSD sits in
    the second slot as wire-ready scaffold pending a scriptable
    endpoint (browser-gated as of Sprint L probe, 2026-04-21).

    JP-specific degradations (Phase 1):

    - ``expected_inflation_5y_pct`` defaults to BoJ's 2 % CPI target —
      no BoJ breakeven-inflation mirror exists at this scope; emits
      ``EXPECTED_INFLATION_CB_TARGET`` flag (mirrors GB pattern).
    - ``balance_sheet_pct_gdp_*`` zero-seeded with ``JP_BS_GDP_PROXY_ZERO``
      flag — JP balance-sheet ratios require BoJ Monetary Base (BoJ
      TSD ``BS01'MABJMTA``) combined with Cabinet Office JP nominal
      GDP, neither FRED-mirrored at Sprint L scope. Lands when TSD
      becomes scriptable or we wire a direct FRED JP M2 / GDP path.
    """
    start = observation_date - timedelta(days=history_years * 366)

    policy_hist, cascade_flags, cascade_sources = await _jp_bank_rate_cascade(
        start, observation_date, te=te, boj=boj, fred=fred
    )
    latest_policy = _latest_on_or_before(policy_hist, observation_date)
    if latest_policy is None:
        msg = "JP Bank Rate: no observation at or before anchor"
        raise ValueError(msg)
    policy_rate_pct = latest_policy.value / 100.0

    r_star_pct, _is_proxy = resolve_r_star("JP")  # is_proxy always True for JP
    expected_inflation_5y_pct = 0.02  # BoJ CPI target; proxy

    policy_monthly_pct = _resample_monthly(
        policy_hist, observation_date, n_months=history_years * 12
    )
    real_shadow_hist = [p / 100.0 - expected_inflation_5y_pct for p in policy_monthly_pct]
    stance_hist = [r - r_star_pct for r in real_shadow_hist]

    flags: list[str] = [
        *cascade_flags,
        "R_STAR_PROXY",
        "EXPECTED_INFLATION_CB_TARGET",
        "JP_BS_GDP_PROXY_ZERO",
    ]

    return M1EffectiveRatesInputs(
        country_code="JP",
        observation_date=observation_date,
        policy_rate_pct=policy_rate_pct,
        expected_inflation_5y_pct=expected_inflation_5y_pct,
        r_star_pct=r_star_pct,
        balance_sheet_pct_gdp_current=0.0,
        balance_sheet_pct_gdp_12m_ago=0.0,
        real_shadow_rate_history=tuple(real_shadow_hist),
        stance_vs_neutral_history=tuple(stance_hist),
        balance_sheet_signal_history=tuple([0.0] * len(real_shadow_hist)),
        lookback_years=history_years,
        source_connector=cascade_sources,
        upstream_flags=tuple(flags),
    )


# ---------------------------------------------------------------------------
# M2 — JP (Sprint L — wire-ready scaffold, raises pending connector gaps)
# ---------------------------------------------------------------------------


async def build_m2_jp_inputs(
    fred: FredConnector,
    observation_date: date,
    *,
    te: TEConnector | None = None,
    boj: BoJConnector | None = None,
    oecd_eo: OECDEOConnector | None = None,
    history_years: int = M2_DEFAULT_LOOKBACK_YEARS,
) -> M2TaylorGapsInputs:
    """Assemble M2 JP inputs — full compute live (Week 10 Sprint F).

    Sprint L wired the dispatch; Sprint C wired OECD EO output-gap
    (``ref_area=JPN``); Sprint F (this commit) wires TE CPI YoY + 12m
    forecast via :meth:`TEConnector.fetch_jp_cpi_yoy` and
    :meth:`TEConnector.fetch_jp_inflation_forecast`. BoJ Outlook
    Report projections inform the TE forecast blend.

    BoJ's 2 % inflation target (adopted 2013) anchors ``inflation
    _target_pct``; ``r_star_pct`` is 0 % from ``r_star_values.yaml``
    (QQE-era staff synthesis) with ``R_STAR_PROXY`` flag propagated.
    """
    start = observation_date - timedelta(days=history_years * 366)
    policy_hist, cascade_flags, cascade_sources = await _jp_bank_rate_cascade(
        start, observation_date, te=te, boj=boj, fred=fred
    )
    cpi_obs = await _try_fetch_cpi_yoy(te, start, observation_date, "fetch_jp_cpi_yoy")
    forecast_12m_pct, forecast_flags = await _try_fetch_inflation_forecast_12m(
        te, "JP", observation_date, "fetch_jp_inflation_forecast"
    )
    gap_pct = await _try_fetch_oecd_output_gap_pct(oecd_eo, "JP", observation_date)
    return await _assemble_m2_full_compute(
        country_code="JP",
        observation_date=observation_date,
        policy_hist=policy_hist,
        cascade_flags=cascade_flags,
        cascade_sources=cascade_sources,
        cpi_observations=cpi_obs,
        forecast_12m_pct=forecast_12m_pct,
        forecast_flags=forecast_flags,
        output_gap_pct=gap_pct,
        history_years=history_years,
    )


# ---------------------------------------------------------------------------
# M4 — JP (Sprint L — wire-ready scaffold, raises pending FCI components)
# ---------------------------------------------------------------------------


async def build_m4_jp_inputs(
    fred: FredConnector,  # noqa: ARG001 - wired for future JP FCI components
    observation_date: date,  # noqa: ARG001
    *,
    te: TEConnector | None = None,  # noqa: ARG001
    history_years: int = M4_DEFAULT_LOOKBACK_YEARS,  # noqa: ARG001
) -> M4FciInputs:
    """Assemble M4 JP inputs (scaffold — raises until ≥5 FCI components).

    JP lacks the direct-provider shortcut that US gets via Chicago Fed
    NFCI, so JP must walk the spec §4 custom path, which needs
    ``MIN_CUSTOM_COMPONENTS == 5`` of the seven FCI inputs (credit
    spread, vol index, 10Y gov yield, FX NEER, mortgage rate). At Sprint
    L close only the 10Y JGB yield is mappable via TE
    (``GJGB10:IND``) — below the 5-component floor.

    Pending components (open CAL-JP-M4-FCI bundle):

    - JP credit spread (BBB corp vs JGB; TE / BoJ J-REIT proxy)
    - JP vol index (Nikkei VI via TE ``NKYVOLX:IND`` or OSE direct)
    - JP JPY NEER (BIS narrow / broad; wrapper not yet shipped)
    - JP mortgage rate (FRED ``INTDSRJPM193N`` candidate; probe pending)

    Once the 5-component bar is met this builder composes
    :class:`M4FciInputs` and the compute-side fallback through
    :func:`sonar.indices.monetary.m4_fci._compute_custom_fci` takes over.
    Until then, :class:`InsufficientDataError` keeps the pipeline clean
    (mirrors M2 JP skip behaviour).
    """
    msg = (
        "M4 JP builder scaffold shipped Sprint L but <5/5 custom-FCI "
        "components available (need credit spread + vol + 10Y + FX NEER "
        "+ mortgage; see CAL-JP-M4-FCI). Raises so the pipeline skips "
        "M4 JP cleanly."
    )
    raise InsufficientDataError(msg)


# ---------------------------------------------------------------------------
# M1 — CA (Sprint S — TE primary → BoC Valet native → FRED stale-flagged)
# ---------------------------------------------------------------------------


async def _ca_bank_rate_cascade(
    start: date,
    end: date,
    *,
    te: TEConnector | None,
    boc: BoCConnector | None,
    fred: FredConnector,
) -> tuple[list[_DatedValue], tuple[str, ...], tuple[str, ...]]:
    """Fetch CA Bank Rate via TE → BoC → FRED priority-first-wins cascade.

    Returns ``(series_pct, cascade_flags, source_connector_tuple)``.

    Priority ordering mirrors the Sprint I-patch GB + Sprint L JP
    cascades (first success wins); the material difference for CA is
    that the **secondary** slot (BoC Valet V39079) is a first-class
    reachable public API — empirical probe 2026-04-21 confirmed
    scriptable JSON REST with no auth, no anti-bot gate. The cascade
    therefore sits mostly on TE primary with BoC Valet as a robust,
    widely-usable fallback (unlike GB/JP where the native slot is a
    wire-ready scaffold pending a browser-gate bypass).

    1. **TE primary** (``fetch_ca_bank_rate`` — daily, BoC-sourced via
       ``CCLR``). Emits ``CA_BANK_RATE_TE_PRIMARY`` on success.
    2. **BoC Valet native** (``fetch_bank_rate`` on V39079 — Target
       for the overnight rate). Emits ``CA_BANK_RATE_BOC_NATIVE`` on
       success.
    3. **FRED OECD mirror** (``IRSTCI01CAM156N`` — monthly lag).
       Last-resort fallback emitting both
       ``CA_BANK_RATE_FRED_FALLBACK_STALE`` and ``CALIBRATION_STALE``
       so downstream consumers can surface the degradation.

    All three branches fail-open to the next source on
    :class:`DataUnavailableError` or empty payload. If all three
    return empty the cascade raises ``ValueError``.
    """
    from sonar.overlays.exceptions import DataUnavailableError  # noqa: PLC0415

    if te is not None:
        try:
            te_obs = await te.fetch_ca_bank_rate(start, end)
        except DataUnavailableError:
            te_obs = []
        if te_obs:
            return (
                [_DatedValue(o.observation_date, o.value) for o in te_obs],
                ("CA_BANK_RATE_TE_PRIMARY",),
                ("te",),
            )

    if boc is not None:
        try:
            boc_obs = await boc.fetch_bank_rate(start, end)
        except DataUnavailableError:
            boc_obs = []
        if boc_obs:
            return (
                [_DatedValue(o.observation_date, o.yield_bps / 100.0) for o in boc_obs],
                ("CA_BANK_RATE_BOC_NATIVE",),
                ("boc",),
            )

    fred_obs = await fred.fetch_series(FRED_CA_BANK_RATE_SERIES, start, end)
    if fred_obs:
        return (
            [_DatedValue(o.observation_date, o.yield_bps / 100.0) for o in fred_obs],
            ("CA_BANK_RATE_FRED_FALLBACK_STALE", "CALIBRATION_STALE"),
            ("fred",),
        )

    msg = "CA Bank Rate unavailable from TE, BoC, and FRED"
    raise ValueError(msg)


async def build_m1_ca_inputs(
    fred: FredConnector,
    observation_date: date,
    *,
    te: TEConnector | None = None,
    boc: BoCConnector | None = None,
    history_years: int = M1_DEFAULT_LOOKBACK_YEARS,
) -> M1EffectiveRatesInputs:
    """Assemble M1 CA inputs via TE → BoC → FRED cascade + YAML r*/target.

    Sprint S introduces the CA country path using the canonical cascade
    pattern established by Sprint I-patch (GB) and Sprint L (JP). TE's
    ``interest rate`` indicator for Canada back-fills the full BoC
    policy-rate history (``CCLR``) at daily cadence and is the
    empirically preferred source — decisions propagate into TE within
    hours of the BoC press conference, whereas the FRED OECD mirror
    (``IRSTCI01CAM156N``) only updates once a month. BoC Valet V39079
    ("Target for the overnight rate") sits in the secondary slot as a
    first-class reachable public API (contrast BoE IADB / BoJ TSD
    which ship as wire-ready scaffolds).

    CA-specific degradations (Phase 1):

    - ``expected_inflation_5y_pct`` defaults to BoC's 2 % CPI target —
      no BoC breakeven-inflation mirror exists at this scope; emits
      ``EXPECTED_INFLATION_CB_TARGET`` flag (mirrors GB + JP pattern).
    - ``balance_sheet_pct_gdp_*`` zero-seeded with
      ``CA_BS_GDP_PROXY_ZERO`` flag — CA balance-sheet ratios require
      BoC weekly balance-sheet (Valet series `B50000` family) combined
      with StatCan nominal GDP, neither wired at Sprint S scope. Lands
      when CAL-133 (CA BS/GDP ratio wiring) closes.
    """
    start = observation_date - timedelta(days=history_years * 366)

    policy_hist, cascade_flags, cascade_sources = await _ca_bank_rate_cascade(
        start, observation_date, te=te, boc=boc, fred=fred
    )
    latest_policy = _latest_on_or_before(policy_hist, observation_date)
    if latest_policy is None:
        msg = "CA Bank Rate: no observation at or before anchor"
        raise ValueError(msg)
    policy_rate_pct = latest_policy.value / 100.0

    r_star_pct, _is_proxy = resolve_r_star("CA")  # is_proxy always True for CA
    expected_inflation_5y_pct = 0.02  # BoC CPI target; proxy

    policy_monthly_pct = _resample_monthly(
        policy_hist, observation_date, n_months=history_years * 12
    )
    real_shadow_hist = [p / 100.0 - expected_inflation_5y_pct for p in policy_monthly_pct]
    stance_hist = [r - r_star_pct for r in real_shadow_hist]

    flags: list[str] = [
        *cascade_flags,
        "R_STAR_PROXY",
        "EXPECTED_INFLATION_CB_TARGET",
        "CA_BS_GDP_PROXY_ZERO",
    ]

    return M1EffectiveRatesInputs(
        country_code="CA",
        observation_date=observation_date,
        policy_rate_pct=policy_rate_pct,
        expected_inflation_5y_pct=expected_inflation_5y_pct,
        r_star_pct=r_star_pct,
        balance_sheet_pct_gdp_current=0.0,
        balance_sheet_pct_gdp_12m_ago=0.0,
        real_shadow_rate_history=tuple(real_shadow_hist),
        stance_vs_neutral_history=tuple(stance_hist),
        balance_sheet_signal_history=tuple([0.0] * len(real_shadow_hist)),
        lookback_years=history_years,
        source_connector=cascade_sources,
        upstream_flags=tuple(flags),
    )


# ---------------------------------------------------------------------------
# M2 — CA (Sprint S — wire-ready scaffold, raises pending CA gap + CPI)
# ---------------------------------------------------------------------------


async def build_m2_ca_inputs(
    fred: FredConnector,
    observation_date: date,
    *,
    te: TEConnector | None = None,
    boc: BoCConnector | None = None,
    oecd_eo: OECDEOConnector | None = None,
    history_years: int = M2_DEFAULT_LOOKBACK_YEARS,
) -> M2TaylorGapsInputs:
    """Assemble M2 CA inputs — full compute live (Week 10 Sprint F).

    Progression:

    - Sprint S (Week 9): wire-ready scaffold; raised
      InsufficientDataError with the CAL-130 blocker message.
    - Sprint C (Week 10 Day 1): wired OECD EO output-gap via
      ``ref_area=CAN``; raise message narrowed to the CPI + forecast
      blockers per :func:`_m2_blocked_msg`.
    - **Sprint F (Week 10 Day 2)**: this commit — wires TE CPI YoY
      + inflation-forecast wrappers (Commit 1
      :meth:`TEConnector.fetch_ca_cpi_yoy` /
      :meth:`TEConnector.fetch_ca_inflation_forecast`) to complete
      the four-component Taylor compute. Policy-rate path reuses the
      Sprint S :func:`_ca_bank_rate_cascade` so this M2 builder
      inherits TE-primary → BoC native → FRED staleness fallback
      without re-implementing it.

    Flag contract:

    - ``CA_BANK_RATE_TE_PRIMARY`` / ``..._BOC_NATIVE`` / ``..._FRED_FALLBACK_STALE``
      from the cascade.
    - ``CA_M2_CPI_TE_LIVE`` when the TE CPI observation window is non-empty.
    - ``CA_M2_INFLATION_FORECAST_TE_LIVE`` when the 12m-ahead forecast
      wires in; ``..._FORECAST_UNAVAILABLE`` otherwise (Taylor-forward
      variant degrades gracefully).
    - ``CA_M2_OUTPUT_GAP_OECD_EO_LIVE`` when OECD EO returns a gap.
    - ``CA_M2_FULL_COMPUTE_LIVE`` when all four components wire;
      ``..._PARTIAL_COMPUTE`` when forecast is missing but gap + CPI +
      policy all succeed.
    - ``R_STAR_PROXY`` propagates from
      :func:`resolve_r_star` (CA ships ``proxy: true``).
    """
    start = observation_date - timedelta(days=history_years * 366)
    policy_hist, cascade_flags, cascade_sources = await _ca_bank_rate_cascade(
        start, observation_date, te=te, boc=boc, fred=fred
    )

    cpi_obs = await _try_fetch_cpi_yoy(te, start, observation_date, "fetch_ca_cpi_yoy")
    forecast_12m_pct, forecast_flags = await _try_fetch_inflation_forecast_12m(
        te, "CA", observation_date, "fetch_ca_inflation_forecast"
    )
    gap_pct = await _try_fetch_oecd_output_gap_pct(oecd_eo, "CA", observation_date)

    return await _assemble_m2_full_compute(
        country_code="CA",
        observation_date=observation_date,
        policy_hist=policy_hist,
        cascade_flags=cascade_flags,
        cascade_sources=cascade_sources,
        cpi_observations=cpi_obs,
        forecast_12m_pct=forecast_12m_pct,
        forecast_flags=forecast_flags,
        output_gap_pct=gap_pct,
        history_years=history_years,
    )


# ---------------------------------------------------------------------------
# M4 — CA (Sprint S — wire-ready scaffold, raises pending FCI components)
# ---------------------------------------------------------------------------


async def build_m4_ca_inputs(
    fred: FredConnector,  # noqa: ARG001 - wired for future CA FCI components
    observation_date: date,  # noqa: ARG001
    *,
    te: TEConnector | None = None,  # noqa: ARG001
    boc: BoCConnector | None = None,  # noqa: ARG001
    history_years: int = M4_DEFAULT_LOOKBACK_YEARS,  # noqa: ARG001
) -> M4FciInputs:
    """Assemble M4 CA inputs (scaffold — raises until ≥5 FCI components).

    CA lacks the direct-provider shortcut that US gets via Chicago Fed
    NFCI, so CA must walk the spec §4 custom path which needs
    ``MIN_CUSTOM_COMPONENTS == 5`` of the seven FCI inputs. At Sprint
    S close the reachable components are:

    - 10Y GoC yield via BoC Valet ``BD.CDN.10YR.DQ.YLD`` (wired C2)
    - Policy rate via the M1 cascade (wired C4)

    Pending components (bundled into CAL-131):

    - CA credit spread (BBB corp vs GoC; candidate: FRED
      ``BAMLHYCA`` or Valet bond-yield curve proxy)
    - CA vol index (no S&P/TSX VIX-analog readily on FRED; Yahoo
      ^VIXC or proxy from ^VIX)
    - CA CAD NEER (BoC Valet ``CEER_BROADN`` is the canonical daily
      nominal-CEER series)
    - CA mortgage rate (BoC Valet ``V80691335`` or equivalent)

    Once ≥5 components land, this builder composes
    :class:`M4FciInputs` and the compute-side fallback through
    :func:`sonar.indices.monetary.m4_fci._compute_custom_fci` takes
    over. Until then, :class:`InsufficientDataError` keeps the
    pipeline clean (mirrors M2 CA skip behaviour).
    """
    msg = (
        "M4 CA builder scaffold shipped Sprint S but <5/5 custom-FCI "
        "components available (need credit spread + vol + 10Y + CAD "
        "NEER + mortgage; see CAL-131). Raises so the pipeline skips "
        "M4 CA cleanly."
    )
    raise InsufficientDataError(msg)


# ---------------------------------------------------------------------------
# M1 — AU (Sprint T — TE primary → RBA F1 native → FRED stale-flagged)
# ---------------------------------------------------------------------------


async def _au_cash_rate_cascade(
    start: date,
    end: date,
    *,
    te: TEConnector | None,
    rba: RBAConnector | None,
    fred: FredConnector,
) -> tuple[list[_DatedValue], tuple[str, ...], tuple[str, ...]]:
    """Fetch AU Cash Rate via TE → RBA → FRED priority-first-wins cascade.

    Returns ``(series_pct, cascade_flags, source_connector_tuple)``.

    Priority ordering mirrors the Sprint I-patch (GB), Sprint L (JP),
    and Sprint S (CA) cascades (first success wins). AU joins CA as the
    second country with a reachable native secondary slot — the RBA
    statistical-tables CSVs are a public static publication, so when TE
    fails AU lands ``AU_CASH_RATE_RBA_NATIVE`` with no staleness flag
    (unlike GB / JP where the native slot ships as a wire-ready
    scaffold).

    1. **TE primary** (``fetch_au_cash_rate`` — daily, RBA-sourced via
       ``RBATCTR``). Emits ``AU_CASH_RATE_TE_PRIMARY`` on success.
    2. **RBA F1 native** (``fetch_cash_rate`` on ``FIRMMCRTD`` — Cash
       Rate Target). Emits ``AU_CASH_RATE_RBA_NATIVE`` on success.
    3. **FRED OECD mirror** (``IRSTCI01AUM156N`` — monthly lag).
       Last-resort fallback emitting both
       ``AU_CASH_RATE_FRED_FALLBACK_STALE`` and ``CALIBRATION_STALE``
       so downstream consumers can surface the degradation.

    All three branches fail-open to the next source on
    :class:`DataUnavailableError` or empty payload. If all three
    return empty the cascade raises ``ValueError``.
    """
    from sonar.overlays.exceptions import DataUnavailableError  # noqa: PLC0415

    if te is not None:
        try:
            te_obs = await te.fetch_au_cash_rate(start, end)
        except DataUnavailableError:
            te_obs = []
        if te_obs:
            return (
                [_DatedValue(o.observation_date, o.value) for o in te_obs],
                ("AU_CASH_RATE_TE_PRIMARY",),
                ("te",),
            )

    if rba is not None:
        try:
            rba_obs = await rba.fetch_cash_rate(start, end)
        except DataUnavailableError:
            rba_obs = []
        if rba_obs:
            return (
                [_DatedValue(o.observation_date, o.yield_bps / 100.0) for o in rba_obs],
                ("AU_CASH_RATE_RBA_NATIVE",),
                ("rba",),
            )

    fred_obs = await fred.fetch_series(FRED_AU_CASH_RATE_SERIES, start, end)
    if fred_obs:
        return (
            [_DatedValue(o.observation_date, o.yield_bps / 100.0) for o in fred_obs],
            ("AU_CASH_RATE_FRED_FALLBACK_STALE", "CALIBRATION_STALE"),
            ("fred",),
        )

    msg = "AU Cash Rate unavailable from TE, RBA, and FRED"
    raise ValueError(msg)


async def build_m1_au_inputs(
    fred: FredConnector,
    observation_date: date,
    *,
    te: TEConnector | None = None,
    rba: RBAConnector | None = None,
    history_years: int = M1_DEFAULT_LOOKBACK_YEARS,
) -> M1EffectiveRatesInputs:
    """Assemble M1 AU inputs via TE → RBA → FRED cascade + YAML r*/target.

    Sprint T introduces the AU country path using the canonical cascade
    pattern established by Sprint I-patch (GB), Sprint L (JP), and
    Sprint S (CA). TE's ``interest rate`` indicator for Australia
    back-fills the full RBA policy-rate history (``RBATCTR``) at daily
    cadence and is the empirically preferred source — decisions
    propagate into TE within hours of the RBA announcement, whereas the
    FRED OECD mirror (``IRSTCI01AUM156N``) only updates once a month.
    RBA F1 ``FIRMMCRTD`` (Cash Rate Target) sits in the secondary slot
    as a first-class reachable public static CSV (contrast BoE IADB /
    BoJ TSD which ship as wire-ready scaffolds).

    AU-specific degradations (Phase 1):

    - ``expected_inflation_5y_pct`` defaults to RBA's 2-3 % target
      midpoint (2.5 %) — no RBA breakeven-inflation mirror exists at
      this scope; emits ``EXPECTED_INFLATION_CB_TARGET`` flag (mirrors
      GB / JP / CA pattern).
    - ``balance_sheet_pct_gdp_*`` zero-seeded with
      ``AU_BS_GDP_PROXY_ZERO`` flag — AU balance-sheet ratios require
      RBA weekly balance-sheet (table ``A1`` series) combined with ABS
      nominal GDP, neither wired at Sprint T scope. Lands when
      CAL-AU-BS-GDP closes.
    """
    start = observation_date - timedelta(days=history_years * 366)

    policy_hist, cascade_flags, cascade_sources = await _au_cash_rate_cascade(
        start, observation_date, te=te, rba=rba, fred=fred
    )
    latest_policy = _latest_on_or_before(policy_hist, observation_date)
    if latest_policy is None:
        msg = "AU Cash Rate: no observation at or before anchor"
        raise ValueError(msg)
    policy_rate_pct = latest_policy.value / 100.0

    r_star_pct, _is_proxy = resolve_r_star("AU")  # is_proxy always True for AU
    # RBA 2-3 % band midpoint used as the 5Y inflation-expectation anchor;
    # the central-bank target loader (bc_targets.yaml) returns 0.025 for AU.
    expected_inflation_5y_pct = resolve_inflation_target("AU")

    policy_monthly_pct = _resample_monthly(
        policy_hist, observation_date, n_months=history_years * 12
    )
    real_shadow_hist = [p / 100.0 - expected_inflation_5y_pct for p in policy_monthly_pct]
    stance_hist = [r - r_star_pct for r in real_shadow_hist]

    flags: list[str] = [
        *cascade_flags,
        "R_STAR_PROXY",
        "EXPECTED_INFLATION_CB_TARGET",
        "AU_BS_GDP_PROXY_ZERO",
    ]

    return M1EffectiveRatesInputs(
        country_code="AU",
        observation_date=observation_date,
        policy_rate_pct=policy_rate_pct,
        expected_inflation_5y_pct=expected_inflation_5y_pct,
        r_star_pct=r_star_pct,
        balance_sheet_pct_gdp_current=0.0,
        balance_sheet_pct_gdp_12m_ago=0.0,
        real_shadow_rate_history=tuple(real_shadow_hist),
        stance_vs_neutral_history=tuple(stance_hist),
        balance_sheet_signal_history=tuple([0.0] * len(real_shadow_hist)),
        lookback_years=history_years,
        source_connector=cascade_sources,
        upstream_flags=tuple(flags),
    )


# ---------------------------------------------------------------------------
# M2 — AU (Sprint T — wire-ready scaffold, raises pending AU gap + CPI)
# ---------------------------------------------------------------------------


async def build_m2_au_inputs(
    fred: FredConnector,
    observation_date: date,
    *,
    te: TEConnector | None = None,
    rba: RBAConnector | None = None,
    oecd_eo: OECDEOConnector | None = None,
    history_years: int = M2_DEFAULT_LOOKBACK_YEARS,
) -> M2TaylorGapsInputs:
    """Assemble M2 AU inputs — full compute live (Week 10 Sprint F).

    Sprint T shipped the dispatch wire-ready; Sprint C wired OECD EO
    output-gap (``ref_area=AUS``); Sprint F (this commit) wires TE CPI
    YoY + inflation forecast via :meth:`TEConnector.fetch_au_cpi_yoy`
    and :meth:`TEConnector.fetch_au_inflation_forecast`.

    **AU-specific degradation flag**: the ABS Monthly CPI Indicator
    coverage on TE begins only in 2025-04-30 (~11 observations at
    Sprint F probe). When the returned CPI window has fewer than 12
    observations the builder emits ``AU_M2_CPI_SPARSE_MONTHLY`` so
    downstream consumers can surface the coverage limitation.
    """
    start = observation_date - timedelta(days=history_years * 366)
    policy_hist, cascade_flags, cascade_sources = await _au_cash_rate_cascade(
        start, observation_date, te=te, rba=rba, fred=fred
    )
    cpi_obs = await _try_fetch_cpi_yoy(te, start, observation_date, "fetch_au_cpi_yoy")
    forecast_12m_pct, forecast_flags = await _try_fetch_inflation_forecast_12m(
        te, "AU", observation_date, "fetch_au_inflation_forecast"
    )
    gap_pct = await _try_fetch_oecd_output_gap_pct(oecd_eo, "AU", observation_date)
    extra_flags = ("AU_M2_CPI_SPARSE_MONTHLY",) if len(cpi_obs) < 12 else ()
    return await _assemble_m2_full_compute(
        country_code="AU",
        observation_date=observation_date,
        policy_hist=policy_hist,
        cascade_flags=cascade_flags,
        cascade_sources=cascade_sources,
        cpi_observations=cpi_obs,
        forecast_12m_pct=forecast_12m_pct,
        forecast_flags=forecast_flags,
        output_gap_pct=gap_pct,
        history_years=history_years,
        extra_flags=extra_flags,
    )


# ---------------------------------------------------------------------------
# M4 — AU (Sprint T — wire-ready scaffold, raises pending FCI components)
# ---------------------------------------------------------------------------


async def build_m4_au_inputs(
    fred: FredConnector,  # noqa: ARG001 - wired for future AU FCI components
    observation_date: date,  # noqa: ARG001
    *,
    te: TEConnector | None = None,  # noqa: ARG001
    rba: RBAConnector | None = None,  # noqa: ARG001
    history_years: int = M4_DEFAULT_LOOKBACK_YEARS,  # noqa: ARG001
) -> M4FciInputs:
    """Assemble M4 AU inputs (scaffold — raises until ≥5 FCI components).

    AU lacks the direct-provider shortcut that US gets via Chicago Fed
    NFCI, so AU must walk the spec §4 custom path which needs
    ``MIN_CUSTOM_COMPONENTS == 5`` of the seven FCI inputs. At Sprint
    T close the reachable components are:

    - 10Y AGB yield via RBA F2 ``FCMYGBAG10D`` (wired C2)
    - Cash Rate via the M1 cascade (wired C4)

    Pending components (bundled into CAL-AU-M4-FCI):

    - AU credit spread (BBB corp vs AGB; candidate: FRED ``BAMLHYAU``
      or RBA F3 corporate-yield series)
    - AU vol index (no S&P/ASX VIX-analog readily on FRED; Yahoo
      ^AXVI or proxy from ^VIX)
    - AU AUD NEER (RBA F11 nominal-TWI; index form)
    - AU mortgage rate (RBA F5 lender-rates table)

    Once ≥5 components land, this builder composes
    :class:`M4FciInputs` and the compute-side fallback through
    :func:`sonar.indices.monetary.m4_fci._compute_custom_fci` takes
    over. Until then, :class:`InsufficientDataError` keeps the
    pipeline clean (mirrors M2 AU / CA skip behaviour).
    """
    msg = (
        "M4 AU builder scaffold shipped Sprint T but <5/5 custom-FCI "
        "components available (need credit spread + vol + 10Y + AUD "
        "NEER + mortgage; see CAL-AU-M4-FCI). Raises so the pipeline "
        "skips M4 AU cleanly."
    )
    raise InsufficientDataError(msg)


# ---------------------------------------------------------------------------
# M1 — NZ (Sprint U-NZ — TE primary → RBNZ B2 native (raises) → FRED stale)
# ---------------------------------------------------------------------------


async def _nz_ocr_cascade(
    start: date,
    end: date,
    *,
    te: TEConnector | None,
    rbnz: RBNZConnector | None,
    fred: FredConnector,
) -> tuple[list[_DatedValue], tuple[str, ...], tuple[str, ...]]:
    """Fetch NZ OCR via TE → RBNZ → FRED priority-first-wins cascade.

    Returns ``(series_pct, cascade_flags, source_connector_tuple)``.

    Priority ordering mirrors the Sprint I-patch (GB), Sprint L (JP),
    Sprint S (CA), and Sprint T (AU) cascades (first success wins).
    NZ differs from AU in that the RBNZ B2 secondary slot currently
    raises :class:`DataUnavailableError` against the live host
    (``www.rbnz.govt.nz`` perimeter-403s the SONAR VPS IP regardless
    of User-Agent — see :mod:`sonar.connectors.rbnz` docstring for
    the 2026-04-21 probe findings). Behaviour matches the GB / JP
    scaffolds: the call is attempted so the cascade flags record the
    attempt, then FRED steps in as the last-resort staleness-flagged
    fallback.

    1. **TE primary** (``fetch_nz_ocr`` — daily, RBNZ-sourced via
       ``NZOCRS``). Emits ``NZ_OCR_TE_PRIMARY`` on success.
    2. **RBNZ B2 native** (``fetch_ocr`` on the ``hb2-daily`` CSV).
       Emits ``NZ_OCR_RBNZ_NATIVE`` on success once
       CAL-NZ-RBNZ-TABLES closes and the edge unblocks; until then
       the call raises :class:`DataUnavailableError` and the cascade
       records ``NZ_OCR_RBNZ_UNAVAILABLE``.
    3. **FRED OECD mirror** (``IRSTCI01NZM156N`` — monthly lag).
       Last-resort fallback emitting both
       ``NZ_OCR_FRED_FALLBACK_STALE`` and ``CALIBRATION_STALE`` so
       downstream consumers can surface the degradation.

    All three branches fail-open to the next source on
    :class:`DataUnavailableError` or empty payload. If all three
    return empty the cascade raises ``ValueError``.
    """
    from sonar.overlays.exceptions import DataUnavailableError  # noqa: PLC0415

    cascade_flags: list[str] = []

    if te is not None:
        try:
            te_obs = await te.fetch_nz_ocr(start, end)
        except DataUnavailableError:
            te_obs = []
            cascade_flags.append("NZ_OCR_TE_UNAVAILABLE")
        if te_obs:
            return (
                [_DatedValue(o.observation_date, o.value) for o in te_obs],
                ("NZ_OCR_TE_PRIMARY",),
                ("te",),
            )

    if rbnz is not None:
        try:
            rbnz_obs = await rbnz.fetch_ocr(start, end)
        except DataUnavailableError:
            rbnz_obs = []
            cascade_flags.append("NZ_OCR_RBNZ_UNAVAILABLE")
        if rbnz_obs:
            return (
                [_DatedValue(o.observation_date, o.yield_bps / 100.0) for o in rbnz_obs],
                (*cascade_flags, "NZ_OCR_RBNZ_NATIVE"),
                ("rbnz",),
            )

    fred_obs = await fred.fetch_series(FRED_NZ_OCR_SERIES, start, end)
    if fred_obs:
        return (
            [_DatedValue(o.observation_date, o.yield_bps / 100.0) for o in fred_obs],
            (*cascade_flags, "NZ_OCR_FRED_FALLBACK_STALE", "CALIBRATION_STALE"),
            ("fred",),
        )

    msg = "NZ OCR unavailable from TE, RBNZ, and FRED"
    raise ValueError(msg)


async def build_m1_nz_inputs(
    fred: FredConnector,
    observation_date: date,
    *,
    te: TEConnector | None = None,
    rbnz: RBNZConnector | None = None,
    history_years: int = M1_DEFAULT_LOOKBACK_YEARS,
) -> M1EffectiveRatesInputs:
    """Assemble M1 NZ inputs via TE → RBNZ → FRED cascade + YAML r*/target.

    Sprint U-NZ introduces the NZ country path using the canonical
    cascade pattern established by Sprint I-patch (GB), Sprint L (JP),
    Sprint S (CA), and Sprint T (AU). TE's ``interest rate`` indicator
    for New Zealand back-fills the full RBNZ Official Cash Rate
    history (``NZOCRS``) at daily cadence and is the empirically
    preferred source — decisions propagate into TE within hours of
    the RBNZ announcement, whereas the FRED OECD mirror
    (``IRSTCI01NZM156N``) only updates once a month. The RBNZ B2
    ``hb2-daily`` CSV sits in the secondary slot as a wire-ready
    scaffold; the RBNZ host currently perimeter-403s from the SONAR
    VPS (CAL-NZ-RBNZ-TABLES) so the RBNZ call surfaces
    :class:`DataUnavailableError` and the cascade flags
    ``NZ_OCR_RBNZ_UNAVAILABLE`` before reaching FRED.

    NZ-specific degradations (Phase 1):

    - ``expected_inflation_5y_pct`` defaults to RBNZ's 1-3 % target
      midpoint (2 %) resolved from :mod:`bc_targets.yaml` — no RBNZ
      breakeven-inflation mirror exists at this scope; emits
      ``EXPECTED_INFLATION_CB_TARGET`` flag (mirrors GB / JP / CA /
      AU pattern).
    - ``balance_sheet_pct_gdp_*`` zero-seeded with
      ``NZ_BS_GDP_PROXY_ZERO`` flag — NZ balance-sheet ratios
      require RBNZ balance-sheet (B5/B6 series) combined with Stats
      NZ nominal GDP, neither wired at Sprint U-NZ scope. Lands when
      CAL-NZ-BS-GDP closes.
    """
    start = observation_date - timedelta(days=history_years * 366)

    policy_hist, cascade_flags, cascade_sources = await _nz_ocr_cascade(
        start, observation_date, te=te, rbnz=rbnz, fred=fred
    )
    latest_policy = _latest_on_or_before(policy_hist, observation_date)
    if latest_policy is None:
        msg = "NZ OCR: no observation at or before anchor"
        raise ValueError(msg)
    policy_rate_pct = latest_policy.value / 100.0

    r_star_pct, _is_proxy = resolve_r_star("NZ")  # is_proxy always True for NZ
    # RBNZ 1-3 % band midpoint (2 %) used as the 5Y inflation-expectation
    # anchor; the central-bank target loader (bc_targets.yaml) returns
    # 0.02 for NZ callers.
    expected_inflation_5y_pct = resolve_inflation_target("NZ")

    policy_monthly_pct = _resample_monthly(
        policy_hist, observation_date, n_months=history_years * 12
    )
    real_shadow_hist = [p / 100.0 - expected_inflation_5y_pct for p in policy_monthly_pct]
    stance_hist = [r - r_star_pct for r in real_shadow_hist]

    flags: list[str] = [
        *cascade_flags,
        "R_STAR_PROXY",
        "EXPECTED_INFLATION_CB_TARGET",
        "NZ_BS_GDP_PROXY_ZERO",
    ]

    return M1EffectiveRatesInputs(
        country_code="NZ",
        observation_date=observation_date,
        policy_rate_pct=policy_rate_pct,
        expected_inflation_5y_pct=expected_inflation_5y_pct,
        r_star_pct=r_star_pct,
        balance_sheet_pct_gdp_current=0.0,
        balance_sheet_pct_gdp_12m_ago=0.0,
        real_shadow_rate_history=tuple(real_shadow_hist),
        stance_vs_neutral_history=tuple(stance_hist),
        balance_sheet_signal_history=tuple([0.0] * len(real_shadow_hist)),
        lookback_years=history_years,
        source_connector=cascade_sources,
        upstream_flags=tuple(flags),
    )


# ---------------------------------------------------------------------------
# M2 — NZ (Sprint U-NZ — wire-ready scaffold, raises pending gap + CPI)
# ---------------------------------------------------------------------------


async def build_m2_nz_inputs(
    fred: FredConnector,
    observation_date: date,
    *,
    te: TEConnector | None = None,
    rbnz: RBNZConnector | None = None,
    oecd_eo: OECDEOConnector | None = None,
    history_years: int = M2_DEFAULT_LOOKBACK_YEARS,
) -> M2TaylorGapsInputs:
    """Assemble M2 NZ inputs — full compute live (Week 10 Sprint F).

    Sprint U-NZ shipped the dispatch wire-ready; Sprint C wired OECD EO
    output-gap; Sprint F (this commit) wires TE CPI YoY + inflation
    forecast. The StatsNZ native CPI publication is **quarterly**, and
    TE mirrors that cadence — the builder emits ``NZ_M2_CPI_QUARTERLY``
    on every compute to surface the lower cadence to downstream
    consumers (contrast the monthly CPI path of most other T1
    countries).
    """
    start = observation_date - timedelta(days=history_years * 366)
    policy_hist, cascade_flags, cascade_sources = await _nz_ocr_cascade(
        start, observation_date, te=te, rbnz=rbnz, fred=fred
    )
    cpi_obs = await _try_fetch_cpi_yoy(te, start, observation_date, "fetch_nz_cpi_yoy")
    forecast_12m_pct, forecast_flags = await _try_fetch_inflation_forecast_12m(
        te, "NZ", observation_date, "fetch_nz_inflation_forecast"
    )
    gap_pct = await _try_fetch_oecd_output_gap_pct(oecd_eo, "NZ", observation_date)
    return await _assemble_m2_full_compute(
        country_code="NZ",
        observation_date=observation_date,
        policy_hist=policy_hist,
        cascade_flags=cascade_flags,
        cascade_sources=cascade_sources,
        cpi_observations=cpi_obs,
        forecast_12m_pct=forecast_12m_pct,
        forecast_flags=forecast_flags,
        output_gap_pct=gap_pct,
        history_years=history_years,
        extra_flags=("NZ_M2_CPI_QUARTERLY",),
    )


# ---------------------------------------------------------------------------
# M4 — NZ (Sprint U-NZ — wire-ready scaffold, raises pending FCI components)
# ---------------------------------------------------------------------------


async def build_m4_nz_inputs(
    fred: FredConnector,  # noqa: ARG001 - wired for future NZ FCI components
    observation_date: date,  # noqa: ARG001
    *,
    te: TEConnector | None = None,  # noqa: ARG001
    rbnz: RBNZConnector | None = None,  # noqa: ARG001
    history_years: int = M4_DEFAULT_LOOKBACK_YEARS,  # noqa: ARG001
) -> M4FciInputs:
    """Assemble M4 NZ inputs (scaffold — raises until ≥5 FCI components).

    NZ lacks the direct-provider shortcut that US gets via Chicago
    Fed NFCI, so NZ must walk the spec §4 custom path which needs
    ``MIN_CUSTOM_COMPONENTS == 5`` of the seven FCI inputs. At Sprint
    U-NZ close the only reachable component is the OCR via the M1
    cascade; the remaining components bundle into CAL-NZ-M4-FCI:

    - NZ credit spread (BBB corp vs NZ gov; candidate: Bloomberg NZD
      credit indices or RBNZ B5 corporate-yield series once the host
      unblocks)
    - NZ vol index (no NZX VIX-analog readily published; proxy from
      global VIX or ASX ^AXVI with weighting)
    - NZ 10Y government stock yield (RBNZ B2 weekly long-maturity
      series pending host unblock; FRED ``IRLTLT01NZM156N`` OECD
      mirror available monthly)
    - NZ NZD NEER (RBNZ B14 trade-weighted index)
    - NZ mortgage rate (RBNZ B20 lender-rates table)

    Once ≥5 components land, this builder composes
    :class:`M4FciInputs` and the compute-side fallback through
    :func:`sonar.indices.monetary.m4_fci._compute_custom_fci` takes
    over. Until then, :class:`InsufficientDataError` keeps the
    pipeline clean (mirrors M2 NZ / M4 AU / M4 CA skip behaviour).
    """
    msg = (
        "M4 NZ builder scaffold shipped Sprint U-NZ but <5/5 custom-FCI "
        "components available (need credit spread + vol + 10Y + NZD "
        "NEER + mortgage; see CAL-NZ-M4-FCI). Raises so the pipeline "
        "skips M4 NZ cleanly."
    )
    raise InsufficientDataError(msg)


# ---------------------------------------------------------------------------
# M1 — CH (Sprint V TE → SNB → FRED cascade + negative-rate era flag)
# ---------------------------------------------------------------------------


async def _ch_policy_rate_cascade(
    start: date,
    end: date,
    *,
    te: TEConnector | None,
    snb: SNBConnector | None,
    fred: FredConnector,
) -> tuple[list[_DatedValue], tuple[str, ...], tuple[str, ...]]:
    """Fetch CH Policy Rate via TE → SNB → FRED priority-first-wins cascade.

    Returns ``(series_pct, cascade_flags, source_connector_tuple)``.

    Priority ordering mirrors the Sprint I-patch (GB), Sprint L (JP),
    Sprint S (CA), and Sprint T (AU) cascades (first success wins). CH
    joins CA and AU as the third country with a reachable native
    secondary slot — the SNB data portal is a public unscreened CSV
    endpoint. Cadence delta versus TE daily primary: SNB is monthly, so
    the secondary lands ``CH_POLICY_RATE_SNB_NATIVE`` alongside
    ``CH_POLICY_RATE_SNB_NATIVE_MONTHLY`` to flag the cadence delta
    explicitly — but **no** ``CALIBRATION_STALE`` flag, since SNB
    policy-rate changes at a quarterly decision cadence and the monthly
    aggregation is materially equivalent for M1 purposes.

    1. **TE primary** (``fetch_ch_policy_rate`` — daily, SNB-sourced via
       ``SZLTTR``). Emits ``CH_POLICY_RATE_TE_PRIMARY`` on success.
    2. **SNB native** (``fetch_saron`` on ``zimoma`` cube). Emits
       ``CH_POLICY_RATE_SNB_NATIVE`` + ``CH_POLICY_RATE_SNB_NATIVE_MONTHLY``
       on success.
    3. **FRED OECD mirror** (``IRSTCI01CHM156N`` — monthly lag; probe
       2026-04-21 showed the series stale at 2024-03). Last-resort
       fallback emitting both ``CH_POLICY_RATE_FRED_FALLBACK_STALE``
       and ``CALIBRATION_STALE`` so downstream consumers can surface
       the degradation.

    **Negative-rate era**: when the resolved history contains at least
    one strictly-negative observation, the cascade additionally emits
    ``CH_NEGATIVE_RATE_ERA_DATA`` — preserving the signal that the
    window spans the 2014-2022 SNB negative corridor (minimum policy
    rate -0.75 %). This is the characteristic CH cascade flag; no
    other Tier-1 country's cascade needs it at Sprint V scope.

    All three branches fail-open to the next source on
    :class:`DataUnavailableError` or empty payload. If all three
    return empty the cascade raises ``ValueError``.
    """
    from sonar.overlays.exceptions import DataUnavailableError  # noqa: PLC0415

    hist: list[_DatedValue] | None = None
    flags: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()

    if te is not None:
        try:
            te_obs = await te.fetch_ch_policy_rate(start, end)
        except DataUnavailableError:
            te_obs = []
        if te_obs:
            hist = [_DatedValue(o.observation_date, o.value) for o in te_obs]
            flags = ("CH_POLICY_RATE_TE_PRIMARY",)
            sources = ("te",)

    if hist is None and snb is not None:
        try:
            snb_obs = await snb.fetch_saron(start, end)
        except DataUnavailableError:
            snb_obs = []
        if snb_obs:
            hist = [_DatedValue(o.observation_date, o.yield_bps / 100.0) for o in snb_obs]
            flags = (
                "CH_POLICY_RATE_SNB_NATIVE",
                "CH_POLICY_RATE_SNB_NATIVE_MONTHLY",
            )
            sources = ("snb",)

    if hist is None:
        fred_obs = await fred.fetch_series(FRED_CH_POLICY_RATE_SERIES, start, end)
        if fred_obs:
            hist = [_DatedValue(o.observation_date, o.yield_bps / 100.0) for o in fred_obs]
            flags = ("CH_POLICY_RATE_FRED_FALLBACK_STALE", "CALIBRATION_STALE")
            sources = ("fred",)

    if hist is None:
        msg = "CH Policy Rate unavailable from TE, SNB, and FRED"
        raise ValueError(msg)

    if any(o.value < 0 for o in hist):
        flags = (*flags, "CH_NEGATIVE_RATE_ERA_DATA")
    return hist, flags, sources


async def build_m1_ch_inputs(
    fred: FredConnector,
    observation_date: date,
    *,
    te: TEConnector | None = None,
    snb: SNBConnector | None = None,
    history_years: int = M1_DEFAULT_LOOKBACK_YEARS,
) -> M1EffectiveRatesInputs:
    """Assemble M1 CH inputs via TE → SNB → FRED cascade + YAML r*/target.

    Sprint V introduces the CH country path using the canonical cascade
    pattern established by Sprint I-patch (GB), Sprint L (JP), Sprint S
    (CA), and Sprint T (AU). TE's ``interest rate`` indicator for
    Switzerland back-fills the full SNB policy-rate history (``SZLTTR``)
    at daily cadence across the 2014-2022 negative-rate corridor and
    is the empirically preferred source — decisions propagate into TE
    within hours of the SNB announcement, whereas the FRED OECD mirror
    (``IRSTCI01CHM156N``) only updates once a month and runs ~12-24
    months stale at Sprint V probe. SNB ``zimoma`` cube SARON sits in
    the secondary slot as a first-class reachable public-CSV native
    (monthly cadence, matching SNB's quarterly decision rhythm).

    CH-specific degradations and Phase-1 proxies:

    - ``r_star_pct`` sourced from SNB WP 2024-09 posterior median
      (0.25 % real) — Swiss r* is structurally low because CHF
      safe-haven status compresses the domestic natural rate. Emits
      ``R_STAR_PROXY`` (mirrors GB / JP / CA / AU pattern).
    - ``expected_inflation_5y_pct`` defaults to SNB 0-2 % band
      midpoint (1 %) — SNB does not publish a point target; emits both
      ``EXPECTED_INFLATION_CB_TARGET`` (proxy-source flag) and
      ``CH_INFLATION_TARGET_BAND`` (band-midpoint-convention flag) so
      downstream operators don't misinterpret the 1 % figure as an
      SNB-published point target.
    - ``balance_sheet_pct_gdp_*`` zero-seeded with
      ``CH_BS_GDP_PROXY_ZERO`` flag — SNB balance-sheet is unusual
      (large forex-intervention-driven assets dating from the
      2011-2015 CHF floor regime) and requires SNB Monthly Statistical
      Bulletin (MSB Table B1A) combined with SECO nominal GDP; neither
      wired at Sprint V scope. Lands when CAL-CH-BS-GDP closes.
    - **Negative-rate era flag** — when the resolved cascade history
      contains ≥ 1 strictly-negative observation, the cascade emits
      ``CH_NEGATIVE_RATE_ERA_DATA`` so downstream M1 / real-shadow
      computations can branch on negative-policy-rate regimes (e.g.
      the shadow-rate formula is unchanged, but regime classifiers may
      need to handle ZLB breaches differently for CH than for
      positive-rate-only cascades).
    """
    start = observation_date - timedelta(days=history_years * 366)

    policy_hist, cascade_flags, cascade_sources = await _ch_policy_rate_cascade(
        start, observation_date, te=te, snb=snb, fred=fred
    )
    latest_policy = _latest_on_or_before(policy_hist, observation_date)
    if latest_policy is None:
        msg = "CH Policy Rate: no observation at or before anchor"
        raise ValueError(msg)
    policy_rate_pct = latest_policy.value / 100.0

    r_star_pct, _is_proxy = resolve_r_star("CH")  # is_proxy always True for CH
    # SNB 0-2 % band midpoint used as the 5Y inflation-expectation anchor;
    # the central-bank target loader (bc_targets.yaml) returns 0.01 for CH.
    expected_inflation_5y_pct = resolve_inflation_target("CH")

    policy_monthly_pct = _resample_monthly(
        policy_hist, observation_date, n_months=history_years * 12
    )
    real_shadow_hist = [p / 100.0 - expected_inflation_5y_pct for p in policy_monthly_pct]
    stance_hist = [r - r_star_pct for r in real_shadow_hist]

    flags: list[str] = [
        *cascade_flags,
        "R_STAR_PROXY",
        "EXPECTED_INFLATION_CB_TARGET",
        "CH_INFLATION_TARGET_BAND",
        "CH_BS_GDP_PROXY_ZERO",
    ]

    return M1EffectiveRatesInputs(
        country_code="CH",
        observation_date=observation_date,
        policy_rate_pct=policy_rate_pct,
        expected_inflation_5y_pct=expected_inflation_5y_pct,
        r_star_pct=r_star_pct,
        balance_sheet_pct_gdp_current=0.0,
        balance_sheet_pct_gdp_12m_ago=0.0,
        real_shadow_rate_history=tuple(real_shadow_hist),
        stance_vs_neutral_history=tuple(stance_hist),
        balance_sheet_signal_history=tuple([0.0] * len(real_shadow_hist)),
        lookback_years=history_years,
        source_connector=cascade_sources,
        upstream_flags=tuple(flags),
    )


# ---------------------------------------------------------------------------
# M2 — CH (Sprint V — wire-ready scaffold, raises pending CPI + gap)
# ---------------------------------------------------------------------------


async def build_m2_ch_inputs(
    fred: FredConnector,
    observation_date: date,
    *,
    te: TEConnector | None = None,
    snb: SNBConnector | None = None,
    oecd_eo: OECDEOConnector | None = None,
    history_years: int = M2_DEFAULT_LOOKBACK_YEARS,
) -> M2TaylorGapsInputs:
    """Assemble M2 CH inputs — full compute live (Week 10 Sprint F).

    Sprint V wired the dispatch; Sprint C wired the OECD EO output gap
    (``ref_area=CHE`` — SNB does not publish a domestic gap, so OECD is
    canonical); Sprint F (this commit) wires TE CPI YoY + 12m-ahead
    forecast via :meth:`TEConnector.fetch_ch_cpi_yoy` and
    :meth:`TEConnector.fetch_ch_inflation_forecast`. The SNB 0-2 % band
    midpoint (1 %) resolves through ``bc_targets.yaml`` for
    ``inflation_target_pct``; propagates ``R_STAR_PROXY`` via the EA
    r* fallback (CH is not in :data:`EA_PROXY_COUNTRIES`, so the r*
    loader uses the CH-specific YAML entry with proxy=True).
    """
    start = observation_date - timedelta(days=history_years * 366)
    policy_hist, cascade_flags, cascade_sources = await _ch_policy_rate_cascade(
        start, observation_date, te=te, snb=snb, fred=fred
    )
    cpi_obs = await _try_fetch_cpi_yoy(te, start, observation_date, "fetch_ch_cpi_yoy")
    forecast_12m_pct, forecast_flags = await _try_fetch_inflation_forecast_12m(
        te, "CH", observation_date, "fetch_ch_inflation_forecast"
    )
    gap_pct = await _try_fetch_oecd_output_gap_pct(oecd_eo, "CH", observation_date)
    return await _assemble_m2_full_compute(
        country_code="CH",
        observation_date=observation_date,
        policy_hist=policy_hist,
        cascade_flags=cascade_flags,
        cascade_sources=cascade_sources,
        cpi_observations=cpi_obs,
        forecast_12m_pct=forecast_12m_pct,
        forecast_flags=forecast_flags,
        output_gap_pct=gap_pct,
        history_years=history_years,
        extra_flags=("CH_INFLATION_TARGET_BAND",),
    )


# ---------------------------------------------------------------------------
# M4 — CH (Sprint V — wire-ready scaffold, raises pending FCI components)
# ---------------------------------------------------------------------------


async def build_m4_ch_inputs(
    fred: FredConnector,  # noqa: ARG001 - wired for future CH FCI components
    observation_date: date,  # noqa: ARG001
    *,
    te: TEConnector | None = None,  # noqa: ARG001
    snb: SNBConnector | None = None,  # noqa: ARG001
    history_years: int = M4_DEFAULT_LOOKBACK_YEARS,  # noqa: ARG001
) -> M4FciInputs:
    """Assemble M4 CH inputs (scaffold — raises until ≥5 FCI components).

    CH lacks the direct-provider shortcut that US gets via Chicago Fed
    NFCI, so CH must walk the spec §4 custom path which needs
    ``MIN_CUSTOM_COMPONENTS == 5`` of the seven FCI inputs. At Sprint
    V close the reachable components are:

    - 10Y Confederation yield via SNB ``rendoblim`` cube / 10J tenor
      (wired C2)
    - Policy rate via the M1 cascade (wired C4)

    Pending components (bundled into CAL-CH-M4-FCI):

    - CH credit spread (CHF corp vs Confederation; candidate: SNB
      ``rendopa`` — Pfandbrief yields; no FRED mirror known)
    - CH vol index (no SMI vol index readily on FRED; candidate: Yahoo
      ^VSMI which SIX/UBS co-publish; or a realised-vol proxy from
      ^SSMI returns)
    - CHF NEER (SNB ``capaerenexch`` or BIS Trade-Weighted indices; the
      BIS CHF TWI via ``connectors/bis.py`` is a candidate)
    - CH mortgage rate (SNB ``zihypch`` table; no wrapper at Sprint V
      scope)

    Once ≥5 components land, this builder composes
    :class:`M4FciInputs` and the compute-side fallback through
    :func:`sonar.indices.monetary.m4_fci._compute_custom_fci` takes
    over. Until then, :class:`InsufficientDataError` keeps the
    pipeline clean (mirrors M2 CH / M4 AU / CA skip behaviour).
    """
    msg = (
        "M4 CH builder scaffold shipped Sprint V but <5/5 custom-FCI "
        "components available (need credit spread + vol + 10Y + CHF "
        "NEER + mortgage; see CAL-CH-M4-FCI). Raises so the pipeline "
        "skips M4 CH cleanly."
    )
    raise InsufficientDataError(msg)


# ---------------------------------------------------------------------------
# M1 — NO (Sprint X-NO — TE primary → Norges Bank native → FRED OECD stale)
# ---------------------------------------------------------------------------


async def _no_policy_rate_cascade(
    start: date,
    end: date,
    *,
    te: TEConnector | None,
    norgesbank: NorgesBankConnector | None,
    fred: FredConnector,
) -> tuple[list[_DatedValue], tuple[str, ...], tuple[str, ...]]:
    """Fetch NO Policy Rate via TE → Norges Bank → FRED priority-first-wins cascade.

    Returns ``(series_pct, cascade_flags, source_connector_tuple)``.

    Priority ordering mirrors the Sprint I-patch (GB), Sprint L (JP),
    Sprint S (CA), Sprint T (AU), Sprint U-NZ (NZ), and Sprint V (CH)
    cascades (first success wins). NO joins CA, AU, and CH as a country
    with a reachable native secondary slot — the Norges Bank DataAPI
    SDMX-JSON endpoint is public + scriptable + unscreened (Sprint X-NO
    probe 2026-04-22). Daily cadence on both TE primary and Norges Bank
    native; the cascade does **not** attach a monthly qualifier (contrast
    CH's ``CH_POLICY_RATE_SNB_NATIVE_MONTHLY``).

    1. **TE primary** (``fetch_no_policy_rate`` — daily, Norges-Bank-
       sourced via ``NOBRDEP``). Emits ``NO_POLICY_RATE_TE_PRIMARY`` on
       success.
    2. **Norges Bank native** (``fetch_policy_rate`` on ``IR/B.KPRA.SD.R``).
       Emits ``NO_POLICY_RATE_NORGESBANK_NATIVE`` on success. No
       staleness or cadence flag — daily-parity with TE.
    3. **FRED OECD mirror** (``IRSTCI01NOM156N`` — monthly cadence, ~1
       month lag at probe). Last-resort fallback emitting both
       ``NO_POLICY_RATE_FRED_FALLBACK_STALE`` and ``CALIBRATION_STALE``
       so downstream consumers can surface the degradation.

    **Standard positive-only processing** (contrast CH Sprint V): Norway
    never ran a negative policy rate across the full 35Y TE history
    (minimum observed is exactly 0 % during the 2020-05-08 → 2021-09-24
    COVID trough). No ``_NEGATIVE_RATE_ERA_DATA`` flag is emitted; if a
    negative row ever appears the cascade will surface it unchanged but
    no dedicated flag is attached at Sprint X-NO scope.

    All three branches fail-open to the next source on
    :class:`DataUnavailableError` or empty payload. If all three return
    empty the cascade raises ``ValueError``.
    """
    from sonar.overlays.exceptions import DataUnavailableError  # noqa: PLC0415

    hist: list[_DatedValue] | None = None
    flags: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()

    if te is not None:
        try:
            te_obs = await te.fetch_no_policy_rate(start, end)
        except DataUnavailableError:
            te_obs = []
        if te_obs:
            hist = [_DatedValue(o.observation_date, o.value) for o in te_obs]
            flags = ("NO_POLICY_RATE_TE_PRIMARY",)
            sources = ("te",)

    if hist is None and norgesbank is not None:
        try:
            nb_obs = await norgesbank.fetch_policy_rate(start, end)
        except DataUnavailableError:
            nb_obs = []
        if nb_obs:
            hist = [_DatedValue(o.observation_date, o.yield_bps / 100.0) for o in nb_obs]
            flags = ("NO_POLICY_RATE_NORGESBANK_NATIVE",)
            sources = ("norgesbank",)

    if hist is None:
        fred_obs = await fred.fetch_series(FRED_NO_POLICY_RATE_SERIES, start, end)
        if fred_obs:
            hist = [_DatedValue(o.observation_date, o.yield_bps / 100.0) for o in fred_obs]
            flags = ("NO_POLICY_RATE_FRED_FALLBACK_STALE", "CALIBRATION_STALE")
            sources = ("fred",)

    if hist is None:
        msg = "NO Policy Rate unavailable from TE, Norges Bank, and FRED"
        raise ValueError(msg)

    return hist, flags, sources


async def build_m1_no_inputs(
    fred: FredConnector,
    observation_date: date,
    *,
    te: TEConnector | None = None,
    norgesbank: NorgesBankConnector | None = None,
    history_years: int = M1_DEFAULT_LOOKBACK_YEARS,
) -> M1EffectiveRatesInputs:
    """Assemble M1 NO inputs via TE → Norges Bank → FRED cascade + YAML r*/target.

    Sprint X-NO introduces the NO country path using the canonical
    cascade pattern established by Sprint I-patch (GB), Sprint L (JP),
    Sprint S (CA), Sprint T (AU), Sprint U-NZ (NZ), and Sprint V (CH).
    TE's ``interest rate`` indicator for Norway back-fills the full
    Norges Bank key-policy-rate history (``NOBRDEP``) at daily cadence
    to 1991-01-01 and is the empirically preferred source — decisions
    propagate into TE within hours of the Norges Bank announcement.
    Norges Bank's own DataAPI matches the daily cadence exactly
    (SDMX-JSON public endpoint, no staleness flag), and FRED OECD
    mirror (``IRSTCI01NOM156N``) is relegated to last-resort with
    staleness flags.

    NO-specific degradations (Phase 1):

    - ``r_star_pct`` sourced from Norges Bank MPR 1/2024 + Staff Memo
      7/2023 neutral-range mid (1.25 % real). Emits ``R_STAR_PROXY``
      (mirrors GB / JP / CA / AU / NZ / CH pattern).
    - ``expected_inflation_5y_pct`` defaults to Norges Bank 2 % CPI
      target (post-2018-03-02 regime; pre-2018 was 2.5 %). Emits
      ``EXPECTED_INFLATION_CB_TARGET``.
    - ``balance_sheet_pct_gdp_*`` zero-seeded with ``NO_BS_GDP_PROXY_ZERO``
      flag — Norges Bank balance-sheet ratios require Norges Bank MSB +
      Statistics Norway nominal GDP, neither wired at Sprint X-NO scope.
      Lands when CAL-NO-BS-GDP closes. **Special note**: Norway's
      petroleum-wealth savings (GPFG, legally offshore-invested) make
      the domestic balance-sheet ratio unusually small vs. G10 peers;
      downstream regime classifiers should treat NO balance-sheet
      signals with caution until a proper sovereign-fund-adjusted
      series is wired (Phase 2+ research).
    """
    start = observation_date - timedelta(days=history_years * 366)

    policy_hist, cascade_flags, cascade_sources = await _no_policy_rate_cascade(
        start, observation_date, te=te, norgesbank=norgesbank, fred=fred
    )
    latest_policy = _latest_on_or_before(policy_hist, observation_date)
    if latest_policy is None:
        msg = "NO Policy Rate: no observation at or before anchor"
        raise ValueError(msg)
    policy_rate_pct = latest_policy.value / 100.0

    r_star_pct, _is_proxy = resolve_r_star("NO")  # is_proxy always True for NO
    expected_inflation_5y_pct = resolve_inflation_target("NO")

    policy_monthly_pct = _resample_monthly(
        policy_hist, observation_date, n_months=history_years * 12
    )
    real_shadow_hist = [p / 100.0 - expected_inflation_5y_pct for p in policy_monthly_pct]
    stance_hist = [r - r_star_pct for r in real_shadow_hist]

    flags: list[str] = [
        *cascade_flags,
        "R_STAR_PROXY",
        "EXPECTED_INFLATION_CB_TARGET",
        "NO_BS_GDP_PROXY_ZERO",
    ]

    return M1EffectiveRatesInputs(
        country_code="NO",
        observation_date=observation_date,
        policy_rate_pct=policy_rate_pct,
        expected_inflation_5y_pct=expected_inflation_5y_pct,
        r_star_pct=r_star_pct,
        balance_sheet_pct_gdp_current=0.0,
        balance_sheet_pct_gdp_12m_ago=0.0,
        real_shadow_rate_history=tuple(real_shadow_hist),
        stance_vs_neutral_history=tuple(stance_hist),
        balance_sheet_signal_history=tuple([0.0] * len(real_shadow_hist)),
        lookback_years=history_years,
        source_connector=cascade_sources,
        upstream_flags=tuple(flags),
    )


# ---------------------------------------------------------------------------
# M2 — NO (Sprint X-NO — wire-ready scaffold, raises pending CPI + gap)
# ---------------------------------------------------------------------------


async def build_m2_no_inputs(
    fred: FredConnector,
    observation_date: date,
    *,
    te: TEConnector | None = None,
    norgesbank: NorgesBankConnector | None = None,
    oecd_eo: OECDEOConnector | None = None,
    history_years: int = M2_DEFAULT_LOOKBACK_YEARS,
) -> M2TaylorGapsInputs:
    """Assemble M2 NO inputs — full compute live (Week 10 Sprint F).

    Sprint X-NO wired the dispatch; Sprint C wired OECD EO output-gap;
    Sprint F (this commit) wires TE CPI YoY + 12m-ahead forecast via
    :meth:`TEConnector.fetch_no_cpi_yoy` and
    :meth:`TEConnector.fetch_no_inflation_forecast`.

    Norges Bank target: 2 % CPI (reduced from 2.5 % on 2018-03-02).
    ``bc_targets.yaml`` returns the current 2 % — backtests anchoring
    pre-2018 need to override in-loader.
    """
    start = observation_date - timedelta(days=history_years * 366)
    policy_hist, cascade_flags, cascade_sources = await _no_policy_rate_cascade(
        start, observation_date, te=te, norgesbank=norgesbank, fred=fred
    )
    cpi_obs = await _try_fetch_cpi_yoy(te, start, observation_date, "fetch_no_cpi_yoy")
    forecast_12m_pct, forecast_flags = await _try_fetch_inflation_forecast_12m(
        te, "NO", observation_date, "fetch_no_inflation_forecast"
    )
    gap_pct = await _try_fetch_oecd_output_gap_pct(oecd_eo, "NO", observation_date)
    return await _assemble_m2_full_compute(
        country_code="NO",
        observation_date=observation_date,
        policy_hist=policy_hist,
        cascade_flags=cascade_flags,
        cascade_sources=cascade_sources,
        cpi_observations=cpi_obs,
        forecast_12m_pct=forecast_12m_pct,
        forecast_flags=forecast_flags,
        output_gap_pct=gap_pct,
        history_years=history_years,
    )


# ---------------------------------------------------------------------------
# M4 — NO (Sprint X-NO — wire-ready scaffold, raises pending FCI components)
# ---------------------------------------------------------------------------


async def build_m4_no_inputs(
    fred: FredConnector,  # noqa: ARG001 - wired for future NO FCI components
    observation_date: date,  # noqa: ARG001
    *,
    te: TEConnector | None = None,  # noqa: ARG001
    norgesbank: NorgesBankConnector | None = None,  # noqa: ARG001
    history_years: int = M4_DEFAULT_LOOKBACK_YEARS,  # noqa: ARG001
) -> M4FciInputs:
    """Assemble M4 NO inputs (scaffold — raises until ≥5 FCI components).

    NO lacks the direct-provider shortcut that US gets via Chicago Fed
    NFCI, so NO must walk the spec §4 custom path which needs
    ``MIN_CUSTOM_COMPONENTS == 5`` of the seven FCI inputs. At Sprint
    X-NO close the reachable components are:

    - 10Y Norwegian government bond yield via Norges Bank DataAPI
      ``GOVT_GENERIC_RATES/B.10Y.GBON`` (wired C2)
    - Policy rate via the M1 cascade (wired C4)

    Pending components (bundled into CAL-NO-M4-FCI):

    - NO credit spread (BBB NOK corp vs Norwegian gov; candidate:
      Nordic Credit Rating / Nordea indices, or SSB corporate-bond
      yield tables — SSB table 12132 tracks long-term corp yields at
      quarterly cadence)
    - NO vol index (no OSE-VIX-analog published; candidate: realised-
      vol proxy from OBX 25 Index returns, or Yahoo Finance ^OSEBX)
    - NOK NEER (Norges Bank ``EXR`` dataflow publishes the TWI-based
      effective exchange rate as ``I-44`` — wire-ready via an
      additional Norges Bank DataAPI call, deferred to Phase 2+)
    - NO mortgage rate (SSB table 10746 tracks mortgage-rate averages
      at monthly cadence; no wrapper at Sprint X-NO scope)

    **Petroleum context**: Norway's oil-NOK coupling is a structural
    feature that future NO FCI work needs to address — Brent / WTI
    price moves propagate into NOK exchange-rate and domestic
    petroleum-sector credit conditions within trading days, which is
    tighter than any other G10 FCI-component coupling (contrast the
    CAD / AUD / NZD commodity-currency pairs where the transmission
    is more diffuse). This is Phase 2+ research scope, NOT Sprint X-NO
    scope — the scaffold raises uniformly regardless of oil regime.

    Once ≥5 components land, this builder composes
    :class:`M4FciInputs` and the compute-side fallback through
    :func:`sonar.indices.monetary.m4_fci._compute_custom_fci` takes
    over. Until then, :class:`InsufficientDataError` keeps the pipeline
    clean (mirrors M2 NO / M4 NZ / CH skip behaviour).
    """
    msg = (
        "M4 NO builder scaffold shipped Sprint X-NO but <5/5 custom-FCI "
        "components available (need credit spread + vol + 10Y + NOK "
        "NEER + mortgage; see CAL-NO-M4-FCI). Raises so the pipeline "
        "skips M4 NO cleanly."
    )
    raise InsufficientDataError(msg)


# ---------------------------------------------------------------------------
# M1 — SE (Sprint W-SE TE → Riksbank → FRED cascade + negative-rate era flag)
# ---------------------------------------------------------------------------


async def _se_policy_rate_cascade(
    start: date,
    end: date,
    *,
    te: TEConnector | None,
    riksbank: RiksbankConnector | None,
    fred: FredConnector,
) -> tuple[list[_DatedValue], tuple[str, ...], tuple[str, ...]]:
    """Fetch SE Policy Rate via TE → Riksbank → FRED priority-first-wins cascade.

    Returns ``(series_pct, cascade_flags, source_connector_tuple)``.

    Priority ordering mirrors the Sprint I-patch (GB), Sprint L (JP),
    Sprint S (CA), Sprint T (AU), Sprint U-NZ, and Sprint V (CH)
    cascades (first success wins). SE joins CA / AU / CH as the fourth
    country with a reachable native secondary slot — the Riksbank Swea
    JSON REST API is public + unscreened. Unlike the CH / AU natives
    which land at monthly cadence, Swea ships SECBREPOEFF at **daily**
    cadence matching TE's primary — so the secondary lands
    ``SE_POLICY_RATE_RIKSBANK_NATIVE`` alone (no ``*_MONTHLY`` cadence
    flag), and no ``CALIBRATION_STALE`` is emitted on this path.

    1. **TE primary** (``fetch_se_policy_rate`` — daily, Riksbank-
       sourced via ``SWRRATEI``). Emits ``SE_POLICY_RATE_TE_PRIMARY``
       on success.
    2. **Riksbank native** (``fetch_policy_rate`` on ``SECBREPOEFF``).
       Emits ``SE_POLICY_RATE_RIKSBANK_NATIVE`` on success.
    3. **FRED OECD mirror** (``IRSTCI01SEM156N`` — **discontinued at
       2020-10-01** per Sprint W-SE probe, ~5.5 years frozen). Last-
       resort fallback emitting both
       ``SE_POLICY_RATE_FRED_FALLBACK_STALE`` and ``CALIBRATION_STALE``
       so downstream consumers can surface the degradation. The FRED
       SE mirror is substantially more broken than the CH / AU / NZ
       mirrors (which stay within 1-12 months of real time); the flag
       pair should be treated as near-permanent for any post-2020
       anchor rather than a transient cache lag.

    **Negative-rate era**: when the resolved history contains at least
    one strictly-negative observation, the cascade additionally emits
    ``SE_NEGATIVE_RATE_ERA_DATA`` — preserving the signal that the
    window spans the 2015-02-12 → 2019-11-30 Riksbank negative
    corridor (minimum policy rate -0.50 %, roughly two-thirds the
    depth of SNB's -0.75 % corridor). Mirrors the Sprint V-CH
    ``CH_NEGATIVE_RATE_ERA_DATA`` flag contract: the flag attaches to
    the **value**, not the source — all three cascade depths emit it
    when the resolved window contains any strictly-negative value.

    All three branches fail-open to the next source on
    :class:`DataUnavailableError` or empty payload. If all three
    return empty the cascade raises ``ValueError``.
    """
    from sonar.overlays.exceptions import DataUnavailableError  # noqa: PLC0415

    hist: list[_DatedValue] | None = None
    flags: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()

    if te is not None:
        try:
            te_obs = await te.fetch_se_policy_rate(start, end)
        except DataUnavailableError:
            te_obs = []
        if te_obs:
            hist = [_DatedValue(o.observation_date, o.value) for o in te_obs]
            flags = ("SE_POLICY_RATE_TE_PRIMARY",)
            sources = ("te",)

    if hist is None and riksbank is not None:
        try:
            riks_obs = await riksbank.fetch_policy_rate(start, end)
        except DataUnavailableError:
            riks_obs = []
        if riks_obs:
            hist = [_DatedValue(o.observation_date, o.yield_bps / 100.0) for o in riks_obs]
            flags = ("SE_POLICY_RATE_RIKSBANK_NATIVE",)
            sources = ("riksbank",)

    if hist is None:
        fred_obs = await fred.fetch_series(FRED_SE_POLICY_RATE_SERIES, start, end)
        if fred_obs:
            hist = [_DatedValue(o.observation_date, o.yield_bps / 100.0) for o in fred_obs]
            flags = ("SE_POLICY_RATE_FRED_FALLBACK_STALE", "CALIBRATION_STALE")
            sources = ("fred",)

    if hist is None:
        msg = "SE Policy Rate unavailable from TE, Riksbank, and FRED"
        raise ValueError(msg)

    if any(o.value < 0 for o in hist):
        flags = (*flags, "SE_NEGATIVE_RATE_ERA_DATA")
    return hist, flags, sources


async def build_m1_se_inputs(
    fred: FredConnector,
    observation_date: date,
    *,
    te: TEConnector | None = None,
    riksbank: RiksbankConnector | None = None,
    history_years: int = M1_DEFAULT_LOOKBACK_YEARS,
) -> M1EffectiveRatesInputs:
    """Assemble M1 SE inputs via TE → Riksbank → FRED cascade + YAML r*/target.

    Sprint W-SE introduces the SE country path using the canonical
    cascade pattern established by Sprint I-patch (GB), Sprint L (JP),
    Sprint S (CA), Sprint T (AU), Sprint U-NZ, and Sprint V (CH). TE's
    ``interest rate`` indicator for Sweden back-fills the full
    Riksbank policy-rate history (``SWRRATEI``) at daily cadence
    across the 2015-2019 negative-rate corridor and is the empirically
    preferred source — decisions propagate into TE within hours of the
    Riksbank announcement, whereas the FRED OECD mirror
    (``IRSTCI01SEM156N``) is **discontinued at 2020-10-01** and frozen
    indefinitely. Riksbank Swea ``SECBREPOEFF`` sits in the secondary
    slot as a first-class public JSON REST native at daily cadence —
    a tighter cadence match than CH / AU where the native is monthly.

    SE-specific degradations and Phase-1 proxies:

    - ``r_star_pct`` sourced from Riksbank MPR March 2026 neutral-rate
      range midpoint (0.75 % real) — Swedish r* sits in the Nordic
      low-r* cluster but above CH because SE lacks CHF-specific safe-
      haven compression. Emits ``R_STAR_PROXY`` (mirrors GB / JP / CA
      / AU / NZ / CH pattern).
    - ``expected_inflation_5y_pct`` defaults to the Riksbank 2 % CPIF
      point target — unlike CH's 0-2 % SNB band, the Riksbank ships a
      clean explicit target (since 1993; CPIF basis since 2017) so no
      ``SE_INFLATION_TARGET_BAND`` flag is needed. Emits
      ``EXPECTED_INFLATION_CB_TARGET`` (proxy-source flag) only.
    - ``balance_sheet_pct_gdp_*`` zero-seeded with
      ``SE_BS_GDP_PROXY_ZERO`` flag — Riksbank balance sheet requires
      the Riksbank Monthly Statistical Bulletin combined with SCB
      nominal GDP; neither wired at Sprint W-SE scope. Lands when
      CAL-SE-BS-GDP closes.
    - **Negative-rate era flag** — when the resolved cascade history
      contains ≥ 1 strictly-negative observation, the cascade emits
      ``SE_NEGATIVE_RATE_ERA_DATA`` (same post-resolution augmentation
      pattern Sprint V-CH established) so downstream M1 / real-shadow
      computations can branch on negative-policy-rate regimes.
    """
    start = observation_date - timedelta(days=history_years * 366)

    policy_hist, cascade_flags, cascade_sources = await _se_policy_rate_cascade(
        start, observation_date, te=te, riksbank=riksbank, fred=fred
    )
    latest_policy = _latest_on_or_before(policy_hist, observation_date)
    if latest_policy is None:
        msg = "SE Policy Rate: no observation at or before anchor"
        raise ValueError(msg)
    policy_rate_pct = latest_policy.value / 100.0

    r_star_pct, _is_proxy = resolve_r_star("SE")  # is_proxy always True for SE
    # Riksbank 2 % CPIF point target — bc_targets.yaml SE → Riksbank → 0.02.
    expected_inflation_5y_pct = resolve_inflation_target("SE")

    policy_monthly_pct = _resample_monthly(
        policy_hist, observation_date, n_months=history_years * 12
    )
    real_shadow_hist = [p / 100.0 - expected_inflation_5y_pct for p in policy_monthly_pct]
    stance_hist = [r - r_star_pct for r in real_shadow_hist]

    flags: list[str] = [
        *cascade_flags,
        "R_STAR_PROXY",
        "EXPECTED_INFLATION_CB_TARGET",
        "SE_BS_GDP_PROXY_ZERO",
    ]

    return M1EffectiveRatesInputs(
        country_code="SE",
        observation_date=observation_date,
        policy_rate_pct=policy_rate_pct,
        expected_inflation_5y_pct=expected_inflation_5y_pct,
        r_star_pct=r_star_pct,
        balance_sheet_pct_gdp_current=0.0,
        balance_sheet_pct_gdp_12m_ago=0.0,
        real_shadow_rate_history=tuple(real_shadow_hist),
        stance_vs_neutral_history=tuple(stance_hist),
        balance_sheet_signal_history=tuple([0.0] * len(real_shadow_hist)),
        lookback_years=history_years,
        source_connector=cascade_sources,
        upstream_flags=tuple(flags),
    )


# ---------------------------------------------------------------------------
# M2 — SE (Sprint W-SE — wire-ready scaffold, raises pending CPI + gap)
# ---------------------------------------------------------------------------


async def build_m2_se_inputs(
    fred: FredConnector,
    observation_date: date,
    *,
    te: TEConnector | None = None,
    riksbank: RiksbankConnector | None = None,
    oecd_eo: OECDEOConnector | None = None,
    history_years: int = M2_DEFAULT_LOOKBACK_YEARS,
) -> M2TaylorGapsInputs:
    """Assemble M2 SE inputs — full compute live (Week 10 Sprint F).

    Sprint W-SE wired the dispatch; Sprint C wired OECD EO output-gap;
    Sprint F (this commit) wires TE CPI YoY + 12m-ahead forecast via
    :meth:`TEConnector.fetch_se_cpi_yoy` and
    :meth:`TEConnector.fetch_se_inflation_forecast`.

    Note: Riksbank target is **CPIF** (2 % point target since 2017);
    TE returns headline CPI, not CPIF. Gap typically <= 30 bps; the
    headline CPI path ships as the Sprint F primary per the brief's
    scope note. A CPIF-specific wrapper can land under a Phase 2+
    sprint if the M2 compute requires CPIF strictness.
    """
    start = observation_date - timedelta(days=history_years * 366)
    policy_hist, cascade_flags, cascade_sources = await _se_policy_rate_cascade(
        start, observation_date, te=te, riksbank=riksbank, fred=fred
    )
    cpi_obs = await _try_fetch_cpi_yoy(te, start, observation_date, "fetch_se_cpi_yoy")
    forecast_12m_pct, forecast_flags = await _try_fetch_inflation_forecast_12m(
        te, "SE", observation_date, "fetch_se_inflation_forecast"
    )
    gap_pct = await _try_fetch_oecd_output_gap_pct(oecd_eo, "SE", observation_date)
    return await _assemble_m2_full_compute(
        country_code="SE",
        observation_date=observation_date,
        policy_hist=policy_hist,
        cascade_flags=cascade_flags,
        cascade_sources=cascade_sources,
        cpi_observations=cpi_obs,
        forecast_12m_pct=forecast_12m_pct,
        forecast_flags=forecast_flags,
        output_gap_pct=gap_pct,
        history_years=history_years,
        extra_flags=("SE_M2_CPI_HEADLINE_NOT_CPIF",),
    )


# ---------------------------------------------------------------------------
# M4 — SE (Sprint W-SE — wire-ready scaffold, raises pending FCI components)
# ---------------------------------------------------------------------------


async def build_m4_se_inputs(
    fred: FredConnector,  # noqa: ARG001 - wired for future SE FCI components
    observation_date: date,  # noqa: ARG001
    *,
    te: TEConnector | None = None,  # noqa: ARG001
    riksbank: RiksbankConnector | None = None,  # noqa: ARG001
    history_years: int = M4_DEFAULT_LOOKBACK_YEARS,  # noqa: ARG001
) -> M4FciInputs:
    """Assemble M4 SE inputs (scaffold — raises until ≥5 FCI components).

    SE lacks the direct-provider shortcut that US gets via Chicago Fed
    NFCI, so SE must walk the spec §4 custom path which needs
    ``MIN_CUSTOM_COMPONENTS == 5`` of the seven FCI inputs. At Sprint
    W-SE close the reachable components are:

    - 10Y SGB (Swedish Government Bond) yield via FRED
      ``IRLTLT01SEM156N`` OECD mirror (monthly; active, last 2026-03
      at probe) — could also come via TE ``SGBG10:IND``
    - Policy rate via the M1 cascade (wired C4) + corridor floor /
      ceiling (SECBDEPOEFF / SECBLENDEFF on Swea, shipped C2)

    Pending components (bundled into CAL-SE-M4-FCI):

    - SE credit spread (SEK corp vs SGB; Riksbank FMÖ / SCB sources;
      no FRED mirror known)
    - SE vol index (no OMXS30 vol index readily on FRED; candidate:
      Nasdaq OMX's VINX30 or a realised-vol proxy from ^OMXS30
      returns via Yahoo Finance)
    - SEK NEER (Riksbank publishes the KIX effective exchange-rate
      index; candidate: Riksbank Swea ``SEKKIX`` or the BIS
      Trade-Weighted indices via ``connectors/bis.py``)
    - SE mortgage rate (SCB MFI lending rates; no wrapper at Sprint
      W-SE scope)

    Once ≥5 components land, this builder composes
    :class:`M4FciInputs` and the compute-side fallback through
    :func:`sonar.indices.monetary.m4_fci._compute_custom_fci` takes
    over. Until then, :class:`InsufficientDataError` keeps the
    pipeline clean (mirrors M2 SE / M4 CH / AU / CA skip behaviour).
    """
    msg = (
        "M4 SE builder scaffold shipped Sprint W-SE but <5/5 custom-FCI "
        "components available (need credit spread + vol + 10Y + SEK "
        "NEER + mortgage; see CAL-SE-M4-FCI). Raises so the pipeline "
        "skips M4 SE cleanly."
    )
    raise InsufficientDataError(msg)


# ---------------------------------------------------------------------------
# M1 — DK (Sprint Y-DK TE → Nationalbanken → FRED cascade + EUR-peg flags)
# ---------------------------------------------------------------------------


async def _dk_policy_rate_cascade(
    start: date,
    end: date,
    *,
    te: TEConnector | None,
    nationalbanken: NationalbankenConnector | None,
    fred: FredConnector,
) -> tuple[list[_DatedValue], tuple[str, ...], tuple[str, ...]]:
    """Fetch DK Policy Rate via TE → Nationalbanken → FRED priority-first-wins cascade.

    Returns ``(series_pct, cascade_flags, source_connector_tuple)``.

    Priority ordering mirrors the Sprint I-patch (GB), Sprint L (JP),
    Sprint S (CA), Sprint T (AU), Sprint U-NZ, Sprint V (CH), Sprint
    X-NO (NO), and Sprint W-SE (SE) cascades (first success wins).
    DK joins as the **third negative-rate country** (after CH and SE)
    and the **first EUR-peg country** in the cascade family.

    1. **TE primary** (``fetch_dk_policy_rate`` — daily, Nationalbanken-
       sourced via ``DEBRDISC`` = the legacy DISCOUNT rate
       ``diskontoen``). Emits ``DK_POLICY_RATE_TE_PRIMARY`` on success.
    2. **Nationalbanken native** (``fetch_policy_rate`` on ``OIBNAA``
       = the certificate-of-deposit rate ``indskudsbevisrenten`` —
       the active EUR-peg defence tool). Emits
       ``DK_POLICY_RATE_NATIONALBANKEN_NATIVE`` on success. Both
       cascade slots are daily-cadence so the secondary lands the
       single-element flag pair (no ``*_MONTHLY`` qualifier — matches
       the Sprint W-SE Riksbank pattern, not the CH / AU monthly-
       native pattern).
    3. **FRED OECD mirror** (``IRSTCI01DKM156N`` — fresh at probe,
       ~4-month lag). Last-resort fallback emitting both
       ``DK_POLICY_RATE_FRED_FALLBACK_STALE`` and ``CALIBRATION_STALE``
       so the monthly-vs-daily cadence delta surfaces to operators.

    **Source-instrument divergence** (Sprint Y-DK key empirical
    finding; documented in :class:`TEConnector.fetch_dk_policy_rate` +
    :class:`NationalbankenConnector` module docstrings + retro §4):
    TE returns the legacy DISCOUNT rate ``DEBRDISC`` (i.e. the same
    instrument as Statbank ``ODKNAA``), while the Nationalbanken
    native cascade slot returns the **CD rate** ``OIBNAA`` — the
    actual EUR-peg defence tool. The two diverged sharply across the
    2014-2022 negative-rate corridor (CD trough -0.75 % at
    2015-04-07 with 2450 strictly-negative daily observations through
    2020-01-07; discount only briefly negative 2021-2022 with 18
    observations and a -0.60 % min). The cascade flag-emission
    contract (``*_TE_PRIMARY`` vs ``*_NATIONALBANKEN_NATIVE``)
    surfaces the source so downstream consumers can pick the right
    semantic — both representations are operationally valid.

    **Negative-rate era**: when the resolved history contains at
    least one strictly-negative observation, the cascade additionally
    emits ``DK_NEGATIVE_RATE_ERA_DATA`` — the third-country
    instantiation of the Sprint V-CH ``CH_NEGATIVE_RATE_ERA_DATA``
    pattern (after SE Sprint W-SE). Mirrors the same flag contract:
    attaches to the **value**, not the source — all three cascade
    depths emit it when the resolved window contains any
    strictly-negative value. Note the divergence implication: a
    TE-primary resolution will only emit this flag for
    2021-03-31 → 2022-08-31 windows (the brief discount-rate dip),
    while a Nationalbanken-native resolution will emit it for the
    full 2015-04-07 → 2022-09-15 EUR-peg-defence corridor.

    All three branches fail-open to the next source on
    :class:`DataUnavailableError` or empty payload. If all three
    return empty the cascade raises ``ValueError``.
    """
    from sonar.overlays.exceptions import DataUnavailableError  # noqa: PLC0415

    hist: list[_DatedValue] | None = None
    flags: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()

    if te is not None:
        try:
            te_obs = await te.fetch_dk_policy_rate(start, end)
        except DataUnavailableError:
            te_obs = []
        if te_obs:
            hist = [_DatedValue(o.observation_date, o.value) for o in te_obs]
            flags = ("DK_POLICY_RATE_TE_PRIMARY",)
            sources = ("te",)

    if hist is None and nationalbanken is not None:
        try:
            nb_obs = await nationalbanken.fetch_policy_rate(start, end)
        except DataUnavailableError:
            nb_obs = []
        if nb_obs:
            hist = [_DatedValue(o.observation_date, o.yield_bps / 100.0) for o in nb_obs]
            flags = ("DK_POLICY_RATE_NATIONALBANKEN_NATIVE",)
            sources = ("nationalbanken",)

    if hist is None:
        fred_obs = await fred.fetch_series(FRED_DK_POLICY_RATE_SERIES, start, end)
        if fred_obs:
            hist = [_DatedValue(o.observation_date, o.yield_bps / 100.0) for o in fred_obs]
            flags = ("DK_POLICY_RATE_FRED_FALLBACK_STALE", "CALIBRATION_STALE")
            sources = ("fred",)

    if hist is None:
        msg = "DK Policy Rate unavailable from TE, Nationalbanken, and FRED"
        raise ValueError(msg)

    if any(o.value < 0 for o in hist):
        flags = (*flags, "DK_NEGATIVE_RATE_ERA_DATA")
    return hist, flags, sources


async def build_m1_dk_inputs(
    fred: FredConnector,
    observation_date: date,
    *,
    te: TEConnector | None = None,
    nationalbanken: NationalbankenConnector | None = None,
    history_years: int = M1_DEFAULT_LOOKBACK_YEARS,
) -> M1EffectiveRatesInputs:
    """Assemble M1 DK inputs via TE → Nationalbanken → FRED cascade + YAML r*/target.

    Sprint Y-DK introduces the DK country path using the canonical
    cascade pattern established by Sprint I-patch (GB), Sprint L (JP),
    Sprint S (CA), Sprint T (AU), Sprint U-NZ, Sprint V (CH), Sprint
    X-NO (NO), and Sprint W-SE (SE). DK is the **third negative-rate
    country** (after CH and SE) and the **first EUR-peg country** in
    the cascade family.

    DK-specific degradations and Phase-1 conventions:

    - ``r_star_pct`` sourced from Nationalbanken WP 152/2020 +
      Monetary Review 2024 neutral-range midpoint synthesis (0.75 %
      real) — Danish r* sits in the Nordic low-r* cluster (matches
      SE; above CH because DKK lacks the CHF-specific safe-haven
      compression). Emits ``R_STAR_PROXY``.
    - ``expected_inflation_5y_pct`` defaults to the **ECB 2 % HICP
      target imported via the DKK/EUR ERM-II peg** — Nationalbanken
      does not publish a domestic inflation target (mandate is
      exchange-rate stability). The cascade emits the
      **DK-specific** flag
      ``DK_INFLATION_TARGET_IMPORTED_FROM_EA`` (always) instead of
      the standard ``EXPECTED_INFLATION_CB_TARGET`` flag the other
      countries emit. The convention is materialised in
      ``bc_targets.yaml`` via the ``target_conventions`` block + the
      :func:`resolve_inflation_target_convention` resolver hook.
    - ``balance_sheet_pct_gdp_*`` zero-seeded with
      ``DK_BS_GDP_PROXY_ZERO`` flag — Nationalbanken balance sheet
      requires the Nationalbanken Monthly Statistical Bulletin
      combined with Statistics Denmark nominal GDP; neither wired
      at Sprint Y-DK scope. Lands when CAL-DK-BS-GDP closes.
    - **Negative-rate era flag** — when the resolved cascade history
      contains ≥ 1 strictly-negative observation, the cascade emits
      ``DK_NEGATIVE_RATE_ERA_DATA`` (same post-resolution
      augmentation pattern Sprint V-CH established) so downstream
      M1 / real-shadow computations can branch on negative-policy-
      rate regimes. Note source-instrument divergence: TE-primary
      windows only see the brief 2021-03-31 → 2022-08-31 discount-
      rate dip (18 obs, min -0.60 %); Nationalbanken-native windows
      see the full 2015-04-07 → 2022-09-15 CD-rate EUR-peg-defence
      corridor (2450 obs, min -0.75 %).
    """
    start = observation_date - timedelta(days=history_years * 366)

    policy_hist, cascade_flags, cascade_sources = await _dk_policy_rate_cascade(
        start, observation_date, te=te, nationalbanken=nationalbanken, fred=fred
    )
    latest_policy = _latest_on_or_before(policy_hist, observation_date)
    if latest_policy is None:
        msg = "DK Policy Rate: no observation at or before anchor"
        raise ValueError(msg)
    policy_rate_pct = latest_policy.value / 100.0

    r_star_pct, _is_proxy = resolve_r_star("DK")  # is_proxy always True for DK
    # ECB 2 % HICP target imported via DKK/EUR ERM-II peg —
    # bc_targets.yaml DK → ECB → 0.02. Convention surfaced via the
    # DK_INFLATION_TARGET_IMPORTED_FROM_EA flag below.
    expected_inflation_5y_pct = resolve_inflation_target("DK")
    target_convention = resolve_inflation_target_convention("DK")
    inflation_target_flag = (
        "DK_INFLATION_TARGET_IMPORTED_FROM_EA"
        if target_convention == "imported_eur_peg"
        else "EXPECTED_INFLATION_CB_TARGET"
    )

    policy_monthly_pct = _resample_monthly(
        policy_hist, observation_date, n_months=history_years * 12
    )
    real_shadow_hist = [p / 100.0 - expected_inflation_5y_pct for p in policy_monthly_pct]
    stance_hist = [r - r_star_pct for r in real_shadow_hist]

    flags: list[str] = [
        *cascade_flags,
        "R_STAR_PROXY",
        inflation_target_flag,
        "DK_BS_GDP_PROXY_ZERO",
    ]

    return M1EffectiveRatesInputs(
        country_code="DK",
        observation_date=observation_date,
        policy_rate_pct=policy_rate_pct,
        expected_inflation_5y_pct=expected_inflation_5y_pct,
        r_star_pct=r_star_pct,
        balance_sheet_pct_gdp_current=0.0,
        balance_sheet_pct_gdp_12m_ago=0.0,
        real_shadow_rate_history=tuple(real_shadow_hist),
        stance_vs_neutral_history=tuple(stance_hist),
        balance_sheet_signal_history=tuple([0.0] * len(real_shadow_hist)),
        lookback_years=history_years,
        source_connector=cascade_sources,
        upstream_flags=tuple(flags),
    )


# ---------------------------------------------------------------------------
# M2 — DK (Sprint Y-DK — wire-ready scaffold, raises pending CPI + gap)
# ---------------------------------------------------------------------------


async def build_m2_dk_inputs(
    fred: FredConnector,
    observation_date: date,
    *,
    te: TEConnector | None = None,
    nationalbanken: NationalbankenConnector | None = None,
    oecd_eo: OECDEOConnector | None = None,
    history_years: int = M2_DEFAULT_LOOKBACK_YEARS,
) -> M2TaylorGapsInputs:
    """Assemble M2 DK inputs — full compute live (Week 10 Sprint F).

    Sprint Y-DK wired the dispatch; Sprint C wired OECD EO output-gap;
    Sprint F (this commit) wires TE CPI YoY + 12m-ahead forecast via
    :meth:`TEConnector.fetch_dk_cpi_yoy` and
    :meth:`TEConnector.fetch_dk_inflation_forecast`. The
    :func:`resolve_inflation_target` path picks up the
    ``imported_eur_peg`` convention from ``bc_targets.yaml`` and
    :func:`_assemble_m2_full_compute` emits
    ``DK_INFLATION_TARGET_IMPORTED_FROM_EA`` automatically; the ECB
    target value (2 %) is used as the DK target.

    **Known limitation** preserved from Sprint Y-DK: the vanilla
    Taylor-gap formula will systematically mis-fit DK because
    Nationalbanken does not run an independent monetary policy — the
    policy-rate response function is dominated by the EUR-peg-
    defence imperative. The EUR-peg-aware spec revision is tracked
    separately under ``CAL-DK-M2-EUR-PEG-TAYLOR`` (Phase 2+).
    Sprint F ships the full compute regardless so operators can
    quantify the mis-fit empirically.
    """
    start = observation_date - timedelta(days=history_years * 366)
    policy_hist, cascade_flags, cascade_sources = await _dk_policy_rate_cascade(
        start, observation_date, te=te, nationalbanken=nationalbanken, fred=fred
    )
    cpi_obs = await _try_fetch_cpi_yoy(te, start, observation_date, "fetch_dk_cpi_yoy")
    forecast_12m_pct, forecast_flags = await _try_fetch_inflation_forecast_12m(
        te, "DK", observation_date, "fetch_dk_inflation_forecast"
    )
    gap_pct = await _try_fetch_oecd_output_gap_pct(oecd_eo, "DK", observation_date)
    return await _assemble_m2_full_compute(
        country_code="DK",
        observation_date=observation_date,
        policy_hist=policy_hist,
        cascade_flags=cascade_flags,
        cascade_sources=cascade_sources,
        cpi_observations=cpi_obs,
        forecast_12m_pct=forecast_12m_pct,
        forecast_flags=forecast_flags,
        output_gap_pct=gap_pct,
        history_years=history_years,
        extra_flags=("DK_M2_EUR_PEG_TAYLOR_MISFIT",),
    )


# ---------------------------------------------------------------------------
# M4 — DK (Sprint Y-DK — wire-ready scaffold, raises pending FCI components)
# ---------------------------------------------------------------------------


async def build_m4_dk_inputs(
    fred: FredConnector,  # noqa: ARG001 - wired for future DK FCI components
    observation_date: date,  # noqa: ARG001
    *,
    te: TEConnector | None = None,  # noqa: ARG001
    nationalbanken: NationalbankenConnector | None = None,  # noqa: ARG001
    history_years: int = M4_DEFAULT_LOOKBACK_YEARS,  # noqa: ARG001
) -> M4FciInputs:
    """Assemble M4 DK inputs (scaffold — raises until ≥5 FCI components).

    DK lacks the direct-provider shortcut that US gets via Chicago Fed
    NFCI, so DK must walk the spec §4 custom path which needs
    ``MIN_CUSTOM_COMPONENTS == 5`` of the seven FCI inputs. At Sprint
    Y-DK close the reachable components are:

    - 10Y DGB (Danish Government Bond) yield via FRED
      ``IRLTLT01DKM156N`` OECD mirror (monthly; active, last 2026-02
      at probe) — could also come via TE.
    - Policy rate via the M1 cascade (wired C4) + corridor floor /
      ceiling (Nationalbanken OFONAA / OIRNAA on Statbank, shipped
      C2 alongside the CD rate).

    Pending components (bundled into CAL-DK-M4-FCI):

    - DK credit spread (DKK corp vs DGB; Nationalbanken FNOR /
      Statbank sources; no FRED mirror known)
    - DK vol index (no OMXC25 vol index readily on FRED; candidate:
      Nasdaq OMX's VINX25 or a realised-vol proxy from ^OMXC25
      returns via Yahoo Finance)
    - DKK NEER (Nationalbanken publishes the effective exchange-rate
      index; the EUR-peg keeps DKK NEER tightly coupled to EUR NEER
      so a pragmatic alternative is to consume the BIS Trade-
      Weighted indices via ``connectors/bis.py``)
    - DK mortgage rate (Statbank MFI lending rates; no wrapper at
      Sprint Y-DK scope)

    EUR-peg implication: the FCI components above are heavily
    EUR-coupled — Danish credit spreads, vol, NEER, and mortgage
    rates all move with EUR-area cycles much more than would be the
    case in an independent-monetary-policy country. This argues for
    a hybrid M4 DK that blends DK-specific + EA-area inputs in
    Phase 2+ (CAL-DK-M4-EUR-PEG-FCI).

    Once ≥ 5 components land, this builder composes
    :class:`M4FciInputs` and the compute-side fallback through
    :func:`sonar.indices.monetary.m4_fci._compute_custom_fci` takes
    over. Until then, :class:`InsufficientDataError` keeps the
    pipeline clean (mirrors M2 DK / M4 SE skip behaviour).
    """
    msg = (
        "M4 DK builder scaffold shipped Sprint Y-DK but <5/5 custom-FCI "
        "components available (need credit spread + vol + 10Y + DKK "
        "NEER + mortgage; see CAL-DK-M4-FCI + CAL-DK-M4-EUR-PEG-FCI). "
        "Raises so the pipeline skips M4 DK cleanly."
    )
    raise InsufficientDataError(msg)


def _ea_balance_sheet_signal_history(
    bs: Sequence[_DatedValue],
    gdp_resolver: Callable[[date], float],
    anchor: date,
    n_months: int,
) -> list[float]:
    def _ratio_at(d: date) -> float | None:
        b = _latest_on_or_before(bs, d)
        if b is None:
            return None
        gdp_value = gdp_resolver(d)
        if gdp_value == 0:
            return None
        return b.value / gdp_value

    ratios: list[tuple[date, float]] = []
    year, month = anchor.year, anchor.month
    for _ in range(n_months + 12):
        me = _last_day_of_month(year, month)
        r = _ratio_at(min(me, anchor))
        if r is None:
            break
        ratios.append((me, r))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    ratios.reverse()

    out: list[float] = []
    for i in range(12, len(ratios)):
        out.append(-(ratios[i][1] - ratios[i - 12][1]))
    return out[-n_months:]


# ---------------------------------------------------------------------------
# M2 — US
# ---------------------------------------------------------------------------


async def build_m2_us_inputs(
    fred: FredConnector,
    cbo: CboConnector,
    observation_date: date,
    *,
    history_years: int = M2_DEFAULT_LOOKBACK_YEARS,
) -> M2TaylorGapsInputs:
    """Assemble M2 US inputs from FRED + CBO + YAML."""
    start = observation_date - timedelta(days=history_years * 366)

    upper = _to_dated(await fred.fetch_fed_funds_target_upper_us(start, observation_date))
    lower = _to_dated(await fred.fetch_fed_funds_target_lower_us(start, observation_date))
    policy_rate_pct = _us_policy_rate_pct(upper, lower, observation_date)
    prev_policy_rate_pct = _us_policy_rate_prev_month(upper, lower, observation_date)

    infl = _to_dated(await fred.fetch_pce_core_yoy_us(start, observation_date))
    latest_infl = _latest_on_or_before(infl, observation_date)
    if latest_infl is None:
        msg = "No PCEPILFE YoY observation at or before anchor"
        raise ValueError(msg)
    inflation_yoy_pct = latest_infl.value  # already decimal (YoY transform returns decimal)

    gaps = _to_dated(await cbo.fetch_output_gap_us(start, observation_date), value_attr="gap")
    latest_gap = _latest_on_or_before(gaps, observation_date)
    if latest_gap is None:
        msg = "No CBO output-gap observation at or before anchor"
        raise ValueError(msg)
    output_gap_pct = latest_gap.value

    r_star_pct, _is_proxy = resolve_r_star("US")
    inflation_target_pct = resolve_inflation_target("US")

    # Forward 2Y expected inflation: UMich 5Y as proxy — spec §4 allows.
    exp_infl_obs = _to_dated(await fred.fetch_umich_5y_inflation_us(start, observation_date))
    latest_forecast = _latest_on_or_before(exp_infl_obs, observation_date)
    inflation_forecast_2y_pct = (
        latest_forecast.value / 100.0 if latest_forecast is not None else None
    )

    return M2TaylorGapsInputs(
        country_code="US",
        observation_date=observation_date,
        policy_rate_pct=policy_rate_pct,
        inflation_yoy_pct=inflation_yoy_pct,
        inflation_target_pct=inflation_target_pct,
        output_gap_pct=output_gap_pct,
        r_star_pct=r_star_pct,
        prev_policy_rate_pct=prev_policy_rate_pct,
        inflation_forecast_2y_pct=inflation_forecast_2y_pct,
        lookback_years=history_years,
        source_connector=("fred", "cbo"),
        upstream_flags=("INFLATION_FORECAST_PROXY_UMICH",),
    )


def _us_policy_rate_prev_month(
    upper: Sequence[_DatedValue], lower: Sequence[_DatedValue], anchor: date
) -> float | None:
    prior = anchor - timedelta(days=30)
    u = _latest_on_or_before(upper, prior)
    loader = _latest_on_or_before(lower, prior)
    if u is None or loader is None:
        return None
    return (u.value + loader.value) / 2.0 / 100.0


# ---------------------------------------------------------------------------
# M4 — US
# ---------------------------------------------------------------------------


async def build_m4_us_inputs(
    fred: FredConnector,
    observation_date: date,
    *,
    history_years: int = M4_DEFAULT_LOOKBACK_YEARS,
) -> M4FciInputs:
    """Assemble M4 US inputs from FRED (direct NFCI path)."""
    start = observation_date - timedelta(days=history_years * 366)

    nfci = _to_dated(await fred.fetch_nfci_us(start, observation_date))
    latest = _latest_on_or_before(nfci, observation_date)
    if latest is None:
        msg = "No NFCI observation at or before anchor"
        raise ValueError(msg)
    nfci_level = latest.value
    prior = _latest_on_or_before(nfci, observation_date - timedelta(days=365))
    fci_level_12m_ago = prior.value if prior is not None else None

    nfci_history = _resample_monthly(nfci, observation_date, n_months=history_years * 12)

    return M4FciInputs(
        country_code="US",
        observation_date=observation_date,
        nfci_level=nfci_level,
        nfci_history=tuple(nfci_history),
        fci_level_12m_ago=fci_level_12m_ago,
        lookback_years=history_years,
        source_connector=("fred",),
    )


# ---------------------------------------------------------------------------
# Orchestration facade
# ---------------------------------------------------------------------------


class MonetaryInputsBuilder:
    """Thin facade that holds connectors + exposes typed build methods.

    Consumers (pipelines / orchestrators) can pass a single instance
    instead of plumbing three connectors through every call site.
    """

    def __init__(
        self,
        *,
        fred: FredConnector,
        cbo: CboConnector,
        ecb_sdw: EcbSdwConnector,
        boc: BoCConnector | None = None,
        boe: BoEDatabaseConnector | None = None,
        boj: BoJConnector | None = None,
        rba: RBAConnector | None = None,
        rbnz: RBNZConnector | None = None,
        riksbank: RiksbankConnector | None = None,
        snb: SNBConnector | None = None,
        norgesbank: NorgesBankConnector | None = None,
        nationalbanken: NationalbankenConnector | None = None,
        te: TEConnector | None = None,
        oecd_eo: OECDEOConnector | None = None,
    ) -> None:
        self.fred = fred
        self.cbo = cbo
        self.ecb_sdw = ecb_sdw
        self.boc = boc
        self.boe = boe
        self.boj = boj
        self.rba = rba
        self.rbnz = rbnz
        self.riksbank = riksbank
        self.snb = snb
        self.norgesbank = norgesbank
        self.nationalbanken = nationalbanken
        self.te = te
        self.oecd_eo = oecd_eo

    async def build_m1_inputs(  # noqa: PLR0911 — dispatch table; flat returns are the clearest form
        self, country: str, observation_date: date, **kwargs: object
    ) -> M1EffectiveRatesInputs:
        if country == "US":
            return await build_m1_us_inputs(self.fred, observation_date, **kwargs)  # type: ignore[arg-type]
        if country == "EA":
            return await build_m1_ea_inputs(self.ecb_sdw, observation_date, **kwargs)  # type: ignore[arg-type]
        if country in ("GB", "UK"):
            # ADR-0007: "GB" canonical; "UK" alias silently normalised at
            # dispatch. CLI entry (`daily_monetary_indices._warn_if_deprecated_alias`)
            # emits the operator-facing deprecation warning; re-warning
            # here would double-log and obscure the trace.
            return await build_m1_gb_inputs(
                self.fred,
                observation_date,
                te=self.te,
                boe=self.boe,
                **kwargs,  # type: ignore[arg-type]
            )
        if country == "JP":
            return await build_m1_jp_inputs(
                self.fred,
                observation_date,
                te=self.te,
                boj=self.boj,
                **kwargs,  # type: ignore[arg-type]
            )
        if country == "CA":
            return await build_m1_ca_inputs(
                self.fred,
                observation_date,
                te=self.te,
                boc=self.boc,
                **kwargs,  # type: ignore[arg-type]
            )
        if country == "AU":
            return await build_m1_au_inputs(
                self.fred,
                observation_date,
                te=self.te,
                rba=self.rba,
                **kwargs,  # type: ignore[arg-type]
            )
        if country == "NZ":
            return await build_m1_nz_inputs(
                self.fred,
                observation_date,
                te=self.te,
                rbnz=self.rbnz,
                **kwargs,  # type: ignore[arg-type]
            )
        if country == "CH":
            return await build_m1_ch_inputs(
                self.fred,
                observation_date,
                te=self.te,
                snb=self.snb,
                **kwargs,  # type: ignore[arg-type]
            )
        if country == "NO":
            return await build_m1_no_inputs(
                self.fred,
                observation_date,
                te=self.te,
                norgesbank=self.norgesbank,
                **kwargs,  # type: ignore[arg-type]
            )
        if country == "SE":
            return await build_m1_se_inputs(
                self.fred,
                observation_date,
                te=self.te,
                riksbank=self.riksbank,
                **kwargs,  # type: ignore[arg-type]
            )
        if country == "DK":
            return await build_m1_dk_inputs(
                self.fred,
                observation_date,
                te=self.te,
                nationalbanken=self.nationalbanken,
                **kwargs,  # type: ignore[arg-type]
            )
        msg = f"M1 builder not implemented for country={country!r} (Week 7+)"
        raise NotImplementedError(msg)

    async def build_m2_inputs(  # noqa: PLR0911 — dispatch table; flat returns are the clearest form
        self, country: str, observation_date: date, **kwargs: object
    ) -> M2TaylorGapsInputs:
        if country == "US":
            # US keeps CBO GDPPOT (quarterly) as canonical — OECD EO USA is
            # annual and strictly coarser. No regression path: US builder
            # signature unchanged Sprint C.
            return await build_m2_us_inputs(self.fred, self.cbo, observation_date, **kwargs)  # type: ignore[arg-type]
        if country == "EA":
            # Sprint L wiring — EA aggregate M2 Taylor compute via ECB DFR
            # (policy rate) + TE EA HICP (``ECCPEMUY``) + TE EA inflation
            # forecast + OECD EO EA17 output gap. Per CAL-M2-EA-AGGREGATE.
            return await build_m2_ea_inputs(
                self.ecb_sdw,
                observation_date,
                te=self.te,
                oecd_eo=self.oecd_eo,
                **kwargs,  # type: ignore[arg-type]
            )
        if country == "JP":
            return await build_m2_jp_inputs(
                self.fred,
                observation_date,
                te=self.te,
                boj=self.boj,
                oecd_eo=self.oecd_eo,
                **kwargs,  # type: ignore[arg-type]
            )
        if country == "CA":
            return await build_m2_ca_inputs(
                self.fred,
                observation_date,
                te=self.te,
                boc=self.boc,
                oecd_eo=self.oecd_eo,
                **kwargs,  # type: ignore[arg-type]
            )
        if country == "AU":
            return await build_m2_au_inputs(
                self.fred,
                observation_date,
                te=self.te,
                rba=self.rba,
                oecd_eo=self.oecd_eo,
                **kwargs,  # type: ignore[arg-type]
            )
        if country == "NZ":
            return await build_m2_nz_inputs(
                self.fred,
                observation_date,
                te=self.te,
                rbnz=self.rbnz,
                oecd_eo=self.oecd_eo,
                **kwargs,  # type: ignore[arg-type]
            )
        if country == "CH":
            return await build_m2_ch_inputs(
                self.fred,
                observation_date,
                te=self.te,
                snb=self.snb,
                oecd_eo=self.oecd_eo,
                **kwargs,  # type: ignore[arg-type]
            )
        if country == "NO":
            return await build_m2_no_inputs(
                self.fred,
                observation_date,
                te=self.te,
                norgesbank=self.norgesbank,
                oecd_eo=self.oecd_eo,
                **kwargs,  # type: ignore[arg-type]
            )
        if country == "SE":
            return await build_m2_se_inputs(
                self.fred,
                observation_date,
                te=self.te,
                riksbank=self.riksbank,
                oecd_eo=self.oecd_eo,
                **kwargs,  # type: ignore[arg-type]
            )
        if country == "DK":
            return await build_m2_dk_inputs(
                self.fred,
                observation_date,
                te=self.te,
                nationalbanken=self.nationalbanken,
                oecd_eo=self.oecd_eo,
                **kwargs,  # type: ignore[arg-type]
            )
        if country in ("GB", "UK"):
            return await build_m2_gb_inputs(
                self.fred,
                observation_date,
                te=self.te,
                boe=self.boe,
                oecd_eo=self.oecd_eo,
                **kwargs,  # type: ignore[arg-type]
            )
        # Per-country EA members (DE/FR/IT/ES/NL/PT) remain unimplemented
        # at M2 post-Sprint-L scope. Sprint F prioritised the non-EA T1
        # countries where the Taylor compute has a well-defined
        # per-country policy-rate instrument; Sprint L closed EA
        # aggregate on top of the shared ECB DFR. For per-country EA
        # members the policy rate is still the ECB DFR (shared, not
        # per-country) so a per-country Taylor rule is academically
        # ambiguous without a country-specific reaction-function spec.
        # Tracked under CAL-M2-EA-PER-COUNTRY for Phase 2+ work.
        msg = (
            f"M2 builder not implemented for country={country!r}. "
            f"Sprint F + Sprint L (Week 10 Day 2) ship US + EA + 9 "
            f"non-EA T1 countries (CA/AU/NZ/CH/SE/NO/DK + GB/JP) live; "
            f"per-country EA members deferred to Phase 2+ (see "
            f"CAL-M2-EA-PER-COUNTRY)."
        )
        raise NotImplementedError(msg)

    async def build_m4_inputs(  # noqa: PLR0911 — dispatch table; flat returns are the clearest form
        self, country: str, observation_date: date, **kwargs: object
    ) -> M4FciInputs:
        if country == "US":
            return await build_m4_us_inputs(self.fred, observation_date, **kwargs)  # type: ignore[arg-type]
        if country == "JP":
            return await build_m4_jp_inputs(
                self.fred,
                observation_date,
                te=self.te,
                **kwargs,  # type: ignore[arg-type]
            )
        if country == "CA":
            return await build_m4_ca_inputs(
                self.fred,
                observation_date,
                te=self.te,
                boc=self.boc,
                **kwargs,  # type: ignore[arg-type]
            )
        if country == "AU":
            return await build_m4_au_inputs(
                self.fred,
                observation_date,
                te=self.te,
                rba=self.rba,
                **kwargs,  # type: ignore[arg-type]
            )
        if country == "NZ":
            return await build_m4_nz_inputs(
                self.fred,
                observation_date,
                te=self.te,
                rbnz=self.rbnz,
                **kwargs,  # type: ignore[arg-type]
            )
        if country == "CH":
            return await build_m4_ch_inputs(
                self.fred,
                observation_date,
                te=self.te,
                snb=self.snb,
                **kwargs,  # type: ignore[arg-type]
            )
        if country == "NO":
            return await build_m4_no_inputs(
                self.fred,
                observation_date,
                te=self.te,
                norgesbank=self.norgesbank,
                **kwargs,  # type: ignore[arg-type]
            )
        if country == "SE":
            return await build_m4_se_inputs(
                self.fred,
                observation_date,
                te=self.te,
                riksbank=self.riksbank,
                **kwargs,  # type: ignore[arg-type]
            )
        if country == "DK":
            return await build_m4_dk_inputs(
                self.fred,
                observation_date,
                te=self.te,
                nationalbanken=self.nationalbanken,
                **kwargs,  # type: ignore[arg-type]
            )
        msg = f"M4 builder not implemented for country={country!r} (Week 7+ custom-FCI EA)"
        raise NotImplementedError(msg)


# Sanity: keep ZLB threshold import-accessible for callers that want to
# early-flag SHADOW_RATE_UNAVAILABLE.
_ = ZLB_THRESHOLD_PCT


# ---------------------------------------------------------------------------
# Deprecated aliases (ADR-0007) — removal planned Week 10 Day 1
# ---------------------------------------------------------------------------


async def build_m1_uk_inputs(
    fred: FredConnector,
    observation_date: date,
    *,
    te: TEConnector | None = None,
    boe: BoEDatabaseConnector | None = None,
    history_years: int = M1_DEFAULT_LOOKBACK_YEARS,
) -> M1EffectiveRatesInputs:
    """Deprecated alias for :func:`build_m1_gb_inputs` (ADR-0007).

    Preserved so external callers that still import the UK-named
    function keep functioning during the transition window. Emits a
    structlog ``builders.build_m1_uk_inputs.deprecated`` warning on
    every invocation. Removal planned Week 10 Day 1.
    """
    log.warning(
        "builders.build_m1_uk_inputs.deprecated",
        replacement="build_m1_gb_inputs",
        adr="ADR-0007",
        removal="week10-day1",
    )
    return await build_m1_gb_inputs(
        fred,
        observation_date,
        te=te,
        boe=boe,
        history_years=history_years,
    )
