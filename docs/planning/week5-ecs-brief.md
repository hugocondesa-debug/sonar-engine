# Week 5 ECS Track — E1 Activity + E3 Labor + E4 Sentiment

**Target**: 3 economic indices shipped for 7 T1 countries (E1, E3, E4)
**Priority**: HIGH (unblocks ECS composite Week 6; adds 3 L3 indices → 13/16)
**Budget**: 6–8h CC autonomous
**Commits**: ~11–13
**Base**: main HEAD post F-cycle (`5a42b15` or later)
**Concurrency**: Parallel to Sprint 1 F-cycle live wiring in tmux `sonar-l3`. See §Concurrency.

---

## 1. Scope

In:
- `src/sonar/indices/economic/` package (E2 already exists from Week 3.5)
  - `e1_activity.py` — E1 Activity coincident index per `E1_ACTIVITY_v0.1`
  - `e3_labor.py` — E3 Labor market depth per `E3_LABOR_v0.1`
  - `e4_sentiment.py` — E4 Sentiment & expectations per `E4_SENTIMENT_v0.1`
- New connectors as needed:
  - `connectors/eurostat.py` — Eurostat SDMX client (namq_10_gdp, sts_inpr_m, lfsi_emp_m, sts_trtu_m, etc.)
  - `connectors/spglobal_pmi.py` — S&P Global PMI composite/manufacturing/services (where accessible — may need scraping or markiteconomics)
  - `connectors/ism.py` — ISM Manufacturing + Services PMI (US-specific, ISM doesn't publish API — scrape preferred pages)
  - Existing `connectors/fred.py` extension: add series IDs for PAYEMS, RRSFS, W875RX1, UNRATE, JTSJOL, CES0500000003, ICSA, TEMPHELPS, UMCSENT, CONCCONF, etc.
- Alembic migration **012** — 3 dedicated tables per spec §8 (+ economic indices table registry in models.py)
- Orchestrator extension: `compute_all_economic_indices(country, date, session)` — includes existing E2 + new E1/E3/E4
- Integration test 7 T1 countries
- Retrospective

Out:
- E2 Leading (already shipped Week 3.5 — `e2_leading.py`)
- ECS composite computation (Week 6+ after all 4 E-indices shipped)
- UK Office for National Statistics connector (T2 scope, deferred)
- Tier 4 EM coverage (Phase 2+)
- Real-time / streaming updates (daily cadence sufficient)

---

## 2. Spec reference

Authoritative (verified 2026-04-20):
- `docs/specs/indices/economic/E1-activity.md` @ `E1_ACTIVITY_v0.1`
- `docs/specs/indices/economic/E3-labor.md` @ `E3_LABOR_v0.1`
- `docs/specs/indices/economic/E4-sentiment.md` @ `E4_SENTIMENT_v0.1`
- `docs/specs/indices/economic/README.md` (z-score 10Y rolling; 7Y fallback T4; ECS composite preview)
- `docs/specs/cycles/economic-ecs.md` (downstream consumer — informational)
- `docs/specs/conventions/units.md`, `flags.md`, `exceptions.md`, `patterns.md`
- SESSION_CONTEXT §Decision authority + §Brief format + §Regras operacionais

**Pre-flight requirement**: Commit 1 CC reads each of E1/E3/E4 specs end-to-end. Document in commit body any material deviation from brief §3 assumptions. If ≥ 2 specs deviate materially → HALT trigger #0 fires, chat reconciles.

Canonical normalization per README (applies all 3 indices + existing E2):
- z-score vs 10Y rolling window (canonical) / 7Y Tier 4 fallback
- aggregate sub-scores per index weights (per spec §4)
- output: `clip(50 + 16.67 · z_aggregate, 0, 100)`
- INSUFFICIENT_HISTORY flag + confidence cap when window tight

---

## 3. Concurrency — parallel protocol with Sprint 1 F-cycle

Sprint 1 runs concurrently in tmux `sonar-l3`. Both push to main.

**Hard-locked resource allocation**:
- Migration number: **012** (Sprint 1 doesn't create migrations — no collision)
- `src/sonar/db/models.py`: this brief touches Indices bookmark zone (new ORMs E1Result, E3Result, E4Result). Sprint 1 doesn't touch models.py. Zero overlap.
- `src/sonar/connectors/`: this brief creates `eurostat.py`, `spglobal_pmi.py`, `ism.py` (new files) + extends `fred.py`. Sprint 1 modifies `move_index.py`, `aaii.py`, `cftc_cot.py` (different files). Zero overlap except `fred.py` — **caution needed**.
  - `fred.py` extension risk: if both briefs modify `fred.py` simultaneously (Sprint 1 might add FRED-based MOVE fallback), rebase conflict possible.
  - Mitigation: ECS adds FRED series IDs to a **new section** in `fred.py` clearly marked `# === Economic indicators ===`. Sprint 1 shouldn't touch fred.py per its brief §2 (MOVE goes via Yahoo, not FRED).
- Tests: separate subdirectories/filenames — zero overlap
- Cassettes: both may add — separate filenames per connector
- `pyproject.toml`: ECS may add `sdmx1>=2.16` or similar for Eurostat parsing. Sprint 1 may add xls parsing lib. If both modify simultaneously, rebase.

**Push race handling**:
- Normal `git pull --rebase origin main` on rejection
- `fred.py` conflict possible but unlikely — both briefs scoped to separate add-only sections

---

## 4. Commits

### Commit 1 — Economic indices scaffold + ORM models

```
feat(indices): E1/E3/E4 scaffold + ORMs in models.py Indices zone

Extend src/sonar/indices/economic/ package:
- __init__.py: add E1/E3/E4 exports alongside existing e2_leading
- exceptions.py: InsufficientInputsError per-index if custom
- Per-index modules scaffolded with dataclass skeletons

In src/sonar/db/models.py inside # === Indices models === bookmark:
- E1ActivityResult, E3LaborResult, E4SentimentResult ORM classes
- Shared EconomicIndexMixin for common columns (country_code, date,
  methodology_version, score_normalized, score_raw, components_json,
  lookback_years, confidence, flags, source_connector, created_at,
  UNIQUE (country_code, date, methodology_version))
- Per-spec extras per §8:
  - E1: gdp_yoy, ip_yoy, employment_yoy, retail_yoy, income_yoy,
    pmi_composite, pmi_band
  - E3: unemployment_rate, unemployment_zscore, sahm_rule_value,
    sahm_rule_triggered, claims_4wma, claims_zscore, labor_state
  - E4: umich_z, cb_confidence_z, ism_z, epu_z, esi_z, sentiment_state

Sanity check (per v3 brief lessons): commit body MUST include output of:
  python -c "from sonar.db.models import E1ActivityResult, E3LaborResult, E4SentimentResult; print('OK')"

No migration yet — Commit 2.
```

### Commit 2 — Alembic migration 012 + 3 economic tables

```
feat(db): migration 012 economic indices dedicated tables

3 dedicated tables per spec §8:
- economic_e1_activity_results
- economic_e3_labor_results
- economic_e4_sentiment_results

Common preamble + per-spec extras (see Commit 1).
UNIQUE (country_code, date, methodology_version) each.
CHECK constraints: score_normalized [0,100], confidence [0,1].
Indexes: idx_e{1,3,4}_cd (country_code, date).

Rationale: dedicated tables (not polymorphic index_values) consistent
with credit + financial pattern — typed columns, CHECK constraints,
distinct downstream consumers.

Alembic upgrade/downgrade round-trip clean.

Pre-flight check: verify `alembic heads` shows 011 (CAL-058 head) or
later. If Sprint 1 somehow creates migration (shouldn't per its brief),
this brief rebases to next number.
```

### Commit 3 — Eurostat SDMX connector

```
feat(connectors): Eurostat SDMX connector for EA economic indicators

src/sonar/connectors/eurostat.py subclasses BaseConnector.

Base URL: https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1
Format: JSON (SDMX-JSON 1.0) — no auth required
Rate limit: undocumented; polite usage 2 req/sec

Dataflows relevant to E1/E3/E4:
- namq_10_gdp (quarterly GDP)
- sts_inpr_m (industrial production monthly)
- lfsi_emp_m (employment level monthly)
- sts_trtu_m (retail trade monthly)
- une_rt_m (unemployment rate monthly) — E3 input
- ei_bsco_m (economic sentiment indicator, ESI) — E4 input
- teibs020 (consumer confidence) — E4 input

Public methods:
- fetch_series(dataflow, geo, start_date, end_date, **filters)
  → list[Observation]
- Helper methods per indicator: fetch_gdp(country, ...),
  fetch_industrial_production(country, ...), etc.

Country coverage: EA + individual EU member states by geo code
(DE, PT, IT, ES, FR, NL per T1 7 scope).

Parse SDMX-JSON 1.0 response via json stdlib (avoid sdmx1 dep if
possible — lighter dep footprint).

Tests:
- Cassette-replay unit tests (multi-country × multi-dataflow)
- @pytest.mark.slow live canary (GDP + unemployment + ESI)
- Coverage ≥ 92%

pyproject.toml: no new dep if raw JSON parsing sufficient. If sdmx1
needed → add with rationale.
```

### Commit 4 — S&P Global PMI connector

```
feat(connectors): S&P Global PMI composite + manufacturing + services

src/sonar/connectors/spglobal_pmi.py subclasses BaseConnector.

Source: S&P Global (formerly IHS Markit) PMI releases
Challenge: S&P Global does NOT offer a public API for PMI data.
Options:
  1. Monthly press release scrape from spglobal.com/marketintelligence/
     news/pmi-by-ihs-markit (HTML + structured data)
  2. TradingEconomics as intermediary (paid; existing TE connector)
  3. FRED (limited — FRED has NAPMPMI for ISM Manufacturing US only,
     not S&P Global PMI directly)

Implementation:
- Primary: scrape S&P Global monthly PMI release HTML
- Fallback: TE via existing `connectors/te.py` (using indicators
  endpoint for PMI series per country)
- Graceful DataUnavailableError on scrape failure + flag
  PMI_SCRAPE_FAIL

Country coverage: US, UK, EA (aggregate + DE/FR/IT/ES/NL),
JP, CN, IN, BR, AU.

Cadence: monthly (1st business day of following month)

Tests:
- Cassette-replay unit tests
- Schema stability check
- @pytest.mark.slow live canary (US + EA + DE PMI composite)
- Coverage ≥ 92%

Note: PMI data may require manual cassette recording initially —
scraping is fragile. Document fragility in module docstring.
```

### Commit 5 — ISM Manufacturing + Services connectors (US-specific)

```
feat(connectors): ISM Manufacturing + Services PMI (US)

src/sonar/connectors/ism.py subclasses BaseConnector.

Source: Institute for Supply Management (ISM) US PMI releases
Challenge: ISM does not offer a public API. Data is in monthly
press releases + dashboard-style pages.

Primary path: FRED wraps ISM indices:
- NAPMPMI (ISM Manufacturing PMI, discontinued Q1 2024 by FRED)
- Successor: use NAPM (original name) or series released by ISM
  directly via scrape

Alternatives:
- Scrape ism.org/research/business-surveys/business-index/ monthly
- TE `TE_ISM_*` series via existing TE connector

Implementation:
- Primary: FRED NAPMPMI (continue until confirmed unavailable)
- Fallback: scrape ism.org monthly release
- Graceful DataUnavailableError + flag ISM_UNAVAILABLE

Tests:
- Cassette-replay unit tests
- @pytest.mark.slow live canary
- Coverage ≥ 92%

Scope note: US-specific. EA PMI comes via S&P Global (Commit 4).
```

### Commit 6 — FRED connector extension (economic indicators)

```
feat(connectors): FRED extension for E1/E3/E4 series IDs

Extend src/sonar/connectors/fred.py with new series resolvers in
a new section clearly marked:

# === Economic indicators (E1 Activity, E3 Labor, E4 Sentiment) ===

Series IDs added:
E1 (Activity):
  - GDPC1 (real GDP)
  - INDPRO (industrial production)
  - PAYEMS (non-farm payrolls)
  - RRSFS (real retail sales)
  - W875RX1 (real personal income ex transfers)
  - (PMI US via ISM, not FRED — see Commit 5)

E3 (Labor):
  - UNRATE (unemployment rate)
  - JTSJOL (JOLTS openings)
  - CES0500000003 (average hourly earnings)
  - ICSA (initial claims)
  - TEMPHELPS (temporary help employment)

E4 (Sentiment):
  - UMCSENT (UMich consumer sentiment)
  - CONCCONF (Conference Board consumer confidence)
  - USEPUINDXD (US economic policy uncertainty, EPU)
  - (SLOOS via FRED DRTSCILM if accessible)

Helper methods:
  fetch_gdp_yoy(start_date, end_date)
  fetch_unemployment_rate(start_date, end_date)
  fetch_sentiment_suite(start_date, end_date, indicator_list)
  etc.

All fetches use existing fred.py BaseConnector pattern.
Zero new dependencies.

Coverage on fred.py: ≥ 95% (exceeds hard gate 92%).

Concurrency note: Sprint 1 brief does NOT modify fred.py (MOVE goes via
Yahoo, not FRED). If Sprint 1 unexpectedly touches fred.py, rebase +
merge sections cleanly.
```

### Commit 7 — E1 Activity implementation

```
feat(indices): E1 Activity per E1_ACTIVITY_v0.1

src/sonar/indices/economic/e1_activity.py per spec §4.

Inputs (per spec §2):
- gdp_yoy (FRED GDPC1 for US; Eurostat namq_10_gdp for EA)
- industrial_production_yoy (FRED INDPRO for US; Eurostat sts_inpr_m)
- employment_yoy (FRED PAYEMS for US; Eurostat lfsi_emp_m)
- retail_sales_real_yoy (FRED RRSFS for US; Eurostat sts_trtu_m)
- personal_income_ex_transfers_yoy (FRED W875RX1 for US; EA proxy/None)
- pmi_composite (ISM US; S&P Global PMI for EA — Commit 4)

Compute per spec §4:
1. Fetch all 6 sub-components; require ≥ 4 of 6 non-None
2. YoY % change computation upstream (connectors handle)
3. Per-component z-score vs 10Y rolling (7Y T4 fallback)
4. PMI: threshold-based transformation per Method C (Cap 15.4) — PMI > 50 = expansion bias; convert to z-space via (pmi - 50) / 5 as normalized distance from neutral
5. Aggregate per spec §4 weights (check exact weights; placeholder: GDP 20%, IP 20%, Employment 20%, Retail 15%, Income 10%, PMI 15%)
6. z_aggregate → score_normalized = clip(50 + 16.67·z, 0, 100)
7. pmi_band: contraction (< 48) / neutral (48-52) / expansion (> 52)
8. Flags per spec §6

Countries 7 T1:
- US: full 6-component path (FRED + ISM)
- DE/PT/IT/ES/FR/NL: Eurostat + S&P Global PMI; income may be degraded
  → flag INCOME_PROXY or skip (min 4/6 requirement handles)

Persistence via persist_e1_activity_result helper.

Fixtures per spec §7 if defined; synthetic spec-plausible otherwise.

Behavioral tests ≥ 18; coverage ≥ 90%.
```

### Commit 8 — E3 Labor implementation

```
feat(indices): E3 Labor per E3_LABOR_v0.1

src/sonar/indices/economic/e3_labor.py per spec §4.

Inputs (per spec §2):
- unemployment_rate (FRED UNRATE for US; Eurostat une_rt_m)
- sahm_rule_components: 3mo avg unemployment rate - min over last 12mo
  (compute internally from unemployment_rate series)
- jolts_openings_rate (FRED JTSJOL / PAYEMS; EA limited)
- wage_growth_yoy (FRED CES0500000003 for US; Eurostat wage indices)
- initial_claims_4wma (FRED ICSA 4-week moving average; US only)
- temp_help_employment_yoy (FRED TEMPHELPS; US only)

Compute per spec §4:
1. Sahm Rule: triggered if 3mo avg UR - 12mo min ≥ 0.5pp (Method C binary)
2. Unemployment z-score 10Y rolling (Method A)
3. JOLTS openings rate z-score
4. Wage growth z-score
5. Initial claims z-score (high claims = weak labor; sign-flip)
6. Temp help z-score (leading indicator of payroll direction)
7. Aggregate per spec weights (placeholder: Sahm 25%, Unemployment 20%, JOLTS 20%, Wages 15%, Claims 10%, Temp 10%)
8. labor_state: recession (Sahm triggered OR z < -2) / cooling (z -2 to -1) / trend (z -1 to +1) / tight (z +1 to +2) / overheated (z > +2)
9. Flags per spec §6

Countries 7 T1:
- US: full 6-component path
- DE/PT/IT/ES/FR/NL: unemployment + wages available via Eurostat; JOLTS/claims/temp help US-only → degraded path flagged SAHM_US_ONLY, CLAIMS_US_ONLY

Behavioral tests ≥ 18; coverage ≥ 90%.
```

### Commit 9 — E4 Sentiment implementation

```
feat(indices): E4 Sentiment per E4_SENTIMENT_v0.1

src/sonar/indices/economic/e4_sentiment.py per spec §4.

Inputs (per spec §2):
- umich_sentiment (FRED UMCSENT; US)
- conference_board_confidence (FRED CONCCONF; US)
- ism_pmi (US; from ism.py connector)
- epu_index (FRED USEPUINDXD; US)
- ec_esi (Eurostat ei_bsco_m; EA countries)
- zew_indicator (Eurostat or scrape; DE) — optional, flag ZEW_UNAVAILABLE if absent
- ifo_business_climate (Bundesbank or scrape; DE) — optional
- tankan_business_conditions (JP, out of scope 7 T1)
- vix (from cboe.py; already live) — E4 component per spec §2
- sloos_tightening (FRED DRTSCILM; US)

Compute per spec §4:
1. Per-component z-score 10Y rolling
2. PMI: threshold transformation (same as E1)
3. Aggregate per spec weights (placeholder: UMich 15%, CB 15%, ISM 15%, EPU 10%, ESI 15%, ZEW/Ifo 10%, VIX 10%, SLOOS 10%)
4. Weight redistribution when country-specific components None (e.g., EA gets ESI instead of UMich+CB)
5. sentiment_state: panic (z < -2) / pessimistic (-2 to -1) / neutral (-1 to +1) / optimistic (+1 to +2) / euphoric (> +2)
6. Flags per spec §6

Countries 7 T1:
- US: UMich + CB + ISM + EPU + VIX + SLOOS (6 live)
- DE: ESI + Ifo + ZEW + VIX (+ EPU optional)
- PT/IT/ES/FR/NL: ESI + VIX (partial)

US_PROXY flags where applicable per brief §9.

Behavioral tests ≥ 18; coverage ≥ 90%.
```

### Commit 10 — Orchestrator extension + CLI flags

```
feat(indices): economic orchestrator + --economic-only CLI

src/sonar/indices/orchestrator.py extension:
- compute_all_economic_indices(country, date, session) runs E1 (new),
  E2 (existing Week 3.5), E3 (new), E4 (new) in parallel — no
  inter-E dependencies per spec (E2 is slope-based, E1/E3/E4 are
  composite indicator panels)

CLI extensions:
- --economic-only flag: runs only E1/E2/E3/E4
- --all-cycles extended: credit + financial + economic (12 indices
  for 7 T1 = 84 rows per date)

python -m sonar.indices.orchestrator --country US --date 2024-01-02 \
       --economic-only → 4 rows (E1, E2, E3, E4)
```

### Commit 11 — Integration test 7 T1 countries

```
test(integration): E1-E4 vertical slice 7 T1 countries

tests/integration/test_economic_indices.py:
- 7-country parametrized (US/DE/PT/IT/ES/FR/NL) for 2024-01-02 or
  2024-02-29 (more recent month-end with Eurostat data available)
- Cassette-replayed Eurostat + FRED + PMI fetches
- Assert each country produces E1+E2+E3+E4 minimum
- Assert all score_normalized ∈ [0, 100]
- Assert confidence ∈ [0, 1]
- Assert degraded paths flagged correctly (JOLTS_US_ONLY,
  UMICH_US_ONLY, SLOOS_US_ONLY where expected)
- Persistence round-trip: 28 rows total (4 indices × 7 countries)

≥ 14 integration tests.
```

### Commit 12 — Daily economic indices pipeline

```
feat(pipelines): daily_economic_indices.py L6 pipeline

src/sonar/pipelines/daily_economic_indices.py mirrors
daily_financial_indices.py + daily_credit_indices.py pattern:
- Pluggable InputsBuilder (default empty bundle)
- Orchestrate E1-E4 computation per country × date
- Batch persist via persist_many_economic_results helper
- CLI: python -m sonar.pipelines.daily_economic_indices \
         --country US --date 2024-01-02 [--all-t1]
- Exit codes per established pattern

Live builder deferred as CAL item (mirrors CAL-058 pattern) —
production run uses DbBackedInputsBuilder when ingestion pipeline
for Eurostat + FRED economic series is built (Week 6+ scope).

Tests: test_daily_economic_indices.py ≥ 6 unit.
```

### Commit 13 — Retrospective

```
docs(planning): Week 5 ECS track retrospective

File: docs/planning/retrospectives/week5-ecs-indices-report.md

Structure per prior retrospectives:
- Summary (duration, commits, status)
- Commits table with SHAs + CI status
- Coverage delta per scope
- Tests breakdown (E1 + E3 + E4 + connectors + integration)
- 7-country 2024-01-02 snapshot: E1/E2/E3/E4 score_normalized +
  states + flags
- Connector validation: Eurostat + S&P Global PMI + ISM + FRED ext
- HALT triggers fired/not fired
- Deviations from brief
- New backlog items
- ECS composite readiness: E1/E2/E3/E4 operational → composite is next
- Blockers for Week 6: ECS composite brief, MSC indices M1/M2/M4,
  then 4 cycles + regime classifier

Close relevant CAL items if any surfaced during implementation.
```

---

## 5. HALT triggers (atomic)

0. **Pre-flight spec deviation** — CC reads E1/E3/E4 specs Commit 1 and finds ≥ 2 materially deviate → HALT
1. **Eurostat SDMX schema drift** — dataflow key unexpected format (similar to BIS CAL-019 pattern) → debug via structure endpoint
2. **S&P Global PMI scrape fails** — HTML layout changed → fallback TE connector; if TE also unreliable, flag PMI_PROXY_TE + continue
3. **ISM FRED series discontinued** (NAPMPMI depreciation) → fallback scrape ism.org; if both fail, US E1/E4 degrade (pmi_composite None; 5/6 components for E1)
4. **VIX source inconsistency** — E4 uses VIX via CBOE connector; Sprint 1 may be modifying CBOE — verify no conflict
5. **Eurostat rate limit** (2 req/sec polite usage insufficient for 7 countries × 6 indicators) → reduce to 1 req/sec + accept longer sprint time
6. **Migration 012 collision** with Sprint 1 (shouldn't happen per brief) → rebase
7. **models.py rebase conflict** outside Indices bookmark → Sprint 1 violated discipline (unlikely — Sprint 1 doesn't touch models.py per its brief)
8. **fred.py rebase conflict** on Commit 6 — Sprint 1 added unexpected FRED calls → reconcile Economic section cleanly
9. **Coverage regression > 3pp** on connectors or indices scope → HALT
10. **Pre-push gate fails** → fix before push, no `--no-verify`

"User authorized in principle" does NOT cover specific triggers.

---

## 6. Acceptance

### Per commit
Commit body checklist enforceable (tests count, canaries count per connector, cassettes count).

### Global sprint-end
- [ ] 11-13 commits pushed, main HEAD matches remote, all CI green
- [ ] Migration 012 applied clean; downgrade/upgrade round-trip green
- [ ] 3 new index modules (E1/E3/E4) + existing E2 remain operational
- [ ] `src/sonar/indices/economic/` coverage ≥ 90% per module
- [ ] 3 new connectors (eurostat, spglobal_pmi, ism) + fred.py extension each coverage ≥ 92%
- [ ] 7 T1 countries produce E1+E2+E3+E4 rows for 2024-01-02 (degraded paths flagged appropriately)
- [ ] `python -m sonar.indices.orchestrator --country US --date 2024-01-02 --economic-only` → 4 rows
- [ ] `python -m sonar.indices.orchestrator --country US --date 2024-01-02 --all-cycles` → 12 rows (4 credit + 4 financial + 4 economic)
- [ ] Full test suite green: ≥ 650 unit + ≥ 40 integration tests
- [ ] No `--no-verify` pushes
- [ ] Pre-push gate enforced before every push

---

## 7. Report-back artifact export (mandatory)

File: `docs/planning/retrospectives/week5-ecs-indices-report.md`

Structure per existing retrospective template.

**Per-commit tmux echoes** (short form):
```
COMMIT N/11-13 DONE: <scope>, SHA, coverage delta, tests added, HALT status
```

**Final tmux echo**:
```
ECS TRACK DONE: N commits, 3 indices (E1/E3/E4) × 7 countries operational
3 new connectors (Eurostat/S&P Global PMI/ISM) + FRED extension
HALT triggers: [list or "none"]
Artifact: docs/planning/retrospectives/week5-ecs-indices-report.md
```

---

## 8. Pre-push gate (mandatory per CI-debt saga lessons)

Before every `git push`:
```
uv run ruff format --check src/sonar tests
uv run ruff check src/sonar tests
uv run mypy src/sonar
uv run pytest tests/unit/ -x --no-cov
```

All four exit 0. No `--no-verify`.

---

## 9. Notes on implementation

### Eurostat is key
Eurostat connector enables all 6 EA T1 countries for economic indicators. Without it, ECS is essentially US-only. Prioritize Commit 3 robustness.

### S&P Global PMI fragility
Scraping is inherent fragility. Module docstring MUST document this + point at TE fallback path. CAL entry if fragility manifests in production.

### ISM discontinuation risk
FRED discontinued NAPMPMI in Q1 2024. Verify current state in Commit 5 implementation. May need direct ism.org scrape as primary going forward.

### Sahm Rule is special
E3 Sahm Rule is binary (Method C — threshold-based). Wraps in z-space as `+2` when triggered, `0` otherwise — or emit as separate sub-indicator channel. Check spec §4 for exact handling.

### Weight redistribution vs degraded path flag
When country-specific components unavailable (e.g., JOLTS only US), weights redistribute to remaining components. Flag emitted but index still computes. Spec handles this per §6.

### US_PROXY flags
Per SESSION_CONTEXT §Princípios operacionais. Composite consumers cap confidence when present. Document in each spec amendment if needed.

### Parallel Sprint 1 track
Runs in tmux `sonar-l3`. Zero overlap except `fred.py` (low risk). Pre-push gate catches issues.

---

*End of ECS brief. 3 indices + 3 new connectors + FRED extension + orchestrator + pipeline + integration + retrospective. Budget 6-8h. Concurrency with Sprint 1 via migration + bookmark + connector file separation.*
