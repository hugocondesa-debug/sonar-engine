# Week 10 Day 2 Sprint I — CAL-CURVES-FR-TE-PROBE

**Tier scope**: T1 ONLY (16 countries). T2 expansion deferred to Phase 5 per ADR-0010.

**Target**: Re-probe TE per-tenor yield coverage for France. Sprint D FR-BDF (HALT-0 national CB) noted "TE GFRN10 10Y-only, below MIN_OBSERVATIONS=6" — but never ran per-tenor sweep. Per ADR-0009 v2 (TE Path 1 canonical, shipped Sprint H), France may be viable via TE cascade if ≥ 6 tenors cover daily. Closes ADR-0009 v2 validation for France.
**Priority**: HIGH (closes FR EA periphery gap; validates ADR-0009 v2 systematically for FR; T1 curves 8 → 9 if success)
**Budget**: 2-3h CC
**Commits**: ~4-5
**Base**: branch `sprint-curves-fr-te-probe` (isolated worktree `/home/macro/projects/sonar-wt-curves-fr-te-probe`)
**Concurrency**: PARALELO with Sprint J (CAL-M4-T1-FCI-EXPANSION). Zero primary file overlap.

**Brief format**: v3

---

## 1. Scope

In (3 tracks):

### Track 1 — TE FR per-tenor probe + decision (~30min-1h)
Per ADR-0009 v2 TE Path 1 discipline, probe FR full tenor spectrum:

```bash
set -a && source .env && set +a
for tenor in "1 month" "3 month" "6 month" "1 year" "2 year" "3 year" "5 year" "7 year" "10 year" "15 year" "20 year" "30 year"; do
    url="https://api.tradingeconomics.com/historical/country/france/indicator/government%20bond%20${tenor// /%20}?c=${TE_API_KEY}&format=json&d1=2024-12-01&d2=2024-12-05"
    result=$(curl -s "$url" | jq '.[0] | {HistoricalDataSymbol, Frequency, Value}' 2>/dev/null)
    echo "FR ${tenor}: $result"
done
```

Document Commit 1 per-tenor coverage matrix:
- HistoricalDataSymbol per tenor
- Frequency (daily/monthly)
- Historical range
- Sample values

**Decision criteria (mirror Sprint H)**:
- ≥ 6 tenors daily → ship via TE cascade (mirror CAL-138 GB/JP/CA + Sprint H IT/ES pattern)
- < 6 tenors daily → HALT-0 per ADR-0009 sub-caso B (confirm Sprint D finding definitively + update ADR)

### Track 2 — TE FR yield wrapper (if probe succeeds, ~1h)
Mirror Sprint H IT + ES pattern exactly:

- `src/sonar/connectors/te.py` APPEND (yield section, after Sprint H IT + ES wrappers):
  - `fetch_fr_yield_curve_nominal(observation_date)` → returns dict of YieldCurvePoint per tenor
- HistoricalDataSymbol source-drift guard (GFRN10 documented Sprint D as 10Y reference)
- Per-tenor series codes from Commit 1 probe

### Track 3 — Pipeline integration + tests + ADR update + retro (~1h)
**If FR probe succeeds**:
- `src/sonar/pipelines/daily_curves.py` MODIFY:
  - Expand T1_CURVES_COUNTRIES tuple: `(US, DE, EA, GB, JP, CA, IT, ES)` → `(US, DE, EA, GB, JP, CA, IT, ES, FR)` (8 → 9 countries)
  - Dispatcher: FR → te.fetch_fr_yield_curve_nominal
- Cassettes + live canary @pytest.mark.slow FR NSS fit
- Sprint D FR-BDF scaffold (banque_de_france.py) retained as future direct-CB placeholder
- CAL-CURVES-FR-BDF SHARPENED (national CB still BLOCKED per Sprint D; TE cascade shipped as ADR-0009 v2 canonical path)
- CAL-CURVES-FR-TE-PROBE CLOSED
- ADR-0009 addendum: FR success adds to per-country probe outcomes table

**If FR HALT-0** (all tenors non-daily/empty):
- Commit 1 documents definitive per-tenor gap
- CAL-CURVES-FR-BDF remains BLOCKED per Sprint D unblock criteria
- CAL-CURVES-FR-TE-PROBE CLOSED (negative outcome documented)
- ADR-0009 addendum: FR confirmed ternary sub-caso B (same as IT Sprint G)
- No pipeline changes
- Retrospective documents HALT-0 + pattern library update

Out:
- FR linker (OAT€I) probe — separate CAL item if needed
- Other EA periphery countries (PT + NL pending; T1 sparse pending)

---

## 2. Spec reference

Authoritative:
- `docs/backlog/calibration-tasks.md` — CAL-CURVES-FR-TE-PROBE entry (opened Sprint H)
- `docs/adr/ADR-0009-national-cb-connectors-ea-periphery.md` v2 — TE Path 1 canonical (Sprint H amendment, 1e04362)
- `docs/planning/retrospectives/week10-sprint-curves-fr-bdf-report.md` — Sprint D HALT-0 (national CB; noted TE GFRN10 10Y-only)
- `docs/planning/retrospectives/week10-sprint-curves-it-es-te-report.md` — Sprint H TE cascade pattern template (primary reference)
- `src/sonar/connectors/te.py` — existing TE yield wrappers (Sprint H IT/ES + CAL-138 GB/JP/CA)
- `src/sonar/pipelines/daily_curves.py` — current 8-country dispatcher
- `src/sonar/connectors/banque_de_france.py` — Sprint D scaffold (retained)
- `docs/adr/ADR-0010-t1-complete-before-t2-expansion.md` — tier scope lock

**Pre-flight requirement**: Commit 1 CC:
1. Read Sprint H retrospective (primary pattern template) + Sprint D FR-BDF retrospective
2. Run per-tenor probe sweep (command above)
3. Document Commit 1 body — per-tenor matrix FR
4. Decision: ≥ 6 daily tenors → ship TE cascade / < 6 → HALT-0

**Pre-flight HALT trigger**: if probe reveals < 6 tenors daily OR systematic errors across 12 tenors, HALT-0 per ADR-0009 v2.

---

## 3. Concurrency — PARALELO with Sprint J

**Sprint I worktree**: `/home/macro/projects/sonar-wt-curves-fr-te-probe`
**Sprint I branch**: `sprint-curves-fr-te-probe`

**Sprint J (for awareness)**: CAL-M4-T1-FCI-EXPANSION, worktree `/home/macro/projects/sonar-wt-m4-fci-t1`

**File scope Sprint I**:
- `src/sonar/connectors/te.py` APPEND yield section (primary, if probe succeeds)
- `src/sonar/pipelines/daily_curves.py` MODIFY (primary, if probe succeeds)
- `tests/unit/test_connectors/test_te*.py` EXTEND
- `tests/integration/test_daily_curves_multi_country.py` EXTEND
- `tests/fixtures/cassettes/te_yield_fr_*.json` NEW (conditional)
- `docs/backlog/calibration-tasks.md` MODIFY (close CAL-CURVES-FR-TE-PROBE per outcome)
- `docs/adr/ADR-0009-national-cb-connectors-ea-periphery.md` MODIFY (FR probe outcome addendum)
- `docs/planning/retrospectives/week10-sprint-curves-fr-te-probe-report.md` NEW

**Sprint J file scope** (DO NOT TOUCH):
- `src/sonar/indices/financial/builders.py` (Sprint J primary — M4 FCI builders; actually `src/sonar/indices/monetary/builders.py` since M4 is monetary indice #4)
- `src/sonar/pipelines/daily_monetary_indices.py` (Sprint J M4 dispatch)
- Sprint J connectors for VIX + credit spread + NEER

**Potential overlap zones**:
- `src/sonar/connectors/te.py` — both Sprints may APPEND. Sprint I in yield section. Sprint J if uses TE for VIX/NEER generic per country, appends in different section. **Zero overlap** if bookmark zones respected.
- `docs/backlog/calibration-tasks.md` — both modify; different sections (CAL-CURVES-* vs CAL-M4-*); union-merge trivial.

**Zero primary-file conflict expected**.

**Rebase expected minor**: alphabetical merge priority — Sprint I (i < j) ships first. Sprint J rebases CAL file (union-merge trivial).

**Pre-merge checklist** (brief v3 §10):
- [ ] All commits pushed
- [ ] Workspace clean
- [ ] Pre-push gate green
- [ ] Branch tracking set
- [ ] FR probe outcome documented (success OR HALT-0)
- [ ] If success: live canary PASS, NSS RMSE ≤ 10 bps
- [ ] Tier scope verified T1 only (per ADR-0010)

**Merge execution** (brief v3 §11):
```bash
./scripts/ops/sprint_merge.sh sprint-curves-fr-te-probe
```

---

## 4. Commits

### Commit 1 — Pre-flight probe + decision

```
feat(connectors): FR yield per-tenor TE probe + decision (Sprint I C1)

Pre-flight findings (Commit 1 body):

Per-tenor TE probe France:
- 1 month: [HistoricalDataSymbol + Frequency + value]
- 3 month: [HistoricalDataSymbol + Frequency + value]
- 6 month: ...
- 1 year: ...
- 2 year: ...
- 3 year: ...
- 5 year: ...
- 7 year: ...
- 10 year: GFRN10 (documented Sprint D)
- 15 year: ...
- 20 year: ...
- 30 year: ...

Summary:
- Daily tenors: [N]
- Monthly tenors: [N]
- Unavailable tenors: [N]

Decision (per ADR-0009 v2):
- If ≥ 6 daily tenors: ship TE cascade (proceed Commits 2-4)
- If < 6 daily tenors: HALT-0 per ADR-0009 sub-caso B (scope narrow Commits 2-3 skipped, Commit 4 ADR addendum + CAL closure)

[Decision documented + rationale]

No code changes this commit; probe matrix only.
```

### Commit 2 — TE FR yield wrapper (conditional on probe success)

```
feat(connectors): TE fetch_fr_yield_curve_nominal

[Skip if Commit 1 HALT-0]

Append to src/sonar/connectors/te.py yield section (after Sprint H ES wrapper):

async def fetch_fr_yield_curve_nominal(
    self,
    observation_date: date,
) -> dict[str, YieldCurvePoint]:
    """Fetch FR OAT nominal yield curve via TE generic indicator API.

    Source-drift guard: HistoricalDataSymbol validation (GFRN10 10Y reference).
    Returns dict {tenor_label: YieldCurvePoint} for tenors [per Commit 1 probe matrix].

    Empirical probe findings (Commit 1): N tenors daily since YYYY.
    """

Tests:
- Unit: fetch_fr_yield_curve_nominal happy path mocked
- Unit: source-drift guard
- Unit: 404 / empty → DataUnavailableError
- @pytest.mark.slow live canary: FR yield curve 2024-12-31, assert ≥ 6 tenors

Cassettes:
- tests/fixtures/cassettes/te_yield_fr_2024_12_31.json (per tenor shipped)

Coverage te.py FR extension ≥ 90%.
```

### Commit 3 — Pipeline integration FR dispatch (conditional)

```
refactor(pipelines): daily_curves FR dispatch + T1 tuple 8→9 (conditional)

[Skip if Commit 1 HALT-0]

Update src/sonar/pipelines/daily_curves.py:

1. Import fetch_fr_yield_curve_nominal (already in te.py Commit 2)

2. Expand T1_CURVES_COUNTRIES tuple:
   Current: ("US", "DE", "EA", "GB", "JP", "CA", "IT", "ES")
   Post: ("US", "DE", "EA", "GB", "JP", "CA", "IT", "ES", "FR")

3. Dispatcher:
   - FR → te.fetch_fr_yield_curve_nominal

4. NSS fit uniform

Tests:
- Unit: dispatcher routes FR to TE
- Unit: --all-t1 iterates 9 countries
- Unit: T1_CURVES_COUNTRIES assertion (9 entries all T1)

Coverage daily_curves.py ≥ 90%.

Docstring update: "T1 curves coverage 9/16 post-Sprint-I (US/DE/EA/GB/JP/CA/IT/ES/FR)."
```

### Commit 4 — Cassettes + live canary + ADR + CAL + retro

```
docs + test: FR cassettes + live canary + ADR-0009 addendum + CAL + retro

[Split per outcome]

IF SUCCESS:
- Cassettes per tenor shipped Commit 2
- Live canary @pytest.mark.slow:
  - FR NSS fit 2024-12-31, confidence ≥ 0.9, rmse_bps ≤ 10, tenors ≥ 6
- --all-t1 integration canary 9 countries persist

ADR-0009 addendum v2.1:
- Section "EA periphery probe outcomes" — add FR row:
  - FR-BDF: HALT-0 national CB (Sprint D) → SUCCESS via TE cascade (Sprint I)
- Pattern library v2 confirmed: TE Path 1 canonical for all country-data probes
- Sprint D FR national CB unblock criteria preserved (national CB scaffold banque_de_france.py remains documented path for future direct connector)

CAL-CURVES-FR-TE-PROBE CLOSED:
- Status: done (shipped via TE cascade, commit [SHA])

CAL-CURVES-FR-BDF SHARPENED:
- National CB direct connector still BLOCKED per Sprint D
- TE cascade now ships FR curves (ADR-0009 v2 canonical Path 1)
- National CB unblock criteria documented + preserved for future reactivation

Retrospective: docs/planning/retrospectives/week10-sprint-curves-fr-te-probe-report.md
- FR probe per-tenor outcomes
- NSS fit quality (RMSE bps, tenor count)
- Pattern replication (7th TE cascade use: GB/JP/CA/IT/ES/FR)
- ADR-0009 v2 empirical validation (FR confirms canonical Path 1 discipline)
- Production impact: tomorrow 07:30 WEST overlays cascade gains FR functional

IF HALT-0:
- No cassettes (probe empty)
- No live canary

ADR-0009 addendum v2.1:
- FR-BDF: confirmed HALT-0 both paths (national CB Sprint D + TE per-tenor Sprint I)
- FR added to ternary sub-caso B (alongside IT Sprint G): all paths dead
- Pattern library v2 validated: probe discipline prevented Sprint I over-commitment

CAL-CURVES-FR-TE-PROBE CLOSED:
- Status: done (negative outcome documented; national CB + TE both BLOCKED)
- FR remains on EA-aggregate proxy
- Unblock path: (1) Bundesbank-style alternative REST API emergence OR (2) Bloomberg/Refinitiv commercial feed OR (3) MEF-AFT direct data integration

CAL-CURVES-FR-BDF SHARPENED (Sprint I addendum).

Retrospective: HALT-0 + pattern library validation + decision rationale.
```

---

## 5. HALT triggers (atomic)

0. **FR probe per-tenor reveals < 6 daily tenors OR systematic errors** — HALT-0, scope Commits 2-3 skipped. Ship Commit 4 HALT-0 variant.
1. **HistoricalDataSymbol unexpected** — document + investigate. HALT if systematic.
2. **NSS fit convergence failure (if probe success)** — emit flag + investigate. CAL item opens.
3. **RMSE > 20 bps (if probe success)** — investigate data quality. HALT if systematic.
4. **Cassette count < 2 (if probe success)** — HALT.
5. **Live canary wall-clock > 15s** — optimize.
6. **Pre-push gate fails** — fix before push.
7. **No `--no-verify`**.
8. **Coverage regression > 3pp** — HALT.
9. **Push before stopping** — script mandates.
10. **Sprint J file conflict** — te.py append-only respected; CAL file union-merge trivial.
11. **ADR-0010 violation** — FR is T1; brief header enforces.

---

## 6. Acceptance

### Global sprint-end (per outcome)

**Success path**:
- [ ] fetch_fr_yield_curve_nominal shipped + tested (≥ 90% coverage)
- [ ] Pipeline dispatcher routes FR correctly to TE
- [ ] T1_CURVES_COUNTRIES tuple expanded 8 → 9 countries
- [ ] NSS fit RMSE ≤ 10 bps
- [ ] Cassettes ≥ 2
- [ ] Live canary @pytest.mark.slow PASS
- [ ] CAL-CURVES-FR-TE-PROBE CLOSED with commit refs
- [ ] CAL-CURVES-FR-BDF SHARPENED (national CB still BLOCKED)
- [ ] ADR-0009 addendum v2.1 shipped
- [ ] Coverage te.py extensions ≥ 90%, daily_curves.py ≥ 90%

**HALT-0 path**:
- [ ] Probe matrix documented Commit 1 body
- [ ] ADR-0009 addendum v2.1 shipped (FR sub-caso B confirmation)
- [ ] CAL-CURVES-FR-TE-PROBE CLOSED (negative outcome)
- [ ] CAL-CURVES-FR-BDF SHARPENED
- [ ] No pipeline changes

**Global (both paths)**:
- [ ] No `--no-verify`
- [ ] Pre-push gate green every push
- [ ] §10 Pre-merge checklist executed
- [ ] Merge via `sprint_merge.sh`
- [ ] Retrospective shipped per v3 format
- [ ] ADR-0010 tier scope compliance verified

---

## 7. Report-back artifact

File: `docs/planning/retrospectives/week10-sprint-curves-fr-te-probe-report.md`

**Final tmux echo (success)**:
```
SPRINT I FR TE CASCADE DONE: N commits on branch sprint-curves-fr-te-probe

T1 curves coverage: 8 → 9 countries (...FR added)

TE cascade FR:
- HistoricalDataSymbol: GFRN10 (10Y reference)
- Tenors: N daily
- NSS RMSE: [X] bps
- Confidence: [X]

CAL-CURVES-FR-TE-PROBE CLOSED.
CAL-CURVES-FR-BDF SHARPENED (national CB still BLOCKED; TE cascade canonical).

ADR-0009 v2.1 addendum: FR success confirms TE Path 1 canonical.

Remaining T1 curves gap:
- PT + NL (EA periphery pending)
- AU/NZ/CH/SE/NO/DK (T1 sparse pending)

Paralelo with Sprint J: zero file conflicts.

Merge: ./scripts/ops/sprint_merge.sh sprint-curves-fr-te-probe

Artifact: docs/planning/retrospectives/week10-sprint-curves-fr-te-probe-report.md
```

**Final tmux echo (HALT-0)**:
```
SPRINT I FR HALT-0: N commits on branch sprint-curves-fr-te-probe

Per-tenor probe outcome: FR confirmed HALT-0 sub-caso B (all paths dead).
- National CB: blocked per Sprint D (legacy SDMX decommissioned)
- TE per-tenor: [N] daily tenors insufficient for NSS fit

CAL-CURVES-FR-TE-PROBE CLOSED (negative outcome).
CAL-CURVES-FR-BDF SHARPENED (remains BLOCKED both paths).

ADR-0009 v2.1 addendum: FR added to sub-caso B (alongside IT Sprint G).

FR curves remain on EA-aggregate proxy fallback.

Merge: ./scripts/ops/sprint_merge.sh sprint-curves-fr-te-probe
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

### Pattern replication (7th TE cascade use if success)
GB/JP/CA (CAL-138) + IT/ES (Sprint H) + FR (Sprint I) = 6 T1 countries via TE cascade if success. Mature pattern — trivial ship.

### Sprint D FR scaffold retention
banque_de_france.py remains as documentation + future direct-CB placeholder. Not deleted. Reference from ADR-0009 addendum.

### ADR-0009 v2 empirical validation
Sprint I per probe outcome:
- If success: validates TE Path 1 canonical (reinforces v2 amendment)
- If HALT-0: validates sub-caso B exists for FR like IT (pattern robust)
Either outcome strengthens ADR-0009 v2.

### Sprint G precedent — TE probe discipline
Sprint G brief §2 omitted TE — led to suboptimal HALT-0 conclusion corrected Sprint H. Sprint I brief §2 explicitly includes TE per-tenor probe Commit 1 mandatory.

### Paralelo discipline with Sprint J
Sprint J is M4 FCI indices — completely separate domain from curves. Zero primary overlap. Shared secondary (CAL file) union-merge trivial.

### Script merge dogfooded
12th production use Week 10.

### Post-sprint state
- If success: T1 curves 9/16, remaining 7 countries pending (PT + NL + AU/NZ/CH/SE/NO/DK)
- If HALT-0: T1 curves 8/16 unchanged, FR confirmed HALT-0 both paths

### Tier scope T1 only
FR is T1 per country_tiers.yaml. ADR-0010 compliance absolute.

---

*End of Sprint I brief. 4-5 commits. FR yield via TE cascade OR HALT-0 per ADR-0009 v2. Paralelo with Sprint J.*
