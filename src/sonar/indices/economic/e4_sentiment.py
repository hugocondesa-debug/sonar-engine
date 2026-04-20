"""E4 Sentiment & Expectations — survey + market sentiment index.

Spec: docs/specs/indices/economic/E4-sentiment.md (v0.1)

13-component composite across US surveys (UMich, Conference Board,
UMich 5Y inflation expectations, ISM Manufacturing + Services, NFIB,
SLOOS), EA surveys (EC ESI, ZEW, Ifo), JP surveys (Tankan), EPU, and
market-based VIX. Requires >= 6/13 components available; raises
:class:`InsufficientDataError` below threshold per spec §6.

Weights (spec §4, sum = 1.00)::

    umich_sentiment_12m_change             0.10
    conference_board_confidence_12m_change 0.10
    umich_5y_inflation_exp                 0.10  (inverted sign)
    ism_manufacturing                      0.10
    ism_services                           0.10
    nfib_small_business                    0.05
    epu_index                              0.05  (inverted sign)
    ec_esi                                 0.10
    zew_expectations                       0.10
    ifo_business_climate                   0.05
    vix_level                              0.05  (inverted sign)
    tankan_large_mfg                       0.05
    sloos_standards_net_pct                0.05  (inverted sign)

Country coverage is materially asymmetric by design (spec §2):
US-only surveys skip for EA/JP; EA surveys skip for US. PT/IT/ES/FR/NL
typically have < 6 components and therefore raise
:class:`InsufficientDataError` per spec intent.
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

METHODOLOGY_VERSION: str = "E4_SENTIMENT_v0.1"
DEFAULT_LOOKBACK_YEARS: int = 10
TIER4_LOOKBACK_YEARS: int = 7
MIN_COMPONENTS_FOR_COMPUTE: int = 6
TOTAL_COMPONENTS: int = 13

COMPONENT_WEIGHTS: dict[str, float] = {
    "umich_sentiment_12m_change": 0.10,
    "conference_board_confidence_12m_change": 0.10,
    "umich_5y_inflation_exp": 0.10,
    "ism_manufacturing": 0.10,
    "ism_services": 0.10,
    "nfib_small_business": 0.05,
    "epu_index": 0.05,
    "ec_esi": 0.10,
    "zew_expectations": 0.10,
    "ifo_business_climate": 0.05,
    "vix_level": 0.05,
    "tankan_large_mfg": 0.05,
    "sloos_standards_net_pct": 0.05,
}

INVERTED_SIGN_COMPONENTS: frozenset[str] = frozenset(
    {"umich_5y_inflation_exp", "epu_index", "vix_level", "sloos_standards_net_pct"}
)


@dataclass(frozen=True, slots=True)
class E4SentimentInputs:
    """Inputs bundle for a single (country, date) E4 compute."""

    country_code: str
    observation_date: date
    umich_sentiment_12m_change: float | None = None
    umich_sentiment_12m_change_history: Sequence[float] = field(default_factory=tuple)
    conference_board_confidence_12m_change: float | None = None
    conference_board_confidence_12m_change_history: Sequence[float] = field(default_factory=tuple)
    umich_5y_inflation_exp: float | None = None
    umich_5y_inflation_exp_history: Sequence[float] = field(default_factory=tuple)
    ism_manufacturing: float | None = None
    ism_manufacturing_history: Sequence[float] = field(default_factory=tuple)
    ism_services: float | None = None
    ism_services_history: Sequence[float] = field(default_factory=tuple)
    nfib_small_business: float | None = None
    nfib_small_business_history: Sequence[float] = field(default_factory=tuple)
    epu_index: float | None = None
    epu_index_history: Sequence[float] = field(default_factory=tuple)
    ec_esi: float | None = None
    ec_esi_history: Sequence[float] = field(default_factory=tuple)
    zew_expectations: float | None = None
    zew_expectations_history: Sequence[float] = field(default_factory=tuple)
    ifo_business_climate: float | None = None
    ifo_business_climate_history: Sequence[float] = field(default_factory=tuple)
    vix_level: float | None = None
    vix_level_history: Sequence[float] = field(default_factory=tuple)
    tankan_large_mfg: float | None = None
    tankan_large_mfg_history: Sequence[float] = field(default_factory=tuple)
    sloos_standards_net_pct: float | None = None
    sloos_standards_net_pct_history: Sequence[float] = field(default_factory=tuple)
    lookback_years: int = DEFAULT_LOOKBACK_YEARS
    source_connectors: tuple[str, ...] = ()
    upstream_flags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class E4SentimentResult:
    """Canonical E4 output contract — mirrors ``idx_economic_e4_sentiment`` schema."""

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


def _pack_components(
    inputs: E4SentimentInputs,
) -> list[tuple[str, float | None, Sequence[float]]]:
    return [
        (
            "umich_sentiment_12m_change",
            inputs.umich_sentiment_12m_change,
            inputs.umich_sentiment_12m_change_history,
        ),
        (
            "conference_board_confidence_12m_change",
            inputs.conference_board_confidence_12m_change,
            inputs.conference_board_confidence_12m_change_history,
        ),
        (
            "umich_5y_inflation_exp",
            inputs.umich_5y_inflation_exp,
            inputs.umich_5y_inflation_exp_history,
        ),
        ("ism_manufacturing", inputs.ism_manufacturing, inputs.ism_manufacturing_history),
        ("ism_services", inputs.ism_services, inputs.ism_services_history),
        ("nfib_small_business", inputs.nfib_small_business, inputs.nfib_small_business_history),
        ("epu_index", inputs.epu_index, inputs.epu_index_history),
        ("ec_esi", inputs.ec_esi, inputs.ec_esi_history),
        ("zew_expectations", inputs.zew_expectations, inputs.zew_expectations_history),
        (
            "ifo_business_climate",
            inputs.ifo_business_climate,
            inputs.ifo_business_climate_history,
        ),
        ("vix_level", inputs.vix_level, inputs.vix_level_history),
        ("tankan_large_mfg", inputs.tankan_large_mfg, inputs.tankan_large_mfg_history),
        (
            "sloos_standards_net_pct",
            inputs.sloos_standards_net_pct,
            inputs.sloos_standards_net_pct_history,
        ),
    ]


def compute_e4_sentiment(inputs: E4SentimentInputs) -> E4SentimentResult:
    """Compute the E4 Sentiment index per spec §4.

    Pipeline:
        1. Assemble (available, missing) component sets from the 13 slots.
        2. Invert sign on inverted-sign components (spec §4 table).
        3. Raise :class:`InsufficientDataError` below 6/13.
        4. Per-component z via rolling_zscore over lookback history.
        5. Re-normalize weights over available; score_raw =
           ``sum(w'_i * z_i)``; score_normalized =
           ``clip(50 + 16.67 * score_raw, 0, 100)``.
        6. Flags: E4_PARTIAL_COMPONENTS (per spec §6, -0.05 per
           missing — lower than E1/E3 because sentiment is noisier),
           INSUFFICIENT_HISTORY per component below floor.
    """
    triples = _pack_components(inputs)
    hist_floor = int(inputs.lookback_years * 12 * 0.8)

    flags: list[str] = list(inputs.upstream_flags)
    insufficient_history_components: list[str] = []
    components_json: dict[str, dict[str, float]] = {}
    available: list[tuple[str, float, float]] = []

    for name, current, history in triples:
        if current is None:
            continue
        z_input = -current if name in INVERTED_SIGN_COMPONENTS else current
        z_history = [-x for x in history] if name in INVERTED_SIGN_COMPONENTS else list(history)
        z_clamped, _mu, _sigma, n_obs = rolling_zscore(z_history, current=z_input)
        weight = COMPONENT_WEIGHTS[name]
        components_json[name] = {
            "raw": float(current),
            "z": z_clamped,
            "weight": weight,
            "contribution": 0.0,
        }
        if n_obs < hist_floor:
            insufficient_history_components.append(name)
        available.append((name, z_clamped, weight))

    if len(available) < MIN_COMPONENTS_FOR_COMPUTE:
        msg = (
            f"E4 requires >= {MIN_COMPONENTS_FOR_COMPUTE} components; "
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
        flags.append("E4_PARTIAL_COMPONENTS")
    if insufficient_history_components:
        flags.append("INSUFFICIENT_HISTORY")
    flags = sorted(set(flags))

    # Spec §6: E4 confidence deduction is -0.05 per missing (noisier than
    # E1/E3 which are -0.10); INSUFFICIENT_HISTORY still -0.10 per component.
    confidence = 1.0 - 0.05 * missing_count - 0.10 * len(insufficient_history_components)
    confidence = max(0.0, min(1.0, confidence))

    return E4SentimentResult(
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
