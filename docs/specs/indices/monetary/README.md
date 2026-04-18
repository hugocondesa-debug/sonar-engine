# SONAR · Indices · Monetary Cycle (M1-M4)

> Layer L3 · cycle: **monetary** · scope: 4 sub-índices que alimentam o composite MSC (cycle layer L4, fora deste pacote).

## Purpose

Quatro sub-índices que decompõem o stance monetário per `(country, date)` em `[0, 100]` (higher = tighter), foundation do **Monetary Stance Composite (MSC)** + Dilemma flag (Cap 15-16):

- **M1 — Effective rates**: shadow rate (Wu-Xia / Krippner) → real rate → `stance_vs_neutral` vs r* (HLW). "Onde está policy hoje, em termos comparáveis cross-time / cross-BC."
- **M2 — Taylor Rule gaps**: `actual − Taylor_implied` para 4 variantes (1993, 1999, inertia, forward-looking); median + range. "Quanto BC diverge da regra benchmark."
- **M3 — Market expectations**: forwards 1y1y / 2y1y / 5y5y (NSS) + 5y5y breakeven (anchor) + policy surprise. "O que o mercado pricing diz sobre trajetória + credibility."
- **M4 — FCI**: Chicago Fed NFCI (US) ou custom-FCI 7-component (PT/EA/UK/JP) — credit spreads, equity vol, yield level, FX, liquidity. "Stance as felt by markets."

Cada índice emite `score_normalized ∈ [0, 100]` por `(country, date)` consumível pelo cycle layer L4.

## Normalization choice — z-score sobre 30Y rolling window

Todos os 4 indices aplicam **z-score com janela rolling de 30 anos** ao nível dos components/raw signals, agregam ponderado conforme weights de Cap 15.5 (sub-indices ES / RD / EP / FC), e mapeiam o composite z para `[0, 100]` via `clip(50 + 16.67·z, 0, 100)` (3σ ≈ ±50). Justificação:

- Manual Cap 15.4 prescreve z-score (método A) como predominante para shadow rates / Taylor gaps / FCI — todos stock-like.
- 30Y window (vs 10-15Y do CCCS/ECS) é necessário porque ciclo monetário inclui o regime ZLB 2008-2022 — janela curta excluiria histórico onde shadow rate atingiu −7.56% (ECB 2020) ou Taylor gap −3.5pp (Fed 2022). Sem essa cauda, z-scores ficam comprimidos.
- Output `[0, 100]` é canonical para todos os 4 indices — comparabilidade direta inter-índices é requisito do composite MSC.
- Sign convention uniforme: **higher = tighter stance** (positive deviation, hawkish surprise, tight financial conditions all positive).

**Window override**:

| Tier | Window | Rationale |
|---|---|---|
| Tier 1 (US, EA, DE, UK, JP) | 30Y rolling | cobre pre-2008 + ZLB regime + post-2022 |
| Tier 2 (FR, IT, ES, CA, AU) | 30Y rolling | data availability ≥ 30Y para curvas + rates |
| Tier 3 (PT, IE, NL, SE, CH) | 25-30Y best-effort | pré-EUR data sparse; senão `INSUFFICIENT_HISTORY` flag |
| Tier 4 (CN, IN, BR, TR, MX) | 15Y rolling | structural breaks; cap confidence via `EM_COVERAGE` |

`lookback_years INTEGER` é coluna persistida em todas as 4 tabelas para auditoria + reproducibility.

## Lookback window — 30 years (canonical) / 15 years (Tier 4 fallback)

Mais longo que ECS (10Y) por desenho — único modo de capturar variance do shadow rate / Taylor gap durante ZLB. M2 e M3 herdam mesma window por consistency; M4 idem (NFCI Chicago Fed back-computed desde 1971 — coverage não é constraint).

## MSC composite preview

A spec do cycle MSC (`cycles/monetary-msc.md`, P5) consome os 4 indices e mapeia aos 5 sub-indices canónicos do manual (ES, RD, EP, FC, CS) — M3 transporta tanto EP quanto a componente nominal de CS (anchor):

```text
MSC_t = w_ES · M1_t  +  w_RD · M2_t  +  w_EP+CS · M3_t  +  w_FC · M4_t
      = 0.30 · M1    +  0.15 · M2    +  0.35 · M3        +  0.20 · M4
MSC ∈ [0, 100]
```

Pesos derivam directamente de Cap 15.6 (manual ciclo monetário), agrupados aos 4 indices SONAR:

| Sub-index manual | Peso Cap 15.6 | Index SONAR L3 | Justificação |
|---|---|---|---|
| ES (Effective Stance) | 30% | M1 — Effective rates | Current reality; foundation of classification |
| EP (Expected Path) | 25% | M3 (parcial, EP weight) | Forward-looking; dominant for future effects |
| FC (Financial Conditions) | 20% | M4 — FCI | Market transmission; links to real economy |
| RD (Rule Deviation) | 15% | M2 — Taylor gaps | Rule benchmark; identifies discretionary divergence |
| CS (Credibility Signal) | 10% | M3 (parcial, anchor) | Meta-level; warning signal weight |

Soma M3 = 25% (EP) + 10% (CS, via 5y5y anchor + policy surprise) = **35%** combinado; demais sub-indices CS quantitativos (dot plot deviation, dissent rate, framework revision activity, communication NLP) são Tier 2 connectors futuros consumidos directamente em `cycles/monetary-msc` (não em M3 v0.1).

**Sign convention**: **MSC higher = tighter stance**. Cada index contribui sign-coherently — positive policy rate deviation, hawkish surprise, anchor breaking upward, tight financial conditions são todos positivos.

## MSC phase bands preview (Cap 15.8)

| MSC | Estado | Editorial label |
|---|---|---|
| 0-20 | Strongly Accommodative | "QE active, near-zero rates" |
| 20-35 | Accommodative | "Rates below neutral, easing bias" |
| 35-50 | Neutral-Accommodative | "Slightly supportive" |
| 50-65 | Neutral-Tight | "Slightly restrictive" |
| 65-80 | Tight | "Above neutral, restrictive" |
| 80-100 | Strongly Tight | "Aggressive tightening" |

Task brief simplification (Accommodative <40 / Neutral 40-60 / Tight >60) é consistent com bandas finas do manual (40 cai dentro de Neutral-Accommodative; 60 cai dentro de Neutral-Tight). Phase classification fina (6 bandas) vive em `cycles/monetary-msc` (P5).

> **Nota**: pesos e thresholds documentados aqui são *placeholder — recalibrate após 24m de production data + walk-forward backtest contra periods de identified monetary regime changes* (2004-06 Fed hike, 2013 taper tantrum, 2014 ECB easing, 2019 Fed cut, 2022 hiking — Cap 15.6).

## Intra-cycle dependencies

| Index | Consumes (overlays L2) | Consumes (other indices L3) | Consumes (connectors L0) |
|---|---|---|---|
| **M1 Effective rates** | `expected-inflation` (5Y for real rate) | — | `krippner`, `wu_xia_atlanta`, `laubach_williams`, `fred`/`ecb_sdw`/`boe_database`/`boj` (policy + balance sheet) |
| **M2 Taylor gaps** | `expected-inflation` (2Y forecast for forward variant) | — | `imf_weo`, `oecd_eo`, `cbo`, `ameco` (output gap) + inflation YoY connectors + `laubach_williams` |
| **M3 Market expectations** | `nss-curves` (forwards 1y1y, 5y5y), `expected-inflation` (5y5y, anchor_status) | — | `policy_surprise` (Tier 2; Miranda-Agrippino) — optional |
| **M4 FCI** | `nss-curves` (10Y level), `erp-daily` (P/E z-score, optional) | optional read of `m1-effective-rates.shadow_rate_pct` | `fred` (NFCI/credit spreads), `ecb_sdw` (NEER, MIR), `yahoo_finance` (VIX/VSTOXX) |

**Não há dependências cruzadas M↔M de hard data** — os 4 indices computam-se em paralelo. M4 pode ler M1's `shadow_rate_pct` como component se preferir vs. fetch from connector — both paths resultam no mesmo número (M1 já computa shadow_rate). Decisão de read-from-M1 vs read-from-connector é implementation detail, não contrato.

Ambos M1 e M2 partilham `r_star_pct` (HLW) — single source of truth, lido independentemente.

## Country coverage

| Tier | Countries | M1 | M2 | M3 | M4 | Notes |
|---|---|---|---|---|---|---|
| 1 | US, EA, DE, UK, JP | full | full | full | full (NFCI for US; custom for EA/UK/JP) | reference universe; calibration target |
| 2 | FR, IT, ES, CA, AU | full | full | full | custom | HLW r* available for CA; AU/IT/ES use HLW EA proxy or `FIXED_2PCT` |
| 3 | PT, IE, NL, SE, CH | proxy (EA r*) | proxy (EA r*) | full (PT NSS exists) | custom (Cap 10.6) | PT é Tier 3 — flag `R_STAR_PROXY` em M1+M2; full M3+M4 |
| 4 | CN, IN, BR, TR, MX | sparse | sparse (PBoC: skip) | partial (no anchor for CN/TR) | sparse | wider CI; `EM_COVERAGE` cap 0.60 |

Portugal especificamente: full M3+M4 (NSS + custom-FCI funcionam end-to-end); M1+M2 com `R_STAR_PROXY` (EA HLW como neutral rate); confidence cap 0.75 nos dois.

Coverage real é limitada por **r* availability** (Cap 7.5: PT/IE/NL/CH não têm HLW oficial) e por **shadow rate live** (Krippner cobre 7 BCs; outros usam policy rate fora do ZLB).

## Cross-references

- **Reference manual**: [`../../../reference/cycles/monetary.md`](../../../reference/cycles/monetary.md) — Partes I/II/III/IV/V; Cap 15 MSC design (Layer 1-3), Cap 16 Dilemma states.
- **Index reference docs**: [M1](../../../reference/indices/monetary/M1-effective-rates.md) · [M2](../../../reference/indices/monetary/M2-taylor-gaps.md) · [M3](../../../reference/indices/monetary/M3-market-expectations.md) · [M4](../../../reference/indices/monetary/M4-fci.md).
- **Data sources plan**: [`../../../data_sources/monetary.md`](../../../data_sources/monetary.md) — 7 camadas funcionais, 3 tiers, 4-week MVP roadmap.
- **Overlays consumed**: [nss-curves](../../overlays/nss-curves.md) · [expected-inflation](../../overlays/expected-inflation.md) · [erp-daily](../../overlays/erp-daily.md) (M4 P/E component).
- **Cycle composite spec (P5, future)**: `cycles/monetary-msc.md` — consumirá `M1..M4.score_normalized` + Dilemma logic Cap 16.
- **Conventions**: [flags](../../conventions/flags.md) · [exceptions](../../conventions/exceptions.md) · [units](../../conventions/units.md) · [methodology-versions](../../conventions/methodology-versions.md).
