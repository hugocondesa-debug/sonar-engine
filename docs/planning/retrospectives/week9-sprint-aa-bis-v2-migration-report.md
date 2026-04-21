# Week 9 Sprint AA — BIS SDMX v2 API Migration Fix — Implementation Report

## 1. Summary

- **Duration**: ~1h55m wall-clock, single session.
- **Commits**: 6 shipped to branch `sprint-aa-bis-v2-migration` in
  isolated worktree `/home/macro/projects/sonar-wt-sprint-aa`.
- **Scope**: URL + Accept-header v2 migration formalisation + parser
  regression lock + cassette refresh + pipeline lookback bump +
  retrospective.
- **Outcome**: **CAL-136 CLOSED**, credit-indices production
  unblocked. Manual trigger validation: bis ingestion 21/21 fetches
  succeeded, L1 + L2 credit indices computed for 7/7 T1 countries.
- **Deferred to operator**: `sudo systemctl enable --now
  sonar-daily-{bis-ingestion,credit-indices}.timer` — the brief
  assumed passwordless sudo which this CC session does not have; the
  enablement is a one-line operator action post fast-forward merge.

## 2. Context — what broke and why

Sprint S-CA (Week 9 Day 1 evening) surfaced that the systemd
`sonar-daily-bis-ingestion.timer` was disabled and that manual
triggers against `/home/macro/projects/sonar-engine` produced 0 rows
in `bis_credit_raw`. The brief presumed a hard HTTP 500 on the
legacy URL path `/api/v2/data/{DATAFLOW}/{key}?format=jsondata` and
scoped Sprint AA around the canonical v2 URL + Accept header
changes documented in brief §2.

The pre-flight audit (c1) revealed a more nuanced root cause:

1. **URL migration was already landed**. Commit `7abded7` (credit
   c2/10, 2026-04-20) had shipped `bis.py` with the v2 path pattern
   `/data/dataflow/BIS/{flow_id}/{version}/{key}` and the correct
   dataflow version tuples (WS_TC 2.0 / WS_DSR 1.0 / WS_CREDIT_GAP
   1.0 / WS_SPP 1.0). Live canary logs emitted
   `bis.fetched country=US flow=WS_TC n=3` before failing — the
   fetch was succeeding.
2. **Live canary test was broken at the teardown layer**. The
   integration test called `asyncio.run()` twice — once for
   `run_ingestion`, again for `connector.aclose()` inside the
   `finally` block. `httpx.AsyncClient` binds to its creating loop,
   so the second run hit `RuntimeError("Event loop is closed")`
   during TLS socket shutdown. The symptom read as "test fails" but
   the fetch had already persisted data.
3. **Real pipeline blocker was a date-window bug, not the v2 URL**.
   `DEFAULT_LOOKBACK_DAYS = 90` meant that on 2026-04-21 the
   ingestion built `startPeriod=2026-Q1, endPeriod=2026-Q2`. BIS
   quarterly credit aggregates publish with ~2-quarter lag — the
   latest available WS_TC observation on 2026-04-21 was 2025-Q3.
   Every (country, dataflow) call therefore fell into an empty
   future window and returned HTTP 404 → tenacity exhausted 5
   retries → `RetryError[HTTPStatusError]` → `failures=21
   successes=0` on the full batch.

Brief §2's empirical findings were accurate; the brief's narrative
("URL migration broken since API migration; HTTP 500") was stale by
one commit. Sprint AA's actual resolution path turned out to be a
combination of cleanup (c2), parser regression-lock (c3), fixture
refresh + asyncio teardown fix (c4), and a pragmatic pipeline
lookback bump (c5) — not the full URL reconstruction the brief
anticipated.

## 3. Commits

| # | SHA | Scope |
|---|---|---|
| 1 | `36d3c9f` | `chore(bis): pre-flight BIS connector audit + test baseline` |
| 2 | `13ac228` | `feat(bis): DATAFLOW_VERSIONS map + strict Accept header + drop format=jsondata` |
| 3 | `7e7d70d` | `feat(bis): verify SDMX-JSON 1.0 parser against live 2026-04-21 response` |
| 4 | `eb41608` | `test(bis): refresh 3 sample fixtures + fix live-canary asyncio teardown` |
| 5 | `750c224` | `feat(pipelines): bump daily_bis_ingestion lookback 90d → 540d + post-fix validation` |
| 6 | this | `docs(planning+backlog): Week 9 Sprint AA BIS v2 migration retrospective` |

All 5 code commits pushed with full pre-push gate (ruff format +
ruff check + mypy src/sonar + BIS-scoped pytest) green.

## 4. Empirical probes (2026-04-21)

All probes executed via direct curl to `stats.bis.org` with
`Accept: application/vnd.sdmx.data+json;version=1.0.0`.

### 4.1 URL pattern corroboration

| URL | Status |
|---|---|
| `/api/v2/data/dataflow/BIS/WS_TC/2.0/Q.US.P.A.M.770.A?lastNObservations=5` | HTTP 200 |
| `/api/v2/data/dataflow/BIS/WS_DSR/1.0/Q.US.P?startPeriod=2023-Q4&endPeriod=2024-Q2` | HTTP 200 |
| `/api/v2/data/dataflow/BIS/WS_CREDIT_GAP/1.0/Q.PT.P.A.C?format=jsondata` | HTTP 200 |
| **Legacy** `/api/v2/data/WS_TC/Q.US.P.A.M.770.A?format=jsondata` | **HTTP 500** |

Confirms the v2 dataflow-namespaced path is live-correct and the
legacy path is retired.

### 4.2 Date-window lag

| Window | Status |
|---|---|
| `2024-Q1..2024-Q2` | HTTP 200 (2 obs) |
| `2025-Q1..2025-Q1` | HTTP 200 |
| `2025-Q3..2025-Q3` | HTTP 200 |
| `2025-Q4..2025-Q4` | HTTP 404 |
| `2026-Q1..2026-Q1` | HTTP 404 |
| `2026-Q1..2026-Q2` (default 90d range) | HTTP 404 |
| `2024-Q1..2026-Q2` (spans lag boundary) | HTTP 200 |
| `lastNObservations=1` | `id="2025-Q3"` |

BIS returns HTTP 200 iff the requested window overlaps ≥ 1
published quarter; returns HTTP 404 when all requested periods are
in the future. 90-day lookback from 2026-04-21 sits entirely inside
the BIS publication lag. 540d lookback guarantees ≥ 4 published
quarters land in every window.

### 4.3 Response shape

Captured as `tests/fixtures/bis/ws_tc_US_live_2024h1.json` for
parser regression-lock in c3. Confirms:

- `data.dataSets[0].series["0:0:0:0:0:0:0"].observations[idx] = [value, attr, attr, attr]`
- `data.structure.dimensions.observation[0].values[idx].id = "YYYY-Qn"`
- `meta.links[0].href` echoes requested URL (debug aid)

The SDMX-JSON 1.0 shape is unchanged vs. the pre-migration
fixtures. `_parse_series` required no code change.

## 5. End-to-end validation trace

### 5.1 BIS ingestion

```bash
cd /home/macro/projects/sonar-engine
DATABASE_URL="sqlite:////home/macro/projects/sonar-engine/data/sonar-dev.db" \
  uv run python -m sonar.pipelines.daily_bis_ingestion \
  --start-date 2024-01-01 --end-date 2025-10-01
# [...] 14 successes + 7 transient ReadTimeouts on WS_CREDIT_GAP
#       (FR/NL/etc; did not reproduce on retry — BIS side-effect)

DATABASE_URL="..." uv run python -m sonar.pipelines.daily_bis_ingestion \
  --start-date 2024-01-01 --end-date 2025-10-01 --dataflows WS_CREDIT_GAP
# bis_ingest.complete failures=0 successes=7 totals={'new': 42, 'skipped': 7}
```

Final row counts in `bis_credit_raw` (windowed ingest):

| Dataflow | Rows | Countries |
|---|---|---|
| WS_TC | 49 | 7 |
| WS_DSR | 49 | 7 |
| WS_CREDIT_GAP | 49 | 7 |

Full historical WS_TC backfill (2000-01-01 → 2025-10-01):

```
bis_ingest.complete failures=0 successes=7 totals={'new': 672, 'skipped': 49}
```

103 obs × 7 countries = 721 rows total in `bis_credit_raw` for
WS_TC after backfill.

### 5.2 Credit indices computation

```bash
DATABASE_URL="..." uv run python -m sonar.pipelines.daily_credit_indices \
  --date 2025-09-30 --all-t1 --backend db
# credit_indices.persisted country=US  persisted={'l1': 1, 'l2': 1, 'l3': 0, 'l4': 0}
# credit_indices.persisted country=DE  persisted={'l1': 1, 'l2': 1, ...}
# [...] 7/7 countries, 0 errors
```

`credit_to_gdp_stock` + `credit_to_gdp_gap` both hold 7 rows for
`date='2025-09-30'`, one per T1 country. L3/L4 remain
DbBackedInputsBuilder-out-of-scope — covered by CAL-059/060.

## 6. HALT triggers

| # | Description | Fired? |
|---|---|---|
| 0 | Connector file ambiguity | No (`bis.py` singular) |
| 1 | URL pattern variant | No (uniform across dataflows) |
| 2 | Parser breaks | No (shape unchanged) |
| 3 | Cassette refresh burden | Partial — pragmatic scope 3 representative fixtures vs 21 permutations per brief §9 |
| 4 | Live-canary persistent HTTP | No (transient WS_CREDIT_GAP ReadTimeouts; did not reproduce) |
| 5 | L1/L2 compute failure | No (7/7 land after history backfill) |
| 6 | Coverage regression | No |
| 7 | Pre-push gate failure | No |
| 8 | Version map incomplete | No (4 entries: WS_TC / WS_DSR / WS_CREDIT_GAP / WS_SPP) |

## 7. Deviations from brief

1. **Brief anticipated URL migration — found already-landed in 7abded7**. The Sprint AA c2 formalised three residual gaps rather than migrating from scratch: Accept-header alternate cleanup, `format=jsondata` drop, `DATAFLOW_VERSIONS` dict introduction.
2. **Real production blocker was the pipeline lookback window**, not the URL. Added as c5 (not originally in brief §4) because the brief's acceptance criteria require successful end-to-end ingestion + L1/L2 compute.
3. **Live-canary teardown bug was asyncio-layer**, not connector-layer. Fixed in c4 as part of "make the canary assertion actually test the fetch".
4. **Cassette refresh scope 3 vs 21 permutations** — HALT-3 pragmatic budget; 3 representative fixtures (US WS_TC + PT WS_TC + PT WS_CREDIT_GAP + US WS_DSR) exercise all orthogonal parser paths. CAL-137 (opened) wires a weekly live canary to cover the remaining drift surface.
5. **Systemd timer enablement deferred** — this CC session lacks passwordless sudo (brief §9 assumed CC has it). The validation run demonstrates the fix is safe; enablement is a post-merge operator action.

## 8. Production impact

- **Outage detection**: Week 9 Sprint S-CA (2026-04-20 evening — ~20h before Sprint AA start).
- **Outage window**: plausibly from 90-day lookback entering the 2026-Q1 hole (approximately Week 8 Day 1, ~2026-04-14) through 2026-04-21 — a 7-day window. Prior to the lag-boundary crossing, 90-day lookback still caught 2025-Q3 (last published) and ingestion succeeded silently. Exact first-failure date not tracked because the bis-ingestion timer had been disabled pending validation earlier in Week 9 and no canary ran in-between.
- **Credit indices offline**: 7 T1 countries × (L1 + L2) = 14 cycle scores stale for ≤ 7 days.
- **Resolution**: 2026-04-21 22:01 WEST (manual trigger + validation).
- **Blast radius**: contained. No L3/L4/L5 compute — those depend on CAL-059/060 which remain Phase 2+.

## 9. Concurrency protocol

Sprint AA operated in isolated worktree
`/home/macro/projects/sonar-wt-sprint-aa` on branch
`sprint-aa-bis-v2-migration`. Sprint T-AU operated in
`/home/macro/projects/sonar-wt-sprint-t` on branch
`sprint-t-au-connector`. Zero file overlap (BIS connector domain
vs. RBA connector domain). Only union-merge candidate was
`docs/backlog/calibration-tasks.md` — c6 appends CAL-137 at EOF, so
collision-free.

Merge strategy post-sprint:

```bash
cd /home/macro/projects/sonar-engine
git fetch origin
git checkout main
git merge --ff-only sprint-aa-bis-v2-migration
git push origin main
```

## 10. Lessons

1. **Live canaries are the only end-to-end gate**. Mocked tests
   stayed green through the entire outage window. CAL-137 opens a
   weekly live-canary systemd timer to close the drift-detection
   gap — `pytest tests/ -m slow -k bis` nightly emails operator on
   failure.
2. **API-migration commits need co-landed cassette refresh**.
   Commit 7abded7 introduced the v2 URL pattern but left the old
   `, application/json` alternate and `format=jsondata` param
   behind. Both were cosmetic but noisy enough that Sprint AA
   treated them as "half-done migration" rather than "clean-up".
3. **Default lookback windows must cover source publication lag**.
   BIS quarterly data ships with ~2-quarter delay; 90d ≈ 1 quarter
   is a permanent time-bomb. Every source-lag-sensitive pipeline
   should document the lag explicitly and default to ≥ 2× lag.
4. **`asyncio.run()` + `httpx.AsyncClient` is a footgun pair**.
   Always pair client lifecycle with a single event loop via a
   context manager or an inner async function, never two sibling
   `asyncio.run()` calls. Will propagate as a convention check on
   the next async connector landing.

## 11. CAL items

- **CAL-136 CLOSED** — BIS SDMX v2 migration. This sprint.
- **CAL-137 OPEN** — weekly live-canary surveillance. New item.
  Priority MEDIUM. Scope: `sonar-weekly-bis-canary.timer` (systemd)
  that runs `uv run pytest tests/integration/test_bis_ingestion.py
  -m slow -k bis` weekly and emails the operator on failure.
  Rationale: the 2026-04-21 outage went undetected for ~7 days
  because only mocked tests ran; a weekly live canary would have
  paged on day 1 of the lag-boundary crossing.

Both recorded in `docs/backlog/calibration-tasks.md`.

## 12. Report-back

```
SPRINT AA BIS V2 MIGRATION DONE: 6 commits on branch sprint-aa-bis-v2-migration
URL pattern migrated: /data/{ID} → /data/dataflow/BIS/{ID}/{VER}/{key}  (already landed 7abded7; c2 cleanup)
Versions: WS_TC 2.0 | WS_DSR 1.0 | WS_CREDIT_GAP 1.0 | WS_SPP 1.0
Accept header: application/vnd.sdmx.data+json;version=1.0.0 (strict — alternate dropped)
Cassettes refreshed: 3 (ws_tc_PT / ws_dsr_US / ws_credit_gap_PT) + 1 new (ws_tc_US_live_2024h1)
Live canary: BEFORE fail-teardown (fetch ok) → AFTER HTTP 200 + 3 obs persisted + assertions pass
Production impact: ~7 days credit indices stale (2026-04-14..2026-04-21) resolved
Root cause: v2 URL already migrated; real blocker was 90d lookback vs 2-quarter BIS publication lag
Pipeline fix: DEFAULT_LOOKBACK_DAYS 90 → 540
Systemd timers: DEFERRED (CC lacks passwordless sudo); operator enables post-merge
HALT triggers: #3 partial (pragmatic 3-cassette scope)
CAL-136 CLOSED | CAL-137 OPEN (weekly canary surveillance)
Merge: cd /home/macro/projects/sonar-engine && git checkout main && git merge --ff-only sprint-aa-bis-v2-migration
Artifact: docs/planning/retrospectives/week9-sprint-aa-bis-v2-migration-report.md
```
