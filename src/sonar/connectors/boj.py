"""Bank of Japan (BoJ) Time Series Database (TSD) L0 connector.

Empirical probe 2026-04-21 (Week 8 Sprint L pre-flight): the BoJ TSD
portal at ``https://www.stat-search.boj.or.jp/`` serves HTTP 200 on
the root + FAME form endpoint ``/ssi/cgi-bin/famecgi2`` but ships the
search UI as Shift_JIS-encoded HTML designed for interactive browser
use — there is **no documented JSON/CSV REST API** for programmatic
series retrieval. This is the BoJ analogue of the BoE IADB Akamai
gate (Sprint I pre-flight); the connector is wire-ready but callers
must treat it as soft-fail.

Canonical series codes (BoE TSD catalogue; kept here as documentation
even when the portal is browser-only — surfaces the intent and makes
future unblock trivial):

* **FM01'STRAMUCOLR** — uncollateralized overnight call rate
  (mean — `call_rate`; the daily realised BoJ policy-operating
  target since Feb 1999).
* **FM02'OUCYOTKMM10Y** — 10Y JGB (nominal yield).
* **BS01'MABJMTA** — BoJ Monetary Base (adjusted, monthly).
* **FM08'IRJPY10Y** — 10Y IRS JPY mid.

All series returned as ``list[Observation]`` per ``base.Observation``
with ``yield_bps = int(round(close_pct * 100))`` per
``conventions/units.md`` §Spreads.

Callers in the monetary-indices cascade
(:mod:`sonar.indices.monetary.builders`) treat
:class:`DataUnavailableError` from this connector as a soft fail and
fall back to TE / FRED per Sprint L cascade.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from sonar.connectors.cache import ConnectorCache
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from datetime import date
    from pathlib import Path

    from sonar.connectors.base import Observation

log = structlog.get_logger()

__all__ = [
    "BOJ_BALANCE_SHEET",
    "BOJ_BANK_RATE",
    "BOJ_JGB_10Y",
    "BOJ_TSD_URL",
    "BoJConnector",
]

# Series-ID catalogue (BoJ TSD canonical; sourced from the FAME form
# listing on the public portal). Kept public to aid the post-unblock
# transition — tests assert these constants stay stable.
BOJ_BANK_RATE: Final[str] = "FM01'STRAMUCOLR"
BOJ_JGB_10Y: Final[str] = "FM02'OUCYOTKMM10Y"
BOJ_BALANCE_SHEET: Final[str] = "BS01'MABJMTA"

# Public TSD entry point. The FAME interface below is form-based — all
# series downloads require navigating the /ssi/cgi-bin/famecgi2 wizard
# in a browser session. The canonical URL kept for documentation.
BOJ_TSD_URL: Final[str] = "https://www.stat-search.boj.or.jp/ssi/cgi-bin/famecgi2"

# Reason string emitted when the browser-gated portal blocks the
# connector. Kept as a module constant so tests + retrospectives can
# pin the exact phrasing.
_PORTAL_GATED_REASON: Final[str] = (
    "BoJ TSD portal is browser-gated (form-based FAME interface; no "
    "documented JSON/CSV REST API). Fallback cascade required at "
    "builder layer — TE primary → FRED OECD mirror."
)


class BoJConnector:
    """L0 connector scaffold for BoJ TSD.

    The public TSD portal does not expose a scriptable REST endpoint
    (empirical 2026-04-21 probe — see module docstring). The connector
    ships wire-ready so the JP monetary cascade can consume it as a
    typed dependency; every fetch raises :class:`DataUnavailableError`
    by default so upstream builders fall through to TE primary.

    Should BoJ ship an official JSON/CSV API (or a well-behaved scrape
    path be validated), implement :meth:`_fetch_raw` to populate the
    series payload; the public ``fetch_*`` methods remain unchanged.
    """

    BASE_URL: Final[str] = BOJ_TSD_URL
    CACHE_NAMESPACE: Final[str] = "boj_tsd"
    CONNECTOR_ID: Final[str] = "boj"

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
                "Accept": "text/csv, application/json, text/html, */*",
                "Accept-Language": "en",
            },
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=2, max=30),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _fetch_raw(
        self,
        series_id: str,
        start: date,
        end: date,
    ) -> str:
        """Probe-stage: TSD portal is browser-gated — raise immediately.

        Kept as an ``async`` method (vs a plain ``raise`` on the caller)
        so the future un-gate is a drop-in: replace the body with the
        real HTTP call once BoJ ships a machine-friendly endpoint.
        """
        _ = series_id, start, end  # documented intent; inputs ignored while gated
        log.warning(
            "boj.portal_gated",
            series=series_id,
            reason=_PORTAL_GATED_REASON,
        )
        raise DataUnavailableError(
            f"BoJ TSD series={series_id!r} unavailable: {_PORTAL_GATED_REASON}"
        )

    async def fetch_series(
        self,
        series_id: str,
        start: date,
        end: date,
    ) -> list[Observation]:
        """Return parsed observations for ``(series_id, start, end)``. Cached 24h.

        Always raises :class:`DataUnavailableError` at Sprint L scope
        because :meth:`_fetch_raw` cannot reach a scriptable endpoint.
        Cache hits short-circuit the raise so post-unblock backfills
        land cleanly.
        """
        cache_key = f"{self.CACHE_NAMESPACE}:{series_id}:{start.isoformat()}:{end.isoformat()}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            log.debug("boj.cache_hit", series=series_id)
            # Cache entries are the parsed Observation list (post-unblock).
            # Accept without re-fetching; tests seed this path.
            return list(cached)
        _ = await self._fetch_raw(series_id, start, end)
        # Unreachable under the browser-gated scaffold — retained for
        # the future unblock path where _fetch_raw returns CSV + we
        # parse into Observations.
        raise DataUnavailableError(  # pragma: no cover - unreachable while gated
            f"BoJ TSD series={series_id!r}: unexpected reachable raw body"
        )

    async def fetch_bank_rate(self, start: date, end: date) -> list[Observation]:
        """BoJ uncollateralized overnight call rate — series :data:`BOJ_BANK_RATE`.

        Browser-gated at Sprint L scope; raises
        :class:`DataUnavailableError` which the M1 JP cascade treats as
        soft-fail.
        """
        return await self.fetch_series(BOJ_BANK_RATE, start, end)

    async def fetch_jgb_10y(self, start: date, end: date) -> list[Observation]:
        """10Y JGB nominal yield — series :data:`BOJ_JGB_10Y`."""
        return await self.fetch_series(BOJ_JGB_10Y, start, end)

    async def fetch_balance_sheet(self, start: date, end: date) -> list[Observation]:
        """BoJ Monetary Base (adjusted) — series :data:`BOJ_BALANCE_SHEET`."""
        return await self.fetch_series(BOJ_BALANCE_SHEET, start, end)

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()


# Expose the reason constant so retrospectives + retrieval auditing
# can reference the canonical phrasing without importing a private.
BOJ_PORTAL_GATED_REASON: Final[str] = _PORTAL_GATED_REASON
