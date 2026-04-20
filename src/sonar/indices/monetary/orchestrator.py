"""Monetary indices orchestrator — week6 sprint 2b C6 (CAL-100).

Runs M1/M2/M4 in parallel (no inter-dependencies between these three
sub-indices) and returns a bundle with per-index skip reasons. Pattern
mirrors :class:`sonar.indices.orchestrator.FinancialIndicesResults`.

M3 (market-expectations anchor) lives in the broader ``sonar.indices.orchestrator``
module since it predates M1/M2/M4 and is wired into the legacy
``compute_all_indices`` path; this module covers the three compute
modules shipped by week6-sprint-1b.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sonar.indices.monetary.m1_effective_rates import (
    M1EffectiveRatesInputs,
    M1EffectiveRatesResult,
    compute_m1_effective_rates,
)
from sonar.indices.monetary.m2_taylor_gaps import (
    M2TaylorGapsInputs,
    M2TaylorGapsResult,
    compute_m2_taylor_gaps,
)
from sonar.indices.monetary.m4_fci import (
    M4FciInputs,
    M4FciResult,
    compute_m4_fci,
)
from sonar.overlays.exceptions import InsufficientDataError

if TYPE_CHECKING:
    from datetime import date


__all__ = [
    "MonetaryIndicesInputs",
    "MonetaryIndicesResults",
    "compute_all_monetary_indices",
]


@dataclass(frozen=True, slots=True)
class MonetaryIndicesInputs:
    """Inputs bundle for the M-cycle M1/M2/M4 track."""

    country_code: str
    observation_date: date
    m1: M1EffectiveRatesInputs | None = None
    m2: M2TaylorGapsInputs | None = None
    m4: M4FciInputs | None = None


@dataclass(frozen=True, slots=True)
class MonetaryIndicesResults:
    """Outputs bundle — one field per monetary sub-index (``None`` when skipped)."""

    country_code: str
    observation_date: date
    m1: M1EffectiveRatesResult | None = None
    m2: M2TaylorGapsResult | None = None
    m4: M4FciResult | None = None
    skips: dict[str, str] = field(default_factory=dict)

    def available(self) -> list[str]:
        return [name for name in ("m1", "m2", "m4") if getattr(self, name) is not None]


def compute_all_monetary_indices(inputs: MonetaryIndicesInputs) -> MonetaryIndicesResults:
    """Run M1/M2/M4 independently and record per-index skip reasons.

    Does not raise — missing inputs or insufficient-data failures
    downgrade into a skip entry so callers can surface the full per-
    country status at once.
    """
    skips: dict[str, str] = {}
    m1: M1EffectiveRatesResult | None = None
    m2: M2TaylorGapsResult | None = None
    m4: M4FciResult | None = None

    if inputs.m1 is not None:
        try:
            m1 = compute_m1_effective_rates(inputs.m1)
        except InsufficientDataError as e:
            skips["m1"] = str(e)
    else:
        skips["m1"] = "no inputs provided"

    if inputs.m2 is not None:
        try:
            m2 = compute_m2_taylor_gaps(inputs.m2)
        except InsufficientDataError as e:
            skips["m2"] = str(e)
    else:
        skips["m2"] = "no inputs provided"

    if inputs.m4 is not None:
        try:
            m4 = compute_m4_fci(inputs.m4)
        except InsufficientDataError as e:
            skips["m4"] = str(e)
    else:
        skips["m4"] = "no inputs provided"

    return MonetaryIndicesResults(
        country_code=inputs.country_code,
        observation_date=inputs.observation_date,
        m1=m1,
        m2=m2,
        m4=m4,
        skips=skips,
    )
