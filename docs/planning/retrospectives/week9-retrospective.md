# Week 9 Retrospective — Completionist M2 T1 Arc

**Period**: 2026-04-21 → 2026-04-22 (Day 1 → Day 5)
**Theme**: M2 T1 country completionism + first production natural-fire observations
**Status**: CLOSED (pending Sprint Y-DK merge — see §10 Deviations)
**Total sprints**: 10 (8 connector / fix + 1 DK pending + this meta)
**Total Week 9 commits (at time of writing)**: 50 on `main`
  (excluding Sprint Y-DK and this Sprint Z retro)
**M2 T1 progression**: 8 → 12 countries M1 live (plus DK pending → 13; or 16
  after counting EA-periphery PT/IT/ES/FR/NL already live via the Week 5-6
  EA path)
**Artifact base directory**:
  `docs/planning/retrospectives/week9-*-report.md` (8 sprint retros shipped)

---

## 1. Executive summary

Week 9 closed the advanced-economy monetary M1 arc. In five days SONAR
absorbed six native-CB connectors (BoC, RBA, RBNZ, SNB, Riksbank, Norges
Bank), one legacy-fix migration (BIS SDMX v2), one ISO-3166 rename sweep
follow-up (CAL-128-FOLLOWUP overlay/cycle UK→GB), and its first
production natural-fire cycle since the Week 8 Sprint N systemd
deployment. The TE-primary cascade shape (Sprint I-patch, Week 8) held
across every country expansion without structural deviation; the flag
vocabulary grew by one new axis (post-resolution value-attached
augmentation, i.e. `{CH,SE}_NEGATIVE_RATE_ERA_DATA`) but the routing
contract (TE → native → FRED) stayed invariant.

Two live outages surfaced via systemd timers rather than mocked tests.
BIS credit-indices went silent ~7 days because `DEFAULT_LOOKBACK_DAYS=90`
intersected the BIS ~2-quarter publication lag — the v2 URL migration
had already landed Week 8; the window default was stale. Sprint AA
resolved in ~2h. Day 4 07:00 WEST revealed `daily_curves` still
hardcoded `--country US` from Week 2 scope; CAL-138 is Week 10 P1
because it blocks the overlay + cost-of-capital cascade for 6 T1
countries.

Merge workflow discipline was tested three times (Sprint S-CA Day 1,
V-CH Day 3, W-SE Day 4). The pattern that emerged is unsentimental:
sequential merge → verify → push → only then cleanup. Day 4 W-SE
recovery (orphaned branch after bulk cleanup script) was the last
instance — lesson now load-bearing in the concurrency protocol.

## 2. Day-by-day breakdown

### Day 1 (2026-04-21 morning → afternoon) — Foundation expansion

- **Sprint P** (6 commits / ~1h) — CAL-128-FOLLOWUP UK→GB canonical
  sweep on four consumer surfaces (`cycles/financial_fcs.py`,
  `overlays/crp.py`, `overlays/live_assemblers.py`,
  `pipelines/daily_cost_of_capital.py`). Strict 4-file scope held;
  backward-compat aliases via module-local `_DEPRECATED_COUNTRY_ALIASES`
  + `_normalize_country_code()` emit structlog deprecation warnings.
  Alias removal scheduled Week 10 Day 1 per ADR-0007.
- **Sprint S-CA** (6 commits / ~2h45m) — BoC Valet public JSON REST
  connector + M1 CA cascade. First reachable native in the cascade
  family (contrast BoE / BoJ / RBNZ gated). Net side-fix during live
  canary: `FRED_SERIES_TENORS` missing GB/JP/CA OECD mirror entries;
  JP FRED-fallback silently broken at `main` HEAD — closed in same
  commit.
- Parallel worktrees, disjoint files, zero collision.
  `calibration-tasks.md` append-only union at merge.

### Day 2 (evening → next morning) — Production fire + Australia

- **Sprint AA** (6 commits / ~1h55m) — BIS v2 migration fix. Empirical
  audit revealed the URL migration had *already* landed Week 8 commit
  `7abded7`; real blocker was `DEFAULT_LOOKBACK_DAYS=90` intersecting
  BIS ~2-quarter publication lag. Bumped to 540 so every window
  overlaps ≥ 4 published quarters. Co-landed parser regression-lock,
  3 representative cassette refreshes, and an `httpx.AsyncClient`
  teardown fix (two sibling `asyncio.run()` calls bound to different
  loops). Systemd timer enable deferred to operator. **CAL-136 CLOSED**,
  **CAL-137 OPEN** (weekly BIS canary).
- **Sprint T-AU** (6 commits / ~3h) — RBA statistical-tables CSV
  connector + M1 AU cascade. First CSV-shaped native. Akamai-edge
  UA gate: `Mozilla/5.0` returns 403, descriptive `SONAR/2.0` clears
  — new pre-flight lesson captured for static-publication connectors.

### Day 3 — Hemisphere + first negative rates

- **Sprint U-NZ** (6 commits / ~2h) — RBNZ B2 CSV scaffold + M1 NZ
  cascade. First perimeter-blocked native: 403 `Website unavailable`
  on *every* path under *every* UA (including `/robots.txt`) — block
  is host/IP-scoped, likely geo/ASN. Connector ships wire-ready; day
  the host unblocks, cascade resumes without code change.
  CAL-NZ-RBNZ-TABLES tracks operator remediation. NZ FRED-fallback
  canary surfaced another missing `FRED_SERIES_TENORS` entry — Sprint
  S lesson applied in-commit.
- **Sprint V-CH** (6 commits / ~3h) — SNB portal semicolon-CSV +
  M1 CH cascade; **first negative-rate country**. 93 strictly-negative
  TE obs (floor -0.75%, 2014-12 → 2022-08). Preservation contract
  unit-tested at three layers (TE wrapper, SNB parse, cascade
  aggregation). Non-obvious: SNB has **no dedicated policy-rate
  cube** — ~20 candidates probed, all 404; `zimoma`/SARON serves as
  monthly proxy with explicit `CH_POLICY_RATE_SNB_NATIVE_MONTHLY`
  qualifier. FRED CH mirror ~2y stale. Known ZLB compute gap:
  `compute_m1_effective_rates` raises `InsufficientDataError` at
  negative rates (Krippner shadow-rate not wired; spec §4 step 2).
  Cascade contract complete; M1 compute will consume unchanged once
  Krippner lands Phase 2+.

### Day 4 — Nordics + second production natural fire

- **Sprint W-SE** (6 commits / ~3h) — Riksbank Swea JSON REST + M1
  SE cascade. Second negative-rate country (58 rows, floor -0.50%,
  2015-02 → 2019-12). **First daily-cadence native secondary** —
  SECBREPOEFF matches TE's daily cadence; no `*_MONTHLY` qualifier.
  Two SE-specific concerns: (a) FRED OECD SE mirror
  (`IRSTCI01SEM156N`) *discontinued 2020-10-01*, ~5.5 years frozen;
  (b) no SE anchor exists where FRED-live ∩ Riksbank > ZLB.
  FRED-fallback canary restructured to assert on `inputs.m1`
  pre-compute.
- **Sprint X-NO** (6 commits / ~3h) — Norges Bank DataAPI SDMX-JSON
  + M1 NO cascade. First SDMX-JSON native; cube discovery trivial
  (dedicated `IR/B.KPRA.SD.R` dataflow — contrast SNB's
  no-cube pattern). First fully-positive cascade (min 0% during
  2020-05 → 2021-09 COVID trough); no negative-rate flag attached.
  YAML 1.1 boolean gotcha: unquoted `NO:` parses as Python `False`;
  quote-defensive convention now documented in-file.
- **Production fire #2** — Day 4 07:00 WEST: `daily_curves` rejected
  `--country != US` with `EXIT_IO`; service attempted `--all-t1`
  unsupported by CLI; pipeline reverted US-only. Phase 1 Week 2
  scope never expanded. **CAL-138 OPEN** (HIGH) — unblocks overlay +
  cost-of-capital cascade for 6 T1 countries.

### Day 5 (2026-04-22) — Closure

- **Sprint Y-DK** — Nationalbanken + M1 DK cascade; third
  negative-rate + first EUR-peg country (floor -0.75%, 2012-07 →
  2022-09 — deepest and longest G10 corridor). **Status: in flight
  in `sonar-wt-sprint-y` at time of writing.** Matrices in §4 carry
  "PENDING" placeholders; Sprint Z rebases post-merge.
- **Sprint Z-WEEK9-RETRO** — this document.

## 3. Sprint summary table

| Sprint | Task | Commits | Duration | Key finding |
|---|---|---|---|---|
| P | CAL-128-FOLLOWUP (overlay/cycle UK→GB) | 6 | ~1h | Strict 4-file scope held; 7 alias-consuming entry points preserved until Week 10 Day 1 removal |
| S-CA | Canada BoC Valet + M1 | 6 | ~2h45m | First reachable native (public JSON REST); JP FRED-fallback silently broken at `main` HEAD, fixed net-positive |
| AA | BIS SDMX v2 migration fix | 6 | ~1h55m | URL migration was already landed; real blocker was 90d lookback vs 2-quarter publication lag — bumped to 540d |
| T-AU | Australia RBA CSV + M1 | 6 | ~3h | RBA Akamai edge 403s bare `Mozilla/5.0`; `SONAR/2.0` descriptive UA clears |
| U-NZ | New Zealand RBNZ scaffold + M1 | 6 | ~2h | Perimeter-blocked (host/IP scope) — 403 on every path and every UA; connector ships wire-ready |
| V-CH | Switzerland SNB + M1 (first neg-rate) | 6 | ~3h | SNB has no dedicated policy-rate cube; SARON serves as monthly proxy; 93 neg obs; ZLB compute gap surfaced |
| W-SE | Sweden Riksbank Swea + M1 (2nd neg-rate, daily native) | 6 | ~3h | First daily-cadence native secondary; FRED OECD SE discontinued 2020-10-01 |
| X-NO | Norway Norges Bank SDMX-JSON + M1 | 6 | ~3h | First SDMX-JSON native; first fully-positive cascade; YAML 1.1 `NO` bareword gotcha |
| Y-DK | Denmark Nationalbanken + M1 (3rd neg-rate, EUR-peg) | *PENDING* | *PENDING* | Placeholder — Sprint Y-DK in flight at time of writing |
| Z | This meta-retro | 2-4 | ~2-3h | Week 9 synthesis + pattern consolidation |
| **TOTAL** | | **~50-58** | **~24h active CC time across parallel worktrees** | |

## 4. Pattern matrices

### 4.1 Native-connector outcome matrix (9 countries — GB/JP + Week 9)

| Country | Native | Shape | Outcome | Notes |
|---|---|---|---|---|
| GB | BoE IADB | CSV (Akamai-gated) | GATED | Scaffold; intermittently Akamai-rejected — wire-ready only (Week 8 Sprint I) |
| JP | BoJ TSD | HTML (browser-gated) | GATED | Scaffold; browser-gated — wire-ready only (Week 8 Sprint L) |
| CA | BoC Valet | JSON REST | SUCCESS | Public, no auth, V39079 overnight target; first reachable native |
| AU | RBA F1/F2 tables | static CSV | SUCCESS | UA-gated (Akamai); SONAR/2.0 descriptive UA clears |
| NZ | RBNZ B2 tables | CSV | BLOCKED | Host/IP perimeter 403 on every path and every UA; connector ships wire-ready |
| CH | SNB data portal | semicolon-CSV | PARTIAL | `zimoma` (SARON) + `rendoblim` reachable; no dedicated policy-rate cube — SARON serves as monthly proxy |
| SE | Riksbank Swea | JSON REST | SUCCESS | First daily-cadence native; catalogue endpoint `/Series` exposed |
| NO | Norges Bank DataAPI | SDMX-JSON | SUCCESS | First SDMX-JSON; dedicated `IR/B.KPRA.SD.R` dataflow; daily parity |
| DK | Nationalbanken | *PENDING* | *PENDING* | Sprint Y-DK |

**Aggregate (9 countries)**: 4 SUCCESS / 1 PARTIAL / 1 BLOCKED / 2 GATED / 1 PENDING.
The TE-primary cascade worked for **all** 9 countries; the native-secondary
slot is where the shape variance lives. Native reachability was roughly
**5/9** (counting CH as reachable-but-proxied) by Week 9 close —
substantially better than expected given GB + JP had set the pre-week
baseline at 0/2.

### 4.2 Negative-rate country matrix (3 countries, DK pending)

| Country | Floor | Duration | Obs (TE) | Flag | Notes |
|---|---|---|---|---|---|
| CH | -0.75% | 2014-12-18 → 2022-08-31 (93 months) | 93 | `CH_NEGATIVE_RATE_ERA_DATA` | Deepest corridor; SNB direct policy-rate target |
| SE | -0.50% | 2015-02-12 → 2019-11-30 (58 months) | 58 | `SE_NEGATIVE_RATE_ERA_DATA` | Shallower corridor; Riksbank repo-rate-then-policy-rate rename 2022-06-08 |
| DK | -0.75% | 2012-07-06 → 2022-09-23 (*approx 10y*) | *PENDING* | `DK_NEGATIVE_RATE_ERA_DATA` (projected) | First G10 negative-rate country; EUR-peg defense context |

All three share the same Phase-1 operational gap: at negative or sub-ZLB
rates, `compute_m1_effective_rates` raises `InsufficientDataError` because
the Krippner / Wu-Xia shadow-rate connector is not wired. Cascade preserves
sign through every layer; M1 compute declines gracefully. Phase 2+
CAL-KRIPPNER (née CAL-099) will unblock all three simultaneously.

### 4.3 Cascade flag emission matrix (per country, post-Week-9)

Common pattern for every country: TE-primary depth emits
`{CTRY}_{RATE}_TE_PRIMARY`; native depth emits `{CTRY}_{RATE}_{SRC}_NATIVE`
(+ `_MONTHLY` qualifier iff native cadence is monthly); FRED depth emits
`{CTRY}_{RATE}_FRED_FALLBACK_STALE` + `CALIBRATION_STALE`. Cross-cutting
flags `R_STAR_PROXY`, `EXPECTED_INFLATION_CB_TARGET`,
`{CTRY}_BS_GDP_PROXY_ZERO` fire on every persisted row regardless of
source depth.

Country-specific deltas:

- **CA** (BoC Valet) — daily native parity, no cadence qualifier.
- **AU** (RBA F-tables) — daily-ish via static CSV, no qualifier.
- **NZ** (RBNZ B2) — native currently `NZ_OCR_RBNZ_UNAVAILABLE` (perimeter
  block); post-unblock becomes `NZ_OCR_RBNZ_NATIVE`.
- **CH** (SNB zimoma/SARON) — monthly native → `CH_POLICY_RATE_SNB_NATIVE` +
  `CH_POLICY_RATE_SNB_NATIVE_MONTHLY`. Extra cross-cuttings:
  `CH_INFLATION_TARGET_BAND`. **Post-resolution**:
  `CH_NEGATIVE_RATE_ERA_DATA` when resolved window contains any
  negative obs.
- **SE** (Riksbank Swea SECBREPOEFF) — daily native parity, no
  qualifier. **Post-resolution**: `SE_NEGATIVE_RATE_ERA_DATA`.
- **NO** (Norges Bank IR dataflow) — daily native parity, no qualifier,
  no neg-rate flag (positive-only history).
- **DK** (Nationalbanken) — *PENDING*; projected cross-cutting extension
  `DK_INFLATION_TARGET_IMPORTED_FROM_EA` (EUR-peg semantics).

Invariants confirmed Week 9: (a) FRED-depth flag pair is uniform across
every country; (b) cross-cuttings fire regardless of source depth;
(c) **post-resolution augmentation flags are a new primitive** — attach
to *value*, not *source*, so all three cascade depths emit them. Extends
cleanly to `DK_NEGATIVE_RATE_ERA_DATA` and to any future post-resolution
concern (`X_OUTLIER_DETECTED`, `X_REGIME_CHANGE_SUSPECTED`).

## 5. Lessons learned

1. **Merge and cleanup are separate verbs.** Three Week 9 rebase
   incidents (Sprint S-CA Day 1, V-CH Day 3, W-SE Day 4) traced to
   bundled merge-and-cleanup shell scripts: when the merge conflicts,
   the cleanup runs anyway and orphans the branch. W-SE recovery
   required reflog + worktree recreation (~45 min). Rule: merge →
   verify exit code + remote state → push → only then cleanup. Never
   mix. Load-bearing in future parallel brief §12 merge strategies.

2. **CC delegation for mechanical rebase is cheap and correct.**
   Union-merge rebases across 5-9 append-zone files (`te.py`,
   `builders.py`, `daily_monetary_indices.py`, two YAMLs,
   `calibration-tasks.md`) are exhausting manually but trivially
   correct via delegation: "preserve every entry from both branches,
   re-sort `__all__` alphabetically, keep country-key order stable."
   V-CH and W-SE rebases each took ~15-25 min CC wall-clock.

3. **Production first-natural-fire = discovery goldmine.** Week 9 ran
   the first live cascade since Week 8 Sprint N's systemd deployment.
   Two latent issues surfaced that mocked tests could not see: BIS
   90d lookback vs 2-quarter publication lag (silent outage
   ~2026-04-14 → 2026-04-21; detected Day 2), and `daily_curves`
   US-only scope (Day 4 07:00 WEST). Systemd-driven live canary is
   now the only end-to-end gate; CAL-137 opens the weekly BIS
   surveillance timer.

4. **Empirical probe supersedes brief heuristic, every single time.**
   Week 9 produced five instances: BoC V122544 → `BD.CDN.10YR.DQ.YLD`
   (S), RBA Akamai UA gate (T), SNB no-dedicated-policy-rate-cube →
   SARON proxy (V), Riksbank rename preserves `SWRRATEI` (W-SE), YAML
   1.1 `NO` bareword → `False` (X-NO). Rule: reserve first 15-20
   minutes of each sprint for probes; budget brief deviations as
   expected, not exceptional.

5. **TE-primary cascade is canonical and battle-tested.** Six
   consecutive country expansions via the Sprint-I-patch pattern
   (TE primary → native → FRED). Zero structural deviation; zero
   source-drift-guard false positives across all six
   (`HistoricalDataSymbol` for CCLR / RBATCTR / NZOCRS / SZLTTR /
   SWRRATEI / NOBRDEP held stable). ~3 hours per country end-to-end
   incl. @slow live canaries. Load-bearing for DK Sprint Y and any
   Phase 2+ EM expansion.

6. **Pattern replication velocity — cognitive overhead collapses, not
   wall-clock.** S-CA (Day 1) ~2h45m; V-CH (4th iteration) ~3h; W-SE
   (6th iteration) ~3h. Wall-clock floor ~2h because live canary runs
   dominate the back-half. What *does* collapse is cognitive overhead:
   by iteration 5+ the brief-deviation list is mostly mechanical
   probe-vs-heuristic items, not structural surprises. Correct shape
   of template maturity.

7. **Post-resolution augmentation flag — new cascade-vocabulary
   primitive.** Prior Week 9, all cascade flags were routing-attached
   (`{COUNTRY}_{SOURCE}_{ROLE}`). Sprint V introduced
   `CH_NEGATIVE_RATE_ERA_DATA` — first *value*-attached flag, fires at
   any cascade depth when the resolved window contains a negative
   observation. Sprint W-SE generalised with `SE_NEGATIVE_RATE_ERA_DATA`;
   Y-DK will extend. Primitive generalises to any post-resolution
   regime concern (`OUTLIER_DETECTED`, `REGIME_CHANGE_SUSPECTED`);
   downstream consumers read flags as route-attached or value-attached.

8. **Cassette refresh co-lands with API migrations.** Sprint AA's
   audit found Week 8 `7abded7` migrated BIS to SDMX v2 URLs but left
   old cassettes + alternate `application/json` Accept header +
   `format=jsondata` behind. None functionally broken, but the
   half-done migration made the real lookback bug invisible. Rule:
   any commit bumping an API surface refreshes cassettes in-commit,
   or the next retrospective pays the cost.

## 6. CAL evolution

Sources: `docs/backlog/calibration-tasks.md` + `git log docs/backlog/calibration-tasks.md`.

| Milestone | Count | Delta |
|---|---|---|
| Week 7 close (Phase 1 M1-US milestone) | 62 | — |
| Week 8 close (Sprint L BoJ + Sprint O GB/UK rename) | 74 | +12 |
| Week 9 close (current, pre-Sprint-Y-DK) | 120 | +46 |
| Week 9 close (projected, post-Y-DK) | ~127 | ~+53 |

Week 9 explicit closures (full):

- **CAL-128** — UK → GB canonical rename (Sprint chore commits sweep
  complete, commit `178fc6b`).
- **CAL-128-FOLLOWUP** — UK → GB overlay / cycle / cost-of-capital
  consumer surfaces (Sprint P, 4-file strict scope).
- **CAL-136** — BIS SDMX v2 URL + Accept header migration formalisation
  (Sprint AA; note: the migration itself had already shipped in Week 8
  commit `7abded7`, Sprint AA closed the residual Accept/format/cassette
  loose ends and the lookback-lag root cause).

Week 9 partial closures (parent CAL entries opened at M1-level, sub-CALs
opened for M2/M4/M3 follow-through):

- **CAL-129** (CA), **CAL-AU** (AU), **CAL-NZ** (NZ), **CAL-CH** (CH),
  **CAL-SE** (SE), **CAL-NO** (NO) — six countries live at M1 level,
  M2+M4 as wire-ready scaffolds raising `InsufficientDataError`, M3
  deferred. DK (**CAL-DK**, projected) extends this to seven partial
  closures once Sprint Y-DK merges.

Week 9 new openings — M1-country-expansion sub-CALs, uniform shape
per country (M2 output-gap, M4 FCI 5-component bundle, M3 market-
expectations overlays, BS/GDP ratio, CPI YoY wrapper, inflation-
forecast wrapper):

- **CA** CAL-130..135 (6); **AU** CAL-AU-* (6); **NZ** CAL-NZ-* (7 —
  adds CAL-NZ-RBNZ-TABLES perimeter-block remediation); **CH**
  CAL-CH-* (6); **SE** CAL-SE-* (6); **NO** CAL-NO-* (6).
- **Infra/production**: CAL-137 (weekly BIS canary), CAL-138
  (daily_curves multi-country — HIGH, Week 10 P1).
- **Projected Y-DK**: CAL-DK-* (~6-7 items).

Not opened Week 9 (deferred): CAL-KRIPPNER (shadow-rate connector)
documented as Phase 2+ in Sprint V-CH §11 and Sprint W-SE §11.1;
surfaces formally when L5 regime-classifier work resumes — unblocks
CH + SE + DK ZLB compute simultaneously.

## 7. Production deployment findings

Week 8 Sprint N wired the nine daily pipelines to systemd
(`deploy/systemd/`) but deferred enablement. Early Week 9 operator
enablement triggered the first live cascade cycle. Schedule recap
(UTC): 05:00 bis-ingestion → 06:00 curves → 06:30 overlays → 07:00
four indices in parallel (economic / monetary / financial / credit) →
08:00 cycles → 08:30 cost-of-capital. DAG via `After=` (not
cascade-fail; partial success OK).

**Functional**: `daily_bis_ingestion` (post-Sprint-AA, 21/21
fetches; `bis_credit_raw` holds 672 WS_TC + 49 WS_DSR + 49
WS_CREDIT_GAP); `daily_curves` (US-only, blocks 6 T1 overlays per
CAL-138); `daily_monetary_indices` (12 countries M1 live post-X-NO
= 7 EA-periphery + GB + JP + CA + AU + NZ + CH + SE + NO; DK adds
13th pending Y-DK); `daily_credit_indices` (L1 + L2 for 7 T1; L3/L4
per CAL-059/060); `daily_economic_indices`, `daily_financial_indices`,
`daily_cycles` (L1 per spec; F-cycle canary backfill CAL-071 OPEN).

**Partial / blocked**: `daily_overlays` (blocked by curves US-only —
CAL-138 dependency); `daily_cost_of_capital` (blocked transitively);
L5 integration landed Week 8 Sprint K but composite paths downstream
of overlays.

**Mean-time-to-detect**: BIS outage ran silently ~7 days (detected
via Sprint S-CA operator triage, not automation — CAL-137 closes
this gap). `daily_curves` US-only surprise detected in ~12 hours
(Day 3 enable → Day 4 07:00 WEST fire). Sprint AA deferred
`systemctl enable --now` for bis-ingestion / credit-indices to
operator (CC lacks passwordless sudo); one-line post-merge action.

## 8. Week 10+ priorities

1. **P1 — CAL-138** `daily_curves` multi-country support (HIGH).
   Unblocks overlay + cost-of-capital cascade for 6 T1 countries
   (DE / PT / IT / ES / FR / NL). Extends `run_us()` pattern using
   Eurostat + ECB SDW + BIS yield sources already wired Weeks 5-6.
   Expected ~1 sprint (~4-6h).
2. **P2 — ADR-0007 alias removal** (Week 10 Day 1). Strip
   `_DEPRECATED_COUNTRY_ALIASES` + `_normalize_country_code()` from
   all Sprint O + P + chore surfaces in one atomic commit; remove
   `scripts/backfill_l5.py:93` UK comment. ~1-2h.
3. **P3 — CAL-060 BIS L4 DSR + CAL-059 Credit Impulse L3** (MEDIUM).
   Closes the L3/L4 credit-indices gap currently
   DbBackedInputsBuilder-out-of-scope.
4. **P4 — CAL-KRIPPNER shadow-rate connector** (MEDIUM). Unblocks M1
   compute at ZLB / negative rates for CH + SE + DK (and retroactively
   US pre-2015). Can land earlier if full-HLW r* work (CAL-095) shares
   a connector shape.
5. **P5 — F-cycle canary backfill** (CAL-071, OPEN). MOVE / AAII / COT
   live sources closed Week 4 (CAL-068/069/070) but canary coverage
   wasn't backfilled.
6. **P6 — L5 regime-classifier full integration**. Classifier scaffold
   + CLI wiring shipped Week 8 Sprint H/K; overlay + cycle composites
   still compose against L4. Phase 2+ Week 10-11 candidate.

## 9. Concurrency protocol — self-retrospective

Eight parallel isolated worktrees (`sonar-wt-sprint-*`), zero
filesystem collisions. Shared-file append zones rebased cleanly with
append-only discipline + alphabetical `__all__` sort convention. Sole
failure mode — bundled merge-and-cleanup — addressable by discipline
(§5 Lesson 1). The alphabetical merge-priority rule (earlier letter
first, later rebases) held except when stale-state considerations
recommended otherwise; operator decides specific order at each merge
window. Rule is a guideline, not a contract.

## 10. Deviations from the brief

1. **Sprint Y-DK not yet merged at draft time** — per brief §5 HALT
   trigger #0, Z proceeded with placeholders for the Y-DK row + DK
   column in matrices §4.1-4.3. Post-Y-DK merge, a follow-up commit
   updates cells + M2 T1 total (12 → 13; or 16 counting EA-periphery).
2. **SESSION_CONTEXT.md scope limited** — CLAUDE.md §8 declares the
   file external to repo; brief §4 requests in-repo updates. Z ships
   the Week 9 close snapshot at repo root as a proposal Hugo can merge
   against his external copy. Retro + README are the canonical in-repo
   artifacts; SESSION_CONTEXT updates are advisory.
3. **Commit count 3 vs brief §4's 4** — incremental writes to a single
   docs file produce no useful review seam; Z ships retro / README /
   SESSION_CONTEXT as three separate commits, within brief §1's `~2-4`
   range.
4. **Sprint AA systemd timer enablement deferred** (also documented in
   AA retro §1 + §7). Operator action post-merge.

## 11. HALT triggers (Sprint Z scope)

All 11 atomic triggers from brief §5 evaluated. None fired as HALT;
triggers 0 (Y-DK not yet shipped), 3 (SESSION_CONTEXT scope), and 4
(README.md minor conflict) surfaced as documented-deviations rather
than HALTs per brief clause.

## 12. Closing banner

```
SPRINT Z WEEK 9 RETROSPECTIVE DRAFTED: 3 commits on sprint-z-week9-retro
Week 9: 9 sprints (P + S-CA + AA + T-AU + U-NZ + V-CH + W-SE + X-NO +
  this); Y-DK in flight
M2 T1 progression: 8 → 12 countries M1 live (pre-Y-DK), projected 13
  post-Y-DK (16 incl. EA-periphery)
Total Week 9 commits at draft time: 50
CAL: ~46 opened / 3 full + 6 partial closures (projected ~53 / 3 + 7
  post-Y-DK)
Lessons: 8 distinct | Matrices: 3 | Production fires remediated: 2
Merge: git merge --ff-only sprint-z-week9-retro (rebase expected if
  Y-DK merges first — union-merge at README + calibration-tasks)
Artifact: docs/planning/retrospectives/week9-retrospective.md
```
