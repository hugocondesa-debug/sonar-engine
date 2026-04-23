"""L8 ``daily-curves`` pipeline — multi-country NSS fit (CAL-138 scope).

Orchestrates a single ``(country, date)`` tuple end-to-end:
L0 connector fetch → L2 NSS fit + derive (zero / forward / real) → L1 persist.

Week 2 shipped US-only (``run_us``). Week 10 Sprint CAL-138 expanded
coverage via country-aware connector dispatch; Week 10 Sprint E
(CAL-CURVES-T1-SPARSE-INCLUSION, 2026-04-22) wires GB/JP/CA into the
pipeline's ``--all-t1`` iteration via the new
:data:`T1_CURVES_COUNTRIES` tuple — replacing the shared
``T1_7_COUNTRIES`` convention for curves only, because the curve-fit
surface differs from the per-country connector readiness of the other
daily pipelines.

- **US**  → :class:`~sonar.connectors.fred.FredConnector`
  (nominal DGS* + linker TIPS DFII*)
- **DE**  → :class:`~sonar.connectors.bundesbank.BundesbankConnector`
  (BBSIS daily zero-coupon 9 tenors 1Y-30Y; linker stub)
- **EA**  → :class:`~sonar.connectors.ecb_sdw.EcbSdwConnector`
  (YC dataflow EA-AAA Svensson 11 tenors 3M-30Y; linker stub)
- **GB / JP / CA / IT / ES / FR** → :class:`~sonar.connectors.te.TEConnector`
  (``/markets/historical`` Bloomberg symbols — GB 12 / JP 9 / CA 6
  tenors per CAL-138 empirical probe; IT 12 / ES 9 tenors per Sprint H
  pre-flight 2026-04-22; FR 10 tenors per Sprint I pre-flight
  2026-04-22; linker stub)

Other T1 countries (AU/NZ/CH/SE/NO/DK + EA periphery remainder
PT/NL) have insufficient tenor coverage on currently-wired
connectors. The Week 10 Sprint A pre-flight probe (2026-04-22)
confirmed that ECB SDW cannot serve per-country EA periphery curves
— the ``YC`` dataflow is EA-aggregate only, ``FM`` lacks EA
periphery ``REF_AREA``, and ``IRS`` publishes a single 10Y point per
country (below ``MIN_OBSERVATIONS=6``). The remaining periphery
(PT / NL) is tracked under per-country CAL items
(``CAL-CURVES-PT-BPSTAT`` / ``CAL-CURVES-NL-DNB``) superseding the
umbrella ``CAL-CURVES-EA-PERIPHERY``; AU/NZ/CH/SE/NO/DK remain under
``CAL-CURVES-T1-SPARSE``. Pipeline raises
:class:`~sonar.overlays.exceptions.InsufficientDataError` for those —
in ``--all-t1`` mode the country is skipped and the orchestrator
continues; in ``--country <X>`` mode the exit code is
``EXIT_INSUFFICIENT_DATA`` (1).

Week 10 Sprint D pilot (2026-04-22) executed the FR national-CB
integration attempt and confirmed all four brief §9 fallback paths
(BdF / AFT / TE / FRED) fail to provide a ≥ 6-tenor daily FR
sovereign curve (BdF legacy SDMX decommissioned; BdF OpenDatasoft
successor publishes only a monthly archive; AFT Cloudflare-challenged;
TE single-tenor; FRED 10Y-monthly). ``CAL-CURVES-FR-BDF`` is marked
BLOCKED; the scaffolded :mod:`sonar.connectors.banque_de_france`
connector captures the empirical state. See ADR-0009 for the
national-CB connector pattern lessons applicable to the four
successor sprints (IT/ES/PT/NL).

Week 10 Sprint G (2026-04-22, combined IT + ES pilot) executed
sprints 2 + 3 of the ADR-0009 successor set. Both landed in HALT-0:
IT is strict "all 5 paths dead" (ECB legacy SDMX decommissioned;
BdI Infostat API subdomains NXDOMAIN; MEF HTML-only; ECB SDW FM + IRS
EA-aggregate; FRED 10Y-monthly). ES is "HTTP 200 + non-daily" — the
Banco de España BIE REST API (``https://app.bde.es/bierest/``) is
live and publishes 11-tenor Spanish sovereign yields but at
monthly frequency, below the daily pipeline cadence. Sprint G's
brief §2 probe list had **omitted** TE (Trading Economics generic
indicator API) — Sprint H (2026-04-22) re-probed with TE as Path 1
per ADR-0009 v2 amendment and empirically confirmed 12-tenor IT
coverage (``GBTPGR`` BTP family) + 9-tenor ES coverage (``GSPG``
SPGB family) via the ``/markets/historical`` endpoint. IT + ES
therefore **ship via TE cascade** (this commit) and close both
``CAL-CURVES-IT-BDI`` + ``CAL-CURVES-ES-BDE``. The scaffolded
:mod:`sonar.connectors.banca_ditalia` +
:mod:`sonar.connectors.banco_espana` connectors are retained as
future direct-CB placeholders (Phase 2.5+ unblock paths documented
in the Sprint G retro). PT-BPSTAT + NL-DNB remain pending (ADR-0009
successor sprints 4 + 5).

Week 10 Sprint I (2026-04-22) closed ``CAL-CURVES-FR-TE-PROBE`` via
the same ADR-0009 v2 cascade discipline: a per-tenor sweep across the
``GFRN`` OAT family on ``/markets/historical`` returned 10 daily
tenors (1M-30Y minus 3Y/15Y), well above
``MIN_OBSERVATIONS_FOR_SVENSSON=9``. FR therefore ships via TE
cascade alongside IT + ES; the Sprint D HALT-0 conclusion
(``GFRN10`` 10Y-only, below ``MIN_OBSERVATIONS``) was a
single-symbol-probe artifact superseded by the per-tenor sweep. The
scaffolded :mod:`sonar.connectors.banque_de_france` connector is
retained as a future direct-CB placeholder;
``CAL-CURVES-FR-BDF`` remains BLOCKED for the national-CB direct path
while the TE cascade serves the daily pipeline.

CLI entrypoints:

    python -m sonar.pipelines.daily_curves --country US --date 2024-01-02
    python -m sonar.pipelines.daily_curves --all-t1 --date 2024-01-02

Exit codes (ADR-0011 aligned, Sprint T0 2026-04-23):

* ``0`` — happy path: at least one country persisted OR all requested
  countries were skipped-existing (idempotent no-op re-run). Also 0
  when a mix of persisted + skipped-existing + expected-insufficient
  countries completes without any uncaught exception.
* ``1`` — ``InsufficientDataError`` in strict-single mode
  (``--country X``); or ``--all-t1`` where **every** country failed
  or was skipped without a single persist or skip-existing.
* ``2`` — ``ConvergenceError`` from optimizer. Reserved constant, not
  emitted under ADR-0011 (caught by per-country isolation in
  ``--all-t1``; surfaces as exit 4 in strict-single mode).
* ``4`` — IO / network / unexpected exception at the orchestrator
  boundary (per-country exceptions are caught + logged + continued).

Week 10 Sprint T0 (2026-04-23) removed exit code 3 (DuplicatePersistError)
from the happy-path contract per ADR-0011 Principle 1: duplicates are
skip + continue at the orchestrator via a pre-INSERT existence check
on ``(country_code, date, methodology_version)``. A race-condition
``DuplicatePersistError`` at the persist layer (extremely rare under
single-process systemd scheduling) is still caught + logged as info
+ continued; the exit code 3 literal is retained as defence-in-depth
but unreachable under normal operation.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import structlog
import typer

from sonar.config import settings
from sonar.connectors.bundesbank import BundesbankConnector
from sonar.connectors.ecb_sdw import EcbSdwConnector
from sonar.connectors.fred import FredConnector
from sonar.connectors.te import TE_YIELD_CURVE_SYMBOLS, TEConnector
from sonar.db.models import NSSYieldCurveSpot
from sonar.db.persistence import DuplicatePersistError, persist_nss_fit_result
from sonar.db.session import SessionLocal
from sonar.overlays.exceptions import InsufficientDataError
from sonar.overlays.nss import (
    METHODOLOGY_VERSION as NSS_METHODOLOGY_VERSION,
    MIN_OBSERVATIONS,
    NSSInput,
    _label_to_years,
    assemble_nss_fit_result,
    derive_forward_curve,
    derive_real_curve,
    derive_zero_curve,
    fit_nss,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from sonar.connectors.base import Observation
    from sonar.overlays.nss import NSSFitResult

log = structlog.get_logger()

EXIT_OK = 0
EXIT_INSUFFICIENT_DATA = 1
EXIT_CONVERGENCE = 2
EXIT_DUPLICATE = 3  # retained for defence-in-depth; unreachable under ADR-0011
EXIT_IO = 4


@dataclass(slots=True)
class _CurveRunOutcomes:
    """Bucketed per-country outcomes across a single --all-t1 orchestration.

    ADR-0011 Principle 4 (summary emit): end-of-run log consolidates
    these buckets so a single ``daily_curves.summary`` log line tells
    the operator what happened country-by-country without grep-ing the
    run trace.
    """

    persisted: list[str] = field(default_factory=list)
    skipped_existing: list[str] = field(default_factory=list)
    skipped_insufficient: list[tuple[str, str]] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)


def _curve_already_persisted(
    session: Session,
    country_code: str,
    observation_date: date,
    methodology_version: str = NSS_METHODOLOGY_VERSION,
) -> bool:
    """Return ``True`` if a ``yield_curves_spot`` row already exists.

    ADR-0011 Principle 1 (idempotency per row) pre-INSERT check. Avoids
    re-fetch + re-fit network cost when Run N already persisted the
    ``(country_code, date, methodology_version)`` triplet. The UNIQUE
    constraint ``uq_ycs_country_date_method`` remains as defence in
    depth at the persist layer.
    """
    existing = (
        session.query(NSSYieldCurveSpot.id)
        .filter(
            NSSYieldCurveSpot.country_code == country_code,
            NSSYieldCurveSpot.date == observation_date,
            NSSYieldCurveSpot.methodology_version == methodology_version,
        )
        .first()
    )
    return existing is not None


# Curve-pipeline-specific T1 scope — diverges from the canonical
# ``T1_7_COUNTRIES`` convention (US + 6 EA members) shared by
# daily_overlays / daily_monetary_indices / daily_economic_indices /
# daily_credit_indices / daily_financial_indices / daily_cycles /
# daily_cost_of_capital / cli.status because the curve pipeline has
# different connector readiness per country (Week 10 Sprint E sparse
# inclusion, 2026-04-22; Week 10 Sprint H IT + ES TE cascade,
# 2026-04-22; Week 10 Sprint I FR TE cascade, 2026-04-22). Membership
# reflects ``CURVE_SUPPORTED_COUNTRIES``:
#
# - **US** via FRED (full DGS/DFII — nominal + linker)
# - **DE** via Bundesbank (BBSIS zero-coupon 1Y-30Y)
# - **EA** via ECB SDW (YC EA-AAA Svensson 3M-30Y aggregate)
# - **GB / JP / CA / IT / ES / FR** via TE ``/markets/historical``
#   Bloomberg symbols (CAL-138: GB 12 / JP 9 / CA 6 tenors; Sprint H:
#   IT 12 / ES 9 tenors; Sprint I: FR 10 tenors)
#
# EA periphery remainder (PT / NL) and AU/NZ/CH/SE/NO/DK are deferred
# per per-country CAL items (``CAL-CURVES-PT-BPSTAT`` …) and
# ``CAL-CURVES-T1-SPARSE`` respectively; passing them via ``--country <X>``
# still raises ``InsufficientDataError`` with a CAL pointer — the sparse
# inclusion change only concerns what ``--all-t1`` iterates.
T1_CURVES_COUNTRIES: tuple[str, ...] = ("US", "DE", "EA", "GB", "JP", "CA", "IT", "ES", "FR")

# Countries wired to a curve-fit path at Sprint I close. A country
# outside this set passed to ``--country`` raises InsufficientDataError
# with a pointer to the tracking CAL item.
CURVE_SUPPORTED_COUNTRIES: frozenset[str] = frozenset(
    {"US", "DE", "EA", "GB", "JP", "CA", "IT", "ES", "FR"}
)

# Periphery + sparse-T1 pointers surfaced in error messages so operators
# see the exact CAL item to subscribe to. EA periphery remainder (PT /
# NL) points to their per-country CAL items; Sprint H 2026-04-22 moved
# IT + ES out of the deferral map after TE cascade ship closed
# ``CAL-CURVES-IT-BDI`` + ``CAL-CURVES-ES-BDE``; Sprint I 2026-04-22
# moved FR out via the same TE cascade (closed
# ``CAL-CURVES-FR-TE-PROBE``; ``CAL-CURVES-FR-BDF`` remains BLOCKED
# upstream as the national-CB direct-connector path).
_DEFERRAL_CAL_MAP: dict[str, str] = {
    "PT": "CAL-CURVES-PT-BPSTAT",
    "NL": "CAL-CURVES-NL-DNB",
    "AU": "CAL-CURVES-T1-SPARSE",
    "NZ": "CAL-CURVES-T1-SPARSE",
    "CH": "CAL-CURVES-T1-SPARSE",
    "SE": "CAL-CURVES-T1-SPARSE",
    "NO": "CAL-CURVES-T1-SPARSE",
    "DK": "CAL-CURVES-T1-SPARSE",
}


async def _fetch_nominals_linkers(
    country: str,
    observation_date: date,
    *,
    fred: FredConnector | None,
    bundesbank: BundesbankConnector | None,
    ecb_sdw: EcbSdwConnector | None,
    te: TEConnector | None,
) -> tuple[dict[str, Observation], dict[str, Observation], str]:
    """Connector dispatch — returns ``(nominals, linkers, source_connector)``.

    Raises :class:`InsufficientDataError` for unsupported countries with
    a pointer to the tracking CAL item so the operator sees the next
    unblock path.
    """
    country_upper = country.upper()
    if country_upper == "US":
        if fred is None:
            msg = "US yield curve requires FredConnector"
            raise InsufficientDataError(msg)
        nominals = await fred.fetch_yield_curve_nominal(
            country="US", observation_date=observation_date
        )
        linkers = await fred.fetch_yield_curve_linker(
            country="US", observation_date=observation_date
        )
        return nominals, linkers, "fred"
    if country_upper == "DE":
        if bundesbank is None:
            msg = "DE yield curve requires BundesbankConnector"
            raise InsufficientDataError(msg)
        nominals = await bundesbank.fetch_yield_curve_nominal(
            country="DE", observation_date=observation_date
        )
        linkers = await bundesbank.fetch_yield_curve_linker(
            country="DE", observation_date=observation_date
        )
        return nominals, linkers, "bundesbank"
    if country_upper == "EA":
        if ecb_sdw is None:
            msg = "EA yield curve requires EcbSdwConnector"
            raise InsufficientDataError(msg)
        nominals = await ecb_sdw.fetch_yield_curve_nominal(
            country="EA", observation_date=observation_date
        )
        linkers = await ecb_sdw.fetch_yield_curve_linker(
            country="EA", observation_date=observation_date
        )
        return nominals, linkers, "ecb_sdw"
    if country_upper in TE_YIELD_CURVE_SYMBOLS:
        if te is None:
            msg = f"{country_upper} yield curve requires TEConnector"
            raise InsufficientDataError(msg)
        nominals = await te.fetch_yield_curve_nominal(
            country=country_upper, observation_date=observation_date
        )
        linkers = await te.fetch_yield_curve_linker(
            country=country_upper, observation_date=observation_date
        )
        return nominals, linkers, "te"

    deferral = _DEFERRAL_CAL_MAP.get(country_upper)
    deferral_note = f" Deferred per {deferral}." if deferral else ""
    msg = (
        f"daily_curves: no connector for country={country_upper!r}. "
        f"Supported (CAL-138 scope): "
        f"{sorted(CURVE_SUPPORTED_COUNTRIES)}.{deferral_note}"
    )
    raise InsufficientDataError(msg)


async def run_country(
    country: str,
    observation_date: date,
    session: Session,
    *,
    fred: FredConnector | None = None,
    bundesbank: BundesbankConnector | None = None,
    ecb_sdw: EcbSdwConnector | None = None,
    te: TEConnector | None = None,
) -> NSSFitResult:
    """Single-(country, date) end-to-end: fetch → fit → derive → persist.

    Dispatches to the connector family per :data:`CURVE_SUPPORTED_COUNTRIES`.
    Callers pass whichever connectors they have initialised; the dispatch
    raises :class:`InsufficientDataError` when the required connector is
    missing.
    """
    country_upper = country.upper()
    nominals, linkers, source_connector = await _fetch_nominals_linkers(
        country_upper,
        observation_date,
        fred=fred,
        bundesbank=bundesbank,
        ecb_sdw=ecb_sdw,
        te=te,
    )

    labels = sorted(nominals.keys(), key=_label_to_years)
    if len(labels) < MIN_OBSERVATIONS:
        deferral = _DEFERRAL_CAL_MAP.get(country_upper)
        deferral_note = f" Deferred per {deferral}." if deferral else ""
        msg = (
            f"daily_curves {country_upper}: only {len(labels)} tenors available "
            f"(need ≥{MIN_OBSERVATIONS}).{deferral_note}"
        )
        raise InsufficientDataError(msg)

    nss_input = NSSInput(
        tenors_years=np.array([_label_to_years(t) for t in labels]),
        yields=np.array([nominals[t].yield_bps / 10_000.0 for t in labels]),
        country_code=country_upper,
        observation_date=observation_date,
        curve_input_type="par",
    )
    spot = fit_nss(nss_input)
    zero = derive_zero_curve(spot)
    forward = derive_forward_curve(zero)

    linker_yields = {t: linkers[t].yield_bps / 10_000.0 for t in linkers}
    real = derive_real_curve(
        spot,
        linker_yields=linker_yields if linker_yields else None,
        observation_date=observation_date,
        country_code=country_upper,
    )

    result = assemble_nss_fit_result(
        country_code=country_upper,
        observation_date=observation_date,
        spot=spot,
        zero=zero,
        forward=forward,
        real=real,
    )
    persist_nss_fit_result(session, result, source_connector=source_connector)
    log.info(
        "daily_curves.persisted",
        country=country_upper,
        date=observation_date.isoformat(),
        fit_id=str(result.fit_id),
        rmse_bps=spot.rmse_bps,
        confidence=spot.confidence,
        observations_used=spot.observations_used,
        source_connector=source_connector,
    )
    return result


async def run_us(
    observation_date: date,
    session: Session,
    fred: FredConnector,
) -> NSSFitResult:
    """Back-compat wrapper preserved for existing callers (tests + docs).

    Delegates to :func:`run_country` with ``country="US"``.
    """
    return await run_country(
        country="US",
        observation_date=observation_date,
        session=session,
        fred=fred,
    )


async def _orchestrate_countries(
    countries: list[str],
    observation_date: date,
    cache_dir: Path,
) -> _CurveRunOutcomes:
    """Run each country through :func:`run_country`, collecting outcomes.

    Per ADR-0011 Principles 1-2: pre-INSERT existence check for
    idempotent skip, per-country try/except so one country's failure
    does not sink the pipeline. Returns a :class:`_CurveRunOutcomes`
    with four disjoint buckets (persisted, skipped_existing,
    skipped_insufficient, failed).
    """
    placeholder = "your_fred_api_key_here"  # pragma: allowlist secret
    have_fred = bool(settings.fred_api_key) and settings.fred_api_key != placeholder
    have_te = bool(settings.te_api_key)

    fred = (
        FredConnector(api_key=settings.fred_api_key, cache_dir=str(cache_dir / "fred"))
        if have_fred
        else None
    )
    bundesbank = BundesbankConnector(cache_dir=str(cache_dir / "bundesbank"))
    ecb_sdw = EcbSdwConnector(cache_dir=str(cache_dir / "ecb_sdw"))
    te = (
        TEConnector(api_key=settings.te_api_key, cache_dir=str(cache_dir / "te"))
        if have_te
        else None
    )

    session = SessionLocal()
    outcomes = _CurveRunOutcomes()
    try:
        for c in countries:
            country_upper = c.upper()
            if _curve_already_persisted(session, country_upper, observation_date):
                log.info(
                    "daily_curves.skip_existing",
                    country=country_upper,
                    date=observation_date.isoformat(),
                    methodology_version=NSS_METHODOLOGY_VERSION,
                    reason="idempotent_pre_check",
                )
                outcomes.skipped_existing.append(country_upper)
                continue
            try:
                await run_country(
                    c,
                    observation_date,
                    session,
                    fred=fred,
                    bundesbank=bundesbank,
                    ecb_sdw=ecb_sdw,
                    te=te,
                )
                outcomes.persisted.append(country_upper)
            except InsufficientDataError as exc:
                log.warning(
                    "daily_curves.skipped",
                    country=country_upper,
                    reason="insufficient_data",
                    detail=str(exc),
                )
                outcomes.skipped_insufficient.append((country_upper, str(exc)))
            except DuplicatePersistError as exc:
                # Defence-in-depth: the pre-check above should have caught
                # this. A race-condition hit here (extremely rare under
                # single-process systemd scheduling) is logged as info and
                # counted as skipped_existing, not as an error.
                log.info(
                    "daily_curves.duplicate_race",
                    country=country_upper,
                    date=observation_date.isoformat(),
                    detail=str(exc),
                )
                outcomes.skipped_existing.append(country_upper)
            except Exception as exc:  # ADR-0011 Principle 2
                # Per-country isolation: log + continue. One country's
                # RetryError / HTTPError / unexpected exception must not
                # sink the pipeline (Apr 23 natural-fire root cause).
                log.error(
                    "daily_curves.country_failed",
                    country=country_upper,
                    date=observation_date.isoformat(),
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                outcomes.failed.append((country_upper, f"{type(exc).__name__}: {exc}"))
    finally:
        if fred is not None:
            await fred.aclose()
        await bundesbank.aclose()
        await ecb_sdw.aclose()
        if te is not None:
            await te.aclose()
        session.close()
    return outcomes


def _run_sync(
    countries: list[str],
    observation_date: date,
    cache_dir: Path,
    *,
    strict_single: bool,
) -> int:
    async def _orchestrate() -> int:
        outcomes = await _orchestrate_countries(countries, observation_date, cache_dir)

        log.info(
            "daily_curves.summary",
            date=observation_date.isoformat(),
            n_persisted=len(outcomes.persisted),
            n_skipped_existing=len(outcomes.skipped_existing),
            n_skipped_insufficient=len(outcomes.skipped_insufficient),
            n_failed=len(outcomes.failed),
            countries_persisted=outcomes.persisted,
            countries_skipped_existing=outcomes.skipped_existing,
            countries_skipped_insufficient=[c for c, _ in outcomes.skipped_insufficient],
            countries_failed=[c for c, _ in outcomes.failed],
        )

        ok_count = len(outcomes.persisted) + len(outcomes.skipped_existing)
        if strict_single:
            # --country <X>: this is a single-country request. Report
            # failure (exit 1) if the country failed or was insufficient
            # data; report OK if it persisted or was already persisted.
            if outcomes.failed:
                return EXIT_IO
            if outcomes.skipped_insufficient:
                return EXIT_INSUFFICIENT_DATA
            if ok_count == 0:
                return EXIT_INSUFFICIENT_DATA
            return EXIT_OK
        # --all-t1: exit 0 whenever at least one unit is persisted or
        # already persisted (idempotent no-op re-run). Only exit 1 when
        # every country is either insufficient or failed with no single
        # success. Per ADR-0011 Principle 3.
        if ok_count == 0:
            return EXIT_INSUFFICIENT_DATA
        return EXIT_OK

    return asyncio.run(_orchestrate())


def main(
    country: str = typer.Option("", "--country", help="ISO 3166-1 alpha-2 (omit with --all-t1)."),
    all_t1: bool = typer.Option(
        False,  # noqa: FBT003 — Typer convention
        "--all-t1",
        help=(
            "Iterate the Sprint I curve-capable T1 set "
            "(US/DE/EA/GB/JP/CA/IT/ES/FR — 9 countries). Members without "
            "curve support skip with a warning; exit 0 if at least "
            "one succeeds."
        ),
    ),
    target_date: str = typer.Option(..., "--date", help="ISO date (e.g. 2024-01-02)."),
    cache_dir: Path = typer.Option(  # noqa: B008
        Path(".cache/curves"),
        "--cache-dir",
        help="Connector disk cache directory (per-connector subdir).",
    ),
) -> None:
    """Run the daily-curves pipeline for ``--country`` or ``--all-t1`` on ``--date``."""
    if not country and not all_t1:
        typer.echo("Must pass --country or --all-t1", err=True)
        sys.exit(EXIT_IO)
    if country and all_t1:
        typer.echo("Pass only one of --country or --all-t1", err=True)
        sys.exit(EXIT_IO)

    try:
        obs_date = date.fromisoformat(target_date)
    except ValueError:
        typer.echo(f"Invalid --date={target_date!r}; expected ISO YYYY-MM-DD", err=True)
        sys.exit(EXIT_IO)

    cache_dir.mkdir(parents=True, exist_ok=True)
    countries = list(T1_CURVES_COUNTRIES) if all_t1 else [country.upper()]
    code = _run_sync(
        countries,
        obs_date,
        cache_dir,
        strict_single=not all_t1,
    )
    sys.exit(code)


if __name__ == "__main__":
    typer.run(main)
