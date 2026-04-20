"""Monetary indices live smoke — M1/M2/M4 US + M1 EA (week6 sprint 2b C5).

Per brief §Commit 5: prove that MonetaryInputsBuilder + compute_m1/m2/m4
run end-to-end against live FRED + ECB SDW + CBO feeds and produce
score_normalized in ``[0, 100]`` with methodology_version tags intact.

Runs only under ``pytest -m slow`` so default CI stays fast + network-
independent. All four canaries skip (not xfail) when FRED_API_KEY
isn't exported — that way local devs without secrets don't see
failures.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from sonar.connectors.cbo import CboConnector
from sonar.connectors.ecb_sdw import EcbSdwConnector
from sonar.connectors.fred import FredConnector
from sonar.indices.monetary import (
    compute_m1_effective_rates,
    compute_m2_taylor_gaps,
    compute_m4_fci,
)
from sonar.indices.monetary.builders import MonetaryInputsBuilder

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.slow

LOOKBACK_YEARS = 15  # Tier-4 fallback — keeps live canaries tractable.


@pytest.fixture
def fred_api_key() -> str:
    key = os.environ.get("FRED_API_KEY")
    if not key:
        pytest.skip("FRED_API_KEY not set")
    return key


@pytest.fixture
def observation_date() -> object:
    # Anchor ~14 days back to let weekly series (WALCL, NFCI) publish.
    return datetime.now(tz=UTC).date() - timedelta(days=14)


async def _make_builder(
    tmp_path: Path, fred_api_key: str
) -> tuple[MonetaryInputsBuilder, FredConnector, EcbSdwConnector]:
    fred = FredConnector(api_key=fred_api_key, cache_dir=str(tmp_path / "fred"))
    cbo = CboConnector(fred=fred)
    ecb = EcbSdwConnector(cache_dir=str(tmp_path / "ecb"))
    return MonetaryInputsBuilder(fred=fred, cbo=cbo, ecb_sdw=ecb), fred, ecb


async def test_m1_us_live_smoke(
    tmp_path: Path, fred_api_key: str, observation_date: object
) -> None:
    builder, fred, ecb = await _make_builder(tmp_path, fred_api_key)
    try:
        inputs = await builder.build_m1_inputs("US", observation_date, history_years=LOOKBACK_YEARS)
        result = compute_m1_effective_rates(inputs)
        assert 0 <= result.score_normalized <= 100
        assert result.methodology_version.startswith("M1_EFFECTIVE_RATES_")
        # Above-ZLB path: shadow = policy.
        assert result.shadow_rate_pct == pytest.approx(inputs.policy_rate_pct)
    finally:
        await fred.aclose()
        await ecb.aclose()


async def test_m2_us_live_smoke(
    tmp_path: Path, fred_api_key: str, observation_date: object
) -> None:
    builder, fred, ecb = await _make_builder(tmp_path, fred_api_key)
    try:
        inputs = await builder.build_m2_inputs("US", observation_date, history_years=LOOKBACK_YEARS)
        result = compute_m2_taylor_gaps(inputs)
        assert 0 <= result.score_normalized <= 100
        assert result.methodology_version.startswith("M2_TAYLOR_GAPS_")
        # At least 3 of 4 variants computable (forward uses UMich proxy).
        assert result.variants_computed >= 3
    finally:
        await fred.aclose()
        await ecb.aclose()


async def test_m4_us_live_smoke(
    tmp_path: Path, fred_api_key: str, observation_date: object
) -> None:
    builder, fred, ecb = await _make_builder(tmp_path, fred_api_key)
    try:
        inputs = await builder.build_m4_inputs("US", observation_date, history_years=LOOKBACK_YEARS)
        result = compute_m4_fci(inputs)
        assert 0 <= result.score_normalized <= 100
        assert result.methodology_version.startswith("M4_FCI_")
        assert result.fci_provider == "NFCI_CHICAGO"
    finally:
        await fred.aclose()
        await ecb.aclose()


async def test_m1_ea_live_smoke(
    tmp_path: Path, fred_api_key: str, observation_date: object
) -> None:
    builder, fred, ecb = await _make_builder(tmp_path, fred_api_key)
    try:
        inputs = await builder.build_m1_inputs("EA", observation_date, history_years=LOOKBACK_YEARS)
        result = compute_m1_effective_rates(inputs)
        assert 0 <= result.score_normalized <= 100
        assert inputs.country_code == "EA"
        assert "EXPECTED_INFLATION_PROXY" in inputs.upstream_flags
        assert result.shadow_rate_pct == pytest.approx(inputs.policy_rate_pct)
    finally:
        await fred.aclose()
        await ecb.aclose()
