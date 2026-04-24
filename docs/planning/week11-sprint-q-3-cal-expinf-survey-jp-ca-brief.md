# Sprint Q.3 — CAL-EXPINF-SURVEY-JP-CA (JP Tankan + CA BoC M3 FULL Uplift)

**Branch**: `sprint-q-3-cal-expinf-survey-jp-ca`
**Worktree**: `/home/macro/projects/sonar-wt-q-3-cal-expinf-survey-jp-ca`
**Data**: Week 11 Day 1 — target arranque ~15:15 WEST
**Operator**: Hugo Condesa + CC
**Budget**: 3-4h
**Priority**: **P1** — 2-country M3 FULL uplift (JP + CA)
**ADR-0010 tier scope**: T1
**Brief format**: v3.3
**Systemd services affected**: `sonar-daily-monetary-indices.service` — JP + CA M3 DEGRADED → FULL expected
**Parent**: Sprint Q.2 shipped (6 cascade sites identified: canonical/survey/BEI × 3 consumer paths). Sprint Q.3 applies Lesson #20 #6 from start.

---

## §1 Scope (why)

### Problem

JP + CA M3 currently DEGRADED. Flags `M3_EXPINF_MISSING`. No connector shipped for JP/CA inflation expectations.

### Target data sources

**JP — Tankan Survey (Bank of Japan)**:
- Quarterly enterprise survey, published BoJ
- Contains firms' expected inflation (1Y, 3Y, 5Y horizons)
- Public access via BoJ statistics portal

**CA — BoC Business Outlook Survey (BOS)**:
- Quarterly business survey, Bank of Canada
- Contains inflation expectations
- Public access via BoC website

### Hypothesis

Both sources are **quarterly surveys** analogous to ECB SPF — Sprint Q.1 pattern applies. Differences:
- JP Tankan: likely JSON/CSV via BoJ statistics (similar to BoE approach)
- CA BoS: may require webpage parsing (CSV download link per release)

### Expected impact

- M3 runtime: 7/12 → 9/12 FULL (+JP + CA)
- T1 overall: ~71-73% → ~73-75% (+2pp)
- Phase 2 fim Maio target 75-80% **within reach Day 1**

---

## §2 Spec (what)

### 2.1 Pre-flight probe (MANDATORY, ADR-0009 v2 analog)

#### 2.1.1 JP Tankan source discovery

```bash
cd /home/macro/projects/sonar-wt-q-3-cal-expinf-survey-jp-ca
source .env

# BoJ publishes Tankan results via statistics portal
# Base URL: https://www.boj.or.jp/en/statistics/tk/

# Probe JSON/CSV endpoints
curl -s -I "https://www.boj.or.jp/en/statistics/tk/stat_en.csv" 2>&1 | head -5
curl -s -I "https://www.boj.or.jp/en/statistics/tk/tk2025/tka2503.pdf" 2>&1 | head -5  # latest release

# Tankan inflation expectations are in "Enterprises' Outlook" tables
# Series to probe:
# - "General prices, all industries, 1-year ahead"
# - "General prices, all industries, 3-years ahead"
# - "General prices, all industries, 5-years ahead"
```

Document findings in `docs/backlog/probe-results/sprint-q-3-jp-ca-survey-probe.md`:
- Data availability format (CSV/JSON/PDF)
- Series identifiers / table columns
- Historical depth (quarterly Tankan since 1957)
- Frequency + release timing (quarterly)

#### 2.1.2 CA BoC BOS source discovery

```bash
# BoC publishes BOS via statistical data portal
curl -s -I "https://www.bankofcanada.ca/rates/indicators/business-outlook-survey/" 2>&1 | head -5

# BoC open data portal
curl -s "https://www.bankofcanada.ca/valet/lists/series" 2>&1 | head -20

# Probe Valet API (BoC's REST endpoint)
curl -s "https://www.bankofcanada.ca/valet/observations/INDINF_CPIPCT.INFEXP1YR/csv" 2>&1 | head -10
```

**Valet API** is BoC's official REST endpoint. Critical for Sprint Q.3 feasibility.

Document:
- Series codes for inflation expectations (1Y, 2Y)
- Access method (Valet observations endpoint)
- Historical depth (BOS since ~1997)

#### 2.1.3 Lesson #20 #6 application — **FROM START, not mid-sprint**

**Critical**: Sprint Q.2 discovered 3 cascade sites mid-sprint. Sprint Q.3 must enumerate ALL sites **before writing code**.

Known sites (per Q.2 retro):
1. `build_m3_inputs_from_db` — main function
2. `_load_histories` — helper
3. `classify_m3_compute_mode` — classifier emit

Audit in §2.1:
```bash
grep -rn "_query_expinf\|_query_survey\|_query_bei\|EXPINF_CANONICAL\|_load_histories\|classify_m3" \
  src/sonar/indices/monetary/ | grep -v test | head -30
```

Identify if Q.2 `_query_bei` pattern is reusable OR if JP/CA survey path adds new helper. Most likely: **reuse `_query_survey` + `_survey_tenors_bps`** (Q.1 helpers) since Tankan + BOS are survey-type data.

### 2.2 JP Tankan connector

**File**: `src/sonar/connectors/boj_tankan.py` (new)

```python
class BojTankanConnector:
    """BoJ Tankan Survey connector — quarterly inflation expectations.

    Fetches "General prices, all industries" outlook series.
    """

    async def fetch_inflation_expectations(
        self,
        date_start: date,
        date_end: date,
        horizon: Literal["1Y", "3Y", "5Y"] = "5Y",  # 5y5y proxy
    ) -> list[ExpInflationSurveyObservation]:
        """Fetch Tankan inflation outlook observations."""
        # CSV/JSON endpoint from §2.1.1 probe
        # Parse response, return observations
```

### 2.3 CA BoC BOS connector

**File**: `src/sonar/connectors/boc_valet.py` (new or extend existing)

```python
class BocValetConnector:
    """Bank of Canada Valet API connector."""

    async def fetch_inflation_expectations(
        self,
        date_start: date,
        date_end: date,
        horizon: Literal["1Y", "2Y"] = "2Y",
    ) -> list[ExpInflationSurveyObservation]:
        """Fetch BOS inflation expectations via Valet observations endpoint."""
```

### 2.4 Writer extensions (reuse Q.1 `persist_survey_row`)

Both JP + CA data flows into `exp_inflation_survey` (Q.1 shipped writer). **Zero new writer code expected** — survey_name field distinguishes sources:
- `survey_name='ECB_SPF_HICP'` (EA — Q.1 shipped)
- `survey_name='BOJ_TANKAN'` (JP — Q.3 new)
- `survey_name='BOC_BOS'` (CA — Q.3 new)

Methodology_version bumped per country if differently derived.

### 2.5 Loader + cascade — **apply Lesson #20 #6 from start**

**File**: `src/sonar/indices/monetary/db_backed_builder.py`

Cascade currently (post-Q.2):
1. `exp_inflation_canonical` (US path)
2. `exp_inflation_survey` (EA path Q.1.1 + Q.1.2)
3. `exp_inflation_bei` (GB path Q.2)

Sprint Q.3 — survey path **already present** for JP + CA. Verification:
- `_query_survey` filters by `country_code` only, not by survey_name → **should work out-of-box** for JP/CA after writer populates rows
- Classifier `classify_m3_compute_mode` — verify survey branch covers JP + CA cohort OR needs extension

**If classifier has EA-cohort hardcoded list** (DE/FR/IT/ES/PT), must extend to include JP + CA. Audit in §2.1.3.

### 2.6 Backfill + verify

```bash
# Backfill JP Tankan 2020-2026
uv run python -m sonar.connectors.boj_tankan.backfill \
  --date-start 2020-01-01 --date-end 2026-04-24

# Backfill CA BoC BOS 2020-2026
uv run python -m sonar.connectors.boc_valet.backfill_bos \
  --date-start 2020-01-01 --date-end 2026-04-24

# Verify writes
sqlite3 data/sonar-dev.db \
  "SELECT country_code, survey_name, COUNT(*), MAX(date)
   FROM exp_inflation_survey
   WHERE country_code IN ('JP', 'CA')
   GROUP BY country_code, survey_name;"

# Re-run JP + CA M3
for country in JP CA; do
  for date in 2026-04-21 2026-04-22 2026-04-23; do
    uv run python -m sonar.pipelines.daily_monetary_indices --country $country --date $date
  done
done

# Verify M3 FULL
uv run python -m sonar.pipelines.daily_monetary_indices --all-t1 --date 2026-04-23 2>&1 | \
  grep "m3_compute_mode" | grep -E "country=(JP|CA)"
# Expected: both mode=FULL, flags include M3_EXPINF_FROM_SURVEY
```

### 2.7 Tests

```python
def test_boj_tankan_connector_fetches_inflation_outlook(mock_boj):
    """Sprint Q.3: Tankan CSV parsing."""

def test_boc_valet_connector_fetches_bos(mock_boc_valet):
    """Sprint Q.3: Valet observations endpoint parsing."""

def test_jp_m3_full_via_tankan_survey(test_session, jp_tankan_fixtures):
    """Sprint Q.3: JP M3 resolves FULL via Tankan survey path."""

def test_ca_m3_full_via_bos_survey(test_session, ca_bos_fixtures):
    """Sprint Q.3: CA M3 resolves FULL via BOS survey path."""

def test_classifier_extends_jp_ca_survey_cohort(test_session):
    """Sprint Q.3: classifier accepts JP/CA as survey-FULL-capable."""

def test_existing_cohort_regression(test_session, us_ea_gb_fixtures):
    """Sprint Q.3: US canonical + EA survey + GB BEI paths unchanged."""
```

---

## §3 Commits plan

| # | Scope | Files |
|---|---|---|
| C1 | docs(probes): Sprint Q.3 JP Tankan + CA BoC probe | `docs/backlog/probe-results/sprint-q-3-jp-ca-survey-probe.md` |
| C2 | feat(connectors): BoJ Tankan + BoC Valet connectors | `src/sonar/connectors/boj_tankan.py`, `boc_valet.py` |
| C3 | feat(indices): classifier cohort extension (if needed per §2.5 audit) | `src/sonar/indices/monetary/m3_country_policies.py` (conditional) |
| C4 | test: Tankan + BOS connectors + JP/CA M3 FULL + regression | `tests/...` |
| C5 | ops: backfill JP/CA 2020-2026 + M3 verify | no commit |
| C6 | docs(backlog): CAL-EXPINF-SURVEY-JP-CA closure | `docs/backlog/calibration-tasks.md` |
| C7 | docs(planning): Sprint Q.3 retrospective | `docs/planning/retrospectives/week11-sprint-q-3-cal-expinf-survey-jp-ca-report.md` |

---

## §4 HALT triggers

**HALT-0**:
- BoJ Tankan CSV/JSON endpoint inaccessible (only PDF) → HALT-0 JP, ship CA only, open `CAL-EXPINF-JP-SCRAPE` Week 12+
- BoC Valet API HTTP 5xx sustained → HALT-0 CA, ship JP only
- Both HALT-0 → full Sprint Q.3 HALT, rescope to Q.3.1 scrape approach

**HALT-material**:
- Classifier cohort hardcoded to EA members only (DE/FR/IT/ES/PT) AND requires non-trivial refactor → scope expand 1h, assess
- History depth <60 observations post-backfill → baseline insufficient, document + accept DEGRADED alternative
- US/EA/GB regression → STOP immediately

**HALT-scope**:
- Temptation to ship NL/PT/AU policies → STOP (separate CAL-M3-*-BUILDER future)
- Temptation to ship BEI for JP (JGBi / inflation-linked JGBs) → STOP, scope Sprint Q.3.1 Week 12+
- Temptation to fix M1 per-EA-member → STOP (separate audit)

---

## §5 Acceptance

### Tier A

1. **Probe doc shipped** (JP + CA sources + series codes)
2. **2 connectors shipped** (Tankan + Valet)
3. **JP `exp_inflation_survey` rows populated** (≥60 baseline)
4. **CA `exp_inflation_survey` rows populated** (≥60 baseline)
5. **Local CLI**: JP + CA `m3_compute_mode.*mode=FULL` with `M3_EXPINF_FROM_SURVEY`
6. **Regression**: US + EA + GB M3 FULL unchanged
7. **Pre-commit clean double-run**

**Partial ship acceptable**: if 1 of JP/CA HALT-0, ship other cleanly + document the HALT for Week 12+.

### Tier B

1. **Systemd verify 9 M3 FULL**:
   ```bash
   sudo systemctl reset-failed sonar-daily-monetary-indices.service
   sudo systemctl start sonar-daily-monetary-indices.service
   sleep 120
   sudo journalctl -u sonar-daily-monetary-indices.service --since "-3 min" --no-pager | \
     grep "m3_compute_mode" | grep -oE "mode=[A-Z_]+" | sort | uniq -c
   ```
   Expected: **9 FULL / 0 DEGRADED / 3 NOT_IMPLEMENTED** (if both JP+CA ship). If partial, 8 FULL + 1 DEGRADED.

2. **Summary clean**: `n_failed=0`.

3. **DB verify**:
   ```bash
   sqlite3 data/sonar-dev.db \
     "SELECT country_code, survey_name, COUNT(*) FROM exp_inflation_survey GROUP BY country_code, survey_name;"
   ```
   Expected: EA (ECB_SPF_HICP) + JP (BOJ_TANKAN) + CA (BOC_BOS) + 5 EA members (ECB_SPF_HICP proxies).

---

## §6 Retro scope

- M3 matrix pre/post (7 → 9 FULL if both ship, 7 → 8 if partial)
- Lesson #20 #6 applied from start — 3 cascade sites pre-audited
- BoJ Tankan vs BoC Valet vs ECB SPF pattern comparison — document differences
- T1 coverage delta
- **Phase 2 milestone**: if Day 1 closes with 9 M3 FULL → target fim Maio achievable Week 11-12

---

## §7 Execution notes

- **Probe-first discipline** (§2.1) mandatory
- **Lesson #20 #6 applied from start** — audit ALL cascade sites in §2.1.3 BEFORE connector code
- **Writer reuse** — Q.1 `persist_survey_row` handles JP + CA with different survey_name
- **Classifier cohort extension** only if hardcoded list blocks JP/CA — minimal change
- **Paralelo-safe** with any non-M3 sprint (unlikely to launch Day 1 afternoon)
- **Budget respected**: partial ship (1 of 2) acceptable, better ship 1 clean than both broken

---

## §8 Dependencies & CAL interactions

### Parent
Sprint Q.2 (BoE BEI pattern + Lesson #20 #6 canonical codification)

### CAL closed
- `CAL-EXPINF-SURVEY-JP-CA` primary deliverable

### CAL potentially opened
- `CAL-EXPINF-JP-SCRAPE` if Tankan PDF-only
- `CAL-EXPINF-JP-BEI` if JGBi linker wanted Week 12+
- `CAL-EXPINF-CA-BEI` if RRB linker wanted Week 12+

### Sprints unblocked
- **Phase 2 fim Maio target within immediate reach** if 9/12 M3 FULL shipped Day 1
- Sprint M2-EA-per-country orthogonal (different layer)
- Sprint R E1 activity orthogonal (different layer)

---

## §9 Time budget

Arranque ~15:15 WEST. Hard stop 19:15 WEST (4h).

- Best case 2h: both APIs accessible, CSV/JSON clean, thin connectors
- Median 3h: 1 API quirk (likely Tankan format complexity)
- Worst case 4h: 1 HALT-0, ship other partial

**Merge + Tier B**: +10 min operator. Day 1 close target ~19:30-20:00 WEST.

---

*End brief. 2 countries M3 FULL. Lesson #20 #6 applied from start. Ship disciplined — Phase 2 milestone within reach.*
