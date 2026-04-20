"""Damodaran Historical Implied ERP connector — xval reference.

Endpoint: ``https://pages.stern.nyu.edu/~adamodar/pc/datasets/histimpl.xlsx``

Content structure (per 2024 snapshot): workbook with sheet
``Historical Impl Premiums`` containing annual rows 1960-present.
Columns include ``Year``, ``Earnings Yield``, ``Dividend Yield``,
``S&P 500``, ``Earnings*``, ``Implied Premium (FCFE with sustainable
Payout)``, etc.

Spec §4 step 8 mentions "date.month" for xval — Damodaran's public
historical file is **annual**. Week 3.5B xval consumer therefore
matches on ``date.year``. Monthly Damodaran updates live in separate
files not included in this Phase 1 scope; flagged as spec-vs-reality
deviation in the implementation report.

Week 3.5B scope: ``fetch_annual_erp(year)`` → decimal Implied ERP.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import httpx
import openpyxl
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from sonar.connectors.cache import ConnectorCache

if TYPE_CHECKING:
    from pathlib import Path

log = structlog.get_logger()

HISTIMPL_URL: str = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/histimpl.xlsx"
# Refresh quarterly (Damodaran republishes annually but timestamp drifts).
HISTIMPL_TTL_SECONDS: int = 90 * 24 * 3600

# Column name (canonical per 2024 snapshot; parser reads by name not index).
COL_YEAR = "Year"
COL_IMPLIED_FCFE_SUSTAINABLE = "Implied Premium (FCFE with sustainable Payout)"
COL_IMPLIED_FCFE = "Implied ERP (FCFE)"
COL_SHEET = "Historical Impl Premiums"


@dataclass(frozen=True, slots=True)
class DamodaranERPRow:
    """Annual implied ERP snapshot from Damodaran histimpl.xlsx."""

    year: int
    implied_erp_decimal: float
    source_column: str  # which column was used (we fall back on FCFE if sustainable missing)


class DamodaranConnector:
    """L0 connector for Damodaran histimpl.xlsx."""

    BASE_URL = HISTIMPL_URL
    CACHE_NAMESPACE = "damodaran:histimpl"

    def __init__(self, cache_dir: str | Path, timeout: float = 60.0) -> None:
        self.cache = ConnectorCache(cache_dir)
        self.client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=2, max=30),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _download(self) -> bytes:
        r = await self.client.get(self.BASE_URL)
        r.raise_for_status()
        return r.content

    async def fetch_raw_xlsx(self) -> bytes:
        cached = self.cache.get(self.CACHE_NAMESPACE)
        if cached is not None:
            log.debug("damodaran.cache_hit")
            return cast("bytes", cached)
        body = await self._download()
        self.cache.set(self.CACHE_NAMESPACE, body, ttl=HISTIMPL_TTL_SECONDS)
        log.info("damodaran.fetched", bytes=len(body))
        return body

    async def fetch_annual_erp(self, year: int) -> DamodaranERPRow | None:
        """Return the annual implied ERP row for ``year``, or ``None``.

        Prefers the FCFE-with-sustainable-payout column (spec §4 primary
        convention); falls back to the plain FCFE column. Returns
        ``None`` when the year is absent from the file.
        """
        body = await self.fetch_raw_xlsx()
        return _parse_year(body, year)

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()


def _parse_year(body: bytes, year: int) -> DamodaranERPRow | None:
    wb = openpyxl.load_workbook(io.BytesIO(body), read_only=True, data_only=True)
    ws = wb[COL_SHEET]
    rows = list(ws.iter_rows(values_only=True))
    # Find the header row (contains "Year" in column 0).
    header_idx: int | None = None
    for i, row in enumerate(rows):
        if row and row[0] == COL_YEAR:
            header_idx = i
            break
    if header_idx is None:
        return None
    header = list(rows[header_idx])
    try:
        col_sust = header.index(COL_IMPLIED_FCFE_SUSTAINABLE)
    except ValueError:
        col_sust = -1
    try:
        col_fcfe = header.index(COL_IMPLIED_FCFE)
    except ValueError:
        col_fcfe = -1

    for row in rows[header_idx + 1 :]:
        if not row or row[0] != year:
            continue
        # Prefer sustainable payout column; fall back to FCFE.
        if col_sust >= 0 and col_sust < len(row) and row[col_sust] is not None:
            return DamodaranERPRow(
                year=year,
                implied_erp_decimal=float(row[col_sust]),
                source_column=COL_IMPLIED_FCFE_SUSTAINABLE,
            )
        if col_fcfe >= 0 and col_fcfe < len(row) and row[col_fcfe] is not None:
            return DamodaranERPRow(
                year=year,
                implied_erp_decimal=float(row[col_fcfe]),
                source_column=COL_IMPLIED_FCFE,
            )
        return None
    return None
