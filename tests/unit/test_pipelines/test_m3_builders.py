"""Sprint O regression coverage — M3 T1 cohort dispatcher + classifier.

Parametric coverage over the 9-country M3 T1 cohort (US/DE/EA/GB/JP/CA/
IT/ES/FR) + degradation paths + NOT_IMPLEMENTED dispatch fallback, so
the observability channel (``monetary_pipeline.m3_compute_mode``) and
the country-policy metadata stay locked to the sprint acceptance §1
contract.

Scope (brief §2.5):

* ``test_classifier_full_mode_happy_path`` — US with full forwards +
  EXPINF inputs → ``FULL`` + ``US_M3_T1_TIER`` / ``M3_FULL_LIVE`` flags.
* ``test_classifier_degraded_expinf_missing`` — forwards present, no
  EXPINF row → ``DEGRADED`` + ``M3_EXPINF_MISSING``.
* ``test_classifier_degraded_confidence_subthreshold`` — EXPINF row
  present but confidence < :data:`MIN_EXPINF_CONFIDENCE` → ``DEGRADED``
  + ``M3_EXPINF_CONFIDENCE_SUBTHRESHOLD``.
* ``test_classifier_degraded_forwards_missing`` — forwards row absent
  → ``DEGRADED`` + ``M3_FORWARDS_MISSING`` (upstream curves skip).
* ``test_classifier_not_implemented_*`` — PT / NL / AU outside cohort
  → ``NOT_IMPLEMENTED`` + empty flag tuple (no raise).
* ``test_m3_dispatcher_9_countries_none_not_implemented`` — acceptance
  §1 parametric: every T1 cohort member resolves to FULL *or* DEGRADED,
  none NOT_IMPLEMENTED. Runtime state today = all DEGRADED per audit.
* ``test_country_m3_flags_per_country`` — FR vs IT vs JP wrapper
  shapes: sparsity-flag attachment for JP/CA/IT/ES; FR / US / DE / EA /
  GB stay flag-only-tier (no linker-sparsity reason).
* ``test_run_one_emits_m3_compute_mode_log`` — integration: run_one
  emits ``monetary_pipeline.m3_compute_mode`` structlog event per
  country invocation regardless of whether build_m3_inputs lands.
* ``test_m3_async_lifecycle_compatible`` — ADR-0011 Principle 6
  compatibility: run_one remains callable inside a single asyncio.run
  context; classifier adds no new event-loop boundary.
"""

from __future__ import annotations

import json
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Import sonar.db.session so the PRAGMA FK listener registers.
import sonar.db.session  # noqa: F401
from sonar.db.models import Base, IndexValue, NSSYieldCurveForwards, NSSYieldCurveSpot
from sonar.indices.monetary.db_backed_builder import (
    EXPINF_INDEX_CODE,
    MonetaryDbBackedInputsBuilder,
)
from sonar.indices.monetary.m3_country_policies import (
    M3_T1_COUNTRIES,
    M3_T1_DEGRADED_EXPECTED,
    classify_m3_compute_mode,
    country_m3_flags,
)
from sonar.indices.monetary.m3_market_expectations import MIN_EXPINF_CONFIDENCE
from sonar.pipelines.daily_monetary_indices import (
    T1_M3_COUNTRIES,
    _classify_m3_compute_mode,
    run_one,
)

ANCHOR = date(2026, 4, 22)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _fit_id(obs: date, country: str, suffix: str = "a") -> str:
    return f"{country:>2}{obs.isoformat().replace('-', '')}{suffix:>012}"[:36].ljust(36, "0")


def _seed_forwards(
    session: Session,
    *,
    country: str,
    obs: date = ANCHOR,
    forward_5y5y: float = 0.041,
) -> None:
    fit_id = _fit_id(obs, country)
    session.add(
        NSSYieldCurveSpot(
            country_code=country,
            date=obs,
            methodology_version="NSS_v1.0",
            fit_id=fit_id,
            beta_0=0.04,
            beta_1=-0.01,
            beta_2=0.005,
            beta_3=None,
            lambda_1=1.5,
            lambda_2=None,
            fitted_yields_json=json.dumps({"10Y": 0.04}),
            observations_used=11,
            rmse_bps=5.0,
            xval_deviation_bps=None,
            confidence=0.9,
            flags=None,
            source_connector="fred",
        )
    )
    session.flush()
    session.add(
        NSSYieldCurveForwards(
            country_code=country,
            date=obs,
            methodology_version="NSS_v1.0",
            fit_id=fit_id,
            forwards_json=json.dumps({"5y5y": forward_5y5y, "1y1y": 0.043, "2y1y": 0.038}),
            breakeven_forwards_json=None,
            confidence=0.9,
            flags=None,
        )
    )


def _seed_expinf(
    session: Session,
    *,
    country: str,
    obs: date = ANCHOR,
    confidence: float = 0.85,
) -> None:
    sub = {
        "expected_inflation_tenors": {"5y5y": 0.0245, "10Y": 0.024},
        "source_method_per_tenor": {"5y5y": "BEI", "10Y": "BEI"},
        "methods_available": 1,
        "anchor_status": "well_anchored",
    }
    session.add(
        IndexValue(
            index_code=EXPINF_INDEX_CODE,
            country_code=country,
            date=obs,
            methodology_version="EXPINF_v1.0",
            raw_value=0.024,
            zscore_clamped=0.0,
            value_0_100=50.0,
            sub_indicators_json=json.dumps(sub),
            confidence=confidence,
            flags=None,
            source_overlays_json=json.dumps({}),
        )
    )


# ---------------------------------------------------------------------------
# country_m3_flags — tier + sparsity-reason wrapper
# ---------------------------------------------------------------------------


def test_country_m3_flags_tier_only_for_full_candidates() -> None:
    """US / DE / EA / GB / FR emit the tier flag without a sparsity-reason."""
    for country in ("US", "DE", "EA", "GB", "FR"):
        assert country_m3_flags(country) == (f"{country}_M3_T1_TIER",)


def test_country_m3_flags_attaches_sparsity_for_degraded_expected() -> None:
    """JP / CA / IT / ES emit tier + sparsity-reason per audit §4."""
    jp = country_m3_flags("JP")
    assert jp == ("JP_M3_T1_TIER", "JP_M3_BEI_LINKER_THIN_EXPECTED")

    ca = country_m3_flags("CA")
    assert ca == ("CA_M3_T1_TIER", "CA_M3_BEI_RRB_LIMITED_EXPECTED")

    it = country_m3_flags("IT")
    assert it == ("IT_M3_T1_TIER", "IT_M3_BEI_BTP_EI_SPARSE_EXPECTED")

    es = country_m3_flags("ES")
    assert es == ("ES_M3_T1_TIER", "ES_M3_BEI_BONOS_EI_LIMITED_EXPECTED")


def test_country_m3_flags_empty_for_non_cohort() -> None:
    """PT / NL / AU / unknown-code → empty tuple (cheap membership guard)."""
    for country in ("PT", "NL", "AU", "NZ", "CH", "ZZ"):
        assert country_m3_flags(country) == ()


def test_country_m3_flags_case_normalises() -> None:
    """Lowercase input resolves to the canonical upper-case flag set."""
    assert country_m3_flags("gb") == ("GB_M3_T1_TIER",)


def test_t1_cohort_degraded_expected_consistency() -> None:
    """M3_T1_DEGRADED_EXPECTED must be a subset of M3_T1_COUNTRIES."""
    assert M3_T1_DEGRADED_EXPECTED.issubset(M3_T1_COUNTRIES)
    # FR is excluded (OATi depth + EA SPF suffices once EXPINF wires).
    assert "FR" not in M3_T1_DEGRADED_EXPECTED


def test_t1_m3_countries_alias_resolves_to_unified_cohort() -> None:
    """Sprint Q.0.5: T1_M3_COUNTRIES is now a deprecated alias for the 12-country T1_COUNTRIES.

    M3_T1_COUNTRIES (the per-country classifier policy frozenset, scope
    of Sprint O) remains the 9-country FULL/DEGRADED-capable subset —
    AU/NL/PT outside it resolve to NOT_IMPLEMENTED gracefully when the
    pipeline iterates the unified cohort.
    """
    assert len(T1_M3_COUNTRIES) == 12
    # The 9-country classifier policy set is a strict subset of the
    # 12-country pipeline iteration cohort.
    assert M3_T1_COUNTRIES.issubset(set(T1_M3_COUNTRIES))
    assert set(T1_M3_COUNTRIES) - M3_T1_COUNTRIES == {"AU", "NL", "PT"}


# ---------------------------------------------------------------------------
# classify_m3_compute_mode — core modes
# ---------------------------------------------------------------------------


def test_classifier_full_mode_happy_path(session: Session) -> None:
    """Forwards + high-confidence EXPINF present → FULL + M3_FULL_LIVE."""
    _seed_forwards(session, country="US")
    _seed_expinf(session, country="US", confidence=0.85)
    session.commit()

    mode, flags = classify_m3_compute_mode(session, "US", ANCHOR)
    assert mode == "FULL"
    assert "US_M3_T1_TIER" in flags
    assert "M3_FULL_LIVE" in flags
    assert "M3_EXPINF_MISSING" not in flags


def test_classifier_degraded_expinf_missing(session: Session) -> None:
    """Forwards present, EXPINF absent → DEGRADED + M3_EXPINF_MISSING."""
    _seed_forwards(session, country="GB")
    session.commit()

    mode, flags = classify_m3_compute_mode(session, "GB", ANCHOR)
    assert mode == "DEGRADED"
    assert "GB_M3_T1_TIER" in flags
    assert "M3_EXPINF_MISSING" in flags


def test_classifier_degraded_confidence_subthreshold(session: Session) -> None:
    """EXPINF row present but confidence below threshold → DEGRADED subthreshold."""
    _seed_forwards(session, country="DE")
    _seed_expinf(session, country="DE", confidence=MIN_EXPINF_CONFIDENCE - 0.01)
    session.commit()

    mode, flags = classify_m3_compute_mode(session, "DE", ANCHOR)
    assert mode == "DEGRADED"
    assert "DE_M3_T1_TIER" in flags
    assert "M3_EXPINF_CONFIDENCE_SUBTHRESHOLD" in flags


def test_classifier_degraded_forwards_missing(session: Session) -> None:
    """Forwards absent (T1 curves-ship cohort gap) → DEGRADED + M3_FORWARDS_MISSING.

    Today all 9 T1 curves-ship cohort members have forwards populated by the
    daily-curves pipeline — this path covers the upstream-curves-failure
    edge that the classifier must distinguish from the EXPINF-missing case
    so operator journal grep can root-cause quickly.
    """
    mode, flags = classify_m3_compute_mode(session, "EA", ANCHOR)
    assert mode == "DEGRADED"
    assert "EA_M3_T1_TIER" in flags
    assert "M3_FORWARDS_MISSING" in flags


def test_classifier_not_implemented_pt() -> None:
    """PT outside :data:`M3_T1_COUNTRIES` → NOT_IMPLEMENTED + empty flags."""
    # Session unused — NOT_IMPLEMENTED short-circuits the DB query path.
    mode, flags = classify_m3_compute_mode(None, "PT", ANCHOR)  # type: ignore[arg-type]
    assert mode == "NOT_IMPLEMENTED"
    assert flags == ()


def test_classifier_not_implemented_nl_blocked_on_sprint_m() -> None:
    """NL excluded (blocked on Sprint M curves probe) → NOT_IMPLEMENTED."""
    mode, flags = classify_m3_compute_mode(None, "NL", ANCHOR)  # type: ignore[arg-type]
    assert mode == "NOT_IMPLEMENTED"
    assert flags == ()


def test_classifier_not_implemented_au_week11_deferred() -> None:
    """AU (sparse T1 Week 11+ probe) → NOT_IMPLEMENTED."""
    mode, flags = classify_m3_compute_mode(None, "AU", ANCHOR)  # type: ignore[arg-type]
    assert mode == "NOT_IMPLEMENTED"
    assert flags == ()


def test_classifier_case_normalises(session: Session) -> None:
    """Lowercase input resolves to upper-case cohort member."""
    _seed_forwards(session, country="GB")
    session.commit()
    mode, flags = classify_m3_compute_mode(session, "gb", ANCHOR)
    assert mode == "DEGRADED"
    assert "GB_M3_T1_TIER" in flags


def test_classifier_includes_sparsity_flag_for_jp(session: Session) -> None:
    """DEGRADED path preserves per-country sparsity-reason flag (JP)."""
    _seed_forwards(session, country="JP")
    session.commit()
    _mode, flags = classify_m3_compute_mode(session, "JP", ANCHOR)
    assert "JP_M3_T1_TIER" in flags
    assert "JP_M3_BEI_LINKER_THIN_EXPECTED" in flags
    assert "M3_EXPINF_MISSING" in flags


# ---------------------------------------------------------------------------
# Acceptance §1 — parametric 9-country cohort
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("country", sorted(M3_T1_COUNTRIES))
def test_m3_dispatcher_9_countries_none_not_implemented(session: Session, country: str) -> None:
    """Every M3-classifier-cohort member resolves to FULL or DEGRADED — never NOT_IMPLEMENTED.

    Runtime state today (audit §4) = all 9 DEGRADED pending the upstream
    EXPINF wiring CAL (CAL-EXPINF-LIVE-ASSEMBLER-WIRING, Week 11 P0).
    Seed forwards only — classifier must still resolve FULL / DEGRADED
    (not NOT_IMPLEMENTED) because cohort membership is the gate.

    Sprint Q.0.5 split: the M3 classifier policy frozenset
    (:data:`M3_T1_COUNTRIES`, 9 countries) parametrises this test —
    distinct from the unified pipeline iteration cohort
    (:data:`T1_M3_COUNTRIES` / :data:`T1_COUNTRIES`, 12 countries) where
    AU/NL/PT resolve to NOT_IMPLEMENTED gracefully.
    """
    _seed_forwards(session, country=country)
    session.commit()

    mode, flags = classify_m3_compute_mode(session, country, ANCHOR)
    assert mode in {"FULL", "DEGRADED"}
    assert mode != "NOT_IMPLEMENTED"
    assert f"{country}_M3_T1_TIER" in flags


@pytest.mark.parametrize(
    ("country", "expected_sparsity"),
    [
        ("JP", "JP_M3_BEI_LINKER_THIN_EXPECTED"),
        ("CA", "CA_M3_BEI_RRB_LIMITED_EXPECTED"),
        ("IT", "IT_M3_BEI_BTP_EI_SPARSE_EXPECTED"),
        ("ES", "ES_M3_BEI_BONOS_EI_LIMITED_EXPECTED"),
    ],
)
def test_classifier_attaches_sparsity_for_degraded_expected_cohort(
    session: Session, country: str, expected_sparsity: str
) -> None:
    """JP/CA/IT/ES DEGRADED emission carries the expected sparsity-reason flag."""
    _seed_forwards(session, country=country)
    session.commit()
    _mode, flags = classify_m3_compute_mode(session, country, ANCHOR)
    assert expected_sparsity in flags


# ---------------------------------------------------------------------------
# Pipeline integration — _classify re-export + log emission
# ---------------------------------------------------------------------------


def test_pipeline_re_export_matches_module_function(session: Session) -> None:
    """daily_monetary_indices._classify_m3_compute_mode delegates correctly."""
    _seed_forwards(session, country="FR")
    session.commit()
    a_mode, a_flags = _classify_m3_compute_mode(session, "FR", ANCHOR)
    b_mode, b_flags = classify_m3_compute_mode(session, "FR", ANCHOR)
    assert a_mode == b_mode
    assert a_flags == b_flags


async def test_run_one_emits_m3_compute_mode_log(
    session: Session, capsys: pytest.CaptureFixture[str]
) -> None:
    """run_one emits monetary_pipeline.m3_compute_mode per country invocation.

    Covers the Lesson #7 systemd verify contract — every country passing
    through run_one with a db_backed_builder attached must emit the
    compute-mode log so grep-based journal verification yields at least
    one hit per T1 country.
    """
    _seed_forwards(session, country="IT")
    session.commit()

    db_backed = MonetaryDbBackedInputsBuilder(session)
    await run_one(session, "IT", ANCHOR, db_backed_builder=db_backed)

    captured = capsys.readouterr()
    assert "monetary_pipeline.m3_compute_mode" in captured.out
    assert "country=IT" in captured.out
    # DEGRADED today (EXPINF missing) + tier + sparsity flags surfaced.
    assert "mode=DEGRADED" in captured.out
    assert "IT_M3_T1_TIER" in captured.out
    assert "IT_M3_BEI_BTP_EI_SPARSE_EXPECTED" in captured.out


async def test_run_one_m3_compute_mode_not_implemented_for_pt(
    session: Session, capsys: pytest.CaptureFixture[str]
) -> None:
    """run_one still emits compute_mode for PT — NOT_IMPLEMENTED semantics."""

    db_backed = MonetaryDbBackedInputsBuilder(session)
    await run_one(session, "PT", ANCHOR, db_backed_builder=db_backed)

    captured = capsys.readouterr()
    assert "monetary_pipeline.m3_compute_mode" in captured.out
    assert "country=PT" in captured.out
    assert "mode=NOT_IMPLEMENTED" in captured.out


async def test_m3_async_lifecycle_compatible(session: Session) -> None:
    """Classifier + run_one stay inside a single asyncio.run context.

    ADR-0011 Principle 6 compliance: Sprint T0.1 shipped AsyncExitStack
    discipline for connector teardown; Sprint O must not reintroduce a
    per-country asyncio.run or otherwise cross the event-loop boundary.
    The classifier is sync DB query, so this test simply asserts
    run_one can be awaited cleanly for a cohort iteration inside one
    event loop.
    """
    for country in ("US", "GB", "JP"):
        _seed_forwards(session, country=country)
    session.commit()

    db_backed = MonetaryDbBackedInputsBuilder(session)
    for country in ("US", "GB", "JP"):
        outcome = await run_one(session, country, ANCHOR, db_backed_builder=db_backed)
        # m3 persist = 0 because EXPINF missing → build_m3_inputs None.
        assert outcome.persisted["m3"] == 0
