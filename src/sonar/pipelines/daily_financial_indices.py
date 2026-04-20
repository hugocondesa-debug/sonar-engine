"""Daily financial indices pipeline — orchestrate F1-F4 persistence.

Mirrors ``daily_credit_indices.py`` pattern per f-cycle-brief §Commit 12.
Pluggable :class:`InputsBuilder` so ingestion wiring can land as a
separate future CAL (live connector fetches are shipped per batch but
the inputs-from-DB builder is deferred — CAL-064).

CLI::

    python -m sonar.pipelines.daily_financial_indices --country US --date 2024-01-02
    python -m sonar.pipelines.daily_financial_indices --all-t1 --date 2024-01-02

Exit codes: 0 clean, 1 no-inputs, 3 duplicate, 4 IO.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Protocol

import structlog
import typer

from sonar.db.persistence import DuplicatePersistError, persist_many_financial_results
from sonar.db.session import SessionLocal
from sonar.indices.orchestrator import (
    FinancialIndicesInputs,
    FinancialIndicesResults,
    compute_all_financial_indices,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

log = structlog.get_logger()

__all__ = [
    "T1_7_COUNTRIES",
    "FinancialPipelineOutcome",
    "InputsBuilder",
    "default_inputs_builder",
    "main",
    "run_one",
]

T1_7_COUNTRIES: tuple[str, ...] = ("US", "DE", "PT", "IT", "ES", "FR", "NL")

EXIT_OK = 0
EXIT_NO_INPUTS = 1
EXIT_DUPLICATE = 3
EXIT_IO = 4


class InputsBuilder(Protocol):
    def __call__(
        self,
        session: Session,
        country_code: str,
        observation_date: date,
    ) -> FinancialIndicesInputs: ...


def default_inputs_builder(
    session: Session,  # noqa: ARG001 — Protocol compatibility
    country_code: str,
    observation_date: date,
) -> FinancialIndicesInputs:
    """MVP default — empty bundle so orchestrator skips gracefully.

    Live-data builder (fetch connectors + assemble inputs) is **CAL-064**.
    Tests inject synthetic builders to exercise the full wiring.
    """
    return FinancialIndicesInputs(
        country_code=country_code,
        observation_date=observation_date,
    )


@dataclass(frozen=True, slots=True)
class FinancialPipelineOutcome:
    country_code: str
    observation_date: date
    results: FinancialIndicesResults
    persisted: dict[str, int]


def run_one(
    session: Session,
    country_code: str,
    observation_date: date,
    *,
    inputs_builder: InputsBuilder | None = None,
) -> FinancialPipelineOutcome:
    """Single ``(country, date)`` pipeline run."""
    builder = inputs_builder or default_inputs_builder
    inputs = builder(session, country_code, observation_date)
    results = compute_all_financial_indices(inputs)
    persisted = persist_many_financial_results(session, results)
    log.info(
        "financial_indices.persisted",
        country=country_code,
        date=observation_date.isoformat(),
        persisted=persisted,
        skips=results.skips,
    )
    return FinancialPipelineOutcome(
        country_code=country_code,
        observation_date=observation_date,
        results=results,
        persisted=persisted,
    )


def main(
    country: str = typer.Option("", "--country", help="ISO 3166-1 alpha-2 (omit with --all-t1)."),
    target_date: str = typer.Option(..., "--date", help="ISO date (e.g. 2024-01-02)."),
    all_t1: bool = typer.Option(
        False,  # noqa: FBT003
        "--all-t1",
        help="Iterate over all 7 T1 countries (US/DE/PT/IT/ES/FR/NL).",
    ),
) -> None:
    """Run the daily financial-indices pipeline."""
    try:
        obs_date = date.fromisoformat(target_date)
    except ValueError:
        typer.echo(f"Invalid --date={target_date!r}; expected ISO YYYY-MM-DD", err=True)
        sys.exit(EXIT_IO)

    targets: list[str] = list(T1_7_COUNTRIES) if all_t1 else [country]
    if not targets or targets == [""]:
        typer.echo("Must pass --country or --all-t1", err=True)
        sys.exit(EXIT_IO)

    session = SessionLocal()
    exit_code = EXIT_OK
    try:
        for c in targets:
            try:
                outcome = run_one(session, c, obs_date)
                if sum(outcome.persisted.values()) == 0:
                    log.warning(
                        "financial_indices.no_inputs",
                        country=c,
                        date=obs_date.isoformat(),
                        skips=outcome.results.skips,
                    )
                    exit_code = exit_code or EXIT_NO_INPUTS
            except DuplicatePersistError as exc:
                log.error("financial_indices.duplicate", country=c, error=str(exc))
                exit_code = EXIT_DUPLICATE
    finally:
        session.close()
    sys.exit(exit_code)


if __name__ == "__main__":  # pragma: no cover
    typer.run(main)
