# Sprint Q.0.5 — T1 Cohort Unification (M3/M4 Cohort Merge) — Retrospective

**Sprint**: Week 11 Day 1 Sprint Q.0.5
**Branch**: `sprint-q-0-5-t1-cohort-unification`
**Worktree**: `/home/macro/projects/sonar-wt-q-0-5-t1-cohort-unification`
**Data**: 2026-04-24 manhã (arranque ~09:00 WEST; wall-clock ~25 min vs 30-45min budget)
**Operator**: Hugo Condesa (reviewer) + Claude Code (executor autónomo per SESSION_CONTEXT)
**Parent**: Sprint Q (Week 11 Day 1) Tier B discovery — natural fire default cohort = 7 (M4 FCI EA-custom), missing EA/GB/JP/CA/AU
**Outcome**: 3 commits + retro (this = C4), `T1_COUNTRIES` unified 12-country canonical, deprecated aliases preserved, 4 new tests green, full pre-existing 2131 regression pass.

---

## 1. Scope shipped

| Commit | Scope | Ficheiros |
|---|---|---|
| **C1** | refactor(pipelines): T1_COUNTRIES unified 12-country cohort + deprecation aliases + warning + CLI help | `src/sonar/pipelines/daily_monetary_indices.py` |
| **C2** | (no-op) AU + NL classifier policy unchanged — `m3_country_policies.classify_m3_compute_mode` already returns `("NOT_IMPLEMENTED", ())` for any country outside the 9-country `M3_T1_COUNTRIES` policy frozenset; brief §2.7 conditional clause not triggered | — |
| **C3** | test: regression coverage 12-country cohort + deprecation alias semantics + flag deprecation | `tests/unit/test_pipelines/test_daily_monetary_indices.py`, `tests/unit/test_pipelines/test_m3_builders.py` |
| **C4** (this) | docs(planning): retrospective + cohort unification rationale + Lessons #17/#18 candidates | this file |

**Scope respected**: zero new connectors, zero new builders, zero EXPINF expansion (Sprint Q.1 territory), zero MSC EA work (Sprint P), zero systemd ExecStart edit. Per brief §4 HALT triggers: none fired.

---

## 2. Architectural reality vs brief premise — discoveries

### Discovery #1 — `T1_7_COUNTRIES` is per-pipeline, not cross-imported

Brief §2.4 anticipated `T1_7_COUNTRIES` and `T1_M3_COUNTRIES` being imported across modules. Audit revealed each pipeline (`daily_cost_of_capital.py`, `daily_credit_indices.py`, `daily_financial_indices.py`, `daily_cycles.py`, `daily_economic_indices.py`, `daily_overlays.py`, `cli/status.py`) defines its **own** `T1_7_COUNTRIES = ("US", "DE", "PT", "IT", "ES", "FR", "NL")` constant locally — semantically the M4-FCI-EA-custom-7 cohort scoped to that layer.

**Implication**: Sprint Q.0.5 unification touches only `daily_monetary_indices.py` per brief §2.1 explicit scope. Other pipelines keep their per-layer T1_7 (overlays, FCI, cycles, etc.) which represent the M4-FCI-aligned 7-country cohort, distinct from the **monetary pipeline's M3-classifier dispatch cohort** that this sprint unifies.

`T1_M3_COUNTRIES` was the only truly cross-imported constant (one consumer: `tests/unit/test_pipelines/test_m3_builders.py`). Aliasing it to `T1_COUNTRIES` preserves that import.

Brief §2.4 scope gate (>5 files importing) did not trigger because the imports are local definitions, not cross-imports — refactor stays surgical.

### Discovery #2 — AU + NL graceful path already wired

Brief §2.5 + §2.7 conditional clause anticipated that AU might surface a `KeyError` in `m3_country_policies.py`. Inspection of `src/sonar/indices/monetary/m3_country_policies.py:147-150` shows the classifier handles unknown countries via membership check on the frozenset:

```python
if country not in M3_T1_COUNTRIES:
    return "NOT_IMPLEMENTED", ()
```

AU, NL, PT all flow through this path cleanly — no KeyError, no exception, returns tuple. The brief's defensive C2 commit (add explicit AU/NL `M3Policy` entries) was therefore **not needed**. Saved one commit + kept the policy frozenset purely about FULL/DEGRADED-capable countries (cleaner separation).

`run_one` (lines 540-571) further wraps with `_CURVES_SHIPPED_COUNTRIES` membership check: NL (no curves shipped) emits `m3_skipped_upstream_not_shipped` info-level skip; PT/AU (curves shipped Sprint M/T) flow through the classifier and emit `mode=NOT_IMPLEMENTED` cleanly. Verified E2E in §3 below.

### Discovery #3 — pytest unraisable warnings + asyncio.run

Initial implementation of `test_m3_t1_cohort_flag_deprecated` and `test_all_t1_flag_resolves_to_unified_cohort` invoked `pipeline_mod.main()` directly. `main` calls `asyncio.run(_run_async_pipeline(...))` even with `_run_async_pipeline` monkeypatched to a sync return — the `asyncio.run` call still spins up a fresh event loop. Combined with pytest's strict unraisable-exception checker and pytest-asyncio managing its own loops downstream, the residual loop teardown surfaced as `ResourceWarning: unclosed event loop` collected at the boundary of a later async test (`test_connector_aclose_lifecycle`), failing it.

Fix: `_stub_main` helper monkeypatches both `_run_async_pipeline` (as a sync function) **and** `pipeline_mod.asyncio.run` (passthrough that closes the discarded coroutine and returns the stub's value). No real event loop ever gets created. Test passes in any ordering, full file 38/38 green.

Lesson: when monkeypatching the inner of an `asyncio.run(…)` call site, also monkeypatch `asyncio.run` itself — otherwise pytest-asyncio's loop bookkeeping collides with the throwaway loop.

---

## 3. Cohort unification — before / after

### Constants

| Constant | Pre-Q.0.5 | Post-Q.0.5 |
|---|---|---|
| `T1_COUNTRIES` | (didn't exist) | **canonical**: `("US", "DE", "EA", "GB", "JP", "CA", "IT", "ES", "FR", "NL", "PT", "AU")` — 12 |
| `T1_7_COUNTRIES` | `("US", "DE", "PT", "IT", "ES", "FR", "NL")` — 7 | deprecated alias → `T1_COUNTRIES` (12) |
| `T1_M3_COUNTRIES` | `("US", "DE", "EA", "GB", "JP", "CA", "IT", "ES", "FR")` — 9 | deprecated alias → `T1_COUNTRIES` (12) |

### CLI flag semantics

| Flag | Pre-Q.0.5 | Post-Q.0.5 |
|---|---|---|
| `--all-t1` | iterates 7 (T1_7_COUNTRIES) | iterates 12 (T1_COUNTRIES); help text updated |
| `--m3-t1-cohort` | iterates 9 (T1_M3_COUNTRIES) | iterates 12 (T1_COUNTRIES) + emits `DeprecationWarning`; marked `[DEPRECATED]` in help |
| `--country X` | single X | single X (unchanged) |

### Systemd

`deploy/systemd/sonar-daily-monetary-indices.service` ExecStart **unchanged** per brief §2.3. The flag string `--all-t1` now resolves to 12 countries inside the pipeline — no service-file edit needed, blast radius reduced. Tier B verification (operator-driven post-merge) confirms in journal: 12 `m3_compute_mode` emits per dispatch instead of 7.

---

## 4. Observability impact matrix

Pre-Q.0.5 default `--all-t1` emit (7 countries):

```
US (M3 NOT_IMPLEMENTED — was outside M3 cohort path)
DE PT IT ES FR NL  (no M3 emit because db_backed_builder routes only via run_one which
                    classifier-keys on M3_T1_COUNTRIES; pre-Q.0.5 these resolved to
                    NOT_IMPLEMENTED outside the cohort path that --all-t1 reached)
```

Wait — important nuance: pre-Q.0.5 the M3 classifier emit lived in `run_one` regardless of cohort, but `--all-t1` only iterated 7 countries that happened to mostly be NOT_IMPLEMENTED-mode for M3 (US being the exception, FULL post-Sprint-Q). So **EA/GB/JP/CA/IT/ES/FR M3 DEGRADED was invisible** to natural fire — only reachable via the opt-in `--m3-t1-cohort` flag that systemd never invokes.

Post-Q.0.5 default `--all-t1` emit (12 countries, verified locally on 2026-04-23):

```
m3_compute_mode country=US mode=FULL              flags=('US_M3_T1_TIER', 'M3_FULL_LIVE')
m3_compute_mode country=DE mode=DEGRADED          flags=('DE_M3_T1_TIER', 'M3_EXPINF_MISSING')
m3_compute_mode country=EA mode=DEGRADED          flags=('EA_M3_T1_TIER', 'M3_EXPINF_MISSING')
m3_compute_mode country=GB mode=DEGRADED          flags=('GB_M3_T1_TIER', 'M3_EXPINF_MISSING')
m3_compute_mode country=JP mode=DEGRADED          flags=('JP_M3_T1_TIER', 'JP_M3_BEI_LINKER_THIN_EXPECTED', 'M3_EXPINF_MISSING')
m3_compute_mode country=CA mode=DEGRADED          flags=('CA_M3_T1_TIER', 'CA_M3_BEI_RRB_LIMITED_EXPECTED', 'M3_EXPINF_MISSING')
m3_compute_mode country=IT mode=DEGRADED          flags=('IT_M3_T1_TIER', 'IT_M3_BEI_BTP_EI_SPARSE_EXPECTED', 'M3_EXPINF_MISSING')
m3_compute_mode country=ES mode=DEGRADED          flags=('ES_M3_T1_TIER', 'ES_M3_BEI_BONOS_EI_LIMITED_EXPECTED', 'M3_EXPINF_MISSING')
m3_compute_mode country=FR mode=DEGRADED          flags=('FR_M3_T1_TIER', 'M3_EXPINF_MISSING')
m3_compute_mode country=NL mode=NOT_IMPLEMENTED   flags=()
m3_skipped_upstream_not_shipped country=NL date=2026-04-23 reason=country_outside_curves_ship_cohort
m3_compute_mode country=PT mode=NOT_IMPLEMENTED   flags=()
m3_compute_mode country=AU mode=NOT_IMPLEMENTED   flags=()
```

Breakdown: 1 FULL (US) + 8 DEGRADED (DE/EA/GB/JP/CA/IT/ES/FR) + 3 NOT_IMPLEMENTED (NL/PT/AU). NL additionally emits `m3_skipped_upstream_not_shipped` because it's outside `_CURVES_SHIPPED_COUNTRIES`. AU and PT have curves shipped; classifier returns NOT_IMPLEMENTED because they're outside `M3_T1_COUNTRIES` policy frozenset (deferred to future per-country sprints).

Total observability 7 → 12 countries per natural fire (+71%).

---

## 5. Sprint downstream impact

| Sprint | Pre-Q.0.5 status | Post-Q.0.5 unblock |
|---|---|---|
| **Sprint Q.1 (EA-ECB-SPF)** | EXPINF wiring would deposit data invisible to natural fire | EA visible immediately in default `--all-t1` — `EA_M3_EXPINF_MISSING` → `M3_FULL_LIVE` flips visible per natural fire |
| **Sprint Q.2 (GB-BOE-ILG-SPF)** | idem | GB visible immediately |
| **Sprint P (MSC EA)** | EA aggregate not iterated by default | EA in cohort, MSC EA L4 composite reachable post-Q.1 |
| **Sprint M2-EA-per-country** | DE/FR/IT/ES/NL only via opt-in | DE/FR/IT/ES/NL all in default cohort, per-country builders invoked |
| **Sprint M4-scaffold-upgrade GB/JP/CA** | M4 scaffold paths invisible | GB/JP/CA M4 scaffold emits visible in journal |

---

## 6. Acceptance — Tier A verified

| # | Check | Result |
|---|---|---|
| 1 | Constants — 1 canonical + 2 aliases | ✅ `grep "^T1_.*_COUNTRIES *[:=]"` → 3 lines |
| 2 | Cohort size 12 | ✅ `len(T1_COUNTRIES) == 12; sorted == ['AU','CA','DE','EA','ES','FR','GB','IT','JP','NL','PT','US']` |
| 3 | `--all-t1` 12-country emit | ✅ `grep "m3_compute_mode" \| wc -l` = 12 |
| 4 | US still FULL (Sprint Q regression) | ✅ `country=US mode=FULL flags=('US_M3_T1_TIER', 'M3_FULL_LIVE')` |
| 5 | AU + NL graceful | ✅ both emit `mode=NOT_IMPLEMENTED`, no exception; NL also `m3_skipped_upstream_not_shipped` |
| 6 | Bash wrapper smoke | ✅ exit 0, `n_failed=0` |
| 7 | Regression suite | ✅ 2131 pass (excluding 5 pre-existing live-network/canary failures unrelated to refactor: 2 live FRED 400 with placeholder API key, 3 live network canaries) |
| 8 | Pre-commit clean double-run | ✅ both runs all hooks pass |

Tier B (operator-driven post-merge): systemd `start sonar-daily-monetary-indices.service` + journal verify `m3_compute_mode \| wc -l == 12` + `n_failed=0` + zero event-loop errors.

---

## 7. Technical debt closed

- **Dual-constant drift** (`T1_7_COUNTRIES` vs `T1_M3_COUNTRIES`) eliminated within `daily_monetary_indices.py`. Single canonical `T1_COUNTRIES` tracks true T1 curves coverage (11 with shipped curves + NL graceful skip).
- **CLI flag confusion**: `--all-t1` (7 countries) vs `--m3-t1-cohort` (9 countries) — now both resolve to the same 12. `--m3-t1-cohort` retained with `DeprecationWarning` for one cleanup-window grace period.
- **Brief observability gap**: GB / JP / CA / EA M3 DEGRADED were structurally invisible to systemd default fire pre-Q.0.5; now part of canonical journal output every dispatch.

---

## 8. Lessons candidates

### Lesson #17 — Cohort constants should track true layer coverage, not per-layer slice

**Statement**: When multiple layers (M3 classifier, M4 FCI, M2 Taylor) have overlapping but non-identical country-coverage capability, define **one** canonical cohort constant tracking the **true T1 ship state** (curves availability), and let each per-country classifier policy resolve `FULL/DEGRADED/NOT_IMPLEMENTED` per-country. Avoid the temptation to define `T1_M3`, `T1_M4`, `T1_M2` per-layer constants — they drift apart over time (Sprint J vs Sprint O), the systemd default flag picks one arbitrarily, and the others become invisible.

**Why**: Sprint J (Week 10 Day 2) shipped `T1_7_COUNTRIES` aligned to M4-FCI-EA-custom capability. Sprint O (Week 10 Day 3) shipped `T1_M3_COUNTRIES` aligned to M3 classifier capability, kept separate to avoid breaking Sprint J. Sprint M + T expanded curves T1 to 11 (PT, AU). By Sprint Q (Week 11), the systemd `--all-t1` default cohort was 7 — neither aligned to curves T1 (11) nor M3 cohort (9). Sprint Q's EXPINF FULL promotion was visible only for US in production fire because US is in both old cohorts.

**How to apply**: When a future sprint extends T1 curves coverage to a new country (e.g., NZ, CH), update `T1_COUNTRIES` to include it. Per-layer policy modules (m3_country_policies, m4_country_policies, …) decide what mode each country resolves to — that's where per-layer capability lives, not in the iteration cohort constant.

### Lesson #18 — Systemd ExecStart audit is a Tier B verification standard

**Statement**: Whenever pipeline dispatcher semantics change (cohort size, default flag interpretation, retry policy), Tier B verification should always include the operator-driven systemd journal grep (`m3_compute_mode \| wc -l`, etc.) to confirm the change lands in production fire. CC-side Tier A `--all-t1` smoke against the dev DB is necessary but not sufficient — the systemd unit's `--date $(...)` substitution + cron-style fire shape can mask differences invisible to the local invocation.

**Why**: Sprint Q's "default cohort = 7 not 9" discovery came from Tier B journal grep, not from CC's Tier A smoke. The systemd unit was correct; the brief assumption about which cohort `--all-t1` meant was wrong. Tier B caught it because the operator scrutinised the post-merge journal.

**How to apply**: When a sprint brief's Tier B includes "verify N emit in journal", treat the count as a correctness assertion, not a sanity check. If the count diverges from Tier A's count, the sprint's premise about default semantics needs revisit before ship.

### Lesson #19 — Monkeypatch `asyncio.run` when stubbing async dispatchers

**Statement**: If a unit test monkeypatches an `async` function that is called via `asyncio.run(…)` at the call site, the test must **also** monkeypatch `asyncio.run` to a passthrough — otherwise a fresh event loop spins up per test invocation, conflicts with pytest-asyncio's loop bookkeeping in adjacent async tests, and surfaces as `ResourceWarning: unclosed event loop` at the boundary of a later test (under pytest's strict unraisable-exception checker).

**Why**: Sprint Q.0.5's `test_m3_t1_cohort_flag_deprecated` initially patched `_run_async_pipeline` only. `pipeline_mod.main` calls `asyncio.run(_run_async_pipeline(...))`. The monkeypatched dispatcher returned synchronously, but `asyncio.run` still created a loop, ran the awaitable, and closed it. The closed-but-not-deleted loop survived as an unraisable warning collected at the next async test's `pytest_runtest_call` boundary, failing it. Fix: helper `_stub_main` patches both surfaces.

**How to apply**: `monkeypatch.setattr(pipeline_mod, "_run_async_pipeline", sync_stub)` + `monkeypatch.setattr(pipeline_mod.asyncio, "run", lambda coro: (coro.close(), sync_stub(...))[1])` — keeps the test off real event-loop plumbing entirely.

---

## 9. CAL items

### Closed by this sprint
- **Informal**: dual cohort constant drift (T1_7 vs T1_M3) within `daily_monetary_indices.py` — resolved.

### Opened by this sprint
- **CAL-COHORT-CONSTANT-CLEANUP** (Week 12+ low priority): once Sprint Q.1, Q.2, P, M2-EA-per-country complete, remove `T1_7_COUNTRIES` and `T1_M3_COUNTRIES` deprecated aliases + remove `--m3-t1-cohort` deprecated flag. Single `T1_COUNTRIES` + `--all-t1` only.
- **CAL-M3-AU-BUILDER** (low priority): placeholder for eventual AU M3 builder + EXPINF connector (post-Sprint-T Path 2 future). When opened, AU's classifier resolves to FULL/DEGRADED instead of NOT_IMPLEMENTED.

---

## 10. Time accounting

| Phase | Wall-clock |
|---|---|
| Pre-flight + audit (§2.4 + §2.5) | ~5 min |
| C1 refactor + verify | ~6 min |
| C3 tests + iterate (3 ruff fixes + Lesson #19 discovery) | ~10 min |
| Tier A acceptance + pre-commit double-run | ~3 min |
| C4 retro (this) | ~6 min |
| **Total** | **~30 min** (vs 30-45min budget) |

Audit-first paid off — Discovery #1 (per-pipeline T1_7) and Discovery #2 (graceful AU/NL classifier) up-front kept C1 surgical and saved C2 entirely.

---

*End of retro. Tech-debt micro-sprint shipped clean. Sprint Q.1 (EA-ECB-SPF) and Sprint P (MSC EA) now genuinely unblocked — EA visible in natural fire post-merge.*
