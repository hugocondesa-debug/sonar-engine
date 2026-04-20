"""Credit Cycle Composite Score (CCCS) — L4 cycle composite.

Spec: docs/specs/cycles/credit-cccs.md @ ``CCCS_COMPOSITE_v0.1``

Reads persisted L1/L2/L3/L4 credit rows and F3 + F4 financial rows for
``(country, date)``, applies the 3-sub-component composite per spec §4::

    CS = 0.30 * pts(L1.z) + 0.50 * pts(L2.z) + 0.20 * pts(L4.z)
    LC = 0.60 * pts(L3.z) + 0.40 * pts(L4.z)
    MS = 0.70 * F3.score_normalized + 0.30 * pts(z_20Y(F4.margin_debt_gdp_pct))
    CCCS = 0.44 * CS + 0.33 * LC + 0.22 * MS

where ``pts(z) = clip(50 + 16.67*z, 0, 100)``. QS omitted v0.1 (flag
``QS_PLACEHOLDER`` always).

Regime classification per spec §4::

    REPAIR: score < 30
    RECOVERY: 30 <= score < 50
    BOOM: 50 <= score < 70
    SPECULATION: 70 <= score <= 85
    DISTRESS: score > 85

Anti-whipsaw hysteresis: a transition from the previous row's regime
requires both |Delta score| > 5 and the new criterion satisfied.
Otherwise the previous regime sticks and regime_persistence_days
increments.

Boom overlay (spec §4): ``score > 70`` and ``L2.gap_hp_pp > 10`` and
``L4.score_normalized > 1.5``.
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
    CreditCycleScore,
    CreditGdpGap,
    CreditGdpStock,
    CreditImpulse,
    Dsr,
    FinancialPositioning,
    FinancialRiskAppetite,
)
from sonar.indices._helpers.z_score_rolling import rolling_zscore

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date

    from sqlalchemy.orm import Session

METHODOLOGY_VERSION: str = "CCCS_COMPOSITE_v0.1"
MIN_CORE_COMPONENTS: int = 3
REGIME_TRANSITION_DELTA_MIN: float = 5.0
REGIME_PERSISTENCE_MIN_DAYS: int = 3
BOOM_OVERLAY_L2_GAP_THRESHOLD_PP: float = 10.0
BOOM_OVERLAY_L4_DSR_Z_THRESHOLD: float = 1.5
BOOM_OVERLAY_SCORE_THRESHOLD: float = 70.0
QS_ABSENT_CONFIDENCE_CAP: float = 0.90

CANONICAL_WEIGHTS: dict[str, float] = {"CS": 0.44, "LC": 0.33, "MS": 0.22}


@dataclass(frozen=True, slots=True)
class CccsComputedResult:
    """Full CCCS output bundle; caller persists via helper."""

    cccs_id: str
    country_code: str
    date: date
    methodology_version: str
    score_0_100: float
    regime: str
    regime_persistence_days: int
    cs_score_0_100: float | None
    lc_score_0_100: float | None
    ms_score_0_100: float | None
    qs_score_0_100: None
    cs_weight_effective: float
    lc_weight_effective: float
    ms_weight_effective: float
    components_available: int
    l1_contribution_pct: float | None
    l2_contribution_pct: float | None
    l3_contribution_pct: float | None
    l4_contribution_pct: float | None
    f3_contribution_pct: float | None
    f4_margin_debt_contribution_pct: float | None
    boom_overlay_active: int
    boom_trigger_json: str | None
    confidence: float
    flags: tuple[str, ...]


def pts(z: float) -> float:
    """Map a z-score to the 0-100 canonical scale."""
    return max(0.0, min(100.0, 50.0 + 16.67 * z))


def classify_regime(score: float) -> str:
    """Spec §4 regime boundaries."""
    if score < 30:
        return "REPAIR"
    if score < 50:
        return "RECOVERY"
    if score < 70:
        return "BOOM"
    if score <= 85:
        return "SPECULATION"
    return "DISTRESS"


def apply_hysteresis(
    current_score: float,
    new_regime: str,
    prev_score: float | None,
    prev_regime: str | None,
    prev_persistence_days: int,
) -> tuple[str, int, bool]:
    """Return (regime_t, persistence_days_t, held).

    ``held`` is ``True`` when the transition was rejected (sticky).
    First-observation case (``prev_*`` None) returns the new regime
    with persistence=1 and not held.
    """
    if prev_regime is None or prev_score is None:
        return new_regime, 1, False
    if new_regime == prev_regime:
        return prev_regime, prev_persistence_days + 1, False
    delta_ok = abs(current_score - prev_score) > REGIME_TRANSITION_DELTA_MIN
    if delta_ok:
        return new_regime, 1, False
    # Sticky — hold previous regime, continue counting persistence.
    return prev_regime, prev_persistence_days + 1, True


def _latest_l1(
    session: Session, country_code: str, observation_date: date
) -> CreditGdpStock | None:
    return (
        session.query(CreditGdpStock)
        .filter(
            CreditGdpStock.country_code == country_code,
            CreditGdpStock.date <= observation_date,
        )
        .order_by(CreditGdpStock.date.desc())
        .first()
    )


def _latest_l2(session: Session, country_code: str, observation_date: date) -> CreditGdpGap | None:
    return (
        session.query(CreditGdpGap)
        .filter(
            CreditGdpGap.country_code == country_code,
            CreditGdpGap.date <= observation_date,
        )
        .order_by(CreditGdpGap.date.desc())
        .first()
    )


def _latest_l3(session: Session, country_code: str, observation_date: date) -> CreditImpulse | None:
    return (
        session.query(CreditImpulse)
        .filter(
            CreditImpulse.country_code == country_code,
            CreditImpulse.date <= observation_date,
        )
        .order_by(CreditImpulse.date.desc())
        .first()
    )


def _latest_l4(session: Session, country_code: str, observation_date: date) -> Dsr | None:
    return (
        session.query(Dsr)
        .filter(Dsr.country_code == country_code, Dsr.date <= observation_date)
        .order_by(Dsr.date.desc())
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


def _f4_margin_debt_history(
    session: Session, country_code: str, observation_date: date
) -> tuple[float | None, Sequence[float]]:
    """Fetch (current, 20Y history) of margin_debt_gdp_pct from f4_positioning.

    Returns (None, []) if no rows exist or current value is NULL.
    History is the series of margin_debt_gdp_pct over the trailing 20Y.
    """
    # 20Y daily grid cap would be 20*252 = 5040 observations; in practice
    # F-cycle persists per observation_date so this works from whatever's
    # there.
    cutoff_year = observation_date.year - 20
    rows = (
        session.query(FinancialPositioning)
        .filter(
            FinancialPositioning.country_code == country_code,
            FinancialPositioning.date <= observation_date,
            FinancialPositioning.date >= observation_date.replace(year=cutoff_year),
        )
        .order_by(FinancialPositioning.date.asc())
        .all()
    )
    if not rows:
        return None, []
    history = [r.margin_debt_gdp_pct for r in rows if r.margin_debt_gdp_pct is not None]
    if not history:
        return None, []
    current = rows[-1].margin_debt_gdp_pct
    return current, history


def _extract_l2_gap_pp(l2_row: CreditGdpGap) -> float:
    """L2's ``score_raw`` is the canonical gap in pp per L2-credit-to-gdp-gap.md."""
    return float(l2_row.score_raw)


def _extract_l4_dsr_z(l4_row: Dsr) -> float:
    """L4 ``score_normalized`` is the z-score clamped per L4-dsr.md §8."""
    return float(l4_row.score_normalized)


def compute_cccs(  # noqa: PLR0912, PLR0915
    session: Session,
    country_code: str,
    observation_date: date,
) -> CccsComputedResult:
    """Compute CCCS for ``(country, date)`` per spec §4 — complexity per spec steps.

    Reads persisted L1/L2/L3/L4 + F3 + F4 rows, applies the 3-sub-
    component formula, classifies regime with hysteresis, computes
    boom overlay, persists via caller.

    Raises:
        InsufficientCycleInputsError: when < 3 core sub-components
            computable.
    """
    l1_obj = _latest_l1(session, country_code, observation_date)
    l2_obj = _latest_l2(session, country_code, observation_date)
    l3_obj = _latest_l3(session, country_code, observation_date)
    l4_obj = _latest_l4(session, country_code, observation_date)
    f3_obj = _latest_f3(session, country_code, observation_date)

    flags: list[str] = ["QS_PLACEHOLDER"]

    # CS = 0.30*L1 + 0.50*L2 + 0.20*L4 ; needs all 3 available.
    cs_score: float | None
    if l1_obj is not None and l2_obj is not None and l4_obj is not None:
        cs_score = (
            0.30 * pts(float(l1_obj.score_normalized))
            + 0.50 * pts(float(l2_obj.score_normalized))
            + 0.20 * pts(float(l4_obj.score_normalized))
        )
    else:
        cs_score = None

    # LC = 0.60*L3 + 0.40*L4 ; needs both.
    lc_score: float | None
    if l3_obj is not None and l4_obj is not None:
        lc_score = 0.60 * pts(float(l3_obj.score_normalized)) + 0.40 * pts(
            float(l4_obj.score_normalized)
        )
    else:
        lc_score = None

    # MS = 0.70*F3 + 0.30*pts(z_20Y(F4.margin_debt_gdp_pct))
    f4_margin_current, f4_margin_history = _f4_margin_debt_history(
        session, country_code, observation_date
    )
    f4_margin_z = 0.0
    f4_margin_contrib_available = False
    if f4_margin_current is not None and len(f4_margin_history) >= 2:
        z, _mu, _sigma, _n = rolling_zscore(f4_margin_history, current=f4_margin_current)
        f4_margin_z = z
        f4_margin_contrib_available = True
    else:
        flags.append("F4_MARGIN_MISSING")

    ms_score: float | None
    if f3_obj is not None and f4_margin_contrib_available:
        ms_score = 0.70 * float(f3_obj.score_normalized) + 0.30 * pts(f4_margin_z)
    elif f3_obj is not None:
        ms_score = float(f3_obj.score_normalized)  # 100% F3 fallback per spec §4
    else:
        ms_score = None

    sub_scores: dict[str, float | None] = {
        "CS": cs_score,
        "LC": lc_score,
        "MS": ms_score,
    }
    score_composite, effective_weights, missing_flags, reweighted = apply_policy_1(
        sub_scores, CANONICAL_WEIGHTS, min_required=MIN_CORE_COMPONENTS
    )
    flags.extend(missing_flags)

    # Regime classification + hysteresis.
    prev = (
        session.query(CreditCycleScore)
        .filter(
            CreditCycleScore.country_code == country_code,
            CreditCycleScore.date < observation_date,
        )
        .order_by(CreditCycleScore.date.desc())
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

    # Boom overlay.
    boom_active = 0
    boom_trigger_payload: dict[str, float | bool] | None = None
    if l2_obj is not None and l4_obj is not None:
        l2_gap_pp = _extract_l2_gap_pp(l2_obj)
        l4_dsr_z = _extract_l4_dsr_z(l4_obj)
        if (
            score_composite > BOOM_OVERLAY_SCORE_THRESHOLD
            and l2_gap_pp > BOOM_OVERLAY_L2_GAP_THRESHOLD_PP
            and l4_dsr_z > BOOM_OVERLAY_L4_DSR_Z_THRESHOLD
        ):
            boom_active = 1
            boom_trigger_payload = {
                "score": score_composite,
                "l2_gap_pp": l2_gap_pp,
                "l4_dsr_z": l4_dsr_z,
                "threshold_score": BOOM_OVERLAY_SCORE_THRESHOLD,
                "threshold_gap_pp": BOOM_OVERLAY_L2_GAP_THRESHOLD_PP,
                "threshold_dsr_z": BOOM_OVERLAY_L4_DSR_Z_THRESHOLD,
            }
            flags.append("CCCS_BOOM_OVERLAY")

    # Contribution audit.
    def _pct_contribution(score: float | None, multiplier: float, sub_name: str) -> float | None:
        """Approximate percent contribution of a component to final CCCS.

        Simplified attribution — we know score_composite = sum(w_eff * sub),
        and each sub = weighted sum of L_i. The downstream audit wants
        per-L_i / F3 / F4 attribution vs final CCCS.
        """
        if score is None or score_composite == 0:
            return None
        w_eff = effective_weights.get(sub_name, 0.0)
        return round(w_eff * multiplier * score / score_composite * 100.0, 2)

    l1_score = pts(float(l1_obj.score_normalized)) if l1_obj else None
    l2_score = pts(float(l2_obj.score_normalized)) if l2_obj else None
    l1_contrib = _pct_contribution(l1_score, 0.30, "CS")
    l2_contrib = _pct_contribution(l2_score, 0.50, "CS")
    # L4 appears in both CS (0.20) and LC (0.40) — attribute its combined share.
    l4_value = pts(float(l4_obj.score_normalized)) if l4_obj else None
    l4_contrib: float | None = None
    if l4_value is not None and score_composite > 0:
        cs_w = effective_weights.get("CS", 0.0)
        lc_w = effective_weights.get("LC", 0.0)
        l4_contrib = round((cs_w * 0.20 + lc_w * 0.40) * l4_value / score_composite * 100.0, 2)
    l3_score = pts(float(l3_obj.score_normalized)) if l3_obj else None
    l3_contrib = _pct_contribution(l3_score, 0.60, "LC")
    f3_raw = float(f3_obj.score_normalized) if f3_obj is not None else None
    f3_contrib = _pct_contribution(f3_raw, 0.70, "MS")
    f4_margin_contrib: float | None = None
    if f4_margin_contrib_available and score_composite > 0:
        ms_w = effective_weights.get("MS", 0.0)
        f4_margin_contrib = round(ms_w * 0.30 * pts(f4_margin_z) / score_composite * 100.0, 2)

    # Confidence: base min of sub-input confidences; apply caps.
    confidences: list[float] = []
    for row in (l1_obj, l2_obj, l3_obj, l4_obj, f3_obj):
        if row is not None:
            confidences.append(float(row.confidence))
    base_confidence = min(confidences) if confidences else 0.5
    confidence = min(base_confidence, QS_ABSENT_CONFIDENCE_CAP)
    if reweighted:
        confidence = min(confidence, REWEIGHT_CONFIDENCE_CAP)

    components_available = sum(1 for v in sub_scores.values() if v is not None)

    return CccsComputedResult(
        cccs_id=str(uuid4()),
        country_code=country_code,
        date=observation_date,
        methodology_version=METHODOLOGY_VERSION,
        score_0_100=score_composite,
        regime=regime,
        regime_persistence_days=persistence_days,
        cs_score_0_100=cs_score,
        lc_score_0_100=lc_score,
        ms_score_0_100=ms_score,
        qs_score_0_100=None,
        cs_weight_effective=effective_weights.get("CS", 0.0),
        lc_weight_effective=effective_weights.get("LC", 0.0),
        ms_weight_effective=effective_weights.get("MS", 0.0),
        components_available=components_available,
        l1_contribution_pct=l1_contrib,
        l2_contribution_pct=l2_contrib,
        l3_contribution_pct=l3_contrib,
        l4_contribution_pct=l4_contrib,
        f3_contribution_pct=f3_contrib,
        f4_margin_debt_contribution_pct=f4_margin_contrib,
        boom_overlay_active=boom_active,
        boom_trigger_json=json.dumps(boom_trigger_payload, sort_keys=True)
        if boom_trigger_payload
        else None,
        confidence=confidence,
        flags=tuple(sorted(set(flags))),
    )


def persist_cccs_result(session: Session, result: CccsComputedResult) -> None:
    """Persist a computed CCCS row."""
    row = CreditCycleScore(
        cccs_id=result.cccs_id,
        country_code=result.country_code,
        date=result.date,
        methodology_version=result.methodology_version,
        score_0_100=result.score_0_100,
        regime=result.regime,
        regime_persistence_days=result.regime_persistence_days,
        cs_score_0_100=result.cs_score_0_100,
        lc_score_0_100=result.lc_score_0_100,
        ms_score_0_100=result.ms_score_0_100,
        qs_score_0_100=result.qs_score_0_100,
        cs_weight_effective=result.cs_weight_effective,
        lc_weight_effective=result.lc_weight_effective,
        ms_weight_effective=result.ms_weight_effective,
        components_available=result.components_available,
        l1_contribution_pct=result.l1_contribution_pct,
        l2_contribution_pct=result.l2_contribution_pct,
        l3_contribution_pct=result.l3_contribution_pct,
        l4_contribution_pct=result.l4_contribution_pct,
        f3_contribution_pct=result.f3_contribution_pct,
        f4_margin_debt_contribution_pct=result.f4_margin_debt_contribution_pct,
        boom_overlay_active=result.boom_overlay_active,
        boom_trigger_json=result.boom_trigger_json,
        confidence=result.confidence,
        flags=",".join(result.flags) if result.flags else None,
    )
    session.add(row)
    session.commit()


__all__ = [
    "BOOM_OVERLAY_L2_GAP_THRESHOLD_PP",
    "BOOM_OVERLAY_L4_DSR_Z_THRESHOLD",
    "BOOM_OVERLAY_SCORE_THRESHOLD",
    "CANONICAL_WEIGHTS",
    "METHODOLOGY_VERSION",
    "MIN_CORE_COMPONENTS",
    "REGIME_PERSISTENCE_MIN_DAYS",
    "REGIME_TRANSITION_DELTA_MIN",
    "CccsComputedResult",
    "apply_hysteresis",
    "classify_regime",
    "compute_cccs",
    "persist_cccs_result",
    "pts",
]
