"""Unit tests for FMPConnector — pytest-httpx mocked JSON responses."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from tenacity import wait_none

from sonar.connectors.fmp import (
    FMP_INDEX_SYMBOLS,
    FMPConnector,
    FMPPriceObservation,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from pytest_httpx import HTTPXMock


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "fmp_cache"
    d.mkdir()
    return d


@pytest.fixture(autouse=True)
def _disable_tenacity_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(FMPConnector._fetch_raw.retry, "wait", wait_none())


@pytest_asyncio.fixture
async def fmp_connector(tmp_cache_dir: Path) -> AsyncIterator[FMPConnector]:
    conn = FMPConnector(api_key="test_key", cache_dir=str(tmp_cache_dir))
    yield conn
    await conn.aclose()


def test_index_symbol_mapping_covers_majors() -> None:
    # Sprint §1 expected aliases + FMP pattern validation.
    for alias in ("SPX", "DAX", "CAC", "FTSE", "FTSEMIB", "AEX", "IBEX", "PSI"):
        assert alias in FMP_INDEX_SYMBOLS
    assert FMP_INDEX_SYMBOLS["SPX"] == "^GSPC"
    assert FMP_INDEX_SYMBOLS["DAX"] == "^GDAXI"


async def test_fetch_index_historical_happy(
    httpx_mock: HTTPXMock, fmp_connector: FMPConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        json=[
            {"symbol": "^GSPC", "date": "2024-01-05", "close": 4697.23, "volume": 2155000000},
            {"symbol": "^GSPC", "date": "2024-01-04", "close": 4688.69, "volume": 2000000000},
            {"symbol": "^GSPC", "date": "2024-01-02", "close": 4742.83, "volume": 3000000000},
        ],
    )
    rows = await fmp_connector.fetch_index_historical("SPX", date(2024, 1, 2), date(2024, 1, 5))
    assert len(rows) == 3
    assert all(isinstance(r, FMPPriceObservation) for r in rows)
    assert rows[0].observation_date == date(2024, 1, 2)
    assert rows[-1].observation_date == date(2024, 1, 5)
    assert rows[0].close == pytest.approx(4742.83)
    assert all(r.source == "FMP" for r in rows)
    assert rows[0].symbol_sonar == "SPX"
    assert rows[0].symbol_fmp == "^GSPC"


async def test_fetch_index_unknown_alias_raises(
    httpx_mock: HTTPXMock, fmp_connector: FMPConnector
) -> None:
    _ = httpx_mock
    with pytest.raises(ValueError, match="Unknown SONAR index alias"):
        await fmp_connector.fetch_index_historical("BOGUS", date(2024, 1, 2), date(2024, 1, 5))


async def test_fetch_index_api_error_payload_raises(
    httpx_mock: HTTPXMock, fmp_connector: FMPConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        json={"Error Message": "Legacy Endpoint"},
    )
    with pytest.raises(ValueError, match="FMP error"):
        await fmp_connector.fetch_index_historical("SPX", date(2024, 1, 2), date(2024, 1, 5))


async def test_fetch_index_cache_hit_no_http(
    httpx_mock: HTTPXMock, fmp_connector: FMPConnector
) -> None:
    _ = httpx_mock
    pre_cached = [
        FMPPriceObservation(
            symbol_sonar="SPX",
            symbol_fmp="^GSPC",
            observation_date=date(2024, 1, 2),
            close=4742.83,
            volume=3000000000,
        )
    ]
    fmp_connector.cache.set("fmp:^GSPC:2024-01-02:2024-01-02", pre_cached)
    rows = await fmp_connector.fetch_index_historical("SPX", date(2024, 1, 2), date(2024, 1, 2))
    assert len(rows) == 1
    assert rows[0].close == pytest.approx(4742.83)


async def test_fetch_index_filters_malformed_rows(
    httpx_mock: HTTPXMock, fmp_connector: FMPConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        json=[
            {"symbol": "^GSPC", "date": "2024-01-05", "close": 4697.23},
            {"symbol": "^GSPC", "date": None, "close": 4000.0},  # missing date
            {"symbol": "^GSPC", "date": "2024-01-04"},  # missing close
            {"symbol": "^GSPC", "date": "2024-01-02", "close": 4742.83},
        ],
    )
    rows = await fmp_connector.fetch_index_historical("SPX", date(2024, 1, 2), date(2024, 1, 5))
    # Only 2 valid rows — None-date + missing-close dropped.
    assert len(rows) == 2
    assert {r.observation_date for r in rows} == {date(2024, 1, 2), date(2024, 1, 5)}


async def test_fetch_index_empty_response_ok(
    httpx_mock: HTTPXMock, fmp_connector: FMPConnector
) -> None:
    httpx_mock.add_response(method="GET", json=[])
    rows = await fmp_connector.fetch_index_historical("SPX", date(2024, 1, 2), date(2024, 1, 5))
    assert rows == []
