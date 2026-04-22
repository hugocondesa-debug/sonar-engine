"""Live integration — SE M1 TE-primary cascade (Sprint W-SE C5).

Four @slow canaries that prove the SE Riksbank-connector cascade
end-to-end:

- ``test_daily_monetary_se_te_primary`` — TE key set, full builder
  instantiation, anchor pinned to ``2024-12-31`` (Riksbank policy
  rate 2.50 % — post-normalisation level well above the ZLB
  threshold) so the full M1 compute succeeds; verifies
  ``SE_POLICY_RATE_TE_PRIMARY`` lands on the persisted M1 row and no
  staleness flag is present. M2 + M4 SE are wire-ready scaffolds
  (raise ``InsufficientDataError``) so only ``m1`` persists.
- ``test_daily_monetary_se_riksbank_secondary_when_te_absent`` — same
  2024-12-31 anchor, TE handle omitted but Riksbank handle present;
  pipeline falls through to the public Swea ``SECBREPOEFF`` series
  and emits the ``SE_POLICY_RATE_RIKSBANK_NATIVE`` flag with **no**
  ``*_MONTHLY`` cadence flag (contrast CH) and **no**
  ``CALIBRATION_STALE``. Parallels CA (Sprint S), AU (Sprint T), CH
  (Sprint V): secondary slot is a first-class reachable public
  endpoint. Unique to SE: the native is daily-cadence matching the
  TE primary, so the flag pair carries one element not two.
- ``test_daily_monetary_se_fred_fallback_when_te_and_riksbank_absent``
  — anchor pinned to ``2020-08-31`` (inside the FRED SE mirror
  availability window; the mirror was observed discontinued at
  2020-10-01 per the Sprint W-SE probe so any anchor whose 2y
  history ends after 2022-10-01 returns an empty FRED payload). The
  2020-08-31 anchor sits inside the Riksbank 0 % plateau (below the
  spec-§4 ZLB threshold) so the **downstream M1 compute raises** —
  the canary therefore asserts on ``inputs.m1.upstream_flags``
  rather than a persisted row (pattern mirrors the
  ``NEGATIVE_RATE_ANCHOR`` canary + Sprint V-CH's negative-rate
  canary). Validates that the FRED fallback path resolves + emits
  the ``SE_POLICY_RATE_FRED_FALLBACK_STALE`` + ``CALIBRATION_STALE``
  flag pair. The absence of any SE anchor where both (a) FRED has
  data and (b) the Riksbank rate is above ZLB is the Sprint W-SE
  known gap (retro §11) — a consequence of the FRED series ending in
  Oct 2020 and the Riksbank staying at ≤ 0.25 % throughout the FRED-
  live window.
- ``test_daily_monetary_se_te_primary_preserves_negative_rate_history``
  — Anchor pinned to ``2017-12-31`` (deep inside the 2015-2019
  Riksbank negative-rate corridor at -0.50 %). Asserts on the
  cascade's **inputs** (``inputs.m1.upstream_flags`` +
  ``inputs.m1.policy_rate_pct``) rather than the persisted M1 row:
  at negative policy rates the M1-compute
  :func:`compute_m1_effective_rates` correctly raises
  ``InsufficientDataError`` (spec §4 step 2 ZLB gate — no Krippner
  shadow-rate connector wired at Sprint W-SE scope, matching the
  Sprint V-CH known gap) so the DB row is intentionally absent. What
  we validate is the Sprint W-SE promise: **negative values survive
  the cascade** and ``SE_NEGATIVE_RATE_ERA_DATA`` fires on the
  inputs payload. Pattern identical to the Sprint V-CH canary but
  with the SE-specific flag name.

All gated behind ``pytest -m slow`` and skipped when ``FRED_API_KEY``
is not set. The TE-primary tests additionally skip when ``TE_API_KEY``
is not set. Pattern mirrors ``test_daily_monetary_au.py`` /
``test_daily_monetary_ca.py`` / ``test_daily_monetary_jp.py`` /
``test_daily_monetary_ch.py`` so regressions are easy to spot across
the six-country cascade family.
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
from sonar.connectors.riksbank import RiksbankConnector
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


# Anchor deliberately pinned to a post-normalisation positive-rate
# level. Riksbank policy rate at 2024-12-31 was around 2.50 % — the
# mid-point of the 2024 cutting cycle that started from 4.00 % in
# Q1 2024 and ended 2026 at 1.75 %. Picking a fixed date (rather
# than today-14d) insulates the canaries from future Riksbank cuts
# that might bring the current rate closer to the ZLB threshold
# (0.5 %). Above ZLB the full M1 compute exercises cleanly. The
# negative-rate canary uses a different anchor (see below) to
# exercise the historical-negative-rate path.
POSITIVE_RATE_ANCHOR: date = date(2024, 12, 31)

# Deep inside the Riksbank negative-rate corridor (2015-02-12 →
# 2019-11-30 with a floor at -0.50 % from Feb 2016 → Dec 2018). End
# of 2017 sits cleanly in the -0.50 % regime. Canary validates that
# the cascade preserves the sign and surfaces
# SE_NEGATIVE_RATE_ERA_DATA on the inputs bundle. At this anchor the
# M1 compute itself correctly raises InsufficientDataError (ZLB
# without Krippner) so persistence returns zero rows — spec-correct
# behaviour, not a Sprint W-SE regression. Mirrors the Sprint V-CH
# 2020-12-15 canary pattern.
NEGATIVE_RATE_ANCHOR: date = date(2017, 12, 31)

# Pinned inside the intersection of (a) the FRED OECD SE mirror
# availability window and (b) a realistic Riksbank decision date.
# The FRED mirror is frozen at its 2020-10-01 last observation
# (Sprint W-SE probe) so any 2y-history window whose **end** is
# after 2022-10-01 returns an empty FRED payload and the cascade
# raises; anchoring at 2020-08-31 keeps the FRED window alive. The
# Riksbank rate was 0 % at this anchor (post the 2019-12-19 lift-off
# from -0.25 %) so the downstream M1 compute still raises at the
# spec-§4 ZLB threshold (0.5 %); this canary therefore asserts on
# inputs.m1 rather than the persisted row (pattern mirrors the
# NEGATIVE_RATE_ANCHOR canary and the Sprint V-CH FRED-fallback
# flag-emission test).
FRED_FALLBACK_ANCHOR: date = date(2020, 8, 31)


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


async def test_daily_monetary_se_te_primary(
    mem_session: Session,
    fred_api_key: str,
    te_api_key: str,
    tmp_path: Path,
) -> None:
    """SE M1 pipeline with TE enabled — canonical daily-fresh Riksbank path."""
    fred = FredConnector(api_key=fred_api_key, cache_dir=str(tmp_path / "fred"))
    cbo = CboConnector(fred=fred)
    ecb = EcbSdwConnector(cache_dir=str(tmp_path / "ecb"))
    riksbank = RiksbankConnector(cache_dir=str(tmp_path / "riksbank"))
    te = TEConnector(api_key=te_api_key, cache_dir=str(tmp_path / "te"))
    try:
        monetary_builder = MonetaryInputsBuilder(
            fred=fred, cbo=cbo, ecb_sdw=ecb, riksbank=riksbank, te=te
        )
        inputs: MonetaryIndicesInputs = await build_live_monetary_inputs(
            "SE", POSITIVE_RATE_ANCHOR, builder=monetary_builder, history_years=2
        )
        results = compute_all_monetary_indices(inputs)
        persisted = persist_many_monetary_results(mem_session, results)
    finally:
        await fred.aclose()
        await ecb.aclose()
        await riksbank.aclose()
        await te.aclose()

    assert persisted["m1"] == 1
    # M2 + M4 SE scaffolds raise InsufficientDataError — pipeline skips cleanly.
    assert persisted["m2"] == 0
    assert persisted["m4"] == 0
    row = mem_session.query(M1Row).filter(M1Row.country_code == "SE").one()
    flags = (row.flags or "").split(",")
    # TE-primary path — SE_POLICY_RATE_TE_PRIMARY must be present.
    assert "SE_POLICY_RATE_TE_PRIMARY" in flags
    # Neither native-secondary nor FRED fallback should land on the happy path.
    assert "SE_POLICY_RATE_RIKSBANK_NATIVE" not in flags
    assert "SE_POLICY_RATE_FRED_FALLBACK_STALE" not in flags
    assert "CALIBRATION_STALE" not in flags
    # Cross-cutting SE flags.
    assert "R_STAR_PROXY" in flags
    assert "EXPECTED_INFLATION_CB_TARGET" in flags
    # No band flag — Riksbank publishes a clean 2 % CPIF point target.
    assert "SE_INFLATION_TARGET_BAND" not in flags
    assert "SE_BS_GDP_PROXY_ZERO" in flags


async def test_daily_monetary_se_riksbank_secondary_when_te_absent(
    mem_session: Session,
    fred_api_key: str,
    tmp_path: Path,
) -> None:
    """No TE, Riksbank handle present — cascade hits the public Swea API."""
    fred = FredConnector(api_key=fred_api_key, cache_dir=str(tmp_path / "fred"))
    cbo = CboConnector(fred=fred)
    ecb = EcbSdwConnector(cache_dir=str(tmp_path / "ecb"))
    riksbank = RiksbankConnector(cache_dir=str(tmp_path / "riksbank"))
    try:
        monetary_builder = MonetaryInputsBuilder(fred=fred, cbo=cbo, ecb_sdw=ecb, riksbank=riksbank)
        inputs: MonetaryIndicesInputs = await build_live_monetary_inputs(
            "SE", POSITIVE_RATE_ANCHOR, builder=monetary_builder, history_years=2
        )
        results = compute_all_monetary_indices(inputs)
        persisted = persist_many_monetary_results(mem_session, results)
    finally:
        await fred.aclose()
        await ecb.aclose()
        await riksbank.aclose()

    assert persisted["m1"] == 1
    row = mem_session.query(M1Row).filter(M1Row.country_code == "SE").one()
    flags = (row.flags or "").split(",")
    assert "SE_POLICY_RATE_RIKSBANK_NATIVE" in flags
    # Daily-cadence native — no *_MONTHLY cadence flag (contrast CH).
    assert "SE_POLICY_RATE_RIKSBANK_NATIVE_MONTHLY" not in flags
    assert "SE_POLICY_RATE_TE_PRIMARY" not in flags
    assert "SE_POLICY_RATE_FRED_FALLBACK_STALE" not in flags
    # Key invariant: Riksbank-native daily is NOT stale-flagged.
    assert "CALIBRATION_STALE" not in flags


async def test_daily_monetary_se_fred_fallback_when_te_and_riksbank_absent(
    fred_api_key: str,
    tmp_path: Path,
) -> None:
    """No TE, no Riksbank — SE cascade falls through to FRED with stale flags.

    **Sprint W-SE-specific anchor contortion**: the FRED OECD SE
    mirror (``IRSTCI01SEM156N``) was observed discontinued at
    2020-10-01 per the Sprint W-SE probe — ~5.5 years frozen. For the
    canary to exercise the FRED fallback path at all, the anchor must
    sit within the FRED-live window; ``FRED_FALLBACK_ANCHOR =
    2020-08-31`` does that (last FRED obs 2020-10-01 so a 2-year
    lookback from the anchor definitely returns data). But 2020-08
    sits inside the Riksbank 0 % plateau (post-2019-12-19 lift-off
    from -0.25 %) which is **below the spec-§4 ZLB threshold (0.5 %)**
    — so the downstream M1-compute raises
    ``InsufficientDataError`` and the DB row is intentionally absent.
    The canary validates the Sprint W-SE cascade contract: **FRED
    fallback path resolves + emits the expected staleness flag pair**
    on the ``inputs.m1`` bundle, mirroring the negative-rate canary
    pattern (assert on inputs, not persistence).

    There is **no SE anchor where both (a) FRED has data and (b) the
    Riksbank rate is above ZLB** — the full FRED-live window
    (1955-2020-10) is entirely inside the sub-ZLB regime for the
    Riksbank. This is the SE-specific known gap documented in the
    Sprint W-SE retrospective §11.
    """
    fred = FredConnector(api_key=fred_api_key, cache_dir=str(tmp_path / "fred"))
    cbo = CboConnector(fred=fred)
    ecb = EcbSdwConnector(cache_dir=str(tmp_path / "ecb"))
    try:
        monetary_builder = MonetaryInputsBuilder(fred=fred, cbo=cbo, ecb_sdw=ecb)
        inputs: MonetaryIndicesInputs = await build_live_monetary_inputs(
            "SE", FRED_FALLBACK_ANCHOR, builder=monetary_builder, history_years=2
        )
    finally:
        await fred.aclose()
        await ecb.aclose()

    # FRED fallback path must have resolved the cascade (not raised).
    assert inputs.m1 is not None, (
        "M1 inputs must resolve even when only the stale FRED mirror "
        "has data — only the downstream compute step raises at ZLB."
    )
    flags = inputs.m1.upstream_flags
    assert "SE_POLICY_RATE_FRED_FALLBACK_STALE" in flags
    assert "CALIBRATION_STALE" in flags
    assert "SE_POLICY_RATE_TE_PRIMARY" not in flags
    assert "SE_POLICY_RATE_RIKSBANK_NATIVE" not in flags
    assert inputs.m1.source_connector == ("fred",)


async def test_daily_monetary_se_te_primary_preserves_negative_rate_history(
    fred_api_key: str,
    te_api_key: str,
    tmp_path: Path,
) -> None:
    """Historical negative-rate era: inputs payload surfaces the sign + flag.

    Asserts on ``inputs.m1`` (pre-compute) rather than a persisted row
    because at the 2017 anchor Riksbank was -0.50 % — the M1 compute
    correctly raises ``InsufficientDataError`` (spec §4 step 2 ZLB
    gate with no Krippner shadow-rate connector), so the DB row is
    intentionally absent. What Sprint W-SE is validating here is that
    the CASCADE preserves the negative values and that
    ``SE_NEGATIVE_RATE_ERA_DATA`` fires — i.e., the connector +
    M1-builder contract holds across the negative-rate corridor.
    Mirrors the Sprint V-CH negative-rate canary pattern; the M1-
    compute handling is the same cross-country concern wired to the
    future Krippner connector (Phase 2+ scope).
    """
    fred = FredConnector(api_key=fred_api_key, cache_dir=str(tmp_path / "fred"))
    cbo = CboConnector(fred=fred)
    ecb = EcbSdwConnector(cache_dir=str(tmp_path / "ecb"))
    riksbank = RiksbankConnector(cache_dir=str(tmp_path / "riksbank"))
    te = TEConnector(api_key=te_api_key, cache_dir=str(tmp_path / "te"))
    try:
        monetary_builder = MonetaryInputsBuilder(
            fred=fred, cbo=cbo, ecb_sdw=ecb, riksbank=riksbank, te=te
        )
        inputs: MonetaryIndicesInputs = await build_live_monetary_inputs(
            "SE", NEGATIVE_RATE_ANCHOR, builder=monetary_builder, history_years=3
        )
    finally:
        await fred.aclose()
        await ecb.aclose()
        await riksbank.aclose()
        await te.aclose()

    # M1 inputs must have been built despite the ZLB context.
    assert inputs.m1 is not None, (
        "M1 inputs must resolve even at negative policy rates — "
        "only the downstream compute step raises at ZLB."
    )
    flags = inputs.m1.upstream_flags
    # Historical-window negative-rate flag must fire on inputs.
    assert "SE_NEGATIVE_RATE_ERA_DATA" in flags
    assert "SE_POLICY_RATE_TE_PRIMARY" in flags
    # The 2017 anchor sits at Riksbank -0.50 %; assert the constructed
    # ``policy_rate_pct`` reflects that (tolerance ±0.25 pp to absorb
    # snap to the most recent rate-change announcement before anchor).
    assert inputs.m1.policy_rate_pct < 0, (
        f"expected negative policy rate at 2017 anchor; got {inputs.m1.policy_rate_pct!r}"
    )
    assert -0.0075 <= inputs.m1.policy_rate_pct <= -0.0025
    # Real-shadow-rate history must contain at least one strictly-negative
    # value — the 2017 window is entirely inside the -0.50 % corridor so
    # every monthly sample should be negative after the 2 % CPIF target
    # is subtracted.
    assert any(r < 0 for r in inputs.m1.real_shadow_rate_history)
