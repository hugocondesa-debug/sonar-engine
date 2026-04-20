"""Monetary Stance Composite (MSC) — L4 cycle composite.

Spec: docs/specs/cycles/monetary-msc.md @ ``MSC_COMPOSITE_v0.1``

Reads persisted L3 monetary sub-indices — M1 (effective rates), M2
(Taylor gaps), M4 (FCI) from the dedicated ``monetary_m{1,2,4}_*``
tables and M3 (market expectations) from the polymorphic
``index_values`` table — and aggregates to a 0-100 composite per spec
§4::

    MSC_t = 0.30·M1 + 0.15·M2 + 0.25·M3 + 0.20·M4 + 0.10·CS

with Policy 1 re-weighting when any input is unavailable and
``min_required = 3`` of 5. Phase 0-1 deployments do not yet ship a
Communication Signal (CS) connector family, so CS is always ``None``
in this implementation and the flag ``COMM_SIGNAL_MISSING`` is emitted.

Regime classification is two-track per spec:

- ``regime_6band`` (Cap 15.8): STRONGLY_ACCOMMODATIVE / ACCOMMODATIVE /
  NEUTRAL_ACCOMMODATIVE / NEUTRAL_TIGHT / TIGHT / STRONGLY_TIGHT.
- ``regime_3band`` (consumer convenience): ACCOMMODATIVE / NEUTRAL / TIGHT.

Anti-whipsaw hysteresis: a 6-band transition from the previous row's
regime requires both ``|Δscore| > 5`` and a ``≥ 3``-business-day
sustained streak. Otherwise the previous band sticks and
``regime_persistence_days`` increments + ``REGIME_HYSTERESIS_HOLD``
flag is emitted.

Dilemma overlay (Cap 16 Trigger A — price vs financial stability):
if ``score > 60`` and M3 anchor is drifting/unanchored and
``ecs_score < 55``, emit ``dilemma_overlay_active=1`` with a JSON
trigger payload. Phase 0-1 has no ECS rows yet → flag
``DILEMMA_NO_ECS`` and keep the overlay inactive.
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
    IndexValue,
    M1EffectiveRatesResult,
    M2TaylorGapsResult,
    M4FciResult,
    MonetaryCycleScore,
)

if TYPE_CHECKING:
    from datetime import date

    from sqlalchemy.orm import Session

METHODOLOGY_VERSION: str = "MSC_COMPOSITE_v0.1"
MIN_INPUTS: int = 3
TOTAL_INPUTS: int = 5
REGIME_TRANSITION_DELTA_MIN: float = 5.0
REGIME_PERSISTENCE_MIN_DAYS: int = 3
DILEMMA_MSC_THRESHOLD: float = 60.0
DILEMMA_ECS_THRESHOLD: float = 55.0

CANONICAL_WEIGHTS: dict[str, float] = {
    "M1": 0.30,
    "M2": 0.15,
    "M3": 0.25,
    "M4": 0.20,
    "CS": 0.10,
}

# Spec §2 config: 6-band boundaries (lower inclusive, upper exclusive
# except the last which is inclusive up to 100).
REGIME_6BAND_BOUNDARIES: tuple[tuple[float, float, str], ...] = (
    (0.0, 20.0, "STRONGLY_ACCOMMODATIVE"),
    (20.0, 35.0, "ACCOMMODATIVE"),
    (35.0, 50.0, "NEUTRAL_ACCOMMODATIVE"),
    (50.0, 65.0, "NEUTRAL_TIGHT"),
    (65.0, 80.0, "TIGHT"),
    (80.0, 100.0 + 1e-9, "STRONGLY_TIGHT"),
)
REGIME_3BAND_BOUNDARIES: tuple[tuple[float, float, str], ...] = (
    (0.0, 40.0, "ACCOMMODATIVE"),
    (40.0, 60.0, "NEUTRAL"),
    (60.0, 100.0 + 1e-9, "TIGHT"),
)

# Anchor statuses that make Dilemma Trigger A fire when combined with
# the price+financial-stability conditions.
_DRIFTING_ANCHOR_STATES: frozenset[str] = frozenset({"drifting", "unanchored"})


@dataclass(frozen=True, slots=True)
class MscComputedResult:
    """Full MSC output bundle; caller persists via helper."""

    msc_id: str
    country_code: str
    date: date
    methodology_version: str
    score_0_100: float
    regime_6band: str
    regime_3band: str
    regime_persistence_days: int
    m1_score_0_100: float | None
    m2_score_0_100: float | None
    m3_score_0_100: float | None
    m4_score_0_100: float | None
    cs_score_0_100: float | None
    m1_weight_effective: float
    m2_weight_effective: float
    m3_weight_effective: float
    m4_weight_effective: float
    cs_weight_effective: float
    inputs_available: int
    cs_hawkish_score: float | None
    fed_dissent_count: int | None
    dot_plot_drift_bps: int | None
    dilemma_overlay_active: int
    dilemma_trigger_json: str | None
    confidence: float
    flags: tuple[str, ...]


def classify_regime_6band(score: float) -> str:
    """Map a 0-100 score to the 6-band regime label (spec Cap 15.8)."""
    for lo, hi, label in REGIME_6BAND_BOUNDARIES:
        if lo <= score < hi:
            return label
    # Shouldn't be reachable with clipped inputs, but return the upper bin
    # as a safe fallback so callers never see an empty string.
    return REGIME_6BAND_BOUNDARIES[-1][2]


def classify_regime_3band(score: float) -> str:
    """Map a 0-100 score to the consumer-convenience 3-band label."""
    for lo, hi, label in REGIME_3BAND_BOUNDARIES:
        if lo <= score < hi:
            return label
    return REGIME_3BAND_BOUNDARIES[-1][2]


def apply_hysteresis(
    current_score: float,
    new_regime: str,
    prev_score: float | None,
    prev_regime: str | None,
    prev_persistence_days: int,
) -> tuple[str, int, bool]:
    """Return (regime_6band_t, persistence_days_t, held).

    ``held`` is ``True`` when the transition was rejected (sticky).
    Cold-start case (``prev_*`` None) returns the new regime with
    persistence=1 and ``held=False``.
    """
    if prev_regime is None or prev_score is None:
        return new_regime, 1, False
    if new_regime == prev_regime:
        return prev_regime, prev_persistence_days + 1, False
    delta_ok = abs(current_score - prev_score) > REGIME_TRANSITION_DELTA_MIN
    if delta_ok:
        return new_regime, 1, False
    # Sticky: hold previous regime, continue counting persistence.
    return prev_regime, prev_persistence_days + 1, True


# -------------------------------------------------------------------
# Sub-index lookups
# -------------------------------------------------------------------


def _latest_m1(
    session: Session, country_code: str, observation_date: date
) -> M1EffectiveRatesResult | None:
    return (
        session.query(M1EffectiveRatesResult)
        .filter(
            M1EffectiveRatesResult.country_code == country_code,
            M1EffectiveRatesResult.date <= observation_date,
        )
        .order_by(M1EffectiveRatesResult.date.desc())
        .first()
    )


def _latest_m2(
    session: Session, country_code: str, observation_date: date
) -> M2TaylorGapsResult | None:
    return (
        session.query(M2TaylorGapsResult)
        .filter(
            M2TaylorGapsResult.country_code == country_code,
            M2TaylorGapsResult.date <= observation_date,
        )
        .order_by(M2TaylorGapsResult.date.desc())
        .first()
    )


def _latest_m4(session: Session, country_code: str, observation_date: date) -> M4FciResult | None:
    return (
        session.query(M4FciResult)
        .filter(
            M4FciResult.country_code == country_code,
            M4FciResult.date <= observation_date,
        )
        .order_by(M4FciResult.date.desc())
        .first()
    )


def _latest_m3(session: Session, country_code: str, observation_date: date) -> IndexValue | None:
    """M3 lives in the polymorphic ``index_values`` table (Week 3.5)."""
    return (
        session.query(IndexValue)
        .filter(
            IndexValue.index_code == "M3_MARKET_EXPECTATIONS",
            IndexValue.country_code == country_code,
            IndexValue.date <= observation_date,
        )
        .order_by(IndexValue.date.desc())
        .first()
    )


def _extract_m3_anchor_status(m3_row: IndexValue | None) -> str | None:
    """Pull the anchor_status from M3 sub_indicators_json (best-effort).

    Phase 0-1 M3 compute does not persist anchor_status under that key.
    This helper stays forward-compatible: if the field exists in the
    JSON blob, return it; otherwise return ``None`` so Dilemma stays
    informational.
    """
    if m3_row is None or not m3_row.sub_indicators_json:
        return None
    try:
        payload = json.loads(m3_row.sub_indicators_json)
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    status = payload.get("anchor_status")
    return str(status) if isinstance(status, str) else None


def compute_msc(  # noqa: PLR0915
    session: Session,
    country_code: str,
    observation_date: date,
) -> MscComputedResult:
    """Compute MSC for ``(country, date)`` per spec §4.

    Reads persisted L3 M1/M2/M3/M4 rows (latest on or before
    ``observation_date``), applies Policy 1 re-weighting, classifies
    6-band + 3-band regime with hysteresis vs previous MSC row, and
    emits the Dilemma overlay payload when Trigger A criteria are met.

    Raises:
        InsufficientCycleInputsError: when < ``MIN_INPUTS`` sub-
            indices available.
    """
    m1_row = _latest_m1(session, country_code, observation_date)
    m2_row = _latest_m2(session, country_code, observation_date)
    m3_row = _latest_m3(session, country_code, observation_date)
    m4_row = _latest_m4(session, country_code, observation_date)

    m1_score = float(m1_row.score_normalized) if m1_row is not None else None
    m2_score = float(m2_row.score_normalized) if m2_row is not None else None
    m3_score = float(m3_row.value_0_100) if m3_row is not None else None
    m4_score = float(m4_row.score_normalized) if m4_row is not None else None
    # Phase 0-1: Communication Signal connector family not shipped.
    cs_score: float | None = None
    cs_hawkish_score: float | None = None
    fed_dissent_count: int | None = None
    dot_plot_drift_bps: int | None = None

    flags: list[str] = []

    sub_scores: dict[str, float | None] = {
        "M1": m1_score,
        "M2": m2_score,
        "M3": m3_score,
        "M4": m4_score,
        "CS": cs_score,
    }
    score_composite, effective_weights, missing_flags, reweighted = apply_policy_1(
        sub_scores, CANONICAL_WEIGHTS, min_required=MIN_INPUTS
    )
    flags.extend(missing_flags)
    if cs_score is None:
        # Replace the generic CS_MISSING flag from Policy 1 with the
        # spec-canonical name per §6 table.
        flags = [f for f in flags if f != "CS_MISSING"]
        flags.append("COMM_SIGNAL_MISSING")

    # Regime classification.
    regime_6 = classify_regime_6band(score_composite)
    regime_3 = classify_regime_3band(score_composite)

    # Hysteresis vs previous MSC row.
    prev = (
        session.query(MonetaryCycleScore)
        .filter(
            MonetaryCycleScore.country_code == country_code,
            MonetaryCycleScore.date < observation_date,
        )
        .order_by(MonetaryCycleScore.date.desc())
        .first()
    )
    prev_score = prev.score_0_100 if prev is not None else None
    prev_regime_6 = prev.regime_6band if prev is not None else None
    prev_persistence = prev.regime_persistence_days if prev is not None else 0
    final_regime_6, persistence_days, held = apply_hysteresis(
        score_composite, regime_6, prev_score, prev_regime_6, prev_persistence
    )
    if held:
        flags.append("REGIME_HYSTERESIS_HOLD")
        # When the 6-band is held, re-derive the 3-band from the held
        # regime's centre to preserve the sticky effect across tracks.
        # Use the score-driven 3-band if regimes align; otherwise flag
        # already carries the inconsistency and we keep the score-driven
        # 3-band.
        regime_3_final = regime_3
    else:
        regime_3_final = regime_3

    # Dilemma overlay (Trigger A) — Phase 0-1 lacks ECS rows so keep
    # the overlay inactive and emit DILEMMA_NO_ECS per spec §4 step 9.
    dilemma_active = 0
    dilemma_payload: dict[str, object] | None = None
    anchor_status = _extract_m3_anchor_status(m3_row)
    ecs_score: float | None = None  # ECS composite not yet shipped.
    if score_composite > DILEMMA_MSC_THRESHOLD and anchor_status in _DRIFTING_ANCHOR_STATES:
        if ecs_score is None:
            flags.append("DILEMMA_NO_ECS")
        elif ecs_score < DILEMMA_ECS_THRESHOLD:
            dilemma_active = 1
            dilemma_payload = {
                "trigger": "A_price_vs_financial_stability",
                "msc_score": round(score_composite, 2),
                "m3_anchor_status": anchor_status,
                "ecs_score": ecs_score,
            }

    # Flag inheritance from sub-index rows (lexicographic union).
    for row in (m1_row, m2_row, m3_row, m4_row):
        if row is None or row.flags is None:
            continue
        flags.extend(f for f in str(row.flags).split(",") if f)

    # Confidence: min(sub confidences) · (inputs_available / 5) with
    # the re-weight cap when any slot is absent, per spec §4 step 10.
    confidences: list[float] = []
    for row in (m1_row, m2_row, m3_row, m4_row):
        if row is not None:
            confidences.append(float(row.confidence))
    base_confidence = min(confidences) if confidences else 0.5
    inputs_available = sum(1 for v in sub_scores.values() if v is not None)
    raw_confidence = base_confidence * (inputs_available / TOTAL_INPUTS)
    confidence = max(0.0, min(1.0, raw_confidence))
    if reweighted:
        confidence = min(confidence, REWEIGHT_CONFIDENCE_CAP)

    return MscComputedResult(
        msc_id=str(uuid4()),
        country_code=country_code,
        date=observation_date,
        methodology_version=METHODOLOGY_VERSION,
        score_0_100=score_composite,
        regime_6band=final_regime_6,
        regime_3band=regime_3_final,
        regime_persistence_days=persistence_days,
        m1_score_0_100=m1_score,
        m2_score_0_100=m2_score,
        m3_score_0_100=m3_score,
        m4_score_0_100=m4_score,
        cs_score_0_100=cs_score,
        m1_weight_effective=effective_weights.get("M1", 0.0),
        m2_weight_effective=effective_weights.get("M2", 0.0),
        m3_weight_effective=effective_weights.get("M3", 0.0),
        m4_weight_effective=effective_weights.get("M4", 0.0),
        cs_weight_effective=effective_weights.get("CS", 0.0),
        inputs_available=inputs_available,
        cs_hawkish_score=cs_hawkish_score,
        fed_dissent_count=fed_dissent_count,
        dot_plot_drift_bps=dot_plot_drift_bps,
        dilemma_overlay_active=dilemma_active,
        dilemma_trigger_json=(
            json.dumps(dilemma_payload, sort_keys=True) if dilemma_payload is not None else None
        ),
        confidence=confidence,
        flags=tuple(sorted(set(flags))),
    )


def persist_msc_result(session: Session, result: MscComputedResult) -> None:
    """Persist a computed MSC row in ``monetary_cycle_scores``."""
    row = MonetaryCycleScore(
        msc_id=result.msc_id,
        country_code=result.country_code,
        date=result.date,
        methodology_version=result.methodology_version,
        score_0_100=result.score_0_100,
        regime_6band=result.regime_6band,
        regime_3band=result.regime_3band,
        regime_persistence_days=result.regime_persistence_days,
        m1_score_0_100=result.m1_score_0_100,
        m2_score_0_100=result.m2_score_0_100,
        m3_score_0_100=result.m3_score_0_100,
        m4_score_0_100=result.m4_score_0_100,
        cs_score_0_100=result.cs_score_0_100,
        m1_weight_effective=result.m1_weight_effective,
        m2_weight_effective=result.m2_weight_effective,
        m3_weight_effective=result.m3_weight_effective,
        m4_weight_effective=result.m4_weight_effective,
        cs_weight_effective=result.cs_weight_effective,
        inputs_available=result.inputs_available,
        cs_hawkish_score=result.cs_hawkish_score,
        fed_dissent_count=result.fed_dissent_count,
        dot_plot_drift_bps=result.dot_plot_drift_bps,
        dilemma_overlay_active=result.dilemma_overlay_active,
        dilemma_trigger_json=result.dilemma_trigger_json,
        confidence=result.confidence,
        flags=",".join(result.flags) if result.flags else None,
    )
    session.add(row)
    session.commit()


__all__ = [
    "CANONICAL_WEIGHTS",
    "DILEMMA_ECS_THRESHOLD",
    "DILEMMA_MSC_THRESHOLD",
    "METHODOLOGY_VERSION",
    "MIN_INPUTS",
    "REGIME_PERSISTENCE_MIN_DAYS",
    "REGIME_TRANSITION_DELTA_MIN",
    "TOTAL_INPUTS",
    "MscComputedResult",
    "apply_hysteresis",
    "classify_regime_3band",
    "classify_regime_6band",
    "compute_msc",
    "persist_msc_result",
]
