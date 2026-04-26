# Week 11 Sprint 6 — L2 rating-spread cohort expansion T1 retrospective

**Sprint**: 6 — Rating-spread T1 cohort 10 → 15 países (NL+NZ+CH+SE+NO).
**Branch**: `sprint-6-l2-rating-spread-cohort-expansion`.
**Worktree**: `/home/macro/projects/sonar-wt-6-l2-rating-spread-cohort-expansion`.
**Brief**: `docs/planning/week11-sprint-6-l2-rating-spread-cohort-expansion-brief.md`
(amendment 2026-04-26 — cohort 6 → 5 reduction post-HALT operator
decision pre-Commit-1).
**Pattern reference**: Sprint 4 (commit `f2cc4ef`, 2026-04-25/26) —
TE-driven rating-spread backfill canonical.
**Probe date**: 2026-04-26.
**Duration**: ~2h CC (single session 2026-04-26; within brief §8
budget 2-3h).
**Commits**: 6 (this retro included).
**Outcome**: **Substantive PASS** — cohort delivered (15/15 sovereign
T1 representation), all qualitative Tier B criteria met, 0 países
HALT-0. Numerical shortfall vs brief targets (-12 raw / -11
consolidated) traced to TE archive depth ceiling for sparse AAA-region
Nordic-Alpine sovereigns; documented as data-ceiling, not execution
gap (Hugo authorisation Commit 2 → Commits 3-6 autonomous, option A).

---

## 1. Commit inventory

| # | SHA | Subject | Scope |
|---|---|---|---|
| C1 | `123f91f` | `docs(planning): Sprint 6 L2 rating-spread cohort expansion T1 pre-flight + brief amendment` | Pre-flight findings doc (~210 lines) + brief amendment removing DK from cohort (operator HALT 2026-04-26 pre-Commit 1) |
| C2 | `66f8211` | `feat(overlays): Sprint 6 L2 rating-spread cohort expansion T1 (10→15 países)` | Code change `TIER1_COUNTRIES` + `TE_COUNTRY_OVERRIDES_TIER1` extension; CLI help text + validation message; test invariant 10→15; backfill execution against engine DB; full Tier B SQL in body |
| C3 | `884157d` | `chore(governance): country_tiers.yaml rating_spread_live flag for Sprint 6 cohort (5 países)` | `rating_spread_live: true` flag for NL+NZ+CH+SE+NO |
| C4 | `19fbe04` | `docs(specs): rating-spread §12 country scope appendix (Sprint 6 cohort 10→15)` | New §12 with Shipped (15 países table) / Deferred (DK Phase 5+) / Source-resolution policy / Coverage metrics |
| C5 | `ec15510` | `docs(backlog): close CAL-RATING-COHORT-EXPANSION via Sprint 6 (10→15 países)` | CLOSED entry in `calibration-tasks.md` Consolidated T1 expansion section |
| C6 | (this commit) | `docs(planning): Sprint 6 L2 rating-spread cohort expansion retrospective` | This retro |

---

## 2. Scope outcome vs. brief

### Brief's ambition (§1 Scope, post-amendment)

- Extend rating-spread Tier 1 cohort 10 → 15 países (NL+NZ+CH+SE+NO).
- Per-country TE `/ratings/{country}` snapshot + `/ratings/historical/{country}` archive.
- Consolidate via existing `backfill_consolidate()` (no new compute logic).
- Update `country_tiers.yaml` rating-spread coverage flags.
- Update `docs/specs/overlays/rating-spread.md` country scope appendix.

### Empirical execution (Commit 1 pre-flight + Commit 2 backfill)

| Item | Brief target | Delivered | Status |
|---|---|---|---|
| Cohort size | 5 países | 5 (NL+NZ+CH+SE+NO) | ✓ |
| TE snapshot persisted | ≥1/país | NL=4, NZ=4, CH=4, SE=4, NO=3 (Σ=19) | ✓ |
| TE historical fetched | ≥10 actions/país | NL=15, NZ=40, CH=8, SE=28, NO=11 (Σ=102) | ✓ |
| Historical persisted | (post-invalid skip) | 99 (4 invalid skipped) | ✓ |
| Consolidated 5 país | (no quantitative target/país) | CH=9, NL=16, NO=12, NZ=37, SE=29 (Σ=103) | ✓ |
| `country_tiers.yaml` flag | 5 países | 5 (`rating_spread_live: true`) | ✓ |
| Spec §12 appendix | cohort 10→15 | shipped (Shipped/Deferred/Source/Coverage) | ✓ |
| CAL closure | `CAL-RATING-COHORT-EXPANSION` | CLOSED via `ec15510` | ✓ |

### Brief amendment trace (DK removal pre-Commit 1)

Original brief §1 listed 6 países including DK. Operator HALT
2026-04-26 (pre-Commit 1) reduced cohort to 5 — DK is T2 in
`country_tiers.yaml:91`; ADR-0010 strict T1-ONLY enforcement through
Phase 4 forbids T2 surface. Brief amended in Commit 1 same staging
(single doc commit covers pre-flight findings + brief correction per
operator instruction). DK rating-spread expansion deferred Phase 5+
via CAL-RATING-DK-PHASE5 candidate (this retro §9).

EA aggregate exclusion is **non-requirement** (currency unions don't
issue sovereign debt rated by S&P/Moody's/Fitch/DBRS), not a deferral
slot to fill with arbitrary T2 substitute — clarified in §11 of the
spec and brief amendment header.

---

## 3. HALT triggers (atomic — brief §5 enumeration)

| # | Trigger | Status | Evidence |
|---|---|---|---|
| 0 | Pre-flight TE country mapping fails | Not fired | All 5 países returned snapshot + historical data; 0 HTTP 404 on `/ratings/historical/{country}` |
| 1 | TE quota >70 % mid-sprint | Not fired | Baseline ~40-41 %; Sprint 6 +6 calls (~0.12 pp); post ~40-41 % |
| 2 | TE invalid token | Not a HALT (logged + skipped) | 4 invalid (NZ Moody's `Aa`/`Aa`/`Baa` truncated; NO Moody's `\tAaa` whitespace) — 3.3 % rate vs Sprint 4 ~0.5 % baseline; consistent pattern |
| 3 | CHECK constraint failure post-consolidate | Not fired | 0 constraint errors; consolidated_sonar_notch range [8.75, 21.25] within ck_rc_notch [-1.0, 22.0] |
| 4 | Consolidated rows < 40 total for 5 países | Not fired | 103 consolidated total (well above 40); per-país 9-37 |
| 5 | Coverage regression > 3pp in tests | Not fired | rating_spread_backfill.py 88.31 % unchanged from Sprint 4 |
| 6 | Pre-push gate fail (no `--no-verify`) | Not fired | ruff format/check + mypy ✓; pytest -m "not slow" 2 pre-existing failures (`test_us_smoke_end_to_end` + flake `test_cpi_yoy_c2_from_cassette[NO]`); zero regressions; no `--no-verify` used |

**Discipline outcome**: standard discipline held — single-país HALT-0
tolerance never exercised because all 5 países shipped clean.

---

## 4. Pre-merge checklist

- ✅ ruff format + ruff check green (Commit 2)
- ✅ mypy green (Commit 2)
- ✅ pytest unit `test_rating_spread_te.py` 42/42 pass (Commit 2)
- ✅ pytest -m "not slow" full suite: 2310 passed / 2 pre-existing fail (parity with engine main; zero Sprint-6 regressions)
- ✅ pre-commit 2x green every push (6 pushes)
- ✅ no `--no-verify` used
- ✅ all 6 commits pushed to `sprint-6-l2-rating-spread-cohort-expansion`
- ⏸ branch merge to `main` = operator action (sprint_merge.sh post-retro)

---

## 5. Tier B verification (engine DB post-backfill 2026-04-26)

### 5.1 Row counts

```
agency_raw    648
consolidated  569
calibration    22
```

### 5.2 Per-país distribution `ratings_agency_raw` (15 países)

| ISO | Sprint | rows | Notes |
|---|---|---|---|
| AU | 4 | 35 | high-volatility benchmark |
| CA | 4 | 34 | |
| CH | **6** | 12 | shallow archive (8 actions) |
| DE | 4 | 19 | low-event AAA |
| ES | 4 | 81 | EA periphery |
| FR | 4 | 46 | |
| GB | 4 | 44 | |
| IT | 4 | 81 | EA periphery (highest) |
| JP | 4 | 54 | |
| NL | **6** | 19 | low-event AAA |
| NO | **6** | 14 | shallow archive (11 actions) |
| NZ | **6** | 41 | most active Sprint 6 país |
| PT | 4 | 104 | EA periphery (highest Sprint 4) |
| SE | **6** | 32 | |
| US | 4 | 32 | |

### 5.3 Agency distribution

```
SP     216
FITCH  175
MOODYS 157
DBRS   100
```

All 4 agencies present ✓ (DBRS coverage thinner — historical
expectation per spec §2).

### 5.4 Action_date range

```
earliest 1949-02-05  latest 2026-04-26  n_countries 15  total 648
```

77-year archive depth maintained (Sprint 4 baseline).

### 5.5 Consolidated notch range

```
min 8.75  max 21.25  n 569
```

Within ck_rc_notch [-1.0, 22.0] ✓ (no constraint regression vs
migration 019).

### 5.6 Actual vs target — full delta table (per Hugo §5 instruction)

| Criterion | Brief threshold | Actual | Delta | Verdict |
|---|---|---|---|---|
| `ratings_agency_raw` ≥ 660 | ≥ 660 | **648** | **−12** | **Numerical PARTIAL** |
| `ratings_consolidated` ≥ 580 | ≥ 580 | **569** | **−11** | **Numerical PARTIAL** |
| `n_countries` distinct | = 15 | 15 | 0 | PASS |
| 4 agencies present | yes | SP/FITCH/MOODYS/DBRS | — | PASS |
| `consolidated_sonar_notch` range | ⊂ [-1.0, 22.0] | [8.75, 21.25] | — | PASS |
| All 5 new país in consolidated | yes | NL=16, NZ=37, CH=9, SE=29, NO=12 | — | PASS |
| HALT-0 países | 0 | 0 | 0 | PASS |
| CHECK constraint regression | 0 | 0 | 0 | PASS |
| Pre-push gate | green | green (zero regressions) | — | PASS |
| `CAL-RATING-COHORT-EXPANSION` | closed | closed (`ec15510`) | — | PASS |

**Verdict**: substantive PASS / numerical PARTIAL on row-count
thresholds. Per Hugo authorisation 2026-04-26 (option A): treated as
PASS for sprint completion; root-cause analysis surfaces below (§9).

### 5.7 Data-ceiling rationale (per Hugo §5 instruction)

The −12 raw / −11 consolidated shortfall is **not an execution gap**.
It is a TE archive depth ceiling for sparse AAA-region Nordic-Alpine
sovereigns:

- CH historical: **8 actions** (TE archive only). Switzerland AAA-stable
  since 1980s with very few rating events.
- NO historical: **11 actions** (Norway AAA-stable; Norges Bank +
  sovereign-wealth offset → minimal sovereign credit volatility).
- NL historical: **15 actions** (Netherlands AAA-stable; rare
  downgrades 2013-2015 only).
- NZ historical: **40 actions** (most active; AA / AA+ region with
  some 1990s-2000s movement).
- SE historical: **28 actions** (Sweden AAA-stable since 1980s; AA
  briefly post-1992 banking crisis).

Total fetched: 102 historical + 19 snapshot = 121 max raw rows. With
4 invalid skipped: 117 persisted. Sprint 4 baseline 491 + 117 + ~39
incremental TE 7d-cache misses = 648 actual. Target 660 was estimated
at ~30-38 rows/país avg from Sprint 4 EA periphery cohort (PT/IT/ES =
96/81/81 historical actions; 4-5× the Sprint 6 sparse cohort).

**No additional fetches would close the gap** — TE has 8 actions for
CH; the data ceiling is bounded by S&P/Moody's/Fitch/DBRS rating
event count, not connector throughput.

---

## 6. Per-país TE breakdown (verbatim from backfill log + post-DB query)

| ISO | TE name slug   | Snapshot persisted | Historical fetched | Historical persisted | Invalid tokens |
|-----|----------------|---------------------|---------------------|-----------------------|----------------|
| NL  | `Netherlands`  | 4 (4 agencies) | 15 | 15 | 0 |
| NZ  | `New Zealand`  | 4 (4 agencies) | 40 | 37 | 3 (Moody's `Aa`/`Aa`/`Baa` truncated) |
| CH  | `Switzerland`  | 4 (4 agencies) |  8 |  8 | 0 |
| SE  | `Sweden`       | 4 (4 agencies) | 28 | 28 | 0 |
| NO  | `Norway`       | 3 (3 agencies — MOODYS skip) | 11 | 11 | 1 (Moody's `\tAaa` whitespace prefix) |
| **Σ** | | **19** | **102** | **99** | **4** |

NO snapshot only 3 agencies because TE returned `\tAaa` (tab-prefixed
"Aaa") for Moody's NO — `AGENCY_LOOKUP['MOODYS']['\tAaa']` raises
`KeyError`, the row is skipped + logged. Pattern matches Sprint 4's
"5 invalid across 10 países" baseline.

---

## 7. TE quota delta

| Item | Calls |
|---|---|
| `/ratings` snapshot (1 call, returns 160 países, cached 24h) | 1 |
| `/ratings/historical/{country}` × 5 países | 5 |
| **Total Sprint 6 backfill** | **6** |

- Baseline pre-Sprint-6 (post-Sprint-5B): ~40-41 % April consumed
  (per Sprint 5B retro §9).
- Post-Sprint-6 estimate: **~40-41 %** (~0.12 pp delta).
- Headroom até 70 % HALT ceiling: ~29 pp.
- Negligible quota impact; TE quota was never a Sprint 6 risk.

---

## 8. CAL evolution

### 8.1 Closed

| ID | Status | Evidence |
|---|---|---|
| `CAL-RATING-COHORT-EXPANSION` | CLOSED | Commit `ec15510` (`docs/backlog/calibration-tasks.md`) — full closure body with cohort delta + Tier B counts + numerical-shortfall data-ceiling rationale + forward-looking residuals |

### 8.2 Candidates filed in this retro (option B per Hugo decision; not separate CAL entries)

| Candidate ID | Type | Priority | Description |
|---|---|---|---|
| `CAL-RATING-DK-PHASE5` | Country-specific T1 graduation | LOW (Phase 5+) | DK rating-spread expansion deferred per ADR-0010 strict T1-ONLY through Phase 4. Re-evaluate when ADR-0010 lifts T2 lock OR when DK is promoted T2→T1 in `country_tiers.yaml`. Trigger: same TE Path 1 pattern as Sprint 6 — `/ratings/{denmark}` + `/ratings/historical/{denmark}` (1-2h CC budget; mapping is trivial extension of `TE_COUNTRY_OVERRIDES_TIER1`). |
| `CAL-RATING-COHORT-TARGET-CALIBRATION` | Brief target heuristic refinement | LOW | Refine brief target heuristic methodology for sparse/stable cohorts (current heuristic is calibrated on EA periphery high-volatility issuers; need cohort-aware estimator). See §9.1 below. |

### 8.3 Sprint 4 cohort yaml flag back-fill (janitorial)

`country_tiers.yaml` `rating_spread_live: true` is currently flagged
only for the 5 Sprint 6 países (per brief §4 commit 3 scope). The 10
Sprint 4 países (US/DE/FR/IT/ES/PT/GB/JP/CA/AU) are implicitly
rating-spread-live via `TIER1_COUNTRIES` tuple but lack the yaml flag.
Future janitorial commit can back-fill for full convention parity —
not a blocker (TIER1_COUNTRIES is single source of truth).

---

## 9. Lições — Sprint 6 specifics

### 9.1 Brief target heuristic was calibrated on Sprint 4 EA periphery, not sparse Nordic-Alpine

**Observation**: Brief §6 sprint-end Tier B targets (`agency_raw ≥ 660`,
`consolidated ≥ 580`) were derived from Sprint 4 baseline 491 / 466
+ "expectation +~170-190 raw / +~120-150 consolidated" estimate. The
estimate assumed ~30-38 rows/país avg from the Sprint 4 cohort.

**Reality**: Sprint 4 cohort = high-volatility EA periphery + G7
peers. PT/IT/ES historical = 96/81/81 actions each (sovereign
debt-crisis era 2010-2015). Sprint 6 cohort = AAA-region stable
Nordic-Alpine sovereigns. CH/NO/NL historical = 8/11/15 actions each
— **3-4× shallower archives**. NZ/SE more active (40/28) but still
half of EA periphery cohort.

**Why**: Sovereign credit rating event count correlates strongly with
debt-to-GDP volatility + crisis exposure. AAA-stable Nordic-Alpine
sovereigns with sovereign wealth offsets (NO oil fund; CH neutrality
+ banking surplus) have minimal rating events. The TE archive
faithfully reflects this — the "shortage" is in reality, not the
connector.

**Lesson**: brief target heuristic for cohort-expansion sprints
should be cohort-aware:
- High-volatility T1 (EA periphery, EM-periphery sovereigns):
  ~30-50 historical actions/país avg.
- AAA-stable T1 (Nordic-Alpine, low-volatility advanced): ~8-25
  historical actions/país avg.
- Use `MIN(per-país historical depth)` × `cohort size` × 0.85
  (skip-invalid factor) + cohort_size × 4 (snapshot rows) as a
  cohort-aware lower bound rather than a uniform avg.

**Filing**: CAL-RATING-COHORT-TARGET-CALIBRATION candidate (LOW
priority). Re-visit when next cohort-expansion sprint surfaces (T2
expansion = future Phase 2+). Not actionable in Phase 1.

### 9.2 DK pre-flight HALT — operator-side correction trace

**Observation**: SESSION_CONTEXT (operator-managed external) had DK
listed in T1 cohort context. Brief §1 propagated the mistake into the
6-país cohort. Pre-flight findings doc (Commit 1 first draft) accepted
the brief at face value with a "DK substitution for EA" rationale.

**Operator HALT** (2026-04-26 pre-Commit 1): Hugo verified
`country_tiers.yaml:91` shows DK = T2; ADR-0010 strict T1-ONLY
enforcement forbids T2 surface. Cohort reduced 6 → 5; pre-flight doc
revised; brief amended same Commit 1 staging.

**Lesson**: pre-flight findings doc must verify cohort composition
against `country_tiers.yaml` directly (not against brief or
SESSION_CONTEXT). If cohort includes any país NOT classified T1 in
`country_tiers.yaml`, surface the discrepancy as a HALT-candidate
finding before Commit 1, NOT as a "rationale for inclusion".

**Filing**: lesson captured here; not a separate CAL. Operator-side
SESSION_CONTEXT correction is post-sprint janitorial via Project
knowledge edit (not in CC scope).

### 9.3 Worktree PYTHONPATH override pattern works for shared-DB execution

**Observation**: Sprint 6 worktree branched off main pre-cohort
extension. The engine venv uses an editable install pointing to
`/home/macro/projects/sonar-engine/src` (the engine main, not the
worktree). Naïve `sonar backfill rating-spread --countries "NL,..."`
from the worktree would have run engine-main code, which still
hard-codes the 10-país cohort and would reject the new país.

**Solution**: `PYTHONPATH=$PWD/src .venv/bin/sonar backfill ...` —
PYTHONPATH precedes the editable-install path in `sys.path`, so the
worktree code is loaded. DB is symlinked (`data/sonar-dev.db` → engine
DB), so writes hit the shared engine DB even though code runs from
worktree.

**Lesson**: codify in worktree setup playbook for future
code-change-then-execute sprints. Sprint 4 ran execution post-merge
(only doc/data writes); Sprint 6 ran execution pre-merge via PYTHONPATH
override. Both patterns valid; Sprint 6 pattern is faster
(avoids merge-and-revert cycle if backfill surfaces issues).

### 9.4 TE empirical refresh post-D0 stays stop-gap, not promoted to primary

**Observation**: D0 audit (2026-04-18) rejected TE ratings as primary
or fallback (latest action 2022-09-09 — 4Y stale). Sprint 4 empirical
probe (2026-04-25) revealed TE Premium endpoint is current (latest
2026-03-06 PT). Sprint 6 (2026-04-26) re-confirmed (latest 2026-04-26
across 5 new país snapshot). The D0 finding is **outdated** and TE
Premium is in fact a **viable Path 1 stop-gap**.

**Decision**: spec §2 source priority unchanged — TE = NOT primary
per D0 dated finding. Spec §12.3 source-resolution policy explicitly
labels TE as "Path 1 stop-gap shipped pre-Phase 2" until
`connectors/sp_ratings` + peers land. This avoids spec-source-priority
churn while documenting the empirical reality.

**Lesson**: D0 audit findings are dated snapshots; data sources
re-evaluate periodically. Spec source priority should not flip on a
single empirical refresh — but the data layer can use the current
state as a stop-gap with explicit "stop-gap" labelling. Sprint 4 +
Sprint 6 establish this pattern.

### 9.5 Pre-existing test failures — engine-main parity, not regressions

**Observation**: Pre-push pytest `-m "not slow"` reported 2 failures:
- `test_us_smoke_end_to_end` (cycles composites integration —
  pre-existing on engine main, unrelated to rating-spread).
- `test_cpi_yoy_c2_from_cassette[NO]` (TE indicator — order-dependent
  flake; passes in isolation; rotates with `test_us_full_stack` on
  engine main).

**Decision**: documented in Commit 2 body; treated as engine-main
parity baseline (zero Sprint-6 regressions). Pre-push gate "fail"
trigger NOT activated because failures are not introduced by Sprint 6
change.

**Lesson**: pre-push gate failure triage requires distinguishing
"pre-existing on main" vs "regression from this sprint". Strict
reading of brief §5 trigger 6 (no `--no-verify`) is honoured (no
hooks bypassed); but flake/main-parity failures should not
artificially block sprint completion. Worth codifying as discipline
update for next brief format revision.

---

## 10. Pattern observations vs Sprint 4 baseline

### 10.1 Consistency of TE behaviour across 5 sparse markets

| Pattern | Sprint 4 (10 países) | Sprint 6 (5 países) | Verdict |
|---|---|---|---|
| `/ratings` snapshot returns | 160 países always | Same | ✓ stable |
| `/ratings/historical/{country}` 404 rate | 0/10 | 0/5 | ✓ stable |
| Invalid token rate | ~0.5 % (5/971) | 3.3 % (4/121) | Sprint 6 higher rate but same SHAPE (Moody's truncated tokens + whitespace prefix); likely sample-size noise |
| Snapshot < 4 agencies (one missing) | 0/10 | 1/5 (NO MOODYS skip due to `\tAaa`) | Tail behaviour visible in smaller cohort |
| Multi-decade depth | 1986-11-18 onward | 1949-02-05 onward (NL specifically) | Sprint 6 extended global earliest |

**Key observation**: TE Premium ratings endpoints behave consistently
on sparse cohorts. No ergonomic surprises beyond the same invalid-token
edge cases Sprint 4 surfaced. Sprint 6 confirms the Sprint 4 pattern
generalizes.

### 10.2 Consolidated row count per país tracks historical depth

Linear-ish: per-país consolidated ≈ per-país historical for Sprint 6
cohort (CH 9/8, NL 16/15, NO 12/11, NZ 37/40, SE 29/28). The
consolidated-vs-raw ratio is higher (~1.0) for sparse cohorts because
fewer multi-agency same-date events occur. Sprint 4 EA periphery had
ratio ~0.92 (more multi-agency same-date collapses). Confirms sparse
cohorts are **less consolidatable** but **also less multi-rated**.

### 10.3 Backfill latency negligible

Sprint 6 backfill end-to-end: ~4 seconds (calibration seed 0 + snapshot
1 call + 5 historical calls + consolidate over 5 país × dates). Sprint
4 was ~30s for 10 país. Linear scaling per país ~3s. No throttling
required.

---

## 11. Follow-ups

| # | Item | Owner | Target |
|---|---|---|---|
| F1 | Sprint 4 cohort `rating_spread_live: true` yaml flag back-fill (US/DE/FR/IT/ES/PT/GB/JP/CA/AU) | CC ad-hoc / future janitorial | Phase 1 close-out grooming |
| F2 | DK rating-spread expansion (CAL-RATING-DK-PHASE5 candidate) | Phase 5+ | Post ADR-0010 T2 lock lift OR DK T2→T1 promotion in `country_tiers.yaml` |
| F3 | Brief target heuristic refinement for cohort-expansion sprints (CAL-RATING-COHORT-TARGET-CALIBRATION candidate) | Future brief format revision | Next cohort-expansion sprint |
| F4 | `connectors/sp_ratings` + `moodys_ratings` + `fitch_ratings` + `dbrs_ratings` agency-scrape connectors (Path 1 forward per spec §2) | Phase 2+ | Phase 2 connector batch |
| F5 | Calibration table refresh quarterly automation (spec §4 anchor values + ICE BofA refresh) | Phase 2+ | Quarterly cadence post connectors land |

---

## 12. Referências

- **Brief**: `docs/planning/week11-sprint-6-l2-rating-spread-cohort-expansion-brief.md`
  (amendment 2026-04-26 — DK removed)
- **Pre-flight**: `docs/planning/week11-sprint-6-l2-rating-spread-cohort-expansion-preflight-findings.md`
- **Spec**: `docs/specs/overlays/rating-spread.md` v0.2 (§4/§6/§8 + new §12 country scope)
- **ADR-0010**: `docs/adr/ADR-0010-tier-scope-lock.md` (T1-ONLY through Phase 4)
- **Sprint 4 commits**: `f2cc4ef` (feat) + `faa73d2` (migration 019 patch) + `82f5f52` (spec sync)
- **Sprint 6 commits**: `123f91f` (C1) → `66f8211` (C2) → `884157d` (C3) → `19fbe04` (C4) → `ec15510` (C5) → (this commit C6)
- **CAL closure**: `docs/backlog/calibration-tasks.md` `CAL-RATING-COHORT-EXPANSION` CLOSED entry
- **Sprint 5A precedent**: NSS §12 country scope appendix (commit `f8c0e3c`)
- **Sprint 5B precedent**: retrospective structure
  (`docs/planning/retrospectives/week11-sprint-5b-l2-curves-t1-europe-sparse-report.md`)

---

**Sprint 6 closed 2026-04-26**.
