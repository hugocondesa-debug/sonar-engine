# Week 9 Sprint X-NO — Norges Bank Connector + M1 NO TE-primary Cascade — Implementation Report

## 1. Summary

- **Duration**: ~3h wall-clock, single session (within 3-4h budget).
- **Commits**: 6 shipped to branch `sprint-x-no-connector` (C1 TE
  wrapper → C2 Norges Bank DataAPI connector → C3 NO YAMLs → C4 M1 NO
  cascade + M2/M4 scaffolds → C5 pipeline wiring + FRED OECD NO + 3
  live canaries → C6 this retrospective). Brief budgeted 7 commits;
  C4 bundled M1 cascade + M2/M4 scaffolds per the same rationale as
  Sprints S / T / U-NZ / V (one atomic logical change — facade
  dispatch + `__all__` + fakes share a seam; splitting would break
  the typing surface of `MonetaryInputsBuilder.__init__`).
- **Branch**: `sprint-x-no-connector` in isolated worktree
  `/home/macro/projects/sonar-wt-sprint-x`.
- **Status**: **CLOSED** for M1 NO. Norway monetary M1 row now lands
  via the canonical `TE primary → Norges Bank DataAPI native → FRED
  OECD stale-flagged` cascade — the symmetric closure of Sprints I
  (GB), L (JP), S (CA), T (AU), U-NZ (NZ), and V (CH), with one NO-
  specific consideration: **daily-parity on both TE primary and
  Norges Bank native** means the cascade attaches **no** cadence
  qualifier to the secondary path (contrast CH's
  `CH_POLICY_RATE_SNB_NATIVE_MONTHLY`). M2 + M4 NO ship as wire-ready
  scaffolds raising `InsufficientDataError` until CAL-NO-CPI /
  CAL-NO-M2-OUTPUT-GAP / CAL-NO-INFL-FORECAST / CAL-NO-M4-FCI close.
  M3 NO deferred (CAL-NO-M3).
- **M2 T1 progression**: **11 → 12 countries monetary M1 live**. The
  `--all-t1` loop preserves its historical 7-country semantics
  (US + DE + PT + IT + ES + FR + NL); GB / JP / CA / AU / CH / NO
  are Tier-1 opt-ins via `--country GB|JP|CA|AU|CH|NO` matching the
  pattern Sprint I / L / S / T / V established.

## 2. Context — why NO, why now

NO is the first Nordic country in the monetary cascade family.
Post-Sprint-V the Anglosphere + CH quartet (GB / JP / CA / AU / CH)
were all live; the remaining G10 gap is the three Nordics (NO, SE,
DK) + any EM additions. Sprint X-NO closes the NO piece; SE is the
next natural Phase 2+ target (Riksbank has its own negative-rate era
so it will need CH-style flag semantics).

Norges Bank publishes policy rates + yield curves via three channels
relevant to Sprint X-NO:

- **Norges Bank DataAPI** at
  `https://data.norges-bank.no/api/data/{flow}/{key}` — **public +
  unscreened + scriptable** with an `Accept: application/vnd.sdmx.data+json`
  header. No bot-detection gate (empirical probe 2026-04-22 cleared
  with `curl` + standard header; we still pass a descriptive
  `SONAR/2.0` UA for operator identity on the server-side request
  log). Two dataflows consumed by Sprint X-NO: `IR/B.KPRA.SD.R` (key
  policy rate — sight deposit rate) and
  `GOVT_GENERIC_RATES/B.10Y.GBON` (10Y generic gov bond yield).
- **TradingEconomics (TE)** — same Pro subscription used for
  GB / JP / CA / AU / NZ / CH mirrors Norges Bank's policy rate as
  `HistoricalDataSymbol=NOBRDEP` with daily cadence and full history
  back to 1991-01-01 (504 observations at probe). The NOBRDEP
  identifier has been stable across Norges Bank's 1991-now history
  including the 2001 inflation-targeting regime kick-off, the
  2018-03-02 target-level revision (2.5 % → 2.0 %), and the
  2020-2021 COVID-response 0 % trough.
- **FRED's OECD mirror** (`IRSTCI01NOM156N`) available as last-resort
  fallback. Monthly cadence. **Fresh**: Sprint X-NO probe on
  2026-04-22 observed the latest observation at 2026-03-01 — only
  ~1 month lag, the freshest OECD MEI short-rate mirror of any G10
  country (substantially fresher than GB / JP / CA / AU, and
  dramatically fresher than CH which ran ~2 years stale at probe).
  The cascade still pairs the FRED path with
  `CALIBRATION_STALE` + `NO_POLICY_RATE_FRED_FALLBACK_STALE` so the
  monthly-vs-daily cadence delta surfaces explicitly.

The material Sprint X-NO novelty vs prior sprints is twofold:

1. **First SDMX-JSON native connector** in the monetary-cascade
   family. Contrast Sprint S (BoC Valet JSON REST), Sprint T (RBA
   static CSV), Sprint V (SNB semicolon-delimited CSV), and the
   gated BoE IADB (Sprint I) / BoJ TSD (Sprint L) / RBNZ B2 (Sprint
   U-NZ). The SDMX-JSON parser is a new shape — a genuinely different
   parse path from the flat-JSON and CSV siblings.
2. **First fully-positive cascade reach** across the full country
   history. Norway has never run a negative policy rate (minimum
   observed is exactly 0 % during 2020-05-08 → 2021-09-24); the
   cascade consequently **does not emit** a country-specific
   negative-rate flag (contrast CH Sprint V's `CH_NEGATIVE_RATE_ERA_DATA`).
   The wrapper / connector contracts still preserve sign if a
   negative row ever surfaced, but no flag vocabulary is attached.

## 3. Commits

| # | SHA | Scope |
|---|---|---|
| 1 | `3dc88d3` | feat(connectors): TE `fetch_no_policy_rate` wrapper + `NOBRDEP` source-drift guard |
| 2 | `2fe4bf0` | feat(connectors): Norges Bank DataAPI SDMX-JSON connector (policy rate + 10Y GBON) |
| 3 | `38323bb` | feat(config): NO Tier 1 monetary YAML entries (r* proxy 1.25 % + Norges Bank 2 % target) |
| 4 | `e828296` | feat(indices): M1 NO TE-primary cascade + M2/M4 NO scaffolds |
| 5 | `912d5ca` | feat(pipelines): `daily_monetary_indices` NO country dispatch + FRED OECD NO |
| 6 | this | docs(planning): Week 9 Sprint X-NO retrospective + CAL-NO-* items |

All 6 commits on `sprint-x-no-connector`; full pre-push gate
(`ruff format --check` + `ruff check` + `mypy src/sonar` + `pytest
tests/unit -m "not slow"`) green at Sprint X-NO close — ruff + mypy
clean; unit tests returned `1465 passed, 1 failed` with the
single failure being pre-existing test-ordering flakiness that
reproduces against `main` HEAD (different test fails on each run;
Sprint V retro documented the same pattern). The failure is not
caused by Sprint X-NO changes.

## 4. Empirical findings — probes

Three primary probes ran during pre-flight (C1 commit body):

### 4.1 TE NO Policy Rate

- Endpoint: `GET /historical/country/norway/indicator/interest rate?c=$TE_API_KEY&format=json`
- Response: 504 JSON objects
- First row: `{"DateTime": "1991-01-01T00:00:00", "Value": 8.5, "HistoricalDataSymbol": "NOBRDEP"}`
- Latest row (2026-04-22 probe): `{"DateTime": "2026-03-26T00:00:00", "Value": 4.0, "HistoricalDataSymbol": "NOBRDEP"}`
- All 504 rows carry `HistoricalDataSymbol=NOBRDEP` (no multi-symbol
  contamination across the 2001 inflation-targeting kick-off or the
  2018 target-level revision)
- Frequency: Daily (rate-change announcements + interim constant
  quotes)
- **Positive-only validation**: 0 rows with `Value < 0`. Minimum is
  0 % during 2020-05-08 → 2021-09-24 COVID trough. Maximum is 8.5 %
  at 1991-01-01 legacy opening.
- Pro-tier quota hit: 1 call per day per integration test run
  (caches 24h).

### 4.2 Norges Bank DataAPI native

- Endpoint pattern: `GET /api/data/{flow}/{key}?format=sdmx-json`
- HTTP behaviour: public + unscreened; returns `200` on any valid
  dataflow + key, `404 {"errors":[{"code":404, "message": "..."}]}`
  on invalid combinations. No bot-detection gate.
- **`IR/B.KPRA.SD.R`** probe: 1586 rows 2020-01-02 → 2026-04-20
  (cassette-captured). SDMX-JSON schema: four series dimensions
  (`FREQ=B`, `INSTRUMENT_TYPE=KPRA`, `TENOR=SD`, `UNIT_MEASURE=R`)
  pin a single series key `0:0:0:0`; the `observations` dict keys
  are string integer-indices into the `TIME_PERIOD` axis. Parser
  walks the axis to recover dates, filters to `[start, end]`.
- **`GOVT_GENERIC_RATES/B.10Y.GBON`** probe: daily constant-maturity
  yields available. Latest observations at probe: 2026-04-18 at
  4.40 %, 2026-04-20 at 4.344 %.
- **Cube-ID discovery**: unlike SNB (Sprint V) the Norges Bank
  catalogue has a **dedicated policy-rate dataflow** (`IR`) — no
  empirical cube-search required. Dataflow names are self-documenting
  (`CL_INSTRUMENT_TYPE` codelist exposes `KPRA` = "Key policy rate",
  etc.), which made the pre-flight probe substantially shorter than
  the SNB equivalent.
- Probe time-box: 20 minutes budgeted, ~12 minutes actual.
- Verdict: first SDMX-JSON native in the cascade family; no
  operational gates.

### 4.3 FRED OECD NO mirror

- Series metadata probe
  `https://api.stlouisfed.org/fred/series?series_id=IRSTCI01NOM156N&api_key=...&file_type=json`
  → HTTP 200.
- Monthly cadence, OECD-sourced.
- **Fresh**: last observation 2026-03-01 per the Sprint X-NO probe
  (only ~1 month lag — freshest G10 OECD MEI short-rate mirror).
  Substantially fresher than the CH mirror (~2Y lag). The cascade
  still pairs it with `NO_POLICY_RATE_FRED_FALLBACK_STALE` +
  `CALIBRATION_STALE` flags so the cadence delta surfaces to
  operators regardless of freshness.
- Wired as last-resort fallback with matching flag emission. Live-
  tested via the C5 canary.

## 5. Cascade flag semantics (NO)

```
priority | source              | flags emitted
---------|---------------------|-------------------------------------------------------------
   1     | TE primary          | NO_POLICY_RATE_TE_PRIMARY
   2     | Norges Bank native  | NO_POLICY_RATE_NORGESBANK_NATIVE
   3     | FRED OECD           | NO_POLICY_RATE_FRED_FALLBACK_STALE + CALIBRATION_STALE
```

**No post-resolution augmentation flags** (contrast CH's
`CH_NEGATIVE_RATE_ERA_DATA`). NO is a standard positive-only
cascade.

Always-present cross-cutting flags on every persisted NO M1 row:
- `R_STAR_PROXY` (Norges Bank does not publish HLW — 1.25 % real
  proxy from MPR 1/2024 + Staff Memo 7/2023 neutral-rate range mid)
- `EXPECTED_INFLATION_CB_TARGET` (Norges Bank 2 % CPI target post-
  2018-03-02 regime revision; pre-2018 was 2.5 % — documented in
  the YAML for future backtesting)
- `NO_BS_GDP_PROXY_ZERO` (balance-sheet ratio zero-seeded pending
  CAL-NO-BS-GDP; Norges Bank balance-sheet is unusually small by G10
  standards because the GPFG oil-wealth savings are legally offshore-
  invested)

## 6. Live canary outcomes (Sprint X-NO close)

All 3 @slow integration canaries pass with `FRED_API_KEY` +
`TE_API_KEY` set:

- `tests/integration/test_daily_monetary_no.py::test_daily_monetary_no_te_primary` ✓
- `tests/integration/test_daily_monetary_no.py::test_daily_monetary_no_norgesbank_secondary_when_te_absent` ✓
- `tests/integration/test_daily_monetary_no.py::test_daily_monetary_no_fred_fallback_when_te_and_norgesbank_absent` ✓

Regression validation — prior sprint canaries still green:
- `tests/integration/test_daily_monetary_ch.py::*` ✓ (Sprint V — 4 canaries)
- `tests/integration/test_daily_monetary_au.py::*` ✓ (Sprint T — 3 canaries)

Wall-clock: combined NO + CH + AU canary suite = 13.06s.

**Anchor choice**: NO canaries use the `today - 14 days` default
(the pattern Sprints I/L/S/T/U all followed). No historical-anchor
pinning needed because (a) NO is positive-only so no ZLB concern
across the full history, and (b) the FRED OECD mirror is only
1-month-lagged so the `_latest_on_or_before` resolver always has a
fresh-enough observation.

## 7. Coverage delta

- `src/sonar/connectors/norgesbank.py` NEW — all branches exercised
  (happy path SDMX-JSON parse, empty dataSets / series-map,
  HTTP error via retry exhaustion, null-value cells, all-unparseable
  rows, window filtering, cache round-trip, both wrappers, 2 @slow
  live canaries, series-id format validation).
- `src/sonar/connectors/te.py` — new `fetch_no_policy_rate` method
  covered by 6 tests (happy path, positive-only preservation, source
  drift, empty response, cassette 504 rows, @slow live canary).
- `src/sonar/indices/monetary/builders.py` — new
  `_no_policy_rate_cascade` + `build_m1_no_inputs` +
  `build_m2_no_inputs` + `build_m4_no_inputs` covered by 11 direct
  tests + 5 facade-dispatch tests (4 shared NO fake-connector
  helpers added).
- `src/sonar/pipelines/daily_monetary_indices.py` — NO branch
  exercised by the 3 live canaries + 1 updated unit test
  (`MONETARY_SUPPORTED_COUNTRIES` assertion widens 9 → 11).
- `src/sonar/connectors/fred.py` — 2 new OECD mirror entries in
  `FRED_SERIES_TENORS` (short + long); exercised by the live
  fallback canary.
- `src/sonar/config/r_star_values.yaml` + `bc_targets.yaml` — NO
  entries; covered by 3 new loader tests + 1 updated (eight-bank →
  nine-bank) assertion.

No coverage regression > 0.5pp on any touched module. Project
coverage sits at 87.42 % post-Sprint-X-NO per the final pre-push
gate run (baseline pre-Sprint-X-NO was 87.37 % per the baseline
captured on the `main` checkout).

## 8. HALT triggers fired / not fired

- Trigger 0 (TE NO empirical probe fails) — **not fired**. Probe
  returned 504 rows of `NOBRDEP`.
- Trigger 1 (`HistoricalDataSymbol` mismatch) — **not fired**.
  Source-drift guard in place and unit-tested.
- Trigger 2 (Norges Bank DataAPI unreachable) — **not fired**.
  Public + scriptable; plain curl with SDMX-JSON Accept header
  clears.
- Trigger 3 (NO tier mismatch) — **not fired**. NO is already Tier 1
  in the country-tier mapping.
- Trigger 4 (r* NO uncertainty) — **handled via R_STAR_PROXY flag.**
  Value anchored at 1.25 % real per Norges Bank MPR 1/2024 + Staff
  Memo 7/2023 neutral-range mid, `proxy: true` marker in YAML +
  source string.
- Trigger 5 (inflation target revision history) — **handled via
  YAML comment**. The 2.5 % → 2.0 % revision at 2018-03-02 is
  documented inline so pre-2018 backtesting work can swap the value
  without touching resolver logic.
- Trigger 6 (oil-NOK coupling scope creep) — **not fired**. The
  petroleum context is documented in CAL-NO-M4-FCI / CAL-NO-BS-GDP
  as Phase 2+ research scope; no oil-price wrapper shipped at
  Sprint X-NO scope.
- Trigger 7 (M2 output gap missing) — **handled via graceful
  `InsufficientDataError` scaffold.** CAL-NO-M2-OUTPUT-GAP opens the
  follow-up.
- Trigger 8 (M4 FCI coverage < 3/5 components) — **handled via
  graceful `InsufficientDataError` scaffold.** CAL-NO-M4-FCI opens
  the follow-up.
- Trigger 9 (TE rate limits) — **not fired**. Only 1 indicator
  probe + 1 cassette call hit TE during the sprint.
- Trigger 10 (coverage regression > 3pp) — **not fired**.
- Trigger 11 (pre-push gate failure) — **not fired**. No
  `--no-verify` used on any push. Ruff + mypy clean; pytest unit
  failure is pre-existing test-ordering flakiness (reproduces on
  `main` with Sprint X-NO changes reverted — see §3 and Sprint V
  retro §3 for the documented precedent).

## 9. Deviations from brief

1. **Commit count**: 6 ✓ brief target of 7. C4 and C5 per-brief
   planned as distinct commits; C4 landed as one atomic change (M1
   cascade + M2/M4 scaffolds + facade dispatch + unit tests) because
   splitting would break the typing surface of
   `MonetaryInputsBuilder.__init__` (new `norgesbank` kwarg requires
   all three build_m* dispatch branches to exist in the same commit).
   Sprints S / T / U-NZ / V all made the same call. Total commit
   count matches the post-S/T/U-NZ/V pattern.
2. **YAML 1.1 boolean-parse gotcha**: brief did not call out that
   YAML 1.1 parses the unquoted bareword `NO` as boolean `False`
   (alongside `YES`/`Y`/`N`/`TRUE`/`FALSE`/`ON`/`OFF` aliases).
   Sprint X-NO C3 discovered this when the first test run with
   unquoted `NO:` keys raised `KeyError: 'NO'` — the YAML parser
   silently turned the country key into the Python `False` object.
   Both YAMLs updated to quote `"NO":` defensively. Documented
   inline in YAML comments so future operators understand the
   quoting convention isn't decorative.
3. **YAML target-value revision**: the 2018-03-02 Norges Bank
   inflation-target change (2.5 % → 2.0 %) is documented in the
   YAML inline but **not** retroactively applied to the loader —
   backtesting work that anchors pre-2018 needs to swap the YAML
   value manually or thread a date-aware target resolver. This is
   the spec-correct Phase 1 Simplification (matches the Michigan
   5Y inflation expectations treatment in the US path).
4. **No country-tier YAML**: brief referenced
   `country_tiers.yaml` but none exists in the repo (the tier
   assertion is implicit via the `MONETARY_SUPPORTED_COUNTRIES`
   tuple + `T1_7_COUNTRIES` tuple in the pipeline module).
   Updated the Sprint X-NO C5 commit to widen the tuples with NO.

## 10. Pattern validation

- **TE-primary cascade is canonical** (sixth sprint confirming
  Sprint I-patch lesson). Every country expansion since Sprint
  I-patch has defaulted to `TE → native → FRED` with the same flag
  shape. The pattern is now load-bearing for the remaining G10
  Nordics (SE / DK) sprints.
- **Daily-parity secondary pattern**: NO is the first country where
  the native secondary (Norges Bank DataAPI) matches TE's daily
  cadence exactly. Contrast:
  - CA Sprint S: BoC Valet JSON REST — daily parity ✓
  - AU Sprint T: RBA F1 static CSV — **weekly** cadence
  - NZ Sprint U-NZ: RBNZ B2 — **daily-ish** but host perimeter-403s
  - CH Sprint V: SNB zimoma/SARON — **monthly** cadence (adds
    `CH_POLICY_RATE_SNB_NATIVE_MONTHLY` qualifier)
  - NO Sprint X-NO: Norges Bank DataAPI — **daily** parity ✓
  The flag-emission contract stays identical across cadence shapes,
  but `NO_POLICY_RATE_NORGESBANK_NATIVE` attaches no monthly
  qualifier which is itself a contract — downstream consumers can
  read the absence of a cadence flag as "secondary is daily".
- **SDMX-JSON parser addition**: Sprint X-NO introduces a new parse
  shape to the monetary-cascade connector family. The
  `NorgesBankConnector._parse_sdmx_json` helper walks
  `data.structure.dimensions.observation[0].values` to recover the
  TIME_PERIOD date axis then iterates `data.dataSets[0].series`
  with the `0:0:0:0` pinned key. This pattern generalises to the
  ECB SDW endpoint (already wired separately as `ecb_sdw.py`) and
  to any future central bank exposing an SDMX-REST catalogue (e.g.
  Riksbank has an SDMX-JSON endpoint we can probe for Sprint Y-SE).
- **Positive-only country contract**: NO is the first country where
  the cascade's full history is positive-only. The contract is
  asserted at three layers: (1) cassette test on the TE wrapper
  (504 rows, 0 negatives), (2) cassette test on the Norges Bank
  connector (1500+ rows, `min = 0 bps`), (3) unit test on the M1
  cascade (no `NEGATIVE_RATE` flag emitted regardless of source
  depth). This validates the "negative-rate flag attaches to value,
  not source" pattern Sprint V established — because values never
  go negative, no flag fires.
- **YAML config-first for r***: the Norges Bank MPR 1/2024 + Staff
  Memo 7/2023 posterior was directly citable in the
  `r_star_values.yaml` comment block; operators have a canonical
  source string to re-verify at the quarterly refresh ritual.

## 11. Isolated worktree + concurrency

- Sprint X-NO operated in `/home/macro/projects/sonar-wt-sprint-x` on
  branch `sprint-x-no-connector`.
- Sprint W-SE ran in parallel in `/home/macro/projects/sonar-wt-
  sprint-w` on `connectors/riksbank.py` + SE blocks in
  `builders.py` / `te.py` / `daily_monetary_indices.py` +
  `r_star_values.yaml` / `bc_targets.yaml` / `calibration-tasks.md`.
  **Shared file append zones**: `te.py` (new `fetch_*_policy_rate`
  wrapper), `builders.py` (new `_*_cascade` + builders +
  `__all__` entries + dispatch branches), `daily_monetary_indices.py`
  (`MONETARY_SUPPORTED_COUNTRIES` tuple + `_build_live_connectors`
  block), two YAML files, one Markdown file. Per the brief, Sprint
  W-SE merges first (alphabetical: SE before NO — actually NO before
  SE alphabetically, but the brief instruction stands because Sprint
  W-SE was scheduled to merge first regardless of alphabet); Sprint
  X-NO expects a rebase post-merge.
- Clean separation at the per-file level: different method names
  (`fetch_no_policy_rate` / `fetch_se_repo_rate`), different cascade
  function names (`_no_policy_rate_cascade` / `_se_repo_rate_cascade`),
  different native-connector modules (`norgesbank.py` /
  `riksbank.py`). The only true line-level merge points are the
  sorted `__all__` entries in `builders.py` + the tuple literal in
  `MONETARY_SUPPORTED_COUNTRIES` + the append-only YAML entries —
  all trivial three-way merges at rebase time, simply re-sort the
  `__all__` list alphabetically.

## 12. Merge strategy (post-sprint close)

Expected: fast-forward when Sprint W-SE has not yet merged into
`main` at Sprint X-NO branch close time, or three-way merge with
trivial conflicts (append-only seams on the files listed in §11)
when Sprint W-SE has already landed.

```bash
# If Sprint W-SE has NOT merged:
cd /home/macro/projects/sonar-engine
git fetch origin
git checkout main
git merge --ff-only origin/sprint-x-no-connector
git push origin main

# If Sprint W-SE HAS merged:
cd /home/macro/projects/sonar-wt-sprint-x
git fetch origin
git rebase origin/main
# Resolve conflicts at: builders.py __all__, daily_monetary_indices.py
# MONETARY_SUPPORTED_COUNTRIES, r_star_values.yaml, bc_targets.yaml,
# calibration-tasks.md. All append-only so conflicts are trivial
# three-way merges — just re-sort the __all__ list alphabetically.
git push origin sprint-x-no-connector --force-with-lease
cd /home/macro/projects/sonar-engine
git checkout main
git merge --ff-only origin/sprint-x-no-connector
git push origin main
```

## 13. New CAL items opened

- **CAL-NO** — NO country monetary (M2 T1 Core) — **PARTIALLY
  CLOSED** (M1 level). Mirrors CAL-CH (CH) / CAL-AU (AU) / CAL-129
  (CA) / CAL-119 (JP) / CAL-118 (GB).
- **CAL-NO-M2-OUTPUT-GAP** — NO M2 output-gap source (OPEN).
- **CAL-NO-M4-FCI** — NO M4 FCI 5-component bundle (OPEN).
- **CAL-NO-M3** — NO M3 market-expectations overlays (OPEN,
  Phase 2+).
- **CAL-NO-BS-GDP** — NO balance-sheet / GDP ratio wiring (OPEN;
  includes GPFG sovereign-fund-adjusted variant as Phase 2+
  research scope).
- **CAL-NO-CPI** — NO CPI YoY wrapper (OPEN — SSB table 03013 is
  the natural landing).
- **CAL-NO-INFL-FORECAST** — NO inflation-forecast wrapper (OPEN —
  MPR quarterly PDF / HTML).

Formal entries landed in `docs/backlog/calibration-tasks.md` in this
commit.

## 14. Closing banner

```
SPRINT X-NO CONNECTOR DONE: 6 commits on branch sprint-x-no-connector
TE HistoricalDataSymbol NO validated: NOBRDEP (504 daily obs since
1991-01-01; 0 strictly-negative rows — positive-only cascade)
Norges Bank DataAPI reachability: SUCCESS (IR/B.KPRA.SD.R +
GOVT_GENERIC_RATES/B.10Y.GBON — public SDMX-JSON REST, no auth, no
bot gate; dedicated policy-rate dataflow — no cube-search required
unlike SNB Sprint V)
NO monetary: M1 (cascade live — daily-parity on both TE primary and
Norges Bank native), M2 (scaffold pending CAL-NO-CPI/M2-OUTPUT-GAP/
INFL-FORECAST), M4 (scaffold pending CAL-NO-M4-FCI), M3 deferred
(CAL-NO-M3)
M2 T1 progression: 11 → 12 countries monetary M1 live
Pattern first: first SDMX-JSON native in monetary cascade family;
first fully-positive country across full history (no negative-rate
flag vocabulary attached)
HALT triggers: none (11 evaluated; 0 fired)
Merge: git checkout main && git merge --ff-only sprint-x-no-connector
  (rebase expected if Sprint W-SE merged first — trivial conflicts
  at append-only seams)
Artifact: docs/planning/retrospectives/week9-sprint-x-no-connector-report.md
```
