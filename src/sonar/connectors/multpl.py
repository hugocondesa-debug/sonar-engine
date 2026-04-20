"""multpl.com scraper — S&P 500 dividend yield (current).

Endpoint pattern: ``https://www.multpl.com/s-p-500-dividend-yield``
(static HTML, no API). Returns current dividend yield % as `float`.

Structure depends on page layout; we extract from the ``<meta
name="description">`` tag which contains a deterministic string
``Current S&P 500 Dividend Yield is X.XX%, a change of Y.YY bps``.
This is more stable than scraping the rendered HTML body.

Graceful failure: on HTML parse error or non-200 HTTP, raises
``DataUnavailableError``. Caller decides whether to emit
``OVERLAY_MISS`` flag.
"""

from __future__ import annotations

import re
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
from sonar.overlays.exceptions import OverlayError

if TYPE_CHECKING:
    from pathlib import Path

log = structlog.get_logger()

MULTPL_DIVIDEND_YIELD_URL: str = "https://www.multpl.com/s-p-500-dividend-yield"
MULTPL_TTL_SECONDS: int = 24 * 3600  # daily refresh

# Regex matches patterns like "Current S&P 500 Dividend Yield is 1.10%" in
# the page's <meta name="description"> tag.
_DESCRIPTION_REGEX = re.compile(r"Current S&P 500 Dividend Yield is\s+(\d+\.\d+)%", re.IGNORECASE)


class DataUnavailableError(OverlayError):
    """Raised when a web scraper cannot extract the target value."""


class MultplConnector:
    """L0 scraper for multpl.com current dividend yield."""

    BASE_URL = MULTPL_DIVIDEND_YIELD_URL
    CACHE_NAMESPACE = "multpl:dividend_yield"

    def __init__(self, cache_dir: str | Path, timeout: float = 30.0) -> None:
        self.cache = ConnectorCache(cache_dir)
        self.client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=2, max=30),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _download(self) -> str:
        r = await self.client.get(self.BASE_URL)
        r.raise_for_status()
        return r.text

    async def fetch_current_dividend_yield_decimal(self) -> float:
        """Return current S&P 500 dividend yield as decimal (0.011 = 1.1%)."""
        cached = self.cache.get(self.CACHE_NAMESPACE)
        if cached is not None:
            log.debug("multpl.cache_hit")
            return cast("float", cached)
        html = await self._download()
        decimal = _extract_dividend_yield(html)
        self.cache.set(self.CACHE_NAMESPACE, decimal, ttl=MULTPL_TTL_SECONDS)
        log.info("multpl.fetched", dividend_yield_decimal=round(decimal, 5))
        return decimal

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()


def _extract_dividend_yield(html: str) -> float:
    """Parse the dividend yield percent out of the multpl HTML.

    Raises ``DataUnavailableError`` when the expected marker is absent.
    """
    m = _DESCRIPTION_REGEX.search(html)
    if m is None:
        msg = "multpl.com response did not contain dividend yield marker"
        raise DataUnavailableError(msg)
    try:
        pct = float(m.group(1))
    except (TypeError, ValueError) as exc:
        msg = f"multpl.com parser failed to coerce {m.group(1)!r} to float"
        raise DataUnavailableError(msg) from exc
    return pct / 100.0
