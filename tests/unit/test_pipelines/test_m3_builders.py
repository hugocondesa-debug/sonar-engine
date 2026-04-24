"""Sprint O regression coverage — M3 T1 cohort dispatcher + classifier.

Parametric coverage over the 10-country M3 T1 cohort (US/DE/EA/GB/JP/CA/
IT/ES/FR/PT) + degradation paths + NOT_IMPLEMENTED dispatch fallback, so
the observability channel (``monetary_pipeline.m3_compute_mode``) and
the country-policy metadata stay locked to the sprint acceptance §1
contract. Sprint Q.4b promoted PT via the SPF_AREA_PROXY cascade.

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
* ``test_classifier_not_implemented_*`` — NL / AU outside cohort
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
from sonar.db.models import (
    Base,
    ExpInflationBeiRow,
    ExpInflationSurveyRow,
    IndexValue,
    NSSYieldCurveForwards,
    NSSYieldCurveSpot,
)
from sonar.indices.monetary.db_backed_builder import (
    EXPINF_INDEX_CODE,
    M3_EXPINF_FROM_BEI_FLAG,
    M3_EXPINF_FROM_SURVEY_FLAG,
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
    """NL / AU / unknown-code → empty tuple (cheap membership guard)."""
    for country in ("NL", "AU", "NZ", "CH", "ZZ"):
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
    of Sprint O + Sprint Q.4b) is the 10-country FULL/DEGRADED-capable
    subset — AU/NL outside it resolve to NOT_IMPLEMENTED gracefully when
    the pipeline iterates the unified cohort.
    """
    assert len(M3_T1_COUNTRIES) == 10
    assert len(T1_M3_COUNTRIES) == 12
    # The 10-country classifier policy set is a strict subset of the
    # 12-country pipeline iteration cohort.
    assert M3_T1_COUNTRIES.issubset(set(T1_M3_COUNTRIES))
    assert set(T1_M3_COUNTRIES) - M3_T1_COUNTRIES == {"AU", "NL"}


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
    (:data:`M3_T1_COUNTRIES`, 10 countries post-Sprint-Q.4b)
    parametrises this test — distinct from the unified pipeline iteration
    cohort (:data:`T1_M3_COUNTRIES` / :data:`T1_COUNTRIES`, 12 countries)
    where AU/NL resolve to NOT_IMPLEMENTED gracefully.
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


async def test_run_one_m3_compute_mode_not_implemented_for_au(
    session: Session, capsys: pytest.CaptureFixture[str]
) -> None:
    """run_one still emits compute_mode for AU — NOT_IMPLEMENTED semantics.

    AU replaces the pre-Sprint-Q.4b PT variant of this test now that PT
    has been promoted into :data:`M3_T1_COUNTRIES`. AU remains outside
    the classifier cohort (Week 11+ sparse probe deferred) so the
    Lesson #7 systemd verify contract — every pipelined country emits
    ``monetary_pipeline.m3_compute_mode`` regardless of tier — still has
    a NOT_IMPLEMENTED regression guard.
    """

    db_backed = MonetaryDbBackedInputsBuilder(session)
    await run_one(session, "AU", ANCHOR, db_backed_builder=db_backed)

    captured = capsys.readouterr()
    assert "monetary_pipeline.m3_compute_mode" in captured.out
    assert "country=AU" in captured.out
    assert "mode=NOT_IMPLEMENTED" in captured.out


# ---------------------------------------------------------------------------
# Sprint Q.1.1 — classifier survey-fallback uplift
# ---------------------------------------------------------------------------


def _seed_survey(
    session: Session,
    *,
    country: str,
    obs: date = ANCHOR,
    flags: str | None = "SPF_LT_AS_ANCHOR",
    confidence: float = 1.0,
    be_5y5y: float = 0.0202,
) -> None:
    """Seed an ``exp_inflation_survey`` row mirroring the Sprint Q.1 writer."""
    session.add(
        ExpInflationSurveyRow(
            exp_inf_id=f"{country}-{obs.isoformat()}-spf",
            country_code=country,
            date=obs,
            methodology_version="EXPINF_SURVEY_v1.0",
            confidence=confidence,
            flags=flags,
            survey_name="ECB_SPF_HICP",
            survey_release_date=obs,
            horizons_json=json.dumps({"LTE": be_5y5y}),
            interpolated_tenors_json=json.dumps({"5y5y": be_5y5y, "10Y": be_5y5y, "5Y": be_5y5y}),
        )
    )


def test_classifier_survey_fallback_uplifts_ea_to_full(session: Session) -> None:
    """Sprint Q.1.1: EA canonical empty + survey row present → FULL + propagated flags."""
    _seed_forwards(session, country="EA")
    _seed_survey(session, country="EA", flags="SPF_LT_AS_ANCHOR")
    session.commit()

    mode, flags = classify_m3_compute_mode(session, "EA", ANCHOR)
    assert mode == "FULL"
    assert "EA_M3_T1_TIER" in flags
    assert "SPF_LT_AS_ANCHOR" in flags
    assert M3_EXPINF_FROM_SURVEY_FLAG in flags
    assert "M3_FULL_LIVE" in flags
    assert "M3_EXPINF_MISSING" not in flags


def test_classifier_survey_fallback_propagates_area_proxy(session: Session) -> None:
    """Sprint Q.1.1: DE/FR/IT/ES survey rows carry SPF_AREA_PROXY → propagated to emit."""
    _seed_forwards(session, country="DE")
    _seed_survey(session, country="DE", flags="SPF_LT_AS_ANCHOR,SPF_AREA_PROXY")
    session.commit()

    mode, flags = classify_m3_compute_mode(session, "DE", ANCHOR)
    assert mode == "FULL"
    assert "SPF_LT_AS_ANCHOR" in flags
    assert "SPF_AREA_PROXY" in flags
    assert M3_EXPINF_FROM_SURVEY_FLAG in flags


def test_pt_resolves_via_spf_area_proxy(session: Session) -> None:
    """Sprint Q.4b: PT in cohort + SPF_AREA_PROXY survey row → FULL with propagated flags.

    PT has no national EXPINF canonical path and no linker-market depth;
    the Sprint Q.1 ECB SDW SPF writer persists an EA-aggregate row under
    ``country_code='PT'`` flagged ``SPF_AREA_PROXY``. The Sprint Q.1.1
    classifier survey fallback picks it up and uplifts PT to FULL without
    any PT-specific connector or writer.
    """
    _seed_forwards(session, country="PT")
    _seed_survey(session, country="PT", flags="SPF_LT_AS_ANCHOR,SPF_AREA_PROXY")
    session.commit()

    mode, flags = classify_m3_compute_mode(session, "PT", ANCHOR)
    assert mode == "FULL"
    assert "PT_M3_T1_TIER" in flags
    assert "SPF_LT_AS_ANCHOR" in flags
    assert "SPF_AREA_PROXY" in flags
    assert M3_EXPINF_FROM_SURVEY_FLAG in flags
    assert "M3_FULL_LIVE" in flags


def test_classifier_survey_fallback_preserves_sparsity_flag_for_it(session: Session) -> None:
    """Sprint Q.1.1: IT sparsity flag (BEI_BTP_EI_SPARSE) remains alongside survey uplift."""
    _seed_forwards(session, country="IT")
    _seed_survey(session, country="IT", flags="SPF_LT_AS_ANCHOR,SPF_AREA_PROXY")
    session.commit()

    mode, flags = classify_m3_compute_mode(session, "IT", ANCHOR)
    assert mode == "FULL"
    assert "IT_M3_T1_TIER" in flags
    # Sparsity reason still emitted — structural BEI thinness not masked by survey uplift.
    assert "IT_M3_BEI_BTP_EI_SPARSE_EXPECTED" in flags
    assert "SPF_AREA_PROXY" in flags
    assert M3_EXPINF_FROM_SURVEY_FLAG in flags


def test_classifier_survey_fallback_subthreshold_confidence_degrades(session: Session) -> None:
    """Sprint Q.1.1: survey row with confidence < threshold → DEGRADED subthreshold."""
    _seed_forwards(session, country="EA")
    _seed_survey(session, country="EA", confidence=MIN_EXPINF_CONFIDENCE - 0.05)
    session.commit()

    mode, flags = classify_m3_compute_mode(session, "EA", ANCHOR)
    assert mode == "DEGRADED"
    assert "M3_EXPINF_CONFIDENCE_SUBTHRESHOLD" in flags
    assert M3_EXPINF_FROM_SURVEY_FLAG not in flags


def test_classifier_canonical_priority_over_survey(session: Session) -> None:
    """Sprint Q.1.1: canonical IndexValue present → survey ignored, no FROM_SURVEY flag."""
    _seed_forwards(session, country="EA")
    _seed_expinf(session, country="EA", confidence=0.85)
    _seed_survey(session, country="EA", flags="SPF_LT_AS_ANCHOR")
    session.commit()

    mode, flags = classify_m3_compute_mode(session, "EA", ANCHOR)
    assert mode == "FULL"
    assert "M3_FULL_LIVE" in flags
    # Canonical wins; survey fallback bypassed.
    assert M3_EXPINF_FROM_SURVEY_FLAG not in flags
    assert "SPF_LT_AS_ANCHOR" not in flags


def test_classifier_us_regression_unchanged_by_survey_path(session: Session) -> None:
    """Sprint Q.1.1: US canonical path unchanged even when survey row coexists."""
    _seed_forwards(session, country="US")
    _seed_expinf(session, country="US", confidence=0.85)
    _seed_survey(session, country="US", flags="SPF_LT_AS_ANCHOR")
    session.commit()

    mode, flags = classify_m3_compute_mode(session, "US", ANCHOR)
    assert mode == "FULL"
    assert "US_M3_T1_TIER" in flags
    assert "M3_FULL_LIVE" in flags
    assert M3_EXPINF_FROM_SURVEY_FLAG not in flags


def test_classifier_no_canonical_no_survey_still_degraded(session: Session) -> None:
    """Sprint Q.1.1: GB / JP / CA (no canonical, no survey) → DEGRADED unchanged."""
    _seed_forwards(session, country="GB")
    session.commit()

    mode, flags = classify_m3_compute_mode(session, "GB", ANCHOR)
    assert mode == "DEGRADED"
    assert "M3_EXPINF_MISSING" in flags
    assert M3_EXPINF_FROM_SURVEY_FLAG not in flags


def test_classifier_survey_fallback_picks_most_recent_row(session: Session) -> None:
    """Sprint Q.1.1: sparse survey schedule → classifier picks most recent ≤ date."""
    _seed_forwards(session, country="EA")
    # Seed a stale row (60d old) plus current row.
    _seed_survey(session, country="EA", obs=date(2026, 2, 15))
    _seed_survey(session, country="EA", obs=ANCHOR)
    session.commit()

    mode, flags = classify_m3_compute_mode(session, "EA", ANCHOR)
    assert mode == "FULL"
    assert M3_EXPINF_FROM_SURVEY_FLAG in flags


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


# ---------------------------------------------------------------------------
# Sprint Q.2 — BEI fallback branch of classify_m3_compute_mode
# ---------------------------------------------------------------------------


def _seed_bei(
    session: Session,
    *,
    country: str,
    obs: date = ANCHOR,
    flags: str | None = "BEI_FITTED_IMPLIED",
    confidence: float = 0.85,
    y5: float = 0.040,
    y10: float = 0.035,
) -> None:
    """Seed an ``exp_inflation_bei`` row mirroring the Sprint Q.2 writer."""
    session.add(
        ExpInflationBeiRow(
            exp_inf_id=f"{country}-{obs.isoformat()}-bei",
            country_code=country,
            date=obs,
            methodology_version="EXPINF_BEI_v1.0",
            confidence=confidence,
            flags=flags,
            nominal_yields_json=json.dumps({}),
            linker_real_yields_json=json.dumps({}),
            bei_tenors_json=json.dumps({"5Y": y5, "10Y": y10}),
            linker_connector="BOE_GLC_INFLATION",
            nss_fit_id=None,
        )
    )


def test_classifier_bei_fallback_uplifts_gb_to_full(session: Session) -> None:
    """Sprint Q.2: GB canonical + survey empty + BEI row present → FULL + BEI flags."""
    _seed_forwards(session, country="GB")
    _seed_bei(session, country="GB", flags="BEI_FITTED_IMPLIED")
    session.commit()

    mode, flags = classify_m3_compute_mode(session, "GB", ANCHOR)
    assert mode == "FULL"
    assert "GB_M3_T1_TIER" in flags
    assert "BEI_FITTED_IMPLIED" in flags
    assert M3_EXPINF_FROM_BEI_FLAG in flags
    assert "M3_FULL_LIVE" in flags
    assert "M3_EXPINF_MISSING" not in flags
    assert M3_EXPINF_FROM_SURVEY_FLAG not in flags


def test_classifier_survey_wins_over_bei_when_both_present(session: Session) -> None:
    """Sprint Q.2: survey branch takes priority over BEI — GB gets SURVEY flag, not BEI."""
    _seed_forwards(session, country="GB")
    _seed_survey(session, country="GB", flags="SPF_LT_AS_ANCHOR")
    _seed_bei(session, country="GB")
    session.commit()

    mode, flags = classify_m3_compute_mode(session, "GB", ANCHOR)
    assert mode == "FULL"
    assert M3_EXPINF_FROM_SURVEY_FLAG in flags
    assert M3_EXPINF_FROM_BEI_FLAG not in flags


def test_classifier_canonical_wins_over_bei_when_both_present(session: Session) -> None:
    """Sprint Q.2: canonical IndexValue trumps BEI — GB gets no fallback flag."""
    _seed_forwards(session, country="GB")
    # Seed canonical EXPINF row (mirrors US cohort path).
    session.add(
        IndexValue(
            index_code=EXPINF_INDEX_CODE,
            country_code="GB",
            date=ANCHOR,
            methodology_version="EXPINF_v1.0",
            raw_value=0.025,
            zscore_clamped=0.0,
            value_0_100=50.0,
            sub_indicators_json=json.dumps(
                {
                    "expected_inflation_tenors": {"5y5y": 0.025, "10Y": 0.025},
                    "source_method_per_tenor": {"5y5y": "BEI", "10Y": "BEI"},
                    "methods_available": 1,
                    "anchor_status": "well_anchored",
                }
            ),
            confidence=0.90,
            flags=None,
            source_overlays_json=json.dumps({}),
        )
    )
    _seed_bei(session, country="GB")
    session.commit()

    mode, flags = classify_m3_compute_mode(session, "GB", ANCHOR)
    assert mode == "FULL"
    assert M3_EXPINF_FROM_BEI_FLAG not in flags
    assert M3_EXPINF_FROM_SURVEY_FLAG not in flags


def test_classifier_bei_subthreshold_confidence_remains_degraded(session: Session) -> None:
    """Sprint Q.2: BEI row below MIN_EXPINF_CONFIDENCE does NOT uplift to FULL."""
    _seed_forwards(session, country="GB")
    _seed_bei(session, country="GB", confidence=MIN_EXPINF_CONFIDENCE - 0.01)
    session.commit()

    mode, flags = classify_m3_compute_mode(session, "GB", ANCHOR)
    assert mode == "DEGRADED"
    assert "M3_EXPINF_CONFIDENCE_SUBTHRESHOLD" in flags
    assert M3_EXPINF_FROM_BEI_FLAG not in flags


def test_classifier_bei_us_regression_unchanged(session: Session) -> None:
    """Sprint Q.2: US canonical path identical — BEI row present but ignored."""
    _seed_forwards(session, country="US")
    session.add(
        IndexValue(
            index_code=EXPINF_INDEX_CODE,
            country_code="US",
            date=ANCHOR,
            methodology_version="EXPINF_v1.0",
            raw_value=0.024,
            zscore_clamped=0.0,
            value_0_100=50.0,
            sub_indicators_json=json.dumps(
                {
                    "expected_inflation_tenors": {"5y5y": 0.024, "10Y": 0.024},
                    "source_method_per_tenor": {"5y5y": "BEI", "10Y": "BEI"},
                    "methods_available": 1,
                }
            ),
            confidence=1.0,
            flags=None,
            source_overlays_json=json.dumps({}),
        )
    )
    # A BEI row too — must be completely ignored.
    _seed_bei(session, country="US")
    session.commit()

    mode, flags = classify_m3_compute_mode(session, "US", ANCHOR)
    assert mode == "FULL"
    assert "US_M3_T1_TIER" in flags
    assert "M3_FULL_LIVE" in flags
    assert M3_EXPINF_FROM_BEI_FLAG not in flags
    assert M3_EXPINF_FROM_SURVEY_FLAG not in flags


# ---------------------------------------------------------------------------
# Sprint Q.3 — JP Tankan + CA CES classifier cohort
# ---------------------------------------------------------------------------


def test_classifier_jp_tankan_survey_uplifts_to_full(session: Session) -> None:
    """Sprint Q.3: JP survey row (BOJ_TANKAN) uplifts JP from DEGRADED to FULL.

    JP sits in :data:`M3_T1_DEGRADED_EXPECTED` (linker-sparsity cohort)
    so the sparsity reason flag is emitted alongside the survey uplift
    — same observability pattern as Sprint Q.1 for IT/ES.
    """
    _seed_forwards(session, country="JP")
    session.add(
        ExpInflationSurveyRow(
            exp_inf_id="JP-tankan-anchor",
            country_code="JP",
            date=ANCHOR,
            methodology_version="EXPINF_SURVEY_v1.0",
            confidence=1.0,
            flags="TANKAN_LT_AS_ANCHOR",
            survey_name="BOJ_TANKAN",
            survey_release_date=ANCHOR,
            horizons_json=json.dumps({"1Y": 0.026, "3Y": 0.025, "5Y": 0.025}),
            interpolated_tenors_json=json.dumps(
                {
                    "5y5y": 0.025,
                    "10Y": 0.025,
                    "5Y": 0.025,
                    "2Y": 0.0255,
                    "1Y": 0.026,
                    "3Y": 0.025,
                    "30Y": 0.025,
                }
            ),
        )
    )
    session.commit()

    mode, flags = classify_m3_compute_mode(session, "JP", ANCHOR)
    assert mode == "FULL"
    assert "JP_M3_T1_TIER" in flags
    assert "JP_M3_BEI_LINKER_THIN_EXPECTED" in flags
    assert "TANKAN_LT_AS_ANCHOR" in flags
    assert M3_EXPINF_FROM_SURVEY_FLAG in flags
    assert "M3_FULL_LIVE" in flags


def test_classifier_ca_ces_survey_uplifts_to_full(session: Session) -> None:
    """Sprint Q.3: CA survey row (BOC_CES) uplifts CA from DEGRADED to FULL.

    CA's RRB-sparsity reason flag remains emitted alongside the survey
    uplift.
    """
    _seed_forwards(session, country="CA")
    session.add(
        ExpInflationSurveyRow(
            exp_inf_id="CA-ces-anchor",
            country_code="CA",
            date=ANCHOR,
            methodology_version="EXPINF_SURVEY_v1.0",
            confidence=1.0,
            flags="CES_LT_AS_ANCHOR",
            survey_name="BOC_CES",
            survey_release_date=ANCHOR,
            horizons_json=json.dumps({"1Y": 0.040, "2Y": 0.034, "5Y": 0.030}),
            interpolated_tenors_json=json.dumps(
                {
                    "5y5y": 0.030,
                    "10Y": 0.030,
                    "5Y": 0.030,
                    "2Y": 0.034,
                    "1Y": 0.040,
                    "3Y": 0.032,
                    "30Y": 0.030,
                }
            ),
        )
    )
    session.commit()

    mode, flags = classify_m3_compute_mode(session, "CA", ANCHOR)
    assert mode == "FULL"
    assert "CA_M3_T1_TIER" in flags
    assert "CA_M3_BEI_RRB_LIMITED_EXPECTED" in flags
    assert "CES_LT_AS_ANCHOR" in flags
    assert M3_EXPINF_FROM_SURVEY_FLAG in flags
    assert "M3_FULL_LIVE" in flags


def test_classifier_jp_no_survey_still_degraded(session: Session) -> None:
    """Sprint Q.3 regression: JP without survey row → DEGRADED (pre-Q.3 baseline)."""
    _seed_forwards(session, country="JP")
    session.commit()
    mode, flags = classify_m3_compute_mode(session, "JP", ANCHOR)
    assert mode == "DEGRADED"
    assert "JP_M3_T1_TIER" in flags
    assert "JP_M3_BEI_LINKER_THIN_EXPECTED" in flags
    assert "M3_EXPINF_MISSING" in flags
    assert M3_EXPINF_FROM_SURVEY_FLAG not in flags


def test_classifier_ea_survey_uplift_unchanged_by_q3_additions(session: Session) -> None:
    """Sprint Q.3 regression: EA SPF survey path unchanged — no TANKAN/CES flag bleed."""
    _seed_forwards(session, country="EA")
    _seed_survey(session, country="EA", flags="SPF_LT_AS_ANCHOR")
    session.commit()

    mode, flags = classify_m3_compute_mode(session, "EA", ANCHOR)
    assert mode == "FULL"
    assert "SPF_LT_AS_ANCHOR" in flags
    assert "TANKAN_LT_AS_ANCHOR" not in flags
    assert "CES_LT_AS_ANCHOR" not in flags
