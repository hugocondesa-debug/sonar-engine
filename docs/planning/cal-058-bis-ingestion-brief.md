# CAL-058 BIS Ingestion Pipeline Brief — v1

**Target**: Resolve CAL-058 — live BIS data ingestion enabling credit indices to run with real data (not synthetic fixtures)
**Priority**: MEDIUM (credit indices code-ready but data-empty; unlocks production runs)
**Budget**: 3–4h CC autonomous
**Commits**: ~5–7
**Base**: main HEAD post credit track (`80617d1` or later)
**Concurrency**: Parallel to F-cycle brief in tmux `sonar-l3`. See §Concurrency.

---

## 1. Scope

In:
- `src/sonar/db/models.py` — new `BisCreditRaw` ORM inside new bookmark zone `# === Ingestion models ===`
- Alembic migration **011** — `bis_credit_raw` table for persisted BIS observations
- `src/sonar/pipelines/daily_bis_ingestion.py` — daily pass fetching BIS WS_TC + WS_DSR + WS_CREDIT_GAP for 7 T1 countries, persisting raw observations
- `src/sonar/pipelines/daily_credit_indices.py` extension — new `DbBackedInputsBuilder` that reads from `bis_credit_raw` instead of returning empty
- Integration test: end-to-end ingest → compute → persist for 1 country (US, smallest fixture)
- Live canary: `@pytest.mark.slow` test hits real BIS for US 2024-Q2 and asserts non-empty ingest

Out:
- GDP ingestion (existing FRED / Eurostat connectors handle this per-compute; no centralized GDP cache needed this sprint)
- Historical backfill (this sprint ships forward-looking daily pass; backfill is separate CAL)
- Retry / backoff sophistication beyond BIS 1-req/sec polite pacing
- Error alerting / dashboard
- Non-BIS data ingestion (F-cycle connectors handled separately)
- Multi-country parallelism within a single pipeline run (sequential is fine; BIS rate-limit gentle)
- Schema evolution handling (CAL-019 already resolved WS_TC key schema)

---

## 2. Spec reference

Authoritative:
- `docs/backlog/calibration-tasks.md` — CAL-058 entry (created Commit 10 of credit track, `80617d1`)
- `docs/specs/indices/credit/L{1,2,3,4}-*.md` — upstream consumers of the ingested data
- `docs/data_sources/credit.md` §3.1 — BIS endpoints + key schemas (amended Commit 1 of credit track)
- `docs/specs/conventions/units.md`, `flags.md`, `patterns.md`
- SESSION_CONTEXT §Decision authority + §Brief format + §Regras operacionais

Existing assets:
- `src/sonar/connectors/bis.py` — 3 methods `fetch_dsr`, `fetch_credit_gap`, `fetch_credit_stock_ratio` (live-validated Commit 2 of credit track)
- `src/sonar/pipelines/daily_credit_indices.py` — current `default_inputs_builder` returns empty bundle (per credit retrospective deviation #2)

---

## 3. Concurrency — parallel protocol with F-cycle brief

F-cycle brief runs concurrently in tmux `sonar-l3`. Both push to main.

**Hard-locked resource allocation**:
- Migration number: **011** (F-cycle uses 010)
- `src/sonar/db/models.py`: **new bookmark zone** `# === Ingestion models ===` — positioned after `# === Indices models end ===`. Create defensively if absent in Commit 1.
- Pipeline files: `daily_bis_ingestion.py` new; `daily_credit_indices.py` extension only (add `DbBackedInputsBuilder` class, do NOT modify existing `default_inputs_builder` signature)
- Tests: new `tests/integration/test_bis_ingestion.py` + `tests/unit/test_pipelines/test_daily_bis_ingestion.py`
- `pyproject.toml`: no new deps expected
- `docs/data_sources/credit.md`: may need minor amendment documenting ingestion cadence; coordinate via rebase if F-cycle also touches this file (unlikely)

**Push race handling**:
- `git push` rejection → `git pull --rebase origin main` → resolve trivial conflicts → re-push
- Never `--force`
- Migration 010 ↔ 011 collision → HALT
- `models.py` conflict: this brief adds a NEW bookmark zone AFTER existing Indices zone. If F-cycle somehow touches lines below Indices zone (shouldn't per its brief) → HALT

**Start order**: F-cycle arranca primeiro (creates migration 010). This brief arranca ~1 min depois; verifies 010 in `alembic heads` before creating 011.

---

## 4. Commits

### Commit 1 — Ingestion models scaffold + bookmark zone

```
feat(db): BisCreditRaw ORM scaffold + Ingestion bookmark zone

Create new bookmark in src/sonar/db/models.py:
- "# === Ingestion models begin ===" / "# === Ingestion models end ==="
- Position AFTER "# === Indices models end ===" to keep sections ordered:
  ERP → Indices → Ingestion

Inside new zone, scaffold BisCreditRaw ORM:
- id INTEGER PRIMARY KEY
- country_code TEXT NOT NULL
- date DATE NOT NULL (quarter-end)
- dataflow TEXT NOT NULL CHECK (dataflow IN ('WS_TC','WS_DSR','WS_CREDIT_GAP'))
- value_raw REAL NOT NULL  (raw observation value per dataflow unit)
- unit_descriptor TEXT NOT NULL  (e.g., 'pct_gdp', 'dsr_pct', 'gap_pp')
- fetched_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
- fetch_response_hash TEXT  (sha256 of raw BIS response for audit)
- UNIQUE (country_code, date, dataflow)
- Index idx_bcr_cd on (country_code, date)

Tests:
- test_bis_credit_raw_model.py: 4 unit — insert, UNIQUE violation,
  CHECK constraint, index usage
- Package import tests

No migration yet — Commit 2.
```

### Commit 2 — Alembic migration 011

```
feat(db): migration 011 bis_credit_raw ingestion table

Single table per Commit 1 schema. CHECK constraints + UNIQUE +
Index as specified.

Rationale:
- Raw observations separate from computed indices tables
- Enables re-computation of indices without re-fetching BIS
- Audit trail via fetch_response_hash
- Simple schema — no over-engineering (no vintage tracking,
  no supersedes chains, no connector metadata bloat)

Alembic upgrade/downgrade round-trip verified clean.

Pre-flight: verify `alembic heads` shows 010 (F-cycle migration)
merged before creating 011. If head is still 009, proceed with 010
numbering — F-cycle and this brief coordinate on migration numbers
at push time; whichever pushes first claims 010 de facto. If HEAD is
009 and we push 010 first, F-cycle will bump to 011 via rebase.
```

### Commit 3 — daily_bis_ingestion.py pipeline

```
feat(pipelines): daily_bis_ingestion.py L0 pass for 7 T1 countries

src/sonar/pipelines/daily_bis_ingestion.py:
- Fetches BIS WS_TC + WS_DSR + WS_CREDIT_GAP for 7 T1 countries
  (US, DE, PT, IT, ES, FR, NL) for given date range
- Uses existing bis.py connector (read-only consumer)
- Persists to bis_credit_raw via persist_bis_raw_observations helper
- Idempotent: UNIQUE (country_code, date, dataflow) + upsert pattern
  (skip if identical fetch_response_hash; log warning if changed
  vs existing row — raises BisDataRevisionWarning flag)
- Sequential country iteration (7 × 3 dataflows = 21 fetches; at 1
  req/sec polite pacing = ~21s per full pass)
- CLI: python -m sonar.pipelines.daily_bis_ingestion \
         [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]
         [--countries US,DE,PT,...] [--dataflows WS_TC,WS_DSR,WS_CREDIT_GAP]
- Default: last 90 days back from today, all 7 T1, all 3 dataflows

Exit codes:
- 0: success (all fetches OK, persistence green)
- 1: config error (bad CLI args)
- 2: partial (some countries succeeded, others failed; log detail)
- 3: total failure (all fetches failed — likely network or BIS outage)

persist_bis_raw_observations helper in src/sonar/db/persistence.py:
- Batched insert with ON CONFLICT handling (SQLite) or upsert (PG
  for Phase 2+)
- Returns count_new, count_skipped, count_updated dict

Unit tests ≥ 8:
- Synthetic builder returning mocked observations
- Upsert behavior (skip identical, warn on revision)
- CLI arg parsing
- Exit code matrix (success, partial, failure)
```

### Commit 4 — daily_credit_indices.py DbBackedInputsBuilder

```
feat(pipelines): DbBackedInputsBuilder reads from bis_credit_raw

Extend src/sonar/pipelines/daily_credit_indices.py:

New class DbBackedInputsBuilder:
- __init__(session: Session)
- build(country: str, date: date) -> CreditIndicesInputs
- Queries bis_credit_raw for (country, date range appropriate for
  each index's history requirements):
  - L1: 20Y rolling → fetch [date - 22Y, date]
  - L2: 25Y for HP stability → fetch [date - 26Y, date]
  - L3: 3Y minimum + 20Y z-score → fetch [date - 22Y, date]
  - L4: 20Y rolling → fetch [date - 22Y, date]
- Assembles CreditIndicesInputs with credit_stock_lcu series,
  gdp_nominal_lcu series, etc. from raw observations
- Handles data gaps: interpolates ≤ 1 quarter; raises
  InsufficientInputsError if gap > 1Q or history < hard minimum
- Flag propagation: if raw observations carry flags (future), propagate

Existing default_inputs_builder (returns empty bundle) stays as
backward-compat default. DbBackedInputsBuilder is opt-in via:
  python -m sonar.pipelines.daily_credit_indices \
         --country US --date 2024-01-02 --backend=db

Tests ≥ 6:
- DbBackedInputsBuilder with seeded bis_credit_raw (fixtures)
- Interpolation of 1Q gap
- Raise on 2Q gap
- Raise on insufficient history
- Flag propagation
- CLI --backend=db integration
```

### Commit 5 — End-to-end integration test

```
test(integration): BIS ingest → credit indices compute vertical slice

tests/integration/test_bis_ingestion.py:
- @pytest.mark.slow — actual BIS network call (gated behind CLI flag)
- Fetches US WS_TC + WS_DSR for 2024-Q2 (known-good per credit track)
- Persists to bis_credit_raw
- Invokes daily_credit_indices with --backend=db for US 2024-Q2
- Asserts 4 rows persisted in credit_to_gdp_stock, credit_to_gdp_gap,
  credit_impulse, dsr
- Asserts values within sanity bands (US DSR ~14-16%, etc.)
- Teardown: rollback session

Separate unit integration test (mocked BIS):
- Seeds bis_credit_raw with fixture data
- Invokes daily_credit_indices with --backend=db
- Asserts full pipeline produces persisted indices

≥ 5 integration tests total.
```

### Commit 6 — Documentation + retrospective

```
docs(planning): CAL-058 closure + BIS ingestion retrospective

File: docs/planning/retrospectives/cal-058-bis-ingestion-report.md

Structure:
- Summary (duration, commits, CAL-058 closed status)
- Commits table with SHAs
- Migration 011 schema rationale
- Ingestion cadence: daily, 7 T1 countries × 3 dataflows, ~21s per pass
- DbBackedInputsBuilder behavior:
  - History assembly rules per index
  - Gap interpolation / rejection policies
  - Flag propagation
- Live canary validation: US 2024-Q2 round-trip outcome
- Connector load test: 7 countries × 3 dataflows sequential timing
- HALT triggers fired / not fired
- Coverage delta
- Pipeline status:
  - default builder: empty bundle (backward-compat, synthetic-only)
  - DB builder: opt-in via --backend=db, production-ready
- New backlog items surfaced (unlikely but capture any edge cases)
- Blockers for Week 5+: none (CAL-058 scope fully closed)

Close CAL-058 in docs/backlog/calibration-tasks.md with status
CLOSED + reference SHA of this commit.

Document docs/data_sources/credit.md §X new section "Ingestion cadence":
- Daily pass via daily_bis_ingestion.py
- 90-day default backfill window
- Idempotent upsert semantics
- Revision detection via fetch_response_hash

Commit msg:
docs(planning): CAL-058 BIS ingestion closed + retrospective

Credit indices now production-ready with --backend=db builder.
```

---

## 5. HALT triggers (atomic)

1. **BIS network failure mid-sprint** — WS_TC returns 500 or sustained 429 for 10+ minutes → halt, revisit timing
2. **Migration 011 collision** with F-cycle 010 — if rebase shows 010 already taken by this brief (we pushed first) → bump F-cycle to 011 via their rebase; chat reconciles if conflict persists
3. **bis_credit_raw schema inadequate** for some edge case (e.g., BIS returns aggregated obs not per-quarter) → HALT, redesign schema
4. **fetch_response_hash mechanism unviable** (BIS responses have timestamps / nonces that break hash stability) → drop hash mechanism, use simpler last-modified tracking; document shift
5. **DbBackedInputsBuilder history requirements exceed BIS data availability** (e.g., L2 needs 25Y but PT WS_TC only has 20Y) → raise InsufficientInputsError + flag BIS_HISTORY_TRUNCATED; don't extend history artificially
6. **Gap interpolation policy wrong** — credit track spec says "linear interp upstream for ≤1Q gaps"; if BIS gaps are larger or non-linear, pipe spec section to chat for clarification
7. **persist_bis_raw_observations race condition** with concurrent daily_credit_indices compute (unlikely — sequential within single pipeline) → halt, add lock
8. **Coverage regression** > 3pp on existing scopes → HALT
9. **Pre-push gate fails** → fix before push, no `--no-verify`
10. **`models.py` rebase conflict outside Ingestion bookmark zone** → F-cycle violated discipline → HALT

"User authorized in principle" does NOT cover specific triggers.

---

## 6. Acceptance

### Per-commit
Per commit body checklist.

### Global sprint-end
- [ ] 5-7 commits pushed, main HEAD matches remote, CI green
- [ ] Migration 011 applied clean; downgrade/upgrade round-trip green
- [ ] `src/sonar/pipelines/daily_bis_ingestion.py` coverage ≥ 85%
- [ ] `src/sonar/db/persistence.py` new persist_bis_raw_observations helper coverage ≥ 90%
- [ ] `DbBackedInputsBuilder` coverage ≥ 90%
- [ ] 7 T1 countries × 3 dataflows live-ingest test green (or mocked equivalent with cassettes)
- [ ] End-to-end smoke: `python -m sonar.pipelines.daily_bis_ingestion --countries US --start-date 2024-04-01 --end-date 2024-07-01` → populates bis_credit_raw
- [ ] Followed by: `python -m sonar.pipelines.daily_credit_indices --country US --date 2024-07-01 --backend=db` → 4 rows in credit_to_gdp_stock, credit_to_gdp_gap, credit_impulse, dsr
- [ ] US DSR 2024-Q2 within 1pp of BIS-published value
- [ ] CAL-058 CLOSED in docs/backlog/calibration-tasks.md
- [ ] No `--no-verify` pushes

---

## 7. Report-back artifact export (mandatory)

File: `docs/planning/retrospectives/cal-058-bis-ingestion-report.md`

Structure per §4 Commit 6.

**Per-commit tmux echoes** (short form):
```
COMMIT N/6 DONE: <scope>, SHA, coverage delta, HALT status
```

**Final tmux echo**:
```
CAL-058 DONE: N commits, BIS ingestion pipeline live
US 2024-Q2 round-trip: DSR within Xpp of BIS-published
HALT triggers: [list or "none"]
Artifact: docs/planning/retrospectives/cal-058-bis-ingestion-report.md
```

---

## 8. Pre-push gate (mandatory per CI-debt saga lessons)

Before every `git push`:
```
uv run ruff format --check src/sonar tests
uv run ruff check src/sonar tests
uv run mypy src/sonar
uv run pytest tests/unit/ -x --no-cov
```

All four must exit 0. No `--no-verify`.

---

## 9. Notes on implementation

### BIS revisions
BIS sometimes revises historical quarters. Handle via fetch_response_hash: if new fetch for existing (country, date, dataflow) produces different value_raw, log BIS_DATA_REVISION warning + update row with fetched_at bumped. Keep audit trail simple (no supersedes chain Phase 1).

### GDP not cached
Brief explicitly does NOT ingest GDP into a cache table. Existing FRED / Eurostat / BIS-embedded GDP fetches happen at compute time in indices modules. Centralizing GDP is scope creep; each index knows its preferred GDP source.

### Sequential, not parallel
7 countries × 3 dataflows = 21 BIS requests. At 1 req/sec polite pacing, ~21s per full pass. No async/parallel — simpler code, respects BIS rate-limit conservatively. Parallelization is CAL if needed later.

### DbBackedInputsBuilder opt-in
Existing `default_inputs_builder` stays as default. This is intentional:
1. Backward-compat with credit track tests (synthetic fixture-driven)
2. Production ops teams can choose ingestion mode via CLI
3. Future migration to DB-default is trivial flip

### Parallel F-cycle track
Financial indices run concurrently. Zero overlap expected. If `models.py` race → Ingestion bookmark zone is NEW (below Indices) — F-cycle should NOT touch it. HALT #10 covers.

---

*End of CAL-058 brief. 5-7 commits. BIS ingestion live, DbBackedInputsBuilder opt-in, credit indices production-ready. Concurrency with F-cycle via migration numbering + bookmark zone separation + file-level isolation.*
