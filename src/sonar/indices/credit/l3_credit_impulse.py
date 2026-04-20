"""L3 Credit Impulse per ``L3_CREDIT_IMPULSE_v0.1`` — Biggs-Mayer-Pick 2010.

Full spec: ``docs/specs/indices/credit/L3-credit-impulse.md``.
Independent of L2 (no HP gap dependency) but shares raw credit stock +
GDP nominal with L1. Consumed by ``cycles/credit-cccs`` (L4) with
~50% weight inside the FM (Flow Momentum) sub-index.

Formula (``ma4`` smoothing, spec §4 default):

    impulse_pp_t = mean{ (Delta^2_4 credit_k / gdp_{k-4}) * 100
                        for k in {t, t-1Q, t-2Q, t-3Q} }

Delta^2_4 credit_t = (credit_t - credit_{t-4}) - (credit_{t-4} - credit_{t-8})
                   = delta_flow_lcu.

State classifier per spec §4 step 9 placeholders (CAL-017 recalibrate
after 5Y of production data).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

import numpy as np

from sonar.indices.exceptions import InsufficientInputsError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date as date_t

__all__ = [
    "CONTRACTING_THRESHOLD_PP",
    "METHODOLOGY_VERSION",
    "MIN_HISTORY_QUARTERS",
    "NEUTRAL_THRESHOLD_PP",
    "OUTLIER_THRESHOLD_PP",
    "CreditImpulseInputs",
    "CreditImpulseResult",
    "CreditImpulseState",
    "classify_state",
    "compute_credit_impulse",
    "compute_impulse_pp",
]

METHODOLOGY_VERSION: str = "L3_CREDIT_IMPULSE_v0.1"

MIN_HISTORY_QUARTERS: int = 12  # spec §6 hard floor (t, t-4, t-8 + ma4 offset)
CONTRACTING_THRESHOLD_PP: float = -0.5
NEUTRAL_THRESHOLD_PP: float = 0.5
OUTLIER_THRESHOLD_PP: float = 10.0  # spec §6 IMPULSE_OUTLIER

Smoothing = Literal["raw", "ma4"]
ImpulseSegment = Literal["PNFS", "HH", "NFC"]
CreditImpulseState = Literal["accelerating", "decelerating", "neutral", "contracting"]


@dataclass(frozen=True, slots=True)
class CreditImpulseInputs:
    """L3 per-quarter inputs + optional 20Y z-score history.

    ``credit_stock_lcu_history`` must contain at least 12 observations
    ending at ``observation_date``; index t = len-1 is ``date``, t-4 is
    ``date - 4Q``, etc. ``gdp_nominal_lcu_history`` mirrors the same
    grid (point-quarterly, NOT 4Q rolling sum — see spec §2
    precondition).
    """

    country_code: str
    observation_date: date_t
    credit_stock_lcu_history: Sequence[float]
    gdp_nominal_lcu_history: Sequence[float]
    impulse_pp_history: Sequence[float] = field(default_factory=tuple)
    series_variant: Literal["Q", "F"] = "Q"
    smoothing: Smoothing = "ma4"
    segment: ImpulseSegment = "PNFS"
    upstream_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class CreditImpulseResult:
    """Canonical L3 output — mirrors ``credit_impulse`` table schema."""

    country_code: str
    date: date_t
    methodology_version: str
    segment: ImpulseSegment
    score_normalized: float
    score_raw: float
    impulse_pp: float
    flow_t_lcu: float
    flow_t_minus4_lcu: float
    delta_flow_lcu: float
    gdp_t_minus4_lcu: float
    series_variant: Literal["Q", "F"]
    smoothing: Smoothing
    state: CreditImpulseState
    components_json: str
    lookback_years: int
    confidence: float
    flags: tuple[str, ...]
    source_connector: str


def compute_impulse_pp(
    credit_t: float,
    credit_t_minus_4: float,
    credit_t_minus_8: float,
    gdp_t_minus_4: float,
) -> tuple[float, float, float, float]:
    """Return ``(flow_recent, flow_prior, delta_flow, impulse_pp)``."""
    if gdp_t_minus_4 <= 0.0:
        err = f"gdp_t_minus_4 must be positive, got {gdp_t_minus_4}"
        raise InsufficientInputsError(err)
    flow_recent = credit_t - credit_t_minus_4
    flow_prior = credit_t_minus_4 - credit_t_minus_8
    delta_flow = flow_recent - flow_prior
    impulse_pp = delta_flow / gdp_t_minus_4 * 100.0
    return flow_recent, flow_prior, delta_flow, impulse_pp


def classify_state(
    impulse_pp: float,
    prior_impulse_pp: float | None = None,
) -> CreditImpulseState:
    """State classifier per spec §4 step 9."""
    if impulse_pp < CONTRACTING_THRESHOLD_PP:
        return "contracting"
    if -NEUTRAL_THRESHOLD_PP <= impulse_pp <= NEUTRAL_THRESHOLD_PP:
        return "neutral"
    # Positive regime — discriminate accelerating vs decelerating by
    # the 2Q derivative of impulse.
    if prior_impulse_pp is None:
        return "accelerating"
    return "accelerating" if impulse_pp > prior_impulse_pp else "decelerating"


def _z_clamp_5(z: float) -> float:
    if math.isnan(z):
        return 0.0
    return max(-5.0, min(5.0, z))


def _confidence_from_flags(flags: tuple[str, ...]) -> float:
    conf = 1.0
    if "IMPULSE_OUTLIER" in flags:
        conf -= 0.20
    if "INSUFFICIENT_HISTORY" in flags:
        conf -= 0.20
    if "L1_VARIANT_MISMATCH" in flags:
        conf -= 0.10
    if "STRUCTURAL_BREAK" in flags:
        conf -= 0.20
    if "STALE" in flags:
        conf -= 0.20
    if "EM_COVERAGE" in flags:
        conf = min(conf, 0.70)
    if "CALIBRATION_STALE" in flags:
        conf -= 0.15
    return max(0.0, min(1.0, conf))


def compute_credit_impulse(  # noqa: PLR0912, PLR0915
    inputs: CreditImpulseInputs,
    *,
    source_connector: str = "bis_ws_tc",
) -> CreditImpulseResult:
    """Compute L3 credit impulse per spec §4."""
    credit = np.asarray(inputs.credit_stock_lcu_history, dtype=float)
    gdp = np.asarray(inputs.gdp_nominal_lcu_history, dtype=float)
    if len(credit) < MIN_HISTORY_QUARTERS or len(gdp) < MIN_HISTORY_QUARTERS:
        err = (
            f"L3 requires >= {MIN_HISTORY_QUARTERS} quarters of credit+GDP history; "
            f"got credit={len(credit)}, gdp={len(gdp)}"
        )
        raise InsufficientInputsError(err)
    if len(credit) != len(gdp):
        err = f"credit ({len(credit)}) and gdp ({len(gdp)}) histories must align"
        raise InsufficientInputsError(err)

    flags: list[str] = list(inputs.upstream_flags)

    n = len(credit)
    t = n - 1  # endpoint = observation_date

    # Smoothing: for "ma4", average impulses at t, t-1, t-2, t-3; needs
    # credit stocks at {t, t-1, ..., t-8-3 = t-11}, i.e. 12 points.
    if inputs.smoothing == "ma4":
        impulses: list[float] = []
        for offset in range(4):
            k = t - offset
            _fr, _fp, _delta, imp_k = compute_impulse_pp(
                credit[k],
                credit[k - 4],
                credit[k - 8],
                gdp[k - 4],
            )
            impulses.append(imp_k)
        impulse_pp = float(np.mean(impulses))
        flow_recent_final = credit[t] - credit[t - 4]
        flow_prior_final = credit[t - 4] - credit[t - 8]
        delta_flow = flow_recent_final - flow_prior_final
    else:
        flow_recent_final, flow_prior_final, delta_flow, impulse_pp = compute_impulse_pp(
            credit[t], credit[t - 4], credit[t - 8], gdp[t - 4]
        )

    # Outlier detection on raw delta_flow / gdp before smoothing.
    raw_impulse_pp = delta_flow / gdp[t - 4] * 100.0
    if abs(raw_impulse_pp) > OUTLIER_THRESHOLD_PP:
        flags.append("IMPULSE_OUTLIER")

    # Rolling 20Y z-score.
    hist = np.asarray(inputs.impulse_pp_history, dtype=float)
    if len(hist) >= 2:
        mu = float(hist.mean())
        sigma = float(hist.std(ddof=1))
    else:
        # Fallback: bootstrap from per-quarter impulses over available history.
        bootstrap: list[float] = []
        for k in range(8, n):
            if gdp[k - 4] > 0:
                _fr, _fp, _df, imp_k = compute_impulse_pp(
                    credit[k], credit[k - 4], credit[k - 8], gdp[k - 4]
                )
                bootstrap.append(imp_k)
        if len(bootstrap) >= 2:
            mu = float(np.mean(bootstrap))
            sigma = float(np.std(bootstrap, ddof=1))
        else:
            mu = 0.0
            sigma = 0.0
    if len(hist) < 80 and len(hist) >= 1:
        flags.append("INSUFFICIENT_HISTORY")

    z_raw = (impulse_pp - mu) / sigma if sigma > 1e-12 else 0.0
    score_normalized = _z_clamp_5(z_raw)

    # Prior impulse (for accelerating vs decelerating discrimination).
    prior_impulse_pp: float | None
    try:
        prior_impulse_pp = compute_impulse_pp(
            credit[t - 1], credit[t - 5], credit[t - 9], gdp[t - 5]
        )[3]
    except (IndexError, InsufficientInputsError):
        prior_impulse_pp = None

    state = classify_state(impulse_pp, prior_impulse_pp)
    confidence = _confidence_from_flags(tuple(flags))

    lookback_years = max(1, len(hist) // 4) if len(hist) >= 4 else 1

    components = {
        "credit_t_lcu": float(credit[t]),
        "credit_t_minus_4_lcu": float(credit[t - 4]),
        "credit_t_minus_8_lcu": float(credit[t - 8]),
        "gdp_t_minus_4_lcu": float(gdp[t - 4]),
        "flow_recent_lcu": float(flow_recent_final),
        "flow_prior_lcu": float(flow_prior_final),
        "delta_flow_lcu": float(delta_flow),
        "impulse_pp": impulse_pp,
        "smoothing": inputs.smoothing,
        "segment": inputs.segment,
        "series_variant": inputs.series_variant,
        "rolling_mean_20y_pp": mu,
        "rolling_std_20y_pp": sigma,
    }

    return CreditImpulseResult(
        country_code=inputs.country_code,
        date=inputs.observation_date,
        methodology_version=METHODOLOGY_VERSION,
        segment=inputs.segment,
        score_normalized=score_normalized,
        score_raw=impulse_pp,
        impulse_pp=impulse_pp,
        flow_t_lcu=float(flow_recent_final),
        flow_t_minus4_lcu=float(flow_prior_final),
        delta_flow_lcu=float(delta_flow),
        gdp_t_minus4_lcu=float(gdp[t - 4]),
        series_variant=inputs.series_variant,
        smoothing=inputs.smoothing,
        state=state,
        components_json=json.dumps(components),
        lookback_years=lookback_years,
        confidence=confidence,
        flags=tuple(sorted(set(flags))),
        source_connector=source_connector,
    )
