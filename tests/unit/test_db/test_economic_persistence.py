"""Persistence tests for E1/E3/E4 + batch helpers (week7 sprint B C1)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest

from sonar.db.models import (
    E1Activity,
    E3Labor,
    E4Sentiment,
    IndexValue,
)
from sonar.db.persistence import (
    DuplicatePersistError,
    persist_e1_activity_result,
    persist_e3_labor_result,
    persist_e4_sentiment_result,
    persist_many_economic_results,
)
from sonar.indices.base import IndexResult
from sonar.indices.economic.e1_activity import E1ActivityResult
from sonar.indices.economic.e3_labor import E3LaborResult
from sonar.indices.economic.e4_sentiment import E4SentimentResult

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _e1(**overrides: object) -> E1ActivityResult:
    base: dict[str, object] = {
        "country_code": "US",
        "date": date(2024, 12, 31),
        "methodology_version": "E1_ACTIVITY_v1.0",
        "score_normalized": 60.0,
        "score_raw": 0.5,
        "components_json": '{"gdp_yoy": 0.025}',
        "components_available": 5,
        "lookback_years": 20,
        "confidence": 0.8,
        "flags": (),
        "source_connectors": "fred",
    }
    base.update(overrides)
    return E1ActivityResult(**base)  # type: ignore[arg-type]


def _e3(**overrides: object) -> E3LaborResult:
    base: dict[str, object] = {
        "country_code": "US",
        "date": date(2024, 12, 31),
        "methodology_version": "E3_LABOR_v1.0",
        "score_normalized": 55.0,
        "score_raw": 0.1,
        "sahm_triggered": False,
        "sahm_value": 0.2,
        "components_json": '{"unrate": 0.039}',
        "components_available": 8,
        "lookback_years": 20,
        "confidence": 0.85,
        "flags": (),
        "source_connectors": "fred",
    }
    base.update(overrides)
    return E3LaborResult(**base)  # type: ignore[arg-type]


def _e4(**overrides: object) -> E4SentimentResult:
    base: dict[str, object] = {
        "country_code": "US",
        "date": date(2024, 12, 31),
        "methodology_version": "E4_SENTIMENT_v1.0",
        "score_normalized": 65.0,
        "score_raw": 0.3,
        "components_json": '{"umich": 70.0}',
        "components_available": 7,
        "lookback_years": 20,
        "confidence": 0.75,
        "flags": (),
        "source_connectors": "fred,te",
    }
    base.update(overrides)
    return E4SentimentResult(**base)  # type: ignore[arg-type]


def _e2(**overrides: object) -> IndexResult:
    base: dict[str, object] = {
        "index_code": "E2",
        "country_code": "US",
        "date": date(2024, 12, 31),
        "methodology_version": "E2_LEADING_v1.0",
        "raw_value": 0.012,
        "zscore_clamped": 0.8,
        "value_0_100": 63.4,
        "confidence": 0.78,
        "flags": (),
        "sub_indicators": {"slope_pp": 0.12},
        "source_overlays": {"overlay": "nss"},
    }
    base.update(overrides)
    return IndexResult(**base)  # type: ignore[arg-type]


class TestPersistE1:
    def test_happy_path(self, db_session: Session) -> None:
        persist_e1_activity_result(db_session, _e1())
        row = db_session.query(E1Activity).one()
        assert row.score_normalized == pytest.approx(60.0)

    def test_duplicate_raises(self, db_session: Session) -> None:
        persist_e1_activity_result(db_session, _e1())
        with pytest.raises(DuplicatePersistError, match="E1 row already persisted"):
            persist_e1_activity_result(db_session, _e1())


class TestPersistE3:
    def test_happy_path_sahm_false(self, db_session: Session) -> None:
        persist_e3_labor_result(db_session, _e3())
        row = db_session.query(E3Labor).one()
        assert row.sahm_triggered == 0

    def test_happy_path_sahm_true(self, db_session: Session) -> None:
        persist_e3_labor_result(db_session, _e3(sahm_triggered=True))
        row = db_session.query(E3Labor).one()
        assert row.sahm_triggered == 1

    def test_duplicate_raises(self, db_session: Session) -> None:
        persist_e3_labor_result(db_session, _e3())
        with pytest.raises(DuplicatePersistError, match="E3 row already persisted"):
            persist_e3_labor_result(db_session, _e3())


class TestPersistE4:
    def test_happy_path(self, db_session: Session) -> None:
        persist_e4_sentiment_result(db_session, _e4())
        row = db_session.query(E4Sentiment).one()
        assert row.source_connectors == "fred,te"

    def test_duplicate_raises(self, db_session: Session) -> None:
        persist_e4_sentiment_result(db_session, _e4())
        with pytest.raises(DuplicatePersistError, match="E4 row already persisted"):
            persist_e4_sentiment_result(db_session, _e4())


class TestPersistManyEconomic:
    def test_all_four_in_single_tx(self, db_session: Session) -> None:
        written = persist_many_economic_results(db_session, e1=_e1(), e2=_e2(), e3=_e3(), e4=_e4())
        assert written == {"e1": 1, "e2": 1, "e3": 1, "e4": 1}
        assert db_session.query(E1Activity).count() == 1
        assert db_session.query(E3Labor).count() == 1
        assert db_session.query(E4Sentiment).count() == 1
        assert db_session.query(IndexValue).count() == 1

    def test_partial_subset_ok(self, db_session: Session) -> None:
        written = persist_many_economic_results(db_session, e1=_e1(), e3=_e3())
        assert written["e1"] == 1
        assert written["e3"] == 1
        assert written["e2"] == 0
        assert written["e4"] == 0

    def test_empty_returns_zeros(self, db_session: Session) -> None:
        assert persist_many_economic_results(db_session) == {"e1": 0, "e2": 0, "e3": 0, "e4": 0}

    def test_duplicate_rolls_back_entire_batch(self, db_session: Session) -> None:
        persist_e1_activity_result(db_session, _e1())
        with pytest.raises(DuplicatePersistError, match="Batch economic persist"):
            persist_many_economic_results(db_session, e1=_e1(), e3=_e3())
        # E3 must NOT have been persisted due to rollback.
        assert db_session.query(E3Labor).count() == 0
