"""Unit tests for MoveIndexConnector (Yahoo Finance chart API)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from tenacity import wait_none

from sonar.connectors.move_index import (
    SANITY_MAX_LEVEL,
    SANITY_MIN_LEVEL,
    YAHOO_CHART_URL,
    MoveIndexConnector,
    MoveObservation,
)
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pytest_httpx import HTTPXMock


CASSETTE_DIR = Path(__file__).parent.parent.parent / "cassettes" / "connectors"


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "move_cache"
    d.mkdir()
    return d


@pytest_asyncio.fixture
async def move_connector(
    tmp_cache_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[MoveIndexConnector]:
    # Skip tenacity waits only for cassette-backed tests (fixture-scoped).
    monkeypatch.setattr(MoveIndexConnector._fetch_raw.retry, "wait", wait_none())
    conn = MoveIndexConnector(cache_dir=str(tmp_cache_dir))
    yield conn
    await conn.aclose()


def _load_cassette(name: str) -> dict:
    return json.loads((CASSETTE_DIR / name).read_text())


# ---------------------------------------------------------------------------
# Cassette replay
# ---------------------------------------------------------------------------


async def test_fetch_move_from_cassette(
    httpx_mock: HTTPXMock, move_connector: MoveIndexConnector
) -> None:
    payload = _load_cassette("move_yahoo_2024_01_02.json")
    httpx_mock.add_response(method="GET", json=payload)
    obs = await move_connector.fetch_move(date(2020, 1, 1), date(2030, 1, 1))
    assert len(obs) >= 1
    assert all(isinstance(o, MoveObservation) for o in obs)
    assert all(o.source == "Yahoo" for o in obs)
    assert all(o.source_series_id == "^MOVE" for o in obs)
    # Cassette values should be within MOVE sanity band.
    assert all(SANITY_MIN_LEVEL <= o.value_level <= SANITY_MAX_LEVEL for o in obs)


async def test_fetch_latest_from_cassette(
    httpx_mock: HTTPXMock, move_connector: MoveIndexConnector
) -> None:
    payload = _load_cassette("move_yahoo_2024_01_02.json")
    httpx_mock.add_response(method="GET", json=payload)
    max_ts = max(payload["chart"]["result"][0]["timestamp"])
    max_date = datetime.fromtimestamp(int(max_ts), tz=UTC).date()
    latest = await move_connector.fetch_latest(max_date, window_days=365 * 10)
    assert latest is not None
    assert latest.observation_date <= max_date


# ---------------------------------------------------------------------------
# Window selection
# ---------------------------------------------------------------------------


def test_yahoo_chart_url_constant() -> None:
    assert YAHOO_CHART_URL.startswith("https://query1.finance.yahoo.com/")
    assert "%5EMOVE" in YAHOO_CHART_URL  # URL-encoded ^MOVE ticker


# ---------------------------------------------------------------------------
# Schema-drift guards
# ---------------------------------------------------------------------------


async def test_parse_payload_missing_chart_raises() -> None:
    with pytest.raises(DataUnavailableError, match="schema drift"):
        MoveIndexConnector._parse_payload({"foo": "bar"})


async def test_parse_payload_empty_arrays_raises() -> None:
    bad = {"chart": {"result": [{"timestamp": [], "indicators": {"quote": [{"close": []}]}}]}}
    with pytest.raises(DataUnavailableError, match="empty or mis-aligned"):
        MoveIndexConnector._parse_payload(bad)


async def test_parse_payload_mismatched_arrays_raises() -> None:
    bad = {
        "chart": {
            "result": [
                {
                    "timestamp": [1, 2, 3],
                    "indicators": {"quote": [{"close": [10.0, 20.0]}]},
                }
            ]
        }
    }
    with pytest.raises(DataUnavailableError, match="empty or mis-aligned"):
        MoveIndexConnector._parse_payload(bad)


async def test_parse_payload_skips_none_close() -> None:
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [1_700_000_000, 1_700_086_400, 1_700_172_800],
                    "indicators": {"quote": [{"close": [100.0, None, 110.0]}]},
                }
            ]
        }
    }
    obs = MoveIndexConnector._parse_payload(payload)
    assert len(obs) == 2
    assert obs[0].value_level == 100.0
    assert obs[1].value_level == 110.0


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


async def test_fetch_uses_cache(httpx_mock: HTTPXMock, move_connector: MoveIndexConnector) -> None:
    httpx_mock.add_response(method="GET", json=_load_cassette("move_yahoo_2024_01_02.json"))
    first = await move_connector.fetch_move(date(2020, 1, 1), date(2030, 1, 1))
    second = await move_connector.fetch_move(date(2020, 1, 1), date(2030, 1, 1))
    assert first == second
    # Second fetch should be served from cache (no extra HTTP round-trip).
    assert len(httpx_mock.get_requests()) == 1


# ---------------------------------------------------------------------------
# Live canary (CAL-067) — skipped by default, runs under pytest -m slow
# ---------------------------------------------------------------------------


@pytest.mark.slow
async def test_live_canary_move_recent(tmp_cache_dir: Path) -> None:
    """Fetch MOVE for last 30 days; assert sanity band per HALT #4."""
    conn = MoveIndexConnector(cache_dir=str(tmp_cache_dir))
    try:
        today = datetime.now(tz=UTC).date()
        obs = await conn.fetch_move(today - timedelta(days=30), today)
        assert len(obs) >= 5
        for o in obs:
            assert SANITY_MIN_LEVEL <= o.value_level <= SANITY_MAX_LEVEL, (
                f"MOVE {o.observation_date} = {o.value_level} outside sanity band"
            )
    finally:
        await conn.aclose()
