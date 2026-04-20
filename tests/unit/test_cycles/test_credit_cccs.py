"""Unit tests for CCCS compute — isolated functions + end-to-end with DB."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import sonar.db.session  # noqa: F401
from sonar.cycles.credit_cccs import (
    BOOM_OVERLAY_L2_GAP_THRESHOLD_PP,
    BOOM_OVERLAY_L4_DSR_Z_THRESHOLD,
    BOOM_OVERLAY_SCORE_THRESHOLD,
    CANONICAL_WEIGHTS,
    REGIME_TRANSITION_DELTA_MIN,
    apply_hysteresis,
    classify_regime,
    compute_cccs,
    persist_cccs_result,
    pts,
)
from sonar.db.models import (
    Base,
    CreditCycleScore,
    CreditGdpGap,
    CreditGdpStock,
    CreditImpulse,
    Dsr,
    FinancialPositioning,
    FinancialRiskAppetite,
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


class TestPtsMapping:
    def test_zero_z_maps_to_50(self) -> None:
        assert pts(0.0) == pytest.approx(50.0)

    def test_positive_z_above_50(self) -> None:
        assert pts(1.0) == pytest.approx(66.67, abs=0.01)

    def test_clipped_high(self) -> None:
        assert pts(10.0) == pytest.approx(100.0)

    def test_clipped_low(self) -> None:
        assert pts(-10.0) == pytest.approx(0.0)


class TestClassifyRegime:
    def test_repair(self) -> None:
        assert classify_regime(25.0) == "REPAIR"

    def test_recovery(self) -> None:
        assert classify_regime(40.0) == "RECOVERY"

    def test_boom(self) -> None:
        assert classify_regime(60.0) == "BOOM"

    def test_speculation(self) -> None:
        assert classify_regime(75.0) == "SPECULATION"

    def test_distress(self) -> None:
        assert classify_regime(90.0) == "DISTRESS"

    def test_boundary_30(self) -> None:
        assert classify_regime(30.0) == "RECOVERY"

    def test_boundary_85(self) -> None:
        assert classify_regime(85.0) == "SPECULATION"


class TestHysteresis:
    def test_first_observation(self) -> None:
        regime, persistence, held = apply_hysteresis(60.0, "BOOM", None, None, 0)
        assert regime == "BOOM"
        assert persistence == 1
        assert held is False

    def test_same_regime_increments(self) -> None:
        regime, persistence, held = apply_hysteresis(62.0, "BOOM", 60.0, "BOOM", 5)
        assert regime == "BOOM"
        assert persistence == 6
        assert held is False

    def test_transition_with_large_delta_accepted(self) -> None:
        regime, persistence, held = apply_hysteresis(75.0, "SPECULATION", 62.0, "BOOM", 10)
        assert regime == "SPECULATION"
        assert persistence == 1
        assert held is False

    def test_small_delta_sticky(self) -> None:
        # Δ = 3 < 5 → transition rejected, regime persists.
        regime, persistence, held = apply_hysteresis(50.5, "RECOVERY", 48.0, "RECOVERY", 4)
        # Recovery classifies 50.5 as BOOM (>=50), but sticky rule keeps RECOVERY.
        # Actually classify_regime is not called in apply_hysteresis; caller passes
        # the newly-classified regime. Here we pass RECOVERY as new_regime.
        assert regime == "RECOVERY"
        assert persistence == 5
        assert held is False  # same regime, not held

    def test_small_delta_rejects_transition(self) -> None:
        regime, persistence, held = apply_hysteresis(49.5, "RECOVERY", 51.0, "BOOM", 10)
        # Δ = 1.5 < 5 → hold BOOM, bump persistence.
        assert regime == "BOOM"
        assert persistence == 11
        assert held is True


def _seed_sub_rows(
    session: Session,
    country: str = "US",
    observation_date: date = date(2024, 1, 31),
    *,
    l1_z: float = 0.2,
    l2_z: float = 0.3,
    l3_z: float = 0.1,
    l4_z: float = -0.1,
    f3_score: float = 55.0,
    margin_debt_pct: float | None = 3.5,
) -> None:
    """Seed the 5 upstream rows + a history for F4 margin debt."""
    session.add_all(
        [
            CreditGdpStock(
                country_code=country,
                date=observation_date,
                methodology_version="L1_CREDIT_GDP_STOCK_v0.1",
                score_normalized=l1_z,
                score_raw=150.0,
                components_json="{}",
                series_variant="Q",
                gdp_vintage_mode="production",
                lookback_years=20,
                confidence=0.9,
                source_connector="bis",
            ),
            CreditGdpGap(
                country_code=country,
                date=observation_date,
                methodology_version="L2_CREDIT_GDP_GAP_v0.1",
                score_normalized=l2_z,
                score_raw=3.5,  # gap_hp_pp
                gap_hp_pp=3.5,
                gap_hamilton_pp=3.0,
                trend_gdp_pct=2.0,
                hp_lambda=400000,
                hamilton_horizon_q=8,
                concordance="both_above",
                phase_band="neutral",
                components_json="{}",
                lookback_years=20,
                confidence=0.9,
                source_connector="bis",
            ),
            CreditImpulse(
                country_code=country,
                date=observation_date,
                methodology_version="L3_CREDIT_IMPULSE_v0.1",
                score_normalized=l3_z,
                score_raw=1.5,
                impulse_pp=1.5,
                flow_t_lcu=1000.0,
                flow_t_minus4_lcu=900.0,
                delta_flow_lcu=100.0,
                gdp_t_minus4_lcu=50000.0,
                state="expansion",
                series_variant="Q",
                smoothing="raw",
                components_json="{}",
                lookback_years=20,
                segment="PNFS",
                confidence=0.85,
                source_connector="bis",
            ),
            Dsr(
                country_code=country,
                date=observation_date,
                methodology_version="L4_DSR_v0.1",
                score_normalized=l4_z,
                score_raw=14.5,
                dsr_pct=14.5,
                dsr_deviation_pp=0.5,
                lending_rate_pct=0.04,
                avg_maturity_years=8.0,
                debt_to_gdp_ratio=1.5,
                annuity_factor=0.07,
                formula_mode="full",
                band="baseline",
                denominator="GDP_4Q_sum",
                segment="PNFS",
                components_json="{}",
                lookback_years=20,
                confidence=0.9,
                source_connector="bis",
            ),
            FinancialRiskAppetite(
                country_code=country,
                date=observation_date,
                methodology_version="F3_RISK_APPETITE_v0.1",
                score_normalized=f3_score,
                score_raw=0.3,
                components_json="{}",
                components_available=4,
                lookback_years=20,
                confidence=0.85,
            ),
        ]
    )
    # Seed F4 history with 20+ observations (distinct months) so z_20Y
    # is computable. Spread across prior 3 years Jan-Dec.
    if margin_debt_pct is not None:
        for year_offset in range(1, 4):
            for month in range(1, 12):
                session.add(
                    FinancialPositioning(
                        country_code=country,
                        date=date(observation_date.year - year_offset, month, 28),
                        methodology_version="F4_POSITIONING_v0.1",
                        score_normalized=50.0,
                        score_raw=0.1,
                        components_json="{}",
                        components_available=2,
                        margin_debt_gdp_pct=2.5 + 0.01 * (year_offset * 12 + month),
                        lookback_years=20,
                        confidence=0.8,
                    )
                )
        session.add(
            FinancialPositioning(
                country_code=country,
                date=observation_date,
                methodology_version="F4_POSITIONING_v0.1",
                score_normalized=55.0,
                score_raw=0.2,
                components_json="{}",
                components_available=2,
                margin_debt_gdp_pct=margin_debt_pct,
                lookback_years=20,
                confidence=0.85,
            )
        )
    session.commit()


class TestComputeCccsEndToEnd:
    def test_happy_full_stack(self, db_session: Session) -> None:
        _seed_sub_rows(db_session)
        result = compute_cccs(db_session, "US", date(2024, 1, 31))
        assert 0 <= result.score_0_100 <= 100
        assert result.regime in {"REPAIR", "RECOVERY", "BOOM", "SPECULATION", "DISTRESS"}
        assert result.components_available == 3
        assert "QS_PLACEHOLDER" in result.flags
        # weights_effective sum = 1.0 (all 3 sub-components present)
        assert (
            result.cs_weight_effective + result.lc_weight_effective + result.ms_weight_effective
            == pytest.approx(1.0, abs=1e-9)
        )
        assert result.qs_score_0_100 is None

    def test_f4_margin_missing_fallback(self, db_session: Session) -> None:
        _seed_sub_rows(db_session, margin_debt_pct=None)
        result = compute_cccs(db_session, "US", date(2024, 1, 31))
        # MS falls back to 100% F3 per spec §4.
        assert "F4_MARGIN_MISSING" in result.flags
        # ms_score should be F3 score (55.0 per seed).
        assert result.ms_score_0_100 == pytest.approx(55.0)

    def test_persistence_round_trip(self, db_session: Session) -> None:
        _seed_sub_rows(db_session)
        result = compute_cccs(db_session, "US", date(2024, 1, 31))
        persist_cccs_result(db_session, result)
        row = db_session.execute(select(CreditCycleScore)).scalar_one()
        assert row.cccs_id == result.cccs_id
        assert row.regime == result.regime
        assert row.score_0_100 == pytest.approx(result.score_0_100)


class TestConstants:
    def test_canonical_weights_match_spec(self) -> None:
        assert CANONICAL_WEIGHTS == {"CS": 0.44, "LC": 0.33, "MS": 0.22}

    def test_boom_thresholds_match_spec(self) -> None:
        assert BOOM_OVERLAY_L2_GAP_THRESHOLD_PP == 10.0
        assert BOOM_OVERLAY_L4_DSR_Z_THRESHOLD == 1.5
        assert BOOM_OVERLAY_SCORE_THRESHOLD == 70.0

    def test_regime_delta_min(self) -> None:
        assert REGIME_TRANSITION_DELTA_MIN == 5.0
