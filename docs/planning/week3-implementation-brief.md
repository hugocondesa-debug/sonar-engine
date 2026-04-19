# Week 3 Implementation Sprint — Execution Brief (v2, Opção B)

**Target**: Phase 1 Week 3 (full week, 5 days)
**Priority**: HIGH (M1 cost-of-capital primitives operational)
**Budget**: 15–20h CC autonomous (can span multiple tmux sessions)
**Commits**: ~15–20 across 3 sub-sprints
**Base**: main HEAD post overlays-spec-sweep-brief commits

---

## 1. Scope

In (Opção B ambicioso):

### ERP overlay
- US v0.1 all 4 methods (DCF, Gordon, EY, CAPE)
- EA v0.1 3 methods (DCF, Gordon, EY; CAPE skipped if FactSet fails, degraded gracefully)
- Canonical aggregation + Damodaran xval US only
- Connector dependencies: FRED (SP500, shiller proxies), TE (SXXP index level, fallback if CAL-035 permits), FactSet PDF scrape (risk-accept, skip on failure), multpl scrape (US dividend yield), spdji scrape (US buybacks)

### CRP overlay
- RATING method across T1 (rating-spread spec already present)
- SOV_SPREAD method for PT, IT, ES, FR, NL (vs Bund via NSS from Week 2)
- CDS branch: **skip** unless WGB connector validated mid-sprint
- vol_ratio: damodaran_standard=1.5 throughout (CAL-039 blocker)
- Benchmarks: DE, US, UK, JP → `crp=0` shortcut

### Expected Inflation overlay
- US v0.1 BEI (FRED DFII linkers validated Day 3) + SURVEY (SPF Philly + Michigan)
- EA v0.1 BEI via DE/FR/IT linkers (Bundesbank + connectors to build)
- PT v0.1 DERIVED (EA aggregate BEI + PT-EA 5Y differential via Eurostat HICP)
- 5y5y compounded derivation
- Anchor status computation vs `config/bc_targets.yaml`

### Supporting infrastructure
- `overlays/rating-spread` minimal implementation (already spec'd, not yet coded) — RATING method CRP precisa
- `connectors/te` base (for SXXP, FTAS, TPX market data — scope may degrade per CAL-035 findings)
- `connectors/shiller` (ie_data.xls download + parse)
- `connectors/factset_insight` (PDF scrape with graceful failure)
- `connectors/multpl` + `connectors/spdji` (web scrape US yields)
- `connectors/aft_france`, `connectors/mef_italy` (FR/IT linkers for EA BEI)

Out (defer Week 4+):
- UK ERP/CRP/ExpInf (Gilt yields, BoE DMP)
- JP ERP/CRP/ExpInf (Tankan, JGB curve)
- EM markets (BR, MX, TR, ZA, etc.)
- CDS branch CRP (unless CAL-039/WGB resolves mid-sprint)
- Country-specific vol_ratio (blocked CAL-039)
- L3 indices consuming these overlays (Week 4+)
- L4 cycles (Week 5+)

---

## 2. Spec reference

Post-sweep versions authoritative:
- `docs/specs/overlays/erp-daily.md` @ ERP_CANONICAL_v0.1
- `docs/specs/overlays/crp.md` @ CRP_CANONICAL_v0.1
- `docs/specs/overlays/expected-inflation.md` @ EXP_INF_CANONICAL_v0.1
- `docs/specs/overlays/rating-spread.md` @ RATING_SPREAD_v0.2
- `docs/specs/overlays/nss-curves.md` @ NSS_v0.1 (upstream, stable)
- `docs/specs/conventions/{units,flags,patterns,exceptions}.md`
- `docs/planning/phase1-coverage-policy.md`
- SESSION_CONTEXT §Decision authority + §Brief format

CAL tracking: CAL-035 through CAL-042 registered; check `calibration-tasks.md` for status before deciding connector degradation.

---

## 3. Sub-sprints + commits

### Sub-sprint 3A — Rating-spread + ExpInf US (Day 1-2, ~5-6h)

Rationale: rating-spread unblocks CRP RATING branch (CRP needs it); ExpInf US is pure FRED (validated), low-risk starter.

**3A-1** — `feat(overlays): rating-spread overlay v0.2 implementation`
- `src/sonar/overlays/rating_spread.py`: implement per spec
- Data sources: Damodaran annual backfill (xls download, parse) + agency scrape forward (S&P/Moody's/Fitch public releases)
- Tables: `ratings_raw`, `ratings_consolidated`, `ratings_spread_calibration`
- Alembic migration 003
- Unit tests + 1 integration test for calibration table lookup
- Scope: T1 16 countries ratings; spread calibration from Damodaran

**3A-2** — `feat(connectors): shiller ie_data + FRED T5YIE/T10YIE series`
- `src/sonar/connectors/shiller.py`: download ie_data.xls from shillerdata.com, parse CAPE + 10Y real earnings series
- Extend FRED connector: add `fetch_bei_series(country, tenor)` for T5YIE/T10YIE/T30YIE
- Cassette tests for both

**3A-3** — `feat(overlays): expected-inflation US v0.1 (BEI + SURVEY)`
- `src/sonar/overlays/expected_inflation.py`: core compute functions
- BEI path: FRED nominal DGS + real DFII → per-tenor BEI
- SURVEY path: SPF Philly + FRED MICH/MICH5Y
- Canonical hierarchy picker + anchor_status computation
- `config/bc_targets.yaml` (Fed/ECB/BoE/BoJ/BoC etc)
- Migration 004: 5 `exp_inflation_*` tables
- Tests: fixture `us_2024_01_02_bei` + `us_2024_01_02_canonical` per spec §7

**3A-4** — `feat(connectors): SPF Philly + Michigan surveys (extend FRED)`
- Connector for SPF Philly quarterly releases (CSV from philadelphiafed.org)
- FRED MICH series already via generic fetch_series; add domain wrapper
- Cassette tests

**3A-5** — `test(integration): US cost-of-capital vertical slice (incomplete)`
- Integration test: NSS US + ExpInf US + rating-spread US lookup → persist all → query back
- ERP + CRP pending sub-sprints 3B/3C

### Sub-sprint 3B — ERP overlay US + EA (Day 2-3, ~5-7h)

**3B-1** — `feat(connectors): multpl + spdji buyback scrapers (US)`
- `connectors/multpl.py`: scrape multpl.com for S&P 500 dividend yield (daily)
- `connectors/spdji_buyback.py`: scrape S&P DJI buyback yield (quarterly)
- Graceful failure: 404/parse error → `DataUnavailableError`, caller decides skip
- Cassette tests for happy path; mock tests for failure path

**3B-2** — `feat(connectors): FactSet Earnings Insight PDF (risk-accepted)`
- `connectors/factset_insight.py`: PDF scrape via pdfplumber
- Endpoints: weekly FactSet Earnings Insight PDFs (if URL stable)
- Explicit failure handling: on parse error, emit `OVERLAY_MISS` flag; never block caller
- Document URL stability risk in module docstring; Phase 2 candidate for licensed API

**3B-3** — `feat(connectors): TE market indexes (SXXP initial; CAL-035 gated)`
- Check CAL-035 status: if validated mid-sprint, implement full TE `/markets/historical/:IND`; if not, implement SXXP only via alternative (e.g. ECB SDW STOXX data if available) OR degrade EA ERP to 3 methods skipping CAPE entirely
- `connectors/te.py` base (BaseConnector subclass, API auth via env TE_API_KEY)
- Scope: minimum SXXP daily close; UK/JP deferred

**3B-4** — `feat(overlays): erp-daily v0.1 US implementation (4 methods)`
- `src/sonar/overlays/erp.py`: DCF, Gordon, EY, CAPE compute functions
- DCF: `scipy.optimize.newton` with bounds
- Gordon: `yield + g_sustainable − risk_free`
- EY: `forward_earnings/index − risk_free`
- CAPE: `(1/CAPE) − real_risk_free`
- Canonical aggregation + Damodaran xval (US only via Damodaran histimpl.xlsx)
- Migration 005: 5 `erp_*` tables
- Tests: fixtures us_2024_01_02 + us_partial_3methods + us_partial_2methods per spec §7

**3B-5** — `feat(overlays): erp-daily EA implementation (3-4 methods)`
- EA ERP via SXXP + Bund NSS + ECB SPF forecasts (growth estimate)
- CAPE: skip if FactSet fails to parse STOXX earnings data; log degradation
- Fixture ea_2024_01_02 per spec §7

**3B-6** — `test(integration): ERP US canonical persist + query + Damodaran xval`
- End-to-end test: all connectors → fit all methods → canonical select → persist 5 rows → query canonical
- Assert `xval_deviation_bps < 20` for Jan 2024 vs Damodaran annual update

### Sub-sprint 3C — CRP + ExpInf EA/PT (Day 4-5, ~5-7h)

**3C-1** — `feat(connectors): aft_france + mef_italy linkers`
- French OATi linker + Italian BTP€i linker connectors (Treasury data download, parse)
- Cassette tests
- Feed into ExpInf EA BEI path

**3C-2** — `feat(overlays): expected-inflation EA BEI (DE/FR/IT)`
- Extend `expected_inflation.py` for EA: Bundesbank linkers (already exist) + aft_france + mef_italy
- ECB SDW EA aggregate BEI as DERIVED source for PT
- Fixtures: pt_2024_01_02_derived + de/fr/it_2024_01_02 BEI
- Cross-method divergence flag (BEI vs ECB SPF survey)

**3C-3** — `feat(overlays): expected-inflation PT DERIVED`
- PT path: EA aggregate BEI + PT-EA 5Y HICP differential (Eurostat)
- Differential computation + cache in config (refresh quarterly)
- Fixture pt_2024_01_02_derived + pt_differential_recompute
- Flag `DIFFERENTIAL_TENOR_PROXY` for 1Y/2Y per I4 spec amendment

**3C-4** — `feat(overlays): crp v0.1 RATING + SOV_SPREAD (5 countries)`
- `src/sonar/overlays/crp.py`: hierarchy picker (CDS skip, SOV_SPREAD primary, RATING fallback)
- Benchmark shortcut: DE/US/UK/JP → `crp=0`
- PT/IT/ES/FR/NL SOV_SPREAD from NSS yield_curves_spot (already persisted Week 2)
- vol_ratio fallback to 1.5 (damodaran_standard; CAL-039 blocker)
- Migration 006: 4 `crp_*` tables
- Fixtures: pt_2026_04_17_cds (adapted for no-CDS-only-SOV), de_benchmark, gh_rating_only (adapted to PT rating-only if GH outside scope)

**3C-5** — `feat(pipelines): daily-cost-of-capital US + EA (L6 preview)`
- Pipeline wiring: NSS → ExpInf → ERP → CRP → compose `k_e = rf + β·ERP + CRP`
- Stub β=1.0 (equity beta refinement Phase 2)
- Write to new table `cost_of_capital_daily` (scope creep accepted — enables consumer testing)
- CLI: `python -m sonar.pipelines.daily_cost_of_capital --country US --date 2024-01-02`

**3C-6** — `test(integration): full M1 cost-of-capital US+EA+PT vertical slice`
- End-to-end: fetch everything, compute everything, persist everything, query k_e(US, DE, PT, IT, ES, FR, NL)
- Assert sane ranges per country (US k_e ~8-10%, PT k_e ~9-11% with CRP ~50-100 bps, etc.)

**3C-7** — `docs(planning): Phase 1 Week 3 retrospective`
- Commits count, deliverables, CAL status updates, Week 4 kickoff agenda
- Coverage + test count final stats

---

## 4. HALT triggers

1. **Migration 003-006 ordering conflict**: any of rating-spread/ExpInf/ERP/CRP migrations conflict with existing Week 2 migrations 001-002 or each other on FK or index names — halt, reconcile
2. **FactSet PDF URL changed/moved**: connector works in cassette but live fetch 404s — document in module docstring, emit `DataUnavailableError`, proceed with 3-method ERP. Do NOT halt for this; this is the risk-accepted path per scope.
3. **TE validation (CAL-035) still pending end of Day 3**: make scope call — ship EA ERP 3 methods skipping CAPE; halt only if alternative SXXP source (ECB SDW) also unavailable
4. **Aft/MEF connector endpoints documented are wrong**: many treasury websites restructure — halt, investigate, either fix or fall back to ECB SDW EA-aggregate-only BEI
5. **Cross-cycle integration surfaces Policy 1 fail-mode question**: if composite aggregation needs changes, halt per SESSION_CONTEXT decision authority rule #3

"User authorized in principle" only covers this sprint scope (Opção B). Specific triggers require explicit halt.

---

## 5. Acceptance

Per sub-sprint, checked at sub-sprint boundary:

### 3A (Day 1-2 close)
- [ ] rating-spread overlay live, migration 003 clean, ≥10 countries calibrated
- [ ] expected-inflation US BEI+SURVEY live, migration 004 clean
- [ ] Fixtures us_2024_01_02_bei + us_2024_01_02_canonical green
- [ ] Coverage overlays scope ≥ 92%

### 3B (Day 2-3 close)
- [ ] ERP US 4 methods live, migration 005 clean
- [ ] Damodaran xval for US Jan 2024 within 20 bps
- [ ] ERP EA 3-4 methods live (CAPE depends on FactSet+SXXP success)
- [ ] Fixtures us_2024_01_02 + ea_2024_01_02 green
- [ ] Coverage overlays scope ≥ 90% (dip tolerable for ERP complexity)

### 3C (Day 4-5 close)
- [ ] CRP PT/IT/ES/FR/NL SOV_SPREAD + RATING methods; DE/US benchmarks =0
- [ ] ExpInf EA BEI + PT DERIVED live; migration 006 clean
- [ ] Full M1 cost-of-capital vertical slice integration test green for US + DE + PT + IT + ES + FR + NL (7 countries)
- [ ] Week 3 retrospective committed
- [ ] Global coverage ≥ 92% maintained; connectors ≥ 95%; db ≥ 94%; overlays ≥ 90%

---

## 6. Report-back (single paste at Week 3 close)

1. All commit SHAs grouped by sub-sprint + `git log --oneline -20`
2. Migrations applied: 003/004/005/006 status
3. Coverage deltas per scope (connectors, db, overlays, pipelines, global)
4. Test count + pass rate per sub-sprint
5. Per sub-sprint timer vs budget estimate
6. Connector validation outcomes:
   - TE `:IND` endpoints (CAL-035): validated or degraded?
   - FactSet PDF scrape: stable or flagged?
   - multpl/spdji scrapers: stable?
   - aft_france/mef_italy: endpoints correct?
   - WGB (CDS): any progress or deferred to Week 4?
7. Damodaran xval US Jan 2024: |deviation_bps|
8. k_e sane-range assertions: 7 countries × actual value + expected range
9. New CAL entries surfaced (expect 2-4 new from implementation reality)
10. HALT triggers fired + resolutions
11. Blockers for Week 4 (L3 indices implementation)

---

*End of brief. Proceed sub-sprint-wise; single report at Week 3 close.*
