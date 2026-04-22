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
  + this backlog closure + retrospective). Backward compat aliases
  preserved in all four modules; removal Week 10 Day 1.

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
- **Status:** PARTIALLY CLOSED — M1 only. Full close pending CAL-120
  through CAL-123 landing.

### CAL-120 — JP M2 output-gap source (Week 8 Sprint L surfaced)

- **Priority:** MEDIUM — unblocks M2 JP Taylor-gap compute.
- **Trigger:** Sprint L C5 shipped `build_m2_jp_inputs` as wire-ready
  scaffold raising `InsufficientDataError`; JP has no CBO equivalent
  and OECD EO / BoJ Tankan are outside L0 coverage at Sprint L scope.
- **Scope:**
  - Probe TE generic `fetch_indicator("JP", "gdp gap", ...)` for
    coverage; if empty, probe OECD Economic Outlook direct API
    (quarterly cadence acceptable).
  - Wire JP output gap connector (FRED JPRGDP pattern or OECD EO
    direct) and populate `M2TaylorGapsInputs.output_gap_pct`.
  - Remove the scaffold `raise InsufficientDataError` in
    `build_m2_jp_inputs` once the resolver lands.
- **Unblocks:** M2 JP persistence end-to-end.
- **Status:** OPEN.

### CAL-121 — JP M4 FCI 5-component bundle (Week 8 Sprint L surfaced)

- **Priority:** MEDIUM — unblocks M4 JP custom-FCI compute.
- **Trigger:** Sprint L C5 shipped `build_m4_jp_inputs` as wire-ready
  scaffold raising `InsufficientDataError`; only 10Y JGB yield is
  mappable via existing TE `GJGB10:IND` at Sprint L scope, below the
  `MIN_CUSTOM_COMPONENTS == 5` floor from M4 spec §4.
- **Scope:** connectors/wrappers for the four missing components:
  - JP credit spread (BBB corp vs JGB; TE probe `credit spread`
    indicator or BoJ J-REIT proxy).
  - JP vol index (Nikkei VI via TE `NKYVOLX:IND` or OSE direct).
  - JPY NEER (BIS narrow/broad; wrapper not yet shipped).
  - JP mortgage rate (FRED `INTDSRJPM193N` candidate; probe pending).
- **Unblocks:** M4 JP persistence end-to-end.
- **Status:** OPEN.

### CAL-122 — JP M3 market-expectations overlays (Week 8 Sprint L surfaced)

- **Priority:** LOW — M3 depends on L2 persisted overlays per country;
  analogous to CAL-105 for UK.
- **Trigger:** M3 spec §2 requires persisted NSS forwards + EXPINF rows
  per country; Sprint L did not ship JP NSS or JP EXPINF overlays
  (Phase 2+ scope).
- **Scope:**
  - JP NSS overlay persistence (FRED `IRLTLT01JPM156N` + intermediate
    tenors via TE `GJGB2:IND` / `GJGB5:IND`; NSS fit via existing
    overlay module).
  - JP EXPINF overlay persistence (5Y/10Y breakeven-analog from BoJ
    Tankan survey series, if available; else BoJ 2% CPI target as
    CB-target fallback, mirroring UK).
  - `MonetaryDbBackedInputsBuilder.build_m3_inputs` JP path.
- **Unblocks:** M3 JP persistence end-to-end.
- **Status:** OPEN.

### CAL-123 — JP balance-sheet / GDP ratio wiring (Week 8 Sprint L surfaced)

- **Priority:** LOW — closes the `JP_BS_GDP_PROXY_ZERO` flag on M1 JP.
- **Trigger:** Sprint L C4 zero-seeded JP balance-sheet ratios because
  BoJ Monetary Base (`BS01'MABJMTA` via TSD) + Cabinet Office nominal
  GDP are not FRED-mirrored at Sprint L scope.
- **Scope:** direct BoJ TSD fetch for Monetary Base (if CAL-124 bypass
  lands) OR FRED JP M2 series (`MABMM301JPM189S`) as proxy; combined
  with Cabinet Office JP nominal GDP via FRED `JPNRGDPEXP` or similar.
- **Unblocks:** M1 JP BS/GDP signal history populated (currently seeded
  as zeros → balance_sheet_signal contribution to M1 score is null).
- **Status:** OPEN.

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

- **Priority:** MEDIUM — required input for M2 JP Taylor gap.
- **Trigger:** Sprint L C5 `build_m2_jp_inputs` scaffold lists JP CPI
  YoY as one of three missing inputs; generic TE `fetch_indicator("JP",
  "inflation rate", ...)` should cover but not probed at Sprint L scope.
- **Scope:**
  - Probe TE generic indicator for JP CPI YoY cadence + coverage.
  - Wire `fetch_jp_cpi_yoy` wrapper on `TEConnector` with source-drift
    guard (analogous to `fetch_jp_bank_rate`).
  - Consume in `build_m2_jp_inputs` output.
- **Unblocks:** M2 JP inflation input; combined with CAL-120 closes
  M2 JP.
- **Status:** OPEN.

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
- **Status:** PARTIALLY CLOSED — M1 only. Full close pending CAL-130
  through CAL-133 landing.

### CAL-130 — CA M2 output-gap source (Week 9 Sprint S surfaced)

- **Priority:** MEDIUM — unblocks M2 CA Taylor-gap compute.
- **Trigger:** Sprint S C4 shipped `build_m2_ca_inputs` as wire-ready
  scaffold raising `InsufficientDataError`; BoC publishes a quarterly
  output gap via Valet series (`DMREST_SEGP_GAP` candidate) but the
  wiring is not Sprint S scope.
- **Scope:**
  - Probe BoC Valet `DMREST_SEGP_GAP` + OECD EO CA for cadence +
    coverage.
  - Wire CA output-gap connector (Valet extension or OECD EO direct)
    and populate `M2TaylorGapsInputs.output_gap_pct`.
  - Remove the scaffold `raise InsufficientDataError` in
    `build_m2_ca_inputs` once the resolver lands.
- **Unblocks:** M2 CA persistence end-to-end.
- **Status:** OPEN.

### CAL-131 — CA M4 FCI 5-component bundle (Week 9 Sprint S surfaced)

- **Priority:** MEDIUM — unblocks M4 CA custom-FCI compute.
- **Trigger:** Sprint S C4 shipped `build_m4_ca_inputs` as wire-ready
  scaffold raising `InsufficientDataError`; only 10Y GoC (Valet
  `BD.CDN.10YR.DQ.YLD`) and policy rate (via M1 cascade) are mappable
  at Sprint S scope, below the `MIN_CUSTOM_COMPONENTS == 5` floor.
- **Scope:** connectors/wrappers for the missing components:
  - CA credit spread (BBB corp vs GoC; candidate: FRED `BAMLHYCA` or
    Valet bond-yield curve proxy).
  - CA vol index (no TSX VIX-analog on FRED; Yahoo `^VIXC` candidate
    or proxy from `^VIX`).
  - CA CAD NEER (BoC Valet `CEER_BROADN` is canonical daily
    nominal-CEER series).
  - CA mortgage rate (BoC Valet `V80691335` or equivalent).
- **Unblocks:** M4 CA persistence end-to-end.
- **Status:** OPEN.

### CAL-132 — CA M3 market-expectations overlays (Week 9 Sprint S surfaced)

- **Priority:** LOW — M3 depends on L2 persisted overlays per country;
  analogous to CAL-105 (UK) / CAL-122 (JP).
- **Trigger:** M3 spec §2 requires persisted NSS forwards + EXPINF
  rows per country; Sprint S did not ship CA NSS or CA EXPINF
  overlays (Phase 2+ scope).
- **Scope:**
  - CA NSS overlay persistence (BoC Valet yield-curve series family
    + FRED `IRLTLT01CAM156N` long-end; NSS fit via existing overlay
    module).
  - CA EXPINF overlay persistence (Valet CPI breakeven analog OR BoC
    2 % CPI target as CB-target fallback, mirroring UK / JP).
  - `MonetaryDbBackedInputsBuilder.build_m3_inputs` CA path.
- **Unblocks:** M3 CA persistence end-to-end.
- **Status:** OPEN.

### CAL-133 — CA balance-sheet / GDP ratio wiring (Week 9 Sprint S surfaced)

- **Priority:** LOW — closes the `CA_BS_GDP_PROXY_ZERO` flag on M1 CA.
- **Trigger:** Sprint S C4 zero-seeded CA balance-sheet ratios because
  BoC weekly balance-sheet aggregates (Valet `B50000` family candidate)
  + StatCan nominal GDP are not wired at Sprint S scope.
- **Scope:** direct BoC Valet fetch for balance-sheet aggregate OR
  FRED CA M2 series proxy, combined with StatCan CA nominal GDP via
  FRED `CANRGDPEXP` or equivalent.
- **Unblocks:** M1 CA BS/GDP signal history populated (currently
  seeded as zeros → balance_sheet_signal contribution to M1 score is
  null).
- **Status:** OPEN.

### CAL-134 — CA CPI YoY wrapper (Week 9 Sprint S surfaced)

- **Priority:** MEDIUM — required input for M2 CA Taylor gap.
- **Trigger:** Sprint S C4 `build_m2_ca_inputs` scaffold lists CA CPI
  YoY as one of three missing inputs; TE generic `fetch_indicator("CA",
  "inflation rate", ...)` should cover but not probed at Sprint S
  scope. StatCan also publishes CPI via Valet-adjacent feeds.
- **Scope:**
  - Probe TE generic indicator for CA CPI YoY cadence + coverage.
  - Wire `fetch_ca_cpi_yoy` wrapper on `TEConnector` with
    source-drift guard (analogous to `fetch_ca_bank_rate` /
    `fetch_jp_bank_rate`).
  - Consume in `build_m2_ca_inputs` output.
- **Unblocks:** M2 CA inflation input; combined with CAL-130 +
  CAL-135 closes M2 CA.
- **Status:** OPEN.

### CAL-135 — CA inflation-forecast wrapper (Week 9 Sprint S surfaced)

- **Priority:** LOW — nice-to-have for M2 CA compute; BoC 2 % CPI
  target serves as CB-target proxy until this lands.
- **Trigger:** BoC publishes quarterly Monetary Policy Report forecast
  series that are Valet-hosted (candidate: `MPR_INFL_EXP_4Q` family)
  but unwired at Sprint S scope. M2 CA currently treats the 2 % target
  as the inflation-forecast proxy via `EXPECTED_INFLATION_CB_TARGET`.
- **Scope:**
  - Probe Valet for BoC MPR inflation-forecast series.
  - Wire `fetch_ca_inflation_forecast` on `BoCConnector`.
  - Consume in `build_m2_ca_inputs` with new flag
    `CA_INFLATION_FORECAST_BOC_MPR` (replacing the
    `EXPECTED_INFLATION_CB_TARGET` proxy flag when available).
- **Unblocks:** M2 CA second-cycle inflation input; combined with
  CAL-130 + CAL-134 closes M2 CA.
- **Status:** OPEN.

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
- **Status:** PARTIALLY CLOSED — M1 only. Full close pending
  CAL-AU-GAP / CAL-AU-M4-FCI / CAL-AU-M3 / CAL-AU-BS-GDP / CAL-AU-CPI /
  CAL-AU-INFL-FORECAST landing.

### CAL-AU-GAP — AU M2 output-gap source (Week 9 Sprint T surfaced)

- **Priority:** MEDIUM — unblocks M2 AU Taylor-gap compute.
- **Trigger:** Sprint T C4 shipped `build_m2_au_inputs` as wire-ready
  scaffold raising `InsufficientDataError`; RBA publishes a quarterly
  output-gap discussion in SMP technical notes but no scriptable
  endpoint exists at Sprint T scope.
- **Scope:**
  - Probe OECD EO AU for cadence + coverage (canonical fallback across
    the cascade family).
  - Probe RBA SMP table + ABS RBANZ for any scriptable series;
    otherwise consume the OECD EO path.
  - Wire AU output-gap connector and populate
    `M2TaylorGapsInputs.output_gap_pct`.
  - Remove the scaffold `raise InsufficientDataError` in
    `build_m2_au_inputs` once the resolver lands.
- **Unblocks:** M2 AU persistence end-to-end.
- **Status:** OPEN.

### CAL-AU-M4-FCI — AU M4 FCI 5-component bundle (Week 9 Sprint T surfaced)

- **Priority:** MEDIUM — unblocks M4 AU custom-FCI compute.
- **Trigger:** Sprint T C4 shipped `build_m4_au_inputs` as wire-ready
  scaffold raising `InsufficientDataError`; only 10Y AGB (RBA F2
  `FCMYGBAG10D`) and policy rate (via M1 cascade) are mappable at
  Sprint T scope, below the `MIN_CUSTOM_COMPONENTS == 5` floor.
- **Scope:** connectors/wrappers for the missing components:
  - AU credit spread (BBB corp vs AGB; candidate: FRED `BAMLHYAU` or
    RBA F3 corporate-yield series).
  - AU vol index (no ASX VIX-analog on FRED; Yahoo `^AXVI` candidate
    or proxy from `^VIX`).
  - AU AUD NEER (RBA F11 nominal-TWI index).
  - AU mortgage rate (RBA F5 lender-rates table).
- **Unblocks:** M4 AU persistence end-to-end.
- **Status:** OPEN.

### CAL-AU-M3 — AU M3 market-expectations overlays (Week 9 Sprint T surfaced)

- **Priority:** LOW — M3 depends on L2 persisted overlays per country;
  analogous to CAL-105 (UK) / CAL-122 (JP) / CAL-132 (CA).
- **Trigger:** M3 spec §2 requires persisted NSS forwards + EXPINF
  rows per country; Sprint T did not ship AU NSS or AU EXPINF
  overlays (Phase 2+ scope).
- **Scope:**
  - AU NSS overlay persistence (RBA F2 yield-curve series family +
    FRED `IRLTLT01AUM156N` long-end; NSS fit via existing overlay
    module).
  - AU EXPINF overlay persistence (RBA Indexed-Bond 10Y `FCMYGBAGID`
    breakeven analog OR RBA 2.5 % CPI-target midpoint as CB-target
    fallback, mirroring UK / JP / CA).
  - `MonetaryDbBackedInputsBuilder.build_m3_inputs` AU path.
- **Unblocks:** M3 AU persistence end-to-end.
- **Status:** OPEN.

### CAL-AU-BS-GDP — AU balance-sheet / GDP ratio wiring (Week 9 Sprint T surfaced)

- **Priority:** LOW — closes the `AU_BS_GDP_PROXY_ZERO` flag on M1 AU.
- **Trigger:** Sprint T C4 zero-seeded AU balance-sheet ratios because
  RBA weekly balance-sheet aggregates (table A1 candidate) + ABS
  nominal GDP are not wired at Sprint T scope.
- **Scope:** RBA A1 weekly balance-sheet series (total assets) combined
  with ABS nominal GDP via FRED `AUSGDPNAD2GDQ` or equivalent.
- **Unblocks:** M1 AU BS/GDP signal history populated (currently seeded
  as zeros → balance_sheet_signal contribution to M1 score is null).
- **Status:** OPEN.

### CAL-AU-CPI — AU CPI YoY wrapper (Week 9 Sprint T surfaced)

- **Priority:** MEDIUM — required input for M2 AU Taylor gap.
- **Trigger:** Sprint T C4 `build_m2_au_inputs` scaffold lists AU CPI
  YoY as one of three missing inputs; TE generic
  `fetch_indicator("AU", "inflation rate", ...)` should cover but not
  probed at Sprint T scope. ABS publishes quarterly CPI.
- **Scope:**
  - Probe TE generic indicator for AU CPI YoY cadence + coverage.
  - Wire `fetch_au_cpi_yoy` wrapper on `TEConnector` with
    source-drift guard (analogous to `fetch_au_cash_rate`).
  - Consume in `build_m2_au_inputs` output.
- **Unblocks:** M2 AU inflation input; combined with CAL-AU-GAP +
  CAL-AU-INFL-FORECAST closes M2 AU.
- **Status:** OPEN.

### CAL-AU-INFL-FORECAST — AU inflation-forecast wrapper (Week 9 Sprint T surfaced)

- **Priority:** LOW — nice-to-have for M2 AU compute; RBA 2.5 %
  CPI-target midpoint serves as CB-target proxy until this lands.
- **Trigger:** RBA publishes quarterly SMP forecast tables (HTML-only)
  but unwired at Sprint T scope. M2 AU currently treats the 2.5 %
  target midpoint as the inflation-forecast proxy via
  `EXPECTED_INFLATION_CB_TARGET`.
- **Scope:**
  - Probe RBA SMP for scriptable forecast series.
  - Wire `fetch_au_inflation_forecast` (connector TBD — likely a
    HTML-scrape adapter on top of `RBAConnector`).
  - Consume in `build_m2_au_inputs` with new flag
    `AU_INFLATION_FORECAST_RBA_SMP` (replacing the
    `EXPECTED_INFLATION_CB_TARGET` proxy flag when available).
- **Unblocks:** M2 AU second-cycle inflation input; combined with
  CAL-AU-GAP + CAL-AU-CPI closes M2 AU.
- **Status:** OPEN.

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
- **Status:** PARTIALLY CLOSED — M1 only. Full close pending
  CAL-NZ-M2-OUTPUT-GAP / CAL-NZ-M4-FCI / CAL-NZ-M3 / CAL-NZ-BS-GDP /
  CAL-NZ-CPI / CAL-NZ-INFL-FORECAST / CAL-NZ-RBNZ-TABLES landing.

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

- **Priority:** MEDIUM — unblocks M2 NZ Taylor-gap compute.
- **Trigger:** Sprint U-NZ C4 shipped `build_m2_nz_inputs` as
  wire-ready scaffold raising `InsufficientDataError`; Stats NZ +
  the NZ Treasury (HYEFU / BEFU) publish quarterly output-gap
  estimates but no scriptable endpoint exists at Sprint U-NZ scope.
- **Scope:**
  - Probe OECD EO NZ for cadence + coverage (canonical fallback
    across the cascade family).
  - Probe Stats NZ `infoshare` + NZ Treasury HYEFU/BEFU HTML for any
    scriptable series; otherwise consume the OECD EO path.
  - Wire NZ output-gap connector and populate
    `M2TaylorGapsInputs.output_gap_pct`.
  - Remove the scaffold `raise InsufficientDataError` in
    `build_m2_nz_inputs` once the resolver lands.
- **Unblocks:** M2 NZ persistence end-to-end.
- **Status:** OPEN.

### CAL-NZ-M4-FCI — NZ M4 FCI 5-component bundle (Week 9 Sprint U-NZ surfaced)

- **Priority:** MEDIUM — unblocks M4 NZ custom-FCI compute.
- **Trigger:** Sprint U-NZ C4 shipped `build_m4_nz_inputs` as
  wire-ready scaffold raising `InsufficientDataError`; only policy
  rate (via M1 cascade) is mappable at Sprint U-NZ scope, below the
  `MIN_CUSTOM_COMPONENTS == 5` floor. 10Y NZ gov is available via
  FRED (`IRLTLT01NZM156N`) monthly but not yet wired.
- **Scope:** connectors/wrappers for the missing components:
  - NZ credit spread (BBB corp vs NZ gov; RBNZ B5 corporate-yield
    series candidate once host unblocks, or Bloomberg NZD credit
    indices).
  - NZ vol index (no NZX VIX-analog published; proxy from global
    VIX or `^AXVI` with weighting).
  - NZ 10Y government stock yield (RBNZ B2 weekly long-maturity
    series pending CAL-NZ-RBNZ-TABLES; FRED `IRLTLT01NZM156N` OECD
    mirror available monthly).
  - NZ NZD NEER (RBNZ B14 trade-weighted index).
  - NZ mortgage rate (RBNZ B20 lender-rates table).
- **Unblocks:** M4 NZ persistence end-to-end.
- **Status:** OPEN.

### CAL-NZ-M3 — NZ M3 market-expectations overlays (Week 9 Sprint U-NZ surfaced)

- **Priority:** LOW — M3 depends on L2 persisted overlays per
  country; analogous to CAL-105 (UK) / CAL-122 (JP) / CAL-132 (CA) /
  CAL-AU-M3 (AU).
- **Trigger:** M3 spec §2 requires persisted NSS forwards + EXPINF
  rows per country; Sprint U-NZ did not ship NZ NSS or NZ EXPINF
  overlays (Phase 2+ scope).
- **Scope:**
  - NZ NSS overlay persistence (RBNZ B2 yield-curve series family
    pending host unblock + FRED `IRLTLT01NZM156N` long-end; NSS fit
    via existing overlay module).
  - NZ EXPINF overlay persistence (NZ inflation-indexed bond
    breakeven, or RBNZ 2 % CPI-target midpoint as CB-target
    fallback — mirroring UK / JP / CA / AU).
  - `MonetaryDbBackedInputsBuilder.build_m3_inputs` NZ path.
- **Unblocks:** M3 NZ persistence end-to-end.
- **Status:** OPEN.

### CAL-NZ-BS-GDP — NZ balance-sheet / GDP ratio wiring (Week 9 Sprint U-NZ surfaced)

- **Priority:** LOW — closes the `NZ_BS_GDP_PROXY_ZERO` flag on M1 NZ.
- **Trigger:** Sprint U-NZ C4 zero-seeded NZ balance-sheet ratios
  because RBNZ balance-sheet aggregates (B5/B6 series candidate) +
  Stats NZ nominal GDP are not wired at Sprint U-NZ scope. Stats NZ
  `infoshare` covers NZ GDP; RBNZ balance-sheet pends
  CAL-NZ-RBNZ-TABLES.
- **Scope:** RBNZ B5/B6 balance-sheet series combined with Stats NZ
  nominal GDP (or equivalent FRED mirror).
- **Unblocks:** M1 NZ BS/GDP signal history populated (currently
  seeded as zeros → balance_sheet_signal contribution to M1 score is
  null).
- **Status:** OPEN.

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
- **Status:** PARTIALLY CLOSED — M1 only. Full close pending
  CAL-CH-GAP / CAL-CH-M4-FCI / CAL-CH-M3 / CAL-CH-BS-GDP /
  CAL-CH-CPI / CAL-CH-INFL-FORECAST landing.

### CAL-CH-GAP — CH M2 output-gap source (Week 9 Sprint V surfaced)

- **Priority:** MEDIUM — unblocks M2 CH Taylor-gap compute.
- **Trigger:** Sprint V C4 shipped `build_m2_ch_inputs` as wire-ready
  scaffold raising `InsufficientDataError`; SECO publishes the
  quarterly KOF-SECO output gap but no scriptable endpoint exists
  at Sprint V scope.
- **Scope:**
  - Probe OECD EO CH for cadence + coverage (canonical fallback
    across the cascade family).
  - Probe SECO macroeconomic forecast PDFs / KOF scriptable endpoints
    for any structured series; otherwise consume the OECD EO path.
  - Wire CH output-gap connector and populate
    `M2TaylorGapsInputs.output_gap_pct`.
  - Remove the scaffold `raise InsufficientDataError` in
    `build_m2_ch_inputs` once the resolver lands.
- **Unblocks:** M2 CH persistence end-to-end.
- **Status:** OPEN.

### CAL-CH-M4-FCI — CH M4 FCI 5-component bundle (Week 9 Sprint V surfaced)

- **Priority:** MEDIUM — unblocks M4 CH custom-FCI compute.
- **Trigger:** Sprint V C4 shipped `build_m4_ch_inputs` as wire-ready
  scaffold raising `InsufficientDataError`; only 10Y Confederation
  (SNB `rendoblim` 10J) and policy rate (via M1 cascade) are
  mappable at Sprint V scope, below the `MIN_CUSTOM_COMPONENTS == 5`
  floor.
- **Scope:** connectors/wrappers for the missing components:
  - CH credit spread (CHF corp vs Confederation; candidate: SNB
    `rendopa` Pfandbrief yield cube — no FRED mirror known).
  - CH vol index (no SMI vol index on FRED; candidate: Yahoo `^VSMI`
    which SIX/UBS co-publish, or realised-vol proxy from `^SSMI`
    returns).
  - CHF NEER (SNB `capaerenexch` cube or BIS Trade-Weighted indices
    via existing `bis.py` connector).
  - CH mortgage rate (SNB `zihypch` table — no wrapper at Sprint V
    scope).
- **Unblocks:** M4 CH persistence end-to-end.
- **Status:** OPEN.

### CAL-CH-M3 — CH M3 market-expectations overlays (Week 9 Sprint V surfaced)

- **Priority:** LOW — M3 depends on L2 persisted overlays per country;
  analogous to CAL-105 (UK) / CAL-122 (JP) / CAL-132 (CA) / CAL-AU-M3
  (AU).
- **Trigger:** M3 spec §2 requires persisted NSS forwards + EXPINF
  rows per country; Sprint V did not ship CH NSS or CH EXPINF
  overlays (Phase 2+ scope).
- **Scope:**
  - CH NSS overlay persistence (SNB `rendoblim` 1J-30J tenor family
    + FRED `IRLTLT01CHM156N` long-end; NSS fit via existing overlay
    module).
  - CH EXPINF overlay persistence — note SNB does not issue
    inflation-indexed Confederation bonds (no direct breakeven
    series), so fallback is the 1 % SNB 0-2 % band midpoint (already
    wired as `EXPECTED_INFLATION_CB_TARGET` / `CH_INFLATION_TARGET_BAND`
    proxy).
  - `MonetaryDbBackedInputsBuilder.build_m3_inputs` CH path.
- **Unblocks:** M3 CH persistence end-to-end.
- **Status:** OPEN.

### CAL-CH-BS-GDP — CH balance-sheet / GDP ratio wiring (Week 9 Sprint V surfaced)

- **Priority:** LOW — closes the `CH_BS_GDP_PROXY_ZERO` flag on M1 CH.
- **Trigger:** Sprint V C4 zero-seeded CH balance-sheet ratios because
  SNB monthly statistical bulletin (MSB Table B1A candidate) + SECO
  nominal GDP are not wired at Sprint V scope. SNB balance sheet is
  structurally unusual — large forex-intervention-driven asset base
  dating from the 2011-2015 CHF-floor regime — so the zero-seed is
  especially visible.
- **Scope:** SNB MSB B1A monthly total assets series combined with
  SECO nominal GDP (or equivalent FRED `CHEGDPNAD2GDQ`-style series).
- **Unblocks:** M1 CH BS/GDP signal history populated (currently
  seeded as zeros → balance_sheet_signal contribution to M1 score is
  null).
- **Status:** OPEN.

### CAL-NZ-CPI — NZ CPI YoY wrapper (Week 9 Sprint U-NZ surfaced)

- **Priority:** MEDIUM — required input for M2 NZ Taylor gap.
- **Trigger:** Sprint U-NZ C4 `build_m2_nz_inputs` scaffold lists NZ
  CPI YoY as one of three missing inputs; TE generic
  `fetch_indicator("NZ", "inflation rate", ...)` should cover but
  not probed at Sprint U-NZ scope. Stats NZ publishes quarterly CPI.
- **Scope:**
  - Probe TE generic indicator for NZ CPI YoY cadence + coverage.
  - Wire `fetch_nz_cpi_yoy` wrapper on `TEConnector` with
    source-drift guard (analogous to `fetch_nz_ocr`).
  - Consume in `build_m2_nz_inputs` output.
- **Unblocks:** M2 NZ inflation input; combined with
  CAL-NZ-M2-OUTPUT-GAP + CAL-NZ-INFL-FORECAST closes M2 NZ.
- **Status:** OPEN.

### CAL-NZ-INFL-FORECAST — NZ inflation-forecast wrapper (Week 9 Sprint U-NZ surfaced)

- **Priority:** LOW — nice-to-have for M2 NZ compute; RBNZ 2 %
  CPI-target midpoint serves as CB-target proxy until this lands.
- **Trigger:** RBNZ publishes quarterly Monetary Policy Statement
  (MPS) forecast tables (HTML / PDF) but unwired at Sprint U-NZ
  scope. M2 NZ currently treats the 2 % target midpoint as the
  inflation-forecast proxy via `EXPECTED_INFLATION_CB_TARGET`.
- **Scope:**
  - Probe RBNZ MPS for scriptable forecast series (post host
    unblock).
  - Wire `fetch_nz_inflation_forecast` (connector TBD — likely a
    HTML/PDF-scrape adapter on top of `RBNZConnector`).
  - Consume in `build_m2_nz_inputs` with new flag
    `NZ_INFLATION_FORECAST_RBNZ_MPS` (replacing the
    `EXPECTED_INFLATION_CB_TARGET` proxy flag when available).
- **Unblocks:** M2 NZ second-cycle inflation input; combined with
  CAL-NZ-M2-OUTPUT-GAP + CAL-NZ-CPI closes M2 NZ.
- **Status:** OPEN.

### CAL-CH-CPI — CH CPI YoY wrapper (Week 9 Sprint V surfaced)

- **Priority:** MEDIUM — required input for M2 CH Taylor gap.
- **Trigger:** Sprint V C4 `build_m2_ch_inputs` scaffold lists CH CPI
  YoY as one of three missing inputs; TE generic
  `fetch_indicator("CH", "inflation rate", ...)` should cover but not
  probed at Sprint V scope. SNB publishes the `cpikern` cube
  (headline + core CPI, monthly).
- **Scope:**
  - Probe TE generic indicator for CH CPI YoY cadence + coverage.
  - Probe SNB `cpikern` cube via the existing `SNBConnector` for a
    native alternative.
  - Wire `fetch_ch_cpi_yoy` wrapper on `TEConnector` (or
    `SNBConnector`) with source-drift guard (analogous to
    `fetch_ch_policy_rate`).
  - Consume in `build_m2_ch_inputs` output.
- **Unblocks:** M2 CH inflation input; combined with CAL-CH-GAP +
  CAL-CH-INFL-FORECAST closes M2 CH.
- **Status:** OPEN.

### CAL-CH-INFL-FORECAST — CH inflation-forecast wrapper (Week 9 Sprint V surfaced)

- **Priority:** LOW — nice-to-have for M2 CH compute; SNB 0-2 % band
  midpoint (1 %) serves as CB-target proxy until this lands.
- **Trigger:** SNB publishes quarterly Monetary Policy Assessment
  forecast tables (HTML-only) but unwired at Sprint V scope. M2 CH
  currently treats the 1 % midpoint as the inflation-forecast proxy
  via `EXPECTED_INFLATION_CB_TARGET` + `CH_INFLATION_TARGET_BAND`.
- **Scope:**
  - Probe SNB MPA for scriptable forecast series.
  - Wire `fetch_ch_inflation_forecast` (connector TBD — likely a
    HTML-scrape adapter on top of `SNBConnector`).
  - Consume in `build_m2_ch_inputs` with new flag
    `CH_INFLATION_FORECAST_SNB_MPA` (replacing the
    `EXPECTED_INFLATION_CB_TARGET` proxy flag when available).
- **Unblocks:** M2 CH second-cycle inflation input; combined with
  CAL-CH-GAP + CAL-CH-CPI closes M2 CH.
- **Status:** OPEN.

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
- **Unblocks:** Closes M1 NO M2 T1 Core item. Remaining tracked by
  CAL-NO-CPI / CAL-NO-M2-OUTPUT-GAP / CAL-NO-INFL-FORECAST /
  CAL-NO-M4-FCI / CAL-NO-M3 / CAL-NO-BS-GDP landing.

### CAL-NO-M2-OUTPUT-GAP — NO M2 output-gap source (Week 9 Sprint X-NO surfaced)

- **Priority:** MEDIUM — blocks M2 NO Taylor-gap compute; OECD EO NO
  is the natural mirror path via the existing FRED connector.
- **Trigger:** Sprint X-NO shipped `build_m2_no_inputs` as a scaffold
  that raises `InsufficientDataError` because NO output-gap source is
  not wired. Statistics Norway + Norges Bank's own "regional network"
  qualitative survey contribute the domestic input set but neither
  is scriptable at quarterly cadence within Sprint X-NO scope.
- **Scope:** Probe FRED's OECD EO mirror for the NO output-gap
  series (pattern: `NORGDPGAPQPANA` or similar OECD suffix); wire
  `fetch_no_output_gap` on the FRED connector; consume via the M2 NO
  builder. Alternative (secondary): the Statistics Norway national-
  accounts API at `data.ssb.no/api/v0/en/table/09190` could be
  wrapped as a SSB-native connector if OECD proves unreliable.
- **Unblocks:** M2 NO first-cycle output-gap input; combined with
  CAL-NO-CPI + CAL-NO-INFL-FORECAST closes M2 NO.
- **Status:** OPEN.

### CAL-NO-M4-FCI — NO M4 FCI 5-component bundle (Week 9 Sprint X-NO surfaced)

- **Priority:** MEDIUM — NO lacks an NFCI-style direct aggregator so
  the spec §4 custom-FCI path requires ≥5 components; 2 are wired.
- **Trigger:** Sprint X-NO shipped `build_m4_no_inputs` as a scaffold
  that raises `InsufficientDataError` because fewer than 5 of the
  seven FCI inputs are available. Wired at close: policy-rate M1
  cascade + 10Y generic gov-bond yield (Norges Bank
  `GOVT_GENERIC_RATES/B.10Y.GBON`). Pending: credit spread + vol +
  NOK NEER + mortgage rate.
- **Scope:**
  - NO credit spread: BBB NOK corp vs Norwegian gov — candidates
    Nordic Credit Rating / Nordea indices, or SSB corporate-bond
    yield table 12132 (quarterly).
  - NO vol index: no OSE-VIX-analog published; proxy candidate
    realised-vol from OBX 25 Index returns via Yahoo Finance.
  - NOK NEER: Norges Bank `EXR` dataflow publishes the TWI-based
    effective exchange rate as `I-44`; wire-ready via an additional
    Norges Bank DataAPI call.
  - NO mortgage rate: SSB table 10746 tracks monthly mortgage-rate
    averages; no wrapper at Sprint X-NO scope.
- **Petroleum context**: Norway's oil-NOK coupling is a structural
  feature that future NO FCI work needs to address. Brent / WTI
  price moves propagate into NOK exchange-rate and domestic
  petroleum-sector credit conditions within trading days — tighter
  than any other G10 FCI-component coupling. This is Phase 2+
  research scope, not CAL-NO-M4-FCI scope.
- **Unblocks:** M4 NO composite computation; closes final M-sub-index
  for NO at M1/M2/M4 level (M3 is CAL-NO-M3).
- **Status:** OPEN.

### CAL-NO-M3 — NO M3 market-expectations overlays (Week 9 Sprint X-NO surfaced)

- **Priority:** LOW — M3 requires NO NSS forwards + EXPINF overlay
  persistence which is Phase 2+ scope.
- **Trigger:** Sprint X-NO did not ship M3 NO. Spec M3 market-
  expectations composite requires NSS curve forwards + EXPINF series
  resolution at daily cadence.
- **Scope:** Wire NO NSS curve (Norges Bank publishes zero-coupon
  yields via `SEC` dataflow — possible DB-backed landing), EXPINF
  NO breakeven (not readily available; inflation-linked debt market
  in Norway is thin), and consume in `MonetaryDbBackedInputsBuilder`
  for M3 NO.
- **Unblocks:** M3 NO composite computation.
- **Status:** OPEN (Phase 2+).

### CAL-NO-BS-GDP — NO balance-sheet / GDP ratio wiring (Week 9 Sprint X-NO surfaced)

- **Priority:** LOW — closes the `NO_BS_GDP_PROXY_ZERO` flag on M1 NO.
- **Trigger:** Sprint X-NO C4 zero-seeded NO balance-sheet ratios
  because Norges Bank balance-sheet + Statistics Norway GDP are not
  wired. **Special context**: Norway's GPFG (Government Pension Fund
  Global — NOK ~16 trillion) is legally offshore-invested so the
  domestic central-bank balance-sheet is an order of magnitude
  smaller than G10 peers' post-QE balances. Regime classifiers
  consuming NO BS/GDP should treat the signal with caution until a
  sovereign-fund-adjusted variant is wired (Phase 2+ research).
- **Scope:** Norges Bank balance-sheet aggregate (dataflow TBD — the
  `LIQUIDITY_STATISTICS` or `FINANCIAL_INDICATORS` flow are
  candidates) combined with Statistics Norway nominal GDP (SSB
  table 09842 — quarterly national accounts) or the equivalent FRED
  OECD mirror.
- **Unblocks:** M1 NO BS/GDP signal history populated (currently
  seeded as zeros → balance_sheet_signal contribution to M1 score is
  null).
- **Status:** OPEN.

### CAL-NO-CPI — NO CPI YoY wrapper (Week 9 Sprint X-NO surfaced)

- **Priority:** MEDIUM — blocks M2 NO inflation-gap compute; SSB
  publishes scriptable monthly CPI.
- **Trigger:** Sprint X-NO shipped M2 NO as a scaffold because no
  `fetch_no_cpi_yoy` wrapper exists on either TE or FRED within
  Sprint X-NO scope.
- **Scope:** Probe Statistics Norway's CPI table 03013 at
  `data.ssb.no/api/v0/en/table/03013` for a scriptable monthly CPI
  YoY series; wire via a new SSB connector (or extend the FRED path
  if a NORCPIALLMINMEI-equivalent exists). Consume in
  `build_m2_no_inputs` with new flag `NO_CPI_YOY_SSB_NATIVE` or
  `NO_CPI_YOY_FRED_OECD` depending on source.
- **Unblocks:** M2 NO inflation input; combined with
  CAL-NO-M2-OUTPUT-GAP + CAL-NO-INFL-FORECAST closes M2 NO.
- **Status:** OPEN.

### CAL-NO-INFL-FORECAST — NO inflation-forecast wrapper (Week 9 Sprint X-NO surfaced)

- **Priority:** LOW — nice-to-have for M2 NO compute; Norges Bank
  2 % CPI target (post-2018) serves as CB-target proxy until this
  lands.
- **Trigger:** Norges Bank publishes quarterly Monetary Policy
  Report (MPR) forecasts — PDF + HTML-hosted, unwired Sprint X-NO
  scope. M2 NO currently treats the 2 % target as the inflation-
  forecast proxy via `EXPECTED_INFLATION_CB_TARGET`.
- **Scope:**
  - Probe Norges Bank MPR landing pages + appendix tables for a
    scriptable forecast series. MPR forecast tables are typically
    published quarterly in PDF — no SDMX dataflow at probe.
  - Wire `fetch_no_inflation_forecast` (connector TBD — likely a
    HTML-scrape or PDF-parse adapter on top of the base HTTP client).
  - Consume in `build_m2_no_inputs` with new flag
    `NO_INFLATION_FORECAST_NB_MPR` (replacing the
    `EXPECTED_INFLATION_CB_TARGET` proxy flag when available).
- **Unblocks:** M2 NO second-cycle inflation input; combined with
  CAL-NO-M2-OUTPUT-GAP + CAL-NO-CPI closes M2 NO.
- **Status:** OPEN.


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
- **Status:** PARTIALLY CLOSED — M1 only. Full close pending
  CAL-SE-GAP / CAL-SE-M4-FCI / CAL-SE-M3 / CAL-SE-BS-GDP /
  CAL-SE-CPI / CAL-SE-INFL-FORECAST landing.

### CAL-SE-GAP — SE M2 output-gap source (Week 9 Sprint W-SE surfaced)

- **Priority:** MEDIUM — unblocks M2 SE Taylor-gap compute.
- **Trigger:** Sprint W-SE C4 shipped `build_m2_se_inputs` as
  wire-ready scaffold raising `InsufficientDataError`;
  Konjunkturinstitutet (NIER) publishes the quarterly Swedish
  output gap but no scriptable endpoint exists at Sprint W-SE scope.
- **Scope:**
  - Probe OECD EO SE for cadence + coverage (canonical fallback
    across the cascade family).
  - Probe NIER Konjunkturläget forecast PDFs / HTML tables for any
    structured output-gap series; otherwise consume the OECD EO
    path.
  - Wire SE output-gap connector and populate
    `M2TaylorGapsInputs.output_gap_pct`.
  - Remove the scaffold `raise InsufficientDataError` in
    `build_m2_se_inputs` once the resolver lands.
- **Unblocks:** M2 SE persistence end-to-end.
- **Status:** OPEN.

### CAL-SE-M4-FCI — SE M4 FCI 5-component bundle (Week 9 Sprint W-SE surfaced)

- **Priority:** MEDIUM — unblocks M4 SE custom-FCI compute.
- **Trigger:** Sprint W-SE C4 shipped `build_m4_se_inputs` as
  wire-ready scaffold raising `InsufficientDataError`; only 10Y SGB
  via FRED `IRLTLT01SEM156N` OECD mirror (live at Sprint W-SE
  probe) and policy rate (via M1 cascade) + corridor floor/ceiling
  (SECBDEPOEFF / SECBLENDEFF, shipped Sprint W-SE C2) are mappable
  at Sprint W-SE scope, below the `MIN_CUSTOM_COMPONENTS == 5`
  floor.
- **Scope:** connectors/wrappers for the missing components:
  - SE credit spread (SEK corp vs SGB; candidates: Riksbank
    Financial Market Statistics (FMÖ) or SCB credit aggregates —
    no FRED mirror known).
  - SE vol index (no OMXS30 vol index on FRED; candidates: Nasdaq
    OMX's VINX30 or realised-vol proxy from `^OMXS30` returns via
    Yahoo Finance).
  - SEK NEER (Riksbank publishes the KIX effective exchange-rate
    index via `SEKKIX` on Swea, or BIS Trade-Weighted indices via
    existing `bis.py` connector).
  - SE mortgage rate (SCB MFI lending rates — no wrapper at Sprint
    W-SE scope; candidate: Riksbank / SCB household-lending tables).
- **Unblocks:** M4 SE persistence end-to-end.
- **Status:** OPEN.

### CAL-SE-M3 — SE M3 market-expectations overlays (Week 9 Sprint W-SE surfaced)

- **Priority:** LOW — M3 depends on L2 persisted overlays per
  country; analogous to CAL-105 (UK) / CAL-122 (JP) / CAL-132 (CA)
  / CAL-AU-M3 (AU) / CAL-CH-M3 (CH).
- **Trigger:** M3 spec §2 requires persisted NSS forwards + EXPINF
  rows per country; Sprint W-SE did not ship SE NSS or SE EXPINF
  overlays (Phase 2+ scope).
- **Scope:**
  - SE NSS overlay persistence (SGB tenor family via FRED
    `IRLTLT01SEM156N` long-end + Riksbank Swea SGB yield series;
    NSS fit via existing overlay module).
  - SE EXPINF overlay persistence — Sweden does issue inflation-
    linked government bonds (Statsobligationer SEK-denominated),
    so breakeven construction may be feasible via SGB tenor
    combined with inflation-linked bond yields on SCB / Riksbank.
    Fallback: 2 % CPIF target (already wired as
    `EXPECTED_INFLATION_CB_TARGET` proxy).
  - `MonetaryDbBackedInputsBuilder.build_m3_inputs` SE path.
- **Unblocks:** M3 SE persistence end-to-end.
- **Status:** OPEN.

### CAL-SE-BS-GDP — SE balance-sheet / GDP ratio wiring (Week 9 Sprint W-SE surfaced)

- **Priority:** LOW — closes the `SE_BS_GDP_PROXY_ZERO` flag on M1 SE.
- **Trigger:** Sprint W-SE C4 zero-seeded SE balance-sheet ratios
  because the Riksbank Monthly Statistical Bulletin + SCB nominal
  GDP are not wired at Sprint W-SE scope. Riksbank balance sheet
  expanded significantly during the 2015-2019 QE era (SGB purchases)
  and again during COVID-19 so the zero-seed is visibly inadequate
  for M1 balance-sheet signal contribution.
- **Scope:** Riksbank MSB monthly total assets series combined with
  SCB nominal GDP (or equivalent FRED `SWEGDPNAD2GDQ`-style series).
- **Unblocks:** M1 SE BS/GDP signal history populated (currently
  seeded as zeros → balance_sheet_signal contribution to M1 score
  is null).
- **Status:** OPEN.

### CAL-SE-CPI — SE CPI / CPIF YoY wrapper (Week 9 Sprint W-SE surfaced)

- **Priority:** MEDIUM — required input for M2 SE Taylor gap.
- **Trigger:** Sprint W-SE C4 `build_m2_se_inputs` scaffold lists
  SE CPI / CPIF YoY as one of three missing inputs; TE generic
  `fetch_indicator("SE", "inflation rate", ...)` should cover CPI
  but CPIF (the target measure) may require a dedicated path. SCB
  publishes monthly CPI + CPIF via the SCB Statistical Database
  (`api.scb.se`).
- **Scope:**
  - Probe TE generic indicator for SE CPI YoY cadence + coverage.
  - Probe SCB Statistical Database for CPIF YoY (the target measure
    since 2017 — more appropriate than CPI for Taylor-gap compute).
  - Wire `fetch_se_cpi_yoy` / `fetch_se_cpif_yoy` wrappers with
    source-drift guard (analogous to `fetch_ch_policy_rate`).
  - Consume in `build_m2_se_inputs` output.
- **Unblocks:** M2 SE inflation input; combined with CAL-SE-GAP +
  CAL-SE-INFL-FORECAST closes M2 SE.
- **Status:** OPEN.

### CAL-SE-INFL-FORECAST — SE inflation-forecast wrapper (Week 9 Sprint W-SE surfaced)

- **Priority:** LOW — nice-to-have for M2 SE compute; Riksbank 2 %
  CPIF-target serves as CB-target proxy until this lands.
- **Trigger:** Riksbank publishes quarterly Monetary Policy Report
  (MPR) forecast tables (HTML / PDF) but unwired at Sprint W-SE
  scope. M2 SE currently treats the 2 % CPIF target as the
  inflation-forecast proxy via `EXPECTED_INFLATION_CB_TARGET`.
- **Scope:**
  - Probe Riksbank MPR for scriptable forecast series.
  - Wire `fetch_se_inflation_forecast` (connector TBD — likely a
    HTML/PDF-scrape adapter on top of `RiksbankConnector`, or the
    Riksbank publishes machine-readable MPR appendices).
  - Consume in `build_m2_se_inputs` with new flag
    `SE_INFLATION_FORECAST_RIKSBANK_MPR` (replacing the
    `EXPECTED_INFLATION_CB_TARGET` proxy flag when available).
- **Unblocks:** M2 SE second-cycle inflation input; combined with
  CAL-SE-GAP + CAL-SE-CPI closes M2 SE.
- **Status:** OPEN.

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

### CAL-138 — daily_curves multi-country support (Phase 1 US-only expansion)

- **Priority:** HIGH — unblocks overlays/cost-of-capital cascades for 6 of 7 T1 countries (DE/PT/IT/ES/FR/NL)
- **Trigger:** Week 9 Day 4 production first natural fire (2026-04-22 07:00 WEST) revealed daily_curves pipeline still hardcoded `--country US` (Week 2 scope). Service file attempted `--all-t1` flag unsupported by CLI. Reverted to US-only safe state.
- **Current behavior:** `daily_curves` CLI rejects any country != "US" with EXIT_IO. Line 78 `src/sonar/pipelines/daily_curves.py`: `if country != "US": sys.exit(EXIT_IO)`. Code supports only FRED-sourced US yield curves via `run_us()`.
- **Required work:**
  1. Add country-aware connector dispatch in `daily_curves.py`:
     - US: FRED DGS/DFII series (existing `run_us`)
     - EA (DE/FR/IT/ES/NL/PT): ECB SDMX connector for sovereign yields
     - Individual Tier 1 countries: TE `fetch_indicator(country=<>, indicator="government bond 10y")` with maturity spectrum
  2. NSS fit validation per country (yield conventions differ EUR vs USD)
  3. Linker data per country (DE inflation-indexed vs US TIPS — different series)
  4. `--all-t1` flag added to CLI (mirror other 8 pipelines)
  5. Update `sonar-daily-curves.service` to use `--all-t1`
  6. Cassettes + live canaries for each new country
  7. Update test_daily_curves.py to cover multi-country paths
- **Impact if unresolved:** Overlays/cost-of-capital cascades persist US-only. 6 T1 countries lack ERP/CRP/rating-spread/expected-inflation for cycles integration.
- **Estimate:** 6-8h CC sprint scope (comparable to M1 country additions Week 9)
- **Related:** Blocks tomorrow 07:30 WEST `sonar-daily-overlays.service` from persisting DE/PT/IT/ES/FR/NL data.
