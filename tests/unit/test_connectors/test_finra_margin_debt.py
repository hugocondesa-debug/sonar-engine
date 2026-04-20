"""Unit tests for FinraMarginDebtConnector (FRED quarterly)."""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta
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


# ---------------------------------------------------------------------------
# Live canary (CAL-071)
# ---------------------------------------------------------------------------


@pytest.mark.slow
async def test_live_canary_margin_recent(tmp_cache_dir: Path) -> None:
    """Fetch last 2 quarters margin debt; assert positive + plausible magnitude."""
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        pytest.skip("FRED_API_KEY not set")
    conn = FinraMarginDebtConnector(api_key=api_key, cache_dir=str(tmp_cache_dir))
    try:
        today = datetime.now(tz=UTC).date()
        # Quarterly series; 240d covers 2 quarters + publication lag (1-2mo).
        obs = await conn.fetch_series(today - timedelta(days=240), today)
        assert len(obs) >= 1
        for o in obs:
            # Historically margin debt ranges $100B-$1T (FRED series in $ millions).
            assert 100_000 < o.value_m_usd < 2_000_000, (
                f"Margin debt {o.observation_date}={o.value_m_usd}M out of band"
            )
    finally:
        await conn.aclose()
