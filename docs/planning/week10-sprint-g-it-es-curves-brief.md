# Week 10 Day 2 Sprint G — CAL-CURVES-IT-BDI + CAL-CURVES-ES-BDE (Combined EA Periphery)

**Tier scope**: T1 ONLY (16 countries). T2 expansion deferred to Phase 5 per ADR-0010.

**Target**: Probe + ship Banca d'Italia and Banco de España national CB connectors for IT + ES sovereign yield curves. Combined sprint applies ADR-0009 probe-before-scaffold discipline to 2 EA periphery peninsulas simultaneously. Either succeeds with connectors OR documents gaps + pattern library extension (à la Sprint D FR HALT-0 precedent).
**Priority**: HIGH (pattern validation for remaining EA periphery PT + NL; Phase 2 exit progression)
**Budget**: 5-7h CC
**Commits**: ~7-10
**Base**: branch `sprint-curves-it-es-bdi-bde` (isolated worktree `/home/macro/projects/sonar-wt-curves-it-es`)
**Concurrency**: PARALELO with Sprint F (CPI + inflation T1 wrappers, in flight). Zero primary file overlap.

**Brief format**: v3

---

## 1. Scope

In (2 parallel probe tracks + shared infrastructure):

### Track 1 — Banca d'Italia probe + connector (~2-3h)
- `src/sonar/connectors/banca_ditalia.py` NEW — IT national CB connector
- **Pre-flight probe mandatory** (ADR-0009): identify API endpoint + dataflow + series codes for IT sovereign yields
- Target endpoints to probe (empirical investigation order):
  1. Banca d'Italia BDS (statistical database) SDMX API
  2. Banca d'Italia infostat REST API
  3. MEF (Ministero dell'Economia) Tesoro debt data
  4. ECB SDW FM dataflow IT override (long shot per Sprint A finding)
  5. FRED IRLTLT01ITM156N (monthly 10Y only, fallback)
- Target series (if viable):
  - BTP 1M, 3M, 6M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y, 15Y, 20Y, 30Y (nominal)
  - BTP€I (inflation-indexed) 5Y, 10Y, 20Y, 30Y (linker — Italy well-established post-2003)

### Track 2 — Banco de España probe + connector (~2-3h)
- `src/sonar/connectors/banco_espana.py` NEW — ES national CB connector
- **Pre-flight probe mandatory** (ADR-0009): identify API endpoint for ES sovereign yields
- Target endpoints to probe:
  1. Banco de España BDEstad statistical portal SDMX API
  2. Banco de España web API (non-standard REST if exists)
  3. Tesoro Público (Spanish Treasury) debt data
  4. ECB SDW FM dataflow ES override
  5. FRED IRLTLT01ESM156N fallback
- Target series:
  - Bono 1M-30Y nominal
  - Bonos indexados (ES linkers — LIMITED coverage confirmed Sprint A)

### Track 3 — Pipeline integration (shared, ~1h)
- `src/sonar/pipelines/daily_curves.py` MODIFY — add IT + ES dispatch if connectors shipped
- Expand `T1_CURVES_COUNTRIES` tuple to include IT + ES (if probes succeed)
- Connector lifecycle: BancaDitaliaConnector + BancoEspanaConnector added to connectors_to_close
- If HALT-0 per country, document + defer

### Track 4 — ADR-0009 pattern library extension + retro (~1h)
- Update ADR-0009 with IT + ES probe findings (success patterns OR failure patterns)
- Pattern template for remaining EA periphery (PT-BPSTAT + NL-DNB)
- CAL closures per successful country OR CAL sharpening per HALT-0 country
- Retrospective per v3 format

Out:
- PT + NL curves (separate sprints — PT-BPSTAT + NL-DNB per ADR-0009; NL flagged HIGH RISK per OpenDatasoft precedent)
- IT/ES linker handling edge cases (if partial, emit LINKER_UNAVAILABLE; no deep fix this sprint)
- Historical backfill (Phase 2.5 backtest scope)
- Non-EA T1 (AU/NZ/CH/SE/NO/DK — separate CAL-CURVES-T1-SPARSE-*-PROBE items)

---

## 2. Spec reference

Authoritative:
- `docs/backlog/calibration-tasks.md` — CAL-CURVES-IT-BDI + CAL-CURVES-ES-BDE entries (opened Sprint A)
- `docs/adr/ADR-0009-national-cb-connectors-ea-periphery.md` — probe-before-scaffold discipline canonical
- `docs/planning/retrospectives/week10-sprint-curves-fr-bdf-report.md` — Sprint D FR pilot (HALT-0 precedent + template)
- `docs/planning/retrospectives/week10-sprint-cal138-report.md` — CAL-138 DE Bundesbank pattern (closest successful template)
- `docs/planning/retrospectives/week10-sprint-ea-periphery-report.md` — Sprint A HALT-0 ECB SDW EA periphery gap
- `src/sonar/connectors/bundesbank.py` — DE Bundesbank reference (working EA national CB)
- `src/sonar/connectors/banque_de_france.py` — Sprint D FR scaffold (documentation-first, HALT-0)
- `src/sonar/pipelines/daily_curves.py` — current multi-country dispatcher
- `src/sonar/overlays/nss_curves/` — NSS fit logic (reused uniform)

**Pre-flight requirement**: Commit 1 CC:
1. Read Sprint D FR BDF retrospective (full pattern template + HALT-0 precedent findings)
2. Read ADR-0009 national-CB connectors for EA periphery (probe discipline canonical)
3. Read Sprint A EA periphery retro (ECB SDW gap context)
4. Read Sprint CAL-138 DE Bundesbank implementation (closest successful template)
5. Probe Banca d'Italia APIs in priority order:
   ```bash
   # BDS SDMX probe
   curl -s -H "User-Agent: SONAR/2.0" "https://sdw-wsrest.ecb.europa.eu/service/data/BDS?format=sdmx-json&startPeriod=2024-12-01&endPeriod=2024-12-31" | head -100

   # Infostat REST probe (Banca d'Italia statistical portal)
   curl -s "https://infostat.bancaditalia.it/inquiry/home" | head -50

   # MEF Tesoro debt data
   curl -s "https://www.mef.gov.it/ufficio-stampa/" | head -20

   # ECB SDW FM dataflow IT override (Sprint A said empty, re-probe for Sprint G)
   curl -s "https://data-api.ecb.europa.eu/service/data/FM?detail=dataonly&format=jsondata&filter=REF_AREA:IT&startPeriod=2026-04-18&endPeriod=2026-04-22" | head -30

   # FRED IT 10Y fallback
   curl -s "https://api.stlouisfed.org/fred/series/observations?series_id=IRLTLT01ITM156N&api_key=$FRED_API_KEY&file_type=json&limit=3" | head -30
   ```
6. Probe Banco de España APIs in priority order:
   ```bash
   # BDEstad statistical portal SDMX
   curl -s "https://www.bde.es/webbde/es/estadis/infoest/bde_datasetAux.html" | head -50

   # Banco de España SDMX REST (if exists)
   curl -s -H "User-Agent: SONAR/2.0" "https://www.bde.es/webbde/ws_wsbe/rest/data/" | head -30

   # Tesoro Público debt data
   curl -s "https://www.tesoro.es/sites/default/files/" | head -20

   # ECB SDW FM dataflow ES override
   curl -s "https://data-api.ecb.europa.eu/service/data/FM?detail=dataonly&format=jsondata&filter=REF_AREA:ES&startPeriod=2026-04-18&endPeriod=2026-04-22" | head -30

   # FRED ES 10Y fallback
   curl -s "https://api.stlouisfed.org/fred/series/observations?series_id=IRLTLT01ESM156N&api_key=$FRED_API_KEY&file_type=json&limit=3" | head -30
   ```
7. Document Commit 1 body per country probe matrix:
   - Endpoint reachability (200/403/404/timeout)
   - Authentication (public/key-required)
   - Response format (SDMX-JSON / REST / HTML only)
   - Available series per tenor
   - Linker availability
8. Per ADR-0009 HALT-0 precedent: narrow scope per-country if empirical probes reveal all 5 paths dead for either country. Ship scaffold documentation + sharpened CAL items + pattern extension.

**Pre-flight HALT triggers per country**:
- IT HALT-0: all 5 probe paths fail → IT connector scaffolded only, CAL-CURVES-IT-BDI sharpened
- ES HALT-0: all 5 probe paths fail → ES connector scaffolded only, CAL-CURVES-ES-BDE sharpened
- Both HALT-0: sprint ships scaffold discipline + ADR-0009 extension, 1-2h wall-clock
- Both success: sprint ships 2 connectors + pipeline integration, 5-7h wall-clock
- Split: one success + one HALT-0, ~3-4h wall-clock

---

## 3. Concurrency — PARALELO with Sprint F (2nd paralelo Day 2)

**Sprint G worktree**: `/home/macro/projects/sonar-wt-curves-it-es`
**Sprint G branch**: `sprint-curves-it-es-bdi-bde`

**Sprint F (for awareness)**: CAL-CPI-INFL-T1-WRAPPERS, worktree `/home/macro/projects/sonar-wt-cpi-infl-t1-wrappers`, currently arranque pending CC re-prompt after brief upload.

**Sprint E already merged** (6e1d2b2 on main).

**File scope Sprint G**:
- `src/sonar/connectors/banca_ditalia.py` NEW (primary)
- `src/sonar/connectors/banco_espana.py` NEW (primary)
- `src/sonar/pipelines/daily_curves.py` MODIFY (primary — IT + ES dispatch + tuple expansion if successful)
- `tests/unit/test_connectors/test_banca_ditalia.py` NEW
- `tests/unit/test_connectors/test_banco_espana.py` NEW
- `tests/integration/test_daily_curves_multi_country.py` EXTEND (IT + ES canaries if successful)
- `tests/fixtures/cassettes/banca_ditalia/` NEW (if connector succeeds)
- `tests/fixtures/cassettes/banco_espana/` NEW (if connector succeeds)
- `docs/backlog/calibration-tasks.md` MODIFY (close/sharpen per country outcomes)
- `docs/adr/ADR-0009-national-cb-connectors-ea-periphery.md` MODIFY (extend pattern library with IT + ES findings)
- `docs/planning/retrospectives/week10-sprint-curves-it-es-report.md` NEW

**Sprint F file scope** (for awareness, DO NOT TOUCH):
- `src/sonar/indices/monetary/builders.py` (Sprint F primary — M2 CPI paths)
- `src/sonar/connectors/te.py` APPEND (Sprint F — CPI wrappers)
- `src/sonar/connectors/ecb_sdw.py` EXTEND (Sprint F may extend for EA HICP fallback)
- `src/sonar/pipelines/daily_monetary_indices.py` (Sprint F)

**Potential overlap zones**:
- `src/sonar/connectors/ecb_sdw.py` — Sprint F may EXTEND for HICP; Sprint G may QUERY ECB SDW FM dataflow for probe. Read-only + append scenarios. Zero conflict.
- `docs/backlog/calibration-tasks.md` — both modify; union-merge trivial (different sections: Sprint F closes CAL-CPI-INFL; Sprint G sharpens CAL-CURVES-*).

**Zero primary-file overlap expected**:
- Sprint F: builders.py + daily_monetary_indices.py + te.py APPEND
- Sprint G: daily_curves.py + new national CB connectors

**Rebase expected minor**: alphabetical merge priority unclear (F < G alphabetically). Whichever completes second rebases CAL file + possibly ADR (no ADR overlap expected).

**Pre-merge checklist** (brief v3 §10):
- [ ] All commits pushed
- [ ] Workspace clean
- [ ] Pre-push gate green
- [ ] Branch tracking set
- [ ] Per-country probe outcomes documented (success OR HALT-0 pattern)
- [ ] NSS fit RMSE per successful country ≤ 10 bps
- [ ] Tier scope verified T1 only (per ADR-0010)

**Merge execution** (brief v3 §11):
```bash
./scripts/ops/sprint_merge.sh sprint-curves-it-es-bdi-bde
```

---

## 4. Commits

### Commit 1 — Pre-flight probe IT + ES + ADR-0009 context

```
feat(connectors): IT + ES pre-flight + scaffold probe (ADR-0009 compliance)

Pre-flight findings (Commit 1 body):

1. ADR-0009 context review:
   - Sprint D FR-BDF: HALT-0 after 5 probe paths dead
   - Precedent: Banque de France legacy SDMX REST decommissioned mid-2024 → OpenDatasoft migration
   - Pattern library: probe before scaffold; 4 follow-ons annotated

2. IT probe matrix (Banca d'Italia):
   - BDS SDMX: [reachability + format]
   - Infostat REST: [reachability + format]
   - MEF Tesoro: [reachability + format]
   - ECB SDW FM override: [per Sprint A empty; re-probe Sprint G]
   - FRED IRLTLT01ITM156N: [monthly 10Y-only confirmation]

3. ES probe matrix (Banco de España):
   - BDEstad portal SDMX: [reachability + format]
   - Banco de España REST: [reachability + format]
   - Tesoro Público: [reachability + format]
   - ECB SDW FM override: [per Sprint A empty]
   - FRED IRLTLT01ESM156N: [monthly 10Y-only confirmation]

4. Decision per country:
   - IT: [probe-viable path OR HALT-0 with scaffold]
   - ES: [probe-viable path OR HALT-0 with scaffold]

5. Sprint scope narrowing (if applicable):
   - Both success: proceed full sprint 7+ commits
   - Split outcome: proceed partial sprint (successful country implemented, other scaffolded)
   - Both HALT-0: proceed scaffold sprint (~2-3h, pattern library extension)

Create scaffold files:
- src/sonar/connectors/banca_ditalia.py
- src/sonar/connectors/banco_espana.py

Each scaffold:
- BaseConnector interface preserved
- Documentation-first (probe matrix embedded in module docstring)
- All fetch methods raise InsufficientDataError with probe-evidence
- Unit tests assert scaffold behaviors (raises expected errors)

If probes succeed (scenario: full sprint), Commits 2-4 extend scaffolds with real fetch logic.

Coverage scaffold ≥ 80% (documentation-heavy).
```

### Commit 2 — IT connector implementation (if probe succeeds)

```
feat(connectors): Banca d'Italia IT yield curve implementation

[Conditional on Commit 1 probe success for IT]

Extend banca_ditalia.py scaffold with live fetch methods:

class BancaDItaliaConnector(BaseConnector):
    """Banca d'Italia national CB connector.

    Empirical probe findings (Commit 1):
    - Base URL: [probe-validated endpoint]
    - Dataflow: [probe-validated dataflow code]
    - Format: [SDMX-JSON OR CSV OR other]
    - Auth: [public/key-required]
    - Key series per tenor: [probe-validated series codes]
    """

    async def fetch_yield_curve_nominal(
        self,
        observation_date: date,
    ) -> dict[str, YieldCurvePoint]:
        """Fetch IT BTP nominal yield curve for observation date.

        Returns dict {tenor_label: YieldCurvePoint} for tenors 1M-30Y.
        Handles response parsing per probe-validated format.
        """

    async def fetch_yield_curve_linker(
        self,
        observation_date: date,
    ) -> dict[str, YieldCurvePoint]:
        """Fetch IT BTP€I (inflation-indexed) yield curve.

        Tenors: 5Y, 10Y, 20Y, 30Y (Italy well-established linkers post-2003).
        """

Tests:
- Unit: 5+ unit tests (happy paths + error cases)
- Unit: weekend/holiday handling (Italian holidays)
- @pytest.mark.slow live canary: IT yield curve 2024-12-31

Cassettes per method.

Coverage ≥ 85%.

[Skip this commit if Commit 1 HALT-0 for IT]
```

### Commit 3 — ES connector implementation (if probe succeeds)

```
feat(connectors): Banco de España ES yield curve implementation

[Conditional on Commit 1 probe success for ES]

Mirror Commit 2 pattern for Spanish Bono + Bonos indexados.

ES linker handling (per Sprint A finding): limited coverage likely →
emit ES_LINKER_UNAVAILABLE flag + fallback DERIVED real curve if sparse.

Tests + cassettes per method.

Coverage ≥ 85%.

[Skip this commit if Commit 1 HALT-0 for ES]
```

### Commit 4 — Pipeline integration IT + ES dispatch

```
refactor(pipelines): daily_curves IT + ES dispatch

[Conditional on any Commits 2-3 shipped]

Update src/sonar/pipelines/daily_curves.py:

1. Import BancaDItaliaConnector + BancoEspanaConnector (for successful countries)

2. T1_CURVES_COUNTRIES tuple expansion:
   Current: ("US", "DE", "EA", "GB", "JP", "CA") [post Sprint E]
   Post: (..., "IT", "ES") [if both ship; adjust per outcome]

3. Country dispatcher:
   - IT → banca_ditalia.fetch_yield_curve_nominal (if successful)
   - ES → banco_espana.fetch_yield_curve_nominal (if successful)

4. NSS fit applied uniform

5. Connector lifecycle additions

Tests:
- Unit: dispatcher routes IT + ES correctly (if successful)
- Integration @slow: --all-t1 includes IT + ES persistence

Coverage daily_curves.py ≥ 90%.
```

### Commit 5 — Cassettes + live canaries (if any successes)

```
test: yield curve cassettes + live canaries IT + ES (successful)

[Conditional on Commits 2-3 shipped]

Cassettes per successful country:
- banca_ditalia/btp_nominal_2024_12_31.json (if IT success)
- banca_ditalia/btpei_linker_2024_12_31.json (if IT linker)
- banco_espana/bono_nominal_2024_12_31.json (if ES success)
- banco_espana/bonos_indexados_2024_12_31.json (if ES linker)

Live canaries per country:
- test_daily_curves_it_live_canary (if IT)
- test_daily_curves_es_live_canary (if ES)
- Assert: NSSYieldCurveSpot persisted + confidence ≥ 0.9 + rmse_bps ≤ 10

Cross-val (if successful):
- IT 10Y NSS fit vs MEF published reference (if available) — deviation ≤ 20 bps
- ES 10Y NSS fit vs Tesoro reference (if available) — deviation ≤ 20 bps

Coverage maintained.
```

### Commit 6 — ADR-0009 pattern library extension

```
docs(adr): ADR-0009 extension — IT + ES probe findings

Update docs/adr/ADR-0009-national-cb-connectors-ea-periphery.md:

New section "EA periphery probe outcomes" (evolving matrix):
- FR-BDF (Sprint D): HALT-0 after 5 paths dead (legacy SDMX decommissioned)
- IT-BDI (this sprint): [success pattern OR HALT-0 pattern]
- ES-BDE (this sprint): [success pattern OR HALT-0 pattern]
- PT-BPSTAT (pending): [risk assessment per IT/ES findings]
- NL-DNB (pending): [HIGH RISK confirmed per OpenDatasoft precedent if IT/ES also OpenDatasoft]

Pattern library update:
- If both IT + ES succeed via BDS/BDEstad: template for PT-BPSTAT (Banco de Portugal likely similar pattern)
- If both HALT-0: reinforces ADR-0009 probe discipline; NL-DNB risk maximal
- If split: pattern-specific guidance per country platform

Update Alternative approaches if all 4 EA periphery eventually fail:
- Direct Treasury data per country (MEF IT, Tesoro ES, Tesouro PT, Dutch State Treasury NL)
- Bloomberg/Refinitiv commercial (budget concern — defer Phase 3+)
- Yield curve synthesis from generic rates (accept lower fidelity)

Action items per country CAL sharpening per empirical finding.
```

### Commit 7 — CAL closures + retrospective

```
docs(planning+backlog): Sprint G IT + ES retrospective + CAL resolutions

CAL-CURVES-IT-BDI — Status per outcome:
- If success: CLOSED with commit refs
- If HALT-0: SHARPENED with probe evidence + clear unblock criteria

CAL-CURVES-ES-BDE — Status per outcome:
- If success: CLOSED with commit refs
- If HALT-0: SHARPENED with probe evidence + clear unblock criteria

Retrospective per v3 format:
docs/planning/retrospectives/week10-sprint-curves-it-es-report.md

Content per country:
- Empirical probe findings (5-path matrix)
- Decision rationale (success path OR HALT-0)
- If success: NSS fit quality + linker coverage + production validation
- If HALT-0: pattern evidence + CAL sharpening
- ADR-0009 pattern library update reference
- §10 pre-merge checklist + §11 merge via script
- Paralelo with Sprint F: zero file conflicts

Pattern evolution for remaining EA periphery:
- PT-BPSTAT probe guidance per IT/ES findings
- NL-DNB risk update per IT/ES + OpenDatasoft precedent

Sprint outcome scenarios:
- Both success: T1 curves coverage 6 → 8 countries (US/DE/EA/GB/JP/CA/IT/ES)
- Split: T1 curves coverage 6 → 7 countries
- Both HALT-0: T1 curves coverage unchanged 6; ADR-0009 pattern library enriched
- Production impact per successful country: overlays cascade tomorrow 07:30 WEST
```

---

## 5. HALT triggers (atomic)

0. **IT all 5 probe paths fail** — HALT-0 for IT; scaffold documentation + CAL sharpening + ADR extension. Ship partial sprint.
1. **ES all 5 probe paths fail** — HALT-0 for ES; scaffold documentation + CAL sharpening + ADR extension. Ship partial sprint.
2. **Both IT + ES HALT-0** — sprint scope narrows to ~2-3h: scaffolds + ADR extension + 2 CAL sharpenings. Valid outcome.
3. **Authentication required** — if any probe path requires key not in .env, narrow scope to other paths OR HALT-0 that country.
4. **Response format unexpected** — if API returns custom/non-SDMX format, evaluate parsing feasibility. If > 1h work, defer OR HALT-0.
5. **Per-tenor series codes not discoverable** — document pattern if some tenors work; emit {COUNTRY}_CURVE_PARTIAL flag. Not a HALT.
6. **Linker sparse** — if < 3 linker tenors available per country, emit {COUNTRY}_LINKER_PARTIAL flag. Not a HALT.
7. **NSS fit convergence failure per country** — emit flag + investigate bounds. CAL item opens.
8. **Cassette count < 4** — HALT (minimum 2 per successful country × 2 countries target).
9. **Live canary wall-clock > 45s combined** — optimize OR split.
10. **Pre-push gate fails** — fix before push.
11. **No `--no-verify`**.
12. **Coverage regression > 3pp** — HALT.
13. **Push before stopping** — script mandates; brief v3 §10.
14. **Sprint F file conflict** — CAL file union-merge trivial; ecb_sdw.py read-only + append respect; zero primary conflict.
15. **Cross-val deviation > 30 bps** vs MEF/Tesoro reference per country — investigate data quality. HALT if systematic.
16. **ADR-0010 violation** — all work T1 per ADR-0010. Brief header enforces.

---

## 6. Acceptance

### Global sprint-end (flexible per outcome)
- [ ] IT + ES probes documented in Commit 1 body (both outcomes — success OR HALT-0 — valid)
- [ ] Per successful country (0, 1, or 2):
  - [ ] Connector shipped + tested (≥ 80% coverage)
  - [ ] NSS fit RMSE ≤ 10 bps
  - [ ] Cassettes ≥ 2 per country
  - [ ] Live canary @pytest.mark.slow PASS
- [ ] Per HALT-0 country (0, 1, or 2):
  - [ ] Scaffold file shipped (documentation-first, raises InsufficientDataError)
  - [ ] Unit tests assert scaffold behaviors
  - [ ] Probe matrix documented in module docstring
  - [ ] CAL item sharpened with unblock criteria
- [ ] ADR-0009 pattern library extension shipped (regardless of outcome)
- [ ] `daily_curves.py` T1_CURVES_COUNTRIES tuple updated per outcome
- [ ] CAL-CURVES-IT-BDI + CAL-CURVES-ES-BDE both resolved (CLOSED or SHARPENED)
- [ ] Coverage per connector shipped ≥ 85% (full) OR ≥ 80% (scaffold-only)
- [ ] No `--no-verify`
- [ ] Pre-push gate green every push
- [ ] §10 Pre-merge checklist executed
- [ ] Merge via `sprint_merge.sh`
- [ ] Retrospective shipped per v3 format
- [ ] ADR-0010 tier scope compliance verified

---

## 7. Report-back artifact

File: `docs/planning/retrospectives/week10-sprint-curves-it-es-report.md`

**Final tmux echo**:
```
SPRINT G IT + ES CURVES DONE: N commits on branch sprint-curves-it-es-bdi-bde

Outcomes per country:
- IT-BDI: [SUCCESS / HALT-0]
  - If SUCCESS: NSS RMSE [N] bps, [N] tenors, linker [AVAILABLE/PARTIAL/UNAVAILABLE]
  - If HALT-0: [1-line cause + sharpened CAL evidence]

- ES-BDE: [SUCCESS / HALT-0]
  - If SUCCESS: NSS RMSE [N] bps, [N] tenors, linker [PARTIAL expected]
  - If HALT-0: [1-line cause + sharpened CAL evidence]

CAL-CURVES-IT-BDI: [CLOSED / SHARPENED]
CAL-CURVES-ES-BDE: [CLOSED / SHARPENED]

ADR-0009 pattern library: extended with IT + ES findings.

Pattern guidance for remaining EA periphery:
- PT-BPSTAT: [updated risk assessment per IT/ES outcomes]
- NL-DNB: [updated risk assessment — HIGH likely per OpenDatasoft precedent]

T1 curves coverage post-merge: [current 6 + N successes] / 16 countries.

Production impact: tomorrow 07:30 WEST overlays cascade gains [N successful countries].

Paralelo with Sprint F: zero file conflicts.

Merge: ./scripts/ops/sprint_merge.sh sprint-curves-it-es-bdi-bde

Artifact: docs/planning/retrospectives/week10-sprint-curves-it-es-report.md
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

Live canaries (@pytest.mark.slow) run explicitly if any Commits 2-3 shipped.

---

## 9. Notes on implementation

### Probe-before-scaffold discipline canonical
Per ADR-0009, empirical probe is **mandatory** for EA periphery national CB connectors. Sprint D FR HALT-0 precedent: 5 paths probed, all dead, scaffold shipped. Same rigor IT + ES.

### Dual pilot strategy rationale
Combined sprint IT + ES:
- Pro: broader probability distribution (2 countries vs 1), one sprint covers 2 CAL items, shared infrastructure (pipeline + ADR extension)
- Con: slightly longer wall-clock (5-7h vs 3-4h single)
- Decision: ADR-0009 pattern library benefits most from 2-country data point (trend clearer)

### Linker handling variants
- IT BTP€I: well-established linker post-2003, decent probability of 4-tenor coverage
- ES Bonos indexados: limited per Sprint A finding, likely LINKER_UNAVAILABLE
- Graceful: emit per-country flag; fallback DERIVED real curve via BEI if no linker

### Italian holidays + Spanish holidays
Different from FR (Bastille Day). Document per-country holiday sets if connectors ship.

### ECB SDW FM re-probe
Sprint A confirmed ECB SDW FM dataflow has only {U2, DK, GB, JP, SE, US}. IT + ES absent. Re-probe Sprint G to confirm (unlikely changed) but document completeness.

### Paralelo discipline
Sprint G connectors/daily_curves.py vs Sprint F builders.py/daily_monetary_indices.py. Zero primary overlap. CAL file union-merge trivial.

### Script merge dogfooded
8th production use (Day 1 + Day 2 Sprints E + F + G). Apply learned patterns.

### Tier scope T1 only
All work targets IT + ES (both T1 per ADR-0005 + country_tiers.yaml). ADR-0010 compliance absolute.

### Post-sprint state (any outcome)
- If both success: T1 curves 8/16 countries (50%)
- If split: T1 curves 7/16 (44%)
- If both HALT-0: T1 curves unchanged 6/16, but ADR-0009 pattern library + 2 CAL sharpenings enrich Week 11+ sprint planning
- Remaining after sprint: PT-BPSTAT + NL-DNB pending + 6 T1 sparse (AU/NZ/CH/SE/NO/DK)

### Week 11+ follow-on based on outcomes
- If IT + ES both HALT-0 on OpenDatasoft-like platforms: PT-BPSTAT + NL-DNB likely also HALT-0; pattern inversion to Treasury direct data sources OR commercial feed consideration Phase 3+
- If IT + ES mixed: country-specific patterns per outcome
- If both success: PT-BPSTAT + NL-DNB likely similar path (BDEstad-analog)

---

*End of Sprint G brief. 7-10 commits. Probe + ship IT + ES EA periphery curves per ADR-0009 discipline. Either outcome valid: success ships connectors, HALT-0 enriches pattern library. Paralelo-ready with Sprint F.*
