"""E3 Labor Market Depth — multi-dimensional labor index.

Spec: docs/specs/indices/economic/E3-labor.md (v0.1)

10-component composite combining Sahm Rule discrete trigger with
weighted z-scores across unemployment dynamics, employment-population
ratios, prime-age labor force participation, wage growth (ECI +
Atlanta Fed), JOLTS turnover, initial claims, and temp-help
employment. Requires >= 6/10 components available; unemployment is
mandatory (Sahm input). Output ``score_normalized`` in ``[0, 100]``.

Weights (spec §4, sum = 1.00)::

    sahm_rule_value                   0.20  (discrete + z hybrid)
    unemployment_rate_12m_change      0.15  (inverted sign)
    employment_population_ratio_12m_z 0.10
    prime_age_lfpr_12m_change         0.05
    eci_yoy_growth                    0.10
    atlanta_fed_wage_yoy              0.05
    openings_unemployed_ratio         0.10
    quits_rate                        0.05
    initial_claims_4wk_avg            0.10  (inverted sign)
    temp_help_employment_yoy          0.10

Non-US countries typically degrade via `connectors/eurostat`: JOLTS,
initial claims, Atlanta Fed wage, temp-help employment are US-only;
flags `JOLTS_US_ONLY`, `CLAIMS_US_ONLY`, `ATLANTA_FED_US_ONLY`,
`TEMP_HELPS_US_ONLY` emitted when those slots are absent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date

METHODOLOGY_VERSION: str = "E3_LABOR_v0.1"
DEFAULT_LOOKBACK_YEARS: int = 10
TIER4_LOOKBACK_YEARS: int = 7
MIN_COMPONENTS_FOR_COMPUTE: int = 6
SAHM_TRIGGER_THRESHOLD: float = 0.005  # 0.5pp per spec §4 step 2

COMPONENT_WEIGHTS: dict[str, float] = {
    "sahm_rule_value": 0.20,
    "unemployment_rate_12m_change": 0.15,
    "employment_population_ratio_12m_z": 0.10,
    "prime_age_lfpr_12m_change": 0.05,
    "eci_yoy_growth": 0.10,
    "atlanta_fed_wage_yoy": 0.05,
    "openings_unemployed_ratio": 0.10,
    "quits_rate": 0.05,
    "initial_claims_4wk_avg": 0.10,
    "temp_help_employment_yoy": 0.10,
}

INVERTED_SIGN_COMPONENTS: frozenset[str] = frozenset(
    {"unemployment_rate_12m_change", "initial_claims_4wk_avg"}
)


@dataclass(frozen=True, slots=True)
class E3LaborInputs:
    """Inputs bundle for a single (country, date) E3 compute.

    Unemployment rate current + history is mandatory — required for
    internal Sahm Rule computation per spec §4 step 2. All other
    fields may be ``None`` (graceful skip).
    """

    country_code: str
    observation_date: date
    unemployment_rate: float
    unemployment_rate_history: Sequence[float]
    unemployment_rate_12m_change: float | None = None
    employment_population_ratio_12m_z: float | None = None
    employment_population_ratio_12m_z_history: Sequence[float] = field(default_factory=tuple)
    prime_age_lfpr_12m_change: float | None = None
    prime_age_lfpr_12m_change_history: Sequence[float] = field(default_factory=tuple)
    eci_yoy_growth: float | None = None
    eci_yoy_growth_history: Sequence[float] = field(default_factory=tuple)
    atlanta_fed_wage_yoy: float | None = None
    atlanta_fed_wage_yoy_history: Sequence[float] = field(default_factory=tuple)
    openings_unemployed_ratio: float | None = None
    openings_unemployed_ratio_history: Sequence[float] = field(default_factory=tuple)
    quits_rate: float | None = None
    quits_rate_history: Sequence[float] = field(default_factory=tuple)
    initial_claims_4wk_avg: float | None = None
    initial_claims_4wk_avg_history: Sequence[float] = field(default_factory=tuple)
    temp_help_employment_yoy: float | None = None
    temp_help_employment_yoy_history: Sequence[float] = field(default_factory=tuple)
    lookback_years: int = DEFAULT_LOOKBACK_YEARS
    source_connectors: tuple[str, ...] = ()
    upstream_flags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class E3LaborResult:
    """Canonical E3 output contract — mirrors ``idx_economic_e3_labor`` schema."""

    country_code: str
    date: date
    methodology_version: str
    score_normalized: float
    score_raw: float
    sahm_triggered: int
    sahm_value: float | None
    components_json: str
    components_available: int
    lookback_years: int
    confidence: float
    flags: tuple[str, ...]
    source_connectors: str


def compute_e3_labor(inputs: E3LaborInputs) -> E3LaborResult:
    """Compute the E3 Labor index per spec §4.

    Raises:
        InsufficientDataError: when < 6/10 components available or
            unemployment history insufficient for Sahm Rule computation.

    Implementation lands in the full compute commit (sprint §4 Commit 8).
    """
    msg = "E3 compute implementation pending sprint Commit 8"
    raise NotImplementedError(msg)
