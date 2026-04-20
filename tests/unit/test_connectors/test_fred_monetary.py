"""Unit tests for the FRED monetary-indicator extension (CAL-096, week6 sprint 2b)."""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from tenacity import wait_none

from sonar.connectors.fred import FredConnector

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from pytest_httpx import HTTPXMock


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "fred_monetary"
    d.mkdir()
    return d


@pytest_asyncio.fixture
async def fred_connector(
    tmp_cache_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[FredConnector]:
    monkeypatch.setattr(FredConnector._fetch_raw.retry, "wait", wait_none())
    monkeypatch.setattr(FredConnector._fetch_economic_raw.retry, "wait", wait_none())
    conn = FredConnector(api_key="test-key", cache_dir=str(tmp_cache_dir))
    yield conn
    await conn.aclose()


def _stub_daily(values: list[tuple[str, str]]) -> dict:
    return {"observations": [{"date": d, "value": v} for d, v in values]}


# ---------------------------------------------------------------------------
# Replay — daily / weekly / monthly level series
# ---------------------------------------------------------------------------


async def test_fetch_fed_funds_target_upper(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        json=_stub_daily([("2024-12-01", "4.50"), ("2024-12-02", "4.50"), ("2024-12-18", "4.50")]),
    )
    obs = await fred_connector.fetch_fed_funds_target_upper_us(
        date(2024, 12, 1), date(2024, 12, 31)
    )
    assert len(obs) == 3
    assert all(o.series_id == "DFEDTARU" for o in obs)
    assert obs[0].value == pytest.approx(4.50)


async def test_fetch_fed_funds_target_lower(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        json=_stub_daily([("2024-12-01", "4.25"), ("2024-12-18", "4.25")]),
    )
    obs = await fred_connector.fetch_fed_funds_target_lower_us(
        date(2024, 12, 1), date(2024, 12, 31)
    )
    assert len(obs) == 2
    assert obs[0].series_id == "DFEDTARL"


async def test_fetch_fed_funds_effective(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        json=_stub_daily([("2024-11-01", "4.64"), ("2024-12-01", "4.48")]),
    )
    obs = await fred_connector.fetch_fed_funds_effective_us(date(2024, 11, 1), date(2024, 12, 31))
    assert len(obs) == 2
    assert obs[1].value == pytest.approx(4.48)


async def test_fetch_fed_balance_sheet(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        json=_stub_daily(
            [("2024-12-04", "6945325"), ("2024-12-11", "6902107"), ("2024-12-18", "6886504")]
        ),
    )
    obs = await fred_connector.fetch_fed_balance_sheet_us(date(2024, 12, 1), date(2024, 12, 31))
    assert len(obs) == 3
    # Late-2024 Fed balance sheet ~6.9T USD → at least 6T, at most 9T USDm.
    assert all(6_000_000 < o.value < 9_000_000 for o in obs)


async def test_fetch_pce_core_yoy(httpx_mock: HTTPXMock, fred_connector: FredConnector) -> None:
    # 13 months of level data (index) to let _yoy_transform produce 1 YoY obs.
    levels = [
        ("2023-12-01", "120.0"),
        *[(f"2024-{m:02d}-01", f"{120.0 + m:.1f}") for m in range(1, 13)],
    ]
    httpx_mock.add_response(method="GET", json=_stub_daily(levels))
    obs = await fred_connector.fetch_pce_core_yoy_us(date(2023, 12, 1), date(2024, 12, 31))
    assert len(obs) == 1
    # (132 - 120)/120 = 0.10
    assert obs[0].value == pytest.approx(0.10, abs=1e-6)
    assert obs[0].series_id == "PCEPILFE"


async def test_fetch_usd_neer(httpx_mock: HTTPXMock, fred_connector: FredConnector) -> None:
    httpx_mock.add_response(
        method="GET",
        json=_stub_daily([("2024-12-18", "128.5"), ("2024-12-19", "128.6")]),
    )
    obs = await fred_connector.fetch_usd_neer_us(date(2024, 12, 1), date(2024, 12, 31))
    assert len(obs) == 2
    assert obs[0].series_id == "DTWEXBGS"


async def test_fetch_mortgage_30y(httpx_mock: HTTPXMock, fred_connector: FredConnector) -> None:
    httpx_mock.add_response(
        method="GET",
        json=_stub_daily([("2024-12-05", "6.69"), ("2024-12-12", "6.60"), ("2024-12-19", "6.72")]),
    )
    obs = await fred_connector.fetch_mortgage_30y_us(date(2024, 12, 1), date(2024, 12, 31))
    assert len(obs) == 3
    assert obs[0].series_id == "MORTGAGE30US"


async def test_fetch_nfci(httpx_mock: HTTPXMock, fred_connector: FredConnector) -> None:
    httpx_mock.add_response(
        method="GET",
        json=_stub_daily([("2024-12-13", "-0.55"), ("2024-12-20", "-0.56")]),
    )
    obs = await fred_connector.fetch_nfci_us(date(2024, 12, 1), date(2024, 12, 31))
    assert len(obs) == 2
    # NFCI is a z-score; loose conditions typically negative.
    assert all(-5.0 < o.value < 5.0 for o in obs)


async def test_fetch_potential_gdp(httpx_mock: HTTPXMock, fred_connector: FredConnector) -> None:
    httpx_mock.add_response(
        method="GET",
        json=_stub_daily([("2024-07-01", "23800.0"), ("2024-10-01", "23900.0")]),
    )
    obs = await fred_connector.fetch_potential_gdp_us(date(2024, 1, 1), date(2024, 12, 31))
    assert len(obs) == 2
    assert obs[0].series_id == "GDPPOT"
    # CBO potential-GDP $bn chained 2017 ~$23-24T in 2024.
    assert all(20_000 < o.value < 30_000 for o in obs)


# ---------------------------------------------------------------------------
# Live canaries (brief §4 Commit 1 — DFEDTARU + PCEPILFE + DTWEXBGS)
# ---------------------------------------------------------------------------


@pytest.mark.slow
async def test_live_canary_dfedtaru(tmp_cache_dir: Path) -> None:
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        pytest.skip("FRED_API_KEY not set")
    conn = FredConnector(api_key=api_key, cache_dir=str(tmp_cache_dir))
    try:
        today = datetime.now(tz=UTC).date()
        obs = await conn.fetch_fed_funds_target_upper_us(today - timedelta(days=180), today)
        assert len(obs) >= 30
        for o in obs:
            # Fed funds target upper has spanned 0.25-6.0 since 2008.
            assert 0 <= o.value <= 10
    finally:
        await conn.aclose()


@pytest.mark.slow
async def test_live_canary_pcepilfe(tmp_cache_dir: Path) -> None:
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        pytest.skip("FRED_API_KEY not set")
    conn = FredConnector(api_key=api_key, cache_dir=str(tmp_cache_dir))
    try:
        today = datetime.now(tz=UTC).date()
        levels = await conn.fetch_pce_core_us(today - timedelta(days=400), today)
        assert len(levels) >= 6
        # Core PCE price index is a level (~120+ post-2023, base 2017=100).
        for o in levels:
            assert 90 < o.value < 200
    finally:
        await conn.aclose()


@pytest.mark.slow
async def test_live_canary_dtwexbgs(tmp_cache_dir: Path) -> None:
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        pytest.skip("FRED_API_KEY not set")
    conn = FredConnector(api_key=api_key, cache_dir=str(tmp_cache_dir))
    try:
        today = datetime.now(tz=UTC).date()
        obs = await conn.fetch_usd_neer_us(today - timedelta(days=60), today)
        assert len(obs) >= 10
        for o in obs:
            # Broad USD NEER indexed ~100-140 range since 2006 base.
            assert 80 < o.value < 180
    finally:
        await conn.aclose()
