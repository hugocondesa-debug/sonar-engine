"""Unit tests for cycles orchestrator."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import sonar.db.session  # noqa: F401
from sonar.cycles.orchestrator import compute_all_cycles
from sonar.db.models import Base, CreditCycleScore, FinancialCycleScore

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.orm import Session

from tests.unit.test_cycles.test_credit_cccs import _seed_sub_rows as _seed_cccs_inputs
from tests.unit.test_cycles.test_financial_fcs import _seed_f_rows as _seed_fcs_inputs


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


def _seed_full_stack(
    session: Session, country: str = "US", observation_date: date = date(2024, 1, 31)
) -> None:
    """Seed both CCCS + FCS inputs without double-seeding F3/F4."""
    _seed_cccs_inputs(session, country=country, observation_date=observation_date)
    # CCCS seed already added F3 + F4 at observation_date — FCS seed only
    # needs F1/F2 (F3/F4 are reused from CCCS).
    _seed_fcs_inputs(
        session,
        country=country,
        observation_date=observation_date,
        f3=None,
        f4=None,
    )


class TestOrchestrator:
    def test_full_stack_us_produces_both(self, db_session: Session) -> None:
        _seed_full_stack(db_session)
        outcome = compute_all_cycles(db_session, "US", date(2024, 1, 31))
        assert outcome.cccs is not None
        assert outcome.fcs is not None
        assert outcome.skips == {}
        cccs_rows = db_session.execute(select(CreditCycleScore)).scalars().all()
        fcs_rows = db_session.execute(select(FinancialCycleScore)).scalars().all()
        assert len(cccs_rows) == 1
        assert len(fcs_rows) == 1

    def test_missing_credit_inputs_skips_cccs(self, db_session: Session) -> None:
        # Only FCS inputs seeded — CCCS should raise
        # InsufficientCycleInputsError and orchestrator records the skip.
        _seed_fcs_inputs(db_session, country="US", observation_date=date(2024, 1, 31))
        outcome = compute_all_cycles(db_session, "US", date(2024, 1, 31))
        assert outcome.cccs is None
        assert "CCCS" in outcome.skips
        assert outcome.fcs is not None

    def test_t1_country_missing_f4_skips_fcs(self, db_session: Session) -> None:
        # CCCS inputs seeded with margin_debt_pct=None (no F4 rows seeded)
        # → CCCS falls back to 100% F3 for MS component; FCS cannot find
        # F4 for US Tier 1 → raises and orchestrator records skip.
        _seed_cccs_inputs(
            db_session,
            country="US",
            observation_date=date(2024, 1, 31),
            margin_debt_pct=None,
        )
        _seed_fcs_inputs(
            db_session,
            country="US",
            observation_date=date(2024, 1, 31),
            f3=None,  # F3 reused from CCCS seed
            f4=None,
        )
        outcome = compute_all_cycles(db_session, "US", date(2024, 1, 31))
        assert outcome.cccs is not None
        assert outcome.fcs is None
        assert "FCS" in outcome.skips
        assert "Tier-1" in outcome.skips["FCS"]

    def test_persist_false_keeps_db_clean(self, db_session: Session) -> None:
        _seed_full_stack(db_session)
        outcome = compute_all_cycles(db_session, "US", date(2024, 1, 31), persist=False)
        assert outcome.cccs is not None
        assert outcome.fcs is not None
        assert db_session.execute(select(CreditCycleScore)).scalars().all() == []
        assert db_session.execute(select(FinancialCycleScore)).scalars().all() == []

    def test_partial_missing_returns_both_skips(self, db_session: Session) -> None:
        # Nothing seeded — both skip.
        outcome = compute_all_cycles(db_session, "PT", date(2024, 1, 31))
        assert outcome.cccs is None
        assert outcome.fcs is None
        assert set(outcome.skips.keys()) == {"CCCS", "FCS"}
