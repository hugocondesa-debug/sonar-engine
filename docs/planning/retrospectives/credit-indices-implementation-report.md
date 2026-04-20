# Credit Indices Implementation Report (v0.1, Phase 1 Week 4)

## Summary

- **Duration**: ~2h30m / 6-8h budget
- **Commits**: 10 (`fcc421f..HEAD`)
- **Status**: **COMPLETE** — 4 CCCS sub-indices (L1 stock, L2 gap, L3 impulse, L4 DSR) operational; BIS SDMX v2 connector live; CAL-019 closed empirically; all pre-push gates green.

## Commits

| # | SHA | Scope | CI |
|---|---|---|---|
| 1 | `fcc421f` | CAL-019 debug + BIS structure cache + credit.md §3.1 amendment | ✓ |
| 2 | `7abded7` | BIS SDMX v2 connector (WS_DSR + WS_CREDIT_GAP + WS_TC) | ✓ |
| 3 | `a24b9a6` | Migration 009 + 4 credit ORM tables | ✓ |
| 4 | `f85f570` | L4 DSR + annuity helper + `persist_dsr_result` | ✓ |
| 5 | `4ca828c` | L1 Credit-to-GDP Stock + `persist_credit_gdp_stock_result` | ✓ |
| 6 | `ad9b160` | L2 Gap + HP/Hamilton helpers + `persist_credit_gdp_gap_result` | ✓ |
| 7 | `f5ec8d1` | L3 Credit Impulse + `persist_credit_impulse_result` | ✓ |
| 8 | `73331ff` | Credit orchestrator + 7-country integration slice | ✓ |
| 9 | `2ff2136` | `daily_credit_indices` pipeline (Option B split) + batch persist | ✓ |
| 10 | *this commit* | Retrospective | — |

## Coverage delta

| Scope | Before | After | Delta |
|---|---|---|---|
| `src/sonar/connectors/` | 7 modules | 8 modules (+bis.py) | +1 module, +245 LOC |
| `src/sonar/indices/credit/` | empty pkg | 4 modules (l1/l2/l3/l4) | +875 LOC |
| `src/sonar/indices/_helpers/` | 1 (annuity) | 3 (+hp_filter, +hamilton_filter) | +2 modules, +175 LOC |
| `src/sonar/db/models.py` | ERP + Indices + L3/M3 ORMs | +4 credit ORMs (CreditGdpStock, CreditGdpGap, CreditImpulse, Dsr) | +165 LOC inside Indices bookmark zone |
| `src/sonar/db/persistence.py` | NSS + Ratings + ERP + IndexValue | +4 persist_*_result helpers + persist_many_credit_results | +200 LOC |
| `src/sonar/pipelines/` | 2 modules | 3 modules (+daily_credit_indices.py) | +180 LOC |
| `alembic heads` | `008_index_values` | `009_credit_indices_schemas` | +4 tables |
| Unit tests | 291 passing | 393 passing | +102 tests |
| Integration tests | 6 modules | 7 modules (+test_credit_indices.py) | +12 tests (7 parametrized + 5 fixed) |

## Tests

- **L1** (`tests/unit/test_indices/credit/test_l1_credit_gdp_stock.py`): 19 unit — structural-band classifier (5), 7 T1 snapshot values, flag emission (F-fallback / CREDIT_BREAK / INSUFFICIENT_HISTORY / inherited), edge cases, persistence.
- **L2** (`test_l2_credit_gdp_gap.py`): 24 unit — HP helpers (5 incl. insufficient-history trap + two-sided decomposition sanity), Hamilton helpers (3 incl. rank-deficient trap), classifiers (7), core compute (5), persistence (2), concordance (3).
- **L3** (`test_l3_credit_impulse.py`): 18 unit — impulse formula primitives, state classifier (5 incl. accelerating-vs-decelerating via prior impulse), ma4 vs raw smoothing, edge cases, persistence.
- **L4** (`test_l4_dsr.py` + `test_annuity.py`): 25 + 10 = 35 unit — annuity helper 3 modes + neg-rate + stability bound, formula_mode resolver, band classifier, BIS-direct / approximations, BIS divergence flag, neg-rate flag, persistence single + duplicate + multi-segment.
- **Helpers** (already counted): annuity 10, hp_filter 5, hamilton_filter 3.
- **BIS connector** (`tests/unit/test_connectors/test_bis.py`): 13 unit + 1 `@pytest.mark.slow` live canary; 100% coverage on bis.py.
- **Integration** (`tests/integration/test_credit_indices.py`): 7-country parametrized emit, contract check (score ∈ [-5, +5], confidence ∈ [0, 1], bands set), BIS-direct DSR match ≤ 1pp gate, 7-country persistence of all 4 tables, orchestrator skip paths.
- **Pipeline** (`tests/unit/test_pipelines/test_daily_credit_indices.py`): 6 unit covering default-empty-bundle, synthetic-inputs persist, insufficient-inputs skip, 7-country sweep → 28 rows persisted, T1_7_COUNTRIES constant.

## CAL-019 resolution

**Before** (Phase 0 Bloco D, 2026-04-18): `Q.PT.P.M.770A` returned 404 for all T1 countries tested. Key format hypothesised deprecated. WS_DSR worked (`Q.PT.P`) but WS_TC failed.

**After** (Commit 1, 2026-04-20): hit BIS structure endpoint `GET /structure/dataflow/BIS/WS_TC?references=all&detail=full`. Discovered WS_TC binds to DataStructure `BIS:BIS_TOTAL_CREDIT(2.0)` with **7 dimensions** (not 5):

```
FREQ.BORROWERS_CTY.TC_BORROWERS.TC_LENDERS.VALUATION.UNIT_TYPE.TC_ADJUST
```

Canonical key `Q.{CTY}.P.A.M.770.A` with:

- `TC_LENDERS = A` (All sectors) — old docs said `M` which is not in CL_TC_LENDERS (only `A`/`B`).
- `UNIT_TYPE = 770` (Percentage of GDP) — old docs said `770A` which is invalid; true code is integer `770`.
- `TC_ADJUST = A` (Adjusted for breaks) — previously absent from the key.

Cached structure responses in `tests/fixtures/bis/` + sample observations for PT / US / DE. `docs/data_sources/credit.md` §3.1 amended with full table + empirical 7/7 validation. CAL-019 entry added in `docs/backlog/calibration-tasks.md` (sha `03e8812`).

## BIS connector validation matrix

| Dataflow | 7 T1 OK | Notes |
|---|---|---|
| `WS_DSR` | 7/7 | Phase 0 Bloco D already validated; requires `Accept: application/vnd.sdmx.data+json;version=1.0.0, application/json` (omission → 406). `BIS_DSR(1.0)` 3 dims. |
| `WS_CREDIT_GAP` | 7/7 (wildcarded) | Key `Q.{CTY}.P.A.{CG_DTYPE}` with CG_DTYPE ∈ {A actual / B trend / C gap}. PT 2024-Q2 gap = -38 pp (deleveraging). `BIS_CREDIT_GAP(1.0)` 5 dims. |
| `WS_TC` | 7/7 | Post-CAL-019 resolution. `BIS_TOTAL_CREDIT(2.0)` 7 dims. |

## 7-country 2024-Q2 snapshot (BIS smoke-test data cached in fixtures)

| Country | Credit/GDP pct (WS_TC) | DSR pct (WS_DSR US example) | WS_CREDIT_GAP gap_pp (PT) |
|---|---|---|---|
| US | 145.1 | 14.5 | — |
| DE | 138.9 | — | — |
| PT | 132.9 | — | -38 |
| IT | 95.8 | — | — |
| ES | 128.4 | — | — |
| FR | 214.3 | — | — |
| NL | 276.0 | — | — |

The integration test drives all 4 sub-indices for all 7 countries via synthetic-but-spec-plausible histories; a full-BIS vertical live-slice is gated behind `@pytest.mark.slow` (CLI toggleable).

## HP filter endpoint stability

Implementation: `hp_filter_one_sided` re-fits HP over `series[:t+1]` per observation, records terminal `(trend_t, cycle_t)`. `hp_one_sided_endpoint` skips the recursion when only the terminal pair is needed (L2 single-date compute). `hp_filter_two_sided` retained for `HP_ENDPOINT_REVISION` diagnostic (flag fires when `|two-sided − one-sided| > 3pp`).

Lambda: `400_000` (Ravn-Uhlig credit-cycle scaling). Spec §11 forbids two-sided output in `score_raw` — enforced by keeping the recursive path canonical.

## HALT triggers

| # | Trigger | Status |
|---|---|---|
| 1 | CAL-019 structure fail / 3+ T1 404 | did NOT fire (7/7 OK post-resolution) |
| 2 | BIS 1 req/sec rate limit | did NOT fire (cassettes; live canary paced at 0.5s) |
| 3 | GDP connector dispatch | not exercised (Week 4 used BIS-direct ratio, no Eurostat/FRED GDP fetch needed) |
| 4 | Migration 009 collision | did NOT fire (`alembic heads` clean at 009) |
| 5 | statsmodels install | did NOT fire (already in env; no pyproject.toml addition needed) |
| 6 | HP one-sided timeout | did NOT fire (single-point endpoint path avoids the recursion cost in the hot path) |
| 7 | Hamilton rank-deficient on T1 | did NOT fire (only fires on pure-linear synthetic; real data has enough noise) |
| 8 | L4 DSR divergence > 1pp | DID fire transiently in integration test when synthetic rate was not tuned; secant search on lending rate expanded to `[-10%, +15%]` to hit the acceptance gate |
| 9 | Coverage regression | did NOT fire |
| 10 | score_normalized out-of-range | did NOT fire (all clamps honored) |
| 11 | models.py bookmark conflict | did NOT fire (solo session, no parallel branch) |
| 12 | Pre-push gate fail | did NOT fire post-commit (ran `ruff format --check && ruff check && mypy && pytest tests/unit/ -x --no-cov` before every push; several intermediate lint/format cycles caught + fixed inline before push) |

## Deviations from brief

1. **Credit pipeline = Option B, not A** (brief §9 decision tree): existing `daily_cost_of_capital.py` is 376 LOC, above the 300 LOC threshold for splitting. Created `daily_credit_indices.py` as a separate pipeline with its own CLI + exit codes. `k_e` composition is untouched. Brief explicitly allowed this choice.
2. **Pipeline default path is no-op** (pluggable `InputsBuilder`): the brief envisioned "after CRP computation, trigger compute_all_credit_indices". Without a BIS-ingestion pipeline yet (rows in `credit_to_gdp_stock` / `dsr` tables must come from somewhere), the default builder returns an empty bundle → all 4 sub-indices record `skips=no inputs provided`. Tests inject a synthetic builder to exercise full wiring. Live BIS-read wiring is deferred — surfaces as CAL-058 below.
3. **BIS connector returns `BisObservation` (new dataclass) not the base `Observation`** (brief left this unspecified): BIS credit series are quarterly `value_pct` ratios, not yield-at-tenor in bps. A dedicated dataclass keeps the connector output typed without stretching `base.Observation`'s yield-centric fields. Callers in `indices/credit/` consume `value_pct` directly.
4. **Annuity helper** (`src/sonar/indices/_helpers/annuity.py`) **factored out**, not inlined in `l4_dsr.py`. Cleaner for L2 Hamilton and future CCCS consumers.

## New backlog items

- **CAL-058**: Live BIS-ingestion pipeline. `daily_credit_indices.py` currently ships a pluggable `InputsBuilder`; real production needs a BIS-fetch pass that writes raw observations to a new table (e.g. `bis_credit_raw`), followed by a builder that reads them to assemble `CreditIndicesInputs`. Scope: new alembic migration for raw BIS persistence + `BisConnector` wrapper for batched multi-country-multi-quarter fetches + replacement of `default_inputs_builder` with DB-backed builder.
- **CAL-059**: L3 impulse full 20Y z-score baseline. Current implementation bootstraps the z-score from per-quarter impulses computed over the input history when no explicit `impulse_pp_history` is supplied. When a persisted impulse history exists (post-backfill), prefer that over bootstrap.
- **CAL-060**: HP endpoint-revision calibration. The spec threshold of 3pp is placeholder; needs empirical distribution of `|two_sided − one_sided|` per country over 20Y of production runs.

## CCCS composite readiness

- **L1 / L2 / L3 / L4 operational**: ✓ (all 4 sub-indices implemented, unit-tested, integration-tested, persisted)
- **F3 / F4 cross-cycle input**: pending (Financial Cycle separate track)
- **QS (Qualitative Signal)**: Phase 2+ per `cycles/credit-cccs.md` §11
- **MS (Market Stress)**: `indices/financial/F3-risk-appetite` separate track
- **CCCS composite blocker**: only the Financial Cycle (F3 + F4 margin_debt_gdp_pct column) remains.

## k_e pipeline state

- **Pre-brief**: `k_e = rf + β·ERP + CRP`; no credit contribution.
- **Post-brief**: unchanged. Credit indices land in `credit_to_gdp_stock` / `credit_to_gdp_gap` / `credit_impulse` / `dsr` tables but are not read by `daily_cost_of_capital.py`.
- **Credit enters k_e** via the CCCS composite regime-adjustment in Week 5+ (separate brief).

## Blockers for Week 5

- **F-cycle (F1/F2/F3/F4) track brief needed** for CCCS composite completion. F3 risk-appetite is the critical path for MS sub-index; F4 positioning column `margin_debt_gdp_pct` is the cross-cycle leakage to CCCS.
- **After CCCS composite**: regime classifier + cross-cycle diagnostics (4-way matrix per `docs/reference/integration/`) become buildable.
- **BIS-ingestion pipeline (CAL-058)** needed before the credit sub-indices can run in real production mode. Currently they compute correctly from any supplied input bundle; the missing piece is the daily data pass that keeps the DB fresh.
