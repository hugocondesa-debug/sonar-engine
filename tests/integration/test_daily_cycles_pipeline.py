"""Daily cycles pipeline 7-T1 vertical-slice integration (sprint7-D c4).

Parametrized sweep across the 7 Tier-1 countries at
``observation_date = 2024-12-31``. Each country seeds a coverage
profile consistent with Phase 0-1 real-world availability and runs
the full ``run_one`` pipeline, then asserts row-per-table parity
with ``orchestration.persisted``.

Coverage tiers (matches per-cycle integration tests shipped earlier):

- **US**: seeds the full stack (CCCS + FCS + MSC + ECS sub-inputs) →
  4/4 rows persist.
- **DE / IT / ES / FR / NL**: seed ECS E1-E4 full stack via Eurostat +
  TE coverage. CCCS / FCS / MSC degraded per spec; asserts the
  ECS path persists and the others land in ``skips``.
- **PT**: seeds ECS E2 + E3 + E4 (E1 blocked by CAL-094 gap) → 3/4
  ECS inputs; re-weights + E1_MISSING flag emitted.
"""

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
    MonetaryCycleScore,
)
from sonar.pipelines.daily_cycles import run_one
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
DEFAULT_SF = StagflationInputs(cpi_yoy=0.025, sahm_triggered=0, unemp_delta=0.001)


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


def _seed_full_stack(session: Session, country: str) -> None:
    """Seed inputs for every cycle family (CCCS + FCS + MSC + ECS)."""
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


def _seed_ecs_full(session: Session, country: str) -> None:
    _seed_ecs_e1(session, country_code=country, observation_date=OBS_DATE)
    _seed_ecs_e2(session, country_code=country, observation_date=OBS_DATE)
    _seed_ecs_e3(session, country_code=country, observation_date=OBS_DATE)
    _seed_ecs_e4(session, country_code=country, observation_date=OBS_DATE)
    session.commit()


def _seed_ecs_pt(session: Session) -> None:
    # PT: E1 gap (CAL-094).
    _seed_ecs_e2(session, country_code="PT", observation_date=OBS_DATE)
    _seed_ecs_e3(session, country_code="PT", observation_date=OBS_DATE)
    _seed_ecs_e4(session, country_code="PT", observation_date=OBS_DATE)
    session.commit()


def _seed_country(session: Session, country: str) -> None:
    if country == "US":
        _seed_full_stack(session, country)
    elif country in {"DE", "IT", "ES", "FR", "NL"}:
        _seed_ecs_full(session, country)
    elif country == "PT":
        _seed_ecs_pt(session)


# ---------------------------------------------------------------------------
# 7-country parametrized matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("country", "expected_ecs_persists", "expected_full_stack"),
    [
        ("US", True, True),
        ("DE", True, False),
        ("IT", True, False),
        ("ES", True, False),
        ("FR", True, False),
        ("NL", True, False),
        ("PT", True, False),
    ],
)
def test_daily_cycles_per_country(
    db_session: Session,
    country: str,
    expected_ecs_persists: bool,
    expected_full_stack: bool,
) -> None:
    _seed_country(db_session, country)
    outcome = run_one(
        db_session,
        country,
        OBS_DATE,
        stagflation_resolver=lambda *_: DEFAULT_SF,
    )

    assert (outcome.persisted["ecs"] == 1) is expected_ecs_persists
    if expected_full_stack:
        assert outcome.persisted == {"cccs": 1, "fcs": 1, "msc": 1, "ecs": 1}
        assert outcome.orchestration.skips == {}
    else:
        # ECS persists but CCCS/FCS/MSC skip (no sub-inputs seeded for
        # those families in EA/PT fixtures).
        assert outcome.persisted["cccs"] == 0
        assert outcome.persisted["fcs"] == 0
        assert outcome.persisted["msc"] == 0
        assert {"CCCS", "FCS", "MSC"}.issubset(set(outcome.orchestration.skips.keys()))

    # ECS row present + regime classified.
    if expected_ecs_persists:
        ecs_rows = (
            db_session.execute(
                select(EconomicCycleScore).where(EconomicCycleScore.country_code == country)
            )
            .scalars()
            .all()
        )
        assert len(ecs_rows) == 1
        assert ecs_rows[0].regime in {
            "EXPANSION",
            "PEAK_ZONE",
            "EARLY_RECESSION",
            "RECESSION",
        }


# ---------------------------------------------------------------------------
# End-to-end — US 4/4 cycles + row shape
# ---------------------------------------------------------------------------


class TestEndToEndUS:
    def test_us_4_of_4_cycles(self, db_session: Session) -> None:
        _seed_full_stack(db_session, "US")
        outcome = run_one(
            db_session,
            "US",
            OBS_DATE,
            stagflation_resolver=lambda *_: DEFAULT_SF,
        )
        assert outcome.persisted == {"cccs": 1, "fcs": 1, "msc": 1, "ecs": 1}
        # Each cycle table now holds exactly one row for US 2024-12-31.
        for model in (
            CreditCycleScore,
            FinancialCycleScore,
            MonetaryCycleScore,
            EconomicCycleScore,
        ):
            rows = (
                db_session.execute(
                    select(model).where(model.country_code == "US")  # type: ignore[attr-defined]
                )
                .scalars()
                .all()
            )
            assert len(rows) == 1
            assert rows[0].methodology_version.endswith("v0.1")

    def test_pt_ecs_only_with_e1_missing_flag(self, db_session: Session) -> None:
        _seed_ecs_pt(db_session)
        outcome = run_one(
            db_session,
            "PT",
            OBS_DATE,
            stagflation_resolver=lambda *_: DEFAULT_SF,
        )
        assert outcome.persisted["ecs"] == 1
        assert outcome.orchestration.ecs is not None
        assert "E1_MISSING" in outcome.orchestration.ecs.flags
        assert outcome.orchestration.ecs.indices_available == 3
        # Policy 1 cap → confidence ≤ 0.75.
        assert outcome.orchestration.ecs.confidence <= 0.75
