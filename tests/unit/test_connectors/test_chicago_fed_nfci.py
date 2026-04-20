"""Unit tests for ChicagoFedNfciConnector (NFCI + ANFCI via FRED)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from sonar.connectors.chicago_fed_nfci import (
    FRED_SERIES_ANFCI,
    FRED_SERIES_NFCI,
    ChicagoFedNfciConnector,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from pytest_httpx import HTTPXMock


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "nfci_cache"
    d.mkdir()
    return d


@pytest_asyncio.fixture
async def nfci_connector(
    tmp_cache_dir: Path,
) -> AsyncIterator[ChicagoFedNfciConnector]:
    conn = ChicagoFedNfciConnector(api_key="test-key", cache_dir=str(tmp_cache_dir))
    yield conn
    await conn.aclose()


def _fred_json(rows: list[tuple[str, str]]) -> dict:
    return {"observations": [{"date": d, "value": v} for d, v in rows]}


def test_series_constants() -> None:
    assert FRED_SERIES_NFCI == "NFCI"
    assert FRED_SERIES_ANFCI == "ANFCI"


async def test_fetch_nfci_weekly(
    httpx_mock: HTTPXMock, nfci_connector: ChicagoFedNfciConnector
) -> None:
    # NFCI is weekly (Wednesdays); 3 releases over 3 weeks.
    httpx_mock.add_response(
        method="GET",
        json=_fred_json(
            [
                ("2023-12-27", "-0.45"),
                ("2024-01-03", "-0.48"),
                ("2024-01-10", "-0.52"),
            ]
        ),
    )
    obs = await nfci_connector.fetch_nfci("NFCI", date(2023, 12, 15), date(2024, 1, 12))
    assert len(obs) == 3
    assert obs[0].metric == "NFCI"
    assert obs[0].value_zscore == -0.45


async def test_fetch_anfci(httpx_mock: HTTPXMock, nfci_connector: ChicagoFedNfciConnector) -> None:
    httpx_mock.add_response(method="GET", json=_fred_json([("2024-01-03", "0.10")]))
    obs = await nfci_connector.fetch_nfci("ANFCI", date(2024, 1, 1), date(2024, 1, 10))
    assert obs[0].metric == "ANFCI"
    assert obs[0].source_series_id == FRED_SERIES_ANFCI


async def test_unknown_metric_raises(
    nfci_connector: ChicagoFedNfciConnector,
) -> None:
    with pytest.raises(ValueError, match="Unknown NFCI metric"):
        await nfci_connector.fetch_nfci("XYZ", date(2024, 1, 1), date(2024, 1, 10))


async def test_fetch_latest_14d_window(
    httpx_mock: HTTPXMock, nfci_connector: ChicagoFedNfciConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        json=_fred_json([("2024-01-03", "-0.40"), ("2024-01-10", "-0.50")]),
    )
    latest = await nfci_connector.fetch_latest("NFCI", date(2024, 1, 12))
    assert latest is not None
    assert latest.observation_date == date(2024, 1, 10)
    assert latest.value_zscore == -0.50


async def test_fetch_latest_empty_returns_none(
    httpx_mock: HTTPXMock, nfci_connector: ChicagoFedNfciConnector
) -> None:
    httpx_mock.add_response(method="GET", json={"observations": []})
    latest = await nfci_connector.fetch_latest("NFCI", date(2024, 1, 12))
    assert latest is None


async def test_fetch_skips_sentinel_dots(
    httpx_mock: HTTPXMock, nfci_connector: ChicagoFedNfciConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        json=_fred_json([("2024-01-01", "."), ("2024-01-03", "-0.45"), ("2024-01-10", ".")]),
    )
    obs = await nfci_connector.fetch_nfci("NFCI", date(2024, 1, 1), date(2024, 1, 10))
    assert len(obs) == 1
    assert obs[0].observation_date == date(2024, 1, 3)
