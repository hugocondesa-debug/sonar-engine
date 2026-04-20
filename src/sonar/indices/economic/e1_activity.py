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

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date

METHODOLOGY_VERSION: str = "E1_ACTIVITY_v0.1"
DEFAULT_LOOKBACK_YEARS: int = 10
TIER4_LOOKBACK_YEARS: int = 7
MIN_COMPONENTS_FOR_COMPUTE: int = 4

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


def compute_e1_activity(inputs: E1ActivityInputs) -> E1ActivityResult:
    """Compute the E1 Activity index per spec §4.

    Raises:
        InsufficientDataError: when < 4/6 components available.

    Implementation lands in the full compute commit (sprint §4 Commit 7).
    """
    msg = "E1 compute implementation pending sprint Commit 7"
    raise NotImplementedError(msg)
