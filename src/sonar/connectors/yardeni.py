"""Yardeni Earnings Squiggles PDF scraper — secondary forward-earnings source.

Dr. Ed Yardeni publishes weekly "Earnings Squiggles" reports
containing analyst consensus EPS forecasts for current and next
calendar year plus a time-weighted forward estimate. Used by the
ERP overlay as the secondary forward-earnings source (FactSet is
primary) for the ``ERP_SOURCE_DIVERGENCE`` cross-validation flag
defined in docs/specs/overlays/erp-daily.md §4 step 8.5.

**Consent & licensing (P2-028)**: Yardeni Research requires explicit
consent for automated scraping of the Squiggles PDF. This connector
assumes consent has been granted; the canonical consent artifact
lives at ``docs/governance/licensing/yardeni-consent-YYYY-MM-DD.md``
(pending). If consent lapses or is revoked, disable this connector
by leaving :envvar:`YARDENI_PDF_URL` unset — the connector then
raises :class:`DataUnavailableError` on every call and the ERP
overlay gracefully degrades to FactSet-only.

URL fragility: Yardeni rotates the Squiggles PDF URL roughly weekly
(the filename typically embeds a publication date). The exact
pattern is not published. This connector accepts the full URL via
:envvar:`YARDENI_PDF_URL` (or the ``pdf_url`` constructor argument)
so operators can rotate it without a code change. See
:data:`YARDENI_PDF_URL_ENVVAR` for the env-var contract.

Extracted fields (per spec §2):

* current-calendar-year EPS forecast (``current_year_eps``)
* next-calendar-year EPS forecast (``next_year_eps``)
* time-weighted forward EPS per the Squiggles methodology
  (``time_weighted_forward_eps``) — linear interpolation between
  current and next year weighted by fraction of year elapsed.

Maintenance contract: if Yardeni PDF layout drifts, update
:func:`_parse_pdf_bytes` regexes. On parse or HTTP failure raises
:class:`DataUnavailableError`; caller is expected to flag
``OVERLAY_MISS`` per spec §6.
"""

from __future__ import annotations

import io
import os
import re
from dataclasses import dataclass
from datetime import date, datetime
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

YARDENI_PDF_URL_ENVVAR: str = "YARDENI_PDF_URL"
YARDENI_TTL_SECONDS: int = 7 * 24 * 3600  # weekly publication cadence


class DataUnavailableError(OverlayError):
    """Raised when the Yardeni PDF cannot be fetched or parsed."""


@dataclass(frozen=True, slots=True)
class YardeniEarningsSquigglesSnapshot:
    """One weekly Earnings Squiggles publication."""

    publication_date: date
    current_year_eps: float
    next_year_eps: float
    time_weighted_forward_eps: float


_RE_CURRENT_YEAR_EPS = re.compile(
    r"(?:Current[\s\-]?Year|CY\s*1)[^\n\d]*?\$?([0-9]+(?:\.[0-9]+)?)",
    re.IGNORECASE,
)
_RE_NEXT_YEAR_EPS = re.compile(
    r"(?:Next[\s\-]?Year|CY\s*2)[^\n\d]*?\$?([0-9]+(?:\.[0-9]+)?)",
    re.IGNORECASE,
)
_RE_TIME_WEIGHTED_FWD = re.compile(
    r"Time[\s\-]?Weighted[^\n\d]*?\$?([0-9]+(?:\.[0-9]+)?)",
    re.IGNORECASE,
)
_RE_PUBLICATION_DATE = re.compile(
    r"(?:Published|Publication)\s*(?:Date)?[:\s]+([A-Za-z]+\s+[0-9]{1,2},?\s+[0-9]{4})",
    re.IGNORECASE,
)


class YardeniConnector:
    """L0 connector for Yardeni Earnings Squiggles weekly PDF."""

    CACHE_NAMESPACE_PARSED = "yardeni:squiggles:parsed"

    def __init__(
        self,
        cache_dir: str | Path,
        pdf_url: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        """Construct the connector.

        ``pdf_url`` overrides the :envvar:`YARDENI_PDF_URL` env var.
        When neither is set, every call raises :class:`DataUnavailableError`
        — treat as a graceful stub.
        """
        self.cache = ConnectorCache(cache_dir)
        self.client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)
        self._pdf_url = pdf_url or os.environ.get(YARDENI_PDF_URL_ENVVAR)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=2, max=30),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _download(self, url: str) -> bytes:
        r = await self.client.get(url)
        r.raise_for_status()
        return r.content

    async def fetch_latest_snapshot(
        self, fallback_publication_date: date | None = None
    ) -> YardeniEarningsSquigglesSnapshot:
        """Download the configured Squiggles PDF and parse it.

        ``fallback_publication_date`` is used when the PDF text does
        not contain a machine-readable date header. Raises
        :class:`DataUnavailableError` on missing URL, HTTP failure,
        or parse failure.
        """
        if not self._pdf_url:
            msg = (
                "Yardeni connector has no PDF URL configured — set "
                f"{YARDENI_PDF_URL_ENVVAR} env var or pass pdf_url to constructor"
            )
            raise DataUnavailableError(msg)

        cache_key = f"{self.CACHE_NAMESPACE_PARSED}:{self._pdf_url}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            log.debug("yardeni.cache_hit")
            return cast("YardeniEarningsSquigglesSnapshot", cached)

        try:
            body = await self._download(self._pdf_url)
        except httpx.HTTPError as exc:
            msg = f"Yardeni PDF fetch failed: {exc}"
            raise DataUnavailableError(msg) from exc

        snapshot = _parse_pdf_bytes(body, fallback_publication_date)
        self.cache.set(cache_key, snapshot, ttl=YARDENI_TTL_SECONDS)
        log.info(
            "yardeni.fetched",
            publication_date=snapshot.publication_date.isoformat(),
            time_weighted_forward_eps=snapshot.time_weighted_forward_eps,
        )
        return snapshot

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()


def _parse_pdf_bytes(
    body: bytes, fallback_publication_date: date | None
) -> YardeniEarningsSquigglesSnapshot:
    """Open the PDF via pdfplumber and delegate to :func:`_parse_pdf_text`."""
    try:
        with pdfplumber.open(io.BytesIO(body)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as exc:
        msg = f"Yardeni PDF parse failed (pdfplumber error): {exc}"
        raise DataUnavailableError(msg) from exc
    return _parse_pdf_text(text, fallback_publication_date)


def _parse_pdf_text(
    text: str, fallback_publication_date: date | None
) -> YardeniEarningsSquigglesSnapshot:
    """Extract EPS forecasts from extracted PDF text.

    Raises :class:`DataUnavailableError` if any required numeric field
    is missing. If the PDF contains no machine-readable publication
    date header, falls back to ``fallback_publication_date``; if both
    are absent, raises.
    """
    current = _extract_float(_RE_CURRENT_YEAR_EPS, text, "current-year EPS")
    nxt = _extract_float(_RE_NEXT_YEAR_EPS, text, "next-year EPS")
    twf = _extract_float(_RE_TIME_WEIGHTED_FWD, text, "time-weighted forward EPS")
    publication_date = _extract_publication_date(text) or fallback_publication_date
    if publication_date is None:
        msg = "Yardeni PDF has no publication date and no fallback supplied"
        raise DataUnavailableError(msg)
    return YardeniEarningsSquigglesSnapshot(
        publication_date=publication_date,
        current_year_eps=current,
        next_year_eps=nxt,
        time_weighted_forward_eps=twf,
    )


def _extract_float(regex: re.Pattern[str], text: str, label: str) -> float:
    m = regex.search(text)
    if m is None:
        msg = f"Yardeni PDF missing label {label!r}"
        raise DataUnavailableError(msg)
    try:
        return float(m.group(1))
    except (TypeError, ValueError) as exc:
        msg = f"Yardeni PDF value for {label!r} not a float: {m.group(1)!r}"
        raise DataUnavailableError(msg) from exc


def _extract_publication_date(text: str) -> date | None:
    m = _RE_PUBLICATION_DATE.search(text)
    if m is None:
        return None
    raw = m.group(1).replace(",", "")
    for fmt in ("%B %d %Y", "%b %d %Y"):
        try:
            # Calendar date string; tz is irrelevant (discarded by .date()).
            return datetime.strptime(raw, fmt).date()  # noqa: DTZ007
        except ValueError:
            continue
    return None
