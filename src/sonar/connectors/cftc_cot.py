"""CFTC Commitments of Traders (COT) — weekly non-commercial positioning.

Per spec ``F4-positioning.md`` §2: non-commercial net positions for
S&P 500 futures (plus VIX futures / 10Y Treasury / DXY diagnostics).
Weekly Tuesday as-of date, released Friday.

Endpoint target: https://publicreporting.cftc.gov/resource/6dca-aqww.json
(JSON Open Data API). V0.1 ships as a placeholder connector raising
:class:`DataUnavailableError` on fetch; live wiring is **CAL-063**.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from datetime import date
    from pathlib import Path

log = structlog.get_logger()

CFTC_JSON_API = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"

__all__ = [
    "CFTC_JSON_API",
    "CftcCotConnector",
    "CotObservation",
]


@dataclass(frozen=True, slots=True)
class CotObservation:
    """COT non-commercial net position for a futures contract."""

    observation_date: date  # Tuesday as-of date
    release_date: date  # Friday release date
    contract: str  # "SP500" | "VIX" | "10Y" | "DXY"
    noncomm_long: int
    noncomm_short: int
    source: str = "CFTC"

    @property
    def noncomm_net(self) -> int:
        return self.noncomm_long - self.noncomm_short


class CftcCotConnector:
    """L0 connector for CFTC COT futures positioning.

    V0.1 placeholder — live JSON-API wiring is **CAL-063**. F4 calls
    :meth:`fetch_latest_sp500` and handles
    :class:`DataUnavailableError` by redistributing COT weight per
    spec §6.
    """

    def __init__(self, cache_dir: str | Path | None = None) -> None:
        self.cache_dir = cache_dir

    async def fetch_latest_sp500(self, observation_date: date) -> CotObservation:
        err = (
            f"CFTC COT connector not provisioned (CAL-063); "
            f"observation_date={observation_date.isoformat()}"
        )
        log.warning("cftc_cot.unavailable", observation_date=observation_date)
        raise DataUnavailableError(err)

    async def aclose(self) -> None:
        return None
