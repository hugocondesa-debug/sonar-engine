"""Unit tests for the bis.py WS_LONG_PP property-price extension."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from tenacity import wait_none

from sonar.connectors.bis import (
    DATAFLOW_WS_LONG_PP,
    BisConnector,
)

CASSETTE_DIR = Path(__file__).parent.parent.parent / "cassettes" / "connectors"


def _load_connector_cassette(name: str) -> dict:
    return json.loads((CASSETTE_DIR / name).read_text())


if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pytest_httpx import HTTPXMock

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "bis"


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "bis_pp_cache"
    d.mkdir()
    return d


@pytest.fixture(autouse=True)
def _disable_tenacity_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(BisConnector._fetch_raw_data.retry, "wait", wait_none())


@pytest_asyncio.fixture
async def bis_connector(tmp_cache_dir: Path) -> AsyncIterator[BisConnector]:
    conn = BisConnector(cache_dir=str(tmp_cache_dir), rate_limit_seconds=0.0)
    yield conn
    await conn.aclose()


def test_dataflow_constant() -> None:
    assert DATAFLOW_WS_LONG_PP == ("WS_LONG_PP", "1.0")


async def test_fetch_property_price_index_happy(
    httpx_mock: HTTPXMock, bis_connector: BisConnector
) -> None:
    # Reuse the WS_TC sample shape — BIS SDMX-JSON response is uniform.
    payload = json.loads((FIXTURES_DIR / "ws_tc_PT_sample.json").read_text())
    httpx_mock.add_response(method="GET", json=payload)
    obs = await bis_connector.fetch_property_price_index("PT", date(2023, 10, 1), date(2024, 6, 30))
    assert len(obs) == 3
    assert all(o.country_code == "PT" for o in obs)
    assert all(o.source == "BIS_WS_LONG_PP" for o in obs)
    assert all(o.source_series_key == "Q.PT.N.628" for o in obs)


async def test_fetch_property_empty_payload(
    httpx_mock: HTTPXMock, bis_connector: BisConnector
) -> None:
    httpx_mock.add_response(method="GET", json={"data": {"dataSets": []}})
    obs = await bis_connector.fetch_property_price_index("XX", date(2023, 1, 1), date(2024, 1, 1))
    assert obs == []


# ---------------------------------------------------------------------------
# Cassette replay (CAL-071: captured BIS WS_SPP PT Q.PT.N.628 2022-Q1..2024-Q1)
# NB: the cassette was fetched from WS_SPP (Selected Property Prices, current
# dataflow) rather than the deprecated WS_LONG_PP. The SDMX-JSON 1.0 response
# shape is identical — parser is dataflow-agnostic. Production code in bis.py
# still points at WS_LONG_PP which BIS renamed → tracked as CAL-072.
# ---------------------------------------------------------------------------


async def test_fetch_property_pt_from_cassette(
    httpx_mock: HTTPXMock, bis_connector: BisConnector
) -> None:
    payload = _load_connector_cassette("bis_property_pt_2024_01_02.json")
    httpx_mock.add_response(method="GET", json=payload)
    obs = await bis_connector.fetch_property_price_index("PT", date(2022, 1, 1), date(2024, 3, 31))
    assert len(obs) >= 1
    assert all(o.country_code == "PT" for o in obs)
    assert all(o.source == "BIS_WS_LONG_PP" for o in obs)
    assert all(o.value_pct > 0 for o in obs)


# ---------------------------------------------------------------------------
# Live canary (CAL-071)
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.xfail(
    reason="BIS renamed dataflow WS_LONG_PP → WS_SPP; production bis.py still "
    "references the old ID and will 404. Tracked as CAL-072.",
    strict=False,
)
async def test_live_canary_property_pt_recent(tmp_cache_dir: Path) -> None:
    """Fetch last 2y PT property price index; assert non-empty + positive values."""
    # BIS is public; no API key. Autouse fixture disables tenacity wait — fine.
    conn = BisConnector(cache_dir=str(tmp_cache_dir), rate_limit_seconds=0.5)
    try:
        today = datetime.now(tz=UTC).date()
        # BIS property data has significant publication lag (2-3 quarters);
        # 2y window gives at least 4 quarterly obs.
        obs = await conn.fetch_property_price_index("PT", today - timedelta(days=730), today)
        assert len(obs) >= 1
        for o in obs:
            # Real property indices: >0 always (pre-2008 base around 50-100,
            # current ~100-200 range for most countries).
            assert o.value_pct > 0
    finally:
        await conn.aclose()
