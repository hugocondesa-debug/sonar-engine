# Sprint Q.4b — PT M3 FULL Promotion (Cohort Extension)

**Branch**: `sprint-q-4b-pt-m3-cohort-promotion`
**Worktree**: `/home/macro/projects/sonar-wt-q-4b-pt-m3-cohort-promotion`
**Data**: Week 11 Day 1 — arranque ~17:15 WEST
**Budget**: 20-30min
**Priority**: P1 — free M3 uplift (SPF row já existe)
**Parent**: Sprint Q.1 (PT SPF row populated via AREA_PROXY) + Sprint Q.3 (Lesson #20 #6 graduated)

---

## §1 Scope

PT tem SPF row em `exp_inflation_survey` desde Sprint Q.1 (ECB SPF AREA_PROXY extends EA aggregate to PT). Q.3 retro identificou:
> *"PT promotion is 'free' — SPF row exists, just cohort extension."*

**Gap actual**: `M3_T1_COUNTRIES` constant não inclui PT. Classifier emite `mode=NOT_IMPLEMENTED`.

**Objectivo**: add PT a `M3_T1_COUNTRIES` → M3 resolves FULL via existing SPF cascade. Zero new connector code.

### Expected impact
- M3 runtime: 9/12 → **10/12 FULL** (83%)
- T1 overall: ~75-77% → ~76-78%

---

## §2 Spec

### 2.1 Pre-flight
```bash
cd /home/macro/projects/sonar-wt-q-4b-pt-m3-cohort-promotion

# Verify PT SPF row exists
sqlite3 data/sonar-dev.db \
  "SELECT country_code, survey_name, COUNT(*), MAX(date), flags
   FROM exp_inflation_survey
   WHERE country_code='PT' GROUP BY country_code, survey_name;"
# Expected: ≥1 row with 'SPF_AREA_PROXY' flag

# Verify PT M1/M2/M4 inputs available (for persist downstream)
sqlite3 data/sonar-dev.db \
  "SELECT 'M1', COUNT(*) FROM monetary_m1_effective_rates WHERE country_code='PT' AND date='2026-04-23'
   UNION SELECT 'M2', COUNT(*) FROM monetary_m2_taylor_gaps WHERE country_code='PT' AND date='2026-04-23'
   UNION SELECT 'M4', COUNT(*) FROM monetary_m4_fci WHERE country_code='PT' AND date='2026-04-23';"

# Locate M3_T1_COUNTRIES
grep -rn "M3_T1_COUNTRIES" src/sonar/indices/monetary/ | head -5
```

If PT SPF row missing OR PT M1/M2/M4 inputs missing → HALT-0 (escalate, not a 20min fix).

### 2.2 Implementation

Single change in classifier module (likely `m3_country_policies.py`):
```python
# Before:
M3_T1_COUNTRIES = ("US", "DE", "EA", "GB", "JP", "CA", "IT", "ES", "FR")

# After:
M3_T1_COUNTRIES = ("US", "DE", "EA", "GB", "JP", "CA", "IT", "ES", "FR", "PT")
```

That's it. Classifier cascade via SPF_AREA_PROXY handles PT like IT/ES/FR.

### 2.3 Tests

Extend `tests/unit/test_indices/test_m3_country_policies.py`:
- Length assertion update `len == 10`
- `test_pt_resolves_via_spf_area_proxy` — PT classifier emits FULL with `SPF_AREA_PROXY` + `M3_EXPINF_FROM_SURVEY` flags

### 2.4 Verify
```bash
uv run python -m sonar.pipelines.daily_monetary_indices --country PT --date 2026-04-23 2>&1 | \
  grep "m3_compute_mode.*country=PT"
# Expected: mode=FULL flags include SPF_AREA_PROXY + M3_EXPINF_FROM_SURVEY
```

---

## §3 Commits plan

3 commits:
1. `refactor(indices): M3_T1_COUNTRIES extended para PT via SPF_AREA_PROXY`
2. `test: PT M3 FULL via existing SPF cascade`
3. `docs(planning): Sprint Q.4b retrospectiva — PT promotion free via Q.1 cascade`

---

## §4 HALT

**HALT-0**:
- PT SPF row missing (§2.1 empty) → Sprint Q.1 bug, escalate to audit
- PT M1/M2/M4 missing → open `CAL-MSC-PT-INPUTS-BACKFILL`, can't promote to FULL usefully

**HALT-material**:
- Classifier cohort hardcoded in multiple files → extend all (Lesson #20 #6 pattern)
- Regression any other country → STOP

**HALT-scope**: zero new connector. Zero new writer. Zero new helper. Cohort extension only.

---

## §5 Acceptance Tier A

1. PT in M3_T1_COUNTRIES constant
2. CLI PT `m3_compute_mode=FULL` with SPF_AREA_PROXY + M3_EXPINF_FROM_SURVEY
3. Regression: US/EA/GB/JP/CA/DE/FR/IT/ES unchanged (9 other FULL)
4. Tests pass
5. Pre-commit clean double-run

### Tier B
Systemd verify — **10 FULL / 0 DEGRADED / 2 NOT_IMPLEMENTED** (NL + AU only).

---

## §6 Time budget

Arranque ~17:15 WEST. Hard stop 17:45 WEST (30min).
Best case 15min. Median 20-25min.

**Paralelo com Sprint P.2 GB forwards backfill** — zero file overlap (P.2 = ops script + `yield_curves_forwards` table, Q.4b = classifier constant + M3_T1_COUNTRIES).

---

*Minimal brief. 1-line cohort extension. Ship 20min.*
