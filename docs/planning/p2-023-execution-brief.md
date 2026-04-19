# P2-023 Execution Brief — Country Code ISO alpha-3 → alpha-2 Revert

**Target session**: Phase 1 Week 2, Day 1 AM
**Priority**: HIGH (blocker for NSS overlay development Day 1 PM onward)
**Time budget**: 45–75 min
**Authority**: Full autonomy granted via decision authority rule; HALT only on triggers in §6
**Commit count**: 1 (strict per regra #2 Week 1+; split only if HALT trigger fires)
**Base commit**: `979369b` (main HEAD at Week 1 close)

---

## 1. Context and rationale

`CLAUDE.md` §3 establishes ISO 3166-1 alpha-2 as canonical country code
representation across the SONAR codebase. `docs/data_sources/country_tiers.yaml`
(committed Phase 0 Bloco D1) already uses alpha-2 literals
(`iso_code: US`, `iso_code: DE`, `iso_code: PT`).

During Phase 1 Week 1 Day 2, the `Observation` schema was introduced using
alpha-3 (`USA`, `DEU`, `PRT`). This drift was deferred as P2-023 with HIGH
priority under the constraint that **NSS overlay development (Week 2 Day 1 PM
onward) must not persist alpha-3 values into `yield_curves_*` tables**.

Revert before any NSS code touches the database.

---

## 2. Canonical invariants — do not modify

- `docs/data_sources/country_tiers.yaml` (already alpha-2; source of truth)
- `.pre-commit-config.yaml` (hook baseline)
- `alembic/env.py` (session setup)
- `CLAUDE.md` (governance; already correct)
- ADR documents under `docs/adr/` (historical record; no retroactive rewrites)

---

## 3. Discovery phase (execute before editing)

```bash
cd /home/macro/projects/sonar-engine
mkdir -p /tmp/p2-023

# Code references to alpha-3
rg -in 'alpha.?3|iso_alpha3|ISO_ALPHA3' src/ tests/ --type py \
  > /tmp/p2-023/scope-code.txt

# Migrations
rg -in 'alpha.?3|iso_alpha3' alembic/versions/ \
  > /tmp/p2-023/scope-migrations.txt

# Docs (report-only; do not modify in this commit unless Observation-specific)
rg -in 'alpha.?3|iso_alpha3' docs/ \
  > /tmp/p2-023/scope-docs.txt

# Alpha-3 literals that should have been alpha-2
rg -wn 'USA|DEU|PRT|GBR|FRA|ITA|ESP|JPN|CHN|CAN|AUS|NZL|CHE|NLD|BEL|SWE' \
  src/ tests/ \
  > /tmp/p2-023/scope-literals.txt

wc -l /tmp/p2-023/*.txt
cat /tmp/p2-023/scope-code.txt
```

Inspect output. Build modification list. Confirm no HALT trigger (§6) before
proceeding.

---

## 4. Change scope

### 4.1 In-scope

| File class | Action |
|---|---|
| `src/sonar/db/models.py` (or wherever `Observation` lives) | Change `country_code` column type from `String(3)` to `String(2)`; update any `CheckConstraint` for length; update docstring |
| Pydantic schemas for `Observation` (if separate from ORM) | Update `Field(..., min_length=2, max_length=2)` + regex `^[A-Z]{2}$` if enforced |
| Seed / fixture data | Replace `USA` → `US`, `DEU` → `DE`, `PRT` → `PT`, etc. |
| Tests instantiating `Observation` with alpha-3 literals | Update literals to alpha-2 |
| Alembic migration referencing `country_code` length | See §5 decision tree |
| Code docstrings/comments referencing alpha-3 | Update to alpha-2 |

### 4.2 Out-of-scope (do not touch in this commit)

- FRED connector code (US yield curve data is single-country at API level; no country field to revert)
- Wiki pages under `wiki/` (defer to next wiki sync task)
- `docs/data_sources/*.md` — alpha-3 references there may be illustrative (country names full-text); report in §10 but do not modify
- Documentation under `docs/specs/`, `docs/reference/`, `docs/adr/` (historical/spec; out of this PR)

---

## 5. Migration decision tree

Inspect `alembic/versions/001_*.py` for `country_code` column definition:

- **Case A** — Migration 001 has `country_code = Column(String(3))` AND local
  dev SQLite DB was seeded with data during Week 1.
  **HALT** (§6 trigger #1). Destructive migration to dev DB is a scope decision
  requiring chat authorization.

- **Case B** — Migration 001 has `String(3)` but DB is empty or trivially
  re-creatable from migration replay. Modify migration 001 in-place (acceptable
  because Week 1 migration 001 has not reached any shared/prod state; dev reset
  is cheap). Document the in-place amendment in commit body.

- **Case C** — Migration 001 uses `String(3)` only in a non-authoritative
  sibling or metadata table. Modify in-place; no new migration needed.

**Default**: Case B. If Case A surfaces → HALT.

---

## 6. HALT triggers

Pause execution and report to chat **without pushing** if any of these fire:

1. Case A migration surface (destructive migration to dev DB with committed data)
2. Discovery reveals alpha-3 references in more than 15 files (blast radius larger than P2-023 entry anticipates; may require scope split)
3. Pre-commit hook failure not covered by existing `.pre-commit-config.yaml` (regra #4 Week 1+: no force-fix on unanticipated hook fails)
4. Coverage drop exceeding 2pp from 96.59% Week 1 baseline
5. mypy surfaces type errors in modules not touched by this change (indicates coupled refactor out-of-scope)
6. Any `rm -rf`, `DROP TABLE`, or destructive git command being required to complete the fix

Report includes: grep outputs, file list, proposed sub-plan. Wait for chat decision before resuming.

---

## 7. Execution sequence

1. Run discovery greps (§3); inspect outputs.
2. Build modification list; confirm no HALT trigger.
3. Edit files; preserve formatting, import order, comments.
4. `uv run pytest tests/ -x` — all green.
5. `uv run pytest --cov=src/sonar --cov-report=term-missing tests/` — coverage ≥ 94.5%.
6. `pre-commit run --all-files` — all hooks pass.
7. `git add -p` (review hunks); `git status` (sanity).
8. Commit with message per §8.
9. `git push origin main`.
10. Verify: `gh api /repos/hugocondesa-debug/sonar-engine/commits/main --jq .sha` matches local HEAD.

---

## 8. Commit message format

```
refactor(db): revert country_code to ISO alpha-2 (P2-023)

Align Observation schema with CLAUDE.md §3 canonical ISO 3166-1 alpha-2
representation. country_tiers.yaml is authoritative source; Observation
model drifted to alpha-3 during Week 1 Day 2 schema design. Revert is
pre-requisite to NSS overlay development (Week 2 Day 1 PM) — prevents
alpha-3 values from being persisted into yield_curves_* tables.

Scope:
- src/sonar/db/models.py: country_code String(3) → String(2)
- [migration 001 in-place update | migration 002 added]  ← pick one
- N test files updated to 'US', 'DE', 'PT' literals
- docstrings aligned with alpha-2 canon

Acceptance:
- rg -i 'alpha.?3|iso_alpha3' src/ tests/ returns empty
- pytest exits 0
- coverage: 96.59% → XX.XX% (delta ≤ 2pp)

Closes P2-023.
```

---

## 9. Acceptance checklist (self-check before `git push`)

- [ ] `rg -in 'alpha.?3|iso_alpha3|ISO_ALPHA3' src/ tests/` returns empty
- [ ] `rg -wn 'USA|DEU|PRT|GBR|FRA' src/ tests/` returns empty (or only explicit negative-assertion tests, if any)
- [ ] `uv run pytest tests/ -x` exits 0
- [ ] Coverage ≥ 94.5%
- [ ] `pre-commit run --all-files` exits 0
- [ ] `git log --oneline -1` shows single commit matching §8 format
- [ ] Local HEAD matches remote after push
- [ ] P2-023 entry in `docs/backlog/phase2-items.md` — **do not close in this commit**; chat will close after verification and update SESSION_CONTEXT §7

---

## 10. Report-back (paste to chat after push)

1. Commit SHA + `git log --oneline -1` output
2. Post-fix grep outputs (should be empty)
3. Coverage delta (before: 96.59% / after: XX.XX%)
4. Timer actual vs 45–75 min budget
5. Migration path taken (Case B in-place, Case C non-authoritative, or Case A HALT resolution)
6. Any out-of-scope items surfaced during discovery (chat triages as new P2-XXX or CAL-XXX)

---

*End of brief. Proceed.*
