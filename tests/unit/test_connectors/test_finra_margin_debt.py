"""Unit tests for FinraMarginDebtConnector (FRED quarterly)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from sonar.connectors.finra_margin_debt import (
    FRED_SERIES_MARGIN_DEBT,
    FinraMarginDebtConnector,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from pytest_httpx import HTTPXMock


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "finra_cache"
    d.mkdir()
    return d


@pytest_asyncio.fixture
async def finra_connector(
    tmp_cache_dir: Path,
) -> AsyncIterator[FinraMarginDebtConnector]:
    conn = FinraMarginDebtConnector(api_key="test-key", cache_dir=str(tmp_cache_dir))
    yield conn
    await conn.aclose()


def _fred_json(rows: list[tuple[str, str]]) -> dict:
    return {"observations": [{"date": d, "value": v} for d, v in rows]}


def test_series_constant() -> None:
    assert FRED_SERIES_MARGIN_DEBT == "BOGZ1FL663067003Q"


async def test_fetch_series_quarterly(
    httpx_mock: HTTPXMock, finra_connector: FinraMarginDebtConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        json=_fred_json(
            [
                ("2023-09-30", "820000.0"),
                ("2023-12-31", "835000.0"),
                ("2024-03-31", "851000.0"),
            ]
        ),
    )
    obs = await finra_connector.fetch_series(date(2023, 9, 30), date(2024, 3, 31))
    assert len(obs) == 3
    assert obs[0].value_m_usd == 820_000.0
    assert obs[0].source == "FRED"
    assert obs[0].source_series_id == FRED_SERIES_MARGIN_DEBT


async def test_fetch_latest_wider_window(
    httpx_mock: HTTPXMock, finra_connector: FinraMarginDebtConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        json=_fred_json([("2023-12-31", "820000.0"), ("2024-03-31", "851000.0")]),
    )
    # Request a date > 60d after latest obs; default window=180d should still find.
    latest = await finra_connector.fetch_latest(date(2024, 5, 15))
    assert latest is not None
    assert latest.observation_date == date(2024, 3, 31)


async def test_fetch_latest_empty_returns_none(
    httpx_mock: HTTPXMock, finra_connector: FinraMarginDebtConnector
) -> None:
    httpx_mock.add_response(method="GET", json={"observations": []})
    latest = await finra_connector.fetch_latest(date(2024, 5, 15))
    assert latest is None


async def test_fetch_skips_sentinel(
    httpx_mock: HTTPXMock, finra_connector: FinraMarginDebtConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        json=_fred_json([("2023-09-30", "."), ("2023-12-31", "820000.0")]),
    )
    obs = await finra_connector.fetch_series(date(2023, 9, 30), date(2024, 3, 31))
    assert len(obs) == 1
    assert obs[0].observation_date == date(2023, 12, 31)
