"""Unit tests for YahooFinanceConnector (sprint6-3 c5)."""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from tenacity import wait_none

from sonar.connectors.yahoo_finance import (
    PUT_CALL_SANITY_MAX,
    PUT_CALL_SANITY_MIN,
    YAHOO_CHART_BASE_URL,
    YAHOO_SYMBOL_PUT_CALL,
    YahooFinanceConnector,
    YahooObservation,
)
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pytest_httpx import HTTPXMock


CASSETTE_DIR = Path(__file__).parent.parent.parent / "cassettes" / "connectors"


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "yahoo_cache"
    d.mkdir()
    return d


@pytest_asyncio.fixture
async def yahoo_connector(
    tmp_cache_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[YahooFinanceConnector]:
    monkeypatch.setattr(YahooFinanceConnector._fetch_raw.retry, "wait", wait_none())
    conn = YahooFinanceConnector(cache_dir=str(tmp_cache_dir))
    yield conn
    await conn.aclose()


def _load_cassette(name: str) -> dict:
    return json.loads((CASSETTE_DIR / name).read_text())


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_url_constant() -> None:
    assert YAHOO_CHART_BASE_URL == "https://query1.finance.yahoo.com/v7/finance/chart"


def test_put_call_symbol_constant() -> None:
    assert YAHOO_SYMBOL_PUT_CALL == "^CPC"


def test_put_call_sanity_band() -> None:
    assert PUT_CALL_SANITY_MIN == 0.3
    assert PUT_CALL_SANITY_MAX == 3.0


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def _mk_payload(timestamps: list[int], closes: list[float | None]) -> dict:
    return {
        "chart": {
            "result": [
                {
                    "meta": {"symbol": "^CPC"},
                    "timestamp": timestamps,
                    "indicators": {"quote": [{"close": closes}]},
                }
            ],
            "error": None,
        }
    }


def test_parse_happy_path() -> None:
    ts = [int(datetime(2024, 1, 2, tzinfo=UTC).timestamp())]
    payload = _mk_payload(ts, [0.85])
    obs = YahooFinanceConnector._parse_payload(payload, "^CPC")
    assert len(obs) == 1
    assert obs[0].observation_date == date(2024, 1, 2)
    assert obs[0].value_close == 0.85
    assert obs[0].symbol == "^CPC"


def test_parse_skips_null_close() -> None:
    ts = [
        int(datetime(2024, 1, 2, tzinfo=UTC).timestamp()),
        int(datetime(2024, 1, 3, tzinfo=UTC).timestamp()),
    ]
    payload = _mk_payload(ts, [0.85, None])
    obs = YahooFinanceConnector._parse_payload(payload, "^CPC")
    assert len(obs) == 1
    assert obs[0].observation_date == date(2024, 1, 2)


def test_parse_raises_on_missing_chart_result() -> None:
    with pytest.raises(DataUnavailableError, match="schema drift"):
        YahooFinanceConnector._parse_payload({"chart": {"result": []}}, "^CPC")


def test_parse_raises_on_mis_aligned_arrays() -> None:
    ts = [1, 2, 3]
    payload = _mk_payload(ts, [0.8, 0.9])  # fewer closes than timestamps
    with pytest.raises(DataUnavailableError, match="mis-aligned"):
        YahooFinanceConnector._parse_payload(payload, "^CPC")


def test_parse_raises_on_empty_arrays() -> None:
    with pytest.raises(DataUnavailableError, match="empty"):
        YahooFinanceConnector._parse_payload(_mk_payload([], []), "^CPC")


# ---------------------------------------------------------------------------
# Fetch + cassette
# ---------------------------------------------------------------------------


async def test_fetch_put_call_from_cassette(
    httpx_mock: HTTPXMock, yahoo_connector: YahooFinanceConnector
) -> None:
    httpx_mock.add_response(method="GET", json=_load_cassette("yahoo_cpc_put_call_2024_01_02.json"))
    obs = await yahoo_connector.fetch_put_call_ratio_us(date(2024, 1, 2), date(2024, 3, 5))
    assert len(obs) > 30
    assert all(isinstance(o, YahooObservation) for o in obs)
    assert all(o.symbol == "^CPC" for o in obs)
    for o in obs:
        assert PUT_CALL_SANITY_MIN <= o.value_close <= PUT_CALL_SANITY_MAX


async def test_fetch_latest_put_call(
    httpx_mock: HTTPXMock, yahoo_connector: YahooFinanceConnector
) -> None:
    httpx_mock.add_response(method="GET", json=_load_cassette("yahoo_cpc_put_call_2024_01_02.json"))
    latest = await yahoo_connector.fetch_latest_put_call(date(2024, 2, 15), window_days=30)
    assert latest is not None
    assert latest.observation_date <= date(2024, 2, 15)
    assert PUT_CALL_SANITY_MIN <= latest.value_close <= PUT_CALL_SANITY_MAX


async def test_fetch_uses_cache(
    httpx_mock: HTTPXMock, yahoo_connector: YahooFinanceConnector
) -> None:
    httpx_mock.add_response(method="GET", json=_load_cassette("yahoo_cpc_put_call_2024_01_02.json"))
    first = await yahoo_connector.fetch_put_call_ratio_us(date(2024, 1, 2), date(2024, 3, 5))
    second = await yahoo_connector.fetch_put_call_ratio_us(date(2024, 1, 2), date(2024, 3, 5))
    assert first == second
    assert len(httpx_mock.get_requests()) == 1


async def test_fetch_chart_generic_accepts_custom_range(
    httpx_mock: HTTPXMock, yahoo_connector: YahooFinanceConnector
) -> None:
    httpx_mock.add_response(method="GET", json=_load_cassette("yahoo_cpc_put_call_2024_01_02.json"))
    obs = await yahoo_connector.fetch_chart(
        "^CPC", date(2024, 1, 2), date(2024, 3, 5), range_str="3mo"
    )
    assert len(obs) > 30


# ---------------------------------------------------------------------------
# Live canary (CAL-073)
# ---------------------------------------------------------------------------


@pytest.mark.slow
async def test_live_canary_put_call_recent(tmp_cache_dir: Path) -> None:
    """Fetch last 30 days ^CPC via Yahoo; assert plausible band.

    Yahoo chart rate-limits aggressively on the bare endpoint; tenacity
    retry covers transient 429s. Declared slow so default CI skips.
    """
    conn = YahooFinanceConnector(cache_dir=str(tmp_cache_dir))
    try:
        today = datetime.now(tz=UTC).date()
        obs = await conn.fetch_put_call_ratio_us(today - timedelta(days=30), today)
        if not obs:
            pytest.skip("Yahoo rate-limited or empty window; see CAL-073")
        assert len(obs) >= 5
        for o in obs:
            assert PUT_CALL_SANITY_MIN <= o.value_close <= PUT_CALL_SANITY_MAX
    finally:
        await conn.aclose()


@pytest.mark.skipif(os.environ.get("SKIP_LIVE") == "1", reason="live canary disabled")
def test_observation_is_frozen() -> None:
    obs = YahooObservation(
        observation_date=date(2024, 1, 2),
        value_close=0.85,
        symbol="^CPC",
    )
    assert obs.source == "YAHOO"
    with pytest.raises(AttributeError):
        obs.value_close = 1.0  # type: ignore[misc]
