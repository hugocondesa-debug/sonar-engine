"""Tests for persist_l5_meta_regime_result (Week 8 Sprint H)."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
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
from sonar.db.persistence import DuplicatePersistError, persist_l5_meta_regime_result
from sonar.regimes.types import L5RegimeResult, MetaRegime

ANCHOR = date(2024, 12, 31)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_parents(session: Session) -> tuple[str, str, str, str]:
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


def _result(
    *,
    ecs_id: str | None,
    cccs_id: str | None,
    fcs_id: str | None,
    msc_id: str | None,
    meta_regime: MetaRegime = MetaRegime.SOFT_LANDING,
    flags: tuple[str, ...] = ("L5_SOFT_LANDING",),
) -> L5RegimeResult:
    return L5RegimeResult(
        country_code="US",
        date=ANCHOR,
        meta_regime=meta_regime,
        ecs_id=ecs_id,
        cccs_id=cccs_id,
        fcs_id=fcs_id,
        msc_id=msc_id,
        confidence=0.85,
        flags=flags,
        classification_reason="expansion+neutral",
    )


def test_happy_path_persists_row(session: Session) -> None:
    ecs_id, cccs_id, fcs_id, msc_id = _seed_parents(session)
    persist_l5_meta_regime_result(
        session,
        _result(ecs_id=ecs_id, cccs_id=cccs_id, fcs_id=fcs_id, msc_id=msc_id),
    )
    row = session.execute(select(L5MetaRegime)).scalar_one()
    assert row.country_code == "US"
    assert row.meta_regime == "soft_landing"
    assert row.flags == "L5_SOFT_LANDING"
    assert row.classification_reason == "expansion+neutral"
    assert row.methodology_version == "L5_META_REGIME_v0.1"


def test_duplicate_raises(session: Session) -> None:
    ecs_id, cccs_id, fcs_id, msc_id = _seed_parents(session)
    payload = _result(ecs_id=ecs_id, cccs_id=cccs_id, fcs_id=fcs_id, msc_id=msc_id)
    persist_l5_meta_regime_result(session, payload)
    with pytest.raises(DuplicatePersistError, match="L5 row already persisted"):
        persist_l5_meta_regime_result(session, payload)


def test_nullable_fks_persist(session: Session) -> None:
    """3/4 cycles → ECS slot None still persists via nullable FK."""
    _, cccs_id, fcs_id, msc_id = _seed_parents(session)
    persist_l5_meta_regime_result(
        session,
        _result(
            ecs_id=None,
            cccs_id=cccs_id,
            fcs_id=fcs_id,
            msc_id=msc_id,
            meta_regime=MetaRegime.UNCLASSIFIED,
            flags=("L5_UNCLASSIFIED", "L5_ECS_MISSING"),
        ),
    )
    row = session.execute(select(L5MetaRegime)).scalar_one()
    assert row.ecs_id is None
    assert row.cccs_id == cccs_id
    assert row.flags == "L5_UNCLASSIFIED,L5_ECS_MISSING"


def test_empty_flags_round_trip(session: Session) -> None:
    ecs_id, cccs_id, fcs_id, msc_id = _seed_parents(session)
    persist_l5_meta_regime_result(
        session,
        _result(
            ecs_id=ecs_id,
            cccs_id=cccs_id,
            fcs_id=fcs_id,
            msc_id=msc_id,
            flags=(),
        ),
    )
    row = session.execute(select(L5MetaRegime)).scalar_one()
    assert row.flags is None
