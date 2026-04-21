"""Unit tests for daily_cycles pipeline (week7 sprint D C3)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import sonar.db.session  # noqa: F401
from sonar.cycles.economic_ecs import StagflationInputs
from sonar.db.models import (
    Base,
    CreditCycleScore,
    EconomicCycleScore,
    FinancialCycleScore,
    L5MetaRegime,
    MonetaryCycleScore,
)
from sonar.pipelines.daily_cycles import (
    EXIT_IO,
    EXIT_NO_INPUTS,
    EXIT_OK,
    T1_7_COUNTRIES,
    CyclesPipelineOutcome,
    _classify_and_persist_l5,
    count_persisted,
    default_stagflation_resolver,
    main,
    run_one,
)
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


def _seed_all_four_cycles(session: Session, country: str = "US") -> None:
    """Seed sub-inputs so every cycle computes cleanly."""
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


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_t1_set_matches_spec() -> None:
    assert T1_7_COUNTRIES == ("US", "DE", "PT", "IT", "ES", "FR", "NL")


def test_exit_codes() -> None:
    assert EXIT_OK == 0
    assert EXIT_NO_INPUTS == 1
    assert EXIT_IO == 4


def test_default_resolver_returns_none(db_session: Session) -> None:
    assert default_stagflation_resolver(db_session, "US", OBS_DATE) is None


# ---------------------------------------------------------------------------
# count_persisted
# ---------------------------------------------------------------------------


class TestCountPersisted:
    def test_all_four_present(self) -> None:
        # Use a minimal fake result object with non-None fields.
        class _R:
            pass

        result = _R()
        result.cccs = object()
        result.fcs = object()
        result.msc = object()
        result.ecs = object()
        counts = count_persisted(result)  # type: ignore[arg-type]
        assert counts == {"cccs": 1, "fcs": 1, "msc": 1, "ecs": 1}

    def test_all_none_counts_zero(self) -> None:
        class _R:
            cccs = None
            fcs = None
            msc = None
            ecs = None

        assert count_persisted(_R()) == {"cccs": 0, "fcs": 0, "msc": 0, "ecs": 0}  # type: ignore[arg-type]

    def test_partial(self) -> None:
        class _R:
            cccs = object()
            fcs = None
            msc = object()
            ecs = None

        assert count_persisted(_R()) == {"cccs": 1, "fcs": 0, "msc": 1, "ecs": 0}  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# run_one
# ---------------------------------------------------------------------------


class TestRunOne:
    def test_full_stack_us_persists_all_four(self, db_session: Session) -> None:
        _seed_all_four_cycles(db_session)
        outcome = run_one(
            db_session,
            "US",
            OBS_DATE,
            stagflation_resolver=lambda *_: StagflationInputs(
                cpi_yoy=0.025, sahm_triggered=0, unemp_delta=0.001
            ),
        )
        assert isinstance(outcome, CyclesPipelineOutcome)
        assert outcome.orchestration.cccs is not None
        assert outcome.orchestration.fcs is not None
        assert outcome.orchestration.msc is not None
        assert outcome.orchestration.ecs is not None
        assert outcome.persisted == {"cccs": 1, "fcs": 1, "msc": 1, "ecs": 1}
        assert outcome.orchestration.skips == {}
        # One row per cycle table.
        assert len(db_session.execute(select(CreditCycleScore)).scalars().all()) == 1
        assert len(db_session.execute(select(FinancialCycleScore)).scalars().all()) == 1
        assert len(db_session.execute(select(MonetaryCycleScore)).scalars().all()) == 1
        assert len(db_session.execute(select(EconomicCycleScore)).scalars().all()) == 1

    def test_empty_db_persists_nothing(self, db_session: Session) -> None:
        outcome = run_one(db_session, "PT", OBS_DATE)
        assert outcome.persisted == {"cccs": 0, "fcs": 0, "msc": 0, "ecs": 0}
        assert set(outcome.orchestration.skips.keys()) == {"CCCS", "FCS", "MSC", "ECS"}

    def test_only_ecs_inputs_persists_ecs(self, db_session: Session) -> None:
        _seed_ecs_e1(db_session, observation_date=OBS_DATE)
        _seed_ecs_e2(db_session, observation_date=OBS_DATE)
        _seed_ecs_e3(db_session, observation_date=OBS_DATE)
        _seed_ecs_e4(db_session, observation_date=OBS_DATE)
        db_session.commit()
        outcome = run_one(
            db_session,
            "US",
            OBS_DATE,
            stagflation_resolver=lambda *_: StagflationInputs(
                cpi_yoy=0.025, sahm_triggered=0, unemp_delta=0.001
            ),
        )
        assert outcome.persisted == {"cccs": 0, "fcs": 0, "msc": 0, "ecs": 1}
        assert outcome.orchestration.ecs is not None

    def test_default_resolver_wires_stagflation_inputs_missing(self, db_session: Session) -> None:
        """No resolver → ECS emits STAGFLATION_INPUT_MISSING per spec §6."""
        _seed_ecs_e1(db_session, observation_date=OBS_DATE)
        _seed_ecs_e2(db_session, observation_date=OBS_DATE)
        _seed_ecs_e3(db_session, observation_date=OBS_DATE)
        _seed_ecs_e4(db_session, observation_date=OBS_DATE)
        db_session.commit()
        outcome = run_one(db_session, "US", OBS_DATE)
        assert outcome.orchestration.ecs is not None
        assert "STAGFLATION_INPUT_MISSING" in outcome.orchestration.ecs.flags


# ---------------------------------------------------------------------------
# L5 wiring (Sprint K C2)
# ---------------------------------------------------------------------------


class TestL5Wiring:
    def test_full_stack_classifies_and_persists_l5(self, db_session: Session) -> None:
        """4/4 L4 cycles → L5 classified + persisted."""
        _seed_all_four_cycles(db_session)
        outcome = run_one(
            db_session,
            "US",
            OBS_DATE,
            stagflation_resolver=lambda *_: StagflationInputs(
                cpi_yoy=0.025, sahm_triggered=0, unemp_delta=0.001
            ),
        )
        assert outcome.l5_result is not None
        assert outcome.l5_skip_reason is None
        assert outcome.l5_result.methodology_version == "L5_META_REGIME_v0.1"
        # Persisted row exists.
        rows = db_session.execute(select(L5MetaRegime)).scalars().all()
        assert len(rows) == 1
        assert rows[0].country_code == "US"
        assert rows[0].date == OBS_DATE

    def test_only_ecs_triggers_l5_insufficient_skip(self, db_session: Session) -> None:
        """1/4 L4 cycle (ECS only) → L5 InsufficientL4DataError → soft skip."""
        _seed_ecs_e1(db_session, observation_date=OBS_DATE)
        _seed_ecs_e2(db_session, observation_date=OBS_DATE)
        _seed_ecs_e3(db_session, observation_date=OBS_DATE)
        _seed_ecs_e4(db_session, observation_date=OBS_DATE)
        db_session.commit()
        outcome = run_one(
            db_session,
            "US",
            OBS_DATE,
            stagflation_resolver=lambda *_: StagflationInputs(
                cpi_yoy=0.025, sahm_triggered=0, unemp_delta=0.001
            ),
        )
        # ECS persisted, L5 absent because Policy 1 (>= 3/4) not met.
        assert outcome.orchestration.ecs is not None
        assert outcome.l5_result is None
        assert outcome.l5_skip_reason is not None
        assert "1/4" in outcome.l5_skip_reason
        # Zero L5 rows persisted.
        assert db_session.execute(select(L5MetaRegime)).scalars().all() == []

    def test_rerun_l5_duplicate_handled_gracefully(self, db_session: Session) -> None:
        """Re-running same (country, date) surfaces DuplicatePersistError as skip."""
        _seed_all_four_cycles(db_session)

        def _resolver(*_: object) -> StagflationInputs:
            return StagflationInputs(cpi_yoy=0.025, sahm_triggered=0, unemp_delta=0.001)

        first = run_one(db_session, "US", OBS_DATE, stagflation_resolver=_resolver)
        assert first.l5_result is not None
        # A full L4 re-run would raise DuplicatePersistError in the cycles
        # orchestrator; here we only exercise the L5 duplicate path by
        # calling the classifier helper directly on a fresh orchestration.
        l5_retry, skip_reason = _classify_and_persist_l5(
            db_session, "US", OBS_DATE, first.orchestration
        )
        # Result still returned (classifier succeeded); persist raised
        # DuplicatePersistError which was swallowed into skip_reason.
        assert l5_retry is not None
        assert skip_reason is not None
        assert "duplicate" in skip_reason.lower()
        # Still exactly one L5 row in the DB.
        assert len(db_session.execute(select(L5MetaRegime)).scalars().all()) == 1


# ---------------------------------------------------------------------------
# CLI main()
# ---------------------------------------------------------------------------


class TestCLI:
    def test_invalid_date_exits_io(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with pytest.raises(SystemExit) as exc:
            main(country="US", target_date="not-a-date", all_t1=False)
        assert exc.value.code == EXIT_IO

    def test_no_country_no_all_t1_exits_io(self) -> None:
        with pytest.raises(SystemExit) as exc:
            main(country="", target_date="2024-12-31", all_t1=False)
        assert exc.value.code == EXIT_IO

    def test_unknown_backend_exits_io(self) -> None:
        with pytest.raises(SystemExit) as exc:
            main(country="US", target_date="2024-12-31", backend="bogus")
        assert exc.value.code == EXIT_IO

    def test_live_backend_without_key_exits_io(self) -> None:
        with pytest.raises(SystemExit) as exc:
            main(country="US", target_date="2024-12-31", backend="live", fred_api_key="")
        assert exc.value.code == EXIT_IO
