# Backfill Strategy — Spec

> Layer L8 · pipeline · slug: `backfill-strategy` · methodology_version: `BACKFILL_v0.1`

**Status**: NOT YET IMPLEMENTED (target Phase 2-9 incremental).

## Purpose

Policy canónica para (a) backfill inicial histórico (boot de uma spec nova), (b) rebackfill por bump `methodology_version` MAJOR, (c) recovery depois de connector outage.

## Scope

- **Full historical backfill** — carregar X anos de histórico para um país novo ou spec nova.
- **Selective rebackfill** — recompute `(country, date)` window após MAJOR bump.
- **Gap-fill** — preencher `(country, date)` em falta após outage, com `fetched_at` ajustado.
- **Out**: daily forward-runs (cobertos por `daily-*.md`).
- **Schedule**: on-demand — ver master schedule em [`pipelines/README.md`](./README.md).

## Princípios

- **Methodology freeze per run**: backfill usa UMA `methodology_version` do início ao fim; não mistura.
- **Chronological**: histórico corrido old → new (respeita rolling-window dependencies).
- **Confidence ajustado**: backfilled rows marcadas com flag `BACKFILLED` e possível `HIGH_RMSE` / `EM_COVERAGE` per input quality.
- **Idempotent**: re-running backfill não duplica rows (UNIQUE constraint enforces).
- **Rate limit honoring**: respeita limites de connectors (FRED, ECB SDW).

## Cross-references

- Conventions: [`../conventions/methodology-versions.md`](../conventions/methodology-versions.md) — bump rules trigger rebackfill.
- Flags: [`../conventions/flags.md`](../conventions/flags.md) — `BACKFILLED` a adicionar antes de implementar.
- Historical depth targets: Tier 1 ≥20Y, Tier 2 ≥10Y, Tier 3 best-effort, Tier 4 5Y+.

## TODO (Phase 2+)

Detailed spec antes do primeiro backfill real.
