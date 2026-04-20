"""Unit tests for cycles orchestrator."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import sonar.db.session  # noqa: F401
from sonar.cycles.economic_ecs import StagflationInputs
from sonar.cycles.orchestrator import compute_all_cycles
from sonar.db.models import (
    Base,
    CreditCycleScore,
    EconomicCycleScore,
    FinancialCycleScore,
    MonetaryCycleScore,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.orm import Session

from tests.unit.test_cycles.test_credit_cccs import _seed_sub_rows as _seed_cccs_inputs
from tests.unit.test_cycles.test_economic_ecs import (
    _seed_e1 as _seed_ecs_e1,
    _seed_e2 as _seed_ecs_e2,
    _seed_e3 as _seed_ecs_e3,
    _seed_e4 as _seed_ecs_e4,
)
from tests.unit.test_cycles.test_financial_fcs import _seed_f_rows as _seed_fcs_inputs
from tests.unit.test_cycles.test_monetary_msc import (
    _seed_m1 as _seed_msc_m1,
    _seed_m2 as _seed_msc_m2,
    _seed_m3 as _seed_msc_m3,
    _seed_m4 as _seed_msc_m4,
)


def _seed_msc_inputs(
    session: Session, country: str = "US", observation_date: date = date(2024, 1, 31)
) -> None:
    _seed_msc_m1(session, country_code=country, observation_date=observation_date)
    _seed_msc_m2(session, country_code=country, observation_date=observation_date)
    _seed_msc_m3(session, country_code=country, observation_date=observation_date)
    _seed_msc_m4(session, country_code=country, observation_date=observation_date)
    session.commit()


def _seed_ecs_inputs(
    session: Session, country: str = "US", observation_date: date = date(2024, 1, 31)
) -> None:
    _seed_ecs_e1(session, country_code=country, observation_date=observation_date)
    _seed_ecs_e2(session, country_code=country, observation_date=observation_date)
    _seed_ecs_e3(session, country_code=country, observation_date=observation_date)
    _seed_ecs_e4(session, country_code=country, observation_date=observation_date)
    session.commit()


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
        # MSC is absent here (no M* seeds) — orchestrator records the skip
        # but continues. Remaining cycles still persist.
        assert "CCCS" not in outcome.skips
        assert "FCS" not in outcome.skips
        assert "MSC" in outcome.skips
        assert "ECS" in outcome.skips
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

    def test_partial_missing_returns_four_skips(self, db_session: Session) -> None:
        # Nothing seeded — all four cycles skip.
        outcome = compute_all_cycles(db_session, "PT", date(2024, 1, 31))
        assert outcome.cccs is None
        assert outcome.fcs is None
        assert outcome.msc is None
        assert outcome.ecs is None
        assert set(outcome.skips.keys()) == {"CCCS", "FCS", "MSC", "ECS"}

    def test_full_stack_with_msc_produces_three_ecs_skipped(self, db_session: Session) -> None:
        _seed_full_stack(db_session)
        _seed_msc_inputs(db_session)
        outcome = compute_all_cycles(db_session, "US", date(2024, 1, 31))
        assert outcome.cccs is not None
        assert outcome.fcs is not None
        assert outcome.msc is not None
        # ECS skips because E-indices not seeded.
        assert outcome.ecs is None
        assert set(outcome.skips.keys()) == {"ECS"}
        msc_rows = db_session.execute(select(MonetaryCycleScore)).scalars().all()
        assert len(msc_rows) == 1

    def test_msc_only_skips_when_sub_indices_absent(self, db_session: Session) -> None:
        # Seed only MSC sub-indices → CCCS + FCS + ECS skip; MSC produces a row.
        _seed_msc_inputs(db_session)
        outcome = compute_all_cycles(db_session, "US", date(2024, 1, 31))
        assert outcome.cccs is None
        assert outcome.fcs is None
        assert outcome.msc is not None
        assert outcome.ecs is None
        assert set(outcome.skips.keys()) == {"CCCS", "FCS", "ECS"}

    def test_ecs_standalone_with_all_e_indices(self, db_session: Session) -> None:
        """Seed only E-indices → only ECS produces a row (the others skip)."""
        _seed_ecs_inputs(db_session)
        outcome = compute_all_cycles(
            db_session,
            "US",
            date(2024, 1, 31),
            ecs_stagflation_inputs=StagflationInputs(
                cpi_yoy=0.02, sahm_triggered=0, unemp_delta=0.001
            ),
        )
        assert outcome.ecs is not None
        assert outcome.cccs is None
        assert outcome.fcs is None
        assert outcome.msc is None
        assert set(outcome.skips.keys()) == {"CCCS", "FCS", "MSC"}
        ecs_rows = db_session.execute(select(EconomicCycleScore)).scalars().all()
        assert len(ecs_rows) == 1

    def test_full_four_cycles_us(self, db_session: Session) -> None:
        """US with CCCS + FCS + MSC + ECS inputs all seeded → 4/4 L4 cycles."""
        _seed_full_stack(db_session)
        _seed_msc_inputs(db_session)
        _seed_ecs_inputs(db_session)
        outcome = compute_all_cycles(
            db_session,
            "US",
            date(2024, 1, 31),
            ecs_stagflation_inputs=StagflationInputs(
                cpi_yoy=0.02, sahm_triggered=0, unemp_delta=0.001
            ),
        )
        assert outcome.cccs is not None
        assert outcome.fcs is not None
        assert outcome.msc is not None
        assert outcome.ecs is not None
        assert outcome.skips == {}
