"""Expected-inflation overlay (L2) — Week 3 US v0.1 → Week 11 Sprint 1.

Spec: docs/specs/overlays/expected-inflation.md
Methodology versions:
  - BEI:        ``EXP_INF_BEI_v0.1``
  - SWAP:       ``EXP_INF_SWAP_v0.1``
  - DERIVED:    ``EXP_INF_DERIVED_v0.1``
  - SURVEY:     ``EXP_INF_SURVEY_v0.1``
  - CANONICAL:  ``EXP_INF_CANONICAL_v0.1``

Week 11 Sprint 1 completes the 5-table hierarchy: canonical composer
+ persistence + SWAP + DERIVED writers. Sub-modules:

* :mod:`.swap` — SWAP method (``EA`` writer Sprint 1).
* :mod:`.derived` — DERIVED method (``PT`` EA-aggregate + diff).
* :mod:`.canonical` — hierarchy pick + anchor + persistence.
* :mod:`.backfill` — 10 T1 countries x 60 recent bd orchestrator.

Storage convention per units.md §Yields: all rates decimal (0.0245 =
2.45%). Anchor deviation stored in bps for editorial / display.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date as date_type
    from uuid import UUID

__all__ = [
    "ANCHOR_BANDS_BPS",
    "METHODOLOGY_VERSION_BEI",
    "METHODOLOGY_VERSION_CANONICAL",
    "METHODOLOGY_VERSION_DERIVED",
    "METHODOLOGY_VERSION_SURVEY",
    "MIN_CONFIDENCE_NOMINAL",
    "STANDARD_TENORS",
    "ExpInfBEI",
    "ExpInfCanonical",
    "ExpInfSurvey",
    "anchor_status",
    "build_bei_row",
    "build_canonical",
    "build_us_bei_row",
    "compute_5y5y",
    "compute_bei_from_yields",
    "compute_bei_us",
    "compute_survey_spf",
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


def compute_survey_spf(
    country_code: str,
    survey_horizons: dict[str, float],
    *,
    observation_date: date_type,
    survey_release_date: date_type,
    is_area_proxy: bool = False,
    survey_name: str = "ECB_SPF_HICP",
) -> ExpInfSurvey:
    """EA SURVEY method — ECB SPF HICP point-forecast composition.

    Consumes the ECB SPF horizons exposed by :meth:`sonar.connectors.
    ecb_sdw.EcbSdwConnector.fetch_survey_expected_inflation`:

    * ``1Y`` / ``2Y`` — rolling 1y / 2y-ahead inflation expectations.
    * ``LTE`` — SPF "long-term" (≈ 5y ahead) anchor proxy. Mapped to
      the canonical ``5Y``, ``10Y`` and ``5y5y`` tenors so downstream
      :func:`build_canonical` + M3 DB-backed readers can evaluate
      anchor deviation.

    ``is_area_proxy`` tags non-``EA`` callers (DE/FR/IT/ES/PT/NL) so
    each per-country emit declares the ``SPF_AREA_PROXY`` flag; Sprint
    Q.1 ships the EA aggregate as the shared survey leg pending
    per-country national-survey CALs. The ``SPF_LT_AS_ANCHOR`` flag
    is always emitted when ``LTE`` is present — analyst transparency
    that the 5y5y value is the SPF long-term horizon (not a
    BEI-derived forward).
    """
    interpolated: dict[str, float] = {}
    if "1Y" in survey_horizons:
        interpolated["1Y"] = survey_horizons["1Y"]
    if "2Y" in survey_horizons:
        interpolated["2Y"] = survey_horizons["2Y"]

    flags: list[str] = []
    if "LTE" in survey_horizons:
        lt_value = survey_horizons["LTE"]
        interpolated.setdefault("5Y", lt_value)
        interpolated.setdefault("10Y", lt_value)
        interpolated.setdefault("5y5y", lt_value)
        interpolated.setdefault("30Y", lt_value)
        flags.append("SPF_LT_AS_ANCHOR")

    if is_area_proxy:
        flags.append("SPF_AREA_PROXY")

    return ExpInfSurvey(
        country_code=country_code,
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


# Re-export from sub-module so ``from sonar.overlays.expected_inflation
# import ExpInfCanonical, build_canonical`` continues to resolve (back-
# compat with Week 3 caller surface) while the canonical composer +
# persistence lives in :mod:`.canonical` per Sprint 1 split. Placed at
# module tail so canonical.py's own imports of this package can read
# :class:`ExpInfBEI` / :class:`ExpInfSurvey` without circular-import
# error.
from sonar.overlays.expected_inflation.bei import (  # noqa: E402
    build_bei_row,
    build_us_bei_row,
)
from sonar.overlays.expected_inflation.canonical import (  # noqa: E402
    ExpInfCanonical,
    build_canonical,
)
