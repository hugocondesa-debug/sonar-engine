"""Unit tests for the ECS stagflation-input resolver (sprint7-A c4)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sonar.db.session  # noqa: F401
from sonar.connectors.fred import FredEconomicObservation
from sonar.cycles.stagflation_inputs import (
    FRED_CPI_OECD_TEMPLATE,
    FRED_CPI_US,
    FRED_UNRATE_US,
    SUPPORTED_EA_COUNTRIES,
    resolve_stagflation_inputs,
)
from sonar.db.models import Base, E3Labor
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.orm import Session


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _monthly_dates(start: date, n: int) -> list[date]:
    """Return n consecutive month-1 dates starting at ``start``."""
    out: list[date] = []
    y, m = start.year, start.month
    for _ in range(n):
        out.append(date(y, m, 1))
        m += 1
        if m == 13:
            m = 1
            y += 1
    return out


def _cpi_history_us(latest_pct: float, prior_pct: float) -> list[FredEconomicObservation]:
    """14 monthly CPIAUCSL points so obs[-13] == prior_pct and obs[-1] == latest_pct.

    Uses a 14-element list with index 1 == prior and index 13 == latest so
    that ``obs[-1]`` and ``obs[-13]`` resolve exactly. Intermediate values
    don't matter for the YoY calculation.
    """
    dates = _monthly_dates(date(2024, 1, 1), 14)
    values: list[float] = [prior_pct] * 14
    values[13] = latest_pct  # obs[-1]
    values[1] = prior_pct  # obs[-13]
    return [
        FredEconomicObservation(
            observation_date=d,
            value=v,
            series_id=FRED_CPI_US,
        )
        for d, v in zip(dates, values, strict=True)
    ]


def _unrate_history(latest: float, prior: float) -> list[FredEconomicObservation]:
    dates = _monthly_dates(date(2024, 1, 1), 14)
    values: list[float] = [prior] * 14
    values[13] = latest
    values[1] = prior
    return [
        FredEconomicObservation(
            observation_date=d,
            value=v,
            series_id=FRED_UNRATE_US,
        )
        for d, v in zip(dates, values, strict=True)
    ]


def _seed_e3(session: Session, country: str = "US", sahm_triggered: int = 0) -> None:
    session.add(
        E3Labor(
            country_code=country,
            date=date(2024, 12, 31),
            methodology_version="E3_LABOR_v0.1",
            score_normalized=55.0,
            score_raw=0.3,
            sahm_triggered=sahm_triggered,
            sahm_value=0.0,
            components_json="{}",
            components_available=8,
            lookback_years=10,
            confidence=0.82,
            source_connectors="FRED",
        )
    )
    session.commit()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_constants() -> None:
    assert FRED_CPI_US == "CPIAUCSL"
    assert FRED_CPI_OECD_TEMPLATE == "CPALTT01{iso}M659N"
    assert FRED_UNRATE_US == "UNRATE"
    assert frozenset({"DE", "PT", "IT", "ES", "FR", "NL"}) == SUPPORTED_EA_COUNTRIES


# ---------------------------------------------------------------------------
# US path
# ---------------------------------------------------------------------------


async def test_resolve_us_full_stack(db_session: Session) -> None:
    """CPI 3% YoY, UNRATE 0.5pp rise, E3 Sahm=0 → all three inputs present."""
    _seed_e3(db_session, country="US", sahm_triggered=0)
    fred = AsyncMock()
    fred.fetch_economic_series.side_effect = [
        # First call: CPI
        _cpi_history_us(latest_pct=103.0, prior_pct=100.0),
        # Second call: UNRATE
        _unrate_history(latest=4.5, prior=4.0),
    ]
    inputs = await resolve_stagflation_inputs(
        "US", date(2025, 1, 31), fred=fred, session=db_session
    )
    assert inputs.cpi_yoy == pytest.approx(0.03, abs=0.001)
    assert inputs.sahm_triggered == 0
    assert inputs.unemp_delta == pytest.approx(0.005, abs=0.001)
    # Two FRED calls: CPI + UNRATE.
    assert fred.fetch_economic_series.call_count == 2


async def test_resolve_us_sahm_triggered(db_session: Session) -> None:
    """E3 Sahm=1 surfaces through sahm_triggered field."""
    _seed_e3(db_session, country="US", sahm_triggered=1)
    fred = AsyncMock()
    fred.fetch_economic_series.side_effect = [
        _cpi_history_us(latest_pct=108.0, prior_pct=100.0),
        _unrate_history(latest=5.0, prior=4.2),
    ]
    inputs = await resolve_stagflation_inputs(
        "US", date(2025, 1, 31), fred=fred, session=db_session
    )
    assert inputs.sahm_triggered == 1


async def test_resolve_us_cpi_unavailable_returns_none(db_session: Session) -> None:
    """FRED CPI DataUnavailableError → cpi_yoy=None, other fields still populated."""
    _seed_e3(db_session, country="US", sahm_triggered=0)
    fred = AsyncMock()
    fred.fetch_economic_series.side_effect = [
        DataUnavailableError("CPI outage"),
        _unrate_history(latest=4.5, prior=4.0),
    ]
    inputs = await resolve_stagflation_inputs(
        "US", date(2025, 1, 31), fred=fred, session=db_session
    )
    assert inputs.cpi_yoy is None
    assert inputs.sahm_triggered == 0
    assert inputs.unemp_delta == pytest.approx(0.005, abs=0.001)


async def test_resolve_us_unrate_unavailable_returns_none(db_session: Session) -> None:
    _seed_e3(db_session, country="US", sahm_triggered=0)
    fred = AsyncMock()
    fred.fetch_economic_series.side_effect = [
        _cpi_history_us(latest_pct=103.0, prior_pct=100.0),
        DataUnavailableError("UNRATE outage"),
    ]
    inputs = await resolve_stagflation_inputs(
        "US", date(2025, 1, 31), fred=fred, session=db_session
    )
    assert inputs.cpi_yoy == pytest.approx(0.03, abs=0.001)
    assert inputs.unemp_delta is None


async def test_resolve_us_cpi_too_few_points(db_session: Session) -> None:
    """< 13 monthly CPI points → YoY returns None."""
    _seed_e3(db_session, country="US", sahm_triggered=0)
    fred = AsyncMock()
    fred.fetch_economic_series.side_effect = [
        # Only 5 months of CPI.
        [
            FredEconomicObservation(
                observation_date=date(2024, 8 + i, 1),
                value=100.0,
                series_id=FRED_CPI_US,
            )
            for i in range(5)
        ],
        _unrate_history(latest=4.0, prior=4.0),
    ]
    inputs = await resolve_stagflation_inputs(
        "US", date(2025, 1, 31), fred=fred, session=db_session
    )
    assert inputs.cpi_yoy is None


async def test_resolve_us_no_e3_row_returns_none_sahm(db_session: Session) -> None:
    fred = AsyncMock()
    fred.fetch_economic_series.side_effect = [
        _cpi_history_us(latest_pct=103.0, prior_pct=100.0),
        _unrate_history(latest=4.5, prior=4.0),
    ]
    inputs = await resolve_stagflation_inputs(
        "US", date(2025, 1, 31), fred=fred, session=db_session
    )
    assert inputs.sahm_triggered is None


# ---------------------------------------------------------------------------
# EA path
# ---------------------------------------------------------------------------


async def test_resolve_de_oecd_cpi(db_session: Session) -> None:
    """DE: CPI via OECD CPALTT01DEM659N; sahm_triggered=None, unemp_delta=None."""
    fred = AsyncMock()
    # OECD series returns YoY growth directly as percent (e.g. 3.5 → 0.035).
    fred.fetch_economic_series.return_value = [
        FredEconomicObservation(
            observation_date=date(2024, m + 1, 1),
            value=3.5,
            series_id="CPALTT01DEM659N",
        )
        for m in range(3)
    ]
    inputs = await resolve_stagflation_inputs(
        "DE", date(2024, 3, 31), fred=fred, session=db_session
    )
    assert inputs.cpi_yoy == pytest.approx(0.035, abs=0.0001)
    assert inputs.sahm_triggered is None
    assert inputs.unemp_delta is None
    # Only one FRED call on the EA path.
    assert fred.fetch_economic_series.call_count == 1


async def test_resolve_de_cpi_unavailable(db_session: Session) -> None:
    fred = AsyncMock()
    fred.fetch_economic_series.side_effect = DataUnavailableError("OECD outage")
    inputs = await resolve_stagflation_inputs(
        "DE", date(2024, 3, 31), fred=fred, session=db_session
    )
    assert inputs.cpi_yoy is None
    assert inputs.sahm_triggered is None
    assert inputs.unemp_delta is None


async def test_resolve_unsupported_country(db_session: Session) -> None:
    """JP (or other) not in supported set → all None, no FRED calls."""
    fred = AsyncMock()
    inputs = await resolve_stagflation_inputs(
        "JP", date(2024, 1, 31), fred=fred, session=db_session
    )
    assert inputs.cpi_yoy is None
    assert inputs.sahm_triggered is None
    assert inputs.unemp_delta is None
    fred.fetch_economic_series.assert_not_called()
