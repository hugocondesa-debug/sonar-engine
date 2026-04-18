# SONAR · Indices · Economic Cycle (E1-E4)

> Layer L3 · cycle: **economic** · scope: 4 sub-índices que alimentam o composite ECS (cycle layer L4, fora deste pacote).

## Purpose

Quatro sub-índices coincident/leading que decompõem a actividade económica para construção do **Economic Cycle Score (ECS)**:

- **E1 — Activity** (coincident, hard data): GDP, IP, employment, retail, real income, PMI composite.
- **E2 — Leading** (forward-looking): yield curve, credit spreads, PMI new orders, building permits, LEI, OECD CLI.
- **E3 — Labor** (multi-dimensional dynamics): Sahm Rule, unemployment, JOLTS, wages, claims, temp help.
- **E4 — Sentiment** (expectations): UMich, Conference Board, ISM, EPU, EC ESI, ZEW, Ifo, Tankan, VIX, SLOOS.

Cada índice emite output `[0, 100]` por `(country, date)` consumível pelo cycle layer.

## Normalization choice — z-score on 10Y rolling window

Todos os 4 indices aplicam **z-score com janela rolling de 10 anos** ao nível dos sub-componentes (Layer 1 do framework Cap 15.4 do manual), depois **rescala linear para `[0, 100]`** ao nível do composite (50 = trend, 0 = severe contraction, 100 = strong expansion). Justificação:

- O manual (Cap 15.4) prescreve explicitamente z-score 10Y como método A predominante; percentile rank (B) e threshold-based (C) ficam reservados a indicadores específicos (yield-curve spread, Sahm Rule, PMI 50 threshold) tratados como input components, não como método global.
- 10 anos cobre tipicamente um ciclo económico completo + buffer, evitando contaminação por single-regime.
- Output `[0, 100]` é **canonical para todos os 4 indices** — comparabilidade direta inter-índices é requisito do composite ECS (Cap 15.6).
- Z-score → `[0, 100]` via mapeamento `score_100 = clip(50 + 16.67·z, 0, 100)` (3σ ≈ ±50 pontos do centro). Mapping é determinístico e documentado por spec.

**Window override**: para Tier 4 EM (data history insuficiente), fallback para 7Y rolling com `EM_COVERAGE` flag. Para Covid (2020-2021), z-scores podem opcionalmente excluir esse intervalo (modo *regime-switch*) — decisão fica em `cycles/economic-ecs` (P5), não nos indices.

## Lookback window — 10 years (canonical) / 7 years (Tier 4 fallback)

| Tier | Window | Rationale |
|---|---|---|
| Tier 1 (US, EA, DE, UK, JP) | 10Y rolling | manual Cap 15.4 default; cobre cycle médio + buffer |
| Tier 2 (FR, IT, ES, CA, AU) | 10Y rolling | mesmo método; data availability ≥ 20Y |
| Tier 3 (PT, IE, NL, SE, CH) | 10Y rolling, best-effort | ≥ 7Y obs requirement; senão `INSUFFICIENT_HISTORY` flag |
| Tier 4 (CN, IN, BR, TR) | 7Y rolling | structural break risk; widen confidence cap |

`lookback_years INTEGER` é coluna persistida em todas as tabelas dos 4 indices para auditoria e reproducibility.

## ECS composite preview

A spec do cycle ECS (`cycles/economic-ecs.md`, P5) consome os 4 indices:

```text
ECS_t = 0.35 · E1_t + 0.25 · E2_t + 0.25 · E3_t + 0.15 · E4_t
ECS ∈ [0, 100]
```

Pesos derivam de calibração contra NBER/CEPR historical dating (Cap 15.6 + Cap 10.11 do manual; análogo a hit-ratio framework de CCCS/MSC):

| Sub-index | Weight | Justification |
|---|---|---|
| E1 Activity | 35% | foundation — current reality, weighted highest to not be late on obvious signals |
| E2 Leading | 25% | forward-looking, critical for antecipação mas noisy |
| E3 Labor | 25% | most reliable single signal (Sahm Rule); deserves significant weight |
| E4 Sentiment | 15% | useful complement mas noisiest as primary signal |

Phase classification (também P5): `>70 Strong Expansion`, `55-70 Expansion`, `45-55 Near-trend`, `30-45 Slowdown`, `20-30 Recession (mild)`, `<20 Recession (severe)`.

> **Nota**: pesos e thresholds documentados aqui são *placeholder — recalibrate após 24m de production data + walk-forward backtest contra NBER/CEPR*.

## Intra-cycle dependencies

| Index | Consumes (overlays L2) | Consumes (other indices L3) |
|---|---|---|
| **E1 Activity** | — (raw FRED/Eurostat/OECD coincident series via `connectors/`) | — |
| **E2 Leading** | `overlays/nss-curves` (10Y−2Y, 10Y−3M slopes, NFS) | — |
| **E3 Labor** | — | — |
| **E4 Sentiment** | — | (VIX consumido como market-sentiment proxy via `connectors/fred`) |

E2 é o único índice com dependência hard em overlay L2 (yield curve). Os outros 3 leem directamente de connectors L0. **Não há dependências cruzadas E↔E** — os 4 indices são paralelos por design (Cap 15.5).

## Country coverage

| Tier | Countries | E1 | E2 | E3 | E4 | Notes |
|---|---|---|---|---|---|---|
| 1 | US, EA, DE, UK, JP | full | full | full | full | reference universe; calibration target |
| 2 | FR, IT, ES, CA, AU | full | partial (LEI may miss) | full | partial (sentiment reduced set) | best-effort; flag where missing |
| 3 | PT, IE, NL, SE, CH | partial (no PMI) | reduced (no LEI) | partial (no JOLTS) | partial (EU ESI overlay) | requires EA overlay; data gaps explicit |
| 4 | CN, IN, BR, TR | experimental | experimental | experimental | experimental | wider CI; `EM_COVERAGE` cap |

Portugal específicamente em Tier 3 — INE + BPStat + Eurostat overlay; ECS computável but gap-aware.

## Cross-references

- **Reference manual**: [`../../reference/cycles/economic.md`](../../reference/cycles/economic.md) — Partes I/II/IV/V/VI; Cap 15 ECS design, Cap 17 matrix 4-way.
- **Index reference docs**: [E1](../../reference/indices/economic/E1-activity.md) · [E2](../../reference/indices/economic/E2-leading.md) · [E3](../../reference/indices/economic/E3-labor.md) · [E4](../../reference/indices/economic/E4-sentiment.md).
- **Data sources plan**: [`../../data_sources/economic.md`](../../data_sources/economic.md) — connector inventory, FRED/Eurostat/OECD series.
- **Cycle composite spec (P5, future)**: `cycles/economic-ecs.md` — consumirá `E1..E4.score_normalized`.
- **Conventions**: [flags](../conventions/flags.md) · [exceptions](../conventions/exceptions.md) · [units](../conventions/units.md) · [methodology-versions](../conventions/methodology-versions.md).
