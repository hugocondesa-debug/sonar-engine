"""Unit tests for OECD Economic Outlook L0 connector (Sprint C)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from tenacity import wait_none

from sonar.connectors.oecd_eo import (
    OECD_EO_BASE_URL,
    OECD_EO_COUNTRY_MAP,
    OECD_EO_DATAFLOW,
    OECDEOConnector,
    OutputGapObservation,
)
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_httpx import HTTPXMock


# ---------------------------------------------------------------------------
# Canonical constants (regression guards)
# ---------------------------------------------------------------------------


def test_base_url_canonical() -> None:
    assert OECD_EO_BASE_URL == (
        "https://sdmx.oecd.org/public/rest/data/OECD.ECO.MAD,DSD_EO@DF_EO,1.4"
    )


def test_dataflow_canonical() -> None:
    assert OECD_EO_DATAFLOW == "DSD_EO@DF_EO"


def test_country_map_covers_16_t1_plus_ea() -> None:
    # 16 T1 ISO2 + EA aggregate.
    expected = {
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
        "EA",
    }
    assert set(OECD_EO_COUNTRY_MAP) == expected


def test_country_map_ea_uses_legacy_ea17() -> None:
    # OECD EO exposes only EA17 for the GAP measure (EA19/EA20 absent —
    # confirmed live 2026-04-22).
    assert OECD_EO_COUNTRY_MAP["EA"] == "EA17"


def test_country_map_iso2_to_iso3() -> None:
    assert OECD_EO_COUNTRY_MAP["US"] == "USA"
    assert OECD_EO_COUNTRY_MAP["JP"] == "JPN"
    assert OECD_EO_COUNTRY_MAP["GB"] == "GBR"
    assert OECD_EO_COUNTRY_MAP["CH"] == "CHE"


# ---------------------------------------------------------------------------
# Dataclass shape
# ---------------------------------------------------------------------------


def test_output_gap_observation_dataclass_defaults() -> None:
    obs = OutputGapObservation(
        country_code="US",
        observation_date=date(2024, 12, 31),
        gap_pct=0.537,
        ref_area="USA",
    )
    assert obs.source == "OECD_EO"
    assert obs.measure == "GAP"


# ---------------------------------------------------------------------------
# Connector lifecycle
# ---------------------------------------------------------------------------


class TestOECDEOConnectorLifecycle:
    @pytest.mark.asyncio
    async def test_instantiation_and_aclose(self, tmp_path: Path) -> None:
        conn = OECDEOConnector(cache_dir=str(tmp_path / "oecd_eo"))
        assert conn.CONNECTOR_ID == "oecd_eo"
        assert conn.CACHE_NAMESPACE == "oecd_eo"
        await conn.aclose()


# ---------------------------------------------------------------------------
# Fixtures — retry-disabled connector
# ---------------------------------------------------------------------------


@pytest.fixture
def oecd_connector(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> OECDEOConnector:
    monkeypatch.setattr(OECDEOConnector._fetch_raw.retry, "wait", wait_none())
    return OECDEOConnector(cache_dir=str(tmp_path / "oecd_eo"))


# ---------------------------------------------------------------------------
# Payload fixture — minimal SDMX-JSON body mirroring live EO response shape
# ---------------------------------------------------------------------------


def _sdmx_json_payload(ref_area: str, observations: list[tuple[str, float]]) -> dict[str, object]:
    """Minimal SDMX-JSON 2.0 payload with GAP measure + annual frequency."""
    return {
        "meta": {"schema": "sdmx-json-data-schema.json"},
        "data": {
            "dataSets": [
                {
                    "structure": 0,
                    "action": "Information",
                    "series": {
                        "0:0:0": {
                            "attributes": [0, 0, None, 0, None, 0, 0, None],
                            "annotations": [],
                            "observations": {str(i): [v] for i, (_, v) in enumerate(observations)},
                        }
                    },
                }
            ],
            "structures": [
                {
                    "name": "Economic Outlook No 118",
                    "dimensions": {
                        "observation": [
                            {
                                "id": "TIME_PERIOD",
                                "values": [{"id": tp} for tp, _ in observations],
                            }
                        ],
                        "series": [
                            {"id": "REF_AREA", "values": [{"id": ref_area}]},
                            {"id": "MEASURE", "values": [{"id": "GAP"}]},
                            {"id": "FREQ", "values": [{"id": "A"}]},
                        ],
                    },
                }
            ],
        },
    }


# ---------------------------------------------------------------------------
# fetch_output_gap happy path + parse semantics
# ---------------------------------------------------------------------------


class TestFetchOutputGap:
    @pytest.mark.asyncio
    async def test_happy_path_parses_annual_observations(
        self, httpx_mock: HTTPXMock, oecd_connector: OECDEOConnector
    ) -> None:
        httpx_mock.add_response(
            method="GET",
            json=_sdmx_json_payload(
                "USA",
                [
                    ("2020", -4.022),
                    ("2021", -0.437),
                    ("2022", -0.316),
                    ("2023", 0.167),
                    ("2024", 0.537),
                ],
            ),
        )
        gaps = await oecd_connector.fetch_output_gap("US", date(2020, 1, 1), date(2024, 12, 31))
        assert len(gaps) == 5
        assert all(isinstance(g, OutputGapObservation) for g in gaps)
        # Sorted ascending by date.
        assert gaps[0].observation_date == date(2020, 12, 31)
        assert gaps[-1].observation_date == date(2024, 12, 31)
        assert gaps[-1].gap_pct == pytest.approx(0.537)
        assert gaps[-1].ref_area == "USA"
        assert gaps[-1].country_code == "US"
        assert gaps[-1].source == "OECD_EO"
        assert gaps[-1].measure == "GAP"

    @pytest.mark.asyncio
    async def test_unsupported_country_raises_value_error(
        self, oecd_connector: OECDEOConnector
    ) -> None:
        with pytest.raises(ValueError, match="CAL-M2-T1-OUTPUT-GAP-EXPANSION"):
            await oecd_connector.fetch_output_gap("ZZ", date(2020, 1, 1), date(2024, 12, 31))

    @pytest.mark.asyncio
    async def test_ea_aggregate_uses_ea17_ref_area(
        self, httpx_mock: HTTPXMock, oecd_connector: OECDEOConnector
    ) -> None:
        httpx_mock.add_response(
            method="GET",
            json=_sdmx_json_payload("EA17", [("2024", -0.2)]),
        )
        gaps = await oecd_connector.fetch_output_gap("EA", date(2024, 1, 1), date(2024, 12, 31))
        assert len(gaps) == 1
        assert gaps[0].ref_area == "EA17"
        assert gaps[0].country_code == "EA"

    @pytest.mark.asyncio
    async def test_no_records_found_raises_data_unavailable(
        self, httpx_mock: HTTPXMock, oecd_connector: OECDEOConnector
    ) -> None:
        httpx_mock.add_response(method="GET", text="NoRecordsFound")
        with pytest.raises(DataUnavailableError, match="no records"):
            await oecd_connector.fetch_output_gap("DE", date(2020, 1, 1), date(2024, 12, 31))

    @pytest.mark.asyncio
    async def test_empty_body_raises_data_unavailable(
        self, httpx_mock: HTTPXMock, oecd_connector: OECDEOConnector
    ) -> None:
        httpx_mock.add_response(method="GET", text="")
        with pytest.raises(DataUnavailableError, match="no records"):
            await oecd_connector.fetch_output_gap("DE", date(2020, 1, 1), date(2024, 12, 31))

    @pytest.mark.asyncio
    async def test_malformed_json_raises_data_unavailable(
        self, httpx_mock: HTTPXMock, oecd_connector: OECDEOConnector
    ) -> None:
        httpx_mock.add_response(method="GET", text="not-json{")
        with pytest.raises(DataUnavailableError, match="non-JSON"):
            await oecd_connector.fetch_output_gap("DE", date(2020, 1, 1), date(2024, 12, 31))

    @pytest.mark.asyncio
    async def test_empty_series_raises_data_unavailable(
        self, httpx_mock: HTTPXMock, oecd_connector: OECDEOConnector
    ) -> None:
        # Valid SDMX-JSON envelope, but series block empty.
        httpx_mock.add_response(
            method="GET",
            json={
                "meta": {},
                "data": {
                    "dataSets": [{"structure": 0, "series": {}}],
                    "structures": [
                        {
                            "dimensions": {
                                "observation": [{"id": "TIME_PERIOD", "values": []}],
                                "series": [],
                            }
                        }
                    ],
                },
            },
        )
        with pytest.raises(DataUnavailableError, match="no usable observations"):
            await oecd_connector.fetch_output_gap("DE", date(2020, 1, 1), date(2024, 12, 31))

    @pytest.mark.asyncio
    async def test_http_error_raises_data_unavailable(
        self, httpx_mock: HTTPXMock, oecd_connector: OECDEOConnector
    ) -> None:
        # tenacity wraps the retry: stop_after_attempt(5) means 5 HTTP
        # attempts before surfacing. Register 5 x 500 responses so the
        # pytest-httpx strict-match assertion is satisfied.
        for _ in range(5):
            httpx_mock.add_response(method="GET", status_code=500)
        with pytest.raises(DataUnavailableError, match="HTTP error"):
            await oecd_connector.fetch_output_gap("DE", date(2020, 1, 1), date(2024, 12, 31))

    @pytest.mark.asyncio
    async def test_null_observations_skipped(
        self, httpx_mock: HTTPXMock, oecd_connector: OECDEOConnector
    ) -> None:
        payload = _sdmx_json_payload("USA", [("2023", 0.167), ("2024", 0.537)])
        # Overwrite the obs map so one is null.
        payload["data"]["dataSets"][0]["series"]["0:0:0"][  # type: ignore[index]
            "observations"
        ] = {
            "0": [None],
            "1": [0.537],
        }
        httpx_mock.add_response(method="GET", json=payload)
        gaps = await oecd_connector.fetch_output_gap("US", date(2023, 1, 1), date(2024, 12, 31))
        assert len(gaps) == 1
        assert gaps[0].gap_pct == pytest.approx(0.537)

    @pytest.mark.asyncio
    async def test_cache_round_trip_short_circuits_http(
        self, httpx_mock: HTTPXMock, oecd_connector: OECDEOConnector
    ) -> None:
        httpx_mock.add_response(
            method="GET",
            json=_sdmx_json_payload("USA", [("2024", 0.537)]),
        )
        # First call populates cache.
        first = await oecd_connector.fetch_output_gap("US", date(2024, 1, 1), date(2024, 12, 31))
        # Second call served from cache — no HTTP mock required, would
        # 500 otherwise because pytest-httpx enforces all responses used.
        second = await oecd_connector.fetch_output_gap("US", date(2024, 1, 1), date(2024, 12, 31))
        assert first == second
        assert len(httpx_mock.get_requests()) == 1


# ---------------------------------------------------------------------------
# fetch_latest_output_gap behaviour
# ---------------------------------------------------------------------------


class TestFetchLatestOutputGap:
    @pytest.mark.asyncio
    async def test_returns_most_recent_at_or_before_anchor(
        self, httpx_mock: HTTPXMock, oecd_connector: OECDEOConnector
    ) -> None:
        httpx_mock.add_response(
            method="GET",
            json=_sdmx_json_payload(
                "CAN",
                [("2022", -0.316), ("2023", 0.167), ("2024", -0.043)],
            ),
        )
        latest = await oecd_connector.fetch_latest_output_gap("CA", date(2024, 6, 30))
        assert latest is not None
        # 2024 year-end > 2024-06-30, so the latest usable is 2023.
        assert latest.observation_date == date(2023, 12, 31)
        assert latest.gap_pct == pytest.approx(0.167)

    @pytest.mark.asyncio
    async def test_returns_none_when_no_records_found(
        self, httpx_mock: HTTPXMock, oecd_connector: OECDEOConnector
    ) -> None:
        httpx_mock.add_response(method="GET", text="NoRecordsFound")
        latest = await oecd_connector.fetch_latest_output_gap("DE", date(2024, 12, 31))
        assert latest is None

    @pytest.mark.asyncio
    async def test_returns_none_when_all_obs_after_anchor(
        self, httpx_mock: HTTPXMock, oecd_connector: OECDEOConnector
    ) -> None:
        # Anchor before first observation → no usable obs.
        httpx_mock.add_response(
            method="GET",
            json=_sdmx_json_payload("DEU", [("2024", -1.954)]),
        )
        latest = await oecd_connector.fetch_latest_output_gap("DE", date(2020, 1, 1))
        assert latest is None

    @pytest.mark.asyncio
    async def test_honours_observation_date_year_end_semantic(
        self, httpx_mock: HTTPXMock, oecd_connector: OECDEOConnector
    ) -> None:
        # When anchor = 2024-12-31, the year-end observation is usable.
        httpx_mock.add_response(
            method="GET",
            json=_sdmx_json_payload("DEU", [("2024", -1.954)]),
        )
        latest = await oecd_connector.fetch_latest_output_gap("DE", date(2024, 12, 31))
        assert latest is not None
        assert latest.observation_date == date(2024, 12, 31)
        assert latest.gap_pct == pytest.approx(-1.954)


# ---------------------------------------------------------------------------
# Live canary — gated by environment (run via @pytest.mark.slow)
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.asyncio
async def test_live_canary_oecd_eo_usa_recent(tmp_path: Path) -> None:
    """Live canary — USA GAP has a last-2y observation within sane bands."""
    conn = OECDEOConnector(cache_dir=str(tmp_path / "oecd_eo"))
    try:
        today = datetime.now(tz=UTC).date()
        gaps = await conn.fetch_output_gap("US", today - timedelta(days=5 * 366), today)
        assert len(gaps) >= 3
        # OECD USA GAP historical range well within [-10%, +10%] post-2000.
        for g in gaps:
            assert -10.0 < g.gap_pct < 10.0
    finally:
        await conn.aclose()


@pytest.mark.slow
@pytest.mark.asyncio
async def test_live_canary_oecd_eo_16_t1_countries_all_return_data(
    tmp_path: Path,
) -> None:
    """Smoke — every ISO2 in OECD_EO_COUNTRY_MAP returns ≥1 observation."""
    conn = OECDEOConnector(cache_dir=str(tmp_path / "oecd_eo"))
    try:
        today = datetime.now(tz=UTC).date()
        for iso2 in OECD_EO_COUNTRY_MAP:
            gaps = await conn.fetch_output_gap(iso2, today - timedelta(days=3 * 366), today)
            assert len(gaps) >= 1, f"{iso2} returned no OECD EO GAP data"
    finally:
        await conn.aclose()


def test_no_api_key_required_for_oecd_eo(tmp_path: Path) -> None:
    """OECD SDMX is public (no auth) — constructor takes no key."""
    # If this line constructs successfully without an API key, the
    # connector honours the "public endpoint" invariant.
    conn = OECDEOConnector(cache_dir=str(tmp_path / "oecd_eo"))
    assert conn.CONNECTOR_ID == "oecd_eo"
