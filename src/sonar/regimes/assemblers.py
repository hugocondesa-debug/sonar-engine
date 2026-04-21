"""L5 input assemblers — build :class:`L5RegimeInputs` from L4 outputs.

Sprint H shipped the Snapshot dataclasses + classifier. This module
is the glue that translates ``CyclesOrchestrationResult`` (the
L4 compute output) into the Snapshot view the classifier consumes.

Design choice (Sprint K Commit 1):

- **Option A** (chosen): assemble Snapshots from the in-memory
  orchestrator result. Avoids a DB round-trip, preserves type
  coupling to the compute-layer dataclasses, and keeps the pipeline's
  L4 → L5 flow synchronous.
- **Option B** (rejected): persist the cycle rows, re-read from the
  DB, then snapshot. Adds latency for no correctness benefit —
  ``persist_{cccs,fcs,msc,ecs}_result`` already wrote the rows with
  the same field values that live on the ``*ComputedResult``
  dataclasses.

Each per-cycle helper converts the integer overlay flags
(``boom_overlay_active``, ``stagflation_overlay_active`` …) to ``bool``
at the Snapshot boundary to match the classifier's predicate
expectations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from sonar.regimes.types import (
    CccsSnapshot,
    EcsSnapshot,
    FcsSnapshot,
    L5RegimeInputs,
    MscSnapshot,
)

if TYPE_CHECKING:
    from datetime import date

    from sonar.cycles.credit_cccs import CccsComputedResult
    from sonar.cycles.economic_ecs import EcsComputedResult
    from sonar.cycles.financial_fcs import FcsComputedResult
    from sonar.cycles.monetary_msc import MscComputedResult
    from sonar.cycles.orchestrator import CyclesOrchestrationResult
    from sonar.db.models import (
        CreditCycleScore,
        EconomicCycleScore,
        FinancialCycleScore,
        MonetaryCycleScore,
    )
    from sonar.regimes.types import CccsRegime, EcsRegime, FcsRegime, MscRegime3Band

__all__ = [
    "build_cccs_snapshot",
    "build_cccs_snapshot_from_orm",
    "build_ecs_snapshot",
    "build_ecs_snapshot_from_orm",
    "build_fcs_snapshot",
    "build_fcs_snapshot_from_orm",
    "build_l5_inputs_from_cycles_result",
    "build_l5_inputs_from_snapshots",
    "build_msc_snapshot",
    "build_msc_snapshot_from_orm",
]


def build_ecs_snapshot(result: EcsComputedResult | None) -> EcsSnapshot | None:
    """Minimal ECS view from the L4 compute result. ``None`` pass-through."""
    if result is None:
        return None
    return EcsSnapshot(
        ecs_id=result.ecs_id,
        score=float(result.score_0_100),
        regime=cast("EcsRegime", result.regime),
        stagflation_active=bool(result.stagflation_overlay_active),
        confidence=float(result.confidence),
    )


def build_cccs_snapshot(result: CccsComputedResult | None) -> CccsSnapshot | None:
    """Minimal CCCS view from the L4 compute result."""
    if result is None:
        return None
    return CccsSnapshot(
        cccs_id=result.cccs_id,
        score=float(result.score_0_100),
        regime=cast("CccsRegime", result.regime),
        boom_active=bool(result.boom_overlay_active),
        confidence=float(result.confidence),
    )


def build_fcs_snapshot(result: FcsComputedResult | None) -> FcsSnapshot | None:
    """Minimal FCS view from the L4 compute result."""
    if result is None:
        return None
    return FcsSnapshot(
        fcs_id=result.fcs_id,
        score=float(result.score_0_100),
        regime=cast("FcsRegime", result.regime),
        bubble_warning_active=bool(result.bubble_warning_active),
        confidence=float(result.confidence),
    )


def build_msc_snapshot(result: MscComputedResult | None) -> MscSnapshot | None:
    """Minimal MSC view — takes the 3-band regime column."""
    if result is None:
        return None
    return MscSnapshot(
        msc_id=result.msc_id,
        score=float(result.score_0_100),
        regime_3band=cast("MscRegime3Band", result.regime_3band),
        dilemma_active=bool(result.dilemma_overlay_active),
        confidence=float(result.confidence),
    )


def build_l5_inputs_from_cycles_result(
    country_code: str,
    observation_date: date,
    result: CyclesOrchestrationResult,
) -> L5RegimeInputs:
    """Assemble :class:`L5RegimeInputs` from a :class:`CyclesOrchestrationResult`.

    Any cycle that the orchestrator marked as skipped (``None`` slot in
    ``result``) propagates as ``None`` into the Snapshot bundle. The
    classifier enforces the ≥ 3/4 Policy-1 threshold downstream via
    :class:`sonar.regimes.exceptions.InsufficientL4DataError`.
    """
    return L5RegimeInputs(
        country_code=country_code,
        date=observation_date,
        ecs=build_ecs_snapshot(result.ecs),
        cccs=build_cccs_snapshot(result.cccs),
        fcs=build_fcs_snapshot(result.fcs),
        msc=build_msc_snapshot(result.msc),
    )


# ---------------------------------------------------------------------------
# ORM → Snapshot helpers (used by the backfill script; same field
# conventions as the in-memory ``*ComputedResult`` helpers above).
# ---------------------------------------------------------------------------


def build_ecs_snapshot_from_orm(row: EconomicCycleScore | None) -> EcsSnapshot | None:
    """Build :class:`EcsSnapshot` from a persisted ``economic_cycle_scores`` row."""
    if row is None:
        return None
    return EcsSnapshot(
        ecs_id=str(row.ecs_id),
        score=float(row.score_0_100),
        regime=cast("EcsRegime", row.regime),
        stagflation_active=bool(row.stagflation_overlay_active),
        confidence=float(row.confidence),
    )


def build_cccs_snapshot_from_orm(row: CreditCycleScore | None) -> CccsSnapshot | None:
    """Build :class:`CccsSnapshot` from a persisted ``credit_cycle_scores`` row."""
    if row is None:
        return None
    return CccsSnapshot(
        cccs_id=str(row.cccs_id),
        score=float(row.score_0_100),
        regime=cast("CccsRegime", row.regime),
        boom_active=bool(row.boom_overlay_active),
        confidence=float(row.confidence),
    )


def build_fcs_snapshot_from_orm(row: FinancialCycleScore | None) -> FcsSnapshot | None:
    """Build :class:`FcsSnapshot` from a persisted ``financial_cycle_scores`` row."""
    if row is None:
        return None
    return FcsSnapshot(
        fcs_id=str(row.fcs_id),
        score=float(row.score_0_100),
        regime=cast("FcsRegime", row.regime),
        bubble_warning_active=bool(row.bubble_warning_active),
        confidence=float(row.confidence),
    )


def build_msc_snapshot_from_orm(row: MonetaryCycleScore | None) -> MscSnapshot | None:
    """Build :class:`MscSnapshot` from a persisted ``monetary_cycle_scores`` row."""
    if row is None:
        return None
    return MscSnapshot(
        msc_id=str(row.msc_id),
        score=float(row.score_0_100),
        regime_3band=cast("MscRegime3Band", row.regime_3band),
        dilemma_active=bool(row.dilemma_overlay_active),
        confidence=float(row.confidence),
    )


def build_l5_inputs_from_snapshots(
    country_code: str,
    observation_date: date,
    *,
    ecs: EcsSnapshot | None,
    cccs: CccsSnapshot | None,
    fcs: FcsSnapshot | None,
    msc: MscSnapshot | None,
) -> L5RegimeInputs:
    """Thin constructor wrapper for pre-built Snapshot tuples.

    Used by the backfill script (:mod:`sonar.scripts.backfill_l5`),
    which reads persisted cycle rows and produces Snapshots directly
    rather than routing through ``CyclesOrchestrationResult``.
    """
    return L5RegimeInputs(
        country_code=country_code,
        date=observation_date,
        ecs=ecs,
        cccs=cccs,
        fcs=fcs,
        msc=msc,
    )
