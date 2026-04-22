"""Unit tests for Norges Bank DataAPI L0 connector (Sprint X-NO).

The Norges Bank DataAPI SDMX-JSON endpoint is reachable + scriptable
(empirical probe 2026-04-22 — see ``norgesbank.py`` module docstring).
The connector ships with a real fetch implementation, not a gated
scaffold; tests exercise:

- Dataflow + series-key catalogue stability (regression guard).
- Happy-path parse of SDMX-JSON ``(TIME_PERIOD, series["0:0:0:0"],
  observations[idx])`` tensor.
- Empty dataSets / missing structure → ``DataUnavailableError``.
- HTTP error → ``DataUnavailableError``.
- Disk cache round-trip (set / get short-circuits the HTTP call).
- Series-id format validation (must be ``"{flow}/{key}"``).
- Both ``fetch_policy_rate`` + ``fetch_gbon_10y`` convenience wrappers.
- Full-range cassette (1586 real daily observations 2020-2026).
- @slow live canaries against the public DataAPI.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest
from tenacity import wait_none

from sonar.connectors.base import Observation
from sonar.connectors.norgesbank import (
    NORGESBANK_BASE_URL,
    NORGESBANK_GBON_10Y_FLOW,
    NORGESBANK_GBON_10Y_KEY,
    NORGESBANK_POLICY_RATE_FLOW,
    NORGESBANK_POLICY_RATE_KEY,
    NorgesBankConnector,
)
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from pytest_httpx import HTTPXMock


CASSETTE_DIR = Path(__file__).parent.parent.parent / "cassettes" / "connectors"


def _load_cassette(name: str) -> dict:
    return json.loads((CASSETTE_DIR / name).read_text())


def test_dataflow_catalogue_canonical() -> None:
    """Regression guard — Norges Bank DataAPI dataflow + key must stay stable."""
    assert NORGESBANK_POLICY_RATE_FLOW == "IR"
    assert NORGESBANK_POLICY_RATE_KEY == "B.KPRA.SD.R"
    assert NORGESBANK_GBON_10Y_FLOW == "GOVT_GENERIC_RATES"
    assert NORGESBANK_GBON_10Y_KEY == "B.10Y.GBON"


def test_base_url_canonical() -> None:
    assert NORGESBANK_BASE_URL == "https://data.norges-bank.no/api/data"


class TestNorgesBankConnectorLifecycle:
    @pytest.mark.asyncio
    async def test_instantiation_and_aclose(self, tmp_path: Path) -> None:
        conn = NorgesBankConnector(cache_dir=str(tmp_path / "norgesbank"))
        assert conn.CONNECTOR_ID == "norgesbank"
        assert conn.CACHE_NAMESPACE == "norgesbank_dataapi"
        await conn.aclose()


@pytest.fixture
async def norgesbank_connector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> NorgesBankConnector:
    monkeypatch.setattr(NorgesBankConnector._fetch_raw.retry, "wait", wait_none())
    return NorgesBankConnector(cache_dir=str(tmp_path / "norgesbank"))


def _sdmx_json_payload(
    dates: list[str],
    values: list[str],
    *,
    flow: str = "IR",
) -> dict:
    """Build a minimal SDMX-JSON payload matching Norges Bank's shape.

    Mirrors the live response we probed 2026-04-22 — a single series
    (pinned to all dimensions) with observations dict keyed by string
    index-of-date-in-axis.
    """
    assert len(dates) == len(values), "dates and values must align"
    observations = {str(idx): [v] for idx, v in enumerate(values)}
    obs_values = [{"id": d, "start": f"{d}T00:00:00", "end": f"{d}T23:59:59"} for d in dates]
    return {
        "meta": {"id": "IREF1", "prepared": "2026-04-22T00:00:00", "test": False},
        "data": {
            "dataSets": [
                {
                    "links": [{"rel": "dataflow", "urn": f"urn:sdmx:...:{flow}(1.0)"}],
                    "action": "Information",
                    "series": {
                        "0:0:0:0": {
                            "attributes": [0, 0],
                            "observations": observations,
                        }
                    },
                    "attributes": [0],
                }
            ],
            "structure": {
                "dimensions": {
                    "dataset": [],
                    "series": [
                        {"id": "FREQ", "keyPosition": 0, "values": [{"id": "B"}]},
                        {"id": "INSTRUMENT_TYPE", "keyPosition": 1, "values": [{"id": "KPRA"}]},
                        {"id": "TENOR", "keyPosition": 2, "values": [{"id": "SD"}]},
                        {"id": "UNIT_MEASURE", "keyPosition": 3, "values": [{"id": "R"}]},
                    ],
                    "observation": [
                        {
                            "id": "TIME_PERIOD",
                            "role": "time",
                            "values": obs_values,
                        }
                    ],
                },
            },
        },
    }


class TestNorgesBankConnectorFetchSeries:
    @pytest.mark.asyncio
    async def test_happy_path_parses_sdmx_json(
        self, httpx_mock: HTTPXMock, norgesbank_connector: NorgesBankConnector
    ) -> None:
        httpx_mock.add_response(
            method="GET",
            json=_sdmx_json_payload(
                dates=["2024-12-19", "2024-12-20", "2025-01-23"],
                values=["4.5", "4.5", "4.5"],
            ),
        )
        try:
            obs = await norgesbank_connector.fetch_series(
                "IR/B.KPRA.SD.R", date(2024, 12, 1), date(2025, 2, 1)
            )
            assert len(obs) == 3
            assert all(isinstance(o, Observation) for o in obs)
            # yield_bps = round(pct * 100). 4.5 % → 450 bps.
            assert obs[0].yield_bps == 450
            assert obs[0].country_code == "NO"
            assert obs[0].source == "NORGESBANK"
            assert obs[0].source_series_id == "IR/B.KPRA.SD.R"
            assert obs[0].observation_date == date(2024, 12, 19)
        finally:
            await norgesbank_connector.aclose()

    @pytest.mark.asyncio
    async def test_series_id_without_slash_raises(
        self, norgesbank_connector: NorgesBankConnector
    ) -> None:
        """``series_id`` must be ``'<FLOW>/<KEY>'`` — reject bare keys."""
        try:
            with pytest.raises(DataUnavailableError, match="must be"):
                await norgesbank_connector.fetch_series(
                    "B.KPRA.SD.R", date(2024, 1, 1), date(2024, 12, 31)
                )
        finally:
            await norgesbank_connector.aclose()

    @pytest.mark.asyncio
    async def test_empty_datasets_raises_unavailable(
        self, httpx_mock: HTTPXMock, norgesbank_connector: NorgesBankConnector
    ) -> None:
        httpx_mock.add_response(
            method="GET",
            json={"meta": {}, "data": {"dataSets": [], "structure": {}}},
        )
        try:
            with pytest.raises(DataUnavailableError, match="empty dataSets"):
                await norgesbank_connector.fetch_series(
                    "IR/B.KPRA.SD.R", date(2024, 1, 1), date(2024, 12, 31)
                )
        finally:
            await norgesbank_connector.aclose()

    @pytest.mark.asyncio
    async def test_empty_series_map_raises(
        self, httpx_mock: HTTPXMock, norgesbank_connector: NorgesBankConnector
    ) -> None:
        """Structure present but dataSets[0].series empty → soft-fail."""
        httpx_mock.add_response(
            method="GET",
            json={
                "meta": {},
                "data": {
                    "dataSets": [{"series": {}, "attributes": []}],
                    "structure": {
                        "dimensions": {
                            "series": [],
                            "observation": [
                                {"id": "TIME_PERIOD", "values": [{"id": "2024-12-19"}]}
                            ],
                        }
                    },
                },
            },
        )
        try:
            with pytest.raises(DataUnavailableError, match="empty series map"):
                await norgesbank_connector.fetch_series(
                    "IR/B.KPRA.SD.R", date(2024, 1, 1), date(2024, 12, 31)
                )
        finally:
            await norgesbank_connector.aclose()

    @pytest.mark.asyncio
    async def test_http_error_raises_unavailable(
        self, httpx_mock: HTTPXMock, norgesbank_connector: NorgesBankConnector
    ) -> None:
        """500s exhaust tenacity's 5 retries → surface as ``DataUnavailableError``."""
        httpx_mock.add_response(
            method="GET",
            status_code=500,
            text="Internal Server Error",
            is_reusable=True,
        )
        try:
            with pytest.raises(DataUnavailableError, match="HTTP error"):
                await norgesbank_connector.fetch_series(
                    "IR/B.KPRA.SD.R", date(2024, 1, 1), date(2024, 12, 31)
                )
        finally:
            await norgesbank_connector.aclose()

    @pytest.mark.asyncio
    async def test_null_value_cells_are_skipped(
        self, httpx_mock: HTTPXMock, norgesbank_connector: NorgesBankConnector
    ) -> None:
        """Null / empty cells drop quietly rather than crashing the parser."""
        payload = _sdmx_json_payload(
            dates=["2024-12-19", "2024-12-20", "2024-12-23"],
            values=["4.5", "4.5", "4.5"],
        )
        # Replace one observation value with None and one with empty string.
        observations = payload["data"]["dataSets"][0]["series"]["0:0:0:0"]["observations"]
        observations["0"] = [None]
        observations["1"] = [""]
        httpx_mock.add_response(method="GET", json=payload)
        try:
            obs = await norgesbank_connector.fetch_series(
                "IR/B.KPRA.SD.R", date(2024, 12, 1), date(2024, 12, 31)
            )
            assert len(obs) == 1
            assert obs[0].observation_date == date(2024, 12, 23)
        finally:
            await norgesbank_connector.aclose()

    @pytest.mark.asyncio
    async def test_all_rows_unparseable_raises(
        self, httpx_mock: HTTPXMock, norgesbank_connector: NorgesBankConnector
    ) -> None:
        payload = _sdmx_json_payload(dates=["2024-12-19", "2024-12-20"], values=["4.5", "4.5"])
        # Replace every value with null.
        observations = payload["data"]["dataSets"][0]["series"]["0:0:0:0"]["observations"]
        for idx in observations:
            observations[idx] = [None]
        httpx_mock.add_response(method="GET", json=payload)
        try:
            with pytest.raises(DataUnavailableError, match="no parseable rows"):
                await norgesbank_connector.fetch_series(
                    "IR/B.KPRA.SD.R", date(2024, 1, 1), date(2024, 12, 31)
                )
        finally:
            await norgesbank_connector.aclose()

    @pytest.mark.asyncio
    async def test_out_of_window_rows_filtered(
        self, httpx_mock: HTTPXMock, norgesbank_connector: NorgesBankConnector
    ) -> None:
        """Rows outside [start, end] are excluded even if the API returned them."""
        httpx_mock.add_response(
            method="GET",
            json=_sdmx_json_payload(
                dates=["2020-01-02", "2024-12-19", "2026-04-01"],
                values=["1.5", "4.5", "4.0"],
            ),
        )
        try:
            obs = await norgesbank_connector.fetch_series(
                "IR/B.KPRA.SD.R", date(2024, 1, 1), date(2025, 12, 31)
            )
            assert len(obs) == 1
            assert obs[0].observation_date == date(2024, 12, 19)
        finally:
            await norgesbank_connector.aclose()

    @pytest.mark.asyncio
    async def test_cache_round_trip_skips_second_http_call(
        self, httpx_mock: HTTPXMock, norgesbank_connector: NorgesBankConnector
    ) -> None:
        """Second call on the same ``(series, start, end)`` hits the cache, not HTTP."""
        httpx_mock.add_response(
            method="GET",
            json=_sdmx_json_payload(dates=["2024-12-19"], values=["4.5"]),
        )
        try:
            first = await norgesbank_connector.fetch_series(
                "IR/B.KPRA.SD.R", date(2024, 12, 1), date(2024, 12, 31)
            )
            second = await norgesbank_connector.fetch_series(
                "IR/B.KPRA.SD.R", date(2024, 12, 1), date(2024, 12, 31)
            )
            assert len(first) == 1
            assert first == second
            assert len(httpx_mock.get_requests()) == 1
        finally:
            await norgesbank_connector.aclose()

    @pytest.mark.asyncio
    async def test_full_history_cassette_parse(
        self, httpx_mock: HTTPXMock, norgesbank_connector: NorgesBankConnector
    ) -> None:
        """Full 2020-2026 daily cassette parses 1500+ rows, zero negatives."""
        payload = _load_cassette("norgesbank_policy_rate_2020_2026.json")
        httpx_mock.add_response(method="GET", json=payload)
        try:
            obs = await norgesbank_connector.fetch_series(
                "IR/B.KPRA.SD.R", date(2020, 1, 1), date(2026, 4, 30)
            )
            assert len(obs) >= 1500
            assert obs[0].country_code == "NO"
            assert obs[0].source == "NORGESBANK"
            # Positive-only invariant — Norway never ran a negative policy rate.
            assert all(o.yield_bps >= 0 for o in obs)
            # Minimum is 0 bps (0 %) during the 2020-05-08 → 2021-09-24
            # COVID-response trough; maximum is ~475 bps (4.75 %).
            assert min(o.yield_bps for o in obs) == 0
            assert max(o.yield_bps for o in obs) <= 600
            # Chronological ordering invariant.
            dates_out = [o.observation_date for o in obs]
            assert dates_out == sorted(dates_out)
        finally:
            await norgesbank_connector.aclose()


class TestNorgesBankConnectorWrappers:
    @pytest.mark.asyncio
    async def test_fetch_policy_rate_uses_ir_dataflow(
        self, httpx_mock: HTTPXMock, norgesbank_connector: NorgesBankConnector
    ) -> None:
        """``fetch_policy_rate`` routes to IR/B.KPRA.SD.R (sight-deposit rate)."""
        httpx_mock.add_response(
            method="GET",
            json=_sdmx_json_payload(dates=["2024-12-19"], values=["4.5"]),
        )
        try:
            obs = await norgesbank_connector.fetch_policy_rate(
                date(2024, 12, 1), date(2024, 12, 31)
            )
            assert obs[0].source_series_id == "IR/B.KPRA.SD.R"
            assert obs[0].yield_bps == 450
            assert obs[0].tenor_years == 0.01
        finally:
            await norgesbank_connector.aclose()

    @pytest.mark.asyncio
    async def test_fetch_gbon_10y_stamps_10y_tenor(
        self, httpx_mock: HTTPXMock, norgesbank_connector: NorgesBankConnector
    ) -> None:
        """``fetch_gbon_10y`` routes to GOVT_GENERIC_RATES/B.10Y.GBON and tenor=10.0."""
        httpx_mock.add_response(
            method="GET",
            json=_sdmx_json_payload(
                dates=["2024-12-19"], values=["3.85"], flow="GOVT_GENERIC_RATES"
            ),
        )
        try:
            obs = await norgesbank_connector.fetch_gbon_10y(date(2024, 12, 1), date(2024, 12, 31))
            assert obs[0].source_series_id == "GOVT_GENERIC_RATES/B.10Y.GBON"
            assert obs[0].yield_bps == 385
            # Tenor override applied — not the 0.01 short-rate default.
            assert obs[0].tenor_years == 10.0
        finally:
            await norgesbank_connector.aclose()


@pytest.mark.slow
async def test_live_canary_norgesbank_policy_rate(tmp_path: Path) -> None:
    """Live DataAPI probe — key policy rate within the last 60 days.

    No API key — Norges Bank DataAPI is public. Skips only if the
    network is unreachable. Asserts the recent band roughly matches
    2023-26 policy corridor (2.5-4.75 %).
    """
    conn = NorgesBankConnector(cache_dir=str(tmp_path / "norgesbank"))
    try:
        today = datetime.now(tz=UTC).date()
        start = today - timedelta(days=60)
        try:
            obs = await conn.fetch_policy_rate(start, today)
        except (httpx.HTTPError, DataUnavailableError) as exc:
            pytest.skip(f"Norges Bank DataAPI unreachable: {exc}")
        assert len(obs) >= 20  # ≥20 business days in a 60-day window
        assert obs[0].country_code == "NO"
        assert obs[0].source_series_id == "IR/B.KPRA.SD.R"
        for o in obs:
            # yield_bps in [200, 500] — guards against unit regression
            # (Norges Bank hasn't touched that band post-2023).
            assert 200 <= o.yield_bps <= 500
    finally:
        await conn.aclose()


@pytest.mark.slow
async def test_live_canary_norgesbank_gbon_10y(tmp_path: Path) -> None:
    """Live DataAPI probe — 10Y generic gov-bond yield last 60 days."""
    conn = NorgesBankConnector(cache_dir=str(tmp_path / "norgesbank"))
    try:
        today = datetime.now(tz=UTC).date()
        start = today - timedelta(days=60)
        try:
            obs = await conn.fetch_gbon_10y(start, today)
        except (httpx.HTTPError, DataUnavailableError) as exc:
            pytest.skip(f"Norges Bank DataAPI unreachable: {exc}")
        assert len(obs) >= 20
        assert obs[0].tenor_years == 10.0
        # NO 10Y gov-bond stayed within [150, 600] bps across the last decade.
        for o in obs:
            assert 150 <= o.yield_bps <= 600
    finally:
        await conn.aclose()
