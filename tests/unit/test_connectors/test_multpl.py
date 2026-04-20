"""Unit tests for MultplConnector — HTML regex extraction + graceful fail."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from tenacity import RetryError, wait_none

from sonar.connectors.multpl import (
    DataUnavailableError,
    MultplConnector,
    _extract_dividend_yield,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from pytest_httpx import HTTPXMock


SAMPLE_HTML_OK = (
    "<html><head>"
    '<meta name="description" content="S&P 500 Dividend Yield chart, '
    "historic, and current data. Current S&P 500 Dividend Yield is 1.10%, "
    'a change of -1.37 bps from previous market close." />'
    "</head><body></body></html>"
)

SAMPLE_HTML_BROKEN = "<html><body>no dividend marker here</body></html>"


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "multpl_cache"
    d.mkdir()
    return d


@pytest.fixture(autouse=True)
def _disable_tenacity_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MultplConnector._download.retry, "wait", wait_none())


@pytest_asyncio.fixture
async def multpl(tmp_cache_dir: Path) -> AsyncIterator[MultplConnector]:
    conn = MultplConnector(cache_dir=str(tmp_cache_dir))
    yield conn
    await conn.aclose()


def test_extract_dividend_yield_known_good() -> None:
    result = _extract_dividend_yield(SAMPLE_HTML_OK)
    assert result == pytest.approx(0.011)


def test_extract_dividend_yield_missing_raises() -> None:
    with pytest.raises(DataUnavailableError, match="did not contain"):
        _extract_dividend_yield(SAMPLE_HTML_BROKEN)


def test_extract_dividend_yield_rejects_current_date(tmp_path: Path) -> None:
    # Makes sure the regex anchors on "Current" and parses decimal correctly.
    html = SAMPLE_HTML_OK.replace("1.10%", "2.55%")
    assert _extract_dividend_yield(html) == pytest.approx(0.0255)


async def test_fetch_dividend_happy(httpx_mock: HTTPXMock, multpl: MultplConnector) -> None:
    httpx_mock.add_response(method="GET", text=SAMPLE_HTML_OK)
    result = await multpl.fetch_current_dividend_yield_decimal()
    assert result == pytest.approx(0.011)


async def test_fetch_dividend_broken_html_raises(
    httpx_mock: HTTPXMock, multpl: MultplConnector
) -> None:
    httpx_mock.add_response(method="GET", text=SAMPLE_HTML_BROKEN)
    with pytest.raises(DataUnavailableError):
        await multpl.fetch_current_dividend_yield_decimal()


async def test_fetch_dividend_cache_hit_no_http(
    httpx_mock: HTTPXMock, multpl: MultplConnector
) -> None:
    _ = httpx_mock
    multpl.cache.set("multpl:dividend_yield", 0.013)
    result = await multpl.fetch_current_dividend_yield_decimal()
    assert result == pytest.approx(0.013)


async def test_fetch_dividend_404_raises(httpx_mock: HTTPXMock, multpl: MultplConnector) -> None:
    for _ in range(3):
        httpx_mock.add_response(method="GET", status_code=404, text="not found")
    with pytest.raises(RetryError):
        await multpl.fetch_current_dividend_yield_decimal()
