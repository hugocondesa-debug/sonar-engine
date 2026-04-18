# SONAR · Indices · Financial Cycle (F1-F4)

> Layer L3 · cycle: **financial** · scope: 4 sub-índices que alimentam o composite FCS (cycle layer L4, fora deste pacote) + Bubble Warning overlay (L6).

## Purpose

Quatro sub-índices que decompõem o ciclo financeiro para construção do **Financial Cycle Score (FCS)**:

- **F1 — Valuations** (foundation, structural): CAPE, Buffett ratio, ERP (consume `overlays/erp-daily`), forward P/E, BIS property gap.
- **F2 — Momentum** (coincident regime): price 3M/6M/12M returns, breadth (`% > 200d MA`), cross-asset risk-on signal.
- **F3 — Risk Appetite** (key driver): VIX/VSTOXX, MOVE, HY/IG OAS, FCI (NFCI/CISS); crypto vol diagnostic only.
- **F4 — Positioning** (leading at extremes): AAII bull-bear, put/call, COT non-comm S&P, margin debt/GDP, IPO activity.

Cada índice emite output `[0, 100]` por `(country, date)` consumível pelo cycle layer FCS (L4) e Bubble Warning overlay (L6).

## Normalization choice — z-score on 20Y rolling window

Todos os 4 indices aplicam **z-score com janela rolling de 20 anos** ao nível dos sub-componentes, depois **rescala linear para `[0, 100]`** com mapping `score_normalized = clip(50 + 16.67·z, 0, 100)` (3σ ≈ ±50 pontos do centro). Justificação:

- **20Y > 10Y (economic ECS)** porque o ciclo financeiro tem duração tipicamente maior (Borio: 15-20 anos para o medium-term BIS cycle; Kindleberger bubble episodes 5-15Y); janela mais curta contamina por single-regime.
- **F1 CAPE** complementarmente computa **percentile rank vs 40Y** (persistido em `components_json` como diagnostic) — manual cap 7.2 enfatiza interpretabilidade histórica de longo-prazo para CAPE especificamente. Z-score 20Y continua a ser o input do composite.
- Output `[0, 100]` é **canonical para todos os 4 indices** — comparabilidade direta inter-índices é requisito do FCS composite (Cap 15.4-15.6).
- Mapping `50 + 16.67·z` é determinístico, idêntico ao do ECS para coerência cross-cycle.

**Window override**: para Tier 4 EM (data history insuficiente para 20Y), fallback para 10Y rolling com `INSUFFICIENT_HISTORY` flag (proposto). `EM_COVERAGE` cap simultaneously aplicado.

## Lookback window — 20 years (canonical) / 10 years (Tier 4 fallback)

| Tier | Window | Rationale |
|---|---|---|
| Tier 1 (US, EA, DE, UK, JP) | 20Y rolling | manual default; cobre múltiplos cycles + bubble episodes (1998, 2007, 2021) |
| Tier 2 (FR, IT, ES, CA, AU) | 20Y rolling | mesmo método; data availability ≥ 25Y |
| Tier 3 (PT, IE, NL, SE, CH) | 20Y best-effort | ≥ 10Y obs requirement; senão `INSUFFICIENT_HISTORY` flag |
| Tier 4 (CN, IN, BR, TR, MX) | 10Y rolling | structural break risk; `EM_COVERAGE` cap |

`lookback_years INTEGER` é coluna persistida em todas as tabelas dos 4 indices para auditoria e reproducibility.

## FCS composite preview

A spec do cycle FCS (`cycles/financial-fcs.md`, P5) consome os 4 indices com pesos canónicos do manual cap 15.5:

```text
FCS_t = 0.30 · F1_t + 0.25 · F2_t + 0.25 · F3_t + 0.20 · F4_t
FCS ∈ [0, 100]
```

| Sub-index | Weight | Justification (manual cap 10.11 + 15.5) |
|---|---|---|
| F1 Valuations | 30% | foundation, structural — distância from fair value define potential downside |
| F2 Momentum | 25% | current regime — coincident; strong momentum = robust regime |
| F3 Risk appetite | 25% | key driver — willingness to hold risky assets, includes vol + spreads + FCI |
| F4 Positioning | 20% | leading-at-extremes — most useful at tails (contrarian edge) |

### Phase classification (FCS bands)

| FCS | State | Interpretation |
|---|---|---|
| `> 75` | **Euphoria** | bubble territory, asymmetric downside risk |
| `55-75` | **Optimism** | mid-cycle sweet spot |
| `30-55` | **Caution** | early stress, pre/mid correction |
| `< 30` | **Stress** | crisis mode, extreme opportunities |

### Sign convention

**Higher FCS = more euphoric / risk-on / overvalued.** Each F1-F4 follows same convention:

- F1: high score = expensive valuations
- F2: high score = strong positive momentum
- F3: high score = complacent (low vol, tight spreads, loose FCI) — **all components sign-flipped internally**
- F4: high score = bullish positioning (contrarian warning) — **put/call sign-flipped internally**

Cycle L4 spec consome `score_normalized` directamente; sign-flip happens **inside cada index spec**, FCS composite é simples weighted average.

### Bubble Warning overlay (medium-term, L6 integration)

Composite trigger conjugando 3 condições (manual cap 16):

```text
bubble_warning = (FCS > 70)
              AND (BIS credit-to-GDP gap > 10 pp)
              AND (BIS property price gap > 20 %)
```

- **FCS** vem de `cycles/financial-fcs` (peso 30% F1 dominante).
- **BIS credit gap** vem de `indices/credit/L2-credit-to-gdp-gap` (NÃO duplicado em F1).
- **BIS property gap** vem do mesmo input que F1 (`connectors/bis_property`); F1 já o consome internamente como component.

Bubble Warning é **overlay diagnostic** em L6, não classification primária — não substitui FCS phase, complementa.

> **Placeholder thresholds — recalibrate after 24m de production data + walk-forward backtest contra Borio-Drehmann historical bubble episodes (Japan 1989, US 2006, Spain 2007, China 2021)**.

## Intra-cycle dependencies

| Index | Consumes (overlays L2) | Consumes (other indices L3) | Consumes (raw connectors L0) |
|---|---|---|---|
| **F1 Valuations** | `overlays/erp-daily.erp_canonical.erp_median_bps` (heavy) | — | `shiller`, `multpl`, `factset_insight`, `fred (Wilshire/GDP)`, `bis_property` |
| **F2 Momentum** | — | — | `fred (SP500)`, `yahoo`, breadth sources |
| **F3 Risk Appetite** | — | conceptual overlap with `cycles/monetary-msc.M4_FCI` (see note) | `fred (VIXCLS, NFCI, BAMLH0A0HYM2, BAMLC0A0CM)`, `ecb_sdw (CISS)`, `ice_move`, `coinglass` |
| **F4 Positioning** | — | — | `aaii`, `cboe`, `cftc_cot`, `finra`, `renaissance_ipo`, `fred (GDP)` |

**Heavy overlay consumer**: F1 reads `erp_canonical.erp_median_bps` directamente; ERP method divergence flag inherited per `flags.md` propagation rule.

**F3 ↔ M4 FCI overlap**: `cycles/monetary-msc.M4_FCI` é o canonical FCI computation per country (MSC layer 1). F3 consome `NFCI` / `CISS` raw como input próprio com normalization independente (20Y vs MSC-specific window). Os dois reportam dimensões diferentes — M4 stance monetária via condições financeiras; F3 risk appetite ciclo financeiro. **v0.2 candidato**: F3 reads `M4_FCI.fci_level` directamente (cross-cycle consistency) em vez de raw NFCI. Documentado em `cycles/financial-fcs` Cap 15 §integração.

**No cross-imports F↔F**: os 4 indices financeiros são paralelos por design.

## Country coverage

| Tier | Countries | F1 | F2 | F3 | F4 | Notes |
|---|---|---|---|---|---|---|
| 1 | US | full | full | full | full | reference universe; calibration target |
| 1 | EA / DE / UK / JP | full (ERP via mature index) | full (regional breadth proxy) | full (VSTOXX/VXJ; CISS for EA) | partial (AAII proxied; no FINRA) | Tier 1 com ERP coverage |
| 2 | FR / IT / ES / CA / AU | partial (ERP via EA aggregate) | full | partial (MOVE proxied) | sparse (AAII proxied; no margin) | Tier 2 com ERP heritado |
| 3 | PT / IE / NL / SE / CH | reduced (PSI-20 synthetic CAPE; EA ERP fallback) | reduced (`BREADTH_PROXY` flag) | reduced (`MOVE_PROXY`, EA CISS) | severely degraded — ≥2/5 components apenas via US proxies | Portugal target; data gaps explicit |
| 4 | CN / IN / BR / TR / MX | experimental — no ERP, sparse property gap | experimental (no breadth) | experimental (US proxies) | likely fails `InsufficientDataError` | wider CI; `EM_COVERAGE` cap; positioning data essentially N/A |

**Portugal specifics**: PT equity valuations via PSI-20 CAPE (constructed locally via `connectors/euronext_lisbon`). Real estate via `bis_property` + `connectors/ine_pt`. Limited positioning data — F4 fica em ≤ 2 components com flags `AAII_PROXY` + degradação confidence. ERP cai para EA aggregate (`SXXP`) heritado.

**EM positioning data gap**: F4 emite `InsufficientDataError` para a maioria dos Tier 4. EM positioning composite é roadmap v0.2 quando local broker / exchange APIs forem accessible.

## Confidence floors

| Tier | Min confidence allowed | Behavior at floor |
|---|---|---|
| Tier 1 US | 0.50 | full row persisted |
| Tier 1 EA/UK/JP | 0.40 | full row persisted, multiple proxy flags expected |
| Tier 2 | 0.35 | reduced component set acceptable |
| Tier 3 PT et al. | 0.30 | flagged-heavy row; editorial advisable |
| Tier 4 EM | 0.25 (or `InsufficientDataError`) | row only if ≥ 2 components OR `EM_COVERAGE` informational |

## Cross-references

- **Reference manual**: [`../../reference/cycles/financial.md`](../../reference/cycles/financial.md) — Partes I-VI; Cap 15 FCS design, Cap 16 Bubble Warning, Cap 17 matrix 4-way.
- **Index reference docs**: [F1](../../reference/indices/financial/F1-valuations.md) · [F2](../../reference/indices/financial/F2-momentum.md) · [F3](../../reference/indices/financial/F3-risk-appetite.md) · [F4](../../reference/indices/financial/F4-positioning.md).
- **Data sources plan**: [`../../data_sources/financial.md`](../../data_sources/financial.md) — connector inventory (~120 FRED series + new connectors AAII, CFTC, FINRA, CBOE, BIS property, Glassnode, Renaissance IPO).
- **Upstream overlays**: [`overlays/erp-daily`](../../overlays/erp-daily.md) (F1 heavy consumer) · [`overlays/nss-curves`](../../overlays/nss-curves.md) (indirect via ERP).
- **Cycle composite spec (P5, future)**: `cycles/financial-fcs.md` — consumirá `F1..F4.score_normalized`.
- **Bubble Warning overlay (L6, future)**: `integration/diagnostics/bubble-warning.md` — consume FCS + BIS credit gap + BIS property gap.
- **Conventions**: [flags](../../conventions/flags.md) · [exceptions](../../conventions/exceptions.md) · [units](../../conventions/units.md) · [methodology-versions](../../conventions/methodology-versions.md).
