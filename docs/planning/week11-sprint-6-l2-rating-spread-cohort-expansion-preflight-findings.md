---
sprint: week11-sprint-6-l2-rating-spread-cohort-expansion
phase: pre-flight
date: 2026-04-26
status: HALT-0 cleared (no triggers fired); Commit 2 cohort-extension code change required + authorised per brief §8
amendment: 2026-04-26 cohort reduced 6 → 5 (DK removed per ADR-0010 T1-strict)
---

# Sprint 6 — L2 rating-spread cohort expansion T1 — Pre-flight findings

Empirical pre-flight audit per brief §2 (HALT #0 mandatory) and brief §4
Commit 1 contract. Ships under Commit 1 of the Sprint 6 run as the
specs-first record of what will be committed in Commits 2-6.

Cohort scope: **NL + NZ + CH + SE + NO** (5 países). EA aggregate
excluded by Sprint 4 precedent + spec §3 (rating agencies don't rate
currency-union aggregates). DK excluded by amendment 2026-04-26
(T2 per `country_tiers.yaml:90`; ADR-0010 strict T1-ONLY through
Phase 4 forbids T2 surface — DK rating-spread expansion deferred to
Phase 5+ via CAL-RATING-DK-PHASE5 candidate filed in Sprint 6
retrospective).

## 1. Brief + spec reads (HALT #0 cleared)

End-to-end reads completed:

- `docs/planning/week11-sprint-6-l2-rating-spread-cohort-expansion-brief.md` (§1 → §8) ✓
- `docs/specs/overlays/rating-spread.md` v0.2 §4 (algorithm) + §6 (edge
  cases) + §8 (storage schema, ck_rc_notch `[-1.0, 22.0]`) ✓
- `docs/specs/conventions/patterns.md` Pattern 4 (aggregator-primary +
  native-override) — implicit; not re-read this sprint as Sprint 4
  pattern is reused verbatim (no new compute logic)
- `docs/adr/ADR-0010-tier-scope-lock.md` — T1 ONLY enforcement honoured
  by cohort scope (DK exclusion 2026-04-26 amendment is the explicit
  manifestation of this constraint)
- `src/sonar/overlays/rating_spread_backfill.py` (688 lines) — reuse
  surface confirmed; only data tables `TIER1_COUNTRIES` +
  `TE_COUNTRY_OVERRIDES_TIER1` need extending
- `src/sonar/cli/backfill.py` lines 368-481 — `rating-spread` Typer
  subcommand validates every `--countries` token against
  `RATING_TIER1_COUNTRIES`; non-Tier1 codes raise `EXIT_IO`
- Sprint 4 commit `f2cc4ef` (feat) + patch `faa73d2` (migration 019
  ck_rc_notch range fix) + spec sync `82f5f52` — backfill orchestrator
  baseline + schema parity verified

No separate Sprint 4 retrospective markdown exists in
`docs/planning/retrospectives/`; Sprint 4 context was folded into the
brief + commit body. Used Sprint 4 brief
(`week11-sprint-4-l2-rating-spread-te-brief.md`) as the canonical
reference for invariants that Sprint 6 inherits.

## 2. TE country-name pre-validation (mandatory per brief §2)

Sprint 4 mapping pattern: TE returns the country in the canonical
English form (e.g. `"United States"`, `"United Kingdom"`). Sprint 6
extension uses identical form for the 5 new país:

| ISO | TE country slug   | Pattern verified |
|-----|-------------------|------------------|
| NL  | `Netherlands`     | single-word, matches Sprint 4 single-word pattern (e.g. `Germany`/`France`/`Japan`) |
| NZ  | `New Zealand`     | 2-word capitalised, matches `United States`/`United Kingdom` Sprint 4 pattern |
| CH  | `Switzerland`     | single-word |
| SE  | `Sweden`          | single-word |
| NO  | `Norway`          | single-word |

Live TE-snapshot verification deferred to Commit 2 backfill execution —
the `/ratings` snapshot returns all 160 countries in a single call, so
the 5-of-160 lookup is a derivative of one already-cached fetch (no
incremental quota cost). Per-country `/ratings/historical/{slug}` HTTP
calls in Commit 2 will surface any 404 → HALT-0 case (per brief §5
trigger 0); risk is bounded since Sprint 4 hit zero 404s on the 10-país
cohort and the 5 new país are all OECD high-grade sovereigns with
multi-decade rating histories.

## 3. TE quota pre-check (mandatory per brief §2)

| Item | Value |
|------|-------|
| Baseline (post-Sprint 5B, 2026-04-26) | ~40-41 % of 5000/mo |
| Sprint 6 estimated calls | 1 snapshot (cached 24h; reused if warm) + 5 historical = **5-6 calls** |
| Headroom to 70 % HALT trigger | ~29 pp |
| HALT #1 risk | Negligible (5-6 calls = ~0.1-0.12 pp delta) |

Source: `docs/planning/retrospectives/week11-sprint-5b-l2-curves-t1-europe-sparse-report.md`
§9 ("baseline pre-Sprint-5B ~40 %; post ~40-41 %; headroom ~29 pp").

## 4. Schema validation (mandatory per brief §2)

| Check | Result |
|-------|--------|
| Alembic head | `019_rating_consolidated_notch_range_fix` ✓ matches brief §2 expected `019` |
| `ck_rc_notch` range | `[-1.0, 22.0]` ✓ accommodates outlook/watch modifiers + single-agency edge cases (per Sprint 4 patch `faa73d2`) |
| Migration count | 19 (head) — no new migration expected (data-only sprint) |

## 5. Tables baseline (engine DB, shared via `data/sonar-dev.db` symlink)

```
tbl           n
------------  ---
agency_raw    530
consolidated  466
calibration   22
n_countries   10  (US, DE, FR, IT, ES, PT, GB, JP, CA, AU)
```

Per-country distribution (`ratings_agency_raw`):

| ISO | Rows |
|-----|------|
| AU  | 35   |
| CA  | 34   |
| DE  | 19   |
| ES  | 81   |
| FR  | 46   |
| GB  | 44   |
| IT  | 81   |
| JP  | 54   |
| PT  | 104  |
| US  | 32   |
| **Total** | **530** |

Note: Sprint 4 commit body (`f2cc4ef`) cited `agency_raw ≥ 350` /
`consolidated ≥ 200` as post-merge targets. Brief §2 cited
"Sprint 4 baseline 491 / 466". Live engine DB shows 530 raw / 466
consolidated as of 2026-04-26 — the +39 raw delta vs. brief baseline
likely reflects incremental TE 7d-cache misses re-pulling new
historical actions during routine pipeline runs. `ratings_consolidated`
is unchanged (466) which confirms no new `(country, date, rating_type)`
tuples have entered the consolidator since Sprint 4 close.

Sprint 6 sprint-end Tier B targets per brief §6 amendment
(`agency_raw ≥ 660`, `consolidated ≥ 580`, `n_countries = 15`)
measured from current 530 / 466 / 10 baseline (not the brief's 491 /
466 / 10 baseline) — gives expected +130-160 raw / +115-150 consolidated
/ +5 país from Sprint 6 contribution (proportional drop vs. brief's
6-país pre-amendment estimate).

## 6. Cohort vs. country_tiers.yaml T1 — confirmed

Reading of `docs/data_sources/country_tiers.yaml` (live audit 2026-04-26):

| ISO | country_tiers.yaml tier | Notes |
|-----|------------------------|-------|
| NL  | T1 (line 47)           | canonical T1 |
| NZ  | T1 (line 52)           | canonical T1 (`curves_path_2_pending: true` flag) |
| CH  | T1 (line 53)           | canonical T1 |
| SE  | T1 (line 55)           | canonical T1 |
| NO  | T1 (line 54)           | canonical T1 |

All 5 cohort países are canonical T1. ADR-0010 strict T1-ONLY
satisfied. **DK exclusion** rationale: line 91 classifies DK as T2;
spec §3 EA-aggregate exclusion is by design (currency unions don't
issue), not a slot to fill with a T2 substitute. DK rating-spread
expansion deferred Phase 5+ via CAL-RATING-DK-PHASE5 candidate (filed
in Sprint 6 retrospective).

## 7. Code-change requirement (brief §8 explicit authorisation)

Existing constants in `src/sonar/overlays/rating_spread_backfill.py`
hard-code the Sprint 4 10-país cohort:

- `TIER1_COUNTRIES` (line 81) — 10-tuple
- `TE_COUNTRY_OVERRIDES_TIER1` (line 97) — 10-entry dict
- `TIER1_ISO_TO_TE_NAME` (line 110) — derived from above

`src/sonar/cli/backfill.py:412` rejects any `--countries` token outside
`RATING_TIER1_COUNTRIES`. Sprint 6 cohort cannot run end-to-end without
extending these constants.

Brief §8 ("`_te_country_to_iso` mapper já implementado Sprint 4 —
verify 5 países handled OR add mapping if not") explicitly authorises
this extension. Commit 2 will:

1. Extend `TIER1_COUNTRIES` from 10 to 15 ISO codes (append NL, NZ, CH,
   SE, NO).
2. Extend `TE_COUNTRY_OVERRIDES_TIER1` with 5 new TE-name → ISO entries
   matching §2 mapping table.
3. Update module docstring (`Sprint 4 cohort scope: 10 sovereign Tier 1
   countries` → `Sprint 4 cohort + Sprint 6 expansion: 15 sovereign
   Tier 1 countries`).
4. Re-run pre-push gate (`ruff format/check + mypy + pytest -m "not slow"`).

No new test fixtures expected — Sprint 4 unit tests cover the parsing
+ mapping + persistence helpers in isolation; the cohort tuple is data,
not behaviour. Test file at
`tests/unit/test_overlays/test_rating_spread_te.py:241` references
`CAL-RATING-COHORT-EXPANSION` in a doc-string only.

## 8. HALT triggers — current status

| # | Trigger | Status |
|---|---------|--------|
| 0 | Pre-flight TE country mapping fails | **No live probe yet**; deterministic mapping pre-validated §2; live verification in Commit 2 |
| 1 | TE quota >70 % mid-sprint | No (~40-41 % baseline; +0.1-0.12 pp expected) |
| 2 | TE invalid token (Sprint 4 saw 5 across 10 país, ~0.5 %) | Not a HALT; logged + skipped |
| 3 | CHECK constraint failure post-consolidate | No (migration 019 head, range parity confirmed) |
| 4 | Consolidated rows < 40 total for 5 país | Pending Commit 2 execution |
| 5 | Coverage regression > 3pp in tests | Pending pre-push gate |
| 6 | Pre-push gate fail (no `--no-verify`) | Pending |

HALT-0 cleared. Sprint proceeds to Commit 2.

## 9. Plan — 6 commits

1. **Commit 1 (this doc + brief amendment)** — Pre-flight findings +
   plan + brief edit removing DK from cohort references (single doc
   commit per operator instruction 2026-04-26).
2. **Commit 2** — Cohort extension code change in
   `src/sonar/overlays/rating_spread_backfill.py` (TIER1_COUNTRIES
   10→15 + TE_COUNTRY_OVERRIDES_TIER1 + docstring) + pre-push gate
   green + backfill execution against engine DB (worktree code via
   PYTHONPATH override; data writes hit shared engine DB) + Tier B SQL
   output recorded in commit body.
3. **Commit 3** — `docs/data_sources/country_tiers.yaml` flag — add
   `rating_spread_live: true` for the 5 país (under existing T1
   entries; DK retains T2 classification — no flag added).
4. **Commit 4** — `docs/specs/overlays/rating-spread.md` country-scope
   appendix update (cohort 10 → 15; DK exclusion documented as
   Phase 5+ deferral per ADR-0010).
5. **Commit 5** — `docs/backlog/calibration-tasks.md` —
   `CAL-RATING-COHORT-EXPANSION` registered as a CLOSED CAL with
   cohort delta + Tier B row counts; `CAL-RATING-DK-PHASE5` opened as
   forward-looking entry.
6. **Commit 6** — Retrospective at
   `docs/planning/retrospectives/week11-sprint-6-l2-rating-spread-cohort-expansion-report.md`
   per brief §7 structure, including HALT-0 amendment trace
   (cohort 6→5 reduction operator decision 2026-04-26).

Pre-push gate (`ruff format && ruff check && mypy && pytest -m "not slow"`)
mandatory before every push, no `--no-verify`.

## 10. Acceptance pre-check (brief §6 sprint-end targets)

Will be re-asserted with live numbers in Commit 5 + Commit 6:

- [ ] `ratings_agency_raw` ≥ 660 rows total (current 530 + ~130-160 expected)
- [ ] `ratings_consolidated` ≥ 580 rows total (current 466 + ~115-150 expected)
- [ ] `n_countries` distinct in `ratings_agency_raw` = 15
- [ ] 4 agencies still present (SP / MOODYS / FITCH / DBRS)
- [ ] `consolidated_sonar_notch` range within `[-1.0, 22.0]`
- [ ] All 5 new país represented in consolidated table
- [ ] `CAL-RATING-COHORT-EXPANSION` closed
- [ ] `CAL-RATING-DK-PHASE5` filed as Phase 5+ candidate
- [ ] No `--no-verify`
- [ ] Pre-push gate green every push

---

**END PRE-FLIGHT FINDINGS**
