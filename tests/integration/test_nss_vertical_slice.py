"""Integration test — L0 → L2 → L1 vertical slice for US on canonical date.

Fetches live FRED nominal + linker via FredConnector, fits NSS,
derives zero/forward, attempts real curve (expected None for US per
CAL-033 — TIPS publishes only 5 tenors), assembles NSSFitResult,
persists into in-memory SQLite via the spec §8 sibling tables, and
queries back. Marked ``@pytest.mark.integration``; skipped without an
API key.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import numpy as np
import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator
    from pathlib import Path

    from sqlalchemy.orm import Session

# Side-effect import: registers the SQLite FK-pragma listener.
import sonar.db.session  # noqa: F401
from sonar.config import settings
from sonar.connectors.fred import FredConnector
from sonar.db.models import (
    Base,
    NSSYieldCurveForwards,
    NSSYieldCurveReal,
    NSSYieldCurveSpot,
    NSSYieldCurveZero,
)
from sonar.db.persistence import persist_nss_fit_result
from sonar.overlays.nss import (
    NSSInput,
    _label_to_years,
    assemble_nss_fit_result,
    derive_forward_curve,
    derive_real_curve,
    derive_zero_curve,
    fit_nss,
)

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def live_fred(tmp_path: Path) -> AsyncIterator[FredConnector]:
    placeholder = "your_fred_api_key_here"  # pragma: allowlist secret
    if not settings.fred_api_key or settings.fred_api_key == placeholder:
        pytest.skip("FRED_API_KEY not configured in .env")
    cache_dir = tmp_path / "fred_vertical_cache"
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


async def test_us_2024_01_02_end_to_end_persist(
    live_fred: FredConnector, db_session: Session
) -> None:
    obs_date = date(2024, 1, 2)

    nominals = await live_fred.fetch_yield_curve_nominal(country="US", observation_date=obs_date)
    linkers = await live_fred.fetch_yield_curve_linker(country="US", observation_date=obs_date)

    # All 11 nominal tenors expected on a US business day.
    assert len(nominals) == 11
    # Linker has 5 tenors (CAL-033 — below MIN_OBSERVATIONS for fit).
    assert len(linkers) == 5

    tenor_labels_sorted = sorted(nominals.keys(), key=_label_to_years)
    nss_input = NSSInput(
        tenors_years=np.array([_label_to_years(t) for t in tenor_labels_sorted]),
        yields=np.array([nominals[t].yield_bps / 10_000.0 for t in tenor_labels_sorted]),
        country_code="US",
        observation_date=obs_date,
        curve_input_type="par",
    )
    spot = fit_nss(nss_input)
    zero = derive_zero_curve(spot)
    forward = derive_forward_curve(zero)

    linker_yields = {t: linkers[t].yield_bps / 10_000.0 for t in linkers}
    # 5 tenors → InsufficientDataError raises inside fit; we expect None per CAL-033.
    with pytest.raises(Exception):  # noqa: B017,PT011 — InsufficientDataError chained from fit_nss
        derive_real_curve(
            spot,
            linker_yields=linker_yields,
            observation_date=obs_date,
            country_code="US",
        )
    real = None  # CAL-033 limitation surfaced

    result = assemble_nss_fit_result(
        country_code="US",
        observation_date=obs_date,
        spot=spot,
        zero=zero,
        forward=forward,
        real=real,
    )
    persist_nss_fit_result(db_session, result)

    spot_row = db_session.query(NSSYieldCurveSpot).filter_by(country_code="US", date=obs_date).one()
    zero_row = db_session.query(NSSYieldCurveZero).filter_by(fit_id=spot_row.fit_id).one()
    fwd_row = db_session.query(NSSYieldCurveForwards).filter_by(fit_id=spot_row.fit_id).one()
    assert spot_row.fit_id == str(result.fit_id)
    assert spot_row.rmse_bps == spot.rmse_bps
    assert spot_row.observations_used == 11
    assert zero_row.derivation == "nss_derived"
    assert fwd_row.breakeven_forwards_json is None
    # No real row — CAL-033 limitation.
    assert db_session.query(NSSYieldCurveReal).count() == 0
