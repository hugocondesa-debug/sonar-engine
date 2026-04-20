"""Tests for ``persist_index_value`` + ``persist_many_index_values``.

Uses an in-memory SQLite + a single migration-equivalent create_all to
materialize the polymorphic ``index_values`` table without going
through alembic on every test run.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from sonar.db.models import Base, IndexValue
from sonar.db.persistence import (
    DuplicatePersistError,
    persist_index_value,
    persist_many_index_values,
)
from sonar.indices.base import IndexResult


def _result(
    *,
    index_code: str = "E2_LEADING",
    country: str = "US",
    d: date = date(2024, 1, 2),
    methodology: str = "E2_LEADING_SLOPE_v0.1",
    value: float = 42.5,
) -> IndexResult:
    return IndexResult(
        index_code=index_code,
        country_code=country,
        date=d,
        methodology_version=methodology,
        raw_value=-38.0,
        zscore_clamped=-0.45,
        value_0_100=value,
        sub_indicators={"slope_10y_2y_bps": -38},
        confidence=0.85,
        flags=("SLOPE_INVERTED",),
        source_overlays={"nss": country},
    )


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def test_persist_single_row(session: Session) -> None:
    persist_index_value(session, _result())
    rows = session.query(IndexValue).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.index_code == "E2_LEADING"
    assert row.country_code == "US"
    assert row.value_0_100 == pytest.approx(42.5)
    assert row.flags == "SLOPE_INVERTED"
    assert '"slope_10y_2y_bps"' in (row.sub_indicators_json or "")


def test_persist_duplicate_raises(session: Session) -> None:
    persist_index_value(session, _result())
    with pytest.raises(DuplicatePersistError, match="already persisted"):
        persist_index_value(session, _result())


def test_persist_many_single_transaction(session: Session) -> None:
    results = [
        _result(index_code="E2_LEADING", country="US"),
        _result(index_code="E2_LEADING", country="DE"),
        _result(index_code="M3_MARKET_EXPECTATIONS", country="US"),
    ]
    n = persist_many_index_values(session, results)
    assert n == 3
    assert session.query(IndexValue).count() == 3


def test_persist_many_empty_returns_zero(session: Session) -> None:
    assert persist_many_index_values(session, []) == 0
    assert session.query(IndexValue).count() == 0


def test_persist_many_rolls_back_on_duplicate(session: Session) -> None:
    persist_index_value(session, _result(country="US"))
    batch = [
        _result(country="DE"),
        _result(country="US"),  # duplicate
    ]
    with pytest.raises(DuplicatePersistError):
        persist_many_index_values(session, batch)
    # Verify rollback: only the first single-row insert remains.
    assert session.query(IndexValue).count() == 1


def test_value_range_check_enforced(session: Session) -> None:
    bad = _result(value=150.0)
    with pytest.raises(IntegrityError, match="ck_iv_value_range"):
        persist_index_value(session, bad)
