"""Unit tests for daily_cost_of_capital compose_k_e + build helpers."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sonar.db.session  # noqa: F401 — register fk-on pragma listener
from sonar.connectors.damodaran import DamodaranMonthlyERPRow
from sonar.db.models import Base, ERPCanonical
from sonar.overlays.crp import CRPCanonical, build_canonical, compute_sov_spread
from sonar.overlays.erp import METHODOLOGY_VERSION_CANONICAL
from sonar.pipelines.daily_cost_of_capital import (
    COUNTRY_TO_CURRENCY,
    DAMODARAN_MATURE_ERP_BPS,
    DAMODARAN_MATURE_ERP_DECIMAL,
    T1_7_COUNTRIES,
    _lookup_erp_canonical,
    _MatureFallback,
    _normalize_country_code,
    _resolve_erp_bps,
    compose_k_e,
    resolve_mature_erp_fallback,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.orm import Session


def _make_crp(country: str, crp_bps: int, flags: tuple[str, ...] = ()) -> CRPCanonical:
    return CRPCanonical(
        crp_id=__import__("uuid").uuid4(),
        country_code=country,
        observation_date=date(2024, 1, 2),
        method_selected="SOV_SPREAD",
        crp_canonical_bps=crp_bps,
        default_spread_bps=crp_bps,
        vol_ratio=1.5,
        vol_ratio_source="damodaran_standard",
        crp_cds_bps=None,
        crp_sov_spread_bps=crp_bps,
        crp_rating_bps=None,
        basis_default_spread_sov_minus_cds_bps=None,
        confidence=0.9,
        flags=flags,
    )


class TestComposeKE:
    def test_us_benchmark_plus_erp_equals_rf_plus_erp(self) -> None:
        # US is benchmark → crp_canonical_bps = 0.
        crp = build_canonical(
            country_code="US",
            observation_date=date(2024, 1, 2),
            currency="USD",
        )
        rf = 0.04  # 4% nominal 10Y
        result = compose_k_e(
            country_code="US",
            observation_date=date(2024, 1, 2),
            rf_local_decimal=rf,
            crp=crp,
            beta=1.0,
        )
        # k_e = rf + 1.0 * 5.5% + 0% = 9.5%
        assert result.k_e_pct == pytest.approx(0.095)
        assert result.crp_bps == 0

    def test_pt_adds_crp_spread(self) -> None:
        # PT 10Y = 3.10%, DE 10Y = 2.13% → SOV spread ≈ 97 bps → CRP ≈ 146 bps
        sov = compute_sov_spread(
            country_code="PT",
            observation_date=date(2024, 1, 2),
            sov_yield_country_pct=0.0310,
            sov_yield_benchmark_pct=0.0213,
        )
        crp = build_canonical(
            country_code="PT",
            observation_date=date(2024, 1, 2),
            sov_spread=sov,
            currency="EUR",
        )
        result = compose_k_e(
            country_code="PT",
            observation_date=date(2024, 1, 2),
            rf_local_decimal=0.0310,
            crp=crp,
            beta=1.0,
        )
        # k_e = 3.10% + 5.50% + 1.46% ≈ 10.06%
        assert 0.095 <= result.k_e_pct <= 0.105
        assert result.crp_bps >= 100

    def test_beta_scaling(self) -> None:
        crp = _make_crp("PT", 146)
        result_b1 = compose_k_e(
            country_code="PT",
            observation_date=date(2024, 1, 2),
            rf_local_decimal=0.031,
            crp=crp,
            beta=1.0,
        )
        result_b2 = compose_k_e(
            country_code="PT",
            observation_date=date(2024, 1, 2),
            rf_local_decimal=0.031,
            crp=crp,
            beta=1.2,
        )
        # Delta should be 0.2 * ERP = 0.2 * 5.5% = 1.1%.
        assert result_b2.k_e_pct - result_b1.k_e_pct == pytest.approx(0.011, abs=1e-5)


class TestConstants:
    def test_damodaran_erp_55pct(self) -> None:
        assert DAMODARAN_MATURE_ERP_DECIMAL == 0.055
        assert DAMODARAN_MATURE_ERP_BPS == 550

    def test_t1_7_countries_complete(self) -> None:
        assert set(T1_7_COUNTRIES) == {"US", "DE", "PT", "IT", "ES", "FR", "NL"}

    def test_country_currency_mapping_complete(self) -> None:
        for c in T1_7_COUNTRIES:
            assert c in COUNTRY_TO_CURRENCY

    def test_gb_canonical_mapping_present(self) -> None:
        """ADR-0007: GB is the canonical ISO alpha-2 key for GBP."""
        assert COUNTRY_TO_CURRENCY["GB"] == "GBP"
        assert "UK" not in COUNTRY_TO_CURRENCY


class TestNormalizeCountryCode:
    def test_gb_canonical_is_passthrough(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert _normalize_country_code("GB") == "GB"
        captured = capsys.readouterr()
        assert "deprecated_country_alias" not in captured.out

    def test_us_canonical_is_passthrough(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert _normalize_country_code("US") == "US"
        captured = capsys.readouterr()
        assert "deprecated_country_alias" not in captured.out

    def test_uk_alias_resolves_to_gb_with_warning(self, capsys: pytest.CaptureFixture[str]) -> None:
        """ADR-0007: "UK" legacy alias resolves to "GB" + emits structlog warning."""
        assert _normalize_country_code("UK") == "GB"
        captured = capsys.readouterr()
        assert "deprecated_country_alias" in captured.out
        assert "alias=UK" in captured.out
        assert "canonical=GB" in captured.out


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _seed_erp_canonical(
    session: Session,
    market_index: str = "SPX",
    observation_date: date = date(2024, 1, 2),
    erp_median_bps: int = 472,
) -> None:
    import uuid  # noqa: PLC0415 — test-local

    row = ERPCanonical(
        erp_id=str(uuid.uuid4()),
        market_index=market_index,
        country_code="US",
        date=observation_date,
        methodology_version=METHODOLOGY_VERSION_CANONICAL,
        erp_median_bps=erp_median_bps,
        erp_range_bps=50,
        methods_available=4,
        erp_dcf_bps=480,
        erp_gordon_bps=465,
        erp_ey_bps=455,
        erp_cape_bps=495,
        forward_eps_divergence_pct=None,
        xval_deviation_bps=None,
        confidence=0.95,
        flags=None,
    )
    session.add(row)
    session.commit()


class TestErpLookup:
    def test_lookup_returns_none_on_empty_db(self, db_session: Session) -> None:
        assert _lookup_erp_canonical(db_session, "SPX", date(2024, 1, 2)) is None

    def test_lookup_returns_persisted_value(self, db_session: Session) -> None:
        _seed_erp_canonical(db_session, erp_median_bps=472)
        assert _lookup_erp_canonical(db_session, "SPX", date(2024, 1, 2)) == 472

    def test_lookup_returns_most_recent_when_multiple(self, db_session: Session) -> None:
        _seed_erp_canonical(db_session, observation_date=date(2023, 12, 15), erp_median_bps=400)
        _seed_erp_canonical(db_session, observation_date=date(2024, 1, 2), erp_median_bps=472)
        # Querying for 2024-01-10 should return the Jan 2 row (most recent on-or-before).
        assert _lookup_erp_canonical(db_session, "SPX", date(2024, 1, 10)) == 472


class TestResolveErpBps:
    def test_us_live_has_no_proxy_flag(self, db_session: Session) -> None:
        _seed_erp_canonical(db_session, erp_median_bps=472)
        bps, flags = _resolve_erp_bps(db_session, "US", date(2024, 1, 2))
        assert bps == 472
        assert flags == ()

    def test_pt_live_gets_proxy_flag(self, db_session: Session) -> None:
        _seed_erp_canonical(db_session, erp_median_bps=472)
        bps, flags = _resolve_erp_bps(db_session, "PT", date(2024, 1, 2))
        assert bps == 472
        assert flags == ("MATURE_ERP_PROXY_US",)

    def test_no_canonical_falls_back_to_stub(self, db_session: Session) -> None:
        bps, flags = _resolve_erp_bps(db_session, "US", date(2024, 1, 2))
        assert bps == DAMODARAN_MATURE_ERP_BPS
        assert "ERP_STUB" in flags


class TestComposeKEIntegratesErpFlags:
    def test_stub_flag_reduces_confidence(self) -> None:
        crp = build_canonical(
            country_code="US",
            observation_date=date(2024, 1, 2),
            currency="USD",
        )
        result = compose_k_e(
            country_code="US",
            observation_date=date(2024, 1, 2),
            rf_local_decimal=0.04,
            crp=crp,
            erp_mature_bps=DAMODARAN_MATURE_ERP_BPS,
            erp_flags=("ERP_STUB",),
        )
        assert "ERP_STUB" in result.flags
        # Base crp confidence 1.0 - 0.20 deduction for stub.
        assert result.confidence == pytest.approx(0.80)

    def test_proxy_flag_carried_through(self) -> None:
        crp = _make_crp("PT", 146)
        result = compose_k_e(
            country_code="PT",
            observation_date=date(2024, 1, 2),
            rf_local_decimal=0.031,
            crp=crp,
            erp_mature_bps=472,
            erp_flags=("MATURE_ERP_PROXY_US",),
        )
        assert "MATURE_ERP_PROXY_US" in result.flags
        # Proxy flag does not deduct confidence (only ERP_STUB does).
        assert result.confidence == pytest.approx(0.9)

    def test_live_erp_changes_k_e_vs_stub(self) -> None:
        crp = build_canonical(
            country_code="US",
            observation_date=date(2024, 1, 2),
            currency="USD",
        )
        stub = compose_k_e(
            country_code="US",
            observation_date=date(2024, 1, 2),
            rf_local_decimal=0.04,
            crp=crp,
            erp_mature_bps=DAMODARAN_MATURE_ERP_BPS,  # 550 bps
        )
        live = compose_k_e(
            country_code="US",
            observation_date=date(2024, 1, 2),
            rf_local_decimal=0.04,
            crp=crp,
            erp_mature_bps=472,
        )
        # 550 - 472 = 78 bps delta → 0.0078 lower k_e with live.
        assert stub.k_e_pct - live.k_e_pct == pytest.approx(0.0078, abs=1e-5)


# ---------------------------------------------------------------------------
# Week 10 Sprint B — Damodaran monthly live fallback wiring
# ---------------------------------------------------------------------------


def _mature_fallback(
    *, erp_decimal: float = 0.0417, source_file: str = "ERPFeb26.xlsx"
) -> _MatureFallback:
    """Build an in-memory ``_MatureFallback`` with a canned Damodaran row."""
    return _MatureFallback(
        damodaran_row=DamodaranMonthlyERPRow(
            start_of_month=date(2026, 2, 1),
            implied_erp_decimal=erp_decimal,
            implied_erp_t12m_decimal=erp_decimal + 0.0008,
            sp500_level=6939.0,
            tbond_rate_decimal=0.0426,
            source_file=source_file,
        )
    )


class TestResolveErpBpsWithLiveFallback:
    def test_live_damodaran_preempts_static_stub_for_us(self, db_session: Session) -> None:
        """No erp_canonical row → Damodaran monthly wins over static 5.5 %."""
        bps, flags = _resolve_erp_bps(
            db_session,
            "US",
            date(2024, 1, 2),
            mature_fallback=_mature_fallback(erp_decimal=0.0417),
        )
        assert bps == 417
        assert flags == ("ERP_MATURE_LIVE_DAMODARAN",)

    def test_live_damodaran_preempts_static_stub_for_non_us(self, db_session: Session) -> None:
        """Non-US also benefits — retains MATURE_ERP_PROXY_US alongside live flag."""
        bps, flags = _resolve_erp_bps(
            db_session,
            "PT",
            date(2024, 1, 2),
            mature_fallback=_mature_fallback(erp_decimal=0.0425),
        )
        assert bps == 425
        assert set(flags) == {"ERP_MATURE_LIVE_DAMODARAN", "MATURE_ERP_PROXY_US"}

    def test_erp_canonical_still_wins_over_damodaran(self, db_session: Session) -> None:
        """erp_canonical row is authoritative — Damodaran fallback untouched."""
        _seed_erp_canonical(db_session, erp_median_bps=472)
        bps, flags = _resolve_erp_bps(
            db_session,
            "US",
            date(2024, 1, 2),
            mature_fallback=_mature_fallback(erp_decimal=0.0417),
        )
        assert bps == 472
        assert flags == ()
        # Same for non-US (still proxy, using canonical not Damodaran).
        bps, flags = _resolve_erp_bps(
            db_session,
            "DE",
            date(2024, 1, 2),
            mature_fallback=_mature_fallback(erp_decimal=0.0417),
        )
        assert bps == 472
        assert flags == ("MATURE_ERP_PROXY_US",)

    def test_empty_fallback_falls_through_to_static_stub(self, db_session: Session) -> None:
        """``_MatureFallback(None)`` ≈ offline mode — static stub preserved."""
        bps, flags = _resolve_erp_bps(
            db_session,
            "US",
            date(2024, 1, 2),
            mature_fallback=_MatureFallback(damodaran_row=None),
        )
        assert bps == DAMODARAN_MATURE_ERP_BPS
        assert flags == ("ERP_STUB",)


class TestResolveMatureErpFallbackDisabled:
    def test_flag_disables_fetch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SONAR_DISABLE_DAMODARAN_LIVE", raising=False)
        fb = resolve_mature_erp_fallback(date(2024, 1, 2), disabled=True)
        assert fb.damodaran_row is None

    def test_env_var_disables_fetch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SONAR_DISABLE_DAMODARAN_LIVE", "1")
        fb = resolve_mature_erp_fallback(date(2024, 1, 2), disabled=False)
        assert fb.damodaran_row is None


class TestComposeKEWithDamodaranLiveFlag:
    def test_live_damodaran_flag_does_not_deduct_confidence(self) -> None:
        """Unlike ``ERP_STUB``, the Damodaran-live flag is a live signal."""
        crp = build_canonical(
            country_code="US",
            observation_date=date(2024, 1, 2),
            currency="USD",
        )
        result = compose_k_e(
            country_code="US",
            observation_date=date(2024, 1, 2),
            rf_local_decimal=0.04,
            crp=crp,
            erp_mature_bps=425,
            erp_flags=("ERP_MATURE_LIVE_DAMODARAN",),
        )
        assert "ERP_MATURE_LIVE_DAMODARAN" in result.flags
        # Confidence stays at CRP baseline — only ERP_STUB deducts.
        assert result.confidence == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Sprint T0 ADR-0011 — idempotency + per-country isolation structures
# ---------------------------------------------------------------------------


def test_curves_shipped_countries_matches_daily_curves() -> None:
    """cost_of_capital's shipped-cohort set must match daily_curves'
    actual ship list. Drift → spurious warn-vs-info classification.
    """
    from sonar.pipelines.daily_cost_of_capital import (  # noqa: PLC0415
        _CURVES_SHIPPED_COUNTRIES,
    )
    from sonar.pipelines.daily_curves import CURVE_SUPPORTED_COUNTRIES  # noqa: PLC0415

    assert _CURVES_SHIPPED_COUNTRIES == CURVE_SUPPORTED_COUNTRIES


def test_cost_of_capital_run_outcomes_default_empty() -> None:
    """Sprint T0 _CostOfCapitalRunOutcomes default-constructs with four
    empty buckets — invariant relied on by the summary-emit Principle 4.
    """
    from sonar.pipelines.daily_cost_of_capital import (  # noqa: PLC0415
        _CostOfCapitalRunOutcomes,
    )

    outcomes = _CostOfCapitalRunOutcomes()
    assert outcomes.persisted == []
    assert outcomes.duplicate == []
    assert outcomes.insufficient == []
    assert outcomes.failed == []
