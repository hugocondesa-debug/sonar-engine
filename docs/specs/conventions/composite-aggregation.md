# Composite aggregation — fail-mode

Todos os cycles L4 aplicam **Policy 1** (re-weight proporcional) quando sub-indices estão indisponíveis. Policy uniforme cross-cycle aprovada em P5.

## Input contract

Cycle L4 consome 4 indices L3 (`score_normalized ∈ [0, 100]`) com pesos `w_i` somando 1. Ex: ECS composite = `0.35·E1 + 0.25·E2 + 0.25·E3 + 0.15·E4`.

## Fail-mode rules

### Regra 1: Re-weight proporcional

Sub-index missing → `{INDEX}_MISSING` flag + re-weight dos restantes:

```
w'_i = w_i / Σ_{j ∈ available} w_j   # renormalização proporcional
composite = Σ (w'_i · score_i)
```

Ex: ECS com E4 missing → pesos `(0.35, 0.25, 0.25, 0.0)` renormalizados para `(0.412, 0.294, 0.294, 0.0)`.

### Regra 2: Mínimo ≥ 3 of 4 indices

Se < 3 indices disponíveis (2 ou fewer):

- Cycle **não persiste row**.
- Raise `InsufficientDataError`.
- Operator alertado via log `ERROR`.

Motivo: composite com ≤ 50% de cobertura perde validade estatística para classificação de regime.

### Regra 3: Confidence cap

Quando re-weight activo (≥ 1 index missing):

- `confidence` capped a **0.75**.
- `confidence_base = min(score_i.confidence ∀ i available) · (N_available / 4)`.
- `confidence_final = min(confidence_base, 0.75)`.

### Regra 4: Flags obrigatórios

Row persistida deve carregar:

- `{INDEX}_MISSING` para cada index ausente (ex: `E4_MISSING`).
- Flag informativa quando `confidence` foi capado por Policy 1 (naming canónico a estabelecer quando primeiro consumer activar em Phase 1).
- `lookback_years` do mais curto dos available.

## Campos persistidos (mandatory em cycles L4)

Todas as tabelas `*_cycle_scores` devem incluir:

- `score_0_100 REAL NOT NULL`
- `regime TEXT NOT NULL` (enum per cycle)
- `regime_persistence_days INTEGER NOT NULL`
- `effective_weights TEXT` (JSON com pesos reais usados, reflecte re-weight se activo)
- `confidence REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1)`
- `flags TEXT` (CSV ou JSON array de flags)

## Exceptions

`InsufficientDataError` é leaf sob `DataError` (ver [`exceptions.md`](exceptions.md)). Cycle raises + logger ERROR; pipeline isola falha per-country (outros countries continuam).

## Cross-cycle dependencies

Policy 1 aplica-se ao nível **intra-cycle** (4 indices do próprio ciclo). Cross-cycle dependencies (CCCS ← F3/F4; MSC ← ECS; FCS ← L2/M4) têm regras próprias em specs individuais de cycles. Quando dependency cross-cycle está missing:

- **CCCS sem F3/F4**: CCCS não corre; raise `InsufficientDataError`.
- **MSC sem ECS**: Dilemma overlay suppressed com flag `DILEMMA_NO_ECS`; MSC continua.
- **FCS sem L2/M4**: Bubble Warning suppressed com flag apropriado; FCS continua.

Ver spec individual por cycle para detalhe.

## Contra-exemplo

Overlays L2 não aplicam Policy 1 — cada overlay tem own fail-mode (ex: ERP com ≥ 2 of 4 methods; CRP com method hierarchy fallback; NSS com 4-param fallback quando < 8 observations).

## Referências

- [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md) §8 — Fail-mode cross-cycle
- [`../../GLOSSARY.md`](../../GLOSSARY.md) §10 — Policy 1 entry
- [`flags.md`](flags.md) — catálogo completo de flags
- [`exceptions.md`](exceptions.md) — `InsufficientDataError`
- [`../cycles/economic-ecs.md`](../cycles/economic-ecs.md),
  [`../cycles/credit-cccs.md`](../cycles/credit-cccs.md),
  [`../cycles/monetary-msc.md`](../cycles/monetary-msc.md),
  [`../cycles/financial-fcs.md`](../cycles/financial-fcs.md) — aplicação individual
