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

Exit codes:

* ``0`` — clean run, at least one country succeeded (``--all-t1``) or the
  single country succeeded (``--country``).
* ``1`` — ``InsufficientDataError`` (single country, or all T1 skipped).
* ``2`` — ``ConvergenceError`` from optimizer (single country only).
* ``3`` — ``DuplicatePersistError`` (triplet already in DB).
* ``4`` — IO / network / unexpected exception.
"""

from __future__ import annotations

import asyncio
import sys
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
from sonar.db.persistence import DuplicatePersistError, persist_nss_fit_result
from sonar.db.session import SessionLocal
from sonar.overlays.exceptions import ConvergenceError, InsufficientDataError
from sonar.overlays.nss import (
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
EXIT_DUPLICATE = 3
EXIT_IO = 4

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
) -> tuple[list[str], list[tuple[str, str]]]:
    """Run each country through :func:`run_country`, collecting outcomes.

    Returns ``(successes, skipped)`` where ``skipped`` is a list of
    ``(country, reason)`` pairs. ``ConvergenceError`` /
    ``DuplicatePersistError`` bubble up — the caller wraps them.
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
    successes: list[str] = []
    skipped: list[tuple[str, str]] = []
    try:
        for c in countries:
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
                successes.append(c.upper())
            except InsufficientDataError as exc:
                log.warning(
                    "daily_curves.skipped",
                    country=c.upper(),
                    reason="insufficient_data",
                    detail=str(exc),
                )
                skipped.append((c.upper(), str(exc)))
    finally:
        if fred is not None:
            await fred.aclose()
        await bundesbank.aclose()
        await ecb_sdw.aclose()
        if te is not None:
            await te.aclose()
        session.close()
    return successes, skipped


def _run_sync(
    countries: list[str],
    observation_date: date,
    cache_dir: Path,
    *,
    strict_single: bool,
) -> int:
    async def _orchestrate() -> int:
        try:
            successes, skipped = await _orchestrate_countries(
                countries, observation_date, cache_dir
            )
        except InsufficientDataError as exc:
            log.error("daily_curves.insufficient_data", error=str(exc))
            return EXIT_INSUFFICIENT_DATA
        except ConvergenceError as exc:
            log.error("daily_curves.convergence_failed", error=str(exc))
            return EXIT_CONVERGENCE
        except DuplicatePersistError as exc:
            log.error("daily_curves.duplicate", error=str(exc))
            return EXIT_DUPLICATE

        log.info(
            "daily_curves.summary",
            n_success=len(successes),
            n_skipped=len(skipped),
            successes=successes,
            skipped=[c for c, _ in skipped],
        )
        if strict_single and skipped:
            # --country <X> asked for exactly this country; if it skipped we
            # surface EXIT_INSUFFICIENT_DATA so the operator sees failure.
            return EXIT_INSUFFICIENT_DATA
        if not successes:
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
