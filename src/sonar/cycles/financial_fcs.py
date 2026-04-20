"""Financial Cycle Score (FCS) — L4 cycle composite.

Spec: docs/specs/cycles/financial-fcs.md @ ``FCS_COMPOSITE_v0.1``

Aggregates F1-F4 persisted rows into ``[0, 100]`` composite score per
spec §4::

    FCS = 0.30 * F1 + 0.25 * F2 + 0.25 * F3 + 0.20 * F4

Regime classification (spec §4)::

    STRESS: FCS < 30
    CAUTION: 30 <= FCS <= 55
    OPTIMISM: 55 < FCS <= 75
    EUPHORIA: FCS > 75

Anti-whipsaw hysteresis identical to CCCS: transition requires
``|Delta FCS| > 5`` (spec), else sticky. regime_persistence_days
tracked.

Tier-conditional Policy 4 (spec §2):

- Tier 1 strict (US/DE/UK/JP per spec list): F4 required or raise.
- Tier 2-4: F4 optional; flag F4_COVERAGE_SPARSE when missing;
  confidence capped at 0.80 (T2/T3) / 0.75 (T4).

Non-T1 countries from ADR-0005 shared scope (PT/IT/ES/FR/NL) treated
as T2-equivalent per user key decision #3 — F4 degradation allowed.

Bubble Warning overlay (spec §4): FCS > 70 AND credit_gap > 10pp AND
property_gap_pct > 20pct; emits bubble_warning_active + components
JSON. When M4 not persisted yet (pending MSC sprint), f3_m4_divergence
stays NULL + flag M4_UNAVAILABLE; when property_gap_pct not persisted
by upstream F1, overlay skips condition-3 + BUBBLE_WARNING_INPUTS_
UNAVAILABLE flag.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

from sonar.cycles.base import (
    REWEIGHT_CONFIDENCE_CAP,
    InsufficientCycleInputsError,
    apply_policy_1,
)
from sonar.db.models import (
    CreditGdpGap,
    FinancialCycleScore,
    FinancialMomentum,
    FinancialPositioning,
    FinancialRiskAppetite,
    FinancialValuations,
)

if TYPE_CHECKING:
    from datetime import date

    from sqlalchemy.orm import Session

METHODOLOGY_VERSION: str = "FCS_COMPOSITE_v0.1"
MIN_INDICES_REQUIRED: int = 3
REGIME_TRANSITION_DELTA_MIN: float = 5.0
BUBBLE_WARNING_FCS_THRESHOLD: float = 70.0
BUBBLE_WARNING_CREDIT_GAP_THRESHOLD_PP: float = 10.0
BUBBLE_WARNING_PROPERTY_GAP_THRESHOLD_PCT: float = 20.0
F3_M4_DIVERGENCE_THRESHOLD: float = 15.0

CANONICAL_WEIGHTS: dict[str, float] = {"F1": 0.30, "F2": 0.25, "F3": 0.25, "F4": 0.20}

TIER_1_STRICT_COUNTRIES: frozenset[str] = frozenset({"US", "DE", "UK", "JP"})
TIER_2_COUNTRIES: frozenset[str] = frozenset({"FR", "IT", "ES", "CA", "AU"})
TIER_3_COUNTRIES: frozenset[str] = frozenset({"PT", "IE", "NL", "SE", "CH"})

TIER_CONFIDENCE_CAPS: dict[int, float] = {1: 1.0, 2: 0.80, 3: 0.80, 4: 0.75}


@dataclass(frozen=True, slots=True)
class FcsComputedResult:
    """Full FCS output bundle; caller persists via helper."""

    fcs_id: str
    country_code: str
    date: date
    methodology_version: str
    score_0_100: float
    regime: str
    regime_persistence_days: int
    f1_score_0_100: float | None
    f2_score_0_100: float | None
    f3_score_0_100: float | None
    f4_score_0_100: float | None
    f1_weight_effective: float
    f2_weight_effective: float
    f3_weight_effective: float
    f4_weight_effective: float | None
    indices_available: int
    country_tier: int
    f3_m4_divergence: float | None
    bubble_warning_active: int
    bubble_warning_components_json: str | None
    confidence: float
    flags: tuple[str, ...]


def classify_regime(score: float) -> str:
    """Spec §4 regime boundaries."""
    if score < 30:
        return "STRESS"
    if score <= 55:
        return "CAUTION"
    if score <= 75:
        return "OPTIMISM"
    return "EUPHORIA"


def resolve_tier(country_code: str) -> int:
    """Map country to tier per spec §2 + user key decision #3."""
    if country_code in TIER_1_STRICT_COUNTRIES:
        return 1
    if country_code in TIER_2_COUNTRIES:
        return 2
    if country_code in TIER_3_COUNTRIES:
        return 3
    return 4


def apply_hysteresis(
    current_score: float,
    new_regime: str,
    prev_score: float | None,
    prev_regime: str | None,
    prev_persistence_days: int,
) -> tuple[str, int, bool]:
    """FCS hysteresis mirrors CCCS (spec §4 anti-whipsaw)."""
    if prev_regime is None or prev_score is None:
        return new_regime, 1, False
    if new_regime == prev_regime:
        return prev_regime, prev_persistence_days + 1, False
    delta_ok = abs(current_score - prev_score) > REGIME_TRANSITION_DELTA_MIN
    if delta_ok:
        return new_regime, 1, False
    return prev_regime, prev_persistence_days + 1, True


def _latest_f1(
    session: Session, country_code: str, observation_date: date
) -> FinancialValuations | None:
    return (
        session.query(FinancialValuations)
        .filter(
            FinancialValuations.country_code == country_code,
            FinancialValuations.date <= observation_date,
        )
        .order_by(FinancialValuations.date.desc())
        .first()
    )


def _latest_f2(
    session: Session, country_code: str, observation_date: date
) -> FinancialMomentum | None:
    return (
        session.query(FinancialMomentum)
        .filter(
            FinancialMomentum.country_code == country_code,
            FinancialMomentum.date <= observation_date,
        )
        .order_by(FinancialMomentum.date.desc())
        .first()
    )


def _latest_f3(
    session: Session, country_code: str, observation_date: date
) -> FinancialRiskAppetite | None:
    return (
        session.query(FinancialRiskAppetite)
        .filter(
            FinancialRiskAppetite.country_code == country_code,
            FinancialRiskAppetite.date <= observation_date,
        )
        .order_by(FinancialRiskAppetite.date.desc())
        .first()
    )


def _latest_f4(
    session: Session, country_code: str, observation_date: date
) -> FinancialPositioning | None:
    return (
        session.query(FinancialPositioning)
        .filter(
            FinancialPositioning.country_code == country_code,
            FinancialPositioning.date <= observation_date,
        )
        .order_by(FinancialPositioning.date.desc())
        .first()
    )


def _latest_l2_gap_pp(session: Session, country_code: str, observation_date: date) -> float | None:
    """Read L2 gap_hp_pp for bubble-warning condition 2."""
    row = (
        session.query(CreditGdpGap)
        .filter(
            CreditGdpGap.country_code == country_code,
            CreditGdpGap.date <= observation_date,
        )
        .order_by(CreditGdpGap.date.desc())
        .first()
    )
    if row is None:
        return None
    return float(row.gap_hp_pp)


def compute_fcs(
    session: Session,
    country_code: str,
    observation_date: date,
) -> FcsComputedResult:
    """Compute FCS for ``(country, date)`` per spec §4."""
    tier = resolve_tier(country_code)
    f1_obj = _latest_f1(session, country_code, observation_date)
    f2_obj = _latest_f2(session, country_code, observation_date)
    f3_obj = _latest_f3(session, country_code, observation_date)
    f4_obj = _latest_f4(session, country_code, observation_date)

    flags: list[str] = []
    # Policy 4: Tier 1 strict — F4 required.
    if tier == 1 and f4_obj is None:
        msg = (
            f"FCS requires F4 for Tier-1 country {country_code}; "
            f"f4_positioning row missing for date {observation_date}"
        )
        raise InsufficientCycleInputsError(msg)

    if f4_obj is None and tier != 1:
        flags.append("F4_COVERAGE_SPARSE")

    sub_scores: dict[str, float | None] = {
        "F1": float(f1_obj.score_normalized) if f1_obj is not None else None,
        "F2": float(f2_obj.score_normalized) if f2_obj is not None else None,
        "F3": float(f3_obj.score_normalized) if f3_obj is not None else None,
        "F4": float(f4_obj.score_normalized) if f4_obj is not None else None,
    }

    score_composite, effective_weights, missing_flags, reweighted = apply_policy_1(
        sub_scores, CANONICAL_WEIGHTS, min_required=MIN_INDICES_REQUIRED
    )
    flags.extend(missing_flags)

    # Regime + hysteresis.
    prev = (
        session.query(FinancialCycleScore)
        .filter(
            FinancialCycleScore.country_code == country_code,
            FinancialCycleScore.date < observation_date,
        )
        .order_by(FinancialCycleScore.date.desc())
        .first()
    )
    new_regime = classify_regime(score_composite)
    prev_score = prev.score_0_100 if prev is not None else None
    prev_regime = prev.regime if prev is not None else None
    prev_persistence = prev.regime_persistence_days if prev is not None else 0
    regime, persistence_days, held = apply_hysteresis(
        score_composite, new_regime, prev_score, prev_regime, prev_persistence
    )
    if held:
        flags.append("REGIME_HYSTERESIS_HOLD")

    # M4 divergence — NULL + flag until MSC sprint ships M4 indices.
    flags.append("M4_UNAVAILABLE")
    f3_m4_divergence: float | None = None

    # Bubble Warning overlay.
    bubble_active = 0
    bubble_payload: dict[str, float | None] | None = None
    credit_gap_pp = _latest_l2_gap_pp(session, country_code, observation_date)
    property_gap_pct: float | None = None  # pending BIS property integration
    property_gap_available = False

    if credit_gap_pp is None or not property_gap_available:
        flags.append("BUBBLE_WARNING_INPUTS_UNAVAILABLE")
    elif (
        score_composite > BUBBLE_WARNING_FCS_THRESHOLD
        and credit_gap_pp > BUBBLE_WARNING_CREDIT_GAP_THRESHOLD_PP
        and property_gap_pct is not None
        and property_gap_pct > BUBBLE_WARNING_PROPERTY_GAP_THRESHOLD_PCT
    ):
        bubble_active = 1
        bubble_payload = {
            "fcs": score_composite,
            "credit_gap_pp": credit_gap_pp,
            "property_gap_pct": property_gap_pct,
        }
        flags.append("BUBBLE_WARNING_ACTIVE")

    # Confidence: base min of sub-confidences; apply caps.
    confidences: list[float] = []
    for row in (f1_obj, f2_obj, f3_obj, f4_obj):
        if row is not None:
            confidences.append(float(row.confidence))
    base_confidence = min(confidences) if confidences else 0.5
    tier_cap = TIER_CONFIDENCE_CAPS[tier]
    confidence = min(base_confidence, tier_cap)
    if reweighted:
        confidence = min(confidence, REWEIGHT_CONFIDENCE_CAP)

    indices_available = sum(1 for v in sub_scores.values() if v is not None)

    return FcsComputedResult(
        fcs_id=str(uuid4()),
        country_code=country_code,
        date=observation_date,
        methodology_version=METHODOLOGY_VERSION,
        score_0_100=score_composite,
        regime=regime,
        regime_persistence_days=persistence_days,
        f1_score_0_100=sub_scores["F1"],
        f2_score_0_100=sub_scores["F2"],
        f3_score_0_100=sub_scores["F3"],
        f4_score_0_100=sub_scores["F4"],
        f1_weight_effective=effective_weights.get("F1", 0.0),
        f2_weight_effective=effective_weights.get("F2", 0.0),
        f3_weight_effective=effective_weights.get("F3", 0.0),
        f4_weight_effective=effective_weights.get("F4") if "F4" in effective_weights else None,
        indices_available=indices_available,
        country_tier=tier,
        f3_m4_divergence=f3_m4_divergence,
        bubble_warning_active=bubble_active,
        bubble_warning_components_json=json.dumps(bubble_payload, sort_keys=True)
        if bubble_payload
        else None,
        confidence=confidence,
        flags=tuple(sorted(set(flags))),
    )


def persist_fcs_result(session: Session, result: FcsComputedResult) -> None:
    """Persist a computed FCS row."""
    row = FinancialCycleScore(
        fcs_id=result.fcs_id,
        country_code=result.country_code,
        date=result.date,
        methodology_version=result.methodology_version,
        score_0_100=result.score_0_100,
        regime=result.regime,
        regime_persistence_days=result.regime_persistence_days,
        f1_score_0_100=result.f1_score_0_100,
        f2_score_0_100=result.f2_score_0_100,
        f3_score_0_100=result.f3_score_0_100,
        f4_score_0_100=result.f4_score_0_100,
        f1_weight_effective=result.f1_weight_effective,
        f2_weight_effective=result.f2_weight_effective,
        f3_weight_effective=result.f3_weight_effective,
        f4_weight_effective=result.f4_weight_effective,
        indices_available=result.indices_available,
        country_tier=result.country_tier,
        f3_m4_divergence=result.f3_m4_divergence,
        bubble_warning_active=result.bubble_warning_active,
        bubble_warning_components_json=result.bubble_warning_components_json,
        confidence=result.confidence,
        flags=",".join(result.flags) if result.flags else None,
    )
    session.add(row)
    session.commit()


__all__ = [
    "BUBBLE_WARNING_CREDIT_GAP_THRESHOLD_PP",
    "BUBBLE_WARNING_FCS_THRESHOLD",
    "BUBBLE_WARNING_PROPERTY_GAP_THRESHOLD_PCT",
    "CANONICAL_WEIGHTS",
    "METHODOLOGY_VERSION",
    "MIN_INDICES_REQUIRED",
    "REGIME_TRANSITION_DELTA_MIN",
    "TIER_1_STRICT_COUNTRIES",
    "FcsComputedResult",
    "apply_hysteresis",
    "classify_regime",
    "compute_fcs",
    "persist_fcs_result",
    "resolve_tier",
]
