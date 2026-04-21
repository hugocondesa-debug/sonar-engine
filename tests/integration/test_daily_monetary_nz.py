"""Live integration — NZ M1 TE-primary cascade (Sprint U-NZ c5).

Two @slow canaries that prove the NZ RBNZ-connector cascade end-to-end:

- ``test_daily_monetary_nz_te_primary`` — TE key set, full builder
  instantiation; verifies ``NZ_OCR_TE_PRIMARY`` flag lands on the
  persisted M1 row and no staleness flag is present. M2 + M4 NZ are
  still wire-ready scaffolds (raise ``InsufficientDataError``) so
  only ``m1`` persists.
- ``test_daily_monetary_nz_fred_fallback_when_te_absent_rbnz_blocked``
  — TE handle omitted and RBNZ handle present but the live host
  currently perimeter-403s (CAL-NZ-RBNZ-TABLES). Pipeline falls
  through to FRED OECD mirror (``IRSTCI01NZM156N``) and raises the
  explicit ``NZ_OCR_FRED_FALLBACK_STALE`` + ``CALIBRATION_STALE``
  plus ``NZ_OCR_RBNZ_UNAVAILABLE`` flag recording the blocked
  secondary. Mirrors the Sprint T AU-fred-fallback canary structure;
  the RBNZ-secondary canary (AU analog) lands when the perimeter
  block lifts.

All gated behind ``pytest -m slow`` and skipped when ``FRED_API_KEY``
is not set. The TE-primary test additionally skips when ``TE_API_KEY``
is not set. Pattern mirrors ``test_daily_monetary_au.py`` /
``test_daily_monetary_ca.py`` so regressions are easy to spot across
the country cascades.
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
from sonar.connectors.fred import FredConnector
from sonar.connectors.rbnz import RBNZConnector
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


async def test_daily_monetary_nz_te_primary(
    mem_session: Session,
    fred_api_key: str,
    te_api_key: str,
    anchor: date,
    tmp_path: Path,
) -> None:
    """NZ M1 pipeline with TE enabled — canonical daily-fresh RBNZ-via-TE path."""
    fred = FredConnector(api_key=fred_api_key, cache_dir=str(tmp_path / "fred"))
    cbo = CboConnector(fred=fred)
    ecb = EcbSdwConnector(cache_dir=str(tmp_path / "ecb"))
    rbnz = RBNZConnector(cache_dir=str(tmp_path / "rbnz"))
    te = TEConnector(api_key=te_api_key, cache_dir=str(tmp_path / "te"))
    try:
        monetary_builder = MonetaryInputsBuilder(fred=fred, cbo=cbo, ecb_sdw=ecb, rbnz=rbnz, te=te)
        inputs: MonetaryIndicesInputs = await build_live_monetary_inputs(
            "NZ", anchor, builder=monetary_builder, history_years=2
        )
        results = compute_all_monetary_indices(inputs)
        persisted = persist_many_monetary_results(mem_session, results)
    finally:
        await fred.aclose()
        await ecb.aclose()
        await rbnz.aclose()
        await te.aclose()

    assert persisted["m1"] == 1
    # M2 + M4 NZ scaffolds raise InsufficientDataError — pipeline skips cleanly.
    assert persisted["m2"] == 0
    assert persisted["m4"] == 0
    row = mem_session.query(M1Row).filter(M1Row.country_code == "NZ").one()
    flags = (row.flags or "").split(",")
    # TE-primary path — NZ_OCR_TE_PRIMARY must be present.
    assert "NZ_OCR_TE_PRIMARY" in flags
    # Neither native-secondary nor FRED fallback should land on the happy path.
    assert "NZ_OCR_RBNZ_NATIVE" not in flags
    assert "NZ_OCR_FRED_FALLBACK_STALE" not in flags
    assert "CALIBRATION_STALE" not in flags
    # Cross-cutting NZ flags.
    assert "R_STAR_PROXY" in flags
    assert "EXPECTED_INFLATION_CB_TARGET" in flags
    assert "NZ_BS_GDP_PROXY_ZERO" in flags


async def test_daily_monetary_nz_fred_fallback_when_te_absent_rbnz_blocked(
    mem_session: Session,
    fred_api_key: str,
    anchor: date,
    tmp_path: Path,
) -> None:
    """No TE, RBNZ handle present but perimeter-403 — falls through to FRED.

    Documents the live state at Sprint U-NZ close (2026-04-21): the
    RBNZ host returns HTTP 403 Website-unavailable from the SONAR VPS
    egress, so the RBNZ secondary slot surfaces DataUnavailableError
    and the cascade records NZ_OCR_RBNZ_UNAVAILABLE before landing on
    FRED with the canonical staleness flags. When CAL-NZ-RBNZ-TABLES
    closes (edge unblocks) this canary flips to asserting
    NZ_OCR_RBNZ_NATIVE instead — the parser is already wired.
    """
    fred = FredConnector(api_key=fred_api_key, cache_dir=str(tmp_path / "fred"))
    cbo = CboConnector(fred=fred)
    ecb = EcbSdwConnector(cache_dir=str(tmp_path / "ecb"))
    rbnz = RBNZConnector(cache_dir=str(tmp_path / "rbnz"))
    try:
        monetary_builder = MonetaryInputsBuilder(fred=fred, cbo=cbo, ecb_sdw=ecb, rbnz=rbnz)
        inputs: MonetaryIndicesInputs = await build_live_monetary_inputs(
            "NZ", anchor, builder=monetary_builder, history_years=2
        )
        results = compute_all_monetary_indices(inputs)
        persisted = persist_many_monetary_results(mem_session, results)
    finally:
        await fred.aclose()
        await ecb.aclose()
        await rbnz.aclose()

    assert persisted["m1"] == 1
    row = mem_session.query(M1Row).filter(M1Row.country_code == "NZ").one()
    flags = (row.flags or "").split(",")
    assert "NZ_OCR_FRED_FALLBACK_STALE" in flags
    assert "CALIBRATION_STALE" in flags
    assert "NZ_OCR_RBNZ_UNAVAILABLE" in flags
    assert "NZ_OCR_TE_PRIMARY" not in flags
    assert "NZ_OCR_RBNZ_NATIVE" not in flags
