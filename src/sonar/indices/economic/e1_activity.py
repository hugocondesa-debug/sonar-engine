"""E1 Activity — coincident economic activity index.

Spec: docs/specs/indices/economic/E1-activity.md (v0.1)

6-component weighted z-score composite (GDP YoY, Employment YoY,
Industrial Production YoY, PMI Composite, Personal Income ex
Transfers YoY, Retail Sales Real YoY). Requires >= 4/6 components
available; raises :class:`InsufficientDataError` below threshold per
spec §6. Output ``score_normalized`` in ``[0, 100]``.

Weights (spec §4, sum = 1.00)::

    gdp_yoy                        0.25
    employment_yoy                 0.20
    industrial_production_yoy      0.15
    pmi_composite                  0.15
    personal_income_ex_transfers   0.15
    retail_sales_real_yoy          0.10

This module is the compute layer only — connectors pre-fetch history
for z-score windows upstream.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sonar.indices._helpers.z_score_rolling import rolling_zscore
from sonar.overlays.exceptions import InsufficientDataError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date

METHODOLOGY_VERSION: str = "E1_ACTIVITY_v0.1"
DEFAULT_LOOKBACK_YEARS: int = 10
TIER4_LOOKBACK_YEARS: int = 7
MIN_COMPONENTS_FOR_COMPUTE: int = 4
TOTAL_COMPONENTS: int = 6

COMPONENT_WEIGHTS: dict[str, float] = {
    "gdp_yoy": 0.25,
    "employment_yoy": 0.20,
    "industrial_production_yoy": 0.15,
    "pmi_composite": 0.15,
    "personal_income_ex_transfers_yoy": 0.15,
    "retail_sales_real_yoy": 0.10,
}


@dataclass(frozen=True, slots=True)
class E1ActivityInputs:
    """Inputs bundle for a single (country, date) E1 compute.

    Each per-component field pairs a current observation with its
    rolling history (most-recent-last). ``None`` for a component
    means the connector could not source it; compute will skip that
    slot and re-weight remaining components.
    """

    country_code: str
    observation_date: date
    gdp_yoy: float | None
    gdp_yoy_history: Sequence[float] = field(default_factory=tuple)
    employment_yoy: float | None = None
    employment_yoy_history: Sequence[float] = field(default_factory=tuple)
    industrial_production_yoy: float | None = None
    industrial_production_yoy_history: Sequence[float] = field(default_factory=tuple)
    pmi_composite: float | None = None
    pmi_composite_history: Sequence[float] = field(default_factory=tuple)
    personal_income_ex_transfers_yoy: float | None = None
    personal_income_ex_transfers_yoy_history: Sequence[float] = field(default_factory=tuple)
    retail_sales_real_yoy: float | None = None
    retail_sales_real_yoy_history: Sequence[float] = field(default_factory=tuple)
    lookback_years: int = DEFAULT_LOOKBACK_YEARS
    source_connectors: tuple[str, ...] = ()
    upstream_flags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class E1ActivityResult:
    """Canonical E1 output contract — mirrors ``idx_economic_e1_activity`` schema."""

    country_code: str
    date: date
    methodology_version: str
    score_normalized: float
    score_raw: float
    components_json: str
    components_available: int
    lookback_years: int
    confidence: float
    flags: tuple[str, ...]
    source_connectors: str


def _pack_components(inputs: E1ActivityInputs) -> list[tuple[str, float | None, Sequence[float]]]:
    """Return (name, current, history) triples in weight-ordered form."""
    return [
        ("gdp_yoy", inputs.gdp_yoy, inputs.gdp_yoy_history),
        ("employment_yoy", inputs.employment_yoy, inputs.employment_yoy_history),
        (
            "industrial_production_yoy",
            inputs.industrial_production_yoy,
            inputs.industrial_production_yoy_history,
        ),
        ("pmi_composite", inputs.pmi_composite, inputs.pmi_composite_history),
        (
            "personal_income_ex_transfers_yoy",
            inputs.personal_income_ex_transfers_yoy,
            inputs.personal_income_ex_transfers_yoy_history,
        ),
        (
            "retail_sales_real_yoy",
            inputs.retail_sales_real_yoy,
            inputs.retail_sales_real_yoy_history,
        ),
    ]


def compute_e1_activity(inputs: E1ActivityInputs) -> E1ActivityResult:
    """Compute the E1 Activity index per spec §4.

    Pipeline:
        1. Assemble (available, missing) component sets.
        2. Raise :class:`InsufficientDataError` below
           :data:`MIN_COMPONENTS_FOR_COMPUTE`.
        3. Per-component z-score via rolling_zscore on history.
        4. Re-normalize weights over the available set.
        5. ``score_raw = sum(w'_i * z_i)``, clip, map to ``[0, 100]``.
        6. Emit flags (partial components, insufficient history).
        7. Compute confidence: base 1.0, minus 0.10 per missing
           component, minus 0.10 per INSUFFICIENT_HISTORY flag.

    History hard minimum per component: ``lookback_years * 12 * 0.8``
    observations (per spec §2 preconditions).
    """
    triples = _pack_components(inputs)
    hist_floor = int(inputs.lookback_years * 12 * 0.8)

    flags: list[str] = list(inputs.upstream_flags)
    insufficient_history_components: list[str] = []
    components_json: dict[str, dict[str, float]] = {}

    available: list[tuple[str, float, float]] = []  # (name, z_clamped, weight_nominal)
    for name, current, history in triples:
        if current is None:
            continue
        z_clamped, _mu, _sigma, n_obs = rolling_zscore(history, current=current)
        weight = COMPONENT_WEIGHTS[name]
        components_json[name] = {
            "raw": float(current),
            "z": z_clamped,
            "weight": weight,
            "contribution": 0.0,  # filled after re-normalization
        }
        if n_obs < hist_floor:
            insufficient_history_components.append(name)
        available.append((name, z_clamped, weight))

    if len(available) < MIN_COMPONENTS_FOR_COMPUTE:
        msg = (
            f"E1 requires >= {MIN_COMPONENTS_FOR_COMPUTE} components; "
            f"got {len(available)} for {inputs.country_code} {inputs.observation_date}"
        )
        raise InsufficientDataError(msg)

    weight_sum = sum(w for _, _, w in available)
    score_raw = 0.0
    for name, z, w in available:
        w_effective = w / weight_sum
        contribution = w_effective * z
        score_raw += contribution
        components_json[name]["contribution"] = contribution

    score_normalized = max(0.0, min(100.0, 50.0 + 16.67 * score_raw))

    missing_count = TOTAL_COMPONENTS - len(available)
    if missing_count > 0:
        flags.append("E1_PARTIAL_COMPONENTS")
    if insufficient_history_components:
        flags.append("INSUFFICIENT_HISTORY")
    flags = sorted(set(flags))

    confidence = 1.0 - 0.10 * missing_count - 0.10 * len(insufficient_history_components)
    confidence = max(0.0, min(1.0, confidence))

    return E1ActivityResult(
        country_code=inputs.country_code,
        date=inputs.observation_date,
        methodology_version=METHODOLOGY_VERSION,
        score_normalized=score_normalized,
        score_raw=score_raw,
        components_json=json.dumps(components_json, sort_keys=True),
        components_available=len(available),
        lookback_years=inputs.lookback_years,
        confidence=confidence,
        flags=tuple(flags),
        source_connectors=",".join(sorted(inputs.source_connectors))
        if inputs.source_connectors
        else "",
    )
