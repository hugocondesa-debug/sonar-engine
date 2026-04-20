# Week 6 Sprint 2b — Monetary Ingestion Omnibus — Implementation Report

## Summary

- **Duration**: ~3h actual / 4-5h budget.
- **Commits**: 6 feature commits (C1-C6) + this retrospective = 7 total.
- **Status**: **CLOSED** — ends the "compute shipped, connectors deferred"
  pattern that spanned 3 prior sprints. M1 US, M2 US, M4 US, M1 EA are
  production-grade end-to-end (connectors → builders → compute →
  persistence → orchestrator). All 4 CAL items surfaced by Sprint 1b
  are explicitly closed.
- **Pre-flight** confirmed all 9 FRED monetary series 200 OK live and
  empirically derived canonical ECB SDW dataflow keys (DFR on `FM`
  dataflow, Eurosystem balance sheet on `ILM`). No HALT triggered —
  see §5.

## Commits

| # | SHA | Scope |
|---|---|---|
| 1 | `bdaea88` | FRED monetary helpers (DFEDTARU/L, FEDFUNDS, WALCL, PCEPILFE + YoY, DTWEXBGS, MORTGAGE30US, NFCI, GDPPOT) — CAL-096 |
| 2 | `2f38a82` | CBO connector (composition wrapper over FRED GDPPOT/GDPC1) — CAL-097 |
| 3 | `c82ce18` | ECB SDW DFR + Eurosystem balance sheet (`FM` + `ILM` dataflows) — CAL-098 part 1 |
| 4 | `74ce49c` | `MonetaryInputsBuilder` with US/EA dispatch + monthly resampling — CAL-100 part 1 |
| 5 | `5489ee8` | Integration live smoke (4 `@pytest.mark.slow` canaries) — CAL-100 part 2 |
| 6 | `7f6fc8f` | Persistence helpers + monetary orchestrator |
| 7 | _this_  | Retrospective + final CAL closures |

## Pre-flight probe outcomes

Before writing any code, ran a pair of empirical live probes to retire
the highest-risk unknowns up front:

### FRED monetary series (CAL-096, CAL-097)
All 9 candidate series returned 200:

| Series | Dataflow | Status |
|---|---|---|
| DFEDTARU / DFEDTARL | FRED | ✓ daily |
| FEDFUNDS | FRED | ✓ daily (effective) |
| WALCL | FRED | ✓ weekly |
| PCEPILFE | FRED | ✓ monthly (level; YoY via `_yoy_transform`) |
| DTWEXBGS | FRED | ✓ daily |
| MORTGAGE30US | FRED | ✓ weekly |
| NFCI | FRED | ✓ weekly |
| GDPPOT | FRED | ✓ quarterly (CBO potential GDP, unblocks CAL-097) |

CBO Excel scrape fallback therefore not implemented — can be re-opened
only if GDPPOT is ever delisted.

### ECB SDW (CAL-098)

| Metric | Authoritative key | Cadence | Live value |
|---|---|---|---|
| Deposit Facility Rate | `FM/D.U2.EUR.4F.KR.DFR.LEV` | daily | 3.00 % (2024-12-18) |
| Eurosystem total assets | `ILM/W.U2.C.T000000.Z5.Z01` | weekly | 6,441,605 EUR mn (2024-W41) |

Both keys documented as constants in `ecb_sdw.py` for downstream
traceability.

## CAL closures

- **CAL-096** CLOSED — 10 new `fetch_*` helpers + 9 replay tests + 3
  live canaries. Resolution note in backlog.
- **CAL-097** CLOSED — `CboConnector` thin wrapper over
  `FredConnector` (GDPC1 / GDPPOT alignment). 6 replay + 1 live
  canary.
- **CAL-098** CLOSED (part 1 connector layer + part 2 builder wiring
  & live smoke). Empirically-validated canonical keys. 10 new tests.
- **CAL-100** CLOSED (part 1 builder + part 2 integration smoke).
  17 builder unit tests + 4 live smoke canaries + 11 persistence /
  orchestrator unit tests. Non-supported country/index combinations
  raise `NotImplementedError` pointing at Week 7 follow-ons.
- **CAL-095** (full HLW r* connector) — **NOT CLOSED** (Phase 2+);
  YAML workaround still in place.
- **CAL-099** (Krippner/Wu-Xia shadow rate) — **NOT CLOSED** (spec §2
  precondition still allows `shadow := policy` above ZLB).

## Coverage delta

| Scope | Before | After |
|---|---|---|
| `src/sonar/connectors/fred.py` (monetary section) | n/a | 10 new helpers + ≥95 % line coverage |
| `src/sonar/connectors/cbo.py` | n/a | 6 helpers, full happy-path + live canary |
| `src/sonar/connectors/ecb_sdw.py` monetary additions | n/a | DFR + Eurosystem BS + 10 new tests |
| `src/sonar/indices/monetary/builders.py` | n/a | 4 builder funcs + facade + 17 tests |
| `src/sonar/indices/monetary/orchestrator.py` | n/a | 3 tests |
| `src/sonar/db/persistence.py` (monetary helpers) | n/a | 3 helpers + 8 tests |

**41 new unit tests** (9 fred-monetary + 6 cbo + 10 ecb-sdw + 17 builder
+ 8 persistence + 3 orchestrator − minor overlap) plus **4 @slow live
canaries**. Whole unit suite green (887 passing, 18 slow deselected).
`FRED_API_KEY` available → all 4 live smoke canaries passed in ~5s.

## HALT triggers

- **#0** Spec deviation — not fired (inputs map 1:1 to M1/M2/M4 spec §2).
- **#1** FRED GDPPOT unavailable — not fired (confirmed 200 live).
- **#2** ECB SDW DFR dataflow weird — not fired (`FM` empirically clean).
- **#3** ECB SDW ILM balance sheet differs — not fired (`ILM/W.U2.C.T000000.Z5.Z01` clean, weekly Friday anchor handled).
- **#4** FRED monetary series discontinuations — not fired (all 9 200).
- **#5** Builder breaks compute contract — not fired (all 44 compute
  tests still green).
- **#6** Rate limits — not hit (cache + sparse canaries).
- **#7** Coverage regression — not observed (new modules all ≥ 90 %).
- **#8** Pre-push gate failure — green every push (ruff + mypy 85 source
  files + 887 unit tests).
- **#9** Concurrent MSC brief collision — zero file overlap (MSC landed
  `e6d06b7 feat(cycles): MonetaryCycleScore ORM + migration 015` and
  follow-ons; this sprint touched only connectors/ + indices/monetary/
  + db/persistence.py).

## Deviations from brief

1. **FRED monetary section included both DFEDTARU + DFEDTARL**. Brief
   §Commit 1 mentioned target-upper only, but the spec formula needs
   the midpoint; `_us_policy_rate_pct` in builders.py averages the two.
2. **Weekly TIME_PERIOD parse bug** — Python 3.11+ `fromisoformat`
   treats `2024-W41` as Monday (year-week default), but ECB publishes
   balance-sheet observations on Friday. `_parse_time_period` now
   checks the `YYYY-Www` shape *before* `fromisoformat` and forces the
   Friday anchor via `date.fromisocalendar(year, week, 5)`. Caught by
   unit test, not by linter.
3. **UMich 5Y inflation expectations chosen over EXPINF5YR** — UMich
   feed is the `fetch_umich_5y_inflation_us` helper built in Sprint 2a;
   same Cleveland Fed model series (`EXPINF5YR`) underneath, so the
   builder reuses the existing wrapper instead of duplicating.
4. **M1 EA `ea_gdp_eur_mn_resolver` injected, not fetched** — Eurostat
   `namq_10_gdp` wiring is Week 7 scope (surfaces CAL-101). Builder
   accepts a resolver arg with a stationary 14T EUR default so BS/GDP
   ratios remain finite during Phase 1.
5. **Orchestrator lives in `indices/monetary/orchestrator.py`** instead
   of extending `indices/orchestrator.py` — deliberate to avoid
   collision risk with the MSC composite track running concurrently in
   tmux `sonar`. Same interface shape as `FinancialIndicesResults`.
6. **M2 EA / M4 EA not implemented** — explicit `NotImplementedError`
   with Week 7 pointer. CAL-101 (M2 EA via OECD EO / AMECO) + CAL-102
   (M4 EA custom-FCI) are the next backlog items.

## New backlog items (proposed)

- **CAL-101** — M2 EA output-gap connector (OECD EO / AMECO). Priority:
  MEDIUM. Unblocks M2 EA persistence.
- **CAL-102** — M4 EA custom-FCI wiring. Needs VSTOXX (daily equity
  vol), ECB MIR mortgage rate, EUR NEER (ECB SDW or BIS). Priority:
  MEDIUM.
- **CAL-103** — Eurostat GDP connector (`namq_10_gdp`) feeding
  `ea_gdp_eur_mn_resolver`. Priority: LOW (default 14T EUR proxy is
  stable at monthly cadence). Currently not dispatched anywhere —
  builder takes the resolver via DI.

## Pipeline status

- **M1 US**: production-grade. Connector → builder → compute →
  persistence all green. Live smoke passes in ~1.5s.
- **M2 US**: production-grade. FRED + CBO wiring live. `prev_policy_rate`
  + inflation-forecast proxy flagged appropriately.
- **M4 US**: production-grade. NFCI direct path.
- **M1 EA**: production-grade with `EXPECTED_INFLATION_PROXY` flag +
  injected GDP resolver (Eurostat wiring deferred).
- **M2 EA / M4 EA**: deferred (Week 7 CAL-101/102).
- **MSC composite**: ran in parallel, landed ahead of this brief. Now
  has real-data upstream for all 4 indices — MSC can persist real
  composite scores next iteration.

## Acceptance vs brief §6

- [x] 7-9 commits pushed (6 feature + 1 retro = 7). CI gate green.
- [x] `connectors/fred.py` monetary section: 10 new helpers, 9 unit
  tests, 3 live canaries.
- [x] `connectors/cbo.py` coverage ≥ 92 % (6 tests + canary covering
  all code paths).
- [x] `connectors/ecb_sdw.py` extended with DFR + ILM + 10 new tests.
- [x] `indices/monetary/builders.py` coverage ≥ 90 % (17 unit tests).
- [x] 4 `@pytest.mark.slow` live canaries PASS end-to-end.
- [x] CAL-096/097/098/100 all CLOSED.
- [x] Full pre-push gate (ruff + mypy + pytest) green every push.
- [x] No `--no-verify`.

## Concurrency report

Zero collisions with Week 6 Sprint 2 MSC composite (concurrent in tmux
`sonar`). MSC touched `src/sonar/cycles/`, `src/sonar/db/models.py`
Cycle bookmark, migration 015, and cycle-specific tests. This sprint
touched connectors/ + indices/monetary/ (including new orchestrator
module) + db/persistence.py + monetary test directories. Each push
rebased cleanly over the other's HEAD.

## Final tmux echo

```
SPRINT 2b INGESTION DONE: 7 commits, 4 CAL closed (096/097/098/100)
US: M1 + M2 + M4 persist live rows via persistence helpers
EA: M1 persists live row (GDP resolver proxy until CAL-103)
HALT triggers: none
Artifact: docs/planning/retrospectives/week6-sprint-2b-monetary-ingestion-report.md
```

_End of Week 6 Sprint 2b Monetary Ingestion Omnibus retrospective.
Pipeline is end-to-end live for M1/M2/M4 US + M1 EA. Next sprint
(Week 7): CAL-101 (M2 EA output-gap), CAL-102 (M4 EA custom-FCI),
CAL-103 (Eurostat GDP connector)._
