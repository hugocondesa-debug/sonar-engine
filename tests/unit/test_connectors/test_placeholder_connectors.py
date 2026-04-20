"""Tests for placeholder connectors (MOVE / AAII / CFTC COT).

Per brief §9 "Connector degraded paths are acceptable": these three
connectors ship as documented placeholders that raise
DataUnavailableError so F3/F4 can emit the spec-defined *_UNAVAILABLE /
*_PROXY flags and redistribute weights. Live-fetch implementations are
scheduled as CAL-061 (MOVE), CAL-062 (AAII), CAL-063 (CFTC).
"""

from __future__ import annotations

from datetime import date

import pytest

from sonar.connectors.aaii import AAII_PUBLIC_URL, AaiiConnector, AaiiSurveyObservation
from sonar.connectors.cftc_cot import CFTC_JSON_API, CftcCotConnector, CotObservation
from sonar.connectors.move_index import MoveIndexConnector, MoveObservation
from sonar.overlays.exceptions import DataUnavailableError

# --- MOVE ---------------------------------------------------------------


async def test_move_fetch_latest_raises() -> None:
    conn = MoveIndexConnector()
    with pytest.raises(DataUnavailableError, match="CAL-061"):
        await conn.fetch_latest(date(2024, 1, 2))
    await conn.aclose()


def test_move_observation_dataclass() -> None:
    obs = MoveObservation(observation_date=date(2024, 1, 2), value_level=110.5)
    assert obs.source == "ICE"
    assert obs.source_series_id == "MOVE"


# --- AAII ---------------------------------------------------------------


async def test_aaii_fetch_latest_raises() -> None:
    conn = AaiiConnector()
    with pytest.raises(DataUnavailableError, match="CAL-062"):
        await conn.fetch_latest(date(2024, 1, 4))
    await conn.aclose()


def test_aaii_public_url_constant() -> None:
    assert AAII_PUBLIC_URL.startswith("https://www.aaii.com/")


def test_aaii_bull_minus_bear_property() -> None:
    obs = AaiiSurveyObservation(
        observation_date=date(2024, 1, 4),
        bull_pct=42.5,
        bear_pct=25.0,
        neutral_pct=32.5,
    )
    assert obs.bull_minus_bear_pct == 17.5


# --- CFTC COT -----------------------------------------------------------


async def test_cftc_cot_fetch_latest_raises() -> None:
    conn = CftcCotConnector()
    with pytest.raises(DataUnavailableError, match="CAL-063"):
        await conn.fetch_latest_sp500(date(2024, 1, 2))
    await conn.aclose()


def test_cftc_api_url_constant() -> None:
    assert CFTC_JSON_API.startswith("https://publicreporting.cftc.gov/")


def test_cot_noncomm_net_property() -> None:
    obs = CotObservation(
        observation_date=date(2024, 1, 2),
        release_date=date(2024, 1, 5),
        contract="SP500",
        noncomm_long=200_000,
        noncomm_short=115_000,
    )
    assert obs.noncomm_net == 85_000
