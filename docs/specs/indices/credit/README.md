# SONAR · Indices · Credit (CCCS sub-indices)

Os 4 sub-índices L3 do **Credit Cycle Composite Score (CCCS)** (Manual Ciclo de Crédito, Parte V Cap 15). Cada um isolado mede uma dimensão distinta do ciclo de crédito; a agregação acontece em `cycles/credit-cccs` (L4).

## Os 4 sub-índices

| Slug | Layer | Mede | Methodology version | Reference |
|---|---|---|---|---|
| [`L1-credit-to-gdp-stock`](./L1-credit-to-gdp-stock.md) | L3 | Stock total de crédito ao PNFS / GDP — base level estrutural | `L1_CREDIT_GDP_STOCK_v0.1` | Cap 7 |
| [`L2-credit-to-gdp-gap`](./L2-credit-to-gdp-gap.md) | L3 | Desvio do L1 face a HP λ=400k one-sided + Hamilton (dual) — early warning long horizon (AUC 0.84 @ 3-5Y) | `L2_CREDIT_GDP_GAP_v0.1` | Cap 8 |
| [`L3-credit-impulse`](./L3-credit-impulse.md) | L3 | Segunda derivada do credit stock / GDP — Biggs-Mayer-Pick — leading 2-4Q vs GDP growth | `L3_CREDIT_IMPULSE_v0.1` | Cap 9 |
| [`L4-dsr`](./L4-dsr.md) | L3 | Debt Service Ratio — Drehmann-Juselius — best short horizon predictor (AUC 0.89 @ 1-2Y) | `L4_DSR_v0.1` | Cap 10 |

## Dependency map (intra-cycle)

```
              connectors/bis (WS_TC, WS_DSR)
                         │
        ┌────────────────┼─────────────────┐
        │                │                 │
        ▼                ▼                 ▼
    ┌─────┐         ┌─────────┐        ┌─────┐
    │ L1  │         │ raw     │        │ L4  │
    │stock│         │ stock + │        │ DSR │  (independent: lending_rate
    └──┬──┘         │ GDP     │        └──┬──┘     + maturity + D/Y)
       │            └────┬────┘           │
       │                 │                │
       ▼                 ▼                │
    ┌─────┐           ┌─────┐             │
    │ L2  │           │ L3  │             │
    │ gap │           │imp. │             │
    └──┬──┘           └──┬──┘             │
       │                 │                │
       └─────────────────┴────────────────┘
                         │
                         ▼
                   cycles/credit-cccs (L4)
                         │
                         ▼
                   CCCS [0-100]
```

**Edges**:

- **L1 → L2** (HP filter): L2 consume `l1_score_raw` (raw ratio in pct) como input para HP filter one-sided λ=400,000 e Hamilton regression. Single hard dependency intra-cycle.
- **L1 → L3** (derivative): L3 partilha o **mesmo raw credit stock + GDP** que L1 consome do connector BIS. Não consume `l1_score_raw` directamente (precisa LCU absolutos para 2nd derivative); mas o resolver de `series_variant` (Q vs F) deve mirror L1 para coerência — flag `L1_VARIANT_MISMATCH` se diverge.
- **L4 ⊥ {L1, L2, L3}** (independent): DSR usa lending_rate + maturity + debt-to-GDP como inputs separados. Não cruza credit stock direto. **Por desenho** — DSR pode disparar crítico mesmo com gap neutro (caso 2024 rate-hike regime), e essa independência é informacional.

## Normalization (escolha cross-spec)

**Método: z-score 20Y rolling window, country-specific**.

- Calculado per `(country_code, indicator)` sobre rolling history de 20Y (80 quarters) de `score_raw`.
- Output `score_normalized = (score_raw_t − μ_20Y) / σ_20Y`, clamp `[−5, +5]`.
- Quando `lookback_years < 15`, flag `INSUFFICIENT_HISTORY`, confidence −0.20.

**Rationale**:

1. **Comparabilidade cross-country**: cada país medido contra a sua própria distribuição histórica (princípio Drehmann-Juselius — desvios > níveis absolutos).
2. **Comparabilidade cross-index**: 4 z-scores na mesma escala alimentam directamente o CCCS composite.
3. **Robustez**: 20Y captura ≥ 1 ciclo completo (duração média ciclo crédito ~16-20Y per Cap 5.1).
4. **L2 specifically**: o gap BIS já é "gap em pp"; aplicamos z-score adicional para coerência com L1/L3/L4. `score_raw=gap_pp` permanece exposto para readers que prefiram o pp directo.

**Não usado**:

- Percentile rank (Método B Cap 15.4): perde informação de magnitude.
- Threshold-based scoring (Método C): aplicado *adicionalmente* via `phase_band`/`band` columns (informational), mas não substitui z-score como `score_normalized`.

## Lookback window (cross-spec)

**Window: 20 anos rolling (80 quarters)**.

| Indicator | Min hard | Min preferred | Notes |
|---|---|---|---|
| L1 | 15Y (60 obs) | 20Y (80 obs) | shorter → flag `INSUFFICIENT_HISTORY` |
| L2 | 10Y (40 obs) hard floor; Hamilton precisa de h+4=12 obs absolute min | 20Y (80 obs) | HP λ=400k requer ≥ 1 ciclo crédito completo para trend estável |
| L3 | 3Y (12 obs) hard floor (formula); 20Y (80 obs) para z-score | 20Y (80 obs) | shorter z-score → flag |
| L4 | 15Y (60 obs) for `dsr_deviation_pp` baseline; 20Y for z-score | 20Y (80 obs) | BIS `WS_DSR` typically starts 1999, may bind |

**Rationale**: o ciclo de crédito tem duração média 16-20Y (Cap 5.1). 20Y captura aproximadamente um ciclo completo, suficiente para baseline statistics estáveis. Para countries com séries < 15Y (alguns EM), flag e cap confidence — aceitamos sub-óptimo em vez de excluir.

## Output schema (consistent across 4)

Todas as 4 specs partilham este preâmbulo na `CREATE TABLE` (cada slug tem nome próprio):

```sql
country_code           TEXT    NOT NULL,
date                   DATE    NOT NULL,                 -- quarter-end
methodology_version    TEXT    NOT NULL,
score_normalized       REAL    NOT NULL,                 -- z-score [-5, +5]
score_raw              REAL    NOT NULL,                 -- pre-normalization (per-spec unit)
components_json        TEXT    NOT NULL,
lookback_years         INTEGER NOT NULL,
confidence             REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
flags                  TEXT,                              -- CSV
source_connector       TEXT    NOT NULL,
created_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
UNIQUE (country_code, date, methodology_version[, segment])  -- L3/L4 add segment
```

**Per-spec extra columns** (see individual specs):

- L1: `series_variant`, `gdp_vintage_mode`, `structural_band`.
- L2: `gap_hp_pp`, `gap_hamilton_pp`, `trend_gdp_pct`, `hp_lambda`, `hamilton_horizon_q`, `concordance`, `phase_band`.
- L3: `segment`, `flow_t_lcu`, `flow_t_minus4_lcu`, `delta_flow_lcu`, `gdp_t_minus4_lcu`, `series_variant`, `smoothing`, `state`.
- L4: `segment`, `dsr_pct`, `dsr_deviation_pp`, `lending_rate_pct`, `avg_maturity_years`, `debt_to_gdp_ratio`, `annuity_factor`, `formula_mode`, `band`, `denominator`.

**Unit per `score_raw`**:

| Spec | Unit | Example |
|---|---|---|
| L1 | percent (display) | `145.3` |
| L2 | percentage points (gap) | `+3.4` |
| L3 | percentage points of GDP | `+1.8` |
| L4 | percent (display) | `18.4` |

## CCCS composite preview

Manual Cap 15 especifica composite em **três layers** (raw → 5 sub-indices → CCCS [0-100]). Os 4 specs deste folder são **subset dos raw indicators** (Layer 1 of Cap 15 architecture). A agregação completa em `cycles/credit-cccs` (L4) também consume MS (Market Stress, from `indices/financial`), QS (Qualitative Signal, from `indices/credit/extended/surveys`), and housing (from `indices/financial/F4-housing`).

**Within-CCCS weighting**: pesos canónicos Cap 15.6 (validated against AUC backtest 1960-2020 JST):

| Sub-index | Weight | Powered by (this folder) | Powered by (other folders) |
|---|---|---|---|
| **SS** (Stock Stress) | **25%** | L2 gap (60% within SS) + L1 stock-level dev (25% within SS) | + house price gap (15% within SS) |
| **FM** (Flow Momentum) | **15%** | L3 impulse (50% within FM) | + credit growth YoY (30%), mortgage growth (20%) |
| **BP** (Burden Pressure) | **30%** ← **dominant** | L4 DSR deviation (55% within BP) + L4 interest burden (25% within BP) | + NPL YoY change (20% within BP) |
| **MS** (Market Stress) | **20%** | — | HY OAS, IG OAS, CDS sovereign (lives in `indices/financial`) |
| **QS** (Qualitative Signal) | **10%** | — | SLOOS, BLS, BdP survey (lives in `indices/credit/extended/surveys`) |

**Composite formula (preview, full spec lives in `cycles/credit-cccs`)**:

```text
CCCS_t = 0.25·SS_t + 0.30·BP_t + 0.15·FM_t + 0.20·MS_t + 0.10·QS_t   ∈ [0, 100]
```

Where each sub-index ∈ [0, 100] derives from constituent z-scores via min-max scaling against historical extremes (also defined in `cycles/credit-cccs`).

**Phase bands** (Cap 15.8, placeholder — recalibrate after 5Y of production data):

| CCCS | State | Crisis prob (2-3Y) |
|---|---|---|
| 0-30 | Repair / deleveraging active | very low |
| 30-50 | Recovery / Normality | ~5-15% |
| 50-70 | Boom / mid-late expansion | ~15-35% |
| 70-85 | Late boom / Speculation | ~35-60% |
| 85-100 | Distress / critical | ~60-80% |

## Country coverage (CCCS-relevant)

- **L1** (Q-series): 40 countries BIS Tier 1; ~50 with F-series fallback.
- **L2** (gap): same as L1 minus countries with `< 40 obs` history (~10Y bind).
- **L3** (impulse): same as L1 (formula needs `t`, `t−4`, `t−8`).
- **L4** (DSR): 32 countries BIS-direct (`WS_DSR`); approximation o2/o1 extends to ~45.

**Intersection** (all 4 specs covered): ~30 economies including all G20 + EU periphery + Norway/Sweden/Switzerland. Portugal fully covered.

## References

- **Cycle reference**: [`docs/reference/cycles/credit-cccs.md`](../../../reference/cycles/credit-cccs.md) — Manual Ciclo de Crédito (Parte V Cap 15-17).
- **Per-index reference**: [`docs/reference/indices/credit/`](../../../reference/indices/credit/).
- **Data sources**: [`docs/data_sources/credit.md`](../../../data_sources/credit.md) — Camadas 1-2.
- **Conventions**: [`docs/specs/conventions/`](../../conventions/) — flags, exceptions, units, methodology-versions.
