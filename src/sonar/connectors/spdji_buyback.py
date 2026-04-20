"""S&P DJI buyback yield connector — Week 3.5B graceful-stub.

S&P DJI publishes quarterly buyback figures on spglobal.com in PDF
format. The URL pattern is not stable across publications and
scraping requires per-release maintenance. Phase 1 ships a stub
that returns ``None`` with a well-defined ``DataUnavailableError``
on call, so the ERP Gordon method can gracefully handle missing
buyback data by treating ``buyback_yield_pct = None`` and setting
just the dividend-yield component.

Real implementation deferred to Phase 2 (PDF scrape with
maintenance playbook). Scope explicitly accepted in Week 3.5B brief
§1 ("graceful degrade").
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from sonar.overlays.exceptions import OverlayError

if TYPE_CHECKING:
    from pathlib import Path

log = structlog.get_logger()


class DataUnavailableError(OverlayError):
    """Raised when buyback yield cannot be retrieved."""


class SPDJIBuybackConnector:
    """Stub connector for S&P DJI quarterly buybacks.

    Week 3.5B: all calls raise ``DataUnavailableError`` — Gordon method
    consumer handles ``None`` buyback_yield gracefully. Phase 2 replaces
    the stub with a live PDF scrape per SPGlobal publication calendar.
    """

    def __init__(self, cache_dir: str | Path) -> None:
        self._cache_dir = cache_dir  # retained for future use

    async def fetch_latest_buyback_yield_decimal(self) -> float:
        """Always raises — stub not yet implemented."""
        msg = (
            "spdji_buyback connector is a graceful stub (Week 3.5B scope). "
            "Caller should treat buyback_yield_pct as None."
        )
        log.info("spdji_buyback.stub_invoked")
        raise DataUnavailableError(msg)

    async def aclose(self) -> None:
        return None
