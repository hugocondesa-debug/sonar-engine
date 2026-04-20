"""MOVE index connector — degraded path pending ICE data license.

Per spec ``F3-risk-appetite.md`` §2 + §Non-US handling: MOVE (ICE BofA
Merrill Lynch Option Volatility Estimate) is NOT on FRED natively and
ICE does not expose a free public endpoint. Per brief §9 notes,
degraded paths via ``MOVE_UNAVAILABLE`` flag + weight redistribution
are acceptable in F3 v0.1.

This connector declares the interface contract for the future live
path (ICE paid endpoint OR Yahoo scrape per governance/LICENSING.md §7
ethics pattern) but raises :class:`DataUnavailableError` on every
``fetch_latest`` call until the live source is authorised. F3 must
handle the exception → emit ``MOVE_UNAVAILABLE`` + redistribute
weights per spec §6.

Live-source decision tracked as **CAL-061** in the F-cycle retro.
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

__all__ = [
    "MoveIndexConnector",
    "MoveObservation",
]


@dataclass(frozen=True, slots=True)
class MoveObservation:
    """MOVE observation — level in bps-annualized (e.g. 110.0)."""

    observation_date: date
    value_level: float
    source: str = "ICE"
    source_series_id: str = "MOVE"


class MoveIndexConnector:
    """Placeholder connector documenting the MOVE data-gap status.

    Always raises :class:`DataUnavailableError` from :meth:`fetch_latest`;
    F3 aggregates this into the ``MOVE_UNAVAILABLE`` flag.
    """

    def __init__(self, cache_dir: str | Path | None = None) -> None:
        self.cache_dir = cache_dir

    async def fetch_latest(self, observation_date: date) -> MoveObservation:
        """Always raises; MOVE is not yet provisioned. See CAL-061."""
        err = (
            f"MOVE connector not provisioned (CAL-061); "
            f"observation_date={observation_date.isoformat()}"
        )
        log.warning("move_index.unavailable", observation_date=observation_date)
        raise DataUnavailableError(err)

    async def aclose(self) -> None:
        return None
