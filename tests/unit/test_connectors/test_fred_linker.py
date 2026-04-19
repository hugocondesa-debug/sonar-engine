"""Unit tests for FRED TIPS (linker) series + curve wrappers — pytest-httpx."""

from datetime import date

import pytest
from pytest_httpx import HTTPXMock

from sonar.connectors.fred import (
    FRED_SERIES_TENORS,
    FRED_US_LINKER_SERIES,
    FRED_US_NOMINAL_SERIES,
    FredConnector,
)


def test_linker_series_mapping_sanity() -> None:
    # 5 TIPS tenors; all have a matching entry in the combined lookup.
    assert len(FRED_US_LINKER_SERIES) == 5
    assert FRED_US_LINKER_SERIES["5Y"] == "DFII5"
    assert FRED_US_LINKER_SERIES["10Y"] == "DFII10"
    for series_id in FRED_US_LINKER_SERIES.values():
        assert series_id in FRED_SERIES_TENORS


def test_nominal_series_mapping_sanity() -> None:
    # Nominal: 11 tenors 1M..30Y, all in combined lookup.
    assert len(FRED_US_NOMINAL_SERIES) == 11
    assert FRED_US_NOMINAL_SERIES["1M"] == "DGS1MO"
    assert FRED_US_NOMINAL_SERIES["30Y"] == "DGS30"
    for series_id in FRED_US_NOMINAL_SERIES.values():
        assert series_id in FRED_SERIES_TENORS


async def test_fetch_series_linker_happy(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    # DFII10 2024-01-02 sample ~1.79%.
    httpx_mock.add_response(
        method="GET",
        json={"observations": [{"date": "2024-01-02", "value": "1.79"}]},
    )
    obs = await fred_connector.fetch_series("DFII10", date(2024, 1, 2), date(2024, 1, 2))
    assert len(obs) == 1
    assert obs[0].source_series_id == "DFII10"
    assert obs[0].tenor_years == 10.0
    assert obs[0].yield_bps == 179  # 1.79 * 100


async def test_fetch_yield_curve_nominal_aggregates_all_tenors(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    # 11 sequential responses, one per nominal series. Values picked so bps
    # differ (so we can verify tenor→obs mapping without cross-contamination).
    for idx, _series_id in enumerate(FRED_US_NOMINAL_SERIES.values()):
        httpx_mock.add_response(
            method="GET",
            json={"observations": [{"date": "2024-01-02", "value": f"{4.00 + idx * 0.1:.2f}"}]},
        )

    curve = await fred_connector.fetch_yield_curve_nominal(
        country="US", observation_date=date(2024, 1, 2)
    )
    assert set(curve.keys()) == set(FRED_US_NOMINAL_SERIES.keys())
    assert curve["1M"].tenor_years == 1 / 12
    assert curve["10Y"].tenor_years == 10.0


async def test_fetch_yield_curve_linker_aggregates_5_tenors(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    for idx, _series_id in enumerate(FRED_US_LINKER_SERIES.values()):
        httpx_mock.add_response(
            method="GET",
            json={"observations": [{"date": "2024-01-02", "value": f"{1.80 + idx * 0.05:.2f}"}]},
        )

    curve = await fred_connector.fetch_yield_curve_linker(
        country="US", observation_date=date(2024, 1, 2)
    )
    assert set(curve.keys()) == set(FRED_US_LINKER_SERIES.keys())
    assert curve["5Y"].tenor_years == 5.0
    assert curve["30Y"].tenor_years == 30.0


async def test_fetch_yield_curve_skips_series_with_no_obs(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    # Simulate DFII7 empty (sentinel-only), rest populated → curve has 4 tenors.
    responses: list[dict[str, list[dict[str, str]]]] = []
    for series_id in FRED_US_LINKER_SERIES.values():
        if series_id == "DFII7":
            responses.append({"observations": [{"date": "2024-01-02", "value": "."}]})
        else:
            responses.append({"observations": [{"date": "2024-01-02", "value": "1.80"}]})
    for payload in responses:
        httpx_mock.add_response(method="GET", json=payload)

    curve = await fred_connector.fetch_yield_curve_linker(
        country="US", observation_date=date(2024, 1, 2)
    )
    assert "7Y" not in curve
    assert len(curve) == 4


async def test_fetch_yield_curve_rejects_non_us(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    _ = httpx_mock  # no HTTP expected
    with pytest.raises(ValueError, match="only supports country=US"):
        await fred_connector.fetch_yield_curve_nominal(
            country="DE", observation_date=date(2024, 1, 2)
        )


async def test_fetch_yield_curve_picks_latest_in_window(
    httpx_mock: HTTPXMock, fred_connector: FredConnector
) -> None:
    # Single series covers window; curve wrapper should pick the most recent.
    # We mock only DGS1MO (first in dict) and skip the rest — to trigger `continue`
    # path we provide empty payload for others.
    first_series = next(iter(FRED_US_NOMINAL_SERIES.values()))
    httpx_mock.add_response(
        method="GET",
        json={
            "observations": [
                {"date": "2023-12-28", "value": "5.40"},
                {"date": "2024-01-02", "value": "5.52"},  # latest
            ]
        },
    )
    # Remaining 10 series return empty obs.
    for _ in range(len(FRED_US_NOMINAL_SERIES) - 1):
        httpx_mock.add_response(method="GET", json={"observations": []})

    curve = await fred_connector.fetch_yield_curve_nominal(
        country="US", observation_date=date(2024, 1, 2)
    )
    tenor_label = next(k for k, v in FRED_US_NOMINAL_SERIES.items() if v == first_series)
    assert curve[tenor_label].yield_bps == 552
    assert curve[tenor_label].observation_date == date(2024, 1, 2)
