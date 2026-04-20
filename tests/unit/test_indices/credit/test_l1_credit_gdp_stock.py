"""Behavioral tests for L1 Credit-to-GDP Stock per spec §7 fixtures."""

from __future__ import annotations

import json
from datetime import date

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from sonar.db.models import Base, CreditGdpStock
from sonar.db.persistence import DuplicatePersistError, persist_credit_gdp_stock_result
from sonar.indices.credit.l1_credit_gdp_stock import (
    METHODOLOGY_VERSION,
    CreditGdpStockInputs,
    classify_structural_band,
    compute_credit_gdp_stock,
)
from sonar.indices.exceptions import InsufficientInputsError


def _synth_history(mean_pct: float, sd_pct: float, n: int, seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    return rng.normal(loc=mean_pct, scale=sd_pct, size=n).tolist()


# ---------------------------------------------------------------------------
# Structural band classifier
# ---------------------------------------------------------------------------


def test_structural_band_sub_financialized() -> None:
    assert classify_structural_band(30.0) == "sub_financialized"
    assert classify_structural_band(49.9) == "sub_financialized"


def test_structural_band_intermediate() -> None:
    assert classify_structural_band(50.0) == "intermediate"
    assert classify_structural_band(98.0) == "intermediate"


def test_structural_band_advanced_economy_typical() -> None:
    assert classify_structural_band(100.0) == "advanced_economy_typical"
    assert classify_structural_band(145.0) == "advanced_economy_typical"
    assert classify_structural_band(149.9) == "advanced_economy_typical"


def test_structural_band_highly_financialized() -> None:
    assert classify_structural_band(150.0) == "highly_financialized"
    assert classify_structural_band(199.9) == "highly_financialized"


def test_structural_band_outlier() -> None:
    assert classify_structural_band(200.0) == "outlier"
    assert classify_structural_band(285.0) == "outlier"  # NL 2023-Q4


# ---------------------------------------------------------------------------
# Core compute path
# ---------------------------------------------------------------------------


def _pt_2024_q4() -> CreditGdpStockInputs:
    return CreditGdpStockInputs(
        country_code="PT",
        observation_date=date(2024, 12, 31),
        ratio_pct=136.1,
        ratio_pct_history=_synth_history(mean_pct=145.0, sd_pct=10.0, n=80, seed=1),
        series_variant="Q",
    )


def test_pt_2024_q4_happy_path() -> None:
    result = compute_credit_gdp_stock(_pt_2024_q4())
    assert result.methodology_version == METHODOLOGY_VERSION
    assert result.score_raw == pytest.approx(136.1)
    assert result.structural_band == "advanced_economy_typical"
    assert -5.0 <= result.score_normalized <= 5.0
    assert result.confidence == pytest.approx(1.0, abs=0.05)
    assert result.flags == ()


def test_nl_2023_q4_outlier_band() -> None:
    inputs = CreditGdpStockInputs(
        country_code="NL",
        observation_date=date(2023, 12, 31),
        ratio_pct=285.3,
        ratio_pct_history=_synth_history(mean_pct=260.0, sd_pct=15.0, n=80, seed=2),
    )
    result = compute_credit_gdp_stock(inputs)
    assert result.structural_band == "outlier"
    assert result.score_normalized > 0.5


def test_it_2024_q2_intermediate_band() -> None:
    inputs = CreditGdpStockInputs(
        country_code="IT",
        observation_date=date(2024, 6, 30),
        ratio_pct=95.8,
        ratio_pct_history=_synth_history(mean_pct=105.0, sd_pct=8.0, n=80, seed=3),
    )
    result = compute_credit_gdp_stock(inputs)
    assert result.structural_band == "intermediate"
    assert result.score_normalized < 0.0


# ---------------------------------------------------------------------------
# Flags
# ---------------------------------------------------------------------------


def test_f_fallback_flag() -> None:
    inputs = CreditGdpStockInputs(
        country_code="EE",
        observation_date=date(2024, 12, 31),
        ratio_pct=85.0,
        ratio_pct_history=_synth_history(mean_pct=80.0, sd_pct=10.0, n=80, seed=4),
        series_variant="F",
    )
    result = compute_credit_gdp_stock(inputs)
    assert "CREDIT_F_FALLBACK" in result.flags
    assert result.confidence <= 0.75


def test_credit_break_on_large_quarterly_jump() -> None:
    inputs = CreditGdpStockInputs(
        country_code="XX",
        observation_date=date(2024, 12, 31),
        ratio_pct=200.0,
        prior_ratio_pct=100.0,  # 100% jump → exceeds 50% threshold
        ratio_pct_history=_synth_history(mean_pct=150.0, sd_pct=20.0, n=80, seed=5),
    )
    result = compute_credit_gdp_stock(inputs)
    assert "CREDIT_BREAK" in result.flags
    assert result.confidence <= 0.85


def test_no_credit_break_on_normal_move() -> None:
    inputs = CreditGdpStockInputs(
        country_code="PT",
        observation_date=date(2024, 12, 31),
        ratio_pct=138.0,
        prior_ratio_pct=136.0,  # 1.5% jump → normal
        ratio_pct_history=_synth_history(mean_pct=145.0, sd_pct=10.0, n=80, seed=6),
    )
    result = compute_credit_gdp_stock(inputs)
    assert "CREDIT_BREAK" not in result.flags


def test_insufficient_history_flag() -> None:
    inputs = CreditGdpStockInputs(
        country_code="PT",
        observation_date=date(2024, 12, 31),
        ratio_pct=136.1,
        ratio_pct_history=_synth_history(mean_pct=140.0, sd_pct=10.0, n=30, seed=7),
    )
    result = compute_credit_gdp_stock(inputs)
    assert "INSUFFICIENT_HISTORY" in result.flags
    assert result.confidence <= 0.65


def test_upstream_flags_propagate() -> None:
    inputs = CreditGdpStockInputs(
        country_code="TR",
        observation_date=date(2024, 12, 31),
        ratio_pct=85.0,
        ratio_pct_history=_synth_history(mean_pct=80.0, sd_pct=15.0, n=80, seed=8),
        upstream_flags=("EM_COVERAGE", "STALE"),
    )
    result = compute_credit_gdp_stock(inputs)
    assert "EM_COVERAGE" in result.flags
    assert "STALE" in result.flags
    assert result.confidence <= 0.70


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_zero_ratio_raises() -> None:
    inputs = CreditGdpStockInputs(
        country_code="PT",
        observation_date=date(2024, 12, 31),
        ratio_pct=0.0,
        ratio_pct_history=_synth_history(145.0, 10.0, 80, 9),
    )
    with pytest.raises(InsufficientInputsError, match="ratio_pct"):
        compute_credit_gdp_stock(inputs)


def test_too_short_history_raises() -> None:
    inputs = CreditGdpStockInputs(
        country_code="PT",
        observation_date=date(2024, 12, 31),
        ratio_pct=136.1,
        ratio_pct_history=[145.0],
    )
    with pytest.raises(InsufficientInputsError, match="history"):
        compute_credit_gdp_stock(inputs)


def test_components_json_shape() -> None:
    result = compute_credit_gdp_stock(_pt_2024_q4())
    payload = json.loads(result.components_json)
    for key in (
        "credit_stock_lcu",
        "gdp_4q_sum_lcu",
        "ratio_pct",
        "series_variant",
        "gdp_vintage_mode",
        "rolling_mean_20y_pct",
        "rolling_std_20y_pct",
        "structural_band",
    ):
        assert key in payload


def test_zscore_clamped_at_5() -> None:
    # Engineered scenario: ratio wildly above history mean to force z > 5.
    inputs = CreditGdpStockInputs(
        country_code="XX",
        observation_date=date(2024, 12, 31),
        ratio_pct=500.0,
        ratio_pct_history=_synth_history(mean_pct=100.0, sd_pct=10.0, n=80, seed=10),
    )
    result = compute_credit_gdp_stock(inputs)
    assert result.score_normalized == 5.0


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def test_persist_single_row(session: Session) -> None:
    result = compute_credit_gdp_stock(_pt_2024_q4())
    persist_credit_gdp_stock_result(session, result)
    rows = session.query(CreditGdpStock).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.country_code == "PT"
    assert row.series_variant == "Q"
    assert row.structural_band == "advanced_economy_typical"


def test_persist_duplicate_raises(session: Session) -> None:
    result = compute_credit_gdp_stock(_pt_2024_q4())
    persist_credit_gdp_stock_result(session, result)
    with pytest.raises(DuplicatePersistError, match="already persisted"):
        persist_credit_gdp_stock_result(session, result)
