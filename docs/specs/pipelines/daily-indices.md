# Daily Indices Pipeline — Spec

> Layer L8 · pipeline · slug: `daily-indices` · methodology_version: `DAILY_INDICES_v0.1`
> Last review: 2026-04-19 (Phase 0 Bloco E3)

**Status**: NOT YET IMPLEMENTED (target Phase 2).

## Purpose

Compute 16 sub-índices (E1-E4, L1-L4, M1-M4, F1-F4) por country-date consumindo overlays + raw indicators. Outputs normalized (z-score / percentile) feed cycle composites.

## Scope

- **In**: 16 indices L3.
- **Out**: cycle classification (L4) — separate pipeline.
- **Schedule**: see master schedule in [`pipelines/README.md`](./README.md).
- **Parallelism**: 4 cycles × 4 indices = 16; paralelo por ciclo (within-cycle sequential if composite requires).

## Cross-references

- Specs: [`../indices/`](../indices/) — **post-Bloco E2: E2-leading v0.2 (USSLIND removed, LEI GAP pending CAL-023) + M1-effective-rates v0.2 (DFEDTARU+DFEDTARL pair); restantes 14 v0.1 com cross-refs actualizadas.**
- Conventions: [`../conventions/patterns.md`](../conventions/patterns.md) §Pattern 4 (TE primary + native overrides) · [`../conventions/flags.md`](../conventions/flags.md) (`LEI_US_PROXY`, `FED_TARGET_RANGE`, `ZLB_UNADJUSTED`, `PROXY_APPLIED`, `COVERAGE_TE_DEGRADED`) · [`../conventions/composite-aggregation.md`](../conventions/composite-aggregation.md) Policy 1 re-weight.
- Architecture: [`../../adr/ADR-0005-country-tiers-classification.md`](../../adr/ADR-0005-country-tiers-classification.md) — tier-aware scheduling + tier-conditional re-weight integration Phase 1.
- Upstream: [`daily-overlays.md`](./daily-overlays.md)
- Downstream: [`daily-cycles.md`](./daily-cycles.md)
- D-block: [`../../data_sources/D1_coverage_matrix.csv`](../../data_sources/D1_coverage_matrix.csv) series mapping + [`D2_empirical_validation.md`](../../data_sources/D2_empirical_validation.md) §3 FRED validation.

## TODO (Phase 2)

Detailed spec a escrever antes de implementar.
