# Daily Overlays Pipeline — Spec

> Layer L8 · pipeline · slug: `daily-overlays` · methodology_version: `DAILY_OVERLAYS_v0.1`
> Last review: 2026-04-19 (Phase 0 Bloco E3)

**Status**: NOT YET IMPLEMENTED (target Phase 2).

## Purpose

Execute the 4 overlays that depend on outputs de `daily-curves`: `erp-daily`, `crp`, `rating-spread`, `expected-inflation`. Ordering respects intra-L2 DAG (e.g. `expected-inflation` pode depender de `nss-curves` forwards).

## Scope

- **In**: orchestração dos 4 overlays L2 pós-curves.
- **Out**: L3+, display, alerts.
- **Schedule**: see master schedule in [`pipelines/README.md`](./README.md).
- **Parallelism**: os 4 overlays são independentes entre si após `daily-curves` → paralelo.

## Cross-references

- Specs algorithm: [`overlays/erp-daily.md`](../overlays/erp-daily.md), [`crp.md`](../overlays/crp.md), [`rating-spread.md`](../overlays/rating-spread.md) (**v0.2 post-Bloco E1 — Damodaran annual backfill + agency scrape forward; TE ratings REJECTED per D0**), [`expected-inflation.md`](../overlays/expected-inflation.md) (INE PT endpoint broken; Eurostat mirror proxy `INE_MIRROR_EUROSTAT`).
- Conventions: [`../conventions/patterns.md`](../conventions/patterns.md) §Pattern 2 (Hierarchy best-of CRP + expected-inflation) + §Pattern 4 (TE primary) · [`../conventions/proxies.md`](../conventions/proxies.md) (proxy registry consumers).
- Architecture: [`../../adr/ADR-0005-country-tiers-classification.md`](../../adr/ADR-0005-country-tiers-classification.md) — tier-aware scheduling inherited from daily-curves.
- Licensing: [`../../governance/LICENSING.md`](../../governance/LICENSING.md) §3 (Shiller/Damodaran/FRED/ECB SDW attribution propagated from overlays).
- Upstream: [`daily-curves.md`](./daily-curves.md)
- Downstream: [`daily-indices.md`](./daily-indices.md)
- D-block: [`../../data_sources/D2_empirical_validation.md`](../../data_sources/D2_empirical_validation.md) §2 TE breadth + §7 INE PT broken findings.

## TODO (Phase 2)

Detailed spec a escrever antes de implementar.
