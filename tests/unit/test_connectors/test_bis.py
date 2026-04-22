"""Unit tests for BisConnector — SDMX-JSON 1.0 response parsing."""

from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from tenacity import wait_none

from sonar.connectors.bis import (
    ACCEPT_HEADER,
    AGENCY_ID,
    BASE_URL,
    BIS_EER_COUNTRY_CODES,
    DATAFLOW_VERSIONS,
    BisConnector,
    BisEerObservation,
    BisObservation,
    _date_to_period,
    _month_label_to_end_date,
    _parse_series,
    _quarter_label_to_end_date,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pytest_httpx import HTTPXMock


FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "bis"


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "bis_cache"
    d.mkdir()
    return d


@pytest.fixture(autouse=True)
def _disable_tenacity_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(BisConnector._fetch_raw_data.retry, "wait", wait_none())
    monkeypatch.setattr(BisConnector.fetch_structure.retry, "wait", wait_none())


@pytest_asyncio.fixture
async def bis_connector(tmp_cache_dir: Path) -> AsyncIterator[BisConnector]:
    conn = BisConnector(cache_dir=str(tmp_cache_dir), rate_limit_seconds=0.0)
    yield conn
    await conn.aclose()


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text())


def test_date_to_period_q4() -> None:
    assert _date_to_period(date(2023, 12, 31)) == "2023-Q4"
    assert _date_to_period(date(2024, 1, 1)) == "2024-Q1"
    assert _date_to_period(date(2024, 4, 30)) == "2024-Q2"
    assert _date_to_period(date(2024, 7, 15)) == "2024-Q3"


def test_quarter_label_to_end_date() -> None:
    assert _quarter_label_to_end_date("2024-Q1") == date(2024, 3, 31)
    assert _quarter_label_to_end_date("2024-Q2") == date(2024, 6, 30)
    assert _quarter_label_to_end_date("2024-Q3") == date(2024, 9, 30)
    assert _quarter_label_to_end_date("2024-Q4") == date(2024, 12, 31)


def test_parse_series_empty_dataset() -> None:
    assert _parse_series({}, country="PT", source_tag="BIS", series_key="k") == []
    assert (
        _parse_series({"data": {"dataSets": []}}, country="PT", source_tag="BIS", series_key="k")
        == []
    )


def test_parse_series_ws_tc_pt_sample() -> None:
    payload = _load_fixture("ws_tc_PT_sample")
    obs = _parse_series(
        payload,
        country="PT",
        source_tag="BIS_WS_TC",
        series_key="Q.PT.P.A.M.770.A",
    )
    assert len(obs) == 3
    assert all(o.country_code == "PT" for o in obs)
    assert all(o.source == "BIS_WS_TC" for o in obs)
    # PT credit-to-GDP 2023-Q4 = 136.1 per cached fixture
    first_by_date = sorted(obs, key=lambda o: o.observation_date)
    assert first_by_date[0].observation_date == date(2023, 12, 31)
    assert first_by_date[0].value_pct == pytest.approx(136.1, abs=0.01)
    assert first_by_date[-1].observation_date == date(2024, 6, 30)
    assert first_by_date[-1].value_pct == pytest.approx(132.9, abs=0.01)


def test_parse_series_ws_dsr_us_sample() -> None:
    payload = _load_fixture("ws_dsr_US_sample")
    obs = _parse_series(payload, country="US", source_tag="BIS_WS_DSR", series_key="Q.US.P")
    assert len(obs) == 3
    # US DSR 2024-Q2 = 14.5 per cached fixture
    last_obs = max(obs, key=lambda o: o.observation_date)
    assert last_obs.value_pct == pytest.approx(14.5, abs=0.01)
    assert last_obs.source == "BIS_WS_DSR"


def test_parse_series_ws_credit_gap_multi_series() -> None:
    """WS_CREDIT_GAP returns 3 series (A=actual, B=trend, C=gap) concatenated."""
    payload = _load_fixture("ws_credit_gap_PT_sample")
    obs = _parse_series(payload, country="PT", source_tag="BIS_WS_CG", series_key="Q.PT.P.A.*")
    # 3 series x 3 obs each = 9 observations.
    assert len(obs) == 9
    assert all(o.country_code == "PT" for o in obs)


async def test_fetch_dsr_happy(httpx_mock: HTTPXMock, bis_connector: BisConnector) -> None:
    payload = _load_fixture("ws_dsr_US_sample")
    httpx_mock.add_response(method="GET", json=payload)
    obs = await bis_connector.fetch_dsr("US", date(2023, 10, 1), date(2024, 6, 30))
    assert len(obs) == 3
    assert all(isinstance(o, BisObservation) for o in obs)
    assert all(o.country_code == "US" for o in obs)
    assert all(o.source == "BIS_WS_DSR" for o in obs)


async def test_fetch_credit_stock_ratio_happy(
    httpx_mock: HTTPXMock, bis_connector: BisConnector
) -> None:
    payload = _load_fixture("ws_tc_PT_sample")
    httpx_mock.add_response(method="GET", json=payload)
    obs = await bis_connector.fetch_credit_stock_ratio("PT", date(2023, 10, 1), date(2024, 6, 30))
    assert len(obs) == 3
    assert all(o.source == "BIS_WS_TC" for o in obs)
    # Resolved CAL-019 key should be Q.PT.P.A.M.770.A
    assert all(o.source_series_key == "Q.PT.P.A.M.770.A" for o in obs)


async def test_fetch_credit_gap_happy(httpx_mock: HTTPXMock, bis_connector: BisConnector) -> None:
    payload = _load_fixture("ws_credit_gap_PT_sample")
    httpx_mock.add_response(method="GET", json=payload)
    obs = await bis_connector.fetch_credit_gap("PT", date(2023, 10, 1), date(2024, 6, 30))
    # Fixture was fetched with wildcard key so returns all 3 CG_DTYPE series
    # (A actual / B trend / C gap) concatenated — 3 series x 3 obs = 9 rows.
    assert len(obs) == 9
    assert all(o.source == "BIS_WS_CREDIT_GAP_C" for o in obs)


async def test_fetch_uses_cache(httpx_mock: HTTPXMock, bis_connector: BisConnector) -> None:
    payload = _load_fixture("ws_dsr_US_sample")
    httpx_mock.add_response(method="GET", json=payload)
    first = await bis_connector.fetch_dsr("US", date(2023, 10, 1), date(2024, 6, 30))
    # Second call must be served from cache — no httpx request.
    second = await bis_connector.fetch_dsr("US", date(2023, 10, 1), date(2024, 6, 30))
    assert first == second
    # Only 1 request was mocked; cache hit avoids 2nd roundtrip.
    assert len(httpx_mock.get_requests()) == 1


async def test_fetch_structure_happy(httpx_mock: HTTPXMock, bis_connector: BisConnector) -> None:
    payload = _load_fixture("ws_tc_structure")
    httpx_mock.add_response(method="GET", json=payload)
    structure = await bis_connector.fetch_structure("WS_TC")
    assert "data" in structure
    assert "dataStructures" in structure["data"]


async def test_rate_limit_between_requests(httpx_mock: HTTPXMock, tmp_cache_dir: Path) -> None:
    """With rate_limit=0.05s, two sequential fetches should pace at least 0.05s."""
    conn = BisConnector(cache_dir=str(tmp_cache_dir), rate_limit_seconds=0.05)
    try:
        payload = _load_fixture("ws_dsr_US_sample")
        payload_de = json.loads(json.dumps(payload))  # deepcopy
        httpx_mock.add_response(method="GET", json=payload)
        httpx_mock.add_response(method="GET", json=payload_de)

        t0 = time.perf_counter()
        await conn.fetch_dsr("US", date(2024, 1, 1), date(2024, 6, 30))
        await conn.fetch_dsr("DE", date(2024, 1, 1), date(2024, 6, 30))
        elapsed = time.perf_counter() - t0
        assert elapsed >= 0.04  # allow some slack vs 0.05s window
    finally:
        await conn.aclose()


async def test_empty_payload_returns_empty_list(
    httpx_mock: HTTPXMock, bis_connector: BisConnector
) -> None:
    httpx_mock.add_response(method="GET", json={"data": {"dataSets": []}})
    obs = await bis_connector.fetch_dsr("XX", date(2024, 1, 1), date(2024, 6, 30))
    assert obs == []


def test_accept_header_exact_spec() -> None:
    """Accept header must be exactly the v1.0.0 SDMX-JSON media type.

    BIS stats.bis.org rejects ``;version=2.0.0`` / ``;version=3.0.0``
    with HTTP 406 and returns SDMX-XML if the header is omitted
    (Week 9 Sprint AA / CAL-136 empirical findings). Any extra
    alternates (``, application/json``) tighten attack surface but the
    spec pins us to the canonical string.
    """
    assert ACCEPT_HEADER == "application/vnd.sdmx.data+json;version=1.0.0"


def test_dataflow_versions_map() -> None:
    """Dataflow → version map is the single source of truth."""
    assert DATAFLOW_VERSIONS["WS_TC"] == "2.0"
    assert DATAFLOW_VERSIONS["WS_DSR"] == "1.0"
    assert DATAFLOW_VERSIONS["WS_CREDIT_GAP"] == "1.0"
    assert DATAFLOW_VERSIONS["WS_SPP"] == "1.0"


async def test_fetch_url_pattern_ws_tc(httpx_mock: HTTPXMock, bis_connector: BisConnector) -> None:
    """URL for WS_TC must be /data/dataflow/BIS/WS_TC/2.0/{key} with no format qs."""
    httpx_mock.add_response(method="GET", json=_load_fixture("ws_tc_PT_sample"))
    await bis_connector.fetch_credit_stock_ratio("PT", date(2024, 1, 1), date(2024, 6, 30))
    [req] = httpx_mock.get_requests()
    expected_path = f"{BASE_URL}/data/dataflow/{AGENCY_ID}/WS_TC/2.0/Q.PT.P.A.M.770.A"
    assert str(req.url).startswith(expected_path), str(req.url)
    assert "format=jsondata" not in str(req.url), str(req.url)
    assert req.headers["Accept"] == ACCEPT_HEADER


async def test_fetch_url_pattern_ws_dsr(httpx_mock: HTTPXMock, bis_connector: BisConnector) -> None:
    """URL for WS_DSR must be /data/dataflow/BIS/WS_DSR/1.0/{key}."""
    httpx_mock.add_response(method="GET", json=_load_fixture("ws_dsr_US_sample"))
    await bis_connector.fetch_dsr("US", date(2024, 1, 1), date(2024, 6, 30))
    [req] = httpx_mock.get_requests()
    expected_path = f"{BASE_URL}/data/dataflow/{AGENCY_ID}/WS_DSR/1.0/Q.US.P"
    assert str(req.url).startswith(expected_path), str(req.url)
    assert "format=jsondata" not in str(req.url), str(req.url)


async def test_fetch_url_pattern_ws_credit_gap(
    httpx_mock: HTTPXMock, bis_connector: BisConnector
) -> None:
    """URL for WS_CREDIT_GAP must be /data/dataflow/BIS/WS_CREDIT_GAP/1.0/{key}."""
    httpx_mock.add_response(method="GET", json=_load_fixture("ws_credit_gap_PT_sample"))
    await bis_connector.fetch_credit_gap("PT", date(2024, 1, 1), date(2024, 6, 30))
    [req] = httpx_mock.get_requests()
    expected_path = f"{BASE_URL}/data/dataflow/{AGENCY_ID}/WS_CREDIT_GAP/1.0/Q.PT.P.A.C"
    assert str(req.url).startswith(expected_path), str(req.url)


def test_parse_series_live_2024h1_shape() -> None:
    """Parse a freshly captured 2026-04-21 live response (CAL-136 canary).

    Locks in the current-gen BIS SDMX-JSON 1.0 response shape so any
    future structural drift (e.g. if BIS enables v2.0.0 JSON by default)
    surfaces here rather than in production. Fixture covers US WS_TC
    2023-Q4 → 2024-Q2; values cross-validated against the FRED/H.15
    equivalent public series.
    """
    payload = _load_fixture("ws_tc_US_live_2024h1")
    obs = _parse_series(
        payload,
        country="US",
        source_tag="BIS_WS_TC",
        series_key="Q.US.P.A.M.770.A",
    )
    assert len(obs) == 3
    by_date = sorted(obs, key=lambda o: o.observation_date)
    # 2023-Q4 / 2024-Q1 / 2024-Q2 credit-to-GDP — US private non-financial.
    assert by_date[0].observation_date == date(2023, 12, 31)
    assert by_date[-1].observation_date == date(2024, 6, 30)
    assert all(140.0 <= o.value_pct <= 150.0 for o in obs), [o.value_pct for o in obs]


@pytest.mark.slow
async def test_live_canary_ws_dsr_us(tmp_cache_dir: Path) -> None:
    """Live smoke test — skipped in CI; runnable via `pytest -m live`."""
    conn = BisConnector(cache_dir=str(tmp_cache_dir), rate_limit_seconds=0.5)
    try:
        obs = await conn.fetch_dsr("US", date(2023, 10, 1), date(2024, 6, 30))
        assert len(obs) >= 1
        assert all(5.0 <= o.value_pct <= 30.0 for o in obs)
    finally:
        await conn.aclose()


# ---------------------------------------------------------------------------
# Week 10 Sprint J — WS_EER NEER extension
# ---------------------------------------------------------------------------


def test_month_label_to_end_date() -> None:
    assert _month_label_to_end_date("2024-01") == date(2024, 1, 31)
    assert _month_label_to_end_date("2024-02") == date(2024, 2, 29)  # leap
    assert _month_label_to_end_date("2023-02") == date(2023, 2, 28)
    assert _month_label_to_end_date("2024-12") == date(2024, 12, 31)
    assert _month_label_to_end_date("2024-04") == date(2024, 4, 30)


def test_bis_eer_country_codes_cover_t1_plus_xm() -> None:
    for c in (
        "US",
        "DE",
        "FR",
        "IT",
        "ES",
        "NL",
        "PT",
        "GB",
        "JP",
        "CA",
        "AU",
        "NZ",
        "CH",
        "SE",
        "NO",
        "DK",
        "XM",
    ):
        assert c in BIS_EER_COUNTRY_CODES
    assert len(BIS_EER_COUNTRY_CODES) == 17


@pytest.mark.parametrize(
    ("country", "fixture_stem", "bis_ref"),
    [
        ("US", "bis_neer_us_2023_2024", "US"),
        ("DE", "bis_neer_de_2023_2024", "DE"),
        ("EA", "bis_neer_xm_2023_2024", "XM"),
    ],
)
async def test_fetch_neer_from_cassette(
    httpx_mock: HTTPXMock,
    bis_connector: BisConnector,
    country: str,
    fixture_stem: str,
    bis_ref: str,
) -> None:
    """NEER round-trip for US/DE/EA via cassettes. EA -> XM translation."""
    payload = _load_fixture(fixture_stem)
    httpx_mock.add_response(method="GET", json=payload)
    obs = await bis_connector.fetch_neer(country, date(2023, 1, 1), date(2024, 12, 31))
    assert len(obs) >= 20
    assert all(isinstance(o, BisEerObservation) for o in obs)
    # SONAR country surfaces uppercase EA (not BIS's XM) to the consumer.
    assert obs[0].country_code == country.upper()
    assert obs[0].source == "BIS_WS_EER"
    assert obs[0].source_series_key == f"M.N.B.{bis_ref}"
    # Monthly cadence — month-end dates, values are index levels (2010=100).
    assert obs[0].observation_date.day >= 28
    assert all(50.0 < o.value_index < 200.0 for o in obs)


async def test_fetch_neer_unsupported_country_raises(
    bis_connector: BisConnector,
) -> None:
    with pytest.raises(ValueError, match="CAL-M4-NEER-T2-EXPANSION"):
        await bis_connector.fetch_neer("CN", date(2024, 1, 1), date(2024, 6, 30))


async def test_fetch_neer_url_shape(
    httpx_mock: HTTPXMock,
    bis_connector: BisConnector,
) -> None:
    """Dispatch uses WS_EER 1.0 dataflow + M.N.B.{REF_AREA} key + EA->XM."""
    payload = _load_fixture("bis_neer_xm_2023_2024")
    httpx_mock.add_response(method="GET", json=payload)
    await bis_connector.fetch_neer("EA", date(2024, 1, 1), date(2024, 6, 30))
    [req] = httpx_mock.get_requests()
    expected_path = f"{BASE_URL}/data/dataflow/{AGENCY_ID}/WS_EER/1.0/M.N.B.XM"
    assert str(req.url).startswith(expected_path), str(req.url)


@pytest.mark.slow
async def test_live_canary_ws_eer_de(tmp_cache_dir: Path) -> None:
    """Sprint J — live BIS WS_EER NEER for DE Q4/2024."""
    conn = BisConnector(cache_dir=str(tmp_cache_dir), rate_limit_seconds=0.5)
    try:
        obs = await conn.fetch_neer("DE", date(2024, 10, 1), date(2024, 12, 31))
        assert len(obs) >= 1
        assert all(o.source == "BIS_WS_EER" for o in obs)
        assert all(80.0 < o.value_index < 140.0 for o in obs)
    finally:
        await conn.aclose()
