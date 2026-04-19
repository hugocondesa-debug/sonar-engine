"""Unit tests for BundesbankConnector — pytest-httpx mocked CSV responses."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from tenacity import wait_none

from sonar.connectors.bundesbank import (
    BUNDESBANK_DE_NOMINAL_SERIES,
    BUNDESBANK_SERIES_TENORS,
    BundesbankConnector,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from pytest_httpx import HTTPXMock


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "bb_cache"
    d.mkdir()
    return d


@pytest.fixture(autouse=True)
def _disable_tenacity_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(BundesbankConnector._fetch_raw.retry, "wait", wait_none())


@pytest_asyncio.fixture
async def bb_connector(tmp_cache_dir: Path) -> AsyncIterator[BundesbankConnector]:
    conn = BundesbankConnector(cache_dir=str(tmp_cache_dir))
    yield conn
    await conn.aclose()


def _csv(rows: list[tuple[str, str]]) -> str:
    """German-locale CSV body: 5-line header + data rows ``YYYY-MM-DD;v,vv;``."""
    header = (
        '"";BBSIS.D.X;FLAGS\n'
        '"";Series title;\n'
        "Einheit;PROZENT;\n"
        "Dimension;Eins;\n"
        "Stand vom;17.04.2026 12:15:04 Uhr;\n"
    )
    body = "".join(f"{date};{value};\n" for date, value in rows)
    return header + body


def test_series_mapping_sanity() -> None:
    assert len(BUNDESBANK_DE_NOMINAL_SERIES) == 9  # 1Y..30Y subset
    assert "10Y" in BUNDESBANK_DE_NOMINAL_SERIES
    assert "1M" not in BUNDESBANK_DE_NOMINAL_SERIES  # short-end out of scope
    assert "30Y" in BUNDESBANK_DE_NOMINAL_SERIES
    for series_id in BUNDESBANK_DE_NOMINAL_SERIES.values():
        assert series_id in BUNDESBANK_SERIES_TENORS


async def test_fetch_series_happy_german_decimal(
    httpx_mock: HTTPXMock, bb_connector: BundesbankConnector
) -> None:
    series = BUNDESBANK_DE_NOMINAL_SERIES["10Y"]
    httpx_mock.add_response(
        method="GET",
        text=_csv([("2024-01-02", "2,13"), ("2024-01-03", "2,15")]),
    )
    obs = await bb_connector.fetch_series(series, date(2024, 1, 2), date(2024, 1, 3))
    assert len(obs) == 2
    assert all(o.country_code == "DE" for o in obs)
    assert all(o.tenor_years == 10.0 for o in obs)
    assert all(o.source == "BUNDESBANK" for o in obs)
    assert obs[0].yield_bps == 213
    assert obs[1].yield_bps == 215


async def test_fetch_series_filters_sentinel(
    httpx_mock: HTTPXMock, bb_connector: BundesbankConnector
) -> None:
    series = BUNDESBANK_DE_NOMINAL_SERIES["10Y"]
    httpx_mock.add_response(
        method="GET",
        text=_csv([("2024-01-02", "2,13"), ("2024-01-03", "."), ("2024-01-04", "2,18")]),
    )
    obs = await bb_connector.fetch_series(series, date(2024, 1, 2), date(2024, 1, 4))
    assert len(obs) == 2
    assert obs[1].yield_bps == 218


async def test_fetch_series_window_filter(
    httpx_mock: HTTPXMock, bb_connector: BundesbankConnector
) -> None:
    """Bundesbank serves full history; connector filters to [start, end] in-process."""
    series = BUNDESBANK_DE_NOMINAL_SERIES["10Y"]
    httpx_mock.add_response(
        method="GET",
        text=_csv(
            [
                ("2023-12-29", "2,10"),
                ("2024-01-02", "2,13"),
                ("2024-01-03", "2,15"),
                ("2024-01-04", "2,18"),
            ]
        ),
    )
    obs = await bb_connector.fetch_series(series, date(2024, 1, 2), date(2024, 1, 3))
    assert {o.observation_date for o in obs} == {date(2024, 1, 2), date(2024, 1, 3)}


async def test_fetch_series_unknown_raises(
    httpx_mock: HTTPXMock, bb_connector: BundesbankConnector
) -> None:
    _ = httpx_mock
    with pytest.raises(ValueError, match="Unknown Bundesbank series"):
        await bb_connector.fetch_series("BOGUS", date(2024, 1, 2), date(2024, 1, 2))


async def test_fetch_yield_curve_nominal_aggregates_9_tenors(
    httpx_mock: HTTPXMock, bb_connector: BundesbankConnector
) -> None:
    for idx, _series_id in enumerate(BUNDESBANK_DE_NOMINAL_SERIES.values()):
        httpx_mock.add_response(
            method="GET",
            text=_csv([("2024-01-02", f"{2.0 + idx * 0.05:,.2f}".replace(".", ","))]),
        )
    curve = await bb_connector.fetch_yield_curve_nominal(
        country="DE", observation_date=date(2024, 1, 2)
    )
    assert set(curve.keys()) == set(BUNDESBANK_DE_NOMINAL_SERIES.keys())
    assert curve["10Y"].tenor_years == 10.0


async def test_fetch_yield_curve_rejects_non_de(
    httpx_mock: HTTPXMock, bb_connector: BundesbankConnector
) -> None:
    _ = httpx_mock
    with pytest.raises(ValueError, match="only supports country=DE"):
        await bb_connector.fetch_yield_curve_nominal(
            country="FR", observation_date=date(2024, 1, 2)
        )
