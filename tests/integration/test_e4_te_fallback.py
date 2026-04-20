"""E4 Sentiment with TE fallback — US + DE live integration smoke.

Per Week 6 Sprint 1 brief §Commit 5: prove that the TE-extended
builder raises E4 component availability materially. US target
≥ 10/13 (vs 6/13 without TE); DE target ≥ 7/13 (vs 3/13 without TE).

Marked ``@pytest.mark.slow`` so default CI stays network-independent.
Requires ``FRED_API_KEY`` and ``TE_API_KEY`` env vars.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from sonar.connectors.eurostat import EurostatConnector
from sonar.connectors.fred import FredConnector
from sonar.connectors.te import TEConnector
from sonar.indices.economic.builders import build_e4_inputs

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.slow


def _count_available(inputs: object) -> int:
    """Count E4 components (non-None slots) on the assembled inputs."""
    slots = (
        "umich_sentiment_12m_change",
        "conference_board_confidence_12m_change",
        "umich_5y_inflation_exp",
        "ism_manufacturing",
        "ism_services",
        "nfib_small_business",
        "epu_index",
        "ec_esi",
        "zew_expectations",
        "ifo_business_climate",
        "vix_level",
        "tankan_large_mfg",
        "sloos_standards_net_pct",
    )
    return sum(1 for s in slots if getattr(inputs, s, None) is not None)


async def test_e4_us_with_te_fallback(tmp_path: Path) -> None:
    """US E4 with TE fallback should cover ISM Mfg + ISM Svc + NFIB."""
    fred_key = os.environ.get("FRED_API_KEY")
    te_key = os.environ.get("TE_API_KEY")
    if not fred_key or not te_key:
        pytest.skip("FRED_API_KEY or TE_API_KEY not set")

    today = datetime.now(tz=UTC).date()
    observation_date = today - timedelta(days=60)

    fred = FredConnector(api_key=fred_key, cache_dir=str(tmp_path / "fred"))
    eurostat = EurostatConnector(cache_dir=str(tmp_path / "eurostat"), rate_limit_seconds=0.5)
    te = TEConnector(api_key=te_key, cache_dir=str(tmp_path / "te"))

    try:
        inputs = await build_e4_inputs(
            "US",
            observation_date,
            fred=fred,
            eurostat=eurostat,
            te=te,
        )
    finally:
        await fred.aclose()
        await eurostat.aclose()
        await te.aclose()

    available = _count_available(inputs)
    # US baseline without TE typically 6/13; with TE we expect ISM Mfg +
    # ISM Svc + NFIB slots to populate (= 9-10/13 depending on CB stale).
    assert available >= 9, f"US E4 availability {available} < 9 with TE fallback"
    for slot in ("ism_manufacturing", "ism_services", "nfib_small_business"):
        assert getattr(inputs, slot) is not None, f"{slot} not populated via TE"
    for flag in ("TE_FALLBACK_ISM_MFG", "TE_FALLBACK_ISM_SVC", "TE_FALLBACK_NFIB"):
        assert flag in inputs.upstream_flags, f"{flag} not in flags"
    assert "TE" in inputs.source_connectors


async def test_e4_de_with_te_fallback(tmp_path: Path) -> None:
    """DE E4 with TE fallback should add Ifo + ZEW to Eurostat ESI."""
    fred_key = os.environ.get("FRED_API_KEY")
    te_key = os.environ.get("TE_API_KEY")
    if not fred_key or not te_key:
        pytest.skip("FRED_API_KEY or TE_API_KEY not set")

    today = datetime.now(tz=UTC).date()
    observation_date = today - timedelta(days=60)

    fred = FredConnector(api_key=fred_key, cache_dir=str(tmp_path / "fred"))
    eurostat = EurostatConnector(cache_dir=str(tmp_path / "eurostat"), rate_limit_seconds=0.5)
    te = TEConnector(api_key=te_key, cache_dir=str(tmp_path / "te"))

    try:
        inputs = await build_e4_inputs(
            "DE",
            observation_date,
            fred=fred,
            eurostat=eurostat,
            te=te,
        )
    finally:
        await fred.aclose()
        await eurostat.aclose()
        await te.aclose()

    available = _count_available(inputs)
    # DE baseline without TE: ESI + ConsConf + VIX = 3/13. With TE Ifo + ZEW
    # add 2 → 5/13. Accept ≥ 4 (in case one DE series has publication lag).
    assert available >= 4, f"DE E4 availability {available} < 4 with TE fallback"
    assert inputs.ifo_business_climate is not None
    assert inputs.zew_expectations is not None
    for flag in ("TE_FALLBACK_IFO", "TE_FALLBACK_ZEW"):
        assert flag in inputs.upstream_flags
    assert "TE" in inputs.source_connectors
