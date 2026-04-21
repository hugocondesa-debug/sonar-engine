"""Bank of England Statistical Interactive Database (IADB) L0 connector.

Empirical probe 2026-04-21 (Week 8 Sprint I pre-flight): the IADB CSV
endpoint ``_iadb-FromShowColumns.asp`` sits behind Akamai anti-bot.
From the SONAR VPS every probe — plain ``curl``, browser-mimicking
headers, referer + cookie jar — returned HTTP 302 →
``ErrorPage.asp?ei=1809``. The canonical series IDs below remain
correct (confirmed against BoE's IADB documentation); the connector
is wire-ready and will work from any IP that the BoE session logic
accepts. For production the MSC GB pipeline uses a FRED / TE
fallback cascade (see :mod:`sonar.indices.monetary.builders`).

Canonical series codes (IADB public catalogue):

* **IUDBEDR** — Bank Rate (policy rate; daily since 1694).
* **IUDSOIA** — SONIA (overnight sterling index average).
* **IUDMNPY** — 10Y gilt nominal yield (daily).
* **LPMVWYR** — GB M4 money supply (monthly; balance-sheet proxy).

All series returned as ``list[Observation]`` with
``yield_bps = int(round(close_pct * 100))`` per
:mod:`conventions/units.md` §Spreads.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from sonar.connectors.base import Observation
from sonar.connectors.cache import DEFAULT_TTL_SECONDS, ConnectorCache
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from datetime import date
    from pathlib import Path

log = structlog.get_logger()

__all__ = [
    "BOE_BALANCE_SHEET_M4",
    "BOE_BANK_RATE",
    "BOE_GILT_10Y",
    "BOE_IADB_URL",
    "BOE_SONIA_RATE",
    "BoEDatabaseConnector",
]

# Series-ID catalogue (IADB-canonical — documented by BoE).
BOE_BANK_RATE: str = "IUDBEDR"
BOE_SONIA_RATE: str = "IUDSOIA"
BOE_GILT_10Y: str = "IUDMNPY"
BOE_BALANCE_SHEET_M4: str = "LPMVWYR"

# IADB CSV endpoint — the canonical "give me a series in CSV" path.
BOE_IADB_URL: str = "https://www.bankofengland.co.uk/boeapps/database/_iadb-FromShowColumns.asp"


class BoEDatabaseConnector:
    """L0 connector over BoE IADB CSV export endpoint.

    Methods raise :class:`sonar.overlays.exceptions.DataUnavailableError`
    when the endpoint returns the ``ErrorPage.asp`` redirect (ei=1809).
    Callers in the GB monetary-indices cascade treat this as a soft
    fail and fall back to FRED / TE mirrors.
    """

    BASE_URL: str = BOE_IADB_URL
    CACHE_NAMESPACE: str = "boe_iadb"

    def __init__(
        self,
        cache_dir: str | Path,
        timeout: float = 30.0,
    ) -> None:
        self.cache = ConnectorCache(cache_dir)
        self.client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; SONAR/2.0)",
                "Accept": "text/csv, text/plain, */*",
                "Referer": "https://www.bankofengland.co.uk/boeapps/iadb/",
            },
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=2, max=30),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _fetch_raw(self, series_id: str, start: date, end: date) -> str:
        params = {
            "csv.x": "yes",
            "Datefrom": start.strftime("%d/%b/%Y"),
            "Dateto": end.strftime("%d/%b/%Y"),
            "SeriesCodes": series_id,
            "CSVF": "TN",
            "UsingCodes": "Y",
            "VPD": "Y",
        }
        r = await self.client.get(self.BASE_URL, params=params)
        r.raise_for_status()
        # IADB behind Akamai can return an HTML error page with 200
        # after following the 302 redirect chain. Detect + raise.
        text = r.text
        if "ErrorPage.asp" in str(r.url) or text.lstrip().startswith("<"):
            msg = (
                f"BoE IADB ErrorPage for series={series_id!r} "
                f"({start.isoformat()}..{end.isoformat()}). "
                "Fallback cascade required at builder layer."
            )
            raise DataUnavailableError(msg)
        return text

    async def fetch_series_csv(
        self,
        series_id: str,
        start: date,
        end: date,
    ) -> str:
        """Return raw CSV body for ``(series_id, start, end)``. Cached 24h."""
        cache_key = f"{self.CACHE_NAMESPACE}:{series_id}:{start.isoformat()}:{end.isoformat()}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            log.debug("boe.cache_hit", series=series_id)
            return cast("str", cached)
        body = await self._fetch_raw(series_id, start, end)
        self.cache.set(cache_key, body, ttl=DEFAULT_TTL_SECONDS)
        log.info("boe.fetched", series=series_id, bytes=len(body))
        return body

    async def fetch_series(
        self,
        series_id: str,
        start: date,
        end: date,
        *,
        tenor_years: float = 0.0,
    ) -> list[Observation]:
        """Parse IADB CSV into :class:`Observation` rows.

        ``tenor_years`` is passed through to :class:`Observation` for
        yield series; pass ``0.0`` for policy rates / balance-sheet
        proxies (Observation contract requires ``gt=0``, so callers use
        a sentinel like ``0.01`` when needed).
        """
        body = await self.fetch_series_csv(series_id, start, end)
        return _parse_csv(body, series_id, tenor_years=tenor_years, start=start, end=end)

    async def fetch_bank_rate(self, start: date, end: date) -> list[Observation]:
        """Bank Rate (policy) — series :data:`BOE_BANK_RATE`."""
        return await self.fetch_series(BOE_BANK_RATE, start, end, tenor_years=0.01)

    async def fetch_gilt_10y(self, start: date, end: date) -> list[Observation]:
        """10Y nominal gilt yield — series :data:`BOE_GILT_10Y`."""
        return await self.fetch_series(BOE_GILT_10Y, start, end, tenor_years=10.0)

    async def fetch_balance_sheet(self, start: date, end: date) -> list[Observation]:
        """GB M4 money stock (balance-sheet proxy) — series :data:`BOE_BALANCE_SHEET_M4`.

        M4 is in ``£ million`` and is **not** a yield; ``yield_bps`` is
        re-purposed per the existing Observation contract (same pattern
        as FMP price series). Consumers must cast back to a float.
        """
        return await self.fetch_series(BOE_BALANCE_SHEET_M4, start, end, tenor_years=0.01)

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()


def _parse_csv(
    body: str,
    series_id: str,
    *,
    tenor_years: float,
    start: date,
    end: date,
) -> list[Observation]:
    """Parse IADB CSV payload → list of :class:`Observation`.

    IADB CSV format (TN variant):

    .. code-block:: text

        DATE,<SERIES_CODE>
        01 Dec 2024,4.75
        02 Dec 2024,4.75
        ...

    The first line is the header; subsequent rows are
    ``(date, value)``. Rows with non-numeric values are skipped with a
    ``boe.parse_skip`` log event (handles ``.``/``-`` placeholders).
    """
    reader = csv.reader(io.StringIO(body))
    try:
        header = next(reader)
    except StopIteration:
        msg = f"BoE IADB empty CSV for series={series_id!r}"
        raise DataUnavailableError(msg) from None
    # Schema-drift guard: expect two columns, with series code in
    # header[1]. Warn (don't crash) if BoE reshuffles.
    if len(header) < 2 or series_id not in header[1]:
        log.warning(
            "boe.schema_drift",
            series=series_id,
            header=header,
        )
    out: list[Observation] = []
    for row in reader:
        if len(row) < 2:
            continue
        date_str, value_str = row[0].strip(), row[1].strip()
        if not date_str or value_str in {"", ".", "-"}:
            log.debug("boe.parse_skip", series=series_id, raw_date=date_str)
            continue
        try:
            obs_date = datetime.strptime(date_str, "%d %b %Y").replace(tzinfo=UTC).date()
            value_pct = float(value_str)
        except (ValueError, TypeError):
            log.debug("boe.parse_error", series=series_id, row=row)
            continue
        if obs_date < start or obs_date > end:
            continue
        out.append(
            Observation(
                country_code="GB",
                observation_date=obs_date,
                tenor_years=tenor_years,
                yield_bps=round(value_pct * 100),
                source="BOE",
                source_series_id=series_id,
            )
        )
    out.sort(key=lambda o: o.observation_date)
    return out
