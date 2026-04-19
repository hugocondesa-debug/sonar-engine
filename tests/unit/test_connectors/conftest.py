"""Shared fixtures for connector tests."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from tenacity import wait_none

from sonar.connectors.fred import FredConnector


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "cache"
    d.mkdir()
    return d


@pytest.fixture(autouse=True)
def _disable_tenacity_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch tenacity wait → wait_none() so retry tests run instantly.

    Applies to FredConnector._fetch_raw retry config. Autouse: zero caller
    boilerplate. Real waits restored after each test via monkeypatch.
    """
    monkeypatch.setattr(FredConnector._fetch_raw.retry, "wait", wait_none())


@pytest_asyncio.fixture
async def fred_connector(tmp_cache_dir: Path) -> AsyncIterator[FredConnector]:
    conn = FredConnector(api_key="test_key", cache_dir=str(tmp_cache_dir))
    yield conn
    await conn.aclose()
