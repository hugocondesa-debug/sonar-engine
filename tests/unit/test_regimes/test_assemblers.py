"""Unit tests for :mod:`sonar.regimes.assemblers` (Sprint K C1)."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import TYPE_CHECKING

from sonar.regimes.assemblers import (
    build_cccs_snapshot,
    build_ecs_snapshot,
    build_fcs_snapshot,
    build_l5_inputs_from_cycles_result,
    build_msc_snapshot,
)

if TYPE_CHECKING:
    from typing import Any


ANCHOR = date(2024, 12, 31)


# ---------------------------------------------------------------------------
# Test doubles — light SimpleNamespaces mimicking the L4 result dataclasses.
# The assemblers read attribute names, not the concrete classes, so duck
# typing keeps the tests decoupled from the compute-layer imports.
# ---------------------------------------------------------------------------


def _ecs_result() -> Any:
    return SimpleNamespace(
        ecs_id="ecs-abc",
        score_0_100=58.5,
        regime="PEAK_ZONE",
        stagflation_overlay_active=1,
        confidence=0.82,
    )


def _cccs_result() -> Any:
    return SimpleNamespace(
        cccs_id="cccs-abc",
        score_0_100=72.1,
        regime="BOOM",
        boom_overlay_active=1,
        confidence=0.78,
    )


def _fcs_result() -> Any:
    return SimpleNamespace(
        fcs_id="fcs-abc",
        score_0_100=61.0,
        regime="OPTIMISM",
        bubble_warning_active=0,
        confidence=0.80,
    )


def _msc_result() -> Any:
    return SimpleNamespace(
        msc_id="msc-abc",
        score_0_100=55.0,
        regime_3band="NEUTRAL",
        dilemma_overlay_active=0,
        confidence=0.85,
    )


def _orchestration_result(
    *,
    ecs: Any = None,
    cccs: Any = None,
    fcs: Any = None,
    msc: Any = None,
) -> Any:
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
# Per-cycle snapshot helpers
# ---------------------------------------------------------------------------


class TestPerCycleBuilders:
    def test_ecs_snapshot_populated(self) -> None:
        snap = build_ecs_snapshot(_ecs_result())
        assert snap is not None
        assert snap.ecs_id == "ecs-abc"
        assert snap.score == 58.5
        assert snap.regime == "PEAK_ZONE"
        assert snap.stagflation_active is True  # int(1) → bool(True)
        assert snap.confidence == 0.82

    def test_ecs_snapshot_none_passthrough(self) -> None:
        assert build_ecs_snapshot(None) is None

    def test_cccs_snapshot_boom_active_bool_coercion(self) -> None:
        snap = build_cccs_snapshot(_cccs_result())
        assert snap is not None
        assert snap.boom_active is True

    def test_cccs_snapshot_boom_active_zero(self) -> None:
        r = _cccs_result()
        r.boom_overlay_active = 0
        snap = build_cccs_snapshot(r)
        assert snap is not None
        assert snap.boom_active is False

    def test_fcs_snapshot_populated(self) -> None:
        snap = build_fcs_snapshot(_fcs_result())
        assert snap is not None
        assert snap.regime == "OPTIMISM"
        assert snap.bubble_warning_active is False

    def test_msc_snapshot_reads_regime_3band(self) -> None:
        snap = build_msc_snapshot(_msc_result())
        assert snap is not None
        assert snap.regime_3band == "NEUTRAL"
        assert snap.dilemma_active is False


# ---------------------------------------------------------------------------
# Composite assembler
# ---------------------------------------------------------------------------


class TestBuildL5Inputs:
    def test_all_four_cycles_present(self) -> None:
        inputs = build_l5_inputs_from_cycles_result(
            "US",
            ANCHOR,
            _orchestration_result(
                ecs=_ecs_result(),
                cccs=_cccs_result(),
                fcs=_fcs_result(),
                msc=_msc_result(),
            ),
        )
        assert inputs.country_code == "US"
        assert inputs.date == ANCHOR
        assert inputs.available_count() == 4
        assert inputs.ecs is not None
        assert inputs.cccs is not None
        assert inputs.fcs is not None
        assert inputs.msc is not None

    def test_one_cycle_missing_snapshot_none(self) -> None:
        inputs = build_l5_inputs_from_cycles_result(
            "US",
            ANCHOR,
            _orchestration_result(
                ecs=_ecs_result(),
                cccs=_cccs_result(),
                fcs=_fcs_result(),
                msc=None,
            ),
        )
        assert inputs.available_count() == 3
        assert inputs.msc is None
        assert "L5_MSC_MISSING" in inputs.missing_flags()

    def test_three_cycles_missing_snapshots_none(self) -> None:
        """Only 1/4 cycles — classifier will raise InsufficientL4DataError."""
        inputs = build_l5_inputs_from_cycles_result(
            "US",
            ANCHOR,
            _orchestration_result(
                ecs=_ecs_result(),
            ),
        )
        assert inputs.available_count() == 1
        assert inputs.cccs is None
        assert inputs.fcs is None
        assert inputs.msc is None
        flags = inputs.missing_flags()
        assert "L5_CCCS_MISSING" in flags
        assert "L5_FCS_MISSING" in flags
        assert "L5_MSC_MISSING" in flags
        assert "L5_ECS_MISSING" not in flags

    def test_all_none_empty_bundle(self) -> None:
        inputs = build_l5_inputs_from_cycles_result(
            "DE",
            ANCHOR,
            _orchestration_result(),
        )
        assert inputs.country_code == "DE"
        assert inputs.available_count() == 0
        assert len(inputs.missing_flags()) == 4
