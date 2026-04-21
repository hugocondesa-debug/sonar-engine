# Week 9 Sprint U-NZ — NZ RBNZ Connector + M1 NZ TE-primary Cascade — Implementation Report

## 1. Summary

- **Duration**: ~2h wall-clock, single session (within 3-4h budget).
- **Commits**: 5 shipped to branch `sprint-u-nz-connector` (C1 TE
  wrapper → C2 RBNZ connector → C3 NZ YAML → C4 M1 NZ cascade +
  M2/M4 scaffolds → C5 pipeline wiring + FRED OECD NZ extension +
  integration canaries). Brief budgeted 6-8 commits; C4 bundled M1
  cascade + M2/M4 scaffolds per the same rationale as Sprint S/T
  (one atomic logical change — facade dispatch + `__all__` + fakes
  share a seam), and the retrospective lands as C6 (this file).
- **Branch**: `sprint-u-nz-connector` in isolated worktree
  `/home/macro/projects/sonar-wt-sprint-u`.
- **Status**: **CLOSED** for M1 NZ. New Zealand monetary M1 row
  now lands via the canonical `TE primary → RBNZ B2 CSV scaffold
  (raises) → FRED OECD stale-flagged` cascade — the symmetric
  closure of the Sprint I (UK/GB), Sprint L (JP), Sprint S (CA),
  and Sprint T (AU) cascades. M2 + M4 NZ ship as wire-ready
  scaffolds raising `InsufficientDataError` until the per-country
  connector bundle lands (CAL-NZ-M2-OUTPUT-GAP / CAL-NZ-CPI /
  CAL-NZ-INFL-FORECAST / CAL-NZ-M4-FCI). M3 NZ deferred
  (CAL-NZ-M3) — requires NZ NSS + EXPINF overlay persistence which
  is Phase 2+ scope.
- **M2 T1 progression**: **10 → 11 countries monetary M1 live**.
  The `--all-t1` loop preserves its historical 7-country semantics
  (US + DE + PT + IT + ES + FR + NL); GB / JP / CA / AU / NZ are
  Tier-1 opt-ins via `--country GB|JP|CA|AU|NZ` matching the
  pattern Sprint I / L / S / T established.

## 2. Context — why NZ, why now

NZ was the next deferred Tier-1 advanced economy after the UK / JP /
CA / AU quartet shipped. Sprint U-NZ closes the Anglosphere advanced-
economy bundle (US + GB + CA + AU + NZ) for M1, leaving CH / NO / SE
as the remaining non-Euro Tier-1 countries pending (CH is underway in
Sprint V-CH parallel; PT already lives via the EA-periphery path; EA
is wired but not per-country; NO / SE are Phase 2+ scope).

Reserve Bank of New Zealand publishes policy rates + yield curves via
three channels relevant to Sprint U-NZ:

- **RBNZ statistical-tables CSV** at `https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/...`
  — **public in principle but host-perimeter-blocked** from the
  SONAR VPS egress (empirical probe 2026-04-21 returned HTTP 403
  `Website unavailable` on every path regardless of User-Agent).
  Expected to be RBA-analogous in payload shape (header metadata +
  `Series ID` row + `YYYY-MM-DD,value` data rows) per RBNZ public
  documentation; the connector ships a parser for that shape but
  it remains **unvalidated against a real payload** until
  CAL-NZ-RBNZ-TABLES closes.
- **TradingEconomics (TE)** — same Pro subscription used for GB /
  JP / CA / AU mirrors RBNZ's Official Cash Rate as
  `HistoricalDataSymbol=NZOCRS` with daily cadence and history
  back-filled to 1985-01. Sprint I-patch established that TE-
  primary is the canonical aggregator shape for country expansion,
  so NZ defaults to the same pattern. Sprint U-NZ makes this the
  fifth consecutive country shipped via this pattern.
- **FRED's OECD mirror** (`IRSTCI01NZM156N` short-rate +
  `IRLTLT01NZM156N` 10Y) available as last-resort fallback but
  monthly-lagged — demoted to staleness-flagged on the same terms
  as the GB / JP / CA / AU mirrors.

The material Sprint U-NZ novelty vs prior sprints is **the first
scaffold-only native slot where the scaffold is driven by a live-
host block, not API-access cost**. BoE IADB (Sprint I) and BoJ TSD
(Sprint L) also ship as wire-ready scaffolds — but those are
intermittently Akamai-rejected and theoretically unblockable with
better headers. The RBNZ host 403s uniformly from the SONAR egress
regardless of User-Agent, which means the cascade hits the FRED
stale-flagged branch every single run at Sprint U-NZ close.
`CAL-NZ-RBNZ-TABLES` tracks the operator-side fix (likely VPS
egress IP allowlist or proxy routing).

## 3. Commits

| # | SHA | Scope |
|---|---|---|
| 1 | `ea96edd` | feat(connectors): TE `fetch_nz_ocr` wrapper + `NZOCRS` source-drift guard |
| 2 | `b5da528` | feat(connectors): RBNZ statistical-tables connector (wire-ready, perimeter-blocked) |
| 3 | `90cffb6` | feat(config): NZ Tier 1 monetary YAML entries (r* proxy + RBNZ 1-3% target) |
| 4 | `4d965d6` | feat(indices): M1 NZ TE-primary cascade + M2/M4 NZ scaffolds |
| 5 | `2ce0060` | feat(pipelines): `daily_monetary_indices` NZ country dispatch |
| 6 | this | docs(planning): Week 9 Sprint U-NZ retrospective + CAL-NZ-* items |

All 5 feature commits on `sprint-u-nz-connector`; full pre-push
gate (ruff format + ruff check + mypy src/sonar + pytest unit -m
"not slow") green every push.

## 4. Empirical findings — probes

Two primary probes ran during pre-flight (C1 commit body):

### 4.1 TE NZ OCR

- Endpoint: `GET /historical/country/new%20zealand/indicator/interest%20rate?c=$TE_API_KEY&format=json`
- Response: 533 JSON objects
- First row: `{"DateTime": "1985-01-31T00:00:00", "Value": 14.89, "HistoricalDataSymbol": "NZOCRS"}`
- Latest row (2026-04-21 probe): `{"DateTime": "2026-04-08T00:00:00", "Value": 2.25, "HistoricalDataSymbol": "NZOCRS"}`
- All 533 rows carry `HistoricalDataSymbol=NZOCRS` (no multi-symbol
  contamination). Pre-1999 values reflect legacy RBNZ policy-rate
  proxies TE consolidates under the same interest-rate indicator;
  post-1999 (OCR inception) values track the published OCR history.
- Frequency: Daily (sparse — TE captures each rate-change
  announcement plus interim quotes; 533 rows is within the BoC
  2320-row / RBA 330-row band and consistent with RBNZ's mixed
  cadence since 1999).
- Validation: ✓ matches current RBNZ 2.25% OCR (April 2026 decision
  after the RBNZ's 2024-2026 easing cycle from a 5.5% peak). Pro-
  tier quota hit: 1 call per day per integration test run (caches
  24h).

### 4.2 RBNZ statistics host

- Endpoints probed (all 2026-04-21):
  - `GET /statistics`
  - `GET /statistics/key-graphs/ocr`
  - `GET /-/media/project/sites/rbnz/files/statistics/tables/b2/hb2-daily.csv`
  - `GET /-/media/project/sites/rbnz/files/statistics/tables/b/b2/hb2-daily.csv`
  - `GET /-/media/project/sites/rbnz/files/statistics/series/b2-daily.csv`
  - `GET /robots.txt`
  - `GET /`
- HTTP behaviour: **HTTP 403 `Website unavailable` on every path**
  under both `Mozilla/5.0` chrome UA with full `Accept` / `Accept-
  Language` headers **and** `SONAR/2.0 (monetary-cascade; ...)`
  descriptive UA. Response body is an HTML page with
  `Website unavailable - Reserve Bank of New Zealand - Te Pūtea
  Matua` and an Akamai-style error token. Even `/robots.txt` 403s
  → confirms the block is at the hostname / IP perimeter, not
  per-path.
- Interpretation: the block is host / IP-scoped, not UA-scoped, so
  the Sprint T-AU UA-gate fix does not unlock it. Likely root cause:
  geo / ASN-based filtering at the RBNZ edge (historically enforced
  for a subset of foreign cloud providers). The SONAR VPS egress
  IP may need RBNZ operator allowlisting or the probes need to
  route via an NZ-residing proxy.
- Probe time-box: 20 minutes budgeted, ~5 minutes actual
  (block signal was unambiguous after the third path).
- Verdict: RBNZ secondary slot cannot ship live at Sprint U-NZ close.
  The connector ships wire-ready so the day the host unblocks the
  parser handles the payload without code changes — plus
  `CAL-NZ-RBNZ-TABLES` tracks operator resolution.

### 4.3 FRED OECD NZ mirror

- Series metadata probe deferred (extrapolated from GB / JP / CA / AU
  OECD mirror behaviour which has identical shape on FRED). The C5
  integration canary surfaced "Unknown FRED series mapping:
  IRSTCI01NZM156N" before the `FredConnector.FRED_SERIES_TENORS`
  extension, proving the fallback was reached live. After the
  extension both canaries pass.
- Monthly cadence, OECD-sourced, monthly-lagged.
- Wired as last-resort fallback with `NZ_OCR_FRED_FALLBACK_STALE` +
  `CALIBRATION_STALE` flags.

## 5. Cascade flag semantics (NZ)

```
priority | source         | flags emitted
---------|----------------|------------------------------------------------------------
   1     | TE primary     | NZ_OCR_TE_PRIMARY
   2     | RBNZ B2 CSV    | NZ_OCR_RBNZ_NATIVE (post-unblock)
   X     | RBNZ scaffold  | NZ_OCR_RBNZ_UNAVAILABLE (current live state)
   3     | FRED OECD      | NZ_OCR_FRED_FALLBACK_STALE + CALIBRATION_STALE
```

TE misses also emit `NZ_OCR_TE_UNAVAILABLE` into the flag tuple for
downstream visibility — same pattern as the other countries'
cascades.

Always-present cross-cutting flags on every persisted NZ M1 row:
- `R_STAR_PROXY` (RBNZ does not publish HLW — 1.75% proxy from
  RBNZ Bulletin / Discussion Papers 2023-2024 neutral-range
  synthesis: ~3.5% nominal minus 2% target → ~1.5-2% real,
  midpoint 1.75%)
- `EXPECTED_INFLATION_CB_TARGET` (RBNZ 1-3% CPI target midpoint
  2% is the Phase 1 proxy for 5Y inflation expectation)
- `NZ_BS_GDP_PROXY_ZERO` (balance-sheet ratio zero-seeded pending
  CAL-NZ-BS-GDP)

## 6. Live canary outcomes (Sprint U-NZ close)

All @slow integration canaries pass with `FRED_API_KEY` +
`TE_API_KEY` set (NZ + AU + CA + JP cascade suite):

- `tests/integration/test_daily_monetary_nz.py::test_daily_monetary_nz_te_primary` ✓ (NEW)
- `tests/integration/test_daily_monetary_nz.py::test_daily_monetary_nz_fred_fallback_when_te_absent_rbnz_blocked` ✓ (NEW)
- `tests/unit/test_connectors/test_te_indicator.py::test_live_canary_nz_ocr` ✓ (NEW)
- `tests/unit/test_connectors/test_rbnz.py::test_live_canary_rbnz_ocr_expects_block` ✓ (NEW; documents the 403 live state)
- `tests/integration/test_daily_monetary_au.py` (3 canaries) ✓ (unchanged)
- `tests/integration/test_daily_monetary_ca.py` (3 canaries) ✓ (unchanged)
- `tests/integration/test_daily_monetary_jp.py` (2 canaries) ✓ (unchanged)

Wall-clock: combined NZ canary suite = ~10s against live TE + FRED
+ RBNZ endpoints.

The NZ FRED fallback canary surfaced the missing
`IRSTCI01NZM156N` / `IRLTLT01NZM156N` entries in
`FredConnector.FRED_SERIES_TENORS` during the C5 integration run —
caught pre-merge, fixed in the same commit. Matches the Sprint S
lesson (OECD mirror tenors must be registered before the cascade
can hit FRED) and supersedes the Sprint T pre-emptive fix (which
was applied speculatively and landed clean).

## 7. Coverage delta

- `src/sonar/connectors/rbnz.py` NEW — all branches exercised (parser
  happy-path, missing Series ID row, missing column, bad-date rows,
  empty cells, date window filter, HTTP 403 retry exhaustion,
  200-with-HTML perimeter body detection, cache round-trip, UA
  discipline regression guard, @slow live canary against the 403
  block).
- `src/sonar/connectors/te.py` — new `fetch_nz_ocr` method +
  `TE_EXPECTED_SYMBOL_NZ_OCR` + `NZ → "new zealand"` in
  `TE_COUNTRY_NAME_MAP` covered by 5 tests (happy path, source
  drift, empty response, 533-row cassette, @slow live canary).
- `src/sonar/indices/monetary/builders.py` — new `_nz_ocr_cascade`
  + `build_m1_nz_inputs` + `build_m2_nz_inputs` +
  `build_m4_nz_inputs` covered by 11 direct tests + 5 facade-
  dispatch tests.
- `src/sonar/pipelines/daily_monetary_indices.py` — NZ branch +
  RBNZConnector wiring exercised by 1 new unit test + 2 live
  canaries.
- `src/sonar/connectors/fred.py` — 2 new OECD mirror entries in
  `FRED_SERIES_TENORS` (short + long); exercised by the live
  fallback canary.
- `src/sonar/config/r_star_values.yaml` + `bc_targets.yaml` — NZ
  entries; covered by 3 new loader tests (value + source metadata
  + inflation target mapping).

No coverage regression > 0.5pp on any touched module.

## 8. HALT triggers fired / not fired

- Trigger 0 (TE NZ empirical probe fails) — **not fired**. Probe
  returned 533 rows of `NZOCRS`.
- Trigger 1 (HistoricalDataSymbol mismatch) — **not fired**. Source-
  drift guard in place and unit-tested.
- Trigger 2 (RBNZ tables unreachable) — **handled, not HALT per
  brief**. Probe confirmed perimeter 403 on every path under both
  Mozilla and SONAR UAs; connector scaffolds raise
  DataUnavailableError cleanly; CAL-NZ-RBNZ-TABLES opened. Brief
  §5 explicitly marks this as "not a HALT — scaffold with
  DataUnavailableError + open CAL-NZ-RBNZ-TABLES".
- Trigger 3 (RBNZ CSV schema divergent from RBA) — **not evaluable
  at Sprint close**. Host unreachable from the VPS; parser shipped
  with the documented RBNZ B-series shape (header metadata +
  Series ID row + `YYYY-MM-DD,value` rows) pending empirical
  validation post-unblock.
- Trigger 4 (NZ tier mismatch) — **not fired**. NZ is already
  Tier 1 in `country_tiers.yaml`.
- Trigger 5 (r* NZ uncertainty) — **handled via R_STAR_PROXY
  flag.** Value anchored at 1.75% per RBNZ Bulletin / Discussion
  Paper series 2023-2024 neutral-range synthesis, `proxy: true`
  marker in YAML + source string.
- Trigger 6 (M2/M4 scaffolds pattern) — **handled via graceful
  InsufficientDataError scaffold.** CAL-NZ-M2-OUTPUT-GAP /
  CAL-NZ-M4-FCI open the follow-ups.
- Trigger 7 (TE rate limits) — **not fired**. Only 1 indicator
  probe + 1 cassette call hit TE during the sprint.
- Trigger 8 (coverage regression > 3pp) — **not fired**.
- Trigger 9 (pre-push gate failure) — **not fired**. No
  `--no-verify` used on any push.
- Trigger 10 (concurrent Sprint V-CH touches pipeline / builder /
  te.py / YAML files) — **not fired at Sprint U-NZ close**. Sprint
  V-CH runs in `sonar-wt-sprint-v` on `connectors/snb.py` + same
  shared-append zones; since U-NZ merges first (alphabetical),
  V-CH rebases on merge.

## 9. Deviations from brief

1. **Commit count**: 5 feature commits + 1 retrospective commit = 6
   total; brief target of 6-8. C4 landed as one atomic change (M1
   cascade + M2/M4 scaffolds + facade dispatch + unit tests) because
   splitting would break the typing surface of
   `MonetaryInputsBuilder.__init__` (new `rbnz` kwarg requires all
   three `build_m*` dispatch branches to exist in the same commit).
   Sprint S and T made the same call; the merge was clean each time.
2. **RBNZ perimeter block**: anticipated by the brief at the
   Sprint T-AU UA-gate lesson level, but the actual failure mode was
   IP-scoped rather than UA-scoped — i.e. the UA fix did **not**
   unlock RBNZ. The brief's fallback clause ("scaffold with
   DataUnavailableError + open CAL-NZ-RBNZ-TABLES") kicked in
   without deviation.
3. **FRED FRED_SERIES_TENORS extension**: the brief listed this as
   implicit C5 scope; the integration canary surfaced the missing
   entries before merge so the fix landed in the same commit rather
   than as a post-hoc patch. Matches the Sprint S C5 lesson.
4. **r\* value**: brief suggested 1.5-2.0% range (anchored 1.75%
   midpoint); implementation landed exactly at 1.75% with the
   documented RBNZ Bulletin / Discussion Papers 2023-2024 source
   string. `proxy: true` marker set per spec §4.

## 10. NZ monetary indices operational state

- **M1 NZ**: live via TE cascade; per-row flags
  `NZ_OCR_TE_PRIMARY` (happy path, when TE_API_KEY set) or
  `NZ_OCR_RBNZ_UNAVAILABLE + NZ_OCR_FRED_FALLBACK_STALE +
  CALIBRATION_STALE` (current live state without TE key — RBNZ
  perimeter-blocked).
- **M2 NZ**: scaffold — raises `InsufficientDataError`. Pipeline
  catches + logs `monetary_pipeline.builder_skipped` warning and
  proceeds with M1 persisted (M2 row = 0). Tracked via
  CAL-NZ-M2-OUTPUT-GAP / CAL-NZ-CPI / CAL-NZ-INFL-FORECAST.
- **M3 NZ**: deferred — requires NZ NSS + EXPINF overlay
  persistence (Phase 2+ scope). Tracked via CAL-NZ-M3.
- **M4 NZ**: scaffold — raises `InsufficientDataError` because
  < 5/5 custom-FCI components are wired. Tracked via
  CAL-NZ-M4-FCI.

## 11. Pattern validation

- **TE-primary cascade continues canonical** — NZ is the fifth
  consecutive country to ship via the Sprint I-patch pattern
  (GB / JP / CA / AU / NZ). Zero deviation in builder shape,
  flag names, or facade dispatch. The pattern is now battle-tested.
- **Native-secondary slot flexibility** — CA (BoC Valet JSON REST)
  and AU (RBA F-tables CSV) ship as reachable secondaries; GB (BoE
  IADB) and JP (BoJ TSD) ship as wire-ready scaffolds due to
  Akamai-style bot detection; NZ (RBNZ B2 CSV) ships as wire-ready
  scaffold due to host / IP perimeter block. The cascade handles
  all three states (`*_NATIVE` vs raising-scaffold vs
  host-blocked) identically from the builder perspective — the
  `DataUnavailableError` catch is the single integration point.
- **UA discipline preventively applied** — the RBNZ connector
  encodes `SONAR/2.0 (monetary-cascade; contact hugocondesa@pm.me)`
  as `RBNZ_USER_AGENT: Final[str]`; the fact that this UA doesn't
  unlock the current RBNZ edge doesn't invalidate the discipline
  for post-unblock day-1.

## 12. Isolated worktree + merge strategy

- Sprint U-NZ operated entirely in
  `/home/macro/projects/sonar-wt-sprint-u` on branch
  `sprint-u-nz-connector`.
- Sprint V-CH operates concurrently in
  `/home/macro/projects/sonar-wt-sprint-v` on branch
  `sprint-v-ch-connector`.
- Shared-file append zones used by both sprints:
  `src/sonar/connectors/te.py` (new wrappers — distinct functions),
  `src/sonar/indices/monetary/builders.py` (new builders — distinct
  functions), `src/sonar/pipelines/daily_monetary_indices.py`
  (`MONETARY_SUPPORTED_COUNTRIES` tuple + `_build_live_connectors`
  handle list — likely union-merge conflict),
  `src/sonar/config/r_star_values.yaml` +
  `src/sonar/config/bc_targets.yaml` (distinct country keys — merge
  clean), `docs/backlog/calibration-tasks.md` (CAL entries — union
  merge).
- Zero collision incidents during Sprint U-NZ development itself
  (Sprint V-CH has not yet merged; U-NZ is the alphabetically-first
  branch and merges first per brief protocol).

Merge command (to run once the sprint is signed off):
```bash
cd /home/macro/projects/sonar-engine
git fetch origin
git checkout main
git merge --ff-only sprint-u-nz-connector
git push origin main
```

Sprint V-CH will then rebase against the new `main` tip — the
`MONETARY_SUPPORTED_COUNTRIES` tuple + `_build_live_connectors`
list + YAMLs + `calibration-tasks.md` are the likely conflict
zones, all resolvable via straight union merge.

## 13. CAL items opened (Sprint U-NZ)

Opened in `docs/backlog/calibration-tasks.md` by this commit:

- **CAL-NZ** (PARTIALLY CLOSED — M1 level shipped Sprint U-NZ;
  M2/M4/M3 paths tracked by sub-items) — parent entry mirroring
  CAL-118 / CAL-119 / CAL-129 / CAL-AU structure.
- **CAL-NZ-RBNZ-TABLES** (OPEN, MEDIUM) — RBNZ host perimeter-block
  resolution (VPS egress allowlist or proxy routing).
- **CAL-NZ-M2-OUTPUT-GAP** (OPEN, MEDIUM) — Stats NZ / OECD EO NZ
  / NZ Treasury HYEFU/BEFU output-gap source for M2 NZ.
- **CAL-NZ-M4-FCI** (OPEN, MEDIUM) — NZ custom-FCI 5-component
  bundle (credit spread + vol + 10Y + NZD NEER + mortgage).
- **CAL-NZ-M3** (OPEN, LOW) — NZ NSS + EXPINF overlay persistence
  for M3 NZ (Phase 2+ dependency).
- **CAL-NZ-BS-GDP** (OPEN, LOW) — RBNZ balance-sheet (B5/B6) +
  Stats NZ nominal GDP for M1 NZ balance_sheet_signal populat.
- **CAL-NZ-CPI** (OPEN, MEDIUM) — TE generic NZ CPI YoY wrapper
  + source-drift guard for M2 NZ inflation input.
- **CAL-NZ-INFL-FORECAST** (OPEN, LOW) — RBNZ MPS forecast
  HTML/PDF scrape for M2 NZ inflation-forecast cycle input
  (replaces the CB-target proxy once available).

## 14. Forward work

- Sprint V-CH parallel: Switzerland SNB connector + M1 CH (running
  concurrently in `sonar-wt-sprint-v`; rebases post-U-NZ merge).
- Next T1 targets after CH: NO / SE (non-Euro advanced; Phase 2+
  candidates once Anglosphere + CH bundle is fully shipped).
- CAL-NZ-RBNZ-TABLES operator follow-up: probe quarterly + explore
  egress-IP allowlisting with RBNZ contact or NZ-residing proxy
  path.
- M2 T1 Core CAL ladder closure order (per CAL parent-entry
  priorities):
  1. CAL-NZ-CPI + CAL-NZ-M2-OUTPUT-GAP close M2 NZ (combined with
     inflation-forecast proxy).
  2. CAL-NZ-M4-FCI bundle closes M4 NZ.
  3. CAL-NZ-M3 closes M3 NZ once NSS + EXPINF overlays ship.
  4. CAL-NZ-RBNZ-TABLES closes the RBNZ_UNAVAILABLE path.
  5. CAL-NZ-BS-GDP closes the BS/GDP proxy.

## 15. Final tmux echo

```
SPRINT U-NZ NEW ZEALAND CONNECTOR DONE: 6 commits on branch sprint-u-nz-connector
TE HistoricalDataSymbol NZ validated: NZOCRS (daily, back-filled 1985-01..2026-04, 533 obs)
RBNZ tables reachability: BLOCKED (perimeter 403 on all paths under both Mozilla and SONAR UAs — CAL-NZ-RBNZ-TABLES)
NZ monetary: M1 (TE cascade live), M2/M4 (scaffolds), M3 (deferred)
M2 T1 progression: 10 → 11 countries
HALT triggers: none (Trigger 2 handled per brief fallback clause)
Merge: git checkout main && git merge --ff-only sprint-u-nz-connector
Artifact: docs/planning/retrospectives/week9-sprint-u-nz-connector-report.md
```
