"""Tests for the regimes package scaffold (types + ABC + exceptions)."""

from __future__ import annotations

from datetime import date

import pytest

from sonar.regimes import (
    InsufficientL4DataError,
    InvalidMetaRegimeError,
    L5RegimeError,
    L5RegimeInputs,
    L5RegimeResult,
    MetaRegime,
    RegimeClassifier,
)
from sonar.regimes.types import (
    CccsSnapshot,
    EcsSnapshot,
    FcsSnapshot,
    MscSnapshot,
)


def _ecs(**overrides: object) -> EcsSnapshot:
    base: dict[str, object] = {
        "ecs_id": "ecs-us",
        "score": 55.0,
        "regime": "EXPANSION",
        "stagflation_active": False,
        "confidence": 0.85,
    }
    base.update(overrides)
    return EcsSnapshot(**base)  # type: ignore[arg-type]


def _cccs(**overrides: object) -> CccsSnapshot:
    base: dict[str, object] = {
        "cccs_id": "cccs-us",
        "score": 60.0,
        "regime": "RECOVERY",
        "boom_active": False,
        "confidence": 0.85,
    }
    base.update(overrides)
    return CccsSnapshot(**base)  # type: ignore[arg-type]


def _fcs(**overrides: object) -> FcsSnapshot:
    base: dict[str, object] = {
        "fcs_id": "fcs-us",
        "score": 62.0,
        "regime": "OPTIMISM",
        "bubble_warning_active": False,
        "confidence": 0.85,
    }
    base.update(overrides)
    return FcsSnapshot(**base)  # type: ignore[arg-type]


def _msc(**overrides: object) -> MscSnapshot:
    base: dict[str, object] = {
        "msc_id": "msc-us",
        "score": 58.0,
        "regime_3band": "NEUTRAL",
        "dilemma_active": False,
        "confidence": 0.85,
    }
    base.update(overrides)
    return MscSnapshot(**base)  # type: ignore[arg-type]


class TestMetaRegime:
    def test_six_values(self) -> None:
        values = {m.value for m in MetaRegime}
        assert values == {
            "overheating",
            "stagflation_risk",
            "late_cycle_bubble",
            "recession_risk",
            "soft_landing",
            "unclassified",
        }

    def test_str_enum_comparison(self) -> None:
        # MetaRegime inherits str, so string equality works.
        assert MetaRegime.OVERHEATING == "overheating"


class TestAvailableCount:
    def test_all_four(self) -> None:
        inputs = L5RegimeInputs(
            country_code="US",
            date=date(2024, 12, 31),
            ecs=_ecs(),
            cccs=_cccs(),
            fcs=_fcs(),
            msc=_msc(),
        )
        assert inputs.available_count() == 4
        assert inputs.missing_flags() == ()

    def test_three_ecs_missing(self) -> None:
        inputs = L5RegimeInputs(
            country_code="US",
            date=date(2024, 12, 31),
            cccs=_cccs(),
            fcs=_fcs(),
            msc=_msc(),
        )
        assert inputs.available_count() == 3
        assert inputs.missing_flags() == ("L5_ECS_MISSING",)

    def test_two_only(self) -> None:
        inputs = L5RegimeInputs(
            country_code="US",
            date=date(2024, 12, 31),
            cccs=_cccs(),
            fcs=_fcs(),
        )
        assert inputs.available_count() == 2
        assert set(inputs.missing_flags()) == {"L5_ECS_MISSING", "L5_MSC_MISSING"}

    def test_none_available(self) -> None:
        inputs = L5RegimeInputs(country_code="US", date=date(2024, 12, 31))
        assert inputs.available_count() == 0
        assert set(inputs.missing_flags()) == {
            "L5_ECS_MISSING",
            "L5_CCCS_MISSING",
            "L5_FCS_MISSING",
            "L5_MSC_MISSING",
        }


class TestL5RegimeResult:
    def test_default_methodology_version(self) -> None:
        result = L5RegimeResult(
            country_code="US",
            date=date(2024, 12, 31),
            meta_regime=MetaRegime.SOFT_LANDING,
            ecs_id="ecs-1",
            cccs_id="cccs-1",
            fcs_id="fcs-1",
            msc_id="msc-1",
            confidence=0.85,
            flags=("L5_SOFT_LANDING",),
            classification_reason="expansion+neutral",
        )
        assert result.methodology_version == "L5_META_REGIME_v0.1"


class TestABC:
    def test_abc_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError, match="abstract"):
            RegimeClassifier()  # type: ignore[abstract]

    def test_subclass_requires_classify(self) -> None:
        class _Incomplete(RegimeClassifier):
            METHODOLOGY_VERSION = "TEST_v0.0"

        with pytest.raises(TypeError, match="abstract"):
            _Incomplete()  # type: ignore[abstract]

    def test_concrete_subclass_instantiates(self) -> None:
        class _Concrete(RegimeClassifier):
            METHODOLOGY_VERSION = "TEST_v0.0"

            def classify(self, inputs: L5RegimeInputs) -> L5RegimeResult:
                return L5RegimeResult(
                    country_code=inputs.country_code,
                    date=inputs.date,
                    meta_regime=MetaRegime.UNCLASSIFIED,
                    ecs_id=None,
                    cccs_id=None,
                    fcs_id=None,
                    msc_id=None,
                    confidence=0.0,
                )

        classifier = _Concrete()
        assert classifier.METHODOLOGY_VERSION == "TEST_v0.0"


class TestExceptions:
    def test_hierarchy(self) -> None:
        assert issubclass(InsufficientL4DataError, L5RegimeError)
        assert issubclass(InvalidMetaRegimeError, L5RegimeError)

    def test_insufficient_l4_data_carries_message(self) -> None:
        exc = InsufficientL4DataError("got 2/4")
        assert "2/4" in str(exc)
