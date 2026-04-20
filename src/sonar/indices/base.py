"""Base primitives shared by L3 index modules.

Per SESSION_CONTEXT (Distincao critica, L3 normalization), every L3
index emits a canonical ``value_0_100`` derived from a clamped z-score
via the affine map::

    value_0_100 = clip(50 + 16.67 * z_clamped, 0, 100)

with ``z_clamped = clip(z, -3, +3)``. The slope ``100 / 6`` maps a
3-sigma band to the [0, 100] range so that ``z=0`` -> 50, ``z=+3`` ->
100, ``z=-3`` -> 0.

Individual specs may invert sign convention upstream (e.g. high credit
spread = stress = LOW value); inversion happens in each module before
calling ``normalize_zscore_to_0_100``.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import date as date_t

Z_CLAMP_BOUND: float = 3.0
Z_TO_0_100_SLOPE: float = 100.0 / 6.0


def z_clamp(z: float, bound: float = Z_CLAMP_BOUND) -> float:
    """Symmetric clamp of a z-score to ``[-bound, +bound]``."""
    if math.isnan(z):
        raise ValueError("z-score is NaN")
    if z > bound:
        return bound
    if z < -bound:
        return -bound
    return z


def normalize_zscore_to_0_100(z: float, bound: float = Z_CLAMP_BOUND) -> float:
    """Map a z-score to canonical ``[0, 100]`` via the §Distinção formula.

    ``z=0 → 50``; ``z=+bound → 100``; ``z=-bound → 0``. Outside the bound
    the result clips to the corresponding endpoint.
    """
    z_c = z_clamp(z, bound=bound)
    raw = 50.0 + Z_TO_0_100_SLOPE * z_c
    if raw < 0.0:
        return 0.0
    if raw > 100.0:
        return 100.0
    return raw


@dataclass(frozen=True, slots=True)
class IndexResult:
    """Canonical output contract returned by every ``IndexBase.compute``.

    Mirrors the ``index_values`` table schema (migration 008). Persisted
    via ``sonar.db.persistence.persist_index_value``.
    """

    index_code: str
    country_code: str
    date: date_t
    methodology_version: str
    raw_value: float
    zscore_clamped: float
    value_0_100: float
    sub_indicators: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    flags: tuple[str, ...] = ()
    source_overlays: dict[str, Any] = field(default_factory=dict)


class IndexBase(ABC):
    """Abstract base for all L3 indices.

    Subclasses implement ``compute(country_code, date, *, session)`` and
    return an :class:`IndexResult`. Helpers ``z_clamp`` /
    ``normalize_zscore_to_0_100`` are exposed as static methods for use
    inside the algorithm body.
    """

    index_code: str
    methodology_version: str

    @abstractmethod
    def compute(self, country_code: str, observation_date: date_t, **kwargs: Any) -> IndexResult:
        """Compute the index for a given ``(country, date)``."""

    @staticmethod
    def z_clamp(z: float, bound: float = Z_CLAMP_BOUND) -> float:
        return z_clamp(z, bound=bound)

    @staticmethod
    def normalize_zscore_to_0_100(z: float, bound: float = Z_CLAMP_BOUND) -> float:
        return normalize_zscore_to_0_100(z, bound=bound)
