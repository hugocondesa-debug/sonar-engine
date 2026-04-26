# Sprint 6 — L2 rating-spread cohort expansion T1 (CAL-RATING-COHORT-EXPANSION)

**Tier scope**: T1 ONLY per ADR-0010 (5 countries, sparse cohort).
**Pattern reference**: Sprint 4 (2026-04-25/26) — TE-driven rating-spread backfill canonical.
**Predecessor success**: Sprint 4 shipped 10 países T1 + 491 agency_raw + 466 consolidated rows + migration 019 schema fix.

**Amendment 2026-04-26**: cohort reduced 6 → 5 países (DK removed) per
operator HALT decision. `country_tiers.yaml:90` classifies DK as T2;
ADR-0010 strict T1-ONLY enforcement through Phase 4 forbids T2 surface.
DK rating-spread expansion deferred to Phase 5+ (CAL-RATING-DK-PHASE5
candidate filed in Sprint 6 retrospective). EA aggregate exclusion is
by design (currency unions don't issue sovereign debt rated by S&P/
Moody's/Fitch/DBRS) — not a slot to fill with arbitrary T2 substitute.

---

## 1. Scope

**In**:
- Extend rating-spread Tier 1 cohort from 10 → 15 countries via TE Path 1
- 5 países: **NL + NZ + CH + SE + NO**
- Per-country: TE `/ratings/{country}` snapshot + `/ratings/historical/{country}` archive
- Consolidate via existing `backfill_consolidate()` (no new compute logic)
- Update `country_tiers.yaml` rating-spread coverage flags
- Update `docs/specs/overlays/rating-spread.md` country scope appendix

**Out**:
- EA aggregate (excluded by design — Sprint 4 precedent; not a sovereign issuer)
- DK (T2 per `country_tiers.yaml:90`; ADR-0010 strict T1-ONLY through
  Phase 4 — deferred to Phase 5+ via CAL-RATING-DK-PHASE5 candidate)
- Calibration table refresh (Sprint 4 shipped APRIL_2026_CALIBRATION; quarterly refresh per spec §4 = separate task)
- Downstream CRP integration (consumer-side; separate sprint)
- New methodology version (`RATING_SPREAD_v0.2` reused verbatim)

---

## 2. Spec reference + pre-flight

**Authoritative**:
- `docs/specs/overlays/rating-spread.md` (§4 algorithm + §6 edge cases + §8 schema)
- `docs/adr/ADR-0010-tier-scope-lock.md` (T1 ONLY enforcement)
- `docs/specs/conventions/patterns.md` Pattern 4 (aggregator-primary + native-override)
- `src/sonar/overlays/rating_spread_backfill.py` (Sprint 4 backfill orchestrator)
- `src/sonar/cli/backfill.py` (`rating-spread` command)
- `docs/planning/retrospectives/week11-sprint-4-l2-rating-spread-te-report.md` (Sprint 4 retro template)
- Sprint 4 commit `f2cc4ef` + patch `faa73d2` + spec sync `82f5f52`

**Pre-flight HALT #0 requirement** (mandatory Commit 1):

CC reads end-to-end:
1. rating-spread.md §4 (consolidation formula `median(notch_adjusted_i)` over `[-1.0, 22.0]`) + §6 (edge cases) + §8 (schema)
2. Sprint 4 retrospective (TE country name mapping + invalid token handling pattern)
3. `rating_spread_backfill.py` `backfill_consolidate()` + `_te_country_to_iso` mapper
4. Existing `_DEFAULT_COHORT` constant (Sprint 4 cohort list) — extend or override via `--countries` flag

**TE country name mapping pre-validation** per country:
- NL = "netherlands"
- NZ = "new zealand"
- CH = "switzerland"
- SE = "sweden"
- NO = "norway"

**TE quota pre-check**: report current consumption vs 5000/mo cap before Commit 1. Sprint 5B baseline ~40-41%; Sprint 6 estimated 1 call snapshot (cached, returns all 160 países) + 5 calls historical = ~5-6 calls (negligible).

**Schema validation**: confirm migration 019 applied (head = 019). NL+NZ+CH+SE+NO consolidated values may include single-agency edge cases similar to JP — ck_rc_notch `[-1.0, 22.0]` already accommodates.

---

## 3. Concurrency

**Single CC sequential** — no worktree split. Sprint 4 pattern.

**File-level isolation**: not applicable (single CC).

**Migration numbers**: NONE expected (data-only sprint; 019 head accommodates).

---

## 4. Commits

Target ~5-7 commits:

1. **Pre-flight audit** — spec reads + TE quota + cohort confirmation + plan
2. **Backfill execution** — `uv run sonar backfill rating-spread --countries "NL,NZ,CH,SE,NO" --include-historical` + Tier B SQL outputs
3. **country_tiers.yaml** — add `rating_spread_live: true` flag for 5 países (verify existing flag schema first)
4. **Spec country scope §** — `docs/specs/overlays/rating-spread.md` country scope appendix update (cohort 10 → 15)
5. **CAL closure** — `docs/backlog/calibration-tasks.md` close `CAL-RATING-COHORT-EXPANSION` with cohort delta + row counts
6. **Retrospective** — `docs/planning/retrospectives/week11-sprint-6-l2-rating-spread-cohort-expansion-report.md`

Commit body checklist enforceable per backfill commit:
- TE country mapping verification (5/5 confirmed)
- Agency raw rows persisted per country
- Consolidated rows persisted per country
- Invalid token count per country (Sprint 4 saw 5 invalid; expected similar low-volume)
- TE quota delta

---

## 5. HALT triggers (atomic)

0. **Pre-flight HALT #0 fail** — TE country name mapping fails for 1+ países (no `/ratings/{country}` returns) → HALT, document, defer per-country to follow-up
1. **TE quota >70% mid-sprint** → HALT
2. **TE invalid token** (Sprint 4 pattern) — log + skip + flag `TE_TOKEN_DEGRADED`; not a HALT
3. **CHECK constraint failure** post-consolidate (regression migration 019) → HALT critical, immediate diagnosis
4. **Consolidated rows < 40 total for 5 países** (Sprint 4 saw 466 for 10 = ~46/país avg; expectation ≥30/país) → HALT, investigate TE historical depth per país
5. **Coverage regression > 3pp** in tests → HALT (no `--no-verify`)
6. **Pre-push gate fail** (ruff format/check + mypy + pytest -m "not slow") → fix, no `--no-verify`

**HALT discipline**: standard discipline — single-país HALT-0 acceptable + ship rest; 2+ países HALT-0 sprint-wide pause.

---

## 6. Acceptance

**Per país**:
- [ ] TE `/ratings/{country}` snapshot returned ≥1 row
- [ ] TE `/ratings/historical/{country}` archive returned ≥10 actions
- [ ] Agency raw rows persisted (≥30 expected per Sprint 4 baseline)
- [ ] Consolidated rows persisted (`backfill_consolidate` skip-existing logic)
- [ ] No CHECK constraint failures
- [ ] country_tiers.yaml flag updated

**Sprint-end Tier B targets**:
- [ ] `ratings_agency_raw` ≥ 660 rows total (Sprint 4 baseline 491 + ~170-190 expected from 5 países)
- [ ] `ratings_consolidated` ≥ 580 rows total (Sprint 4 baseline 466 + ~120-150 expected)
- [ ] `n_countries` distinct in `ratings_agency_raw` = 15
- [ ] 4 agencies still presentes (SP/MOODYS/FITCH/DBRS)
- [ ] `consolidated_sonar_notch` range within `[-1.0, 22.0]`
- [ ] All 5 new países represented in consolidated table
- [ ] CAL-RATING-COHORT-EXPANSION closed
- [ ] No `--no-verify`
- [ ] Pre-push gate green every push

---

## 7. Report-back artifact

Path: `docs/planning/retrospectives/week11-sprint-6-l2-rating-spread-cohort-expansion-report.md`

Structure:
- Sprint metadata (CC duration, commits)
- Cohort delta table (10 → 15 países)
- TE per-country: snapshot rows + historical actions + invalid tokens
- Tier B SQL output verbatim
- TE quota consumption delta
- HALT-0 reasons per país (if any)
- CAL closures + new CALs filed (CAL-RATING-DK-PHASE5 candidate per
  amendment 2026-04-26; any pattern-driven CALs)
- Pattern observations vs Sprint 4 baseline (consistency check TE behaviour 5 sparse markets)

---

## 8. Notes on implementation

- Sprint 4 CLI `--countries` flag accepts comma-separated ISO α-2 codes; default is `_DEFAULT_COHORT` 10 países; explicit `--countries "NL,NZ,CH,SE,NO"` overrides cohort
- `--include-historical` mandatory para depth (Sprint 4 baseline 96 actions PT, 74 IT, 73 ES; expect similar variance across 5 sparse)
- `_te_country_to_iso` mapper já implementado Sprint 4 — verify 5 países handled OR add mapping if not
- Sprint 4 lesson: TE invalid token edge case (whitespace ' Aa1', truncated 'Aa', 'A') = 5 across 10 países = ~0.5%; expect similar low rate 5 países
- Sustainable pacing: target sprint complete same-day, ~2-3h wall-clock single CC
