# Weekly Integration Pipeline — Spec

> Layer L8 · pipeline · slug: `weekly-integration` · methodology_version: `WEEKLY_INTEG_v0.1`
> Last review: 2026-04-19 (Phase 0 Bloco E3)

**Status**: NOT YET IMPLEMENTED (target Phase 3+).

## Purpose

Recompute integration layer outputs que têm cadência fraca ou janelas rolling longas: matriz 4-way transition probabilities, 5Y rolling vol ratios (CRP), PT-EA inflation differential, calibration drift checks.

## Scope

- **In**: rolling-window recomputes + transition probability tracking.
- **Out**: daily classification (já corre em `daily-cycles`).
- **Schedule**: see master schedule in [`pipelines/README.md`](./README.md).

## Cross-references

- Specs: [`../integration/`](../integration/) (Phase 2+)
- Upstream: histórico de 5 dias de `daily-cycles` runs.
- Conventions: [`../conventions/methodology-versions.md`](../conventions/methodology-versions.md) — MINOR bumps triggered por calibration drift · [`../conventions/patterns.md`](../conventions/patterns.md) §Pattern 4 (override matrix maintenance).
- Architecture: [`../../adr/ADR-0005-country-tiers-classification.md`](../../adr/ADR-0005-country-tiers-classification.md) — T3 weekly batch window é esta pipeline; T2 rolling recompute aqui quando daily flags excedem threshold.
- D-block ops: [`../../data_sources/D2_empirical_validation.md`](../../data_sources/D2_empirical_validation.md) §10 **TE observation mode Phase 1: 7-14 dias com 5-10 T1 pilot countries; Hugo monitoriza TE Premium dashboard quota; weekly review trigger**. Post-observation tier sizing decision (Premium adequate? Enterprise? Downgrade Standard?).

## TODO (Phase 3+)

Detailed spec quando integration layer arrancar.
