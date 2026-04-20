"""Exception types for L3 indices layer.

Per spec ``docs/specs/conventions/exceptions.md``. Indices reuse the
``DataError`` family from the canonical tree; ``IndexError`` (Python
builtin) is intentionally avoided as a name to prevent clobbering — the
base class is ``IndexComputationError``.
"""

from __future__ import annotations


class IndexComputationError(Exception):
    """Base for all L3 index computation failures."""


class InsufficientInputsError(IndexComputationError):
    """Raised when an upstream overlay row is missing or below minimum quality.

    Per ``conventions/exceptions.md`` this is conceptually a ``DataError``;
    indices use a dedicated subclass so the orchestrator can ``except`` and
    skip gracefully without interfering with overlay-level data errors.
    """


class IndexVersionMismatchError(IndexComputationError):
    """Raised when stored ``methodology_version`` differs from runtime."""
