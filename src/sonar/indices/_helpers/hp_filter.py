"""One-sided recursive HP filter for L2 credit-to-GDP gap (Basel III standard).

Spec: ``docs/specs/indices/credit/L2-credit-to-gdp-gap.md`` §4 + Basel III
CCyB (Ravn-Uhlig 2002, ``lambda = 400000`` for quarterly credit cycle).

Production code MUST use the one-sided variant: at each evaluation
date ``t``, fit HP over the half-open interval ``[t_0, t]`` and record
``tau_t``. Two-sided HP introduces look-ahead bias and is forbidden
per spec §11 non-requirements; it may still be computed as a
diagnostic for the ``HP_ENDPOINT_REVISION`` flag.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from statsmodels.tsa.filters.hp_filter import hpfilter  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from collections.abc import Sequence

    SeriesLike = Sequence[float] | np.ndarray
else:
    SeriesLike = object  # type alias runtime placeholder

__all__ = [
    "HP_LAMBDA_CREDIT_CYCLE",
    "hp_filter_one_sided",
    "hp_filter_two_sided",
    "hp_one_sided_endpoint",
]

# Ravn-Uhlig adjustment: business-cycle HP lambda 1600 multiplied by
# (4**4) to rescale for credit-cycle duration ~ 4x business-cycle.
HP_LAMBDA_CREDIT_CYCLE: int = 400_000


def hp_filter_two_sided(
    series: SeriesLike,
    lamb: int = HP_LAMBDA_CREDIT_CYCLE,
) -> tuple[np.ndarray, np.ndarray]:
    """Classical (two-sided) HP filter. Diagnostic use only."""
    arr = np.asarray(series, dtype=float)
    cycle, trend = hpfilter(arr, lamb=lamb)
    return np.asarray(trend), np.asarray(cycle)


def hp_one_sided_endpoint(
    series: SeriesLike,
    lamb: int = HP_LAMBDA_CREDIT_CYCLE,
) -> tuple[float, float]:
    """One-sided HP at the series endpoint.

    Returns ``(trend_t, cycle_t)`` where ``t`` is the last observation
    — fits HP over the whole array and extracts only the terminal
    trend/cycle pair, discarding the rest. This mirrors a "real-time"
    refit as each new datapoint arrives.
    """
    arr = np.asarray(series, dtype=float)
    if len(arr) < 4:
        err = f"HP filter requires >= 4 observations, got {len(arr)}"
        raise ValueError(err)
    trend, cycle = hp_filter_two_sided(arr, lamb=lamb)
    return float(trend[-1]), float(cycle[-1])


def hp_filter_one_sided(
    series: SeriesLike,
    lamb: int = HP_LAMBDA_CREDIT_CYCLE,
    *,
    min_history: int = 40,
) -> tuple[np.ndarray, np.ndarray]:
    """Recursive one-sided HP filter across the full series.

    For every ``t`` with ``t >= min_history`` (the first 40 obs = 10Y
    of quarterly data per spec §6 hard floor), refit HP over
    ``series[:t+1]`` and record ``trend[t]``, ``cycle[t]``. Earlier
    observations produce NaN placeholders.
    """
    arr = np.asarray(series, dtype=float)
    n = len(arr)
    trend_out = np.full(n, np.nan)
    cycle_out = np.full(n, np.nan)
    for t in range(min_history - 1, n):
        window = arr[: t + 1]
        trend_t, cycle_t = hp_one_sided_endpoint(window, lamb=lamb)
        trend_out[t] = trend_t
        cycle_out[t] = cycle_t
    return trend_out, cycle_out
