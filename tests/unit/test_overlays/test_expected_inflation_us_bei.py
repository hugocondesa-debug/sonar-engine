"""Sprint 1.1 — US BEI writer fixture per spec §7.

Fixture: ``us_2024_01_02_bei`` — UST 5/10/30Y + DFII5/10/30 from FRED
on 2024-01-02 → BEI_5Y≈0.0230, BEI_10Y≈0.0242, 5y5y≈0.0254 within
±10 bps; cross-val matches T5YIFR.

The test is hermetic: pytest-httpx mocks every FRED HTTP call and an
in-memory SQLite session carries a synthetic ``yield_curves_spot`` US
row so the ``nss_fit_id`` FK lookup resolves deterministically.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from tenacity import wait_none

import sonar.db.session  # noqa: F401 — registers SQLite FK PRAGMA listener.
from sonar.connectors.fred import (
    FRED_US_BEI_SERIES,
    FRED_US_LINKER_SERIES,
    FRED_US_NOMINAL_SERIES,
    FredConnector,
)
from sonar.db.models import Base, NSSYieldCurveSpot
from sonar.overlays.exceptions import DataUnavailableError
from sonar.overlays.expected_inflation.bei import build_us_bei_row

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator
    from pathlib import Path

    from pytest_httpx import HTTPXMock
    from sqlalchemy.orm import Session

US_FIT_ID = str(uuid4())
US_FIT_DATE = date(2024, 1, 2)


@pytest.fixture
def in_memory_session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def session_with_us_spot(in_memory_session: Session) -> Session:
    """In-memory session with a synthetic US spot row for 2024-01-02.

    The row carries a deterministic ``fit_id`` (module-level constant)
    so the test can assert nss_fit_id round-trips end-to-end. The flag
    column is populated to exercise upstream-flag inheritance.
    """
    in_memory_session.add(
        NSSYieldCurveSpot(
            country_code="US",
            date=US_FIT_DATE,
            methodology_version="NSS_v0.1",
            fit_id=US_FIT_ID,
            beta_0=0.04,
            beta_1=-0.01,
            beta_2=0.0,
            beta_3=None,
            lambda_1=2.0,
            lambda_2=None,
            fitted_yields_json="{}",
            observations_used=10,
            rmse_bps=2.5,
            xval_deviation_bps=None,
            confidence=0.95,
            flags="NSS_REDUCED",
            source_connector="fred",
        )
    )
    in_memory_session.commit()
    return in_memory_session


@pytest.fixture(autouse=True)
def _disable_tenacity_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(FredConnector._fetch_raw.retry, "wait", wait_none())


@pytest_asyncio.fixture
async def fred_connector(tmp_path: Path) -> AsyncIterator[FredConnector]:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    conn = FredConnector(api_key="test_key", cache_dir=str(cache_dir))
    yield conn
    await conn.aclose()


def _mock_fred_calls(
    httpx_mock: HTTPXMock,
    *,
    bei_values: dict[str, str],
    nominal_values: dict[str, str],
    linker_values: dict[str, str],
    xval_value: str | None,
    iso_date: str = "2024-01-02",
) -> None:
    """Queue mock responses in the order ``build_us_bei_row`` calls FRED.

    Order: ``fetch_bei_series`` (T5YIE/T10YIE/T30YIEM) →
    ``fetch_yield_curve_nominal`` (11 DGS series) →
    ``fetch_yield_curve_linker`` (5 DFII series) → ``T5YIFR``.
    """
    for tenor in FRED_US_BEI_SERIES:
        value = bei_values.get(tenor)
        payload = (
            {"observations": [{"date": iso_date, "value": value}]}
            if value is not None
            else {"observations": []}
        )
        httpx_mock.add_response(method="GET", json=payload)

    for tenor in FRED_US_NOMINAL_SERIES:
        value = nominal_values.get(tenor)
        payload = (
            {"observations": [{"date": iso_date, "value": value}]}
            if value is not None
            else {"observations": []}
        )
        httpx_mock.add_response(method="GET", json=payload)

    for tenor in FRED_US_LINKER_SERIES:
        value = linker_values.get(tenor)
        payload = (
            {"observations": [{"date": iso_date, "value": value}]}
            if value is not None
            else {"observations": []}
        )
        httpx_mock.add_response(method="GET", json=payload)

    httpx_mock.add_response(
        method="GET",
        json=(
            {"observations": [{"date": iso_date, "value": xval_value}]}
            if xval_value is not None
            else {"observations": []}
        ),
    )


async def test_us_2024_01_02_bei_fixture(
    httpx_mock: HTTPXMock,
    session_with_us_spot: Session,
    fred_connector: FredConnector,
) -> None:
    # Spec §7 fixture inputs: T5YIE=2.30, T10YIE=2.42 (BEI direct);
    # DGS30=4.20, DFII30=1.95 → BEI_30Y ≈ 0.0225 (component fallback).
    # T5YIFR=2.54 — matches BEI_5y5y within tolerance, so no XVAL_DRIFT.
    _mock_fred_calls(
        httpx_mock,
        bei_values={"5Y": "2.30", "10Y": "2.42"},  # T30YIEM monthly: skipped.
        nominal_values={"30Y": "4.20"},
        linker_values={"30Y": "1.95"},
        xval_value="2.54",
    )

    bei = await build_us_bei_row(
        session_with_us_spot,
        US_FIT_DATE,
        fred_connector=fred_connector,
    )

    # Spec §7 tolerances ±10 bps (±0.001 decimal).
    assert bei.bei_tenors["5Y"] == pytest.approx(0.0230, abs=0.001)
    assert bei.bei_tenors["10Y"] == pytest.approx(0.0242, abs=0.001)
    assert bei.bei_tenors["5y5y"] == pytest.approx(0.0254, abs=0.001)

    # 30Y from DGS30 - DFII30 component subtraction (spec §4 fallback).
    assert bei.bei_tenors["30Y"] == pytest.approx(0.0225, abs=0.001)

    # FK round-trip: the dataclass UUID must match the synthetic spot fit_id.
    assert bei.linker_connector == "fred"
    assert bei.nss_fit_id is not None
    assert str(bei.nss_fit_id) == US_FIT_ID

    # Confidence: all three primary tenors landed → 0.90 baseline.
    assert bei.confidence == pytest.approx(0.90)

    # Upstream flag from yield_curves_spot.flags is inherited; T5YIFR
    # within tolerance so XVAL_DRIFT does NOT fire.
    assert "NSS_REDUCED" in bei.flags
    assert "XVAL_DRIFT" not in bei.flags


async def test_us_bei_emits_xval_drift_when_5y5y_diverges(
    httpx_mock: HTTPXMock,
    session_with_us_spot: Session,
    fred_connector: FredConnector,
) -> None:
    # Same compute path as the spec fixture, but T5YIFR diverges by
    # ~50 bps from the compounded 5y5y → expect XVAL_DRIFT flag.
    _mock_fred_calls(
        httpx_mock,
        bei_values={"5Y": "2.30", "10Y": "2.42"},
        nominal_values={"30Y": "4.20"},
        linker_values={"30Y": "1.95"},
        xval_value="3.05",
    )

    bei = await build_us_bei_row(
        session_with_us_spot,
        US_FIT_DATE,
        fred_connector=fred_connector,
    )

    assert "XVAL_DRIFT" in bei.flags


async def test_us_bei_raises_when_no_spot_row(
    httpx_mock: HTTPXMock,
    in_memory_session: Session,
    fred_connector: FredConnector,
) -> None:
    # Spec §8 mandates ``nss_fit_id`` FK; without a spot row the
    # builder raises ``DataUnavailableError`` so the orchestrator can
    # log + skip cleanly.
    _mock_fred_calls(
        httpx_mock,
        bei_values={"5Y": "2.30", "10Y": "2.42"},
        nominal_values={"30Y": "4.20"},
        linker_values={"30Y": "1.95"},
        xval_value=None,
    )

    with pytest.raises(DataUnavailableError, match="yield_curves_spot"):
        await build_us_bei_row(
            in_memory_session,
            US_FIT_DATE,
            fred_connector=fred_connector,
        )


async def test_us_bei_confidence_drops_when_30y_missing(
    httpx_mock: HTTPXMock,
    session_with_us_spot: Session,
    fred_connector: FredConnector,
) -> None:
    # 30Y absent (no DGS30 / DFII30 values) → only 5Y + 10Y land →
    # missing one primary tenor → confidence 0.90 - 0.10 = 0.80.
    _mock_fred_calls(
        httpx_mock,
        bei_values={"5Y": "2.30", "10Y": "2.42"},
        nominal_values={},
        linker_values={},
        xval_value="2.54",
    )

    bei = await build_us_bei_row(
        session_with_us_spot,
        US_FIT_DATE,
        fred_connector=fred_connector,
    )

    assert "30Y" not in bei.bei_tenors
    assert "5y5y" in bei.bei_tenors  # still computed from 5Y + 10Y.
    assert bei.confidence == pytest.approx(0.80)
