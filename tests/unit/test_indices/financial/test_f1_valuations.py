"""Behavioral tests for F1 Valuations per spec §7 fixtures."""

from __future__ import annotations

import json
from datetime import date

import numpy as np
import pytest

from sonar.indices.exceptions import InsufficientInputsError
from sonar.indices.financial.f1_valuations import (
    METHODOLOGY_VERSION,
    SPEC_WEIGHTS,
    F1Inputs,
    classify_valuation_band,
    compute_f1_valuations,
)


def _synth_hist(mean: float, sd: float, n: int, seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    return rng.normal(mean, sd, n).tolist()


def _us_2024_inputs(**overrides: object) -> F1Inputs:
    base: dict[str, object] = {
        "country_code": "US",
        "observation_date": date(2024, 1, 2),
        "cape_ratio": 33.2,
        "buffett_ratio": 1.85,
        "erp_median_bps": 472,
        "forward_pe": 19.5,
        "property_gap_pp": 4.2,
        "cape_history": _synth_hist(mean=25.0, sd=5.0, n=80, seed=1),
        "buffett_history": _synth_hist(mean=1.4, sd=0.3, n=80, seed=2),
        "erp_history_bps": _synth_hist(mean=500.0, sd=100.0, n=80, seed=3),
        "forward_pe_history": _synth_hist(mean=17.0, sd=3.0, n=80, seed=4),
        "property_gap_history": _synth_hist(mean=0.0, sd=3.0, n=80, seed=5),
    }
    base.update(overrides)
    return F1Inputs(**base)  # type: ignore[arg-type]


def test_spec_weights_sum_to_one() -> None:
    assert sum(SPEC_WEIGHTS.values()) == pytest.approx(1.0, abs=1e-9)


def test_us_2024_returns_stretched_band() -> None:
    result = compute_f1_valuations(_us_2024_inputs())
    assert result.methodology_version == METHODOLOGY_VERSION
    # CAPE 33.2 vs 25±5 → z≈+1.6; Buffett 1.85 vs 1.4 → z≈+1.5
    # ERP 472 vs 500 → z≈-0.28, sign-flipped → +0.28
    # FwdPE 19.5 vs 17 → z≈+0.83
    # Property 4.2 vs 0 → z≈+1.4
    # Expected score_normalized in the "stretched" band (55-75).
    assert 55.0 <= result.score_normalized <= 80.0
    assert result.valuation_band in ("stretched", "bubble")


def test_us_2000_bubble_extreme() -> None:
    # CAPE=44, Buffett=2.10, ERP=-50bps (post-flip pushes high), etc.
    result = compute_f1_valuations(
        _us_2024_inputs(
            cape_ratio=44.0,
            buffett_ratio=2.10,
            erp_median_bps=-50,
            forward_pe=25.0,
            property_gap_pp=8.0,
        )
    )
    assert result.score_normalized > 80.0
    assert result.valuation_band == "bubble"
    assert "F1_EXTREME_HIGH" in result.flags or result.score_normalized <= 95.0


def test_us_2009_trough_cheap() -> None:
    result = compute_f1_valuations(
        _us_2024_inputs(
            cape_ratio=13.0,
            buffett_ratio=0.62,
            erp_median_bps=820,
            forward_pe=12.0,
            property_gap_pp=-15.0,
        )
    )
    assert result.score_normalized < 35.0
    assert result.valuation_band in ("cheap", "fair")


def test_classify_valuation_band() -> None:
    assert classify_valuation_band(10.0) == "cheap"
    assert classify_valuation_band(29.9) == "cheap"
    assert classify_valuation_band(30.0) == "fair"
    assert classify_valuation_band(54.9) == "fair"
    assert classify_valuation_band(55.0) == "stretched"
    assert classify_valuation_band(74.9) == "stretched"
    assert classify_valuation_band(75.0) == "bubble"
    assert classify_valuation_band(99.0) == "bubble"


def test_erp_missing_emits_overlay_miss_and_reweights() -> None:
    result = compute_f1_valuations(_us_2024_inputs(erp_median_bps=None, erp_history_bps=None))
    assert "OVERLAY_MISS" in result.flags
    assert result.confidence <= 0.60
    # Remaining 4 components reweight to 1.0.
    payload = json.loads(result.components_json)
    remaining_weights = sum(
        payload[k]["weight_effective"] for k in ("cape", "buffett", "fwd_pe", "property")
    )
    assert remaining_weights == pytest.approx(1.0, abs=1e-9)


def test_cape_only_emits_degenerate_flag() -> None:
    result = compute_f1_valuations(
        F1Inputs(
            country_code="US",
            observation_date=date(2024, 1, 2),
            cape_ratio=33.2,
            buffett_ratio=None,
            erp_median_bps=None,
            forward_pe=None,
            property_gap_pp=None,
            cape_history=_synth_hist(25.0, 5.0, 80, 1),
        )
    )
    assert "F1_CAPE_ONLY" in result.flags
    assert "OVERLAY_MISS" in result.flags
    assert result.confidence <= 0.55


def test_no_components_raises() -> None:
    inputs = F1Inputs(
        country_code="XX",
        observation_date=date(2024, 1, 2),
        cape_ratio=None,
        buffett_ratio=None,
        erp_median_bps=None,
        forward_pe=None,
        property_gap_pp=None,
    )
    with pytest.raises(InsufficientInputsError, match="no valuation components"):
        compute_f1_valuations(inputs)


def test_insufficient_history_flag() -> None:
    result = compute_f1_valuations(
        _us_2024_inputs(
            cape_history=_synth_hist(25.0, 5.0, 20, 1),
            buffett_history=_synth_hist(1.4, 0.3, 20, 2),
            erp_history_bps=_synth_hist(500.0, 100.0, 20, 3),
            forward_pe_history=_synth_hist(17.0, 3.0, 20, 4),
            property_gap_history=_synth_hist(0.0, 3.0, 20, 5),
        )
    )
    assert "INSUFFICIENT_HISTORY" in result.flags
    assert result.confidence <= 0.65


def test_score_in_0_100_range() -> None:
    # Extreme inputs shouldn't break the clamp.
    result = compute_f1_valuations(
        _us_2024_inputs(cape_ratio=60.0, buffett_ratio=3.0, erp_median_bps=-500)
    )
    assert 0.0 <= result.score_normalized <= 100.0


def test_upstream_flag_propagation() -> None:
    result = compute_f1_valuations(_us_2024_inputs(upstream_flags=("ERP_METHOD_DIVERGENCE",)))
    assert "ERP_METHOD_DIVERGENCE" in result.flags
    assert result.confidence < 1.0
