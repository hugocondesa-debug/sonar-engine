"""Unit tests for cycles.base — CycleResult + Policy 1 fail-mode."""

from __future__ import annotations

from datetime import date

import pytest

from sonar.cycles.base import (
    REWEIGHT_CONFIDENCE_CAP,
    CycleCompositeBase,
    CycleResult,
    InsufficientCycleInputsError,
    apply_policy_1,
)

CANONICAL_3 = {"A": 0.50, "B": 0.30, "C": 0.20}
CANONICAL_4 = {"F1": 0.30, "F2": 0.25, "F3": 0.25, "F4": 0.20}


class TestApplyPolicy1Happy:
    def test_all_available_no_reweighting(self) -> None:
        score, w_eff, flags, reweighted = apply_policy_1(
            {"A": 60.0, "B": 40.0, "C": 50.0},
            CANONICAL_3,
            min_required=2,
        )
        assert reweighted is False
        assert flags == []
        assert w_eff == pytest.approx({"A": 0.50, "B": 0.30, "C": 0.20})
        # 0.5*60 + 0.3*40 + 0.2*50 = 30 + 12 + 10 = 52
        assert score == pytest.approx(52.0)

    def test_weights_sum_to_one_after_reweighting(self) -> None:
        score, w_eff, flags, reweighted = apply_policy_1(
            {"A": 60.0, "B": 40.0, "C": None},
            CANONICAL_3,
            min_required=2,
        )
        assert reweighted is True
        assert sum(w_eff.values()) == pytest.approx(1.0)
        assert flags == ["C_MISSING"]
        # available weights sum = 0.8; effective A = 0.625, B = 0.375
        assert w_eff["A"] == pytest.approx(0.625)
        assert w_eff["B"] == pytest.approx(0.375)
        # 0.625*60 + 0.375*40 = 37.5 + 15 = 52.5
        assert score == pytest.approx(52.5)

    def test_single_missing_flags_sorted(self) -> None:
        _score, _w_eff, flags, _reweighted = apply_policy_1(
            {"F1": 70.0, "F2": None, "F3": None, "F4": 50.0},
            CANONICAL_4,
            min_required=2,
        )
        assert flags == ["F2_MISSING", "F3_MISSING"]


class TestApplyPolicy1Boundary:
    def test_below_min_raises(self) -> None:
        with pytest.raises(InsufficientCycleInputsError, match=">= 3"):
            apply_policy_1(
                {"A": 60.0, "B": None, "C": None},
                CANONICAL_3,
                min_required=3,
            )

    def test_exactly_min_passes(self) -> None:
        score, _w, _f, _r = apply_policy_1(
            {"A": 80.0, "B": None, "C": None},
            CANONICAL_3,
            min_required=1,
        )
        assert score == pytest.approx(80.0)

    def test_zero_available_raises(self) -> None:
        with pytest.raises(InsufficientCycleInputsError):
            apply_policy_1(
                {"A": None, "B": None, "C": None},
                CANONICAL_3,
                min_required=1,
            )


class TestApplyPolicy1KeyMismatch:
    def test_extra_key_in_values_raises(self) -> None:
        with pytest.raises(KeyError):
            apply_policy_1({"A": 1.0, "B": 2.0, "C": 3.0, "D": 4.0}, CANONICAL_3, min_required=1)

    def test_missing_key_in_values_raises(self) -> None:
        with pytest.raises(KeyError):
            apply_policy_1({"A": 1.0, "B": 2.0}, CANONICAL_3, min_required=1)


class TestCycleResult:
    def test_default_construction(self) -> None:
        result = CycleResult(
            country_code="US",
            date=date(2024, 1, 31),
            cycle_type="CCCS",
            methodology_version="CCCS_COMPOSITE_v0.1",
            score_composite=65.0,
            confidence=0.85,
        )
        assert result.cycle_type == "CCCS"
        assert result.sub_index_contributions == {}
        assert result.flags == ()

    def test_flags_tuple_immutable(self) -> None:
        result = CycleResult(
            country_code="US",
            date=date(2024, 1, 31),
            cycle_type="FCS",
            methodology_version="FCS_COMPOSITE_v0.1",
            score_composite=60.0,
            confidence=0.80,
            flags=("F4_MARGIN_MISSING",),
        )
        assert result.flags == ("F4_MARGIN_MISSING",)


class TestCycleCompositeBaseABC:
    def test_compute_not_implemented(self) -> None:
        base = CycleCompositeBase()
        with pytest.raises(NotImplementedError):
            base.compute("US", date(2024, 1, 31))

    def test_class_attrs_default_to_placeholders(self) -> None:
        assert CycleCompositeBase.cycle_type == "BASE"
        assert CycleCompositeBase.methodology_version == "BASE_v0.1"


class TestReweightConfidenceCap:
    def test_cap_value_matches_spec(self) -> None:
        # Spec: reweight_confidence_cap = 0.75 per CCCS §2 + FCS Policy 1
        assert pytest.approx(0.75) == REWEIGHT_CONFIDENCE_CAP
