# Credit Track — BIS Connector + CCCS Sub-Indices L1-L4 — Execution Brief (v3)

**Target**: Post-ERP continuation — CCCS sub-indices operational for 7 T1 countries
**Priority**: HIGH (unblocks CCCS composite L4 cycle Week 5+; closes CAL-019 blocker)
**Budget**: 6–8h CC autonomous (revised up from v2 — CAL-019 debug + 2 HP methods + annuity formula)
**Commits**: ~10–12
**Base**: main HEAD post-ERP (7426715 or later)

---

## 1. Scope

In:
- `src/sonar/connectors/bis.py` — BIS SDMX v2 connector: WS_DSR + WS_CREDIT_GAP + WS_TC (after CAL-019 resolved)
- `src/sonar/indices/credit/l4_dsr.py` — `L4_DSR_v0.1` Drehmann-Juselius annuity formula (unblocked path, ship first)
- `src/sonar/indices/credit/l1_credit_gdp_stock.py` — `L1_CREDIT_GDP_STOCK_v0.1` (depends on WS_TC unblocked)
- `src/sonar/indices/credit/l2_credit_gdp_gap.py` — `L2_CREDIT_GDP_GAP_v0.1` HP one-sided λ=400000 + Hamilton dual
- `src/sonar/indices/credit/l3_credit_impulse.py` — `L3_CREDIT_IMPULSE_v0.1` Biggs-Mayer-Pick 2nd derivative
- Alembic migration 009 (4 dedicated tables per spec §8: `credit_to_gdp_stock`, `credit_to_gdp_gap`, `credit_impulse`, `dsr`)
- HP filter helper (L2 internal, one-sided recursive implementation)
- Hamilton regression helper (L2 internal, h=8 quarters)
- Annuity factor helper (L4 internal, 3 formula modes: full/o2/o1)
- Credit orchestrator extension: `compute_all_credit_indices(country, date, session)`
- Behavioral tests per spec §7 fixtures

Out:
- **CCCS composite computation** (Week 5+ L4 cycle work — this brief ships the 4 inputs only)
- **F3/F4 cross-cycle inputs for CCCS** (Financial Cycle prerequisite, separate track)
- **QS (Qualitative Signal) sub-index** — Phase 2+ per credit.md §6.3
- **MS (Market Stress) sub-index** — lives in `indices/financial`, separate track
- **Segment HH/NFC rows** for L3/L4 beyond PNFS default (Phase 2+ scope); ship only PNFS rows
- **T3/T4 countries** — BIS 43-country universe only; T3 raises `DataUnavailableError`
- **Extended historical backfill** pre-1970 (JST tloans) — separate spec
- **Housing cycle integration** (F1, separate track)

---

## 2. Spec reference

Authoritative (verified present 2026-04-20):
- `docs/specs/indices/credit/L1-credit-to-gdp-stock.md` @ `L1_CREDIT_GDP_STOCK_v0.1`
- `docs/specs/indices/credit/L2-credit-to-gdp-gap.md` @ `L2_CREDIT_GDP_GAP_v0.1`
- `docs/specs/indices/credit/L3-credit-impulse.md` @ `L3_CREDIT_IMPULSE_v0.1`
- `docs/specs/indices/credit/L4-dsr.md` @ `L4_DSR_v0.1`
- `docs/specs/indices/credit/README.md` (normalization + lookback rationale + CCCS composite preview)
- `docs/specs/cycles/credit-cccs.md` (downstream consumer — informational)
- `docs/data_sources/credit.md` §3.1 (BIS SDMX v2 endpoint structure)
- `docs/specs/conventions/units.md`, `flags.md`, `exceptions.md`, `patterns.md`
- `docs/backlog/calibration-tasks.md` — CAL-019 (WS_TC key schema) **blocker this brief resolves**
- SESSION_CONTEXT §Decision authority + §Brief format + §Regras operacionais

---

## 3. Commits

### Commit 1 — BIS WS_TC key schema debug (CAL-019 resolution)

```
feat(connectors): BIS SDMX structure discovery + WS_TC key schema resolution

Resolves CAL-019 empirically via BIS structure endpoint:
  GET /structure/dataflow/BIS/WS_TC?detail=allstubs&format=json

Compare returned dimension codelist for UNIT_MEASURE vs broken key
Q.PT.P.M.770A. Current hypothesis: 770A deprecated; correct code may
be XDC_R_B1GQ (percent of GDP) per SDMX dimension naming convention.

Test matrix (verify key resolution before claiming CAL-019 closed):
- WS_TC structure: parse UNIT_MEASURE codelist, extract valid codes
- Smoke test PT: Q.PT.P.M.{code1} for top-3 candidate UNIT_MEASURE codes
- Expected hit: 200 OK with populated observations (credit-to-GDP pct)
- WS_TC structure: verify all 5 dimensions per credit.md §3.1 still valid:
  FREQ, BORROWERS_CTY, BORROWERS_SECTOR, LENDERS_SECTOR, UNIT_MEASURE

Scaffolding only this commit — no connector module yet. Output is:
- tests/fixtures/bis/ws_tc_structure.json (cached structure response)
- docs/data_sources/credit.md §3.1 amendment: update WS_TC key pattern
  with resolved UNIT_MEASURE code
- CAL-019 closed in calibration-tasks.md

If structure endpoint itself fails OR resolved key still returns 404
for 3+ BIS Tier 1 countries → HALT, CAL-019 upgrades to cross-cycle
BLOCKER and brief pauses for Hugo consultation (alternative paths:
ECB SDW credit counterparts, FRED US-only degraded mode).
```

### Commit 2 — BIS SDMX connector base

```
feat(connectors): BIS SDMX v2 connector for WS_DSR, WS_CREDIT_GAP, WS_TC

src/sonar/connectors/bis.py subclasses BaseConnector per Week 1
scaffolding.

Base URL: https://stats.bis.org/api/v2
Format: ?format=jsondata (SDMX-JSON 1.0)
Accept: application/vnd.sdmx.data+json;version=1.0.0, application/json
Rate limit: 1 req/sec (BIS polite use)
Auth: none (public)

Public methods:
- fetch_dsr(country, start_date, end_date) → list[Observation]
  Dataflow WS_DSR, key Q.{C}.P (3 dims; Phase 0 Bloco D validated 7/7)
  Returns DSR values in pct display (e.g. 18.4)
- fetch_credit_gap(country, start_date, end_date) → list[Observation]
  Dataflow WS_CREDIT_GAP, BIS pre-computed one-sided HP gap in pp
- fetch_credit_stock_ratio(country, start_date, end_date) → list[Observation]
  Dataflow WS_TC with resolved UNIT_MEASURE code per Commit 1
  Returns credit-to-GDP ratio in pct display
- fetch_structure(dataflow_id) → dict (internal; used by Commit 1)

SDMX-JSON parsing: prefer raw parsing via existing stdlib json + minimal
helper; avoid sdmx1 dependency if feasible (2MB+ dep for narrow use).
If sdmx1 required for robust parsing, add to pyproject.toml with
rationale in commit body.

Cassette-replayed unit tests (7 country smoke); @pytest.mark.live canary.
Coverage ≥ 95% connectors hard gate per phase1-coverage-policy.
```

### Commit 3 — Alembic migration 009 + dedicated schemas

```
feat(db): migration 009 credit indices dedicated tables (4 per spec §8)

Four dedicated tables per README §"Output schema (consistent across 4)"
common preamble + per-spec extra columns.

Tables:
- credit_to_gdp_stock (L1 schema per L1 spec §8)
- credit_to_gdp_gap (L2 schema per L2 spec §8)
- credit_impulse (L3 schema per L3 spec §8; UNIQUE includes segment)
- dsr (L4 schema per L4 spec §8; UNIQUE includes segment)

Common columns across 4:
country_code, date, methodology_version, score_normalized, score_raw,
components_json, lookback_years, confidence, flags, source_connector,
created_at, UNIQUE per spec.

Indexes: idx_l1_cgs_cd, idx_l2_cgg_cd, idx_l3_ci_cd, idx_l4_dsr_cd
per spec.

NOT polymorphic index_values — CCCS sub-indices warrant dedicated
schemas because:
- Each has substantially different extra columns (L4 has 11+ extras)
- Consumer code in cycles/credit-cccs reads typed columns directly
- CHECK constraints vary per spec (formula_mode, band, concordance)

Design contrast: E2/M3 fit polymorphic index_values (similar shapes);
credit L1-L4 do not. Acknowledged departure from L3 brief pattern —
rationale documented in commit body.

Add IndexValue models under # === Indices models === bookmark zone
(from ERP brief Commit 1). ORM classes:
CreditGdpStock, CreditGdpGap, CreditImpulse, Dsr.

Alembic upgrade/downgrade round-trip verified clean.
```

### Commit 4 — L4 DSR implementation (unblocked path, ship first)

```
feat(indices): L4 DSR per L4_DSR_v0.1 (Drehmann-Juselius annuity formula)

src/sonar/indices/credit/l4_dsr.py implements spec §4 verbatim.

Annuity factor helper (src/sonar/indices/_helpers/annuity.py):
- annuity_factor(i, s, mode) where mode ∈ {"full", "o2", "o1"}
- full: i / (1 - (1+i)^(-s))
- o2: i + 1/s (2nd-order approx, ~0.95 corr to full)
- o1: i (1st-order, interest-only, ~0.85 corr to full)
- Handles negative rates (JP/CH/EA pre-2022): full formula still valid
  for small i; flag DSR_NEG_RATE per spec §6

fit_dsr(country, date, session, segment="PNFS") orchestrates:
1. Resolve formula_mode per country coverage matrix (spec §4 step 1):
   - BIS WS_DSR 32 → "full" (read pre-computed + transparency fields)
   - else if rate+maturity+D/Y available → "o2"
   - else if rate+D/Y only → "o1"
   - else raise DataUnavailableError
2. Fetch inputs: BIS WS_DSR direct for 32 OR compute from
   lending_rate (BIS WS_DSR derived | ECB MIR | FRED) +
   maturity (BIS standard assumption PNFS 15Y) +
   debt_to_gdp_ratio (BIS WS_TC once unblocked)
3. Compute annuity_factor → dsr_pct = annuity_factor × D/Y × 100
4. Rolling 20Y baseline → μ, σ → score_normalized + dsr_deviation_pp
5. Band classification (baseline/alert/critical per spec §4 step 8)
6. Confidence per §6 matrix + flags propagation

Countries Week 4 scope: 7 T1 (US/DE/PT/IT/ES/FR/NL) — all within
BIS WS_DSR 32. All use formula_mode="full".

BIS-published DSR sanity: if SONAR-computed vs BIS-published > 1pp →
flag DSR_BIS_DIVERGE (spec §6).

Persistence via new persist_dsr_fit_result helper (pattern mirrors
persist_nss/erp): atomic single-row with segment-aware UNIQUE.

Fixtures: pt_2024_q4_pnfs, pt_2009_q4_pnfs, us_2024_q4_pnfs (BIS
direct), xx_no_maturity (fallback o1), jp_2020_q4_neg_rate,
xx_invalid_maturity (raises).

Behavioral tests ≥ 18; coverage ≥ 90% on l4_dsr.py.
```

### Commit 5 — L1 Credit-to-GDP Stock implementation

```
feat(indices): L1 Credit-to-GDP Stock per L1_CREDIT_GDP_STOCK_v0.1

src/sonar/indices/credit/l1_credit_gdp_stock.py implements spec §4.

Formula: CtG_t = Total_Credit_PNFS_t / GDP_4Q_sum_t × 100

fit_credit_gdp_stock(country, date, session) orchestrates:
1. Resolve series_variant: try Q-series; fall back to F if stale > 2Q
2. Fetch credit_stock_lcu from BIS WS_TC (now unblocked)
3. Fetch gdp_nominal_lcu from BIS WS_TC denominator OR Eurostat
   namq_10_gdp OR FRED GDP* (4Q rolling sum computed locally, NOT
   point-quarterly — sazonalidade-killer per spec §4 precondition)
4. Validate growth jumps < 50% Q-on-Q (else flag CREDIT_BREAK per spec)
5. Compute ratio_pct = credit_stock / gdp_4q_sum × 100
6. Rolling 20Y z-score → score_normalized
7. Classify structural_band (advanced_economy_typical / etc.)
8. Confidence + flags per §6

Countries Week 4: 7 T1 via BIS Q-series (all confirmed in BIS
Q-series 40-country universe). Tier 2 F-fallback skeleton present but
not exercised this sprint.

GDP connector resolution: T1 EA countries prefer Eurostat namq_10_gdp
(fresher, harmonized); US prefer FRED GDP; others BIS-embedded.
Document connector dispatch logic in module docstring.

Fixtures: pt_2024_q4, us_2024_q4, cn_2024_q4 (deferred — T2+),
ee_2024_q4 (F-fallback, skip for 7 T1 scope),
pt_1995_q1_short_history (insufficient).

Behavioral tests ≥ 15; coverage ≥ 90%.
```

### Commit 6 — L2 Credit-to-GDP Gap implementation (HP + Hamilton dual)

```
feat(indices): L2 Gap per L2_CREDIT_GDP_GAP_v0.1 (HP one-sided + Hamilton)

Two helper modules:

src/sonar/indices/_helpers/hp_filter.py:
- hp_filter_one_sided(series, lamb=400000) → (trend, cycle_pp)
- Recursive refit at each t: for each t, fit HP trend over [t_0, t],
  record τ_t. One-sided = no look-ahead bias (production requirement).
- Uses statsmodels.tsa.filters.hp_filter.hpfilter per t-slice with
  per-country cache (patterns.md HP cache policy).
- Diagnostic only: two-sided HP computed in parallel for
  HP_ENDPOINT_REVISION flag detection (|two_sided - one_sided| > 3pp).

src/sonar/indices/_helpers/hamilton_filter.py:
- hamilton_residual(series, h=8) → ε_t
- Regression y_t = β0 + β1·y_{t-h} + β2·y_{t-h-1} + β3·y_{t-h-2} +
  β4·y_{t-h-3} + ε_t (rolling window)
- No λ tuning, no endpoint bias — Hamilton (2018) "Why You Should
  Never Use the HP Filter" alternative

Main module: src/sonar/indices/credit/l2_credit_gdp_gap.py

fit_credit_gdp_gap(country, date, session):
1. Pull l1_score_raw from credit_to_gdp_stock for (country, date) range
2. Validate ≥ 40 obs hard floor (spec §6: InsufficientDataError < 40)
3. HP path: trend_hp, gap_hp_pp = hp_filter_one_sided(ratio_pct, 400000)
4. Hamilton path: gap_hamilton_pp = hamilton_residual(ratio_pct, 8)
5. score_raw = mean(gap_hp_pp, gap_hamilton_pp)
6. Rolling 20Y z-score → score_normalized clamped [-5, +5]
7. Concordance flag: both_above / both_below / divergent (±2pp threshold)
8. phase_band: deleveraging < -5 / neutral / boom_zone +2 / danger_zone +10
9. HP_ENDPOINT_REVISION flag if two_sided diverges > 3pp
10. Confidence + flags per §6

statsmodels>=0.14 added to pyproject.toml.

Fixtures: pt_2024_q4 (neutral), pt_2009_q4 (danger_zone), us_2007_q3
(boom_zone pre-GFC), cn_2016_q1 (danger_zone EM), pt_1995_short
(raises), xx_divergent_synthetic (GAP_DIVERGENT flag).

Behavioral tests ≥ 20 (HP + Hamilton + concordance + bands + endpoint
revision matrix). Coverage ≥ 90%.
```

### Commit 7 — L3 Credit Impulse implementation

```
feat(indices): L3 Credit Impulse per L3_CREDIT_IMPULSE_v0.1

src/sonar/indices/credit/l3_credit_impulse.py implements spec §4.

Formula: CI_t = (Δ₄Credit_t - Δ₄Credit_{t-4}) / GDP_{t-4} × 100
         = Δ²₄ Credit_t / GDP_{t-4} × 100

Key distinction from L1 denominator: GDP here is POINT quarterly at
t-4, not 4Q rolling sum. This normalizes the flow-of-flows per a
single quarter's GDP (Biggs-Mayer-Pick 2010 canonical).

fit_credit_impulse(country, date, session, segment="PNFS",
                    smoothing="ma4"):
1. Read series_variant from L1 row (L1_VARIANT_MISMATCH flag if
   diverges)
2. Fetch credit_stock_lcu at t, t-4Q, t-8Q; gdp_nominal_lcu at t-4Q
3. Validate all > 0, no NaN; else InsufficientDataError
4. Compute flow_recent, flow_prior, delta_flow
5. impulse_pp = delta_flow / gdp_{t-4} × 100
6. If smoothing="ma4": average impulses at t, t-1Q, t-2Q, t-3Q
7. Rolling 20Y z-score → score_normalized
8. State: accelerating/decelerating/neutral/contracting per spec §4
   step 9 (requires 2nd-order derivative of impulse for
   accelerating-vs-decelerating discrimination)
9. IMPULSE_OUTLIER flag if |delta_flow/gdp| > 10pp
10. Confidence + flags per §6

Countries Week 4: same 7 T1 as L1 (impulse requires L1 raw credit
stock for t, t-4, t-8).

PNFS segment only this sprint; HH/NFC segment rows deferred Phase 2+
(spec §2 "Does not smooth across segment boundary"; distinct
emission paths).

Fixtures: pt_2024_q4 (accelerating mild), pt_2009_q4 (contracting),
cn_2009_q2 (EM post-stimulus, flags EM_COVERAGE),
us_2008_q4 (Lehman quarter, contracting),
pt_decelerating_2007_q4 (state=decelerating),
xx_outlier_synthetic (IMPULSE_OUTLIER flag).

Behavioral tests ≥ 18; coverage ≥ 90%.
```

### Commit 8 — Orchestrator + integration test 7 countries

```
feat(indices): credit orchestrator + 7-country vertical slice test

src/sonar/indices/orchestrator.py extension:
- compute_all_credit_indices(country, date, session) → dict[str, IndexResult]
- Runs L1 → L2 → L3 → L4 in sequence (L2/L3 depend on L1)
- Gracefully skip individual index on InsufficientInputsError;
  record skip + reason in top-level dict

Integration test tests/integration/test_credit_indices.py:
- 7-country loop (US/DE/PT/IT/ES/FR/NL) for 2024-01-02 (Q4 2023 data)
- Cassette-replayed BIS fetches
- Assert each country produces L1 + L2 + L4 minimum; L3 may degrade
  on insufficient 2nd-diff history
- Assert BIS-direct DSR match (|SONAR - BIS| ≤ 1pp for T1 direct)
- Assert L1 structural_band classified; L2 phase_band classified;
  L3 state classified; L4 band classified
- Assert all score_normalized ∈ [-5, +5]
- Assert all confidence ∈ [0, 1]
- Assert flags well-formed CSV

CLI extension:
python -m sonar.indices.orchestrator --country US --date 2024-01-02 \
       --credit-only
```

### Commit 9 — Pipeline integration

```
feat(pipelines): credit indices in daily pipeline

Option A: extend daily_cost_of_capital.py to include credit indices
as side computation (not input to k_e composition).
Option B: new daily_credit_indices.py separate pipeline.

CC judgement — prefer A for 7 T1 countries unified daily run;
reconsider B if daily_cost_of_capital.py exceeds 300 lines.

Integration: after CRP computation in pipeline, trigger
compute_all_credit_indices per country, persist via
persist_many_credit_results (helper aggregating L1-L4 persist calls).

Pipeline test updates: 7-country run completes with credit indices
persisted; k_e composition unaffected (credit indices not yet in
k_e formula — will be in Week 5+ via CCCS).

No new CLI flags; existing --all-t1 triggers credit too.
```

### Commit 10 — Retrospective + §7 artifact

```
docs(planning): credit indices implementation retrospective

File: docs/planning/retrospectives/credit-indices-implementation-report.md

Consolidated §7 structure mirroring erp-us-implementation-report.md:
- Summary (duration, commits, status COMPLETE/PARTIAL/HALTED)
- Commits table (10 SHAs + scope)
- Coverage delta per scope (connectors, indices, db, pipelines)
- Tests: L1/L2/L3/L4 behavioral count + integration count
- CAL-019 resolution: before/after WS_TC smoke test output
- BIS connector validation outcomes table:
  | Dataflow | Countries OK | Notes |
  | WS_DSR | 7/7 | Phase 0 Bloco D confirmation |
  | WS_CREDIT_GAP | x/7 | new validation |
  | WS_TC | x/7 | post-CAL-019 |
- 7-country 2024-01-02 snapshot:
  | Country | L1 | L2 | L3 | L4 | CCCS preview |
  | US | 155.0 / +0.15 z | +3.4 gap_pp / +0.80 z boom | +0.6 impulse | 15.5 dsr / baseline | preview |
  | ... |
  Note: CCCS composite preview computed locally for retrospective only
  (not persisted — L4 cycle work owns composite spec).
- HALT triggers fired + resolutions
- New backlog items (CAL/P2 surfaced)
- CCCS composite readiness:
  - L1/L2/L3/L4 shipped: ✓
  - F3/F4 cross-cycle input: pending (Financial Cycle separate track)
  - QS + MS sub-indices: Phase 2+ per spec §6.3
  - CCCS composite blocker: only F-cycle remaining
- k_e pipeline state: unchanged (credit not yet in k_e formula)
- Blockers for Week 5:
  - F-cycle (F1/F2/F3/F4) track brief needed
  - CCCS composite brief post-F-cycle

Commit msg:
docs(planning): credit track retrospective (CAL-019 resolved, L1-L4 operational)

Closes CAL-019, CAL-051/052/053/054/055 (resolved via this sprint)
```

---

## 4. HALT triggers (atomic)

1. **Commit 1 CAL-019 debug fails** — BIS structure endpoint unavailable OR resolved key still returns 404 for 3+ T1 countries → HALT, Hugo consultation on alternative paths (ECB SDW fallback for EA, FRED US-only degraded mode)
2. **BIS rate limit** — if 1 req/sec too slow for cassette recording → halt, decide throttling vs batch
3. **GDP connector dispatch** — Eurostat namq_10_gdp or FRED GDP endpoints unavailable → halt, BIS-embedded denominator fallback
4. **Migration 009 collision** — ERP used 007, L3 used 008; 009 should be clean but verify `alembic heads` before migration create
5. **statsmodels install failure** — pyproject.toml add fails in CI or local → halt (environment issue)
6. **HP filter one-sided recursive fit timeout** — 20Y series × 7 countries × per-t refit may be slow; if > 30s per country → halt, evaluate caching strategy per patterns.md
7. **Hamilton regression rank-deficient** on pt_1995_short_history or similar → persist expected raise per spec §6; test passes. If unexpectedly fails on T1 country fixture → HALT, spec may need revision
8. **L4 DSR BIS-published divergence > 1pp** on US/DE 2024-Q4 fixture → HALT, investigate connector parsing or BIS data version mismatch
9. **Coverage regression > 3pp** on existing scopes → halt
10. **Any score_normalized outside [-5, +5]** post-clamp → halt (clamp bug)
11. **models.py Indices bookmark zone rebase conflict** → halt (L3 brief violated discipline OR new ORM patterns)
12. **Pre-push gate fails** (`uv run ruff format --check src/sonar tests` OR `ruff check` OR `mypy src/sonar`) → halt, fix before push (CI-debt-free saga pattern)

"User authorized in principle" does NOT cover specific triggers. Atomic per SESSION_CONTEXT §Decision authority.

---

## 5. Acceptance

### Per commit
- **Commit 1**: CAL-019 closed in backlog; `docs/data_sources/credit.md` §3.1 updated with resolved UNIT_MEASURE code; structure response cached in fixture
- **Commit 2**: BIS connector 3 dataflows operational; cassette tests 7-country smoke; live canary runs clean
- **Commit 3**: Migration 009 upgrade/downgrade round-trip green; 4 tables created with correct schemas per spec §8
- **Commit 4**: L4 DSR produces row for 7 T1 countries 2024-01-02; BIS-direct match ≤ 1pp
- **Commit 5**: L1 produces rows; structural_band classified; 7/7 countries
- **Commit 6**: L2 produces rows; HP + Hamilton both computed; concordance + phase_band set; HP_ENDPOINT_REVISION flag operational
- **Commit 7**: L3 produces rows; state classified; IMPULSE_OUTLIER flag operational
- **Commit 8**: Orchestrator `compute_all_credit_indices` produces 4-row dict per country; integration test green
- **Commit 9**: Pipeline extension green; `--all-t1` triggers credit indices persistence
- **Commit 10**: Retrospective artifact in `docs/planning/retrospectives/credit-indices-implementation-report.md`

### Global sprint-end
- [ ] 10-12 commits pushed, main HEAD matches remote
- [ ] All CI runs green (pre-push gate enforced)
- [ ] `src/sonar/connectors/bis.py` coverage ≥ 95% (connectors hard gate)
- [ ] `src/sonar/indices/credit/*.py` coverage ≥ 90% per module
- [ ] `src/sonar/indices/_helpers/{hp_filter,hamilton_filter,annuity}.py` coverage ≥ 95%
- [ ] `src/sonar/db/persistence.py` credit helpers coverage ≥ 90%
- [ ] 7 T1 countries have L1/L2/L3/L4 rows for 2024-01-02
- [ ] CAL-019 closed; CAL-051..055 closed (resolved via this sprint)
- [ ] Full test suite green: ≥ 340 unit + 18 integration tests
- [ ] No `--no-verify` pushes

---

## 6. Report-back artifact export (mandatory)

Progressive per commit boundary, consolidated final:

**Per-commit summaries in tmux echo only** (short form, 5-line max):
```
COMMIT N/10 DONE: <scope>, SHA, coverage delta, tests added, HALT status
```

**Consolidated final artifact** (mandatory):
`docs/planning/retrospectives/credit-indices-implementation-report.md`

Structure per ERP retrospective pattern (see `erp-us-implementation-report.md` shipped in 7426715 for template):

```markdown
# Credit Indices Implementation Report (v0.1, Phase 1 Week 4)

## Summary
- Duration: Xh Ymin / 6-8h budget
- Commits: N (SHA range)
- Status: COMPLETE / PARTIAL / HALTED

## Commits
| # | SHA | Scope | CI |

## Coverage delta
| Scope | Before | After | Delta |

## Tests
- L1: X unit
- L2: Y unit (HP + Hamilton split)
- L3: Z unit
- L4: W unit (full + o2 + o1 formula tests)
- Helpers: U unit (annuity + HP + Hamilton)
- BIS connector: V unit + 1 live canary
- Integration: 7-country vertical slice

## CAL-019 resolution
- Before (Phase 0 Bloco D): Q.PT.P.M.770A → 404
- After (Commit 1): Q.PT.P.M.{resolved_code} → 200 with N observations
- UNIT_MEASURE resolved: {code} ({description})
- credit.md §3.1 amended

## BIS connector validation matrix
| Dataflow | 7 T1 OK | Notes |
| WS_DSR | y/7 | Phase 0 Bloco D already validated 7/7 |
| WS_CREDIT_GAP | y/7 | New live validation |
| WS_TC | y/7 | Post-CAL-019 |

## 7-country 2024-01-02 snapshot
| Country | L1 raw/z | L2 raw/z + band | L3 raw/z + state | L4 raw/z + band | Flags |
| US | 155.0 / +0.15 | +3.4 / +0.80 boom_zone | +0.6 / +0.1 accel | 15.5 / +0.10 baseline | (none) |
| DE | 140.0 / -0.5 | -1.2 / -0.3 neutral | +0.3 / -0.2 neutral | 12.8 / -0.3 baseline | (none) |
| PT | 145.0 / -1.1 | -2.5 / -0.6 neutral | +0.6 / +0.1 accel | 12.2 / -0.4 baseline | (none) |
| IT | 125.0 / -1.5 | -4.0 / -0.9 neutral | +0.2 / -0.2 neutral | 14.5 / -0.2 baseline | (none) |
| ES | 130.0 / -0.8 | -3.0 / -0.7 neutral | +0.4 / 0.0 neutral | 13.8 / -0.25 baseline | (none) |
| FR | 160.0 / +0.3 | +1.5 / +0.4 neutral | +0.8 / +0.2 accel | 18.2 / +0.3 alert | (none) |
| NL | 230.0 / +1.8 | +5.5 / +1.2 boom_zone | +1.2 / +0.5 accel | 16.5 / +0.2 baseline | (none) |

(Values illustrative — actual values emerge from live BIS data.)

## HP filter endpoint stability
- Two-sided vs one-sided divergence per country at 2024-Q4:
  | Country | one_sided_pp | two_sided_pp | |diff| | HP_ENDPOINT_REVISION? |

## HALT triggers
[fired/resolved or "none"]

## Deviations from brief
[any interpretation beyond verbatim]

## New backlog items
[CAL/P2 surfaced]

## CCCS composite readiness
- L1/L2/L3/L4 operational: ✓
- F3/F4 cross-cycle input: pending (F-cycle separate track)
- QS (Qualitative Signal): Phase 2+ per spec
- MS (Market Stress): `indices/financial` separate track
- CCCS composite blocker: only F-cycle remaining

## k_e pipeline state
- Pre-brief: k_e = rf + β·ERP + CRP; no credit contribution
- Post-brief: unchanged (credit not yet in k_e formula)
- Credit enters k_e via CCCS composite regime adjustment Week 5+

## Blockers for Week 5
- F-cycle (F1/F2/F3/F4) track brief needed for CCCS composite completion
- After CCCS composite: can start regime classifier + cross-cycle diagnostics
```

After final push, echo to tmux:
```
CREDIT TRACK DONE: N commits, 4 indices × 7 countries operational
CAL-019 resolved; BIS connector 3 dataflows live-validated
HALT triggers: [list or "none"]
Artifact: docs/planning/retrospectives/credit-indices-implementation-report.md
```

---

## 7. Concurrency protocol (reference)

This brief executes in **single CC session** (tmux `sonar-l3` previously idle after L3 E2+M3 sub-sprint). ERP CC in tmux `sonar` is idle post-retrospective (7426715); no parallel work this sprint.

If future parallel work emerges:
- Migration 010+ allocation rules
- models.py bookmark zones already established (ERP + Indices)
- Pre-push gate remains mandatory per CI-debt saga lessons

---

## 8. Pre-push gate (mandatory per CI-debt saga lessons)

Before EVERY `git push`:
```
uv run ruff format --check src/sonar tests
uv run ruff check src/sonar tests
uv run mypy src/sonar
uv run pytest tests/unit/ -x --no-cov
```

All four must exit 0. If any fails → fix before push. No exceptions.

CI runs same plus integration tests + security scan + docs check. Pre-push gate catches ~95% of CI-debt scenarios.

---

## 9. Notes on spec adherence

### L2 HP filter one-sided vs two-sided
Production code MUST use one-sided recursive refit. Two-sided is computed only as diagnostic for `HP_ENDPOINT_REVISION` flag. Never persisted as `score_raw`. Per spec §4 + §11 non-requirements.

### L4 DSR negative rates
JP/CH/EA pre-2022 had negative policy rates. Full annuity formula `i / (1 - (1+i)^(-s))` remains valid for small negative i; DSR approaches `D/Y/s` asymptotically. Spec §6 confirms: flag `DSR_NEG_RATE`, −0.05 confidence, continue. No special-case code path.

### L3 segment default PNFS
PNFS = HH + NFC aggregate. HH and NFC separate rows deferred Phase 2+ per spec §2. Schema supports segment column (UNIQUE includes segment) but this sprint only persists segment="PNFS" rows.

### L1 GDP denominator 4Q rolling sum
Non-negotiable: per spec §2 precondition, gdp_nominal_lcu must be 4Q rolling sum (sazonalidade-killer), NOT point-quarterly. L3 impulse uses different denominator (point gdp_{t-4}) — these are methodologically distinct and spec-driven.

### CCCS composite scope
This brief ships 4 raw sub-indices (L1/L2/L3/L4) + 1 retrospective-only CCCS preview for orientation. The composite formula lives in `cycles/credit-cccs.md` (future Week 5+ brief) with MS + QS components from other folders. Do NOT ship CCCS composite computation in this sprint.

---

*End of brief. 10-commit sprint. CAL-019 debug first, L4 DSR quick win, L1-L2-L3 sequential dependencies. Pre-push gate enforced. Artifact export final.*
