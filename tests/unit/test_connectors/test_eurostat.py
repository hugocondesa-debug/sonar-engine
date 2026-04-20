"""Unit tests for EurostatConnector (JSON-stat 2.0 parse + schema-drift guard)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from tenacity import wait_none

from sonar.connectors.eurostat import (
    EUROSTAT_BASE_URL,
    EurostatConnector,
    EurostatObservation,
    SchemaChangedError,
    _parse_jsonstat,
    _period_label_to_date,
    resolve_ea_geo_code,
)
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pytest_httpx import HTTPXMock


CASSETTE_DIR = Path(__file__).parent.parent.parent / "cassettes" / "connectors"


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "eurostat_cache"
    d.mkdir()
    return d


@pytest_asyncio.fixture
async def eurostat_connector(
    tmp_cache_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[EurostatConnector]:
    monkeypatch.setattr(EurostatConnector._fetch_raw.retry, "wait", wait_none())
    conn = EurostatConnector(cache_dir=str(tmp_cache_dir), rate_limit_seconds=0.0)
    yield conn
    await conn.aclose()


def _load_cassette(name: str) -> dict:
    return json.loads((CASSETTE_DIR / name).read_text())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_url_constant() -> None:
    assert EUROSTAT_BASE_URL == "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1"


def test_period_label_year() -> None:
    assert _period_label_to_date("2024") == date(2024, 12, 31)


def test_period_label_quarter() -> None:
    assert _period_label_to_date("2024-Q1") == date(2024, 3, 31)
    assert _period_label_to_date("2024-Q2") == date(2024, 6, 30)
    assert _period_label_to_date("2024-Q3") == date(2024, 9, 30)
    assert _period_label_to_date("2024-Q4") == date(2024, 12, 31)


def test_period_label_month() -> None:
    assert _period_label_to_date("2024-01") == date(2024, 1, 31)
    assert _period_label_to_date("2024-02") == date(2024, 2, 29)  # leap year
    assert _period_label_to_date("2023-02") == date(2023, 2, 28)
    assert _period_label_to_date("2024-12") == date(2024, 12, 31)


def test_period_label_iso_date() -> None:
    assert _period_label_to_date("2024-01-15") == date(2024, 1, 15)


def test_resolve_ea_geo_code() -> None:
    assert resolve_ea_geo_code(date(2022, 12, 31)) == "EA19"
    assert resolve_ea_geo_code(date(2023, 1, 1)) == "EA20"
    assert resolve_ea_geo_code(date(2024, 6, 30)) == "EA20"


# ---------------------------------------------------------------------------
# Cassette replay
# ---------------------------------------------------------------------------


async def test_fetch_une_rt_de_from_cassette(
    httpx_mock: HTTPXMock, eurostat_connector: EurostatConnector
) -> None:
    payload = _load_cassette("eurostat_une_rt_m_de_2024_01_02.json")
    httpx_mock.add_response(method="GET", json=payload)
    obs = await eurostat_connector.fetch_series(
        dataflow="une_rt_m",
        geo="DE",
        key="M.NSA.TOTAL.PC_ACT.T.DE",
        start_period="2023-01",
        end_period="2024-06",
    )
    assert len(obs) >= 12  # monthly series across >= 1y window
    assert all(isinstance(o, EurostatObservation) for o in obs)
    assert all(o.dataflow == "une_rt_m" for o in obs)
    assert all(o.geo == "DE" for o in obs)
    # Unemployment rates in DE historically in [2, 15] % range.
    for o in obs:
        assert 0 < o.value < 30


async def test_fetch_gdp_de_from_cassette(
    httpx_mock: HTTPXMock, eurostat_connector: EurostatConnector
) -> None:
    payload = _load_cassette("eurostat_namq_10_gdp_de_2024_01_02.json")
    httpx_mock.add_response(method="GET", json=payload)
    obs = await eurostat_connector.fetch_series(
        dataflow="namq_10_gdp",
        geo="DE",
        key="Q.CLV20_MEUR.SCA.B1GQ.DE",
        start_period="2020",
        end_period="2024",
    )
    assert len(obs) >= 8  # quarterly over multiple years
    assert all(o.time_period.startswith("20") and "Q" in o.time_period for o in obs)
    # DE quarterly GDP in CLV20 €M: historically 5-900k range.
    for o in obs:
        assert 500_000 < o.value < 2_000_000


async def test_fetch_uses_cache(
    httpx_mock: HTTPXMock, eurostat_connector: EurostatConnector
) -> None:
    payload = _load_cassette("eurostat_une_rt_m_de_2024_01_02.json")
    httpx_mock.add_response(method="GET", json=payload)
    first = await eurostat_connector.fetch_series(
        dataflow="une_rt_m",
        geo="DE",
        key="M.NSA.TOTAL.PC_ACT.T.DE",
        start_period="2023-01",
        end_period="2024-06",
    )
    second = await eurostat_connector.fetch_series(
        dataflow="une_rt_m",
        geo="DE",
        key="M.NSA.TOTAL.PC_ACT.T.DE",
        start_period="2023-01",
        end_period="2024-06",
    )
    assert first == second
    # Second call cache-hit — only one HTTP round-trip.
    assert len(httpx_mock.get_requests()) == 1


# ---------------------------------------------------------------------------
# Schema-drift guards
# ---------------------------------------------------------------------------


def test_parse_rejects_missing_id() -> None:
    with pytest.raises(SchemaChangedError, match="missing required key"):
        _parse_jsonstat({"size": [1, 1]}, expected_dataflow="x", expected_geo="DE")


def test_parse_rejects_id_size_length_mismatch() -> None:
    bad = {
        "id": ["freq", "geo", "time"],
        "size": [1, 1],  # missing time size
        "value": {},
        "dimension": {"time": {"category": {"index": {"2024-01": 0}}}},
    }
    with pytest.raises(SchemaChangedError, match="length mismatch"):
        _parse_jsonstat(bad, expected_dataflow="x", expected_geo="DE")


def test_parse_rejects_missing_time_dimension() -> None:
    bad = {
        "id": ["freq", "geo"],
        "size": [1, 1],
        "value": {"0": 1.0},
        "dimension": {
            "freq": {"category": {"index": {"M": 0}}},
            "geo": {"category": {"index": {"DE": 0}}},
        },
    }
    with pytest.raises(SchemaChangedError, match="missing time dimension"):
        _parse_jsonstat(bad, expected_dataflow="x", expected_geo="DE")


def test_parse_rejects_multi_select_dim() -> None:
    bad = {
        "id": ["freq", "time"],
        "size": [2, 1],  # freq size=2 (multi-select) not supported
        "value": {"0": 1.0, "1": 2.0},
        "dimension": {
            "freq": {"category": {"index": {"M": 0, "Q": 1}}},
            "time": {"category": {"index": {"2024-01": 0}}},
        },
    }
    with pytest.raises(SchemaChangedError, match="single-select"):
        _parse_jsonstat(bad, expected_dataflow="x", expected_geo="DE")


def test_schema_changed_is_subclass_of_data_unavailable() -> None:
    assert issubclass(SchemaChangedError, DataUnavailableError)


# ---------------------------------------------------------------------------
# Dataclass behaviour
# ---------------------------------------------------------------------------


def test_observation_is_frozen_and_slotted() -> None:
    obs = EurostatObservation(
        observation_date=date(2024, 1, 31),
        value=3.5,
        dataflow="une_rt_m",
        geo="DE",
        time_period="2024-01",
    )
    assert obs.source == "EUROSTAT"
    with pytest.raises(AttributeError):
        obs.value = 9.9  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Live canary (CAL-080)
# ---------------------------------------------------------------------------


@pytest.mark.slow
async def test_live_canary_une_rt_de(tmp_cache_dir: Path) -> None:
    """Fetch live DE unemployment rate for last 12m; assert sensible band."""
    conn = EurostatConnector(cache_dir=str(tmp_cache_dir), rate_limit_seconds=0.5)
    try:
        today = datetime.now(tz=UTC).date()
        start = (today - timedelta(days=365)).strftime("%Y-%m")
        end = today.strftime("%Y-%m")
        obs = await conn.fetch_series(
            dataflow="une_rt_m",
            geo="DE",
            key="M.NSA.TOTAL.PC_ACT.T.DE",
            start_period=start,
            end_period=end,
        )
        assert len(obs) >= 6
        for o in obs:
            assert 0 < o.value < 30
    finally:
        await conn.aclose()


@pytest.mark.slow
async def test_live_canary_gdp_de(tmp_cache_dir: Path) -> None:
    """Fetch live DE quarterly GDP CLV20 €M; plausible magnitude check."""
    conn = EurostatConnector(cache_dir=str(tmp_cache_dir), rate_limit_seconds=0.5)
    try:
        today = datetime.now(tz=UTC).date()
        obs = await conn.fetch_series(
            dataflow="namq_10_gdp",
            geo="DE",
            key="Q.CLV20_MEUR.SCA.B1GQ.DE",
            start_period=str(today.year - 2),
            end_period=str(today.year),
        )
        assert len(obs) >= 2
        for o in obs:
            assert 500_000 < o.value < 2_000_000
    finally:
        await conn.aclose()
