"""Banque de France L0 connector — FR sovereign yield curve scaffold (DEFERRED).

Sprint D pilot (Week 10 Day 1+, 2026-04-22) scoped this connector as the
first national-CB integration for EA periphery curves, mirroring the
:class:`~sonar.connectors.bundesbank.BundesbankConnector` pattern. The
Commit 1 pre-flight probe fired HALT trigger 0
(``docs/planning/week10-sprint-d-fr-bdf-brief.md`` §5) — all four
fallback data paths failed to provide a ≥ 6-tenor daily FR sovereign
yield curve:

* **BdF legacy SDMX-JSON REST** ``https://webstat.banque-france.fr/ws_wsfr/rest/data/``:
  HTTP 404 on every probe. The endpoint was decommissioned when BdF
  migrated ``webstat.banque-france.fr`` to the OpenDatasoft platform
  (mid-2024 — last ``Taux_indicatifs_et_OAT_Archive`` publication date
  2024-07-11 aligns with the migration window).
* **BdF OpenDatasoft explore API** ``https://webstat.banque-france.fr/api/explore/v2.1/catalog/datasets``:
  catalog exposes a single dataset (``tableaux_rapports_preetablis``)
  which embeds one yield-related file — ``Taux_indicatifs_et_OAT_Archive.csv``.
  Content: end-of-period monthly (not daily), 8 tenors {1M, 3M, 6M, 9M,
  12M, 2Y, 5Y, 30Y}, **no 10Y**, marked "Archive" with publication
  frozen at 2024-07-11. Unfit for ``daily_curves`` both on frequency
  (monthly vs daily) and tenor completeness (10Y benchmark absent).
* **Agence France Trésor (AFT) public portal** ``https://www.aft.gouv.fr/``:
  HTTP 403 behind Cloudflare managed-challenge (``cf-mitigated: challenge``).
  Programmatic fetch blocked without interactive browser flow; not
  viable for headless pipelines.
* **TE ``fetch_fr_yield_curve_nominal``**: never shipped (Sprint CAL-138
  empirically confirmed FR exposes ``GFRN10:IND`` = 10Y-only Bloomberg
  symbol via ``/markets/historical``; below ``MIN_OBSERVATIONS = 6`` for
  NSS fit; FR is absent from :data:`sonar.connectors.te.TE_YIELD_CURVE_SYMBOLS`).
* **FRED OECD mirror** ``IRLTLT01FRM156N``: 10Y only, monthly frequency.

The brief's §9 fallback hierarchy (BdF → AFT → TE → FRED) is exhausted.
No viable sub-monthly ≥ 6-tenor source for FR sovereign yields exists
on the public data plane as of the probe date. FR consequently remains
on the EA-AAA aggregate proxy fallback in downstream overlays
(ERP / CRP / rating-spread / expected-inflation) until either (a) BdF
restores a per-tenor daily feed through its OpenDatasoft portal,
(b) SONAR provisions a licensed feed (Bloomberg / Refinitiv / FactSet),
or (c) Sprint D's successor re-probes AFT behind a browser-automation
shim. Each option is tracked under the updated ``CAL-CURVES-FR-BDF``
backlog entry and the shared umbrella opened by this sprint.

This module ships as a **documentation-first scaffold**. It preserves
the :class:`sonar.connectors.base.BaseConnector` interface so future
work can drop in real fetch logic without a breaking API change, and
it surfaces the empirical finding at connector-read time — any attempt
to dispatch FR through this connector raises
:class:`~sonar.overlays.exceptions.InsufficientDataError` with a
pointer to ``CAL-CURVES-FR-BDF`` and the probe date, matching the
Sprint A precedent for :class:`~sonar.connectors.ecb_sdw.EcbSdwConnector`
periphery handling.

References:

* ``docs/planning/week10-sprint-d-fr-bdf-brief.md`` §2 pre-flight, §5 HALT-0.
* ``docs/planning/retrospectives/week10-sprint-curves-fr-bdf-report.md``
  — retrospective with full probe matrix.
* ``docs/adr/ADR-0009-national-cb-connectors-ea-periphery.md`` — pattern
  lessons for IT-BDI / ES-BDE / PT-BPSTAT / NL-DNB follow-on sprints.
* ``docs/backlog/calibration-tasks.md`` CAL-CURVES-FR-BDF (BLOCKED).
* ``src/sonar/connectors/bundesbank.py`` — DE reference implementation
  (functional analog that future FR work would mirror).
* ``src/sonar/connectors/ecb_sdw.py`` — Sprint A periphery-stub precedent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import structlog

from sonar.connectors.base import BaseConnector, Observation
from sonar.overlays.exceptions import InsufficientDataError

if TYPE_CHECKING:
    from datetime import date
    from pathlib import Path

log = structlog.get_logger()

# OpenDatasoft explore catalog root — kept as a forward-reference for
# when BdF restores a daily per-tenor feed (the URL resolves today but
# exposes only the monthly archive dataset per the probe). Future
# implementation would layer dataflow-specific paths under this root
# once a suitable dataset is published.
BDF_BASE_URL: Final = "https://webstat.banque-france.fr/api/explore/v2.1"

# User-Agent string mirrors the BdF pattern documented in the brief
# (§4 Commit 1 template). Applied to future live requests; no HTTP
# traffic issued in the current scaffold path.
BDF_USER_AGENT: Final = "SONAR/2.0 (curves; https://github.com/hugocondesa-debug/sonar-engine)"

# CAL item tracking the FR sovereign-curve gap. The pointer is surfaced
# in the :class:`BanqueDeFranceConnector` error messages so operators
# reading pipeline logs land on the backlog entry in one lookup.
FR_CAL_POINTER: Final = "CAL-CURVES-FR-BDF"

# Probe date recorded in module-level doc + error messages. Pinned as a
# constant so the operator sees "this was last checked on X" at
# ``pytest -v`` output + structlog warnings.
BDF_PROBE_DATE: Final = "2026-04-22"

# Empirical probe findings summarised for downstream error messages.
# Short-form list; the module docstring carries the full narrative.
BDF_PROBE_FINDINGS: Final[tuple[str, ...]] = (
    "BdF legacy SDMX REST (ws_wsfr/rest/data) HTTP 404 — decommissioned",
    "BdF OpenDatasoft catalog exposes only monthly archive (stopped 2024-07-11)",
    "AFT (www.aft.gouv.fr) Cloudflare-challenged (HTTP 403) to headless clients",
    "TE FR yield curve = GFRN10:IND 10Y-only (<MIN_OBSERVATIONS=6)",
    "FRED OECD mirror IRLTLT01FRM156N = 10Y monthly only",
)


class BanqueDeFranceConnector(BaseConnector):
    """FR sovereign-curve scaffold — raises :class:`InsufficientDataError` on fetch.

    The connector preserves the :class:`BaseConnector` contract so the
    pipeline dispatcher can instantiate it unconditionally (no optional
    ``None`` branch), but every fetch method short-circuits with a
    deferral message. Switching to a functional implementation is a
    methods-only change once a viable data source lands — the public
    surface, constructor signature, and exception taxonomy are frozen
    by this scaffold.

    Pattern analog: :class:`~sonar.connectors.ecb_sdw.EcbSdwConnector`
    periphery handling (Sprint A 2026-04-22 precedent) — the connector
    exists and is wired through the dispatcher, but the fetch path
    raises ``InsufficientDataError`` with a CAL pointer until the
    probe-blocking condition is resolved.
    """

    BASE_URL: Final = BDF_BASE_URL
    USER_AGENT: Final = BDF_USER_AGENT

    def __init__(self, cache_dir: str | Path, timeout: float = 30.0) -> None:
        # Constructor signature mirrors BundesbankConnector so the pipeline
        # can construct via the same keyword idiom; ``cache_dir`` +
        # ``timeout`` are accepted but unused until live fetch lands.
        self._cache_dir = str(cache_dir)
        self._timeout = timeout

    async def fetch_series(
        self,
        series_id: str,
        start: date,  # noqa: ARG002 — scaffold; symmetric signature with real impl
        end: date,  # noqa: ARG002 — scaffold; symmetric signature with real impl
    ) -> list[Observation]:
        """Deferred per :data:`FR_CAL_POINTER` — see module docstring.

        Raises :class:`InsufficientDataError` regardless of
        ``series_id`` / ``start`` / ``end`` because the empirical probe
        found no viable per-tenor daily FR source. The exception text
        cites the probe date + CAL pointer so operators can map pipeline
        log noise onto the backlog entry without grep'ing source.
        """
        msg = _deferral_message(
            scope=f"fetch_series(series_id={series_id!r})",
        )
        raise InsufficientDataError(msg)

    async def fetch_yield_curve_nominal(
        self,
        country: str,
        observation_date: date,  # noqa: ARG002 — scaffold; matches real-impl signature
    ) -> dict[str, Observation]:
        """Deferred per :data:`FR_CAL_POINTER` — see module docstring.

        Accepts only ``country='FR'`` (raises :class:`ValueError` for
        any other code — the connector is single-country by design,
        mirroring the Bundesbank DE-only contract). For FR, always
        raises :class:`InsufficientDataError` with the probe-finding
        narrative until the data gap resolves.
        """
        if country.upper() != "FR":
            msg = (
                "BanqueDeFranceConnector only supports country='FR'; "
                f"got {country!r}. Use the country-specific connector for other codes."
            )
            raise ValueError(msg)
        msg = _deferral_message(scope="fetch_yield_curve_nominal")
        raise InsufficientDataError(msg)

    async def fetch_yield_curve_linker(
        self,
        country: str,
        observation_date: date,  # noqa: ARG002 — scaffold; matches real-impl signature
    ) -> dict[str, Observation]:
        """Deferred per :data:`FR_CAL_POINTER` — see module docstring.

        OATei (inflation-indexed OAT) linker coverage is nominally the
        best-in-class among EA periphery members (full tenor spectrum
        1998+), but the nominal-curve data gap blocks any real-curve
        composition regardless of linker quality. Raises
        :class:`InsufficientDataError` symmetrically with
        :meth:`fetch_yield_curve_nominal` until the nominal path is
        restored.
        """
        if country.upper() != "FR":
            msg = (
                "BanqueDeFranceConnector only supports country='FR'; "
                f"got {country!r}. Use the country-specific connector for other codes."
            )
            raise ValueError(msg)
        msg = _deferral_message(scope="fetch_yield_curve_linker")
        raise InsufficientDataError(msg)

    async def aclose(self) -> None:
        """No-op for scaffold — no HTTP client or cache handle to release."""


def _deferral_message(*, scope: str) -> str:
    """Compose the stock deferral message shared by every fetch method."""
    findings = "; ".join(BDF_PROBE_FINDINGS)
    return (
        f"BanqueDeFranceConnector.{scope} deferred per {FR_CAL_POINTER} "
        f"(Week 10 Sprint D pilot pre-flight {BDF_PROBE_DATE}): {findings}. "
        f"FR overlays remain on the EA-AAA proxy fallback until the "
        f"national-CB data gap resolves — see "
        f"docs/planning/retrospectives/week10-sprint-curves-fr-bdf-report.md."
    )
