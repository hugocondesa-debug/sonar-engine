"""Tests for ``sonar health`` (Week 7 Sprint G)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import sonar.db.session  # noqa: F401 — activates FK=ON connect listener
from sonar.cli.health import (
    PIPELINE_TO_TABLE,
    NullAlertSink,
    PipelineHealth,
    _classify,
    collect_pipeline_health,
    format_health_report,
)
from sonar.db.models import Base

NOW = datetime(2024, 12, 31, 12, 0, tzinfo=UTC)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_e1_row(session: Session, created_at: datetime, country: str = "US") -> None:
    session.execute(
        text(
            "INSERT INTO idx_economic_e1_activity "
            "(country_code, date, methodology_version, score_normalized, score_raw, "
            "components_json, components_available, lookback_years, confidence, "
            "flags, source_connectors, created_at) "
            "VALUES (:c, :d, 'E1_v1.0', 55.0, 0.1, '{}', 5, 20, 0.8, NULL, 'fred', :ts)"
        ),
        {"c": country, "d": date(2024, 12, 31).isoformat(), "ts": created_at.isoformat()},
    )
    session.commit()


def test_classify_fresh() -> None:
    assert _classify(NOW - timedelta(hours=1), now=NOW) == "fresh"


def test_classify_stale() -> None:
    assert _classify(NOW - timedelta(hours=48), now=NOW) == "stale"


def test_classify_missing_via_old_timestamp() -> None:
    assert _classify(NOW - timedelta(days=7), now=NOW) == "missing"


def test_classify_missing_when_none() -> None:
    assert _classify(None, now=NOW) == "missing"


def test_pipeline_map_covers_all_domains() -> None:
    names = set(PIPELINE_TO_TABLE)
    assert any("cycles" in n for n in names)
    assert any("economic" in n for n in names)
    assert any("monetary" in n for n in names)
    assert any("financial" in n for n in names)
    assert any("credit" in n for n in names)


def test_collect_pipeline_health_empty_db(session: Session) -> None:
    healths = collect_pipeline_health(session, now=NOW)
    assert len(healths) == len(PIPELINE_TO_TABLE)
    # All existing tables are empty → last_run_timestamp is None, status missing.
    for h in healths:
        assert h.last_run_timestamp is None
        assert h.freshness_status == "missing"
        assert h.rows_total == 0


def test_collect_pipeline_health_classifies_fresh(session: Session) -> None:
    _seed_e1_row(session, created_at=NOW - timedelta(hours=2))
    healths = {h.pipeline_name: h for h in collect_pipeline_health(session, now=NOW)}
    e1 = healths["daily_economic_indices (E1)"]
    assert e1.freshness_status == "fresh"
    assert e1.rows_total == 1


def test_collect_pipeline_health_classifies_stale(session: Session) -> None:
    _seed_e1_row(session, created_at=NOW - timedelta(hours=48))
    healths = {h.pipeline_name: h for h in collect_pipeline_health(session, now=NOW)}
    assert healths["daily_economic_indices (E1)"].freshness_status == "stale"


def test_country_filter(session: Session) -> None:
    _seed_e1_row(session, created_at=NOW - timedelta(hours=2), country="US")
    _seed_e1_row(session, created_at=NOW - timedelta(hours=2), country="DE")
    healths_us = {
        h.pipeline_name: h for h in collect_pipeline_health(session, country_code="US", now=NOW)
    }
    assert healths_us["daily_economic_indices (E1)"].rows_total == 1


def test_format_health_report_returns_rich_table() -> None:
    healths = [
        PipelineHealth(
            pipeline_name="daily_curves",
            table_name="yield_curves_spot",
            last_run_timestamp=NOW - timedelta(hours=1),
            freshness_status="fresh",
            rows_total=10,
        ),
    ]
    table = format_health_report(healths)
    assert table.title == "SONAR pipeline health"
    assert len(table.columns) == 5


def test_null_alert_sink_noop() -> None:
    sink = NullAlertSink()
    # No return value; no exception.
    assert sink.emit("info", "test message") is None
