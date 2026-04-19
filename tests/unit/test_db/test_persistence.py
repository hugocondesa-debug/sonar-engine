"""Persistence layer tests — atomic 4-row write, dup detection, rollback."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from sonar.db.models import (
    NSSYieldCurveForwards,
    NSSYieldCurveReal,
    NSSYieldCurveSpot,
    NSSYieldCurveZero,
)
from sonar.db.persistence import DuplicatePersistError, persist_nss_fit_result
from sonar.overlays.nss import RealCurve

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from sonar.overlays.nss import NSSFitResult


def test_persist_three_tables_when_real_is_none(
    db_session: Session, us_fit_result: NSSFitResult
) -> None:
    assert us_fit_result.real is None  # fixture invariant
    persist_nss_fit_result(db_session, us_fit_result)

    spot = (
        db_session.query(NSSYieldCurveSpot)
        .filter_by(country_code="US", date=date(2024, 1, 2))
        .one()
    )
    zero = db_session.query(NSSYieldCurveZero).filter_by(fit_id=spot.fit_id).one()
    forwards = db_session.query(NSSYieldCurveForwards).filter_by(fit_id=spot.fit_id).one()
    assert spot.fit_id == str(us_fit_result.fit_id)
    assert spot.confidence == us_fit_result.spot.confidence
    assert spot.beta_0 == pytest.approx(us_fit_result.spot.params.beta_0)
    assert json.loads(spot.fitted_yields_json)["10Y"] == pytest.approx(
        us_fit_result.spot.fitted_yields["10Y"]
    )
    assert zero.derivation == "nss_derived"
    assert "5y5y" in json.loads(forwards.forwards_json)
    assert db_session.query(NSSYieldCurveReal).count() == 0


def test_persist_four_tables_with_real(db_session: Session, us_fit_result: NSSFitResult) -> None:
    real = RealCurve(
        real_yields={"5Y": 0.018, "10Y": 0.020, "30Y": 0.021},
        method="direct_linker",
        linker_connector="fred",
    )
    result = replace(us_fit_result, real=real)
    persist_nss_fit_result(db_session, result)

    real_row = db_session.query(NSSYieldCurveReal).one()
    assert real_row.method == "direct_linker"
    assert real_row.linker_connector == "fred"
    assert json.loads(real_row.real_yields_json)["10Y"] == pytest.approx(0.020)


def test_duplicate_triplet_raises(db_session: Session, us_fit_result: NSSFitResult) -> None:
    persist_nss_fit_result(db_session, us_fit_result)

    # Re-persist same triplet (different fit_id) → should fail UNIQUE
    # on (country, date, methodology_version).
    duplicate = replace(us_fit_result, fit_id=uuid4())
    with pytest.raises(DuplicatePersistError, match="Fit already persisted"):
        persist_nss_fit_result(db_session, duplicate)

    # Spot table still has only the first row.
    assert db_session.query(NSSYieldCurveSpot).count() == 1


def test_partial_failure_rolls_back_spot(db_session: Session, us_fit_result: NSSFitResult) -> None:
    """If a sibling write fails after spot landed, spot is rolled back too.

    Setup: pre-persist a complete fit for a *different* fit_id but the same
    triplet on a sibling table only (we forge a forwards row that collides
    on the (country, date, version) UNIQUE). When persist_nss_fit_result
    runs:

      1. spot row inserts (its UNIQUE is on a different triplet — fresh)
      2. zero row inserts
      3. forwards row hits UNIQUE collision → IntegrityError
      4. session.rollback() must wipe spot + zero (not just forwards)
    """
    # First persist a real fit to seed a spot row; then we add an extra
    # forwards row pointing to it for a different (date) triplet that will
    # collide with the second persist call.
    persist_nss_fit_result(db_session, us_fit_result)
    seeded_spot = db_session.query(NSSYieldCurveSpot).one()

    other_date_fit = replace(us_fit_result, fit_id=uuid4(), observation_date=date(2024, 1, 3))
    # Pre-write a forwards row at 2024-01-03 reusing the seeded fit_id
    # (FK valid) and triplet that will collide.
    db_session.add(
        NSSYieldCurveForwards(
            country_code="US",
            date=date(2024, 1, 3),
            methodology_version=us_fit_result.methodology_version,
            fit_id=seeded_spot.fit_id,
            forwards_json="{}",
            confidence=0.9,
        )
    )
    db_session.commit()

    spot_count_before = db_session.query(NSSYieldCurveSpot).count()
    zero_count_before = db_session.query(NSSYieldCurveZero).count()

    with pytest.raises(DuplicatePersistError):
        persist_nss_fit_result(db_session, other_date_fit)

    # Spot for 2024-01-03 must NOT exist (rollback wiped it).
    assert db_session.query(NSSYieldCurveSpot).count() == spot_count_before
    # Zero for 2024-01-03 must NOT exist either.
    assert db_session.query(NSSYieldCurveZero).count() == zero_count_before


def test_fit_id_unique_constraint(db_session: Session, us_fit_result: NSSFitResult) -> None:
    """fit_id is UNIQUE: two different (country,date) pairs can't share one."""
    persist_nss_fit_result(db_session, us_fit_result)
    other_date = replace(us_fit_result, observation_date=date(2024, 1, 3))
    # Same fit_id reused intentionally — should violate uq_ycs_fit_id.
    with pytest.raises(DuplicatePersistError):
        persist_nss_fit_result(db_session, other_date)


def test_flags_csv_encoding(db_session: Session, us_fit_result: NSSFitResult) -> None:
    """flags tuple → CSV in DB; empty tuple → NULL."""
    persist_nss_fit_result(db_session, us_fit_result)
    spot = db_session.query(NSSYieldCurveSpot).one()
    # us_fit_result fixture has no flags (clean fit) → NULL in DB.
    assert spot.flags is None


def test_source_connector_default_fred(db_session: Session, us_fit_result: NSSFitResult) -> None:
    persist_nss_fit_result(db_session, us_fit_result)
    spot = db_session.query(NSSYieldCurveSpot).one()
    assert spot.source_connector == "fred"


def test_source_connector_override(db_session: Session, us_fit_result: NSSFitResult) -> None:
    persist_nss_fit_result(db_session, us_fit_result, source_connector="treasury_gov")
    spot = db_session.query(NSSYieldCurveSpot).one()
    assert spot.source_connector == "treasury_gov"
