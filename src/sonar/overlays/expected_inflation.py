"""Expected-inflation overlay (L2) — Week 3 US v0.1.

Spec: docs/specs/overlays/expected-inflation.md
Methodology versions:
  - BEI:        ``EXP_INF_BEI_v0.1``
  - SWAP:       ``EXP_INF_SWAP_v0.1`` (not implemented Week 3)
  - DERIVED:    ``EXP_INF_DERIVED_v0.1`` (not implemented Week 3)
  - SURVEY:     ``EXP_INF_SURVEY_v0.1``
  - CANONICAL:  ``EXP_INF_CANONICAL_v0.1``

Week 3 scope: US BEI + SURVEY paths only. EA + DE/PT DERIVED paths
deferred to Week 4 sprint (CAL-043).

Storage convention per units.md §Yields: all rates decimal (0.0245 =
2.45%). Anchor deviation stored in bps for editorial / display.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

if TYPE_CHECKING:
    from datetime import date as date_type
    from uuid import UUID

__all__ = [
    "ANCHOR_BANDS_BPS",
    "ExpInfBEI",
    "ExpInfCanonical",
    "ExpInfSurvey",
    "METHODOLOGY_VERSION_BEI",
    "METHODOLOGY_VERSION_CANONICAL",
    "METHODOLOGY_VERSION_SURVEY",
    "STANDARD_TENORS",
    "anchor_status",
    "build_canonical",
    "compute_5y5y",
    "compute_bei_from_yields",
    "compute_bei_us",
    "compute_survey_us",
]

METHODOLOGY_VERSION_BEI: str = "EXP_INF_BEI_v0.1"
METHODOLOGY_VERSION_SURVEY: str = "EXP_INF_SURVEY_v0.1"
METHODOLOGY_VERSION_DERIVED: str = "EXP_INF_DERIVED_v0.1"
METHODOLOGY_VERSION_CANONICAL: str = "EXP_INF_CANONICAL_v0.1"

# Spec §4 + §8: canonical tenors include forward 5y5y.
STANDARD_TENORS: tuple[str, ...] = ("1Y", "2Y", "5Y", "10Y", "30Y", "5y5y")

# Anchor bands per `config/bc_targets.yaml::anchor_bands_bps`.
ANCHOR_BANDS_BPS: dict[str, int] = {
    "well_anchored": 20,
    "moderately_anchored": 50,
    "drifting": 100,
}

MIN_CONFIDENCE_NOMINAL: float = 0.50
HierarchyMethod = Literal["BEI", "SWAP", "DERIVED", "SURVEY"]
HIERARCHY: tuple[HierarchyMethod, ...] = ("BEI", "SWAP", "DERIVED", "SURVEY")


@dataclass(frozen=True, slots=True)
class ExpInfBEI:
    """BEI method row — per-tenor breakeven from nominal - linker real."""

    country_code: str
    observation_date: date_type
    nominal_yields: dict[str, float]
    linker_real_yields: dict[str, float]
    bei_tenors: dict[str, float]
    linker_connector: str
    nss_fit_id: UUID | None
    confidence: float
    flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExpInfSurvey:
    """SURVEY method row — survey-based expectations."""

    country_code: str
    observation_date: date_type
    survey_name: str
    survey_release_date: date_type
    horizons: dict[str, float]
    interpolated_tenors: dict[str, float]
    confidence: float
    flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExpInfCanonical:
    """Canonical per-tenor selection across methods."""

    exp_inf_id: UUID
    country_code: str
    observation_date: date_type
    expected_inflation_tenors: dict[str, float]
    source_method_per_tenor: dict[str, HierarchyMethod]
    methods_available: int
    bc_target_pct: float | None
    anchor_deviation_bps: int | None
    anchor_status: str | None
    bei_vs_survey_divergence_bps: int | None
    confidence: float
    flags: tuple[str, ...] = field(default_factory=tuple)


def compute_bei_from_yields(
    nominal_yields: dict[str, float],
    linker_real_yields: dict[str, float],
) -> dict[str, float]:
    """BEI(τ) = nominal(τ) - linker_real(τ) for tenors present in both maps.

    Inputs are decimal per units.md (0.0415 = 4.15%). Returns decimal too.
    """
    return {
        t: nominal_yields[t] - linker_real_yields[t]
        for t in nominal_yields
        if t in linker_real_yields
    }


def compute_5y5y(rate_5y_decimal: float, rate_10y_decimal: float) -> float:
    """5y5y compounded: ``[(1+r10)^10 / (1+r5)^5]^(1/5) - 1`` per spec §4."""
    num = (1.0 + rate_10y_decimal) ** 10
    den = (1.0 + rate_5y_decimal) ** 5
    result: float = (num / den) ** (1.0 / 5.0) - 1.0
    return result


def compute_bei_us(
    nominal_yields: dict[str, float],
    bei_market: dict[str, float],
    *,
    observation_date: date_type,
    linker_connector: str = "fred",
    nss_fit_id: UUID | None = None,
) -> ExpInfBEI:
    """US BEI method: prefer market-published BEI (FRED T*YIE) over manual
    nominal - linker subtraction. Adds compounded 5y5y when 5Y + 10Y both
    present. Returns ExpInfBEI with confidence 1.0 baseline (flags absent).
    """
    bei_tenors = dict(bei_market)
    if "5Y" in bei_tenors and "10Y" in bei_tenors:
        bei_tenors["5y5y"] = compute_5y5y(bei_tenors["5Y"], bei_tenors["10Y"])

    flags: list[str] = []
    return ExpInfBEI(
        country_code="US",
        observation_date=observation_date,
        nominal_yields=dict(nominal_yields),
        linker_real_yields={},  # using market BEI directly; raw linker not stored
        bei_tenors=bei_tenors,
        linker_connector=linker_connector,
        nss_fit_id=nss_fit_id,
        confidence=1.0,
        flags=tuple(flags),
    )


def compute_survey_us(
    survey_horizons: dict[str, float],
    *,
    observation_date: date_type,
    survey_release_date: date_type,
    survey_name: str = "FRED_COMPOSITE",
) -> ExpInfSurvey:
    """US SURVEY method — Michigan 1Y + Cleveland Fed model 10Y; interpolate
    to other canonical tenors via linear in (1Y, 10Y) span.
    """
    interpolated = dict(survey_horizons)
    if "1Y" in survey_horizons and "10Y" in survey_horizons:
        r_1, r_10 = survey_horizons["1Y"], survey_horizons["10Y"]
        for tenor_label, years in (("2Y", 2.0), ("5Y", 5.0), ("30Y", 30.0)):
            if tenor_label in interpolated:
                continue
            # Linear interp in years for 2Y/5Y; constant-extrapolate 30Y.
            if 1.0 <= years <= 10.0:
                weight = (years - 1.0) / (10.0 - 1.0)
                interpolated[tenor_label] = r_1 + weight * (r_10 - r_1)
            else:
                interpolated[tenor_label] = r_10

    if "5Y" in interpolated and "10Y" in interpolated:
        interpolated["5y5y"] = compute_5y5y(interpolated["5Y"], interpolated["10Y"])

    flags: list[str] = []
    return ExpInfSurvey(
        country_code="US",
        observation_date=observation_date,
        survey_name=survey_name,
        survey_release_date=survey_release_date,
        horizons=dict(survey_horizons),
        interpolated_tenors=interpolated,
        confidence=1.0,
        flags=tuple(flags),
    )


def anchor_status(deviation_bps_abs: int) -> str:
    """Map |deviation_bps| → band per ANCHOR_BANDS_BPS thresholds."""
    if deviation_bps_abs < ANCHOR_BANDS_BPS["well_anchored"]:
        return "well_anchored"
    if deviation_bps_abs < ANCHOR_BANDS_BPS["moderately_anchored"]:
        return "moderately_anchored"
    if deviation_bps_abs < ANCHOR_BANDS_BPS["drifting"]:
        return "drifting"
    return "unanchored"


def _hierarchy_pick(
    tenor: str,
    method_rows: dict[HierarchyMethod, dict[str, float]],
    min_confidence: dict[HierarchyMethod, float],
) -> tuple[HierarchyMethod | None, float | None]:
    for method in HIERARCHY:
        rates = method_rows.get(method)
        if rates is None:
            continue
        if tenor not in rates:
            continue
        if min_confidence.get(method, 0.0) < MIN_CONFIDENCE_NOMINAL:
            continue
        return method, rates[tenor]
    return None, None


def build_canonical(
    *,
    country_code: str,
    observation_date: date_type,
    bei: ExpInfBEI | None = None,
    survey: ExpInfSurvey | None = None,
    bc_target_pct: float | None = None,
) -> ExpInfCanonical:
    """Hierarchy picker (BEI > SURVEY for Week 3 US) + anchor computation."""
    method_rows: dict[HierarchyMethod, dict[str, float]] = {}
    confidences: dict[HierarchyMethod, float] = {}
    if bei is not None:
        method_rows["BEI"] = bei.bei_tenors
        confidences["BEI"] = bei.confidence
    if survey is not None:
        method_rows["SURVEY"] = survey.interpolated_tenors
        confidences["SURVEY"] = survey.confidence

    expected_tenors: dict[str, float] = {}
    sources: dict[str, HierarchyMethod] = {}
    flags: list[str] = []

    for tenor in STANDARD_TENORS:
        method, value = _hierarchy_pick(tenor, method_rows, confidences)
        if method is None or value is None:
            continue
        expected_tenors[tenor] = value
        sources[tenor] = method

    methods_available = len(method_rows)

    # Anchor computation requires 5y5y forward.
    deviation_bps: int | None = None
    status: str | None = None
    if bc_target_pct is not None and "5y5y" in expected_tenors:
        deviation = expected_tenors["5y5y"] - bc_target_pct
        deviation_bps = int(round(deviation * 10_000.0))
        status = anchor_status(abs(deviation_bps))
    else:
        flags.append("ANCHOR_UNCOMPUTABLE")

    bei_vs_survey: int | None = None
    if bei is not None and survey is not None:
        bei_10y = bei.bei_tenors.get("10Y")
        survey_10y = survey.interpolated_tenors.get("10Y")
        if bei_10y is not None and survey_10y is not None:
            diff = abs(bei_10y - survey_10y)
            bei_vs_survey = int(round(diff * 10_000.0))
            if bei_vs_survey > 100:
                flags.append("INFLATION_METHOD_DIVERGENCE")

    base_confidence = max(confidences.values()) if confidences else 0.0
    deduction = 0.0
    if "INFLATION_METHOD_DIVERGENCE" in flags:
        deduction += 0.10
    if "ANCHOR_UNCOMPUTABLE" in flags:
        deduction += 0.10
    confidence_canonical = max(0.0, min(1.0, base_confidence - deduction))

    return ExpInfCanonical(
        exp_inf_id=uuid4(),
        country_code=country_code,
        observation_date=observation_date,
        expected_inflation_tenors=expected_tenors,
        source_method_per_tenor=sources,
        methods_available=methods_available,
        bc_target_pct=bc_target_pct,
        anchor_deviation_bps=deviation_bps,
        anchor_status=status,
        bei_vs_survey_divergence_bps=bei_vs_survey,
        confidence=confidence_canonical,
        flags=tuple(flags),
    )
