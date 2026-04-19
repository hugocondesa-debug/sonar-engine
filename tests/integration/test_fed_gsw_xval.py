"""Integration test — Fed GSW canary vs live SONAR fit on US 2024-01-02.

Invokes the live FRED connector, fits NSS, then cross-validates against the
static feds200628 snapshot committed at
``tests/fixtures/xval/feds200628_2024-01-02.csv``. Asserts max deviation at
{2Y,5Y,10Y,30Y} stays below ``FED_GSW_XVAL_THRESHOLD_BPS`` (10 bps per
spec §7).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pytest
import pytest_asyncio

from sonar.config import settings
from sonar.connectors.fred import FredConnector
from sonar.overlays.nss import NSSInput, _label_to_years, fit_nss
from sonar.overlays.validation import (
    FED_GSW_XVAL_THRESHOLD_BPS,
    compare_to_gsw,
    parse_feds200628_csv,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.integration

GSW_FIXTURE = Path(__file__).parent.parent / "fixtures" / "xval" / "feds200628_2024-01-02.csv"


@pytest_asyncio.fixture
async def live_fred(tmp_path: Path) -> AsyncIterator[FredConnector]:
    placeholder = "your_fred_api_key_here"  # pragma: allowlist secret
    if not settings.fred_api_key or settings.fred_api_key == placeholder:
        pytest.skip("FRED_API_KEY not configured in .env")
    cache_dir = tmp_path / "fred_xval_cache"
    cache_dir.mkdir()
    conn = FredConnector(api_key=settings.fred_api_key, cache_dir=str(cache_dir))
    yield conn
    await conn.aclose()


async def test_us_2024_01_02_xval_under_threshold(live_fred: FredConnector) -> None:
    obs_date = date(2024, 1, 2)
    nominals = await live_fred.fetch_yield_curve_nominal(country="US", observation_date=obs_date)

    labels = sorted(nominals.keys(), key=_label_to_years)
    nss_input = NSSInput(
        tenors_years=np.array([_label_to_years(t) for t in labels]),
        yields=np.array([nominals[t].yield_bps / 10_000.0 for t in labels]),
        country_code="US",
        observation_date=obs_date,
        curve_input_type="par",
    )
    spot = fit_nss(nss_input)

    reference = parse_feds200628_csv(GSW_FIXTURE, obs_date)
    deviations = compare_to_gsw(spot, reference)

    assert set(deviations.keys()) == {2, 5, 10, 30}
    max_dev = max(deviations.values())
    assert max_dev <= FED_GSW_XVAL_THRESHOLD_BPS, (
        f"SONAR vs Fed GSW max |deviation| = {max_dev:.2f} bps exceeds "
        f"spec §7 threshold {FED_GSW_XVAL_THRESHOLD_BPS} bps. "
        f"Per-tenor: {deviations}"
    )
