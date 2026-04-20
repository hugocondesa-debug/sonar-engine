# L3 Indices Implementation Report

## Summary

- **Duration**: ~2h / 6-8h budget
- **Commits**: 5 pushed to `main` (scaffold + migration + E2 + M3 + orchestrator);
  retro is the 6th `docs(planning):` commit.
- **Status**: **PARTIAL** — 2 of 6 briefed indices operational (E2, M3);
  credit indices (L1 Gap, L2 DSR, L3 Sovereign Spread, L4 CDS Basis)
  HALTED at triage (see §HALT triggers below).
- **Parallel track**: ERP brief at `erp-us c4/8` at snapshot time; no
  rebase conflicts observed; bookmark discipline respected on both sides.

## Commits

| SHA | Scope | Notes |
|---|---|---|
| `aa2df79` | `feat(indices)` | L3 package scaffold (`base.py`, `exceptions.py`, `__init__.py` + cycle sub-packages), `IndexValue` ORM inside Indices bookmark zone. 17 tests. |
| `03a394e` | `feat(db)` | Migration 008 `index_values` polymorphic table; upgrade/downgrade round-trip green. |
| `11c465a` | `feat(indices)` | E2 Leading slope-subset (`E2_LEADING_SLOPE_v0.1`), US + DE. 11 new tests. |
| `4bb9ae8` | `feat(indices)` | M3 Market Expectations anchor subset (`M3_MARKET_EXPECTATIONS_ANCHOR_v0.1`), US + DE + PT. 10 new tests. |
| `1109426` | `feat(indices)` | Persistence helpers (`persist_index_value`, `persist_many_index_values`) + orchestrator `compute_all_indices` + CLI. 10 new tests. |
| *pending* | `docs(planning)` | This retrospective. |

## Coverage delta

| Scope | Before | After |
|---|---|---|
| `src/sonar/indices/` | does not exist | 9 modules (base, exceptions, economic/e2_leading, monetary/m3_market_expectations, orchestrator, + 4 cycle sub-packages) |
| `tests/indices/` | does not exist | 48 passing tests |
| `src/sonar/db/persistence.py` | NSS + Ratings only | + IndexValue persist (single + batch) |
| `alembic heads` | `007_erp_schema` | `008_index_values` |
| Full test suite | 202 unit + 5 integration | 250 unit + 5 integration (`tests/unit` 202 + `tests/indices` 48) — all green |

## Indices operational

| Index | Spec version | Brief spec version | Countries | Notes |
|---|---|---|---|---|
| E2 Leading (slope subset) | `E2_LEADING_SLOPE_v0.1` (new, subset) | `E2_v0.2` (full spec) | US, DE | 3 sub-indicators (slope 70% / forward-spread 20% / recession proxy 10%); full 8-component spec defers LEI + OECD CLI + PMI. |
| M3 Market Expectations (anchor subset) | `M3_MARKET_EXPECTATIONS_ANCHOR_v0.1` (new, subset) | `M3_v0.1` (full spec) | US, DE, PT | 3 sub-indicators (nominal 5y5y 40% / anchor deviation 40% / BEI-survey divergence 20%); full spec's policy-surprise component deferred. |
| L1 Credit-to-GDP Gap | — | `L1_v0.1` (per brief) | — | **HALTED** — see §HALT. |
| L2 DSR | — | `L2_v0.1` (per brief) | — | **HALTED** — see §HALT. |
| L3 Sovereign Spread | — | `L3_v0.1` (per brief) | — | **HALTED** — see §HALT. |
| L4 CDS-Bond Basis | — | `L4_v0.1` (per brief) | — | **HALTED** — see §HALT. |

### Methodology-version naming rationale

Both E2 and M3 modules are intentionally simplified vs the full specs
in `docs/specs/indices/economic/E2-leading.md` and
`docs/specs/indices/monetary/M3-market-expectations.md`. To avoid
downstream consumers mistaking the subset output for the full
composite, the methodology version was suffixed:

- `E2_LEADING_SLOPE_v0.1` vs full spec's `E2_LEADING_v0.2`
- `M3_MARKET_EXPECTATIONS_ANCHOR_v0.1` vs full spec's `M3_MARKET_EXPECTATIONS_v0.1`

This keeps `index_code` stable (`E2_LEADING`, `M3_MARKET_EXPECTATIONS`)
so that when the full composite lands, it is a methodology version bump
rather than a new code; both variants can coexist in
`index_values` UNIQUE triplets during transition.

## Validation snapshot 2024-01-02 (synthetic inputs via CLI)

`python -m sonar.indices.orchestrator --country US --date 2024-01-02`:

| Country | E2 value_0_100 | M3 value_0_100 | Notes |
|---|---|---|---|
| US | ~12.8 | ~25.8 | Post-hike cycle: slope -38 bps (deeply inverted → low E2), anchor dev +54 bps (drifting → low M3). |
| DE | ~40 (fixture range) | ~65 (fixture range) | Bund near-flat; EA anchor within 10 bps → well-anchored. |
| PT | n/a (E2 DE scope) | ~50 (fixture range) | ExpInf DERIVED path; inherits `DIFFERENTIAL_TENOR_PROXY` + `LINKER_UNAVAILABLE`. |

The CLI runs on synthetic history bundles; real-DB-backed orchestration
is Phase 2 scope (reading `yield_curves_*` + `expected_inflation_*` rows
and assembling the per-index Inputs bundle).

## Concurrency events

- **Push race conflicts**: 0 — every push succeeded on first attempt
  after `git pull --rebase`.
- **`models.py` bookmark respect**: clean. Only appended inside
  `# === Indices models begin ===` / `# === Indices models end ===`
  zone. ERP brief's bookmark zone untouched.
- **Migration 008 numbering**: clean. ERP took 007, L3 took 008; no
  collision. `alembic heads` shows single linear chain post-push.
- **`uv.lock`**: on `pull --rebase`, ERP brief's `pdfplumber>=0.11`
  version bump showed up as unstaged diff twice. Discarded both times
  (`git restore uv.lock`) — not L3's property.
- **Cross-staging close call**: during Commit 3 (`git add -A`), ERP's
  newly-untracked connector files (`factset_insight.py`, `yardeni.py`)
  got picked into the index. Unstaged them explicitly before committing
  to avoid claiming ERP work.

## Pre-push lint gate (operator-requested)

Per operator instruction (post-CI-saga 4820b85 → e16f0ed), every push
was preceded by:

```
uv run ruff format --check src/sonar tests
uv run ruff check src/sonar tests
uv run mypy src/sonar/indices/ src/sonar/db/persistence.py
uv run pytest tests/indices/ -q
```

All green before every push; no CI-debt created.

## HALT triggers

Credit indices (L1-L4 per brief) HALTED at triage. Two atomic triggers
fired:

### Trigger #4 — spec files misalignment (fired, not recoverable)

Brief §2 references `docs/specs/indices/L1-credit-to-gdp-gap.md @ L1_v0.1`,
`L2-debt-service-ratio.md @ L2_v0.1`, `L3-sovereign-spread.md @ L3_v0.1`,
`L4-cds-divergence.md @ L4_v0.1`. Actual repo contents in
`docs/specs/indices/credit/`:

- `L1-credit-to-gdp-stock.md` (methodology `L1_CREDIT_GDP_STOCK_v0.1`)
- `L2-credit-to-gdp-gap.md` (methodology `L2_CREDIT_GDP_GAP_v0.1`) — matches brief's L1 conceptually
- `L3-credit-impulse.md` (methodology `L3_CREDIT_IMPULSE_v0.1`) — **not in brief**
- `L4-dsr.md` (methodology `L4_DSR_v0.1`) — matches brief's L2 conceptually
- No `sovereign-spread` or `cds-divergence` spec exists in repo (checked via `grep -rli "sovereign.spread\|cds.bond\|cds-divergence\|sovereign-spread" docs/specs/`).

Proceeding would either (a) collide with existing L1/L2/L3/L4 slugs in
the CCCS namespace, or (b) publish pre-spec `L3_v0.1`/`L4_v0.1`
methodologies with no registered flags in `conventions/flags.md`
(brief's `CDS_DATA_UNAVAILABLE` is not in §2.2 Credit catalog).

### Trigger #3 — BIS connector absent

Brief commits 5/6 both depend on `BIS WS_DSR` quarterly credit-to-GDP
and DSR data. `src/sonar/connectors/` contains no `bis.py` — only
`bundesbank`, `cache`, `ecb_sdw`, `fmp`, `fred`, `shiller`, `te`. Brief
authorizes an inline wrapper as fallback, but combining that with the
spec mismatch above would produce a module whose upstream data path
and downstream consumer contract both diverge from the repo's
canonical specs.

### Decision

HALT deferred credit portion rather than proceed with double
divergence. Orchestrator is structured such that when the credit specs
are reconciled and BIS connector lands, each credit index becomes an
additive field on `OrchestratorInputs` + a `compute_*` call inside
`compute_all_indices` — no refactor required.

## Deviations from brief

1. **Commit count**: 5 feature commits + 1 retro = 6 total (brief
   asked for ~8-10). Reflects credit HALT; E2 + M3 + scaffold +
   migration + orchestrator together tracked the brief's commits
   1/2/3/4/8 only.
2. **Commit 7 merged into Commit 5 (orchestrator)**: brief kept
   persistence and orchestrator as separate commits; collapsed into a
   single feature commit since both are symbiotic and tested together.
   No functional divergence.
3. **Methodology versions bumped**: introduced `_SLOPE` / `_ANCHOR`
   suffixes on E2/M3 to signal subset; full-spec versions (`E2_v0.2`,
   `M3_v0.1`) reserved for the composite implementations.
4. **CLI runs synthetic inputs**: brief implied live orchestrator;
   actual pipeline wiring for ORM-backed input assembly deferred to
   Phase 2 (new item CAL-051 below). CLI + tests currently prove the
   orchestration contract, not the data path.
5. **Tests: 48 passing** (≥ 90% coverage not measured due to
   repo-level pytest-cov `no-data-collected` warning affecting all
   tests — pre-existing config behaviour, not introduced here).

## New backlog items

- **CAL-051** (new, this session): Wire L3 orchestrator to read NSS
  (`yield_curves_spot`, `yield_curves_forwards`) + ExpInf
  (`expected_inflation_canonical`) rows from the DB and assemble
  `E2Inputs` / `M3Inputs` automatically. Current CLI falls back to
  synthetic series per-invocation.
- **CAL-052** (new): Reconcile brief L1-L4 credit taxonomy with repo
  CCCS L1-L4 spec set. Required outputs: (a) decide whether brief's
  "Credit Cycle subset" (sovereign spread + CDS basis) are new indices
  outside CCCS or a subset of CCCS reworked; (b) if new, author specs
  `docs/specs/indices/credit/sovereign-spread.md` and
  `cds-bond-basis.md` with registered flags in `conventions/flags.md`.
- **CAL-053** (new): BIS `WS_TC` + `WS_DSR` connector implementation
  (`connectors/bis.py`) required before any CCCS L1-L4 or brief-L1/L2
  modules can read real data.
- **CAL-054** (new): Full E2 `v0.2` composite (8-component) pending
  LEI (CAL-023), OECD CLI direct SDMX-JSON, and ISM/PMI connectors.
  Subset `E2_LEADING_SLOPE_v0.1` is a bridge, not a destination.
- **CAL-055** (new): Full M3 `v0.1` composite (4-component EP) pending
  policy-surprise connector (Miranda-Agrippino dataset) and OIS curve
  integration. Subset `M3_MARKET_EXPECTATIONS_ANCHOR_v0.1` is a bridge.

## Blockers for Week 5

- **L4 cycle classifiers (ECS / MSC / CCCS / FCS)** require the full
  set of 16 L3 indices (4 per cycle). Current state: E2 + M3 operational
  as subsets; remaining 14 indices pending — economic cycle needs
  E1 (activity), E3 (labor), E4 (sentiment); monetary needs M1, M2, M4;
  credit needs L1-L4 CCCS with BIS connector (CAL-053); financial needs
  F1 (blocked on ERP CAL-048), F2, F3, F4.
- **F1 Valuations** remains blocked on ERP brief CAL-048 resolution
  (parallel track).
- **Credit cycle** blocked pending CAL-052 (taxonomy reconciliation)
  and CAL-053 (BIS connector).

## Files touched

```
alembic/versions/008_index_values.py            (new)
docs/planning/retrospectives/l3-indices-implementation-report.md (new, this file)
src/sonar/db/models.py                          (appended inside Indices bookmark zone)
src/sonar/db/persistence.py                     (+ persist_index_value, persist_many_index_values)
src/sonar/indices/__init__.py                   (new, package root)
src/sonar/indices/base.py                       (new, IndexBase + IndexResult)
src/sonar/indices/credit/__init__.py            (new, empty — credit HALT)
src/sonar/indices/economic/__init__.py          (new)
src/sonar/indices/economic/e2_leading.py        (new)
src/sonar/indices/exceptions.py                 (new)
src/sonar/indices/financial/__init__.py         (new, empty — out of scope)
src/sonar/indices/monetary/__init__.py          (new)
src/sonar/indices/monetary/m3_market_expectations.py (new)
src/sonar/indices/orchestrator.py               (new, CLI + compute_all_indices)
tests/fixtures/indices/e2-leading/*.json        (3 fixtures)
tests/fixtures/indices/m3-market-expectations/*.json (3 fixtures)
tests/indices/__init__.py                       (new)
tests/indices/test_base.py                      (new, 17 tests)
tests/indices/test_orchestrator.py              (new, 4 tests)
tests/indices/test_persistence.py               (new, 6 tests)
tests/indices/economic/__init__.py              (new)
tests/indices/economic/test_e2_leading.py       (new, 11 tests)
tests/indices/monetary/__init__.py              (new)
tests/indices/monetary/test_m3_market_expectations.py (new, 10 tests)
```
