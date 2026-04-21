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

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from sonar.connectors.boe_database import BoEDatabaseConnector
    from sonar.connectors.cbo import CboConnector
    from sonar.connectors.ecb_sdw import EcbSdwConnector
    from sonar.connectors.fred import FredConnector


__all__ = [
    "MonetaryInputsBuilder",
    "build_m1_ea_inputs",
    "build_m1_uk_inputs",
    "build_m1_us_inputs",
    "build_m2_us_inputs",
    "build_m4_us_inputs",
]

# UK OECD-mirror series on FRED — monthly, reliable backfill for BoE IADB
# which is currently gated by Akamai anti-bot (Sprint I empirical probe).
FRED_UK_BANK_RATE_SERIES: str = "IRSTCI01GBM156N"
FRED_UK_GILT_10Y_SERIES: str = "IRLTLT01GBM156N"


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
# M1 — UK (Sprint I CAL — BoE → TE → FRED cascade)
# ---------------------------------------------------------------------------


async def _uk_bank_rate_cascade(
    start: date,
    end: date,
    *,
    boe: BoEDatabaseConnector | None,
    fred: FredConnector,
) -> tuple[list[_DatedValue], tuple[str, ...]]:
    """Fetch UK Bank Rate history with BoE → FRED fallback.

    Returns the series + any `upstream_flags` describing which source
    answered. BoE is preferred (daily, authoritative); FRED's
    ``IRSTCI01GBM156N`` OECD mirror is monthly but reliably reachable
    from any IP (BoE IADB is currently behind Akamai anti-bot — see
    :mod:`sonar.connectors.boe_database`).
    """
    flags: list[str] = []
    if boe is not None:
        from sonar.overlays.exceptions import DataUnavailableError  # noqa: PLC0415

        try:
            boe_obs = await boe.fetch_bank_rate(start, end)
        except DataUnavailableError:
            flags.append("UK_BANK_RATE_BOE_FALLBACK")
        else:
            if boe_obs:
                return (
                    [_DatedValue(o.observation_date, o.yield_bps / 100.0) for o in boe_obs],
                    (),
                )
            flags.append("UK_BANK_RATE_BOE_EMPTY")
    fred_obs = await fred.fetch_series(FRED_UK_BANK_RATE_SERIES, start, end)
    if not fred_obs:
        msg = "UK Bank Rate: BoE + FRED both returned empty"
        raise ValueError(msg)
    return (
        [_DatedValue(o.observation_date, o.yield_bps / 100.0) for o in fred_obs],
        tuple(flags),
    )


async def build_m1_uk_inputs(
    fred: FredConnector,
    observation_date: date,
    *,
    boe: BoEDatabaseConnector | None = None,
    history_years: int = M1_DEFAULT_LOOKBACK_YEARS,
) -> M1EffectiveRatesInputs:
    """Assemble M1 UK inputs via BoE → FRED cascade + YAML r*/target.

    BoE IADB is preferred when reachable. When the CSV endpoint returns
    the Akamai anti-bot ErrorPage (or ``boe`` is omitted), the builder
    falls back to FRED's OECD-mirror series.

    UK-specific degradations (Phase 1):

    - ``expected_inflation_5y_pct`` defaults to the BoE CPI target (2 %)
      because no BoE breakeven-inflation mirror exists at this scope;
      emits ``EXPECTED_INFLATION_CB_TARGET`` flag.
    - ``balance_sheet_pct_gdp_*`` zero-seeded with ``UK_BS_GDP_PROXY_ZERO``
      flag — UK balance-sheet ratios require the BoE weekly bank-return
      aggregate which is not FRED-mirrored. Lands when IADB becomes
      reachable or when we wire an ONS-sourced GDP+APF composite.
    """
    start = observation_date - timedelta(days=history_years * 366)

    policy_hist, cascade_flags = await _uk_bank_rate_cascade(
        start, observation_date, boe=boe, fred=fred
    )
    latest_policy = _latest_on_or_before(policy_hist, observation_date)
    if latest_policy is None:
        msg = "UK Bank Rate: no observation at or before anchor"
        raise ValueError(msg)
    policy_rate_pct = latest_policy.value / 100.0

    r_star_pct, _is_proxy = resolve_r_star("UK")  # is_proxy always True for UK
    expected_inflation_5y_pct = 0.02  # BoE CPI target; proxy

    policy_monthly_pct = _resample_monthly(
        policy_hist, observation_date, n_months=history_years * 12
    )
    real_shadow_hist = [p / 100.0 - expected_inflation_5y_pct for p in policy_monthly_pct]
    stance_hist = [r - r_star_pct for r in real_shadow_hist]

    flags: list[str] = list(cascade_flags)
    flags.append("R_STAR_PROXY")
    flags.append("EXPECTED_INFLATION_CB_TARGET")
    flags.append("UK_BS_GDP_PROXY_ZERO")

    source: tuple[str, ...] = ("boe", "fred") if boe is not None else ("fred",)
    return M1EffectiveRatesInputs(
        country_code="UK",
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
        source_connector=source,
        upstream_flags=tuple(flags),
    )


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
        boe: BoEDatabaseConnector | None = None,
    ) -> None:
        self.fred = fred
        self.cbo = cbo
        self.ecb_sdw = ecb_sdw
        self.boe = boe

    async def build_m1_inputs(
        self, country: str, observation_date: date, **kwargs: object
    ) -> M1EffectiveRatesInputs:
        if country == "US":
            return await build_m1_us_inputs(self.fred, observation_date, **kwargs)  # type: ignore[arg-type]
        if country == "EA":
            return await build_m1_ea_inputs(self.ecb_sdw, observation_date, **kwargs)  # type: ignore[arg-type]
        if country == "UK":
            return await build_m1_uk_inputs(
                self.fred,
                observation_date,
                boe=self.boe,
                **kwargs,  # type: ignore[arg-type]
            )
        msg = f"M1 builder not implemented for country={country!r} (Week 7+)"
        raise NotImplementedError(msg)

    async def build_m2_inputs(
        self, country: str, observation_date: date, **kwargs: object
    ) -> M2TaylorGapsInputs:
        if country == "US":
            return await build_m2_us_inputs(self.fred, self.cbo, observation_date, **kwargs)  # type: ignore[arg-type]
        msg = f"M2 builder not implemented for country={country!r} (Week 7+ OECD/AMECO gap)"
        raise NotImplementedError(msg)

    async def build_m4_inputs(
        self, country: str, observation_date: date, **kwargs: object
    ) -> M4FciInputs:
        if country == "US":
            return await build_m4_us_inputs(self.fred, observation_date, **kwargs)  # type: ignore[arg-type]
        msg = f"M4 builder not implemented for country={country!r} (Week 7+ custom-FCI EA)"
        raise NotImplementedError(msg)


# Sanity: keep ZLB threshold import-accessible for callers that want to
# early-flag SHADOW_RATE_UNAVAILABLE.
_ = ZLB_THRESHOLD_PCT
