# Sprint 9A — EXPINF T1 audit (CAL-EXPINF-T1-AUDIT)

**Tier scope**: T1 ONLY per ADR-0010 (audit scope; no expansion in this track).
**Pattern reference**: Sprint A precedente (test-hygiene audit-then-fix; same discipline).
**Empirical context**: SESSION_CONTEXT documented 4/16 EXPINF live; reality post-Sprint-8 is **10/16 in `exp_inflation_canonical`**. Audit closes documentation drift.

---

## 1. Scope

**In**:
- Audit complete state of EXPINF tables (`exp_inflation_bei`, `exp_inflation_swap`, `exp_inflation_derived`, `exp_inflation_survey`, `exp_inflation_canonical`) per país T1 (16 países)
- Document active method (BEI/SWAP/DERIVED/SURVEY/MISSING) per país per spec §3 hierarchy
- Document spec §3 deviation patterns (Hugo's empirical finding: spec says BEI for DE/FR/IT/ES but reality is SURVEY-based)
- Document missing países (AU/NL/NZ/CH/SE/NO genuine gaps)
- Update `docs/specs/overlays/expected-inflation.md` country scope appendix (§10 if exists; else add)
- Close CAL-EXPINF-T1-AUDIT with full state matrix
- Update SESSION_STATE.md per WORKFLOW.md mandate
- File new CALs surfaced during audit (e.g. CAL-EXPINF-DE-FR-IT-ES-BEI-NATIVE if BEI implementation gap is genuine)

**Out**:
- BEI implementation upgrade DE/FR/IT/ES (Sprint 9B scope, paralelo worktree)
- Probe missing países AU/NL/NZ/CH/SE/NO (Sprint 9C scope, paralelo within 9BC worktree)
- Connector creation/upgrade (boe_dmp, boj_tankan, etc — separate sprints)
- Calibration refresh / methodology version bump

---

## 2. Spec reference + pre-flight

**Authoritative**:
- `docs/specs/overlays/expected-inflation.md` (§2 inputs + §3 paths + §4 algorithm + §6 edge cases)
- `docs/backlog/calibration-tasks.md` `CAL-EXPINF-T1-AUDIT` (this sprint closes it)
- `src/sonar/overlays/expected_inflation/` modules (`bei.py`, `swap.py`, `derived.py`, `canonical.py`, `backfill.py`)
- DB tables: `exp_inflation_{bei,swap,derived,survey,canonical}` schemas + row counts
- Sprint 8 retro reference (precedent: audit-then-fix Track 1 pattern)

**Pre-flight HALT #0 requirement** (mandatory Commit 1):

CC reads end-to-end + executes empirical baseline:

1. spec §3 paths table verbatim (lines 16-46)
2. Each module source (bei.py / swap.py / derived.py / canonical.py / backfill.py)
3. Empirical SQL queries:
```sql
   SELECT 'bei' tbl, country_code, COUNT(*) n, MIN(date) min_dt, MAX(date) max_dt FROM exp_inflation_bei GROUP BY country_code;
   -- same for swap/derived/survey/canonical
```
4. Identify discrepancies: spec §3 method ≠ reality method per país
5. Identify true missing países (zero rows in any table)

**No TE quota burn** (audit only; SQL + source reads).

---

## 3. Concurrency

**Single CC** in worktree `sonar-wt-9a-expinf-audit`. Paralelo to Sprint 9BC worktree (different module no overlap risk).

**File-level isolation vs 9BC**:
- 9A writes only: `docs/planning/retrospectives/`, `docs/specs/overlays/expected-inflation.md` (§10 country scope appendix), `docs/backlog/calibration-tasks.md` (CAL closure + new CAL filings), `docs/SESSION_STATE.md`
- 9A does NOT edit: `src/sonar/overlays/expected_inflation/*.py` (9BC scope)

**Migration numbers**: NONE.

---

## 4. Commits

Target ~4-5 commits:

1. **Pre-flight audit** — module reads + spec reads + SQL empirical baseline matrix per país per path
2. **Country scope matrix doc** — `docs/planning/sprint-9a-expinf-audit-matrix.md` (full table 16 países × 5 paths + spec compliance per país)
3. **Spec country scope §** — `docs/specs/overlays/expected-inflation.md` country scope appendix update (cohort 16 países documented vs spec §3 path table)
4. **CAL closure + new filings** — `docs/backlog/calibration-tasks.md`:
   - Close CAL-EXPINF-T1-AUDIT with full audit findings + reference to matrix doc
   - File new CAL(s) surfaced: candidates per audit (likely `CAL-EXPINF-EA-PERIPHERY-BEI-NATIVE` for DE/FR/IT/ES BEI upgrade gap; `CAL-EXPINF-MISSING-PROBE` for AU/NL/NZ/CH/SE/NO if 9C doesn't ship them)
5. **Sprint 9A retrospective + SESSION_STATE.md update** — combined commit covering retro path + state file

---

## 5. HALT triggers (atomic)

0. **Pre-flight HALT #0 fail** — module source unrecognisable / SQL queries error → HALT, document
1. **Schema mismatch** — table names diverge from `exp_inflation_*` convention → HALT, surface
2. **Audit reveals data corruption** (NULL canonical rows, broken FK refs) → HALT, escalate to data-integrity sprint
3. **Coverage regression > 3pp** in tests → HALT
4. **Pre-push gate fail** → fix, no `--no-verify`

---

## 6. Acceptance

- [ ] Country scope matrix shipped (16 países × 5 paths per spec §3)
- [ ] Spec deviation patterns documented (DE/FR/IT/ES BEI vs SURVEY actuality)
- [ ] Missing países confirmed (AU/NL/NZ/CH/SE/NO — empirically zero rows in any table)
- [ ] CAL-EXPINF-T1-AUDIT closed with audit findings
- [ ] New CALs filed for follow-up work surfaced
- [ ] Spec §10 country scope appendix updated
- [ ] SESSION_STATE.md updated (EXPINF section: 10/16 confirmed in canonical, missing 6, audit complete)
- [ ] Sprint 9A retrospective shipped
- [ ] No `--no-verify`
- [ ] Pre-commit 2x every commit
- [ ] Pre-push gate green every push

---

## 7. Report-back artifact

Path: `docs/planning/retrospectives/week11-sprint-9a-expinf-t1-audit-report.md`

Structure:
- Sprint metadata (CC duration, commits, audit scope)
- Audit matrix verbatim (16 países × 5 paths)
- Spec compliance per país (canonical method vs actual method)
- Missing países confirmed list
- CAL closures + filings
- Recommendations Sprint 9B/9C scope (or follow-up sprints)

---

## 8. Notes on implementation

- Audit is **read-only** — no modifications to `src/sonar/overlays/expected_inflation/*.py`
- Matrix output format: markdown table 16 países × {BEI rows, SWAP rows, DERIVED rows, SURVEY rows, CANONICAL rows, spec §3 method, actual method, deviation note}
- Sustainable pacing: target ~1.5-2h wall-clock single CC
- Paralelo with 9BC worktree active — no file conflicts (read-only docs vs source edits)
