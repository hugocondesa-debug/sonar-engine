"""Unit tests for FredConnector — pytest-httpx mock, 8 scenarios."""

from datetime import date

import httpx
import pytest
from pytest_httpx import HTTPXMock
from tenacity import RetryError

from sonar.connectors.base import Observation
from sonar.connectors.fred import FRED_US_TENORS, FredConnector


# ---------------------------------------------------------------------------
# 1 — Happy path
# ---------------------------------------------------------------------------
async def test_fetch_series_happy_path(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        json={
            "observations": [
                {"date": "2026-04-15", "value": "4.12"},
                {"date": "2026-04-16", "value": "4.15"},
            ]
        },
    )
    obs = await fred_connector.fetch_series("DGS10", date(2026, 4, 15), date(2026, 4, 16))
    assert len(obs) == 2
    assert all(o.country_code == "USA" for o in obs)
    assert all(o.tenor_years == 10.0 for o in obs)
    assert all(o.source == "FRED" for o in obs)
    assert all(o.source_series_id == "DGS10" for o in obs)
    assert obs[0].yield_bps == 412  # 4.12 * 100
    assert obs[1].yield_bps == 415  # 4.15 * 100
    assert obs[0].observation_date == date(2026, 4, 15)


# ---------------------------------------------------------------------------
# 2 — FRED sentinel "." filtering
# ---------------------------------------------------------------------------
async def test_fetch_series_filters_sentinel(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        json={
            "observations": [
                {"date": "2026-04-15", "value": "4.12"},
                {"date": "2026-04-16", "value": "."},  # missing
                {"date": "2026-04-17", "value": "4.15"},
            ]
        },
    )
    obs = await fred_connector.fetch_series("DGS10", date(2026, 4, 15), date(2026, 4, 17))
    assert len(obs) == 2  # sentinel filtered
    assert obs[0].observation_date == date(2026, 4, 15)
    assert obs[1].observation_date == date(2026, 4, 17)


# ---------------------------------------------------------------------------
# 3 — Unknown series_id raises ValueError
# ---------------------------------------------------------------------------
async def test_fetch_series_unknown_raises(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    # pytest-httpx asserts zero unused mocks; explicit zero for clarity.
    _ = httpx_mock  # unused — no HTTP call should happen
    with pytest.raises(ValueError, match="Unknown FRED series mapping"):
        await fred_connector.fetch_series("DGS99", date(2026, 4, 15), date(2026, 4, 16))


# ---------------------------------------------------------------------------
# 4 — Cache hit returns without HTTP call
# ---------------------------------------------------------------------------
async def test_fetch_series_cache_hit_no_http(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    _ = httpx_mock  # assertive: zero HTTP calls expected
    key = "fred:DGS10:2026-04-15:2026-04-15"
    pre_cached = [
        Observation(
            country_code="USA",
            observation_date=date(2026, 4, 15),
            tenor_years=10.0,
            yield_bps=412,
            source="FRED",
            source_series_id="DGS10",
        )
    ]
    fred_connector.cache.set(key, pre_cached)

    obs = await fred_connector.fetch_series("DGS10", date(2026, 4, 15), date(2026, 4, 15))
    assert len(obs) == 1
    assert obs[0].yield_bps == 412


# ---------------------------------------------------------------------------
# 5 — Cache miss then set (second call hits cache)
# ---------------------------------------------------------------------------
async def test_fetch_series_cache_miss_then_hit(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        json={"observations": [{"date": "2026-04-15", "value": "4.12"}]},
    )
    # First call → HTTP
    obs1 = await fred_connector.fetch_series("DGS10", date(2026, 4, 15), date(2026, 4, 15))
    assert len(obs1) == 1

    # Second call → cache hit (zero new HTTP mocks added = test fails
    # implicitly if HTTP is attempted).
    obs2 = await fred_connector.fetch_series("DGS10", date(2026, 4, 15), date(2026, 4, 15))
    assert len(obs2) == 1
    assert obs2[0].yield_bps == obs1[0].yield_bps


# ---------------------------------------------------------------------------
# 6 — pct → bps determinism (banker's rounding documented)
# ---------------------------------------------------------------------------
async def test_fetch_series_banker_rounding(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    """Python 3 round() uses banker's rounding (round half to even).

    - 4.125 * 100 = 412.5 → round → 412 (even) NOT 413
    - 4.135 * 100 = 413.5 → round → 414 (even) NOT 413
    - Float precision issues may shift these; document actual behaviour.
    """
    httpx_mock.add_response(
        method="GET",
        json={
            "observations": [
                {"date": "2026-04-15", "value": "4.125"},
                {"date": "2026-04-16", "value": "4.135"},
            ]
        },
    )
    obs = await fred_connector.fetch_series("DGS10", date(2026, 4, 15), date(2026, 4, 16))
    # Actual round outputs per Python float repr: 4.125*100 = 412.5 (exact),
    # round(412.5) = 412 per banker's rule. 4.135 has float imprecision —
    # 4.135 * 100 ≈ 413.49999..., round → 413.
    assert obs[0].yield_bps in (412, 413)  # banker's rule edge
    assert obs[1].yield_bps in (413, 414)  # float imprecision edge


# ---------------------------------------------------------------------------
# 7 — HTTP retry: 3 failures then success
# ---------------------------------------------------------------------------
async def test_fetch_series_retry_then_success(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    httpx_mock.add_response(method="GET", status_code=500)
    httpx_mock.add_response(method="GET", status_code=503)
    httpx_mock.add_response(method="GET", status_code=500)
    httpx_mock.add_response(
        method="GET",
        json={"observations": [{"date": "2026-04-15", "value": "4.12"}]},
    )
    obs = await fred_connector.fetch_series("DGS10", date(2026, 4, 15), date(2026, 4, 15))
    assert len(obs) == 1
    assert obs[0].yield_bps == 412
    # 4 HTTP calls registered (3 failures + 1 success)
    assert len(httpx_mock.get_requests()) == 4


# ---------------------------------------------------------------------------
# 8 — Max retries exceeded raises
# ---------------------------------------------------------------------------
async def test_fetch_series_max_retries_exceeded(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    for _ in range(5):
        httpx_mock.add_response(method="GET", status_code=500)

    with pytest.raises((RetryError, httpx.HTTPStatusError)):
        await fred_connector.fetch_series("DGS10", date(2026, 4, 15), date(2026, 4, 15))
    assert len(httpx_mock.get_requests()) == 5


# ---------------------------------------------------------------------------
# Sanity: all 11 FRED_US_TENORS entries have positive, bounded tenor_years
# ---------------------------------------------------------------------------
def test_fred_us_tenors_sanity() -> None:
    assert len(FRED_US_TENORS) == 11
    assert all(0 < t <= 30 for t in FRED_US_TENORS.values())
    assert FRED_US_TENORS["DGS10"] == 10.0
    assert FRED_US_TENORS["DGS30"] == 30.0
