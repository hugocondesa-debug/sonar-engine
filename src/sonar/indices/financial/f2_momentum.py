"""F2 Momentum per ``F2_MOMENTUM_v0.1``.

Full spec: ``docs/specs/indices/financial/F2-momentum.md``.
Aggregates 5 momentum components (3M / 6M / 12M price returns, breadth
above 200d MA, cross-asset risk-on signal) into ``score_normalized``
in ``[0, 100]``. Higher score = strong positive momentum / risk-on.

Spec §4 weights: 0.20 each (5 x 0.20 = 1.0).

Cross-asset risk-on signal per spec §4:
    risk_on = sign(equity_3m) - sign(vix_3m) + sign(comm_3m) - sign(usd_3m) +
              sign(-credit_hy_3m)  # spread tightening flipped
Standardized against 20Y rolling baseline to emit cross_asset_z.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

import numpy as np

from sonar.indices._helpers.z_score_rolling import rolling_zscore
from sonar.indices.exceptions import InsufficientInputsError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date as date_t

__all__ = [
    "METHODOLOGY_VERSION",
    "MIN_HISTORY_QUARTERS",
    "SPEC_WEIGHTS",
    "F2Inputs",
    "F2Result",
    "MomentumState",
    "classify_momentum_state",
    "compute_f2_momentum",
    "risk_on_signal",
]

METHODOLOGY_VERSION: str = "F2_MOMENTUM_v0.1"
MIN_HISTORY_QUARTERS: int = 40  # 10Y hard floor (spec §6 Tier 3-4)

SPEC_WEIGHTS: dict[str, float] = {
    "mom_3m": 0.20,
    "mom_6m": 0.20,
    "mom_12m": 0.20,
    "breadth": 0.20,
    "cross_asset": 0.20,
}

MomentumState = Literal["strong_up", "weak_up", "flat", "weak_down", "strong_down"]


@dataclass(frozen=True, slots=True)
class F2Inputs:
    country_code: str
    observation_date: date_t
    mom_3m_pct: float | None
    mom_6m_pct: float | None
    mom_12m_pct: float | None
    breadth_above_ma200_pct: float | None
    cross_asset_signal: float | None  # raw risk_on value at t, computed upstream
    mom_3m_history_pct: Sequence[float] | None = None
    mom_6m_history_pct: Sequence[float] | None = None
    mom_12m_history_pct: Sequence[float] | None = None
    breadth_history_pct: Sequence[float] | None = None
    cross_asset_history: Sequence[float] | None = None
    primary_index: str = "SPX"
    upstream_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class F2Result:
    country_code: str
    date: date_t
    methodology_version: str
    score_normalized: float
    score_raw: float
    components_json: str
    mom_3m_pct: float | None
    mom_6m_pct: float | None
    mom_12m_pct: float | None
    breadth_above_ma200_pct: float | None
    cross_asset_score: float | None
    primary_index: str
    lookback_years: int
    momentum_state: MomentumState
    confidence: float
    flags: tuple[str, ...]


def classify_momentum_state(score_normalized: float) -> MomentumState:
    if score_normalized >= 75.0:
        return "strong_up"
    if score_normalized >= 55.0:
        return "weak_up"
    if score_normalized >= 45.0:
        return "flat"
    if score_normalized >= 25.0:
        return "weak_down"
    return "strong_down"


def risk_on_signal(
    equity_3m: float | None,
    vix_3m: float | None,
    commodities_3m: float | None,
    usd_3m: float | None,
    credit_hy_3m: float | None,
) -> float:
    """Spec §4 risk-on composite (5 sub-assets when all present)."""

    def _sign(x: float | None) -> float:
        if x is None or math.isnan(x):
            return 0.0
        if x > 0:
            return 1.0
        if x < 0:
            return -1.0
        return 0.0

    return (
        _sign(equity_3m)
        - _sign(vix_3m)
        + _sign(commodities_3m)
        - _sign(usd_3m)
        + _sign(-credit_hy_3m if credit_hy_3m is not None else None)
    )


def _score_to_0_100(z: float) -> float:
    raw = 50.0 + (100.0 / 6.0) * z
    return max(0.0, min(100.0, raw))


def _confidence_from_flags(flags: tuple[str, ...]) -> float:
    conf = 1.0
    if "BREADTH_PROXY" in flags:
        conf -= 0.15
    if "CROSS_ASSET_PARTIAL" in flags:
        conf -= 0.10
    if "INSUFFICIENT_HISTORY" in flags:
        conf = min(conf, 0.65)
    if "EM_COVERAGE" in flags:
        conf = min(conf, 0.70)
    if "STALE" in flags:
        conf -= 0.20
    return max(0.0, min(1.0, conf))


def compute_f2_momentum(  # noqa: PLR0915
    inputs: F2Inputs,
    *,
    breadth_is_proxy: bool = False,
    cross_asset_n_assets: int = 5,
) -> F2Result:
    """Compute F2 momentum per spec §4."""
    flags: list[str] = list(inputs.upstream_flags)
    if breadth_is_proxy:
        flags.append("BREADTH_PROXY")
    # Spec §6 threshold: < 6/8 available → CROSS_ASSET_PARTIAL.
    if cross_asset_n_assets < 5:
        flags.append("CROSS_ASSET_PARTIAL")

    components: dict[str, object] = {}
    total_weight = 0.0
    z_weighted_sum = 0.0
    history_lens: list[int] = []

    def _add(
        name: str,
        current: float | None,
        history: Sequence[float] | None,
        weight: float,
    ) -> None:
        nonlocal z_weighted_sum, total_weight
        if current is None or history is None or len(history) < 2:
            components[name] = {"z": None, "value": current, "weight_effective": 0.0}
            return
        z, mu, sigma, n = rolling_zscore(history, current=float(current))
        z_weighted_sum += weight * z
        total_weight += weight
        history_lens.append(n)
        components[name] = {
            "z": z,
            "value": current,
            "mu": mu,
            "sigma": sigma,
            "weight_nominal": weight,
            "n_obs": n,
        }

    _add("mom_3m", inputs.mom_3m_pct, inputs.mom_3m_history_pct, SPEC_WEIGHTS["mom_3m"])
    _add("mom_6m", inputs.mom_6m_pct, inputs.mom_6m_history_pct, SPEC_WEIGHTS["mom_6m"])
    _add(
        "mom_12m",
        inputs.mom_12m_pct,
        inputs.mom_12m_history_pct,
        SPEC_WEIGHTS["mom_12m"],
    )
    _add(
        "breadth",
        inputs.breadth_above_ma200_pct,
        inputs.breadth_history_pct,
        SPEC_WEIGHTS["breadth"],
    )
    _add(
        "cross_asset",
        inputs.cross_asset_signal,
        inputs.cross_asset_history,
        SPEC_WEIGHTS["cross_asset"],
    )

    # Spec §4 precondition: ≥ 252 obs (1Y) for 12M return — checked at input
    # layer. Here we just guard against zero-weight aggregate.
    if total_weight <= 0.0:
        raise InsufficientInputsError("F2: no momentum components available")

    z_aggregate = z_weighted_sum / total_weight
    if math.isnan(z_aggregate):
        z_aggregate = 0.0
    score_normalized = _score_to_0_100(z_aggregate)
    state = classify_momentum_state(score_normalized)

    # Breadth-divergence detection per spec §4 step 8.
    breadth_z_raw = components["breadth"]
    breadth_z = None
    if isinstance(breadth_z_raw, dict):
        breadth_z = breadth_z_raw.get("z")
    if score_normalized > 70.0 and isinstance(breadth_z, int | float) and breadth_z < -0.5:
        flags.append("BREADTH_DIVERGENCE")

    if history_lens and min(history_lens) < MIN_HISTORY_QUARTERS:
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

    # Derive cross_asset sub-score [0, 100] for persistence convenience.
    cross_asset_raw = components.get("cross_asset")
    cross_asset_score: float | None = None
    if isinstance(cross_asset_raw, dict):
        cz = cross_asset_raw.get("z")
        if isinstance(cz, int | float):
            cross_asset_score = _score_to_0_100(float(cz))

    components["score_aggregate_z"] = {"value": z_aggregate}
    components["momentum_state"] = {"value": state}

    return F2Result(
        country_code=inputs.country_code,
        date=inputs.observation_date,
        methodology_version=METHODOLOGY_VERSION,
        score_normalized=score_normalized,
        score_raw=z_aggregate,
        components_json=json.dumps(components, default=str),
        mom_3m_pct=inputs.mom_3m_pct,
        mom_6m_pct=inputs.mom_6m_pct,
        mom_12m_pct=inputs.mom_12m_pct,
        breadth_above_ma200_pct=inputs.breadth_above_ma200_pct,
        cross_asset_score=cross_asset_score,
        primary_index=inputs.primary_index,
        lookback_years=lookback_years,
        momentum_state=state,
        confidence=confidence,
        flags=tuple(sorted(set(flags))),
    )


# Silence unused numpy import guard — retained for potential future vectorized
# cross-asset history construction.
_ = np
