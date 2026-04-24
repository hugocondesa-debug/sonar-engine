# Sprint P.1 — MSC GB L4 Expansion

**Branch**: `sprint-p-1-msc-gb-l4-expansion`
**Worktree**: `/home/macro/projects/sonar-wt-p-1-msc-gb-l4-expansion`
**Data**: Week 11 Day 1 — target arranque ~14:20 WEST (paralelo com Q.3)
**Operator**: Hugo + CC
**Budget**: 1-2h
**Priority**: P1 — L4 third country
**Parent**: Sprint P (MSC EA pattern validated Path A) + Sprint Q.2 (GB M3 FULL shipped)

---

## §1 Scope (why)

Sprint P shipped MSC EA Path A (pure function, `MSC_CROSS_COUNTRY_COHORT = ("US", "EA")` constant). Sprint Q.2 promoted GB M3 to FULL via BoE BEI.

**Sprint P.1 objectivo**: extend MSC cohort to GB. Minimal change — constant +1 entry, test extension, verification.

### Expected impact
- L4 coverage: 2/16 → 3/16 (+6pp L4 layer)
- Completes US/EA/GB major developed-economy L4 composite trio

---

## §2 Spec

### 2.1 Pre-flight
```bash
cd /home/macro/projects/sonar-wt-p-1-msc-gb-l4-expansion

# Verify GB M3 FULL persist operational
sqlite3 data/sonar-dev.db \
  "SELECT 'M1' AS layer, COUNT(*) FROM monetary_m1_effective_rates WHERE country_code='GB' AND date='2026-04-23'
   UNION SELECT 'M2', COUNT(*) FROM monetary_m2_taylor_gaps WHERE country_code='GB' AND date='2026-04-23'
   UNION SELECT 'M4', COUNT(*) FROM monetary_m4_fci WHERE country_code='GB' AND date='2026-04-23';"

# M3 inflight via run (no persist table)
uv run python -m sonar.pipelines.daily_monetary_indices --country GB --date 2026-04-23 2>&1 | \
  grep "m3_compute_mode.*country=GB"
# Expected: mode=FULL
```

If M1/M2/M4 GB rows missing at 2026-04-23 → HALT-0, open `CAL-MSC-GB-INPUTS-BACKFILL`.

### 2.2 Implementation

Single change in `src/sonar/pipelines/daily_cycles.py`:
```python
# Before (Sprint P):
MSC_CROSS_COUNTRY_COHORT: tuple[str, ...] = ("US", "EA")

# After (Sprint P.1):
MSC_CROSS_COUNTRY_COHORT: tuple[str, ...] = ("US", "EA", "GB")
```

That's it. `compute_msc` is already pure (Sprint P Path A confirmed) — accepts any country_code, reads country-filtered sub-indices.

### 2.3 Tests

Extend `tests/unit/test_pipelines/test_daily_cycles.py`:
- Constant assertion length update `len == 3`
- MSC GB composite test fixture

Extend `tests/unit/test_cycles/test_monetary_msc.py`:
- `test_msc_gb_composite` — similar to EA test, GB-specific flags (`M3_EXPINF_FROM_BEI` + `BEI_FITTED_IMPLIED`)
- `test_cohort_us_ea_gb_isolation` — each country MSC independent

### 2.4 Backfill + verify

```bash
# Re-run cycles for cohort + dates
for date in 2026-04-21 2026-04-22 2026-04-23; do
  uv run python -m sonar.pipelines.daily_cycles --date $date
done

# Verify GB MSC row
sqlite3 data/sonar-dev.db \
  "SELECT country_code, date, composite_score, regime_6band
   FROM monetary_cycle_scores
   WHERE date='2026-04-23' ORDER BY country_code;"
# Expected: 3 rows (US + EA + GB)
```

---

## §3 Commits plan

3 commits:
1. `refactor(pipelines): MSC cohort extended para GB` — constant + test assertion
2. `test(cycles): MSC GB composite + 3-country cohort isolation`
3. `docs(planning): Sprint P.1 retrospectiva MSC GB L4 expansion`

---

## §4 HALT

**HALT-0**: GB M1/M2/M4 inputs missing → open backfill CAL, ship Sprint P.1 só após inputs present.

**HALT-material**:
- MSC regime classification returns nonsensical value for GB (e.g., all inputs present but score NaN) → triage, may reveal GB-specific builder gap
- US/EA regression → STOP

**HALT-scope**:
- Temptation to extend cohort to DE/FR/IT/ES/PT (per-member MSC) → STOP, separate CAL-MSC-DE-FR-IT-ES (Sprint P.2+ post M1-per-member audit)
- Temptation to refactor `compute_msc` → STOP, pure function works

---

## §5 Acceptance

### Tier A
1. Constant updated `("US", "EA", "GB")`
2. GB MSC row persisted for 2026-04-23
3. Score within plausible range (0-100, regime labeled)
4. GB-specific flags propagated (`M3_EXPINF_FROM_BEI`, `BEI_FITTED_IMPLIED`)
5. US + EA regression unchanged (60+ tests pass)
6. Pre-commit clean double-run

### Tier B
1. Systemd verify — 3 MSC rows persisted
2. `sqlite3 data/sonar-dev.db "SELECT country_code, composite_score FROM monetary_cycle_scores WHERE date='2026-04-23';"` → 3 rows

---

## §6 Time budget

Arranque ~14:20 WEST. Hard stop 16:20 WEST (2h).
- Best 30min: constant change, 2 test cases, backfill clean
- Median 1h: minor quirks (GB-specific flag propagation edge case)
- Worst 2h: GB M4 scaffold returns partial data → document + ship with flag

**Paralelo com Q.3**: zero file overlap. Q.3 toca connectors + writer + classifier cohort. P.1 toca só pipeline dispatch constant + tests L4.

---

## §7 Execution notes

- Sprint P pattern proven (45min budget met) — expect similar velocity
- Pure function `compute_msc` reusable — no builder touch
- Pre-commit double-run (#2), sprint_merge.sh Step 10 (#4), filename (#15)

---

*Minimal brief. Pattern replication. Ship fast.*
