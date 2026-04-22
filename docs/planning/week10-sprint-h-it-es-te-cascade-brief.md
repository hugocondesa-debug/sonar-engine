# Week 10 Day 2 Sprint H — IT + ES Yield Curves via TE Cascade

**Tier scope**: T1 ONLY (16 countries). T2 expansion deferred to Phase 5 per ADR-0010.

**Target**: Ship TE fetch_it_yield_curve_nominal + fetch_es_yield_curve_nominal wrappers + pipeline integration. Closes Sprint G HALT-0 gap (brief §2 omitted TE probe path; empirical TE coverage confirmed 2026-04-22 for both countries). Mirror CAL-138 GB/JP/CA pattern exactly. T1 curves coverage 6 → 8 countries.
**Priority**: HIGH (closes CAL-CURVES-IT-BDI + CAL-CURVES-ES-BDE; trivial ship via validated pattern)
**Budget**: 2-3h CC
**Commits**: ~5-6
**Base**: branch `sprint-curves-it-es-te-cascade` (isolated worktree `/home/macro/projects/sonar-wt-curves-it-es-te`)
**Concurrency**: PARALELO with Sprint L (CAL-M2-EA-AGGREGATE). Zero primary file overlap (curves vs M2 monetary).

**Brief format**: v3

---

## 1. Scope

In (3 tracks):

### Track 1 — TE yield curve wrappers IT + ES (~1h)
Mirror Sprint CAL-138 GB/JP/CA pattern exactly for IT + ES:
- `src/sonar/connectors/te.py` APPEND:
  - `fetch_it_yield_curve_nominal(observation_date)` → returns dict of YieldCurvePoint per tenor
  - `fetch_es_yield_curve_nominal(observation_date)` → returns dict of YieldCurvePoint per tenor
- HistoricalDataSymbol source-drift guards per country:
  - IT: `GBTPGR10` (10Y reference, empirically validated 2026-04-22)
  - ES: `GSPG10YR` (10Y reference, empirically validated 2026-04-22)
- Per-tenor series codes (pre-flight probe in Commit 1 to confirm):
  - Tenors targeted: 1M, 3M, 6M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y, 15Y, 20Y, 30Y
  - Expected coverage per country: 10+ tenors each (historical daily since 1991)

### Track 2 — Pipeline integration (~1h)
- `src/sonar/pipelines/daily_curves.py` MODIFY:
  - Extend T1_CURVES_COUNTRIES tuple: `("US", "DE", "EA", "GB", "JP", "CA")` → `("US", "DE", "EA", "GB", "JP", "CA", "IT", "ES")` (6 → 8 countries)
  - Country dispatcher: IT + ES → TE (mirror GB/JP/CA routing)
- Connector lifecycle: TE already in connectors_to_close (no change needed)
- NSS fit applied uniform (reused)

### Track 3 — Cassettes + live canaries + CAL closures + retro (~1h)
- Cassettes: `tests/fixtures/cassettes/te_yield_it_*.json` + `te_yield_es_*.json` (2-3 cassettes per country for nominal curve)
- Live canary @pytest.mark.slow per country:
  - IT NSS fit 2024-12-31, confidence ≥ 0.9, rmse_bps ≤ 10
  - ES NSS fit 2024-12-31, confidence ≥ 0.9, rmse_bps ≤ 10
- `--all-t1` integration canary: 8 countries persist
- CAL-CURVES-IT-BDI + CAL-CURVES-ES-BDE **CLOSED via TE cascade** (scaffolds banca_ditalia.py + banco_espana.py retained as future direct-CB placeholders)
- ADR-0009 amendment: "TE generic cascade mandatory Path 1 for any country-data probe; national CB probe only post-TE-exhaustion confirmed"
- Retrospective per v3 format

Out:
- Linker data IT + ES (BTP€I + Bonos indexados) — separate future sprint if needed; TE may not expose linker series; defer
- AU/NZ/CH/SE/NO/DK curves (separate CAL-CURVES-T1-SPARSE-PROBES sprint)
- PT + NL curves (pending sprints per ADR-0009 Sprint G addendum)
- Historical backfill (Phase 2.5 backtest scope)

---

## 2. Spec reference

Authoritative:
- `docs/backlog/calibration-tasks.md` — CAL-CURVES-IT-BDI + CAL-CURVES-ES-BDE entries (currently BLOCKED sharpened per Sprint G)
- `docs/planning/retrospectives/week10-sprint-curves-it-es-report.md` — Sprint G HALT-0 context + TE omission noted
- `docs/planning/retrospectives/week10-sprint-cal138-report.md` — **CAL-138 GB/JP/CA TE cascade pattern template** (primary reference)
- `src/sonar/connectors/te.py` — existing GB/JP/CA yield wrappers (copy-adapt pattern)
- `src/sonar/pipelines/daily_curves.py` — current dispatcher + T1_CURVES_COUNTRIES tuple
- `src/sonar/connectors/banca_ditalia.py` — Sprint G scaffold (retained)
- `src/sonar/connectors/banco_espana.py` — Sprint G scaffold (retained)
- `docs/adr/ADR-0009-national-cb-connectors-ea-periphery.md` — probe discipline (amendment target)
- `docs/adr/ADR-0010-t1-complete-before-t2-expansion.md` — tier scope lock

**Empirical TE probe evidence (2026-04-22)**:
```
IT 10Y:
  curl -s "https://api.tradingeconomics.com/historical/country/italy/indicator/government%20bond%2010y?c=${TE_API_KEY}&format=json&d1=2024-12-01&d2=2024-12-05"
  → [{HistoricalDataSymbol: "GBTPGR10", Frequency: "Daily", historical since 1991}]

ES 10Y:
  curl -s "https://api.tradingeconomics.com/historical/country/spain/indicator/government%20bond%2010y?c=${TE_API_KEY}&format=json&d1=2024-12-01&d2=2024-12-05"
  → [{HistoricalDataSymbol: "GSPG10YR", Frequency: "Daily", historical since 1991}]
```

**Pre-flight requirement**: Commit 1 CC:
1. Read CAL-138 retrospective + te.py fetch_gb_yield_curve_nominal + fetch_jp_yield_curve_nominal + fetch_ca_yield_curve_nominal implementations (primary pattern template)
2. Probe TE per-tenor coverage for IT + ES:
   ```bash
   set -a && source .env && set +a

   # IT per tenor sweep
   for tenor in "1 month" "3 month" "6 month" "1 year" "2 year" "3 year" "5 year" "7 year" "10 year" "15 year" "20 year" "30 year"; do
       url="https://api.tradingeconomics.com/historical/country/italy/indicator/government%20bond%20${tenor// /%20}?c=${TE_API_KEY}&format=json&d1=2024-12-01&d2=2024-12-05"
       result=$(curl -s "$url" | jq '.[0] | {HistoricalDataSymbol, Frequency, Value}' 2>/dev/null)
       echo "IT ${tenor}: $result"
   done

   # ES per tenor sweep
   for tenor in "1 month" "3 month" "6 month" "1 year" "2 year" "3 year" "5 year" "7 year" "10 year" "15 year" "20 year" "30 year"; do
       url="https://api.tradingeconomics.com/historical/country/spain/indicator/government%20bond%20${tenor// /%20}?c=${TE_API_KEY}&format=json&d1=2024-12-01&d2=2024-12-05"
       result=$(curl -s "$url" | jq '.[0] | {HistoricalDataSymbol, Frequency, Value}' 2>/dev/null)
       echo "ES ${tenor}: $result"
   done
   ```
3. Document per-country tenor coverage matrix in Commit 1 body:
   - IT: [list tenors with HistoricalDataSymbol + frequency + sample value]
   - ES: [list tenors with HistoricalDataSymbol + frequency + sample value]
4. Minimum ≥ 8 tenors per country for NSS fit stability (per CAL-138 CA shipped at 6 tenors NS-reduced minimum).

**Pre-flight HALT trigger**: if probe reveals < 6 tenors per country OR non-daily frequency for majority tenors, HALT and surface. Expected outcome: ≥ 10 tenors daily per country (Italy + Spain are major sovereign markets with full TE coverage).

---

## 3. Concurrency — PARALELO with Sprint L

**Sprint H worktree**: `/home/macro/projects/sonar-wt-curves-it-es-te`
**Sprint H branch**: `sprint-curves-it-es-te-cascade`

**Sprint L (for awareness)**: CAL-M2-EA-AGGREGATE, worktree `/home/macro/projects/sonar-wt-m2-ea-aggregate`

**File scope Sprint H**:
- `src/sonar/connectors/te.py` APPEND (primary — IT + ES yield wrappers)
- `src/sonar/pipelines/daily_curves.py` MODIFY (primary — tuple expansion + dispatcher)
- `tests/unit/test_connectors/test_te*.py` EXTEND (IT + ES unit tests)
- `tests/integration/test_daily_curves_multi_country.py` EXTEND (IT + ES live canaries)
- `tests/fixtures/cassettes/te_yield_it_*.json` + `te_yield_es_*.json` NEW
- `docs/backlog/calibration-tasks.md` MODIFY (close CAL-CURVES-IT-BDI + CAL-CURVES-ES-BDE via TE)
- `docs/adr/ADR-0009-national-cb-connectors-ea-periphery.md` MODIFY (amendment: TE Path 1 canonical)
- `docs/planning/retrospectives/week10-sprint-curves-it-es-te-report.md` NEW

**Sprint L file scope** (for awareness, DO NOT TOUCH):
- `src/sonar/indices/monetary/builders.py` (Sprint L primary — EA aggregate M2 builder)
- `src/sonar/connectors/ecb_sdw.py` EXTEND (Sprint L possibly — ECB SDW HICP aggregate)
- `src/sonar/connectors/te.py` APPEND (Sprint L may append EA aggregate CPI/inflation wrappers)

**Potential overlap zones**:
- `src/sonar/connectors/te.py` APPEND — both Sprints H + L append new methods. **APPEND-ONLY pattern** means zero conflict if:
  - Sprint H appends yield wrappers (IT + ES) in yield section of te.py
  - Sprint L appends CPI/inflation wrappers (EA aggregate) in CPI section of te.py
  - Both sprints append at end of respective bookmark zones
- `docs/backlog/calibration-tasks.md` — both modify; different sections (CAL-CURVES-* vs CAL-M2-*); union-merge trivial.

**Zero primary-file conflict** when bookmark zones respected.

**Rebase expected minor**: alphabetical merge priority — Sprint H ships first (h < l). Sprint L rebases te.py + CAL file (union-merge trivial).

**Pre-merge checklist** (brief v3 §10):
- [ ] All commits pushed
- [ ] Workspace clean
- [ ] Pre-push gate green
- [ ] Branch tracking set
- [ ] Live canaries IT + ES PASS
- [ ] NSS fit RMSE per country ≤ 10 bps
- [ ] Tier scope verified T1 only (per ADR-0010)

**Merge execution** (brief v3 §11):
```bash
./scripts/ops/sprint_merge.sh sprint-curves-it-es-te-cascade
```

---

## 4. Commits

### Commit 1 — Pre-flight + TE IT yield wrapper

```
feat(connectors): TE fetch_it_yield_curve_nominal + pre-flight

Pre-flight findings (Commit 1 body):
- TE IT per-tenor probe matrix:
  [12 tenors probed, document HistoricalDataSymbol + Frequency per tenor]
- Expected daily coverage for ≥ 10 tenors (Italy major sovereign market).
- HistoricalDataSymbol GBTPGR10 (10Y reference) confirmed.

Append to src/sonar/connectors/te.py (mirror fetch_gb_yield_curve_nominal pattern from CAL-138):

async def fetch_it_yield_curve_nominal(
    self,
    observation_date: date,
) -> dict[str, YieldCurvePoint]:
    """Fetch IT BTP nominal yield curve via TE generic indicator API.

    Source-drift guard: HistoricalDataSymbol validation (GBTPGR10 10Y reference).
    Returns dict {tenor_label: YieldCurvePoint} for tenors 1M-30Y.

    Empirical probe findings (Commit 1): [N tenors daily since 1991].
    """

Tests:
- Unit: fetch_it_yield_curve_nominal happy path mocked
- Unit: source-drift guard (HistoricalDataSymbol mismatch raises)
- Unit: 404 / empty response → DataUnavailableError
- @pytest.mark.slow live canary: IT yield curve 2024-12-31, assert ≥ 8 tenors

Cassettes:
- tests/fixtures/cassettes/te_yield_it_2024_12_31.json (per tenor)

Coverage te.py IT extensions ≥ 90%.
```

### Commit 2 — TE ES yield wrapper

```
feat(connectors): TE fetch_es_yield_curve_nominal

Mirror Commit 1 pattern for Spain.

HistoricalDataSymbol GSPG10YR (10Y reference) confirmed.

Tests:
- Unit: fetch_es_yield_curve_nominal happy path + source-drift guard
- @pytest.mark.slow live canary: ES yield curve 2024-12-31

Cassettes.
```

### Commit 3 — Pipeline integration IT + ES dispatch

```
refactor(pipelines): daily_curves IT + ES dispatch + T1 tuple expansion

Update src/sonar/pipelines/daily_curves.py:

1. Import fetch_it_yield_curve_nominal + fetch_es_yield_curve_nominal (already in te.py)

2. Expand T1_CURVES_COUNTRIES tuple:
   Current: ("US", "DE", "EA", "GB", "JP", "CA")
   Post: ("US", "DE", "EA", "GB", "JP", "CA", "IT", "ES")

3. Dispatcher routing:
   - IT → te.fetch_it_yield_curve_nominal (via run_country mirror GB/JP/CA)
   - ES → te.fetch_es_yield_curve_nominal

4. NSS fit applied uniform (no change)

5. Connector lifecycle: TE already registered (no change)

Tests:
- Unit: dispatcher routes IT + ES correctly to TE
- Unit: --all-t1 iterates 8 countries
- Unit: T1_CURVES_COUNTRIES assertion (8 entries, all T1 per ADR-0010)

Coverage daily_curves.py ≥ 90%.

Update docstring: "T1 curves coverage 8/16 post-Sprint-H (US/DE/EA/GB/JP/CA/IT/ES)."
```

### Commit 4 — Cassettes + live canaries

```
test(integration): yield curve live canaries IT + ES + --all-t1 8 countries

Extend tests/integration/test_daily_curves_multi_country.py:

@pytest.mark.slow
async def test_daily_curves_it_live_canary():
    """IT NSS fit via TE for 2024-12-31.

    Assert:
    - NSSYieldCurveSpot persisted
    - confidence ≥ 0.9
    - rmse_bps ≤ 10
    - tenors_observed ≥ 8
    - source_connector = 'te'
    """

@pytest.mark.slow
async def test_daily_curves_es_live_canary():
    """ES NSS fit via TE for 2024-12-31 (mirror pattern)."""

@pytest.mark.slow
async def test_daily_curves_all_t1_iterates_8():
    """--all-t1 full execution 2024-12-31 persists 8 countries."""

Combined wall-clock target ≤ 45s.

Cassettes per country shipped via Commits 1-2.

Coverage maintained.
```

### Commit 5 — ADR-0009 amendment + CAL closures + retro

```
docs(adr+planning+backlog): ADR-0009 amendment — TE Path 1 canonical + CAL closures + Sprint H retro

1. ADR-0009 amendment (docs/adr/ADR-0009-national-cb-connectors-ea-periphery.md):

New section "Pattern library v2 — TE Path 1 canonical":
- Empirical finding 2026-04-22: Sprint G IT + ES HALT-0 conclusions were materially
  incomplete because brief §2 probe list omitted TE (Trading Economics generic
  indicator API).
- Correction: Sprint H shipped IT + ES via TE cascade (HistoricalDataSymbol GBTPGR10 + GSPG10YR, daily since 1991).
- Operational rule: any country-data probe sprint MUST include TE generic indicator
  API as Path 1 in pre-flight probe matrix. National CB probe only when TE
  coverage gap confirmed empirically.

Updated EA periphery probe matrix:
- DE-Bundesbank: SUCCESS via direct (Sprint CAL-138)
- FR-BDF: HALT-0 national CB (Sprint D); awaits TE probe (likely GFRN10 existing)
- IT-BDI: HALT-0 national CB (Sprint G) → SHIPPED via TE cascade (Sprint H)
- ES-BDE: HALT-0 national CB (Sprint G) → SHIPPED via TE cascade (Sprint H)
- PT-BPSTAT: pending probe (TE Path 1 first per amendment)
- NL-DNB: pending probe (TE Path 1 first per amendment)

2. CAL-CURVES-IT-BDI CLOSED:
   - Status: done (shipped via TE cascade Sprint H, commit [SHA])
   - National CB direct connector remains blocked per Sprint G HALT-0; scaffold retained (banca_ditalia.py)
   - Unblock path for direct: same as Sprint G (3 unblock paths documented)

3. CAL-CURVES-ES-BDE CLOSED:
   - Status: done (shipped via TE cascade Sprint H, commit [SHA])
   - National CB direct connector remains blocked per Sprint G HALT-0; scaffold retained (banco_espana.py)
   - Unblock path for direct: same as Sprint G (4 unblock paths documented)

4. CAL items opened (Phase 2.5 scope):
   - CAL-CURVES-IT-ES-LINKER (BTP€I + Bonos indexados probe separate sprint if needed)
   - CAL-CURVES-FR-TE-PROBE (Sprint D FR TE was mentioned "GFRN10 10Y-only, below MIN_OBSERVATIONS=6" — re-probe full tenor spectrum per ADR-0009 v2)

5. Retrospective per v3 format:
docs/planning/retrospectives/week10-sprint-curves-it-es-te-report.md

Content:
- TE probe outcomes per country (tenor coverage matrix)
- NSS fit quality IT + ES (RMSE bps)
- Pattern replication validation (CAL-138 GB/JP/CA template applied 5th time)
- ADR-0009 amendment rationale (TE Path 1 canonical)
- Sprint G HALT-0 correction
- Production impact: overlays cascade tomorrow 07:30 WEST gains IT + ES
- §10 pre-merge checklist + §11 merge via script
- Paralelo with Sprint L: zero primary file conflicts (te.py append-zones respected)
- ADR-0010 compliance: both countries T1

T1 curves coverage post-merge: 8/16 (US + DE + EA + GB + JP + CA + IT + ES).
Remaining: FR (TE re-probe) + PT + NL (EA periphery) + AU/NZ/CH/SE/NO/DK (sparse probes).
```

---

## 5. HALT triggers (atomic)

0. **TE per-tenor probe reveals < 6 daily tenors per country** — scope narrow; HALT for that country. Highly unlikely for IT + ES (major sovereign markets).
1. **HistoricalDataSymbol unexpected** — if GBTPGR10 / GSPG10YR drift to different symbol, document + investigate. HALT if systematic.
2. **NSS fit convergence failure per country** — emit flag + investigate bounds. CAL item opens.
3. **RMSE > 20 bps** — data quality issue. HALT + investigate.
4. **Cassette count < 2** — HALT.
5. **Live canary wall-clock > 30s combined** — optimize.
6. **Pre-push gate fails** — fix before push.
7. **No `--no-verify`**.
8. **Coverage regression > 3pp** — HALT.
9. **Push before stopping** — script mandates; brief v3 §10.
10. **Sprint L file conflict** — te.py append-only respected; CAL file union-merge trivial.
11. **ADR-0010 violation** — both countries T1; brief header enforces.

---

## 6. Acceptance

### Global sprint-end
- [ ] fetch_it_yield_curve_nominal shipped + tested (≥ 90% coverage)
- [ ] fetch_es_yield_curve_nominal shipped + tested (≥ 90% coverage)
- [ ] Pipeline dispatcher routes IT + ES correctly to TE
- [ ] T1_CURVES_COUNTRIES tuple expanded 6 → 8 countries
- [ ] NSS fit RMSE ≤ 10 bps per country
- [ ] Cassettes ≥ 2 shipped (one per country)
- [ ] Live canaries 3+ new (IT + ES + --all-t1 8 countries)
- [ ] CAL-CURVES-IT-BDI CLOSED with commit refs
- [ ] CAL-CURVES-ES-BDE CLOSED with commit refs
- [ ] ADR-0009 amendment shipped (TE Path 1 canonical)
- [ ] 2 new CAL items (CAL-CURVES-IT-ES-LINKER + CAL-CURVES-FR-TE-PROBE)
- [ ] Coverage te.py extensions ≥ 90%, daily_curves.py ≥ 90%
- [ ] No `--no-verify`
- [ ] Pre-push gate green every push
- [ ] §10 Pre-merge checklist executed
- [ ] Merge via `sprint_merge.sh`
- [ ] Retrospective shipped per v3 format
- [ ] ADR-0010 tier scope compliance verified

---

## 7. Report-back artifact

File: `docs/planning/retrospectives/week10-sprint-curves-it-es-te-report.md`

**Final tmux echo**:
```
SPRINT H IT + ES TE CASCADE DONE: N commits on branch sprint-curves-it-es-te-cascade

T1 curves coverage: 6 → 8 countries (US + DE + EA + GB + JP + CA + IT + ES)

TE cascade outcomes:
- IT: HistoricalDataSymbol GBTPGR10, N tenors daily, NSS RMSE [X] bps
- ES: HistoricalDataSymbol GSPG10YR, N tenors daily, NSS RMSE [X] bps

CAL-CURVES-IT-BDI CLOSED (via TE cascade).
CAL-CURVES-ES-BDE CLOSED (via TE cascade).

ADR-0009 amended: TE Path 1 canonical for all country-data probe sprints.

Production impact: tomorrow 07:30 WEST overlays cascade gains IT + ES functional.

Remaining T1 curves gap:
- FR: TE re-probe needed (CAL-CURVES-FR-TE-PROBE opened)
- PT + NL: EA periphery pending (ADR-0009 per country)
- AU/NZ/CH/SE/NO/DK: T1 sparse probes pending

Paralelo with Sprint L: zero file conflicts.

Merge: ./scripts/ops/sprint_merge.sh sprint-curves-it-es-te-cascade

Artifact: docs/planning/retrospectives/week10-sprint-curves-it-es-te-report.md
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

Live canaries (@pytest.mark.slow) run explicitly during Commit 4.

---

## 9. Notes on implementation

### Pattern replication (5th use)
CAL-138 GB/JP/CA template applied IT + ES. Pattern proven canonical — trivial ship.

### Sprint G scaffolds retention
banca_ditalia.py + banco_espana.py remain as documentation + future direct-CB placeholders. Not deleted. Reference from ADR-0009 amendment explicitly.

### TE API efficiency
TE rate limits generous. Per-country per-tenor fetch ~12 API calls per country per day. 24 calls total Sprint H pipeline runs. Cache layer handles repeats.

### Linker handling
TE may not expose BTP€I or Bonos indexados. If empirical probe reveals linker sparse, emit LINKER_UNAVAILABLE flag + fallback DERIVED real curve method (BEI-style). Document in CAL-CURVES-IT-ES-LINKER opened per outcome.

### Paralelo discipline
Sprint L in builders.py + ecb_sdw.py (possibly) + te.py append (CPI/inflation section). Sprint H in te.py append (yield section) + daily_curves.py. Zero primary overlap if te.py bookmark zones respected.

### Script merge dogfooded
10th production use Week 10.

### FR TE re-probe opportunity
Sprint D FR-BDF noted "TE GFRN10 10Y-only, below MIN_OBSERVATIONS=6". ADR-0009 v2 amendment requires per-tenor TE probe (not just 10Y). CAL-CURVES-FR-TE-PROBE opened this sprint — Week 11+ candidate sprint to apply same ADR-0009 v2 discipline to FR.

---

*End of Sprint H brief. 5-6 commits. IT + ES curves shipped via TE cascade. T1 coverage 6 → 8. Closes Sprint G HALT-0 gap. Paralelo-ready with Sprint L.*
