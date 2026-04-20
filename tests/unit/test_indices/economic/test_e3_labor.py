"""Unit tests for E3 Labor compute per spec E3-labor.md §4."""

from __future__ import annotations

import json
from datetime import date

import pytest

from sonar.indices.economic.e3_labor import (
    COMPONENT_WEIGHTS,
    INVERTED_SIGN_COMPONENTS,
    METHODOLOGY_VERSION,
    MIN_COMPONENTS_FOR_COMPUTE,
    SAHM_TRIGGER_THRESHOLD,
    TOTAL_COMPONENTS,
    E3LaborInputs,
    _compute_sahm,
    compute_e3_labor,
)
from sonar.overlays.exceptions import InsufficientDataError


def _ur_history(n: int = 150, base: float = 0.04, trend: float = 0.0) -> list[float]:
    """Synthetic unemployment-rate history with optional trend."""
    return [base + trend * i + 0.001 * (i % 5 - 2) for i in range(n)]


def _hist(level: float, n: int = 120, noise: float = 0.002) -> list[float]:
    return [level + noise * (i % 7 - 3) for i in range(n)]


def _full_us_inputs(**overrides: object) -> E3LaborInputs:
    base: dict[str, object] = {
        "country_code": "US",
        "observation_date": date(2024, 1, 31),
        "unemployment_rate": 0.037,
        "unemployment_rate_history": _ur_history(),
        "unemployment_rate_12m_change": -0.002,
        "employment_population_ratio_12m_z": 0.002,
        "employment_population_ratio_12m_z_history": _hist(0.0),
        "prime_age_lfpr_12m_change": 0.003,
        "prime_age_lfpr_12m_change_history": _hist(0.0),
        "eci_yoy_growth": 0.042,
        "eci_yoy_growth_history": _hist(0.035),
        "atlanta_fed_wage_yoy": 0.045,
        "atlanta_fed_wage_yoy_history": _hist(0.04),
        "openings_unemployed_ratio": 1.35,
        "openings_unemployed_ratio_history": _hist(1.2, noise=0.05),
        "quits_rate": 0.022,
        "quits_rate_history": _hist(0.025),
        "initial_claims_4wk_avg": 235.0,
        "initial_claims_4wk_avg_history": _hist(240.0, noise=10.0),
        "temp_help_employment_yoy": -0.015,
        "temp_help_employment_yoy_history": _hist(0.0, noise=0.01),
        "lookback_years": 10,
        "source_connectors": ("fred",),
        "upstream_flags": (),
    }
    base.update(overrides)
    return E3LaborInputs(**base)  # type: ignore[arg-type]


class TestSahmRule:
    def test_short_history_returns_none(self) -> None:
        value, triggered = _compute_sahm([0.04, 0.041])
        assert value is None
        assert triggered == 0

    def test_stable_series_not_triggered(self) -> None:
        ur = [0.04] * 40
        value, triggered = _compute_sahm(ur)
        assert value is not None
        assert value == pytest.approx(0.0, abs=1e-12)
        assert triggered == 0

    def test_half_pp_rise_triggers(self) -> None:
        # Stable 4% for 30 months then +0.7pp spike in last 4 months.
        ur = [0.04] * 30 + [0.047] * 4
        value, triggered = _compute_sahm(ur)
        assert value is not None
        assert value >= SAHM_TRIGGER_THRESHOLD
        assert triggered == 1


class TestComputeE3Happy:
    def test_full_10_components(self) -> None:
        result = compute_e3_labor(_full_us_inputs())
        assert 0 <= result.score_normalized <= 100
        assert result.components_available == TOTAL_COMPONENTS
        assert result.methodology_version == METHODOLOGY_VERSION
        assert result.sahm_triggered == 0
        assert result.confidence == pytest.approx(1.0)
        assert "E3_PARTIAL_COMPONENTS" not in result.flags

    def test_weights_sum_to_one(self) -> None:
        assert sum(COMPONENT_WEIGHTS.values()) == pytest.approx(1.0)

    def test_inverted_components_declared(self) -> None:
        assert (
            frozenset({"sahm_rule_value", "unemployment_rate_12m_change", "initial_claims_4wk_avg"})
            == INVERTED_SIGN_COMPONENTS
        )

    def test_components_json_contains_sahm_trigger(self) -> None:
        result = compute_e3_labor(_full_us_inputs())
        parsed = json.loads(result.components_json)
        assert "trigger" in parsed["sahm_rule_value"]

    def test_contributions_sum_to_score_raw(self) -> None:
        result = compute_e3_labor(_full_us_inputs())
        contributions = [p["contribution"] for p in json.loads(result.components_json).values()]
        assert sum(contributions) == pytest.approx(result.score_raw, abs=1e-10)


class TestSahmTriggered:
    def test_spike_triggers_penalty(self) -> None:
        # UR history stable then 0.7pp spike.
        spike_history = [0.04] * 60 + [0.047] * 4
        result = compute_e3_labor(
            _full_us_inputs(
                unemployment_rate=0.047,
                unemployment_rate_history=spike_history,
            )
        )
        assert result.sahm_triggered == 1
        assert "E3_SAHM_TRIGGERED" in result.flags
        assert result.sahm_value is not None
        assert result.sahm_value >= SAHM_TRIGGER_THRESHOLD


class TestComputeE3Degraded:
    def test_ea_style_missing_us_only_components(self) -> None:
        """EA country degrades to 6/10 components — should still compute."""
        inputs = _full_us_inputs(
            country_code="DE",
            openings_unemployed_ratio=None,
            quits_rate=None,
            initial_claims_4wk_avg=None,
            atlanta_fed_wage_yoy=None,
        )
        result = compute_e3_labor(inputs)
        assert result.components_available == 6
        assert "E3_PARTIAL_COMPONENTS" in result.flags
        assert "JOLTS_US_ONLY" in result.flags
        assert "CLAIMS_US_ONLY" in result.flags
        assert "ATLANTA_FED_US_ONLY" in result.flags

    def test_below_threshold_raises(self) -> None:
        inputs = _full_us_inputs(
            openings_unemployed_ratio=None,
            quits_rate=None,
            initial_claims_4wk_avg=None,
            atlanta_fed_wage_yoy=None,
            temp_help_employment_yoy=None,
        )
        # 5 components remaining — below threshold.
        with pytest.raises(InsufficientDataError, match=f">= {MIN_COMPONENTS_FOR_COMPUTE}"):
            compute_e3_labor(inputs)


class TestComputeE3ScoreDirection:
    def test_sahm_triggered_pushes_score_down(self) -> None:
        stable = compute_e3_labor(_full_us_inputs())
        spike = compute_e3_labor(
            _full_us_inputs(
                unemployment_rate=0.047,
                unemployment_rate_history=[0.04] * 60 + [0.047] * 4,
            )
        )
        assert spike.score_raw < stable.score_raw
