# SONAR · Specs · Conventions

Contratos partilhados por **todas** as specs. Source of truth para naming, unidades, versões, flags e exceptions. Specs individuais referenciam; nunca redefinem.

## Ficheiros

| Ficheiro | Âmbito | Quando mexer |
|---|---|---|
| [`flags.md`](./flags.md) | Catálogo canónico de flags `UPPER_SNAKE_CASE` emitidas em `flags` column | Adicionar uma flag **antes** de a emitir em qualquer spec |
| [`exceptions.md`](./exceptions.md) | Hierarquia `SonarError` · 4 branches · 8 leaves | Nova exception → novo leaf aqui, nunca inline numa spec |
| [`units.md`](./units.md) | Yields decimal vs display, bps, datas, confidence | Só em RFC — mudança aqui é breaking em toda a DB |
| [`methodology-versions.md`](./methodology-versions.md) | Schema `{MODULE}_v{MAJOR}.{MINOR}` + bump rules | Toda revisão algorítmica mexe aqui |
| [`patterns.md`](./patterns.md) | 4 architectural patterns (Parallel equals, Hierarchy best-of, Versioning per-table, TE primary + native overrides) | PR dedicado — FROZEN |
| [`normalization.md`](./normalization.md) | `clip(50 + 16.67·z, 0, 100)` score formula | PR dedicado — FROZEN |
| [`composite-aggregation.md`](./composite-aggregation.md) | Policy 1 re-weight fail-mode | PR dedicado — FROZEN |
| [`proxies.md`](./proxies.md) | Proxies registry — proxy vs fallback vs placeholder distinction + registry table | PR dedicado — FROZEN |

## Regra cardinal

Se uma spec precisa introduzir um conceito partilhado (flag nova, exception nova, unidade nova) → **PR que toca primeiro o ficheiro desta pasta**, depois a spec que o usa. Specs fail review se referenciam tokens não catalogados aqui.
