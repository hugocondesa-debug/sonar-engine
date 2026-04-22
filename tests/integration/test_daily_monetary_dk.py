"""Live integration — DK M1 TE-primary cascade (Sprint Y-DK C5).

Four @slow canaries that prove the DK Nationalbanken-connector
cascade end-to-end:

- ``test_daily_monetary_dk_te_primary`` — TE key set, full builder
  instantiation, anchor pinned to ``2024-12-31`` (Nationalbanken
  discount rate well above the spec-§4 ZLB threshold) so the full
  M1 compute succeeds; verifies ``DK_POLICY_RATE_TE_PRIMARY``
  lands on the persisted M1 row + the DK-specific
  ``DK_INFLATION_TARGET_IMPORTED_FROM_EA`` flag is present (vs the
  standard ``EXPECTED_INFLATION_CB_TARGET`` flag the other
  countries emit). M2 + M4 DK are wire-ready scaffolds (raise
  ``InsufficientDataError``) so only ``m1`` persists.
- ``test_daily_monetary_dk_nationalbanken_secondary_when_te_absent``
  — same 2024-12-31 anchor, TE handle omitted but Nationalbanken
  handle present; pipeline falls through to the public
  Statbank.dk ``DNRENTD/OIBNAA`` series and emits the
  ``DK_POLICY_RATE_NATIONALBANKEN_NATIVE`` flag with **no**
  ``*_MONTHLY`` cadence flag (matches the SE Riksbank pattern,
  contrast CH) and **no** ``CALIBRATION_STALE``. Note this routes
  to the actual EUR-peg-defence CD rate which is the active
  Nationalbanken policy instrument (vs the discount rate TE
  returns) — see retro §4 for the source-instrument divergence
  context.
- ``test_daily_monetary_dk_fred_fallback_when_te_and_nationalbanken_absent``
  — same 2024-12-31 anchor, no TE + no Nationalbanken handles;
  cascade falls through to the FRED OECD mirror
  ``IRSTCI01DKM156N`` (fresh at probe — ~4-month lag — so the
  full M1 compute succeeds against a real persisted row, unlike
  the SE FRED-fallback canary which had to assert pre-compute
  due to the SE mirror's discontinuation). Validates the
  ``DK_POLICY_RATE_FRED_FALLBACK_STALE`` + ``CALIBRATION_STALE``
  flag pair lands.
- ``test_daily_monetary_dk_te_primary_preserves_negative_rate_history``
  — Anchor pinned to ``2021-09-30`` (deep inside the brief
  2021-2022 discount-rate corridor at -0.60 %, the trough of TE's
  DEBRDISC view). Asserts on the cascade's **inputs**
  (``inputs.m1.upstream_flags`` + ``inputs.m1.policy_rate_pct``)
  rather than the persisted M1 row: at negative policy rates the
  M1-compute :func:`compute_m1_effective_rates` correctly raises
  ``InsufficientDataError`` (spec §4 step 2 ZLB gate — no Krippner
  shadow-rate connector wired at Sprint Y-DK scope, matching the
  Sprint V-CH / W-SE known gap). What we validate is the Sprint
  Y-DK promise: **negative values survive the cascade** and
  ``DK_NEGATIVE_RATE_ERA_DATA`` fires on the inputs payload.

All gated behind ``pytest -m slow`` and skipped when ``FRED_API_KEY``
is not set. The TE-primary tests additionally skip when ``TE_API_KEY``
is not set.
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
from sonar.connectors.nationalbanken import NationalbankenConnector
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


# Anchor deliberately pinned to a positive-rate post-normalisation
# level. Nationalbanken discount rate at 2024-12-31 was roughly
# 2.60 % (mid of the cutting cycle from 3.60 % H1 2024 to 1.60 % at
# probe time 2026-04). Picking a fixed historical date insulates the
# canaries from future Nationalbanken cuts that might bring the
# current rate closer to the spec-§4 ZLB threshold (0.5 %).
POSITIVE_RATE_ANCHOR: date = date(2024, 12, 31)

# Deep inside the TE-primary discount-rate dip 2021-03..2022-08
# (min -0.60 % at 2021-09-30 per Sprint Y-DK probe). Canary
# validates the cascade preserves the sign and surfaces
# DK_NEGATIVE_RATE_ERA_DATA on the inputs bundle. At this anchor
# the M1 compute itself correctly raises InsufficientDataError
# (ZLB without Krippner) so persistence returns zero rows —
# spec-correct behaviour, not a Sprint Y-DK regression. Mirrors the
# Sprint V-CH / W-SE negative-rate canary pattern.
NEGATIVE_RATE_ANCHOR: date = date(2021, 9, 30)


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


async def test_daily_monetary_dk_te_primary(
    mem_session: Session,
    fred_api_key: str,
    te_api_key: str,
    tmp_path: Path,
) -> None:
    """DK M1 pipeline with TE enabled — canonical daily-fresh DEBRDISC path."""
    fred = FredConnector(api_key=fred_api_key, cache_dir=str(tmp_path / "fred"))
    cbo = CboConnector(fred=fred)
    ecb = EcbSdwConnector(cache_dir=str(tmp_path / "ecb"))
    nationalbanken = NationalbankenConnector(cache_dir=str(tmp_path / "nationalbanken"))
    te = TEConnector(api_key=te_api_key, cache_dir=str(tmp_path / "te"))
    try:
        monetary_builder = MonetaryInputsBuilder(
            fred=fred, cbo=cbo, ecb_sdw=ecb, nationalbanken=nationalbanken, te=te
        )
        inputs: MonetaryIndicesInputs = await build_live_monetary_inputs(
            "DK", POSITIVE_RATE_ANCHOR, builder=monetary_builder, history_years=2
        )
        results = compute_all_monetary_indices(inputs)
        persisted = persist_many_monetary_results(mem_session, results)
    finally:
        await fred.aclose()
        await ecb.aclose()
        await nationalbanken.aclose()
        await te.aclose()

    assert persisted["m1"] == 1
    # M2 + M4 DK scaffolds raise InsufficientDataError — pipeline skips cleanly.
    assert persisted["m2"] == 0
    assert persisted["m4"] == 0
    row = mem_session.query(M1Row).filter(M1Row.country_code == "DK").one()
    flags = (row.flags or "").split(",")
    # TE-primary path — DK_POLICY_RATE_TE_PRIMARY must be present.
    assert "DK_POLICY_RATE_TE_PRIMARY" in flags
    # Neither native-secondary nor FRED fallback should land on the happy path.
    assert "DK_POLICY_RATE_NATIONALBANKEN_NATIVE" not in flags
    assert "DK_POLICY_RATE_FRED_FALLBACK_STALE" not in flags
    assert "CALIBRATION_STALE" not in flags
    # Cross-cutting DK flags — note imported_eur_peg convention.
    assert "R_STAR_PROXY" in flags
    assert "DK_INFLATION_TARGET_IMPORTED_FROM_EA" in flags
    # DK does NOT emit the standard EXPECTED_INFLATION_CB_TARGET
    # flag — the imported_eur_peg convention is the whole point.
    assert "EXPECTED_INFLATION_CB_TARGET" not in flags
    assert "DK_BS_GDP_PROXY_ZERO" in flags


async def test_daily_monetary_dk_nationalbanken_secondary_when_te_absent(
    mem_session: Session,
    fred_api_key: str,
    tmp_path: Path,
) -> None:
    """No TE, Nationalbanken handle present — cascade hits the Statbank.dk public API.

    This routes to the **CD rate (OIBNAA)** which is Nationalbanken's
    actual EUR-peg defence tool, not the discount rate (DEBRDISC →
    ODKNAA) that TE primary returns. The two diverged sharply across
    2014-2022 — see retro §4 for the source-instrument divergence
    context. Both representations are operationally valid; the
    cascade flag-emission contract makes the source observable.
    """
    fred = FredConnector(api_key=fred_api_key, cache_dir=str(tmp_path / "fred"))
    cbo = CboConnector(fred=fred)
    ecb = EcbSdwConnector(cache_dir=str(tmp_path / "ecb"))
    nationalbanken = NationalbankenConnector(cache_dir=str(tmp_path / "nationalbanken"))
    try:
        monetary_builder = MonetaryInputsBuilder(
            fred=fred, cbo=cbo, ecb_sdw=ecb, nationalbanken=nationalbanken
        )
        inputs: MonetaryIndicesInputs = await build_live_monetary_inputs(
            "DK", POSITIVE_RATE_ANCHOR, builder=monetary_builder, history_years=2
        )
        results = compute_all_monetary_indices(inputs)
        persisted = persist_many_monetary_results(mem_session, results)
    finally:
        await fred.aclose()
        await ecb.aclose()
        await nationalbanken.aclose()

    assert persisted["m1"] == 1
    row = mem_session.query(M1Row).filter(M1Row.country_code == "DK").one()
    flags = (row.flags or "").split(",")
    assert "DK_POLICY_RATE_NATIONALBANKEN_NATIVE" in flags
    # Daily-cadence native — no *_MONTHLY cadence flag (matches
    # SE Riksbank pattern, contrast CH SNB monthly secondary).
    assert "DK_POLICY_RATE_NATIONALBANKEN_NATIVE_MONTHLY" not in flags
    assert "DK_POLICY_RATE_TE_PRIMARY" not in flags
    assert "DK_POLICY_RATE_FRED_FALLBACK_STALE" not in flags
    # Key invariant: Nationalbanken-native daily is NOT stale-flagged.
    assert "CALIBRATION_STALE" not in flags
    # EUR-peg-imported target flag still fires on the secondary path.
    assert "DK_INFLATION_TARGET_IMPORTED_FROM_EA" in flags


async def test_daily_monetary_dk_fred_fallback_when_te_and_nationalbanken_absent(
    mem_session: Session,
    fred_api_key: str,
    tmp_path: Path,
) -> None:
    """No TE, no Nationalbanken — DK cascade falls through to FRED with stale flags.

    Unlike the SE FRED-fallback canary (which has to assert
    pre-compute because the SE FRED mirror was discontinued at
    2020-10-01), the DK FRED OECD mirror is fresh at probe
    (~4-month lag) so a 2024-12-31 anchor returns a recent FRED
    observation well above the spec-§4 ZLB threshold and the full
    M1 compute succeeds against a persisted row.
    """
    fred = FredConnector(api_key=fred_api_key, cache_dir=str(tmp_path / "fred"))
    cbo = CboConnector(fred=fred)
    ecb = EcbSdwConnector(cache_dir=str(tmp_path / "ecb"))
    try:
        monetary_builder = MonetaryInputsBuilder(fred=fred, cbo=cbo, ecb_sdw=ecb)
        inputs: MonetaryIndicesInputs = await build_live_monetary_inputs(
            "DK", POSITIVE_RATE_ANCHOR, builder=monetary_builder, history_years=2
        )
        results = compute_all_monetary_indices(inputs)
        persisted = persist_many_monetary_results(mem_session, results)
    finally:
        await fred.aclose()
        await ecb.aclose()

    assert persisted["m1"] == 1
    row = mem_session.query(M1Row).filter(M1Row.country_code == "DK").one()
    flags = (row.flags or "").split(",")
    assert "DK_POLICY_RATE_FRED_FALLBACK_STALE" in flags
    assert "CALIBRATION_STALE" in flags
    assert "DK_POLICY_RATE_TE_PRIMARY" not in flags
    assert "DK_POLICY_RATE_NATIONALBANKEN_NATIVE" not in flags
    # EUR-peg-imported target flag still fires on the FRED-fallback path.
    assert "DK_INFLATION_TARGET_IMPORTED_FROM_EA" in flags


async def test_daily_monetary_dk_te_primary_preserves_negative_rate_history(
    fred_api_key: str,
    te_api_key: str,
    tmp_path: Path,
) -> None:
    """Historical negative-rate era: inputs payload surfaces the sign + flag.

    Asserts on ``inputs.m1`` (pre-compute) rather than a persisted row
    because at the 2021-09-30 anchor the Nationalbanken discount rate
    was -0.60 % — the M1 compute correctly raises
    ``InsufficientDataError`` (spec §4 step 2 ZLB gate with no
    Krippner shadow-rate connector), so the DB row is intentionally
    absent. What Sprint Y-DK is validating here is that the CASCADE
    preserves the negative values and that ``DK_NEGATIVE_RATE_ERA_DATA``
    fires — i.e., the connector + M1-builder contract holds across
    the negative-rate corridor. Mirrors the Sprint V-CH / W-SE
    negative-rate canary pattern.

    Note: TE returns the discount rate (DEBRDISC) which only briefly
    dipped negative 2021-2022 (18 obs, min -0.60 %). The
    Nationalbanken-native cascade slot would surface the deeper
    -0.75 % CD-rate (OIBNAA) corridor across the longer 2015-2022
    EUR-peg-defence window — captured separately in C2's slow canary.
    """
    fred = FredConnector(api_key=fred_api_key, cache_dir=str(tmp_path / "fred"))
    cbo = CboConnector(fred=fred)
    ecb = EcbSdwConnector(cache_dir=str(tmp_path / "ecb"))
    nationalbanken = NationalbankenConnector(cache_dir=str(tmp_path / "nationalbanken"))
    te = TEConnector(api_key=te_api_key, cache_dir=str(tmp_path / "te"))
    try:
        monetary_builder = MonetaryInputsBuilder(
            fred=fred, cbo=cbo, ecb_sdw=ecb, nationalbanken=nationalbanken, te=te
        )
        inputs: MonetaryIndicesInputs = await build_live_monetary_inputs(
            "DK", NEGATIVE_RATE_ANCHOR, builder=monetary_builder, history_years=2
        )
    finally:
        await fred.aclose()
        await ecb.aclose()
        await nationalbanken.aclose()
        await te.aclose()

    # M1 inputs must have been built despite the ZLB context.
    assert inputs.m1 is not None, (
        "M1 inputs must resolve even at negative policy rates — "
        "only the downstream compute step raises at ZLB."
    )
    flags = inputs.m1.upstream_flags
    # Historical-window negative-rate flag must fire on inputs.
    assert "DK_NEGATIVE_RATE_ERA_DATA" in flags
    assert "DK_POLICY_RATE_TE_PRIMARY" in flags
    # The 2021-09-30 anchor sits at Nationalbanken discount rate
    # -0.60 %; assert the constructed ``policy_rate_pct`` reflects
    # that (tolerance ±0.30 pp to absorb snap to the most recent
    # rate-change announcement before anchor — TE only records
    # discrete rate-change observations).
    assert inputs.m1.policy_rate_pct < 0, (
        f"expected negative policy rate at 2021-09-30 anchor; got {inputs.m1.policy_rate_pct!r}"
    )
    assert -0.0090 <= inputs.m1.policy_rate_pct <= -0.0030
