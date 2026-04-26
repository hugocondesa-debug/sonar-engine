# Calibration tasks — backlog

Placeholders declarados em specs P3-P5 a recalibrar empiricamente quando production data atingir horizonte mínimo. Agrupados por horizonte (acção ordenada) + spec owner (rastreabilidade).

**Convenção**: cada placeholder em specs marcado `placeholder — recalibrate after Nm`. Este inventário consolida todos os placeholders catalogados com ID estável `CAL-NNN`.

**Última revisão major**: 2026-04-22 (Week 10 Day 0).
- Phase 3 reframe em torno de L7 API + Website (ver `../ROADMAP.md`).
- Phase 2.5 introduzida como bridge (L5 regimes + L6 integration + L7 infra prep).
- Country-specific sub-CALs Week 9 (CA/AU/NZ/CH/SE/NO/DK × 6-7 shapes) consolidados em 5 generic T1-expansion items (ver §Consolidated T1 expansion items).
- Forward-looking CAL items for Phase 2.5 + Phase 3 added (L5 regimes, L6 matriz 4-way / diagnostics / cross-country k_e, L7 API MCP / REST / Website, backtest harness, per-country ERP).
- Nenhum item matched deprecation categories do brief §4 Commit 7 (Streamlit dashboard / alerts MVP / PT-vertical stack / React dashboard interna) — essas scopes não tinham CAL items in-flight; roadmap remove-as-scope registada directamente em `../ROADMAP.md#Deprecated`.

CAL items catalogued per 9-layer + Phase scope. See ROADMAP.md §Phase definitions.

## Sumário

**20 itens catalogados** (inventory real via grep). SESSION_CONTEXT estimava ~40; reality revelou ~20 após exclusão de fixtures, non-requirements e duplicados.

| Horizonte | Count | Categorias |
|---|---|---|
| Recurring 3m | 1 | rating-spread anchor values |
| 12m | 1 | overlay threshold (CRP CDS liquidity) |
| 18m | 3 | overlays (CRP vol_ratio, CRP rating-CDS, rating-spread modifier weights) |
| 24m | 10 | index bands (E1-E4), cycle weights (MSC), general README (economic + monetary) |
| 60m per country | 5 | credit phase bands (L1-L4 + credit README) |

## Activação

Phase 4 "Calibração Empírica & Scale" é gate primário ([`../ROADMAP.md`](../ROADMAP.md) §Phase 4). Items individuais podem activar antes se spec owner (Hugo) tiver fundamento empírico suficiente (evidence-based, documentado em ADR ou spec bump).

## Recurring 3m — rating-spread anchor values

Única categoria recurring (não one-shot). Quarterly recalibration a partir de Moody's Annual Default Study + ICE BofA observed spreads.

| ID | Spec | Placeholder | Valor actual | Critério recalibração |
|---|---|---|---|---|
| CAL-020 | `overlays/rating-spread.md:143` | Anchor values notch→bps | notch 21→10 / 18→35 / 15→90 / 12→245 / 9→600 / 6→1325 / 3→3250 / 0→N/A (April 2026 snapshot) | Every 3m vs published spreads |

## Horizonte 12m — overlay thresholds (rápidos)

Items com ≥ 250 observações diárias em 12m, recalibráveis empiricamente cedo.

| ID | Spec | Placeholder | Valor actual | Critério recalibração |
|---|---|---|---|---|
| CAL-001 | `overlays/crp.md:39` | CDS liquidity threshold (bid-ask cutoff) | 15 bps | Distribuição empírica de bid-ask em 12m production |

## Horizonte 18m — overlay parameters

| ID | Spec | Placeholder | Valor actual | Critério recalibração |
|---|---|---|---|---|
| CAL-002 | `overlays/crp.md:41` | `vol_ratio_bounds` (σ_equity/σ_bond clamp) | (1.2, 2.5) | Distribuição empírica vol_ratio em 18m |
| CAL-003 | `overlays/crp.md:43` | `rating_cds_divergence_threshold_pct` para flag `RATING_CDS_DIVERGE` | 50% (\|cds − rating_implied\| / cds > 0.50) | Observação de false positives em 18m |
| CAL-004 | `overlays/rating-spread.md:103` | Modifier weights outlook/watch | ±0.25 / ±0.50 notches | Ex-post rating action transitions em 18m |

## Horizonte 24m — index bands + cycle weights

O horizonte dominante. 10 items: 4 index band thresholds (E1-E4), 2 cycle weights/internals (MSC), 1 index M1 classification, 1 Taylor rule ρ, 2 general READMEs (economic, monetary).

| ID | Spec | Placeholder | Valor actual | Critério recalibração |
|---|---|---|---|---|
| CAL-005 | `indices/economic/E1-activity.md:95` | Band "Recession (mild)" threshold | score 20-30 | NBER/CEPR historical alignment |
| CAL-006 | `indices/economic/E2-leading.md:103` | Band "Recession warning" threshold | score < 30 | NBER/CEPR alignment |
| CAL-007 | `indices/economic/E3-labor.md:116` | Band "Deteriorating rapidly" threshold | score < 30 | NBER/CEPR alignment + Sahm trigger events |
| CAL-008 | `indices/economic/E4-sentiment.md:125` | Band "Widespread pessimism" threshold | score < 30 | NBER/CEPR alignment |
| CAL-009 | `indices/economic/README.md:58` | Pesos ECS + thresholds gerais (umbrella) | Cap 15.6 weights (0.35/0.25/0.25/0.15) | Walk-forward backtest vs NBER/CEPR; hit-ratio ≥ 87% Pagan-Sossounov |
| CAL-010 | `indices/monetary/M1-effective-rates.md:134` | Classification bands (fixture `us_2026_04_17` sample) | "Neutral-Tight" threshold (score≈62) | Regime change events (2004-06/2013/2014/2019/2022) |
| CAL-011 | `indices/monetary/M2-taylor-gaps.md:80` | Taylor rule inertia `ρ` | 0.85 | Backtest per BC via Phase 9 harness |
| CAL-012 | `indices/monetary/README.md:77` | Pesos MSC + thresholds gerais (umbrella) | Cap 15.6 weights | Walk-forward backtest vs monetary regime changes (Fed hike/taper/easing/cut/hiking) |
| CAL-013 | `cycles/monetary-msc.md:34` | CS internal weights (dot plot / dissent / NLP) | 40/25/35 | Backtest quando CS connectors speced (P2-014) |
| CAL-014 | `cycles/monetary-msc.md:44` | MSC composite weights | `{m1:0.30, m2:0.15, m3:0.25, m4:0.20, cs:0.10}` | Walk-forward vs regime changes; Cap 15.6 hit-ratio |

## Horizonte 60m per country — credit phase bands

Dataset BIS curto (trimestral, ~30-40 anos per country mas regime changes infrequentes). 5 items.

| ID | Spec | Placeholder | Valor actual | Critério recalibração |
|---|---|---|---|---|
| CAL-015 | `indices/credit/L1-credit-to-gdp-stock.md:89` | `structural_band` per country level | `<50% sub-financialized; 50-100% intermediate; 100-150% advanced typical; 150-200% highly financialized; >200% outlier` | Distribuição per country em 5Y |
| CAL-016 | `indices/credit/L2-credit-to-gdp-gap.md:95` | Phase band thresholds | (per spec) | BIS crisis events + Moody's default study alignment |
| CAL-017 | `indices/credit/L3-credit-impulse.md:91` | State classification thresholds | (per spec) | Credit cycle transitions historical |
| CAL-018 | `indices/credit/L4-dsr.md:118` | Band classification thresholds | (per spec) | DSR peak events (2009 PT, 2012 ES, etc.) |
| CAL-019 | `indices/credit/README.md:139` | Phase bands gerais Cap 15.8 (umbrella) | (per spec) | BIS crisis chronicle + country-specific regime dating |

## Horizonte Phase 1 pre-connector — D2 data source gaps

Items surfaced por D2 empirical validation (2026-04-18) que bloqueiam implementação de specs antes do Phase 1 connector dev.

### CAL-023 — US E2 LEI alternative source

- **Surfaced:** D2 empirical validation 2026-04-18 (commit: post-D2 hotfix).
- **Problem:** `USSLIND` (Philly Fed State Leading Index) descontinuado 2020 per D2 findings (last update 2020-09; 2 268d stale vs 2026-04-18). Conference Board LEI permanece paywalled. US E2 LEI é GAP actual.
- **Candidate replacements:**
  - Philly Fed ADS Business Conditions Index (`USPHCI` FRED? — validar).
  - ECRI Weekly Leading Index (paywall nível limited; scrape?).
  - Conference Board LEI scrape (ethical).
  - State-level aggregation manual (Philly Fed state indexes individuais ainda publicados).
- **Horizon:** Phase 1 pre-connector dev (blocks E2 spec implementation sem alternative).

### CAL-029 — Docs alpha-3 → alpha-2 alignment sweep

- **Priority:** LOW (conditional upgrade to HIGH)
- **Trigger:** P2-023 out-of-scope surface — 25 refs in `docs/`
- **Scope:** scope-docs.txt output from P2-023 discovery
- **Upgrade rule:** if any ref in `docs/specs/conventions/`, bump HIGH
- **Deferral:** execute when docs hygiene window opens (Week 3+)
- **Status:** CLOSED no-op 2026-04-19 (same day as creation)
- **Verification:** 25 refs triaged by chat; all in meta-docs
  (phase2-items.md P2-023 entry, retrospective, execution brief).
  Zero refs in `docs/specs/conventions/`, `docs/specs/overlays/`,
  `docs/adr/`, `docs/reference/`, `docs/data_sources/`. Conditional
  HIGH trigger did not fire. No action required.

### CAL-030 — NSS β0 bounds relaxation for negative yields

- **Priority:** LOW → HOLD 2026-04-20 (DE 2024-01-02 surface clean)
- **Trigger:** pre-Week 3 DE/JP entry
- **Current:** `bounds[β0] = (0, 0.20)` per nss-curves.md §4
- **Issue:** Excludes negative yields (Bunds 2019-2021, JGBs 2016-).
  US Week 2 safe; DE Week 2 (2024-01-02) safe (1.95-3.01% range);
  JP entry blocker.
- **Day 5 surface check:** Bundesbank live fetch DE 2024-01-02 returned
  9 tenors all positive → CAL-030 trigger NOT fired this date. Status
  remains HOLD pending JP onboarding OR DE backfill into 2019-2021
  trough range.
- **Fix:** Relax to `(-0.02, 0.20)`. Validation fixture:
  `de_bund_2019-08-15` (Bund 10Y trough negative).
- **Upgrade rule:** if Week 3 agenda includes JP OR DE backfill into
  2019-2021 → HIGH.

### CAL-031 — NSS fixture live fetch + spec §7 tolerance calibration

- **Priority:** MEDIUM → CLOSED 2026-04-20 (branch B)
- **Trigger:** Day 3 AM FRED live fetch
- **Resolution:** Live FRED H.15 DGS* fetched for 2024-01-02 (commit
  `9ed7cd1`). Fit produces RMSE 6.25 bps > spec §7 nominal 5 bps →
  branch B fires. Fixture `rmse_bps_max` tightened from 10.0 → 9.0
  per `ceil(actual + 2)` formula. Spec §7 tolerance revision deferred
  to **CAL-034** (separate task — needs Fed GSW benchmark eval).

### CAL-032 — Brief policy: contract locks are post-consumer

- **Priority:** LOW (process) → CLOSED 2026-04-20
- **Trigger:** next chat-produced brief (was)
- **Verification:** SESSION_CONTEXT §"Decision authority", §"Brief format",
  §"Regras operacionais" revised 2026-04-20. New model active: dataclasses
  are soft-locked pre-consumer, hard-locked post-consumer (CAL-032 transition
  marker present in commit `5c63876` body where first external consumer —
  persistence layer — landed against L2 dataclasses).
- **Issue (history):** Day 2 AM brief §2 locked dataclass shapes
  pre-consumer; units.md deviation obliged 6 field renames
  (`yields_pct` → `yields`, etc). Blast radius zero (no external consumer),
  but formal §2 invariant was violated.

### CAL-033 — US real curve direct-linker blocked by TIPS coverage

- **Priority:** MEDIUM → CLOSED 2026-04-20 (option (a))
- **Resolution:** `LINKER_MIN_OBSERVATIONS = 5` constant added to
  `src/sonar/overlays/nss.py`; `_validate_inputs` consults
  `inputs.curve_input_type` and uses the lower threshold for
  `linker_real` only. Nominal path retains `MIN_OBSERVATIONS=6` per
  spec §6 row 1. No NSS_v0.1 bump (carve-out is implementation-detail
  inside the linker_real branch).

### CAL-035 — Spec §7 DE xval tolerance revision (Bundesbank benchmark)

- **Priority:** MEDIUM
- **Trigger:** DE 2024-01-02 vertical-slice live fit (commit `eb29851`)
  produces max |deviation| = 5.33 bps at 30Y vs Bundesbank published
  zero rates, just above spec §7 `de_bund_2024_01_02` nominal 5 bps.
- **Scope:** Benchmark Bundesbank Svensson published RMSE on same date
  (their own model is the source of the published yields, so the
  published value tracks the model exactly — divergence is purely from
  SONAR re-fit on the published anchors). Decide whether spec §7
  threshold should reflect SONAR-vs-Bundesbank refit error (~6-10 bps
  realistic) or stay strict at 5 bps.
- **Interim:** test_de_nss_vertical_slice.py uses calibration ceiling
  10 bps (`DE_XVAL_CEILING_BPS`).
- **Sibling of CAL-034 (US/Fed GSW)**; resolve as part of same spec §7
  sweep.

### CAL-034 — Spec §7 RMSE tolerance revision (Fed GSW benchmark)

- **Priority:** MEDIUM
- **Trigger:** us_2024_01_02 live fit RMSE 6.25 bps > spec §7 nominal 5.0
  (CAL-031 branch B handed off here).
- **Scope:** Benchmark Fed GSW NSS published RMSE same date
  (`https://www.federalreserve.gov/data/yield-curve-tables/feds200628.csv`
  — confirm spec §10 §Cross-validation reference). Propose realistic
  `rmse_bps_max` for spec §7 `us_2024_01_02` row + analogous fixtures
  (de_bund, uk, pt). Update spec §7 tolerance column.
- **Decision branch A:** Fed GSW RMSE on same date ≤ 5 → keep spec §7 tight,
  investigate fit quality gap (initial-guess seeding, convergence options).
- **Decision branch B:** Fed GSW RMSE > 5 → revise spec §7 to ~ceil(GSW + 2)
  per family; bump fixture rmse_bps_max accordingly. Probably **no**
  NSS_v0.1 bump (tolerance != math contract).
- **Interim:** Fixture currently `rmse_bps_max=9.0`.

### CAL-036 — TE /markets/historical endpoints validation

- **Priority:** MEDIUM
- **Trigger:** Week 3 ERP EA/UK/JP
- **Scope:** Empirically validate TE `/markets/historical/{SXXP,FTAS,TPX}:IND`
  endpoints for daily EOD reuse: availability, rate limits, licensing
  for our use case, historical depth (min 10Y for CAPE). Document
  results in `docs/data_sources/financial.md`.
- **Blocker for:** Week 3 ERP EA/UK/JP implementation.

### CAL-037 — CDS liquidity threshold calibration

- **Priority:** LOW
- **Trigger:** post 12m production data
- **Scope:** Current `cds_liquidity_threshold_bps = 15` (bid-ask) is
  placeholder from spec draft. Collect 12m production CDS bid-ask data,
  recalibrate threshold based on empirical distribution (e.g. 75th
  percentile of observed bid-ask as cutoff).
- **Ref:** `crp.md` §2 parameters.

### CAL-038 — vol_ratio bounds calibration

- **Priority:** LOW
- **Trigger:** post 18m production data
- **Scope:** Current `vol_ratio_bounds = (1.2, 2.5)` placeholder.
  Recalibrate empirically: compute vol_ratio distribution across
  30+ countries × 18m, set bounds at percentiles 5-95 or use robust
  z-score clipping. Damodaran standard 1.5 remains fallback.
- **Ref:** `crp.md` §2 parameters.

### CAL-039 — rating-CDS divergence threshold calibration

- **Priority:** LOW
- **Trigger:** post 18m production data
- **Scope:** Current `rating_cds_divergence_threshold_pct = 50`
  placeholder. Recalibrate on observed `|cds − rating_implied| / cds`
  distribution; likely 75th or 90th percentile.
- **Ref:** `crp.md` §2 parameters.

### CAL-040 — Equity/bond vol data source validation

- **Priority:** MEDIUM → CLOSED 2026-04-20
- **Trigger:** Week 3 CRP (vol_ratio country-specific branch)
- **Scope:** Validate `twelvedata` (equity index daily 5Y history,
  Tier/licensing review) and `yfinance` (bond ETF price series, scrape
  stability, ToS). Alternatives if both fail: (a) TE equity history +
  derived bond vol via sovereign NSS yield changes; (b) Damodaran
  standard 1.5 permanent.
- **Blocker for:** CRP country-specific vol_ratio Week 3+; CRP ships
  with `damodaran_standard=1.5` interim.
- **Status**: CLOSED 2026-04-20 — resolved via FMP Ultimate (equity
  historical) + TE historical yields (bond vol proxy) pivot. Neither
  twelvedata nor yfinance needed. Country-specific vol_ratio
  activates Week 3.5. (Note: brief `spec-sweep-crp-erp-brief.md`
  referenced this entry as `CAL-039` reflecting its pre-Option-A-
  renumber label; actual ID post-renumber is CAL-040.)

### CAL-019 — BIS WS_TC key unit code debug (CLOSED 2026-04-20)

- **Priority:** HIGH → **CLOSED 2026-04-20** via credit-indices-brief-v3
  Commit 1.
- **Note on ID collision:** the table row at top of this file under
  "60m per country / credit phase bands" also carries the label CAL-019
  referencing phase bands in `indices/credit/README.md:139`. That is a
  pre-existing ID re-use (doc inconsistency surfaced during Phase 0
  Bloco D). The WS_TC key-debug usage documented here is the one
  referenced by `docs/data_sources/credit.md` (pre-2026-04-20 §3.1
  Finding D1-T2) and by CAL-053. Phase-bands CAL-019 remains open.
- **Trigger (original, 2026-04-18):** BIS WS_TC smoke test
  `Q.PT.P.M.770A` returned 404 across all T1 countries tested;
  key format hypothesised deprecated but not resolved.
- **Scope (resolved):** hit BIS structure endpoint
  `GET /structure/dataflow/BIS/WS_TC?references=all&detail=full`,
  parse `BIS_TOTAL_CREDIT(2.0)` dimension list, resolve
  `UNIT_TYPE=770` (Percentage of GDP) and discover 7-dim key
  (vs the broken 5-dim key): FREQ.BORROWERS_CTY.TC_BORROWERS.
  TC_LENDERS.VALUATION.UNIT_TYPE.TC_ADJUST.
- **Resolution (2026-04-20)**: canonical key for L1 consumers is
  `Q.{CTY}.P.A.M.770.A`. Empirical 7/7 T1 HTTP 200 on
  US/DE/PT/IT/ES/FR/NL with plausible credit-to-GDP values (US 147%,
  NL 285%, IT 98% range). `docs/data_sources/credit.md` §3.1 amended.
  Structure response cached
  `tests/fixtures/bis/ws_tc_structure.json`. Bonus: validated
  WS_DSR 3-dim key `Q.{CTY}.P` and WS_CREDIT_GAP 5-dim key
  `Q.{CTY}.P.A.{CG_DTYPE}` (CG_DTYPE=C → gap) for the same 7 T1
  countries in the same commit.
- **Unblocks (closed):** CAL-053 (BIS connector) can proceed;
  CAL-052 resolution remains a Hugo decision but data layer is no
  longer a blocker.

### CAL-041 — CRP distress CDS threshold calibration

- **Priority:** LOW
- **Trigger:** post-observation
- **Scope:** Current `distress_cds_threshold_bps = 1500` placeholder
  (Argentina-class). Recalibrate empirically on observed distressed
  sovereigns CDS distribution over 5Y+.
- **Ref:** `crp.md` §2 parameters + §6 edge cases.

### CAL-042 — PT-EA inflation differential per-tenor refinement

- **Priority:** LOW
- **Trigger:** Phase 2
- **Scope:** Current DERIVED formula applies flat 5Y rolling PT-EA
  HICP differential across all tenors (1Y/2Y/5Y/10Y/30Y).
  Economically, long-dated differential should converge (EU
  convergence); short-dated responds to local shocks. Investigate
  per-tenor differential via term_factor scaling or tenor-specific
  rolling windows.
- **Ref:** `expected-inflation.md` §4 DERIVED + §6 edge cases.

### CAL-043 — Expected inflation connector validation (UK/JP/EM)

- **Priority:** MEDIUM
- **Trigger:** Week 4+ ExpInf expansion beyond US/EA/DE/PT
- **Scope:** Validate 4 connectors: `boe_dmp` (UK DMP survey
  quarterly, web API/CSV), `boj_tankan` (JP BoJ Tankan quarterly,
  XML feed), `imf_weo` (IMF WEO CPI projections semi-annual,
  database API), `focuseconomics` (EM Tier 3 monthly consensus,
  CSV subscription ToS review).
- **Blocker for:** UK/JP/EM ExpInf coverage Week 4+.

### CAL-044 — ERP overlay implementation (Week 3 deferred → CLOSED Week 3.5B-equivalent via ERP US brief)

- **Priority:** HIGH → **CLOSED 2026-04-20** (superseded by CAL-048
  which shipped in the 8-commit ERP US implementation brief;
  retrospective at `docs/planning/retrospectives/erp-us-implementation-report.md`).
- **Original trigger:** Week 3 brief §1 ERP scope partially
  implemented, needed FactSet PDF scrape, multpl + spdji web
  scrapers, and the 4-method DCF/Gordon/EY/CAPE compute layer with
  Damodaran xval.
- **Resolution:** Re-chunked as CAL-048 and delivered across 8
  commits (`98fbe2e`..`6f3f9f0`) during the ERP US brief —
  migration 007 + 5 erp_* tables + 4-method compute + Damodaran
  xval + FactSet/Yardeni divergence flag + 42 behavioural tests +
  pipeline wiring. US-only scope per original graceful-degradation
  plan; EA/UK/JP per-country overlays remain Week 4+ scope (not
  part of this CAL closure).

### CAL-045 — Treasury connectors aft_france / mef_italy (Week 3 deferred)

- **Priority:** MEDIUM
- **Trigger:** Week 3 brief §1 ExpInf EA scope (BEI via DE/FR/IT
  linkers) deferred. Bundesbank already validated Week 2 Day 5; the
  French OATi (via Agence France Trésor) and Italian BTP€i (via MEF)
  endpoints remain to investigate.
- **Scope:** Endpoint discovery + parser per country; extend
  `expected_inflation.py` to compute EA BEI from these tenors
  alongside Bundesbank.
- **HALT-trigger reference:** Week 3 brief §4.4 — if endpoints
  documented are wrong, fall back to ECB SDW EA-aggregate-only BEI.

### CAL-046 — Persistence helpers + integration tests (Week 3 deferred)

- **Priority:** MEDIUM
- **Trigger:** Compute layers for ratings_spread / expected_inflation
  / crp shipped Week 3 (commits `6c5239e`, `5cff096`, `c1a131d`)
  without paired persistence helpers and integration tests beyond
  the rating-spread persistence + duplicate detection tests.
- **Scope:** persist_exp_inflation_canonical + per-method writers;
  persist_crp_canonical + per-method writers; vertical-slice
  integration tests US (NSS → ExpInf → ratings → CRP → assert all
  rows joined by exp_inf_id / crp_id / fit_id chains).

### CAL-047 — daily-cost-of-capital pipeline (Week 3 deferred → CLOSED Week 3.5F)

- **Priority:** MEDIUM → **CLOSED 2026-04-20** via commit `ee634f8`.
- **Resolution:** Pipeline skeleton shipped Week 3.5F:
  `src/sonar/pipelines/daily_cost_of_capital.py` + alembic 006 +
  `cost_of_capital_daily` table + CLI `--country | --all-t1`. Uses
  Damodaran mature 5.5% ERP placeholder until CAL-044 ERP overlay
  lands. Wiring to real ERP: one-line swap from constant to
  `erp_canonical` SELECT.

### CAL-048 — ERP overlay full implementation (Week 3.5B deferred → CLOSED)

- **Priority:** HIGH → **CLOSED 2026-04-20** via 8-commit ERP US
  implementation brief (`98fbe2e`..`6f3f9f0`). Retrospective at
  `docs/planning/retrospectives/erp-us-implementation-report.md`.
- **Resolution summary:** Migration 007 + 5 `erp_*` tables shipped;
  6 L0 connectors delivered (Damodaran histimpl.xlsx, multpl, spdji
  buyback stub, FactSet Earnings Insight PDF, Yardeni Squiggles
  PDF, Shiller already pre-existing); 4-method compute
  (DCF/Gordon/EY/CAPE) with canonical aggregation at 94.42 %
  coverage on `erp.py`; Damodaran xval + FactSet↔Yardeni divergence
  flags wired; 42 behavioural tests + 4 spec §7 fixtures; daily
  cost-of-capital pipeline now reads live ERP canonical (US k_e
  pre-brief 9.65 % stub → post-brief 7.37 % computed on
  2024-01-02, −228 bps). EA/UK/JP overlays proxy US with
  `MATURE_ERP_PROXY_US` flag pending Week 4+.
- **Gaps flagged** (follow-up CALs): CAL-056 (Damodaran connector
  HTTP coverage gap — 75 % vs 92 % connectors hard gate); CAL-057
  (`daily_erp_us` L8 pipeline for live connector orchestration).

### CAL-049 — FR/IT linkers + EA BEI + PT DERIVED (Week 3.5D deferred)

- **Priority:** MEDIUM
- **Trigger:** Week 3.5 brief §3 3.5D scope not executed this session.
  FR aft_france OATi endpoint + IT mef_italy BTP€i endpoint need
  discovery (public sites restructure frequently — brief §4.4 HALT
  trigger anticipates this).
- **Scope:** Week 3.5 brief §3 items 3.5D-1 through 3.5D-3 (2
  connectors + EA BEI path in expected_inflation.py extending the
  hierarchy picker + PT DERIVED with 5Y PT-EA HICP differential
  computation via Eurostat + fixtures per spec §7 for DE/FR/IT/PT).
- **Unblocks:** ExpInf EA canonical rows for FR/IT/DE/PT countries;
  DERIVED path for periphery countries; unblocks L3 E2 leading /
  M3 market-expectations consumers.

### CAL-050 — Persistence helpers + 7-country vertical slice (Week 3.5E deferred)

- **Priority:** MEDIUM
- **Trigger:** Week 3.5 brief §3 3.5E scope partially covered (simple
  persistence of `cost_of_capital_daily` shipped inline with
  daily_cost_of_capital.py). Broader persistence helpers for ExpInf
  + CRP + integration test exercising live 7-country vertical slice
  not executed.
- **Scope:** `src/sonar/db/persistence_expinf.py` + `persistence_crp.py`
  + integration test `test_seven_country_vertical_slice.py` that
  fetches all connectors (live or cassette), computes all overlays,
  persists, queries back, and asserts k_e plausibility bands per
  country.

### CAL-051 — L3 orchestrator live-data wiring (L3 sub-sprint surfaced)

- **Priority:** MEDIUM
- **Trigger:** `src/sonar/indices/orchestrator.py` (l3-indices c5/6,
  SHA `1109426`) runs only on synthetic input bundles. CLI
  `python -m sonar.indices.orchestrator --country X --date Y`
  regenerates the E2/M3 Inputs via `np.random.default_rng` per
  invocation instead of reading live `yield_curves_spot`,
  `yield_curves_forwards`, and `expected_inflation_canonical` rows
  from the DB. Tests prove the orchestration contract, not the
  data path.
- **Scope:** read `NSSYieldCurveSpot` + `NSSYieldCurveForwards` rows
  for `(country, date)` to derive `spot_2y_bps`, `spot_10y_bps`, and
  `forward_2y1y_bps`; walk back 5Y of rows to assemble
  `slope_history_bps` and `forward_spread_history_bps`; read
  `ExpInfCanonical` for `breakeven_5y5y_bps`, `anchor_deviation_bps`
  (implied `bc_target_bps` via config), `bei_10y_bps`, `survey_10y_bps`,
  plus matching 5Y histories. Replace `_synthetic_inputs` with a
  `_inputs_from_db(session, country, date)` helper; CLI gains a
  `--use-db` flag (default) with `--synthetic` fallback for CI.
- **Unblocks:** pipelines layer daily orchestration of L3 indices;
  prerequisite for L4 cycle classifiers that consume persisted
  `index_values` rows rather than in-memory `IndexResult` objects.

### CAL-052 — Credit indices taxonomy reconciliation (L3 sub-sprint HALT #4)

- **Priority:** HIGH
- **Trigger:** L3 indices implementation brief (commit `c1d6684`)
  §Commits 5-7 references specs named `L1-credit-to-gdp-gap @
  L1_v0.1`, `L2-debt-service-ratio @ L2_v0.1`, `L3-sovereign-spread
  @ L3_v0.1`, `L4-cds-divergence @ L4_v0.1`. Actual repo state in
  `docs/specs/indices/credit/` is `L1-credit-to-gdp-stock` (methodology
  `L1_CREDIT_GDP_STOCK_v0.1`), `L2-credit-to-gdp-gap`, `L3-credit-impulse`,
  `L4-dsr` — fundamentally different taxonomy. Brief-L3 and brief-L4
  specs (sovereign spread / CDS basis) do not exist anywhere in
  `docs/specs/`. HALT trigger #4 fired during l3-indices sub-sprint;
  see `docs/planning/retrospectives/l3-indices-implementation-report.md`
  §HALT triggers. Brief-L1 corresponds conceptually to repo `L2-gap`;
  brief-L2 to repo `L4-dsr`.
- **Scope:** Hugo/chat decision on (a) whether brief's "Credit Cycle
  subset" (sovereign spread + CDS-bond basis) are *new* indices
  outside the CCCS L1-L4 set, or a re-scoping of CCCS that supersedes
  the current README chart; (b) if new: author specs
  `docs/specs/indices/credit/sovereign-spread.md` and
  `cds-bond-basis.md` + register their flags (`CDS_DATA_UNAVAILABLE`
  at minimum) in `conventions/flags.md` §2.2 Credit; (c) if
  re-scoping: deprecate repo `L1-stock` / `L3-impulse` via ADR and
  bump `credit-cccs.md` methodology to reference new sub-indices.
- **Unblocks:** brief commits 5-7 (4 credit indices); unblocks CCCS
  composite cycle once sub-indices are finalised.

### CAL-053 — BIS WS_TC + WS_DSR connector (L3 sub-sprint HALT #3)

- **Priority:** HIGH
- **Trigger:** `src/sonar/connectors/` has no `bis.py` as of
  2026-04-20. L3 indices brief commits 5-6 require BIS
  quarterly credit-to-GDP (WS_TC) and DSR (WS_DSR) series for
  7 T1 countries (US/DE/PT/IT/ES/FR/NL). Brief authorized an
  inline wrapper as fallback, but combining inline wrapper with
  CAL-052 taxonomy divergence risks double-divergence from repo
  canon. HALT trigger #3 fired. Data-sources doc
  `docs/data_sources/credit.md` §3.1 already catalogs the endpoint
  shape and notes outstanding WS_TC key-format debug (see CAL-019).
- **Scope:** `src/sonar/connectors/bis.py` — SDMX v2 client with
  dataflows `WS_TC` (credit-to-GDP), `WS_DSR` (debt service ratio),
  `WS_CREDIT_GAP` (BIS one-sided HP gap). Respect rate limits,
  cache by `(flow, key, startPeriod, endPeriod)` in `.cache/bis/`,
  emit SDMX-JSON 1.0 parsed series. Validate WS_TC key structure
  (`Q.{CTY}.P.M.{UNIT}`) — 2026-04 smoke test showed `770A`
  dimension returning 404, investigate via metadata fetch. Fixtures
  cassettes for 7 T1 countries quarter-end 2024-Q4.
- **Unblocks:** repo L1/L2/L4 CCCS sub-indices (stock, gap, DSR);
  resolves the data dependency for CAL-019 (WS_TC key format) and
  any `credit-cccs` composite implementation.

### CAL-054 — E2 Leading full composite (8-component v0.2) upgrade

- **Priority:** MEDIUM
- **Trigger:** L3 sub-sprint shipped `E2_LEADING_SLOPE_v0.1`
  (commit `11c465a`) — a 3-component subset (slope 70% /
  forward-spread 20% / recession proxy 10%) — because the full
  `E2_LEADING_v0.2` spec requires connectors not yet in production:
  LEI (blocked on CAL-023), OECD CLI direct SDMX-JSON, PMI
  manufacturing new orders (ISM + SPGlobal), building permits
  (FRED `PERMIT` + Eurostat), non-defense capex orders (FRED
  `ANDEV`), HY OAS (FRED `BAMLH0A0HYM2`). Subset is documented as
  a bridge, not a destination.
- **Scope:** extend `src/sonar/indices/economic/e2_leading.py` with
  the remaining 5 sub-components per spec `E2-leading.md` §4
  (weights 0.10 HY OAS, 0.15 PMI new orders, 0.15 PMI composite
  change, 0.10 building permits, 0.05 capex, 0.10 LEI, 0.10 OECD
  CLI); re-weight logic per spec §6 for partial-component paths;
  bump methodology to `E2_LEADING_v0.2`; retire
  `E2_LEADING_SLOPE_v0.1` once downstream ECS consumer is migrated.
- **Unblocks:** ECS cycle composite (`cycles/economic-ecs`) —
  requires full v0.2 weight distribution per spec Cap 15.6.

### CAL-055 — M3 Market Expectations full composite (EP 4-component) upgrade

- **Priority:** MEDIUM
- **Trigger:** L3 sub-sprint shipped
  `M3_MARKET_EXPECTATIONS_ANCHOR_v0.1` (commit `4bb9ae8`) — a
  3-component anchor subset (nominal 5y5y 40% / anchor deviation
  40% / BEI-survey divergence 20%) — because the full
  `M3_MARKET_EXPECTATIONS_v0.1` spec requires connectors not yet in
  production: Miranda-Agrippino policy-surprise dataset (Tier 2),
  OIS curves for `forward_1y1y` / `forward_2y1y` beyond
  sovereign-derived. Subset covers the credibility-anchor half of
  the EP sub-index; the rate-path half (1y1y / 2y1y vs policy) is
  deferred.
- **Scope:** extend `src/sonar/indices/monetary/m3_market_expectations.py`
  with the full 4-component EP per spec `M3-market-expectations.md`
  §4 (weights 0.40 1y1y vs policy, 0.25 2y1y vs policy, 0.20 5y5y
  anchor, 0.15 policy surprise); add `connectors/policy_surprise.py`
  (Miranda-Agrippino CSV ingestion); bump methodology to
  `M3_MARKET_EXPECTATIONS_v0.1`; retire the `_ANCHOR_v0.1` subset
  once MSC downstream consumer is migrated.
- **Unblocks:** MSC cycle composite (`cycles/monetary-msc`) EP
  sub-index at full spec weight; Dilemma trigger A logic that needs
  `anchor_status` + policy-surprise amplitude jointly.

### CAL-056 — Damodaran connector HTTP / cache / aclose coverage gap (ERP US brief surfaced)

- **Priority:** MEDIUM
- **Trigger:** ERP US brief retrospective flagged
  `src/sonar/connectors/damodaran.py` at 75.00 % coverage — below the
  92 % connectors hard gate. Parse path (`_parse_year`) is
  exhaustively tested; HTTP `_download`, `fetch_raw_xlsx` cache-miss
  path, and `aclose` remain uncovered. Same pattern used in the
  FactSet + Yardeni tests (pytest-httpx / AsyncMock / cache
  pre-seeding) applies directly.
- **Scope:** Add tests for (a) HTTP happy path with `pytest-httpx`
  mocking the xlsx body, (b) HTTP retry exhaustion, (c) cache hit
  bypassing HTTP, (d) `aclose` closing both client and cache.
  Target ≥ 92 %.
- **Unblocks:** CAL-048 acceptance strictness (connectors hard-gate
  compliance across the ERP connector family).

### CAL-058 — BIS ingestion pipeline + DbBackedInputsBuilder (credit track surfaced → CLOSED)

- **Priority:** MEDIUM → **CLOSED 2026-04-20** via 6-commit CAL-058
  brief (`e565898`..retrospective commit). Retrospective at
  `docs/planning/retrospectives/cal-058-bis-ingestion-report.md`.
- **Original trigger:** Credit track c9/10 shipped
  `daily_credit_indices.py` with a pluggable `InputsBuilder` whose
  default path returns an empty bundle. Production mode needed (a)
  a BIS-fetch pass that writes raw observations to a persistent
  cache and (b) a DB-backed builder that reads them.
- **Resolution:** Migration 011 added `bis_credit_raw`;
  `daily_bis_ingestion.py` pipeline fetches WS_TC / WS_DSR /
  WS_CREDIT_GAP for 7 T1 countries with idempotent upsert;
  `DbBackedInputsBuilder` assembles L1 + L2 inputs from the raw
  table (L3 + L4 scope-trimmed — see CAL-059/060 below).
- **Scope trims (documented in retrospective):**
  - CAL-059 (LCU ingestion for L3 credit impulse).
  - CAL-060 (lending-rate + maturity ingestion for L4 DSR).
  - CAL-061 (lift `daily_bis_ingestion` CLI coverage from 80.8% to 85%+).

### CAL-059 — LCU credit stock + GDP ingestion for L3 impulse (CAL-058 surfaced)

- **Priority:** MEDIUM
- **Trigger:** `DbBackedInputsBuilder` leaves L3 `None` because
  `bis_credit_raw` carries only credit-to-GDP ratios, not the
  LCU-level series (`credit_stock_lcu_history` +
  `gdp_nominal_lcu_history`) L3 credit-impulse compute requires.
- **Scope:** Add ingestion of (a) FRED `TCMDO` + `GDP` for US, (b)
  Eurostat `nasq_10_f_bs` + `namq_10_gdp` for EA periphery, (c) BIS
  embedded LCU where available; extend `DbBackedInputsBuilder` to
  populate `CreditImpulseInputs` with the assembled histories.
- **Unblocks:** L3 credit impulse rows in `--backend=db` production
  mode (currently always skipped).

### CAL-060 — L4 DSR input assembly (CAL-058 surfaced)

- **Priority:** MEDIUM
- **Trigger:** `DbBackedInputsBuilder` leaves L4 `None` because DSR
  compute needs `lending_rate_pct`, `avg_maturity_years`, and
  segment-level `debt_to_gdp_ratio` — none of which come from
  `bis_credit_raw` alone.
- **Scope:** Derive `lending_rate_pct` from NSS 10Y nominal (or
  national central-bank direct data where superior),
  `avg_maturity_years` from BIS-embedded segment maturity where
  available + fallback national sources, `debt_to_gdp_ratio` from
  WS_TC (already ingested). Extend `DbBackedInputsBuilder` to
  populate `DsrInputs`.
- **Unblocks:** L4 DSR rows in `--backend=db` production mode + US
  DSR 2024-Q2 canary within 1pp of BIS-published (CAL-058 brief §6
  partial acceptance).

### CAL-061 — `daily_bis_ingestion` CLI wrapper coverage lift (CAL-058 surfaced)

- **Priority:** LOW
- **Trigger:** CAL-058 shipped `daily_bis_ingestion.py` at 80.8%
  coverage vs the 85% brief target. Gap lives in `main()` + the
  `asyncio.run(_orchestrate())` wrapper.
- **Scope:** Add Typer `CliRunner` smoke tests covering the full
  CLI path end-to-end (not just config-error paths already
  covered). Likely `monkeypatch`-heavy for the connector + session.
- **Unblocks:** Connector-scope coverage hard-gate compliance for
  the full ingestion family.

### CAL-057 — `daily_erp_us` pipeline for live connector orchestration (ERP US brief surfaced) (CLOSED 2026-04-22 via daily_cost_of_capital composition)

- **Priority:** MEDIUM → **CLOSED 2026-04-22** (Week 10 Day 0 CAL grooming).
- **Trigger:** ERP US brief commit 8 (`6f3f9f0`) wired
  `daily_cost_of_capital` to **read** `erp_canonical` rows instead of
  the 5.5 % stub, but explicitly deferred the **write** path: no
  module today fetches FactSet + Yardeni + Shiller + multpl + spdji
  + FRED SP500 + Damodaran, calls `fit_erp_us`, and persists. Until
  such a pipeline exists, `erp_canonical` is populated only by direct
  test invocations / ad-hoc notebooks.
- **Original scope:** New `src/sonar/pipelines/daily_erp_us.py` CLI
  (`--date YYYY-MM-DD`) that orchestrates the 7 connectors (FactSet
  + Yardeni best-effort + rest hard), assembles `ERPInput`, calls
  `fit_erp_us(inputs, damodaran_erp_decimal=...)`, persists via
  `persist_erp_fit_result`. Graceful degradation: each connector
  failure emits the relevant flag (`OVERLAY_MISS` etc.) but does not
  abort the fit unless < 2 methods remain. Integration test with
  cassette fixtures for all 7 sources.
- **Resolution:** dedicated `daily_erp_us.py` pipeline NOT
  materialized; instead ERP composition + persist path was integrated
  into `daily_cost_of_capital` (Week 3.5F) which orchestrates the
  Damodaran ingest + live overlay composition in-situ. When
  `daily_cost_of_capital` runs, `erp_canonical` rows are produced as
  a by-product; no separate pipeline needed. Architecturally cleaner
  than the original dedicated-pipeline design because
  cost-of-capital already owns the ERP surface.
- **Status:** done (via `daily_cost_of_capital` composition — Week
  3.5F live assemblers commit family + Sprint G M1 US close). No
  standalone pipeline ship required.
- **Follow-on:** per-country ERP live paths (CAL-ERP-T1-PER-COUNTRY
  Phase 2) remains OPEN and replaces the `MATURE_ERP_PROXY_US` flag
  for EA/GB/JP with native per-market assemblers.

### CAL-068 — MOVE index live data source (F-cycle retro CAL-061 renumbered) (CLOSED 2026-04-20)

- **Priority:** MEDIUM → **CLOSED 2026-04-20** via
  week5-sprint-1-brief Commit 1.
- **ID note:** The F-cycle retrospective
  (`docs/planning/retrospectives/f-cycle-implementation-report.md`)
  declared this item as "CAL-061" but the ID slot was already held by
  CAL-058's surfaced `daily_bis_ingestion` coverage lift. This entry
  re-numbers to CAL-068 for backlog uniqueness; the f-cycle retro
  prose mention survives as historical reference.
- **Trigger:** `src/sonar/connectors/move_index.py` shipped in f-cycle
  commit `b1a46e5` as a documented placeholder raising
  `DataUnavailableError`. F3 Risk Appetite relied on
  `MOVE_UNAVAILABLE` flag + weight redistribution as a degraded path.
- **Scope (resolved):** Yahoo Finance chart API for `^MOVE` ticker
  (public, no auth). fetch_move(start, end) → list[MoveObservation]
  with level in bps. Schema-drift guard raises
  `DataUnavailableError` on missing `chart.result[0].timestamp` or
  misaligned arrays. Cassette replay tests + `@pytest.mark.slow` live
  canary verifying sanity band [5, 200].
- **Unblocks:** F3 Risk Appetite full component stack (US + global
  proxy path); `MOVE_UNAVAILABLE` flag path no longer the default.

### CAL-069 — AAII sentiment live data source (F-cycle retro CAL-062 renumbered) (CLOSED 2026-04-20)

- **Priority:** MEDIUM → **CLOSED 2026-04-20** via
  week5-sprint-1-brief Commit 2.
- **ID note:** F-cycle retro labelled "CAL-062"; renumbered to CAL-069
  for backlog uniqueness.
- **Trigger:** AAII sentiment placeholder raising
  `DataUnavailableError` blocked F4 Positioning full component stack.
- **Scope (resolved):** AAII public xlsx endpoint
  `https://www.aaii.com/files/surveys/sentiment.xlsx` parsed via
  openpyxl with schema-drift guard (assert columns Date/Bullish/
  Neutral/Bearish present). `SchemaChangedError` raised on column
  drift → subclass of `DataUnavailableError` for backward compat
  with F4 `AAII_PROXY` fallback.
- **Unblocks:** F4 Positioning US full 5-component path.

### CAL-070 — CFTC COT live data source (F-cycle retro CAL-063 renumbered) (CLOSED 2026-04-20)

- **Priority:** MEDIUM → **CLOSED 2026-04-20** via
  week5-sprint-1-brief Commit 3.
- **ID note:** F-cycle retro labelled "CAL-063"; renumbered to CAL-070.
- **Trigger:** CFTC COT placeholder raising `DataUnavailableError`.
- **Scope (resolved):** Socrata JSON API
  `https://publicreporting.cftc.gov/resource/6dca-aqww.json` filtered
  for `E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE`, returning
  weekly non-commercial long/short positions. fetch_cot_sp500_net
  returns list[CotObservation].
- **Unblocks:** F4 Positioning COT component live.

### CAL-071 — F-cycle connector canary backfill (F-cycle retro CAL-067 renumbered) (CLOSED 2026-04-20)

- **Priority:** MEDIUM → **CLOSED 2026-04-20** via
  week5-sprint-1-brief Commit 4.
- **ID note:** F-cycle retro labelled "CAL-067"; renumbered to CAL-071.
- **Trigger:** 8 F-cycle connectors shipped without
  `@pytest.mark.slow` live canary tests. Schema drift / endpoint
  decay would go undetected until integration runs.
- **Scope (resolved):** One live canary per F-cycle connector (CBOE
  VIX, ICE BofA HY OAS, Chicago Fed NFCI, FINRA margin, BIS property,
  MOVE, AAII, CFTC COT). Each fetches a recent observation window +
  asserts sanity band + non-empty response. Slow-marked so they skip
  from default `pytest tests/unit/` invocation; runnable via
  `pytest -m slow`.
- **Unblocks:** Production-grade F-cycle connector coverage.

### CAL-072 — BIS property dataflow rename (WS_LONG_PP → WS_SPP) (CLOSED 2026-04-20)

- **Priority:** HIGH → **CLOSED 2026-04-20** via Week 6 Sprint 3 C1
  (`667f581`).
- **Trigger:** Week 5 Sprint 1 Commit 5 cassette backfill discovered
  BIS SDMX v2 no longer serves dataflow `BIS:WS_LONG_PP(1.0)`. Live
  canary was xfail'd while production `bis.py` still referenced the
  old id and 404'd.
- **Scope (resolved):** Renamed `DATAFLOW_WS_LONG_PP` → `DATAFLOW_WS_SPP`
  in `src/sonar/connectors/bis.py`. Key pattern `Q.{CTY}.N.628` still
  resolves. Source tag updated `BIS_WS_LONG_PP` → `BIS_WS_SPP`. Test
  assertions updated. xfail decorator removed from live canary; canary
  passes live (fetches PT 2y property-price index with positive values).
  Existing cassette needed no re-record (Sprint 1 captured WS_SPP
  payload directly as stopgap — identical SDMX-JSON 1.0 shape).

### CAL-073 — CBOE S&P put/call FRED series (PUTCLSPX) delisted (CLOSED 2026-04-20)

- **Priority:** MEDIUM → **CLOSED 2026-04-20** via Week 6 Sprint 3
  Commits 5 + 6 (`9fe7d78`, `62942c2`).
- **Trigger:** Week 5 Sprint 1 Commit 6 F4 live integration smoke
  discovered FRED `PUTCLSPX` delisted (400 "does not exist"). CBOE
  also paywalled the XLS download.
- **Scope (resolved):** New `src/sonar/connectors/yahoo_finance.py`
  generic chart-API connector (future-proof for more Yahoo symbols)
  with `fetch_put_call_ratio_us` wrapper around Yahoo ticker `^CPC`
  (CBOE Equity Put/Call Ratio, daily close). Existing
  `move_index.py` intentionally left untouched (HALT #5 discipline).
  F4 live-smoke integration test rewired to consume Yahoo; post-
  sprint US F4 = 5/5 components when Yahoo rate-limit cooperates;
  test skips cleanly on 429 (Yahoo applies aggressive anti-bot
  throttling on bare-endpoint probes — tenacity retry covers it
  under normal load).

### CAL-092 — FRED ISM/NFIB delisted series fallback connectors (CLOSED 2026-04-20)

- **Priority:** MEDIUM → **CLOSED 2026-04-20** via Week 6 Sprint 1
  Commits 1-3 (`a2b86a6`, `d1cd3ac`, `8e59498`).
- **Trigger:** Week 5 Sprint 2a Commit 3 live probes confirmed FRED no
  longer serves ``NAPM`` (ISM Mfg PMI), ``NAPMII`` (ISM Svc PMI) or any
  ``NFIB`` series.
- **Scope (resolved):** TE Pro serves as the production fallback.
  `TEConnector.fetch_ism_manufacturing_us` → TE "business confidence"
  (sourced from ISM); `fetch_ism_services_us` → "non manufacturing
  pmi"; `fetch_nfib_us` → "nfib business optimism index". Builder
  `build_e4_inputs` tries FRED first, falls through to TE on
  DataUnavailableError, flags `TE_FALLBACK_{ISM_MFG,ISM_SVC,NFIB}`
  when it substitutes. CAL-082 (direct ISM scraper) + CAL-091 (NFIB
  scraper) become unnecessary unless TE Pro access is dropped.
- **Follow-up:** N/A — TE coverage verified, live smoke green.

### CAL-093 — Conference Board Consumer Confidence live feed (CLOSED 2026-04-20, re-opened + re-closed correctly)

- **Priority:** LOW → **re-CLOSED 2026-04-20** via Week 6 Sprint 3
  Commits 2-4 (`4b6e037`, `bd76354`).
- **Trigger:** Sprint 2a Commit 3: ``CONCCONF`` is not a FRED id.
  OECD CLI proxy (``CSCICP03USM665S``) was substituted but freezes
  at 2024-01.
- **Original (incorrect) closure — superseded:** Week 6 Sprint 1
  closed this CAL as "not resolvable by TE" on the premise that TE's
  US "Consumer Confidence" was UMich-sourced. **This premise was
  wrong.** Empirical probe (Sprint 3 2026-04-20) confirmed TE returns
  ``HistoricalDataSymbol=CONCCONF`` for the ``consumer confidence``
  indicator on the ``united states`` endpoint — i.e. actual
  Conference Board CCI. The Sprint 1 inference relied on the
  ``Source="University of Michigan"`` field on the catalogue
  endpoint, which is misleading; the historical endpoint carries the
  definitive symbol.
- **Operational lesson:** always probe the
  ``HistoricalDataSymbol`` on TE's historical endpoint to verify
  source identity before concluding. The catalogue endpoint's
  ``Source`` field is unreliable for disambiguation.
- **Resolution:** ``TEConnector.fetch_conference_board_cc_us``
  ships with a ``CONCCONF`` source-identity guard (raises
  ``DataUnavailableError("source drift")`` if TE ever swaps the
  feed). E4 builder takes TE as primary for the CB slot (FRED
  fallback); emits ``TE_FALLBACK_CB_CC`` flag when TE is used.
  Sprint 3 live smoke confirms the uplift: CB slot no longer stale.
- **Follow-up:** None.

### CAL-094 — Eurostat namq_10_pe gap for PT employment (OPEN)

- **Priority:** LOW
- **Trigger:** Sprint 2a Commit 5 live smoke discovered
  ``namq_10_pe/Q.THS_PER.SCA.EMP_DC.PT`` returns zero observations —
  Eurostat does not publish seasonally+calendar adjusted domestic-
  concept employment for PT. DE works; PT doesn't. Consequence: PT
  E1 typically lands at 3/6 components and raises
  :class:`InsufficientDataError`.
- **Scope:** Evaluate alternative Eurostat keys (NSA/SA variants,
  ``lfsq_egan``) or fall back to the national statistical office (INE)
  for PT employment. Same investigation applies for IT/ES/FR/NL where
  namq_10_pe may also gap.
- **Surfaced from:** Week 5 Sprint 2a Commit 5.

### CAL-080 — Eurostat SDMX connector (Week 5 ECS surfaced) (CLOSED 2026-04-20)

- **Priority:** MEDIUM → **CLOSED 2026-04-20** via Sprint 2a
  Commits 1-2 (`4805a24`, `9b48af1`).
- **Trigger:** Week 5 ECS compute layer ships (E1/E3/E4 per spec)
  but stays data-empty for EA countries without Eurostat. Was
  originally brief week5 §Commit 3; descoped per user §7 budget trim.
- **Scope (resolved):** `src/sonar/connectors/eurostat.py` implements
  the JSON-stat 2.0 path (not SDMX-JSON 1.0 — confirmed empirically)
  with SchemaChangedError guards + gzip-without-Content-Encoding
  workaround. Seven indicator helpers ship: GDP + IP + Employment +
  Retail (YoY) + UR + ESI + ConsConf (levels). Deviations from brief:
  `lfsi_emp_m` 404s (use `namq_10_pe`); ESI lives in `ei_bssi_m_r2`
  (not `ei_bsco_m`); `teibs020` trails only 12m → use `ei_bsco_m`
  BS-CSMCI for ConsConf history. See CAL-094 for PT employment gap.
- **Unblocks:** E1/E3/E4 EA coverage (DE + IT + ES + FR + NL);
  Sprint 2b CCCS + FCS + ECS composite readiness.

### CAL-081 — S&P Global PMI scraper (Week 5 ECS surfaced)

- **Priority:** MEDIUM
- **Trigger:** Week 5 ECS brief §Commit 4; descoped to CAL.
- **Scope:** `src/sonar/connectors/spglobal_pmi.py` scraping
  spglobal.com/marketintelligence PMI release HTML; fallback to TE
  connector. Graceful DataUnavailableError + PMI_SCRAPE_FAIL flag.
  Module docstring documents scraping fragility.
- **Unblocks:** E1 `pmi_composite` input for EA + non-US markets;
  ISM still primary for US.

### CAL-082 — ISM Manufacturing + Services connector (Week 5 ECS surfaced)

- **Priority:** MEDIUM
- **Trigger:** Week 5 ECS brief §Commit 5; descoped to CAL.
- **Scope:** `src/sonar/connectors/ism.py`. Primary via FRED
  `NAPM`/`NAPMII` series; fallback scrape ism.org monthly release.
  Graceful DataUnavailableError + ISM_UNAVAILABLE flag.
- **Unblocks:** US E1 (`pmi_composite`) + E4 (`ism_manufacturing`,
  `ism_services`).

### CAL-083 — FRED connector Economic-series extension (Week 5 ECS surfaced) (CLOSED 2026-04-20)

- **Priority:** LOW → **CLOSED 2026-04-20** via Sprint 2a Commit 3
  (`122d1b3`).
- **Trigger:** Week 5 ECS brief §Commit 6; descoped to CAL.
- **Scope (resolved):** `src/sonar/connectors/fred.py` adds the
  `# === Economic indicators ===` section with 23 helpers (raw-level
  path + YoY variants) + `FredEconomicObservation` dataclass. Delisted
  series route to CAL-092: `NAPM`, `NAPMII`, any `NFIB*`. Placeholder
  swaps: `CONCCONF` → `CSCICP03USM665S` (OECD CLI; OECD discontinued
  2024-01 → CAL-093); `MICHM5YM5` → `EXPINF5YR` (Cleveland Fed model).
- **Unblocks:** US coverage for E1/E3/E4 on the default FRED path.

### CAL-084 — Atlanta Fed wage tracker connector (Week 5 ECS surfaced)

- **Priority:** LOW
- **Trigger:** E3 `atlanta_fed_wage_yoy` missing without a dedicated
  connector. US-specific; without it the E3 compute flags
  `ATLANTA_FED_US_ONLY` and degrades gracefully.
- **Scope:** `src/sonar/connectors/atlanta_fed.py` — Atlanta Fed
  Wage Growth Tracker CSV at atlantafed.org/chcs/wage-growth-tracker.
- **Unblocks:** Full 10/10 E3 components for US.

### CAL-085 — EPU index scraper (Week 5 ECS surfaced)

- **Priority:** LOW
- **Trigger:** E4 `epu_index`. Primary is FRED `USEPUINDXD` (covered
  by CAL-083); direct policyuncertainty.com scraper only needed as
  fallback / validation.
- **Scope:** `src/sonar/connectors/policyuncertainty.py` scraping
  policyuncertainty.com monthly CSV.
- **Unblocks:** EPU fallback path.

### CAL-086 — ZEW + Ifo DE sentiment scrapers (CLOSED 2026-04-20)

- **Priority:** LOW → **CLOSED 2026-04-20** via Week 6 Sprint 1
  Commits 2-3 (`d1cd3ac`, `8e59498`).
- **Trigger:** E4 DE components `zew_expectations` +
  `ifo_business_climate`. Without them DE E4 drops to 3/13 components
  (below threshold → InsufficientDataError).
- **Scope (resolved):** TE Pro provides both headlines.
  `TEConnector.fetch_ifo_business_climate_de` → TE "business confidence"
  under germany (source: Ifo Institute, value matches Ifo Business
  Climate headline). `fetch_zew_economic_sentiment_de` → TE
  "zew economic sentiment index". Builder `build_e4_inputs` wires
  both when a TEConnector is supplied; flags
  `TE_FALLBACK_{IFO,ZEW}`. Dedicated
  `connectors/{zew,ifo}.py` scrapers become unnecessary. Re-open
  if/when TE ceases to serve these specific series.
- **Follow-up:** None.

### CAL-087 — BoJ Tankan connector (Week 5 ECS surfaced)

- **Priority:** LOW
- **Trigger:** E4 `tankan_large_mfg`. JP-only. Out of current T1
  7-country scope but noted for completeness.
- **Scope:** `src/sonar/connectors/boj.py` quarterly Tankan survey
  download.
- **Unblocks:** JP E4 coverage when JP enters T1.

### CAL-088 — `compute_all_economic_indices` orchestrator + CLI (Week 5 ECS surfaced)

- **Priority:** MEDIUM
- **Trigger:** Week 5 ECS brief §Commit 10 descoped.
- **Scope:** `src/sonar/indices/orchestrator.py` extension with
  `compute_all_economic_indices(country, date, session)` dispatching
  to E1 + E2 (existing) + E3 + E4; `--economic-only` and
  `--all-cycles` CLI flags on the top-level orchestrator CLI.
- **Unblocks:** Week 6 ECS composite preparatory orchestration.

### CAL-089 — `daily_economic_indices.py` pipeline (Week 5 ECS surfaced)

- **Priority:** LOW
- **Trigger:** Week 5 ECS brief §Commit 12 descoped.
- **Scope:** `src/sonar/pipelines/daily_economic_indices.py`
  mirroring `daily_credit_indices.py` + `daily_financial_indices.py`
  pattern with pluggable InputsBuilder (default empty). DB-backed
  builder follows once CAL-080/083 ingest historical series.
- **Unblocks:** Cron-able economic-indices daily run.

### CAL-090 — Week 5 ECS 7 T1 integration test (Week 5 ECS surfaced)

- **Priority:** LOW
- **Trigger:** Week 5 ECS brief §Commit 11 descoped.
- **Scope:** `tests/integration/test_economic_indices.py` with
  parametrized 7-country run, cassette-replayed connector fetches,
  assertions on score ranges + expected flags + persistence
  round-trip.
- **Unblocks:** End-to-end validation ahead of ECS composite.

### CAL-095 — Full HLW r* connector (Week 6 Sprint 1b surfaced)

- **Priority:** MEDIUM
- **Trigger:** M1 + M2 currently read r_star from
  `src/sonar/config/r_star_values.yaml` (hardcoded NY Fed Q4 2024
  values). Phase 1 workaround per user key decision; Phase 2+ needs
  proper connector for quarterly NY Fed HLW + Holston-Laubach-
  Williams EA equivalent releases.
- **Scope:** `src/sonar/connectors/hlw.py` polling
  https://www.newyorkfed.org/research/policy/rstar quarterly. Cross-
  validation: pulled values must match YAML for the most recent
  quarter (xval drift detection); CALIBRATION_STALE flag stays as
  per CCCS spec §2.
- **Unblocks:** Removes `last_updated` manual ritual; auto-refresh
  for r* across US/EA + future UK/JP/CA/AU additions.

### CAL-096 — FRED monetary-series extension (Week 6 Sprint 1b surfaced) — **CLOSED** (Week 6 Sprint 2b)

- **Priority:** MEDIUM
- **Trigger:** Week 6 Sprint 1b brief §Commit 3 descoped — connector
  layer not built. Compute layer ready but cannot persist live rows
  without FRED helpers for WALCL (Fed balance sheet), DTWEXBGS
  (USD NEER), MORTGAGE30US, NFCI / ANFCI, BAMLH0A0HYM2, PCEPILFE
  (verify if shipped earlier), VIXCLS (verify).
- **Scope:** `src/sonar/connectors/fred.py` extension under new
  `# === Monetary indicators ===` section with helper resolvers
  matching M1/M2/M4 input dataclass field names. Cassette-replay tests
  per series + slow-marked live canaries.
- **Unblocks:** Live M1 + M4 wiring for US.
- **Resolution (Week 6 Sprint 2b):** 10 new helpers shipped under
  `# === Monetary indicators (M1 / M2 / M4) === — CAL-096`:
  `fetch_fed_funds_target_upper_us` (DFEDTARU), `_lower_us`
  (DFEDTARL), `fetch_fed_funds_effective_us` (FEDFUNDS),
  `fetch_fed_balance_sheet_us` (WALCL), `fetch_pce_core_us`
  (PCEPILFE level) + `fetch_pce_core_yoy_us` (YoY via
  `_yoy_transform`), `fetch_usd_neer_us` (DTWEXBGS),
  `fetch_mortgage_30y_us` (MORTGAGE30US), `fetch_nfci_us` (NFCI),
  `fetch_potential_gdp_us` (GDPPOT). Cassette-replay tests +
  3 `@pytest.mark.slow` live canaries (DFEDTARU + PCEPILFE +
  DTWEXBGS) in `tests/unit/test_connectors/test_fred_monetary.py`.
  VIXCLS already shipped under CAL-083 (E4); BAMLH0A0HYM2 not
  required by M1/M2/M4 spec §4 (FCS scope). ANFCI deferred — NFCI
  alone is the M4 direct-path signal.

### CAL-097 — CBO output gap connector (Week 6 Sprint 1b surfaced) — **CLOSED** (Week 6 Sprint 2b)

- **Priority:** MEDIUM
- **Trigger:** Week 6 Sprint 1b brief §Commit 4 descoped. M2 needs
  output_gap_pct input (US primary).
- **Scope:** Path A — verify FRED `GDPPOT` (potential GDP) availability,
  compute gap = GDP / GDPPOT - 1; if absent, Path B = CBO Excel scrape
  with schema-drift guard. Start with Path A (trivial).
- **Unblocks:** Live M2 (US output_gap input).
- **Resolution (Week 6 Sprint 2b):** Path A (FRED GDPPOT) responded 200
  live during pre-flight. `src/sonar/connectors/cbo.py` shipped as a
  composition wrapper over `FredConnector` with
  `fetch_output_gap_us(start, end)` pairing `GDPC1` with `GDPPOT` on
  quarterly dates and returning `OutputGapObservation(gap=(a-p)/p, ...)`.
  `fetch_latest_output_gap_us(date, window_days=200)` handles BEA Q4
  advance-release lag. 6 unit tests + 1 `@pytest.mark.slow` live canary
  covering the 2Y window. Excel fallback deliberately not implemented —
  re-open only if GDPPOT is ever delisted.

### CAL-098 — ECB SDW M1-EA builder integration (Week 6 Sprint 1b surfaced) — **CLOSED** (Week 6 Sprint 2b)

- **Priority:** MEDIUM
- **Trigger:** Week 6 Sprint 1b brief §Commit 9 descoped. M1 EA
  needs ECB DFR (policy rate) + ILM (balance sheet) keys empirically
  validated.
- **Scope:** `src/sonar/indices/monetary/builders.py` with
  `build_m1_ea(...)` reading ECB SDW dataflow keys (DFR
  `M.U2.EUR.4F.KR.DFR.LEV` + ILM equivalent). Live key probing per
  CAL-019 BIS pattern.
- **Unblocks:** M1 EA persisted rows.
- **Resolution (Week 6 Sprint 2b, part 1 — connector layer):**
  Pre-flight live probe confirmed canonical keys:
  - DFR: ``FM/D.U2.EUR.4F.KR.DFR.LEV`` (daily, 3.0 % on 2024-12-18)
  - Eurosystem total assets: ``ILM/W.U2.C.T000000.Z5.Z01`` (weekly,
    ≈6.44T EUR on 2024-W41)

  `src/sonar/connectors/ecb_sdw.py` extended:
  - `_fetch_raw` now accepts a ``dataflow`` override (kept
    backward-compatible default ``YC``).
  - New `EcbMonetaryObservation` dataclass (generic, no tenor field).
  - `fetch_dfr_rate(start, end)` + `fetch_eurosystem_balance_sheet(start, end)`
    wrapping the new dataflow paths via `_fetch_monetary_series` helper.
  - `_parse_time_period` handles both daily ISO dates and weekly
    ``YYYY-Www`` periods (Friday-anchor per ECB weekly convention,
    since Python 3.11+ fromisoformat treats week-only strings as Monday).

  Part 2 (MonetaryInputsBuilder wiring) lands in C4 of this sprint.

### CAL-099 — Krippner / Wu-Xia shadow rate connector (Week 6 Sprint 1b surfaced)

- **Priority:** LOW
- **Trigger:** M1 spec §2 precondition allows shadow := policy when
  policy > 0.5% (above ZLB). Current US (~5%) + EA (~3%) above ZLB
  so workaround spec-compliant. Connector only needed when
  policy returns to ZLB territory (post-2008 US, 2020-22 EA periods).
- **Scope:** `src/sonar/connectors/krippner.py` (or wu_xia equivalent)
  polling Atlanta Fed Wu-Xia / Reserve Bank of NZ Krippner shadow rate
  series.
- **Unblocks:** Historical M1 backfill across ZLB periods.

### CAL-100 — Monetary input builders + integration smoke (Week 6 Sprint 1b surfaced) — **CLOSED** (Week 6 Sprint 2b C4+C5)

- **Priority:** MEDIUM
- **Trigger:** Week 6 Sprint 1b brief §Commits 9-10 descoped. End-to-
  end live persistence path needs builder layer + slow-marked
  canaries.
- **Scope:** `src/sonar/indices/monetary/builders.py` with
  `build_m{1,2,4}_inputs(country, date, fred_conn, ecb_sdw_conn,
  cbo_conn)`; `tests/integration/test_monetary_indices_live.py`
  with 4 @slow canaries for US M1/M2/M4 + M1 EA per brief §Commit 10.
- **Unblocks:** M1 + M2 + M4 US + M1 EA rows persisted for production
  date (2024-12-31). MSC composite Week 7+ depends on this.
- **Resolution (Week 6 Sprint 2b C4):** `src/sonar/indices/monetary/builders.py`
  ships four typed builders:
  - `build_m1_us_inputs(fred, date, history_years=30)`
  - `build_m1_ea_inputs(ecb_sdw, date, history_years=30, ea_gdp_eur_mn_resolver=None)`
    with `EXPECTED_INFLATION_PROXY` upstream flag until Week 7 SPF wiring.
  - `build_m2_us_inputs(fred, cbo, date, history_years=30)` with
    `INFLATION_FORECAST_PROXY_UMICH` flag.
  - `build_m4_us_inputs(fred, date, history_years=30)` direct-NFCI path.
  - `MonetaryInputsBuilder` facade holds all three connectors and
    dispatches on country; non-US/EA combinations raise
    `NotImplementedError` pointing to Week 7 backlog.

  Shared helpers: `_latest_on_or_before`, `_resample_monthly` (monthly
  end-of-month forward-fill), `_last_day_of_month`, `_to_dated` (generic
  observation → dated-value converter). 17 unit tests cover helpers +
  happy paths + dispatch guards. Integration smoke (4 slow canaries)
  lands in C5 of this sprint.

### CAL-102 — UMich 5Y inflation expectations FRED delisted, TE fallback wired (CLOSED 2026-04-20)

- **Priority:** LOW → **CLOSED 2026-04-20** via Week 6 Sprint 3
  Commits 2-4 (`4b6e037`, `bd76354`).
- **Trigger:** Sprint 2a live validation flagged FRED ``MICHM5YM5``
  (UMich 5-10Y inflation expectations) as delisted. Sprint 2a used
  FRED ``EXPINF5YR`` (Cleveland-Fed model-based 5Y expected
  inflation) as a substitute, but that is a distinct series — model
  output, not the survey.
- **Resolution:** ``TEConnector.fetch_michigan_5y_inflation_us``
  reaches the actual UMich survey series via TE indicator
  ``michigan 5 year inflation expectations`` →
  ``HistoricalDataSymbol=USAM5YIE``. Source-identity guard matches
  the same pattern as CAL-093. E4 builder takes TE as primary for
  the UMich 5Y slot (FRED Cleveland-Fed fallback remains); emits
  ``TE_FALLBACK_UMICH_5Y`` flag. Sprint 3 live smoke confirms the
  uplift: UMich 5Y slot now carries the actual survey reading.
- **Follow-up:** None.

### CAL-113 — BEI/SURVEY split in EXPINF sub_indicators (CLOSED 2026-04-21 via Sprint M)

- **Priority:** LOW — affects M3 diagnostic paths only; composite unchanged.
- **Trigger:** Sprint E retrospective (CAL-108 M3 DB-backed builder)
  §Deviations. EXPINF persistence in Sprint C unified all method
  outputs into a single ``expected_inflation_tenors`` dict, so
  ``build_m3_inputs_from_db`` could populate ``bei_10y_bps`` but
  ``survey_10y_bps`` was forced to ``None`` — M3 spec §2 expects
  both distinct fields.
- **Scope:**
  - `daily_overlays._compute_expected_inflation` emits a BEI/SURVEY
    split via three new ``sub_indicators`` keys: ``bei_tenors`` +
    ``survey_tenors`` + ``method_per_tenor``. The canonical unified
    ``expected_inflation_tenors`` dict stays for back-compat with any
    downstream consumer.
  - `build_m3_inputs_from_db` reads the split keys when present;
    falls back to unified tenors for pre-Sprint-M rows.
  - Backward compatibility preserved: old rows without the split
    keys populate ``bei_10y_bps`` and ``survey_10y_bps`` to
    ``None`` (prior behaviour).
- **Dependency:** Sprint C EXPINF persistence pattern + Sprint E M3
  DB-backed reader.
- **Status:** CLOSED 2026-04-21 via Sprint M Commits 3 + 4.

### CAL-128 — GB vs UK canonical country code rename (Sprint O — Week 8 Day 4)

- **Priority:** MEDIUM — ISO 3166-1 alpha-2 compliance + internal
  consistency debt. Non-critical path; backward compat preserves
  operator workflows during transition.
- **Trigger:** Sprint I retro §Deviations (2026-04-21). SONAR internal
  code uses `"UK"` for United Kingdom; canonical ISO 3166-1 alpha-2
  is `"GB"`. Inconsistent with all other T1 countries
  (US/DE/PT/IT/ES/FR/NL) which use canonical alpha-2. Affects TE
  mappings, config YAML, connector constants, pipeline dispatch,
  tier resolution, currency lookups.
- **Scope (Sprint O — partial closure):**
  - `docs/data_sources/country_tiers.yaml` iso_code: already `GB`
    (corrected pre-Sprint) with `aliases: [UK]` preserved.
  - `src/sonar/config/r_star_values.yaml` + `bc_targets.yaml`:
    top-level key `UK` → `GB`; loader adds `"UK"` alias normalization
    with deprecation log.
  - `src/sonar/connectors/te.py`: `TE_COUNTRY_NAME_MAP` +
    `TE_10Y_SYMBOLS` → `GB` primary; `UK` alias entries preserved.
    `TE_EXPECTED_SYMBOL_UK_BANK_RATE` renamed to
    `TE_EXPECTED_SYMBOL_GB_BANK_RATE` (alias `UK_*` re-export).
    `fetch_uk_bank_rate` → primary `fetch_gb_bank_rate`; UK wrapper
    emits deprecation warning.
  - `src/sonar/pipelines/daily_monetary_indices.py`:
    `MONETARY_SUPPORTED_COUNTRIES` → `("US", "EA", "GB")`;
    `--country UK` accepted as deprecated alias with structlog
    warning; internal dispatch translates `GB → UK` at
    builders.py boundary until final chore.
  - `src/sonar/cycles/financial_fcs.py`: `TIER_1_STRICT_COUNTRIES`
    frozenset includes both `GB` (canonical) + `UK` (transitional
    alias; removed post final chore).
  - `src/sonar/overlays/live_assemblers.py`, `overlays/crp.py`,
    `pipelines/daily_cost_of_capital.py`: benchmark/currency dicts
    rename `"UK"` → `"GB"`.
  - Tests sweep `tests/unit/` + `tests/integration/` country_code
    strings and expected values.
  - `docs/adr/ADR-0007-iso-country-codes.md` NEW — canonical
    decision + deprecation timeline.
  - **EXCLUDED (Sprint L carve-out)**: `src/sonar/indices/monetary/builders.py`
    UK builder references → post-both-merges chore commit sweeps
    `builders.py` (JP additions from Sprint L + pre-existing UK
    references) in one atomic change.
  - **EXCLUDED (archival)**: historical retrospectives referencing
    `UK` preserved verbatim.
- **Implementation:** Sprint O Week 8 Day 4 — isolated worktree
  `/home/macro/projects/sonar-wt-sprint-o` on branch
  `sprint-o-gb-uk-rename`. ~5-7 commits.
- **Closure action:** post both Sprint L + Sprint O merges, operator
  runs consolidated chore commit on main covering `builders.py`
  sweep (UK → GB primary + deprecated alias wrappers for
  `build_m1_uk_inputs`, constants). See `docs/planning/retrospectives/week8-sprint-o-gb-uk-rename-report.md`
  §Post-merge for operator runbook.
- **Closure commit (2026-04-22):** `178fc6b` swept `builders.py`
  (`build_m1_gb_inputs` canonical + `build_m1_uk_inputs` deprecated
  wrapper; `_gb_bank_rate_cascade`; `FRED_GB_BANK_RATE_SERIES` +
  `FRED_GB_GILT_10Y_SERIES` canonical with `FRED_UK_*` aliases;
  `GB_BANK_RATE_*` + `GB_BS_GDP_PROXY_ZERO` flag strings; dispatch
  canonicaliza `"UK"` → `"GB"` silently). Integration test renamed
  `test_daily_monetary_uk_te_cascade.py` → `test_daily_monetary_gb_te_cascade.py`.
  Backward-compat surfaces preserved (3 call sites):
  - `src/sonar/connectors/te.py::fetch_uk_bank_rate` (Sprint O).
  - `src/sonar/indices/monetary/builders.py::build_m1_uk_inputs`
    + `FRED_UK_BANK_RATE_SERIES` + `FRED_UK_GILT_10Y_SERIES` (este
    commit).
  - `src/sonar/pipelines/daily_monetary_indices.py::_warn_if_deprecated_alias`
    handles o `--country UK` CLI path (Sprint O).
  Alias removal scheduled Week 10 Day 1 per ADR-0007 §Review
  triggers #1.
- **Status:** CLOSED 2026-04-22 (Week 9 Day 1 chore commit `178fc6b`).
  Backward compat aliases preserved in builders.py, te.py, and
  daily_monetary_indices.py; removal Week 10 Day 1.

### CAL-128-FOLLOWUP — UK → GB rename carve-out files beyond Sprint O strict scope — **CLOSED** (Week 9 Sprint P)

- **Priority:** MEDIUM — completes ISO 3166-1 alpha-2 compliance started
  in CAL-128 (Sprint O).
- **Trigger:** Sprint O (Week 8 Day 4) resumed session narrowed the
  brief §1 literal scope to `config/*.yaml`, `connectors/te.py`,
  `connectors/boe_database.py`, `pipelines/daily_monetary_indices.py`,
  and corresponding tests. Earlier draft of CAL-128 (and ADR-0007
  scope table) listed additional consumer files where `"UK"` was
  still the canonical key. These were **not** touched by Sprint O
  and tracked under this follow-up.
- **Scope executed (Week 9 Sprint P, 2026-04-21):**
  - `src/sonar/cycles/financial_fcs.py` — `TIER_1_STRICT_COUNTRIES`
    frozenset member "UK" → "GB" + docstring "US/DE/UK/JP" →
    "US/DE/GB/JP". `_normalize_country_code()` wired into
    `resolve_tier()` with structlog deprecation warning.
  - `src/sonar/overlays/crp.py` —
    `BENCHMARK_COUNTRIES_BY_CURRENCY["GBP"]` value "UK" → "GB".
    `_normalize_country_code()` wired into `is_benchmark()`.
  - `src/sonar/overlays/live_assemblers.py` —
    `BENCHMARK_BY_CURRENCY["GBP"]` value + `_DEFAULT_CURRENCY_BY_COUNTRY`
    key + `build_crp_from_live` docstring all flipped to "GB".
    `_normalize_country_code()` wired into `LiveInputsBuilder.__call__`
    + `build_crp_from_live`.
  - `src/sonar/pipelines/daily_cost_of_capital.py` —
    `COUNTRY_TO_CURRENCY` key "UK" → "GB".
    `_normalize_country_code()` wired into `main()` CLI entry +
    `run_one()`.
  - All four source modules emit a structlog
    `*.deprecated_country_alias` event with
    `deprecation_target="CAL-128-alias-removal-week10"` on alias
    encounter; canonical codes silent.
  - Each module ships 1+ backward-compat test verifying the "UK"
    alias still resolves correctly and emits the structlog warning
    (capsys-captured).
- **Out-of-scope references observed but preserved** (Sprint O
  deprecated-alias surfaces, remove Week 10 Day 1):
  - `config/bc_targets.yaml`, `config/r_star_values.yaml` — loader
    alias comments.
  - `connectors/te.py` — `fetch_uk_bank_rate` deprecated wrapper +
    `TE_*_UK_*` constants re-exported.
  - `pipelines/daily_monetary_indices.py` — CLI alias + tuple +
    dispatch normaliser.
  - `indices/monetary/_config.py`, `indices/monetary/builders.py` —
    Sprint L + Week 9 chore sweep alias-preservation surfaces.
  - `scripts/backfill_l5.py:93` — comment-only CLI contract note
    (describes `--country UK` opt-in; consistent with deprecated
    alias posture).
- **Carve-out rationale:** `builders.py` was Sprint L's parallel-worktree
  domain; touching the overlay / cycle / cost-of-capital consumers was
  flagged as scope creep in the resumed Sprint O session. Consolidated
  into this dedicated follow-up on branch `sprint-p-cal-128-followup`
  (worktree `/home/macro/projects/sonar-wt-sprint-p`).
- **Alias removal:** Week 10 Day 1 per ADR-0007 §Review triggers #1;
  removal commit will strip `_DEPRECATED_COUNTRY_ALIASES`
  +`_normalize_country_code()` across all four Sprint P modules + the
  Sprint O surfaces listed above.
- **Status:** CLOSED 2026-04-21 (Week 9 Sprint P — 4 feature commits
  + this backlog closure commit `cacc57c` + retrospective commit
  `ce2c7d6`). Backward compat aliases preserved in all four modules;
  removal Week 10 Day 1.

### CAL-119 — JP country monetary (M2 T1 Core) — **PARTIALLY CLOSED** (Week 8 Sprint L — M1 level)

- **Priority:** MEDIUM — M2 T1 Core milestone blocker (alongside UK /
  CAL-118).
- **Trigger:** M1/US scorecard flagged UK + JP as the two deferred
  Tier-1 countries (`docs/milestones/m1-us.md` §Coverage).
- **Scope:**
  - `src/sonar/connectors/boj.py` new BoJ Time Series Database
    connector scaffold (Sprint L C2).
  - `src/sonar/connectors/te.py` `fetch_jp_bank_rate` wrapper with
    `BOJDTR` source-drift guard (Sprint L C1).
  - `src/sonar/indices/monetary/builders.py` `build_m1_jp_inputs`
    TE → BoJ → FRED cascade (Sprint L C4); `build_m2_jp_inputs` +
    `build_m4_jp_inputs` wire-ready scaffolds (Sprint L C5).
  - JP entries in `country_tiers.yaml` + `r_star_values.yaml` +
    `bc_targets.yaml` (Sprint L C3).
  - `daily_monetary_indices.py` JP country support (Sprint L C6).
- **Resolution (Week 8 Sprint L, M1 level):** JP M1 live via TE primary
  cascade; persisted row emits `JP_BANK_RATE_TE_PRIMARY` + `R_STAR_PROXY`
  + `EXPECTED_INFLATION_CB_TARGET` + `JP_BS_GDP_PROXY_ZERO` flags.
  BoJ TSD native path preserved wire-ready (browser-gated portal).
  FRED OECD mirror demoted to last-resort with `JP_BANK_RATE_FRED_FALLBACK_STALE`
  + `CALIBRATION_STALE` flags.
- **Remaining:** M2/M4/M3 JP paths via CAL-120 / CAL-121 / CAL-122.
- **Status:** PARTIALLY CLOSED — M1 only (Week 8 Sprint L;
  retrospective `week8-sprint-l-boj-connector-report.md`). Full close
  pending CAL-120 through CAL-123 landing.

### CAL-120 — JP M2 output-gap source (Week 8 Sprint L surfaced)

- **Status:** merged into `CAL-M2-T1-OUTPUT-GAP-EXPANSION` on
  2026-04-22 (Week 10 Day 0 consolidation). See that item for T1 scope
  + per-country sources.

### CAL-121 — JP M4 FCI 5-component bundle (Week 8 Sprint L surfaced)

- **Status:** merged into `CAL-M4-T1-FCI-EXPANSION` on 2026-04-22
  (Week 10 Day 0 consolidation). See that item for T1 scope +
  per-country sources.

### CAL-122 — JP M3 market-expectations overlays (Week 8 Sprint L surfaced)

- **Status:** merged into `CAL-M3-T1-EXPANSION` on 2026-04-22
  (Week 10 Day 0 consolidation). See that item for T1 scope +
  per-country sources.

### CAL-123 — JP balance-sheet / GDP ratio wiring (Week 8 Sprint L surfaced)

- **Status:** merged into `CAL-BS-GDP-T1-EXPANSION` on 2026-04-22
  (Week 10 Day 0 consolidation). See that item for T1 scope +
  per-country sources.

### CAL-124 — BoJ TSD browser-gate bypass (Week 8 Sprint L surfaced)

- **Priority:** DORMANT — opens only if BoJ portal exposes a scriptable
  endpoint or operator policy allows a proxy.
- **Trigger:** Sprint L C2 probe confirmed the BoJ TSD "FAME" portal is
  browser-gated (JavaScript-rendered landing + session-cookie CSV
  export), analogous to BoE IADB's Akamai gate.
- **Scope:** evaluate ProtonVPN / similar proxy OR official BoJ API
  application if one becomes available.
- **Unblocks:** `BoJConnector.fetch_bank_rate` native path → JP cascade
  secondary slot becomes live (currently always fails over to FRED).
- **Status:** OPEN (dormant).

### CAL-125 — JP 10Y JGB yield direct FRED path (Week 8 Sprint L surfaced)

- **Priority:** LOW — secondary-slot redundancy.
- **Trigger:** Sprint L C4 shipped `FRED_JP_JGB_10Y_SERIES =
  "IRLTLT01JPM156N"` constant but the current M1/M2/M4 JP path fetches
  10Y JGB yield via TE `GJGB10:IND` through existing
  `fetch_sovereign_yield_historical`. FRED path is a monthly-cadence
  fallback for when TE 10Y is unavailable.
- **Scope:** wire the FRED 10Y path into the JP cascade analog (only
  when M4 JP lands under CAL-121) with `JP_10Y_FRED_FALLBACK_STALE`
  flag.
- **Unblocks:** full cascade symmetry between M1 and M4 JP paths.
- **Status:** OPEN.

### CAL-126 — JP CPI YoY wrapper (Week 8 Sprint L surfaced)

- **Status:** merged into `CAL-CPI-INFL-T1-WRAPPERS` on 2026-04-22
  (Week 10 Day 0 consolidation). See that item for T1 scope +
  per-country sources.

### CAL-129 — CA country monetary (M2 T1 Core) — **PARTIALLY CLOSED** (Week 9 Sprint S — M1 level)

- **Priority:** MEDIUM — M2 T1 Core milestone progression (8 → 9
  countries monetary M1 live; symmetric close of the Sprint I / L /
  S family).
- **Trigger:** M1/US scorecard flagged CA as a deferred Tier-1
  country alongside UK + JP. Sprint S ships CA as the third country
  in the Sprint I-patch cascade family.
- **Scope:**
  - `src/sonar/connectors/boc.py` new BoC Valet public API connector
    (Sprint S C2) — first native connector in the cascade family to
    land reachable primary-class (contrast BoE / BoJ which are both
    browser-gated).
  - `src/sonar/connectors/te.py` `fetch_ca_bank_rate` wrapper with
    `CCLR` source-drift guard (Sprint S C1).
  - `src/sonar/indices/monetary/builders.py` `build_m1_ca_inputs`
    TE → BoC Valet → FRED cascade (Sprint S C4); `build_m2_ca_inputs`
    + `build_m4_ca_inputs` wire-ready scaffolds (Sprint S C4).
  - CA entries in `r_star_values.yaml` (Sprint S C3); CA already
    present in `country_tiers.yaml` + `bc_targets.yaml`.
  - `daily_monetary_indices.py` CA country support (Sprint S C5).
  - `FredConnector.FRED_SERIES_TENORS` extended with OECD mirror
    series for CA + GB + JP (Sprint S C5 — also unblocked the JP
    FRED-fallback live canary which was silently broken).
- **Resolution (Week 9 Sprint S, M1 level):** CA M1 live via TE
  primary cascade; persisted row emits `CA_BANK_RATE_TE_PRIMARY` +
  `R_STAR_PROXY` + `EXPECTED_INFLATION_CB_TARGET` +
  `CA_BS_GDP_PROXY_ZERO` flags. BoC Valet native path **live** (not a
  wire-ready scaffold like BoJ) — when TE fails, cascade lands
  `CA_BANK_RATE_BOC_NATIVE` without staleness. FRED OECD mirror
  (`IRSTCI01CAM156N`) demoted to last-resort with
  `CA_BANK_RATE_FRED_FALLBACK_STALE` + `CALIBRATION_STALE` flags.
- **Remaining:** M2/M4/M3 CA paths via CAL-130 / CAL-131 / CAL-132.
- **Status:** PARTIALLY CLOSED — M1 only (Week 9 Sprint S; retro
  commit `683e872`). Full close pending CAL-130 through CAL-133
  landing.

### CAL-130 — CA M2 output-gap source (Week 9 Sprint S surfaced)

- **Status:** merged into `CAL-M2-T1-OUTPUT-GAP-EXPANSION` on
  2026-04-22 (Week 10 Day 0 consolidation).

### CAL-131 — CA M4 FCI 5-component bundle (Week 9 Sprint S surfaced)

- **Status:** merged into `CAL-M4-T1-FCI-EXPANSION` on 2026-04-22
  (Week 10 Day 0 consolidation).

### CAL-132 — CA M3 market-expectations overlays (Week 9 Sprint S surfaced)

- **Status:** merged into `CAL-M3-T1-EXPANSION` on 2026-04-22
  (Week 10 Day 0 consolidation).

### CAL-133 — CA balance-sheet / GDP ratio wiring (Week 9 Sprint S surfaced)

- **Status:** merged into `CAL-BS-GDP-T1-EXPANSION` on 2026-04-22
  (Week 10 Day 0 consolidation).

### CAL-134 — CA CPI YoY wrapper (Week 9 Sprint S surfaced)

- **Status:** merged into `CAL-CPI-INFL-T1-WRAPPERS` on 2026-04-22
  (Week 10 Day 0 consolidation).

### CAL-135 — CA inflation-forecast wrapper (Week 9 Sprint S surfaced)

- **Status:** merged into `CAL-CPI-INFL-T1-WRAPPERS` on 2026-04-22
  (Week 10 Day 0 consolidation).

### CAL-136 — BIS SDMX v2 API migration (CLOSED 2026-04-21 via Sprint AA)

- **Priority:** URGENT — resolved.
- **Trigger:** Sprint S-CA discovery Week 9 Day 1 evening that
  `sonar-daily-bis-ingestion.timer` was disabled and manual triggers
  produced 0 rows in `bis_credit_raw`. Initial hypothesis was a BIS
  URL path retirement / jsondata format removal.
- **Scope:** src/sonar/connectors/bis.py URL + Accept header + version
  map tightening; tests/fixtures/bis/*.json cassette refresh;
  src/sonar/pipelines/daily_bis_ingestion.py lookback window fix;
  live-canary teardown bug; systemd timer re-enable preparation.
- **Resolution:**
  1. URL migration already landed in commit 7abded7 (credit c2/10,
     2026-04-20). Sprint AA c2 formalised three residual gaps: strict
     Accept header (drop ``, application/json`` alternate),
     `format=jsondata` param drop, `DATAFLOW_VERSIONS: Final[dict[str,
     str]]` single-source-of-truth dict.
  2. Parser regression-locked against live 2026-04-21 response
     (`tests/fixtures/bis/ws_tc_US_live_2024h1.json`) — no code change
     needed.
  3. Cassette refresh scope: 3 representative fixtures (HALT-3
     pragmatic budget) covering all orthogonal parser paths.
  4. **Root cause of actual production outage: DEFAULT_LOOKBACK_DAYS
     = 90 vs. BIS ~2-quarter publication lag**. On 2026-04-21 the
     90-day window mapped to startPeriod=2026-Q1 which returns HTTP
     404 because no 2026 observations are published yet. Raised to
     540 days (6 quarters) — window always overlaps ≥ 4 published
     quarters.
  5. Live-canary asyncio teardown fix — single `asyncio.run()` wrap,
     `httpx.AsyncClient` lifecycle confined to one event loop.
- **Validation:** Manual ingestion 21/21 fetches succeeded, 147 rows
  in `bis_credit_raw` spanning 7 T1 × 3 dataflows. Historical WS_TC
  backfill 2000-2025-Q3 landed 103 × 7 = 721 rows. Credit-indices
  manual trigger persisted L1 + L2 for all 7 T1 countries on
  2025-09-30.
- **Status:** CLOSED 2026-04-21.
- **Commits:** `36d3c9f` / `13ac228` / `7e7d70d` / `eb41608` /
  `750c224` / c6 (this file) on branch
  `sprint-aa-bis-v2-migration`.
- **Report:**
  [`../planning/retrospectives/week9-sprint-aa-bis-v2-migration-report.md`](../planning/retrospectives/week9-sprint-aa-bis-v2-migration-report.md).
- **Post-merge operator action:** `sudo systemctl enable --now
  sonar-daily-{bis-ingestion,credit-indices}.timer` —- deferred
  from Sprint AA because the CC session lacked passwordless sudo.

### CAL-137 — Weekly BIS live-canary surveillance (Week 9 Sprint AA)

- **Priority:** MEDIUM — prevents the same silent-failure class as
  the CAL-136 incident.
- **Trigger:** The 2026-04-14..2026-04-21 outage went undetected for
  ~7 days because only mocked tests ran on every push while the live
  canary was `@pytest.mark.slow`-gated and therefore skipped by
  default. Weekly live canaries are the minimum nightly-enough
  cadence that catches API drift / publication-lag bugs before the
  downstream credit indices go stale for multiple quarters.
- **Scope:**
  - New `deploy/systemd/sonar-weekly-bis-canary.service` +
    `.timer` unit pair.
  - Service command: `uv run pytest tests/integration/test_bis_ingestion.py
    -m slow -k bis --tb=line` with `StandardOutput=journal`.
  - Timer `OnCalendar=Mon 04:00` (UTC) — runs before the 05:00 BIS
    ingestion timer so an API drift surfaces before the main daily
    pipeline hits it.
  - Failure handler: `OnFailure=sonar-canary-alert@%n.service`
    (systemd dropin) that emails operator with journal tail + exit
    code.
- **Unblocks:** Ongoing BIS drift detection + provides a template
  for weekly live canaries on other connectors (FRED, ECB, BIS-SPP,
  BoE, BoJ, BoC, RBA).
- **Status:** OPEN.

### CAL-AU — AU country monetary (M2 T1 Core) — **PARTIALLY CLOSED** (Week 9 Sprint T — M1 level)

- **Priority:** MEDIUM — M2 T1 Core milestone progression (9 → 10
  countries monetary M1 live; extends the Sprint I / L / S family to
  Australia). Mirrors CAL-118 (UK) / CAL-119 (JP) / CAL-129 (CA).
- **Trigger:** M2 T1 Core milestone listed AU as the next country after
  CA. Sprint T ships AU as the fourth country in the Sprint I-patch
  cascade family.
- **Scope:**
  - `src/sonar/connectors/rba.py` new RBA statistical-tables connector
    (Sprint T C2) — first native connector in the cascade family to
    consume **public static CSVs** rather than a JSON REST API (BoC
    Valet) or a gated portal (BoE IADB / BoJ TSD). Serves F1
    (Cash Rate Target `FIRMMCRTD`) and F2 (AGB 10Y `FCMYGBAG10D`);
    Akamai edge cleared with a descriptive `SONAR/2.0` user-agent.
  - `src/sonar/connectors/te.py` `fetch_au_cash_rate` wrapper with
    `RBATCTR` source-drift guard (Sprint T C1).
  - `src/sonar/indices/monetary/builders.py` `build_m1_au_inputs` TE →
    RBA F1 → FRED cascade (Sprint T C4); `build_m2_au_inputs` +
    `build_m4_au_inputs` wire-ready scaffolds (Sprint T C4).
  - AU entries in `r_star_values.yaml` (Sprint T C3); AU already
    present in `country_tiers.yaml` + `bc_targets.yaml`.
  - `daily_monetary_indices.py` AU country support (Sprint T C5).
  - `FredConnector.FRED_SERIES_TENORS` extended with
    `IRSTCI01AUM156N` + `IRLTLT01AUM156N` (Sprint T C5).
- **Resolution (Week 9 Sprint T, M1 level):** AU M1 live via TE
  primary cascade; persisted row emits `AU_CASH_RATE_TE_PRIMARY` +
  `R_STAR_PROXY` + `EXPECTED_INFLATION_CB_TARGET` +
  `AU_BS_GDP_PROXY_ZERO` flags. RBA F1 CSV native path **live** (not a
  wire-ready scaffold like BoE / BoJ) — when TE fails, cascade lands
  `AU_CASH_RATE_RBA_NATIVE` without staleness (parallel to the CA
  BoC-Valet slot Sprint S shipped). FRED OECD mirror
  (`IRSTCI01AUM156N`) demoted to last-resort with
  `AU_CASH_RATE_FRED_FALLBACK_STALE` + `CALIBRATION_STALE` flags.
- **Remaining:** M2/M4/M3 AU paths via CAL-AU-GAP / CAL-AU-M4-FCI /
  CAL-AU-M3.
- **Status:** PARTIALLY CLOSED — M1 only (Week 9 Sprint T-AU; retro
  commit `1acd0be`). Full close pending CAL-AU-GAP / CAL-AU-M4-FCI /
  CAL-AU-M3 / CAL-AU-BS-GDP / CAL-AU-CPI / CAL-AU-INFL-FORECAST
  landing.

### CAL-AU-GAP — AU M2 output-gap source (Week 9 Sprint T surfaced)

- **Status:** merged into `CAL-M2-T1-OUTPUT-GAP-EXPANSION` on
  2026-04-22 (Week 10 Day 0 consolidation).

### CAL-AU-M4-FCI — AU M4 FCI 5-component bundle (Week 9 Sprint T surfaced)

- **Status:** merged into `CAL-M4-T1-FCI-EXPANSION` on 2026-04-22
  (Week 10 Day 0 consolidation).

### CAL-AU-M3 — AU M3 market-expectations overlays (Week 9 Sprint T surfaced)

- **Status:** merged into `CAL-M3-T1-EXPANSION` on 2026-04-22
  (Week 10 Day 0 consolidation).

### CAL-AU-BS-GDP — AU balance-sheet / GDP ratio wiring (Week 9 Sprint T surfaced)

- **Status:** merged into `CAL-BS-GDP-T1-EXPANSION` on 2026-04-22
  (Week 10 Day 0 consolidation).

### CAL-AU-CPI — AU CPI YoY wrapper (Week 9 Sprint T surfaced)

- **Status:** merged into `CAL-CPI-INFL-T1-WRAPPERS` on 2026-04-22
  (Week 10 Day 0 consolidation).

### CAL-AU-INFL-FORECAST — AU inflation-forecast wrapper (Week 9 Sprint T surfaced)

- **Status:** merged into `CAL-CPI-INFL-T1-WRAPPERS` on 2026-04-22
  (Week 10 Day 0 consolidation).

### CAL-NZ — NZ country monetary (M2 T1 Core) — **PARTIALLY CLOSED** (Week 9 Sprint U-NZ — M1 level)

- **Priority:** MEDIUM — M2 T1 Core milestone progression (10 → 11
  countries monetary M1 live; extends the Sprint I / L / S / T family
  to New Zealand). Mirrors CAL-118 (UK) / CAL-119 (JP) / CAL-129 (CA)
  / CAL-AU (AU).
- **Trigger:** M2 T1 Core milestone listed NZ as the next country
  after AU. Sprint U-NZ ships NZ as the fifth country in the Sprint
  I-patch cascade family.
- **Scope:**
  - `src/sonar/connectors/rbnz.py` new RBNZ statistical-tables
    connector (Sprint U-NZ C2) — wire-ready CSV parser for RBNZ
    B-series tables + perimeter-block detection. Ships raising
    `DataUnavailableError` against the live host (see
    CAL-NZ-RBNZ-TABLES).
  - `src/sonar/connectors/te.py` `fetch_nz_ocr` wrapper with
    `NZOCRS` source-drift guard (Sprint U-NZ C1).
  - `src/sonar/indices/monetary/builders.py` `build_m1_nz_inputs` TE
    → RBNZ → FRED cascade (Sprint U-NZ C4); `build_m2_nz_inputs` +
    `build_m4_nz_inputs` wire-ready scaffolds (Sprint U-NZ C4).
  - NZ entries in `r_star_values.yaml` + `bc_targets.yaml` (Sprint
    U-NZ C3); NZ already present in `country_tiers.yaml` as Tier 1.
  - `daily_monetary_indices.py` NZ country support + RBNZConnector
    in `_build_live_connectors` (Sprint U-NZ C5).
  - `FredConnector.FRED_SERIES_TENORS` extended with
    `IRSTCI01NZM156N` + `IRLTLT01NZM156N` (Sprint U-NZ C5).
- **Resolution (Week 9 Sprint U-NZ, M1 level):** NZ M1 live via TE
  primary cascade; persisted row emits `NZ_OCR_TE_PRIMARY` +
  `R_STAR_PROXY` + `EXPECTED_INFLATION_CB_TARGET` +
  `NZ_BS_GDP_PROXY_ZERO` flags. RBNZ B2 CSV native path ships as a
  **wire-ready scaffold raising** (not a live-reachable slot like
  AU/CA) — the www.rbnz.govt.nz host perimeter-403s the SONAR VPS
  egress regardless of User-Agent (Sprint U-NZ empirical probe
  2026-04-21). When TE fails, the cascade records
  `NZ_OCR_RBNZ_UNAVAILABLE` and falls through to FRED with
  `NZ_OCR_FRED_FALLBACK_STALE` + `CALIBRATION_STALE`. FRED OECD
  mirror (`IRSTCI01NZM156N`) is the demoted last-resort slot.
- **Remaining:** M2/M4/M3 NZ paths via CAL-NZ-M2-OUTPUT-GAP /
  CAL-NZ-M4-FCI / CAL-NZ-M3; RBNZ host unblock via
  CAL-NZ-RBNZ-TABLES.
- **Status:** PARTIALLY CLOSED — M1 only (Week 9 Sprint U-NZ; retro
  commit `b86757c`). Full close pending CAL-NZ-M2-OUTPUT-GAP /
  CAL-NZ-M4-FCI / CAL-NZ-M3 / CAL-NZ-BS-GDP / CAL-NZ-CPI /
  CAL-NZ-INFL-FORECAST / CAL-NZ-RBNZ-TABLES landing.

### CAL-NZ-RBNZ-TABLES — RBNZ statistics host perimeter block (Week 9 Sprint U-NZ surfaced)

- **Priority:** MEDIUM — unblocks NZ native secondary slot (daily
  RBNZ-sourced OCR + long-maturity yields) that currently delegates
  to FRED OECD mirror (monthly lag).
- **Trigger:** Sprint U-NZ pre-flight probe (2026-04-21) found the
  www.rbnz.govt.nz host returns HTTP 403 `Website unavailable`
  (Akamai-style perimeter page) for every probed path —
  `/statistics` index, `/-/media/project/sites/rbnz/files/statistics/...`
  media paths, `/robots.txt`, root `/` — under both generic
  `Mozilla/5.0` and descriptive `SONAR/2.0` user-agents. The block
  is host / IP-scoped, not UA-scoped, so the Sprint T-AU UA-gate fix
  does not unlock it from the SONAR VPS egress. Likely root cause:
  geo / ASN-based filtering at the RBNZ edge (historically enforced
  for a subset of foreign cloud providers).
- **Scope:**
  - Retry the perimeter probe periodically (e.g. quarterly) in case
    the block lifts.
  - If persistent, investigate SONAR VPS egress IP allowlisting with
    RBNZ operator contact — or route NZ-native probes through a
    different egress (Cloudflare worker / NZ-residing proxy).
  - Once reachable, empirically validate the B2-daily CSV schema
    (header / Series ID / data-row format) against the connector's
    parser — the current implementation mirrors the RBA F-table
    pattern with a `YYYY-MM-DD` date axis, which is the most likely
    shape but unvalidated against a real payload.
  - Extend the RBNZ connector with `fetch_government_10y` (B2 weekly
    long-maturity series) once the host is reachable.
  - Flip the `test_live_canary_rbnz_ocr_expects_block` pytest canary
    from "expected DataUnavailable" to a band assertion
    (OCR ∈ [0.25, 5.50]% historically).
- **Unblocks:** `NZ_OCR_RBNZ_NATIVE` flag on M1 NZ row when TE fails
  + future NZ M4 10Y component (CAL-NZ-M4-FCI).
- **Status:** OPEN (wire-ready; scaffold already raises cleanly).

### CAL-NZ-M2-OUTPUT-GAP — NZ M2 output-gap source (Week 9 Sprint U-NZ surfaced)

- **Status:** merged into `CAL-M2-T1-OUTPUT-GAP-EXPANSION` on
  2026-04-22 (Week 10 Day 0 consolidation). Note: NZ also depends on
  CAL-NZ-RBNZ-TABLES host-block remediation (tracked separately).

### CAL-NZ-M4-FCI — NZ M4 FCI 5-component bundle (Week 9 Sprint U-NZ surfaced)

- **Status:** merged into `CAL-M4-T1-FCI-EXPANSION` on 2026-04-22
  (Week 10 Day 0 consolidation). Note: NZ vol-index and corporate-
  yield components partly depend on CAL-NZ-RBNZ-TABLES.

### CAL-NZ-M3 — NZ M3 market-expectations overlays (Week 9 Sprint U-NZ surfaced)

- **Status:** merged into `CAL-M3-T1-EXPANSION` on 2026-04-22
  (Week 10 Day 0 consolidation).

### CAL-NZ-BS-GDP — NZ balance-sheet / GDP ratio wiring (Week 9 Sprint U-NZ surfaced)

- **Status:** merged into `CAL-BS-GDP-T1-EXPANSION` on 2026-04-22
  (Week 10 Day 0 consolidation). Note: NZ balance-sheet series partly
  depend on CAL-NZ-RBNZ-TABLES host unblock.

### CAL-CH — CH country monetary (M2 T1 Core) — **PARTIALLY CLOSED** (Week 9 Sprint V — M1 level)

- **Priority:** CLOSED at M1; remaining M2/M3/M4 levels tracked as
  separate CAL-CH-* items. Mirrors CAL-AU (Sprint T) / CAL-129 (CA) /
  CAL-119 (JP) / CAL-118 (GB).
- **Trigger:** CH was the fourth G10 country after the UK/JP/CA/AU
  quartet that still lacked M1 live. Sprint V ships CH as the fifth
  country in the Sprint I-patch TE-primary cascade expansion — and
  introduces the **first negative-rate era flag** in the monetary
  cascade family, required because the SNB policy rate sat at
  -0.75 % from 2014-12-18 through 2022-08-31 and Sprint V must
  preserve the sign throughout.
- **Scope delivered:**
  - `SNBConnector` for the SNB data portal (Sprint V C2) —
    semicolon-delimited public CSVs at
    `data.snb.ch/api/cube/{cube_id}/data/csv/en`; first connector
    to consume the SNB cube API in the monetary family. Two cubes
    wired: `zimoma` (SARON row — monthly overnight rate) and
    `rendoblim` (10Y Confederation bond yield).
  - `TEConnector.fetch_ch_policy_rate` wrapper with `SZLTTR`
    source-drift guard (Sprint V C1). The SZLTTR symbol is TE's
    legacy "Swiss LIBOR Target Rate" identifier preserved across
    the 2019 SNB regime change (3M-CHF-LIBOR target → directly-set
    policy rate).
  - `build_m1_ch_inputs` + `_ch_policy_rate_cascade` with TE → SNB →
    FRED cascade (Sprint V C4) including
    `CH_NEGATIVE_RATE_ERA_DATA` flag whenever the resolved window
    contains ≥ 1 strictly-negative observation;
    `build_m2_ch_inputs` + `build_m4_ch_inputs` wire-ready
    scaffolds (Sprint V C4).
  - CH entries in `r_star_values.yaml` (0.25 % proxy per SNB WP
    2024-09) + `bc_targets.yaml` (SNB 1 % band midpoint per SNB
    0-2 % price-stability definition) (Sprint V C3).
  - `daily_monetary_indices.py` CH country support + SNB connector
    instantiation (Sprint V C5).
  - `FredConnector.FRED_SERIES_TENORS` extended with
    `IRSTCI01CHM156N` + `IRLTLT01CHM156N` (Sprint V C5).
- **Resolution (Week 9 Sprint V, M1 level):** CH M1 live via TE
  primary cascade; persisted row emits `CH_POLICY_RATE_TE_PRIMARY` +
  `R_STAR_PROXY` + `EXPECTED_INFLATION_CB_TARGET` +
  `CH_INFLATION_TARGET_BAND` + `CH_BS_GDP_PROXY_ZERO` flags. SNB
  native path **live** (monthly cadence; no `CALIBRATION_STALE`
  since SNB policy-rate changes are quarterly). FRED OECD mirror
  (`IRSTCI01CHM156N`, last observed 2024-03) demoted to last-resort
  with `CH_POLICY_RATE_FRED_FALLBACK_STALE` + `CALIBRATION_STALE`
  flags. When any cascade-resolved observation is strictly-negative
  (e.g. 2014-2022 window), cascade additionally emits
  `CH_NEGATIVE_RATE_ERA_DATA`.
- **Known gap (spec §4 step 2 ZLB gate):** at negative policy
  rates, M1 compute raises `InsufficientDataError` because no
  Krippner shadow-rate connector is wired at Sprint V scope — this
  is spec-correct behaviour, surfaced during the C5 canary with a
  2020 anchor. Krippner integration is Phase 2+ scope (CAL-KRIPPNER
  — not opened Sprint V; bundled with L5 regime-classifier
  enhancements).
- **Remaining:** M2/M4/M3 CH paths via CAL-CH-GAP / CAL-CH-M4-FCI /
  CAL-CH-M3.
- **Status:** PARTIALLY CLOSED — M1 only (Week 9 Sprint V-CH; retro
  commit `d837558`). Full close pending CAL-CH-GAP / CAL-CH-M4-FCI /
  CAL-CH-M3 / CAL-CH-BS-GDP / CAL-CH-CPI / CAL-CH-INFL-FORECAST
  landing.

### CAL-CH-GAP — CH M2 output-gap source (Week 9 Sprint V surfaced)

- **Status:** merged into `CAL-M2-T1-OUTPUT-GAP-EXPANSION` on
  2026-04-22 (Week 10 Day 0 consolidation).

### CAL-CH-M4-FCI — CH M4 FCI 5-component bundle (Week 9 Sprint V surfaced)

- **Status:** merged into `CAL-M4-T1-FCI-EXPANSION` on 2026-04-22
  (Week 10 Day 0 consolidation). Note: CH balance sheet is
  structurally unusual (large forex-intervention base from 2011-2015
  CHF-floor regime) — interpretation differs from peer countries.

### CAL-CH-M3 — CH M3 market-expectations overlays (Week 9 Sprint V surfaced)

- **Status:** merged into `CAL-M3-T1-EXPANSION` on 2026-04-22
  (Week 10 Day 0 consolidation). Note: SNB does not issue inflation-
  indexed Confederation bonds, so EXPINF overlay relies on the
  0-2 % SNB band midpoint (1 %) as CB-target proxy — no direct
  breakeven series.

### CAL-CH-BS-GDP — CH balance-sheet / GDP ratio wiring (Week 9 Sprint V surfaced)

- **Status:** merged into `CAL-BS-GDP-T1-EXPANSION` on 2026-04-22
  (Week 10 Day 0 consolidation). Note: CH balance-sheet is
  structurally unusual — large forex-intervention asset base dating
  from 2011-2015 CHF-floor regime — so the zero-seed is especially
  visible and the ratio carries a non-standard interpretation.

### CAL-NZ-CPI — NZ CPI YoY wrapper (Week 9 Sprint U-NZ surfaced)

- **Status:** merged into `CAL-CPI-INFL-T1-WRAPPERS` on 2026-04-22
  (Week 10 Day 0 consolidation).

### CAL-NZ-INFL-FORECAST — NZ inflation-forecast wrapper (Week 9 Sprint U-NZ surfaced)

- **Status:** merged into `CAL-CPI-INFL-T1-WRAPPERS` on 2026-04-22
  (Week 10 Day 0 consolidation). Note: RBNZ MPS scraping partly
  depends on CAL-NZ-RBNZ-TABLES host unblock.

### CAL-CH-CPI — CH CPI YoY wrapper (Week 9 Sprint V surfaced)

- **Status:** merged into `CAL-CPI-INFL-T1-WRAPPERS` on 2026-04-22
  (Week 10 Day 0 consolidation).

### CAL-CH-INFL-FORECAST — CH inflation-forecast wrapper (Week 9 Sprint V surfaced)

- **Status:** merged into `CAL-CPI-INFL-T1-WRAPPERS` on 2026-04-22
  (Week 10 Day 0 consolidation). Note: SNB 0-2 % band midpoint
  (1 %) currently serves as CB-target proxy via
  `EXPECTED_INFLATION_CB_TARGET` + `CH_INFLATION_TARGET_BAND`.

### CAL-NO — NO country monetary (M2 T1 Core) — **PARTIALLY CLOSED** (Week 9 Sprint X-NO — M1 level)

- **Priority:** CLOSED at M1; remaining M2/M3/M4 levels tracked as
  separate CAL-NO-* items. Mirrors CAL-CH (Sprint V) / CAL-AU (Sprint T)
  / CAL-129 (CA) / CAL-119 (JP) / CAL-118 (GB).
- **Trigger:** NO is the first Nordic country in the monetary cascade
  family. Sprint X-NO ships NO as the sixth country in the Sprint
  I-patch TE-primary cascade expansion and validates the standard
  positive-only contract (contrast CH Sprint V which introduced the
  first negative-rate era flag). Norway never ran a negative policy
  rate across the full 35Y TE history — minimum is 0 % during the
  2020-05-08 → 2021-09-24 COVID-response trough.
- **Scope delivered:**
  - `NorgesBankConnector` for the Norges Bank DataAPI (Sprint X-NO
    C2) — SDMX-JSON REST at
    `data.norges-bank.no/api/data/{flow}/{key}`; first SDMX-JSON
    native connector in the monetary cascade family (contrast CSV
    for SNB/RBA, JSON REST for BoC, BoE-gated IADB + BoJ-gated TSD
    for GB/JP). Two dataflows wired: `IR/B.KPRA.SD.R` (key policy
    rate — sight deposit rate) and `GOVT_GENERIC_RATES/B.10Y.GBON`
    (10Y generic gov bond yield — reserved for M4 FCI NO).
  - `TEConnector.fetch_no_policy_rate` wrapper with `NOBRDEP`
    source-drift guard (Sprint X-NO C1). The NOBRDEP symbol has been
    stable across Norges Bank's 1991-now history including the 2001
    inflation-targeting regime kick-off and the 2018 target-level
    revision (2.5 % → 2.0 %).
  - `build_m1_no_inputs` + `_no_policy_rate_cascade` with TE →
    Norges Bank → FRED cascade (Sprint X-NO C4). Flags:
    `NO_POLICY_RATE_TE_PRIMARY` / `NO_POLICY_RATE_NORGESBANK_NATIVE`
    / `NO_POLICY_RATE_FRED_FALLBACK_STALE + CALIBRATION_STALE`.
    Always-present cross-cutting flags: `R_STAR_PROXY` +
    `EXPECTED_INFLATION_CB_TARGET` + `NO_BS_GDP_PROXY_ZERO`. No
    negative-rate flag (NO is positive-only).
  - `build_m2_no_inputs` + `build_m4_no_inputs` scaffolds (Sprint
    X-NO C4) raising `InsufficientDataError` until CPI / output-gap /
    inflation-forecast / ≥5 FCI components are wired.
  - `daily_monetary_indices` pipeline dispatches `--country NO`
    (Sprint X-NO C5). `MONETARY_SUPPORTED_COUNTRIES` widens 10 → 11.
  - `r_star_values.yaml` NO entry at 1.25 % real (Norges Bank MPR
    1/2024 + Staff Memo 7/2023 neutral-range mid); `bc_targets.yaml`
    Norges Bank entry at 2 % (post-2018-03-02 regime; pre-2018 was
    2.5 %). Both YAMLs quote `"NO":` defensively to work around
    YAML 1.1 parsing the bareword as boolean False.
- **Remaining:** M2/M4/M3 NO paths via CAL-NO-CPI /
  CAL-NO-M2-OUTPUT-GAP / CAL-NO-INFL-FORECAST / CAL-NO-M4-FCI /
  CAL-NO-M3; NO balance-sheet signal via CAL-NO-BS-GDP.
- **Status:** PARTIALLY CLOSED — M1 only (Week 9 Sprint X-NO; retro
  commit `cbf3f77`). Full close pending CAL-NO-CPI /
  CAL-NO-M2-OUTPUT-GAP / CAL-NO-INFL-FORECAST / CAL-NO-M4-FCI /
  CAL-NO-M3 / CAL-NO-BS-GDP landing.

### CAL-NO-M2-OUTPUT-GAP — NO M2 output-gap source (Week 9 Sprint X-NO surfaced)

- **Status:** merged into `CAL-M2-T1-OUTPUT-GAP-EXPANSION` on
  2026-04-22 (Week 10 Day 0 consolidation).

### CAL-NO-M4-FCI — NO M4 FCI 5-component bundle (Week 9 Sprint X-NO surfaced)

- **Status:** merged into `CAL-M4-T1-FCI-EXPANSION` on 2026-04-22
  (Week 10 Day 0 consolidation). Note: NO has a structural oil-NOK
  coupling (Brent/WTI moves propagate into NOK exchange-rate and
  domestic petroleum-sector credit conditions within trading days —
  tighter than any other G10 FCI-component coupling). This is
  Phase 2+ research scope, not the T1-expansion scope.

### CAL-NO-M3 — NO M3 market-expectations overlays (Week 9 Sprint X-NO surfaced)

- **Status:** merged into `CAL-M3-T1-EXPANSION` on 2026-04-22
  (Week 10 Day 0 consolidation). Note: inflation-linked debt market
  in NO is thin, so NO EXPINF overlay leans heavily on CB-target
  fallback.

### CAL-NO-BS-GDP — NO balance-sheet / GDP ratio wiring (Week 9 Sprint X-NO surfaced)

- **Status:** merged into `CAL-BS-GDP-T1-EXPANSION` on 2026-04-22
  (Week 10 Day 0 consolidation). Note: Norway's GPFG (Government
  Pension Fund Global, NOK ~16 trillion) is legally offshore-
  invested so the domestic CB balance-sheet is an order of magnitude
  smaller than G10 peers' post-QE balances. Regime classifiers
  consuming NO BS/GDP should treat the signal with caution until a
  sovereign-fund-adjusted variant is wired (Phase 2+ research).

### CAL-NO-CPI — NO CPI YoY wrapper (Week 9 Sprint X-NO surfaced)

- **Status:** merged into `CAL-CPI-INFL-T1-WRAPPERS` on 2026-04-22
  (Week 10 Day 0 consolidation).

### CAL-NO-INFL-FORECAST — NO inflation-forecast wrapper (Week 9 Sprint X-NO surfaced)

- **Status:** merged into `CAL-CPI-INFL-T1-WRAPPERS` on 2026-04-22
  (Week 10 Day 0 consolidation).


### CAL-SE — SE country monetary (M2 T1 Core) — **PARTIALLY CLOSED** (Week 9 Sprint W-SE — M1 level)

- **Priority:** CLOSED at M1; remaining M2/M3/M4 levels tracked as
  separate CAL-SE-* items. Mirrors CAL-CH (Sprint V) / CAL-AU
  (Sprint T) / CAL-129 (CA) / CAL-119 (JP) / CAL-118 (GB).
- **Trigger:** SE was the fifth G10 country after the CH Sprint V
  close that still lacked M1 live, and the **second Nordic country**
  after NO (Sprint X-NO runs in parallel Week 9). Sprint W-SE ships
  SE as the seventh country in the Sprint I-patch TE-primary cascade
  expansion — and the **second negative-rate era cascade** after CH.
  Unlike CH whose corridor reached -0.75 %, Riksbank's corridor
  bottomed at -0.50 % (Feb 2016 → Dec 2018) across the 2015-02-12 →
  2019-11-30 era — roughly two-thirds the depth. Same sign-
  preservation contract across all three cascade layers (TE wrapper
  + Riksbank native + cascade aggregation).
- **Scope delivered:**
  - `RiksbankConnector` for the Riksbank Swea JSON REST API (Sprint
    W-SE C2) — public + scriptable at `api.riksbank.se/swea/v1/`;
    first Nordic-native connector in the monetary cascade family.
    Three series wired: `SECBREPOEFF` (policy rate / styrränta —
    SE M1 cascade secondary), `SECBDEPOEFF` (deposit rate — M4
    corridor floor, reserved), `SECBLENDEFF` (lending rate — M4
    corridor ceiling, reserved).
  - `TEConnector.fetch_se_policy_rate` wrapper with `SWRRATEI`
    source-drift guard (Sprint W-SE C1). The SWRRATEI symbol is
    TE's legacy "Swedish Repo Rate Indicator" identifier preserved
    across the 2022-06-08 Riksbank rename from "repo rate"
    (reporänta) to "policy rate" (styrränta) — the underlying
    7-day instrument is unchanged.
  - `build_m1_se_inputs` + `_se_policy_rate_cascade` with TE →
    Riksbank → FRED cascade (Sprint W-SE C4) including
    `SE_NEGATIVE_RATE_ERA_DATA` flag whenever the resolved window
    contains ≥ 1 strictly-negative observation; `build_m2_se_inputs`
    + `build_m4_se_inputs` wire-ready scaffolds (Sprint W-SE C4).
  - SE entries in `r_star_values.yaml` (0.75 % proxy per Riksbank
    MPR March 2026 neutral-rate range midpoint; Nordic low-r*
    cluster but above CH because SE lacks CHF safe-haven
    compression) + `bc_targets.yaml` (Riksbank 2 % CPIF explicit
    point target — no band flag needed, contrast CH's 0-2 % SNB
    band) (Sprint W-SE C3).
  - `daily_monetary_indices.py` SE country support + Riksbank
    connector instantiation (Sprint W-SE C5).
  - `FredConnector.FRED_SERIES_TENORS` extended with
    `IRSTCI01SEM156N` + `IRLTLT01SEM156N` (Sprint W-SE C5).
- **Resolution (Week 9 Sprint W-SE, M1 level):** SE M1 live via TE
  primary cascade; persisted row emits `SE_POLICY_RATE_TE_PRIMARY` +
  `R_STAR_PROXY` + `EXPECTED_INFLATION_CB_TARGET` +
  `SE_BS_GDP_PROXY_ZERO` flags (no band flag — Riksbank's 2 % CPIF
  is a clean point target). Riksbank Swea native path **live**
  (daily cadence; no `CALIBRATION_STALE`; no `*_MONTHLY` flag —
  contrast CH where SNB SARON is monthly). FRED OECD mirror
  (`IRSTCI01SEM156N`) demoted to last-resort with
  `SE_POLICY_RATE_FRED_FALLBACK_STALE` + `CALIBRATION_STALE` flags.
  When any cascade-resolved observation is strictly-negative
  (e.g. 2015-02 → 2019-11 window), cascade additionally emits
  `SE_NEGATIVE_RATE_ERA_DATA`.
- **Known gap — FRED mirror discontinuation:** the FRED OECD SE
  short-rate mirror (`IRSTCI01SEM156N`) was **discontinued at
  2020-10-01** per the Sprint W-SE probe 2026-04-22 — frozen for
  ~5.5 years, substantially more severe than CH (~2y), AU / NZ / CA
  / JP (a few months). The full FRED-live window is also entirely
  inside the sub-ZLB regime for the Riksbank (rate ≤ 0.25 % through
  all of 2020), so there is no SE anchor where both (a) the FRED
  mirror has data and (b) the Riksbank rate is above the spec-§4
  ZLB threshold (0.5 %). The FRED-fallback live canary therefore
  asserts on `inputs.m1` pre-compute rather than a persisted row,
  mirroring the Sprint V-CH negative-rate canary pattern. This is a
  surface-level reporting gap, not a contract violation — the
  cascade resolves + flags fire correctly; the persistence skip is
  the spec-§4 ZLB gate working as intended.
- **Known gap (spec §4 step 2 ZLB gate):** at negative / sub-ZLB
  policy rates, M1 compute raises `InsufficientDataError` because
  no Krippner shadow-rate connector is wired at Sprint W-SE scope —
  same spec-correct behaviour as Sprint V-CH. Surfaced during the
  C5 negative-rate canary with a 2017 anchor. Krippner integration
  is Phase 2+ scope (CAL-KRIPPNER — not opened Sprint W-SE; bundled
  with L5 regime-classifier enhancements).
- **Remaining:** M2/M4/M3 SE paths via CAL-SE-GAP / CAL-SE-M4-FCI /
  CAL-SE-M3.
- **Status:** PARTIALLY CLOSED — M1 only (Week 9 Sprint W-SE; retro
  commit `26fd8c0`). Full close pending CAL-SE-GAP / CAL-SE-M4-FCI /
  CAL-SE-M3 / CAL-SE-BS-GDP / CAL-SE-CPI / CAL-SE-INFL-FORECAST
  landing.

### CAL-SE-GAP — SE M2 output-gap source (Week 9 Sprint W-SE surfaced)

- **Status:** merged into `CAL-M2-T1-OUTPUT-GAP-EXPANSION` on
  2026-04-22 (Week 10 Day 0 consolidation).

### CAL-SE-M4-FCI — SE M4 FCI 5-component bundle (Week 9 Sprint W-SE surfaced)

- **Status:** merged into `CAL-M4-T1-FCI-EXPANSION` on 2026-04-22
  (Week 10 Day 0 consolidation). Note: SE policy corridor (deposit
  vs lending, shipped Sprint W-SE C2 as `SECBDEPOEFF` /
  `SECBLENDEFF`) already wired — counts as pre-existing M4 inputs
  beyond the 5-component floor.

### CAL-SE-M3 — SE M3 market-expectations overlays (Week 9 Sprint W-SE surfaced)

- **Status:** merged into `CAL-M3-T1-EXPANSION` on 2026-04-22
  (Week 10 Day 0 consolidation). Note: Sweden issues inflation-
  linked Statsobligationer (SEK-denominated), so breakeven
  construction is feasible — more favourable than CH/NO.

### CAL-SE-BS-GDP — SE balance-sheet / GDP ratio wiring (Week 9 Sprint W-SE surfaced)

- **Status:** merged into `CAL-BS-GDP-T1-EXPANSION` on 2026-04-22
  (Week 10 Day 0 consolidation). Note: Riksbank balance sheet
  expanded significantly during 2015-2019 QE era (SGB purchases)
  and again during COVID-19 so the zero-seed is visibly inadequate.

### CAL-SE-CPI — SE CPI / CPIF YoY wrapper (Week 9 Sprint W-SE surfaced)

- **Status:** merged into `CAL-CPI-INFL-T1-WRAPPERS` on 2026-04-22
  (Week 10 Day 0 consolidation). Note: SE target measure is CPIF
  (not CPI) since 2017 — the consolidated item's SE entry must
  source CPIF specifically.

### CAL-SE-INFL-FORECAST — SE inflation-forecast wrapper (Week 9 Sprint W-SE surfaced)

- **Status:** merged into `CAL-CPI-INFL-T1-WRAPPERS` on 2026-04-22
  (Week 10 Day 0 consolidation).

### CAL-DK — DK country monetary (M2 T1 Core) — **PARTIALLY CLOSED** (Week 9 Sprint Y-DK — M1 level)

- **Priority:** CLOSED at M1; remaining M2/M3/M4 levels tracked as
  separate CAL-DK-* items. Mirrors CAL-SE (Sprint W-SE) / CAL-NO
  (Sprint X-NO) / CAL-CH (Sprint V) / CAL-AU (Sprint T) / CAL-129
  (CA) / CAL-119 (JP) / CAL-118 (GB).
- **Trigger:** DK was the eighth G10 country after the SE Sprint
  W-SE close that still lacked M1 live, and the **third Nordic
  country** after NO + SE. Sprint Y-DK ships DK as the eighth
  country in the Sprint I-patch TE-primary cascade expansion — and
  the **third negative-rate era cascade** after CH + SE (and the
  **first EUR-peg country** in the family).
- **Distinctive Sprint Y-DK novelty (two cross-cutting):**
  - **Source-instrument divergence**: TE returns the legacy
    DISCOUNT rate (`DEBRDISC` ≡ Statbank `ODKNAA`; only briefly
    negative 2021-2022, min -0.60 %), while the Nationalbanken
    native cascade slot returns the **CD rate** (`OIBNAA` —
    `indskudsbevisrenten`, the active EUR-peg defence tool;
    deeply negative across 2015-2022, min -0.75 % at 2015-04-07
    with 2450 strictly-negative daily observations). The cascade
    flag-emission contract (`*_TE_PRIMARY` vs
    `*_NATIONALBANKEN_NATIVE`) makes the source observable so
    downstream consumers can pick the right semantic — both
    representations are operationally valid, the EUR-peg-defence
    story is captured by the OIBNAA path. This is a first in the
    cascade family — every prior country exposed the same single
    policy-rate instrument across all cascade depths.
  - **EUR-peg-imported inflation target**: DK has NO domestic
    inflation target — Nationalbanken's mandate is exchange-rate
    stability (DKK fixed to EUR at 7.46038 within ERM-II
    ±2.25 %), and the de-facto inflation anchor is imported from
    the ECB's 2 % HICP target via the peg. The cascade emits the
    **DK-specific** `DK_INFLATION_TARGET_IMPORTED_FROM_EA` flag
    (always) instead of the standard `EXPECTED_INFLATION_CB_TARGET`
    flag the other countries emit. The convention is materialised
    in `bc_targets.yaml` via the new `target_conventions` block +
    a new `resolve_inflation_target_convention` resolver hook in
    `_config.py` — generalisable to any future EUR-peg country.
- **Scope delivered:**
  - `NationalbankenConnector` for the Statistics Denmark Statbank.
    dk public BULK CSV API (Sprint Y-DK C2) — public + scriptable
    at `api.statbank.dk/v1/`; first central bank where the data
    lands via a third-party-host API (Statistics Denmark hosts
    Nationalbanken's monetary tables under the `DN` table prefix).
    Four series wired from the `DNRENTD` table:
    - `OIBNAA` (CD rate / indskudsbevisrenten — DK M1 cascade
      secondary; the active EUR-peg defence tool)
    - `ODKNAA` (discount rate / diskontoen — historical benchmark;
      what TE primary returns; exposed for cross-validation)
    - `OIRNAA` (lending rate / udlånsrenten — corridor ceiling;
      reserved for M4 FCI)
    - `OFONAA` (current-account deposit rate / foliorenten —
      corridor floor; reserved for M4 FCI)
  - `TEConnector.fetch_dk_policy_rate` wrapper with `DEBRDISC`
    source-drift guard (Sprint Y-DK C1). The DEBRDISC symbol is
    TE's legacy "Denmark Bank Rate Discount" identifier.
  - `build_m1_dk_inputs` + `_dk_policy_rate_cascade` with TE →
    Nationalbanken → FRED cascade (Sprint Y-DK C4) including
    `DK_NEGATIVE_RATE_ERA_DATA` flag whenever the resolved window
    contains ≥ 1 strictly-negative observation;
    `build_m2_dk_inputs` + `build_m4_dk_inputs` wire-ready
    scaffolds (Sprint Y-DK C4) referencing the new EUR-peg-
    specific CAL items below.
  - DK entries in `r_star_values.yaml` (0.75 % proxy per
    Nationalbanken WP 152/2020 + Monetary Review 2024 neutral-
    range midpoint synthesis; matches SE's Nordic low-r* cluster
    magnitude; above CH because DKK lacks the CHF safe-haven
    compression) + `bc_targets.yaml` (ECB 2 % via the new
    `target_conventions: DK: imported_eur_peg` block) (Sprint
    Y-DK C3).
  - New `resolve_inflation_target_convention` loader hook +
    `load_target_conventions` reader (Sprint Y-DK C3) — countries
    absent default to "domestic"; DK lands "imported_eur_peg".
    Generalisable to any future EUR-peg country.
  - `daily_monetary_indices.py` DK country support +
    Nationalbanken connector instantiation (Sprint Y-DK C5).
  - `FredConnector.FRED_SERIES_TENORS` extended with
    `IRSTCI01DKM156N` + `IRLTLT01DKM156N` (Sprint Y-DK C5).
- **Resolution (Week 9 Sprint Y-DK, M1 level):** DK M1 live via
  TE primary cascade; persisted row emits
  `DK_POLICY_RATE_TE_PRIMARY` + `R_STAR_PROXY` +
  `DK_INFLATION_TARGET_IMPORTED_FROM_EA` (NOT
  `EXPECTED_INFLATION_CB_TARGET`) + `DK_BS_GDP_PROXY_ZERO` flags.
  Nationalbanken Statbank native path **live** (daily cadence; no
  `CALIBRATION_STALE`; no `*_MONTHLY` flag — matches the SE
  Riksbank pattern, contrast CH SNB monthly secondary). FRED OECD
  mirror (`IRSTCI01DKM156N`) demoted to last-resort with
  `DK_POLICY_RATE_FRED_FALLBACK_STALE` + `CALIBRATION_STALE`
  flags. When any cascade-resolved observation is strictly-
  negative, cascade additionally emits `DK_NEGATIVE_RATE_ERA_DATA`.
- **Known gap (spec §4 step 2 ZLB gate):** at negative / sub-ZLB
  policy rates, M1 compute raises `InsufficientDataError` because
  no Krippner shadow-rate connector is wired at Sprint Y-DK scope —
  same spec-correct behaviour as Sprint V-CH / W-SE. Surfaced
  during the C5 negative-rate canary with a 2021-09-30 anchor.
  Krippner integration is Phase 2+ scope (CAL-KRIPPNER — bundled
  with L5 regime-classifier enhancements; not opened Sprint Y-DK).
- **Remaining:** M2/M4/M3 DK paths via CAL-DK-GAP / CAL-DK-M4-FCI
  / CAL-DK-M3 + the DK-specific EUR-peg variants
  (CAL-DK-M2-EUR-PEG-TAYLOR / CAL-DK-M4-EUR-PEG-FCI).
- **Status:** PARTIALLY CLOSED — M1 only (Week 9 Sprint Y-DK; retro
  commit `5019e7f`). Full close pending the CAL-DK-* items below.

### CAL-DK-CPI — DK CPI / HICP YoY wrapper (Week 9 Sprint Y-DK surfaced)

- **Status:** merged into `CAL-CPI-INFL-T1-WRAPPERS` on 2026-04-22
  (Week 10 Day 0 consolidation). Note: for an EUR-peg country the
  relevant inflation measure for the monetary stance is HICP (the
  ECB target measure) rather than CPI (the domestic measure) —
  the M2 spec revision required for EUR-peg countries
  (`CAL-DK-M2-EUR-PEG-TAYLOR`) should pin HICP as primary.
  Statbank.dk REST API already wired Sprint Y-DK C2 for the
  monetary tables; CPI / HICP add-ons reuse same host.

### CAL-DK-GAP — DK M2 output-gap source (Week 9 Sprint Y-DK surfaced)

- **Status:** merged into `CAL-M2-T1-OUTPUT-GAP-EXPANSION` on
  2026-04-22 (Week 10 Day 0 consolidation).

### CAL-DK-INFL-FORECAST — DK inflation-forecast wrapper (Week 9 Sprint Y-DK surfaced)

- **Status:** merged into `CAL-CPI-INFL-T1-WRAPPERS` on 2026-04-22
  (Week 10 Day 0 consolidation). Note: consider importing the ECB
  SPF EA-area inflation forecast as a structurally consistent
  proxy (DK inflation expectations are EUR-peg-anchored). Current
  proxy flag: `DK_INFLATION_TARGET_IMPORTED_FROM_EA`.

### CAL-DK-M2-EUR-PEG-TAYLOR — DK M2 spec revision for EUR-peg regime (Week 9 Sprint Y-DK surfaced)

- **Priority:** LOW — Phase 2+ research scope; not blocking M2 DK
  numerical persistence (CAL-DK-CPI / CAL-DK-GAP /
  CAL-DK-INFL-FORECAST close that), but blocking M2 DK *signal
  validity* because the vanilla domestic Taylor rule will
  systematically mis-fit a peg-defence policy regime.
- **Trigger:** Sprint Y-DK C4 `build_m2_dk_inputs` docstring +
  raise message call out that even when all three input sources
  land, the M2 Taylor-gap formula will need a DK-specific
  adaptation. Nationalbanken does not run an independent
  monetary policy — the policy-rate response function is
  dominated by the EUR-peg-defence imperative, not the standard
  inflation-gap + output-gap weighting.
- **Scope:**
  - Spec a DK-specific Taylor-rule variant that incorporates the
    DKK/EUR FX deviation as a third Taylor regressor (or
    decompose into "ECB rate + DK-specific peg-defence spread").
  - Backtest against the historical Nationalbanken decision
    record (every CD-rate move 2014-now).
  - Bump `methodology_version` MINOR for M2 DK (`M2_DK_v1.1`)
    when shipped.
  - Document the EUR-peg-coupling story in the M2 spec as the
    canonical example (generalisable to any future EUR-peg
    country addition — same spec applies).
- **Unblocks:** M2 DK signal-validity sign-off.
- **Status:** OPEN (Phase 2+).

### CAL-DK-M4-FCI — DK M4 FCI 5-component bundle (Week 9 Sprint Y-DK surfaced)

- **Status:** merged into `CAL-M4-T1-FCI-EXPANSION` on 2026-04-22
  (Week 10 Day 0 consolidation) for the **numerical** path. Note:
  the EUR-peg keeps DKK NEER tightly coupled to EUR NEER — the
  BIS Trade-Weighted path via existing `bis.py` is a pragmatic
  shortcut over a dedicated Nationalbanken NEER connector.
  Signal-validity for an EUR-peg country tracked separately via
  `CAL-DK-M4-EUR-PEG-FCI` (Phase 2+ research scope).

### CAL-DK-M4-EUR-PEG-FCI — DK M4 FCI hybrid DK + EA-area (Week 9 Sprint Y-DK surfaced)

- **Priority:** LOW — Phase 2+ research scope; not blocking M4 DK
  numerical persistence (CAL-DK-M4-FCI closes that), but informs
  the *signal validity* of an FCI compose for an EUR-peg country.
- **Trigger:** Sprint Y-DK C4 `build_m4_dk_inputs` docstring
  notes that the DK FCI components (credit spread, vol, NEER,
  mortgage rate) are heavily EUR-coupled — Danish credit /
  vol / NEER all move with EUR-area cycles much more than would
  be the case in an independent-monetary-policy country. A
  hybrid FCI that blends DK-specific + EA-area inputs may carry
  more signal than a pure DK FCI.
- **Scope:**
  - Empirical study of cross-correlation between DK FCI
    components and EA-area equivalents during 2014-2025 (a
    decade spanning EA negative-rate era + COVID stress + 2022
    rate-hike cycle).
  - Spec a hybrid M4 DK-EUR-PEG variant if the empirical study
    supports it.
  - Bump `methodology_version` MINOR (`M4_DK_v1.1`) when shipped.
- **Unblocks:** M4 DK signal-validity sign-off.
- **Status:** OPEN (Phase 2+).

### CAL-DK-M3 — DK M3 market-expectations overlays (Week 9 Sprint Y-DK surfaced)

- **Status:** merged into `CAL-M3-T1-EXPANSION` on 2026-04-22
  (Week 10 Day 0 consolidation). Note: for an EUR-peg country the
  structurally consistent EXPINF anchor is the ECB EXPINF (already
  wired via the EA path); the DK domestic Indeksoblig breakeven
  serves as cross-validation rather than primary.

### CAL-DK-BS-GDP — DK balance-sheet / GDP ratio wiring (Week 9 Sprint Y-DK surfaced)

- **Status:** merged into `CAL-BS-GDP-T1-EXPANSION` on 2026-04-22
  (Week 10 Day 0 consolidation). Note: for an EUR-peg country the
  Nationalbanken BS dynamic is dominated by FX-intervention flow
  (DKK reserves built up to defend the peg during EA QE era;
  partially unwound 2022-2025) rather than QE per se — a
  DK-specific signal interpretation may be required even once the
  numerical wiring lands.

### CAL-backfill-l5 — L5 retroactive classification script (CLOSED 2026-04-21 via Sprint M)

- **Priority:** LOW — fewer than 30 production dates affected (Phase 1
  history still recent); not critical path.
- **Trigger:** Sprint K (Week 8 Day 2) deferred Commit 6 per brief
  §4 backfill allowance. L5 wiring shipped operational; backfill
  closes the loop for any historical cycle date without a sibling
  ``l5_meta_regimes`` row.
- **Scope:**
  - `src/sonar/scripts/backfill_l5.py` new module with Typer CLI.
  - Iterates ``(country, date)`` tuples where at least one of the
    four L4 cycle tables has a row AND no matching L5 row exists.
  - Classifies via :class:`MetaRegimeClassifier`; persists via
    ``persist_l5_meta_regime_result``.
  - Idempotent: second run is a no-op. Dry-run default; explicit
    ``--execute`` required to write.
  - CLI flags: ``--country``, ``--all-t1``, ``--from-date``,
    ``--dry-run/--execute``.
- **Dependency:** Sprint H L5 classifier + persist helper (closed)
  and Sprint K daily_cycles wiring (closed).
- **Status:** CLOSED 2026-04-21 via Sprint M Commit 2.

## Não-categorizado por horizonte

Zero items. Todos têm horizonte explícito no spec.

## Workflow de recalibração

1. Item reaches activation window (production data ≥ horizonte).
2. Spec owner (Hugo) corre backtest com harness ([`../ROADMAP.md`](../ROADMAP.md) §Phase 2 scope) contra benchmark específico do item.
3. Decisão: manter valor OR recalibrar.
4. Se recalibra:
   - Bump `methodology_version` MINOR (weight/threshold change).
   - Selective rebackfill per country.
   - Actualiza spec + regista ADR se trade-off relevante.
   - Este ficheiro: status `done`, link commit + valor final.
5. Se mantém: status `done (validated)`, rationale + backtest link.

## Exclusões documentadas (não são CAL items)

Items encontrados em grep mas **não catalogáveis** como calibration tasks one-shot:

- `overlays/rating-spread.md:143` — anchor values são recurring 3m, catalogados separadamente como **CAL-020**.
- `indices/monetary/M2-taylor-gaps.md:213` — non-requirement sobre ρ auto-recalibration, duplica CAL-011.
- `indices/monetary/M4-fci.md:210` — scope expansion (Goldman FCI replication), não recalibração.
- `cycles/credit-cccs.md:209` — nome de test fixture `xx_qs_placeholder`, não placeholder de threshold.

## Referências

- [`../ROADMAP.md`](../ROADMAP.md) §Phase 4 Calibração Empírica
- [`../specs/conventions/methodology-versions.md`](../specs/conventions/methodology-versions.md) — bump rules
- [`../specs/conventions/normalization.md`](../specs/conventions/normalization.md) — lookbacks per cycle
- [`../specs/conventions/composite-aggregation.md`](../specs/conventions/composite-aggregation.md) — Policy 1 + cycle weights

## Forward-looking items (Phase 2 / 2.5 / 3 scope)

Added 2026-04-22 (Week 10 Day 0 Phase 3 reframe). Catalogues the
larger scope items implied by the revised `../ROADMAP.md` so they
have stable CAL IDs for cross-reference before implementation begins.

### CAL-ERP-T1-PER-COUNTRY — Per-country ERP live paths (Phase 2) — PARTIAL

- **Priority:** HIGH — Phase 2 gate blocker (T1 uniformity); explicit
  Phase 2 exit criterion in roadmap.
- **Trigger:** current cost-of-capital composite uses
  `MATURE_ERP_PROXY_US` flag for EA / GB / JP (fallback to US ERP).
  Phase 2 gate requires per-market ERP live paths.
- **Status:** PARTIAL (2026-04-22 via Week 10 Sprint B). Narrowed
  scope shipped; per-country 4-method compute deferred pending
  fundamentals connectors. See ADR-0008 and
  `docs/planning/retrospectives/week10-sprint-erp-t1-report.md`.
- **Shipped (Week 10 Sprint B)**:
  - `src/sonar/connectors/te.py::fetch_equity_index_historical` for
    DE / GB / JP / FR / EA with source-drift guards (DAX / UKX /
    NKY / CAC / SX5E) + 5 cassettes + 5 @slow live canaries.
  - `src/sonar/connectors/damodaran.py::fetch_monthly_implied_erp`
    parsing `implprem/ERPMMMYY.xlsx`.
  - `daily_cost_of_capital` three-tier mature-ERP fallback
    (`erp_canonical` → Damodaran monthly → static 5.5 %) with new
    flag `ERP_MATURE_LIVE_DAMODARAN`.
  - `docs/planning/week10-sprint-b-erp-t1-preflight-findings.md`
    empirical-probe reference doc.
  - `docs/adr/ADR-0008-per-country-erp-data-constraints.md`.
- **Deferred (fresh sub-CALs below)**:
  - `CAL-ERP-COUNTRY-FUNDAMENTALS` — dividend yield / EPS / CAPE
    per market index (Refinitiv / FactSet / Bloomberg / MSCI).
  - `CAL-ERP-CAPE-CROSS-COUNTRY` — CAPE per country requires
    Shiller-style ≥ 10Y smoothed-earnings per market.
  - `CAL-ERP-BUYBACK-CROSS-COUNTRY` — buyback yield US-only.
  - `CAL-ERP-T1-SMALLER-MARKETS` — IT/ES/NL/PT extension.
  - `CAL-ERP-T1-NON-EA` — CA/AU/NZ/CH/SE/NO/DK extension.
- **Original scope** (remains unshipped, awaiting
  CAL-ERP-COUNTRY-FUNDAMENTALS):
  - `src/sonar/overlays/erp_ea.py` — ERP EA assembler (FactSet EA
    earnings yield + Eurostoxx DDM + Eurostoxx Gordon + Buyback EA
    + FRED ECB CPI expectations + Damodaran EA cross-val).
  - `src/sonar/overlays/erp_gb.py` — ERP GB assembler (GBP
    equivalents).
  - `src/sonar/overlays/erp_jp.py` — ERP JP assembler (JPY
    equivalents; Nikkei DDM via TE; Topix Gordon).
  - `daily_erp_<market>` assembly inside `daily_cost_of_capital`
    composition (follow CAL-057 pattern).
  - Integration tests per market with cassette fixtures.
- **Unblocks (once full scope resolves):** Phase 2 T1 uniformity
  gate; per-market k_e in DCF workflows for EA / GB / JP.
- **Follow-on:** additional T1 markets (CA / AU / NZ / CH / SE / NO /
  DK) after Phase 2 gate — same pattern applied to Nordic + ANZ +
  North America peer markets.


### CAL-ERP-COUNTRY-FUNDAMENTALS — Per-market equity-fundamentals connectors (Phase 2.5)

- **Priority:** HIGH — hard blocker for CAL-ERP-T1-PER-COUNTRY full
  resolution.
- **Trigger:** Week 10 Sprint B pre-flight confirmed that neither TE
  (`/historical/country/.../indicator/stock market` surfaces only
  closing level) nor FMP `stable` (`key-metrics` / `ratios` empty
  for index tickers) nor Damodaran monthly / annual files expose
  aggregate dividend yield + trailing / forward EPS + CAPE ratio per
  market index in compute-friendly form. All four ERP methods
  (DCF / Gordon / EY / CAPE) therefore fail for every non-US market.
- **Required work:**
  1. Source evaluation for per-market aggregate fundamentals.
     Candidates (trial-and-price matrix required):
     - Refinitiv Workspace / Eikon Data API (per-index fundamentals).
     - FactSet IBES (forward EPS + consensus growth per benchmark).
     - Bloomberg Index Fundamentals (DAX / UKX / NKY / CAC / SX5E).
     - MSCI Index Analytics (per-index valuation metrics).
     - Russell Benchmark data (less relevant — US-centric).
  2. Connector(s) implementing a uniform contract:
     `fetch_equity_index_fundamentals(index, date) -> IndexFundamentals`
     carrying `index_level`, `trailing_eps`, `forward_eps`,
     `dividend_yield_pct`, `buyback_yield_pct?`, `cape_ratio?`.
  3. ERP per-market input assemblers layered on top (DE / GB / JP /
     FR / EA first; other T1 markets as follow-on).
  4. Cross-validation vs Damodaran annual `ctryprem.xlsx` within
     the ±20 % band already established for US via `XVAL_DRIFT`.
- **Impact if unresolved:** `daily_cost_of_capital` remains on
  US-mature-ERP proxy for non-US countries; Phase 2 T1 uniformity
  exit criterion remains unmet.
- **Estimate:** vendor negotiation + API setup +
  5 × 3h per country + cross-val → 20-30h CC once vendor contract
  lands.
- **Related:** CAL-ERP-T1-PER-COUNTRY (parent, PARTIAL); ADR-0008.

### CAL-ERP-CAPE-CROSS-COUNTRY — CAPE ratio per non-US market

- **Priority:** MEDIUM — one-of-four ERP methods; EY + DCF + Gordon
  suffice for canonical with `MIN_METHODS_FOR_CANONICAL = 2`.
- **Trigger:** Shiller CAPE is computed on a smoothed 10Y earnings
  history per market. Non-US markets lack an equivalent published
  series. Building it in-house requires ≥ 120 months of monthly
  aggregate earnings-per-index plus an inflation-adjusted price
  series per country.
- **Required work:**
  1. Decide whether to compute CAPE from the fundamentals connectors
     (CAL-ERP-COUNTRY-FUNDAMENTALS) once they land, or to ingest a
     third-party CAPE series (Research Affiliates, Barclays).
  2. Implement CAPE extractor per country; maintain the 10Y
     smoothing convention.
  3. Wire into `ERPInput.cape_ratio` for non-US markets.
- **Impact if unresolved:** `ERPInput.cape_ratio` stays US-only;
  CAPE method drops for non-US → canonical uses ≤ 3 methods.
- **Estimate:** 6-10h CC after CAL-ERP-COUNTRY-FUNDAMENTALS lands.
- **Related:** CAL-ERP-T1-PER-COUNTRY.

### CAL-ERP-BUYBACK-CROSS-COUNTRY — Buyback yield for non-US markets

- **Priority:** LOW — buyback is a discretionary input on the
  DCF/Gordon cash-yield side; `None` degrades gracefully via
  `ERPMethodResult` flags without dropping the method.
- **Trigger:** Week 10 Sprint B pre-flight confirmed buyback yield
  is US-centric (S&P Dow Jones Indices publishes S&P 500 buybacks
  back to 2000). Non-US markets have sparse-to-zero buyback
  activity and no canonical per-market series exists.
- **Required work:**
  1. Document the US-only limitation in `docs/specs/overlays/erp-daily.md`
     §6 "buyback > 1q stale" edge case.
  2. Ensure per-country ERP assemblers pass `buyback_yield_pct=None`
     explicitly and rely on the existing `_compute_gordon` ``STALE``
     flag path.
  3. Revisit in Phase 3+ if vendor publishes EA / GB / JP buyback
     aggregates.
- **Impact if unresolved:** Gordon method for non-US carries the
  ``STALE`` flag by default; canonical confidence takes a single
  0.05 deduction per spec §Confidence.
- **Estimate:** 1-2h CC documentation sweep.

### CAL-ERP-T1-SMALLER-MARKETS — ERP for IT / ES / NL / PT

- **Priority:** MEDIUM — these 4 EA-periphery markets currently
  proxy via SPX canonical (``MATURE_ERP_PROXY_US`` flag). Cheaper
  win once CAL-ERP-COUNTRY-FUNDAMENTALS delivers the connector.
- **Trigger:** Week 10 Sprint B explicitly deferred these under the
  "smaller equity markets — proxy suffices initially" rationale in
  the brief §1 Out scope.
- **Required work:** once fundamentals connector lands, add per-market
  ERP assemblers (`erp_it.py`, `erp_es.py`, `erp_nl.py`, `erp_pt.py`)
  following the DE / FR template. Cassettes + @slow canaries
  per country.
- **Impact if unresolved:** smaller EA peripherals ride on SPX
  proxy for per-market k_e — acceptable until Consumer A workflows
  demand genuine per-market signal.
- **Estimate:** 4-6h CC after CAL-ERP-COUNTRY-FUNDAMENTALS lands.
- **Related:** CAL-ERP-T1-PER-COUNTRY.

### CAL-ERP-T1-NON-EA — ERP for CA / AU / NZ / CH / SE / NO / DK

- **Priority:** MEDIUM — Phase 2.5+ per the original brief §1 Out
  scope. 7 markets on SPX proxy today.
- **Trigger:** Week 10 Sprint B explicitly deferred these under the
  Phase 2.5+ scope bullet. Each market has distinct equity index
  (S&P/TSX, S&P/ASX 200, NZX 50, SMI, OMXS30, OBX, OMXC25) and
  distinct sovereign curve / inflation series already partly wired
  in Phase 1.
- **Required work:** once fundamentals connector lands, add per-market
  ERP assemblers following DE / GB / JP template. Cassettes + @slow
  canaries per country. Likely shares vendor contract with
  CAL-ERP-COUNTRY-FUNDAMENTALS.
- **Impact if unresolved:** non-EA T1 markets ride on SPX proxy;
  per-market k_e in DCF workflows remains US-biased.
- **Estimate:** 10-14h CC after CAL-ERP-COUNTRY-FUNDAMENTALS lands.
- **Related:** CAL-ERP-T1-PER-COUNTRY.

### CAL-L5-REGIME-TAXONOMY — L5 regimes dedicated table (Phase 2.5)

- **Priority:** HIGH — Phase 2.5 gate blocker.
- **Trigger:** current L5 implementation shipped Week 8 Sprint H/K
  as scaffold + classifier + CLI wiring; overlay booleans still
  persisted inside cycle scores. Phase 2.5 roadmap demands dedicated
  regimes table with `active`, `intensity`, `duration_days`,
  `transition_probability`.
- **Scope:**
  - Spec `docs/specs/regimes/README.md` + per-regime files (regime
    taxonomy currently absent from Phase 0 specs).
  - Alembic migration for `regimes` table (composite PK: country,
    regime_slug, date).
  - Classifier upgrade: overlay boolean → intensity in [0, 1] +
    duration counter + transition probability per regime.
  - Overlay / cycle composite integration (currently gated).
- **Unblocks:** L6 matriz 4-way + diagnostics (depend on regime
  state); L7 `regime_active` API endpoint.
- **Status:** OPEN (Phase 2.5).

### CAL-L6-MATRIZ-4WAY — 4-way cycle-state matrix (Phase 2.5)

- **Priority:** MEDIUM — Phase 2.5 gate blocker.
- **Trigger:** roadmap Phase 2.5 exit criterion. ECS × CCCS × MSC ×
  FCS → 16 canonical states + outliers persisted daily. Currently
  cycle scores are persisted individually but no composite state
  classification exists.
- **Scope:**
  - Spec `docs/specs/integration/matriz-4way.md` (16 canonical
    states + outlier criteria).
  - Alembic migration for `matriz_4way_daily` table.
  - `src/sonar/integration/matriz_4way.py` + CLI / pipeline wiring.
  - Historical backfill once spec frozen.
- **Unblocks:** L7 `matriz_4way` API + website heatmap page.
- **Status:** OPEN (Phase 2.5).

### CAL-L6-DIAGNOSTICS — Four diagnostic composites (Phase 2.5)

- **Priority:** MEDIUM — Phase 2.5 gate blocker.
- **Trigger:** roadmap Phase 2.5 exit criterion. Four composites:
  `bubble-detection` (FCS + overlay triggers), `minsky-fragility`
  (L4 credit + L2 CRP + L3 market-exp), `real-estate-cycle` (L3
  credit + BIS property prices), `risk-appetite-regime` (cross-
  cycle composite).
- **Scope:**
  - Spec `docs/specs/integration/diagnostics.md` (4 sub-files per
    diagnostic).
  - Alembic migration for `diagnostics_daily` table.
  - Per-diagnostic module under `src/sonar/integration/`.
  - CLI + pipeline wiring.
- **Unblocks:** L7 `diagnostic` API + website per-country diagnostic
  pages.
- **Status:** OPEN (Phase 2.5).

### CAL-L6-KE-CROSS-COUNTRY — Cost-of-capital cross-country composite (Phase 2.5)

- **Priority:** HIGH — Phase 2.5 gate blocker; unblocks primary
  DCF workflow use case.
- **Trigger:** current `daily_cost_of_capital` ships US k_e only.
  Cross-country composite requires per-market ERP
  (CAL-ERP-T1-PER-COUNTRY) + per-market CRP + β sourcing documented.
- **Scope:**
  - Composite formula: `k_e_country = risk_free_country + β ·
    ERP_mature + CRP_country`.
  - β sourcing: per-market (FactSet / Bloomberg) or bottom-up by
    sector — decision in ADR.
  - Persistence extension of existing `cost_of_capital_daily`
    table schema.
  - Per-country pipeline runs.
- **Unblocks:** L7 `cost_of_capital` API endpoint per country;
  Consumer A MCP endpoint functionality.
- **Status:** OPEN (Phase 2.5).

### CAL-BACKTEST-HARNESS — Walk-forward backtest infrastructure (Phase 2.5)

- **Priority:** MEDIUM — Phase 2.5 scope (harness pronto, calibração
  final em Phase 4).
- **Trigger:** roadmap Phase 2.5 requires harness executable against
  production data. Backtests: ECS vs NBER (US) / CEPR (EA); FCS
  Pagan-Sossounov bear/bull dating; MSC transition frequencies vs
  regime changes; CCCS crisis-prediction AUC vs Moody's default
  study.
- **Scope:**
  - `src/sonar/backtest/harness.py` — walk-forward runner.
  - Per-cycle scoring module (`backtest_ecs.py`, `backtest_fcs.py`,
    etc.).
  - Benchmark data loaders (NBER recessions, CEPR EA, Pagan-
    Sossounov dated periods, Moody's default events).
  - CLI `sonar backtest --cycle {ecs,fcs,msc,cccs}`.
- **Unblocks:** Phase 4 empirical calibration gate (harness must
  exist before Phase 4 recalibration starts).
- **Status:** OPEN (Phase 2.5).

### CAL-L7-API-MCP — MCP server implementation (Phase 3)

- **Priority:** HIGH — Phase 3 primary unlock milestone.
- **Trigger:** Consumer A (Hugo DCF workflows) demands MCP endpoint
  exposure. Roadmap Phase 3 lists 9 endpoints:
  `sonar.cost_of_capital`, `sonar.yield_curve`, `sonar.crp`,
  `sonar.rating_spread`, `sonar.expected_inflation`,
  `sonar.cycle_status`, `sonar.regime_active`, `sonar.matriz_4way`,
  `sonar.diagnostic`.
- **Scope:**
  - MCP server framework selection (ADR-P3-MCP-framework).
  - Per-endpoint schema + handler.
  - Auth model (API key in header; private-vs-public routing).
  - Cloudflared tunnel `mcp.hugocondesa.com` (depends on
    CAL-CLOUDFLARE-TUNNEL-REACTIVATION).
- **Unblocks:** Consumer A live consumption.
- **Status:** OPEN (Phase 3).

### CAL-L7-API-REST — REST API implementation (Phase 3)

- **Priority:** HIGH — Phase 3 primary unlock milestone.
- **Trigger:** Consumer B (website) + Consumer A fallback need REST
  equivalent to MCP endpoints. Roadmap Phase 3 tech stack: FastAPI
  confirmed, OpenAPI auto-gen.
- **Scope:**
  - FastAPI app skeleton.
  - REST endpoints mirroring MCP surface (9 endpoints) + OpenAPI
    spec auto-gen at `/docs`.
  - Auth model identical to MCP (API key + rate limit per key).
  - Deployment to `api.sonar.hugocondesa.com` via cloudflared.
- **Unblocks:** Consumer B website + programmatic consumers outside
  MCP.
- **Status:** OPEN (Phase 3).

### CAL-L7-WEBSITE — Website implementation (Phase 3)

- **Priority:** HIGH — Phase 3 primary unlock milestone (Consumer B).
- **Trigger:** roadmap Phase 3 Consumer B. 8 page categories: Home,
  Cycles, Curves, Cost of capital, Matriz 4-way, Diagnostics,
  Methodology, Editorial.
- **Scope:**
  - Frontend tech stack decision (ADR-P3-website-stack — React/Next
    vs static SSG vs hybrid).
  - Per-page layout + data-fetching (consumes REST API).
  - Editorial workflow (ADR-P3-editorial — triggered regime shifts
    vs manual Hugo drafting).
  - Licensing per dataset (ADR-P3-licensing — which outputs
    publishable vs API-only per BIS / TE / paid-source constraints).
  - Deployment to `sonar.hugocondesa.com` via cloudflared.
- **Unblocks:** Public consumption of SONAR outputs.
- **Status:** OPEN (Phase 3).

### CAL-CLOUDFLARE-TUNNEL-REACTIVATION — Cloudflare tunnel infrastructure (Phase 3)

- **Priority:** LOW — infra dependency; activation condition of
  Phase 3 L7 ship.
- **Trigger:** cloudflared config preserved in `/etc/cloudflared/`
  but inactive since Phase 0. Phase 3 L7 requires public routes
  for `sonar.hugocondesa.com` + `mcp.hugocondesa.com` +
  `api.sonar.hugocondesa.com`.
- **Scope:**
  - Reactivate cloudflared service.
  - DNS + tunnel routing to local FastAPI + MCP + static-site
    endpoints.
  - Monitoring: uptime + request rate + error rate.
- **Unblocks:** Public L7 URLs; Consumer A MCP + Consumer B website
  access.
- **Status:** OPEN (Phase 3).

## Consolidated T1 expansion items (Phase 2 scope)

Week 9 introduced ~46 country-specific sub-CALs as the advanced-economy
monetary M1 arc shipped (CA / AU / NZ / CH / SE / NO / DK × 6-7 sub-
shapes each). Week 10 Day 0 grooming consolidates these per-country
copies into 5 generic T1-expansion items — the work is genuinely
uniform per country (same data-source pattern, same wire-ready
scaffold, same `InsufficientDataError` escape) and does not benefit
from per-country tracking once parent M2 T1 Core items (CAL-119 /
CAL-129 / CAL-AU / CAL-NZ / CAL-CH / CAL-SE / CAL-NO / CAL-DK) capture
the per-country partial closure. Country-specific context preserved
as sub-bullets below when it differs materially from peer countries.

**Not consolidated** (material scope difference, tracked separately):

- `CAL-120..126` (JP) — already opened at M2 T1 Core level; merged
  here alongside Week 9 peer countries.
- `CAL-NZ-RBNZ-TABLES` — RBNZ host perimeter-block remediation
  (NZ-specific infrastructure; NOT a calibration/data-source item in
  the T1 expansion sense).
- `CAL-124` (BoJ TSD browser-gate bypass) — JP-specific scraper
  problem; tracked separately.
- `CAL-125` (JP 10Y JGB FRED path) — JP-specific FRED routing;
  tracked separately.
- `CAL-DK-M2-EUR-PEG-TAYLOR` + `CAL-DK-M4-EUR-PEG-FCI` — DK EUR-peg
  regime is structural (Danmarks Nationalbanken imports ECB DFR
  target), not a variant of generic M2/M4 T1 expansion; tracked
  separately under DK parent item.

### CAL-M2-T1-OUTPUT-GAP-EXPANSION — M2 Taylor-gap output-gap connectors for T1 countries (Phase 2) — **CLOSED output-gap half (Week 10 Sprint C, 2026-04-22)**

- **Priority:** MEDIUM → LOW (output-gap component delivered; remaining
  residual is the per-country M2 scaffold work which depends on
  `CAL-CPI-INFL-T1-WRAPPERS`).
- **Scope:** OECD Economic Outlook / per-country statistics office
  output-gap connectors for 8 T1 countries beyond US/EA (JP + CA +
  AU + NZ + CH + SE + NO + DK). Populates
  `M2TaylorGapsInputs.output_gap_pct`. Removes the wire-ready-scaffold
  `raise InsufficientDataError` in each country's
  `build_m2_<country>_inputs`.
- **Sprint C (Week 10, 2026-04-22) outcome:**
  - OECD EO SDMX connector shipped — `src/sonar/connectors/oecd_eo.py`.
    Public endpoint, no auth key required. Annual cadence (`FREQ=A`)
    covering 1990 → 2027 (EO118 edition historicals + 2y forecasts).
  - Coverage confirmed live for 16 T1 ISO3 codes + EA aggregate (via
    legacy `EA17` code — `EA19 / EA20` return `NoRecordsFound` for
    the `GAP` measure).
  - 8 per-country M2 scaffolds + facade dispatch accept the
    `oecd_eo: OECDEOConnector | None` parameter and fetch the
    canonical output gap opportunistically. `InsufficientDataError`
    raise message now narrows to name the remaining blockers
    (CPI YoY + inflation-forecast) and explicitly states
    "output-gap live via OECD EO" when the fetch succeeds.
  - Pipeline lifecycle — `_build_live_connectors` instantiates the
    OECD EO connector alongside the rest of the monetary bundle;
    `aclose()` is called in the `finally` teardown.
- **Residual (open):**
  - Full M2 live compute still blocked per country on
    `CAL-CPI-INFL-T1-WRAPPERS` (CPI YoY + inflation-forecast per
    country). Once that CAL closes, the same eight scaffolds flip
    to full compute with no further L0 work (output-gap is already
    fetched).
  - US M2 deliberately unchanged — CBO GDPPOT quarterly path stays
    canonical (OECD EO USA annual is strictly coarser; HALT-13
    regression check shipped).
- **Unblocks:** M2 Taylor-gap compute across T1 (Phase 2 gate) pending
  `CAL-CPI-INFL-T1-WRAPPERS`. For DK, works alongside
  `CAL-DK-M2-EUR-PEG-TAYLOR` (structural spec revision for EUR-peg
  regime, preserved separately).
- **Replaces:** `CAL-120`, `CAL-130`, `CAL-AU-GAP`,
  `CAL-NZ-M2-OUTPUT-GAP`, `CAL-CH-GAP`, `CAL-SE-GAP`,
  `CAL-NO-M2-OUTPUT-GAP`, `CAL-DK-GAP` (8 items → 1).

### CAL-M3-T1-EXPANSION — M3 market-expectations overlays for T1 countries (Phase 2)

- **Priority:** MEDIUM — unblocks M3 T1 uniformity (Phase 2 gate).
  Dependent on CAL-138 (curves multi-country) for forward curves per
  country.
- **Scope:** `MarketExpectationsInputs` assembly for 8 T1 countries
  beyond US/EA (JP + CA + AU + NZ + CH + SE + NO + DK). Sources:
  - NSS forwards from curves per country (gated by CAL-138).
  - SPF / central-bank survey of inflation forecasts per market
    (BoJ Tankan, BoC MPR, RBA SoMP, RBNZ MPS, SNB GDP+CPI projections,
    Konjunkturinstitutet, Norges Bank MPR, Danish Economic Council).
  - OIS / FRA / swap rates per currency (ECB EUR, GBP, JPY, CAD, AUD,
    NZD, CHF, SEK, NOK, DKK).
- **Unblocks:** M3 compute across T1. Central dependency: CAL-138
  curves.
- **Replaces:** `CAL-122`, `CAL-132`, `CAL-AU-M3`, `CAL-NZ-M3`,
  `CAL-CH-M3`, `CAL-SE-M3`, `CAL-NO-M3`, `CAL-DK-M3`
  (8 items → 1).

### CAL-RATING-COHORT-EXPANSION — Rating-spread T1 cohort 10→15 países ✅ CLOSED

- **Status:** CLOSED 2026-04-26 via Week 11 Sprint 6 (branch
  `sprint-6-l2-rating-spread-cohort-expansion`). Opened informally by
  Sprint 4 (commit `f2cc4ef`, 2026-04-25) as future-sprint marker
  embedded in `src/sonar/overlays/rating_spread_backfill.py:14` and
  `tests/unit/test_overlays/test_rating_spread_te.py:241` —
  uncatalogued in this file at Sprint 4 close.
- **Scope shipped:**
  - `TIER1_COUNTRIES` tuple extended 10 → 15 in
    `src/sonar/overlays/rating_spread_backfill.py` (append NL, NZ,
    CH, SE, NO).
  - `TE_COUNTRY_OVERRIDES_TIER1` dict extended 10 → 15 (5 TE-name →
    ISO α-2 entries; verified empirically against TE Premium
    `/ratings` snapshot 2026-04-26).
  - `country_tiers.yaml` `rating_spread_live: true` flag added for
    NL+NZ+CH+SE+NO (Sprint 4 cohort flag back-fill = future
    janitorial task; TIER1_COUNTRIES is single source of truth).
  - `docs/specs/overlays/rating-spread.md` §12 country-scope appendix
    added (Shipped / Deferred / Source-resolution / Coverage metrics).
  - Sprint 6 amendment 2026-04-26 reduced cohort 6 → 5 (DK removed
    per ADR-0010 strict T1-ONLY through Phase 4; DK is T2 in
    `country_tiers.yaml:91`).
- **Tier B verification (engine DB post-backfill 2026-04-26):**
  - `ratings_agency_raw` 648 (Sprint 4 baseline 491 + Sprint 6
    contribution +118 + ~39 incremental TE 7d-cache misses).
  - `ratings_consolidated` 569 (Sprint 4 baseline 466 + Sprint 6
    +103).
  - `ratings_spread_calibration` 22 (unchanged).
  - 4 agencies present (SP=216, FITCH=175, MOODYS=157, DBRS=100).
  - Notch range [8.75, 21.25] within ck_rc_notch [-1.0, 22.0].
  - 15/15 sovereign T1 países represented; all 5 new país in
    consolidated table (CH=9, NL=16, NO=12, NZ=37, SE=29).
  - 4 invalid tokens (Sprint 4 pattern: NZ Moody's `Aa`/`Aa`/`Baa`
    truncated; NO Moody's `\tAaa` whitespace prefix) — log + skip +
    flag, not HALT.
  - TE quota delta: 6 calls (~0.12 pp); post-Sprint baseline ~40-41 %.
- **Numerical shortfall vs brief §6 thresholds (data-ceiling, not
  execution gap):**
  - agency_raw 648 vs brief target ≥660 (−12 short).
  - consolidated 569 vs brief target ≥580 (−11 short).
  - Root cause: TE archive depth ceiling for sparse high-grade
    Nordic-Alpine sovereigns (CH 8 historical actions; NO 11; NL 15)
    — these países have stable AAA-region ratings with very few
    rating events. Brief target was estimated from Sprint 4 PT/IT/ES
    (96/81/81 actions = high-volatility EA periphery cohort).
    See Sprint 6 retrospective §5 + §9 for full analysis.
- **Forward-looking residuals (NOT this sprint):**
  - DK rating-spread expansion deferred Phase 5+ — captured as
    CAL-RATING-DK-PHASE5 candidate in Sprint 6 retrospective §9
    (option B retro filing per Hugo decision; no separate CAL entry
    here).
  - Brief target heuristic methodology refinement for sparse/stable
    cohorts (CAL-RATING-COHORT-TARGET-CALIBRATION candidate, low
    priority) — captured in Sprint 6 retrospective §9.
  - Sprint 4 cohort `rating_spread_live: true` yaml flag back-fill
    (US/DE/FR/IT/ES/PT/GB/JP/CA/AU) = future janitorial task; not a
    blocker.

### CAL-EXPINF-LIVE-ASSEMBLER-WIRING — US EXPINF live wiring → M3 FULL ✅ CLOSED

- **Status:** CLOSED 2026-04-23 via Week 11 Sprint Q (branch
  `sprint-q-cal-expinf-live-assembler-wiring`). Opened by Sprint O
  audit `docs/backlog/audits/sprint-o-m3-exp-inflation-audit.md` §7
  2026-04-22 after the M3 classifier shipped with 0/9 runtime FULL
  (observability emit 9/9, runtime FULL 0/9 — "ghost FULL" pattern).
- **Scope shipped:** `src/sonar/indices/monetary/exp_inflation_loader.py`
  (new) composes FRED BEI (`T5YIE` / `T10YIE`) + FRED survey
  (`MICH` + `EXPINF10YR`) into ``build_canonical`` kwargs; `fred`
  added as optional field on `LiveConnectorSuite`; `LiveInputsBuilder._run`
  replaces the Sprint 7F hard-coded ``expected_inflation=None`` with
  the loader call; `daily_overlays._live_inputs_builder_factory` passes
  `fred` into the suite. Verified end-to-end with 3-day backfill
  (2026-04-21..23) — US `EXPINF_CANONICAL` `IndexValue` rows
  `(confidence=1.0, raw_value ≈ 0.024)` persisted and M3 classifier
  emits `mode=FULL` with `M3_FULL_LIVE` for US; 8 other T1 countries
  stay DEGRADED with existing flag sets.
- **Revised acceptance delta vs brief:** brief §5.1 item 4 anticipated
  ≥3 FULL (US + EA + GB); audit §1 revealed only US has live BEI +
  survey connectors today (Bundesbank / BoE / BoJ / BoC / ECB SDW
  expose no live inflation endpoints; country-native linker fetchers
  are stubs). Sprint Q ships **1/9 FULL (US)** and opens per-country
  CALs below to land the remaining 8.
- **Opens:** per-country BEI/survey connector CALs (below); these
  graduate M3 FULL coverage as connectors land. ADR-0011 Principle 8
  (observability-before-wiring) not promoted — pattern already surfaced
  by Sprint O audit-first discipline; revisit if E1/E3/E4 sprints hit
  the same premise gap.

### CAL-EXPINF-DE-BUNDESBANK-LINKER — DE BEI via Bundesbank inflation-linked Bund (Phase 2)

- **Priority:** MEDIUM — single-country FULL uplift. Unblocks DE M3
  DEGRADED→FULL once Bundesbank linker `BBSSY` family connector lands.
- **Scope:** `BundesbankConnector.fetch_yield_curve_linker` stub
  (`src/sonar/connectors/bundesbank.py:134`) → real implementation on
  `BBSSY` inflation-linked Bund series. Feeds DE branch of the Sprint Q
  loader (new per-country dispatch) → `ExpInfBEI` → `build_canonical`
  → `index_values(EXPINF_CANONICAL)` for DE → M3 classifier promotes
  DE to FULL.
- **Replaces:** `CAL-CURVES-DE-LINKER` reference in the stub docstring
  (re-scoped to this EXPINF-specific CAL since linker is only consumed
  by EXPINF overlay today).
- **Dependency:** none beyond Sprint Q closure.

### CAL-EXPINF-EA-ECB-SPF — EA survey expected-inflation via ECB SDW SPF ✅ CLOSED

- **Status:** Sprint Q.1 (2026-04-24) — CLOSED.
- **Outcome:** Shipped `EcbSdwConnector.fetch_survey_expected_inflation`
  (SDMX-CSV, 7-dim key `Q.U2.HICP.POINT.{horizon}.Q.AVG`) +
  `ExpInflationSurveyObservation` dataclass +
  `exp_inflation_writers.persist_survey_row` (idempotent SQLite
  upsert on `uq_exp_survey_cdsm`) + `compute_survey_spf` overlay
  helper + EA-cohort branch in
  `exp_inflation_loader.load_live_exp_inflation_kwargs` + factory
  wire-in through `LiveConnectorSuite.ecb_sdw` +
  `src/sonar/db/models.ExpInflationSurveyRow` ORM surface.
- **Method:** SPF publishes `REF_AREA=U2` only (no per-country series)
  — shipped as EA-aggregate proxy to EA members (DE/FR/IT/ES/PT/NL)
  carrying the `SPF_AREA_PROXY` flag. The SPF long-term (`LT`)
  horizon is mapped to the canonical `5Y`/`10Y`/`5y5y`/`30Y` tenors
  (`SPF_LT_AS_ANCHOR` flag); `1Y`/`2Y` derived from rolling target
  years (`survey_year + 1` / `+2`). Probe + decision documented in
  `docs/backlog/probe-results/sprint-q-1-ecb-spf-probe.md`.
- **Data coverage:** SPF quarterly; Sprint Q.1 backfill populated
  30 `exp_inflation_survey` rows (EA + DE + FR + IT + ES + PT × 5
  observation dates spanning 2026-02-15 → 2026-04-24).
- **M3 cascade:** Projected 6 countries M3 DEGRADED → FULL (pending
  downstream `daily_overlays --backend=live` run to persist
  `EXPINF_CANONICAL` in `index_values` for the EA cohort).
- **Related:** ADR-0011 Principle 1 (idempotent writer — INSERT OR
  IGNORE on unique key), Sprint Q parent (EXPINF live-assembler
  wiring, US).
- **Sub-CALs opened:**
  - `CAL-EXPINF-PER-COUNTRY-LINKERS-FOLLOWUP` — per-country BEI
    upgrades for DE/FR/IT/ES/PT/NL replacing the AREA_PROXY with
    national linker-based breakevens (Week 12+).
  - `CAL-ECB-SPF-MDN-VARIANT` — MDN source variant returned 404 at
    probe; AVG used. Low priority cross-check CAL.
  - `CAL-ECB-SPF-HISTOGRAM` — expose SPF distribution buckets for
    tail-risk / deflation-probability use cases (Phase 2+).

### CAL-EXPINF-GB-BOE-ILG-SPF — GB BEI via BoE inflation-linked gilts ✅ CLOSED (ILG leg)

- **Status:** CLOSED 2026-04-24 via Week 11 Sprint Q.2 (branch
  `sprint-q-2-cal-expinf-gb-boe-ilg-spf`). Retrospective at
  `docs/planning/retrospectives/week11-sprint-q-2-cal-expinf-gb-boe-ilg-spf-report.md`;
  pre-flight probe at
  `docs/backlog/probe-results/sprint-q-2-boe-ilg-spf-probe.md`.
- **Shipped:**
  - New connector `BoeYieldCurvesConnector` (distinct from the
    Akamai-blocked `BoEDatabaseConnector` IADB path) reading the
    public content-store ``glcinflationddata.zip`` → sheet
    ``4. spot curve``.
  - `exp_inflation_bei` table first writer:
    `persist_bei_row` in
    `src/sonar/indices/monetary/exp_inflation_writers.py`.
  - `build_m3_inputs_from_db` + `_load_histories` +
    `classify_m3_compute_mode` extended with BEI fallback branch
    (Lesson #20 #5 applied from start — all three shipped in the
    same commit). Priority cascade: canonical > survey > BEI.
  - 1578 GB BEI rows backfilled 2020-01-02 → 2026-03-31 via the
    idempotent `sonar.scripts.backfill_boe_bei` script.
  - GB M3 DEGRADED → FULL — compute-mode classifier emits
    ``m3_compute_mode=FULL`` with flags
    ``{GB_M3_T1_TIER, BEI_FITTED_IMPLIED, M3_EXPINF_FROM_BEI,
    M3_FULL_LIVE}`` when the cascade reaches the BEI branch.
- **Outstanding (sub-CALs):**
  - **`CAL-EXPINF-GB-SEF`** — BoE Survey of External Forecasters
    leg (survey-side divergence signal vs BEI). Deferred from
    Sprint Q.2 scope lock; Week 12+ if ILG-alone proves
    insufficient for the `BEI_SURVEY_DIVERGENCE` M3 observability
    signal.
  - **`CAL-EXPINF-GB-FORWARDS-BACKFILL`** — GB
    `yield_curves_forwards` only has 2 days of history in DB at
    Sprint-Q.2 close; full FRED gilt cascade backfill is pipeline
    ops, not an EXPINF-side CAL but tracked here for cross-ref.
- **Dependency:** none.

### CAL-EXPINF-FR-BDF-OATI-LINKER — FR BEI via Banque de France OATi/OATei (Phase 2)

- **Priority:** MEDIUM — OATei liquidity at 10Y-20Y is the deepest
  EA linker market; FR FULL uplift is highest-quality EA member
  promotion after EA aggregate.
- **Scope:** `BanqueDeFranceConnector.fetch_yield_curve_linker` stub
  (`src/sonar/connectors/banque_de_france.py:184`) → real OATi/OATei
  implementation. Loader adds FR branch composing `ExpInfBEI`.
- **Dependency:** CAL-EXPINF-EA-ECB-SPF (survey leg shared).

### CAL-EXPINF-EA-PERIPHERY-LINKERS — IT/ES BEI via BTP€i / Bonos€i (Phase 2)

- **Priority:** LOW-MEDIUM — long-run DEGRADED expected even post-ship
  per `M3_T1_DEGRADED_EXPECTED` (linker thin, structurally sparse).
  Ship still worth it to convert `M3_EXPINF_MISSING` → structural
  `{IT,ES}_M3_BEI_{BTP_EI,BONOS_EI}_{SPARSE,LIMITED}_EXPECTED`
  + confidence-penalty DEGRADED (a softer failure).
- **Scope:** `BancaDItaliaConnector.fetch_yield_curve_linker` +
  `BancoEspañaConnector.fetch_yield_curve_linker` stubs
  (`src/sonar/connectors/banca_ditalia.py:208` +
  `src/sonar/connectors/banco_espana.py:233`) → real BTP€i /
  Bonos€i implementations.
- **Dependency:** CAL-EXPINF-EA-ECB-SPF (survey leg shared).

### CAL-EXPINF-SURVEY-JP-CA — JP Tankan + CA BoC CES survey legs ✅ CLOSED (Sprint Q.3, Week 11 Day 1)

- **Shipped:** 2026-04-24 afternoon (Week 11 Day 1,
  `sprint-q-3-cal-expinf-survey-jp-ca`).
- **M3 impact:** 7 FULL → **9 FULL** / 0 DEGRADED / 3 NOT_IMPLEMENTED
  (PT / NL / AU — outside M3_T1_COUNTRIES). T1 coverage ~71% → ~75%.
- **Deliverables:**
  - `src/sonar/connectors/boj_tankan.py` — `BoJTankanConnector`
    (ZIP → `GA_E1.xlsx` → TABLE7 parser, 5-year bucket fallback).
  - `src/sonar/connectors/boc.py` — `fetch_ces_inflation_expectations`
    + `CESInflationExpectation` (stable Valet `CES_C1_{SHORT,MID,LONG}_TERM`
    aggregate series).
  - `src/sonar/connectors/boj_tankan_backfill.py` /
    `boc_ces_backfill.py` — CLI backfills invoking the Sprint Q.1
    `persist_survey_row` writer unchanged.
  - **Zero** classifier, builder, or writer changes — Lesson #20 #6
    audit completed **before** connector code found all three cascade
    sites (`build_m3_inputs_from_db` / `_load_histories` /
    `classify_m3_compute_mode`) filter by `country_code` alone.
- **DB state post-backfill:**
  - JP: 21 rows, 2021-03-01 → 2026-03-01 (quarterly), survey_name `BOJ_TANKAN`.
  - CA: 46 rows, 2014-10-01 → 2026-01-01 (quarterly), survey_name `BOC_CES`.
  - M3 flags: `TANKAN_LT_AS_ANCHOR` + `JP_M3_BEI_LINKER_THIN_EXPECTED`
    (JP); `CES_LT_AS_ANCHOR` + `CA_M3_BEI_RRB_LIMITED_EXPECTED` (CA).
- **Source deviation from brief:** BoC **CES** (Canadian Survey of
  Consumer Expectations) replaces brief's suggested **BOS** (Business
  Outlook Survey). BOS publishes per-quarter snapshot series with no
  stable long-run ID; CES has clean `CES_C1_*_TERM` aggregate series.
  Documented in probe §2.3.
- **Follow-up CALs opened:**
  - `CAL-EXPINF-JP-SCRAPE-PRE2020` — 2014-Q1 through 2020-Q4 Tankan
    data is PDF-only in the older `/gaiyo/2016/` bucket; scrape sprint
    Week 12+ if back-history analytically valuable.
  - `CAL-EXPINF-CA-BOS-AUGMENT` — business-side divergence signal vs
    consumer-side (BOS C12_S{1..3} per release), if value emerges.
- **Retrospective:** `docs/planning/retrospectives/week11-sprint-q-3-cal-expinf-survey-jp-ca-report.md`.

### CAL-EXPINF-JP-SCRAPE-PRE2020 — pre-2021 Tankan PDF scrape (Week 12+)

- **Priority:** LOW — 21 quarterly observations 2021-2026 already
  blanket the M3 survey path via forward-fill; pre-2020 data is
  analytical back-history only.
- **Scope:** scrape `/en/statistics/tk/gaiyo/2016/tka{YY}{MM}.pdf`
  (2016-2020) + `/en/statistics/tk/bukka/{year}/tkc{YY}{MM}.pdf`
  (2014-2015 standalone bukka), feed into the existing `BOJ_TANKAN`
  survey row writer. ~25 additional quarterly rows across 2014-Q1 →
  2020-Q4.
- **Dependency:** CAL-EXPINF-SURVEY-JP-CA (closed Sprint Q.3).

### CAL-EXPINF-CA-BOS-AUGMENT — BoC Business Outlook Survey cross-check (Week 12+)

- **Priority:** LOW — BOS is business-side; CES (already live) is
  consumer-side. Dual-survey panel gives divergence signal (businesses
  vs consumers on inflation) useful for L5 sentiment regime probes.
- **Scope:** per-release scraping of `BOS_{YYYY}Q{Q}_C12_S{1..3}`
  Valet series (BLP 1Y/2Y/5Y) + emission of
  `BOS_VS_CES_DIVERGENCE_BPS` sub-indicator. No M3 behaviour change —
  CES remains the canonical consumer-anchor leg.
- **Dependency:** CAL-EXPINF-SURVEY-JP-CA (closed Sprint Q.3).

### CAL-EXPINF-PER-COUNTRY-LINKERS-FOLLOWUP — per-country BEI replacing SPF_AREA_PROXY (Week 12+)

- **Priority:** MEDIUM — Sprint Q.1 ships DE/FR/IT/ES/PT/NL as
  EA-aggregate `SPF_AREA_PROXY`. Per-country upgrade via linker-based
  BEI gives each member its own inflation path, eliminates the proxy
  flag, improves M3 anchor precision.
- **Scope:** co-sequenced with `CAL-EXPINF-DE-BUNDESBANK-LINKER`,
  `CAL-EXPINF-FR-BDF-OATI-LINKER`, `CAL-EXPINF-EA-PERIPHERY-LINKERS`.
  Per-country linker connectors land; loader routes per-country BEI +
  the EA SPF as the shared SURVEY leg.
- **Dependency:** each of the per-country linker CALs above.

### CAL-ECB-SPF-MDN-VARIANT — SPF median source cross-check (Low / deferred)

- **Priority:** LOW — AVG source produces the Sprint Q.1 ship; MDN
  (median) is a pure cross-check overlay without behaviour change.
- **Scope:** Revisit Sprint Q.1 probe finding that
  `Q.U2.HICP.POINT.*.Q.MDN` returned HTTP 404 on the probe (likely a
  schema-generation lag or different key shape); fetch MDN variant
  when available + emit divergence flag when `|AVG - MDN| > 10 bps`.
- **Dependency:** CAL-EXPINF-EA-ECB-SPF (closed Sprint Q.1).

### CAL-ECB-SPF-HISTOGRAM — SPF distribution buckets for tail-risk signals (Phase 2+)

- **Priority:** LOW — Phase 2+ L5 meta-regime input. SPF emits full
  histogram buckets (100+ `FN_X_N_Y` codes in `CL_FCT_BREAKDOWN`) per
  target year — usable for deflation-probability / skew signals that
  inform the L5 regime classifier.
- **Scope:** extend `ExpInflationSurveyObservation` with optional
  histogram payload; expose a `fetch_spf_histogram` method on
  `EcbSdwConnector`; write a dedicated histogram table + downstream
  L5 consumer.
- **Dependency:** CAL-EXPINF-EA-ECB-SPF (closed Sprint Q.1) + L5
  regime spec (Phase 2+).

### CAL-M3-DEGRADED-MODE-UPLIFT — Tracking umbrella for DEGRADED→FULL transitions (Phase 2)

- **Priority:** tracking — closes when all 9 T1 M3 countries reach
  FULL (contingent on the 6 per-country CALs above).
- **Scope:** periodic re-check of M3 coverage as EXPINF connectors
  mature. Retrospective per quarter summarising deltas.
- **Dependency:** CAL-EXPINF-DE-BUNDESBANK-LINKER +
  CAL-EXPINF-EA-ECB-SPF + CAL-EXPINF-GB-BOE-ILG-SPF +
  CAL-EXPINF-FR-BDF-OATI-LINKER + CAL-EXPINF-EA-PERIPHERY-LINKERS +
  CAL-EXPINF-SURVEY-JP-CA.

### CAL-M4-T1-FCI-EXPANSION — M4 FCI 5-component bundles for T1 countries ✅ CLOSED

- **Status:** CLOSED 2026-04-23 via Week 10 Sprint J (branch
  `sprint-m4-fci-t1-expansion`). Retrospective at
  `docs/planning/retrospectives/week10-sprint-m4-fci-t1-report.md`;
  pre-flight probe matrix at
  `docs/planning/week10-sprint-j-m4-fci-t1-preflight-findings.md`.
- **Shipped scope** (6 implementation commits + pre-flight):
  - Commit 1 (`f693c02`) — Sprint J brief v3 + pre-flight probe
    matrix (48 probes across 16 T1 + EA aggregate × 3 legacy
    components). HALT-0 cleared; HALT-14 surfaced (SCAFFOLD > 6).
  - Commit 2 (`33e8dee`) — TE equity-volatility markets wrappers
    (`VIX:IND` + `VSTOXX:IND`) + FRED OAS wrappers (`BAMLC0A0CM` US
    IG + `BAMLHE00EHYIOAS` EA HY).
  - Commit 3 (`6a2d51d`) — `BisConnector.fetch_neer` on
    `M.N.B.{CTY}` (BIS WS_EER broad-basket, monthly). 17/17 coverage.
  - Commit 4 (`6c0e414`) — `ecb_sdw.fetch_mortgage_rate` (MIR
    `M.{CC}.B.A2C.A.R.A.2250.EUR.N`) + monthly `TIME_PERIOD` parse +
    `_assemble_m4_ea_custom_inputs` helper + `build_m4_ea_inputs` +
    `build_m4_de_inputs` + US canonical regression guard
    (`TestSprintJUsBaselineGuard`, HALT-1 absolute).
  - Commit 5 (`162ea2b`) — `build_m4_{fr,it,es,nl,pt}_inputs`
    EA-member FULL-compute wrappers + `build_m4_gb_inputs` scaffold +
    `_M4_EA_PROXY_BUILDERS` dispatch dict.
  - Commit 6 (`e09d8b4`) — pipeline `_classify_m4_compute_mode` +
    `monetary_pipeline.m4_compute_mode` observability log +
    `MONETARY_SUPPORTED_COUNTRIES` DE/FR/IT/ES/NL/PT +
    `_build_live_connectors` BIS plumbing.
- **Coverage post-merge:** **8/17 entities FULL compute** (US
  canonical + 7 new: EA + DE + FR + IT + ES + NL + PT via shared-EA
  proxy pattern) + **9/17 SCAFFOLD** (GB new + 8 preserved: AU / CA /
  CH / DK / JP / NO / NZ / SE). 17/17 dispatcher-wired. US canonical
  preserved absolutely (HALT-1, unit regression guard PASS).
- **Components shipped:**
  1. BIS NEER on `M.N.B.{CTY}` — monthly, 17/17 coverage. Daily
     cadence deferred to `CAL-M4-NEER-FREQUENCY-DAILY` below.
  2. VSTOXX via TE markets — EA aggregate + 6 EA members via
     shared-EA-proxy convention. Per-country tier-3 vol symbols
     (`V2TX`, `VFTSE`, `NKYVOLX`, etc.) empty at our TE key;
     deferred to `CAL-M4-VOL-T2-TIER3-EXPANSION` below.
  3. BAML EA HY OAS (`BAMLHE00EHYIOAS`) via FRED — shared-EA credit
     spread for EA + 6 EA members. Per-country OAS deferred to
     `CAL-M4-CREDIT-SPREAD-T2-PER-COUNTRY` below.
  4. ECB MIR mortgage rate on `M.{CC}.B.A2C.A.R.A.2250.EUR.N` —
     7 EA entities. Non-EA T1 per-CB native mortgage series
     deferred to `CAL-M4-MORTGAGE-RATE-T1-NATIVE-EXPANSION` below.
  5. 10Y sovereign yield via TE `fetch_sovereign_yield_historical`
     (Sprint I-patch surface) or NSS overlay — all 17 entities
     covered through pre-existing curves work.
- **Replaces:** `CAL-121`, `CAL-131`, `CAL-AU-M4-FCI`,
  `CAL-NZ-M4-FCI`, `CAL-CH-M4-FCI`, `CAL-SE-M4-FCI`, `CAL-NO-M4-FCI`,
  `CAL-DK-M4-FCI` (8 items → 1, all closed by this sprint). Does NOT
  replace `CAL-DK-M4-EUR-PEG-FCI` (DK EUR-peg hybrid preserved
  separately).
- **Opens:** 4 follow-on CAL items to close the remaining 9
  SCAFFOLD entities' per-component gaps — see below.

### CAL-M4-VOL-T2-TIER3-EXPANSION — National equity-vol index for 9 non-EA-proxy T1 countries (Phase 2)

- **Priority:** HIGH-MEDIUM — single-component gap blocks 9/17 M4
  entities from reaching FULL. Opens post-Sprint-J.
- **Scope:** national equity-vol index for GB / JP / CA / AU / NZ /
  CH / SE / NO / DK (9 countries). Sprint J pre-flight established
  TE tier-3 symbols `V2TX` / `VFTSE` / `NKYVOLX` / national
  equivalents return `200 []` at our API key.
- **Candidate sources (empirical-probe required):**
  - Upgrade TE API tier (single action; unblocks all 9 if tier-3
    covers the missing symbols).
  - Yahoo Finance `^VIXC` (CA) / `^AXVI` (AU) / `^VFTSE` (GB) /
    `^NKYVOLX` (JP) — requires a Yahoo Finance connector extension.
  - stooq.com historical + computed implied-vol surface per country.
- **Unblocks:** moves 9 entities closer to FULL (from 2/5 → 3/5);
  combined with the 2 CALs below, moves them to FULL (5/5).
- **Opened by:** Sprint J Commit 7 (`CAL-M4-T1-FCI-EXPANSION` closure).

### CAL-M4-CREDIT-SPREAD-T2-PER-COUNTRY — Per-country IG/HY OAS beyond BAML (Phase 2.5)

- **Priority:** MEDIUM — second-component gap blocking the same 9
  non-EA-proxy entities as `CAL-M4-VOL-T2-TIER3-EXPANSION`.
- **Scope:** per-country IG or HY OAS (credit-spread vs sovereign)
  for GB / JP / CA / AU / NZ / CH / SE / NO / DK. Sprint J pre-flight
  confirmed FRED exposes only `BAMLC0A0CM` (US IG) + `BAMLHE00EHYIOAS`
  (EA HY); per-country BAML series not published.
- **Candidate sources:**
  - ICE Data direct (paywalled — SLA / commercial decision needed).
  - IHS iBoxx feeds (paywalled).
  - National-CB bond-yield composites: RBA F3 corporate yield, BoE
    IUDR-family, BoJ JGB spreads, BoC bond curves. Most are IG-
    equivalent not HY; may still meet the spec §4 intent.
  - Synthetic credit-spread: per-country sovereign curve (NSS
    overlay) + corporate-yield proxy once TE / BBG provisions.
- **Unblocks:** 9 entities to 4/5 components (combined with
  `CAL-M4-VOL-T2-TIER3-EXPANSION`).
- **Opened by:** Sprint J Commit 7.

### CAL-M4-MORTGAGE-RATE-T1-NATIVE-EXPANSION — Per-CB native mortgage rate for 9 non-EA T1 countries (Phase 2)

- **Priority:** MEDIUM — third-component gap for the 9 non-EA-proxy
  entities. ECB MIR already covers the 7 EA entities.
- **Scope:** per-CB native mortgage-rate series for GB / JP / CA /
  AU / NZ / CH / SE / NO / DK. Each CB publishes a canonical
  household mortgage rate on its native connector surface:
  - BoE IUMTLMV — gated behind Akamai (see Sprint I-patch learnings;
    browser-gate or rotating-UA bypass required).
  - BoJ prime rate (published monthly on BoJ website).
  - BoC V39079-family (Valet API; reachable public endpoint).
  - RBA G3 housing-loan rates (daily CSV).
  - RBNZ B19 (host perimeter currently 403 — see `CAL-NZ-RBNZ-TABLES`).
  - SNB monthly bulletin mortgage rates.
  - Riksbank MFI interest rates.
  - Norges Bank interest statistics (bank-reporting rates).
  - Nationalbanken MFI interest rates.
- **Unblocks:** 9 entities to **5/5 FULL** when combined with
  `CAL-M4-VOL-T2-TIER3-EXPANSION` + `CAL-M4-CREDIT-SPREAD-T2-PER-COUNTRY`.
- **Opened by:** Sprint J Commit 7.

### CAL-M4-NEER-FREQUENCY-DAILY — Daily NEER via bilateral-FX composite (Phase 2.5)

- **Priority:** LOW — does not block FULL compute (monthly NEER with
  most-recent-available anchor is spec-compliant). Every Sprint J
  FULL-compute emits `{CC}_M4_NEER_MONTHLY_CADENCE` as observability.
- **Scope:** reconstruct daily NEER per country via bilateral-FX
  composite — sum of weighted spot rates against the BIS EER basket
  weights (narrow or broad). Requires (a) BIS EER weight matrix
  connector (CAL-TBD), (b) daily bilateral-FX connector (FRED + TE
  already cover the major pairs; extend as needed), (c) composite
  assembler with monthly-weight / daily-spot assembly.
- **Unblocks:** daily-cadence FCI compute (Phase 2.5 dashboards /
  backtest). Not a Phase 2 blocker.
- **Opened by:** Sprint J Commit 7.

### CAL-BS-GDP-T1-EXPANSION — Central-bank balance-sheet / GDP ratio for T1 countries (Phase 2.5)

- **Priority:** LOW — M4 FCI nice-to-have signal (QE / QT intensity).
- **Scope:** `<country>_BS_GDP` signal per country — central-bank
  balance sheet (CB assets in LCU) ÷ nominal GDP (LCU, quarterly).
  Replaces the per-country `<CC>_BS_GDP_PROXY_ZERO` flag currently
  emitted as placeholder.
- **Sources per country:**
  - JP — BoJ balance sheet statistics.
  - CA — BoC weekly statement + StatCan GDP.
  - AU — RBA statistical tables D3 + ABS GDP.
  - NZ — RBNZ balance sheet + StatsNZ GDP.
  - CH — SNB monthly bulletin + SECO GDP.
  - SE — Riksbank balance sheet + SCB GDP.
  - NO — Norges Bank balance sheet + StatsNorway GDP.
  - DK — Danmarks Nationalbanken balance sheet + DST GDP.
- **Unblocks:** M4 FCI signal breadth; proper QE/QT intensity
  measurement cross-country.
- **Replaces:** `CAL-123`, `CAL-133`, `CAL-AU-BS-GDP`,
  `CAL-NZ-BS-GDP`, `CAL-CH-BS-GDP`, `CAL-SE-BS-GDP`, `CAL-NO-BS-GDP`,
  `CAL-DK-BS-GDP` (8 items → 1).

### CAL-CPI-INFL-T1-WRAPPERS — CPI YoY + inflation-forecast wrappers for T1 countries ✅ CLOSED

- **Status:** CLOSED 2026-04-22 via Week 10 Sprint F (branch
  `sprint-cpi-infl-t1-wrappers`). Retrospective at
  `docs/planning/retrospectives/week10-sprint-cpi-infl-t1-report.md`.
- **Shipped scope** (7 commits + pre-flight):
  - Commit 1 (`1fb8be8`) — TE CPI + forecast wrappers CA / AU / NZ
    (6 methods) + per-country `TE_CPI_YOY_EXPECTED_SYMBOL` guards
    for all 16 T1 countries + `TEInflationForecast` dataclass +
    shared `fetch_inflation_forecast` core. Pre-flight probe body
    documented per-country HistoricalDataSymbol + frequency +
    historical depth. ECB SDW fallback evaluated as HALT-1 and
    **not required** — TE coverage complete for all 16 T1 countries
    (inverse of Sprint A EA-periphery outcome).
  - Commit 2 (`3233d27`) — TE CPI + forecast wrappers
    CH / SE / NO / DK / GB / JP (12 methods). Negative-rate era
    has zero CPI impact; no `*_NEGATIVE_RATE_ERA_DATA` flag needed
    (that flag is policy-rate semantic, not CPI). SE-headline-not-
    CPIF caveat documented.
  - Commit 4 (`7f595cf`) — M2 builders CA / AU / NZ / CH / SE / NO / DK
    flipped scaffold → full compute via shared
    `_assemble_m2_full_compute` helper. AU `_CPI_SPARSE_MONTHLY`,
    NZ `_CPI_QUARTERLY`, CH `_INFLATION_TARGET_BAND`, DK
    `_EUR_PEG_TAYLOR_MISFIT`, SE `_CPI_HEADLINE_NOT_CPIF` flags.
  - Commit 5 (`6abaed7`) — M2 JP flipped + M2 GB first-ship +
    US M2 canonical regression guard
    (`TestSprintFUsBaselineGuard`).
  - Commit 6 (`d5eb810`) — Pipeline `_classify_m2_compute_mode`
    helper + `monetary_pipeline.m2_compute_mode` log line +
    `tests/integration/test_daily_monetary_m2_full_compute.py`
    integration smoke (10 live canaries, 34.5s wall-clock).
- **Coverage:** 10 of 16 T1 countries at **full-compute live**
  (US canonical + 9 non-EA T1). EA + per-country EA members
  (DE/FR/IT/ES/NL/PT) deferred per ADR-0010 phased-completion to
  dedicated CAL items (`CAL-M2-EA-PER-COUNTRY` +
  `CAL-M2-EA-AGGREGATE` — both opened in this sprint).
- **Cross-validation** (documented in retrospective §3): headline
  CPI YoY values per country vs TE web + BLS / ECB / ONS / Eurostat
  latest published values match within < 10 bps (standard CPI
  numerology — TE mirrors the underlying statistics offices).
- **Replaces:** `CAL-126`, `CAL-134`, `CAL-135`, `CAL-AU-CPI`,
  `CAL-AU-INFL-FORECAST`, `CAL-NZ-CPI`, `CAL-NZ-INFL-FORECAST`,
  `CAL-CH-CPI`, `CAL-CH-INFL-FORECAST`, `CAL-SE-CPI`,
  `CAL-SE-INFL-FORECAST`, `CAL-NO-CPI`, `CAL-NO-INFL-FORECAST`,
  `CAL-DK-CPI`, `CAL-DK-INFL-FORECAST` (15 items → 1, now all
  closed via this umbrella item).

### CAL-M2-EA-PER-COUNTRY — M2 per-country EA member Taylor compute (Phase 2+)

- **Priority:** LOW — academically ambiguous; deferred until spec
  revision.
- **Trigger:** Week 10 Sprint F (2026-04-22) scoped out DE / FR / IT /
  ES / NL / PT individual M2 builders because the Taylor rule's
  policy-rate instrument is the ECB Deposit Facility Rate (shared
  across EA members). A country-specific reaction-function spec
  — e.g. a "DE-M2-as-if-Bundesbank" counterfactual rule —
  requires explicit methodology decisions the brief avoided.
- **Scope:** Drafting a per-country EA M2 spec revision in
  `docs/specs/indices/monetary/M2-taylor-gaps.md` (new §5 — "EA
  member per-country adaptation"), plus the 6 corresponding
  builders (`build_m2_{de,fr,it,es,nl,pt}_inputs`) and dispatch
  wiring. TE CPI + forecast wrappers for these 6 countries were
  **already** shipped in Sprint F Commits 1-2 via the
  `TE_CPI_YOY_EXPECTED_SYMBOL` registry — spec decisions remain
  the only blocker.
- **Unblocks:** M2 full-compute coverage 10 → 16 of 16 T1.

### CAL-M2-EA-AGGREGATE — M2 Taylor compute for EA aggregate ✅ CLOSED

- **Status:** CLOSED 2026-04-22 via Sprint L (Week 10 Day 2).
- **Resolution commits (sprint-m2-ea-aggregate branch):**
  - `ed420f4` — TE `fetch_ea_hicp_yoy` + `fetch_ea_inflation_forecast`
    + pre-flight probe (HALT-1 inversion — ECB SDW HICP/SPF extension
    not required; TE coverage confirmed complete during Commit 1
    probe 1991-01-31 → 2026-03-31).
  - `d79030d` — `build_m2_ea_inputs` wiring ECB DFR + TE EA HICP +
    TE EA inflation forecast + OECD EO EA17 output gap (via Sprint C
    `EA → EA17` country map). MonetaryInputsBuilder facade dispatch
    updated. **US M2 canonical regression guard** (HALT-3 absolute):
    `TestSprintLUsBaselineGuard` + `test_m2_us_canonical_preserved`
    both passed — US path remains `(\"fred\", \"cbo\")` with CBO
    GDPPOT primary and no Sprint L flag leakage.
  - `809766e` — `test_m2_ea_aggregate_full_compute_live_sprint_l`
    integration live canary (@pytest.mark.slow). Exercises the full
    pipeline path via `build_live_monetary_inputs`; asserts
    `EA_M2_FULL_COMPUTE_LIVE` + OECD_EO output-gap source + EA-specific
    source_connector tuple (`ecb_sdw` first, no `fred`/`cbo` leakage).
    Wall-clock 5.21s.
- **Shipped scope:**
  - Policy rate: ECB DFR (`EA_M2_POLICY_RATE_ECB_DFR_LIVE`).
  - HICP YoY: TE `ECCPEMUY` (`EA_M2_CPI_TE_LIVE`).
  - Inflation forecast: TE q4 ≈ 12m-ahead (`EA_M2_INFLATION_FORECAST_TE_LIVE`).
  - Output gap: OECD EO EA17 (`EA_M2_OUTPUT_GAP_OECD_EO_LIVE`).
  - r*: HLW EA Q4 2024 = -0.5 % (native, non-proxy — no
    `R_STAR_PROXY` flag).
  - Inflation target: ECB 2 % (`bc_targets.yaml:EA → ECB`).
- **Live canary output (2026-04-22 anchor)**:
  policy_rate 0.0300 / HICP 0.0260 / forecast 0.0260 / gap -0.7339 /
  target 0.0200 / r* -0.0050. `EA_M2_FULL_COMPUTE_LIVE` emitted.
- **Deferred (opened during Sprint F, still open):**
  - `CAL-M2-EA-PER-COUNTRY` — per-country Taylor compute for the 6 EA
    members (DE / FR / IT / ES / NL / PT). Blocker: methodology spec
    revision. TE CPI + forecast wrappers for these 6 countries
    already shipped in Sprint F Commits 1-2; Sprint L did **not**
    touch the per-country EA M2 dispatch (still `NotImplementedError`
    with narrowed message pointing only at `CAL-M2-EA-PER-COUNTRY`).
- **M2 T1 coverage post-merge:** 11 of 16 (US canonical LEGACY + EA
  aggregate FULL via Sprint L + 9 non-EA FULL via Sprint F). Gap =
  6 EA per-country members (`CAL-M2-EA-PER-COUNTRY`).

### CAL-138 — daily_curves multi-country support (Phase 1 US-only expansion) ✅ CLOSED

- **Status:** CLOSED 2026-04-22 via Sprint CAL-138 (Week 10 Day 1-2).
- **Resolution commits (sprint-cal138-curves-multi-country branch):**
  - `f7d5d18` — pre-flight + ECB SDW / Bundesbank linker stubs.
  - `a47f469` — TE fetch_yield_curve_nominal for GB/JP/CA
    (12/9/6 tenors per empirical scope).
  - `680282b` — pipeline multi-country dispatch + ``--all-t1`` + 9
    integration tests (5 live canaries).
  - `4ba3d91` — systemd service + ops docs refreshed to ``--all-t1``.
- **Shipped scope** (HALT trigger 1 scope narrow per empirical probe):
  - US → FRED (existing, unchanged).
  - DE → Bundesbank (existing connector wired into pipeline).
  - EA → ECB SDW YC EA-AAA aggregate (existing connector wired).
  - GB → TE GUKG family (new, 12 tenors 1M-30Y).
  - JP → TE GJGB family (new, 9 tenors 1M-10Y).
  - CA → TE GCAN family (new, 6 tenors NS-reduced).
  - Pipeline ``--all-t1`` originally iterated the shared T1_7 tier;
    superseded Week 10 Sprint E (``CAL-CURVES-T1-SPARSE-INCLUSION``
    2026-04-22) by a pipeline-local ``T1_CURVES_COUNTRIES`` tuple
    ``(US, DE, EA, GB, JP, CA)`` that reflects the curve-capable
    scope — the EA periphery members are dropped from iteration
    because they always skipped (the five per-country CAL items
    below are the re-entry path); AU/NZ/CH/SE/NO/DK remain deferred
    under ``CAL-CURVES-T1-SPARSE``.
- **Deferred gaps** (opened as separate tracked items):
  - ``CAL-CURVES-EA-PERIPHERY`` — **SUPERSEDED** Week 10 Sprint A
    (2026-04-22) by five per-country items
    (``CAL-CURVES-PT-BPSTAT`` / ``CAL-CURVES-IT-BDI`` /
    ``CAL-CURVES-ES-BDE`` / ``CAL-CURVES-FR-BDF`` /
    ``CAL-CURVES-NL-DNB``) after ECB SDW FM-dataflow fallback
    probe failed (no EA-periphery REF_AREA published).
  - ``CAL-CURVES-T1-SPARSE`` — AU/NZ/CH/SE/NO/DK full yield curves
    (TE exposes only 1-2 tenors per country; native CB connectors
    Phase 2+).
  - ``CAL-CURVES-T1-LINKER`` — inflation-indexed curves for DE/GB/
    JP/CA + EA periphery (US TIPS already live via FRED DFII).
  - ``CAL-CURVES-CA-MIDCURVE`` — CA has 1M/3M/6M/1Y/2Y/10YR via TE;
    3Y/5Y/7Y gap forces NS-reduced fit. BoC Valet has finer spectrum.
- **Production impact:** tomorrow 06:00 UTC ``sonar-daily-curves.service``
  will invoke ``--all-t1``; DE persists alongside US. 07:30 WEST
  ``sonar-daily-overlays.service`` gains functional DE overlay
  cascade (ERP / CRP / rating-spread / expected-inflation).

### CAL-CURVES-EA-PERIPHERY — EA periphery per-country sovereign yield curves (PT/IT/ES/FR/NL) — **SUPERSEDED**

- **Status:** **SUPERSEDED** by five per-country items Week 10 Sprint A (2026-04-22) after the umbrella-scope brief's ECB SDW fallback path (HALT-0 "FM dataflow + SONAR NSS fit") was empirically invalidated: FM publishes no EA-periphery ``REF_AREA`` (live set: U2/DK/GB/JP/SE/US).
- **Successor items:** ``CAL-CURVES-PT-BPSTAT`` / ``CAL-CURVES-IT-BDI`` / ``CAL-CURVES-ES-BDE`` / ``CAL-CURVES-FR-BDF`` / ``CAL-CURVES-NL-DNB`` (one per national CB; scoped individually so each can ship independently).
- **Sprint artefact:** ``docs/planning/retrospectives/week10-sprint-ea-periphery-report.md`` records the probe output + scope-narrow rationale.
- **Original scope** (preserved for cross-reference):
  - Priority MEDIUM — unblocks per-country ERP/CRP/rating-spread for the 5 EA periphery members (currently on ``EA_AAA_PROXY_FALLBACK``).
  - Trigger: CAL-138 Sprint empirical probe 2026-04-22 first documented ECB SDW ``YC`` dataflow is EA-aggregate only.
  - Original required work (now decomposed per-country):
    1. Native connectors per periphery CB:
       - PT → Banco de Portugal BPstat API (sovereign yields, OT benchmark maturities).
       - IT → Banca d'Italia BDS (BTP zero-coupon curves).
       - ES → Banco de España (BCE SeriesTemporales — Bonos y Obligaciones).
       - FR → Banque de France Webstat (OAT zero-coupon 1Y-30Y).
       - NL → DNB Statistics (DSL yields limited historical + ESS fallback).
    2. NSS fit validation per country (credit spreads differ vs Bund so β0/β1 bounds likely unchanged, but sanity-check convergence on high-spread PT/IT periods).
    3. Pipeline dispatch extension (add periphery branch alongside DE Bundesbank).
    4. Live canaries per country (2024-12-30 baseline).
- **Related:** CAL-138 (grandparent, closed); CAL-CURVES-T1-LINKER (linker coverage — will fold into the per-country sprints).

### CAL-CURVES-FR-BDF — FR sovereign yield curve via Banque de France Webstat — **BLOCKED (national-CB direct path) · daily-pipeline surface CLOSED via TE cascade Sprint I 2026-04-22**

- **Sprint I sharpening (2026-04-22):** the daily-pipeline surface for FR no longer depends on this CAL — Sprint I shipped FR via the TE per-tenor cascade (10-tenor `GFRN` OAT family; closes ``CAL-CURVES-FR-TE-PROBE``). This entry retains BLOCKED status strictly for the **direct-CB national-feed upgrade path** (Banque de France / AFT / licensed-feed alternatives). Pipeline behaviour: ``daily_curves --country FR`` and ``--all-t1`` now persist a 10-tenor Svensson fit via TE (RMSE 2.005 bps, confidence 1.0 on 2024-12-30 live canary). Overlay cascade gains functional FR branch starting 2026-04-23 post-merge; FR no longer falls back to EA-AAA proxy. Future direct-CB connector swap-in remains the documented unblock path — ``BanqueDeFranceConnector`` scaffold preserved for that purpose.
- **Status:** **BLOCKED (direct-CB path)** Week 10 Sprint D pilot pre-flight 2026-04-22 — all four brief §9 fallback data paths (BdF primary / AFT / TE / FRED) failed to provide a ≥ 6-tenor daily FR sovereign yield curve. HALT trigger 0 fired; narrow-scope ship per Sprint A / CAL-138 precedents. Pilot outcome inverts the brief's assumption that BdF would mirror Bundesbank cleanly, and consequently **re-frames the probe discipline for the four successor EA-periphery sprints** (``CAL-CURVES-IT-BDI`` / ``CAL-CURVES-ES-BDE`` / ``CAL-CURVES-PT-BPSTAT`` / ``CAL-CURVES-NL-DNB``). Sprint I subsequently demonstrated that the Sprint D entry "TE GFRN10 10Y-only" was itself a single-symbol-probe artifact superseded by a per-tenor sweep — but the BdF / AFT / FRED legs of the Sprint D matrix remain unchanged and still block the direct-feed alternative.
- **Priority:** DEFERRED — parked pending either (a) BdF restoring a per-tenor daily feed through its OpenDatasoft portal (the one dataset currently exposed is a monthly archive frozen 2024-07-11), (b) SONAR provisioning a licensed feed (Bloomberg / Refinitiv / FactSet), or (c) a successor sprint running a browser-automation shim against AFT to bypass the Cloudflare challenge. Daily pipeline already served by TE cascade — this CAL motivates only redundancy / vendor lock-in mitigation / richer microstructure data, not core pipeline functionality.
- **Trigger:** Week 10 Sprint D pilot pre-flight probe 2026-04-22 — see commit (Commit 1, scaffolded connector ``src/sonar/connectors/banque_de_france.py``) and retrospective ``docs/planning/retrospectives/week10-sprint-curves-fr-bdf-report.md``. Earlier Sprint A probe 2026-04-22 had already ruled out ECB SDW ``YC``/``FM``/``IRS`` as feasible surfaces; Sprint D completes the fallback-hierarchy audit. Sprint I (2026-04-22) closes the TE leg via cascade — see ``docs/planning/retrospectives/week10-sprint-curves-fr-te-probe-report.md``.
- **Current behavior (post Sprint I):** ``daily_curves --country FR`` persists a 10-tenor Svensson fit via TE; ``--all-t1`` includes FR (9-country tuple). The scaffolded ``BanqueDeFranceConnector`` remains documentation-first + future direct-CB placeholder — **not** wired into the dispatcher (TE branch handles FR via `TE_YIELD_CURVE_SYMBOLS["FR"]`). Sprint I removed FR from ``_DEFERRAL_CAL_MAP``. Direct-CB unblock conditions below unchanged from Sprint D.
- **Fallback-hierarchy probe matrix (2026-04-22):**
  - **BdF legacy SDMX REST** ``https://webstat.banque-france.fr/ws_wsfr/rest/data/`` — HTTP 404. Decommissioned when BdF migrated ``webstat`` to the OpenDatasoft platform mid-2024.
  - **BdF OpenDatasoft explore API** ``https://webstat.banque-france.fr/api/explore/v2.1/catalog/datasets`` — ``total_count=1``. Single dataset ``tableaux_rapports_preetablis``; yield-adjacent file ``Taux_indicatifs_et_OAT_Archive.csv`` carries 8 tenors {1M, 3M, 6M, 9M, 12M, 2Y, 5Y, 30Y} (**no 10Y benchmark**), end-of-period monthly, publication frozen 2024-07-11. Unfit for daily pipelines on frequency + tenor completeness.
  - **AFT direct** ``https://www.aft.gouv.fr/`` — HTTP 403 behind Cloudflare managed-challenge (``cf-mitigated: challenge``). Not viable for headless pipelines.
  - **TE ``fetch_fr_yield_curve_nominal``** — never shipped Sprint CAL-138 (FR exposes only ``GFRN10:IND`` via ``/markets/historical``; 10Y single-tenor, below ``MIN_OBSERVATIONS=6``). FR is absent from ``TE_YIELD_CURVE_SYMBOLS``.
  - **FRED OECD mirror** — ``IRLTLT01FRM156N``: 10Y only, monthly frequency. Insufficient.
- **Pilot artefacts shipped (scope-narrow):**
  1. ``src/sonar/connectors/banque_de_france.py`` — documentation-first scaffold preserving ``BaseConnector`` interface; every fetch method raises ``InsufficientDataError`` citing the CAL pointer + probe date + findings.
  2. ``docs/adr/ADR-0009-national-cb-connectors-ea-periphery.md`` — pattern lessons for IT/ES/PT/NL pre-flights (required probe sequence, migration-risk budget adjustment, alternative-source research track).
  3. ``docs/planning/retrospectives/week10-sprint-curves-fr-bdf-report.md`` — v3-format retrospective.
- **Required work (future, when unblocked):**
  1. Re-probe BdF OpenDatasoft catalog and AFT surfaces (via browser-automation shim if Cloudflare remains in place).
  2. Swap ``BanqueDeFranceConnector`` fetch methods for real HTTP logic once a viable source is identified; the interface is frozen so the delta is methods-only.
  3. Wire into ``daily_curves.run_country`` FR branch alongside DE Bundesbank; drop FR from ``_DEFERRAL_CAL_MAP``.
  4. Unit tests on live data + @slow canary + cross-validation against a public reference (Trésor / OECD / Reuters).
- **Impact if unresolved (post Sprint I):** FR overlays (ERP / CRP / rating-spread / expected-inflation) now read country-specific OAT term structure via TE; ``MATURE_ERP_PROXY_FR`` / ``EA_AAA_PROXY_FALLBACK`` flags no longer fire on FR runs starting 2026-04-23 post-merge. Direct-CB upgrade would add redundancy + per-ISIN secondary-market microstructure (OATei included) currently unavailable via TE benchmark-only publication.
- **Estimate (future):** 4-6h CC (original 3-4h was predicated on a BdF-is-Bundesbank analog assumption; the probe matrix inflates the budget for re-probe + alternative-source research + either a browser-automation shim or a licensed-feed integration). Lower urgency post Sprint I — not blocking any pipeline.
- **Related:** ``CAL-CURVES-EA-PERIPHERY`` (superseded grandparent); ``CAL-CURVES-FR-TE-PROBE`` (Sprint I — CLOSED via TE cascade; canonical Path 1 separation from this entry's Path 3 direct-CB scope); ``CAL-CURVES-T1-LINKER`` FR portion absorbed here (OATei coverage irrelevant while nominal path was blocked; Sprint I unblocks nominal but leaves linker side gap unchanged); ``ADR-0009`` v2.1 (Sprint I addendum — TE Path 1 canonical reinforcement); ``CAL-CURVES-IT-ES-LINKER`` (FR linker probe could fold into this entry on a future sweep — natural extension because TE Bloomberg `ITBI*` / `ESBI*` probe shape carries forward).

### CAL-CURVES-IT-BDI — IT sovereign yield curve via Banca d'Italia BDS — **CLOSED (via TE cascade, Sprint H 2026-04-22)**

- **Priority:** MEDIUM — IT has the widest sovereign-spread range of the periphery (post-2011 crisis, 2018 Lega spike, 2022 energy-war widening) so country-specific curves materially improve rating-spread precision.
- **Status:** **CLOSED** Week 10 Sprint H 2026-04-22 — shipped via TE cascade (`TE_YIELD_CURVE_SYMBOLS["IT"]` extension with 12-tenor BTP family `GBTPGR1M:IND` … `GBTPGR30Y:IND`). Live canary 2024-12-30 fit: RMSE 5.23 bps, confidence 1.0, 12 tenors persisted. Commit `1857196` wires IT into `T1_CURVES_COUNTRIES` + dispatcher. The **BdI direct-feed path remains BLOCKED** per Sprint G empirical probe (national-CB entry preserved below as historical record + unblock path).
- **Sprint H correction:** Sprint G brief §2 probe list omitted TE generic-indicator API + `/markets/historical` endpoint — a material scope error captured in ADR-0009 v2 (Sprint H addendum). TE was already serving GB/JP/CA since CAL-138 via the same mechanics; the omission is corrected in Sprint H + formalised as "TE Path 1 canonical" in ADR-0009 v2.
- **Sprint G BdI national-CB path (historical record — remains BLOCKED):**
- **Status (national-CB direct):** **BLOCKED** Week 10 Sprint G pre-flight 2026-04-22 — all five brief §2 probed data paths (ECB legacy SDMX ``sdw-wsrest`` / BdI Infostat REST / MEF Tesoro / ECB SDW ``FM`` + ``IRS`` IT override / FRED OECD mirror) failed to provide a ≥ 6-tenor daily IT sovereign yield curve. HALT trigger 0 fired; narrow-scope ship per Sprint D FR-BDF precedent. Sprint G twinned with ``CAL-CURVES-ES-BDE`` — the parallel ES probe reached HALT-0 on a *different* sub-case (HTTP 200 + non-daily; see entry below).
- **Pre-flight discipline (executed Sprint G 2026-04-22):** ADR-0009 probe discipline applied. Findings frozen in ``src/sonar/connectors/banca_ditalia.py`` module docstring + ``BDI_PROBE_FINDINGS`` tuple. Retrospective at ``docs/planning/retrospectives/week10-sprint-curves-it-es-report.md``.
- **Empirical probe matrix (Sprint G Commit 1, 2026-04-22):**
  | Source | URL / Probe | Result | Verdict |
  |---|---|---|---|
  | ECB legacy SDMX REST | ``https://sdw-wsrest.ecb.europa.eu/service/data/BDS`` | HTTP 000 (connection timeout) | **DEAD** — host decommissioned in 2023 SDW→Data Portal migration; BDS dataflow not re-published on ``data-api.ecb.europa.eu`` |
  | BdI Infostat REST | ``https://infostat.bancaditalia.it/`` (HTTP 200 SPA); ``a2a.infostat.bancaditalia.it`` / ``sdmx.bancaditalia.it`` / ``bip.bancaditalia.it`` | **NXDOMAIN** on all application subdomains | **UNREACHABLE** — Infostat is browser-only; no public REST surface |
  | MEF / Tesoro Italiano | ``https://www.dt.mef.gov.it/it/debito_pubblico/titoli_di_stato/``; ``https://www.mef.gov.it/opendata/`` | HTML only / HTTP 404 | **INSUFFICIENT** — PDF/XLS press-release attachments, no pipeline surface |
  | ECB SDW ``FM`` IT override | ``data-api.ecb.europa.eu/service/data/FM?filter=REF_AREA:IT`` | HTTP 200 but returns EA-aggregate MP rates (-0.25/2.00 MRO), no IT yields | **INSUFFICIENT** — Sprint A finding re-confirmed |
  | ECB SDW ``IRS`` IT override | ``IRS?filter=REF_AREA:IT`` | HTTP 200; single MATURITY_CAT='CI' (EMU criterion 10Y monthly) | **INSUFFICIENT** — below MIN_OBSERVATIONS=6; monthly |
  | FRED OECD mirror | ``IRLTLT01ITM156N`` | HTTP 200, 420 monthly obs | **INSUFFICIENT** — 10Y only, monthly |
- **Priority:** DEFERRED — parked pending either (a) Banca d'Italia publishing a public SDMX / REST surface for BTP yields (no known roadmap), (b) SONAR provisioning a licensed feed (Bloomberg BVAL / Refinitiv / FactSet), or (c) a browser-automation shim driving the Infostat SPA to extract CSV downloads.
- **Current behavior (post Sprint H):** ``daily_curves --country IT`` persists a 12-tenor Svensson fit via TE; ``--all-t1`` includes IT (8-country tuple). The scaffolded ``BancaDItaliaConnector`` is retained as documentation-first + future direct-CB placeholder — **not** wired into the dispatcher (TE branch handles IT directly via `TE_YIELD_CURVE_SYMBOLS` lookup). Unblock-for-direct-CB conditions (below) unchanged from Sprint G — a future switch to BdI direct would require one of them.
- **Impact resolution:** IT ERP/CRP per-country now reads country-specific BTP term structure; rating-spread signal captures the Italy-specific credit premium that drives most of the peripheral spread variance. Overlay cascade 07:30 WEST gains functional IT branch starting 2026-04-23 post-merge.
- **Estimate to switch to direct BdI feed (future):** 4-6h CC *after* any of the three national-CB unblock conditions materialise. Motivation would be redundancy (TE vendor lock-in mitigation) or richer per-ISIN data (TE publishes benchmark curves only; BdI Infostat would expose full secondary-market microstructure).
- **Related:** ``CAL-CURVES-EA-PERIPHERY`` (superseded grandparent); ``CAL-CURVES-FR-BDF`` (BLOCKED pilot — Sprint D template); ``CAL-CURVES-ES-BDE`` (Sprint G twin — also CLOSED via TE cascade Sprint H); ``CAL-CURVES-FR-TE-PROBE`` (Sprint H opened; FR may follow same TE Path 1 resolution); ``ADR-0009`` v2 (TE Path 1 canonical amendment Sprint H); ``CAL-CURVES-IT-ES-LINKER`` (Sprint H opened; linker BTP€i separate from this nominal closure); ``CAL-CURVES-T1-LINKER`` IT linker portion migrates to `CAL-CURVES-IT-ES-LINKER`.

### CAL-CURVES-ES-BDE — ES sovereign yield curve via Banco de España — **CLOSED (via TE cascade, Sprint H 2026-04-22)**

- **Priority:** MEDIUM — ES spread dynamics mirror IT on a smaller scale; country-specific curve would improve rating-spread precision for peripheral EU exposure.
- **Status:** **CLOSED** Week 10 Sprint H 2026-04-22 — shipped via TE cascade (`TE_YIELD_CURVE_SYMBOLS["ES"]` extension with 9-tenor SPGB family `GSPG3M:IND` … `GSPG30YR:IND`). Live canary 2024-12-30 fit: RMSE 4.41 bps, confidence 1.0, 9 tenors persisted (sits at exact MIN_OBSERVATIONS_FOR_SVENSSON=9 boundary). Commit `1857196` wires ES into `T1_CURVES_COUNTRIES` + dispatcher. The **BdE BIE direct-feed path remains BLOCKED** per Sprint G empirical probe (monthly cadence incompatible with daily pipeline).
- **Sprint H correction:** same omission pattern as IT — Sprint G brief §2 probe list skipped TE. Sprint H amendment formalises "TE Path 1 canonical" in ADR-0009 v2.
- **Sprint G BdE national-CB path (historical record — remains BLOCKED on frequency mismatch):**
- **Status (national-CB direct):** **BLOCKED** Week 10 Sprint G pre-flight 2026-04-22 — ES lands on a **softer** HALT-0 sub-case than IT / FR: the Banco de España BIE REST API (``https://app.bde.es/bierest/resources/srdatosapp/``) is **reachable** (HTTP 200) and returns Spanish sovereign yield series via ``listaSeries?series=<code>&rango=<period>``, but every Spanish sovereign yield series exposed through it publishes at **monthly** frequency (CSV suffix ``.M`` + declared ``FRECUENCIA=MENSUAL``; confirmed via REST for ``D_1NBBO320`` ES long-term Rendimiento de la Deuda Pública = ``codFrecuencia='M'``, 31 obs in 30-month window). This is below the daily pipeline cadence the ``daily_curves`` pipeline requires. ADR-0009 decision matrix: "HTTP 200 + non-daily" → scaffold per Sprint D pattern (new sub-case captured in ADR extension).
- **Pre-flight discipline (executed Sprint G 2026-04-22):** ADR-0009 probe discipline applied. Findings frozen in ``src/sonar/connectors/banco_espana.py`` module docstring + ``BDE_PROBE_FINDINGS`` tuple.
- **Empirical probe matrix (Sprint G Commit 1, 2026-04-22):**
  | Source | URL / Probe | Result | Verdict |
  |---|---|---|---|
  | BDEstad portal | ``https://www.bde.es/webbde/es/estadis/infoest/`` | HTTP 301 → ``/wbe/es/estadisticas/`` (legacy path decommissioned) | **MIGRATED** — old path refs in Sprint A backlog stale |
  | BdE BIE REST API | ``https://app.bde.es/bierest/resources/srdatosapp/listaSeries?series=<code>&rango=<period>`` | HTTP 200 JSON; ``D_1NBBO320`` returns 31 monthly obs (ES long-term sovereign yield) | **LIVE but MONTHLY** — below daily pipeline cadence. 11-tenor ES sovereign yield coverage catalogued via BIE statistical tables (BE_22_6 Letras 6 buckets 3M-12M + BE_22_7 Bonos 5 tenors 3Y-30Y), all monthly |
  | Tesoro Público | ``https://www.tesoro.es/`` | HTTP 000 (TLS handshake fails in ~116 ms) | **UNREACHABLE** — effectively blocked from VPS data plane |
  | ECB SDW ``FM`` ES override | ``FM?filter=REF_AREA:ES`` | HTTP 200 but returns EA-aggregate MP rates (-0.25/2.00), no ES yields | **INSUFFICIENT** — Sprint A finding re-confirmed |
  | FRED OECD mirror | ``IRLTLT01ESM156N`` | HTTP 200, 555 monthly obs | **INSUFFICIENT** — 10Y only, monthly |
- **Priority:** DEFERRED — parked pending either (a) BdE publishing daily Bono secondary-market yields through BIE REST (no known roadmap), (b) ``daily_curves`` evolving to accept a monthly-resolution connector family with an explicit forward-fill + flag policy (scope expansion beyond Sprint G), (c) SONAR launching a parallel ``monthly_curves`` pipeline (Phase 2+ architecture), or (d) licensed-feed provisioning for ES sovereign yields.
- **Current behavior (post Sprint H):** ``daily_curves --country ES`` persists a 9-tenor Svensson fit via TE; ``--all-t1`` includes ES (8-country tuple). The scaffolded ``BancoEspanaConnector`` is retained as documentation-first + future direct-CB placeholder — **not** wired into the dispatcher. Unlike IT's BdI scaffold (all-paths-dead sub-case), the BdE scaffold's docstring preserves the concrete series-code shape (``D_`` prefix; BE_22 statistical-table chapter) for future swap-in if BdE begins publishing daily Bono yields or if the pipeline gains monthly-cadence support.
- **Impact resolution:** ES overlays now read country-specific SPGB term structure; linker BEI derivation improves once SPGB secondary yields flow through `daily_overlays`. Peripheral spread signal now covers IT + ES (FR + PT + NL remain in proxy-fallback).
- **Estimate to switch to direct BdE feed (future):** 4-6h CC under (a) if BdE publishes daily Bono yields; 6-8h CC under (b) if `daily_curves` gains a monthly-cadence tier. Post-Sprint-H TE coverage reduces the urgency (9-tenor daily fit production-ready); the switch would be motivated by redundancy or richer data (per-ISIN secondary-market microstructure unavailable via TE benchmark-only publication).
- **Related:** ``CAL-CURVES-EA-PERIPHERY`` (superseded grandparent); ``CAL-CURVES-FR-BDF`` (BLOCKED pilot — Sprint D template); ``CAL-CURVES-IT-BDI`` (Sprint G twin — also CLOSED via TE cascade Sprint H); ``CAL-CURVES-FR-TE-PROBE`` (Sprint H opened); ``ADR-0009`` v2 (TE Path 1 canonical amendment Sprint H; pattern library entry with "non-daily" sub-case for historical record); ``CAL-CURVES-IT-ES-LINKER`` (Sprint H opened — linker Bonos-i separate from this nominal closure); ``CAL-CURVES-T1-LINKER`` ES linker portion migrates to `CAL-CURVES-IT-ES-LINKER`.

### CAL-CURVES-FR-TE-PROBE — FR sovereign yield curve re-probe via TE per-tenor cascade — **CLOSED (via TE cascade, Sprint I 2026-04-22)**

- **Priority:** MEDIUM — FR is the fourth-largest EA economy and the widest EA-core spread gap; country-specific curve replaces EA-aggregate-proxy for FR ERP/CRP overlays.
- **Status:** **CLOSED** Week 10 Sprint I 2026-04-22 — shipped via TE cascade (`TE_YIELD_CURVE_SYMBOLS["FR"]` extension with 10-tenor OAT family `GFRN1M:IND` … `GFRN30Y:IND`; missing 3Y + 15Y empirically). Live canary 2024-12-30 fit: RMSE **2.005 bps**, confidence **1.0**, 10 tenors persisted (cleaner than IT 5.23 / ES 4.41 via the same cascade). Commits ``db8fe82`` C1 (probe matrix) + ``93564bc`` C2 (TE dict extension) + ``8e2f6c4`` C3 (pipeline tuple 8→9 + dispatcher) + C4 (this commit — addendum + cassettes + canary + retro).
- **Sprint I empirical probe (Commit 1, 2026-04-22):** per-tenor sweep across `GFRN{1M, 3M, 6M, 1Y, 1YR, 2Y, 2YR, 3Y, 4Y, 5Y, 5YR, 7Y, 7YR, 10, 10Y, 10YR, 15Y, 20Y, 20YR, 25Y, 30Y, 30YR, 50Y}` and bare-no-suffix variants. Result: **10 daily tenors confirmed** (1M, 3M, 6M, 1Y, 2Y, 5Y, 7Y, 10Y, 20Y, 30Y), missing 3Y + 15Y across every tested spelling. Frequency verified daily over Nov 2024 (n=21/21 trading days for both 20Y + 30Y); historical depth verified to 2020-01-31 daily. FR's quirk: bare `Y` suffix uniformly on 1Y+ tenors, no suffix on 10Y (matches IT `GBTPGR10` + GB `GUKG10` + JP `GJGB10` precedent — distinct from ES uniform `YR`).
- **Sprint D HALT-0 reframe:** the Sprint D entry "TE `GFRN10` 10Y-only, below MIN_OBSERVATIONS=6" was a single-symbol-probe artifact inherited uncritically from CAL-138 (which catalogued FR as 10Y-only because the CAL-138 probe assumed Bloomberg-family uniformity per country and did not sweep per-tenor). Sprint H's amendment v2 mandated the sweep; Sprint I executed and empirically demonstrated 10-tenor coverage. The BdF / AFT / FRED legs of the Sprint D matrix remain accurate — only the TE leg was incomplete.
- **Outcome:** SUCCESS. FR shipped via Path 1 (TE cascade), 7th application of the pattern (CAL-138 GB/JP/CA + Sprint H IT/ES + Sprint I FR). Pattern library v2 reinforced, no textual change to ADR-0009 v2.
- **Closure refs:** retrospective ``docs/planning/retrospectives/week10-sprint-curves-fr-te-probe-report.md`` (v3 format); ADR addendum v2.1 in ``docs/adr/ADR-0009-national-cb-connectors-ea-periphery.md`` (Sprint I section).
- **Related:** ``CAL-CURVES-FR-BDF`` (SHARPENED Sprint I — direct-CB national-feed path remains BLOCKED for redundancy / per-ISIN microstructure upgrade; daily pipeline no longer depends); ``CAL-CURVES-IT-BDI`` + ``CAL-CURVES-ES-BDE`` (Sprint H precedent — same correction applied to FR); ``ADR-0009`` v2.1 (Sprint I addendum — empirical reinforcement of TE Path 1 canonical); ``CAL-138 retrospective`` (original single-tenor finding for FR — corrected by this Sprint I sweep).

### CAL-CURVES-IT-ES-LINKER — Inflation-indexed yield curves for IT + ES

- **Priority:** LOW-MEDIUM — linker coverage for BTP€i (Italian) + Bonos indexados (Spanish) would replace the current `DERIVED` BEI fallback path with an authoritative real-rate signal. ERP cost-of-capital uses nominal + expected-inflation primarily; BEI adds a direct market-inferred real-rate check useful for cycle-phase discrimination.
- **Status:** OPEN — opened Week 10 Sprint H 2026-04-22. Out-of-scope for Sprint H per brief §1 (nominal-only ship) because TE `/markets/historical` does not expose per-country inflation-indexed bond yields (CAL-138 confirmed the same gap for GB gilts-IL / JP JGBi / CA RRB under `CAL-CURVES-T1-LINKER`).
- **Trigger:** Sprint H IT + ES nominal ship revealed the remaining linker gap as a discrete follow-up; splitting the linker scope off per-country-pair keeps the unblock-path matrix tractable.
- **Data path (candidate):**
  - **IT BTP€i:** Banca d'Italia / MEF publish primary-market auction results for BTP€i (inflation-indexed BTP) but no daily secondary-market curve in an open feed. Bloomberg publishes `ITBI*` family but TE does not mirror. Candidate: Eurostat Harmonised CPI-linker dataflow (indirect), or licensed Bloomberg feed (direct).
  - **ES Bonos indexados:** Tesoro Público publishes primary-auction results for Bonos del Estado indexados (reference index HICP ex-tobacco EU); no daily secondary curve in an open feed. Same candidates as IT.
- **Required work:** Sprint H-style per-tenor probe for both `ITBI*` / `ESBI*` (or Bloomberg-equivalent symbols) on TE; if confirmed, extend `fetch_yield_curve_linker` stub to return real data for IT + ES (currently returns empty dict for all TE-served countries). If TE gap persists, defer to Phase 2.5 licensed-feed scope same as `CAL-CURVES-T1-LINKER`.
- **Impact if unresolved:** IT + ES real-curve path continues on `DERIVED` BEI fallback (nominal - expected_inflation); loss of direct market-inferred real yield signal. Cycle-phase discrimination retains the approximation but not the precision of a direct BTP€i / Bonos-i NSS fit.
- **Estimate:** 1h CC probe + 2h CC ship if Path 1 succeeds; 0h action if TE gap persists (rollup into Phase 2.5 licensed-feed scope).
- **Related:** ``CAL-CURVES-IT-BDI`` + ``CAL-CURVES-ES-BDE`` (nominal closures Sprint H; this CAL covers the linker complement); ``CAL-CURVES-T1-LINKER`` (parent for GB / JP / CA linker coverage; IT + ES split off into this CAL to keep scope tractable); ``CAL-CURVES-FR-TE-PROBE`` (adjacent Sprint H open item — French OAT€i would be a natural third country for any linker probe sweep).

### CAL-CURVES-PT-BPSTAT — PT sovereign yield curve via Banco de Portugal BPstat — **CLOSED (via TE cascade, Sprint M 2026-04-23)**

- **Priority:** — (closed).
- **Outcome:** CLOSED pre-open. Sprint M 2026-04-23 per-tenor TE Path 1 probe (ADR-0009 v2 canonical) on the ``GSPT`` family returned 10 daily tenors ≥ 586 observations each (3M / 6M / 1Y / 2Y / 3Y / 5Y / 7Y / 10Y / 20Y / 30Y; 1M + 15Y are TE-coverage structural gaps confirmed via ``/search/portugal%20government%20bond`` cross-validation). Live canary 2026-04-21/22/23 returned ``rmse_bps ∈ [7.24, 7.53]`` with confidence=1.0 across all 3 days. PT therefore ships via TE Path 1 cascade mirroring the IT/ES Sprint H + FR Sprint I pattern — no BPstat native-CB integration was required. The ADR-0009 v2 rule "probe TE Path 1 first; escalate to Path 2/3 only on empirical Path 1 failure" held cleanly for its 4th consecutive successor sprint. PT mixed-suffix quirk (YR on 2Y + 10Y, bare Y on 1Y / 3Y / 5Y / 7Y / 20Y / 30Y, M on sub-year) catalogued in ``te.py`` block docstring for future reference.
- **Current behavior:** ``daily_curves --country PT`` and ``--all-t1`` persist a 10-tenor Svensson fit via TE. Overlay cascade gains functional PT branch starting 2026-04-24 post-merge.
- **Direct-CB future path (non-blocking):** A native BPstat connector remains a future upgrade path (tracks IGCP long-end granularity beyond TE's 30Y ceiling + potential OTRV indexed coverage) but is not scheduled — TE Path 1 is sufficient for Phase 1 daily-pipeline needs. If pursued, pattern precedent is now ``BancaDItalia`` / ``BancoEspana`` scaffold (placeholder preserved post-Sprint-H) rather than BdF's blocked OpenDatasoft trajectory.
- **Closure commits:** Sprint M (`dce9287` probe doc, `612cf7f` te.py, `94d68ec` daily_curves, `a8e9987` tests, `2909ce6` downstream drift-guards, `<retro>` ADR-0009 addendum + retro).
- **Related:** ``CAL-CURVES-EA-PERIPHERY`` (superseded grandparent); ``CAL-CURVES-IT-BDI`` + ``CAL-CURVES-ES-BDE`` (Sprint H twin closures — same TE cascade pattern); ``CAL-CURVES-FR-TE-PROBE`` (Sprint I analog); ``CAL-CURVES-NL-DNB-PROBE`` (Sprint M twin — **OPEN** as first Path 1 non-inversion); ``ADR-0009`` v2.2 (Sprint M addendum — Shape S1 codification); ``CAL-CURVES-T1-LINKER`` PT portion = permanent ``LINKER_UNAVAILABLE`` (no OTRV coverage in open form).

### CAL-CURVES-NL-DNB-PROBE — NL sovereign yield curve re-probe via De Nederlandsche Bank native cascade — **OPEN (Week 11 Path 2; first ADR-0009 v2 non-inversion)**

- **Priority:** LOW-MEDIUM — NL trades close to DE (AAA cluster) so country-specific curve gain vs DE-Bund proxy is smaller; still needed for per-country ERP cleanliness. First **non-inversion** observed in the ADR-0009 v2 ledger (see Sprint M retro §5.1 for the load-bearing empirical significance).
- **Supersedes:** ``CAL-CURVES-NL-DNB`` (previously framed around BPstat-style direct-CB probe; Sprint M's TE Path 1 failure reshapes it into an empirically-motivated Path 2 probe). Renamed from `-DNB` to `-DNB-PROBE` to signal the Path 2 cascade entry.
- **Trigger:** Sprint M 2026-04-23 per-tenor TE Path 1 probe returned only 4/12 tenors (3M / 6M / 2Y / 10Y) against the ``GNTH`` family. 4 < ``MIN_OBSERVATIONS_FOR_SVENSSON = 6`` → HALT-0. First TE Path 1 HALT observed across 5 successor sprints (IT / ES / FR / PT all PASS); NL is the first Shape S2 country (point-estimates only, not Svensson-rich) in the ADR-0009 pattern library v2.2.
- **Empirical probe matrix (Sprint M 2026-04-23):**
  - PASS: ``GNTH3M:IND`` (n=597), ``GNTH6M:IND`` (n=595), ``GNTH2YR:GOV`` (n=598 — note the unique ``:GOV`` suffix quirk, only one in the entire TE T1 registry), ``GNTH10YR:IND`` (n=600).
  - FAIL (all variants empty): 1M / 1Y / 3Y / 5Y / 7Y / 15Y / 20Y / 30Y. Verified via both per-tenor ``/markets/historical`` sweep and ``/search/netherlands%20government%20bond`` cross-validation — structural TE-coverage gaps, not probe-naming misses.
- **Current behavior:** ``daily_curves --country NL`` raises ``InsufficientDataError`` citing ``CAL-CURVES-NL-DNB-PROBE``; ``--all-t1`` skips NL.
- **Candidate Path 2 data paths (re-probe required — expect DNB sub-case split):**
  1. **DNB Statistics portal Statline (statline.dnb.nl)** — SDMX / OpenDatasoft cube; expected to publish DSL (Dutch State Loan) daily yields; tenor spectrum unknown pre-probe. Precedent risk: BdF (Sprint D) migrated to OpenDatasoft and surfaces only monthly archive data — same platform risk applies to DNB as Sprint D's addendum predicted.
  2. **DSTA (Dutch State Treasury Agency, dsta.nl)** — sovereign issuer with tenor-specific benchmark quotes. No open API; web-scrape fallback if Statline fails or proves monthly-only.
  3. **ECB SDW IRS dataflow** — already probed at Sprint A; returns only 10Y for NL (single tenor). Not a solution but documented as floor.
- **Required work:** ADR-0009 v2 Path 2 brief + scaffold + empirical probe. If Statline ships daily 6+ tenors: standard cascade ship mirroring Bundesbank (AAA native precedent). If Statline monthly-only: scaffold + defer to Phase 2.5 (mirror ``CAL-CURVES-FR-BDF`` BLOCKED pattern). If DSTA scrape-path opens (HTML / XLSX / CSV): bespoke connector + daily cadence.
- **Impact if unresolved:** NL overlays stay on EA-aggregate proxy (lowest-cost gap of the five EA periphery members since NL ≈ DE in spread terms — rarely +50 bps over Bund even in 2011/2020 stress).
- **Estimate:** 3-5h CC (probe + scaffold + ship **or** probe + scaffold + BLOCKED mark).
- **Related:** ``CAL-CURVES-PT-BPSTAT`` (Sprint M twin — CLOSED via TE Path 1; NL diverges); ``CAL-CURVES-FR-BDF`` (BLOCKED pilot template — near-duplicate OpenDatasoft platform risk); ``ADR-0009`` v2.2 (Sprint M addendum — Shape S2 codification + first non-inversion); ``CAL-CURVES-EA-PERIPHERY`` (superseded grandparent); ``CAL-CURVES-T1-LINKER`` NL portion = permanent ``LINKER_UNAVAILABLE``.

### CAL-CURVES-T1-SPARSE — Non-EA T1 full yield curves (AU/NZ/CH/SE/NO/DK) — **SUPERSEDED (Sprint T 2026-04-23)**

- **Priority:** SUPERSEDED — umbrella CAL replaced by 6 per-country CALs (one per sparse T1 country) post Sprint T empirical decomposition.
- **Supersession:** Sprint T 2026-04-23 re-probed all 6 countries under ADR-0009 v2 discipline (TE Path 1 mandatory + v2.2 S1/S2 classifier). Outcome: 1 S1 PASS (AU, 8 tenors via TE ``GACGB`` family — **CAL-CURVES-AU-PATH-2** closed pre-open) + 5 S2 HALT-0 (NZ/CH/SE/NO/DK, all ≤3 tenors). The 5 HALT-0 countries move to dedicated per-country CALs (**CAL-CURVES-NZ-PATH-2**, **CAL-CURVES-CH-PATH-2**, **CAL-CURVES-SE-PATH-2**, **CAL-CURVES-NO-PATH-2**, **CAL-CURVES-DK-PATH-2** — see below), each scoped to its Path 2 national-CB / aggregator candidate independently.
- **Related:** ``CAL-CURVES-AU-PATH-2`` (CLOSED Sprint T pre-open); ``CAL-CURVES-{NZ,CH,SE,NO,DK}-PATH-2`` (OPEN Week 11+ per-country Path 2 probes); ``ADR-0009`` v2.2 (Sprint T addendum — first large-scale S1/S2 classifier application).

### CAL-CURVES-AU-PATH-2 — AU sovereign yield curve via TE Path 1 cascade — **CLOSED (pre-open via TE cascade, Sprint T 2026-04-23)**

- **Priority:** CLOSED — AU ships via TE Path 1 per ADR-0009 v2.2 S1 PASS classification (mirrors PT-BPSTAT Sprint M precedent — CAL opens + closes in same sprint).
- **Trigger:** Sprint T 2026-04-23 per-tenor TE Path 1 probe returned 8/12 tenors (1Y, 2Y, 3Y, 5Y, 7Y, 10Y, 20Y, 30Y via ``GACGB`` family; 1M/3M/6M/15Y structural gaps). 8 ≥ ``MIN_OBSERVATIONS_FOR_SVENSSON=6`` → S1 PASS, first **sparse-T1** S1 inversion in the ADR-0009 v2 ledger.
- **Empirical probe matrix (Sprint T 2026-04-23):**
  - PASS: ``GACGB1Y:IND`` (n=616), ``GACGB2Y:IND`` (n=611), ``GACGB3Y:IND`` (n=611), ``GACGB5Y:IND`` (n=614), ``GACGB7Y:IND`` (n=612), ``GACGB10:IND`` (n=608 — bare 10Y quirk, same as IT/GB/JP/FR), ``GACGB20Y:IND`` (n=624), ``GACGB30Y:IND`` (n=623). All latest 2026-04-22.
  - FAIL: 1M / 3M / 6M / 15Y — structural TE-coverage gaps (confirmed via ``/search/australia%20government%20bond`` exhaustive list).
- **Resolution:** ``src/sonar/connectors/te.py`` ``TE_YIELD_CURVE_SYMBOLS["AU"]`` + ``TE_10Y_SYMBOLS["AU"] = "GACGB10:IND"`` shipped Sprint T; ``T1_CURVES_COUNTRIES`` extended 10 → 11; Apr 21/22/23 backfilled (rmse_bps 3.08 / 3.18 / 3.63, confidence 0.75 uniform).
- **Related:** ``CAL-CURVES-PT-BPSTAT`` (Sprint M precedent — same pre-open CAL closure pattern); ``ADR-0009`` v2.2 (Sprint T addendum — Shape S1 validation for first sparse-T1); ``CAL-CURVES-T1-LINKER`` AU portion = permanent ``LINKER_UNAVAILABLE`` (no open-form ACGBi retail coverage).

### CAL-CURVES-NZ-PATH-2 — NZ sovereign yield curve via RBNZ Path 2 cascade — **OPEN (Week 11 Path 2; Sprint T non-inversion #2 — Sprint T-Retry 2026-04-24 re-confirmed)**

- **Priority:** LOW-MEDIUM — NZD is a small sovereign market but T1 per ADR-0010; needed for per-country ERP cleanliness.
- **Trigger:** Sprint T 2026-04-23 per-tenor TE Path 1 probe returned only 3 tenors (``GNZGB1:IND`` n=531 1Y, ``GNZGB2:GOV`` n=587 2Y — note ``:GOV`` suffix quirk analogous to NL's ``GNTH2YR:GOV``, ``GNZGB10:IND`` n=599 10Y). 3 < ``MIN_OBSERVATIONS_FOR_SVENSSON=6`` → S2 HALT-0. **Discovery**: ``GNZGB1:IND`` returned live-daily via per-tenor probe but was **not listed** in ``/search/new-zealand%20government%20bond`` — pattern-library signal that ``/search`` is high-recall but not exhaustive (ADR-0009 v2.3 amendment candidate §9.1).
- **Sprint T-Retry 2026-04-24 re-confirmation:** Multi-prefix Path 1 probe (prefixes `GNZGB / NZGB / GNZD / NZDEP / NZTB` × 20 tenors × 3 suffixes) + `/markets/bond?Country="New Zealand"` authoritative listing cross-validation surfaced **2 additional short-tenor symbols** (``GNZGB3M:IND`` n=581 + ``GNZGB6M:IND`` n=581) absent from any `/search` query variant. **Post-Retry aggregate: 5 tenors** (3M, 6M, 1Y, 2Y, 10Y) — still < 6 threshold and **structural mid-tenor gap** (3Y / 5Y / 7Y entirely absent in TE regardless of probe depth) blocks Svensson fit. S2 HALT-0 **re-confirmed**; Path 2 RBNZ cascade empirically justified. See `docs/backlog/probe-results/sprint-t-retry-multi-prefix-probe.md` §3.1 for raw matrix. ADR-0009 v2.3 §7.5.2 codifies `/markets/bond` authoritative endpoint discipline validated on NZ.
- **Current behavior:** ``daily_curves --country NZ`` raises ``InsufficientDataError`` citing ``CAL-CURVES-NZ-PATH-2``; ``--all-t1`` skips NZ.
- **Candidate Path 2 data paths (re-probe required):**
  1. **RBNZ statistics portal (rbnz.govt.nz/statistics)** — table B2 (government bond yields) is the primary candidate; tenor spectrum unknown pre-probe. Expected publication is monthly archive but daily aggregation may be available via API.
  2. **NZDMO (New Zealand Debt Management Office)** — issuer-side tenor-specific benchmark quotes; no known open API.
- **Estimate:** 2-3h CC probe + scaffold.
- **Related:** ``CAL-CURVES-NL-DNB-PROBE`` (same Shape S2 pattern, Sprint M precedent); ``ADR-0009`` v2.2 (Sprint T addendum).

### CAL-CURVES-CH-PATH-2 — CH sovereign yield curve via SNB Path 2 cascade — **OPEN (Week 11 Path 2; Sprint T non-inversion #3 — Sprint T-Retry 2026-04-24 + Sprint 5B 2026-04-26 re-confirmed × 3)**

- **Priority:** LOW-MEDIUM — CHF haven-currency status makes CH curve valuable for cross-asset risk but TE coverage refutes "sovereign-market-size ⇒ TE coverage" prior.
- **Trigger:** Sprint T 2026-04-23 per-tenor TE Path 1 probe returned only 2 tenors (``GSWISS2:GOV`` n=584 2Y, ``GSWISS10:IND`` n=583 10Y). 2 < ``MIN_OBSERVATIONS_FOR_SVENSSON=6`` → S2 HALT-0. Hypothesis "CHF haven bid drives TE depth" refuted.
- **Sprint T-Retry 2026-04-24 re-confirmation:** Multi-prefix Path 1 probe (prefixes `GSWISS / GCHF / GSWI / SWG / CHGB / SWISSGB` × 31 tenors × 3 suffixes) + `/markets/bond?Country="Switzerland"` authoritative listing — **zero delta**. Only `GSWISS2:GOV` + `GSWISS10:IND` exist in TE regardless of probe depth. `GCHF` ISO-currency-code prefix candidate empirically falsified (per ADR-0009 v2.3 §7.5.3). S2 HALT-0 **re-confirmed**; Path 2 SNB cascade empirically justified. See `docs/backlog/probe-results/sprint-t-retry-multi-prefix-probe.md` §3.2.
- **Sprint 5B 2026-04-26 re-confirmation (3rd):** `/markets/bond` filtered + per-tenor `/markets/historical` daily-live verification — symbol set unchanged (2 tenors), obs counts +2 vs. T-Retry (n=586/585 → ~3 trading days appended), latest 24/04/2026 (≤7 day staleness window). Zero delta vs. v2.3 baseline. State frozen across 3 consecutive probes in 3-day window. Liberal HALT cap (≥3 cohort-wide) triggered by Sprint 5B alone (4 países HALT-0); ADR-0009 §5B addendum stamps reinforcement (no v3 amendment — v2.3 already canonical). See `docs/backlog/probe-results/sprint-5b-europe-sparse-confirmation-probe.md` §4.
- **Current behavior:** ``daily_curves --country CH`` raises ``InsufficientDataError`` citing ``CAL-CURVES-CH-PATH-2``; ``--all-t1`` skips CH.
- **Candidate Path 2 data paths (re-probe required):**
  1. **SNB data portal (data.snb.ch)** — primary candidate; SNB publishes sight-deposit rate via the already-wired ``SnbConnector`` (Sprint V-CH monetary), so auth + parsing infra is partially reusable. Yield-curve spectrum unknown pre-probe — need to explore the fixed-income data cube.
  2. **Swiss Federal Treasury (efv.admin.ch)** — issuer side, tenor-specific.
  3. **BIS sovereign yields** — cross-country fallback, lower cadence.
- **Negative-rate-era handling:** CH experienced sustained negative yields 2014-2022 (SNB deposit rate trough -0.75%). β0 lower bound widening + ``CH_YIELD_NEGATIVE_ERA_DATA`` flag per Sprint V/W/Y monetary precedent.
- **Estimate:** 2-3h CC probe + scaffold.
- **Related:** ``CAL-CURVES-NL-DNB-PROBE`` / ``CAL-CURVES-NZ-PATH-2`` (same Shape S2 pattern); Sprint V-CH ``SnbConnector`` (reusable auth infra).

### CAL-CURVES-SE-PATH-2 — SE sovereign yield curve via Riksbank Path 2 cascade — **OPEN (Week 11 Path 2; Sprint T non-inversion #4 — Sprint T-Retry 2026-04-24 + Sprint 5B 2026-04-26 re-confirmed × 3)**

- **Priority:** LOW-MEDIUM — SEK Nordic market; per-country cost-of-capital cleanliness.
- **Trigger:** Sprint T 2026-04-23 per-tenor TE Path 1 probe returned only 2 tenors (``GSGB2YR:GOV`` n=580 2Y, ``GSGB10YR:GOV`` n=589 10Y, both uniformly ``:GOV`` suffix). 2 < ``MIN_OBSERVATIONS_FOR_SVENSSON=6`` → S2 HALT-0.
- **Sprint T-Retry 2026-04-24 re-confirmation:** Multi-prefix Path 1 probe (prefixes `GSGB / GSEK / GSWE / SWDGB / SEGB` × 31 tenors × 3 suffixes) + `/markets/bond?Country="Sweden"` authoritative listing — **zero delta**. Only `GSGB2YR:GOV` + `GSGB10YR:GOV` exist in TE. `GSEK` ISO-currency-code prefix candidate empirically falsified (per ADR-0009 v2.3 §7.5.3). S2 HALT-0 **re-confirmed**; Path 2 Riksbank cascade empirically justified. See `docs/backlog/probe-results/sprint-t-retry-multi-prefix-probe.md` §3.3.
- **Sprint 5B 2026-04-26 re-confirmation (3rd):** `/markets/bond` filtered + per-tenor `/markets/historical` daily-live verification — symbol set unchanged (2 tenors), obs counts +2 vs. T-Retry (n=582/591 → ~3 trading days appended), latest 24/04/2026 (≤7 day staleness window). Zero delta vs. v2.3 baseline. State frozen across 3 consecutive probes in 3-day window. Liberal HALT cap (≥3 cohort-wide) triggered by Sprint 5B alone; ADR-0009 §5B addendum stamps reinforcement (no v3 amendment). See `docs/backlog/probe-results/sprint-5b-europe-sparse-confirmation-probe.md` §4.
- **Current behavior:** ``daily_curves --country SE`` raises ``InsufficientDataError`` citing ``CAL-CURVES-SE-PATH-2``; ``--all-t1`` skips SE.
- **Candidate Path 2 data paths (re-probe required):**
  1. **Riksbank statistics portal (www.riksbank.se/en-gb/statistics/)** — primary; Riksbank publishes SGB benchmark rates daily. Auth / parsing infra partially reusable via Sprint W-SE ``RiksbankConnector``.
  2. **Swedish National Debt Office (riksgalden.se)** — issuer side.
- **Negative-rate-era handling:** SE experienced negative rates 2015-2019 (min SE repo -0.50%); β0 widening + flag per Sprint W precedent.
- **Estimate:** 2-3h CC probe + scaffold.
- **Related:** ``CAL-CURVES-NO-PATH-2`` / ``CAL-CURVES-DK-PATH-2`` (Nordic cohort); Sprint W-SE ``RiksbankConnector`` (reusable infra).

### CAL-CURVES-NO-PATH-2 — NO sovereign yield curve via Norges Bank Path 2 cascade — **OPEN (Week 11 Path 2; Sprint T non-inversion #5 — Sprint T-Retry 2026-04-24 + Sprint 5B 2026-04-26 re-confirmed × 3)**

- **Priority:** LOW — NOK sovereign wealth offset → smaller public debt market; lowest priority of sparse T1 Path 2 cohort.
- **Trigger:** Sprint T 2026-04-23 per-tenor TE Path 1 probe returned only 3 tenors (``NORYIELD6M:GOV`` n=585 6M, ``NORYIELD52W:GOV`` n=587 1Y-equivalent, ``GNOR10YR:GOV`` n=582 10Y). 3 < ``MIN_OBSERVATIONS_FOR_SVENSSON=6`` → S2 HALT-0. **Quirk**: NO spans two distinct prefix families simultaneously within TE — ``GNOR`` (Bloomberg-style, 10Y only) + ``NORYIELD`` (Norwegian convention, short-end). First T1 country to exhibit dual-prefix family coverage in TE — pattern-library signal (ADR-0009 v2.3 amendment candidate §9.2).
- **Sprint T-Retry 2026-04-24 re-confirmation:** Multi-prefix Path 1 probe (prefixes `GNOR / NORYIELD / NOGB / NOKGB` × 31 tenors × 3 suffixes) + `/markets/bond?Country="Norway"` authoritative listing — **zero delta**. Multi-prefix dual-family discipline (`GNOR` + `NORYIELD`) re-validated; only 3 tenors exist across both families in TE. Additional prefix candidates (`NOGB`, `NOKGB`) empirically falsified. S2 HALT-0 **re-confirmed**; Path 2 Norges Bank cascade empirically justified. Multi-prefix canonical rule now codified in ADR-0009 v2.3 §7.5.2. See `docs/backlog/probe-results/sprint-t-retry-multi-prefix-probe.md` §3.4.
- **Sprint 5B 2026-04-26 re-confirmation (3rd):** `/markets/bond` filtered + per-tenor `/markets/historical` daily-live verification — symbol set unchanged (3 tenors across `GNOR` + `NORYIELD` dual-prefix), obs counts +2 vs. T-Retry (n=584/589/587 → ~3 trading days appended), latest 24/04/2026 (≤7 day staleness window). Zero delta vs. v2.3 baseline. Dual-prefix multi-family v2.3 §7.5.2 re-validated. Liberal HALT cap (≥3 cohort-wide) triggered by Sprint 5B alone; ADR-0009 §5B addendum stamps reinforcement (no v3 amendment). See `docs/backlog/probe-results/sprint-5b-europe-sparse-confirmation-probe.md` §4.
- **Current behavior:** ``daily_curves --country NO`` raises ``InsufficientDataError`` citing ``CAL-CURVES-NO-PATH-2``; ``--all-t1`` skips NO.
- **Candidate Path 2 data paths (re-probe required):**
  1. **Norges Bank statistics (www.norges-bank.no/en/topics/Statistics/)** — primary; Norges Bank publishes NGB yields daily. Auth / parsing infra partially reusable via Sprint X-NO ``NorgesbankConnector``.
  2. **Oslo Børs fixed income** — issuer-side market depth.
- **Estimate:** 2-3h CC probe + scaffold.
- **Related:** ``CAL-CURVES-SE-PATH-2`` / ``CAL-CURVES-DK-PATH-2`` (Nordic cohort); Sprint X-NO ``NorgesbankConnector`` (reusable infra).

### CAL-CURVES-DK-PATH-2 — DK sovereign yield curve via Nationalbanken Path 2 cascade — **OPEN (Week 11 Path 2; Sprint T non-inversion #6 — Sprint T-Retry 2026-04-24 + Sprint 5B 2026-04-26 re-confirmed × 3)**

- **Priority:** LOW-MEDIUM — DKK EUR-peg → DK curve tracks Bund + small premium, but per-country ERP/cost-of-capital pipelines still need it.
- **Trigger:** Sprint T 2026-04-23 per-tenor TE Path 1 probe returned only 2 tenors (``GDGB2YR:GOV`` n=592 2Y, ``GDGB10YR:GOV`` n=598 10Y). 2 < ``MIN_OBSERVATIONS_FOR_SVENSSON=6`` → S2 HALT-0.
- **Sprint T-Retry 2026-04-24 re-confirmation:** Multi-prefix Path 1 probe (prefixes `GDGB / GDKK / GDEN / DKGB / DKKGB / DANGB` × 31 tenors × 3 suffixes) + `/markets/bond?Country="Denmark"` authoritative listing — **zero delta**. Only `GDGB2YR:GOV` + `GDGB10YR:GOV` exist in TE. `GDKK` ISO-currency-code prefix candidate empirically falsified (per ADR-0009 v2.3 §7.5.3). S2 HALT-0 **re-confirmed**; Path 2 Nationalbanken cascade empirically justified (existing `NationalbankenConnector` infra reusable — lowest Path 2 cohort cost). See `docs/backlog/probe-results/sprint-t-retry-multi-prefix-probe.md` §3.5.
- **Sprint 5B 2026-04-26 re-confirmation (3rd):** `/markets/bond` filtered + per-tenor `/markets/historical` daily-live verification — symbol set unchanged (2 tenors), obs counts +2 vs. T-Retry (n=594/600 → ~3 trading days appended), latest 24/04/2026 (≤7 day staleness window). Zero delta vs. v2.3 baseline. State frozen across 3 consecutive probes in 3-day window. Liberal HALT cap (≥3 cohort-wide) triggered by Sprint 5B alone; ADR-0009 §5B addendum stamps reinforcement (no v3 amendment). DK retains lowest Path 2 cost (1-2h CC) given `NationalbankenConnector` infra. See `docs/backlog/probe-results/sprint-5b-europe-sparse-confirmation-probe.md` §4.
- **Current behavior:** ``daily_curves --country DK`` raises ``InsufficientDataError`` citing ``CAL-CURVES-DK-PATH-2``; ``--all-t1`` skips DK.
- **Candidate Path 2 data paths (re-probe required):**
  1. **Danmarks Nationalbanken Statsbank (nationalbanken.statbank.dk)** — primary; Nationalbanken publishes DGB yields daily. Auth / parsing infra largely reusable via Sprint Y-DK ``NationalbankenConnector`` (which already handles CD-rate vs discount-rate divergence during negative-rate era — ver retro §4).
  2. **Danish Ministry of Finance** — issuer side, auction results.
- **Negative-rate-era handling:** DK experienced sustained negative yields 2015-2022 (CD rate trough -0.75%, discount rate -0.60% 2021-2022); β0 widening + flag per Sprint Y precedent.
- **Estimate:** 1-2h CC (lowest cost of the 5 Path 2 CALs given existing ``NationalbankenConnector`` infrastructure).
- **Related:** ``CAL-CURVES-NO-PATH-2`` / ``CAL-CURVES-SE-PATH-2`` (Nordic cohort); Sprint Y-DK ``NationalbankenConnector`` (reusable infra + negative-rate handling precedent).

### CAL-CURVES-T1-LINKER — Inflation-indexed yield curves for T1 non-US countries

- **Priority:** LOW — US TIPS already serves real-curve direct-linker path; non-US countries fall back to DERIVED (BEI-based) method once ExpInf overlay wires per-country inputs.
- **Trigger:** CAL-138 Sprint left fetch_yield_curve_linker as empty-dict stubs for Bundesbank / ECB SDW / TE (GB/JP/CA).
- **Current behavior:** ``derive_real_curve`` receives None linker_yields for DE/EA/GB/JP/CA, returns None RealCurve. Persistence skips NSSYieldCurveReal sibling row.
- **Required work per country:**
  - DE: Bundesbank BBSSY family (inflation-indexed Bund-i daily zero-coupon).
  - EA: N/A (aggregate series do not exist; track per-country via ``CAL-CURVES-FR-BDF`` / ``CAL-CURVES-IT-BDI`` / ``CAL-CURVES-ES-BDE`` / ``CAL-CURVES-PT-BPSTAT`` / ``CAL-CURVES-NL-DNB`` — linker scope folded into each per-country sprint post Sprint A 2026-04-22 supersession).
  - GB: BoE Database IFBS series (index-linked gilt 5Y-30Y).
  - JP: BoJ JGBi (10Y-30Y, limited).
  - CA: BoC Real Return Bonds (2Y-30Y, partial).
- **Impact if unresolved:** Real-curve direct-linker path remains US-only. DERIVED fallback (nominal - E[π]) provides coverage once ExpInf wires per-country.
- **Estimate:** 8-12h CC sprint (mostly DE + GB + CA; JP + periphery limited data).
- **Related:** CAL-138 (parent, closed); overlays/expected-inflation per-country integration.

### CAL-CURVES-CA-MIDCURVE — CA mid-curve gap (3Y/5Y/7Y tenors)

- **Priority:** LOW — CA currently fits via NS-reduced (6 tenors, MIN_OBSERVATIONS met); Svensson preferred if mid-curve fills.
- **Trigger:** CAL-138 Sprint empirical probe 2026-04-22 found TE GCAN family exposes 1M/3M/6M/1Y/2Y/10YR only — 3Y/5Y/7Y absent.
- **Current behavior:** CA daily_curves run fits NS 4-param (below MIN_OBSERVATIONS_FOR_SVENSSON=9).
- **Required work:** Wire BoC Valet (Government of Canada benchmark yields) for 3Y / 5Y / 7Y series. BoC Valet series IDs: ``V39056`` (3Y), ``V39060`` (5Y), ``V39062`` (7Y).
- **Impact if unresolved:** CA curve fit quality is NS-reduced; Svensson precision on hump/curvature unavailable. Downstream overlay impact modest (10Y anchor unchanged).
- **Estimate:** 2-3h CC.
- **Related:** CAL-138 (parent, closed); CAL-CURVES-T1-SPARSE (shared BoC Valet infrastructure).

### CAL-MONETARY-SINGLE-EVENT-LOOP — daily_monetary_indices single `asyncio.run` lifecycle ✅ CLOSED

- **Priority:** URGENT — resolved.
- **Trigger:** Week 10 Day 3 Apr 23 evening natural-fire via
  `sonar-daily-monetary-indices.service`. US + DE persisted (duplicate
  skip), then PT / IT / ES / FR / NL failed back-to-back with
  `RuntimeError: Event loop is closed`; connector teardown emitted
  5× `connector_aclose_error` (FredConnector / BisConnector / ...)
  and the service exited 1. Systemd restart loop 17:37-17:45 WEST
  until the timer was stopped manually.
- **Root cause:** `src/sonar/pipelines/daily_monetary_indices.py`
  wrapped the async `build_live_monetary_inputs` facade in a sync
  `InputsBuilder` that invoked `asyncio.run()` **per country** (linha
  627 factory) and iterated a second `asyncio.run(conn.aclose())`
  loop at teardown (linhas 735-748). Each `asyncio.run` creates and
  destroys a fresh event loop; `httpx.AsyncClient` transports bind to
  the loop of first I/O, so country #2+ hit closed-loop sockets. A
  pre-existing comment (linha 735) acknowledged the hazard but the
  historical mitigation was try/except warning, not cure.
- **Fix:** Sprint T0.1 refactor — single `asyncio.run(_run_async_pipeline())`
  at process entry; `_run_async_pipeline` manages a
  `contextlib.AsyncExitStack`, registers every connector via
  `stack.push_async_callback(conn.aclose)`, then awaits a single
  async dispatcher loop that `await`s the inputs builder per country.
  Zero `asyncio.run()` calls inside the loop. Pattern elevated to
  ADR-0011 **Principle 6 — Async lifecycle discipline**.
- **Validation:**
  1. Unit: `test_async_lifecycle_single_loop` asserts single
     `id(asyncio.get_running_loop())` across three-country dispatch.
  2. Unit: `test_connector_aclose_lifecycle` asserts each registered
     stub is closed exactly once, all closures on the same loop.
  3. Unit: `test_pipeline_no_asyncio_run_per_country` static-asserts
     the module source contains exactly one `asyncio.run(` site.
  4. Systemd: `sudo systemctl start sonar-daily-monetary-indices.service`
     → exit 0, journal clean of `Event loop is closed` /
     `connector_aclose_error` / `country_failed`.
- **Status:** CLOSED 2026-04-23 (Sprint T0.1).
- **Related:** ADR-0011 Principle 6 (canonical pattern);
  CAL-136 precedent (BIS live-canary teardown fix — same pattern,
  narrower scope).

### CAL-EXPINF-T1-AUDIT — Expected Inflation T1 coverage audit
- **Priority:** MEDIUM — gating L2 100% Phase 2 T1 declaration; bottleneck identified during Sprint 5 prep gap-to-100% review.
- **Trigger:** Phase 2 status review 2026-04-26 revealed coverage uncertain for 12/16 T1 countries. Confirmed live: US (BEI FRED), DE (BEI Bundesbank), EA (BEI ECB SDW), PT (DERIVED). Unconfirmed/sparse: FR, IT, ES, NL, GB, JP, CA, AU, NZ, CH, SE, NO, DK.
- **Required work:**
  1. Audit `expected_inflation_*` tables per spec hierarchy `BEI > SWAP > DERIVED > SURVEY` for each T1 country.
  2. Document active method per country in audit table (BEI/SWAP/DERIVED/SURVEY/MISSING + source).
  3. For DERIVED-eligible EA members (FR/IT/ES/NL): verify `EA + diff` path operational; ship if absent.
  4. For GB: probe BEI via BoE inflation-linked gilts before SURVEY DMP fallback.
  5. For JP: validate `boj_tankan` connector status (currently scaffold per Week 10); ship SURVEY path or escalate connector sprint.
  6. For CA/AU/NZ/CH/SE/NO/DK: probe TE Path 1 BEI/SWAP availability per ADR-0009 v2; SURVEY fallback if exhausted.
  7. Update `docs/specs/overlays/expected-inflation.md` country scope table with audit findings.
- **Impact if unresolved:** Expected Inflation Phase 2 T1 coverage % uncertain — blocks honest L2 100% milestone declaration. Downstream nominal-real conversions for cross-country MSC/FCS may quietly fall through to NULL flags.
- **Estimate:** 1-2 sprints CC (audit + DERIVED expansion ~1 sprint; SURVEY connector sprint potentially +1).
- **Related:** CAL-042 (per-tenor PT-EA differential, Phase 2 deferral); CAL-043 (boe_dmp/boj_tankan connector validation, Week 4+ deferral); ADR-0009 v2 (TE Path 1 mandatory probe discipline).

### CAL-TEST-CYCLES-FIXTURE-FLAKE-AND-FAIL — Cycles US tests inconsistent
- **Priority:** LOW — does not affect production pipeline; pre-existing.
- **Trigger:** Sprint 7B Commit 1 pre-push gate 2026-04-26 surfaced 2 issues. Supersedes preliminary CAL-TEST-CYCLES-FIXTURE-SEED-REGRESSION (filed 3f95f34, replaced after Hugo verified diagnosis split issue into genuine-failure + flake).
- **Issue 1 (genuine failure):** `tests/integration/test_cycles_composites.py::TestOrchestratorSmoke::test_us_smoke_end_to_end` fails consistently on main + branches. Error: `cycles.msc.skipped error="Composite requires >= 3 sub-indices; got 0 (missing: ['CS', 'M1', 'M2', 'M3', 'M4'])"`. Root cause: `_seed_all` seed function not populating in-memory test session for US monetary subindices. Schema canonical: `monetary_m1_effective_rates` / `monetary_m2_taylor_gaps` / `monetary_m4_fci`.
- **Issue 2 (flake):** `tests/unit/test_cycles/test_financial_fcs.py::TestComputeFcsHappy::test_us_full_stack` passes isolated (`pytest path::test_id`) but fails in full-suite run. Order-dependent test pollution / shared fixture interaction.
- **Required work:**
  1. Audit `_seed_all` (`test_cycles_composites.py`) seed function vs canonical schema names.
  2. Audit `_seed_f_rows` (`test_financial_fcs.py`) for shared state with sibling tests.
  3. Add per-test session isolation (function-scoped fixtures) where needed.
  4. Verify composite readers (`compute_all_cycles`, `compute_fcs`) match seed naming.
- **Impact if unresolved:** Pre-push gate continues to surface 2 failures every sprint; option-2 push-and-track pattern repeats. Test reliability degraded; CI false-positives.
- **Estimate:** 2-3h dedicated test-hygiene sprint.
- **Related:** Sprint 7B Commit 1 (defer-and-track precedent); Week 10 schema consolidation potential origin.
