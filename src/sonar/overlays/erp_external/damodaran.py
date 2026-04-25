"""Damodaran monthly ERP external-reference writer (Sprint 3.1).

Consumes :class:`sonar.connectors.damodaran.DamodaranMonthlyERPRow` (one
start-of-month US S&P 500 implied ERP per fetch; ~2-month publication
lag at NYU Stern) and emits an :class:`ERPExternalReferenceRow` with
``source='damodaran_monthly'``.

Spec ``overlays/erp-daily.md`` §11 separation of concerns: the computed
``erp_canonical`` table stays untouched — this writer feeds the
adjacent ``erp_external_reference`` table only, used for editorial /
benchmarking purposes.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from sonar.db.models import ERPExternalReferenceRow
from sonar.overlays.exceptions import InsufficientDataError

if TYPE_CHECKING:
    from sonar.connectors.damodaran import DamodaranMonthlyERPRow

METHODOLOGY_VERSION = "DAMODARAN_MONTHLY_v0.1"
DEFAULT_CONFIDENCE = 0.95


def build_damodaran_external_row(
    *,
    year: int,
    month: int,
    damodaran_row: DamodaranMonthlyERPRow,
) -> ERPExternalReferenceRow:
    """Build an :class:`ERPExternalReferenceRow` from a Damodaran monthly snapshot.

    Args:
        year: Calendar year of the requested snapshot (sanity-checked
            against ``damodaran_row.start_of_month`` to flag mis-aligned fetches).
        month: Calendar month 1-12 (same sanity check).
        damodaran_row: Result from ``DamodaranConnector.fetch_monthly_implied_erp``.

    Returns:
        ``ERPExternalReferenceRow`` ready for ``session.merge`` /
        ``session.add``. Caller persists.

    Raises:
        InsufficientDataError: when ``implied_erp_decimal`` is NaN or
            non-positive, or when the row's ``start_of_month`` does not
            match the requested ``(year, month)``.
    """
    erp_decimal = damodaran_row.implied_erp_decimal
    if math.isnan(erp_decimal) or erp_decimal <= 0:
        msg = (
            f"Damodaran monthly row {year}-{month:02d}: "
            f"implied_erp_decimal invalid ({erp_decimal!r})"
        )
        raise InsufficientDataError(msg)

    snapshot_date = damodaran_row.start_of_month
    if snapshot_date.year != year or snapshot_date.month != month:
        msg = (
            f"Damodaran monthly row mis-aligned: requested {year}-{month:02d}, "
            f"got {snapshot_date.isoformat()}"
        )
        raise InsufficientDataError(msg)

    erp_bps = round(erp_decimal * 10_000)

    return ERPExternalReferenceRow(
        market_index="SPX",
        country_code="US",
        date=snapshot_date,
        source="damodaran_monthly",
        erp_bps=erp_bps,
        publication_date=None,
        source_file=damodaran_row.source_file,
        methodology_version=METHODOLOGY_VERSION,
        confidence=DEFAULT_CONFIDENCE,
        flags=None,
    )
