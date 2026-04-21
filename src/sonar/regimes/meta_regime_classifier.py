"""Rule-based 6-regime classifier — :mod:`sonar.regimes` canonical Phase 1 impl.

Implements the decision tree in
``docs/specs/regimes/cross-cycle-meta-regimes.md`` §3. Priority-ordered
(first match wins); missing cycle slots evaluate their predicates to
``False`` so the decision flows naturally toward less-specific
branches.

Phase 2+ may swap this classifier for an ML variant; interface is
:class:`sonar.regimes.base.RegimeClassifier` and the wire format is
versioned via :data:`METHODOLOGY_VERSION`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sonar.regimes.base import RegimeClassifier
from sonar.regimes.exceptions import InsufficientL4DataError
from sonar.regimes.types import L5RegimeResult, MetaRegime

if TYPE_CHECKING:
    from sonar.regimes.types import (
        CccsSnapshot,
        EcsSnapshot,
        FcsSnapshot,
        L5RegimeInputs,
        MscSnapshot,
    )


__all__ = ["MetaRegimeClassifier"]


MIN_L4_CYCLES: int = 3
CONFIDENCE_CAP_ONE_MISSING: float = 0.75
CONFIDENCE_CAP_TWO_MISSING: float = 0.60  # documented; unreachable (exception fires)


# Flag emitted for every regime (one per classification).
_REGIME_FLAG: dict[MetaRegime, str] = {
    MetaRegime.OVERHEATING: "L5_OVERHEATING",
    MetaRegime.STAGFLATION_RISK: "L5_STAGFLATION_RISK",
    MetaRegime.LATE_CYCLE_BUBBLE: "L5_LATE_CYCLE_BUBBLE",
    MetaRegime.RECESSION_RISK: "L5_RECESSION_RISK",
    MetaRegime.SOFT_LANDING: "L5_SOFT_LANDING",
    MetaRegime.UNCLASSIFIED: "L5_UNCLASSIFIED",
}


class MetaRegimeClassifier(RegimeClassifier):
    """Rule-based 6-regime classifier per spec §3."""

    METHODOLOGY_VERSION = "L5_META_REGIME_v0.1"

    def classify(self, inputs: L5RegimeInputs) -> L5RegimeResult:
        """Classify ``inputs`` → :class:`L5RegimeResult`.

        Raises :class:`InsufficientL4DataError` when fewer than
        :data:`MIN_L4_CYCLES` (3) of the 4 cycle slots are populated.
        """
        n_available = inputs.available_count()
        if n_available < MIN_L4_CYCLES:
            msg = f"L5 requires >= {MIN_L4_CYCLES}/4 L4 cycles; got {n_available}/4"
            raise InsufficientL4DataError(msg)

        meta_regime, reason = _classify(inputs)

        flags: list[str] = [_REGIME_FLAG[meta_regime]]
        flags.extend(inputs.missing_flags())

        confidence = _compute_confidence(inputs, n_available=n_available)

        return L5RegimeResult(
            country_code=inputs.country_code,
            date=inputs.date,
            meta_regime=meta_regime,
            ecs_id=inputs.ecs.ecs_id if inputs.ecs else None,
            cccs_id=inputs.cccs.cccs_id if inputs.cccs else None,
            fcs_id=inputs.fcs.fcs_id if inputs.fcs else None,
            msc_id=inputs.msc.msc_id if inputs.msc else None,
            confidence=confidence,
            flags=tuple(flags),
            classification_reason=reason,
            methodology_version=self.METHODOLOGY_VERSION,
        )


# ---------------------------------------------------------------------------
# Decision-tree helpers
# ---------------------------------------------------------------------------


def _classify(inputs: L5RegimeInputs) -> tuple[MetaRegime, str]:
    """Priority-ordered evaluation; first predicate True wins."""
    if _is_stagflation_risk(inputs.ecs, inputs.msc):
        return MetaRegime.STAGFLATION_RISK, "stagflation+dilemma"
    if _is_recession_risk(inputs.ecs, inputs.cccs):
        return MetaRegime.RECESSION_RISK, "recession+distress"
    if _is_late_cycle_bubble(inputs.fcs, inputs.cccs):
        return MetaRegime.LATE_CYCLE_BUBBLE, "euphoria+bubble+speculation"
    if _is_overheating(inputs.ecs, inputs.cccs, inputs.fcs, inputs.msc):
        return MetaRegime.OVERHEATING, "peak+boom+optimism"
    if _is_soft_landing(inputs.ecs, inputs.cccs, inputs.fcs, inputs.msc):
        return MetaRegime.SOFT_LANDING, "expansion+neutral"
    return MetaRegime.UNCLASSIFIED, "default"


def _is_stagflation_risk(ecs: EcsSnapshot | None, msc: MscSnapshot | None) -> bool:
    if ecs is None or msc is None:
        return False
    return ecs.stagflation_active and msc.dilemma_active


def _is_recession_risk(ecs: EcsSnapshot | None, cccs: CccsSnapshot | None) -> bool:
    if ecs is None or cccs is None:
        return False
    return ecs.regime in ("EARLY_RECESSION", "RECESSION") and cccs.regime in (
        "DISTRESS",
        "REPAIR",
    )


def _is_late_cycle_bubble(fcs: FcsSnapshot | None, cccs: CccsSnapshot | None) -> bool:
    if fcs is None or cccs is None:
        return False
    return fcs.regime == "EUPHORIA" and fcs.bubble_warning_active and cccs.regime == "SPECULATION"


def _is_overheating(
    ecs: EcsSnapshot | None,
    cccs: CccsSnapshot | None,
    fcs: FcsSnapshot | None,
    msc: MscSnapshot | None,
) -> bool:
    if ecs is None or cccs is None or fcs is None or msc is None:
        return False
    return (
        ecs.regime == "PEAK_ZONE"
        and cccs.regime == "BOOM"
        and fcs.regime in ("OPTIMISM", "EUPHORIA")
        and not msc.dilemma_active
    )


def _is_soft_landing(
    ecs: EcsSnapshot | None,
    cccs: CccsSnapshot | None,
    fcs: FcsSnapshot | None,
    msc: MscSnapshot | None,
) -> bool:
    if ecs is None or cccs is None or fcs is None or msc is None:
        return False
    return (
        ecs.regime == "EXPANSION"
        and cccs.regime in ("RECOVERY", "BOOM")
        and fcs.regime in ("OPTIMISM", "CAUTION")
        and msc.regime_3band == "NEUTRAL"
    )


def _compute_confidence(inputs: L5RegimeInputs, *, n_available: int) -> float:
    """Minimum-of-minimums across present cycles + Policy-1 cap."""
    confidences: list[float] = []
    for cycle in (inputs.ecs, inputs.cccs, inputs.fcs, inputs.msc):
        if cycle is not None:
            confidences.append(cycle.confidence)
    base = min(confidences) if confidences else 0.0
    if n_available == 3:
        return min(base, CONFIDENCE_CAP_ONE_MISSING)
    if n_available == 2:  # pragma: no cover — exception fires first
        return min(base, CONFIDENCE_CAP_TWO_MISSING)
    return base
