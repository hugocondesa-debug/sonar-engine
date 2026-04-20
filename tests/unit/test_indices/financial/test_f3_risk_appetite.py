"""Behavioral tests for F3 Risk Appetite per spec §7 fixtures."""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from sonar.indices.exceptions import InsufficientInputsError
from sonar.indices.financial.f3_risk_appetite import (
    METHODOLOGY_VERSION,
    SPEC_WEIGHTS,
    F3Inputs,
    classify_risk_regime,
    compute_f3_risk_appetite,
)


def _synth_hist(mean: float, sd: float, n: int, seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    return rng.normal(mean, sd, n).tolist()


def _us_2024_inputs(**overrides: object) -> F3Inputs:
    base: dict[str, object] = {
        "country_code": "US",
        "observation_date": date(2024, 1, 2),
        "vix_level": 13.2,
        "move_level": 110.0,
        "credit_spread_hy_bps": 320,
        "credit_spread_ig_bps": 105,
        "fci_level": -0.45,
        "vix_history": _synth_hist(18.0, 6.0, 80, 1),
        "move_history": _synth_hist(90.0, 25.0, 80, 2),
        "hy_history_bps": _synth_hist(500.0, 200.0, 80, 3),
        "ig_history_bps": _synth_hist(150.0, 50.0, 80, 4),
        "fci_history": _synth_hist(0.0, 0.6, 80, 5),
    }
    base.update(overrides)
    return F3Inputs(**base)  # type: ignore[arg-type]


def test_spec_weights_sum_to_one() -> None:
    assert sum(SPEC_WEIGHTS.values()) == pytest.approx(1.0, abs=1e-9)


def test_us_2024_greed_regime() -> None:
    result = compute_f3_risk_appetite(_us_2024_inputs())
    assert result.methodology_version == METHODOLOGY_VERSION
    assert result.components_available == 5
    # Low vol + tight spreads + loose FCI → high score.
    assert result.score_normalized >= 55.0
    assert result.risk_regime in ("neutral", "greed")


def test_us_2008_crisis_extreme_fear() -> None:
    result = compute_f3_risk_appetite(
        _us_2024_inputs(
            vix_level=68.0,
            move_level=240.0,
            credit_spread_hy_bps=1850,
            credit_spread_ig_bps=520,
            fci_level=3.5,
        )
    )
    assert result.score_normalized < 20.0
    assert result.risk_regime == "extreme_fear"
    assert "F3_STRESS_EXTREME" in result.flags


def test_classify_risk_regime_bands() -> None:
    assert classify_risk_regime(10.0) == "extreme_fear"
    assert classify_risk_regime(30.0) == "fear"
    assert classify_risk_regime(50.0) == "neutral"
    assert classify_risk_regime(70.0) == "greed"
    assert classify_risk_regime(90.0) == "extreme_greed"


def test_insufficient_components_raises() -> None:
    # Only 2/5 components
    inputs = F3Inputs(
        country_code="XX",
        observation_date=date(2024, 1, 2),
        vix_level=14.0,
        vix_history=_synth_hist(18.0, 6.0, 80, 1),
        move_level=None,
        credit_spread_hy_bps=320,
        hy_history_bps=_synth_hist(500.0, 200.0, 80, 3),
        credit_spread_ig_bps=None,
        fci_level=None,
    )
    with pytest.raises(InsufficientInputsError, match=">= 3 components"):
        compute_f3_risk_appetite(inputs)


def test_minimum_3_components_ok() -> None:
    inputs = F3Inputs(
        country_code="XX",
        observation_date=date(2024, 1, 2),
        vix_level=14.0,
        vix_history=_synth_hist(18.0, 6.0, 80, 1),
        move_level=None,
        credit_spread_hy_bps=320,
        hy_history_bps=_synth_hist(500.0, 200.0, 80, 3),
        credit_spread_ig_bps=110,
        ig_history_bps=_synth_hist(150.0, 50.0, 80, 4),
        fci_level=None,
    )
    result = compute_f3_risk_appetite(inputs)
    assert result.components_available == 3
    assert "OVERLAY_MISS" in result.flags


def test_move_proxy_flag() -> None:
    result = compute_f3_risk_appetite(_us_2024_inputs(), move_is_proxy=True)
    assert "MOVE_PROXY" in result.flags
    assert result.confidence <= 0.90


def test_vol_proxy_global_flag() -> None:
    result = compute_f3_risk_appetite(_us_2024_inputs(), vix_is_global_proxy=True)
    assert "VOL_PROXY_GLOBAL" in result.flags
    assert result.confidence <= 0.85


def test_stress_extreme_on_vix_gt_50() -> None:
    result = compute_f3_risk_appetite(_us_2024_inputs(vix_level=72.0))
    assert "F3_STRESS_EXTREME" in result.flags


def test_stress_extreme_on_hy_gt_1000() -> None:
    result = compute_f3_risk_appetite(_us_2024_inputs(vix_level=20.0, credit_spread_hy_bps=1100))
    assert "F3_STRESS_EXTREME" in result.flags


def test_insufficient_history_flag() -> None:
    result = compute_f3_risk_appetite(
        _us_2024_inputs(
            vix_history=_synth_hist(18.0, 6.0, 20, 1),
            move_history=_synth_hist(90.0, 25.0, 20, 2),
            hy_history_bps=_synth_hist(500.0, 200.0, 20, 3),
            ig_history_bps=_synth_hist(150.0, 50.0, 20, 4),
            fci_history=_synth_hist(0.0, 0.6, 20, 5),
        )
    )
    assert "INSUFFICIENT_HISTORY" in result.flags
    assert result.confidence <= 0.65


def test_score_in_range() -> None:
    result = compute_f3_risk_appetite(_us_2024_inputs(vix_level=3.0))
    assert 0.0 <= result.score_normalized <= 100.0
