"""Behavioral tests for L4 DSR per spec §7 fixtures."""

from __future__ import annotations

import json
from datetime import date

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from sonar.db.models import Base, Dsr
from sonar.db.persistence import DuplicatePersistError, persist_dsr_result
from sonar.indices.credit.l4_dsr import (
    BIS_WS_DSR_UNIVERSE,
    METHODOLOGY_VERSION,
    DsrInputs,
    compute_dsr,
    resolve_band,
    resolve_formula_mode,
)
from sonar.indices.exceptions import InsufficientInputsError


def _synth_history(mean_pct: float, sd_pct: float, n: int, seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    return rng.normal(loc=mean_pct, scale=sd_pct, size=n).tolist()


# ---------------------------------------------------------------------------
# Coverage resolver
# ---------------------------------------------------------------------------


def test_bis_universe_includes_7_t1() -> None:
    for c in ("US", "DE", "PT", "IT", "ES", "FR", "NL"):
        assert c in BIS_WS_DSR_UNIVERSE


def test_resolve_full_mode_for_bis_country() -> None:
    assert (
        resolve_formula_mode(
            "US",
            has_lending_rate=True,
            has_maturity=True,
            has_debt_to_gdp=True,
        )
        == "full"
    )


def test_resolve_o2_for_non_bis_country_with_maturity() -> None:
    assert (
        resolve_formula_mode(
            "XX",
            has_lending_rate=True,
            has_maturity=True,
            has_debt_to_gdp=True,
        )
        == "o2"
    )


def test_resolve_o1_without_maturity() -> None:
    assert (
        resolve_formula_mode(
            "US",
            has_lending_rate=True,
            has_maturity=False,
            has_debt_to_gdp=True,
        )
        == "o1"
    )


def test_resolve_raises_without_lending_rate() -> None:
    with pytest.raises(InsufficientInputsError, match="lending_rate"):
        resolve_formula_mode(
            "US",
            has_lending_rate=False,
            has_maturity=True,
            has_debt_to_gdp=True,
        )


# ---------------------------------------------------------------------------
# Band classification
# ---------------------------------------------------------------------------


def test_band_baseline() -> None:
    assert resolve_band(-3.0) == "baseline"
    assert resolve_band(0.0) == "baseline"
    assert resolve_band(1.5) == "baseline"


def test_band_alert() -> None:
    assert resolve_band(2.0) == "alert"
    assert resolve_band(3.5) == "alert"
    assert resolve_band(5.9) == "alert"


def test_band_critical() -> None:
    assert resolve_band(6.0) == "critical"
    assert resolve_band(10.0) == "critical"


# ---------------------------------------------------------------------------
# Core compute path
# ---------------------------------------------------------------------------


def _pt_2024_q4_inputs(**overrides: object) -> DsrInputs:
    base: dict[str, object] = {
        "country_code": "PT",
        "observation_date": date(2024, 12, 31),
        "lending_rate_pct": 0.0345,
        "avg_maturity_years": 15.0,
        "debt_to_gdp_ratio": 1.329,
        "dsr_pct_history": _synth_history(mean_pct=13.0, sd_pct=1.5, n=80, seed=42),
        "segment": "PNFS",
    }
    base.update(overrides)
    return DsrInputs(**base)  # type: ignore[arg-type]


def test_pt_2024_q4_full_mode_band_baseline() -> None:
    result = compute_dsr(_pt_2024_q4_inputs())
    assert result.methodology_version == METHODOLOGY_VERSION
    assert result.formula_mode == "full"
    # DSR = annuity_factor(0.0345, 15) * 1.329 * 100 ≈ 0.0843 * 132.9 ≈ 11.2
    assert 10.0 <= result.dsr_pct <= 12.5
    # History mean ≈ 13, so dsr_deviation ≈ -1.7 → baseline
    assert result.band == "baseline"
    assert -5.0 <= result.score_normalized <= 5.0
    assert result.confidence == pytest.approx(1.0, abs=0.05)


def test_pt_2009_q4_critical_band() -> None:
    # PT 2009 Q4: peak debt-to-GDP ratio; synthesize high lending rate.
    inputs = _pt_2024_q4_inputs(
        observation_date=date(2009, 12, 31),
        lending_rate_pct=0.055,
        debt_to_gdp_ratio=1.95,
        dsr_pct_history=_synth_history(mean_pct=13.0, sd_pct=1.5, n=80, seed=42),
    )
    result = compute_dsr(inputs)
    # DSR ≈ annuity_factor(0.055, 15) * 195 ≈ 19.7, deviation vs 13 ~ +6.7 → critical
    assert result.dsr_pct > 18.0
    assert result.band == "critical"
    assert result.dsr_deviation_pp >= 6.0


def test_us_2024_q4_bis_direct_sanity() -> None:
    inputs = _pt_2024_q4_inputs(
        country_code="US",
        observation_date=date(2024, 6, 30),
        lending_rate_pct=0.045,
        avg_maturity_years=15.0,
        debt_to_gdp_ratio=1.451,
        dsr_pct_history=_synth_history(mean_pct=14.5, sd_pct=1.2, n=80, seed=51),
        bis_published_dsr_pct=14.5,
    )
    result = compute_dsr(inputs)
    assert result.formula_mode == "full"
    # Our computed DSR with i=4.5%, s=15, D/Y=1.451: af≈0.0933 * 1.451 *100≈13.5
    # BIS published 14.5 → diverge ~1pp; should be borderline flag.
    if "DSR_BIS_DIVERGE" in result.flags:
        assert abs(result.dsr_pct - 14.5) > 1.0
    else:
        assert abs(result.dsr_pct - 14.5) <= 1.0


def test_bis_diverge_flag_fires_on_large_mismatch() -> None:
    inputs = _pt_2024_q4_inputs(bis_published_dsr_pct=20.0)  # 9pp off
    result = compute_dsr(inputs)
    assert "DSR_BIS_DIVERGE" in result.flags
    assert result.confidence < 1.0


def test_bis_diverge_flag_absent_on_close_match() -> None:
    inputs = _pt_2024_q4_inputs(bis_published_dsr_pct=11.5)
    result = compute_dsr(inputs)
    assert "DSR_BIS_DIVERGE" not in result.flags


# ---------------------------------------------------------------------------
# Fallback paths
# ---------------------------------------------------------------------------


def test_fallback_o1_when_no_maturity() -> None:
    inputs = _pt_2024_q4_inputs(avg_maturity_years=None, country_code="XX")
    result = compute_dsr(inputs)
    assert result.formula_mode == "o1"
    assert "DSR_APPROX_O1" in result.flags
    # Interest-only: DSR = i * D/Y * 100 = 0.0345 * 1.329 * 100 ~ 4.58
    assert 4.0 <= result.dsr_pct <= 5.0
    assert result.confidence <= 0.90


def test_fallback_o2_non_bis_country() -> None:
    inputs = _pt_2024_q4_inputs(country_code="XX")
    result = compute_dsr(inputs)
    assert result.formula_mode == "o2"
    assert "DSR_APPROX_O2" in result.flags
    assert result.confidence <= 0.95


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_negative_rate_emits_flag() -> None:
    inputs = _pt_2024_q4_inputs(
        country_code="JP",
        lending_rate_pct=-0.001,
        avg_maturity_years=15.0,
    )
    result = compute_dsr(inputs)
    assert "DSR_NEG_RATE" in result.flags
    # Confidence takes -0.05 per flags.md §2.2 DSR_NEG_RATE
    assert result.confidence <= 0.96


def test_invalid_maturity_raises_in_full_mode() -> None:
    inputs = _pt_2024_q4_inputs(avg_maturity_years=-5.0)
    with pytest.raises(ValueError, match="maturity"):
        compute_dsr(inputs)


def test_zero_debt_ratio_raises() -> None:
    inputs = _pt_2024_q4_inputs(debt_to_gdp_ratio=0.0)
    with pytest.raises(InsufficientInputsError, match="debt_to_gdp_ratio"):
        compute_dsr(inputs)


def test_short_history_flag() -> None:
    inputs = _pt_2024_q4_inputs(
        dsr_pct_history=_synth_history(mean_pct=13.0, sd_pct=1.5, n=20, seed=42),
    )
    result = compute_dsr(inputs)
    assert "INSUFFICIENT_HISTORY" in result.flags
    assert result.confidence <= 0.65


def test_too_short_history_raises() -> None:
    inputs = _pt_2024_q4_inputs(dsr_pct_history=[13.0])
    with pytest.raises(InsufficientInputsError, match="history"):
        compute_dsr(inputs)


def test_hh_segment_with_gdp_denominator_flag() -> None:
    inputs = _pt_2024_q4_inputs(segment="HH", denominator="GDP_4Q_sum")
    result = compute_dsr(inputs)
    assert "DSR_DENOMINATOR_GDP" in result.flags


def test_components_json_shape() -> None:
    result = compute_dsr(_pt_2024_q4_inputs())
    payload = json.loads(result.components_json)
    for key in (
        "lending_rate_pct",
        "avg_maturity_years",
        "debt_to_gdp_ratio",
        "annuity_factor",
        "dsr_pct",
        "dsr_mean_20y_pct",
        "dsr_deviation_pp",
        "formula_mode",
        "segment",
    ):
        assert key in payload


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def test_persist_dsr_single_row(session: Session) -> None:
    result = compute_dsr(_pt_2024_q4_inputs())
    persist_dsr_result(session, result)
    rows = session.query(Dsr).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.country_code == "PT"
    assert row.segment == "PNFS"
    assert row.formula_mode == "full"
    assert row.band == "baseline"


def test_persist_dsr_duplicate_raises(session: Session) -> None:
    result = compute_dsr(_pt_2024_q4_inputs())
    persist_dsr_result(session, result)
    with pytest.raises(DuplicatePersistError, match="already persisted"):
        persist_dsr_result(session, result)


def test_persist_dsr_different_segment_allowed(session: Session) -> None:
    pnfs = compute_dsr(_pt_2024_q4_inputs(segment="PNFS"))
    hh = compute_dsr(_pt_2024_q4_inputs(segment="HH"))
    persist_dsr_result(session, pnfs)
    persist_dsr_result(session, hh)
    assert session.query(Dsr).count() == 2
