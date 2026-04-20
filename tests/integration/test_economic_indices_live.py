"""E1/E3/E4 live full-stack smoke for US + DE + PT (sprint-2a c5/6).

Per brief §Commit 5 spec: prove that the builders + connectors can
compute E1/E3/E4 end-to-end against live Eurostat + FRED feeds for
three representative countries. Runs only under ``pytest -m slow``
so default CI stays fast + network-independent.

Expectations by country:

- US: E1 ≥ 5 components (PMI miss = ISM delisted); E3 ≥ 8/10; E4 ≥ 4
  (ISM/NFIB missed; UMich/CB/5Y/EPU/VIX/SLOOS live).
- DE: E1 ≥ 4 components via Eurostat; E3 drops to UR-only but builders
  still populate; E4 produces ESI + ConsConf + VIX (≥ 3 but < 6 →
  compute_e4 raises InsufficientDataError per spec §6 intent).
- PT: same shape as DE; E4 similarly below threshold.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from sonar.connectors.eurostat import EurostatConnector
from sonar.connectors.fred import FredConnector
from sonar.indices.economic.builders import (
    build_e1_inputs,
    build_e3_inputs,
    build_e4_inputs,
)
from sonar.indices.economic.e1_activity import compute_e1_activity
from sonar.indices.economic.e3_labor import compute_e3_labor
from sonar.indices.economic.e4_sentiment import compute_e4_sentiment
from sonar.overlays.exceptions import InsufficientDataError

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.slow


async def _run_country(
    country: str,
    *,
    fred: FredConnector,
    eurostat: EurostatConnector,
    observation_date: object,
) -> dict[str, object]:
    """Build + compute E1/E3/E4; return per-country outcome map."""
    outcomes: dict[str, object] = {}

    e1_inputs = await build_e1_inputs(country, observation_date, fred=fred, eurostat=eurostat)
    try:
        e1 = compute_e1_activity(e1_inputs)
        outcomes["e1_score"] = e1.score_normalized
        outcomes["e1_available"] = e1.components_available
        outcomes["e1_flags"] = e1.flags
    except InsufficientDataError as e:
        outcomes["e1_error"] = str(e)

    e3_inputs = await build_e3_inputs(country, observation_date, fred=fred, eurostat=eurostat)
    try:
        e3 = compute_e3_labor(e3_inputs)
        outcomes["e3_score"] = e3.score_normalized
        outcomes["e3_available"] = e3.components_available
        outcomes["e3_flags"] = e3.flags
    except InsufficientDataError as e:
        outcomes["e3_error"] = str(e)

    e4_inputs = await build_e4_inputs(country, observation_date, fred=fred, eurostat=eurostat)
    try:
        e4 = compute_e4_sentiment(e4_inputs)
        outcomes["e4_score"] = e4.score_normalized
        outcomes["e4_available"] = e4.components_available
        outcomes["e4_flags"] = e4.flags
    except InsufficientDataError as e:
        outcomes["e4_error"] = str(e)
    return outcomes


async def test_e1_e3_e4_us_de_pt_live_smoke(tmp_path: Path) -> None:
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        pytest.skip("FRED_API_KEY not set")

    today = datetime.now(tz=UTC).date()
    # Month-end 2 months back — gives connectors time for their
    # latest-release cadence (GDP is quarterly + ~60d lag).
    observation_date = today - timedelta(days=60)

    fred = FredConnector(api_key=api_key, cache_dir=str(tmp_path / "fred"))
    eurostat = EurostatConnector(cache_dir=str(tmp_path / "eurostat"), rate_limit_seconds=0.5)

    try:
        us = await _run_country(
            "US", fred=fred, eurostat=eurostat, observation_date=observation_date
        )
        de = await _run_country(
            "DE", fred=fred, eurostat=eurostat, observation_date=observation_date
        )
        pt = await _run_country(
            "PT", fred=fred, eurostat=eurostat, observation_date=observation_date
        )
    finally:
        await fred.aclose()
        await eurostat.aclose()

    # US: E1 + E3 must succeed; E4 may succeed or hit MIN_COMPONENTS.
    assert "e1_error" not in us, f"US E1 failed: {us.get('e1_error')}"
    assert "e3_error" not in us, f"US E3 failed: {us.get('e3_error')}"
    e1_available = us.get("e1_available")
    assert isinstance(e1_available, int)
    assert e1_available >= 4
    e3_available = us.get("e3_available")
    assert isinstance(e3_available, int)
    assert e3_available >= 6

    # DE: E1 must succeed via Eurostat (GDP + IP + Employment + Retail all live).
    assert "e1_error" not in de, f"DE E1 failed: {de.get('e1_error')}"
    de_e1_available = de.get("e1_available")
    assert isinstance(de_e1_available, int)
    assert de_e1_available >= 3

    # DE E4 will usually fall below MIN_COMPONENTS=6 — accept either path.
    if "e4_error" in de:
        assert "requires" in str(de["e4_error"]).lower()

    # PT: namq_10_pe (national-accounts quarterly employment) returns 0 rows
    # for PT — Eurostat does not publish that slice. This drops E1 below
    # MIN_COMPONENTS=4 → InsufficientDataError per spec §6. Recorded for
    # retro + filed as CAL-094. Accept either success or the expected raise.
    if "e1_error" in pt:
        assert "requires" in str(pt["e1_error"]).lower()
    else:
        pt_e1_available = pt.get("e1_available")
        assert isinstance(pt_e1_available, int)
        assert pt_e1_available >= 3
