"""Integration smoke for the ``sonar`` CLI (Week 7 Sprint G C6).

Exercises the four Sprint-G CLI commands end-to-end via Typer's
``CliRunner`` against an in-memory SQLite seeded with realistic
fixtures:

- ``sonar status --country US --date 2024-12-31``
- ``sonar status --all-t1``
- ``sonar health``
- ``sonar retention run --dry-run``

These are pipeline-orchestration smokes (no external network), but
kept under ``@pytest.mark.slow`` to stay consistent with the other
integration modules.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from typer.testing import CliRunner

import sonar.db.session  # noqa: F401 — activates FK=ON connect listener
from sonar.cli.health import app as health_app
from sonar.cli.status import app as status_app
from sonar.db.models import Base
from sonar.scripts.retention import app as retention_app

pytestmark = pytest.mark.slow


ANCHOR = date(2024, 12, 31)
NOW = datetime(2024, 12, 31, 12, 0, tzinfo=UTC)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def patched_session_local(tmp_path) -> Session:  # type: ignore[no-untyped-def]
    """Install an in-memory SessionLocal and seed fixtures."""
    engine = create_engine(f"sqlite:///{tmp_path}/sonar.db", future=True)
    Base.metadata.create_all(engine)
    session = Session(engine)
    # Seed minimum fixtures for the 3 CLI paths below.
    _seed_ecs(session, country="US", score=55.0)
    _seed_ecs(session, country="DE", score=52.0)
    # bis_credit_raw row older than 10Y so retention can report it.
    session.execute(
        text(
            "INSERT INTO bis_credit_raw "
            "(country_code, date, dataflow, value_raw, unit_descriptor) "
            "VALUES ('US', :d, 'WS_TC', 100.0, 'pct_gdp')"
        ),
        {"d": (ANCHOR - timedelta(days=365 * 12)).isoformat()},
    )
    session.commit()
    # Patch SessionLocal so the CLI callbacks open this engine.
    patches = [
        patch("sonar.cli.status.SessionLocal", lambda: Session(engine)),
        patch("sonar.cli.health.SessionLocal", lambda: Session(engine)),
        patch("sonar.scripts.retention.SessionLocal", lambda: Session(engine)),
    ]
    for p in patches:
        p.start()
    yield session
    for p in patches:
        p.stop()
    session.close()


def _seed_ecs(session: Session, country: str, score: float) -> None:
    session.execute(
        text(
            "INSERT INTO economic_cycle_scores "
            "(ecs_id, country_code, date, methodology_version, score_0_100, regime, "
            "regime_persistence_days, "
            "e1_score_0_100, e2_score_0_100, e3_score_0_100, e4_score_0_100, "
            "e1_weight_effective, e2_weight_effective, e3_weight_effective, e4_weight_effective, "
            "indices_available, stagflation_overlay_active, "
            "confidence, flags, created_at) "
            "VALUES (:id, :c, :d, 'ECS_v1.0', :s, 'EXPANSION', 5, 58.0, 55.0, 50.0, 60.0, "
            "0.35, 0.25, 0.25, 0.15, 4, 0, 0.85, NULL, :ts)"
        ),
        {
            "id": f"ecs-{country}",
            "c": country,
            "d": ANCHOR.isoformat(),
            "s": score,
            "ts": NOW.isoformat(),
        },
    )


def test_sonar_status_us_with_fixtures(runner: CliRunner, patched_session_local: Session) -> None:
    result = runner.invoke(status_app, ["--country", "US", "--date", ANCHOR.isoformat()])
    assert result.exit_code == 0, result.stdout
    # ECS row landed → EXPANSION regime renders in the table.
    assert "ECS" in result.stdout
    assert "EXPANSION" in result.stdout


def test_sonar_status_all_t1_matrix(runner: CliRunner, patched_session_local: Session) -> None:
    result = runner.invoke(status_app, ["--all-t1"])
    assert result.exit_code == 0, result.stdout
    # Matrix columns: Country + 4 cycles.
    assert "US" in result.stdout
    assert "DE" in result.stdout
    # Countries without seeded rows show N/A markers.
    assert "N/A" in result.stdout


def test_sonar_status_missing_flags_errors(runner: CliRunner) -> None:
    result = runner.invoke(status_app, [])
    # Missing both --country and --all-t1 → EXIT_IO (4).
    assert result.exit_code == 4


def test_sonar_health_lists_all_pipelines(
    runner: CliRunner, patched_session_local: Session
) -> None:
    result = runner.invoke(health_app, [])
    assert result.exit_code == 0, result.stdout
    # Every pipeline registered in PIPELINE_TO_TABLE appears in the output.
    assert "daily_curves" in result.stdout
    assert "daily_cycles" in result.stdout


def test_sonar_retention_dry_run_reports_count(
    runner: CliRunner, patched_session_local: Session
) -> None:
    result = runner.invoke(retention_app, ["run"])
    assert result.exit_code == 0, result.stdout
    assert "DRY-RUN" in result.stdout
    # The fixture seeded 1 BIS row older than 10Y → total should be ≥ 1.
    assert "bis_credit_raw: 1 rows" in result.stdout


def test_sonar_retention_execute_deletes(runner: CliRunner, patched_session_local: Session) -> None:
    result = runner.invoke(retention_app, ["run", "--execute"])
    assert result.exit_code == 0, result.stdout
    assert "EXECUTED" in result.stdout
