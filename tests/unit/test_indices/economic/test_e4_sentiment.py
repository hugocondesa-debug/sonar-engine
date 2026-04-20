"""Unit tests for E4 Sentiment compute per spec E4-sentiment.md §4."""

from __future__ import annotations

import json
from datetime import date

import pytest

from sonar.indices.economic.e4_sentiment import (
    COMPONENT_WEIGHTS,
    INVERTED_SIGN_COMPONENTS,
    METHODOLOGY_VERSION,
    MIN_COMPONENTS_FOR_COMPUTE,
    TOTAL_COMPONENTS,
    E4SentimentInputs,
    compute_e4_sentiment,
)
from sonar.overlays.exceptions import InsufficientDataError


def _hist(level: float, n: int = 120, noise: float = 1.0) -> list[float]:
    return [level + noise * (i % 7 - 3) for i in range(n)]


def _full_us_inputs(**overrides: object) -> E4SentimentInputs:
    base: dict[str, object] = {
        "country_code": "US",
        "observation_date": date(2024, 1, 31),
        "umich_sentiment_12m_change": 5.2,
        "umich_sentiment_12m_change_history": _hist(0.0, noise=2.0),
        "conference_board_confidence_12m_change": 3.1,
        "conference_board_confidence_12m_change_history": _hist(0.0, noise=1.5),
        "umich_5y_inflation_exp": 0.028,
        "umich_5y_inflation_exp_history": _hist(0.025, noise=0.003),
        "ism_manufacturing": 51.5,
        "ism_manufacturing_history": _hist(50.0, noise=1.5),
        "ism_services": 53.0,
        "ism_services_history": _hist(52.0, noise=1.5),
        "nfib_small_business": 93.0,
        "nfib_small_business_history": _hist(95.0, noise=2.0),
        "epu_index": 140.0,
        "epu_index_history": _hist(150.0, noise=20.0),
        "vix_level": 14.5,
        "vix_level_history": _hist(17.0, noise=5.0),
        "sloos_standards_net_pct": 12.5,
        "sloos_standards_net_pct_history": _hist(5.0, noise=10.0),
        # EA/JP components left None for US.
        "lookback_years": 10,
        "source_connectors": ("fred",),
        "upstream_flags": (),
    }
    base.update(overrides)
    return E4SentimentInputs(**base)  # type: ignore[arg-type]


def _full_de_inputs(**overrides: object) -> E4SentimentInputs:
    base: dict[str, object] = {
        "country_code": "DE",
        "observation_date": date(2024, 1, 31),
        "umich_5y_inflation_exp": 0.025,
        "umich_5y_inflation_exp_history": _hist(0.025, noise=0.003),
        "ec_esi": 96.5,
        "ec_esi_history": _hist(100.0, noise=3.0),
        "zew_expectations": 15.2,
        "zew_expectations_history": _hist(0.0, noise=10.0),
        "ifo_business_climate": 86.0,
        "ifo_business_climate_history": _hist(95.0, noise=3.0),
        "vix_level": 14.5,
        "vix_level_history": _hist(17.0, noise=5.0),
        "epu_index": 140.0,
        "epu_index_history": _hist(150.0, noise=20.0),
        "lookback_years": 10,
        "source_connectors": ("eurostat", "fred"),
        "upstream_flags": (),
    }
    base.update(overrides)
    return E4SentimentInputs(**base)  # type: ignore[arg-type]


class TestComputeE4Happy:
    def test_us_profile_yields_valid_output(self) -> None:
        result = compute_e4_sentiment(_full_us_inputs())
        assert 0 <= result.score_normalized <= 100
        assert result.components_available == 9  # 9 US-applicable components
        assert result.methodology_version == METHODOLOGY_VERSION

    def test_weights_sum_to_one(self) -> None:
        assert sum(COMPONENT_WEIGHTS.values()) == pytest.approx(1.0)

    def test_inverted_components_declared(self) -> None:
        assert (
            frozenset(
                {"umich_5y_inflation_exp", "epu_index", "vix_level", "sloos_standards_net_pct"}
            )
            == INVERTED_SIGN_COMPONENTS
        )

    def test_components_json_shape(self) -> None:
        result = compute_e4_sentiment(_full_us_inputs())
        parsed = json.loads(result.components_json)
        assert len(parsed) == 9
        for payload in parsed.values():
            assert set(payload.keys()) == {"raw", "z", "weight", "contribution"}

    def test_contributions_sum_to_score_raw(self) -> None:
        result = compute_e4_sentiment(_full_us_inputs())
        contributions = [p["contribution"] for p in json.loads(result.components_json).values()]
        assert sum(contributions) == pytest.approx(result.score_raw, abs=1e-10)


class TestComputeE4DE:
    def test_de_profile_six_components_passes_threshold(self) -> None:
        result = compute_e4_sentiment(_full_de_inputs())
        assert result.components_available == 6
        assert "E4_PARTIAL_COMPONENTS" in result.flags
        # 7 missing * 0.05 deduction = 0.65 confidence.
        assert result.confidence == pytest.approx(0.65)


class TestComputeE4Insufficient:
    def test_pt_style_below_threshold_raises(self) -> None:
        # PT-ish: only ESI + VIX + EPU = 3 → raises.
        inputs = E4SentimentInputs(
            country_code="PT",
            observation_date=date(2024, 1, 31),
            ec_esi=95.0,
            ec_esi_history=_hist(100.0),
            vix_level=14.5,
            vix_level_history=_hist(17.0, noise=5.0),
            epu_index=140.0,
            epu_index_history=_hist(150.0, noise=20.0),
        )
        with pytest.raises(InsufficientDataError, match=f">= {MIN_COMPONENTS_FOR_COMPUTE}"):
            compute_e4_sentiment(inputs)

    def test_zero_components_raises(self) -> None:
        inputs = E4SentimentInputs(country_code="US", observation_date=date(2024, 1, 31))
        with pytest.raises(InsufficientDataError):
            compute_e4_sentiment(inputs)


class TestComputeE4Sign:
    def test_vix_elevated_pulls_score_down(self) -> None:
        stable = compute_e4_sentiment(_full_us_inputs())
        scared = compute_e4_sentiment(_full_us_inputs(vix_level=35.0))
        # VIX inverted: high VIX → negative z → lower score.
        assert scared.score_raw < stable.score_raw

    def test_sloos_tightening_pulls_score_down(self) -> None:
        stable = compute_e4_sentiment(_full_us_inputs())
        tight = compute_e4_sentiment(_full_us_inputs(sloos_standards_net_pct=45.0))
        # SLOOS inverted: high tightening → negative z → lower score.
        assert tight.score_raw < stable.score_raw

    def test_inflation_expectations_elevated_pulls_score_down(self) -> None:
        stable = compute_e4_sentiment(_full_us_inputs())
        inflating = compute_e4_sentiment(_full_us_inputs(umich_5y_inflation_exp=0.045))
        assert inflating.score_raw < stable.score_raw


class TestComponentSet:
    def test_total_components_matches_weights(self) -> None:
        assert len(COMPONENT_WEIGHTS) == TOTAL_COMPONENTS
