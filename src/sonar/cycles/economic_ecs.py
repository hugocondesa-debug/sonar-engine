"""Economic Cycle Score (ECS) — L4 cycle composite.

Spec: docs/specs/cycles/economic-ecs.md @ ``ECS_COMPOSITE_v0.1``

Reads persisted E1 (Activity), E3 (Labor), E4 (Sentiment) from their
dedicated tables and E2 (Leading) from the polymorphic
``index_values`` table (``index_code = "E2_LEADING"``), and aggregates
per spec §4::

    ECS_t = 0.35·E1 + 0.25·E2 + 0.25·E3 + 0.15·E4

with Policy 1 proportional re-weight when any sub-index is unavailable
(``MIN_REQUIRED = 3`` of 4; else ``InsufficientCycleInputsError``).

Regime classification (spec §4, 4-state canonical — Cap 15.7):

- ``EXPANSION``: ``score > 60``
- ``PEAK_ZONE``: ``55 ≤ score ≤ 70`` (overlap resolved by ties-to-
  higher-severity: PEAK_ZONE wins over EXPANSION at 55-60)
- ``EARLY_RECESSION``: ``40 ≤ score < 55``
- ``RECESSION``: ``score < 40``

Anti-whipsaw hysteresis: a transition from the previous row's regime
requires both ``|Δscore| > 5`` and the new raw band observed for
``≥ 3`` consecutive business days. Otherwise the previous regime
sticks and ``regime_persistence_days`` increments (no flag in the
expected held-path; ``REGIME_HYSTERESIS_HOLD`` is emitted only when
a buffer reset happens mid-sequence — Phase 0-1 simplifies to the
sticky path without a buffer counter).

Stagflation overlay (spec §4, Cap 16 Trigger A):

- Active iff ``score < 55`` AND ``cpi_yoy > 0.03`` AND
  (``sahm_triggered == 1`` OR ``unemp_delta > 0.003``).
- ``stagflation_trigger_json`` populated with the three condition
  values when active.
- If ``cpi_yoy`` or ``unemp_delta`` are missing the overlay is
  forced to 0 and the ``STAGFLATION_INPUT_MISSING`` flag is emitted
  with a ``-0.05`` confidence hit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

from sonar.cycles.base import (
    REWEIGHT_CONFIDENCE_CAP,
    apply_policy_1,
)
from sonar.db.models import (
    E1Activity,
    E3Labor,
    E4Sentiment,
    EconomicCycleScore,
    IndexValue,
)

if TYPE_CHECKING:
    from datetime import date

    from sqlalchemy.orm import Session

METHODOLOGY_VERSION: str = "ECS_COMPOSITE_v0.1"
MIN_REQUIRED: int = 3
TOTAL_INDICES: int = 4
SUB_INDEX_CONFIDENCE_GATE: float = 0.50
REGIME_TRANSITION_DELTA_MIN: float = 5.0
REGIME_PERSISTENCE_MIN_DAYS: int = 3
STAGFLATION_SCORE_THRESHOLD: float = 55.0
STAGFLATION_CPI_THRESHOLD: float = 0.03
STAGFLATION_UNEMP_DELTA_THRESHOLD: float = 0.003
STAGFLATION_CONFIDENCE_PENALTY: float = 0.05

CANONICAL_WEIGHTS: dict[str, float] = {
    "E1": 0.35,
    "E2": 0.25,
    "E3": 0.25,
    "E4": 0.15,
}

E2_INDEX_CODE = "E2_LEADING"


@dataclass(frozen=True, slots=True)
class StagflationInputs:
    """Per-(country, date) stagflation-overlay inputs.

    Any field ``None`` forces the overlay to 0 and emits the
    ``STAGFLATION_INPUT_MISSING`` flag per spec §6.
    """

    cpi_yoy: float | None
    sahm_triggered: int | None
    unemp_delta: float | None


@dataclass(frozen=True, slots=True)
class EcsComputedResult:
    """Full ECS output bundle; caller persists via helper."""

    ecs_id: str
    country_code: str
    date: date
    methodology_version: str
    score_0_100: float
    regime: str
    regime_persistence_days: int
    e1_score_0_100: float | None
    e2_score_0_100: float | None
    e3_score_0_100: float | None
    e4_score_0_100: float | None
    e1_weight_effective: float
    e2_weight_effective: float
    e3_weight_effective: float
    e4_weight_effective: float
    indices_available: int
    stagflation_overlay_active: int
    stagflation_trigger_json: str | None
    confidence: float
    flags: tuple[str, ...]


def classify_regime(score: float) -> str:
    """Map a 0-100 score to the canonical regime (spec §4 tie-breaking).

    Spec §4 ties-go-to-higher-severity:

    - PEAK_ZONE wins over EXPANSION in the 55-60 overlap.
    - EARLY_RECESSION wins at the 55 boundary (>=40 and <55 yields
      EARLY_RECESSION; PEAK_ZONE requires >=55 and <=70).
    """
    if score < 40:
        return "RECESSION"
    if score < 55:
        return "EARLY_RECESSION"
    if score <= 70:
        return "PEAK_ZONE"
    return "EXPANSION"


def apply_hysteresis(
    current_score: float,
    new_regime: str,
    prev_score: float | None,
    prev_regime: str | None,
    prev_persistence_days: int,
) -> tuple[str, int, bool]:
    """Return (regime_t, persistence_days_t, held).

    ``held`` is ``True`` when a candidate transition was rejected by
    the |Δscore| > 5 gate. First-observation case (``prev_*`` None)
    returns the new regime with persistence=1 and not held.
    Simplified Phase 0-1 path: no multi-day buffer state; a single
    row's |Δ| ≤ 5 holds the previous regime. Multi-day buffer state
    (REGIME_HYSTERESIS_HOLD with buffer-reset semantics) is a Phase
    2+ pipeline-level feature.
    """
    if prev_regime is None or prev_score is None:
        return new_regime, 1, False
    if new_regime == prev_regime:
        return prev_regime, prev_persistence_days + 1, False
    delta_ok = abs(current_score - prev_score) > REGIME_TRANSITION_DELTA_MIN
    if delta_ok:
        return new_regime, 1, False
    return prev_regime, prev_persistence_days + 1, True


def evaluate_stagflation_overlay(
    score_0_100: float, inputs: StagflationInputs
) -> tuple[int, str | None, bool]:
    """Evaluate spec §4 Trigger A.

    Returns ``(active, trigger_json_or_none, input_missing)``. The
    ``input_missing`` flag indicates at least one of ``cpi_yoy`` or
    ``unemp_delta`` is unavailable and ``sahm_triggered`` alone was
    insufficient; the caller emits ``STAGFLATION_INPUT_MISSING`` and
    applies the confidence penalty.
    """
    # Determine labor-weakness condition.
    sahm = inputs.sahm_triggered == 1
    unemp_ok = inputs.unemp_delta is not None
    unemp_weak = unemp_ok and (inputs.unemp_delta or 0.0) > STAGFLATION_UNEMP_DELTA_THRESHOLD
    labor_weakness = sahm or unemp_weak

    # Input-missing when CPI is None, or when unemp is None AND Sahm is None.
    input_missing = inputs.cpi_yoy is None or (
        inputs.unemp_delta is None and inputs.sahm_triggered is None
    )
    if input_missing:
        return 0, None, True

    if inputs.cpi_yoy is None:  # redundant guard for mypy
        return 0, None, True

    active = (
        score_0_100 < STAGFLATION_SCORE_THRESHOLD
        and inputs.cpi_yoy > STAGFLATION_CPI_THRESHOLD
        and labor_weakness
    )
    if not active:
        return 0, None, False

    trigger = {
        "cpi_yoy": round(inputs.cpi_yoy, 4),
        "sahm_triggered": int(sahm),
        "unemp_delta": (round(inputs.unemp_delta, 4) if inputs.unemp_delta is not None else None),
        "unemployment_trend": "rising" if unemp_weak else "flat_or_declining",
    }
    return 1, json.dumps(trigger, sort_keys=True), False


# ---------------------------------------------------------------------------
# Sub-index lookups
# ---------------------------------------------------------------------------


def _latest_e1(session: Session, country_code: str, observation_date: date) -> E1Activity | None:
    return (
        session.query(E1Activity)
        .filter(
            E1Activity.country_code == country_code,
            E1Activity.date <= observation_date,
        )
        .order_by(E1Activity.date.desc())
        .first()
    )


def _latest_e2(session: Session, country_code: str, observation_date: date) -> IndexValue | None:
    return (
        session.query(IndexValue)
        .filter(
            IndexValue.index_code == E2_INDEX_CODE,
            IndexValue.country_code == country_code,
            IndexValue.date <= observation_date,
        )
        .order_by(IndexValue.date.desc())
        .first()
    )


def _latest_e3(session: Session, country_code: str, observation_date: date) -> E3Labor | None:
    return (
        session.query(E3Labor)
        .filter(
            E3Labor.country_code == country_code,
            E3Labor.date <= observation_date,
        )
        .order_by(E3Labor.date.desc())
        .first()
    )


def _latest_e4(session: Session, country_code: str, observation_date: date) -> E4Sentiment | None:
    return (
        session.query(E4Sentiment)
        .filter(
            E4Sentiment.country_code == country_code,
            E4Sentiment.date <= observation_date,
        )
        .order_by(E4Sentiment.date.desc())
        .first()
    )


def _score_if_confident(obj: object | None) -> float | None:
    """Return ``score_normalized`` / ``value_0_100`` if confidence ≥ gate."""
    if obj is None:
        return None
    confidence = float(getattr(obj, "confidence", 0.0))
    if confidence < SUB_INDEX_CONFIDENCE_GATE:
        return None
    # E1/E3/E4 expose `score_normalized`; IndexValue exposes `value_0_100`.
    if hasattr(obj, "score_normalized"):
        return float(obj.score_normalized)
    if hasattr(obj, "value_0_100"):
        return float(obj.value_0_100)
    return None


def compute_ecs(
    session: Session,
    country_code: str,
    observation_date: date,
    stagflation_inputs: StagflationInputs | None = None,
) -> EcsComputedResult:
    """Compute ECS for ``(country, date)`` per spec §4.

    Reads persisted E1/E2/E3/E4 rows (latest on or before
    ``observation_date``), applies Policy 1 re-weighting, classifies
    regime with hysteresis vs previous ECS row, and evaluates the
    stagflation overlay. Persist via :func:`persist_ecs_result`.

    Callers supply ``stagflation_inputs`` when they have CPI /
    Sahm / unemp-delta readings for ``(country, date)``. When the
    parameter is ``None`` the overlay is forced inactive and the
    ``STAGFLATION_INPUT_MISSING`` flag fires with the spec confidence
    penalty.

    Raises:
        InsufficientCycleInputsError: when < :data:`MIN_REQUIRED`
            sub-indices available.
    """
    e1_row = _latest_e1(session, country_code, observation_date)
    e2_row = _latest_e2(session, country_code, observation_date)
    e3_row = _latest_e3(session, country_code, observation_date)
    e4_row = _latest_e4(session, country_code, observation_date)

    e1_score = _score_if_confident(e1_row)
    e2_score = _score_if_confident(e2_row)
    e3_score = _score_if_confident(e3_row)
    e4_score = _score_if_confident(e4_row)

    flags: list[str] = []

    sub_scores: dict[str, float | None] = {
        "E1": e1_score,
        "E2": e2_score,
        "E3": e3_score,
        "E4": e4_score,
    }
    score_composite, effective_weights, missing_flags, reweighted = apply_policy_1(
        sub_scores, CANONICAL_WEIGHTS, min_required=MIN_REQUIRED
    )
    flags.extend(missing_flags)

    # Regime classification.
    raw_regime = classify_regime(score_composite)

    # Hysteresis against previous ECS row.
    prev = (
        session.query(EconomicCycleScore)
        .filter(
            EconomicCycleScore.country_code == country_code,
            EconomicCycleScore.date < observation_date,
        )
        .order_by(EconomicCycleScore.date.desc())
        .first()
    )
    prev_score = prev.score_0_100 if prev is not None else None
    prev_regime = prev.regime if prev is not None else None
    prev_persistence = prev.regime_persistence_days if prev is not None else 0
    final_regime, persistence_days, held = apply_hysteresis(
        score_composite, raw_regime, prev_score, prev_regime, prev_persistence
    )
    if prev is None:
        flags.append("REGIME_BOOTSTRAP")
    if held:
        flags.append("REGIME_HYSTERESIS_HOLD")

    # Stagflation overlay.
    sf_inputs = stagflation_inputs or StagflationInputs(
        cpi_yoy=None, sahm_triggered=None, unemp_delta=None
    )
    sf_active, sf_trigger_json, sf_missing = evaluate_stagflation_overlay(
        score_composite, sf_inputs
    )
    if sf_missing:
        flags.append("STAGFLATION_INPUT_MISSING")
    if sf_active == 1:
        flags.append("STAGFLATION_OVERLAY_ACTIVE")

    # Sub-index flag inheritance (lexicographic union).
    for row in (e1_row, e2_row, e3_row, e4_row):
        if row is None or row.flags is None:
            continue
        flags.extend(f for f in str(row.flags).split(",") if f)

    # Confidence: min of available sub-index confidences · (available/4),
    # then apply the re-weight cap + stagflation-input penalty.
    confidences: list[float] = []
    for row in (e1_row, e2_row, e3_row, e4_row):
        if row is not None and _score_if_confident(row) is not None:
            confidences.append(float(row.confidence))
    base_confidence = min(confidences) if confidences else 0.5
    indices_available = sum(1 for v in sub_scores.values() if v is not None)
    raw_confidence = base_confidence * (indices_available / TOTAL_INDICES)
    confidence = max(0.0, min(1.0, raw_confidence))
    if reweighted:
        confidence = min(confidence, REWEIGHT_CONFIDENCE_CAP)
    if sf_missing:
        confidence = max(0.0, confidence - STAGFLATION_CONFIDENCE_PENALTY)

    return EcsComputedResult(
        ecs_id=str(uuid4()),
        country_code=country_code,
        date=observation_date,
        methodology_version=METHODOLOGY_VERSION,
        score_0_100=score_composite,
        regime=final_regime,
        regime_persistence_days=persistence_days,
        e1_score_0_100=e1_score,
        e2_score_0_100=e2_score,
        e3_score_0_100=e3_score,
        e4_score_0_100=e4_score,
        e1_weight_effective=effective_weights.get("E1", 0.0),
        e2_weight_effective=effective_weights.get("E2", 0.0),
        e3_weight_effective=effective_weights.get("E3", 0.0),
        e4_weight_effective=effective_weights.get("E4", 0.0),
        indices_available=indices_available,
        stagflation_overlay_active=sf_active,
        stagflation_trigger_json=sf_trigger_json,
        confidence=confidence,
        flags=tuple(sorted(set(flags))),
    )


def persist_ecs_result(session: Session, result: EcsComputedResult) -> None:
    """Persist a computed ECS row in ``economic_cycle_scores``."""
    row = EconomicCycleScore(
        ecs_id=result.ecs_id,
        country_code=result.country_code,
        date=result.date,
        methodology_version=result.methodology_version,
        score_0_100=result.score_0_100,
        regime=result.regime,
        regime_persistence_days=result.regime_persistence_days,
        e1_score_0_100=result.e1_score_0_100,
        e2_score_0_100=result.e2_score_0_100,
        e3_score_0_100=result.e3_score_0_100,
        e4_score_0_100=result.e4_score_0_100,
        e1_weight_effective=result.e1_weight_effective,
        e2_weight_effective=result.e2_weight_effective,
        e3_weight_effective=result.e3_weight_effective,
        e4_weight_effective=result.e4_weight_effective,
        indices_available=result.indices_available,
        stagflation_overlay_active=result.stagflation_overlay_active,
        stagflation_trigger_json=result.stagflation_trigger_json,
        confidence=result.confidence,
        flags=",".join(result.flags) if result.flags else None,
    )
    session.add(row)
    session.commit()


__all__ = [
    "CANONICAL_WEIGHTS",
    "E2_INDEX_CODE",
    "METHODOLOGY_VERSION",
    "MIN_REQUIRED",
    "REGIME_PERSISTENCE_MIN_DAYS",
    "REGIME_TRANSITION_DELTA_MIN",
    "STAGFLATION_CONFIDENCE_PENALTY",
    "STAGFLATION_CPI_THRESHOLD",
    "STAGFLATION_SCORE_THRESHOLD",
    "STAGFLATION_UNEMP_DELTA_THRESHOLD",
    "SUB_INDEX_CONFIDENCE_GATE",
    "TOTAL_INDICES",
    "EcsComputedResult",
    "StagflationInputs",
    "apply_hysteresis",
    "classify_regime",
    "compute_ecs",
    "evaluate_stagflation_overlay",
    "persist_ecs_result",
]
