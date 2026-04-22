# Week 10 Day 2 Sprint J — CAL-M4-T1-FCI-EXPANSION

**Tier scope**: T1 ONLY (16 countries). T2 expansion deferred to Phase 5 per ADR-0010.

**Target**: Ship M4 Financial Conditions Index per T1 country. M4 currently 0/16 (US scaffold only per M4 spec). Components: equity volatility + credit spread + NEER. Uses ADR-0009 v2 discipline (TE Path 1 canonical) + Sprint F per-country builder pattern.
**Priority**: HIGH (M4 opens 4th monetary dimension; completes M1+M2+M3+M4 T1 uniformity foundation for MSC composite multi-country; 0/16 → 16/16 significant progression)
**Budget**: 4-6h CC
**Commits**: ~6-8
**Base**: branch `sprint-m4-fci-t1-expansion` (isolated worktree `/home/macro/projects/sonar-wt-m4-fci-t1`)
**Concurrency**: PARALELO with Sprint I (FR-TE-PROBE curves). Zero primary file overlap.

**Brief format**: v3

---

## 1. Scope

In (3 tracks):

### Track 1 — M4 FCI spec review + component data sources (~1h)
Per M4 spec (`docs/specs/indices/monetary/M4-fci.md`), composite financial conditions index requires 3 components per country:

1. **Equity volatility** — country-specific VIX analog (implied vol ~30d)
2. **Credit spread** — IG corporate OAS vs sovereign benchmark
3. **NEER** — Nominal Effective Exchange Rate (trade-weighted)

**Component data sources per country per ADR-0009 v2 TE Path 1 discipline**:

**US (canonical reference preserved)**:
- Volatility: VIX (CBOE via FRED)
- Credit spread: ICE BofA US IG Corporate OAS (FRED BAMLC0A0CM)
- NEER: US Broad Trade-Weighted Dollar Index (FRED DTWEXBGS)

**EA aggregate**:
- Volatility: VSTOXX (EuroStoxx 50 vol) — via TE `euro area volatility` OR FRED VIXCLS analog
- Credit spread: ICE BofA Euro IG Corporate OAS (FRED BAMLHE00EHYIOAS or similar)
- NEER: ECB EA NEER (via ECB SDW or TE aggregate)

**16 T1 countries per country components** (pre-flight probe mandatory Commit 1):
- Volatility: TE `[country] volatility` generic OR specific equity vol series per country
- Credit spread: TE `[country] corporate bond spread` OR BIS credit data
- NEER: BIS NEER dataset (daily, broad coverage) OR TE `[country] exchange rate` effective

### Track 2 — Connectors + M4 per-country builders (~2-3h)
**Connector extensions per probe outcome**:
- `src/sonar/connectors/te.py` APPEND (M4 section at end) — per-country vol/spread/NEER wrappers OR
- `src/sonar/connectors/bis.py` EXTEND — NEER dataset per country (BIS has comprehensive NEER coverage)
- FRED-first for US components (already wired)
- Conditional ECB SDW extension for EA aggregate components if TE/BIS sparse

**M4 builders per country** in `src/sonar/indices/monetary/builders.py`:
- Mirror Sprint F/L M2 pattern: `build_m4_{country}_inputs(...)` per country
- 3-component assembly with per-component fallback flags:
  - `{CODE}_M4_VOL_TE_LIVE` / `{CODE}_M4_VOL_FRED_LIVE` / `{CODE}_M4_VOL_UNAVAILABLE`
  - `{CODE}_M4_SPREAD_TE_LIVE` / `{CODE}_M4_SPREAD_BIS_LIVE` / `{CODE}_M4_SPREAD_UNAVAILABLE`
  - `{CODE}_M4_NEER_BIS_LIVE` / `{CODE}_M4_NEER_TE_LIVE` / `{CODE}_M4_NEER_UNAVAILABLE`
  - `{CODE}_M4_FULL_COMPUTE_LIVE` (all 3 components)
  - `{CODE}_M4_PARTIAL_COMPUTE` (1-2 components)
- US M4 canonical preserved (if already shipped US M4 scaffold, regression guard)

**Priority order per country coverage** (depends probe Commit 1):
- Tier A (highest confidence data): US, EA, GB, JP, CA, DE (major reserve currency / FRED + TE coverage)
- Tier B (moderate): FR, IT, ES, AU, NZ (BIS NEER + TE vol likely viable)
- Tier C (depends probe): CH, SE, NO, DK, NL, PT (smaller markets, spread data sparse possible)

### Track 3 — Pipeline + tests + CAL closure + retro (~1-2h)
- `src/sonar/pipelines/daily_monetary_indices.py` MODIFY:
  - Add M4 dispatcher per-country (mirror M1/M2 pattern)
  - M4 supported countries tuple
- Cassettes per country per component (ballpark ~30-40 cassettes if 15 countries × 3 components each cached)
- Live canaries @pytest.mark.slow per country (~16 canaries, combined ≤ 120s)
- CAL-M4-T1-FCI-EXPANSION CLOSED with per-country compute mode status
- New CAL items opened for degraded countries (specific data source gaps)
- Retrospective per v3 format

Out:
- M4 composite scoring (this sprint ships components + builders; composite computation separate sprint post M1+M2+M3+M4 T1 uniform)
- Historical backfill (Phase 2.5 backtest scope)
- T2 country expansion (Phase 5+ per ADR-0010)
- ERP/cost-of-capital integration with M4 (L6 integration scope)

---

## 2. Spec reference

Authoritative:
- `docs/specs/indices/monetary/M4-fci.md` — M4 Financial Conditions Index methodology
- `docs/backlog/calibration-tasks.md` — CAL-M4-T1-FCI-EXPANSION entry
- `docs/planning/retrospectives/week10-sprint-cpi-infl-t1-report.md` — Sprint F per-country M2 pattern template (primary reference)
- `docs/planning/retrospectives/week10-sprint-m2-ea-aggregate-report.md` — Sprint L EA aggregate pattern
- `src/sonar/connectors/te.py` — Sprint F + L CPI/inflation wrappers (mirror for vol/spread/NEER)
- `src/sonar/connectors/bis.py` — BIS v2 connector (extend for NEER if needed)
- `src/sonar/connectors/fred.py` — FRED connector (already wired US components)
- `src/sonar/indices/monetary/builders.py` — Sprint F per-country M2 builders (mirror pattern)
- `src/sonar/pipelines/daily_monetary_indices.py` — M1/M2/M3 dispatch pattern
- `docs/adr/ADR-0010-t1-complete-before-t2-expansion.md` — tier scope lock
- `docs/adr/ADR-0009-national-cb-connectors-ea-periphery.md` v2 — TE Path 1 canonical

**Pre-flight requirement**: Commit 1 CC:
1. Read M4 FCI spec + Sprint F per-country M2 pattern
2. Probe TE per-country components (16 T1 countries × 3 components = 48 probes):
   ```bash
   set -a && source .env && set +a

   # Sample: equity volatility per country
   for country in germany france italy spain netherlands portugal united-kingdom japan canada australia new-zealand switzerland sweden norway denmark; do
       echo "=== $country volatility ==="
       curl -s "https://api.tradingeconomics.com/historical/country/$country/indicator/volatility?c=${TE_API_KEY}&format=json&d1=2024-12-01&d2=2024-12-05" | jq '.[0] | {HistoricalDataSymbol, Frequency, Value}' 2>/dev/null
   done

   # Credit spread per country
   for country in germany france italy spain united-kingdom japan canada australia; do
       echo "=== $country corporate bond spread ==="
       curl -s "https://api.tradingeconomics.com/historical/country/$country/indicator/corporate%20bond%20spread?c=${TE_API_KEY}&format=json&d1=2024-12-01&d2=2024-12-05" | jq '.[0]' 2>/dev/null
   done
   ```
3. Probe BIS NEER dataset availability per country:
   ```bash
   # BIS NEER is comprehensive — verify 16 T1 countries via existing bis.py connector
   grep -A 20 "class BISConnector" src/sonar/connectors/bis.py | head -50
   ```
4. Document per-country per-component probe matrix Commit 1 body
5. Decide per-country compute mode expected:
   - FULL (all 3 components viable): target countries
   - PARTIAL (1-2 components): acceptable with flags
   - SCAFFOLD (0 components): HALT-0 per country, scaffold only

**Pre-flight HALT trigger**: if probes reveal < 8 of 16 countries have ≥ 2 components viable, HALT scope + surface. Expected outcome: ≥ 10 countries full or near-full compute, ~6 PARTIAL/SCAFFOLD.

---

## 3. Concurrency — PARALELO with Sprint I

**Sprint J worktree**: `/home/macro/projects/sonar-wt-m4-fci-t1`
**Sprint J branch**: `sprint-m4-fci-t1-expansion`

**Sprint I (for awareness)**: CAL-CURVES-FR-TE-PROBE, worktree `/home/macro/projects/sonar-wt-curves-fr-te-probe`

**File scope Sprint J**:
- `src/sonar/indices/monetary/builders.py` MODIFY (primary — M4 per-country builders + _assemble_m4_full_compute helper)
- `src/sonar/connectors/te.py` APPEND M4 section at end (primary — vol/spread/NEER wrappers if TE primary per probe)
- `src/sonar/connectors/bis.py` EXTEND (likely — NEER per country if BIS dataset covers)
- `src/sonar/connectors/ecb_sdw.py` EXTEND (possibly — EA aggregate components if TE sparse)
- `src/sonar/pipelines/daily_monetary_indices.py` MODIFY (M4 dispatch)
- `tests/unit/test_connectors/*` EXTEND
- `tests/unit/test_indices/monetary/test_builders.py` EXTEND (M4 per-country tests)
- `tests/integration/test_daily_monetary_*.py` EXTEND (M4 live canaries)
- `tests/fixtures/cassettes/*` NEW (~30-40 cassettes)
- `docs/backlog/calibration-tasks.md` MODIFY (close CAL-M4-T1-FCI-EXPANSION)
- `docs/planning/retrospectives/week10-sprint-m4-fci-t1-report.md` NEW

**Sprint I file scope** (DO NOT TOUCH):
- `src/sonar/pipelines/daily_curves.py` (Sprint I primary)

**Potential overlap zones**:
- `src/sonar/connectors/te.py` — both Sprints APPEND. Sprint I in yield section (end of yield block). Sprint J in M4 section (end of file). Bookmark zones distinct. **Zero conflict** if respected.
- `docs/backlog/calibration-tasks.md` — both modify; different sections (CAL-CURVES-* vs CAL-M4-*); union-merge trivial.

**Zero primary-file conflict expected**.

**Rebase expected minor**: alphabetical merge priority — Sprint I (i < j) ships first. Sprint J rebases te.py + CAL file (union-merge trivial if bookmark zones respected).

**Pre-merge checklist** (brief v3 §10):
- [ ] All commits pushed
- [ ] Workspace clean
- [ ] Pre-push gate green
- [ ] Branch tracking set
- [ ] US M4 canonical preserved (if applicable regression guard)
- [ ] M4 T1 coverage ≥ 10 of 16 FULL or PARTIAL (target)
- [ ] Tier scope verified T1 only (per ADR-0010)

**Merge execution** (brief v3 §11):
```bash
./scripts/ops/sprint_merge.sh sprint-m4-fci-t1-expansion
```

---

## 4. Commits

### Commit 1 — Pre-flight probes per country per component

```
feat(connectors): M4 FCI components pre-flight probe matrix (Sprint J C1)

Pre-flight findings (Commit 1 body):

Per country per component probe matrix (16 T1 × 3 components = 48 probes):

Equity volatility:
- US: VIX FRED VIXCLS ✓ (canonical)
- DE: [HistoricalDataSymbol + Frequency]
- FR: ...
- ... (15 countries)

Credit spread:
- US: ICE BofA IG FRED BAMLC0A0CM ✓ (canonical)
- DE: TE `germany corporate bond spread` [outcome]
- ... (15 countries)

NEER (BIS + TE):
- US: FRED DTWEXBGS ✓ (canonical)
- 16 T1 via BIS NEER [confirm coverage]
- Alternative: TE `[country] effective exchange rate` where BIS sparse

Per-country compute mode decision:
- FULL expected (3/3): [list countries]
- PARTIAL (2/3): [list countries]
- PARTIAL (1/3): [list countries]
- SCAFFOLD (0/3): [list countries — HALT-0 per country]

Summary:
- FULL compute eligible: N countries
- PARTIAL compute: N countries
- SCAFFOLD only: N countries

Proceed Commits 2-7 per outcome matrix.

No code changes this commit; probe matrix only.
```

### Commit 2 — TE connector M4 component wrappers (vol + spread)

```
feat(connectors): TE M4 volatility + credit spread wrappers

Append to src/sonar/connectors/te.py M4 section (new section at end):

# ============================================
# M4 FCI Components (Sprint J)
# ============================================

async def fetch_country_volatility(
    self,
    country: str,  # Full name e.g. "germany", "united-kingdom"
    observation_date: date,
    history_days: int = 60,
) -> list[Observation]:
    """Country-specific equity volatility proxy via TE volatility indicator.

    Source-drift guard: HistoricalDataSymbol validation.
    Typical frequency: daily. History: 20+ years for major markets.
    """

async def fetch_country_credit_spread(
    self,
    country: str,
    observation_date: date,
    history_days: int = 60,
) -> list[Observation]:
    """Country corporate bond spread via TE.

    Spread = corporate yield - sovereign benchmark yield.
    """

Tests:
- Unit: 4+ tests per method (CA + DE + JP + GB happy paths + source-drift)
- @pytest.mark.slow live canaries per viable country (from Commit 1 probe)

Cassettes per country per component.

Coverage te.py M4 extensions ≥ 90%.
```

### Commit 3 — BIS NEER per country wrapper

```
feat(connectors): BIS NEER per country extension

Extend src/sonar/connectors/bis.py:

async def fetch_country_neer(
    self,
    country: str,  # ISO code
    observation_date: date,
    history_days: int = 60,
) -> list[Observation]:
    """NEER (Nominal Effective Exchange Rate) per country via BIS.

    BIS Effective Exchange Rate Index dataset — broad basket (61 economies).
    Typical frequency: monthly (BIS publishes monthly averages).

    For daily FCI compute, use monthly NEER + interpolation OR flag MONTHLY frequency.
    """

Tests:
- Unit: fetch_country_neer mocked (US, DE, GB, JP)
- Unit: unsupported country (T2+ country should raise)
- @pytest.mark.slow live canary: DE NEER 2024-12-31

Cassettes.

Coverage bis.py extension ≥ 90%.
```

### Commit 4 — M4 builders priority Tier A (US + EA + GB + JP + CA + DE)

```
feat(indices): M4 FCI builders Tier A (6 countries + US preservation)

Add to src/sonar/indices/monetary/builders.py:

async def _assemble_m4_full_compute(
    *,
    country: str,
    volatility: float | None,
    credit_spread: float | None,
    neer: float | None,
    vol_source_flag: str,
    spread_source_flag: str,
    neer_source_flag: str,
) -> M4Inputs:
    """Shared helper for M4 per-country compute + flag emission.

    Mirror Sprint F _assemble_m2_full_compute pattern.
    """
    flags = [vol_source_flag, spread_source_flag, neer_source_flag]

    if all([volatility is not None, credit_spread is not None, neer is not None]):
        flags.append(f"{country}_M4_FULL_COMPUTE_LIVE")
    else:
        flags.append(f"{country}_M4_PARTIAL_COMPUTE")

    return M4Inputs(
        volatility=volatility,
        credit_spread=credit_spread,
        neer=neer,
        flags=flags,
    )

async def build_m4_us_inputs(fred, te, observation_date, *, bis=None) -> M4Inputs:
    """US M4 canonical (VIX + ICE BofA + TWD).

    CANONICAL PRESERVATION: if US M4 already shipped, regression guard mandatory.
    """
    # Fetch VIX, IG OAS, TWD from FRED (existing canonical)
    # Assemble via _assemble_m4_full_compute

async def build_m4_de_inputs(...): ...
async def build_m4_ea_inputs(...): ...
async def build_m4_gb_inputs(...): ...
async def build_m4_jp_inputs(...): ...
async def build_m4_ca_inputs(...): ...

Tests:
- Unit: happy path per country (6 tests)
- Unit: partial compute (1-2 missing components per country)
- Unit: all-missing → SCAFFOLD + flag emission
- @pytest.mark.slow live canaries per country (6 canaries)
- **US M4 CANONICAL REGRESSION GUARD**: test_us_m4_canonical_preserved (2 unit + 1 integration)

Coverage builders.py M4 ≥ 90%.
```

### Commit 5 — M4 builders Tier B + Tier C (remaining 10 countries)

```
feat(indices): M4 FCI builders Tier B + C (FR/IT/ES/AU/NZ + CH/SE/NO/DK/NL/PT)

Apply Commit 4 pattern for remaining 10 countries per Commit 1 probe outcomes.

Per-country expected compute mode:
- Tier B (FR/IT/ES/AU/NZ): FULL or PARTIAL (likely 2-3 components)
- Tier C (CH/SE/NO/DK/NL/PT): PARTIAL or SCAFFOLD depending on probe

For SCAFFOLD countries: builder raises InsufficientDataError + emits `{CODE}_M4_SCAFFOLD_ONLY` flag.

Tests + cassettes per country.

Coverage maintained.
```

### Commit 6 — Pipeline integration M4 dispatcher

```
refactor(pipelines): daily_monetary_indices M4 dispatch + smoke integration

Update src/sonar/pipelines/daily_monetary_indices.py:

1. Add M4_SUPPORTED_COUNTRIES tuple (per Commit 1 probe outcomes)
   Expected: all 16 T1, some degraded

2. M4 dispatcher per country routes to respective build_m4_{country}_inputs

3. Update _classify_m2_compute_mode parallel → _classify_m4_compute_mode
   Recognize {COUNTRY}_M4_FULL_COMPUTE_LIVE + _PARTIAL_COMPUTE + _SCAFFOLD_ONLY flags

4. Connector lifecycle: BIS + TE + FRED all already registered

Tests:
- Unit: M4 dispatcher routes per country
- Unit: --all-t1 iterates 16 countries for M4
- Integration smoke @slow:
  - 16 T1 countries M4 compute 2024-12-31
  - Wall-clock ≤ 120s combined
  - ≥ 10 countries FULL or PARTIAL expected

Coverage daily_monetary_indices.py ≥ 90%.
```

### Commit 7 — CAL closure + retrospective + new CAL items

```
docs(backlog+planning): Sprint J M4 FCI T1 retrospective + CAL closure

CAL-M4-T1-FCI-EXPANSION CLOSED:
- Status: done (shipped; N countries FULL compute, M PARTIAL, K SCAFFOLD)
- Per country compute mode matrix documented retrospective

New CAL items per degraded country (if any):
- CAL-M4-{COUNTRY}-COMPONENT-GAP per country with partial compute (e.g. CH volatility sparse)
- CAL-M4-NEER-FREQUENCY-DAILY (if BIS monthly NEER → daily interpolation needed separate sprint)

Retrospective per v3 format:
docs/planning/retrospectives/week10-sprint-m4-fci-t1-report.md

Content:
- Per country per component probe matrix (Commit 1)
- M4 compute mode per country (FULL / PARTIAL / SCAFFOLD)
- US canonical preservation validated (if US M4 already shipped)
- Connector coverage dividends (TE M4 section + BIS NEER extension)
- Flag emissions matrix per country
- Production impact: daily_monetary_indices M4 live for N countries tomorrow 07:30 WEST
- MSC composite multi-country unblocked post-Sprint-J for countries where M1+M2+M3+M4 all FULL
- §10 pre-merge checklist + §11 merge via script
- Paralelo with Sprint I: zero file conflicts
- ADR-0010 compliance verified

M4 T1 coverage post-merge:
- FULL compute: [N] countries
- PARTIAL compute: [M] countries
- SCAFFOLD only: [K] countries
- Total: [N+M] of 16 operational (target ≥ 10)

Remaining M monetary gap for MSC composite:
- M3: 4/16 (curves-dependent; FR/IT/ES shipped Week 10 Day 2; PT/NL/sparse pending)
- M4: [per this sprint outcome]
- M1: ✓ 16/16
- M2: ✓ 11/16 full (post Sprints F + L)
- MSC eligible countries: intersect of all 4 M-indices FULL
```

---

## 5. HALT triggers (atomic)

0. **Commit 1 probe reveals < 8 of 16 countries have ≥ 2 components** — scope narrow, HALT + surface.
1. **US M4 canonical regression** — if US M4 already shipped in prior sprint, Commit 4 regression test fails → HALT absolute.
2. **BIS NEER dataset unsupported T1 country** — emit per-country flag, fallback TE effective exchange rate.
3. **TE per-country volatility sparse (< 5 countries coverage)** — investigate per-country specific equity vol alternatives. HALT if systematic.
4. **Credit spread TE empty majority** — investigate BIS credit dataset alternative OR per-country sovereign-vs-corporate manual calc.
5. **Cassette count < 20** — HALT (minimum ~20 cassettes per 15 countries × 2-3 components).
6. **Live canary wall-clock > 180s combined** — optimize + split.
7. **Pre-push gate fails** — fix before push.
8. **No `--no-verify`**.
9. **Coverage regression > 3pp** — HALT.
10. **Push before stopping** — script mandates.
11. **Sprint I file conflict** — te.py append-only bookmark zones respected; CAL file union-merge trivial.
12. **M4 PARTIAL majority** — if > 8 countries end PARTIAL_COMPUTE (< half FULL), surface + investigate data source gaps. Per-component CAL items open.
13. **ADR-0010 violation** — all work T1 per tier scope lock; brief header enforces.
14. **M4 SCAFFOLD > 6 countries** — investigate SCAFFOLD reason per country; surface per-component alternatives.

---

## 6. Acceptance

### Global sprint-end
- [ ] TE M4 wrappers shipped (volatility + credit spread) per viable countries
- [ ] BIS NEER extension shipped (16 T1 countries supported)
- [ ] M4 builders shipped 16 T1 countries (FULL/PARTIAL/SCAFFOLD per probe outcome)
- [ ] US M4 canonical preserved (regression guard PASS if applicable)
- [ ] M4 T1 coverage: ≥ 10 of 16 FULL or PARTIAL (target)
- [ ] Cassettes ≥ 20 shipped
- [ ] Live canaries ≥ 10 @pytest.mark.slow PASS combined ≤ 180s
- [ ] Pipeline M4 dispatcher shipped + tested
- [ ] _classify_m4_compute_mode shipped (mirror M2 pattern)
- [ ] CAL-M4-T1-FCI-EXPANSION CLOSED with commit refs
- [ ] Coverage te.py M4 + bis.py NEER + builders.py M4 ≥ 90%
- [ ] Coverage daily_monetary_indices.py ≥ 90%
- [ ] No `--no-verify`
- [ ] Pre-push gate green every push
- [ ] §10 Pre-merge checklist executed
- [ ] Merge via `sprint_merge.sh`
- [ ] Retrospective shipped per v3 format
- [ ] ADR-0010 tier scope compliance verified

---

## 7. Report-back artifact

File: `docs/planning/retrospectives/week10-sprint-m4-fci-t1-report.md`

**Final tmux echo**:
```
SPRINT J M4 FCI T1 DONE: N commits on branch sprint-m4-fci-t1-expansion

M4 T1 coverage post-merge per country:
- US: FULL (canonical preserved) ✓
- DE: [FULL / PARTIAL / SCAFFOLD]
- FR: ...
- [16 rows per country]

Total FULL compute: [N] of 16
Total PARTIAL compute: [M] of 16
Total SCAFFOLD only: [K] of 16

US canonical: PRESERVED ✓

CAL-M4-T1-FCI-EXPANSION CLOSED.
New CAL items: [if any — list per-component gaps]

Production impact: daily_monetary_indices M4 live for [N+M] countries tomorrow 07:30 WEST.
MSC composite unblock: countries with FULL M1+M2+M3+M4 operational.

M4 dimension summary:
- Volatility: TE primary (N countries) + FRED US (1)
- Credit spread: TE per-country (N countries)
- NEER: BIS dataset (16 T1 coverage) + FRED US

Paralelo with Sprint I: zero file conflicts.

Merge: ./scripts/ops/sprint_merge.sh sprint-m4-fci-t1-expansion

Artifact: docs/planning/retrospectives/week10-sprint-m4-fci-t1-report.md
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

### Pattern replication (Sprint F/L M2 template)
Per-country M4 builder mirrors Sprint F per-country M2 pattern + Sprint L EA aggregate pattern.
`_assemble_m4_full_compute` helper mirrors `_assemble_m2_full_compute`.

### M4 vs M2 differences
- M2: output_gap + cpi_yoy + inflation_forecast (3 components)
- M4: volatility + credit_spread + neer (3 components)
- Similar structure → code reuse pattern applies

### US canonical preservation (if applicable)
If prior sprint shipped US M4 scaffold, preservation guard mandatory. If M4 ships fresh this sprint, US ships as part of Commit 4 (no regression concern, new path).

Check pre-flight: does `build_m4_us_inputs` OR `M4Inputs` already exist in builders.py? If yes, preservation guard required. If no, fresh M4 implementation.

### BIS NEER frequency handling
BIS publishes monthly NEER. For daily FCI compute:
- Interpolate monthly → daily OR
- Use latest available monthly value with timestamp flag (acceptable for FCI, not high-frequency)
- Document in `{CODE}_M4_NEER_MONTHLY_FREQUENCY` flag

### Component data quality per country
Expected quality dividend:
- US: Tier A all components canonical (FRED)
- DE/EA/GB/JP: Tier A all components likely FULL
- CA/FR/IT/ES/AU/NZ: Tier B, likely FULL or near-FULL
- CH/SE/NO/DK/NL/PT: Tier C, likely PARTIAL (smaller corporate bond markets → spread sparse)

### Paralelo discipline with Sprint I
Sprint I in daily_curves.py + te.py yield section. Sprint J in daily_monetary_indices.py + te.py M4 section + bis.py + builders.py.

Zero primary overlap. te.py append zones distinct (yield vs M4).

### Script merge dogfooded
13th production use Week 10.

### MSC composite dividend
Post-Sprint-J, M4 dimension opens. Combined with M1 (Week 9 ✓) + M2 (Sprint F + L ✓ 11/16) + M3 (partial 4/16):
- MSC eligible = intersect(M1, M2, M3, M4) FULL per country
- US likely first MSC cross-country candidate
- DE + EA second tier if M3 extends

### Tier scope T1 only
All 16 T1 countries. ADR-0010 compliance absolute.

### Post-sprint state M4 dimension
- 0/16 → target 10+/16 operational (FULL or PARTIAL)
- Completes 4th monetary dimension foundation
- Unlocks MSC composite design Week 11+

---

*End of Sprint J brief. 6-8 commits. M4 FCI T1 expansion 16 countries. 0/16 → ≥10/16 operational. Paralelo with Sprint I.*
