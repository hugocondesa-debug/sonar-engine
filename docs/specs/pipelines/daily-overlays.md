# Daily Overlays Pipeline — Spec

> Layer L8 · pipeline · slug: `daily-overlays` · methodology_version: `DAILY_OVERLAYS_v0.1`

**Status**: NOT YET IMPLEMENTED (target Phase 2).

## Purpose

Execute the 4 overlays that depend on outputs de `daily-curves`: `erp-daily`, `crp`, `rating-spread`, `expected-inflation`. Ordering respects intra-L2 DAG (e.g. `expected-inflation` pode depender de `nss-curves` forwards).

## Scope

- **In**: orchestração dos 4 overlays L2 pós-curves.
- **Out**: L3+, display, alerts.
- **Schedule**: see master schedule in [`pipelines/README.md`](./README.md).
- **Parallelism**: os 4 overlays são independentes entre si após `daily-curves` → paralelo.

## Cross-references

- Specs algorithm: [`overlays/erp-daily.md`](../overlays/erp-daily.md), [`crp.md`](../overlays/crp.md), [`rating-spread.md`](../overlays/rating-spread.md), [`expected-inflation.md`](../overlays/expected-inflation.md)
- Upstream: [`daily-curves.md`](./daily-curves.md)
- Downstream: [`daily-indices.md`](./daily-indices.md)

## TODO (Phase 2)

Detailed spec a escrever antes de implementar.
