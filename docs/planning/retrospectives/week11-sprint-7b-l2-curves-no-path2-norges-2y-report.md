---
sprint: week11-sprint-7b-l2-curves-no-path2-norges-2y
phase: complete
date: 2026-04-26
outcome: PATH C — NO ships via Norges Bank Path 2 native cascade (7 tenors, NS-reduced, RMSE 3.689 bps); T1 curves coverage 11/16 → 12/16
brief: docs/planning/week11-sprint-7b-l2-curves-no-path2-norges-2y-brief.md
pre-flight: docs/planning/week11-sprint-7b-l2-curves-no-path2-norges-2y-preflight-findings.md
probe-results: docs/backlog/probe-results/sprint-7b-no-norges-2y-probe.md
---

# Sprint 7B — NO 2Y curves Path 2 via Norges Bank — Retrospective

## 1. Sprint metadata

| Field | Value |
|---|---|
| Branch | `sprint-7b-l2-curves-no-path2-norges-2y` |
| CC duration | ~2.5h wall-clock |
| Commits | 6 (1 + 1.5 + 1.5-superseded + 2 + 3 + 4 + 5) |
| HALT triggers fired | 0 (none) |
| HALT-style pivot | 1 (binary brief inversion → Path C; Hugo authorized 2026-04-26) |
| Final outcome | **Path C** — NO ships T1 via Norges Bank single-source cascade (NOT Path A connector-only as initially scoped; NOT Path B T2 downgrade) |

## 2. Probe matrix Norges Bank 2Y verbatim API response

Reproduced from Commit 2 (sha `6b64320`); full doc at
`docs/backlog/probe-results/sprint-7b-no-norges-2y-probe.md`.

| # | URL | Status | Bytes | Outcome |
|---|---|---|---|---|
| 1 | `GET /api/data/GOVT_GENERIC_RATES/B.2Y.GBON?...` | **404** | 160 | Literal 2Y absent |
| 2 | `GET /api/data/GOVT_GENERIC_RATES/B.02Y.GBON?...` | **404** | 160 | Zero-padded 2Y absent |
| 3 | `GET /api/data/GOVT_GENERIC_RATES?startPeriod=2026-04-20&endPeriod=2026-04-26` | **200** | 4026 | 28 obs / 4 trading days; **TENOR_CODES** = `['3Y', '3M', '6M', '12M', '10Y', '5Y', '7Y']` |
| 4 | `GET /api/data/GOVT_GENERIC_RATES/B.10Y.GBON?...` | **200** | 3114 | 4 obs (regression guard — existing connector unchanged) |

**Per-key follow-up (Commit 4 sha `51c802c`)** — within-sprint correction
of Commit 3 INSTRUMENT_TYPE assumption:

| TENOR | `B.{T}.GBON` | `B.{T}.TBIL` | Resolution |
|---|---|---|---|
| 3M | 404 | **200** | TBIL |
| 6M | 404 | **200** | TBIL |
| 12M | 404 | **200** | TBIL |
| 1Y | 404 | (n/a) | absent |
| 2Y | 404 | 404 | **empirically absent under either instrument type** |
| 3Y | **200** | (n/a) | GBON |
| 5Y | **200** | (n/a) | GBON |
| 7Y | **200** | (n/a) | GBON |
| 10Y | **200** | (n/a) | GBON (existing M1 production key) |

## 3. Tenor coverage shipped vs. target

Hugo NSS criterion (brief §1): "2Y+10Y mandatory + rest nice-to-have"
→ infeasible (2Y absent). **Path C re-scope**: NS-reduced fit on the 7
tenors empirically available.

| Tenor | TE Path 1 | Norges Bank Path 2 | Final ship (Path C) |
|---|---|---|---|
| 3M  | — | ✓ `B.3M.TBIL` | Norges Bank |
| 6M  | ✓ `NORYIELD6M:GOV` | ✓ `B.6M.TBIL` | Norges Bank (Path 2 native > TE aggregator) |
| 1Y  | ✓ `NORYIELD52W:GOV` | ✓ `B.12M.TBIL` (canonicalised → `1Y`) | Norges Bank |
| 2Y  | — | — | **MISSING (permanent data limitation)** |
| 3Y  | — | ✓ `B.3Y.GBON` | Norges Bank |
| 5Y  | — | ✓ `B.5Y.GBON` | Norges Bank |
| 7Y  | — | ✓ `B.7Y.GBON` | Norges Bank |
| 10Y | ✓ `GNOR10YR:GOV` | ✓ `B.10Y.GBON` | Norges Bank |
| 15Y / 20Y / 30Y | — | — | brief §1 Out (deferred) |

7 tenors ≥ `MIN_OBSERVATIONS=6` → NSS NS-reduced 4-param fit accepted
(7 < `MIN_OBSERVATIONS_FOR_SVENSSON=9`). TE Path 1 fully redundant for
NO curves layer — Norges Bank covers identical tenors plus 4 more.

## 4. Path A NSS RMSE table + connector cassettes inventory

### 4.1 Live canary metrics (2024-12-30)

```
test_daily_curves_no_end_to_end PASSED:
  observations_used: 7
  rmse_bps:          3.689
  confidence:        0.75
  source_connector:  norgesbank
  fit_id:            0c5dbb40-2709-4e16-935d-41fad055ae1a
```

3.689 bps clears the spec tier 1 target (`<5 bps RMSE`) despite the
NS-reduced fit — better than CA (≤5 bps NS-reduced precedent) and PT
(7.24-7.53 bps Svensson). Confidence 0.75 reflects the larger relative
weight of TBIL short-end vs Svensson countries.

### 4.2 Cassette inventory

No new full-history cassette shipped. `tests/cassettes/connectors/norgesbank_policy_rate_2020_2026.json` (Sprint X-NO baseline) covers
the existing IR/B.KPRA.SD.R series; the Sprint 7B unit tests use
synthetic SDMX-JSON via `_sdmx_json_payload` helper for happy-path
parametrisation, plus a `@slow` live canary
(`test_live_canary_norgesbank_govt_yield_5y`) for the 5Y tenor —
representative mid-curve probe per Hugo direction. Connector cache
namespace `norgesbank_dataapi` covers all 7 keys at runtime.

## 5. CAL closures + new CALs filed

### 5.1 Closed
- **`CAL-CURVES-NO-PATH-2`** → `CLOSED · DONE-FULL` (Commit 5 sha TBD).
  Delta: TE 3 tenors → Norges Bank Path 2 native cascade 7 tenors.
  Sprint 7B Path C pivot rationale captured in CAL body.

### 5.2 Filed during sprint
- **`CAL-TEST-CYCLES-FIXTURE-FLAKE-AND-FAIL`** (sha `89d9ac1`) —
  superseded preliminary `CAL-TEST-CYCLES-FIXTURE-SEED-REGRESSION`
  (sha `3f95f34`) after Hugo verified diagnosis. Issue 1 (genuine
  failure: `test_us_smoke_end_to_end`) + Issue 2 (order-dependent
  flake: `test_us_full_stack` / `test_economic_ecs::test_fixture_us_2020_03_23_recession`
  / `test_te_indicator::test_wrapper_ch_policy_rate_from_cassette` —
  flake target rotates with test ordering). LOW priority, 2-3h
  dedicated test-hygiene sprint estimate.

### 5.3 No new CALs filed for the 2Y absence
Empirical permanent data limitation (Norges Bank does not publish
NOK 2Y govt-bond series); no track-and-fix path. Documented in CAL
body, probe-results, this retro, and `nss-curves.md` §12.1 NO row
comment.

## 6. Pattern observations Path 2 vs Sprint M/I (TE) cascade

### 6.1 Sprint M (PT) / I (FR) — TE Path 1 inversions
Sprint M shipped PT via TE GSPT (10 tenors); Sprint I shipped FR via
TE GFRN (10 tenors). Both were S1 cascade inversions: TE Path 1
sufficed (no Path 2 required). Cascade discipline: `/markets/bond` ≥
`/search` per ADR-0009 v2.3.1.

### 6.2 Sprint 7B (NO) — Path 2 first ship
Sprint 7B ships NO via the FIRST Path 2 native-CB direct cascade in
the sparse-T1 cohort (post AU's S1 PASS in Sprint T). Norges Bank
DataAPI is the second Path 2 ship in the broader project after
Bundesbank DE (which was Phase 0 baseline, not sparse-T1 cohort).
Pattern observations:

- **Path 2 has higher tenor density than TE for sparse-T1 sovereigns**:
  TE NO had 3 tenors; Norges Bank NO has 7 (+ 6M /1Y duplicates → 4
  net new). The mid-curve gap that S2 HALT-0 surfaces in TE is often
  not a sovereign-market gap — it's an offshore-real-money-tracking
  gap (Bloomberg/Reuters primary-market desk activity threshold
  unmet for NOK; same pattern hypothesised for CHF/SEK/DKK).
- **Native-CB SDMX-JSON is friendlier than Bloomberg-symbol probing**:
  ECB / Bundesbank / Norges Bank / DNB(?)/SNB(?)/Riksbank(?) all use
  SDMX-JSON. The flow-listing → per-key → cache pattern generalises.
  TE per-symbol probing requires multi-prefix × multi-suffix grid (see
  Sprint T-Retry); Path 2 native-CB needs one well-formed flow query.
- **Hybrid dispatch unnecessary when Path 2 dominates**: Hugo's "Path 2
  native > TE aggregator" rule + Norges Bank tenor superset means NO
  ships via single-source Norges Bank, not TE+Norges Bank cascade.
  This simplifies the dispatch (NO is now a "single-source country"
  like DE / US / EA, not a "hybrid" first).

### 6.3 Brief binary architecture proved insufficient
Brief §6 binary (Path A 2Y available → ship; Path B 2Y absent → close
EXHAUSTED) discarded an entire orthogonal opportunity. Probe 3 (full-
flow listing) surfaced 6 mid-curve tenors that the binary did not
anticipate. Without ADR-0009 v2.3.1 discipline (probe full-flow
listing, not just per-key), this sprint would have shipped Path B —
NO T2 downgrade and 6 live tenors discarded.

**Lesson codified**: brief binary architectures must include an "open
discovery" branch when the probe domain is sparsely characterised.
Equivalent: add Probe 3 / authoritative listing as **mandatory
pre-flight HALT condition**, not optional secondary.

## 7. Lessons (codified for ADR-0009 v2.3.4 amendment candidate)

### 7.1 Methodology gap caught by within-sprint follow-up
Commit 3 shipped `NORGESBANK_GBON_TENOR_KEYS` with GBON instrument-
type prefix for all 7 tenors (3M/6M/12M/3Y/5Y/7Y/10Y). Commit 4 live
canary surfaced only 4/7 tenors — debug per-key probe revealed:
- Long-end (3Y/5Y/7Y/10Y) → INSTRUMENT_TYPE=GBON ✓
- Short-end (3M/6M/12M)   → INSTRUMENT_TYPE=TBIL (treasury bills)

Commit 2 full-flow listing returned the TENOR dimension values but
the script did not resolve the full series-key dimensions. The
INSTRUMENT_TYPE dimension was visible in the response but ignored
during decode.

**ADR-0009 v2.3.4 candidate amendment**:

> When probing a SDMX-JSON dataflow with multiple `series` dimensions,
> the operator MUST decode ALL series dimensions (not just TENOR or
> the single dimension of immediate interest). The colon-keyed series
> map (e.g. `"0:1:1"` → `[FREQ=B, TENOR=3M, INSTRUMENT_TYPE=TBIL]`)
> is the authoritative ledger. A flow-listing probe that decodes only
> one dimension can falsely imply uniform dimension values across the
> rest, leading to malformed resource-key URLs and 404s on otherwise-
> live series.

This amendment generalises Sprint T-Retry's v2.3.1 (full-flow listing
authoritative over `/search`) and v2.3.2 (multi-prefix canonical) by
extending discipline to **multi-dimension** flows.

### 7.2 Brief binary insufficient for sparse-data probes
See §6.3.

### 7.3 Path 2 native-CB infra is generally re-usable
`NorgesBankConnector` was Sprint X-NO infrastructure (M1 cascade input).
Sprint 7B extended it via `fetch_govt_yield(tenor)` + domain wrappers
without breaking the M1 contract. Generalising: each Path 2 cohort CAL
should explicitly note "reusable connector infra Sprint X-{COUNTRY}"
in its trigger field — Hugo direction Sprint 5B retro already flags this
for DK (`NationalbankenConnector` Sprint Y-DK), CH (`SnbConnector`
Sprint V-CH), SE (`RiksbankConnector` Sprint W-SE), NO (this sprint).
Sprint 7B is the empirical validation that the infra-reuse pattern
ships in 2-3h CC time as estimated.

## 8. Acceptance checklist (brief §6 binary, re-mapped to Path C)

**Path C — NO 12/16 T1 shipped via Norges Bank Path 2 native cascade**:

- [x] `NorgesBankConnector.fetch_govt_yield(tenor)` shipped (Commit 3 `90ec916`)
- [x] `fetch_yield_curve_nominal(country)` + `fetch_yield_curve_linker(country)` domain wrappers shipped (Commit 4 `51c802c`)
- [x] NSS NS-reduced fit NO ships with 7 tenors (3M / 6M / 1Y / 3Y / 5Y / 7Y / 10Y); 2Y absent documented
- [x] RMSE = 3.689 bps reported (Commit 4 body + this retro §4.1)
- [x] `country_tiers.yaml` NO `curves_live: true` (Commit 5)
- [x] `nss-curves.md` §12.2 NO row → §12.1 (Commit 5; 11/16 → 12/16)
- [x] `CAL-CURVES-NO-PATH-2` closed `DONE-FULL` (Commit 5)
- [x] daily-curves pipeline includes NO post-merge (`T1_CURVES_COUNTRIES` 11 → 12)
- [x] T1 curves coverage 11/16 → 12/16

**Sprint-end discipline**:

- [x] No `--no-verify`
- [x] Pre-push gate green every push (ruff + mypy clean; pytest -m "not slow" 2320 passed / 2 failed inherited per CAL-TEST-CYCLES-FIXTURE-FLAKE-AND-FAIL — same baseline pre-Sprint-7B + 10 net new norgesbank tests passing)
- [x] Sprint 7B retrospective shipped (this file)

## 9. Sprint commits ledger

```
51c802c  feat(curves): wire NO daily-curves dispatch via NorgesBankConnector — Sprint 7B Path C ship
90ec916  feat(connectors): NorgesBankConnector.fetch_govt_yield(tenor) — Sprint 7B Path C extension
6b64320  docs(probes): Sprint 7B NO Norges Bank 2Y probe — binary inversion → Path C pivot
89d9ac1  docs(backlog): file CAL-TEST-CYCLES-FIXTURE-FLAKE-AND-FAIL (Sprint 7B inherited)
3f95f34  docs(backlog): file CAL-TEST-CYCLES-FIXTURE-SEED-REGRESSION (superseded by 89d9ac1)
15c21fe  docs(planning): Sprint 7B NO 2Y Path 2 Norges Bank pre-flight findings
c890033  docs(planning): Sprint 7B NO 2Y Path 2 Norges Bank brief                ← already on main pre-Sprint-7B
```

Plus this Commit 5 (sha TBD) which closes the sprint.

## 10. Next-action queue post-merge

- **Sprint 7C / 7D (Path 2 cohort)**: NL/NZ/CH/SE/DK remain S2 deferred.
  Sprint 7B validates the Path 2 native-CB SDMX-JSON pattern works for
  Norges Bank — extending to:
  - DK: `NationalbankenConnector` (Sprint Y-DK infra reusable; lowest
    Path 2 cost per Sprint 5B retro recommendation).
  - CH: `SnbConnector` (Sprint V-CH; potential native Svensson per
    `data.snb.ch`).
  - SE: `RiksbankConnector` (Sprint W-SE).
  - NZ: RBNZ table B2 (no existing connector; greenfield).
  - NL: DNB `statline.dnb.nl` (CAL-CURVES-NL-DNB-PROBE; greenfield).
- **CAL-TEST-CYCLES-FIXTURE-FLAKE-AND-FAIL** (LOW): test-hygiene sprint
  to fix Issue 1 + Issue 2 before pre-push gate erosion compounds.
- **ADR-0009 v2.3.4 amendment** (low-burn docs): codify
  multi-dimension SDMX flow-listing discipline per §7.1 of this retro.
  Operator decision — Hugo to authorise via dedicated amendment sprint
  or fold into next Path 2 cohort retro.
- **CAL-NO-M4-FCI** (deferred Sprint X-NO): unaffected by this sprint;
  Norges Bank 10Y connector key + canonical alias preserved.
- **CAL-EXPINF-T1-AUDIT**: NO BEI / SURVEY input still pending for
  DERIVED real-curve path. Real-curve linker stub returns empty for NO
  per Sprint 7B Commit 4 (symmetric with DE / EA pattern).

---

**END SPRINT 7B RETROSPECTIVE — ready for `sprint_merge.sh`**
