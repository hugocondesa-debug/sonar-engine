# Sprint Q.2 — CAL-EXPINF-GB-BOE-ILG-SPF (GB M3 FULL Uplift)

**Branch**: `sprint-q-2-cal-expinf-gb-boe-ilg-spf`
**Worktree**: `/home/macro/projects/sonar-wt-q-2-cal-expinf-gb-boe-ilg-spf`
**Data**: Week 11 Day 1 — target arranque ~14:30 WEST (paralelo com Sprint P)
**Operator**: Hugo Condesa + CC
**Budget**: 3-4h
**Priority**: **P1** — 1-country M3 FULL uplift (GB)
**ADR-0010 tier scope**: T1
**Brief format**: v3.3
**Systemd services affected**: `sonar-daily-monetary-indices.service` — GB M3 DEGRADED → FULL expected
**Parent**: Sprint Q.1.2 shipped (EXPINF wiring complete EA). Sprint Q.2 replicates pattern for GB via BoE.

---

## §1 Scope (why)

### Problem

GB M3 currently DEGRADED — flag `M3_EXPINF_MISSING`. No BoE connector shipped for inflation expectations. 6 per-country EXPINF CALs opened Sprint Q retro; Q.2 targets GB-BOE-ILG-SPF.

### Objectivo

Ship BoE connector extension for GB expected inflation data:
- **Primary source**: BoE Inflation-Linked Gilts (ILG) breakeven inflation — market-implied
- **Secondary source**: BoE SPF-equivalent (Monetary Policy Report forecasts OR BoE Survey of External Forecasters)

Populate `exp_inflation_bei` (ILG) and/or `exp_inflation_survey` (SPF-equivalent) for GB. Extend `db_backed_builder` loader to read GB path. Apply **Lesson #20 iteration #5 from start** — extend BOTH `build_m3_inputs_from_db` AND `_load_histories` helper in same sprint.

### Expected impact

- M3 runtime: 6/12 → 7/12 FULL (+1 country GB)
- T1 overall: ~68-70% → ~70-71% (+1-2pp)

---

## §2 Spec (what)

### 2.1 Pre-flight probe (MANDATORY — ADR-0009 v2 analog for EXPINF sources)

#### 2.1.1 BoE data sources discovery

```bash
cd /home/macro/projects/sonar-wt-q-2-cal-expinf-gb-boe-ilg-spf
source .env

# BoE has Statistical Interactive Database (IADB) — REST API
curl -s "https://www.bankofengland.co.uk/boeapps/database/fromshowcolumns.asp?Travel=NIxSTx&FromSeries=1&ToSeries=50&DAT=RNG&FD=1&FM=Jan&FY=2020&TD=24&TM=Apr&TM=Jul&TY=2026&VFD=Y&CSVF=TT&html.x=35&html.y=16&SeriesCodes=IUMABEDR&UsingCodes=Y&Filter=N&title=IUMABEDR&VPD=Y" 2>&1 | head -20

# Alternative — BoE Database query interface
curl -s "https://www.bankofengland.co.uk/boeapps/iadb/rates.asp" 2>&1 | head -30

# ILG-specific series — check BoE statistical releases
# Series likely IUDLUN25 (UK implied BEI 10Y), IUDVG025 (UK nominal yield), etc
```

#### 2.1.2 ILG breakeven data availability

**Hypothesis**: BoE publishes **yield curves** (nominal + real) daily. Breakeven = nominal - real. Series candidates:
- `IUDLUN25` — 10Y nominal zero-coupon yield
- `IUDLRN25` (or similar) — 10Y real zero-coupon yield (inflation-indexed gilts)
- `IUDAMIH` — 5Y5Y implied inflation forward

Probe each:
```bash
for series in IUDLUN25 IUDLRN25 IUDAMIH IUDLG25; do
  echo "=== $series ==="
  curl -s "https://www.bankofengland.co.uk/boeapps/iadb/fromshowcolumns.asp?csv.x=yes&CodeVer=new&SeriesCodes=${series}&UsingCodes=Y&FD=1&FM=Jan&FY=2020&TD=24&TM=Apr&TY=2026" 2>&1 | head -5
done
```

Document findings in `docs/backlog/probe-results/sprint-q-2-boe-ilg-spf-probe.md`:
- Which series have data
- Historical depth (required for `_load_histories` baseline ≥ 2 rows per Lesson #20 #5)
- Tenor coverage (10Y minimum; 5Y + 30Y + 5Y5Y ideal)
- Data quality (daily vs weekly/monthly)

#### 2.1.3 BoE SPF-equivalent

BoE publishes:
- **Monetary Policy Report (MPR)** quarterly with inflation forecasts — PDF primarily
- **Survey of External Forecasters (SEF)** — quarterly, inflation expectations

Probe API availability:
```bash
# Check if BoE exposes SEF via API
curl -s "https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes/2025/november-2025/mpc-summary-nov-2025" | head -5
curl -s "https://www.bankofengland.co.uk/-/media/boe/files/statistics/mfs.json" 2>&1 | head -10
```

**Fallback**: if BoE SEF not API-exposed, ship ILG breakeven only. GB M3 FULL via BEI source (similar to US canonical path).

#### 2.1.4 Lesson #20 #5 application — from start

**Critical**: identify ALL helper functions that Sprint Q.2 must extend:

```bash
grep -rn "_query_expinf\|_query_survey\|_load_histories\|_query_bei\|expinf_row\|EXPINF_CANONICAL" \
  src/sonar/indices/monetary/db_backed_builder.py | head -20
```

For each helper touching expinf data:
- Does it read `IndexValue(EXPINF_CANONICAL)` only? → extend to also read `exp_inflation_bei`
- Does it read `exp_inflation_survey` only? → also extend if GB BEI path
- History loading — `_load_histories` needs same fallback extended to BEI

Document in audit (§2.1 deliverable) the full list of functions to touch.

### 2.2 BoE connector

**File**: `src/sonar/connectors/boe_iadb.py` (new OR extend existing)

```python
class BoeIadbConnector:
    """Bank of England Interactive Statistical Database (IADB) connector.

    Fetches time series via the CSV export endpoint.
    Sprint Q.2 scope: ILG breakeven + optional SEF inflation expectations.
    """

    async def fetch_bei_observations(
        self,
        tenor: Literal["5Y", "10Y", "30Y", "5Y5Y"],
        date_start: date,
        date_end: date,
    ) -> list[BeiObservation]:
        """Fetch ILG-implied breakeven inflation for tenor."""
        # CSV URL pattern: ...?CodeVer=new&SeriesCodes=<code>&FD=...&TD=...
        # Parse CSV response, return observations
```

### 2.3 Writer for exp_inflation_bei

**File**: `src/sonar/indices/monetary/exp_inflation_writers.py` (Q.1 shipped survey writer, extend for BEI)

```python
async def persist_bei_row(
    country_code: str,
    date: date,
    observations: list[BeiObservation],
    session: Session,
) -> int:
    """Persist BEI observations to exp_inflation_bei table."""
```

Mirror Q.1 writer pattern. Idempotent per ADR-0011 P1.

### 2.4 Loader integration — Lesson #20 #5 applied

**File**: `src/sonar/indices/monetary/db_backed_builder.py`

Extend BOTH functions **in same commit**:

1. **`build_m3_inputs_from_db` main function**:
   - After canonical check → after survey check → add BEI fallback branch
   - For GB: `_query_bei(session, country_code, date)` → extract tenor map → return M3Inputs

2. **`_load_histories` helper**:
   - Current: canonical IndexValue + survey fallback (Q.1.2)
   - Extend: also BEI fallback from `exp_inflation_bei`
   - Forward-fill pattern same as Q.1.2

3. **New helper**: `_query_bei`, `_bei_tenors_bps` mirroring Q.1.1 survey helpers.

### 2.5 Backfill + verify

```bash
# Backfill BEI 2020-2026 GB
uv run python -m sonar.connectors.boe_iadb.backfill_bei --country GB --date-start 2020-01-01 --date-end 2026-04-24

# Verify
sqlite3 data/sonar-dev.db \
  "SELECT country_code, COUNT(*), MIN(date), MAX(date) FROM exp_inflation_bei WHERE country_code='GB' GROUP BY country_code;"

# Re-run GB M3
for date in 2026-04-21 2026-04-22 2026-04-23; do
  uv run python -m sonar.pipelines.daily_monetary_indices --country GB --date $date
done

# Verify GB M3 FULL
uv run python -m sonar.pipelines.daily_monetary_indices --country GB --date 2026-04-23 2>&1 | \
  grep "m3_compute_mode.*country=GB"
# Expected: mode=FULL, flags include M3_EXPINF_FROM_BEI
```

### 2.6 Tests

```python
def test_boe_connector_fetches_bei_10y(mock_boe_iadb):
    """Sprint Q.2: BoE IADB CSV parsing for 10Y BEI."""

def test_expinf_bei_writer_persists_gb(test_session):
    """Sprint Q.2: BEI writer persists GB rows idempotently."""

def test_load_histories_bei_fallback_when_canonical_and_survey_empty(test_session, gb_bei_fixtures):
    """Sprint Q.2 Lesson #20 #5: _load_histories extends to BEI fallback."""

def test_build_m3_inputs_gb_bei_path(test_session, gb_bei_fixtures):
    """Sprint Q.2: GB M3 resolves FULL via BEI path."""

def test_us_regression_unchanged(test_session, us_fixtures):
    """Sprint Q.2: US canonical path unchanged."""
```

---

## §3 Commits plan

| # | Scope | Files |
|---|---|---|
| C1 | docs(probes): BoE IADB ILG + SEF probe results | `docs/backlog/probe-results/sprint-q-2-boe-ilg-spf-probe.md` |
| C2 | feat(connectors): BoE IADB BEI fetch | `src/sonar/connectors/boe_iadb.py` |
| C3 | feat(indices): exp_inflation_bei writer + db_backed_builder main + _load_histories BEI fallback | `src/sonar/indices/monetary/exp_inflation_writers.py`, `db_backed_builder.py` |
| C4 | test: BoE connector + BEI writer + loader + _load_histories + US regression | `tests/...` |
| C5 | ops: backfill GB BEI 2020-2026 + M3 verify | no commit |
| C6 | docs(backlog): CAL-EXPINF-GB-BOE-ILG-SPF closure + potential sub-CALs | `docs/backlog/calibration-tasks.md` |
| C7 | docs(planning): Sprint Q.2 retrospective | `docs/planning/retrospectives/week11-sprint-q-2-cal-expinf-gb-boe-ilg-spf-report.md` |

---

## §4 HALT triggers

**HALT-0**:
- BoE IADB CSV export not accessible via scripted HTTP (e.g., requires session cookie) → HALT, open `CAL-EXPINF-GB-SCRAPE` for Week 12+ alternative
- ILG series absent OR insufficient history (<60 observations for baseline) → HALT, escalate

**HALT-material**:
- Lesson #20 #5 not applied (extending only main func, not `_load_histories`) → Sprint Q.1.1 pattern recurrence. MUST extend both in same commit.
- US regression break → STOP
- Sprint P conflict (unlikely, different files) → coordinate merge order

**HALT-scope**:
- Temptation to ship BoE SEF if ILG works → STOP, ship ILG only, open SEF sub-CAL
- Temptation to fix EA periphery BEI linkers → STOP (separate CALs)
- Temptation to touch `live_assemblers` → STOP (db_backed path only)

---

## §5 Acceptance

### Tier A
1. Probe doc shipped (BoE IADB availability + series list)
2. BoE connector BEI fetch method
3. `exp_inflation_bei` GB rows populated (≥ 60 observations baseline)
4. `db_backed_builder` extended BOTH main AND `_load_histories` (Lesson #20 #5)
5. Local CLI: GB `m3_compute_mode.*mode=FULL` + `flags=M3_EXPINF_FROM_BEI`
6. US regression unchanged (canonical path)
7. Pre-commit clean double-run

### Tier B
1. Systemd verify — GB M3 FULL persist
2. DB verify:
   ```bash
   sqlite3 data/sonar-dev.db \
     "SELECT country_code, date, COUNT(*) FROM monetary_m1_effective_rates WHERE country_code='GB' AND date='2026-04-23';"
   ```
   Expected: row persisted
3. M3 mode breakdown: 7 FULL (was 6), 2 DEGRADED (JP + CA), 3 NOT_IMPLEMENTED

---

## §6 Retro scope

- M3 matrix pre/post (6 → 7 FULL)
- Lesson #20 #5 applied from start — meta-validation of pattern
- BoE connector pattern (ILG BEI vs ECB SPF survey) — document differences
- Coverage delta
- Sprint Q.3 candidates (JP Tankan, CA BoC survey) next

---

## §7 Execution notes
- Probe-first discipline (§2.1) mandatory before connector code
- Lesson #20 #5: extend BOTH `build_m3_inputs_from_db` AND `_load_histories` in same commit
- BoE IADB CSV may need user-agent header OR specific date format — document quirks
- Paralelo Sprint P — zero file overlap (P = MSC aggregator, Q.2 = BoE connector + loader extension)
- Pre-commit double-run, sprint_merge.sh Step 10, DB symlink, filename compliant
- Pre-stage pre-commit (Lesson #16)

---

## §8 Dependencies & CAL interactions

### Parent
Sprint Q.1.2 — `_load_histories` survey fallback shipped, pattern reference

### CAL closed
- `CAL-EXPINF-GB-BOE-ILG-SPF` primary deliverable

### CAL potentially opened
- `CAL-EXPINF-GB-SEF` if ILG-only shipped (SEF deferred Week 12+)
- `CAL-EXPINF-GB-SCRAPE` if API HALT-0

### Sprints unblocked
- Sprint Q.3 (JP Tankan + CA BoC surveys) — pattern reference
- Sprint P.1 (MSC GB) — post-Q.2 ship, GB M3 FULL operational

---

## §9 Time budget
Arranque ~14:30 WEST. Hard stop 18:30 WEST (4h).
- Best 2.5h: BoE IADB clean CSV, ILG series accessible, thin connector
- Median 3.5h: quirks (date format, series codes, history depth)
- Worst 4h HALT-0: BoE API inaccessible → open scrape CAL

---

*End brief. GB M3 FULL via BoE BEI. Ship with Lesson #20 #5 applied from start.*
