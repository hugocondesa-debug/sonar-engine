"""Damodaran monthly ERP external-reference backfill orchestrator (Sprint 3.1).

Iterates calendar months in the requested window, fetches each via the
existing :class:`sonar.connectors.damodaran.DamodaranConnector`, and
persists ``ERPExternalReferenceRow`` rows with
``source='damodaran_monthly'`` (one row per ``start_of_month``).

Idempotent via the ``UNIQUE (market_index, date, source)`` constraint —
duplicate rows are skipped at the per-month level (``skipped_existing``)
so re-runs over the same window are safe.

Damodaran's publication lag is ~2 months: the orchestrator silently
counts months that the connector returns ``None`` for under
``skipped_unavailable`` (e.g. running in April 2026 typically yields
through Feb 2026 at the latest, depending on Damodaran's cadence).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_t
from typing import TYPE_CHECKING

import httpx
import structlog

from sonar.connectors.damodaran import DamodaranConnector
from sonar.db.models import ERPExternalReferenceRow
from sonar.overlays.erp_external.damodaran import build_damodaran_external_row
from sonar.overlays.exceptions import (
    DataUnavailableError,
    InsufficientDataError,
    OverlayError,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from sqlalchemy.orm import Session

log = structlog.get_logger()

# Damodaran monthly implied-ERP archive starts at Sep 2008 (file
# ``ERPSep08.xlsx``); earlier requests are clamped with a warning.
DAMODARAN_MONTHLY_START = date_t(2008, 9, 1)


@dataclass(frozen=True)
class DamodaranBackfillResult:
    """Aggregate counters returned by :func:`backfill_damodaran_monthly`."""

    persisted: int
    skipped_existing: int
    skipped_unavailable: int
    skipped_insufficient: int
    errors: int

    def total(self) -> int:
        return (
            self.persisted
            + self.skipped_existing
            + self.skipped_unavailable
            + self.skipped_insufficient
            + self.errors
        )


def _iter_months(start: date_t, end: date_t) -> Iterator[tuple[int, int]]:
    """Yield ``(year, month)`` tuples from ``start`` to ``end`` inclusive."""
    if end < start:
        return
    y, m = start.year, start.month
    end_y, end_m = end.year, end.month
    while (y, m) <= (end_y, end_m):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


async def backfill_damodaran_monthly(
    session: Session,
    *,
    cache_dir: Path,
    start: date_t,
    end: date_t,
) -> DamodaranBackfillResult:
    """Backfill Damodaran monthly external-reference rows for ``[start, end]``.

    Args:
        session: SQLAlchemy session; the orchestrator commits at the end.
        cache_dir: Path for the connector disk cache (one subdir created
            for the Damodaran namespace under ``cache_dir / "damodaran"``).
        start: Earliest month to fetch; clamped forward to
            :data:`DAMODARAN_MONTHLY_START` when older.
        end: Latest month to fetch (typically ``today`` or earlier; the
            connector returns ``None`` for unpublished months).

    Returns:
        :class:`DamodaranBackfillResult` with per-month outcome counts.
    """
    if start < DAMODARAN_MONTHLY_START:
        log.warning(
            "damodaran.backfill.start_clamped",
            requested=start.isoformat(),
            clamped_to=DAMODARAN_MONTHLY_START.isoformat(),
        )
        start = DAMODARAN_MONTHLY_START

    cache_dir.mkdir(parents=True, exist_ok=True)
    connector = DamodaranConnector(cache_dir=str(cache_dir / "damodaran"))

    persisted = skipped_existing = skipped_unavailable = skipped_insufficient = errors = 0

    try:
        for year, month in _iter_months(start, end):
            target_date = date_t(year, month, 1)

            existing = (
                session.query(ERPExternalReferenceRow)
                .filter_by(
                    market_index="SPX",
                    country_code="US",
                    date=target_date,
                    source="damodaran_monthly",
                )
                .first()
            )
            if existing is not None:
                skipped_existing += 1
                continue

            try:
                damodaran_row = await connector.fetch_monthly_implied_erp(year, month)
            except (OverlayError, ValueError, OSError, httpx.HTTPError) as exc:
                log.warning(
                    "damodaran.backfill.fetch_error",
                    year=year,
                    month=month,
                    error=str(exc),
                )
                errors += 1
                continue

            if damodaran_row is None:
                log.info("damodaran.backfill.unavailable", year=year, month=month)
                skipped_unavailable += 1
                continue

            try:
                row = build_damodaran_external_row(
                    year=year,
                    month=month,
                    damodaran_row=damodaran_row,
                )
            except InsufficientDataError as exc:
                log.warning(
                    "damodaran.backfill.insufficient",
                    year=year,
                    month=month,
                    error=str(exc),
                )
                skipped_insufficient += 1
                continue
            except DataUnavailableError as exc:
                log.warning(
                    "damodaran.backfill.unavailable_build",
                    year=year,
                    month=month,
                    error=str(exc),
                )
                skipped_unavailable += 1
                continue

            session.add(row)
            persisted += 1
            log.info(
                "damodaran.backfill.persisted",
                year=year,
                month=month,
                erp_bps=row.erp_bps,
                source_file=row.source_file,
            )

        session.commit()
    finally:
        await connector.aclose()

    log.info(
        "damodaran.backfill.done",
        persisted=persisted,
        skipped_existing=skipped_existing,
        skipped_unavailable=skipped_unavailable,
        skipped_insufficient=skipped_insufficient,
        errors=errors,
    )

    return DamodaranBackfillResult(
        persisted=persisted,
        skipped_existing=skipped_existing,
        skipped_unavailable=skipped_unavailable,
        skipped_insufficient=skipped_insufficient,
        errors=errors,
    )
