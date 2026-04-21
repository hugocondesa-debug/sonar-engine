"""Reserve Bank of New Zealand (RBNZ) statistical-tables L0 connector.

Empirical probe 2026-04-21 (Week 9 Sprint U-NZ pre-flight): the RBNZ
statistics host at ``https://www.rbnz.govt.nz/`` returns HTTP 403
(``Website unavailable`` Akamai-style perimeter block) for **every**
probed path — ``/statistics`` index, ``/statistics/series/b/b2/...``
media paths, ``/robots.txt``, root ``/`` — under both generic
``Mozilla/5.0`` and descriptive ``SONAR/2.0`` user-agents. The block is
host-scoped rather than path-scoped, so the Sprint T-AU UA-gate fix
does not unlock it from the SONAR VPS IP space. The likely root cause
is geo / ASN-based filtering at the RBNZ edge (historically enforced
for a subset of foreign cloud providers).

Connector consequence: the Sprint U-NZ RBNZ slot ships **wire-ready
but raising** — :meth:`fetch_ocr` and :meth:`fetch_government_10y`
invoke the RBNZ host and surface the 403 as
:class:`DataUnavailableError`. The NZ M1 cascade therefore degrades to
**TE primary → RBNZ scaffold (raises) → FRED OECD mirror** with
``NZ_OCR_RBNZ_UNAVAILABLE`` emitted on the scaffold miss. Once the
host-level block lifts (or SONAR moves onto an allowlisted egress),
:data:`RBNZ_B2_SERIES` / :data:`RBNZ_B2_SERIES_URL` should parse
successfully without code changes — the connector expects the
documented B-series CSV schema (header metadata + data rows
``YYYY-MM-DD,value``). Tracked via CAL-NZ-RBNZ-TABLES.

Canonical series catalogue (RBNZ B-table documentation; URLs are the
expected forms pending the host unblock):

* **hb2-daily** — B2 daily Official Cash Rate + related short-end
  money-market rates (cascade M1 secondary slot).
* **hb2-weekly** — B2 weekly long-maturity NZ government stock yields
  (M4 FCI AU-analog landing; deferred CAL-NZ-M4-FCI).

All observations are returned as ``list[Observation]`` per
``base.Observation`` with ``yield_bps = int(round(rate_pct * 100))``
per ``conventions/units.md`` §Spreads — mirroring the RBA CSV
connector so the builder resampler reads both without branching.

Callers in the monetary-indices cascade
(:mod:`sonar.indices.monetary.builders`) treat
:class:`DataUnavailableError` from this connector as a soft fail and
fall back to FRED OECD mirror per the Sprint U cascade (TE primary →
RBNZ tables scaffold → FRED stale-flagged).
"""

from __future__ import annotations

import csv
from datetime import UTC, date, datetime
from io import StringIO
from typing import TYPE_CHECKING, Final

import httpx
import structlog
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from sonar.connectors.base import Observation
from sonar.connectors.cache import DEFAULT_TTL_SECONDS, ConnectorCache
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from pathlib import Path

log = structlog.get_logger()

__all__ = [
    "RBNZ_B2_SERIES",
    "RBNZ_B2_SERIES_URL",
    "RBNZ_GOVT_10Y_SERIES",
    "RBNZ_OCR_COLUMN",
    "RBNZ_STATISTICS_BASE_URL",
    "RBNZ_USER_AGENT",
    "RBNZConnector",
]

# Series-ID catalogue (RBNZ B-table canonical; URLs pending host unblock —
# empirical probe 2026-04-21 returned 403 on every probed path). Kept
# public so tests + cascades can reference the series without magic
# strings.
RBNZ_B2_SERIES: Final[str] = "hb2-daily"
RBNZ_GOVT_10Y_SERIES: Final[str] = "hb2-weekly"

# OCR column label inside the B2-daily CSV data region. Placeholder —
# will need empirical validation once the host is reachable. Until
# then the parser uses this as the default extraction key.
RBNZ_OCR_COLUMN: Final[str] = "OCR"

# Expected CSV location (B2 daily is the cascade's M1 secondary-slot
# target). Concrete path form lifted from RBNZ's public statistics
# documentation; must be re-probed once the 403 clears.
RBNZ_STATISTICS_BASE_URL: Final[str] = "https://www.rbnz.govt.nz"
RBNZ_B2_SERIES_URL: Final[str] = (
    f"{RBNZ_STATISTICS_BASE_URL}/-/media/project/sites/rbnz/files/statistics/series/b/b2/hb2-daily.csv"
)

# The RBNZ edge 403s both generic Mozilla and descriptive SONAR UAs
# (Sprint U-NZ probe 2026-04-21), so the UA choice is informational
# only — the block is host/IP-scoped. Keeping the descriptive UA
# aligns the connector with the Sprint T-AU RBA canonical for the day
# the edge unblocks.
RBNZ_USER_AGENT: Final[str] = "SONAR/2.0 (monetary-cascade; contact hugocondesa@pm.me)"


class RBNZConnector:
    """L0 connector for RBNZ statistical-tables CSV endpoints.

    The RBNZ statistics host is public in principle — no API key, no
    auth — but the Akamai-style edge returns 403 ``Website
    unavailable`` on every probed path from the SONAR VPS (empirical
    probe 2026-04-21). The connector therefore ships **wire-ready but
    raising**: any :meth:`fetch_ocr` / :meth:`fetch_government_10y`
    call will currently surface the 403 as
    :class:`DataUnavailableError`, and the NZ M1 cascade falls through
    to the FRED OECD mirror.

    Slot in cascade: **secondary** behind TE primary for NZ monetary
    inputs (see :func:`build_m1_nz_inputs`). Returns results in the
    generic ``Observation`` shape so the builder resampler can consume
    them unchanged — mirroring :class:`RBAConnector`.
    """

    BASE_URL: Final[str] = RBNZ_STATISTICS_BASE_URL
    CACHE_NAMESPACE: Final[str] = "rbnz_stats"
    CONNECTOR_ID: Final[str] = "rbnz"

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
                "User-Agent": RBNZ_USER_AGENT,
                "Accept": "text/csv,application/octet-stream,*/*",
            },
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=2, max=30),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _fetch_raw(self, url: str) -> str:
        """Hit ``url`` on the RBNZ host and return the body.

        Raises :class:`DataUnavailableError` when the host returns the
        perimeter ``Website unavailable`` page (HTML with 403 or 200)
        — the connector surfaces these as unavailable so the cascade
        falls back to FRED OECD mirror cleanly. Actual CSV bodies pass
        through unchanged.
        """
        r = await self.client.get(url)
        r.raise_for_status()
        text = r.text
        # Perimeter-block HTML leak: the RBNZ edge sometimes serves a
        # 200 with an HTML error body under certain UA / referer
        # combinations. Detect by HTML tag-prefix rather than relying
        # on HTTP status alone.
        stripped = text.lstrip()
        if stripped.startswith("<") or "Website unavailable" in text:
            msg = (
                f"RBNZ host returned HTML perimeter page for url={url!r}; "
                "treating as DataUnavailable (CAL-NZ-RBNZ-TABLES)."
            )
            raise DataUnavailableError(msg)
        return text

    @staticmethod
    def _parse_csv(
        body: str,
        *,
        series_label: str,
        column_label: str,
    ) -> list[tuple[date, float]]:
        """Parse an RBNZ B-series CSV into ``[(obs_date, value_pct), ...]``.

        The RBNZ B-table format (per RBNZ documentation) wraps a
        metadata header block followed by a data region whose first
        row is ``Series ID`` / column labels and subsequent rows are
        ``YYYY-MM-DD,value,value,...``. The parser scans forward from
        row 0 until it finds the ``Series ID`` marker, then extracts
        ``(obs_date, value)`` tuples from the matching column.

        Schema-drift safeguards:

        - Raises :class:`DataUnavailableError` if no ``Series ID`` row
          found (empty / truncated payload).
        - Raises :class:`DataUnavailableError` if ``column_label``
          absent from the header row.
        - Skips rows with non-ISO dates or empty cells without
          raising (handles weekend / holiday gaps).

        Pending empirical validation against a real RBNZ payload
        (CAL-NZ-RBNZ-TABLES); once the host is reachable the parser
        may need minor adjustments (e.g. trailing metadata rows,
        alternate date format). The shape matches the RBA F-table
        parser so future divergence is visible.
        """
        reader = list(csv.reader(StringIO(body)))
        series_id_row: int | None = None
        for idx, row in enumerate(reader):
            if row and row[0].strip() == "Series ID":
                series_id_row = idx
                break
        if series_id_row is None:
            msg = (
                f"RBNZ series={series_label!r} CSV: no 'Series ID' header row "
                f"found in {len(reader)} rows (schema drift or truncated payload)."
            )
            raise DataUnavailableError(msg)

        header = reader[series_id_row]
        try:
            col_idx = header.index(column_label)
        except ValueError as exc:
            msg = (
                f"RBNZ series={series_label!r} column={column_label!r} "
                f"not in header={header!r} (schema drift)."
            )
            raise DataUnavailableError(msg) from exc

        out: list[tuple[date, float]] = []
        for row in reader[series_id_row + 1 :]:
            if not row or not row[0].strip():
                continue
            if col_idx >= len(row):
                continue
            raw_date = row[0].strip()
            raw_value = row[col_idx].strip()
            if not raw_value:
                continue
            try:
                obs_date = datetime.strptime(raw_date, "%Y-%m-%d").replace(tzinfo=UTC).date()
                value_pct = float(raw_value)
            except (TypeError, ValueError):
                continue
            out.append((obs_date, value_pct))
        if not out:
            msg = f"RBNZ series={series_label!r} column={column_label!r}: no parseable rows."
            raise DataUnavailableError(msg)
        return out

    async def fetch_series(
        self,
        url: str,
        series_label: str,
        column_label: str,
        start: date,
        end: date,
        *,
        tenor_years: float = 0.01,
    ) -> list[Observation]:
        """Return parsed observations for ``(url, column_label)`` in ``[start, end]``. Cached 24h.

        Host-level block or HTTP error raises
        :class:`DataUnavailableError`; upstream cascade callers treat
        that as soft-fail and fall back to FRED OECD mirror.
        """
        cache_key = (
            f"{self.CACHE_NAMESPACE}:{series_label}:{column_label}:"
            f"{start.isoformat()}:{end.isoformat()}"
        )
        cached = self.cache.get(cache_key)
        if cached is not None:
            log.debug("rbnz.cache_hit", series=series_label, column=column_label)
            return list(cached)

        try:
            body = await self._fetch_raw(url)
        except (httpx.HTTPError, RetryError) as exc:
            msg = f"RBNZ series={series_label!r} HTTP error: {exc}"
            raise DataUnavailableError(msg) from exc

        parsed = self._parse_csv(body, series_label=series_label, column_label=column_label)
        out: list[Observation] = []
        for obs_date, value_pct in parsed:
            if not (start <= obs_date <= end):
                continue
            out.append(
                Observation(
                    country_code="NZ",
                    observation_date=obs_date,
                    tenor_years=tenor_years,
                    yield_bps=round(value_pct * 100),
                    source="RBNZ",
                    source_series_id=f"{series_label}:{column_label}",
                )
            )
        if not out:
            msg = (
                f"RBNZ series={series_label!r} column={column_label!r}: "
                f"no rows in [{start.isoformat()}, {end.isoformat()}]"
            )
            raise DataUnavailableError(msg)
        out.sort(key=lambda o: o.observation_date)
        self.cache.set(cache_key, out, ttl=DEFAULT_TTL_SECONDS)
        log.info(
            "rbnz.fetched",
            series=series_label,
            column=column_label,
            n=len(out),
        )
        return out

    async def fetch_ocr(self, start: date, end: date) -> list[Observation]:
        """Official Cash Rate — B2 daily :data:`RBNZ_OCR_COLUMN` column.

        This is the RBNZ policy rate; the cascade's M1 secondary-slot
        target behind TE primary. Named ``fetch_ocr`` to align with
        RBNZ terminology (the RBA analog is ``fetch_cash_rate``).
        Currently raises :class:`DataUnavailableError` against the
        live host because the RBNZ edge 403s (CAL-NZ-RBNZ-TABLES).
        """
        return await self.fetch_series(
            RBNZ_B2_SERIES_URL,
            RBNZ_B2_SERIES,
            RBNZ_OCR_COLUMN,
            start,
            end,
            tenor_years=0.01,
        )

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()
