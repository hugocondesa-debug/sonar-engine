# SONAR · Specs · Pipelines (L8)

Camada de orchestration. Coordena execução ordenada de connectors (L0) → db (L1) → overlays (L2) → indices (L3) → cycles (L4) → regimes (L5) → integration (L6) → outputs (L7).

## Status geral

Phase 0-1 (actual): specs skeleton apenas. Execução manual via CLI `sonar-cli pipeline ...`.

Phase 2+: orchestrator (APScheduler ou Prefect — ver BRIEF_FOR_DEBATE §3) + schedule production.

## Ficheiros

| Ficheiro | Status | Descrição |
|---|---|---|
| [`daily-curves.md`](./daily-curves.md) | **Stub** | Fetch yields + NSS fit para todos os países |
| [`daily-overlays.md`](./daily-overlays.md) | **Stub** | ERP, CRP, rating-spread, expected-inflation |
| [`daily-indices.md`](./daily-indices.md) | **Stub** | 16 sub-índices (E/L/M/F × 1-4) |
| [`daily-cycles.md`](./daily-cycles.md) | **Stub** | Composite scores + regime overlays (L5) |
| [`weekly-integration.md`](./weekly-integration.md) | **Stub** | Rolling recomputes, matriz 4-way transitions |
| [`backfill-strategy.md`](./backfill-strategy.md) | **Stub** | Historical boot, rebackfill, gap-fill |

## Master schedule (source of truth)

**Schedules canonizados aqui; stubs referenciam, nunca duplicam.** Horários são `Europe/Lisbon`. Any change propaga-se via edit deste ficheiro + bump `methodology_version` do pipeline afectado.

| Pipeline | Frequency | Trigger | Timezone | Dependencies |
|---|---|---|---|---|
| `daily-curves` | daily | 09:00 Lisbon | Europe/Lisbon | connectors refreshed |
| `daily-overlays` | daily | 09:30 Lisbon | Europe/Lisbon | `daily-curves` completed |
| `daily-indices` | daily | 10:00 Lisbon | Europe/Lisbon | `daily-overlays` completed |
| `daily-cycles` | daily | 10:15 Lisbon | Europe/Lisbon | `daily-indices` completed |
| `weekly-integration` | weekly (Sun) | 11:00 Lisbon | Europe/Lisbon | all daily completed |
| `backfill-strategy` | on-demand | manual / gap-detection | Europe/Lisbon | — |

Downstream consumers (editorial briefing, alerts, dashboard refresh) arrancam após `daily-cycles` completo — specs a serem escritas em Phase 2+.

## Princípios gerais

- **Idempotency** — mesmo `(country, date)` corrido N vezes produz o mesmo output (insert com `UNIQUE (country, date, methodology_version)` + `ON CONFLICT` upsert).
- **Fail fast** em startup (config inválida); **fail graceful** em runtime (isolate per country — falha em PT não derruba DE).
- **Ordering** respeita camadas: L2 → L3 → L4 → L5 → L6. Dentro de cada layer, isolamento entre slugs permite paralelização.
- **Atomicity**: multi-table writes (ex: 4 sibling tables do NSS) num único `BEGIN/COMMIT`.
- **Confidence propagation**: flags in → `confidence` cap out.
- **Methodology version freeze**: uma pipeline run usa a `methodology_version` current no início; não muda mid-run.

## Cross-refs

- Contratos: [`../conventions/`](../conventions/)
- Overlays: [`../overlays/`](../overlays/)
- Indices, cycles, integration: idem
- Operations runbooks (Phase 8): `docs/operations/runbooks/`
