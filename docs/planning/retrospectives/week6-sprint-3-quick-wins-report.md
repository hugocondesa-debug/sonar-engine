# Week 6 Sprint 3 — Connector Quick Wins

**Brief:** `docs/planning/week6-sprint-3-quick-wins-brief.md`
**Duration:** ~2.5h (2026-04-20)
**Commits:** 7 (C2 + C3 combined into one commit per tight-hunks precedent)
**Status:** SPRINT CLOSED — 4 CAL resolutions shipped

---

## 1. Summary

Fastest sprint of Week 6. Closed three open CAL items (072 BIS rename,
073 put/call delisted, 093 Conference Board CC) plus surfaced +
closed one new CAL (102 UMich-5Y inflation delisted). Each resolution
is independent; they share only the TE-probe empirical-validation
pattern.

E4 US availability on live data went from 6/13 (Sprint 2a baseline)
to 9/13 (post-Sprint 6.1 ISM + NFIB wiring) to **9/13 with higher-
quality sourcing on the CB and UMich-5Y slots** post-Quick-Wins.
F4 US went from 4/5 (put/call absent) to **5/5 when Yahoo `^CPC`
cooperates** (5/5 confirmed in `test_f4_live_integration`; skipped
in the uplift smoke due to Yahoo rate-limiting on a cold cache).

Operational lesson: the Sprint 1 Week 6 closure of CAL-093 was based
on a wrong premise — TE's "Consumer Confidence" feed is **Conference
Board**, not UMich (empirical probe on the historical endpoint
returns `HistoricalDataSymbol=CONCCONF`). The Sprint 1 inference
relied on the catalogue-endpoint `Source` field which is misleading.
Documented in the backlog re-closure note + source-identity guards
now land with every TE wrapper.

## 2. Commits

| # | SHA | Title | Gate |
|---|-----|-------|------|
| 1 | `667f581` | fix(connectors): BIS property dataflow WS_LONG_PP → WS_SPP (CAL-072) | green |
| 2+3 | `4b6e037` | feat(connectors): TE Conference Board CC + UMich 5Y inflation wrappers | green |
| 4 | `bd76354` | feat(indices): E4 Sentiment TE-primary for CB CC + UMich 5Y | green |
| 5 | `9fe7d78` | feat(connectors): Yahoo Finance ^CPC put/call ratio (CAL-073) | green |
| 6 | `62942c2` | feat(indices): F4 Positioning put/call live via Yahoo ^CPC | green |
| 7 | `c00fbef` | test(integration): E4 + F4 quality uplift post-Quick-Wins | green |
| 8 | _this doc_ | docs(planning): retrospective + CAL closures | pending |

Pre-push gate (`ruff format --check + ruff check + mypy full-project
+ pytest --no-cov`) green before every push. No `--no-verify`.

## 3. CAL resolutions

| CAL | Status | Resolution |
|-----|--------|-----------|
| 072 | CLOSED | BIS dataflow renamed WS_LONG_PP → WS_SPP in `bis.py`; xfail removed; canary passes live |
| 073 | CLOSED | Yahoo `^CPC` via new `yahoo_finance.py` generic connector; F4 live smoke passes 5/5 |
| 093 | RE-OPENED + RE-CLOSED | Original Sprint 1 closure wrong-premise; TE `consumer confidence` is actually Conference Board (CONCCONF); `fetch_conference_board_cc_us` wrapper with source-identity guard |
| 102 | OPENED + CLOSED | MICHM5YM5 FRED delisted (surfaced Sprint 2a); TE `michigan 5 year inflation expectations` → USAM5YIE |

All four CAL items are resolved in the same sprint — no new follow-ups.

## 4. Commit details

### C1 — BIS WS_SPP fix (CAL-072)

- Single find/replace in `bis.py`: `DATAFLOW_WS_LONG_PP` → `DATAFLOW_WS_SPP`;
  `source_tag BIS_WS_LONG_PP` → `BIS_WS_SPP`; `__all__` updated.
- Existing cassette was already captured from WS_SPP during Sprint 1
  (stopgap), so no re-record needed.
- `tests/unit/test_connectors/test_bis_property.py` assertions updated;
  xfail decorator removed from live canary; canary now passes with real
  PT property-index data.

### C2 + C3 — TE CB CC + UMich 5Y wrappers (CAL-093, CAL-102)

Combined into one commit (`4b6e037`) because their code hunks share
the same module constant block, dataclass field, and parser update
line — splitting would be artificial noise. Precedent: Sprint 1 Week 6
folded c4 telemetry into c1 for similar reasons.

Key shipments:
- `TEIndicatorObservation.historical_data_symbol` field (new).
- Constants: `TE_INDICATOR_MICHIGAN_5Y_INFLATION`,
  `TE_EXPECTED_SYMBOL_CONFERENCE_BOARD_CC`,
  `TE_EXPECTED_SYMBOL_MICHIGAN_5Y_INFLATION`.
- Wrappers: `fetch_conference_board_cc_us`, `fetch_michigan_5y_inflation_us`.
- Source-drift guard on both: raises `DataUnavailableError("source drift")`
  when the first row's `HistoricalDataSymbol` doesn't start with the
  expected identifier. Captures the operational lesson from Sprint 1.

### C4 — E4 builder TE-primary (CAL-093 completion)

Deviation from brief literal documented in commit body: brief said
"if FRED None, try TE", but `fred.fetch_conference_board_confidence_us`
and `fred.fetch_umich_5y_inflation_us` return proxy data (OECD CLI
stale, Cleveland Fed model) so the literal fallback never triggered.
Swapped priority: **TE primary when provided, FRED fallback**. This
turns CAL-093 from cosmetic to real-quality — the CB slot now carries
actual Conference Board values, not the 2024-01-frozen OECD proxy.

### C5 — Yahoo `^CPC` put/call (CAL-073)

New module `yahoo_finance.py` designed as a forward-looking generic
connector (future-proof for more Yahoo symbols). Existing
`move_index.py` left untouched per HALT #5 discipline. Fully typed
schema-drift guards + 12 unit tests + 1 live canary (which degrades
gracefully when Yahoo rate-limits).

Cassette note: Yahoo returned 429 during the initial probe, so the
unit-test cassette is **synthetic** (64 daily closes in [0.55, 1.25]).
Live canary verifies the real path when rate-limit relaxes.

### C6 — F4 Positioning wiring

Test-side change only: `tests/integration/test_f4_live_integration.py`
swapped `CboeConnector.fetch_put_call` (broken path — FRED PUTCLSPX
delisted) for `YahooFinanceConnector.fetch_put_call_ratio_us`. No
shared `builders.py` in `src/sonar/indices/financial/`; F4Inputs
assembly is inline in integration tests. Live smoke green in 20s;
components_available == 5/5.

### C7 — Uplift smoke

New test file `tests/integration/test_sentiment_positioning_uplift.py`:

- `test_e4_us_post_quick_wins`: live PASS, 9/13 components,
  `TE_FALLBACK_{CB_CC, UMICH_5Y, ISM_MFG, ISM_SVC, NFIB}` all present.
- `test_f4_us_post_quick_wins`: SKIPPED (Yahoo 429 on cold cache).
  Same test passed in `test_f4_live_integration` when Yahoo had been
  warmed earlier in the sprint.

## 5. E4 + F4 quality delta

| Cycle / country | Pre-sprint | Post-sprint | Delta | Notes |
|-----------------|-----------|-------------|-------|-------|
| E4 US | 9/13 (Sprint 6.1 post-ISM/NFIB) | 9/13 (same count, higher quality) | +0 count / ↑↑ quality | CB now real Conference Board (CONCCONF) vs stale OECD CLI; UMich-5Y now real UMich survey (USAM5YIE) vs Cleveland-Fed model |
| E4 DE | 5/13 (Sprint 6.1) | 5/13 | +0 | no DE-specific CAL addressed this sprint |
| F4 US | 4/5 (put/call missing) | 5/5 (Yahoo ^CPC live, when rate-limit allows) | +1 | OVERLAY_MISS flag gone |
| F1 property-gap | blocked (WS_LONG_PP 404) | unblocked (WS_SPP) | +1 input | BIS canary no longer xfail |

## 6. Operational lesson: always verify TE source identity

Sprint 1 Week 6 closed CAL-093 on the premise that TE's US
"Consumer Confidence" was UMich-sourced. The evidence was the
`Source="University of Michigan"` field on TE's catalogue endpoint.
This sprint probed the **historical** endpoint and found
`HistoricalDataSymbol="CONCCONF"` — the actual Conference Board
series. The catalogue-endpoint `Source` field was misleading
(possibly reflecting a page-layout provenance field, not the data
identity).

Mitigation landed this sprint:
- Every new TE wrapper validates `HistoricalDataSymbol` against a
  pre-declared expected value.
- Mismatch raises `DataUnavailableError("source drift")` rather
  than silently substituting a different series.

## 7. HALT triggers

- **#1 (BIS WS_SPP still 404)**: not fired — rename resolved cleanly.
- **#2 (TE CC non-CONCCONF symbol)**: not fired — probe confirmed CONCCONF.
- **#3 (UMich-5Y unexpected)**: not fired — returned USAM5YIE as expected.
- **#4 (Yahoo `^CPC` unavailable)**: fired SOFTLY — endpoint rate-limited
  during the sprint (HTTP 429 on cold cache). Mitigation: cassette
  built synthetically, live canary declared slow + tolerates empty
  response. Brief §10 fallback pattern followed.
- **#5 (move_index refactor breaks tests)**: not fired — move_index
  intentionally left untouched.
- **#6 (F4 wiring location)**: resolved trivially — no builders.py
  in financial/; inline assembly in integration tests.
- **#7 (CAL-093 manual edit)**: fired as expected — backlog re-wrote
  the closure with documented correction.
- **#8 (concurrent calibration-tasks.md edit)**: not fired — Ingestion
  Omnibus completed (`84c7259`) before Sprint 3 opened backlog.
- **#9 (pre-push gate)**: not fired.
- **#10 (TE rate limit)**: not triggered — sprint consumed ~6 TE
  calls (well inside 15-call target, leaves 985/month buffer).

## 8. Deviations from brief

- **Commit count**: 7 effective commits, not 7-9. C2 + C3 folded
  into one (tight hunks; precedent).
- **C4 priority-swap**: TE becomes primary for CB + UMich-5Y rather
  than secondary fallback per brief literal. Reason: FRED proxies
  always succeed today, so the literal brief wiring never triggered.
  Priority swap turns the resolution from cosmetic to real-quality.
  Documented in commit body + retro.
- **Yahoo cassette synthetic**: Yahoo rate-limited during the sprint,
  forcing a synthetic cassette for unit-test coverage. Live canary
  handles rate-limit degradation cleanly.
- **E4 count target ≥ 11**: actual post-sprint 9/13. Brief's 11/13
  target was based on the assumption that CB + UMich-5Y were MISSING
  pre-sprint; in reality they were present via FRED proxies, so the
  count-delta is 0 — the *quality* delta is what matters (real CB
  data, real UMich-5Y). Brief target was a count-miscount, not a
  scope miss.

## 9. Concurrency report

Ingestion Omnibus (Week 6 Sprint 2b) finished before this sprint
opened — retrospective commit `84c7259` was visible at start time
and no additional pushes from that lane landed during Sprint 3.
Zero push-race conditions. `calibration-tasks.md` rebase-merge
protocol was declared but not needed.

## 10. New backlog

Zero new items. CAL-102 opened + closed in the same sprint.

## 11. Sprint readiness downstream

- E4 US data quality now materially production-grade (5 of 6 sourced
  live: UMich, CB, UMich-5Y, ISM Mfg, ISM Svc, NFIB — only IPO stays
  placeholder).
- F4 US is a full 5/5 stack for the first time (pending Yahoo rate-
  limit cooperation on daily production runs; tenacity retry covers
  normal load).
- F1 property-gap is unblocked for 7-T1 countries (BIS WS_SPP live).
- FCS Bubble Warning condition-3 (F1 input) now armable.
- MSC (Week 6 Sprint 2) continues to work on whatever M-stack rows
  are persisted; nothing in this sprint touched MSC directly.

*End of retrospective. Sprint CLOSED 2026-04-20.*
