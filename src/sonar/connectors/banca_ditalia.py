"""Banca d'Italia L0 connector — IT sovereign yield curve scaffold (DEFERRED).

Sprint G combined pilot (Week 10 Day 2, 2026-04-22) executed the
first of the four ADR-0009 successor probes in parallel with the
Banco de España probe (:mod:`sonar.connectors.banco_espana`). The
Commit 1 pre-flight probe fired HALT trigger 0
(``docs/planning/week10-sprint-g-it-es-curves-brief.md`` §5) — all
five fallback data paths failed to provide a ≥ 6-tenor daily IT
sovereign yield curve:

* **ECB legacy SDMX REST** ``https://sdw-wsrest.ecb.europa.eu/service/data/BDS``:
  HTTP 000 (connection timeout). The ``sdw-wsrest`` host is the
  decommissioned gateway that migrated to ``data-api.ecb.europa.eu``
  in 2023; the ``BDS`` (Banca d'Italia) dataflow is not re-published
  on the new endpoint. No IT-specific SDMX data plane at ECB.
* **Banca d'Italia Infostat** ``https://infostat.bancaditalia.it/``:
  HTTP 200 on the landing page (a JavaScript single-page application).
  The advertised application-to-application REST / SDMX 2.1 subdomain
  ``a2a.infostat.bancaditalia.it`` — referenced throughout the BdI
  technical documentation — resolves as **NXDOMAIN** from public DNS,
  along with ``sdmx.bancaditalia.it`` and ``bip.bancaditalia.it``.
  The Infostat portal exposes no programmatic REST surface: the
  ``/inquiry/api/1.0/dataflow`` probe returned HTTP 404 behind a
  generic "risorsa protetta" HTML error page, and the SPA requires
  an interactive session to drive queries. Infostat is consequently
  a browser-only statistical portal as of 2026-04-22, not a
  pipeline-viable HTTP surface.
* **MEF / Tesoro Italiano** ``https://www.dt.mef.gov.it/it/debito_pubblico/titoli_di_stato/``:
  HTTP 200 HTML landing page for debt publications; no REST/CSV API
  surface discoverable. ``https://www.mef.gov.it/opendata/`` returns
  HTTP 404. MEF publishes auction bulletins as PDF/XLS attached to
  press-release pages, incompatible with a headless pipeline without
  a bespoke scraper per publication cadence.
* **ECB SDW ``FM`` dataflow IT override**
  ``https://data-api.ecb.europa.eu/service/data/FM?filter=REF_AREA:IT``:
  HTTP 200 but the returned ``dataSets`` carry the EA-aggregate
  monetary-policy rates (deposit facility ≈ ``-0.25`` / MRO ≈ ``2.00``
  / marginal lending) — **no IT sovereign-yield series**. The filter
  is ignored by the API for this dataflow because IT is absent from
  the ``REF_AREA`` codelist projected onto ``FM``. Sprint A 2026-04-22
  probe reached the same conclusion; re-probe Sprint G confirms the
  gap persists. The adjacent ``IRS`` dataflow publishes IT data but
  with a single ``MATURITY_CAT='CI'`` (EMU convergence-criterion
  long-term interest rate, monthly, 10Y equivalent) — below
  ``MIN_OBSERVATIONS=6`` for NSS fit.
* **FRED OECD mirror** ``IRLTLT01ITM156N``: HTTP 200, 420 monthly
  observations of IT 10Y sovereign yield. Single-tenor, monthly
  frequency. Below ``MIN_OBSERVATIONS=6`` and frequency-mismatched
  against the daily pipeline cadence.

The brief's §2 fallback hierarchy (BDS SDMX / Infostat / MEF / ECB
SDW / FRED) is exhausted. No viable sub-monthly ≥ 6-tenor source
for IT sovereign yields exists on the public data plane as of the
probe date. IT consequently remains on the EA-AAA aggregate proxy
fallback in downstream overlays (ERP / CRP / rating-spread /
expected-inflation) until either (a) Banca d'Italia publishes a
public SDMX/REST surface for BTP yields, (b) SONAR provisions a
licensed feed (Bloomberg / Refinitiv / FactSet), or (c) a browser-
automation shim drives the Infostat SPA to extract CSV downloads.
Each option is tracked under the updated ``CAL-CURVES-IT-BDI``
backlog entry.

This module ships as a **documentation-first scaffold** per the
Sprint D precedent (:mod:`sonar.connectors.banque_de_france`). It
preserves the :class:`sonar.connectors.base.BaseConnector` interface
so future work can drop in real fetch logic without a breaking API
change, and it surfaces the empirical finding at connector-read
time — any attempt to dispatch IT through this connector raises
:class:`~sonar.overlays.exceptions.InsufficientDataError` with a
pointer to ``CAL-CURVES-IT-BDI`` and the probe date.

References:

* ``docs/planning/week10-sprint-g-it-es-curves-brief.md`` §2 pre-flight,
  §5 HALT-0.
* ``docs/planning/retrospectives/week10-sprint-curves-it-es-report.md``
  — retrospective with full IT probe matrix.
* ``docs/adr/ADR-0009-national-cb-connectors-ea-periphery.md`` — pattern
  lessons extended with IT + ES empirical findings.
* ``docs/backlog/calibration-tasks.md`` ``CAL-CURVES-IT-BDI`` (BLOCKED).
* ``src/sonar/connectors/banque_de_france.py`` — Sprint D scaffold precedent.
* ``src/sonar/connectors/bundesbank.py`` — DE reference implementation
  (functional analog that future IT work would mirror if BdI publishes a
  public SDMX surface).
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

# Infostat landing page — kept as a forward-reference in case Banca
# d'Italia restores or publishes an application-to-application REST /
# SDMX surface. The URL resolves today (HTTP 200) but serves only an
# interactive single-page-application; no programmatic payload is
# exposed at the root or known subpaths.
BDI_BASE_URL: Final = "https://infostat.bancaditalia.it/"

# User-Agent string mirrors the Bundesbank + BdF pattern documented
# in ADR-0009 successor sprint templates. Applied to future live
# requests; no HTTP traffic issued in the current scaffold path.
BDI_USER_AGENT: Final = "SONAR/2.0 (curves; https://github.com/hugocondesa-debug/sonar-engine)"

# CAL item tracking the IT sovereign-curve gap. The pointer is
# surfaced in the :class:`BancaDItaliaConnector` error messages so
# operators reading pipeline logs land on the backlog entry in one
# lookup.
IT_CAL_POINTER: Final = "CAL-CURVES-IT-BDI"

# Probe date recorded in module-level doc + error messages. Pinned as
# a constant so the operator sees "this was last checked on X" at
# ``pytest -v`` output + structlog warnings.
BDI_PROBE_DATE: Final = "2026-04-22"

# Empirical probe findings summarised for downstream error messages.
# Short-form list; the module docstring carries the full narrative.
BDI_PROBE_FINDINGS: Final[tuple[str, ...]] = (
    "ECB legacy SDMX sdw-wsrest (BDS dataflow) HTTP 000 — host decommissioned",
    "BdI Infostat API subdomains (a2a, sdmx, bip) NXDOMAIN — no public REST surface",
    "MEF / Tesoro Italiano www HTML-only; opendata/ HTTP 404",
    "ECB SDW FM REF_AREA:IT returns EA-aggregate monetary-policy rates only",
    "ECB SDW IRS IT = single MATURITY_CAT 'CI' 10Y monthly (<MIN_OBSERVATIONS=6)",
    "FRED OECD mirror IRLTLT01ITM156N = 10Y monthly only",
)


class BancaDItaliaConnector(BaseConnector):
    """IT sovereign-curve scaffold — raises :class:`InsufficientDataError` on fetch.

    The connector preserves the :class:`BaseConnector` contract so the
    pipeline dispatcher can instantiate it unconditionally (no optional
    ``None`` branch), but every fetch method short-circuits with a
    deferral message. Switching to a functional implementation is a
    methods-only change once a viable data source lands — the public
    surface, constructor signature, and exception taxonomy are frozen
    by this scaffold.

    Pattern analog: :class:`~sonar.connectors.banque_de_france.BanqueDeFranceConnector`
    (Sprint D pilot 2026-04-22) — the connector exists and is
    pipeline-dispatchable, but the fetch path raises
    ``InsufficientDataError`` with a CAL pointer until the
    probe-blocking condition is resolved.
    """

    BASE_URL: Final = BDI_BASE_URL
    USER_AGENT: Final = BDI_USER_AGENT

    def __init__(self, cache_dir: str | Path, timeout: float = 30.0) -> None:
        # Constructor signature mirrors BundesbankConnector + BdF scaffold
        # so the pipeline can construct via the same keyword idiom;
        # ``cache_dir`` + ``timeout`` are accepted but unused until live
        # fetch lands.
        self._cache_dir = str(cache_dir)
        self._timeout = timeout

    async def fetch_series(
        self,
        series_id: str,
        start: date,  # noqa: ARG002 — scaffold; symmetric signature with real impl
        end: date,  # noqa: ARG002 — scaffold; symmetric signature with real impl
    ) -> list[Observation]:
        """Deferred per :data:`IT_CAL_POINTER` — see module docstring.

        Raises :class:`InsufficientDataError` regardless of
        ``series_id`` / ``start`` / ``end`` because the empirical probe
        found no viable per-tenor daily IT source. The exception text
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
        """Deferred per :data:`IT_CAL_POINTER` — see module docstring.

        Accepts only ``country='IT'`` (raises :class:`ValueError` for
        any other code — the connector is single-country by design,
        mirroring the Bundesbank DE-only + BdF FR-only contracts).
        For IT, always raises :class:`InsufficientDataError` with the
        probe-finding narrative until the data gap resolves.
        """
        if country.upper() != "IT":
            msg = (
                "BancaDItaliaConnector only supports country='IT'; "
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
        """Deferred per :data:`IT_CAL_POINTER` — see module docstring.

        BTP€i (inflation-indexed BTP) linker coverage is nominally
        strong among EA-periphery peers (4-tenor coverage 5Y / 10Y /
        20Y / 30Y post-2003), but the nominal-curve data gap blocks
        any real-curve composition regardless of linker quality.
        Raises :class:`InsufficientDataError` symmetrically with
        :meth:`fetch_yield_curve_nominal` until the nominal path is
        restored.
        """
        if country.upper() != "IT":
            msg = (
                "BancaDItaliaConnector only supports country='IT'; "
                f"got {country!r}. Use the country-specific connector for other codes."
            )
            raise ValueError(msg)
        msg = _deferral_message(scope="fetch_yield_curve_linker")
        raise InsufficientDataError(msg)

    async def aclose(self) -> None:
        """No-op for scaffold — no HTTP client or cache handle to release."""


def _deferral_message(*, scope: str) -> str:
    """Compose the stock deferral message shared by every fetch method."""
    findings = "; ".join(BDI_PROBE_FINDINGS)
    return (
        f"BancaDItaliaConnector.{scope} deferred per {IT_CAL_POINTER} "
        f"(Week 10 Sprint G pre-flight {BDI_PROBE_DATE}): {findings}. "
        f"IT overlays remain on the EA-AAA proxy fallback until the "
        f"national-CB data gap resolves — see "
        f"docs/planning/retrospectives/week10-sprint-curves-it-es-report.md."
    )
