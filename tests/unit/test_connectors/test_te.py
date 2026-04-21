"""Unit tests for TEConnector — pytest-httpx mocked JSON responses."""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from tenacity import wait_none

from sonar.connectors.base import Observation
from sonar.connectors.te import TE_10Y_SYMBOLS, TEConnector

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from pytest_httpx import HTTPXMock


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "te_cache"
    d.mkdir()
    return d


@pytest.fixture(autouse=True)
def _disable_tenacity_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(TEConnector._fetch_raw.retry, "wait", wait_none())


@pytest_asyncio.fixture
async def te_connector(tmp_cache_dir: Path) -> AsyncIterator[TEConnector]:
    conn = TEConnector(api_key="test:secret", cache_dir=str(tmp_cache_dir))
    yield conn
    await conn.aclose()


def test_10y_symbol_mapping_covers_t1() -> None:
    for c in ("US", "DE", "UK", "JP", "IT", "ES", "FR", "NL", "PT"):
        assert c in TE_10Y_SYMBOLS
    assert TE_10Y_SYMBOLS["US"] == "USGG10YR:IND"
    assert TE_10Y_SYMBOLS["DE"] == "GDBR10:IND"


async def test_fetch_happy_us_10y(httpx_mock: HTTPXMock, te_connector: TEConnector) -> None:
    httpx_mock.add_response(
        method="GET",
        json=[
            {"Symbol": "USGG10YR:IND", "Date": "05/01/2024", "Close": 4.042},
            {"Symbol": "USGG10YR:IND", "Date": "04/01/2024", "Close": 3.991},
            {"Symbol": "USGG10YR:IND", "Date": "02/01/2024", "Close": 3.944},
        ],
    )
    rows = await te_connector.fetch_sovereign_yield_historical(
        "US", "10Y", date(2024, 1, 2), date(2024, 1, 5)
    )
    assert len(rows) == 3
    assert all(isinstance(r, Observation) for r in rows)
    assert rows[0].observation_date == date(2024, 1, 2)
    assert rows[-1].observation_date == date(2024, 1, 5)
    assert rows[0].yield_bps == 394  # 3.944 * 100
    assert rows[-1].yield_bps == 404  # 4.042 * 100
    assert all(r.country_code == "US" for r in rows)
    assert all(r.tenor_years == 10.0 for r in rows)
    assert all(r.source == "TE" for r in rows)


async def test_unsupported_tenor_raises(httpx_mock: HTTPXMock, te_connector: TEConnector) -> None:
    _ = httpx_mock
    with pytest.raises(ValueError, match="tenor='10Y' only"):
        await te_connector.fetch_sovereign_yield_historical(
            "US", "5Y", date(2024, 1, 2), date(2024, 1, 5)
        )


async def test_unknown_country_raises(httpx_mock: HTTPXMock, te_connector: TEConnector) -> None:
    _ = httpx_mock
    with pytest.raises(ValueError, match="Unknown TE 10Y symbol"):
        await te_connector.fetch_sovereign_yield_historical(
            "XX", "10Y", date(2024, 1, 2), date(2024, 1, 5)
        )


async def test_filters_malformed_rows(httpx_mock: HTTPXMock, te_connector: TEConnector) -> None:
    httpx_mock.add_response(
        method="GET",
        json=[
            {"Symbol": "USGG10YR:IND", "Date": "05/01/2024", "Close": 4.042},
            {"Symbol": "USGG10YR:IND", "Date": "bogus", "Close": 3.5},  # bad date
            {"Symbol": "USGG10YR:IND", "Date": "04/01/2024"},  # no close
            {"Symbol": "USGG10YR:IND", "Close": 3.7},  # no date
        ],
    )
    rows = await te_connector.fetch_sovereign_yield_historical(
        "US", "10Y", date(2024, 1, 2), date(2024, 1, 5)
    )
    assert len(rows) == 1
    assert rows[0].observation_date == date(2024, 1, 5)


async def test_cache_hit_no_http(httpx_mock: HTTPXMock, te_connector: TEConnector) -> None:
    _ = httpx_mock
    pre_cached = [
        Observation(
            country_code="US",
            observation_date=date(2024, 1, 2),
            tenor_years=10.0,
            yield_bps=394,
            source="TE",
            source_series_id="USGG10YR:IND",
        )
    ]
    te_connector.cache.set("te:USGG10YR:IND:2024-01-02:2024-01-02", pre_cached)
    rows = await te_connector.fetch_sovereign_yield_historical(
        "US", "10Y", date(2024, 1, 2), date(2024, 1, 2)
    )
    assert len(rows) == 1
    assert rows[0].yield_bps == 394


async def test_window_around_wrapper_widens_to_5y(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        json=[{"Symbol": "GDBR10:IND", "Date": "02/01/2024", "Close": 2.13}],
    )
    rows = await te_connector.fetch_10y_window_around("DE", observation_date=date(2024, 1, 2))
    assert len(rows) == 1
    assert rows[0].country_code == "DE"
    assert rows[0].yield_bps == 213


# ---------------------------------------------------------------------------
# UK 10Y gilt via existing fetch_sovereign_yield_historical (Sprint I-patch C2)
# ---------------------------------------------------------------------------


def test_uk_10y_symbol_mapping_present() -> None:
    """Verification — existing GUKG10:IND mapping already covers UK 10Y."""
    assert TE_10Y_SYMBOLS["UK"] == "GUKG10:IND"


async def test_fetch_uk_10y_gilt_via_existing_helper(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """``fetch_sovereign_yield_historical(country='UK', tenor='10Y')``
    already returns UK 10Y gilt yields via the ``GUKG10:IND`` mapping; no
    dedicated UK wrapper needed for Sprint I-patch (verified empirically
    during the C1 probe)."""
    httpx_mock.add_response(
        method="GET",
        json=[
            {"Symbol": "GUKG10:IND", "Date": "31/12/2024", "Close": 4.568},
            {"Symbol": "GUKG10:IND", "Date": "30/12/2024", "Close": 4.612},
            {"Symbol": "GUKG10:IND", "Date": "23/12/2024", "Close": 4.487},
        ],
    )
    rows = await te_connector.fetch_sovereign_yield_historical(
        "UK", "10Y", date(2024, 12, 1), date(2024, 12, 31)
    )
    assert len(rows) == 3
    assert all(r.country_code == "UK" for r in rows)
    assert all(r.tenor_years == 10.0 for r in rows)
    assert all(r.source_series_id == "GUKG10:IND" for r in rows)
    # GBP 10Y gilt late 2024 sat ~4.4-4.7%.
    assert rows[-1].yield_bps == 457  # 4.568 * 100


@pytest.mark.slow
async def test_live_canary_uk_10y_gilt(tmp_cache_dir: Path) -> None:
    """Live probe — UK 10Y gilt daily observations via TE markets endpoint."""
    api_key = os.environ.get("TE_API_KEY")
    if not api_key:
        pytest.skip("TE_API_KEY not set")
    conn = TEConnector(api_key=api_key, cache_dir=str(tmp_cache_dir))
    try:
        today = datetime.now(tz=UTC).date()
        start = today - timedelta(days=60)
        rows = await conn.fetch_sovereign_yield_historical("UK", "10Y", start, today)
        # Daily cadence over ~60 days → expect ≥ 20 business-day observations.
        assert len(rows) >= 20
        assert rows[0].country_code == "UK"
        # UK 10Y gilt has stayed in [0.1, 6.0]% for the past decade.
        for o in rows:
            assert 0 < o.yield_bps / 100 < 10
    finally:
        await conn.aclose()
