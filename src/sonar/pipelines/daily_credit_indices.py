"""Daily credit indices pipeline — orchestrate L1/L2/L3/L4 persistence.

Per credit-indices-brief-v3 §Commit 9, the credit indices live in their
own pipeline rather than extending ``daily_cost_of_capital.py`` (that
module is already 376 LOC; brief §9 guidance said split when >300).
k_e composition is unaffected — credit indices do not enter the k_e
formula in this phase; they are inputs for the CCCS composite (Week 5+).

Build inputs strategy:

- **Default path**: empty bundle → orchestrator skips (kept for
  backward-compat with credit-track tests).
- **DB-backed path** (CAL-058): :class:`DbBackedInputsBuilder` reads
  persisted BIS observations from ``bis_credit_raw`` and assembles
  L1 + L2 inputs directly. L3 + L4 require inputs beyond BIS (LCU
  series for L3; lending-rate + maturity for L4) and stay ``None``
  under this builder; future CALs wire their own sources.

CLI::

    python -m sonar.pipelines.daily_credit_indices --country PT --date 2024-06-30
    python -m sonar.pipelines.daily_credit_indices --all-t1 --date 2024-06-30
    python -m sonar.pipelines.daily_credit_indices --country US --date 2024-06-30 --backend=db

Exit codes mirror :mod:`daily_cost_of_capital`: 0 clean, 1 no inputs,
3 duplicate, 4 IO.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date
from itertools import pairwise
from typing import TYPE_CHECKING, Protocol

import structlog
import typer

from sonar.db.models import BisCreditRaw
from sonar.db.persistence import DuplicatePersistError, persist_many_credit_results
from sonar.db.session import SessionLocal
from sonar.indices.credit.l1_credit_gdp_stock import CreditGdpStockInputs
from sonar.indices.credit.l2_credit_gdp_gap import CreditGdpGapInputs
from sonar.indices.orchestrator import (
    CreditIndicesInputs,
    CreditIndicesResults,
    compute_all_credit_indices,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

log = structlog.get_logger()

__all__ = [
    "L1_L2_LOOKBACK_YEARS",
    "MIN_L1_HISTORY_QUARTERS",
    "MIN_L2_HISTORY_QUARTERS",
    "T1_7_COUNTRIES",
    "CreditPipelineOutcome",
    "DbBackedInputsBuilder",
    "InputsBuilder",
    "InsufficientInputsError",
    "default_inputs_builder",
    "main",
    "run_one",
]

T1_7_COUNTRIES: tuple[str, ...] = ("US", "DE", "PT", "IT", "ES", "FR", "NL")

# DbBackedInputsBuilder history windows + hard minima per spec §§2-4 for
# L1 / L2. L1 needs a rolling 20Y z-score baseline; L2 needs enough
# quarters for HP one-sided filter stability (spec recommends 25Y).
L1_L2_LOOKBACK_YEARS: int = 22  # fetch 22Y of history; compute window is 20Y
MIN_L1_HISTORY_QUARTERS: int = 20  # hard min (5Y) for meaningful z-score
MIN_L2_HISTORY_QUARTERS: int = 80  # 20Y minimum for credible HP trend

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
    """Backward-compat default — returns an empty bundle so the orchestrator skips.

    Opt into DB-backed assembly via :class:`DbBackedInputsBuilder`
    (CAL-058).
    """
    return CreditIndicesInputs(
        country_code=country_code,
        observation_date=observation_date,
    )


class InsufficientInputsError(Exception):
    """Raised by :class:`DbBackedInputsBuilder` when history falls short.

    The builder prefers this over silently returning a partial bundle
    so the pipeline surfaces data gaps as exit-code 1 (no inputs)
    rather than trying to compute a degraded sub-index.
    """


class DbBackedInputsBuilder:
    """Reads ``bis_credit_raw`` and assembles L1 + L2 inputs for compute.

    Scope (CAL-058 c4/6):

    * L1 (credit-to-GDP stock) + L2 (credit-to-GDP gap) — assembled
      from ``WS_TC`` quarterly observations over the trailing
      :data:`L1_L2_LOOKBACK_YEARS`. Interpolation fills single-quarter
      gaps linearly; larger gaps or history below the hard minimum
      raise :class:`InsufficientInputsError`.
    * L3 (credit impulse) — **left None**. Requires LCU levels of
      credit + GDP which ``bis_credit_raw`` does not carry. Future
      CAL will wire FRED / Eurostat LCU ingestion.
    * L4 (DSR) — **left None**. Requires lending rate + average
      maturity + segment debt-to-GDP (decimal) not available from
      ``bis_credit_raw`` alone. Future CAL will assemble from NSS +
      household-credit splits.

    Orchestrator skips any sub-index whose input slot is ``None``;
    downstream persistence writes whichever indices computed.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def __call__(
        self, session: Session, country_code: str, observation_date: date
    ) -> CreditIndicesInputs:  # pragma: no cover — trivial delegate
        return self.build(country_code, observation_date, session=session)

    def build(
        self,
        country_code: str,
        observation_date: date,
        *,
        session: Session | None = None,
    ) -> CreditIndicesInputs:
        """Fetch + assemble inputs. Raises :class:`InsufficientInputsError`."""
        sess = session or self.session
        ws_tc_rows = self._fetch_rows(sess, country_code, observation_date, "WS_TC")
        if not ws_tc_rows:
            msg = (
                f"No WS_TC observations in bis_credit_raw for country={country_code} "
                f"up to {observation_date.isoformat()}"
            )
            raise InsufficientInputsError(msg)

        ratio_history = _interpolate_quarterly([(r.date, r.value_raw) for r in ws_tc_rows])
        if len(ratio_history) < MIN_L1_HISTORY_QUARTERS:
            msg = (
                f"WS_TC history too short for L1 (n={len(ratio_history)} "
                f"< {MIN_L1_HISTORY_QUARTERS})"
            )
            raise InsufficientInputsError(msg)

        current_ratio = ratio_history[-1]

        l1 = CreditGdpStockInputs(
            country_code=country_code,
            observation_date=observation_date,
            ratio_pct=current_ratio,
            ratio_pct_history=tuple(ratio_history),
        )
        l2 = (
            CreditGdpGapInputs(
                country_code=country_code,
                observation_date=observation_date,
                ratio_pct_history=tuple(ratio_history),
            )
            if len(ratio_history) >= MIN_L2_HISTORY_QUARTERS
            else None
        )
        return CreditIndicesInputs(
            country_code=country_code,
            observation_date=observation_date,
            l1=l1,
            l2=l2,
            l3=None,  # requires LCU series not in bis_credit_raw
            l4=None,  # requires lending rate + maturity not in bis_credit_raw
        )

    @staticmethod
    def _fetch_rows(
        session: Session, country_code: str, observation_date: date, dataflow: str
    ) -> list[BisCreditRaw]:
        cutoff = observation_date.replace(year=observation_date.year - L1_L2_LOOKBACK_YEARS)
        return (
            session.query(BisCreditRaw)
            .filter(
                BisCreditRaw.country_code == country_code,
                BisCreditRaw.dataflow == dataflow,
                BisCreditRaw.date >= cutoff,
                BisCreditRaw.date <= observation_date,
            )
            .order_by(BisCreditRaw.date.asc())
            .all()
        )


def _interpolate_quarterly(points: list[tuple[date, float]]) -> list[float]:
    """Sort by date, fill single-quarter gaps via linear interp; raise on larger.

    BIS ingests quarterly (March / June / September / December). Missing
    intermediate quarters are interpolated if exactly one quarter short;
    multi-quarter gaps raise :class:`InsufficientInputsError` (caller
    decides whether to skip or abort).
    """
    if not points:
        return []
    sorted_points = sorted(points, key=lambda p: p[0])
    out: list[float] = [sorted_points[0][1]]
    for prev, curr in pairwise(sorted_points):
        q_gap = _quarters_between(prev[0], curr[0])
        if q_gap == 1:
            out.append(curr[1])
            continue
        if q_gap == 2:
            # One missing quarter — linear interp.
            out.append((prev[1] + curr[1]) / 2.0)
            out.append(curr[1])
            continue
        msg = (
            f"Gap of {q_gap} quarters between {prev[0]} and {curr[0]} "
            f"exceeds interpolation tolerance of 1 quarter"
        )
        raise InsufficientInputsError(msg)
    return out


def _quarters_between(earlier: date, later: date) -> int:
    """Calendar-quarter distance; expects dates on quarter-ends."""
    return (later.year - earlier.year) * 4 + (later.month - earlier.month) // 3


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
    backend: str = typer.Option(
        "default",
        "--backend",
        help="Inputs source: 'default' (empty bundle skip) or 'db' (DbBackedInputsBuilder).",
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
    if backend not in {"default", "db"}:
        typer.echo(f"Unknown --backend={backend!r}; expected 'default' or 'db'", err=True)
        sys.exit(EXIT_IO)

    session = SessionLocal()
    builder: InputsBuilder = (
        DbBackedInputsBuilder(session) if backend == "db" else default_inputs_builder
    )
    exit_code = EXIT_OK
    try:
        for c in targets:
            try:
                outcome = run_one(session, c, obs_date, inputs_builder=builder)
                if sum(outcome.persisted.values()) == 0:
                    log.warning(
                        "credit_indices.no_inputs",
                        country=c,
                        date=obs_date.isoformat(),
                        skips=outcome.results.skips,
                    )
                    exit_code = exit_code or EXIT_NO_INPUTS
            except InsufficientInputsError as exc:
                log.error("credit_indices.insufficient_inputs", country=c, error=str(exc))
                exit_code = exit_code or EXIT_NO_INPUTS
            except DuplicatePersistError as exc:
                log.error("credit_indices.duplicate", country=c, error=str(exc))
                exit_code = EXIT_DUPLICATE
    finally:
        session.close()
    sys.exit(exit_code)


if __name__ == "__main__":  # pragma: no cover
    typer.run(main)
