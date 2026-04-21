"""Country Risk Premium overlay (L2) — Week 3 minimal scope.

Spec: docs/specs/overlays/crp.md (post-sweep)
Methodology versions:
  - CDS:        ``CRP_CDS_v0.1`` (not implemented Week 3 — WGB connector pending CAL)
  - SOV_SPREAD: ``CRP_SOV_SPREAD_v0.1``
  - RATING:     ``CRP_RATING_v0.1``
  - CANONICAL:  ``CRP_CANONICAL_v0.1``

Week 3 scope: SOV_SPREAD (PT/IT/ES/FR/NL vs Bund) + RATING (T1 fallback)
+ BENCHMARK shortcut (DE/US → crp=0). CDS branch deferred until WGB
connector validates (CAL).

vol_ratio defaults to ``DAMODARAN_STANDARD_RATIO = 1.5`` per CAL-040 —
country-specific ratios unblock when twelvedata/yfinance validate.

Storage convention per units.md §Spreads: per-method `*_bps` is INTEGER
(rounded display); per-method `crp_decimal` is REAL (source of truth
for recomputation). Compute internally in decimal; round only at the
persistence boundary.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

import structlog

from sonar.overlays.exceptions import InsufficientDataError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date as date_type
    from uuid import UUID

    from sonar.connectors.base import Observation
    from sonar.connectors.fmp import FMPPriceObservation

log = structlog.get_logger()

__all__ = [
    "BENCHMARK_COUNTRIES_BY_CURRENCY",
    "DAMODARAN_STANDARD_RATIO",
    "METHODOLOGY_VERSION_CANONICAL",
    "METHODOLOGY_VERSION_RATING",
    "METHODOLOGY_VERSION_SOV_SPREAD",
    "MIN_VOL_OBSERVATIONS",
    "VOL_RATIO_BOUNDS",
    "CRPCanonical",
    "CRPRating",
    "CRPSovSpread",
    "Method",
    "VolRatioResult",
    "build_canonical",
    "compute_rating",
    "compute_sov_spread",
    "compute_vol_ratio",
    "is_benchmark",
]

METHODOLOGY_VERSION_CDS: str = "CRP_CDS_v0.1"
METHODOLOGY_VERSION_SOV_SPREAD: str = "CRP_SOV_SPREAD_v0.1"
METHODOLOGY_VERSION_RATING: str = "CRP_RATING_v0.1"
METHODOLOGY_VERSION_CANONICAL: str = "CRP_CANONICAL_v0.1"

# CAL-040 interim: Damodaran standard 1.5 for all countries until
# twelvedata/yfinance country-specific vol_ratio validates.
DAMODARAN_STANDARD_RATIO: float = 1.5

# Benchmark countries for the EUR / USD / GBP / JPY worlds. CRP for the
# benchmark is 0 by construction; consumers compose CRP = 0 + benchmark
# risk premia upstream.
BENCHMARK_COUNTRIES_BY_CURRENCY: dict[str, str] = {
    "EUR": "DE",
    "USD": "US",
    "GBP": "GB",
    "JPY": "JP",
}

# ADR-0007 deprecated country aliases — preserved during CAL-128-FOLLOWUP
# transition window. Removal scheduled Week 10 Day 1
# (deprecation_target="CAL-128-alias-removal-week10").
_DEPRECATED_COUNTRY_ALIASES: dict[str, str] = {"UK": "GB"}

Method = Literal["CDS", "SOV_SPREAD", "RATING", "BENCHMARK"]
HIERARCHY: tuple[Method, ...] = ("CDS", "SOV_SPREAD", "RATING")
MIN_CONFIDENCE_METHOD: float = 0.50

# Spec §2 + §4 vol_ratio bounds: country-specific ratio must fall inside
# this range, else fall back to Damodaran 1.5.
VOL_RATIO_BOUNDS: tuple[float, float] = (1.2, 2.5)
MIN_VOL_OBSERVATIONS: int = 750  # ~3Y daily
TRADING_DAYS_PER_YEAR: float = 252.0


@dataclass(frozen=True, slots=True)
class VolRatioResult:
    """Output of ``compute_vol_ratio``."""

    vol_ratio: float
    source: str  # "country_specific" | "damodaran_standard"
    equity_obs: int
    bond_obs: int
    sigma_equity: float | None
    sigma_bond: float | None


def _daily_returns(closes: Sequence[float]) -> list[float]:
    """log-returns (preferred for volatility math)."""
    out: list[float] = []
    prev = closes[0] if closes else 0.0
    for c in closes[1:]:
        if prev <= 0 or c <= 0:
            prev = c
            continue
        out.append(math.log(c / prev))
        prev = c
    return out


def _std_dev(series: Sequence[float]) -> float:
    n = len(series)
    if n < 2:
        return 0.0
    mean = sum(series) / n
    var = sum((x - mean) ** 2 for x in series) / (n - 1)
    return math.sqrt(var)


def compute_vol_ratio(
    equity_prices: Sequence[FMPPriceObservation],
    bond_yields: Sequence[Observation],
) -> VolRatioResult:
    """sigma_equity / sigma_bond over the intersection of the two series.

    Equity volatility from FMP closes -> log daily returns -> std *
    sqrt(252). Bond volatility from TE yield daily changes (absolute
    diffs in yield_bps, not returns — yield changes are the standard
    bond-vol proxy per spec §4).

    Falls back to ``damodaran_standard_ratio = 1.5`` when:
    - Either series has fewer than MIN_VOL_OBSERVATIONS = 750 rows
    - Computed ratio is outside ``VOL_RATIO_BOUNDS = (1.2, 2.5)``
    - Either sigma is non-positive (degenerate input)

    Returns the ``VolRatioResult`` — caller consults ``.source`` to
    decide whether to emit ``CRP_VOL_STANDARD`` flag.
    """
    eq_closes = [float(o.close) for o in equity_prices]
    eq_returns = _daily_returns(eq_closes)
    eq_obs = len(eq_returns)

    # Bond returns proxy: daily yield changes in decimal (yield_bps / 10000)
    bond_decimal = [o.yield_bps / 10_000.0 for o in bond_yields]
    bond_changes = [bond_decimal[i] - bond_decimal[i - 1] for i in range(1, len(bond_decimal))]
    bond_obs = len(bond_changes)

    if eq_obs < MIN_VOL_OBSERVATIONS or bond_obs < MIN_VOL_OBSERVATIONS:
        return VolRatioResult(
            vol_ratio=DAMODARAN_STANDARD_RATIO,
            source="damodaran_standard",
            equity_obs=eq_obs,
            bond_obs=bond_obs,
            sigma_equity=None,
            sigma_bond=None,
        )

    sigma_eq = _std_dev(eq_returns) * math.sqrt(TRADING_DAYS_PER_YEAR)
    sigma_bond = _std_dev(bond_changes) * math.sqrt(TRADING_DAYS_PER_YEAR)
    if sigma_bond <= 0.0 or sigma_eq <= 0.0:
        return VolRatioResult(
            vol_ratio=DAMODARAN_STANDARD_RATIO,
            source="damodaran_standard",
            equity_obs=eq_obs,
            bond_obs=bond_obs,
            sigma_equity=sigma_eq,
            sigma_bond=sigma_bond,
        )

    ratio = sigma_eq / sigma_bond
    lo, hi = VOL_RATIO_BOUNDS
    if ratio < lo or ratio > hi:
        return VolRatioResult(
            vol_ratio=DAMODARAN_STANDARD_RATIO,
            source="damodaran_standard",
            equity_obs=eq_obs,
            bond_obs=bond_obs,
            sigma_equity=sigma_eq,
            sigma_bond=sigma_bond,
        )

    return VolRatioResult(
        vol_ratio=ratio,
        source="country_specific",
        equity_obs=eq_obs,
        bond_obs=bond_obs,
        sigma_equity=sigma_eq,
        sigma_bond=sigma_bond,
    )


def _normalize_country_code(country_code: str) -> str:
    """Normalise deprecated ISO aliases to canonical codes (ADR-0007).

    Emits a structlog deprecation warning when an alias is resolved. Canonical
    codes are returned unchanged. Removal scheduled Week 10 Day 1.
    """
    canonical = _DEPRECATED_COUNTRY_ALIASES.get(country_code)
    if canonical is None:
        return country_code
    log.warning(
        "crp.deprecated_country_alias",
        alias=country_code,
        canonical=canonical,
        adr="ADR-0007",
        deprecation_target="CAL-128-alias-removal-week10",
    )
    return canonical


def is_benchmark(country_code: str, currency: str = "EUR") -> bool:
    """``True`` if the country is the benchmark for its currency block.

    Deprecated ISO aliases (e.g. "UK") are normalised to canonical ("GB")
    before comparison and emit a structlog deprecation warning. Removal
    Week 10 Day 1 per ADR-0007.
    """
    normalized = _normalize_country_code(country_code)
    return BENCHMARK_COUNTRIES_BY_CURRENCY.get(currency) == normalized


# ---------------------------------------------------------------------------
# Method dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CRPSovSpread:
    """SOV_SPREAD method row (one per country-date)."""

    country_code: str
    observation_date: date_type
    sov_yield_country_pct: float
    sov_yield_benchmark_pct: float
    tenor: str
    default_spread_bps: int
    crp_decimal: float
    crp_bps: int
    currency_denomination: str
    vol_ratio: float
    vol_ratio_source: str
    confidence: float
    flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CRPRating:
    """RATING method row consuming `ratings_consolidated`."""

    country_code: str
    observation_date: date_type
    consolidated_sonar_notch: float
    notch_int: int
    calibration_date: date_type
    default_spread_bps: int
    crp_decimal: float
    crp_bps: int
    rating_id: str
    vol_ratio: float
    vol_ratio_source: str
    confidence: float
    flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CRPCanonical:
    """Canonical row — first-available method per hierarchy."""

    crp_id: UUID
    country_code: str
    observation_date: date_type
    method_selected: Method
    crp_canonical_bps: int
    default_spread_bps: int
    vol_ratio: float
    vol_ratio_source: str
    crp_cds_bps: int | None
    crp_sov_spread_bps: int | None
    crp_rating_bps: int | None
    basis_default_spread_sov_minus_cds_bps: int | None
    confidence: float
    flags: tuple[str, ...]


# ---------------------------------------------------------------------------
# Method computers
# ---------------------------------------------------------------------------


def compute_sov_spread(
    *,
    country_code: str,
    observation_date: date_type,
    sov_yield_country_pct: float,
    sov_yield_benchmark_pct: float,
    tenor: str = "10Y",
    currency_denomination: str = "EUR",
    vol_ratio: float = DAMODARAN_STANDARD_RATIO,
    vol_ratio_source: str = "damodaran_standard",
) -> CRPSovSpread:
    """SOV_SPREAD method: country yield - benchmark yield, scaled by vol_ratio.

    Negative spread (arbitrage / quote noise) is clamped to 0 with the
    ``CRP_NEG_SPREAD`` flag. Inputs are decimal yields.
    """
    flags: list[str] = []
    raw_spread_decimal = sov_yield_country_pct - sov_yield_benchmark_pct
    if raw_spread_decimal < 0:
        raw_spread_decimal = 0.0
        flags.append("CRP_NEG_SPREAD")
    if vol_ratio_source == "damodaran_standard":
        flags.append("CRP_VOL_STANDARD")

    default_spread_bps = round(raw_spread_decimal * 10_000.0)
    crp_decimal = raw_spread_decimal * vol_ratio
    crp_bps = round(crp_decimal * 10_000.0)

    confidence = _compute_confidence(flags)
    return CRPSovSpread(
        country_code=country_code,
        observation_date=observation_date,
        sov_yield_country_pct=sov_yield_country_pct,
        sov_yield_benchmark_pct=sov_yield_benchmark_pct,
        tenor=tenor,
        default_spread_bps=default_spread_bps,
        crp_decimal=crp_decimal,
        crp_bps=crp_bps,
        currency_denomination=currency_denomination,
        vol_ratio=vol_ratio,
        vol_ratio_source=vol_ratio_source,
        confidence=confidence,
        flags=tuple(flags),
    )


def compute_rating(
    *,
    country_code: str,
    observation_date: date_type,
    consolidated_sonar_notch: float,
    default_spread_bps: int,
    rating_id: str,
    calibration_date: date_type,
    vol_ratio: float = DAMODARAN_STANDARD_RATIO,
    vol_ratio_source: str = "damodaran_standard",
) -> CRPRating:
    """RATING method: take `ratings_consolidated.default_spread_bps` and scale
    by ``vol_ratio``. Caller resolves the notch lookup; this function only
    multiplies + rounds + flags.
    """
    notch_int = round(consolidated_sonar_notch)
    flags: list[str] = []
    if vol_ratio_source == "damodaran_standard":
        flags.append("CRP_VOL_STANDARD")

    crp_decimal = (default_spread_bps / 10_000.0) * vol_ratio
    crp_bps = round(crp_decimal * 10_000.0)
    confidence = _compute_confidence(flags)

    return CRPRating(
        country_code=country_code,
        observation_date=observation_date,
        consolidated_sonar_notch=consolidated_sonar_notch,
        notch_int=notch_int,
        calibration_date=calibration_date,
        default_spread_bps=default_spread_bps,
        crp_decimal=crp_decimal,
        crp_bps=crp_bps,
        rating_id=rating_id,
        vol_ratio=vol_ratio,
        vol_ratio_source=vol_ratio_source,
        confidence=confidence,
        flags=tuple(flags),
    )


# ---------------------------------------------------------------------------
# Canonical
# ---------------------------------------------------------------------------


def _compute_confidence(flags: list[str]) -> float:
    base = 1.0
    deduction = 0.0
    cap = 1.0
    if "CRP_DISTRESS" in flags:
        cap = min(cap, 0.60)
    if "CRP_NEG_SPREAD" in flags:
        deduction += 0.10
    if "CRP_BOND_CDS_BASIS" in flags:
        deduction += 0.05
    if "CRP_VOL_STANDARD" in flags:
        deduction += 0.05
    if "LOCAL_CCY_SPREAD" in flags:
        deduction += 0.15
    return float(max(0.0, min(cap, base - deduction)))


def build_canonical(
    *,
    country_code: str,
    observation_date: date_type,
    sov_spread: CRPSovSpread | None = None,
    rating: CRPRating | None = None,
    currency: str = "EUR",
) -> CRPCanonical:
    """Hierarchy picker (CDS > SOV_SPREAD > RATING) + benchmark shortcut.

    Raises:
        InsufficientDataError: when no method available (and country is
            not a benchmark for its currency).
    """
    if is_benchmark(country_code, currency):
        return CRPCanonical(
            crp_id=uuid4(),
            country_code=country_code,
            observation_date=observation_date,
            method_selected="BENCHMARK",
            crp_canonical_bps=0,
            default_spread_bps=0,
            vol_ratio=1.0,
            vol_ratio_source="benchmark",
            crp_cds_bps=None,
            crp_sov_spread_bps=None,
            crp_rating_bps=None,
            basis_default_spread_sov_minus_cds_bps=None,
            confidence=1.0,
            flags=("CRP_BENCHMARK",),
        )

    candidates: dict[Method, tuple[int, int, float, float, str, list[str]]] = {}
    if sov_spread is not None and sov_spread.confidence >= MIN_CONFIDENCE_METHOD:
        candidates["SOV_SPREAD"] = (
            sov_spread.crp_bps,
            sov_spread.default_spread_bps,
            sov_spread.vol_ratio,
            sov_spread.confidence,
            sov_spread.vol_ratio_source,
            list(sov_spread.flags),
        )
    if rating is not None and rating.confidence >= MIN_CONFIDENCE_METHOD:
        candidates["RATING"] = (
            rating.crp_bps,
            rating.default_spread_bps,
            rating.vol_ratio,
            rating.confidence,
            rating.vol_ratio_source,
            list(rating.flags),
        )

    selected: Method | None = None
    for method in HIERARCHY:
        if method in candidates:
            selected = method
            break
    if selected is None:
        msg = (
            f"CRP build_canonical: no method available for "
            f"country={country_code} on {observation_date}"
        )
        raise InsufficientDataError(msg)

    crp_bps, default_spread_bps, vol_ratio, base_conf, vol_src, method_flags = candidates[selected]

    return CRPCanonical(
        crp_id=uuid4(),
        country_code=country_code,
        observation_date=observation_date,
        method_selected=selected,
        crp_canonical_bps=crp_bps,
        default_spread_bps=default_spread_bps,
        vol_ratio=vol_ratio,
        vol_ratio_source=vol_src,
        crp_cds_bps=None,
        crp_sov_spread_bps=sov_spread.crp_bps if sov_spread is not None else None,
        crp_rating_bps=rating.crp_bps if rating is not None else None,
        basis_default_spread_sov_minus_cds_bps=None,
        confidence=base_conf,
        flags=tuple(method_flags),
    )
