# Week 10 Day 1+ Sprint D — CAL-CURVES-FR-BDF Pilot (Banque de France national CB)

**Target**: Ship Banque de France connector for FR sovereign yield curves. First national-CB connector for EA periphery post-Sprint-A HALT (ECB SDW lacks per-country periphery). Validates Bundesbank-analog pattern for 4 follow-on sprints (IT-BDI + ES-BDE + PT-BPSTAT + NL-DNB).
**Priority**: HIGH (pilot pattern — unblocks 4 future EA periphery sprints; Phase 2 exit progression)
**Budget**: 3-4h CC
**Commits**: ~5-7
**Base**: branch `sprint-curves-fr-bdf` (isolated worktree `/home/macro/projects/sonar-wt-curves-fr-bdf`)
**Concurrency**: PARALELO with Sprint C (M2 output gap). Zero primary file overlap.

**Brief format**: v3

---

## 1. Scope

In (3 tracks):

### Track 1 — Banque de France connector (~1.5-2h)
- `src/sonar/connectors/banque_de_france.py` NEW — Banque de France data API connector
- Endpoint: `https://webstat.banque-france.fr/ws_wsfr/rest/` OR `https://webstat.banque-france.fr/en/download-page.do`
- **Pre-flight probe required** (Commit 1): identify correct API endpoint + dataflow + series codes for FR sovereign yields
- Key series target per tenor:
  - OAT 1M, 3M, 6M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y, 15Y, 20Y, 30Y (nominal)
  - OATei (inflation-indexed) 5Y, 10Y, 20Y, 30Y (linker — well-established)
- **Fallback**: if Banque de France API insufficient, probe ECB SDW per-country FR override (already checked Sprint A — empty)

### Track 2 — Pipeline integration (~1h)
- `src/sonar/pipelines/daily_curves.py` MODIFY — add FR dispatch routing
- Expand `T1_7_COUNTRIES` tuple (or equivalent) to include FR
- NSS fit applied uniform (existing logic reused)
- Linker path: OATei available → full real curve; no LINKER_UNAVAILABLE flag needed

### Track 3 — Pattern validation + tests + retro (~1h)
- Cassettes: FR yield_curve_nominal + FR yield_curve_linker (2 cassettes)
- Live canary @pytest.mark.slow FR yield curve 2024-12-31
- Cross-validation: compare FR 10Y computed vs Trésor-published daily reference (spot check)
- NSS fit RMSE target ≤ 10 bps (DE reference from Sprint CAL-138)
- Retrospective per v3 format + pattern notes for 4 follow-on EA periphery sprints

Out:
- IT/ES/PT/NL connectors (separate sprints per CAL items opened Sprint A)
- Smaller EA markets (Luxembourg, Ireland — Phase 2.5)
- OAT repo/futures implied yields (academic; defer)
- Historical FR yield curve back-filling (Phase 2.5 — backtest sprint)
- FR ERP integration (Sprint B already shipped FR ERP scaffold via Damodaran monthly fallback)

---

## 2. Spec reference

Authoritative:
- `docs/backlog/calibration-tasks.md` — CAL-CURVES-FR-BDF entry (opened Sprint A)
- `docs/planning/retrospectives/week10-sprint-ea-periphery-report.md` — Sprint A HALT findings + deferral rationale
- `docs/planning/retrospectives/week10-sprint-cal138-report.md` — Sprint CAL-138 DE Bundesbank pattern (closest template)
- `src/sonar/connectors/bundesbank.py` — DE Bundesbank reference implementation (Sprint CAL-138)
- `src/sonar/pipelines/daily_curves.py` — current multi-country dispatcher
- `src/sonar/overlays/nss_curves/` — NSS fit logic (reused uniform)

**Pre-flight requirement**: Commit 1 CC:
1. Read Sprint CAL-138 DE Bundesbank implementation (template pattern)
2. Read Sprint A EA periphery retro (context for why ECB SDW insufficient)
3. Probe Banque de France data API:
   ```bash
   # Primary probe — webstat.banque-france.fr
   curl -s -H "User-Agent: SONAR/2.0" "https://webstat.banque-france.fr/ws_wsfr/rest/data/BDF.CUR/Q.FR.DAILY.?format=sdmx-json&startPeriod=2024-12-01" | head -100

   # Alternative: Banque de France CSV/Excel download endpoint
   curl -sL "https://webstat.banque-france.fr/en/download-page.do?dataset=CUR&country=FR" | head -50

   # Per-tenor OAT series (try common codes)
   for tenor in 1M 3M 6M 1Y 2Y 3Y 5Y 7Y 10Y 15Y 20Y 30Y; do
       echo "=== OAT $tenor ==="
       curl -s "https://webstat.banque-france.fr/ws_wsfr/rest/data/BDF.TITRES/D.OAT.$tenor.R?format=jsondata&lastNObservations=5" | head -20
   done
   ```
4. **Fallback probe if Banque de France API insufficient**:
   - Agence France Trésor (AFT) — may publish daily yield curve directly
   - FRED: AFT republishes some FR yield series via FRED
   - TE: FR sovereign yields via TE (already scaffolded Sprint CAL-138 `fetch_fr_yield_curve_nominal`?)
5. Document findings Commit 1 body. If Banque de France probe insufficient:
   - Option A: use AFT direct
   - Option B: use TE primary (already shipped Sprint CAL-138)
   - Option C: HALT and surface (scope narrow to "FR via TE only, national CB deferred")

**Pre-flight HALT trigger**: if Banque de France AND AFT AND TE all fail to provide ≥ 8 tenors, narrow scope per brief §5 HALT-0 precedent.

---

## 3. Concurrency — PARALELO with Sprint C (4th paralelo Day 1)

**Sprint D worktree**: `/home/macro/projects/sonar-wt-curves-fr-bdf`
**Sprint D branch**: `sprint-curves-fr-bdf`

**Sprint C (for awareness)**: M2 output gap, worktree `/home/macro/projects/sonar-wt-m2-output-gap-expansion`, currently in execution.

**Sprint A merged** (f830a2d).
**Sprint B merged** (e78f204).

**File scope Sprint D**:
- `src/sonar/connectors/banque_de_france.py` NEW (primary)
- `src/sonar/pipelines/daily_curves.py` MODIFY (primary — FR dispatch + T1 tuple)
- `tests/unit/test_connectors/test_banque_de_france.py` NEW
- `tests/integration/test_daily_curves_multi_country.py` EXTEND (FR canary)
- `tests/fixtures/cassettes/banque_de_france/` NEW (2 cassettes)
- `docs/backlog/calibration-tasks.md` MODIFY (close CAL-CURVES-FR-BDF; add pattern notes)
- `docs/planning/retrospectives/week10-sprint-curves-fr-bdf-report.md` NEW

**Sprint C file scope** (for awareness, DO NOT TOUCH):
- `src/sonar/connectors/oecd_eo.py` NEW (Sprint C primary)
- `src/sonar/indices/monetary/builders.py` MODIFY (Sprint C primary — M2 paths)
- `src/sonar/pipelines/daily_monetary_indices.py` MODIFY (Sprint C)

**Potential overlap zones**:
- `docs/backlog/calibration-tasks.md` — both sprints modify; union-merge trivial
- `src/sonar/pipelines/daily_curves.py` — Sprint D primary; Sprint C **does not touch** (C works on daily_monetary_indices.py). Zero conflict expected.
- `src/sonar/connectors/te.py` — Sprint D may read existing FR yield wrapper (Sprint CAL-138 shipped `fetch_fr_yield_curve_nominal`?) for fallback. Read-only usage. No append needed.

**Zero primary-file overlap expected**.

**Rebase expected minor**: alphabetical merge priority → Sprint C ships when ready; Sprint D ships when ready. Whichever ships second rebases CAL file only.

**Pre-merge checklist** (brief v3 §10):
- [ ] All commits pushed
- [ ] Workspace clean
- [ ] Pre-push gate green
- [ ] Branch tracking set
- [ ] Cassettes + canaries green
- [ ] NSS fit RMSE per country acceptable (≤ 10 bps target)

**Merge execution** (brief v3 §11):
```bash
./scripts/ops/sprint_merge.sh sprint-curves-fr-bdf
```

---

## 4. Commits

### Commit 1 — Pre-flight + Banque de France connector scaffold

```
feat(connectors): Banque de France connector + pre-flight FR yield curves

Pre-flight findings (Commit 1 body):

1. Banque de France webstat API state:
   - Reachability: [success/404/403]
   - Authentication: [public / key required]
   - Response format: [SDMX-JSON / CSV / Excel]
   - Dataflow for FR sovereign yields: [dataflow code found]
   - Per-tenor OAT series availability: [list tenors with valid series codes]
   - OATei (linker) availability: [5Y/10Y/20Y/30Y]

2. Alternative data source probes:
   - AFT direct: [reachable / format]
   - TE fetch_fr_yield_curve_nominal: [verify from Sprint CAL-138 code; was it shipped?]
   - FRED OECD mirror: [FR yield series availability]

3. Decision rationale:
   - Primary connector: [Banque de France OR fallback]
   - Linker strategy: [OATei via BdF / OATei via TE / LINKER_UNAVAILABLE]

Create src/sonar/connectors/banque_de_france.py:

"""Banque de France webstat connector.

Public data — no auth required. SDMX-JSON REST API.
Provides FR sovereign yields (OAT) + inflation-indexed (OATei) per tenor.

Empirical probe findings (Commit 1):
- Base URL: https://webstat.banque-france.fr/ws_wsfr/rest/data/
- Dataflow: [probe-validated]
- Format: SDMX-JSON
- Auth: public (descriptive UA recommended)
- Key series:
  - OAT {tenor} nominal: [series codes per tenor]
  - OATei {tenor} indexed: [series codes per tenor]
"""

BDF_UA: Final = "SONAR/2.0 (curves; https://github.com/hugocondesa-debug/sonar-engine)"

class BanqueDeFranceConnector(BaseConnector):
    """Banque de France webstat SDMX API — public REST."""

    CONNECTOR_ID = "banque_de_france"
    USER_AGENT = BDF_UA
    BASE_URL = "https://webstat.banque-france.fr/ws_wsfr/rest/data/"

    async def fetch_yield_curve_nominal(
        self,
        observation_date: date,
    ) -> dict[str, YieldCurvePoint]:
        """Fetch FR OAT nominal yield curve for observation date.

        Returns dict {tenor_label: YieldCurvePoint} for tenors 1M-30Y.
        Handles SDMX-JSON parsing.
        Raises DataUnavailableError if series unreachable.
        """

    async def fetch_yield_curve_linker(
        self,
        observation_date: date,
    ) -> dict[str, YieldCurvePoint]:
        """Fetch FR OATei (inflation-indexed) yield curve.

        Tenors: 5Y, 10Y, 20Y, 30Y.
        Returns empty dict + LINKER_UNAVAILABLE flag if probe revealed sparse.
        """

Tests:
- Unit: connector instantiation + URL building + UA header
- Unit: fetch_yield_curve_nominal success mocked (SDMX-JSON)
- Unit: fetch_yield_curve_linker success mocked
- Unit: 404 → DataUnavailableError
- Unit: empty response → DataUnavailableError
- @pytest.mark.slow live canary: FR yield curve 2024-12-31; assert ≥ 8 tenors

Cassettes:
- tests/fixtures/cassettes/banque_de_france/oat_nominal_2024_12_31.json
- tests/fixtures/cassettes/banque_de_france/oatei_linker_2024_12_31.json

Coverage banque_de_france.py ≥ 85%.
```

### Commit 2 — Fetch methods complete + edge cases

```
feat(connectors): Banque de France fetch methods + weekend/holiday handling

Extend banque_de_france.py:
- Handle French holidays (yield curve not published)
- Backfill logic: previous business day if observation_date is weekend/holiday
- Error handling: partial tenor availability (e.g., 1M missing but 2Y-30Y present)

Tests:
- Unit: weekend handling (Saturday → previous Friday)
- Unit: holiday handling (Bastille Day fallback)
- Unit: partial tenor coverage (fit succeeds with ≥ 6 tenors minimum)
- @pytest.mark.slow canary: FR yield curve 2024-07-14 (Bastille Day) → fallback
```

### Commit 3 — Pipeline integration FR dispatch

```
refactor(pipelines): daily_curves FR dispatch via Banque de France

Update src/sonar/pipelines/daily_curves.py:

1. Import BanqueDeFranceConnector
2. Add FR to T1_7_COUNTRIES tuple (was 8 countries post Sprint CAL-138 scope; now 9):
   Current: ("US", "DE", "EA", "GB", "JP", "CA", ...)
   Post: (..., "FR")

3. Country dispatcher:
   - US → fred (existing)
   - DE → bundesbank (existing Sprint CAL-138)
   - EA → ecb_sdw (existing Sprint CAL-138)
   - GB/JP/CA → te (existing Sprint CAL-138)
   - FR → banque_de_france (NEW — this sprint)

4. NSS fit applied uniform (reused)

5. Connector lifecycle: BanqueDeFranceConnector added to connectors_to_close

Tests:
- Unit: pipeline dispatcher routes FR correctly
- Unit: --all-t1 iterates FR
- Integration @slow: FR yield curve 2024-12-31 persists with confidence ≥ 0.9
- NSS fit RMSE target ≤ 10 bps (DE reference)

Coverage daily_curves.py ≥ 90%.
```

### Commit 4 — Cassettes + live canary + cross-val

```
test: FR yield curve cassettes + live canary + Trésor cross-val

Cassettes shipped:
- banque_de_france/oat_nominal_2024_12_31.json (12 tenors)
- banque_de_france/oatei_linker_2024_12_31.json (4 tenors)

Live canary:
- tests/integration/test_daily_curves_multi_country.py EXTEND
- test_daily_curves_fr_live_canary (@pytest.mark.slow)
- Assert: FR NSSYieldCurveSpot persisted + confidence ≥ 0.9 + rmse_bps ≤ 10

Cross-validation (documented, not automated):
- FR 10Y NSS fit vs Trésor published reference rate
- Expected deviation: ≤ 5 bps for par curve
- Deviation > 10 bps → investigate data source quality

Coverage maintained.
```

### Commit 5 — ADR + pattern notes for follow-on sprints

```
docs(adr+planning): ADR-00XX Banque de France connector + EA periphery pattern

ADR-00XX: National CB connectors for EA periphery curves
- Context: ECB SDW lacks per-country periphery (Sprint A HALT-0 empirical finding)
- Decision: National CB connector per country (Bundesbank-analog for each periphery)
- Rationale: FR pilot validates pattern; IT-BDI / ES-BDE / PT-BPSTAT / NL-DNB follow
- Consequences: 5 national-CB connectors required for EA T1 uniformity; linker varies per country
- Status: Active (post-Sprint-D merge)

Update docs/planning/retrospectives/week10-sprint-curves-fr-bdf-report.md:
- FR connector implementation summary
- Data quality assessment (NSS RMSE + cross-val)
- Pattern lessons for IT/ES/PT/NL sprints:
  - Banque de France SDMX API: [notes]
  - Linker coverage per country: FR solid (OATei), IT decent (BTP€I), PT/ES/NL limited (confirmed Sprint A)
  - Per-CB API divergence risk: document deviations for IT/ES/PT/NL pre-flight probes

Pattern template for follow-on CAL items:
  CAL-CURVES-IT-BDI, CAL-CURVES-ES-BDE, CAL-CURVES-PT-BPSTAT, CAL-CURVES-NL-DNB
  Each ~3-4h CC budget (same as FR pilot).
  Shared: pipeline T1_7_COUNTRIES tuple expansion + dispatcher routing.
```

### Commit 6 — CAL closures + retrospective

```
docs(planning+backlog): Sprint D Banque de France retrospective + CAL closures

CAL-CURVES-FR-BDF CLOSED (resolution):
- Banque de France connector shipped + tested
- FR yield curve operational (12 tenors nominal + 4 linker)
- NSS fit RMSE: [value bps]
- Production impact: overlays cascade gains FR tomorrow 07:30 WEST

Retrospective per v3 format:
docs/planning/retrospectives/week10-sprint-curves-fr-bdf-report.md

Content:
- Empirical probe findings (Banque de France API structure)
- NSS fit quality FR (RMSE + confidence)
- Linker coverage validation (OATei full spectrum)
- Pattern validation for IT/ES/PT/NL follow-on
- Data source quality assessment
- Cross-val vs Trésor reference
- §10 pre-merge checklist + §11 merge via script
- Paralelo with Sprint C: zero primary file conflicts (shared CAL file union-merge)

Pattern notes for Week 11+ sprints:
- CAL-CURVES-IT-BDI (Banca d'Italia) — ~3-4h
- CAL-CURVES-ES-BDE (Banco de España) — ~3-4h
- CAL-CURVES-PT-BPSTAT (Banco de Portugal) — ~3-4h; linker limited
- CAL-CURVES-NL-DNB (De Nederlandsche Bank) — ~3-4h; linker limited

Post Sprint D + 4 follow-ons, EA T1 curves uniform (6 EA periphery + DE + EA aggregate = 8 EA-related).
```

---

## 5. HALT triggers (atomic)

0. **Banque de France API + AFT + TE all fail** for FR yields — HALT and surface. Narrow scope to "FR deferred pending CB API resolution" OR use TE fallback (already shipped).
1. **Banque de France API requires authentication** — if API key needed and not available in .env, scope narrow to TE fallback.
2. **SDMX format unexpected** — if Banque de France uses custom format (not SDMX-JSON standard), investigate. HALT if parsing non-trivial.
3. **Per-tenor series codes not discoverable** — if empirical probe reveals series codes change per tenor unpredictably, document pattern OR narrow scope.
4. **OATei linker series sparse** — if < 3 linker tenors available, emit FR_LINKER_PARTIAL flag + fallback DERIVED real curve; not a HALT.
5. **NSS fit convergence failure** FR specific — emit flag + investigate per-country fit bounds. CAL item opens.
6. **Cassette count < 2** — HALT.
7. **Live canary wall-clock > 30s** — optimize OR split.
8. **Pre-push gate fails** — fix before push.
9. **No `--no-verify`**.
10. **Coverage regression > 3pp** — HALT.
11. **Push before stopping** — script mandates; brief v3 §10.
12. **Sprint C file conflict** — CAL file union-merge trivial.
13. **FR cross-val deviation > 20 bps** vs Trésor reference — investigate data source quality. HALT if systematic.

---

## 6. Acceptance

### Global sprint-end
- [ ] BanqueDeFranceConnector shipped + tested (≥ 8 tenors nominal + ≥ 3 linker)
- [ ] `daily_curves.py` FR dispatch routing + T1 tuple expanded
- [ ] NSS fit FR RMSE ≤ 10 bps (DE reference)
- [ ] Cross-val FR 10Y vs Trésor published: deviation ≤ 20 bps
- [ ] Cassettes ≥ 2 shipped
- [ ] Live canary FR @pytest.mark.slow PASS
- [ ] CAL-CURVES-FR-BDF CLOSED with commit refs
- [ ] ADR-00XX shipped (national CB connectors pattern)
- [ ] Pattern notes shipped for follow-on CAL sprints (IT/ES/PT/NL)
- [ ] Coverage banque_de_france.py ≥ 85%, daily_curves.py ≥ 90%
- [ ] No `--no-verify`
- [ ] Pre-push gate green every push
- [ ] §10 Pre-merge checklist executed
- [ ] Merge via `sprint_merge.sh`
- [ ] Retrospective shipped per v3 format

---

## 7. Report-back artifact

File: `docs/planning/retrospectives/week10-sprint-curves-fr-bdf-report.md`

**Final tmux echo**:
```
SPRINT D FR BANQUE DE FRANCE DONE: N commits on branch sprint-curves-fr-bdf

FR yield curve operational:
- Nominal: N tenors (1M-30Y)
- Linker: N tenors (OATei)
- NSS fit RMSE: [value] bps
- Cross-val vs Trésor: [deviation] bps

CAL-CURVES-FR-BDF CLOSED.
ADR-00XX shipped: national CB connectors pattern for EA periphery.

Pattern validated for follow-on sprints:
- CAL-CURVES-IT-BDI
- CAL-CURVES-ES-BDE
- CAL-CURVES-PT-BPSTAT (linker limited)
- CAL-CURVES-NL-DNB (linker limited)

Production impact: tomorrow 07:30 WEST overlays cascade gains FR (ERP/CRP/rating-spread/expected-inflation).

Total T1 curves coverage post-merge: US + DE + EA + GB + JP + CA + FR (7 countries live).

Paralelo with Sprint C: zero primary file conflicts.

Merge: ./scripts/ops/sprint_merge.sh sprint-curves-fr-bdf

Artifact: docs/planning/retrospectives/week10-sprint-curves-fr-bdf-report.md
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

### Pilot sprint discipline
This is **pilot** for 4 follow-on EA periphery sprints. Pattern lessons captured matter more than raw velocity. ADR-00XX + pattern notes = key deliverables beyond FR-specific code.

### Banque de France expected API
Webstat is Banque de France's public statistics portal. SDMX-JSON endpoint typical for EA central banks. Compare DE Bundesbank (Sprint CAL-138) structure — high likelihood similar.

### Fallback hierarchy
1. **Primary**: Banque de France webstat (national CB, authoritative)
2. **Secondary**: AFT (Agence France Trésor) direct — may publish daily yield curve
3. **Tertiary**: TE fetch_fr_yield_curve_nominal (if shipped Sprint CAL-138)
4. **Fallback**: FRED OECD mirror (monthly, stale — last resort)

HALT trigger 0 fires only if all 4 fail.

### Linker coverage FR vs other EA periphery
FR OATei has **full tenor spectrum** since 1998 — best-in-class EA linker. Makes FR ideal pilot (validates methodology before tackling harder cases).

Follow-on sprints have progressively harder linker:
- IT: BTP€I decent coverage (2003+)
- ES: Bonos indexados limited
- PT: Limited historical (permanent N/A likely)
- NL: Limited historical (permanent N/A likely)

### Paralelo discipline (4th paralelo Day 1)
Sprint A merged. Sprint B merged. Sprint C in flight. Sprint D arranca.

File scope zero primary overlap with Sprint C:
- Sprint C: connectors/oecd_eo.py + indices/monetary/builders.py + daily_monetary_indices.py
- Sprint D: connectors/banque_de_france.py + daily_curves.py

Shared: docs/backlog/calibration-tasks.md. Union-merge trivial.

### Script merge dogfooded
3rd use Day 1 successful. Apply learned patterns (push before stopping, workspace clean, HALT gates) discipline.

### Post-sprint unlock
4 follow-on sprints (~3-4h each) = **12-16h total Week 11 scope** for complete EA periphery curves. Major Phase 2 progression.

---

*End of Sprint D pilot brief. 5-7 commits. FR via Banque de France. Pattern validation for 4 follow-on EA periphery sprints. Paralelo-ready with Sprint C.*
