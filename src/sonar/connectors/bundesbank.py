"""Bundesbank L0 connector — DE term-structure derived yields.

Pattern mirrors :class:`sonar.connectors.fred.FredConnector`. Endpoint is
the Bundesbank statistic-rmi web download (no API key); series IDs
follow the BBSIS daily zero-coupon-implied-yields family
``BBSIS.D.I.ZAR.ZI.EUR.S1311.B.A604.R{TT}XX.R.A.A._Z._Z.A``
where ``TT`` is the tenor in years zero-padded to 2 digits.

Tenors published at integer years 1..30; we surface the 9 maturities
that align with ``STANDARD_OUTPUT_TENORS`` (1Y, 2Y, 3Y, 5Y, 7Y, 10Y,
15Y, 20Y, 30Y). Sub-year tenors live in a different Bundesbank dataset
and are out of scope for Week 2.

CSV format: German locale (``;`` separator, ``,`` decimal). Header
spans 5 lines (title + unit + dimension + Stand vom + blank);
``_parse_csv`` strips them.

Reference: ``docs/data_sources/monetary.md`` line 155;
spec ``docs/specs/overlays/nss-curves.md`` §2 T1 DE primary.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, cast

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from sonar.connectors.base import BaseConnector, Observation
from sonar.connectors.cache import DEFAULT_TTL_SECONDS, ConnectorCache

if TYPE_CHECKING:
    from datetime import date
    from pathlib import Path

log = structlog.get_logger()

# Bundesbank Daily Zero-coupon Implied yields, residual maturity TT years.
BUNDESBANK_DE_NOMINAL_SERIES: dict[str, str] = {
    "1Y": "BBSIS.D.I.ZAR.ZI.EUR.S1311.B.A604.R01XX.R.A.A._Z._Z.A",
    "2Y": "BBSIS.D.I.ZAR.ZI.EUR.S1311.B.A604.R02XX.R.A.A._Z._Z.A",
    "3Y": "BBSIS.D.I.ZAR.ZI.EUR.S1311.B.A604.R03XX.R.A.A._Z._Z.A",
    "5Y": "BBSIS.D.I.ZAR.ZI.EUR.S1311.B.A604.R05XX.R.A.A._Z._Z.A",
    "7Y": "BBSIS.D.I.ZAR.ZI.EUR.S1311.B.A604.R07XX.R.A.A._Z._Z.A",
    "10Y": "BBSIS.D.I.ZAR.ZI.EUR.S1311.B.A604.R10XX.R.A.A._Z._Z.A",
    "15Y": "BBSIS.D.I.ZAR.ZI.EUR.S1311.B.A604.R15XX.R.A.A._Z._Z.A",
    "20Y": "BBSIS.D.I.ZAR.ZI.EUR.S1311.B.A604.R20XX.R.A.A._Z._Z.A",
    "30Y": "BBSIS.D.I.ZAR.ZI.EUR.S1311.B.A604.R30XX.R.A.A._Z._Z.A",
}

BUNDESBANK_SERIES_TENORS: dict[str, float] = {
    sid: float(label.rstrip("Y")) for label, sid in BUNDESBANK_DE_NOMINAL_SERIES.items()
}


class BundesbankConnector(BaseConnector):
    """L0 connector for Bundesbank statistic-rmi web downloads (DE)."""

    BASE_URL = "https://www.bundesbank.de/statistic-rmi/StatisticDownload"

    def __init__(self, cache_dir: str | Path, timeout: float = 30.0) -> None:
        self.cache = ConnectorCache(cache_dir)
        self.client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=60),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _fetch_raw(self, series_id: str) -> str:
        # Bundesbank web download serves the **full history** of a series; we
        # window-filter in Python afterwards (no startPeriod query param honoured
        # by this endpoint).
        params = {
            "tsId": series_id,
            "its_csvFormat": "de",
            "its_fileFormat": "csv",
            "mode": "its",
        }
        r = await self.client.get(self.BASE_URL, params=params)
        r.raise_for_status()
        return r.text

    async def fetch_series(self, series_id: str, start: date, end: date) -> list[Observation]:
        cache_key = f"bundesbank:{series_id}:{start.isoformat()}:{end.isoformat()}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            log.debug("bundesbank.cache_hit", series=series_id)
            return cast("list[Observation]", cached)

        tenor = BUNDESBANK_SERIES_TENORS.get(series_id)
        if tenor is None:
            msg = f"Unknown Bundesbank series mapping: {series_id}"
            raise ValueError(msg)

        body = await self._fetch_raw(series_id)
        observations = [
            obs
            for obs in _parse_csv(body, series_id, tenor)
            if start <= obs.observation_date <= end
        ]
        self.cache.set(cache_key, observations, ttl=DEFAULT_TTL_SECONDS)
        log.info("bundesbank.fetched", series=series_id, n=len(observations))
        return observations

    async def fetch_yield_curve_nominal(
        self, country: str, observation_date: date
    ) -> dict[str, Observation]:
        """DE term-structure derived yield curve (9 tenors 1Y..30Y)."""
        if country != "DE":
            msg = f"Bundesbank yield curve only supports country=DE; got {country}"
            raise ValueError(msg)

        window_days = 7
        start = observation_date - timedelta(days=window_days)
        end = observation_date
        out: dict[str, Observation] = {}
        for tenor_label, series_id in BUNDESBANK_DE_NOMINAL_SERIES.items():
            obs_list = await self.fetch_series(series_id, start, end)
            usable = [o for o in obs_list if o.observation_date <= observation_date]
            if not usable:
                continue
            usable.sort(key=lambda o: o.observation_date)
            out[tenor_label] = usable[-1]
        return out

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()


def _parse_csv(body: str, series_id: str, tenor: float) -> list[Observation]:
    """Parse Bundesbank CSV (German locale: ``;`` separator, ``,`` decimal).

    Header spans the first 5 lines (title + Einheit + Dimension + Stand
    vom + blank). Data rows: ``YYYY-MM-DD;value[,decimal];flags``. Empty
    or sentinel ``.`` rows are skipped.
    """
    out: list[Observation] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # Skip header rows (the data rows always start with YYYY-).
        if not (len(line) >= 10 and line[4] == "-" and line[7] == "-"):
            continue
        parts = line.split(";")
        if len(parts) < 2:
            continue
        date_str, value_str = parts[0], parts[1].strip()
        if not value_str or value_str in {".", "NA"}:
            continue
        try:
            obs_date = datetime.fromisoformat(date_str).date()
        except ValueError:
            continue
        try:
            value_pct = float(value_str.replace(",", "."))
        except ValueError:
            continue
        out.append(
            Observation(
                country_code="DE",
                observation_date=obs_date,
                tenor_years=tenor,
                yield_bps=round(value_pct * 100),
                source="BUNDESBANK",
                source_series_id=series_id,
            )
        )
    return out
