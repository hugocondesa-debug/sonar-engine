"""Monetary-cycle L3 indices (M1-M4)."""

from sonar.indices.monetary.m1_effective_rates import (
    METHODOLOGY_VERSION as M1_METHODOLOGY_VERSION,
    M1EffectiveRatesInputs,
    M1EffectiveRatesResult,
    compute_m1_effective_rates,
)
from sonar.indices.monetary.m2_taylor_gaps import (
    METHODOLOGY_VERSION as M2_METHODOLOGY_VERSION,
    M2TaylorGapsInputs,
    M2TaylorGapsResult,
    compute_m2_taylor_gaps,
)
from sonar.indices.monetary.m4_fci import (
    METHODOLOGY_VERSION as M4_METHODOLOGY_VERSION,
    M4FciInputs,
    M4FciResult,
    compute_m4_fci,
)

__all__ = [
    "M1_METHODOLOGY_VERSION",
    "M2_METHODOLOGY_VERSION",
    "M4_METHODOLOGY_VERSION",
    "M1EffectiveRatesInputs",
    "M1EffectiveRatesResult",
    "M2TaylorGapsInputs",
    "M2TaylorGapsResult",
    "M4FciInputs",
    "M4FciResult",
    "compute_m1_effective_rates",
    "compute_m2_taylor_gaps",
    "compute_m4_fci",
]
