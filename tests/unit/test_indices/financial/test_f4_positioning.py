"""Behavioral tests for F4 Positioning per spec §7 fixtures."""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from sonar.indices.exceptions import InsufficientInputsError
from sonar.indices.financial.f4_positioning import (
    METHODOLOGY_VERSION,
    SPEC_WEIGHTS,
    F4Inputs,
    compute_f4_positioning,
)


def _synth_hist(mean: float, sd: float, n: int, seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    return rng.normal(mean, sd, n).tolist()


def _us_2024_inputs(**overrides: object) -> F4Inputs:
    base: dict[str, object] = {
        "country_code": "US",
        "observation_date": date(2024, 1, 2),
        "aaii_bull_minus_bear_pct": 18.0,
        "put_call_ratio": 0.78,
        "cot_noncomm_net_sp500": 85_000,
        "margin_debt_gdp_pct": 2.60,
        "ipo_activity_score": 55.0,
        "aaii_history": _synth_hist(5.0, 10.0, 80, 1),
        "put_call_history": _synth_hist(1.0, 0.2, 80, 2),
        "cot_history": _synth_hist(0.0, 80_000.0, 80, 3),
        "margin_history_pct": _synth_hist(2.2, 0.5, 80, 4),
        "ipo_history": _synth_hist(50.0, 15.0, 80, 5),
    }
    base.update(overrides)
    return F4Inputs(**base)  # type: ignore[arg-type]


def test_spec_weights_sum_to_one() -> None:
    assert sum(SPEC_WEIGHTS.values()) == pytest.approx(1.0, abs=1e-9)


def test_us_2024_bullish_regime() -> None:
    result = compute_f4_positioning(_us_2024_inputs())
    assert result.methodology_version == METHODOLOGY_VERSION
    assert result.components_available == 5
    # AAII bb +18 vs 5 → z ≈ +1.3; P/C 0.78 vs 1.0 → z ≈ -1.1 sign-flipped → +1.1
    # COT +85k vs 0 → z ≈ +1.06; margin 2.6 vs 2.2 → z ≈ +0.8
    # Expect bullish regime.
    assert result.score_normalized > 55.0


def test_us_2021_contrarian_extreme() -> None:
    result = compute_f4_positioning(
        _us_2024_inputs(
            aaii_bull_minus_bear_pct=45.0,
            put_call_ratio=0.55,
            cot_noncomm_net_sp500=180_000,
            margin_debt_gdp_pct=3.5,
            ipo_activity_score=85.0,
        )
    )
    assert result.score_normalized > 85.0
    assert result.positioning_extreme_flag is True
    assert "F4_CONTRARIAN_EXTREME" in result.flags


def test_us_2009_contrarian_buy_extreme() -> None:
    result = compute_f4_positioning(
        _us_2024_inputs(
            aaii_bull_minus_bear_pct=-51.0,
            put_call_ratio=1.45,
            cot_noncomm_net_sp500=-120_000,
            margin_debt_gdp_pct=1.5,
            ipo_activity_score=15.0,
        )
    )
    assert result.score_normalized < 15.0
    assert result.positioning_extreme_flag is True
    assert "F4_CONTRARIAN_EXTREME" in result.flags


def test_2_component_minimum_ok() -> None:
    # AAII + P/C only
    inputs = F4Inputs(
        country_code="EA",
        observation_date=date(2024, 1, 2),
        aaii_bull_minus_bear_pct=18.0,
        aaii_history=_synth_hist(5.0, 10.0, 80, 1),
        put_call_ratio=0.78,
        put_call_history=_synth_hist(1.0, 0.2, 80, 2),
        cot_noncomm_net_sp500=None,
        margin_debt_gdp_pct=None,
        ipo_activity_score=None,
    )
    result = compute_f4_positioning(inputs)
    assert result.components_available == 2
    assert "OVERLAY_MISS" in result.flags


def test_less_than_2_components_raises() -> None:
    inputs = F4Inputs(
        country_code="TR",
        observation_date=date(2024, 1, 2),
        aaii_bull_minus_bear_pct=10.0,
        aaii_history=_synth_hist(5.0, 10.0, 80, 1),
        put_call_ratio=None,
        cot_noncomm_net_sp500=None,
        margin_debt_gdp_pct=None,
        ipo_activity_score=None,
    )
    with pytest.raises(InsufficientInputsError, match=">= 2 components"):
        compute_f4_positioning(inputs)


def test_aaii_proxy_flag() -> None:
    result = compute_f4_positioning(_us_2024_inputs(), aaii_is_us_proxy=True)
    assert "AAII_PROXY" in result.flags
    assert result.confidence <= 0.80


def test_insufficient_history_flag() -> None:
    result = compute_f4_positioning(
        _us_2024_inputs(
            aaii_history=_synth_hist(5.0, 10.0, 20, 1),
            put_call_history=_synth_hist(1.0, 0.2, 20, 2),
            cot_history=_synth_hist(0.0, 80_000.0, 20, 3),
            margin_history_pct=_synth_hist(2.2, 0.5, 20, 4),
            ipo_history=_synth_hist(50.0, 15.0, 20, 5),
        )
    )
    assert "INSUFFICIENT_HISTORY" in result.flags
    assert result.confidence <= 0.65


def test_put_call_sign_flip() -> None:
    # High P/C (bearish) should pull score DOWN.
    high_pc = compute_f4_positioning(_us_2024_inputs(put_call_ratio=1.8))
    low_pc = compute_f4_positioning(_us_2024_inputs(put_call_ratio=0.4))
    assert low_pc.score_normalized > high_pc.score_normalized


def test_score_in_range() -> None:
    result = compute_f4_positioning(
        _us_2024_inputs(aaii_bull_minus_bear_pct=100.0, margin_debt_gdp_pct=10.0)
    )
    assert 0.0 <= result.score_normalized <= 100.0


def test_extreme_flag_not_set_near_center() -> None:
    result = compute_f4_positioning(
        _us_2024_inputs(
            aaii_bull_minus_bear_pct=5.0,
            put_call_ratio=1.0,
            cot_noncomm_net_sp500=0,
            margin_debt_gdp_pct=2.2,
            ipo_activity_score=50.0,
        )
    )
    assert result.positioning_extreme_flag is False
    assert "F4_CONTRARIAN_EXTREME" not in result.flags
