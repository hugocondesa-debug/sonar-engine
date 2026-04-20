"""Live smoke for daily economic + monetary pipelines (week7 sprint B C4).

Per brief §Commit 6: prove that the two new pipelines run end-to-end
against live FRED + ECB SDW feeds and persist rows into the shared
in-memory SQLite database. Runs only under ``pytest -m slow`` so default
CI stays offline. Skips when ``FRED_API_KEY`` isn't set.

Tests run the async builders directly via ``pytest-asyncio`` rather than
through the pipelines' ``asyncio.run`` Typer bridge — the bridge works
fine for CLI use but spawns a fresh event loop per call, which raises
``PytestUnraisableExceptionWarning`` when httpx's async sockets get
garbage-collected on a loop they no longer own. Driving the async layer
directly keeps the integration assertions strict (E1/E3/E4/M1/M2/M4
persist in the shared DB session) while avoiding the double-loop quirk.
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from sonar.connectors.cbo import CboConnector
from sonar.connectors.ecb_sdw import EcbSdwConnector
from sonar.connectors.eurostat import EurostatConnector
from sonar.connectors.fred import FredConnector
from sonar.db.models import (
    Base,
    E1Activity,
    E3Labor,
    E4Sentiment,
    M1EffectiveRatesResult as M1Row,
    M2TaylorGapsResult as M2Row,
    M4FciResult as M4Row,
)
from sonar.db.persistence import (
    persist_many_economic_results,
    persist_many_monetary_results,
)
from sonar.indices.monetary.builders import MonetaryInputsBuilder
from sonar.indices.monetary.orchestrator import (
    MonetaryIndicesInputs,
    compute_all_monetary_indices,
)
from sonar.pipelines.daily_economic_indices import (
    EconomicIndicesInputs,
    build_live_economic_inputs,
    compute_all_economic_indices,
)
from sonar.pipelines.daily_monetary_indices import build_live_monetary_inputs

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.slow


@pytest.fixture
def fred_api_key() -> str:
    key = os.environ.get("FRED_API_KEY")
    if not key:
        pytest.skip("FRED_API_KEY not set")
    return key


@pytest.fixture
def anchor() -> date:
    # ~14 days back so weekly FRED/NFCI series have already published.
    return datetime.now(tz=UTC).date() - timedelta(days=14)


@pytest.fixture
def mem_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


async def test_daily_economic_indices_us_live(
    mem_session: Session, fred_api_key: str, anchor: date, tmp_path: Path
) -> None:
    fred = FredConnector(api_key=fred_api_key, cache_dir=str(tmp_path / "fred"))
    eurostat = EurostatConnector(cache_dir=str(tmp_path / "eurostat"))
    try:
        inputs: EconomicIndicesInputs = await build_live_economic_inputs(
            "US", anchor, fred=fred, eurostat=eurostat
        )
        results = compute_all_economic_indices(inputs)
        persisted = persist_many_economic_results(
            mem_session, e1=results.e1, e3=results.e3, e4=results.e4
        )
    finally:
        await fred.aclose()
        await eurostat.aclose()

    assert persisted["e1"] >= 1
    assert persisted["e3"] >= 1
    assert persisted["e4"] >= 1
    assert mem_session.query(E1Activity).count() >= 1
    assert mem_session.query(E3Labor).count() >= 1
    assert mem_session.query(E4Sentiment).count() >= 1


async def test_daily_monetary_indices_us_live(
    mem_session: Session, fred_api_key: str, anchor: date, tmp_path: Path
) -> None:
    fred = FredConnector(api_key=fred_api_key, cache_dir=str(tmp_path / "fred"))
    cbo = CboConnector(fred=fred)
    ecb = EcbSdwConnector(cache_dir=str(tmp_path / "ecb"))
    try:
        monetary_builder = MonetaryInputsBuilder(fred=fred, cbo=cbo, ecb_sdw=ecb)
        inputs: MonetaryIndicesInputs = await build_live_monetary_inputs(
            "US", anchor, builder=monetary_builder, history_years=15
        )
        results = compute_all_monetary_indices(inputs)
        persisted = persist_many_monetary_results(mem_session, results)
    finally:
        await fred.aclose()
        await ecb.aclose()

    assert persisted["m1"] == 1
    assert persisted["m2"] == 1
    assert persisted["m4"] == 1
    assert persisted["m3"] == 0  # M3 not wired this sprint.
    assert mem_session.query(M1Row).count() == 1
    assert mem_session.query(M2Row).count() == 1
    assert mem_session.query(M4Row).count() == 1


async def test_daily_monetary_indices_ea_live_partial(
    mem_session: Session, fred_api_key: str, anchor: date, tmp_path: Path
) -> None:
    """EA persists M1 only; M2 + M4 NotImplementedError skipped gracefully."""
    fred = FredConnector(api_key=fred_api_key, cache_dir=str(tmp_path / "fred"))
    cbo = CboConnector(fred=fred)
    ecb = EcbSdwConnector(cache_dir=str(tmp_path / "ecb"))
    try:
        monetary_builder = MonetaryInputsBuilder(fred=fred, cbo=cbo, ecb_sdw=ecb)
        inputs: MonetaryIndicesInputs = await build_live_monetary_inputs(
            "EA", anchor, builder=monetary_builder, history_years=15
        )
        results = compute_all_monetary_indices(inputs)
        persisted = persist_many_monetary_results(mem_session, results)
    finally:
        await fred.aclose()
        await ecb.aclose()

    assert persisted["m1"] == 1
    assert persisted["m2"] == 0
    assert persisted["m4"] == 0
    assert mem_session.query(M1Row).count() == 1
    assert mem_session.query(M1Row).one().country_code == "EA"
