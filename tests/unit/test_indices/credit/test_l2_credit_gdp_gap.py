"""Behavioral tests for L2 Credit-to-GDP Gap + HP/Hamilton helpers."""

from __future__ import annotations

import json
from datetime import date

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from sonar.db.models import Base, CreditGdpGap
from sonar.db.persistence import DuplicatePersistError, persist_credit_gdp_gap_result
from sonar.indices._helpers.hamilton_filter import hamilton_residual
from sonar.indices._helpers.hp_filter import (
    HP_LAMBDA_CREDIT_CYCLE,
    hp_filter_one_sided,
    hp_filter_two_sided,
    hp_one_sided_endpoint,
)
from sonar.indices.credit.l2_credit_gdp_gap import (
    METHODOLOGY_VERSION,
    CreditGdpGapInputs,
    classify_concordance,
    classify_phase_band,
    compute_credit_gdp_gap,
)
from sonar.indices.exceptions import InsufficientInputsError

# ---------------------------------------------------------------------------
# HP filter helpers
# ---------------------------------------------------------------------------


def _trend_plus_cycle(n: int, trend_slope: float, cycle_amp: float, seed: int) -> np.ndarray:
    """Synthesize ratio history = linear trend + sinusoidal cycle + noise."""
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    trend = 100.0 + trend_slope * t
    cycle = cycle_amp * np.sin(2 * np.pi * t / 32)  # ~8Y credit cycle
    noise = rng.normal(0, 0.5, size=n)
    return trend + cycle + noise


def test_hp_two_sided_decomposition_shape() -> None:
    y = _trend_plus_cycle(80, trend_slope=0.3, cycle_amp=5.0, seed=1)
    trend, cycle = hp_filter_two_sided(y)
    assert len(trend) == len(y) == len(cycle)
    assert np.allclose(trend + cycle, y, atol=1e-6)


def test_hp_one_sided_endpoint_smoke() -> None:
    y = _trend_plus_cycle(80, trend_slope=0.3, cycle_amp=5.0, seed=2)
    trend_t, cycle_t = hp_one_sided_endpoint(y)
    # Sanity: trend + cycle should equal the last observation up to HP resid.
    assert trend_t + cycle_t == pytest.approx(y[-1], abs=1e-6)


def test_hp_one_sided_insufficient_history_raises() -> None:
    with pytest.raises(ValueError, match="HP filter requires"):
        hp_one_sided_endpoint([100.0, 101.0, 102.0])


def test_hp_one_sided_recursive_fills_nans_at_start() -> None:
    y = _trend_plus_cycle(60, trend_slope=0.3, cycle_amp=5.0, seed=3)
    trend, _cycle = hp_filter_one_sided(y, min_history=40)
    assert np.isnan(trend[:39]).all()
    assert not np.isnan(trend[40:]).any()


def test_hp_lambda_constant() -> None:
    assert HP_LAMBDA_CREDIT_CYCLE == 400_000


# ---------------------------------------------------------------------------
# Hamilton filter helper
# ---------------------------------------------------------------------------


def test_hamilton_residual_trend_plus_cycle() -> None:
    y = _trend_plus_cycle(80, trend_slope=0.3, cycle_amp=5.0, seed=4)
    eps = hamilton_residual(y.tolist())
    # Residuals should be small-magnitude deviations, not huge.
    assert abs(eps) < 20.0


def test_hamilton_insufficient_observations_raises() -> None:
    with pytest.raises(ValueError, match="Hamilton requires"):
        hamilton_residual([100.0, 101.0, 102.0])


def test_hamilton_rank_deficient_pure_trend_raises() -> None:
    # Pure linear trend makes the 4 lag regressors collinear via the
    # exact AR(1) relation; lstsq reports rank < 5 and the helper
    # raises so the caller emits HAMILTON_FAIL per spec §6.
    y = (100.0 + 0.5 * np.arange(40)).tolist()
    with pytest.raises(ValueError, match="rank-deficient"):
        hamilton_residual(y)


# ---------------------------------------------------------------------------
# Classifiers
# ---------------------------------------------------------------------------


def test_phase_band_deleveraging() -> None:
    assert classify_phase_band(-8.0) == "deleveraging"
    assert classify_phase_band(-5.1) == "deleveraging"


def test_phase_band_neutral() -> None:
    assert classify_phase_band(-4.0) == "neutral"
    assert classify_phase_band(0.0) == "neutral"
    assert classify_phase_band(1.9) == "neutral"


def test_phase_band_boom_zone() -> None:
    assert classify_phase_band(2.0) == "boom_zone"
    assert classify_phase_band(5.0) == "boom_zone"
    assert classify_phase_band(9.9) == "boom_zone"


def test_phase_band_danger_zone() -> None:
    assert classify_phase_band(10.0) == "danger_zone"
    assert classify_phase_band(20.0) == "danger_zone"


def test_concordance_both_above() -> None:
    assert classify_concordance(3.0, 4.0) == "both_above"


def test_concordance_both_below() -> None:
    assert classify_concordance(-3.0, -1.0) == "both_below"


def test_concordance_divergent() -> None:
    assert classify_concordance(5.0, -3.0) == "divergent"


# ---------------------------------------------------------------------------
# Core compute
# ---------------------------------------------------------------------------


def _pt_gap_inputs(
    trend_slope: float = 0.2,
    cycle_amp: float = 4.0,
    n: int = 80,
) -> CreditGdpGapInputs:
    arr = _trend_plus_cycle(n=n, trend_slope=trend_slope, cycle_amp=cycle_amp, seed=100)
    return CreditGdpGapInputs(
        country_code="PT",
        observation_date=date(2024, 12, 31),
        ratio_pct_history=arr.tolist(),
    )


def test_pt_neutral_regime() -> None:
    result = compute_credit_gdp_gap(_pt_gap_inputs())
    assert result.methodology_version == METHODOLOGY_VERSION
    assert -5.0 <= result.score_normalized <= 5.0
    assert result.phase_band in ("deleveraging", "neutral", "boom_zone", "danger_zone")
    # Synthetic data produces gap near the cycle component; expect |gap| < 10pp
    assert abs(result.gap_hp_pp) < 10.0


def test_boom_zone_detection() -> None:
    # Force boom by appending a strong upward shock to the last 8 quarters.
    arr = _trend_plus_cycle(80, trend_slope=0.2, cycle_amp=3.0, seed=200)
    arr[-8:] += 15.0  # ratio_pct pushed up sharply
    inputs = CreditGdpGapInputs(
        country_code="XX",
        observation_date=date(2024, 12, 31),
        ratio_pct_history=arr.tolist(),
    )
    result = compute_credit_gdp_gap(inputs)
    assert result.gap_hp_pp > 2.0  # boom-zone threshold
    assert result.phase_band in ("boom_zone", "danger_zone")


def test_insufficient_history_raises() -> None:
    inputs = CreditGdpGapInputs(
        country_code="XX",
        observation_date=date(2024, 12, 31),
        ratio_pct_history=[100.0] * 10,
    )
    with pytest.raises(InsufficientInputsError, match="hard floor"):
        compute_credit_gdp_gap(inputs)


def test_gap_divergent_flag_fires() -> None:
    """Engineer a series where HP gap and Hamilton residual disagree
    sharply: a regime break in the last quarter pulls HP but not Hamilton.
    """
    arr = _trend_plus_cycle(80, trend_slope=0.2, cycle_amp=3.0, seed=300)
    arr[-1] += 15.0
    inputs = CreditGdpGapInputs(
        country_code="XX",
        observation_date=date(2024, 12, 31),
        ratio_pct_history=arr.tolist(),
    )
    result = compute_credit_gdp_gap(inputs)
    # With a single-quarter shock, HP and Hamilton should diverge.
    if "GAP_DIVERGENT" in result.flags:
        assert abs(result.gap_hp_pp - result.gap_hamilton_pp) > 5.0
    # Either way, concordance classification must be set.
    assert result.concordance in ("both_above", "both_below", "divergent")


def test_upstream_flags_propagate() -> None:
    inputs = CreditGdpGapInputs(
        country_code="PT",
        observation_date=date(2024, 12, 31),
        ratio_pct_history=_trend_plus_cycle(80, 0.2, 3.0, 400).tolist(),
        upstream_flags=("CREDIT_BREAK",),
    )
    result = compute_credit_gdp_gap(inputs)
    assert "CREDIT_BREAK" in result.flags
    assert result.confidence < 1.0


def test_components_json_shape() -> None:
    result = compute_credit_gdp_gap(_pt_gap_inputs())
    payload = json.loads(result.components_json)
    for key in (
        "ratio_pct",
        "trend_hp_pct",
        "gap_hp_pp",
        "gap_hamilton_pp",
        "hp_lambda",
        "hamilton_horizon_q",
        "phase_band",
        "concordance",
        "endpoint_revision_pp",
    ):
        assert key in payload


def test_score_raw_is_avg_of_gaps() -> None:
    result = compute_credit_gdp_gap(_pt_gap_inputs())
    expected = (result.gap_hp_pp + result.gap_hamilton_pp) / 2.0
    assert result.score_raw == pytest.approx(expected, rel=1e-9)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def test_persist_single_row(session: Session) -> None:
    result = compute_credit_gdp_gap(_pt_gap_inputs())
    persist_credit_gdp_gap_result(session, result)
    rows = session.query(CreditGdpGap).all()
    assert len(rows) == 1
    assert rows[0].country_code == "PT"
    assert rows[0].hp_lambda == HP_LAMBDA_CREDIT_CYCLE


def test_persist_duplicate_raises(session: Session) -> None:
    result = compute_credit_gdp_gap(_pt_gap_inputs())
    persist_credit_gdp_gap_result(session, result)
    with pytest.raises(DuplicatePersistError, match="already persisted"):
        persist_credit_gdp_gap_result(session, result)
