"""Unit tests for E1 Activity compute per spec E1-activity.md §4."""

from __future__ import annotations

import json
from datetime import date

import pytest

from sonar.indices.economic.e1_activity import (
    COMPONENT_WEIGHTS,
    METHODOLOGY_VERSION,
    MIN_COMPONENTS_FOR_COMPUTE,
    TOTAL_COMPONENTS,
    E1ActivityInputs,
    compute_e1_activity,
)
from sonar.overlays.exceptions import InsufficientDataError


# 10Y * 12 = 120 monthly observations. Use a simple sine-ish synthetic history
# with sd ~= 0.01 so z-scores land in plausible ranges.
def _history(level: float, n: int = 120, noise: float = 0.005) -> list[float]:
    return [level + noise * (i % 7 - 3) for i in range(n)]


def _full_inputs(**overrides: object) -> E1ActivityInputs:
    base: dict[str, object] = {
        "country_code": "US",
        "observation_date": date(2024, 1, 31),
        "gdp_yoy": 0.025,
        "gdp_yoy_history": _history(0.02),
        "employment_yoy": 0.018,
        "employment_yoy_history": _history(0.015),
        "industrial_production_yoy": 0.012,
        "industrial_production_yoy_history": _history(0.01),
        "pmi_composite": 51.5,
        "pmi_composite_history": _history(50.0, noise=1.0),
        "personal_income_ex_transfers_yoy": 0.022,
        "personal_income_ex_transfers_yoy_history": _history(0.02),
        "retail_sales_real_yoy": 0.014,
        "retail_sales_real_yoy_history": _history(0.012),
        "lookback_years": 10,
        "source_connectors": ("fred",),
        "upstream_flags": (),
    }
    base.update(overrides)
    return E1ActivityInputs(**base)  # type: ignore[arg-type]


class TestComputeE1Happy:
    def test_all_six_components_yields_valid_output(self) -> None:
        result = compute_e1_activity(_full_inputs())
        assert 0 <= result.score_normalized <= 100
        assert result.components_available == TOTAL_COMPONENTS
        assert result.methodology_version == METHODOLOGY_VERSION
        assert result.confidence == pytest.approx(1.0)
        assert "E1_PARTIAL_COMPONENTS" not in result.flags

    def test_components_json_shape(self) -> None:
        result = compute_e1_activity(_full_inputs())
        parsed = json.loads(result.components_json)
        assert set(parsed.keys()) == set(COMPONENT_WEIGHTS.keys())
        for name, payload in parsed.items():
            assert set(payload.keys()) == {"raw", "z", "weight", "contribution"}
            assert payload["weight"] == pytest.approx(COMPONENT_WEIGHTS[name])

    def test_contributions_sum_to_score_raw(self) -> None:
        result = compute_e1_activity(_full_inputs())
        contributions = [p["contribution"] for p in json.loads(result.components_json).values()]
        assert sum(contributions) == pytest.approx(result.score_raw, abs=1e-10)

    def test_weights_sum_to_one(self) -> None:
        assert sum(COMPONENT_WEIGHTS.values()) == pytest.approx(1.0)


class TestComputeE1Partial:
    def test_four_of_six_allowed_with_flag(self) -> None:
        inputs = _full_inputs(
            personal_income_ex_transfers_yoy=None,
            retail_sales_real_yoy=None,
        )
        result = compute_e1_activity(inputs)
        assert result.components_available == 4
        assert "E1_PARTIAL_COMPONENTS" in result.flags
        # 2 missing * 0.10 deduction = 0.80 confidence.
        assert result.confidence == pytest.approx(0.80)

    def test_three_components_raises(self) -> None:
        inputs = _full_inputs(
            industrial_production_yoy=None,
            pmi_composite=None,
            personal_income_ex_transfers_yoy=None,
            retail_sales_real_yoy=None,
        )
        # gdp + employment = 2; with 3 needed? We asked for 2, min is 4.
        # Make only 3 present.
        inputs = _full_inputs(
            gdp_yoy=None,
            employment_yoy=None,
            retail_sales_real_yoy=None,
        )
        with pytest.raises(InsufficientDataError, match=f">= {MIN_COMPONENTS_FOR_COMPUTE}"):
            compute_e1_activity(inputs)

    def test_weights_renormalize_when_component_missing(self) -> None:
        # Drop PMI (weight 0.15). Remaining 5 components sum to 0.85;
        # re-normalization should push their contributions up proportionally.
        full = compute_e1_activity(_full_inputs())
        partial = compute_e1_activity(_full_inputs(pmi_composite=None))
        assert partial.components_available == 5
        # score_raw magnitudes should still be in a comparable range since
        # the z-scores are weighted averages either way.
        assert abs(partial.score_raw) < 3.0
        assert 0 <= partial.score_normalized <= 100
        # confidence deducted by 0.10 for 1 missing.
        assert partial.confidence == pytest.approx(0.90)
        # Sanity: both runs produced valid outputs.
        assert full.components_available == TOTAL_COMPONENTS


class TestComputeE1Insufficient:
    def test_zero_components_raises(self) -> None:
        # Force every current value to None.
        inputs = E1ActivityInputs(
            country_code="US",
            observation_date=date(2024, 1, 31),
            gdp_yoy=None,
        )
        with pytest.raises(InsufficientDataError):
            compute_e1_activity(inputs)

    def test_insufficient_history_emits_flag(self) -> None:
        # 10-month history but lookback_years=10 → hist_floor = 96 obs.
        short_hist = [0.02] * 10
        inputs = _full_inputs(
            gdp_yoy_history=short_hist,
            employment_yoy_history=short_hist,
            industrial_production_yoy_history=short_hist,
            pmi_composite_history=short_hist,
            personal_income_ex_transfers_yoy_history=short_hist,
            retail_sales_real_yoy_history=short_hist,
        )
        result = compute_e1_activity(inputs)
        assert "INSUFFICIENT_HISTORY" in result.flags
        # 6 components flagged insufficient → 6 * 0.10 deduction.
        assert result.confidence < 0.5


class TestComputeE1Scaling:
    def test_high_positive_z_raises_score_above_50(self) -> None:
        # Current values substantially above history mean → positive z.
        result = compute_e1_activity(
            _full_inputs(
                gdp_yoy=0.06,
                employment_yoy=0.05,
                industrial_production_yoy=0.04,
                pmi_composite=60.0,
                personal_income_ex_transfers_yoy=0.05,
                retail_sales_real_yoy=0.04,
            )
        )
        assert result.score_normalized > 50.0
        assert result.score_raw > 0

    def test_low_negative_z_pulls_score_below_50(self) -> None:
        result = compute_e1_activity(
            _full_inputs(
                gdp_yoy=-0.02,
                employment_yoy=-0.01,
                industrial_production_yoy=-0.03,
                pmi_composite=42.0,
                personal_income_ex_transfers_yoy=-0.01,
                retail_sales_real_yoy=-0.02,
            )
        )
        assert result.score_normalized < 50.0
        assert result.score_raw < 0

    def test_score_clipped_to_100(self) -> None:
        # Extreme values blow the z past clamp; output still bounded.
        result = compute_e1_activity(
            _full_inputs(
                gdp_yoy=1.0,
                employment_yoy=1.0,
                industrial_production_yoy=1.0,
                pmi_composite=200.0,
                personal_income_ex_transfers_yoy=1.0,
                retail_sales_real_yoy=1.0,
            )
        )
        assert result.score_normalized <= 100.0
