"""Danmarks Nationalbanken Statbank L0 connector (Statistics Denmark API host).

Empirical probe 2026-04-22 (Week 9 Sprint Y-DK pre-flight): Danmarks
Nationalbanken's monetary statistics tables are published on the
Statistics Denmark (Danmarks Statistik) Statbank platform — REST + JSON
at ``https://api.statbank.dk/v1/`` — **public + scriptable** with no
auth required for the historical series. This is the first cascade
where the central-bank's own data lands via a *third-party-host* API
(Danmarks Statistik hosts Nationalbanken's monetary statistics tables
under the ``DN`` table-prefix); the Nationalbanken own-host
(``nationalbanken.statistikbank.dk``) is the older PX-Web 5a UI and
does not expose a programmatic JSON endpoint.

Two endpoint shapes consumed by Sprint Y-DK:

- ``GET /v1/tableinfo/{tableId}?lang=en&format=JSON`` — catalogue /
  metadata, used to discover variable codes.
- ``POST /v1/data`` (JSON body) — observation extraction; we use
  ``format=BULK`` (semicolon-delimited CSV) rather than ``JSONSTAT``
  because BULK supports the wildcard ``Tid=["*"]`` selector for
  full-history pulls without paging, while JSONSTAT enforces an
  observation-count ceiling per request.

Canonical instrument codes (Statbank ``DNRENTD`` table, INSTRUMENT
variable; all observed live during the Sprint Y-DK probe):

- **OIBNAA** — Nationalbanken official **certificate-of-deposit
  rate** (``indskudsbevisrenten``; the CD rate). This is the active
  EUR-peg defence tool — Nationalbanken adjusts the CD rate to
  defend the DKK/EUR peg within the ERM-II ±2.25 % band. The CD rate
  was the primary policy lever across the 2014-2022 negative-rate
  corridor (trough -0.75 % at 2015-04-07; 2450 strictly-negative
  daily observations through 2020-01-07 per the Sprint Y-DK probe
  on the 10780-row full-history series). Sprint Y-DK consumes this
  series as the **DK M1 cascade native secondary**.
- **ODKNAA** — Nationalbanken official **discount rate**
  (``diskontoen``). Historical benchmark; not the active policy
  tool. TE's primary cascade slot exposes this instrument under
  ``DEBRDISC``. Sprint Y-DK does not consume this series via
  Statbank (the TE primary slot covers it) but the instrument code
  is exposed here for future operators who need cross-validation.
- **OIRNAA** — Nationalbanken official **lending rate**
  (``udlånsrenten``); reserved for future M4 FCI corridor
  ceiling consumer (CAL-DK-M4-FCI).
- **OFONAA** — Nationalbanken **current-account deposit rate**
  (``foliorenten``); reserved for future M4 FCI corridor floor
  consumer (CAL-DK-M4-FCI). The current-account rate is what banks
  earn on overnight deposits with Nationalbanken up to the CD
  ceiling — historically zero through most of the 2014-2022 era.

Source-instrument divergence vs the TE primary cascade slot is the
key Sprint Y-DK empirical finding: TE returns the discount rate
(``DEBRDISC`` → ``ODKNAA``) but the active EUR-peg defence tool is
the CD rate (``OIBNAA``). The two diverged across 2014-2022 — the
discount rate spent most of the era at ~0 % while the CD rate ran
to -0.75 %. The cascade contract emits flags on the active source
(``DK_POLICY_RATE_TE_PRIMARY`` vs ``DK_POLICY_RATE_NATIONALBANKEN_NATIVE``)
so downstream consumers can pick the right semantic — see
:func:`sonar.indices.monetary.builders._dk_policy_rate_cascade` and
the Sprint Y-DK retrospective §4 for the full empirical context.

All observations are returned as ``list[Observation]`` per
``base.Observation`` with ``yield_bps = round(rate_pct * 100)`` per
``conventions/units.md`` §Spreads — negative values preserved verbatim
(no clamp, no sign flip) so the 2015-2022 EUR-peg-defence corridor
flows through unchanged to the downstream cascade.

BULK response schema (Sprint Y-DK empirical probe; semicolon-delimited
five-column rows ``INSTRUMENT;LAND;OPGOER;TID;INDHOLD`` — e.g. the
2015-04-07 trough at -0.75 %).

Time codes use Statbank's ``YYYYMxxDxx`` format (e.g. ``2015M04D07``
== ``2015-04-07``) — converted at parse time. Missing observations
appear as the literal ``..`` token and are skipped.

Callers in the monetary-indices cascade
(:mod:`sonar.indices.monetary.builders`) treat
:class:`DataUnavailableError` from this connector as a soft fail and
fall back to FRED OECD mirror per the Sprint Y-DK cascade
(TE primary → Nationalbanken Statbank native → FRED stale-flagged).
The FRED OECD DK mirror ``IRSTCI01DKM156N`` is fresh at probe
(observation_end 2025-12-01; ~4-month lag) so the FRED slot remains a
viable last-resort — substantially better than the SE mirror's
5.5-year discontinuation.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import TYPE_CHECKING, Any, Final

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
    from datetime import date
    from pathlib import Path

log = structlog.get_logger()

__all__ = [
    "NATIONALBANKEN_CD_RATE",
    "NATIONALBANKEN_CURRENT_ACCOUNT_RATE",
    "NATIONALBANKEN_DISCOUNT_RATE",
    "NATIONALBANKEN_LENDING_RATE",
    "NATIONALBANKEN_RATES_TABLE",
    "STATBANK_BASE_URL",
    "NationalbankenConnector",
]

# Statbank DNRENTD table (Danmarks Nationalbanken daily interest rates;
# validated empirically during Sprint Y-DK pre-flight 2026-04-22).
# Public so tests + cascades can reference the codes without magic
# strings.
NATIONALBANKEN_RATES_TABLE: Final[str] = "DNRENTD"

# Active EUR-peg defence tool — certificate-of-deposit rate
# (indskudsbevisrenten). Sprint Y-DK M1 cascade consumes this as the
# native secondary behind TE primary.
NATIONALBANKEN_CD_RATE: Final[str] = "OIBNAA"
# Historical benchmark — discount rate (diskontoen). TE primary slot
# returns this instrument under DEBRDISC; exposed here for cross-
# validation but not consumed by Sprint Y-DK directly.
NATIONALBANKEN_DISCOUNT_RATE: Final[str] = "ODKNAA"
# Lending rate (udlånsrenten) — corridor ceiling. Reserved for M4
# FCI corridor consumer (CAL-DK-M4-FCI).
NATIONALBANKEN_LENDING_RATE: Final[str] = "OIRNAA"
# Current-account deposit rate (foliorenten) — corridor floor for
# overnight deposits up to the CD ceiling. Reserved for M4 FCI
# corridor consumer (CAL-DK-M4-FCI).
NATIONALBANKEN_CURRENT_ACCOUNT_RATE: Final[str] = "OFONAA"

STATBANK_BASE_URL: Final[str] = "https://api.statbank.dk/v1"


def _parse_statbank_date(token: str) -> date:
    """Parse a Statbank ``YYYYMxxDxx`` token into a date.

    Examples: ``2015M04D07`` → ``date(2015, 4, 7)``,
    ``2026M04D21`` → ``date(2026, 4, 21)``.

    Raises :class:`ValueError` on a malformed token; callers in this
    module catch and skip the row.
    """
    if len(token) != 10 or token[4] != "M" or token[7] != "D":
        msg = f"Statbank time token not in YYYYMxxDxx form: {token!r}"
        raise ValueError(msg)
    return datetime.strptime(token, "%YM%mD%d").date()  # noqa: DTZ007 — token is naive by design


class NationalbankenConnector:
    """L0 connector for Danmarks Nationalbanken via the Statbank.dk public API.

    Statbank is public + scriptable — no auth, no anti-bot gate (Sprint
    Y-DK empirical probe 2026-04-22). Observation extraction goes
    through ``POST /v1/data`` with a JSON body specifying the table +
    variables + format. We use ``format=BULK`` (semicolon-delimited
    CSV) because BULK supports the wildcard ``Tid=["*"]`` selector for
    full-history pulls without paging, while ``JSONSTAT`` enforces a
    smaller observation-count ceiling per request.

    Slot in cascade: **secondary** behind TE primary for DK monetary
    inputs (see :func:`build_m1_dk_inputs`). Returns results in the
    generic ``Observation`` shape so the builder resampler can consume
    them unchanged — critically, **negative values flow through
    verbatim** (no clamp, no sign flip) to preserve the 2015-2022
    Nationalbanken EUR-peg-defence corridor that Sprint Y-DK's
    ``DK_NEGATIVE_RATE_ERA_DATA`` cascade flag annotates.
    """

    BASE_URL: Final[str] = STATBANK_BASE_URL
    CACHE_NAMESPACE: Final[str] = "nationalbanken_statbank"
    CONNECTOR_ID: Final[str] = "nationalbanken"

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
                "User-Agent": "SONAR/2.0 (monetary-cascade; contact hugocondesa@pm.me)",
                "Accept": "text/csv, application/json",
            },
        )

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=30),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _fetch_raw(
        self,
        instrument: str,
    ) -> str:
        """POST to ``/v1/data`` with a BULK extract for ``(DNRENTD, instrument, *)``.

        Returns the raw semicolon-delimited CSV body. Statbank's BULK
        endpoint requires explicit ``LAND`` selection (``"DK"`` is the
        only valid value for the Nationalbanken-hosted DN tables) and
        the ``Tid=["*"]`` wildcard for the full history.
        """
        url = f"{self.BASE_URL}/data"
        body: dict[str, Any] = {
            "table": NATIONALBANKEN_RATES_TABLE,
            "format": "BULK",
            "lang": "en",
            "variables": [
                {"code": "INSTRUMENT", "values": [instrument]},
                {"code": "LAND", "values": ["DK"]},
                {"code": "OPGOER", "values": ["E"]},
                {"code": "Tid", "values": ["*"]},
            ],
        }
        r = await self.client.post(url, json=body)
        r.raise_for_status()
        return r.text

    async def fetch_series(
        self,
        instrument: str,
        start: date,
        end: date,
    ) -> list[Observation]:
        """Return parsed observations for ``(instrument, start, end)``. Cached 24h.

        Empty payload, all-unparseable, or HTTP error raise
        :class:`DataUnavailableError`; upstream cascade callers treat
        that as soft-fail and fall back to FRED OECD mirror per the
        Sprint Y-DK cascade contract.

        ``instrument`` is one of the four Statbank ``DNRENTD``
        INSTRUMENT codes (``OIBNAA`` / ``ODKNAA`` / ``OIRNAA`` /
        ``OFONAA``); see module docstring for semantics.
        """
        cache_key = f"{self.CACHE_NAMESPACE}:{instrument}:{start.isoformat()}:{end.isoformat()}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            log.debug("nationalbanken.cache_hit", instrument=instrument)
            return list(cached)

        try:
            csv_text = await self._fetch_raw(instrument)
        except (httpx.HTTPError, RetryError) as exc:
            msg = f"Nationalbanken Statbank instrument={instrument!r} HTTP error: {exc}"
            raise DataUnavailableError(msg) from exc

        if not csv_text.strip():
            msg = f"Nationalbanken Statbank returned empty payload: instrument={instrument!r}"
            raise DataUnavailableError(msg)

        # BULK schema: INSTRUMENT;LAND;OPGOER;TID;INDHOLD
        reader = csv.DictReader(io.StringIO(csv_text), delimiter=";")
        out: list[Observation] = []
        for row in reader:
            raw_date = (row.get("TID") or "").strip()
            raw_value = (row.get("INDHOLD") or "").strip()
            if not raw_date or not raw_value or raw_value == "..":
                continue
            try:
                obs_date = _parse_statbank_date(raw_date)
                value_pct = float(raw_value)
            except (TypeError, ValueError):
                continue
            if obs_date < start or obs_date > end:
                continue
            out.append(
                Observation(
                    country_code="DK",
                    observation_date=obs_date,
                    tenor_years=0.01,
                    # round() preserves sign for negative rates:
                    # -0.75 % → -75 bps without clamp.
                    yield_bps=round(value_pct * 100),
                    source="NATIONALBANKEN",
                    source_series_id=instrument,
                )
            )
        if not out:
            msg = f"Nationalbanken Statbank instrument={instrument!r}: no parseable rows in window"
            raise DataUnavailableError(msg)
        out.sort(key=lambda o: o.observation_date)
        self.cache.set(cache_key, out, ttl=DEFAULT_TTL_SECONDS)
        log.info("nationalbanken.fetched", instrument=instrument, n=len(out))
        return out

    async def fetch_policy_rate(self, start: date, end: date) -> list[Observation]:
        """Nationalbanken policy rate — series :data:`NATIONALBANKEN_CD_RATE` (OIBNAA).

        This is the certificate-of-deposit rate (indskudsbevisrenten)
        — Nationalbanken's active EUR-peg defence tool. Returns the
        canonical daily series the monetary cascade consumes as the
        DK native secondary behind TE primary.

        Named ``fetch_policy_rate`` to stay consistent with the GB /
        JP / CA / AU / NZ / CH / NO / SE cascade vocabulary
        (``fetch_bank_rate`` / ``fetch_ocr`` / ``fetch_cash_rate`` /
        ``fetch_policy_rate`` — the M1 cascade slot is the same
        regardless of country label). Note that this returns the CD
        rate, **not** the discount rate (which is what TE returns
        under ``DEBRDISC``); see module docstring §"Source-instrument
        divergence" for the empirical context.
        """
        return await self.fetch_series(NATIONALBANKEN_CD_RATE, start, end)

    async def fetch_discount_rate(self, start: date, end: date) -> list[Observation]:
        """Nationalbanken discount rate — series :data:`NATIONALBANKEN_DISCOUNT_RATE`.

        Historical benchmark (diskontoen); not the active policy
        instrument. Exposed for cross-validation against TE primary
        (which returns this same series under ``DEBRDISC``); not
        consumed by Sprint Y-DK directly.
        """
        return await self.fetch_series(NATIONALBANKEN_DISCOUNT_RATE, start, end)

    async def fetch_lending_rate(self, start: date, end: date) -> list[Observation]:
        """Nationalbanken lending rate — series :data:`NATIONALBANKEN_LENDING_RATE`.

        Corridor ceiling (udlånsrenten). Reserved for future M4 FCI
        corridor consumer (CAL-DK-M4-FCI).
        """
        return await self.fetch_series(NATIONALBANKEN_LENDING_RATE, start, end)

    async def fetch_current_account_rate(self, start: date, end: date) -> list[Observation]:
        """Nationalbanken current-account deposit rate — series ``OFONAA``.

        Corridor floor (foliorenten) — overnight deposits with
        Nationalbanken up to the CD ceiling. Reserved for future M4
        FCI corridor consumer (CAL-DK-M4-FCI).
        """
        return await self.fetch_series(NATIONALBANKEN_CURRENT_ACCOUNT_RATE, start, end)

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()
