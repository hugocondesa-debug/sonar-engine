"""Sprint F integration — M2 full-compute smoke for 10 non-EA T1 countries.

@slow canary that proves the full Sprint F flip end-to-end: TE CPI
wrappers + TE inflation-forecast wrappers + OECD EO output-gap +
Sprint I-patch family policy-rate cascades all wire through the
:class:`MonetaryInputsBuilder` facade into a single
:meth:`build_m2_inputs` call per country.

Coverage: US (canonical CBO path) + 9 Sprint F builders
(CA/AU/NZ/CH/SE/NO/DK/GB/JP). EA + per-country EA members are
deferred under CAL-M2-EA-PER-COUNTRY / CAL-M2-EA-AGGREGATE.

Gated behind ``@pytest.mark.slow`` + skipped when ``TE_API_KEY`` or
``FRED_API_KEY`` are absent. Wall-clock target ≤ 90s combined across
all countries. Implementation reuses the per-country M1 test pattern
(TE + FRED handles only — native-CB secondaries omitted to keep the
wall-clock tractable; M1 tests cover those in depth).
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
from sonar.connectors.oecd_eo import OECDEOConnector
from sonar.connectors.te import TEConnector
from sonar.db.models import Base
from sonar.indices.monetary.builders import MonetaryInputsBuilder
from sonar.pipelines.daily_monetary_indices import (
    _classify_m2_compute_mode,
    build_live_monetary_inputs,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.slow


@pytest.fixture
def te_api_key() -> str:
    key = os.environ.get("TE_API_KEY")
    if not key:
        pytest.skip("TE_API_KEY not set")
    return key


@pytest.fixture
def fred_api_key() -> str:
    key = os.environ.get("FRED_API_KEY")
    if not key:
        pytest.skip("FRED_API_KEY not set")
    return key


@pytest.fixture
def anchor() -> date:
    return datetime.now(tz=UTC).date() - timedelta(days=14)


@pytest.fixture
def mem_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


# ---------------------------------------------------------------------------
# Per-country M2 full-compute assertions for the 9 Sprint F builders.
# Parametrised so a single test run surfaces which countries flake.
# US canonical path covered in a dedicated test below (different builder
# signature — CBO primary, no TE / OECD EO).
# ---------------------------------------------------------------------------


_SPRINT_F_T1_COUNTRIES = ("CA", "AU", "NZ", "CH", "SE", "NO", "DK", "GB", "JP")


@pytest.mark.parametrize("country", _SPRINT_F_T1_COUNTRIES)
async def test_m2_full_compute_live_smoke(
    country: str,
    te_api_key: str,
    fred_api_key: str,
    anchor: date,
    tmp_path: Path,
    mem_session: Session,
) -> None:
    """Each Sprint F country builds M2 live and emits FULL or PARTIAL mode."""
    fred = FredConnector(api_key=fred_api_key, cache_dir=str(tmp_path / "fred"))
    cbo = CboConnector(fred=fred)
    ecb = EcbSdwConnector(cache_dir=str(tmp_path / "ecb"))
    te = TEConnector(api_key=te_api_key, cache_dir=str(tmp_path / "te"))
    oecd = OECDEOConnector(cache_dir=str(tmp_path / "oecd_eo"))
    try:
        monetary_builder = MonetaryInputsBuilder(
            fred=fred, cbo=cbo, ecb_sdw=ecb, te=te, oecd_eo=oecd
        )
        inputs = await build_live_monetary_inputs(
            country, anchor, builder=monetary_builder, history_years=2
        )
    finally:
        await fred.aclose()
        await ecb.aclose()
        await te.aclose()
        await oecd.aclose()

    assert inputs.m2 is not None, f"M2 {country} did not compute on {anchor}"
    mode = _classify_m2_compute_mode(inputs.m2.upstream_flags)
    assert mode in ("FULL", "PARTIAL"), (
        f"M2 {country} mode={mode!r} on {anchor} — expected FULL or PARTIAL. "
        f"Flags: {inputs.m2.upstream_flags}"
    )
    # Minimum invariants per Sprint F flag contract.
    assert any(f == f"{country}_M2_CPI_TE_LIVE" for f in inputs.m2.upstream_flags), (
        f"Missing {country}_M2_CPI_TE_LIVE flag"
    )
    assert any(f == f"{country}_M2_OUTPUT_GAP_OECD_EO_LIVE" for f in inputs.m2.upstream_flags), (
        f"Missing {country}_M2_OUTPUT_GAP_OECD_EO_LIVE flag"
    )
    # Unit sanity: policy rate is in decimal (e.g., 0.025 = 2.5 %); always < 0.20.
    assert -0.02 <= inputs.m2.policy_rate_pct <= 0.20
    # Inflation YoY bound — modern decimal.
    assert -0.05 <= inputs.m2.inflation_yoy_pct <= 0.20
    # Output gap in percentage points — modern T1 stays within +- 15.
    assert -15.0 <= inputs.m2.output_gap_pct <= 15.0


async def test_m2_us_canonical_preserved(
    te_api_key: str,
    fred_api_key: str,
    anchor: date,
    tmp_path: Path,
    mem_session: Session,
) -> None:
    """HALT-2 regression guard: US M2 still computes via CBO-primary path.

    Sprint F must not drift US M2 off the canonical CBO GDPPOT +
    FRED fed-funds + PCE-core path. Asserts:

    - build_m2_inputs("US", ...) succeeds with output_gap_source == "CBO".
    - source_connector == ("fred", "cbo") — TE + OECD EO do not appear.
    - Sprint F country-specific flags do not leak into US compute.
    """
    fred = FredConnector(api_key=fred_api_key, cache_dir=str(tmp_path / "fred"))
    cbo = CboConnector(fred=fred)
    ecb = EcbSdwConnector(cache_dir=str(tmp_path / "ecb"))
    # Instantiate TE + OECD EO but prove they're not invoked for US.
    te = TEConnector(api_key="unused-in-us-path", cache_dir=str(tmp_path / "te"))
    oecd = OECDEOConnector(cache_dir=str(tmp_path / "oecd_eo"))
    try:
        monetary_builder = MonetaryInputsBuilder(
            fred=fred, cbo=cbo, ecb_sdw=ecb, te=te, oecd_eo=oecd
        )
        inputs = await build_live_monetary_inputs(
            "US", anchor, builder=monetary_builder, history_years=2
        )
    finally:
        await fred.aclose()
        await ecb.aclose()
        await te.aclose()
        await oecd.aclose()

    assert inputs.m2 is not None, f"US M2 did not compute on {anchor}"
    assert inputs.m2.output_gap_source == "CBO"
    assert inputs.m2.source_connector == ("fred", "cbo")
    for flag in inputs.m2.upstream_flags:
        assert not flag.startswith(
            ("US_M2_CPI_TE_LIVE", "US_M2_FULL_COMPUTE_LIVE", "US_M2_OUTPUT_GAP_OECD_EO_LIVE")
        ), f"Sprint F flag leaked into US canonical compute: {flag!r}"
    assert _classify_m2_compute_mode(inputs.m2.upstream_flags) == "LEGACY"


# ---------------------------------------------------------------------------
# Sprint L — EA aggregate M2 live canary (CAL-M2-EA-AGGREGATE)
# ---------------------------------------------------------------------------


async def test_m2_ea_aggregate_full_compute_live_sprint_l(
    te_api_key: str,
    fred_api_key: str,
    anchor: date,
    tmp_path: Path,
    mem_session: Session,
) -> None:
    """Sprint L live canary — EA aggregate builds FULL_COMPUTE_LIVE.

    Exercises the complete EA M2 Taylor-gap path end-to-end via the
    MonetaryInputsBuilder facade:
    - ECB SDW DFR (policy rate)
    - TE \\`fetch_ea_hicp_yoy\\` (ECCPEMUY — Eurostat Monetary Union HICP)
    - TE \\`fetch_ea_inflation_forecast\\` (q4 ≈ 12m-ahead horizon)
    - OECD EO EA17 aggregate output gap
    """
    fred = FredConnector(api_key=fred_api_key, cache_dir=str(tmp_path / "fred"))
    cbo = CboConnector(fred=fred)
    ecb = EcbSdwConnector(cache_dir=str(tmp_path / "ecb"))
    te = TEConnector(api_key=te_api_key, cache_dir=str(tmp_path / "te"))
    oecd = OECDEOConnector(cache_dir=str(tmp_path / "oecd_eo"))
    try:
        monetary_builder = MonetaryInputsBuilder(
            fred=fred, cbo=cbo, ecb_sdw=ecb, te=te, oecd_eo=oecd
        )
        inputs = await build_live_monetary_inputs(
            "EA", anchor, builder=monetary_builder, history_years=2
        )
    finally:
        await fred.aclose()
        await ecb.aclose()
        await te.aclose()
        await oecd.aclose()

    assert inputs.m2 is not None, f"EA M2 did not compute on {anchor}"
    mode = _classify_m2_compute_mode(inputs.m2.upstream_flags)
    assert mode == "FULL", (
        f"EA M2 mode={mode!r} on {anchor} — expected FULL. Flags: {inputs.m2.upstream_flags}"
    )
    assert "EA_M2_POLICY_RATE_ECB_DFR_LIVE" in inputs.m2.upstream_flags
    assert "EA_M2_CPI_TE_LIVE" in inputs.m2.upstream_flags
    assert "EA_M2_INFLATION_FORECAST_TE_LIVE" in inputs.m2.upstream_flags
    assert "EA_M2_OUTPUT_GAP_OECD_EO_LIVE" in inputs.m2.upstream_flags
    assert "EA_M2_FULL_COMPUTE_LIVE" in inputs.m2.upstream_flags
    # Source identity: EA aggregate must route ECB DFR (not FRED / CBO).
    assert inputs.m2.source_connector[0] == "ecb_sdw"
    assert "te" in inputs.m2.source_connector
    assert "oecd_eo" in inputs.m2.source_connector
    assert "fred" not in inputs.m2.source_connector
    assert "cbo" not in inputs.m2.source_connector
    # Output gap tagged OECD_EO (EA17 mapping from Sprint C).
    assert inputs.m2.output_gap_source == "OECD_EO"
    # Unit sanity: policy rate decimal in [-0.02, 0.20].
    assert -0.02 <= inputs.m2.policy_rate_pct <= 0.20
    # HICP YoY decimal bound — EA has stayed well inside [-0.02, 0.15]
    # across the full 1991-2026 window (2022 peak ~0.106).
    assert -0.02 <= inputs.m2.inflation_yoy_pct <= 0.15
    # Output gap in pp — EA17 modern range roughly +- 10.
    assert -15.0 <= inputs.m2.output_gap_pct <= 15.0
