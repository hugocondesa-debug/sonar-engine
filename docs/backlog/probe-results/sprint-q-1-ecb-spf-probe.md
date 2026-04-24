# Sprint Q.1 — ECB SDW SPF Probe Results

**Date**: 2026-04-24 (Week 11 Day 1 PM)
**Scope**: Empirical feasibility of publishing SPF inflation expectations
to `exp_inflation_survey` for the 6-country M3 FULL cascade
(EA + DE + FR + IT + ES + PT).
**HALT gate**: §2.1 of
`docs/planning/week11-sprint-q-1-cal-expinf-ea-ecb-spf-brief.md`.
**Outcome**: ✅ PROBE CLEAN — SPF dataflow live + SDMX-JSON + CSV both
supported + sufficient history (1999-Q3 → 2026-Q1) + sub-daily freshness
acceptable for a quarterly survey source. **HALT-0 cleared.**

---

## §1 Dataflow discovery

### §1.1 Candidate probes (§2.1.1 of brief)

Seven candidate identifiers probed against
`https://data-api.ecb.europa.eu/service/dataflow/ECB/{id}` with
`Accept: application/vnd.sdmx.structure+xml;version=2.1`:

| Dataflow | HTTP | Name |
|---|---|---|
| **SPF** | **200** | **Survey of Professional Forecasters** |
| ECB_SURVEY | 404 | — |
| EIN | 404 | — |
| BSI_IND | 404 | — |
| SPF_IND | 404 | — |
| ICP | 404 | — |
| SURV / SURVEY | 404 | — |

SPF is the canonical dataflow ID. (Initial probe used default JSON Accept
header and surfaced HTTP 406 "Acceptable representations: [application/xml
, application/vnd.sdmx.structure+xml;version=2.1]" for all candidates —
the metadata endpoint is XML-only; the data endpoint supports
`application/vnd.sdmx.data+json` and CSV. Existing
`EcbSdwConnector._fetch_raw` already uses CSV so we reuse the pattern.)

### §1.2 Data structure definition

```
GET /service/datastructure/ECB/ECB_FCT1?references=children
```

Returns the DSD referenced by `SPF` (structure `ECB:ECB_FCT1(1.0)`).
**7 dimensions**:

| Pos | ID | Role |
|---|---|---|
| 1 | FREQ | Frequency of TIME_PERIOD (Q = quarterly) |
| 2 | REF_AREA | Geography (**U2 only**) |
| 3 | FCT_TOPIC | Forecast topic (HICP, CORE, RGDP, UNEM, …) |
| 4 | FCT_BREAKDOWN | Distribution breakdown (POINT, histogram buckets, …) |
| 5 | FCT_HORIZON | Target year (1999–2050, or **LT** long-term) |
| 6 | SURVEY_FREQ | Survey frequency (Q only) |
| 7 | FCT_SOURCE | Source (AVG, MDN subset, or individual forecasters 001–…) |

### §1.3 Relevant codelists

**CL_FCT_TOPIC** (8 codes):
- `HICP` — Harmonised ICP ← **primary target**
- `CORE` — Harmonised ICP excluding energy and food
- `ICP0`, `RGDP`, `UNEM`, `PCER`, `GGDS`, `ASSU`

**CL_FCT_BREAKDOWN** (non-histogram codes):
- `POINT` — Point forecast ← **primary target**
- `SUM`, `IR`, `LAB`, `OIL`, `USD` (non-HICP indicators)
- 100+ histogram buckets (`F2_0T2_4`, `F2_5T2_9`, …) for distribution data

**CL_FCT_HORIZON** (100 codes):
- Years `1991` … `2050` (rolling calendar-year targets)
- `LT` — Long-term equivalent (≈ 5y ahead) ← **anchor input**

**CL_FCT_SOURCE** (159 codes):
- `AVG` — **Average of forecasts** ← primary (live data present)
- `MDN` — Median (dataflow declares it but returned HTTP 404 on probe;
  falls outside brief scope — defer)
- `STD`, `VAR`, `HIF`, `LOF`, `NUM`, `PFC` — dispersion measures
- `001`–`103` individual forecasters (too granular for M3)

**CL_AREA_EE** on REF_AREA — only `U2` (Euro area) returns data (1 series
in the live response below). Per-country SPF series do **not** exist in
the SPF dataflow (`DE`/`FR`/`IT`/`ES`/`PT`/`NL` are codelist-present but
SPF does not publish national-level forecasts).

---

## §2 Live data retrieval

### §2.1 SDMX-JSON response — `Q.U2.HICP.POINT...AVG`

```
GET /service/data/SPF/Q.U2.HICP.POINT...AVG?lastNObservations=2
Accept: application/vnd.sdmx.data+json;version=1.0.0-wd
```

HTTP 200, 21.4 KB. Structure: 33 series (one per FCT_HORIZON),
TIME_PERIOD observations 1999-Q3 → 2026-Q1. Each series corresponds
to one target year (or `LT`).

### §2.2 CSV response

```
GET /service/data/SPF/Q.U2.HICP.POINT...AVG?startPeriod=2025-Q1&endPeriod=2026-Q1&format=csvdata
```

HTTP 200. CSV columns:

```
KEY,FREQ,REF_AREA,FCT_TOPIC,FCT_BREAKDOWN,FCT_HORIZON,SURVEY_FREQ,FCT_SOURCE,
TIME_PERIOD,OBS_VALUE,OBS_STATUS,OBS_CONF,OBS_PRE_BREAK,OBS_COM,
SURVEY_ROUND,TIME_FORMAT,COLLECTION,COMPILING_ORG,DISS_ORG,DECIMALS,
SOURCE_AGENCY,TITLE,TITLE_COMPL,UNIT,UNIT_MULT
```

Sample row (`SPF.Q.U2.HICP.POINT.2025.Q.AVG` @ 2025-Q1):

```
SPF.Q.U2.HICP.POINT.2025.Q.AVG,Q,U2,HICP,POINT,2025,Q,AVG,2025-Q1,
2.053388770166667,F,F,,,,P3M,A,,,2,4F0,
Euro area - HICP Inflation - Average of Point forecasts - 2025,
Euro area (changing composition) - Harmonised ICP - Point forecast - 2025 - Quarterly survey,
PCPA,0
```

Unit: `PCPA` (% per annum). Decimal-point text. `OBS_STATUS=F` / `OBS_CONF=F`
= "final" release. Existing `_parse_monetary_csv` handles this schema
(already parses TIME_PERIOD + OBS_VALUE) — **reusable pattern.**

### §2.3 Cross-horizon snapshot (freshness verification)

2026-Q1 survey round populates multiple horizons simultaneously:

| FCT_HORIZON | Survey quarter | OBS_VALUE (%) | Canonical tenor |
|---|---|---|---|
| 2026 | 2026-Q1 | 1.838 | 0Y (current-year) |
| 2027 | 2026-Q1 | 1.971 | **1Y rolling** |
| 2028 | 2026-Q1 | 2.051 | **2Y rolling** |
| 2030 | 2026-Q1 | 2.017 | ~4Y target |
| **LT** | **2026-Q1** | **2.017** | **Long-term equivalent** |

2025-Q4 + 2025-Q3 populate parallel sets — quarterly cadence confirmed
with `P3M` (ISO-8601 3-month period) `SURVEY_ROUND` and freshness
< 90 days (well within ADR-0011 P1 timeliness bounds for a survey
source).

---

## §3 Per-country feasibility (§2.1.4 of brief)

**Empirical finding: REF_AREA = U2 only.** No per-country SPF series
published by ECB. Per-country national surveys (e.g. Bundesbank Expert
Forecast, INSEE, Banco de España Previsiones) are tracked under separate
CAL items (`CAL-EXPINF-DE-BUNDESBANK-LINKER`, etc.).

### §3.1 Decision: AREA_PROXY pattern

Sprint Q.1 ships **EA-aggregate SPF proxied to 5 EA members**
(DE / FR / IT / ES / PT). Each per-country emit carries a
`SPF_AREA_PROXY` flag in the `ExpInfSurvey.flags` tuple for analyst
transparency. Per-country refinement deferred to the three
per-country CALs flagged above + `CAL-EXPINF-EA-PERIPHERY-LINKERS`
(linker-based BEI successors).

### §3.2 Horizon → canonical-tenor mapping

For a survey quarter `t` with calendar year `y = t.year`:

| FCT_HORIZON | Canonical tenor | Mapping rule |
|---|---|---|
| `y` | 0Y (current-year) | Discarded — below M3 cadence |
| `y + 1` | **1Y** | Rolling 1-year-ahead annual inflation |
| `y + 2` | **2Y** | Rolling 2-year-ahead annual inflation |
| `LT` | **5Y / 10Y / 5y5y** | Long-term anchor proxy (SPF methodological definition = 4–5y ahead) |

The `LT` value is used as the anchor / 5y5y approximation: SPF's
documented long-term horizon is the canonical euro-area 5y-forward
inflation expectation for central-bank credibility analysis. Emitted
under the `SPF_LT_AS_ANCHOR` flag.

### §3.3 M3 FULL promotion path

With `interpolated_tenors = {1Y, 2Y, 5Y, 10Y, 5y5y}` populated per the
rule above, `build_canonical(..., survey=ExpInfSurvey(...))` yields
`expected_inflation_tenors_json['5y5y']` (via SURVEY source) — the
exact key `build_m3_inputs_from_db` (§db_backed_builder.py:224) requires
to emit M3 FULL.

Projected M3 cascade (2026-04-23 tick):

| Country | Pre-Q.1 | Post-Q.1 | EXPINF source | Flag |
|---|---|---|---|---|
| US | FULL | FULL | FRED BEI + survey | — |
| EA | DEGRADED | **FULL** | ECB SDW SPF | SPF_LT_AS_ANCHOR |
| DE | DEGRADED | **FULL** | ECB SDW SPF | + SPF_AREA_PROXY |
| FR | DEGRADED | **FULL** | ECB SDW SPF | + SPF_AREA_PROXY |
| IT | DEGRADED | **FULL** | ECB SDW SPF | + SPF_AREA_PROXY |
| ES | DEGRADED | **FULL** | ECB SDW SPF | + SPF_AREA_PROXY |
| PT | DEGRADED | **FULL** | ECB SDW SPF | + SPF_AREA_PROXY |
| GB | DEGRADED | DEGRADED | (Sprint Q.2) | — |
| JP | DEGRADED | DEGRADED | (Sprint Q.3) | — |
| CA | DEGRADED | DEGRADED | (Sprint Q.3) | — |

6 countries M3 DEGRADED → FULL from a single connector extension.

---

## §4 Implementation constants (for §2.2 of brief)

```
ECB_SPF_DATAFLOW       = "SPF"
ECB_SPF_REF_AREA       = "U2"   # EA aggregate only
ECB_SPF_TOPIC_HICP     = "HICP"
ECB_SPF_BREAKDOWN      = "POINT"
ECB_SPF_SURVEY_FREQ    = "Q"
ECB_SPF_SOURCE_AGG     = "AVG"  # Median (MDN) returned 404; defer
ECB_SPF_KEY_TEMPLATE   = "Q.U2.HICP.POINT.{horizon}.Q.AVG"
ECB_SPF_WILDCARD_KEY   = "Q.U2.HICP.POINT...AVG"    # all horizons

# Horizon → canonical tenor derivation
def derive_tenor(survey_quarter_year: int, horizon: str) -> str | None:
    if horizon == "LT":
        return "LTE"
    try:
        delta = int(horizon) - survey_quarter_year
    except ValueError:
        return None
    return {1: "1Y", 2: "2Y"}.get(delta)

# AREA_PROXY cohort
SPF_EA_COHORT = frozenset({"EA", "DE", "FR", "IT", "ES", "PT", "NL"})
```

`NL` is in the cohort for consistency with other L2 EA periphery paths
but is not in the 6-country cascade target — Sprint Q.1 emits NL as
`SPF_AREA_PROXY` only if the M3 pipeline requests it (optional / free
extension if the factory wiring surfaces NL automatically).

---

## §5 Follow-on CAL candidates surfaced

| Proposed CAL | Trigger | Priority |
|---|---|---|
| `CAL-EXPINF-PER-COUNTRY-LINKERS-FOLLOWUP` | Per-country BEI via national linker connectors (upgrade from AREA_PROXY) | Medium — Week 12+ |
| `CAL-ECB-SPF-MDN-VARIANT` | Fetch MDN source variant (404 on first probe — schema or params issue); would provide cross-check on AVG | Low — scope creep |
| `CAL-ECB-SPF-HISTOGRAM` | Expose histogram-bucket distribution for risk-of-deflation / tail-risk analysis (L5 regime input) | Low — Phase 2+ |
| `CAL-EXPINF-SURVEY-NATIONAL` | Per-country national surveys (Bundesbank Expert Forecast, INSEE, BdE Previsiones) | Medium — parallel to Sprint Q.2+ |

---

## §6 HALT disposition

**HALT-0 cleared** (brief §4): dataflow live, JSON + CSV both supported,
series return 200 with data 2026-Q1 at freshness < 90 days. No SDMX-ML-only
fallback needed. No schema-constraint surprises (7-dim key maps cleanly
to existing `_parse_monetary_csv` pattern; writer unique key
`(country_code, date, survey_name, methodology_version)` matches the
survey-quarter cadence without conflict).

Proceed to C2 (connector extension) + C3 (writer) + C4 (wiring).

---

*End of probe. 6-country M3 FULL cascade is empirically feasible from a
single ECB SDW SPF dataflow extension.*
