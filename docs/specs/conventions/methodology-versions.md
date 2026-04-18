# Methodology Versions · Schema & Bump Rules

Toda row persistida transporta `methodology_version TEXT NOT NULL`. Permite reproduzir historicamente, backfill selectivo, e cross-check quando spec muda.

## Formato

```
{MODULE}_{VARIANT?}_v{MAJOR}.{MINOR}
```

- `MODULE`: UPPER_SNAKE_CASE · slug da spec · ex: `NSS`, `ERP`, `CRP`, `RATING_SPREAD`, `CCCS`, `MATRIZ_4WAY`.
- `VARIANT` (optional): UPPER_SNAKE_CASE · quando o mesmo module tem múltiplos methods · ex: `DCF`, `GORDON`, `EY`, `CAPE` dentro de `ERP`.
- `MAJOR.MINOR`: inteiros.

### Exemplos válidos

| Version | Módulo / variant |
|---|---|
| `NSS_v0.1` | NSS overlay, v0.1 |
| `ERP_DCF_v0.1` | ERP overlay, DCF method |
| `ERP_CAPE_v0.1` | ERP overlay, CAPE method |
| `CRP_CDS_v0.1` | CRP overlay, CDS-based |
| `CRP_SOVEREIGN_SPREAD_v0.1` | CRP overlay, sovereign-spread fallback |
| `CCCS_COMPOSITE_v0.1` | CCCS cycle composite score |
| `MATRIZ_4WAY_v0.1` | Integration · matriz 4-way classifier |

### Proibido

- `nss-v0.1` (lowercase)
- `NSSv0.1` (missing underscore + dot)
- `NSS_v0.1.2` (patch não existe — see bump rules)
- Datas em vez de MAJOR.MINOR.

## Bump rules

| Mudança | Bump | Backfill necessário? |
|---|---|---|
| Nova column *nullable* em tabela output | MINOR | não |
| Re-calibração (weights, thresholds, bounds) | MINOR | sim, selectivo por country |
| Nova flag adicional (sem remover anteriores) | MINOR | não |
| Fix bug sem mudar output para mesmo input | MINOR | opcional |
| Mudança de fórmula / algoritmo core | **MAJOR** | sim, full re-run |
| Schema breaking (rename column, drop, FK novo) | **MAJOR** | sim, migration obrigatória |
| Mudança de unidade (ex: bps → decimal) | **MAJOR** | sim, full re-run |
| Mudança no significado de um output (ex: CRP definition) | **MAJOR** | sim, full re-run + editorial note |

## Storage

Toda tabela SONAR tem:

```sql
methodology_version TEXT NOT NULL,
UNIQUE (country_code, date, methodology_version)
```

**Duas rows com mesmo `(country, date)` e diferentes versions coexistem** — a newer é servida por default, a older fica para auditoria / reproducibilidade.

View convention:

```sql
CREATE VIEW v_latest_<slug> AS
SELECT * FROM <table>
WHERE (country_code, date, methodology_version) IN (
    SELECT country_code, date, MAX(methodology_version)
    FROM <table>
    GROUP BY country_code, date
);
```

## Ciclo de vida de uma bump

1. **Spec edit** — atualizar spec com nova `methodology_version` no header + descrição da mudança em §10 Reference.
2. **Migration** — se schema change, Alembic revision + upgrade path.
3. **Code** — constante `METHODOLOGY_VERSION` no module bump.
4. **Backfill** — se MAJOR, scheduled job re-executa `(country, date)` history.
5. **Editorial note** — se mudança material afeta signals já publicados, registar em changelog.

## Matriz de responsabilidade

| Quem | O quê |
|---|---|
| Autor da spec | Decide MINOR vs MAJOR |
| Reviewer | Challenge: "isto é realmente MINOR?" |
| Implementador | Garante `METHODOLOGY_VERSION` constante em sync |
| Backfill job | Corre em nova version MAJOR; SELECTIVE em MINOR |

## Estado atual (v0.1 — nenhum production)

Todas as specs arrancam em `_v0.1`. Primeira bump esperada após backtesting (Phase 9) validar calibrações.
