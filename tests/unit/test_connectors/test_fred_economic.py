"""Unit tests for the FRED Economic-indicators extension (CAL-083)."""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from tenacity import wait_none

from sonar.connectors.fred import (
    FredConnector,
    FredEconomicObservation,
    _yoy_transform,
)
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pytest_httpx import HTTPXMock


CASSETTE_DIR = Path(__file__).parent.parent.parent / "cassettes" / "connectors"


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "fred_econ"
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


def _load_cassette(name: str) -> dict:
    return json.loads((CASSETTE_DIR / name).read_text())


# ---------------------------------------------------------------------------
# _yoy_transform
# ---------------------------------------------------------------------------


def _mk(d: date, v: float, sid: str = "X") -> FredEconomicObservation:
    return FredEconomicObservation(observation_date=d, value=v, series_id=sid)


def test_yoy_transform_monthly() -> None:
    levels = [_mk(date(2023, m, 1), 100.0 + m) for m in range(1, 13)] + [
        _mk(date(2024, 1, 1), 115.0)
    ]
    yoy = _yoy_transform(levels, periods_per_year=12)
    assert len(yoy) == 1
    assert yoy[0].observation_date == date(2024, 1, 1)
    assert yoy[0].value == pytest.approx((115.0 - 101.0) / 101.0)


def test_yoy_transform_skips_zero_prior() -> None:
    levels = [_mk(date(2023, 1, 1), 0.0), _mk(date(2024, 1, 1), 5.0)]
    assert _yoy_transform(levels, periods_per_year=12) == []


def test_yoy_transform_empty() -> None:
    assert _yoy_transform([], periods_per_year=4) == []


# ---------------------------------------------------------------------------
# Cassette replay — E1 helpers
# ---------------------------------------------------------------------------


async def test_fetch_gdp_yoy_from_cassette(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    httpx_mock.add_response(method="GET", json=_load_cassette("fred_gdpc1_2024_01_02.json"))
    yoy = await fred_connector.fetch_gdp_real_yoy_us(date(2021, 1, 1), date(2024, 6, 30))
    assert len(yoy) >= 4
    for o in yoy:
        # US real GDP YoY historically ±10% outside crisis/COVID.
        assert -0.2 < o.value < 0.2
        assert o.series_id == "GDPC1"


async def test_fetch_industrial_production_yoy_from_cassette(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    httpx_mock.add_response(method="GET", json=_load_cassette("fred_indpro_2024_01_02.json"))
    yoy = await fred_connector.fetch_industrial_production_yoy_us(
        date(2021, 1, 1), date(2024, 6, 30)
    )
    assert len(yoy) >= 12
    for o in yoy:
        assert -0.3 < o.value < 0.3


# ---------------------------------------------------------------------------
# Cassette replay — E3 helpers
# ---------------------------------------------------------------------------


async def test_fetch_unemployment_rate_from_cassette(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    httpx_mock.add_response(method="GET", json=_load_cassette("fred_unrate_2024_01_02.json"))
    obs = await fred_connector.fetch_unemployment_rate_us(date(2020, 1, 1), date(2024, 6, 30))
    assert len(obs) >= 30
    for o in obs:
        assert 0 < o.value < 30


async def test_fetch_eci_wages_yoy_from_cassette(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    httpx_mock.add_response(method="GET", json=_load_cassette("fred_eciwag_2024_01_02.json"))
    yoy = await fred_connector.fetch_eci_wages_yoy_us(date(2021, 1, 1), date(2024, 6, 30))
    assert len(yoy) >= 4
    for o in yoy:
        assert 0 < o.value < 0.15


# ---------------------------------------------------------------------------
# Cassette replay — E4 helpers
# ---------------------------------------------------------------------------


async def test_fetch_umich_from_cassette(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    httpx_mock.add_response(method="GET", json=_load_cassette("fred_umcsent_2024_01_02.json"))
    obs = await fred_connector.fetch_umich_sentiment_us(date(2020, 1, 1), date(2024, 6, 30))
    assert len(obs) >= 30
    for o in obs:
        assert 30 < o.value < 120


async def test_fetch_vix_from_cassette(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    httpx_mock.add_response(method="GET", json=_load_cassette("fred_vixcls_2024_01_02.json"))
    obs = await fred_connector.fetch_vix_us(date(2020, 1, 1), date(2024, 6, 30))
    assert len(obs) >= 500
    for o in obs:
        assert 5 < o.value < 100


async def test_fetch_sloos_from_cassette(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    httpx_mock.add_response(method="GET", json=_load_cassette("fred_drtscilm_2024_01_02.json"))
    obs = await fred_connector.fetch_sloos_tightening_us(date(2020, 1, 1), date(2024, 6, 30))
    assert len(obs) >= 10
    for o in obs:
        assert -100 <= o.value <= 100


# ---------------------------------------------------------------------------
# Delisted-series guards (CAL-092 hooks)
# ---------------------------------------------------------------------------


async def test_ism_mfg_pmi_raises_delisted(fred_connector: FredConnector) -> None:
    with pytest.raises(DataUnavailableError, match="ISM Manufacturing PMI"):
        await fred_connector.fetch_ism_mfg_pmi(date(2024, 1, 1), date(2024, 6, 30))


async def test_ism_services_pmi_raises_delisted(fred_connector: FredConnector) -> None:
    with pytest.raises(DataUnavailableError, match="ISM Services PMI"):
        await fred_connector.fetch_ism_services_pmi(date(2024, 1, 1), date(2024, 6, 30))


async def test_nfib_raises_not_hosted(fred_connector: FredConnector) -> None:
    with pytest.raises(DataUnavailableError, match="NFIB"):
        await fred_connector.fetch_nfib_small_biz_us(date(2024, 1, 1), date(2024, 6, 30))


# ---------------------------------------------------------------------------
# Cache round-trip
# ---------------------------------------------------------------------------


async def test_fetch_economic_series_caches(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    httpx_mock.add_response(method="GET", json=_load_cassette("fred_unrate_2024_01_02.json"))
    first = await fred_connector.fetch_economic_series(
        "UNRATE", date(2020, 1, 1), date(2024, 6, 30)
    )
    second = await fred_connector.fetch_economic_series(
        "UNRATE", date(2020, 1, 1), date(2024, 6, 30)
    )
    assert first == second
    assert len(httpx_mock.get_requests()) == 1


async def test_fetch_economic_series_skips_dot_sentinel(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        json={
            "observations": [
                {"date": "2024-01-01", "value": "."},
                {"date": "2024-02-01", "value": "3.7"},
            ]
        },
    )
    obs = await fred_connector.fetch_economic_series("UNRATE", date(2024, 1, 1), date(2024, 2, 28))
    assert len(obs) == 1
    assert obs[0].observation_date == date(2024, 2, 1)


# ---------------------------------------------------------------------------
# Live canaries (CAL-083)
# ---------------------------------------------------------------------------


@pytest.mark.slow
async def test_live_canary_unrate_recent(tmp_cache_dir: Path) -> None:
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        pytest.skip("FRED_API_KEY not set")
    conn = FredConnector(api_key=api_key, cache_dir=str(tmp_cache_dir))
    try:
        today = datetime.now(tz=UTC).date()
        obs = await conn.fetch_unemployment_rate_us(today - timedelta(days=365), today)
        assert len(obs) >= 6
        for o in obs:
            assert 0 < o.value < 30
    finally:
        await conn.aclose()


@pytest.mark.slow
async def test_live_canary_umich_recent(tmp_cache_dir: Path) -> None:
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        pytest.skip("FRED_API_KEY not set")
    conn = FredConnector(api_key=api_key, cache_dir=str(tmp_cache_dir))
    try:
        today = datetime.now(tz=UTC).date()
        obs = await conn.fetch_umich_sentiment_us(today - timedelta(days=365), today)
        assert len(obs) >= 6
        for o in obs:
            assert 30 < o.value < 120
    finally:
        await conn.aclose()


@pytest.mark.slow
async def test_live_canary_vix_recent(tmp_cache_dir: Path) -> None:
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        pytest.skip("FRED_API_KEY not set")
    conn = FredConnector(api_key=api_key, cache_dir=str(tmp_cache_dir))
    try:
        today = datetime.now(tz=UTC).date()
        obs = await conn.fetch_vix_us(today - timedelta(days=30), today)
        assert len(obs) >= 10
        for o in obs:
            assert 5 < o.value < 100
    finally:
        await conn.aclose()
