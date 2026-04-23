# Sprint T — Sparse T1 Curves Sweep (6 Countries) via ADR-0009 v2.2 S1/S2 Classifier

**Branch**: `sprint-t-sparse-t1-sweep-au-nz-ch-se-no-dk`
**Worktree**: `/home/macro/projects/sonar-wt-t-sparse-t1-sweep-au-nz-ch-se-no-dk`
**Data**: 2026-04-23 Day 3 late night (~23:00 WEST arranque)
**Operator**: Hugo Condesa (reviewer) + CC (executor, full autonomy per SESSION_CONTEXT)
**Budget**: 4-6h solo
**ADR-0010 tier scope**: T1 ONLY (all 6 countries — AU/NZ/CH/SE/NO/DK are T1 per handoff §3)
**ADR-0009 v2.2 TE Path 1 probe**: **MANDATORY** + **S1/S2 classifier as triage** (pattern library first empirical validation sweep)
**Brief format**: v3.2 (Tier A / Tier B split — Lesson #12 compliance)
**Systemd services affected**: `sonar-daily-curves.service` (T1 tuple expansion 10 → up to 16 pending per-country PASS/HALT outcomes)
**Parent**: Sprint M (codified S1/S2 classifier in ADR-0009 v2.2) — first large-scale application of pattern library

---

## §1 Scope (why)

**Gap identificado**: T1 curves coverage = 10/16 post-Sprint-M (US/DE/EA/GB/JP/CA/IT/ES/FR/PT). Missing 6 sparse T1 countries + NL (Sprint M HALT-0, deferred Week 11 via DNB Path 2):

- **AU** (Australia, AUD sovereign — ACGB)
- **NZ** (New Zealand, NZD sovereign — NZGB)
- **CH** (Switzerland, CHF sovereign — Swiss Confed)
- **SE** (Sweden, SEK sovereign — SGB)
- **NO** (Norway, NOK sovereign — NGB)
- **DK** (Denmark, DKK sovereign — DGB)

**ADR-0009 v2.2 empirical ledger status**: 4 PASS (IT/ES/FR/PT) + 1 non-inversion (NL). Sprint T applies **S1/S2 classifier** as binary triage — 6 probes = 6 classifications against canonical criteria.

**Objectivo Sprint T**: probe 6 countries via TE Path 1, classify each S1 (Svensson-rich, ≥6 daily tenors ≥500 obs) vs S2 (point-estimates, <6 tenors). Ship S1 via cascade mirror Sprint H pattern. Document S2 with CAL-CURVES-<COUNTRY>-PATH-2 for Week 11.

**Hypothesis empírica** (documented for retro empirical enrichment):

| Country | Sovereign market | TE coverage prior (qualitative) | Probability S1 PASS |
|---|---|---|---|
| AU | AUD ~$500B+ outstanding | Major, daily liquidity | HIGH (~80%) |
| NZ | NZD ~$100B+ outstanding | Smaller, some liquidity gaps | MEDIUM (~60%) |
| CH | CHF ~$120B+ outstanding | Moderate, CHF haven bid | HIGH (~75%) |
| SE | SEK ~$90B+ outstanding | Moderate, Nordic liquidity | MEDIUM-HIGH (~70%) |
| NO | NOK ~$35B+ outstanding | Smaller, sovereign wealth offset | MEDIUM (~55%) |
| DK | DKK ~$75B+ outstanding | Moderate, EUR-pegged | MEDIUM (~60%) |

**Realistic expectation**: 3-5 PASS of 6. Coverage delta Sprint T: +3-5pp L2 curves (10/16 → 13-15/16).

---

## §2 Spec (what)

### 2.1 Pre-flight probe matrix (ADR-0009 v2 mandatory + v2.2 classifier)

**Per-country probe sequence** (CC executes 6× in order, documents each):

```bash
# Country probe template — repeat for each of AU/NZ/CH/SE/NO/DK
set -a && source .env && set +a
COUNTRY="australia"  # or new-zealand / switzerland / sweden / norway / denmark
SYMBOL_PREFIX="GACGB"  # TE uses various prefixes; verify via probe

for tenor in 1M 3M 6M 1 2 3 5 7 10 15 20 30; do
  SYMBOL="${SYMBOL_PREFIX}${tenor}:IND"  # Adjust :IND vs :GOV per country quirk

  # Daily tenor count probe
  COUNT=$(curl -s "https://api.tradingeconomics.com/historical/country/${COUNTRY}/indicator/government%20bond%20${tenor}y?c=${TE_API_KEY}&format=json&d1=2024-01-01&d2=2026-04-22" | jq 'length' 2>/dev/null || echo "0")

  # LastUpdate recency
  LATEST=$(curl -s "https://api.tradingeconomics.com/historical/country/${COUNTRY}/indicator/government%20bond%20${tenor}y?c=${TE_API_KEY}&format=json&d1=2026-04-01&d2=2026-04-22" | jq '.[-1].DateTime' 2>/dev/null || echo "null")

  echo "${COUNTRY} ${tenor}: count=${COUNT} latest=${LATEST}"
done
```

### 2.2 S1/S2 classification per country (ADR-0009 v2.2)

**Classification criteria** (canonical, per pattern library):

- **S1 (Svensson-rich)** — PASS:
  - ≥6 distinct daily tenors available
  - Each tenor ≥500 observations
  - LastUpdate ≤7 days stale
  - No structural tenor gaps that break NSS fit (min 2 short + 2 mid + 2 long tenors)

- **S2 (point-estimates only)** — HALT-0:
  - <6 tenors OR structural gaps blocking NSS
  - Defer to Path 2 (national CB or aggregator)
  - CAL opened for Week 11

**Document in `docs/backlog/probe-results/sprint-t-sparse-t1-sweep-probe.md`** (new):
- Per-country raw tenor counts + symbols + LastUpdate
- S1/S2 classification decision + justification
- If S1, symbol spectrum captured for te.py extension
- If S2, which tenors fail + hypothesized Path 2

### 2.3 TE quota pre-check (Lesson #8 proactive)

Before first probe, verify quota:

```bash
# Approximate 6 countries × 12 tenors = 72 probes + potential backfill = ~150-200 TE calls expected
# Baseline Day 3 close: ~27% consumed (post Sprint M)
# Budget ceiling: must remain <50% after Sprint T

curl -s -I "https://api.tradingeconomics.com/markets/historical/country/portugal:rating?c=${TE_API_KEY}" 2>&1 | grep -iE "x-ratelimit" || echo "No quota headers"
```

**HALT-pre-flight** if observed quota >45% OR HTTP 403 sustained.

### 2.4 TE symbols table extension (conditional per S1 PASS)

For each S1 country, extend `src/sonar/connectors/te.py` `TE_YIELD_CURVE_SYMBOLS`:

```python
TE_YIELD_CURVE_SYMBOLS = {
    ...existing US/DE/EA/GB/JP/CA/IT/ES/FR/PT...,
    # Sprint T additions conditional on S1 classification
    "AU": {...},  # ACGB family
    "NZ": {...},  # NZGB family (if S1)
    "CH": {...},  # Swiss Confed (if S1)
    "SE": {...},  # SGB family (if S1)
    "NO": {...},  # NGB family (if S1)
    "DK": {...},  # DGB family (if S1)
}
```

**Per-country quirks expected** (Sprint M mixed-suffix precedent):
- TE symbol conventions vary: `:IND` vs `:GOV` vs country-specific
- Tenor suffix mixing: `M` (months) vs `YR` vs bare `Y`
- CC must verify each symbol via `HistoricalDataSymbol` response field, not assume pattern

### 2.5 daily_curves.py T1 tuple expansion (conditional per-country)

`src/sonar/pipelines/daily_curves.py` — extend T1 tuple per S1 countries:

```python
# After Sprint M: T1_COUNTRIES = ("US", "DE", "EA", "GB", "JP", "CA", "IT", "ES", "FR", "PT")
# After Sprint T (if all 6 S1): T1_COUNTRIES = (...above..., "AU", "NZ", "CH", "SE", "NO", "DK")
# Partial: only S1 countries added, S2 countries deferred
```

### 2.6 Per-country isolation + dispatcher

ADR-0011 Principle 2 (per-country isolation) already shipped. Reuse. If any S1 country fails NSS fit post-symbol-add (e.g., data quality issue in specific period), graceful skip + warning, not pipeline abort.

### 2.7 Backfill Apr 21-23 per S1 country

Post-code ship:

```bash
for country in <s1_countries>; do
  for date in 2026-04-21 2026-04-22 2026-04-23; do
    uv run python -m sonar.pipelines.daily_curves --country $country --date $date
  done
done
```

Verify:
```bash
sqlite3 data/sonar-dev.db \
  "SELECT country_code, MAX(date) AS latest, COUNT(*) AS n FROM yield_curves_spot WHERE country_code IN (<s1_list>) GROUP BY country_code;"
```

### 2.8 ADR-0009 v2.2 empirical ledger update

`docs/adr/ADR-0009-national-cb-connectors-ea-periphery.md` — Sprint T addendum:

```markdown
### Sprint T Empirical Ledger Update (2026-04-23)

First large-scale application of S1/S2 classifier from v2.2 (Sprint M codification).
Probe sweep 6 sparse T1 countries:

| Country | Classification | Tenors | Decision |
|---|---|---|---|
| AU | S1/S2 | <n>/12 | PASS/HALT-0 |
| NZ | ... | ... | ... |
| CH | ... | ... | ... |
| SE | ... | ... | ... |
| NO | ... | ... | ... |
| DK | ... | ... | ... |

**Ledger status post-Sprint-T**: <N> PASS cumulative (inc IT/ES/FR/PT), <M> HALT-0 cumulative (inc NL).
**Pattern library**: classifier validated empirically against 6-country cohort — <objective assessment>.
```

### 2.9 Per-country CALs for S2 outcomes

For each S2 country, open `CAL-CURVES-<COUNTRY>-PATH-2` (analogous to NL DNB Path 2 post-Sprint-M):

```markdown
### CAL-CURVES-AU-PATH-2 — AU sovereign yield curve via national CB/stat office fallback
- Priority: LOW (AU is sparse T1, PT/NL priority higher)
- Path 2 candidate: RBA (Reserve Bank of Australia) statistics portal
- Path 3 fallback: BIS sovereign yields
- Budget: 2-3h Week 11+ scoped probe
```

### 2.10 Sprint T retro — pattern library empirical assessment

Critical retro deliverable: honest assessment of **S1/S2 classifier usefulness in practice**. Questions to answer:

1. Did the classifier correctly predict S1/S2 outcomes, or were there edge cases?
2. Were any countries borderline (e.g., 5 tenors — is that S1 with relaxed threshold or S2)?
3. Pattern library improvements suggested (e.g., tenor-weighted scoring vs binary count)?
4. Velocity multiplier evidence: 6 probes in N hours vs estimated 8-10h pre-v2.2?

---

## §3 Commits plan

Conditional structure — per-country commits may vary by S1/S2 outcome.

| Commit | Scope | Conditional |
|---|---|---|
| **C1** | docs(planning): Sprint T brief | always |
| **C2** | docs(probes): S1/S2 classification results per country | always (probe-first discipline per ADR-0009 v2) |
| **C3** | feat(connectors): te.py symbols expansion for S1 countries | conditional (if ≥1 S1) |
| **C4** | feat(pipelines): daily_curves T1 tuple expansion | conditional (if ≥1 S1) |
| **C5** | test: regression coverage S1 countries | conditional (if ≥1 S1) |
| **C6** | ops: backfill Apr 21-23 verification | conditional (if ≥1 S1) |
| **C7** | docs: ADR-0009 v2.2 Sprint T addendum + CALs for S2 countries | always |
| **C8** | docs: Sprint T retrospective + pattern library assessment | always |

---

## §4 HALT triggers

**HALT-pre-flight**:
- TE quota >45% April consumption OR sustained HTTP 403 → HALT, defer Day 4 or Week 11

**HALT-0 (per-country, expected outcomes for some)**:
- S2 classification = country-specific HALT-0 (expected for 1-3 of 6). Document + CAL opened. Continue next country.
- Full sweep HALT-0 (all 6 S2): improbable but would invalidate Sprint T scope. Full retro documenting ADR-0009 v2.2 boundary conditions.

**HALT-material**:
- TE probe PASS but NSS fit fails (rmse_bps > 30, confidence < 0.5) for any country → HALT that country, investigate data quality before ship
- DB unique constraint violation unexpected despite ADR-0011 P1 → HALT
- Scope creep: temptation to also probe EA periphery remaining (e.g., AT, BE, IE, FI) → STOP (T1 sparse only)

**HALT-scope**:
- Temptation to upgrade GB/JP/CA M4 FCI scaffold → STOP (Sprint T is curves only)
- Temptation to touch Sprint O M3 classifier → STOP (merged, stable)
- Temptation to resurrect NL via alternate path → STOP (CAL-CURVES-NL-DNB-PROBE Week 11 scope)

**HALT-security**: standard.

---

## §5 Acceptance

### Tier A (pre-merge, CC scope — v3.2 compliance)

**Primary** (conditional on outcome distribution):

1. **Probe discipline** — `docs/backlog/probe-results/sprint-t-sparse-t1-sweep-probe.md` contains 6 country classification entries with raw data
2. **S1 countries shipped** — `yield_curves_spot` persisted Apr 21/22/23 for all S1 classifications
3. **S2 countries documented** — CAL opened per S2 country, ADR-0009 v2.2 addendum reflects non-inversion count
4. **Regression tests** — `pytest tests/unit/test_pipelines/test_daily_curves.py -v` pass including new S1 country tests
5. **Local CLI exit 0** — `uv run python -m sonar.pipelines.daily_curves --all-t1 --date 2026-04-22` → summary reports N+10 countries, n_failed=0
6. **Bash wrapper smoke** — `bash -lc 'uv run python -m sonar.pipelines.daily_curves --all-t1 --date 2026-04-22'` → same clean output
7. **Pre-commit clean** — double-run all-files pass

### Tier B (post-merge, operator scope — applied ~04:30-05:00 WEST or Day 4 manhã)

1. **Systemd curves service verify**:
   ```bash
   sudo systemctl start sonar-daily-curves.service
   sleep 180
   systemctl is-active sonar-daily-curves.service
   sudo journalctl -u sonar-daily-curves.service --since "-3 min" --no-pager | \
     grep "daily_curves.summary"
   ```
   Expected: N+10 countries in summary (where N = S1 countries shipped), n_failed=0

2. **DB coverage**:
   ```bash
   sqlite3 data/sonar-dev.db \
     "SELECT country_code, MAX(date) AS latest FROM yield_curves_spot GROUP BY country_code;"
   ```
   Expected: 10 + N countries (pre-Sprint-T + S1 additions), all latest=2026-04-23

3. **Timer armed**:
   ```bash
   systemctl is-active sonar-daily-curves.timer
   ```
   Expected: active

---

## §6 Retro scope

Documentar em `docs/planning/retrospectives/week10-sprint-t-sparse-t1-sweep-report.md`:

### Empirical outcomes table

6-country matrix: S1/S2 classification, tenor counts, LastUpdate, decision rationale.

### S1/S2 classifier validation

- **Correctness**: did v2.2 classifier predict S1/S2 correctly vs actual NSS fit quality?
- **Edge cases**: any country borderline (e.g., exactly 6 tenors, or tenors ≥500 obs but structural gap)?
- **Quirks discovered**: new TE symbol conventions (Sprint M mixed-suffix extension analogs)?

### Pattern library v2.3 amendment candidates

- Threshold refinements (e.g., weighted tenor scoring vs binary ≥6)?
- Structural gap classification (short/mid/long coverage requirement)?
- LastUpdate tolerance adjustment?

### Velocity multiplier assessment

- Actual time spent vs pre-v2.2 estimate (8-10h)
- Compound value: Sprint T is 4th Pattern library application post-v2.2 codification
- Week 11+ projection for remaining T1 gaps (NL via Path 2)

### Week 10 close delta

- T1 overall % post-Sprint-T = pre-Sprint-T (~57%) + Sprint T contribution
- ADR-0009 ledger position (PASS count, non-inversion count)

---

## §7 Execution notes

- **Probe BEFORE code discipline** (ADR-0009 v2 canonical): C2 must precede C3/C4 regardless of S1/S2 distribution
- **Per-country isolation**: each country probed independently, decisions isolated, partial ship embraced
- **TE symbol verification**: NEVER assume naming pattern — always verify via `HistoricalDataSymbol` field in probe response
- **Budget discipline**: if wall-clock exceeds 5h, HALT residual countries + ship whatever S1 countries already verified. Don't marathon past 04:00 WEST.
- **Pre-commit double-run** (Week 10 Lesson #2)
- **sprint_merge.sh Step 10** cleanup (Lesson #4 fix)
- **CC arranque template** (Lesson #5 fix)
- **DB symlink** should auto-link via sprint_setup.sh (Lesson #14 fix shipped Sprint V) — verify if operational
- **Zero-overlap assumption**: no other sprints running parallel (Sprint V + O merged). Clean solo sprint.

---

## §8 Dependencies & CAL interactions

### Parent sprint
Sprint M (ADR-0009 v2.2 S1/S2 codification — Sprint T is first large-scale application)

### CAL items closed by this sprint (per S1 country)
- `CAL-CURVES-AU-*` (if S1) — TE Path 1 resolves
- `CAL-CURVES-NZ-*` (if S1)
- `CAL-CURVES-CH-*` (if S1)
- `CAL-CURVES-SE-*` (if S1)
- `CAL-CURVES-NO-*` (if S1)
- `CAL-CURVES-DK-*` (if S1)

### CAL items opened by this sprint (per S2 country)
- `CAL-CURVES-<S2_COUNTRY>-PATH-2` — Week 11 Path 2 probe (RBA/RBNZ/SNB/Riksbank/NorgesBank/Nationalbanken)

### Sprints blocked by this sprint
- **None**

### Sprints unblocked by this sprint
- L4 MSC cross-country composite (future) — eventual coverage 11-16 countries curves enables progressively more M1/M2/M3/M4 intersection where all FULL
- Week 11 E1/E3/E4 coverage scope — sparse T1 countries now have yield foundation for expected-inflation-adjacent economic indices

---

## §9 Time budget ceiling

Sprint T hard stop at **04:00 WEST** (2026-04-24 03:00 UTC). Reasons:

1. Natural fire Apr 24 05:00 UTC needs main in ship-clean state
2. Operator sleep budget: minimum 3h before Day 4 morning (wake ~07:30-08:00 WEST)
3. Pattern library discipline: marathon sprints historically correlate with Lesson #3 pattern recurrence (tired brief gaps)

If wall-clock 03:30 WEST approaches and residual countries not probed:
- Ship partial (S1 countries already shipped, S2 countries documented)
- Residual probe Day 4 manhã OR Week 11
- No scope pressure overrides time discipline

---

*End of brief. First large-scale empirical application of ADR-0009 v2.2 S1/S2 classifier. Ship disciplined, close Week 10 clean.*
