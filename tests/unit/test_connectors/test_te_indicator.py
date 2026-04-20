"""Unit tests for TE Economic-indicator extension (Week 6 Sprint 1)."""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from tenacity import wait_none

from sonar.connectors.te import (
    TE_COUNTRY_NAME_MAP,
    TE_INDICATOR_IFO_HEADLINE,
    TE_INDICATOR_ISM_MFG_HEADLINE,
    TE_INDICATOR_ISM_SVC_HEADLINE,
    TE_INDICATOR_MICHIGAN_5Y_INFLATION,
    TE_INDICATOR_NFIB,
    TE_INDICATOR_ZEW_ECONOMIC_SENTIMENT,
    TEConnector,
    TEIndicatorObservation,
)
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pytest_httpx import HTTPXMock


CASSETTE_DIR = Path(__file__).parent.parent.parent / "cassettes" / "connectors"


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "te_ind_cache"
    d.mkdir()
    return d


@pytest_asyncio.fixture
async def te_connector(
    tmp_cache_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[TEConnector]:
    monkeypatch.setattr(TEConnector._fetch_indicator_raw.retry, "wait", wait_none())
    conn = TEConnector(api_key="test:secret", cache_dir=str(tmp_cache_dir))
    yield conn
    await conn.aclose()


def _load_cassette(name: str) -> list[dict]:
    return json.loads((CASSETTE_DIR / name).read_text())


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_country_name_map_covers_t1() -> None:
    for c in ("US", "DE", "UK", "JP", "IT", "ES", "FR", "NL", "PT"):
        assert c in TE_COUNTRY_NAME_MAP
    assert TE_COUNTRY_NAME_MAP["US"] == "united states"
    assert TE_COUNTRY_NAME_MAP["DE"] == "germany"


def test_indicator_name_constants() -> None:
    # TE labels ISM Mfg + Ifo both as "business confidence".
    assert TE_INDICATOR_ISM_MFG_HEADLINE == "business confidence"
    assert TE_INDICATOR_IFO_HEADLINE == "business confidence"
    assert TE_INDICATOR_ISM_SVC_HEADLINE == "non manufacturing pmi"
    assert TE_INDICATOR_NFIB == "nfib business optimism index"
    assert TE_INDICATOR_ZEW_ECONOMIC_SENTIMENT == "zew economic sentiment index"


# ---------------------------------------------------------------------------
# fetch_indicator
# ---------------------------------------------------------------------------


async def test_fetch_indicator_ism_mfg_from_cassette(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    payload = _load_cassette("te_ism_mfg_us_2024_01_02.json")
    httpx_mock.add_response(method="GET", json=payload)
    obs = await te_connector.fetch_indicator(
        "US", "business confidence", date(2020, 1, 1), date(2024, 6, 30)
    )
    assert len(obs) > 100  # cassette covers multi-decade history
    assert all(isinstance(o, TEIndicatorObservation) for o in obs)
    # ISM PMI sanity band [20, 80].
    for o in obs[-24:]:
        assert 20 < o.value < 80
    assert obs[0].country == "US"
    assert obs[0].indicator == "business confidence"


async def test_fetch_indicator_ism_svc_from_cassette(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    payload = _load_cassette("te_ism_svc_us_2024_01_02.json")
    httpx_mock.add_response(method="GET", json=payload)
    obs = await te_connector.fetch_indicator(
        "US", TE_INDICATOR_ISM_SVC_HEADLINE, date(2020, 1, 1), date(2024, 6, 30)
    )
    assert len(obs) >= 50
    for o in obs[-24:]:
        assert 20 < o.value < 80


async def test_fetch_indicator_nfib_from_cassette(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    payload = _load_cassette("te_nfib_us_2024_01_02.json")
    httpx_mock.add_response(method="GET", json=payload)
    obs = await te_connector.fetch_indicator(
        "US", TE_INDICATOR_NFIB, date(2020, 1, 1), date(2024, 6, 30)
    )
    assert len(obs) >= 50
    # NFIB typically in [80, 110] range.
    for o in obs[-12:]:
        assert 70 < o.value < 120


async def test_fetch_indicator_ifo_de_from_cassette(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    payload = _load_cassette("te_ifo_de_2024_01_02.json")
    httpx_mock.add_response(method="GET", json=payload)
    obs = await te_connector.fetch_indicator(
        "DE", TE_INDICATOR_IFO_HEADLINE, date(2020, 1, 1), date(2024, 6, 30)
    )
    assert len(obs) >= 50
    # Ifo Business Climate typically 75-115.
    for o in obs[-24:]:
        assert 60 < o.value < 130


async def test_fetch_indicator_zew_de_from_cassette(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    payload = _load_cassette("te_zew_de_2024_01_02.json")
    httpx_mock.add_response(method="GET", json=payload)
    obs = await te_connector.fetch_indicator(
        "DE", TE_INDICATOR_ZEW_ECONOMIC_SENTIMENT, date(2020, 1, 1), date(2024, 6, 30)
    )
    assert len(obs) >= 20
    # ZEW Economic Sentiment ∈ [-100, +100].
    for o in obs[-24:]:
        assert -100 <= o.value <= 100


async def test_fetch_indicator_unknown_country_raises(
    te_connector: TEConnector,
) -> None:
    with pytest.raises(ValueError, match="Unknown TE country"):
        await te_connector.fetch_indicator(
            "XX", "business confidence", date(2024, 1, 1), date(2024, 6, 30)
        )


async def test_fetch_indicator_empty_payload_raises(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    httpx_mock.add_response(method="GET", json=[])
    with pytest.raises(DataUnavailableError, match="empty series"):
        await te_connector.fetch_indicator(
            "US", "business confidence", date(2024, 1, 1), date(2024, 6, 30)
        )


async def test_fetch_indicator_non_list_payload_raises(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    httpx_mock.add_response(method="GET", json={"error": "something"})
    with pytest.raises(DataUnavailableError, match="non-list"):
        await te_connector.fetch_indicator(
            "US", "business confidence", date(2024, 1, 1), date(2024, 6, 30)
        )


async def test_fetch_indicator_skips_malformed_rows(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        json=[
            {"DateTime": None, "Value": 55.0},  # bad date
            {"DateTime": "2024-03-31T00:00:00", "Value": None},  # bad value
            {"DateTime": "2024-04-30T00:00:00", "Value": 54.0, "Frequency": "Monthly"},
        ],
    )
    obs = await te_connector.fetch_indicator(
        "US", "business confidence", date(2024, 1, 1), date(2024, 6, 30)
    )
    assert len(obs) == 1
    assert obs[0].observation_date == date(2024, 4, 30)
    assert obs[0].value == 54.0
    assert obs[0].frequency == "Monthly"


async def test_fetch_indicator_caches(httpx_mock: HTTPXMock, te_connector: TEConnector) -> None:
    httpx_mock.add_response(
        method="GET",
        json=[{"DateTime": "2024-04-30T00:00:00", "Value": 54.0}],
    )
    first = await te_connector.fetch_indicator(
        "US", "business confidence", date(2024, 1, 1), date(2024, 6, 30)
    )
    second = await te_connector.fetch_indicator(
        "US", "business confidence", date(2024, 1, 1), date(2024, 6, 30)
    )
    assert first == second
    assert len(httpx_mock.get_requests()) == 1


# ---------------------------------------------------------------------------
# Telemetry (CAL-092 c4)
# ---------------------------------------------------------------------------


async def test_call_counter_increments(httpx_mock: HTTPXMock, te_connector: TEConnector) -> None:
    httpx_mock.add_response(method="GET", json=[{"DateTime": "2024-04-30T00:00:00", "Value": 54.0}])
    assert te_connector.get_call_count() == 0
    await te_connector.fetch_indicator(
        "US", "business confidence", date(2024, 1, 1), date(2024, 6, 30)
    )
    assert te_connector.get_call_count() == 1


async def test_reset_call_count(httpx_mock: HTTPXMock, te_connector: TEConnector) -> None:
    httpx_mock.add_response(method="GET", json=[{"DateTime": "2024-04-30T00:00:00", "Value": 54.0}])
    await te_connector.fetch_indicator(
        "US", "business confidence", date(2024, 1, 1), date(2024, 6, 30)
    )
    te_connector.reset_call_count()
    assert te_connector.get_call_count() == 0


# ---------------------------------------------------------------------------
# CAL-targeted convenience wrappers (c2)
# ---------------------------------------------------------------------------


async def test_wrapper_ism_manufacturing_us(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    httpx_mock.add_response(method="GET", json=_load_cassette("te_ism_mfg_us_2024_01_02.json"))
    obs = await te_connector.fetch_ism_manufacturing_us(date(2024, 1, 1), date(2024, 6, 30))
    assert len(obs) >= 50
    assert obs[0].country == "US"
    assert obs[0].indicator == "business confidence"


async def test_wrapper_ism_services_us(httpx_mock: HTTPXMock, te_connector: TEConnector) -> None:
    httpx_mock.add_response(method="GET", json=_load_cassette("te_ism_svc_us_2024_01_02.json"))
    obs = await te_connector.fetch_ism_services_us(date(2024, 1, 1), date(2024, 6, 30))
    assert len(obs) >= 50
    assert obs[0].indicator == "non manufacturing pmi"


async def test_wrapper_nfib_us(httpx_mock: HTTPXMock, te_connector: TEConnector) -> None:
    httpx_mock.add_response(method="GET", json=_load_cassette("te_nfib_us_2024_01_02.json"))
    obs = await te_connector.fetch_nfib_us(date(2024, 1, 1), date(2024, 6, 30))
    assert len(obs) >= 50
    assert obs[0].indicator == "nfib business optimism index"


async def test_wrapper_ifo_de(httpx_mock: HTTPXMock, te_connector: TEConnector) -> None:
    httpx_mock.add_response(method="GET", json=_load_cassette("te_ifo_de_2024_01_02.json"))
    obs = await te_connector.fetch_ifo_business_climate_de(date(2024, 1, 1), date(2024, 6, 30))
    assert len(obs) >= 50
    assert obs[0].country == "DE"


async def test_wrapper_zew_de(httpx_mock: HTTPXMock, te_connector: TEConnector) -> None:
    httpx_mock.add_response(method="GET", json=_load_cassette("te_zew_de_2024_01_02.json"))
    obs = await te_connector.fetch_zew_economic_sentiment_de(date(2024, 1, 1), date(2024, 6, 30))
    assert len(obs) >= 20
    assert obs[0].country == "DE"
    assert obs[0].indicator == "zew economic sentiment index"


# ---------------------------------------------------------------------------
# Sprint 6.3 wrappers — CB CC (CAL-093) + Michigan 5Y (new CAL)
# ---------------------------------------------------------------------------


async def test_wrapper_conference_board_cc_us(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    httpx_mock.add_response(
        method="GET", json=_load_cassette("te_consumer_confidence_us_2024_01_02.json")
    )
    obs = await te_connector.fetch_conference_board_cc_us(date(2024, 1, 1), date(2024, 6, 30))
    assert len(obs) >= 100
    assert obs[0].country == "US"
    assert obs[0].indicator == "consumer confidence"
    # Source-guard: every row on this feed is CONCCONF (Conference Board).
    assert obs[0].historical_data_symbol == "CONCCONF"
    # CB CC values historically in [25, 145] range.
    for o in obs[-24:]:
        assert 20 <= o.value <= 160


async def test_wrapper_conference_board_cc_raises_on_source_drift(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    # TE returns the payload with a non-CONCCONF symbol (e.g. UMich
    # label) — wrapper should raise to prevent silent mis-attribution.
    httpx_mock.add_response(
        method="GET",
        json=[
            {
                "Country": "United States",
                "Category": "Consumer Confidence",
                "DateTime": "2024-01-31T00:00:00",
                "Value": 61.3,
                "HistoricalDataSymbol": "USAMCE",  # UMich, not CONCCONF
            }
        ],
    )
    with pytest.raises(DataUnavailableError, match="source drift"):
        await te_connector.fetch_conference_board_cc_us(date(2024, 1, 1), date(2024, 6, 30))


async def test_wrapper_michigan_5y_inflation_us(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    httpx_mock.add_response(
        method="GET", json=_load_cassette("te_michigan_5y_inflation_us_2024_01_02.json")
    )
    obs = await te_connector.fetch_michigan_5y_inflation_us(date(2024, 1, 1), date(2024, 6, 30))
    assert len(obs) >= 50
    assert obs[0].country == "US"
    assert obs[0].indicator == "michigan 5 year inflation expectations"
    assert obs[0].historical_data_symbol == "USAM5YIE"
    # UMich 5Y inflation expectations historically [1.5, 8.0] %.
    for o in obs[-24:]:
        assert 0.5 <= o.value <= 10.0


async def test_wrapper_michigan_5y_raises_on_source_drift(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        json=[
            {
                "Country": "United States",
                "Category": "Michigan 5 Year Inflation Expectations",
                "DateTime": "2024-01-31T00:00:00",
                "Value": 2.9,
                "HistoricalDataSymbol": "OTHER_ID",
            }
        ],
    )
    with pytest.raises(DataUnavailableError, match="source drift"):
        await te_connector.fetch_michigan_5y_inflation_us(date(2024, 1, 1), date(2024, 6, 30))


# ---------------------------------------------------------------------------
# Live canary (CAL-092)
# ---------------------------------------------------------------------------


@pytest.mark.slow
async def test_live_canary_te_ism_mfg_recent(tmp_cache_dir: Path) -> None:
    """Fetch last 12m ISM Mfg via TE; assert sensible PMI band."""
    api_key = os.environ.get("TE_API_KEY")
    if not api_key:
        pytest.skip("TE_API_KEY not set")
    conn = TEConnector(api_key=api_key, cache_dir=str(tmp_cache_dir))
    try:
        today = datetime.now(tz=UTC).date()
        obs = await conn.fetch_indicator(
            "US",
            TE_INDICATOR_ISM_MFG_HEADLINE,
            today - timedelta(days=365),
            today,
        )
        assert len(obs) >= 3
        for o in obs:
            assert 20 < o.value < 80
    finally:
        await conn.aclose()


@pytest.mark.slow
async def test_live_canary_te_conference_board_cc_recent(tmp_cache_dir: Path) -> None:
    """Fetch last 3m US CC via TE; confirm CONCCONF + plausible CB band.

    TE's ``d1``/``d2`` params are advisory; filter client-side to the
    recent window before asserting the band (1974 CB CC troughs ~40).
    """
    api_key = os.environ.get("TE_API_KEY")
    if not api_key:
        pytest.skip("TE_API_KEY not set")
    conn = TEConnector(api_key=api_key, cache_dir=str(tmp_cache_dir))
    try:
        today = datetime.now(tz=UTC).date()
        start = today - timedelta(days=120)
        obs = await conn.fetch_conference_board_cc_us(start, today)
        assert len(obs) >= 1
        assert obs[0].historical_data_symbol == "CONCCONF"
        recent = [o for o in obs if start <= o.observation_date <= today]
        assert len(recent) >= 1
        for o in recent:
            # Conference Board CCI historically in [25, 145].
            assert 20 <= o.value <= 160
    finally:
        await conn.aclose()


@pytest.mark.slow
async def test_live_canary_te_michigan_5y_inflation_recent(tmp_cache_dir: Path) -> None:
    """Fetch last 12m US UMich 5Y inflation via TE; band check + symbol guard.

    TE's ``d1``/``d2`` params are advisory — the full historical series
    comes back regardless. Filter client-side to the recent window
    before asserting the band (historical 1980s peaks go ~10%).
    """
    api_key = os.environ.get("TE_API_KEY")
    if not api_key:
        pytest.skip("TE_API_KEY not set")
    conn = TEConnector(api_key=api_key, cache_dir=str(tmp_cache_dir))
    try:
        today = datetime.now(tz=UTC).date()
        start = today - timedelta(days=365)
        obs = await conn.fetch_michigan_5y_inflation_us(start, today)
        assert len(obs) >= 3
        assert obs[0].historical_data_symbol == "USAM5YIE"
        recent = [o for o in obs if start <= o.observation_date <= today]
        assert len(recent) >= 3
        for o in recent:
            # Post-2000 UMich 5Y expectations stayed in [1.5, 6.0]%.
            assert 1.0 <= o.value <= 8.0
    finally:
        await conn.aclose()


def test_michigan_5y_indicator_constant() -> None:
    assert TE_INDICATOR_MICHIGAN_5Y_INFLATION == "michigan 5 year inflation expectations"
