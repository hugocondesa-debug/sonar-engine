# Week 6 Sprint 2b — Monetary Ingestion Omnibus (CAL-096/097/098/100)

**Target**: Close CAL-096 (FRED monetary ext) + CAL-097 (CBO output gap) + CAL-098 (ECB SDW M1-EA builder) + CAL-100 (monetary builders + integration smoke). Unlocks M1/M2/M4 US + M1 EA real-data production rows.

**Priority**: HIGH (breaks the "compute shipped, connectors deferred" pattern — actual production readiness for M-indices)

**Budget**: 4-5h CC autonomous
**Commits**: ~8-11
**Base**: main HEAD post Sprint 1 + 1b (`3f5417f` or later)
**Concurrency**: Parallel to Week 6 Sprint 2 MSC composite in tmux `sonar`. See §3.

---

## 1. Scope

In:
- **CAL-096**: Extend `src/sonar/connectors/fred.py` with new `# === Monetary indicators ===` section:
  - `fetch_fed_funds_target_upper_us()` — DFEDTARU
  - `fetch_fed_funds_target_lower_us()` — DFEDTARL
  - `fetch_fed_funds_effective_us()` — FEDFUNDS
  - `fetch_fed_balance_sheet_us()` — WALCL (weekly, level)
  - `fetch_pce_core_yoy_us()` — PCEPILFE (US core inflation; for M2)
  - `fetch_usd_neer_us()` — DTWEXBGS (trade-weighted dollar; for M4)
  - `fetch_mortgage_30y_us()` — MORTGAGE30US (for M4)
  - Verify existing helpers for NFCI/ANFCI/HY OAS/IG OAS/VIX — reuse if present
- **CAL-097**: `src/sonar/connectors/cbo.py` new — CBO output gap for M2 Taylor rule
  - Primary path: FRED `GDPPOT` (CBO potential GDP on FRED) → compute gap = actual/potential - 1
  - Fallback: CBO Excel scrape if GDPPOT absent
- **CAL-098**: Use existing `src/sonar/connectors/ecb_sdw.py` for M1 EA inputs:
  - DFR policy rate — dataflow empirical probe
  - ILM balance sheet — dataflow empirical probe
  - Document exact dataflow keys discovered
- **CAL-100**: `src/sonar/indices/monetary/builders.py` new:
  - `MonetaryInputsBuilder` class analogous to economic/builders.py
  - `build_m1_inputs(country, date, ...)` routing US → FRED, EA → ECB SDW
  - `build_m2_inputs(country, date, ...)` US only (output_gap via CBO)
  - `build_m4_inputs(country, date, ...)` US primary (NFCI direct)
- Integration tests: `tests/integration/test_monetary_indices_live.py` with 4 `@pytest.mark.slow` canaries (M1 US, M2 US, M4 US, M1 EA)
- Retrospective + close CAL-096/097/098/100

Out:
- MSC composite (Sprint 2 parallel track)
- Krippner shadow rate connector (CAL-099, Phase 2+, irrelevant above ZLB currently)
- Full HLW r* connector (Phase 2+, YAML workaround stays)
- M2 EA output_gap (requires OECD EO / AMECO / Eurostat — defer Week 7)
- M4 EA custom-FCI 7-component (requires VSTOXX + ECB MIR mortgage + EUR NEER wiring — defer Week 7)
- UK/JP coverage (BoE/BoJ connectors — Week 7)
- Daily pipeline `daily_monetary_indices.py` (separate brief — scaffolding only this sprint if time)

---

## 2. Spec reference

Authoritative:
- `docs/backlog/calibration-tasks.md` — CAL-096, CAL-097, CAL-098, CAL-100 entries
- `docs/specs/indices/monetary/M1-effective-rates.md` §2 (input sources)
- `docs/specs/indices/monetary/M2-taylor-gaps.md` §2
- `docs/specs/indices/monetary/M4-fci.md` §2
- `docs/specs/indices/monetary/README.md`
- Previous ingestion pattern: `src/sonar/pipelines/daily_bis_ingestion.py` + `src/sonar/pipelines/daily_credit_indices.py` (DbBackedInputsBuilder pattern)
- SESSION_CONTEXT §Decision authority + §Brief format

Existing assets:
- `src/sonar/connectors/fred.py` — already has economic section (Sprint 2a); add monetary section
- `src/sonar/connectors/ecb_sdw.py` — exists (verify API patterns in Commit 1)
- `src/sonar/indices/monetary/{m1_effective_rates,m2_taylor_gaps,m4_fci}.py` — shipped Sprint 1b
- `src/sonar/indices/monetary/_config.py` — r_star + bc_targets loaders shipped Sprint 1b

---

## 3. Concurrency — parallel protocol with MSC composite

MSC composite runs concurrently in tmux `sonar`. Both push to main.

**Hard-locked resource allocation**:
- Migration numbers: **this brief creates no migration**. MSC uses 015.
- `src/sonar/db/models.py`: **NO CHANGES** (no new ORMs). MSC adds MonetaryCycleScore inside Cycle bookmark.
- `src/sonar/connectors/`: this brief modifies `fred.py` + `cbo.py` (new) + `ecb_sdw.py` (reads/probes). MSC doesn't touch connectors.
- `src/sonar/indices/monetary/`: this brief creates `builders.py` (new). MSC doesn't touch indices/monetary/.
- `src/sonar/cycles/`: **DO NOT TOUCH** — MSC owns.
- Tests: separate directories
- `pyproject.toml`: no new deps

**Push race**:
- Normal rebase on rejection
- Zero file collisions expected

**Start order**: MSC arranca primeiro (smaller). This brief ~1 min depois.

---

## 4. Commits

### Commit 1 — FRED monetary section extension (CAL-096)

```
feat(connectors): FRED monetary-series helpers (CAL-096)

Extend src/sonar/connectors/fred.py with new section:

# === Monetary indicators (M1/M2/M4) ===

Thin wrappers over existing fetch_series pattern:

M1 Effective Rates inputs:
- fetch_fed_funds_target_upper_us(start, end) — DFEDTARU
- fetch_fed_funds_target_lower_us(start, end) — DFEDTARL
- fetch_fed_funds_effective_us(start, end) — FEDFUNDS
- fetch_fed_balance_sheet_us(start, end) — WALCL
  - Weekly series (Wed release typical)

M2 Taylor Gaps inputs:
- fetch_pce_core_yoy_us(start, end) — PCEPILFE
  - Monthly; YoY transformation

M4 FCI inputs:
- fetch_usd_neer_us(start, end) — DTWEXBGS (trade-weighted broad)
- fetch_mortgage_30y_us(start, end) — MORTGAGE30US
- Verify existence: fetch_nfci_chicago_us (may be Sprint 2a or Week 4)
  - If absent, add here

Delisted-series guards: verify each FRED series responds 200 live
during Commit 1 canary. Any 404 → document + flag + CAL item.

Tests:
- Cassette-replay per series (8 cassettes minimum)
- @pytest.mark.slow live canary for 3 representative:
  - DFEDTARU (M1 primary)
  - PCEPILFE (M2 critical)
  - DTWEXBGS (M4)
- Coverage fred.py maintains ≥ 95%

Close CAL-096 in docs/backlog/calibration-tasks.md.
```

### Commit 2 — CBO output gap connector (CAL-097)

```
feat(connectors): CBO output gap via FRED GDPPOT (CAL-097)

src/sonar/connectors/cbo.py new.

Primary implementation: FRED GDPPOT wrapper.
- FRED GDPPOT = "Real Potential Gross Domestic Product" (CBO source)
- If GDPPOT responds 200 live → trivial wrap:

  class CboConnector(BaseConnector):
      async def fetch_output_gap_us(start, end):
          # Fetch GDPPOT quarterly + GDPC1 (actual real GDP)
          potential = await self.fred.fetch_series('GDPPOT', start, end)
          actual = await self.fred.fetch_series('GDPC1', start, end)

          # Align quarterly dates (both should match)
          # gap = (actual - potential) / potential
          gaps = [...]
          return gaps

Fallback if GDPPOT absent: CBO Excel scrape from cbo.gov/data/budget-economic-data
- Fragile; schema-drift guard mandatory
- Implement only if primary path fails in Commit 2 canary

Tests:
- Cassette-replay for GDPPOT + GDPC1
- Unit test for gap calculation math
- @pytest.mark.slow live canary: fetch US output gap last 4 quarters,
  assert values in [-0.10, 0.10] (historical range post-2010)
- Coverage ≥ 92%

Close CAL-097 in docs/backlog/calibration-tasks.md.
```

### Commit 3 — ECB SDW M1-EA empirical dataflow discovery

```
feat(connectors): ECB SDW DFR + ILM M1-EA dataflows (CAL-098 part 1)

Empirical discovery + wiring for M1 EA inputs via ecb_sdw.py.

M1 EA inputs needed:
- policy_rate: DFR (Deposit Facility Rate)
  - Likely ECB dataflow: ILM.D.U2.EUR.4F.KR.DFR.LEV or FM.D.U2.EUR.4F.KR.DFR.LEV
  - Probe live Commit 3 — document canonical key
- balance_sheet: Eurosystem total assets
  - Likely: BSI.M.U2.Y.V.A.A.MAT.U2.2300.Z01.E or similar
  - Probe live — document

Extend ecb_sdw.py with (if not already present):
- fetch_dfr_rate(start, end) -> list[Observation]
- fetch_eurosystem_balance_sheet(start, end) -> list[Observation]

Error handling: if dataflow key format changes (similar BIS CAL-019
pattern), raise DataUnavailableError with canonical-key hint + flag
EA_UNAVAILABLE.

Tests:
- Cassette-replay + schema-drift guards
- @pytest.mark.slow live canary
- Coverage ecb_sdw.py ≥ 90% (maintain)

Note: ecb_sdw.py may already have similar methods from prior work.
If so, adapt this commit to add only missing methods + verify existing
work for M1-EA use case.

Close CAL-098 (part 1) in docs/backlog/calibration-tasks.md.
```

### Commit 4 — Monetary input builders (CAL-100)

```
feat(indices): monetary input builders for M1/M2/M4 (CAL-100)

src/sonar/indices/monetary/builders.py new.

class MonetaryInputsBuilder:
    def __init__(self, fred_conn, ecb_sdw_conn, cbo_conn, nss_overlay, exp_infl_overlay):
        ...

    async def build_m1_inputs(self, country, date) -> M1Inputs:
        """Builds M1 Effective Rates input bundle per spec §2."""

        if country == 'US':
            # FRED primary path
            policy_rate_pct = await self._resolve_us_policy_rate(date)
            balance_sheet = await self.fred.fetch_fed_balance_sheet_us(...)
            # Compute balance_sheet_pct_gdp_yoy

        elif country in ('EA', 'DE', 'PT', 'IT', 'ES', 'FR', 'NL'):
            # ECB SDW primary path
            policy_rate_pct = await self.ecb_sdw.fetch_dfr_rate(date)
            balance_sheet = await self.ecb_sdw.fetch_eurosystem_balance_sheet(...)
            # For non-EA periphery: flag EA_PROXY_MULTIPLE

        # Common: NSS short end + expected inflation + r_star (YAML)
        nss_short_end = await self.nss.fetch_spot(country, date, '3M')
        exp_infl = await self.exp_infl.fetch_canonical(country, date, '5Y')
        r_star = load_r_star_values()[country_or_ea_proxy]

        # Shadow rate: spec §2 precondition — use policy_rate if above ZLB
        shadow_rate = policy_rate_pct if policy_rate_pct > 0.005 else None  # → CAL-099 future

        return M1Inputs(...)

    async def build_m2_inputs(self, country, date) -> M2Inputs:
        """US only this sprint; EA output_gap deferred."""
        if country != 'US':
            raise NotImplementedError("M2 EA pending Week 7 OECD/AMECO output_gap connector")

        # FRED PCEPILFE + CBO output gap + bc_targets + exp_infl 2Y forecast
        ...

    async def build_m4_inputs(self, country, date) -> M4Inputs:
        """US NFCI-primary path."""
        if country != 'US':
            raise NotImplementedError("M4 EA custom-FCI pending Week 7")

        # FRED NFCI + shadow_rate + 10Y from NSS + HY OAS + VIX + mortgage + NEER
        ...

Tests: mocked connector responses + live-canary wiring + assert
graceful NotImplementedError for out-of-scope countries.

Coverage builders.py ≥ 90%.

Close CAL-100 in docs/backlog/calibration-tasks.md.
```

### Commit 5 — Integration live smoke: M1 + M2 + M4 US + M1 EA

```
test(integration): monetary indices live smoke (CAL-098 part 2 + CAL-100 verify)

tests/integration/test_monetary_indices_live.py:

@pytest.mark.slow
async def test_m1_us_live_smoke():
    """Real FRED + computed M1 for US 2024-12-31.
    Assert:
    - score_normalized ∈ [0, 100]
    - stance_vs_neutral_pct in plausible range (Fed post-hiking ~+200 bps
      real stance above neutral)
    - No SHADOW_RATE_UNAVAILABLE flag (above ZLB)
    - No R_STAR_PROXY flag (US has direct HLW value)
    - Confidence ≥ 0.70
    - Persists row in monetary_m1_effective_rates"""

@pytest.mark.slow
async def test_m2_us_live_smoke():
    """Real FRED + CBO + computed M2 for US 2024-12-31.
    Assert:
    - score_normalized ∈ [0, 100]
    - ≥ 3 of 4 Taylor variants computed
    - gap_median_pp likely positive (Fed above rule 2024)
    - Confidence ≥ 0.65"""

@pytest.mark.slow
async def test_m4_us_live_smoke():
    """Real FRED + computed M4 for US 2024-12-31.
    Assert:
    - score_normalized ∈ [0, 100]
    - NFCI-direct path used
    - Confidence ≥ 0.75"""

@pytest.mark.slow
async def test_m1_ea_live_smoke():
    """Real ECB SDW + computed M1 for EA 2024-12-31.
    Assert:
    - score_normalized ∈ [0, 100]
    - Policy rate = ECB DFR
    - Balance sheet via ECB ILM/BSI
    - R_STAR_PROXY flag absent (EA has direct HLW)
    - Confidence ≥ 0.65"""

Wall-clock ≤ 60s total all 4 tests.

Close CAL-098 part 2 (integration smoke) in docs/backlog/calibration-tasks.md.
```

### Commit 6 — Persistence helpers + orchestrator wiring

```
feat(pipelines): monetary persistence helpers + orchestrator entry points

Add to src/sonar/db/persistence.py (or appropriate location):
- persist_m1_effective_rates_result(session, result)
- persist_m2_taylor_gaps_result(session, result)
- persist_m4_fci_result(session, result)

Pattern: same as existing persist_credit_* / persist_financial_*.
Handles UNIQUE constraint violations via upsert (update on conflict by
triplet country_code + date + methodology_version).

Extend src/sonar/indices/orchestrator.py if present:
- compute_all_monetary_indices(country, date, session) → dict

Or if no monetary orchestrator exists yet, create skeleton:
- src/sonar/indices/monetary/orchestrator.py
- compute_all_monetary(country, date, session, builder)
  → {'M1': ..., 'M2': ..., 'M3': ..., 'M4': ...}
- Handles per-index exceptions gracefully

Tests: 8+ unit tests for persistence + orchestrator.

Coverage persistence helpers ≥ 90%.
```

### Commit 7 — Retrospective + CAL closures

```
docs(planning): Week 6 Sprint 2b Monetary Ingestion Omnibus retrospective

File: docs/planning/retrospectives/week6-sprint-2b-monetary-ingestion-report.md

Structure:
- Summary (duration, commits, CAL closures)
- Commits table with SHAs + gate status
- CAL resolutions: CAL-096, CAL-097, CAL-098, CAL-100 closed
- FRED monetary coverage validation (7-8 series live-validated)
- CBO output gap path chosen (GDPPOT FRED primary or Excel fallback)
- ECB SDW M1-EA dataflow keys discovered + documented
- MonetaryInputsBuilder integration matrix (US + EA coverage; non-US
  EA countries + UK/JP still raise NotImplementedError)
- Live smoke outcomes US + EA:
  - M1 US: score + stance pp
  - M2 US: Taylor variants computed
  - M4 US: NFCI-direct
  - M1 EA: score + policy rate + balance sheet
- HALT triggers fired / not fired
- Deviations from brief
- New backlog items:
  - CAL-101 (potential): M2 EA output_gap via OECD EO / AMECO (Week 7+)
  - CAL-102 (potential): M4 EA custom-FCI wiring (Week 7+)
  - CAL-099 remains: Krippner shadow rate (Phase 2+, not ZLB currently)
  - CAL-095 remains: full HLW connector (Phase 2+, YAML works)
- Pipeline readiness: M1/M2/M4 US + M1 EA production-grade

Close CAL-096, CAL-097, CAL-098, CAL-100 in docs/backlog/calibration-tasks.md.
```

---

## 5. HALT triggers (atomic)

0. **Pre-flight spec review** — Commit 1 CC reads CAL entries + spec §2 for M1/M2/M4. Align connector implementations with spec input names + types.
1. **FRED GDPPOT not available** — Commit 2 live probe fails → fallback to CBO Excel scrape. If scrape fragile > 30min → document + defer CAL-097 partial → HALT decision.
2. **ECB SDW DFR dataflow key format unexpected** — Commit 3 empirical probe reveals weird format (BIS CAL-019 pattern) → debug via structure metadata endpoint + document; if not resolvable in 45min, flag EA_UNAVAILABLE + partial close CAL-098.
3. **ECB SDW ILM balance sheet series missing or different code** — similar; document + potentially skip M1 EA balance_sheet component + flag.
4. **FRED monetary series discontinuations** — similar to prior Sprint 2a ISM issue; verify each series Commit 1 live; any 404 → flag + CAL item.
5. **MonetaryInputsBuilder integration breaks existing M1/M2/M4 compute** — input contract mismatch → HALT.
6. **Rate limits on FRED/ECB SDW** hit during batch live canary — reduce scope + document.
7. **Coverage regression > 3pp** → HALT.
8. **Pre-push gate fails** → fix before push, no `--no-verify`.
9. **Concurrent MSC brief touches connectors/** (shouldn't per its §3) → reconcile via rebase.

---

## 6. Acceptance

### Global sprint-end
- [ ] 7-9 commits pushed, main HEAD matches remote, CI green
- [ ] `src/sonar/connectors/fred.py` monetary section ≥ 7 new helpers + coverage maintains ≥ 95%
- [ ] `src/sonar/connectors/cbo.py` coverage ≥ 92%
- [ ] `src/sonar/connectors/ecb_sdw.py` extended with DFR + ILM methods + live-validated
- [ ] `src/sonar/indices/monetary/builders.py` coverage ≥ 90%
- [ ] 4 `@pytest.mark.slow` live canaries PASS: M1 US, M2 US, M4 US, M1 EA
- [ ] Live rows persist to monetary_m1/m2/m4 tables for 2024-12-31 US + M1 EA
- [ ] CAL-096, CAL-097, CAL-098, CAL-100 all CLOSED in `docs/backlog/calibration-tasks.md`
- [ ] Full pre-push gate (full mypy + ruff + pytest) green every push
- [ ] No `--no-verify`

---

## 7. Report-back artifact

File: `docs/planning/retrospectives/week6-sprint-2b-monetary-ingestion-report.md`

**Final tmux echo**:
```
SPRINT 2b INGESTION DONE: N commits, 4 CAL closed (096/097/098/100)
US: M1 + M2 + M4 persist live rows
EA: M1 persists live row
HALT triggers: [list or "none"]
Artifact: docs/planning/retrospectives/week6-sprint-2b-monetary-ingestion-report.md
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

### Break the "compute-defer-connectors" pattern
This sprint is deliberately scoped to **close connectors + ingestion** that 3 prior sprints descoped. If CC finds themselves tempted to HALT and defer to more CAL items, that's a signal of systemic issue — raise to chat, don't silently defer.

### FRED monetary section keeps growing
fred.py is getting large but well-sectioned. Maintain bookmarks:
# === Economic indicators === (Sprint 2a)
# === Monetary indicators === (this brief)
# === (earlier sections: rates, curves, etc.) ===

Consider splitting fred.py into fred/__init__.py + fred/economic.py + fred/monetary.py in a future refactor — NOT this sprint.

### CBO GDPPOT is the happy path
Most CBO output gap series are computed against their GDPPOT. Highest probability is it responds. Fallback Excel scrape only if truly needed.

### ECB SDW dataflow key format is an empirical unknown
Expect to spend 30-45min on Commit 3 probing correct keys. This is the highest-risk item. If it blows up, document + partial close CAL-098 + surface as HALT.

### Integration smoke is the definitive test
Unit tests + cassettes confirm logic. Live smoke confirms the full stack works. Sprint isn't done until all 4 canaries PASS.

### Parallel MSC brief
Runs in tmux `sonar`. Zero file overlap per §3.

---

*End of Week 6 Sprint 2b Monetary Ingestion Omnibus brief. 7-9 commits. 4 CAL items closed. M1/M2/M4 US + M1 EA production-grade.*
