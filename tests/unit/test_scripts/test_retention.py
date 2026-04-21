"""Tests for retention policies + VACUUM helper (Week 7 Sprint G)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import sonar.db.session  # noqa: F401 — activates FK=ON connect listener
from sonar.db.models import Base
from sonar.scripts.retention import (
    RETENTION_POLICIES,
    TablePolicy,
    apply_retention,
    vacuum_sqlite,
)

ANCHOR = date(2024, 12, 31)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_bis_row(session: Session, obs_date: date, country: str = "US") -> None:
    session.execute(
        text(
            "INSERT INTO bis_credit_raw "
            "(country_code, date, dataflow, value_raw, unit_descriptor) "
            "VALUES (:c, :d, 'WS_TC', 100.0, 'pct_gdp')"
        ),
        {"c": country, "d": obs_date.isoformat()},
    )


def test_policies_cover_the_four_raw_tables() -> None:
    names = {p.table_name for p in RETENTION_POLICIES}
    assert names == {
        "bis_credit_raw",
        "yield_curves_spot",
        "yield_curves_forwards",
        "ratings_agency_raw",
    }


def test_policies_keep_years_sensible() -> None:
    for policy in RETENTION_POLICIES:
        assert 1 <= policy.keep_years <= 50


def test_dry_run_counts_without_deleting(session: Session) -> None:
    # Seed 3 BIS rows: 1 within 10Y window, 2 older.
    _seed_bis_row(session, ANCHOR)
    _seed_bis_row(session, ANCHOR - timedelta(days=365 * 12))
    _seed_bis_row(session, ANCHOR - timedelta(days=365 * 11))
    session.commit()

    report = apply_retention(session, dry_run=True, today=ANCHOR)
    assert report.executed is False
    assert report.per_table["bis_credit_raw"] == 2
    # No actual delete.
    remaining = session.execute(text("SELECT COUNT(*) FROM bis_credit_raw")).scalar_one()
    assert remaining == 3


def test_execute_deletes_rows_outside_window(session: Session) -> None:
    _seed_bis_row(session, ANCHOR)
    _seed_bis_row(session, ANCHOR - timedelta(days=365 * 12))
    session.commit()

    report = apply_retention(session, dry_run=False, today=ANCHOR)
    assert report.executed is True
    assert report.per_table["bis_credit_raw"] == 1
    remaining = session.execute(text("SELECT COUNT(*) FROM bis_credit_raw")).scalar_one()
    assert remaining == 1


def test_empty_policy_returns_empty_report(session: Session) -> None:
    report = apply_retention(session, dry_run=True, today=ANCHOR, policies=())
    assert report.executed is False
    assert report.per_table == {}
    assert report.total_rows == 0


def test_missing_table_is_skipped(session: Session) -> None:
    ghost_policy = (TablePolicy(table_name="does_not_exist", date_column="date", keep_years=1),)
    report = apply_retention(session, dry_run=True, today=ANCHOR, policies=ghost_policy)
    assert "does_not_exist" in report.skipped
    assert "missing" in report.skipped["does_not_exist"]


def test_vacuum_sqlite_runs_cleanly(session: Session) -> None:
    before, after = vacuum_sqlite(session)
    # In-memory DB returns 0 for both — the helper still runs without error.
    assert before == 0
    assert after == 0


def test_total_rows_aggregates_across_policies(session: Session) -> None:
    _seed_bis_row(session, ANCHOR - timedelta(days=365 * 12))
    _seed_bis_row(session, ANCHOR - timedelta(days=365 * 13))
    session.commit()

    report = apply_retention(session, dry_run=True, today=ANCHOR)
    # Our fixture only seeds bis_credit_raw; the other tables are empty so
    # their counts are zero.
    assert report.per_table.get("bis_credit_raw") == 2
    assert report.per_table.get("yield_curves_spot") == 0
    assert report.total_rows == 2
