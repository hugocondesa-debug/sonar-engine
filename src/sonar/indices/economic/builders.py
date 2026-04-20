"""Builders that turn live connector output into E1/E3/E4 inputs.

Per Week 5 Sprint 2a brief §Commit 4: each builder takes a
``(country, observation_date)`` plus live :class:`EurostatConnector` and
:class:`FredConnector` instances and returns the matching
``E{1,3,4}Inputs`` dataclass fully populated with ``current`` + history
fields. Missing components resolve to ``None`` / empty history so the
downstream compute functions can emit the spec §6 degradation flags.

US → FRED is the primary path; EA codes (DE, PT, IT, ES, FR, NL, EA*) →
Eurostat primary. Globally-defined components (e.g. VIX) come from FRED
regardless of country.

The builders perform no z-score calculations — they only pull raw data
and surface the latest value + history to the compute layer. History
slicing respects the requested ``lookback_years`` window so callers can
control series length without each helper having to re-derive the
window.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

import structlog

from sonar.indices.economic.e1_activity import (
    DEFAULT_LOOKBACK_YEARS as E1_DEFAULT_LOOKBACK_YEARS,
    E1ActivityInputs,
)
from sonar.indices.economic.e3_labor import (
    DEFAULT_LOOKBACK_YEARS as E3_DEFAULT_LOOKBACK_YEARS,
    E3LaborInputs,
)
from sonar.indices.economic.e4_sentiment import (
    DEFAULT_LOOKBACK_YEARS as E4_DEFAULT_LOOKBACK_YEARS,
    E4SentimentInputs,
)
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from sonar.connectors.eurostat import EurostatConnector
    from sonar.connectors.fred import FredConnector, FredEconomicObservation

log = structlog.get_logger()

US_COUNTRY = "US"
EA_COUNTRIES: frozenset[str] = frozenset({"DE", "PT", "IT", "ES", "FR", "NL", "EA"})


def _window_start(end: date, years: int) -> date:
    return end - timedelta(days=years * 366 + 60)


async def _try_fetch_fred(
    label: str,
    coro: Awaitable[list[FredEconomicObservation]],
) -> list[float] | None:
    """Run a FRED helper coroutine; on DataUnavailableError return None."""
    try:
        obs = await coro
    except DataUnavailableError as e:
        log.info("builder.fred.unavailable", component=label, reason=str(e))
        return None
    return [o.value for o in obs]


def _split_current_history(values: list[float] | None) -> tuple[float | None, list[float]]:
    if not values:
        return None, []
    return values[-1], list(values[:-1])


# ---------------------------------------------------------------------------
# E1 Activity builder
# ---------------------------------------------------------------------------


async def build_e1_inputs(
    country: str,
    observation_date: date,
    *,
    fred: FredConnector,
    eurostat: EurostatConnector,
    lookback_years: int = E1_DEFAULT_LOOKBACK_YEARS,
) -> E1ActivityInputs:
    """Assemble E1 inputs for ``(country, date)`` from live connectors."""
    country = country.upper()
    start = _window_start(observation_date, lookback_years)
    flags: list[str] = []
    sources: list[str] = []

    if country == US_COUNTRY:
        sources.append("FRED")
        gdp = await _try_fetch_fred(
            "gdp",
            fred.fetch_gdp_real_yoy_us(start, observation_date),
        )
        ip = await _try_fetch_fred(
            "industrial_production",
            fred.fetch_industrial_production_yoy_us(start, observation_date),
        )
        emp = await _try_fetch_fred(
            "employment",
            fred.fetch_nonfarm_payrolls_yoy_us(start, observation_date),
        )
        retail = await _try_fetch_fred(
            "retail_sales",
            fred.fetch_retail_sales_real_yoy_us(start, observation_date),
        )
        personal_income = await _try_fetch_fred(
            "personal_income",
            fred.fetch_personal_income_real_yoy_us(start, observation_date),
        )
        pmi_vals = await _try_fetch_fred(
            "pmi",
            fred.fetch_ism_mfg_pmi(start, observation_date),
        )
        if pmi_vals is None:
            flags.append("ISM_MFG_UNAVAILABLE")
    elif country in EA_COUNTRIES:
        sources.append("EUROSTAT")
        gdp = [o.value for o in await eurostat.fetch_gdp_real_yoy(country, start, observation_date)]
        ip = [
            o.value
            for o in await eurostat.fetch_industrial_production_yoy(
                country, start, observation_date
            )
        ]
        emp = [
            o.value for o in await eurostat.fetch_employment_yoy(country, start, observation_date)
        ]
        retail = [
            o.value
            for o in await eurostat.fetch_retail_sales_real_yoy(country, start, observation_date)
        ]
        # EA personal-income series has no direct Eurostat equivalent → skip.
        personal_income = None
        flags.append("PERSONAL_INCOME_US_ONLY")
        # PMI (S&P Global) requires a separate scraper → deferred CAL-081.
        pmi_vals = None
        flags.append("PMI_UNAVAILABLE")
    else:
        msg = f"E1 builder does not support country={country!r}"
        raise ValueError(msg)

    gdp_cur, gdp_hist = _split_current_history(gdp)
    ip_cur, ip_hist = _split_current_history(ip)
    emp_cur, emp_hist = _split_current_history(emp)
    retail_cur, retail_hist = _split_current_history(retail)
    pi_cur, pi_hist = _split_current_history(personal_income)
    pmi_cur, pmi_hist = _split_current_history(pmi_vals)

    return E1ActivityInputs(
        country_code=country,
        observation_date=observation_date,
        gdp_yoy=gdp_cur,
        gdp_yoy_history=tuple(gdp_hist),
        employment_yoy=emp_cur,
        employment_yoy_history=tuple(emp_hist),
        industrial_production_yoy=ip_cur,
        industrial_production_yoy_history=tuple(ip_hist),
        pmi_composite=pmi_cur,
        pmi_composite_history=tuple(pmi_hist),
        personal_income_ex_transfers_yoy=pi_cur,
        personal_income_ex_transfers_yoy_history=tuple(pi_hist),
        retail_sales_real_yoy=retail_cur,
        retail_sales_real_yoy_history=tuple(retail_hist),
        lookback_years=lookback_years,
        source_connectors=tuple(sources),
        upstream_flags=tuple(flags),
    )


# ---------------------------------------------------------------------------
# E3 Labor builder
# ---------------------------------------------------------------------------


async def build_e3_inputs(
    country: str,
    observation_date: date,
    *,
    fred: FredConnector,
    eurostat: EurostatConnector,
    lookback_years: int = E3_DEFAULT_LOOKBACK_YEARS,
) -> E3LaborInputs:
    """Assemble E3 inputs; unemployment is mandatory per spec §2."""
    country = country.upper()
    start = _window_start(observation_date, lookback_years)
    flags: list[str] = []
    sources: list[str] = []

    if country == US_COUNTRY:
        sources.append("FRED")
        ur_vals = await _try_fetch_fred(
            "unemployment_rate",
            fred.fetch_unemployment_rate_us(start, observation_date),
        )
        emratio_vals = await _try_fetch_fred(
            "emp_pop_ratio",
            fred.fetch_emp_pop_ratio_us(start, observation_date),
        )
        lfpr_vals = await _try_fetch_fred(
            "prime_age_lfpr",
            fred.fetch_prime_age_lfpr_us(start, observation_date),
        )
        eci_vals = await _try_fetch_fred(
            "eci_wages_yoy",
            fred.fetch_eci_wages_yoy_us(start, observation_date),
        )
        openings_vals = await _try_fetch_fred(
            "openings",
            fred.fetch_jolts_openings_us(start, observation_date),
        )
        claims_vals = await _try_fetch_fred(
            "initial_claims_4wma",
            fred.fetch_initial_claims_4wma_us(start, observation_date),
        )
        temp_vals = await _try_fetch_fred(
            "temp_help_yoy",
            fred.fetch_temp_help_yoy_us(start, observation_date),
        )
        quits_vals = await _try_fetch_fred(
            "quits",
            fred.fetch_quits_us(start, observation_date),
        )
        atlanta_vals: list[float] | None = None
        flags.append("ATLANTA_FED_US_ONLY")
    elif country in EA_COUNTRIES:
        sources.append("EUROSTAT")
        ur_obs = await eurostat.fetch_unemployment_rate(country, start, observation_date)
        ur_vals = [o.value for o in ur_obs]
        # Rest of the components are predominantly US-only series.
        emratio_vals = None
        lfpr_vals = None
        eci_vals = None
        openings_vals = None
        claims_vals = None
        temp_vals = None
        quits_vals = None
        atlanta_vals = None
        for token in (
            "JOLTS_US_ONLY",
            "CLAIMS_US_ONLY",
            "ATLANTA_FED_US_ONLY",
            "TEMP_HELPS_US_ONLY",
            "ECI_US_ONLY",
        ):
            flags.append(token)
    else:
        msg = f"E3 builder does not support country={country!r}"
        raise ValueError(msg)

    if not ur_vals:
        err = f"E3 requires unemployment_rate for {country}; none returned"
        raise DataUnavailableError(err)

    # Derived components: 12m change (UR) + 12m z (EM ratio) + 12m change (LFPR).
    ur_12m_change = _twelve_month_change(ur_vals)
    emratio_12m_z = None
    if emratio_vals and len(emratio_vals) >= 13:
        emratio_12m_z = emratio_vals[-1] - emratio_vals[-13]
    lfpr_12m_change = _twelve_month_change(lfpr_vals)

    # Openings/Unemployed ratio = JOLTS openings / UR-implied unemployed.
    openings_unemployed_ratio = None
    openings_hist: list[float] = []
    if openings_vals and ur_vals:
        openings_unemployed_ratio = openings_vals[-1] / max(ur_vals[-1], 1e-9)
        openings_hist = [o / max(u, 1e-9) for o, u in zip(openings_vals, ur_vals, strict=False)]

    quits_rate = None
    if quits_vals:
        quits_rate = quits_vals[-1]

    return E3LaborInputs(
        country_code=country,
        observation_date=observation_date,
        unemployment_rate=ur_vals[-1],
        unemployment_rate_history=tuple(ur_vals),
        unemployment_rate_12m_change=ur_12m_change,
        employment_population_ratio_12m_z=emratio_12m_z,
        employment_population_ratio_12m_z_history=tuple(emratio_vals or ()),
        prime_age_lfpr_12m_change=lfpr_12m_change,
        prime_age_lfpr_12m_change_history=tuple(lfpr_vals or ()),
        eci_yoy_growth=(eci_vals[-1] if eci_vals else None),
        eci_yoy_growth_history=tuple(eci_vals[:-1] if eci_vals else ()),
        atlanta_fed_wage_yoy=(atlanta_vals[-1] if atlanta_vals else None),
        atlanta_fed_wage_yoy_history=tuple(atlanta_vals[:-1] if atlanta_vals else ()),
        openings_unemployed_ratio=openings_unemployed_ratio,
        openings_unemployed_ratio_history=tuple(openings_hist[:-1]),
        quits_rate=quits_rate,
        quits_rate_history=tuple(quits_vals[:-1] if quits_vals else ()),
        initial_claims_4wk_avg=(claims_vals[-1] if claims_vals else None),
        initial_claims_4wk_avg_history=tuple(claims_vals[:-1] if claims_vals else ()),
        temp_help_employment_yoy=(temp_vals[-1] if temp_vals else None),
        temp_help_employment_yoy_history=tuple(temp_vals[:-1] if temp_vals else ()),
        lookback_years=lookback_years,
        source_connectors=tuple(sources),
        upstream_flags=tuple(flags),
    )


def _twelve_month_change(values: list[float] | None) -> float | None:
    if not values or len(values) < 13:
        return None
    return values[-1] - values[-13]


# ---------------------------------------------------------------------------
# E4 Sentiment builder
# ---------------------------------------------------------------------------


async def build_e4_inputs(
    country: str,
    observation_date: date,
    *,
    fred: FredConnector,
    eurostat: EurostatConnector,
    lookback_years: int = E4_DEFAULT_LOOKBACK_YEARS,
) -> E4SentimentInputs:
    """Assemble E4 inputs. Spec §6 MIN_COMPONENTS = 6."""
    country = country.upper()
    start = _window_start(observation_date, lookback_years)
    flags: list[str] = []
    sources: list[str] = []

    # VIX is global — fetched from FRED regardless of country.
    sources.append("FRED")
    vix_vals = await _try_fetch_fred("vix", fred.fetch_vix_us(start, observation_date))

    if country == US_COUNTRY:
        umich_vals = await _try_fetch_fred(
            "umich", fred.fetch_umich_sentiment_us(start, observation_date)
        )
        cb_vals = await _try_fetch_fred(
            "cb_confidence",
            fred.fetch_conference_board_confidence_us(start, observation_date),
        )
        umich_5y_vals = await _try_fetch_fred(
            "umich_5y", fred.fetch_umich_5y_inflation_us(start, observation_date)
        )
        ism_mfg_vals = await _try_fetch_fred(
            "ism_mfg", fred.fetch_ism_mfg_pmi(start, observation_date)
        )
        if ism_mfg_vals is None:
            flags.append("ISM_MFG_UNAVAILABLE")
        ism_svc_vals = await _try_fetch_fred(
            "ism_svc", fred.fetch_ism_services_pmi(start, observation_date)
        )
        if ism_svc_vals is None:
            flags.append("ISM_SVC_UNAVAILABLE")
        nfib_vals = await _try_fetch_fred(
            "nfib", fred.fetch_nfib_small_biz_us(start, observation_date)
        )
        if nfib_vals is None:
            flags.append("NFIB_UNAVAILABLE")
        epu_vals = await _try_fetch_fred("epu", fred.fetch_epu_us(start, observation_date))
        sloos_vals = await _try_fetch_fred(
            "sloos", fred.fetch_sloos_tightening_us(start, observation_date)
        )
        esi_vals: list[float] | None = None
        zew_vals: list[float] | None = None
        ifo_vals: list[float] | None = None
        tankan_vals: list[float] | None = None
    elif country in EA_COUNTRIES:
        sources.append("EUROSTAT")
        esi_obs = await eurostat.fetch_economic_sentiment_indicator(
            country, start, observation_date
        )
        esi_vals = [o.value for o in esi_obs]
        cc_obs = await eurostat.fetch_consumer_confidence(country, start, observation_date)
        # EA consumer confidence feeds the cb_confidence slot structurally.
        cb_vals = [o.value for o in cc_obs]
        umich_vals = None
        umich_5y_vals = None
        ism_mfg_vals = None
        ism_svc_vals = None
        nfib_vals = None
        epu_vals = None
        sloos_vals = None
        zew_vals = None
        ifo_vals = None
        tankan_vals = None
        for token in (
            "UMICH_US_ONLY",
            "ISM_MFG_US_ONLY",
            "ISM_SVC_US_ONLY",
            "NFIB_US_ONLY",
            "EPU_US_ONLY",
            "SLOOS_US_ONLY",
            "ZEW_DE_ONLY",
            "IFO_DE_ONLY",
            "TANKAN_JP_ONLY",
        ):
            flags.append(token)
    else:
        msg = f"E4 builder does not support country={country!r}"
        raise ValueError(msg)

    # 12m change transforms (UMich + CB).
    umich_12m = _twelve_month_change(umich_vals)
    cb_12m = _twelve_month_change(cb_vals)

    return E4SentimentInputs(
        country_code=country,
        observation_date=observation_date,
        umich_sentiment_12m_change=umich_12m,
        umich_sentiment_12m_change_history=tuple(umich_vals or ()),
        conference_board_confidence_12m_change=cb_12m,
        conference_board_confidence_12m_change_history=tuple(cb_vals or ()),
        umich_5y_inflation_exp=(umich_5y_vals[-1] if umich_5y_vals else None),
        umich_5y_inflation_exp_history=tuple(umich_5y_vals[:-1] if umich_5y_vals else ()),
        ism_manufacturing=(ism_mfg_vals[-1] if ism_mfg_vals else None),
        ism_manufacturing_history=tuple(ism_mfg_vals[:-1] if ism_mfg_vals else ()),
        ism_services=(ism_svc_vals[-1] if ism_svc_vals else None),
        ism_services_history=tuple(ism_svc_vals[:-1] if ism_svc_vals else ()),
        nfib_small_business=(nfib_vals[-1] if nfib_vals else None),
        nfib_small_business_history=tuple(nfib_vals[:-1] if nfib_vals else ()),
        epu_index=(epu_vals[-1] if epu_vals else None),
        epu_index_history=tuple(epu_vals[:-1] if epu_vals else ()),
        ec_esi=(esi_vals[-1] if esi_vals else None),
        ec_esi_history=tuple(esi_vals[:-1] if esi_vals else ()),
        zew_expectations=(zew_vals[-1] if zew_vals else None),
        zew_expectations_history=tuple(zew_vals[:-1] if zew_vals else ()),
        ifo_business_climate=(ifo_vals[-1] if ifo_vals else None),
        ifo_business_climate_history=tuple(ifo_vals[:-1] if ifo_vals else ()),
        vix_level=(vix_vals[-1] if vix_vals else None),
        vix_level_history=tuple(vix_vals[:-1] if vix_vals else ()),
        tankan_large_mfg=(tankan_vals[-1] if tankan_vals else None),
        tankan_large_mfg_history=tuple(tankan_vals[:-1] if tankan_vals else ()),
        sloos_standards_net_pct=(sloos_vals[-1] if sloos_vals else None),
        sloos_standards_net_pct_history=tuple(sloos_vals[:-1] if sloos_vals else ()),
        lookback_years=lookback_years,
        source_connectors=tuple(sources),
        upstream_flags=tuple(flags),
    )


__all__ = [
    "EA_COUNTRIES",
    "US_COUNTRY",
    "build_e1_inputs",
    "build_e3_inputs",
    "build_e4_inputs",
]
