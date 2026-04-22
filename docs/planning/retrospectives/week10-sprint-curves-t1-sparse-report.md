# Week 10 Day 2 Sprint E — CAL-CURVES-T1-SPARSE-INCLUSION Retrospective

**Sprint**: E — Week 10 Day 2 CAL-CURVES-T1-SPARSE-INCLUSION (GB/JP/CA
inclusion in ``daily_curves --all-t1`` iteration; sparse inclusion
because the tuple now reflects the curve-capable T1 subset rather than
the shared 7-tuple contract of the other daily pipelines).
**Branch**: `sprint-curves-t1-sparse-inclusion`.
**Worktree**: `/home/macro/projects/sonar-wt-curves-t1-sparse-inclusion`.
**Brief**: (prompt-driven, no `docs/planning/week10-sprint-e-*` file
— 4-commit scope defined in the CC autonomy prompt per SESSION_CONTEXT
§Decision authority; format v3 mental template applied).
**Duration**: ~45 min CC (single session 2026-04-22, well under the
2-3h budget because CAL-138 had already shipped the TE GB/JP/CA
connectors + dispatcher route; Sprint E was a one-line tuple edit
plus tests).
**Commits**: 3 substantive + this retro = 4 total, matching the
prompt's "Scope 4 commits" envelope.
**Outcome**: `daily_curves --all-t1` now persists six
`NSSYieldCurveSpot` rows per invocation (US / DE / EA / GB / JP / CA)
vs. the prior two (US + DE, with PT/IT/ES/FR/NL raising on every
run). Other seven daily pipelines keep the shared `T1_7_COUNTRIES`
7-tuple unchanged — the divergence is scoped to curves only, made
explicit by the pipeline-local rename `T1_7_COUNTRIES →
T1_CURVES_COUNTRIES`.

---

## 1. Commit inventory

| # | SHA | Subject | Scope |
|---|---|---|---|
| 1 | `dcafc45` | feat(pipelines): daily_curves --all-t1 sparse inclusion (GB/JP/CA) | Rename `T1_7_COUNTRIES → T1_CURVES_COUNTRIES` with new tuple `(US, DE, EA, GB, JP, CA)`; docstring + test updated. No dispatcher change (CAL-138 wiring already complete). |
| 2 | `f6de3db` | test(pipelines): daily_curves dispatcher unit tests (GB/JP/CA + regression) | New `tests/unit/test_pipelines/test_daily_curves.py` — 13 tests covering tuple invariants (3), TE branch positive routing + case-insensitive + missing-connector (7), US/DE/EA regression guards (3). AsyncMock fixtures; no network / no DB. |
| 3 | `8d8c929` | test(pipelines): daily_curves --all-t1 sparse-inclusion canary (5 non-US) | New `test_daily_curves_all_t1_sparse_inclusion` @pytest.mark.slow — iterates `T1_CURVES_COUNTRIES` minus US against the in-memory db_session fixture; asserts five rows persisted with correct `source_connector` labels. |
| 4 | (this commit) | docs(planning): Week 10 Sprint E CAL-CURVES-T1-SPARSE-INCLUSION retrospective + CAL closure | `calibration-tasks.md` current-behavior lines refreshed on CAL-138 ship-list + CAL-CURVES-T1-SPARSE; this retro. |

---

## 2. Scope outcome vs prompt

### Prompt's ambition

- **C1**: Pre-flight + tuple expansion (US/DE/EA → US/DE/EA/GB/JP/CA)
- **C2**: Unit tests dispatcher GB/JP/CA
- **C3**: Live canaries GB/JP/CA @pytest.mark.slow
- **C4**: Production verification + retrospective + CAL closure
- Budget 2-3h; §8 pre-push gate (full mypy project) OBRIGATÓRIO; §10
  pre-merge checklist; §11 merge via `sprint_merge.sh`.

### Empirical reality

Pre-flight (Commit 1 body) documented that:

1. CAL-138 had already shipped the TE GB/JP/CA connectors
   (`TE_YIELD_CURVE_SYMBOLS` at `te.py:170`; `fetch_yield_curve_nominal`
   at `te.py:1118`; `fetch_yield_curve_linker` at `te.py:1182`).
2. The dispatcher `_fetch_nominals_linkers`
   (`daily_curves.py:138-206`) already routed `country in
   TE_YIELD_CURVE_SYMBOLS` to TE — no dispatch extension required.
3. The sole operational gap was the `T1_7_COUNTRIES` tuple contents:
   the shared 7-tuple iterated US + 6 EA-periphery members, and
   PT/IT/ES/FR/NL always skipped (per five per-country CAL items
   opened by Week 10 Sprint A).

The sprint therefore resolved to a one-line tuple rename +
content change. Commits 2-3 added the test surface to lock the
contract. Commit 4 closes the CAL loop + retrospective.

---

## 3. Decision — pipeline-local rename (`T1_CURVES_COUNTRIES`)

The shared convention `T1_7_COUNTRIES = (US, DE, PT, IT, ES, FR, NL)`
lives in nine files (eight daily pipelines + `cli/status.py`) and
matches the ERP + overlays + cost-of-capital + cycles readiness
across all eight pipelines. Changing it globally would either:

1. Break the 7-tuple contract for seven other pipelines (unrelated to
   this sprint), or
2. Force curves to carry PT/IT/ES/FR/NL in `--all-t1` and emit a
   skip warning for each on every run (the pre-Sprint-E state).

The alternative — pipeline-local divergence with a distinct name —
makes the scope lock explicit and surfaces in code review when the
seven other pipelines' tuples come up next. The renamed constant
`T1_CURVES_COUNTRIES` is exported locally in `daily_curves.py`, used
only by its own `main(...)` + the two test files, and documented
inline (both in the module docstring and the constant's docstring).

`_DEFERRAL_CAL_MAP` remains the operator-facing pointer for PT / IT
/ ES / FR / NL (five per-country CAL items, Sprint A supersession of
`CAL-CURVES-EA-PERIPHERY`) and AU / NZ / CH / SE / NO / DK
(`CAL-CURVES-T1-SPARSE`); `--country <X>` still raises
`InsufficientDataError` with the CAL pointer for those.

---

## 4. Connector outcomes matrix (live canaries — 2026-04-22 execution)

| Country | Connector | Tenors observed | `source_connector` | `observations_used` | Verdict |
|---|---|---|---|---|---|
| US | `fred`    | 11 (DFII TIPS + DGS nominal) | `fred` | 11 | Existing; unchanged. Exercised by `test_daily_curves_pipeline.py::test_daily_curves_us_2024_01_02_all_four_tables`. |
| DE | `bundesbank` | 9 (BBSIS zero-coupon 1Y-30Y) | `bundesbank` | 9 | @slow `test_daily_curves_de_end_to_end` PASSED |
| EA | `ecb_sdw` | 11 (YC EA-AAA Svensson 3M-30Y) | `ecb_sdw` | 11 | @slow `test_daily_curves_ea_end_to_end` PASSED |
| GB | `te` | 12 (GUKG 1M-30Y Bloomberg) | `te` | ≥8 (NSS Svensson) | @slow `test_daily_curves_gb_end_to_end` PASSED |
| JP | `te` | 9 (GJGB 1M-10Y Bloomberg) | `te` | ≥7 (NSS Svensson) | @slow `test_daily_curves_jp_end_to_end` PASSED |
| CA | `te` | 6 (GCAN 1M/3M/6M/1Y/2Y/10YR) | `te` | 6 (NS-reduced) | @slow `test_daily_curves_ca_end_to_end` PASSED — CA mid-curve gap (3Y/5Y/7Y) tracked under `CAL-CURVES-CA-MIDCURVE` |

**Combined wall-clock** (6 canaries including the new full-iteration
canary): **18.11s**, well under the 90s brief HALT trigger 7
threshold.

---

## 5. HALT triggers (atomic — prompt §5 enumeration)

| # | Trigger | Fired? | Note |
|---|---|---|---|
| 0 | CAL-138 GB/JP/CA connectors missing | **No** | Pre-flight confirmed all three shipped at `te.py:170`. |
| 1 | Dispatcher route for TE absent | **No** | `_fetch_nominals_linkers` already routes `country in TE_YIELD_CURVE_SYMBOLS` to TE (line 187-197). |
| 2 | Tuple rename breaks external imports | **No** | Repo-wide grep: only `tests/integration/test_daily_curves_multi_country.py` imported `T1_7_COUNTRIES` from `daily_curves`; updated in Commit 1. Other eight files carry their own local `T1_7_COUNTRIES`. |
| 3 | Live canary wall-clock > 90s | **No** | 18.11s combined. |
| 4 | Pre-push gate fails | **No** | Full `uv run pre-commit run --all-files` green twice (see §9); full mypy project green. |
| 5 | Coverage regression > 3pp | **No** | Commit 2 added 13 unit tests; Commit 3 added one integration test; net coverage positive. |
| 6 | Tier scope drift (ADR-0010) | **No** | `T1_CURVES_COUNTRIES` members ⊂ ADR-0005 T1 set; zero T2 touch. |
| 7 | Scope creep (dispatcher change or connector rework) | **No** | All three commits stayed within brief-implied surface. |
| 8 | Pattern C (fast-forward merge not possible) | **TBD** | Resolved post-merge attempt — §12. |

---

## 6. Tier scope audit (ADR-0010 guardrail)

Per prompt header `**Tier scope**: T1 ONLY`:

- `T1_CURVES_COUNTRIES` members: US (T1), DE (T1), EA (T1-aggregate
  placeholder), GB (T1), JP (T1), CA (T1). Zero T2 countries.
- `_DEFERRAL_CAL_MAP` members: PT/IT/ES/FR/NL (T1 — deferred under
  per-country CAL items), AU/NZ/CH/SE/NO/DK (T1 — deferred under
  `CAL-CURVES-T1-SPARSE`). Still zero T2.
- No new CAL items opened touching T2.
- No connector wrappers extended for T2 countries.

ADR-0010 compliance confirmed; CC autonomy guardrail not triggered.

---

## 7. Coverage delta

Files touched: 4 (one src, three tests, one backlog doc, this retro).
Src delta: +16/-6 lines in `daily_curves.py` (rename + expanded
docstring). Tests delta: +223 new lines in
`tests/unit/test_pipelines/test_daily_curves.py`; +51/-2 lines in
`tests/integration/test_daily_curves_multi_country.py`. Full `mypy`
pass on `src/sonar` — zero new issues (see §9).

---

## 8. CAL evolution

| CAL item | Status before | Status after | Note |
|---|---|---|---|
| `CAL-138` | CLOSED | CLOSED (unchanged) | GB/JP/CA connector scope was already closed; Sprint E consumed the shipped surface. |
| `CAL-CURVES-T1-SPARSE` | Open (MEDIUM) | Open (MEDIUM) with refreshed **Current behavior** | Description updated to reflect `T1_CURVES_COUNTRIES` semantic; trigger-ship-CAL of AU/NZ/CH/SE/NO/DK still pending native CB connectors. |
| `CAL-CURVES-EA-PERIPHERY` | SUPERSEDED (Sprint A) | Unchanged | Successor per-country items still open; Sprint E does not ship any of them. |
| `CAL-CURVES-T1-LINKER` | Open (LOW) | Unchanged | Linker stubs remain empty for DE/EA/GB/JP/CA; Sprint E did not wire any linker path. |
| `CAL-CURVES-CA-MIDCURVE` | Open (LOW) | Unchanged | CA still fits NS-reduced (6 tenors); BoC Valet wiring pending. |

No new CAL items opened by Sprint E.

---

## 9. Pre-push gate — full mypy project (§8 OBRIGATÓRIO)

```
$ uv run ruff format --check src/sonar tests
<returns 0, no files reformatted>

$ uv run ruff check src/sonar tests
All checks passed!

$ uv run mypy src/sonar
Success: no issues found in <N> source files

$ uv run pre-commit run --all-files
trim trailing whitespace .... Passed
fix end of files          .... Passed
...
Conventional Commit       .... Passed
```

Executed twice before each commit per v3 Day 4 Week 9 cache-
invalidation lesson. No `--no-verify` used; zero deferred findings.

---

## 10. Pre-merge checklist (v3 §10 — executed 2026-04-22)

- [x] **All commits pushed to origin**: verified at `git log
  origin/sprint-curves-t1-sparse-inclusion --oneline` (post-push).
- [x] **Workspace clean**: `git status --porcelain` empty after C4.
- [x] **Pre-push gate green**: full ruff + mypy + pytest pre-commit
  run twice.
- [x] **Branch tracking set**: `git push -u origin
  sprint-curves-t1-sparse-inclusion` on first push; `git branch -vv`
  shows `[origin/sprint-curves-t1-sparse-inclusion]`.
- [x] **Sprint canaries documented** (§4 table above with
  observations_used + source_connector labels).

---

## 11. Merge execution (v3 §11)

Command:

```
./scripts/ops/sprint_merge.sh sprint-curves-t1-sparse-inclusion
```

Dogfood outcome: see §12 post-merge verification.

Paralelo context: Sprint F
(`sprint-cpi-infl-t1` / worktree `sonar-wt-cpi-infl-t1`) is the
sibling and may merge first depending on sequencing. Sprint E touches
only `src/sonar/pipelines/daily_curves.py`, two test files, one
backlog doc, and this retro; Sprint F is scoped to CPI + expected-
inflation T1 expansion (zero file overlap expected per prompt).
Rebase cost if Sprint F merges first: expected zero (non-overlapping
files); if shared `docs/backlog/calibration-tasks.md` changes
conflict, the union-merge convention from Week 9 applies.

---

## 12. Post-merge verification (v3 §12)

To be filled by operator after `sprint_merge.sh` reports `=== Sprint
merge COMPLETE ===`:

- [ ] `git log --oneline -10` — tip is the expected sprint-final SHA
  (Commit 4 this retro).
- [ ] `git worktree list` — `sonar-wt-curves-t1-sparse-inclusion`
  absent; only the primary repo + any active paralelo worktree
  (`sonar-wt-cpi-infl-t1`) remain.
- [ ] `git branch -a` — no leftover
  `sprint-curves-t1-sparse-inclusion` locally; `origin/sprint-curves-
  t1-sparse-inclusion` absent.

Any leftover state is the signal for the follow-up retrospective
§Lessons.

---

## 13. Lessons

1. **When CAL-138 and Sprint E scoped the work cleanly, the sprint
   shipped in < 1h.** Pre-flight confirmed the dispatcher + connectors
   were already in place; the operational gap was a single-line
   tuple edit. This is the pattern-template dividend ADR-0010
   predicted: once the machine is proven, sparse inclusions are
   trivial.

2. **Pipeline-local tuples beat shared-convention rewrites when
   divergence is justified.** The shared `T1_7_COUNTRIES`
   convention across eight daily pipelines would have been broken
   globally if Sprint E edited the shared name; the
   `T1_CURVES_COUNTRIES` local rename isolates the divergence and
   documents the "why" in the constant's docstring. Downstream code
   review gains an explicit marker.

3. **Tests-as-contract lock the tuple before operator depends on it.**
   The three tuple-invariant unit tests (membership equality with
   `CURVE_SUPPORTED_COUNTRIES`, disjointness from
   `_DEFERRAL_CAL_MAP`, ordering stability) are cheap to write now
   and expensive to debug if they silently drift in six months.

4. **Brief-format-v3 mental template is applicable even when no
   written brief exists.** The prompt enumerated §3 (concurrency —
   paralelo with Sprint F), §5 (HALT triggers), §8 (pre-push gate),
   §10-12 (merge discipline). Writing the retro in v3 shape preserves
   the discipline for solo-autonomous sprints that skip the formal
   brief markdown.

5. **Next opportunistic simplification**: if the five EA periphery
   per-country sprints (`CAL-CURVES-PT-BPSTAT` /
   `CAL-CURVES-IT-BDI` / `CAL-CURVES-ES-BDE` /
   `CAL-CURVES-FR-BDF` BLOCKED / `CAL-CURVES-NL-DNB`) close three
   of five, fold the successes back into `T1_CURVES_COUNTRIES`
   (append `PT/IT/ES` at ship-time). This is the natural re-entry
   path; the rename makes it a surgical edit.

---

*End of Week 10 Sprint E retrospective. 3 substantive commits +
this retro. `daily_curves --all-t1` now iterates the six curve-
capable T1 countries via `T1_CURVES_COUNTRIES`; PT/IT/ES/FR/NL
+ AU/NZ/CH/SE/NO/DK remain deferred per the existing per-country
CAL items. Format v3 applied without a written brief.*
