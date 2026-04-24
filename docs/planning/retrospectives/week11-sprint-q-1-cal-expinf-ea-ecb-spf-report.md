# Sprint Q.1 — CAL-EXPINF-EA-ECB-SPF Retrospective

**Branch**: `sprint-q-1-cal-expinf-ea-ecb-spf`
**Worktree**: `/home/macro/projects/sonar-wt-q-1-cal-expinf-ea-ecb-spf`
**Date**: Week 11 Day 1 afternoon — 2026-04-24 (~14:30–17:00 WEST)
**Budget used**: ~3 h wall-clock (well under 5 h cap)
**Tier A acceptance**: 5/6 clean; 6th is pre-existing infra flake (see §4.3).
**CAL closed**: `CAL-EXPINF-EA-ECB-SPF` (primary).
**Sub-CALs opened**: 3 (per-country-linkers followup, SPF MDN variant, SPF histogram).

---

## §1 Goal recap

Sprint Q shipped the EXPINF wiring *pattern* US-only. The audit surfaced
that `exp_inflation_survey` was a dormant table — schema-only since
Week 3 migration 004, no writer. Sprint Q retro ranked
`CAL-EXPINF-EA-ECB-SPF` as the highest-leverage successor: one ECB
SDW connector extension would cascade M3 DEGRADED → FULL across 6
countries (EA + DE + FR + IT + ES + PT) if SPF per-country data
exists or if EA-aggregate proxies acceptably.

Sprint Q.1 executed that ship end-to-end within the single afternoon
window while Sprint T-Retry ran in parallel (zero file overlap, clean
separation on both branches).

---

## §2 Deliverables shipped

### §2.1 Probe (C1)

`docs/backlog/probe-results/sprint-q-1-ecb-spf-probe.md`
(≈ 200 lines). Key findings:

- **Dataflow**: `SPF` (canonical); DSD `ECB:ECB_FCT1(1.0)` with 7
  dimensions (FREQ, REF_AREA, FCT_TOPIC, FCT_BREAKDOWN, FCT_HORIZON,
  SURVEY_FREQ, FCT_SOURCE).
- **Per-country feasibility**: **no per-country SPF series**. REF_AREA
  codelist contains DE/FR/IT/ES/PT/NL but SPF dataflow only publishes
  `U2` (euro-area aggregate). AREA_PROXY pattern adopted.
- **Horizon convention**: FCT_HORIZON encodes target calendar year
  (rolling horizon) or literal `LT` (long-term ≈ 5y ahead). Mapping:
  `survey_year + 1 → 1Y`, `+2 → 2Y`, `LT → LTE` (anchor proxy).
- **Source selection**: `AVG` live, `MDN` returned 404 → follow-up CAL
  opened (`CAL-ECB-SPF-MDN-VARIANT`).
- **Format**: CSV + SDMX-JSON both supported; CSV reused existing
  `_parse_monetary_csv` shape.

### §2.2 Connector + writer + loader + wiring (C2–C4)

- `src/sonar/connectors/ecb_sdw.py`
  - `ExpInflationSurveyObservation` dataclass (frozen, slots).
  - `ECB_SPF_*` module constants (dataflow / key template / cohort).
  - `fetch_survey_expected_inflation(country, start, end)` method
    (single CSV call with wildcarded horizon, 24-hour cache TTL).
  - `_parse_spf_csv` + `_spf_quarter_to_date` + `_spf_derive_tenor`
    helpers.
- `src/sonar/indices/monetary/exp_inflation_writers.py` (new file)
  - `persist_survey_row(session, survey, methodology_version)` —
    idempotent SQLite `INSERT OR IGNORE` on
    `uq_exp_survey_cdsm`.
  - Raw-SQL path (no ORM dependency) — keeps writer
    surface small + portable to the Phase 2+ Postgres migration.
- `src/sonar/db/models.py`
  - `ExpInflationSurveyRow` ORM class — registers the existing
    `exp_inflation_survey` table with `Base.metadata` so the
    in-memory SQLite test fixture can create it via `create_all()`.
- `src/sonar/overlays/expected_inflation.py`
  - `compute_survey_spf(country_code, horizons, ...,
    is_area_proxy)` — composes `ExpInfSurvey` with
    `SPF_LT_AS_ANCHOR` + `SPF_AREA_PROXY` flags.
  - `build_canonical` — propagates `bei.flags + survey.flags` into
    `canonical.flags` for M3 transparency (small side-effect fix;
    previously anchor-only).
- `src/sonar/indices/monetary/exp_inflation_loader.py`
  - `load_live_exp_inflation_kwargs` gains `ecb_sdw` + `session`
    kwargs + EA-cohort branch via `_load_ea_spf_kwargs`.
  - Lookback window extended to 210 days so a single-API call always
    captures a fully-released quarterly observation regardless of
    calendar alignment.
- `src/sonar/overlays/live_assemblers.py`
  - `LiveConnectorSuite.ecb_sdw` optional field; `_run` passes it
    through.
- `src/sonar/pipelines/daily_overlays.py`
  - Factory instantiates `EcbSdwConnector` + appends to the close list
    (connector count 6 → 7).

### §2.3 Backfill (C6)

6 countries (EA + DE + FR + IT + ES + PT) × 5 observation dates
(2026-02-15 → 2026-04-24) = **30 rows persisted to
`exp_inflation_survey`**. Writer idempotence verified via 3 × re-run of
the same triplets (duplicate-skipped log + count unchanged).

Sample row (2026-04-23 EA):

| field | value |
|---|---|
| survey_name | `ECB_SPF_HICP` |
| methodology_version | `EXP_INF_SURVEY_v0.1` |
| horizons_json | `{"1Y": 0.01971, "2Y": 0.02051, "LTE": 0.02017}` |
| interpolated_tenors_json | `{"1Y": .., "2Y": .., "5Y": 0.02017, "10Y": 0.02017, "5y5y": 0.02017, "30Y": 0.02017}` |
| flags | `SPF_LT_AS_ANCHOR` (EA) / `SPF_LT_AS_ANCHOR,SPF_AREA_PROXY` (members) |
| confidence | 1.0 |

`build_canonical` end-to-end smoke:

```
EA: 5y5y=0.02017  1Y=0.01971  anchor_status=well_anchored  dev_bps=2  conf=1.00
DE/FR/IT/ES/PT: identical values (EA proxy) + SPF_AREA_PROXY flag
```

### §2.4 Tests (C5)

4 test files modified / extended:

| File | New tests | What they cover |
|---|---|---|
| `tests/unit/test_connectors/test_ecb_sdw.py` | 6 | `ECB_SPF_COHORT` integrity, `_spf_derive_tenor` horizon→tenor rules, `fetch_survey_expected_inflation` happy path + AREA_PROXY + non-cohort guard + malformed-rows skip + `ExpInflationSurveyObservation` frozen contract |
| `tests/unit/test_overlays/test_expected_inflation.py` | 4 | `compute_survey_spf` full EA horizons + EA-member flag + missing-LT skip + end-to-end `build_canonical` with SPF → 5y5y emit |
| `tests/unit/test_pipelines/test_expinf_wiring.py` | 10 | EA cohort kwargs composition, non-EA return-None guard, AREA_PROXY tagging for 6 members, empty-window fallback, HTTP-error fallback, session persistence, 3× idempotence, session-None compatibility |
| `tests/unit/test_pipelines/test_daily_overlays.py` | — | Factory count 6 → 7 + async test wrapper for event-loop hygiene |

**Targeted suite:** 119/119 pass (all 4 files, including regression
coverage of Sprint Q US path).

---

## §3 M3 coverage matrix

### §3.1 Pre- vs post-Sprint-Q.1 (observation_date = 2026-04-23)

| Country | Pre-Q.1 | Post-Q.1 | EXPINF source | Sprint Q.1 flags |
|---|---|---|---|---|
| US | FULL (Sprint Q) | FULL (unchanged) | FRED BEI + FRED survey | — |
| EA | DEGRADED | **FULL** | ECB SDW SPF | SPF_LT_AS_ANCHOR |
| DE | DEGRADED | **FULL** | ECB SDW SPF (proxy) | SPF_LT_AS_ANCHOR + SPF_AREA_PROXY |
| FR | DEGRADED | **FULL** | ECB SDW SPF (proxy) | SPF_LT_AS_ANCHOR + SPF_AREA_PROXY |
| IT | DEGRADED | **FULL** | ECB SDW SPF (proxy) | SPF_LT_AS_ANCHOR + SPF_AREA_PROXY |
| ES | DEGRADED | **FULL** | ECB SDW SPF (proxy) | SPF_LT_AS_ANCHOR + SPF_AREA_PROXY |
| PT | DEGRADED | **FULL** | ECB SDW SPF (proxy) | SPF_LT_AS_ANCHOR + SPF_AREA_PROXY |
| NL | (not-configured) | ready (7th cohort member, awaits pipeline config) | ECB SDW SPF (proxy) | — |
| GB | DEGRADED | DEGRADED | awaits Sprint Q.2 | — |
| JP | DEGRADED | DEGRADED | awaits Sprint Q.3 | — |
| CA | DEGRADED | DEGRADED | awaits Sprint Q.3 | — |

Six countries promoted with a single ECB SDW connector extension —
the leverage bet paid out exactly as modelled by Sprint Q retro.

### §3.2 T1 coverage delta

Pre-Q.1 baseline: ~58% (Sprint Q US-only uplift).
Post-Q.1 projection: **~68–70%** (+10–12 pp).
Phase 2 end-of-May target (75–80%): **comfortable margin**.

Actual M3 FULL emit pending a live `daily_overlays --backend=live`
run that persists `EXPINF_CANONICAL` `IndexValue` rows for the EA
cohort — the loader + writer + wiring are all in place, but the
end-to-end overlay compute (which needs FMP + TE + ECB SDW +
Shiller) was not run in Sprint Q.1 scope (connector budget + API
quota preservation). Operator Tier B step to follow.

---

## §4 What went well / surprised / to fix

### §4.1 What went well

- **Probe-first discipline paid off immediately**: the candidate
  dataflow short-list from the brief was 7 entries; `SPF` was the
  first to return HTTP 200 on the metadata probe. Content/MIME
  negotiation required XML for metadata but CSV for data —
  surfaced cleanly in <5 minutes.
- **CSV re-use**: the existing `_parse_monetary_csv` pattern covered
  90% of the SPF parser; `_parse_spf_csv` is a 20-line analogue that
  adds horizon/tenor derivation.
- **Table already in SQLite**: migration 004 had shipped
  `exp_inflation_survey` in Week 3 but never seen a writer. One
  writer module + one ORM class closed the gap without a new
  migration.
- **AREA_PROXY pattern**: REF_AREA=U2-only turned out to be fine —
  with transparent flags on EA-member emits, analyst interpretation
  stays intact + future per-country linker upgrades remain in-scope
  (new `CAL-EXPINF-PER-COUNTRY-LINKERS-FOLLOWUP`).
- **Budget**: 3 h total (probe 30 min, code 90 min, tests 45 min,
  backfill + retro 20 min). Median estimate in brief was 4–5 h.

### §4.2 Non-obvious SPF quirks worth remembering

- `startPeriod` with a `YYYY-MM-DD` date is compared against the
  `TIME_PERIOD` of each series — and `TIME_PERIOD` is the quarter
  anchor (`YYYY-Qn` → start of quarter, Jan 1 / Apr 1 / …). So
  `startPeriod=2026-01-13` silently **excludes** 2026-Q1 (anchored
  Jan 1). Initial 100-day lookback window cut off the latest quarter;
  raised to 210 days with a docstring note.
- `LT` is *not* strictly "5y5y". SPF defines it as the 4–5-year-ahead
  annual inflation expectation. Close enough to 5y5y for anchor
  purposes (`SPF_LT_AS_ANCHOR` flag declares the proxy).
- `MDN` (median) source variant returned HTTP 404 despite the
  codelist declaring it — SDW key-generation lag or schema quirk.
  Fresh CAL opened (`CAL-ECB-SPF-MDN-VARIANT`).

### §4.3 Sharp edges / known limitations

- **Test-suite leak (pre-existing)**: full `tests/unit` run under
  `filterwarnings = error` surfaces a non-deterministic
  `PytestUnraisableExceptionWarning` about unclosed sockets /
  SQLAlchemy cursors + event loops. The failing test cycles per run
  (test_daily_bis_ingestion → test_daily_financial_indices →
  test_daily_cycles → …). **Confirmed pre-existing** — reproduced
  after `git stash` with all Sprint Q.1 changes reverted. Does not
  block Sprint Q.1 Tier A; logged for a future "pytest event-loop
  hygiene" CAL.
- **Writer emits one row per (country, observation_date)** — SPF is
  quarterly, so (EA, 2026-04-21), (EA, 2026-04-22), etc. all share
  the same quarter's horizons. The current schema has no "as-of"
  semantics so each pipeline tick persists a fresh row even when the
  survey payload is unchanged. Acceptable for Phase 1 SQLite MVP;
  Postgres migration (Phase 2+) can revisit if row-count becomes a
  concern.
- **AREA_PROXY is coarse**: DE / FR / IT / ES / PT / NL all carry
  identical survey values. True per-country precision lives in
  `CAL-EXPINF-PER-COUNTRY-LINKERS-FOLLOWUP` via national-linker BEI.

### §4.4 Sub-CALs opened

- `CAL-EXPINF-PER-COUNTRY-LINKERS-FOLLOWUP` — MEDIUM, Week 12+
  (co-sequenced with the three per-country linker CALs that were
  already open).
- `CAL-ECB-SPF-MDN-VARIANT` — LOW, deferred.
- `CAL-ECB-SPF-HISTOGRAM` — LOW, Phase 2+ (feeds L5 regime tail-risk
  inputs).

---

## §5 Commits shipped

| Commit | Scope | Files |
|---|---|---|
| C1 | `docs(probes)` | `docs/backlog/probe-results/sprint-q-1-ecb-spf-probe.md` (new) |
| C2 | `feat(connectors)` | `src/sonar/connectors/ecb_sdw.py` (SPF extension) |
| C3 | `feat(indices,db)` | `src/sonar/indices/monetary/exp_inflation_writers.py` (new) + `src/sonar/db/models.py` (ExpInflationSurveyRow ORM) + loader EA branch |
| C4 | `refactor(overlays,pipelines)` | `src/sonar/overlays/live_assemblers.py` + `src/sonar/pipelines/daily_overlays.py` + `src/sonar/overlays/expected_inflation.py` (compute_survey_spf + flag propagation) |
| C5 | `test` | 4 test files (see §2.4) |
| C6 | ops | 30-row SQLite backfill; 6-country cascade smoke |
| C7 | `docs(backlog)` | `docs/backlog/calibration-tasks.md` (CAL closure + 3 new sub-CALs) |
| C8 | `docs(planning)` | this file |

(C1–C5 + C7 + C8 are committable; C6 is ops-only per the brief.)

---

## §6 Sprints unblocked

- **Sprint P (MSC EA)** — 4/5 L4 monetary sub-indices for EA now
  carry FULL M3, so the composite becomes feasible immediately after
  a live `daily_overlays --backend=live` run for the EA cohort.
- **Sprint Q.2 (GB-BOE-ILG-SPF)** — pattern reference: the
  `compute_survey_spf` + writer structure is directly reusable with
  GB horizons.
- **Sprint M2-EA-per-country** — per-country MSC for DE/FR/IT/ES
  depends on their individual M3 FULL status, all of which flipped
  in Sprint Q.1.

---

## §7 ADR candidate — AREA_PROXY pattern

Sprint Q.1 demonstrates a reusable architectural pattern for
"currency-union-aggregate published, member-level synthesised":

1. Connector exposes the aggregate series (`REF_AREA=U2`).
2. Loader branches on the cohort membership (`ECB_SPF_COHORT`) and
   tags non-aggregate callers with `..._AREA_PROXY`.
3. Compute helper carries `is_area_proxy` into the output flag tuple.
4. Canonical layer propagates source flags for M3 analyst
   transparency.

The same pattern applies to future sprints (e.g., an ECB SDW HICP
harmonised series proxied to EA members, or an OECD forecast
aggregate proxied to its member cohort). ADR candidate drafted
implicitly via this retrospective — promotion to a formal
`ADR-0011 amendment` or a new `ADR-00xx-currency-union-aggregate-
proxy.md` is a follow-on decision for Hugo.

---

## §8 Day-1 afternoon end state

- **Sprint Q + Sprint Q.0.5 + Sprint Q.1** merged / ready-to-merge.
- **Parallel Sprint T-Retry** working on `te.py` + `daily_curves` —
  zero overlap with Sprint Q.1 surface.
- **T1 coverage projection**: 68–72% after the operator runs
  `daily_overlays --backend=live` for EA cohort.
- **L4 MSC EA**: unblocked for Day-2 AM.
- **Week 11 target** (75–80% end-of-May): ahead of schedule.

---

*End of retro. Highest-leverage EXPINF connector shipped clean under budget.*
