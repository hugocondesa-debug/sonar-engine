"""L5 regime types — enum + inputs + result dataclasses.

The dataclasses mirror
``docs/specs/regimes/cross-cycle-meta-regimes.md`` §2 + §6: inputs
carry lightweight snapshots of the four L4 cycle rows (only the
fields the classifier reads) and results carry the persisted-row
shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from datetime import date as date_t

__all__ = [
    "CccsSnapshot",
    "EcsSnapshot",
    "FcsSnapshot",
    "L5RegimeInputs",
    "L5RegimeResult",
    "MetaRegime",
    "MscSnapshot",
]


class MetaRegime(StrEnum):
    """The six canonical Phase 1 meta-regimes."""

    OVERHEATING = "overheating"
    STAGFLATION_RISK = "stagflation_risk"
    LATE_CYCLE_BUBBLE = "late_cycle_bubble"
    RECESSION_RISK = "recession_risk"
    SOFT_LANDING = "soft_landing"
    UNCLASSIFIED = "unclassified"


EcsRegime = Literal["EXPANSION", "PEAK_ZONE", "EARLY_RECESSION", "RECESSION"]
CccsRegime = Literal["REPAIR", "RECOVERY", "BOOM", "SPECULATION", "DISTRESS"]
FcsRegime = Literal["STRESS", "CAUTION", "OPTIMISM", "EUPHORIA"]
MscRegime3Band = Literal["ACCOMMODATIVE", "NEUTRAL", "TIGHT"]


@dataclass(frozen=True, slots=True)
class EcsSnapshot:
    """Minimal ECS view the classifier reads (populated from cycle row)."""

    ecs_id: str
    score: float
    regime: EcsRegime
    stagflation_active: bool
    confidence: float


@dataclass(frozen=True, slots=True)
class CccsSnapshot:
    """Minimal CCCS view."""

    cccs_id: str
    score: float
    regime: CccsRegime
    boom_active: bool
    confidence: float


@dataclass(frozen=True, slots=True)
class FcsSnapshot:
    """Minimal FCS view."""

    fcs_id: str
    score: float
    regime: FcsRegime
    bubble_warning_active: bool
    confidence: float


@dataclass(frozen=True, slots=True)
class MscSnapshot:
    """Minimal MSC view — uses the 3-band regime column."""

    msc_id: str
    score: float
    regime_3band: MscRegime3Band
    dilemma_active: bool
    confidence: float


@dataclass(frozen=True, slots=True)
class L5RegimeInputs:
    """Inputs bundle for a single ``(country, date)`` L5 classification.

    Any cycle slot may be ``None`` to represent a missing L4 row; the
    classifier enforces the ≥ 3/4 Policy-1 threshold.
    """

    country_code: str
    date: date_t
    ecs: EcsSnapshot | None = None
    cccs: CccsSnapshot | None = None
    fcs: FcsSnapshot | None = None
    msc: MscSnapshot | None = None

    def available_count(self) -> int:
        """Return the number of non-``None`` cycle slots."""
        return sum(c is not None for c in (self.ecs, self.cccs, self.fcs, self.msc))

    def missing_flags(self) -> tuple[str, ...]:
        """Return ``L5_{CYCLE}_MISSING`` flags for absent cycles."""
        out: list[str] = []
        if self.ecs is None:
            out.append("L5_ECS_MISSING")
        if self.cccs is None:
            out.append("L5_CCCS_MISSING")
        if self.fcs is None:
            out.append("L5_FCS_MISSING")
        if self.msc is None:
            out.append("L5_MSC_MISSING")
        return tuple(out)


@dataclass(frozen=True, slots=True)
class L5RegimeResult:
    """Canonical L5 output — mirrors the ``l5_meta_regimes`` ORM."""

    country_code: str
    date: date_t
    meta_regime: MetaRegime
    ecs_id: str | None
    cccs_id: str | None
    fcs_id: str | None
    msc_id: str | None
    confidence: float
    flags: tuple[str, ...] = field(default_factory=tuple)
    classification_reason: str = ""
    methodology_version: str = "L5_META_REGIME_v0.1"
