"""Rating-to-spread overlay (L2).

Spec: docs/specs/overlays/rating-spread.md
Methodology versions:
  - per-agency raw: ``RATING_AGENCY_v0.1``
  - consolidated:   ``RATING_SPREAD_v0.2``
  - calibration:    ``RATING_CALIBRATION_v0.1``

Week 3 scope: pure-compute layer (lookup tables + consolidation +
calibration). Live agency-scrape connectors and the Damodaran
historical backfill are deferred — callers seed ``ratings_agency_raw``
manually for now.

Storage convention per units.md §Spreads: ``default_spread_bps`` is
``int``, ``notch_*`` is ``REAL`` (allows fractional modifiers).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

from sonar.overlays.exceptions import InsufficientDataError, OverlayError

if TYPE_CHECKING:
    from datetime import date
    from uuid import UUID

__all__ = [
    "AGENCY_LOOKUP",
    "APRIL_2026_CALIBRATION",
    "ConsolidatedRating",
    "InvalidRatingTokenError",
    "MODIFIER_OUTLOOK",
    "MODIFIER_WATCH",
    "METHODOLOGY_VERSION_AGENCY",
    "METHODOLOGY_VERSION_CALIBRATION",
    "METHODOLOGY_VERSION_CONSOLIDATED",
    "RatingAgencyRaw",
    "consolidate",
    "lookup_default_spread_bps",
    "notch_to_grade",
]

METHODOLOGY_VERSION_AGENCY: str = "RATING_AGENCY_v0.1"
METHODOLOGY_VERSION_CONSOLIDATED: str = "RATING_SPREAD_v0.2"
METHODOLOGY_VERSION_CALIBRATION: str = "RATING_CALIBRATION_v0.1"

Agency = Literal["SP", "MOODYS", "FITCH", "DBRS"]
RatingType = Literal["FC", "LC"]
Outlook = Literal["positive", "stable", "negative", "developing"]
Watch = Literal["watch_positive", "watch_negative", "watch_developing"] | None

MIN_AGENCIES_FOR_CONSOLIDATION: int = 2

# Spec §2 modifier weights (placeholders — recalibrate after 18m, CAL-004).
MODIFIER_OUTLOOK: dict[str, float] = {
    "positive": 0.25,
    "negative": -0.25,
    "stable": 0.0,
    "developing": 0.0,
}
MODIFIER_WATCH: dict[str, float] = {
    "watch_positive": 0.50,
    "watch_negative": -0.50,
    "watch_developing": 0.0,
}


class InvalidRatingTokenError(OverlayError):
    """Raised when an agency rating token is not in the known lookup."""


# ---------------------------------------------------------------------------
# Agency → SONAR notch lookup tables (spec §13.3 reference, Manual Parte V)
# ---------------------------------------------------------------------------

_SP_FITCH_LOOKUP: dict[str, int] = {
    "AAA": 21,
    "AA+": 20,
    "AA": 19,
    "AA-": 18,
    "A+": 17,
    "A": 16,
    "A-": 15,
    "BBB+": 14,
    "BBB": 13,
    "BBB-": 12,
    "BB+": 11,
    "BB": 10,
    "BB-": 9,
    "B+": 8,
    "B": 7,
    "B-": 6,
    "CCC+": 5,
    "CCC": 4,
    "CCC-": 3,
    "CC": 2,
    "C": 1,
    "SD": 0,
    "D": 0,
    "RD": 0,
}

_MOODYS_LOOKUP: dict[str, int] = {
    "Aaa": 21,
    "Aa1": 20,
    "Aa2": 19,
    "Aa3": 18,
    "A1": 17,
    "A2": 16,
    "A3": 15,
    "Baa1": 14,
    "Baa2": 13,
    "Baa3": 12,
    "Ba1": 11,
    "Ba2": 10,
    "Ba3": 9,
    "B1": 8,
    "B2": 7,
    "B3": 6,
    "Caa1": 5,
    "Caa2": 4,
    "Caa3": 3,
    "Ca": 2,
    "C": 1,
}

_DBRS_LOOKUP: dict[str, int] = {
    "AAA": 21,
    "AA (high)": 20,
    "AA": 19,
    "AA (low)": 18,
    "A (high)": 17,
    "A": 16,
    "A (low)": 15,
    "BBB (high)": 14,
    "BBB": 13,
    "BBB (low)": 12,
    "BB (high)": 11,
    "BB": 10,
    "BB (low)": 9,
    "B (high)": 8,
    "B": 7,
    "B (low)": 6,
    "CCC (high)": 5,
    "CCC": 4,
    "CCC (low)": 3,
    "CC": 2,
    "C": 1,
    "D": 0,
}

AGENCY_LOOKUP: dict[Agency, dict[str, int]] = {
    "SP": _SP_FITCH_LOOKUP,
    "MOODYS": _MOODYS_LOOKUP,
    "FITCH": _SP_FITCH_LOOKUP,
    "DBRS": _DBRS_LOOKUP,
}


def lookup_base_notch(agency: Agency, rating_raw: str) -> int:
    table = AGENCY_LOOKUP.get(agency)
    if table is None:
        msg = f"Unknown agency: {agency}"
        raise InvalidRatingTokenError(msg)
    if rating_raw not in table:
        msg = f"Unknown rating token for {agency}: {rating_raw!r}"
        raise InvalidRatingTokenError(msg)
    return table[rating_raw]


def apply_modifiers(
    base_notch: int,
    outlook: Outlook,
    watch: Watch = None,
) -> float:
    out_mod = MODIFIER_OUTLOOK.get(outlook, 0.0)
    watch_mod = MODIFIER_WATCH.get(watch, 0.0) if watch is not None else 0.0
    return float(base_notch) + out_mod + watch_mod


# ---------------------------------------------------------------------------
# Calibration table (April 2026 snapshot per spec §4 line 147)
# ---------------------------------------------------------------------------

# Anchor values: notch → (default_spread_bps, ICE BofA bucket, p25, p75)
# Linearly interpolated for non-anchor notches in `lookup_default_spread_bps`.
APRIL_2026_CALIBRATION: dict[int, tuple[int, str, int, int]] = {
    21: (10, "AAA", 5, 18),
    18: (35, "AA", 22, 52),
    15: (90, "A", 60, 130),
    12: (245, "BBB", 180, 320),
    9: (600, "BB", 450, 780),
    6: (1325, "B", 1000, 1700),
    3: (3250, "CCC", 2500, 4200),
    0: (0, "D", 0, 0),  # default — spread N/A by spec; sentinel 0 for storage
}


_GRADE_BANDS: tuple[tuple[int, str], ...] = (
    (21, "AAA"),
    (18, "AA"),
    (15, "A"),
    (12, "BBB"),
    (9, "BB"),
    (6, "B"),
    (1, "CCC"),
    (0, "D"),
)


def notch_to_grade(notch_int: int) -> str:
    """Map integer notch → ICE BofA bucket (AAA/AA/A/BBB/BB/B/CCC/D)."""
    for floor, grade in _GRADE_BANDS:
        if notch_int >= floor:
            return grade
    return "D"


def lookup_default_spread_bps(
    notch_int: int,
    calibration: dict[int, tuple[int, str, int, int]] = APRIL_2026_CALIBRATION,
) -> int | None:
    """Linear interpolation across calibration anchors. ``None`` for default (notch 0)."""
    if notch_int <= 0:
        return None
    if notch_int in calibration:
        return calibration[notch_int][0]
    anchors = sorted(calibration.keys())
    lo = max((a for a in anchors if a <= notch_int), default=anchors[0])
    hi = min((a for a in anchors if a >= notch_int), default=anchors[-1])
    if lo == hi:
        return calibration[lo][0]
    lo_bps = calibration[lo][0]
    hi_bps = calibration[hi][0]
    weight = (notch_int - lo) / (hi - lo)
    return int(round(lo_bps + weight * (hi_bps - lo_bps)))


# ---------------------------------------------------------------------------
# Dataclasses + consolidation
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RatingAgencyRaw:
    """Per-agency raw rating row (post-modifier)."""

    agency: Agency
    rating_raw: str
    rating_type: RatingType
    base_notch: int
    notch_adjusted: float
    outlook: Outlook
    watch: Watch
    action_date: date


@dataclass(frozen=True, slots=True)
class ConsolidatedRating:
    """Consolidated row across agencies."""

    rating_id: UUID
    country_code: str
    observation_date: date
    rating_type: RatingType
    consolidated_sonar_notch: float
    notch_int: int
    notch_fractional: float
    agencies_count: int
    agencies: dict[str, float]
    outlook_composite: str
    watch_composite: str | None
    default_spread_bps: int | None
    confidence: float
    flags: tuple[str, ...]


def _median_with_floor_tie(values: list[float]) -> float:
    """Median; on even-count ties returns ``floor((lo+hi)/2)`` (conservative)."""
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    mid = n // 2
    if n % 2 == 1:
        return sorted_vals[mid]
    lo, hi = sorted_vals[mid - 1], sorted_vals[mid]
    avg = (lo + hi) / 2.0
    # Conservative tie-break: floor the average.
    import math

    return math.floor(avg) if not math.isclose(lo, hi) else lo


def _outlook_composite(outlooks: list[str]) -> str:
    counts: dict[str, int] = {}
    for o in outlooks:
        counts[o] = counts.get(o, 0) + 1
    best = max(counts.values())
    winners = [o for o, c in counts.items() if c == best]
    if "stable" in winners:
        return "stable"
    return winners[0]


def _watch_composite(watches: list[Watch]) -> str | None:
    for w in watches:
        if w is not None:
            return w
    return None


def _compute_confidence(flags: list[str], agencies_count: int) -> float:
    base = 1.0
    deduction = 0.0
    cap = 1.0
    if "RATING_SINGLE_AGENCY" in flags or agencies_count < 2:
        cap = min(cap, 0.60)
    if "RATING_DEFAULT" in flags:
        cap = min(cap, 0.40)
    if "EM_COVERAGE" in flags:
        cap = min(cap, 0.70)
    if "RATING_SPLIT" in flags:
        deduction += 0.10
    if "RATING_CDS_DIVERGE" in flags:
        deduction += 0.10
    if "RATING_OUTLOOK_UNCERTAIN" in flags:
        deduction += 0.05
    if "RATING_WATCH_UNCERTAIN" in flags:
        deduction += 0.05
    if "STALE" in flags:
        deduction += 0.20
    if "CALIBRATION_STALE" in flags:
        deduction += 0.15
    return float(max(0.0, min(cap, base - deduction)))


def consolidate(
    rows: list[RatingAgencyRaw],
    country_code: str,
    observation_date: date,
    rating_type: RatingType = "FC",
) -> ConsolidatedRating:
    """Median-consolidate per-agency rows + spread lookup.

    Raises:
        InsufficientDataError: when ``len(rows) == 0``.
    """
    if not rows:
        msg = "consolidate requires >=1 agency row"
        raise InsufficientDataError(msg)

    notches = [r.notch_adjusted for r in rows]
    consolidated = _median_with_floor_tie(notches)
    notch_int = int(round(consolidated))
    notch_fractional = float(consolidated - notch_int)

    flags: list[str] = []
    if len(rows) < MIN_AGENCIES_FOR_CONSOLIDATION:
        flags.append("RATING_SINGLE_AGENCY")
    notch_range = max(notches) - min(notches)
    if notch_range >= 3:
        flags.append("RATING_SPLIT")
    if notch_int == 0:
        flags.append("RATING_DEFAULT")
    if any(r.outlook == "developing" for r in rows):
        flags.append("RATING_OUTLOOK_UNCERTAIN")
    if any(r.watch == "watch_developing" for r in rows):
        flags.append("RATING_WATCH_UNCERTAIN")

    spread_bps = lookup_default_spread_bps(notch_int)

    agencies_dict: dict[str, float] = {str(r.agency): r.notch_adjusted for r in rows}
    confidence = _compute_confidence(flags, agencies_count=len(rows))

    return ConsolidatedRating(
        rating_id=uuid4(),
        country_code=country_code,
        observation_date=observation_date,
        rating_type=rating_type,
        consolidated_sonar_notch=float(consolidated),
        notch_int=notch_int,
        notch_fractional=notch_fractional,
        agencies_count=len(rows),
        agencies=agencies_dict,
        outlook_composite=_outlook_composite([r.outlook for r in rows]),
        watch_composite=_watch_composite([r.watch for r in rows]),
        default_spread_bps=spread_bps,
        confidence=confidence,
        flags=tuple(flags),
    )
