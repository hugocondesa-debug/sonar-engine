"""F3 Risk Appetite per ``F3_RISK_APPETITE_v0.1``.

Full spec: ``docs/specs/indices/financial/F3-risk-appetite.md``.
Aggregates 5 stress/risk-appetite inputs (equity vol, bond vol, HY OAS,
IG OAS, FCI) into ``score_normalized in [0, 100]`` with **higher =
euphoria / complacency** (low vol, tight spreads, loose FCI).

Spec §4 weights: VIX 0.30 + MOVE 0.15 + HY 0.20 + IG 0.15 + FCI 0.20.
**All components sign-flipped** (high stress → low score). Minimum
3 of 5 components required; InsufficientInputsError raised otherwise.

FCI is a single component per spec (sourced as NFCI for US / CISS for
EA — brief §3 misread it as two separate components at 20+10%; this
module honours the spec per brief §9 "CC MUST read spec §4").
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
    "MIN_COMPONENTS",
    "SPEC_WEIGHTS",
    "F3Inputs",
    "F3Result",
    "RiskRegime",
    "classify_risk_regime",
    "compute_f3_risk_appetite",
]

METHODOLOGY_VERSION: str = "F3_RISK_APPETITE_v0.1"
MIN_COMPONENTS: int = 3

SPEC_WEIGHTS: dict[str, float] = {
    "vix": 0.30,
    "move": 0.15,
    "hy": 0.20,
    "ig": 0.15,
    "fci": 0.20,
}

RiskRegime = Literal["extreme_fear", "fear", "neutral", "greed", "extreme_greed"]


@dataclass(frozen=True, slots=True)
class F3Inputs:
    country_code: str
    observation_date: date_t
    vix_level: float | None
    move_level: float | None
    credit_spread_hy_bps: int | None
    credit_spread_ig_bps: int | None
    fci_level: float | None  # NFCI z-score (US) or CISS level (EA)
    crypto_vol_level: float | None = None  # diagnostic v0.1
    vix_history: Sequence[float] | None = None
    move_history: Sequence[float] | None = None
    hy_history_bps: Sequence[float] | None = None
    ig_history_bps: Sequence[float] | None = None
    fci_history: Sequence[float] | None = None
    upstream_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class F3Result:
    country_code: str
    date: date_t
    methodology_version: str
    score_normalized: float
    score_raw: float
    components_json: str
    vix_level: float | None
    move_level: float | None
    credit_spread_hy_bps: int | None
    credit_spread_ig_bps: int | None
    fci_level: float | None
    crypto_vol_level: float | None
    components_available: int
    lookback_years: int
    risk_regime: RiskRegime
    confidence: float
    flags: tuple[str, ...]


def classify_risk_regime(score_normalized: float) -> RiskRegime:
    if score_normalized < 20.0:
        return "extreme_fear"
    if score_normalized < 40.0:
        return "fear"
    if score_normalized < 60.0:
        return "neutral"
    if score_normalized < 80.0:
        return "greed"
    return "extreme_greed"


def _score_to_0_100(z: float) -> float:
    raw = 50.0 + (100.0 / 6.0) * z
    return max(0.0, min(100.0, raw))


def _confidence_from_flags(flags: tuple[str, ...]) -> float:
    conf = 1.0
    if "VOL_PROXY_GLOBAL" in flags:
        conf -= 0.15
    if "MOVE_PROXY" in flags:
        conf -= 0.10
    if "OVERLAY_MISS" in flags:
        conf -= 0.15
    if "INSUFFICIENT_HISTORY" in flags:
        conf = min(conf, 0.65)
    if "EM_COVERAGE" in flags:
        conf = min(conf, 0.70)
    if "STALE" in flags:
        conf -= 0.20
    return max(0.0, min(1.0, conf))


def compute_f3_risk_appetite(  # noqa: PLR0915
    inputs: F3Inputs,
    *,
    move_is_proxy: bool = False,
    vix_is_global_proxy: bool = False,
) -> F3Result:
    """Compute F3 risk-appetite per spec §4."""
    flags: list[str] = list(inputs.upstream_flags)
    if move_is_proxy:
        flags.append("MOVE_PROXY")
    if vix_is_global_proxy:
        flags.append("VOL_PROXY_GLOBAL")

    components: dict[str, object] = {}
    components_available = 0
    total_weight = 0.0
    z_weighted_sum = 0.0
    history_lens: list[int] = []

    def _add(
        name: str,
        current: float | None,
        history: Sequence[float] | None,
        weight: float,
    ) -> None:
        nonlocal z_weighted_sum, total_weight, components_available
        if current is None or history is None or len(history) < 2:
            components[name] = {"z": None, "value": current, "weight_effective": 0.0}
            return
        z, mu, sigma, n = rolling_zscore(history, current=float(current))
        z_signed = -z  # spec §4: sign-flip every component
        z_weighted_sum += weight * z_signed
        total_weight += weight
        components_available += 1
        history_lens.append(n)
        components[name] = {
            "z": z_signed,
            "value": current,
            "mu": mu,
            "sigma": sigma,
            "weight_nominal": weight,
            "n_obs": n,
        }

    _add("vix", inputs.vix_level, inputs.vix_history, SPEC_WEIGHTS["vix"])
    _add("move", inputs.move_level, inputs.move_history, SPEC_WEIGHTS["move"])
    _add(
        "hy",
        float(inputs.credit_spread_hy_bps) if inputs.credit_spread_hy_bps is not None else None,
        inputs.hy_history_bps,
        SPEC_WEIGHTS["hy"],
    )
    _add(
        "ig",
        float(inputs.credit_spread_ig_bps) if inputs.credit_spread_ig_bps is not None else None,
        inputs.ig_history_bps,
        SPEC_WEIGHTS["ig"],
    )
    _add("fci", inputs.fci_level, inputs.fci_history, SPEC_WEIGHTS["fci"])

    if components_available < MIN_COMPONENTS:
        err = f"F3 requires >= {MIN_COMPONENTS} components; got {components_available}/5"
        raise InsufficientInputsError(err)

    if inputs.fci_level is None:
        flags.append("OVERLAY_MISS")

    z_aggregate = z_weighted_sum / total_weight
    if math.isnan(z_aggregate):
        z_aggregate = 0.0
    score_normalized = _score_to_0_100(z_aggregate)
    regime = classify_risk_regime(score_normalized)

    # Extreme-stress informational flags per spec §6.
    if inputs.vix_level is not None and inputs.vix_level > 50.0:
        flags.append("F3_STRESS_EXTREME")
    if (
        inputs.credit_spread_hy_bps is not None
        and inputs.credit_spread_hy_bps > 1000
        and "F3_STRESS_EXTREME" not in flags
    ):
        flags.append("F3_STRESS_EXTREME")

    if history_lens and min(history_lens) < 60:
        flags.append("INSUFFICIENT_HISTORY")

    confidence = _confidence_from_flags(tuple(flags))
    lookback_years = max(1, (max(history_lens) if history_lens else 0) // 4)

    for info in components.values():
        if not isinstance(info, dict):
            continue
        z = info.get("z")
        nominal_raw = info.get("weight_nominal", 0.0) or 0.0
        nominal = float(nominal_raw) if isinstance(nominal_raw, int | float) else 0.0
        info["weight_effective"] = (nominal / total_weight) if z is not None else 0.0

    components["score_aggregate_z"] = {"value": z_aggregate}
    components["risk_regime"] = {"value": regime}

    return F3Result(
        country_code=inputs.country_code,
        date=inputs.observation_date,
        methodology_version=METHODOLOGY_VERSION,
        score_normalized=score_normalized,
        score_raw=z_aggregate,
        components_json=json.dumps(components, default=str),
        vix_level=inputs.vix_level,
        move_level=inputs.move_level,
        credit_spread_hy_bps=inputs.credit_spread_hy_bps,
        credit_spread_ig_bps=inputs.credit_spread_ig_bps,
        fci_level=inputs.fci_level,
        crypto_vol_level=inputs.crypto_vol_level,
        components_available=components_available,
        lookback_years=lookback_years,
        risk_regime=regime,
        confidence=confidence,
        flags=tuple(sorted(set(flags))),
    )
