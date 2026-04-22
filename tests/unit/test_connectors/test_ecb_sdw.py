"""Unit tests for EcbSdwConnector — pytest-httpx mocked CSV responses."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from tenacity import wait_none

from sonar.connectors.base import Observation

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from pytest_httpx import HTTPXMock

from sonar.connectors.ecb_sdw import (
    ECB_DFR_DATAFLOW,
    ECB_DFR_SERIES_ID,
    ECB_EA_NOMINAL_SERIES,
    ECB_EUROSYSTEM_BS_DATAFLOW,
    ECB_EUROSYSTEM_BS_SERIES_ID,
    ECB_SERIES_TENORS,
    PERIPHERY_CAL_POINTERS,
    EcbMonetaryObservation,
    EcbSdwConnector,
    _parse_time_period,
)


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "ecb_cache"
    d.mkdir()
    return d


@pytest.fixture(autouse=True)
def _disable_tenacity_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(EcbSdwConnector._fetch_raw.retry, "wait", wait_none())


@pytest_asyncio.fixture
async def ecb_connector(tmp_cache_dir: Path) -> AsyncIterator[EcbSdwConnector]:
    conn = EcbSdwConnector(cache_dir=str(tmp_cache_dir))
    yield conn
    await conn.aclose()


def _csv(rows: list[tuple[str, str]]) -> str:
    """Build a minimal csvdata payload — TIME_PERIOD,OBS_VALUE columns."""
    out = ["TIME_PERIOD,OBS_VALUE"]
    out.extend(f"{date},{value}" for date, value in rows)
    return "\n".join(out) + "\n"


def test_series_mapping_sanity() -> None:
    assert len(ECB_EA_NOMINAL_SERIES) == 11
    assert "1M" not in ECB_EA_NOMINAL_SERIES  # ECB does not publish 1M
    assert ECB_EA_NOMINAL_SERIES["10Y"].endswith("SR_10Y")
    for series_id in ECB_EA_NOMINAL_SERIES.values():
        assert series_id in ECB_SERIES_TENORS


async def test_fetch_series_happy(httpx_mock: HTTPXMock, ecb_connector: EcbSdwConnector) -> None:
    httpx_mock.add_response(
        method="GET",
        text=_csv([("2024-01-02", "2.45"), ("2024-01-03", "2.48")]),
    )
    obs = await ecb_connector.fetch_series(
        "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y", date(2024, 1, 2), date(2024, 1, 3)
    )
    assert len(obs) == 2
    assert all(o.country_code == "EA" for o in obs)
    assert all(o.tenor_years == 10.0 for o in obs)
    assert all(o.source == "ECB_SDW" for o in obs)
    assert obs[0].yield_bps == 245
    assert obs[1].yield_bps == 248


async def test_fetch_series_filters_na(
    httpx_mock: HTTPXMock, ecb_connector: EcbSdwConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        text=_csv([("2024-01-02", "2.45"), ("2024-01-03", "NA"), ("2024-01-04", "2.50")]),
    )
    obs = await ecb_connector.fetch_series(
        "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y", date(2024, 1, 2), date(2024, 1, 4)
    )
    assert len(obs) == 2
    assert obs[1].yield_bps == 250


async def test_fetch_series_unknown_raises(
    httpx_mock: HTTPXMock, ecb_connector: EcbSdwConnector
) -> None:
    _ = httpx_mock
    with pytest.raises(ValueError, match="Unknown ECB SDW series"):
        await ecb_connector.fetch_series("BOGUS", date(2024, 1, 2), date(2024, 1, 2))


async def test_fetch_yield_curve_nominal_aggregates_11_tenors(
    httpx_mock: HTTPXMock, ecb_connector: EcbSdwConnector
) -> None:
    for idx, _series_id in enumerate(ECB_EA_NOMINAL_SERIES.values()):
        httpx_mock.add_response(
            method="GET",
            text=_csv([("2024-01-02", f"{2.0 + idx * 0.05:.2f}")]),
        )
    curve = await ecb_connector.fetch_yield_curve_nominal(
        country="EA", observation_date=date(2024, 1, 2)
    )
    assert set(curve.keys()) == set(ECB_EA_NOMINAL_SERIES.keys())
    assert curve["10Y"].tenor_years == 10.0
    assert curve["3M"].tenor_years == 0.25


async def test_fetch_yield_curve_skips_empty(
    httpx_mock: HTTPXMock, ecb_connector: EcbSdwConnector
) -> None:
    # 10 tenors return real values; one (5Y) returns empty CSV (header only).
    for series_id in ECB_EA_NOMINAL_SERIES.values():
        if series_id.endswith("SR_5Y"):
            httpx_mock.add_response(method="GET", text="TIME_PERIOD,OBS_VALUE\n")
        else:
            httpx_mock.add_response(method="GET", text=_csv([("2024-01-02", "2.45")]))
    curve = await ecb_connector.fetch_yield_curve_nominal(
        country="EA", observation_date=date(2024, 1, 2)
    )
    assert "5Y" not in curve
    assert len(curve) == 10


async def test_fetch_yield_curve_rejects_non_ea(
    httpx_mock: HTTPXMock, ecb_connector: EcbSdwConnector
) -> None:
    _ = httpx_mock
    with pytest.raises(ValueError, match="only supports country=EA"):
        await ecb_connector.fetch_yield_curve_nominal(
            country="DE", observation_date=date(2024, 1, 2)
        )


async def test_fetch_yield_curve_linker_returns_empty_for_ea(
    httpx_mock: HTTPXMock, ecb_connector: EcbSdwConnector
) -> None:
    """CAL-138 stub — EA has no inflation-indexed YC aggregate."""
    _ = httpx_mock
    linkers = await ecb_connector.fetch_yield_curve_linker(
        country="EA", observation_date=date(2024, 1, 2)
    )
    assert linkers == {}


async def test_fetch_yield_curve_linker_rejects_non_ea(
    httpx_mock: HTTPXMock, ecb_connector: EcbSdwConnector
) -> None:
    _ = httpx_mock
    with pytest.raises(ValueError, match="only accepts country=EA"):
        await ecb_connector.fetch_yield_curve_linker(
            country="DE", observation_date=date(2024, 1, 2)
        )


# ---------------------------------------------------------------------------
# Sprint A 2026-04-22 periphery deferral — per-country CAL pointers
# ---------------------------------------------------------------------------


def test_periphery_cal_pointers_complete() -> None:
    """Sprint A supersedes CAL-CURVES-EA-PERIPHERY with five per-country items."""
    assert set(PERIPHERY_CAL_POINTERS) == {"PT", "IT", "ES", "FR", "NL"}
    assert PERIPHERY_CAL_POINTERS["PT"] == "CAL-CURVES-PT-BPSTAT"
    assert PERIPHERY_CAL_POINTERS["IT"] == "CAL-CURVES-IT-BDI"
    assert PERIPHERY_CAL_POINTERS["ES"] == "CAL-CURVES-ES-BDE"
    assert PERIPHERY_CAL_POINTERS["FR"] == "CAL-CURVES-FR-BDF"
    assert PERIPHERY_CAL_POINTERS["NL"] == "CAL-CURVES-NL-DNB"


@pytest.mark.parametrize(
    ("country", "pointer"),
    [
        ("PT", "CAL-CURVES-PT-BPSTAT"),
        ("IT", "CAL-CURVES-IT-BDI"),
        ("ES", "CAL-CURVES-ES-BDE"),
        ("FR", "CAL-CURVES-FR-BDF"),
        ("NL", "CAL-CURVES-NL-DNB"),
    ],
)
async def test_fetch_yield_curve_nominal_cites_per_country_cal_for_periphery(
    httpx_mock: HTTPXMock,
    ecb_connector: EcbSdwConnector,
    country: str,
    pointer: str,
) -> None:
    _ = httpx_mock
    with pytest.raises(ValueError, match=pointer):
        await ecb_connector.fetch_yield_curve_nominal(
            country=country, observation_date=date(2024, 1, 2)
        )


@pytest.mark.parametrize(
    ("country", "pointer"),
    [
        ("PT", "CAL-CURVES-PT-BPSTAT"),
        ("IT", "CAL-CURVES-IT-BDI"),
        ("ES", "CAL-CURVES-ES-BDE"),
        ("FR", "CAL-CURVES-FR-BDF"),
        ("NL", "CAL-CURVES-NL-DNB"),
    ],
)
async def test_fetch_yield_curve_linker_cites_per_country_cal_for_periphery(
    httpx_mock: HTTPXMock,
    ecb_connector: EcbSdwConnector,
    country: str,
    pointer: str,
) -> None:
    _ = httpx_mock
    with pytest.raises(ValueError, match=pointer):
        await ecb_connector.fetch_yield_curve_linker(
            country=country, observation_date=date(2024, 1, 2)
        )


# ---------------------------------------------------------------------------
# M1-EA monetary series (CAL-098, week6 sprint 2b)
# ---------------------------------------------------------------------------


def test_m1_ea_dataflow_constants() -> None:
    assert ECB_DFR_DATAFLOW == "FM"
    assert ECB_DFR_SERIES_ID == "D.U2.EUR.4F.KR.DFR.LEV"
    assert ECB_EUROSYSTEM_BS_DATAFLOW == "ILM"
    assert ECB_EUROSYSTEM_BS_SERIES_ID == "W.U2.C.T000000.Z5.Z01"


def test_parse_time_period_daily() -> None:
    assert _parse_time_period("2024-12-18") == date(2024, 12, 18)


def test_parse_time_period_weekly_friday_anchor() -> None:
    # ISO week 2024-W41 Friday = 2024-10-11
    assert _parse_time_period("2024-W41") == date(2024, 10, 11)


def test_parse_time_period_invalid_returns_none() -> None:
    assert _parse_time_period("") is None
    assert _parse_time_period("not-a-date") is None
    assert _parse_time_period("2024-W99") is None  # week 99 doesn't exist


async def test_fetch_dfr_rate_happy(httpx_mock: HTTPXMock, ecb_connector: EcbSdwConnector) -> None:
    httpx_mock.add_response(
        method="GET",
        text=_csv([("2024-12-16", "3.25"), ("2024-12-17", "3.25"), ("2024-12-18", "3.00")]),
    )
    obs = await ecb_connector.fetch_dfr_rate(date(2024, 12, 1), date(2024, 12, 31))
    assert len(obs) == 3
    assert all(isinstance(o, EcbMonetaryObservation) for o in obs)
    assert obs[0].dataflow == "FM"
    assert obs[0].source_series_id == ECB_DFR_SERIES_ID
    assert obs[-1].value == pytest.approx(3.00)


async def test_fetch_dfr_rate_filters_na(
    httpx_mock: HTTPXMock, ecb_connector: EcbSdwConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        text=_csv([("2024-12-16", "3.25"), ("2024-12-17", "NA"), ("2024-12-18", "3.00")]),
    )
    obs = await ecb_connector.fetch_dfr_rate(date(2024, 12, 1), date(2024, 12, 31))
    assert len(obs) == 2


async def test_fetch_eurosystem_balance_sheet_happy(
    httpx_mock: HTTPXMock, ecb_connector: EcbSdwConnector
) -> None:
    httpx_mock.add_response(
        method="GET",
        text=_csv([("2024-W41", "6441605"), ("2024-W42", "6420100")]),
    )
    obs = await ecb_connector.fetch_eurosystem_balance_sheet(date(2024, 10, 1), date(2024, 10, 31))
    assert len(obs) == 2
    assert obs[0].observation_date == date(2024, 10, 11)
    assert obs[0].dataflow == "ILM"
    assert obs[0].source_series_id == ECB_EUROSYSTEM_BS_SERIES_ID
    # ~6.4T EUR — level in millions.
    assert 5_000_000 < obs[0].value < 10_000_000


async def test_fetch_monetary_caches_hit(
    httpx_mock: HTTPXMock, ecb_connector: EcbSdwConnector
) -> None:
    httpx_mock.add_response(method="GET", text=_csv([("2024-12-18", "3.00")]))
    first = await ecb_connector.fetch_dfr_rate(date(2024, 12, 1), date(2024, 12, 31))
    second = await ecb_connector.fetch_dfr_rate(date(2024, 12, 1), date(2024, 12, 31))
    assert first == second
    assert len(httpx_mock.get_requests()) == 1


async def test_cache_hit_no_http(httpx_mock: HTTPXMock, ecb_connector: EcbSdwConnector) -> None:
    _ = httpx_mock
    pre_cached = [
        Observation(
            country_code="EA",
            observation_date=date(2024, 1, 2),
            tenor_years=10.0,
            yield_bps=245,
            source="ECB_SDW",
            source_series_id="B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y",
        )
    ]
    key = "ecb_sdw:B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y:2024-01-02:2024-01-02"
    ecb_connector.cache.set(key, pre_cached)
    obs = await ecb_connector.fetch_series(
        "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y", date(2024, 1, 2), date(2024, 1, 2)
    )
    assert len(obs) == 1
    assert obs[0].yield_bps == 245
