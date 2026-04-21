# Week 8 Sprint O — CAL-128 GB/UK Canonical Rename (Carve-Out Scope)

**Target**: Resolve ISO compliance debt by renaming "UK" → "GB" across configs, connectors, pipelines, tests. **Carve-out from builders.py** (Sprint L domain; post-sprint chore commit does final rename sweep).
**Priority**: MEDIUM (ISO 3166-1 alpha-2 compliance; technical debt closure)
**Budget**: 1.5-2h CC autonomous
**Commits**: ~5-7
**Base**: branch `sprint-o-gb-uk-rename` (isolated worktree `/home/macro/projects/sonar-wt-sprint-o`)
**Concurrency**: Parallel to Sprint L BoJ connector in worktree `sonar-wt-sprint-l`. See §3.

---

## 1. Scope

In:
- Rename "UK" → "GB" canonical ISO alpha-2 in:
  - `docs/data_sources/country_tiers.yaml` (iso_code key)
  - `src/sonar/config/r_star_values.yaml` (country dict key)
  - `src/sonar/config/bc_targets.yaml` (country dict key)
  - `src/sonar/connectors/te.py` country mappings dicts (`"UK": "united kingdom"` → `"GB": "united kingdom"`)
  - `src/sonar/connectors/te.py` TE_10Y_SYMBOLS (`"UK": "GUKG10:IND"` → `"GB": "GUKG10:IND"`)
  - `src/sonar/connectors/te.py` UK Bank Rate constants (UK_BANK_RATE_* → GB_BANK_RATE_*)
  - `src/sonar/connectors/boe_database.py` (Sprint I shipped) — rename internal UK references to GB where applicable
  - `src/sonar/pipelines/daily_monetary_indices.py` MONETARY_SUPPORTED_COUNTRIES (`"UK"` → `"GB"`)
  - `src/sonar/pipelines/daily_monetary_indices.py` country branches and dispatch logic
  - Test files references in `tests/unit/` + `tests/integration/` (UK → GB in country_code strings, fixture dict keys, etc.)
  - Documentation: `docs/ops/systemd-deployment.md`, relevant retrospectives (mark as historical — keep original)
- Backward compat alias: maintain "UK" as deprecated alias in critical lookup points (e.g. TE_10Y_SYMBOLS) with deprecation log — soft migration path
- Document canonical decision in `docs/adr/ADR-0007-iso-country-codes.md` NEW
- CAL-128 formalization + closure in `docs/backlog/calibration-tasks.md`
- Tests updated to expect "GB" everywhere + 1-2 tests verify backward compat "UK" alias still works
- Retrospective
- **Post-merge chore commit documented** for Sprint L's `builders.py` remaining UK references

Out:
- **`src/sonar/indices/monetary/builders.py`** — **CARVE-OUT**: Sprint L owns this file Day 4. Sprint O does NOT touch.
- All Sprint L new files (`boj.py`, new JP builders)
- UK M1 cascade logic (shipped Sprint I-patch; rename touches constants only, not logic)
- L0 FRED UK series IDs (FRED uses country codes like `IRLTLT01GBM156N` — already uses GB; no change needed)
- Historical retros that reference "UK" — preserved as archival; not rewritten
- Test fixture JSONs that reference "UK" as literal data content — preserved (data authenticity)
- BIS country codes (BIS uses full names like "United Kingdom" — not affected)

---

## 2. Spec reference

Authoritative-ish (rename is spec-driven compliance work):
- `docs/adr/ADR-0005-country-tiers-classification.md` — **canonical ISO 3166-1 alpha-2 mandate**
- `docs/planning/retrospectives/week8-sprint-i-boe-connector-report.md` §Deviations — CAL-128 origin
- `SESSION_CONTEXT.md` §Country tiers — "iso_code: US/DE/PT" convention
- ISO 3166-1 alpha-2 standard: UK is assigned to "GB" (Great Britain)

**Pre-flight requirement**: Commit 1 CC:
1. Sweep entire codebase for "UK" references:
   ```bash
   cd /home/macro/projects/sonar-wt-sprint-o
   rg -l '\bUK\b|"UK"' src/ tests/ docs/
   ```
2. Categorize matches:
   - **In-scope** (rename): config YAML keys, connector mappings, pipeline country lists, test country_code strings
   - **Out-of-scope** (preserve): Sprint L's builders.py (carve-out), historical retros (archival), FRED series names (already GB), BIS full names
3. Document scope in Commit 1 body
4. Verify no Sprint L in-progress work visible (different worktrees, different branches — should be invisible)
5. Read current iso_code conventions in `country_tiers.yaml`

Document findings in Commit 1 body.

Existing assets:
- Per SESSION_CONTEXT: "country_tiers.yaml usa iso_code: US/DE/PT" (alpha-2) — UK should be GB
- All other T1 countries already use canonical ISO alpha-2 (US, DE, PT, IT, ES, FR, NL)
- Sprint I Week 8 Day 1 shipped with "UK" as internal convention (inconsistent with rest)

---

## 3. Concurrency — parallel protocol with Sprint L + ISOLATED WORKTREES + CARVE-OUT

**Sprint O operates in isolated worktree**: `/home/macro/projects/sonar-wt-sprint-o`

Sprint L operates in separate worktree: `/home/macro/projects/sonar-wt-sprint-l`

**Critical workflow**:
1. Sprint O CC starts by `cd /home/macro/projects/sonar-wt-sprint-o`
2. All file operations happen in this worktree
3. Branch name: `sprint-o-gb-uk-rename`
4. Pushes to `origin/sprint-o-gb-uk-rename`
5. Final merge to main via fast-forward post-sprint-close

**File scope Sprint O (MUST OBEY CARVE-OUT)**:
- `docs/data_sources/country_tiers.yaml` MODIFY
- `src/sonar/config/r_star_values.yaml` MODIFY
- `src/sonar/config/bc_targets.yaml` MODIFY
- `src/sonar/connectors/te.py` MODIFY (all UK mappings → GB)
- `src/sonar/connectors/boe_database.py` MODIFY (internal refs)
- `src/sonar/pipelines/daily_monetary_indices.py` MODIFY (country dispatch, MONETARY_SUPPORTED_COUNTRIES)
- `tests/unit/test_connectors/test_te.py` MODIFY (UK test references → GB)
- `tests/unit/test_connectors/test_boe_database.py` MODIFY
- `tests/unit/test_indices/monetary/test_config_loaders.py` MODIFY
- `tests/unit/test_pipelines/test_daily_monetary_indices.py` MODIFY
- `tests/integration/test_daily_monetary_uk_te_cascade.py` RENAME or update references → GB (keep filename OR rename to `_gb_`; decide Commit 1)
- `tests/fixtures/cassettes/te/uk_*.json` RENAME → `tests/fixtures/cassettes/te/gb_*.json` if fixture filenames encode country
- `docs/adr/ADR-0007-iso-country-codes.md` NEW
- `docs/backlog/calibration-tasks.md` — CAL-128 formalization + closure
- `docs/planning/retrospectives/week8-sprint-o-gb-uk-rename-report.md` NEW

**CARVE-OUT (DO NOT TOUCH)**:
- **`src/sonar/indices/monetary/builders.py`** — Sprint L adds JP builder here + touches UK builder cascade. Leave UK references verbatim. Post-both-merges chore commit sweeps this file separately.

**Sprint L scope** (for awareness, carve-out respected):
- Sprint L adds JP builder + JP connector
- Sprint L does NOT rename UK references anywhere
- New JP additions use current conventions (pre-Sprint-O state)
- Post-both-merges chore commit consolidates all UK → GB including Sprint L's

**Worktree sync**:
- Before Commit 1: `cd /home/macro/projects/sonar-wt-sprint-o && git pull origin main --rebase`

**Push race**: normal `git push origin sprint-o-gb-uk-rename`. Zero collisions expected (different files entirely excluding carve-out).

**Merge strategy end-of-sprint**:
```bash
cd /home/macro/projects/sonar-engine
git fetch origin
git checkout main
git merge --ff-only sprint-o-gb-uk-rename
git push origin main
```
Fast-forward expected.

**Post-both-merges chore commit (Sprint L + Sprint O both merged)**:
```bash
cd /home/macro/projects/sonar-engine
git checkout main
# Final builders.py sweep
sed -i 's/"UK":/"GB":/g; s/UK_BANK_RATE/GB_BANK_RATE/g; ... ' src/sonar/indices/monetary/builders.py
# Update tests
git add -A
git commit -m "chore(rename): finalize UK → GB sweep on builders.py (CAL-128 completion)"
git push origin main
```

---

## 4. Commits

### Commit 1 — Pre-flight + ADR-0007 design decisions

```
docs(adr): ADR-0007 ISO country codes canonical + rename scope

Pre-flight: sweep codebase for UK references + categorize scope.

Document in commit body:
- rg -l '\bUK\b|"UK"' src/ tests/ docs/
- In-scope files (Sprint O touches): [list]
- Out-of-scope (carve-out builders.py; historical retros; FRED already GB): [list]
- Test file rename strategy (filename encoding → GB OR keep UK for discoverability)

Create docs/adr/ADR-0007-iso-country-codes.md:

# ADR-0007 ISO 3166-1 alpha-2 canonical country codes

## Status
Accepted — 2026-04-21 Sprint O

## Context
Sprint I Week 8 shipped BoE connector + UK monetary indices using
internal convention "UK". All other T1 countries (US, DE, PT, IT, ES,
FR, NL) use canonical ISO 3166-1 alpha-2 codes. UK's canonical ISO
alpha-2 is "GB" (Great Britain).

Inconsistency flagged in Sprint I retro §Deviations (CAL-128):
- country_tiers.yaml: US, DE, PT, IT, ES, FR, NL (consistent)
- SONAR internal: "UK" (inconsistent)
- FRED series: IRLTLT01GBM156N (already GB)

## Decision
1. Canonical: ISO 3166-1 alpha-2 — "GB" for United Kingdom
2. Migration path: rename "UK" → "GB" in all config YAML keys, connector mappings, pipeline country lists, test country_code references
3. Backward compat: maintain "UK" alias in 1-2 critical lookup points (e.g. TE_10Y_SYMBOLS) with deprecation log for 1 release
4. Exceptions: historical retrospectives preserved as archival (do not rewrite history); FRED series names already use GB natively (no change needed); BIS country names unaffected (full name, not alpha-2)

## Consequences
- Positive: ISO compliance + internal consistency
- Positive: easier automated data source integration (APIs expect alpha-2)
- Negative: 1-time rename sweep across codebase
- Negative: post-sprint chore commit for Sprint L's builders.py carve-out

## Alternatives considered
- Keep "UK": rejected — inconsistent with rest of codebase + ISO non-compliance
- Rename all to ISO 3166-1 alpha-3 ("GBR"): rejected — all other countries use alpha-2; compatibility
- Deprecation period only (no rename): rejected — kicks debt indefinitely

## References
- ADR-0005 (country tiers classification)
- Sprint I retro (CAL-128 origin)
- ISO 3166-1 alpha-2 standard

Also document CAL-128 formalization:

Append to docs/backlog/calibration-tasks.md:

### CAL-128 — GB vs UK canonical country code rename
- **Priority**: MEDIUM
- **Trigger**: Sprint I retro §Deviations (2026-04-21)
- **Context**: SONAR internal code uses "UK"; canonical ISO 3166-1
  alpha-2 is "GB". Inconsistent with US/DE/PT/IT/ES/FR/NL all using
  canonical alpha-2. Affects TE mappings, config YAML, connector
  constants, pipeline dispatch.
- **Scope**:
  - country_tiers.yaml iso_code: UK → GB
  - r_star_values.yaml + bc_targets.yaml keys
  - TE_COUNTRY_INDICATOR_MAP + TE_10Y_SYMBOLS
  - UK_BANK_RATE_* constants → GB_BANK_RATE_*
  - daily_monetary_indices country dispatch
  - Tests + fixture references
  - EXCLUDED (Sprint L domain): builders.py UK builder references → post-sprint chore commit
  - EXCLUDED: historical retrospectives (archival)
- **Implementation**: Sprint O Week 8 Day 4 (isolated worktree)
- **Status**: In progress Sprint O → CLOSED with final chore commit
  post Sprint L merge

No tests (documentation + ADR).
```

### Commit 2 — Config YAML rename

```
feat(config): rename UK → GB in country_tiers + r_star_values + bc_targets

Modify docs/data_sources/country_tiers.yaml:
  # Before: UK entry (or "iso_code: UK" if present — verify)
  # After:  iso_code: GB
  # Preserve tier, monetary enabled, description updated:
  # "description: United Kingdom (GB per ISO 3166-1 alpha-2) — Tier 1"

Modify src/sonar/config/r_star_values.yaml:
  # Before: UK: {value: 0.005, proxy: true, ...}
  # After:  GB: {value: 0.005, proxy: true, ...}
  # Preserve value + metadata

Modify src/sonar/config/bc_targets.yaml:
  # Before: UK: {target: 0.02, ...}
  # After:  GB: {target: 0.02, ...}

Tests (tests/unit/test_indices/monetary/test_config_loaders.py):
- Unit: resolve_r_star("GB") returns (0.005, True) (unchanged behavior, renamed key)
- Unit: resolve_r_star("UK") — if backward compat alias shipped, returns same OR raises KeyError; decide Commit 1
- Unit: bc_targets GB 2% (was UK 2%)
- Unit: country_tiers_parser GB in T1 list

Coverage maintained.
```

### Commit 3 — TE connector rename + backward compat alias

```
feat(connectors): TE UK → GB canonical + backward compat alias

Modify src/sonar/connectors/te.py:

TE_COUNTRY_INDICATOR_MAP:
  # Before: "UK": "united kingdom", ...
  # After:  "GB": "united kingdom", ...
  # Backward compat: "UK": "united kingdom"  # deprecated alias
  # Log deprecation warning on lookup (structlog warning)

TE_10Y_SYMBOLS:
  # Before: "UK": "GUKG10:IND"
  # After:  "GB": "GUKG10:IND"
  # Backward compat alias "UK": "GUKG10:IND" with deprecation log

UK_BANK_RATE_EXPECTED_SYMBOL → GB_BANK_RATE_EXPECTED_SYMBOL
UK_BANK_RATE_INDICATOR → GB_BANK_RATE_INDICATOR (if distinct)
fetch_uk_bank_rate → fetch_gb_bank_rate (primary) + fetch_uk_bank_rate (deprecated alias calling fetch_gb_bank_rate with warning)

Tests (tests/unit/test_connectors/test_te.py):
- Unit: TE_COUNTRY_INDICATOR_MAP["GB"] returns "united kingdom"
- Unit: TE_COUNTRY_INDICATOR_MAP["UK"] returns "united kingdom" + logs deprecation warning (backward compat)
- Unit: fetch_gb_bank_rate = fetch_uk_bank_rate behavior (renamed function)
- Unit: fetch_uk_bank_rate logs deprecation warning when called

Coverage te.py maintained.
```

### Commit 4 — BoE connector + pipeline UK → GB

```
feat(connectors): boe_database + daily_monetary_indices UK → GB

Modify src/sonar/connectors/boe_database.py:
- Internal references UK → GB where present (docstrings, logs, error messages)
- Class name BoEConnector preserved (Bank of England is proper noun)
- Constants BOE_UK_BANK_RATE etc. — decide rename OR preserve (BoE is the source name; UK is the context; rename to GB_ prefix)

Modify src/sonar/pipelines/daily_monetary_indices.py:
- MONETARY_SUPPORTED_COUNTRIES: ("US", "EA", "UK", ...) → ("US", "EA", "GB", ...)
- Country dispatch: if country == "UK": → if country == "GB":
- Backward compat: accept --country UK + emit deprecation warning + route to GB logic

Tests (tests/unit/test_pipelines/test_daily_monetary_indices.py):
- Unit: --country GB dispatches correctly
- Unit: --country UK dispatches to GB path + emits deprecation warning
- Unit: MONETARY_SUPPORTED_COUNTRIES contains "GB" (and "UK" if backward compat)

Coverage maintained.
```

### Commit 5 — Test suite update

```
test: update UK → GB references across test suite

Sweep tests/ for UK literal country_code strings + fixture keys:
- tests/unit/test_connectors/test_te.py: UK → GB in test data
- tests/unit/test_connectors/test_boe_database.py: UK → GB
- tests/unit/test_indices/monetary/test_builders.py:
  WARNING — touches builders.py tests but not builders.py source
  (carve-out preserves source; can update test data to GB for tests
  that mock the builder inputs; coordinate carefully)
- tests/integration/test_daily_monetary_uk_te_cascade.py: rename
  file → test_daily_monetary_gb_te_cascade.py OR keep filename +
  rename internal country_code references → GB (decide Commit 1)
- tests/fixtures/cassettes/te/uk_bank_rate_*.json: rename →
  gb_bank_rate_*.json (filenames); update test paths

Backward compat tests:
- Verify "UK" string fallback still works in critical lookup points
  (TE_10Y_SYMBOLS, fetch_uk_bank_rate deprecated alias)

Coverage maintained.
```

### Commit 6 — Retrospective + post-merge chore commit documentation

```
docs(planning): Week 8 Sprint O GB/UK rename retrospective

File: docs/planning/retrospectives/week8-sprint-o-gb-uk-rename-report.md

Structure per prior retrospectives:
- Summary (duration, commits, scope)
- Commits table with SHAs + gate status
- ADR shipped: ADR-0007
- Scope executed:
  - Config YAML: country_tiers + r_star_values + bc_targets
  - Connectors: te.py + boe_database.py
  - Pipelines: daily_monetary_indices.py
  - Tests: test suite sweep
  - CAL-128 formalized + set status to "partially closed — final
    chore commit pending Sprint L merge"
- Carve-out compliance:
  - builders.py NOT touched ✓
  - Post-merge chore commit documented in retro §PostMerge +
    as CAL-128 closure action
- Backward compat analysis:
  - "UK" aliases preserved in 2 critical points: TE_10Y_SYMBOLS +
    fetch_uk_bank_rate
  - Deprecation logs emitted on access
  - Removal planned for 2 releases ahead (when?)
- HALT triggers fired / not fired
- Deviations from brief
- Isolated worktree: zero collision incidents
- Merge strategy: branch sprint-o-gb-uk-rename → main fast-forward

## Post-merge chore commit (Sprint O + Sprint L BOTH merged)

Operator action post both merges:

```bash
cd /home/macro/projects/sonar-engine
git checkout main
git pull origin main

# Sweep builders.py (Sprint L may have added JP; sweep covers UK existing + JP new + any Sprint L additions with UK convention)
python -c "
import re
from pathlib import Path
f = Path('src/sonar/indices/monetary/builders.py')
content = f.read_text()
content = re.sub(r'\"UK\":', '\"GB\":', content)
content = re.sub(r'UK_BANK_RATE_(BOE_FALLBACK|TE_PRIMARY|TE_UNAVAILABLE|BOE_NATIVE|FRED_FALLBACK_STALE)', r'GB_BANK_RATE_\\1', content)
content = re.sub(r'build_m1_uk_inputs', 'build_m1_gb_inputs', content)
# Add backward compat function alias in builders.py:
# def build_m1_uk_inputs(*args, **kwargs):
#     logger.warning('build_m1_uk_inputs is deprecated; use build_m1_gb_inputs')
#     return build_m1_gb_inputs(*args, **kwargs)
f.write_text(content)
"

# Verify tests still pass after sweep
cd /home/macro/projects/sonar-engine
uv run pytest tests/unit/test_indices/monetary/test_builders.py -x --no-cov

# Commit
git add -A
git commit -m "chore(rename): finalize UK → GB sweep on builders.py (CAL-128 completion)

Post-merge cleanup applied via automated sed/re.sub sweep on builders.py.
Sprint O and Sprint L both merged; this commit closes the carve-out gap
on the single file Sprint O was not permitted to touch during paralelo
execution.

Backward compat: build_m1_uk_inputs preserved as deprecated alias.

Closes CAL-128."

git push origin main
```

Status in backlog post-chore: CAL-128 CLOSED.

- Post Week 8 cumulative:
  - ISO compliance complete T1 countries
  - 1 CAL closure
  - No new CAL items
  - M2 T1 9 countries (post Sprint L JP merge)
```

### Commit 7 (optional) — Deprecation log plan

```
docs(ops): deprecation timeline for UK aliases

Create docs/ops/deprecation-timeline.md:
- CAL-128 UK → GB rename shipped Week 8 Day 4
- "UK" aliases preserved 2 releases for backward compat
- Removal planned Week 10 Day 1 (~2 weeks sustained production)
- Consumers notified via structlog deprecation warnings
- Remove alias points:
  - TE_COUNTRY_INDICATOR_MAP["UK"]
  - TE_10Y_SYMBOLS["UK"]
  - fetch_uk_bank_rate wrapper
  - build_m1_uk_inputs wrapper (post Sprint L chore)

No tests.
```

---

## 5. HALT triggers (atomic)

0. **Sweep reveals unexpected file touches** — if pre-flight finds UK in files not in brief scope (Commit 1), add to scope OR defer to separate sprint. Don't expand silently.
1. **Sprint L in-flight changes visible** — isolated worktrees should prevent this. If worktree sync pulls Sprint L commits, HALT + reconcile (shouldn't happen with different branches).
2. **Test fixture filename carries country code** — decision Commit 1: rename files OR keep with internal country_code update. Document chosen approach.
3. **BoE connector class name rename** — "BoE" is Bank of England (proper noun, not country code). Do NOT rename class; internal refs to "UK" context yes.
4. **Backward compat alias risk** — aliases add complexity. If >2 alias points needed, reconsider deprecation timeline or full-break decision. Document in retro.
5. **Integration test fails post-rename** — indicates missed rename somewhere. HALT + grep + fix.
6. **Coverage regression > 3pp** → HALT.
7. **Pre-push gate fails** → fix before push, no `--no-verify`. Full mypy.
8. **Concurrent Sprint L touches any file in Sprint O scope** (shouldn't per §3 carve-out) → reconcile via rebase.

---

## 6. Acceptance

### Global sprint-end
- [ ] 5-7 commits pushed to branch `sprint-o-gb-uk-rename`
- [ ] ADR-0007 shipped
- [ ] CAL-128 formalized in backlog
- [ ] Config YAML files renamed (country_tiers + r_star_values + bc_targets)
- [ ] `te.py` UK → GB canonical + backward compat alias
- [ ] `boe_database.py` internal refs UK → GB
- [ ] `daily_monetary_indices.py` MONETARY_SUPPORTED_COUNTRIES + country dispatch
- [ ] Test suite updated (UK → GB in country_code strings + fixture filenames)
- [ ] Backward compat aliases working (deprecation warnings logged)
- [ ] **Carve-out respected**: `src/sonar/indices/monetary/builders.py` NOT modified
- [ ] Retrospective documents post-merge chore commit plan
- [ ] No `--no-verify`
- [ ] Full pre-push gate green every push

---

## 7. Report-back artifact

File: `docs/planning/retrospectives/week8-sprint-o-gb-uk-rename-report.md`

**Final tmux echo**:
```
SPRINT O GB/UK RENAME DONE: N commits on branch sprint-o-gb-uk-rename
ISO compliance: 6 files renamed (YAML configs + te.py + boe_database.py + pipeline + tests)
ADR-0007 shipped; CAL-128 partially closed (final chore commit on builders.py post-Sprint-L merge)
Backward compat: UK aliases preserved with deprecation warnings
Carve-out respected: builders.py untouched
HALT triggers: [list or "none"]
Merge: git checkout main && git merge --ff-only sprint-o-gb-uk-rename
Post-both-merges: chore commit on builders.py per retro §PostMerge section
Artifact: docs/planning/retrospectives/week8-sprint-o-gb-uk-rename-report.md
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

---

## 9. Notes on implementation

### ISO 3166-1 alpha-2 compliance
GB is the canonical code for United Kingdom per ISO standard. UK is not formally assigned (ccTLD .uk is a separate convention). Brief honors this standard for consistency with other T1 countries.

### Backward compat preserves operator workflows
`--country UK` continues working with deprecation warning. Prevents user-facing breakage while signaling migration path.

### Carve-out is structural discipline
Sprint L touches builders.py for JP additions. Sprint O avoids builders.py entirely. Post-merge chore commit consolidates rename. Isolated worktrees make this enforceable.

### Historical retrospectives preserved
Retros from Sprint I + Sprint I-patch reference "UK" — preserved as archival record. Future retros use "GB".

### Deprecation timeline documented
Aliases live 2 releases (~2 weeks sustained production). Week 10 Day 1 removal planned. Commits referencing alias removal include CAL-128 full closure.

### Isolated worktree workflow
Sprint O operates entirely in `/home/macro/projects/sonar-wt-sprint-o`. Branch: `sprint-o-gb-uk-rename`. Final merge via fast-forward.

### Sprint L parallel
Runs in `sonar-wt-sprint-l`. Adds JP + does NOT rename UK. Post-both-merges chore commit does final builders.py sweep covering Sprint L additions + pre-existing UK references.

---

*End of Week 8 Sprint O GB/UK rename brief. 5-7 commits. ISO compliance via carve-out pattern.*
