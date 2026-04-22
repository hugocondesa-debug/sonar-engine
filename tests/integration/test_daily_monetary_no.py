"""Live integration — NO M1 TE-primary cascade (Sprint X-NO C5).

Three @slow canaries that prove the NO Norges Bank-connector cascade
end-to-end:

- ``test_daily_monetary_no_te_primary`` — TE key set, full builder
  instantiation, anchor pinned to ``today - 14 days``; verifies
  ``NO_POLICY_RATE_TE_PRIMARY`` lands on the persisted M1 row and no
  staleness flag is present. M2 + M4 NO are wire-ready scaffolds
  (raise ``InsufficientDataError``) so only ``m1`` persists.
- ``test_daily_monetary_no_norgesbank_secondary_when_te_absent`` — same
  anchor, TE handle omitted but Norges Bank handle present;
  pipeline falls through to the public Norges Bank DataAPI SDMX-JSON
  endpoint and emits the ``NO_POLICY_RATE_NORGESBANK_NATIVE`` flag with
  **no** ``CALIBRATION_STALE`` / monthly qualifier (daily-parity with
  TE). Mirrors the CA BoC Valet / AU RBA F1 CSV reachable-native
  pattern — NO is the fourth country with a first-class reachable
  public secondary endpoint.
- ``test_daily_monetary_no_fred_fallback_when_te_and_norgesbank_absent``
  — same anchor, both TE + Norges Bank handles omitted; pipeline falls
  through to FRED OECD mirror (``IRSTCI01NOM156N``) and emits the
  explicit ``NO_POLICY_RATE_FRED_FALLBACK_STALE`` + ``CALIBRATION_STALE``
  flags. Notable: the FRED mirror is only ~1 month lagged at Sprint
  X-NO probe (freshest of the G10 OECD mirrors), but the cascade still
  surfaces the cadence delta.

Standard positive-only country — no negative-rate canary (contrast
``test_daily_monetary_ch.py`` which pins a 2020 -0.75 % anchor). Norges
Bank never ran a negative policy rate; the 2020-2021 COVID trough sat
at exactly 0 % which is above the ZLB threshold so compute succeeds.

All gated behind ``pytest -m slow`` and skipped when ``FRED_API_KEY``
is not set. The TE-primary test additionally skips when ``TE_API_KEY``
is not set. Pattern mirrors ``test_daily_monetary_au.py`` /
``test_daily_monetary_ca.py`` / ``test_daily_monetary_ch.py`` so
regressions are easy to spot across the six country cascades.
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
from sonar.connectors.norgesbank import NorgesBankConnector
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


def _recent_anchor() -> date:
    """14 days back so the resolver has a stable observation even on weekends."""
    today = datetime.now(tz=UTC).date()
    return today - timedelta(days=14)


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
def mem_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


async def test_daily_monetary_no_te_primary(
    mem_session: Session,
    fred_api_key: str,
    te_api_key: str,
    tmp_path: Path,
) -> None:
    """NO M1 pipeline with TE enabled — canonical daily-fresh Norges Bank path."""
    fred = FredConnector(api_key=fred_api_key, cache_dir=str(tmp_path / "fred"))
    cbo = CboConnector(fred=fred)
    ecb = EcbSdwConnector(cache_dir=str(tmp_path / "ecb"))
    norgesbank = NorgesBankConnector(cache_dir=str(tmp_path / "norgesbank"))
    te = TEConnector(api_key=te_api_key, cache_dir=str(tmp_path / "te"))
    try:
        monetary_builder = MonetaryInputsBuilder(
            fred=fred, cbo=cbo, ecb_sdw=ecb, norgesbank=norgesbank, te=te
        )
        inputs: MonetaryIndicesInputs = await build_live_monetary_inputs(
            "NO", _recent_anchor(), builder=monetary_builder, history_years=2
        )
        results = compute_all_monetary_indices(inputs)
        persisted = persist_many_monetary_results(mem_session, results)
    finally:
        await fred.aclose()
        await ecb.aclose()
        await norgesbank.aclose()
        await te.aclose()

    assert persisted["m1"] == 1
    # M2 + M4 NO scaffolds raise InsufficientDataError — pipeline skips cleanly.
    assert persisted["m2"] == 0
    assert persisted["m4"] == 0
    row = mem_session.query(M1Row).filter(M1Row.country_code == "NO").one()
    flags = (row.flags or "").split(",")
    # TE-primary path — NO_POLICY_RATE_TE_PRIMARY must be present.
    assert "NO_POLICY_RATE_TE_PRIMARY" in flags
    # Neither native-secondary nor FRED fallback should land on the happy path.
    assert "NO_POLICY_RATE_NORGESBANK_NATIVE" not in flags
    assert "NO_POLICY_RATE_FRED_FALLBACK_STALE" not in flags
    assert "CALIBRATION_STALE" not in flags
    # Cross-cutting NO flags.
    assert "R_STAR_PROXY" in flags
    assert "EXPECTED_INFLATION_CB_TARGET" in flags
    assert "NO_BS_GDP_PROXY_ZERO" in flags


async def test_daily_monetary_no_norgesbank_secondary_when_te_absent(
    mem_session: Session,
    fred_api_key: str,
    tmp_path: Path,
) -> None:
    """No TE, Norges Bank handle present — cascade hits the public SDMX-JSON endpoint."""
    fred = FredConnector(api_key=fred_api_key, cache_dir=str(tmp_path / "fred"))
    cbo = CboConnector(fred=fred)
    ecb = EcbSdwConnector(cache_dir=str(tmp_path / "ecb"))
    norgesbank = NorgesBankConnector(cache_dir=str(tmp_path / "norgesbank"))
    try:
        monetary_builder = MonetaryInputsBuilder(
            fred=fred, cbo=cbo, ecb_sdw=ecb, norgesbank=norgesbank
        )
        inputs: MonetaryIndicesInputs = await build_live_monetary_inputs(
            "NO", _recent_anchor(), builder=monetary_builder, history_years=2
        )
        results = compute_all_monetary_indices(inputs)
        persisted = persist_many_monetary_results(mem_session, results)
    finally:
        await fred.aclose()
        await ecb.aclose()
        await norgesbank.aclose()

    assert persisted["m1"] == 1
    row = mem_session.query(M1Row).filter(M1Row.country_code == "NO").one()
    flags = (row.flags or "").split(",")
    assert "NO_POLICY_RATE_NORGESBANK_NATIVE" in flags
    assert "NO_POLICY_RATE_TE_PRIMARY" not in flags
    assert "NO_POLICY_RATE_FRED_FALLBACK_STALE" not in flags
    # Key invariant: Norges Bank DataAPI is daily-parity with TE, no
    # CALIBRATION_STALE or MONTHLY qualifier (contrast CH SNB).
    assert "CALIBRATION_STALE" not in flags
    assert not any("MONTHLY" in f for f in flags)


async def test_daily_monetary_no_fred_fallback_when_te_and_norgesbank_absent(
    mem_session: Session,
    fred_api_key: str,
    tmp_path: Path,
) -> None:
    """No TE, no Norges Bank — NO cascade falls through to FRED with stale flags."""
    fred = FredConnector(api_key=fred_api_key, cache_dir=str(tmp_path / "fred"))
    cbo = CboConnector(fred=fred)
    ecb = EcbSdwConnector(cache_dir=str(tmp_path / "ecb"))
    try:
        monetary_builder = MonetaryInputsBuilder(fred=fred, cbo=cbo, ecb_sdw=ecb)
        inputs: MonetaryIndicesInputs = await build_live_monetary_inputs(
            "NO", _recent_anchor(), builder=monetary_builder, history_years=2
        )
        results = compute_all_monetary_indices(inputs)
        persisted = persist_many_monetary_results(mem_session, results)
    finally:
        await fred.aclose()
        await ecb.aclose()

    assert persisted["m1"] == 1
    row = mem_session.query(M1Row).filter(M1Row.country_code == "NO").one()
    flags = (row.flags or "").split(",")
    assert "NO_POLICY_RATE_FRED_FALLBACK_STALE" in flags
    assert "CALIBRATION_STALE" in flags
    assert "NO_POLICY_RATE_TE_PRIMARY" not in flags
    assert "NO_POLICY_RATE_NORGESBANK_NATIVE" not in flags
