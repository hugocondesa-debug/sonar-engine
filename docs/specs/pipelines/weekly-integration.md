# Weekly Integration Pipeline — Spec

> Layer L8 · pipeline · slug: `weekly-integration` · methodology_version: `WEEKLY_INTEG_v0.1`

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
- Convention: [`../conventions/methodology-versions.md`](../conventions/methodology-versions.md) — MINOR bumps triggered por calibration drift.

## TODO (Phase 3+)

Detailed spec quando integration layer arrancar.
