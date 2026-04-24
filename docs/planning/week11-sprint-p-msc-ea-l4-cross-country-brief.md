# Sprint P — MSC EA L4 First Cross-Country Composite

**Branch**: `sprint-p-msc-ea-l4-cross-country`
**Worktree**: `/home/macro/projects/sonar-wt-p-msc-ea-l4-cross-country`
**Data**: Week 11 Day 1 — target arranque ~14:30 WEST
**Operator**: Hugo Condesa + CC
**Budget**: 3-4h
**Priority**: **P1** — L4 composite first cross-country unlock (post-Q series EXPINF stack operational)
**ADR-0010 tier scope**: T1
**Brief format**: v3.3
**Systemd services affected**: `sonar-daily-cycle-scores.service` (OR new `sonar-daily-msc.service` per audit)
**Parent**: Sprint Q.1.2 shipped (6 countries M3 FULL persist) + Sprint J shipped M4 EA-custom

---

## §1 Scope (why)

### Problem

L4 Monetary State Composite (MSC) currently ships for **US only** (Week 4-5). L4 cross-country expansion blocked until M3 FULL persist for non-US countries. Sprint Q series (Day 1 Week 11) delivered EA M3 FULL persist operational. **Sprint P unlocks MSC EA**.

### Objectivo

Ship MSC EA composite aggregating:
- **M1 EA**: ECB policy rate effective (existing)
- **M2 EA**: Taylor gap EA aggregate (Sprint L shipped)
- **M3 EA**: Anchoring via SPF now FULL persisted (Q.1.2)
- **M4 EA**: FCI EA-custom FULL (Sprint J shipped)

Output: `monetary_cycle_scores` row per date for `country_code='EA'` with composite score + regime classification.

### Expected impact

- L4 coverage: 1/16 (US only) → 2/16 (US + EA) = +6pp L4 layer
- T1 overall: ~68-70% → ~70-72% (+1-2pp)
- **Strategic visibility win**: first cross-country composite proves L4 replication pattern

---

## §2 Spec (what)

### 2.1 Pre-flight audit (MANDATORY)

#### 2.1.1 MSC US reference pattern
```bash
cd /home/macro/projects/sonar-wt-p-msc-ea-l4-cross-country

grep -rn "msc\|monetary_cycle_scores\|compute_msc\|build_msc" src/sonar/indices/monetary/ | head -20
find src/sonar -name "*msc*" -type f | head -5
```

Document existing US MSC builder location, function signature, DB write pattern.

#### 2.1.2 EA aggregate inputs availability per date
```bash
sqlite3 data/sonar-dev.db "
SELECT
  (SELECT COUNT(*) FROM monetary_m1_effective_rates WHERE country_code='EA' AND date='2026-04-23') AS m1_ea,
  (SELECT COUNT(*) FROM monetary_m2_taylor_gaps WHERE country_code='EA' AND date='2026-04-23') AS m2_ea,
  (SELECT COUNT(*) FROM monetary_m4_fci WHERE country_code='EA' AND date='2026-04-23') AS m4_ea;
"
```

Expected: all 4 sub-indices present for EA at 2026-04-23. If any missing, HALT-0 + document gap.

**M3 note**: M3 is builder-only (no persistence table — verified Day 1 Tier B). MSC EA must invoke M3 builder in-flight during composite calc, not query M3 table.

#### 2.1.3 Scope gate — US MSC logic reusable?
Audit US MSC implementation. Key questions:
- Is US MSC a pure function `msc(m1, m2, m3, m4) -> score` (reusable for any country)?
- Or US-specific (hardcoded FRED series, US regime labels)?

If pure → Sprint P = thin EA wrapper (~1h code). If US-specific → Sprint P = refactor + EA adaptation (~2-3h).

### 2.2 Implementation

Based on §2.1 audit:

**Path A (pure function, preferred)**:
```python
# src/sonar/indices/monetary/msc_builder.py (if not exists) OR reuse US module
def build_msc(
    country_code: str,
    observation_date: date,
    session: Session,
) -> MSCOutput | None:
    """Aggregate M1+M2+M3+M4 for country_code into composite MSC score."""
    m1 = _load_m1(country_code, observation_date, session)
    m2 = _load_m2(country_code, observation_date, session)
    m3 = _build_m3_inflight(country_code, observation_date, session)  # no persist table
    m4 = _load_m4(country_code, observation_date, session)

    if any(x is None for x in (m1, m2, m3, m4)):
        return None  # graceful skip if any sub-index missing

    composite_score = _compose_msc_score(m1, m2, m3, m4)
    regime = _classify_regime(composite_score)
    flags = _aggregate_flags(m1, m2, m3, m4)  # propagate SPF_AREA_PROXY etc

    return MSCOutput(country_code, observation_date, composite_score, regime, flags)
```

**Path B (refactor)**: Extract US-specific elements, parameterize, apply to EA. Scope doubles.

### 2.3 Pipeline dispatch

Extend `daily_cycle_scores.py` (or equivalent) to invoke MSC for EA cohort:
```python
targets = ["US", "EA"]  # was ["US"]
for country in targets:
    msc = build_msc(country, observation_date, session)
    if msc:
        persist_msc(msc, session)
```

### 2.4 Flags propagation critical

MSC EA must preserve upstream flags:
- From M3: `SPF_LT_AS_ANCHOR`, `SPF_AREA_PROXY`, `M3_EXPINF_FROM_SURVEY`
- From M4: EA-custom FCI flags (Sprint J)
- Aggregate into MSC-level `msc_flags` field for consumer transparency

### 2.5 Tests

```python
def test_msc_ea_full_composite(test_session, populated_ea_fixtures):
    """Sprint P: EA MSC composite with all 4 sub-indices present."""
    msc = build_msc("EA", date(2026, 4, 23), session)
    assert msc is not None
    assert msc.regime in ("neutral", "accommodative", "restrictive")
    assert "M3_EXPINF_FROM_SURVEY" in msc.flags

def test_msc_ea_graceful_when_m3_missing(test_session, ea_missing_m3):
    """Sprint P: graceful None when M3 inflight-build fails."""

def test_msc_us_regression_unchanged(test_session, us_fixtures):
    """Sprint P: US MSC continues to work (backward compat)."""
```

### 2.6 Backfill + verify
```bash
for date in 2026-04-21 2026-04-22 2026-04-23; do
  uv run python -m sonar.pipelines.daily_cycle_scores --country EA --date $date
done

sqlite3 data/sonar-dev.db \
  "SELECT country_code, date, regime FROM monetary_cycle_scores WHERE country_code='EA' ORDER BY date;"
```

---

## §3 Commits plan

| # | Scope | Files |
|---|---|---|
| C1 | docs(backlog): Sprint P pre-flight audit (MSC US pattern + EA input availability) | `docs/backlog/audits/sprint-p-msc-ea-audit.md` |
| C2 | feat(indices): MSC builder extended for EA (Path A) OR refactored for cross-country (Path B) | `src/sonar/indices/monetary/msc_builder.py` OR US module |
| C3 | refactor(pipelines): daily_cycle_scores dispatch extended to EA cohort | `src/sonar/pipelines/daily_cycle_scores.py` |
| C4 | test: MSC EA composite + US regression + graceful missing-inputs | `tests/unit/test_indices/test_msc_builder.py` |
| C5 | docs(planning): Sprint P retrospective + L4 coverage matrix | `docs/planning/retrospectives/week11-sprint-p-msc-ea-l4-cross-country-report.md` |

---

## §4 HALT triggers

**HALT-0**:
- EA M2 or M4 rows missing for 2026-04-23 (§2.1.2 audit empty) — can't compose without inputs
- US MSC builder completely US-hardcoded (Path B scope 2x brief budget) — open `CAL-MSC-REFACTOR-CROSS-COUNTRY` for Week 11+, ship Sprint P only if Path A or quick refactor

**HALT-material**:
- US regression — any US MSC test break = STOP
- M3 in-flight build fails for EA (Q.1.2 regression surface) — STOP + triage
- M4 EA-custom scaffold returns partial data — assess propagation rules

**HALT-scope**:
- Temptation to ship MSC DE/FR/IT/ES → STOP (separate Sprint P.1+ — needs M1 per-member audit first)
- Temptation to extend MSC to L5+ layers → STOP
- Temptation to refactor sub-index builders → STOP

---

## §5 Acceptance

### Tier A
1. Audit doc shipped (MSC US pattern + EA availability confirmed)
2. MSC EA builder logic implemented (Path A or B)
3. Dispatcher extended EA cohort
4. Local CLI: `daily_cycle_scores --country EA --date 2026-04-23` → exit 0, EA row persisted
5. US regression: `daily_cycle_scores --country US --date 2026-04-23` unchanged
6. Regression tests pass
7. Pre-commit clean double-run

### Tier B
1. Systemd `sonar-daily-cycle-scores.service` verify (OR relevant service per audit)
2. DB verify:
   ```bash
   sqlite3 data/sonar-dev.db \
     "SELECT country_code, date, regime FROM monetary_cycle_scores WHERE date='2026-04-23';"
   ```
   Expected: 2 rows (US + EA)
3. MSC EA regime value sanity (should be "neutral" or adjacent — ECB policy moderately accommodative 2026-04)
4. Flags include `M3_EXPINF_FROM_SURVEY` + `SPF_LT_AS_ANCHOR`

---

## §6 Retro scope

- MSC EA composite matrix pre/post
- Path A vs B decision rationale
- L4 coverage: 1/16 → 2/16 (+6pp)
- T1 overall delta
- Next step: MSC DE/FR/IT/ES (Sprint P.1+) pending M1 per-member audit

---

## §7 Execution notes
- Audit-first §2.1 mandatory
- M3 in-flight build (no persist table) — handle correctly
- Flags propagation critical
- Paralelo com Sprint Q.2 — zero file overlap (Q.2 = BoE connector + loader extension, P = MSC aggregator)
- Lesson #20 iteration #5 applied: extend ALL helpers if needed
- Pre-commit double-run (#2), sprint_merge.sh Step 10 (#4), DB symlink (#14), filename #15 compliant

---

## §8 Dependencies & CAL interactions

### Parent sprints
- Sprint Q.1.2 (M3 EA FULL persist operational)
- Sprint J (M4 EA-custom FCI)
- Sprint L (M2 EA Taylor gaps)

### CAL opened (potential)
- `CAL-MSC-REFACTOR-CROSS-COUNTRY` if Path B needed
- `CAL-MSC-DE-FR-IT-ES` for per-member MSC (Sprint P.1+ Week 11 Day 3)
- `CAL-M1-PER-EA-MEMBER` audit (flagged Day 1 Tier B observation)

### Sprints unblocked
- Sprint P.1+ per-country MSC (after M1 audit)
- L5 layer cross-country expansion future

---

## §9 Time budget
Arranque ~14:30 WEST. Hard stop 18:30 WEST (4h).
- Best case 2h: Path A clean, EA inputs present, thin wrapper
- Median 3h: minor quirks flags propagation
- Worst 4h HALT: US MSC fully US-hardcoded → refactor scope, ship partial

---

*End brief. L4 first cross-country. Ship disciplined.*
