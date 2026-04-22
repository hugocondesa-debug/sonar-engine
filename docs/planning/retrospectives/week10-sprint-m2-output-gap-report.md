# Week 10 Day 1+ Sprint C — CAL-M2-T1-OUTPUT-GAP-EXPANSION Retrospective

**Sprint**: C — Week 10 Day 1+ M2 output-gap expansion via OECD EO (CAL-M2-T1-OUTPUT-GAP-EXPANSION, output-gap half).
**Branch**: `sprint-m2-output-gap-expansion`.
**Worktree**: `/home/macro/projects/sonar-wt-m2-output-gap-expansion`.
**Brief**: `docs/planning/week10-sprint-c-m2-output-gap-brief.md` (format v3 — third production use).
**Duration**: ~3h CC (single session 2026-04-22, under the 4-6h budget).
**Commits**: 5 substantive + this retro = 6 total.
**Outcome**: Ship output-gap half of `CAL-M2-T1-OUTPUT-GAP-EXPANSION`. All 16 T1 countries + EA17 aggregate reachable through a single new `OECDEOConnector`; 8 per-country M2 scaffolds (JP / CA / AU / NZ / CH / SE / NO / DK) now opportunistically fetch the gap and reflect that in the raise message. Full M2 compute still blocked on `CAL-CPI-INFL-T1-WRAPPERS` per brief §2 + HALT-0 analysis.

---

## 1. Commit inventory

| # | SHA | Subject | Scope |
|---|-----|---------|-------|
| 1 | `8f2c607` | feat(connectors): OECD Economic Outlook SDMX connector + Sprint C brief | L0 connector scaffold + brief v3 reinstated + 22 unit tests + 2 live canaries |
| 2 | `504ea69` | feat(connectors): OECD EO T1 coverage tuple + is_t1_covered helper | `OECD_EO_T1_ISO2` tuple + `is_t1_covered` membership helper + 39 parametrised tests (17 countries) |
| 3 | `571f79c` | feat(indices): wire OECD EO output-gap into Week-9 + JP M2 builders | 8 builder signatures + facade + narrowed raise messages + 27 new Sprint C tests |
| 4 | `faf92c0` | feat(indices): M2 unsupported-country dispatch references Sprint C state + US verify | Facade `NotImplementedError` msg + HALT-13 US-signature guard + 8 new parametrised tests |
| 5 | `751fb44` | feat(pipelines): OECD EO connector lifecycle in daily_monetary_indices | `_build_live_connectors` wiring + aclose bundle + 1 unit lifecycle test + 2 live integration canaries |
| 6 | (this commit) | docs(planning+backlog): Sprint C M2 output-gap retrospective + CAL closure | CAL marked CLOSED output-gap-half + retro |

---

## 2. Pre-flight findings (Commit 1, 2026-04-22 probe)

Following the HALT-0 precedent from Sprint A (EA periphery ECB SDW probe
invalidating the brief's primary + fallback paths), Sprint C's Commit 1
ran a systematic per-country probe against the OECD EO SDMX endpoint
(`https://sdmx.oecd.org/public/rest/data/OECD.ECO.MAD,DSD_EO@DF_EO,1.4`).

### Endpoint

- Public — no auth key.
- SDMX-JSON via `format=jsondata`.
- Edition EO118 (OECD Economic Outlook No. 118, 2025/2).
- Range 1990 → 2027 (historicals + two-year forecasts interleaved).

### Measure selection

Brief §1 anticipated deriving output gap from `GDPV` (real GDP) +
`GDPVTR` (trend GDP via HP-filter). The probe revealed OECD already
publishes the gap directly under the `GAP` measure (percent of
potential GDP, annual frequency). This avoids HP-filter methodology
divergence risk flagged in brief §9 — we consume the raw OECD
computation rather than re-running our own HP-filter, which would
have diverged from OECD's canonical parameters.

### Per-country coverage matrix

| ISO2 | OECD `REF_AREA` | `GAP` (2024) | History | Status |
|------|-----------------|--------------|---------|--------|
| US   | USA  | +0.537 | 1990-2027 | live |
| DE   | DEU  | -1.954 | 1990-2027 | live |
| FR   | FRA  | -0.349 | 1990-2027 | live |
| IT   | ITA  | +0.882 | 1990-2027 | live |
| ES   | ESP  | -1.153 | 1990-2027 | live |
| NL   | NLD  | -0.061 | 1990-2027 | live |
| PT   | PRT  | +0.848 | 1990-2027 | live |
| GB   | GBR  | +0.051 | 1990-2027 | live |
| JP   | JPN  | -2.044 | 1990-2027 | live |
| CA   | CAN  | -0.043 | 1990-2027 | live |
| AU   | AUS  | +0.104 | 1990-2027 | live |
| NZ   | NZL  | -2.681 | 1990-2027 | live |
| CH   | CHE  | +1.089 | 1990-2027 | live |
| SE   | SWE  | -2.550 | 1990-2027 | live |
| NO   | NOR  | -0.643 | 1990-2027 | live |
| DK   | DNK  | +0.167 | 1990-2027 | live |
| EA   | **EA17** | empty for EA19 / EA20 — falls back to legacy EA17 code | 1990-2027 | live via legacy code |

**All 16 T1 + EA17 aggregate live** — no HALT-0 fired; Sprint A precedent
inverted (Sprint A found empty per-country YC; Sprint C finds full
coverage for GAP).

### Cadence caveat vs US CBO

OECD EO is **annual** (`FREQ=A`). US CBO GDPPOT path is **quarterly**,
so the US M2 builder was deliberately left on the CBO path — OECD EO
USA annual is strictly coarser. HALT-13 regression check shipped as
`test_us_builder_signature_unchanged_no_regression` to guard this.

The per-country cost of this cadence change (vs a hypothetical
quarterly native path) is documented in the connector module docstring:
observation anchored on Dec 31 of the TIME_PERIOD year; M2 builders
pick the latest TIME_PERIOD year ≤ anchor date.

---

## 3. Scope outcome vs brief

### Brief's ambition (§1 Scope)

Ship live M2 Taylor-gap compute across 15+ T1 countries by upgrading
the Week-9 scaffolds from `raise InsufficientDataError` to full
compute. Three tracks: OECD EO connector (~2h), per-country M2
wiring (~2-3h), pipeline + tests (~1-2h).

### Empirical reality (Commit 1 probe + Commits 3-4 wiring)

OECD EO delivers the output-gap component cleanly for 16 T1 + EA17.
But the M2 Taylor-gap formula needs three per-country inputs
(CPI YoY, output-gap, inflation-forecast) — none of the Week-9
scaffolds ship CPI or forecast wrappers. Full M2 live compute
therefore remains blocked on `CAL-CPI-INFL-T1-WRAPPERS`, independent
of this sprint's scope.

Per brief §5 HALT-0 ("OECD EO empirical probe reveals sparse per-
country coverage — scope narrow"): the empirical probe did NOT
reveal sparse coverage (opposite of Sprint A) — OECD EO covers
every T1 target. But the honest scope is still narrower than the
brief's C3/C4 aspirations because the *other* M2 inputs remain
unwired. Taking the CAL's own wording as authoritative —

> `CAL-M2-T1-OUTPUT-GAP-EXPANSION — M2 Taylor-gap output-gap
> connectors for T1 countries`

— the sprint delivers exactly the output-gap half of that CAL, which
is the unambiguous scope signal.

### Shipped outcomes

**L0** (`src/sonar/connectors/oecd_eo.py`):

- `OECDEOConnector(cache_dir, timeout=30.0)` — public SDMX-JSON fetch
  with tenacity retry + ConnectorCache 24h TTL + structured logs.
- `fetch_output_gap(country_code, start, end) → list[OutputGapObservation]`.
- `fetch_latest_output_gap(country_code, observation_date, *, history_years=10)`.
- `OECD_EO_COUNTRY_MAP` (17 ISO2 → ISO3 entries) + `OECD_EO_T1_ISO2`
  sorted tuple + `is_t1_covered(country_code)` helper.

**L3 M2 builders** (`src/sonar/indices/monetary/builders.py`):

- 8 per-country scaffolds (JP / CA / AU / NZ / CH / SE / NO / DK) gain
  `oecd_eo: OECDEOConnector | None = None` parameter; call
  `_try_fetch_oecd_output_gap_pct(oecd_eo, country, anchor)` and pass
  the result to `_m2_blocked_msg` for message composition.
- `_m2_blocked_msg` central helper — output_gap_wired branching keeps
  the per-country raise texts consistent.
- Facade `MonetaryInputsBuilder.__init__` accepts `oecd_eo`; M2
  dispatch passes it through to all 8 Week-9 builders.
- Facade `NotImplementedError` for unsupported M2 countries (DE / FR /
  IT / ES / NL / PT / EA / GB) now cites Sprint C state (output-gap
  wire-ready, M2 scaffold itself missing).

**L8 pipeline** (`src/sonar/pipelines/daily_monetary_indices.py`):

- `_build_live_connectors` instantiates `OECDEOConnector` unconditionally
  (no key gate) and includes it in `connectors: list[object]` for
  aclose lifecycle.
- Passes `oecd_eo` to the facade.

**Tests**:

- 61 unit tests in `test_oecd_eo.py` (constants, connector shape,
  fetch happy path + soft-fail branches, cache round-trip, parametrised
  per T1 ISO2).
- 27 Sprint C unit tests in `test_builders.py` (3 parametrised classes
  x 8 countries covering OECD EO success / unavailable / not-injected
  branches; facade pass-through; US signature regression guard).
- 8 new parametrised tests in `test_builders.py` covering the updated
  unsupported-country facade phrasing for DE/FR/IT/ES/NL/PT/EA/GB.
- 1 lifecycle test in `test_daily_monetary_indices.py` exercising
  `_build_live_connectors` with OECD EO.
- 2 live integration canaries
  (`test_daily_monetary_oecd_eo_sprint_c.py`, `@slow`): 17-country
  coverage smoke + facade-end-to-end raise assertion.

**Full unit suite**: 1681 pass (known-flaky re-run-to-green pattern per
`docs/testing-strategy.md` §4 — pipeline cross-test ordering
flake pre-existing, surfaces on 1-2 runs; passes in isolation).

**Full-project mypy**: 118 files clean.

**Ruff format + check**: clean.

**Live canary wall-clock**: 59s (well under HALT-7 70s threshold).

### Residual tracked (CAL updated)

`CAL-M2-T1-OUTPUT-GAP-EXPANSION` marked **CLOSED output-gap half** with
explicit residual citation:

1. `CAL-CPI-INFL-T1-WRAPPERS` — per-country CPI YoY + inflation-
   forecast wrappers needed for full M2 compute. When that closes,
   the 8 scaffolds flip to full compute with zero further L0 work.
2. US M2 path deliberately preserved (CBO quarterly > OECD EO annual).
3. DE/FR/IT/ES/NL/PT/EA/GB M2 scaffolds themselves remain to be
   created — this is M2-builder-body work, not L0 work, and follows
   once CPI/forecast wrappers exist.

---

## 4. HALT triggers

| # | Trigger | Fired? | Outcome |
|---|---------|--------|---------|
| 0 | OECD EO probe reveals sparse per-country coverage | **No** | All 16 T1 + EA17 live. Sprint A precedent (HALT-0 forcing scope narrow) inverted — here the probe validates the brief path |
| 1 | OECD EO SDMX format unexpected | No | SDMX-JSON 2.0 shape matched expectations; parser handled null observations + NoRecordsFound text body cleanly |
| 2 | EA aggregate unavailable | **Near-miss** | `EA19` + `EA20` return `NoRecordsFound`; resolved by mapping `EA → EA17` (legacy 17-member composition, still published for `GAP`). Documented in module docstring + country-map comment |
| 3 | Output gap values implausible | No | 2024 values across all 16 countries within [-3.5 %, +1.1 %] band; historical range for all countries within [-11 %, +2 %]; sanity-band in live canary is [-15 %, +10 %] |
| 4 | HP-filter methodology divergence | N/A | Avoided by using OECD's own `GAP` measure rather than re-computing from `GDPV` / `GDPVTR`. Probe finding promoted into connector design |
| 5 | TE equity probe conflict (Sprint B zone) | No | Zero te.py edits; primary-file discipline held |
| 6 | Cassette count < 10 | N/A | OECD EO is public + cheap; in-test SDMX-JSON payload fixtures used instead of cassettes (22+ payloads composed via `_sdmx_json_payload` helper) |
| 7 | Live canary wall-clock > 70s | No | 59s wall-clock for 17-country fetch + facade round-trip |
| 8 | Pre-push gate fails | No | ruff + mypy + unit tests green on every push |
| 9 | No `--no-verify` | No | Standard discipline; one pre-commit secret-keyword false positive fixed with `# pragma: allowlist secret` (fake-key string in unit test) |
| 10 | Coverage regression > 3pp | No | New modules (oecd_eo.py 100 %; builder helpers 100 %) pull average up; no existing module touched in a coverage-losing way |
| 11 | Push before stopping | **Yes (deliberate)** | Every commit pushed immediately after local gate pass |
| 12 | Sprint B file conflict | No | Zero overlap — Sprint B works in `overlays/erp/` + `daily_cost_of_capital.py` + `te.py`; Sprint C in `connectors/oecd_eo.py` + `indices/monetary/builders.py` + `daily_monetary_indices.py` |
| 13 | US M2 regression | No | US M2 builder signature + body unchanged; HALT-13 guard shipped as `test_us_builder_signature_unchanged_no_regression` |

---

## 5. Brief format v3 — third-use lessons

- ✓ **§10 pre-merge checklist useful again** — pre-push gate discipline
  held every commit; the CAL-file single-touch (`docs/backlog/
  calibration-tasks.md`) trivial-union-merge surface with Sprint B
  in flight was anticipated per §3 and did not materialise as a
  blocker since Sprint B had not yet touched that file when C6
  landed.
- ✓ **§11 `sprint_merge.sh`** — third production use imminent (post-
  this retro commit).
- ~ **§5 HALT-0 + §2 pre-flight compose cleanly when probe validates**
  — Sprint A had HALT-0 fire and narrow the scope; Sprint C had the
  probe validate the full path. The brief's §2 pre-flight table was
  the right place to document the probe outcomes per country; the
  decision to use the `GAP` measure directly (vs derive from GDPV +
  GDPVTR) emerged from the probe and is documented in Commit 1 body +
  connector module docstring.
- ~ **§6 acceptance criteria still scope-fixed** — "M2 live for 15+
  T1 countries" was aspirational; the honest interpretation (output-
  gap component wired — the CAL's actual name) delivered within
  budget. Fourth-use suggestion matches the Sprint A retro: outcome-
  based phrasing ("output-gap connector shipped; per-country dispatch
  accepts it") would survive better than count-based phrasing.

### New for v4 recommendation (concurs with Sprint A retro)

§2 pre-flight should enumerate **what the probe outcome unlocks vs
blocks**, not just what to fetch. Sprint C's pre-flight would have
been sharper with a table like:

| Probe outcome | Unlocks | Blocks / deferred |
|---|---|---|
| `GAP` measure present per country | Direct consumption path (avoid HP-filter divergence) | — |
| `GDPV + GDPVTR` only | Fallback derivation path (HP-filter sampled; methodology-divergence tracked) | — |
| Neither | HALT-0 — scope narrow; open per-country CAL items | Full sprint scope |

This would have pre-authorised the "use `GAP` directly" pivot at §2
time rather than inside Commit 1 body.

---

## 6. Production impact

**Pre-Sprint-C**: running `sonar daily_monetary_indices --all-t1` for
the 8 Week-9 countries emitted `monetary_pipeline.builder_skipped`
with a three-blocker (`CPI + output-gap + forecast`) error message per
country.

**Post-Sprint-C** (same `--all-t1` invocation):

- US: live M2 row persisted (CBO quarterly; no regression).
- JP / CA / AU / NZ / CH / SE / NO / DK (8 countries): pipeline still
  emits `monetary_pipeline.builder_skipped`, but:
  - The structlog event now carries a narrower `message` —
    "`output-gap live via OECD EO per Sprint C Week 10`, remaining
    blocker is CPI + inflation-forecast".
  - A structured `monetary_builder.m2.output_gap_wired` info line
    per country per run confirms the OECD EO fetch succeeded
    (observation year + gap_pct logged).
- DE / FR / IT / ES / NL / PT / EA / GB (8 countries): pipeline emits
  `monetary_pipeline.builder_skipped` with a `NotImplementedError` citing
  Sprint C wire-ready state + CAL pointer.

The disk cache at `{cache_dir}/oecd_eo/` stores per-country 10y
history payloads with 24h TTL; first run per day hits OECD, subsequent
runs hit the cache. OECD EO is public — no rate-limit headroom
observed; aggregate daily fetch across 8 countries is ~8 HTTP calls
(well under polite-use thresholds).

MSC composite multi-country remains blocked on `CAL-CPI-INFL-T1-
WRAPPERS` → full M2 per-country → M1+M2+M4 uniformity. Once CPI +
forecast wrappers ship, Sprint C's wiring flips M2 live for all 8
Week-9 countries automatically (zero further code in the monetary
layer).

---

## 7. Final tmux echo

```
SPRINT C M2 OUTPUT GAP DONE: 6 commits on branch sprint-m2-output-gap-expansion

OECD EO connector shipped (public SDMX-JSON, no auth). 17 ISO2 codes
covered (16 T1 + EA17 aggregate) — pre-flight 2026-04-22 probe
validated GAP measure direct consumption (avoids HP-filter divergence
risk per brief §9).

2024 output gap values (OECD EO, % of potential GDP):
  US +0.54  DE -1.95  FR -0.35  IT +0.88  ES -1.15  NL -0.06
  PT +0.85  GB +0.05  JP -2.04  CA -0.04  AU +0.10  NZ -2.68
  CH +1.09  SE -2.55  NO -0.64  DK +0.17  EA17 -0.20 (probe)

8 M2 builders (JP/CA/AU/NZ/CH/SE/NO/DK) accept oecd_eo kwarg; raise
message acknowledges "output-gap live via OECD EO per Sprint C" when
fetch succeeds.

US M2 canonical CBO quarterly path PRESERVED (HALT-13 signature guard
shipped: test_us_builder_signature_unchanged_no_regression).

CAL-M2-T1-OUTPUT-GAP-EXPANSION marked CLOSED output-gap-half.
Residual: CAL-CPI-INFL-T1-WRAPPERS (CPI YoY + inflation-forecast
per country). When that lands, 8 scaffolds flip to full compute with
zero further L0 work.

Pipeline: _build_live_connectors instantiates OECDEOConnector
unconditionally + aclose-lifecycle.

Tests:
- 61 unit tests (test_oecd_eo.py) — 100% parse + cache + ISO2/3 dispatch.
- 27 Sprint C unit tests (test_builders.py) — parametrised across 8
  countries x 3 branches (success/unavailable/not-injected); facade
  pass-through; US signature regression guard.
- 8 new unsupported-country facade tests (DE/FR/IT/ES/NL/PT/EA/GB).
- 1 lifecycle test (test_daily_monetary_indices.py).
- 2 live integration canaries (@slow, 59s combined): 17-country smoke
  + facade end-to-end M2 CA raise assertion.

Full unit suite: 1681 pass (known-flaky re-run-to-green pattern per
docs/testing-strategy.md §4 — pipeline cross-test ordering flake
pre-existing, not Sprint C).
Full-project mypy: 118 files clean.
Ruff format + check: clean every commit. No --no-verify.

HALT triggers fired: 0 (HALT-0 did NOT fire — Sprint A precedent
inverted, full coverage). HALT-2 near-miss resolved by mapping
EA → EA17 legacy code (EA19/EA20 return NoRecordsFound for GAP).

Paralelo with Sprint B (per-country ERP): zero file conflicts
(Sprint B primary: overlays/erp/, daily_cost_of_capital.py, te.py;
Sprint C primary: connectors/oecd_eo.py, indices/monetary/builders.py,
daily_monetary_indices.py).

Brief format v3 third-use: §10 pre-merge checklist + §11
sprint_merge.sh valuable. §2 pre-flight outcome table recommendation
for v4 — sharper when probe validates full path vs scope-narrow.

Merge: ./scripts/ops/sprint_merge.sh sprint-m2-output-gap-expansion

Artifact: docs/planning/retrospectives/week10-sprint-m2-output-gap-report.md
```
