"""Orchestrator for L3 indices — compute-all entry point + CLI.

Runs the set of indices currently in production for a given ``(country,
date)`` and returns results keyed by module. Three tracks supported:

- **E2 / M3** (l3-indices brief): slope-subset + anchor-subset per the
  simplified Week 4 paths. Returns :class:`IndexResult` (polymorphic
  ``index_values`` table).
- **Credit L1/L2/L3/L4** (credit brief v3): CCCS sub-indices backed by
  BIS ``WS_TC`` + ``WS_DSR``. Each returns its own typed result
  dataclass (dedicated tables per migration 009).

CLI::

    python -m sonar.indices.orchestrator --country US --date 2024-01-02
    python -m sonar.indices.orchestrator --country PT --date 2024-12-31 \\
        --credit-only

The CLI path relies on synthetic input bundles (the brief-scoped
variants do not yet read live data from the ORM — that wiring lives in
the pipelines layer; ORM-reading orchestration is CAL-051 + a future
credit-pipeline brief).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date as date_t
from typing import TYPE_CHECKING, Any

import numpy as np

from sonar.indices.credit.l1_credit_gdp_stock import (
    CreditGdpStockInputs,
    CreditGdpStockResult,
    compute_credit_gdp_stock,
)
from sonar.indices.credit.l2_credit_gdp_gap import (
    CreditGdpGapInputs,
    CreditGdpGapResult,
    compute_credit_gdp_gap,
)
from sonar.indices.credit.l3_credit_impulse import (
    CreditImpulseInputs,
    CreditImpulseResult,
    compute_credit_impulse,
)
from sonar.indices.credit.l4_dsr import (
    DsrInputs,
    DsrResult,
    compute_dsr,
)
from sonar.indices.economic.e2_leading import E2Inputs, compute_e2_leading_slope
from sonar.indices.exceptions import InsufficientInputsError
from sonar.indices.monetary.m3_market_expectations import (
    M3Inputs,
    compute_m3_market_expectations_anchor,
)

if TYPE_CHECKING:
    from sonar.indices.base import IndexResult

__all__ = [
    "CreditIndicesInputs",
    "CreditIndicesResults",
    "OrchestratorInputs",
    "compute_all_credit_indices",
    "compute_all_indices",
    "main",
]


@dataclass(frozen=True, slots=True)
class OrchestratorInputs:
    """Inputs bundle for the polymorphic E2 / M3 indices track."""

    country_code: str
    observation_date: date_t
    e2: E2Inputs | None = None
    m3: M3Inputs | None = None


@dataclass(frozen=True, slots=True)
class CreditIndicesInputs:
    """Inputs bundle for the credit L1-L4 CCCS track.

    Each sub-index is optional; the orchestrator skips any index whose
    input bundle is absent. Integration tests typically wire all four
    from a single BIS connector pass.
    """

    country_code: str
    observation_date: date_t
    l1: CreditGdpStockInputs | None = None
    l2: CreditGdpGapInputs | None = None
    l3: CreditImpulseInputs | None = None
    l4: DsrInputs | None = None


@dataclass(frozen=True, slots=True)
class CreditIndicesResults:
    """Outputs bundle — one field per credit sub-index (None if skipped)."""

    country_code: str
    observation_date: date_t
    l1: CreditGdpStockResult | None = None
    l2: CreditGdpGapResult | None = None
    l3: CreditImpulseResult | None = None
    l4: DsrResult | None = None
    skips: dict[str, str] = None  # type: ignore[assignment]

    def available(self) -> list[str]:
        """List of sub-indices that successfully computed."""
        names: list[str] = []
        for name in ("l1", "l2", "l3", "l4"):
            if getattr(self, name) is not None:
                names.append(name)
        return names


def compute_all_indices(inputs: OrchestratorInputs) -> dict[str, IndexResult]:
    """Run E2 / M3 tracks; skip gracefully on insufficient inputs."""
    results: dict[str, IndexResult] = {}

    if inputs.e2 is not None:
        try:
            r = compute_e2_leading_slope(inputs.e2)
            results[r.index_code] = r
        except InsufficientInputsError:
            pass

    if inputs.m3 is not None:
        try:
            r = compute_m3_market_expectations_anchor(inputs.m3)
            results[r.index_code] = r
        except InsufficientInputsError:
            pass

    return results


def compute_all_credit_indices(inputs: CreditIndicesInputs) -> CreditIndicesResults:
    """Run L1 -> L2 -> L3 -> L4 (L2/L3 depend on L1); skip gracefully.

    Skip reasons are recorded in the returned ``skips`` dict so callers
    can distinguish missing-inputs from failed-compute vs. degraded
    data. The orchestrator never raises ``InsufficientInputsError`` on
    its own — it downgrades into a skip.
    """
    skips: dict[str, str] = {}
    l1_result: CreditGdpStockResult | None = None
    l2_result: CreditGdpGapResult | None = None
    l3_result: CreditImpulseResult | None = None
    l4_result: DsrResult | None = None

    if inputs.l1 is not None:
        try:
            l1_result = compute_credit_gdp_stock(inputs.l1)
        except InsufficientInputsError as e:
            skips["l1"] = str(e)
    else:
        skips["l1"] = "no inputs provided"

    if inputs.l2 is not None:
        try:
            l2_result = compute_credit_gdp_gap(inputs.l2)
        except InsufficientInputsError as e:
            skips["l2"] = str(e)
    else:
        skips["l2"] = "no inputs provided"

    if inputs.l3 is not None:
        try:
            l3_result = compute_credit_impulse(inputs.l3)
        except InsufficientInputsError as e:
            skips["l3"] = str(e)
    else:
        skips["l3"] = "no inputs provided"

    if inputs.l4 is not None:
        try:
            l4_result = compute_dsr(inputs.l4)
        except (InsufficientInputsError, ValueError) as e:
            skips["l4"] = str(e)
    else:
        skips["l4"] = "no inputs provided"

    return CreditIndicesResults(
        country_code=inputs.country_code,
        observation_date=inputs.observation_date,
        l1=l1_result,
        l2=l2_result,
        l3=l3_result,
        l4=l4_result,
        skips=skips,
    )


def _synthetic_inputs(country: str, obs_date: date_t) -> OrchestratorInputs:
    rng = np.random.default_rng(seed=hash((country, obs_date.isoformat())) % (2**32))
    slope_hist = rng.normal(60.0, 40.0, size=1260).tolist()
    fwd_hist = rng.normal(-20.0, 30.0, size=1260).tolist()
    e2 = E2Inputs(
        country_code=country,
        observation_date=obs_date,
        spot_2y_bps=433.0,
        spot_10y_bps=395.0,
        forward_2y1y_bps=380.0,
        slope_history_bps=slope_hist,
        forward_spread_history_bps=fwd_hist,
        nss_confidence=0.85,
    )
    nominal_hist = rng.normal(300.0, 50.0, size=1260).tolist()
    anchor_hist = [abs(x) for x in rng.normal(25.0, 20.0, size=1260).tolist()]
    bei_div_hist = [abs(x) for x in rng.normal(10.0, 15.0, size=1260).tolist()]
    m3 = M3Inputs(
        country_code=country,
        observation_date=obs_date,
        nominal_5y5y_bps=385.0,
        breakeven_5y5y_bps=254.0,
        bc_target_bps=200.0,
        bei_10y_bps=227.0,
        survey_10y_bps=248.0,
        nominal_5y5y_history_bps=nominal_hist,
        anchor_deviation_abs_history_bps=anchor_hist,
        bei_survey_div_abs_history_bps=bei_div_hist,
        expinf_confidence=0.85,
    )
    return OrchestratorInputs(
        country_code=country,
        observation_date=obs_date,
        e2=e2,
        m3=m3,
    )


def _synthetic_credit_inputs(country: str, obs_date: date_t) -> CreditIndicesInputs:
    """Build synthetic credit inputs for the CLI path.

    Generates 80 quarters (20Y) of credit stock + GDP + DSR history so
    all four sub-indices compute without raising.
    """
    rng = np.random.default_rng(seed=hash((country, "credit", obs_date.isoformat())) % (2**32))
    credit_hist = (1000.0 * (1.015 ** np.arange(80))) + rng.normal(0, 3, 80)
    gdp_hist = (500.0 * (1.010 ** np.arange(80))) + rng.normal(0, 1, 80)
    ratio_hist = (credit_hist / gdp_hist * 100.0).tolist()

    l1 = CreditGdpStockInputs(
        country_code=country,
        observation_date=obs_date,
        ratio_pct=ratio_hist[-1],
        ratio_pct_history=ratio_hist,
    )
    l2 = CreditGdpGapInputs(
        country_code=country,
        observation_date=obs_date,
        ratio_pct_history=ratio_hist,
    )
    l3 = CreditImpulseInputs(
        country_code=country,
        observation_date=obs_date,
        credit_stock_lcu_history=credit_hist.tolist(),
        gdp_nominal_lcu_history=gdp_hist.tolist(),
    )
    dsr_hist = (rng.normal(13.0, 1.5, 80)).tolist()
    l4 = DsrInputs(
        country_code=country,
        observation_date=obs_date,
        lending_rate_pct=0.035,
        avg_maturity_years=15.0,
        debt_to_gdp_ratio=ratio_hist[-1] / 100.0,
        dsr_pct_history=dsr_hist,
    )
    return CreditIndicesInputs(
        country_code=country,
        observation_date=obs_date,
        l1=l1,
        l2=l2,
        l3=l3,
        l4=l4,
    )


def _result_to_json_dict(r: IndexResult) -> dict[str, Any]:
    return {
        "index_code": r.index_code,
        "country_code": r.country_code,
        "date": r.date.isoformat(),
        "methodology_version": r.methodology_version,
        "raw_value": r.raw_value,
        "zscore_clamped": r.zscore_clamped,
        "value_0_100": r.value_0_100,
        "confidence": r.confidence,
        "flags": list(r.flags),
    }


def _credit_results_to_json(results: CreditIndicesResults) -> dict[str, Any]:
    def _row(
        name: str,
        r: CreditGdpStockResult | CreditGdpGapResult | CreditImpulseResult | DsrResult | None,
    ) -> dict[str, Any] | None:
        if r is None:
            return None
        return {
            "index_code": name.upper(),
            "methodology_version": r.methodology_version,
            "score_normalized": r.score_normalized,
            "score_raw": r.score_raw,
            "confidence": r.confidence,
            "flags": list(r.flags),
        }

    return {
        "country": results.country_code,
        "date": results.observation_date.isoformat(),
        "credit_indices": {
            "l1": _row("l1", results.l1),
            "l2": _row("l2", results.l2),
            "l3": _row("l3", results.l3),
            "l4": _row("l4", results.l4),
        },
        "skips": results.skips or {},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sonar.indices.orchestrator",
        description="Compute all L3 indices for a given (country, date).",
    )
    parser.add_argument("--country", required=True, help="ISO 3166-1 alpha-2 code")
    parser.add_argument("--date", required=True, help="Observation date YYYY-MM-DD")
    parser.add_argument(
        "--credit-only",
        action="store_true",
        help="Run only the credit L1-L4 track (skip E2 / M3).",
    )
    args = parser.parse_args(argv)

    obs_date = date_t.fromisoformat(args.date)

    if args.credit_only:
        credit_inputs = _synthetic_credit_inputs(args.country, obs_date)
        credit_results = compute_all_credit_indices(credit_inputs)
        payload = _credit_results_to_json(credit_results)
    else:
        inputs = _synthetic_inputs(args.country, obs_date)
        results = compute_all_indices(inputs)
        credit_inputs = _synthetic_credit_inputs(args.country, obs_date)
        credit_results = compute_all_credit_indices(credit_inputs)
        payload = {
            "country": args.country,
            "date": obs_date.isoformat(),
            "indices": [_result_to_json_dict(r) for r in results.values()],
            "credit_indices": _credit_results_to_json(credit_results)["credit_indices"],
        }

    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
