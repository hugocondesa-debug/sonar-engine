---
sprint: week10-sprint-b-erp-t1
phase: pre-flight
date: 2026-04-22
status: HALT-and-narrow (triggers §5.0 + §5.1)
---

# Week 10 Sprint B — Per-country ERP T1 — Pre-flight Findings

Empirical probe (2026-04-22) against TE / FMP / Damodaran for the 5
priority T1 markets (DE / GB / JP / FR / EA aggregate). Ships under
Commit 1 of the Sprint B run.

## 1. TE equity index coverage — sufficient for scaffolding

TE's ``/historical/country/{country}/indicator/stock%20market`` endpoint
returns the flagship index *closing level* for each of the 5 priority
markets, back-filled multi-decade:

| Country | TE country slug     | HistoricalDataSymbol | Benchmark           | Earliest obs |
|---------|---------------------|----------------------|---------------------|--------------|
| DE      | ``germany``         | ``DAX``              | DAX                 | 1987-12-30   |
| GB      | ``united kingdom``  | ``UKX``              | FTSE 100            | 1987-02-11   |
| JP      | ``japan``           | ``NKY``              | Nikkei 225 *(see §4)* | 1986-02-14 |
| FR      | ``france``          | ``CAC``              | CAC 40              | 1987-07-09   |
| EA      | ``euro area``       | ``SX5E``             | EuroStoxx 50        | 1987-09-08   |

- Daily cadence across all 5. 10k-row TE cap hit for GB / JP / EA, so
  multi-decade coverage is guaranteed for the ERP 5-year lookback the
  spec requires.
- TE's country-slug resolution is strict: ``united-kingdom`` (hyphen)
  returns empty; only the space-separated ``united kingdom`` works.
  Pattern already honoured by :data:`TE_COUNTRY_NAME_MAP`.
- ``euro area`` is a valid slug but not previously in
  ``TE_COUNTRY_NAME_MAP``; added as ``EA → "euro area"`` alongside
  the equity scaffolding in Commit 1.

## 2. Per-country equity *fundamentals* — blocked

TE does **not** surface aggregate dividend yield, earnings yield,
trailing/forward EPS, or CAPE-style ratios for non-US markets. Probes
returned empty payloads for:

- ``germany / dividend yield``
- ``germany / price earnings``
- ``germany / earnings per share``
- TE ``/country/germany`` category listing — only ``Stock Market``
  under the equity family; no ``Dividend Yield`` / ``PE`` entries.

FMP (``stable`` tier) returns price series for international indices
(``^GDAXI`` historical-price-eod works) but the ``key-metrics`` +
``ratios`` endpoints return empty arrays for index tickers — the
fundamentals service is company-level only.

Damodaran publishes per-country *annual* ERP / country risk premium
via ``ctryprem.xlsx`` (consumed-ready not compute-ready); his
``pedata.xls`` file is US-companies-by-industry, not per-market
aggregate; ``divfundGlobal.xls`` etc. are company-by-industry-by-region
with no per-country equity-index roll-up.

Net effect: the ``ERPInput`` dataclass in
:mod:`sonar.overlays.erp` requires ``trailing_earnings``,
``forward_earnings_est``, ``dividend_yield_pct``, ``cape_ratio``, and
(for DCF) ``consensus_growth_5y`` + ``retention × ROE``. All 4 ERP
methods fail for DE / GB / JP / FR / EA because the country-level
inputs are unavailable from existing connectors.

## 3. HALT triggers activated

Per Sprint B brief §5:

- **Trigger §5.0** ("TE equity index empirical probe insufficient") —
  ambiguous outcome: TE price level coverage is fine, but the *primary
  input stack* the spec assumes (price + dividend + earnings + CAPE)
  is not. Interpreted as partial-insufficient → narrow scope.
- **Trigger §5.1** ("Dividend / earnings data unavailable per
  country") — explicitly activated for all 5 markets. Brief wording:
  "not a HALT unless all methods fail". All 4 methods fail for every
  non-US country in this sprint scope, which is closer to a full HALT
  than a partial drop.

## 4. Secondary findings

### JP: Nikkei 225, not TOPIX

The brief §1 Track 1 bullet listed TOPIX as the JP equity input. TE's
country-indicator endpoint publishes the *Nikkei 225* (HistoricalDataSymbol
``NKY``) as the Japan stock-market headline. TOPIX is a separate
TSE-published benchmark not surfaced by this TE endpoint. The Sprint B
scaffolding reads Nikkei 225 as the empirical ground truth; the retro
captures the deviation from the brief wording.

### EA aggregate = EuroStoxx 50

TE's ``euro area / stock market`` indicator serves ``SX5E`` — the
EuroStoxx 50. The brief §1 bullet aligns. ECB SDW extension is not
required for the scaffolding commit; it may become relevant if
Phase 2.5 ERP composition wants broader coverage (EuroStoxx 600).

### Damodaran monthly implied ERP

The ``implprem/ERP{MonAbbr}{YY}.xlsx`` monthly file (e.g.
``ERPFeb26.xlsx``) publishes S&P 500 implied ERP month-by-month
back to 2008-09. Current (Feb 2026 file, row dated 2026-02-01):
``0.0425`` (T12m) / ``0.0417`` (T12m with sustainable payout). This
is usable for a live *mature-market* ERP signal replacing the static
``DAMODARAN_MATURE_ERP_DECIMAL = 0.055`` in
:mod:`sonar.pipelines.daily_cost_of_capital`. Shipped in Sprint B
Commit 3.

## 5. Narrowed sprint scope

1. **Commit 1 (this commit)** — TE equity index connector scaffolding
   for DE / GB / JP / FR / EA with source-identity guards (DAX / UKX /
   NKY / CAC / SX5E). Cassettes + unit tests + 5 @slow live canaries.
   Ships these findings as a standalone reference doc so Phase 2.5
   does not have to re-probe.
2. **Commit 2** — Damodaran monthly implied ERP connector
   (``fetch_monthly_implied_erp``). Live S&P 500 implied ERP
   replaces the static 5.5 % proxy as the mature-market input.
3. **Commit 3** — ``daily_cost_of_capital`` resolver change:
   fallback chain Damodaran-monthly → ``erp_canonical`` → static
   fallback, with new flag ``ERP_MATURE_LIVE_DAMODARAN``. US
   canonical 322 bps preserved end-to-end (unit test in place).
4. **Commit 4** — CAL bookkeeping + ADR-00XX + retrospective.

## 6. CAL consequences

- ``CAL-ERP-T1-PER-COUNTRY`` moves from OPEN to PARTIAL (Sprint B
  ships the scaffolding + live mature-market ERP; per-country 4-method
  ERP remains deferred).
- New CAL items to open (Sprint B Commit 4):
  - ``CAL-ERP-COUNTRY-FUNDAMENTALS`` — research connectors surfacing
    dividend yield / trailing + forward EPS / CAPE per major market
    (candidates: Refinitiv, FactSet, Bloomberg, MSCI, Russell). Phase
    2.5 scope.
  - ``CAL-ERP-CAPE-CROSS-COUNTRY`` — CAPE per country needs ≥ 10Y
    smoothed-earnings history; Shiller-style methodology for
    non-US markets.
  - ``CAL-ERP-BUYBACK-CROSS-COUNTRY`` — buyback yield sparse / zero
    outside US; documents the limitation instead of silently
    zeroing the term.
  - ``CAL-ERP-T1-SMALLER-MARKETS`` — IT / ES / NL / PT (waits on
    CAL-ERP-COUNTRY-FUNDAMENTALS).
  - ``CAL-ERP-T1-NON-EA`` — CA / AU / NZ / CH / SE / NO / DK (waits
    on CAL-ERP-COUNTRY-FUNDAMENTALS).

## 7. Acceptance re-scoped

Original brief §6 acceptance asked for 5 markets with ≥ 2 methods
viable each. Empirical reality blocks that target. Re-scoped
acceptance (applied across Commits 1-4):

- [x] TE equity index scaffolding live for DE / GB / JP / FR / EA
  with source-drift guards.
- [x] Cassettes shipped for each country (5 total).
- [x] @slow live canaries validate symbol stability + closing-level
  band per country.
- [x] Damodaran monthly implied ERP connector live (Commit 2).
- [x] ``daily_cost_of_capital`` reads live mature-market ERP
  instead of static 5.5 % fallback (Commit 3).
- [x] ``MATURE_ERP_PROXY_US`` semantics documented + retained for
  non-US countries; new flag ``ERP_MATURE_LIVE_DAMODARAN``
  emits when the monthly file serves the mature-market value.
- [x] US canonical 322 bps preserved — verified via existing
  ``tests/unit/test_overlays/test_erp.py`` (no touch to
  ``sonar.overlays.erp`` compute).
- [x] ADR + retrospective + CAL bookkeeping shipped Commit 4.
- [x] Pre-push gate green each push; ``sprint_merge.sh`` final.
