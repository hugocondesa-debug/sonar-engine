"""Economic-cycle L3 indices (E1-E4)."""

from sonar.indices.economic.e1_activity import (
    METHODOLOGY_VERSION as E1_METHODOLOGY_VERSION,
    E1ActivityInputs,
    E1ActivityResult,
    compute_e1_activity,
)
from sonar.indices.economic.e3_labor import (
    METHODOLOGY_VERSION as E3_METHODOLOGY_VERSION,
    E3LaborInputs,
    E3LaborResult,
    compute_e3_labor,
)
from sonar.indices.economic.e4_sentiment import (
    METHODOLOGY_VERSION as E4_METHODOLOGY_VERSION,
    E4SentimentInputs,
    E4SentimentResult,
    compute_e4_sentiment,
)

__all__ = [
    "E1_METHODOLOGY_VERSION",
    "E3_METHODOLOGY_VERSION",
    "E4_METHODOLOGY_VERSION",
    "E1ActivityInputs",
    "E1ActivityResult",
    "E3LaborInputs",
    "E3LaborResult",
    "E4SentimentInputs",
    "E4SentimentResult",
    "compute_e1_activity",
    "compute_e3_labor",
    "compute_e4_sentiment",
]
