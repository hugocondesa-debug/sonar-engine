"""Shared scaffolding for L4 cycle composite computations.

Implements the ``Policy 1`` fail-mode aggregation contract defined in
``docs/specs/conventions/composite-aggregation.md``:

- When a sub-index is unavailable, re-weight the remaining sub-indices
  proportionally (``w'_i = w_i / sum(w_j available)``).
- Emit a ``{NAME}_MISSING`` flag per absent slot.
- Cap confidence at :data:`REWEIGHT_CONFIDENCE_CAP` (0.75) whenever
  any re-weighting was required.
- When fewer than ``min_required`` sub-indices remain available,
  raise :class:`InsufficientCycleInputsError`.

The concrete CCCS / FCS modules supply sub-index keys + weights +
``min_required`` and do not duplicate this logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date

REWEIGHT_CONFIDENCE_CAP: float = 0.75


class InsufficientCycleInputsError(Exception):
    """Raised when available sub-indices fall below the spec's minimum.

    Halts composite computation — caller is expected to log + skip
    persistence rather than emit a degraded row.
    """


@dataclass(frozen=True, slots=True)
class CycleResult:
    """Canonical cycle-composite output contract.

    Per-cycle specs extend with additional columns (boom_overlay,
    hysteresis tracking, etc.) via subclassing or by enriching the
    composite persistence helper; this dataclass carries only the
    shared fields.
    """

    country_code: str
    date: date
    cycle_type: str
    methodology_version: str
    score_composite: float
    confidence: float
    sub_index_contributions: dict[str, dict[str, float]] = field(default_factory=dict)
    regime_phase: str = ""
    flags: tuple[str, ...] = ()
    source_cycle: str = ""


class CycleCompositeBase:
    """ABC for L4 cycle composite computations.

    Subclasses implement ``compute(country, date, session)`` and may
    call :func:`apply_policy_1` for the re-weighting step. This
    base class exists for shared type hints + future refactors; it
    intentionally stays minimal so composites can also be expressed
    as plain functions (the pattern the sprint uses).
    """

    cycle_type: str = "BASE"
    methodology_version: str = "BASE_v0.1"
    min_required: int = 1
    canonical_weights: dict[str, float] = {}  # noqa: RUF012 — intentional class attr default

    def compute(self, country_code: str, observation_date: date) -> CycleResult:
        """Override in subclass."""
        msg = f"{type(self).__name__}.compute() not implemented"
        raise NotImplementedError(msg)


def apply_policy_1(
    sub_values: dict[str, float | None],
    canonical_weights: dict[str, float],
    min_required: int,
) -> tuple[float, dict[str, float], list[str], bool]:
    """Apply the Policy 1 fail-mode re-weighting.

    Parameters
    ----------
    sub_values
        ``{name: score | None}`` per sub-index. ``None`` signals a
        missing / unavailable slot.
    canonical_weights
        ``{name: weight}`` canonical (nominal) weights per spec; must
        cover exactly the keys in ``sub_values``. Sum does not need
        to equal 1.00 (spec §4 may intentionally omit components,
        e.g. CCCS QS).
    min_required
        Minimum number of available sub-indices. When strictly fewer
        than this remain, raise :class:`InsufficientCycleInputsError`.

    Returns
    -------
    tuple
        ``(weighted_score, effective_weights, flags, reweighted)``:

        * ``weighted_score`` — canonical weighted sum of available
          sub-index scores (already re-normalised).
        * ``effective_weights`` — ``{name: w'}`` per available
          sub-index (sums to 1.0 only across available keys).
        * ``flags`` — ``[{NAME}_MISSING, ...]`` for each absent slot,
          sorted lexicographically.
        * ``reweighted`` — ``True`` when any slot was absent (caller
          applies :data:`REWEIGHT_CONFIDENCE_CAP` on that signal).

    Raises
    ------
    InsufficientCycleInputsError
        When available < ``min_required``.
    KeyError
        When ``sub_values`` and ``canonical_weights`` key sets differ.
    """
    if set(sub_values.keys()) != set(canonical_weights.keys()):
        msg = (
            f"sub_values keys {set(sub_values.keys())!r} disagree with "
            f"canonical_weights keys {set(canonical_weights.keys())!r}"
        )
        raise KeyError(msg)

    available = [(name, val) for name, val in sub_values.items() if val is not None]
    missing = [name for name, val in sub_values.items() if val is None]

    if len(available) < min_required:
        msg = (
            f"Composite requires >= {min_required} sub-indices; "
            f"got {len(available)} (missing: {sorted(missing)})"
        )
        raise InsufficientCycleInputsError(msg)

    available_weight_sum = sum(canonical_weights[name] for name, _ in available)
    effective_weights = {
        name: canonical_weights[name] / available_weight_sum for name, _ in available
    }
    weighted_score = sum(effective_weights[name] * val for name, val in available)
    flags = sorted(f"{name.upper()}_MISSING" for name in missing)
    return weighted_score, effective_weights, flags, bool(missing)
