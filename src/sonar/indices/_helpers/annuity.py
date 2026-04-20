"""Annuity-factor helper for L4 DSR (Drehmann-Juselius 2015).

Three formula modes per docs/specs/indices/credit/L4-dsr.md §4:

- ``full`` : canonical Drehmann-Juselius ``i / (1 - (1+i)**(-s))``.
- ``o2``   : 2nd-order approximation ``i + 1/s`` (correlation ~0.95 vs
              full per BIS WP 529 Table 1).
- ``o1``   : 1st-order (interest-only) ``i`` (correlation ~0.85; used
              when maturity is unknown — spec §6 row ``DSR_APPROX_O1``).

Negative-rate note: for JP/CH/EA pre-2022 the full formula remains
defined for small negative ``i`` (denominator ``1 - (1+i)**(-s)``
stays positive when ``i > -1``); caller is responsible for emitting
the ``DSR_NEG_RATE`` flag per spec §6. This module does not raise
on negative ``i`` — it computes the annuity factor correctly and the
upstream module records the condition.
"""

from __future__ import annotations

from typing import Literal

__all__ = ["AnnuityFormulaMode", "annuity_factor"]

AnnuityFormulaMode = Literal["full", "o2", "o1"]


def annuity_factor(
    i: float,
    s: float | None,
    mode: AnnuityFormulaMode,
) -> float:
    """Compute the DSR annuity factor per the selected formula mode.

    Parameters
    ----------
    i
        Annualised lending rate as a decimal (``0.0345`` for 3.45%).
    s
        Residual weighted-average maturity in years. Required for
        ``full`` and ``o2`` modes; ignored (may be ``None``) for ``o1``.
    mode
        Selected approximation mode per data availability resolver.

    Returns
    -------
    float
        Dimensionless annuity factor.

    Raises
    ------
    ValueError
        When ``mode`` requires ``s`` but ``s`` is missing or non-positive
        (``s <= 0`` or ``s > 50`` per spec §2 sanity), or when ``i``
        violates the annuity-formula stability bound ``i > -1``.
    """
    if i <= -1.0:
        err = f"lending rate {i} violates i > -1 annuity stability bound"
        raise ValueError(err)

    if mode == "o1":
        return i

    if s is None or s <= 0.0 or s > 50.0:
        err = f"maturity s={s} invalid for mode={mode!r} (require 0 < s <= 50)"
        raise ValueError(err)

    if mode == "o2":
        return i + 1.0 / s

    # mode == "full": Drehmann-Juselius closed form.
    return float(i / (1.0 - (1.0 + i) ** (-s)))
