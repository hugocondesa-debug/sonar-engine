# F-Cycle Indices Implementation Brief (F1-F4) — v1

**Target**: Phase 1 Week 4-5 — Financial Cycle sub-indices operational
**Priority**: CRITICAL (unblocks CCCS composite MS sub-index + FCS composite + Bubble Warning overlay)
**Budget**: 8–12h CC autonomous (4 indices + 6-8 new connectors + orchestrator + pipeline)
**Commits**: ~14–18
**Base**: main HEAD post credit track (`80617d1` or later)
**Concurrency**: Parallel to CAL-058 BIS ingestion in tmux `sonar`. See §Concurrency.

---

## 1. Scope

In:
- 4 financial sub-indices operational per spec: F1 Valuations, F2 Momentum, F3 Risk Appetite, F4 Positioning
- New connectors as needed per F3/F4 input matrix:
  - `connectors/cboe` — VIX, VVIX, put/call ratio (CBOE public CSV)
  - `connectors/ice_bofa_oas` — HY OAS (H0A0), IG OAS (C0A0) via FRED (BAMLH0A0HYM2, BAMLC0A0CM)
  - `connectors/chicago_fed_nfci` — NFCI via FRED (NFCI)
  - `connectors/move_index` — MOVE via FRED (MERRILL_LYNCH_MOVE_INDEX proxy) OR ICE direct if free
  - `connectors/aaii` — AAII sentiment weekly survey (free CSV/scrape)
  - `connectors/cftc_cot` — COT non-commercial S&P net positions
  - `connectors/fred_margin_debt` — FINRA margin debt via FRED (BOGZ1FL663067003Q) or FINRA direct
  - `connectors/bis_property` — BIS property price index (existing bis.py extension for WS_LONG_PP dataflow)
- `src/sonar/indices/financial/` package: 4 modules + shared helpers
- Alembic migration **010** — 4 dedicated financial indices tables per spec §8 patterns
- Behavioral tests per spec §7 fixtures (each index)
- `daily_financial_indices.py` pipeline (mirrors daily_credit_indices.py pattern)
- Orchestrator extension: `compute_all_financial_indices(country, date, session)`
- Integration test 7 T1 countries vertical slice

Out:
- **FCS composite computation** (L4 cycle spec, separate sprint Week 5+)
- **Bubble Warning overlay** (L6 diagnostic, separate sprint)
- **Crypto vol** F3 diagnostic sub-component (spec mentions as "diagnostic only" — low priority)
- **Tier 3/4 country coverage** for F2/F3/F4 — T1 only this sprint (T2 partial OK)
- **Real-time WebSocket / streaming feeds** — daily close prices sufficient
- **Options-implied vol surfaces** — VIX/MOVE spot only, no term structure decomposition
- **Live production ingestion layer** — builders return assembled bundle from existing persisted overlays + new connector fetches; NO raw-fetch-persist layer (that is what CAL-058 pattern does for BIS; financial equivalents can emerge later as CAL items)

---

## 2. Spec reference

Authoritative (verified present 2026-04-20, `Last review: 2026-04-19 Phase 0 Bloco E2`):
- `docs/specs/indices/financial/F1-valuations.md` @ `F1_VALUATIONS_v0.1`
- `docs/specs/indices/financial/F2-momentum.md` @ `F2_MOMENTUM_v0.1`
- `docs/specs/indices/financial/F3-risk-appetite.md` @ `F3_RISK_APPETITE_v0.1`
- `docs/specs/indices/financial/F4-positioning.md` @ `F4_POSITIONING_v0.1`
- `docs/specs/indices/financial/README.md` (normalization rationale: z-score 20Y rolling → `clip(50 + 16.67·z, 0, 100)`; lookback 20Y canonical / 10Y Tier 4 fallback with INSUFFICIENT_HISTORY flag)
- `docs/specs/cycles/financial-fcs.md` (downstream consumer — informational; this brief does NOT implement FCS)
- `docs/specs/conventions/units.md`, `flags.md`, `exceptions.md`, `patterns.md`
- `docs/specs/overlays/erp-daily.md` (F1 consumer of ERP median)
- SESSION_CONTEXT §Decision authority + §Brief format + §Regras operacionais

**Pre-flight requirement**: before Commit 1, CC reads each of F1/F2/F3/F4 specs end-to-end and caches in commit body any **material deviation** from assumptions in this brief §3. If ≥ 2 specs deviate materially (e.g., different connector requirements, different normalization scheme, different output schema) → HALT trigger #0 fires, chat reconciles.

Canonical normalization per README (applies all 4 indices):
- z-score vs 20Y rolling window per sub-component
- aggregate sub-scores per index weights (per-spec)
- output: `clip(50 + 16.67 · z_aggregate, 0, 100)` — 3σ ≈ ±50 from centre
- Tier 4 EM fallback: 10Y window + `INSUFFICIENT_HISTORY` flag + `EM_COVERAGE` cap

---

## 3. Concurrency — parallel protocol with CAL-058 BIS ingestion

CAL-058 brief runs in tmux `sonar` simultaneously. Both push to main.

**Hard-locked resource allocation**:
- Migration number: this brief uses **010** (CAL-058 uses 011)
- `src/sonar/db/models.py`: append only between `# === Indices models begin ===` and `# === Indices models end ===` (existing from credit track) — 4 new ORMs `FinancialValuationsResult`, `FinancialMomentumResult`, `FinancialRiskAppetiteResult`, `FinancialPositioningResult`
- CAL-058 will add `BisCreditRaw` ORM in a separate bookmark zone `# === Ingestion models ===` — zero overlap
- `src/sonar/pipelines/`: new file `daily_financial_indices.py` (this brief); CAL-058 creates `daily_bis_ingestion.py`
- `pyproject.toml`: this brief may add `pandas-datareader>=0.10` for some FRED-wrapped series if needed; CAL-058 does not touch pyproject
- Integration tests: new `tests/integration/test_financial_indices.py` (this brief); CAL-058 creates `tests/integration/test_bis_ingestion.py`

**Push race handling**:
- `git push` rejection → `git pull --rebase origin main` → resolve trivial conflicts (import ordering, test discovery) → re-push
- Never `--force`
- `models.py` rebase conflict outside Indices bookmark zone → HALT, CAL-058 violated discipline
- Migration 010 ↔ 011 collision → HALT, chat reconciles

**Start order**: F-cycle brief (this) arranca **primeiro** para criar bookmark zone if needed + establish migration 010. CAL-058 arranca **~1 min depois** para ver state atualizado.

---

## 4. Commits

### Commit 1 — Financial indices package scaffold

```
feat(indices): financial package scaffold + models.py 4 ORMs

Create src/sonar/indices/financial/ package:
- __init__.py with public exports (fit_f1_valuations, fit_f2_momentum,
  fit_f3_risk_appetite, fit_f4_positioning)
- exceptions.py (InsufficientInputsError base, per-index exceptions
  if spec emits custom)
- base.py (FinancialIndexBase ABC with shared normalize method per
  README canonical formula)

Shared helper in src/sonar/indices/_helpers/z_score_rolling.py:
- z_score_rolling_20y(series, date, window_y=20) → (z, μ, σ, n_obs)
- Clamp [-5, +5], flag INSUFFICIENT_HISTORY if n_obs < 60 (15Y hard floor)
- Shared across F1/F2/F3/F4 + reused by credit L1/L2/L3/L4 eventually
  (refactor opportunity, not mandatory this sprint)

In src/sonar/db/models.py (inside # === Indices models === bookmark):
- 4 new ORM classes: FinancialValuationsResult, FinancialMomentumResult,
  FinancialRiskAppetiteResult, FinancialPositioningResult
- Shared common-preamble mixin via FinancialIndexMixin (id, country_code,
  date, methodology_version, score_normalized [0-100], score_raw,
  components_json, lookback_years, confidence, flags, source_connector,
  created_at, UNIQUE (country_code, date, methodology_version))
- Per-spec extras per §8 spec schemas

Unit tests:
- test_z_score_rolling.py: rolling mechanics, INSUFFICIENT_HISTORY flag,
  clamp behavior, synthetic monotonic series
- Package import tests

No alembic migration yet — Commit 2.
```

### Commit 2 — Alembic migration 010 + 4 financial tables

```
feat(db): migration 010 financial indices dedicated tables (4)

4 dedicated tables per spec §8 schemas:
- financial_valuations_results
- financial_momentum_results
- financial_risk_appetite_results
- financial_positioning_results

Common preamble (shared with credit pattern):
country_code, date, methodology_version, score_normalized [0-100] CHECK,
score_raw, components_json, lookback_years, confidence [0-1] CHECK,
flags TEXT, source_connector TEXT, created_at, UNIQUE triplet

Per-spec extra columns (from each spec §8):
- F1: cape_z, buffett_ratio, erp_bps_consumed, forward_pe, property_gap_pp,
  valuation_band
- F2: return_3m_z, return_6m_z, return_12m_z, breadth_pct, cross_asset_z,
  momentum_state
- F3: vix_z, move_z, hy_oas_z, ig_oas_z, nfci_z, ciss_z, risk_regime
- F4: aaii_bull_bear_z, put_call_z, cot_net_z, margin_debt_gdp_z,
  ipo_activity_z, positioning_extreme_flag

Indexes: idx_fin_{val,mom,ra,pos}_cd per standard pattern.

Migration 010 upgrade/downgrade round-trip verified clean.

NOT polymorphic index_values — rationale per credit track (typed
columns, spec-specific CHECK constraints, distinct consumers).
```

### Commit 3 — New connectors batch 1: CBOE + ICE BofA OAS + Chicago NFCI

```
feat(connectors): CBOE (VIX+VVIX+P/C) + ICE BofA OAS + Chicago Fed NFCI

Three connectors — daily price/index series, relatively simple endpoints:

src/sonar/connectors/cboe.py:
- VIX daily close (FRED VIXCLS as primary fallback since CBOE direct
  requires cookie; FRED is clean)
- VVIX daily close (FRED VIXVIX or CBOE direct)
- put/call ratio daily total (CBOE daily CSV at
  https://cdn.cboe.com/api/global/us_indices/daily_prices/ or FRED)
- Cassette-replay tests + live canary

src/sonar/connectors/ice_bofa_oas.py:
- HY OAS via FRED (BAMLH0A0HYM2) — daily, percent
- IG OAS via FRED (BAMLC0A0CM) — daily, percent
- BBB OAS via FRED (BAMLC0A4CBBB) — daily, diagnostic
- Uses existing fred.py BaseConnector pattern

src/sonar/connectors/chicago_fed_nfci.py:
- NFCI via FRED (NFCI) — weekly, standardized
- ANFCI via FRED (ANFCI) — weekly, diagnostic

All connectors:
- BaseConnector subclass per established pattern
- Disk-cached (daily/weekly refresh cadence per series)
- Coverage ≥ 92% per module (phase1-coverage-policy connector hard gate)
- pytest cassettes + live @pytest.mark.slow canaries

pyproject.toml: no new deps if FRED wrapping covers all (existing
httpx + pydantic sufficient).
```

### Commit 4 — New connectors batch 2: MOVE + AAII + CFTC COT

```
feat(connectors): MOVE + AAII sentiment + CFTC COT non-commercial

Three connectors:

src/sonar/connectors/move_index.py:
- MOVE via FRED if available (FRED series ID TBD — MOVE not on FRED
  natively; alternative: ICE public endpoint if free)
- If neither available: degraded connector that raises
  DataUnavailableError + flag path for F3; CAL entry surfaced

src/sonar/connectors/aaii.py:
- AAII weekly sentiment survey bull/bear/neutral percentages
- Primary: AAII public CSV at
  https://www.aaii.com/files/surveys/sentiment.xls (free)
- Fallback: scrape www.aaii.com/sentimentsurvey
- Weekly cadence, Thursday updates
- Graceful DataUnavailableError on layout change + flag

src/sonar/connectors/cftc_cot.py:
- CFTC Commitments of Traders weekly report
- Endpoint: https://www.cftc.gov/dea/newcot/deacot.txt (text) or
  https://publicreporting.cftc.gov/ (JSON API preferred)
- S&P 500 futures non-commercial net positions
- Optional: VIX futures, 10Y Treasury futures, DXY futures (diagnostic)
- Weekly Tuesday data, released Friday

All cassette tests + live canaries + ≥ 92% coverage.
```

### Commit 5 — New connectors batch 3: margin debt + BIS property

```
feat(connectors): FINRA margin debt + BIS property price index extension

src/sonar/connectors/finra_margin_debt.py:
- FRED BOGZ1FL663067003Q (Margin loans by securities brokers and
  dealers) quarterly
- GDP denominator for margin_debt/GDP ratio → fetch from existing
  FRED GDP series
- Alternative: FINRA direct https://www.finra.org/finra-data/browse-
  catalog/margin-statistics weekly if accessible

src/sonar/connectors/bis.py extension:
- Add fetch_property_price_index(country, ...) method
- Dataflow WS_LONG_PP (or WS_PP_LS) for long-run property prices
- Validates whether existing BIS connector pattern extends cleanly

All tests + ≥ 92% coverage on new modules; bis.py coverage stays ≥ 95%.
```

### Commit 6 — F1 Valuations implementation

```
feat(indices): F1 Valuations per F1_VALUATIONS_v0.1

src/sonar/indices/financial/f1_valuations.py per spec §4.

Inputs (per spec §2):
- CAPE (Shiller existing connector — reuse)
- Buffett ratio = Wilshire 5000 / GDP (new: fetch Wilshire 5000 via
  FRED WILL5000INDFC; GDP via FRED GDP) — or use existing market cap
  / GDP series
- ERP median bps from erp_canonical table (existing consumer, computed
  daily per ERP US brief — US only for now, other T1 countries degraded)
- Forward P/E (Shiller ie_data OR FactSet earnings insight existing
  connector — check which has forward P/E persisted)
- BIS property price gap (new: bis_property connector output + HP filter
  equivalent to L2 credit pattern — defer complex HP to flag PROPERTY_GAP_SIMPLE
  and use simple 20Y z-score of level if HP-filter helper not re-applied)

Compute per spec §4 algorithm:
1. Fetch all inputs for (country, date)
2. Compute per-sub-component z-scores vs 20Y rolling
3. Aggregate per spec weights (check spec §4 for exact weights — placeholder:
   CAPE 30%, Buffett 20%, ERP 25%, Forward P/E 15%, Property 10%)
4. score_normalized = clip(50 + 16.67 · z_aggregate, 0, 100)
5. Classify valuation_band: cheap / fair / stretched / bubble per spec
6. Flags per spec §6

Countries Week 4 scope:
- US: full 5-component path
- DE/PT/IT/ES/FR/NL: degraded paths — CAPE may not exist for all (Shiller
  US only); ERP uses US proxy (MATURE_ERP_PROXY_US flag from existing
  k_e pipeline); Buffett ratio needs country-specific market cap (limited
  data); property gap available via BIS for all 7
- Target: all 7 produce a row; US full-confidence, others degraded with flags

Persistence via persist_f1_valuations_result (new helper).

Fixtures per spec §7: us_2024_01_02, us_2000_q1 (bubble peak), us_2009_q1
(trough), de_2024_01_02, pt_2024_01_02_degraded.

Behavioral tests ≥ 20; coverage ≥ 90%.
```

### Commit 7 — F2 Momentum implementation

```
feat(indices): F2 Momentum per F2_MOMENTUM_v0.1

src/sonar/indices/financial/f2_momentum.py per spec §4.

Inputs (per spec §2):
- Price returns 3M/6M/12M from equity index (FMP existing connector —
  S&P 500 for US, country-specific for T1 EU)
- Breadth: % constituents > 200d MA (S&P 500: FRED or compute from
  constituent-level if available; degraded fallback: use price momentum
  z-score as proxy, flag BREADTH_PROXY)
- Cross-asset risk-on signal: ratio of EM equity / DM equity, or
  equity / bond ratio — compute from FMP existing indices

Compute per spec §4:
1. Return windows → z-scores 20Y rolling per window
2. Breadth → z-score 20Y rolling
3. Cross-asset ratio → z-score 20Y rolling
4. Aggregate per spec weights (placeholder: 3M 25%, 6M 25%, 12M 25%,
   breadth 15%, cross-asset 10%)
5. score_normalized = clip(50 + 16.67 · z_aggregate, 0, 100)
6. momentum_state: strong_up / weak_up / flat / weak_down / strong_down
   per spec

All 7 T1 countries in scope (price data available via FMP for all).

Fixtures: us_2024_01_02, us_2020_03_23 (COVID trough — strong_down),
us_2021_12_31 (post-stimulus peak — strong_up).

Behavioral tests ≥ 18; coverage ≥ 90%.
```

### Commit 8 — F3 Risk Appetite implementation

```
feat(indices): F3 Risk Appetite per F3_RISK_APPETITE_v0.1

src/sonar/indices/financial/f3_risk_appetite.py per spec §4.

Inputs (per spec §2):
- VIX via cboe connector (US)
- VSTOXX via stoxx or degraded fallback to FRED STLFSI2 if VSTOXX
  direct not accessible — flag VSTOXX_FALLBACK
- MOVE via move_index connector (US) — flag MOVE_UNAVAILABLE if
  connector returned DataUnavailableError (likely given FRED doesn't
  carry MOVE)
- HY OAS via ice_bofa_oas connector (US benchmark for global)
- IG OAS via ice_bofa_oas connector (US benchmark for global)
- NFCI via chicago_fed_nfci connector (US)
- CISS via ECB SDW existing connector (EA countries) — extend ecb_sdw
  if not already fetching CISS

Compute per spec §4:
1. Vol indices → invert sign then z-score 20Y (high vol = low risk
   appetite → invert for consistent directionality)
2. OAS spreads → invert sign then z-score 20Y (wide spreads = low
   risk appetite)
3. NFCI / CISS → invert sign then z-score 20Y (tight conditions = low)
4. Aggregate per spec weights (placeholder: VIX 20%, MOVE 15%,
   HY OAS 20%, IG OAS 15%, NFCI 20%, CISS 10%)
5. score_normalized = clip(50 + 16.67 · z_aggregate, 0, 100)
6. risk_regime: extreme_fear / fear / neutral / greed / extreme_greed
   per spec

Countries:
- US: full stack (VIX, MOVE, OAS, NFCI) — highest confidence
- EA countries (DE/PT/IT/ES/FR/NL): partial (VSTOXX if available, CISS
  via ECB SDW, US OAS as proxy for risk-off global); flag
  US_PROXY_RISK_APPETITE where applicable

Crypto vol diagnostic: deferred per spec "diagnostic only".

Fixtures: us_2024_01_02, us_2020_03_23 (COVID crash — extreme_fear),
us_2021_12_31 (pre-correction — extreme_greed).

Behavioral tests ≥ 18; coverage ≥ 90%.
```

### Commit 9 — F4 Positioning implementation

```
feat(indices): F4 Positioning per F4_POSITIONING_v0.1

src/sonar/indices/financial/f4_positioning.py per spec §4.

Inputs (per spec §2):
- AAII bull-bear spread weekly via aaii connector (US)
- Put/call ratio via cboe connector (US)
- COT non-commercial S&P net positions via cftc_cot connector (US)
- Margin debt / GDP quarterly via finra_margin_debt connector (US)
- IPO activity quarterly — proxy: count of S&P 500 additions OR FMP
  IPO calendar aggregation; if not tractable this sprint, flag
  IPO_ACTIVITY_UNAVAILABLE and skip in aggregate (weight redistributes)

Compute per spec §4:
1. AAII bull-bear → z-score 20Y
2. Put/call → z-score 20Y (invert — high put/call = defensive = low
   positioning index)
3. COT net positions → z-score 20Y (extreme net long = potential
   reversal)
4. Margin debt / GDP → z-score 20Y
5. IPO activity → z-score 20Y (high IPO = late-cycle froth) OR skip
6. Aggregate per spec weights (placeholder: AAII 25%, P/C 20%, COT 20%,
   margin 25%, IPO 10%)
7. score_normalized = clip(50 + 16.67 · z_aggregate, 0, 100)
8. positioning_extreme_flag: set if |z_aggregate| > 2σ

Countries:
- US: full 5-component path (all connectors US-native)
- DE/PT/IT/ES/FR/NL: US_PROXY_POSITIONING flag — use US as proxy since
  EA-equivalent positioning data sparse and often delayed

Fixtures: us_2024_01_02, us_2000_q1 (margin debt peak), us_2009_q1
(AAII bear extreme).

Behavioral tests ≥ 18; coverage ≥ 90%.
```

### Commit 10 — Financial orchestrator

```
feat(indices): financial orchestrator + compute_all_financial_indices

src/sonar/indices/orchestrator.py extension:
- compute_all_financial_indices(country, date, session) → dict[str, FinancialIndexResult]
- Runs F1 → F2 → F3 → F4 independently (no inter-dependencies per spec —
  4 sub-indices are parallel dimensions)
- Gracefully skip individual on InsufficientInputsError
- Aggregate FCS composite preview in retrospective only (not persisted)

CLI extension:
python -m sonar.indices.orchestrator --country US --date 2024-01-02 \
       --financial-only

--all-cycles flag (new): runs credit + financial in one pass.
```

### Commit 11 — Integration test 7 T1 countries

```
test(integration): F1-F4 vertical slice 7 T1 countries

tests/integration/test_financial_indices.py:
- 7-country parametrized (US/DE/PT/IT/ES/FR/NL) for 2024-01-02
- Cassette-replayed fetches for all new connectors
- Assert each country produces F1+F2+F3+F4 minimum
- Assert all score_normalized ∈ [0, 100]
- Assert confidence ∈ [0, 1]
- Assert flags well-formed CSV
- Assert degraded paths flagged correctly (MATURE_ERP_PROXY_US,
  US_PROXY_RISK_APPETITE, US_PROXY_POSITIONING where expected)
- Persistence round-trip: 28 rows total (4 indices × 7 countries)

Extended cassette library: 6-8 new connectors × 7 countries where
applicable.

≥ 14 integration tests (7 countries × 2 assertions minimum).
```

### Commit 12 — Daily financial pipeline

```
feat(pipelines): daily_financial_indices.py pipeline (L6)

src/sonar/pipelines/daily_financial_indices.py mirrors
daily_credit_indices.py pattern:
- Pluggable InputsBuilder (default empty bundle for now, same defer
  pattern as credit — real production ingestion arrives via future
  CAL item similar to CAL-058)
- Orchestrate F1-F4 computation per country × date
- Batch persist via persist_many_financial_results helper
- CLI: python -m sonar.pipelines.daily_financial_indices \
         --country US --date 2024-01-02 [--all-t1]

Exit codes: 0 success, 1 config error, 2 partial (some countries
succeeded, others skipped), 3 all skipped.

Tests: test_daily_financial_indices.py ≥ 6 unit.
```

### Commit 13 — Documentation amendments

```
docs: F-cycle implementation notes + data_sources

Update docs/data_sources/ with new sources:
- Create docs/data_sources/financial.md documenting:
  - CBOE (VIX, VVIX, P/C)
  - ICE BofA OAS (HY, IG, BBB via FRED)
  - Chicago Fed NFCI (NFCI, ANFCI via FRED)
  - MOVE index availability status
  - AAII sentiment
  - CFTC COT
  - FINRA margin debt
  - BIS property prices
- Licensing notes per existing governance/LICENSING.md pattern

Amendments to existing specs if minor inconsistencies discovered
during implementation (flag commit body, separate from feat commits).
```

### Commit 14 — Retrospective

```
docs(planning): F-cycle implementation retrospective (v0.1 shipped)

File: docs/planning/retrospectives/f-cycle-implementation-report.md

Structure per credit-indices-implementation-report.md template:
- Summary (duration, commits, status)
- Commits table
- Coverage delta per scope
- Tests per index + connector + integration counts
- Connector validation matrix (8 new connectors tested)
- 7-country 2024-01-02 snapshot: F1/F2/F3/F4 values + bands per country
- HALT triggers fired / resolved
- Deviations from brief (likely several given spec reading happens
  during implementation)
- New backlog items surfaced (CAL/P2)
- FCS composite readiness status
- Bubble Warning overlay readiness status
- Blockers for Week 5+ (CCCS composite, FCS composite, regime classifier)
```

---

## 5. HALT triggers (atomic)

0. **Pre-flight spec deviation** — CC reads F1-F4 specs Commit 1 and finds ≥ 2 specs materially deviate from brief §3 assumptions (different connectors, different weights, different output schemas) → HALT, surface to chat
1. **MOVE index connector unavailable** (FRED doesn't carry, ICE doesn't expose free) → proceed with MOVE_UNAVAILABLE flag in F3; redistribute weight; document CAL entry
2. **AAII endpoint 404 or layout changed** → fallback scrape attempts; if both fail, flag AAII_UNAVAILABLE in F4; document CAL
3. **CFTC COT endpoint format change** (text format or JSON API) → pick working path; if both fail, HALT
4. **BIS property price dataflow schema drift** (new CAL-019-style issue for WS_LONG_PP) → debug via structure endpoint; if not resolvable in 30min, flag PROPERTY_GAP_UNAVAILABLE in F1
5. **Migration 010 collision** with CAL-058 migration 011 via rebase → HALT
6. **`models.py` rebase conflict outside Indices bookmark** → CAL-058 violated discipline → HALT
7. **z-score 20Y rolling helper produces NaN** for T1 country with < 60 obs → spec says flag INSUFFICIENT_HISTORY, not raise; verify implementation
8. **Any score_normalized outside [0, 100]** post-clamp → HALT (math bug)
9. **Coverage regression > 3pp** on existing scopes → HALT
10. **Pre-push gate fails** (`uv run ruff format --check && ruff check && mypy && pytest tests/unit/ -x --no-cov`) → fix before push, no `--no-verify`
11. **F1 ERP integration fails** — ERP canonical table query returns no rows for 7 T1 on 2024-01-02 → ERP was only shipped for US; brief assumption correct but verify and flag MATURE_ERP_PROXY_US for non-US

"User authorized in principle" does NOT cover specific triggers. Atomic per SESSION_CONTEXT §Decision authority.

---

## 6. Acceptance

### Per-commit
Enforcement per commit body checklist (CC judgment on formatting).

### Global sprint-end
- [ ] 14-18 commits pushed, main HEAD matches remote, all CI runs green
- [ ] `src/sonar/indices/financial/` 4 modules operational; coverage ≥ 90% per module
- [ ] 6-8 new connectors in `src/sonar/connectors/` coverage ≥ 92% per phase1-coverage-policy hard gate
- [ ] `src/sonar/indices/_helpers/z_score_rolling.py` coverage ≥ 95%
- [ ] `src/sonar/pipelines/daily_financial_indices.py` coverage ≥ 85%
- [ ] Migration 010 applied clean; downgrade/upgrade round-trip green
- [ ] 7 T1 countries produce F1/F2/F3/F4 rows for 2024-01-02 (degraded paths flagged)
- [ ] `python -m sonar.indices.orchestrator --country US --date 2024-01-02 --financial-only` → 4 rows
- [ ] `python -m sonar.indices.orchestrator --country US --date 2024-01-02 --all-cycles` → 8 rows (4 credit + 4 financial)
- [ ] US `risk_regime` classification for 2024-01-02 falls within realistic range (likely "neutral" or "greed" given VIX context)
- [ ] Full test suite green: ≥ 470 unit + ≥ 25 integration tests
- [ ] No `--no-verify` pushes
- [ ] Pre-push gate enforced before every push

---

## 7. Report-back artifact export (mandatory)

Consolidated final: `docs/planning/retrospectives/f-cycle-implementation-report.md`

Template per credit retrospective. Required sections:
1. Summary (duration, commits, status)
2. Commits table with SHAs + scope + CI status
3. Coverage delta per scope (connectors, indices, db, pipelines, helpers)
4. Tests breakdown (F1, F2, F3, F4, connectors 1-8, integration)
5. 7-country 2024-01-02 snapshot: F1/F2/F3/F4 score_normalized + bands + flags
6. Connector validation matrix: 8 new connectors status + degraded paths
7. Spec adherence notes: deviations from brief vs spec reality discovered during implementation
8. HALT triggers table (fired / not fired)
9. New backlog items (CAL/P2) with priorities
10. FCS composite readiness: F1/F2/F3/F4 ready; composite in separate future sprint
11. Bubble Warning overlay readiness: inputs ready; overlay lives L6
12. Blockers for Week 5+: FCS composite, CCCS composite (post-Credit + F-cycle), regime classifier (post-all-cycles)

**Per-commit tmux echoes** (short form):
```
COMMIT N/14 DONE: <scope>, SHA, coverage delta, tests added, HALT status
```

**Final tmux echo**:
```
F-CYCLE DONE: N commits, 4 indices × 7 countries operational
8 new connectors live-validated (with degraded paths per flag matrix)
HALT triggers: [list or "none"]
Artifact: docs/planning/retrospectives/f-cycle-implementation-report.md
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

All four must exit 0. If any fails → fix before push. No `--no-verify`.

---

## 9. Notes on implementation

### Connector degraded paths are acceptable
Spec flags like `MOVE_UNAVAILABLE`, `AAII_UNAVAILABLE`, `US_PROXY_*` are designed in. Don't pause sprint to solve every data gap — flag it + weight redistribution + continue.

### F1 ERP consumer
ERP canonical table has US rows only (per ERP brief scope). Non-US T1 F1 indices will use `MATURE_ERP_PROXY_US` flag. This is consistent with existing k_e pipeline proxy pattern. CAL entry for EA ERP full implementation already exists (CAL-044 or successors).

### z-score rolling helper is shared infrastructure
Move `z_score_rolling_20y` to `src/sonar/indices/_helpers/` now (Commit 1) — credit indices L1-L4 may refactor to use it later (CAL opportunity, not this sprint).

### US_PROXY flags are a governance thing
These flags mean "the signal is directionally correct but magnitude/timing may be US-biased for this country." Editorial outputs should respect them. CCCS/FCS composite consumers should probably cap confidence when US_PROXY flags present. Document in spec amendments (Commit 13).

### Spec weights are placeholders in this brief
Brief uses placeholder weights (e.g., "CAPE 30%, Buffett 20%, ..."). CC MUST read each spec §4 for authoritative weights and use those. If spec weights differ from brief placeholders, use spec. Document in commit body.

### Parallel CAL-058 track
BIS ingestion runs concurrently. Zero overlap expected. If race condition hits `models.py` outside Indices bookmark → HALT trigger #6 fires.

---

*End of F-cycle brief. 4 indices + 8 connectors + orchestrator + pipeline + integration + retrospective. Budget 8-12h. Concurrency with CAL-058 via migration + bookmark + pipeline file separation.*
