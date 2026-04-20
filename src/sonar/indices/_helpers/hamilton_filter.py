"""Hamilton (2018) regression residual — alternative to HP filter.

Spec: ``docs/specs/indices/credit/L2-credit-to-gdp-gap.md`` §4 Hamilton
path. The regression uses an ``h``-quarter-ahead forecast of the
current value based on the lagged ``h``, ``h+1``, ``h+2``, ``h+3``
observations; the residual is the "gap" — free of HP's look-ahead
concerns and endpoint instability.

Reference: Hamilton J. (2018), "Why You Should Never Use the Hodrick-
Prescott Filter", *RES* 100(5). ``h=8`` quarters is Hamilton's
canonical choice for quarterly macro series.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence

    SeriesLike = Sequence[float] | np.ndarray
else:
    SeriesLike = object

__all__ = [
    "HAMILTON_DEFAULT_HORIZON_Q",
    "HAMILTON_MIN_OBSERVATIONS",
    "hamilton_residual",
]

HAMILTON_DEFAULT_HORIZON_Q: int = 8
HAMILTON_MIN_OBSERVATIONS: int = 12  # h + 4 per spec §6


def _design_matrix(arr: np.ndarray, h: int) -> tuple[np.ndarray, np.ndarray, int]:
    """Build design matrix ``[1, y_{t-h}, y_{t-h-1}, y_{t-h-2}, y_{t-h-3}]``
    and target vector ``y_t`` over the feasible index range.

    Returns ``(X, y, start_idx)`` where ``start_idx = h + 3`` is the
    first feasible index for ``y_t`` (requires 4 lagged obs at h, h+1,
    h+2, h+3 behind).
    """
    n = len(arr)
    start = h + 3
    if n <= start:
        err = f"Hamilton requires > {start} observations, got {n}"
        raise ValueError(err)
    rows = n - start
    x_mat = np.empty((rows, 5))
    y = np.empty(rows)
    for i in range(rows):
        t = start + i
        x_mat[i, 0] = 1.0
        x_mat[i, 1] = arr[t - h]
        x_mat[i, 2] = arr[t - h - 1]
        x_mat[i, 3] = arr[t - h - 2]
        x_mat[i, 4] = arr[t - h - 3]
        y[i] = arr[t]
    return x_mat, y, start


def hamilton_residual(
    series: SeriesLike,
    h: int = HAMILTON_DEFAULT_HORIZON_Q,
) -> float:
    """Fit Hamilton regression over the full series and return epsilon_T.

    Raises ``ValueError`` when the series is shorter than ``h + 4``
    observations (spec §6 row ``HAMILTON_FAIL`` falls back to HP-only;
    caller handles that path and emits the flag).
    """
    arr = np.asarray(series, dtype=float)
    if len(arr) < HAMILTON_MIN_OBSERVATIONS:
        err = f"Hamilton requires >= {HAMILTON_MIN_OBSERVATIONS} observations, got {len(arr)}"
        raise ValueError(err)
    x_mat, y, _ = _design_matrix(arr, h)
    # Solve OLS via lstsq for numerical robustness.
    beta, _residuals, rank, _sv = np.linalg.lstsq(x_mat, y, rcond=None)
    if rank < x_mat.shape[1]:
        err = f"Hamilton design rank-deficient (rank={rank}, expected {x_mat.shape[1]})"
        raise ValueError(err)
    y_hat = x_mat @ beta
    residuals = y - y_hat
    return float(residuals[-1])
