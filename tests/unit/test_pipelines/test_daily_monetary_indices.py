"""Tests for daily_monetary_indices pipeline (week7 sprint B C3)."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from sonar.db.models import (
    Base,
    M1EffectiveRatesResult as M1Row,
    M2TaylorGapsResult as M2Row,
    M4FciResult as M4Row,
)
from sonar.indices.monetary.m1_effective_rates import M1EffectiveRatesInputs
from sonar.indices.monetary.m2_taylor_gaps import M2TaylorGapsInputs
from sonar.indices.monetary.m4_fci import M4FciInputs
from sonar.indices.monetary.orchestrator import MonetaryIndicesInputs
from sonar.pipelines import daily_monetary_indices as pipeline_mod
from sonar.pipelines.daily_monetary_indices import (
    MONETARY_SUPPORTED_COUNTRIES,
    T1_7_COUNTRIES,
    T1_COUNTRIES,
    T1_M3_COUNTRIES,
    _warn_if_deprecated_alias,
    default_inputs_builder,
    run_one,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


async def _synthetic_builder(
    _session: Session,
    country_code: str,
    observation_date: date,
) -> MonetaryIndicesInputs:
    rng = np.random.default_rng(seed=0)
    m1 = M1EffectiveRatesInputs(
        country_code=country_code,
        observation_date=observation_date,
        policy_rate_pct=0.0525,
        expected_inflation_5y_pct=0.025,
        r_star_pct=0.008,
        balance_sheet_pct_gdp_current=0.30,
        balance_sheet_pct_gdp_12m_ago=0.34,
        real_shadow_rate_history=rng.normal(0.01, 0.005, 360).tolist(),
        stance_vs_neutral_history=rng.normal(0.005, 0.005, 360).tolist(),
        balance_sheet_signal_history=rng.normal(0.0, 0.01, 360).tolist(),
        source_connector=("fred",),
    )
    m2 = M2TaylorGapsInputs(
        country_code=country_code,
        observation_date=observation_date,
        policy_rate_pct=0.0525,
        inflation_yoy_pct=0.028,
        inflation_target_pct=0.02,
        output_gap_pct=0.005,
        r_star_pct=0.008,
        prev_policy_rate_pct=0.0525,
        inflation_forecast_2y_pct=0.024,
        gap_1993_history=rng.normal(0.0, 0.003, 360).tolist(),
        gap_1999_history=rng.normal(0.0, 0.003, 360).tolist(),
        gap_forward_history=rng.normal(0.0, 0.003, 360).tolist(),
        gap_inertia_history=rng.normal(0.0, 0.003, 360).tolist(),
        source_connector=("fred", "cbo"),
    )
    m4 = M4FciInputs(
        country_code=country_code,
        observation_date=observation_date,
        nfci_level=-0.5,
        nfci_history=rng.normal(-0.5, 0.3, 360).tolist(),
        fci_level_12m_ago=-0.45,
        source_connector=("fred",),
    )
    return MonetaryIndicesInputs(
        country_code=country_code,
        observation_date=observation_date,
        m1=m1,
        m2=m2,
        m4=m4,
    )


async def test_default_builder_returns_empty(session: Session) -> None:
    bundle = await default_inputs_builder(session, "US", date(2024, 12, 31))
    assert bundle.m1 is None
    assert bundle.m2 is None
    assert bundle.m4 is None


async def test_run_one_default_persists_nothing(session: Session) -> None:
    outcome = await run_one(session, "US", date(2024, 12, 31))
    assert outcome.persisted == {"m1": 0, "m2": 0, "m3": 0, "m4": 0}


async def test_run_one_with_synthetic_persists_three(session: Session) -> None:
    outcome = await run_one(session, "US", date(2024, 12, 31), inputs_builder=_synthetic_builder)
    assert outcome.persisted == {"m1": 1, "m2": 1, "m3": 0, "m4": 1}
    assert session.query(M1Row).count() == 1
    assert session.query(M2Row).count() == 1
    assert session.query(M4Row).count() == 1


async def test_unified_t1_cohort_synthetic_run(session: Session) -> None:
    """Sprint Q.0.5: synthetic builder persists M1 for every member of the unified T1 cohort."""
    d = date(2024, 12, 31)
    for country in T1_COUNTRIES:
        outcome = await run_one(session, country, d, inputs_builder=_synthetic_builder)
        assert outcome.persisted["m1"] == 1
    assert session.query(M1Row).count() == len(T1_COUNTRIES)


def test_t1_countries_unified_size() -> None:
    """Sprint Q.0.5: T1_COUNTRIES is the canonical 12-country cohort.

    Tracks true T1 curves coverage (11 with shipped curves + NL graceful skip).
    """
    assert len(T1_COUNTRIES) == 12
    assert set(T1_COUNTRIES) == {
        "US",
        "DE",
        "EA",
        "GB",
        "JP",
        "CA",
        "IT",
        "ES",
        "FR",
        "NL",
        "PT",
        "AU",
    }


def test_t1_countries_iteration_order_stable() -> None:
    """Tuple ordering is deterministic so journal grep contracts (Lesson #7) stay stable."""
    assert T1_COUNTRIES == (
        "US",
        "DE",
        "EA",
        "GB",
        "JP",
        "CA",
        "IT",
        "ES",
        "FR",
        "NL",
        "PT",
        "AU",
    )


def test_deprecated_aliases_resolve_to_unified() -> None:
    """Sprint Q.0.5: T1_7_COUNTRIES + T1_M3_COUNTRIES alias to T1_COUNTRIES (backward compat)."""
    assert T1_7_COUNTRIES is T1_COUNTRIES
    assert T1_M3_COUNTRIES is T1_COUNTRIES


def _stub_main(monkeypatch: pytest.MonkeyPatch, captured: dict[str, object]) -> None:
    """Patch the async dispatcher + asyncio.run so main() stays in-process.

    Replaces ``_run_async_pipeline`` with a sync stub that captures the
    ``targets`` list, and replaces :func:`asyncio.run` with a passthrough
    that calls the stub directly — keeps the test off the event-loop
    plumbing entirely so the unraisable-exception checker doesn't fire
    on later async tests in the file.
    """

    def fake_run(*, targets: list[str], **_kwargs: object) -> object:
        captured["targets"] = list(targets)
        return SimpleNamespace(persisted=[], no_inputs=[], duplicate=[], failed=[])

    def fake_asyncio_run(coro: object) -> object:
        # Discard the coroutine — fake_run's return value is what main()
        # actually uses. Closing the coroutine prevents
        # ``RuntimeWarning: coroutine '...' was never awaited``.
        if hasattr(coro, "close"):
            coro.close()
        return fake_run(targets=captured.get("__targets_proxy", []))

    # Swap _run_async_pipeline to a sync function so main()'s
    # ``asyncio.run(_run_async_pipeline(...))`` call site receives a
    # plain object (not a coroutine) — combined with the asyncio.run
    # passthrough below, no real event loop is ever created.
    def sync_dispatcher(**kwargs: object) -> object:
        captured["__targets_proxy"] = kwargs.get("targets", [])
        return fake_run(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(pipeline_mod, "_run_async_pipeline", sync_dispatcher)
    monkeypatch.setattr(pipeline_mod.asyncio, "run", fake_asyncio_run)


def test_m3_t1_cohort_flag_deprecated(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    """Sprint Q.0.5: --m3-t1-cohort emits DeprecationWarning + resolves to T1_COUNTRIES.

    Stubs the dispatcher + asyncio.run so the test stays in-process and
    doesn't touch live connectors / DB sessions. Captures the targets
    list passed to the dispatcher to assert the deprecated flag still
    resolves to the unified 12-country cohort.
    """
    captured: dict[str, object] = {}
    _stub_main(monkeypatch, captured)

    with (
        pytest.warns(DeprecationWarning, match="m3-t1-cohort"),
        pytest.raises(SystemExit) as excinfo,
    ):
        pipeline_mod.main(
            country="",
            target_date="2026-04-23",
            all_t1=False,
            m3_t1_cohort=True,
            backend="default",
            fred_api_key="",
            te_api_key="",
            cache_dir=str(tmp_path),
            history_years=15,
        )
    assert excinfo.value.code == 0
    assert captured["targets"] == list(T1_COUNTRIES)


def test_all_t1_flag_resolves_to_unified_cohort(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: object,
    recwarn: pytest.WarningsRecorder,
) -> None:
    """Sprint Q.0.5: --all-t1 dispatches the 12-country unified cohort (no warning)."""
    captured: dict[str, object] = {}
    _stub_main(monkeypatch, captured)

    with pytest.raises(SystemExit) as excinfo:
        pipeline_mod.main(
            country="",
            target_date="2026-04-23",
            all_t1=True,
            m3_t1_cohort=False,
            backend="default",
            fred_api_key="",
            te_api_key="",
            cache_dir=str(tmp_path),
            history_years=15,
        )
    assert excinfo.value.code == 0
    assert captured["targets"] == list(T1_COUNTRIES)
    assert len(captured["targets"]) == 12
    # No DeprecationWarning emitted on the canonical --all-t1 path.
    assert not [w for w in recwarn.list if issubclass(w.category, DeprecationWarning)]


def test_monetary_supported_countries_includes_gb_and_jp() -> None:
    """GB (ADR-0007) + JP + CA + AU + NZ + CH + NO + SE + DK stay; US + EA present.

    Sprint Q.0.5 unification: GB / JP / CA / AU / EA now live in the
    default :data:`T1_COUNTRIES` cohort; CH / NO / SE / DK / NZ remain
    opt-in via ``--country`` until promoted by future sprints.
    """
    for country in (
        "GB",
        "JP",
        "CA",
        "AU",
        "NZ",
        "CH",
        "NO",
        "SE",
        "DK",
        "US",
        "EA",
    ):
        assert country in MONETARY_SUPPORTED_COUNTRIES
    # CH / NO / SE / DK / NZ remain outside the default --all-t1 cohort.
    for country in ("NZ", "CH", "NO", "SE", "DK"):
        assert country not in T1_COUNTRIES


def test_monetary_supported_countries_preserves_uk_alias() -> None:
    """Backward compat: "UK" remains accepted per ADR-0007 deprecation window."""
    assert "UK" in MONETARY_SUPPORTED_COUNTRIES


def test_warn_if_deprecated_alias_logs_on_uk(capsys: pytest.CaptureFixture[str]) -> None:
    """--country UK emits ``monetary_pipeline.deprecated_country_alias`` warning.

    structlog renders to stdout by default; capsys captures the event.
    """
    _warn_if_deprecated_alias("UK")
    captured = capsys.readouterr()
    assert "deprecated_country_alias" in captured.out
    assert "alias=UK" in captured.out
    assert "canonical=GB" in captured.out


def test_warn_if_deprecated_alias_silent_on_gb(capsys: pytest.CaptureFixture[str]) -> None:
    """Canonical GB must not emit the deprecation log."""
    _warn_if_deprecated_alias("GB")
    captured = capsys.readouterr()
    assert "deprecated_country_alias" not in captured.out


def test_warn_if_deprecated_alias_silent_on_us(capsys: pytest.CaptureFixture[str]) -> None:
    """Existing canonical codes untouched by the alias helper."""
    _warn_if_deprecated_alias("US")
    captured = capsys.readouterr()
    assert "deprecated_country_alias" not in captured.out


async def test_run_one_gb_synthetic_persists_m1(session: Session) -> None:
    """GB canonical synthetic bundle — pipeline persists M1 end-to-end."""
    outcome = await run_one(session, "GB", date(2024, 12, 31), inputs_builder=_synthetic_builder)
    assert outcome.persisted["m1"] == 1
    assert session.query(M1Row).filter(M1Row.country_code == "GB").count() == 1


async def test_run_one_uk_synthetic_persists_m1(session: Session) -> None:
    """Legacy UK synthetic bundle — backward-compat path during carve-out.

    Synthetic builder is country-agnostic (pass-through); this exercises
    the run_one library entry point with the pre-rename country code
    that operators may still be supplying. Will be retired once
    builders.py carve-out closes (post-Sprint-L chore commit).
    """
    outcome = await run_one(session, "UK", date(2024, 12, 31), inputs_builder=_synthetic_builder)
    assert outcome.persisted["m1"] == 1
    assert session.query(M1Row).filter(M1Row.country_code == "UK").count() == 1


async def test_run_one_jp_synthetic_persists_m1(session: Session) -> None:
    """JP synthetic bundle — pipeline persists M1 via the TE-primary cascade.

    Mirrors the UK synthetic-bundle smoke — the live builder leaves M2/M4
    None via ``InsufficientDataError`` catch (scaffold raises pending
    CAL-JP-OUTPUT-GAP + CAL-JP-M4-FCI), but with a synthetic builder the
    M2/M4 rows persist too so we can assert end-to-end routing.
    """
    outcome = await run_one(session, "JP", date(2024, 12, 31), inputs_builder=_synthetic_builder)
    assert outcome.persisted["m1"] == 1
    assert session.query(M1Row).filter(M1Row.country_code == "JP").count() == 1


async def test_run_one_ca_synthetic_persists_m1(session: Session) -> None:
    """CA synthetic bundle — pipeline persists M1 via the TE-primary cascade.

    Mirrors the JP / UK synthetic-bundle smoke — live builders leave
    M2/M4 as None via ``InsufficientDataError`` catch (scaffold raises
    pending CAL-130 / CAL-131 / CAL-134), but the synthetic builder
    passes through so the M1/M2/M4 routing is exercised end-to-end.
    """
    outcome = await run_one(session, "CA", date(2024, 12, 31), inputs_builder=_synthetic_builder)
    assert outcome.persisted["m1"] == 1
    assert session.query(M1Row).filter(M1Row.country_code == "CA").count() == 1


async def test_run_one_au_synthetic_persists_m1(session: Session) -> None:
    """AU synthetic bundle — pipeline persists M1 via the TE-primary cascade.

    Mirrors the JP / CA synthetic-bundle smoke — live builders leave
    M2/M4 as None via ``InsufficientDataError`` catch (scaffold raises
    pending CAL-AU-CPI / CAL-AU-GAP / CAL-AU-M4-FCI), but the
    synthetic builder passes through so the M1/M2/M4 routing is
    exercised end-to-end.
    """
    outcome = await run_one(session, "AU", date(2024, 12, 31), inputs_builder=_synthetic_builder)
    assert outcome.persisted["m1"] == 1
    assert session.query(M1Row).filter(M1Row.country_code == "AU").count() == 1


async def test_run_one_nz_synthetic_persists_m1(session: Session) -> None:
    """NZ synthetic bundle — pipeline persists M1 via the TE-primary cascade.

    Mirrors the AU / CA synthetic-bundle smoke — live builders leave
    M2/M4 as None via ``InsufficientDataError`` catch (scaffold raises
    pending CAL-NZ-CPI / CAL-NZ-M2-OUTPUT-GAP / CAL-NZ-M4-FCI), but
    the synthetic builder passes through so the M1/M2/M4 routing is
    exercised end-to-end.
    """
    outcome = await run_one(session, "NZ", date(2024, 12, 31), inputs_builder=_synthetic_builder)
    assert outcome.persisted["m1"] == 1
    assert session.query(M1Row).filter(M1Row.country_code == "NZ").count() == 1


# ---------------------------------------------------------------------------
# Sprint C — OECD EO connector lifecycle in _build_live_connectors
# ---------------------------------------------------------------------------


def test_build_live_connectors_references_oecd_eo() -> None:
    """Sprint C: ``_build_live_connectors`` wires the OECD EO class.

    Unit-level check using ``inspect.getsource`` — proves the function
    imports and instantiates ``OECDEOConnector`` + passes it to the
    builder + includes it in the connector lifecycle list, without
    actually spinning up the 12 live httpx clients the full function
    creates (which leaked unclosed sockets across test boundaries in
    earlier Sprint C iterations, surfacing as
    ``PytestUnraisableExceptionWarning`` in unrelated suites).

    The end-to-end lifecycle is covered by
    ``tests/integration/test_daily_monetary_oecd_eo_sprint_c.py::
    test_m2_ca_raise_message_reflects_oecd_eo_live`` (``@slow``).
    """
    import inspect  # noqa: PLC0415

    from sonar.pipelines.daily_monetary_indices import (  # noqa: PLC0415
        _build_live_connectors,
    )

    src = inspect.getsource(_build_live_connectors)
    # Import brought in (used for construction).
    assert "from sonar.connectors.oecd_eo import OECDEOConnector" in src
    # Constructed with the cache dir convention used by siblings.
    assert 'OECDEOConnector(cache_dir=f"{cache_dir}/oecd_eo")' in src
    # Passed as ``oecd_eo=...`` kwarg on the builder.
    assert "oecd_eo=oecd_eo" in src
    # Included in the ``connectors`` list for ``aclose()`` teardown.
    assert "oecd_eo," in src


# ---------------------------------------------------------------------------
# Sprint F — M2 compute-mode classifier + pipeline observability
# ---------------------------------------------------------------------------


def test_classify_m2_compute_mode_full() -> None:
    from sonar.pipelines.daily_monetary_indices import (  # noqa: PLC0415
        _classify_m2_compute_mode,
    )

    flags = (
        "CA_BANK_RATE_TE_PRIMARY",
        "CA_M2_CPI_TE_LIVE",
        "CA_M2_INFLATION_FORECAST_TE_LIVE",
        "CA_M2_OUTPUT_GAP_OECD_EO_LIVE",
        "CA_M2_FULL_COMPUTE_LIVE",
    )
    assert _classify_m2_compute_mode(flags) == "FULL"


def test_classify_m2_compute_mode_partial() -> None:
    from sonar.pipelines.daily_monetary_indices import (  # noqa: PLC0415
        _classify_m2_compute_mode,
    )

    flags = (
        "AU_CASH_RATE_TE_PRIMARY",
        "AU_M2_CPI_TE_LIVE",
        "AU_M2_INFLATION_FORECAST_UNAVAILABLE",
        "AU_M2_OUTPUT_GAP_OECD_EO_LIVE",
        "AU_M2_PARTIAL_COMPUTE",
        "AU_M2_CPI_SPARSE_MONTHLY",
    )
    assert _classify_m2_compute_mode(flags) == "PARTIAL"


def test_classify_m2_compute_mode_legacy_us_canonical() -> None:
    """US canonical CBO path emits no Sprint F FULL / PARTIAL flags → LEGACY."""
    from sonar.pipelines.daily_monetary_indices import (  # noqa: PLC0415
        _classify_m2_compute_mode,
    )

    flags = ("INFLATION_FORECAST_PROXY_UMICH",)
    assert _classify_m2_compute_mode(flags) == "LEGACY"


def test_classify_m2_compute_mode_full_takes_precedence_over_partial() -> None:
    """A FULL flag wins over a stray PARTIAL — contract holds for flag-reuse."""
    from sonar.pipelines.daily_monetary_indices import (  # noqa: PLC0415
        _classify_m2_compute_mode,
    )

    flags = (
        "GB_M2_PARTIAL_COMPUTE",  # impossible in practice but tests dominance
        "GB_M2_FULL_COMPUTE_LIVE",
    )
    assert _classify_m2_compute_mode(flags) == "FULL"


def test_classify_m4_compute_mode_full_sprint_j() -> None:
    """Sprint J EA-proxy tier — 5-component FULL compute flag wins."""
    from sonar.pipelines.daily_monetary_indices import (  # noqa: PLC0415
        _classify_m4_compute_mode,
    )

    flags = (
        "EA_M4_VOL_TE_LIVE",
        "EA_M4_CREDIT_SPREAD_FRED_OAS_LIVE",
        "EA_M4_10Y_YIELD_LIVE",
        "EA_M4_NEER_BIS_LIVE",
        "EA_M4_NEER_MONTHLY_CADENCE",
        "EA_M4_MORTGAGE_ECB_MIR_LIVE",
        "EA_M4_FULL_COMPUTE_LIVE",
    )
    assert _classify_m4_compute_mode(flags) == "FULL"


def test_classify_m4_compute_mode_scaffold() -> None:
    """Sprint J SCAFFOLD_ONLY flag surfaces through the classifier."""
    from sonar.pipelines.daily_monetary_indices import (  # noqa: PLC0415
        _classify_m4_compute_mode,
    )

    flags = ("GB_M4_NEER_BIS_LIVE", "GB_M4_SCAFFOLD_ONLY")
    assert _classify_m4_compute_mode(flags) == "SCAFFOLD"


def test_classify_m4_compute_mode_canonical_us_nfci() -> None:
    """US NFCI direct-provider path emits no Sprint J flags → CANONICAL."""
    from sonar.pipelines.daily_monetary_indices import (  # noqa: PLC0415
        _classify_m4_compute_mode,
    )

    flags = ("US_M4_NFCI_FRED_LIVE",)
    assert _classify_m4_compute_mode(flags) == "CANONICAL"


def test_classify_m4_compute_mode_full_takes_precedence_over_scaffold() -> None:
    """FULL beats SCAFFOLD when both happen to appear — contract invariant."""
    from sonar.pipelines.daily_monetary_indices import (  # noqa: PLC0415
        _classify_m4_compute_mode,
    )

    flags = ("DE_M4_SCAFFOLD_ONLY", "DE_M4_FULL_COMPUTE_LIVE")
    assert _classify_m4_compute_mode(flags) == "FULL"


def test_monetary_supported_countries_includes_sprint_j_ea_members() -> None:
    """Sprint J C6 — DE/FR/IT/ES/NL/PT added for M4 FCI dispatch."""
    from sonar.pipelines.daily_monetary_indices import (  # noqa: PLC0415
        MONETARY_SUPPORTED_COUNTRIES,
    )

    for cc in ("DE", "FR", "IT", "ES", "NL", "PT"):
        assert cc in MONETARY_SUPPORTED_COUNTRIES, cc


# ---------------------------------------------------------------------------
# Sprint T0 ADR-0011 — exit-code sanitization + per-country isolation
# ---------------------------------------------------------------------------


def test_curves_shipped_countries_matches_daily_curves() -> None:
    """The monetary pipeline's T1-curves-shipped set must match the set
    the curves pipeline actually ships. Guard against drift.
    """
    from sonar.pipelines.daily_curves import CURVE_SUPPORTED_COUNTRIES  # noqa: PLC0415
    from sonar.pipelines.daily_monetary_indices import (  # noqa: PLC0415
        _CURVES_SHIPPED_COUNTRIES,
    )

    assert _CURVES_SHIPPED_COUNTRIES == CURVE_SUPPORTED_COUNTRIES


def test_ea_per_country_deferred_disjoint_from_us() -> None:
    """EA-per-country-deferred set covers the six EA members whose M1/M2
    raise NotImplementedError. US is the canonical path and must not
    appear in the deferral set — otherwise a US no_inputs would be
    incorrectly downgraded to info level.
    """
    from sonar.pipelines.daily_monetary_indices import (  # noqa: PLC0415
        _EA_PER_COUNTRY_DEFERRED,
    )

    expected = frozenset({"DE", "FR", "IT", "ES", "NL", "PT"})
    assert expected == _EA_PER_COUNTRY_DEFERRED
    assert "US" not in _EA_PER_COUNTRY_DEFERRED


def test_monetary_run_outcomes_default_empty() -> None:
    """Sprint T0 _MonetaryRunOutcomes default constructs with four
    empty buckets — invariant relied on by the summary-emit Principle 4.
    """
    from sonar.pipelines.daily_monetary_indices import _MonetaryRunOutcomes  # noqa: PLC0415

    outcomes = _MonetaryRunOutcomes()
    assert outcomes.persisted == []
    assert outcomes.no_inputs == []
    assert outcomes.duplicate == []
    assert outcomes.failed == []


# ---------------------------------------------------------------------------
# Sprint T0.1 — ADR-0011 Principle 6 async-lifecycle regression guards
# ---------------------------------------------------------------------------


async def test_async_lifecycle_single_loop(session: Session) -> None:
    """ADR-0011 Principle 6 — dispatcher awaits the inputs builder inside
    a single event loop for every country. Regression guard for the
    pre-fix ``asyncio.run()`` per-country anti-pattern that killed the
    httpx transports after the first country (CAL-MONETARY-SINGLE-EVENT-LOOP).

    Recording the ``id(asyncio.get_running_loop())`` at each builder
    invocation and asserting the set size is 1 proves the whole run
    is under one loop — the exact property the httpx transports rely
    on.
    """
    import asyncio as _asyncio  # noqa: PLC0415

    from sonar.pipelines.daily_monetary_indices import (  # noqa: PLC0415
        _dispatch_country_loop,
    )

    seen_loop_ids: set[int] = set()

    async def _loop_tracking_builder(
        sess: Session,
        country_code: str,
        observation_date: date,
    ) -> MonetaryIndicesInputs:
        seen_loop_ids.add(id(_asyncio.get_running_loop()))
        return await _synthetic_builder(sess, country_code, observation_date)

    outcomes = await _dispatch_country_loop(
        session=session,
        targets=["US", "DE", "PT"],
        observation_date=date(2024, 12, 31),
        inputs_builder=_loop_tracking_builder,
        db_backed_builder=None,  # type: ignore[arg-type]
    )

    assert len(seen_loop_ids) == 1, (
        f"Expected single event loop across countries; saw {len(seen_loop_ids)}."
    )
    assert len(outcomes.persisted) == 3
    assert outcomes.failed == []


async def test_country_failure_isolation(session: Session) -> None:
    """ADR-0011 Principle 2 — one country's uncaught exception buckets
    into ``failed`` but subsequent countries keep running.

    Mocks a builder that raises on country #2 (DE) and asserts country
    #1 (US) and country #3 (PT) still persisted.
    """
    from sonar.pipelines.daily_monetary_indices import (  # noqa: PLC0415
        _dispatch_country_loop,
    )

    async def _selectively_failing_builder(
        sess: Session,
        country_code: str,
        observation_date: date,
    ) -> MonetaryIndicesInputs:
        if country_code.upper() == "DE":
            raise RuntimeError("synthetic connector failure")
        return await _synthetic_builder(sess, country_code, observation_date)

    outcomes = await _dispatch_country_loop(
        session=session,
        targets=["US", "DE", "PT"],
        observation_date=date(2024, 12, 31),
        inputs_builder=_selectively_failing_builder,
        db_backed_builder=None,  # type: ignore[arg-type]
    )

    assert outcomes.persisted == ["US", "PT"]
    assert len(outcomes.failed) == 1
    failed_country, failed_msg = outcomes.failed[0]
    assert failed_country == "DE"
    assert "synthetic connector failure" in failed_msg


async def test_exit_code_success_on_all_duplicate(session: Session) -> None:
    """ADR-0011 Principle 3 — if every country bucketed into
    ``duplicate`` (idempotent re-run), the pipeline must still exit 0.

    Exercises the dispatcher bucket-routing: two countries, both
    ``DuplicatePersistError`` via a builder + stub session combination
    that triggers the duplicate path. The assertion targets the
    main() exit-code predicate:

        failed and not persisted and not no_inputs and not duplicate

    which must evaluate False when the only bucket populated is
    ``duplicate`` (→ exit 0).
    """
    from sonar.db.persistence import DuplicatePersistError  # noqa: PLC0415
    from sonar.pipelines.daily_monetary_indices import (  # noqa: PLC0415
        _dispatch_country_loop,
    )

    async def _raising_builder(
        sess: Session,
        country_code: str,
        observation_date: date,
    ) -> MonetaryIndicesInputs:
        raise DuplicatePersistError(f"already persisted for {country_code}")

    outcomes = await _dispatch_country_loop(
        session=session,
        targets=["US", "DE"],
        observation_date=date(2024, 12, 31),
        inputs_builder=_raising_builder,
        db_backed_builder=None,  # type: ignore[arg-type]
    )

    assert outcomes.duplicate == ["US", "DE"]
    assert outcomes.persisted == []
    assert outcomes.no_inputs == []
    assert outcomes.failed == []

    # Guard the main() exit-code predicate verbatim (ADR-0011 Principle 3).
    should_exit_nonzero = bool(
        outcomes.failed
        and not outcomes.persisted
        and not outcomes.no_inputs
        and not outcomes.duplicate
    )
    assert should_exit_nonzero is False


async def test_connector_aclose_lifecycle() -> None:
    """ADR-0011 Principle 6 — ``_run_async_pipeline`` calls ``aclose()``
    exactly once per registered connector under a single event loop.

    Feeds a synthetic ``_build_live_connectors`` via monkeypatch that
    returns stub connectors tracking their own ``aclose`` invocations
    and the loop id at teardown; asserts:

    1. every stub was closed exactly once,
    2. all closures happened under the same loop id as the pipeline run.
    """
    import asyncio as _asyncio  # noqa: PLC0415
    from dataclasses import dataclass as _dataclass, field as _field  # noqa: PLC0415
    from unittest.mock import patch  # noqa: PLC0415

    from sonar.pipelines.daily_monetary_indices import (  # noqa: PLC0415
        _run_async_pipeline,
    )

    @_dataclass
    class _StubConnector:
        name: str
        close_count: int = 0
        close_loop_ids: list[int] = _field(default_factory=list)

        async def aclose(self) -> None:
            self.close_count += 1
            self.close_loop_ids.append(id(_asyncio.get_running_loop()))

    stubs = [_StubConnector(name=f"stub_{i}") for i in range(3)]

    def _fake_build_live_connectors(
        *,
        fred_api_key: str,
        te_api_key: str,
        cache_dir: str,
    ) -> tuple[object, list[object]]:
        # Builder slot is unused here — we pass ``targets=[]`` below so
        # the dispatcher never enters its loop and never invokes the
        # builder factory the live path wires.
        return (None, list(stubs))

    # Run with backend="live" so _build_live_connectors is invoked and
    # the stack registers aclose callbacks, then pass ``targets=[]``
    # so the dispatcher never touches the (None) builder.
    with patch(
        "sonar.pipelines.daily_monetary_indices._build_live_connectors",
        _fake_build_live_connectors,
    ):
        outcomes = await _run_async_pipeline(
            obs_date=date(2024, 12, 31),
            targets=[],  # skip the inputs builder invocation entirely
            backend="live",
            fred_api_key="placeholder",  # pragma: allowlist secret
            te_api_key="",
            cache_dir="/tmp/stub-cache",
            history_years=15,
        )

    assert outcomes.persisted == []
    assert outcomes.failed == []
    # Every stub closed exactly once, all under the same event loop.
    assert [s.close_count for s in stubs] == [1, 1, 1]
    unique_loop_ids = {lid for s in stubs for lid in s.close_loop_ids}
    assert len(unique_loop_ids) == 1


async def test_pipeline_no_asyncio_run_per_country() -> None:
    """Static invariant: the pipeline module must contain exactly one
    ``asyncio.run`` call (at the process entry in ``main``) — zero
    per-country or per-connector ``asyncio.run`` sites.

    Regression guard for the pre-T0.1 anti-pattern (two ``asyncio.run``
    sites: the factory and the aclose loop). If anyone adds another,
    this test fires.
    """
    import inspect  # noqa: PLC0415

    from sonar.pipelines import daily_monetary_indices  # noqa: PLC0415

    src = inspect.getsource(daily_monetary_indices)
    assert src.count("asyncio.run(") == 1, (
        "daily_monetary_indices must host exactly one asyncio.run() site "
        "(main → _run_async_pipeline). Per-country or per-connector "
        "asyncio.run calls violate ADR-0011 Principle 6."
    )
