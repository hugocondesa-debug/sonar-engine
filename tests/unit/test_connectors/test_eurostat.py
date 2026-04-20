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
    DATAFLOW_CONSUMER_CONFIDENCE,
    DATAFLOW_ECONOMIC_SENTIMENT,
    DATAFLOW_EMPLOYMENT_QUARTERLY,
    DATAFLOW_GDP_QUARTERLY,
    DATAFLOW_INDUSTRIAL_PRODUCTION,
    DATAFLOW_RETAIL_TRADE,
    DATAFLOW_UNEMPLOYMENT_RATE,
    EUROSTAT_BASE_URL,
    EurostatConnector,
    EurostatObservation,
    SchemaChangedError,
    _parse_jsonstat,
    _period_label_to_date,
    resolve_ea_geo_code,
    yoy_transform,
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


# ---------------------------------------------------------------------------
# yoy_transform
# ---------------------------------------------------------------------------


def _mk_obs(d: date, v: float) -> EurostatObservation:
    return EurostatObservation(
        observation_date=d,
        value=v,
        dataflow="x",
        geo="DE",
        time_period=d.isoformat(),
    )


def test_yoy_transform_quarterly() -> None:
    levels = [
        _mk_obs(date(2023, 3, 31), 100.0),
        _mk_obs(date(2023, 6, 30), 101.0),
        _mk_obs(date(2023, 9, 30), 102.0),
        _mk_obs(date(2023, 12, 31), 103.0),
        _mk_obs(date(2024, 3, 31), 105.0),
        _mk_obs(date(2024, 6, 30), 106.0),
    ]
    yoy = yoy_transform(levels, periods_per_year=4)
    assert len(yoy) == 2
    assert yoy[0].observation_date == date(2024, 3, 31)
    assert yoy[0].value == pytest.approx(0.05, abs=1e-9)
    assert yoy[1].value == pytest.approx((106.0 - 101.0) / 101.0, abs=1e-9)


def test_yoy_transform_empty() -> None:
    assert yoy_transform([], periods_per_year=12) == []


def test_yoy_transform_skips_zero_prior() -> None:
    levels = [_mk_obs(date(2023, 1, 31), 0.0), _mk_obs(date(2024, 1, 31), 5.0)]
    assert yoy_transform(levels, periods_per_year=12) == []


# ---------------------------------------------------------------------------
# Helper cassette tests
# ---------------------------------------------------------------------------


async def test_fetch_gdp_real_yoy_de(
    httpx_mock: HTTPXMock, eurostat_connector: EurostatConnector
) -> None:
    payload = _load_cassette("eurostat_namq_10_gdp_de_2024_01_02.json")
    httpx_mock.add_response(method="GET", json=payload)
    yoy = await eurostat_connector.fetch_gdp_real_yoy("DE", date(2024, 1, 1), date(2024, 12, 31))
    # Cassette covers 2020-2024 (20 quarters); YoY drops first 4 → up to 16.
    assert 1 <= len(yoy) <= 20
    for o in yoy:
        # German real GDP YoY historically ± 10% outside wartime/COVID.
        assert -0.2 < o.value < 0.2


async def test_fetch_industrial_production_yoy_de(
    httpx_mock: HTTPXMock, eurostat_connector: EurostatConnector
) -> None:
    payload = _load_cassette("eurostat_ip_sts_inpr_m_de_2024_01_02.json")
    httpx_mock.add_response(method="GET", json=payload)
    yoy = await eurostat_connector.fetch_industrial_production_yoy(
        "DE", date(2023, 1, 1), date(2024, 6, 30)
    )
    assert len(yoy) >= 6  # 30 months - 12 for YoY = 18 usable points
    for o in yoy:
        assert -0.3 < o.value < 0.3


async def test_fetch_employment_yoy_de(
    httpx_mock: HTTPXMock, eurostat_connector: EurostatConnector
) -> None:
    payload = _load_cassette("eurostat_emp_namq_10_pe_de_2024_01_02.json")
    httpx_mock.add_response(method="GET", json=payload)
    yoy = await eurostat_connector.fetch_employment_yoy("DE", date(2022, 1, 1), date(2024, 12, 31))
    assert len(yoy) >= 4
    for o in yoy:
        # German employment growth rarely deviates outside ±5%.
        assert -0.1 < o.value < 0.1


async def test_fetch_retail_sales_real_yoy_de(
    httpx_mock: HTTPXMock, eurostat_connector: EurostatConnector
) -> None:
    payload = _load_cassette("eurostat_retail_sts_trtu_m_de_2024_01_02.json")
    httpx_mock.add_response(method="GET", json=payload)
    yoy = await eurostat_connector.fetch_retail_sales_real_yoy(
        "DE", date(2023, 1, 1), date(2024, 6, 30)
    )
    assert len(yoy) >= 1
    for o in yoy:
        assert -0.3 < o.value < 0.3


async def test_fetch_unemployment_rate_de(
    httpx_mock: HTTPXMock, eurostat_connector: EurostatConnector
) -> None:
    payload = _load_cassette("eurostat_une_rt_m_de_2024_01_02.json")
    httpx_mock.add_response(method="GET", json=payload)
    obs = await eurostat_connector.fetch_unemployment_rate(
        "DE", date(2023, 1, 1), date(2024, 6, 30)
    )
    assert len(obs) >= 12
    for o in obs:
        assert 0 < o.value < 30
    assert obs[0].dataflow == DATAFLOW_UNEMPLOYMENT_RATE


async def test_fetch_economic_sentiment_indicator_de(
    httpx_mock: HTTPXMock, eurostat_connector: EurostatConnector
) -> None:
    payload = _load_cassette("eurostat_esi_ei_bssi_m_r2_de_2024_01_02.json")
    httpx_mock.add_response(method="GET", json=payload)
    obs = await eurostat_connector.fetch_economic_sentiment_indicator(
        "DE", date(2022, 1, 1), date(2024, 6, 30)
    )
    assert len(obs) >= 12
    # ESI is indexed on a long-run mean of 100.
    for o in obs:
        assert 0 < o.value < 200
    assert obs[0].dataflow == DATAFLOW_ECONOMIC_SENTIMENT


async def test_fetch_consumer_confidence_de(
    httpx_mock: HTTPXMock, eurostat_connector: EurostatConnector
) -> None:
    payload = _load_cassette("eurostat_consconf_ei_bsco_m_de_2024_01_02.json")
    httpx_mock.add_response(method="GET", json=payload)
    obs = await eurostat_connector.fetch_consumer_confidence(
        "DE", date(2022, 1, 1), date(2024, 6, 30)
    )
    assert len(obs) >= 12
    # Consumer confidence balance ∈ [-100, +100].
    for o in obs:
        assert -100 <= o.value <= 100
    assert obs[0].dataflow == DATAFLOW_CONSUMER_CONFIDENCE


def test_dataflow_constants() -> None:
    assert DATAFLOW_GDP_QUARTERLY == "namq_10_gdp"
    assert DATAFLOW_INDUSTRIAL_PRODUCTION == "sts_inpr_m"
    assert DATAFLOW_EMPLOYMENT_QUARTERLY == "namq_10_pe"
    assert DATAFLOW_RETAIL_TRADE == "sts_trtu_m"
    assert DATAFLOW_UNEMPLOYMENT_RATE == "une_rt_m"
    assert DATAFLOW_ECONOMIC_SENTIMENT == "ei_bssi_m_r2"
    assert DATAFLOW_CONSUMER_CONFIDENCE == "ei_bsco_m"


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
