"""Integration test — daily-curves US end-to-end pipeline.

Exercises the L8 ``run_us`` orchestrator: live FRED nominal+linker fetch
→ NSS fit + zero/forward/real derive → atomic persist into in-memory
SQLite. Asserts all 4 sibling rows populated for 2024-01-02. Skipped
without a FRED API key.
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
from sonar.connectors.fred import FredConnector
from sonar.db.models import (
    Base,
    NSSYieldCurveForwards,
    NSSYieldCurveReal,
    NSSYieldCurveSpot,
    NSSYieldCurveZero,
)
from sonar.pipelines.daily_curves import run_us

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator
    from pathlib import Path

    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def live_fred(tmp_path: Path) -> AsyncIterator[FredConnector]:
    placeholder = "your_fred_api_key_here"  # pragma: allowlist secret
    if not settings.fred_api_key or settings.fred_api_key == placeholder:
        pytest.skip("FRED_API_KEY not configured in .env")
    cache_dir = tmp_path / "fred_pipeline_cache"
    cache_dir.mkdir()
    conn = FredConnector(api_key=settings.fred_api_key, cache_dir=str(cache_dir))
    yield conn
    await conn.aclose()


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


async def test_daily_curves_us_2024_01_02_all_four_tables(
    live_fred: FredConnector, db_session: Session
) -> None:
    obs_date = date(2024, 1, 2)
    result = await run_us(obs_date, db_session, live_fred)

    spot = db_session.query(NSSYieldCurveSpot).filter_by(country_code="US", date=obs_date).one()
    zero = db_session.query(NSSYieldCurveZero).filter_by(fit_id=spot.fit_id).one()
    forwards = db_session.query(NSSYieldCurveForwards).filter_by(fit_id=spot.fit_id).one()
    real = db_session.query(NSSYieldCurveReal).filter_by(fit_id=spot.fit_id).one()

    assert spot.fit_id == str(result.fit_id)
    assert spot.observations_used == 11
    assert spot.confidence > 0.0
    assert spot.source_connector == "fred"
    assert zero.derivation == "nss_derived"
    assert forwards.breakeven_forwards_json is None
    assert real.method == "direct_linker"
    assert real.linker_connector == "fred"
