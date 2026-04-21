"""Swiss National Bank (SNB) data-portal L0 connector.

Empirical probe 2026-04-21 (Week 9 Sprint V pre-flight): the SNB data
portal at ``https://data.snb.ch/api/cube/{cube_id}/data/csv/en`` serves
**semicolon-delimited CSVs** with a tiny header (CubeId + PublishingDate
on rows 1-2, blank row, column header on row 4, data rows after) for
any published cube. No auth, no bot-detection gate (plain ``curl``
clears it with an ``Accept: text/csv`` header).

Canonical cubes (all observed live during the Sprint V probe):

* **``zimoma``** — Swiss money-market rates. Multi-series cube; the
  ``SARON`` row (Swiss Average Rate Overnight, 3M-CHF-LIBOR successor)
  lands monthly-averaged back to 2000-06 (651 non-empty observations
  at probe). SNB has targeted SARON directly as its policy rate since
  June 2019; pre-2019 SARON data is the empirical rate underlying
  whatever regime SNB ran (3M-CHF-LIBOR target midpoint, negative-rate
  corridor, etc.). The monetary cascade consumes SARON as the **M1
  native secondary** — monthly cadence is coarser than TE's daily
  primary, but SNB policy-rate changes are quarterly so the monthly
  aggregation is materially equivalent for M1 purposes.
* **``rendoblim``** — Swiss Confederation bond yields at constant
  maturity. Multi-series cube keyed by tenor (``1J``..``30J`` where
  ``J`` = ``Jahre``). Monthly cadence back to 1988-01 (5867 rows at
  probe). Landing point for M4 FCI CH 10Y input (CAL-CH-M4-FCI —
  deferred Sprint V).

The portal uses German-language ``J`` (Jahre) tenor suffixes; we map
``10J`` → ``tenor_years = 10.0`` at the wrapper level.

CSV schema (both cubes):

```
"CubeId";"<cube_id>"
"PublishingDate";"YYYY-MM-DD HH:MM"
<blank>
"Date";"D0";"Value"
"YYYY-MM";"<series_code>";"<value>"
...
```

The ``D0`` column carries the series code within a multi-series cube
(``SARON``, ``1TGT``, ``EURIBOR``, ``10J``, etc.). Empty ``Value``
cells mark a not-yet-populated observation — we skip those. The
``Date`` column is **monthly** (``YYYY-MM``) across both public cubes
observed so far; we normalise to the first-of-month.

All observations are returned as ``list[Observation]`` per
``base.Observation`` with ``yield_bps = int(round(rate_pct * 100))``
per ``conventions/units.md`` §Spreads. Negative-rate era observations
(2014-2022 for SARON) flow through unchanged — see
:func:`SNBConnector.fetch_saron` for the preservation contract.

Callers in the monetary-indices cascade
(:mod:`sonar.indices.monetary.builders`) treat
:class:`DataUnavailableError` from this connector as a soft fail and
fall back to FRED OECD mirror per the Sprint V cascade (TE primary →
SNB native → FRED stale-flagged).
"""

from __future__ import annotations

import csv
from datetime import UTC, date, datetime
from io import StringIO
from typing import TYPE_CHECKING, Final

import httpx
import structlog
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from sonar.connectors.base import Observation
from sonar.connectors.cache import DEFAULT_TTL_SECONDS, ConnectorCache
from sonar.overlays.exceptions import DataUnavailableError

if TYPE_CHECKING:
    from pathlib import Path

log = structlog.get_logger()

__all__ = [
    "SNB_CONFED_10Y_TENOR",
    "SNB_DATA_PORTAL_BASE_URL",
    "SNB_RENDOBLIM_CUBE",
    "SNB_SARON_SERIES",
    "SNB_USER_AGENT",
    "SNB_ZIMOMA_CUBE",
    "SNBConnector",
]

# Cube-ID catalogue (SNB data-portal canonical; validated empirically
# during Sprint V pre-flight, 2026-04-21).
SNB_ZIMOMA_CUBE: Final[str] = "zimoma"
SNB_RENDOBLIM_CUBE: Final[str] = "rendoblim"

# D0-column series codes for the SNB cubes we consume.
SNB_SARON_SERIES: Final[str] = "SARON"
# Swiss Confederation bond-yield tenor code (German ``J`` = Jahre).
SNB_CONFED_10Y_TENOR: Final[str] = "10J"

SNB_DATA_PORTAL_BASE_URL: Final[str] = "https://data.snb.ch/api/cube"

# SNB data portal does not bot-screen the CSV endpoints, but we send a
# descriptive UA anyway — keeps operator identity on the server-side
# request log and matches the Sprint T (RBA) / Sprint S (BoC) pattern.
SNB_USER_AGENT: Final[str] = "SONAR/2.0 (monetary-cascade; contact hugocondesa@pm.me)"

# Row of the "Date;D0;Value" header (0-indexed). Rows 0-1 carry
# CubeId / PublishingDate metadata, row 2 is blank, row 3 is the
# column header, rows 4+ are data.
_HEADER_ROW_INDEX: Final[int] = 3


class SNBConnector:
    """L0 connector for the SNB data-portal CSV endpoints.

    The portal is public — no API key, no auth, no bot screen on the
    ``/api/cube/{cube_id}/data/csv/en`` path (Sprint V probe
    2026-04-21). Responses are **monthly** semicolon-delimited CSVs
    with a 3-column ``Date;D0;Value`` schema where ``D0`` multiplexes
    multiple series within a single cube (SARON, 1TGT, EURIBOR on
    ``zimoma``; 1J..30J on ``rendoblim``).

    Slot in cascade: **secondary** behind TE primary for CH monetary
    inputs (see :func:`build_m1_ch_inputs`). Returns results in the
    generic ``Observation`` shape so the builder resampler can consume
    them unchanged.

    Monthly cadence is coarser than TE's daily primary, but SNB policy
    rate changes at a quarterly decision cadence so the monthly
    aggregation is materially equivalent for M1 purposes. The cascade
    never emits a staleness flag on the SNB native path — the
    monthly-vs-daily delta is documented via
    ``CH_POLICY_RATE_SNB_NATIVE_MONTHLY`` rather than
    ``CALIBRATION_STALE``.
    """

    BASE_URL: Final[str] = SNB_DATA_PORTAL_BASE_URL
    CACHE_NAMESPACE: Final[str] = "snb_portal"
    CONNECTOR_ID: Final[str] = "snb"

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
                "User-Agent": SNB_USER_AGENT,
                "Accept": "text/csv,application/octet-stream,*/*",
            },
        )

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=30),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _fetch_raw(self, cube_id: str) -> str:
        """Hit ``/api/cube/{cube_id}/data/csv/en`` and return the body."""
        url = f"{self.BASE_URL}/{cube_id}/data/csv/en"
        r = await self.client.get(url)
        r.raise_for_status()
        return r.text

    @staticmethod
    def _parse_csv(
        body: str,
        *,
        cube_id: str,
        series_code: str,
    ) -> list[tuple[date, float]]:
        """Parse an SNB cube CSV string into ``[(obs_date, value), ...]``.

        Filters data rows to the single ``series_code`` value within
        the multi-series ``D0`` column and normalises the monthly
        ``YYYY-MM`` date to the first-of-month.

        Raises :class:`DataUnavailableError` when the header row is
        not where expected (schema drift) or when no parseable rows
        survive for the requested series.
        """
        reader = list(csv.reader(StringIO(body), delimiter=";"))
        if len(reader) <= _HEADER_ROW_INDEX:
            msg = f"SNB cube={cube_id!r} CSV too short: {len(reader)} rows"
            raise DataUnavailableError(msg)
        header = [cell.strip() for cell in reader[_HEADER_ROW_INDEX]]
        expected = ["Date", "D0", "Value"]
        if header != expected:
            msg = f"SNB cube={cube_id!r} header mismatch: expected {expected!r}, got {header!r}"
            raise DataUnavailableError(msg)

        out: list[tuple[date, float]] = []
        for row in reader[_HEADER_ROW_INDEX + 1 :]:
            if len(row) < 3:
                continue
            raw_date = row[0].strip()
            row_series = row[1].strip()
            raw_value = row[2].strip()
            if not raw_date or row_series != series_code or not raw_value:
                continue
            try:
                # SNB monthly dates are ``YYYY-MM``; anchor on the 1st.
                obs_date = datetime.strptime(raw_date, "%Y-%m").replace(tzinfo=UTC).date()
                value = float(raw_value)
            except (TypeError, ValueError):
                continue
            out.append((obs_date, value))
        if not out:
            msg = f"SNB cube={cube_id!r} series={series_code!r}: no parseable rows"
            raise DataUnavailableError(msg)
        return out

    async def fetch_series(
        self,
        cube_id: str,
        series_code: str,
        start: date,
        end: date,
    ) -> list[Observation]:
        """Return parsed observations for ``(cube_id, series_code)`` in ``[start, end]``.

        Cached 24h.

        Empty column or HTTP error raises :class:`DataUnavailableError`;
        upstream cascade callers treat that as soft-fail and fall back
        to FRED OECD mirror.

        Negative values are preserved verbatim. Per SNB conventions,
        SARON / CHF-LIBOR / 1TGT observations from the 2015-2022
        negative-rate corridor carry strictly-negative values (minimum
        around -0.76 % on SARON); the ``int(round(value_pct * 100))``
        conversion at the Observation layer round-half-evens naturally
        on negatives and no clamp is applied.
        """
        cache_key = (
            f"{self.CACHE_NAMESPACE}:{cube_id}:{series_code}:{start.isoformat()}:{end.isoformat()}"
        )
        cached = self.cache.get(cache_key)
        if cached is not None:
            log.debug("snb.cache_hit", cube=cube_id, series=series_code)
            return list(cached)

        try:
            body = await self._fetch_raw(cube_id)
        except (httpx.HTTPError, RetryError) as exc:
            msg = f"SNB cube={cube_id!r} HTTP error: {exc}"
            raise DataUnavailableError(msg) from exc

        parsed = self._parse_csv(body, cube_id=cube_id, series_code=series_code)
        out: list[Observation] = []
        for obs_date, value_pct in parsed:
            if not (start <= obs_date <= end):
                continue
            out.append(
                Observation(
                    country_code="CH",
                    observation_date=obs_date,
                    tenor_years=0.01,
                    yield_bps=round(value_pct * 100),
                    source="SNB",
                    source_series_id=f"{cube_id}:{series_code}",
                )
            )
        if not out:
            msg = (
                f"SNB cube={cube_id!r} series={series_code!r}: no rows in "
                f"[{start.isoformat()}, {end.isoformat()}]"
            )
            raise DataUnavailableError(msg)
        out.sort(key=lambda o: o.observation_date)
        self.cache.set(cache_key, out, ttl=DEFAULT_TTL_SECONDS)
        log.info(
            "snb.fetched",
            cube=cube_id,
            series=series_code,
            n=len(out),
        )
        return out

    async def fetch_saron(self, start: date, end: date) -> list[Observation]:
        """SARON monthly — cube :data:`SNB_ZIMOMA_CUBE`, series :data:`SNB_SARON_SERIES`.

        Swiss Average Rate Overnight, monthly-averaged. SNB's direct
        policy-rate target since June 2019; pre-2019 the value
        reflects the empirical rate under the 3M-CHF-LIBOR corridor
        regime including the 2015-2022 negative-rate era (minimum
        around -0.76 % on SARON). Named ``fetch_saron`` because
        "policy rate" has two meanings in the CH context depending on
        era — SARON is the unambiguous underlying.

        The cascade (see
        :func:`sonar.indices.monetary.builders.build_m1_ch_inputs`)
        consumes SARON as the M1 native secondary, emitting
        ``CH_POLICY_RATE_SNB_NATIVE`` (never staleness) alongside
        ``CH_POLICY_RATE_SNB_NATIVE_MONTHLY`` to flag the cadence
        delta vs the daily TE primary.
        """
        return await self.fetch_series(SNB_ZIMOMA_CUBE, SNB_SARON_SERIES, start, end)

    async def fetch_confederation_10y(self, start: date, end: date) -> list[Observation]:
        """10Y Confederation bond yield — cube :data:`SNB_RENDOBLIM_CUBE`, tenor ``10J``.

        Swiss Confederation constant-maturity 10-year benchmark,
        monthly-averaged. Landing point for M4 FCI CH 10Y input and
        any future CH rating-spread anchoring. Tenor is overridden to
        10.0 years on the returned Observations (vs the 0.01 default
        :func:`fetch_series` stamps for short-rate use).
        """
        obs = await self.fetch_series(SNB_RENDOBLIM_CUBE, SNB_CONFED_10Y_TENOR, start, end)
        return [o.model_copy(update={"tenor_years": 10.0}) for o in obs]

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()
