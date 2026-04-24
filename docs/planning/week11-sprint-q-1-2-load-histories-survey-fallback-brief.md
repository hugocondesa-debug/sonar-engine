# Sprint Q.1.2 — _load_histories Survey Fallback Extension

**Branch**: `sprint-q-1-2-load-histories-survey-fallback`
**Worktree**: `/home/macro/projects/sonar-wt-q-1-2-load-histories-survey-fallback`
**Data**: Week 11 Day 1 (2026-04-24) — target arranque ~20:30 WEST
**Operator**: Hugo Condesa (reviewer) + CC (executor, full autonomy per SESSION_CONTEXT)
**Budget**: 20-30min CC + 10min operator merge
**Priority**: **P0 urgent** — Sprint Q.1.1 regression: 6 countries persist failure despite classifier FULL emit
**ADR-0010 tier scope**: T1 ONLY
**ADR-0009 v2.2 TE Path 1 probe**: N/A (DB refactor only)
**Brief format**: v3.3
**Systemd services affected**: `sonar-daily-monetary-indices.service` — expected 6 countries M3 persist success post-fix
**Parent**: Sprint Q.1.1 Tier B — classifier emit FULL works, persist fails with `InsufficientInputsError("history series too short for z-score baseline")`

---

## §1 Scope (why)

### Problem statement (diagnosed via Sprint Q.1.1 Tier B triage)

Sprint Q.1.1 shipped `db_backed_builder` survey fallback for `build_m3_inputs_from_db` (commit c277703). Classifier emit promotes EA cohort (EA/DE/FR/IT/ES) to M3 FULL runtime. **But persist step fails** for the exact same 6 countries.

Natural fire output (post-Q.1.1):
```
countries_duplicate=['US', 'GB', 'JP', 'CA', 'NL', 'AU']
countries_failed=['DE', 'EA', 'IT', 'ES', 'FR', 'PT']
n_failed=6
```

Error source identified in `src/sonar/indices/monetary/m3_market_expectations.py:124`:
```python
if len(inputs.nominal_5y5y_history_bps) < 2 or len(inputs.anchor_deviation_abs_history_bps) < 2:
    raise InsufficientInputsError("history series too short for z-score baseline")
```

### Root cause

Sprint Q.1.1 fallback path:
- Extends `build_m3_inputs_from_db` to accept survey row when canonical `IndexValue(EXPINF_CANONICAL)` missing
- **Does NOT** extend `_load_histories` function

`_load_histories` queries **only** `IndexValue` (canonical) table:
```python
expinf_rows = session.query(IndexValue).filter(
    IndexValue.index_code == EXPINF_INDEX_CODE,  # 'EXPINF_CANONICAL'
    ...
).all()
expinf_by_date = {row.date: row for row in expinf_rows}
```

For EA cohort countries (DE/EA/FR/IT/ES):
- Canonical table empty → `expinf_rows = []` → `expinf_by_date = {}`
- Loop iterates `forwards` (2 dates for EA cohort)
- `nominal_hist` populated (2 entries)
- `anchor_hist` skipped at `if expinf_row is None: continue` → **empty list**

Result M3Inputs:
- `nominal_5y5y_history_bps = (n1, n2)` — len 2 ✓
- `anchor_deviation_abs_history_bps = ()` — **len 0 ✗**

Downstream `m3_market_expectations` builder raises `InsufficientInputsError`.

**Q.1.1 canonical path was complete (via IndexValue)**. Q.1.1 survey fallback path is **half-shipped** — new data point recognized, but history reconstruction unchanged.

### Objectivo Sprint Q.1.2

Extend `_load_histories` to reconstruct `anchor_hist` from survey table fallback when canonical table empty for (country, date window).

Expected outcome: 6 EA cohort countries persist M3 successfully. Runtime M3 FULL = 6 countries (US + EA + DE + FR + IT + ES) operational, not just classifier emit.

---

## §2 Spec (what)

### 2.1 Pre-flight audit (MANDATORY)

#### 2.1.1 Confirm root cause via journal

```bash
cd /home/macro/projects/sonar-wt-q-1-2-load-histories-survey-fallback

sudo journalctl -u sonar-daily-monetary-indices.service --since "-60 min" --no-pager | \
  grep -E "InsufficientInputsError|history series too short|country_failed|country=DE" | head -20
```

Document in `docs/backlog/audits/sprint-q-1-2-load-histories-fallback-audit.md` (new):
- Error message captured
- Per-country failure dates
- Confirm hypothesis (anchor_hist empty vs nominal_hist populated)

#### 2.1.2 Current `_load_histories` structure

```bash
sed -n '/^def _load_histories/,/^def /p' \
  src/sonar/indices/monetary/db_backed_builder.py
```

Document:
- Function signature + parameters
- Canonical query pattern (lines)
- Loop structure (`forwards` iteration)
- Return tuple shape

#### 2.1.3 Survey row forward-fill pattern (Q.1.1 reference)

Q.1.1 shipped `_query_survey` with `on-or-before` semantic for single-date lookup. Sprint Q.1.2 extends same pattern to history window — for each forwards date in range, find latest survey row ≤ that date.

Alternative pattern: batch-query all survey rows in window, build sorted list, use pointer traversal per forwards date (more efficient for large windows).

Document chosen pattern + complexity analysis.

### 2.2 `_load_histories` extension

**File**: `src/sonar/indices/monetary/db_backed_builder.py`

Target function: `_load_histories` (line ~377).

Current signature (from Q.1.1 inspection):
```python
def _load_histories(
    session: Session,
    country_code: str,
    *,
    start: date,
    end: date,
    bc_target_bps: float | None,
) -> tuple[list[float], list[float]]:
```

Extension approach (option A — **preferred**, minimal structural change):

```python
def _load_histories(
    session: Session,
    country_code: str,
    *,
    start: date,
    end: date,
    bc_target_bps: float | None,
) -> tuple[list[float], list[float]]:
    """..."""
    forwards = <existing query>

    # Canonical expinf rows
    expinf_rows = <existing IndexValue query>
    expinf_by_date = {row.date: row for row in expinf_rows}

    # NEW Sprint Q.1.2: survey fallback when canonical empty
    survey_rows: list[ExpInflationSurveyRow] = []
    if not expinf_rows:
        survey_rows = (
            session.query(ExpInflationSurveyRow)
            .filter(
                ExpInflationSurveyRow.country_code == country_code,
                ExpInflationSurveyRow.date >= start,
                ExpInflationSurveyRow.date <= end,
            )
            .order_by(ExpInflationSurveyRow.date.asc())
            .all()
        )

    nominal_hist: list[float] = []
    anchor_hist: list[float] = []

    for fwd in forwards:
        forwards_map = _parse_json_dict(fwd.forwards_json)  # existing
        fwd_5y5y = forwards_map.get("5y5y")
        if fwd_5y5y is None:
            continue
        nominal_hist.append(_decimal_to_bps(float(fwd_5y5y)))

        if bc_target_bps is None:
            continue

        # Try canonical first (existing)
        expinf_row = expinf_by_date.get(fwd.date)
        be_5y5y: float | None = None

        if expinf_row is not None:
            expinf_tenors = _expinf_tenors_bps(expinf_row)
            be_5y5y = expinf_tenors.get("5y5y")
        elif survey_rows:
            # NEW: survey forward-fill — find latest survey row ≤ fwd.date
            matched_survey = _latest_survey_on_or_before(survey_rows, fwd.date)
            if matched_survey is not None:
                survey_tenors = _survey_tenors_bps(matched_survey)
                be_5y5y = survey_tenors.get("5y5y")

        if be_5y5y is None:
            continue

        anchor_hist.append(abs(be_5y5y - bc_target_bps))

    return nominal_hist, anchor_hist


def _latest_survey_on_or_before(
    survey_rows: list[ExpInflationSurveyRow],
    target_date: date,
) -> ExpInflationSurveyRow | None:
    """Return the latest survey row with date <= target_date.

    Precondition: survey_rows sorted ascending by date.
    Linear scan acceptable for small N (≤20 quarterly releases in 5Y window).
    """
    matched: ExpInflationSurveyRow | None = None
    for row in survey_rows:
        if row.date <= target_date:
            matched = row
        else:
            break
    return matched
```

### 2.3 Import adjustments

`ExpInflationSurveyRow` already imported at top of module (Q.1.1 shipped). No new imports needed.

`_survey_tenors_bps` already defined in module (Q.1.1 shipped). Reuse.

### 2.4 Regression tests

**File**: `tests/unit/test_indices/test_db_backed_builder.py` (extend existing Q.1.1 tests)

```python
def test_load_histories_canonical_populated_unchanged(test_session, sample_canonical_history):
    """Sprint Q.1.2: canonical path unchanged from Q.1.1 behavior."""
    # Populate IndexValue(EXPINF_CANONICAL) for US 2-year window
    # Populate forwards table
    # Assert _load_histories returns both lists ≥2
    # Assert no survey queries made (canonical path exclusive)

def test_load_histories_survey_fallback_when_canonical_empty(test_session, sample_survey_history):
    """Sprint Q.1.2: survey fallback populates anchor_hist."""
    # Canonical empty
    # Survey table has 3 quarterly rows in window
    # Forwards has 5 daily rows
    # Assert anchor_hist len ≥ 2 (forward-filled from survey)

def test_load_histories_survey_sparse_forward_fill(test_session):
    """Sprint Q.1.2: sparse survey (quarterly) forward-filled across daily forwards."""
    # Survey: 1 row at date D1
    # Forwards: 4 daily rows all > D1
    # Assert all 4 anchor_hist entries use same survey value (forward-filled)

def test_load_histories_no_data_returns_empty(test_session):
    """Sprint Q.1.2: no canonical, no survey → anchor_hist empty (triggers builder error)."""
    # Backward compat: explicit empty case

def test_build_m3_inputs_full_path_survey_fallback_persistable(test_session, mock_ea_setup):
    """Sprint Q.1.2 integration: EA cohort M3Inputs persist successfully via survey path."""
    # Full EA setup: curves 2 days + SPF 3 dates
    # Call build_m3_inputs_from_db
    # Assert M3Inputs fields populated (history arrays ≥ 2)
    # Assert no InsufficientInputsError raised downstream
```

### 2.5 Backfill + verify

Post-code ship:

```bash
# Re-run M3 for 6 EA cohort countries
for date in 2026-04-20 2026-04-21 2026-04-22 2026-04-23; do
  uv run python -m sonar.pipelines.daily_monetary_indices --all-t1 --date $date
done

# Verify persist success
sqlite3 data/sonar-dev.db \
  "SELECT country_code, COUNT(*) FROM monetary_m1_effective_rates WHERE date='2026-04-23' GROUP BY country_code;"

# Verify n_failed=0
uv run python -m sonar.pipelines.daily_monetary_indices --all-t1 --date 2026-04-23 2>&1 | \
  grep "monetary_pipeline.summary"
```

Expected: `countries_failed=[]`, `n_failed=0`, 6 EA cohort persisted.

---

## §3 Commits plan

| Commit | Scope | Ficheiros |
|---|---|---|
| **C1** | docs(backlog): Sprint Q.1.2 audit — _load_histories gap analysis | `docs/backlog/audits/sprint-q-1-2-load-histories-fallback-audit.md` (new) |
| **C2** | fix(indices): _load_histories survey fallback for anchor_hist reconstruction | `src/sonar/indices/monetary/db_backed_builder.py` |
| **C3** | test: regression coverage canonical+survey history paths | `tests/unit/test_indices/test_db_backed_builder.py` (extend) |
| **C4** | docs(planning): Sprint Q.1.2 retrospective + Lesson #20 pattern iteration #5 | `docs/planning/retrospectives/week11-sprint-q-1-2-load-histories-survey-fallback-report.md` |

4 commits clean scope.

---

## §4 HALT triggers

**HALT-0 (structural)**:
- **ExpInflationSurveyRow import fails** (ORM path changed post-Q.1.1) → audit first, fix import
- **`_latest_survey_on_or_before` binary-search needed** for >50 rows → nice-to-have, linear OK for current scope

**HALT-material**:
- **Anchor values nonsensical** (negative abs values OR extreme magnitudes) → data quality check
- **US regression** — any test breaks US path → STOP immediately
- **M4 FCI downstream similar gap discovered** — pattern #6 of Lesson #20 → document but don't scope-creep Q.1.2

**HALT-scope**:
- Temptation to add BEI/swap fallback simultaneously → STOP. Survey only this sprint.
- Temptation to forward-fill canonical-from-survey (canonical writer) → STOP. Separate Week 12+ CAL.
- Temptation to refactor `_load_histories` broader → STOP. Minimum change to close regression.
- Temptation to fix Q.1.1 retro over-claims → defer docs cleanup Week 11 R3.

**HALT-security**: standard.

---

## §5 Acceptance

### Tier A — pre-merge (CC scope, v3.3 compliance)

1. **Audit doc shipped**:
   ```bash
   test -f docs/backlog/audits/sprint-q-1-2-load-histories-fallback-audit.md && \
     wc -l docs/backlog/audits/sprint-q-1-2-load-histories-fallback-audit.md
   ```
   Expected: ≥40 lines.

2. **Fallback logic present**:
   ```bash
   grep "survey_rows\|_latest_survey_on_or_before\|ExpInflationSurveyRow" \
     src/sonar/indices/monetary/db_backed_builder.py | wc -l
   ```
   Expected: ≥4 new references (beyond Q.1.1 baseline).

3. **Local CLI — 6 countries persist success**:
   ```bash
   uv run python -m sonar.pipelines.daily_monetary_indices --all-t1 --date 2026-04-23 2>&1 | \
     grep "monetary_pipeline.summary"
   ```
   Expected: `countries_failed=[]`, `n_failed=0`, `n_persisted≥1` OR all `countries_duplicate` if already persisted.

4. **US regression check**:
   ```bash
   uv run python -m sonar.pipelines.daily_monetary_indices --country US --date 2026-04-23 2>&1 | \
     grep "m3_compute_mode.*country=US"
   ```
   Expected: `mode=FULL` unchanged.

5. **Regression tests**:
   ```bash
   uv run pytest tests/unit/test_indices/test_db_backed_builder.py -v
   uv run pytest tests/ -x --tb=short
   ```
   Expected: new tests pass; no regressions (pre-existing SQLAlchemy/pytest-asyncio flake OK).

6. **Bash wrapper smoke** (Lesson #12 Tier A).

7. **Pre-commit clean double-run** (Lesson #2).

### Tier B — post-merge (operator scope)

1. **Systemd 6 EA cohort persist success**:
   ```bash
   sudo systemctl reset-failed sonar-daily-monetary-indices.service
   sudo systemctl start sonar-daily-monetary-indices.service
   sleep 120
   sudo journalctl -u sonar-daily-monetary-indices.service --since "-3 min" --no-pager | \
     grep "monetary_pipeline.summary"
   ```
   Expected: `n_failed=0`.

2. **DB persist verify**:
   ```bash
   sqlite3 data/sonar-dev.db \
     "SELECT country_code, COUNT(*) FROM monetary_m1_effective_rates WHERE date='2026-04-23' GROUP BY country_code;"
   ```
   Expected: 6+ countries with rows (depending on prior state).

3. **M3 FULL emit preserved**:
   ```bash
   sudo journalctl -u sonar-daily-monetary-indices.service --since "-3 min" --no-pager | \
     grep "m3_compute_mode" | grep -oE "mode=[A-Z_]+" | sort | uniq -c
   ```
   Expected: `6 mode=FULL`, `3 mode=DEGRADED`, `3 mode=NOT_IMPLEMENTED`.

4. **Zero event-loop errors**, **zero InsufficientInputsError**.

---

## §6 Retro scope

Documentar em `docs/planning/retrospectives/week11-sprint-q-1-2-load-histories-survey-fallback-report.md`:

### Regression root cause (empirical)

Sprint Q.1.1 shipped survey fallback for data point extraction (`build_m3_inputs_from_db` main function) but did NOT extend `_load_histories` helper function. Helper queries canonical `IndexValue` table exclusively → empty `anchor_hist` for EA cohort → downstream `InsufficientInputsError`.

### Lesson #20 iteration #5

Pattern "shipping path ≠ consuming path" observed again:
- Q.1.1 shipped `build_m3_inputs_from_db` survey branch (shipping path)
- `_load_histories` helper (consuming path for history arrays) unchanged
- `m3_market_expectations` downstream validates history arrays ≥ 2
- Gap: Q.1.1 fallback data-point-correct but history-incomplete

**Refinement of Lesson #20**: "Extend ALL helper functions along data flow path, not just the entry point."

Candidate ADR-0011 Principle 8 — "Observability-before-wiring + consumer-path-completeness" combined principle.

### M3 FULL runtime coverage (post Q.1.2)

Pre-Q.1.2: 1/12 FULL (US only, 6 EA cohort classifier-FULL but persist-failed)
Post-Q.1.2: 6/12 FULL runtime materialized

### T1 coverage delta

Pre-Q.1.2: ~58% (Q.1.1 regression negated Q.1 intended uplift)
Post-Q.1.2: ~68-70% (6 countries M3 FULL persist + runtime visible)

### Sprint Q series closure

- Sprint Q: wiring pattern canonical (Week 11 Day 1 AM)
- Sprint Q.0.5: cohort unification (Week 11 Day 1 lunch)
- Sprint Q.1: SPF connector + writer (Week 11 Day 1 PM)
- Sprint Q.1.1: db_backed_builder main path survey fallback (Week 11 Day 1 PM)
- **Sprint Q.1.2: _load_histories helper survey fallback (Week 11 Day 1 late)**

Together form architectural unblock EXPINF pipeline EA cohort. Sprint P MSC EA now truly unblocked for Day 2 AM.

### Week 11 Day 1 close state

5 sprints shipped clean + 1 regression fix (Q.1.2) = **6 sprints total Day 1**.

---

## §7 Execution notes

- **Audit-first §2.1** MUST precede §2.2 refactor. Confirm root cause exactly.
- **Minimal diff scope**: extend `_load_histories` only. Zero touch `build_m3_inputs_from_db`, classifier, live_assemblers.
- **Forward-fill semantics**: survey sparse (quarterly) → each forwards date gets latest-on-or-before survey row. Acceptable given SPF release cadence.
- **Existing helpers reuse**: `_survey_tenors_bps` (Q.1.1 shipped) + `ExpInflationSurveyRow` import (Q.1.1 shipped). No new helper imports.
- **US regression non-negotiable**: test 4 explicit check.
- **Pre-commit double-run** (Lesson #2)
- **sprint_merge.sh Step 10** (Lesson #4)
- **CC arranque template** (Lesson #5)
- **DB symlink** (Lesson #14)
- **Brief filename** Lesson #15 compliant
- **Pre-stage pre-commit** (Lesson #16 Day 3 prevention)

---

## §8 Dependencies & CAL interactions

### Parent sprint
Sprint Q.1.1 (Week 11 Day 1 PM) — builder main path survey fallback shipped, helper gap discovered Tier B

### CAL items closed by this sprint
- Informal — Q.1.1 `_load_histories` gap closed
- **Effective CAL-EXPINF-EA-ECB-SPF FULL operational closure** (Q.1 data + Q.1.1 builder + Q.1.2 helper = complete runtime path)

### CAL items potentially opened
- Nil — helper extension is bounded. If M4 FCI similar gap discovered during Tier B, open `CAL-M4-FCI-SURVEY-FALLBACK` Week 12+.

### Sprints blocked by this sprint
- **Sprint P (MSC EA)** — truly unblocked only post-Q.1.2 (needs M3 runtime FULL persist + data in DB for aggregation)

### Sprints unblocked by this sprint
- **Sprint P** confirmed Day 2 AM scope
- **Sprint Q.2 (GB-BOE-ILG-SPF)** pattern reference: Q.2 must extend BOTH `build_m3_inputs_from_db` AND `_load_histories` from start (Lesson #20 iteration #5 applied)

---

## §9 Time budget

Arranque target: ~20:30 WEST Day 1.
Hard stop: 21:15 WEST (45min wall-clock hard cap).

Realistic range:
- **Best case 15min**: helper extension trivial, tests pass first try, backfill clean
- **Median 25-30min**: 1-2 test iterations, edge case on sparse survey
- **Worst case 40-45min**: M4 similar gap discovered → document for Q.1.3 (Week 12+), ship Q.1.2 standalone

**Merge + Tier B**: +10 min operator.
**Day 1 close target**: 21:30-21:45 WEST com 6 sprints shipped + 6 countries M3 FULL persistently operational.

---

*End of brief. Fix Sprint Q.1.1 regression. Close Day 1 with runtime truth: 6 countries M3 FULL shipped AND persisted.*
