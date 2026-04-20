"""Unit tests for MSC compute — isolated helpers + end-to-end with DB."""

from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import sonar.db.session  # noqa: F401
from sonar.cycles.base import InsufficientCycleInputsError
from sonar.cycles.monetary_msc import (
    CANONICAL_WEIGHTS,
    DILEMMA_MSC_THRESHOLD,
    METHODOLOGY_VERSION,
    MIN_INPUTS,
    REGIME_TRANSITION_DELTA_MIN,
    TOTAL_INPUTS,
    apply_hysteresis,
    classify_regime_3band,
    classify_regime_6band,
    compute_msc,
    persist_msc_result,
)
from sonar.db.models import (
    Base,
    IndexValue,
    M1EffectiveRatesResult,
    M2TaylorGapsResult,
    M4FciResult,
    MonetaryCycleScore,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.orm import Session


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


def _seed_m1(
    session: Session,
    country_code: str = "US",
    observation_date: date = date(2024, 12, 31),
    score: float = 62.0,
    confidence: float = 0.88,
    flags: str | None = None,
) -> None:
    session.add(
        M1EffectiveRatesResult(
            country_code=country_code,
            date=observation_date,
            methodology_version="M1_EFFECTIVE_RATES_v0.2",
            score_normalized=score,
            score_raw=0.5,
            policy_rate_pct=5.25,
            shadow_rate_pct=5.25,
            real_rate_pct=2.3,
            r_star_pct=0.7,
            components_json="{}",
            lookback_years=10,
            confidence=confidence,
            flags=flags,
            source_connector="FRED",
        )
    )


def _seed_m2(
    session: Session,
    country_code: str = "US",
    observation_date: date = date(2024, 12, 31),
    score: float = 54.0,
    confidence: float = 0.82,
) -> None:
    session.add(
        M2TaylorGapsResult(
            country_code=country_code,
            date=observation_date,
            methodology_version="M2_TAYLOR_GAPS_v0.1",
            score_normalized=score,
            score_raw=0.2,
            taylor_implied_pct=3.5,
            taylor_gap_pp=1.2,
            taylor_uncertainty_pp=0.5,
            r_star_source="HLW",
            output_gap_source="CBO",
            variants_computed=3,
            components_json="{}",
            lookback_years=10,
            confidence=confidence,
            source_connector="FRED",
        )
    )


def _seed_m3(
    session: Session,
    country_code: str = "US",
    observation_date: date = date(2024, 12, 31),
    value_0_100: float = 45.0,
    confidence: float = 0.80,
    sub_indicators: dict[str, object] | None = None,
) -> None:
    session.add(
        IndexValue(
            index_code="M3_MARKET_EXPECTATIONS",
            country_code=country_code,
            date=observation_date,
            methodology_version="M3_MARKET_EXPECTATIONS_ANCHOR_v0.1",
            raw_value=0.3,
            zscore_clamped=0.3,
            value_0_100=value_0_100,
            sub_indicators_json=json.dumps(sub_indicators) if sub_indicators else None,
            confidence=confidence,
        )
    )


def _seed_m4(
    session: Session,
    country_code: str = "US",
    observation_date: date = date(2024, 12, 31),
    score: float = 42.0,
    confidence: float = 0.85,
) -> None:
    session.add(
        M4FciResult(
            country_code=country_code,
            date=observation_date,
            methodology_version="M4_FCI_v0.1",
            score_normalized=score,
            score_raw=0.1,
            fci_level=-0.1,
            fci_change_12m=0.05,
            fci_provider="NFCI_CHICAGO",
            components_available=4,
            fci_components_json="{}",
            lookback_years=10,
            confidence=confidence,
            source_connector="FRED",
        )
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_canonical_weights_sum_to_one() -> None:
    assert sum(CANONICAL_WEIGHTS.values()) == pytest.approx(1.0)


def test_weights_match_spec() -> None:
    assert CANONICAL_WEIGHTS == {
        "M1": 0.30,
        "M2": 0.15,
        "M3": 0.25,
        "M4": 0.20,
        "CS": 0.10,
    }


def test_total_inputs_is_5() -> None:
    assert TOTAL_INPUTS == 5
    assert MIN_INPUTS == 3


# ---------------------------------------------------------------------------
# Regime classification
# ---------------------------------------------------------------------------


class TestClassifyRegime6Band:
    def test_strongly_accommodative(self) -> None:
        assert classify_regime_6band(10.0) == "STRONGLY_ACCOMMODATIVE"

    def test_accommodative(self) -> None:
        assert classify_regime_6band(25.0) == "ACCOMMODATIVE"

    def test_neutral_accommodative(self) -> None:
        assert classify_regime_6band(45.0) == "NEUTRAL_ACCOMMODATIVE"

    def test_neutral_tight(self) -> None:
        assert classify_regime_6band(58.0) == "NEUTRAL_TIGHT"

    def test_tight(self) -> None:
        assert classify_regime_6band(72.0) == "TIGHT"

    def test_strongly_tight(self) -> None:
        assert classify_regime_6band(90.0) == "STRONGLY_TIGHT"

    def test_boundary_20_is_accommodative(self) -> None:
        assert classify_regime_6band(20.0) == "ACCOMMODATIVE"

    def test_boundary_100(self) -> None:
        assert classify_regime_6band(100.0) == "STRONGLY_TIGHT"


class TestClassifyRegime3Band:
    def test_accommodative(self) -> None:
        assert classify_regime_3band(30.0) == "ACCOMMODATIVE"

    def test_neutral(self) -> None:
        assert classify_regime_3band(50.0) == "NEUTRAL"

    def test_tight(self) -> None:
        assert classify_regime_3band(75.0) == "TIGHT"

    def test_boundary_40(self) -> None:
        assert classify_regime_3band(40.0) == "NEUTRAL"

    def test_boundary_60(self) -> None:
        assert classify_regime_3band(60.0) == "TIGHT"


# ---------------------------------------------------------------------------
# Hysteresis
# ---------------------------------------------------------------------------


class TestHysteresis:
    def test_first_observation(self) -> None:
        regime, persistence, held = apply_hysteresis(58.0, "NEUTRAL_TIGHT", None, None, 0)
        assert regime == "NEUTRAL_TIGHT"
        assert persistence == 1
        assert held is False

    def test_same_regime_increments(self) -> None:
        regime, persistence, held = apply_hysteresis(
            60.0, "NEUTRAL_TIGHT", 58.0, "NEUTRAL_TIGHT", 5
        )
        assert regime == "NEUTRAL_TIGHT"
        assert persistence == 6
        assert held is False

    def test_large_delta_transition_accepted(self) -> None:
        # |Δ| = 8 > 5 → transition committed.
        regime, persistence, held = apply_hysteresis(68.0, "TIGHT", 60.0, "NEUTRAL_TIGHT", 10)
        assert regime == "TIGHT"
        assert persistence == 1
        assert held is False

    def test_small_delta_sticky(self) -> None:
        # |Δ| = 3 ≤ 5 → transition rejected, previous band held.
        regime, persistence, held = apply_hysteresis(66.0, "TIGHT", 63.0, "NEUTRAL_TIGHT", 4)
        assert regime == "NEUTRAL_TIGHT"
        assert persistence == 5
        assert held is True

    def test_boundary_delta_5_is_sticky(self) -> None:
        regime, _persistence, held = apply_hysteresis(67.0, "TIGHT", 62.0, "NEUTRAL_TIGHT", 1)
        assert held is True
        assert regime == "NEUTRAL_TIGHT"


# ---------------------------------------------------------------------------
# compute_msc end-to-end
# ---------------------------------------------------------------------------


class TestComputeMsc:
    def test_us_full_four_inputs(self, db_session: Session) -> None:
        _seed_m1(db_session)
        _seed_m2(db_session)
        _seed_m3(db_session)
        _seed_m4(db_session)
        db_session.commit()

        result = compute_msc(db_session, "US", date(2024, 12, 31))

        # With CS absent, 4 of 5 inputs available.
        assert result.inputs_available == 4
        assert result.cs_score_0_100 is None
        # Weights re-normalised over (M1,M2,M3,M4) = 0.30+0.15+0.25+0.20 = 0.90.
        # So effective M1 = 0.30/0.90 ≈ 0.333...
        assert result.m1_weight_effective == pytest.approx(0.30 / 0.90, abs=1e-3)
        assert result.cs_weight_effective == 0.0
        assert 0 <= result.score_0_100 <= 100
        # Dataset seeds around 45-62 → NEUTRAL_TIGHT territory.
        assert result.regime_6band in {
            "NEUTRAL_ACCOMMODATIVE",
            "NEUTRAL_TIGHT",
        }
        assert result.regime_3band in {"NEUTRAL", "TIGHT"}
        # CS absent → COMM_SIGNAL_MISSING flag + confidence cap 0.75.
        assert "COMM_SIGNAL_MISSING" in result.flags
        assert result.confidence <= 0.75
        # Cold-start persistence.
        assert result.regime_persistence_days == 1
        assert result.methodology_version == METHODOLOGY_VERSION

    def test_persist_round_trip(self, db_session: Session) -> None:
        _seed_m1(db_session)
        _seed_m2(db_session)
        _seed_m3(db_session)
        _seed_m4(db_session)
        db_session.commit()
        result = compute_msc(db_session, "US", date(2024, 12, 31))
        persist_msc_result(db_session, result)
        row = db_session.execute(select(MonetaryCycleScore)).scalar_one()
        assert row.msc_id == result.msc_id
        assert row.score_0_100 == pytest.approx(result.score_0_100)
        assert row.regime_6band == result.regime_6band

    def test_raises_when_only_one_input(self, db_session: Session) -> None:
        _seed_m1(db_session)  # single input — below MIN_INPUTS=3 even with CS absent.
        db_session.commit()
        with pytest.raises(InsufficientCycleInputsError):
            compute_msc(db_session, "US", date(2024, 12, 31))

    def test_raises_when_two_inputs(self, db_session: Session) -> None:
        _seed_m1(db_session)
        _seed_m2(db_session)
        db_session.commit()
        with pytest.raises(InsufficientCycleInputsError):
            compute_msc(db_session, "US", date(2024, 12, 31))

    def test_three_inputs_suffices(self, db_session: Session) -> None:
        _seed_m1(db_session)
        _seed_m3(db_session)
        _seed_m4(db_session)
        db_session.commit()
        result = compute_msc(db_session, "US", date(2024, 12, 31))
        assert result.inputs_available == 3
        assert "M2_MISSING" in result.flags
        assert "COMM_SIGNAL_MISSING" in result.flags
        # 3/5 inputs, re-weighted → confidence cap 0.75 AND raw scaling ≤ 0.75·3/5.
        assert result.confidence <= 0.75

    def test_hysteresis_applies_against_previous_row(self, db_session: Session) -> None:
        # Seed previous MSC row: score=63, regime_6band=NEUTRAL_TIGHT (so a
        # today score that crosses just into TIGHT (66) at Δ=3 holds).
        prev = MonetaryCycleScore(
            msc_id="prev",
            country_code="US",
            date=date(2024, 12, 30),
            methodology_version=METHODOLOGY_VERSION,
            score_0_100=63.0,
            regime_6band="NEUTRAL_TIGHT",
            regime_3band="TIGHT",
            regime_persistence_days=10,
            m1_score_0_100=60.0,
            m2_score_0_100=55.0,
            m3_score_0_100=50.0,
            m4_score_0_100=55.0,
            cs_score_0_100=None,
            m1_weight_effective=0.333,
            m2_weight_effective=0.167,
            m3_weight_effective=0.278,
            m4_weight_effective=0.222,
            cs_weight_effective=0.0,
            inputs_available=4,
            dilemma_overlay_active=0,
            confidence=0.72,
            flags="COMM_SIGNAL_MISSING",
        )
        db_session.add(prev)
        # Today's inputs push score to ~66 (small Δ vs 63 → stick).
        _seed_m1(db_session, score=72.0)
        _seed_m2(db_session, score=62.0)
        _seed_m3(db_session, value_0_100=60.0)
        _seed_m4(db_session, score=62.0)
        db_session.commit()

        result = compute_msc(db_session, "US", date(2024, 12, 31))
        # |Δ| ≤ 5 → sticky.
        assert abs(result.score_0_100 - prev.score_0_100) <= REGIME_TRANSITION_DELTA_MIN or (
            result.regime_6band == prev.regime_6band
        )
        if abs(result.score_0_100 - prev.score_0_100) <= REGIME_TRANSITION_DELTA_MIN and (
            classify_regime_6band(result.score_0_100) != prev.regime_6band
        ):
            assert "REGIME_HYSTERESIS_HOLD" in result.flags

    def test_dilemma_no_ecs_flag_when_anchor_drifting(self, db_session: Session) -> None:
        _seed_m1(db_session, score=72.0)
        _seed_m2(db_session, score=68.0)
        _seed_m3(
            db_session,
            value_0_100=65.0,
            sub_indicators={"anchor_status": "drifting"},
        )
        _seed_m4(db_session, score=63.0)
        db_session.commit()
        result = compute_msc(db_session, "US", date(2024, 12, 31))
        # Score > 60 + anchor drifting + ECS not shipped → DILEMMA_NO_ECS.
        assert result.score_0_100 > DILEMMA_MSC_THRESHOLD
        assert "DILEMMA_NO_ECS" in result.flags
        # Overlay inactive per spec step 9 when ECS missing.
        assert result.dilemma_overlay_active == 0

    def test_flags_inherited_from_sub_indices(self, db_session: Session) -> None:
        _seed_m1(db_session, flags="R_STAR_PROXY")
        _seed_m2(db_session)
        _seed_m3(db_session)
        _seed_m4(db_session)
        db_session.commit()
        result = compute_msc(db_session, "US", date(2024, 12, 31))
        assert "R_STAR_PROXY" in result.flags

    def test_tight_regime_with_high_score(self, db_session: Session) -> None:
        # Push all inputs to high values → STRONGLY_TIGHT.
        _seed_m1(db_session, score=92.0)
        _seed_m2(db_session, score=85.0)
        _seed_m3(db_session, value_0_100=82.0)
        _seed_m4(db_session, score=80.0)
        db_session.commit()
        result = compute_msc(db_session, "US", date(2024, 12, 31))
        assert result.regime_6band in {"TIGHT", "STRONGLY_TIGHT"}
        assert result.regime_3band == "TIGHT"

    def test_accommodative_regime_with_low_score(self, db_session: Session) -> None:
        _seed_m1(db_session, score=18.0)
        _seed_m2(db_session, score=25.0)
        _seed_m3(db_session, value_0_100=22.0)
        _seed_m4(db_session, score=35.0)
        db_session.commit()
        result = compute_msc(db_session, "US", date(2024, 12, 31))
        assert result.regime_6band in {
            "STRONGLY_ACCOMMODATIVE",
            "ACCOMMODATIVE",
        }
        assert result.regime_3band == "ACCOMMODATIVE"

    def test_score_is_canonical_weighted_sum(self, db_session: Session) -> None:
        """Manual sanity: with m1=60, m2=50, m3=40, m4=30 + CS missing,
        re-weighted sum = (0.30·60 + 0.15·50 + 0.25·40 + 0.20·30) / 0.90
        = (18 + 7.5 + 10 + 6) / 0.90 = 41.5 / 0.90 ≈ 46.11.
        """
        _seed_m1(db_session, score=60.0)
        _seed_m2(db_session, score=50.0)
        _seed_m3(db_session, value_0_100=40.0)
        _seed_m4(db_session, score=30.0)
        db_session.commit()
        result = compute_msc(db_session, "US", date(2024, 12, 31))
        expected = (0.30 * 60 + 0.15 * 50 + 0.25 * 40 + 0.20 * 30) / 0.90
        assert result.score_0_100 == pytest.approx(expected, abs=0.01)
