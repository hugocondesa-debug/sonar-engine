"""Live integration — CH M1 TE-primary cascade (Sprint V C5).

Four @slow canaries that prove the CH SNB-connector cascade end-to-end:

- ``test_daily_monetary_ch_te_primary`` — TE key set, full builder
  instantiation, anchor pinned to ``2024-03-31`` (SNB policy rate
  1.50 % — first post-normalisation level well above the ZLB
  threshold) so the full M1 compute succeeds; verifies
  ``CH_POLICY_RATE_TE_PRIMARY`` lands on the persisted M1 row and no
  staleness flag is present. M2 + M4 CH are wire-ready scaffolds
  (raise ``InsufficientDataError``) so only ``m1`` persists.
- ``test_daily_monetary_ch_snb_secondary_when_te_absent`` — same
  2024-03-31 anchor, TE handle omitted but SNB handle present;
  pipeline falls through to the public SNB ``zimoma`` cube (SARON
  row) and emits the ``CH_POLICY_RATE_SNB_NATIVE`` +
  ``CH_POLICY_RATE_SNB_NATIVE_MONTHLY`` flag pair with **no**
  ``CALIBRATION_STALE``. Parallels CA (Sprint S) and AU (Sprint T):
  secondary slot is a first-class reachable public endpoint.
- ``test_daily_monetary_ch_fred_fallback_when_te_and_snb_absent`` —
  same anchor, both TE + SNB handles omitted; pipeline falls
  through to FRED OECD mirror (``IRSTCI01CHM156N``) and emits the
  explicit ``CH_POLICY_RATE_FRED_FALLBACK_STALE`` +
  ``CALIBRATION_STALE`` flags. Notable: the FRED mirror was observed
  lagging ~2Y at the Sprint V probe (last update 2024-03) so the
  2024-03-31 anchor is exactly where the last FRED observation
  lands; ``_latest_on_or_before`` resolves cleanly.
- ``test_daily_monetary_ch_te_primary_preserves_negative_rate_history``
  — Anchor pinned to ``2020-12-15`` (deep inside the 2014-2022 SNB
  negative-rate corridor at -0.75 %). Asserts on the cascade's
  **inputs** (``inputs.m1.upstream_flags`` + ``inputs.m1.policy_rate_pct``)
  rather than the persisted M1 row: at negative policy rates the
  M1-compute :func:`compute_m1_effective_rates` correctly raises
  ``InsufficientDataError`` (spec §4 step 2 ZLB gate — no Krippner
  shadow-rate connector wired at Sprint V scope) so the DB row is
  intentionally absent. What we validate is the Sprint V promise:
  **negative values survive the cascade** and
  ``CH_NEGATIVE_RATE_ERA_DATA`` fires on the inputs payload. No
  other Tier-1 country cascade has a persistent negative-rate era
  worth guarding.

All gated behind ``pytest -m slow`` and skipped when ``FRED_API_KEY``
is not set. The TE-primary tests additionally skip when ``TE_API_KEY``
is not set. Pattern mirrors ``test_daily_monetary_au.py`` /
``test_daily_monetary_ca.py`` / ``test_daily_monetary_jp.py`` so
regressions are easy to spot across the five country cascades.
"""

from __future__ import annotations

import os
from datetime import date
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from sonar.connectors.cbo import CboConnector
from sonar.connectors.ecb_sdw import EcbSdwConnector
from sonar.connectors.fred import FredConnector
from sonar.connectors.snb import SNBConnector
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


# Anchor deliberately pinned to SNB's post-normalisation first 1.50 %
# level — chosen because (a) it sits well above the spec-§4 ZLB
# threshold (0.5 %) so the full M1 compute path exercises, (b) the
# FRED OECD mirror (IRSTCI01CHM156N) had its last observation at
# 2024-03-01 per the Sprint V probe so the FRED-fallback canary can
# resolve cleanly, and (c) a fixed historical anchor insulates the
# canaries from future SNB cuts bringing the current rate back to the
# ZLB. The 2020 negative-rate canary uses a different anchor (see
# below) to exercise the historical-negative-rate path.
POSITIVE_RATE_ANCHOR: date = date(2024, 3, 31)

# Deep inside the SNB negative-rate corridor (2014-12 → 2022-08 at
# -0.75 %). Canary validates that the cascade preserves the sign and
# surfaces CH_NEGATIVE_RATE_ERA_DATA on the inputs bundle. At this
# anchor the M1 compute itself correctly raises InsufficientDataError
# (ZLB without Krippner) so persistence returns zero rows — that's
# the spec-correct behaviour, not a Sprint V regression.
NEGATIVE_RATE_ANCHOR: date = date(2020, 12, 15)


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


async def test_daily_monetary_ch_te_primary(
    mem_session: Session,
    fred_api_key: str,
    te_api_key: str,
    tmp_path: Path,
) -> None:
    """CH M1 pipeline with TE enabled — canonical daily-fresh SNB path."""
    fred = FredConnector(api_key=fred_api_key, cache_dir=str(tmp_path / "fred"))
    cbo = CboConnector(fred=fred)
    ecb = EcbSdwConnector(cache_dir=str(tmp_path / "ecb"))
    snb = SNBConnector(cache_dir=str(tmp_path / "snb"))
    te = TEConnector(api_key=te_api_key, cache_dir=str(tmp_path / "te"))
    try:
        monetary_builder = MonetaryInputsBuilder(fred=fred, cbo=cbo, ecb_sdw=ecb, snb=snb, te=te)
        inputs: MonetaryIndicesInputs = await build_live_monetary_inputs(
            "CH", POSITIVE_RATE_ANCHOR, builder=monetary_builder, history_years=2
        )
        results = compute_all_monetary_indices(inputs)
        persisted = persist_many_monetary_results(mem_session, results)
    finally:
        await fred.aclose()
        await ecb.aclose()
        await snb.aclose()
        await te.aclose()

    assert persisted["m1"] == 1
    # M2 + M4 CH scaffolds raise InsufficientDataError — pipeline skips cleanly.
    assert persisted["m2"] == 0
    assert persisted["m4"] == 0
    row = mem_session.query(M1Row).filter(M1Row.country_code == "CH").one()
    flags = (row.flags or "").split(",")
    # TE-primary path — CH_POLICY_RATE_TE_PRIMARY must be present.
    assert "CH_POLICY_RATE_TE_PRIMARY" in flags
    # Neither native-secondary nor FRED fallback should land on the happy path.
    assert "CH_POLICY_RATE_SNB_NATIVE" not in flags
    assert "CH_POLICY_RATE_FRED_FALLBACK_STALE" not in flags
    assert "CALIBRATION_STALE" not in flags
    # Cross-cutting CH flags.
    assert "R_STAR_PROXY" in flags
    assert "EXPECTED_INFLATION_CB_TARGET" in flags
    assert "CH_INFLATION_TARGET_BAND" in flags
    assert "CH_BS_GDP_PROXY_ZERO" in flags


async def test_daily_monetary_ch_snb_secondary_when_te_absent(
    mem_session: Session,
    fred_api_key: str,
    tmp_path: Path,
) -> None:
    """No TE, SNB handle present — cascade hits the public SNB zimoma cube."""
    fred = FredConnector(api_key=fred_api_key, cache_dir=str(tmp_path / "fred"))
    cbo = CboConnector(fred=fred)
    ecb = EcbSdwConnector(cache_dir=str(tmp_path / "ecb"))
    snb = SNBConnector(cache_dir=str(tmp_path / "snb"))
    try:
        monetary_builder = MonetaryInputsBuilder(fred=fred, cbo=cbo, ecb_sdw=ecb, snb=snb)
        inputs: MonetaryIndicesInputs = await build_live_monetary_inputs(
            "CH", POSITIVE_RATE_ANCHOR, builder=monetary_builder, history_years=2
        )
        results = compute_all_monetary_indices(inputs)
        persisted = persist_many_monetary_results(mem_session, results)
    finally:
        await fred.aclose()
        await ecb.aclose()
        await snb.aclose()

    assert persisted["m1"] == 1
    row = mem_session.query(M1Row).filter(M1Row.country_code == "CH").one()
    flags = (row.flags or "").split(",")
    assert "CH_POLICY_RATE_SNB_NATIVE" in flags
    assert "CH_POLICY_RATE_SNB_NATIVE_MONTHLY" in flags
    assert "CH_POLICY_RATE_TE_PRIMARY" not in flags
    assert "CH_POLICY_RATE_FRED_FALLBACK_STALE" not in flags
    # Key invariant: SNB-native monthly is NOT stale-flagged.
    assert "CALIBRATION_STALE" not in flags


async def test_daily_monetary_ch_fred_fallback_when_te_and_snb_absent(
    mem_session: Session,
    fred_api_key: str,
    tmp_path: Path,
) -> None:
    """No TE, no SNB — CH cascade falls through to FRED with stale flags."""
    fred = FredConnector(api_key=fred_api_key, cache_dir=str(tmp_path / "fred"))
    cbo = CboConnector(fred=fred)
    ecb = EcbSdwConnector(cache_dir=str(tmp_path / "ecb"))
    try:
        monetary_builder = MonetaryInputsBuilder(fred=fred, cbo=cbo, ecb_sdw=ecb)
        inputs: MonetaryIndicesInputs = await build_live_monetary_inputs(
            "CH", POSITIVE_RATE_ANCHOR, builder=monetary_builder, history_years=2
        )
        results = compute_all_monetary_indices(inputs)
        persisted = persist_many_monetary_results(mem_session, results)
    finally:
        await fred.aclose()
        await ecb.aclose()

    assert persisted["m1"] == 1
    row = mem_session.query(M1Row).filter(M1Row.country_code == "CH").one()
    flags = (row.flags or "").split(",")
    assert "CH_POLICY_RATE_FRED_FALLBACK_STALE" in flags
    assert "CALIBRATION_STALE" in flags
    assert "CH_POLICY_RATE_TE_PRIMARY" not in flags
    assert "CH_POLICY_RATE_SNB_NATIVE" not in flags


async def test_daily_monetary_ch_te_primary_preserves_negative_rate_history(
    fred_api_key: str,
    te_api_key: str,
    tmp_path: Path,
) -> None:
    """Historical negative-rate era: inputs payload surfaces the sign + flag.

    Asserts on ``inputs.m1`` (pre-compute) rather than a persisted row
    because at the 2020 anchor SNB was -0.75 % — the M1 compute
    correctly raises ``InsufficientDataError`` (spec §4 step 2 ZLB
    gate with no Krippner shadow-rate connector), so the DB row is
    intentionally absent. What Sprint V is validating here is that
    the CASCADE preserves the negative values and that
    ``CH_NEGATIVE_RATE_ERA_DATA`` fires — i.e., the connector + M1-
    builder contract holds across the negative-rate corridor. The
    M1-compute handling is a separate concern wired to the future
    Krippner connector (Phase 2+).
    """
    fred = FredConnector(api_key=fred_api_key, cache_dir=str(tmp_path / "fred"))
    cbo = CboConnector(fred=fred)
    ecb = EcbSdwConnector(cache_dir=str(tmp_path / "ecb"))
    snb = SNBConnector(cache_dir=str(tmp_path / "snb"))
    te = TEConnector(api_key=te_api_key, cache_dir=str(tmp_path / "te"))
    try:
        monetary_builder = MonetaryInputsBuilder(fred=fred, cbo=cbo, ecb_sdw=ecb, snb=snb, te=te)
        inputs: MonetaryIndicesInputs = await build_live_monetary_inputs(
            "CH", NEGATIVE_RATE_ANCHOR, builder=monetary_builder, history_years=3
        )
    finally:
        await fred.aclose()
        await ecb.aclose()
        await snb.aclose()
        await te.aclose()

    # M1 inputs must have been built despite the ZLB context.
    assert inputs.m1 is not None, (
        "M1 inputs must resolve even at negative policy rates — "
        "only the downstream compute step raises at ZLB."
    )
    flags = inputs.m1.upstream_flags
    # Historical-window negative-rate flag must fire on inputs.
    assert "CH_NEGATIVE_RATE_ERA_DATA" in flags
    assert "CH_POLICY_RATE_TE_PRIMARY" in flags
    # The 2020 anchor sits at SNB -0.75 %; assert the constructed
    # ``policy_rate_pct`` reflects that (tolerance ±0.25 pp to absorb
    # snap to the most recent rate-change announcement before anchor).
    assert inputs.m1.policy_rate_pct < 0, (
        f"expected negative policy rate at 2020 anchor; got {inputs.m1.policy_rate_pct!r}"
    )
    assert -0.0100 <= inputs.m1.policy_rate_pct <= -0.0050
    # Real-shadow-rate history must contain at least one strictly-negative
    # value — the 2020 window is entirely inside the -0.75 % corridor so
    # every monthly sample should be negative after the 1 % inflation
    # target is subtracted.
    assert any(r < 0 for r in inputs.m1.real_shadow_rate_history)
