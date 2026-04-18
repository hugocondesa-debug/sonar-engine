# Daily Curves Pipeline — Spec

> Layer L8 · pipeline · slug: `daily-curves` · methodology_version: `DAILY_CURVES_v0.1`

**Status**: NOT YET IMPLEMENTED (target Phase 2).

## Purpose

Fetch raw sovereign + linker yields from all connectors and run `overlays/nss-curves` for every country in `config/countries.yaml` tiers 1-3 (tier 4 best-effort). Emits 4 sibling curve tables per country-date.

## Scope

- **In**: NSS fit, zero derivation, forwards (1y1y, 1y2y, 1y5y, 5y5y, 10y10y), real curves.
- **Out**: everything else (see [`specs/overlays/nss-curves.md`](../overlays/nss-curves.md) §11).
- **Schedule**: see master schedule in [`pipelines/README.md`](./README.md).
- **Parallelism**: per-country isolation (one slow/failing country must not block others).

## Cross-references

- Algorithm spec: [`overlays/nss-curves.md`](../overlays/nss-curves.md)
- Connectors envolvidos: `treasury_gov`, `bundesbank`, `boe_yieldcurves`, `mof_japan`, `ecb_sdw`, `igcp`, `fred`
- Conventions: [`../conventions/`](../conventions/)
- Downstream: [`daily-overlays.md`](./daily-overlays.md)

## TODO (Phase 2)

Detailed spec a escrever antes de implementar. Abrir como stub esqueleto com secções 1-10 do template geral.
