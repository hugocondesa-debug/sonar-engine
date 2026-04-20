"""L2 Credit-to-GDP Gap per ``L2_CREDIT_GDP_GAP_v0.1`` — HP one-sided + Hamilton dual.

Full spec: ``docs/specs/indices/credit/L2-credit-to-gdp-gap.md``.

Consumes L1 ``score_raw`` (ratio in percent) as upstream input; applies
BOTH the Basel III one-sided HP filter (lambda = 400000) and the
Hamilton (2018) regression as a cross-check that removes the
endpoint-revision bias of HP at the series tail. ``score_raw`` is the
average of the two gap estimates.

Concordance classification per spec §4 step 7 with ±2pp threshold:
``both_above`` / ``both_below`` / ``divergent`` (flag
``GAP_DIVERGENT`` when the two methods disagree by > 5pp).

Phase band (placeholder per spec §11, CAL-016 recalibrate):
``deleveraging`` (< -5pp), ``neutral`` (-5..+2pp), ``boom_zone``
(+2..+10pp, CCyB activation threshold), ``danger_zone`` (>= +10pp).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

import numpy as np

from sonar.indices._helpers.hamilton_filter import (
    HAMILTON_DEFAULT_HORIZON_Q,
    HAMILTON_MIN_OBSERVATIONS,
    hamilton_residual,
)
from sonar.indices._helpers.hp_filter import (
    HP_LAMBDA_CREDIT_CYCLE,
    hp_filter_two_sided,
    hp_one_sided_endpoint,
)
from sonar.indices.exceptions import InsufficientInputsError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date as date_t

__all__ = [
    "CONCORDANCE_THRESHOLD_PP",
    "DIVERGENT_DIFF_THRESHOLD_PP",
    "ENDPOINT_REVISION_THRESHOLD_PP",
    "METHODOLOGY_VERSION",
    "MIN_HISTORY_QUARTERS",
    "CreditGdpGapInputs",
    "CreditGdpGapResult",
    "GapConcordance",
    "PhaseBand",
    "classify_concordance",
    "classify_phase_band",
    "compute_credit_gdp_gap",
]

METHODOLOGY_VERSION: str = "L2_CREDIT_GDP_GAP_v0.1"

MIN_HISTORY_QUARTERS: int = 40  # 10Y hard floor per spec §6

CONCORDANCE_THRESHOLD_PP: float = 2.0
DIVERGENT_DIFF_THRESHOLD_PP: float = 5.0
ENDPOINT_REVISION_THRESHOLD_PP: float = 3.0
PHASE_BAND_DELEVERAGING_PP: float = -5.0
PHASE_BAND_BOOM_PP: float = 2.0
PHASE_BAND_DANGER_PP: float = 10.0

GapConcordance = Literal["both_above", "both_below", "divergent"]
PhaseBand = Literal["deleveraging", "neutral", "boom_zone", "danger_zone"]


@dataclass(frozen=True, slots=True)
class CreditGdpGapInputs:
    """L2 inputs: full ratio_pct history terminating at ``observation_date``."""

    country_code: str
    observation_date: date_t
    ratio_pct_history: Sequence[float]
    score_raw_history: Sequence[float] = field(default_factory=tuple)
    hp_lambda: int = HP_LAMBDA_CREDIT_CYCLE
    hamilton_horizon_q: int = HAMILTON_DEFAULT_HORIZON_Q
    upstream_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class CreditGdpGapResult:
    """Canonical L2 output contract — mirrors ``credit_to_gdp_gap`` schema."""

    country_code: str
    date: date_t
    methodology_version: str
    score_normalized: float
    score_raw: float  # == avg(gap_hp_pp, gap_hamilton_pp)
    gap_hp_pp: float
    gap_hamilton_pp: float
    trend_gdp_pct: float
    hp_lambda: int
    hamilton_horizon_q: int
    concordance: GapConcordance
    phase_band: PhaseBand
    components_json: str
    lookback_years: int
    confidence: float
    flags: tuple[str, ...]
    source_connector: str


def classify_phase_band(gap_hp_pp: float) -> PhaseBand:
    """Spec §4 step 8 placeholder bands on HP gap."""
    if gap_hp_pp < PHASE_BAND_DELEVERAGING_PP:
        return "deleveraging"
    if gap_hp_pp < PHASE_BAND_BOOM_PP:
        return "neutral"
    if gap_hp_pp < PHASE_BAND_DANGER_PP:
        return "boom_zone"
    return "danger_zone"


def classify_concordance(gap_hp_pp: float, gap_hamilton_pp: float) -> GapConcordance:
    """Spec §4 step 7 concordance check around ±2pp threshold."""
    thr = CONCORDANCE_THRESHOLD_PP
    if gap_hp_pp > thr and gap_hamilton_pp > thr:
        return "both_above"
    if gap_hp_pp < thr and gap_hamilton_pp < thr:
        return "both_below"
    return "divergent"


def _z_clamp_5(z: float) -> float:
    if math.isnan(z):
        return 0.0
    return max(-5.0, min(5.0, z))


def _confidence_from_flags(flags: tuple[str, ...]) -> float:
    conf = 1.0
    if "HP_FAIL" in flags:
        conf = min(conf, 0.50)
    if "HAMILTON_FAIL" in flags:
        conf = min(conf, 0.50)
    if "GAP_DIVERGENT" in flags:
        conf -= 0.10
    if "HP_ENDPOINT_REVISION" in flags:
        conf -= 0.10
    if "INSUFFICIENT_HISTORY" in flags:
        conf -= 0.20
    if "CREDIT_BREAK" in flags:
        conf -= 0.10
    if "STRUCTURAL_BREAK" in flags:
        conf -= 0.20
    return max(0.0, min(1.0, conf))


def compute_credit_gdp_gap(
    inputs: CreditGdpGapInputs,
    *,
    source_connector: str = "l1_credit_gdp_stock",
) -> CreditGdpGapResult:
    """Compute L2 credit-to-GDP gap per spec §4."""
    arr = np.asarray(inputs.ratio_pct_history, dtype=float)
    if len(arr) < MIN_HISTORY_QUARTERS:
        err = (
            f"L2 gap requires >= {MIN_HISTORY_QUARTERS} quarters; "
            f"got {len(arr)} (hard floor per spec §6)"
        )
        raise InsufficientInputsError(err)

    flags: list[str] = list(inputs.upstream_flags)
    hp_lambda = inputs.hp_lambda
    hamilton_horizon = inputs.hamilton_horizon_q

    # HP one-sided at endpoint (recursive across the tail; for a single
    # compute point we only need the last trend/cycle).
    try:
        trend_hp, gap_hp_pp = hp_one_sided_endpoint(arr, lamb=hp_lambda)
    except (ValueError, RuntimeError) as e:
        err = f"HP filter failed at endpoint: {e}"
        raise InsufficientInputsError(err) from e

    # Hamilton residual at endpoint.
    if len(arr) < HAMILTON_MIN_OBSERVATIONS + hamilton_horizon - HAMILTON_DEFAULT_HORIZON_Q:
        flags.append("HAMILTON_FAIL")
        gap_hamilton_pp = gap_hp_pp  # fallback to HP value
    else:
        try:
            gap_hamilton_pp = hamilton_residual(arr, h=hamilton_horizon)
        except ValueError:
            flags.append("HAMILTON_FAIL")
            gap_hamilton_pp = gap_hp_pp

    # Endpoint-revision diagnostic: compare one-sided HP (terminal point
    # of full refit) vs two-sided HP run over the whole series.
    trend_two, _cycle_two = hp_filter_two_sided(arr, lamb=hp_lambda)
    two_sided_endpoint = float(trend_two[-1])
    endpoint_diff = abs(arr[-1] - two_sided_endpoint - gap_hp_pp)
    if endpoint_diff > ENDPOINT_REVISION_THRESHOLD_PP:
        flags.append("HP_ENDPOINT_REVISION")

    # Concordance & divergence.
    if abs(gap_hp_pp - gap_hamilton_pp) > DIVERGENT_DIFF_THRESHOLD_PP:
        flags.append("GAP_DIVERGENT")
    concordance = classify_concordance(gap_hp_pp, gap_hamilton_pp)

    score_raw = (gap_hp_pp + gap_hamilton_pp) / 2.0
    phase_band = classify_phase_band(gap_hp_pp)

    # Rolling 20Y z-score on historical score_raw if provided; fallback
    # to standard-deviation of ratio residuals.
    hist = (
        np.asarray(inputs.score_raw_history, dtype=float)
        if inputs.score_raw_history
        else arr - trend_hp  # residual history vs single terminal trend
    )
    if len(hist) >= 2:
        mu = float(hist.mean())
        sigma = float(hist.std(ddof=1))
    else:
        mu = 0.0
        sigma = 0.0
    z_raw = (score_raw - mu) / sigma if sigma > 1e-12 else 0.0
    score_normalized = _z_clamp_5(z_raw)

    lookback_years = max(1, len(arr) // 4)
    confidence = _confidence_from_flags(tuple(flags))

    components = {
        "ratio_pct": float(arr[-1]),
        "trend_hp_pct": trend_hp,
        "gap_hp_pp": gap_hp_pp,
        "gap_hamilton_pp": gap_hamilton_pp,
        "hp_lambda": hp_lambda,
        "hamilton_horizon_q": hamilton_horizon,
        "phase_band": phase_band,
        "concordance": concordance,
        "endpoint_revision_pp": endpoint_diff,
    }

    return CreditGdpGapResult(
        country_code=inputs.country_code,
        date=inputs.observation_date,
        methodology_version=METHODOLOGY_VERSION,
        score_normalized=score_normalized,
        score_raw=score_raw,
        gap_hp_pp=gap_hp_pp,
        gap_hamilton_pp=gap_hamilton_pp,
        trend_gdp_pct=trend_hp,
        hp_lambda=hp_lambda,
        hamilton_horizon_q=hamilton_horizon,
        concordance=concordance,
        phase_band=phase_band,
        components_json=json.dumps(components),
        lookback_years=lookback_years,
        confidence=confidence,
        flags=tuple(sorted(set(flags))),
        source_connector=source_connector,
    )
