"""7-country vertical slice — F1-F4 orchestrated + persisted.

Uses synthetic-but-spec-plausible input bundles for all 7 T1 countries
(US/DE/PT/IT/ES/FR/NL) at 2024-01-02. Connectors are stubbed to
exercise the orchestrator + persistence path end-to-end without
hitting any network provider.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from sonar.db.models import (
    Base,
    FinancialMomentum,
    FinancialPositioning,
    FinancialRiskAppetite,
    FinancialValuations,
)
from sonar.db.persistence import (
    persist_f1_valuations_result,
    persist_f2_momentum_result,
    persist_f3_risk_appetite_result,
    persist_f4_positioning_result,
    persist_many_financial_results,
)
from sonar.indices.financial.f1_valuations import F1Inputs
from sonar.indices.financial.f2_momentum import F2Inputs
from sonar.indices.financial.f3_risk_appetite import F3Inputs
from sonar.indices.financial.f4_positioning import F4Inputs
from sonar.indices.orchestrator import (
    FinancialIndicesInputs,
    compute_all_financial_indices,
)

T1_COUNTRIES: tuple[str, ...] = ("US", "DE", "PT", "IT", "ES", "FR", "NL")


def _build_country_inputs(country: str, d: date, seed: int) -> FinancialIndicesInputs:
    rng = np.random.default_rng(seed)
    # F1 Valuations — US full; other T1 degrades ERP to MATURE_ERP_PROXY_US
    # (brief §9 notes).
    f1 = F1Inputs(
        country_code=country,
        observation_date=d,
        cape_ratio=25.0 + rng.uniform(-2.0, 2.0),
        buffett_ratio=1.2 + rng.uniform(-0.1, 0.1),
        erp_median_bps=450 if country == "US" else None,
        forward_pe=17.0 + rng.uniform(-1.0, 1.0),
        property_gap_pp=rng.uniform(-3.0, 5.0),
        cape_history=rng.normal(22.0, 5.0, 80).tolist(),
        buffett_history=rng.normal(1.1, 0.3, 80).tolist(),
        erp_history_bps=rng.normal(500.0, 100.0, 80).tolist() if country == "US" else None,
        forward_pe_history=rng.normal(16.0, 3.0, 80).tolist(),
        property_gap_history=rng.normal(0.0, 3.0, 80).tolist(),
        upstream_flags=() if country == "US" else ("MATURE_ERP_PROXY_US",),
    )
    f2 = F2Inputs(
        country_code=country,
        observation_date=d,
        mom_3m_pct=0.04 + rng.uniform(-0.02, 0.02),
        mom_6m_pct=0.08 + rng.uniform(-0.03, 0.03),
        mom_12m_pct=0.15 + rng.uniform(-0.05, 0.05),
        breadth_above_ma200_pct=60.0 + rng.uniform(-10.0, 10.0),
        cross_asset_signal=1.0 + rng.uniform(-1.0, 1.0),
        mom_3m_history_pct=rng.normal(0.02, 0.05, 80).tolist(),
        mom_6m_history_pct=rng.normal(0.04, 0.08, 80).tolist(),
        mom_12m_history_pct=rng.normal(0.08, 0.15, 80).tolist(),
        breadth_history_pct=rng.normal(55.0, 15.0, 80).tolist(),
        cross_asset_history=rng.normal(0.0, 1.5, 80).tolist(),
        primary_index="SPX" if country == "US" else "SXXP",
    )
    f3 = F3Inputs(
        country_code=country,
        observation_date=d,
        vix_level=15.0 + rng.uniform(-3.0, 3.0),
        move_level=100.0 if country == "US" else None,
        credit_spread_hy_bps=int(350 + rng.uniform(-50, 50)),
        credit_spread_ig_bps=int(110 + rng.uniform(-20, 20)),
        fci_level=-0.3 + rng.uniform(-0.3, 0.3),
        vix_history=rng.normal(18.0, 6.0, 80).tolist(),
        move_history=rng.normal(90.0, 25.0, 80).tolist() if country == "US" else None,
        hy_history_bps=rng.normal(500.0, 200.0, 80).tolist(),
        ig_history_bps=rng.normal(150.0, 50.0, 80).tolist(),
        fci_history=rng.normal(0.0, 0.6, 80).tolist(),
    )
    f4 = F4Inputs(
        country_code=country,
        observation_date=d,
        aaii_bull_minus_bear_pct=10.0 + rng.uniform(-10.0, 10.0) if country == "US" else None,
        put_call_ratio=0.85 + rng.uniform(-0.15, 0.15),
        cot_noncomm_net_sp500=int(50_000 + rng.uniform(-20_000, 20_000))
        if country == "US"
        else None,
        margin_debt_gdp_pct=2.5 + rng.uniform(-0.3, 0.3) if country == "US" else None,
        ipo_activity_score=50.0 + rng.uniform(-10.0, 10.0),
        aaii_history=rng.normal(5.0, 10.0, 80).tolist() if country == "US" else None,
        put_call_history=rng.normal(1.0, 0.2, 80).tolist(),
        cot_history=rng.normal(0.0, 80_000.0, 80).tolist() if country == "US" else None,
        margin_history_pct=rng.normal(2.2, 0.5, 80).tolist() if country == "US" else None,
        ipo_history=rng.normal(50.0, 15.0, 80).tolist(),
        upstream_flags=() if country == "US" else ("AAII_PROXY",),
    )
    return FinancialIndicesInputs(
        country_code=country, observation_date=d, f1=f1, f2=f2, f3=f3, f4=f4
    )


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


@pytest.mark.parametrize("country", T1_COUNTRIES)
def test_orchestrator_emits_f1_to_f4_per_country(country: str) -> None:
    d = date(2024, 1, 2)
    seed = 100 + T1_COUNTRIES.index(country)
    inputs = _build_country_inputs(country, d, seed)
    results = compute_all_financial_indices(inputs)
    # US: all 4 full. Non-US: F1/F2/F3 always emit; F4 may skip (< 2/5 after
    # AAII/COT/margin drops).
    assert results.f1 is not None, f"{country}: F1 missing"
    assert results.f2 is not None, f"{country}: F2 missing"
    assert results.f3 is not None, f"{country}: F3 missing"
    if country == "US":
        assert results.f4 is not None, "US F4 must emit"
    # score_normalized ∈ [0, 100] invariant.
    for r in (results.f1, results.f2, results.f3):
        assert 0.0 <= r.score_normalized <= 100.0


def test_seven_country_contract_all_indices_clip_range() -> None:
    d = date(2024, 1, 2)
    for idx, country in enumerate(T1_COUNTRIES):
        results = compute_all_financial_indices(_build_country_inputs(country, d, 200 + idx))
        for r in (results.f1, results.f2, results.f3, results.f4):
            if r is None:
                continue
            assert 0.0 <= r.score_normalized <= 100.0
            assert 0.0 <= r.confidence <= 1.0


def test_degraded_flags_present_on_non_us() -> None:
    d = date(2024, 1, 2)
    for idx, country in enumerate(T1_COUNTRIES):
        if country == "US":
            continue
        results = compute_all_financial_indices(_build_country_inputs(country, d, 300 + idx))
        # F1 must carry MATURE_ERP_PROXY_US (inherited as upstream flag).
        assert results.f1 is not None
        assert "MATURE_ERP_PROXY_US" in results.f1.flags, f"{country}: missing proxy flag"


def test_persist_all_7_countries(session: Session) -> None:
    d = date(2024, 1, 2)
    for idx, country in enumerate(T1_COUNTRIES):
        results = compute_all_financial_indices(_build_country_inputs(country, d, 400 + idx))
        if results.f1 is not None:
            persist_f1_valuations_result(session, results.f1)
        if results.f2 is not None:
            persist_f2_momentum_result(session, results.f2)
        if results.f3 is not None:
            persist_f3_risk_appetite_result(session, results.f3)
        if results.f4 is not None:
            persist_f4_positioning_result(session, results.f4)

    assert session.query(FinancialValuations).count() == 7
    assert session.query(FinancialMomentum).count() == 7
    assert session.query(FinancialRiskAppetite).count() == 7
    # F4 persists for US + partial EA (put_call + ipo → 2/5 minimum met)
    assert session.query(FinancialPositioning).count() >= 1


def test_persist_many_helper_batches(session: Session) -> None:
    d = date(2024, 1, 2)
    results = compute_all_financial_indices(_build_country_inputs("US", d, 500))
    written = persist_many_financial_results(session, results)
    assert written == {"f1": 1, "f2": 1, "f3": 1, "f4": 1}
    assert session.query(FinancialValuations).count() == 1
    assert session.query(FinancialMomentum).count() == 1
    assert session.query(FinancialRiskAppetite).count() == 1
    assert session.query(FinancialPositioning).count() == 1


def test_orchestrator_skips_missing_inputs() -> None:
    d = date(2024, 1, 2)
    inputs = FinancialIndicesInputs(country_code="US", observation_date=d)
    results = compute_all_financial_indices(inputs)
    assert results.f1 is None
    assert results.f2 is None
    assert results.f3 is None
    assert results.f4 is None
    assert set(results.skips.keys()) == {"f1", "f2", "f3", "f4"}
