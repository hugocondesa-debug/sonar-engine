# Week 10 Day 2 Sprint L — CAL-M2-EA-AGGREGATE (EA Aggregate M2 Composite)

**Tier scope**: T1 ONLY (16 countries). T2 expansion deferred to Phase 5 per ADR-0010.

**Target**: Ship EA aggregate M2 Taylor-gap composite. EA is T1 per country_tiers.yaml (aggregate representation of 6 EA member states). CAL opened Sprint F post-closure (`CAL-M2-EA-AGGREGATE` Phase 2+ scope). Completes M2 T1 coverage: 10 (existing full compute) + 1 (EA aggregate) = 11/16 T1.
**Priority**: MEDIUM-HIGH (closes Sprint F residual CAL; completes M2 T1 aggregate coverage; unblocks MSC aggregate composite Week 11+)
**Budget**: 2-3h CC
**Commits**: ~4-5
**Base**: branch `sprint-m2-ea-aggregate` (isolated worktree `/home/macro/projects/sonar-wt-m2-ea-aggregate`)
**Concurrency**: PARALELO with Sprint H (IT + ES TE cascade curves). Zero primary file overlap (M2 monetary vs curves).

**Brief format**: v3

---

## 1. Scope

In (3 tracks):

### Track 1 — EA aggregate inputs (~1-1.5h)
EA aggregate M2 Taylor gap composite requires 3 inputs at EA-aggregate level:

1. **Output gap (EA17/EA19/EA20)** — already available via OECD EO (Sprint C shipped connector with EA aggregate support)
2. **HICP YoY (EA aggregate)** — ECB SDW ICP dataflow OR TE generic HICP indicator for EA area
3. **Inflation forecast (EA aggregate)** — ECB SPF (Survey of Professional Forecasters) OR TE inflation forecast for EA area

**Probe decision**: use TE primary (consistent with Sprint F per-country pattern) + ECB SDW fallback if TE sparse.

Extend connectors:
- `src/sonar/connectors/te.py` APPEND (CPI section):
  - `fetch_ea_hicp_yoy(observation_date)` → EA HICP YoY
  - `fetch_ea_inflation_forecast(observation_date)` → EA 12m ahead forecast
- OR if TE sparse for EA aggregate: `src/sonar/connectors/ecb_sdw.py` EXTEND with HICP + SPF methods

### Track 2 — M2 EA aggregate builder (~1h)
- `src/sonar/indices/monetary/builders.py` MODIFY:
  - `build_m2_ea_inputs(fred, te, observation_date, *, oecd_eo=None, ecb_sdw=None)` → M2Inputs
  - Mirror per-country pattern from Sprint F (build_m2_de_inputs etc.)
  - Fallback cascade: OECD EO EA aggregate → OECD EO EA19 → OECD EO EA20 → ECB SDW aggregate GDP + SONAR HP filter
  - Flag emissions:
    - `EA_M2_OECD_EO_LIVE`
    - `EA_M2_HICP_TE_LIVE` or `EA_M2_HICP_ECB_SDW_FALLBACK`
    - `EA_M2_INFLATION_FORECAST_TE_LIVE` or `EA_M2_INFLATION_FORECAST_ECB_SPF_FALLBACK`
    - `EA_M2_FULL_COMPUTE_LIVE` (all 3 components operational)

### Track 3 — Pipeline integration + tests + retro (~30min-1h)
- `src/sonar/pipelines/daily_monetary_indices.py` MODIFY:
  - Add EA to MONETARY_SUPPORTED_COUNTRIES tuple (if not already; EA may already be in M1 scope from Week 9)
  - M2 dispatcher routes EA → build_m2_ea_inputs
- Cassettes: TE EA aggregate CPI + inflation forecast (2-3 cassettes)
- Live canary @pytest.mark.slow: EA M2 2024-12-31 persisted with FULL_COMPUTE_LIVE flag
- Update `_classify_m2_compute_mode` to recognize EA aggregate (mirror per-country logic)
- CAL-M2-EA-AGGREGATE CLOSED
- Retrospective per v3 format

Out:
- EA per-country M2 expansion (CAL-M2-EA-PER-COUNTRY opened Sprint F; separate sprint)
- MSC composite EA aggregate (depends M1 + M2 + M3 + M4 EA — sequential sprints)
- Historical HICP/SPF backfill (Phase 2.5 backtest scope)
- Real-time ECB SPF parsing (SPF published quarterly — document monthly-forward-latest retrieval pattern)

---

## 2. Spec reference

Authoritative:
- `docs/specs/indices/monetary/M2-taylor-gaps.md` — M2 methodology (country-agnostic applies to aggregate)
- `docs/backlog/calibration-tasks.md` — CAL-M2-EA-AGGREGATE entry (opened Sprint F)
- `docs/planning/retrospectives/week10-sprint-m2-output-gap-report.md` — Sprint C OECD EO with EA aggregate support (EA17 mapping confirmed)
- `docs/planning/retrospectives/week10-sprint-cpi-infl-t1-report.md` — Sprint F CPI + inflation pattern per country
- `src/sonar/connectors/oecd_eo.py` — existing connector with OECD_EO_COUNTRY_MAP including EA17
- `src/sonar/connectors/te.py` — existing CPI + inflation forecast wrappers per country (Sprint F pattern template)
- `src/sonar/connectors/ecb_sdw.py` — existing ECB SDW connector (HICP + SPF extension may be needed)
- `src/sonar/indices/monetary/builders.py` — existing M2 per-country builders (Sprint F)
- `docs/adr/ADR-0010-t1-complete-before-t2-expansion.md` — tier scope lock (EA is T1)

**Pre-flight requirement**: Commit 1 CC:
1. Read Sprint F retrospective + M2 per-country builder pattern
2. Probe TE EA aggregate CPI + inflation forecast:
   ```bash
   set -a && source .env && set +a

   # EA HICP YoY
   curl -s "https://api.tradingeconomics.com/historical/country/euro%20area/indicator/inflation%20rate?c=${TE_API_KEY}&format=json&d1=2024-12-01&d2=2024-12-05" | jq '.[0]'

   # EA inflation forecast
   curl -s "https://api.tradingeconomics.com/forecast/country/euro%20area/indicator/inflation%20rate?c=${TE_API_KEY}&format=json" | jq '.[0]'
   ```
3. Verify OECD EO EA17 aggregate output gap works (Sprint C implementation):
   ```bash
   # Sprint C should have this. Verify quickly:
   curl -s "https://sdmx.oecd.org/public/rest/data/OECD.ECO.MAD,DSD_EO@DF_EO/A.EA17.GDPV+GDPVTR?format=jsondata&startPeriod=2023&endPeriod=2024" | head -50
   ```
4. Decide HICP source:
   - TE EA inflation: if ≥ 10 years historical + daily/monthly → TE primary
   - Else: ECB SDW HICP ICP dataflow fallback
5. Document findings Commit 1 body.

**Pre-flight HALT trigger**: if OECD EO EA17 aggregate returns empty (Sprint C confirmed works, but verify) OR TE EA CPI sparse, narrow scope per HALT precedent Sprints A/D/G.

---

## 3. Concurrency — PARALELO with Sprint H

**Sprint L worktree**: `/home/macro/projects/sonar-wt-m2-ea-aggregate`
**Sprint L branch**: `sprint-m2-ea-aggregate`

**Sprint H (for awareness)**: IT + ES yield curves via TE cascade, worktree `/home/macro/projects/sonar-wt-curves-it-es-te`

**File scope Sprint L**:
- `src/sonar/indices/monetary/builders.py` MODIFY (primary — build_m2_ea_inputs)
- `src/sonar/connectors/te.py` APPEND (CPI section — EA aggregate wrappers)
- `src/sonar/connectors/ecb_sdw.py` EXTEND (possibly — HICP + SPF fallback)
- `src/sonar/pipelines/daily_monetary_indices.py` MODIFY (M2 dispatch EA)
- `tests/unit/test_connectors/test_te*.py` EXTEND (EA aggregate tests)
- `tests/unit/test_connectors/test_ecb_sdw.py` EXTEND (if HICP/SPF shipped)
- `tests/unit/test_indices/monetary/test_builders.py` EXTEND (M2 EA builder tests)
- `tests/integration/test_daily_monetary_*.py` EXTEND (EA live canary)
- `tests/fixtures/cassettes/te_ea_*.json` NEW
- `docs/backlog/calibration-tasks.md` MODIFY (close CAL-M2-EA-AGGREGATE)
- `docs/planning/retrospectives/week10-sprint-m2-ea-aggregate-report.md` NEW

**Sprint H file scope** (for awareness, DO NOT TOUCH):
- `src/sonar/pipelines/daily_curves.py` (Sprint H primary)

**Potential overlap zones**:
- `src/sonar/connectors/te.py` APPEND — both sprints append. Sprint H appends in **yield** section. Sprint L appends in **CPI/inflation** section. **Bookmark zones**:
  - Sprint H: after existing `fetch_gb_yield_curve_nominal` / `fetch_jp_yield_curve_nominal` / `fetch_ca_yield_curve_nominal` (yield curve section end)
  - Sprint L: after existing Sprint F CPI wrappers (CPI/inflation section end)
  - **Zero conflict** if both sprints respect section boundaries.
- `docs/backlog/calibration-tasks.md` — both modify; different sections (CAL-CURVES-* vs CAL-M2-*); union-merge trivial.

**Zero primary-file conflict expected**.

**Rebase expected minor**: alphabetical merge priority — Sprint H ships first (h < l). Sprint L rebases te.py + CAL file (union-merge trivial).

**Pre-merge checklist** (brief v3 §10):
- [ ] All commits pushed
- [ ] Workspace clean
- [ ] Pre-push gate green
- [ ] Branch tracking set
- [ ] Live canary EA M2 PASS
- [ ] US M2 canonical regression preserved (regression guard mandatory)
- [ ] Tier scope verified T1 only (EA is T1 per ADR-0010)

**Merge execution** (brief v3 §11):
```bash
./scripts/ops/sprint_merge.sh sprint-m2-ea-aggregate
```

---

## 4. Commits

### Commit 1 — Pre-flight + TE EA aggregate CPI wrappers

```
feat(connectors): TE fetch_ea_hicp_yoy + fetch_ea_inflation_forecast + pre-flight

Pre-flight findings (Commit 1 body):
- TE EA aggregate CPI probe:
  [HistoricalDataSymbol + Frequency + historical range]
- TE EA inflation forecast probe:
  [forecast value + horizon + timestamp]
- OECD EO EA17 aggregate output gap verify:
  [confirmed works per Sprint C implementation]
- Decision: TE primary (mirror Sprint F per-country pattern) with ECB SDW fallback if needed

Append to src/sonar/connectors/te.py CPI section:

async def fetch_ea_hicp_yoy(
    self,
    observation_date: date,
    history_days: int = 120,
) -> list[Observation]:
    """EA aggregate HICP YoY via TE Inflation Rate indicator for euro area.

    Source-drift guard: HistoricalDataSymbol validation.
    Returns monthly HICP YoY observations.
    """

async def fetch_ea_inflation_forecast(
    self,
    observation_date: date,
) -> TEInflationForecast:
    """EA aggregate 12-month ahead inflation forecast via TE forecast endpoint.

    Returns latest forecast value + timestamp.
    """

Tests:
- Unit: fetch_ea_hicp_yoy happy path + source-drift guard
- Unit: fetch_ea_inflation_forecast happy path
- @pytest.mark.slow live canary: EA HICP YoY 2024-12-31
- @pytest.mark.slow live canary: EA inflation forecast

Cassettes:
- tests/fixtures/cassettes/te_ea_hicp_yoy_2024_12_31.json
- tests/fixtures/cassettes/te_ea_inflation_forecast_2024_12_31.json

Coverage te.py EA extensions ≥ 90%.
```

### Commit 2 — ECB SDW HICP + SPF fallback (if needed, conditional)

```
feat(connectors): ECB SDW HICP + SPF aggregate fallback

[Conditional: skip if Commit 1 pre-flight confirmed TE sufficient for EA]

Extend src/sonar/connectors/ecb_sdw.py:

async def fetch_hicp_yoy_aggregate(
    self,
    observation_date: date,
) -> list[Observation]:
    """EA aggregate HICP YoY via ECB SDW ICP dataflow.

    Dataflow: ICP (Indice des Prix à la Consommation — harmonized).
    Frequency: monthly.
    """

async def fetch_spf_inflation_forecast_aggregate(
    self,
    observation_date: date,
) -> Observation:
    """EA aggregate 12-month inflation forecast via ECB SPF.

    Published quarterly; returns latest value.
    """

Tests:
- Unit: fetch_hicp_yoy_aggregate mocked
- Unit: fetch_spf_inflation_forecast_aggregate mocked
- @pytest.mark.slow live canaries (optional if TE sufficient)

Cassettes.

Coverage ≥ 85%.

[Skip this commit if TE primary path sufficient]
```

### Commit 3 — M2 EA aggregate builder

```
feat(indices): M2 EA aggregate builder (output_gap + HICP + forecast)

Add to src/sonar/indices/monetary/builders.py:

async def build_m2_ea_inputs(
    fred: FredConnector,
    te: TEConnector,
    observation_date: date,
    *,
    oecd_eo: OECDEOConnector | None = None,
    ecb_sdw: ECBSDWConnector | None = None,
) -> M2Inputs:
    """Build M2 EA aggregate inputs — full compute.

    Mirror Sprint F per-country pattern for EA aggregate.

    Fallback cascade:
    - Output gap: OECD EO EA17 primary → ECB SDW GDP + SONAR HP filter fallback
    - HICP: TE EA primary → ECB SDW ICP fallback
    - Inflation forecast: TE EA primary → ECB SDW SPF fallback
    """
    flags = []

    # Output gap (Sprint C OECD EO EA17)
    output_gap = None
    if oecd_eo:
        try:
            obs = await oecd_eo.fetch_country_output_gap("EA", observation_date)
            if obs:
                output_gap = obs[-1].value
                flags.append("EA_M2_OUTPUT_GAP_OECD_EO_LIVE")
        except (DataUnavailableError, ConnectorError):
            flags.append("EA_M2_OUTPUT_GAP_OECD_EO_UNAVAILABLE")
            # Fallback ECB SDW GDP aggregate + HP filter — defer to Phase 2.5 if needed

    # HICP YoY
    hicp_yoy = None
    try:
        cpi_obs = await te.fetch_ea_hicp_yoy(observation_date)
        if cpi_obs:
            hicp_yoy = cpi_obs[-1].value
            flags.append("EA_M2_HICP_TE_LIVE")
    except (DataUnavailableError, ConnectorError):
        if ecb_sdw:
            try:
                obs = await ecb_sdw.fetch_hicp_yoy_aggregate(observation_date)
                if obs:
                    hicp_yoy = obs[-1].value
                    flags.append("EA_M2_HICP_ECB_SDW_FALLBACK")
            except Exception:
                flags.append("EA_M2_HICP_UNAVAILABLE")

    # Inflation forecast
    inflation_forecast = None
    try:
        forecast = await te.fetch_ea_inflation_forecast(observation_date)
        if forecast:
            inflation_forecast = forecast.value
            flags.append("EA_M2_INFLATION_FORECAST_TE_LIVE")
    except (DataUnavailableError, ConnectorError):
        if ecb_sdw:
            try:
                obs = await ecb_sdw.fetch_spf_inflation_forecast_aggregate(observation_date)
                if obs:
                    inflation_forecast = obs.value
                    flags.append("EA_M2_INFLATION_FORECAST_ECB_SPF_FALLBACK")
            except Exception:
                flags.append("EA_M2_INFLATION_FORECAST_UNAVAILABLE")

    if all([output_gap is not None, hicp_yoy is not None, inflation_forecast is not None]):
        flags.append("EA_M2_FULL_COMPUTE_LIVE")
    else:
        flags.append("EA_M2_PARTIAL_COMPUTE")

    return M2Inputs(
        output_gap=output_gap,
        cpi_yoy=hicp_yoy,
        inflation_forecast=inflation_forecast,
        flags=flags,
    )

Tests:
- Unit: build_m2_ea_inputs happy path (all 3 components available)
- Unit: partial compute (1-2 components missing)
- Unit: both fallbacks exercised
- @pytest.mark.slow live canary: EA M2 2024-12-31 builds FULL_COMPUTE_LIVE

Coverage builders.py EA builder ≥ 90%.

**US M2 CANONICAL REGRESSION GUARD** (per Sprint F precedent):
- Verify US M2 canonical path unchanged post-refactor
- Run test_us_m2_canonical_preserved against existing reference values
- HALT if regression
```

### Commit 4 — Pipeline integration + live canary

```
refactor(pipelines): daily_monetary_indices M2 EA aggregate dispatch

Update src/sonar/pipelines/daily_monetary_indices.py:

1. Add EA to MONETARY_SUPPORTED_COUNTRIES (verify EA already there from Week 9 M1; add if missing)

2. M2 dispatcher:
   - EA → build_m2_ea_inputs (new Commit 3)

3. Connector lifecycle: OECD EO + ECB SDW both already registered (no change)

4. Update _classify_m2_compute_mode:
   - Recognize EA_M2_FULL_COMPUTE_LIVE flag per Sprint F pattern

Tests:
- Unit: dispatcher routes EA correctly
- Unit: --all-t1 includes EA M2 compute
- Integration smoke @slow:
  - EA M2 2024-12-31 persisted
  - FULL_COMPUTE_LIVE flag verified
  - Wall-clock ≤ 15s

M2 T1 coverage post-merge: 10 per-country full compute (Sprint F) + 1 EA aggregate = 11/16 T1.

Coverage daily_monetary_indices.py ≥ 90%.
```

### Commit 5 — CAL closure + retro

```
docs(backlog+planning): Sprint L EA aggregate M2 retrospective + CAL closure

CAL-M2-EA-AGGREGATE CLOSED:
- Status: done (shipped via TE primary + OECD EO EA17 output gap, commit [SHA])
- EA aggregate M2 FULL_COMPUTE_LIVE
- 3-tier fallback per component (TE → ECB SDW → static proxy)

Retrospective per v3 format:
docs/planning/retrospectives/week10-sprint-m2-ea-aggregate-report.md

Content:
- EA aggregate probe outcomes (TE + OECD EO EA17 + ECB SDW if exercised)
- M2 EA full compute validation (all 3 components operational)
- US canonical preservation validated (regression guard test passed)
- Production impact: daily_monetary_indices M2 EA aggregate live tomorrow 07:30 WEST
- M2 T1 coverage 11/16 full compute (+ 5 countries still partial/scaffold)
- §10 pre-merge checklist + §11 merge via script
- Paralelo with Sprint H (IT + ES TE cascade curves): zero file conflicts
- ADR-0010 compliance: EA is T1 (16 countries include EA aggregate per country_tiers.yaml)

Remaining M2 T1 gap:
- EA per-country expansion (CAL-M2-EA-PER-COUNTRY opened Sprint F — Phase 2+ scope)
- 5 countries partial/scaffold per Sprint F retro (review per-country M2 mode matrix)
```

---

## 5. HALT triggers (atomic)

0. **TE EA aggregate CPI probe empty** — ECB SDW fallback path activated; not a HALT.
1. **OECD EO EA17 aggregate empty** — Sprint C implementation claims support; re-verify + HALT if broken.
2. **ECB SDW HICP/SPF extension non-trivial** — if Commit 2 grows beyond 1h, defer to separate sprint; scope narrow Sprint L to TE-only path (conditional on Commit 1 probe result).
3. **US M2 canonical regression** — if Commit 3 regression test fails, HALT. Absolute.
4. **TE EA HICP frequency non-daily** — monthly acceptable for CPI (standard); not a HALT.
5. **Inflation forecast horizon variability** — standardize to 12m where possible; document deviations.
6. **Cassette count < 2** — HALT (minimum TE EA CPI + forecast).
7. **Live canary wall-clock > 20s** — optimize.
8. **Pre-push gate fails** — fix before push.
9. **No `--no-verify`**.
10. **Coverage regression > 3pp** — HALT.
11. **Push before stopping** — script mandates; brief v3 §10.
12. **Sprint H file conflict** — te.py append-only respected (CPI vs yield sections); CAL file union-merge trivial.
13. **ADR-0010 violation** — EA is T1 per country_tiers.yaml; brief header enforces.

---

## 6. Acceptance

### Global sprint-end
- [ ] fetch_ea_hicp_yoy + fetch_ea_inflation_forecast shipped (TE primary)
- [ ] ECB SDW HICP/SPF extension shipped (if needed per pre-flight)
- [ ] build_m2_ea_inputs shipped with 3-tier fallback
- [ ] Pipeline dispatcher routes EA → M2 builder
- [ ] US M2 canonical regression PRESERVED (test_us_m2_canonical_preserved passes)
- [ ] EA M2 FULL_COMPUTE_LIVE flag verified
- [ ] M2 T1 coverage: 10 per-country + 1 EA aggregate = 11/16 T1
- [ ] Cassettes ≥ 2 shipped (TE EA HICP + forecast)
- [ ] Live canary EA M2 @pytest.mark.slow PASS
- [ ] CAL-M2-EA-AGGREGATE CLOSED with commit refs
- [ ] Coverage te.py extensions ≥ 90%, builders.py EA ≥ 90%, daily_monetary_indices.py ≥ 90%
- [ ] No `--no-verify`
- [ ] Pre-push gate green every push
- [ ] §10 Pre-merge checklist executed
- [ ] Merge via `sprint_merge.sh`
- [ ] Retrospective shipped per v3 format
- [ ] ADR-0010 tier scope compliance verified

---

## 7. Report-back artifact

File: `docs/planning/retrospectives/week10-sprint-m2-ea-aggregate-report.md`

**Final tmux echo**:
```
SPRINT L M2 EA AGGREGATE DONE: N commits on branch sprint-m2-ea-aggregate

EA M2 aggregate full compute LIVE:
- Output gap: OECD EO EA17 [value]%
- HICP YoY: TE [value]%
- Inflation forecast: TE [value]% (12m ahead)
- Flag: EA_M2_FULL_COMPUTE_LIVE ✓

US canonical: PRESERVED ✓

M2 T1 coverage post-merge: 11/16 (10 per-country full + 1 EA aggregate).

CAL-M2-EA-AGGREGATE CLOSED.

Production impact: daily_monetary_indices M2 EA aggregate live tomorrow 07:30 WEST.

Remaining M2 T1 gap:
- 5 partial countries (review per Sprint F retro matrix)
- CAL-M2-EA-PER-COUNTRY (6 EA members per-country M2) — Phase 2+ separate sprint

Paralelo with Sprint H (IT + ES TE cascade curves): zero file conflicts.

Merge: ./scripts/ops/sprint_merge.sh sprint-m2-ea-aggregate

Artifact: docs/planning/retrospectives/week10-sprint-m2-ea-aggregate-report.md
```

---

## 8. Pre-push gate (mandatory)

```
uv run ruff format --check src/sonar tests
uv run ruff check src/sonar tests
uv run mypy src/sonar
uv run pytest tests/unit/ -x --no-cov
```

Full project mypy. No `--no-verify`.

Live canaries (@pytest.mark.slow) run explicitly during Commits 1 + 4.

---

## 9. Notes on implementation

### Pattern replication (Sprint F template)
Per-country M2 builder pattern from Sprint F applied to EA aggregate. Minor adjustments (aggregate vs country-specific flags). Trivial ship.

### ECB SDW conditional extension
Commit 2 conditional on Commit 1 pre-flight probe. If TE EA coverage sufficient, skip Commit 2 entirely (saves ~1h per HALT-1 inversion precedent Sprint F).

### EA aggregate country mapping
OECD EO uses EA17 (legacy) or EA19/EA20 codes. Sprint C implementation maps EA → EA17 per empirical probe finding. Sprint L reuses this mapping — no new OECD EO work needed.

### US canonical regression discipline
Per Sprint F precedent (HALT-2 absolute). Regression guard test mandatory Commit 3. Any deviation = HALT.

### Paralelo discipline with Sprint H
Sprint H in te.py **yield section** APPEND. Sprint L in te.py **CPI section** APPEND. Bookmark zones respect. Zero conflict.

### Script merge dogfooded
11th production use Week 10.

### Post-sprint state
- M2 T1 coverage: 11/16 full compute (EA aggregate + 10 per-country from Sprint F)
- Next M2 work: CAL-M2-EA-PER-COUNTRY (Phase 2+) — 6 EA member states per-country (not aggregate)
- Then MSC composite aggregate (requires M1 + M2 + M3 + M4 aggregate; depends M3/M4 T1 uniform)

### Tier scope T1 only
EA is T1 per ADR-0005 country_tiers.yaml. ADR-0010 compliance absolute.

---

*End of Sprint L brief. 4-5 commits. EA aggregate M2 full compute. M2 T1 coverage 11/16. Paralelo-ready with Sprint H.*
