# Normalization contract

Todos os indices L3 emitem `score_normalized ∈ [0, 100]` via fórmula canónica. Cycles L4 consomem directo sem re-normalização.

## Fórmula canónica

```
z = (x − μ_lookback) / σ_lookback     # z-score per country
z_clamped = clip(z, -5, +5)           # floor/ceil antes de rescala
score_normalized = clip(50 + 16.67·z_clamped, 0, 100)
```

Constantes:

- **50**: centro da escala (neutral, trend).
- **16.67**: rescala tal que `z = ±3σ → score = 0 ou 100` (extremos).
- **Clamp ±5**: evita outliers extremos dominarem normalização.
- **Clip final `[0, 100]`**: enforcement estrito de range.

## Semântica dos scores

- `score < 30`: extreme deviation negative (> 2σ abaixo).
- `score 30-50`: below trend.
- `score = 50`: trend / neutral.
- `score 50-70`: above trend.
- `score > 70`: extreme deviation positive (> 2σ acima).

Semântica direccional per cycle pode inverter sign convention — ver spec do index individual (ex: F3 risk-appetite usa sign-flip para alguns componentes).

## Lookback window per cycle

Declarado em cada README de indices/. Tabela canónica:

| Cycle | Canonical | Tier 4 fallback | Rationale |
|---|---|---|---|
| Economic | 10Y | 7Y | Cap 15.4 default; cycle médio + buffer |
| Credit | 20Y | 15Y floor | 80 quarters, BIS WS_TC standard |
| Financial | 20Y | 10Y | múltiplos cycles + bubble episodes |
| Monetary | 30Y | 15Y | cobre regime ZLB 2008-2022 |

F1 CAPE adicionalmente computa percentile rank 40Y como diagnostic (persistido em `components_json`, não usado no composite).

## `INSUFFICIENT_HISTORY` — trigger

Spec individual declara threshold per-cycle (tipicamente `< 15Y` para credit/financial, `< 7Y` para economic, `< 20Y` para monetary). Quando disparado:

- Flag `INSUFFICIENT_HISTORY` emitido.
- Window reduzida para o disponível.
- `confidence` capped (tipicamente 0.65-0.70 conforme spec).
- `lookback_years` column regista o window real usado.

## Campos persistidos (mandatory em indices L3)

Todas as tabelas `*_index_scores` devem incluir:

- `score_normalized REAL NOT NULL CHECK (score_normalized BETWEEN 0 AND 100)`
- `score_raw REAL` (unidade natural do index, pré-normalização)
- `lookback_years INTEGER NOT NULL` (window real usado)
- `components_json TEXT` (z-scores por componente para audit)

## Consumer contract

Cycles L4 aplicam **weighted sum directo** sem re-normalização:

```
composite = Σ (w_i · score_normalized_i)
# composite já em [0, 100] se pesos somam 1
```

Re-weighting (fail-mode) delegado a [`composite-aggregation.md`](composite-aggregation.md).

## Contra-exemplo

Overlays L2 emitem contínuo em **unidades naturais** (bps, decimal, pp). Não aplicam clip formula — output é o cálculo directo. Normalização é propriedade exclusiva de L3.

## Referências

- [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md) §7 — Normalization convergente
- [`../../GLOSSARY.md`](../../GLOSSARY.md) §9 — clip formula entry
- [`../indices/economic/README.md`](../indices/economic/README.md),
  [`../indices/credit/README.md`](../indices/credit/README.md),
  [`../indices/monetary/README.md`](../indices/monetary/README.md),
  [`../indices/financial/README.md`](../indices/financial/README.md) — lookbacks per cycle
