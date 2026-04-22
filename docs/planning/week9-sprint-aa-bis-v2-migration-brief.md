# Week 9 Sprint AA — BIS SDMX v2 API Migration Fix

**Target**: Restore BIS ingestion pipeline operational. BIS API migrated URL path structure + dataflow versioning (WS_TC → 2.0). Current connector broken since API migration; all live canaries failing HTTP 500. Credit indices production blocked.
**Priority**: URGENT (production outage — credit indices offline 7 T1 countries)
**Budget**: 1.5-2.5h CC autonomous
**Commits**: ~4-6
**Base**: branch `sprint-aa-bis-v2-migration` (isolated worktree `/home/macro/projects/sonar-wt-sprint-aa`)
**Concurrency**: Parallel to Sprint T-AU Australia RBA connector in worktree `sonar-wt-sprint-t`. See §3.

---

## 1. Scope

In:
- `src/sonar/connectors/bis.py` OR `src/sonar/connectors/bis_sdmx.py` (identify actual file name Commit 1)
- Migrate URL path pattern + add dataflow version map + update Accept header
- Cassette refresh for 7 T1 × 3 dataflows (WS_TC + WS_DSR + WS_CREDIT_GAP)
- Live canary restoration (`@pytest.mark.slow tests/integration/test_bis_ingestion.py::TestLiveCanary`)
- Re-enable systemd timers (bis-ingestion + credit-indices)
- CAL-136 formal closure (opened this sprint) + CAL-137 (weekly canary schedule) tracking
- Retrospective

Out:
- CAL-059/060 L3/L4 DbBackedInputsBuilder extensions (separate work, BIS-agnostic)
- Credit indices logic changes (L1/L2/L3/L4 formulas unchanged)
- BIS SDMX v3 migration (not yet needed; v2 still live at stats.bis.org)
- Other connector migrations (scope strict to BIS)

---

## 2. Empirical findings (pre-validated — DO NOT re-probe)

Operator probed BIS API exhaustively Day 1 evening. Confirmed findings:

### URL pattern (confirmed HTTP 200)
```
https://stats.bis.org/api/v2/data/dataflow/{AGENCY}/{DATAFLOW_ID}/{VERSION}/{key}?{params}
```

Example working:
```
GET https://stats.bis.org/api/v2/data/dataflow/BIS/WS_TC/2.0/Q.US.P.A.M.770.A?lastNObservations=5
Accept: application/vnd.sdmx.data+json;version=1.0.0
```

### Accept header (confirmed)
`application/vnd.sdmx.data+json;version=1.0.0` — MUST use this exact string. Variants rejected:
- `;version=2.0.0` → HTTP 406
- `;version=3.0.0` → HTTP 406
- No header → returns XML StructureSpecificData (not preferred)

### Dataflow versions (confirmed via discovery + structure endpoints)
| Dataflow | Current Version |
|----------|-----------------|
| WS_TC | **2.0** (migrated from 1.0) |
| WS_DSR | 1.0 (unchanged) |
| WS_CREDIT_GAP | 1.0 (unchanged) |

### Dimension order (CAL-019 legacy — still correct)
`FREQ.BORROWERS_CTY.TC_BORROWERS.TC_LENDERS.VALUATION.UNIT_TYPE.TC_ADJUST`

Example key: `Q.US.P.A.M.770.A`
- FREQ=Q (quarterly)
- BORROWERS_CTY=US
- TC_BORROWERS=P (private non-financial)
- TC_LENDERS=A (all sectors)
- VALUATION=M (market value)
- UNIT_TYPE=770 (% of GDP)
- TC_ADJUST=A (adjusted for breaks)

### Response format (confirmed sample)
SDMX-JSON 1.0 format. Structure:
```json
{
  "meta": {...},
  "data": {
    "dataSets": [{
      "series": {
        "0:0:0:0:0:0:0": {
          "attributes": [0,0,0,0],
          "observations": {
            "0": ["144.5", 0, null, 0],
            "1": ["142.5", 0, null, 0],
            ...
          }
        }
      }
    }],
    "structure": {
      "dimensions": {
        "observation": [{
          "id": "TIME_PERIOD",
          "values": [
            {"id": "2024-Q3", "start": "2024-07-01T00:00:00", "end": "2024-09-30T23:59:59"},
            {"id": "2024-Q4", ...}
          ]
        }]
      }
    }
  }
}
```

Observations indexed positionally. TIME_PERIOD values in `structure.dimensions.observation[0].values[i]`. Observation value = `observations[i][0]` (first element; rest are attributes).

### Previous broken URL (for code diff reference)
```
https://stats.bis.org/api/v2/data/{DATAFLOW_ID}/{key}?format=jsondata
```

---

## 3. Concurrency — parallel protocol with Sprint T-AU + ISOLATED WORKTREES

**Sprint AA operates in isolated worktree**: `/home/macro/projects/sonar-wt-sprint-aa`

Sprint T-AU operates in separate worktree: `/home/macro/projects/sonar-wt-sprint-t`

**Critical workflow**:
1. Sprint AA CC starts by `cd /home/macro/projects/sonar-wt-sprint-aa`
2. All file operations happen in this worktree
3. Branch name: `sprint-aa-bis-v2-migration`
4. Pushes to `origin/sprint-aa-bis-v2-migration`
5. Final merge to main via fast-forward post-sprint-close

**File scope Sprint AA (STRICT)**:
- `src/sonar/connectors/bis.py` OR `bis_sdmx.py` MODIFY (URL + header + version map)
- `tests/unit/test_connectors/test_bis.py` OR `test_bis_sdmx.py` MODIFY (unit tests new URL pattern)
- `tests/integration/test_bis_ingestion.py` MODIFY (cassette refresh + canary verification)
- `tests/fixtures/cassettes/bis/` OR similar — NEW cassette files replacing old
- `docs/backlog/calibration-tasks.md` MODIFY (CAL-136 CLOSED + CAL-137 opened)
- `docs/planning/retrospectives/week9-sprint-aa-bis-v2-migration-report.md` NEW

**Sprint T-AU scope** (for awareness, DO NOT TOUCH):
- `src/sonar/connectors/rba.py` NEW (Reserve Bank of Australia)
- `src/sonar/connectors/te.py` APPEND (AU wrapper)
- `src/sonar/indices/monetary/builders.py` APPEND (AU builders)
- `src/sonar/config/*.yaml` (AU entries)
- `src/sonar/pipelines/daily_monetary_indices.py` MODIFY (AU dispatch)

**Zero file overlap confirmed**. BIS connector vs RBA connector. Different domains entirely.

**Worktree sync**:
- Before Commit 1: `cd /home/macro/projects/sonar-wt-sprint-aa && git pull origin main --rebase`

**Push race**: normal `git push origin sprint-aa-bis-v2-migration`. Zero collisions.

**Merge strategy end-of-sprint**:
```bash
cd /home/macro/projects/sonar-engine
git fetch origin
git checkout main
git merge --ff-only sprint-aa-bis-v2-migration
git push origin main
```

---

## 4. Commits

### Commit 1 — Pre-flight + connector code audit

```
chore(bis): pre-flight BIS connector code audit + test baseline

Pre-flight steps:
1. Identify actual BIS connector file:
   find src/sonar/connectors -name "*bis*"

2. Read current implementation fully:
   - URL build function
   - Request headers
   - Response parsing

3. Read current test suite:
   - tests/unit/test_connectors/test_bis*.py
   - tests/integration/test_bis_ingestion.py

4. Inventory current cassettes:
   ls tests/fixtures/cassettes/bis/ OR similar

5. Run baseline tests (document current state):
   uv run pytest tests/unit/test_connectors/ -k bis -v --no-cov 2>&1 | head -30
   uv run pytest tests/integration/test_bis_ingestion.py -v --no-cov 2>&1 | head -40
   # Expected: mocked tests PASS, live canaries FAIL with HTTPStatusError

6. Document findings in commit body:
   - Connector file path
   - URL build logic (how path constructed)
   - Header setting logic
   - Response parser logic
   - Test file paths + cassette paths
   - Baseline test results (pass/fail counts)

No code changes this commit. Audit trail only.
```

### Commit 2 — URL pattern + Accept header migration

```
feat(bis): migrate URL pattern to /api/v2/data/dataflow/BIS/{ID}/{VERSION}/{key}

Breaking API migration: BIS deprecated old URL structure + jsondata format.

Updates to src/sonar/connectors/bis.py (OR bis_sdmx.py):

1. Add DATAFLOW_VERSIONS constant map:
   DATAFLOW_VERSIONS: Final[dict[str, str]] = {
       "WS_TC": "2.0",           # migrated from 1.0 2026-04-21
       "WS_DSR": "1.0",
       "WS_CREDIT_GAP": "1.0",
   }

2. Update URL builder:
   OLD: f"{BASE_URL}/data/{dataflow_id}/{key}"
   NEW: f"{BASE_URL}/data/dataflow/{AGENCY_ID}/{dataflow_id}/{DATAFLOW_VERSIONS[dataflow_id]}/{key}"

   Where AGENCY_ID = "BIS"

3. Update Accept header:
   OLD: format=jsondata querystring OR no header
   NEW: Accept: application/vnd.sdmx.data+json;version=1.0.0
   (remove format=jsondata querystring — rejected with HTTP 406)

4. Add sanity check:
   python -c "from sonar.connectors.bis import BisConnector; print(BisConnector.DATAFLOW_VERSIONS)"

5. Tests (tests/unit/test_connectors/test_bis*.py):
   - Unit: URL built for WS_TC uses version 2.0
   - Unit: URL built for WS_DSR uses version 1.0
   - Unit: URL built for WS_CREDIT_GAP uses version 1.0
   - Unit: Accept header includes ";version=1.0.0"
   - Unit: URL structure matches /api/v2/data/dataflow/BIS/{ID}/{VER}/{key}
   - Unit: No format=jsondata in querystring

Pre-push gate full. Mypy clean.

Unit tests SHOULD pass. Integration live canaries still may fail if
response parser needs update (addressed Commit 3).
```

### Commit 3 — Response parser verification + fix if needed

```
feat(bis): verify SDMX-JSON 1.0 response parser against new endpoint

Current parser may still work (SDMX-JSON 1.0 format stable). Verify:

1. Read existing parser logic:
   - How observations extracted from response
   - How TIME_PERIOD resolved (positional index → actual period)
   - How numeric values parsed

2. Test against real response:
   curl -s -H "Accept: application/vnd.sdmx.data+json;version=1.0.0" \
     'https://stats.bis.org/api/v2/data/dataflow/BIS/WS_TC/2.0/Q.US.P.A.M.770.A?lastNObservations=5' \
     > /tmp/bis_ws_tc_sample.json

   Compare structure to parser expectations:
   - series["0:0:0:0:0:0:0"].observations["0"]=["144.5",...] — positional
   - structure.dimensions.observation[0].values[i].id="2024-Q3" — time period labels
   - observations keyed by positional index referencing values array

3. If parser works unchanged → no code change Commit 3; document verification.
   If parser broken → minimal fix to extract observations from new structure.

4. Unit tests for parser:
   - Parse sample response → assert list of (date, value) tuples
   - Handle missing observations gracefully
   - Handle empty dataSets list

5. @pytest.mark.slow live canary (tests/integration/test_bis_ingestion.py):
   async def test_us_ingest_end_to_end(tmp_path, db_session):
       # ... existing test body
       # Expected: ≥ 1 observation persisted, not empty
       # Expected: BIS table row with country=US, dataflow=WS_TC
       # Expected: obs value in reasonable range for US credit-to-GDP (~140-150%)

Coverage bis connector ≥ 85%.

This commit may be empty (no code change) if parser works unchanged.
Document verification in commit body either way.
```

### Commit 4 — Cassette refresh

```
test(bis): refresh cassettes with new API response format

Old cassettes captured /api/v2/data/WS_TC/... response structure.
New API returns same SDMX-JSON 1.0 structure BUT different URL path.

1. Identify cassette files:
   find tests/ -path "*bis*" -name "*.yaml" -o -path "*bis*" -name "*.json"

2. For each cassette:
   - Delete old cassette
   - Run pytest with --record-mode=all (vcr pattern)
     OR manually re-capture via curl + save to fixture path
   - Verify re-recorded cassette has new URL in metadata + response unchanged structure

3. 7 T1 countries × 3 dataflows = 21 cassette refreshes potentially needed.
   Prioritize US WS_TC + DE WS_DSR + PT WS_CREDIT_GAP (representative across all 3).
   Consider multi-country cassette OR parametrized fixtures.

4. Mocked integration tests:
   uv run pytest tests/integration/test_bis_ingestion.py -v --no-cov -k "not TestLiveCanary"
   Expected: 5/5 PASS with refreshed cassettes

5. Live canary tests:
   uv run pytest tests/integration/test_bis_ingestion.py -v --no-cov -m slow
   Expected: 1/1 PASS (live fetch now works)

Coverage maintained. Full pre-push gate green.
```

### Commit 5 — Re-enable systemd timers + smoke validation

```
chore(ops): re-enable BIS + credit timers post-fix validation

Pre-flight verification:
1. Manual trigger bis-ingestion service:
   sudo systemctl daemon-reload
   sudo systemctl start sonar-daily-bis-ingestion.service

   journalctl -u sonar-daily-bis-ingestion.service -n 50 --no-pager
   # Expected: 7 T1 × 3 dataflows fetched + persisted, exit 0

2. Verify database:
   sqlite3 /home/macro/projects/sonar-engine/data/sonar.db \
     "SELECT COUNT(*), dataflow_id FROM bis_credit_raw GROUP BY dataflow_id;"
   # Expected: rows for WS_TC, WS_DSR, WS_CREDIT_GAP

3. Manual trigger credit-indices:
   sudo systemctl start sonar-daily-credit-indices.service
   # Expected: L1/L2 populated (7 T1 countries), L3/L4 depends on CAL-059/060

4. Re-enable timers:
   sudo systemctl enable sonar-daily-bis-ingestion.timer
   sudo systemctl start sonar-daily-bis-ingestion.timer
   sudo systemctl enable sonar-daily-credit-indices.timer
   sudo systemctl start sonar-daily-credit-indices.timer

   sudo systemctl list-timers 'sonar-*' --no-pager
   # Expected: 9 timers active (bis + credit restored)

5. Document validation results in commit body:
   - Manual trigger exit codes
   - Rows ingested count per dataflow
   - L1/L2 computation outcome
   - Timers status

Commit message placeholder acknowledges ops-level change (no code
changes; this commit is documentation trace of production recovery).

git commit --allow-empty -m "chore(ops): re-enable BIS + credit timers post-v2-migration fix
BIS connector v2 migration validated via manual pipeline trigger.
[validation details...]
Closes CAL-136."
```

### Commit 6 — Retrospective + CAL update

```
docs(planning+backlog): Week 9 Sprint AA BIS v2 migration retrospective

File: docs/planning/retrospectives/week9-sprint-aa-bis-v2-migration-report.md

Structure:
- Summary (duration, commits, scope)
- Discovery timeline (Day 1 probes → URL pattern identified)
- Root cause: BIS API URL path migration + dataflow versioning
- Fix summary:
  - URL: /data/{ID} → /data/dataflow/BIS/{ID}/{VER}
  - Versions: WS_TC 2.0 (migrated), WS_DSR 1.0, WS_CREDIT_GAP 1.0
  - Header: Accept application/vnd.sdmx.data+json;version=1.0.0
- Commits table with SHAs + gate status
- Cassette refresh scope (N files refreshed)
- Live canary outcome: [before: HTTP 500, after: HTTP 200 + rows persisted]
- Coverage delta
- HALT triggers fired / not fired
- Deviations from brief
- Production impact:
  - Outage duration: [~hours from detection Day 1 evening]
  - Credit indices offline 7 T1 countries during window
  - Resolution: [today timestamp]
- Systemd timers restored: 9/9 active
- Concurrency protocol: isolated worktree with Sprint T-AU, zero collision
- Lessons:
  - BIS API migration silent (no deprecation notice observed)
  - Live canaries critical (mocked-only tests missed)
  - Weekly canary schedule = CAL-137 new item
- CAL items:
  - CAL-136 CLOSED (this sprint)
  - CAL-137 OPEN (weekly live canary surveillance via systemd timer)

Update docs/backlog/calibration-tasks.md:
- CAL-136 entry: CLOSED 2026-04-22 with sprint AA commits
- CAL-137 NEW: Weekly BIS live canary surveillance
  Priority: MEDIUM
  Scope: systemd timer sonar-weekly-bis-canary that runs
    pytest tests/integration/ -m slow -k bis weekly, emails on failure
  Rationale: BIS silent API migration (2026-04-21 incident) → prevent
    future undetected outages

Merge command:
  cd /home/macro/projects/sonar-engine
  git checkout main
  git merge --ff-only sprint-aa-bis-v2-migration
  git push origin main
```

---

## 5. HALT triggers (atomic)

0. **Connector file ambiguity** — if both `bis.py` and `bis_sdmx.py` exist OR neither, HALT + surface. Inspect imports in pipelines/daily_bis_ingestion.py to determine canonical.
1. **URL pattern variant response** — if different dataflow requires different URL structure (e.g., BIS may have exceptions for BIS_REL_CAL etc.), document + scope the migration narrowly.
2. **Parser breaks on new response** — if existing SDMX-JSON parser fails on new response despite same format claim, deeper fix required. Time-box parser fix 45 min; if exceeds, HALT.
3. **Cassette refresh burden** — if 21 cassettes (7 countries × 3 dataflows) each need individual re-capture, HALT + pragmatic scope: record 3 representative + delete others, update fixture loader to be more tolerant.
4. **Live canary persistent HTTP error** — if manual pipeline fails despite URL+header correct, investigate BIS rate limit or account requirement. Do NOT proceed with timer re-enablement.
5. **L1/L2 computation fails with new data** — if ingestion succeeds but credit index computation errors, data schema change. Out of scope; HALT + defer to CAL-XXX.
6. **Coverage regression > 3pp** → HALT.
7. **Pre-push gate fails** → fix before push, no `--no-verify`. Full mypy.
8. **Version map incomplete** — if additional dataflows discovered needing version mapping, HALT + add + document.

---

## 6. Acceptance

### Global sprint-end
- [ ] 4-6 commits pushed to branch `sprint-aa-bis-v2-migration`
- [ ] Connector URL pattern migrated to `/api/v2/data/dataflow/BIS/{ID}/{VER}/{key}`
- [ ] Accept header `application/vnd.sdmx.data+json;version=1.0.0`
- [ ] DATAFLOW_VERSIONS map: WS_TC=2.0, WS_DSR=1.0, WS_CREDIT_GAP=1.0
- [ ] Cassettes refreshed (3+ representative OR all 21)
- [ ] Live canary test_us_ingest_end_to_end PASSES
- [ ] Manual bis-ingestion trigger SUCCESS
- [ ] Database populated post-trigger (bis_credit_raw rows > 0)
- [ ] L1 + L2 credit indices computation succeeds (credit-indices manual trigger)
- [ ] systemd timers re-enabled (bis + credit)
- [ ] CAL-136 CLOSED in backlog
- [ ] CAL-137 OPEN (weekly canary surveillance)
- [ ] Retrospective shipped
- [ ] Coverage bis connector ≥ 85% (maintained)
- [ ] Full pre-push gate green every push

---

## 7. Report-back artifact

File: `docs/planning/retrospectives/week9-sprint-aa-bis-v2-migration-report.md`

**Final tmux echo**:
```
SPRINT AA BIS V2 MIGRATION DONE: N commits on branch sprint-aa-bis-v2-migration
URL pattern migrated: /data/{ID} → /data/dataflow/BIS/{ID}/{VER}/{key}
Versions: WS_TC 2.0 | WS_DSR 1.0 | WS_CREDIT_GAP 1.0
Accept header: application/vnd.sdmx.data+json;version=1.0.0
Cassettes refreshed: N files
Live canary: [BEFORE HTTP 500 → AFTER HTTP 200 + N obs persisted]
Production impact: [outage duration] resolved
systemd timers: 9/9 active (bis + credit restored)
HALT triggers: [list or "none"]
CAL-136 CLOSED | CAL-137 OPEN (weekly canary)
Merge: git checkout main && git merge --ff-only sprint-aa-bis-v2-migration
Artifact: docs/planning/retrospectives/week9-sprint-aa-bis-v2-migration-report.md
```

---

## 8. Pre-push gate (mandatory)

```
uv run ruff format --check src/sonar tests
uv run ruff check src/sonar tests
uv run mypy src/sonar
uv run pytest tests/unit/ -x --no-cov
```

Full project mypy. No `--no-verify`.

Live canaries (@pytest.mark.slow) run explicitly during Commit 4+5 validation.

---

## 9. Notes on implementation

### Empirical findings are pre-validated
§2 contains curl-probed URL + Accept + versions. CC does NOT need to re-probe. Trust findings; implement accordingly.

### Cassette refresh pragmatism
21 cassettes = burdensome. If fixture architecture allows:
- Single country/dataflow cassette as representative
- Mock remainder via parametrized fixtures using cassette template
- Document decision in Commit 4 body

If each cassette is independent + all required:
- Use HALT #3 budget (≤45 min cassette refresh)
- Escape hatch: refresh only US, mark others `@pytest.mark.skip(reason="cassette refresh deferred CAL-XXX")` temporarily
- Document decision + followup CAL

### Timer re-enablement safety
Before `systemctl enable --now`, manual-trigger + validate database rows FIRST. Avoid tomorrow 06:00 WEST fire with broken connector.

### Production outage context
BIS connector broke silently between Sprint M (Week 8 Day 3, last validated) and Sprint S-CA discovery (Week 9 Day 1 evening). Live canaries would have caught earlier — CAL-137 tracks weekly canary schedule.

### Isolated worktree workflow
Sprint AA operates entirely in `/home/macro/projects/sonar-wt-sprint-aa`. Branch: `sprint-aa-bis-v2-migration`. Final merge via fast-forward.

### Sprint T-AU parallel
Runs in `sonar-wt-sprint-t`. Different domains entirely. Zero file overlap.

### Systemd ops access
CC has sudo (macro uid 1000). systemctl commands work in CC tmux session. CC should still surface via report-back for transparency.

---

*End of Week 9 Sprint AA BIS v2 migration brief. 4-6 commits. Production restore priority.*
