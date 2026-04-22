"""Integration tests — daily-curves multi-country dispatch (CAL-138 Sprint).

Covers the post-CAL-138 curve-fit surface: US (FRED, existing), DE
(Bundesbank), EA (ECB SDW), GB/JP/CA (TE). Countries deferred per
CAL-CURVES-EA-PERIPHERY / CAL-CURVES-T1-SPARSE raise
:class:`InsufficientDataError` at dispatch — verified by unit tests of
``_fetch_nominals_linkers``; integration tests here exercise the live
cascade end-to-end.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sonar.db.session  # noqa: F401 — registers SQLite FK pragma listener
from sonar.config import settings
from sonar.connectors.bundesbank import BundesbankConnector
from sonar.connectors.ecb_sdw import EcbSdwConnector
from sonar.connectors.te import TEConnector
from sonar.db.models import Base, NSSYieldCurveSpot
from sonar.overlays.exceptions import InsufficientDataError
from sonar.pipelines.daily_curves import (
    CURVE_SUPPORTED_COUNTRIES,
    T1_7_COUNTRIES,
    _fetch_nominals_linkers,
    run_country,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator
    from pathlib import Path

    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


@pytest_asyncio.fixture
async def bundesbank(tmp_path: Path) -> AsyncIterator[BundesbankConnector]:
    cache = tmp_path / "bundesbank"
    cache.mkdir()
    conn = BundesbankConnector(cache_dir=str(cache))
    yield conn
    await conn.aclose()


@pytest_asyncio.fixture
async def ecb_sdw(tmp_path: Path) -> AsyncIterator[EcbSdwConnector]:
    cache = tmp_path / "ecb_sdw"
    cache.mkdir()
    conn = EcbSdwConnector(cache_dir=str(cache))
    yield conn
    await conn.aclose()


@pytest_asyncio.fixture
async def te(tmp_path: Path) -> AsyncIterator[TEConnector]:
    api_key = settings.te_api_key
    if not api_key:
        pytest.skip("TE_API_KEY not configured in .env")
    cache = tmp_path / "te"
    cache.mkdir()
    conn = TEConnector(api_key=api_key, cache_dir=str(cache))
    yield conn
    await conn.aclose()


# ---------------------------------------------------------------------------
# Dispatch unit coverage
# ---------------------------------------------------------------------------


def test_t1_7_tier_constant_matches_expected() -> None:
    assert T1_7_COUNTRIES == ("US", "DE", "PT", "IT", "ES", "FR", "NL")


def test_curve_supported_countries_matches_cal138_scope() -> None:
    """Post-CAL-138 ship list: US (FRED) + DE (BB) + EA (ECB) + GB/JP/CA (TE)."""
    assert frozenset({"US", "DE", "EA", "GB", "JP", "CA"}) == CURVE_SUPPORTED_COUNTRIES


async def test_fetch_nominals_raises_for_periphery_with_cal_pointer(
    bundesbank: BundesbankConnector, ecb_sdw: EcbSdwConnector
) -> None:
    """EA periphery countries raise InsufficientDataError pointing to CAL item."""
    for country in ("PT", "IT", "ES", "FR", "NL"):
        with pytest.raises(InsufficientDataError, match="CAL-CURVES-EA-PERIPHERY"):
            await _fetch_nominals_linkers(
                country,
                date(2024, 12, 30),
                fred=None,
                bundesbank=bundesbank,
                ecb_sdw=ecb_sdw,
                te=None,
            )


async def test_fetch_nominals_raises_for_sparse_t1_with_cal_pointer(
    bundesbank: BundesbankConnector, ecb_sdw: EcbSdwConnector
) -> None:
    """AU/NZ/CH/SE/NO/DK raise InsufficientDataError pointing to CAL-CURVES-T1-SPARSE."""
    for country in ("AU", "NZ", "CH", "SE", "NO", "DK"):
        with pytest.raises(InsufficientDataError, match="CAL-CURVES-T1-SPARSE"):
            await _fetch_nominals_linkers(
                country,
                date(2024, 12, 30),
                fred=None,
                bundesbank=bundesbank,
                ecb_sdw=ecb_sdw,
                te=None,
            )


# ---------------------------------------------------------------------------
# Live canaries (one per shipped country except US — already covered in
# test_daily_curves_pipeline.py). Wall-clock target ≤ 60s combined.
# ---------------------------------------------------------------------------


@pytest.mark.slow
async def test_daily_curves_de_end_to_end(
    bundesbank: BundesbankConnector, db_session: Session
) -> None:
    """DE 2024-12-30 via Bundesbank → full NSS fit persisted."""
    obs_date = date(2024, 12, 30)
    result = await run_country(
        country="DE",
        observation_date=obs_date,
        session=db_session,
        bundesbank=bundesbank,
    )
    spot = db_session.query(NSSYieldCurveSpot).filter_by(country_code="DE", date=obs_date).one()
    assert spot.fit_id == str(result.fit_id)
    assert spot.observations_used >= 6  # NS min
    assert spot.source_connector == "bundesbank"


@pytest.mark.slow
async def test_daily_curves_ea_end_to_end(ecb_sdw: EcbSdwConnector, db_session: Session) -> None:
    """EA AAA 2024-12-30 via ECB SDW → full NSS fit persisted."""
    obs_date = date(2024, 12, 30)
    result = await run_country(
        country="EA",
        observation_date=obs_date,
        session=db_session,
        ecb_sdw=ecb_sdw,
    )
    spot = db_session.query(NSSYieldCurveSpot).filter_by(country_code="EA", date=obs_date).one()
    assert spot.fit_id == str(result.fit_id)
    assert spot.observations_used >= 9  # Svensson min
    assert spot.source_connector == "ecb_sdw"


@pytest.mark.slow
async def test_daily_curves_gb_end_to_end(te: TEConnector, db_session: Session) -> None:
    """GB 2024-12-30 via TE GUKG family → full NSS fit persisted."""
    obs_date = date(2024, 12, 30)
    result = await run_country(
        country="GB",
        observation_date=obs_date,
        session=db_session,
        te=te,
    )
    spot = db_session.query(NSSYieldCurveSpot).filter_by(country_code="GB", date=obs_date).one()
    assert spot.fit_id == str(result.fit_id)
    assert spot.observations_used >= 8
    assert spot.source_connector == "te"


@pytest.mark.slow
async def test_daily_curves_jp_end_to_end(te: TEConnector, db_session: Session) -> None:
    """JP 2024-12-30 via TE GJGB family → full NSS fit persisted."""
    obs_date = date(2024, 12, 30)
    result = await run_country(
        country="JP",
        observation_date=obs_date,
        session=db_session,
        te=te,
    )
    spot = db_session.query(NSSYieldCurveSpot).filter_by(country_code="JP", date=obs_date).one()
    assert spot.fit_id == str(result.fit_id)
    assert spot.observations_used >= 7
    assert spot.source_connector == "te"


@pytest.mark.slow
async def test_daily_curves_ca_end_to_end(te: TEConnector, db_session: Session) -> None:
    """CA 2024-12-30 via TE GCAN family → NS-reduced fit persisted."""
    obs_date = date(2024, 12, 30)
    result = await run_country(
        country="CA",
        observation_date=obs_date,
        session=db_session,
        te=te,
    )
    spot = db_session.query(NSSYieldCurveSpot).filter_by(country_code="CA", date=obs_date).one()
    assert spot.fit_id == str(result.fit_id)
    # CA has 6 tenors → NS-reduced fit (MIN_OBSERVATIONS met,
    # MIN_OBSERVATIONS_FOR_SVENSSON=9 not met).
    assert 6 <= spot.observations_used < 9
    assert spot.source_connector == "te"
