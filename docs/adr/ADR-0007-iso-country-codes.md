# ADR-0007: ISO 3166-1 alpha-2 canonical country codes

**Status**: Accepted
**Data**: 2026-04-21
**Decisores**: Hugo Condesa (solo operator)
**Consultados**: Claude Code (Sprint O rename implementation)

## Contexto

Sprint I (Week 8 Day 1) shipped BoE connector + UK monetary indices
usando convenção interna `"UK"`. Todos os outros T1 countries (US, DE,
PT, IT, ES, FR, NL) já usam canonical ISO 3166-1 alpha-2 codes. O
código ISO 3166-1 alpha-2 oficial para United Kingdom é **`GB`** (o
sufixo `.uk` é convenção ccTLD separada, não assignada formalmente
em ISO 3166-1). `country_tiers.yaml` já regista o entry correcto
(`iso_code: GB, aliases: [UK]`).

Inconsistência catalogada em Sprint I retro §Deviations como **CAL-128**:

| Superfície | Convenção actual | Canonical |
|---|---|---|
| `country_tiers.yaml` | `GB` (já corrigido; `aliases: [UK]`) | `GB` ✓ |
| `r_star_values.yaml` | `UK` | `GB` (rename) |
| `bc_targets.yaml` | `UK` | `GB` (rename) |
| `TE_10Y_SYMBOLS` (te.py) | `UK` | `GB` (rename + alias) |
| `TE_COUNTRY_NAME_MAP` (te.py) | `UK` | `GB` (rename + alias) |
| `fetch_uk_bank_rate` (te.py) | `UK` | `fetch_gb_bank_rate` + alias |
| `TIER_1_STRICT_COUNTRIES` (financial_fcs) | `UK` | `GB` (with UK alias) |
| `BENCHMARK_*_BY_CURRENCY` (live_assemblers + crp) | `UK` | `GB` |
| `COUNTRY_TO_CURRENCY` (daily_cost_of_capital) | `UK` | `GB` |
| `MONETARY_SUPPORTED_COUNTRIES` (daily_monetary_indices) | `UK` | `GB` (with UK alias) |
| `builders.py` M1 UK cascade | `UK` | deferred to CAL-128 final chore post Sprint L merge |
| FRED series IDs | já uses `GB` (e.g. `IRLTLT01GBM156N`) | `GB` ✓ |
| BIS series | full country name (`United Kingdom`) — não affected | n/a |

## Decisão

1. **Canonical code**: ISO 3166-1 alpha-2 → `"GB"` para United Kingdom
   em todos os lookup points, config keys, connector mappings,
   pipeline country lists, test `country_code` references.
2. **Migration path**: rename `"UK"` → `"GB"` em superfícies listadas
   acima (Sprint O Day 4), preservando carve-out em
   `src/sonar/indices/monetary/builders.py` (Sprint L domain;
   post-merge chore commit finaliza).
3. **Backward compatibility**: mantém `"UK"` como deprecated alias em
   pontos críticos (TE_10Y_SYMBOLS, TE_COUNTRY_NAME_MAP,
   `fetch_uk_bank_rate`, `resolve_r_star`, `resolve_inflation_target`,
   pipeline `MONETARY_SUPPORTED_COUNTRIES`, `TIER_1_STRICT_COUNTRIES`)
   com `structlog` deprecation warnings. Removal planejada para Week
   10 Day 1 (2 releases ahead; ~2 semanas sustained production).
4. **Exceptions**:
   - Retrospectives historical: preservados archival; não re-escritos.
   - FRED series names: já usam `GB` nativamente (`IRLTLT01GBM156N`,
     `IRSTCI01GBM156N`); no change.
   - BIS: full country names (`United Kingdom`); unaffected.
   - `BoEDatabaseConnector` class name: `BoE` é proper noun (Bank of
     England), preservado.

## Alternativas consideradas

- **Manter `UK`**: rejeitado — inconsistente com o resto do codebase,
  ISO non-compliant, complica auto-integração de APIs externas que
  esperam alpha-2.
- **Rename para ISO 3166-1 alpha-3 (`GBR`)**: rejeitado — todos os
  outros countries usam alpha-2; uniformity maior valor que alpha-3
  disambiguation.
- **Deprecation period only (sem rename)**: rejeitado — kicks debt
  indefinitely; ISO compliance é melhor cimentada imediatamente.
- **Big-bang rename (no backward compat aliases)**: rejeitado — breaks
  operator workflows (`--country UK` CLI invocation). Soft migration
  preserves UX com deprecation warnings.

## Consequências

### Positivas

- ISO 3166-1 alpha-2 compliance completa T1 countries.
- Internal consistency: single country-code convention cross-module.
- Easier automated data-source integration: external APIs (FRED,
  Eurostat, TE) esperam alpha-2.
- Deprecation warnings fornecem migration signal auditable para
  operators que ainda usam `UK`.

### Negativas / trade-offs aceites

- 1-time sweep across ~12 files + tests.
- Post-merge chore commit coupling: Sprint L's `builders.py` adiciona
  JP path preservando UK refs; Sprint O não toca; final chore sweep
  é required post ambos os merges (encoded em CAL-128 closure
  action).
- Backward compat aliases adicionam transitional complexity (~6
  alias points) — removal planejada 2 releases.
- Persisted DB rows de pre-rename continuam com `country_code="UK"`;
  compatibility mantida via alias resolvers mas queries downstream
  precisam aceitar ambos durante window de transição.

## Implementation references

- [`../backlog/calibration-tasks.md`](../backlog/calibration-tasks.md) — CAL-128 formalization.
- [`../planning/retrospectives/week8-sprint-i-boe-connector-report.md`](../planning/retrospectives/week8-sprint-i-boe-connector-report.md) §Deviations — CAL-128 origin.
- [`../planning/week8-sprint-o-gb-uk-rename-brief.md`](../planning/week8-sprint-o-gb-uk-rename-brief.md) — Sprint O scope.
- [`../data_sources/country_tiers.yaml`](../data_sources/country_tiers.yaml) — canonical tier assignments (GB + UK alias).

## Review triggers

Este ADR é re-visitado (não auto-superseded) quando:

1. **Week 10 Day 1** — deprecation removal planned. Aliases retirados
   se zero CI warnings em production sustained. Commit referencia
   CAL-128 final closure.
2. **Novos country codes** entrando no codebase: ISO 3166-1 alpha-2
   obrigatório, sem alias duality. ADR preempte non-compliant
   additions.
3. **Database migration**: quando persisted rows com
   `country_code="UK"` forem re-backfilled (Phase 2+), normalizar
   para `"GB"`.

## Decision makers

- **Hugo Condesa** (solo operator, 7365 Capital): autoriza canonical
  convention + deprecation timeline.
- **Claude Code** (Sprint O autonomous executor): implementation.

## Referências

- [`ADR-0005-country-tiers-classification.md`](ADR-0005-country-tiers-classification.md) — country tiers (convention `iso_code: alpha-2 uppercase`).
- [`../planning/retrospectives/week8-sprint-i-boe-connector-report.md`](../planning/retrospectives/week8-sprint-i-boe-connector-report.md) — CAL-128 origin.
- ISO 3166-1 standard — alpha-2 uppercase.
