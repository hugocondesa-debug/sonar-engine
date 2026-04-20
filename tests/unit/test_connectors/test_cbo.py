"""Unit tests for the CBO output-gap connector (CAL-097, week6 sprint 2b)."""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from tenacity import wait_none

from sonar.connectors.cbo import CboConnector, OutputGapObservation
from sonar.connectors.fred import FredConnector

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from pytest_httpx import HTTPXMock


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "cbo"
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


def _stub(series_values: list[tuple[str, str]]) -> dict:
    return {"observations": [{"date": d, "value": v} for d, v in series_values]}


async def test_fetch_output_gap_us_aligns_dates(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    # Simulate GDPC1 + GDPPOT quarterly aligned on same dates.
    httpx_mock.add_response(
        method="GET",
        json=_stub([("2024-07-01", "23500.0"), ("2024-10-01", "23700.0")]),
    )
    httpx_mock.add_response(
        method="GET",
        json=_stub([("2024-07-01", "23800.0"), ("2024-10-01", "23900.0")]),
    )
    cbo = CboConnector(fred=fred_connector)
    gaps = await cbo.fetch_output_gap_us(date(2024, 1, 1), date(2024, 12, 31))
    assert len(gaps) == 2
    # Q3: (23500 - 23800) / 23800 ≈ -0.01260
    assert gaps[0].gap == pytest.approx((23500.0 - 23800.0) / 23800.0, abs=1e-6)
    # Q4: (23700 - 23900) / 23900 ≈ -0.00837
    assert gaps[1].gap == pytest.approx((23700.0 - 23900.0) / 23900.0, abs=1e-6)
    assert gaps[0].real_series_id == "GDPC1"
    assert gaps[0].potential_series_id == "GDPPOT"


async def test_fetch_output_gap_drops_unpaired_quarter(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        json=_stub([("2024-07-01", "23500.0"), ("2024-10-01", "23700.0")]),
    )
    httpx_mock.add_response(
        method="GET",
        json=_stub([("2024-07-01", "23800.0")]),  # Q4 potential missing
    )
    cbo = CboConnector(fred=fred_connector)
    gaps = await cbo.fetch_output_gap_us(date(2024, 1, 1), date(2024, 12, 31))
    assert len(gaps) == 1
    assert gaps[0].observation_date == date(2024, 7, 1)


async def test_fetch_output_gap_skips_zero_potential(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        json=_stub([("2024-07-01", "23500.0")]),
    )
    httpx_mock.add_response(
        method="GET",
        json=_stub([("2024-07-01", "0.0")]),
    )
    cbo = CboConnector(fred=fred_connector)
    gaps = await cbo.fetch_output_gap_us(date(2024, 1, 1), date(2024, 12, 31))
    assert gaps == []


async def test_fetch_latest_output_gap_us_returns_most_recent(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        json=_stub([("2024-07-01", "23500.0"), ("2024-10-01", "23700.0")]),
    )
    httpx_mock.add_response(
        method="GET",
        json=_stub([("2024-07-01", "23800.0"), ("2024-10-01", "23900.0")]),
    )
    cbo = CboConnector(fred=fred_connector)
    latest = await cbo.fetch_latest_output_gap_us(date(2024, 12, 31))
    assert latest is not None
    assert latest.observation_date == date(2024, 10, 1)


async def test_fetch_latest_output_gap_us_returns_none_when_empty(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        json=_stub([]),
    )
    httpx_mock.add_response(
        method="GET",
        json=_stub([]),
    )
    cbo = CboConnector(fred=fred_connector)
    assert await cbo.fetch_latest_output_gap_us(date(2024, 12, 31)) is None


def test_output_gap_observation_dataclass_slots() -> None:
    obs = OutputGapObservation(
        observation_date=date(2024, 10, 1),
        gap=-0.005,
        real_gdp=23700.0,
        potential_gdp=23900.0,
    )
    assert obs.source == "FRED"
    assert obs.real_series_id == "GDPC1"


# ---------------------------------------------------------------------------
# Live canary (FRED GDPPOT + GDPC1)
# ---------------------------------------------------------------------------


@pytest.mark.slow
async def test_live_canary_cbo_output_gap_us_recent(tmp_cache_dir: Path) -> None:
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        pytest.skip("FRED_API_KEY not set")
    fred = FredConnector(api_key=api_key, cache_dir=str(tmp_cache_dir))
    try:
        today = datetime.now(tz=UTC).date()
        cbo = CboConnector(fred=fred)
        gaps = await cbo.fetch_output_gap_us(today - timedelta(days=730), today)
        assert len(gaps) >= 4
        for g in gaps:
            # Post-2010 US output gap essentially within [-10%, +10%].
            assert -0.10 < g.gap < 0.10
    finally:
        await fred.aclose()
