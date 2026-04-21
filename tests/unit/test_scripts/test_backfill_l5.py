"""Unit tests for :mod:`sonar.scripts.backfill_l5` (CAL-backfill-l5)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sonar.db.models import (
    Base,
    CreditCycleScore,
    EconomicCycleScore,
    FinancialCycleScore,
    L5MetaRegime,
    MonetaryCycleScore,
)
from sonar.scripts.backfill_l5 import (
    T1_COUNTRIES,
    BackfillReport,
    backfill_country,
    iter_classifiable_triplets,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.orm import Session


NOW = datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC)


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


# ---------------------------------------------------------------------------
# Seeders — mirror Sprint K test patterns
# ---------------------------------------------------------------------------


def _seed_ecs(
    session: Session,
    *,
    country: str,
    d: date,
    regime: str = "EXPANSION",
    score: float = 60.0,
    stagflation: int = 0,
) -> None:
    session.add(
        EconomicCycleScore(
            ecs_id=f"ecs-{country}-{d.isoformat()}",
            country_code=country,
            date=d,
            methodology_version="ECS_v1.0",
            score_0_100=score,
            regime=regime,
            regime_persistence_days=5,
            e1_score_0_100=58.0,
            e2_score_0_100=55.0,
            e3_score_0_100=50.0,
            e4_score_0_100=60.0,
            e1_weight_effective=0.35,
            e2_weight_effective=0.25,
            e3_weight_effective=0.25,
            e4_weight_effective=0.15,
            indices_available=4,
            stagflation_overlay_active=stagflation,
            confidence=0.85,
            flags=None,
        )
    )


def _seed_cccs(
    session: Session,
    *,
    country: str,
    d: date,
    regime: str = "RECOVERY",
    score: float = 58.0,
    boom: int = 0,
) -> None:
    session.add(
        CreditCycleScore(
            cccs_id=f"cccs-{country}-{d.isoformat()}",
            country_code=country,
            date=d,
            methodology_version="CCCS_v1.0",
            score_0_100=score,
            regime=regime,
            regime_persistence_days=5,
            cs_score_0_100=55.0,
            lc_score_0_100=58.0,
            ms_score_0_100=60.0,
            qs_score_0_100=52.0,
            cs_weight_effective=0.3,
            lc_weight_effective=0.3,
            ms_weight_effective=0.3,
            components_available=4,
            boom_overlay_active=boom,
            confidence=0.85,
            flags=None,
        )
    )


def _seed_fcs(
    session: Session,
    *,
    country: str,
    d: date,
    regime: str = "OPTIMISM",
    score: float = 62.0,
    bubble: int = 0,
) -> None:
    session.add(
        FinancialCycleScore(
            fcs_id=f"fcs-{country}-{d.isoformat()}",
            country_code=country,
            date=d,
            methodology_version="FCS_v1.0",
            score_0_100=score,
            regime=regime,
            regime_persistence_days=5,
            f1_score_0_100=60.0,
            f2_score_0_100=62.0,
            f3_score_0_100=None,
            f4_score_0_100=None,
            f1_weight_effective=0.5,
            f2_weight_effective=0.5,
            f3_weight_effective=0.0,
            f4_weight_effective=None,
            indices_available=3,
            country_tier=1,
            f3_m4_divergence=None,
            bubble_warning_active=bubble,
            bubble_warning_components_json=None,
            confidence=0.85,
            flags=None,
        )
    )


def _seed_msc(
    session: Session,
    *,
    country: str,
    d: date,
    regime_3band: str = "NEUTRAL",
    score: float = 50.0,
    dilemma: int = 0,
) -> None:
    session.add(
        MonetaryCycleScore(
            msc_id=f"msc-{country}-{d.isoformat()}",
            country_code=country,
            date=d,
            methodology_version="MSC_v1.0",
            score_0_100=score,
            regime_6band="NEUTRAL_TIGHT",
            regime_3band=regime_3band,
            regime_persistence_days=5,
            m1_score_0_100=52.0,
            m2_score_0_100=50.0,
            m3_score_0_100=48.0,
            m4_score_0_100=50.0,
            cs_score_0_100=None,
            m1_weight_effective=0.3,
            m2_weight_effective=0.3,
            m3_weight_effective=0.2,
            m4_weight_effective=0.2,
            cs_weight_effective=0.0,
            inputs_available=4,
            cs_hawkish_score=None,
            fed_dissent_count=None,
            dot_plot_drift_bps=None,
            dilemma_overlay_active=dilemma,
            dilemma_trigger_json=None,
            confidence=0.85,
            flags=None,
        )
    )


def _seed_full_stack(session: Session, *, country: str, d: date) -> None:
    _seed_ecs(session, country=country, d=d)
    _seed_cccs(session, country=country, d=d)
    _seed_fcs(session, country=country, d=d)
    _seed_msc(session, country=country, d=d)
    session.commit()


# ---------------------------------------------------------------------------
# iter_classifiable_triplets
# ---------------------------------------------------------------------------


class TestIterClassifiableTriplets:
    def test_yields_dates_with_any_cycle_and_no_l5(self, db_session: Session) -> None:
        d1 = date(2024, 1, 31)
        d2 = date(2024, 2, 29)
        d3 = date(2024, 3, 29)
        _seed_full_stack(db_session, country="US", d=d1)
        _seed_full_stack(db_session, country="US", d=d2)
        # Seed only ECS for d3 (still eligible — permissive iterator).
        _seed_ecs(db_session, country="US", d=d3)
        db_session.commit()

        out = list(iter_classifiable_triplets(db_session, "US"))
        assert out == [d1, d2, d3]

    def test_excludes_dates_already_classified(self, db_session: Session) -> None:
        d1 = date(2024, 1, 31)
        d2 = date(2024, 2, 29)
        _seed_full_stack(db_session, country="US", d=d1)
        _seed_full_stack(db_session, country="US", d=d2)
        db_session.add(
            L5MetaRegime(
                l5_id="l5-us-2024-01-31",
                country_code="US",
                date=d1,
                methodology_version="L5_META_REGIME_v0.1",
                meta_regime="soft_landing",
                ecs_id="ecs-US-2024-01-31",
                cccs_id="cccs-US-2024-01-31",
                fcs_id="fcs-US-2024-01-31",
                msc_id="msc-US-2024-01-31",
                confidence=0.85,
                flags=None,
                classification_reason="expansion+neutral",
            )
        )
        db_session.commit()
        out = list(iter_classifiable_triplets(db_session, "US"))
        assert out == [d2]

    def test_respects_from_date_filter(self, db_session: Session) -> None:
        d1 = date(2023, 12, 31)
        d2 = date(2024, 6, 30)
        d3 = date(2024, 12, 31)
        _seed_full_stack(db_session, country="US", d=d1)
        _seed_full_stack(db_session, country="US", d=d2)
        _seed_full_stack(db_session, country="US", d=d3)
        out = list(iter_classifiable_triplets(db_session, "US", from_date=date(2024, 1, 1)))
        assert out == [d2, d3]

    def test_country_scoped(self, db_session: Session) -> None:
        d = date(2024, 12, 31)
        _seed_full_stack(db_session, country="US", d=d)
        _seed_full_stack(db_session, country="DE", d=d)
        out_us = list(iter_classifiable_triplets(db_session, "US"))
        out_de = list(iter_classifiable_triplets(db_session, "DE"))
        assert out_us == [d]
        assert out_de == [d]


# ---------------------------------------------------------------------------
# backfill_country
# ---------------------------------------------------------------------------


class TestBackfillCountry:
    def test_dry_run_classifies_without_persisting(self, db_session: Session) -> None:
        _seed_full_stack(db_session, country="US", d=date(2024, 12, 31))
        report = backfill_country(db_session, "US", dry_run=True)
        assert report.eligible == 1
        assert report.classified == 1
        assert report.persisted == 0
        assert report.skipped_insufficient == 0
        assert report.skipped_duplicate == 0
        # No rows inserted.
        assert db_session.query(L5MetaRegime).count() == 0

    def test_execute_persists_row(self, db_session: Session) -> None:
        _seed_full_stack(db_session, country="US", d=date(2024, 12, 31))
        report = backfill_country(db_session, "US", dry_run=False)
        assert report.persisted == 1
        assert report.classified == 1
        rows = db_session.query(L5MetaRegime).all()
        assert len(rows) == 1
        assert rows[0].country_code == "US"

    def test_execute_idempotent(self, db_session: Session) -> None:
        _seed_full_stack(db_session, country="US", d=date(2024, 12, 31))
        first = backfill_country(db_session, "US", dry_run=False)
        assert first.persisted == 1
        # Second run: no eligible dates, zero work done.
        second = backfill_country(db_session, "US", dry_run=False)
        assert second.eligible == 0
        assert second.persisted == 0
        assert db_session.query(L5MetaRegime).count() == 1

    def test_insufficient_cycles_counted(self, db_session: Session) -> None:
        # Only 2/4 cycles seeded → classifier raises InsufficientL4DataError.
        d = date(2024, 12, 31)
        _seed_ecs(db_session, country="US", d=d)
        _seed_cccs(db_session, country="US", d=d)
        db_session.commit()
        report = backfill_country(db_session, "US", dry_run=False)
        assert report.eligible == 1
        assert report.skipped_insufficient == 1
        assert report.persisted == 0
        assert db_session.query(L5MetaRegime).count() == 0


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_t1_countries_matches_sonar_convention() -> None:
    assert T1_COUNTRIES == ("US", "DE", "PT", "IT", "ES", "FR", "NL")


def test_backfill_report_default_values() -> None:
    r = BackfillReport()
    assert r.eligible == 0
    assert r.per_country == {}
