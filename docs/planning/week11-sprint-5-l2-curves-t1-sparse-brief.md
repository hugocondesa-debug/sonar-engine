# Sprint 5 — T1 sparse curves cohort via TE Path 1 (CAL-CURVES-T1-SPARSE-PROBES)

**Tier scope**: T1 ONLY per ADR-0010 (6 countries, sparse cohort).
**Pattern reference**: ADR-0009 v2 — TE Path 1 mandatory pre-flight; national CB only post-TE-exhaustion.
**Predecessor success**: Sprint H/I Week 10 — IT/ES/FR via TE cascade (3 countries, RMSE 2.005bps best).

---

## 1. Scope

**In**:
- Probe + ship NSS curves for 6 T1 sparse countries via TE Path 1
- 2 paralelo CCs hybrid:
  - **5A APAC**: AU + NZ (2 countries, single CC)
  - **5B Europa Nórdica/Alpina**: CH + SE + NO + DK (4 countries, single CC)
- Per-country: TE generic indicator API probe → tenor coverage assessment → NSS fit if ≥4 tenors → daily pipeline integration
- Connector cassettes + live canaries per country
- Backfill ≥30d historical per country shipped (post-merge)
- Update `country_tiers.yaml` curves coverage flags + `docs/specs/overlays/nss-curves.md` country scope appendix

**Out**:
- National CB connectors (RBA/RBNZ/SNB/Riksbank/Norges Bank/Nationalbanken) — defer to follow-up sprints if TE insufficient
- Forward curves derivation (CAL separate)
- L3 M3 expansion (depends curves coverage; separate Sprint candidate)
- EA periphery (PT/NL — separate Sprint per Week 10 backlog)

---

## 2. Spec reference + pre-flight

**Authoritative**:
- `docs/specs/overlays/nss-curves.md` (NSS methodology + country scope §)
- `docs/adr/ADR-0009-curves-probe-discipline.md` v2 (TE Path 1 canonical)
- `docs/adr/ADR-0010-tier-scope-lock.md` (T1 ONLY enforcement)
- `docs/specs/conventions/patterns.md` Pattern 4 (aggregator-primary)
- `src/sonar/connectors/te.py` (TE generic indicator endpoint, Sprint H/I patterns)
- `src/sonar/overlays/nss_curves_backfill.py` (existing backfill orchestrator)
- `docs/planning/retrospectives/week10-sprint-h-curves-it-es-bdi-bde-report.md` (TE cascade success template)
- `docs/planning/retrospectives/week10-sprint-i-curves-fr-bdf-report.md` (TE cascade reference)

**Pre-flight HALT #0 requirement** (mandatory Commit 1):

CC reads end-to-end:
1. nss-curves.md §2 (inputs) + §3 (outputs) + §4 (algorithm) + §6 (edge cases) + §10 (country scope)
2. ADR-0009 v2 full (probe matrix + Path 1 canonical structure)
3. Sprint H/I retrospectives (TE cascade pattern — country name mapping, tenor extraction, RMSE thresholds)
4. te.py existing TE generic indicator method signatures (Sprint H additions)
5. nss_curves_backfill.py existing CLI + per-country flow

**TE Path 1 probe matrix mandatory** per country:
1. TE generic indicator API: search "{country} government bond yield {tenor}Y" for tenors 2/3/5/7/10/20/30Y
2. Document tenor coverage matrix (which tenors return data, which empty)
3. RMSE acceptance: NSS fit ≤ 5bps consensus (Sprint H/I cohort: 2-4bps)
4. If <4 tenors return data → HALT-0 with country-specific deferral note

**TE quota pre-check**: report current consumption vs 5000/mo cap before Commit 1.

---

## 3. Concurrency — Hybrid 2 paralelos

**Worktree 5A**: `/home/macro/projects/sonar-wt-curves-apac` — branch `sprint-curves-t1-apac` (AU + NZ)
**Worktree 5B**: `/home/macro/projects/sonar-wt-curves-europe-sparse` — branch `sprint-curves-t1-europe-sparse` (CH + SE + NO + DK)

**File-level isolation**:
- te.py: each CC appends to its country block (alphabetical within group: AU before NZ; CH before DK before NO before SE)
- nss_curves_backfill.py: per-country dispatch via cohort flag (existing pattern — Sprint H/I precedent)
- country_tiers.yaml: bookmark zones — 5A edits AU/NZ rows, 5B edits CH/DK/NO/SE rows
- Migration numbers: NONE expected (no schema change; data-only sprint)

**Pre-flight sanity (Commit 1 each CC)**:
- ORM imports clean: `from sonar.connectors.te import TEConnector`
- yaml country block locations identified (line ranges)
- te.py append zone identified (post-existing FR block per Sprint I)

**Merge order post-completion**:
1. 5A APAC ships first (smaller scope, faster) → merge → main update
2. 5B rebases onto updated main → merge

`sprint_merge.sh` 10-step atomic per group.

---

## 4. Commits per CC

**5A (AU + NZ, ~4 commits)**:
1. Pre-flight audit (probe matrix + spec reads + TE quota report)
2. AU connector + cassette + live canary + NSS fit RMSE report
3. NZ connector + cassette + live canary + NSS fit RMSE report
4. Pipeline + backfill + country_tiers.yaml + spec country scope §

**5B (CH + SE + NO + DK, ~6 commits)**:
1. Pre-flight audit (probe matrix 4 countries + spec reads + TE quota report)
2. CH connector + cassette + live canary + RMSE
3. SE connector + cassette + live canary + RMSE
4. NO connector + cassette + live canary + RMSE
5. DK connector + cassette + live canary + RMSE
6. Pipeline + backfill + country_tiers.yaml + spec country scope §

**Commit body checklist enforceable** per country commit:
- TE tenor coverage table
- NSS fit RMSE bps
- Cassette path
- Live canary pass/fail
- Country tier flag updated

---

## 5. HALT triggers (atomic)

0. **Pre-flight HALT #0 fail** — TE Path 1 probe returns <4 tenors per country → document HALT-0 reason + national CB candidate annotation. Per Liberal discipline (Hugo decision): **continue cohort**; cap 2 HALT-0 across both groups before sprint-wide pause.
1. **TE quota >70% consumption** mid-sprint → HALT, report quota state, await Hugo decision.
2. **TE invalid token / schema drift** (Sprint 4 pattern) — log + skip + flag `TE_TOKEN_DEGRADED`; not a HALT.
3. **NSS fit RMSE > 5bps** post-probe → HALT-0 country-specific; document tenor sparsity; deferral.
4. **Coverage regression > 3pp** in tests → HALT (no `--no-verify`).
5. **Pre-push gate fail** (ruff format/check/mypy/pytest) → fix, no `--no-verify`.
6. **Concurrent file conflict** between 5A + 5B (te.py / yaml) → CC delegation rebase per ADR-0009/Week 10 precedent.

**Liberal HALT discipline cap**: ≤2 HALT-0 across cohort = continue + ship rest; ≥3 = sprint-wide HALT, formalize ADR-0009 v3 amendment if systemic TE issue.

---

## 6. Acceptance

**Per country**:
- [ ] TE probe matrix documented (tenors covered)
- [ ] NSS fit RMSE ≤ 5bps (Sprint H/I cohort 2-4bps)
- [ ] Cassette + live canary green
- [ ] country_tiers.yaml flag updated (`curves_live: true`)
- [ ] daily-curves pipeline includes country (post-merge fire)

**Sprint-end**:
- [ ] T1 curves coverage 9/16 → 13-15/16 depending on HALT-0 count
- [ ] 4-6 countries shipped clean (target 6, acceptable ≥4 per Liberal)
- [ ] `docs/specs/overlays/nss-curves.md` country scope § updated
- [ ] CAL-CURVES-T1-SPARSE-PROBES closed in `docs/backlog/calibration-tasks.md` (or partial close if HALT-0 countries deferred)
- [ ] Sprint 5 retrospective shipped: `docs/planning/retrospectives/week11-sprint-5-l2-curves-t1-sparse-report.md`
- [ ] TE quota delta reported in retro
- [ ] No `--no-verify`
- [ ] Pre-push gate green every push

---

## 7. Report-back artifact

Path: `docs/planning/retrospectives/week11-sprint-5-l2-curves-t1-sparse-report.md`

Structure:
- Sprint metadata (CC group, duration, commits per group)
- TE probe matrix per country (6 rows)
- NSS RMSE table per country
- HALT-0 reasons per country (if any)
- TE quota consumption delta
- Connector cassettes inventory
- Live canary results
- CAL closures + new CALs filed
- Pattern observations (TE behaviour sparse markets vs IT/ES/FR mid-Q EA periphery)

---

## 8. Notes on implementation

- TE country name strings: AU="australia", NZ="new zealand", CH="switzerland", SE="sweden", NO="norway", DK="denmark"
- Sprint H/I established: TE generic indicator handles 2-30Y tenors via `te:get_indicator_data(country, indicator)`; tenor mapped via indicator name string
- Liberal HALT permits partial cohort ship — retro must table which countries HALT-0'd for Phase 2.5+ national CB sprint candidates
- ADR-0009 v3 amendment trigger: ≥3 HALT-0 across cohort suggests systemic sparse-market TE limit; Hugo decision post-sprint
- Sustainable pacing: target sprint complete same-day (5A ~3h, 5B ~5h sequential, hybrid ~5h wall-clock)
