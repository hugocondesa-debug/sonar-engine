# Week 10 Day 1+ Sprint B — Per-country ERP Live Paths (T1 Expansion)

**Target**: Replace `MATURE_ERP_PROXY_US` flag with per-market ERPInput assemblers for T1 countries. Enable cross-country cost-of-capital composites with genuine per-country ERP signal. Phase 2 exit criterion.
**Priority**: HIGH (Phase 2 exit criterion; unblocks cross-country valuation workflows for Consumer A)
**Budget**: 5-7h CC
**Commits**: ~7-9
**Base**: branch `sprint-erp-t1-per-country` (isolated worktree `/home/macro/projects/sonar-wt-erp-t1`)
**Concurrency**: PARALELO with Sprint A (EA periphery curves). Minimal file overlap.

**Brief format**: v3

---

## 1. Scope

In (3 tracks):

### Track 1 — ERP input assemblers per T1 country (~3-4h)
Replace US-only `MATURE_ERP_PROXY_US` flag with genuine per-country ERP signal via per-market input assemblers.

**Priority T1 markets** (Phase 2 scope, 5 countries):
- **DE**: DAX equity + DE sovereign 10Y yield + DE inflation → ERP via DCF/Gordon/EY/CAPE median (mirror US pattern)
- **GB**: FTSE equity + GB Gilts 10Y + GB inflation → ERP
- **JP**: TOPIX equity + JGB 10Y + JP inflation → ERP
- **FR**: CAC equity + OAT 10Y + FR inflation → ERP
- **EA aggregate**: EuroStoxx equity + Bund 10Y + EA HICP → ERP (cross-EA composite)

**Deferred per-country** (Phase 2.5+ scope):
- IT/ES/NL/PT (smaller equity markets, proxy suffices initially)
- CA/AU/NZ/CH/SE/NO/DK (non-EA T1, Phase 2.5 scope per priority)

### Track 2 — Pipeline integration (~1-2h)
- `src/sonar/pipelines/daily_cost_of_capital.py` MODIFY — country-aware ERP assembler dispatch
- Remove `MATURE_ERP_PROXY_US` flag emission for countries with live ERP (keep for non-scoped T1)
- Cassette + live canary per new country (5 × 1 canary = 5 new canaries)

### Track 3 — Connector + data source additions (~1-2h)
Connectors required for per-country ERP inputs:
- **DE equity**: DAX via TE (TE equity indices broad coverage)
- **GB equity**: FTSE 100 via TE
- **JP equity**: TOPIX via TE
- **FR equity**: CAC 40 via TE
- **EuroStoxx**: STOXX 50 via TE OR ECB SDW
- **Inflation per country**: TE HICP per country (or ECB SDW for EA members)
- Dividend yield + earnings per country: harder — may need Damodaran Oct 2025 per-country tables as static input OR FMP per-market

**Data source decisions per country** — probe Commit 1.

Out:
- Smaller EA markets (IT/ES/NL/PT) — defer to Phase 2.5
- Non-EA T1 (CA/AU/NZ/CH/SE/NO/DK) — defer to Phase 2.5+
- Buyback yield per country — US has SPDJI; others don't; defer
- CAPE per country Shiller-style — depends on 10y earnings history per country
- Historical per-country ERP backtest — Phase 4 calibration

---

## 2. Spec reference

Authoritative:
- `docs/specs/overlays/erp-daily.md` — ERP methodology (US-centric language, applies uniform cross-country)
- `docs/backlog/calibration-tasks.md` — CAL-ERP-T1-PER-COUNTRY entry
- `src/sonar/overlays/erp/` — existing US ERP implementation
- `docs/milestones/m1-us.md` — M1 US ERP canonical 322 bps reference (2024-01-02)
- `docs/planning/retrospectives/` — Week 9 country sprints for TE connector patterns

**Pre-flight requirement**: Commit 1 CC:
1. Read existing ERP overlay implementation in `src/sonar/overlays/erp/`
2. Probe TE for per-country equity indices:
   ```bash
   set -a && source .env && set +a
   for country in germany united-kingdom japan france euro-area; do
       echo "=== $country stock market ==="
       curl -s "https://api.tradingeconomics.com/historical/country/$country/indicator/stock market?c=$TE_API_KEY&format=json&d1=2024-12-01&d2=2024-12-05" | jq '.[0:2]'
   done
   ```
3. Identify required inputs per ERP method:
   - **DCF method**: price + dividend + buyback + earnings growth → implied ERP solve
   - **Gordon method**: price + dividend + expected growth + risk-free → ERP
   - **EY method**: earnings yield − risk-free = EY-based ERP
   - **CAPE method**: Shiller PE inverted − risk-free = CAPE-based ERP
4. Per-country input availability matrix:
   - DE: price ✓ / dividend ? / buyback ✗ / earnings ✓ / 10y hist ✓
   - GB: similar
   - JP: price + dividend solid; buyback limited
   - FR: similar
   - EA: via EuroStoxx + ECB sources
5. Determine which methods viable per country:
   - US: all 4 (full-blown implementation, canonical)
   - DE/GB/JP/FR: likely 2-3 methods (drop buyback; may simplify)
   - EA: 2-3 methods
6. Document Commit 1 body — narrow scope if major input gaps.

Existing assets:
- ERP overlay code reusable uniform (methodology country-agnostic)
- TE connector canonical for country data
- Damodaran reference values (Oct 2025 per-country) for cross-validation

---

## 3. Concurrency — PARALELO with Sprint A

**Sprint B worktree**: `/home/macro/projects/sonar-wt-erp-t1`
**Sprint B branch**: `sprint-erp-t1-per-country`

**Sprint A (for awareness)**: EA periphery curves, worktree `/home/macro/projects/sonar-wt-ea-periphery`

**File scope Sprint B**:
- `src/sonar/overlays/erp/` EXTEND (primary; new per-country input assemblers)
- `src/sonar/pipelines/daily_cost_of_capital.py` MODIFY (country-aware dispatch)
- `src/sonar/connectors/te.py` APPEND (equity index wrappers per country — if needed)
- `tests/unit/test_overlays/test_erp/` EXTEND (per country tests)
- `tests/integration/test_daily_cost_of_capital.py` EXTEND (live canaries per country)
- `tests/fixtures/cassettes/erp_*` NEW (per country)
- `docs/backlog/calibration-tasks.md` MODIFY (close CAL-ERP-T1-PER-COUNTRY; open sub-CALs if limited)
- `docs/planning/retrospectives/week10-sprint-erp-t1-report.md` NEW

**Sprint A file scope** (for awareness, DO NOT TOUCH):
- `src/sonar/connectors/ecb_sdw.py` (primary)
- `src/sonar/pipelines/daily_curves.py` (primary)

**Zero primary-file overlap**.

**Shared secondary**: `docs/backlog/calibration-tasks.md` — both sprints touch; union-merge trivial.

**Rebase expected minor**: alphabetical merge priority → Sprint A ships first; Sprint B rebases if shared CAL file conflicts.

**Pre-merge checklist** (brief v3 §10):
- [ ] All commits pushed
- [ ] Workspace clean
- [ ] Pre-push gate green
- [ ] Branch tracking set
- [ ] Cassettes + canaries green
- [ ] Cross-validation vs Damodaran reference documented in retro

**Merge execution** (brief v3 §11):
```bash
./scripts/ops/sprint_merge.sh sprint-erp-t1-per-country
```

---

## 4. Commits

### Commit 1 — Pre-flight + DE ERP input assembler

```
feat(overlays): DE ERP input assembler + TE equity wrapper

Pre-flight findings (Commit 1 body):
- TE DAX equity index availability: [HistoricalDataSymbol + historical range]
- DE earnings data availability: [source + coverage]
- DE dividend yield: [source]
- DE 10y historical for CAPE: [viable yes/no]

Extend src/sonar/connectors/te.py:
- fetch_de_equity_index (DAX) with HistoricalDataSymbol source-drift guard
- fetch_de_earnings_per_share (if available) OR document proxy

Create src/sonar/overlays/erp/de_inputs.py:
- build_erp_inputs_de(observation_date) → ERPInput dataclass
- Methods available: [DCF / Gordon / EY / CAPE — per probe results]

Tests:
- Unit: DE TE equity fetch happy path + source-drift guard
- Unit: DE ERP input assembler happy path
- @pytest.mark.slow live canary DE ERP 2024-12-31 computed; cross-validate vs Damodaran DE Oct 2025

Cassettes.

Coverage DE additions ≥ 90%.
```

### Commit 2 — GB + JP ERP input assemblers

```
feat(overlays): GB + JP ERP input assemblers

Extend te.py:
- fetch_gb_equity_index (FTSE 100)
- fetch_jp_equity_index (TOPIX)
- Source-drift guards per country

Create:
- src/sonar/overlays/erp/gb_inputs.py
- src/sonar/overlays/erp/jp_inputs.py

Per country:
- Replicate DE pattern
- Methods viable per empirical input availability
- Cross-validate vs Damodaran reference values

Tests per country — unit + @pytest.mark.slow canaries.

Cassettes per country.
```

### Commit 3 — FR + EA aggregate ERP input assemblers

```
feat(overlays): FR + EA aggregate ERP input assemblers

Extend te.py:
- fetch_fr_equity_index (CAC 40)
- fetch_eurostoxx_50 (STOXX 50 EA aggregate)

Create:
- src/sonar/overlays/erp/fr_inputs.py
- src/sonar/overlays/erp/ea_inputs.py

EA aggregate special case:
- Uses STOXX 50 + Bund 10Y + EA HICP (ECB SDW)
- May require ECB SDW extension OR use TE EA aggregate data

Tests per country — unit + @pytest.mark.slow canaries.

Cassettes per country.
```

### Commit 4 — Pipeline integration daily_cost_of_capital

```
feat(pipelines): daily_cost_of_capital country-aware ERP dispatch

Update src/sonar/pipelines/daily_cost_of_capital.py:
- Country dispatcher for ERP:
  - US: existing (canonical)
  - DE: build_erp_inputs_de
  - GB: build_erp_inputs_gb
  - JP: build_erp_inputs_jp
  - FR: build_erp_inputs_fr
  - EA: build_erp_inputs_ea
  - Others T1 (IT/ES/NL/PT/CA/AU/NZ/CH/SE/NO/DK): continue MATURE_ERP_PROXY_US flag

Update flags:
- MATURE_ERP_PROXY_US removed for 5 countries with live ERP
- New flag per country: {COUNTRY}_ERP_LIVE_COMPUTED

Tests:
- Unit: dispatcher routes correctly per country
- Unit: MATURE_ERP_PROXY_US still emitted for non-scoped countries
- Integration @slow: daily_cost_of_capital for DE/GB/JP/FR/EA; assert per-country ERP persisted

Coverage pipeline ≥ 90%.

systemd service sonar-daily-cost-of-capital.service: already uses --all-t1, no change.
```

### Commit 5 — Cassettes + live canaries full suite

```
test: ERP cassettes + live canaries 5 T1 countries

Cassettes:
- TE equity indices: DAX, FTSE, TOPIX, CAC, EuroStoxx (5 cassettes)
- ERP inputs per country (5 cassettes)
- Cross-validation snapshots vs Damodaran Oct 2025

Live canaries (@pytest.mark.slow):
- tests/integration/test_daily_cost_of_capital.py EXTEND
- 5 new canaries (ERP per country)
- Combined wall-clock ≤ 40s

Assert ERP values within Damodaran reference band (±20% tolerance T1 markets).

Coverage maintained.
```

### Commit 6 — Documentation + ADR

```
docs(overlays): per-country ERP methodology + ADR

Update src/sonar/overlays/erp/README.md OR create:
- Per-country methodology section
- Data source per country table
- Method availability matrix per country
- Cross-validation policy (Damodaran reference ±20% T1 tolerance)

Create docs/adr/ADR-00XX-per-country-erp.md:
- Context: MATURE_ERP_PROXY_US flag limitation
- Decision: per-country live ERP for 5 T1 markets; others proxy
- Rationale: Phase 2 exit criterion; Consumer A valuation workflows need per-country signal
- Consequences: smaller EA markets + non-EA T1 remain proxy until Phase 2.5
- Status: Active

Alternatives rejected:
- Damodaran direct consumption (violates "compute, don't consume" principle)
- Historical average per country (ignores current market state)
```

### Commit 7 — CAL closures + retrospective

```
docs(planning+backlog): Sprint B ERP T1 retrospective + CAL closures

CAL-ERP-T1-PER-COUNTRY CLOSED (partial resolution):
- 5 T1 markets live: DE, GB, JP, FR, EA
- Deferred T1: IT, ES, NL, PT, CA, AU, NZ, CH, SE, NO, DK (smaller markets + non-EA)

New CAL items:
- CAL-ERP-T1-SMALLER-MARKETS (IT/ES/NL/PT) — Phase 2.5
- CAL-ERP-T1-NON-EA (CA/AU/NZ/CH/SE/NO/DK) — Phase 2.5+
- CAL-ERP-CAPE-CROSS-COUNTRY — per-country CAPE depends on 10y earnings history availability
- CAL-ERP-BUYBACK-CROSS-COUNTRY — buyback yield US-only; non-US markets have sparse coverage

Retrospective per v3 format:
docs/planning/retrospectives/week10-sprint-erp-t1-report.md

Content:
- ERP computed per country (DE/GB/JP/FR/EA values + Damodaran cross-val)
- Methods available matrix per country (DCF/Gordon/EY/CAPE)
- Data source matrix (TE + Damodaran + ECB SDW + FRED)
- Flag changes (MATURE_ERP_PROXY_US removal per country)
- Production impact: daily_cost_of_capital cross-country composites gain 5 T1 markets
- §10 pre-merge checklist + §11 merge via script
- Paralelo with Sprint A: zero conflicts
```

---

## 5. HALT triggers (atomic)

0. **TE equity index empirical probe insufficient** — if any country has < 5 years data OR HistoricalDataSymbol drift, narrow scope (drop country from Sprint B, open CAL item).
1. **Dividend / earnings data unavailable per country** — methods drop (EY may fail if no earnings; Gordon may fail if no dividend). Document per-country method availability; not a HALT unless all methods fail.
2. **Damodaran cross-val outside ±30% band** — likely data source quality issue; HALT and investigate.
3. **Currency handling** — per-country ERP computed in local currency. Conversion to USD deferred (L6 integration scope). Document.
4. **Buyback yield universally US-only** — expected; document limitation; DCF method adjusted to drop buyback for non-US.
5. **CAPE requires 10y earnings history** — if country lacks, drop CAPE method; retain DCF/Gordon/EY.
6. **ECB SDW for EA aggregate** — may require extension; scope narrow to TE EuroStoxx if ECB SDW connector insufficient.
7. **Pipeline regression US ERP** — CANARY: verify US ERP 2024-01-02 canonical 322 bps still computed post-refactor. HALT if regression.
8. **Cassette count < 10** — HALT.
9. **Live canary wall-clock > 50s combined** — optimize OR split.
10. **Pre-push gate fails** — fix before push.
11. **No `--no-verify`**.
12. **Coverage regression > 3pp** — HALT.
13. **Push before stopping** — script mandates.
14. **Sprint A file conflict** — CAL file union-merge trivial.

---

## 6. Acceptance

### Global sprint-end
- [ ] ERP input assemblers live for DE, GB, JP, FR, EA (5 countries)
- [ ] Each country: ≥ 2 methods viable (DCF + Gordon minimum; EY + CAPE where data supports)
- [ ] Damodaran cross-validation within ±20% for 5 countries
- [ ] `daily_cost_of_capital.py` country-aware dispatcher operational
- [ ] `MATURE_ERP_PROXY_US` flag removed for 5 scoped countries
- [ ] New flags per country: `{CODE}_ERP_LIVE_COMPUTED`
- [ ] US ERP canonical 322 bps preserved (no regression)
- [ ] Cassettes ≥ 10 shipped
- [ ] Live canaries ≥ 5 @pytest.mark.slow PASS
- [ ] CAL-ERP-T1-PER-COUNTRY CLOSED (partial); new CAL-ERP-* items for deferred T1
- [ ] Coverage overlays/erp/ per-country modules ≥ 90%
- [ ] daily_cost_of_capital.py ≥ 90%
- [ ] No `--no-verify`
- [ ] Pre-push gate green every push
- [ ] §10 Pre-merge checklist executed
- [ ] Merge via `sprint_merge.sh`
- [ ] ADR shipped per-country ERP methodology
- [ ] Retrospective shipped per v3 format

---

## 7. Report-back artifact

File: `docs/planning/retrospectives/week10-sprint-erp-t1-report.md`

**Final tmux echo**:
```
SPRINT B ERP T1 DONE: N commits on branch sprint-erp-t1-per-country

ERP live for 5 T1 markets: DE, GB, JP, FR, EA
Damodaran cross-val: [per-country bps + deviation %]

Methods available matrix:
- DE: [DCF / Gordon / EY / CAPE]
- GB: [DCF / Gordon / EY / CAPE]
- JP: [DCF / Gordon / EY / CAPE]
- FR: [DCF / Gordon / EY / CAPE]
- EA: [DCF / Gordon / EY / CAPE]

US canonical 322 bps: PRESERVED ✓

Deferred: IT/ES/NL/PT (CAL-ERP-T1-SMALLER-MARKETS), CA/AU/NZ/CH/SE/NO/DK (CAL-ERP-T1-NON-EA).

Production impact: daily_cost_of_capital cross-country composites gain 5 T1 markets.

Paralelo with Sprint A: zero file conflicts.

Merge: ./scripts/ops/sprint_merge.sh sprint-erp-t1-per-country

Artifact: docs/planning/retrospectives/week10-sprint-erp-t1-report.md
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

### ERP methodology uniform cross-country
NSS-style: compute-not-consume principle applies. Each country builds ERPInput with available methods; median of available methods = canonical.

### Damodaran cross-validation philosophy
Damodaran publishes monthly per-country ERP (Oct 2025 reference). SONAR values should align ±20% (reasonable band for methodology differences). Systematic deviation > 20% → investigate data source quality.

### Phase 2 priority scoping
5 markets cover ~75% of global T1 equity market cap. Remaining 11 T1 proxy via US until Phase 2.5 or consumer demand justifies.

### Paralelo discipline
Sprint B in `overlays/erp/` + `daily_cost_of_capital.py`. Sprint A in `ecb_sdw.py` + `daily_curves.py`. Zero primary overlap.

### Script merge
Dogfooded Day 1+2 Week 10. If HALT, surface + do not intervene manually.

### Consumer A implications
Post-sprint, Consumer A (MCP/API private) can query:
- `sonar.cost_of_capital(country="DE", date=today)` → live composite
- `sonar.cost_of_capital(country="GB", date=today)` → live composite
- etc.

Pre-sprint: same query returned US-proxy. Post-sprint: genuine per-market signal.

---

*End of Sprint B brief. 7-9 commits. Per-country ERP for 5 T1 markets. Paralelo-ready with Sprint A.*
