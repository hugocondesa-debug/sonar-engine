# Flags · Catálogo Canónico

Flags são tokens `UPPER_SNAKE_CASE` emitidos na coluna `flags TEXT` de qualquer tabela (CSV additive). Propagam-se up-stream: flag num input reduz `confidence` no output a jusante.

## Regras

- **Formato**: `UPPER_SNAKE_CASE`, ≤ 30 chars, ASCII only.
- **Storage**: CSV na coluna `flags` (ex: `NSS_REDUCED,STALE,XVAL_DRIFT`). Ordem lexicográfica ao persistir.
- **Additive**: nunca remover flags downstream; apenas adicionar.
- **Registo**: toda flag nova entra neste catálogo **antes** de qualquer spec a emitir.
- **Owner**: cada flag tem uma spec owner (a que a introduz); outras specs podem reemitir referenciando o mesmo token.
- **Confidence impact**: aditivo (−0.10 + −0.20 = −0.30), *floor* em 0.0, *ceiling* em 1.0, aplicado após cálculo base.

## Índice

- [§1 Overlays (L2)](#1-overlays-l2) — 29 flags
  - [1.1 NSS curves](#11-nss-curves) — 10
  - [1.2 ERP daily](#12-erp-daily) — 1
  - [1.3 CRP](#13-crp) — 6
  - [1.4 Rating-spread](#14-rating-spread) — 6
  - [1.5 Expected-inflation](#15-expected-inflation) — 6
- [§2 Indices (L3)](#2-indices-l3) — 42 flags
  - [2.1 Economic](#21-economic) — 7
  - [2.2 Credit](#22-credit) — 14
  - [2.3 Monetary](#23-monetary) — 10
  - [2.4 Financial](#24-financial) — 11
- [§3 Cycles (L4)](#3-cycles-l4) — 24 flags
  - [3.1 ECS](#31-ecs) — 6
  - [3.2 CCCS](#32-cccs) — 6
  - [3.3 MSC](#33-msc) — 6
  - [3.4 FCS](#34-fcs) — 6
- [§4 Generic](#4-generic) — 5 flags

**Total: 100 flags** (catálogo v0.1).

## 1. Overlays (L2)

### 1.1 NSS curves

| Flag | Owner spec | Trigger | Confidence impact |
|---|---|---|---|
| `COMPLEX_SHAPE` | `overlays/nss-curves` | Multi-hump (≥3 sign changes na 1ª derivada da curve) | −0.10 |
| `EM_COVERAGE` | `overlays/nss-curves` | Country tier 4 (CN, IN, BR, TR, MX, …) | cap at 0.70 |
| `EXTRAPOLATED` | `overlays/nss-curves` | Tenor fitted fora do range observado | −0.10 (nos tenores afetados) |
| `HIGH_RMSE` | `overlays/nss-curves` | `rmse_bps > 15` (Tier 1) ou `> 30` (Tier 4) | −0.20 |
| `NEG_FORWARD` | `overlays/nss-curves` | Forward rate `< −1%` em tenor > 1Y | −0.15 (partial output) |
| `NSS_FAIL` | `overlays/nss-curves` | `scipy.optimize` não convergiu; linear-interp fallback | cap at 0.50 |
| `NSS_REDUCED` | `overlays/nss-curves` | 6-8 obs → 4-param Nelson-Siegel fallback (drop `β3`, `λ2`) | cap at 0.75 |
| `REGIME_BREAK` | `overlays/nss-curves` | EM: `σ(Δy) > 3×` 5Y mean | cap at 0.60 |
| `STALE` | `overlays/nss-curves` | Input connector `>2` business days | −0.20 |
| `XVAL_DRIFT` | `overlays/nss-curves` | \|deviation vs BC-published\| > target | −0.10 |

### 1.2 ERP daily

| Flag | Owner spec | Trigger | Confidence impact |
|---|---|---|---|
| `ERP_METHOD_DIVERGENCE` | `overlays/erp-daily` | `erp_range_bps > 400` entre os 4 methods (DCF, Gordon, EY, CAPE) — sinal de regime transition ou dislocation | canonical: −0.10 |

### 1.3 CRP

| Flag | Owner spec | Trigger | Confidence impact |
|---|---|---|---|
| `CRP_BENCHMARK` | `overlays/crp` | Country é benchmark (DE para EUR world, US para USD world); `crp = 0` by construction | informational (none) |
| `CRP_BOND_CDS_BASIS` | `overlays/crp` | `|default_spread_sov_bps − cds_5y_bps| > 50` — bond/CDS divergence (liquidity, repo specialness, restructuring) | canonical: −0.05 |
| `CRP_DISTRESS` | `overlays/crp` | CDS `> 1500 bps` OR SOV spread `> 1500 bps` (Argentina-class distress) | cap at 0.60 |
| `CRP_NEG_SPREAD` | `overlays/crp` | Sovereign bond spread vs benchmark `< 0` (arbitrage / quote noise); clamp a 0 | −0.10 |
| `CRP_VOL_STANDARD` | `overlays/crp` | `vol_ratio` insufficient obs OR fora de `[1.2, 2.5]` → fallback para Damodaran standard `1.5x` | −0.05 |
| `LOCAL_CCY_SPREAD` | `overlays/crp` | Country sem liquid USD/EUR sovereign bonds; spread vs local-CB benchmark, contaminated por currency premium | −0.15 |

### 1.4 Rating-spread

| Flag | Owner spec | Trigger | Confidence impact |
|---|---|---|---|
| `RATING_CDS_DIVERGE` | `overlays/rating-spread` | `|rating_implied_bps − cds_5y_bps| / cds_5y_bps > 0.50` | −0.10 |
| `RATING_DEFAULT` | `overlays/rating-spread` | `consolidated_sonar_notch == 0` (D/SD) | cap at 0.40 |
| `RATING_OUTLOOK_UNCERTAIN` | `overlays/rating-spread` | Outlook `"developing"` em ≥1 agência | −0.05 |
| `RATING_SINGLE_AGENCY` | `overlays/rating-spread` | `agencies_available < 2` para `(country, date, rating_type)` | cap at 0.60 |
| `RATING_SPLIT` | `overlays/rating-spread` | Range de `notch_adjusted` entre agências ≥ 3 notches | −0.10 |
| `RATING_WATCH_UNCERTAIN` | `overlays/rating-spread` | Watch `"watch_developing"` em ≥1 agência | −0.05 |

### 1.5 Expected-inflation

| Flag | Owner spec | Trigger | Confidence impact |
|---|---|---|---|
| `ANCHOR_UNCOMPUTABLE` | `overlays/expected-inflation` | `5Y` ou `10Y` em falta → `5y5y` não derivável → `anchor_status=NULL` | canonical: −0.10 |
| `BEI_SHORT_SEASONALITY` | `overlays/expected-inflation` | `1Y` ou `2Y` BEI seasonally contaminated (short-dated breakeven caveat) | −0.10 (tenors afetados) |
| `INFLATION_METHOD_DIVERGENCE` | `overlays/expected-inflation` | `|BEI_10Y − SURVEY_10Y| > 100 bps` quando ambos disponíveis | canonical: −0.10 |
| `LINKER_UNAVAILABLE` | `overlays/expected-inflation` | Country sem linker market OR linker connector retorna < 3 tenors — DERIVED path | cap 0.70 no method row |
| `NO_TARGET` | `overlays/expected-inflation` | Country sem operative BC inflation target (CN, TR sem target credível, AR) — skip `anchor_status` | informational (none) |
| `SURVEY_MISSING` | `overlays/expected-inflation` | Survey esperado (SPF, Michigan, ECB SPF, Tankan) não publicado até `survey_freshness_max_days` | −0.20 no SURVEY row |

## 2. Indices (L3)

### 2.1 Economic

| Flag | Owner spec | Trigger | Confidence impact |
|---|---|---|---|
| `E1_GDP_GDI_DIVERGENCE` | `indices/economic/E1-activity` | `|GDP_yoy − GDI_yoy| > 1pp` annualized quando ambos disponíveis | −0.05 |
| `E1_PARTIAL_COMPONENTS` | `indices/economic/E1-activity` | `4 ≤ components_available < 6` (sub-componentes ausentes) | −0.10 por missing |
| `E2_PARTIAL_COMPONENTS` | `indices/economic/E2-leading` | `5 ≤ components_available < 8` (yield-curve miss, LEI absent non-US, OECD CLI stale) | −0.10 por missing |
| `E3_PARTIAL_COMPONENTS` | `indices/economic/E3-labor` | `6 ≤ components_available < 10` (JOLTS, Atlanta Fed, ECI, temp-help missing) | −0.10 por missing |
| `E3_SAHM_TRIGGERED` | `indices/economic/E3-labor` | `sahm_value ≥ 0.005` (0.5pp threshold Sahm 2019) | informational (none) |
| `E4_PARTIAL_COMPONENTS` | `indices/economic/E4-sentiment` | `6 ≤ components_available < 13` (expected for non-US por design) | −0.05 por missing |
| `E4_SENTIMENT_DIVERGENCE` | `indices/economic/E4-sentiment` | `|E4_score − E1_score| > 30 pts` (sentiment vs reality anomaly) | informational (none) |

### 2.2 Credit

| Flag | Owner spec | Trigger | Confidence impact |
|---|---|---|---|
| `CREDIT_BREAK` | `indices/credit/L1-credit-to-gdp-stock` | Quarterly jump > 50% (write-off, methodological break) | −0.15 |
| `CREDIT_F_FALLBACK` | `indices/credit/L1-credit-to-gdp-stock` | Q-series indisponível → fallback to bank-only F-series | cap 0.75 |
| `DSR_APPROX_O1` | `indices/credit/L4-dsr` | 1st-order formula (no maturity data) | −0.20 |
| `DSR_APPROX_O2` | `indices/credit/L4-dsr` | 2nd-order formula (no BIS direct DSR available) | −0.10 |
| `DSR_BIS_DIVERGE` | `indices/credit/L4-dsr` | Computed DSR diverges > 1pp from BIS-published | −0.10 |
| `DSR_DENOMINATOR_GDP` | `indices/credit/L4-dsr` | HH segment requested mas DHI indisponível → GDP fallback | −0.10 |
| `DSR_NEG_RATE` | `indices/credit/L4-dsr` | `lending_rate_pct < 0` (NIRP jurisdiction) | −0.05 |
| `GAP_DIVERGENT` | `indices/credit/L2-credit-to-gdp-gap` | HP vs Hamilton differ > 5pp; transição zone | −0.10 |
| `HAMILTON_FAIL` | `indices/credit/L2-credit-to-gdp-gap` | Hamilton regression rank-deficient | cap 0.50 |
| `HP_ENDPOINT_REVISION` | `indices/credit/L2-credit-to-gdp-gap` | One-sided vs two-sided differ > 3pp | −0.10 |
| `HP_FAIL` | `indices/credit/L2-credit-to-gdp-gap` | HP sparse solver non-convergent | cap 0.50 |
| `IMPULSE_OUTLIER` | `indices/credit/L3-credit-impulse` | Quarterly jump `|Δflow / gdp| > 10pp` (write-off / re-class) | −0.20 |
| `L1_VARIANT_MISMATCH` | `indices/credit/L3-credit-impulse` | L3 `series_variant` ≠ L1 variant para mesmo `(country, date)` | −0.10 |
| `STRUCTURAL_BREAK` | `indices/credit/L2-credit-to-gdp-gap` | Inherited `CREDIT_BREAK`; propagates HP instability (L2/L3) | −0.20 |

### 2.3 Monetary

| Flag | Owner spec | Trigger | Confidence impact |
|---|---|---|---|
| `FCI_EASING_SHOCK` | `indices/monetary/M4-fci` | FCI `Δ < −0.5σ` in a single day | informational (none) |
| `FCI_OUTLIER` | `indices/monetary/M4-fci` | Single component `|z| > 4` (sigma-tail) dominates FCI | −0.10 |
| `FCI_TIGHTENING_SHOCK` | `indices/monetary/M4-fci` | FCI `Δ > 0.5σ` in a single day | informational (none) |
| `OIS_PROXY` | `indices/monetary/M3-market-expectations` | OIS curve unavailable → uses sovereign short-end as proxy | −0.15 |
| `OUTPUT_GAP_DIVERGE` | `indices/monetary/M2-taylor-gaps` | IMF vs OECD vs CBO output gap differ > 1pp | −0.10 |
| `POLICY_SURPRISE_LARGE` | `indices/monetary/M3-market-expectations` | Market-implied policy path changed `> 25 bps` vs prev day | −0.10 |
| `R_STAR_PROXY` | `indices/monetary/M1-effective-rates` | Country sem HLW r*; uses EA/US proxy (shared M1/M2) | −0.10 |
| `SHADOW_DIVERGE` | `indices/monetary/M1-effective-rates` | Shadow rate (Wu-Xia vs Krippner) differ > 50 bps | −0.10 |
| `TAYLOR_VARIANT_DIVERGE` | `indices/monetary/M2-taylor-gaps` | Taylor variants (original/balanced/forward) differ > 50 bps | −0.10 |
| `ZLB_REGIME` | `indices/monetary/M2-taylor-gaps` | Policy rate `≤ 0.005` → shadow-rate substitution active | informational (none) |

### 2.4 Financial

| Flag | Owner spec | Trigger | Confidence impact |
|---|---|---|---|
| `AAII_PROXY` | `indices/financial/F4-positioning` | Non-US uses US AAII como global retail-sentiment proxy | −0.20 |
| `BREADTH_DIVERGENCE` | `indices/financial/F2-momentum` | `score > 70` AND `breadth_z < −0.5` (internal weakness) | informational (none) |
| `BREADTH_PROXY` | `indices/financial/F2-momentum` | Breadth source indisponível; EA/regional proxy substitute | −0.15 |
| `CROSS_ASSET_PARTIAL` | `indices/financial/F2-momentum` | `< 6/8` assets no cross-asset basket | −0.10 |
| `F1_CAPE_ONLY` | `indices/financial/F1-valuations` | Degenerate aggregation (only CAPE component available) | cap 0.55 |
| `F1_EXTREME_HIGH` | `indices/financial/F1-valuations` | `score_normalized > 95` sustained 5+ sessions | informational (none) |
| `F3_M4_DIVERGENCE` | `indices/financial/F3-risk-appetite` | `|F3 − inverted M4 FCI| > 20` (cross-cycle drift) | informational (none) |
| `F3_STRESS_EXTREME` | `indices/financial/F3-risk-appetite` | `VIX > 50` OR `HY_OAS > 1000 bps` | informational (none) |
| `F4_CONTRARIAN_EXTREME` | `indices/financial/F4-positioning` | `score > 85` OR `< 15` (contrarian signal threshold) | informational (none) |
| `MOVE_PROXY` | `indices/financial/F3-risk-appetite` | Non-US uses US MOVE como bond-vol proxy | −0.10 |
| `VOL_PROXY_GLOBAL` | `indices/financial/F3-risk-appetite` | Country sem local liquid vol index; US VIX como global proxy | −0.15 |

## 3. Cycles (L4)

### 3.1 ECS

| Flag | Owner spec | Trigger | Confidence impact |
|---|---|---|---|
| `E1_MISSING` | `cycles/economic-ecs` | Sub-index E1 Activity unavailable/low-confidence; Policy 1 re-weight active | cap 0.75 |
| `E2_MISSING` | `cycles/economic-ecs` | Sub-index E2 Leading unavailable; re-weight active | cap 0.75 |
| `E3_MISSING` | `cycles/economic-ecs` | Sub-index E3 Labor unavailable; re-weight active | cap 0.75 |
| `E4_MISSING` | `cycles/economic-ecs` | Sub-index E4 Sentiment unavailable; re-weight active | cap 0.75 |
| `STAGFLATION_INPUT_MISSING` | `cycles/economic-ecs` | `cpi_yoy` OR `unemployment_rate_12m_ago` unavailable → overlay suppressed | −0.05 |
| `STAGFLATION_OVERLAY_ACTIVE` | `cycles/economic-ecs` | All 3 conditions met: score < 55, CPI YoY > 3%, labor weakness (Sahm OR unemployment rising) | informational (none) |

### 3.2 CCCS

| Flag | Owner spec | Trigger | Confidence impact |
|---|---|---|---|
| `CCCS_BOOM_OVERLAY` | `cycles/credit-cccs` | Boom overlay triggered (score>70 + gap>10pp + DSR z>1.5) | informational (none) |
| `CS_MISSING` | `cycles/credit-cccs` | Credit Stress sub-component (aggregates L1/L2/L4) uncomputable; re-weight LC+MS | cap 0.75 |
| `F4_MARGIN_MISSING` | `cycles/credit-cccs` | F4 `margin_debt_gdp_pct IS NULL` (non-US); MS falls back a 100% F3 | −0.05 |
| `LC_MISSING` | `cycles/credit-cccs` | Lending Conditions sub-component uncomputable (L3 AND L4 missing); re-weight CS+MS | cap 0.75 |
| `MS_MISSING` | `cycles/credit-cccs` | Market Stress sub-component uncomputable (F3 missing); re-weight CS+LC | cap 0.75 |
| `QS_PLACEHOLDER` | `cycles/credit-cccs` | Qualitative Signal omitted em v0.1 (sempre emitida enquanto `CCCS_COMPOSITE_v0.1`) | cap 0.90 |

### 3.3 MSC

| Flag | Owner spec | Trigger | Confidence impact |
|---|---|---|---|
| `COMM_SIGNAL_MISSING` | `cycles/monetary-msc` | Communication Signal direct connectors (NLP, dissent, dot plot) unavailable — expected default em Phase 0-1 | cap 0.75 |
| `DILEMMA_NO_ECS` | `cycles/monetary-msc` | Dilemma pre-conditions met em MSC + anchor, mas ECS row indisponível → overlay suppressed | informational (none) |
| `M1_MISSING` | `cycles/monetary-msc` | M1 Effective rates unavailable; re-weight active | cap 0.75 |
| `M2_MISSING` | `cycles/monetary-msc` | M2 Taylor gaps unavailable; re-weight active | cap 0.75 |
| `M3_MISSING` | `cycles/monetary-msc` | M3 Market expectations unavailable; re-weight active | cap 0.75 |
| `M4_MISSING` | `cycles/monetary-msc` | M4 FCI unavailable; re-weight active | cap 0.75 |

### 3.4 FCS

| Flag | Owner spec | Trigger | Confidence impact |
|---|---|---|---|
| `BUBBLE_PROPERTY_FALLBACK` | `cycles/financial-fcs` | BIS property gap connector unavailable; F1 `property_gap_pp` used como fallback | −0.05 |
| `BUBBLE_PROPERTY_UNAVAILABLE` | `cycles/financial-fcs` | BIS primary + F1 fallback both missing → Bubble Warning condition 3 uncomputable; overlay default inactive | −0.05 |
| `F1_MISSING` | `cycles/financial-fcs` | F1 Valuations unavailable; Policy 1 re-weight active | cap 0.75 |
| `F2_MISSING` | `cycles/financial-fcs` | F2 Momentum unavailable; re-weight active | cap 0.75 |
| `F3_MISSING` | `cycles/financial-fcs` | F3 Risk appetite unavailable; re-weight active | cap 0.75 |
| `F4_COVERAGE_SPARSE` | `cycles/financial-fcs` | F4 ausente (Tier 2-3 best-effort) OR não esperado (Tier 4 EM) — FCS = F1+F2+F3 re-weighted | cap 0.80 (Tier 2-3) / 0.75 (Tier 4) |

## 4. Generic

Flags transversais emitidas por múltiplas specs — contrato partilhado, não propriedade de um módulo específico.

| Flag | Owner spec | Trigger | Confidence impact |
|---|---|---|---|
| `CALIBRATION_STALE` | generic | Calibration table (ex: rating-to-spread, PT-EA differential) older than `freshness_threshold` (default 30 dias) | −0.15 |
| `INSUFFICIENT_HISTORY` | generic | Rolling lookback window tem menos observações do que mínimo requerido pela spec (z-score under-determined, baseline estatisticamente frágil) | cap at 0.65 |
| `OVERLAY_MISS` | generic | Consumer reads overlay X for `(country, date)` mas row não existe | cap 0.60 (no consumer) |
| `REGIME_BOOTSTRAP` | generic | First row per `(country, cycle)` — sem prev state; hysteresis suspended, regime derivado do raw band | informational (none) |
| `REGIME_HYSTERESIS_HOLD` | generic | Regime transition attempted mas rejected por anti-whipsaw (`|Δscore| ≤ 5` OR persistence `< 3 BD`) | −0.05 |

## Convenção de propagação

Quando uma spec consome output flagged, a sua própria output:

1. **Inherits** as flags do input principal (ex: `overlays/erp-daily` consumindo `nss-curves` com `STALE` → `erp-daily` output carrega `STALE,RISK_FREE_STALE`).
2. **Adiciona** flags próprias do próprio cálculo.
3. **Não** sobrescreve nem remove flags do input.

## Futuras (a registar antes da implementação)

Reservadas — não emitir ainda. Promover ao catálogo principal quando owner spec existir + consumer confirmado:

- `BACKFILLED` — row produzida por `pipelines/backfill-strategy`, não daily forward-run.

*`SURVEY_MISSING` e `LINKER_UNAVAILABLE` foram promovidas para o catálogo principal em P3a (owner: `overlays/expected-inflation`).*
