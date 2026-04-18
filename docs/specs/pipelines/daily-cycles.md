# Daily Cycles Pipeline — Spec

> Layer L8 · pipeline · slug: `daily-cycles` · methodology_version: `DAILY_CYCLES_v0.1`

**Status**: NOT YET IMPLEMENTED (target Phase 2).

## Purpose

Compute the 4 cycle composite scores (ECS, CCCS, MSC, FCS) + regime overlays (L5: Stagflation, Boom, Dilemma, Bubble Warning) per country-date. Outputs feed integration layer (L6).

## Scope

- **In**: 4 cycle scores + regime detection.
- **Out**: matriz 4-way, diagnostics, cost-of-capital (L6 pipeline).
- **Schedule**: see master schedule in [`pipelines/README.md`](./README.md).
- **Parallelism**: 4 cycles independentes → paralelo. Regimes L5 runs after L4 completo.

## Cross-references

- Specs: [`../cycles/`](../cycles/)
- Regime specs (Phase 2+): `../regimes/` (a criar)
- Upstream: [`daily-indices.md`](./daily-indices.md)
- Downstream: [`weekly-integration.md`](./weekly-integration.md)

## TODO (Phase 2)

Detailed spec a escrever antes de implementar.
