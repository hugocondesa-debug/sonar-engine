"""Tests for daily_economic_indices pipeline (week7 sprint B C2)."""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from sonar.db.models import Base, E1Activity, E3Labor, E4Sentiment
from sonar.indices.economic.e1_activity import E1ActivityInputs
from sonar.indices.economic.e3_labor import E3LaborInputs
from sonar.indices.economic.e4_sentiment import E4SentimentInputs
from sonar.pipelines.daily_economic_indices import (
    T1_7_COUNTRIES,
    EconomicIndicesInputs,
    compute_all_economic_indices,
    default_inputs_builder,
    run_one,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _synthetic_builder(
    _session: Session,
    country_code: str,
    observation_date: date,
) -> EconomicIndicesInputs:
    rng = np.random.default_rng(seed=0)
    e1 = E1ActivityInputs(
        country_code=country_code,
        observation_date=observation_date,
        gdp_yoy=0.025,
        gdp_yoy_history=rng.normal(0.025, 0.01, 80).tolist(),
        employment_yoy=0.015,
        employment_yoy_history=rng.normal(0.015, 0.005, 80).tolist(),
        industrial_production_yoy=0.01,
        industrial_production_yoy_history=rng.normal(0.01, 0.02, 80).tolist(),
        retail_sales_real_yoy=0.018,
        retail_sales_real_yoy_history=rng.normal(0.018, 0.01, 80).tolist(),
        personal_income_ex_transfers_yoy=0.022,
        personal_income_ex_transfers_yoy_history=rng.normal(0.022, 0.008, 80).tolist(),
        source_connectors=("FRED",),
    )
    e3 = E3LaborInputs(
        country_code=country_code,
        observation_date=observation_date,
        unemployment_rate=0.039,
        unemployment_rate_history=rng.normal(0.05, 0.01, 80).tolist(),
        employment_population_ratio_12m_z=-0.1,
        employment_population_ratio_12m_z_history=rng.normal(0.0, 0.5, 80).tolist(),
        prime_age_lfpr_12m_change=0.002,
        prime_age_lfpr_12m_change_history=rng.normal(0.0, 0.003, 80).tolist(),
        eci_yoy_growth=0.042,
        eci_yoy_growth_history=rng.normal(0.03, 0.01, 80).tolist(),
        openings_unemployed_ratio=1.2,
        openings_unemployed_ratio_history=rng.normal(1.2, 0.3, 80).tolist(),
        quits_rate=0.024,
        quits_rate_history=rng.normal(0.024, 0.003, 80).tolist(),
        initial_claims_4wk_avg=220_000.0,
        initial_claims_4wk_avg_history=rng.normal(250_000.0, 50_000.0, 80).tolist(),
        source_connectors=("FRED",),
    )
    e4 = E4SentimentInputs(
        country_code=country_code,
        observation_date=observation_date,
        umich_sentiment_12m_change=-5.0,
        umich_sentiment_12m_change_history=rng.normal(0.0, 5.0, 80).tolist(),
        conference_board_confidence_12m_change=-2.0,
        conference_board_confidence_12m_change_history=rng.normal(0.0, 3.0, 80).tolist(),
        umich_5y_inflation_exp=3.0,
        umich_5y_inflation_exp_history=rng.normal(3.0, 0.3, 80).tolist(),
        ism_manufacturing=50.0,
        ism_manufacturing_history=rng.normal(50.0, 5.0, 80).tolist(),
        ism_services=54.0,
        ism_services_history=rng.normal(54.0, 3.0, 80).tolist(),
        epu_index=120.0,
        epu_index_history=rng.normal(120.0, 30.0, 80).tolist(),
        vix_level=18.0,
        vix_level_history=rng.normal(18.0, 6.0, 80).tolist(),
        sloos_standards_net_pct=0.0,
        sloos_standards_net_pct_history=rng.normal(0.0, 15.0, 80).tolist(),
        source_connectors=("FRED",),
    )
    return EconomicIndicesInputs(
        country_code=country_code,
        observation_date=observation_date,
        e1=e1,
        e3=e3,
        e4=e4,
    )


def test_default_builder_returns_empty(session: Session) -> None:
    bundle = default_inputs_builder(session, "US", date(2024, 12, 31))
    assert bundle.e1 is None
    assert bundle.e3 is None
    assert bundle.e4 is None


def test_compute_all_economic_indices_empty_inputs() -> None:
    results = compute_all_economic_indices(
        EconomicIndicesInputs(country_code="US", observation_date=date(2024, 12, 31))
    )
    assert results.e1 is None
    assert results.e2 is None
    assert results.e3 is None
    assert results.e4 is None
    assert results.skips is not None
    assert set(results.skips) == {"e1", "e2", "e3", "e4"}


def test_run_one_default_persists_nothing(session: Session) -> None:
    outcome = run_one(session, "US", date(2024, 12, 31))
    assert outcome.persisted == {"e1": 0, "e2": 0, "e3": 0, "e4": 0}


def test_run_one_with_synthetic_persists_three(session: Session) -> None:
    outcome = run_one(session, "US", date(2024, 12, 31), inputs_builder=_synthetic_builder)
    assert outcome.persisted == {"e1": 1, "e2": 0, "e3": 1, "e4": 1}
    assert session.query(E1Activity).count() == 1
    assert session.query(E3Labor).count() == 1
    assert session.query(E4Sentiment).count() == 1


def test_seven_country_synthetic_run(session: Session) -> None:
    d = date(2024, 12, 31)
    for country in T1_7_COUNTRIES:
        outcome = run_one(session, country, d, inputs_builder=_synthetic_builder)
        # E3 + E4 require some US-specific inputs (VIX is US-fetched) but
        # with synthetic data all three sub-indices compute for every
        # country.
        assert outcome.persisted["e1"] == 1
    assert session.query(E1Activity).count() == 7


def test_targets_constant_matches_brief() -> None:
    assert T1_7_COUNTRIES == ("US", "DE", "PT", "IT", "ES", "FR", "NL")
    assert len(T1_7_COUNTRIES) == 7
