"""L4 Debt Service Ratio (DSR) per ``L4_DSR_v0.1`` — Drehmann-Juselius 2015.

Full spec: ``docs/specs/indices/credit/L4-dsr.md``. Independent of
L1/L2/L3 (takes debt-to-GDP + lending rate + maturity as separate
inputs; does not consume credit stock from L1).

Key design choices per spec §4:
- Three formula modes (``full``/``o2``/``o1``) resolved from data
  availability; BIS ``WS_DSR`` 32-country universe gets ``full``.
- For BIS-direct countries, the module accepts an optional
  ``bis_published_dsr_pct`` and emits ``DSR_BIS_DIVERGE`` when the
  internally-computed DSR differs by more than 1pp.
- Historical 20Y baseline: z-score over rolling ``dsr_pct`` history
  of the same country + formula_mode. Callers supply the history.
- Band classification from ``dsr_deviation_pp`` per spec §4 step 8:
  ``baseline`` (< +2), ``alert`` (+2..+6), ``critical`` (>= +6).
  Thresholds are placeholders per spec §11 — recalibrate after 5Y
  of production data (see CAL-018).

Consumed by ``cycles/credit-cccs`` (L4) with ~55% within BP sub-index
plus an additional 25% interest-burden input (spec README.md §CCCS
preview).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

import numpy as np

from sonar.indices._helpers.annuity import AnnuityFormulaMode, annuity_factor
from sonar.indices.exceptions import InsufficientInputsError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date as date_t

__all__ = [
    "BAND_ALERT_DEVIATION_PP",
    "BAND_CRITICAL_DEVIATION_PP",
    "BIS_DIVERGE_THRESHOLD_PP",
    "METHODOLOGY_VERSION",
    "MIN_HISTORY_QUARTERS",
    "SEGMENT_PNFS",
    "DsrBand",
    "DsrInputs",
    "DsrResult",
    "DsrSegment",
    "compute_dsr",
    "compute_dsr_pct",
    "resolve_band",
    "resolve_formula_mode",
]

METHODOLOGY_VERSION: str = "L4_DSR_v0.1"

MIN_HISTORY_QUARTERS: int = 60  # 15Y hard floor per spec §6 + README §lookback

BAND_ALERT_DEVIATION_PP: float = 2.0
BAND_CRITICAL_DEVIATION_PP: float = 6.0
BIS_DIVERGE_THRESHOLD_PP: float = 1.0

DsrSegment = Literal["PNFS", "HH", "NFC"]
DsrBand = Literal["baseline", "alert", "critical"]
SEGMENT_PNFS: DsrSegment = "PNFS"

# BIS WS_DSR 32-country universe per spec §2 coverage table (Q1 2026 release).
BIS_WS_DSR_UNIVERSE: frozenset[str] = frozenset(
    {
        "AT",
        "AU",
        "BE",
        "BR",
        "CA",
        "CH",
        "CN",
        "CZ",
        "DE",
        "DK",
        "ES",
        "FI",
        "FR",
        "GB",
        "GR",
        "HU",
        "ID",
        "IE",
        "IN",
        "IT",
        "JP",
        "KR",
        "MX",
        "NL",
        "NO",
        "PL",
        "PT",
        "RU",
        "SE",
        "TR",
        "US",
        "ZA",
    }
)


@dataclass(frozen=True, slots=True)
class DsrInputs:
    """Per-quarter DSR inputs + 20Y history for z-score baseline."""

    country_code: str
    observation_date: date_t
    lending_rate_pct: float  # decimal, e.g. 0.0345
    avg_maturity_years: float | None
    debt_to_gdp_ratio: float  # decimal, e.g. 1.45
    dsr_pct_history: Sequence[float]  # rolling 20Y quarterly, most-recent-last
    segment: DsrSegment = SEGMENT_PNFS
    denominator: str = "GDP_4Q_sum"
    bis_published_dsr_pct: float | None = None
    upstream_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class DsrResult:
    """Canonical L4 DSR output contract — mirrors ``dsr`` table schema."""

    country_code: str
    date: date_t
    methodology_version: str
    segment: DsrSegment
    score_normalized: float  # z-score clamped [-5, +5]
    score_raw: float  # == dsr_pct
    dsr_pct: float
    dsr_deviation_pp: float
    lending_rate_pct: float
    avg_maturity_years: float
    debt_to_gdp_ratio: float
    annuity_factor: float
    formula_mode: AnnuityFormulaMode
    band: DsrBand
    denominator: str
    components_json: str
    lookback_years: int
    confidence: float
    flags: tuple[str, ...]
    source_connector: str


def resolve_formula_mode(
    country_code: str,
    *,
    has_lending_rate: bool,
    has_maturity: bool,
    has_debt_to_gdp: bool,
) -> AnnuityFormulaMode:
    """Resolve formula mode per spec §4 step 1."""
    if not has_lending_rate or not has_debt_to_gdp:
        err = "DSR requires lending_rate + debt_to_gdp at minimum"
        raise InsufficientInputsError(err)
    if country_code in BIS_WS_DSR_UNIVERSE and has_maturity:
        return "full"
    if has_maturity:
        return "o2"
    return "o1"


def compute_dsr_pct(
    lending_rate_pct: float,
    avg_maturity_years: float | None,
    debt_to_gdp_ratio: float,
    mode: AnnuityFormulaMode,
) -> tuple[float, float]:
    """Return ``(annuity_factor, dsr_pct)`` for the selected mode."""
    af = annuity_factor(lending_rate_pct, avg_maturity_years, mode)
    dsr_pct = af * debt_to_gdp_ratio * 100.0
    return af, dsr_pct


def resolve_band(deviation_pp: float) -> DsrBand:
    """Classify band per spec §4 step 8 placeholder thresholds."""
    if deviation_pp >= BAND_CRITICAL_DEVIATION_PP:
        return "critical"
    if deviation_pp >= BAND_ALERT_DEVIATION_PP:
        return "alert"
    return "baseline"


def _z_clamp_5(z: float) -> float:
    if math.isnan(z):
        return 0.0
    return max(-5.0, min(5.0, z))


def _confidence_from_flags(flags: tuple[str, ...]) -> float:
    """Apply flags.md deduction/cap rules; baseline starts at 1.0."""
    conf = 1.0
    if "DSR_APPROX_O1" in flags:
        conf -= 0.20
    if "DSR_APPROX_O2" in flags:
        conf -= 0.10
    if "DSR_BIS_DIVERGE" in flags:
        conf -= 0.10
    if "DSR_NEG_RATE" in flags:
        conf -= 0.05
    if "DSR_DENOMINATOR_GDP" in flags:
        conf -= 0.10
    if "INSUFFICIENT_HISTORY" in flags:
        conf = min(conf, 0.65)
    if "CALIBRATION_STALE" in flags:
        conf -= 0.15
    return max(0.0, min(1.0, conf))


def compute_dsr(
    inputs: DsrInputs,
    *,
    source_connector: str = "bis_ws_dsr",
) -> DsrResult:
    """Compute L4 DSR for a given ``(country, date, segment)``."""
    if inputs.debt_to_gdp_ratio <= 0.0:
        err = f"debt_to_gdp_ratio must be positive, got {inputs.debt_to_gdp_ratio}"
        raise InsufficientInputsError(err)
    if len(inputs.dsr_pct_history) < 2:
        raise InsufficientInputsError("dsr history too short for z-score baseline")

    flags: list[str] = list(inputs.upstream_flags)

    mode = resolve_formula_mode(
        inputs.country_code,
        has_lending_rate=True,
        has_maturity=inputs.avg_maturity_years is not None,
        has_debt_to_gdp=True,
    )

    if mode == "o1":
        flags.append("DSR_APPROX_O1")
    elif mode == "o2":
        flags.append("DSR_APPROX_O2")

    if inputs.lending_rate_pct < 0.0:
        flags.append("DSR_NEG_RATE")

    maturity = inputs.avg_maturity_years if inputs.avg_maturity_years is not None else float("nan")

    af, dsr_pct = compute_dsr_pct(
        inputs.lending_rate_pct,
        inputs.avg_maturity_years,
        inputs.debt_to_gdp_ratio,
        mode,
    )

    if inputs.bis_published_dsr_pct is not None:
        diverge = abs(dsr_pct - inputs.bis_published_dsr_pct)
        if diverge > BIS_DIVERGE_THRESHOLD_PP:
            flags.append("DSR_BIS_DIVERGE")

    hist = np.asarray(inputs.dsr_pct_history, dtype=float)
    mu = float(hist.mean())
    sigma = float(hist.std(ddof=1))
    if len(inputs.dsr_pct_history) < MIN_HISTORY_QUARTERS:
        flags.append("INSUFFICIENT_HISTORY")

    if inputs.segment == "HH" and inputs.denominator == "GDP_4Q_sum":
        flags.append("DSR_DENOMINATOR_GDP")

    dsr_deviation_pp = dsr_pct - mu
    z_raw = (dsr_pct - mu) / sigma if sigma > 1e-12 else 0.0
    score_normalized = _z_clamp_5(z_raw)
    band = resolve_band(dsr_deviation_pp)
    confidence = _confidence_from_flags(tuple(flags))

    lookback_years = max(1, len(inputs.dsr_pct_history) // 4)

    interest_burden_pct = inputs.lending_rate_pct * inputs.debt_to_gdp_ratio * 100.0
    amort_burden_pct = max(0.0, dsr_pct - interest_burden_pct)
    components = {
        "lending_rate_pct": inputs.lending_rate_pct,
        "avg_maturity_years": (
            None if inputs.avg_maturity_years is None else inputs.avg_maturity_years
        ),
        "debt_to_gdp_ratio": inputs.debt_to_gdp_ratio,
        "annuity_factor": af,
        "interest_burden_pct": interest_burden_pct,
        "amort_burden_pct": amort_burden_pct,
        "dsr_pct": dsr_pct,
        "dsr_mean_20y_pct": mu,
        "dsr_deviation_pp": dsr_deviation_pp,
        "formula_mode": mode,
        "segment": inputs.segment,
        "denominator": inputs.denominator,
        "bis_published_dsr_pct": inputs.bis_published_dsr_pct,
    }

    return DsrResult(
        country_code=inputs.country_code,
        date=inputs.observation_date,
        methodology_version=METHODOLOGY_VERSION,
        segment=inputs.segment,
        score_normalized=score_normalized,
        score_raw=dsr_pct,
        dsr_pct=dsr_pct,
        dsr_deviation_pp=dsr_deviation_pp,
        lending_rate_pct=inputs.lending_rate_pct,
        avg_maturity_years=maturity,
        debt_to_gdp_ratio=inputs.debt_to_gdp_ratio,
        annuity_factor=af,
        formula_mode=mode,
        band=band,
        denominator=inputs.denominator,
        components_json=json.dumps(components),
        lookback_years=lookback_years,
        confidence=confidence,
        flags=tuple(sorted(set(flags))),
        source_connector=source_connector,
    )
