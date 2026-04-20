"""Unit tests for IceBofaOasConnector (HY + IG + BBB via FRED)."""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from sonar.connectors.ice_bofa_oas import (
    FRED_SERIES_BBB_OAS,
    FRED_SERIES_HY_OAS,
    FRED_SERIES_IG_OAS,
    IceBofaOasConnector,
    OasObservation,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pytest_httpx import HTTPXMock


CASSETTE_DIR = Path(__file__).parent.parent.parent / "cassettes" / "connectors"


def _load_cassette(name: str) -> dict:
    return json.loads((CASSETTE_DIR / name).read_text())


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "oas_cache"
    d.mkdir()
    return d


@pytest_asyncio.fixture
async def oas_connector(tmp_cache_dir: Path) -> AsyncIterator[IceBofaOasConnector]:
    conn = IceBofaOasConnector(api_key="test-key", cache_dir=str(tmp_cache_dir))
    yield conn
    await conn.aclose()


def _fred_json(rows: list[tuple[str, str]]) -> dict:
    return {"observations": [{"date": d, "value": v} for d, v in rows]}


def test_series_constants() -> None:
    assert FRED_SERIES_HY_OAS == "BAMLH0A0HYM2"
    assert FRED_SERIES_IG_OAS == "BAMLC0A0CM"
    assert FRED_SERIES_BBB_OAS == "BAMLC0A4CBBB"


async def test_fetch_hy_oas(httpx_mock: HTTPXMock, oas_connector: IceBofaOasConnector) -> None:
    httpx_mock.add_response(
        method="GET",
        json=_fred_json([("2024-01-02", "3.20"), ("2024-01-03", "3.15")]),
    )
    obs = await oas_connector.fetch_oas("HY", date(2024, 1, 2), date(2024, 1, 3))
    assert len(obs) == 2
    assert obs[0].metric == "HY"
    assert obs[0].value_pct == 3.20
    assert obs[0].value_bps == 320
    assert obs[0].source_series_id == FRED_SERIES_HY_OAS


async def test_fetch_ig_oas(httpx_mock: HTTPXMock, oas_connector: IceBofaOasConnector) -> None:
    httpx_mock.add_response(method="GET", json=_fred_json([("2024-01-02", "1.05")]))
    obs = await oas_connector.fetch_oas("IG", date(2024, 1, 2), date(2024, 1, 2))
    assert obs[0].metric == "IG"
    assert obs[0].value_bps == 105


async def test_fetch_bbb_oas(httpx_mock: HTTPXMock, oas_connector: IceBofaOasConnector) -> None:
    httpx_mock.add_response(method="GET", json=_fred_json([("2024-01-02", "1.55")]))
    obs = await oas_connector.fetch_oas("BBB", date(2024, 1, 2), date(2024, 1, 2))
    assert obs[0].source_series_id == FRED_SERIES_BBB_OAS


async def test_unknown_metric_raises(oas_connector: IceBofaOasConnector) -> None:
    with pytest.raises(ValueError, match="Unknown OAS metric"):
        await oas_connector.fetch_oas("JUNK", date(2024, 1, 1), date(2024, 1, 2))


async def test_fetch_latest_returns_most_recent(
    httpx_mock: HTTPXMock, oas_connector: IceBofaOasConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        json=_fred_json([("2024-01-01", "3.20"), ("2024-01-02", "3.15"), ("2024-01-03", "3.10")]),
    )
    latest = await oas_connector.fetch_latest("HY", date(2024, 1, 3))
    assert latest is not None
    assert latest.observation_date == date(2024, 1, 3)
    assert latest.value_pct == 3.10


async def test_fetch_latest_empty_returns_none(
    httpx_mock: HTTPXMock, oas_connector: IceBofaOasConnector
) -> None:
    httpx_mock.add_response(method="GET", json={"observations": []})
    latest = await oas_connector.fetch_latest("HY", date(2024, 1, 2))
    assert latest is None


def test_value_bps_conversion() -> None:
    obs = OasObservation(
        observation_date=date(2024, 1, 2),
        value_pct=4.25,
        metric="HY",
        source_series_id=FRED_SERIES_HY_OAS,
    )
    assert obs.value_bps == 425


# ---------------------------------------------------------------------------
# Cassette replay (CAL-071: captured FRED BAMLH0A0HYM2 2023-12-01..2024-01-05)
# ---------------------------------------------------------------------------


async def test_fetch_hy_from_cassette(
    httpx_mock: HTTPXMock, oas_connector: IceBofaOasConnector
) -> None:
    payload = _load_cassette("ice_bofa_hy_oas_2024_01_02.json")
    httpx_mock.add_response(method="GET", json=payload)
    obs = await oas_connector.fetch_oas("HY", date(2023, 12, 1), date(2024, 1, 5))
    # Parser skips FRED "." sentinel rows, so obs count ≤ raw count.
    assert 1 <= len(obs) <= len(payload["observations"])
    for o in obs:
        assert 100 <= o.value_bps <= 2500
        assert o.metric == "HY"


# ---------------------------------------------------------------------------
# Live canary (CAL-071)
# ---------------------------------------------------------------------------


@pytest.mark.slow
async def test_live_canary_hy_oas_recent(tmp_cache_dir: Path) -> None:
    """Fetch last 30 days BAMLH0A0HYM2; assert plausible [100, 2500] bps band."""
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        pytest.skip("FRED_API_KEY not set")
    conn = IceBofaOasConnector(api_key=api_key, cache_dir=str(tmp_cache_dir))
    try:
        today = datetime.now(tz=UTC).date()
        obs = await conn.fetch_oas("HY", today - timedelta(days=30), today)
        assert len(obs) >= 10  # ~20 trading days in 30d window
        for o in obs:
            assert 100 <= o.value_bps <= 2500, (
                f"HY OAS {o.observation_date}={o.value_bps}bps out of band"
            )
    finally:
        await conn.aclose()
