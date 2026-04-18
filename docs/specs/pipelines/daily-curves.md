# Daily Curves Pipeline — Spec

> Layer L8 · pipeline · slug: `daily-curves` · methodology_version: `DAILY_CURVES_v0.1`
> Last review: 2026-04-19 (Phase 0 Bloco E3)

**Status**: NOT YET IMPLEMENTED (target Phase 2).

## Purpose

Fetch raw sovereign + linker yields from all connectors and run `overlays/nss-curves` for every country in `config/countries.yaml` tiers 1-3 (tier 4 best-effort). Emits 4 sibling curve tables per country-date.

## Scope

- **In**: NSS fit, zero derivation, forwards (1y1y, 1y2y, 1y5y, 5y5y, 10y10y), real curves.
- **Out**: everything else (see [`specs/overlays/nss-curves.md`](../overlays/nss-curves.md) §11).
- **Schedule**: see master schedule in [`pipelines/README.md`](./README.md).
- **Parallelism**: per-country isolation (one slow/failing country must not block others).

## Cross-references

- Algorithm spec: [`overlays/nss-curves.md`](../overlays/nss-curves.md) (post-Bloco E1: aligned tier table com ADR-0005 + Pattern 4 native overrides).
- Connectors envolvidos: `treasury_gov`, `bundesbank`, `boe_yieldcurves`, `mof_japan`, `ecb_sdw`, `igcp`, `fred` (Pattern 4 native overrides per tier); TE breadth para T2 EMs sovereign yields.
- Conventions: [`../conventions/patterns.md`](../conventions/patterns.md) §Pattern 4 · [`../conventions/flags.md`](../conventions/flags.md) (`NSS_SPARSE`, `STALE`, `COVERAGE_TE_DEGRADED`).
- Architecture: [`../../adr/ADR-0005-country-tiers-classification.md`](../../adr/ADR-0005-country-tiers-classification.md) — **tier-aware scheduling: T1 (16) daily mandatory; T2 (30) best-effort com flags-tolerated; T3 (43) weekly batch; T4 (~110) on-demand**.
- Downstream: [`daily-overlays.md`](./daily-overlays.md)
- D-block: [`../../data_sources/D2_empirical_validation.md`](../../data_sources/D2_empirical_validation.md) §3 FRED DGS* fresh validation.

## TODO (Phase 2)

Detailed spec a escrever antes de implementar. Abrir como stub esqueleto com secções 1-10 do template geral.
