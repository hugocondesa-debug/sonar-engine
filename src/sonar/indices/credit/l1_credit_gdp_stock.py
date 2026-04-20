"""L1 Credit-to-GDP Stock per ``L1_CREDIT_GDP_STOCK_v0.1``.

Full spec: ``docs/specs/indices/credit/L1-credit-to-gdp-stock.md``.
Primary input for L2 HP gap + L3 credit impulse.

Two input paths supported:

- **Direct ratio path**: BIS ``WS_TC`` returns credit-to-GDP as % of GDP
  directly. Callers pass ``ratio_pct`` and the module records the
  numerator/denominator LCU values as ``None``.
- **LCU path**: compute ``ratio_pct = credit / gdp_4q_sum * 100`` from
  separate local-currency stock + 4Q-sum GDP inputs (used for backtest
  vintage-alignment or when the BIS ratio is not yet published).

Historical baseline: rolling 20Y z-score over ``ratio_pct`` history
per spec §4 step 7; clamped ``[-5, +5]``. Structural bands per spec
§4 step 9 are placeholders subject to CAL-015 country-specific
recalibration.
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
    "MAX_QUARTERLY_GROWTH_JUMP_PCT",
    "METHODOLOGY_VERSION",
    "MIN_HISTORY_QUARTERS",
    "CreditGdpStockInputs",
    "CreditGdpStockResult",
    "SeriesVariant",
    "StructuralBand",
    "classify_structural_band",
    "compute_credit_gdp_stock",
]

METHODOLOGY_VERSION: str = "L1_CREDIT_GDP_STOCK_v0.1"

MIN_HISTORY_QUARTERS: int = 60  # 15Y hard floor per spec §6
MAX_QUARTERLY_GROWTH_JUMP_PCT: float = 50.0  # spec §4 step 3

SeriesVariant = Literal["Q", "F"]
GdpVintageMode = Literal["production", "backtest"]
StructuralBand = Literal[
    "sub_financialized",  # < 50%
    "intermediate",  # 50..100%
    "advanced_economy_typical",  # 100..150%
    "highly_financialized",  # 150..200%
    "outlier",  # > 200%
]


@dataclass(frozen=True, slots=True)
class CreditGdpStockInputs:
    """L1 per-quarter inputs + rolling 20Y history."""

    country_code: str
    observation_date: date_t
    ratio_pct: float  # credit-to-GDP in percent display (e.g. 145.21)
    ratio_pct_history: Sequence[float]
    credit_stock_lcu: float | None = None
    gdp_4q_sum_lcu: float | None = None
    series_variant: SeriesVariant = "Q"
    gdp_vintage_mode: GdpVintageMode = "production"
    prior_ratio_pct: float | None = None  # optional for CREDIT_BREAK detection
    upstream_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class CreditGdpStockResult:
    """Canonical L1 output contract — mirrors ``credit_to_gdp_stock`` schema."""

    country_code: str
    date: date_t
    methodology_version: str
    score_normalized: float
    score_raw: float  # == ratio_pct
    components_json: str
    series_variant: SeriesVariant
    gdp_vintage_mode: GdpVintageMode
    lookback_years: int
    structural_band: StructuralBand | None
    confidence: float
    flags: tuple[str, ...]
    source_connector: str


def classify_structural_band(ratio_pct: float) -> StructuralBand:
    """Classify country level per spec §4 step 9 placeholder thresholds.

    Bands are CAL-015 targets for recalibration after 5Y of production
    data. Current thresholds: <50 / 50-100 / 100-150 / 150-200 / >200.
    """
    if ratio_pct < 50.0:
        return "sub_financialized"
    if ratio_pct < 100.0:
        return "intermediate"
    if ratio_pct < 150.0:
        return "advanced_economy_typical"
    if ratio_pct < 200.0:
        return "highly_financialized"
    return "outlier"


def _z_clamp_5(z: float) -> float:
    if math.isnan(z):
        return 0.0
    return max(-5.0, min(5.0, z))


def _confidence_from_flags(flags: tuple[str, ...]) -> float:
    conf = 1.0
    if "CREDIT_F_FALLBACK" in flags:
        conf = min(conf, 0.75)
    if "CREDIT_BREAK" in flags:
        conf -= 0.15
    if "INSUFFICIENT_HISTORY" in flags:
        conf = min(conf, 0.65)
    if "EM_COVERAGE" in flags:
        conf = min(conf, 0.70)
    if "STALE" in flags:
        conf -= 0.20
    return max(0.0, min(1.0, conf))


def compute_credit_gdp_stock(
    inputs: CreditGdpStockInputs,
    *,
    source_connector: str = "bis_ws_tc",
) -> CreditGdpStockResult:
    """Compute L1 credit-to-GDP stock per spec §4."""
    if inputs.ratio_pct <= 0.0:
        err = f"ratio_pct must be positive, got {inputs.ratio_pct}"
        raise InsufficientInputsError(err)
    if len(inputs.ratio_pct_history) < 2:
        raise InsufficientInputsError("ratio_pct history too short for z-score baseline")

    flags: list[str] = list(inputs.upstream_flags)

    if inputs.series_variant == "F":
        flags.append("CREDIT_F_FALLBACK")

    # CREDIT_BREAK: quarterly growth jump > MAX_QUARTERLY_GROWTH_JUMP_PCT.
    if inputs.prior_ratio_pct is not None and inputs.prior_ratio_pct > 0.0:
        growth_pct = abs(inputs.ratio_pct - inputs.prior_ratio_pct) / inputs.prior_ratio_pct * 100.0
        if growth_pct > MAX_QUARTERLY_GROWTH_JUMP_PCT:
            flags.append("CREDIT_BREAK")

    hist = np.asarray(inputs.ratio_pct_history, dtype=float)
    mu = float(hist.mean())
    sigma = float(hist.std(ddof=1))
    if len(inputs.ratio_pct_history) < MIN_HISTORY_QUARTERS:
        flags.append("INSUFFICIENT_HISTORY")

    z_raw = (inputs.ratio_pct - mu) / sigma if sigma > 1e-12 else 0.0
    score_normalized = _z_clamp_5(z_raw)
    structural_band = classify_structural_band(inputs.ratio_pct)
    confidence = _confidence_from_flags(tuple(flags))

    lookback_years = max(1, len(inputs.ratio_pct_history) // 4)

    components = {
        "credit_stock_lcu": inputs.credit_stock_lcu,
        "gdp_4q_sum_lcu": inputs.gdp_4q_sum_lcu,
        "ratio_pct": inputs.ratio_pct,
        "series_variant": inputs.series_variant,
        "gdp_vintage_mode": inputs.gdp_vintage_mode,
        "rolling_mean_20y_pct": mu,
        "rolling_std_20y_pct": sigma,
        "structural_band": structural_band,
    }

    return CreditGdpStockResult(
        country_code=inputs.country_code,
        date=inputs.observation_date,
        methodology_version=METHODOLOGY_VERSION,
        score_normalized=score_normalized,
        score_raw=inputs.ratio_pct,
        components_json=json.dumps(components),
        series_variant=inputs.series_variant,
        gdp_vintage_mode=inputs.gdp_vintage_mode,
        lookback_years=lookback_years,
        structural_band=structural_band,
        confidence=confidence,
        flags=tuple(sorted(set(flags))),
        source_connector=source_connector,
    )
