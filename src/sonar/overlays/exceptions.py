"""Exception types for L2 overlay layer.

Per spec conventions/exceptions.md and individual overlay specs.
"""

from __future__ import annotations


class OverlayError(Exception):
    """Base exception for all L2 overlay failures."""


class InsufficientDataError(OverlayError):
    """Raised when observation count or quality falls below fit minimum.

    Per nss-curves.md §6: n_obs < 6, non-finite values, or out-of-range
    yields [-5%, 30%] trigger this exception.
    """


class ConvergenceError(OverlayError):
    """Raised when optimizer fails to converge on NSS parameters.

    Per nss-curves.md §6 row 3: downstream handler falls back to linear
    interpolation, flags NSS_FAIL, caps confidence at 0.50, and persists
    degraded row.
    """
