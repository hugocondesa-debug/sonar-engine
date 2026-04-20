"""Unit tests for E1/E3/E4 builders (sprint-2a c4)."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import AsyncMock

import pytest

from sonar.connectors.eurostat import EurostatObservation
from sonar.connectors.fred import FredEconomicObservation
from sonar.connectors.te import TEIndicatorObservation
from sonar.indices.economic.builders import (
    build_e1_inputs,
    build_e3_inputs,
    build_e4_inputs,
)
from sonar.overlays.exceptions import DataUnavailableError


def _te_series(
    indicator: str, country: str, n: int = 60, base: float = 52.0
) -> list[TEIndicatorObservation]:
    """Synthetic monthly TE series with mild variation."""
    return [
        TEIndicatorObservation(
            observation_date=date(2019 + (i // 12), (i % 12) + 1, 28),
            value=base + (i % 10) * 0.2,
            country=country,
            indicator=indicator,
        )
        for i in range(n)
    ]


@pytest.fixture
def mock_te() -> Any:
    """TEConnector stub with all 5 fallback wrappers populated."""
    m = AsyncMock()
    m.fetch_ism_manufacturing_us.return_value = _te_series(
        "business confidence", "US", n=60, base=52.0
    )
    m.fetch_ism_services_us.return_value = _te_series(
        "non manufacturing pmi", "US", n=60, base=54.0
    )
    m.fetch_nfib_us.return_value = _te_series("nfib business optimism index", "US", n=60, base=95.0)
    m.fetch_ifo_business_climate_de.return_value = _te_series(
        "business confidence", "DE", n=60, base=90.0
    )
    m.fetch_zew_economic_sentiment_de.return_value = _te_series(
        "zew economic sentiment index", "DE", n=60, base=5.0
    )
    # Sprint 6.3 wrappers.
    m.fetch_conference_board_cc_us.return_value = _te_series(
        "consumer confidence", "US", n=60, base=99.0
    )
    m.fetch_michigan_5y_inflation_us.return_value = _te_series(
        "michigan 5 year inflation expectations", "US", n=60, base=2.9
    )
    return m


def _fred_series(sid: str, n: int = 36, base: float = 100.0) -> list[FredEconomicObservation]:
    """Synthetic monthly series with a smooth upward trend."""
    return [
        FredEconomicObservation(
            observation_date=date(2022 + (i // 12), (i % 12) + 1, 1),
            value=base + i * 0.3,
            series_id=sid,
        )
        for i in range(n)
    ]


def _eurostat_series(df: str, n: int = 36, base: float = 100.0) -> list[EurostatObservation]:
    return [
        EurostatObservation(
            observation_date=date(2022 + (i // 12), (i % 12) + 1, 28),
            value=base + i * 0.5,
            dataflow=df,
            geo="DE",
            time_period=f"2022-{i:02d}",
        )
        for i in range(n)
    ]


@pytest.fixture
def mock_fred() -> Any:
    """FredConnector stub pre-populated with every helper used by builders."""
    m = AsyncMock()
    # YoY-ish helpers return small decimal values.
    m.fetch_gdp_real_yoy_us.return_value = _fred_series("GDPC1", 20, base=0.02)
    m.fetch_industrial_production_yoy_us.return_value = _fred_series("INDPRO", 48, base=0.01)
    m.fetch_nonfarm_payrolls_yoy_us.return_value = _fred_series("PAYEMS", 48, base=0.015)
    m.fetch_retail_sales_real_yoy_us.return_value = _fred_series("RRSFS", 48, base=0.005)
    m.fetch_personal_income_real_yoy_us.return_value = _fred_series("W875RX1", 48, base=0.02)
    # Delisted series raise.
    m.fetch_ism_mfg_pmi.side_effect = DataUnavailableError("NAPM delisted")
    m.fetch_ism_services_pmi.side_effect = DataUnavailableError("NAPMII delisted")
    m.fetch_nfib_small_biz_us.side_effect = DataUnavailableError("NFIB delisted")
    # E3 level/rate helpers (big values).
    m.fetch_unemployment_rate_us.return_value = _fred_series("UNRATE", 48, base=4.0)
    m.fetch_emp_pop_ratio_us.return_value = _fred_series("EMRATIO", 48, base=60.0)
    m.fetch_prime_age_lfpr_us.return_value = _fred_series("LNS11300060", 48, base=83.0)
    m.fetch_eci_wages_yoy_us.return_value = _fred_series("ECIWAG", 20, base=0.04)
    m.fetch_jolts_openings_us.return_value = _fred_series("JTSJOL", 48, base=10_000.0)
    m.fetch_initial_claims_4wma_us.return_value = _fred_series("IC4WSA", 200, base=220_000.0)
    m.fetch_temp_help_yoy_us.return_value = _fred_series("TEMPHELPS", 48, base=0.005)
    m.fetch_quits_us.return_value = _fred_series("JTSQUL", 48, base=3_500.0)
    # E4.
    m.fetch_umich_sentiment_us.return_value = _fred_series("UMCSENT", 48, base=70.0)
    m.fetch_conference_board_confidence_us.return_value = _fred_series(
        "CSCICP03USM665S", 48, base=99.0
    )
    m.fetch_umich_5y_inflation_us.return_value = _fred_series("EXPINF5YR", 48, base=2.2)
    m.fetch_epu_us.return_value = _fred_series("USEPUINDXD", 200, base=120.0)
    m.fetch_vix_us.return_value = _fred_series("VIXCLS", 200, base=16.0)
    m.fetch_sloos_tightening_us.return_value = _fred_series("DRTSCILM", 20, base=5.0)
    return m


@pytest.fixture
def mock_eurostat() -> Any:
    m = AsyncMock()
    m.fetch_gdp_real_yoy.return_value = _eurostat_series("namq_10_gdp", 16, base=0.015)
    m.fetch_industrial_production_yoy.return_value = _eurostat_series("sts_inpr_m", 48, base=0.0)
    m.fetch_employment_yoy.return_value = _eurostat_series("namq_10_pe", 16, base=0.01)
    m.fetch_retail_sales_real_yoy.return_value = _eurostat_series("sts_trtu_m", 48, base=0.005)
    m.fetch_unemployment_rate.return_value = _eurostat_series("une_rt_m", 48, base=3.0)
    m.fetch_economic_sentiment_indicator.return_value = _eurostat_series(
        "ei_bssi_m_r2", 48, base=90.0
    )
    m.fetch_consumer_confidence.return_value = _eurostat_series("ei_bsco_m", 48, base=-15.0)
    return m


# ---------------------------------------------------------------------------
# build_e1_inputs
# ---------------------------------------------------------------------------


async def test_build_e1_us_full_stack(mock_fred: Any, mock_eurostat: Any) -> None:
    inputs = await build_e1_inputs(
        "US",
        date(2024, 6, 30),
        fred=mock_fred,
        eurostat=mock_eurostat,
    )
    assert inputs.country_code == "US"
    assert inputs.observation_date == date(2024, 6, 30)
    assert inputs.gdp_yoy is not None
    assert inputs.employment_yoy is not None
    assert inputs.industrial_production_yoy is not None
    assert inputs.retail_sales_real_yoy is not None
    assert inputs.personal_income_ex_transfers_yoy is not None
    # PMI must be None (delisted) + ISM_MFG_UNAVAILABLE flag.
    assert inputs.pmi_composite is None
    assert "ISM_MFG_UNAVAILABLE" in inputs.upstream_flags
    assert "FRED" in inputs.source_connectors


async def test_build_e1_de_eurostat(mock_fred: Any, mock_eurostat: Any) -> None:
    inputs = await build_e1_inputs(
        "DE",
        date(2024, 6, 30),
        fred=mock_fred,
        eurostat=mock_eurostat,
    )
    assert inputs.country_code == "DE"
    assert inputs.gdp_yoy is not None
    assert inputs.industrial_production_yoy is not None
    # EA: no personal-income Eurostat series, no PMI scraper yet.
    assert inputs.personal_income_ex_transfers_yoy is None
    assert inputs.pmi_composite is None
    assert "PERSONAL_INCOME_US_ONLY" in inputs.upstream_flags
    assert "PMI_UNAVAILABLE" in inputs.upstream_flags
    assert "EUROSTAT" in inputs.source_connectors


async def test_build_e1_unsupported_country_raises(mock_fred: Any, mock_eurostat: Any) -> None:
    with pytest.raises(ValueError, match="E1 builder does not support"):
        await build_e1_inputs("JP", date(2024, 6, 30), fred=mock_fred, eurostat=mock_eurostat)


# ---------------------------------------------------------------------------
# build_e3_inputs
# ---------------------------------------------------------------------------


async def test_build_e3_us_full_stack(mock_fred: Any, mock_eurostat: Any) -> None:
    inputs = await build_e3_inputs("US", date(2024, 6, 30), fred=mock_fred, eurostat=mock_eurostat)
    assert inputs.country_code == "US"
    assert inputs.unemployment_rate > 0
    assert inputs.unemployment_rate_12m_change is not None
    # With 48m of EM ratio history, 12m z-score is populated.
    assert inputs.employment_population_ratio_12m_z is not None
    assert inputs.openings_unemployed_ratio is not None
    assert "ATLANTA_FED_US_ONLY" in inputs.upstream_flags


async def test_build_e3_de_minimum_ur_only(mock_fred: Any, mock_eurostat: Any) -> None:
    inputs = await build_e3_inputs("DE", date(2024, 6, 30), fred=mock_fred, eurostat=mock_eurostat)
    assert inputs.country_code == "DE"
    assert inputs.unemployment_rate > 0
    # Plenty of US-only flags present.
    for tok in (
        "JOLTS_US_ONLY",
        "CLAIMS_US_ONLY",
        "ATLANTA_FED_US_ONLY",
        "TEMP_HELPS_US_ONLY",
        "ECI_US_ONLY",
    ):
        assert tok in inputs.upstream_flags
    assert inputs.eci_yoy_growth is None


async def test_build_e3_raises_without_unemployment(mock_fred: Any, mock_eurostat: Any) -> None:
    mock_fred.fetch_unemployment_rate_us.return_value = []
    with pytest.raises(DataUnavailableError, match="unemployment_rate"):
        await build_e3_inputs("US", date(2024, 6, 30), fred=mock_fred, eurostat=mock_eurostat)


# ---------------------------------------------------------------------------
# build_e4_inputs
# ---------------------------------------------------------------------------


async def test_build_e4_us_stack(mock_fred: Any, mock_eurostat: Any) -> None:
    inputs = await build_e4_inputs("US", date(2024, 6, 30), fred=mock_fred, eurostat=mock_eurostat)
    assert inputs.country_code == "US"
    # VIX always present (FRED global).
    assert inputs.vix_level is not None
    # ISM + NFIB miss → flags.
    for tok in ("ISM_MFG_UNAVAILABLE", "ISM_SVC_UNAVAILABLE", "NFIB_UNAVAILABLE"):
        assert tok in inputs.upstream_flags
    # 12m change is populated when series len >= 13.
    assert inputs.umich_sentiment_12m_change is not None


async def test_build_e4_de_partial(mock_fred: Any, mock_eurostat: Any) -> None:
    inputs = await build_e4_inputs("DE", date(2024, 6, 30), fred=mock_fred, eurostat=mock_eurostat)
    assert inputs.country_code == "DE"
    assert inputs.ec_esi is not None  # Eurostat ESI live
    assert inputs.vix_level is not None  # FRED global
    # US-only components absent + flagged.
    for tok in ("UMICH_US_ONLY", "ISM_MFG_US_ONLY", "NFIB_US_ONLY"):
        assert tok in inputs.upstream_flags


# ---------------------------------------------------------------------------
# TE fallback wiring (Week 6 Sprint 1 c3)
# ---------------------------------------------------------------------------


async def test_build_e4_us_with_te_fallback_covers_delisted(
    mock_fred: Any, mock_eurostat: Any, mock_te: Any
) -> None:
    """With TE connector provided, delisted FRED slots are filled + flagged."""
    inputs = await build_e4_inputs(
        "US",
        date(2024, 6, 30),
        fred=mock_fred,
        eurostat=mock_eurostat,
        te=mock_te,
    )
    # All three delisted slots now populated via TE.
    assert inputs.ism_manufacturing is not None
    assert inputs.ism_services is not None
    assert inputs.nfib_small_business is not None
    # TE_FALLBACK flags emitted.
    for tok in ("TE_FALLBACK_ISM_MFG", "TE_FALLBACK_ISM_SVC", "TE_FALLBACK_NFIB"):
        assert tok in inputs.upstream_flags
    # _UNAVAILABLE flags should NOT be present (TE covered).
    for tok in ("ISM_MFG_UNAVAILABLE", "ISM_SVC_UNAVAILABLE", "NFIB_UNAVAILABLE"):
        assert tok not in inputs.upstream_flags
    assert "TE" in inputs.source_connectors


async def test_build_e4_us_without_te_keeps_unavailable_flags(
    mock_fred: Any, mock_eurostat: Any
) -> None:
    """Omitting the TE connector preserves legacy *_UNAVAILABLE behaviour."""
    inputs = await build_e4_inputs("US", date(2024, 6, 30), fred=mock_fred, eurostat=mock_eurostat)
    for tok in ("ISM_MFG_UNAVAILABLE", "ISM_SVC_UNAVAILABLE", "NFIB_UNAVAILABLE"):
        assert tok in inputs.upstream_flags
    for tok in ("TE_FALLBACK_ISM_MFG", "TE_FALLBACK_ISM_SVC", "TE_FALLBACK_NFIB"):
        assert tok not in inputs.upstream_flags


async def test_build_e4_us_te_fallback_also_fails(mock_fred: Any, mock_eurostat: Any) -> None:
    """TE wrapper raises → slot stays None + legacy _UNAVAILABLE flag."""
    from unittest.mock import AsyncMock  # noqa: PLC0415

    m_te = AsyncMock()
    m_te.fetch_ism_manufacturing_us.side_effect = DataUnavailableError("TE outage")
    m_te.fetch_ism_services_us.side_effect = DataUnavailableError("TE outage")
    m_te.fetch_nfib_us.side_effect = DataUnavailableError("TE outage")

    inputs = await build_e4_inputs(
        "US",
        date(2024, 6, 30),
        fred=mock_fred,
        eurostat=mock_eurostat,
        te=m_te,
    )
    assert inputs.ism_manufacturing is None
    assert inputs.ism_services is None
    assert inputs.nfib_small_business is None
    for tok in ("ISM_MFG_UNAVAILABLE", "ISM_SVC_UNAVAILABLE", "NFIB_UNAVAILABLE"):
        assert tok in inputs.upstream_flags
    for tok in ("TE_FALLBACK_ISM_MFG", "TE_FALLBACK_ISM_SVC", "TE_FALLBACK_NFIB"):
        assert tok not in inputs.upstream_flags


async def test_build_e4_de_with_te_fallback_adds_ifo_zew(
    mock_fred: Any, mock_eurostat: Any, mock_te: Any
) -> None:
    """DE + TE: Ifo + ZEW now populated, flagged TE_FALLBACK_*."""
    inputs = await build_e4_inputs(
        "DE",
        date(2024, 6, 30),
        fred=mock_fred,
        eurostat=mock_eurostat,
        te=mock_te,
    )
    assert inputs.ifo_business_climate is not None
    assert inputs.zew_expectations is not None
    for tok in ("TE_FALLBACK_IFO", "TE_FALLBACK_ZEW"):
        assert tok in inputs.upstream_flags
    # Ifo/ZEW _DE_ONLY flags should NOT fire when TE covers them.
    for tok in ("IFO_DE_ONLY", "ZEW_DE_ONLY"):
        assert tok not in inputs.upstream_flags
    assert "TE" in inputs.source_connectors


async def test_build_e4_de_without_te_keeps_ifo_zew_flags(
    mock_fred: Any, mock_eurostat: Any
) -> None:
    inputs = await build_e4_inputs("DE", date(2024, 6, 30), fred=mock_fred, eurostat=mock_eurostat)
    for tok in ("IFO_DE_ONLY", "ZEW_DE_ONLY"):
        assert tok in inputs.upstream_flags


# ---------------------------------------------------------------------------
# Sprint 6.3: TE primary for CB CC + UMich 5Y inflation (CAL-093 resolve)
# ---------------------------------------------------------------------------


async def test_build_e4_us_te_primary_for_cb_and_umich_5y(
    mock_fred: Any, mock_eurostat: Any, mock_te: Any
) -> None:
    """When TE is provided, CB CC + UMich 5Y come from TE (higher quality)
    and the builder emits TE_FALLBACK_{CB_CC, UMICH_5Y} flags.
    """
    inputs = await build_e4_inputs(
        "US", date(2024, 6, 30), fred=mock_fred, eurostat=mock_eurostat, te=mock_te
    )
    # TE slots populated.
    assert inputs.conference_board_confidence_12m_change is not None
    assert inputs.umich_5y_inflation_exp is not None
    for tok in ("TE_FALLBACK_CB_CC", "TE_FALLBACK_UMICH_5Y"):
        assert tok in inputs.upstream_flags
    assert "TE" in inputs.source_connectors
    # Confirm TE wrappers were invoked and FRED was not for these slots
    # (post-swap behaviour).
    mock_te.fetch_conference_board_cc_us.assert_called_once()
    mock_te.fetch_michigan_5y_inflation_us.assert_called_once()
    mock_fred.fetch_conference_board_confidence_us.assert_not_called()
    mock_fred.fetch_umich_5y_inflation_us.assert_not_called()


async def test_build_e4_us_te_unavailable_falls_back_to_fred(
    mock_fred: Any, mock_eurostat: Any
) -> None:
    """TE wrappers raise → FRED fallback populates CB + UMich 5Y slots."""
    from unittest.mock import AsyncMock  # noqa: PLC0415

    m_te = AsyncMock()
    m_te.fetch_conference_board_cc_us.side_effect = DataUnavailableError("TE down")
    m_te.fetch_michigan_5y_inflation_us.side_effect = DataUnavailableError("TE down")
    # Other TE wrappers still work (otherwise this regresses ISM/NFIB coverage).
    m_te.fetch_ism_manufacturing_us.return_value = _te_series(
        "business confidence", "US", n=60, base=52.0
    )
    m_te.fetch_ism_services_us.return_value = _te_series(
        "non manufacturing pmi", "US", n=60, base=54.0
    )
    m_te.fetch_nfib_us.return_value = _te_series("nfib business optimism index", "US", n=60)

    inputs = await build_e4_inputs(
        "US", date(2024, 6, 30), fred=mock_fred, eurostat=mock_eurostat, te=m_te
    )
    # FRED fallback covered both slots.
    assert inputs.conference_board_confidence_12m_change is not None
    assert inputs.umich_5y_inflation_exp is not None
    for tok in ("TE_FALLBACK_CB_CC", "TE_FALLBACK_UMICH_5Y"):
        assert tok not in inputs.upstream_flags
    mock_fred.fetch_conference_board_confidence_us.assert_called_once()
    mock_fred.fetch_umich_5y_inflation_us.assert_called_once()
