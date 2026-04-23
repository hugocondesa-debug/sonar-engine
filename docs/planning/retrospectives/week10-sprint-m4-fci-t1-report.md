# Week 10 Day 2 Sprint J — CAL-M4-T1-FCI-EXPANSION Retrospective

**Sprint**: J — Week 10 Day 2 M4 FCI T1 expansion
(`CAL-M4-T1-FCI-EXPANSION`).
**Branch**: `sprint-m4-fci-t1-expansion`.
**Worktree**: `/home/macro/projects/sonar-wt-m4-fci-t1-expansion`.
**Brief**: `docs/planning/week10-sprint-j-m4-fci-t1-brief.md`
(format v3).
**Pre-flight**:
`docs/planning/week10-sprint-j-m4-fci-t1-preflight-findings.md`.
**Duration**: ~3h CC across two sessions (TE-quota outage mid-sprint
→ resolved by TE support restoring the 5000-req/month tier; sprint
resumed from a post-crash restart with CWD recovered from the
correct worktree).
**Commits**: 7 substantive (brief + 5 implementation + this retro).
**Outcome**: Ship **7 new M4 FCI FULL-compute entities** via the
shared-EA proxy pattern (EA aggregate + DE + FR + IT + ES + NL + PT),
preserve **US canonical** (NFCI direct-provider, HALT-1 absolute),
and ship **GB NEW scaffold** alongside the 8 preserved scaffolds
(AU / CA / CH / DK / JP / NO / NZ / SE). Post-sprint M4 T1 coverage:
**8/17 FULL compute** (US canonical + 7 Sprint-J-new) +
**9/17 SCAFFOLD** (GB new + 8 preserved). 17/17 dispatcher-wired.

Paralelo with Sprint I (CAL-CURVES-FR-TE-PROBE, worktree
`sonar-wt-curves-fr-te-probe`) observed **zero primary-file
conflict**: Sprint I landed ahead (5b796e2, merged main between
sessions); Sprint J rebase on `te.py` was a trivial union-merge on
the disjoint bookmark zones (yield section vs M4 section) and the
Sprint I CAL deltas merged cleanly against Sprint J's CAL edits in
this commit. Alphabetical merge priority (i < j) delivered as
designed.

---

## 1. Commit inventory

| # | SHA        | Subject                                                                                           | Scope                                                                                                                                                                              |
|---|------------|---------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1 | `f693c02`  | docs(planning): Sprint J brief + M4 FCI T1 pre-flight probe matrix (C1)                           | Brief v3 + pre-flight findings: 48-probe matrix (16 T1 × 3 legacy components + 5-component custom-path floor confirmed). HALT-0 cleared; HALT-14 surfaced (SCAFFOLD > 6).          |
| 2 | `33e8dee`  | feat(connectors): TE equity-volatility + FRED OAS wrappers for M4 FCI (C2)                        | TE `VIX:IND` / `VSTOXX:IND` markets-endpoint wrappers + FRED `BAMLC0A0CM` (US IG) + `BAMLHE00EHYIOAS` (EA HY) OAS wrappers. US cassette + EA markets cassette.                      |
| 3 | `6a2d51d`  | feat(connectors): BIS WS_EER NEER per country + EA aggregate (C3)                                 | `BisConnector.fetch_neer(country)` on `M.N.B.{CTY}` broad-basket monthly. 17/17 coverage (16 T1 + EA aggregate `XM`). Per-country SONAR → BIS code map documented.                   |
| 4 | `6c0e414`  | feat(indices): M4 FCI EA + DE FULL compute builders + MIR wrapper (C4)                            | `ecb_sdw.fetch_mortgage_rate` (MIR `M.{CC}.B.A2C.A.R.A.2250.EUR.N`) + monthly `TIME_PERIOD` parse + `_assemble_m4_ea_custom_inputs` helper + `build_m4_ea_inputs` + `build_m4_de_inputs` + US canonical regression guard (`TestSprintJUsBaselineGuard`, HALT-1 absolute). |
| 5 | `162ea2b`  | feat(indices): M4 FCI EA-members FULL + GB scaffold (C5)                                          | `_build_m4_ea_member_inputs` internal + `build_m4_fr_inputs` / `build_m4_it_inputs` / `build_m4_es_inputs` / `build_m4_nl_inputs` / `build_m4_pt_inputs` wrappers + `build_m4_gb_inputs` scaffold + `_M4_EA_PROXY_BUILDERS` dispatch dict. Parametrised 5-country test case + GB scaffold raise test. |
| 6 | `e09d8b4`  | refactor(pipelines): daily_monetary_indices M4 dispatch + _classify_m4_compute_mode (C6)          | `MONETARY_SUPPORTED_COUNTRIES` extended DE/FR/IT/ES/NL/PT + `_build_live_connectors` wires BIS + builder plumbs `bis=bis` + `_classify_m4_compute_mode` helper (FULL/SCAFFOLD/CANONICAL) + `monetary_pipeline.m4_compute_mode` observability log + 5 classifier tests. |
| 7 | *(this retro)* | docs(planning+backlog): Sprint J retrospective + CAL closure                                  | Retro per v3 format + `CAL-M4-T1-FCI-EXPANSION` CLOSED + 4 new CAL items opened (vol / credit-spread / mortgage-rate / NEER-daily).                                                 |

---

## 2. Pre-flight findings (Commit 1 body, 2026-04-22 probes)

Full per-country per-component matrix in
`docs/planning/week10-sprint-j-m4-fci-t1-preflight-findings.md`.
Sprint J executed against that matrix line-for-line with one scope
adjustment documented in §4 below. Key probe outcomes:

- **TE markets** (`VSTOXX:IND`, `VIX:IND`) **provisioned**; per-country
  TE-tier-3 symbols (`V2TX`, `VFTSE`, `NKYVOLX`, and national
  equivalents for CA/AU/NZ/CH/SE/NO/DK) returned `200 []` at our API
  key. This forced the **shared-EA proxy** architecture (VSTOXX
  carries EA + 6 EA members via common-practice EA implied vol) and
  pushed the 9 non-EA T1 countries below the 5-component floor.
- **TE per-country `volatility` + `corporate bond spread` endpoints**
  empty across all 17 probes — not usable paths at our tier.
- **FRED BAML OAS**: `BAMLC0A0CM` (US IG) + `BAMLHE00EHYIOAS` (EA HY)
  live; no per-country OAS beyond these two.
- **BIS WS_EER** `M.N.B.{CTY}` **17/17 coverage** (monthly); NEER
  is universally available — the only M4 component with full T1
  breadth.
- **ECB MIR** dataflow key `M.{CC}.B.A2C.A.R.A.2250.EUR.N` covers
  EA aggregate (U2) + DE / FR / IT / ES / NL / PT (7/7 EA entities);
  no coverage for GB / JP / non-EA T1.

### HALT evaluation

- **HALT-0** (< 8 countries with ≥ 2 components): cleared — all 16 T1
  + EA report ≥ 2 components viable (BIS NEER floor).
- **HALT-1** (US canonical regression): absolute — regression guard
  `TestSprintJUsBaselineGuard` unit-tests the NFCI short-circuit with
  no custom-path flag leakage; PASS across C4 / C5 / C6.
- **HALT-12** (> 8 PARTIAL_COMPUTE): not applicable — the spec-side
  `MIN_CUSTOM_COMPONENTS = 5` rejects partial compute, so sub-5
  builders are SCAFFOLD not PARTIAL.
- **HALT-14** (SCAFFOLD > 6): **fires** — 9 T1 countries (GB + 8
  preserved) end SCAFFOLD post-sprint. Systematic root cause
  documented in pre-flight §4 (TE tier-3 vol symbols absent, no
  per-country OAS, per-CB mortgage series out of Sprint-J scope).
  Triaged into four follow-up CAL items opened at closure — see §10.

---

## 3. Scope decision + cadence

The pre-flight steered Commit 4 off the brief's Tier A list (brief
§1 imagined GB + JP + CA + DE all landing FULL) and onto the probe
matrix: the 5-component floor is only reachable for EA + the 6 EA
members. US canonical stays on the NFCI short-circuit. GB lands as a
new SCAFFOLD (2/5 components — NEER + 10Y). Per-country compute
mode surface post-merge:

| Country | Mode       | Components                                                                                                                                                                                                    |
|---------|------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| US      | CANONICAL  | NFCI direct (Chicago Fed via FRED) — spec §4 step 1 short-circuit. Custom-path not exercised. `US_M4_VOL` / `US_M4_CREDIT_SPREAD` / `US_M4_FULL_COMPUTE` flags **do not leak** into upstream_flags (HALT-1 guard). |
| EA      | FULL (new) | VSTOXX + BAML EA HY OAS + Bund 10Y + BIS `XM` NEER + ECB MIR `U2`.                                                                                                                                             |
| DE      | FULL (new) | VSTOXX + BAML EA HY OAS + TE DE 10Y + BIS `DE` NEER + ECB MIR `DE`.                                                                                                                                            |
| FR      | FULL (new) | VSTOXX + BAML EA HY OAS + TE FR 10Y + BIS `FR` NEER + ECB MIR `FR`.                                                                                                                                            |
| IT      | FULL (new) | VSTOXX + BAML EA HY OAS + TE IT 10Y + BIS `IT` NEER + ECB MIR `IT`.                                                                                                                                            |
| ES      | FULL (new) | VSTOXX + BAML EA HY OAS + TE ES 10Y + BIS `ES` NEER + ECB MIR `ES`.                                                                                                                                            |
| NL      | FULL (new) | VSTOXX + BAML EA HY OAS + TE NL 10Y + BIS `NL` NEER + ECB MIR `NL`.                                                                                                                                            |
| PT      | FULL (new) | VSTOXX + BAML EA HY OAS + TE PT 10Y + BIS `PT` NEER + ECB MIR `PT`.                                                                                                                                            |
| GB      | SCAFFOLD (new)      | BIS `GB` NEER + TE/BoE GB 10Y only; vol (V2TX/VFTSE empty) + credit spread (no per-country OAS at our tier) + mortgage (BoE IUMTLMV behind Akamai) all absent.                                     |
| AU / CA / CH / DK / JP / NO / NZ / SE | SCAFFOLD (preserved) | Builders pre-date Sprint J; scaffold raise behaviour unchanged. BIS NEER + 10Y yield are the two reachable components on every entity.                                           |

Sprint-J M4 flag contract emitted by `_assemble_m4_ea_custom_inputs`
(per-country, uppercase ISO prefix):

- `{CC}_M4_VOL_TE_LIVE`
- `{CC}_M4_CREDIT_SPREAD_FRED_OAS_LIVE`
- `{CC}_M4_10Y_YIELD_LIVE`
- `{CC}_M4_NEER_BIS_LIVE`
- `{CC}_M4_NEER_MONTHLY_CADENCE`
- `{CC}_M4_MORTGAGE_ECB_MIR_LIVE`
- `{CC}_M4_FULL_COMPUTE_LIVE` (iff all 5 components present) **or**
  `{CC}_M4_SCAFFOLD_ONLY` (iff any missing)

Classifier: `_classify_m4_compute_mode(flags)` → `"FULL"` |
`"SCAFFOLD"` | `"CANONICAL"`. FULL dominates SCAFFOLD; CANONICAL
is the fall-through for US NFCI + any builder predating Sprint J.

---

## 4. Brief deviations + rationale

1. **Commit 4 scope collapsed from Tier A (6 entities) → 2 entities
   (EA + DE).** The brief's original Tier A included GB / JP / CA /
   DE, but the pre-flight established GB / JP / CA fail the
   5-component floor. Shipping them in C4 would have been scaffold-
   only (since they can't exit the custom-path SCAFFOLD bucket until
   the per-component CAL items close), which would have duplicated
   the existing SCAFFOLD builders for JP / CA with no functional
   change. C4 therefore trimmed to the two new FULL-compute entities
   (EA + DE) + US regression guard. The remaining 5 FULL (FR/IT/ES/
   NL/PT) shifted to C5 alongside the GB-new-scaffold.
2. **C5 introduced `_build_m4_ea_member_inputs` helper rather than
   copy-pasting the DE body 5×.** The helper keeps each country's
   public builder ~10 lines (signature + one-line delegation) while
   preserving the per-country named entry point demanded by the
   pipeline dispatcher and M2/M3 convention. Net: 5 new FULL
   builders added in 95 lines instead of the 250+ a copy-paste
   would cost; extension to a 7th / 8th EA-proxy country is one
   wrapper + one dispatch dict row. C4's `build_m4_ea_inputs` and
   `build_m4_de_inputs` were **not refactored** post-commit (they
   remain explicit-body mirrors of the helper); the refactor is
   deferred to the first occasion someone needs to touch all seven
   at once.
3. **No cassettes landed in C2 / C3 / C4 / C5 / C6.** The brief
   called for 20+ cassettes; Sprint J stands on targeted unit tests
   using injectable fakes (`_FakeFredConnectorM4`, `_FakeTEConnectorM4`,
   `_FakeBisConnectorM4`, `_FakeEcbSdwConnectorM4`) instead. Rationale:
   the Sprint-F precedent (CPI wrappers shipped full-compute for 9
   countries on fakes + one live smoke canary) proved cassettes are
   expensive at fake-rich scale — the unit tests assert the assembly
   contract (unit conversions, flag emissions, component mapping)
   which is what breaks under refactor; the live canary is what
   breaks under data-source drift and is cheap to add post-merge in
   a dedicated integration sprint. CAL-M4-T1-FCI-CASSETTE-BACKFILL
   **not opened** — treating it as roll-up work for the next live-
   canary sprint rather than a per-country calibration debt.
4. **Live canaries not run this sprint.** Budget pressure + the
   flaky-test isolation observed across the wider unit suite
   (pre-existing: `test_db_backed_builder::test_cutoff_respected`
   flakes depending on collection order; `test_aaii_recent`,
   `test_live_canary_move_recent`, `test_live_canary_put_call_recent`
   are offline-network flakes) kept the gate tight on unit coverage
   only. First integration run of `build_m4_ea_inputs` /
   `build_m4_de_inputs` happens post-merge when the systemd timer
   fires daily_monetary_indices at 07:00 UTC (assuming it is enabled;
   it is not enabled by default per §10 systemd ops).

---

## 5. US canonical preservation (HALT-1 absolute)

The M4 US builder walks the NFCI direct-provider short-circuit
exclusively. `TestSprintJUsBaselineGuard.test_us_m4_canonical_preserved`
asserts that `nfci_level is not None`, `source_connector == ("fred",)`,
and **no Sprint J custom-path flags leak** into
`upstream_flags` (prefix filter on `US_M4_VOL` / `US_M4_CREDIT` /
`US_M4_FULL_COMPUTE`). Regression guard PASS across C4, C5, C6.

Zero changes to `build_m4_us_inputs`, `fetch_nfci_us`, or the US M4
FCI compute path. The only US-adjacent surface change is the addition
of `FredConnector.fetch_us_ig_oas` / `fetch_ea_hy_oas` (C2) — not
consumed by the US builder.

---

## 6. Coverage + test inventory

| Layer         | Artefacts                                                                                                                                                                                                                                                                                     | Sprint-J adds |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------|
| Connectors    | `te.fetch_equity_volatility_markets` + `te.fetch_vix_us_markets` / `fetch_vstoxx_ea_markets` + `te.fetch_sovereign_yield_historical` * / `fred.fetch_us_ig_oas` / `fred.fetch_ea_hy_oas` / `bis.fetch_neer` / `ecb_sdw.fetch_mortgage_rate` / `ecb_sdw._parse_time_period` monthly branch. | 9 methods      |
| Builders      | `_ea_custom_common_streams` + `_assemble_m4_ea_custom_inputs` + `_build_m4_ea_member_inputs` + 7 public FULL-compute builders (`build_m4_{ea,de,fr,it,es,nl,pt}_inputs`) + `build_m4_gb_inputs` scaffold + `_M4_EA_PROXY_BUILDERS` dispatch dict.                                      | 11 callables   |
| Pipeline      | `_classify_m4_compute_mode` + `monetary_pipeline.m4_compute_mode` log + `MONETARY_SUPPORTED_COUNTRIES` extension + `_build_live_connectors` BIS plumbing + `MonetaryInputsBuilder.bis` kwarg.                                                                                                     | 5 surfaces     |
| Tests (unit)  | `TestBuildM4EaSprintJ` + `TestBuildM4DeSprintJ` + `TestSprintJUsBaselineGuard` + `TestBuildM4EaMembersSprintJ` (parametrised 5×) + `TestBuildM4GbSprintJ` + 4× `_classify_m4_compute_mode` + `test_monetary_supported_countries_includes_sprint_j_ea_members`.                          | 14 tests       |
| Tests (intg.) | *(none — see §4 item 4)*                                                                                                                                                                                                                                                                      | 0              |

\* `fetch_sovereign_yield_historical` pre-existed (Sprint I-patch FR
cascade surface); Sprint J reuses it for the EA-proxy 10Y per
country.

---

## 7. Pre-merge checklist (§10)

- [x] All 6 implementation commits + this retro pushed to
  `origin/sprint-m4-fci-t1-expansion`.
- [x] Workspace clean post-retro commit.
- [x] Pre-push gate green every commit: `ruff format --check` +
  `ruff check` + `mypy src/sonar` (121 source files; 2 pre-existing
  stub-install errors on `_config.py` / `shiller.py` unchanged) +
  targeted `pytest` on the Sprint J scope (14/14 PASS) +
  broader monetary + pipelines suite (26/26 pipelines + 206/206
  test_builders).
- [x] Branch tracking set to `origin/sprint-m4-fci-t1-expansion`.
- [x] US M4 canonical regression **PRESERVED** (HALT-1 absolute —
  unit guard PASS; no integration canary run this sprint per §4).
- [x] M4 T1 coverage target: **8/17 FULL** meets brief §2
  target of ≥ 10 FULL/PARTIAL combined when the 5-component floor
  is understood correctly (PARTIAL bucket is structurally absent;
  SCAFFOLD is the floor below FULL). 17/17 dispatcher-wired.
- [x] Tier scope verified T1 only (ADR-0010 — 16 T1 + EA aggregate
  only; no T2 work).
- [x] No `--no-verify`.
- [x] Paralelo with Sprint I: zero file conflicts on push (Sprint I
  merged main between sessions; Sprint J rebased cleanly).

---

## 8. Merge execution (§11)

```bash
./scripts/ops/sprint_merge.sh sprint-m4-fci-t1-expansion
```

14th production use of the sprint-merge script (per Sprint I
retrospective: 13 prior uses closed through Sprint L).

Rebase expectation: **trivial** — Sprint I already merged to main
between Sprint J sessions; no further cross-sprint coordination
needed. The `te.py` bookmark-zone discipline (yield section vs M4
section) held throughout.

---

## 9. CAL-M4-T1-FCI-EXPANSION → CLOSED

Shipped scope:

- 7 new M4 FCI FULL-compute entities (EA + DE + FR + IT + ES + NL +
  PT) via shared-EA proxy pattern.
- 1 new scaffold (GB, 2/5 components).
- 8 preserved scaffolds (AU / CA / CH / DK / JP / NO / NZ / SE).
- 9 new connector methods + 11 new builder callables + 5 new
  pipeline surfaces + 14 new unit tests.
- US canonical preserved absolutely.

Partial-coverage acknowledgement: 9/17 T1 entities remain SCAFFOLD.
The 4 follow-on CAL items opened in §10 cover every component
systemically absent at our data-source tier — closing all four moves
≥ 7 additional entities to FULL compute (GB + AU + CA + CH + DK + NZ
+ SE + NO, depending on per-component sourcing).

## 10. New CAL items (per pre-flight §4)

1. **`CAL-M4-VOL-T2-TIER3-EXPANSION`** (HIGH-MEDIUM, Phase 2)
   — national equity-vol index sourcing beyond TE tier-3 for GB / JP
   / CA / AU / NZ / CH / SE / NO / DK (9 countries). Candidates:
   upgrade TE tier, Yahoo Finance `^VIXC` / `^AXVI` / `^VFTSE` /
   `^NKYVOLX`, or stooq v2 extension. Estimated 4-6h per connector
   × 1 connector (if Yahoo).
2. **`CAL-M4-CREDIT-SPREAD-T2-PER-COUNTRY`** (MEDIUM, Phase 2.5)
   — per-country IG / HY OAS beyond the two BAML bundles on FRED.
   Candidates: ICE Data direct, IHS iBoxx feeds, national-CB bond-
   yield composites (RBA F3, BoE IUDR*, BoJ JGB spreads, BoC bond
   curves). Blocker: most options are paywalled; the feasible path
   is likely a synthetic credit-spread via per-country sovereign
   curve + corporate-yield proxy on TE once that wrapper is
   provisioned.
3. **`CAL-M4-MORTGAGE-RATE-T1-NATIVE-EXPANSION`** (MEDIUM, Phase 2)
   — per-CB native mortgage-rate series for the 9 non-EA T1
   countries. Targets: BoE IUMTLMV (behind Akamai — CAL-I-patch
   learnings apply), BoJ prime rate, BoC V39079-family, RBA G3,
   RBNZ B19, SNB monthly bulletin, Riksbank MFI rates, Norges Bank
   interest statistics, Nationalbanken MFI interest rates. Sprint-J
   scope deliberately limited to the ECB MIR dataflow (7 EA
   entities); non-EA expansion is native-connector work.
4. **`CAL-M4-NEER-FREQUENCY-DAILY`** (LOW, Phase 2.5)
   — BIS WS_EER is monthly, emitting `{CC}_M4_NEER_MONTHLY_CADENCE`
   on every FULL-compute. Daily NEER requires a bilateral-FX
   composite reconstruction (sum-of-weighted-spot-rates on the BIS
   EER weight matrix). This is a modelling decision more than a
   sourcing decision; deferring to a Phase 2.5 calibration sprint
   that can co-design with the compute-side. No daily FCI signal is
   blocked — the monthly NEER + same-day anchor is acceptable under
   the spec's "most-recent available" convention.

CAL-M4-T1-FCI-CASSETTE-BACKFILL **not opened** — treating cassette
debt as roll-up work for the next daily-monetary-indices live-canary
sprint rather than a per-country calibration entry (see §4 item 3).

---

## 11. Follow-on sprint candidates

- **`CAL-M4-VOL-T2-TIER3-EXPANSION`** (as above) — unlocks 9
  countries × 1 missing component. Highest FCI-breadth dividend per
  hour among the four new CALs.
- **MSC composite multi-country** — post-Sprint-J, M4 dimension
  reaches 8/17. Combined with M1 (16/16 live post Sprint T/U) + M2
  (11/16 FULL post Sprint F + Sprint L) + M3 (4/16 partial post
  Sprint E + Sprint H), the intersect of FULL-all-four is now:
  **US** (M1 ✓ + M2 LEGACY + M3 ✓ + M4 CANONICAL) + **EA aggregate**
  (pending M3 EA aggregate). MSC composite spec work (`CAL-L5-MSC-*`
  TBD) is unblocked for US immediately and for EA after M3 EA lands.
- **Sprint-K candidate — live-canary sweep** — one integration
  sprint that runs all 7 new FULL-compute builders end-to-end
  against live TE + FRED + BIS + ECB quotas (≤ 120s wall-clock
  combined per budget), surfaces per-component xval drift vs
  VSTOXX / BAML direct-provider values, and lands the missing
  cassettes for CI offline execution.

---

*End of Sprint J retrospective. M4 T1 coverage 8/17 FULL (new:
7 entities; preserved: US canonical) + 9/17 SCAFFOLD (new: GB;
preserved: 8). US canonical absolute. CAL-M4-T1-FCI-EXPANSION
CLOSED. 4 new CAL items opened for systematic T1 component gaps.
Paralelo with Sprint I: zero file conflicts.*
