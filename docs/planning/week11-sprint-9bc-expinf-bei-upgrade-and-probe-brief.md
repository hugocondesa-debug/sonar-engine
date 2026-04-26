# Sprint 9BC — EXPINF BEI upgrade DE/FR/IT/ES + probe missing AU/NL/NZ/CH/SE/NO

**Tier scope**: T1 ONLY per ADR-0010.
**Pattern reference**: Sprint 4 (rating-spread cohort) + Sprint 7B (Path 2 probe). Sequential within-worktree (B → C).
**Predecessor context**: Sprint 9A audit (paralelo worktree) — empirical state confirmed 10/16 canonical, 6 missing, 4 BEI-spec/SURVEY-actual deviation.

---

## 1. Scope

**Track B — BEI native upgrade DE/FR/IT/ES (4 países)**:
- Empirical context: spec §3 lines 36-39 prescribe BEI-derived (Bundesbank ILB / AFT OATi / MEF BTP€i / Tesoro BEIi), reality is SURVEY fallback (5 rows each, ECB SPF probably)
- Investigate BEI source availability per país:
  - DE: Bundesbank ILB BEI series (real yield curve via existing bundesbank connector)
  - FR: AFT OATi BEI (TE Path 1 first per ADR-0009 v2 → AFT native if exhausted)
  - IT: MEF Italy BTP€i BEI (TE Path 1 first → MEF native if exhausted)
  - ES: Tesoro Spain BEIi (TE Path 1 first → Tesoro native if exhausted)
- Ship native BEI path for países where source available; flag as `BEI_DATA_UNAVAILABLE` for países where BEI genuinely thin
- Update `bei.py` + `canonical.py` to prefer BEI when available
- Backfill: `sonar backfill expinf-{country}-bei` CLI extension (Sprint 1.1 pattern)

**Track C — Probe missing países AU/NL/NZ/CH/SE/NO (6 países)**:
- TE Path 1 BEI/SWAP probe per país (literal first; full-flow listing only on fail per Hugo discipline)
- Adaptive probe matrix per país:
  1. TE literal: `{country} inflation linked bond yield {tenor}Y` for tenors 5/10
  2. TE literal: `{country} inflation swap rate {tenor}Y` for tenors 5/10
  3. If both 1+2 empty: full-flow listing GET TE indicator catalog + filter inflation*/breakeven*/swap*
- If BEI available: ship via existing `bei.py` extension
- If SWAP available: ship via existing `swap.py` extension
- If both unavailable: file `CAL-EXPINF-{country}-PATH-2` (Phase 2.5+ deferral, like NSS Path 2 cohort)

**Out**:
- Connector creation greenfield (boe_dmp / boj_tankan / RBA / RBNZ / SNB / Riksbank / Norges Bank EXPINF endpoints — separate sprint candidates if probe surfaces need)
- DERIVED expansion to non-PT países (separate sprint candidate)
- Calibration / methodology version bump
- M3 expansion (curves-derived; separate sprint)

---

## 2. Spec reference + pre-flight

**Authoritative**:
- `docs/specs/overlays/expected-inflation.md` (§3 paths verbatim + §6 edge cases)
- `docs/adr/ADR-0009-national-cb-connectors-ea-periphery.md` v2.3.1 (TE Path 1 + full-flow listing discipline)
- `src/sonar/overlays/expected_inflation/bei.py` + `swap.py` + `canonical.py` + `backfill.py`
- `src/sonar/connectors/te.py` (TE generic indicator method)
- `src/sonar/connectors/{bundesbank,aft_france,mef_italy,tesoro_spain}.py` (existing scaffolds — verify status)
- Sprint 9A audit findings (read once 9A ships in main; OR pre-flight reads matrix doc directly from worktree)

**Pre-flight HALT #0 requirement** (mandatory Commit 1):

CC reads end-to-end:
1. Sprint 9A audit matrix (sync with main if 9A merged; else read 9A worktree directly)
2. spec §3 BEI canonical paths per país DE/FR/IT/ES verbatim
3. ADR-0009 v2.3.1 multi-prefix probe discipline
4. Existing `bei.py` + `swap.py` source — identify extension points
5. Existing connector status DE/FR/IT/ES BEI source (Bundesbank ILB / AFT OATi / MEF BTP€i / Tesoro BEIi)

**TE quota pre-check**: report current consumption vs 5000/mo cap before Commit 1. Estimate Track C: 12-30 calls (6 países × 2-5 calls adaptive).

**Probe matrix Adaptive (Track C)**:
- Step 1: Literal TE indicator probe per país per path (BEI then SWAP) — 1-2 calls per país
- Step 2 (only if Step 1 empty): full-flow listing GET TE catalog → filter inflation/breakeven/swap by country — 1 call per país
- Cap 6 países × ~3 calls = ~18 calls (vs strict ADR-0009 v2.3.1 ~30-50)

---

## 3. Concurrency

**Sequential within worktree** `sonar-wt-9bc-expinf-bei-upgrade-and-probe`:
- Track B first (4 commits BEI upgrade DE/FR/IT/ES)
- Track C second (4-6 commits probe + ship/file CAL per país)

Single CC. Paralelo with 9A worktree (different files; no overlap).

**File-level isolation vs 9A**:
- 9BC writes: `src/sonar/overlays/expected_inflation/*.py` + `tests/unit/test_overlays/test_expected_inflation*.py` + `tests/cassettes/te/expinf_*.yaml` + `country_tiers.yaml` (expinf flags)
- 9BC does NOT edit: `docs/specs/overlays/expected-inflation.md` country scope (9A scope) — except spec amendment if BEI implementation reveals genuine spec deviation

**Track B → Track C transition**:
- B closes with commit "feat(expinf): BEI native upgrade DE/FR/IT/ES"
- C opens with new commit "docs(probes): EXPINF Path 1 probe AU/NL/NZ/CH/SE/NO"
- Same worktree, same branch, sequential commits

**Migration numbers**: NONE expected.

---

## 4. Commits

Target ~8-12 commits across Track B + Track C:

**Track B (BEI upgrade DE/FR/IT/ES, 4-6 commits)**:
1. **Pre-flight audit** — Track B specific: connector status verify + spec §3 read + plan
2. **BEI upgrade DE** — bei.py extension + connector wiring + tests + cassette + canonical rerun
3. **BEI upgrade FR** — same shape (TE Path 1 first per ADR-0009)
4. **BEI upgrade IT** — same shape
5. **BEI upgrade ES** — same shape
6. **Track B closure commit** — country_tiers.yaml flag updates DE/FR/IT/ES BEI live; spec §3 amendment if deviation surfaces

**Track C (probe 6 países, 4-6 commits)**:
7. **Probe AU+NL adaptive** (or alphabetical 6 países single commit if all HALT-0 quickly)
8. **Probe NZ+CH adaptive**
9. **Probe SE+NO adaptive**
10. **Track C closure** — per país: ship if 1+ path live OR file CAL-EXPINF-{country}-PATH-2 if both empty
11. **Sprint 9BC retrospective + SESSION_STATE.md update** — combined commit

Commit body checklist enforceable per Track B país:
- BEI source confirmed live (TE Path 1 OR native CB)
- Test cassette + live canary green
- Canonical recompute confirms BEI replaces SURVEY
- country_tiers.yaml flag updated

Per Track C país:
- Probe matrix verbatim
- Ship outcome (live/CAL filed)
- TE quota delta cumulative

---

## 5. HALT triggers (atomic)

0. **Pre-flight HALT #0 fail** — Sprint 9A audit not yet merged AND audit matrix not readable from 9A worktree → HALT (workaround: 9BC starts post 9A merge)
1. **Track B país BEI source genuinely thin** (TE empty + native CB connector unavailable) → flag country `BEI_DATA_UNAVAILABLE`, keep SURVEY canonical, document; not a HALT-0
2. **Track B BEI upgrade introduces canonical regression** (post-upgrade canonical rows fewer than pre-upgrade) → HALT, revert
3. **TE quota >70% mid-sprint** → HALT
4. **Track C probe HALT-0 ≥4/6 países** → cohort-wide HALT, escalate to dedicated EXPINF connector sprint Phase 2.5+
5. **Coverage regression > 3pp** → HALT, no `--no-verify`
6. **Pre-push gate fail** → fix, no `--no-verify`
7. **Concurrent file conflict with 9A** (e.g. spec amendment double-edit) → HALT, coordinate via Hugo

---

## 6. Acceptance

**Track B**:
- [ ] DE/FR/IT/ES: BEI native path shipped where source available; SURVEY preserved as fallback per spec §4 hierarchy
- [ ] Canonical recomputed for upgraded países; row counts maintained or improved
- [ ] Tests + cassettes per país
- [ ] country_tiers.yaml flags updated

**Track C**:
- [ ] AU/NL/NZ/CH/SE/NO: probe matrix documented per país
- [ ] Per país: shipped (BEI/SWAP/DERIVED) OR CAL filed (Path 2 deferral)
- [ ] TE quota delta reported

**Sprint-end**:
- [ ] EXPINF canonical coverage delta vs Sprint 9 baseline (pre: 10/16 → post: 10+X/16)
- [ ] No `--no-verify`
- [ ] Pre-commit 2x every commit
- [ ] Pre-push gate green every push
- [ ] Sprint 9BC retrospective shipped
- [ ] SESSION_STATE.md updated (EXPINF section)

---

## 7. Report-back artifact

Path: `docs/planning/retrospectives/week11-sprint-9bc-expinf-bei-upgrade-and-probe-report.md`

Structure:
- Sprint metadata (CC duration, commits, Tracks B+C breakdown)
- Track B: BEI upgrade outcomes per país (TE source / native CB / data-unavailable)
- Track C: probe matrix per país verbatim + outcome (ship / Path 2 deferral)
- TE quota delta
- HALT-0 reasons per país (if any)
- CAL closures + filings
- Pattern observations (spec compliance Sprint 4 rating-spread vs Sprint 9 EXPINF)

---

## 8. Notes on implementation

### Track B per país pattern (recycle Sprint 4 rating-spread orchestrator philosophy):
1. TE Path 1 first per ADR-0009 v2 (existing TE connector inflation indicator probe)
2. Native CB fallback (Bundesbank ILB / AFT OATi / MEF BTP€i / Tesoro BEIi) — only if TE empty
3. Existing connectors verify per país before extending

### Track C per país pattern (Sprint 7B Norges Bank precedent):
1. TE literal probe BEI tenor 5Y/10Y
2. TE literal probe SWAP tenor 5Y/10Y
3. If both empty: TE full-flow listing inflation/breakeven/swap filter
4. Ship via existing `bei.py` or `swap.py` if 1+ path live
5. File CAL-EXPINF-{country}-PATH-2 if all empty

### TE quota discipline
- Adaptive probe budget Track C: ~18 calls cap
- Track B: native CB fallback minimal TE burn (~5-10 calls)
- Total estimate Sprint 9BC: ~25-30 calls (~0.6% mensal)

### Sustainable pacing
- Track B: ~3-4h wall-clock
- Track C: ~2-3h wall-clock
- Total Sprint 9BC: ~5-7h single CC sequential
- Brief multi-day acceptable; CC may pause if energy budget exhausted

### SESSION_STATE.md update mandate
Per WORKFLOW.md (post Sprint A): retrospective commit updates `docs/SESSION_STATE.md` EXPINF section with new canonical coverage + new CAL filings + Path 2 cohort updates.
