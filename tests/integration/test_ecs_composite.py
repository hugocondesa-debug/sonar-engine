"""ECS composite 7 T1 countries vertical-slice integration test (sprint7-A c6).

Parametrized across the seven Tier-1 countries for a single
``observation_date = 2024-12-31``. Each country gets a synthetic
sub-index seed profile appropriate for its coverage tier:

- **US**: all 4 of (E1, E2, E3, E4) seeded → ECS computes with
  stagflation inputs provided.
- **DE / IT / ES / FR / NL**: all 4 seeded (post-Week 6 Sprint 3
  TE coverage for CB CC + UMich 5Y lifted E4 availability).
- **PT**: E2 + E3 + E4 only (E1 blocked by CAL-094 Eurostat
  namq_10_pe gap) → ECS computes with E1_MISSING + re-weight.
- **UK / JP**: no rows → raises InsufficientCycleInputsError
  (sub-indices pending Week 7+ BoE / BoJ connectors).

Policy 1 edge cases (two-inputs raise, 3-input re-weight confidence
cap, weighted-sum arithmetic) land at the bottom.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import sonar.db.session  # noqa: F401
from sonar.cycles.base import InsufficientCycleInputsError
from sonar.cycles.economic_ecs import (
    MIN_REQUIRED,
    StagflationInputs,
    compute_ecs,
    persist_ecs_result,
)
from sonar.db.models import (
    Base,
    E1Activity,
    E3Labor,
    E4Sentiment,
    EconomicCycleScore,
    IndexValue,
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


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _seed_e1(session: Session, country: str, *, score: float = 55.0) -> None:
    session.add(
        E1Activity(
            country_code=country,
            date=OBS_DATE,
            methodology_version="E1_ACTIVITY_v0.1",
            score_normalized=score,
            score_raw=0.2,
            components_json="{}",
            components_available=6,
            lookback_years=10,
            confidence=0.82,
            source_connectors="FRED",
        )
    )


def _seed_e2(session: Session, country: str, *, value_0_100: float = 54.0) -> None:
    session.add(
        IndexValue(
            index_code="E2_LEADING",
            country_code=country,
            date=OBS_DATE,
            methodology_version="E2_LEADING_SLOPE_v0.1",
            raw_value=0.1,
            zscore_clamped=0.1,
            value_0_100=value_0_100,
            sub_indicators_json=None,
            confidence=0.78,
        )
    )


def _seed_e3(
    session: Session,
    country: str,
    *,
    score: float = 56.0,
    sahm_triggered: int = 0,
) -> None:
    session.add(
        E3Labor(
            country_code=country,
            date=OBS_DATE,
            methodology_version="E3_LABOR_v0.1",
            score_normalized=score,
            score_raw=0.3,
            sahm_triggered=sahm_triggered,
            sahm_value=0.0,
            components_json="{}",
            components_available=8,
            lookback_years=10,
            confidence=0.80,
            source_connectors="FRED",
        )
    )


def _seed_e4(session: Session, country: str, *, score: float = 57.0) -> None:
    session.add(
        E4Sentiment(
            country_code=country,
            date=OBS_DATE,
            methodology_version="E4_SENTIMENT_v0.1",
            score_normalized=score,
            score_raw=0.4,
            components_json="{}",
            components_available=9,
            lookback_years=10,
            confidence=0.78,
            source_connectors="FRED,TE",
        )
    )


def _seed_country(session: Session, country: str) -> None:
    """Seed a per-country profile matching real Phase 0-1 coverage."""
    if country == "US":
        _seed_e1(session, country, score=62.0)
        _seed_e2(session, country, value_0_100=55.0)
        _seed_e3(session, country, score=57.0)
        _seed_e4(session, country, score=58.0)
    elif country in {"DE", "IT", "ES", "FR", "NL"}:
        # Full 4-stack via Eurostat + TE coverage.
        _seed_e1(session, country, score=54.0)
        _seed_e2(session, country, value_0_100=52.0)
        _seed_e3(session, country, score=55.0)
        _seed_e4(session, country, score=53.0)
    elif country == "PT":
        # PT E1 blocked by CAL-094 namq_10_pe gap.
        _seed_e2(session, country, value_0_100=50.0)
        _seed_e3(session, country, score=53.0)
        _seed_e4(session, country, score=52.0)
    elif country in {"UK", "JP"}:
        return
    session.commit()


DEFAULT_SF_INPUTS = StagflationInputs(cpi_yoy=0.025, sahm_triggered=0, unemp_delta=0.001)


# ---------------------------------------------------------------------------
# 7-country parametrized matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("country", "expected_persists", "expected_min_indices"),
    [
        ("US", True, 4),
        ("DE", True, 4),
        ("IT", True, 4),
        ("ES", True, 4),
        ("FR", True, 4),
        ("NL", True, 4),
        ("PT", True, 3),
        ("UK", False, 0),
        ("JP", False, 0),
    ],
)
def test_ecs_per_country(
    db_session: Session,
    country: str,
    expected_persists: bool,
    expected_min_indices: int,
) -> None:
    _seed_country(db_session, country)
    if not expected_persists:
        with pytest.raises(InsufficientCycleInputsError):
            compute_ecs(db_session, country, OBS_DATE, DEFAULT_SF_INPUTS)
        return

    result = compute_ecs(db_session, country, OBS_DATE, DEFAULT_SF_INPUTS)
    assert result.indices_available >= expected_min_indices
    assert 0 <= result.score_0_100 <= 100
    assert result.regime in {
        "EXPANSION",
        "PEAK_ZONE",
        "EARLY_RECESSION",
        "RECESSION",
    }
    # Bootstrap: first row for this country.
    assert result.regime_persistence_days == 1
    assert "REGIME_BOOTSTRAP" in result.flags
    # Weights sum to 1 over available indices.
    total_weight = (
        result.e1_weight_effective
        + result.e2_weight_effective
        + result.e3_weight_effective
        + result.e4_weight_effective
    )
    assert total_weight == pytest.approx(1.0, abs=0.001)

    # PT specifically: E1 missing + re-weight cap.
    if country == "PT":
        assert result.e1_score_0_100 is None
        assert "E1_MISSING" in result.flags
        assert result.confidence <= 0.75

    persist_ecs_result(db_session, result)
    row = db_session.execute(
        select(EconomicCycleScore).where(EconomicCycleScore.country_code == country)
    ).scalar_one()
    assert row.score_0_100 == pytest.approx(result.score_0_100)


# ---------------------------------------------------------------------------
# Policy 1 edge cases
# ---------------------------------------------------------------------------


class TestPolicy1:
    def test_e1_missing_reweights(self, db_session: Session) -> None:
        _seed_e2(db_session, "US", value_0_100=55.0)
        _seed_e3(db_session, "US", score=57.0)
        _seed_e4(db_session, "US", score=58.0)
        db_session.commit()
        result = compute_ecs(db_session, "US", OBS_DATE, DEFAULT_SF_INPUTS)
        assert result.indices_available == 3
        assert "E1_MISSING" in result.flags
        assert result.e1_weight_effective == 0.0
        # Remaining weights re-normalize over (0.25 + 0.25 + 0.15) = 0.65.
        expected_e2_weight = 0.25 / 0.65
        assert result.e2_weight_effective == pytest.approx(expected_e2_weight, abs=0.001)

    def test_two_inputs_raises(self, db_session: Session) -> None:
        _seed_e1(db_session, "US")
        _seed_e3(db_session, "US")
        db_session.commit()
        with pytest.raises(InsufficientCycleInputsError):
            compute_ecs(db_session, "US", OBS_DATE, DEFAULT_SF_INPUTS)

    def test_min_required_constant_is_3(self) -> None:
        assert MIN_REQUIRED == 3

    def test_canonical_weighted_sum(self, db_session: Session) -> None:
        """E1=60 E2=50 E3=40 E4=30 → 0.35·60 + 0.25·50 + 0.25·40 + 0.15·30 = 48.0."""
        _seed_e1(db_session, "US", score=60.0)
        _seed_e2(db_session, "US", value_0_100=50.0)
        _seed_e3(db_session, "US", score=40.0)
        _seed_e4(db_session, "US", score=30.0)
        db_session.commit()
        result = compute_ecs(db_session, "US", OBS_DATE, DEFAULT_SF_INPUTS)
        expected = 0.35 * 60 + 0.25 * 50 + 0.25 * 40 + 0.15 * 30
        assert result.score_0_100 == pytest.approx(expected, abs=0.01)
        assert result.regime == "EARLY_RECESSION"  # 40 ≤ 48 < 55

    def test_stagflation_active_us(self, db_session: Session) -> None:
        """Score < 55 + CPI 5% + Sahm triggered → overlay active."""
        _seed_e1(db_session, "US", score=42.0)
        _seed_e2(db_session, "US", value_0_100=38.0)
        _seed_e3(db_session, "US", score=44.0, sahm_triggered=1)
        _seed_e4(db_session, "US", score=40.0)
        db_session.commit()
        result = compute_ecs(
            db_session,
            "US",
            OBS_DATE,
            StagflationInputs(cpi_yoy=0.05, sahm_triggered=1, unemp_delta=0.005),
        )
        assert result.stagflation_overlay_active == 1
        assert "STAGFLATION_OVERLAY_ACTIVE" in result.flags
        assert result.stagflation_trigger_json is not None
