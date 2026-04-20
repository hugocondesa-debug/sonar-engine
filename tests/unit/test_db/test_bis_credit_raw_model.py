"""Unit tests for BisCreditRaw ORM — in-memory SQLite schema + constraints."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from sonar.db.models import BisCreditRaw

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _row(**overrides: object) -> BisCreditRaw:
    base: dict[str, object] = {
        "country_code": "US",
        "date": date(2024, 6, 30),
        "dataflow": "WS_TC",
        "value_raw": 255.3,
        "unit_descriptor": "pct_gdp",
        "fetch_response_hash": "a" * 64,
    }
    base.update(overrides)
    return BisCreditRaw(**base)  # type: ignore[arg-type]


class TestBisCreditRawSchema:
    def test_insert_and_read_back(self, db_session: Session) -> None:
        db_session.add(_row())
        db_session.commit()
        result = db_session.execute(select(BisCreditRaw)).scalar_one()
        assert result.country_code == "US"
        assert result.dataflow == "WS_TC"
        assert result.value_raw == pytest.approx(255.3)
        assert result.fetched_at is not None  # server default populated

    def test_unique_triplet_violation(self, db_session: Session) -> None:
        db_session.add(_row())
        db_session.commit()
        db_session.add(_row(value_raw=256.0))  # same (country, date, dataflow)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_different_dataflow_allowed(self, db_session: Session) -> None:
        db_session.add(_row(dataflow="WS_TC"))
        db_session.add(_row(dataflow="WS_DSR", value_raw=14.8, unit_descriptor="dsr_pct"))
        db_session.add(_row(dataflow="WS_CREDIT_GAP", value_raw=-2.1, unit_descriptor="gap_pp"))
        db_session.commit()
        rows = db_session.execute(select(BisCreditRaw)).scalars().all()
        assert len(rows) == 3
        dataflows = {r.dataflow for r in rows}
        assert dataflows == {"WS_TC", "WS_DSR", "WS_CREDIT_GAP"}

    def test_invalid_dataflow_rejected(self, db_session: Session) -> None:
        db_session.add(_row(dataflow="WS_INVALID"))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_nullable_hash(self, db_session: Session) -> None:
        db_session.add(_row(fetch_response_hash=None))
        db_session.commit()
        row = db_session.execute(select(BisCreditRaw)).scalar_one()
        assert row.fetch_response_hash is None
