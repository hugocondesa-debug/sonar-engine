"""M2 Taylor Gaps — monetary-rule deviation index.

Spec: docs/specs/indices/monetary/M2-taylor-gaps.md @
``M2_TAYLOR_GAPS_v0.1``.

4 Taylor variants; RD sub-index per Cap 15.5 weights
(1993 0.30 / 1999 0.25 / forward 0.30 / inertia 0.15)::

    T1993     = r* + pi + 0.5*(pi - pi*) + 0.5*(y - y*)
    T1999     = r* + pi + 0.5*(pi - pi*) + 1.0*(y - y*)
    Tinertia  = 0.85*prev_policy_rate + 0.15*T1993
    Tforward  = r* + pi_h + 0.5*(pi_h - pi*) + 0.5*(y - y*)

    gap_v   = policy_rate - T_v
    RD_raw  = 0.30*z(gap_1993) + 0.25*z(gap_1999)
            + 0.30*z(gap_forward) + 0.15*z(gap_inertia)
    score_normalized = clip(50 + 16.67 * RD_raw, 0, 100)

Higher = tighter vs rule (positive gap = hawkish). Requires >= 2
variants computable or raises :class:`InsufficientDataError`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from statistics import median
from typing import TYPE_CHECKING

from sonar.indices._helpers.z_score_rolling import rolling_zscore
from sonar.overlays.exceptions import InsufficientDataError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date

METHODOLOGY_VERSION: str = "M2_TAYLOR_GAPS_v0.1"
DEFAULT_LOOKBACK_YEARS: int = 30
TIER4_LOOKBACK_YEARS: int = 15
MIN_VARIANTS_FOR_COMPUTE: int = 2
TAYLOR_INERTIA_RHO: float = 0.85  # placeholder per spec §4 (recalibrate)
VARIANT_DIVERGE_THRESHOLD_PP: float = 0.01  # 1pp per spec §4 step 12

VARIANT_WEIGHTS: dict[str, float] = {
    "taylor_1993": 0.30,
    "taylor_1999": 0.25,
    "taylor_forward": 0.30,
    "taylor_inertia": 0.15,
}


@dataclass(frozen=True, slots=True)
class M2TaylorGapsInputs:
    """Inputs for a single (country, date) M2 compute."""

    country_code: str
    observation_date: date
    policy_rate_pct: float
    inflation_yoy_pct: float
    inflation_target_pct: float
    output_gap_pct: float
    r_star_pct: float
    prev_policy_rate_pct: float | None = None  # lag for inertia variant
    inflation_forecast_2y_pct: float | None = None  # for forward variant
    gap_1993_history: Sequence[float] = field(default_factory=tuple)
    gap_1999_history: Sequence[float] = field(default_factory=tuple)
    gap_forward_history: Sequence[float] = field(default_factory=tuple)
    gap_inertia_history: Sequence[float] = field(default_factory=tuple)
    r_star_source: str = "HLW"
    output_gap_source: str = "CBO"
    lookback_years: int = DEFAULT_LOOKBACK_YEARS
    source_connector: tuple[str, ...] = ()
    upstream_flags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class M2TaylorGapsResult:
    """Canonical M2 output contract — mirrors ``monetary_m2_taylor_gaps`` schema."""

    country_code: str
    date: date
    methodology_version: str
    score_normalized: float
    score_raw: float  # median_gap_pp
    taylor_implied_pct: float
    taylor_gap_pp: float
    taylor_uncertainty_pp: float
    r_star_source: str
    output_gap_source: str | None
    variants_computed: int
    components_json: str
    lookback_years: int
    confidence: float
    flags: tuple[str, ...]
    source_connector: str


def compute_m2_taylor_gaps(inputs: M2TaylorGapsInputs) -> M2TaylorGapsResult:  # noqa: PLR0915
    """Compute M2 Taylor gaps per spec §4 — complexity per spec 4 variants."""
    flags: list[str] = list(inputs.upstream_flags)

    pi = inputs.inflation_yoy_pct
    pi_star = inputs.inflation_target_pct
    y_gap = inputs.output_gap_pct
    r_star = inputs.r_star_pct
    policy = inputs.policy_rate_pct

    # Variant 1: Taylor 1993.
    t1993 = r_star + pi + 0.5 * (pi - pi_star) + 0.5 * y_gap
    gap_1993 = policy - t1993

    # Variant 2: Taylor 1999 (stronger output response).
    t1999 = r_star + pi + 0.5 * (pi - pi_star) + 1.0 * y_gap
    gap_1999 = policy - t1999

    # Variant 3: Taylor with inertia (requires prev_policy_rate).
    gap_inertia: float | None = None
    if inputs.prev_policy_rate_pct is not None:
        t_inertia = (
            TAYLOR_INERTIA_RHO * inputs.prev_policy_rate_pct + (1 - TAYLOR_INERTIA_RHO) * t1993
        )
        gap_inertia = policy - t_inertia

    # Variant 4: Forward-looking (requires inflation forecast).
    gap_forward: float | None = None
    if inputs.inflation_forecast_2y_pct is not None:
        pi_h = inputs.inflation_forecast_2y_pct
        t_forward = r_star + pi_h + 0.5 * (pi_h - pi_star) + 0.5 * y_gap
        gap_forward = policy - t_forward

    # Collect available gaps.
    available_variants: list[tuple[str, float, Sequence[float]]] = [
        ("taylor_1993", gap_1993, inputs.gap_1993_history),
        ("taylor_1999", gap_1999, inputs.gap_1999_history),
    ]
    if gap_forward is not None:
        available_variants.append(("taylor_forward", gap_forward, inputs.gap_forward_history))
    if gap_inertia is not None:
        available_variants.append(("taylor_inertia", gap_inertia, inputs.gap_inertia_history))

    if len(available_variants) < MIN_VARIANTS_FOR_COMPUTE:
        msg = (
            f"M2 requires >= {MIN_VARIANTS_FOR_COMPUTE} variants; "
            f"got {len(available_variants)} for {inputs.country_code} "
            f"{inputs.observation_date}"
        )
        raise InsufficientDataError(msg)

    gap_values = [g for _, g, _ in available_variants]
    median_gap_pp = float(median(gap_values))
    range_pp = max(gap_values) - min(gap_values)

    if range_pp > VARIANT_DIVERGE_THRESHOLD_PP:
        flags.append("TAYLOR_VARIANT_DIVERGE")

    # Per-variant z-score + weighted RD_raw.
    rd_raw = 0.0
    total_weight = sum(VARIANT_WEIGHTS[name] for name, _, _ in available_variants)
    components: dict[str, object] = {}
    hist_floor = int(inputs.lookback_years * 12 * 0.8)
    insufficient_history = 0
    for name, gap, history in available_variants:
        z, _mu, _sigma, n_obs = rolling_zscore(history, current=gap)
        if n_obs < hist_floor:
            insufficient_history += 1
        w_effective = VARIANT_WEIGHTS[name] / total_weight
        rd_raw += w_effective * z
        components[f"{name}_gap_pp"] = gap
        components[f"{name}_z"] = z
        components[f"{name}_weight_effective"] = w_effective

    components["median_gap_pp"] = median_gap_pp
    components["range_pp"] = range_pp
    components["weights_in_RD"] = dict(VARIANT_WEIGHTS)

    if insufficient_history > 0:
        flags.append("INSUFFICIENT_HISTORY")

    score_normalized = max(0.0, min(100.0, 50.0 + 16.67 * rd_raw))

    # taylor_implied_pct = median of variant prescribed rates.
    implied_rates = [policy - g for g in gap_values]
    taylor_implied_pct = float(median(implied_rates))

    confidence = 1.0 - 0.10 * insufficient_history - 0.05 * (4 - len(available_variants))
    confidence = max(0.0, min(1.0, confidence))

    return M2TaylorGapsResult(
        country_code=inputs.country_code,
        date=inputs.observation_date,
        methodology_version=METHODOLOGY_VERSION,
        score_normalized=score_normalized,
        score_raw=median_gap_pp,
        taylor_implied_pct=taylor_implied_pct,
        taylor_gap_pp=median_gap_pp,
        taylor_uncertainty_pp=range_pp,
        r_star_source=inputs.r_star_source,
        output_gap_source=inputs.output_gap_source,
        variants_computed=len(available_variants),
        components_json=json.dumps(components, sort_keys=True),
        lookback_years=inputs.lookback_years,
        confidence=confidence,
        flags=tuple(sorted(set(flags))),
        source_connector=",".join(sorted(inputs.source_connector))
        if inputs.source_connector
        else "",
    )


__all__ = [
    "DEFAULT_LOOKBACK_YEARS",
    "METHODOLOGY_VERSION",
    "MIN_VARIANTS_FOR_COMPUTE",
    "TAYLOR_INERTIA_RHO",
    "TIER4_LOOKBACK_YEARS",
    "VARIANT_WEIGHTS",
    "M2TaylorGapsInputs",
    "M2TaylorGapsResult",
    "compute_m2_taylor_gaps",
]
