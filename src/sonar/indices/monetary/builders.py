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
    from sonar.connectors.rba import RBAConnector
    from sonar.connectors.rbnz import RBNZConnector
    from sonar.connectors.snb import SNBConnector
    from sonar.connectors.te import TEConnector


log = structlog.get_logger()


__all__ = [
    "MonetaryInputsBuilder",
    "build_m1_au_inputs",
    "build_m1_ca_inputs",
    "build_m1_ch_inputs",
    "build_m1_ea_inputs",
    "build_m1_gb_inputs",
    "build_m1_jp_inputs",
    "build_m1_nz_inputs",
    "build_m1_uk_inputs",
    "build_m1_us_inputs",
    "build_m2_au_inputs",
    "build_m2_ca_inputs",
    "build_m2_ch_inputs",
    "build_m2_jp_inputs",
    "build_m2_nz_inputs",
    "build_m2_us_inputs",
    "build_m4_au_inputs",
    "build_m4_ca_inputs",
    "build_m4_ch_inputs",
    "build_m4_jp_inputs",
    "build_m4_nz_inputs",
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
    fred: FredConnector,  # noqa: ARG001 - wired for future OECD JP gap path
    observation_date: date,  # noqa: ARG001
    *,
    te: TEConnector | None = None,  # noqa: ARG001
    boj: BoJConnector | None = None,  # noqa: ARG001
    history_years: int = M2_DEFAULT_LOOKBACK_YEARS,  # noqa: ARG001
) -> M2TaylorGapsInputs:
    """Assemble M2 JP inputs (scaffold — raises until JP gap source lands).

    Sprint L ships the dispatch wire-ready so the pipeline can route
    ``--country JP`` without crashing. The JP Taylor-gap inputs require
    three sources that are not yet connected at this scope:

    - **JP CPI YoY**: no ``fetch_jp_cpi_yoy`` wrapper on either TE or
      FRED within Sprint L scope (brief §1 defers CPI/unemployment to
      generic TE ``fetch_indicator`` probes).
    - **Output gap**: Japan has no CBO equivalent; OECD EO + BoJ Tankan
      are both outside L0 coverage today (CAL-JP-OUTPUT-GAP).
    - **Inflation forecast**: BoJ does not publish a UMich-analog 5Y
      breakeven series, and the TE ``inflation expectations`` feed lags
      at quarterly cadence (CAL-JP-M2-INFL-FORECAST).

    Once any of those sources lands, this function resolves the cascade
    like :func:`build_m2_us_inputs` does for the CBO output-gap path —
    mirroring the Sprint I-patch cascade shape so the pattern stays
    consistent across Tier-1 countries. Until then,
    :class:`InsufficientDataError` keeps the pipeline clean (caught by
    :func:`daily_monetary_indices.build_live_monetary_inputs` which logs
    a structured ``monetary_pipeline.builder_skipped`` warning rather
    than crashing).
    """
    msg = (
        "M2 JP builder scaffold shipped Sprint L but requires CPI YoY, "
        "output-gap, and inflation-forecast JP connectors that are not "
        "yet wired (see CAL-JP-OUTPUT-GAP, CAL-JP-M2-CPI, "
        "CAL-JP-M2-INFL-FORECAST). Raises so the pipeline skips M2 JP "
        "cleanly."
    )
    raise InsufficientDataError(msg)


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
    fred: FredConnector,  # noqa: ARG001 - wired for future OECD CA gap path
    observation_date: date,  # noqa: ARG001
    *,
    te: TEConnector | None = None,  # noqa: ARG001
    boc: BoCConnector | None = None,  # noqa: ARG001
    history_years: int = M2_DEFAULT_LOOKBACK_YEARS,  # noqa: ARG001
) -> M2TaylorGapsInputs:
    """Assemble M2 CA inputs (scaffold — raises until CA gap source lands).

    Sprint S ships the dispatch wire-ready so the pipeline can route
    ``--country CA`` without crashing. The CA Taylor-gap inputs require
    three sources that are not yet connected at this scope:

    - **CA CPI YoY**: no ``fetch_ca_cpi_yoy`` wrapper on either TE or
      FRED within Sprint S scope (CAL-134).
    - **Output gap**: Canada-specific — the BoC itself publishes a
      quarterly output gap via Valet series (``DMREST_SEGP_GAP``
      candidate) but the wiring is not Sprint S scope (CAL-130).
      OECD EO CA also maps through the same connector family.
    - **Inflation forecast**: BoC publishes quarterly Monetary Policy
      Report forecasts — Valet-hosted but unwired Sprint S (CAL-135).

    Once any of those sources lands, this function resolves the
    cascade like :func:`build_m2_us_inputs` does for the CBO output-
    gap path. Until then, :class:`InsufficientDataError` keeps the
    pipeline clean (caught by
    :func:`daily_monetary_indices.build_live_monetary_inputs` which
    logs a structured ``monetary_pipeline.builder_skipped`` warning
    rather than crashing).
    """
    msg = (
        "M2 CA builder scaffold shipped Sprint S but requires CPI YoY, "
        "output-gap, and inflation-forecast CA connectors that are not "
        "yet wired (see CAL-130 / CAL-134 / CAL-135). Raises so the "
        "pipeline skips M2 CA cleanly."
    )
    raise InsufficientDataError(msg)


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
    fred: FredConnector,  # noqa: ARG001 - wired for future OECD AU gap path
    observation_date: date,  # noqa: ARG001
    *,
    te: TEConnector | None = None,  # noqa: ARG001
    rba: RBAConnector | None = None,  # noqa: ARG001
    history_years: int = M2_DEFAULT_LOOKBACK_YEARS,  # noqa: ARG001
) -> M2TaylorGapsInputs:
    """Assemble M2 AU inputs (scaffold — raises until AU gap source lands).

    Sprint T ships the dispatch wire-ready so the pipeline can route
    ``--country AU`` without crashing. The AU Taylor-gap inputs require
    three sources that are not yet connected at this scope:

    - **AU CPI YoY**: no ``fetch_au_cpi_yoy`` wrapper on either TE or
      FRED within Sprint T scope (CAL-AU-CPI).
    - **Output gap**: Australia-specific — the RBA publishes a
      quarterly output gap via SMP technical notes but no scriptable
      endpoint exists at Sprint T scope (CAL-AU-GAP). OECD EO AU also
      maps through the same connector family.
    - **Inflation forecast**: RBA publishes quarterly SMP forecasts —
      HTML-hosted but unwired Sprint T (CAL-AU-INFL-FORECAST).

    Once any of those sources lands, this function resolves the
    cascade like :func:`build_m2_us_inputs` does for the CBO output-
    gap path. Until then, :class:`InsufficientDataError` keeps the
    pipeline clean (caught by
    :func:`daily_monetary_indices.build_live_monetary_inputs` which
    logs a structured ``monetary_pipeline.builder_skipped`` warning
    rather than crashing).
    """
    msg = (
        "M2 AU builder scaffold shipped Sprint T but requires CPI YoY, "
        "output-gap, and inflation-forecast AU connectors that are not "
        "yet wired (see CAL-AU-CPI / CAL-AU-GAP / CAL-AU-INFL-FORECAST). "
        "Raises so the pipeline skips M2 AU cleanly."
    )
    raise InsufficientDataError(msg)


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
    fred: FredConnector,  # noqa: ARG001 - wired for future OECD NZ gap path
    observation_date: date,  # noqa: ARG001
    *,
    te: TEConnector | None = None,  # noqa: ARG001
    rbnz: RBNZConnector | None = None,  # noqa: ARG001
    history_years: int = M2_DEFAULT_LOOKBACK_YEARS,  # noqa: ARG001
) -> M2TaylorGapsInputs:
    """Assemble M2 NZ inputs (scaffold — raises until NZ gap source lands).

    Sprint U-NZ ships the dispatch wire-ready so the pipeline can
    route ``--country NZ`` without crashing. The NZ Taylor-gap inputs
    require three sources that are not yet connected at this scope:

    - **NZ CPI YoY**: no ``fetch_nz_cpi_yoy`` wrapper on either TE or
      FRED within Sprint U-NZ scope (CAL-NZ-CPI).
    - **Output gap**: New Zealand-specific — Stats NZ + the Treasury
      (HYEFU/BEFU) publish quarterly output-gap estimates but no
      scriptable endpoint exists at Sprint U-NZ scope
      (CAL-NZ-M2-OUTPUT-GAP). OECD EO NZ maps through the same
      connector family.
    - **Inflation forecast**: RBNZ publishes quarterly Monetary Policy
      Statement (MPS) forecasts — HTML / PDF-hosted, unwired Sprint
      U-NZ (CAL-NZ-INFL-FORECAST).

    Once any of those sources lands, this function resolves the
    cascade like :func:`build_m2_us_inputs` does for the CBO output-
    gap path. Until then, :class:`InsufficientDataError` keeps the
    pipeline clean (caught by
    :func:`daily_monetary_indices.build_live_monetary_inputs` which
    logs a structured ``monetary_pipeline.builder_skipped`` warning
    rather than crashing).
    """
    msg = (
        "M2 NZ builder scaffold shipped Sprint U-NZ but requires CPI YoY, "
        "output-gap, and inflation-forecast NZ connectors that are not "
        "yet wired (see CAL-NZ-CPI / CAL-NZ-M2-OUTPUT-GAP / "
        "CAL-NZ-INFL-FORECAST). Raises so the pipeline skips M2 NZ cleanly."
    )
    raise InsufficientDataError(msg)


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
    fred: FredConnector,  # noqa: ARG001 - wired for future OECD CH gap path
    observation_date: date,  # noqa: ARG001
    *,
    te: TEConnector | None = None,  # noqa: ARG001
    snb: SNBConnector | None = None,  # noqa: ARG001
    history_years: int = M2_DEFAULT_LOOKBACK_YEARS,  # noqa: ARG001
) -> M2TaylorGapsInputs:
    """Assemble M2 CH inputs (scaffold — raises until CH sources land).

    Sprint V ships the dispatch wire-ready so the pipeline can route
    ``--country CH`` without crashing. The CH Taylor-gap inputs require
    three sources that are not yet connected at this scope:

    - **CH CPI YoY**: no ``fetch_ch_cpi_yoy`` wrapper on either TE or
      FRED within Sprint V scope (CAL-CH-CPI). SNB publishes CPI on
      the ``cpikern`` cube but the parse path needs its own wrapper.
    - **Output gap**: Switzerland-specific — SECO publishes the
      quarterly KOF-SECO output gap but no scriptable endpoint exists
      at Sprint V scope (CAL-CH-GAP). OECD EO CH also maps through the
      same connector family.
    - **Inflation forecast**: SNB publishes quarterly Monetary Policy
      Assessment forecasts — HTML-hosted but unwired Sprint V
      (CAL-CH-INFL-FORECAST).

    Once any of those sources lands, this function resolves the
    cascade like :func:`build_m2_us_inputs` does for the CBO output-
    gap path. Until then, :class:`InsufficientDataError` keeps the
    pipeline clean (caught by
    :func:`daily_monetary_indices.build_live_monetary_inputs` which
    logs a structured ``monetary_pipeline.builder_skipped`` warning
    rather than crashing).
    """
    msg = (
        "M2 CH builder scaffold shipped Sprint V but requires CPI YoY, "
        "output-gap, and inflation-forecast CH connectors that are not "
        "yet wired (see CAL-CH-CPI / CAL-CH-GAP / CAL-CH-INFL-FORECAST). "
        "Raises so the pipeline skips M2 CH cleanly."
    )
    raise InsufficientDataError(msg)


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
        snb: SNBConnector | None = None,
        te: TEConnector | None = None,
    ) -> None:
        self.fred = fred
        self.cbo = cbo
        self.ecb_sdw = ecb_sdw
        self.boc = boc
        self.boe = boe
        self.boj = boj
        self.rba = rba
        self.rbnz = rbnz
        self.snb = snb
        self.te = te

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
        msg = f"M1 builder not implemented for country={country!r} (Week 7+)"
        raise NotImplementedError(msg)

    async def build_m2_inputs(
        self, country: str, observation_date: date, **kwargs: object
    ) -> M2TaylorGapsInputs:
        if country == "US":
            return await build_m2_us_inputs(self.fred, self.cbo, observation_date, **kwargs)  # type: ignore[arg-type]
        if country == "JP":
            return await build_m2_jp_inputs(
                self.fred,
                observation_date,
                te=self.te,
                boj=self.boj,
                **kwargs,  # type: ignore[arg-type]
            )
        if country == "CA":
            return await build_m2_ca_inputs(
                self.fred,
                observation_date,
                te=self.te,
                boc=self.boc,
                **kwargs,  # type: ignore[arg-type]
            )
        if country == "AU":
            return await build_m2_au_inputs(
                self.fred,
                observation_date,
                te=self.te,
                rba=self.rba,
                **kwargs,  # type: ignore[arg-type]
            )
        if country == "NZ":
            return await build_m2_nz_inputs(
                self.fred,
                observation_date,
                te=self.te,
                rbnz=self.rbnz,
                **kwargs,  # type: ignore[arg-type]
            )
        if country == "CH":
            return await build_m2_ch_inputs(
                self.fred,
                observation_date,
                te=self.te,
                snb=self.snb,
                **kwargs,  # type: ignore[arg-type]
            )
        msg = f"M2 builder not implemented for country={country!r} (Week 7+ OECD/AMECO gap)"
        raise NotImplementedError(msg)

    async def build_m4_inputs(
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
