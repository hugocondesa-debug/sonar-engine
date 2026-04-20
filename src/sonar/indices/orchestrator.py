"""Orchestrator for L3 indices — compute-all entry point + CLI.

Runs the set of indices currently in production (Week 4 scope: E2
Leading slope subset + M3 Market Expectations anchor subset) for a
given ``(country, date)`` and returns a ``dict[index_code,
IndexResult]``. Any index raising ``InsufficientInputsError`` is
skipped gracefully; the orchestrator never emits a partial
``IndexResult``.

CLI::

    python -m sonar.indices.orchestrator --country US --date 2024-01-02

The CLI path relies on synthetic input bundles (the brief-scoped
variants do not yet read live data from the ORM — that wiring lives in
the pipelines layer once the L3 ORM queries are authored in Phase 2).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date as date_t
from typing import TYPE_CHECKING, Any

import numpy as np

from sonar.indices.economic.e2_leading import E2Inputs, compute_e2_leading_slope
from sonar.indices.exceptions import InsufficientInputsError
from sonar.indices.monetary.m3_market_expectations import (
    M3Inputs,
    compute_m3_market_expectations_anchor,
)

if TYPE_CHECKING:
    from sonar.indices.base import IndexResult

__all__ = [
    "OrchestratorInputs",
    "compute_all_indices",
    "main",
]


@dataclass(frozen=True, slots=True)
class OrchestratorInputs:
    """Inputs bundle for a single ``(country, date)`` run.

    Each sub-dict maps one index to its typed inputs dataclass. Missing
    keys cause the orchestrator to skip that index with a graceful log
    line; the index is absent from the returned dict.
    """

    country_code: str
    observation_date: date_t
    e2: E2Inputs | None = None
    m3: M3Inputs | None = None


def compute_all_indices(inputs: OrchestratorInputs) -> dict[str, IndexResult]:
    """Run every index with matching inputs; skip on insufficient data."""
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


def _synthetic_inputs(country: str, obs_date: date_t) -> OrchestratorInputs:
    """Build synthetic inputs bundle so ``--country X --date Y`` has something
    to compute until the ORM-reading pipeline wiring lands in Phase 2.
    """
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sonar.indices.orchestrator",
        description="Compute all L3 indices for a given (country, date).",
    )
    parser.add_argument("--country", required=True, help="ISO 3166-1 alpha-2 code (e.g. US)")
    parser.add_argument(
        "--date",
        required=True,
        help="Observation date in YYYY-MM-DD format",
    )
    args = parser.parse_args(argv)

    obs_date = date_t.fromisoformat(args.date)
    inputs = _synthetic_inputs(args.country, obs_date)
    results = compute_all_indices(inputs)

    payload = {
        "country": args.country,
        "date": obs_date.isoformat(),
        "indices": [_result_to_json_dict(r) for r in results.values()],
    }
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
