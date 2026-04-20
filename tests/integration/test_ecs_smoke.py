"""ECS US end-to-end smoke with scorecard (sprint7-A c7).

Seeds a plausible 2024-12-31 US snapshot (mid-cycle soft-landing:
E1 activity ~60, E2 leading flat, E3 labor firm, E4 sentiment near
long-run mean; CPI ~2.6%, Sahm=0, unemp Δ ~0.2pp) and runs
``compute_ecs`` + ``persist_ecs_result`` end-to-end. Marked
``@pytest.mark.slow`` so default CI skips.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sonar.db.session  # noqa: F401
from sonar.cycles.economic_ecs import (
    StagflationInputs,
    compute_ecs,
    persist_ecs_result,
)
from sonar.db.models import (
    Base,
    E1Activity,
    E3Labor,
    E4Sentiment,
    IndexValue,
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


def _seed_soft_landing_us(session: Session) -> None:
    """US 2024-12-31 snapshot: soft-landing mid-cycle."""
    session.add(
        E1Activity(
            country_code="US",
            date=OBS_DATE,
            methodology_version="E1_ACTIVITY_v0.1",
            score_normalized=60.0,
            score_raw=0.5,
            components_json="{}",
            components_available=6,
            lookback_years=10,
            confidence=0.85,
            source_connectors="FRED",
        )
    )
    session.add(
        IndexValue(
            index_code="E2_LEADING",
            country_code="US",
            date=OBS_DATE,
            methodology_version="E2_LEADING_SLOPE_v0.1",
            raw_value=0.05,
            zscore_clamped=0.05,
            value_0_100=52.0,
            sub_indicators_json=None,
            confidence=0.78,
        )
    )
    session.add(
        E3Labor(
            country_code="US",
            date=OBS_DATE,
            methodology_version="E3_LABOR_v0.1",
            score_normalized=58.0,
            score_raw=0.35,
            sahm_triggered=0,
            sahm_value=0.0,
            components_json="{}",
            components_available=9,
            lookback_years=10,
            confidence=0.82,
            source_connectors="FRED",
        )
    )
    session.add(
        E4Sentiment(
            country_code="US",
            date=OBS_DATE,
            methodology_version="E4_SENTIMENT_v0.1",
            score_normalized=55.0,
            score_raw=0.25,
            components_json="{}",
            components_available=9,
            lookback_years=10,
            confidence=0.80,
            source_connectors="FRED,TE",
        )
    )
    session.commit()


def test_ecs_us_smoke(db_session: Session) -> None:
    """End-to-end: compute + persist ECS for US 2024-12-31 soft-landing."""
    _seed_soft_landing_us(db_session)
    result = compute_ecs(
        db_session,
        "US",
        OBS_DATE,
        StagflationInputs(cpi_yoy=0.026, sahm_triggered=0, unemp_delta=0.002),
    )

    print(  # noqa: T201 — scorecard is the deliverable for the retro
        "\nECS US 2024-12-31 scorecard:\n"
        f"  score_0_100          = {result.score_0_100:.2f}\n"
        f"  regime               = {result.regime}\n"
        f"  regime_persistence   = {result.regime_persistence_days} days\n"
        f"  indices_available    = {result.indices_available}/4\n"
        f"  effective weights    = E1 {result.e1_weight_effective:.3f} / "
        f"E2 {result.e2_weight_effective:.3f} / "
        f"E3 {result.e3_weight_effective:.3f} / "
        f"E4 {result.e4_weight_effective:.3f}\n"
        f"  confidence           = {result.confidence:.2f}\n"
        f"  stagflation_overlay  = {result.stagflation_overlay_active}\n"
        f"  flags                = {result.flags}"
    )

    # Core contract.
    assert 0 <= result.score_0_100 <= 100
    assert result.regime in {
        "EXPANSION",
        "PEAK_ZONE",
        "EARLY_RECESSION",
        "RECESSION",
    }
    assert result.indices_available == 4
    # Canonical arithmetic: 0.35·60 + 0.25·52 + 0.25·58 + 0.15·55
    # = 21 + 13 + 14.5 + 8.25 = 56.75 → PEAK_ZONE.
    assert result.score_0_100 == pytest.approx(56.75, abs=0.1)
    assert result.regime == "PEAK_ZONE"
    assert result.regime_persistence_days == 1
    assert "REGIME_BOOTSTRAP" in result.flags
    # Stagflation: CPI 2.6% < 3% threshold → overlay inactive.
    assert result.stagflation_overlay_active == 0
    # Full 4/4 stack → no Policy 1 re-weight cap; min-conf 0.78 · 4/4 = 0.78.
    assert result.confidence >= 0.60

    persist_ecs_result(db_session, result)
