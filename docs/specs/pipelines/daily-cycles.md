# Daily Cycles Pipeline — Spec

> Layer L8 · pipeline · slug: `daily-cycles` · methodology_version: `DAILY_CYCLES_v0.1`
> Last review: 2026-04-19 (Phase 0 Bloco E3)

**Status**: NOT YET IMPLEMENTED (target Phase 2).

## Purpose

Compute the 4 cycle composite scores (ECS, CCCS, MSC, FCS) + regime overlays (L5: Stagflation, Boom, Dilemma, Bubble Warning) per country-date. Outputs feed integration layer (L6).

## Scope

- **In**: 4 cycle scores + regime detection.
- **Out**: matriz 4-way, diagnostics, cost-of-capital (L6 pipeline).
- **Schedule**: see master schedule in [`pipelines/README.md`](./README.md).
- **Parallelism**: 4 cycles independentes → paralelo. Regimes L5 runs after L4 completo.

## Cross-references

- Specs: [`../cycles/`](../cycles/) — ECS/CCCS/MSC/FCS v0.1 (cycles são abstract layer; E2/M1 v0.2 bumps upstream consumed via sub-index methodology_version preconditions).
- Regime specs (Phase 2+): `../regimes/` (a criar)
- Conventions: [`../conventions/composite-aggregation.md`](../conventions/composite-aggregation.md) Policy 1 fail-mode · [`../conventions/flags.md`](../conventions/flags.md) (`COVERAGE_TE_DEGRADED` emergency re-weight quando TE rate limit/outage → T2-T3 breadth affected, Policy 1 activado).
- Architecture: [`../../adr/ADR-0005-country-tiers-classification.md`](../../adr/ADR-0005-country-tiers-classification.md) — **tier-aware scheduling canonical: T1 daily mandatory (SLO estrito), T2 best-effort (flags-tolerated), T3 weekly batch, T4 on-demand**; per-tier confidence cap integration Phase 1+ (T2 0.85 / T3 0.65 / T4 fail aligns com ADR-0005 §Consequences).
- Upstream: [`daily-indices.md`](./daily-indices.md)
- Downstream: [`weekly-integration.md`](./weekly-integration.md)

## TODO (Phase 2)

Detailed spec a escrever antes de implementar.
