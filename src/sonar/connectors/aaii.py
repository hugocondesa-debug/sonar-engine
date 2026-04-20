"""AAII weekly investor-sentiment survey connector.

Per spec ``F4-positioning.md`` §2: bull/bear/neutral percentages from
the American Association of Individual Investors. Thursday publication.

Primary path: public xls / csv at ``www.aaii.com/files/surveys/sentiment.xls``.
Layout drift is a real risk (the spec §6 row warns about layout
changes → ``AAII_UNAVAILABLE`` flag). This connector exposes a
``fetch_latest`` that can be monkey-patched in tests to inject known
rows; live fetch support is guarded by an explicit ``live=True`` flag
+ raises :class:`DataUnavailableError` when the public endpoint
returns a 404 or unexpected schema.
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

AAII_PUBLIC_URL = "https://www.aaii.com/files/surveys/sentiment.xls"

__all__ = [
    "AAII_PUBLIC_URL",
    "AaiiConnector",
    "AaiiSurveyObservation",
]


@dataclass(frozen=True, slots=True)
class AaiiSurveyObservation:
    """AAII weekly survey row (Thursday publication)."""

    observation_date: date
    bull_pct: float
    bear_pct: float
    neutral_pct: float
    source: str = "AAII"

    @property
    def bull_minus_bear_pct(self) -> float:
        return self.bull_pct - self.bear_pct


class AaiiConnector:
    """L0 connector for AAII sentiment survey.

    Live fetching of the public xls is **not** implemented in v0.1; the
    spec §6 anticipates ``AAII_UNAVAILABLE`` flag as acceptable. The
    primary consumer (F4) calls :meth:`fetch_latest`, catches
    :class:`DataUnavailableError`, and proceeds with the
    ``AAII_PROXY`` fallback. A live-fetch path (+ schema-drift guard)
    is scheduled as **CAL-062**.
    """

    def __init__(self, cache_dir: str | Path | None = None) -> None:
        self.cache_dir = cache_dir

    async def fetch_latest(self, observation_date: date) -> AaiiSurveyObservation:
        """Placeholder — raises DataUnavailableError. See CAL-062."""
        err = (
            f"AAII connector not provisioned (CAL-062); "
            f"observation_date={observation_date.isoformat()}"
        )
        log.warning("aaii.unavailable", observation_date=observation_date)
        raise DataUnavailableError(err)

    async def aclose(self) -> None:
        return None
