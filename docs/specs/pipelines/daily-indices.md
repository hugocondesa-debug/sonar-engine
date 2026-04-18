# Daily Indices Pipeline — Spec

> Layer L8 · pipeline · slug: `daily-indices` · methodology_version: `DAILY_INDICES_v0.1`

**Status**: NOT YET IMPLEMENTED (target Phase 2).

## Purpose

Compute 16 sub-índices (E1-E4, L1-L4, M1-M4, F1-F4) por country-date consumindo overlays + raw indicators. Outputs normalized (z-score / percentile) feed cycle composites.

## Scope

- **In**: 16 indices L3.
- **Out**: cycle classification (L4) — separate pipeline.
- **Schedule**: see master schedule in [`pipelines/README.md`](./README.md).
- **Parallelism**: 4 cycles × 4 indices = 16; paralelo por ciclo (within-cycle sequential if composite requires).

## Cross-references

- Specs: [`../indices/`](../indices/)
- Upstream: [`daily-overlays.md`](./daily-overlays.md)
- Downstream: [`daily-cycles.md`](./daily-cycles.md)

## TODO (Phase 2)

Detailed spec a escrever antes de implementar.
