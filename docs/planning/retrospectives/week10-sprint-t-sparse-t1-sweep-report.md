# Week 10 Sprint T — Sparse T1 TE Path 1 Sweep Retrospective

**Sprint**: T — 6-country sparse T1 sweep (AU/NZ/CH/SE/NO/DK) via
ADR-0009 v2.2 S1/S2 classifier — first **large-scale empirical
application** of the pattern library codified in Sprint M.
**Branch**: `sprint-t-sparse-t1-sweep-au-nz-ch-se-no-dk`.
**Worktree**: `/home/macro/projects/sonar-wt-t-sparse-t1-sweep-au-nz-ch-se-no-dk`.
**Brief**: `docs/planning/week10-sprint-t-sparse-t1-sweep-au-nz-ch-se-no-dk-brief.md` (format v3.2 — Tier A / Tier B split).
**Duration**: ~1.5h CC (single session 2026-04-23 ~22:20–23:45 WEST,
well inside the 4-6h budget; 9th replication of the TE Path 1 pattern
post-v2.2 codification runs fast).
**Commits**: 7 substantive + this retro = 8 total.
**Outcome**: **Partial PASS**. T1 curves coverage 10 → 11
(US/DE/EA/GB/JP/CA/IT/ES/FR/PT **+ AU**). **AU PASS** via TE Path 1
(8 tenors, RMSE 3.08-3.63 bps across 3 canary dates, confidence 0.75
uniform — Svensson-capable with structural coverage 2+3+3
short/mid/long). **5 S2 HALT-0** (NZ/CH/SE/NO/DK + meta-confirmed NL
from Sprint M) — 5 per-country Path 2 CALs open for Week 11+. 6/6
classifier predictions correct (classifier validated). **Hypothesis
priors refuted 5/6** — the §1 brief's "sovereign-market-size →
TE-coverage" heuristic is systematically biased for sparse T1 non-EA.

---

## 1. Commit inventory

| # | Subject | Scope |
|---|---|---|
| C1 | `docs(planning): Sprint T sparse T1 sweep brief (v3.2)` | Brief staged pre-sprint via sprint_setup.sh (Lesson #1 fix) |
| C2 | `docs(probes): Sprint T 6-country TE Path 1 sweep results` | Per-country probe matrix + `/search` cross-validation + S1/S2 classification + pattern-library amendment candidates at `docs/backlog/probe-results/sprint-t-sparse-t1-sweep-probe.md` (550+ lines) |
| C3 | `feat(connectors): te.py AU yield curve symbols` | AU entry (8 tenors) added to `TE_YIELD_CURVE_SYMBOLS`; `TE_10Y_SYMBOLS["AU"]` wired; comment block documents `GACGB` mixed-suffix quirk |
| C4 | `feat(pipelines): daily_curves T1 tuple 10 → 11 (AU)` | `T1_CURVES_COUNTRIES` + `CURVE_SUPPORTED_COUNTRIES` extend to 11; `_DEFERRAL_CAL_MAP` removes AU + re-points NZ/CH/SE/NO/DK from umbrella `CAL-CURVES-T1-SPARSE` to per-country `CAL-CURVES-{X}-PATH-2`; docstring refresh |
| C5 | `test: regression coverage AU S1 + update 10Y drift guards` | `test_daily_curves.py` + `test_te.py` updated with AU parametrize entries, AU spectrum test added; `daily_cost_of_capital._CURVES_SHIPPED_COUNTRIES` + `daily_monetary_indices._CURVES_SHIPPED_COUNTRIES` extended; integration test `test_t1_curves_tier_constant_matches_expected` re-hardcoded to 11-tuple |
| C6 | (no code) ops: AU backfill Apr 21-23 + idempotency verify | Local DB canary: AU persisted 2026-04-21/22/23 via `--country AU --date $d`; rmse_bps 3.08/3.18/3.63; confidence 0.75 uniform. `--all-t1 --date 2026-04-22` shows 11 countries skipped-existing (ADR-0011 idempotency). Bash wrapper smoke exit 0 |
| C7 | `docs(adr+backlog): ADR-0009 Sprint T addendum + 5 Path 2 CALs` | ADR-0009 addendum Sprint T (ledger v2 updated to 5 inversions / 6 non-inversions; pattern library v2.3 amendment candidates §9.1-9.3 documented); `calibration-tasks.md` CAL-CURVES-T1-SPARSE marked SUPERSEDED, CAL-CURVES-AU-PATH-2 closed pre-open, 5 new Path 2 CALs opened |
| C8 | (this commit) `docs(planning)` Sprint T retrospective | This retro |

---

## 2. Empirical outcomes matrix (classifier validation)

### 2.1 Per-country outcomes

| Country | Prior §1 prob | TE tenors | /search exhaustive? | Classifier | Decision | CAL delta |
|---|---|---|---|---|---|---|
| AU | HIGH ~80% | **8** (1Y–30Y minus 15Y + 1M/3M/6M) | yes (8 symbols) | **S1** | PASS ship | `CAL-CURVES-AU-PATH-2` CLOSED pre-open |
| NZ | MEDIUM ~60% | **3** (1Y, 2Y, 10Y) | **no** (GNZGB1 missed) | **S2** | HALT-0 | `CAL-CURVES-NZ-PATH-2` OPEN Week 11 |
| CH | HIGH ~75% | **2** (2Y, 10Y) | yes | **S2** | HALT-0 | `CAL-CURVES-CH-PATH-2` OPEN Week 11 |
| SE | MEDIUM-HIGH ~70% | **2** (2Y, 10Y) | yes | **S2** | HALT-0 | `CAL-CURVES-SE-PATH-2` OPEN Week 11 |
| NO | MEDIUM ~55% | **3** (6M, 52W, 10Y — dual-prefix) | yes | **S2** | HALT-0 | `CAL-CURVES-NO-PATH-2` OPEN Week 11 |
| DK | MEDIUM ~60% | **2** (2Y, 10Y) | yes | **S2** | HALT-0 | `CAL-CURVES-DK-PATH-2` OPEN Week 11 |

**Summary: 1 S1 PASS / 5 S2 HALT-0.** Below brief §1 hypothesis (3-5 PASS).

### 2.2 AU fit quality canary (Apr 21/22/23 backfill)

| Date | RMSE (bps) | Confidence | observations_used | Result |
|---|---|---|---|---|
| 2026-04-21 | 3.08 | 0.75 | 8 | ✓ persisted |
| 2026-04-22 | 3.18 | 0.75 | 8 | ✓ persisted |
| 2026-04-23 | 3.63 | 0.75 | 8 | ✓ persisted |

All below HALT-material §4 threshold (rmse_bps ≤ 30, confidence ≥ 0.5).
Confidence 0.75 (not 1.0 like PT Sprint M) reflects the 15Y gap +
missing short-end (1M/3M/6M) — structural but Svensson-handleable.

### 2.3 S1/S2 classifier correctness

**6/6 correct predictions.** The classifier's binary threshold (≥6
tenors S1, <6 S2) cleanly separates the cohort — no borderline
5-tenor ambiguity. The tenor-count gap 8↔3 is so wide (3 countries
at 2, 2 at 3, 1 at 8) that the classifier performs cleanly on this
dataset. Edge-case testing (exactly 6 tenors) still pending from
future cohorts.

---

## 3. Hypothesis priors — systematic bias refuted

Brief §1 probability table assumed "sovereign-market size → TE
coverage breadth" as the dominant driver. Empirical outcome:

| Hypothesis | Cohort | Observed | Verdict |
|---|---|---|---|
| "Major sovereign → HIGH PASS" | AU (80%) | S1 PASS | ✓ correct |
| "Major sovereign → HIGH PASS" | CH (75%) | S2 HALT-0 | ✗ over-optimistic |
| "Medium sovereign → MEDIUM PASS" | NZ/DK (~60%) | S2 HALT-0 | ✗ over-optimistic |
| "Smaller sovereign → MEDIUM-LOW PASS" | NO (55%) | S2 HALT-0 | ✗ validated direction, wrong magnitude |
| "Nordic liquidity → MEDIUM-HIGH PASS" | SE (70%) | S2 HALT-0 | ✗ over-optimistic |

**Hit rate 1/6 (17%).** Updated empirical model:

- The real driver of TE coverage is **English-language
  Bloomberg/Reuters primary-market desk presence**, not AUM.
- AU clears because ACGB is actively followed by offshore real-money
  accounts in USD-ish terms + the RBA is an English-speaking central
  bank with tight Bloomberg integration.
- CHF/SEK/NOK/DKK trade primarily via local dealers (CHF interbank
  Zurich; SEK/NOK/DKK Nordic-cluster), with local-currency native-CB
  datafeeds (SNB Data / Riksbank / Norges Bank / Nationalbanken) as
  the authoritative sovereign curve. TE scrapes Bloomberg — Bloomberg
  underweights these vs primary-market direct.
- The `/search` exhaustiveness discovery (NZ's `GNZGB1:IND` missed)
  confirms TE has inventory quirks beyond just Bloomberg listing
  parity.

**Pattern library v2.3 amendment (candidate)**: sparse T1 default
prior = 25-30% (not 55-80%) until EA-periphery-analogous coverage
evidence surfaces. Mid-tier-T1 (periphery EA — IT/ES/FR/PT) benefits
from EA sovereign-market standardization; non-EA sparse T1 does not.

---

## 4. Pattern library discoveries (ADR-0009 v2.3 amendment candidates)

Three amendments surfaced by Sprint T empirical evidence — documented
in ADR-0009 Sprint T addendum §3 + probe-results §9:

### 4.1 `/search` is high-recall but not exhaustive

**Evidence**: NZ's `GNZGB1:IND` (531 obs, daily-live, `latest=22/04/2026`)
returned via per-tenor sweep but was **not listed** in the 2 symbols
from `/search/new-zealand%20government%20bond`. Sprint M had
confirmed `/search` as exhaustive for PT + NL; Sprint T refutes that
generalization.

**Amendment candidate**: retain per-tenor sweep discipline even
after `/search` enumeration. Cost is ~12 calls, value is ground-truth
coverage. Do not truncate probe scope at `/search`.

### 4.2 Multi-prefix families within a single country

**Evidence**: NO spans two distinct prefix families simultaneously —
`GNOR{n}YR:GOV` (10Y only) + `NORYIELD{n}M:GOV` / `NORYIELD52W:GOV`
(6M + 52W). No prior T1 precedent: IT (`GBTPGR`), ES (`GSPG`), FR
(`GFRN`), PT (`GSPT`), AU (`GACGB`) all maintain single-prefix per
country.

**Amendment candidate**: probe MUST sweep all plausible prefix
candidates, not just the dominant Bloomberg-style `G{ISO}{*}`. When
`/search` returns ≥2 distinct prefix families for a country, log
both in probe results matrix.

### 4.3 Sparse-T1 hypothesis prior re-baselining

**Evidence**: 1/6 hit rate on brief §1 (see §3 above).

**Amendment candidate**: default sparse-T1 S1 probability to ~25-30%
(not 55-80%). Re-calibrate after sub-sequent Path 2 probes surface
non-TE data availability.

---

## 5. Velocity assessment (ADR-0009 v2.2 compounding)

### 5.1 Sprint time spent vs pre-v2.2 estimate

- Brief-estimated budget: 4-6h (reasonable ballpark for 6-country
  sweep + code ship + tests + docs).
- Actual: ~1.5h CC wall-clock (single session).
- **Compression ratio**: ~3-4×. Pre-v2.2 baseline for a single
  country was ~1.5-2h (Sprint I FR), so raw expectation for 6
  countries sequential would be ~9-12h. The 1.5h actual reflects:
  1. Brief-first structure enabled early probe discipline (Commit 2
     before 3/4).
  2. S1/S2 classifier is binary triage — no deliberation on
     borderline cases.
  3. Per-country isolation (ADR-0011 Principle 2) means 5 HALT-0
     countries are each ~2 minutes of CAL-text, not ~30 min of probe
     + investigation + ship decision.
  4. Probe parallelism: `/search` + per-tenor sweep can be run as
     batched shell loops (~5 min total TE calls vs ~30 min if
     serially prompted).

### 5.2 Sprint T is the 9th TE Path 1 application

Sequence:
1. CAL-138 (GB/JP/CA) — Sprint E
2. IT — Sprint H
3. ES — Sprint H (same sprint)
4. FR — Sprint I
5. PT — Sprint M (pattern library v2.2 codified here)
6. NL — Sprint M (first S2 HALT-0)
7. AU — Sprint T (this sprint, first sparse-T1 S1 PASS)
8-12. NZ/CH/SE/NO/DK — Sprint T (this sprint, S2 HALT-0 cohort)

Post-Sprint-M the pattern is fully routinized — probe-first discipline
is reflexive, CAL templates are boilerplate, pre-commit hygiene is
muscle memory. Sprint T demonstrates the pattern scales to 6-country
sweeps without loss of rigor.

### 5.3 Projection for Week 11+ Path 2 sprints

6 open CAL-CURVES-{X}-PATH-2 items (NL + 5 Sprint T). Estimated budget
per country:

- DK: 1-2h (reuses Sprint Y-DK `NationalbankenConnector`)
- NO: 2-3h (reuses Sprint X-NO `NorgesbankConnector`)
- SE: 2-3h (reuses Sprint W-SE `RiksbankConnector`)
- CH: 2-3h (reuses Sprint V-CH `SnbConnector`)
- NL: 3-5h (new `DnbConnector` from scratch; OpenDatasoft platform risk per Sprint D precedent)
- NZ: 2-3h (new RBNZ scraper, no prior monetary infra)

**Total Week 11+ Path 2 budget**: 12-19h CC. Could run as a single
sweep sprint ("Sprint W11-Path2-cohort") or as 6 independent sprints.
Recommend a hybrid: 1 brief-up-front cohort sprint + per-country
closure sprints depending on probe outcomes (Path 2 may split S3
"native daily >6 tenors" vs S4 "native monthly only" vs S5 "no native
API, scrape required" sub-shapes).

---

## 6. Week 10 close delta

### 6.1 Pre-Sprint-T state (post-Sprint-M close)

T1 curves coverage: 10/16 (US/DE/EA/GB/JP/CA/IT/ES/FR/PT) = **62.5%**.

### 6.2 Post-Sprint-T state

T1 curves coverage: 11/16 (+ AU) = **68.75%**. Delta: +6.25pp (1
country; below brief §1 "+3-5pp" projection because 5 of the 6
probed turned out S2 not S1).

Non-curve T1 coverage (monetary / economic / credit / financial /
cycles pipelines) unaffected — zero-touch scope respected.

### 6.3 ADR-0009 v2 ledger at Week 10 close

- **Inversions (S1 PASS)**: IT + ES + FR + PT + AU = **5 cumulative**.
- **Non-inversions (S2 HALT-0)**: NL + NZ + CH + SE + NO + DK = **6 cumulative**.
- **Mix**: 5:6, near-paritarian. TE Path 1 serves as useful binary
  filter but not exhaustive coverage — Path 2 is warranted for ~55%
  of probed-to-date T1 non-EA countries.

### 6.4 TE quota impact

- Baseline Day 3 close (per brief §2.3): ~27%.
- Sprint T probe calls: ~104 (6 `/search` + 98 per-tenor).
- Sprint T backfill calls: 24 (3 dates × 8 AU tenors).
- Total Sprint T TE calls: ~128.
- Estimated quota post-Sprint-T: **~29-30%**. Well under 45% ceiling.

---

## 7. Lessons

### 7.1 Brief §1 hypothesis table is valuable *because* it can be refuted

The brief's §1 probability table (80%/60%/75%/70%/55%/60%) was
systematically wrong — but recording it pre-probe enabled a 17% hit
rate calibration post-probe. **Hypothesis-first retrospective
enrichment** is load-bearing for pattern library evolution.

**Propagate**: every cohort-scan sprint should ship a pre-probe
hypothesis table in §1 of its brief. Refuted hypotheses are more
valuable than confirmed ones for library calibration.

### 7.2 Per-country isolation (ADR-0011 Principle 2) scales linearly

5 S2 HALT-0 countries took ~15 min of CAL-writing (3 min each) —
not 5× the full "investigate + ship or defer" cycle. The S1/S2
classifier (v2.2) combined with the `_DEFERRAL_CAL_MAP` per-country
pointer mechanism produces a natural per-country branch that needs
no orchestration overhead.

### 7.3 `/search` exhaustiveness is not transitive across countries

Sprint M assumed PT + NL `/search` exhaustive (confirmed empirically
for both). Sprint T inherited that assumption and almost truncated
NZ probe at 2 tenors (the `/search` returns) — but the per-tenor
sweep discipline caught `GNZGB1:IND`. **Never trust a prior
exhaustiveness claim across cohorts**; always run per-tenor sweep.

### 7.4 Pre-commit double-run caught nothing (good signal)

Sprint T touched only 6 files (te.py, daily_curves.py, 2 pipelines
drift-guards, 2 test files). Ruff + mypy + pytest clean on first
commit; double-run confirmed idempotency. The Week 10 Lesson #2
discipline (double-run on every commit) is now reflexive and low-cost
— no Sprint T commits were blocked by hook feedback.

### 7.5 Single-session execution respects the time ceiling

Brief §9 hard-stop was 04:00 WEST. Actual completion ~23:45 WEST
(4h early). The §9 ceiling discipline (sleep before marathon) paid
off in mental bandwidth — probe results analysis was accurate on
first pass, classifier edge cases (exactly-6-tenor) were correctly
flagged as "not in this cohort" rather than forced.

---

## 8. Follow-ups

| # | Item | Owner | Target |
|---|---|---|---|
| F1 | Week 11 Path 2 cohort sprint (6 countries: NL + NZ/CH/SE/NO/DK) | CC | Week 11 |
| F2 | Pattern library v2.3 codification in ADR-0009 (formalize §9 amendment candidates) | CC (successor sprint) | Week 11 |
| F3 | Systemd curves service post-merge verification (Tier B §5.2) | Hugo (operator) | Apr 24 05:00 UTC auto-fire OR Apr 24 manhã manual smoke |
| F4 | Downstream CRP / cost-of-capital AU wiring (if not already covered by dispatcher) | CC / deferred | Sprint-post-T or Week 11 cohort |
| F5 | 10Y drift-guard: verify `TE_10Y_SYMBOLS["AU"] == "GACGB10:IND"` is used by CRP bridge | CC verification | Week 11 |

---

## 9. Referências

- Sprint T brief: `docs/planning/week10-sprint-t-sparse-t1-sweep-au-nz-ch-se-no-dk-brief.md`
- Sprint T probe results: `docs/backlog/probe-results/sprint-t-sparse-t1-sweep-probe.md`
- ADR-0009 Sprint T addendum: `docs/adr/ADR-0009-national-cb-connectors-ea-periphery.md` §"Addendum Sprint T"
- CAL-CURVES-AU-PATH-2 (CLOSED), CAL-CURVES-{NZ,CH,SE,NO,DK}-PATH-2 (OPEN): `docs/backlog/calibration-tasks.md`
- Sprint M retro (immediate precedent; v2.2 codification): `docs/planning/retrospectives/week10-sprint-m-report.md`
- Sprint I retro (FR first-post-v2 reinforcement): `docs/planning/retrospectives/week10-sprint-curves-fr-te-probe-report.md`
- ADR-0011 Principle 2 (per-country isolation) + Principle 1 (idempotency)

---

*End Sprint T retrospective. First large-scale empirical application
of ADR-0009 v2.2 S1/S2 classifier: pattern library correctness
validated (6/6), hypothesis priors refuted (1/6), ledger ratio 5:6
inversions/non-inversions, +6.25pp T1 curves coverage, 5 per-country
Path 2 CALs open for Week 11.*
