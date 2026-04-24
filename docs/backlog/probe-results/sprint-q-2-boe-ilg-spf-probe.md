# Sprint Q.2 — BoE ILG + SEF availability probe

**Data**: 2026-04-24 Week 11 Day 1
**Operator**: Hugo + CC (VPS `sonar-engine`)
**Goal**: determine whether Bank of England publishes, over a
scripted-HTTP path, inflation-linked gilt (ILG) breakeven data and/or
Survey of External Forecasters (SEF) inflation expectations sufficient
to populate `exp_inflation_bei` / `exp_inflation_survey` for GB → M3
FULL.

---

## §1 — IADB CSV endpoint (primary path per brief §2.1.1)

**Status**: **BLOCKED** (as documented by the existing
`src/sonar/connectors/boe_database.py` header — confirmed re-probe
2026-04-24).

Re-probe command:

```bash
curl -sSL -o /tmp/boe_probe.txt -w "HTTP=%{http_code} URL=%{url_effective}\n" \
  "https://www.bankofengland.co.uk/boeapps/database/_iadb-FromShowColumns.asp?csv.x=yes&Datefrom=01/Jan/2024&Dateto=01/Apr/2026&SeriesCodes=IUDAMIH&CSVF=TN&UsingCodes=Y&VPD=Y" --max-time 20
# HTTP=200 URL=https://www.bankofengland.co.uk/boeapps/database/ErrorPage.asp?ei=1809&ui=26072013808
# Body: <!DOCTYPE html>... (Akamai block page)
```

Tried variants that failed identically:

- Plain `curl`.
- Browser-mimicking `User-Agent: Mozilla/5.0 ... Chrome/120 Safari/537.36`.
- `Accept-Language: en-GB`, `Referer:
  https://www.bankofengland.co.uk/boeapps/database/index.asp`,
  cookie jar.

Every request follows a 302 → `ErrorPage.asp?ei=1809&ui=…`. The VPS IP is
clearly blacklisted by BoE's Akamai shield. Matches the empirical finding
recorded in the `BoEDatabaseConnector` docstring from Sprint I (Week 8,
2026-04-21). **Not resolvable from this infra without a proxy.**

**HALT-0 trigger would fire here.** But §2 below finds a workable
non-IADB path.

## §2 — BoE yield-curves content-store (non-IADB path — VIABLE)

BoE also publishes the raw fitted yield-curve data as daily Excel
spreadsheets, distributed via the public content-store CDN (same
origin as the press-release PDFs). The content-store is **not** behind
the IADB Akamai block.

**Discovery page**: `https://www.bankofengland.co.uk/statistics/yield-curves`

**Canonical archives** (confirmed 200 OK, public CDN):

| Archive | Contents | Size |
|---|---|---|
| `glcnominalddata.zip` | Daily nominal gilt curves (5Y–40Y spot + forwards) | — |
| `glcrealddata.zip` | Daily real gilt curves (inflation-linked linker-derived) | — |
| **`glcinflationddata.zip`** | **Daily implied inflation curves (BEI, NSS-fitted from nominal−real)** | **~24 MB** |
| `blcnomddata.zip` | Daily bank-liability curves (OIS derived, nominal) | — |
| `oisddata.zip` | Daily OIS curves | — |

Monthly siblings also exist (`glcinflationmonthedata.zip`, etc.).

**Inspection of `glcinflationddata.zip`** — contains 7 `.xlsx` files
split by date range:

```
GLC Inflation daily data_1985 to 1989.xlsx
GLC Inflation daily data_1990 to 1994.xlsx
GLC Inflation daily data_1995 to 1999.xlsx
GLC Inflation daily data_2000 to 2004.xlsx
GLC Inflation daily data_2005 to 2015.xlsx
GLC Inflation daily data_2016 to 2024.xlsx
GLC Inflation daily data_2025 to present.xlsx   (mtime 2026-04-01)
```

**Schema per file**: 5 sheets — `info`, `1. fwds, short end`,
`2. fwd curve`, `3. spot, short end`, **`4. spot curve`**. The spot curve
sheet is the canonical BEI — zero-coupon implied inflation at each
tenor, fitted via BoE's NSS-style spline.

Sheet-4 header layout (verified):

- Row 4, col A = "years:" label; row 4 cols B… carry tenor in years
  (2.5, 3.0, 3.5, 4.0, … 40.0 …).
- Row 6+ = data; col A = `datetime`, cols B+ = implied inflation rate
  in **percent** (e.g. `3.49` → 3.49 %).

**Tenor → column index** (confirmed):

| Tenor (years) | Column index (0-based) | Excel column |
|---|---|---|
| 5.0 | 6 | G |
| 10.0 | 16 | Q |
| 15.0 | 26 | AA |
| 20.0 | 36 | AK |
| 25.0 | 46 | AU |
| 30.0 | 56 | BE |
| 40.0 | 76 | BY |

**Coverage check** (2025 to present file, 2026-04-24 inspection):

- First data row: 2025-01-02 (5Y=3.5073, 10Y values present from col Q).
- Last data row: **2026-03-31** (5Y=4.4912 decimal %, 10Y populated).
- ~330 rows total → weekday cadence, reflects pre-freshness ~24 days
  (BoE publishes with a lag).

Historical archive 2016–2024 has ~2250 rows covering those 9 years →
easily satisfies the brief's ≥60-row baseline.

## §3 — BoE SEF (Survey of External Forecasters)

Out of Sprint Q.2 scope per brief §scope-locks ("BoE ILG only; SEF
fallback Week 12 if ILG works"). Probed the MPR page URL briefly —
returns HTML with embedded tables, no JSON API. Will defer to Sprint
Q.2.x or later (new CAL `CAL-EXPINF-GB-SEF` if BEI-alone proves
insufficient downstream).

## §4 — Lesson #20 #5 inventory

`grep _query_expinf|_query_survey|_load_histories|exp_inflation_bei` in
`src/sonar/indices/monetary/db_backed_builder.py`:

**Helpers touching expinf data** (Sprint Q.2 MUST extend each that
currently reads only `IndexValue(EXPINF_CANONICAL)` or
`exp_inflation_survey`):

1. `_query_expinf` — canonical IndexValue reader. **No change** — BEI
   fallback triggers only when canonical miss.
2. `_query_survey` — exp_inflation_survey on-or-before reader. **No
   change** — BEI fallback runs after survey miss.
3. `build_m3_inputs_from_db` main function — **EXTEND**: add BEI
   fallback branch after the Sprint Q.1.1 survey branch
   (`survey_row is None` → try BEI; `bei_row is None` → the existing
   `return None`). Emit `M3_EXPINF_FROM_BEI` flag.
4. `_load_histories` helper — **EXTEND** (Lesson #20 #5, the whole
   point of Q.2 vs Q.1.1): when neither `expinf_rows` nor
   `survey_rows` yield a match for a `fwd.date`, also try the BEI
   table forward-fill. Same `_latest_<row>_on_or_before` pattern as
   survey.

**New helpers to add** (mirror the survey pair):

- `_query_bei(session, country_code, observation_date)` — most recent
  `exp_inflation_bei` row on-or-before date.
- `_latest_bei_on_or_before(bei_rows, target_date)` — list walker.
- `_bei_tenors_bps(row)` — `bei_tenors_json` → tenor→bps dict.
- `M3_EXPINF_FROM_BEI_FLAG` constant.

## §5 — Decision

**Go** on BoE yield-curves ZIP path. HALT-0 does not fire.

- **Primary connector** (new): `BoEYieldCurvesConnector` reading
  `glcinflationddata.zip` → parse sheet `4. spot curve` → daily BEI
  rows for 5Y / 10Y / 15Y / 20Y / 30Y.
- **5Y5Y derivation**: computed in the BEI writer as
  `bei_5y5y = 2 × bei_10y − bei_5y` (continuous-zero forward
  identity) — BoE does not publish a 5Y5Y spot directly, but given
  5Y + 10Y spots the forward follows algebraically and is bit-exact
  with the Sprint Q.1 convention.
- **Connector pattern**: NOT a sibling of `boe_database.py`; the
  Akamai-blocked IADB endpoint is orthogonal. New module
  `src/sonar/connectors/boe_yield_curves.py`. Leaves
  `boe_database.py` exactly as-is (preserves the MSC GB fallback
  cascade).
- **Backfill depth**: 2020-01-01 → 2026-04-24 from the
  `GLC Inflation daily data_2016 to 2024.xlsx` +
  `2025 to present.xlsx` files only (ignore 1985–2015 archives —
  out of scope, no downstream consumer).

Proceeding to connector implementation (C2).
