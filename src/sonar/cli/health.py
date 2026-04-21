"""``sonar health`` — pipeline freshness + success snapshot (Week 7 Sprint G).

Reads the canonical output tables each daily pipeline writes to, buckets
the most-recent row per pipeline into **fresh** / **stale** / **missing**,
and renders a Rich table.

The command is operational, not analytical — it answers "did yesterday's
cron run land all the rows we expect?" without needing a separate
journal / log aggregator. Phase 2+ ops layers a real alerting stack on
top via the :class:`AlertSink` Protocol shipped here.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Literal, Protocol

import structlog
import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import text

from sonar.db.session import SessionLocal

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


log = structlog.get_logger()


__all__ = [
    "PIPELINE_TO_TABLE",
    "AlertSink",
    "NullAlertSink",
    "PipelineHealth",
    "app",
    "collect_pipeline_health",
    "format_health_report",
]


EXIT_OK = 0
EXIT_IO = 4


FreshnessStatus = Literal["fresh", "stale", "missing"]


# Pipeline → canonical output table. When a pipeline writes to multiple
# tables we pick the one most indicative of the full run landing (e.g.
# overlays → erp_canonical is proxied by any ERP publish; cycle tables
# each get one entry so the ops dashboard shows per-cycle freshness).
PIPELINE_TO_TABLE: dict[str, tuple[str, str]] = {
    "daily_curves": ("yield_curves_spot", "created_at"),
    "daily_bis_ingestion": ("bis_credit_raw", "fetched_at"),
    "daily_overlays (ERP canonical)": ("erp_canonical", "created_at"),
    "daily_overlays (index_values)": ("index_values", "created_at"),
    "daily_overlays (ratings)": ("ratings_consolidated", "created_at"),
    "daily_credit_indices (L1)": ("credit_to_gdp_stock", "created_at"),
    "daily_credit_indices (L4)": ("dsr", "created_at"),
    "daily_financial_indices (F1)": ("f1_valuations", "created_at"),
    "daily_financial_indices (F4)": ("f4_positioning", "created_at"),
    "daily_economic_indices (E1)": ("idx_economic_e1_activity", "created_at"),
    "daily_economic_indices (E4)": ("idx_economic_e4_sentiment", "created_at"),
    "daily_monetary_indices (M1)": ("monetary_m1_effective_rates", "created_at"),
    "daily_monetary_indices (M4)": ("monetary_m4_fci", "created_at"),
    "daily_cycles (CCCS)": ("credit_cycle_scores", "created_at"),
    "daily_cycles (FCS)": ("financial_cycle_scores", "created_at"),
    "daily_cycles (MSC)": ("monetary_cycle_scores", "created_at"),
    "daily_cycles (ECS)": ("economic_cycle_scores", "created_at"),
}

FRESHNESS_FRESH_HOURS = 24
FRESHNESS_STALE_HOURS = 72


@dataclass(frozen=True, slots=True)
class PipelineHealth:
    """Per-pipeline freshness snapshot."""

    pipeline_name: str
    table_name: str
    last_run_timestamp: datetime | None
    freshness_status: FreshnessStatus
    rows_total: int


class AlertSink(Protocol):
    """Sink interface for pipeline-health alerts (Phase 2+ stub).

    Real implementations will post to email / webhook / Slack; the
    Phase 1 default :class:`NullAlertSink` is a no-op so the health
    command ships without any external dependency. Operators wire a
    concrete sink when they stand up the alerting stack.
    """

    def emit(self, severity: Literal["info", "warning", "error"], message: str) -> None: ...


class NullAlertSink:
    """No-op alert sink — default. Drops every ``emit`` silently."""

    def emit(
        self,
        severity: Literal["info", "warning", "error"],  # noqa: ARG002
        message: str,  # noqa: ARG002
    ) -> None:
        return None


def _classify(last_seen: datetime | None, *, now: datetime) -> FreshnessStatus:
    if last_seen is None:
        return "missing"
    age = now - last_seen
    if age <= timedelta(hours=FRESHNESS_FRESH_HOURS):
        return "fresh"
    if age <= timedelta(hours=FRESHNESS_STALE_HOURS):
        return "stale"
    return "missing"


def _table_exists(session: Session, table_name: str) -> bool:
    row = session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
        {"name": table_name},
    ).first()
    return row is not None


def _query_latest(
    session: Session, table_name: str, ts_column: str, country_code: str | None
) -> tuple[datetime | None, int]:
    """Return ``(max(ts_column), count(*))`` for the table, optionally scoped."""
    where = "WHERE country_code = :c" if country_code else ""
    params: dict[str, str] = {"c": country_code} if country_code else {}
    row = session.execute(
        text(f"SELECT MAX({ts_column}) AS last_ts, COUNT(*) AS n FROM {table_name} {where}"),
        params,
    ).first()
    if row is None:
        return None, 0
    last_ts_raw, count_raw = row
    count = int(count_raw or 0)
    if last_ts_raw is None:
        return None, count
    last_ts = _coerce_timestamp(last_ts_raw)
    return last_ts, count


def _coerce_timestamp(value: object) -> datetime:
    """Normalise a SQLAlchemy-returned timestamp into a tz-aware UTC datetime."""
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    # SQLite often surfaces text; parse best-effort.
    parsed = datetime.fromisoformat(str(value))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def collect_pipeline_health(
    session: Session,
    *,
    country_code: str | None = None,
    now: datetime | None = None,
) -> list[PipelineHealth]:
    """Return a :class:`PipelineHealth` row per entry in :data:`PIPELINE_TO_TABLE`.

    Missing tables yield a ``missing``-status row with ``rows_total=0``
    (no query against a non-existent table). ``country_code`` filters
    the per-pipeline queries when the underlying table carries a
    ``country_code`` column — all pipeline tables in the current
    catalog do, so this is the happy path.
    """
    anchor = now or datetime.now(tz=UTC)
    out: list[PipelineHealth] = []
    for pipeline_name, (table_name, ts_column) in PIPELINE_TO_TABLE.items():
        if not _table_exists(session, table_name):
            out.append(
                PipelineHealth(
                    pipeline_name=pipeline_name,
                    table_name=table_name,
                    last_run_timestamp=None,
                    freshness_status="missing",
                    rows_total=0,
                )
            )
            continue
        last_ts, rows_total = _query_latest(session, table_name, ts_column, country_code)
        out.append(
            PipelineHealth(
                pipeline_name=pipeline_name,
                table_name=table_name,
                last_run_timestamp=last_ts,
                freshness_status=_classify(last_ts, now=anchor),
                rows_total=rows_total,
            )
        )
    return out


_STATUS_STYLE: dict[FreshnessStatus, str] = {
    "fresh": "green",
    "stale": "yellow",
    "missing": "red",
}


def format_health_report(healths: list[PipelineHealth]) -> Table:
    """Render a Rich table — caller prints via a :class:`Console`."""
    table = Table(
        title="SONAR pipeline health",
        show_lines=False,
        header_style="bold",
    )
    table.add_column("Pipeline")
    table.add_column("Table", style="dim")
    table.add_column("Last seen")
    table.add_column("Status")
    table.add_column("Rows", justify="right")
    for h in healths:
        last_str = (
            h.last_run_timestamp.isoformat(sep=" ", timespec="minutes")
            if h.last_run_timestamp
            else "—"
        )
        style = _STATUS_STYLE[h.freshness_status]
        table.add_row(
            h.pipeline_name,
            h.table_name,
            last_str,
            f"[{style}]{h.freshness_status}[/{style}]",
            str(h.rows_total),
        )
    return table


# ---------------------------------------------------------------------------
# Typer CLI
# ---------------------------------------------------------------------------


app = typer.Typer(no_args_is_help=False, help="Pipeline freshness + success snapshot.")


@app.callback(invoke_without_command=True)
def cli(
    country: str = typer.Option("", "--country", help="Filter by ISO 3166-1 alpha-2 country code."),
) -> None:
    """Print the pipeline health report."""
    session = SessionLocal()
    try:
        healths = collect_pipeline_health(session, country_code=country.upper() or None)
    except Exception as exc:
        typer.echo(f"health collection failed: {exc}", err=True)
        sys.exit(EXIT_IO)
    finally:
        session.close()
    console = Console()
    console.print(format_health_report(healths))
    sys.exit(EXIT_OK)


if __name__ == "__main__":  # pragma: no cover
    app()
