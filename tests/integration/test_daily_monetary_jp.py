"""Live integration — JP M1 TE-primary cascade (Sprint L c6/7).

Two @slow canaries that prove the JP BoJ-connector cascade end-to-end:

- ``test_daily_monetary_jp_te_primary`` — TE key set, full builder
  instantiation; verifies ``JP_BANK_RATE_TE_PRIMARY`` flag lands on the
  persisted M1 row and no staleness flag is present. M2 + M4 JP are
  still wire-ready scaffolds (raise ``InsufficientDataError``) so only
  ``m1`` persists.
- ``test_daily_monetary_jp_fred_fallback_when_te_absent`` — TE handle
  omitted (simulates TE outage / no-key); pipeline falls through to
  FRED OECD mirror (``IRSTCI01JPM156N``) and raises the explicit
  ``JP_BANK_RATE_FRED_FALLBACK_STALE`` + ``CALIBRATION_STALE`` flags.

Both are gated behind ``pytest -m slow`` and skipped when
``FRED_API_KEY`` is not set. The TE-primary test additionally skips
when ``TE_API_KEY`` is not set. Pattern mirrors
``test_daily_monetary_gb_te_cascade.py`` so regressions are easy to
spot across the two cascades.
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from sonar.connectors.boj import BoJConnector
from sonar.connectors.cbo import CboConnector
from sonar.connectors.ecb_sdw import EcbSdwConnector
from sonar.connectors.fred import FredConnector
from sonar.connectors.te import TEConnector
from sonar.db.models import Base, M1EffectiveRatesResult as M1Row
from sonar.db.persistence import persist_many_monetary_results
from sonar.indices.monetary.builders import MonetaryInputsBuilder
from sonar.indices.monetary.orchestrator import (
    MonetaryIndicesInputs,
    compute_all_monetary_indices,
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
def te_api_key() -> str:
    key = os.environ.get("TE_API_KEY")
    if not key:
        pytest.skip("TE_API_KEY not set")
    return key


@pytest.fixture
def anchor() -> date:
    return datetime.now(tz=UTC).date() - timedelta(days=14)


@pytest.fixture
def mem_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


async def test_daily_monetary_jp_te_primary(
    mem_session: Session,
    fred_api_key: str,
    te_api_key: str,
    anchor: date,
    tmp_path: Path,
) -> None:
    """JP M1 pipeline with TE enabled — canonical daily-fresh BoJ path."""
    fred = FredConnector(api_key=fred_api_key, cache_dir=str(tmp_path / "fred"))
    cbo = CboConnector(fred=fred)
    ecb = EcbSdwConnector(cache_dir=str(tmp_path / "ecb"))
    boj = BoJConnector(cache_dir=str(tmp_path / "boj"))
    te = TEConnector(api_key=te_api_key, cache_dir=str(tmp_path / "te"))
    try:
        monetary_builder = MonetaryInputsBuilder(fred=fred, cbo=cbo, ecb_sdw=ecb, boj=boj, te=te)
        inputs: MonetaryIndicesInputs = await build_live_monetary_inputs(
            "JP", anchor, builder=monetary_builder, history_years=2
        )
        results = compute_all_monetary_indices(inputs)
        persisted = persist_many_monetary_results(mem_session, results)
    finally:
        await fred.aclose()
        await ecb.aclose()
        await boj.aclose()
        await te.aclose()

    assert persisted["m1"] == 1
    # M2 + M4 JP scaffolds raise InsufficientDataError — pipeline skips cleanly.
    assert persisted["m2"] == 0
    assert persisted["m4"] == 0
    row = mem_session.query(M1Row).filter(M1Row.country_code == "JP").one()
    flags = (row.flags or "").split(",")
    # TE-primary path — JP_BANK_RATE_TE_PRIMARY must be present.
    assert "JP_BANK_RATE_TE_PRIMARY" in flags
    # FRED fallback flags must be absent on the happy path.
    assert "JP_BANK_RATE_FRED_FALLBACK_STALE" not in flags
    assert "CALIBRATION_STALE" not in flags
    # Cross-cutting JP flags.
    assert "R_STAR_PROXY" in flags
    assert "EXPECTED_INFLATION_CB_TARGET" in flags
    assert "JP_BS_GDP_PROXY_ZERO" in flags


async def test_daily_monetary_jp_fred_fallback_when_te_absent(
    mem_session: Session,
    fred_api_key: str,
    anchor: date,
    tmp_path: Path,
) -> None:
    """TE handle omitted — JP cascade falls through to FRED with stale flags."""
    fred = FredConnector(api_key=fred_api_key, cache_dir=str(tmp_path / "fred"))
    cbo = CboConnector(fred=fred)
    ecb = EcbSdwConnector(cache_dir=str(tmp_path / "ecb"))
    # No TE, no BoJ — cascade must still deliver M1 via FRED's OECD mirror
    # (IRSTCI01JPM156N) with the staleness flags surfaced.
    try:
        monetary_builder = MonetaryInputsBuilder(fred=fred, cbo=cbo, ecb_sdw=ecb)
        inputs: MonetaryIndicesInputs = await build_live_monetary_inputs(
            "JP", anchor, builder=monetary_builder, history_years=2
        )
        results = compute_all_monetary_indices(inputs)
        persisted = persist_many_monetary_results(mem_session, results)
    finally:
        await fred.aclose()
        await ecb.aclose()

    assert persisted["m1"] == 1
    row = mem_session.query(M1Row).filter(M1Row.country_code == "JP").one()
    flags = (row.flags or "").split(",")
    assert "JP_BANK_RATE_FRED_FALLBACK_STALE" in flags
    assert "CALIBRATION_STALE" in flags
    assert "JP_BANK_RATE_TE_PRIMARY" not in flags
