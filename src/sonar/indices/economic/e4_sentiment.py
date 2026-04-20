"""E4 Sentiment & Expectations — survey + market sentiment index.

Spec: docs/specs/indices/economic/E4-sentiment.md (v0.1)

13-component composite across US surveys (UMich, Conference Board,
UMich 5Y inflation expectations, ISM Manufacturing + Services, NFIB,
SLOOS), EA surveys (EC ESI, ZEW, Ifo), JP surveys (Tankan), EPU, and
market-based VIX. Requires >= 6/13 components available; raises
:class:`InsufficientDataError` below threshold per spec §6.

Weights (spec §4, sum = 1.00)::

    umich_sentiment_12m_change            0.10
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
:class:`InsufficientDataError` per spec intent — documented gap
rather than graceful degradation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date

METHODOLOGY_VERSION: str = "E4_SENTIMENT_v0.1"
DEFAULT_LOOKBACK_YEARS: int = 10
TIER4_LOOKBACK_YEARS: int = 7
MIN_COMPONENTS_FOR_COMPUTE: int = 6

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
    """Inputs bundle for a single (country, date) E4 compute.

    All 13 components are optional; connectors populate the subset
    applicable to the country per spec §2. Compute skips ``None``
    slots and re-weights.
    """

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


def compute_e4_sentiment(inputs: E4SentimentInputs) -> E4SentimentResult:
    """Compute the E4 Sentiment index per spec §4.

    Raises:
        InsufficientDataError: when < 6/13 components available.

    Implementation lands in the full compute commit (sprint §4 Commit 9).
    """
    msg = "E4 compute implementation pending sprint Commit 9"
    raise NotImplementedError(msg)
