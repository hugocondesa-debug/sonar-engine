"""Abstract base for L5 regime classifiers.

The ABC is intentionally minimal — one :meth:`classify` method. Phase
1 ships the rule-based :class:`sonar.regimes.meta_regime_classifier.MetaRegimeClassifier`;
Phase 2+ may swap in an ML implementation without touching callers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sonar.regimes.types import L5RegimeInputs, L5RegimeResult


__all__ = ["RegimeClassifier"]


class RegimeClassifier(ABC):
    """Abstract base for regime classifiers.

    Subclasses publish a class-level :data:`METHODOLOGY_VERSION` string
    that feeds the persisted row's ``methodology_version`` column so the
    wire format evolves alongside the decision logic.
    """

    METHODOLOGY_VERSION: str

    @abstractmethod
    def classify(self, inputs: L5RegimeInputs) -> L5RegimeResult:
        """Classify ``inputs`` into a cross-cycle meta-regime.

        Raises
        ------
        InsufficientL4DataError
            When ``inputs.available_count() < 3`` (Policy 1 threshold).
        """
