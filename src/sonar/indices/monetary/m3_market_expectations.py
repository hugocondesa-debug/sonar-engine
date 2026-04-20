"""M3 Market Expectations — Week 4 simplified variant (anchor-focused).

Full spec: ``docs/specs/indices/monetary/M3-market-expectations.md``
(v0.1) defines a 4-component EP composite (forward 1y1y vs policy,
forward 2y1y vs policy, 5y5y anchor, policy surprise). This module
implements the **anchor subset** covering the inflation-credibility
signal that is computable from the NSS forwards + expected-inflation
overlays already in production; policy-surprise component is deferred
pending connector integration.

Methodology version: ``M3_MARKET_EXPECTATIONS_ANCHOR_v0.1`` — distinct
from ``M3_MARKET_EXPECTATIONS_v0.1`` so consumers can distinguish the
simplified path from the full composite.

Canonical output per SESSION_CONTEXT (Distincao critica):
``value_0_100 = clip(50 + 16.67 * z_clamped, 0, 100)`` where HIGHER
means better-anchored / more credible policy regime, LOWER means
unanchored / regime-shift risk.

Sub-indicators (weights per brief):
  - ``nominal_5y5y_level_z`` (40%): z-score of nominal 5y5y forward
    over 5Y rolling, sign-inverted so elevated nominal rates pull the
    score down (embedded inflation concerns).
  - ``anchor_deviation_z`` (40%): z-score of ``|5y5y_breakeven -
    bc_target|`` over 5Y rolling, sign-inverted so larger deviations
    pull the score down.
  - ``bei_vs_survey_div_z`` (20%): z-score of
    ``|BEI_10Y - SURVEY_10Y|`` over 5Y rolling, sign-inverted so method
    divergence pulls the score down.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from sonar.indices.base import IndexBase, IndexResult, z_clamp
from sonar.indices.exceptions import InsufficientInputsError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date as date_t

__all__ = [
    "INDEX_CODE",
    "METHODOLOGY_VERSION",
    "MIN_EXPINF_CONFIDENCE",
    "MIN_HISTORY_BUSINESS_DAYS",
    "M3Inputs",
    "M3MarketExpectationsAnchor",
    "compute_m3_market_expectations_anchor",
]

INDEX_CODE: str = "M3_MARKET_EXPECTATIONS"
METHODOLOGY_VERSION: str = "M3_MARKET_EXPECTATIONS_ANCHOR_v0.1"

MIN_HISTORY_BUSINESS_DAYS: int = 1260  # 5Y rolling window
MIN_EXPINF_CONFIDENCE: float = 0.50

SUB_WEIGHT_NOMINAL_5Y5Y: float = 0.40
SUB_WEIGHT_ANCHOR_DEVIATION: float = 0.40
SUB_WEIGHT_BEI_SURVEY_DIVERGENCE: float = 0.20


@dataclass(frozen=True, slots=True)
class M3Inputs:
    """Bundle of per-date inputs + historical series for z-score baseline."""

    country_code: str
    observation_date: date_t
    nominal_5y5y_bps: float
    breakeven_5y5y_bps: float
    bc_target_bps: float | None
    bei_10y_bps: float | None
    survey_10y_bps: float | None
    nominal_5y5y_history_bps: Sequence[float]
    anchor_deviation_abs_history_bps: Sequence[float]
    bei_survey_div_abs_history_bps: Sequence[float] | None
    expinf_confidence: float
    expinf_flags: tuple[str, ...] = ()


def _rolling_zscore(series: Sequence[float], current: float) -> float:
    arr = np.asarray(series, dtype=float)
    mu = float(arr.mean())
    sigma = float(arr.std(ddof=1))
    if sigma <= 1e-12:
        return 0.0
    return (current - mu) / sigma


def _confidence_from_flags(expinf_confidence: float, flags: tuple[str, ...]) -> float:
    conf = expinf_confidence
    if "INSUFFICIENT_HISTORY" in flags:
        conf = min(conf, 0.65)
    if "INFLATION_METHOD_DIVERGENCE" in flags:
        conf = min(conf, 0.80)
    if "ANCHOR_UNCOMPUTABLE" in flags:
        conf = min(conf, 0.60)
    if "NO_TARGET" in flags:
        conf = min(conf, 0.55)
    if "OVERLAY_MISS" in flags:
        conf = min(conf, 0.60)
    return max(0.0, min(1.0, conf))


def compute_m3_market_expectations_anchor(inputs: M3Inputs) -> IndexResult:
    """Compute the M3 anchor-subset index for a given ``(country, date)``.

    Raises ``InsufficientInputsError`` when the upstream
    expected-inflation row has confidence below
    ``MIN_EXPINF_CONFIDENCE``, or when the primary history series are
    shorter than 2 observations (z-score undefined).
    """
    if inputs.expinf_confidence < MIN_EXPINF_CONFIDENCE:
        err = (
            f"expected-inflation confidence {inputs.expinf_confidence:.3f} below "
            f"minimum {MIN_EXPINF_CONFIDENCE} for M3 computation"
        )
        raise InsufficientInputsError(err)
    if len(inputs.nominal_5y5y_history_bps) < 2 or len(inputs.anchor_deviation_abs_history_bps) < 2:
        raise InsufficientInputsError("history series too short for z-score baseline")

    flags: list[str] = list(inputs.expinf_flags)
    weights = {
        "nominal_5y5y": SUB_WEIGHT_NOMINAL_5Y5Y,
        "anchor_deviation": SUB_WEIGHT_ANCHOR_DEVIATION,
        "bei_survey_divergence": SUB_WEIGHT_BEI_SURVEY_DIVERGENCE,
    }

    nominal_z = _rolling_zscore(inputs.nominal_5y5y_history_bps, inputs.nominal_5y5y_bps)
    nominal_contrib = -nominal_z  # higher nominal rates -> lower anchoring score

    if inputs.bc_target_bps is None:
        anchor_dev_z = 0.0
        anchor_dev_abs = None
        flags.append("NO_TARGET")
        # Reweight: drop anchor component, redistribute to nominal + divergence.
        weights = {
            "nominal_5y5y": 0.60,
            "anchor_deviation": 0.0,
            "bei_survey_divergence": 0.40,
        }
    else:
        anchor_dev_abs = abs(inputs.breakeven_5y5y_bps - inputs.bc_target_bps)
        anchor_dev_z = _rolling_zscore(inputs.anchor_deviation_abs_history_bps, anchor_dev_abs)
    anchor_dev_contrib = -anchor_dev_z  # larger deviation -> lower anchoring score

    have_bei_survey = (
        inputs.bei_10y_bps is not None
        and inputs.survey_10y_bps is not None
        and inputs.bei_survey_div_abs_history_bps is not None
        and len(inputs.bei_survey_div_abs_history_bps) >= 2
    )
    if have_bei_survey:
        assert inputs.bei_10y_bps is not None
        assert inputs.survey_10y_bps is not None
        assert inputs.bei_survey_div_abs_history_bps is not None
        bei_survey_div_abs = abs(inputs.bei_10y_bps - inputs.survey_10y_bps)
        bei_survey_div_z = _rolling_zscore(
            inputs.bei_survey_div_abs_history_bps, bei_survey_div_abs
        )
    else:
        bei_survey_div_abs = None
        bei_survey_div_z = 0.0
        # Reweight: drop divergence component.
        total_remaining = weights["nominal_5y5y"] + weights["anchor_deviation"]
        if total_remaining > 0:
            weights = {
                "nominal_5y5y": weights["nominal_5y5y"] / total_remaining,
                "anchor_deviation": weights["anchor_deviation"] / total_remaining,
                "bei_survey_divergence": 0.0,
            }
    bei_survey_contrib = -bei_survey_div_z

    if len(inputs.nominal_5y5y_history_bps) < MIN_HISTORY_BUSINESS_DAYS:
        flags.append("INSUFFICIENT_HISTORY")

    raw_z = (
        weights["nominal_5y5y"] * nominal_contrib
        + weights["anchor_deviation"] * anchor_dev_contrib
        + weights["bei_survey_divergence"] * bei_survey_contrib
    )
    zc = z_clamp(raw_z)
    value = IndexBase.normalize_zscore_to_0_100(raw_z)
    confidence = _confidence_from_flags(inputs.expinf_confidence, tuple(flags))

    sub_indicators = {
        "nominal_5y5y_bps": inputs.nominal_5y5y_bps,
        "nominal_5y5y_z": nominal_z,
        "breakeven_5y5y_bps": inputs.breakeven_5y5y_bps,
        "bc_target_bps": inputs.bc_target_bps,
        "anchor_deviation_abs_bps": anchor_dev_abs,
        "anchor_deviation_z": anchor_dev_z,
        "bei_10y_bps": inputs.bei_10y_bps,
        "survey_10y_bps": inputs.survey_10y_bps,
        "bei_survey_div_abs_bps": bei_survey_div_abs,
        "bei_survey_div_z": bei_survey_div_z,
        "weights": weights,
        "history_len": len(inputs.nominal_5y5y_history_bps),
    }

    raw_signal_value = (
        float(anchor_dev_abs) if anchor_dev_abs is not None else inputs.nominal_5y5y_bps
    )

    return IndexResult(
        index_code=INDEX_CODE,
        country_code=inputs.country_code,
        date=inputs.observation_date,
        methodology_version=METHODOLOGY_VERSION,
        raw_value=raw_signal_value,
        zscore_clamped=zc,
        value_0_100=value,
        sub_indicators=sub_indicators,
        confidence=confidence,
        flags=tuple(sorted(set(flags))),
        source_overlays={
            "expinf": inputs.country_code,
            "expinf_confidence": inputs.expinf_confidence,
        },
    )


class M3MarketExpectationsAnchor(IndexBase):
    """ABC-compliant façade for the pure function."""

    index_code: str = INDEX_CODE
    methodology_version: str = METHODOLOGY_VERSION

    def compute(  # type: ignore[override]
        self,
        country_code: str,
        observation_date: date_t,
        *,
        inputs: M3Inputs,
    ) -> IndexResult:
        if inputs.country_code != country_code or inputs.observation_date != observation_date:
            err = "M3Inputs (country, date) must match compute arguments"
            raise ValueError(err)
        return compute_m3_market_expectations_anchor(inputs)
