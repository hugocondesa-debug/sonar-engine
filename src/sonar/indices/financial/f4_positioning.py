"""F4 Positioning per ``F4_POSITIONING_v0.1``.

Full spec: ``docs/specs/indices/financial/F4-positioning.md``.
Aggregates 5 positioning / flow components (AAII bull-bear spread,
put/call ratio, COT non-commercial S&P net, margin debt / GDP, IPO
activity) into ``score_normalized in [0, 100]`` with **higher = bullish
extremes (contrarian warning)**.

Spec §4 weights: AAII 0.25 + P/C 0.25 (sign-flipped) + COT 0.20 + Margin
0.20 + IPO 0.10. Minimum 2 of 5 components required.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sonar.indices._helpers.z_score_rolling import rolling_zscore
from sonar.indices.exceptions import InsufficientInputsError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date as date_t

__all__ = [
    "METHODOLOGY_VERSION",
    "MIN_COMPONENTS",
    "SPEC_WEIGHTS",
    "F4Inputs",
    "F4Result",
    "compute_f4_positioning",
]

METHODOLOGY_VERSION: str = "F4_POSITIONING_v0.1"
MIN_COMPONENTS: int = 2

SPEC_WEIGHTS: dict[str, float] = {
    "aaii": 0.25,
    "put_call": 0.25,  # sign-flipped internally
    "cot": 0.20,
    "margin": 0.20,
    "ipo": 0.10,
}


@dataclass(frozen=True, slots=True)
class F4Inputs:
    country_code: str
    observation_date: date_t
    aaii_bull_minus_bear_pct: float | None
    put_call_ratio: float | None
    cot_noncomm_net_sp500: int | None
    margin_debt_gdp_pct: float | None
    ipo_activity_score: float | None  # 0..100 sub-composite already
    aaii_history: Sequence[float] | None = None
    put_call_history: Sequence[float] | None = None
    cot_history: Sequence[float] | None = None
    margin_history_pct: Sequence[float] | None = None
    ipo_history: Sequence[float] | None = None
    upstream_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class F4Result:
    country_code: str
    date: date_t
    methodology_version: str
    score_normalized: float
    score_raw: float
    components_json: str
    aaii_bull_minus_bear_pct: float | None
    put_call_ratio: float | None
    cot_noncomm_net_sp500: int | None
    margin_debt_gdp_pct: float | None
    ipo_activity_score: float | None
    components_available: int
    lookback_years: int
    positioning_extreme_flag: bool
    confidence: float
    flags: tuple[str, ...]


def _score_to_0_100(z: float) -> float:
    raw = 50.0 + (100.0 / 6.0) * z
    return max(0.0, min(100.0, raw))


def _confidence_from_flags(flags: tuple[str, ...]) -> float:
    conf = 1.0
    if "AAII_PROXY" in flags:
        conf -= 0.20
    if "OVERLAY_MISS" in flags:
        conf -= 0.15
    if "STALE" in flags:
        conf -= 0.20
    if "INSUFFICIENT_HISTORY" in flags:
        conf = min(conf, 0.65)
    if "EM_COVERAGE" in flags:
        conf = min(conf, 0.70)
    return max(0.0, min(1.0, conf))


def compute_f4_positioning(  # noqa: PLR0915
    inputs: F4Inputs,
    *,
    aaii_is_us_proxy: bool = False,
) -> F4Result:
    """Compute F4 positioning per spec §4."""
    flags: list[str] = list(inputs.upstream_flags)
    if aaii_is_us_proxy:
        flags.append("AAII_PROXY")

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
        *,
        sign_flip: bool = False,
    ) -> None:
        nonlocal z_weighted_sum, total_weight, components_available
        if current is None or history is None or len(history) < 2:
            components[name] = {"z": None, "value": current, "weight_effective": 0.0}
            return
        z, mu, sigma, n = rolling_zscore(history, current=float(current))
        if sign_flip:
            z = -z
        z_weighted_sum += weight * z
        total_weight += weight
        components_available += 1
        history_lens.append(n)
        components[name] = {
            "z": z,
            "value": current,
            "mu": mu,
            "sigma": sigma,
            "weight_nominal": weight,
            "n_obs": n,
        }

    _add(
        "aaii",
        inputs.aaii_bull_minus_bear_pct,
        inputs.aaii_history,
        SPEC_WEIGHTS["aaii"],
    )
    _add(
        "put_call",
        inputs.put_call_ratio,
        inputs.put_call_history,
        SPEC_WEIGHTS["put_call"],
        sign_flip=True,  # spec §4: high P/C = bearish → invert
    )
    _add(
        "cot",
        float(inputs.cot_noncomm_net_sp500) if inputs.cot_noncomm_net_sp500 is not None else None,
        inputs.cot_history,
        SPEC_WEIGHTS["cot"],
    )
    _add(
        "margin",
        inputs.margin_debt_gdp_pct,
        inputs.margin_history_pct,
        SPEC_WEIGHTS["margin"],
    )
    _add(
        "ipo",
        inputs.ipo_activity_score,
        inputs.ipo_history,
        SPEC_WEIGHTS["ipo"],
    )

    if components_available < MIN_COMPONENTS:
        err = f"F4 requires >= {MIN_COMPONENTS} components; got {components_available}/5"
        raise InsufficientInputsError(err)

    # OVERLAY_MISS when any component beyond the minimum set is missing.
    missing_optional = 0
    for c in ("cot", "margin", "ipo"):
        info = components.get(c)
        if isinstance(info, dict) and info.get("z") is None:
            missing_optional += 1
    if missing_optional > 0:
        flags.append("OVERLAY_MISS")

    z_aggregate = z_weighted_sum / total_weight
    if math.isnan(z_aggregate):
        z_aggregate = 0.0
    score_normalized = _score_to_0_100(z_aggregate)

    positioning_extreme_flag = score_normalized > 85.0 or score_normalized < 15.0
    if positioning_extreme_flag:
        flags.append("F4_CONTRARIAN_EXTREME")

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
    components["positioning_extreme_flag"] = {"value": positioning_extreme_flag}

    return F4Result(
        country_code=inputs.country_code,
        date=inputs.observation_date,
        methodology_version=METHODOLOGY_VERSION,
        score_normalized=score_normalized,
        score_raw=z_aggregate,
        components_json=json.dumps(components, default=str),
        aaii_bull_minus_bear_pct=inputs.aaii_bull_minus_bear_pct,
        put_call_ratio=inputs.put_call_ratio,
        cot_noncomm_net_sp500=inputs.cot_noncomm_net_sp500,
        margin_debt_gdp_pct=inputs.margin_debt_gdp_pct,
        ipo_activity_score=inputs.ipo_activity_score,
        components_available=components_available,
        lookback_years=lookback_years,
        positioning_extreme_flag=positioning_extreme_flag,
        confidence=confidence,
        flags=tuple(sorted(set(flags))),
    )
