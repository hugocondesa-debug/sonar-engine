"""Daily credit indices pipeline — orchestrate L1/L2/L3/L4 persistence.

Per credit-indices-brief-v3 §Commit 9, the credit indices live in their
own pipeline rather than extending ``daily_cost_of_capital.py`` (that
module is already 376 LOC; brief §9 guidance said split when >300).
k_e composition is unaffected — credit indices do not enter the k_e
formula in this phase; they are inputs for the CCCS composite (Week 5+).

Build inputs strategy:

- **Production path** (future: post-BIS-ingestion brief): read the
  latest persisted BIS rows (once we have an ingestion pipeline) and
  assemble :class:`CreditIndicesInputs` from the DB.
- **Current MVP path**: exposes a pluggable ``build_inputs`` callable
  so the pipeline structure is ready for BIS ingestion but the default
  behaviour is a conservative skip (all four sub-indices record
  ``no inputs provided`` in the orchestrator skips dict). Tests inject
  a synthetic builder to exercise the end-to-end wiring.

CLI::

    python -m sonar.pipelines.daily_credit_indices --country PT --date 2024-06-30
    python -m sonar.pipelines.daily_credit_indices --all-t1 --date 2024-06-30

Exit codes mirror :mod:`daily_cost_of_capital`: 0 clean, 1 no inputs,
3 duplicate, 4 IO.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Protocol

import structlog
import typer

from sonar.db.persistence import DuplicatePersistError, persist_many_credit_results
from sonar.db.session import SessionLocal
from sonar.indices.orchestrator import (
    CreditIndicesInputs,
    CreditIndicesResults,
    compute_all_credit_indices,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

log = structlog.get_logger()

__all__ = [
    "T1_7_COUNTRIES",
    "CreditPipelineOutcome",
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
    """Build :class:`CreditIndicesInputs` for a ``(country, date)``.

    Returning a bundle with all four sub-index slots ``None`` triggers
    graceful skips downstream (tested path for the MVP default builder).
    """

    def __call__(
        self, session: Session, country_code: str, observation_date: date
    ) -> CreditIndicesInputs: ...


def default_inputs_builder(
    session: Session,  # noqa: ARG001 — kept for Protocol compatibility
    country_code: str,
    observation_date: date,
) -> CreditIndicesInputs:
    """MVP default — returns an empty bundle so the orchestrator skips.

    The real implementation will read the latest persisted BIS rows for
    ``(country, date)`` and assemble typed inputs; that wiring is
    deferred to a dedicated BIS-ingestion brief (CAL-058 surfaced in
    Commit 10 retro).
    """
    return CreditIndicesInputs(
        country_code=country_code,
        observation_date=observation_date,
    )


@dataclass(frozen=True, slots=True)
class CreditPipelineOutcome:
    country_code: str
    observation_date: date
    results: CreditIndicesResults
    persisted: dict[str, int]


def run_one(
    session: Session,
    country_code: str,
    observation_date: date,
    *,
    inputs_builder: InputsBuilder | None = None,
) -> CreditPipelineOutcome:
    """Single ``(country, date)`` run: build inputs → compute → persist."""
    builder = inputs_builder or default_inputs_builder
    inputs = builder(session, country_code, observation_date)
    results = compute_all_credit_indices(inputs)
    persisted = persist_many_credit_results(session, results)
    log.info(
        "credit_indices.persisted",
        country=country_code,
        date=observation_date.isoformat(),
        persisted=persisted,
        skips=results.skips,
    )
    return CreditPipelineOutcome(
        country_code=country_code,
        observation_date=observation_date,
        results=results,
        persisted=persisted,
    )


def main(
    country: str = typer.Option("", "--country", help="ISO 3166-1 alpha-2 (omit with --all-t1)."),
    target_date: str = typer.Option(..., "--date", help="ISO date (e.g. 2024-06-30)."),
    all_t1: bool = typer.Option(
        False,  # noqa: FBT003
        "--all-t1",
        help="Iterate over all 7 T1 countries (US/DE/PT/IT/ES/FR/NL).",
    ),
) -> None:
    """Run the daily credit-indices pipeline."""
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
                        "credit_indices.no_inputs",
                        country=c,
                        date=obs_date.isoformat(),
                        skips=outcome.results.skips,
                    )
                    exit_code = exit_code or EXIT_NO_INPUTS
            except DuplicatePersistError as exc:
                log.error("credit_indices.duplicate", country=c, error=str(exc))
                exit_code = EXIT_DUPLICATE
    finally:
        session.close()
    sys.exit(exit_code)


if __name__ == "__main__":  # pragma: no cover
    typer.run(main)
