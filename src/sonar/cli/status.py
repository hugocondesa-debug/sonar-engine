"""``sonar status`` — cross-cycle country snapshot (Week 7 Sprint G).

Reads the four L4 cycle tables (``credit_cycle_scores`` + ``financial_cycle_scores``
+ ``monetary_cycle_scores`` + ``economic_cycle_scores``) and renders
a Rich table with the latest score + regime + confidence per cycle
per country.

Three render modes:

- ``sonar status --country US`` — single-country summary (4 rows).
- ``sonar status --country US --verbose`` — adds L3 sub-index scores
  (E1/E2/E3/E4, M1/M2/M3/M4 via columns already on the cycle tables).
- ``sonar status --all-t1`` — 7-country x 4-cycle matrix.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Literal

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
    "T1_7_COUNTRIES",
    "CountryStatus",
    "CycleStatus",
    "L5MetaRegimeStatus",
    "app",
    "format_matrix",
    "format_status_summary",
    "format_status_verbose",
    "get_country_status",
]


EXIT_OK = 0
EXIT_IO = 4


T1_7_COUNTRIES: tuple[str, ...] = ("US", "DE", "PT", "IT", "ES", "FR", "NL")

FRESHNESS_FRESH_HOURS = 24

Freshness = Literal["fresh", "stale", "unknown"]


@dataclass(frozen=True, slots=True)
class CycleStatus:
    """Snapshot of a single L4 cycle for a ``(country, as_of_date)``."""

    cycle_code: Literal["CCCS", "FCS", "MSC", "ECS"]
    score: float
    regime: str
    confidence: float
    flags: tuple[str, ...]
    last_updated: datetime
    freshness: Freshness
    sub_scores: dict[str, float | None] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class L5MetaRegimeStatus:
    """Snapshot of the L5 meta-regime for a ``(country, as_of_date)``."""

    meta_regime: str
    confidence: float
    flags: tuple[str, ...]
    classification_reason: str
    last_updated: datetime
    freshness: Freshness


@dataclass(frozen=True, slots=True)
class CountryStatus:
    """All four L4 cycles + the L5 meta-regime for a country at a given anchor date."""

    country_code: str
    as_of_date: date
    cccs: CycleStatus | None = None
    fcs: CycleStatus | None = None
    msc: CycleStatus | None = None
    ecs: CycleStatus | None = None
    l5_meta_regime: L5MetaRegimeStatus | None = None


def _coerce_timestamp(value: object) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(str(value))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _classify_freshness(last_seen: datetime, *, now: datetime) -> Freshness:
    age = now - last_seen
    if age <= timedelta(hours=FRESHNESS_FRESH_HOURS):
        return "fresh"
    return "stale"


def _parse_flags(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    return tuple(p for p in raw.split(",") if p)


def _fetch_latest(
    session: Session,
    *,
    table: str,
    country_code: str,
    as_of: date,
    regime_column: str,
    sub_columns: dict[str, str],
) -> tuple[dict[str, object], dict[str, float | None]] | None:
    """Return the most recent row for ``(country_code, date <= as_of)`` + sub-score map.

    Returns ``None`` when no row exists. Designed to be resilient against
    missing tables (caller invokes only when the table is known present).
    """
    sub_select = ", ".join(f"{col} AS sub_{key}" for key, col in sub_columns.items())
    sub_clause = f", {sub_select}" if sub_select else ""
    row = (
        session.execute(
            text(
                "SELECT score_0_100 AS score, "
                f"{regime_column} AS regime, confidence, flags, created_at{sub_clause} "
                f"FROM {table} "
                "WHERE country_code = :c AND date <= :d "
                "ORDER BY date DESC, created_at DESC LIMIT 1"
            ),
            {"c": country_code, "d": as_of.isoformat()},
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    core = {
        "score": float(row["score"]),
        "regime": str(row["regime"]),
        "confidence": float(row["confidence"]),
        "flags": _parse_flags(row["flags"]),
        "created_at": _coerce_timestamp(row["created_at"]),
    }
    sub_scores: dict[str, float | None] = {
        key: (float(row[f"sub_{key}"]) if row.get(f"sub_{key}") is not None else None)
        for key in sub_columns
    }
    return core, sub_scores


def get_country_status(
    session: Session,
    country_code: str,
    as_of: date,
    *,
    now: datetime | None = None,
) -> CountryStatus:
    """Fetch all four L4 cycles for the country on or before ``as_of``."""
    anchor = now or datetime.now(tz=UTC)

    def _build(
        cycle_code: Literal["CCCS", "FCS", "MSC", "ECS"],
        table: str,
        regime_column: str,
        sub_columns: dict[str, str],
    ) -> CycleStatus | None:
        hit = _fetch_latest(
            session,
            table=table,
            country_code=country_code,
            as_of=as_of,
            regime_column=regime_column,
            sub_columns=sub_columns,
        )
        if hit is None:
            return None
        core, sub_scores = hit
        return CycleStatus(
            cycle_code=cycle_code,
            score=core["score"],  # type: ignore[arg-type]
            regime=core["regime"],  # type: ignore[arg-type]
            confidence=core["confidence"],  # type: ignore[arg-type]
            flags=core["flags"],  # type: ignore[arg-type]
            last_updated=core["created_at"],  # type: ignore[arg-type]
            freshness=_classify_freshness(core["created_at"], now=anchor),  # type: ignore[arg-type]
            sub_scores=sub_scores,
        )

    return CountryStatus(
        country_code=country_code,
        as_of_date=as_of,
        cccs=_build(
            "CCCS",
            "credit_cycle_scores",
            "regime",
            {
                "cs": "cs_score_0_100",
                "lc": "lc_score_0_100",
                "ms": "ms_score_0_100",
                "qs": "qs_score_0_100",
            },
        ),
        fcs=_build(
            "FCS",
            "financial_cycle_scores",
            "regime",
            {
                "f1": "f1_score_0_100",
                "f2": "f2_score_0_100",
                "f3": "f3_score_0_100",
                "f4": "f4_score_0_100",
            },
        ),
        msc=_build(
            "MSC",
            "monetary_cycle_scores",
            "regime_3band",
            {
                "m1": "m1_score_0_100",
                "m2": "m2_score_0_100",
                "m3": "m3_score_0_100",
                "m4": "m4_score_0_100",
            },
        ),
        ecs=_build(
            "ECS",
            "economic_cycle_scores",
            "regime",
            {
                "e1": "e1_score_0_100",
                "e2": "e2_score_0_100",
                "e3": "e3_score_0_100",
                "e4": "e4_score_0_100",
            },
        ),
        l5_meta_regime=_fetch_l5_meta_regime(session, country_code, as_of, now=anchor),
    )


def _fetch_l5_meta_regime(
    session: Session,
    country_code: str,
    as_of: date,
    *,
    now: datetime,
) -> L5MetaRegimeStatus | None:
    """Query ``l5_meta_regimes`` for the latest row at or before ``as_of``.

    Returns ``None`` when no row exists (expected when the L4 cycles
    persisted without meeting the Policy 1 >= 3/4 threshold, or when
    Sprint K's daily_cycles wiring has not yet run for this triplet).
    """
    row = (
        session.execute(
            text(
                "SELECT meta_regime, confidence, flags, classification_reason, created_at "
                "FROM l5_meta_regimes "
                "WHERE country_code = :c AND date <= :d "
                "ORDER BY date DESC, created_at DESC LIMIT 1"
            ),
            {"c": country_code, "d": as_of.isoformat()},
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    last_updated = _coerce_timestamp(row["created_at"])
    return L5MetaRegimeStatus(
        meta_regime=str(row["meta_regime"]),
        confidence=float(row["confidence"]),
        flags=_parse_flags(row["flags"]),
        classification_reason=str(row["classification_reason"]),
        last_updated=last_updated,
        freshness=_classify_freshness(last_updated, now=now),
    )


_REGIME_STYLE = {
    # CCCS
    "REPAIR": "yellow",
    "RECOVERY": "green",
    "BOOM": "cyan",
    "SPECULATION": "magenta",
    "DISTRESS": "red",
    # FCS
    "STRESS": "red",
    "CAUTION": "yellow",
    "OPTIMISM": "green",
    "EUPHORIA": "cyan",
    # MSC (3-band)
    "ACCOMMODATIVE": "green",
    "NEUTRAL": "white",
    "TIGHT": "red",
    # ECS
    "EXPANSION": "green",
    "PEAK_ZONE": "yellow",
    "EARLY_RECESSION": "magenta",
    "RECESSION": "red",
}


# L5 meta-regime → Rich style. Six canonical regimes per
# docs/specs/regimes/cross-cycle-meta-regimes.md §2.
_L5_REGIME_STYLE: dict[str, str] = {
    "overheating": "red",
    "stagflation_risk": "magenta",
    "late_cycle_bubble": "yellow",  # "orange" not a canonical Rich color
    "recession_risk": "red",
    "soft_landing": "green",
    "unclassified": "bright_black",  # Rich equivalent of gray
}


def _regime_markup(regime: str) -> str:
    style = _REGIME_STYLE.get(regime, "white")
    return f"[{style}]{regime}[/{style}]"


def _l5_regime_markup(meta_regime: str) -> str:
    style = _L5_REGIME_STYLE.get(meta_regime, "white")
    return f"[{style}]{meta_regime}[/{style}]"


def format_status_summary(status: CountryStatus) -> Table:
    """4-row Rich table with one row per L4 cycle plus an L5 meta-regime row."""
    table = Table(
        title=f"SONAR cycle status — {status.country_code} @ {status.as_of_date.isoformat()}",
        show_lines=False,
        header_style="bold",
    )
    table.add_column("Cycle")
    table.add_column("Score", justify="right")
    table.add_column("Regime")
    table.add_column("Confidence", justify="right")
    table.add_column("Last seen")
    table.add_column("Freshness")
    for cycle in (status.cccs, status.fcs, status.msc, status.ecs):
        if cycle is None:
            continue
        table.add_row(
            cycle.cycle_code,
            f"{cycle.score:.1f}",
            _regime_markup(cycle.regime),
            f"{cycle.confidence:.2f}",
            cycle.last_updated.isoformat(sep=" ", timespec="minutes"),
            cycle.freshness,
        )
    # L5 row — "Meta-Regime" in the cycle column, regime styled via
    # _L5_REGIME_STYLE, score column left blank (L5 has no 0-100 score).
    if status.l5_meta_regime is not None:
        l5 = status.l5_meta_regime
        table.add_row(
            "Meta-Regime",
            "—",
            _l5_regime_markup(l5.meta_regime),
            f"{l5.confidence:.2f}",
            l5.last_updated.isoformat(sep=" ", timespec="minutes"),
            l5.freshness,
        )
    else:
        table.add_row("Meta-Regime", "—", "[dim]N/A[/dim]", "—", "—", "—")
    return table


def format_status_verbose(status: CountryStatus) -> Table:
    """Extend the summary with L3 sub-score breakdowns per cycle and L5 detail."""
    table = Table(
        title=f"SONAR cycle status (verbose) — {status.country_code} "
        f"@ {status.as_of_date.isoformat()}",
        show_lines=False,
        header_style="bold",
    )
    table.add_column("Cycle")
    table.add_column("Composite", justify="right")
    table.add_column("Regime")
    table.add_column("Sub-index scores")
    table.add_column("Flags")
    for cycle in (status.cccs, status.fcs, status.msc, status.ecs):
        if cycle is None:
            continue
        sub_pairs = [f"{k.upper()}={v:.1f}" for k, v in cycle.sub_scores.items() if v is not None]
        table.add_row(
            cycle.cycle_code,
            f"{cycle.score:.1f}",
            _regime_markup(cycle.regime),
            " ".join(sub_pairs) or "—",
            ",".join(cycle.flags) or "—",
        )
    # L5 verbose row — classification_reason in the sub-index slot, flags
    # (including any L5_*_MISSING markers) in the flags column.
    if status.l5_meta_regime is not None:
        l5 = status.l5_meta_regime
        table.add_row(
            "Meta-Regime",
            "—",
            _l5_regime_markup(l5.meta_regime),
            f"reason={l5.classification_reason}",
            ",".join(l5.flags) or "—",
        )
    else:
        table.add_row("Meta-Regime", "—", "[dim]N/A[/dim]", "—", "—")
    return table


def format_matrix(statuses: list[CountryStatus]) -> Table:
    """7-country x 4-cycle matrix + L5 meta-regime column."""
    table = Table(title="SONAR cross-country cycle matrix", header_style="bold")
    table.add_column("Country")
    for cycle in ("CCCS", "FCS", "MSC", "ECS"):
        table.add_column(cycle)
    table.add_column("L5")
    for status in statuses:
        row: list[str] = [status.country_code]
        for slot in (status.cccs, status.fcs, status.msc, status.ecs):
            if slot is None:
                row.append("[dim]N/A[/dim]")
            else:
                row.append(f"{slot.score:.0f} {_regime_markup(slot.regime)}")
        if status.l5_meta_regime is None:
            row.append("[dim]N/A[/dim]")
        else:
            row.append(_l5_regime_markup(status.l5_meta_regime.meta_regime))
        table.add_row(*row)
    return table


# ---------------------------------------------------------------------------
# Typer CLI
# ---------------------------------------------------------------------------


app = typer.Typer(no_args_is_help=False, help="Cross-cycle country status dashboard.")


@app.callback(invoke_without_command=True)
def cli(
    country: str = typer.Option("", "--country", help="Single-country ISO 3166-1 alpha-2."),
    all_t1: bool = typer.Option(
        False,  # noqa: FBT003
        "--all-t1",
        help="Render the 7 T1 countries as a matrix.",
    ),
    target_date: str = typer.Option(
        "", "--date", help="Anchor date (ISO YYYY-MM-DD); default is today (UTC)."
    ),
    verbose: bool = typer.Option(
        False,  # noqa: FBT003
        "--verbose",
        help="Include L3 sub-index scores + flags (single-country only).",
    ),
) -> None:
    """Print L4 cycle scores + regimes for one country or the full T1 matrix."""
    if not country and not all_t1:
        typer.echo("Must pass --country or --all-t1", err=True)
        sys.exit(EXIT_IO)

    as_of = _parse_date_or_today(target_date)
    session = SessionLocal()
    console = Console()
    try:
        if all_t1:
            statuses = [get_country_status(session, c, as_of) for c in T1_7_COUNTRIES]
            console.print(format_matrix(statuses))
        else:
            status = get_country_status(session, country.upper(), as_of)
            renderer = format_status_verbose if verbose else format_status_summary
            console.print(renderer(status))
    except Exception as exc:
        typer.echo(f"status query failed: {exc}", err=True)
        sys.exit(EXIT_IO)
    finally:
        session.close()
    sys.exit(EXIT_OK)


def _parse_date_or_today(raw: str) -> date:
    if not raw:
        return datetime.now(tz=UTC).date()
    return date.fromisoformat(raw)


if __name__ == "__main__":  # pragma: no cover
    app()
