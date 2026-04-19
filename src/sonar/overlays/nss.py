"""Nelson-Siegel-Svensson yield curve overlay (L2).

Spec: docs/specs/overlays/nss-curves.md
Methodology version: NSS_v0.1

Unit convention (per ``docs/specs/conventions/units.md`` §Yields):
- All yields, betas, and lambdas are stored and computed in **decimal**
  (0.0415 = 4.15%). Display-layer conversion to percent happens in
  ``sonar/outputs/exporters/`` (to be implemented), never here.
- ``NSSInput.yields`` and every ``*_yields`` / ``*_rates`` / ``forwards``
  dict in the output dataclasses carries decimal values.
- ``rmse_bps`` is the only output intentionally expressed in basis
  points (integer-friendly) per spec §3 + units.md §Spreads.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

import numpy as np
import scipy.optimize

from sonar.overlays.exceptions import ConvergenceError, InsufficientDataError

if TYPE_CHECKING:
    from datetime import date
    from uuid import UUID

__all__ = [
    "FIT_BOUNDS",
    "LINKER_MIN_OBSERVATIONS",
    "METHODOLOGY_VERSION",
    "MIN_OBSERVATIONS",
    "MIN_OBSERVATIONS_FOR_SVENSSON",
    "STANDARD_FORWARD_KEYS",
    "STANDARD_OUTPUT_TENORS",
    "YIELD_RANGE",
    "ForwardCurve",
    "NSSFitResult",
    "NSSInput",
    "NSSParams",
    "RealCurve",
    "SpotCurve",
    "ZeroCurve",
    "assemble_nss_fit_result",
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

# CAL-033: linker (TIPS / inflation-indexed) curves are published only at the
# long-end (Fed publishes DFII5/7/10/20/30 — 5 tenors, no short-end). Spec §6
# row 1 nominal threshold (n_obs<6 raises) is preserved; linker_real curves
# accept n_obs>=5. Carve-out is implementation-detail within the linker_real
# code path; nominal callers see no change. No NSS_v0.1 bump.
LINKER_MIN_OBSERVATIONS: int = 5

# Decimal yield range per units.md §Yields (-5% to 30% expressed as decimal).
YIELD_RANGE: tuple[float, float] = (-0.05, 0.30)

# Tier 1 RMSE threshold in bps per spec §6 (`rmse_bps > 15` triggers HIGH_RMSE).
HIGH_RMSE_THRESHOLD_BPS_T1: float = 15.0

CurveInputType = Literal["par", "zero", "linker_real"]
RealCurveMethod = Literal["direct_linker", "derived"]
ZeroCurveDerivation = Literal["nss_derived", "bootstrap"]
Tier = Literal["T1", "T2", "T3", "T4"]


# ---------------------------------------------------------------------------
# Input / Output dataclasses (spec §2, §3) — all yields in DECIMAL per units.md
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class NSSInput:
    """Per spec §2. Yields in decimal (0.0415 = 4.15%), per units.md."""

    tenors_years: np.ndarray
    yields: np.ndarray
    country_code: str  # ISO 3166-1 alpha-2 (post P2-023)
    observation_date: date
    curve_input_type: CurveInputType


@dataclass(frozen=True, slots=True)
class NSSParams:
    """Fitted NSS parameters per spec §4 (all in decimal)."""

    beta_0: float
    beta_1: float
    beta_2: float
    beta_3: float | None  # None if 4-param reduced fit
    lambda_1: float
    lambda_2: float | None  # None if 4-param reduced fit


@dataclass(frozen=True, slots=True)
class SpotCurve:
    """Per spec §3 / §8 yield_curves_spot. ``fitted_yields`` dict values decimal."""

    params: NSSParams
    fitted_yields: dict[str, float]
    rmse_bps: float
    confidence: float
    flags: tuple[str, ...]
    observations_used: int


@dataclass(frozen=True, slots=True)
class ZeroCurve:
    """Per spec §3 / §8 yield_curves_zero. ``zero_rates`` dict values decimal."""

    zero_rates: dict[str, float]
    derivation: ZeroCurveDerivation


@dataclass(frozen=True, slots=True)
class ForwardCurve:
    """Per spec §3 / §8 yield_curves_forwards. ``forwards`` dict values decimal."""

    forwards: dict[str, float]
    breakeven_forwards: dict[str, float] | None


@dataclass(frozen=True, slots=True)
class RealCurve:
    """Per spec §3 / §8 yield_curves_real. ``real_yields`` dict values decimal."""

    real_yields: dict[str, float]
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
# Tenor label ↔ years helpers
# ---------------------------------------------------------------------------

_TENOR_LABEL_TO_YEARS: dict[str, float] = {
    "1M": 1 / 12,
    "3M": 0.25,
    "6M": 0.5,
    "1Y": 1.0,
    "2Y": 2.0,
    "3Y": 3.0,
    "5Y": 5.0,
    "7Y": 7.0,
    "10Y": 10.0,
    "15Y": 15.0,
    "20Y": 20.0,
    "30Y": 30.0,
}


def _label_to_years(label: str) -> float:
    return _TENOR_LABEL_TO_YEARS[label]


def _tenor_years_to_label(years: float) -> str:
    """Return the canonical label nearest to ``years`` (tolerance 0.01y)."""
    best = min(_TENOR_LABEL_TO_YEARS.items(), key=lambda kv: abs(kv[1] - years))
    label, canonical = best
    if abs(canonical - years) > 0.01:
        msg = f"Non-standard tenor {years}y cannot be labeled"
        raise ValueError(msg)
    return label


# ---------------------------------------------------------------------------
# NSS math primitives
# ---------------------------------------------------------------------------


def _nss_eval(
    tenors_years: np.ndarray,
    beta_0: float,
    beta_1: float,
    beta_2: float,
    beta_3: float | None,
    lambda_1: float,
    lambda_2: float | None,
) -> np.ndarray:
    """Evaluate NSS at given tenors, returning decimal yields.

    Stable at τ → 0 via ``np.expm1``. Collapses to 4-param Nelson-Siegel
    when ``beta_3`` and ``lambda_2`` are both ``None`` (spec §6 row 2).
    """
    tau = np.asarray(tenors_years, dtype=np.float64)
    x1 = tau / lambda_1

    with np.errstate(divide="ignore", invalid="ignore"):
        term1_load = np.where(x1 == 0, 1.0, -np.expm1(-x1) / x1)
    term2_load = term1_load - np.exp(-x1)

    y = beta_0 + beta_1 * term1_load + beta_2 * term2_load

    if beta_3 is not None and lambda_2 is not None:
        x2 = tau / lambda_2
        with np.errstate(divide="ignore", invalid="ignore"):
            term3_load_a = np.where(x2 == 0, 1.0, -np.expm1(-x2) / x2)
        term3_load = term3_load_a - np.exp(-x2)
        y = y + beta_3 * term3_load

    return y


def _params_as_args(
    params: NSSParams,
) -> tuple[float, float, float, float | None, float, float | None]:
    return (
        params.beta_0,
        params.beta_1,
        params.beta_2,
        params.beta_3,
        params.lambda_1,
        params.lambda_2,
    )


# ---------------------------------------------------------------------------
# Validation (spec §6 row 1)
# ---------------------------------------------------------------------------


def _validate_inputs(inputs: NSSInput) -> None:
    n = len(inputs.tenors_years)
    threshold = (
        LINKER_MIN_OBSERVATIONS if inputs.curve_input_type == "linker_real" else MIN_OBSERVATIONS
    )
    if n < threshold:
        msg = f"NSS requires >={threshold} observations, got {n}"
        raise InsufficientDataError(msg)
    if len(inputs.yields) != n:
        msg = f"tenors ({n}) and yields ({len(inputs.yields)}) length mismatch"
        raise InsufficientDataError(msg)
    if not np.all(np.isfinite(inputs.tenors_years)):
        raise InsufficientDataError("Non-finite tenor values")
    if not np.all(np.isfinite(inputs.yields)):
        raise InsufficientDataError("Non-finite yield values (NaN or inf)")
    lo, hi = YIELD_RANGE
    if np.any(inputs.yields < lo) or np.any(inputs.yields > hi):
        msg = f"Yields outside [{lo}, {hi}] decimal range"
        raise InsufficientDataError(msg)
    if not np.all(np.diff(inputs.tenors_years) > 0):
        raise InsufficientDataError("Tenors must be strictly ascending")


# ---------------------------------------------------------------------------
# Optimizer (spec §4 L-BFGS-B)
# ---------------------------------------------------------------------------

_OPTIMIZER_OPTIONS = {"maxiter": 500, "ftol": 1e-10, "gtol": 1e-8}


def _fit_nss_6param(
    tenors: np.ndarray,
    yields_dec: np.ndarray,
) -> tuple[NSSParams, float]:
    x0 = np.array(
        [
            yields_dec[-1],  # β0 ≈ long-end
            yields_dec[0] - yields_dec[-1],  # β1 ≈ short-long slope
            0.0,
            0.0,
            1.5,
            5.0,
        ],
        dtype=np.float64,
    )

    def loss(x: np.ndarray) -> float:
        b0, b1, b2, b3, l1, l2 = x
        fitted = _nss_eval(tenors, b0, b1, b2, b3, l1, l2)
        residuals = fitted - yields_dec
        return float(np.sum(residuals * residuals))

    result = scipy.optimize.minimize(
        loss,
        x0,
        method="L-BFGS-B",
        bounds=FIT_BOUNDS,
        options=_OPTIMIZER_OPTIONS,
    )
    if not result.success:
        msg = f"NSS 6-param fit did not converge: {result.message}"
        raise ConvergenceError(msg)

    b0, b1, b2, b3, l1, l2 = result.x
    params = NSSParams(
        beta_0=float(b0),
        beta_1=float(b1),
        beta_2=float(b2),
        beta_3=float(b3),
        lambda_1=float(l1),
        lambda_2=float(l2),
    )
    rmse_dec = float(np.sqrt(result.fun / len(tenors)))
    return params, rmse_dec


def _fit_ns_4param(
    tenors: np.ndarray,
    yields_dec: np.ndarray,
) -> tuple[NSSParams, float]:
    x0 = np.array(
        [
            yields_dec[-1],  # β0
            yields_dec[0] - yields_dec[-1],  # β1
            0.0,  # β2
            1.5,  # λ1
        ],
        dtype=np.float64,
    )
    bounds = (FIT_BOUNDS[0], FIT_BOUNDS[1], FIT_BOUNDS[2], FIT_BOUNDS[4])

    def loss(x: np.ndarray) -> float:
        b0, b1, b2, l1 = x
        fitted = _nss_eval(tenors, b0, b1, b2, None, l1, None)
        residuals = fitted - yields_dec
        return float(np.sum(residuals * residuals))

    result = scipy.optimize.minimize(
        loss,
        x0,
        method="L-BFGS-B",
        bounds=bounds,
        options=_OPTIMIZER_OPTIONS,
    )
    if not result.success:
        msg = f"NSS 4-param fit did not converge: {result.message}"
        raise ConvergenceError(msg)

    b0, b1, b2, l1 = result.x
    params = NSSParams(
        beta_0=float(b0),
        beta_1=float(b1),
        beta_2=float(b2),
        beta_3=None,
        lambda_1=float(l1),
        lambda_2=None,
    )
    rmse_dec = float(np.sqrt(result.fun / len(tenors)))
    return params, rmse_dec


# ---------------------------------------------------------------------------
# Confidence (spec §6 via flags.md authoritative propagation)
# ---------------------------------------------------------------------------


def _compute_confidence(flags: list[str], tier: Tier = "T1") -> float:
    """Cap-then-deduct per flags.md §Convenção header.

    Base 1.0, additive deductions, cap via min. Floor 0.0, ceiling 1.0.
    """
    base = 1.0
    deduction = 0.0
    cap = 1.0

    # Caps per flags.md §1.1 (NSS overlays)
    if "NSS_REDUCED" in flags:
        cap = min(cap, 0.75)
    if "NSS_FAIL" in flags:
        cap = min(cap, 0.50)
    if "REGIME_BREAK" in flags:
        cap = min(cap, 0.60)
    if "EM_COVERAGE" in flags or tier == "T4":
        cap = min(cap, 0.70)

    # Additive deductions per flags.md §1.1 + §4 Generic
    if "HIGH_RMSE" in flags:
        deduction += 0.20
    if "XVAL_DRIFT" in flags:
        deduction += 0.10
    if "NEG_FORWARD" in flags:
        deduction += 0.15
    if "EXTRAPOLATED" in flags:
        deduction += 0.10
    if "STALE" in flags:
        deduction += 0.20
    if "COMPLEX_SHAPE" in flags:
        deduction += 0.10

    return float(max(0.0, min(cap, base - deduction)))


# ---------------------------------------------------------------------------
# Public fit entry point
# ---------------------------------------------------------------------------


def fit_nss(inputs: NSSInput, tier: Tier = "T1") -> SpotCurve:
    """Fit Nelson-Siegel-Svensson 6-param to observed yields (decimal in, decimal out).

    Reduces to 4-param Nelson-Siegel when ``6 <= n_obs < 9`` (spec §6 row 2).

    Raises:
        InsufficientDataError: n_obs < 6, non-finite, or yields outside YIELD_RANGE.
        ConvergenceError: optimizer fails to converge (spec §6 row 3).
    """
    _validate_inputs(inputs)

    tenors = np.asarray(inputs.tenors_years, dtype=np.float64)
    yields_dec = np.asarray(inputs.yields, dtype=np.float64)
    n_obs = len(tenors)
    reduced = n_obs < MIN_OBSERVATIONS_FOR_SVENSSON

    flags: list[str] = []
    if reduced:
        params, rmse_dec = _fit_ns_4param(tenors, yields_dec)
        flags.append("NSS_REDUCED")
    else:
        params, rmse_dec = _fit_nss_6param(tenors, yields_dec)

    rmse_bps = rmse_dec * 10_000.0

    if tier == "T1" and rmse_bps > HIGH_RMSE_THRESHOLD_BPS_T1:
        flags.append("HIGH_RMSE")

    fitted_decimal = _nss_eval(tenors, *_params_as_args(params))
    fitted: dict[str, float] = {
        _tenor_years_to_label(float(t)): float(y)
        for t, y in zip(tenors, fitted_decimal, strict=True)
    }

    confidence = _compute_confidence(flags, tier=tier)

    return SpotCurve(
        params=params,
        fitted_yields=fitted,
        rmse_bps=float(rmse_bps),
        confidence=float(confidence),
        flags=tuple(flags),
        observations_used=n_obs,
    )


# ---------------------------------------------------------------------------
# Derivations
# ---------------------------------------------------------------------------


def derive_zero_curve(spot: SpotCurve) -> ZeroCurve:
    """Evaluate NSS at STANDARD_OUTPUT_TENORS (spec §4 step 4). Phase 1 simplification:
    treats fitted yields as zero rates directly (full bootstrap is Phase 2).
    """
    tenor_years = np.array([_label_to_years(t) for t in STANDARD_OUTPUT_TENORS])
    zeros_decimal = _nss_eval(tenor_years, *_params_as_args(spot.params))
    zero_rates: dict[str, float] = {
        label: float(z) for label, z in zip(STANDARD_OUTPUT_TENORS, zeros_decimal, strict=True)
    }
    return ZeroCurve(zero_rates=zero_rates, derivation="nss_derived")


_FORWARD_KEY_PATTERN = re.compile(r"^(\d+)y(\d+)y$")


def _parse_forward_key(key: str) -> tuple[int, int]:
    m = _FORWARD_KEY_PATTERN.match(key)
    if m is None:
        msg = f"Invalid forward key: {key}"
        raise ValueError(msg)
    start = int(m.group(1))
    tenor = int(m.group(2))
    return start, start + tenor


def derive_forward_curve(zero: ZeroCurve) -> ForwardCurve:
    """Bootstrap forward rates from zero curve (spec §4 step 5)."""
    zero_years: dict[float, float] = {_label_to_years(k): v for k, v in zero.zero_rates.items()}
    years_sorted = sorted(zero_years)
    rates_sorted = [zero_years[y] for y in years_sorted]

    def _z(t: float) -> float:
        return float(np.interp(t, years_sorted, rates_sorted))

    forwards: dict[str, float] = {}
    for key in STANDARD_FORWARD_KEYS:
        t1, t2 = _parse_forward_key(key)
        z1, z2 = _z(float(t1)), _z(float(t2))
        f = ((1 + z2) ** t2 / (1 + z1) ** t1) ** (1 / (t2 - t1)) - 1
        forwards[key] = float(f)

    return ForwardCurve(forwards=forwards, breakeven_forwards=None)


def derive_real_curve(
    nominal_spot: SpotCurve,  # noqa: ARG001 — kept for contract; derived path uses it Phase 1 later
    linker_yields: dict[str, float] | None = None,
    expected_inflation: dict[str, float] | None = None,  # noqa: ARG001 — derived path Phase 1 later
    observation_date: date | None = None,
    country_code: str = "US",
    tier: Tier = "T1",
) -> RealCurve | None:
    """Direct-linker path only for Week 2 (spec §4 step 6).

    The derived path ``real = nominal - E[π]`` is stubbed (returns ``None``)
    until ``overlays/expected-inflation`` integration lands (Phase 1 later).
    """
    if linker_yields is None:
        return None

    labels = list(linker_yields.keys())
    tenors = np.array([_label_to_years(label) for label in labels], dtype=np.float64)
    yields_dec = np.array([linker_yields[label] for label in labels], dtype=np.float64)
    order = np.argsort(tenors)
    tenors = tenors[order]
    yields_dec = yields_dec[order]

    from datetime import date as _date

    linker_input = NSSInput(
        tenors_years=tenors,
        yields=yields_dec,
        country_code=country_code,
        observation_date=observation_date or _date(1970, 1, 1),
        curve_input_type="linker_real",
    )
    linker_fit = fit_nss(linker_input, tier=tier)

    std_years = np.array(
        [_label_to_years(label) for label in STANDARD_OUTPUT_TENORS],
        dtype=np.float64,
    )
    real_decimal = _nss_eval(std_years, *_params_as_args(linker_fit.params))
    real_yields: dict[str, float] = {
        label: float(r) for label, r in zip(STANDARD_OUTPUT_TENORS, real_decimal, strict=True)
    }
    return RealCurve(
        real_yields=real_yields,
        method="direct_linker",
        linker_connector="fred",
    )


def assemble_nss_fit_result(
    country_code: str,
    observation_date: date,
    spot: SpotCurve,
    zero: ZeroCurve,
    forward: ForwardCurve,
    real: RealCurve | None,
) -> NSSFitResult:
    """Build an ``NSSFitResult`` with a fresh ``fit_id`` shared by all siblings."""
    return NSSFitResult(
        fit_id=uuid4(),
        country_code=country_code,
        observation_date=observation_date,
        methodology_version=METHODOLOGY_VERSION,
        spot=spot,
        zero=zero,
        forward=forward,
        real=real,
    )
