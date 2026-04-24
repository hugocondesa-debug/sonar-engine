# Sprint Q.0.5 — T1 Cohort Unification (M3/M4 Cohort Merge)

**Branch**: `sprint-q-0-5-t1-cohort-unification`
**Worktree**: `/home/macro/projects/sonar-wt-q-0-5-t1-cohort-unification`
**Data**: Week 11 Day 1 (2026-04-24) — target arranque ~12:00 WEST
**Operator**: Hugo Condesa (reviewer) + CC (executor)
**Budget**: 30-45min CC + 10min operator merge
**Priority**: **P0 prerequisite** — unblocks Sprint Q.1 (EA-ECB-SPF), Sprint P (MSC EA), Sprint M2-EA-per-country
**ADR-0010 tier scope**: T1 ONLY
**ADR-0009 v2.2 TE Path 1 probe**: N/A (refactor only)
**Brief format**: v3.3 (Tier A / Tier B + filename convention compliance)
**Systemd services affected**: `sonar-daily-monetary-indices.service` (cohort size change 7 → 12)
**Parent**: Sprint Q Tier B discovery — Sprint Q wiring works but natural fire default cohort is 7 (M4 FCI EA-custom), missing EA/GB/JP/CA/AU

---

## §1 Scope (why)

### Problem statement

Sprint Q (Week 11 Day 1 morning) shipped EXPINF wiring for M3 FULL promotion. Tier B verification revealed:

```
ExecStart=/bin/bash -lc 'uv run python -m sonar.pipelines.daily_monetary_indices --all-t1 --date $(...)'
```

`--all-t1` flag resolves to `T1_7_COUNTRIES = (US/DE/EA-periphery/NL)` — 7 countries **M4 FCI EA-custom cohort** (Sprint J scope).

Sprint O shipped separate `T1_M3_COUNTRIES = (US/DE/EA/GB/JP/CA/IT/ES/FR)` — 9 countries M3 observability cohort, opt-in via `--m3-t1-cohort` flag only.

**Consequence**: Natural fire default iterates 7, not 9. Sprint Q FULL promotion visible for US only (in both cohorts). EA/GB/JP/CA are **not invoked** by systemd default. Sprint Q.1 EA-ECB-SPF connector shipping would deposit data into `exp_inflation_*` tables that never get queried by default pipeline → runtime impact invisible.

### Root cause analysis

Sprint J (Week 10 Day 2) shipped M4 FCI EA-custom builder for 8 countries (US + EA aggregate + 5 EA members + PT/NL/Italy/Spain/France). Defined `T1_7_COUNTRIES` constant aligned with M4 FCI capability boundary.

Sprint O (Week 10 Day 3) shipped M3 classifier for 9 countries matching M3 T1 scope (US + DE + EA aggregate + non-EA T1: GB/JP/CA + EA periphery: IT/ES/FR). Defined separate `T1_M3_COUNTRIES` to avoid breaking Sprint J M4 dispatch.

**Tension**: two constants represent overlapping-but-non-identical T1 cohorts. Sprint M + Sprint T added PT/AU curves expanding true T1 curves to 11 countries (10 pre-Sprint-T + AU). Cohorts diverged further from reality.

### Objectivo Sprint Q.0.5

Unify to single `T1_COUNTRIES` constant matching **true T1 curves coverage**:

```python
T1_COUNTRIES = ("US", "DE", "EA", "GB", "JP", "CA", "IT", "ES", "FR", "NL", "PT", "AU")
```

12 countries (11 with live curves + NL with classifier-NOT_IMPLEMENTED graceful skip).

Default `--all-t1` iterates unified 12. `--m3-t1-cohort` deprecated (no-op, emits deprecation warning, resolves to same set). M4 FCI EA-custom builder logic remains per-country — AU/GB/JP/CA/NL simply classifier-resolve to scaffold/NOT_IMPLEMENTED gracefully (ADR-0011 Principle 2).

### Phase 2 impact

Post-Sprint Q.0.5:
- Natural fire processes 12 countries per dispatch
- EA/GB/JP/CA M3 classifier emit visible (DEGRADED, awaiting Sprint Q.1+Q.2)
- Sprint Q.1 ECB-SPF shipping becomes **visible immediately** — EA SPF data loaded by EA invocation in next natural fire
- Sprint P MSC EA L4 composite **truly unblockable** post-Q.1

---

## §2 Spec (what)

### 2.1 Constants unification

**File**: `src/sonar/pipelines/daily_monetary_indices.py`

**Current state**:
```python
T1_7_COUNTRIES = ("US", "DE", "EA", "IT", "ES", "FR", "NL", "PT")
T1_M3_COUNTRIES = ("US", "DE", "EA", "GB", "JP", "CA", "IT", "ES", "FR")
```

**Target state**:
```python
T1_COUNTRIES = (
    "US",   # M1/M2/M3/M4 FULL
    "DE",   # M3 DEGRADED (awaits Sprint Q.2), M4 FULL (Sprint J)
    "EA",   # M3 DEGRADED (awaits Sprint Q.1), M4 FULL (Sprint J), MSC-candidate post-Q.1
    "GB",   # M3 DEGRADED (awaits Sprint Q.2 BOE-ILG), M4 scaffold
    "JP",   # M3 DEGRADED, M4 scaffold
    "CA",   # M3 DEGRADED, M4 scaffold
    "IT",   # M3 DEGRADED (awaits EA-PERIPHERY-LINKERS), M4 FULL (Sprint J)
    "ES",   # M3 DEGRADED (awaits EA-PERIPHERY-LINKERS), M4 FULL (Sprint J)
    "FR",   # M3 DEGRADED (awaits BDF-OATI-LINKER), M4 FULL (Sprint J)
    "NL",   # Curves absent (Sprint M HALT-0), M-layers NOT_IMPLEMENTED gracefully
    "PT",   # Curves shipped Sprint M, M4 FULL (Sprint J), M3 DEGRADED
    "AU",   # Curves shipped Sprint T, M-layers NOT_IMPLEMENTED gracefully
)

# Backward compat aliases (deprecated, will remove Week 12+)
T1_7_COUNTRIES = T1_COUNTRIES  # deprecated alias (scope expanded)
T1_M3_COUNTRIES = T1_COUNTRIES  # deprecated alias (scope expanded)
```

**Rationale for aliases**: callers in other modules (tests, CLI docs, retrospectives) reference both. Preserve imports without break. Actual iteration logic uses single `T1_COUNTRIES`.

### 2.2 CLI flag semantics

**Before**:
```python
--all-t1         → T1_7_COUNTRIES (7)
--m3-t1-cohort   → T1_M3_COUNTRIES (9)
--country X      → single X
```

**After**:
```python
--all-t1         → T1_COUNTRIES (12)   # unified canonical
--m3-t1-cohort   → T1_COUNTRIES (12) + emit DeprecationWarning  # flag deprecated
--country X      → single X            # unchanged
```

Deprecation warning:
```python
if m3_t1_cohort:
    warnings.warn(
        "--m3-t1-cohort is deprecated. Use --all-t1 (now unified 12-country cohort). "
        "Flag will be removed in Week 12+ cleanup sprint.",
        DeprecationWarning,
        stacklevel=2,
    )
    targets = list(T1_COUNTRIES)
elif all_t1:
    targets = list(T1_COUNTRIES)
```

### 2.3 Systemd service — ExecStart verification

**Current**:
```
ExecStart=/bin/bash -lc '/home/macro/.local/bin/uv run python -m sonar.pipelines.daily_monetary_indices --all-t1 --date $(date -u -I -d yesterday)'
```

**Post-Sprint-Q.0.5**: **no ExecStart change required**. `--all-t1` now means 12 countries instead of 7. Systemd file untouched — reduces blast radius.

If CC disagrees (discovers some reason systemd needs update), document in retro §6 item #4.

### 2.4 Downstream consumer audit

`T1_7_COUNTRIES` and `T1_M3_COUNTRIES` may be imported elsewhere:

```bash
grep -rn "T1_7_COUNTRIES\|T1_M3_COUNTRIES" src/ tests/ docs/ 2>/dev/null | grep -v ".pyc"
```

For each match:
1. Production code in `src/` — replace with `T1_COUNTRIES` (aliases preserve interim)
2. Tests in `tests/` — adapt to 12-country expectations
3. Docs references — note in retro §6 for Week 11 docs cleanup sprint

**Scope gate**: if audit reveals >5 files importing either constant, limit Sprint Q.0.5 to `daily_monetary_indices.py` + tests/ adaptations; docs + aux cleanup defer to micro-sprint Week 11 Day 5.

### 2.5 Classifier per-country graceful handling

**Pre-requirement** — verify classifier handles:

| Country | Curves state | Expected classifier emit |
|---|---|---|
| US/DE/EA/GB/JP/CA/IT/ES/FR | live | FULL or DEGRADED (Sprint O/Q logic) |
| PT | live (Sprint M) | DEGRADED (no EXPINF yet) |
| NL | absent (Sprint M HALT-0) | `NOT_IMPLEMENTED` mode + `m3_skipped_upstream_not_shipped` |
| AU | live (Sprint T) | `NOT_IMPLEMENTED` mode + policy `AU: no M3 policy shipped yet` |

CC must verify NL + AU emit graceful NOT_IMPLEMENTED without exception. Sprint O classifier was designed for 9-country cohort; AU addition may surface edge case.

If AU classifier raises `KeyError: 'AU' not in m3_country_policies`:
- Add AU to `m3_country_policies.py` with explicit `NOT_IMPLEMENTED` policy + rationale "M3 builder not implemented — awaiting future Sprint"
- Do NOT ship M3 builder for AU this sprint (scope lock)

### 2.6 Regression tests update

Adapt existing tests:

```bash
grep -rn "T1_7_COUNTRIES\|T1_M3_COUNTRIES\|len.*== *7\|len.*== *9" tests/ 2>/dev/null
```

For each match, update expectations:
- Test asserting cohort size 7 → 12
- Test asserting cohort size 9 → 12
- Test asserting specific country in cohort → ensure country present in unified 12

New test:
```python
def test_t1_countries_unified_size():
    """Sprint Q.0.5: T1_COUNTRIES unified cohort is 12 (curves T1 + classifier coverage)."""
    from sonar.pipelines.daily_monetary_indices import T1_COUNTRIES
    assert len(T1_COUNTRIES) == 12
    expected = {"US", "DE", "EA", "GB", "JP", "CA", "IT", "ES", "FR", "NL", "PT", "AU"}
    assert set(T1_COUNTRIES) == expected

def test_deprecated_aliases_return_unified():
    """Backward compat: T1_7_COUNTRIES and T1_M3_COUNTRIES alias to T1_COUNTRIES."""
    from sonar.pipelines.daily_monetary_indices import (
        T1_COUNTRIES, T1_7_COUNTRIES, T1_M3_COUNTRIES,
    )
    assert T1_7_COUNTRIES == T1_COUNTRIES
    assert T1_M3_COUNTRIES == T1_COUNTRIES

def test_m3_t1_cohort_flag_deprecated():
    """CLI --m3-t1-cohort emits DeprecationWarning + resolves to T1_COUNTRIES."""
    # ... runner invocation + warning capture
```

### 2.7 AU classifier policy (conditional on §2.5 finding)

**Only if** §2.5 audit reveals AU missing from `m3_country_policies.py`:

```python
# src/sonar/indices/monetary/m3_country_policies.py
M3_COUNTRY_POLICIES = {
    "US": ...,
    "DE": ...,
    # ... existing 9 ...
    "AU": M3Policy(
        country="AU",
        mode="NOT_IMPLEMENTED",
        reason="M3 builder + EXPINF connector not shipped. Awaits future sprint.",
        related_cals=["CAL-M3-AU-BUILDER"],
    ),
}
```

Similar for NL if missing (should be present from Sprint O based on NL AU ship Day 3 retro).

### 2.8 CLI help text update

```bash
grep -A 3 "all-t1\|m3-t1-cohort" src/sonar/pipelines/daily_monetary_indices.py | head -20
```

Update `--all-t1` help text:
```
--all-t1: Iterate over the 12-country T1 cohort (US/DE/EA/GB/JP/CA/IT/ES/FR/NL/PT/AU).
          Unified Sprint Q.0.5 (Week 11 Day 1) — replaces M4-EA-custom-7 and M3-T1-9
          cohorts with single canonical T1 coverage.
```

Update `--m3-t1-cohort` help text to `[DEPRECATED — use --all-t1]`.

---

## §3 Commits plan

| Commit | Scope | Ficheiros |
|---|---|---|
| **C1** | refactor(pipelines): T1_COUNTRIES unified 12-country cohort | `src/sonar/pipelines/daily_monetary_indices.py` |
| **C2** | fix(indices): AU + NL m3_country_policies NOT_IMPLEMENTED policies (if §2.5 audit needs) | `src/sonar/indices/monetary/m3_country_policies.py` (conditional) |
| **C3** | test: regression coverage 12-country cohort + deprecation aliases | `tests/unit/test_pipelines/test_daily_monetary_indices.py` (extend) |
| **C4** | docs(planning): Sprint Q.0.5 retrospective + cohort unification rationale | `docs/planning/retrospectives/week11-sprint-q-0-5-t1-cohort-unification-report.md` |

4 commits target. C2 conditional. C4 mandatory.

---

## §4 HALT triggers

**HALT-0 (structural)**:
- §2.4 audit reveals >10 files importing T1_7_COUNTRIES/T1_M3_COUNTRIES → sprint scope explodes. Ship only `daily_monetary_indices.py` + direct tests. Open CAL-COHORT-CONSTANT-CLEANUP for Week 11 Day 5.
- `m3_country_policies.py` raise on AU or NL invocation → §2.7 required, but if policy module has architectural issue, pause + report.

**HALT-material**:
- Systemd service requires update despite §2.3 claim → revisit, document.
- `--all-t1` semantic change breaks other pipelines (daily_curves, daily_cost_of_capital) that import T1_COUNTRIES indirectly → STOP, assess downstream cascade.

**HALT-scope**:
- Temptation to ship M3 builder for AU/NL → STOP. Sprint Q.0.5 is cohort unification only.
- Temptation to add new EXPINF connectors → STOP. Sprint Q.1 scope.
- Temptation to update docs/backlog/calibration-tasks.md extensively → STOP. Defer doc cleanup.

**HALT-security**: standard.

---

## §5 Acceptance

### Tier A — pre-merge (CC scope, v3.3 compliance)

1. **Constants unified**:
```bash
grep -E "^T1_.*_COUNTRIES *=" src/sonar/pipelines/daily_monetary_indices.py
```
Expected: 3 definitions (T1_COUNTRIES canonical + 2 deprecated aliases).

2. **Cohort size 12**:
```bash
uv run python -c "from sonar.pipelines.daily_monetary_indices import T1_COUNTRIES; print(len(T1_COUNTRIES), sorted(T1_COUNTRIES))"
```
Expected: `12 ['AU', 'CA', 'DE', 'EA', 'ES', 'FR', 'GB', 'IT', 'JP', 'NL', 'PT', 'US']`

3. **Local CLI — 12-country iteration**:
```bash
uv run python -m sonar.pipelines.daily_monetary_indices --all-t1 --date 2026-04-23 2>&1 | \
  grep "m3_compute_mode" | wc -l
```
Expected: 12 entries (one per country).

4. **US still FULL** (regression check Sprint Q):
```bash
uv run python -m sonar.pipelines.daily_monetary_indices --all-t1 --date 2026-04-23 2>&1 | \
  grep "m3_compute_mode.*country=US"
```
Expected: `mode=FULL`.

5. **AU + NL graceful**:
```bash
uv run python -m sonar.pipelines.daily_monetary_indices --all-t1 --date 2026-04-23 2>&1 | \
  grep -E "country=(AU|NL)"
```
Expected: emit present, no exception, mode=NOT_IMPLEMENTED or m3_skipped_upstream_not_shipped.

6. **Bash wrapper smoke** (Lesson #12 Tier A):
```bash
bash -lc 'uv run python -m sonar.pipelines.daily_monetary_indices --all-t1 --date 2026-04-23'
```
Expected: exit 0, same 12 emit.

7. **Regression tests**:
```bash
uv run pytest tests/ -x --tb=short
```
Expected: all pass (no regressions on 2158+ existing tests).

8. **Pre-commit clean double-run** (Lesson #2).

### Tier B — post-merge (operator scope)

1. **Systemd verify 12-country cohort**:
```bash
sudo systemctl reset-failed sonar-daily-monetary-indices.service
sudo systemctl start sonar-daily-monetary-indices.service
sleep 120
sudo journalctl -u sonar-daily-monetary-indices.service --since "-3 min" --no-pager | \
  grep "m3_compute_mode" | wc -l
```
Expected: 12.

2. **Classification breakdown**:
```bash
sudo journalctl -u sonar-daily-monetary-indices.service --since "-3 min" --no-pager | \
  grep "m3_compute_mode" | awk '{print $NF}' | sort | uniq -c
```
Expected approx:
- `1 mode=FULL` (US)
- `8 mode=DEGRADED` (DE/EA/GB/JP/CA/IT/ES/FR — classifier-capable)
- `3 mode=NOT_IMPLEMENTED` (PT/NL/AU — policies but no classifier path OR curves absent)

(Or similar — exact breakdown depends on classifier state per country.)

3. **Summary clean**:
```bash
sudo journalctl -u sonar-daily-monetary-indices.service --since "-3 min" --no-pager | \
  grep "monetary_pipeline.summary"
```
Expected: n_failed=0.

4. **Zero event-loop errors** (ADR-0011 P6 holds):
```bash
sudo journalctl -u sonar-daily-monetary-indices.service --since "-3 min" --no-pager | \
  grep -iE "event loop is closed|connector_aclose_error" | wc -l
```
Expected: 0.

---

## §6 Retro scope

Documentar em `docs/planning/retrospectives/week11-sprint-q-0-5-t1-cohort-unification-report.md`:

### Cohort unification history

- Sprint J Week 10 Day 2 → T1_7_COUNTRIES (M4 FCI EA-custom scope)
- Sprint O Week 10 Day 3 → T1_M3_COUNTRIES (M3 classifier scope, separate to avoid Sprint J break)
- Sprint M + T Week 10 Day 3 → PT + AU added to curves T1
- Sprint Q Week 11 Day 1 AM → EXPINF wiring visible for US only (cohort mismatch discovery)
- Sprint Q.0.5 Week 11 Day 1 lunch → unification to 12-country canonical

### Observability impact matrix

Pre-Q.0.5 (default `--all-t1`): 7 countries observable
Post-Q.0.5 (default `--all-t1`): 12 countries observable

### Sprint downstream impact

- Sprint Q.1 (EA-ECB-SPF) — now visible immediately in natural fire
- Sprint Q.2 (GB-BOE-ILG-SPF) — idem
- Sprint P (MSC EA) — unblocked
- Sprint M2-EA-per-country — DE/FR/IT/ES/NL now iterated, per-country builders can be invoked

### Technical debt closed

Dual-constant drift (T1_7 vs T1_M3) eliminated. Backward compat via deprecated aliases preserves imports. Week 12+ cleanup sprint can remove aliases.

### Lessons candidates

- **Lesson #17 candidate**: cohort constants should track true layer coverage, not per-layer slice. Single T1_COUNTRIES with per-country classifier policies is cleaner than multiple constants per-layer scope.
- **Lesson #18 candidate**: systemd ExecStart audit should be Tier B verification standard whenever pipeline dispatcher semantics change.

---

## §7 Execution notes

- **Audit-first § 2.4 + §2.5** MUST precede C1 refactor. Surfaces edge cases (AU missing policy) early.
- **Backward compat aliases critical** — don't remove T1_7/T1_M3 references in production code this sprint. Only replace in `daily_monetary_indices.py` itself + tests. Other files use aliases until Week 12+ cleanup.
- **Deprecation warning syntax**: use Python standard `warnings.warn(..., DeprecationWarning)`, not custom logger — tests can capture via `pytest.warns`.
- **Pre-commit double-run** (Lesson #2)
- **sprint_merge.sh Step 10** cleanup (Lesson #4)
- **CC arranque template** (Lesson #5) — apply
- **DB symlink** auto-provisioned (Lesson #14) — verify operational
- **Brief filename** Lesson #15 compliant (`week11-sprint-q-0-5-t1-cohort-unification-brief.md`)

---

## §8 Dependencies & CAL interactions

### Parent sprint
Sprint Q (Week 11 Day 1 AM) — cohort mismatch Tier B discovery

### CAL items closed by this sprint
- Informal — "dual cohort constant drift" resolved

### CAL items opened by this sprint
- **CAL-COHORT-CONSTANT-CLEANUP** (Week 12+ low priority) — remove deprecated aliases once all downstream consumers migrate
- **CAL-M3-AU-BUILDER** (low priority) — placeholder for eventual AU M3 builder (post-Sprint-T Path 2 future)

### Sprints blocked by this sprint
- **None** — Sprint Q.0.5 is unblock, not blocked.

### Sprints unblocked by this sprint
- **Sprint Q.1 (EA-ECB-SPF)** — EA visible in natural fire post-unification
- **Sprint Q.2 (GB-BOE-ILG-SPF)** — GB visible
- **Sprint P (MSC EA)** — EA aggregate iteration confirmed
- **Sprint M2-EA-per-country** — DE/FR/IT/ES/NL all iterated
- **Sprint M4-scaffold-upgrade GB/JP/CA** — iteration confirmed for M4 scope

---

*End of brief. Technical debt micro-sprint. Ship quick, unlock cascade Week 11.*
