# SONAR v2 — Glossary

**Status**: v2.0 · Phase 0 Bloco C em curso
**Última revisão**: 2026-04-18

Taxonomia canónica do SONAR v2. Termos técnicos (identifiers EN) com definição breve em PT-PT. Referenciável por specs, ADRs, governance e Claude Code. Live document — novos termos entram quando specs ou ADRs os introduzem. Nunca duplicar conteúdo das specs: aqui é definição de 2-4 linhas + ponteiro.

## 1. Como ler este glossary

- Cada entrada: termo EN como header, definição PT, ponteiro para fonte canónica.
- Termos com múltiplos nomes: entrada canónica + redirect (`### Ciclo → ver Cycle`).
- Organização híbrida: secções temáticas (§4-§13); alfabético dentro de cada secção.
- Índice alfabético global em §3 para `Ctrl+F` rápido — mapeia termo a secção.
- Redirects inline na secção lógica (não secção própria).

## 2. Convenções tipográficas

`code` para identifiers, paths, flags. **Bold** para termo quando citado em definição vizinha. `→` para redirect ou ponteiro para spec/doc canónico.

## 3. Índice alfabético global

| Termo | Secção |
|---|---|
| 9-layer architecture | §4 Arquitectura |
| ADR | §11 Operacional |
| APScheduler | §12 Stack |
| Backfill | §11 Operacional |
| Bloco A/B/C/D | §11 Operacional |
| Boom overlay | §5 Ciclos & Regimes |
| Breaking change | §11 Operacional |
| Bubble Warning overlay | §5 Ciclos & Regimes |
| `CALIBRATION_STALE` | §9 Conventions |
| CAPE | §6 Overlays |
| CCCS | §5 Ciclos & Regimes |
| Ciclo | §5 Ciclos & Regimes (redirect) |
| `clip(50 + 16.67·z, 0, 100)` | §9 Conventions |
| Cold start | §10 Fail-mode |
| `COMM_SIGNAL_MISSING` | §9 Conventions |
| Compute-don't-consume | §4 Arquitectura |
| Confidence cap | §9 Conventions |
| Connector | §4 Arquitectura |
| Conventional Commits | §11 Operacional |
| Cost-of-capital | §6 Overlays / §4 L6 |
| CRP | §6 Overlays |
| CS (Communication Signal) | §8 Sub-components |
| Cycle | §4 / §5 |
| Cycle overlay | §5 (redirect) |
| DAG canónico | §4 Arquitectura |
| DCF | §6 Overlays |
| `DILEMMA_NO_ECS` | §9 Conventions |
| Dilemma overlay | §5 Ciclos & Regimes |
| Discovery precede implementation | §11 Operacional |
| DSR | §7 Indices |
| E1 Activity / E2 Leading / E3 Labor / E4 Sentiment | §7 Indices |
| ECS | §5 Ciclos & Regimes |
| `EM_COVERAGE` | §9 Conventions |
| ERP | §6 Overlays |
| Exception hierarchy | §9 Conventions |
| Expected inflation | §6 Overlays |
| Expected inflation (BEI/SWAP/DERIVED/SURVEY) | §6 Overlays |
| `F3_M4_DIVERGENCE` | §9 Conventions |
| `f3_m4_divergence` | §8 Sub-components |
| `F4_COVERAGE_SPARSE` | §9 Conventions |
| F1-F4 (Financial indices) | §7 Indices |
| FCS | §5 Ciclos & Regimes |
| FCI | §7 Indices / §8 |
| Flags catalog | §9 Conventions |
| Frozen contracts | §4 Arquitectura / §9 |
| Full rebackfill | §9 Conventions |
| Gordon (ERP method) | §6 Overlays |
| Hierarchy best-of | §6 Overlays |
| Horizontal expansion | §11 Operacional |
| Hysteresis | §5 / §10 |
| `INSUFFICIENT_HISTORY` | §9 / §10 |
| `InsufficientDataError` | §9 Conventions |
| Integration (L6) | §4 Arquitectura |
| L0-L8 | §4 Arquitectura |
| Layer | §4 Arquitectura |
| LC / MS / QS (CCCS components) | §8 Sub-components |
| Lookback window | §10 Fail-mode |
| M1-M4 (Monetary indices) | §7 Indices |
| MAJOR / MINOR bump | §9 Conventions |
| `methodology_version` | §9 Conventions |
| MSC | §5 Ciclos & Regimes |
| NEER | §8 Sub-components |
| NSS | §6 Overlays |
| Outputs (L7) | §4 Arquitectura |
| Overlay (L2) | §4 / §6 |
| Overlay boolean | §5 Ciclos & Regimes |
| `OVERLAY_MISS` | §9 Conventions |
| Parallel equals | §6 Overlays |
| Phase 0/1/2/3/4 | §11 Operacional |
| Phase gate | §11 Operacional |
| Pipelines (L8) | §4 Arquitectura |
| Placeholders declarados | §4 Arquitectura |
| Policy 1 (re-weight) | §10 Fail-mode |
| Portugal-aware | §4 / §13 |
| Postgres gate | §12 Stack |
| Rating-spread | §6 Overlays |
| Regime (L4 column) | §5 Ciclos & Regimes |
| Regime (L5 table) | §5 Ciclos & Regimes |
| `REGIME_BOOTSTRAP` | §9 Conventions |
| `REGIME_HYSTERESIS_HOLD` | §9 Conventions |
| Regime transition rule | §5 Ciclos & Regimes |
| Re-weight | §10 Fail-mode |
| Shadow rate | §8 Sub-components |
| Ship-first | §11 Operacional |
| SONAR | §4 Arquitectura |
| `SonarError` | §9 Conventions |
| Specs-first | §4 Arquitectura |
| Stagflation overlay | §5 Ciclos & Regimes |
| Sub-modelo | §6 Overlays (redirect) |
| Stagflation Trap | §5 Ciclos & Regimes |
| Taylor gap | §8 Sub-components |
| Tiers T1-T4 | §13 Países |
| Units convention | §9 Conventions |
| UTC / Europe/Lisbon | §9 Conventions |
| Vertical slice | §11 Operacional |
| VIX / CISS / NFCI | §8 Sub-components |
| `XVAL_DRIFT` | §9 Conventions |
| z-score clamp | §10 Fail-mode |

## 4. Arquitectura

### 9-layer architecture
Stack estritamente hierárquico: L0 → L1 → ... → L8. Fluxo dados L0 → L7, orquestrado por L8. → [`ARCHITECTURE.md §3`](ARCHITECTURE.md).

### Compute-don't-consume
Princípio #1: overlays/indices calculados localmente a partir de raw data; nunca copy-paste de outputs agregados externos. Fontes "published" = cross-validation (`XVAL_DRIFT`), não input. → [`ARCHITECTURE.md §2.1`](ARCHITECTURE.md).

### Connector
Adapter para data source externa (API, scrape, download). Output: raw observations + provenance metadata. Base class em `sonar/connectors/` Phase 1. → §4 L0.

### DAG canónico
Grafo de dependências entre specs/módulos. Dados fluem L0 → L7; L4 tem cross-cycle edges (CCCS ← F3/F4; FCS ← L2/M4; MSC ← ECS). → [`ARCHITECTURE.md §6`](ARCHITECTURE.md).

### Frozen contracts
`docs/specs/conventions/` é fonte partilhada de verdade. Alteração = breaking change cross-spec, PR dedicado. → §9.

### L0 Connectors
Adapters para sources externas. → §4 Connector.

### L1 DB
Persistência única. SQLite v0.1 + SQLAlchemy 2.0 + Alembic. Schema é source of truth; código segue schema. → [`ARCHITECTURE.md §3`](ARCHITECTURE.md).

### L2 Overlays
Calculadoras quantitativas universais. Output contínuo em unidades naturais. → §6.

### L3 Indices
Síntese ponderada por sub-dimensão de um ciclo. Output normalizado `[0, 100]`. → §7.

### L4 Cycles
Classificadores de regime macroeconómico. Composite + regime discreto com hysteresis. → §5.

### L5 Regimes
Cenários cruzados reificados (Stagflation Trap, Bubble Warning medium-term, etc.). **Phase 2+**. Em v0.1 vivem como colunas booleanas em L4. → §5.

### L6 Integration
Composição cross-country/cross-cycle: matriz-4way, diagnostics, cost-of-capital. **Phase 2+**.

### L7 Outputs
CLI, FastAPI, editorial pipeline, alerts, dashboard. **Phase 2-3+**.

### L8 Pipelines
Orquestração. Coordena execução L0-L6 por `(country, date)` respeitando dependency DAG. → [`specs/pipelines/README.md`](specs/pipelines/README.md).

### Layer
Camada do stack. Abrevia-se `L<N>`. 9 camadas L0-L8.

### Placeholders declarados
Threshold ungrounded marcado `placeholder — recalibrate after Nm of production data`. ~40 inventariados em specs. → [`ROADMAP.md §Phase 4`](ROADMAP.md).

### Portugal-aware
PT é first-class em cada camada: connectors (IGCP, BPStat, INE), PT CRP daily, PT synthesis expected-inflation, fixtures historical. → §13.

### SONAR
Motor analítico 7365 Capital. Computa ciclos macro + overlays quantitativos + integration cross-country num pipeline batch diário.

### Specs-first
Código em `sonar/` só com spec aprovado em `docs/specs/`. Template canónico em [`specs/template.md`](specs/template.md).

## 5. Ciclos & Regimes

### Boom overlay
Boolean em `credit_cycle_scores`. Trigger: CCCS > 70 + L2 credit_gap > 10pp + L4 DSR z-score > 1.5. → [`specs/cycles/credit-cccs.md`](specs/cycles/credit-cccs.md).

### Bubble Warning overlay
Boolean em `financial_cycle_scores`. Trigger: FCS > 70 + L2 credit_gap > 10pp + BIS property gap > 20%. Medium-term overlay. → [`specs/cycles/financial-fcs.md`](specs/cycles/financial-fcs.md).

### CCCS
Composite Credit Cycle Signal. Regimes: REPAIR / RECOVERY / BOOM / SPECULATION / DISTRESS. Formula v0.1: `0.44·CS + 0.33·LC + 0.22·MS` (QS omitted). → [`specs/cycles/credit-cccs.md`](specs/cycles/credit-cccs.md).

### Ciclo
→ ver **Cycle**.

### Cycle
Classificador L4. 4 cycles: ECS (economic), CCCS (credit), MSC (monetary), FCS (financial). Cada um emite `score_0_100` + `regime` discreto.

### Cycle overlay
→ ver **Overlay boolean**.

### Dilemma overlay
Boolean em `monetary_cycle_scores`. Trigger: MSC > 60 + anchor drifting + ECS < 55. Se ECS faltar, flag `DILEMMA_NO_ECS` e suppressa. → [`specs/cycles/monetary-msc.md`](specs/cycles/monetary-msc.md).

### ECS
Economic Cycle Score. Regimes: EXPANSION / PEAK_ZONE / EARLY_RECESSION / RECESSION. Formula: `0.35·E1 + 0.25·E2 + 0.25·E3 + 0.15·E4`. → [`specs/cycles/economic-ecs.md`](specs/cycles/economic-ecs.md).

### FCS
Financial Cycle Score. Regimes: STRESS / CAUTION / OPTIMISM / EUPHORIA. Formula: `0.30·F1 + 0.25·F2 + 0.25·F3 + 0.20·F4` (F4 tier-conditional). → [`specs/cycles/financial-fcs.md`](specs/cycles/financial-fcs.md).

### Hysteresis
Anti-whipsaw rule: transição de regime requer `|Δscore| > 5` AND `persistence ≥ 3 business days`. Universal cross-cycle.

### MSC
Monetary Stance Classifier. Regimes 6-band (STRONGLY_ACCOMMODATIVE → STRONGLY_TIGHT) + 3-band convenience. Formula: `0.30·M1 + 0.15·M2 + 0.25·M3 + 0.20·M4 + 0.10·CS` (CS direct). → [`specs/cycles/monetary-msc.md`](specs/cycles/monetary-msc.md).

### Overlay boolean
Coluna booleana em tabela L4 (Stagflation, Boom, Dilemma, Bubble Warning). **≠ L2 Overlay**. Em Phase 2+ migra para L5 regimes table.

### Regime (L4 column)
Estado discreto por cycle persistido em coluna `regime` de `*_cycle_scores`. Derivado de score com hysteresis.

### Regime (L5 table)
Cenário cruzado reificado (futuro). **Phase 2+**. Row por `(country, date, regime_scenario)` com `active`, `intensity`, `duration_days`, transition probabilities.

### Regime transition rule
`|Δscore| > 5` AND persistência `≥ 3 business days` no novo band. Uniforme cross-cycle.

### Stagflation overlay
Boolean em `economic_cycle_scores`. Trigger: ECS < 55 + CPI YoY > 3% + labor weakness. → [`specs/cycles/economic-ecs.md`](specs/cycles/economic-ecs.md).

### Stagflation Trap
L5 regime (Phase 2+): ECS RECESSION + CPI > 3% + MSC TIGHT sustentado. Cenário crítico persistido como entidade, não apenas overlay.

## 6. Overlays (L2)

### CAPE
Cyclically Adjusted P/E. Método ERP: `ERP_CAPE = (1/CAPE) − real_risk_free`. Usado em F1. → [`specs/overlays/erp-daily.md`](specs/overlays/erp-daily.md).

### Cost-of-capital
Composite L6 (Phase 2+): `cost_of_equity_country = risk_free + β·ERP_mature + CRP_country`.

### CRP
Country Risk Premium. Hierarchy best-of: CDS → sovereign spread → rating-implied, multiplicado por `σ_equity / σ_bond` vol ratio. 30+ países. → [`specs/overlays/crp.md`](specs/overlays/crp.md).

### DCF
Discounted Cash Flow. Método ERP primary: 5-year projection + terminal, Newton root-find. → [`specs/overlays/erp-daily.md`](specs/overlays/erp-daily.md).

### ERP
Equity Risk Premium. 4 markets (US, EA, UK, JP), 4 methods paralelos (DCF, Gordon, EY, CAPE), canonical = median em bps + range. → [`specs/overlays/erp-daily.md`](specs/overlays/erp-daily.md).

### Expected inflation
Term structure per country-tenor (1Y, 2Y, 5Y, 5y5y, 10Y, 30Y). Hierarchy best-of: BEI → SWAP → DERIVED (PT path: EA + differential) → SURVEY. → [`specs/overlays/expected-inflation.md`](specs/overlays/expected-inflation.md).

### Gordon (ERP method)
`ERP = dividend + buyback + g_sustainable − risk_free`. `g_sustainable = min(retention·ROE, 0.06)`.

### Hierarchy best-of
Padrão arquitectural: methods com quality gradient conhecido; canonical = primeiro disponível na ordem. Usado em CRP, expected-inflation. → [`ARCHITECTURE.md §7`](ARCHITECTURE.md).

### NSS
Nelson-Siegel-Svensson. Fitting 6-param (β0-β3, λ1, λ2) a yields sovereign. 4 output curves: spot, zero, forward, real. 4-param fallback quando <8 obs. → [`specs/overlays/nss-curves.md`](specs/overlays/nss-curves.md).

### Overlay (L2)
Calculadora quantitativa universal. **≠ Overlay boolean (coluna L4)**. 5 overlays: NSS, ERP, CRP, rating-spread, expected-inflation.

### Parallel equals
Padrão arquitectural: methods com standing epistémico igual; canonical = median + range como uncertainty. Usado em ERP. → [`ARCHITECTURE.md §7`](ARCHITECTURE.md).

### Rating-spread
Cross-agency consolidation (S&P / Moody's / Fitch / DBRS) → SONAR scale 0-21 → calibrated `default_spread_bps`. 3 `methodology_version` distintas (pattern "versioning per-table"). → [`specs/overlays/rating-spread.md`](specs/overlays/rating-spread.md).

### Sub-modelo
→ ver **Overlay** (L2). Terminologia v1 legacy. Nunca usar em v2.

### Versioning per-table
Padrão arquitectural: múltiplas tabelas relacionadas com cadências de bump divergentes. Usado em rating-spread (3 versions). → [`ARCHITECTURE.md §7`](ARCHITECTURE.md).

## 7. Indices (L3)

Sub-dimensões por ciclo. Cada spec em `specs/indices/<cycle>/`. Output: `score_normalized ∈ [0, 100]` via z-score clip. Lookback per cycle em §10.

### Economic (ECS inputs)

| Code | Nome | Ref |
|---|---|---|
| E1 | Activity — GDP/IP/retail/employment/income composite | [`specs/indices/economic/E1-activity.md`](specs/indices/economic/E1-activity.md) |
| E2 | Leading — yield slope (from NSS), LEI, OECD CLI, PMIs | [`specs/indices/economic/E2-leading.md`](specs/indices/economic/E2-leading.md) |
| E3 | Labor — unemployment, Sahm, JOLTS, claims | [`specs/indices/economic/E3-labor.md`](specs/indices/economic/E3-labor.md) |
| E4 | Sentiment — UMich, Conference Board, EPU, VIX, ESI | [`specs/indices/economic/E4-sentiment.md`](specs/indices/economic/E4-sentiment.md) |

### Credit (CCCS inputs, aggregated via CS/LC/MS/QS)

| Code | Nome | Ref |
|---|---|---|
| L1 | Credit-to-GDP Stock — BIS ratio, rolling baseline | [`specs/indices/credit/L1-credit-to-gdp-stock.md`](specs/indices/credit/L1-credit-to-gdp-stock.md) |
| L2 | Credit-to-GDP Gap — HP + Hamilton vs trend, BIS Basel III | [`specs/indices/credit/L2-credit-to-gdp-gap.md`](specs/indices/credit/L2-credit-to-gdp-gap.md) |
| L3 | Credit Impulse — ΔΔcredit/GDP, flow momentum | [`specs/indices/credit/L3-credit-impulse.md`](specs/indices/credit/L3-credit-impulse.md) |
| L4 | DSR — Debt Service Ratio (Drehmann-Juselius) | [`specs/indices/credit/L4-dsr.md`](specs/indices/credit/L4-dsr.md) |

### Monetary (MSC inputs)

| Code | Nome | Ref |
|---|---|---|
| M1 | Effective Rates — policy + shadow + real | [`specs/indices/monetary/M1-effective-rates.md`](specs/indices/monetary/M1-effective-rates.md) |
| M2 | Taylor Gaps — policy vs Taylor-implied | [`specs/indices/monetary/M2-taylor-gaps.md`](specs/indices/monetary/M2-taylor-gaps.md) |
| M3 | Market Expectations — forwards, breakevens, 5y5y | [`specs/indices/monetary/M3-market-expectations.md`](specs/indices/monetary/M3-market-expectations.md) |
| M4 | FCI — Financial Conditions Index (NFCI/CISS composite) | [`specs/indices/monetary/M4-fci.md`](specs/indices/monetary/M4-fci.md) |

### Financial (FCS inputs)

| Code | Nome | Ref |
|---|---|---|
| F1 | Valuations — CAPE, Buffett, ERP, property gap | [`specs/indices/financial/F1-valuations.md`](specs/indices/financial/F1-valuations.md) |
| F2 | Momentum — returns 3M/6M/12M, breadth, cross-asset | [`specs/indices/financial/F2-momentum.md`](specs/indices/financial/F2-momentum.md) |
| F3 | Risk Appetite — VIX, MOVE, credit spreads (overlap M4) | [`specs/indices/financial/F3-risk-appetite.md`](specs/indices/financial/F3-risk-appetite.md) |
| F4 | Positioning — AAII, COT, flows, margin debt (tier-conditional) | [`specs/indices/financial/F4-positioning.md`](specs/indices/financial/F4-positioning.md) |

## 8. Sub-components & métricas

### CS (Communication Signal)
Qualitative input consumido directamente por MSC (não via L3). Componentes: dot plot drift, central bank dissent count, NLP hawkish score. Em Phase 0-1 `COMM_SIGNAL_MISSING` é default.

### `f3_m4_divergence`
Diagnostic column em `financial_cycle_scores`: `F3_score − (100 − M4_score)`. Flag `F3_M4_DIVERGENCE` quando `|div| > 15`. Tracked para reconciliation v0.2 candidate.

### FCI
Financial Conditions Index. Composite NFCI Chicago Fed / CISS ECB / custom. Vive em M4 (L3 monetary) e parcialmente em F3 (overlap conceptual).

### LC / MS / QS (CCCS components)
Leverage Cycle (LC, 33%), Market Stress (MS, 22%, cross-cycle from F3/F4), Quality Signal (QS, 10%, omitted v0.1). + CS Credit Stress (44%) que agrega L1/L2/L4. → [`specs/cycles/credit-cccs.md`](specs/cycles/credit-cccs.md).

### NEER
Nominal Effective Exchange Rate. Raw input em M4 FCI.

### NFCI / CISS / VIX
FCI components principais: NFCI (Chicago Fed National Financial Conditions Index), CISS (ECB Composite Indicator of Systemic Stress), VIX (CBOE volatility). Consumidos por M4 e F3.

### Shadow rate
Taxa negativa implícita durante ZLB (Wu-Xia, Krippner). ECB shadow atingiu −7.56% em 2020. Input M1.

### Taylor gap
`policy_rate − Taylor_implied`. Mede stance vs regra de política óptima. Input M2.

### DSR
Debt Service Ratio (Drehmann-Juselius BIS). Fórmula envolve annuity factor × D/Y. AUC 0.89 para crisis 1-2Y forward. Input L4.

## 9. Conventions & contracts

### `clip(50 + 16.67·z, 0, 100)`
Fórmula canonical de normalização L3: z-score rolling per country → `[0, 100]`. Range natural `[-3σ, +3σ]`. Emergiu convergentemente P4, agora padrão. → [`ARCHITECTURE.md §7`](ARCHITECTURE.md).

### Confidence cap
Limite superior aplicado em `confidence` quando condição degradada (missing input, sub-quality source, tier 4 coverage). Policy 1 re-weight impõe cap 0.75.

### `DILEMMA_NO_ECS`
Flag informational emitida por MSC quando ECS row missing → Dilemma overlay suppressed.

### `EM_COVERAGE`
Flag per-row cap 0.75 para países tier 4 EM. Propaga upstream.

### `F3_M4_DIVERGENCE`
Flag informational em FCS quando `|f3_m4_divergence| > 15`. Observability signal para reconciliation v0.2.

### `F4_COVERAGE_SPARSE`
Flag emitida quando F4 positioning data missing (tier 2-3) ou ignorada por design (tier 4). Confidence cap 0.80/0.75.

### Flags catalog
`UPPER_SNAKE_CASE` tokens em coluna `flags` de qualquer tabela. 100 flags catalogadas. Nenhuma spec emite token não catalogado. → [`specs/conventions/flags.md`](specs/conventions/flags.md).

### Full rebackfill
Re-execução de pipelines para toda a história após bump MAJOR de `methodology_version`. Destrói e recria rows com nova version.

### `INDEX_MISSING` (pattern)
Flag `{E1..E4,L1..L4,M1..M4,F1..F4}_MISSING` emitida por cycle L4 quando sub-index unavailable. Trigger re-weight (Policy 1).

### `INSUFFICIENT_HISTORY`
Flag generic: rolling lookback tem menos observações que mínimo requerido pela spec. Cap 0.65.

### `InsufficientDataError`
Exception leaf sob `DataError`. Raise quando `len(observations) < minimum`. Cycle aborta (row não persistida).

### MAJOR / MINOR bump
MAJOR: schema/formula breaking → full rebackfill. MINOR: weights/thresholds → selective backfill per country. → [`specs/conventions/methodology-versions.md`](specs/conventions/methodology-versions.md).

### `methodology_version`
`TEXT NOT NULL` em toda row persistida. Formato `{MODULE}_{VARIANT?}_v{MAJOR}.{MINOR}`. Row com version ≠ runtime raise `VersionMismatchError`.

### `OVERLAY_MISS`
Flag generic: consumer tenta ler overlay X para `(country, date)` mas row não existe. Cap 0.60.

### `REGIME_BOOTSTRAP`
Flag generic: primeira row per `(country, cycle)` sem prev state; hysteresis suspenso. Informational.

### `REGIME_HYSTERESIS_HOLD`
Flag generic: transição de regime tentada mas rejeitada por anti-whipsaw (`|Δscore| ≤ 5` OR persistência `< 3 BD`). −0.05.

### `SonarError`
Root da hierarquia de exceptions (abstract). 4 branches: `DataError`, `AlgorithmError`, `MethodologyError`, `ConnectorError`. 10 leaves. → [`specs/conventions/exceptions.md`](specs/conventions/exceptions.md).

### Units convention
Yields como decimal (`0.0415`, não `4.15`). Basis points como `int`. Timestamps UTC storage, scheduling `Europe/Lisbon`. ISO 8601. → [`specs/conventions/units.md`](specs/conventions/units.md).

### `XVAL_DRIFT`
Flag emitida quando cross-validation vs published source (Fed GSW, Bundesbank Svensson, Damodaran) excede target. Per-overlay thresholds em spec.

## 10. Fail-mode & edge cases

### Cold start
Primeira execução de cycle L4 para um country sem prev state. Emite `REGIME_BOOTSTRAP`, hysteresis suspenso na row.

### Lookback window
Janela rolling para z-score per cycle: **Economic 10Y** / **Credit 20Y** / **Financial 20Y** / **Monetary 30Y** (captura ZLB 2008-2022). Tier 4 EM fallbacks menores. → [`ARCHITECTURE.md §3 L3`](ARCHITECTURE.md).

### Policy 1 (re-weight)
Fail-mode uniforme cross-cycle. Sub-index missing → `{INDEX}_MISSING` flag + re-weight proporcional restantes (`w'_i = w_i / Σ w_available`). `≥ 3 of 4` required; menos → `InsufficientDataError`. Cap confidence 0.75.

### Re-weight
→ ver **Policy 1**.

### z-score clamp
`[-5, +5]` floor/ceil em z-score bruto antes de aplicar clip formula. Evita outliers extremos dominar normalização.

## 11. Operacional & processo

### ADR
Architecture Decision Record. Decisão formal com rationale, alternativas, consequências. `ADR-NNNN-kebab-case.md` em `docs/adr/`. → [`ROADMAP.md`](ROADMAP.md) Mapping fase↔documentos.

### Backfill
Re-execução histórica de pipeline. On-demand (new country, MAJOR bump) ou scheduled. → [`specs/pipelines/backfill-strategy.md`](specs/pipelines/backfill-strategy.md).

### Bloco A/B/C/D
Segmentação de Phase 0: A Fundações (ARCHITECTURE + CLAUDE.md), B Specs (25 specs merged), C Documentação (ROADMAP, REPOSITORY_STRUCTURE, GLOSSARY, ADRs, governance, conventions novas, backlog, flags refactor), D Data Discovery (inventário de fontes). → [`ROADMAP.md §Phase 0`](ROADMAP.md).

### Breaking change
Alteração que quebra contracts partilhados (`conventions/`, schema DDL, API pública). Exige PR dedicado + bump MAJOR onde aplicável.

### Compute-before-calibrate
Princípio: placeholders ficam placeholders até ≥ 24m production data permitir recalibração empírica. Recalibração é Phase 4. → [`ROADMAP.md §Princípios`](ROADMAP.md).

### Conventional Commits
`type(scope): subject`. Types: feat, fix, docs, refactor, chore, style, perf, test, build, ci. PT-PT para subject. Multi-paragraph via `-m` repetido.

### Discovery precede implementation
Princípio: nenhum connector em código sem spec de fonte em `docs/data_sources/`. Bloco D Phase 0 pré-requisito de Phase 1.

### Horizontal expansion
Phase 2 foco: cobertura completa overlays + indices + cycles em velocity, 10-15 países.

### Phase 0/1/2/3/4
Bootstrap & Specs · Vertical Slice · Horizontal Expansion · Integration & Outputs · Calibração & Scale. → [`ROADMAP.md`](ROADMAP.md).

### Phase gate
Critério de saída de fase. Próxima arranca quando satisfeito, sem datas absolutas.

### Ship-first
Princípio: vertical slice Phase 1 (ciclo económico completo) antes de expandir Phase 2. Prova arquitectura, descobre friction.

### Vertical slice
Phase 1 entregável: pipeline diário completo para 1 cycle (Economic) L0-L4. NSS + E1-E4 + ECS + daily-* pipelines.

## 12. Stack

| Área | Tool | Nota |
|---|---|---|
| Language | Python 3.12 | → CLAUDE.md §6 |
| Package manager | uv | nunca pip directo |
| Lint + format | ruff | substitui black/isort/flake8 |
| Type check | mypy | strict |
| Tests | pytest + hypothesis | property-based onde aplicável |
| Pre-commit | `.pre-commit-config.yaml` | ruff, mypy, gitleaks, detect-secrets |
| DB MVP | SQLite + SQLAlchemy 2.0 + Alembic | Phase 0-1 |
| DB scale | Postgres | Phase 2+, condicional (ARCHITECTURE §10 gates) |
| CLI | Typer | Phase 2 |
| API | FastAPI | Phase 3 |
| Dashboard MVP | Streamlit | Phase 3 |
| Dashboard prod | React / TypeScript | Phase 4+ conditional |
| Orchestration | APScheduler vs cron vs Prefect | BRIEF §3 pending |
| CI/CD | GitHub Actions | ci.yml + daily-pipeline.yml |
| Exposure | Cloudflare Tunnel | Phase 4+ conditional |

## 13. Países & cobertura

### Tiers T1-T4

| Tier | Países | F4 handling | FCS confidence cap |
|---|---|---|---|
| 1 | US, DE, UK, JP | required | — |
| 2-3 | FR, IT, ES, CA, AU, PT, IE, NL, SE, CH | best-effort; `F4_COVERAGE_SPARSE` se missing | 0.80 |
| 4 EM | CN, IN, BR, TR, MX, ZA, ID | ignored sempre; `F4_COVERAGE_SPARSE` always | 0.75 |

### Portugal-aware
PT first-class em cada camada. Connectors dedicated: **IGCP** (sovereign debt), **BPStat** (Banco de Portugal), **INE** (Instituto Nacional de Estatística).

### Fixtures historical PT
Anchors canónicos de validação em specs:
- 2007 CRP ~20 bps (pre-crisis baseline)
- 2012 CRP peak ~1500 bps (sovereign crisis)
- 2009 DSR peak (credit stress)
- 2012 CCCS distress (cycle bottom)
- 2019 normalização (post-Troika recovery)
- 2026 CRP ~54 bps (current)

---

*Glossary v0.1 · Phase 0 Bloco 4b · live document, atualiza quando specs/ADRs introduzem termos.*
