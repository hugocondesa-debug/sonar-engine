"""Tests for daily_monetary_indices pipeline (week7 sprint B C3)."""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from sonar.db.models import (
    Base,
    M1EffectiveRatesResult as M1Row,
    M2TaylorGapsResult as M2Row,
    M4FciResult as M4Row,
)
from sonar.indices.monetary.m1_effective_rates import M1EffectiveRatesInputs
from sonar.indices.monetary.m2_taylor_gaps import M2TaylorGapsInputs
from sonar.indices.monetary.m4_fci import M4FciInputs
from sonar.indices.monetary.orchestrator import MonetaryIndicesInputs
from sonar.pipelines.daily_monetary_indices import (
    MONETARY_SUPPORTED_COUNTRIES,
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
    _session: Session,
    country_code: str,
    observation_date: date,
) -> MonetaryIndicesInputs:
    rng = np.random.default_rng(seed=0)
    m1 = M1EffectiveRatesInputs(
        country_code=country_code,
        observation_date=observation_date,
        policy_rate_pct=0.0525,
        expected_inflation_5y_pct=0.025,
        r_star_pct=0.008,
        balance_sheet_pct_gdp_current=0.30,
        balance_sheet_pct_gdp_12m_ago=0.34,
        real_shadow_rate_history=rng.normal(0.01, 0.005, 360).tolist(),
        stance_vs_neutral_history=rng.normal(0.005, 0.005, 360).tolist(),
        balance_sheet_signal_history=rng.normal(0.0, 0.01, 360).tolist(),
        source_connector=("fred",),
    )
    m2 = M2TaylorGapsInputs(
        country_code=country_code,
        observation_date=observation_date,
        policy_rate_pct=0.0525,
        inflation_yoy_pct=0.028,
        inflation_target_pct=0.02,
        output_gap_pct=0.005,
        r_star_pct=0.008,
        prev_policy_rate_pct=0.0525,
        inflation_forecast_2y_pct=0.024,
        gap_1993_history=rng.normal(0.0, 0.003, 360).tolist(),
        gap_1999_history=rng.normal(0.0, 0.003, 360).tolist(),
        gap_forward_history=rng.normal(0.0, 0.003, 360).tolist(),
        gap_inertia_history=rng.normal(0.0, 0.003, 360).tolist(),
        source_connector=("fred", "cbo"),
    )
    m4 = M4FciInputs(
        country_code=country_code,
        observation_date=observation_date,
        nfci_level=-0.5,
        nfci_history=rng.normal(-0.5, 0.3, 360).tolist(),
        fci_level_12m_ago=-0.45,
        source_connector=("fred",),
    )
    return MonetaryIndicesInputs(
        country_code=country_code,
        observation_date=observation_date,
        m1=m1,
        m2=m2,
        m4=m4,
    )


def test_default_builder_returns_empty(session: Session) -> None:
    bundle = default_inputs_builder(session, "US", date(2024, 12, 31))
    assert bundle.m1 is None
    assert bundle.m2 is None
    assert bundle.m4 is None


def test_run_one_default_persists_nothing(session: Session) -> None:
    outcome = run_one(session, "US", date(2024, 12, 31))
    assert outcome.persisted == {"m1": 0, "m2": 0, "m3": 0, "m4": 0}


def test_run_one_with_synthetic_persists_three(session: Session) -> None:
    outcome = run_one(session, "US", date(2024, 12, 31), inputs_builder=_synthetic_builder)
    assert outcome.persisted == {"m1": 1, "m2": 1, "m3": 0, "m4": 1}
    assert session.query(M1Row).count() == 1
    assert session.query(M2Row).count() == 1
    assert session.query(M4Row).count() == 1


def test_seven_country_synthetic_run(session: Session) -> None:
    d = date(2024, 12, 31)
    for country in T1_7_COUNTRIES:
        outcome = run_one(session, country, d, inputs_builder=_synthetic_builder)
        assert outcome.persisted["m1"] == 1
    assert session.query(M1Row).count() == 7


def test_targets_constant_matches_brief() -> None:
    assert T1_7_COUNTRIES == ("US", "DE", "PT", "IT", "ES", "FR", "NL")
    assert len(T1_7_COUNTRIES) == 7


def test_monetary_supported_countries_includes_uk() -> None:
    """Sprint 8-I adds UK; US + EA stay; UK must be opt-in via --country."""
    assert "UK" in MONETARY_SUPPORTED_COUNTRIES
    assert "US" in MONETARY_SUPPORTED_COUNTRIES
    assert "EA" in MONETARY_SUPPORTED_COUNTRIES
    # UK is NOT in T1_7_COUNTRIES (--all-t1 preserves 7-country semantics).
    assert "UK" not in T1_7_COUNTRIES


def test_run_one_uk_synthetic_persists_m1(session: Session) -> None:
    """UK synthetic bundle — pipeline persists M1 (M2/M4 not wired this sprint)."""
    outcome = run_one(session, "UK", date(2024, 12, 31), inputs_builder=_synthetic_builder)
    assert outcome.persisted["m1"] == 1
    # The synthetic builder populates M2/M4 too, so they persist here;
    # the real live path leaves them None via NotImplementedError catch.
    assert session.query(M1Row).filter(M1Row.country_code == "UK").count() == 1
