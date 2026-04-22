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
    for c in ("US", "DE", "GB", "JP", "CA", "IT", "ES", "FR", "NL", "PT"):
        assert c in TE_COUNTRY_NAME_MAP
    assert TE_COUNTRY_NAME_MAP["US"] == "united states"
    assert TE_COUNTRY_NAME_MAP["DE"] == "germany"
    assert TE_COUNTRY_NAME_MAP["GB"] == "united kingdom"
    assert TE_COUNTRY_NAME_MAP["CA"] == "canada"
    # Nordic Tier-1 entries — added Week 9 Sprint X-NO.
    assert TE_COUNTRY_NAME_MAP["NO"] == "norway"


def test_country_name_map_uk_alias_preserved() -> None:
    """Legacy ``"UK"`` resolves to the same TE slug per ADR-0007 alias."""
    assert TE_COUNTRY_NAME_MAP["UK"] == TE_COUNTRY_NAME_MAP["GB"] == "united kingdom"


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


async def test_wrapper_gb_bank_rate_happy_path(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """TE ``interest rate`` for GB returns ``UKBRBASE`` (BoE Bank Rate)."""
    httpx_mock.add_response(
        method="GET",
        json=[
            {
                "Country": "United Kingdom",
                "Category": "Interest Rate",
                "DateTime": "2024-12-19T00:00:00",
                "Value": 4.75,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "UKBRBASE",
                "LastUpdate": "2024-12-19T12:00:00",
            },
            {
                "Country": "United Kingdom",
                "Category": "Interest Rate",
                "DateTime": "2025-02-06T00:00:00",
                "Value": 4.50,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "UKBRBASE",
                "LastUpdate": "2025-02-06T12:00:00",
            },
        ],
    )
    obs = await te_connector.fetch_gb_bank_rate(date(2024, 12, 1), date(2025, 3, 1))
    assert len(obs) == 2
    assert obs[0].country == "GB"
    assert obs[0].indicator == "interest rate"
    assert obs[0].historical_data_symbol == "UKBRBASE"
    # BoE Bank Rate has historically spanned [0.10, 15.0].
    for o in obs:
        assert 0.0 <= o.value <= 20.0


async def test_wrapper_gb_bank_rate_raises_on_source_drift(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """If TE swaps in a non-UKBRBASE symbol, raise — catches mis-attribution."""
    httpx_mock.add_response(
        method="GET",
        json=[
            {
                "Country": "United Kingdom",
                "Category": "Interest Rate",
                "DateTime": "2024-12-19T00:00:00",
                "Value": 4.75,
                "HistoricalDataSymbol": "GBINTR",  # wrong symbol
            }
        ],
    )
    with pytest.raises(DataUnavailableError, match="GB-bank-rate source drift"):
        await te_connector.fetch_gb_bank_rate(date(2024, 12, 1), date(2024, 12, 31))


async def test_wrapper_gb_bank_rate_empty_response_raises(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """Empty payload → fetch_indicator raises; cascade callers treat as
    TE-unavailable and fall through to the next source."""
    httpx_mock.add_response(method="GET", json=[])
    with pytest.raises(DataUnavailableError, match="empty series"):
        await te_connector.fetch_gb_bank_rate(date(2024, 12, 1), date(2024, 12, 31))


async def test_wrapper_uk_bank_rate_deprecated_alias_delegates(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """``fetch_uk_bank_rate`` is preserved as a deprecated alias for
    :meth:`TEConnector.fetch_gb_bank_rate` per ADR-0007 — called today
    by ``builders.py`` UK cascade carve-out. Emits a structlog
    deprecation warning and delegates to the canonical GB method."""
    httpx_mock.add_response(
        method="GET",
        json=[
            {
                "Country": "United Kingdom",
                "Category": "Interest Rate",
                "DateTime": "2024-12-19T00:00:00",
                "Value": 4.75,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "UKBRBASE",
            }
        ],
    )
    obs = await te_connector.fetch_uk_bank_rate(date(2024, 12, 1), date(2024, 12, 31))
    assert len(obs) == 1
    assert obs[0].historical_data_symbol == "UKBRBASE"


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


async def test_wrapper_jp_bank_rate_happy_path(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """TE ``interest rate`` for JP returns ``BOJDTR`` (BoJ policy rate)."""
    httpx_mock.add_response(
        method="GET",
        json=[
            {
                "Country": "Japan",
                "Category": "Interest Rate",
                "DateTime": "2024-03-19T00:00:00",
                "Value": 0.10,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "BOJDTR",
                "LastUpdate": "2024-03-19T03:00:00",
            },
            {
                "Country": "Japan",
                "Category": "Interest Rate",
                "DateTime": "2024-07-31T00:00:00",
                "Value": 0.25,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "BOJDTR",
                "LastUpdate": "2024-07-31T03:00:00",
            },
            {
                "Country": "Japan",
                "Category": "Interest Rate",
                "DateTime": "2026-01-23T00:00:00",
                "Value": 0.75,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "BOJDTR",
                "LastUpdate": "2026-01-23T03:00:00",
            },
        ],
    )
    obs = await te_connector.fetch_jp_bank_rate(date(2024, 1, 1), date(2026, 3, 1))
    assert len(obs) == 3
    assert obs[0].country == "JP"
    assert obs[0].indicator == "interest rate"
    assert obs[0].historical_data_symbol == "BOJDTR"
    # Post-1990 BoJ policy rate bounded in [-0.1, 6.0]%.
    for o in obs:
        assert -0.5 <= o.value <= 10.0


async def test_wrapper_jp_bank_rate_raises_on_source_drift(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """If TE swaps in a non-BOJDTR symbol, raise — catches mis-attribution."""
    httpx_mock.add_response(
        method="GET",
        json=[
            {
                "Country": "Japan",
                "Category": "Interest Rate",
                "DateTime": "2024-07-31T00:00:00",
                "Value": 0.25,
                "HistoricalDataSymbol": "JPINTR",
            }
        ],
    )
    with pytest.raises(DataUnavailableError, match="JP-bank-rate source drift"):
        await te_connector.fetch_jp_bank_rate(date(2024, 1, 1), date(2024, 12, 31))


async def test_wrapper_jp_bank_rate_empty_response_raises(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """Empty payload → fetch_indicator raises; cascade callers treat as
    TE-unavailable and fall through to the next source."""
    httpx_mock.add_response(method="GET", json=[])
    with pytest.raises(DataUnavailableError, match="empty series"):
        await te_connector.fetch_jp_bank_rate(date(2024, 1, 1), date(2024, 12, 31))


async def test_wrapper_jp_bank_rate_from_cassette(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """Full-history cassette confirms 690+ BOJDTR daily observations."""
    payload = _load_cassette("te_jp_bank_rate_2024_01_02.json")
    httpx_mock.add_response(method="GET", json=payload)
    obs = await te_connector.fetch_jp_bank_rate(date(2024, 1, 1), date(2024, 12, 31))
    assert len(obs) >= 600
    assert obs[0].historical_data_symbol == "BOJDTR"
    assert obs[0].country == "JP"
    # Every row on this feed is the BoJ policy rate series.
    for o in obs[-24:]:
        assert -0.5 <= o.value <= 15.0


@pytest.mark.slow
async def test_live_canary_jp_bank_rate(tmp_cache_dir: Path) -> None:
    """Live probe of TE JP Bank Rate — confirms BOJDTR symbol + daily cadence.

    Skips when ``TE_API_KEY`` is not set. Series back-fills the full
    history; filter client-side to the recent window before asserting
    the band (BoJ hiked Dec 2024 → 0.25 %; Jan 2026 → 0.75 %).
    """
    api_key = os.environ.get("TE_API_KEY")
    if not api_key:
        pytest.skip("TE_API_KEY not set")
    conn = TEConnector(api_key=api_key, cache_dir=str(tmp_cache_dir))
    try:
        today = datetime.now(tz=UTC).date()
        start = today - timedelta(days=365 * 2)
        obs = await conn.fetch_jp_bank_rate(start, today)
        assert len(obs) >= 3
        assert obs[0].historical_data_symbol == "BOJDTR"
        assert obs[0].country == "JP"
        recent = [o for o in obs if o.observation_date >= start]
        for o in recent:
            assert -0.5 <= o.value <= 5.0
    finally:
        await conn.aclose()


@pytest.mark.slow
async def test_live_canary_gb_bank_rate(tmp_cache_dir: Path) -> None:
    """Live probe of TE GB Bank Rate — confirms UKBRBASE symbol + daily cadence.

    Skips when ``TE_API_KEY`` is not set. The endpoint back-fills the
    full history regardless of the window, so filter client-side to
    the anchor year before asserting the band.
    """
    api_key = os.environ.get("TE_API_KEY")
    if not api_key:
        pytest.skip("TE_API_KEY not set")
    conn = TEConnector(api_key=api_key, cache_dir=str(tmp_cache_dir))
    try:
        today = datetime.now(tz=UTC).date()
        start = today - timedelta(days=365 * 2)
        obs = await conn.fetch_gb_bank_rate(start, today)
        assert len(obs) >= 5
        assert obs[0].historical_data_symbol == "UKBRBASE"
        assert obs[0].country == "GB"
        # BoE Bank Rate ranged [0.10, 5.25] across the last decade; keep
        # the canary band loose to absorb future moves without flaking.
        recent = [o for o in obs if o.observation_date >= start]
        for o in recent:
            assert 0.0 <= o.value <= 20.0
    finally:
        await conn.aclose()


async def test_wrapper_ca_bank_rate_happy_path(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """TE ``interest rate`` for CA returns ``CCLR`` (BoC overnight target)."""
    httpx_mock.add_response(
        method="GET",
        json=[
            {
                "Country": "Canada",
                "Category": "Interest Rate",
                "DateTime": "2024-06-05T00:00:00",
                "Value": 4.75,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "CCLR",
                "LastUpdate": "2024-06-05T13:45:00",
            },
            {
                "Country": "Canada",
                "Category": "Interest Rate",
                "DateTime": "2024-12-11T00:00:00",
                "Value": 3.25,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "CCLR",
                "LastUpdate": "2024-12-11T13:45:00",
            },
            {
                "Country": "Canada",
                "Category": "Interest Rate",
                "DateTime": "2026-03-18T00:00:00",
                "Value": 2.25,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "CCLR",
                "LastUpdate": "2026-03-18T13:45:00",
            },
        ],
    )
    obs = await te_connector.fetch_ca_bank_rate(date(2024, 1, 1), date(2026, 4, 1))
    assert len(obs) == 3
    assert obs[0].country == "CA"
    assert obs[0].indicator == "interest rate"
    assert obs[0].historical_data_symbol == "CCLR"
    # BoC target for overnight rate stays in [0.25, 10] pct post-1990.
    for o in obs:
        assert 0.0 <= o.value <= 15.0


async def test_wrapper_ca_bank_rate_raises_on_source_drift(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """If TE swaps in a non-CCLR symbol, raise — catches mis-attribution."""
    httpx_mock.add_response(
        method="GET",
        json=[
            {
                "Country": "Canada",
                "Category": "Interest Rate",
                "DateTime": "2024-12-11T00:00:00",
                "Value": 3.25,
                "HistoricalDataSymbol": "CAINTR",
            }
        ],
    )
    with pytest.raises(DataUnavailableError, match="CA-bank-rate source drift"):
        await te_connector.fetch_ca_bank_rate(date(2024, 1, 1), date(2024, 12, 31))


async def test_wrapper_ca_bank_rate_empty_response_raises(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """Empty payload → ``fetch_indicator`` raises; cascade callers treat as
    TE-unavailable and fall through to BoC native."""
    httpx_mock.add_response(method="GET", json=[])
    with pytest.raises(DataUnavailableError, match="empty series"):
        await te_connector.fetch_ca_bank_rate(date(2024, 1, 1), date(2024, 12, 31))


async def test_wrapper_ca_bank_rate_from_cassette(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """Full-history cassette confirms 2000+ CCLR daily observations."""
    payload = _load_cassette("te_ca_bank_rate_2024_01_02.json")
    httpx_mock.add_response(method="GET", json=payload)
    obs = await te_connector.fetch_ca_bank_rate(date(2024, 1, 1), date(2024, 12, 31))
    assert len(obs) >= 2000
    assert obs[0].historical_data_symbol == "CCLR"
    assert obs[0].country == "CA"
    # Recent window: 2024+ BoC overnight sits in [2.25, 5.00]%.
    recent = obs[-24:]
    for o in recent:
        assert 0.0 <= o.value <= 10.0


@pytest.mark.slow
async def test_live_canary_ca_bank_rate(tmp_cache_dir: Path) -> None:
    """Live probe of TE CA Bank Rate — confirms ``CCLR`` symbol + daily cadence.

    Skips when ``TE_API_KEY`` is not set. The endpoint back-fills the
    full history regardless of the window, so filter client-side to
    the recent 2Y before asserting the band.
    """
    api_key = os.environ.get("TE_API_KEY")
    if not api_key:
        pytest.skip("TE_API_KEY not set")
    conn = TEConnector(api_key=api_key, cache_dir=str(tmp_cache_dir))
    try:
        today = datetime.now(tz=UTC).date()
        start = today - timedelta(days=365 * 2)
        obs = await conn.fetch_ca_bank_rate(start, today)
        assert len(obs) >= 3
        assert obs[0].historical_data_symbol == "CCLR"
        assert obs[0].country == "CA"
        recent = [o for o in obs if o.observation_date >= start]
        for o in recent:
            # BoC overnight stayed within [0.25, 5.00]% across 2023-26.
            assert 0.0 <= o.value <= 10.0
    finally:
        await conn.aclose()


async def test_wrapper_au_cash_rate_happy_path(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """TE ``interest rate`` for AU returns ``RBATCTR`` (RBA cash-rate target)."""
    httpx_mock.add_response(
        method="GET",
        json=[
            {
                "Country": "Australia",
                "Category": "Interest Rate",
                "DateTime": "2024-11-05T00:00:00",
                "Value": 4.35,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "RBATCTR",
                "LastUpdate": "2024-11-05T03:30:00",
            },
            {
                "Country": "Australia",
                "Category": "Interest Rate",
                "DateTime": "2025-02-18T00:00:00",
                "Value": 4.10,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "RBATCTR",
                "LastUpdate": "2025-02-18T03:30:00",
            },
            {
                "Country": "Australia",
                "Category": "Interest Rate",
                "DateTime": "2026-04-07T00:00:00",
                "Value": 4.10,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "RBATCTR",
                "LastUpdate": "2026-04-07T03:30:00",
            },
        ],
    )
    obs = await te_connector.fetch_au_cash_rate(date(2024, 1, 1), date(2026, 5, 1))
    assert len(obs) == 3
    assert obs[0].country == "AU"
    assert obs[0].indicator == "interest rate"
    assert obs[0].historical_data_symbol == "RBATCTR"
    # RBA target cash rate stayed in [0.10, 17.5] pct post-1990.
    for o in obs:
        assert 0.0 <= o.value <= 20.0


async def test_wrapper_au_cash_rate_raises_on_source_drift(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """If TE swaps in a non-RBATCTR symbol, raise — catches mis-attribution."""
    httpx_mock.add_response(
        method="GET",
        json=[
            {
                "Country": "Australia",
                "Category": "Interest Rate",
                "DateTime": "2025-02-18T00:00:00",
                "Value": 4.10,
                "HistoricalDataSymbol": "AUSINTR",
            }
        ],
    )
    with pytest.raises(DataUnavailableError, match="AU-cash-rate source drift"):
        await te_connector.fetch_au_cash_rate(date(2024, 1, 1), date(2025, 12, 31))


async def test_wrapper_au_cash_rate_empty_response_raises(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """Empty payload → ``fetch_indicator`` raises; cascade callers treat as
    TE-unavailable and fall through to RBA native."""
    httpx_mock.add_response(method="GET", json=[])
    with pytest.raises(DataUnavailableError, match="empty series"):
        await te_connector.fetch_au_cash_rate(date(2024, 1, 1), date(2025, 12, 31))


async def test_wrapper_au_cash_rate_from_cassette(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """Full-history cassette confirms 300+ RBATCTR daily observations."""
    payload = _load_cassette("te_au_cash_rate_2024_01_02.json")
    httpx_mock.add_response(method="GET", json=payload)
    obs = await te_connector.fetch_au_cash_rate(date(2024, 1, 1), date(2024, 12, 31))
    assert len(obs) >= 300
    assert obs[0].historical_data_symbol == "RBATCTR"
    assert obs[0].country == "AU"
    # Recent window: 2024+ RBA cash rate sits in [3.60, 4.35]%.
    recent = obs[-24:]
    for o in recent:
        assert 0.0 <= o.value <= 10.0


@pytest.mark.slow
async def test_live_canary_au_cash_rate(tmp_cache_dir: Path) -> None:
    """Live probe of TE AU Cash Rate — confirms ``RBATCTR`` symbol + daily cadence.

    Skips when ``TE_API_KEY`` is not set. The endpoint back-fills the
    full history regardless of the window, so filter client-side to
    the recent 2Y before asserting the band.
    """
    api_key = os.environ.get("TE_API_KEY")
    if not api_key:
        pytest.skip("TE_API_KEY not set")
    conn = TEConnector(api_key=api_key, cache_dir=str(tmp_cache_dir))
    try:
        today = datetime.now(tz=UTC).date()
        start = today - timedelta(days=365 * 2)
        obs = await conn.fetch_au_cash_rate(start, today)
        assert len(obs) >= 3
        assert obs[0].historical_data_symbol == "RBATCTR"
        assert obs[0].country == "AU"
        recent = [o for o in obs if o.observation_date >= start]
        for o in recent:
            # RBA cash-rate target stayed within [0.10, 4.35]% across 2023-26.
            assert 0.0 <= o.value <= 10.0
    finally:
        await conn.aclose()


async def test_wrapper_nz_ocr_happy_path(httpx_mock: HTTPXMock, te_connector: TEConnector) -> None:
    """TE ``interest rate`` for NZ returns ``NZOCRS`` (RBNZ Official Cash Rate)."""
    httpx_mock.add_response(
        method="GET",
        json=[
            {
                "Country": "New Zealand",
                "Category": "Interest Rate",
                "DateTime": "2024-08-14T00:00:00",
                "Value": 5.25,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "NZOCRS",
                "LastUpdate": "2024-08-14T02:00:00",
            },
            {
                "Country": "New Zealand",
                "Category": "Interest Rate",
                "DateTime": "2025-02-19T00:00:00",
                "Value": 3.75,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "NZOCRS",
                "LastUpdate": "2025-02-19T02:00:00",
            },
            {
                "Country": "New Zealand",
                "Category": "Interest Rate",
                "DateTime": "2026-04-08T00:00:00",
                "Value": 2.25,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "NZOCRS",
                "LastUpdate": "2026-04-08T02:00:00",
            },
        ],
    )
    obs = await te_connector.fetch_nz_ocr(date(2024, 1, 1), date(2026, 5, 1))
    assert len(obs) == 3
    assert obs[0].country == "NZ"
    assert obs[0].indicator == "interest rate"
    assert obs[0].historical_data_symbol == "NZOCRS"
    # RBNZ OCR stayed in [0.25, 8.25]% post-1999 inception.
    for o in obs:
        assert 0.0 <= o.value <= 20.0


async def test_wrapper_nz_ocr_raises_on_source_drift(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """If TE swaps in a non-NZOCRS symbol, raise — catches mis-attribution."""
    httpx_mock.add_response(
        method="GET",
        json=[
            {
                "Country": "New Zealand",
                "Category": "Interest Rate",
                "DateTime": "2025-02-19T00:00:00",
                "Value": 3.75,
                "HistoricalDataSymbol": "NZINTR",
            }
        ],
    )
    with pytest.raises(DataUnavailableError, match="NZ-OCR source drift"):
        await te_connector.fetch_nz_ocr(date(2024, 1, 1), date(2025, 12, 31))


async def test_wrapper_nz_ocr_empty_response_raises(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """Empty payload → ``fetch_indicator`` raises; cascade callers treat as
    TE-unavailable and fall through to RBNZ scaffold / FRED."""
    httpx_mock.add_response(method="GET", json=[])
    with pytest.raises(DataUnavailableError, match="empty series"):
        await te_connector.fetch_nz_ocr(date(2024, 1, 1), date(2025, 12, 31))


async def test_wrapper_nz_ocr_from_cassette(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """Full-history cassette confirms 500+ NZOCRS observations end-to-end."""
    payload = _load_cassette("te_nz_ocr_2024_01_02.json")
    httpx_mock.add_response(method="GET", json=payload)
    obs = await te_connector.fetch_nz_ocr(date(2024, 1, 1), date(2024, 12, 31))
    assert len(obs) >= 300
    assert obs[0].historical_data_symbol == "NZOCRS"
    assert obs[0].country == "NZ"
    # Recent window: RBNZ OCR sits in [2.25, 5.50]% across 2023-26.
    recent = obs[-24:]
    for o in recent:
        assert 0.0 <= o.value <= 10.0


@pytest.mark.slow
async def test_live_canary_nz_ocr(tmp_cache_dir: Path) -> None:
    """Live probe of TE NZ OCR — confirms ``NZOCRS`` symbol + daily cadence.

    Skips when ``TE_API_KEY`` is not set. TE back-fills the full
    history regardless of the window, so filter client-side to the
    recent 2Y before asserting the band.
    """
    api_key = os.environ.get("TE_API_KEY")
    if not api_key:
        pytest.skip("TE_API_KEY not set")
    conn = TEConnector(api_key=api_key, cache_dir=str(tmp_cache_dir))
    try:
        today = datetime.now(tz=UTC).date()
        start = today - timedelta(days=365 * 2)
        obs = await conn.fetch_nz_ocr(start, today)
        assert len(obs) >= 3
        assert obs[0].historical_data_symbol == "NZOCRS"
        assert obs[0].country == "NZ"
        recent = [o for o in obs if o.observation_date >= start]
        for o in recent:
            # RBNZ OCR stayed within [0.25, 5.50]% across 2023-26.
            assert 0.0 <= o.value <= 10.0
    finally:
        await conn.aclose()


async def test_wrapper_ch_policy_rate_happy_path(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """TE ``interest rate`` for CH returns ``SZLTTR`` (SNB policy rate)."""
    httpx_mock.add_response(
        method="GET",
        json=[
            {
                "Country": "Switzerland",
                "Category": "Interest Rate",
                "DateTime": "2022-09-22T00:00:00",
                "Value": 0.5,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "SZLTTR",
                "LastUpdate": "2022-09-22T07:30:00",
            },
            {
                "Country": "Switzerland",
                "Category": "Interest Rate",
                "DateTime": "2024-03-21T00:00:00",
                "Value": 1.5,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "SZLTTR",
                "LastUpdate": "2024-03-21T08:30:00",
            },
            {
                "Country": "Switzerland",
                "Category": "Interest Rate",
                "DateTime": "2026-03-19T00:00:00",
                "Value": 0.0,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "SZLTTR",
                "LastUpdate": "2026-03-19T08:30:00",
            },
        ],
    )
    obs = await te_connector.fetch_ch_policy_rate(date(2022, 1, 1), date(2026, 4, 1))
    assert len(obs) == 3
    assert obs[0].country == "CH"
    assert obs[0].indicator == "interest rate"
    assert obs[0].historical_data_symbol == "SZLTTR"
    # SNB policy rate ranged over [-0.75, 3.50]% since 2000.
    for o in obs:
        assert -1.0 <= o.value <= 5.0


async def test_wrapper_ch_policy_rate_preserves_negative_values(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """Negative-rate era 2015-2022 flows through wrapper with sign intact.

    SNB policy rate reached -0.75 % (Jan 2015 → Jun 2022). The wrapper
    must not clamp, flip, or drop negative observations — the downstream
    cascade emits ``CH_NEGATIVE_RATE_ERA_DATA`` on detection.
    """
    httpx_mock.add_response(
        method="GET",
        json=[
            {
                "Country": "Switzerland",
                "Category": "Interest Rate",
                "DateTime": "2015-01-15T00:00:00",
                "Value": -0.75,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "SZLTTR",
                "LastUpdate": "2015-01-15T08:30:00",
            },
            {
                "Country": "Switzerland",
                "Category": "Interest Rate",
                "DateTime": "2020-06-18T00:00:00",
                "Value": -0.75,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "SZLTTR",
                "LastUpdate": "2020-06-18T08:30:00",
            },
            {
                "Country": "Switzerland",
                "Category": "Interest Rate",
                "DateTime": "2022-06-16T00:00:00",
                "Value": -0.25,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "SZLTTR",
                "LastUpdate": "2022-06-16T07:30:00",
            },
        ],
    )
    obs = await te_connector.fetch_ch_policy_rate(date(2015, 1, 1), date(2022, 12, 31))
    assert len(obs) == 3
    values = [o.value for o in obs]
    assert values == [-0.75, -0.75, -0.25]
    # Preserving sign is the whole point — guard explicitly.
    assert all(v < 0 for v in values)


async def test_wrapper_ch_policy_rate_raises_on_source_drift(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """If TE swaps in a non-SZLTTR symbol, raise — catches mis-attribution."""
    httpx_mock.add_response(
        method="GET",
        json=[
            {
                "Country": "Switzerland",
                "Category": "Interest Rate",
                "DateTime": "2024-03-21T00:00:00",
                "Value": 1.5,
                "HistoricalDataSymbol": "SWINTR",
            }
        ],
    )
    with pytest.raises(DataUnavailableError, match="CH-policy-rate source drift"):
        await te_connector.fetch_ch_policy_rate(date(2024, 1, 1), date(2024, 12, 31))


async def test_wrapper_ch_policy_rate_empty_response_raises(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """Empty payload → ``fetch_indicator`` raises; cascade callers treat as
    TE-unavailable and fall through to SNB native."""
    httpx_mock.add_response(method="GET", json=[])
    with pytest.raises(DataUnavailableError, match="empty series"):
        await te_connector.fetch_ch_policy_rate(date(2024, 1, 1), date(2024, 12, 31))


async def test_wrapper_ch_policy_rate_from_cassette(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """Full-history cassette confirms 300+ SZLTTR daily obs + 93 negatives."""
    payload = _load_cassette("te_ch_policy_rate_2024_01_02.json")
    httpx_mock.add_response(method="GET", json=payload)
    obs = await te_connector.fetch_ch_policy_rate(date(2000, 1, 1), date(2026, 4, 1))
    assert len(obs) >= 300
    assert obs[0].historical_data_symbol == "SZLTTR"
    assert obs[0].country == "CH"
    # Negative-rate era 2014-12-18 → 2022-08-31 is preserved in the
    # cassette; exactly 93 strictly-negative rows per Sprint V probe.
    neg = [o for o in obs if o.value < 0]
    assert len(neg) >= 80  # empirical: 93; guard the ≥80 lower bound
    # Boundaries of the negative era line up with documented SNB history.
    first_neg = min(neg, key=lambda o: o.observation_date)
    last_neg = max(neg, key=lambda o: o.observation_date)
    assert first_neg.observation_date >= date(2014, 1, 1)
    assert last_neg.observation_date <= date(2023, 1, 1)


@pytest.mark.slow
async def test_live_canary_ch_policy_rate(tmp_cache_dir: Path) -> None:
    """Live probe of TE CH Policy Rate — confirms ``SZLTTR`` symbol + daily cadence.

    Skips when ``TE_API_KEY`` is not set. The endpoint back-fills the
    full history regardless of the window, so a generous 12Y lookback
    still returns at least the negative-rate era for historical
    validation.
    """
    api_key = os.environ.get("TE_API_KEY")
    if not api_key:
        pytest.skip("TE_API_KEY not set")
    conn = TEConnector(api_key=api_key, cache_dir=str(tmp_cache_dir))
    try:
        today = datetime.now(tz=UTC).date()
        start = today - timedelta(days=365 * 12)
        obs = await conn.fetch_ch_policy_rate(start, today)
        assert len(obs) >= 10
        assert obs[0].historical_data_symbol == "SZLTTR"
        assert obs[0].country == "CH"
        # Full CH policy-rate corridor 2014-2026: [-0.75, 1.75] pct.
        for o in obs:
            assert -1.0 <= o.value <= 5.0
        # Historical negative-rate preservation: with 12Y lookback we
        # expect to see at least one strictly-negative observation.
        neg = [o for o in obs if o.value < 0]
        assert len(neg) >= 1, "expected at least one negative-rate era observation"
    finally:
        await conn.aclose()


async def test_wrapper_no_policy_rate_happy_path(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """TE ``interest rate`` for NO returns ``NOBRDEP`` (Norges Bank policy rate)."""
    httpx_mock.add_response(
        method="GET",
        json=[
            {
                "Country": "Norway",
                "Category": "Interest Rate",
                "DateTime": "2020-05-08T00:00:00",
                "Value": 0.0,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "NOBRDEP",
                "LastUpdate": "2020-05-08T09:00:00",
            },
            {
                "Country": "Norway",
                "Category": "Interest Rate",
                "DateTime": "2024-01-25T00:00:00",
                "Value": 4.5,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "NOBRDEP",
                "LastUpdate": "2024-01-25T09:00:00",
            },
            {
                "Country": "Norway",
                "Category": "Interest Rate",
                "DateTime": "2026-03-26T00:00:00",
                "Value": 4.0,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "NOBRDEP",
                "LastUpdate": "2026-03-26T09:00:00",
            },
        ],
    )
    obs = await te_connector.fetch_no_policy_rate(date(2020, 1, 1), date(2026, 4, 1))
    assert len(obs) == 3
    assert obs[0].country == "NO"
    assert obs[0].indicator == "interest rate"
    assert obs[0].historical_data_symbol == "NOBRDEP"
    # Norges Bank policy rate ranged over [0.0, 8.5]% since 1991;
    # across 2020+ the observed corridor is [0.0, 4.75]%.
    for o in obs:
        assert 0.0 <= o.value <= 10.0


async def test_wrapper_no_policy_rate_positive_only(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """Norway never ran a negative policy rate — the minimum is 0 %.

    Validates the standard positive-only wrapper contract (contrast the
    CH / SE / EA wrappers which span the 2014-2022 negative-rate era).
    The 2020-2021 COVID-response trough sat at exactly 0 %; the wrapper
    passes that through verbatim.
    """
    httpx_mock.add_response(
        method="GET",
        json=[
            {
                "Country": "Norway",
                "Category": "Interest Rate",
                "DateTime": "2020-05-08T00:00:00",
                "Value": 0.0,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "NOBRDEP",
                "LastUpdate": "2020-05-08T09:00:00",
            },
            {
                "Country": "Norway",
                "Category": "Interest Rate",
                "DateTime": "2021-09-24T00:00:00",
                "Value": 0.25,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "NOBRDEP",
                "LastUpdate": "2021-09-24T09:00:00",
            },
        ],
    )
    obs = await te_connector.fetch_no_policy_rate(date(2020, 1, 1), date(2022, 12, 31))
    assert len(obs) == 2
    values = [o.value for o in obs]
    assert values == [0.0, 0.25]
    # Guard the positive-only contract — no row should ever be negative
    # for NO across the full TE history.
    assert all(v >= 0 for v in values)


async def test_wrapper_no_policy_rate_raises_on_source_drift(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """If TE swaps in a non-NOBRDEP symbol, raise — catches mis-attribution."""
    httpx_mock.add_response(
        method="GET",
        json=[
            {
                "Country": "Norway",
                "Category": "Interest Rate",
                "DateTime": "2024-01-25T00:00:00",
                "Value": 4.5,
                "HistoricalDataSymbol": "NORWINTR",
            }
        ],
    )
    with pytest.raises(DataUnavailableError, match="NO-policy-rate source drift"):
        await te_connector.fetch_no_policy_rate(date(2024, 1, 1), date(2024, 12, 31))


async def test_wrapper_no_policy_rate_empty_response_raises(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """Empty payload → ``fetch_indicator`` raises; cascade callers treat as
    TE-unavailable and fall through to Norges Bank DataAPI native."""
    httpx_mock.add_response(method="GET", json=[])
    with pytest.raises(DataUnavailableError, match="empty series"):
        await te_connector.fetch_no_policy_rate(date(2024, 1, 1), date(2024, 12, 31))


async def test_wrapper_no_policy_rate_from_cassette(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """Full-history cassette confirms 500+ NOBRDEP daily obs (no negatives)."""
    payload = _load_cassette("te_no_policy_rate_2024_01_02.json")
    httpx_mock.add_response(method="GET", json=payload)
    obs = await te_connector.fetch_no_policy_rate(date(1991, 1, 1), date(2026, 4, 1))
    assert len(obs) >= 500
    assert obs[0].historical_data_symbol == "NOBRDEP"
    assert obs[0].country == "NO"
    # Standard positive-only contract — no row should ever be negative
    # across the full 35Y Norges Bank history.
    neg = [o for o in obs if o.value < 0]
    assert neg == [], f"expected 0 negative rows; found {len(neg)}"
    # Minimum observed is 0 % across the 2020-2021 COVID trough; maximum
    # sits at 8.5 % (1991-01-01 legacy opening).
    values = [o.value for o in obs]
    assert min(values) >= 0.0
    assert max(values) <= 12.0


@pytest.mark.slow
async def test_live_canary_no_policy_rate(tmp_cache_dir: Path) -> None:
    """Live probe of TE NO Policy Rate — confirms ``NOBRDEP`` + daily cadence.

    Skips when ``TE_API_KEY`` is not set. The endpoint back-fills the
    full history regardless of the window; a 5Y lookback still returns
    enough rows to cross-validate the 2022-2024 tightening cycle.
    """
    api_key = os.environ.get("TE_API_KEY")
    if not api_key:
        pytest.skip("TE_API_KEY not set")
    conn = TEConnector(api_key=api_key, cache_dir=str(tmp_cache_dir))
    try:
        today = datetime.now(tz=UTC).date()
        start = today - timedelta(days=365 * 5)
        obs = await conn.fetch_no_policy_rate(start, today)
        assert len(obs) >= 5
        assert obs[0].historical_data_symbol == "NOBRDEP"
        assert obs[0].country == "NO"
        # NO policy-rate corridor 2020-2026 sits in [0.0, 4.75] %.
        for o in obs:
            assert 0.0 <= o.value <= 10.0
        # Positive-only invariant — cross-validates the cassette contract.
        assert all(o.value >= 0 for o in obs)
    finally:
        await conn.aclose()


async def test_wrapper_se_policy_rate_happy_path(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """TE ``interest rate`` for SE returns ``SWRRATEI`` (Riksbank policy rate)."""
    httpx_mock.add_response(
        method="GET",
        json=[
            {
                "Country": "Sweden",
                "Category": "Interest Rate",
                "DateTime": "2022-06-30T00:00:00",
                "Value": 0.75,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "SWRRATEI",
                "LastUpdate": "2022-06-30T08:30:00",
            },
            {
                "Country": "Sweden",
                "Category": "Interest Rate",
                "DateTime": "2023-11-23T00:00:00",
                "Value": 4.0,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "SWRRATEI",
                "LastUpdate": "2023-11-23T08:30:00",
            },
            {
                "Country": "Sweden",
                "Category": "Interest Rate",
                "DateTime": "2026-04-30T00:00:00",
                "Value": 1.75,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "SWRRATEI",
                "LastUpdate": "2026-04-01T08:39:00",
            },
        ],
    )
    obs = await te_connector.fetch_se_policy_rate(date(2022, 1, 1), date(2026, 5, 1))
    assert len(obs) == 3
    assert obs[0].country == "SE"
    assert obs[0].indicator == "interest rate"
    assert obs[0].historical_data_symbol == "SWRRATEI"
    # Riksbank policy rate ranged over [-0.50, 4.00]% since 1994.
    for o in obs:
        assert -1.0 <= o.value <= 10.0


async def test_wrapper_se_policy_rate_preserves_negative_values(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """Negative-rate era 2015-2019 flows through wrapper with sign intact.

    Riksbank repo rate reached -0.50 % (Feb 2016 → Dec 2018; with a
    -0.25 % step-up from 2019-01 before the return to zero on
    2019-12-19). The wrapper must not clamp, flip, or drop negative
    observations — the downstream cascade emits
    ``SE_NEGATIVE_RATE_ERA_DATA`` on detection, mirroring the
    Sprint V-CH pattern.
    """
    httpx_mock.add_response(
        method="GET",
        json=[
            {
                "Country": "Sweden",
                "Category": "Interest Rate",
                "DateTime": "2016-02-17T00:00:00",
                "Value": -0.5,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "SWRRATEI",
                "LastUpdate": "2016-02-17T08:30:00",
            },
            {
                "Country": "Sweden",
                "Category": "Interest Rate",
                "DateTime": "2017-12-15T00:00:00",
                "Value": -0.5,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "SWRRATEI",
                "LastUpdate": "2017-12-15T08:30:00",
            },
            {
                "Country": "Sweden",
                "Category": "Interest Rate",
                "DateTime": "2019-11-30T00:00:00",
                "Value": -0.25,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "SWRRATEI",
                "LastUpdate": "2019-12-13T16:35:00",
            },
        ],
    )
    obs = await te_connector.fetch_se_policy_rate(date(2015, 1, 1), date(2019, 12, 31))
    assert len(obs) == 3
    values = [o.value for o in obs]
    assert values == [-0.5, -0.5, -0.25]
    # Preserving sign is the whole point — guard explicitly.
    assert all(v < 0 for v in values)


async def test_wrapper_se_policy_rate_raises_on_source_drift(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """If TE swaps in a non-SWRRATEI symbol, raise — catches mis-attribution."""
    httpx_mock.add_response(
        method="GET",
        json=[
            {
                "Country": "Sweden",
                "Category": "Interest Rate",
                "DateTime": "2024-03-21T00:00:00",
                "Value": 4.0,
                "HistoricalDataSymbol": "SEPRATE",
            }
        ],
    )
    with pytest.raises(DataUnavailableError, match="SE-policy-rate source drift"):
        await te_connector.fetch_se_policy_rate(date(2024, 1, 1), date(2024, 12, 31))


async def test_wrapper_se_policy_rate_empty_response_raises(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """Empty payload → ``fetch_indicator`` raises; cascade callers treat as
    TE-unavailable and fall through to Riksbank native."""
    httpx_mock.add_response(method="GET", json=[])
    with pytest.raises(DataUnavailableError, match="empty series"):
        await te_connector.fetch_se_policy_rate(date(2024, 1, 1), date(2024, 12, 31))


async def test_wrapper_se_policy_rate_from_cassette(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """Full-history cassette confirms 400+ SWRRATEI daily obs + 58 negatives."""
    payload = _load_cassette("te_se_policy_rate_2024_01_02.json")
    httpx_mock.add_response(method="GET", json=payload)
    obs = await te_connector.fetch_se_policy_rate(date(1994, 1, 1), date(2026, 5, 1))
    assert len(obs) >= 400
    assert obs[0].historical_data_symbol == "SWRRATEI"
    assert obs[0].country == "SE"
    # Negative-rate era 2015-02-12 → 2019-11-30 is preserved in the
    # cassette; exactly 58 strictly-negative rows per Sprint W-SE probe.
    neg = [o for o in obs if o.value < 0]
    assert len(neg) >= 50  # empirical: 58; guard the ≥50 lower bound
    # Boundaries of the negative era line up with documented Riksbank history.
    first_neg = min(neg, key=lambda o: o.observation_date)
    last_neg = max(neg, key=lambda o: o.observation_date)
    assert first_neg.observation_date >= date(2015, 1, 1)
    assert last_neg.observation_date <= date(2020, 6, 1)


@pytest.mark.slow
async def test_live_canary_se_policy_rate(tmp_cache_dir: Path) -> None:
    """Live probe of TE SE Policy Rate — confirms ``SWRRATEI`` symbol + daily cadence.

    Skips when ``TE_API_KEY`` is not set. The endpoint back-fills the
    full history regardless of the window, so a generous 12Y lookback
    still returns at least the negative-rate era for historical
    validation.
    """
    api_key = os.environ.get("TE_API_KEY")
    if not api_key:
        pytest.skip("TE_API_KEY not set")
    conn = TEConnector(api_key=api_key, cache_dir=str(tmp_cache_dir))
    try:
        today = datetime.now(tz=UTC).date()
        start = today - timedelta(days=365 * 12)
        obs = await conn.fetch_se_policy_rate(start, today)
        assert len(obs) >= 10
        assert obs[0].historical_data_symbol == "SWRRATEI"
        assert obs[0].country == "SE"
        # Full Riksbank policy-rate corridor 2014-2026: [-0.50, 4.00] pct.
        for o in obs:
            assert -1.0 <= o.value <= 10.0
        # Historical negative-rate preservation: with 12Y lookback we
        # expect to see at least one strictly-negative observation.
        neg = [o for o in obs if o.value < 0]
        assert len(neg) >= 1, "expected at least one negative-rate era observation"
    finally:
        await conn.aclose()


async def test_wrapper_dk_policy_rate_happy_path(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """TE ``interest rate`` for DK returns ``DEBRDISC`` (Nationalbanken discount rate).

    Note the source-instrument divergence: TE exposes the legacy
    discount rate (``diskontoen``), not the active CD rate that
    Nationalbanken uses to defend the DKK/EUR peg — see the wrapper
    docstring + Sprint Y-DK retro §4 for the empirical context.
    """
    httpx_mock.add_response(
        method="GET",
        json=[
            {
                "Country": "Denmark",
                "Category": "Interest Rate",
                "DateTime": "2022-09-09T00:00:00",
                "Value": 0.65,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "DEBRDISC",
                "LastUpdate": "2022-09-09T08:30:00",
            },
            {
                "Country": "Denmark",
                "Category": "Interest Rate",
                "DateTime": "2024-06-30T00:00:00",
                "Value": 3.25,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "DEBRDISC",
                "LastUpdate": "2024-06-30T08:30:00",
            },
            {
                "Country": "Denmark",
                "Category": "Interest Rate",
                "DateTime": "2026-03-31T00:00:00",
                "Value": 1.6,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "DEBRDISC",
                "LastUpdate": "2026-04-02T08:47:00",
            },
        ],
    )
    obs = await te_connector.fetch_dk_policy_rate(date(2022, 1, 1), date(2026, 5, 1))
    assert len(obs) == 3
    assert obs[0].country == "DK"
    assert obs[0].indicator == "interest rate"
    assert obs[0].historical_data_symbol == "DEBRDISC"
    # Discount-rate corridor across [-0.60, 9.00] % since 1987.
    for o in obs:
        assert -1.0 <= o.value <= 10.0


async def test_wrapper_dk_policy_rate_preserves_negative_values(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """Discount-rate negative window 2021-03-31 → 2022-08-31 flows through unchanged.

    The discount rate spent a comparatively short window strictly-
    negative (18 rows; min -0.60 % per Sprint Y-DK probe) — the deeper
    -0.75 % CD-rate corridor 2015-2022 is captured separately by the
    Nationalbanken native cascade slot. This test guards the wrapper-
    layer sign preservation specifically for the discount-rate path.
    """
    httpx_mock.add_response(
        method="GET",
        json=[
            {
                "Country": "Denmark",
                "Category": "Interest Rate",
                "DateTime": "2021-03-31T00:00:00",
                "Value": -0.5,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "DEBRDISC",
                "LastUpdate": "2021-03-31T08:30:00",
            },
            {
                "Country": "Denmark",
                "Category": "Interest Rate",
                "DateTime": "2021-09-30T00:00:00",
                "Value": -0.6,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "DEBRDISC",
                "LastUpdate": "2021-09-30T08:30:00",
            },
            {
                "Country": "Denmark",
                "Category": "Interest Rate",
                "DateTime": "2022-08-31T00:00:00",
                "Value": -0.1,
                "Frequency": "Daily",
                "HistoricalDataSymbol": "DEBRDISC",
                "LastUpdate": "2022-08-31T08:30:00",
            },
        ],
    )
    obs = await te_connector.fetch_dk_policy_rate(date(2021, 1, 1), date(2022, 12, 31))
    assert len(obs) == 3
    values = [o.value for o in obs]
    assert values == [-0.5, -0.6, -0.1]
    assert all(v < 0 for v in values)


async def test_wrapper_dk_policy_rate_raises_on_source_drift(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """If TE swaps in a non-DEBRDISC symbol, raise — catches mis-attribution.

    Source-drift is especially load-bearing for DK because the discount
    rate / CD rate / lending rate / current-account rate are four
    distinct Nationalbanken instruments that TE could plausibly cross-
    wire (see retro §4 — the Statbank ``OIBNAA`` CD rate diverged from
    the discount rate by up to 25 bps across the 2015-2022 negative
    corridor).
    """
    httpx_mock.add_response(
        method="GET",
        json=[
            {
                "Country": "Denmark",
                "Category": "Interest Rate",
                "DateTime": "2024-03-21T00:00:00",
                "Value": 3.5,
                "HistoricalDataSymbol": "DKCDRATE",
            }
        ],
    )
    with pytest.raises(DataUnavailableError, match="DK-policy-rate source drift"):
        await te_connector.fetch_dk_policy_rate(date(2024, 1, 1), date(2024, 12, 31))


async def test_wrapper_dk_policy_rate_empty_response_raises(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """Empty payload → ``fetch_indicator`` raises; cascade callers fall to native."""
    httpx_mock.add_response(method="GET", json=[])
    with pytest.raises(DataUnavailableError, match="empty series"):
        await te_connector.fetch_dk_policy_rate(date(2024, 1, 1), date(2024, 12, 31))


async def test_wrapper_dk_policy_rate_from_cassette(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """Full-history cassette confirms 400+ DEBRDISC daily obs + 18 negatives."""
    payload = _load_cassette("te_dk_policy_rate_2024_01_02.json")
    httpx_mock.add_response(method="GET", json=payload)
    obs = await te_connector.fetch_dk_policy_rate(date(1987, 1, 1), date(2026, 5, 1))
    assert len(obs) >= 400
    assert obs[0].historical_data_symbol == "DEBRDISC"
    assert obs[0].country == "DK"
    # Negative-discount-rate window 2021-03-31 → 2022-08-31 — exactly
    # 18 rows per Sprint Y-DK probe; guard the ≥ 10 lower bound.
    neg = [o for o in obs if o.value < 0]
    assert len(neg) >= 10
    first_neg = min(neg, key=lambda o: o.observation_date)
    last_neg = max(neg, key=lambda o: o.observation_date)
    assert first_neg.observation_date >= date(2020, 1, 1)
    assert last_neg.observation_date <= date(2023, 6, 1)


@pytest.mark.slow
async def test_live_canary_dk_policy_rate(tmp_cache_dir: Path) -> None:
    """Live probe of TE DK Policy Rate — confirms ``DEBRDISC`` + daily cadence.

    Skips when ``TE_API_KEY`` is not set. Generous 6Y lookback covers
    the 2021-2022 negative-rate window so the historical-negative
    validation has data to assert on.
    """
    api_key = os.environ.get("TE_API_KEY")
    if not api_key:
        pytest.skip("TE_API_KEY not set")
    conn = TEConnector(api_key=api_key, cache_dir=str(tmp_cache_dir))
    try:
        today = datetime.now(tz=UTC).date()
        start = today - timedelta(days=365 * 6)
        obs = await conn.fetch_dk_policy_rate(start, today)
        assert len(obs) >= 10
        assert obs[0].historical_data_symbol == "DEBRDISC"
        assert obs[0].country == "DK"
        # Discount-rate band [-1.00, 5.00] % since 2014.
        for o in obs:
            assert -1.0 <= o.value <= 10.0
        # Historical negative-rate preservation: 6Y lookback covers
        # 2021-2022 — at least one strictly-negative observation.
        neg = [o for o in obs if o.value < 0]
        assert len(neg) >= 1, "expected at least one negative-discount-rate observation"
    finally:
        await conn.aclose()
