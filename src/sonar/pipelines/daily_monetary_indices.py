"""Daily monetary indices pipeline — orchestrate M1/M2/M4 persistence.

Mirrors :mod:`sonar.pipelines.daily_economic_indices` (which itself mirrors
the credit + financial templates). Uses the
:class:`sonar.indices.monetary.builders.MonetaryInputsBuilder` facade
shipped in Week 6 Sprint 2b and the sync
:func:`sonar.indices.monetary.orchestrator.compute_all_monetary_indices`
orchestrator.

**Scope this sprint (Week 7 Sprint B)**:

- M1 / M2 / M4 live via the async builders on ``MonetaryInputsBuilder``.
  Non-US/EA combinations raise :class:`NotImplementedError` inside the
  facade and the pipeline logs a ``monetary_pipeline.builder_skipped``
  warning instead of crashing.
- M3 Market Expectations is **not** wired to the live path — its inputs
  come from persisted NSS + expected-inflation overlays (L2), not from
  L0 connectors directly, same as E2 in the economic pipeline. M3 stays
  out of this sprint and the pipeline persists only M1/M2/M4.
- EA M2 / M4 are explicitly not supported by the Sprint-2b builder
  (``NotImplementedError`` with a Week 7 pointer). The pipeline catches
  those and routes to a structured skip log so the --all-t1 loop
  continues.

CLI::

    python -m sonar.pipelines.daily_monetary_indices --country US --date 2024-12-31
    python -m sonar.pipelines.daily_monetary_indices --all-t1 --date 2024-12-31

Exit codes (ADR-0011 aligned, Sprint T0 2026-04-23):

- ``0`` — happy path: pipeline ran to completion. Includes all
  mixes of (persisted countries + expected no_inputs for EA members
  with CAL-M2-EA-PER-COUNTRY deferred + duplicate re-run skips).
- ``1`` — uncaught structural exception at the orchestrator boundary
  (per-country failures are caught + logged + continued).
- ``4`` — IO / connector init failure before the country loop runs.

Sprint T0 removed exit code 3 (duplicate) from the happy-path contract
per ADR-0011 Principle 1: duplicates are skip + continue and no_inputs
for EA-per-country deferred builders is expected, not fatal.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Protocol

import structlog
import typer

from sonar.db.persistence import (
    DuplicatePersistError,
    persist_many_monetary_results,
)
from sonar.db.session import SessionLocal
from sonar.indices.monetary.builders import MonetaryInputsBuilder
from sonar.indices.monetary.m3_market_expectations import (
    compute_m3_market_expectations_anchor,
)
from sonar.indices.monetary.orchestrator import (
    MonetaryIndicesInputs,
    MonetaryIndicesResults,
    compute_all_monetary_indices,
)
from sonar.overlays.exceptions import InsufficientDataError

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from sonar.indices.base import IndexResult
    from sonar.indices.monetary.db_backed_builder import MonetaryDbBackedInputsBuilder


log = structlog.get_logger()

__all__ = [
    "MONETARY_SUPPORTED_COUNTRIES",
    "T1_7_COUNTRIES",
    "InputsBuilder",
    "MonetaryPipelineOutcome",
    "build_live_monetary_inputs",
    "default_inputs_builder",
    "main",
    "run_one",
]

# Kept module-private — public surface guarded via __all__. Tests import
# directly via module path.

T1_7_COUNTRIES: tuple[str, ...] = ("US", "DE", "PT", "IT", "ES", "FR", "NL")

# Monetary pipeline accepts GB via BoE → FRED cascade (sprint 8-I),
# JP via BoJ → FRED cascade (sprint 8-L), CA via BoC Valet → FRED
# cascade (sprint 9-S), AU via RBA F1 CSV → FRED cascade (sprint
# 9-T), CH via SNB zimoma/SARON → FRED cascade (sprint 9-V), NO via
# Norges Bank DataAPI SDMX-JSON → FRED cascade (sprint 9-X-NO), SE
# via Riksbank Swea SECBREPOEFF → FRED cascade (sprint 9-W-SE), and
# DK via Nationalbanken Statbank.dk DNRENTD/OIBNAA → FRED cascade
# (sprint 9-Y-DK; first EUR-peg country in the family — emits
# DK_INFLATION_TARGET_IMPORTED_FROM_EA always since the inflation
# anchor is imported from the ECB via the DKK/EUR ERM-II peg). All
# stay separate from T1_7_COUNTRIES so --all-t1 preserves the
# historical 7-country semantics; callers opt in via --country GB
# (or the deprecated "UK" alias — ADR-0007), --country JP, --country
# CA, --country AU, --country CH, --country NO, --country SE, or
# --country DK.
#
# Backward compat: "UK" preserved as deprecated alias per ADR-0007.
# CLI emits a structlog deprecation warning when ``--country UK`` is
# passed and forwards the code verbatim; builders.py's
# :class:`MonetaryInputsBuilder` dispatch silently normalises "UK" →
# "GB" and invokes :func:`build_m1_gb_inputs` (CAL-128 closure — post-
# Sprint-L chore commit). End-to-end GB dispatch is live; alias path
# scheduled for removal Week 10 Day 1.
MONETARY_SUPPORTED_COUNTRIES: tuple[str, ...] = (
    "US",
    "EA",
    # Sprint J (Week 10) — EA-member M4 FCI FULL compute via shared-EA
    # proxy pattern (VSTOXX + BAML EA HY OAS + BIS NEER + ECB MIR +
    # TE 10Y). M1 / M2 for these countries remain NotImplementedError
    # (policy-rate is shared ECB DFR; per-country Taylor is academically
    # ambiguous — CAL-M2-EA-PER-COUNTRY) and are captured as
    # `monetary_pipeline.builder_skipped` in the live-input logger.
    "DE",
    "FR",
    "IT",
    "ES",
    "NL",
    "PT",
    "GB",
    "UK",
    "JP",
    "CA",
    "AU",
    "NZ",
    "CH",
    "NO",
    "SE",
    "DK",
)

# ADR-0007 deprecated country aliases. Map ``alias -> canonical``.
_DEPRECATED_COUNTRY_ALIASES: dict[str, str] = {"UK": "GB"}


def _warn_if_deprecated_alias(country_code: str) -> None:
    """Emit a structlog deprecation warning when ``country_code`` is an alias.

    Canonical codes are silent. Used at CLI entry to signal migration to
    operators still passing ``--country UK``. The alias value is passed
    through verbatim to downstream builders; :class:`MonetaryInputsBuilder`
    normalises "UK" → "GB" at dispatch and persists rows under the
    canonical "GB" country_code (ADR-0007, CAL-128).
    """
    upper = country_code.upper()
    canonical = _DEPRECATED_COUNTRY_ALIASES.get(upper)
    if canonical is None:
        return
    log.warning(
        "monetary_pipeline.deprecated_country_alias",
        alias=upper,
        canonical=canonical,
        adr="ADR-0007",
    )


EXIT_OK = 0
EXIT_NO_INPUTS = 1
EXIT_DUPLICATE = 3  # retained for back-compat; unreachable under ADR-0011
EXIT_IO = 4

# T1 curves-ship cohort — countries with shipped NSS curves (Sprint T0
# 2026-04-23 / post-Sprint-I). For these countries, m3_forwards_missing
# is a genuine upstream problem (curves were expected to have persisted
# the prior daily_curves run). For countries outside this set, m3
# forwards absent is the expected state (no curves shipped). Split used
# by :func:`run_one` to log at warning vs info level so journal signal
# stays proportional to actual coverage expectations.
_CURVES_SHIPPED_COUNTRIES: frozenset[str] = frozenset(
    {"US", "DE", "EA", "GB", "JP", "CA", "IT", "ES", "FR", "PT"}
)

# EA-per-country-deferred members — M1 (policy rate is shared ECB DFR)
# and M2 (academically ambiguous per-country Taylor rule) raise
# NotImplementedError by design per CAL-M2-EA-PER-COUNTRY (deferred
# Phase 2+). no_inputs for these countries is **expected**, not an
# error. Split used by the --all-t1 dispatcher to downgrade the
# no_inputs log to info level.
_EA_PER_COUNTRY_DEFERRED: frozenset[str] = frozenset({"DE", "FR", "IT", "ES", "NL", "PT"})


class InputsBuilder(Protocol):
    """Build :class:`MonetaryIndicesInputs` for a ``(country, date)``.

    Async by contract — lives inside the single-event-loop pipeline
    scope per ADR-0011 Principle 6. The default path returns an empty
    bundle (``await``-friendly), the live path awaits connector I/O
    via :func:`build_live_monetary_inputs`.
    """

    async def __call__(
        self,
        session: Session,
        country_code: str,
        observation_date: date,
    ) -> MonetaryIndicesInputs: ...


async def default_inputs_builder(
    session: Session,  # noqa: ARG001 — Protocol compatibility
    country_code: str,
    observation_date: date,
) -> MonetaryIndicesInputs:
    """MVP default — empty bundle so orchestrator skips gracefully (test path)."""
    return MonetaryIndicesInputs(
        country_code=country_code,
        observation_date=observation_date,
    )


def _classify_m2_compute_mode(flags: tuple[str, ...]) -> str:
    """Return ``"FULL"`` / ``"PARTIAL"`` / ``"LEGACY"`` per Sprint F flag contract.

    - ``FULL``: any flag ending ``_M2_FULL_COMPUTE_LIVE`` (Sprint F
      Commits 4-5 builders that wire all four Taylor components).
    - ``PARTIAL``: any flag ending ``_M2_PARTIAL_COMPUTE`` (Sprint F
      builders with forecast missing — Taylor-forward variant
      skipped but base 1993 / 1999 variants still compute).
    - ``LEGACY``: none of the Sprint F flags present (US canonical
      CBO path or any builder that predates Sprint F). Operators
      read this as "no Sprint F observability on this builder".
    """
    for flag in flags:
        if flag.endswith("_M2_FULL_COMPUTE_LIVE"):
            return "FULL"
    for flag in flags:
        if flag.endswith("_M2_PARTIAL_COMPUTE"):
            return "PARTIAL"
    return "LEGACY"


def _classify_m4_compute_mode(flags: tuple[str, ...]) -> str:
    """Return ``"FULL"`` / ``"SCAFFOLD"`` / ``"CANONICAL"`` per Sprint J flag contract.

    Mirrors :func:`_classify_m2_compute_mode` but for the M4 FCI axis.
    M4 has strict semantics: the compute-side enforces
    ``MIN_CUSTOM_COMPONENTS = 5`` so the partial bucket is absent by
    construction — a sub-5 country is either a SCAFFOLD (builder
    raised ``InsufficientDataError``) or absent entirely from the
    ``results.m4`` slot.

    - ``FULL``: any flag ending ``_M4_FULL_COMPUTE_LIVE`` (Sprint J
      EA-proxy tier — EA aggregate + DE/FR/IT/ES/NL/PT).
    - ``SCAFFOLD``: any flag ending ``_M4_SCAFFOLD_ONLY`` (emitted by
      builders that compose partial inputs but the compute side will
      still reject; included for observability symmetry).
    - ``CANONICAL``: none of the Sprint J flags present. Covers the
      US NFCI direct-provider path (spec §4 step 1 short-circuit)
      and any future builder that predates Sprint J.
    """
    for flag in flags:
        if flag.endswith("_M4_FULL_COMPUTE_LIVE"):
            return "FULL"
    for flag in flags:
        if flag.endswith("_M4_SCAFFOLD_ONLY"):
            return "SCAFFOLD"
    return "CANONICAL"


async def build_live_monetary_inputs(
    country_code: str,
    observation_date: date,
    *,
    builder: MonetaryInputsBuilder,
    history_years: int = 15,
) -> MonetaryIndicesInputs:
    """Live builder — invokes the MonetaryInputsBuilder facade.

    ``NotImplementedError`` from the facade for non-supported
    ``(country, index)`` combinations (e.g., M2 EA, M4 EA) is caught
    and logged as ``monetary_pipeline.builder_skipped``; the slot is
    left ``None`` and the orchestrator skips that sub-index.
    ``InsufficientDataError`` is likewise caught.

    ``history_years`` defaults to 15 (Tier-4 fallback) to keep live
    canary wall-clock tractable; callers can opt into the canonical
    30Y via the CLI ``--history-years`` flag.
    """
    country = country_code.upper()
    m1 = m2 = m4 = None
    try:
        m1 = await builder.build_m1_inputs(country, observation_date, history_years=history_years)
    except (NotImplementedError, InsufficientDataError, ValueError) as exc:
        log.warning(
            "monetary_pipeline.builder_skipped",
            index="m1",
            country=country,
            error=str(exc),
        )
    try:
        m2 = await builder.build_m2_inputs(country, observation_date, history_years=history_years)
    except (NotImplementedError, InsufficientDataError, ValueError) as exc:
        log.warning(
            "monetary_pipeline.builder_skipped",
            index="m2",
            country=country,
            error=str(exc),
        )
    else:
        log.info(
            "monetary_pipeline.m2_compute_mode",
            country=country,
            observation_date=observation_date.isoformat(),
            mode=_classify_m2_compute_mode(m2.upstream_flags),
            flags=tuple(m2.upstream_flags),
        )
    try:
        m4 = await builder.build_m4_inputs(country, observation_date, history_years=history_years)
    except (NotImplementedError, InsufficientDataError, ValueError) as exc:
        log.warning(
            "monetary_pipeline.builder_skipped",
            index="m4",
            country=country,
            error=str(exc),
        )
    else:
        log.info(
            "monetary_pipeline.m4_compute_mode",
            country=country,
            observation_date=observation_date.isoformat(),
            mode=_classify_m4_compute_mode(m4.upstream_flags),
            flags=tuple(m4.upstream_flags),
        )
    return MonetaryIndicesInputs(
        country_code=country,
        observation_date=observation_date,
        m1=m1,
        m2=m2,
        m4=m4,
    )


@dataclass(frozen=True, slots=True)
class MonetaryPipelineOutcome:
    country_code: str
    observation_date: date
    results: MonetaryIndicesResults
    persisted: dict[str, int]


@dataclass(slots=True)
class _MonetaryRunOutcomes:
    """Bucketed per-country outcomes across a --all-t1 orchestration.

    ADR-0011 Principle 4 — end-of-run summary emit. Four disjoint
    buckets: persisted (at least one index row landed), no_inputs
    (builders all skipped / returned empty), duplicate (pre-existing
    rows — idempotent no-op re-run), failed (uncaught exception per
    country).
    """

    persisted: list[str] = field(default_factory=list)
    no_inputs: list[str] = field(default_factory=list)
    duplicate: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)


async def _dispatch_country_loop(
    *,
    session: Session,
    targets: list[str],
    observation_date: date,
    inputs_builder: InputsBuilder,
    db_backed_builder: MonetaryDbBackedInputsBuilder,
) -> _MonetaryRunOutcomes:
    """Run each target country; collect outcomes across four buckets.

    ADR-0011 Principle 2 — per-country isolation. A single country's
    exception is logged + bucketed into ``failed`` and the loop
    continues so downstream countries still get a shot.

    ADR-0011 Principle 6 — async lifecycle discipline. This runs
    inside the single pipeline event loop; the inputs builder is
    awaited in-loop (no per-country ``asyncio.run`` churn).
    """
    outcomes = _MonetaryRunOutcomes()
    for c in targets:
        country_upper = c.upper()
        try:
            outcome = await run_one(
                session,
                c,
                observation_date,
                inputs_builder=inputs_builder,
                db_backed_builder=db_backed_builder,
            )
            if sum(outcome.persisted.values()) == 0:
                # ADR-0011 Principle 3: no_inputs is expected for
                # EA-per-country-deferred members (M1/M2 share ECB
                # DFR + academically ambiguous Taylor —
                # CAL-M2-EA-PER-COUNTRY). Downgrade to info for
                # those; warn for other T1 countries where a gap
                # is a genuine signal of upstream absence.
                if country_upper in _EA_PER_COUNTRY_DEFERRED:
                    log.info(
                        "monetary_pipeline.expected_no_inputs",
                        country=country_upper,
                        date=observation_date.isoformat(),
                        reason="ea_per_country_deferred",
                        skips=outcome.results.skips,
                    )
                else:
                    log.warning(
                        "monetary_pipeline.no_inputs",
                        country=country_upper,
                        date=observation_date.isoformat(),
                        skips=outcome.results.skips,
                    )
                outcomes.no_inputs.append(country_upper)
            else:
                outcomes.persisted.append(country_upper)
        except DuplicatePersistError as exc:
            # ADR-0011 Principle 1: duplicate = skip + continue.
            # Unreachable under normal single-process systemd
            # scheduling (pre-check upstream in daily_curves), retained
            # here as defence in depth.
            log.info(
                "monetary_pipeline.duplicate_skipped",
                country=country_upper,
                error=str(exc),
            )
            outcomes.duplicate.append(country_upper)
        except Exception as exc:  # ADR-0011 Principle 2 — per-country isolation
            # Per-country isolation: one country's HTTP / JSON / upstream
            # glitch does not kill the pipeline (Apr 23 natural-fire
            # root cause pattern).
            log.error(
                "monetary_pipeline.country_failed",
                country=country_upper,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            outcomes.failed.append((country_upper, f"{type(exc).__name__}: {exc}"))
    return outcomes


async def run_one(
    session: Session,
    country_code: str,
    observation_date: date,
    *,
    inputs_builder: InputsBuilder | None = None,
    db_backed_builder: MonetaryDbBackedInputsBuilder | None = None,
) -> MonetaryPipelineOutcome:
    """Single ``(country, date)`` pipeline run: build → compute → persist.

    When ``db_backed_builder`` is supplied the pipeline additionally
    reads persisted NSS forwards + EXPINF rows via
    :meth:`MonetaryDbBackedInputsBuilder.build_m3_inputs` and routes the
    computed M3 IndexResult through ``persist_many_monetary_results``'s
    ``m3=`` kwarg (CAL-108). Missing rows keep ``m3=None`` so the
    orchestrator reports a clean skip.

    Async by contract (ADR-0011 Principle 6) — the live input builder
    path awaits connector I/O, and the dispatcher awaits this under a
    single ``asyncio.run`` at the process entry. Compute + persist
    stay synchronous; only the inputs-build path crosses the event
    loop boundary.
    """
    builder = inputs_builder or default_inputs_builder
    inputs = await builder(session, country_code, observation_date)
    results = compute_all_monetary_indices(inputs)

    m3_result: IndexResult | None = None
    if db_backed_builder is not None:
        country_upper = country_code.upper()
        if country_upper not in _CURVES_SHIPPED_COUNTRIES:
            # ADR-0011 Principle 1 / 3: skip m3 attempt when curves
            # upstream is not shipped for this country (PT / NL / AU /
            # NZ / CH / SE / NO / DK). The forwards row will not exist;
            # the underlying library would emit
            # ``m3_db_backed.forwards_missing`` warning which is noise
            # for non-shipped countries. Info-level skip keeps journals
            # clean; the signal for genuine upstream failure is
            # preserved for T1 shipped countries (US/DE/EA/GB/JP/CA/
            # IT/ES/FR) where forwards_missing remains a warning.
            log.info(
                "monetary_pipeline.m3_skipped_upstream_not_shipped",
                country=country_upper,
                date=observation_date.isoformat(),
                reason="country_outside_curves_ship_cohort",
            )
            m3_inputs = None
        else:
            try:
                m3_inputs = db_backed_builder.build_m3_inputs(country_code, observation_date)
            except Exception as exc:
                log.warning(
                    "monetary_pipeline.db_backed_m3_error",
                    country=country_code,
                    error=str(exc),
                )
                m3_inputs = None
        if m3_inputs is not None:
            try:
                m3_result = compute_m3_market_expectations_anchor(m3_inputs)
            except InsufficientDataError as exc:
                log.warning(
                    "monetary_pipeline.m3_insufficient_data",
                    country=country_code,
                    error=str(exc),
                )

    persisted = persist_many_monetary_results(session, results, m3=m3_result)
    log.info(
        "monetary_pipeline.persisted",
        country=country_code,
        date=observation_date.isoformat(),
        persisted=persisted,
        skips=results.skips,
    )
    return MonetaryPipelineOutcome(
        country_code=country_code,
        observation_date=observation_date,
        results=results,
        persisted=persisted,
    )


def _build_live_connectors(
    *,
    fred_api_key: str,
    te_api_key: str,
    cache_dir: str,
) -> tuple[MonetaryInputsBuilder, list[object]]:
    """Instantiate live monetary connectors + bundle them for aclose().

    TE is optional: when ``te_api_key`` is empty the builder falls
    through to BoE → FRED (stale-flagged) for the GB cascade, BoJ →
    FRED (stale-flagged) for the JP cascade, BoC Valet → FRED
    (stale-flagged) for the CA cascade, RBA F1 CSV → FRED
    (stale-flagged) for the AU cascade, RBNZ B2 → FRED (stale-
    flagged) for the NZ cascade, SNB zimoma/SARON → FRED
    (stale-flagged) for the CH cascade, and Norges Bank DataAPI →
    FRED (stale-flagged) for the NO cascade. Note the CA / AU / CH /
    NO secondary slots are all reachable public endpoints so
    --te-api-key="" still delivers fresh M1 rows for those countries
    when the native host is up — the NZ RBNZ host currently
    perimeter-403s (CAL-NZ-RBNZ-TABLES) so NZ without TE lands on
    FRED with NZ_OCR_FRED_FALLBACK_STALE + CALIBRATION_STALE flags.

    Sprint C (Week 10) adds the :class:`~sonar.connectors.oecd_eo.
    OECDEOConnector` to the bundle. OECD EO is public (no auth) so it
    is always instantiated — the M2 builders use it to fetch the
    canonical annual output gap for the 8 Week-9 T1 countries
    (JP / CA / AU / NZ / CH / NO / SE / DK). US stays on the CBO
    GDPPOT quarterly path (strictly finer than OECD EO annual).
    """
    from sonar.connectors.bis import BisConnector  # noqa: PLC0415
    from sonar.connectors.boc import BoCConnector  # noqa: PLC0415
    from sonar.connectors.boe_database import BoEDatabaseConnector  # noqa: PLC0415
    from sonar.connectors.boj import BoJConnector  # noqa: PLC0415
    from sonar.connectors.cbo import CboConnector  # noqa: PLC0415
    from sonar.connectors.ecb_sdw import EcbSdwConnector  # noqa: PLC0415
    from sonar.connectors.fred import FredConnector  # noqa: PLC0415
    from sonar.connectors.nationalbanken import NationalbankenConnector  # noqa: PLC0415
    from sonar.connectors.norgesbank import NorgesBankConnector  # noqa: PLC0415
    from sonar.connectors.oecd_eo import OECDEOConnector  # noqa: PLC0415
    from sonar.connectors.rba import RBAConnector  # noqa: PLC0415
    from sonar.connectors.rbnz import RBNZConnector  # noqa: PLC0415
    from sonar.connectors.riksbank import RiksbankConnector  # noqa: PLC0415
    from sonar.connectors.snb import SNBConnector  # noqa: PLC0415
    from sonar.connectors.te import TEConnector  # noqa: PLC0415

    fred = FredConnector(api_key=fred_api_key, cache_dir=f"{cache_dir}/fred")
    cbo = CboConnector(fred=fred)
    ecb = EcbSdwConnector(cache_dir=f"{cache_dir}/ecb")
    bis = BisConnector(cache_dir=f"{cache_dir}/bis")
    boc = BoCConnector(cache_dir=f"{cache_dir}/boc")
    boe = BoEDatabaseConnector(cache_dir=f"{cache_dir}/boe")
    boj = BoJConnector(cache_dir=f"{cache_dir}/boj")
    rba = RBAConnector(cache_dir=f"{cache_dir}/rba")
    rbnz = RBNZConnector(cache_dir=f"{cache_dir}/rbnz")
    riksbank = RiksbankConnector(cache_dir=f"{cache_dir}/riksbank")
    snb = SNBConnector(cache_dir=f"{cache_dir}/snb")
    norgesbank = NorgesBankConnector(cache_dir=f"{cache_dir}/norgesbank")
    nationalbanken = NationalbankenConnector(cache_dir=f"{cache_dir}/nationalbanken")
    oecd_eo = OECDEOConnector(cache_dir=f"{cache_dir}/oecd_eo")
    te = TEConnector(api_key=te_api_key, cache_dir=f"{cache_dir}/te") if te_api_key else None
    builder = MonetaryInputsBuilder(
        fred=fred,
        cbo=cbo,
        ecb_sdw=ecb,
        boc=boc,
        boe=boe,
        boj=boj,
        rba=rba,
        rbnz=rbnz,
        riksbank=riksbank,
        snb=snb,
        norgesbank=norgesbank,
        nationalbanken=nationalbanken,
        te=te,
        oecd_eo=oecd_eo,
        bis=bis,
    )
    connectors: list[object] = [
        fred,
        ecb,
        bis,
        boc,
        boe,
        boj,
        rba,
        rbnz,
        riksbank,
        snb,
        norgesbank,
        nationalbanken,
        oecd_eo,
    ]
    if te is not None:
        connectors.append(te)
    return builder, connectors


def _live_inputs_builder_factory(
    *,
    builder: MonetaryInputsBuilder,
    history_years: int,
) -> InputsBuilder:
    """Adapt the async live builder to the async ``InputsBuilder`` Protocol.

    ADR-0011 Principle 6 — zero per-country ``asyncio.run``. The
    returned callable is an async function that awaits
    :func:`build_live_monetary_inputs` directly; the outer pipeline
    ``asyncio.run`` at process entry keeps every connector call inside
    the same event loop so ``httpx.AsyncClient`` instances survive
    across countries.
    """

    async def _builder(
        session: Session,  # noqa: ARG001 — Protocol compatibility
        country_code: str,
        observation_date: date,
    ) -> MonetaryIndicesInputs:
        return await build_live_monetary_inputs(
            country_code,
            observation_date,
            builder=builder,
            history_years=history_years,
        )

    return _builder


def main(
    country: str = typer.Option("", "--country", help="ISO 3166-1 alpha-2 (omit with --all-t1)."),
    target_date: str = typer.Option(..., "--date", help="ISO date (e.g. 2024-12-31)."),
    all_t1: bool = typer.Option(
        False,  # noqa: FBT003
        "--all-t1",
        help="Iterate over all 7 T1 countries (US/DE/PT/IT/ES/FR/NL).",
    ),
    backend: str = typer.Option(
        "live",
        "--backend",
        help="Inputs source: 'live' (async connector fetch) or 'default' (empty bundle).",
    ),
    fred_api_key: str = typer.Option(
        "",
        "--fred-api-key",
        envvar="FRED_API_KEY",
        help="FRED API key for live backend.",
    ),
    te_api_key: str = typer.Option(
        "",
        "--te-api-key",
        envvar="TE_API_KEY",
        help=(
            "TradingEconomics API key — unlocks the GB M1 TE-primary "
            "cascade (Sprint I-patch), JP M1 TE-primary cascade (Sprint "
            "L), CA M1 TE-primary cascade (Sprint S), AU M1 TE-primary "
            "cascade (Sprint T), NZ M1 TE-primary cascade (Sprint U-NZ), "
            "CH M1 TE-primary cascade (Sprint V), and SE M1 TE-primary "
            "cascade (Sprint W-SE). Optional; country-native fallbacks "
            "(BoE / BoJ / BoC Valet / RBA F1 CSV / RBNZ B2 CSV / SNB "
            "zimoma / Riksbank Swea) and the FRED OECD mirror remain "
            "available when absent."
        ),
    ),
    cache_dir: str = typer.Option(
        ".cache/daily_monetary",
        "--cache-dir",
        help="Connector cache directory.",
    ),
    history_years: int = typer.Option(
        15,
        "--history-years",
        help="Rolling-window span (years) for M1/M2/M4 histories (canonical 30, Tier-4 15).",
    ),
) -> None:
    """Run the daily monetary-indices pipeline."""
    try:
        obs_date = date.fromisoformat(target_date)
    except ValueError:
        typer.echo(f"Invalid --date={target_date!r}; expected ISO YYYY-MM-DD", err=True)
        sys.exit(EXIT_IO)

    targets: list[str] = list(T1_7_COUNTRIES) if all_t1 else [country]
    if not targets or targets == [""]:
        typer.echo("Must pass --country or --all-t1", err=True)
        sys.exit(EXIT_IO)
    for t in targets:
        _warn_if_deprecated_alias(t)
    if backend not in {"default", "live"}:
        typer.echo(f"Unknown --backend={backend!r}; expected 'default' or 'live'", err=True)
        sys.exit(EXIT_IO)

    if backend == "live" and not fred_api_key:
        typer.echo("FRED_API_KEY required for --backend=live", err=True)
        sys.exit(EXIT_IO)

    outcomes = asyncio.run(
        _run_async_pipeline(
            obs_date=obs_date,
            targets=targets,
            backend=backend,
            fred_api_key=fred_api_key,
            te_api_key=te_api_key,
            cache_dir=cache_dir,
            history_years=history_years,
        )
    )

    log.info(
        "monetary_pipeline.summary",
        date=obs_date.isoformat(),
        n_persisted=len(outcomes.persisted),
        n_no_inputs=len(outcomes.no_inputs),
        n_duplicate=len(outcomes.duplicate),
        n_failed=len(outcomes.failed),
        countries_persisted=outcomes.persisted,
        countries_no_inputs=outcomes.no_inputs,
        countries_duplicate=outcomes.duplicate,
        countries_failed=[c for c, _ in outcomes.failed],
    )

    # ADR-0011 Principle 3: exit 0 whenever the pipeline ran to completion
    # without an uncaught structural exception. Partial coverage
    # (some persisted, others expected-no_inputs) is OK. Exit 1 only
    # when *every* country failed with an uncaught exception — i.e.
    # zero persisted, zero no_inputs, zero duplicate, and ≥1 failed.
    if (
        outcomes.failed
        and not outcomes.persisted
        and not outcomes.no_inputs
        and not outcomes.duplicate
    ):
        sys.exit(EXIT_NO_INPUTS)
    sys.exit(EXIT_OK)


async def _run_async_pipeline(
    *,
    obs_date: date,
    targets: list[str],
    backend: str,
    fred_api_key: str,
    te_api_key: str,
    cache_dir: str,
    history_years: int,
) -> _MonetaryRunOutcomes:
    """Run the full pipeline inside a single event loop.

    ADR-0011 Principle 6 — async lifecycle discipline. Connectors are
    instantiated once, registered with :class:`contextlib.AsyncExitStack`
    so their ``aclose()`` runs inside the same loop that created their
    ``httpx.AsyncClient`` transports, and torn down deterministically
    on exit. No per-country ``asyncio.run`` call exists in this
    module — exactly one site lives in :func:`main`, at process entry.
    """
    async with contextlib.AsyncExitStack() as stack:
        builder: InputsBuilder = default_inputs_builder
        if backend == "live":
            monetary_builder, connectors_to_close = _build_live_connectors(
                fred_api_key=fred_api_key,
                te_api_key=te_api_key,
                cache_dir=cache_dir,
            )
            for conn in connectors_to_close:
                close = getattr(conn, "aclose", None)
                if close is None:
                    continue
                stack.push_async_callback(close)
            builder = _live_inputs_builder_factory(
                builder=monetary_builder, history_years=history_years
            )

        session = SessionLocal()
        stack.callback(session.close)
        # Always spin up the DB-backed reader so M3 fills when
        # daily_curves + daily_overlays have persisted the NSS forwards
        # + EXPINF row for the country/date (CAL-108). Additive over
        # live M1/M2/M4.
        from sonar.indices.monetary.db_backed_builder import (  # noqa: PLC0415
            MonetaryDbBackedInputsBuilder as _MonetaryDbBackedInputsBuilder,
        )

        db_backed = _MonetaryDbBackedInputsBuilder(session)
        return await _dispatch_country_loop(
            session=session,
            targets=targets,
            observation_date=obs_date,
            inputs_builder=builder,
            db_backed_builder=db_backed,
        )


if __name__ == "__main__":  # pragma: no cover
    typer.run(main)
