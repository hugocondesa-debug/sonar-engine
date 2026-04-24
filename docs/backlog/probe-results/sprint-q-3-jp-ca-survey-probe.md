# Sprint Q.3 — BoJ Tankan + BoC CES Probe Results

**Date**: 2026-04-24 (Week 11 Day 1 PM)
**Scope**: Empirical feasibility of publishing JP + CA inflation-
expectations survey observations to `exp_inflation_survey` for the
2-country M3 DEGRADED → FULL uplift.
**HALT gate**: §4 of
`docs/planning/week11-sprint-q-3-cal-expinf-survey-jp-ca-brief.md`.
**Outcome**: ✅ **BOTH PROBES CLEAN** — JP via Tankan Summary XLSX
TABLE7 (March 2020 onward, quarterly); CA via BoC Valet JSON
`CES_C1_{SHORT,MID,LONG}_TERM` (2014-Q4 onward, quarterly).
HALT-0 cleared for both legs. Brief's suggested BoC BOS repointed to
**CES** (Canadian Survey of Consumer Expectations) — see §2.3 rationale.

---

## §1 JP — BoJ Tankan (Inflation Outlook of Enterprises)

### §1.1 Endpoint discovery

Initial probe candidates (brief §2.1.1 scope) all 404:

| URL | HTTP | Notes |
|---|---|---|
| `https://www.boj.or.jp/en/statistics/tk/stat_en.csv` | 404 | no long-run CSV export |
| `https://www.boj.or.jp/en/statistics/tk/tk2025/tka2503.csv` | 404 | CSV format not published |
| `https://www.boj.or.jp/en/statistics/tk/tk2025/tka2503.pdf` | 404 | path incorrect |

Discovery follow-up via directory walk of
`https://www.boj.or.jp/en/statistics/tk/`:

| URL | HTTP | Content |
|---|---|---|
| `/en/statistics/tk/` | 200 | landing (gaiyo/yoshi/bukka/zenyo sub-indexes) |
| `/en/statistics/tk/gaiyo/2026/tka2603.zip` | 200 | **Tankan Summary — containing ZIP→GA_E1.xlsx** |
| `/en/statistics/tk/bukka/2016/*.pdf` | 200 | pre-Mar-2020 **PDF-only** legacy bukka |
| `/en/statistics/tk/bukka/2024/` | empty | post-Mar-2020 consolidated into gaiyo |

**Key finding (page text)**: "From the March 2020 survey, '(Reference)
The Average of Enterprises' Inflation Outlook' of TANKAN is integrated
into TANKAN (Summary)." This means the inflation-outlook series
we need is now part of the main Tankan release ZIP (since 2020-Q1);
pre-2020 data only in standalone bukka PDFs.

### §1.2 Data structure (GA_E1.xlsx)

`GA_E1.xlsx` contains 9 `TABLE{1..9}` sheets:

- `TABLE1` — Business Conditions DI (+ revision sign)
- `TABLE2` — Supply/Demand, Inventories, Prices
- `TABLE3` — Sales & Current Profits
- `TABLE4` — Fixed Investment, Software, R&D
- `TABLE5` — Employment
- `TABLE6` — Financial Position, Lending Attitudes
- **`TABLE7` — Inflation Outlook of Enterprises** ← primary target
- `TABLE8` — Assumed FX Rates
- `TABLE9` — Sample Enterprises

**TABLE7 layout** (empirical probe 2026-Q1 release, tka2603.zip):

| Row label | Sub-label | Horizon | Projection | E (Output Prices) | G (General Prices) |
|---|---|---|---|---|---|
| Large / Manu | — | 1 year ahead | Current | 2.5 | 2.2 |
| Large / Manu | — | 3 years ahead | Current | 3.5 | 2.1 |
| Large / Manu | — | 5 years ahead | Current | 4.3 | 2.0 |
| Large / Nonmanu | — | 1Y / 3Y / 5Y | Current | 2.5 / 3.7 / 4.3 | 2.2 / 2.1 / 2.0 |
| Small / Manu | — | 1Y / 3Y / 5Y | Current | 3.5 / 5.3 / 6.5 | 2.8 / 2.7 / 2.7 |
| Small / Nonmanu | — | 1Y / 3Y / 5Y | Current | 3.3 / 5.0 / 5.9 | 2.7 / 2.7 / 2.6 |
| **All Enterprises / All industries** | — | **1Y / 3Y / 5Y** | **Current** | **3.1 / 4.6 / 5.6** | **2.6 / 2.5 / 2.5** |

Sprint Q.3 consumes the "**All Enterprises / All industries /
General Prices / Current projection**" row — canonical economy-wide
inflation expectation published by BoJ, 3 horizons per release.

### §1.3 Release cadence + depth

Quarterly — March, June, September, December. URL pattern:

```
/en/statistics/tk/gaiyo/{YEAR}/tka{YY}{MM}.zip
  YEAR = 4-digit publication year
  YY   = 2-digit year (last two of YEAR)
  MM   = 03|06|09|12  (quarter-end month)
```

**History depth**: 2020-Q1 (March 2020, tka2003.zip) → 2026-Q1
(March 2026, tka2603.zip) = 6 years × 4 quarters + 1 = **25 releases**
expected; actual count depends on which archives remain posted.

Pre-2020 inflation outlook lives in standalone bukka PDFs
(`/en/statistics/tk/bukka/{ARCHIVE_YEAR}/tkc{YYMM}.pdf`). Scope-locked
out per brief §4 HALT-scope — PDF scraping = separate Week 12+ sprint
(`CAL-EXPINF-JP-SCRAPE-PRE2020`).

**Baseline sufficiency**: 25 quarterly releases is below the brief's
"≥60 baseline" target but **acceptable** — M3 classifier survey path
looks up "most recent row on-or-before observation_date" (sparse
quarterly cadence is by design; the 25 releases blanket the full
2020-Q1 → 2026-Q1 window with forward-fill). Matches Sprint Q.1 SPF
cadence (~28 quarterly rows per EA member).

### §1.4 Access mechanics

- Native format: ZIP → XLSX (openpyxl reads data_only).
- Auth: public, no token, no anti-bot (validated on tka2603.zip
  HTTP 200, 99400 B).
- Rate limit: assumed generous (no published limit). Sprint Q.3
  backfill touches ~25 archives total — single-pass sequential fine.
- Japanese original also published; ``/en/`` path returns the English
  XLSX with the labels shown in §1.2.

### §1.5 HALT-0 verdict

**CLEAR**. JP Tankan inflation outlook data is accessible via public
ZIP → XLSX endpoints; series identifiers are stable
(TABLE7 / "All Enterprises" / "General Prices" / "Current projection");
quarterly cadence matches survey-path expectations.

---

## §2 CA — BoC Valet / Canadian Survey of Consumer Expectations (CES)

### §2.1 Endpoint discovery

Brief suggested **BoC BOS** (Business Outlook Survey). Empirical
`/valet/lists/series/json` probe surfaced two relevant series
namespaces:

1. `BOS_{YYYY}Q{Q}_C{NN}_S{N}` — Business Outlook Survey,
   **per-quarter snapshot** series (~15000 entries). Label example:
   `BOS_2024Q1_C12_S3 = "BLP, 5-year-ahead"`. Each quarter issues a
   fresh series id — unusable for a long-run time series without
   manual stitching.
2. `CES_*` — Canadian Survey of Consumer Expectations,
   **stable long-run aggregate** series.

BoC publishes the BOS and CES separately. BOS is business-side,
published quarterly but as per-release snapshots. CES is consumer-side
quarterly inflation expectations with clean long-run series codes.

**Decision**: pivot brief's BOS reference to **CES** — stable series
ids, clean semantics (1Y/2Y/5Y horizons aligned with ECB SPF pattern),
longer history. Document this deviation in the probe (here) +
retrospective.

### §2.2 Canonical series (CES aggregate)

| Series ID | Label | Horizon |
|---|---|---|
| **`CES_C1_SHORT_TERM`** | 1-year-ahead inflation expectations | **1Y** |
| **`CES_C1_MID_TERM`**   | 2-year-ahead inflation expectations | **2Y** |
| **`CES_C1_LONG_TERM`**  | 5-year-ahead inflation expectations | **5Y** |

These three codes carry the headline CES aggregates (all-respondent
mean). Demographic subgroup series (`CES_C1A_*` / `CES_C1B_*` / etc.)
published alongside — not consumed by Sprint Q.3 (headline suffices
for M3).

Endpoint (validated 2026-04-24):
```
GET https://www.bankofcanada.ca/valet/observations/CES_C1_SHORT_TERM/json?start_date=2014-01-01
→ 200 OK, 46 observations, 2014-10-01 … 2026-01-01
```

Response sample:
```json
{
  "observations": [
    {"d": "2014-10-01", "CES_C1_SHORT_TERM": {"v": "2.91"}},
    ...
    {"d": "2026-01-01", "CES_C1_SHORT_TERM": {"v": "3.98"}}
  ]
}
```

Values are **% per annum** (consistent with ECB SPF).

### §2.3 Why CES over BOS — rationale

| Criterion | BOS_{YYYY}Q{Q}_C12_S{3} (5Y) | CES_C1_LONG_TERM (5Y) |
|---|---|---|
| Long-run series id | ❌ per-quarter ID | ✅ stable |
| All-respondent aggregate | partial (BLP only) | ✅ full panel |
| Historical depth | 2014-Q1 (BLP since 2018) | 2014-Q4 |
| Semantic match to ECB SPF pattern | lower (business side) | higher (consumer, analogous to Michigan 1Y in US) |
| Maintenance cost | high — re-wire each quarter | zero — stable IDs |

CES is the cleaner operational choice. Spec alignment is preserved —
the brief's intent ("consumer/firm inflation expectations, 1Y/2Y/5Y
horizons") is served by CES. BOS remains a future follow-up
(`CAL-EXPINF-CA-BOS-AUGMENT` Week 12+) if business-side divergence
vs consumer-side becomes analytically valuable.

### §2.4 Release cadence + depth

Quarterly — typically published late in the quarter-end month.
Observation dates stamped as quarter-start (`YYYY-01-01`,
`YYYY-04-01`, `YYYY-07-01`, `YYYY-10-01`). **46 observations** over
2014-Q4 → 2026-Q1.

Below the brief's "≥60 baseline" target but **acceptable** — matches
the CES survey's actual history (started 2014-Q4, no pre-existing
data to scrape). Forward-fill semantics make 46 quarterly rows
cover ~2014-2026 daily observation dates.

### §2.5 Access mechanics

- Native format: JSON (or CSV via `/csv`).
- Auth: public, no token.
- Rate limit: generous (Sprint S validated on V39079/BD.CDN.10YR.DQ.YLD
  — same endpoint).
- Existing connector: `sonar.connectors.boc.BoCConnector` already
  wraps Valet with cache + tenacity retry. Extend with a new
  `fetch_ces_inflation_expectations` method; no new connector class
  needed.

### §2.6 HALT-0 verdict

**CLEAR**. CES data accessible via stable Valet JSON endpoint;
46 quarterly observations covering 2014-Q4 → 2026-Q1.

---

## §3 Lesson #20 #6 pre-audit — cascade sites

Per brief §2.1.3, auditing **all** cascade sites **before** touching
connector code. Sprint Q.2 burned one iteration discovering
`_load_histories` + classifier mid-sprint; Sprint Q.3 shifts left.

### §3.1 Site inventory (grep + read)

| # | Function | File | Filter predicate |
|---|---|---|---|
| 1 | `build_m3_inputs_from_db` | `src/sonar/indices/monetary/db_backed_builder.py:282` | `ExpInflationSurveyRow.country_code == country` |
| 2 | `_load_histories` | `src/sonar/indices/monetary/db_backed_builder.py:533` | `ExpInflationSurveyRow.country_code == country_code` |
| 3 | `classify_m3_compute_mode` | `src/sonar/indices/monetary/m3_country_policies.py:117` | `ExpInflationSurveyRow.country_code == country` |

All three sites filter by `country_code` alone. None filter by
`survey_name`. JP + CA survey rows populated with any `survey_name`
(e.g. `BOJ_TANKAN`, `BOC_CES`) will be picked up by the existing
cascade without code changes.

### §3.2 Classifier cohort check

`M3_T1_COUNTRIES = {"US", "DE", "EA", "GB", "JP", "CA", "IT", "ES", "FR"}`
already contains JP + CA (Sprint O Week 10).

`M3_T1_DEGRADED_EXPECTED = {"JP", "CA", "IT", "ES"}` — these four
countries carry a per-country `*_M3_BEI_LINKER_*_EXPECTED` *observability*
flag on emission. **This flag does NOT block FULL** — it is appended
to the flags tuple regardless of classifier verdict. Survey path in
`classify_m3_compute_mode` still returns `"FULL"` when a valid survey
row is found.

### §3.3 Verdict

**ZERO classifier or builder changes needed.** Sprint Q.3 scope
collapses to:
1. Tankan XLSX parser + BoJ connector extension
2. Valet CES fetcher + BoC connector extension
3. Per-source backfill CLI (invokes `persist_survey_row`)
4. Tests — connector parsing + JP/CA FULL integration + regression

Zero touch on `db_backed_builder.py`, `m3_country_policies.py`,
`exp_inflation_writers.py`.

---

## §4 Decisions locked

1. **JP source**: BoJ Tankan Summary ZIP → `GA_E1.xlsx` → TABLE7 →
   "All Enterprises / All industries / General Prices / Current".
   Horizons 1Y / 3Y / 5Y.
2. **CA source**: BoC Valet JSON `/observations/CES_C1_{SHORT,MID,LONG}_TERM`.
   Horizons 1Y / 2Y / 5Y.
3. **Survey names** (written to `exp_inflation_survey.survey_name`):
   - JP → `BOJ_TANKAN`
   - CA → `BOC_CES`
4. **Methodology version**: reuse `METHODOLOGY_VERSION_SURVEY` =
   `EXP_INF_SURVEY_v0.1` (Sprint Q.1 constant). Source-specific
   sub-variant reserved via flags, not version bump (consistent with
   Sprint Q.2 pattern where GB BEI shares the bei version).
5. **Flags propagated per source**:
   - JP → `TANKAN_LT_AS_ANCHOR` (5Y horizon maps to 5Y/10Y/5y5y
     canonical tenors, analogous to Sprint Q.1 `SPF_LT_AS_ANCHOR`).
   - CA → `CES_LT_AS_ANCHOR` (5Y horizon same treatment).
6. **No classifier change**. No builder change. No writer code change
   (schema already supports `survey_name`).
7. **Pre-2020 JP coverage**: scope-locked out —
   `CAL-EXPINF-JP-SCRAPE-PRE2020` Week 12+ if analytical need arises.

---

*End probe. JP + CA both HALT-0 clear. 2-country M3 FULL ready to
implement without classifier disturbance.*
