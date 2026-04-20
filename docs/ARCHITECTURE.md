# SONAR v2 — Architecture

**Status**: v2.0 · Phase 1 Week 3.5 em curso — 5 overlays L2 live (NSS/rating-spread/expected-inflation/CRP/ERP), L3 indices scaffold + E2/M3 subsets, L6 `daily_cost_of_capital` pipeline live.
**Maintainer**: Hugo · 7365 Capital
**Última revisão arquitetural**: 2026-04-20

## 1. Propósito e escopo

SONAR é motor analítico de ciclos macroeconómicos e overlays quantitativos para 7365 Capital. Computa estado cíclico (quatro ciclos agregados em scores compostos), primitivos quantitativos (yield curves NSS, ERP, CRP, rating-spread, expected inflation) e integration cross-country (matriz 4-way, cost-of-capital) num pipeline batch diário.

**Portugal-aware by design**: cada overlay e ciclo tem derivação PT first-class. PT yield curve via IGCP; PT CRP daily; PT expected inflation via EA + historical differential synthesis (ausência de linker market doméstico); PT rating consolidado cross-agency; fixtures historical PT (2007 CRP ~20 bps → 2012 peak ~1500 bps → 2026 ~54 bps; 2009 DSR peak; 2012 CCCS distress) são canonical validation anchors.

**Sucessor de v1**: v1 (2024-2026) arquivado por debt técnico severo — 434 indicadores em 19 connectors sem spec formal, schema drift cross-ciclo, confidence não uniforme. v2 é **greenfield rewrite** com specs-first discipline e 9-layer architecture explícita.

**Escopo v2 Phase 0-1** (horizonte actual):
- Specs L0-L8 merged em `docs/specs/` — 5 overlays + 16 indices + 4 cycles + conventions + pipelines stubs.
- Implementação Phase 1 Week 3.5 delivered: L0 connectors (FRED/ECB-SDW/Bundesbank/TE/FMP/Shiller/Damodaran/multpl/spdji/FactSet/Yardeni); L1 schema (migrations 001-008); L2 overlays (NSS/rating-spread/expected-inflation/CRP/ERP 4-method); L3 indices scaffold + E2/M3 subsets; L6 `daily_cost_of_capital` pipeline.
- SQLite-first; Postgres é Phase 2+ (§10).

## 2. Princípios arquiteturais

Não-negociáveis. Spec, PR ou código que os violar é rejeitado.

### 2.1 Compute, don't consume

Overlays e indices são **calculados localmente** a partir de raw data. Nunca copy-paste de outputs agregados externos.

| Anti-pattern (consume) | Pattern (compute) |
|---|---|
| Damodaran ERP mensal publicado | ERP daily via DCF + Gordon + EY + CAPE (median canonical) |
| Bloomberg CRP | CRP via CDS + σ_equity/σ_bond vol ratio |
| Bundesbank Svensson fitted curves | NSS fit próprio (Bundesbank usado como cross-validation target <5 bps) |
| Shiller CAPE published | Download `ie_data.xls`, compute CAPE rolling 10Y real earnings |

Fontes "published" servem como **cross-validation contínua** (`XVAL_DRIFT` flag quando deviation excede target), não input primário.

### 2.2 Specs-first

Cada módulo em `sonar/` tem um spec em `docs/specs/` **escrito antes** do código. Spec declara propósito, inputs/outputs tipados, algoritmo com pseudocódigo, dependencies, edge cases, test fixtures, storage DDL, consumers, references. Template canónico em `docs/specs/template.md` (10 secções mandatory + §11 Non-requirements opcional). Toda spec referencia `docs/specs/conventions/` e nunca redefine contratos partilhados.

Mudança algorítmica → bump `methodology_version` (esquema em `conventions/methodology-versions.md`) **antes** de tocar código.

### 2.3 Frozen contracts

`docs/specs/conventions/` é fonte partilhada de verdade para specs e código. Contém quatro ficheiros:

- **`flags.md`** — catálogo de 100 flags `UPPER_SNAKE_CASE` com owner, trigger, confidence impact. Nenhuma spec emite token não catalogado.
- **`exceptions.md`** — hierarquia `SonarError` com 15 classes (1 root, 4 branches abstract, 10 leaves). Nenhuma spec redefine nome de exception.
- **`units.md`** — decimal em storage/compute (yields = `0.0415`, não `4.15`); bps como `int`; datas UTC storage + Europe/Lisbon scheduling; ISO 8601.
- **`methodology-versions.md`** — formato `{MODULE}_{VARIANT?}_v{MAJOR}.{MINOR}` com bump rules (MINOR = weights/thresholds, MAJOR = schema/formula breaking → full rebackfill).

Alteração destes ficheiros é breaking change cross-spec — PR dedicado, review explícito.

### 2.4 Placeholders declarados

Todo threshold empiricamente ungrounded (weights, regime bands, calibration intervals) é marcado:

> *placeholder — recalibrate after Nm of production data*

`N` entre 12m (overlays) e 60m (credit phase bands per country). ~40 placeholders inventariados. Backlog de calibração consolidado em `docs/backlog/calibration-tasks.md` (a criar em Bloco 8 Phase 0); GitHub issues abertos ad-hoc quando item entra em execução.

### 2.5 Portugal-aware

PT é first-class em cada camada:
- L0: IGCP, BPStat, INE como Tier 1 sources.
- L2: PT CRP computed (não rating-implied quando liquidity permite); PT expected inflation via EA + differential (no domestic linker); PT NSS via IGCP + ECB SDW cross-check.
- L4: PT tier 3 em coverage mas fixtures historical dedicated.
- L7: PT CRP trajectory é flagship editorial angle.

## 3. As 9 camadas

Stack layered estritamente hierárquico; dados fluem L0 → L8.

```
┌─────────────────────────────────────────────────────────────────────┐
│ L8  pipelines/    Orchestration + schedule + backfill strategy      │
├─────────────────────────────────────────────────────────────────────┤
│ L7  outputs/      CLI, API, editorial, alerts, dashboard            │
├─────────────────────────────────────────────────────────────────────┤
│ L6  integration/  Matriz 4-way, diagnostics, cost-of-capital        │
├─────────────────────────────────────────────────────────────────────┤
│ L5  regimes/      Cenários cruzados (Stagflation Trap, Bubble, ...) │ ← Phase 2+
├─────────────────────────────────────────────────────────────────────┤
│ L4  cycles/       ECS, CCCS, MSC, FCS (composite + regime)          │
├─────────────────────────────────────────────────────────────────────┤
│ L3  indices/      E1-4, L1-4, M1-4, F1-4 (sub-índices normalizados) │
├─────────────────────────────────────────────────────────────────────┤
│ L2  overlays/     NSS, ERP, CRP, rating-spread, expected-inflation  │
├─────────────────────────────────────────────────────────────────────┤
│ L1  db/           SQLite (v0.1) · tabelas + Alembic migrations      │
├─────────────────────────────────────────────────────────────────────┤
│ L0  connectors/   FRED, ECB SDW, BIS, IGCP, Shiller, WGB CDS, …     │
└─────────────────────────────────────────────────────────────────────┘
```

### L0 · connectors/

**Propósito**: adapters para data sources externas (APIs, scrapes HTML/PDF, downloads XLS/CSV). Um connector por source ou por família de endpoints coesa.

**I/O**: parâmetros typed (`country_code`, date range, series id) → dict / DataFrame com raw observations + provenance metadata (source, fetched_at, data_as_of, confidence, warnings).

**Exemplos**: `treasury_gov`, `bundesbank`, `boe_yieldcurves`, `mof_japan`, `ecb_sdw`, `igcp`, `bpstat`, `ine`, `shiller`, `wgb_cds`, `factset_insight`, `spdji_buyback`, `fred`, `bis`, rating agency connectors (`sp_ratings`, `moodys_ratings`, `fitch_ratings`, `dbrs_ratings`).

**Estado**: base abstract class `BaseConnector` é primeiro deliverable Phase 1. Data source plans em `docs/data_sources/` (4 ficheiros) são o roadmap — ~50-60 connectors catalogados.

### L1 · db/

**Propósito**: persistência. Único ponto de read/write de todas as camadas downstream. Schema é source of truth — código segue schema, não o contrário.

**I/O**: tabelas SQL com `UNIQUE(country_code, date, methodology_version)` ou equivalente. Foreign keys onde sibling tables partilham correlation UUID (ex: `yield_curves_zero.fit_id → yield_curves_spot.fit_id`). Toda row carrega `methodology_version`, `confidence`, `flags`, `created_at`.

**Exemplos** (especificados nos specs L2-L4): `yield_curves_spot/zero/forwards/real`, `erp_dcf/gordon/ey/cape/canonical`, `economic_cycle_scores`, `credit_cycle_scores`, `monetary_cycle_scores`, `financial_cycle_scores`. ~60 tabelas estimadas quando Phase 1-3 completa.

**Estado**: SQLite v0.1 + SQLAlchemy 2.0 + Alembic. Postgres migration é Phase 2+ (§10).

### L2 · overlays/

**Propósito**: calculadoras quantitativas universais, reutilizáveis cross-cycle. Output contínuo em unidades naturais. Não classificam — produzem números.

**I/O**: connectors (via L1 raw tables) + eventualmente outputs de outros overlays (NSS alimenta ERP risk-free). Uma ou mais tabelas por overlay; `{slug}_id` UUID correlaciona sibling rows.

**5 overlays especificados** — ver §5.

**Estado**: specs merged (P3). Implementação Phase 1 (NSS primeiro, end-to-end).

### L3 · indices/

**Propósito**: síntese ponderada por sub-dimensão de um ciclo. Output normalizado para `[0, 100]` via z-score rescaled — consumível por L4 composite scores.

**I/O**: overlays (L2) + connectors directos (via L1). Exemplo: `E2-leading` consome yield-curve slope de NSS + LEI/OECD CLI de connectors. Output tipado: `score_normalized ∈ [0, 100]`, `score_raw`, `components_json`, `confidence`, `flags`.

**16 indices especificados** (4 por ciclo) — ver §5.

**Lookback window per cycle** — cada README em `docs/specs/indices/` declara a janela canónica e fallback Tier 4:

| Cycle | Canonical | Tier 4 fallback | Rationale |
|---|---|---|---|
| Economic | 10Y | 7Y | Cap 15.4 default; cycle médio + buffer |
| Credit | 20Y | 15Y floor | 80 quarters, BIS WS_TC standard |
| Financial | 20Y | 10Y | múltiplos cycles + bubble episodes (1998, 2007, 2021) |
| Monetary | 30Y | 15Y | cobre regime ZLB 2008-2022 (shadow rate, Taylor gap) |

Monetary 30Y é deliberadamente mais longo — ZLB 2008-2022 teve shadow rate ECB −7.56% (2020) e Taylor gap Fed −3.5pp (2022); window curta comprimiria variance dessa cauda. F1 CAPE adicionalmente computa percentile rank 40Y como diagnostic (persistido em `components_json`).

**Estado**: specs merged (P4). Implementação Phase 1-2.

### L4 · cycles/

**Propósito**: classificadores de regime macroeconómico. Consomem indices L3 do próprio ciclo + cross-cycle peers + overlays selectos. Output: score composite contínuo + regime discreto com anti-whipsaw hysteresis.

**I/O**: 4 indices do próprio cycle + cross-cycle dependencies (§6). Output: `score_0_100`, `regime` (enum), `regime_persistence_days`, component scores, effective weights (reflectem re-weighting Policy 1), overlay booleans (Stagflation, Boom, Dilemma, Bubble Warning), `confidence`, `flags`.

**4 cycles especificados** — ver §5.

**Regime transition rule** (universal): `|Δscore| > 5` AND `persistence ≥ 3 business days`. Flags genéricas partilhadas: `REGIME_BOOTSTRAP` (primeira row sem prev state), `REGIME_HYSTERESIS_HOLD` (transição atempted mas rejeitada).

**Estado**: specs merged (P5). Implementação Phase 2.

### L5 · regimes/

**Propósito**: cenários cruzados (dois ou mais ciclos em configurações específicas) reificados como entidades com história, transition probabilities, duration distributions. Exemplos conceptuais: *Stagflation Trap* (ECS RECESSION + CPI >3% + MSC TIGHT), *Bubble Warning medium-term* (FCS EUPHORIA + BIS credit gap >10pp + property gap >20%).

**I/O planeado**: row por `(country, date, regime_scenario)` com `active: bool`, `intensity`, `duration_days`, `transition_prob_json`.

**Estado**: **Phase 2+**. Em v0.1 os overlays equivalentes vivem como colunas booleanas nas tabelas L4 (`stagflation_overlay_active`, `boom_overlay_active`, `dilemma_overlay_active`, `bubble_warning_active`). Sem tabela L5 separada.

### L6 · integration/

**Propósito**: composição cross-country e cross-cycle. Outputs não-single-cycle, não-single-country.

**I/O planeado**:
- `matriz-4way` — classificação canonical pattern (ECS × CCCS × MSC × FCS → 16 estados canónicos + outliers).
- `diagnostics/` — bubble-detection composite, minsky-fragility, real-estate-cycle, risk-appetite-regime.
- `cost-of-capital` — composite `cost_of_equity_country = risk_free_country + β·ERP_mature + CRP_country`.

**Estado**: `docs/specs/integration/` vazio. Specs Phase 2+.

### L7 · outputs/

**Propósito**: consumo humano + máquina. CLI (Typer), API (FastAPI), editorial pipeline (angle detection + briefing generator + markdown templates), alerts (threshold breach, regime shift), dashboard.

**I/O**: leitura via L1 (never recompute); scatter para humanos (editorial briefings, alerts email/Telegram) e máquinas (JSON API).

**Estado**: CLI + JSON exporters são Phase 2. Editorial pipeline Phase 3. Dashboard Phase 4+ (§10).

### L8 · pipelines/

**Propósito**: orchestration. Coordenar execução ordenada L0 → L6 por `(country, date)`, respeitar dependency DAG, isolar falhas per country, persistir atomicamente.

**6 pipelines stub**:
- `daily-curves` (09:00 Lisbon) · NSS fit all countries.
- `daily-overlays` (09:30) · ERP, CRP, rating-spread, expected-inflation.
- `daily-indices` (10:00) · 16 indices (paralelizáveis per cycle).
- `daily-cycles` (10:15) · 4 composite scores + overlays booleans.
- `weekly-integration` (Sun 11:00) · rolling recomputes (5Y vol ratios, PT-EA differential, transition probabilities).
- `backfill-strategy` (on-demand) · historical boot + rebackfill on MAJOR methodology bump.

**Estado**: stubs em `docs/specs/pipelines/`. Detailed specs Phase 2+ (requer decisão orchestrator: APScheduler vs Prefect — `BRIEF_FOR_DEBATE.md` §3).

## 4. Distinções críticas

Três conceitos fáceis de confundir. Definições completas em `docs/GLOSSARY.md` (Bloco futuro); aqui o mínimo para não errar na stack.

### Overlay (L2) vs Index (L3) vs Cycle (L4)

| | Overlay (L2) | Index (L3) | Cycle (L4) |
|---|---|---|---|
| **Tipo de output** | Contínuo em unidades naturais (yield decimal, bps, inflation decimal) | Normalizado `[0, 100]` via z-score rescaled | `score_0_100` contínuo + regime discreto (enum) |
| **Escopo** | Universal, reutilizável cross-cycle | Sub-dimensão de UM ciclo específico | Composite de 4 indices do próprio ciclo + cross-cycle deps |
| **Exemplo** | NSS yield curve fitted | E2 Leading (yield slope + LEI + PMIs + credit spreads) | ECS composite + regime `EXPANSION/PEAK_ZONE/…` |
| **Consumido por** | Indices, cycles, integration, outputs | Cycles | Integration, outputs, editorial |
| **Classifica?** | Não — produz números | Não — normaliza | Sim — regime discreto + overlay booleans |
| **Transparência** | Algorithmic (NSS fit, DCF root-find) | Aggregation + normalization | Weighted sum + hysteresis state machine |

### Regime (L5) cross-cycle ≠ overlay

"Overlay" tem duas acepções no SONAR — ambiguidade herdada dos manuais v1:

1. **Overlay layer (L2)** — calculadora quantitativa (NSS, ERP, CRP, rating-spread, expected-inflation).
2. **Cycle overlay** (coluna booleana em L4) — condição activa num ciclo (Stagflation, Boom, Dilemma, Bubble Warning). Em v0.1 é coluna. Em Phase 2+ migra para **L5 regimes** (cenários cruzados com história).

Regra: quando lêres "overlay" no código, vê o namespace. `overlays/nss-curves` é L2. `stagflation_overlay_active` column é semântica L4 (Phase 0-1) / L5 (Phase 2+).

## 5. Inventário actual

Specs merged em main · 3 commits Phase 0 (sessão 2026-04-18): `97ee9ae` conventions + pipelines stubs · `1a66686` overlays + indices + cycles · `95744d3` template + README 9-layer.

### Overlays (L2) · 5 specs

| Slug | Methodology | Spec |
|---|---|---|
| nss-curves | Nelson-Siegel-Svensson 6-param (4-param fallback) | [specs/overlays/nss-curves.md](specs/overlays/nss-curves.md) |
| erp-daily | 4 methods paralelos → median canonical | [specs/overlays/erp-daily.md](specs/overlays/erp-daily.md) |
| crp | CDS → sovereign spread → rating-implied (hierarchy) × vol_ratio | [specs/overlays/crp.md](specs/overlays/crp.md) |
| rating-spread | Cross-agency consolidation → SONAR scale 0-21 → calibrated spread | [specs/overlays/rating-spread.md](specs/overlays/rating-spread.md) |
| expected-inflation | BEI → SWAP → DERIVED (PT path) → SURVEY (hierarchy) | [specs/overlays/expected-inflation.md](specs/overlays/expected-inflation.md) |

### Indices (L3) · 16 specs (4 por ciclo)

| Ciclo | Indices | Dir |
|---|---|---|
| Economic | E1-activity · E2-leading · E3-labor · E4-sentiment | [specs/indices/economic/](specs/indices/economic/) |
| Credit | L1-credit-to-gdp-stock · L2-credit-to-gdp-gap · L3-credit-impulse · L4-dsr | [specs/indices/credit/](specs/indices/credit/) |
| Monetary | M1-effective-rates · M2-taylor-gaps · M3-market-expectations · M4-fci | [specs/indices/monetary/](specs/indices/monetary/) |
| Financial | F1-valuations · F2-momentum · F3-risk-appetite · F4-positioning | [specs/indices/financial/](specs/indices/financial/) |

### Cycles (L4) · 4 specs

| Slug | Composite formula (v0.1) | Spec |
|---|---|---|
| economic-ecs | `0.35·E1 + 0.25·E2 + 0.25·E3 + 0.15·E4` | [specs/cycles/economic-ecs.md](specs/cycles/economic-ecs.md) |
| credit-cccs | `0.44·CS + 0.33·LC + 0.22·MS` (QS omitted; CS/LC/MS aggregate L1-L4 + F3/F4) | [specs/cycles/credit-cccs.md](specs/cycles/credit-cccs.md) |
| monetary-msc | `0.30·M1 + 0.15·M2 + 0.25·M3 + 0.20·M4 + 0.10·CS` (CS direct, not L3) | [specs/cycles/monetary-msc.md](specs/cycles/monetary-msc.md) |
| financial-fcs | `0.30·F1 + 0.25·F2 + 0.25·F3 + 0.20·F4` (F4 tier-conditional) | [specs/cycles/financial-fcs.md](specs/cycles/financial-fcs.md) |

Pesos são **placeholders** — recalibrate após 24m + walk-forward backtest (NBER/CEPR para ECS; Pagan-Sossounov para FCS; transition frequencies para MSC/CCCS).

## 6. Dependências entre camadas

### DAG canónico (cross-cycle focado)

```
indices L3 ──► cycles L4

  E1 E2 E3 E4
     └──┬───┘
        ▼
       ECS ─────────────────────────────────┐
                                            ▼
                               MSC  (lê ECS para Dilemma trigger)
  M1 M2 M3 M4 ─────────────────► MSC        ▲
  CS direct (connectors) ───────► MSC ──────┘

  credit/L1 credit/L2 credit/L3 credit/L4
               └────────┬────────┘
                        ▼
                       CCCS ◄──── F3 + F4_margin  (✱ cross-cycle, MS component 22%)

  F1 F2 F3 F4
       └──┬──┘
          ▼
         FCS ◄──── credit/L2-credit-to-gdp-gap   (✱ Bubble Warning condition 2)
           ▲
           └────── M4.score         (✱ F3↔M4 divergence diagnostic)
```

Setas `✱` representam cross-cycle dependencies.

### Call-outs

**L4 não é puramente paralelo** — três cross-cycle dependencies:

1. **CCCS ← `indices/financial/F3` + `indices/financial/F4`**
   Componente MS (Market Stress, 22% do composite) = `0.70·F3 + 0.30·F4_margin_debt`. CCCS não corre antes dos F indices estarem persistidos. Pipeline `daily-cycles` enforces ordering.

2. **MSC ← ECS via Dilemma overlay trigger**
   Dilemma overlay triggers com `MSC > 60 + expected-inflation anchor drifting + ECS < 55`. Se ECS row faltar para `(country, date)`, MSC emite `DILEMMA_NO_ECS` flag e suppressa overlay (não falha o cycle). MSC-spec tolerante mas downstream editorial degraded.

3. **FCS ← L2 credit_gap + M4 FCI**
   Bubble Warning overlay (v0.1 trigger: `FCS > 70 + L2.credit_gap > 10pp + property_gap > 20%`). Cross-cycle read de `indices/credit/L2-credit-to-gdp-gap` (sub-índice, não confundir com camada L2 overlays). M4 FCI consumido como diagnostic — ver call-out seguinte.

**F3 ↔ M4 overlap conceptual**
`indices/monetary/M4-fci` e `indices/financial/F3-risk-appetite` consomem inputs parcialmente sobrepostos (NFCI Chicago Fed, CISS ECB, VIX). v0.1 **lêem independentemente** com 20Y z-score próprio; FCS emite `F3_M4_DIVERGENCE` como observability signal. FCS computa `f3_m4_divergence = F3_score − (100 − M4_score)` como diagnostic column; `F3_M4_DIVERGENCE` flag quando `|divergence| > 15`. v0.2 candidate: reconciliar para shared source com single normalization.

**CS de MSC consumido directamente, não via L3**
Communication Signal (dot plot deviation, Fed/ECB/BoE dissent count, NLP hawkish score de statements) é output qualitativo **não normalizável** para um "sub-índice L3" coerente com M1-M4. Consumido directamente por `cycles/monetary-msc` via connectors dedicated (`connectors/central_bank_nlp`, `connectors/fed_dissent`, `connectors/dot_plot` — não speced Phase 1). Em Phase 0-1 `COMM_SIGNAL_MISSING` é expected default; MSC aplica Policy 1 re-weight sem bloquear.

**F4 conditional por tier**
Positioning data (AAII, CFTC COT, fund flows, margin debt) é sparse fora US. `cycles/financial-fcs` aplica tier policy:

| Tier | Países | F4 handling |
|---|---|---|
| 1 | US, DE, UK, JP | F4 required; missing → raise `InsufficientDataError` |
| 2-3 | FR, IT, ES, CA, AU, PT, IE, NL, SE, CH | best-effort; missing → re-weight F1+F2+F3, flag `F4_COVERAGE_SPARSE`, cap confidence 0.80 |
| 4 EM | CN, IN, BR, TR, MX, ZA, ID | F4 ignored mesmo se row exists; cap 0.75 |

## 7. Padrões arquiteturais emergidos

Convergência observada durante specs P3-P5. Detalhe em `docs/specs/conventions/patterns.md` (futuro).

**Parallel equals** — múltiplos methods com standing epistémico igual. Canonical = agregação estatística + range como uncertainty signal.
Exemplo: `erp-daily` → 4 methods (DCF, Gordon, EY, CAPE), canonical = `median_bps`, `range_bps` exposto, `ERP_METHOD_DIVERGENCE` flag quando range > 400 bps.

**Hierarchy best-of** — methods com quality gradient conhecido. Canonical = primeiro disponível na ordem; restantes persistidos lado-a-lado para audit.
Exemplo: `crp` → CDS > sovereign spread > rating-implied. `expected-inflation` → BEI > SWAP > DERIVED (PT path) > SURVEY.

**Versioning per-table** — múltiplas tabelas relacionadas com cadências de bump divergentes.
Exemplo: `rating-spread` emite 3 `methodology_version` distintas — `RATING_AGENCY_v0.1` (per-agency raw, bump on lookup table change), `RATING_SPREAD_v0.1` (consolidated, bump on consolidation rule change), `RATING_CALIBRATION_v0.1` (global notch→spread, quarterly recalibration from Moody's + ICE BofA).

**Normalization convergente** (não padrão formal até P4; emergiu convergentemente nas 4 especificações de indices L3, depois adoptado por cycles L4):

```text
score_0_100 = clip(50 + 16.67·z, 0, 100)
```

`z` = z-score rolling por country. Range natural `[-3σ, +3σ]` → `[0, 100]`. Indices L3 todos emitem nesta escala → cycles L4 aplicam weighted sum directo sem re-normalization.

## 8. Fail-mode cross-cycle

Uniforme em todos os 4 cycles L4 (Policy 1, aprovada P5):

- Sub-index unavailable → `{INDEX}_MISSING` flag, re-weight proporcional dos restantes: `w'_i = w_i / Σ_{j ∈ available} w_j`.
- **Require ≥ 3 of 4 indices disponíveis**. Menos: cycle raises `InsufficientDataError` (row não persistida, operator alertado).
- **Confidence cap 0.75** sempre que re-weight activo.

Exemplo ECS com E4 missing: pesos `(0.35, 0.25, 0.25, 0.0)` → normalizados `(0.412, 0.294, 0.294, 0.0)`. Confidence base `min(e_i.confidence) · 3/4` capped at 0.75.

## 9. Pipeline order canonical

Resumo. Detalhe operacional em `docs/specs/pipelines/` (6 stubs) e `docs/specs/pipelines/README.md` (master schedule).

```
06:00  Connector refresh (morning batch — eurodata, asia overnight)
09:00  daily-curves        · NSS fit all countries (paralelo per-country)
09:30  daily-overlays      · ERP, CRP, rating-spread, expected-inflation
10:00  daily-indices       · 16 indices (paralelizáveis entre ciclos)
10:15  daily-cycles        · ECS → MSC · CCCS (needs F3+F4) · FCS (needs L2+M4)
11:00  (Sun only) weekly-integration · rolling recomputes
```

**Paralelização possível** onde sem dependência:
- L2: NSS primeiro (provides risk-free); ERP/CRP/rating-spread/exp-inflation paralelos pós-NSS.
- L3: 16 indices paralelizáveis cross-cycle (credit tem dep intra `L1 → L2 → L3`).
- L4: ECS independent. MSC precisa ECS. CCCS espera daily-indices. FCS espera daily-indices + M4 row (daily-cycles).

`daily-cycles` tem ordering interno:

```
ECS (independent)
 └─► MSC (lê ECS para Dilemma)
CCCS (aguarda F3 + F4 de daily-indices)
FCS (aguarda L2 de daily-indices + M4 de daily-cycles)
```

## 10. Out-of-scope (Phase 2+ ou posterior)

Decisões explícitas de não fazer agora. Evita scope creep e mantém Phase 0-1 tractable.

**Phase 2+**:
- **Regimes (L5)** como cenários cruzados com tabelas próprias. v0.1 mantém overlays booleans em colunas L4. Migração exige decisão sobre transition probability model (Markov simples vs HMM vs estimativas empíricas).
- **Integration (L6)** full. `matriz-4way`, `diagnostics/*`, `cost-of-capital` têm directório em `docs/specs/integration/` vazio. Arranca após L4 estável em produção.
- **Dashboard (L7)**. Streamlit MVP é Phase 3+. React/TypeScript production Phase 4+. Enquanto isso: CLI + JSON exporters.

**Phase 3+**:
- **Postgres migration**. SQLite é MVP v0.1 e suporta single-user research + pipeline diário < 10 GB. Migração justificada quando (a) multi-user, (b) concurrent writes, (c) DB > 30 GB, ou (d) deployment cloud 24/7.

**Infraestrutura externa**:
- **MCP server exposure**. Cloudflared tunnel para expor endpoints SONAR ao Claude/ChatGPT como context provider foi exploratório em v1; desactivado em v2 Phase 0 até L7 outputs implementado. Reactivação condicional a autorização explícita.
- **Wiki público**. Repo privado em Phase 0-1 enquanto licensing (ver `docs/BRIEF_FOR_DEBATE.md` §5) não decidido. Wiki conteúdo conceptual pode abrir depois sem expor código.

## 11. Decisões formais e governança

Decisões arquiteturais formais são registadas em `docs/adr/` (Architecture Decision Records, template e primeiros ADRs criados no Bloco 5 Phase 0). Governança operacional (workflow, documentação, dados, colaboração AI) em `docs/governance/` (Bloco 6 Phase 0). Template de spec em `docs/specs/template.md`.

---

*Arquitectura v2.0 · Phase 0 specs merged · revisão completa 2026-04-18 post-P5.*
*Fonte de verdade operacional: `docs/specs/`. Resumo executivo de alto nível: Claude chat project context (SESSION_CONTEXT.md), externo ao repo.*
