"""Retention policies + SQLite VACUUM helper (Week 7 Sprint G).

Raw-L0 tables carry the biggest row volumes and the least long-term
value once their derived indices/cycles are persisted. Retention
prunes those tables per :data:`RETENTION_POLICIES`:

- ``bis_credit_raw`` — keep **10 years**.
- ``yield_curves_spot`` — keep **15 years** (E2 Leading needs a long
  window for its z-score history baseline).
- ``yield_curves_forwards`` — keep **10 years**.
- ``ratings_agency_raw`` — keep **5 years**.

All other tables — L3 indices, L4 cycle composites, the generic
``index_values`` store (CRP + EXPINF) — are kept **forever**. Composite
history is compact relative to raw ticks and high-value for
backtesting.

Typer CLI exposes:

- ``sonar retention run --dry-run`` (default): report what would be
  deleted without touching the database.
- ``sonar retention run --execute``: actually delete the rows.
- ``sonar retention vacuum``: run SQLite ``VACUUM`` to reclaim disk
  space after deletions. **Takes an exclusive lock** on the database
  for the duration of the operation; run off-hours.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
import typer
from sqlalchemy import text

from sonar.db.session import SessionLocal

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


log = structlog.get_logger()


__all__ = [
    "RETENTION_POLICIES",
    "RetentionReport",
    "TablePolicy",
    "app",
    "apply_retention",
    "vacuum_sqlite",
]


EXIT_OK = 0
EXIT_IO = 4


@dataclass(frozen=True, slots=True)
class TablePolicy:
    """Retention policy for a single table.

    ``date_column`` names the column used to decide row age. All raw
    tables in the catalog use a simple ``date`` column; ORM-managed
    tables could also key on ``created_at`` but the current policy set
    sticks to business-date pruning so back-dated inserts are not
    pruned spuriously.
    """

    table_name: str
    date_column: str
    keep_years: int


RETENTION_POLICIES: tuple[TablePolicy, ...] = (
    TablePolicy(table_name="bis_credit_raw", date_column="date", keep_years=10),
    TablePolicy(table_name="yield_curves_spot", date_column="date", keep_years=15),
    TablePolicy(table_name="yield_curves_forwards", date_column="date", keep_years=10),
    TablePolicy(table_name="ratings_agency_raw", date_column="date", keep_years=5),
)


@dataclass(frozen=True, slots=True)
class RetentionReport:
    """Summary of a retention pass (dry-run or execute)."""

    executed: bool
    per_table: dict[str, int] = field(default_factory=dict)
    skipped: dict[str, str] = field(default_factory=dict)
    total_rows: int = 0


def _table_exists(session: Session, table_name: str) -> bool:
    """Return True iff ``table_name`` is present in the connected DB."""
    row = session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
        {"name": table_name},
    ).first()
    return row is not None


def _cutoff_for(policy: TablePolicy, today: date) -> date:
    # keep_years measured in 365-day increments to stay portable.
    return today - timedelta(days=365 * policy.keep_years)


def apply_retention(
    session: Session,
    *,
    dry_run: bool = True,
    today: date | None = None,
    policies: tuple[TablePolicy, ...] = RETENTION_POLICIES,
) -> RetentionReport:
    """Apply retention policies; returns a per-table count report.

    ``dry_run=True`` (default) counts rows older than the cutoff but
    never deletes. ``dry_run=False`` deletes in a single transaction
    per table; failures roll back that table's delete but still attempt
    the remaining policies. Missing tables (defensive — none of the
    current set should be absent) are recorded in ``skipped``.
    """
    anchor = today or datetime.now(tz=UTC).date()
    per_table: dict[str, int] = {}
    skipped: dict[str, str] = {}
    total = 0

    for policy in policies:
        if not _table_exists(session, policy.table_name):
            skipped[policy.table_name] = "table missing"
            continue
        cutoff = _cutoff_for(policy, anchor)
        count_row = session.execute(
            text(f"SELECT COUNT(*) FROM {policy.table_name} WHERE {policy.date_column} < :cutoff"),
            {"cutoff": cutoff.isoformat()},
        ).scalar_one()
        n = int(count_row or 0)
        per_table[policy.table_name] = n
        total += n
        if dry_run or n == 0:
            continue
        try:
            session.execute(
                text(f"DELETE FROM {policy.table_name} WHERE {policy.date_column} < :cutoff"),
                {"cutoff": cutoff.isoformat()},
            )
            session.commit()
        except Exception as exc:
            session.rollback()
            skipped[policy.table_name] = f"delete failed: {exc}"

    log.info(
        "retention.applied",
        dry_run=dry_run,
        per_table=per_table,
        skipped=skipped,
        total=total,
    )
    return RetentionReport(
        executed=not dry_run,
        per_table=per_table,
        skipped=skipped,
        total_rows=total,
    )


def vacuum_sqlite(session: Session) -> tuple[int, int]:
    """Run ``VACUUM`` and return ``(bytes_before, bytes_after)``.

    VACUUM rebuilds the database file from scratch, reclaiming space
    left by prior deletes. It holds an exclusive lock for the duration
    so callers should schedule it off-hours. Sizes are best-effort and
    only meaningful for file-backed SQLite databases (for in-memory
    engines both values return ``0``).
    """
    size_before = _database_size(session)
    session.execute(text("VACUUM"))
    session.commit()
    size_after = _database_size(session)
    log.info(
        "retention.vacuum_done",
        bytes_before=size_before,
        bytes_after=size_after,
        reclaimed=size_before - size_after,
    )
    return size_before, size_after


def _database_size(session: Session) -> int:
    """Return current SQLite database file size in bytes (0 for in-memory)."""
    bind = session.bind
    if bind is None:
        return 0
    url = str(getattr(bind, "url", ""))
    path_str = url.removeprefix("sqlite:///") if url.startswith("sqlite:///") else ""
    if not path_str:
        return 0
    path = Path(path_str)
    return path.stat().st_size if path.exists() else 0


# ---------------------------------------------------------------------------
# Typer CLI
# ---------------------------------------------------------------------------


app = typer.Typer(no_args_is_help=True, help="Retention policies + SQLite VACUUM.")


@app.command("run")
def cli_run(
    dry_run: bool = typer.Option(
        True,  # noqa: FBT003
        "--dry-run/--execute",
        help="Dry-run (default, safe) reports counts; --execute deletes rows.",
    ),
) -> None:
    """Apply retention policies (dry-run by default)."""
    session = SessionLocal()
    try:
        report = apply_retention(session, dry_run=dry_run)
    except Exception as exc:
        typer.echo(f"retention failed: {exc}", err=True)
        sys.exit(EXIT_IO)
    finally:
        session.close()

    title = "DRY-RUN" if not report.executed else "EXECUTED"
    typer.echo(f"[retention {title}] total={report.total_rows}")
    for table, n in sorted(report.per_table.items()):
        typer.echo(f"  - {table}: {n} rows")
    if report.skipped:
        for table, reason in sorted(report.skipped.items()):
            typer.echo(f"  - {table}: SKIPPED ({reason})")
    sys.exit(EXIT_OK)


@app.command("vacuum")
def cli_vacuum() -> None:
    """Run SQLite ``VACUUM`` to reclaim space after retention deletes."""
    session = SessionLocal()
    try:
        before, after = vacuum_sqlite(session)
    except Exception as exc:
        typer.echo(f"vacuum failed: {exc}", err=True)
        sys.exit(EXIT_IO)
    finally:
        session.close()

    if before == 0:
        typer.echo("[vacuum] in-memory database — size reclaim not applicable")
    else:
        reclaimed = before - after
        typer.echo(f"[vacuum] {before} -> {after} bytes (reclaimed {reclaimed})")
    sys.exit(EXIT_OK)


if __name__ == "__main__":  # pragma: no cover
    app()
