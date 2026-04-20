"""FactSet Earnings Insight PDF scraper — weekly forward-earnings snapshot.

Endpoint pattern:

    https://advantage.factset.com/hubfs/Website/Resources%20Section/
    Research%20Desk/Earnings%20Insight/EarningsInsight_MMDDYY.pdf

FactSet publishes Earnings Insight on Friday of each week. The
``MMDDYY`` placeholder in the URL is the publication date in
US calendar order (zero-padded month + day + 2-digit year). We
resolve the URL for a given target date by walking back to the
most recent Friday.

Extracted fields (per spec docs/specs/overlays/erp-daily.md §2):

* forward 12-month EPS estimate (``forward_12m_eps``)
* forward P/E ratio (``forward_pe``)
* calendar-year estimates (``cy1_eps`` current year, ``cy2_eps`` next)
* analyst consensus 5-year EPS growth (``consensus_growth_5y``,
  decimal — 0.12 means 12 %/yr)

URL fragility: FactSet may change the hubfs path, slug, or filename
pattern at any time. Parser is pdfplumber-text based, keyed on
deterministic labels inside the PDF ("Forward 12-Month EPS:"). On
layout drift or HTTP failure raises :class:`DataUnavailableError`
— caller is expected to flag ``OVERLAY_MISS`` per spec §6.

Maintenance contract: if FactSet rotates either the URL template
or the label strings inside the PDF, update :data:`FACTSET_URL_TEMPLATE`
or the regexes in :func:`_parse_pdf_text` respectively. Cassette
fixtures for the happy path live under ``tests/fixtures/factset/``.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, cast

import httpx
import pdfplumber
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from sonar.connectors.cache import ConnectorCache
from sonar.overlays.exceptions import OverlayError

if TYPE_CHECKING:
    from pathlib import Path

log = structlog.get_logger()

FACTSET_URL_TEMPLATE: str = (
    "https://advantage.factset.com/hubfs/Website/Resources%20Section/"
    "Research%20Desk/Earnings%20Insight/EarningsInsight_{mmddyy}.pdf"
)
FACTSET_TTL_SECONDS: int = 7 * 24 * 3600  # weekly publication cadence


class DataUnavailableError(OverlayError):
    """Raised when the FactSet PDF cannot be fetched or parsed."""


@dataclass(frozen=True, slots=True)
class FactSetInsightSnapshot:
    """One weekly Earnings Insight publication."""

    publication_date: date
    forward_12m_eps: float
    forward_pe: float
    cy1_eps: float
    cy2_eps: float
    consensus_growth_5y: float  # decimal


_RE_FORWARD_12M_EPS = re.compile(r"Forward\s*12[\s\-]?Month\s*EPS[:\s]+\$?([0-9]+(?:\.[0-9]+)?)")
_RE_FORWARD_PE = re.compile(r"Forward\s*12[\s\-]?Month\s*P/E[:\s]+([0-9]+(?:\.[0-9]+)?)")
_RE_CY1_EPS = re.compile(r"CY\s*[12]\s*EPS[:\s]+\$?([0-9]+(?:\.[0-9]+)?)")
_RE_CY2_EPS = re.compile(r"CY\s*[23]\s*EPS[:\s]+\$?([0-9]+(?:\.[0-9]+)?)")
_RE_GROWTH_5Y = re.compile(r"5[\s\-]?Year\s*EPS\s*Growth[:\s]+([0-9]+(?:\.[0-9]+)?)%")


def _most_recent_friday(target: date) -> date:
    """Walk back to the Friday on or before ``target``.

    FactSet publishes Friday; if called mid-week we use last Friday's PDF.
    Monday's weekday is 0, Friday is 4.
    """
    shift = (target.weekday() - 4) % 7
    return target - timedelta(days=shift)


def _format_mmddyy(d: date) -> str:
    return d.strftime("%m%d%y")


class FactSetInsightConnector:
    """L0 connector for FactSet Earnings Insight weekly PDF.

    Disk-cached per publication date; tenacity retry for transient HTTP.
    """

    CACHE_NAMESPACE_RAW = "factset:insight:raw"
    CACHE_NAMESPACE_PARSED = "factset:insight:parsed"

    def __init__(self, cache_dir: str | Path, timeout: float = 60.0) -> None:
        self.cache = ConnectorCache(cache_dir)
        self.client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)

    def _url_for(self, publication_date: date) -> str:
        return FACTSET_URL_TEMPLATE.format(mmddyy=_format_mmddyy(publication_date))

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=2, max=30),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _download(self, url: str) -> bytes:
        r = await self.client.get(url)
        r.raise_for_status()
        return r.content

    async def fetch_latest_snapshot(self, target_date: date) -> FactSetInsightSnapshot:
        """Return the Earnings Insight snapshot published on or before ``target_date``.

        Raises :class:`DataUnavailableError` on HTTP failure or if the
        parser cannot locate the required fields in the PDF.
        """
        publication_date = _most_recent_friday(target_date)
        cache_key = f"{self.CACHE_NAMESPACE_PARSED}:{publication_date.isoformat()}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            log.debug("factset.cache_hit", publication_date=publication_date.isoformat())
            return cast("FactSetInsightSnapshot", cached)

        url = self._url_for(publication_date)
        try:
            body = await self._download(url)
        except httpx.HTTPError as exc:
            msg = f"FactSet PDF fetch failed for {publication_date}: {exc}"
            raise DataUnavailableError(msg) from exc

        snapshot = _parse_pdf_bytes(body, publication_date)
        self.cache.set(cache_key, snapshot, ttl=FACTSET_TTL_SECONDS)
        log.info(
            "factset.fetched",
            publication_date=publication_date.isoformat(),
            forward_12m_eps=snapshot.forward_12m_eps,
            forward_pe=snapshot.forward_pe,
        )
        return snapshot

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()


def _parse_pdf_bytes(body: bytes, publication_date: date) -> FactSetInsightSnapshot:
    """Open the PDF via pdfplumber and delegate to :func:`_parse_pdf_text`."""
    try:
        with pdfplumber.open(io.BytesIO(body)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as exc:
        msg = f"FactSet PDF parse failed (pdfplumber error): {exc}"
        raise DataUnavailableError(msg) from exc
    return _parse_pdf_text(text, publication_date)


def _parse_pdf_text(text: str, publication_date: date) -> FactSetInsightSnapshot:
    """Extract forward-earnings fields from extracted PDF text.

    Raises :class:`DataUnavailableError` with a diagnostic message when
    any required label is missing. All numeric fields are mandatory;
    partial snapshots are not emitted (ERP compute requires full set).
    """
    forward_12m = _extract_float(_RE_FORWARD_12M_EPS, text, "Forward 12-Month EPS")
    forward_pe = _extract_float(_RE_FORWARD_PE, text, "Forward 12-Month P/E")
    cy1 = _extract_float(_RE_CY1_EPS, text, "CY1 EPS")
    cy2 = _extract_float(_RE_CY2_EPS, text, "CY2 EPS")
    growth_pct = _extract_float(_RE_GROWTH_5Y, text, "5-Year EPS Growth")
    return FactSetInsightSnapshot(
        publication_date=publication_date,
        forward_12m_eps=forward_12m,
        forward_pe=forward_pe,
        cy1_eps=cy1,
        cy2_eps=cy2,
        consensus_growth_5y=growth_pct / 100.0,
    )


def _extract_float(regex: re.Pattern[str], text: str, label: str) -> float:
    m = regex.search(text)
    if m is None:
        msg = f"FactSet PDF missing label {label!r}"
        raise DataUnavailableError(msg)
    try:
        return float(m.group(1))
    except (TypeError, ValueError) as exc:
        msg = f"FactSet PDF value for {label!r} not a float: {m.group(1)!r}"
        raise DataUnavailableError(msg) from exc
