"""Unit tests for Danmarks Nationalbanken Statbank L0 connector (Sprint Y-DK).

The Statbank.dk public API hosts Nationalbanken's monetary statistics
tables (DN-prefixed) — reachable + scriptable (empirical probe
2026-04-22 — see module docstring). The connector ships with a real
fetch implementation, not a gated scaffold; tests exercise:

- Instrument-code catalogue stability (regression guard).
- Statbank time-token parser (``YYYYMxxDxx``).
- Happy-path BULK CSV parse (semicolon-delimited; INSTRUMENT;LAND;
  OPGOER;TID;INDHOLD).
- Negative-value preservation across the parse layer (core Sprint
  Y-DK contract — the 2015-2022 EUR-peg-defence corridor must flow
  through unchanged to the downstream cascade).
- Window filtering (``[start, end]`` clamping).
- ``..`` / empty-cell rows skipped.
- Empty payload → ``DataUnavailableError``.
- HTTP error → ``DataUnavailableError``.
- Disk cache round-trip (set / get short-circuits the HTTP call).
- All four convenience wrappers (``fetch_policy_rate`` /
  ``fetch_discount_rate`` / ``fetch_lending_rate`` /
  ``fetch_current_account_rate``).
- @slow live canary probes OIBNAA and bands the recent values.
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

import httpx
import pytest
from tenacity import wait_none

from sonar.connectors.base import Observation
from sonar.connectors.nationalbanken import (
    NATIONALBANKEN_CD_RATE,
    NATIONALBANKEN_CURRENT_ACCOUNT_RATE,
    NATIONALBANKEN_DISCOUNT_RATE,
    NATIONALBANKEN_LENDING_RATE,
    NATIONALBANKEN_RATES_TABLE,
    STATBANK_BASE_URL,
    NationalbankenConnector,
    _parse_statbank_date,
)
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_httpx import HTTPXMock


def _bulk_csv(rows: list[tuple[str, str]], instrument_label: str = "Test") -> str:
    """Build a semicolon-delimited Statbank BULK payload from ``(date_token, value_str)``."""
    header = "INSTRUMENT;LAND;OPGOER;TID;INDHOLD"
    body = "\n".join(
        f"{instrument_label};DK: Denmark;Daily interest rates (per cent);{d};{v}" for d, v in rows
    )
    return f"{header}\n{body}\n"


def test_instrument_codes_canonical() -> None:
    """Regression guard — Statbank instrument codes must stay stable."""
    assert NATIONALBANKEN_CD_RATE == "OIBNAA"
    assert NATIONALBANKEN_DISCOUNT_RATE == "ODKNAA"
    assert NATIONALBANKEN_LENDING_RATE == "OIRNAA"
    assert NATIONALBANKEN_CURRENT_ACCOUNT_RATE == "OFONAA"


def test_table_id_canonical() -> None:
    assert NATIONALBANKEN_RATES_TABLE == "DNRENTD"


def test_base_url_canonical() -> None:
    assert STATBANK_BASE_URL == "https://api.statbank.dk/v1"


class TestStatbankDateParser:
    def test_parses_canonical_token(self) -> None:
        assert _parse_statbank_date("2015M04D07") == date(2015, 4, 7)
        assert _parse_statbank_date("2026M04D21") == date(2026, 4, 21)

    def test_rejects_short_token(self) -> None:
        with pytest.raises(ValueError, match="YYYYMxxDxx"):
            _parse_statbank_date("2024M01")

    def test_rejects_wrong_separators(self) -> None:
        with pytest.raises(ValueError, match="YYYYMxxDxx"):
            _parse_statbank_date("2024-01-15")

    def test_rejects_garbage(self) -> None:
        with pytest.raises(ValueError, match=r"time data|YYYYMxxDxx"):
            _parse_statbank_date("XXXXMYYDZZ")


class TestNationalbankenConnectorLifecycle:
    @pytest.mark.asyncio
    async def test_instantiation_and_aclose(self, tmp_path: Path) -> None:
        conn = NationalbankenConnector(cache_dir=str(tmp_path / "nationalbanken"))
        assert conn.CONNECTOR_ID == "nationalbanken"
        assert conn.CACHE_NAMESPACE == "nationalbanken_statbank"
        await conn.aclose()


@pytest.fixture
async def nationalbanken_connector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> NationalbankenConnector:
    monkeypatch.setattr(NationalbankenConnector._fetch_raw.retry, "wait", wait_none())
    return NationalbankenConnector(cache_dir=str(tmp_path / "nationalbanken"))


class TestNationalbankenConnectorFetchSeries:
    @pytest.mark.asyncio
    async def test_happy_path_parses_bulk_csv(
        self, httpx_mock: HTTPXMock, nationalbanken_connector: NationalbankenConnector
    ) -> None:
        httpx_mock.add_response(
            method="POST",
            text=_bulk_csv(
                [
                    ("2024M01D02", "3.5000"),
                    ("2024M01D03", "3.5000"),
                    ("2024M06D27", "3.2500"),
                ],
                instrument_label="CD rate (Sprint Y-DK probe label)",
            ),
        )
        try:
            obs = await nationalbanken_connector.fetch_series(
                NATIONALBANKEN_CD_RATE, date(2024, 1, 1), date(2024, 7, 1)
            )
            assert len(obs) == 3
            assert all(isinstance(o, Observation) for o in obs)
            # yield_bps = round(pct * 100). 3.50 % → 350 bps.
            assert obs[0].yield_bps == 350
            assert obs[0].country_code == "DK"
            assert obs[0].source == "NATIONALBANKEN"
            assert obs[0].source_series_id == NATIONALBANKEN_CD_RATE
            assert obs[0].observation_date == date(2024, 1, 2)
            assert obs[-1].yield_bps == 325  # 3.25 %
        finally:
            await nationalbanken_connector.aclose()

    @pytest.mark.asyncio
    async def test_negative_values_preserved(
        self, httpx_mock: HTTPXMock, nationalbanken_connector: NationalbankenConnector
    ) -> None:
        """Negative-rate era 2015-2022: signs flow through unchanged.

        This is the core Sprint Y-DK contract — the 2015-04-07 →
        2022-09-15 Nationalbanken EUR-peg-defence corridor must NOT
        be clamped at zero, flipped in sign, or silently dropped at
        the parse layer. Downstream cascade
        ``_dk_policy_rate_cascade`` emits
        ``DK_NEGATIVE_RATE_ERA_DATA`` when any post-parse observation
        in the resolved window is strictly negative.
        """
        httpx_mock.add_response(
            method="POST",
            text=_bulk_csv(
                [
                    ("2015M04D07", "-0.7500"),
                    ("2017M06D15", "-0.6500"),
                    ("2019M01D09", "-0.6500"),
                    ("2021M03D31", "-0.5000"),
                ],
            ),
        )
        try:
            obs = await nationalbanken_connector.fetch_series(
                NATIONALBANKEN_CD_RATE, date(2015, 1, 1), date(2022, 12, 31)
            )
            assert len(obs) == 4
            assert [o.yield_bps for o in obs] == [-75, -65, -65, -50]
            assert all(o.yield_bps < 0 for o in obs)
            assert all(o.country_code == "DK" for o in obs)
        finally:
            await nationalbanken_connector.aclose()

    @pytest.mark.asyncio
    async def test_window_filter_clamps_to_range(
        self, httpx_mock: HTTPXMock, nationalbanken_connector: NationalbankenConnector
    ) -> None:
        """BULK returns the full history; parser clamps to ``[start, end]``."""
        httpx_mock.add_response(
            method="POST",
            text=_bulk_csv(
                [
                    ("1992M01D02", "9.5000"),  # before window
                    ("2024M06D15", "3.5000"),  # in window
                    ("2024M06D20", "3.5000"),  # in window
                    ("2026M04D21", "1.6000"),  # after window
                ],
            ),
        )
        try:
            obs = await nationalbanken_connector.fetch_series(
                NATIONALBANKEN_CD_RATE, date(2024, 1, 1), date(2024, 12, 31)
            )
            assert len(obs) == 2
            assert obs[0].observation_date == date(2024, 6, 15)
            assert obs[1].observation_date == date(2024, 6, 20)
        finally:
            await nationalbanken_connector.aclose()

    @pytest.mark.asyncio
    async def test_double_dot_rows_skipped(
        self, httpx_mock: HTTPXMock, nationalbanken_connector: NationalbankenConnector
    ) -> None:
        """Statbank emits ``..`` for missing observations — drop without raising."""
        httpx_mock.add_response(
            method="POST",
            text=_bulk_csv(
                [
                    ("2024M12D24", ".."),
                    ("2024M12D25", ".."),
                    ("2024M12D26", "3.5000"),
                ],
            ),
        )
        try:
            obs = await nationalbanken_connector.fetch_series(
                NATIONALBANKEN_CD_RATE, date(2024, 12, 1), date(2024, 12, 31)
            )
            assert len(obs) == 1
            assert obs[0].observation_date == date(2024, 12, 26)
        finally:
            await nationalbanken_connector.aclose()

    @pytest.mark.asyncio
    async def test_malformed_date_token_skipped(
        self, httpx_mock: HTTPXMock, nationalbanken_connector: NationalbankenConnector
    ) -> None:
        """Token parser failure on a row → skip; later good rows preserved."""
        httpx_mock.add_response(
            method="POST",
            text=_bulk_csv(
                [
                    ("BADTOKEN", "3.5000"),
                    ("2024M06D15", "3.5000"),
                ],
            ),
        )
        try:
            obs = await nationalbanken_connector.fetch_series(
                NATIONALBANKEN_CD_RATE, date(2024, 1, 1), date(2024, 12, 31)
            )
            assert len(obs) == 1
            assert obs[0].observation_date == date(2024, 6, 15)
        finally:
            await nationalbanken_connector.aclose()

    @pytest.mark.asyncio
    async def test_empty_payload_raises_unavailable(
        self, httpx_mock: HTTPXMock, nationalbanken_connector: NationalbankenConnector
    ) -> None:
        httpx_mock.add_response(method="POST", text="")
        try:
            with pytest.raises(DataUnavailableError, match="empty payload"):
                await nationalbanken_connector.fetch_series(
                    NATIONALBANKEN_CD_RATE, date(2024, 12, 1), date(2024, 12, 31)
                )
        finally:
            await nationalbanken_connector.aclose()

    @pytest.mark.asyncio
    async def test_all_rows_unparseable_raises(
        self, httpx_mock: HTTPXMock, nationalbanken_connector: NationalbankenConnector
    ) -> None:
        """Header-only / all-skipped → DataUnavailableError."""
        httpx_mock.add_response(
            method="POST",
            text=_bulk_csv(
                [
                    ("2024M12D24", ".."),
                    ("2024M12D25", ".."),
                ],
            ),
        )
        try:
            with pytest.raises(DataUnavailableError, match="no parseable rows"):
                await nationalbanken_connector.fetch_series(
                    NATIONALBANKEN_CD_RATE, date(2024, 12, 1), date(2024, 12, 31)
                )
        finally:
            await nationalbanken_connector.aclose()

    @pytest.mark.asyncio
    async def test_http_error_raises_unavailable(
        self, httpx_mock: HTTPXMock, nationalbanken_connector: NationalbankenConnector
    ) -> None:
        """500s exhaust tenacity's 5 retries → surface as ``DataUnavailableError``."""
        httpx_mock.add_response(
            method="POST",
            status_code=500,
            text="Internal Server Error",
            is_reusable=True,
        )
        try:
            with pytest.raises(DataUnavailableError, match="HTTP error"):
                await nationalbanken_connector.fetch_series(
                    NATIONALBANKEN_CD_RATE, date(2024, 12, 1), date(2024, 12, 31)
                )
        finally:
            await nationalbanken_connector.aclose()

    @pytest.mark.asyncio
    async def test_cache_round_trip_skips_second_http_call(
        self, httpx_mock: HTTPXMock, nationalbanken_connector: NationalbankenConnector
    ) -> None:
        """Second call on same ``(instrument, start, end)`` hits cache, not HTTP."""
        httpx_mock.add_response(
            method="POST",
            text=_bulk_csv([("2024M12D11", "3.5000")]),
        )
        try:
            first = await nationalbanken_connector.fetch_series(
                NATIONALBANKEN_CD_RATE, date(2024, 12, 1), date(2024, 12, 31)
            )
            second = await nationalbanken_connector.fetch_series(
                NATIONALBANKEN_CD_RATE, date(2024, 12, 1), date(2024, 12, 31)
            )
            assert len(first) == 1
            assert first == second
            # Only one mocked HTTP call registered — second was cache.
            assert len(httpx_mock.get_requests()) == 1
        finally:
            await nationalbanken_connector.aclose()


class TestNationalbankenConnectorWrappers:
    @pytest.mark.asyncio
    async def test_fetch_policy_rate_uses_cd_rate(
        self, httpx_mock: HTTPXMock, nationalbanken_connector: NationalbankenConnector
    ) -> None:
        """``fetch_policy_rate`` routes to OIBNAA (CD rate, EUR-peg defence)."""
        httpx_mock.add_response(
            method="POST",
            text=_bulk_csv([("2024M01D02", "3.5000")]),
        )
        try:
            obs = await nationalbanken_connector.fetch_policy_rate(
                date(2024, 1, 1), date(2024, 1, 31)
            )
            assert obs[0].source_series_id == NATIONALBANKEN_CD_RATE
            assert obs[0].yield_bps == 350
        finally:
            await nationalbanken_connector.aclose()

    @pytest.mark.asyncio
    async def test_fetch_discount_rate_uses_canonical_series(
        self, httpx_mock: HTTPXMock, nationalbanken_connector: NationalbankenConnector
    ) -> None:
        """``fetch_discount_rate`` routes to ODKNAA (legacy diskontoen)."""
        httpx_mock.add_response(
            method="POST",
            text=_bulk_csv([("2024M01D02", "3.6000")]),
        )
        try:
            obs = await nationalbanken_connector.fetch_discount_rate(
                date(2024, 1, 1), date(2024, 1, 31)
            )
            assert obs[0].source_series_id == NATIONALBANKEN_DISCOUNT_RATE
            assert obs[0].yield_bps == 360
        finally:
            await nationalbanken_connector.aclose()

    @pytest.mark.asyncio
    async def test_fetch_lending_rate_uses_canonical_series(
        self, httpx_mock: HTTPXMock, nationalbanken_connector: NationalbankenConnector
    ) -> None:
        """``fetch_lending_rate`` routes to OIRNAA (corridor ceiling)."""
        httpx_mock.add_response(
            method="POST",
            text=_bulk_csv([("2024M01D02", "4.0000")]),
        )
        try:
            obs = await nationalbanken_connector.fetch_lending_rate(
                date(2024, 1, 1), date(2024, 1, 31)
            )
            assert obs[0].source_series_id == NATIONALBANKEN_LENDING_RATE
            assert obs[0].yield_bps == 400
        finally:
            await nationalbanken_connector.aclose()

    @pytest.mark.asyncio
    async def test_fetch_current_account_rate_uses_canonical_series(
        self, httpx_mock: HTTPXMock, nationalbanken_connector: NationalbankenConnector
    ) -> None:
        """``fetch_current_account_rate`` routes to OFONAA (corridor floor)."""
        httpx_mock.add_response(
            method="POST",
            text=_bulk_csv([("2024M01D02", "0.0000")]),
        )
        try:
            obs = await nationalbanken_connector.fetch_current_account_rate(
                date(2024, 1, 1), date(2024, 1, 31)
            )
            assert obs[0].source_series_id == NATIONALBANKEN_CURRENT_ACCOUNT_RATE
            assert obs[0].yield_bps == 0
        finally:
            await nationalbanken_connector.aclose()


@pytest.mark.slow
async def test_live_canary_nationalbanken_cd_rate(tmp_path: Path) -> None:
    """Live Statbank probe — OIBNAA (Nationalbanken CD rate) last 60 days.

    Does not require any API key — Statbank.dk is public. Skips only
    if the network is unreachable. Asserts the recent band roughly
    matches the Nationalbanken normalisation post-2022 lift-off
    (CD rate stayed within [-1.00, 5.00] %; current ~1.60 % at probe).
    """
    conn = NationalbankenConnector(cache_dir=str(tmp_path / "nationalbanken"))
    try:
        today = datetime.now(tz=UTC).date()
        start = today - timedelta(days=60)
        try:
            obs = await conn.fetch_policy_rate(start, today)
        except (httpx.HTTPError, DataUnavailableError) as exc:
            pytest.skip(f"Nationalbanken Statbank unreachable: {exc}")
        assert len(obs) >= 5
        assert obs[0].country_code == "DK"
        assert obs[0].source_series_id == NATIONALBANKEN_CD_RATE
        for o in obs:
            # yield_bps in [-100, 600] — band guards against unit
            # regression while leaving slack for the negative-rate
            # floor of the historical -0.75 % corridor (pre-2022).
            assert -100 <= o.yield_bps <= 600
    finally:
        await conn.aclose()


@pytest.mark.slow
async def test_live_canary_nationalbanken_cd_rate_negative_era(tmp_path: Path) -> None:
    """Live Statbank probe of the 2015-2022 EUR-peg-defence corridor.

    Validates end-to-end negative-value preservation through the
    BULK CSV parse + yield_bps conversion layers — the unique Sprint
    Y-DK contract since the CD rate is what actually went deeply
    negative (TE primary returns the discount rate which only briefly
    dipped negative). 2017 sits in the deep -0.65 % corridor.
    """
    conn = NationalbankenConnector(cache_dir=str(tmp_path / "nationalbanken"))
    try:
        try:
            obs = await conn.fetch_policy_rate(date(2017, 1, 1), date(2017, 6, 30))
        except (httpx.HTTPError, DataUnavailableError) as exc:
            pytest.skip(f"Nationalbanken Statbank unreachable: {exc}")
        assert len(obs) >= 50
        neg = [o for o in obs if o.yield_bps < 0]
        # 2017 was fully inside the -0.65 % CD-rate corridor — every
        # observation should be strictly-negative.
        assert len(neg) == len(obs)
        for o in obs:
            assert -80 <= o.yield_bps <= -50  # CD rate band 2017 H1
    finally:
        await conn.aclose()


# Statbank is keyless — guard the env-hook regression.
def test_no_env_key_required_for_nationalbanken() -> None:
    """Statbank.dk is keyless — ``STATBANK_API_KEY`` / similar must not exist."""
    assert "STATBANK_API_KEY" not in os.environ
    assert "NATIONALBANKEN_API_KEY" not in os.environ
