# M1 US Gap Analysis — Spec vs Implementation

Companion to [`m1-us.md`](m1-us.md). M1 US is declared complete at the
close of Phase 1 Week 7 Sprint G: **100 % of Phase 1 planned features
shipped**, and **~70-75 % of the full spec catalog implemented**. This
document catalogues the deltas and categorises open CAL items by impact
on the next milestone gates (M2 T1 Core, Phase 2+).

---

## 1. Overview

- **CAL total**: 62 entries in `docs/backlog/calibration-tasks.md`
- **CAL closed**: 21 (M1 US scope delivered)
- **CAL open**: 41, distributed as:
  - ~15 → **M2 T1 Core** scope (UK/JP, per-country ERP, EA periphery M2/M4)
  - ~15 → **Phase 2+** architectural (Postgres, L5 regimes, ops)
  - ~11 → **LOW priority** nice-to-have (calibration refinements, scraper hardening)

---

## 2. Gap categories

### Category A — M1 US Critical (blocks milestone declaration)

**None remaining.** Every item flagged as M1 US critical at the start
of Week 7 landed in Sprints E + F + G. The milestone is declarable.

### Category B — M1 US Nice-to-Have (quality improvements, unblocks follow-ons)

- **CAL-054** — E2 Leading full 8-component composite (current shape
  has 3 NSS-derived inputs; the 5 non-NSS components — PMI leading
  subset, HY OAS, building permits, jobless-claims slope, commodity
  deflator — were never shipped as the spec envisions them because
  `E2Inputs` dataclass never grew those fields). Incremental: adding
  each component is a localised PR.
- **CAL-055** — M3 Market Expectations EP 4-component composite upgrade
  (current compute runs on nominal_5y5y + breakeven_5y5y + bc_target;
  the EP sub-score needs FOMC dots + minutes-tone signal + dissent
  count). Phase 2+ scope for true "expected-path" signal.
- **CAL-095** — Full HLW r* connector (currently hardcoded via
  `r_star_values.yaml`; quarterly manual refresh ritual). NY Fed
  weekly release ingestion.
- **CAL-099** — Krippner / Wu-Xia shadow rate connector (policy-rate
  proxy above ZLB today; only binds when US returns to ZLB territory).
- **CAL-056** — Damodaran connector HTTP / cache / aclose coverage gap.
- **CAL-061** — `daily_bis_ingestion` CLI wrapper coverage lift.
- **CAL-088** — `compute_all_economic_indices` orchestrator refactor
  (currently lives inline in `daily_economic_indices` per Sprint B
  HALT #2; externalise to `indices/economic/orchestrator.py`).

### Category C — Phase 2+ (explicitly out of Phase 1 scope)

- **L5 regime classifier** — spec undefined in Phase 0. Phase 2+ writes
  the formal regime taxonomy (6-band across all 4 cycles) + classifier
  + backtesting harness.
- **Weekly integration matrix** — spec is an empty stub; no Phase 1
  implementation.
- **L7 client outputs** — dashboards, PDF tearsheets, API layer.
  Zero Phase 1 implementation (ERP composition lives in
  `daily_cost_of_capital` but downstream consumers TBD).
- **Postgres migration** — SQLite MVP + Alembic keeps Phase 1 portable;
  Phase 2+ moves to Postgres for multi-writer ops.
- **Systemd timer / cron wiring** — ops scope; daily pipelines run
  ad-hoc today.
- **Email / webhook alerting** — interface + NullAlertSink shipped
  (Sprint G C3); delivery Phase 2+.
- **24-month production data for empirical calibration** — most
  thresholds / weights in the cycle specs are placeholders pending
  ≥ 18-24 months of live runs.

### Category D — CAL items deferred (not blockers)

**M2 T1 Core scope** (next milestone, ~15 items):

- UK + JP connector coverage (BoE + BoJ suite, FRED alt paths).
- Per-country ERP live paths (currently US only; EA / UK / JP proxy
  via `MATURE_ERP_PROXY_US` flag).
- EA periphery M2 + M4 expansion (CAL-101 + CAL-102 surfaced Sprint 2b).
- Eurostat GDP for EA BS/GDP resolver (CAL-103 surfaced Sprint 2b).
- CAL-057 `daily_erp_us` L8 pipeline dedicated file (today rides on
  `daily_cost_of_capital`).

**Calibration refinements** (~8 items):

- CAL-030 NSS β0 bounds for negative yields.
- CAL-031 NSS fixture live-fetch + §7 tolerance calibration.
- CAL-033 US real-curve direct-linker TIPS coverage.
- CAL-034 / CAL-035 NSS RMSE + xval tolerance revisions.
- CAL-037 / CAL-038 / CAL-039 / CAL-041 CRP calibration (CDS
  liquidity, vol_ratio bounds, rating-CDS divergence, distress CDS).
- CAL-042 PT-EA inflation differential per-tenor refinement.

**Connector hardening** (~6 items):

- CAL-023 US E2 LEI alternative source.
- CAL-036 TE `/markets/historical` endpoints validation.
- CAL-043 Expected-inflation connector validation (UK/JP/EM).
- CAL-081 / CAL-082 / CAL-084 / CAL-085 / CAL-087 ECS survey
  connectors (S&P PMI scraper, ISM direct, Atlanta Fed wage, EPU,
  BoJ Tankan). E4 Sentiment currently uses TE-fallback paths that are
  adequate for US / EA; direct ingestion is a quality lift, not a
  blocker.
- CAL-094 Eurostat `namq_10_pe` gap for PT employment.

---

## 3. Spec-implementation mapping

### Overlays (L2)

| Overlay | Spec compliance | Notes |
|---|---|---|
| NSS Curves | **100 %** | Full spec; 4 sibling tables (spot/zero/forwards/real); direct-linker real path live |
| ERP Daily | **100 % US**, proxy EA/UK/JP | Per-country live ERP is CAL-057-ish Week 8+ |
| CRP | **~90 %** | CDS hierarchy branch not wired (FMP connector scope pending); SOV_SPREAD + RATING branches + BENCHMARK short-circuit all live |
| Rating-Spread v0.2 | **~80 %** | Damodaran primary + in-memory agency consolidation; agency scrape forward-path lands via Sprint F live assemblers (FMP-backed). True multi-agency daily scrape is Phase 2+ |
| Expected-Inflation | **~95 %** | BEI/DERIVED/SURVEY methods all live; BEI-vs-SURVEY split in sub_indicators JSON pending CAL-113 |

### Indices (L3)

| Index | Spec compliance | Notes |
|---|---|---|
| E1 Activity | **100 %** | GDP YoY + 5 components via FRED/Eurostat |
| E2 Leading | **~40 %** (3/8) | `E2Inputs` currently has 3 NSS-derived scalars + histories; CAL-054 expands to full 8-component with PMI/OAS/permits/claims/commodities |
| E3 Labor | **~95 %** | Sahm rule + 8/10 components; Atlanta Fed wage pending CAL-084 |
| E4 Sentiment | **~70 %** (9/13) | TE-fallback paths for CB confidence + UMich 5Y inflation; ISM/NFIB direct via CAL-082 |
| L1 Credit-to-GDP Stock | **100 %** | BIS WS_TC ingestion live; z-score baseline compute full |
| L2 Credit-to-GDP Gap | **100 %** | HP-filter + Hamilton filter dual path |
| L3 Credit Impulse | **compute 100 %, live pending** | LCU input assembly is CAL-059; compute module + ORM shipped |
| L4 DSR | **compute 100 %, live pending** | Input wiring is CAL-060 |
| F1 Valuations | **~95 %** | CAPE + Buffett + ERP median + forward P/E + property gap; forward-EPS live via FMP |
| F2 Momentum | **100 %** | 5-component via FRED + FMP |
| F3 Risk Appetite | **100 %** | VIX + MOVE + HY + IG + NFCI via FRED + CBOE + Chicago Fed |
| F4 Positioning | **100 % US** | AAII + put/call (Yahoo ^CPC) + COT + margin-debt + IPO activity |
| M1 Effective Rates | **100 % US / EA** | ECB DFR + Eurosystem BS wired for EA; r* via YAML (CAL-095 full HLW pending) |
| M2 Taylor Gaps | **100 % US** | Weighted RD_raw canonical; EA deferred (CAL-101) |
| M3 Market Expectations | **~60 %** (3 components) | Live via Sprint E DB-backed reader; EP 4-component is CAL-055 |
| M4 FCI | **100 % US** | Direct NFCI path + 5-component custom backup for EA |

### Cycles (L4)

All four cycles are **100 % operational** with Policy-1 fail-mode
aggregation, regime classification (hysteresis-aware), and overlays:

| Cycle | Spec compliance | Overlay shipped |
|---|---|---|
| CCCS | **100 %** | Boom overlay active |
| FCS | **100 %** | Bubble-warning overlay active |
| MSC | **100 %** | Dilemma overlay + `COMM_SIGNAL_MISSING` re-weight (CS is Phase 2+) |
| ECS | **100 %** | Stagflation overlay (Cap 16 Trigger A) active |

### Pipelines (L8)

9 daily pipelines operational; `daily_cycles` orchestrates all 4 L4
composites; live + DB-backed paths where applicable.

---

## 4. Next milestone gates

### M2 T1 Core (immediate follow-on)

Blocks:

- **UK + JP connector suites** — BoE (yield curves + policy-rate
  trajectory), BoJ (Tankan via CAL-087, monetary operations). New
  country codes in `country_tiers.yaml` + CRP `vol_ratio` calibration.
- **EA periphery M2 + M4** — OECD EO / AMECO output-gap for M2
  (CAL-101); VSTOXX + ECB MIR mortgage for M4 EA custom-FCI
  (CAL-102).
- **Per-country ERP live paths** — Per-market ERPInput assembler for
  EA / UK / JP (replaces `MATURE_ERP_PROXY_US` flag).

### M3 Sem L7 (Phase 1 final)

Blocks:

- M2 T1 complete.
- T2/T3/T4 country expansion (AU/CA/NO/SE/CH, periphery EA, EMs).
- L5 regime classifier spec writing.
- Postgres migration planning.
- Monitoring operational (email/webhook delivery via AlertSink).

### Phase 2+ transition

Major architectural moves:

- Postgres migration for multi-writer ops.
- L5 regime classifier spec + implementation + backtesting.
- L7 output layer (API, dashboards, tearsheets).
- 18-24 months live data → empirical calibration of placeholders.
- Systemd timer / cron wiring.

---

## 5. References

- [`m1-us.md`](m1-us.md) — milestone scorecard.
- [`../backlog/calibration-tasks.md`](../backlog/calibration-tasks.md)
  — all 62 CAL items (21 closed, 41 open).
- [`../planning/retrospectives/`](../planning/retrospectives/) —
  sprint-by-sprint history (Weeks 1-7).
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md) — 9-layer graph.
- [`../ROADMAP.md`](../ROADMAP.md) — phase plan.

---

_Last updated: Week 7 Sprint G (Phase 1 close). Next update: after M2
T1 Core closes — expected UK + JP coverage + per-country ERP._
