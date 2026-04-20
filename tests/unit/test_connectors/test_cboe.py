"""Unit tests for CboeConnector (FRED-mirrored VIX/VVIX/put-call)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from sonar.connectors.cboe import (
    FRED_SERIES_PUTCALL,
    FRED_SERIES_VIX,
    FRED_SERIES_VVIX,
    CboeConnector,
    CboeObservation,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from pytest_httpx import HTTPXMock


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "cboe_cache"
    d.mkdir()
    return d


@pytest_asyncio.fixture
async def cboe_connector(tmp_cache_dir: Path) -> AsyncIterator[CboeConnector]:
    conn = CboeConnector(api_key="test-key", cache_dir=str(tmp_cache_dir))
    yield conn
    await conn.aclose()


def _fred_json(series_id: str, rows: list[tuple[str, str]]) -> dict:
    return {"observations": [{"date": d, "value": v, "series_id": series_id} for d, v in rows]}


def test_series_constants() -> None:
    assert FRED_SERIES_VIX == "VIXCLS"
    assert FRED_SERIES_VVIX == "VVIXCLS"
    assert FRED_SERIES_PUTCALL == "PUTCLSPX"


async def test_fetch_vix_happy(httpx_mock: HTTPXMock, cboe_connector: CboeConnector) -> None:
    httpx_mock.add_response(
        method="GET",
        json=_fred_json("VIXCLS", [("2024-01-02", "14.2"), ("2024-01-03", "13.8")]),
    )
    obs = await cboe_connector.fetch_vix(date(2024, 1, 2), date(2024, 1, 3))
    assert len(obs) == 2
    assert all(isinstance(o, CboeObservation) for o in obs)
    assert obs[0].metric == "VIX"
    assert obs[0].value == pytest.approx(14.2)
    assert obs[0].source_series_id == "VIXCLS"


async def test_fetch_vvix(httpx_mock: HTTPXMock, cboe_connector: CboeConnector) -> None:
    httpx_mock.add_response(
        method="GET",
        json=_fred_json("VVIXCLS", [("2024-01-02", "87.5")]),
    )
    obs = await cboe_connector.fetch_vvix(date(2024, 1, 2), date(2024, 1, 2))
    assert obs[0].metric == "VVIX"
    assert obs[0].value == 87.5


async def test_fetch_put_call(httpx_mock: HTTPXMock, cboe_connector: CboeConnector) -> None:
    httpx_mock.add_response(
        method="GET",
        json=_fred_json("PUTCLSPX", [("2024-01-02", "0.85")]),
    )
    obs = await cboe_connector.fetch_put_call(date(2024, 1, 2), date(2024, 1, 2))
    assert obs[0].metric == "PUTCALL"
    assert obs[0].value == 0.85


async def test_fetch_skips_sentinel_dots(
    httpx_mock: HTTPXMock, cboe_connector: CboeConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        json=_fred_json(
            "VIXCLS",
            [("2024-01-01", "."), ("2024-01-02", "14.2"), ("2024-01-03", ".")],
        ),
    )
    obs = await cboe_connector.fetch_vix(date(2024, 1, 1), date(2024, 1, 3))
    assert len(obs) == 1
    assert obs[0].observation_date == date(2024, 1, 2)


async def test_fetch_latest_level_picks_most_recent(
    httpx_mock: HTTPXMock, cboe_connector: CboeConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        json=_fred_json(
            "VIXCLS",
            [("2024-01-01", "14.0"), ("2024-01-02", "14.5"), ("2024-01-03", "15.2")],
        ),
    )
    latest = await cboe_connector.fetch_latest_level("VIX", observation_date=date(2024, 1, 3))
    assert latest is not None
    assert latest.observation_date == date(2024, 1, 3)
    assert latest.value == 15.2


async def test_fetch_latest_level_empty_window_returns_none(
    httpx_mock: HTTPXMock, cboe_connector: CboeConnector
) -> None:
    httpx_mock.add_response(method="GET", json={"observations": []})
    latest = await cboe_connector.fetch_latest_level("VIX", date(2024, 1, 2))
    assert latest is None


async def test_fetch_latest_level_unknown_metric_raises(
    cboe_connector: CboeConnector,
) -> None:
    with pytest.raises(ValueError, match="Unknown CBOE metric"):
        await cboe_connector.fetch_latest_level("XXX", date(2024, 1, 2))


async def test_fetch_uses_cache(httpx_mock: HTTPXMock, cboe_connector: CboeConnector) -> None:
    httpx_mock.add_response(
        method="GET",
        json=_fred_json("VIXCLS", [("2024-01-02", "14.2")]),
    )
    first = await cboe_connector.fetch_vix(date(2024, 1, 2), date(2024, 1, 2))
    second = await cboe_connector.fetch_vix(date(2024, 1, 2), date(2024, 1, 2))
    assert first == second
    assert len(httpx_mock.get_requests()) == 1
