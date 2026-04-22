"""Unit tests for TEConnector — pytest-httpx mocked JSON responses."""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from tenacity import wait_none

from sonar.connectors.base import Observation
from sonar.connectors.te import (
    _TE_TENOR_YEARS,
    TE_10Y_SYMBOLS,
    TE_YIELD_CURVE_SYMBOLS,
    TEConnector,
)
from sonar.overlays.nss import _TENOR_LABEL_TO_YEARS

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from pytest_httpx import HTTPXMock


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "te_cache"
    d.mkdir()
    return d


@pytest.fixture(autouse=True)
def _disable_tenacity_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(TEConnector._fetch_raw.retry, "wait", wait_none())


@pytest_asyncio.fixture
async def te_connector(tmp_cache_dir: Path) -> AsyncIterator[TEConnector]:
    conn = TEConnector(api_key="test:secret", cache_dir=str(tmp_cache_dir))
    yield conn
    await conn.aclose()


def test_10y_symbol_mapping_covers_t1() -> None:
    for c in ("US", "DE", "GB", "JP", "IT", "ES", "FR", "NL", "PT"):
        assert c in TE_10Y_SYMBOLS
    assert TE_10Y_SYMBOLS["US"] == "USGG10YR:IND"
    assert TE_10Y_SYMBOLS["DE"] == "GDBR10:IND"


def test_10y_symbol_uk_alias_preserved() -> None:
    """Legacy ``"UK"`` lookup returns the same GB symbol per ADR-0007."""
    assert TE_10Y_SYMBOLS["UK"] == TE_10Y_SYMBOLS["GB"] == "GUKG10:IND"


async def test_fetch_happy_us_10y(httpx_mock: HTTPXMock, te_connector: TEConnector) -> None:
    httpx_mock.add_response(
        method="GET",
        json=[
            {"Symbol": "USGG10YR:IND", "Date": "05/01/2024", "Close": 4.042},
            {"Symbol": "USGG10YR:IND", "Date": "04/01/2024", "Close": 3.991},
            {"Symbol": "USGG10YR:IND", "Date": "02/01/2024", "Close": 3.944},
        ],
    )
    rows = await te_connector.fetch_sovereign_yield_historical(
        "US", "10Y", date(2024, 1, 2), date(2024, 1, 5)
    )
    assert len(rows) == 3
    assert all(isinstance(r, Observation) for r in rows)
    assert rows[0].observation_date == date(2024, 1, 2)
    assert rows[-1].observation_date == date(2024, 1, 5)
    assert rows[0].yield_bps == 394  # 3.944 * 100
    assert rows[-1].yield_bps == 404  # 4.042 * 100
    assert all(r.country_code == "US" for r in rows)
    assert all(r.tenor_years == 10.0 for r in rows)
    assert all(r.source == "TE" for r in rows)


async def test_unsupported_tenor_raises(httpx_mock: HTTPXMock, te_connector: TEConnector) -> None:
    _ = httpx_mock
    with pytest.raises(ValueError, match="tenor='10Y' only"):
        await te_connector.fetch_sovereign_yield_historical(
            "US", "5Y", date(2024, 1, 2), date(2024, 1, 5)
        )


async def test_unknown_country_raises(httpx_mock: HTTPXMock, te_connector: TEConnector) -> None:
    _ = httpx_mock
    with pytest.raises(ValueError, match="Unknown TE 10Y symbol"):
        await te_connector.fetch_sovereign_yield_historical(
            "XX", "10Y", date(2024, 1, 2), date(2024, 1, 5)
        )


async def test_filters_malformed_rows(httpx_mock: HTTPXMock, te_connector: TEConnector) -> None:
    httpx_mock.add_response(
        method="GET",
        json=[
            {"Symbol": "USGG10YR:IND", "Date": "05/01/2024", "Close": 4.042},
            {"Symbol": "USGG10YR:IND", "Date": "bogus", "Close": 3.5},  # bad date
            {"Symbol": "USGG10YR:IND", "Date": "04/01/2024"},  # no close
            {"Symbol": "USGG10YR:IND", "Close": 3.7},  # no date
        ],
    )
    rows = await te_connector.fetch_sovereign_yield_historical(
        "US", "10Y", date(2024, 1, 2), date(2024, 1, 5)
    )
    assert len(rows) == 1
    assert rows[0].observation_date == date(2024, 1, 5)


async def test_cache_hit_no_http(httpx_mock: HTTPXMock, te_connector: TEConnector) -> None:
    _ = httpx_mock
    pre_cached = [
        Observation(
            country_code="US",
            observation_date=date(2024, 1, 2),
            tenor_years=10.0,
            yield_bps=394,
            source="TE",
            source_series_id="USGG10YR:IND",
        )
    ]
    te_connector.cache.set("te:USGG10YR:IND:2024-01-02:2024-01-02", pre_cached)
    rows = await te_connector.fetch_sovereign_yield_historical(
        "US", "10Y", date(2024, 1, 2), date(2024, 1, 2)
    )
    assert len(rows) == 1
    assert rows[0].yield_bps == 394


async def test_window_around_wrapper_widens_to_5y(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        json=[{"Symbol": "GDBR10:IND", "Date": "02/01/2024", "Close": 2.13}],
    )
    rows = await te_connector.fetch_10y_window_around("DE", observation_date=date(2024, 1, 2))
    assert len(rows) == 1
    assert rows[0].country_code == "DE"
    assert rows[0].yield_bps == 213


# ---------------------------------------------------------------------------
# GB 10Y gilt via existing fetch_sovereign_yield_historical (Sprint I-patch C2)
# ---------------------------------------------------------------------------


def test_gb_10y_symbol_mapping_present() -> None:
    """Verification — existing GUKG10:IND mapping already covers GB 10Y."""
    assert TE_10Y_SYMBOLS["GB"] == "GUKG10:IND"


async def test_fetch_gb_10y_gilt_via_existing_helper(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """``fetch_sovereign_yield_historical(country='GB', tenor='10Y')``
    returns GB 10Y gilt yields via the ``GUKG10:IND`` mapping."""
    httpx_mock.add_response(
        method="GET",
        json=[
            {"Symbol": "GUKG10:IND", "Date": "31/12/2024", "Close": 4.568},
            {"Symbol": "GUKG10:IND", "Date": "30/12/2024", "Close": 4.612},
            {"Symbol": "GUKG10:IND", "Date": "23/12/2024", "Close": 4.487},
        ],
    )
    rows = await te_connector.fetch_sovereign_yield_historical(
        "GB", "10Y", date(2024, 12, 1), date(2024, 12, 31)
    )
    assert len(rows) == 3
    assert all(r.country_code == "GB" for r in rows)
    assert all(r.tenor_years == 10.0 for r in rows)
    assert all(r.source_series_id == "GUKG10:IND" for r in rows)
    # GBP 10Y gilt late 2024 sat ~4.4-4.7%.
    assert rows[-1].yield_bps == 457  # 4.568 * 100


async def test_fetch_uk_alias_still_resolves(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """Legacy ``"UK"`` input continues to work via the dict alias entry
    (ADR-0007 backward compat); observations carry the input code."""
    httpx_mock.add_response(
        method="GET",
        json=[{"Symbol": "GUKG10:IND", "Date": "31/12/2024", "Close": 4.568}],
    )
    rows = await te_connector.fetch_sovereign_yield_historical(
        "UK", "10Y", date(2024, 12, 1), date(2024, 12, 31)
    )
    assert len(rows) == 1
    assert rows[0].source_series_id == "GUKG10:IND"


@pytest.mark.slow
async def test_live_canary_gb_10y_gilt(tmp_cache_dir: Path) -> None:
    """Live probe — GB 10Y gilt daily observations via TE markets endpoint."""
    api_key = os.environ.get("TE_API_KEY")
    if not api_key:
        pytest.skip("TE_API_KEY not set")
    conn = TEConnector(api_key=api_key, cache_dir=str(tmp_cache_dir))
    try:
        today = datetime.now(tz=UTC).date()
        start = today - timedelta(days=60)
        rows = await conn.fetch_sovereign_yield_historical("GB", "10Y", start, today)
        # Daily cadence over ~60 days → expect ≥ 20 business-day observations.
        assert len(rows) >= 20
        assert rows[0].country_code == "GB"
        # GB 10Y gilt has stayed in [0.1, 6.0]% for the past decade.
        for o in rows:
            assert 0 < o.yield_bps / 100 < 10
    finally:
        await conn.aclose()


# ---------------------------------------------------------------------------
# Multi-tenor yield curve (CAL-138 Sprint)
# ---------------------------------------------------------------------------


def test_yield_curve_symbols_supported_countries() -> None:
    """CAL-138 empirical scope: GB / JP / CA only."""
    assert set(TE_YIELD_CURVE_SYMBOLS) == {"GB", "JP", "CA"}


def test_yield_curve_symbols_tenor_counts() -> None:
    """Per empirical probe 2026-04-22: GB=12, JP=9, CA=6 tenors."""
    assert len(TE_YIELD_CURVE_SYMBOLS["GB"]) == 12
    assert len(TE_YIELD_CURVE_SYMBOLS["JP"]) == 9
    assert len(TE_YIELD_CURVE_SYMBOLS["CA"]) == 6


def test_yield_curve_symbols_gb_spectrum() -> None:
    """GB covers 1M-30Y (full Svensson, MIN_OBSERVATIONS_FOR_SVENSSON=9)."""
    gb = TE_YIELD_CURVE_SYMBOLS["GB"]
    for label in ("1M", "3M", "6M", "1Y", "2Y", "5Y", "10Y", "30Y"):
        assert label in gb, f"GB missing {label}"
    assert gb["2Y"] == "GUKG2:IND"  # no 'Y' suffix on 2Y (empirical)
    assert gb["5Y"] == "GUKG5Y:IND"  # 'Y' suffix on 5Y/7Y (empirical)


def test_yield_curve_symbols_jp_spectrum() -> None:
    """JP covers 1M-10Y (Svensson-minimum, no 20Y/30Y on TE)."""
    jp = TE_YIELD_CURVE_SYMBOLS["JP"]
    assert set(jp) == {"1M", "3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y"}
    assert jp["10Y"] == "GJGB10:IND"


def test_yield_curve_symbols_ca_spectrum() -> None:
    """CA covers 1M-2Y + 10YR (6 tenors, NS-reduced fit)."""
    ca = TE_YIELD_CURVE_SYMBOLS["CA"]
    assert set(ca) == {"1M", "3M", "6M", "1Y", "2Y", "10Y"}
    assert ca["10Y"] == "GCAN10YR:IND"


def test_yield_curve_tenor_years_match_nss() -> None:
    """Guard against drift between TE local tenor-years table and NSS canonical."""
    for label, years in _TE_TENOR_YEARS.items():
        assert _TENOR_LABEL_TO_YEARS[label] == years


async def test_fetch_yield_curve_nominal_gb_happy(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """Happy path — 12-tenor GB curve returned for 2024-12-31."""
    base_yield_pct = 4.20
    for idx, (_label, _symbol) in enumerate(TE_YIELD_CURVE_SYMBOLS["GB"].items()):
        yield_pct = base_yield_pct + idx * 0.05
        httpx_mock.add_response(
            method="GET",
            json=[{"Date": "31/12/2024", "Close": yield_pct}],
        )
    curve = await te_connector.fetch_yield_curve_nominal(
        country="GB", observation_date=date(2024, 12, 31)
    )
    assert set(curve.keys()) == set(TE_YIELD_CURVE_SYMBOLS["GB"].keys())
    assert curve["10Y"].tenor_years == 10.0
    assert curve["10Y"].country_code == "GB"
    assert curve["10Y"].source == "TE"
    # Tenors are iterated in insertion order (Python 3.7+) → 10Y is index 8.
    expected_10y_bps = round((base_yield_pct + 8 * 0.05) * 100)
    assert curve["10Y"].yield_bps == expected_10y_bps


async def test_fetch_yield_curve_nominal_jp_happy(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """Happy path — 9-tenor JP curve."""
    for _tenor_label in TE_YIELD_CURVE_SYMBOLS["JP"]:
        httpx_mock.add_response(
            method="GET",
            json=[{"Date": "31/12/2024", "Close": 0.75}],
        )
    curve = await te_connector.fetch_yield_curve_nominal(
        country="JP", observation_date=date(2024, 12, 31)
    )
    assert len(curve) == 9
    assert all(obs.country_code == "JP" for obs in curve.values())


async def test_fetch_yield_curve_nominal_ca_happy(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """Happy path — 6-tenor CA curve (NS-reduced MIN_OBSERVATIONS)."""
    for _tenor_label in TE_YIELD_CURVE_SYMBOLS["CA"]:
        httpx_mock.add_response(
            method="GET",
            json=[{"Date": "31/12/2024", "Close": 3.25}],
        )
    curve = await te_connector.fetch_yield_curve_nominal(
        country="CA", observation_date=date(2024, 12, 31)
    )
    assert len(curve) == 6
    assert curve["10Y"].source_series_id == "GCAN10YR:IND"


async def test_fetch_yield_curve_nominal_rejects_unsupported(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """AU/NZ/CH/SE/NO/DK + EA periphery rejected with clear pointer to CAL."""
    _ = httpx_mock
    for unsupported in ("AU", "NZ", "CH", "SE", "NO", "DK", "IT", "FR", "US"):
        with pytest.raises(ValueError, match="TE yield curve only supports"):
            await te_connector.fetch_yield_curve_nominal(
                country=unsupported, observation_date=date(2024, 12, 31)
            )


async def test_fetch_yield_curve_nominal_skips_empty_tenors(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """Tenor with empty response is omitted from output (caller decides)."""
    symbols = list(TE_YIELD_CURVE_SYMBOLS["CA"].items())
    for idx, (_label, _symbol) in enumerate(symbols):
        if idx == 2:  # 6M returns empty
            httpx_mock.add_response(method="GET", json=[])
        else:
            httpx_mock.add_response(
                method="GET",
                json=[{"Date": "31/12/2024", "Close": 3.25}],
            )
    curve = await te_connector.fetch_yield_curve_nominal(
        country="CA", observation_date=date(2024, 12, 31)
    )
    assert "6M" not in curve
    assert len(curve) == 5


async def test_fetch_yield_curve_nominal_picks_latest_in_window(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """7-day window; connector picks the most recent date ≤ observation_date."""
    ca_tenors = list(TE_YIELD_CURVE_SYMBOLS["CA"].items())
    # First tenor returns multiple dates to exercise the latest-pick logic;
    # remaining tenors return a single row each.
    for idx, _item in enumerate(ca_tenors):
        if idx == 0:
            httpx_mock.add_response(
                method="GET",
                json=[
                    {"Date": "30/12/2024", "Close": 3.25},
                    {"Date": "31/12/2024", "Close": 3.30},
                    {"Date": "27/12/2024", "Close": 3.20},
                ],
            )
        else:
            httpx_mock.add_response(
                method="GET",
                json=[{"Date": "31/12/2024", "Close": 3.40}],
            )
    curve = await te_connector.fetch_yield_curve_nominal(
        country="CA", observation_date=date(2024, 12, 31)
    )
    first_label = ca_tenors[0][0]
    assert curve[first_label].observation_date == date(2024, 12, 31)
    assert curve[first_label].yield_bps == 330  # 3.30 * 100


async def test_fetch_yield_curve_linker_returns_empty_for_supported(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """CAL-138 stub — TE does not expose linker yields; empty dict for all."""
    _ = httpx_mock
    for country in ("GB", "JP", "CA"):
        linkers = await te_connector.fetch_yield_curve_linker(
            country=country, observation_date=date(2024, 12, 31)
        )
        assert linkers == {}


async def test_fetch_yield_curve_linker_rejects_unsupported(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    _ = httpx_mock
    with pytest.raises(ValueError, match="TE yield curve linker stub"):
        await te_connector.fetch_yield_curve_linker(
            country="AU", observation_date=date(2024, 12, 31)
        )


@pytest.mark.slow
async def test_live_canary_gb_yield_curve_multi_tenor(tmp_cache_dir: Path) -> None:
    """Live probe — GB full-spectrum yield curve via Bloomberg symbols.

    Asserts ≥ 8 tenors return (allow a couple of TE-side gaps) and all
    yields sit inside a plausible GBP range.
    """
    api_key = os.environ.get("TE_API_KEY")
    if not api_key:
        pytest.skip("TE_API_KEY not set")
    conn = TEConnector(api_key=api_key, cache_dir=str(tmp_cache_dir))
    try:
        target = date(2024, 12, 30)  # stable historical date
        curve = await conn.fetch_yield_curve_nominal(country="GB", observation_date=target)
        assert len(curve) >= 8, f"GB curve thin: {list(curve)}"
        for obs in curve.values():
            assert obs.country_code == "GB"
            assert -50 < obs.yield_bps < 1000  # -0.5% to 10%
    finally:
        await conn.aclose()


@pytest.mark.slow
async def test_live_canary_jp_yield_curve_multi_tenor(tmp_cache_dir: Path) -> None:
    """Live probe — JP full-spectrum yield curve via GJGB family."""
    api_key = os.environ.get("TE_API_KEY")
    if not api_key:
        pytest.skip("TE_API_KEY not set")
    conn = TEConnector(api_key=api_key, cache_dir=str(tmp_cache_dir))
    try:
        target = date(2024, 12, 30)
        curve = await conn.fetch_yield_curve_nominal(country="JP", observation_date=target)
        assert len(curve) >= 7, f"JP curve thin: {list(curve)}"
        for obs in curve.values():
            assert obs.country_code == "JP"
            # JP yields historically bounded to [-0.2%, 2.0%] decade-long band.
            assert -50 < obs.yield_bps < 500
    finally:
        await conn.aclose()


@pytest.mark.slow
async def test_live_canary_ca_yield_curve_multi_tenor(tmp_cache_dir: Path) -> None:
    """Live probe — CA 6-tenor yield curve (NS-reduced feed)."""
    api_key = os.environ.get("TE_API_KEY")
    if not api_key:
        pytest.skip("TE_API_KEY not set")
    conn = TEConnector(api_key=api_key, cache_dir=str(tmp_cache_dir))
    try:
        target = date(2024, 12, 30)
        curve = await conn.fetch_yield_curve_nominal(country="CA", observation_date=target)
        assert len(curve) >= 5, f"CA curve thin: {list(curve)}"
        for obs in curve.values():
            assert obs.country_code == "CA"
            assert 0 < obs.yield_bps < 1000  # 0-10% band
    finally:
        await conn.aclose()
