"""ERP overlay (L2) — 4-method compute core.

Spec: docs/specs/overlays/erp-daily.md
Methodology versions:
  - DCF:       ``ERP_DCF_v0.1``
  - Gordon:    ``ERP_GORDON_v0.1``
  - Earnings Yield: ``ERP_EY_v0.1``
  - CAPE:      ``ERP_CAPE_v0.1``
  - Canonical summary: ``ERP_CANONICAL_v0.1``

Pure-compute layer: all network + connector IO happens upstream in
the pipeline. :func:`fit_erp_us` takes a pre-assembled :class:`ERPInput`
and returns an :class:`ERPFitResult` with per-method rows + canonical
aggregation, suitable for the persistence layer (commit 6).

Units: all ERP values stored as ``erp_bps`` ``int`` at persistence
boundary per conventions/units.md §Spreads. Compute is done in
decimal; conversion via ``int(round(decimal * 10_000))`` at the edge.

Confidence propagation per conventions/flags.md: per-method floor is
1.0 with -0.05 per flag; canonical takes ``min(method_confidences)``
then deducts ``0.05 * (4 - methods_available)`` for missing methods,
clamped to [0, 1].

No network. No cross-connector orchestration. Caller (pipeline at
L8) is responsible for fetching inputs, applying freshness flags,
handling InsufficientDataError, and persisting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import numpy as np
import structlog
from scipy import optimize

from sonar.overlays.exceptions import ConvergenceError, InsufficientDataError

if TYPE_CHECKING:
    from datetime import date

log = structlog.get_logger()

__all__ = [
    "DCF_BOUNDS",
    "DIVERGENCE_THRESHOLD_BPS",
    "FORWARD_EPS_DIVERGENCE_THRESHOLD",
    "GROWTH_HORIZON_YEARS",
    "G_SUSTAINABLE_CAP",
    "METHODOLOGY_VERSION_CANONICAL",
    "METHODOLOGY_VERSION_CAPE",
    "METHODOLOGY_VERSION_DCF",
    "METHODOLOGY_VERSION_EY",
    "METHODOLOGY_VERSION_GORDON",
    "MIN_METHODS_FOR_CANONICAL",
    "ERPCanonicalResult",
    "ERPFitResult",
    "ERPInput",
    "ERPMethodResult",
    "fit_erp_us",
]

METHODOLOGY_VERSION_DCF: str = "ERP_DCF_v0.1"
METHODOLOGY_VERSION_GORDON: str = "ERP_GORDON_v0.1"
METHODOLOGY_VERSION_EY: str = "ERP_EY_v0.1"
METHODOLOGY_VERSION_CAPE: str = "ERP_CAPE_v0.1"
METHODOLOGY_VERSION_CANONICAL: str = "ERP_CANONICAL_v0.1"

GROWTH_HORIZON_YEARS: int = 5
G_SUSTAINABLE_CAP: float = 0.06
MIN_METHODS_FOR_CANONICAL: int = 2
DIVERGENCE_THRESHOLD_BPS: int = 400
DCF_BOUNDS: tuple[float, float] = (0.0, 0.30)
FORWARD_EPS_DIVERGENCE_THRESHOLD: float = 0.05  # 5 % per spec §4 step 8.5


@dataclass(frozen=True, slots=True)
class ERPInput:
    """All inputs needed to compute a full (market, date) ERP fit.

    Decimal units for yields/growth/retention/ROE (0.12 = 12 %).
    ``buyback_yield_pct`` and ``yardeni_eps`` are optional to support
    graceful degradation per spec §6 edge cases.
    """

    market_index: str
    country_code: str
    observation_date: date
    index_level: float
    trailing_earnings: float  # E_0 for DCF, denominator for CAPE computation
    forward_earnings_est: float  # FactSet primary; EY + DCF consumer
    dividend_yield_pct: float
    buyback_yield_pct: float | None
    cape_ratio: float
    risk_free_nominal: float
    risk_free_real: float
    consensus_growth_5y: float
    retention: float
    roe: float
    # Confidence + flag propagation from upstream connectors / NSS.
    risk_free_confidence: float
    upstream_flags: tuple[str, ...] = ()
    # Optional Yardeni cross-validation fields (US only).
    yardeni_eps: float | None = None
    factset_fresh_days: int | None = None
    yardeni_fresh_days: int | None = None


@dataclass(frozen=True, slots=True)
class ERPMethodResult:
    """Per-method ERP compute row."""

    method: str  # one of "DCF", "GORDON", "EY", "CAPE"
    methodology_version: str
    erp_decimal: float
    confidence: float
    flags: tuple[str, ...]

    @property
    def erp_bps(self) -> int:
        return round(self.erp_decimal * 10_000)


@dataclass(frozen=True, slots=True)
class ERPCanonicalResult:
    """Canonical aggregation across available methods."""

    methodology_version: str
    erp_median_decimal: float
    erp_range_bps: int
    methods_available: int
    confidence: float
    flags: tuple[str, ...]
    xval_deviation_bps: int | None = None
    forward_eps_divergence_pct: float | None = None

    @property
    def erp_median_bps(self) -> int:
        return round(self.erp_median_decimal * 10_000)


@dataclass(frozen=True, slots=True)
class ERPFitResult:
    """Composite result for one (market, date) ERP computation."""

    erp_id: UUID
    market_index: str
    country_code: str
    observation_date: date
    dcf: ERPMethodResult | None
    gordon: ERPMethodResult | None
    ey: ERPMethodResult | None
    cape: ERPMethodResult | None
    canonical: ERPCanonicalResult
    method_results: tuple[ERPMethodResult, ...] = field(default_factory=tuple)


# -----------------------------------------------------------------------------
# Per-method computations
# -----------------------------------------------------------------------------


def _compute_dcf(inputs: ERPInput) -> ERPMethodResult | None:
    """Solve for required return ``r`` via scipy.optimize.newton.

    Returns ``None`` when the root-find does not converge in bounds
    (caller treats as method-miss and flags NSS_FAIL per spec §6).
    """
    g = inputs.consensus_growth_5y
    g_t = inputs.risk_free_nominal
    payout = inputs.dividend_yield_pct + (inputs.buyback_yield_pct or 0.0)
    if payout <= 0.0:
        # Without payout the DCF collapses; surface as method-miss.
        return None
    e0 = inputs.trailing_earnings
    p = inputs.index_level
    x0 = inputs.risk_free_nominal + 0.05

    def residual(r: float) -> float:
        if r <= g_t:  # terminal denominator must stay positive
            return np.inf
        growth_years = np.arange(1, GROWTH_HORIZON_YEARS + 1)
        pv_stream = np.sum(e0 * (1 + g) ** growth_years * payout / (1 + r) ** growth_years)
        pv_terminal = (
            e0
            * (1 + g) ** GROWTH_HORIZON_YEARS
            * (1 + g_t)
            * payout
            / ((r - g_t) * (1 + r) ** GROWTH_HORIZON_YEARS)
        )
        return float(pv_stream + pv_terminal - p)

    try:
        root = optimize.newton(residual, x0=x0, maxiter=100, tol=1e-6)
    except (RuntimeError, OverflowError, ValueError) as exc:
        log.warning("erp.dcf.newton_failed", error=str(exc))
        return None
    if not np.isfinite(root) or not DCF_BOUNDS[0] <= root <= DCF_BOUNDS[1]:
        log.warning("erp.dcf.root_out_of_bounds", root=root)
        return None
    erp = root - inputs.risk_free_nominal
    return _build_method_result(
        "DCF",
        METHODOLOGY_VERSION_DCF,
        erp_decimal=erp,
        upstream_flags=inputs.upstream_flags,
    )


def _compute_gordon(inputs: ERPInput) -> ERPMethodResult:
    """Dividend + buyback + sustainable growth - risk-free.

    ``g_sustainable = min(retention · ROE, G_SUSTAINABLE_CAP)``.
    """
    buyback = inputs.buyback_yield_pct or 0.0
    g_sustainable = min(inputs.retention * inputs.roe, G_SUSTAINABLE_CAP)
    erp = inputs.dividend_yield_pct + buyback + g_sustainable - inputs.risk_free_nominal
    flags = list(inputs.upstream_flags)
    if inputs.buyback_yield_pct is None:
        flags.append("STALE")  # dividend-only per spec §6 "Buyback > 1q stale" edge case
    return _build_method_result(
        "GORDON",
        METHODOLOGY_VERSION_GORDON,
        erp_decimal=erp,
        upstream_flags=tuple(flags),
    )


def _compute_ey(inputs: ERPInput) -> ERPMethodResult:
    """Forward earnings yield minus risk-free (nominal)."""
    erp = (inputs.forward_earnings_est / inputs.index_level) - inputs.risk_free_nominal
    return _build_method_result(
        "EY",
        METHODOLOGY_VERSION_EY,
        erp_decimal=erp,
        upstream_flags=inputs.upstream_flags,
    )


def _compute_cape(inputs: ERPInput) -> ERPMethodResult:
    """CAPE-based ERP anchored to real risk-free.

    ``ERP_CAPE = (1 / CAPE) - real_risk_free``.
    """
    if inputs.cape_ratio <= 0:
        msg = f"cape_ratio must be positive; got {inputs.cape_ratio}"
        raise InsufficientDataError(msg)
    erp = (1.0 / inputs.cape_ratio) - inputs.risk_free_real
    return _build_method_result(
        "CAPE",
        METHODOLOGY_VERSION_CAPE,
        erp_decimal=erp,
        upstream_flags=inputs.upstream_flags,
    )


def _build_method_result(
    method: str,
    methodology_version: str,
    *,
    erp_decimal: float,
    upstream_flags: tuple[str, ...],
) -> ERPMethodResult:
    """Assemble a per-method result with confidence deduction per flag."""
    flags = sorted(set(upstream_flags))
    confidence = max(0.0, 1.0 - 0.05 * len(flags))
    return ERPMethodResult(
        method=method,
        methodology_version=methodology_version,
        erp_decimal=erp_decimal,
        confidence=confidence,
        flags=tuple(flags),
    )


# -----------------------------------------------------------------------------
# Canonical aggregation
# -----------------------------------------------------------------------------


def _compute_canonical(
    method_results: tuple[ERPMethodResult | None, ...],
    *,
    upstream_flags: tuple[str, ...],
    forward_eps_divergence_pct: float | None,
    xval_deviation_bps: int | None,
) -> ERPCanonicalResult:
    """Aggregate per-method rows into canonical median + flags.

    Raises :class:`InsufficientDataError` when available-method count
    falls below :data:`MIN_METHODS_FOR_CANONICAL`.
    """
    available = [r for r in method_results if r is not None]
    if len(available) < MIN_METHODS_FOR_CANONICAL:
        msg = f"ERP canonical requires {MIN_METHODS_FOR_CANONICAL} methods; got {len(available)}"
        raise InsufficientDataError(msg)

    bps_values = [r.erp_bps for r in available]
    erp_median_decimal = float(median(r.erp_decimal for r in available))
    erp_range_bps = max(bps_values) - min(bps_values)

    flags = list(upstream_flags)
    if erp_range_bps > DIVERGENCE_THRESHOLD_BPS:
        flags.append("ERP_METHOD_DIVERGENCE")
    if forward_eps_divergence_pct is not None and (
        forward_eps_divergence_pct > FORWARD_EPS_DIVERGENCE_THRESHOLD
    ):
        flags.append("ERP_SOURCE_DIVERGENCE")
    if xval_deviation_bps is not None and xval_deviation_bps > 20:
        flags.append("XVAL_DRIFT")
    flags = sorted(set(flags))

    # Cap-then-deduct per flags.md §1 propagation rules.
    confidence = min(r.confidence for r in available)
    confidence -= 0.05 * (4 - len(available))
    if "ERP_METHOD_DIVERGENCE" in flags:
        confidence -= 0.10
    if "XVAL_DRIFT" in flags:
        confidence -= 0.10
    confidence = max(0.0, min(1.0, confidence))

    return ERPCanonicalResult(
        methodology_version=METHODOLOGY_VERSION_CANONICAL,
        erp_median_decimal=erp_median_decimal,
        erp_range_bps=erp_range_bps,
        methods_available=len(available),
        confidence=confidence,
        flags=tuple(flags),
        xval_deviation_bps=xval_deviation_bps,
        forward_eps_divergence_pct=forward_eps_divergence_pct,
    )


def _compute_forward_eps_divergence(
    factset_eps: float,
    yardeni_eps: float | None,
    *,
    factset_fresh_days: int | None,
    yardeni_fresh_days: int | None,
) -> float | None:
    """Compute ``|fact - yard| / mean``; return ``None`` when unusable.

    Per spec §4 step 8.5 both sources must be ≤ 7 days fresh. Returns
    ``None`` (caller does not emit the divergence flag) when Yardeni
    is absent or either source is stale.
    """
    if yardeni_eps is None:
        return None
    if factset_fresh_days is None or yardeni_fresh_days is None:
        return None
    if factset_fresh_days > 7 or yardeni_fresh_days > 7:
        return None
    mean_eps = (factset_eps + yardeni_eps) / 2.0
    if mean_eps == 0:
        return None
    return abs(factset_eps - yardeni_eps) / mean_eps


# -----------------------------------------------------------------------------
# Orchestrator
# -----------------------------------------------------------------------------


def fit_erp_us(
    inputs: ERPInput,
    *,
    xval_deviation_bps: int | None = None,
) -> ERPFitResult:
    """Orchestrate all 4 methods + canonical for a single (market, date).

    Preconditions (per spec §2 §Preconditions):

    * ``risk_free_confidence >= 0.50`` → else :class:`InsufficientDataError`.
    * At least :data:`MIN_METHODS_FOR_CANONICAL` methods usable → else
      :class:`InsufficientDataError` inside canonical aggregation.

    ``xval_deviation_bps`` is passed by the pipeline after consulting
    Damodaran histimpl (US only); pass ``None`` for non-US markets.
    """
    if inputs.risk_free_confidence < 0.50:
        msg = (
            f"risk_free_confidence {inputs.risk_free_confidence:.2f} below 0.50 "
            f"minimum for ERP compute ({inputs.market_index}, {inputs.observation_date})"
        )
        raise InsufficientDataError(msg)

    dcf: ERPMethodResult | None
    try:
        dcf = _compute_dcf(inputs)
    except ConvergenceError:  # not actually raised but defended for symmetry
        dcf = None
    gordon = _compute_gordon(inputs)
    ey = _compute_ey(inputs)
    cape = _compute_cape(inputs)

    forward_eps_divergence_pct = _compute_forward_eps_divergence(
        inputs.forward_earnings_est,
        inputs.yardeni_eps,
        factset_fresh_days=inputs.factset_fresh_days,
        yardeni_fresh_days=inputs.yardeni_fresh_days,
    )

    canonical = _compute_canonical(
        (dcf, gordon, ey, cape),
        upstream_flags=inputs.upstream_flags,
        forward_eps_divergence_pct=forward_eps_divergence_pct,
        xval_deviation_bps=xval_deviation_bps,
    )

    method_results: tuple[ERPMethodResult, ...] = tuple(
        r for r in (dcf, gordon, ey, cape) if r is not None
    )
    return ERPFitResult(
        erp_id=uuid4(),
        market_index=inputs.market_index,
        country_code=inputs.country_code,
        observation_date=inputs.observation_date,
        dcf=dcf,
        gordon=gordon,
        ey=ey,
        cape=cape,
        canonical=canonical,
        method_results=method_results,
    )
