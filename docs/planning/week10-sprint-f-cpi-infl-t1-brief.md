# Week 10 Day 2 Sprint F — CAL-CPI-INFL-T1-WRAPPERS (M2 T1 Full Compute)

**Tier scope**: T1 ONLY (16 countries). T2 expansion deferred to Phase 5 per ADR-0010.

**Target**: Ship CPI YoY + inflation-forecast wrappers per T1 country, flipping 8 M2 scaffolds to **full compute live** (currently output-gap live via Sprint C, CPI/inflation pending). Completes M2 Taylor-gap index T1-wide.
**Priority**: HIGH (Phase 2 exit criterion; completes M2 T1 full compute; unblocks MSC composite multi-country)
**Budget**: 4-6h CC
**Commits**: ~6-8
**Base**: branch `sprint-cpi-infl-t1-wrappers` (isolated worktree `/home/macro/projects/sonar-wt-cpi-infl-t1`)
**Concurrency**: PARALELO with Sprint E (CAL-CURVES-T1-SPARSE-INCLUSION). Different primary files.

**Brief format**: v3

---

## 1. Scope

In (3 tracks):

### Track 1 — Connector wrappers per-country CPI + inflation forecast (~2-3h)
Add country-specific wrappers for CPI YoY actual + inflation forecast (12-month ahead).

**Primary source candidates per country**:
- **TE HICP/CPI**: most countries — `fetch_{country}_cpi_yoy` (TE has generic CPI series ~200 countries)
- **TE inflation forecast**: fetch_{country}_inflation_forecast (TE forecast series consistent)
- **ECB SDW**: EA countries — HICP direct + ECB SPF forecast (Survey of Professional Forecasters)
- **FRED**: US — CPIAUCSL + Michigan expectations (already wired for US M2 canonical)

**Country priority (16 T1)**:
- Already live (US): preserve canonical
- Week 9 priority (CA/AU/NZ/CH/SE/NO/DK) — 7 countries, M2 output-gap live via Sprint C
- EA members (DE/FR/IT/ES/NL/PT) — M2 output-gap live via Sprint C (if OECD EO covers)
- GB/JP — M2 scaffolds exist

**Method**: extend `src/sonar/connectors/te.py` APPEND pattern:
```python
async def fetch_de_cpi_yoy(...) -> list[Observation]:
    """DE CPI YoY via TE (HICP yoy) with source-drift guard."""

async def fetch_de_inflation_forecast(...) -> list[Observation]:
    """DE 12-month ahead inflation forecast via TE."""
```

Replicate for 15 countries (US already wired). Source-drift guards per country (HistoricalDataSymbol validation).

**Alternative paths per country if TE insufficient**:
- ECB SDW for EA HICP + ECB SPF forecast
- National statistics offices (DESTATIS DE, ISTAT IT, INE ES, etc.) — defer

### Track 2 — M2 builders per-country CPI/inflation wiring (~1-2h)
Upgrade `build_m2_{country}_inputs` scaffolds to consume CPI + inflation forecast.

Per country, flip raise-clause from "InsufficientDataError" to:
```python
async def build_m2_de_inputs(fred, te, observation_date, *, oecd_eo=None):
    # Output gap (Sprint C shipped)
    output_gap = await oecd_eo.fetch_country_output_gap("DE", observation_date)

    # CPI YoY (Sprint F)
    cpi_yoy = await te.fetch_de_cpi_yoy(observation_date)

    # Inflation forecast (Sprint F)
    inflation_forecast = await te.fetch_de_inflation_forecast(observation_date)

    # Build M2Inputs with all 3 components
    return M2Inputs(
        output_gap=output_gap,
        cpi_yoy=cpi_yoy,
        inflation_forecast=inflation_forecast,
        ...
    )
```

Replicate for 7-8 countries (Week 9 priority + DE/FR/IT/ES/NL/PT if OECD EO covered).

Flag emissions per country:
- `{CODE}_M2_CPI_TE_LIVE` — primary path
- `{CODE}_M2_CPI_ECB_SDW_FALLBACK` — if TE insufficient for EA members
- `{CODE}_M2_INFLATION_FORECAST_TE_LIVE`
- `{CODE}_M2_INFLATION_FORECAST_NATIONAL_FALLBACK` (if applicable)
- `{CODE}_M2_FULL_COMPUTE_LIVE` — all 3 inputs operational

### Track 3 — Pipeline + tests + retro (~1h)
- `src/sonar/pipelines/daily_monetary_indices.py` — verify M2 dispatch routes per-country
- Cassettes per country (CPI + forecast = ~30 cassettes if 15 countries × 2)
- Live canaries @pytest.mark.slow per country (~15 canaries, combined ≤ 90s)
- CAL-CPI-INFL-T1-WRAPPERS CLOSED
- Retrospective v3 format
- US M2 canonical path PRESERVED (regression test required)

Out:
- M3 market-expectations per-country (separate sprint; depends curves T1 uniform)
- M4 FCI per-country (Phase 2.5 scope)
- MSC composite multi-country (next sprint post M2 T1 full)
- Historical CPI/inflation back-filling (Phase 2.5 backtest scope)
- Currency conversion for MSC (L6 integration scope)

---

## 2. Spec reference

Authoritative:
- `docs/specs/indices/monetary/M2-taylor-gaps.md` — M2 methodology + CPI/inflation inputs
- `docs/backlog/calibration-tasks.md` — CAL-CPI-INFL-T1-WRAPPERS entry
- `docs/planning/retrospectives/week10-sprint-m2-output-gap-report.md` — Sprint C M2 output-gap pattern (mirror for CPI)
- `src/sonar/indices/monetary/builders.py` — current M2 scaffolds per country
- `src/sonar/connectors/te.py` — existing country wrappers pattern (Week 9 M1 shipped)
- `src/sonar/connectors/ecb_sdw.py` — ECB SDW HICP + SPF access (may need extension)
- `docs/adr/ADR-0010-t1-complete-before-t2-expansion.md` — tier scope lock

**Pre-flight requirement**: Commit 1 CC:
1. Read Sprint C M2 output-gap retrospective (template)
2. Probe TE CPI + inflation forecast availability per country:
   ```bash
   set -a && source .env && set +a
   for country in germany united-kingdom japan canada australia new-zealand switzerland sweden norway denmark france italy spain netherlands portugal; do
       echo "=== $country CPI YoY ==="
       curl -s "https://api.tradingeconomics.com/historical/country/$country/indicator/inflation rate?c=$TE_API_KEY&format=json&d1=2024-12-01&d2=2024-12-05" | jq '.[0]'
       echo "=== $country Inflation Forecast ==="
       curl -s "https://api.tradingeconomics.com/forecast/country/$country/indicator/inflation rate?c=$TE_API_KEY&format=json" | jq '.[0]'
   done
   ```
3. Document per-country TE response matrix:
   - HistoricalDataSymbol per country + range
   - Forecast horizon (12m ahead typical)
   - Data frequency (monthly CPI, quarterly/monthly forecast)
4. Identify ECB SDW fallback for EA if TE insufficient:
   - ECB SDW HICP dataflow per EA member
   - ECB SPF forecast dataflow
5. Document findings Commit 1 body. Per ADR-0009 precedent: narrow scope if empirical gaps.

---

## 3. Concurrency — PARALELO with Sprint E

**Sprint F worktree**: `/home/macro/projects/sonar-wt-cpi-infl-t1`
**Sprint F branch**: `sprint-cpi-infl-t1-wrappers`

**Sprint E (for awareness)**: T1 sparse inclusion curves (GB/JP/CA tuple), worktree `/home/macro/projects/sonar-wt-curves-t1-sparse`

**File scope Sprint F**:
- `src/sonar/connectors/te.py` APPEND (primary — CPI + forecast wrappers per country)
- `src/sonar/connectors/ecb_sdw.py` EXTEND (if EA CPI/SPF fallback needed)
- `src/sonar/indices/monetary/builders.py` MODIFY (primary — M2 CPI/inflation wiring)
- `src/sonar/pipelines/daily_monetary_indices.py` MODIFY (M2 dispatch verification)
- `tests/unit/test_connectors/test_te.py` EXTEND (CPI + forecast unit tests per country)
- `tests/unit/test_indices/monetary/test_builders.py` EXTEND (M2 CPI wiring tests)
- `tests/integration/test_daily_monetary_*.py` EXTEND (live canaries CPI per country)
- `tests/fixtures/cassettes/te_*` NEW (CPI + forecast cassettes)
- `docs/backlog/calibration-tasks.md` MODIFY (close CAL-CPI-INFL-T1-WRAPPERS)
- `docs/planning/retrospectives/week10-sprint-cpi-infl-t1-report.md` NEW

**Sprint E file scope** (for awareness, DO NOT TOUCH):
- `src/sonar/pipelines/daily_curves.py` (Sprint E primary — tuple expansion)

**Potential overlap**:
- `src/sonar/connectors/te.py` — Sprint F **APPEND** CPI wrappers; Sprint E **read-only** existing yield wrappers. **No conflict** (append ≠ modify existing).
- `docs/backlog/calibration-tasks.md` — both sprints close CAL items; different sections; union-merge trivial.

**Zero primary-file conflict**:
- Sprint E: `daily_curves.py`
- Sprint F: `daily_monetary_indices.py` + `builders.py` + `te.py` APPEND + `ecb_sdw.py`

**Rebase expected minimal**: alphabetical merge priority → Sprint E ships first (~2-3h budget); Sprint F ships second (~4-6h budget). Sprint F rebases CAL file only.

**Pre-merge checklist** (brief v3 §10):
- [ ] All commits pushed
- [ ] Workspace clean
- [ ] Pre-push gate green
- [ ] Branch tracking set
- [ ] Cassettes + canaries green
- [ ] US M2 canonical preserved (regression guard)
- [ ] Cross-val CPI values vs recent public data documented

**Merge execution** (brief v3 §11):
```bash
./scripts/ops/sprint_merge.sh sprint-cpi-infl-t1-wrappers
```

---

## 4. Commits

### Commit 1 — Pre-flight + TE CPI wrappers Week-9 priority (CA/AU/NZ)

```
feat(connectors): TE CPI YoY + inflation forecast wrappers CA/AU/NZ

Pre-flight findings (Commit 1 body):
- TE CPI per country availability matrix (16 T1):
  [list HistoricalDataSymbol + historical range per country]
- TE inflation forecast per country:
  [list series availability + horizon]
- ECB SDW fallback viability (EA members):
  [HICP dataflow + SPF availability]
- Per-country data source priority decision:
  - CA/AU/NZ: TE primary (broadest generic coverage)
  - EA members: ECB SDW primary if available, TE fallback
  - CH/SE/NO/DK: TE primary
  - GB/JP: TE primary

Extend src/sonar/connectors/te.py APPEND pattern (mirror M1 per-country pattern):

async def fetch_ca_cpi_yoy(
    self,
    observation_date: date,
    history_days: int = 120,
) -> list[Observation]:
    """CA CPI YoY via TE Inflation Rate indicator.

    Source-drift guard: HistoricalDataSymbol validation (CACPIYOY).
    Returns monthly CPI YoY observations.
    """

async def fetch_ca_inflation_forecast(
    self,
    observation_date: date,
) -> Observation:
    """CA 12-month ahead inflation forecast via TE forecast endpoint.

    Returns latest forecast value + timestamp.
    """

Similar for AU (AUCPIYOY), NZ (NZCPIYOY).

Tests:
- Unit: 6 new fetch methods (CA/AU/NZ × CPI + forecast)
- Unit: source-drift guards per country
- @pytest.mark.slow live canaries CA + AU + NZ CPI 2024-12-31
- @pytest.mark.slow live canary CA inflation forecast

Cassettes per country (6 new).

Coverage te.py extensions ≥ 90%.
```

### Commit 2 — TE CPI wrappers remaining Week-9 (CH/SE/NO/DK) + GB/JP

```
feat(connectors): TE CPI + inflation forecast wrappers CH/SE/NO/DK/GB/JP

Mirror CA/AU/NZ pattern for 6 additional countries.

Negative-rate era countries (CH/SE/DK): CPI data unaffected by rate regime;
standard TE series. No special handling needed (unlike M1 where cascade flags
tracked negative rates).

Tests per country — unit + @pytest.mark.slow canaries.

Cassettes per country (12 new).
```

### Commit 3 — ECB SDW HICP + SPF for EA fallback (if needed)

```
feat(connectors): ECB SDW HICP + SPF extension for EA members fallback

If Commit 1 pre-flight revealed TE insufficient for EA members, extend
ecb_sdw.py with:

async def fetch_hicp_yoy(
    self,
    country: str,  # DE, FR, IT, ES, NL, PT, EA19
    observation_date: date,
) -> list[Observation]:
    """HICP YoY per EA member via ECB SDW ICP dataflow."""

async def fetch_spf_inflation_forecast(
    self,
    country: str,
    observation_date: date,
) -> Observation:
    """ECB Survey of Professional Forecasters inflation forecast.

    Published quarterly; 12-24 month horizon. Returns latest value.
    SPF covers EA aggregate + selected members.
    """

If TE sufficient for all EA (pre-flight finding), skip this commit (scope narrow).

Tests:
- Unit: fetch_hicp_yoy per EA member
- Unit: fetch_spf_inflation_forecast
- @pytest.mark.slow canaries DE + IT (if extension shipped)

Cassettes per country.
```

### Commit 4 — M2 builders CPI/inflation wiring Week-9 countries

```
feat(indices): M2 CPI + inflation wiring Week-9 countries (CA/AU/NZ/CH/SE/NO/DK)

Upgrade build_m2_{country}_inputs from output-gap-only (Sprint C) to full compute:

async def build_m2_ca_inputs(
    fred: FredConnector,
    te: TEConnector,
    observation_date: date,
    *,
    oecd_eo: OECDEOConnector | None = None,
) -> M2Inputs:
    """Build M2 CA inputs — full compute live.

    Sprint C shipped output_gap. Sprint F adds CPI YoY + inflation forecast.
    """
    flags = []

    # Output gap (Sprint C)
    output_gap = None
    if oecd_eo:
        try:
            obs = await oecd_eo.fetch_country_output_gap("CA", observation_date)
            if obs:
                output_gap = obs[-1].value
                flags.append("CA_M2_OUTPUT_GAP_OECD_EO_LIVE")
        except (DataUnavailableError, ConnectorError):
            flags.append("CA_M2_OUTPUT_GAP_UNAVAILABLE")

    # CPI YoY (Sprint F)
    cpi_obs = await te.fetch_ca_cpi_yoy(observation_date)
    cpi_yoy = cpi_obs[-1].value if cpi_obs else None
    if cpi_yoy is not None:
        flags.append("CA_M2_CPI_TE_LIVE")

    # Inflation forecast (Sprint F)
    forecast = await te.fetch_ca_inflation_forecast(observation_date)
    inflation_forecast = forecast.value if forecast else None
    if inflation_forecast is not None:
        flags.append("CA_M2_INFLATION_FORECAST_TE_LIVE")

    if all([output_gap, cpi_yoy, inflation_forecast]):
        flags.append("CA_M2_FULL_COMPUTE_LIVE")
    else:
        # Partial: some components missing; document + allow compute with degraded confidence
        flags.append("CA_M2_PARTIAL_COMPUTE")

    return M2Inputs(
        output_gap=output_gap,
        cpi_yoy=cpi_yoy,
        inflation_forecast=inflation_forecast,
        flags=flags,
    )

Replicate for AU/NZ/CH/SE/NO/DK.

Tests per country — unit (happy + partial + unavailable) + @pytest.mark.slow
canaries.

Coverage builders.py M2 per-country paths maintained ≥ 90%.
```

### Commit 5 — M2 builders CPI/inflation wiring EA + GB/JP

```
feat(indices): M2 CPI + inflation wiring EA members + GB/JP

Apply Commit 4 pattern for:
- DE/FR/IT/ES/NL/PT (EA members) — TE primary OR ECB SDW fallback if shipped Commit 3
- GB/JP — TE primary

US M2 canonical path PRESERVED — regression test required:

def test_us_m2_canonical_preserved():
    """Regression guard: US M2 2024-01-02 canonical compute unchanged.

    Pre-Sprint-F: CBO quarterly path
    Post-Sprint-F: same compute, no regression.
    """

Tests per country — unit + @pytest.mark.slow canaries.

Coverage maintained.
```

### Commit 6 — Pipeline integration + production smoke

```
refactor(pipelines): daily_monetary_indices M2 full-compute verification

Update src/sonar/pipelines/daily_monetary_indices.py:

1. Verify M2 dispatcher routes per-country to full-compute builders
2. Log emission per country: `M2 compute mode: [FULL / PARTIAL / SCAFFOLD]`
3. Failure mode: InsufficientDataError if < 2 of 3 components available (country-specific)

Integration smoke @slow:
tests/integration/test_daily_monetary_m2_full_compute.py:

@pytest.mark.slow
async def test_daily_monetary_m2_full_compute_t1_core():
    """Full pipeline 2024-12-31 for 16 T1 countries M2.

    Expected:
    - ≥ 12 countries persist M2_FULL_COMPUTE_LIVE flag
    - ≤ 4 countries M2_PARTIAL_COMPUTE (acceptable for sprint scope)
    - US canonical preserved
    - Combined wall-clock ≤ 90s
    """

Coverage maintained.
```

### Commit 7 — Cassettes + cross-val + CAL closures + retro

```
test + docs: Sprint F cassettes + cross-val + CAL closures + retro

Cassettes ≥ 30 shipped (CPI + forecast per 15 countries).

Live canaries (@pytest.mark.slow):
- 15 new canaries (1 per country × CPI)
- ≤ 8 canaries for inflation forecast (countries with forecast available)
- Combined wall-clock ≤ 90s

Cross-validation (documented, not automated):
- CPI YoY per country vs public ECB/BLS/TE web values
- Expected deviation: ≤ 10 bps (standard CPI numbers, authoritative)

CAL-CPI-INFL-T1-WRAPPERS CLOSED.

New CAL items if gaps:
- CAL-CPI-EA-NATIONAL-FALLBACK (if ECB SDW/TE sparse for specific EA country)
- CAL-INFLATION-FORECAST-QUARTERLY (some TE forecasts only quarterly — data frequency handling)

Retrospective per v3 format:
docs/planning/retrospectives/week10-sprint-cpi-infl-t1-report.md

Content:
- CPI + forecast availability matrix per country
- M2 compute mode per country (FULL / PARTIAL / DEGRADED)
- Cross-val CPI vs public data
- US canonical preservation validated
- Flag emissions matrix per country
- Production impact: M2 full-compute live 8-14 T1 countries tomorrow
- MSC composite multi-country unblocked (next sprint candidate)
- §10 pre-merge checklist + §11 merge via script
- Paralelo with Sprint E: zero file conflicts
- ADR-0010 compliance: all work T1 scope
```

---

## 5. HALT triggers (atomic)

0. **TE CPI + forecast empirical probe insufficient** for majority countries — scope narrow; open CAL items for specific countries.
1. **ECB SDW fallback required but extension non-trivial** — may require dedicated sprint. If Commit 3 grows beyond 1h work, defer ECB SDW fallback to separate sprint.
2. **US M2 canonical regression** — if Commit 5 regression test fails, HALT. US M2 preservation is absolute.
3. **TE rate limits** — tenacity handles; document if persistent.
4. **Data frequency mismatch** — CPI monthly vs forecast quarterly/annual. Handle per-country in M2 compute, document in flags.
5. **Forecast horizon variability** — TE forecast may be 12m or 24m ahead per country. Standardize to 12m where possible; flag deviations.
6. **Cassette count < 20** — HALT (need ≥ 15 countries × 2 series = 30 target).
7. **Live canary wall-clock > 120s combined** — optimize OR split.
8. **Pre-push gate fails** — fix before push.
9. **No `--no-verify`**.
10. **Coverage regression > 3pp** — HALT.
11. **Push before stopping** — script mandates.
12. **Sprint E file conflict** — CAL file union-merge trivial; te.py APPEND-only, read-only conflict impossible.
13. **M2 compute mode degraded majority** — if > 8 countries PARTIAL_COMPUTE (< half FULL), surface + investigate data source gaps.
14. **ADR-0010 violation** — if CPI wrapper slips any non-T1 country, HALT.

---

## 6. Acceptance

### Global sprint-end
- [ ] TE CPI + inflation forecast wrappers shipped for 15 T1 countries (US already wired)
- [ ] ECB SDW HICP + SPF extension shipped if EA fallback needed
- [ ] M2 builders wired CPI + inflation for all 15 T1 countries
- [ ] US M2 canonical path PRESERVED (regression test PASS)
- [ ] M2 full-compute live for ≥ 10 of 16 T1 countries
- [ ] Cassettes ≥ 20 shipped
- [ ] Live canaries ≥ 15 @pytest.mark.slow PASS combined ≤ 120s
- [ ] CAL-CPI-INFL-T1-WRAPPERS CLOSED with commit refs
- [ ] Coverage te.py extensions ≥ 90%, builders.py M2 paths ≥ 90%
- [ ] No `--no-verify`
- [ ] Pre-push gate green every push
- [ ] §10 Pre-merge checklist executed
- [ ] Merge via `sprint_merge.sh`
- [ ] Retrospective shipped per v3 format
- [ ] ADR-0010 tier scope compliance verified

---

## 7. Report-back artifact

File: `docs/planning/retrospectives/week10-sprint-cpi-infl-t1-report.md`

**Final tmux echo**:
```
SPRINT F CPI + INFLATION T1 DONE: N commits on branch sprint-cpi-infl-t1-wrappers

M2 full-compute status per T1 country:
- US: canonical CBO quarterly (preserved) ✓
- DE: [FULL / PARTIAL] — output_gap + cpi_yoy + forecast
- FR: [FULL / PARTIAL]
- IT: [FULL / PARTIAL]
- ES: [FULL / PARTIAL]
- NL: [FULL / PARTIAL]
- PT: [FULL / PARTIAL]
- GB: [FULL / PARTIAL]
- JP: [FULL / PARTIAL]
- CA: [FULL / PARTIAL]
- AU: [FULL / PARTIAL]
- NZ: [FULL / PARTIAL]
- CH: [FULL / PARTIAL]
- SE: [FULL / PARTIAL]
- NO: [FULL / PARTIAL]
- DK: [FULL / PARTIAL]

Total FULL compute: N of 16
Total PARTIAL compute: M of 16

US canonical: PRESERVED ✓

CAL-CPI-INFL-T1-WRAPPERS CLOSED.
New CAL items: [if any — list]

Production impact: daily_monetary_indices M2 full-compute live for N of 16 T1 tomorrow.
MSC composite multi-country unblocked — next sprint candidate Week 10 Day 3 or Week 11.

Paralelo with Sprint E: zero file conflicts.

Merge: ./scripts/ops/sprint_merge.sh sprint-cpi-infl-t1-wrappers

Artifact: docs/planning/retrospectives/week10-sprint-cpi-infl-t1-report.md
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

---

## 9. Notes on implementation

### Connector-type organization mirrors M1 + M2 output-gap
TE-primary cascade canonical for 9 non-EA T1 countries. ECB SDW fallback for EA if TE sparse. Mirror Sprint C OECD EO pattern (separate connector family for specific data type).

### Data frequency handling
- CPI YoY: monthly typical
- Inflation forecast: quarterly OR 12m ahead single point
- Reconciliation in M2 builder: use latest available per series

### Cross-validation discipline
CPI values are **public and authoritative** — cross-val vs ECB/BLS/TE web should be within 10 bps. Larger deviations suggest data source quality issue.

### Forecast horizon variability
Some TE forecasts are 12m ahead, others quarterly. Standardize to 12m where possible. Flag deviations per country in M2 compute.

### Paralelo discipline
Sprint F touches `te.py` APPEND + builders.py + pipelines/daily_monetary_indices.py. Sprint E touches daily_curves.py. Zero primary overlap.

Shared secondary: calibration-tasks.md union-merge trivial.

### US M2 preservation
Regression test critical — US M2 canonical path (CBO quarterly output gap + Michigan expectations) must not change. Sprint F adds per-country paths, doesn't modify US.

### M2 full-compute per-country vs partial
Acceptable to ship "PARTIAL compute" for countries with sparse inflation data. Flag tracks degraded confidence. Prefer completeness over hard failure.

### Tier scope lock
All 15 wrappers for T1 countries per ADR-0010. Zero T2 work. Brief format v3 header enforces.

### Script merge dogfooded
7th production use (Day 1 + Day 2 Sprint F). Apply learned patterns.

### MSC composite unlock
Post-sprint, M-indices T1 uniformity:
- M1: shipped Week 9 (16 countries)
- M2: Sprint F completes full compute (8-14+ countries FULL; rest PARTIAL)
- M3: curves-derived, depends curves T1 uniform (blocked by EA periphery sprints)
- M4: FCI per-country (Phase 2.5 scope)

MSC composite requires all 4 M-indices minimum. Post-Sprint-F, MSC viable for countries with all 4 (currently US only for full M1+M2+M3+M4).

### Week 11 follow-on sprint candidates
Post-Sprint-F completion:
- CAL-M3-T1-EXPANSION (market-expectations curves-derived)
- CAL-M4-T1-FCI-EXPANSION (FCI per-country)
- MSC composite multi-country (depends M1-M4 shipped)

---

*End of Sprint F brief. 6-8 commits. M2 T1 full compute via CPI + inflation wrappers. Paralelo-ready with Sprint E.*
