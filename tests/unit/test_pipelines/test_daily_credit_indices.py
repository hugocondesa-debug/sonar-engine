"""Unit tests for the daily credit-indices pipeline."""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from sonar.db.models import Base, CreditGdpGap, CreditGdpStock, CreditImpulse, Dsr
from sonar.indices.credit.l1_credit_gdp_stock import CreditGdpStockInputs
from sonar.indices.credit.l2_credit_gdp_gap import CreditGdpGapInputs
from sonar.indices.credit.l3_credit_impulse import CreditImpulseInputs
from sonar.indices.credit.l4_dsr import DsrInputs
from sonar.indices.orchestrator import CreditIndicesInputs
from sonar.pipelines.daily_credit_indices import (
    T1_7_COUNTRIES,
    default_inputs_builder,
    run_one,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _build_synthetic_inputs(
    session: Session,
    country_code: str,
    observation_date: date,
) -> CreditIndicesInputs:
    rng = np.random.default_rng(42)
    n = 80
    credit = (1000.0 * (1.015 ** np.arange(n))) + rng.normal(0, 3, n)
    gdp = (500.0 * (1.010 ** np.arange(n))) + rng.normal(0, 1, n)
    ratio = (credit / gdp * 100.0).tolist()
    dsr_hist = rng.normal(13.0, 1.0, n).tolist()
    return CreditIndicesInputs(
        country_code=country_code,
        observation_date=observation_date,
        l1=CreditGdpStockInputs(
            country_code=country_code,
            observation_date=observation_date,
            ratio_pct=ratio[-1],
            ratio_pct_history=ratio,
        ),
        l2=CreditGdpGapInputs(
            country_code=country_code,
            observation_date=observation_date,
            ratio_pct_history=ratio,
        ),
        l3=CreditImpulseInputs(
            country_code=country_code,
            observation_date=observation_date,
            credit_stock_lcu_history=credit.tolist(),
            gdp_nominal_lcu_history=gdp.tolist(),
        ),
        l4=DsrInputs(
            country_code=country_code,
            observation_date=observation_date,
            lending_rate_pct=0.035,
            avg_maturity_years=15.0,
            debt_to_gdp_ratio=ratio[-1] / 100.0,
            dsr_pct_history=dsr_hist,
        ),
    )


def test_default_inputs_builder_produces_empty_bundle(session: Session) -> None:
    bundle = default_inputs_builder(session, "US", date(2024, 6, 30))
    assert bundle.l1 is None
    assert bundle.l2 is None
    assert bundle.l3 is None
    assert bundle.l4 is None


def test_run_one_default_builder_persists_nothing(session: Session) -> None:
    outcome = run_one(session, "US", date(2024, 6, 30))
    assert outcome.persisted == {"l1": 0, "l2": 0, "l3": 0, "l4": 0}
    assert set(outcome.results.skips.keys()) == {"l1", "l2", "l3", "l4"}
    assert session.query(CreditGdpStock).count() == 0


def test_run_one_with_synthetic_inputs_persists_all_4(session: Session) -> None:
    outcome = run_one(
        session,
        "US",
        date(2024, 6, 30),
        inputs_builder=_build_synthetic_inputs,
    )
    assert outcome.persisted == {"l1": 1, "l2": 1, "l3": 1, "l4": 1}
    assert session.query(CreditGdpStock).count() == 1
    assert session.query(CreditGdpGap).count() == 1
    assert session.query(CreditImpulse).count() == 1
    assert session.query(Dsr).count() == 1


def test_run_one_skips_when_inputs_raise_insufficient(session: Session) -> None:
    def bad_builder(
        session: Session,
        country: str,
        observation_date: date,
    ) -> CreditIndicesInputs:
        return CreditIndicesInputs(
            country_code=country,
            observation_date=observation_date,
            l1=CreditGdpStockInputs(
                country_code=country,
                observation_date=observation_date,
                ratio_pct=145.0,
                ratio_pct_history=[145.0],  # too short
            ),
        )

    outcome = run_one(session, "US", date(2024, 6, 30), inputs_builder=bad_builder)
    assert outcome.persisted["l1"] == 0
    assert "history" in outcome.results.skips["l1"].lower()


def test_seven_country_synthetic_run(session: Session) -> None:
    obs = date(2024, 6, 30)
    for country in T1_7_COUNTRIES:
        outcome = run_one(session, country, obs, inputs_builder=_build_synthetic_inputs)
        assert sum(outcome.persisted.values()) == 4
    # All 7 countries x 4 tables = 28 rows total.
    assert session.query(CreditGdpStock).count() == 7
    assert session.query(CreditGdpGap).count() == 7
    assert session.query(CreditImpulse).count() == 7
    assert session.query(Dsr).count() == 7


def test_targets_constant_matches_brief_scope() -> None:
    assert T1_7_COUNTRIES == ("US", "DE", "PT", "IT", "ES", "FR", "NL")
    assert len(T1_7_COUNTRIES) == 7
