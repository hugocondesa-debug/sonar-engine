# Week 9 Sprint S — CA BoC Valet Connector + M1 CA TE-primary Cascade — Implementation Report

## 1. Summary

- **Duration**: ~2h45m wall-clock, single session.
- **Commits**: 6 shipped to branch `sprint-s-ca-connector` (C1 TE
  wrapper → C2 BoC connector → C3 CA YAML → C4 M1 CA cascade + M2/M4
  scaffolds → C5 pipeline wiring + FRED OECD tenor fix → C6 this
  retrospective). The brief budgeted 6-8 commits; C4 and C5 were
  bundled intentionally because the M1 cascade + M2/M4 scaffolds form
  one atomic logical change and splitting produced no reviewable
  seam.
- **Branch**: `sprint-s-ca-connector` in isolated worktree
  `/home/macro/projects/sonar-wt-sprint-s`.
- **Status**: **CLOSED** for M1 CA. Canada monetary M1 row now lands
  via the canonical `TE primary → BoC Valet native → FRED OECD
  stale-flagged` cascade — the symmetric closure of the Sprint I
  (UK/GB) and Sprint L (JP) cascades. M2 + M4 CA ship as wire-ready
  scaffolds raising `InsufficientDataError` until the per-country
  connector bundle lands (CAL-130 / CAL-131 / CAL-134 / CAL-135). M3
  CA deferred (CAL-132) — requires CA NSS + EXPINF overlay
  persistence which is Phase 2+ scope.
- **M2 T1 progression**: **8 → 9 countries monetary M1 live**. The
  `--all-t1` loop preserves its historical 7-country semantics
  (US + DE + PT + IT + ES + FR + NL); GB / JP / CA are Tier-1 opt-ins
  via `--country GB|JP|CA` matching the pattern Sprint I + L
  established.

## 2. Context — why CA, why now

CA is the last of the three deferred Tier-1 advanced economies
flagged in the M1/US scorecard. UK shipped Week 8 Sprint I + I-patch,
JP shipped Week 8 Sprint L, CA closes the group in Week 9.

Bank of Canada publishes policy rates + yield curve via two channels:

- **BoC Valet JSON REST API** at `https://www.bankofcanada.ca/valet/`.
  **Public + scriptable + reachable** — this is the first native
  connector in the monetary-cascade family to land primary-class.
  Contrast BoE IADB (Akamai-gated, Sprint I) and BoJ TSD
  (browser-gated, Sprint L).
- **TradingEconomics (TE)** — same Pro subscription used for GB + JP
  mirrors BoC's overnight-target series as
  `HistoricalDataSymbol=CCLR` (Canadian Central Lending Rate) with
  daily cadence and full history back to 1990-02-07. Sprint I-patch
  established that TE-primary is the canonical aggregator shape for
  country expansion, so CA defaults to the same pattern.

FRED's OECD mirror (`IRSTCI01CAM156N`) is available as last-resort
fallback but monthly-lagged — demoted to staleness-flagged on the
same terms as the GB / JP mirrors.

The material Sprint S novelty vs prior sprints is the secondary slot
being reachable. Sprint I shipped the BoE cascade with BoE native as
a wire-ready scaffold (Akamai gate); Sprint L shipped BoJ native as
a wire-ready scaffold (browser gate). Sprint S ships BoC Valet as a
working native path — so when TE fails, CA lands
`CA_BANK_RATE_BOC_NATIVE` with **no staleness flag**. That gives CA
the most robust cascade of any non-US Tier-1 country.

## 3. Commits

| # | SHA | Scope |
|---|---|---|
| 1 | `9d11917` | feat(connectors): TE `fetch_ca_bank_rate` wrapper + `CCLR` source-drift guard |
| 2 | `bb868d1` | feat(connectors): BoC Valet public API connector (V39079 + GoC 10Y) |
| 3 | `a8cb7f9` | feat(config): CA Tier 1 monetary YAML entries (r* proxy + BoC 2 % target) |
| 4 | `787f45b` | feat(indices): M1 CA TE-primary cascade + M2/M4 CA scaffolds |
| 5 | `22f0454` | feat(pipelines): `daily_monetary_indices` CA country dispatch |
| 6 | this | docs(planning): Week 9 Sprint S retrospective + CAL-129..135 |

All 6 pushed to `origin/sprint-s-ca-connector`; full pre-push gate
(ruff format + ruff check + mypy src/sonar + pytest unit -m "not
slow") green every push.

## 4. Empirical findings — probes

Three probes ran in parallel during the pre-flight (C1 commit body):

### 4.1 TE CA Bank Rate

- Endpoint: `GET /historical/country/canada/indicator/interest rate?c=$TE_API_KEY&format=json`
- Response: 2320 JSON objects
- First row: `{"DateTime": "1990-02-07T00:00:00", "Value": 12.5, "HistoricalDataSymbol": "CCLR"}`
- Latest row (2026-04-21 probe): `{"DateTime": "2026-03-18T00:00:00", "Value": 2.25, "HistoricalDataSymbol": "CCLR"}`
- All 2320 rows carry `HistoricalDataSymbol=CCLR` (no multi-symbol contamination)
- Frequency: Daily
- Validation: ✓ matches current BoC 2.25 % overnight target (Mar 2026
  cut). Pro-tier quota hit: 1 call per day per integration test run
  (caches 24h).

### 4.2 BoC Valet native

- Endpoint: `GET /valet/observations/V39079` (Target for the overnight rate)
- Response format:
  ```json
  {
    "terms": {"url": "https://www.bankofcanada.ca/terms/"},
    "seriesDetail": {"V39079": {"label": ..., "description": "Target for the overnight rate"}},
    "observations": [{"d": "2026-04-20", "V39079": {"v": "2.25"}}]
  }
  ```
- Date filters: `start_date` / `end_date` query params, inclusive both ends
- HTTP: 200, no auth, no user-agent sniff
- Latest probe: `2026-04-20 → 2.25` (daily-fresh, weekends forward-filled)
- Probe time-box: 20 minutes budgeted, ~3 minutes actual.
- Verdict: **first native connector in the cascade family to land
  reachable primary-class.**

Side-finding during C2: the original brief pointer at V122544 (10Y
GoC benchmark) returned 404. The correct Valet series ID for the 10Y
benchmark yield is **`BD.CDN.10YR.DQ.YLD`** (discovered via
`/valet/lists/series/json?search=10`). Fixed in C2 before the series-ID
regression-guard test locked the contract.

### 4.3 FRED OECD CA mirror

- Series metadata probe `https://api.stlouisfed.org/fred/series?series_id=IRSTCI01CAM156N&api_key=...&file_type=json` → HTTP 200
- Monthly cadence, OECD-sourced, ~48-month lag-free
- Wired as last-resort fallback with `CA_BANK_RATE_FRED_FALLBACK_STALE`
  + `CALIBRATION_STALE` flags

## 5. Cascade flag semantics (CA)

```
priority | source       | flags emitted
---------|--------------|------------------------------------------------------------
   1     | TE primary   | CA_BANK_RATE_TE_PRIMARY
   2     | BoC Valet    | CA_BANK_RATE_BOC_NATIVE
   3     | FRED OECD    | CA_BANK_RATE_FRED_FALLBACK_STALE + CALIBRATION_STALE
```

Always-present cross-cutting flags on every persisted CA M1 row:
- `R_STAR_PROXY` (BoC does not publish HLW — 0.75 % proxy from BoC
  Staff Discussion Paper 2024)
- `EXPECTED_INFLATION_CB_TARGET` (BoC 2 % CPI target is the Phase 1
  proxy for 5Y inflation expectation)
- `CA_BS_GDP_PROXY_ZERO` (balance-sheet ratio zero-seeded pending
  CAL-133)

## 6. Live canary outcomes (Sprint S close)

All five @slow integration canaries pass with `FRED_API_KEY` +
`TE_API_KEY` set:

- `tests/integration/test_daily_monetary_ca.py::test_daily_monetary_ca_te_primary` ✓
- `tests/integration/test_daily_monetary_ca.py::test_daily_monetary_ca_boc_secondary_when_te_absent` ✓
- `tests/integration/test_daily_monetary_ca.py::test_daily_monetary_ca_fred_fallback_when_te_and_boc_absent` ✓
- `tests/integration/test_daily_monetary_jp.py::test_daily_monetary_jp_te_primary` ✓ (unchanged)
- `tests/integration/test_daily_monetary_jp.py::test_daily_monetary_jp_fred_fallback_when_te_absent` ✓ **(FIXED by Sprint S C5)**

The JP FRED-fallback canary was silently broken at HEAD before Sprint
S — the OECD mirror series IDs (`IRSTCI01GBM156N` / `IRSTCI01JPM156N`)
were used by the cascade but absent from `FRED_SERIES_TENORS` so the
connector raised `ValueError("Unknown FRED series mapping")`. Sprint S
C5 added those entries (plus the CA equivalents) as a net-positive
wire fix during CA pipeline integration.

Wall-clock: combined CA + JP canary run = 7.19s.

## 7. Coverage delta

- `src/sonar/connectors/boc.py` NEW — all branches exercised (happy
  path, empty observations, HTTP error via retry exhaustion, null-value
  rows, all-unparseable rows, cache round-trip, two wrappers).
- `src/sonar/connectors/te.py` — new `fetch_ca_bank_rate` method
  covered by 5 tests (happy path, source drift, empty response,
  cassette 2320 rows, @slow live canary).
- `src/sonar/indices/monetary/builders.py` — new `_ca_bank_rate_cascade`
  + `build_m1_ca_inputs` + `build_m2_ca_inputs` + `build_m4_ca_inputs`
  covered by 10 direct tests + 5 facade-dispatch tests.
- `src/sonar/pipelines/daily_monetary_indices.py` — CA branch
  exercised by 1 new unit test + 3 live canaries.
- `src/sonar/connectors/fred.py` — 6 new OECD mirror entries in
  `FRED_SERIES_TENORS`; indirectly exercised by the live fallback
  canaries.

No coverage regression > 0.5pp on any touched module.

## 8. HALT triggers fired / not fired

- Trigger 0 (TE CA empirical probe fails) — **not fired**. Probe
  returned 2320 rows of `CCLR`.
- Trigger 1 (HistoricalDataSymbol mismatch) — **not fired**. Source-
  drift guard in place and unit-tested.
- Trigger 2 (BoC Valet unreachable) — **not fired**. Valet is live +
  scriptable.
- Trigger 3 (CA tier mismatch) — **not fired**. CA is already Tier 1
  in `country_tiers.yaml` per ADR-0005.
- Trigger 4 (r* CA uncertainty) — **handled via R_STAR_PROXY flag.**
  Value anchored at 0.75 % per BoC Staff Discussion Paper 2024
  neutral-rate refresh, `proxy: true` marker in YAML + source string.
- Trigger 5 (M2 output gap missing) — **handled via graceful
  InsufficientDataError scaffold.** CAL-130 opens the follow-up.
- Trigger 6 (M4 FCI coverage < 3/5 components) — **handled via
  graceful InsufficientDataError scaffold.** CAL-131 opens the
  follow-up.
- Trigger 7 (TE rate limits) — **not fired**. Only 1 indicator probe
  + 1 cassette call hit TE during the sprint.
- Trigger 8 (coverage regression > 3pp) — **not fired**.
- Trigger 9 (pre-push gate failure) — **not fired**. No `--no-verify`
  used on any push.
- Trigger 10 (concurrent Sprint P touches pipeline/cycle files) —
  **not fired**. Sprint P (CAL-128-FOLLOWUP) operates in
  `sonar-wt-sprint-p` on `cycles/` + `overlays/` + UK→GB rename
  sweeps; zero file overlap with Sprint S which only touched
  connectors/monetary/pipeline paths.

## 9. Deviations from brief

1. **BoC Valet 10Y series ID**: brief drafted the constant as `V122544`
   (following the numeric-V pattern of V39079). Empirical probe returned
   404. Corrected to `BD.CDN.10YR.DQ.YLD` via the Valet
   `/lists/series/json?search=10` search endpoint before C2 was
   committed. Documented in the C2 commit body.
2. **V39051 (Bank Rate vs Target for the overnight rate)**: originally
   catalogued alongside V39079 as a convenience constant. Probe
   returned 404; drop the constant from the `__all__` entirely. The
   overnight target (V39079) is the single canonical policy-rate
   series the cascade consumes.
3. **Commit count**: 6 ✓ brief (6-8). C4 and C5 per-brief planned as
   distinct commits; landed as one atomic change (M1 + M2/M4
   scaffolds) because the facade dispatch + `__all__` + fakes
   genuinely share a seam. Total count within budget.
4. **JP FRED-fallback fix**: not in the brief but surfaced naturally
   during Sprint S live-canary runs. Fixed in C5 as a net-positive
   wire change — the `FRED_SERIES_TENORS` extension covers CA + GB +
   JP in the same hunk.

## 10. Pattern validation

- **TE-primary cascade is canonical** (third sprint confirming
  Sprint I-patch lesson). Every country expansion since Sprint I-patch
  has defaulted to `TE → native → FRED` with the same flag shape.
  Persist this pattern for AU / NZ / CH when they land Phase 2+.
- **First-class reachable native slot**: CA is the counter-example
  to GB + JP's gated natives. When a central bank exposes a public
  scriptable API (BoC Valet, BIS WS_TC, ECB SDW), the native slot
  lands live and the cascade's secondary gains full redundancy
  without staleness. The flag-emission contract stays identical to
  the gated case, so the downstream signal-quality semantics are
  invariant to the reachability of the native path.
- **OECD mirror wire completeness**: the Sprint S C5 discovery (GB +
  JP OECD mirrors silently broken in live fallback) is a lesson for
  future cascade sprints: run the live FRED-fallback canary as part
  of pre-push on any sprint shipping a new cascade, not just a
  post-merge smoke.
- **YAML config-first for r***: the BoC Staff Discussion Paper 2024
  neutral-rate refresh was directly citable in the `r_star_values.yaml`
  comment block; operators have a canonical source string to re-verify
  at the quarterly refresh ritual.

## 11. Isolated worktree + concurrency

- Sprint S operated in `/home/macro/projects/sonar-wt-sprint-s` on
  branch `sprint-s-ca-connector`, pushed to
  `origin/sprint-s-ca-connector`.
- Sprint P (CAL-128-FOLLOWUP — cycles/overlays UK→GB rename) ran in
  parallel in `/home/macro/projects/sonar-wt-sprint-p`. Zero file
  overlap verified post-facto: Sprint S touched
  `connectors/{boc,te,fred}.py` + `indices/monetary/builders.py` +
  `pipelines/daily_monetary_indices.py` + monetary config YAMLs;
  Sprint P touches `cycles/financial_fcs.py` + `overlays/crp.py` +
  `overlays/live_assemblers.py` + `daily_cost_of_capital.py`. Clean
  separation per brief §3.

## 12. Merge strategy (post-sprint close)

Fast-forward expected — no intermediate merges into `main` between
`b528265` (Sprint P-preparatory HEAD at Sprint S branch-point) and
`22f0454` (Sprint S C5, pre-retro).

```bash
cd /home/macro/projects/sonar-engine
git fetch origin
git checkout main
git merge --ff-only origin/sprint-s-ca-connector
git push origin main
```

## 13. New CAL items opened

- **CAL-129** — CA country monetary (M2 T1 Core) — **PARTIALLY
  CLOSED** (M1 level). Mirrors CAL-118 (UK) / CAL-119 (JP).
- **CAL-130** — CA M2 output-gap source (OPEN).
- **CAL-131** — CA M4 FCI 5-component bundle (OPEN).
- **CAL-132** — CA M3 market-expectations overlays (OPEN).
- **CAL-133** — CA balance-sheet / GDP ratio wiring (OPEN).
- **CAL-134** — CA CPI YoY wrapper (OPEN).
- **CAL-135** — CA inflation-forecast wrapper (BoC MPR) (OPEN).

Formal entries landed in `docs/backlog/calibration-tasks.md` in this
commit.

## 14. Closing banner

```
SPRINT S CA CONNECTOR DONE: 6 commits on branch sprint-s-ca-connector
TE HistoricalDataSymbol CA validated: CCLR (2320 daily obs since 1990)
BoC Valet reachability: SUCCESS (V39079 = Target for the overnight
rate — public JSON REST API, no auth)
CA monetary: M1 (cascade live), M2 (scaffold pending CAL-130/134/135),
M4 (scaffold pending CAL-131), M3 deferred (CAL-132)
M2 T1 progression: 8 → 9 countries monetary M1 live
HALT triggers: none
Net wire fix: JP FRED-fallback canary unblocked by FRED_SERIES_TENORS
extension (was silently broken at HEAD)
Merge: git checkout main && git merge --ff-only sprint-s-ca-connector
Carve-out respected: zero file overlap with Sprint P parallel worktree
Artifact: docs/planning/retrospectives/week9-sprint-s-ca-connector-report.md
```
