"""L3 indices layer — composite scores derived from L2 overlays.

Each module under this package implements one index (E2 leading, M3
market expectations, etc.) per the matching ``docs/specs/indices/<cycle>/``
spec. Outputs share the canonical ``IndexResult`` contract and persist
into the polymorphic ``index_values`` table (migration 008).
"""

from sonar.indices.base import (
    Z_CLAMP_BOUND,
    Z_TO_0_100_SLOPE,
    IndexBase,
    IndexResult,
    normalize_zscore_to_0_100,
    z_clamp,
)
from sonar.indices.exceptions import (
    IndexComputationError,
    IndexVersionMismatchError,
    InsufficientInputsError,
)

__all__ = [
    "Z_CLAMP_BOUND",
    "Z_TO_0_100_SLOPE",
    "IndexBase",
    "IndexComputationError",
    "IndexResult",
    "IndexVersionMismatchError",
    "InsufficientInputsError",
    "normalize_zscore_to_0_100",
    "z_clamp",
]
