# Calibration tasks — backlog

Placeholders declarados em specs P3-P5 a recalibrar empiricamente quando production data atingir horizonte mínimo. Agrupados por horizonte (acção ordenada) + spec owner (rastreabilidade).

**Convenção**: cada placeholder em specs marcado `placeholder — recalibrate after Nm`. Este inventário consolida todos os placeholders catalogados com ID estável `CAL-NNN`.

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

### CAL-057 — `daily_erp_us` pipeline for live connector orchestration (ERP US brief surfaced)

- **Priority:** MEDIUM
- **Trigger:** ERP US brief commit 8 (`6f3f9f0`) wired
  `daily_cost_of_capital` to **read** `erp_canonical` rows instead of
  the 5.5 % stub, but explicitly deferred the **write** path: no
  module today fetches FactSet + Yardeni + Shiller + multpl + spdji
  + FRED SP500 + Damodaran, calls `fit_erp_us`, and persists. Until
  such a pipeline exists, `erp_canonical` is populated only by direct
  test invocations / ad-hoc notebooks.
- **Scope:** New `src/sonar/pipelines/daily_erp_us.py` CLI
  (`--date YYYY-MM-DD`) that orchestrates the 7 connectors (FactSet
  + Yardeni best-effort + rest hard), assembles `ERPInput`, calls
  `fit_erp_us(inputs, damodaran_erp_decimal=...)`, persists via
  `persist_erp_fit_result`. Graceful degradation: each connector
  failure emits the relevant flag (`OVERLAY_MISS` etc.) but does not
  abort the fit unless < 2 methods remain. Integration test with
  cassette fixtures for all 7 sources.
- **Unblocks:** production `daily_cost_of_capital` runs with live
  ERP (rather than depending on manual `fit_erp_us` invocations).

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

### CAL-072 — BIS property dataflow rename (WS_LONG_PP → WS_SPP) (OPEN)

- **Priority:** HIGH (blocks F1 property-gap input live data)
- **Trigger:** Week 5 Sprint 1 Commit 5 cassette backfill discovered
  BIS SDMX v2 no longer serves dataflow `BIS:WS_LONG_PP(1.0)`. The
  structure index lists `WS_SPP` (Selected Property Prices),
  `WS_CPP` (Commercial Property Prices), and `WS_DPP` (Detailed
  Property Prices) instead. Current production code in
  `src/sonar/connectors/bis.py` references `DATAFLOW_WS_LONG_PP`,
  which returns HTTP 404. Cassette for `bis_property_pt_2024_01_02.json`
  was fetched from WS_SPP as a stopgap (SDMX-JSON 1.0 shape is
  identical so the parser accepts it). Live canary
  `test_live_canary_property_pt_recent` is xfail-marked until this
  item resolves.
- **Scope:** Rename `DATAFLOW_WS_LONG_PP` to `DATAFLOW_WS_SPP`
  (or equivalent). Verify key pattern `Q.{CTY}.N.628` still resolves
  under WS_SPP (manual probe via stats.bis.org structure endpoint).
  Update `source_tag` `BIS_WS_LONG_PP` → `BIS_WS_SPP` if call sites
  expect updated tags; otherwise retain legacy tag string for
  backward-compat in overlays/indices. Remove xfail marker once
  live canary passes.
- **Surfaced from:** Week 5 Sprint 1 Commit 5 cassette probe.
- **Unblocks:** F1 property-gap component; re-enables BIS property
  canary.

### CAL-073 — CBOE S&P put/call FRED series (PUTCLSPX) delisted (OPEN)

- **Priority:** MEDIUM (F4 degrades to 4-component OVERLAY_MISS path)
- **Trigger:** Week 5 Sprint 1 Commit 6 F4 live integration smoke
  discovered FRED returns ``400 "The series does not exist"`` for
  ``PUTCLSPX`` (CBOE S&P 500 total put/call ratio). CBOE also delisted
  the direct XLS download path for daily P/C history (data now behind
  the CBOE DataShop paywall).
- **Scope:** Identify alternative public source for daily P/C ratio.
  Candidates: Yahoo Finance ``^CPC`` (empirical — confirm availability),
  Nasdaq Data Link P/C ratio feed, or scrape CBOE's web interface
  (terms-of-service review required). Once chosen, refactor
  ``cboe.py::fetch_put_call`` to hit the new source; preserve
  ``FRED_SERIES_PUTCALL`` constant for any remaining historical wiring.
  Live F4 smoke currently tolerates missing P/C via OVERLAY_MISS flag.
- **Surfaced from:** Week 5 Sprint 1 Commit 6.
- **Unblocks:** F4 full 5-component live path; removes OVERLAY_MISS
  baseline flag from US F4 snapshots.

### CAL-092 — FRED ISM/NFIB delisted series fallback connectors (OPEN)

- **Priority:** MEDIUM
- **Trigger:** Week 5 Sprint 2a Commit 3 live probes confirmed FRED no
  longer serves ``NAPM`` (ISM Mfg PMI), ``NAPMII`` (ISM Svc PMI) or any
  ``NFIB`` series. Helpers now raise :class:`DataUnavailableError` with
  a canonical message so builders can emit spec flags.
- **Scope:** Implement direct ISM scraper (``connectors/ism.py`` per
  CAL-082) and NFIB scraper (new ``connectors/nfib.py``). Route around
  the delisted FRED IDs in the builders once the scrapers land.
- **Surfaced from:** Week 5 Sprint 2a Commit 3.
- **Unblocks:** E1 US ``pmi_composite``, E4 US
  ``ism_manufacturing`` / ``ism_services`` / ``nfib_small_business``.

### CAL-093 — Conference Board Consumer Confidence live feed (OPEN)

- **Priority:** LOW
- **Trigger:** Sprint 2a Commit 3: ``CONCCONF`` is not a FRED id. We
  substituted OECD composite consumer-confidence indicator
  ``CSCICP03USM665S`` which OECD discontinued at 2024-01. Values are
  usable historically but freeze going forward; E4 builder should emit
  ``CB_CONFIDENCE_STALE`` once data ages past a threshold.
- **Scope:** Identify a live public feed (Nasdaq Data Link, scrape
  conference-board.org, etc.) and switch the ``fetch_conference_
  board_confidence_us`` helper. Optionally add staleness flag logic.
- **Surfaced from:** Week 5 Sprint 2a Commit 3.

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

### CAL-080 — Eurostat SDMX connector (Week 5 ECS surfaced)

- **Priority:** MEDIUM
- **Trigger:** Week 5 ECS compute layer ships (E1/E3/E4 per spec)
  but stays data-empty for EA countries without Eurostat. Was
  originally brief week5 §Commit 3; descoped per user §7 budget trim.
- **Scope:** `src/sonar/connectors/eurostat.py` over SDMX-JSON 1.0
  at `https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1`.
  Dataflows: `namq_10_gdp`, `sts_inpr_m`, `lfsi_emp_m`, `sts_trtu_m`,
  `une_rt_m`, `ei_bsco_m`, `teibs020`. Country geo codes for 7 T1
  EA set (DE/PT/IT/ES/FR/NL + EA aggregate). Polite pacing 2 req/s.
- **Unblocks:** E1/E3/E4 EA coverage; large chunk of Week 6 ECS
  composite readiness.

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

### CAL-083 — FRED connector Economic-series extension (Week 5 ECS surfaced)

- **Priority:** LOW
- **Trigger:** Week 5 ECS brief §Commit 6; descoped to CAL.
- **Scope:** `src/sonar/connectors/fred.py` new section
  `# === Economic indicators ===` with helper resolvers for
  GDPC1, INDPRO, PAYEMS, RRSFS, W875RX1, UNRATE, JTSJOL,
  CES0500000003, ICSA, TEMPHELPS, UMCSENT, CSCICP03USM665S,
  USEPUINDXD, MICHM5YM5, NAPM, NAPMII, NFIBBTI, DRTSCILM, VIXCLS,
  EMRATIO, LNS11300060, ECIWAG, JTSQUL, IC4WSA. Zero new deps.
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

### CAL-086 — ZEW + Ifo DE sentiment scrapers (Week 5 ECS surfaced)

- **Priority:** LOW
- **Trigger:** E4 DE components `zew_expectations` +
  `ifo_business_climate`. Without them DE E4 drops to 4/13 components
  (below threshold → InsufficientDataError).
- **Scope:** `src/sonar/connectors/zew.py` + `connectors/ifo.py`,
  monthly scrape of headline indices. Module docstrings document
  scraping fragility + maintenance contract.
- **Unblocks:** DE full E4 row production.

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
