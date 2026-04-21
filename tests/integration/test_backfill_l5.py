"""Sprint M C5 — backfill_l5 end-to-end integration smoke.

Seeds realistic multi-country / multi-date L4 state, runs the backfill
script via its public entry point, and asserts idempotency +
insufficient-row handling.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sonar.db.session  # noqa: F401
from sonar.db.models import (
    Base,
    L5MetaRegime,
)
from sonar.scripts.backfill_l5 import backfill_country
from tests.unit.test_scripts.test_backfill_l5 import (
    _seed_cccs,
    _seed_ecs,
    _seed_fcs,
    _seed_full_stack,
    _seed_msc,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.orm import Session


pytestmark = pytest.mark.slow


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


# ---------------------------------------------------------------------------
# Happy path — multi-date backfill
# ---------------------------------------------------------------------------


class TestBackfillHappyPath:
    def test_multi_date_execute_persists_all(self, db_session: Session) -> None:
        dates = [date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 29)]
        for d in dates:
            _seed_full_stack(db_session, country="US", d=d)

        report = backfill_country(db_session, "US", dry_run=False)
        assert report.eligible == 3
        assert report.persisted == 3
        assert report.skipped_insufficient == 0
        assert db_session.query(L5MetaRegime).count() == 3

    def test_dry_run_persists_zero(self, db_session: Session) -> None:
        for d in (date(2024, 6, 28), date(2024, 7, 31)):
            _seed_full_stack(db_session, country="US", d=d)

        report = backfill_country(db_session, "US", dry_run=True)
        assert report.classified == 2
        assert report.persisted == 0
        assert db_session.query(L5MetaRegime).count() == 0

    def test_idempotent_second_run_is_noop(self, db_session: Session) -> None:
        _seed_full_stack(db_session, country="US", d=date(2024, 12, 31))

        first = backfill_country(db_session, "US", dry_run=False)
        assert first.persisted == 1

        second = backfill_country(db_session, "US", dry_run=False)
        assert second.eligible == 0
        assert second.persisted == 0
        assert db_session.query(L5MetaRegime).count() == 1

    def test_from_date_filter_excludes_older(self, db_session: Session) -> None:
        _seed_full_stack(db_session, country="US", d=date(2023, 12, 31))
        _seed_full_stack(db_session, country="US", d=date(2024, 6, 30))
        _seed_full_stack(db_session, country="US", d=date(2024, 12, 31))

        report = backfill_country(db_session, "US", from_date=date(2024, 1, 1), dry_run=False)
        assert report.persisted == 2
        assert {r.date for r in db_session.query(L5MetaRegime).all()} == {
            date(2024, 6, 30),
            date(2024, 12, 31),
        }


# ---------------------------------------------------------------------------
# Insufficient L4 — classifier raises, counter increments, no rows
# ---------------------------------------------------------------------------


class TestInsufficientHandling:
    def test_only_two_cycles_counted_as_insufficient(self, db_session: Session) -> None:
        d = date(2024, 12, 31)
        _seed_ecs(db_session, country="US", d=d)
        _seed_fcs(db_session, country="US", d=d)
        db_session.commit()

        report = backfill_country(db_session, "US", dry_run=False)
        assert report.eligible == 1
        assert report.skipped_insufficient == 1
        assert report.persisted == 0
        assert db_session.query(L5MetaRegime).count() == 0

    def test_mixed_dates_some_sufficient_some_not(self, db_session: Session) -> None:
        sufficient_date = date(2024, 1, 31)
        partial_date = date(2024, 2, 29)
        _seed_full_stack(db_session, country="US", d=sufficient_date)
        _seed_ecs(db_session, country="US", d=partial_date)
        _seed_cccs(db_session, country="US", d=partial_date)
        db_session.commit()

        report = backfill_country(db_session, "US", dry_run=False)
        assert report.eligible == 2
        assert report.persisted == 1
        assert report.skipped_insufficient == 1
        rows = db_session.query(L5MetaRegime).all()
        assert len(rows) == 1
        assert rows[0].date == sufficient_date


# ---------------------------------------------------------------------------
# Multi-country scoping
# ---------------------------------------------------------------------------


class TestMultiCountry:
    def test_per_country_counter_populated(self, db_session: Session) -> None:
        _seed_full_stack(db_session, country="US", d=date(2024, 12, 31))
        _seed_full_stack(db_session, country="DE", d=date(2024, 12, 31))
        _seed_full_stack(db_session, country="DE", d=date(2024, 11, 29))

        report = backfill_country(db_session, "US", dry_run=False)
        report = backfill_country(db_session, "DE", dry_run=False, report=report)

        assert report.persisted == 3
        assert report.per_country == {"US": 1, "DE": 2}
        # Counts separate by country.
        assert db_session.query(L5MetaRegime).filter(L5MetaRegime.country_code == "US").count() == 1
        assert db_session.query(L5MetaRegime).filter(L5MetaRegime.country_code == "DE").count() == 2


# Silence unused-helper warnings.
_ = _seed_msc  # imported via test_backfill_l5 but only used transitively
