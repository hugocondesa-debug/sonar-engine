"""Daily cycles pipeline — orchestrate CCCS + FCS + MSC + ECS persistence.

Mirrors :mod:`sonar.pipelines.daily_economic_indices` (CLI + session +
exit-code convention). Very thin wrapper: the heavy lifting already
lives in :func:`sonar.cycles.orchestrator.compute_all_cycles`, which
reads sub-index rows for each cycle, applies Policy 1 re-weight +
hysteresis + overlays, and (with ``persist=True``) writes the four
L4 rows in the same session. This pipeline layers:

- CLI with ``--country`` / ``--all-t1`` / ``--date``.
- Optional ``StagflationInputs`` resolver for the ECS overlay (auto-
  wired when ``--backend=live`` is requested and FRED creds are
  present; otherwise ECS runs with the overlay forced inactive).
- Per-country loop with structured-log events + exit-code mapping.

CLI::

    python -m sonar.pipelines.daily_cycles --country US --date 2024-12-31
    python -m sonar.pipelines.daily_cycles --country EA --date 2024-12-31
    python -m sonar.pipelines.daily_cycles --all-t1 --date 2024-12-31
    python -m sonar.pipelines.daily_cycles --country US --date 2024-12-31 \
        --backend live --fred-api-key ${FRED_API_KEY}

Cohort constants:

- :data:`T1_7_COUNTRIES` — legacy 7-sovereign T1 cohort used by the
  ``--all-t1`` iteration. Covers the full CCCS / FCS / ECS cycle stack
  (MSC rides the same loop but additionally supports EA via a separate
  MSC-only cohort — see below).
- :data:`MSC_CROSS_COUNTRY_COHORT` — Sprint P (Week 11 Day 1) — explicit
  cross-country cohort for the L4 Monetary Stance Composite. Documents
  that MSC is the **first** L4 cycle shipped cross-country (US + EA).
  Not wired into a CLI flag; callers invoke EA via ``--country EA`` (or
  systemd dispatch) until Week 12+ ``CAL-COHORT-CONSTANT-CLEANUP``
  unifies all cycle cohorts under Sprint Q.0.5's T1_COUNTRIES tuple.

Exit codes mirror :mod:`daily_economic_indices`:

* ``0`` — all requested cycles computed (or skipped with log).
* ``1`` — no cycles persisted for any country in the run.
* ``3`` — duplicate persist collision surfaced from the orchestrator.
* ``4`` — CLI / IO error.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Protocol

import structlog
import typer

from sonar.cycles.orchestrator import CyclesOrchestrationResult, compute_all_cycles
from sonar.db.persistence import DuplicatePersistError, persist_l5_meta_regime_result
from sonar.db.session import SessionLocal
from sonar.regimes.assemblers import build_l5_inputs_from_cycles_result
from sonar.regimes.exceptions import InsufficientL4DataError
from sonar.regimes.meta_regime_classifier import MetaRegimeClassifier

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from sonar.connectors.fred import FredConnector
    from sonar.cycles.economic_ecs import StagflationInputs
    from sonar.regimes.types import L5RegimeResult

log = structlog.get_logger()

__all__ = [
    "MSC_CROSS_COUNTRY_COHORT",
    "T1_7_COUNTRIES",
    "CyclesPipelineOutcome",
    "StagflationInputsResolver",
    "count_persisted",
    "default_stagflation_resolver",
    "main",
    "run_one",
]

T1_7_COUNTRIES: tuple[str, ...] = ("US", "DE", "PT", "IT", "ES", "FR", "NL")

# Sprint P (Week 11 Day 1) — L4 MSC first cross-country cohort. EA added
# atop US once M1 (ECB DFR), M2 (Taylor gap EA, Sprint L), M3 (market
# expectations via ECB_SPF, Sprint Q.1.x), and M4 (FCI EA-custom, Sprint
# J) all landed. Exposed as a separate constant (not fused into
# :data:`T1_7_COUNTRIES`) because the all-cycles CCCS / FCS / ECS
# cohorts stay 7-sovereign until Week 12+ CAL-COHORT-CONSTANT-CLEANUP
# unifies under Sprint Q.0.5's 12-country T1_COUNTRIES. Callers dispatch
# EA MSC via explicit ``--country EA`` or systemd; no new CLI flag.
MSC_CROSS_COUNTRY_COHORT: tuple[str, ...] = ("US", "EA")

EXIT_OK = 0
EXIT_NO_INPUTS = 1
EXIT_DUPLICATE = 3
EXIT_IO = 4


class StagflationInputsResolver(Protocol):
    """Callable signature: ``(session, country, date) -> StagflationInputs | None``.

    Pipelines wire a resolver (typically :func:`sonar.cycles.
    stagflation_inputs.resolve_stagflation_inputs` with connectors
    bound) so ECS can evaluate the overlay. The default resolver
    returns ``None`` → overlay forced inactive + flag per spec §6.
    """

    def __call__(
        self,
        session: Session,
        country_code: str,
        observation_date: date,
    ) -> StagflationInputs | None: ...


def default_stagflation_resolver(
    session: Session,  # noqa: ARG001 — Protocol compatibility
    country_code: str,  # noqa: ARG001
    observation_date: date,  # noqa: ARG001
) -> StagflationInputs | None:
    """MVP default — return ``None`` so ECS emits STAGFLATION_INPUT_MISSING."""
    return None


@dataclass(frozen=True, slots=True)
class CyclesPipelineOutcome:
    country_code: str
    observation_date: date
    orchestration: CyclesOrchestrationResult
    persisted: dict[str, int]
    l5_result: L5RegimeResult | None = None
    l5_skip_reason: str | None = None


def count_persisted(result: CyclesOrchestrationResult) -> dict[str, int]:
    """Return a ``{cycle_slug: 0 | 1}`` map reflecting which rows persisted."""
    return {
        "cccs": 1 if result.cccs is not None else 0,
        "fcs": 1 if result.fcs is not None else 0,
        "msc": 1 if result.msc is not None else 0,
        "ecs": 1 if result.ecs is not None else 0,
    }


def _classify_and_persist_l5(
    session: Session,
    country_code: str,
    observation_date: date,
    orchestration: CyclesOrchestrationResult,
) -> tuple[L5RegimeResult | None, str | None]:
    """Run L5 classifier + persist; returns ``(result, skip_reason)`` tuple.

    Either slot is populated; never both. Graceful on
    :class:`InsufficientL4DataError` (< 3/4 cycles) and
    :class:`DuplicatePersistError` (re-run idempotent). Any other
    exception is not swallowed — those are true bugs.
    """
    l5_inputs = build_l5_inputs_from_cycles_result(country_code, observation_date, orchestration)
    try:
        l5_result = MetaRegimeClassifier().classify(l5_inputs)
    except InsufficientL4DataError as exc:
        log.info(
            "cycles_pipeline.l5_insufficient_l4",
            country=country_code,
            date=observation_date.isoformat(),
            available=l5_inputs.available_count(),
            reason=str(exc),
        )
        return None, str(exc)

    try:
        persist_l5_meta_regime_result(session, l5_result)
    except DuplicatePersistError as exc:
        log.info(
            "cycles_pipeline.l5_duplicate_skip",
            country=country_code,
            date=observation_date.isoformat(),
            reason=str(exc),
        )
        return l5_result, f"duplicate: {exc}"

    log.info(
        "cycles_pipeline.l5_persisted",
        country=country_code,
        date=observation_date.isoformat(),
        meta_regime=str(l5_result.meta_regime),
        confidence=l5_result.confidence,
        classification_reason=l5_result.classification_reason,
    )
    return l5_result, None


def run_one(
    session: Session,
    country_code: str,
    observation_date: date,
    *,
    stagflation_resolver: StagflationInputsResolver | None = None,
) -> CyclesPipelineOutcome:
    """Single ``(country, date)`` pipeline run: orchestrate → persist → log.

    Delegates to :func:`compute_all_cycles` with ``persist=True`` so
    each produced row is written in the same session. A cycle that
    raises :class:`InsufficientCycleInputsError` is recorded in
    ``orchestration.skips`` and does not sink the run.

    ``stagflation_resolver`` lets callers inject live CPI / Sahm /
    unemp-delta readings. When ``None`` the default returns
    ``StagflationInputs`` all-None → ECS emits
    ``STAGFLATION_INPUT_MISSING`` and the overlay stays inactive.
    """
    resolver = stagflation_resolver or default_stagflation_resolver
    sf_inputs = resolver(session, country_code, observation_date)
    orchestration = compute_all_cycles(
        session,
        country_code,
        observation_date,
        persist=True,
        ecs_stagflation_inputs=sf_inputs,
    )
    persisted = count_persisted(orchestration)
    log.info(
        "cycles_pipeline.persisted",
        country=country_code,
        date=observation_date.isoformat(),
        persisted=persisted,
        skips=orchestration.skips,
    )
    l5_result, l5_skip_reason = _classify_and_persist_l5(
        session, country_code, observation_date, orchestration
    )
    return CyclesPipelineOutcome(
        country_code=country_code,
        observation_date=observation_date,
        orchestration=orchestration,
        persisted=persisted,
        l5_result=l5_result,
        l5_skip_reason=l5_skip_reason,
    )


def _live_stagflation_resolver_factory(
    *,
    fred: FredConnector,
) -> StagflationInputsResolver:
    """Wrap the async live resolver into the synchronous Protocol."""
    # Local import so the default-backend CLI keeps a zero-dependency
    # cold import surface.
    from sonar.cycles.stagflation_inputs import (  # noqa: PLC0415
        resolve_stagflation_inputs,
    )

    def _resolver(
        session: Session,
        country_code: str,
        observation_date: date,
    ) -> StagflationInputs | None:
        return asyncio.run(
            resolve_stagflation_inputs(
                country_code,
                observation_date,
                fred=fred,
                session=session,
            )
        )

    return _resolver


def main(  # noqa: PLR0912 — CLI dispatch branches are inherent, not refactor-bait
    country: str = typer.Option("", "--country", help="ISO 3166-1 alpha-2 (omit with --all-t1)."),
    target_date: str = typer.Option(..., "--date", help="ISO date (e.g. 2024-12-31)."),
    all_t1: bool = typer.Option(
        False,  # noqa: FBT003
        "--all-t1",
        help="Iterate over all 7 T1 countries (US/DE/PT/IT/ES/FR/NL).",
    ),
    backend: str = typer.Option(
        "default",
        "--backend",
        help=(
            "Stagflation-inputs source: 'default' (overlay inactive) or "
            "'live' (FRED CPIAUCSL / UNRATE + E3 Sahm passthrough)."
        ),
    ),
    fred_api_key: str = typer.Option(
        "",
        "--fred-api-key",
        envvar="FRED_API_KEY",
        help="FRED API key for --backend=live stagflation resolver.",
    ),
    cache_dir: str = typer.Option(
        ".cache/daily_cycles",
        "--cache-dir",
        help="Connector cache directory (live backend only).",
    ),
) -> None:
    """Run the daily cycles pipeline (CCCS + FCS + MSC + ECS)."""
    try:
        obs_date = date.fromisoformat(target_date)
    except ValueError:
        typer.echo(f"Invalid --date={target_date!r}; expected ISO YYYY-MM-DD", err=True)
        sys.exit(EXIT_IO)

    targets: list[str] = list(T1_7_COUNTRIES) if all_t1 else [country]
    if not targets or targets == [""]:
        typer.echo("Must pass --country or --all-t1", err=True)
        sys.exit(EXIT_IO)
    if backend not in {"default", "live"}:
        typer.echo(f"Unknown --backend={backend!r}; expected 'default' or 'live'", err=True)
        sys.exit(EXIT_IO)

    resolver: StagflationInputsResolver | None = None
    connectors_to_close: list[object] = []
    if backend == "live":
        if not fred_api_key:
            typer.echo("FRED_API_KEY required for --backend=live", err=True)
            sys.exit(EXIT_IO)
        from sonar.connectors.fred import FredConnector  # noqa: PLC0415

        fred = FredConnector(api_key=fred_api_key, cache_dir=f"{cache_dir}/fred")
        connectors_to_close.append(fred)
        resolver = _live_stagflation_resolver_factory(fred=fred)

    session = SessionLocal()
    exit_code = EXIT_OK
    try:
        any_persisted = False
        for c in targets:
            try:
                outcome = run_one(session, c, obs_date, stagflation_resolver=resolver)
            except DuplicatePersistError as exc:
                log.error("cycles_pipeline.duplicate", country=c, error=str(exc))
                exit_code = EXIT_DUPLICATE
                continue
            persisted_total = sum(outcome.persisted.values())
            if persisted_total == 0:
                log.warning(
                    "cycles_pipeline.no_inputs",
                    country=c,
                    date=obs_date.isoformat(),
                    skips=outcome.orchestration.skips,
                )
            else:
                any_persisted = True
        if exit_code == EXIT_OK and not any_persisted:
            exit_code = EXIT_NO_INPUTS
    finally:
        session.close()
        for conn in connectors_to_close:
            close = getattr(conn, "aclose", None)
            if close is not None:
                asyncio.run(close())
    sys.exit(exit_code)


if __name__ == "__main__":  # pragma: no cover
    typer.run(main)
