# Week 3.5 Implementation Sprint — Execution Brief (v2 expandido)

**Target**: Phase 1 Week 3.5 (full sprint, can span multiple tmux sessions)
**Priority**: HIGH (M1 cost-of-capital 7 countries operational — completes M1 US/EA vertical)
**Budget**: 12–18h CC autonomous
**Commits**: ~20–28 across 6 sub-sprints
**Base**: main HEAD post spec sweep

---

## 1. Scope

In (expandido per Hugo 2026-04-20):

### Sub-sprint 3.5A — Connectors foundation
- FMP connector base (BaseConnector subclass, Ultimate tier auth via `FMP_API_KEY` env)
- TE connector extension: historical yields endpoint for bond vol proxy
- Graceful degrade pattern uniform across all fragile scrapers

### Sub-sprint 3.5B — ERP US full implementation (4 methods)
- FactSet Earnings Insight PDF scraper (pdfplumber)
- Yardeni Earnings Forecasts PDF scraper (explicit consent per P2-028)
- multpl.com scrape (US dividend yield)
- S&P DJI buybacks PDF scrape
- Shiller ie_data.xls download + parse
- Damodaran histimpl.xlsx download + parse (US monthly xval)
- `overlays/erp.py` full compute (DCF + Gordon + EY + CAPE + canonical)
- Alembic migration 005: erp_* tables (per spec §8)
- FactSet vs Yardeni forward-EPS divergence flag
- Damodaran US xval hook

### Sub-sprint 3.5C — CRP country-specific vol_ratio + 7 countries
- FMP historical daily index prices (S&P, DAX, CAC, FTSE MIB, AEX, IBEX, PSI)
- TE historical 10Y yields (DE, US, UK, JP, IT, ES, FR, NL, PT)
- `overlays/crp.py` full compute: RATING + SOV_SPREAD + vol_ratio country-specific
- Alembic migration 006: crp_* tables (per spec §8)
- Benchmark countries shortcut (DE/US/UK/JP → crp=0)
- CDS branch stays deferred (WGB not validated; SOV_SPREAD + RATING sufficient)

### Sub-sprint 3.5D — FR/IT linkers + EA expected-inflation
- `connectors/aft_france.py` (OATi linker yields)
- `connectors/mef_italy.py` (BTP€i linker yields)
- Extend `overlays/expected_inflation.py`: EA BEI via DE/FR/IT linkers + PT DERIVED
- Fixtures per spec §7 for DE/FR/IT/PT

### Sub-sprint 3.5E — Persistence + integration tests
- Persistence helpers ExpInf + CRP (sibling to NSS persistence pattern)
- Alembic migrations 007, 008 if not already in 005/006
- Integration test suite: 7-country vertical slice end-to-end

### Sub-sprint 3.5F — Daily cost-of-capital pipeline (L6 primitive)
- `pipelines/daily_cost_of_capital.py`: orchestrate NSS → ExpInf → ERP → CRP → compose k_e
- Formula: `k_e_country = rf_local + β·ERP_mature + CRP_country` (β=1.0 stub)
- CLI: `python -m sonar.pipelines.daily_cost_of_capital --country US --date YYYY-MM-DD`
- Write to `cost_of_capital_daily` table (new, scope creep accepted)
- 7 countries covered: US, DE, PT, IT, ES, FR, NL

Out (defer Week 4+):
- UK/JP k_e (pending BoE/MoF connector extension for UK/JP yields)
- CDS branch CRP (WGB unvalidated)
- EM expansion (BR, MX, TR, etc.)
- L3 indices consuming these overlays
- L4 cycles

---

## 2. Spec reference

Post-sweep authoritative:
- `docs/specs/overlays/erp-daily.md` @ ERP_CANONICAL_v0.1 (Yardeni added, FactSet primary)
- `docs/specs/overlays/crp.md` @ CRP_CANONICAL_v0.1 (FMP+TE for vol_ratio)
- `docs/specs/overlays/expected-inflation.md` @ EXP_INF_CANONICAL_v0.1
- `docs/specs/overlays/rating-spread.md` @ RATING_SPREAD_v0.2 (from Week 3 3A)
- `docs/specs/overlays/nss-curves.md` @ NSS_v0.1
- `docs/specs/conventions/{units,flags,patterns,exceptions}.md`
- `docs/planning/phase1-coverage-policy.md`
- SESSION_CONTEXT §Decision authority + §Brief format
- P2-028 (Yardeni consent — assumed granted per Hugo 2026-04-20)

---

## 3. Sub-sprints + commits

### Sub-sprint 3.5A — Connectors foundation (~1.5-2h)

**3.5A-1** — `feat(connectors): FMP Ultimate connector base`
- `src/sonar/connectors/fmp.py` subclass BaseConnector
- Auth via `FMP_API_KEY` env (Ultimate tier documented in module docstring)
- Endpoints: `historical-price-full/{symbol}`, `historical-chart/1day/{symbol}`
- `fetch_index_historical(symbol, from_date, to_date) -> list[Observation]`
- Symbol mapping helper: "SPX" → "^GSPC", "DAX" → "^GDAXI", etc. for major indices
- Cassette-replay unit tests (5+ symbols); live canary `@pytest.mark.live`
- Coverage ≥ 95%

**3.5A-2** — `feat(connectors): TE historical yields extension`
- Extend `src/sonar/connectors/te.py` (assuming exists from Week 3 Day 3A) OR create if not
- New method: `fetch_sovereign_yield_historical(country, tenor, from_date, to_date) -> list[Observation]`
- Covers 10Y yields for T1 countries
- Cassette tests + live canary

### Sub-sprint 3.5B — ERP US full (~4-5h)

**3.5B-1** — `feat(connectors): Shiller ie_data + Damodaran histimpl downloaders`
- `src/sonar/connectors/shiller.py`: download `http://www.econ.yale.edu/~shiller/data/ie_data.xls` + parse via openpyxl
- `src/sonar/connectors/damodaran.py`: download `https://pages.stern.nyu.edu/~adamodar/pc/datasets/histimpl.xlsx` + parse monthly ERP
- Disk-cache both (monthly refresh cadence)
- Tests: fixture-based parsing (synthetic xls samples); live canary

**3.5B-2** — `feat(connectors): FactSet Earnings Insight PDF scraper`
- `src/sonar/connectors/factset_insight.py`
- URL pattern: `https://advantage.factset.com/hubfs/Website/Resources%20Section/Research%20Desk/Earnings%20Insight/EarningsInsight_MMDDYY.pdf`
- pdfplumber extraction: forward 12M EPS, forward P/E, annual EPS estimates CY+1, CY+2, analyst consensus growth
- Graceful failure: on parse error, emit `DataUnavailableError` → flag `OVERLAY_MISS` caller-side
- Cassette (mock PDF in fixtures) tests + live weekly canary

**3.5B-3** — `feat(connectors): Yardeni Earnings Forecasts PDF scraper`
- `src/sonar/connectors/yardeni.py`
- Explicit consent documented in module docstring referencing P2-028
- Weekly PDF download + parse (similar pattern to FactSet)
- Extract Earnings Squiggles values for forward EPS
- Same graceful-degrade pattern

**3.5B-4** — `feat(connectors): multpl + spdji US-specific scrapers`
- `connectors/multpl.py`: scrape multpl.com for S&P 500 dividend yield
- `connectors/spdji_buyback.py`: scrape S&P DJI for quarterly buybacks (PDF or HTML)
- Graceful degrade

**3.5B-5** — `feat(overlays): ERP US 4-method implementation`
- `src/sonar/overlays/erp.py`
- Methods per spec §4: DCF (scipy.optimize.newton), Gordon, EY, CAPE
- Canonical aggregation: median of 4 methods, erp_range_bps, methods_available
- Confidence per flags.md propagation + E4 canonical formula
- FactSet vs Yardeni divergence check → `ERP_SOURCE_DIVERGENCE` flag
- Damodaran xval → `XVAL_DRIFT` flag when |dev| > 20 bps
- Alembic migration 005: 5 erp_* tables per spec §8
- Dataclasses: NSSFitResult-style pattern (frozen, slots)

**3.5B-6** — `test(overlays): ERP US behavioral suite + fixtures`
- Fixtures per spec §7: us_2024_01_02, us_partial_3methods, us_partial_2methods, us_divergence_2020_03_23, damodaran_xval_2024_01_31
- ≥ 25 behavioral tests
- Coverage ≥ 90% on `src/sonar/overlays/erp.py`

### Sub-sprint 3.5C — CRP 7 countries (~2-3h)

**3.5C-1** — `feat(overlays): CRP vol_ratio country-specific via FMP+TE`
- `src/sonar/overlays/crp.py`
- `_compute_vol_ratio(country, date)`: fetch 5Y equity daily + 5Y bond yield daily via FMP/TE; compute rolling stds annualized; return `(vol_ratio, source, obs_count)` tuple
- Fallback logic: obs < 750 OR ratio ∉ [1.2, 2.5] → `damodaran_standard_ratio = 1.5`, flag `CRP_VOL_STANDARD`

**3.5C-2** — `feat(overlays): CRP RATING + SOV_SPREAD branches`
- Full compute per spec §4
- Benchmark shortcut DE/US/UK/JP → crp=0 + `CRP_BENCHMARK` flag
- PT/IT/ES/FR/NL SOV_SPREAD vs DE Bund NSS
- RATING branch via `ratings_consolidated` + `ratings_spread_calibration` (rating-spread overlay Week 3)
- Canonical hierarchy picker
- Alembic migration 006: 4 crp_* tables per spec §8

**3.5C-3** — `test(overlays): CRP 7-country behavioral suite`
- Fixtures per spec §7: pt_2026_04_17_cds (adapted no-CDS), de_benchmark, it, pt_vol_insufficient
- Skip CDS-branch fixtures (deferred)
- Coverage ≥ 90%

### Sub-sprint 3.5D — FR/IT linkers + EA ExpInf (~2-3h)

**3.5D-1** — `feat(connectors): aft_france + mef_italy linkers`
- `src/sonar/connectors/aft_france.py`: French Treasury OATi linker yield history
- `src/sonar/connectors/mef_italy.py`: Italian Treasury BTP€i linker yield history
- Endpoints investigated via live fetch; if not documented correctly, HALT per §4

**3.5D-2** — `feat(overlays): EA BEI + PT DERIVED implementations`
- Extend `src/sonar/overlays/expected_inflation.py`
- EA BEI via DE/FR/IT linker + ECB SDW EA-aggregate BEI fallback
- PT DERIVED: EA aggregate BEI + PT-EA 5Y rolling HICP differential (Eurostat)
- Differential cache in config (refresh quarterly)
- Flag `DIFFERENTIAL_TENOR_PROXY` for 1Y/2Y per spec I4 amendment

**3.5D-3** — `test(overlays): EA+PT ExpInf suite`
- Fixtures: de/fr/it_2024_01_02 BEI, pt_2024_01_02_derived, pt_differential_recompute
- Coverage ≥ 90%

### Sub-sprint 3.5E — Persistence + integration tests (~2-3h)

**3.5E-1** — `feat(db): ExpInf + CRP persistence helpers`
- `src/sonar/db/persistence_expinf.py`: `persist_exp_inflation_result(session, result)` mirror NSS pattern
- `src/sonar/db/persistence_crp.py`: `persist_crp_result(session, result)` same pattern
- Atomic transaction (session.begin), DuplicatePersistError pattern
- Migrations 007/008 if needed beyond 005/006

**3.5E-2** — `test(integration): 7-country vertical slice`
- Integration test: for each of US/DE/PT/IT/ES/FR/NL → fetch all connectors (cassette) → compute all overlays (NSS/ExpInf/ERP[US only]/CRP) → persist → query back → assert
- ERP only for US (other markets would require SXXP/FTAS/TPX index data — reuse existing TE coverage if available, otherwise skip)
- Assert k_e sane ranges post-pipeline

### Sub-sprint 3.5F — Daily cost-of-capital pipeline L6 (~1.5-2h)

**3.5F-1** — `feat(pipelines): daily-cost-of-capital orchestrator`
- `src/sonar/pipelines/daily_cost_of_capital.py`
- Workflow: NSS fetch → ExpInf fetch → ERP (US mature primary) → CRP per country → compose `k_e`
- Formula: `k_e(country) = nominal_rf_10Y(country) + β_country · ERP_mature(US) + CRP(country)` with β=1.0 stub
- Alembic migration 009: `cost_of_capital_daily` table (country_code, date, methodology_version_hash, rf_local_pct, erp_mature_bps, crp_bps, beta, k_e_pct, confidence, flags, created_at, UNIQUE triplet)
- CLI: `python -m sonar.pipelines.daily_cost_of_capital --country US --date 2024-01-02 [--all-t1]`

**3.5F-2** — `test(integration): cost-of-capital pipeline 7 countries`
- CLI smoke: run `--all-t1` covers US/DE/PT/IT/ES/FR/NL
- Assert k_e plausibility bands per country (US 8-11%, PT 9-13%, DE 7-9%, etc.)

**3.5F-3** — `docs(planning): Phase 1 Week 3.5 retrospective`
- Standard retrospective structure mirroring phase1-week1-retrospective.md
- Commits count, M1 progress assessment, CAL status updates, Week 4 kickoff agenda

---

## 4. HALT triggers (atomic)

1. FMP Ultimate API rate limit hit during 5Y historical fetches (unlikely but possible with 30Y+ queries) — halt, throttle + retry pattern
2. FactSet PDF URL format changes mid-sprint (weekly PDF link restructures) — halt, CC documents new URL pattern; resume after brief verification
3. Yardeni download returns 403 or layout fundamentally changed from reference — halt, surface to Hugo (may indicate consent-revocation signal)
4. aft_france / mef_italy endpoints wrong or authenticated — halt, fall back to ECB SDW EA-aggregate BEI only (PT still derives, but DE/FR/IT lose linker path)
5. TE historical yields endpoint missing tenor granularity — halt, evaluate fallback to NSS yield_curves_spot historical rows (already persisted)
6. Migration 005/006/007/008/009 ordering conflict with Week 2 001/002 or Week 3 003/004 — halt, reconcile
7. Damodaran histimpl.xlsx shape changed (new columns/removed) — halt, parser adaptation call
8. Any coverage regression > 3pp on existing scopes (overlays/connectors/db) — halt, investigate

"User authorized in principle" does NOT cover specific triggers. Atomic per SESSION_CONTEXT §Decision authority.

---

## 5. Acceptance

Per sub-sprint boundary checks, aggregated sprint-end:

### Sub-sprint boundaries
- **3.5A**: FMP connector cassette tests green; TE extension green; coverage connectors ≥ 95%
- **3.5B**: ERP US 4 methods operational; Damodaran xval deviation for Jan 2024 ≤ 20 bps; all ERP fixtures green; coverage overlays ≥ 90%
- **3.5C**: CRP 7 countries operational; vol_ratio country-specific active; benchmark shortcut correct
- **3.5D**: FR/IT linker fetch live (cassette-replayed) OR fallback documented; ExpInf EA BEI + PT DERIVED green
- **3.5E**: Persistence helpers complete; 7-country vertical slice integration green
- **3.5F**: CLI `daily_cost_of_capital --all-t1` produces 7 rows; plausibility assertions pass

### Sprint-end global
- [ ] 20–28 commits pushed, clean
- [ ] Migrations 005-009 applied cleanly (fresh dev DB round-trip downgrade/upgrade)
- [ ] Coverage: connectors ≥ 95%, db ≥ 94%, overlays ≥ 90%, pipelines ≥ 85%, global ≥ 92%
- [ ] Full test suite green: ≥ 250 unit + 30 integration tests
- [ ] All 7 countries (US/DE/PT/IT/ES/FR/NL) have persisted cost_of_capital_daily row for reference date 2024-01-02
- [ ] No `--no-verify` pushes

---

## 6. Report-back artifact export

**Mandatory artifact export** — tmux buffer truncates long reports.

Produce progressive artifacts at sub-sprint boundaries + final at sprint-end:

### Per-sub-sprint summaries
Write to `docs/planning/retrospectives/week3-5-sprint-{A,B,C,D,E,F}-report.md` as each sub-sprint completes. Include:
- Commits in that sub-sprint (SHAs + log)
- Coverage delta for affected scopes
- Test count + pass rate
- HALT triggers fired/resolved in that sub-sprint
- Timer for that sub-sprint vs budget
- Any deviation from brief
- New CAL entries surfaced

Commit each sub-sprint report in its own `docs(planning):` commit OR batched per CC judgement (not mandatory separate commits).

### Sprint-end consolidated retrospective
Write to `docs/planning/retrospectives/week3-5-sprint-final-report.md` at sprint close. Include:
- All commit SHAs grouped by sub-sprint (full list)
- Full coverage matrix (connectors/db/overlays/pipelines/global before/after)
- Complete test count breakdown
- All connector validation outcomes (table: connector / status / notes)
- Damodaran xval result for US Jan 2024
- FactSet vs Yardeni divergence for US current date
- k_e values for all 7 countries with expected range
- All HALT triggers fired (full narrative)
- All new CAL/P2 entries surfaced
- Blockers identified for Week 4
- Timer breakdown per sub-sprint vs budget

After sprint-end push, echo to tmux stdout:
```
REPORT ARTIFACT FINAL: docs/planning/retrospectives/week3-5-sprint-final-report.md
REPORT ARTIFACTS SUB-SPRINT: docs/planning/retrospectives/week3-5-sprint-{A..F}-report.md
```

### Brief tmux summary
After each sub-sprint boundary, echo 5-line summary to tmux:
```
SUB-SPRINT 3.5X DONE: N commits, X.XX% coverage (delta), Y tests pass, Z min vs budget
HALT triggers: [list or "none"]
Artifact: docs/planning/retrospectives/week3-5-sprint-X-report.md
```

Full content lives in artifact files — scp retrievable, git-durable.

---

## 7. Report-back content structure (for artifacts)

Per sub-sprint section:

```markdown
# Week 3.5 Sub-sprint {X} Report — {name}

## Summary
- Sub-sprint: 3.5{X}
- Commits: N (SHA1, SHA2, ...)
- Duration: Xh Ymin actual / Zh budget
- Status: COMPLETE / PARTIAL / HALTED

## Commits
| SHA | Scope |
|---|---|
| ... | ... |

## Coverage delta
| Scope | Before | After | Delta |
|---|---|---|---|
| ... | ... | ... | ... |

## Tests
- Added: N unit + M integration
- Pass rate: X/Y
- Failures (if any): [list]

## Validation results
[Connector live fetches, xval results, etc.]

## HALT triggers
[Fired/resolved or "none"]

## Deviations from brief
[Any interpretation beyond verbatim]

## New backlog items
[CAL/P2 entries to create]

## Blockers / next steps
[Anything blocking next sub-sprint or Week 4]
```

Final sprint report aggregates + adds global sections (full coverage matrix, k_e table, full commit list, Week 4 kickoff agenda).

---

*End of brief. Proceed sub-sprint-wise. Artifact export at every sub-sprint boundary mandatory. Final retrospective required at sprint close.*
