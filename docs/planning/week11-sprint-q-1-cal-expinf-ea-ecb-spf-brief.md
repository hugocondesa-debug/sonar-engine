# Sprint Q.1 — CAL-EXPINF-EA-ECB-SPF (EA Survey Leg Shipping for 6-Country M3 FULL Cascade)

**Branch**: `sprint-q-1-cal-expinf-ea-ecb-spf`
**Worktree**: `/home/macro/projects/sonar-wt-q-1-cal-expinf-ea-ecb-spf`
**Data**: Week 11 Day 1 (2026-04-24) — target arranque ~14:15 WEST
**Operator**: Hugo Condesa (reviewer) + CC (executor, full autonomy per SESSION_CONTEXT)
**Budget**: 3-5h solo
**Priority**: **P0** — highest leverage EXPINF connector shipment (single extension → 6 countries M3 FULL cascade)
**ADR-0010 tier scope**: T1 ONLY
**ADR-0009 v2.2 TE Path 1 probe**: N/A (ECB SDW — not TE)
**Brief format**: v3.3 (Tier A / Tier B + filename convention compliance)
**Systemd services affected**: `sonar-daily-monetary-indices.service` (expected 6 countries M3 DEGRADED → FULL via survey source)
**Parent**: Sprint Q retro §7 — CAL-EXPINF-EA-ECB-SPF flagged as highest-leverage per-country CAL

---

## §1 Scope (why)

### Sprint Q retro context

Sprint Q (Week 11 Day 1 AM) shipped EXPINF wiring pattern canonical. Result: US M3 DEGRADED → FULL via live FRED BEI + survey composition. 8 other T1 countries stayed DEGRADED because EXPINF tables dormant (schema only, no writers).

Sprint Q retro §7 opened 6 per-country EXPINF CALs, ranked by leverage:

| CAL | Countries impacted | Leverage |
|---|---|---|
| **CAL-EXPINF-EA-ECB-SPF** | **EA + DE + FR + IT + ES + PT (6 countries)** | **HIGHEST** |
| CAL-EXPINF-GB-BOE-ILG-SPF | GB (1 country) | Medium |
| CAL-EXPINF-DE-BUNDESBANK-LINKER | DE only (overlaps CAL-EXPINF-EA-ECB-SPF) | Low |
| CAL-EXPINF-FR-BDF-OATI-LINKER | FR only (overlaps) | Low |
| CAL-EXPINF-EA-PERIPHERY-LINKERS | IT + ES (overlaps) | Low |
| CAL-EXPINF-SURVEY-JP-CA | JP + CA (2 countries) | Medium |

**Sprint Q.1 targets CAL-EXPINF-EA-ECB-SPF**: single ECB SDW connector extension publishes SPF (Survey of Professional Forecasters) inflation expectations for Euro Area aggregate. Data may be decomposable per-country OR usable as shared "euro area SPF" source for all 6 EA members.

### ECB SPF background

ECB publishes Survey of Professional Forecasters quarterly. Forecasters polled on euro-area-wide inflation expectations at various horizons (1y / 2y / 5y). Data disseminated via:
- ECB Statistical Data Warehouse (SDW) — primary source, REST API
- ECB Data Portal (successor to SDW, newer UI)
- PDF reports (human-readable)

**Sprint Q.1 hypothesis**: ECB SDW exposes SPF via a dataflow (likely `SPF` or `ECB_SURVEY` or embedded in a broader `EIN` exp-inflation dataflow). Probe first; connector extension predicated on empirical confirmation.

### Expected impact

If SPF data available + usable per-country (EA aggregate applied to EA members):
- **EA aggregate**: M3 DEGRADED → FULL (survey source)
- **DE, FR, IT, ES, PT**: M3 DEGRADED → FULL via shared-EA-survey proxy
- **6 countries M3 FULL** from single sprint
- **T1 overall**: ~58% → ~68-70% (+10-12pp)
- **Sprint P MSC EA** (L4 first cross-country) truly unblocked immediately after

---

## §2 Spec (what)

### 2.1 Pre-flight probe (MANDATORY before code)

CC must complete ECB SDW SPF probe and document findings in `docs/backlog/probe-results/sprint-q-1-ecb-spf-probe.md` (new):

#### 2.1.1 SDW dataflow discovery

```bash
cd /home/macro/projects/sonar-engine
source .env

# Try common SPF dataflow identifiers
for dataflow in SPF ECB_SURVEY EIN BSI_IND SPF_IND; do
  echo "=== Probing dataflow: $dataflow ==="
  curl -s -H "Accept: application/json" \
    "https://data-api.ecb.europa.eu/service/dataflow/ECB/${dataflow}" 2>&1 | \
    jq '.Dataflow.name // .ErrorReport // .errors' 2>/dev/null | head -5
done
```

Expected: at least one dataflow returns 200 with metadata. If all 404 → fallback to `GET /dataflow` listing:

```bash
curl -s "https://data-api.ecb.europa.eu/service/dataflow/ECB" | \
  jq '.[] | select(.name | test("survey|forecaster|SPF|inflation"; "i")) | {id, name}' | head -30
```

#### 2.1.2 SPF series structure (if dataflow found)

Once dataflow identified, probe series:

```bash
# Example for hypothetical SPF dataflow
curl -s "https://data-api.ecb.europa.eu/service/data/SPF/M.U2.N.ICP.PY1Y?format=jsondata&lastNObservations=5" | \
  jq '.dataSets[0].series'
```

Document series key structure:
- Frequency (quarterly most likely)
- Geographic dimension (U2 = euro area — per-country?)
- Tenor dimension (1Y / 2Y / 5Y / LTE long-term expectations)
- Measurement dimension (point / median / mean / distribution percentiles)

#### 2.1.3 Expected inflation series shortlist

Identify specific series keys for:
- **1-year ahead inflation expectation** — primary M3 input (matches US survey shortest horizon)
- **2-year ahead inflation expectation** — secondary
- **5-year ahead / long-term** — tertiary (optional)

Document each series key + URL + sample response.

#### 2.1.4 Per-country feasibility

Key question: does SPF publish per-country (DE/FR/IT/ES) OR only EA aggregate?

- **If per-country**: Sprint Q.1 ships true per-country survey — 6 countries M3 FULL individual
- **If EA aggregate only**: Sprint Q.1 ships EA-aggregate survey shared to 5 EA members — 6 countries M3 FULL via shared proxy (still high leverage)

Document finding. If EA-aggregate only, add DEGRADED `survey_source_is_area_proxy` flag to per-country M3 emit for transparency.

### 2.2 Connector extension — `ecb_sdw.py`

**File**: `src/sonar/connectors/ecb_sdw.py`

Add new method:

```python
async def fetch_survey_expected_inflation(
    self,
    country: str,
    date_start: date,
    date_end: date,
    tenor: Literal["1Y", "2Y", "5Y", "LTE"] = "1Y",
) -> list[ExpInflationSurveyObservation]:
    """
    Fetch Survey of Professional Forecasters (SPF) inflation expectations from ECB SDW.

    If country='EA' or an EA member (DE/FR/IT/ES/PT/NL/...), returns EA-aggregate
    SPF series (per §2.1.4 probe finding — if per-country available, returns that).

    Returns list of observations with:
      - date (quarterly observation date)
      - value (annual % expectation, decimal form)
      - tenor (1Y/2Y/5Y/LTE)
      - source_flag ('ecb_sdw_spf_area' | 'ecb_sdw_spf_country')
    """
    # ECB SDW REST API call
    # URL pattern: https://data-api.ecb.europa.eu/service/data/<dataflow>/<key>?...
    # Parse SDMX-JSON response
    # Return structured observations
```

Dataclass:
```python
@dataclass
class ExpInflationSurveyObservation:
    date: date
    value: float   # annual %, decimal (e.g., 0.021 = 2.1%)
    tenor: str     # '1Y' / '2Y' / '5Y' / 'LTE'
    source: str    # 'ecb_sdw_spf_area' | 'ecb_sdw_spf_country'
    flags: list[str]
```

### 2.3 Writer for exp_inflation_survey table

**Sprint Q audit revealed table dormant**. Sprint Q.1 ships first writer.

File candidate: `src/sonar/indices/monetary/exp_inflation_writers.py` (new) OR extend existing `exp_inflation_loader.py`.

```python
async def write_survey_observations(
    country: str,
    observations: list[ExpInflationSurveyObservation],
    session: Session,
) -> int:
    """
    Persist SPF observations to exp_inflation_survey table.
    Idempotent per ADR-0011 Principle 1 (row-level upsert).
    Returns rows written count.
    """
```

Upsert pattern:
- Unique key: `(country_code, date, tenor, source)`
- Skip if duplicate, log `writer.duplicate_skipped`
- Insert new rows with `inserted_at=now()`

### 2.4 Loader integration

**File**: `src/sonar/indices/monetary/exp_inflation_loader.py` (Sprint Q shipped)

Current state (post-Sprint-Q):
```python
def load_canonical_exp_inflation(country, date, session):
    # Fallback hierarchy:
    # 1. exp_inflation_canonical
    # 2. exp_inflation_derived
    # 3. exp_inflation_bei
    # 4. exp_inflation_swap
    # 5. exp_inflation_survey  ← Sprint Q.1 populates this
```

Extension (maybe minimal — fallback already handles survey):
- Ensure survey path returns `ExpInflationInput` with `source='survey'`, `tenor='1Y'`, `flags` including `AREA_PROXY` if country ≠ 'EA' and source is EA-aggregate

### 2.5 Live assembler factory wiring

**File**: `src/sonar/overlays/live_assemblers.py` (Sprint Q shipped)

Current state: FRED added to LiveConnectorSuite for US. Sprint Q.1 adds ECB SDW:

```python
class LiveConnectorSuite:
    def __init__(self, fred: FredConnector, ecb_sdw: Optional[ECBSDWConnector] = None, ...):
        self.fred = fred
        self.ecb_sdw = ecb_sdw  # NEW Sprint Q.1
```

**File**: `src/sonar/pipelines/daily_overlays.py` — factory passes `ecb_sdw` when country in EA cohort.

### 2.6 Backfill + verify

Post-code ship, backfill SPF observations:

```bash
# Backfill last 12 quarters of SPF (3 years)
uv run python -m sonar.connectors.ecb_sdw.backfill_spf --date-start 2023-01-01 --date-end 2026-04-24

# Verify writes
sqlite3 data/sonar-dev.db \
  "SELECT country_code, tenor, source, COUNT(*) FROM exp_inflation_survey GROUP BY country_code, tenor, source;"

# Re-run M3 for all 6 countries + backfill Apr 21-24
for date in 2026-04-21 2026-04-22 2026-04-23 2026-04-24; do
  uv run python -m sonar.pipelines.daily_monetary_indices --all-t1 --date $date
done

# Verify M3 FULL promotion
sqlite3 data/sonar-dev.db \
  "SELECT country_code, date, mode FROM monetary_m3 WHERE country_code IN ('EA','DE','FR','IT','ES','PT') AND date='2026-04-23' ORDER BY country_code;"
```

Expected post-Q.1: EA + DE + FR + IT + ES + PT rows with `mode=FULL` for date 2026-04-23.

### 2.7 Tests

**File**: `tests/unit/test_connectors/test_ecb_sdw.py` — extend:

```python
async def test_fetch_survey_expected_inflation_ea_aggregate(mock_ecb_sdw):
    """Sprint Q.1: EA aggregate SPF 1Y retrieval."""
    # Mock SDW response with 5 quarterly observations
    # Assert returns 5 ExpInflationSurveyObservation
    # Assert source='ecb_sdw_spf_area', tenor='1Y'

async def test_fetch_survey_per_country_ea_member(mock_ecb_sdw):
    """Sprint Q.1: EA member (e.g., DE) receives EA-aggregate survey with AREA_PROXY flag."""

async def test_fetch_survey_missing_dataflow_halt(mock_ecb_sdw_missing):
    """Sprint Q.1: SDW returns 404 for dataflow → graceful error with CAL reference."""
```

**File**: `tests/unit/test_pipelines/test_expinf_wiring.py` — extend:

```python
def test_m3_full_promotion_ea_members_via_spf(mock_ecb_sdw_spf_populated, test_session):
    """Sprint Q.1: 5 EA members (DE/FR/IT/ES/PT) + EA M3 FULL post survey population."""
```

### 2.8 CAL-EXPINF-EA-ECB-SPF closure

`docs/backlog/calibration-tasks.md`:

```markdown
### CAL-EXPINF-EA-ECB-SPF — **CLOSED (Sprint Q.1, 2026-04-24)**

- **Outcome**: Shipped ECB SDW SPF connector extension. 6 countries (EA + DE + FR + IT + ES + PT) M3 DEGRADED → FULL via survey source.
- **Method**: <per probe finding — per-country OR EA-aggregate proxy>
- **Data coverage**: SPF quarterly 2023-Q1 to 2026-Q1 backfilled
- **Related**: ADR-0011 Principle 1 (idempotent writer), Sprint Q (parent EXPINF wiring)
```

---

## §3 Commits plan

| Commit | Scope | Ficheiros |
|---|---|---|
| **C1** | docs(probes): Sprint Q.1 ECB SDW SPF probe results | `docs/backlog/probe-results/sprint-q-1-ecb-spf-probe.md` (new) |
| **C2** | feat(connectors): ECB SDW SPF extension | `src/sonar/connectors/ecb_sdw.py` |
| **C3** | feat(indices): exp_inflation_survey writer + loader integration | `src/sonar/indices/monetary/exp_inflation_writers.py` (new) + `exp_inflation_loader.py` extension |
| **C4** | refactor(overlays,pipelines): live_assemblers + daily_overlays ECB SDW wiring | `src/sonar/overlays/live_assemblers.py` + `src/sonar/pipelines/daily_overlays.py` |
| **C5** | test: ECB SDW SPF + M3 FULL EA cascade | `tests/unit/test_connectors/test_ecb_sdw.py` + `tests/unit/test_pipelines/test_expinf_wiring.py` |
| **C6** | ops: backfill SPF 2023-Q1 to 2026-Q1 + 6-country M3 verify | (ops only, no commit) |
| **C7** | docs(backlog): CAL-EXPINF-EA-ECB-SPF CLOSED + potentially new sub-CALs | `docs/backlog/calibration-tasks.md` |
| **C8** | docs(planning): Sprint Q.1 retrospective + M3 coverage matrix | `docs/planning/retrospectives/week11-sprint-q-1-cal-expinf-ea-ecb-spf-report.md` |

---

## §4 HALT triggers

**HALT-0**:
- **SDW SPF dataflow not exposed via API** — §2.1.1 probe returns 404 for all candidate dataflows and `/dataflow` listing shows no survey-related dataflow. Fallback: document finding, close Sprint Q.1 as HALT-0, open `CAL-EXPINF-EA-ECB-SPF-SCRAPE` (ECB Data Portal web scrape OR PDF extraction) Week 11 Day 3+.
- **SPF series empty or stale (>3 months)** — fetch succeeds but no observations 2024+ → HALT, document, open re-probe CAL.

**HALT-material**:
- **SPF series in SDMX-ML format only (no SDMX-JSON)** — connector must extend XML parser. Scope grow +2h; if budget insufficient, HALT + defer to Sprint Q.1-continuation.
- **Per-country series exists but uses SDW country codes incompatible with SONAR country codes** — mapping table required. Minor scope expansion OK (~30min).
- **Writer upsert logic conflicts with existing schema constraints** — schema amendment required. STOP, investigate.

**HALT-scope**:
- Temptation to ship BEI linker for IT/ES (CAL-EXPINF-EA-PERIPHERY-LINKERS) → STOP (future sprint).
- Temptation to ship Bundesbank BEI (CAL-EXPINF-DE-BUNDESBANK-LINKER) → STOP.
- Temptation to extend to JP/CA surveys → STOP (CAL-EXPINF-SURVEY-JP-CA separate).
- Temptation to add SPF to cost_of_capital or other pipelines → STOP (monetary M3 only).

**HALT-security**: standard.

---

## §5 Acceptance

### Tier A — pre-merge (CC scope, v3.3 compliance)

1. **Probe doc shipped**:
   ```bash
   test -f docs/backlog/probe-results/sprint-q-1-ecb-spf-probe.md && \
     wc -l docs/backlog/probe-results/sprint-q-1-ecb-spf-probe.md
   ```
   Expected: ≥50 lines with per-country SPF feasibility finding.

2. **Connector extension shipped**:
   ```bash
   grep "def fetch_survey_expected_inflation" src/sonar/connectors/ecb_sdw.py
   ```

3. **Writer shipped**:
   ```bash
   grep -rn "def write_survey_observations\|exp_inflation_survey" src/sonar/indices/monetary/ | head -5
   ```

4. **SPF DB rows populated** (post C6 backfill):
   ```bash
   sqlite3 data/sonar-dev.db \
     "SELECT country_code, COUNT(*) FROM exp_inflation_survey GROUP BY country_code;"
   ```
   Expected: EA + 5 EA members (or EA only with AREA_PROXY flag), ≥8 obs each (8 quarters × 3 years baseline).

5. **Local CLI — M3 FULL emit for EA cohort**:
   ```bash
   uv run python -m sonar.pipelines.daily_monetary_indices --all-t1 --date 2026-04-23 2>&1 | \
     grep "m3_compute_mode" | grep "FULL" | wc -l
   ```
   Expected: ≥2 (US + EA minimum; realistically 6-7 if per-country shipped).

6. **Bash wrapper smoke** (Lesson #12 Tier A):
   ```bash
   bash -lc 'uv run python -m sonar.pipelines.daily_monetary_indices --all-t1 --date 2026-04-23'
   ```
   Expected: exit 0, n_failed=0.

7. **Regression suite**:
   ```bash
   uv run pytest tests/ -x --tb=short
   ```
   Expected: all pass.

8. **Pre-commit clean double-run** (Lesson #2).

### Tier B — post-merge (operator scope)

1. **Systemd 6-country M3 FULL emit**:
   ```bash
   sudo systemctl reset-failed sonar-daily-monetary-indices.service
   sudo systemctl start sonar-daily-monetary-indices.service
   sleep 120
   sudo journalctl -u sonar-daily-monetary-indices.service --since "-3 min" --no-pager | \
     grep "m3_compute_mode" | grep -oE "mode=[A-Z_]+" | sort | uniq -c
   ```
   Expected: 6-7 FULL (US + EA + 5 EA members), 2-3 DEGRADED (GB + JP + CA), 3 NOT_IMPLEMENTED (PT if survey not covered + NL + AU).

2. **Summary clean**:
   ```bash
   sudo journalctl -u sonar-daily-monetary-indices.service --since "-3 min" --no-pager | \
     grep "monetary_pipeline.summary"
   ```
   Expected: n_failed=0.

3. **Zero event-loop errors** (ADR-0011 P6 holds).

4. **DB matrix verify**:
   ```bash
   sqlite3 data/sonar-dev.db \
     "SELECT country_code, mode FROM monetary_m3 WHERE date='2026-04-23' AND country_code IN ('US','EA','DE','FR','IT','ES','PT','GB','JP','CA') ORDER BY country_code;"
   ```
   Expected: US/EA/DE/FR/IT/ES FULL, GB/JP/CA DEGRADED, PT context-dependent.

---

## §6 Retro scope

Documentar em `docs/planning/retrospectives/week11-sprint-q-1-cal-expinf-ea-ecb-spf-report.md`:

### M3 coverage matrix (pre/post-Q.1)

| Country | Pre-Q.1 | Post-Q.1 | EXPINF source |
|---|---|---|---|
| US | FULL (Sprint Q) | FULL (unchanged) | FRED BEI + survey |
| EA | DEGRADED | FULL | ECB SDW SPF |
| DE | DEGRADED | FULL / DEGRADED | EA proxy / own |
| FR | DEGRADED | FULL / DEGRADED | EA proxy / own |
| IT | DEGRADED | FULL / DEGRADED | EA proxy / own |
| ES | DEGRADED | FULL / DEGRADED | EA proxy / own |
| PT | NOT_IMPLEMENTED | FULL / NOT_IMPLEMENTED | EA proxy / own |
| GB | DEGRADED | DEGRADED | (awaits Sprint Q.2) |
| JP | DEGRADED | DEGRADED | (awaits Q.3) |
| CA | DEGRADED | DEGRADED | (awaits Q.3) |

### T1 coverage delta

- Pre-Q.1: ~58%
- Post-Q.1 projection: ~68-72% (+10-14pp via 6-country M3 FULL cascade)
- Phase 2 fim Maio 75-80% target: comfortable

### Sprint Q retro continuation

Sprint Q.1 is first of 6 connector-shipping sprints sequence opened by Sprint Q retro. Each subsequent CAL-EXPINF-X brings +1-2 countries. Validates pattern: Sprint Q architectural unblock → Sprint Q.X targeted connector shipping.

### ADR-0011 Principle 8 candidate revisit

If Sprint Q.1 surfaces new architectural pattern (e.g., "survey source shared across currency union members" as canonical design), document as potential ADR amendment.

### Week 11 Day 1 end state

- 3 sprints shipped (Q + Q.0.5 + Q.1)
- T1 ~68-70%
- L4 composite (MSC EA) unblocked for Day 2 AM

---

## §7 Execution notes

- **Probe-first discipline** (ADR-0009 v2 mandatory analog) — C1 probe BEFORE C2 code
- **Budget hard cap 5h**. If SDW integration proves complex (SDMX-ML parsing), ship C1-C3 and defer C4-C5 to Sprint Q.1-continuation
- **Pattern reusable**: ECB SDW survey → `exp_inflation_survey` writer pattern may extend to Sprint Q.3 JP Tankan, Sprint Q.4 CA BoC survey
- **AREA_PROXY flag transparency**: if shipping EA-aggregate to members, each per-country M3 emit should carry flag for analyst transparency
- **Pre-commit double-run** (Lesson #2)
- **sprint_merge.sh Step 10** cleanup (Lesson #4)
- **CC arranque template** (Lesson #5) — apply
- **DB symlink** auto-provisioned (Lesson #14)
- **Brief filename** Lesson #15 compliant
- **Pre-stage pre-commit** before git add (Lesson #16 Day 3 prevention)

---

## §8 Dependencies & CAL interactions

### Parent sprint
Sprint Q (Week 11 Day 1 AM) — EXPINF wiring pattern shipped + CAL-EXPINF-EA-ECB-SPF opened highest leverage

### CAL items closed by this sprint
- **CAL-EXPINF-EA-ECB-SPF** (primary deliverable)
- Potentially partial closure of CAL-EXPINF-DE-BUNDESBANK-LINKER, CAL-EXPINF-FR-BDF-OATI-LINKER, CAL-EXPINF-EA-PERIPHERY-LINKERS if AREA_PROXY approach suffices

### CAL items potentially opened by this sprint
- `CAL-EXPINF-PER-COUNTRY-LINKERS-FOLLOWUP` — if AREA_PROXY only, flag for per-country upgrade (BEI/linker-based) Week 12+ scope
- `CAL-ECB-SDW-SDMX-ML-PARSER` — if SDMX-ML encountered, document parser extension debt

### Sprints blocked by this sprint
- **None blocking** — Sprint Q.1 is unblocker, not blocked

### Sprints unblocked by this sprint
- **Sprint P (MSC EA)** — EA M3 FULL post-Q.1 = MSC EA L4 composite truly feasible Day 2 AM
- **Sprint Q.2 (GB-BOE-ILG-SPF)** — pattern reference for BoE SPF shipping
- **Sprint M2-EA-per-country** — M3 FULL cascade unlocks per-country MSC DE/FR/IT/ES sequences Day 3+

---

## §9 Time budget

Arranque target: Day 1 ~14:15 WEST (post-Q.0.5 Tier B verify).
Hard stop: 19:00 WEST (5h wall-clock, Day 1 close buffer).

Realistic range:
- **Best case 3h**: SDW probe clean, SDMX-JSON available, per-country or clean AREA_PROXY, wiring trivial
- **Median 4-5h**: SDW probe finds nuances (tenor mapping, frequency handling), some backfill complications
- **Worst case HALT-0**: SDW doesn't expose SPF via API → close Sprint Q.1 early, open scrape-based alternative CAL

---

*End of brief. Highest-leverage EXPINF connector shipping. 6-country M3 FULL cascade if ships clean.*
