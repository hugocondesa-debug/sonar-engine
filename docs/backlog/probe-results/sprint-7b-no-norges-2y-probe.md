---
sprint: week11-sprint-7b-l2-curves-no-path2-norges-2y
phase: probe-results
date: 2026-04-26
status: PROBE COMPLETE — binary inversion → Path C pivot authorized by Hugo
authoritative: yes (full-flow listing per ADR-0009 v2.3.1 discipline)
---

# Sprint 7B — NO Norges Bank `/GOVT_GENERIC_RATES` 2Y probe (Commit 2)

Empirical probe of the Norges Bank DataAPI `GOVT_GENERIC_RATES` dataflow
under the brief §6 binary architecture (Path A: 2Y available → ship
NSS-degraded NO live; Path B: 2Y absent → close `CAL-CURVES-NO-PATH-2`
EXHAUSTED + NO T1→T2 downgrade).

**Outcome**: binary inversion. The 2Y endpoint is empirically absent,
but the authoritative full-flow listing (Probe 3, ADR-0009 v2.3.1
canonical) returned **6 live mid-curve tenors** (`3M`, `6M`, `12M`,
`3Y`, `5Y`, `7Y`) plus the existing `10Y`. Norges Bank is **not
exhausted** — it is in fact richer than the brief assumed.

Hugo decision 2026-04-26 (this transcript): **Path C pivot
authorized**. Sprint 7B re-scopes from "ship 2Y degraded fit" to
"ship 7-tenor NS-reduced fit using TE + Norges Bank cascade". NO stays
T1. `CAL-CURVES-NO-PATH-2` closes as `DONE-FULL` (not `EXHAUSTED`).
T1 curves coverage 11/16 → 12/16.

## 1. Probe matrix (verbatim)

Window: `2024-01-01 → 2026-04-26` (Probes 1-2); `2026-04-20 → 2026-04-26`
(Probes 3-4 — short window for fresh-data confirmation).

Headers: `User-Agent: SONAR/2.0 (monetary-cascade Sprint 7B 2Y probe; contact hugocondesa@pm.me)`,
`Accept: application/vnd.sdmx.data+json`.

| # | URL | Status | Bytes | Outcome |
|---|---|---|---|---|
| 1 | `GET /api/data/GOVT_GENERIC_RATES/B.2Y.GBON?format=sdmx-json&startPeriod=2024-01-01&endPeriod=2026-04-26` | **404** | 160 | Literal 2Y absent |
| 2 | `GET /api/data/GOVT_GENERIC_RATES/B.02Y.GBON?format=sdmx-json&startPeriod=2024-01-01&endPeriod=2026-04-26` | **404** | 160 | Zero-padded 2Y absent |
| 3 | `GET /api/data/GOVT_GENERIC_RATES?format=sdmx-json&startPeriod=2026-04-20&endPeriod=2026-04-26` | **200** | 4026 | 28 obs / 4 trading days; **TENOR_CODES** = `['3Y', '3M', '6M', '12M', '10Y', '5Y', '7Y']` |
| 4 | `GET /api/data/GOVT_GENERIC_RATES/B.10Y.GBON?format=sdmx-json&startPeriod=2026-04-20&endPeriod=2026-04-26` | **200** | 3114 | 4 obs (regression guard — existing connector key unaffected) |

### 1.1 Probe 1 verbatim (literal `B.2Y.GBON`)

```
URL    : https://data.norges-bank.no/api/data/GOVT_GENERIC_RATES/B.2Y.GBON
PARAMS : {'format': 'sdmx-json', 'startPeriod': '2024-01-01', 'endPeriod': '2026-04-26'}
STATUS : 404
BYTES  : 160
BODY   : {"errors":[{"code":404,"message":"No data for data query against the dataflow: urn:sdmx:org.sdmx.infomodel.datastructure.Dataflow=NB:GOVT_GENERIC_RATES(1.0)"}]}
```

### 1.2 Probe 2 verbatim (zero-padded `B.02Y.GBON`)

```
URL    : https://data.norges-bank.no/api/data/GOVT_GENERIC_RATES/B.02Y.GBON
PARAMS : {'format': 'sdmx-json', 'startPeriod': '2024-01-01', 'endPeriod': '2026-04-26'}
STATUS : 404
BYTES  : 160
BODY   : {"errors":[{"code":404,"message":"No data for data query against the dataflow: urn:sdmx:org.sdmx.infomodel.datastructure.Dataflow=NB:GOVT_GENERIC_RATES(1.0)"}]}
```

Identical 404 message confirms tenor key is the missing dimension
value, not malformed URL or auth issue.

### 1.3 Probe 3 verbatim (full-flow listing — **authoritative**)

```
URL    : https://data.norges-bank.no/api/data/GOVT_GENERIC_RATES
PARAMS : {'format': 'sdmx-json', 'startPeriod': '2026-04-20', 'endPeriod': '2026-04-26'}
STATUS : 200
BYTES  : 4026
N_OBSERVATIONS : 28
FIRST_DATE     : 2026-04-20
LAST_DATE      : 2026-04-23
TENOR_CODES    : ['3Y', '3M', '6M', '12M', '10Y', '5Y', '7Y']
```

28 obs across 4 trading days × 7 tenors = exact match → daily cadence
per tenor confirmed. Series dimension `TENOR` enumeration is the
authoritative ledger.

### 1.4 Probe 4 verbatim (10Y regression guard)

```
URL    : https://data.norges-bank.no/api/data/GOVT_GENERIC_RATES/B.10Y.GBON
PARAMS : {'format': 'sdmx-json', 'startPeriod': '2026-04-20', 'endPeriod': '2026-04-26'}
STATUS : 200
BYTES  : 3114
N_OBSERVATIONS : 4
TENOR_CODES    : ['10Y']
```

Existing `NORGESBANK_GBON_10Y_KEY = "B.10Y.GBON"` constant remains
correct and live. M4 FCI NO 10Y plumbing (CAL-NO-M4-FCI, deferred)
unaffected.

## 2. Tenor coverage analysis (combined TE + Norges Bank)

| Tenor | TE Path 1 | Norges Bank Path 2 | Combined unique |
|---|---|---|---|
| 3M  | — | ✓ (`B.3M.GBON`) | 3M |
| 6M  | ✓ (`NORYIELD6M:GOV`) | ✓ (`B.6M.GBON`) | 6M (prefer Norges Bank — Path 2 native > TE aggregator per Hugo direction) |
| 12M | ✓ (`NORYIELD52W:GOV` ≈ 1Y) | ✓ (`B.12M.GBON`) | 12M (prefer Norges Bank; 52W ≈ 12M conceptual equivalence) |
| 2Y  | — | — | **MISSING** |
| 3Y  | — | ✓ (`B.3Y.GBON`) | 3Y |
| 5Y  | — | ✓ (`B.5Y.GBON`) | 5Y |
| 7Y  | — | ✓ (`B.7Y.GBON`) | 7Y |
| 10Y | ✓ (`GNOR10YR:GOV`) | ✓ (`B.10Y.GBON`) | 10Y (prefer Norges Bank — Path 2 native > TE aggregator) |
| 15Y/20Y/30Y | — | — | brief §1 Out (deferred mid-curve completeness) |

**Total unique combined tenors**: **7** (`3M`, `6M`, `12M`, `3Y`, `5Y`,
`7Y`, `10Y`).

NSS fit-quality threshold check (`src/sonar/overlays/nss.py:96-97`):

- 7 ≥ `MIN_OBSERVATIONS = 6` → **NSS fit accepted** ✓
- 7 < `MIN_OBSERVATIONS_FOR_SVENSSON = 9` → **NS-reduced 4-param** (CA precedent — `nss-curves.md` §12.1 row, RMSE ≤5 bps target)

The Sprint 7A floor revision dependency identified in pre-flight §7.2
becomes **moot**: 7-tenor coverage clears the canonical NSS floor with
1 tenor headroom. No spec amendment required for NO ship.

## 3. Path C pivot rationale

Brief §1 Out clause anticipated this exact contingency:

> 3Y/5Y/7Y/15Y/20Y/30Y NO tenors (Norges Bank may have additional
> `GOVT_GENERIC_RATES` keys but mid-curve completeness deferred)

The deferral assumed the 2Y was the live tenor of record. Empirically
the 2Y is the only mid-tenor that is **not** live; 3Y/5Y/7Y are all
live. The Out clause's prioritisation inverts:

- **Briefed assumption**: 2Y available + mid-curve deferred = ship 2Y degraded fit + Sprint 7A floor revision dependency.
- **Empirical reality**: 2Y absent + mid-curve available = ship NS-reduced fit on 7 mid-tenors; Sprint 7A unblocked but no longer load-bearing.

Hugo decision 2026-04-26 (verbatim from transcript):

> Path C pivot AUTHORIZED. NO permanece T1. ... Combined coverage:
> 7 tenors unique. ... NSS NS-reduced fit, ≥ MIN_OBSERVATIONS=6 →
> no Sprint 7A floor revision dependency. CAL-CURVES-NO-PATH-2
> closes as DONE-FULL (not EXHAUSTED).

15Y/20Y/30Y stay deferred per original §1 Out (probe 4 also confirmed
they are not in the listing). Mid-curve completeness sufficient for
NS-reduced fit; long-end gap is operationally tolerable (CA precedent
ships at 10Y anchor).

## 4. ADR-0009 v2.3.1 discipline applied

The full-flow listing (Probe 3) is the canonical authoritative test
per ADR-0009 §7.5.1 (codified Sprint T-Retry 2026-04-24). Without
it, the binary 2Y probe (Probes 1+2) would have prematurely fired
HALT-0 and downgraded NO to T2 — **discarding 6 live tenors**.

This is the second large-scale validation of v2.3.1 as load-bearing
discipline (first: NZ Sprint T-Retry, where `/markets/bond` filter
surfaced 2 short-tenor symbols absent from `/search`). The pattern
generalises beyond TE: **authoritative full-flow listing > per-key
probe matrix** for any sparse-data DataAPI/SDMX source.

## 5. Sprint 7B revised plan (Commits 3-5)

Per Hugo authorisation:

3. **Commit 3 — NorgesBankConnector extension**:
   - Add `NORGESBANK_GBON_TENOR_KEYS: dict[str, str]` constant mapping
     `'3M' → 'B.3M.GBON'` ... `'10Y' → 'B.10Y.GBON'` (7 entries).
   - Add `fetch_govt_yield(tenor: str, start: date, end: date)` generic
     method routing to the appropriate `B.{TENOR}.GBON` key + stamping
     `tenor_years` correctly per tenor.
   - Refactor `fetch_gbon_10y` as thin wrapper over `fetch_govt_yield("10Y", ...)`.
   - Backwards-compat: existing `NORGESBANK_GBON_10Y_KEY` constant
     stays (regression guard).
   - Unit tests: parameterised happy-path for each new tenor + tenor-
     stamping invariants + invalid-tenor format raises clearly.
   - @slow live canary: single representative tenor (Hugo direction:
     5Y).

4. **Commit 4 — Pipeline integration**:
   - `daily_curves.py`:
     - Add `"NO"` to `T1_CURVES_COUNTRIES` and `CURVE_SUPPORTED_COUNTRIES`.
     - Remove `"NO"` from `_DEFERRAL_CAL_MAP`.
     - Add NO branch in `_fetch_nominals_linkers` combining TE primary
       (52W only — let Norges Bank own the rest per Hugo direction
       "prefer Norges Bank for shared tenors") + Norges Bank Path 2
       (3M/6M/12M/3Y/5Y/7Y/10Y) into single `nominals` dict; first
       hybrid country in dispatch.
   - `nss_curves_backfill.py`: add `"NO"` to `T1_SPOT_BACKFILL_COUNTRIES`.
   - RMSE report against historical window (commit body verbatim).

5. **Commit 5 — Docs closure**:
   - `country_tiers.yaml`: NO row → `curves_live: true`.
   - `nss-curves.md` §12.2 → §12.1 (row migration; tenor count 3 → 7;
     connector hybrid `te + norgesbank`; path TE Path 1 + Norges Bank
     Path 2; RMSE TBD per Commit 4).
   - `calibration-tasks.md`: `CAL-CURVES-NO-PATH-2` status →
     `CLOSED · DONE-FULL` (delta TE 3 tenors → combined 7 tenors via
     Path 2 dual-source cascade).
   - Sprint 7B retrospective:
     `docs/planning/retrospectives/week11-sprint-7b-l2-curves-no-path2-norges-2y-report.md`
     including Path C pivot rationale, Hugo authorisation timestamp,
     tenor matrix, RMSE results, lessons (brief binary architecture
     insufficient when probe surfaces orthogonal opportunity; ADR-0009
     v2.3.1 full-flow listing discipline saved a T2-downgrade
     false-positive).

## 6. CAL bookkeeping

- `CAL-CURVES-NO-PATH-2`: closes as `DONE-FULL` in Commit 5 (was OPEN,
  Sprint T/T-Retry/5B 3× HALT-0 stamps).
- `CAL-NO-M4-FCI`: unchanged (deferred Sprint X-NO follow-up; this
  sprint's 7-tenor extension complements but does not close).
- `CAL-TEST-CYCLES-FIXTURE-FLAKE-AND-FAIL`: filed in `89d9ac1`
  (Sprint 7B Commit 1 cluster); not re-touched here.
- No new CAL filed for the 2Y absence — empirical permanent data
  limitation, no track-and-fix path. The 2Y gap is documented in
  this probe-results file + retrospective + nss-curves.md §12.1
  comment column.

## 7. Reproducibility

The probe was a one-off inline Python script (httpx synchronous calls
via the same User-Agent + Accept headers as `NorgesBankConnector`).
No script committed (single-use; output is the artefact). To re-run,
any operator can:

```bash
curl -s -H 'User-Agent: SONAR/2.0' \
     -H 'Accept: application/vnd.sdmx.data+json' \
  'https://data.norges-bank.no/api/data/GOVT_GENERIC_RATES?format=sdmx-json&startPeriod=2026-04-20&endPeriod=2026-04-26' \
  | python -c 'import json,sys;p=json.load(sys.stdin);print([v["id"] for v in p["data"]["structure"]["dimensions"]["series"][2]["values"]])'
```

Expected output: `['3Y', '3M', '6M', '12M', '10Y', '5Y', '7Y']` (or
superset if Norges Bank extends the dataflow).

---

**END PROBE RESULTS — Sprint 7B Commit 2**
