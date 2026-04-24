# Sprint Q.1.1 — DB-Backed Builder EXPINF Survey Fallback Hierarchy

**Branch**: `sprint-q-1-1-db-backed-builder-expinf-survey-fallback`
**Worktree**: `/home/macro/projects/sonar-wt-q-1-1-db-backed-builder-expinf-survey-fallback`
**Data**: Week 11 Day 1 (2026-04-24) — target arranque ~17:45 WEST
**Operator**: Hugo Condesa (reviewer) + CC (executor, full autonomy per SESSION_CONTEXT)
**Budget**: 30-45min CC + 10min operator merge
**Priority**: **P0 urgent** — closes Sprint Q.1 runtime gap (SPF data shipped but classifier still emits M3_EXPINF_MISSING)
**ADR-0010 tier scope**: T1 ONLY
**ADR-0009 v2.2 TE Path 1 probe**: N/A (DB refactor only)
**Brief format**: v3.3
**Systemd services affected**: `sonar-daily-monetary-indices.service` — 6 countries M3 DEGRADED → FULL expected post-fix
**Parent**: Sprint Q.1 Tier B discovery — data-path vs DB-backed-consumer mismatch

---

## §1 Scope (why)

### Problem statement (diagnosed via Sprint Q.1 Tier B + subsequent triage)

Sprint Q.1 shipped:
- ✅ ECB SDW SPF connector (`fetch_survey_expected_inflation`)
- ✅ Writer (`persist_survey_row`)
- ✅ 30 rows populated in `exp_inflation_survey` (6 countries × 5 dates)
- ✅ Loader dispatcher (`load_live_exp_inflation_kwargs`) with EA SPF branch
- ✅ live_assemblers wired to loader

Sprint Q.1 **did not ship** the actual runtime fix — because the production monetary pipeline path uses `db_backed_builder.MonetaryDbBackedInputsBuilder`, not `live_assemblers`. Confirmed via code inspection:

```python
# daily_monetary_indices.py lines 540-575 (canonical path):
if db_backed_builder is not None:
    m3_inputs = db_backed_builder.build_m3_inputs(country_code, observation_date)
```

`db_backed_builder` reads **only** `exp_inflation_canonical` table (via `expected_inflation_tenors_json` field). Sprint Q.1 populated `exp_inflation_survey`, which `db_backed_builder` **ignores**.

### Runtime evidence (natural fire Apr 24)

```
country=EA flags=('EA_M3_T1_TIER', 'M3_EXPINF_MISSING') mode=DEGRADED
country=DE flags=('DE_M3_T1_TIER', 'M3_EXPINF_MISSING') mode=DEGRADED
country=FR flags=('FR_M3_T1_TIER', 'M3_EXPINF_MISSING') mode=DEGRADED
country=IT flags=('IT_M3_T1_TIER', 'IT_M3_BEI_BTP_EI_SPARSE_EXPECTED', 'M3_EXPINF_MISSING') mode=DEGRADED
country=ES flags=('ES_M3_T1_TIER', 'ES_M3_BEI_BONOS_EI_LIMITED_EXPECTED', 'M3_EXPINF_MISSING') mode=DEGRADED
```

6 countries have SPF data in DB, classifier emits `M3_EXPINF_MISSING`.

### SPF data reality (available in exp_inflation_survey)

Sample EA row:
```
survey_name='ECB_SPF_HICP'
interpolated_tenors_json={"10Y": 0.0202, "5Y": 0.0202, "5y5y": 0.0202, "1Y": 0.0197, "2Y": 0.0205, "30Y": 0.0202}
flags='SPF_LT_AS_ANCHOR' (EA) OR 'SPF_LT_AS_ANCHOR,SPF_AREA_PROXY' (DE/FR/IT/ES/PT)
```

Data is usable — 5y5y = 2.02% well-anchored, 10Y available, complete tenor coverage.

### Objectivo Sprint Q.1.1

Extend `db_backed_builder.build_m3_inputs` fallback hierarchy:
1. Primary: `exp_inflation_canonical` (existing behavior)
2. **Fallback NEW**: `exp_inflation_survey` when canonical empty for (country, date)
3. Flags propagation: `SPF_AREA_PROXY` from survey row carries through to M3 classifier emit

---

## §2 Spec (what)

### 2.1 Pre-flight audit (MANDATORY)

CC must complete audits before refactor:

#### 2.1.1 db_backed_builder current structure

```bash
cd /home/macro/projects/sonar-wt-q-1-1-db-backed-builder-expinf-survey-fallback

# Locate build_m3_inputs + expected_inflation_tenors extraction
grep -n "def build_m3_inputs\|expected_inflation_tenors\|expected_inflation_5y5y\|breakeven_5y5y" \
  src/sonar/indices/monetary/db_backed_builder.py

# Full function signature + body
sed -n '/def build_m3_inputs/,/^    def \|^def /p' \
  src/sonar/indices/monetary/db_backed_builder.py | head -100
```

Document in `docs/backlog/audits/sprint-q-1-1-db-backed-fallback-audit.md` (new):
- Current canonical-read logic (line references)
- Return value shape (dict keys, types)
- Flag propagation mechanism (how `M3_EXPINF_MISSING` is set)

#### 2.1.2 exp_inflation_survey schema consumption plan

Schema confirmed from Sprint Q.1 Tier B diagnosis:
```sql
CREATE TABLE exp_inflation_survey (
    id, exp_inf_id, country_code, date, methodology_version,
    confidence, flags (TEXT CSV),
    created_at,
    survey_name, survey_release_date,
    horizons_json,             -- {"1Y": ..., "2Y": ..., "LTE": ...}
    interpolated_tenors_json,  -- {"10Y": ..., "5Y": ..., "5y5y": ..., "1Y": ..., "2Y": ..., "30Y": ...}
    PRIMARY KEY (id)
);
```

Key insight: **`interpolated_tenors_json` has `5y5y` + `10Y` keys** — exactly what M3 builder needs for FULL classification.

Parse pattern:
```python
import json
tenors_raw = json.loads(row.interpolated_tenors_json)
breakeven_5y5y_bps = _decimal_to_bps(tenors_raw.get("5y5y"))
survey_10y_bps = _decimal_to_bps(tenors_raw.get("10Y"))
```

#### 2.1.3 Flag propagation map

Survey row flags → M3 emit flags mapping:
- `SPF_LT_AS_ANCHOR` (from survey) → pass through to M3 flags
- `SPF_AREA_PROXY` (from survey, DE/FR/IT/ES/PT only) → pass through transparently
- **New flag added by fallback**: `M3_EXPINF_FROM_SURVEY` (indicates fallback path used vs canonical)

#### 2.1.4 US regression check

**Critical**: US M3 FULL emit currently works. How? Two hypotheses:
1. US routes through live_assembler path (not db_backed) via special dispatch
2. US has canonical rows populated somewhere Sprint Q.1.1 mustn't disturb

Verify:
```bash
sqlite3 data/sonar-dev.db \
  "SELECT country_code, COUNT(*) FROM exp_inflation_canonical GROUP BY country_code;
   SELECT country_code, COUNT(*) FROM exp_inflation_bei GROUP BY country_code;
   SELECT country_code, COUNT(*) FROM exp_inflation_swap GROUP BY country_code;"
```

Document US path. Sprint Q.1.1 must not regress US FULL.

### 2.2 Fallback implementation

**File**: `src/sonar/indices/monetary/db_backed_builder.py`

Pseudocode:
```python
def build_m3_inputs(self, country_code, observation_date):
    # Step 1: Try canonical (existing)
    canonical_row = self._query_canonical(country_code, observation_date)
    if canonical_row is not None:
        tenors_bps = _parse_canonical_tenors(canonical_row)
        return M3Inputs(
            breakeven_5y5y_bps=tenors_bps.get("5y5y"),
            survey_10y_bps=tenors_bps.get("10Y"),
            bei_10y_bps=tenors_bps.get("10Y"),
            flags=_parse_flags(canonical_row.flags),
            source="canonical",
        )

    # Step 2 NEW (Sprint Q.1.1): Try survey fallback
    survey_row = self._query_survey(country_code, observation_date)
    if survey_row is not None:
        tenors_raw = json.loads(survey_row.interpolated_tenors_json)
        breakeven_5y5y_bps = _decimal_to_bps(tenors_raw.get("5y5y"))
        survey_10y_bps = _decimal_to_bps(tenors_raw.get("10Y"))

        survey_flags = _parse_flags(survey_row.flags)  # CSV → tuple
        propagated_flags = survey_flags + ("M3_EXPINF_FROM_SURVEY",)

        return M3Inputs(
            breakeven_5y5y_bps=breakeven_5y5y_bps,
            survey_10y_bps=survey_10y_bps,
            bei_10y_bps=None,  # survey doesn't provide BEI
            flags=propagated_flags,
            source="survey",
        )

    # Step 3: Nothing available (existing)
    return None  # triggers M3_EXPINF_MISSING
```

### 2.3 Query helper for survey table

Add `_query_survey` method:

```python
def _query_survey(
    self,
    country_code: str,
    observation_date: date,
) -> ExpInfSurvey | None:
    """
    Query exp_inflation_survey for most recent row on-or-before observation_date.
    Uses ORM model ExpInfSurvey (Sprint Q.1 shipped).
    Returns None if no row found.
    """
    return (
        self._session.query(ExpInfSurvey)
        .filter(
            ExpInfSurvey.country_code == country_code,
            ExpInfSurvey.date <= observation_date,
        )
        .order_by(ExpInfSurvey.date.desc())
        .first()
    )
```

Import ORM model from Sprint Q.1 (`src/sonar/overlays/expected_inflation.py` or wherever Q.1 placed it).

### 2.4 Flag parsing helper (reuse if exists)

Check if `_parse_flags(csv_string) -> tuple[str, ...]` utility exists. If yes, reuse. If no, add simple helper:

```python
def _parse_flags(flags_csv: str | None) -> tuple[str, ...]:
    if not flags_csv:
        return ()
    return tuple(f.strip() for f in flags_csv.split(",") if f.strip())
```

### 2.5 Regression tests

**File**: `tests/unit/test_indices/test_db_backed_builder.py` (extend existing or create)

Tests to add:
```python
def test_build_m3_inputs_canonical_primary(test_session, sample_canonical_row):
    """Sprint Q.1.1: canonical row takes priority over survey."""
    # Populate BOTH canonical + survey for EA
    # Assert source='canonical' + M3_EXPINF_FROM_SURVEY NOT in flags

def test_build_m3_inputs_survey_fallback(test_session, sample_survey_row):
    """Sprint Q.1.1: survey fallback when canonical empty."""
    # Populate ONLY survey for EA
    # Assert source='survey', breakeven_5y5y_bps matches interpolated_tenors 5y5y × 10000
    # Assert flags include ('SPF_LT_AS_ANCHOR', 'M3_EXPINF_FROM_SURVEY')

def test_build_m3_inputs_survey_area_proxy_flag_preserved(test_session, sample_survey_row_proxy):
    """Sprint Q.1.1: AREA_PROXY flag from survey preserved through fallback."""
    # Survey row with flags='SPF_LT_AS_ANCHOR,SPF_AREA_PROXY' for DE
    # Assert both flags in output + M3_EXPINF_FROM_SURVEY added

def test_build_m3_inputs_no_data_returns_none(test_session):
    """Sprint Q.1.1: neither canonical nor survey → None (triggers M3_EXPINF_MISSING)."""
    # Empty DB for country
    # Assert returns None (backward compat)

def test_build_m3_inputs_us_regression_unchanged(test_session, sample_us_row):
    """Sprint Q.1.1: US path remains FULL (regression check)."""
    # Assert US still resolves with pre-Q.1.1 behavior
```

### 2.6 Backfill + verify

Post-code ship, re-run M3 for 6 EA cohort countries:

```bash
for date in 2026-04-19 2026-04-20 2026-04-21 2026-04-22 2026-04-23; do
  uv run python -m sonar.pipelines.daily_monetary_indices --all-t1 --date $date
done

# Verify FULL emit
sudo journalctl -u sonar-daily-monetary-indices.service --since "-5 min" --no-pager | \
  grep "m3_compute_mode" | grep -oE "country=[A-Z]+|mode=[A-Z_]+" | paste - - | sort | uniq -c
```

Expected post-Q.1.1:
- `6 mode=FULL` (US + EA + DE + FR + IT + ES + PT — wait, that's 7)
- Actually: EA + DE + FR + IT + ES + PT = 6 from Q.1 cohort + US = **7 FULL**

Correction expected: 7 FULL (US + EA cohort 6), 3 DEGRADED (GB + JP + CA — no EXPINF connector yet), 2 NOT_IMPLEMENTED (NL + AU — no curves or policy).

---

## §3 Commits plan

| Commit | Scope | Ficheiros |
|---|---|---|
| **C1** | docs(backlog): Sprint Q.1.1 audit — db_backed fallback design | `docs/backlog/audits/sprint-q-1-1-db-backed-fallback-audit.md` (new) |
| **C2** | refactor(indices): db_backed_builder EXPINF survey fallback | `src/sonar/indices/monetary/db_backed_builder.py` |
| **C3** | test: regression coverage canonical primary + survey fallback + flag propagation | `tests/unit/test_indices/test_db_backed_builder.py` (extend) |
| **C4** | docs(planning): Sprint Q.1.1 retrospective + M3 FULL runtime matrix | `docs/planning/retrospectives/week11-sprint-q-1-1-db-backed-builder-expinf-survey-fallback-report.md` |

4 commits total. Clean scope.

---

## §4 HALT triggers

**HALT-0 (structural)**:
- **`_query_survey` ORM import fails** (ExpInfSurvey model location unknown) → audit §2.1 must identify correct import path first
- **Schema mismatch discovered** — `interpolated_tenors_json` field structure differs from documented → document + re-plan

**HALT-material**:
- **US regression** — any change to canonical path breaks US FULL emit → STOP + triage
- **Flag CSV parsing edge cases** — multi-flag CSV from survey row doesn't round-trip correctly → fix robust parser
- **Builder signature change required** (new dependencies injected) → assess downstream impact

**HALT-scope**:
- Temptation to ADD canonical writer from survey → STOP. Separate Sprint Q.1.2 scope (survey → canonical synthesis).
- Temptation to wire live_assembler path in parallel → STOP. Architectural refactor separate future sprint.
- Temptation to add BEI fallback simultaneously → STOP. This sprint = survey only.
- Temptation to fix Sprint Q.1 retro over-claims → STOP. Retro amendments separate doc cleanup.

**HALT-security**: standard.

---

## §5 Acceptance

### Tier A — pre-merge (CC scope, v3.3 compliance)

1. **Audit doc shipped**:
   ```bash
   test -f docs/backlog/audits/sprint-q-1-1-db-backed-fallback-audit.md && \
     wc -l docs/backlog/audits/sprint-q-1-1-db-backed-fallback-audit.md
   ```
   Expected: ≥40 lines with canonical path documentation + survey fallback design.

2. **Fallback method shipped**:
   ```bash
   grep "_query_survey\|M3_EXPINF_FROM_SURVEY" src/sonar/indices/monetary/db_backed_builder.py | wc -l
   ```
   Expected: ≥2 matches.

3. **Local CLI — 6-country EA cohort M3 FULL**:
   ```bash
   uv run python -m sonar.pipelines.daily_monetary_indices --all-t1 --date 2026-04-23 2>&1 | \
     grep "m3_compute_mode" | grep -c "FULL"
   ```
   Expected: ≥7 (US + EA + DE + FR + IT + ES + PT)

   Minimum acceptable: ≥6 (in case PT SPF row differs).

4. **Regression tests**:
   ```bash
   uv run pytest tests/unit/test_indices/test_db_backed_builder.py -v
   uv run pytest tests/ -x --tb=short
   ```
   Expected: new tests pass; full suite no regressions (pre-existing SQLAlchemy/pytest-asyncio flake OK per Sprint Q.1 note).

5. **US regression check**:
   ```bash
   uv run python -m sonar.pipelines.daily_monetary_indices --country US --date 2026-04-23 2>&1 | \
     grep "m3_compute_mode.*country=US"
   ```
   Expected: `mode=FULL` still.

6. **Bash wrapper smoke** (Lesson #12 Tier A):
   ```bash
   bash -lc 'uv run python -m sonar.pipelines.daily_monetary_indices --all-t1 --date 2026-04-23'
   ```
   Expected: exit 0, n_failed=0.

7. **Pre-commit clean double-run** (Lesson #2).

### Tier B — post-merge (operator scope)

1. **Systemd 7-country M3 FULL emit**:
   ```bash
   sudo systemctl reset-failed sonar-daily-monetary-indices.service
   sudo systemctl start sonar-daily-monetary-indices.service
   sleep 120
   sudo journalctl -u sonar-daily-monetary-indices.service --since "-3 min" --no-pager | \
     grep "m3_compute_mode" | grep -oE "mode=[A-Z_]+" | sort | uniq -c
   ```
   Expected: `7 mode=FULL`, `3 mode=DEGRADED`, `2 mode=NOT_IMPLEMENTED`.

2. **AREA_PROXY flag visible in emit for DE/FR/IT/ES/PT**:
   ```bash
   sudo journalctl -u sonar-daily-monetary-indices.service --since "-3 min" --no-pager | \
     grep "m3_compute_mode.*country=DE"
   ```
   Expected: flags include `SPF_AREA_PROXY`, `M3_EXPINF_FROM_SURVEY`.

3. **Zero event-loop errors**, **summary n_failed=0**.

---

## §6 Retro scope

Documentar em `docs/planning/retrospectives/week11-sprint-q-1-1-db-backed-builder-expinf-survey-fallback-report.md`:

### M3 FULL runtime coverage matrix (pre/post-Q.1.1)

| Country | Pre-Q.1.1 | Post-Q.1.1 | Source | Flags |
|---|---|---|---|---|
| US | FULL | FULL | (unchanged US path) | US_M3_T1_TIER, M3_FULL_LIVE |
| EA | DEGRADED | FULL | survey | EA_M3_T1_TIER, SPF_LT_AS_ANCHOR, M3_EXPINF_FROM_SURVEY |
| DE | DEGRADED | FULL | survey | DE_M3_T1_TIER, SPF_LT_AS_ANCHOR, SPF_AREA_PROXY, M3_EXPINF_FROM_SURVEY |
| FR | DEGRADED | FULL | survey (proxy) | ... |
| IT | DEGRADED | FULL | survey (proxy) | ... (+IT_M3_BEI_BTP_EI_SPARSE_EXPECTED preserved) |
| ES | DEGRADED | FULL | survey (proxy) | ... |
| PT | NOT_IMPLEMENTED | FULL / NOT_IMPLEMENTED | context-dependent | ... |
| GB | DEGRADED | DEGRADED | (unchanged, awaits Q.2) | GB_M3_T1_TIER, M3_EXPINF_MISSING |
| JP | DEGRADED | DEGRADED | (unchanged, awaits Q.3) | ... |
| CA | DEGRADED | DEGRADED | (unchanged, awaits Q.3) | ... |

### T1 coverage delta

- Pre-Q.1.1: ~58% (only US M3 FULL materialized)
- Post-Q.1.1: ~68-72% (6 additional countries M3 FULL cascade realized)
- **First single-sprint ±10pp realized runtime impact of Week 11**

### Sprint Q.1 retro amendment

Sprint Q.1 retro claim "6 countries M3 FULL cascade" was data-ready + loader-ready, not runtime-operational. Sprint Q.1.1 closes the data-path-to-consumer gap. Amendment stated in retro §6.

### Pattern learned — "observability vs runtime" recursive

Sprint O: classifier shipped but wiring missing → Sprint Q fix.
Sprint Q: wiring shipped to live_assembler but production uses db_backed → Sprint Q.1.1 fix.

**Pattern**: each architectural layer can harbor the "shipped but not consumed" gap. Audit-first discipline must extend to verifying **both shipping path AND consumer path** for full runtime effect.

**Candidate Lesson #20**: "Shipping path ≠ consuming path" — verify both ends of any data pipeline when classifier-promotion depends on it.

### Week 11 Day 1 close delta

- Sprints shipped: 4 → 5 (Q + Q.0.5 + Q.1 + T-Retry + Q.1.1)
- T1 runtime materialized: 68-72%
- Sprint P (MSC EA) now **truly** unblocked for Day 2 AM
- Sprint Q.2 GB-BOE-ILG scope unchanged

---

## §7 Execution notes

- **Audit-first §2.1** MUST precede §2.2 refactor. Surfaces US path uncertainty.
- **Backward compat critical**: canonical primary path unchanged, survey is FALLBACK only.
- **US regression check**: non-negotiable Tier A item 5. Any change breaking US path = STOP.
- **Flag propagation test**: AREA_PROXY transparency is Sprint Q.1 architectural intent, must be preserved through Q.1.1 fallback.
- **Pre-commit double-run** (Lesson #2)
- **sprint_merge.sh Step 10** (Lesson #4)
- **CC arranque template** (Lesson #5)
- **DB symlink** (Lesson #14)
- **Brief filename** Lesson #15 compliant
- **Pre-stage pre-commit** (Lesson #16 Day 3 prevention)

---

## §8 Dependencies & CAL interactions

### Parent sprint
Sprint Q.1 (Week 11 Day 1 afternoon) — data layer shipped, runtime gap discovered via Tier B

### CAL items closed by this sprint
- Informal — "Sprint Q.1 data-path vs consumer gap" resolved
- **Effective CAL-EXPINF-EA-ECB-SPF full closure** (Q.1 opened data, Q.1.1 wires consumer)

### CAL items potentially opened by this sprint
- `CAL-EXPINF-CANONICAL-SYNTHESIS` Week 12+ — canonical writer from survey data for archival / lossless canonical record (low priority)

### Sprints blocked by this sprint
- **Sprint P (MSC EA)** — now truly unblocked post-Q.1.1 (EA M3 FULL runtime, not paper)

### Sprints unblocked by this sprint
- **Sprint P** confirmed Day 2 AM scope
- **Sprint Q.2 (GB-BOE-ILG-SPF)** pattern reference: Q.2 will need analogous db_backed fallback OR canonical writer (scope decision Q.2 brief)
- **Sprint M2-EA-per-country** — MSC per-country feasibility uplift

---

## §9 Time budget

Arranque target: ~17:45 WEST Day 1.
Hard stop: 18:45 WEST (1h wall-clock hard cap — late Day 1).

Realistic range:
- **Best case 30min**: ORM model import clean, fallback logic trivial, tests pass first try
- **Median 40-50min**: audit surfaces US path nuance, 1-2 test iterations
- **Worst case HALT**: `ExpInfSurvey` ORM location fragmented → simpler raw SQL fallback (scope expands 15min)

**Merge + Tier B verify**: +10min operator.
**Day 1 close target**: 19:00 WEST with 5 sprints + 7 FULL M3 emit.

---

*End of brief. P0 runtime gap closure. Ship micro-surgical. Close Day 1 strong.*
