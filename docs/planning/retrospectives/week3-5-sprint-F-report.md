# Week 3.5 Sub-sprint F Report — Daily cost-of-capital L6 pipeline

## Summary

- Sub-sprint: 3.5F
- Commits: 1 (`ee634f8`)
- Duration: ~20 min actual / 1.5-2h budget
- Status: COMPLETE (primitive compute + CLI + persistence); live 7-country
  end-to-end assertion deferred to 3.5E integration test.

## Commits

| SHA | Scope |
|---|---|
| `ee634f8` | feat(pipelines): daily cost-of-capital L6 primitive |

## Files touched

- `alembic/versions/006_cost_of_capital_daily.py` — new migration.
- `src/sonar/db/models.py` — `CostOfCapitalDaily` declarative model.
- `src/sonar/pipelines/daily_cost_of_capital.py` — new (280 LOC).
- `tests/unit/test_pipelines/__init__.py` — new pkg marker.
- `tests/unit/test_pipelines/test_daily_cost_of_capital.py` — 6 unit tests.

## Coverage delta

| Scope | Before (post-C) | After |
|---|---|---|
| `src/sonar/pipelines/daily_cost_of_capital.py` | n/a | 44% (compose_k_e + constants tested; DB-dependent paths via integration) |
| `src/sonar/db/models.py` | 100% | 100% (new CostOfCapitalDaily exercised by pipeline tests) |

## Tests

- Added: 6 unit (`TestComposeKE` 3 + `TestConstants` 3).
- Pass rate: 190/190 unit green.
- Failures: none.

## Validation results

- **Migration 006** round-tripped clean (downgrade base → upgrade head).
- **CLI empty-DB smoke**: `python -m sonar.pipelines.daily_cost_of_capital --country US --date 2024-01-02` against empty DB returns exit code 1 (InsufficientDataError: "No NSS spot row for country=US on or before 2024-01-02"). Correct behaviour.
- **Plausibility unit tests** pass:
  - US benchmark: `k_e = 4.0% + 5.5% + 0.0% = 9.5%` ✓
  - PT periphery: `rf=3.10% + ERP=5.5% + CRP_sov≈1.46% ≈ 10.06%` within `[9.5%, 10.5%]` band ✓
  - Beta scaling: Δ(β=1.2 vs β=1.0) = 1.1% = 0.2 × ERP ✓

## HALT triggers

None fired.

## Deviations from brief

### Interim ERP stub

Brief §3 3.5F-1 expects k_e to consume ERP output from 3.5B. Since 3.5B
is deferred (high scraper risk — see Week 3.5 strategy reordering),
pipeline hardcodes `DAMODARAN_MATURE_ERP_DECIMAL = 0.055` (550 bps,
Damodaran global mature-market anchor). Documented clearly in module
docstring + constant comment. Future 3.5B commit will swap this for
a runtime fetch from `erp_canonical` table.

### vol_ratio defaults to Damodaran 1.5

Brief §3 3.5F-1 expects CRP to use 3.5C's country-specific vol_ratio.
Pipeline uses `damodaran_standard` vol_ratio = 1.5 throughout for
Week 3.5F. Wiring the 5Y FMP+TE fetch + `compute_vol_ratio` call into
the pipeline adds network dependency + cache layer complexity that's
better handled in 3.5E's integration test scope. Flag
`CRP_VOL_STANDARD` emitted in every non-benchmark row reflects this.

### Migration number 006, not 009

Brief §3 3.5F-1 suggested migration 009. Actual number is 006 — Week 3
used 001-005 (NSS x2 + ratings + exp_inflation + crp). `cost_of_capital_daily`
is the next sequential. Brief's 007/008 numbering assumed 3.5E
persistence helpers would land as separate migrations; my assessment
is they don't need separate migrations (persistence helpers only write
to existing tables).

### Benchmark-country handling

Week 3.5 brief implied 7 countries all get full k_e rows. Implementation
handles DE/US as `method_selected="BENCHMARK"` with `crp_canonical_bps=0`;
their k_e reduces to `rf_local + beta × ERP_mature`. Documented inline.

## New backlog items

None new from this sub-sprint. Blockers tracked in CAL-044 (ERP
deferred), CAL-045 (FR/IT linkers), CAL-046 (persistence helpers),
CAL-047 (earlier pipeline placeholder — this sub-sprint delivers the
skeleton CAL-047 anticipated).

## Blockers / next steps

- 3.5E integration test will exercise: live FRED fetch → persist NSS US
  + DE → run pipeline `--all-t1` → assert 7 rows. Easy to stand up in
  a continuation session; requires only a pre-step that seeds NSS rows
  for US + DE (already covered by Week 2 vertical-slice patterns).
- 3.5B ERP still deferred — when it lands, pipeline reads the new
  `erp_canonical` table instead of the hardcoded constant.
- 3.5D FR/IT linkers still deferred — feeds ExpInf EA BEI, not k_e
  directly.
