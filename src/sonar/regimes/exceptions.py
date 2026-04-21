"""Exceptions raised by the L5 regime layer."""

from __future__ import annotations


class L5RegimeError(Exception):
    """Base class for all L5 regime errors."""


class InsufficientL4DataError(L5RegimeError):
    """Raised when fewer than 3 of the 4 L4 cycles are available.

    Per ``docs/specs/regimes/integration-with-l4.md`` §3, L5 classifies
    with ≥ 3/4 cycles. Below threshold we refuse to produce a row —
    the ambiguity would masquerade as a low-confidence meta-regime.
    """


class InvalidMetaRegimeError(L5RegimeError):
    """Raised when a classifier emits a string outside the canonical six."""
