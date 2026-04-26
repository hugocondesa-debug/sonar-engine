"""NSS curves tenor backfill — 10 T1 countries x 60 recent business days.

Sprint 2 (Week 11) orchestrator — populates ``yield_curves_{spot,zero,
forwards,real}`` rows for the curve-supported T1 cohort over the most
recent business-day window. Two distinct code paths share this module:

* **Spot-backfill phase** — :data:`T1_SPOT_BACKFILL_COUNTRIES` (10
  countries; **GB explicitly excluded** because Sprint P.2 BoE archive
  shipped 1 580 spot rows that we must not stomp). Per-(country, date)
  the orchestrator delegates to :func:`sonar.pipelines.daily_curves.run_country`
  which runs the full 4-sibling atomic persist (spot + zero + forwards
  + real per spec §4 step 9). ``run_country`` is idempotent
  (ADR-0011 P1) — pre-INSERT existence check on spot ensures re-runs
  are no-ops.

* **GB real-only fill phase** — for each existing GB spot row in the
  window without a sibling real row, :func:`build_real_row` writes a
  real row sharing the spot's ``fit_id``. This is the only path that
  uses :func:`sonar.overlays.nss_real_writer.build_real_row` (Pattern B);
  the other 9 countries get their real rows from the in-memory builder
  inside ``run_country`` (Pattern A).

Per-country commit isolation: a failure in country *X* does not roll
back countries *Y..Z*. Per-date sub-commits within ``run_country``
preserve the 4-sibling atomicity at the row level.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date as date_t, datetime
from typing import TYPE_CHECKING

import pandas as pd
import structlog

from sonar.db.models import NSSYieldCurveReal, NSSYieldCurveSpot
from sonar.db.session import SessionLocal
from sonar.overlays.nss_real_writer import build_real_row

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session

log = structlog.get_logger()

__all__ = [
    "GB_REAL_FILL_COUNTRY",
    "T1_REAL_COUNTRIES_DERIVED",
    "T1_REAL_COUNTRIES_DIRECT",
    "T1_SPOT_BACKFILL_COUNTRIES",
    "BackfillSummary",
    "backfill_nss_curves",
]


# Spot+zero+forwards+real backfill cohort. GB excluded — 1 580 spot
# rows already shipped via Sprint P.2 BoE nominal archive. NO appended
# Sprint 7B (2026-04-26 Path C pivot — first non-EA non-TE country via
# native-CB direct cascade, Norges Bank GOVT_GENERIC_RATES).
T1_SPOT_BACKFILL_COUNTRIES: tuple[str, ...] = (
    "US",
    "DE",
    "EA",
    "FR",
    "IT",
    "ES",
    "JP",
    "CA",
    "AU",
    "PT",
    "NO",
)

# Spec §4 step 6 cohort split (Sprint 2 scope; matches
# :mod:`sonar.overlays.nss_real_writer` country sets).
T1_REAL_COUNTRIES_DIRECT: frozenset[str] = frozenset(
    {"US", "GB", "DE", "IT", "FR", "CA", "AU"},
)
T1_REAL_COUNTRIES_DERIVED: frozenset[str] = frozenset({"PT", "JP", "ES"})

# GB takes the standalone-real path (Pattern B) — its spot rows already
# exist; we only need to write the real sibling.
GB_REAL_FILL_COUNTRY: str = "GB"

DEFAULT_LOOKBACK_BD: int = 60


@dataclass(slots=True)
class BackfillSummary:
    """Per-country outcome counters for a single backfill run."""

    persisted_full: dict[str, int] = field(default_factory=dict)
    skipped_existing: dict[str, int] = field(default_factory=dict)
    skipped_insufficient: dict[str, int] = field(default_factory=dict)
    failed: dict[str, int] = field(default_factory=dict)
    gb_real_persisted: int = 0
    gb_real_skipped: int = 0
    dates_window: tuple[date_t, date_t] | None = None


def _business_days(start: date_t, end: date_t) -> list[date_t]:
    """Inclusive business-day range ``[start, end]`` (Mon-Fri)."""
    if end < start:
        return []
    rng = pd.bdate_range(start=pd.Timestamp(start), end=pd.Timestamp(end))
    return [d.date() for d in rng]


def _recent_business_days(lookback_bd: int, as_of: date_t | None) -> list[date_t]:
    """Most-recent ``lookback_bd`` business days ending on ``as_of``."""
    end = as_of or datetime.now(UTC).date()
    rng = pd.bdate_range(end=pd.Timestamp(end), periods=lookback_bd)
    return [d.date() for d in rng]


def _gb_spot_rows_in_window(
    session: Session,
    start: date_t,
    end: date_t,
) -> list[NSSYieldCurveSpot]:
    return list(
        session.query(NSSYieldCurveSpot)
        .filter(
            NSSYieldCurveSpot.country_code == GB_REAL_FILL_COUNTRY,
            NSSYieldCurveSpot.date >= start,
            NSSYieldCurveSpot.date <= end,
        )
        .order_by(NSSYieldCurveSpot.date.asc())
        .all(),
    )


def _gb_real_already_exists(
    session: Session,
    fit_id: str,
) -> bool:
    return (
        session.query(NSSYieldCurveReal.id).filter(NSSYieldCurveReal.fit_id == fit_id).first()
        is not None
    )


def _fill_gb_real(
    session: Session,
    start: date_t,
    end: date_t,
    summary: BackfillSummary,
) -> None:
    """Pattern B real-only fill for GB existing spot rows in the window."""
    spot_rows = _gb_spot_rows_in_window(session, start, end)
    for spot_row in spot_rows:
        if _gb_real_already_exists(session, spot_row.fit_id):
            summary.gb_real_skipped += 1
            continue
        try:
            real_row = build_real_row(
                session=session,
                country_code=GB_REAL_FILL_COUNTRY,
                observation_date=spot_row.date,
                spot_row=spot_row,
                # GB linker (BoE ILG) connector wiring is Phase 2+; for
                # now build_real_row falls through to the derived path
                # if E[π] canonical is available, else logs + skips.
                linker_yields=None,
            )
            if real_row is None:
                summary.gb_real_skipped += 1
                continue
            session.add(real_row)
            session.commit()
            summary.gb_real_persisted += 1
        except Exception as exc:
            session.rollback()
            log.error(
                "nss_curves_backfill.gb_real_failed",
                date=spot_row.date.isoformat(),
                fit_id=spot_row.fit_id,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            summary.gb_real_skipped += 1


async def _run_spot_phase(
    countries: tuple[str, ...],
    dates: list[date_t],
    cache_dir: Path,
    summary: BackfillSummary,
) -> None:
    """Iterate ``dates x countries`` through ``run_country``.

    Per-country counters drive the summary report. Per-date connector
    instances are recycled by ``_orchestrate_countries`` to keep the
    HTTP cache hot — we wrap that loop for the date dimension here.
    """
    # Local import keeps the module loadable in non-pipeline contexts
    # (e.g. tests for ``build_real_row`` alone).
    from sonar.pipelines.daily_curves import (  # noqa: PLC0415
        _orchestrate_countries,
    )

    for observation_date in dates:
        outcomes = await _orchestrate_countries(list(countries), observation_date, cache_dir)
        for country in outcomes.persisted:
            summary.persisted_full[country] = summary.persisted_full.get(country, 0) + 1
        for country in outcomes.skipped_existing:
            summary.skipped_existing[country] = summary.skipped_existing.get(country, 0) + 1
        for country, _detail in outcomes.skipped_insufficient:
            summary.skipped_insufficient[country] = summary.skipped_insufficient.get(country, 0) + 1
        for country, _detail in outcomes.failed:
            summary.failed[country] = summary.failed.get(country, 0) + 1


async def backfill_nss_curves(
    *,
    start: date_t | None = None,
    end: date_t | None = None,
    lookback_bd: int = DEFAULT_LOOKBACK_BD,
    countries: tuple[str, ...] = T1_SPOT_BACKFILL_COUNTRIES,
    cache_dir: Path,
    fill_gb_real: bool = True,
) -> BackfillSummary:
    """Backfill 4-sibling NSS rows for the T1 cohort over a date window.

    Date window is either explicit ``[start, end]`` or the trailing
    ``lookback_bd`` business days ending on ``end`` / today (UTC). If
    only one of ``start`` / ``end`` is set, the other is derived from
    ``lookback_bd``.

    GB is excluded from ``countries`` by default (preserves Sprint P.2
    spot rows). When ``fill_gb_real`` is true, the orchestrator runs a
    second phase that adds real-only rows for GB existing spot rows in
    the same window via :func:`build_real_row`.
    """
    if start is not None and end is not None:
        dates = _business_days(start, end)
    elif end is not None:
        dates = _recent_business_days(lookback_bd, end)
    else:
        dates = _recent_business_days(lookback_bd, start)

    if not dates:
        return BackfillSummary()

    summary = BackfillSummary(dates_window=(dates[0], dates[-1]))

    await _run_spot_phase(countries, dates, cache_dir, summary)

    if fill_gb_real:
        session = SessionLocal()
        try:
            _fill_gb_real(session, dates[0], dates[-1], summary)
        finally:
            session.close()

    log.info(
        "nss_curves_backfill.completed",
        countries=list(countries),
        dates_window=[dates[0].isoformat(), dates[-1].isoformat()],
        n_dates=len(dates),
        persisted_full=summary.persisted_full,
        skipped_existing=summary.skipped_existing,
        skipped_insufficient=summary.skipped_insufficient,
        failed=summary.failed,
        gb_real_persisted=summary.gb_real_persisted,
        gb_real_skipped=summary.gb_real_skipped,
    )

    return summary
