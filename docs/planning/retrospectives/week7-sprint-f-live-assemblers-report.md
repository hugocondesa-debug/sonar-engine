# Week 7 Sprint F — Live Connector Assemblers

**Brief:** user-provided spec (no brief file on disk — SESSION_CONTEXT authorized autonomy)
**Duration:** ~2h (2026-04-21)
**Commits:** 4 + retrospective (sprint7-F c1–c5)
**Status:** SPRINT CLOSED

---

## 1. Summary

Shipped the live-connector assembly layer for the three Phase-1 L2
overlays (ERP US + CRP + rating-spread). The assembly module is a
single new file `src/sonar/overlays/live_assemblers.py` that:

- Sources ERP US inputs from FMP (SPX EOD) + Shiller (CAPE + earnings)
  + Multpl (dividend yield) + Damodaran (annual xval reference).
- Sources CRP via Trading Economics 10Y sovereign yields with a
  rating-method fallback that reads `ratings_consolidated` from a
  prior-day persisted row.
- Reads rating-spread inputs from `ratings_agency_raw` (the scrape
  connectors themselves remain out of scope — see §8).

The pipeline CLI grew `--backend [default|live]` alongside
`--fmp-api-key` / `--te-api-key` / `--fred-api-key` / `--cache-dir`;
`daily_overlays` now has a production-ready live path gated behind
explicit creds.

**CAL status**: CAL-109 ERP-US-live **CLOSED**; CAL-110 CRP-live
**CLOSED** for SOV_SPREAD + persisted-rating fallback (CDS method
remains unimplementable without an FMP CDS endpoint); CAL-111
**PARTIAL** — DB-backed reader shipped with schema-drift guards, but
the agency-scrape connectors (Moody's / S&P / Fitch / DBRS /
Damodaran-ctryprem backfill) were moved to a new backlog item below.

## 2. Commits

| # | SHA | Title | Gate |
|---|-----|-------|------|
| 1 | `9a149ac` | feat(overlays): live-connector assemblers for ERP/CRP/rating (CAL-109/110/111) | green |
| 2 | `0e59614` | feat(pipelines): daily_overlays --backend live CLI | green |
| 3 | `9a3d716` | test(integration): daily_overlays live smoke — 7-T1 + graceful degradation | green |
| 4 | `c877cf5` | test(integration): daily_overlays US end-to-end canary | green |
| 5 | _this doc_ | docs(planning): retrospective | pending |

Pre-push gate (`ruff format + ruff check + full-project mypy +
pytest --no-cov` via pre-commit) green before every push. Pre-commit
detect-secrets flagged placeholder API-key strings in CLI tests →
swapped to short tokens + `# pragma: allowlist secret` in C2. No
`--no-verify`.

## 3. Design decisions

### Single-file live_assemblers vs per-overlay split

The three builders share a lot (error-exception set, flag
conventions, Protocol surface) and are orchestrated together by
`LiveInputsBuilder`. Splitting into three files would multiply import
surface without daylighting any genuine layering. One module, four
public symbols (three builders + suite).

### Graceful degradation

Every builder catches the union `(OverlayError, httpx.HTTPError,
ValueError, RuntimeError)` at connector boundaries. Behaviour:

- **Critical-field miss** (ERP: FMP/Shiller; CRP: no method; rating:
  no DB rows) → return `None`; orchestrator reports structured skip.
- **Non-critical-field miss** (Multpl down, Damodaran year absent) →
  add `upstream_flags` entry, fall through to fallback.

The flag lexicon picks up `FORWARD_EPS_PROXY_TRAILING` +
`DIVIDEND_YIELD_FALLBACK_SHILLER` + `DAMODARAN_XVAL_UNAVAILABLE` as
new Sprint-F additions.

### Schema-drift guards (CAL-111)

`_EXPECTED_AGENCY_ROW_FIELDS` enforces minimum fields on each
persisted `ratings_agency_raw` row before it reaches
`consolidate()`. Missing field → drop row + emit
`RATING_SCHEMA_DRIFT`. Unknown agency token → drop + emit
`RATING_UNKNOWN_TOKEN`. Both flags propagate via
`_preconsolidation_flags` marker (stripped before the bundle is
handed to the consolidator, since the caller signature rejects
unknown kwargs).

## 4. Test coverage

### Unit (C1 — 14 tests in `test_live_assemblers.py`)

- **build_erp_us_from_live**: happy path (4-method input), FMP empty,
  FMP HTTP error, Multpl error (fallback flag), Multpl absent (flag),
  Damodaran row missing (flag), Damodaran connector absent (skip flag).
- **build_rating_from_live**: reads persisted rows, zero rows →
  None, unknown token → drop, rating_type filter.
- **LiveInputsBuilder**: US full stack, non-US skips ERP, risk-free
  resolver error graceful.

### CLI dispatch (C2 — 7 tests in `test_daily_overlays.py`)

Invalid backend / missing FMP key / missing TE key / missing FRED
key / invalid date / missing country → all EXIT_IO. Factory instance
test confirms 6 closable connectors returned.

### Integration smoke (C3 — 10 tests in `test_daily_overlays_live_smoke.py`)

7-country parametrised sweep: US/DE BENCHMARK + 5 periphery (FR, IT,
ES, NL, PT) SOV_SPREAD via TE fake. Plus: TE 404 → RATING fallback
(ratings_consolidated seeded as day-N-1 state); no-source-all-skip
case; FMP failure isolates ERP.

### End-to-end US canary (C4 — 1 test in `test_daily_overlays_us_e2e.py`)

Canonical Dec-2024 US run — `ERP_CANONICAL_v0.1` + 4-method canonical
+ `FORWARD_EPS_PROXY_TRAILING` + CRP BENCHMARK + 3-agency
consolidation + persist verification.

## 5. HALT triggers

9 triggers atomic; none fired this sprint:

| # | Trigger | Fired | Notes |
|---|---------|-------|-------|
| 0 | Spec deviation | — | No spec; brief said "FMP agency scrape" which doesn't exist; adapted with DB-backed reader + documented limitation |
| 1 | Math error | — | No new compute math; builders marshal data only |
| 2 | Migration collision | — | No migrations this sprint |
| 3 | Units/bps mismatch | — | TE `yield_bps` (int) → decimal conversion at connector boundary; verified against `units.md` §Spreads |
| 4 | models.py bookmark | — | Not touched |
| 5 | Policy 1 math | — | N/A — no composite compute |
| 6 | Session leak | — | LiveInputsBuilder uses single asyncio.run per tick; connector lifecycle explicit |
| 7 | Confidence out of [0,1] | — | N/A — reusing existing overlay confidence paths |
| 8 | Full-project mypy regression | — | 95 src files green before every push |
| 9 | Schema drift unflagged | — | CAL-111 schema guard emits `RATING_SCHEMA_DRIFT`; `RATING_UNKNOWN_TOKEN` catches lookup misses |

## 6. Concurrency report

Sprint E (DB-backed E2/M3 readers + pipeline wiring) ran in parallel
tmux. Observable interactions:

- `src/sonar/pipelines/daily_overlays.py` (my file) shipped before
  Sprint E landed `daily_economic_indices.py` / `daily_monetary_
  indices.py` mods. Zero overlap — different files.
- `src/sonar/db/persistence.py` not touched by Sprint F (all helpers
  already exist from Sprint C).
- Two push-races resolved by standard `git pull --rebase` with no
  conflicts (only line-adjacency in unrelated pipelines).

Sprint E shipped CAL-108 between my C1 and C2 pushes. No interference
with my work.

## 7. Deviations from brief

- **Commit count**: brief projected 8, shipped 5 effective (4 + retro).
  Rationale: the three live builders share a single module, Protocol,
  exception set, and test file; atomic-per-CAL splits would have been
  artificial. Deviation logged; functionality unchanged.
- **FMP CDS hierarchy** (CAL-110): `FMPConnector` only exposes index
  EOD history — no `/cds` endpoint in the Week 3.5 implementation.
  `build_crp_from_live` skips the CDS branch entirely (no scaffold);
  the overlay module's `build_canonical` still supports CDS when a
  caller provides it directly.
- **FMP agency scrape** (CAL-111): FMP has no agency-ratings endpoint
  either in the current connector scope. Shipped path: DB-backed
  reader over `ratings_agency_raw` + schema-drift guards; the scrape
  connectors themselves (Moody's / S&P / Fitch / DBRS event-driven
  poll + Damodaran `ctryprem.xlsx` historical) become CAL-115 (see §8).
- **Expected-inflation live path**: deliberately not wired — brief
  scoped three CALs (ERP/CRP/rating). BEI live builder is Sprint G+.

## 8. New backlog items

| CAL | Subject | Notes |
|-----|---------|-------|
| **CAL-115** | Agency-rating scrape connectors | S&P / Moody's / Fitch / DBRS event-driven polling (4h cadence per spec §3) + Damodaran `ctryprem.xlsx` historical backfill (pre-2023 per `rating-spread.md` v0.2). Schema-drift guard critical — Damodaran column names drift quarterly. Estimated 2 sprints. |
| **CAL-116** | FMP CDS endpoint integration | If/when FMP ships a CDS endpoint (or we pivot to Bloomberg/Markit), wire `build_crp_from_live` CDS hierarchy branch. Currently build_canonical supports CDS but pipeline doesn't feed it. |
| **CAL-117** | Forward-EPS (FactSet / IBES) | ERP `forward_earnings_est` is currently proxied from trailing earnings with `FORWARD_EPS_PROXY_TRAILING` flag. Real forward-EPS connector would close the ERP DCF vs live-consensus gap. |

## 9. Sprint readiness downstream

- **daily pipelines cron**: `--backend live --fmp-api-key ... --te-api-key
  ... --fred-api-key ...` runs end-to-end. Connector lifecycle +
  exit-code mapping mirror `daily_economic_indices`.
- **L6 integration**: ERP / CRP / rating consumers can now assume a
  live feed rather than manual `StaticInputsBuilder` seeding. CRP's
  fallback hierarchy (SOV_SPREAD > RATING) plays nicely with the
  overlay spec's day-N-1 persistence pattern.
- **Monitoring**: structlog events surface the live-path signals —
  `erp_live.fmp_error`, `crp_live.te_error`, `rating_live.db_error`,
  `live_assemblers.risk_free_error`. Dashboard wiring is Phase 2+.

*End of retrospective. Sprint CLOSED 2026-04-21.*
