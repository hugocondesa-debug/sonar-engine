"""Rolling z-score helper shared across F1-F4 + (future refactor) credit L1-L4.

Per ``docs/specs/indices/financial/README.md`` canonical rule:
``score_normalized = clip(50 + 16.67 * z_clamped, 0, 100)`` where
``z_clamped = clip(z, -5, +5)`` and the rolling window is 20 years
(Tier 1-3) or 10 years (Tier 4 fallback).

Returns `(z, mu, sigma, n_obs)` so callers can emit
``INSUFFICIENT_HISTORY`` when `n_obs < 60` (15Y hard floor per spec §6).

Design contract:

- Input is a flat sequence of the target metric most-recent-last.
- `current` (optional) defaults to the series endpoint.
- `ddof=1` (sample stdev) matches credit-track convention.
- On ``sigma <= 1e-12`` or fewer than 2 observations, returns ``z=0.0``
  so downstream aggregation still works; flag emission is the caller's
  responsibility.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = [
    "MIN_HISTORY_HARD_FLOOR_QUARTERS",
    "Z_CLAMP_BOUND",
    "rolling_zscore",
]

Z_CLAMP_BOUND: float = 5.0
MIN_HISTORY_HARD_FLOOR_QUARTERS: int = 60  # 15Y quarterly per spec §6


def rolling_zscore(
    series: Sequence[float],
    current: float | None = None,
    *,
    ddof: int = 1,
) -> tuple[float, float, float, int]:
    """Compute rolling z-score for a metric vs its history.

    Parameters
    ----------
    series
        Full rolling-window observation series (most-recent-last). When
        ``current`` is not supplied, the last element is used as the
        evaluation point and the z-score is computed against the full
        series including that point.
    current
        Explicit evaluation value. When supplied, ``series`` is the
        baseline history and the z-score is ``(current - mu) / sigma``.
    ddof
        Degrees of freedom for the sample stdev (default 1).

    Returns
    -------
    tuple[float, float, float, int]
        ``(z_clamped, mu, sigma, n_obs)``. z is clamped to
        ``[-Z_CLAMP_BOUND, +Z_CLAMP_BOUND]``. ``n_obs`` is the length of
        the baseline used for the statistics.
    """
    arr = np.asarray(series, dtype=float)
    n = len(arr)
    if n < 2:
        return 0.0, float("nan") if n == 0 else float(arr[0]), 0.0, n

    if current is None:
        current = float(arr[-1])

    mu = float(arr.mean())
    sigma = float(arr.std(ddof=ddof))
    if sigma <= 1e-12 or math.isnan(sigma):
        return 0.0, mu, sigma if not math.isnan(sigma) else 0.0, n

    z = (current - mu) / sigma
    if math.isnan(z):
        return 0.0, mu, sigma, n
    return max(-Z_CLAMP_BOUND, min(Z_CLAMP_BOUND, z)), mu, sigma, n
