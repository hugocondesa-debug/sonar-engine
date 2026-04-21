"""Sprint K C5 — L5 classification branches end-to-end via assemblers.

Each canonical fixture mirrors a scenario from
``docs/specs/regimes/cross-cycle-meta-regimes.md`` §7 but goes through
the full Sprint K wiring (L4 result shape → assemblers → classifier)
instead of hand-building Snapshot dataclasses. Catches regressions in
field-name mappings between compute-layer results and Snapshots.

Fixtures use :class:`types.SimpleNamespace` to mimic the
``*ComputedResult`` dataclasses — the assemblers read attribute names,
not concrete classes, so this keeps the tests decoupled from the
cycle-module imports.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from sonar.regimes import (
    L5RegimeInputs,
    MetaRegime,
    MetaRegimeClassifier,
)
from sonar.regimes.assemblers import build_l5_inputs_from_cycles_result

if TYPE_CHECKING:
    from typing import Any


pytestmark = pytest.mark.slow


ANCHOR = date(2024, 12, 31)


# ---------------------------------------------------------------------------
# Per-cycle SimpleNamespace factories — attribute names must match the
# ``*ComputedResult`` dataclasses the assemblers read.
# ---------------------------------------------------------------------------


def _ecs(
    ecs_id: str, score: float, regime: str, stagflation: int = 0, confidence: float = 0.85
) -> Any:
    return SimpleNamespace(
        ecs_id=ecs_id,
        score_0_100=score,
        regime=regime,
        stagflation_overlay_active=stagflation,
        confidence=confidence,
    )


def _cccs(cccs_id: str, score: float, regime: str, boom: int = 0, confidence: float = 0.85) -> Any:
    return SimpleNamespace(
        cccs_id=cccs_id,
        score_0_100=score,
        regime=regime,
        boom_overlay_active=boom,
        confidence=confidence,
    )


def _fcs(fcs_id: str, score: float, regime: str, bubble: int = 0, confidence: float = 0.85) -> Any:
    return SimpleNamespace(
        fcs_id=fcs_id,
        score_0_100=score,
        regime=regime,
        bubble_warning_active=bubble,
        confidence=confidence,
    )


def _msc(
    msc_id: str,
    score: float,
    regime_3band: str,
    dilemma: int = 0,
    confidence: float = 0.85,
) -> Any:
    return SimpleNamespace(
        msc_id=msc_id,
        score_0_100=score,
        regime_3band=regime_3band,
        dilemma_overlay_active=dilemma,
        confidence=confidence,
    )


def _orch(ecs: Any, cccs: Any, fcs: Any, msc: Any) -> Any:
    return SimpleNamespace(
        country_code="US",
        observation_date=ANCHOR,
        ecs=ecs,
        cccs=cccs,
        fcs=fcs,
        msc=msc,
        skips={},
    )


# ---------------------------------------------------------------------------
# Canonical fixtures — one per meta-regime branch
# ---------------------------------------------------------------------------


def _overheating_orchestration() -> Any:
    return _orch(
        _ecs("ecs-1", 75.0, "PEAK_ZONE"),
        _cccs("cccs-1", 78.0, "BOOM", boom=1),
        _fcs("fcs-1", 72.0, "OPTIMISM"),
        _msc("msc-1", 58.0, "NEUTRAL", dilemma=0),
    )


def _stagflation_risk_orchestration() -> Any:
    return _orch(
        _ecs("ecs-2", 48.0, "EARLY_RECESSION", stagflation=1),
        _cccs("cccs-2", 45.0, "REPAIR"),
        _fcs("fcs-2", 35.0, "STRESS"),
        _msc("msc-2", 72.0, "TIGHT", dilemma=1),
    )


def _late_cycle_bubble_orchestration() -> Any:
    return _orch(
        _ecs("ecs-3", 68.0, "PEAK_ZONE"),
        _cccs("cccs-3", 85.0, "SPECULATION", boom=1),
        _fcs("fcs-3", 92.0, "EUPHORIA", bubble=1),
        _msc("msc-3", 55.0, "NEUTRAL"),
    )


def _recession_risk_orchestration() -> Any:
    return _orch(
        _ecs("ecs-4", 25.0, "RECESSION"),
        _cccs("cccs-4", 20.0, "DISTRESS"),
        _fcs("fcs-4", 22.0, "STRESS"),
        _msc("msc-4", 28.0, "ACCOMMODATIVE"),
    )


def _soft_landing_orchestration() -> Any:
    return _orch(
        _ecs("ecs-5", 60.0, "EXPANSION"),
        _cccs("cccs-5", 58.0, "RECOVERY"),
        _fcs("fcs-5", 62.0, "OPTIMISM"),
        _msc("msc-5", 50.0, "NEUTRAL"),
    )


def _unclassified_orchestration() -> Any:
    # PEAK_ZONE ECS + REPAIR CCCS + CAUTION FCS — no branch matches.
    return _orch(
        _ecs("ecs-6", 65.0, "PEAK_ZONE"),
        _cccs("cccs-6", 42.0, "REPAIR"),
        _fcs("fcs-6", 55.0, "CAUTION"),
        _msc("msc-6", 52.0, "NEUTRAL"),
    )


# ---------------------------------------------------------------------------
# Parametrised end-to-end: orchestration result → assembler → classifier
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("factory", "expected_regime", "expected_reason"),
    [
        (_overheating_orchestration, MetaRegime.OVERHEATING, "peak+boom+optimism"),
        (_stagflation_risk_orchestration, MetaRegime.STAGFLATION_RISK, "stagflation+dilemma"),
        (
            _late_cycle_bubble_orchestration,
            MetaRegime.LATE_CYCLE_BUBBLE,
            "euphoria+bubble+speculation",
        ),
        (_recession_risk_orchestration, MetaRegime.RECESSION_RISK, "recession+distress"),
        (_soft_landing_orchestration, MetaRegime.SOFT_LANDING, "expansion+neutral"),
        (_unclassified_orchestration, MetaRegime.UNCLASSIFIED, "default"),
    ],
)
def test_classification_branch_via_assembler(
    factory: object,
    expected_regime: MetaRegime,
    expected_reason: str,
) -> None:
    """Each canonical branch must classify correctly after the assembler round-trip."""
    orch = factory()  # type: ignore[operator]
    inputs = build_l5_inputs_from_cycles_result("US", ANCHOR, orch)
    assert isinstance(inputs, L5RegimeInputs)
    assert inputs.available_count() == 4
    result = MetaRegimeClassifier().classify(inputs)
    assert result.meta_regime == expected_regime, (
        f"expected {expected_regime}, got {result.meta_regime} "
        f"(reason={result.classification_reason})"
    )
    assert result.classification_reason == expected_reason
    # Every branch emits its canonical L5_<REGIME> flag.
    canonical_flag = f"L5_{expected_regime.name}"
    assert canonical_flag in result.flags
