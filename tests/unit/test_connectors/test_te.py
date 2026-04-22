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
    """CAL-138 (GB/JP/CA) + Sprint H (IT, ES) + Sprint I (FR) empirical scope."""
    assert set(TE_YIELD_CURVE_SYMBOLS) == {"GB", "JP", "CA", "IT", "ES", "FR"}


def test_yield_curve_symbols_tenor_counts() -> None:
    """Per empirical probe 2026-04-22: GB=12, JP=9, CA=6, IT=12, ES=9, FR=10."""
    assert len(TE_YIELD_CURVE_SYMBOLS["GB"]) == 12
    assert len(TE_YIELD_CURVE_SYMBOLS["JP"]) == 9
    assert len(TE_YIELD_CURVE_SYMBOLS["CA"]) == 6
    assert len(TE_YIELD_CURVE_SYMBOLS["IT"]) == 12  # full 1M-30Y spectrum
    assert len(TE_YIELD_CURVE_SYMBOLS["ES"]) == 9  # missing 1M, 2Y, 20Y
    assert len(TE_YIELD_CURVE_SYMBOLS["FR"]) == 10  # missing 3Y, 15Y


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


def test_yield_curve_symbols_it_spectrum() -> None:
    """IT covers full 1M-30Y (12 tenors, Svensson-capable; Sprint H).

    Symbol quirks: ``M``/``Y`` suffixes on sub-10Y and 15Y-30Y; 10Y alone
    drops the ``Y`` suffix (empirically ``GBTPGR10`` vs ``GBTPGR10YR``).
    """
    it = TE_YIELD_CURVE_SYMBOLS["IT"]
    assert set(it) == {
        "1M",
        "3M",
        "6M",
        "1Y",
        "2Y",
        "3Y",
        "5Y",
        "7Y",
        "10Y",
        "15Y",
        "20Y",
        "30Y",
    }
    assert it["10Y"] == "GBTPGR10:IND"  # no Y suffix on 10Y (empirical)
    assert it["2Y"] == "GBTPGR2Y:IND"
    assert it["15Y"] == "GBTPGR15Y:IND"
    assert it["30Y"] == "GBTPGR30Y:IND"


def test_yield_curve_symbols_es_spectrum() -> None:
    """ES covers 3M/6M + 1Y/3Y/5Y/7Y/10Y/15Y/30Y (9 tenors; Sprint H).

    Missing 1M, 2Y, 20Y per empirical probe 2026-04-22 — the bare-``Y``
    and no-suffix variants all returned empty on /markets/historical.
    All 1Y+ tenors use the ``YR`` suffix uniformly (unlike IT's mixed
    ``Y``/no-suffix quirk). Still Svensson-capable (> MIN_OBSERVATIONS).
    """
    es = TE_YIELD_CURVE_SYMBOLS["ES"]
    assert set(es) == {"3M", "6M", "1Y", "3Y", "5Y", "7Y", "10Y", "15Y", "30Y"}
    assert es["10Y"] == "GSPG10YR:IND"  # YR suffix (empirical)
    assert es["1Y"] == "GSPG1YR:IND"
    assert es["30Y"] == "GSPG30YR:IND"


def test_yield_curve_symbols_fr_spectrum() -> None:
    """FR covers 1M-30Y minus 3Y/15Y (10 tenors; Sprint I).

    Per empirical probe 2026-04-22 every available 1Y+ tenor uses the
    bare ``Y`` suffix (unlike ES's uniform ``YR`` or IT's mixed
    ``Y``/no-suffix); 10Y alone drops the suffix as ``GFRN10`` —
    matching the IT / GB / JP 10Y precedent. 3Y + 15Y returned empty
    across every probed spelling. 10 ≥ MIN_OBSERVATIONS_FOR_SVENSSON,
    so Svensson-capable.
    """
    fr = TE_YIELD_CURVE_SYMBOLS["FR"]
    assert set(fr) == {"1M", "3M", "6M", "1Y", "2Y", "5Y", "7Y", "10Y", "20Y", "30Y"}
    assert fr["10Y"] == "GFRN10:IND"  # no Y suffix on 10Y (empirical)
    assert fr["1Y"] == "GFRN1Y:IND"  # bare Y suffix on 1Y (vs ES's GSPG1YR)
    assert fr["20Y"] == "GFRN20Y:IND"
    assert fr["30Y"] == "GFRN30Y:IND"
    # Drift guard: 10Y symbol matches the singleton in TE_10Y_SYMBOLS so
    # the curve fetch and the legacy 10Y wrapper agree on the canonical
    # series for FR.
    assert TE_10Y_SYMBOLS["FR"] == fr["10Y"]


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


async def test_fetch_yield_curve_nominal_it_happy(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """Happy path — 12-tenor IT BTP curve (Sprint H; full Svensson)."""
    base_yield_pct = 2.50
    for idx, _item in enumerate(TE_YIELD_CURVE_SYMBOLS["IT"].items()):
        httpx_mock.add_response(
            method="GET",
            json=[{"Date": "31/12/2024", "Close": base_yield_pct + idx * 0.05}],
        )
    curve = await te_connector.fetch_yield_curve_nominal(
        country="IT", observation_date=date(2024, 12, 31)
    )
    assert set(curve.keys()) == set(TE_YIELD_CURVE_SYMBOLS["IT"].keys())
    assert curve["10Y"].country_code == "IT"
    assert curve["10Y"].source == "TE"
    assert curve["10Y"].source_series_id == "GBTPGR10:IND"
    assert all(obs.country_code == "IT" for obs in curve.values())


async def test_fetch_yield_curve_nominal_es_happy(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """Happy path — 9-tenor ES SPGB curve (Sprint H; Svensson-capable)."""
    base_yield_pct = 2.30
    for idx, _item in enumerate(TE_YIELD_CURVE_SYMBOLS["ES"].items()):
        httpx_mock.add_response(
            method="GET",
            json=[{"Date": "31/12/2024", "Close": base_yield_pct + idx * 0.08}],
        )
    curve = await te_connector.fetch_yield_curve_nominal(
        country="ES", observation_date=date(2024, 12, 31)
    )
    assert set(curve.keys()) == set(TE_YIELD_CURVE_SYMBOLS["ES"].keys())
    assert curve["10Y"].country_code == "ES"
    assert curve["10Y"].source == "TE"
    assert curve["10Y"].source_series_id == "GSPG10YR:IND"
    assert all(obs.country_code == "ES" for obs in curve.values())


async def test_fetch_yield_curve_nominal_fr_happy(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """Happy path — 10-tenor FR OAT curve (Sprint I; Svensson-capable).

    Mirrors the IT/ES Sprint H happy paths against the GFRN family.
    """
    base_yield_pct = 2.40
    for idx, _item in enumerate(TE_YIELD_CURVE_SYMBOLS["FR"].items()):
        httpx_mock.add_response(
            method="GET",
            json=[{"Date": "31/12/2024", "Close": base_yield_pct + idx * 0.07}],
        )
    curve = await te_connector.fetch_yield_curve_nominal(
        country="FR", observation_date=date(2024, 12, 31)
    )
    assert set(curve.keys()) == set(TE_YIELD_CURVE_SYMBOLS["FR"].keys())
    assert curve["10Y"].country_code == "FR"
    assert curve["10Y"].source == "TE"
    assert curve["10Y"].source_series_id == "GFRN10:IND"
    assert curve["1Y"].source_series_id == "GFRN1Y:IND"  # bare-Y suffix
    assert curve["20Y"].source_series_id == "GFRN20Y:IND"
    assert all(obs.country_code == "FR" for obs in curve.values())


async def test_fetch_yield_curve_nominal_rejects_unsupported(
    httpx_mock: HTTPXMock, te_connector: TEConnector
) -> None:
    """AU/NZ/CH/SE/NO/DK + EA periphery remainder (NL/PT) + US rejected.

    IT + ES moved to the supported set in Sprint H; FR in Sprint I.
    """
    _ = httpx_mock
    for unsupported in ("AU", "NZ", "CH", "SE", "NO", "DK", "NL", "PT", "US"):
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
    """CAL-138 + Sprint H stub — TE does not expose linker yields; empty
    dict for every supported-nominal country. Linker coverage for
    BTP€I / gilts-IL / JGBi / RRB deferred under CAL-CURVES-T1-LINKER
    (Phase 2.5 per-country native-CB feed).
    """
    _ = httpx_mock
    for country in sorted(TE_YIELD_CURVE_SYMBOLS):
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


@pytest.mark.slow
async def test_live_canary_it_yield_curve_multi_tenor(tmp_cache_dir: Path) -> None:
    """Live probe — IT 12-tenor BTP curve via GBTPGR family (Sprint H)."""
    api_key = os.environ.get("TE_API_KEY")
    if not api_key:
        pytest.skip("TE_API_KEY not set")
    conn = TEConnector(api_key=api_key, cache_dir=str(tmp_cache_dir))
    try:
        target = date(2024, 12, 30)
        curve = await conn.fetch_yield_curve_nominal(country="IT", observation_date=target)
        # Full spectrum assertion: allow a 1-tenor gap (TE thinning).
        assert len(curve) >= 10, f"IT curve thin: {list(curve)}"
        # IT BTP 10Y sat in [0.4, 7.5]% across 2010-2025.
        for obs in curve.values():
            assert obs.country_code == "IT"
            assert 0 < obs.yield_bps < 1000
    finally:
        await conn.aclose()


@pytest.mark.slow
async def test_live_canary_es_yield_curve_multi_tenor(tmp_cache_dir: Path) -> None:
    """Live probe — ES 9-tenor SPGB curve via GSPG family (Sprint H)."""
    api_key = os.environ.get("TE_API_KEY")
    if not api_key:
        pytest.skip("TE_API_KEY not set")
    conn = TEConnector(api_key=api_key, cache_dir=str(tmp_cache_dir))
    try:
        target = date(2024, 12, 30)
        curve = await conn.fetch_yield_curve_nominal(country="ES", observation_date=target)
        # Allow 1-tenor headroom for TE gaps (probe matrix is 9/9).
        assert len(curve) >= 8, f"ES curve thin: {list(curve)}"
        # ES SPGB 10Y sat in [0.05, 7.6]% across 2012-2025.
        for obs in curve.values():
            assert obs.country_code == "ES"
            assert 0 < obs.yield_bps < 1000
    finally:
        await conn.aclose()
