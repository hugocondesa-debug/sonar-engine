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

- **Priority:** MEDIUM
- **Trigger:** Week 3 CRP (vol_ratio country-specific branch)
- **Scope:** Validate `twelvedata` (equity index daily 5Y history,
  Tier/licensing review) and `yfinance` (bond ETF price series, scrape
  stability, ToS). Alternatives if both fail: (a) TE equity history +
  derived bond vol via sovereign NSS yield changes; (b) Damodaran
  standard 1.5 permanent.
- **Blocker for:** CRP country-specific vol_ratio Week 3+; CRP ships
  with `damodaran_standard=1.5` interim.

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

## Não-categorizado por horizonte

Zero items. Todos os 20 têm horizonte explícito no spec.

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
