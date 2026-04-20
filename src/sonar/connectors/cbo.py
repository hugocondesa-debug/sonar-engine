"""CBO output gap connector (CAL-097, week6 sprint 2b).

Output gap = (real_gdp - potential_gdp) / potential_gdp, primary input for
M2 Taylor-rule variants per spec ``M2-taylor-gaps.md`` §2.

Happy path is FRED-hosted ``GDPPOT`` (CBO real potential GDP) paired with
``GDPC1`` (actual real GDP). Both quarterly, chained 2017 dollars, fully
aligned on FRED quarterly observation dates. The CBO Excel scrape
fallback (``cbo.gov/data/budget-economic-data``) is documented in the
spec but not implemented here — the FRED primary path responded 200 live
during the week6-sprint-2b pre-flight probe, so this connector wraps
FRED directly.

Callers pass an already-constructed :class:`FredConnector` to keep the
auth-and-cache ownership local to the caller (per existing composition
pattern in ``sonar.indices.economic.builders``). The connector itself is
stateless beyond the FRED reference.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sonar.connectors.fred import FredConnector


__all__ = ["CboConnector", "OutputGapObservation"]


@dataclass(frozen=True, slots=True)
class OutputGapObservation:
    """Output gap (decimal) for a quarterly observation.

    ``gap`` = (real_gdp - potential_gdp) / potential_gdp — negative when
    actual trails potential (below-trend), positive when above.
    """

    observation_date: date
    gap: float
    real_gdp: float
    potential_gdp: float
    source: str = "FRED"
    real_series_id: str = "GDPC1"
    potential_series_id: str = "GDPPOT"


class CboConnector:
    """FRED-backed wrapper for CBO output gap (CAL-097 primary path)."""

    def __init__(self, fred: FredConnector) -> None:
        self.fred = fred

    async def fetch_output_gap_us(self, start: date, end: date) -> list[OutputGapObservation]:
        """Return output-gap observations aligned on quarterly FRED dates."""
        actual = await self.fred.fetch_real_gdp_us(start, end)
        potential = await self.fred.fetch_potential_gdp_us(start, end)
        pot_by_date = {o.observation_date: o.value for o in potential}
        out: list[OutputGapObservation] = []
        for a in actual:
            p = pot_by_date.get(a.observation_date)
            if p is None or p == 0:
                continue
            out.append(
                OutputGapObservation(
                    observation_date=a.observation_date,
                    gap=(a.value - p) / p,
                    real_gdp=a.value,
                    potential_gdp=p,
                )
            )
        return out

    async def fetch_latest_output_gap_us(
        self, observation_date: date, *, window_days: int = 200
    ) -> OutputGapObservation | None:
        """Return the most recent output-gap observation at or before ``observation_date``.

        Quarterly series; default 200-day window spans 2+ quarters so the
        latest vintage is always in scope even when the BEA Q4 advance
        release lags publication.
        """
        start = observation_date - timedelta(days=window_days)
        gaps = await self.fetch_output_gap_us(start, observation_date)
        usable = [g for g in gaps if g.observation_date <= observation_date]
        if not usable:
            return None
        usable.sort(key=lambda g: g.observation_date)
        return usable[-1]
