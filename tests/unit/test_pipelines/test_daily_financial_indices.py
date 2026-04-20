"""Tests for daily_financial_indices pipeline."""

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
from sonar.indices.financial.f1_valuations import F1Inputs
from sonar.indices.financial.f2_momentum import F2Inputs
from sonar.indices.financial.f3_risk_appetite import F3Inputs
from sonar.indices.financial.f4_positioning import F4Inputs
from sonar.indices.orchestrator import FinancialIndicesInputs
from sonar.pipelines.daily_financial_indices import (
    T1_7_COUNTRIES,
    default_inputs_builder,
    run_one,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _synthetic_builder(
    session: Session,
    country_code: str,
    observation_date: date,
) -> FinancialIndicesInputs:
    rng = np.random.default_rng(42)
    f1 = F1Inputs(
        country_code=country_code,
        observation_date=observation_date,
        cape_ratio=25.0,
        buffett_ratio=1.4,
        erp_median_bps=500,
        forward_pe=17.0,
        property_gap_pp=0.0,
        cape_history=rng.normal(25.0, 5.0, 80).tolist(),
        buffett_history=rng.normal(1.4, 0.3, 80).tolist(),
        erp_history_bps=rng.normal(500.0, 100.0, 80).tolist(),
        forward_pe_history=rng.normal(17.0, 3.0, 80).tolist(),
        property_gap_history=rng.normal(0.0, 3.0, 80).tolist(),
    )
    f2 = F2Inputs(
        country_code=country_code,
        observation_date=observation_date,
        mom_3m_pct=0.02,
        mom_6m_pct=0.04,
        mom_12m_pct=0.08,
        breadth_above_ma200_pct=55.0,
        cross_asset_signal=0.0,
        mom_3m_history_pct=rng.normal(0.02, 0.05, 80).tolist(),
        mom_6m_history_pct=rng.normal(0.04, 0.08, 80).tolist(),
        mom_12m_history_pct=rng.normal(0.08, 0.15, 80).tolist(),
        breadth_history_pct=rng.normal(55.0, 15.0, 80).tolist(),
        cross_asset_history=rng.normal(0.0, 1.5, 80).tolist(),
    )
    f3 = F3Inputs(
        country_code=country_code,
        observation_date=observation_date,
        vix_level=18.0,
        move_level=90.0,
        credit_spread_hy_bps=500,
        credit_spread_ig_bps=150,
        fci_level=0.0,
        vix_history=rng.normal(18.0, 6.0, 80).tolist(),
        move_history=rng.normal(90.0, 25.0, 80).tolist(),
        hy_history_bps=rng.normal(500.0, 200.0, 80).tolist(),
        ig_history_bps=rng.normal(150.0, 50.0, 80).tolist(),
        fci_history=rng.normal(0.0, 0.6, 80).tolist(),
    )
    f4 = F4Inputs(
        country_code=country_code,
        observation_date=observation_date,
        aaii_bull_minus_bear_pct=5.0,
        put_call_ratio=1.0,
        cot_noncomm_net_sp500=0,
        margin_debt_gdp_pct=2.2,
        ipo_activity_score=50.0,
        aaii_history=rng.normal(5.0, 10.0, 80).tolist(),
        put_call_history=rng.normal(1.0, 0.2, 80).tolist(),
        cot_history=rng.normal(0.0, 80_000.0, 80).tolist(),
        margin_history_pct=rng.normal(2.2, 0.5, 80).tolist(),
        ipo_history=rng.normal(50.0, 15.0, 80).tolist(),
    )
    return FinancialIndicesInputs(
        country_code=country_code,
        observation_date=observation_date,
        f1=f1,
        f2=f2,
        f3=f3,
        f4=f4,
    )


def test_default_builder_returns_empty(session: Session) -> None:
    bundle = default_inputs_builder(session, "US", date(2024, 1, 2))
    assert bundle.f1 is None
    assert bundle.f2 is None
    assert bundle.f3 is None
    assert bundle.f4 is None


def test_run_one_default_persists_nothing(session: Session) -> None:
    outcome = run_one(session, "US", date(2024, 1, 2))
    assert outcome.persisted == {"f1": 0, "f2": 0, "f3": 0, "f4": 0}


def test_run_one_with_synthetic_persists_all_4(session: Session) -> None:
    outcome = run_one(session, "US", date(2024, 1, 2), inputs_builder=_synthetic_builder)
    assert outcome.persisted == {"f1": 1, "f2": 1, "f3": 1, "f4": 1}
    assert session.query(FinancialValuations).count() == 1
    assert session.query(FinancialMomentum).count() == 1
    assert session.query(FinancialRiskAppetite).count() == 1
    assert session.query(FinancialPositioning).count() == 1


def test_seven_country_synthetic_run(session: Session) -> None:
    d = date(2024, 1, 2)
    for country in T1_7_COUNTRIES:
        outcome = run_one(session, country, d, inputs_builder=_synthetic_builder)
        assert sum(outcome.persisted.values()) == 4
    # All 7 x 4 = 28 rows total.
    assert session.query(FinancialValuations).count() == 7
    assert session.query(FinancialMomentum).count() == 7
    assert session.query(FinancialRiskAppetite).count() == 7
    assert session.query(FinancialPositioning).count() == 7


def test_targets_constant_matches_brief() -> None:
    assert T1_7_COUNTRIES == ("US", "DE", "PT", "IT", "ES", "FR", "NL")
    assert len(T1_7_COUNTRIES) == 7
