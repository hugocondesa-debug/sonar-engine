"""Tests for daily_overlays pipeline skeleton (week7 sprint C C1)."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from sonar.db.models import Base, NSSYieldCurveSpot
from sonar.overlays.exceptions import InsufficientDataError
from sonar.pipelines.daily_overlays import (
    EXIT_CONVERGENCE,
    EXIT_DUPLICATE,
    EXIT_INSUFFICIENT_DATA,
    EXIT_IO,
    EXIT_OK,
    T1_7_COUNTRIES,
    OverlayBundle,
    default_inputs_builder,
    nss_spot_exists,
    run_one,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_nss_spot(session: Session, country: str, obs_date: date) -> None:
    row = NSSYieldCurveSpot(
        country_code=country,
        date=obs_date,
        methodology_version="NSS_v1.0",
        fit_id="00000000-0000-0000-0000-000000000000",
        beta_0=0.04,
        beta_1=-0.01,
        beta_2=0.005,
        beta_3=None,
        lambda_1=1.5,
        lambda_2=None,
        fitted_yields_json='{"10Y": 0.04}',
        observations_used=11,
        rmse_bps=5.0,
        xval_deviation_bps=None,
        confidence=0.9,
        flags=None,
        source_connector="fred",
    )
    session.add(row)
    session.commit()


def test_exit_code_enum() -> None:
    assert EXIT_OK == 0
    assert EXIT_INSUFFICIENT_DATA == 1
    assert EXIT_CONVERGENCE == 2
    assert EXIT_DUPLICATE == 3
    assert EXIT_IO == 4


def test_t1_constant() -> None:
    assert T1_7_COUNTRIES == ("US", "DE", "PT", "IT", "ES", "FR", "NL")
    assert len(T1_7_COUNTRIES) == 7


def test_default_builder_returns_empty_bundle(session: Session) -> None:
    bundle = default_inputs_builder(session, "US", date(2024, 12, 31))
    assert isinstance(bundle, OverlayBundle)
    assert bundle.country_code == "US"
    assert bundle.erp is None
    assert bundle.crp is None
    assert bundle.rating is None
    assert bundle.expected_inflation is None


def test_nss_spot_exists_false_when_empty(session: Session) -> None:
    assert nss_spot_exists(session, "US", date(2024, 12, 31)) is False


def test_nss_spot_exists_true_after_seed(session: Session) -> None:
    _seed_nss_spot(session, "US", date(2024, 12, 31))
    assert nss_spot_exists(session, "US", date(2024, 12, 31)) is True


def test_run_one_requires_nss_by_default(session: Session) -> None:
    with pytest.raises(InsufficientDataError, match="yield_curves_spot missing"):
        run_one(session, "US", date(2024, 12, 31))


def test_run_one_skips_all_overlays_with_empty_bundle(session: Session) -> None:
    _seed_nss_spot(session, "US", date(2024, 12, 31))
    outcome = run_one(session, "US", date(2024, 12, 31))
    # Every overlay skipped because default bundle supplies no inputs.
    assert outcome.results.erp is None
    assert outcome.results.crp is None
    assert outcome.results.rating is None
    assert outcome.results.expected_inflation is None
    assert outcome.results.skips == {
        "erp": "no inputs provided",
        "crp": "no inputs provided",
        "rating": "no inputs provided",
        "expected_inflation": "no inputs provided",
    }
    assert outcome.persisted == {"erp": 0, "crp": 0, "rating": 0, "expected_inflation": 0}


def test_run_one_without_nss_precondition_works_for_tests(session: Session) -> None:
    """Unit-test path: ``require_nss=False`` bypasses the DAG gate."""
    outcome = run_one(session, "DE", date(2024, 12, 31), require_nss=False)
    assert outcome.country_code == "DE"
    assert outcome.persisted == {"erp": 0, "crp": 0, "rating": 0, "expected_inflation": 0}
