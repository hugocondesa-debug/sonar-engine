"""Sprint K C4 — end-to-end L4 → L5 → sonar status vertical slice.

Exercises the full stack with an in-memory SQLite DB:

1. Seed L3 sub-index rows for ``US 2024-12-31`` (E1-E4 + M1-M4 + F1-F4
   + CCCS sub-rows) via the per-cycle test seeders that Sprint D/A
   already shipped in the unit suite.
2. Invoke :func:`sonar.pipelines.daily_cycles.run_one` → L4 compute +
   persist + L5 classify + persist.
3. Verify L4 + L5 rows in the DB.
4. Call :func:`sonar.cli.status.get_country_status` → verify
   ``CountryStatus.l5_meta_regime`` populated.
5. Render summary + verbose + matrix; assert the regime label is in
   the output.
6. 2/4-cycles case: pipeline exits cleanly, L5 absent, sonar status
   shows N/A.
7. Duplicate rerun: L5 DuplicatePersistError handled gracefully.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from io import StringIO
from typing import TYPE_CHECKING

import pytest
from rich.console import Console
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import sonar.db.session  # noqa: F401
from sonar.cli.status import (
    format_matrix,
    format_status_summary,
    format_status_verbose,
    get_country_status,
)
from sonar.cycles.economic_ecs import StagflationInputs
from sonar.db.models import (
    Base,
    CreditCycleScore,
    EconomicCycleScore,
    FinancialCycleScore,
    L5MetaRegime,
    MonetaryCycleScore,
)
from sonar.pipelines.daily_cycles import _classify_and_persist_l5, run_one
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

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.orm import Session


pytestmark = pytest.mark.slow


OBS_DATE = date(2024, 12, 31)


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


def _seed_all_l3(session: Session, country: str = "US") -> None:
    _seed_cccs_inputs(session, country=country, observation_date=OBS_DATE)
    _seed_fcs_inputs(session, country=country, observation_date=OBS_DATE, f3=None, f4=None)
    _seed_msc_m1(session, country_code=country, observation_date=OBS_DATE)
    _seed_msc_m2(session, country_code=country, observation_date=OBS_DATE)
    _seed_msc_m3(session, country_code=country, observation_date=OBS_DATE)
    _seed_msc_m4(session, country_code=country, observation_date=OBS_DATE)
    _seed_ecs_e1(session, country_code=country, observation_date=OBS_DATE)
    _seed_ecs_e2(session, country_code=country, observation_date=OBS_DATE)
    _seed_ecs_e3(session, country_code=country, observation_date=OBS_DATE)
    _seed_ecs_e4(session, country_code=country, observation_date=OBS_DATE)
    session.commit()


def _render(table: object) -> str:
    buf = StringIO()
    Console(file=buf, force_terminal=False, no_color=False, width=200).print(table)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Full vertical slice — happy path
# ---------------------------------------------------------------------------


class TestVerticalSliceUS:
    def test_l3_seed_to_l5_to_status_display(self, db_session: Session) -> None:
        # Step 1-2: seed L3, run daily_cycles (triggers L4 + L5).
        _seed_all_l3(db_session, "US")
        outcome = run_one(
            db_session,
            "US",
            OBS_DATE,
            stagflation_resolver=lambda *_: StagflationInputs(
                cpi_yoy=0.025, sahm_triggered=0, unemp_delta=0.001
            ),
        )

        # Step 3: L4 + L5 rows persisted.
        assert db_session.execute(select(CreditCycleScore)).scalars().all()
        assert db_session.execute(select(FinancialCycleScore)).scalars().all()
        assert db_session.execute(select(MonetaryCycleScore)).scalars().all()
        assert db_session.execute(select(EconomicCycleScore)).scalars().all()
        l5_rows = db_session.execute(select(L5MetaRegime)).scalars().all()
        assert len(l5_rows) == 1
        assert outcome.l5_result is not None
        assert outcome.l5_skip_reason is None

        # Step 4: sonar status query returns populated L5.
        status = get_country_status(db_session, "US", OBS_DATE, now=datetime.now(tz=UTC))
        assert status.l5_meta_regime is not None
        assert status.l5_meta_regime.meta_regime == str(outcome.l5_result.meta_regime)

        # Step 5: summary + verbose + matrix render the meta-regime.
        summary = _render(format_status_summary(status))
        assert "Meta-Regime" in summary
        assert status.l5_meta_regime.meta_regime in summary

        verbose = _render(format_status_verbose(status))
        assert "reason=" in verbose

        matrix = _render(format_matrix([status]))
        assert "L5" in matrix
        assert status.l5_meta_regime.meta_regime in matrix


# ---------------------------------------------------------------------------
# Insufficient L4 → L5 skip; pipeline survives
# ---------------------------------------------------------------------------


class TestInsufficientL4:
    def test_only_ecs_no_l5_row_status_displays_na(self, db_session: Session) -> None:
        _seed_ecs_e1(db_session, country_code="US", observation_date=OBS_DATE)
        _seed_ecs_e2(db_session, country_code="US", observation_date=OBS_DATE)
        _seed_ecs_e3(db_session, country_code="US", observation_date=OBS_DATE)
        _seed_ecs_e4(db_session, country_code="US", observation_date=OBS_DATE)
        db_session.commit()

        outcome = run_one(
            db_session,
            "US",
            OBS_DATE,
            stagflation_resolver=lambda *_: StagflationInputs(
                cpi_yoy=0.025, sahm_triggered=0, unemp_delta=0.001
            ),
        )
        assert outcome.l5_result is None
        assert outcome.l5_skip_reason is not None
        assert db_session.execute(select(L5MetaRegime)).scalars().all() == []

        # sonar status: L4 ECS present + L5 N/A.
        status = get_country_status(db_session, "US", OBS_DATE, now=datetime.now(tz=UTC))
        assert status.ecs is not None
        assert status.l5_meta_regime is None
        summary = _render(format_status_summary(status))
        assert "N/A" in summary


# ---------------------------------------------------------------------------
# Duplicate rerun idempotent
# ---------------------------------------------------------------------------


class TestDuplicateRerun:
    def test_rerun_l5_handled_gracefully(self, db_session: Session) -> None:
        _seed_all_l3(db_session, "US")
        resolver = lambda *_: StagflationInputs(  # noqa: E731 — inline builder
            cpi_yoy=0.025, sahm_triggered=0, unemp_delta=0.001
        )
        first = run_one(db_session, "US", OBS_DATE, stagflation_resolver=resolver)
        assert first.l5_result is not None
        # Re-run the classifier helper directly (full run_one would raise
        # DuplicatePersistError from the L4 persist step before reaching
        # the L5 block).
        l5_retry, skip_reason = _classify_and_persist_l5(
            db_session, "US", OBS_DATE, first.orchestration
        )
        assert l5_retry is not None
        assert skip_reason is not None
        assert "duplicate" in skip_reason.lower()
        # Still exactly one L5 row.
        rows = db_session.execute(select(L5MetaRegime)).scalars().all()
        assert len(rows) == 1
