"""F1 Valuations per ``F1_VALUATIONS_v0.1``.

Full spec: ``docs/specs/indices/financial/F1-valuations.md``.
Aggregates 5 valuation components (CAPE, Buffett ratio, ERP, forward
P/E, BIS property gap) into ``score_normalized in [0, 100]`` via the
canonical 20Y-rolling-z-score + ``clip(50 + 16.67*z_clamped, 0, 100)``
mapping. Higher score = more expensive / euphoric.

Spec §4 weights (CAPE 0.35 + Buffett 0.20 + ERP 0.20 + FwdPE 0.10 +
Property 0.15 = 1.00). ERP is **sign-flipped** so high score is
consistently "expensive". When a component is NULL the remaining
weights are renormalized per spec §4 step 5.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from sonar.indices._helpers.z_score_rolling import rolling_zscore
from sonar.indices.exceptions import InsufficientInputsError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date as date_t

__all__ = [
    "METHODOLOGY_VERSION",
    "MIN_HISTORY_QUARTERS",
    "SPEC_WEIGHTS",
    "F1Inputs",
    "F1Result",
    "ValuationBand",
    "classify_valuation_band",
    "compute_f1_valuations",
]

METHODOLOGY_VERSION: str = "F1_VALUATIONS_v0.1"
MIN_HISTORY_QUARTERS: int = 60  # 15Y hard floor per spec §6

SPEC_WEIGHTS: dict[str, float] = {
    "cape": 0.35,
    "buffett": 0.20,
    "erp": 0.20,  # sign-flipped inside algorithm
    "fwd_pe": 0.10,
    "property": 0.15,
}

ValuationBand = Literal["cheap", "fair", "stretched", "bubble"]


@dataclass(frozen=True, slots=True)
class F1Inputs:
    """Per-date inputs + 20Y rolling baselines for each component."""

    country_code: str
    observation_date: date_t
    # Current values (None when unavailable → component dropped + reweight).
    cape_ratio: float | None
    buffett_ratio: float | None
    erp_median_bps: int | None
    forward_pe: float | None
    property_gap_pp: float | None
    # 20Y historical baselines for z-score; each must match the field above.
    cape_history: Sequence[float] | None = None
    buffett_history: Sequence[float] | None = None
    erp_history_bps: Sequence[float] | None = None
    forward_pe_history: Sequence[float] | None = None
    property_gap_history: Sequence[float] | None = None
    upstream_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class F1Result:
    country_code: str
    date: date_t
    methodology_version: str
    score_normalized: float
    score_raw: float
    components_json: str
    cape_ratio: float | None
    erp_median_bps: int | None
    buffett_ratio: float | None
    forward_pe: float | None
    property_gap_pp: float | None
    lookback_years: int
    valuation_band: ValuationBand
    confidence: float
    flags: tuple[str, ...]
    source_overlay: str | None = None


def classify_valuation_band(score_normalized: float) -> ValuationBand:
    if score_normalized < 30.0:
        return "cheap"
    if score_normalized < 55.0:
        return "fair"
    if score_normalized < 75.0:
        return "stretched"
    return "bubble"


def _score_to_0_100(z: float) -> float:
    raw = 50.0 + (100.0 / 6.0) * z
    return max(0.0, min(100.0, raw))


def _confidence_from_flags(flags: tuple[str, ...]) -> float:
    conf = 1.0
    if "OVERLAY_MISS" in flags:
        conf = min(conf, 0.60)
    if "STALE" in flags:
        conf -= 0.20
    if "INSUFFICIENT_HISTORY" in flags:
        conf = min(conf, 0.65)
    if "EM_COVERAGE" in flags:
        conf = min(conf, 0.70)
    if "F1_CAPE_ONLY" in flags:
        conf = min(conf, 0.55)
    if "ERP_METHOD_DIVERGENCE" in flags:
        conf -= 0.05
    return max(0.0, min(1.0, conf))


def compute_f1_valuations(
    inputs: F1Inputs,
    *,
    source_overlay: str | None = "erp_canonical:ERP_CANONICAL_v0.1",
) -> F1Result:
    """Compute F1 valuations per spec §4."""
    flags: list[str] = list(inputs.upstream_flags)

    # Collect (z_score, weight) pairs per available component.
    components: dict[str, dict[str, object]] = {}
    z_weighted_sum = 0.0
    total_weight = 0.0
    history_lens: list[int] = []

    def _add_component(
        name: str,
        current: float | None,
        history: Sequence[float] | None,
        weight: float,
        *,
        sign_flip: bool = False,
    ) -> None:
        nonlocal z_weighted_sum, total_weight
        if current is None or history is None or len(history) < 2:
            components[name] = {"z": None, "value": current, "weight_effective": 0.0}
            return
        z, mu, sigma, n = rolling_zscore(history, current=float(current))
        if sign_flip:
            z = -z
        signed_weight = weight
        z_weighted_sum += signed_weight * z
        total_weight += signed_weight
        history_lens.append(n)
        components[name] = {
            "z": z,
            "value": current,
            "mu": mu,
            "sigma": sigma,
            "weight_nominal": weight,
            "n_obs": n,
        }

    _add_component("cape", inputs.cape_ratio, inputs.cape_history, SPEC_WEIGHTS["cape"])
    _add_component(
        "buffett",
        inputs.buffett_ratio,
        inputs.buffett_history,
        SPEC_WEIGHTS["buffett"],
    )
    _add_component(
        "erp",
        float(inputs.erp_median_bps) if inputs.erp_median_bps is not None else None,
        inputs.erp_history_bps,
        SPEC_WEIGHTS["erp"],
        sign_flip=True,  # high ERP = cheap equity → invert for "expensive" score
    )
    _add_component(
        "fwd_pe",
        inputs.forward_pe,
        inputs.forward_pe_history,
        SPEC_WEIGHTS["fwd_pe"],
    )
    _add_component(
        "property",
        inputs.property_gap_pp,
        inputs.property_gap_history,
        SPEC_WEIGHTS["property"],
    )

    # Flag ERP missing specifically.
    if components["erp"]["z"] is None and inputs.erp_median_bps is None:
        flags.append("OVERLAY_MISS")

    # CAPE-only degenerate case.
    has_cape = components["cape"]["z"] is not None
    others_missing = all(
        components[k]["z"] is None for k in ("buffett", "erp", "fwd_pe", "property")
    )
    if has_cape and others_missing:
        flags.append("F1_CAPE_ONLY")

    if total_weight <= 0.0:
        raise InsufficientInputsError("F1: no valuation components available")

    # Renormalize weights across available components.
    z_aggregate = z_weighted_sum / total_weight
    if math.isnan(z_aggregate):
        z_aggregate = 0.0
    score_normalized = _score_to_0_100(z_aggregate)
    score_raw = z_aggregate
    valuation_band = classify_valuation_band(score_normalized)

    if score_normalized > 95.0:
        flags.append("F1_EXTREME_HIGH")

    # History length flags.
    if history_lens and min(history_lens) < MIN_HISTORY_QUARTERS:
        flags.append("INSUFFICIENT_HISTORY")

    confidence = _confidence_from_flags(tuple(flags))
    lookback_years = max(1, (max(history_lens) if history_lens else 0) // 4)

    for _name, info in components.items():
        z = info.get("z")
        nominal_raw = info.get("weight_nominal", 0.0) or 0.0
        nominal = float(nominal_raw) if isinstance(nominal_raw, int | float) else 0.0
        info["weight_effective"] = (nominal / total_weight) if z is not None else 0.0

    components["score_aggregate_z"] = {"value": z_aggregate}
    components["valuation_band"] = {"value": valuation_band}

    return F1Result(
        country_code=inputs.country_code,
        date=inputs.observation_date,
        methodology_version=METHODOLOGY_VERSION,
        score_normalized=score_normalized,
        score_raw=score_raw,
        components_json=json.dumps(components, default=str),
        cape_ratio=inputs.cape_ratio,
        erp_median_bps=inputs.erp_median_bps,
        buffett_ratio=inputs.buffett_ratio,
        forward_pe=inputs.forward_pe,
        property_gap_pp=inputs.property_gap_pp,
        lookback_years=lookback_years,
        valuation_band=valuation_band,
        confidence=confidence,
        flags=tuple(sorted(set(flags))),
        source_overlay=source_overlay,
    )
