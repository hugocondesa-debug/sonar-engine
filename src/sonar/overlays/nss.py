"""Nelson-Siegel-Svensson yield curve overlay (L2).

Spec: docs/specs/overlays/nss-curves.md
Methodology version: NSS_v0.1
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from datetime import date
    from uuid import UUID

    import numpy as np

__all__ = [
    "FIT_BOUNDS",
    "METHODOLOGY_VERSION",
    "MIN_OBSERVATIONS",
    "MIN_OBSERVATIONS_FOR_SVENSSON",
    "STANDARD_FORWARD_KEYS",
    "STANDARD_OUTPUT_TENORS",
    "YIELD_RANGE_PCT",
    "ForwardCurve",
    "NSSFitResult",
    "NSSInput",
    "NSSParams",
    "RealCurve",
    "SpotCurve",
    "ZeroCurve",
    "derive_forward_curve",
    "derive_real_curve",
    "derive_zero_curve",
    "fit_nss",
]

# ---------------------------------------------------------------------------
# Constants (spec §3, §4)
# ---------------------------------------------------------------------------

METHODOLOGY_VERSION: str = "NSS_v0.1"

STANDARD_OUTPUT_TENORS: tuple[str, ...] = (
    "1M",
    "3M",
    "6M",
    "1Y",
    "2Y",
    "3Y",
    "5Y",
    "7Y",
    "10Y",
    "15Y",
    "20Y",
    "30Y",
)

STANDARD_FORWARD_KEYS: tuple[str, ...] = (
    "1y1y",
    "2y1y",
    "1y2y",
    "1y5y",
    "5y5y",
    "10y10y",
)

# NSS fit bounds per spec §4 (β0 lower=0 for Week 2 US; CAL-030 pre-Week 3 DE/JP).
FIT_BOUNDS: tuple[tuple[float, float], ...] = (
    (0.0, 0.20),  # β0
    (-0.15, 0.15),  # β1
    (-0.15, 0.15),  # β2
    (-0.15, 0.15),  # β3
    (0.1, 10.0),  # λ1
    (0.1, 30.0),  # λ2
)

MIN_OBSERVATIONS: int = 6
MIN_OBSERVATIONS_FOR_SVENSSON: int = 9  # below this, use 4-param NS (spec §6)
YIELD_RANGE_PCT: tuple[float, float] = (-5.0, 30.0)

CurveInputType = Literal["par", "zero", "linker_real"]
RealCurveMethod = Literal["direct_linker", "derived"]
ZeroCurveDerivation = Literal["nss_derived", "bootstrap"]


# ---------------------------------------------------------------------------
# Input / Output dataclasses (spec §2, §3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class NSSInput:
    """Per spec §2.

    tenors_years: maturity in years, ∈ grid of spec §2 constraint.
    yields_pct: corresponding yields in percent (e.g. 4.32 for 4.32%).
    """

    tenors_years: np.ndarray
    yields_pct: np.ndarray
    country_code: str  # ISO 3166-1 alpha-2 (post P2-023)
    observation_date: date
    curve_input_type: CurveInputType


@dataclass(frozen=True, slots=True)
class NSSParams:
    """Fitted NSS parameters per spec §4."""

    beta_0: float
    beta_1: float
    beta_2: float
    beta_3: float | None  # None if 4-param reduced fit
    lambda_1: float
    lambda_2: float | None  # None if 4-param reduced fit


@dataclass(frozen=True, slots=True)
class SpotCurve:
    """Per spec §3 / §8 yield_curves_spot."""

    params: NSSParams
    fitted_yields_pct: dict[str, float]
    rmse_bps: float
    confidence: float
    flags: tuple[str, ...]
    observations_used: int


@dataclass(frozen=True, slots=True)
class ZeroCurve:
    """Per spec §3 / §8 yield_curves_zero."""

    zero_rates_pct: dict[str, float]
    derivation: ZeroCurveDerivation


@dataclass(frozen=True, slots=True)
class ForwardCurve:
    """Per spec §3 / §8 yield_curves_forwards."""

    forwards_pct: dict[str, float]
    breakeven_forwards_pct: dict[str, float] | None


@dataclass(frozen=True, slots=True)
class RealCurve:
    """Per spec §3 / §8 yield_curves_real."""

    real_yields_pct: dict[str, float]
    method: RealCurveMethod
    linker_connector: str | None


@dataclass(frozen=True, slots=True)
class NSSFitResult:
    """Composite output for one country-date; shares fit_id across siblings."""

    fit_id: UUID
    country_code: str
    observation_date: date
    methodology_version: str
    spot: SpotCurve
    zero: ZeroCurve
    forward: ForwardCurve
    real: RealCurve | None  # None if country lacks linker and E[π] unavailable


# ---------------------------------------------------------------------------
# Public functions — signatures only (Day 2 AM fills bodies)
# ---------------------------------------------------------------------------


def fit_nss(inputs: NSSInput) -> SpotCurve:
    """Fit Nelson-Siegel-Svensson 6-param to observed yields.

    Reduces to 4-param Nelson-Siegel when 6 <= n_obs < 9 (spec §6 row 2).

    Args:
        inputs: NSSInput with tenors, yields, country, date.

    Returns:
        SpotCurve with fitted params, rmse_bps, confidence, flags.

    Raises:
        InsufficientDataError: n_obs < 6, non-finite values, or yields
            outside [-5%, 30%] (spec §6 row 1).
        ConvergenceError: optimizer fails to converge (spec §6 row 3);
            downstream handler applies linear interp fallback.
    """
    raise NotImplementedError("Day 2 AM implementation")


def derive_zero_curve(spot: SpotCurve) -> ZeroCurve:
    """Derive zero rates from fitted NSS spot curve.

    Per spec §4 step 4: evaluate NSS at STANDARD_OUTPUT_TENORS treated as
    continuously compounded → zero rates.
    """
    raise NotImplementedError("Day 2 AM implementation")


def derive_forward_curve(zero: ZeroCurve) -> ForwardCurve:
    """Derive forward rates from zero curve.

    Per spec §4 step 5: f(t1, t2) = [((1+z2)^t2) / ((1+z1)^t1)]^(1/(t2-t1)) - 1
    Keys: STANDARD_FORWARD_KEYS.
    """
    raise NotImplementedError("Day 2 AM implementation")


def derive_real_curve(
    nominal_spot: SpotCurve,
    linker_yields_pct: dict[str, float] | None = None,
    expected_inflation_pct: dict[str, float] | None = None,
) -> RealCurve | None:
    """Derive real yield curve.

    Per spec §4 step 6:
    - If country in {US,UK,DE,IT,FR,CA,AU} → fit NSS to linker yields.
    - Else → real(τ) = nominal(τ) - E[π(τ)] from overlays/expected-inflation.
    - Returns None if neither path available.
    """
    raise NotImplementedError("Day 2 AM implementation")
