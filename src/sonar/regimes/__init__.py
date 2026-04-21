"""L5 regime classifier package.

L5 sits on top of the four L4 cycle composites and consolidates them
into a single cross-cycle meta-regime per ``(country, date)``. See
``docs/specs/regimes/`` for the canonical spec.
"""

from sonar.regimes.base import RegimeClassifier
from sonar.regimes.exceptions import (
    InsufficientL4DataError,
    InvalidMetaRegimeError,
    L5RegimeError,
)
from sonar.regimes.meta_regime_classifier import MetaRegimeClassifier
from sonar.regimes.types import (
    L5RegimeInputs,
    L5RegimeResult,
    MetaRegime,
)

__all__ = [
    "InsufficientL4DataError",
    "InvalidMetaRegimeError",
    "L5RegimeError",
    "L5RegimeInputs",
    "L5RegimeResult",
    "MetaRegime",
    "MetaRegimeClassifier",
    "RegimeClassifier",
]
