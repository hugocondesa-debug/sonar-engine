"""Unit tests for the L5MetaRegime ORM + migration 017."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import sonar.db.session  # noqa: F401 — activates FK=ON connect listener
from sonar.db.models import (
    Base,
    CreditCycleScore,
    EconomicCycleScore,
    FinancialCycleScore,
    L5MetaRegime,
    MonetaryCycleScore,
)

ANCHOR = date(2024, 12, 31)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_cycle_parents(session: Session) -> tuple[str, str, str, str]:
    """Seed one row per L4 cycle so the L5 FKs resolve; return the 4 ids."""
    ecs_id = str(uuid4())
    cccs_id = str(uuid4())
    fcs_id = str(uuid4())
    msc_id = str(uuid4())
    session.add(
        EconomicCycleScore(
            ecs_id=ecs_id,
            country_code="US",
            date=ANCHOR,
            methodology_version="ECS_v1.0",
            score_0_100=55.0,
            regime="EXPANSION",
            regime_persistence_days=5,
            e1_weight_effective=0.35,
            e2_weight_effective=0.25,
            e3_weight_effective=0.25,
            e4_weight_effective=0.15,
            indices_available=4,
            stagflation_overlay_active=0,
            confidence=0.85,
        )
    )
    session.add(
        CreditCycleScore(
            cccs_id=cccs_id,
            country_code="US",
            date=ANCHOR,
            methodology_version="CCCS_v1.0",
            score_0_100=60.0,
            regime="RECOVERY",
            regime_persistence_days=5,
            cs_weight_effective=0.3,
            lc_weight_effective=0.3,
            ms_weight_effective=0.3,
            components_available=4,
            boom_overlay_active=0,
            confidence=0.85,
        )
    )
    session.add(
        FinancialCycleScore(
            fcs_id=fcs_id,
            country_code="US",
            date=ANCHOR,
            methodology_version="FCS_v1.0",
            score_0_100=62.0,
            regime="OPTIMISM",
            regime_persistence_days=5,
            f1_weight_effective=0.3,
            f2_weight_effective=0.2,
            f3_weight_effective=0.3,
            f4_weight_effective=0.2,
            indices_available=4,
            country_tier=1,
            bubble_warning_active=0,
            confidence=0.85,
        )
    )
    session.add(
        MonetaryCycleScore(
            msc_id=msc_id,
            country_code="US",
            date=ANCHOR,
            methodology_version="MSC_v1.0",
            score_0_100=58.0,
            regime_6band="NEUTRAL_TIGHT",
            regime_3band="NEUTRAL",
            regime_persistence_days=5,
            m1_weight_effective=0.33,
            m2_weight_effective=0.17,
            m3_weight_effective=0.28,
            m4_weight_effective=0.22,
            cs_weight_effective=0.0,
            inputs_available=4,
            dilemma_overlay_active=0,
            confidence=0.85,
        )
    )
    session.commit()
    return ecs_id, cccs_id, fcs_id, msc_id


def _l5_row(
    ecs_id: str | None,
    cccs_id: str | None,
    fcs_id: str | None,
    msc_id: str | None,
    *,
    meta_regime: str = "soft_landing",
    l5_id: str | None = None,
) -> L5MetaRegime:
    return L5MetaRegime(
        l5_id=l5_id or str(uuid4()),
        country_code="US",
        date=ANCHOR,
        methodology_version="L5_META_REGIME_v0.1",
        meta_regime=meta_regime,
        ecs_id=ecs_id,
        cccs_id=cccs_id,
        fcs_id=fcs_id,
        msc_id=msc_id,
        confidence=0.85,
        flags="L5_SOFT_LANDING",
        classification_reason="expansion+neutral",
    )


def test_table_created(session: Session) -> None:
    insp = inspect(session.bind)
    assert "l5_meta_regimes" in insp.get_table_names()


def test_orm_roundtrip_all_fks_populated(session: Session) -> None:
    ecs_id, cccs_id, fcs_id, msc_id = _seed_cycle_parents(session)
    row = _l5_row(ecs_id, cccs_id, fcs_id, msc_id)
    session.add(row)
    session.commit()
    loaded = session.execute(select(L5MetaRegime)).scalar_one()
    assert loaded.country_code == "US"
    assert loaded.meta_regime == "soft_landing"
    assert loaded.ecs_id == ecs_id


def test_orm_accepts_nullable_fks(session: Session) -> None:
    """Policy 1 3/4 cycles → some FKs may be None."""
    _, cccs_id, fcs_id, msc_id = _seed_cycle_parents(session)
    row = _l5_row(None, cccs_id, fcs_id, msc_id, meta_regime="unclassified")
    session.add(row)
    session.commit()
    loaded = session.execute(select(L5MetaRegime)).scalar_one()
    assert loaded.ecs_id is None
    assert loaded.cccs_id == cccs_id


def test_check_constraint_rejects_unknown_meta_regime(session: Session) -> None:
    ecs_id, cccs_id, fcs_id, msc_id = _seed_cycle_parents(session)
    bad = _l5_row(ecs_id, cccs_id, fcs_id, msc_id, meta_regime="not_a_regime")
    session.add(bad)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_uniqueness_on_country_date_methodology(session: Session) -> None:
    ecs_id, cccs_id, fcs_id, msc_id = _seed_cycle_parents(session)
    first = _l5_row(ecs_id, cccs_id, fcs_id, msc_id)
    session.add(first)
    session.commit()
    second = _l5_row(ecs_id, cccs_id, fcs_id, msc_id)
    session.add(second)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_confidence_bounds_enforced(session: Session) -> None:
    ecs_id, cccs_id, fcs_id, msc_id = _seed_cycle_parents(session)
    row = _l5_row(ecs_id, cccs_id, fcs_id, msc_id)
    row.confidence = 1.5
    session.add(row)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
