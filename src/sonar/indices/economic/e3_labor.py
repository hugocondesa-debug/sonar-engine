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

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sonar.indices._helpers.z_score_rolling import rolling_zscore
from sonar.overlays.exceptions import InsufficientDataError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date

METHODOLOGY_VERSION: str = "E3_LABOR_v0.1"
DEFAULT_LOOKBACK_YEARS: int = 10
TIER4_LOOKBACK_YEARS: int = 7
MIN_COMPONENTS_FOR_COMPUTE: int = 6
TOTAL_COMPONENTS: int = 10
SAHM_TRIGGER_THRESHOLD: float = 0.005  # 0.5pp per spec §4 step 2
SAHM_TRIGGER_Z_PENALTY: float = -1.0  # Added to Sahm z when triggered, spec §4 step 5

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
    {
        "sahm_rule_value",  # high Sahm = labor deteriorating → negative z (spec §3 JSON example)
        "unemployment_rate_12m_change",
        "initial_claims_4wk_avg",
    }
)


@dataclass(frozen=True, slots=True)
class E3LaborInputs:
    """Inputs bundle for a single (country, date) E3 compute."""

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


def _compute_sahm(history: Sequence[float]) -> tuple[float | None, int]:
    """Compute Sahm Rule value + trigger per spec §4 step 2.

    ``sahm_value = 3mo-avg UR - min(3mo-avg, last 12mo)``. Needs >= 15
    monthly observations (12m lookback + 3m rolling).
    Returns ``(sahm_value, triggered_0_or_1)`` or ``(None, 0)`` if
    history too short.
    """
    if len(history) < 15:
        return None, 0
    # Rolling 3-month average, most-recent-last.
    ur = list(history)
    rolling_3ma = [(ur[i] + ur[i - 1] + ur[i - 2]) / 3.0 for i in range(2, len(ur))]
    # Current 3MA is the last element of rolling_3ma; 12m min of 3MA
    # extends over the prior 12 values (exclusive of current point).
    if len(rolling_3ma) < 13:
        return None, 0
    current_3ma = rolling_3ma[-1]
    min_window_12 = min(rolling_3ma[-13:-1])
    sahm_value = current_3ma - min_window_12
    triggered = 1 if sahm_value >= SAHM_TRIGGER_THRESHOLD else 0
    return sahm_value, triggered


def _pack_components(
    inputs: E3LaborInputs, sahm_value: float | None
) -> list[tuple[str, float | None, Sequence[float]]]:
    return [
        ("sahm_rule_value", sahm_value, _sahm_history(inputs)),
        (
            "unemployment_rate_12m_change",
            inputs.unemployment_rate_12m_change,
            inputs.unemployment_rate_history,
        ),
        (
            "employment_population_ratio_12m_z",
            inputs.employment_population_ratio_12m_z,
            inputs.employment_population_ratio_12m_z_history,
        ),
        (
            "prime_age_lfpr_12m_change",
            inputs.prime_age_lfpr_12m_change,
            inputs.prime_age_lfpr_12m_change_history,
        ),
        ("eci_yoy_growth", inputs.eci_yoy_growth, inputs.eci_yoy_growth_history),
        (
            "atlanta_fed_wage_yoy",
            inputs.atlanta_fed_wage_yoy,
            inputs.atlanta_fed_wage_yoy_history,
        ),
        (
            "openings_unemployed_ratio",
            inputs.openings_unemployed_ratio,
            inputs.openings_unemployed_ratio_history,
        ),
        ("quits_rate", inputs.quits_rate, inputs.quits_rate_history),
        (
            "initial_claims_4wk_avg",
            inputs.initial_claims_4wk_avg,
            inputs.initial_claims_4wk_avg_history,
        ),
        (
            "temp_help_employment_yoy",
            inputs.temp_help_employment_yoy,
            inputs.temp_help_employment_yoy_history,
        ),
    ]


def _sahm_history(inputs: E3LaborInputs) -> list[float]:
    """Synthesize a Sahm history from unemployment history.

    Per spec the Sahm Rule's own rolling z-score uses the historical
    series of Sahm values, i.e. for each point t the distance of
    3mo-avg UR to its trailing 12mo min. Derive on-the-fly from
    ``unemployment_rate_history`` so upstream doesn't need to
    pre-compute.
    """
    ur = list(inputs.unemployment_rate_history)
    if len(ur) < 15:
        return []
    rolling_3ma = [(ur[i] + ur[i - 1] + ur[i - 2]) / 3.0 for i in range(2, len(ur))]
    history: list[float] = []
    for i in range(12, len(rolling_3ma)):
        window_min = min(rolling_3ma[i - 12 : i])
        history.append(rolling_3ma[i] - window_min)
    return history


def compute_e3_labor(inputs: E3LaborInputs) -> E3LaborResult:  # noqa: PLR0912 — spec §4 mandatory branches
    """Compute the E3 Labor index per spec §4.

    Pipeline:
        1. Compute Sahm Rule from unemployment_rate_history.
        2. Assemble (available, missing) component sets.
        3. Invert sign on inverted-sign components before z-score.
        4. Sahm z gets an additional -1.0 when triggered (spec §4 step 5).
        5. Raise InsufficientDataError below 6/10.
        6. Re-normalize weights; compute score_raw; map to [0, 100].
        7. Emit flags (partial, insufficient history, Sahm triggered,
           US-only absences).
    """
    sahm_value, sahm_triggered = _compute_sahm(inputs.unemployment_rate_history)
    triples = _pack_components(inputs, sahm_value)
    hist_floor = int(inputs.lookback_years * 12 * 0.8)

    flags: list[str] = list(inputs.upstream_flags)
    insufficient_history_components: list[str] = []
    components_json: dict[str, dict[str, object]] = {}
    available: list[tuple[str, float, float]] = []

    for name, current, history in triples:
        if current is None:
            continue
        raw_current = current
        # Invert sign so "bad for labor" → negative z.
        z_input = -current if name in INVERTED_SIGN_COMPONENTS else current
        # Use the same sign convention on history for consistency.
        z_history = [-x for x in history] if name in INVERTED_SIGN_COMPONENTS else list(history)
        z_clamped, _mu, _sigma, n_obs = rolling_zscore(z_history, current=z_input)
        # Spec §4 step 5: when Sahm triggered, add -1.0 to its z score.
        if name == "sahm_rule_value" and sahm_triggered == 1:
            z_clamped = max(-5.0, z_clamped + SAHM_TRIGGER_Z_PENALTY)
        weight = COMPONENT_WEIGHTS[name]
        payload: dict[str, object] = {
            "raw": float(raw_current),
            "z": z_clamped,
            "weight": weight,
            "contribution": 0.0,
        }
        if name == "sahm_rule_value":
            payload["trigger"] = sahm_triggered
        components_json[name] = payload
        if n_obs < hist_floor:
            insufficient_history_components.append(name)
        available.append((name, z_clamped, weight))

    if len(available) < MIN_COMPONENTS_FOR_COMPUTE:
        msg = (
            f"E3 requires >= {MIN_COMPONENTS_FOR_COMPUTE} components; "
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

    available_names = {name for name, _, _ in available}
    us_only_probes = [
        ("openings_unemployed_ratio", "JOLTS_US_ONLY"),
        ("quits_rate", "JOLTS_US_ONLY"),
        ("initial_claims_4wk_avg", "CLAIMS_US_ONLY"),
        ("atlanta_fed_wage_yoy", "ATLANTA_FED_US_ONLY"),
        ("eci_yoy_growth", "ECI_US_ONLY"),
        ("temp_help_employment_yoy", "TEMP_HELPS_US_ONLY"),
    ]
    if inputs.country_code != "US":
        for comp_name, flag in us_only_probes:
            if comp_name not in available_names:
                flags.append(flag)

    missing_count = TOTAL_COMPONENTS - len(available)
    if missing_count > 0:
        flags.append("E3_PARTIAL_COMPONENTS")
    if insufficient_history_components:
        flags.append("INSUFFICIENT_HISTORY")
    if sahm_triggered == 1:
        flags.append("E3_SAHM_TRIGGERED")
    flags = sorted(set(flags))

    confidence = 1.0 - 0.10 * missing_count - 0.10 * len(insufficient_history_components)
    confidence = max(0.0, min(1.0, confidence))

    return E3LaborResult(
        country_code=inputs.country_code,
        date=inputs.observation_date,
        methodology_version=METHODOLOGY_VERSION,
        score_normalized=score_normalized,
        score_raw=score_raw,
        sahm_triggered=sahm_triggered,
        sahm_value=sahm_value,
        components_json=json.dumps(components_json, sort_keys=True),
        components_available=len(available),
        lookback_years=inputs.lookback_years,
        confidence=confidence,
        flags=tuple(flags),
        source_connectors=",".join(sorted(inputs.source_connectors))
        if inputs.source_connectors
        else "",
    )
