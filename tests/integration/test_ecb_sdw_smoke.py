"""Integration smoke for EcbSdwConnector — live ECB SDW (no API key)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from sonar.connectors.ecb_sdw import EcbSdwConnector

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def live_ecb(tmp_path: Path) -> AsyncIterator[EcbSdwConnector]:
    cache_dir = tmp_path / "ecb_smoke_cache"
    cache_dir.mkdir()
    conn = EcbSdwConnector(cache_dir=str(cache_dir))
    yield conn
    await conn.aclose()


async def test_ea_aaa_10y_2024_01_02_smoke(live_ecb: EcbSdwConnector) -> None:
    obs_date = date(2024, 1, 2)
    obs = await live_ecb.fetch_series("B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y", obs_date, obs_date)
    assert len(obs) >= 1
    o = obs[-1]
    assert o.country_code == "EA"
    assert o.tenor_years == 10.0
    assert o.source == "ECB_SDW"
    # AAA 10Y EA late 2023 / early 2024 sat ~2.0-2.5%; 2.12% historically.
    assert 150 <= o.yield_bps <= 350


async def test_ea_aaa_full_curve_2024_01_02(live_ecb: EcbSdwConnector) -> None:
    obs_date = date(2024, 1, 2)
    curve = await live_ecb.fetch_yield_curve_nominal(country="EA", observation_date=obs_date)
    # ECB publishes 11 spot tenors (no 1M).
    assert len(curve) == 11
    assert "10Y" in curve
    assert curve["10Y"].tenor_years == 10.0
