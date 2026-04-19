"""Shiller ie_data connector — Robert Shiller historical S&P 500 dataset.

Endpoint: ``http://www.econ.yale.edu/~shiller/data/ie_data.xls``
(Yale Department of Economics, public).

The file is a long-history monthly dataset (1871-present) with columns
including monthly S&P 500 level, dividend, earnings, CPI, GS10 (long
interest rate), CAPE (cyclically adjusted P/E), real S&P, real
dividends, real earnings, etc. Sheet name: ``Data``. Headers live on
row 8 (1-indexed). Data starts row 9.

Public-facing API:

- ``fetch_ie_data(observation_date)`` → ``ShillerSnapshot`` for the
  most recent monthly observation at or before ``observation_date``.

Network-policy notes (CLAUDE.md §7): cache-first; live download only
when cache miss + explicit caller flag. URL is stable but we treat it
as a Phase 1 best-effort source and add a graceful failure path.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from sonar.connectors.cache import ConnectorCache

if TYPE_CHECKING:
    from datetime import date as date_type
    from pathlib import Path

log = structlog.get_logger()

SHILLER_IE_DATA_URL: str = "http://www.econ.yale.edu/~shiller/data/ie_data.xls"
# 30 days TTL — Shiller refreshes monthly; cache survives intra-month re-runs.
SHILLER_TTL_SECONDS: int = 30 * 24 * 3600

# Column names in the published file (vary slightly between releases — we
# read by position in tolerant_parse if header lookup fails).
COL_DATE = "Date"
COL_PRICE = "P"  # Nominal S&P 500
COL_DIVIDEND = "D"
COL_EARNINGS = "E"
COL_CPI = "CPI"
COL_LONG_RATE = "Rate GS10"
COL_REAL_PRICE = "Real Price"
COL_REAL_DIVIDEND = "Real Dividend"
COL_REAL_EARNINGS = "Real Earnings"
COL_CAPE = "CAPE"


@dataclass(frozen=True, slots=True)
class ShillerSnapshot:
    """Single-month snapshot of the Shiller ie_data series."""

    observation_date: date_type
    price_nominal: float
    dividend_nominal: float
    earnings_nominal: float
    cpi: float
    long_rate_pct: float
    real_price: float
    real_earnings_10y_avg: float
    cape_ratio: float


class ShillerConnector:
    """L0 connector for Shiller ie_data.xls (monthly S&P 500 dataset)."""

    BASE_URL = SHILLER_IE_DATA_URL
    CACHE_NAMESPACE = "shiller:ie_data"

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

    async def fetch_raw_xls(self) -> bytes:
        """Return the raw xls bytes (cached for ``SHILLER_TTL_SECONDS``)."""
        cached = self.cache.get(self.CACHE_NAMESPACE)
        if cached is not None:
            log.debug("shiller.cache_hit")
            return cast("bytes", cached)
        body = await self._download()
        self.cache.set(self.CACHE_NAMESPACE, body, ttl=SHILLER_TTL_SECONDS)
        log.info("shiller.fetched", bytes=len(body))
        return body

    async def fetch_snapshot(self, observation_date: date_type) -> ShillerSnapshot:
        """Parse the most recent monthly row at-or-before ``observation_date``."""
        body = await self.fetch_raw_xls()
        return _parse_snapshot(body, observation_date)

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()


def _parse_snapshot(body: bytes, observation_date: date_type) -> ShillerSnapshot:
    """Parse Shiller ie_data.xls into a ShillerSnapshot for the target month.

    Tolerant of header-row drift across releases by selecting columns via
    pandas ``DataFrame.columns`` lookup with fallback to positional index.
    """
    import pandas as pd

    df = pd.read_excel(
        io.BytesIO(body),
        sheet_name="Data",
        header=7,  # 0-indexed; spec says headers on row 8 → header=7
        engine="openpyxl" if body[:2] == b"PK" else None,
    )
    df = df.dropna(subset=[COL_DATE])

    # Shiller dates are floats like 2024.01 = Jan 2024. Convert to year/month.
    target_year_month = observation_date.year * 100 + observation_date.month
    candidates: list[tuple[int, int, int]] = []  # (year_month, idx, raw_year)
    for idx, raw in enumerate(df[COL_DATE].tolist()):
        try:
            f = float(raw)
        except (TypeError, ValueError):
            continue
        year = int(f)
        month = int(round((f - year) * 100))
        if month < 1 or month > 12:
            continue
        candidates.append((year * 100 + month, idx, year))

    candidates = [c for c in candidates if c[0] <= target_year_month]
    if not candidates:
        msg = f"Shiller ie_data has no rows at or before {observation_date.isoformat()}"
        raise ValueError(msg)
    _ym, idx, _ = max(candidates, key=lambda c: c[0])
    row = df.iloc[idx]
    year, month = _ym // 100, _ym % 100

    from datetime import date as _date

    return ShillerSnapshot(
        observation_date=_date(year, month, 1),
        price_nominal=float(row[COL_PRICE]),
        dividend_nominal=float(row[COL_DIVIDEND]),
        earnings_nominal=float(row[COL_EARNINGS]),
        cpi=float(row[COL_CPI]),
        long_rate_pct=float(row[COL_LONG_RATE]),
        real_price=float(row[COL_REAL_PRICE]),
        real_earnings_10y_avg=float(row[COL_REAL_EARNINGS]),
        cape_ratio=float(row[COL_CAPE]),
    )
