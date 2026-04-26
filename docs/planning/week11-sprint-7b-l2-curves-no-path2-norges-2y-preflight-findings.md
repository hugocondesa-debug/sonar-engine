---
sprint: week11-sprint-7b-l2-curves-no-path2-norges-2y
phase: pre-flight
date: 2026-04-26
status: HALT-0 cleared (no brief-defined HALT triggers fired); 1 open question surfaced for Hugo §7.2 (6-tenor floor vs. NO degraded-fit) — does not block Commit 2 probe
---

# Sprint 7B — NO 2Y curves Path 2 via Norges Bank — Pre-flight findings

Empirical pre-flight audit per brief §2 (HALT #0 mandatory) + brief §4
Commit 1 contract. Ships under Commit 1 of the Sprint 7B run as the
specs-first record of what will be probed in Commit 2 and (Path A
only) implemented in Commits 3-4.

Single-país scope: **NO** (Norway). Binary outcome architecture per
brief §6:

- **Path A — 2Y available**: ship NSS-degraded NO live (T1 curves
  coverage 11/16 → 12/16) — conditional on Hugo §7.2 resolution.
- **Path B — 2Y unavailable**: confirm Norges Bank exhausted, close
  `CAL-CURVES-NO-PATH-2` as EXHAUSTED + file
  `CAL-CURVES-NO-2Y-MISSING`.

## 1. Brief + spec + ADR + connector reads (HALT #0 cleared)

End-to-end reads completed:

- `docs/planning/week11-sprint-7b-l2-curves-no-path2-norges-2y-brief.md`
  (§1 → §8) ✓ — single-país NO, binary HALT condition on 2Y endpoint
- `docs/specs/overlays/nss-curves.md` §10 cross-references + §12
  country scope appendix (NO row §12.2 — 3 tenors via TE + Path 2
  candidate Norges Bank Statistics) ✓
- `docs/adr/ADR-0009-national-cb-connectors-ea-periphery.md` v2.3
  end-to-end (Path 2 discipline §349-351 + Sprint T addendum §659+
  + Sprint T-Retry §778+ + Sprint 5B §908+) ✓
- `docs/backlog/calibration-tasks.md` `CAL-CURVES-NO-PATH-2` entry
  (lines 3482-3493) — closure conditions: 2Y endpoint either ships
  (close as DONE Path A) or empirically confirms exhausted (amend to
  EXHAUSTED Path B) ✓
- `src/sonar/connectors/norgesbank.py` (358 lines) — module docstring
  lines 1-66 read end-to-end; existing `fetch_series` /
  `fetch_policy_rate` / `fetch_gbon_10y` API contract verified ✓
- `tests/unit/test_connectors/test_norgesbank.py` (437 lines) — unit
  + cassette + @slow live canary patterns; parameterised extension
  surface visible (`_sdmx_json_payload` + `fetch_*` test classes) ✓
- `src/sonar/overlays/nss_curves_backfill.py` (268 lines) — Sprint 2
  orchestrator + `T1_SPOT_BACKFILL_COUNTRIES` 10-tuple; NO must be
  appended to enable Path A backfill ✓
- `src/sonar/pipelines/daily_curves.py` (681 lines) lines 270-391 —
  `T1_CURVES_COUNTRIES` (11) + `CURVE_SUPPORTED_COUNTRIES` (11) +
  `_DEFERRAL_CAL_MAP` (NO maps to `CAL-CURVES-NO-PATH-2`) +
  `_fetch_nominals_linkers` dispatch surface ✓
- `src/sonar/overlays/nss.py` lines 96-104 — `MIN_OBSERVATIONS=6`,
  `MIN_OBSERVATIONS_FOR_SVENSSON=9`, `LINKER_MIN_OBSERVATIONS=5` ✓

No new spec required: NSS overlay already accommodates per-country
deferral; `nss-curves.md` §12 country scope appendix is the canonical
update target for Commit 5.

## 2. Norges Bank DataAPI 2Y endpoint candidate keys

Existing connector module docstring (lines 23-27) documents the
canonical pattern:

```
GOVT_GENERIC_RATES / B.10Y.GBON  (10Y generic gov-bond yield, daily)
```

Series-key shape: `B.{TENOR}.GBON` where `B = FREQ=Business`,
`{TENOR}` = SDMX tenor encoding, `GBON = INSTRUMENT_TYPE=govt bond`.
The connector pins all dimensions via the resource key so the SDMX
response always returns exactly one series with colon-key
`"0:0:0:0"`.

Sprint 7B Commit 2 probe must enumerate plausible 2Y tenor encodings
in the SDMX TENOR dimension under the same `GOVT_GENERIC_RATES`
dataflow. Brief §8 anticipates two encodings:

| Candidate key | Rationale |
|---|---|
| `B.2Y.GBON` | Literal 2Y (SDMX convention seen in module docstring example) |
| `B.02Y.GBON` | Zero-padded (some SDMX flows pad single-digit tenors for sort stability) |

Probe matrix (Commit 2 one-off script):

1. `GET /api/data/GOVT_GENERIC_RATES/B.2Y.GBON?startPeriod=2024-01-01&endPeriod=2026-04-26`
2. If empty / 404: `GET /api/data/GOVT_GENERIC_RATES/B.02Y.GBON?...`
3. If both empty: `GET /api/data/GOVT_GENERIC_RATES?startPeriod=2026-04-20&endPeriod=2026-04-26` (full-flow listing — surfaces all valid TENOR codes, e.g. enumeration like `[3M, 6M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y]` if any 2Y exists at all)

The flow-listing fallback (step 3) is the authoritative exhaustion
test; it equivalences with TE `/markets/bond?Country=Norway` (ADR-0009
v2.3.1). Verbatim API response of the exhaustion-test call goes in
Commit 2 body for posterity (brief §4).

## 3. Connector reuse surface

`NorgesBankConnector` already exposes a generic `fetch_series(series_id, start, end)` (line 257) where `series_id = "{flow}/{key}"`. The
existing `fetch_gbon_10y` wrapper (line 340) routes to
`GOVT_GENERIC_RATES/B.10Y.GBON` and overrides `tenor_years=10.0` on
returned `Observation`s (line 353).

Path A extension (Commit 3) — minimal surface:

```python
async def fetch_govt_yield(self, tenor: str, start: date, end: date) -> list[Observation]:
    """Generic constant-maturity NOK govt-bond yield — flow GOVT_GENERIC_RATES.

    Tenor encoding matches the SDMX TENOR dimension (e.g. ``"2Y"``,
    ``"10Y"``). Stamps ``tenor_years`` on returned Observations as
    parsed from the tenor string.
    """
```

`fetch_gbon_10y` (existing) gets refactored as a thin wrapper that
calls `fetch_govt_yield("10Y", ...)` to avoid duplicating logic; the
existing `NORGESBANK_GBON_10Y_KEY` constant becomes derived (or
remains as a regression-guard backstop). Tests:

1. New unit test `TestFetchGovtYield::test_2y_routes_to_b_2y_gbon` —
   httpx_mock + `_sdmx_json_payload` happy-path with `flow="GOVT_GENERIC_RATES"` +
   tenor stamped 2.0 years.
2. New cassette `tests/cassettes/connectors/norgesbank_gbon_2y_<window>.json`
   — captured live during Commit 2 probe (single full-history fetch).
3. New @slow live canary
   `test_live_canary_norgesbank_gbon_2y` mirroring the existing
   `_gbon_10y` canary (line 419-436).

Backwards compatibility: existing `fetch_gbon_10y` callers (none in
the cascade today — M4 FCI NO 10Y is `CAL-NO-M4-FCI` deferred) remain
green via the wrapper.

## 4. NSS spec §12.2 NO row baseline

Current state (`nss-curves.md` §12.2 row line 272):

```
| NO | 3 (6M, 52W, 10Y) | CAL-CURVES-NO-PATH-2 | Norges Bank `www.norges-bank.no/en/topics/Statistics/` | T + T-Retry |
```

Path A target (Commit 5):

- Move NO from §12.2 (Deferred) → §12.1 (Shipped) row
- Tenor count: 3 → 4 (6M, 52W=1Y, 2Y, 10Y) **provided §7.2 resolves**
- Connector column: `connectors/te + connectors/norgesbank` (first
  hybrid — sets cohort precedent)
- Path column: `TE 3 + Norges Bank Path 2 (2Y)`
- RMSE column: target ≤5 bps (Hugo NSS criterion 2Y+10Y mandatory;
  brief §5 HALT trigger 2 = RMSE > 5 bps)

§12.4 Coverage metrics row update: "T1 shipped 11/16 → 12/16 (75 %)".

Path B target (Commit 5):

- §12.2 row stays; `Sprint probe` column appends `+ 7B (Norges Bank
  2Y missing — EXHAUSTED)`.
- §12.3 ledger sentence appends Path 2 ratio note (1 EXHAUSTED).

## 5. CAL-CURVES-NO-PATH-2 closure conditions (per brief §6 binary)

| Outcome | CAL action | New CAL filed |
|---|---|---|
| Path A | Close `CAL-CURVES-NO-PATH-2` as DONE; record 2Y observation count + cassette pointer + RMSE | None (M4 FCI NO 10Y `CAL-NO-M4-FCI` already exists; mid-curve gap stays under brief §1 Out scope, no new CAL) |
| Path B | Amend `CAL-CURVES-NO-PATH-2` status to EXHAUSTED with verbatim Norges Bank empty response | File `CAL-CURVES-NO-2Y-MISSING` (Priority LOW; permanent data limitation expected) |

## 6. country_tiers.yaml NO row baseline

Current state (`docs/data_sources/country_tiers.yaml:54`):

```
- { iso_code: NO, country: Norway, rating_spread_live: true }
```

NO has no `curves_*` flag yet — neither `curves_live` nor
`curves_path_2_pending`. (NZ at line 52 has
`curves_path_2_pending: true` and AU at line 51 has
`curves_live: true` — Sprint 5A precedent.)

Path A target: append `curves_live: true`.

Path B target: append `curves_path_2_pending: true` (or
`curves_path_2_exhausted: true` if Hugo prefers an explicit terminal
flag — brief §6 leaves this as operator choice; precedent for the
exhausted variant does not exist yet across NL/NZ/CH/SE/DK).

## 7. Code-change requirements (Path A only)

Path B is doc-only — Commits 3-4 skip per brief §4.

### 7.1 Connector + tests + cassette (Commit 3)

- `src/sonar/connectors/norgesbank.py`: add
  `NORGESBANK_GBON_2Y_KEY: Final[str] = "B.2Y.GBON"` (or zero-padded
  per Commit 2 outcome) to `__all__`; add `fetch_govt_yield(tenor)`
  generic method; refactor `fetch_gbon_10y` as thin wrapper;
  preserve existing public API (`NORGESBANK_GBON_10Y_KEY` constant
  stays).
- `tests/unit/test_connectors/test_norgesbank.py`: 1 new unit test
  class `TestFetchGovtYield` (~3 tests: happy-path 2Y, tenor-stamping,
  invalid-tenor format) + 1 new @slow live canary.
- `tests/cassettes/connectors/norgesbank_gbon_2y_<window>.json`:
  recorded live during Commit 2 probe.

### 7.2 Pipeline integration — open question for Hugo

**Surfaced finding** (does not block Commit 2 probe):

NO post-2Y total tenors = TE 3 (6M, 52W, 10Y) + Norges Bank 1 (2Y) = 4. This is **below the canonical NSS floor**:

- `MIN_OBSERVATIONS = 6` (`src/sonar/overlays/nss.py:96`) — NSS-fitter rejects with `InsufficientDataError`
- `MIN_OBSERVATIONS_FOR_SVENSSON = 9` (line 97) — Svensson upgrade threshold
- Hugo NSS criterion (brief §1 + recap): **2Y+10Y mandatory + rest nice-to-have** — implies sub-floor degraded-fit accepted for NO

Brief §1 Out explicitly excludes "NSS Svensson 6-tenor floor revision (separate Sprint 7A spec amendment)". So Sprint 7B Path A ship requires either:

- **Option a** — Add NO-local bypass in `daily_curves.py` `run_country` that accepts 4-tenor input for NO and routes to a degraded fit (NS-2-param? linear interpolation? per Hugo direction). Implementation precedes spec amendment — methodology-versioning concern (CLAUDE.md §4 specs-first).
- **Option b** — Commit 4 stops at "infrastructure ready, fit blocked on Sprint 7A" and ships connector + cassette only. NO stays in `_DEFERRAL_CAL_MAP` until Sprint 7A lands the floor revision; CAL-CURVES-NO-PATH-2 closes infrastructure-only.
- **Option c** — Sprint 7A floor revision ships first, then Sprint 7B Path A ship is unblocked (sequential dependency reversal).

Recommendation: surface to Hugo at Commit 2 close (after 2Y empirical outcome is known). If Path B fires, this question becomes moot. If Path A fires, Hugo decides a/b/c.

### 7.3 nss_curves_backfill.py + daily_curves.py (Commit 4 conditional on §7.2 resolution)

- `T1_SPOT_BACKFILL_COUNTRIES` (`nss_curves_backfill.py:60-71`) 10 → 11 (append `"NO"`).
- `T1_CURVES_COUNTRIES` (`daily_curves.py:279-291`) 11 → 12 (append `"NO"`).
- `CURVE_SUPPORTED_COUNTRIES` (line 296) 11 → 12.
- `_DEFERRAL_CAL_MAP` (line 313) — remove `"NO"` key.
- `_fetch_nominals_linkers` (line 323) — add NO branch combining TE primary (6M, 52W, 10Y) + Norges Bank Path 2 (2Y) into single `nominals` dict (first hybrid country in dispatch).

## 8. HALT triggers — current status

| # | Trigger | Status |
|---|---------|--------|
| 0 | Pre-flight HALT #0 fail (connector regression OR DataAPI down) | **Cleared** — connector source unchanged since Sprint X-NO; DataAPI public + unscreened (verify in Commit 2 probe) |
| 1 | 2Y endpoint empty / 404 / key invalid (binary HALT — Path B) | Pending Commit 2 probe |
| 2 | NSS RMSE > 5 bps post-fit | Pending Commit 4 (Path A only) |
| 3 | Coverage regression > 3pp in tests | Pending pre-push gate (Commit 3 + 4) |
| 4 | Pre-push gate fail / `--no-verify` use | N/A — discipline |

Open question §7.2 (6-tenor floor vs. NO degraded-fit) is **not** a brief HALT trigger — surfaced for Hugo decision conditional on Commit 2 outcome.

## 9. Plan — 5 commits (Path A) / 3 commits (Path B)

1. **Commit 1 (this doc)** — Pre-flight findings + 2Y probe rationale + plan. Single docs commit. Surfaces §7.2 open question for Hugo.
2. **Commit 2** — Norges Bank 2Y endpoint probe (one-off script in `scripts/probes/` or inline in commit body). Verbatim API response in commit body. **Binary HALT decision** here.
   - Path A: Commits 3-5 follow.
   - Path B: skip 3-4; Commit 5 = doc closure + retro only.
3. **Commit 3** *(Path A)* — `NorgesBankConnector.fetch_govt_yield(tenor)` + unit tests + cassette + @slow live canary. Pre-push gate green.
4. **Commit 4** *(Path A, conditional on §7.2 resolution)* — Pipeline integration: `T1_SPOT_BACKFILL_COUNTRIES` + `T1_CURVES_COUNTRIES` + `CURVE_SUPPORTED_COUNTRIES` + `_DEFERRAL_CAL_MAP` (remove NO) + `_fetch_nominals_linkers` NO hybrid branch + RMSE report. Pre-push gate green.
5. **Commit 5** — Docs closure: `country_tiers.yaml` flag + `nss-curves.md` §12 country scope + `CAL-CURVES-NO-PATH-2` close-or-amend + retrospective at `docs/planning/retrospectives/week11-sprint-7b-l2-curves-no-path2-norges-2y-report.md` per brief §7 structure.

Pre-push gate (`ruff format && ruff check && mypy && pytest -m "not slow"`) mandatory before every push, no `--no-verify`.

## 10. Acceptance pre-check (brief §6 binary)

**Path A**:

- [ ] `NorgesBankConnector.fetch_govt_yield(tenor)` shipped + tested + cassette
- [ ] NSS-degraded fit NO ships with 2Y+10Y minimum (per Hugo §7.2 resolution)
- [ ] RMSE ≤ 5 bps reported (Commit 4 body)
- [ ] `country_tiers.yaml` NO `curves_live: true`
- [ ] `nss-curves.md` §12.2 NO row → §12.1
- [ ] `CAL-CURVES-NO-PATH-2` closed
- [ ] daily-curves pipeline includes NO post-merge
- [ ] T1 curves coverage 11/16 → 12/16

**Path B**:

- [ ] Norges Bank DataAPI 2Y empty result documented verbatim (Commit 2 body)
- [ ] `CAL-CURVES-NO-PATH-2` amended to EXHAUSTED
- [ ] `CAL-CURVES-NO-2Y-MISSING` filed (LOW priority)
- [ ] `country_tiers.yaml` NO `curves_path_2_pending` (or `curves_path_2_exhausted` per Hugo choice)

**Both paths**:

- [ ] No `--no-verify`
- [ ] Pre-push gate green every push
- [ ] Sprint 7B retrospective shipped (`docs/planning/retrospectives/week11-sprint-7b-l2-curves-no-path2-norges-2y-report.md`)

---

**END PRE-FLIGHT FINDINGS**
