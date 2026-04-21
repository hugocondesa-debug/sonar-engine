"""Reserve Bank of Australia (RBA) statistical-tables L0 connector.

Empirical probe 2026-04-21 (Week 9 Sprint T pre-flight): the RBA
statistical-tables CSV endpoints at ``https://www.rba.gov.au/statistics/
tables/csv/`` are served via Akamai with a light bot-detection gate —
generic ``Mozilla/5.0`` requests are rejected 403, but a descriptive
project user-agent (``SONAR/2.0 (monetary-cascade; ...)``) passes. This
is the first native connector in the monetary-cascade family to consume
**public static CSVs** rather than a JSON REST API (BoC Valet) or a
gated portal (BoE IADB / BoJ TSD).

Canonical series codes (RBA F-table catalogue; all observed live during
the Sprint T probe):

* **FIRMMCRTD** — F1 Cash Rate Target (daily, since 2011-01-04). This
  is the cascade's M1 input; RBA publishes the target cash rate as of
  the observation date with forward-fill between announcements (weekends
  + pre-announcement days carry the prior level).
* **FCMYGBAG10D** — F2 Australian Government 10-year bond yield
  (daily, since 2013-05-20). Landing point for M4 FCI AU 10Y input
  (CAL-AU-M4-FCI — deferred Sprint T).

The F-table schema is consistent across F1/F2:

* Rows 1-10: metadata (Title / Description / Frequency / Type / Units /
  Source / Publication-date; row 7-8 blank).
* Row 11: ``Series ID`` row — column 1 is the literal string
  ``"Series ID"`` and columns 2..N carry the canonical series IDs
  (e.g. ``FIRMMCRTD`` for F1 col 2, ``FCMYGBAG10D`` for F2 col 5).
* Row 12..: ``DD-Mon-YYYY,val,val,...`` data rows (ISO three-letter
  month abbreviation; Excel-style). Empty cells indicate the series
  is not yet populated on that date — we skip those rows (match BoC
  null-value handling).

All observations are returned as ``list[Observation]`` per
``base.Observation`` with ``yield_bps = int(round(rate_pct * 100))``
per ``conventions/units.md`` §Spreads.

Callers in the monetary-indices cascade
(:mod:`sonar.indices.monetary.builders`) treat
:class:`DataUnavailableError` from this connector as a soft fail and
fall back to FRED OECD mirror per the Sprint T cascade (TE primary →
RBA CSV native → FRED stale-flagged).
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
    "RBA_CASH_RATE_TARGET",
    "RBA_F1_TABLE_ID",
    "RBA_F2_TABLE_ID",
    "RBA_GOVERNMENT_10Y",
    "RBA_STATISTICS_BASE_URL",
    "RBA_USER_AGENT",
    "RBAConnector",
]

# Series-ID catalogue (RBA F-table canonical; validated empirically
# during Sprint T pre-flight, 2026-04-21). Kept public so tests +
# cascades can reference the series without magic strings.
RBA_CASH_RATE_TARGET: Final[str] = "FIRMMCRTD"
RBA_GOVERNMENT_10Y: Final[str] = "FCMYGBAG10D"

# F-table slugs on the RBA statistics host.
RBA_F1_TABLE_ID: Final[str] = "f1"
RBA_F2_TABLE_ID: Final[str] = "f2"

RBA_STATISTICS_BASE_URL: Final[str] = "https://www.rba.gov.au/statistics/tables/csv"

# Akamai edge at rba.gov.au rejects bare ``Mozilla/5.0`` + accepts
# descriptive UAs. Sprint T probe (2026-04-21) confirmed this one
# serves 200 on both F1 and F2.
RBA_USER_AGENT: Final[str] = "SONAR/2.0 (monetary-cascade; contact hugocondesa@pm.me)"

# Row of the Series-ID header in RBA F-table CSVs (1-indexed). Anything
# before this is human-readable metadata (Title/Description/Frequency/
# Type/Units/Source/Publication date).
_SERIES_ID_ROW_INDEX: Final[int] = 10  # 0-indexed row 10 == 1-indexed row 11


class RBAConnector:
    """L0 connector for RBA statistical-tables CSV endpoints.

    The statistics host is public — no API key, no auth — but the
    Akamai edge does a light bot screen. We pass a descriptive UA
    (:data:`RBA_USER_AGENT`) to clear it.

    Slot in cascade: **secondary** behind TE primary for AU monetary
    inputs (see :func:`build_m1_au_inputs`). Returns results in the
    generic ``Observation`` shape so the builder resampler can consume
    them unchanged.
    """

    BASE_URL: Final[str] = RBA_STATISTICS_BASE_URL
    CACHE_NAMESPACE: Final[str] = "rba_stats"
    CONNECTOR_ID: Final[str] = "rba"

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
                "User-Agent": RBA_USER_AGENT,
                "Accept": "text/csv,application/octet-stream,*/*",
            },
        )

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=30),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _fetch_raw(self, table_id: str) -> str:
        """Hit ``/statistics/tables/csv/{table_id}-data.csv`` and return the body."""
        url = f"{self.BASE_URL}/{table_id}-data.csv"
        r = await self.client.get(url)
        r.raise_for_status()
        # RBA F-tables are served with a UTF-8 BOM on the first row —
        # ``response.text`` handles the decode; the parser skips metadata
        # rows so the BOM in the title line is inert.
        return r.text

    @staticmethod
    def _parse_csv(
        body: str,
        *,
        series_id: str,
        table_id: str,
    ) -> list[tuple[date, float]]:
        """Parse an RBA F-table CSV string into ``[(obs_date, value_pct), ...]``.

        Locates ``series_id`` within the Series-ID header row (0-indexed
        row 10), then extracts ``DD-Mon-YYYY,value`` tuples from the
        data region (rows 11+). Empty cells are skipped per the RBA
        convention for not-yet-populated observations.

        Raises :class:`DataUnavailableError` when the series is not
        listed in the header (catches typo + schema drift) or when no
        parseable rows survive.
        """
        reader = list(csv.reader(StringIO(body)))
        if len(reader) <= _SERIES_ID_ROW_INDEX:
            msg = f"RBA table={table_id!r} CSV too short: {len(reader)} rows"
            raise DataUnavailableError(msg)
        header = reader[_SERIES_ID_ROW_INDEX]
        if not header or header[0].strip() != "Series ID":
            msg = (
                f"RBA table={table_id!r} Series-ID row not at expected "
                f"position (row {_SERIES_ID_ROW_INDEX + 1})"
            )
            raise DataUnavailableError(msg)
        try:
            col_idx = header.index(series_id)
        except ValueError as exc:
            msg = f"RBA table={table_id!r} series_id={series_id!r} not in header"
            raise DataUnavailableError(msg) from exc

        out: list[tuple[date, float]] = []
        for row in reader[_SERIES_ID_ROW_INDEX + 1 :]:
            if not row or not row[0].strip():
                continue
            if col_idx >= len(row):
                continue
            raw_date = row[0].strip()
            raw_value = row[col_idx].strip()
            if not raw_value:
                continue
            try:
                obs_date = datetime.strptime(raw_date, "%d-%b-%Y").replace(tzinfo=UTC).date()
                value_pct = float(raw_value)
            except (TypeError, ValueError):
                continue
            out.append((obs_date, value_pct))
        if not out:
            msg = f"RBA table={table_id!r} series_id={series_id!r}: no parseable rows"
            raise DataUnavailableError(msg)
        return out

    async def fetch_series(
        self,
        table_id: str,
        series_id: str,
        start: date,
        end: date,
    ) -> list[Observation]:
        """Return parsed observations for ``(table_id, series_id)`` in ``[start, end]``. Cached 24h.

        Empty column or HTTP error raises :class:`DataUnavailableError`;
        upstream cascade callers treat that as soft-fail and fall back
        to FRED OECD mirror.
        """
        cache_key = (
            f"{self.CACHE_NAMESPACE}:{table_id}:{series_id}:{start.isoformat()}:{end.isoformat()}"
        )
        cached = self.cache.get(cache_key)
        if cached is not None:
            log.debug("rba.cache_hit", table=table_id, series=series_id)
            return list(cached)

        try:
            body = await self._fetch_raw(table_id)
        except (httpx.HTTPError, RetryError) as exc:
            msg = f"RBA table={table_id!r} HTTP error: {exc}"
            raise DataUnavailableError(msg) from exc

        parsed = self._parse_csv(body, series_id=series_id, table_id=table_id)
        out: list[Observation] = []
        for obs_date, value_pct in parsed:
            if not (start <= obs_date <= end):
                continue
            out.append(
                Observation(
                    country_code="AU",
                    observation_date=obs_date,
                    tenor_years=0.01,
                    yield_bps=round(value_pct * 100),
                    source="RBA",
                    source_series_id=series_id,
                )
            )
        if not out:
            msg = (
                f"RBA table={table_id!r} series={series_id!r}: no rows in "
                f"[{start.isoformat()}, {end.isoformat()}]"
            )
            raise DataUnavailableError(msg)
        out.sort(key=lambda o: o.observation_date)
        self.cache.set(cache_key, out, ttl=DEFAULT_TTL_SECONDS)
        log.info("rba.fetched", table=table_id, series=series_id, n=len(out))
        return out

    async def fetch_cash_rate(self, start: date, end: date) -> list[Observation]:
        """Cash Rate Target — F1 series :data:`RBA_CASH_RATE_TARGET`.

        This is the RBA policy rate; ``FIRMMCRTD`` is the canonical
        daily series the monetary cascade consumes. Named
        ``fetch_cash_rate`` to stay consistent with the GB/JP/CA cascade
        vocabulary (the M1 cascade slot is the same regardless of
        country; AU uses "cash rate" terminology rather than "bank
        rate", reflecting RBA lexicon).
        """
        return await self.fetch_series(RBA_F1_TABLE_ID, RBA_CASH_RATE_TARGET, start, end)

    async def fetch_government_10y(self, start: date, end: date) -> list[Observation]:
        """10Y Australian Government bond yield — F2 series :data:`RBA_GOVERNMENT_10Y`.

        AGB 10Y benchmark (interpolated, daily). Landing point for M4
        FCI AU 10Y input and any future AU rating-spread anchoring.
        """
        obs = await self.fetch_series(RBA_F2_TABLE_ID, RBA_GOVERNMENT_10Y, start, end)
        # Override tenor for the 10Y wrapper so downstream resamplers pick
        # up the canonical 10.0 years rather than the 0.01 default set by
        # ``fetch_series`` (which targets overnight / short-rate usage).
        return [o.model_copy(update={"tenor_years": 10.0}) for o in obs]

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()
