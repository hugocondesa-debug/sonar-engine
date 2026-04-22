"""Banco de España L0 connector — ES sovereign yield curve scaffold (DEFERRED).

Sprint G combined pilot (Week 10 Day 2, 2026-04-22) executed the ES
probe in parallel with the Banca d'Italia probe
(:mod:`sonar.connectors.banca_ditalia`). The ES probe outcome differs
from IT in a material way: the Banco de España **BIE REST API**
(``https://app.bde.es/bierest/resources/srdatosapp/``) is live,
public, and returns Spanish sovereign yield data — but only at
**monthly** frequency. Per ADR-0009's decision matrix this maps to
the "HTTP 200 + non-daily" scaffold path, not the "HTTP 4xx /
deprecated" scaffold path. The connector is therefore deferred on
frequency grounds rather than reachability grounds, and the unblock
condition is "BdE publishes daily Bono secondary-market yields"
rather than "BdE publishes any API at all" — a meaningfully softer
bar than the IT / FR HALT-0 outcomes.

Pre-flight probe matrix (Commit 1, Sprint G, 2026-04-22):

* **BDEstad portal SDMX** ``https://www.bde.es/webbde/es/estadis/infoest/bde_datasetAux.html``:
  HTTP 301 permanent redirect to ``https://www.bde.es/wbe/es/estadisticas/``
  (the portal has migrated to the ``/wbe/`` tree). The old
  ``/webbde/`` path used by academic references is deprecated.
* **Banco de España BIE REST** ``https://app.bde.es/bierest/resources/srdatosapp/``:
  HTTP 200 JSON API, gzip-compressed payloads. Operators call
  ``listaSeries?idioma=es&series=<code>&rango={30M,<year>}`` with
  known series codes to retrieve metadata + time series values. The
  ``favoritas`` endpoint returns last-value-only.
  **No public catalog endpoint exists** — series codes must be
  discovered from the BIEST interactive JS application or from the
  CSV files attached to the statistical-table chapters published at
  ``https://www.bde.es/webbe/es/estadisticas/compartido/datos/csv/<chapter>.csv``.

  The statistical-table surface catalogues 11 Spanish sovereign
  yield series across the BE_22_6 (Letras del Tesoro, 6 tenor
  buckets from 3M to 12M) and BE_22_7 (Bonos y Obligaciones del
  Estado, 5 tenors {3Y, 5Y, 10Y, 15Y, 30Y}) chapters. All 11 series
  publish at **monthly** frequency (CSV suffix ``.M`` + declared
  ``FRECUENCIA=MENSUAL``; confirmed through the REST API for
  ``D_1NBBO320`` ES long-term Rendimiento de la Deuda Pública — 31
  observations in a 30-month window, code ``codFrecuencia=M``).
  This is below the daily cadence the ``daily_curves`` pipeline
  requires — daily queries would surface the same month-end value
  for ~30 consecutive days, defeating the intraday signal the
  pipeline exists to capture.

* **Tesoro Público** ``https://www.tesoro.es/``: resolves to
  ``192.187.20.74`` but the HTTPS handshake fails (HTTP 000 in
  ~116 ms, no server hello completion). The Treasury portal is
  effectively unreachable from the VPS data plane. Even if TLS were
  resolvable, Tesoro publishes auction bulletins as PDF/XLS
  attached to press-release pages — not a pipeline-viable surface.
* **ECB SDW ``FM`` dataflow ES override**
  ``https://data-api.ecb.europa.eu/service/data/FM?filter=REF_AREA:ES``:
  HTTP 200 returning the EA-aggregate monetary-policy rates
  (deposit facility, MRO, marginal lending) — no ES-specific
  sovereign-yield series. Same finding as IT. Sprint A 2026-04-22
  confirmed.
* **FRED OECD mirror** ``IRLTLT01ESM156N``: HTTP 200, 555 monthly
  observations of ES 10Y sovereign yield. Single-tenor, monthly
  frequency. Below ``MIN_OBSERVATIONS=6`` and frequency-mismatched
  against the daily pipeline cadence.

The brief's §2 fallback hierarchy (BDEstad / BdE REST / Tesoro /
ECB SDW / FRED) is exhausted for the daily-curve use-case. The
BdE BIE surface **would** support a monthly-resolution Spanish
sovereign curve (11-tenor), which is a different product from
``daily_curves``; integrating it without degrading the pipeline
would require either (a) extending ``daily_curves`` to accept a
monthly-resolution connector family with a forward-fill policy
(scope expansion beyond Sprint G), (b) building a parallel
``monthly_curves`` pipeline (Phase 2+ architecture), or (c) waiting
for BdE to publish daily Bono yields (no announced roadmap).
Each option is tracked under the updated ``CAL-CURVES-ES-BDE``
backlog entry.

This module ships as a **documentation-first scaffold** per the
Sprint D precedent (:mod:`sonar.connectors.banque_de_france`) and
the Sprint G twin (:mod:`sonar.connectors.banca_ditalia`). It
preserves the :class:`sonar.connectors.base.BaseConnector`
interface so future work can drop in real fetch logic without a
breaking API change, and it surfaces the empirical finding at
connector-read time — any attempt to dispatch ES through this
connector raises :class:`~sonar.overlays.exceptions.InsufficientDataError`
with a pointer to ``CAL-CURVES-ES-BDE`` and the probe date.

References:

* ``docs/planning/week10-sprint-g-it-es-curves-brief.md`` §2 pre-flight,
  §5 HALT-0.
* ``docs/planning/retrospectives/week10-sprint-curves-it-es-report.md``
  — retrospective with full ES probe matrix.
* ``docs/adr/ADR-0009-national-cb-connectors-ea-periphery.md`` — pattern
  lessons extended with the "HTTP 200 + non-daily" scaffold sub-case.
* ``docs/backlog/calibration-tasks.md`` ``CAL-CURVES-ES-BDE`` (BLOCKED).
* ``src/sonar/connectors/banque_de_france.py`` — Sprint D "HTTP 4xx +
  OpenDatasoft-monthly" scaffold precedent.
* ``src/sonar/connectors/banca_ditalia.py`` — Sprint G IT twin (strict
  HALT-0; no reachable REST surface).
* ``src/sonar/connectors/bundesbank.py`` — DE reference implementation
  (functional analog that future ES work would mirror if BdE publishes
  a daily surface).
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

# Banco de España BIE REST API root — kept as a forward-reference in
# case BdE publishes a daily Bono secondary-market yield series. The
# endpoint is live and public today (HTTP 200), but every Spanish
# sovereign yield series exposed through it is declared at monthly
# frequency (``codFrecuencia='M'``). Future implementation would use
# this URL plus per-tenor series codes once the frequency gap closes.
BDE_BASE_URL: Final = "https://app.bde.es/bierest/resources/srdatosapp/"

# User-Agent string mirrors the Bundesbank + BdF + BdI pattern. Applied
# to future live requests; no HTTP traffic issued in the current
# scaffold path.
BDE_USER_AGENT: Final = "SONAR/2.0 (curves; https://github.com/hugocondesa-debug/sonar-engine)"

# CAL item tracking the ES sovereign-curve gap. The pointer is
# surfaced in the :class:`BancoEspanaConnector` error messages so
# operators reading pipeline logs land on the backlog entry in one
# lookup.
ES_CAL_POINTER: Final = "CAL-CURVES-ES-BDE"

# Probe date recorded in module-level doc + error messages. Pinned as
# a constant so the operator sees "this was last checked on X" at
# ``pytest -v`` output + structlog warnings.
BDE_PROBE_DATE: Final = "2026-04-22"

# Empirical probe findings summarised for downstream error messages.
# Short-form list; the module docstring carries the full narrative.
# Note: unlike IT + FR scaffolds, ES finding #2 records a *working*
# API path — the block is frequency, not reachability.
BDE_PROBE_FINDINGS: Final[tuple[str, ...]] = (
    "BDEstad portal /webbde/ HTTP 301 — migrated to /wbe/ tree",
    "BdE BIE REST (app.bde.es/bierest) HTTP 200 but ES Bono yields MONTHLY only",
    "BIE catalogues 11-tenor ES Bonos/Letras (BE_22_6 + BE_22_7) all monthly",
    "Tesoro Público www.tesoro.es HTTPS TLS handshake fails (HTTP 000)",
    "ECB SDW FM REF_AREA:ES returns EA-aggregate monetary-policy rates only",
    "FRED OECD mirror IRLTLT01ESM156N = 10Y monthly only",
)


class BancoEspanaConnector(BaseConnector):
    """ES sovereign-curve scaffold — raises :class:`InsufficientDataError` on fetch.

    The connector preserves the :class:`BaseConnector` contract so the
    pipeline dispatcher can instantiate it unconditionally (no optional
    ``None`` branch), but every fetch method short-circuits with a
    deferral message. Switching to a functional implementation is a
    methods-only change once BdE publishes a daily Bono secondary-
    market yield surface — the public interface, constructor
    signature, and exception taxonomy are frozen by this scaffold.

    Pattern analog: :class:`~sonar.connectors.banque_de_france.BanqueDeFranceConnector`
    (Sprint D pilot 2026-04-22) — the connector exists and is
    pipeline-dispatchable, but the fetch path raises
    ``InsufficientDataError`` with a CAL pointer until the
    probe-blocking condition is resolved. ES differs from FR on the
    underlying cause: FR is HTTP 4xx (decommissioned), ES is HTTP 200
    non-daily (monthly).
    """

    BASE_URL: Final = BDE_BASE_URL
    USER_AGENT: Final = BDE_USER_AGENT

    def __init__(self, cache_dir: str | Path, timeout: float = 30.0) -> None:
        # Constructor signature mirrors BundesbankConnector + BdF / BdI
        # scaffolds so the pipeline can construct via the same keyword
        # idiom; ``cache_dir`` + ``timeout`` are accepted but unused
        # until live fetch lands.
        self._cache_dir = str(cache_dir)
        self._timeout = timeout

    async def fetch_series(
        self,
        series_id: str,
        start: date,  # noqa: ARG002 — scaffold; symmetric signature with real impl
        end: date,  # noqa: ARG002 — scaffold; symmetric signature with real impl
    ) -> list[Observation]:
        """Deferred per :data:`ES_CAL_POINTER` — see module docstring.

        Raises :class:`InsufficientDataError` regardless of
        ``series_id`` / ``start`` / ``end`` because the empirical probe
        found the BdE BIE surface publishes only monthly Spanish
        sovereign yields, below the daily pipeline cadence. The
        exception text cites the probe date + CAL pointer so operators
        can map pipeline log noise onto the backlog entry without
        grep'ing source.
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
        """Deferred per :data:`ES_CAL_POINTER` — see module docstring.

        Accepts only ``country='ES'`` (raises :class:`ValueError` for
        any other code — the connector is single-country by design,
        mirroring the Bundesbank DE-only + BdF FR-only + BdI IT-only
        contracts). For ES, always raises :class:`InsufficientDataError`
        with the probe-finding narrative until the frequency gap
        resolves (BdE publishes daily Bono yields) or the pipeline
        gains a parallel monthly-cadence path.
        """
        if country.upper() != "ES":
            msg = (
                "BancoEspanaConnector only supports country='ES'; "
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
        """Deferred per :data:`ES_CAL_POINTER` — see module docstring.

        Bonos indexados (ES inflation-linked bonds) coverage is the
        weakest among EA-periphery peers (post-2014 issuance with
        ≤ 3 tenors typically priced at any given time; Sprint A
        finding). Even if the nominal path resolved via a daily
        surface, the linker path would likely emit ``LINKER_UNAVAILABLE``
        for historical runs pre-2014 and ``ES_LINKER_PARTIAL`` for
        post-2014 runs. Nominal-curve data gap blocks any real-curve
        composition regardless of linker quality; this scaffold raises
        :class:`InsufficientDataError` symmetrically with
        :meth:`fetch_yield_curve_nominal`.
        """
        if country.upper() != "ES":
            msg = (
                "BancoEspanaConnector only supports country='ES'; "
                f"got {country!r}. Use the country-specific connector for other codes."
            )
            raise ValueError(msg)
        msg = _deferral_message(scope="fetch_yield_curve_linker")
        raise InsufficientDataError(msg)

    async def aclose(self) -> None:
        """No-op for scaffold — no HTTP client or cache handle to release."""


def _deferral_message(*, scope: str) -> str:
    """Compose the stock deferral message shared by every fetch method."""
    findings = "; ".join(BDE_PROBE_FINDINGS)
    return (
        f"BancoEspanaConnector.{scope} deferred per {ES_CAL_POINTER} "
        f"(Week 10 Sprint G pre-flight {BDE_PROBE_DATE}): {findings}. "
        f"ES overlays remain on the EA-AAA proxy fallback until BdE "
        f"publishes daily Bono yields or the pipeline gains a monthly "
        f"cadence path — see "
        f"docs/planning/retrospectives/week10-sprint-curves-it-es-report.md."
    )
