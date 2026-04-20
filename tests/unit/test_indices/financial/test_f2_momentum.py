"""Behavioral tests for F2 Momentum per spec §7 fixtures."""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from sonar.indices.exceptions import InsufficientInputsError
from sonar.indices.financial.f2_momentum import (
    METHODOLOGY_VERSION,
    SPEC_WEIGHTS,
    F2Inputs,
    classify_momentum_state,
    compute_f2_momentum,
    risk_on_signal,
)


def _synth_hist(mean: float, sd: float, n: int, seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    return rng.normal(mean, sd, n).tolist()


def _us_2024_inputs(**overrides: object) -> F2Inputs:
    base: dict[str, object] = {
        "country_code": "US",
        "observation_date": date(2024, 1, 2),
        "mom_3m_pct": 0.06,
        "mom_6m_pct": 0.10,
        "mom_12m_pct": 0.24,
        "breadth_above_ma200_pct": 72.0,
        "cross_asset_signal": 2.0,
        "mom_3m_history_pct": _synth_hist(0.02, 0.05, 80, 1),
        "mom_6m_history_pct": _synth_hist(0.04, 0.08, 80, 2),
        "mom_12m_history_pct": _synth_hist(0.08, 0.15, 80, 3),
        "breadth_history_pct": _synth_hist(55.0, 15.0, 80, 4),
        "cross_asset_history": _synth_hist(0.0, 1.5, 80, 5),
        "primary_index": "SPX",
    }
    base.update(overrides)
    return F2Inputs(**base)  # type: ignore[arg-type]


def test_spec_weights_sum_to_one() -> None:
    assert sum(SPEC_WEIGHTS.values()) == pytest.approx(1.0, abs=1e-9)


def test_us_2024_strong_momentum() -> None:
    result = compute_f2_momentum(_us_2024_inputs())
    assert result.methodology_version == METHODOLOGY_VERSION
    assert result.primary_index == "SPX"
    assert result.momentum_state in ("weak_up", "strong_up")
    assert 55.0 <= result.score_normalized <= 100.0


def test_us_covid_trough_strong_down() -> None:
    result = compute_f2_momentum(
        _us_2024_inputs(
            mom_3m_pct=-0.25,
            mom_6m_pct=-0.35,
            mom_12m_pct=-0.45,
            breadth_above_ma200_pct=8.0,
            cross_asset_signal=-3.0,
        )
    )
    assert result.momentum_state in ("weak_down", "strong_down")
    assert result.score_normalized < 35.0


def test_classify_momentum_state() -> None:
    assert classify_momentum_state(10.0) == "strong_down"
    assert classify_momentum_state(30.0) == "weak_down"
    assert classify_momentum_state(50.0) == "flat"
    assert classify_momentum_state(60.0) == "weak_up"
    assert classify_momentum_state(90.0) == "strong_up"


def test_breadth_proxy_flag_applied() -> None:
    result = compute_f2_momentum(_us_2024_inputs(), breadth_is_proxy=True)
    assert "BREADTH_PROXY" in result.flags
    assert result.confidence <= 0.85


def test_cross_asset_partial_flag_applied() -> None:
    result = compute_f2_momentum(_us_2024_inputs(), cross_asset_n_assets=3)
    assert "CROSS_ASSET_PARTIAL" in result.flags


def test_insufficient_history_flag() -> None:
    result = compute_f2_momentum(
        _us_2024_inputs(
            mom_3m_history_pct=_synth_hist(0.02, 0.05, 20, 1),
            mom_6m_history_pct=_synth_hist(0.04, 0.08, 20, 2),
            mom_12m_history_pct=_synth_hist(0.08, 0.15, 20, 3),
            breadth_history_pct=_synth_hist(55.0, 15.0, 20, 4),
            cross_asset_history=_synth_hist(0.0, 1.5, 20, 5),
        )
    )
    assert "INSUFFICIENT_HISTORY" in result.flags
    assert result.confidence <= 0.65


def test_risk_on_signal_all_positive() -> None:
    # Equity +, vix - , comm +, usd -, credit_hy -
    v = risk_on_signal(
        equity_3m=0.05,
        vix_3m=-0.10,
        commodities_3m=0.03,
        usd_3m=-0.02,
        credit_hy_3m=-0.05,
    )
    assert v == 5.0  # all 5 positive


def test_risk_on_signal_risk_off() -> None:
    v = risk_on_signal(
        equity_3m=-0.10,
        vix_3m=0.20,
        commodities_3m=-0.05,
        usd_3m=0.03,
        credit_hy_3m=0.15,
    )
    assert v == -5.0


def test_risk_on_signal_handles_none() -> None:
    # Missing components contribute 0.
    v = risk_on_signal(
        equity_3m=0.05,
        vix_3m=None,
        commodities_3m=None,
        usd_3m=None,
        credit_hy_3m=None,
    )
    assert v == 1.0


def test_breadth_divergence_detection() -> None:
    # Engineer score > 70 with breadth_z < -0.5 (breadth at low value vs its
    # history). Keep all momenta high, set breadth to 30% (well below the
    # 55±15 mean).
    result = compute_f2_momentum(
        _us_2024_inputs(
            mom_3m_pct=0.15,
            mom_6m_pct=0.25,
            mom_12m_pct=0.40,
            breadth_above_ma200_pct=30.0,
            cross_asset_signal=3.0,
        )
    )
    # Fires when score > 70 AND breadth z < -0.5.
    if result.score_normalized > 70.0:
        assert "BREADTH_DIVERGENCE" in result.flags


def test_all_components_missing_raises() -> None:
    inputs = F2Inputs(
        country_code="XX",
        observation_date=date(2024, 1, 2),
        mom_3m_pct=None,
        mom_6m_pct=None,
        mom_12m_pct=None,
        breadth_above_ma200_pct=None,
        cross_asset_signal=None,
    )
    with pytest.raises(InsufficientInputsError, match="no momentum components"):
        compute_f2_momentum(inputs)


def test_score_in_range() -> None:
    # Extreme cross-asset should still clip to [0, 100].
    result = compute_f2_momentum(_us_2024_inputs(cross_asset_signal=50.0, mom_12m_pct=2.0))
    assert 0.0 <= result.score_normalized <= 100.0
