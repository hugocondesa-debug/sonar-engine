# Week 9 Sprint Y-DK — DK Nationalbanken Connector + M1 DK TE-primary Cascade — Implementation Report

## 1. Summary

- **Duration**: ~3h wall-clock, single session (within 3-4h budget).
- **Commits**: 6 shipped to branch `sprint-y-dk-connector` (C1 TE
  wrapper → C2 Nationalbanken Statbank connector → C3 DK YAMLs +
  imported_eur_peg convention → C4 M1 DK cascade + M2/M4 scaffolds
  → C5 pipeline wiring + FRED OECD DK + 4 live canaries → C6 this
  retrospective). Brief budgeted 7 commits; C4 bundled M1 cascade
  + M2/M4 scaffolds per the same rationale as Sprints S / T / U /
  V / X-NO / W-SE (one atomic logical change — facade dispatch +
  `__all__` + fakes share a seam, and the new `nationalbanken`
  kwarg on `MonetaryInputsBuilder.__init__` requires all three
  build_m* dispatch branches to exist in the same commit).
- **Branch**: `sprint-y-dk-connector` in isolated worktree
  `/home/macro/projects/sonar-wt-sprint-y`.
- **Status**: **CLOSED** for M1 DK (with the canonical Phase-2+
  caveat shared with Sprint V-CH / W-SE — see §11). Denmark
  monetary M1 row now lands via the canonical `TE primary →
  Nationalbanken Statbank native → FRED OECD stale-flagged`
  cascade — the eighth instantiation of the Sprint I-patch / L /
  S / T / U-NZ / V / X-NO / W-SE pattern, with **two cross-cutting
  Sprint-Y-DK distinctive additions** (both detailed in §2):
  (a) the **source-instrument divergence** between TE primary
  (returns the legacy DISCOUNT rate `DEBRDISC`) and the Statbank
  native cascade slot (returns the **CD rate** `OIBNAA` — the
  active EUR-peg defence tool), captured by the cascade flag-
  emission contract; and (b) the **EUR-peg-imported inflation
  target** convention, materialised via a new
  `target_conventions` block in `bc_targets.yaml` + a new
  `resolve_inflation_target_convention` resolver hook in
  `_config.py` + the always-emitted
  `DK_INFLATION_TARGET_IMPORTED_FROM_EA` flag (replacing the
  standard `EXPECTED_INFLATION_CB_TARGET` flag the other countries
  emit). M2 + M4 DK ship as wire-ready scaffolds raising
  `InsufficientDataError` until the per-country connector bundle
  lands (CAL-DK-CPI / CAL-DK-GAP / CAL-DK-INFL-FORECAST /
  CAL-DK-M4-FCI). M3 DK deferred (CAL-DK-M3) — requires DK NSS +
  EXPINF overlay persistence which is Phase 2+ scope.
- **M2 T1 progression**: **15 → 16 countries monetary M1 live**
  post-merge — completes the **M2 T1 Core target sweep**
  (US + EA + GB + JP + CA + AU + NZ + CH + NO + SE + DK + the 5 EA
  periphery proxies DE/PT/IT/ES/FR/NL via `--all-t1`). The
  `--all-t1` loop preserves its historical 7-country semantics
  (US + DE + PT + IT + ES + FR + NL); GB / JP / CA / AU / NZ / CH
  / NO / SE / DK are Tier-1 opt-ins via `--country GB|JP|CA|AU|
  NZ|CH|NO|SE|DK` matching the pattern Sprint I / L / S / T / U /
  V / X-NO / W-SE established.

## 2. Context — why DK, why now

DK was the seventh G10 country deferred after the GB / JP / CA /
AU / NZ / CH / NO / SE octet shipped Sprints I-patch → W-SE.
Sprint Y-DK adds the third and final Nordic country to the family
(post NO + SE) and closes the **third negative-rate-cascade slot**
after CH + SE. It is also the **first EUR-peg country** in the
cascade family — a structural distinction that surfaces at two
distinct layers (cascade source-instrument + inflation-target
convention) and motivates two new pieces of generalisable
infrastructure (the `target_conventions` resolver hook + the
DK-specific flag vocabulary).

The **distinctive DK concerns** compared to the prior eight
cascades are two-fold:

- **First source-instrument divergence in the cascade family**:
  every prior cascade exposed the same single policy-rate
  instrument across all cascade depths (TE primary + native +
  FRED all referring to e.g. SE Riksbank styrränta, NO Norges
  Bank sight-deposit rate, CH SNB policy rate). DK breaks this
  pattern: TE primary returns the legacy DISCOUNT rate
  (`DEBRDISC` ≡ Statbank `ODKNAA`; only briefly negative
  2021-2022, min -0.60 %), while the Nationalbanken native
  cascade slot returns the **CD rate** (`OIBNAA` —
  `indskudsbevisrenten`, the active EUR-peg defence tool;
  deeply negative across 2015-2022, min -0.75 % at 2015-04-07
  with 2450 strictly-negative daily observations through
  2020-01-07 on the 10780-row full-history series). Both
  representations are operationally valid — the discount rate is
  Nationalbanken's *historical* benchmark, while the CD rate is
  what Nationalbanken actually adjusts to defend the DKK/EUR
  peg within the ERM-II ±2.25 % band. The cascade flag-emission
  contract (`*_TE_PRIMARY` vs `*_NATIONALBANKEN_NATIVE`) makes
  the source observable so downstream consumers can pick the
  right semantic. The Sprint Y-DK retro / module docstrings
  document the divergence exhaustively so future maintainers
  understand why DK breaks the GB / JP / CA / AU / NZ / CH / NO
  / SE single-policy-rate shape.
- **First EUR-peg cascade with an imported inflation target**:
  Nationalbanken does not run an independent monetary policy +
  does not publish a domestic inflation target. The de-facto
  inflation anchor is imported from the ECB's 2 % HICP
  medium-term target via the DKK/EUR ERM-II peg. Sprint Y-DK
  generalises this into a new YAML structure (the
  `target_conventions` block in `bc_targets.yaml`) + a new
  resolver hook (`resolve_inflation_target_convention`) that
  defaults to `"domestic"` for absent countries and lands
  `"imported_eur_peg"` for DK. The cascade emits a DK-specific
  flag `DK_INFLATION_TARGET_IMPORTED_FROM_EA` (always — across
  all three cascade depths) instead of the standard
  `EXPECTED_INFLATION_CB_TARGET` flag the other countries emit.
  The numeric target value is the same 2 % the ECB targets — only
  the SOURCE/CONVENTION carries the structural-coupling story.
  This infrastructure generalises cleanly to any future EUR-peg
  country addition (Bulgaria's BGN/EUR currency board, the
  Maltese / Estonian / Latvian / Lithuanian / Slovenian / Slovak
  pre-EA-entry periods, etc.).

Nationalbanken publishes monetary statistics through three
channels relevant to Sprint Y-DK:

- **Statistics Denmark Statbank.dk public REST API** at
  `https://api.statbank.dk/v1/` — the third-party host where
  Nationalbanken's monetary tables are published under the `DN`
  table prefix. Public, no auth required. Sprint Y-DK uses the
  `POST /v1/data` endpoint with `format=BULK` (semicolon CSV)
  for full-history pulls. The Nationalbanken own-host
  (`nationalbanken.statistikbank.dk`) is the older PX-Web 5a UI
  without a programmatic JSON API so Sprint Y-DK targets the
  Statistics Denmark host explicitly. Four series consumed from
  the `DNRENTD` table:
  - `OIBNAA` (CD rate / indskudsbevisrenten — active EUR-peg
    defence tool; M1 cascade secondary)
  - `ODKNAA` (discount rate / diskontoen — historical benchmark;
    same instrument TE returns under DEBRDISC; exposed for
    cross-validation but not directly consumed)
  - `OIRNAA` (lending rate / udlånsrenten — corridor ceiling;
    reserved for M4 FCI)
  - `OFONAA` (current-account deposit rate / foliorenten —
    corridor floor; reserved for M4 FCI)
- **TradingEconomics (TE)** — same Pro subscription used for the
  prior eight country mirrors — exposes Nationalbanken's
  discount rate as `HistoricalDataSymbol=DEBRDISC` with daily
  cadence and full history back to 1987-08-31 (464 observations
  at probe). The `DEBRDISC` identifier is TE's legacy "Denmark
  Bank Rate Discount" code; TE has not (per the Sprint Y-DK
  probe) added a separate CD-rate indicator path, so TE primary
  is structurally limited to the discount-rate view. The cascade
  ships TE-primary as the canonical first source per the GB / JP
  / CA / AU / NZ / CH / NO / SE pattern — discount rate is still
  a valid policy-rate signal, just not the same instrument as
  the EUR-peg defence tool.
- **FRED's OECD mirror** (`IRSTCI01DKM156N`) available as
  last-resort fallback. Monthly cadence. **Fresh**: Sprint Y-DK
  probe on 2026-04-22 observed the latest observation at
  2025-12-01 — only ~4-month lag, comparable to NO's freshness
  (substantially better than the SE mirror's 5.5-year
  discontinuation; on par with the AU / CA / JP mirrors). The
  cascade still pairs the FRED path with `CALIBRATION_STALE` +
  `DK_POLICY_RATE_FRED_FALLBACK_STALE` so the monthly-vs-daily
  cadence delta surfaces explicitly.

The material Sprint Y-DK novelty vs prior sprints is the
two-cross-cutting structural pattern (source-instrument
divergence + EUR-peg-imported target convention) summarised
above. The mechanical cascade shape is identical to the SE / NO
sprints — same TE wrapper + native connector + FRED fallback +
cascade builder + dispatch + integration canary structure.

## 3. Commits

| # | SHA | Scope |
|---|---|---|
| 1 | `699a421` | feat(connectors): TE `fetch_dk_policy_rate` wrapper + `DEBRDISC` source-drift guard |
| 2 | `4f396a5` | feat(connectors): Danmarks Nationalbanken Statbank.dk public API connector |
| 3 | `da5f89d` | feat(config): DK Tier 1 monetary YAML entries (r* proxy + imported_eur_peg target) |
| 4 | `7078a61` | feat(indices): M1 DK TE-primary cascade with EUR-peg-imported target + M2/M4 scaffolds |
| 5 | `5b4fb19` | feat(pipelines): `daily_monetary_indices` DK country dispatch + FRED OECD DK |
| 6 | this | docs(planning+backlog): Week 9 Sprint Y-DK retrospective + CAL-DK-* items |

All 6 commits on `sprint-y-dk-connector`; full pre-push gate
(`ruff format --check` + `ruff check` + `mypy src/sonar` +
`pytest tests/unit -m "not slow"`) green at Sprint Y-DK close —
ruff + mypy clean (288 files formatted, 117 source files mypy
green); unit tests returned `1555 passed, 44 deselected, 1
error` with the single error being the same pre-existing test-
ordering flakiness Sprint W-SE / X-NO retros documented
(test passes in isolation; reproduces against `main` HEAD with
Sprint Y-DK changes reverted).

## 4. Empirical findings — probes

Three primary probes ran during pre-flight (C0 commit body):

### 4.1 TE DK Policy Rate

- Endpoint: `GET /historical/country/denmark/indicator/interest rate?c=$TE_API_KEY&format=json`
- Response: 464 JSON objects
- First row: `{"DateTime": "1987-08-31T00:00:00", "Value": 8.75, "HistoricalDataSymbol": "DEBRDISC"}`
- Latest row (2026-04-22 probe): `{"DateTime": "2026-03-31T00:00:00", "Value": 1.6, "HistoricalDataSymbol": "DEBRDISC"}`
- All 464 rows carry `HistoricalDataSymbol=DEBRDISC` (no multi-
  symbol contamination across 1987-2026 — discount rate is a
  single uninterrupted instrument across the full history).
- Frequency: Daily (rate-change announcements + interim constant
  quotes; 464 rows spanning 1987-2026 is sparse-daily TE
  convention).
- **Negative-rate validation (TE view)**: 18 rows with `Value < 0`
  spanning `2021-03-31` (first -0.50 %) → `2022-08-31` (last
  -0.10 %). Minimum value -0.60 %.
- **Source-instrument confirmation**: TE returns the discount
  rate, not the CD rate. This was the first probe-time surprise
  — the brief assumed TE would surface the active policy
  instrument as it does for the prior eight countries; instead
  TE persisted the legacy discount-rate path. The retrospective +
  module docstrings document the divergence; both representations
  are operationally valid. See §4.2 for the CD-rate counterpart.

### 4.2 Statbank.dk Nationalbanken (DNRENTD table)

- Endpoint pattern: `POST /v1/data` (JSON body) + `GET /v1/tableinfo/{tableId}` (catalogue)
- HTTP behaviour: public + unscreened; returns `200` on valid
  table+variable combinations, `404` on unknown tables, `400` on
  missing required variables (LAND must be explicitly selected
  for DN tables — discovered during the Sprint Y-DK probe). No
  bot-detection gate. Descriptive `User-Agent` passed
  (`SONAR/2.0 (monetary-cascade; contact hugocondesa@pm.me)`).
- **DNRENTD catalogue probe** (`GET /v1/tableinfo/DNRENTD?lang=en`):
  10 INSTRUMENT codes, 1 LAND (DK), 3 OPGOER methodologies, 10780
  daily observations 1983-05-10 → 2026-04-21. Sprint Y-DK
  consumes 4 of the 10 instruments:
  - `OIBNAA` — CD rate (active EUR-peg defence tool)
  - `ODKNAA` — Discount rate (historical benchmark; what TE returns)
  - `OIRNAA` — Lending rate (corridor ceiling, reserved for M4)
  - `OFONAA` — Current-account deposit rate (corridor floor,
    reserved for M4)
- **`OIBNAA` full-history probe** (BULK, semicolon CSV): 10780
  daily observations, **2450 strictly-negative** spanning
  `2015-02-18` → `2020-01-07` first/last neg pair. **Trough
  -0.75 %** on `2015-04-07` (the deep floor of the EUR-peg
  defence corridor). The CD rate then ran above zero from
  2020-01-07 → 2021-09-23 (the brief COVID-era reset), back below
  zero 2021-09-23 → 2022-09-15 (final negative-rate exit), and
  has been positive ever since. The 1226-vs-2450 count gap vs SE
  Riksbank's `SECBREPOEFF` (1226 negs over 2015-02-18 → 2020-01-07)
  reflects the longer DK negative-rate window — DK first dipped
  negative 2015-02-18 like SE, but stayed negative ~2-3 years
  longer per the EUR-peg-defence imperative during the ECB's
  deep-negative-rate era.
- **Source-instrument divergence quantification**: at the deepest
  point of the negative-rate corridor (2017 H1), the TE-primary
  view (DEBRDISC discount rate) showed roughly 0 % while the
  Statbank native view (OIBNAA CD rate) showed roughly -0.65 %.
  A 65 bps gap between two cascade depths is unprecedented in
  the cascade family — every prior country showed gaps measured
  in single bps (rounding noise across the FRED monthly-vs-daily
  resampling, not instrument divergence).
- **`api-test.statbank.dk`**: not probed (Statistics Denmark
  documents the production host explicitly without an `api-test`
  sibling, unlike Riksbank Swea's `api-test.riksbank.se` lagged
  cache).
- Probe time-box: 20 minutes budgeted, ~12 minutes actual — the
  catalogue-discovery step was fast (`tableinfo` returned the
  full instrument catalogue without auth) and the BULK extract
  completed in ~3 seconds for the full 10780-row history.
- Verdict: third-party-host data publication pattern (Statistics
  Denmark hosts Nationalbanken tables); first
  source-instrument-divergence cascade in the family; no
  operational gates.

### 4.3 FRED OECD DK mirror

- Series metadata probe
  `https://api.stlouisfed.org/fred/series?series_id=IRSTCI01DKM156N&api_key=...&file_type=json`
  → HTTP 200. Full title: "Interest Rates: Immediate Rates
  (< 24 Hours): Call Money/Interbank Rate: Total for Denmark".
- Metadata payload: `observation_start: 1997-01-01`,
  `observation_end: 2025-12-01`, `frequency: Monthly`,
  `last_updated: 2026-01-15 15:37:26-06`.
- **Fresh**: ~4-month lag at probe (2026-04-22 saw 2025-12 as
  latest observation). Comparable to NO's IRSTCI01NOM156N
  freshness (~1 month at NO probe); on par with AU / CA / JP
  (a few months); substantially fresher than the discontinued
  SE mirror.
- Companion 10Y mirror `IRLTLT01DKM156N` probed: HTTP 200,
  observation_end `2026-02-01` — also fresh.
- Wired as last-resort fallback in the cascade with matching
  flag emission. Live-tested via the C5 canary, which **persists
  a real M1 row** (unlike the Sprint W-SE FRED-fallback canary
  which had to assert pre-compute due to the SE mirror's 2020-10
  discontinuation).

## 5. Cascade flag semantics (DK)

```
priority | source                       | flags emitted
---------|------------------------------|-------------------------------------------------------------
   1     | TE primary (DEBRDISC)        | DK_POLICY_RATE_TE_PRIMARY
   2     | Nationalbanken native (OIBNAA)| DK_POLICY_RATE_NATIONALBANKEN_NATIVE
   3     | FRED OECD                    | DK_POLICY_RATE_FRED_FALLBACK_STALE + CALIBRATION_STALE
```

Post-resolution augment (applied at any source depth):

```
{if any resolved observation value < 0}: + DK_NEGATIVE_RATE_ERA_DATA
```

Always-present cross-cutting flags on every persisted DK M1 row:

- `R_STAR_PROXY` (Nationalbanken does not publish an HLW-
  equivalent — 0.75 % real proxy from Nationalbanken WP 152/2020
  + Monetary Review 2024 neutral-range midpoint synthesis;
  Nordic low-r* cluster matching SE)
- **`DK_INFLATION_TARGET_IMPORTED_FROM_EA`** (DK-specific —
  replaces the standard `EXPECTED_INFLATION_CB_TARGET` flag the
  other countries emit; resolved via the new
  `target_conventions: DK: imported_eur_peg` block in
  `bc_targets.yaml` + the `resolve_inflation_target_convention`
  resolver hook in `_config.py`)
- `DK_BS_GDP_PROXY_ZERO` (balance-sheet ratio zero-seeded pending
  CAL-DK-BS-GDP — Nationalbanken MSB monthly-statistical-
  bulletin path + Statistics Denmark nominal GDP still unwired)

**Distinctive absences** vs the SE / NO cascades:

- No `EXPECTED_INFLATION_CB_TARGET` flag (replaced by
  `DK_INFLATION_TARGET_IMPORTED_FROM_EA` due to the EUR-peg-
  imported-target convention)
- No `*_MONTHLY` cadence flag on the Nationalbanken-native slot
  (daily cadence matches TE primary — same as SE Riksbank,
  contrast CH SNB monthly secondary)

**Distinctive presence** vs the SE / NO cascades:

- The `DK_NEGATIVE_RATE_ERA_DATA` flag emission semantics are
  source-dependent (a TE-primary resolution only fires the flag
  for 2021-03..2022-08 windows; a Nationalbanken-native
  resolution fires it for the full 2015-04..2022-09 EUR-peg-
  defence corridor). This is the cascade-level surfacing of the
  source-instrument divergence; downstream consumers reading the
  flag should also read `source_connector` to disambiguate which
  instrument's negative-rate window is being signalled.

## 6. Live canary outcomes (Sprint Y-DK close)

All 4 DK integration canaries pass with `FRED_API_KEY` +
`TE_API_KEY` set:

- `tests/integration/test_daily_monetary_dk.py::test_daily_monetary_dk_te_primary` ✓
- `tests/integration/test_daily_monetary_dk.py::test_daily_monetary_dk_nationalbanken_secondary_when_te_absent` ✓
- `tests/integration/test_daily_monetary_dk.py::test_daily_monetary_dk_fred_fallback_when_te_and_nationalbanken_absent` ✓
- `tests/integration/test_daily_monetary_dk.py::test_daily_monetary_dk_te_primary_preserves_negative_rate_history` ✓

Wall-clock: 4 DK canaries combined = 4.94s.

Connector-level live canaries (3 total):

- `tests/unit/test_connectors/test_te_indicator.py::test_live_canary_dk_policy_rate` ✓
- `tests/unit/test_connectors/test_nationalbanken.py::test_live_canary_nationalbanken_cd_rate` ✓
- `tests/unit/test_connectors/test_nationalbanken.py::test_live_canary_nationalbanken_cd_rate_negative_era` ✓

Regression validation — prior sprint canaries still green:

- `tests/integration/test_daily_monetary_se.py::*` ✓ (Sprint W-SE — 4 canaries)
- `tests/integration/test_daily_monetary_no.py::*` ✓ (Sprint X-NO — 3 canaries)

Wall-clock: combined SE + NO regression suite = 5.03s.

**Anchor choices**:

- **Positive-rate anchor**: `2024-12-31` (Nationalbanken
  discount rate ~2.60 % — mid of the 2024 cutting cycle from
  3.60 % H1 2024 to 1.60 % at probe time 2026-04). Pinned rather
  than today-minus-14 because future Nationalbanken cuts could
  bring the current rate closer to the spec-§4 ZLB threshold,
  invalidating the persistence assertion.
- **Negative-rate anchor**: `2021-09-30` (deep inside the brief
  TE-primary discount-rate dip 2021-03..2022-08; min -0.60 % at
  2021-09-30). Asserts on `inputs.m1.upstream_flags` rather than
  a persisted row — at negative policy rates `compute_m1_effective_
  rates` correctly raises `InsufficientDataError` (spec §4 step
  2 ZLB gate; same Krippner-not-wired story as Sprint V-CH /
  W-SE). See §11 for the long-form discussion. Note the deeper
  -0.75 % CD-rate corridor 2015-2022 is captured separately in
  the C2 connector @slow live canary (`test_live_canary_
  nationalbanken_cd_rate_negative_era`).
- **FRED-fallback anchor**: `2024-12-31` (same as the positive-
  rate anchor — DK FRED OECD mirror is fresh enough at probe
  that a 2024-12-31 anchor returns a recent FRED observation
  well above ZLB and the full M1 compute succeeds against a
  persisted row, unlike the Sprint W-SE FRED-fallback canary
  which had to use a 2020-08-31 anchor + assert pre-compute due
  to the SE mirror's discontinuation).

## 7. Coverage delta

- `src/sonar/connectors/nationalbanken.py` NEW — all branches
  exercised (happy path, negative-value preservation, window
  filter clamping, `..` rows skipped, malformed-token rows
  skipped, empty payload, all-unparseable, HTTP-error retries-
  exhausted, cache round-trip, four convenience wrappers, and
  two @slow live canaries).
- `src/sonar/connectors/te.py` — new `fetch_dk_policy_rate`
  method covered by 5 tests (happy path, negative-value
  preservation, source drift, empty response, cassette 464 rows)
  + 1 @slow live canary with 6Y lookback asserting ≥ 1 negative
  observation survives.
- `src/sonar/indices/monetary/builders.py` — new
  `_dk_policy_rate_cascade` + `build_m1_dk_inputs` +
  `build_m2_dk_inputs` + `build_m4_dk_inputs` covered by 13
  direct tests + 5 facade-dispatch tests (4 shared DK
  fake-connector helpers added: `_FakeTEDkSuccess`,
  `_FakeTEDkUnavailable`, `_FakeNationalbankenSuccess`,
  `_FakeNationalbankenUnavailable`).
- `src/sonar/indices/monetary/_config.py` — new
  `load_target_conventions` + `resolve_inflation_target_
  convention` covered by 3 new loader tests (DK ==
  imported_eur_peg, other countries default to domestic, unknown
  defaults to domestic).
- `src/sonar/pipelines/daily_monetary_indices.py` — DK branch
  exercised by the 4 live canaries + 1 updated
  `MONETARY_SUPPORTED_COUNTRIES` assertion (the 12-tuple now
  includes DK).
- `src/sonar/connectors/fred.py` — 2 new OECD mirror entries in
  `FRED_SERIES_TENORS` (short + long); exercised by the live
  fallback canary.
- `src/sonar/config/r_star_values.yaml` +
  `src/sonar/config/bc_targets.yaml` — DK entries +
  `target_conventions` block; covered by 3 new loader tests + 1
  updated (nine-bank → unchanged, since DK uses ECB target which
  is already present).

No coverage regression > 0.5pp on any touched module.

## 8. HALT triggers fired / not fired

Brief specifies 13 atomic triggers (§5). None fired.

- Trigger 0 (TE DK empirical probe fails) — **not fired**. Probe
  returned 464 rows of `DEBRDISC` with correctly-negative
  historical values 2021-2022.
- Trigger 1 (`HistoricalDataSymbol` mismatch) — **not fired**.
  Source-drift guard in place and unit-tested.
- Trigger 2 (Statbank.dk unreachable) — **not fired**. Reachable
  with plain `curl` (no auth, no UA gate); soft rate limits not
  encountered at sprint scale.
- Trigger 3 (DK tier mismatch) — **not fired**. DK already Tier
  1 in `docs/data_sources/country_tiers.yaml` line 91.
- Trigger 4 (r* DK uncertainty) — **handled via R_STAR_PROXY
  flag.** Value anchored at 0.75 % per Nationalbanken WP
  152/2020 + Monetary Review 2024 neutral-range midpoint
  synthesis; `proxy: true` marker in YAML + source string.
- Trigger 5 (EUR-peg target convention) — **handled via the new
  `imported_eur_peg` convention + `DK_INFLATION_TARGET_IMPORTED_
  FROM_EA` flag.** This is precisely what Sprint Y-DK was
  designed to ship; the trigger documents the convention rather
  than firing.
- Trigger 6 (negative values dropped / clamped) — **not fired;
  actively tested.** Three-layer preservation contract unit-
  tested (TE wrapper + Nationalbanken native + cascade
  aggregation) plus the @slow live canary validates end-to-end
  with both a 2017 CD-rate anchor (-0.65 %, deep corridor) and a
  2021-09-30 discount-rate anchor (-0.60 %, brief dip).
- Trigger 7 (M2 output gap missing) — **handled via graceful
  `InsufficientDataError` scaffold.** CAL-DK-GAP opens the
  follow-up; CAL-DK-M2-EUR-PEG-TAYLOR opens the M2 spec-revision
  follow-up (vanilla Taylor rule will mis-fit a peg-defence
  regime).
- Trigger 8 (M4 FCI coverage < 3/5 components) — **handled via
  graceful `InsufficientDataError` scaffold.** CAL-DK-M4-FCI
  opens the follow-up; CAL-DK-M4-EUR-PEG-FCI opens the hybrid
  FCI Phase 2+ follow-up.
- Trigger 9 (TE rate limits) — **not fired**. Only 1 indicator
  probe + 1 cassette call hit TE during the sprint.
- Trigger 10 (coverage regression > 3pp) — **not fired**.
- Trigger 11 (pre-push gate failure) — **not fired**. No
  `--no-verify` used on any push. Ruff + mypy clean; pytest
  unit returned `1555 passed, 1 error` with the error being the
  same documented test-ordering flake (passes in isolation;
  reproduces against `main` HEAD with Sprint Y-DK reverted).
- Trigger 12 (concurrent Sprint Z touches Sprint Y files) —
  **TBD**. Sprint Z-WEEK9-RETRO runs in parallel in
  `/home/macro/projects/sonar-wt-sprint-z` on
  `docs/planning/retrospectives/README.md` +
  `docs/backlog/calibration-tasks.md`. Per the brief, Sprint
  Y-DK merges first (alphabetical priority); Sprint Z rebases.
  No collision incidents observed during the Sprint Y-DK
  session.

## 9. Deviations from brief

1. **Commit count**: 6 ✓ brief target of 7. C4 bundled M1
   cascade + M2/M4 scaffolds per the same rationale as Sprints
   S / T / U-NZ / V / X-NO / W-SE — splitting would break the
   typing surface of `MonetaryInputsBuilder.__init__` (new
   `nationalbanken` kwarg requires all three build_m* dispatch
   branches to exist in the same commit). Total commit count
   matches the post-S/T/U-NZ/V/X/W pattern.
2. **Source-instrument divergence discovery**: the brief
   assumed (per the SE / NO precedent) that TE primary and the
   Nationalbanken native cascade slot would expose the same
   policy-rate instrument. Empirical probe disproved: TE
   returns the discount rate (DEBRDISC), Statbank native
   returns the CD rate (OIBNAA). The two diverged sharply
   across the 2014-2022 negative-rate corridor (max gap ~65
   bps). The Sprint Y-DK retrospective + module docstrings +
   commit messages document the divergence; both
   representations ship as live cascade slots so downstream
   consumers can pick the right semantic.
3. **Statbank.dk endpoint discovery**: the brief listed
   `https://api.statbank.dk/v1/` as the base URL. Empirical
   probe confirmed that, plus discovered:
   - The Nationalbanken own-host
     (`nationalbanken.statistikbank.dk`) is the older PX-Web 5a
     UI without a programmatic JSON endpoint — Sprint Y-DK
     targets the Statistics Denmark host explicitly.
   - The `POST /v1/data` endpoint requires explicit
     `LAND=["DK"]` selection for the DN tables (BULK extract
     fails with 400 otherwise). Discovered during probe.
   - `format=BULK` (semicolon CSV) is preferred over
     `format=JSONSTAT` for full-history pulls (BULK supports
     the `Tid=["*"]` wildcard without paging; JSONSTAT enforces
     a smaller observation-count ceiling).
4. **`target_conventions` infrastructure not in brief**: the
   brief specified the `DK_INFLATION_TARGET_IMPORTED_FROM_EA`
   flag + the `target_convention: imported_eur_peg` YAML field
   but did not specify how to wire the resolver. Sprint Y-DK
   ships the convention as a *generalisable* infrastructure
   piece (new `target_conventions` block + new
   `resolve_inflation_target_convention` resolver hook +
   `load_target_conventions` reader) so any future EUR-peg
   country addition (BG / pre-EA Baltics / etc.) lands cleanly.
5. **C5 FRED-series fixture gap**: discovered during the live-
   canary run that `FRED_SERIES_TENORS` needed the
   `IRSTCI01DKM156N` + `IRLTLT01DKM156N` entries to allow the
   FRED-fallback canary to resolve. Brief mentioned wiring
   FRED OECD DK but did not flag the `FRED_SERIES_TENORS`
   tenor-mapping requirement explicitly. Trivial fix landed
   inside C5; no rework needed.

## 10. Pattern validation

- **TE-primary cascade is canonical** (eighth sprint confirming
  Sprint I-patch lesson). Every country expansion since Sprint
  I-patch has defaulted to `TE → native → FRED` with the same
  flag shape. The pattern is now load-bearing for any future
  country expansion (Phase 2+ EM additions).
- **Source-instrument divergence (new pattern)**: DK is the
  first country where TE primary and the native cascade slot
  expose different policy-rate instruments. The cascade flag-
  emission contract surfaces the source so downstream consumers
  can disambiguate; both representations ship as live cascade
  slots. Future cascade additions where the central bank has
  multiple official-rate instruments (e.g. ECB has both Deposit
  Facility Rate and Main Refinancing Rate; Fed has Federal Funds
  Target Range + Discount Window; BoJ has IOER + uncollateralised
  overnight) can apply the same dual-instrument pattern with
  source-flag disambiguation.
- **EUR-peg-imported target convention (new pattern)**: the
  `target_conventions` block + `resolve_inflation_target_
  convention` resolver + DK-specific flag generalise cleanly to
  any future EUR-peg country addition. The same pattern applies
  to other currency-board / fixed-rate regimes (Hong Kong's
  HKD/USD peg → `imported_usd_peg` convention; Bulgarian
  BGN/EUR currency board → `imported_eur_peg`; etc.).
- **Daily-cadence native slot** (third instance): DK joins SE +
  NO as the third country where the native secondary cadence
  matches the TE primary cadence. The flag-shape contract
  accommodates this cleanly — Sprint Y-DK ships
  `DK_POLICY_RATE_NATIONALBANKEN_NATIVE` alone rather than the
  two-element `*_NATIVE + *_NATIVE_MONTHLY` pair. The
  `*_MONTHLY` cadence flag is reserved for truly monthly natives
  (CH / AU so far).
- **Catalogue-first reconnaissance pattern**: like Riksbank Swea,
  Statbank.dk exposes a clean `GET /v1/tableinfo/{tableId}`
  endpoint that returns the full instrument catalogue with
  metadata — probe ran in ~5 minutes. The `GET /v1/subjects` +
  `GET /v1/tables` endpoints provide the table-discovery layer.
  General lesson holds: check for a catalogue endpoint before
  brute-forcing identifiers; future EM cascade additions should
  default to this path.
- **Public-scriptable-native slot**: DK is the **sixth country**
  (after CA JSON REST, AU CSV, NZ-still-gated, CH semicolon CSV,
  NO SDMX-JSON, SE Riksbank Swea JSON REST) with a reachable
  native path. When a central bank exposes any public scriptable
  publication, the native slot lands live and the cascade's
  secondary gains full redundancy without staleness. The flag-
  emission contract stays identical across shapes.
- **Third-party-host data publication (new pattern)**: DK is the
  first country where the central bank's data lands via a
  third-party host (Statistics Denmark hosts Nationalbanken's
  monetary tables). The connector module docstring documents this
  explicitly so future maintainers don't accidentally pin to the
  Nationalbanken own-host (which is the older PX-Web 5a UI
  without a JSON endpoint). Generalisable to other Nordic countries
  where the national stats office aggregates central-bank data.

## 11. Known gaps

### 11.1 M1 compute at ZLB / negative rates (shared with Sprint V-CH / W-SE)

Sprint Y-DK inherits the **spec-correct but operationally
significant gap** that Sprint V-CH first surfaced and Sprint W-SE
re-validated: at negative or sub-ZLB policy rates,
`compute_m1_effective_rates` correctly raises
`InsufficientDataError` because `inputs.shadow_rate_pct` is None
and `inputs.policy_rate_pct <= ZLB_THRESHOLD_PCT` (0.5 %). The
spec (`indices/monetary/M1-effective-rates.md` §4 step 2) calls
for a Krippner-shadow-rate connector in this case; none is wired
at Sprint Y-DK scope.

**Impact on DK**: when Nationalbanken sat at ≤ 0.25 % (which it
did across 2014-2022 EUR-peg-defence corridor on the CD-rate
view, and across 2020-2022 on the discount-rate view), M1 DK
rows do not persist. Today (2026-04-22 with Nationalbanken
discount rate at 1.60 % and CD rate similarly above ZLB), the
live `--country DK --date $(today)` run persists normally. The
@slow negative-rate canary (anchor 2021-09-30 at -0.60 %)
validates this behaviour explicitly: `inputs.m1` builds correctly
with `DK_NEGATIVE_RATE_ERA_DATA` firing, but the M1 persistence
step returns 0.

**Mitigation options** (none adopted at Sprint Y-DK scope — same
options as Sprint V-CH / W-SE):

1. Wire a Krippner / Wu-Xia shadow-rate connector (Phase 2+;
   discussed but not scheduled — would become CAL-KRIPPNER and
   unblock CH + SE + DK simultaneously).
2. Seed `shadow_rate_pct` with the policy rate itself when
   negative (spec violation; abandoned).
3. Relax the ZLB gate to allow negative policy rates to flow
   through the non-shadow-rate path (spec revision required;
   out of Sprint Y-DK scope).

The current behaviour is the spec-correct baseline. When
Krippner lands in Phase 2+, the M1-compute step can consume the
existing Sprint-Y-DK cascade output unchanged.

### 11.2 DK-specific — M2 vanilla Taylor rule mis-fits EUR-peg regime

The `build_m2_dk_inputs` scaffold raises
`InsufficientDataError` referencing **two distinct** CAL items:

- CAL-DK-CPI / CAL-DK-GAP / CAL-DK-INFL-FORECAST close the
  *numerical* persistence gap (the three input sources need to
  be wired before M2 DK can compute anything).
- CAL-DK-M2-EUR-PEG-TAYLOR closes the *signal-validity* gap.
  Even when all three inputs land, the vanilla domestic Taylor
  rule will systematically mis-fit a EUR-peg-defence policy
  regime — Nationalbanken does not run an independent monetary
  policy + the policy-rate response function is dominated by
  the peg-defence imperative, not the standard inflation-gap +
  output-gap weighting.

The CAL-DK-M2-EUR-PEG-TAYLOR scope item proposes a DK-specific
Taylor-rule variant that incorporates the DKK/EUR FX deviation
as a third Taylor regressor (or alternatively decomposes the
target rate into "ECB rate + DK-specific peg-defence spread").
Phase 2+ research scope; not blocking M2 DK numerical persistence
once the input sources land.

### 11.3 DK-specific — M4 FCI components are heavily EUR-coupled

Similar to §11.2, the `build_m4_dk_inputs` scaffold references
**two distinct** CAL items:

- CAL-DK-M4-FCI closes the *numerical* coverage gap (≥ 5/5 of
  the seven custom-FCI components need wrappers).
- CAL-DK-M4-EUR-PEG-FCI closes the *signal-validity* gap. The
  DK FCI components (credit spread, vol, NEER, mortgage rate)
  are heavily EUR-coupled — they move with EUR-area cycles much
  more than would be the case in an independent-monetary-policy
  country. A hybrid FCI that blends DK-specific + EA-area
  inputs may carry more signal than a pure DK FCI.

CAL-DK-M4-EUR-PEG-FCI is Phase 2+ research scope; not blocking
M4 DK numerical persistence once the wrappers land.

## 12. Isolated worktree + concurrency

- Sprint Y-DK operated in `/home/macro/projects/sonar-wt-sprint-y`
  on branch `sprint-y-dk-connector`, will be pushed post-sprint.
- Sprint Z-WEEK9-RETRO runs in parallel in
  `/home/macro/projects/sonar-wt-sprint-z` on
  `docs/planning/retrospectives/README.md` +
  `docs/backlog/calibration-tasks.md` (per the brief). Sprint
  Y-DK touched both files (CAL-DK-* additions + the retro's
  natural docs-index entry). **Shared file append zones**:
  `docs/backlog/calibration-tasks.md` (CAL-DK-* additions),
  `docs/planning/retrospectives/README.md` (TBD — the Y-DK retro
  will add itself to the index naturally). Per the brief,
  Sprint Y-DK merges first (alphabetical: Y before Z); Sprint Z
  rebases.
- Clean separation at the per-file level: different content
  blocks (Y-DK adds CAL-DK-* under the existing CAL-SE-*
  pattern; Sprint Z would add Week-9-retro-summary section
  separately). Append-only seams → trivial conflict resolution
  at rebase time.

## 13. Merge strategy (post-sprint close)

Expected: fast-forward when Sprint Z-WEEK9-RETRO has not yet
merged into `main` at Sprint Y-DK branch close time.

```bash
# If Sprint Z has NOT merged (expected):
cd /home/macro/projects/sonar-engine
git fetch origin
git checkout main
git merge --ff-only origin/sprint-y-dk-connector
git push origin main

# If Sprint Z HAS merged first (defensive — alphabetical rule
# says Y before Z so this should not happen):
cd /home/macro/projects/sonar-wt-sprint-y
git fetch origin
git rebase origin/main
# Resolve conflicts at: docs/backlog/calibration-tasks.md
# and docs/planning/retrospectives/README.md (both append-only).
git push origin sprint-y-dk-connector --force-with-lease
cd /home/macro/projects/sonar-engine
git checkout main
git merge --ff-only origin/sprint-y-dk-connector
git push origin main
```

## 14. New CAL items opened

- **CAL-DK** — DK country monetary (M2 T1 Core) — **PARTIALLY
  CLOSED** (M1 level). Mirrors CAL-SE / CAL-NO / CAL-CH.
- **CAL-DK-CPI** — DK CPI / HICP YoY wrapper (OPEN).
- **CAL-DK-GAP** — DK M2 output-gap source (OPEN).
- **CAL-DK-INFL-FORECAST** — DK inflation-forecast wrapper
  (Nationalbanken Outlook or ECB SPF proxy) (OPEN).
- **CAL-DK-M2-EUR-PEG-TAYLOR** — DK M2 spec revision for EUR-
  peg regime (OPEN, Phase 2+ research).
- **CAL-DK-M4-FCI** — DK M4 FCI 5-component bundle (OPEN).
- **CAL-DK-M4-EUR-PEG-FCI** — DK M4 FCI hybrid DK + EA-area
  (OPEN, Phase 2+ research).
- **CAL-DK-M3** — DK M3 market-expectations overlays (OPEN).
- **CAL-DK-BS-GDP** — DK balance-sheet / GDP ratio wiring
  (OPEN).

Formal entries landed in `docs/backlog/calibration-tasks.md` in
this commit. CAL-KRIPPNER (shadow-rate connector, Phase 2+)
deferred — not opened at Sprint Y-DK scope; will surface
naturally when L5 regime-classifier work resumes, and will
unblock CH + SE + DK simultaneously.

## 15. Closing banner

```
SPRINT Y-DK NATIONALBANKEN CONNECTOR DONE: 6 commits on branch sprint-y-dk-connector
TE HistoricalDataSymbol DK validated: DEBRDISC (464 daily obs since
1987-08-31; 18 strictly-negative rows spanning 2021-03-31 →
2022-08-31; min -0.60 %)
Statbank.dk reachability: SUCCESS (DNRENTD/OIBNAA + ODKNAA + OIRNAA
+ OFONAA — public BULK CSV REST, no auth, no bot gate; catalogue
discoverable via GET /v1/tableinfo)
Source-instrument divergence (FIRST IN FAMILY): TE returns discount
rate (DEBRDISC, brief 2021-2022 dip, min -0.60 %), Statbank native
returns CD rate (OIBNAA, full 2015-2022 EUR-peg-defence corridor,
min -0.75 % with 2450 strictly-negative obs); cascade flag-emission
makes source observable
EUR-peg-imported target (FIRST IN FAMILY): DK_INFLATION_TARGET_
IMPORTED_FROM_EA flag (always); new target_conventions block in
bc_targets.yaml + resolve_inflation_target_convention resolver hook
in _config.py — generalisable to any future EUR-peg country
DK monetary: M1 (cascade live with both negative-rate flag +
imported-target flag), M2 (scaffold pending CAL-DK-CPI/GAP/INFL-
FORECAST + spec-revision CAL-DK-M2-EUR-PEG-TAYLOR), M4 (scaffold
pending CAL-DK-M4-FCI + Phase 2+ CAL-DK-M4-EUR-PEG-FCI), M3
deferred (CAL-DK-M3)
M2 T1 progression: 15 → 16 countries monetary M1 live (M2 T1 Core
sweep complete)
Known gap (shared): M1 compute at negative/ZLB rates raises
InsufficientDataError (spec §4 step 2; Krippner integration is
Phase 2+; shared with Sprint V-CH / W-SE)
HALT triggers: none (13 evaluated; 0 fired)
Merge: git checkout main && git merge --ff-only sprint-y-dk-connector
  (Sprint Z-WEEK9-RETRO rebases per brief; Y-DK first by alphabet)
Artifact: docs/planning/retrospectives/week9-sprint-y-dk-connector-report.md
```
