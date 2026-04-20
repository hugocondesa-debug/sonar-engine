"""E2 Leading index (slope subset) — Week 4 simplified variant.

Full spec: ``docs/specs/indices/economic/E2-leading.md`` (v0.2) defines
an 8-component composite (yield curve, HY OAS, PMI new orders, PMI
change, building permits, capex orders, LEI, OECD CLI) that requires
connectors not yet in production (CAL-023 LEI, OECD CLI direct, ISM
PMI). This module implements a **slope-only subset** covering the
forward-looking yield-curve signal for US + DE using only the NSS
overlay outputs already flowing in Phase 1.

Methodology version: ``E2_LEADING_SLOPE_v0.1`` — deliberately distinct
from the full ``E2_LEADING_v0.2`` so downstream consumers can tell the
two apart; values from this module carry ``E2_PARTIAL_COMPONENTS``
inherited flag.

Canonical output per SESSION_CONTEXT (Distincao critica):
``value_0_100 = clip(50 + 16.67 * z_clamped, 0, 100)`` where higher is
more positive (expansion signal), lower is inversion / recession risk.

Sub-indicators (weights re-normalized vs full spec):
  - ``slope_10y_2y_z`` (70%): z-score of 10Y-2Y slope (bps) over 5Y.
  - ``forward_2y1y_spread_z`` (20%): z-score of ``forward_2y1y -
    spot_2y`` (bps) over 5Y — positive = market pricing hikes 2-3Y out.
  - ``recession_proxy_z`` (10%): NY-Fed-style probit proxy
    ``norm.cdf(-slope_pp)`` z-scored over 5Y, sign-inverted so that
    low recession probability maps to positive contribution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from scipy.stats import norm

from sonar.indices.base import IndexBase, IndexResult, z_clamp
from sonar.indices.exceptions import InsufficientInputsError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date as date_t

__all__ = [
    "INDEX_CODE",
    "METHODOLOGY_VERSION",
    "MIN_HISTORY_BUSINESS_DAYS",
    "MIN_NSS_CONFIDENCE",
    "E2LeadingSlope",
    "compute_e2_leading_slope",
]

INDEX_CODE: str = "E2_LEADING"
METHODOLOGY_VERSION: str = "E2_LEADING_SLOPE_v0.1"

MIN_HISTORY_BUSINESS_DAYS: int = 1260  # 5Y rolling window per brief
MIN_NSS_CONFIDENCE: float = 0.50

SUB_WEIGHT_SLOPE: float = 0.70
SUB_WEIGHT_FORWARD_SPREAD: float = 0.20
SUB_WEIGHT_RECESSION_PROXY: float = 0.10


@dataclass(frozen=True, slots=True)
class E2Inputs:
    """Bundle of per-date inputs + historical series for z-score baseline.

    All bps values are integer-friendly floats; history arrays are bps
    series matching the sub-indicator definitions, most-recent-last.
    """

    country_code: str
    observation_date: date_t
    spot_2y_bps: float
    spot_10y_bps: float
    forward_2y1y_bps: float
    slope_history_bps: Sequence[float]
    forward_spread_history_bps: Sequence[float]
    nss_confidence: float
    nss_flags: tuple[str, ...] = ()


def _rolling_zscore(series: Sequence[float], current: float) -> float:
    arr = np.asarray(series, dtype=float)
    mu = float(arr.mean())
    sigma = float(arr.std(ddof=1))
    if sigma <= 1e-12:
        return 0.0
    return (current - mu) / sigma


def _recession_proxy_pp(slope_bps: float) -> float:
    """NY-Fed-style recession proxy from the 10Y-2Y slope.

    Wraps ``norm.cdf(-slope_pp)`` so the output sits in ``(0, 1)``:
    deeply inverted curves produce probabilities near 1; steep curves
    produce probabilities near 0. The resulting scalar is z-scored
    against a rolling 5Y history built by the caller, then
    sign-inverted in the E2 aggregation (low-prob = positive signal).
    """
    slope_pp = slope_bps / 100.0
    return float(norm.cdf(-slope_pp))


def _confidence_from_flags(nss_confidence: float, flags: tuple[str, ...]) -> float:
    """Apply flags.md deduction + cap rules to a starting confidence.

    Rules used by E2 per brief:
      - ``INSUFFICIENT_HISTORY``: cap 0.65 (from flags.md Generic).
      - ``NSS_UPSTREAM_DEGRADED`` (nss_conf < 0.75): cap 0.65.
      - ``SLOPE_INVERTED``: informational, no impact.
      - Inherited NSS flags propagate without additional deduction
        beyond the upstream confidence already reflecting them.
    """
    conf = nss_confidence
    if "INSUFFICIENT_HISTORY" in flags:
        conf = min(conf, 0.65)
    if "NSS_UPSTREAM_DEGRADED" in flags:
        conf = min(conf, 0.65)
    if "OVERLAY_MISS" in flags:
        conf = min(conf, 0.60)
    return max(0.0, min(1.0, conf))


def compute_e2_leading_slope(inputs: E2Inputs) -> IndexResult:
    """Compute the E2 slope-subset index for a given ``(country, date)``.

    Raises ``InsufficientInputsError`` when NSS confidence is below
    ``MIN_NSS_CONFIDENCE`` (row unusable) or when history arrays are
    shorter than 2 observations (z-score undefined).
    """
    if inputs.nss_confidence < MIN_NSS_CONFIDENCE:
        err = (
            f"NSS confidence {inputs.nss_confidence:.3f} below minimum "
            f"{MIN_NSS_CONFIDENCE} for E2 computation"
        )
        raise InsufficientInputsError(err)
    if len(inputs.slope_history_bps) < 2 or len(inputs.forward_spread_history_bps) < 2:
        raise InsufficientInputsError("history series too short for z-score baseline")

    flags: list[str] = list(inputs.nss_flags)

    slope_bps = inputs.spot_10y_bps - inputs.spot_2y_bps
    forward_spread_bps = inputs.forward_2y1y_bps - inputs.spot_2y_bps

    slope_z = _rolling_zscore(inputs.slope_history_bps, slope_bps)
    forward_spread_z = _rolling_zscore(inputs.forward_spread_history_bps, forward_spread_bps)

    recession_prob = _recession_proxy_pp(slope_bps)
    recession_history = [_recession_proxy_pp(s) for s in inputs.slope_history_bps]
    recession_z_raw = _rolling_zscore(recession_history, recession_prob)
    # Invert so low-prob maps to positive E2 contribution.
    recession_z = -recession_z_raw

    if slope_bps < 0:
        flags.append("SLOPE_INVERTED")
    if len(inputs.slope_history_bps) < MIN_HISTORY_BUSINESS_DAYS:
        flags.append("INSUFFICIENT_HISTORY")
    if inputs.nss_confidence < 0.75:
        flags.append("NSS_UPSTREAM_DEGRADED")

    raw_z = (
        SUB_WEIGHT_SLOPE * slope_z
        + SUB_WEIGHT_FORWARD_SPREAD * forward_spread_z
        + SUB_WEIGHT_RECESSION_PROXY * recession_z
    )
    zc = z_clamp(raw_z)
    value = IndexBase.normalize_zscore_to_0_100(raw_z)
    confidence = _confidence_from_flags(inputs.nss_confidence, tuple(flags))

    sub_indicators = {
        "slope_10y_2y_bps": slope_bps,
        "slope_10y_2y_z": slope_z,
        "forward_2y1y_bps": inputs.forward_2y1y_bps,
        "forward_spread_bps": forward_spread_bps,
        "forward_spread_z": forward_spread_z,
        "recession_prob_proxy": recession_prob,
        "recession_proxy_z": recession_z,
        "weights": {
            "slope": SUB_WEIGHT_SLOPE,
            "forward_spread": SUB_WEIGHT_FORWARD_SPREAD,
            "recession_proxy": SUB_WEIGHT_RECESSION_PROXY,
        },
        "history_len": len(inputs.slope_history_bps),
    }

    return IndexResult(
        index_code=INDEX_CODE,
        country_code=inputs.country_code,
        date=inputs.observation_date,
        methodology_version=METHODOLOGY_VERSION,
        raw_value=slope_bps,
        zscore_clamped=zc,
        value_0_100=value,
        sub_indicators=sub_indicators,
        confidence=confidence,
        flags=tuple(sorted(set(flags))),
        source_overlays={"nss": inputs.country_code, "nss_confidence": inputs.nss_confidence},
    )


class E2LeadingSlope(IndexBase):
    """ABC-compliant façade for the pure function."""

    index_code: str = INDEX_CODE
    methodology_version: str = METHODOLOGY_VERSION

    def compute(  # type: ignore[override]
        self,
        country_code: str,
        observation_date: date_t,
        *,
        inputs: E2Inputs,
    ) -> IndexResult:
        if inputs.country_code != country_code or inputs.observation_date != observation_date:
            err = "E2Inputs (country, date) must match compute arguments"
            raise ValueError(err)
        return compute_e2_leading_slope(inputs)
