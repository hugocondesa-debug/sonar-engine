# Week 2 Close Sprint — Execution Brief (format v2)

**Target**: Phase 1 Week 2 Day 3 PM + Day 4 + Day 5
**Priority**: HIGH (Week 2 gate close; DE T1 second country unlocks Week 3)
**Budget**: 6–10h CC autonomous
**Commits**: ~8–12 across 3 sub-sprints
**Base**: `6476672` (main HEAD post consolidated sweep)

---

## 1. Scope

**In**:
- Day 3 PM sub-sprint: CAL-033 option (a) — relax MIN_OBSERVATIONS=5 for linker-only fits; US real curve unblocks end-to-end; Fed GSW static xval hook (canary vs SONAR NSS)
- Day 4 sub-sprint: pipeline L8 `daily-curves` US skeleton; ECB SDW connector scaffolding
- Day 5 sub-sprint: Bundesbank connector; DE NSS vertical slice replicate; Week 2 retrospective

**Out (defer)**:
- Full Fed GSW historical backfill (static file snapshot Day 3 PM; daily live xval = Day 4+ or Week 3)
- ERP overlay v0.1 (Week 3)
- FR/IT/ES/NL/PT T1 euro core (Week 3)
- TE connector base (Week 3 when ERP needs equity yields)
- UK BoE / JP MoF (Week 3-4)

---

## 2. Spec reference

- `docs/specs/overlays/nss-curves.md` @ NSS_v0.1 (linker threshold decision per CAL-033)
- `docs/specs/pipelines/daily-curves.md` (L8 orchestration contract)
- `docs/data_sources/monetary.md` — ECB SDW yield curves endpoint
- `docs/data_sources/country_tiers.yaml` — DE tier T1, Bundesbank primary per `nss-curves.md` §2
- `docs/specs/conventions/flags.md` — flag emission for xval drift
- Fed GSW static: https://www.federalreserve.gov/data/nominal-yield-curve.htm (feds200628.csv)

---

## 3. Commits

### Sub-sprint Day 3 PM — CAL-033 resolution + Fed GSW xval

**Commit 3PM-1/3** — CAL-033 option (a): linker threshold relaxation
```
feat(overlays): relax MIN_OBSERVATIONS=5 for linker-only fits (CAL-033)

Spec §6 row 1 keeps n_obs<6 → InsufficientDataError for nominal.
Linker-only fits (curve_input_type="linker_real") accept n_obs≥5 via
LINKER_MIN_OBSERVATIONS=5 constant. US TIPS (DFII5/7/10/20/30) now
fits. Real curve for US unblocks end-to-end.

Tests: linker fit with 5 tenors green; nominal with 5 tenors still
raises per spec.

Closes CAL-033. No NSS_v0.1 bump (spec §6 row 1 applies to nominal
curves only; linker relaxation is implementation detail within
"linker_real" path).
```

**Commit 3PM-2/3** — Real curve US vertical slice green
```
test(integration): US real curve live persist via TIPS direct-linker

Vertical slice test previously asserted real=None (CAL-033 block).
Now exercises full path: FRED DFII* → fit_nss (linker threshold=5) →
derive_real_curve → persist → query yield_curves_real. Expected real
10Y ≈ 0.0185 ± 15 bps per spec §7 real_us_2024_01_02 fixture.
```

**Commit 3PM-3/3** — Fed GSW xval hook (static)
```
feat(overlays): Fed GSW xval canary hook (static snapshot)

Add overlays/validation/fed_gsw.py: parse Fed feds200628.csv
snapshot committed to tests/fixtures/xval/feds200628_2024-01-02.csv
(single-day subset, not full historical). Compare SONAR NSS fit
vs GSW published β/λ for US 2024-01-02. Emit XVAL_DRIFT flag when
|deviation| > 10 bps at any tenor ∈ {2Y,5Y,10Y,30Y} per spec §7.

Not wired into live pipeline yet — invoked by integration test only.
Day 4+ promotes to pipeline step.
```

### Sub-sprint Day 4 — Pipeline + ECB SDW scaffolding

**Commit D4-1/3** — Pipeline daily-curves US skeleton
```
feat(pipelines): daily-curves US skeleton (L8)

src/sonar/pipelines/daily_curves.py: orchestrates L0 FRED fetch →
L2 NSS fit → L2 derive zero/forward/real → L1 persist for a given
(country, date). Single-country US-only in this commit; Week 3
generalizes loop across country_tiers.yaml T1.

CLI entrypoint: python -m sonar.pipelines.daily_curves --country US
--date 2024-01-02. Uses session factory from Week 1; atomic persist
per day.

Errors surface as exit codes: 0 clean, 1 InsufficientDataError,
2 ConvergenceError, 3 DuplicatePersistError, 4 IO/network.
```

**Commit D4-2/3** — ECB SDW connector base
```
feat(connectors): ECB SDW connector base (L0)

src/sonar/connectors/ecb_sdw.py: HTTP client for ECB Statistical
Data Warehouse. Pattern mirrors FREDConnector — BaseConnector ABC,
fetch_series, domain wrapper fetch_yield_curve_nominal(country, date).

Covers EA AAA Svensson curve via SDW key YC.B.U2.EUR.4F.G_N_A.SV_C_YM.*
(placeholder — exact series keys verified during cassette recording).
DE-specific Bundesbank connector separately (Day 5) per spec §2
primary hierarchy.

Unit tests cassette-replayed. One live canary @pytest.mark.live.
```

**Commit D4-3/3** — ECB SDW + pipeline integration (smoke)
```
test(integration): ECB SDW smoke + daily-curves US end-to-end

Two new integration tests:
1. ECB SDW EA AAA fetch smoke (cassette replay; verifies schema)
2. daily-curves US pipeline end-to-end (live FRED cassette → fit →
   persist → query → assert all 4 tables populated for US 2024-01-02)

Prep for Day 5 Bundesbank vertical slice replicate.
```

### Sub-sprint Day 5 — Bundesbank + DE vertical slice + Week 2 close

**Commit D5-1/3** — Bundesbank connector
```
feat(connectors): Bundesbank Svensson yield curve (L0, DE primary)

src/sonar/connectors/bundesbank.py: fetches Bundesbank daily Svensson
parameters (β0, β1, β2, β3, τ1, τ2) + implied yields for DE per spec
§2 T1 DE primary. Endpoint: https://api.statistiken.bundesbank.de/...

Two fetch modes:
- fetch_yield_curve_nominal(country="DE", date): returns {tenor: yield_pct}
  for standard output tenors (10 maturities available).
- fetch_svensson_params(date): returns published Bundesbank params
  (used for direct xval vs SONAR fit, same day).

Cassette replay tests. Live canary marked.
```

**Commit D5-2/3** — DE NSS vertical slice
```
test(integration): DE NSS vertical slice via Bundesbank

Mirror US vertical slice for DE: Bundesbank fetch → SONAR NSS fit
→ derive → persist → query. Cross-validation against published
Bundesbank β/λ: expect |deviation| < 5 bps at 2Y/5Y/10Y/30Y per
spec §7 de_bund_2024_01_02 fixture.

If deviation > 5 bps: XVAL_DRIFT flag emitted; test asserts flag
present + confidence reduced per spec §6. Spec tolerance >5 bps
triggers CAL entry.

DE CAL-030 trigger check: β0 bound (0, 0.20) — if Bundesbank 2024-01-02
has any yield < 0 (historical 2019-2022), CAL-030 HIGH upgrade fires.
```

**Commit D5-3/3** — Week 2 retrospective
```
docs(planning): Phase 1 Week 2 retrospective

Summary of Week 2: commits count, M1 progress (US+DE vertical slices),
blockers resolved (P2-023, CAL-029, CAL-031, CAL-032, CAL-033),
blockers opened/deferred (CAL-034, CAL-030 conditional, P2-026, P2-027),
coverage progression, ritmo calibration (chat+CC process revised
2026-04-20, Day 3 AM 50 min vs 90-120 budget).

Template mirror docs/planning/phase1-week1-retrospective.md structure.
Week 3 kickoff agenda appended.
```

---

## 4. HALT triggers

1. CAL-033 relaxation breaks nominal path tests (regression in MIN_OBSERVATIONS enforcement for non-linker curves)
2. Fed GSW feds200628.csv format has changed since last snapshot (Fed restructured publication) — static file parser fails
3. ECB SDW SDMX XML schema surprises not anticipated by connector base abstraction (requires structural refactor of BaseConnector, not just new connector subclass)
4. Bundesbank endpoint requires authentication/API key not documented in data_sources/monetary.md — treat as CAL-019 analogue (new CAL, defer live DE Day 5 integration; scaffolding only)
5. DE 2024-01-02 Bundesbank 10Y yield < 0 (unlikely by late 2023 rates, but CAL-030 upgrade trigger) — still proceed per CAL-030 option pre-configured; flag for Hugo review

"User authorized in principle" does NOT cover specific triggers. Atomic.

---

## 5. Acceptance

Per sub-sprint, checked at sprint boundary:

### Day 3 PM
- [ ] CAL-033 closed in calibration-tasks.md (status appended in commit body OR follow-up sweep)
- [ ] Linker fit with 5 tenors green; nominal with 5 tenors still raises InsufficientDataError
- [ ] US vertical slice integration test: query(NSSYieldCurveReal).count() == 1 for 2024-01-02
- [ ] Fed GSW canary returns deviation in bps per tenor; XVAL_DRIFT flag emitted when > 10 bps
- [ ] Coverage: overlays scope ≥ 93% (slight dip tolerable for xval module), connectors unchanged ≥ 97%

### Day 4
- [ ] `python -m sonar.pipelines.daily_curves --country US --date 2024-01-02` exit code 0 on clean run
- [ ] ECB SDW connector: cassette tests green, ≥ 95% coverage on new module
- [ ] daily-curves end-to-end test asserts all 4 yield_curves_* tables populated

### Day 5
- [ ] Bundesbank connector cassette tests green
- [ ] DE vertical slice test green: xval vs published β/λ within spec §7 tolerance OR XVAL_DRIFT properly flagged
- [ ] CAL-030 status evaluated post-DE fit (close if no negative yields in 2024-01-02 data; upgrade HIGH if any tenor < 0)
- [ ] Week 2 retrospective committed
- [ ] Global coverage ≥ 94% maintained; connectors ≥ 97%; db ≥ 95%; overlays ≥ 92%

---

## 6. Report-back (at sprint-end, single paste to chat)

1. All commit SHAs grouped by sub-sprint + `git log --oneline -12`
2. Coverage deltas per scope (connectors, db, overlays, pipelines [new], global)
3. Test count + pass rate at sprint-end
4. Per sub-sprint: timer actual vs budget (Day 3 PM ~2h, Day 4 ~3h, Day 5 ~3h expected)
5. CAL-030 resolution post-DE (closed / upgraded HIGH / deferred)
6. Fed GSW xval result for US 2024-01-02: max |deviation_bps| across {2Y,5Y,10Y,30Y}
7. DE xval result: max |deviation_bps| vs Bundesbank published β/λ
8. HALT triggers fired + resolutions (if any)
9. New backlog items surfaced (CAL-XXX / P2-XXX) for end-of-sprint chat triage
10. Blockers identified for Week 3 start (if any)

---

*End of brief. Proceed sprint-wise; single report-back at Week 2 close.*
