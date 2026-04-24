# Sprint T-Retry — Path 1 Multi-Prefix Re-Probe (NZ/CH/SE/NO/DK)

**Branch**: `sprint-t-retry-multi-prefix-probe-nz-ch-se-no-dk`
**Worktree**: `/home/macro/projects/sonar-wt-t-retry-multi-prefix-probe-nz-ch-se-no-dk`
**Data**: Week 11 Day 1 (2026-04-24) — target arranque ~14:15 WEST (paralelo com Sprint Q.1)
**Operator**: Hugo Condesa (reviewer) + CC (executor, full autonomy per SESSION_CONTEXT)
**Budget**: 2-3h solo
**Priority**: **P2** — methodology gap closure + opportunistic coverage (~+2-4 countries L2 curves if successful)
**ADR-0010 tier scope**: T1 ONLY (sparse T1 residuals from Sprint T)
**ADR-0009 v2.2 TE Path 1 probe**: **MANDATORY + v2.3 multi-prefix amendment validation**
**Brief format**: v3.3 (Tier A / Tier B + filename convention compliance)
**Systemd services affected**: `sonar-daily-curves.service` (T1 tuple expansion if ≥1 S1 PASS)
**Parent**: Sprint T (Week 10 Day 3) — 5 HALT-0 countries flagged for methodology-gap re-probe

---

## §1 Scope (why)

### Sprint T retrospective context

Sprint T (Week 10 Day 3) shipped 6-country sparse T1 sweep via single-prefix probe methodology. Result: 1 S1 PASS (AU via GACGB), 5 S2 HALT-0 (NZ/CH/SE/NO/DK).

Sprint T discoveries §9 flagged methodology gaps:

**Discovery #1** — TE `/search` is high-recall, not exhaustive. NZ `GNZGB1:IND` missed despite existing in TE.

**Discovery #2** — Multi-prefix families possible within one country. NO uses `GNOR` + `NORYIELD` (different tenor subsets).

**Discovery #3** — Sparse-T1 TE-coverage prior should default ~25-30%, not 55-80% per original brief projection. "Sovereign-market size → TE coverage" heuristic **refuted** for CHF/SEK/NOK/DKK.

### Hypothesis

Sprint T 5/6 HALT-0 may contain **false negatives** — data exists in TE for some countries but single-prefix `G<CC>{tenor}:IND` convention missed them.

### Objectivo Sprint T-Retry

Systematic multi-prefix + multi-suffix + direct-symbol-lookup probe for each of 5 S2 countries. Upgrade any missed S1 classifications. Ship S1 PASS countries via TE cascade + ADR-0009 v2.2 classifier.

### Expected realistic outcome

Per Sprint T Discovery #3 (refuted heuristic), realistic range: **0-3 additional S1 PASS of 5**.

- Best case: 3 additional PASS (NZ + SE + DK via multi-prefix discovery) = +19pp L2 curves
- Median case: 1-2 additional PASS = +6-13pp L2 curves
- Worst case: 0 PASS (all 5 confirm HALT-0) = methodology gap empirically closed, Week 11+ Path 2 cohort sprint justified

### Independent of Sprint Q.1 scope

Sprint T-Retry paralelizável com Sprint Q.1 (EA-ECB-SPF) — zero file overlap:
- Sprint T-Retry touches `src/sonar/connectors/te.py` + `daily_curves.py` + curves tests
- Sprint Q.1 touches `src/sonar/connectors/ecb_sdw.py` + `exp_inflation_*` + overlays

---

## §2 Spec (what)

### 2.1 Multi-prefix probe methodology

For each of 5 S2 countries (NZ/CH/SE/NO/DK), execute systematic probe:

#### 2.1.1 TE exhaustive symbol discovery

```bash
cd /home/macro/projects/sonar-engine
source .env

for country_slug in "new-zealand" "switzerland" "sweden" "norway" "denmark"; do
  echo "=== Country: $country_slug ==="

  # /search endpoint (Sprint T baseline)
  curl -s "https://api.tradingeconomics.com/search/${country_slug}%20government%20bond?c=${TE_API_KEY}&format=json" | \
    jq '.[] | {symbol, name, category}' | head -40

  # Alternative query variants (NEW for Sprint T-Retry)
  curl -s "https://api.tradingeconomics.com/search/${country_slug}%20sovereign%20yield?c=${TE_API_KEY}&format=json" | \
    jq '.[] | {symbol, name}' | head -20

  curl -s "https://api.tradingeconomics.com/search/${country_slug}%20treasury?c=${TE_API_KEY}&format=json" | \
    jq '.[] | {symbol, name}' | head -20
done
```

Document all discovered symbols in `docs/backlog/probe-results/sprint-t-retry-multi-prefix-probe.md` (new).

#### 2.1.2 Multi-prefix enumeration

For each country, identify **all** prefix families observable:

| Country | Sprint T prefix (failed) | Alternative prefix candidates |
|---|---|---|
| NZ | GNZGB | NZGB, GNZD, NZGB (bare), NZDEP, NZTB |
| CH | GCHF | GSWI, SWG, CHGB, SWISSGB |
| SE | GSEK | GSWE, SWDGB, SEGB |
| NO | GNOR | GNOR (confirmed), NORYIELD (confirmed), NOGB, NOKGB |
| DK | GDKK | GDEN, DKGB, DKKGB, DANGB |

Probe **each candidate × each tenor** (3M / 6M / 1Y / 2Y / 3Y / 5Y / 7Y / 10Y / 15Y / 20Y / 30Y):

```bash
for candidate_prefix in GNZGB NZGB GNZD NZDEP NZTB; do
  for tenor in 3M 6M 1 2 3 5 7 10 15 20 30; do
    for suffix in ":IND" ":GOV" ""; do
      SYMBOL="${candidate_prefix}${tenor}${suffix}"
      COUNT=$(curl -s "https://api.tradingeconomics.com/historical/country/new-zealand/indicator/government%20bond%20${tenor}y?c=${TE_API_KEY}&format=json&d1=2024-01-01&d2=2026-04-22" 2>/dev/null | jq 'length' 2>/dev/null)
      # ... document
    done
  done
done
```

This multiplies probe calls but is finite (5 countries × 5 prefixes × 11 tenors × 3 suffixes = 825 max, realistic ~300-400 after filtering). TE quota should absorb comfortably (baseline ~29% April consumed post-Sprint-T).

#### 2.1.3 TE `/markets/historical/country/<country>/indicator/<indicator>` direct endpoint

Discovered Sprint T that `/search` is high-recall but not exhaustive. The `/markets/historical` endpoint is the final arbiter:

```bash
# For NZ, test specific tenor:indicator combinations without symbol pre-guessing
curl -s "https://api.tradingeconomics.com/markets/historical/country/new-zealand/indicator/government%20bond%205y?c=${TE_API_KEY}&format=json&d1=2024-01-01&d2=2026-04-22" | \
  jq '.[0] | {Symbol, Country, Category}'
```

This endpoint returns data even when `/search` misses the symbol. Document canonical Symbol from responses for each tenor returning data.

### 2.2 Classifier application per country

For each of 5 countries, apply ADR-0009 v2.2 S1/S2 classifier against **full multi-prefix probe results**:

- **S1 (Svensson-rich)** — PASS:
  - ≥6 distinct daily tenors across ALL prefix families combined
  - Each tenor ≥500 observations
  - LastUpdate ≤7 days
  - No structural gaps blocking NSS (2+ short + 2+ mid + 2+ long tenors represented)

- **S2 (point-estimates only)** — HALT-0 confirmed:
  - <6 tenors even across multi-prefix aggregation
  - Path 2 escalation justified for Week 11+

Document per-country decision with raw data + hypothesis-refutation statement (Sprint T assumed PASS, Retry confirms/overturns).

### 2.3 TE symbols table extension (conditional per S1 PASS)

For each S1 country upgraded from S2, extend `src/sonar/connectors/te.py` `TE_YIELD_CURVE_SYMBOLS`:

```python
TE_YIELD_CURVE_SYMBOLS = {
    ...existing 11 countries post-Sprint-T...,
    # Sprint T-Retry additions conditional on S1 upgrade
    "NZ": {...},  # e.g., NZGB family if Retry finds it
    "NO": {...},  # multi-prefix GNOR + NORYIELD
    # etc per country
}
```

Handle multi-prefix per country via ordered dict or tuple-of-prefixes structure. Document convention in block docstring.

### 2.4 daily_curves.py T1 tuple expansion (conditional)

`src/sonar/pipelines/daily_curves.py` — extend T1 tuple per S1-upgraded countries:

```python
# Post-Sprint-T: T1_COUNTRIES = (US/DE/EA/GB/JP/CA/IT/ES/FR/PT/AU) — 11 countries
# Post-Sprint-T-Retry: add S1-upgraded subset
```

**Note**: `daily_curves.py` has its own `T1_COUNTRIES` (per Sprint Q.0.5 Discovery #1 — per-pipeline definition). Don't import from `daily_monetary_indices.py`. Each pipeline maintains its own T1 scope.

### 2.5 Per-country isolation + dispatcher

ADR-0011 Principle 2 (per-country isolation) remains. Reuse.

### 2.6 Backfill Apr 21-24 per S1 country

```bash
for country in <s1_upgraded_countries>; do
  for date in 2026-04-21 2026-04-22 2026-04-23 2026-04-24; do
    uv run python -m sonar.pipelines.daily_curves --country $country --date $date
  done
done
```

Verify:
```bash
sqlite3 data/sonar-dev.db \
  "SELECT country_code, MAX(date) AS latest, COUNT(*) AS n FROM yield_curves_spot WHERE country_code IN (<new_s1_list>) GROUP BY country_code;"
```

### 2.7 Regression tests

`tests/unit/test_pipelines/test_daily_curves.py` + `tests/unit/test_connectors/test_te.py`:

- Parametric coverage per S1-upgraded country
- Graceful handling per-country dispatcher isolation
- `TE_YIELD_CURVE_SYMBOLS` tuple integrity (no duplicates, valid structure)

### 2.8 ADR-0009 v2.2 → v2.3 amendment

`docs/adr/ADR-0009-national-cb-connectors-ea-periphery.md` — Sprint T-Retry addendum codifying multi-prefix probe discipline:

```markdown
### Sprint T-Retry Empirical Ledger Update (2026-04-24)

**v2.3 amendment — Multi-prefix + multi-suffix probe canonical**

Sprint T (Week 10 Day 3) identified methodology gaps. Sprint T-Retry (Week 11 Day 1)
validates systematic multi-prefix probe discipline.

Canonical probe sequence per country:
1. `/search` high-recall query (Sprint T baseline)
2. Alternative query variants (`sovereign yield`, `treasury`)
3. Multi-prefix enumeration across TE family conventions
4. `/markets/historical/country/<country>/indicator/government%20bond%20<N>y` direct endpoint
5. S1/S2 classification against aggregated multi-prefix tenor count

New ledger post-Sprint-T-Retry:
- S1 PASS cumulative: <N> (Sprint H: IT/ES; Sprint I: FR; Sprint M: PT; Sprint T: AU; Sprint T-Retry: ...)
- S2 HALT-0 confirmed: <M> (Sprint M: NL; Sprint T-Retry residuals)
- S1 upgraded from S2 via methodology improvement: <K>

Multi-prefix discovery rate: <K>/5 = <K×20>% Sprint T false-negative rate under single-prefix methodology.
```

### 2.9 Path 2 CAL updates per remaining S2 countries

For each country that remains S2 after Sprint T-Retry (confirmed HALT-0 across multi-prefix probe), update existing `CAL-CURVES-<COUNTRY>-PATH-2`:

```markdown
### CAL-CURVES-NZ-RBNZ-PATH-2 — **CONFIRMED OPEN (Sprint T-Retry 2026-04-24)**
- Multi-prefix Path 1 probe exhausted. TE does not cover NZ sovereigns adequately.
- Path 2 escalation: RBNZ (Reserve Bank of New Zealand) statistics portal
- Budget 3-4h Week 11+ Path 2 cohort sprint
```

### 2.10 Retro — pattern library v2.3 empirical assessment

Critical retro deliverable: evaluation of multi-prefix methodology effectiveness.

---

## §3 Commits plan

| Commit | Scope | Conditional |
|---|---|---|
| **C1** | docs(probes): Sprint T-Retry multi-prefix probe results 5 countries | always |
| **C2** | feat(connectors): te.py TE_YIELD_CURVE_SYMBOLS multi-prefix extension for S1-upgraded countries | conditional (≥1 S1 upgrade) |
| **C3** | refactor(pipelines): daily_curves T1 tuple extension | conditional (≥1 S1 upgrade) |
| **C4** | test: regression coverage S1-upgraded countries + multi-prefix support | conditional |
| **C5** | ops: backfill Apr 21-24 verification | conditional (ops only, no commit) |
| **C6** | docs(adr,backlog): ADR-0009 v2.2 → v2.3 multi-prefix amendment + Path 2 CAL updates | always |
| **C7** | docs(planning): Sprint T-Retry retrospective + pattern library v2.3 assessment | always |

---

## §4 HALT triggers

**HALT-pre-flight**:
- TE quota >50% April consumption after probe first 100 calls → HALT, defer Day 2+

**HALT-0 (per-country, expected for some)**:
- All 5 countries confirm HALT-0 across multi-prefix — methodology gap empirically closed but zero coverage upgrade. Retro documents finding. Still value — ADR-0009 v2.3 amendment canonical.

**HALT-material**:
- TE probe PASS but NSS fit fails per newly-discovered symbols → HALT that country, investigate data quality
- Multi-prefix discovery reveals >50 new symbols per country → scope explosion. Focus on top-3 candidate prefixes only, document residuals.
- DB unique constraint violation despite ADR-0011 P1 → STOP

**HALT-scope**:
- Temptation to also re-probe NL (Sprint M HALT-0, pending Week 11 Path 2) → STOP. NL has separate CAL-CURVES-NL-DNB-PROBE pathway.
- Temptation to extend to T2 countries → STOP (ADR-0010 T1 only)
- Temptation to upgrade M-layer for new S1 countries → STOP (curves only, M-layer separate sprint if needed)

**HALT-security**: standard.

---

## §5 Acceptance

### Tier A — pre-merge (CC scope, v3.3 compliance)

1. **Probe doc shipped**:
   ```bash
   test -f docs/backlog/probe-results/sprint-t-retry-multi-prefix-probe.md && \
     wc -l docs/backlog/probe-results/sprint-t-retry-multi-prefix-probe.md
   ```
   Expected: ≥80 lines (5 countries × multi-prefix × tenors matrix).

2. **S1 countries shipped** (if any):
   ```bash
   sqlite3 data/sonar-dev.db \
     "SELECT country_code, MAX(date), COUNT(*) FROM yield_curves_spot WHERE country_code IN (<s1_upgraded_list>) GROUP BY country_code;"
   ```
   Expected: Apr 21/22/23/24 present, NSS fit successful.

3. **S2 confirmed countries documented** (for countries that remain HALT-0):
   CALs updated with Sprint T-Retry confirmation stamp.

4. **Regression tests**:
   ```bash
   uv run pytest tests/unit/test_connectors/test_te.py tests/unit/test_pipelines/test_daily_curves.py -v
   ```
   Expected: all pass.

5. **Local CLI T1 coverage**:
   ```bash
   uv run python -m sonar.pipelines.daily_curves --all-t1 --date 2026-04-24 2>&1 | \
     grep "daily_curves.summary"
   ```
   Expected: N + K countries (N pre-Retry = 11, K = S1-upgraded), n_failed=0.

6. **Bash wrapper smoke** (Lesson #12 Tier A).

7. **Pre-commit clean double-run** (Lesson #2).

### Tier B — post-merge (operator scope, ~ Day 2 morning natural fire verify)

1. **Systemd curves service verify**:
   ```bash
   sudo systemctl reset-failed sonar-daily-curves.service
   sudo systemctl start sonar-daily-curves.service
   sleep 120
   sudo journalctl -u sonar-daily-curves.service --since "-3 min" --no-pager | grep "daily_curves.summary"
   ```
   Expected: N+K countries, n_failed=0.

2. **DB coverage**:
   ```bash
   sqlite3 data/sonar-dev.db \
     "SELECT country_code, MAX(date) FROM yield_curves_spot GROUP BY country_code;"
   ```
   Expected: 11 + K countries, all Apr 24.

3. **Timer armed**.

---

## §6 Retro scope

Documentar em `docs/planning/retrospectives/week11-sprint-t-retry-multi-prefix-probe-report.md`:

### Empirical outcomes table

5-country multi-prefix matrix: all prefix candidates probed, tenor counts per prefix, S1/S2 classification decision rationale.

### Multi-prefix methodology validation

- **Correctness**: did multi-prefix surface symbols single-prefix missed (Sprint T Discovery #1-#2)?
- **Coverage delta**: S1 upgrade rate = K/5 = <K×20>% of Sprint T HALT-0 were false negatives
- **TE exhaustive discovery finding**: is `/markets/historical` direct endpoint gold-standard vs `/search`? Document.

### Pattern library v2.3 amendment shipped

- "Multi-prefix + multi-suffix probe MUST be attempted before S2 declaration"
- "/search is high-recall not exhaustive — use as hint, not final word"
- "Direct `/markets/historical/country/<country>/indicator/` endpoint is final arbiter"

### T1 coverage delta Week 11

- Pre-Retry: 11/16 L2 curves
- Post-Retry: (11+K)/16 L2 curves
- Phase 2 trajectory update

### Sprint T retrospective closure

Sprint T methodology gap closed. Pattern library v2.3 codified. Future sparse-T1 probes benefit from this empirical foundation.

---

## §7 Execution notes

- **Probe discipline** (ADR-0009 v2 canonical): C1 probe MUST precede C2/C3 regardless of S1/S2 distribution
- **Zero overlap with Sprint Q.1**: Q.1 touches ECB SDW + overlays, T-Retry touches TE + curves. Safe paralelo.
- **TE quota awareness**: ~300-400 probes expected. Baseline ~29% April. Budget ceiling ~50% post-Retry.
- **Multi-prefix per country structure**: te.py convention for multi-prefix (tuple of prefixes) vs single-prefix (string). Preserve backward compat for existing 11 countries (single-prefix pattern).
- **sprint_merge.sh Step 10** cleanup (Lesson #4)
- **CC arranque template** (Lesson #5)
- **DB symlink** auto-provisioned (Lesson #14)
- **Pre-commit double-run** (Lesson #2)
- **Pre-stage pre-commit** (Lesson #16 Day 3 prevention)

---

## §8 Dependencies & CAL interactions

### Parent sprint
Sprint T (Week 10 Day 3) — 5 HALT-0 countries flagged for Retry + Discoveries §9 methodology gaps

### CAL items closed by this sprint (per S1 upgrade)
- `CAL-CURVES-NZ-PATH-2` (if S1 upgrade)
- `CAL-CURVES-CH-PATH-2` (if S1 upgrade)
- `CAL-CURVES-SE-PATH-2` (if S1 upgrade)
- `CAL-CURVES-NO-PATH-2` (if S1 upgrade)
- `CAL-CURVES-DK-PATH-2` (if S1 upgrade)

### CAL items updated by this sprint (per S2 confirmed)
- Remaining S2 CALs get "Sprint T-Retry confirmation stamp" for Week 11+ Path 2 cohort sprint

### Sprints blocked by this sprint
- **None** — paralelo com Sprint Q.1

### Sprints unblocked by this sprint
- **Week 11+ Path 2 cohort sprint** — clear empirical basis for which countries genuinely need Path 2 (vs methodology false-negatives)
- **Future ADR-0009 applications**: pattern library v2.3 compound value

---

## §9 Time budget

Arranque target: Day 1 ~14:15 WEST (paralelo Sprint Q.1).
Hard stop: 17:15 WEST (3h wall-clock).

Realistic range:
- **Best case 2h**: multi-prefix probe clean, 0-1 S1 upgrades, no code changes needed
- **Median 2.5-3h**: 1-2 S1 upgrades, te.py symbol table extension + daily_curves tuple update + tests
- **Worst case HALT**: scope explosion via >50 symbols per country → focus top-3 candidates, document residuals

---

*End of brief. Methodology gap closure sprint. Paralelo Sprint Q.1. Ship disciplined with ADR-0009 v2.3 amendment.*
