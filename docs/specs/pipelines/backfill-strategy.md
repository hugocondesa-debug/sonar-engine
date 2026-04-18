# Backfill Strategy — Spec

> Layer L8 · pipeline · slug: `backfill-strategy` · methodology_version: `BACKFILL_v0.1`
> Last review: 2026-04-19 (Phase 0 Bloco E3)

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

- Conventions: [`../conventions/methodology-versions.md`](../conventions/methodology-versions.md) — bump rules trigger rebackfill · [`../conventions/patterns.md`](../conventions/patterns.md) §Pattern 3 (Versioning per-table — rating-spread 3 tables bump independent) · [`../conventions/proxies.md`](../conventions/proxies.md) (proxy applicability per historical vintage).
- Flags: [`../conventions/flags.md`](../conventions/flags.md) — `BACKFILLED` já catalogado §Futuras (a promote quando primeiro backfill real).
- Architecture: [`../../adr/ADR-0005-country-tiers-classification.md`](../../adr/ADR-0005-country-tiers-classification.md) — **historical depth targets per tier: T1 ≥20Y, T2 ≥10Y, T3 ≥7Y, T4 5Y+ (aligned com ADR-0005 §Decision tier scope + ADR-0005 §Review triggers para tier promotion).**
- **Rating-spread v0.2 (Bloco E1) historical backfill path**: pre-2023 via `connectors/damodaran_annual_historical` (`histimpl.xlsx` annual since 1994, ~170 countries); forward ≥2023 via agency scrape connectors (S&P/Moody's/Fitch/DBRS). TE ratings REJECTED D0 (4Y stale) — não usar em backfill.
- **M1-effective-rates v0.2 historical**: pre-2008 usar `DFEDTAR` (legacy, válido pré-discontinuation); post-2008-12-15 usar `DFEDTARU`+`DFEDTARL` pair midpoint OR `FEDFUNDS` effective rate (per v0.2 swap).
- **E2-leading v0.2 historical**: `USSLIND` data 1979-2020 válido (pré-discontinuation 2020-02); post-2020 = GAP pending CAL-023 resolução.
- D-block: [`../../data_sources/D0_audit_report.md`](../../data_sources/D0_audit_report.md) + [`D2_empirical_validation.md`](../../data_sources/D2_empirical_validation.md) documentam stale/broken sources históricos para backfill exclusion rules.

## TODO (Phase 2+)

Detailed spec antes do primeiro backfill real.
