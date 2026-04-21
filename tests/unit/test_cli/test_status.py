"""Tests for ``sonar status`` (Week 7 Sprint G)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import sonar.db.session  # noqa: F401 — activates FK=ON connect listener
from sonar.cli.status import (
    T1_7_COUNTRIES,
    CountryStatus,
    CycleStatus,
    format_matrix,
    format_status_summary,
    format_status_verbose,
    get_country_status,
)
from sonar.db.models import Base

ANCHOR = date(2024, 12, 31)
NOW = datetime(2024, 12, 31, 12, 0, tzinfo=UTC)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_cccs(
    session: Session, country: str = "US", score: float = 55.0, regime: str = "RECOVERY"
) -> None:
    session.execute(
        text(
            "INSERT INTO credit_cycle_scores "
            "(cccs_id, country_code, date, methodology_version, score_0_100, regime, "
            "regime_persistence_days, "
            "cs_score_0_100, lc_score_0_100, ms_score_0_100, qs_score_0_100, "
            "cs_weight_effective, lc_weight_effective, ms_weight_effective, components_available, "
            "boom_overlay_active, confidence, flags, created_at) "
            "VALUES (:id, :c, :d, 'CCCS_v1.0', :s, :r, 5, 50.0, 55.0, 60.0, 52.0, "
            "0.3, 0.3, 0.3, 4, 0, 0.85, NULL, :ts)"
        ),
        {
            "id": f"cccs-{country}",
            "c": country,
            "d": ANCHOR.isoformat(),
            "s": score,
            "r": regime,
            "ts": NOW.isoformat(),
        },
    )


def _seed_fcs(
    session: Session, country: str = "US", score: float = 60.0, regime: str = "OPTIMISM"
) -> None:
    session.execute(
        text(
            "INSERT INTO financial_cycle_scores "
            "(fcs_id, country_code, date, methodology_version, score_0_100, regime, "
            "regime_persistence_days, "
            "f1_score_0_100, f2_score_0_100, f3_score_0_100, f4_score_0_100, "
            "f1_weight_effective, f2_weight_effective, f3_weight_effective, f4_weight_effective, "
            "indices_available, country_tier, bubble_warning_active, "
            "confidence, flags, created_at) "
            "VALUES (:id, :c, :d, 'FCS_v1.0', :s, :r, 5, 62.0, 58.0, 50.0, 70.0, "
            "0.3, 0.2, 0.3, 0.2, 4, 1, 0, 0.85, NULL, :ts)"
        ),
        {
            "id": f"fcs-{country}",
            "c": country,
            "d": ANCHOR.isoformat(),
            "s": score,
            "r": regime,
            "ts": NOW.isoformat(),
        },
    )


def _seed_msc(session: Session, country: str = "US", score: float = 60.0) -> None:
    session.execute(
        text(
            "INSERT INTO monetary_cycle_scores "
            "(msc_id, country_code, date, methodology_version, score_0_100, "
            "regime_6band, regime_3band, regime_persistence_days, "
            "m1_score_0_100, m2_score_0_100, m3_score_0_100, m4_score_0_100, "
            "m1_weight_effective, m2_weight_effective, m3_weight_effective, "
            "m4_weight_effective, cs_weight_effective, inputs_available, "
            "dilemma_overlay_active, confidence, flags, created_at) "
            "VALUES (:id, :c, :d, 'MSC_v1.0', :s, 'NEUTRAL_TIGHT', 'TIGHT', 5, "
            "62.0, 58.0, 55.0, 65.0, 0.33, 0.17, 0.28, 0.22, 0.0, 4, 0, 0.85, NULL, :ts)"
        ),
        {
            "id": f"msc-{country}",
            "c": country,
            "d": ANCHOR.isoformat(),
            "s": score,
            "ts": NOW.isoformat(),
        },
    )


def _seed_ecs(
    session: Session, country: str = "US", score: float = 55.0, regime: str = "EXPANSION"
) -> None:
    session.execute(
        text(
            "INSERT INTO economic_cycle_scores "
            "(ecs_id, country_code, date, methodology_version, score_0_100, regime, "
            "regime_persistence_days, "
            "e1_score_0_100, e2_score_0_100, e3_score_0_100, e4_score_0_100, "
            "e1_weight_effective, e2_weight_effective, e3_weight_effective, e4_weight_effective, "
            "indices_available, stagflation_overlay_active, "
            "confidence, flags, created_at) "
            "VALUES (:id, :c, :d, 'ECS_v1.0', :s, :r, 5, 58.0, 55.0, 50.0, 60.0, "
            "0.35, 0.25, 0.25, 0.15, 4, 0, 0.85, NULL, :ts)"
        ),
        {
            "id": f"ecs-{country}",
            "c": country,
            "d": ANCHOR.isoformat(),
            "s": score,
            "r": regime,
            "ts": NOW.isoformat(),
        },
    )


def test_t1_constant() -> None:
    assert T1_7_COUNTRIES == ("US", "DE", "PT", "IT", "ES", "FR", "NL")
    assert len(T1_7_COUNTRIES) == 7


def test_empty_db_returns_all_none(session: Session) -> None:
    status = get_country_status(session, "US", ANCHOR, now=NOW)
    assert status.country_code == "US"
    assert status.cccs is None
    assert status.fcs is None
    assert status.msc is None
    assert status.ecs is None


def test_happy_path_populates_all_four(session: Session) -> None:
    _seed_cccs(session)
    _seed_fcs(session)
    _seed_msc(session)
    _seed_ecs(session)
    session.commit()

    status = get_country_status(session, "US", ANCHOR, now=NOW)
    assert status.cccs is not None
    assert status.cccs.score == pytest.approx(55.0)
    assert status.cccs.regime == "RECOVERY"
    assert status.cccs.freshness == "fresh"
    assert status.cccs.sub_scores == {"cs": 50.0, "lc": 55.0, "ms": 60.0, "qs": 52.0}
    assert status.fcs is not None
    assert status.fcs.regime == "OPTIMISM"
    assert status.msc is not None
    # MSC uses the 3-band regime column for the dashboard.
    assert status.msc.regime == "TIGHT"
    assert status.ecs is not None
    assert status.ecs.regime == "EXPANSION"


def test_partial_coverage_only_some_cycles(session: Session) -> None:
    _seed_cccs(session)
    _seed_ecs(session)
    session.commit()

    status = get_country_status(session, "US", ANCHOR, now=NOW)
    assert status.cccs is not None
    assert status.fcs is None
    assert status.msc is None
    assert status.ecs is not None


def test_stale_classification(session: Session) -> None:
    # created_at = NOW - 48h → stale
    session.execute(
        text(
            "INSERT INTO credit_cycle_scores "
            "(cccs_id, country_code, date, methodology_version, score_0_100, regime, "
            "regime_persistence_days, "
            "cs_weight_effective, lc_weight_effective, ms_weight_effective, "
            "components_available, boom_overlay_active, confidence, created_at) "
            "VALUES ('stale-us', 'US', :d, 'CCCS_v1.0', 55.0, 'RECOVERY', 5, "
            "0.3, 0.3, 0.3, 4, 0, 0.85, :ts)"
        ),
        {"d": ANCHOR.isoformat(), "ts": (NOW - timedelta(hours=48)).isoformat()},
    )
    session.commit()
    status = get_country_status(session, "US", ANCHOR, now=NOW)
    assert status.cccs is not None
    assert status.cccs.freshness == "stale"


def test_format_status_summary_shape() -> None:
    cycle = CycleStatus(
        cycle_code="CCCS",
        score=55.0,
        regime="RECOVERY",
        confidence=0.85,
        flags=(),
        last_updated=NOW,
        freshness="fresh",
    )
    status = CountryStatus(country_code="US", as_of_date=ANCHOR, cccs=cycle)
    table = format_status_summary(status)
    assert "US" in table.title
    assert len(table.columns) == 6


def test_format_status_verbose_shape() -> None:
    cycle = CycleStatus(
        cycle_code="CCCS",
        score=55.0,
        regime="RECOVERY",
        confidence=0.85,
        flags=("FLAG_A",),
        last_updated=NOW,
        freshness="fresh",
        sub_scores={"cs": 50.0, "lc": 55.0, "ms": 60.0, "qs": None},
    )
    status = CountryStatus(country_code="US", as_of_date=ANCHOR, cccs=cycle)
    table = format_status_verbose(status)
    assert "verbose" in table.title.lower()
    assert len(table.columns) == 5


def test_format_matrix_shape() -> None:
    cycle = CycleStatus(
        cycle_code="ECS",
        score=55.0,
        regime="EXPANSION",
        confidence=0.85,
        flags=(),
        last_updated=NOW,
        freshness="fresh",
    )
    statuses = [
        CountryStatus(country_code="US", as_of_date=ANCHOR, ecs=cycle),
        CountryStatus(country_code="DE", as_of_date=ANCHOR),  # all cycles None
    ]
    table = format_matrix(statuses)
    # Country + 4 cycle columns + L5 column.
    assert len(table.columns) == 6
    assert table.row_count == 2


def test_all_t1_matrix_end_to_end(session: Session) -> None:
    _seed_ecs(session, country="US")
    _seed_ecs(session, country="DE")
    session.commit()

    statuses = [get_country_status(session, c, ANCHOR, now=NOW) for c in T1_7_COUNTRIES]
    # US + DE seeded; others return all-None.
    by_country = {s.country_code: s for s in statuses}
    assert by_country["US"].ecs is not None
    assert by_country["DE"].ecs is not None
    assert by_country["PT"].ecs is None
    table = format_matrix(statuses)
    assert table.row_count == 7


# ---------------------------------------------------------------------------
# L5 meta-regime display (Sprint K C3)
# ---------------------------------------------------------------------------


def _seed_l5(
    session: Session,
    *,
    country: str = "US",
    meta_regime: str = "soft_landing",
    confidence: float = 0.82,
    reason: str = "expansion+neutral",
    flags: str | None = "L5_SOFT_LANDING",
    ts: datetime | None = None,
) -> None:
    session.execute(
        text(
            "INSERT INTO l5_meta_regimes "
            "(l5_id, country_code, date, methodology_version, meta_regime, "
            "ecs_id, cccs_id, fcs_id, msc_id, confidence, flags, "
            "classification_reason, created_at) "
            "VALUES (:id, :c, :d, 'L5_META_REGIME_v0.1', :mr, "
            "NULL, NULL, NULL, NULL, :conf, :flags, :reason, :ts)"
        ),
        {
            "id": f"l5-{country}",
            "c": country,
            "d": ANCHOR.isoformat(),
            "mr": meta_regime,
            "conf": confidence,
            "flags": flags,
            "reason": reason,
            "ts": (ts or NOW).isoformat(),
        },
    )


def test_l5_meta_regime_populated_when_row_exists(session: Session) -> None:
    _seed_l5(session)
    session.commit()
    status = get_country_status(session, "US", ANCHOR, now=NOW)
    assert status.l5_meta_regime is not None
    assert status.l5_meta_regime.meta_regime == "soft_landing"
    assert status.l5_meta_regime.confidence == pytest.approx(0.82)
    assert status.l5_meta_regime.flags == ("L5_SOFT_LANDING",)
    assert status.l5_meta_regime.classification_reason == "expansion+neutral"
    assert status.l5_meta_regime.freshness == "fresh"


def test_l5_none_when_no_row(session: Session) -> None:
    status = get_country_status(session, "US", ANCHOR, now=NOW)
    assert status.l5_meta_regime is None


def test_l5_stale_freshness(session: Session) -> None:
    _seed_l5(session, ts=NOW - timedelta(hours=48))
    session.commit()
    status = get_country_status(session, "US", ANCHOR, now=NOW)
    assert status.l5_meta_regime is not None
    assert status.l5_meta_regime.freshness == "stale"


def test_format_status_summary_includes_l5_row(session: Session) -> None:
    _seed_l5(session, meta_regime="overheating")
    session.commit()
    status = get_country_status(session, "US", ANCHOR, now=NOW)
    table = format_status_summary(status)
    # Row count: we only seeded L5 (no L4 cycles), so one Meta-Regime row.
    assert table.row_count == 1


def test_format_status_summary_na_when_l5_missing() -> None:
    status = CountryStatus(country_code="US", as_of_date=ANCHOR)
    table = format_status_summary(status)
    # No cycles + no L5 → zero L4 rows + one "Meta-Regime … N/A" row.
    assert table.row_count == 1


def test_format_status_verbose_includes_classification_reason(session: Session) -> None:
    _seed_l5(session, reason="peak+boom+optimism", meta_regime="overheating")
    session.commit()
    status = get_country_status(session, "US", ANCHOR, now=NOW)
    table = format_status_verbose(status)
    assert table.row_count == 1  # L5 row only (no L4 cycles seeded)


def test_matrix_includes_l5_column(session: Session) -> None:
    _seed_l5(session, country="US", meta_regime="soft_landing")
    _seed_l5(session, country="DE", meta_regime="recession_risk")
    session.commit()
    statuses = [get_country_status(session, c, ANCHOR, now=NOW) for c in ("US", "DE", "PT")]
    table = format_matrix(statuses)
    assert len(table.columns) == 6  # Country + CCCS/FCS/MSC/ECS + L5
    assert table.row_count == 3
