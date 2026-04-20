"""Unit tests for E1/E3/E4 ORM schema + constraints (week5 c1)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from sonar.db.models import E1Activity, E3Labor, E4Sentiment

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class TestE1Activity:
    def _row(self, **overrides: object) -> E1Activity:
        base: dict[str, object] = {
            "country_code": "US",
            "date": date(2024, 1, 31),
            "methodology_version": "E1_ACTIVITY_v0.1",
            "score_normalized": 58.0,
            "score_raw": 0.48,
            "components_json": "{}",
            "components_available": 6,
            "lookback_years": 10,
            "confidence": 0.9,
            "flags": None,
            "source_connectors": "fred",
        }
        base.update(overrides)
        return E1Activity(**base)  # type: ignore[arg-type]

    def test_insert_and_read_back(self, db_session: Session) -> None:
        db_session.add(self._row())
        db_session.commit()
        row = db_session.execute(select(E1Activity)).scalar_one()
        assert row.score_normalized == pytest.approx(58.0)
        assert row.components_available == 6

    def test_score_out_of_range_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(score_normalized=101.0))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_components_below_min_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(components_available=3))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_unique_cdm(self, db_session: Session) -> None:
        db_session.add(self._row())
        db_session.commit()
        db_session.add(self._row(score_normalized=60.0))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


class TestE3Labor:
    def _row(self, **overrides: object) -> E3Labor:
        base: dict[str, object] = {
            "country_code": "US",
            "date": date(2024, 1, 31),
            "methodology_version": "E3_LABOR_v0.1",
            "score_normalized": 62.0,
            "score_raw": 0.72,
            "sahm_triggered": 0,
            "sahm_value": 0.32,
            "components_json": "{}",
            "components_available": 10,
            "lookback_years": 10,
            "confidence": 0.95,
            "flags": None,
            "source_connectors": "fred",
        }
        base.update(overrides)
        return E3Labor(**base)  # type: ignore[arg-type]

    def test_insert_and_sahm_triggered_field(self, db_session: Session) -> None:
        db_session.add(self._row(sahm_triggered=1, sahm_value=0.55))
        db_session.commit()
        row = db_session.execute(select(E3Labor)).scalar_one()
        assert row.sahm_triggered == 1
        assert row.sahm_value == pytest.approx(0.55)

    def test_sahm_triggered_out_of_range_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(sahm_triggered=2))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_components_6_10_range(self, db_session: Session) -> None:
        db_session.add(self._row(components_available=6))
        db_session.commit()
        assert (
            db_session.execute(select(E3Labor).where(E3Labor.components_available == 6))
            .scalar_one()
            .components_available
            == 6
        )

    def test_components_below_6_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(components_available=5))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


class TestE4Sentiment:
    def _row(self, **overrides: object) -> E4Sentiment:
        base: dict[str, object] = {
            "country_code": "US",
            "date": date(2024, 1, 31),
            "methodology_version": "E4_SENTIMENT_v0.1",
            "score_normalized": 52.0,
            "score_raw": 0.12,
            "components_json": "{}",
            "components_available": 10,
            "lookback_years": 10,
            "confidence": 0.85,
            "flags": None,
            "source_connectors": "fred,eurostat",
        }
        base.update(overrides)
        return E4Sentiment(**base)  # type: ignore[arg-type]

    def test_insert_and_read_back(self, db_session: Session) -> None:
        db_session.add(self._row())
        db_session.commit()
        assert db_session.execute(
            select(E4Sentiment)
        ).scalar_one().score_normalized == pytest.approx(52.0)

    def test_components_13_upper_bound_accepted(self, db_session: Session) -> None:
        db_session.add(self._row(components_available=13))
        db_session.commit()

    def test_components_above_13_rejected(self, db_session: Session) -> None:
        db_session.add(self._row(components_available=14))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


class TestMethodologyVersions:
    """Cross-module sanity: scaffold constants match ORM rows by convention."""

    def test_e1_version_matches_row_default(self) -> None:
        from sonar.indices.economic import E1_METHODOLOGY_VERSION  # noqa: PLC0415

        assert E1_METHODOLOGY_VERSION == "E1_ACTIVITY_v0.1"

    def test_e3_version_matches_row_default(self) -> None:
        from sonar.indices.economic import E3_METHODOLOGY_VERSION  # noqa: PLC0415

        assert E3_METHODOLOGY_VERSION == "E3_LABOR_v0.1"

    def test_e4_version_matches_row_default(self) -> None:
        from sonar.indices.economic import E4_METHODOLOGY_VERSION  # noqa: PLC0415

        assert E4_METHODOLOGY_VERSION == "E4_SENTIMENT_v0.1"
