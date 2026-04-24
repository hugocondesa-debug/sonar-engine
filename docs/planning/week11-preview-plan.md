# Week 11 Preview Plan

**Data**: 2026-04-24 (Week 11 Day 1 afternoon, integrating Sprint Q + Q.0.5 outcomes)
**Author**: Hugo Condesa
**Status**: OPERATIONAL — updated mid-Week 11 Day 1 after P0 unblocks shipped
**Supersedes**: Week 10 handoff §Week-11-preview, Day 3 late draft `week11-preview-plan-AA-draft.md`

---

## 1. Week 10 close state (final)

### Sprints shipped Week 10: 21

| Day | Sprints | Theme |
|---|---|---|
| Day 1 (Apr 21) | 6 | Infrastructure + CAL-138 + A/B/C/D |
| Day 2 (Apr 22) | 7 | E/F/G/H/L/I/J (TE cascade, M2/M4 expansion) |
| Day 3 (Apr 23) | 8 | T0/T0.1/R1/M/O/V/T/Z (prod healing + retros + coverage + methodology) |

### ADRs canonized Week 10: 5

- ADR-0009 v2.2 — TE Path 1 mandatory + S1/S2 classifier
- ADR-0010 — T1 complete before T2 scope lock
- ADR-0011 Principles 1-5 — Systemd idempotency + per-country isolation
- ADR-0011 Principle 6 — Async lifecycle (single asyncio.run + AsyncExitStack)
- ADR-0011 Principle 7 — Worktree data lifecycle (DB symlink canonical)

### Lessons ledger: 12 total

- 11 shipped permanent fix
- 1 pending operator decision (#13 watcher — **Option A disable + investigate decided**)
- 1 deferred Week 11+ (#8 CAL-TE-QUOTA-TELEMETRY)

### T1 coverage Week 10 close: ~57.5% (+25.5pp during Week 10)

---

## 2. Week 11 Day 1 status (ship in-progress)

### Shipped so far Day 1
- **Sprint Q** — CAL-EXPINF-LIVE-ASSEMBLER-WIRING (US M3 DEGRADED→FULL + 6 per-country CALs opened)
- **Sprint Q.0.5** — T1 cohort unification (12-country canonical, natural fire observability +71%)

### In progress Day 1 afternoon (paralelo)
- **Sprint Q.1** — CAL-EXPINF-EA-ECB-SPF (target 6-country M3 FULL cascade)
- **Sprint T-Retry** — Path 1 multi-prefix probe (target methodology gap closure + 0-3 S1 upgrades)

### Day 1 close projection
- 4 sprints shipped (Q + Q.0.5 + Q.1 + T-Retry)
- T1 runtime coverage jump: ~58% → ~68-72%
- Pattern library v2.3 codified (multi-prefix canonical)

---

## 3. Operator decisions confirmed

### Priority sequencing
**P0 Sprint Q sequence is correct first Day 1 (confirmed)**. Sprint T residuals handled via Sprint T-Retry paralelo methodology gap closure, not blocked to Week 12.

### E1 scope budget
**Confirmed "vamos com força"**. E1 10-14h target for PMI Composite + GDP proxies + Industrial Production. Monday-Tuesday Week 11 scope.

### Week 11 start time
**Day 4 (Apr 24) morning start confirmed**. Sprint Q brief produced Day 3 late night for Day 4 fresh arranque — executed as planned.

### CAL-WATCHER-DECISION
**Option A — Disable + investigate source**. Execution scope Week 11 Day 5 (R3 bundle alongside Lesson #8 TE quota telemetry + Lesson #16/#17/#18 micro-fixes from Week 10 Day 3 patterns).

### L4 MSC cross-country expansion
**M2-EA-per-country ship confirmed Week 11** (not deferred Phase 2+). Unlocks MSC DE/FR/IT/ES/NL sequencing post-Q.1 + post-M2-per-country shipping.

### M4 scaffold upgrade
**Week 11 scope confirmed** for GB/JP/CA scaffold → FULL builders.

---

## 4. Week 11 priority matrix

### P0 — Critical path (Day 1-2)

| Sprint | Day | Budget | Impact |
|---|---|---|---|
| Sprint Q ✅ shipped | Day 1 AM | 1h actual | US M3 FULL + wiring pattern canonical + 6 CALs opened |
| Sprint Q.0.5 ✅ shipped | Day 1 lunch | 30min actual | T1 cohort 12-country unified |
| Sprint Q.1 🏃 in-flight | Day 1 PM | 3-5h | 6-country EA cascade M3 FULL |
| Sprint P — MSC EA | Day 2 AM | 3-4h | L4 first cross-country composite (unblocked post-Q.1) |

### P1 — Phase 2 coverage expansion (Day 2-4)

| Sprint | Day | Budget | Impact |
|---|---|---|---|
| Sprint Q.2 — CAL-EXPINF-GB-BOE-ILG-SPF | Day 2 AM | 3-4h | GB M3 FULL |
| Sprint M2-EA-per-country | Day 2 PM | 6-10h (split 2 days if needed) | 5 EA members individual Taylor gaps (DE/FR/IT/ES/NL) |
| Sprint R — E1 activity T1 | Day 3-4 | 10-14h | PMI Composite + GDP + Industrial Production (6-8 countries) |
| Sprint S — E3 labor T1 | Day 4 PM | 8-12h | Unemployment + wages + participation |
| Sprint T2 — E4 sentiment T1 | Day 4 PM / Day 5 | 6-10h | Consumer confidence + business sentiment |

### P2 — Infrastructure hardening (Day 5)

| Sprint | Budget | Impact |
|---|---|---|
| Sprint M4-scaffold-upgrade GB/JP/CA | 6-8h | M4 FCI FULL for 3 non-EA T1 countries |
| Sprint R3 micro-bundle — watcher Option A + TE telemetry + Day 3 Lessons #16/17/18 | 2-3h | Lesson ledger closure Week 10 + Week 11 hardening |

### P3 — Opportunistic (Day 1 PM paralelo)

| Sprint | Budget | Impact |
|---|---|---|
| Sprint T-Retry 🏃 in-flight | 2-3h | 0-3 S1 upgrades (L2 curves +0-19pp) + ADR-0009 v2.3 codification |

### P4 — Deferred Week 12+

- Sprint Q.3 — CAL-EXPINF-SURVEY-JP-CA (JP Tankan + BoC survey — 2 countries M3 FULL)
- CAL-EXPINF-DE-BUNDESBANK-LINKER / FR-BDF-OATI-LINKER / EA-PERIPHERY-LINKERS (per-country BEI upgrade from AREA_PROXY if Q.1 ships proxy-only)
- Sprint U — NL DNB Path 2 probe (Sprint M HALT-0 residual)
- Residual sparse T1 S2 countries (Sprint T-Retry retro will confirm which need Path 2)

---

## 5. Week 11 sequence proposal (revised Day 1 afternoon)

### Day 1 (Monday Apr 24)
- ✅ AM: Sprint Q — CAL-EXPINF-LIVE-ASSEMBLER-WIRING
- ✅ Lunch: Sprint Q.0.5 — T1 cohort unification
- 🏃 PM (paralelo): Sprint Q.1 + Sprint T-Retry
- Evening: Day 1 close + AA committed

### Day 2 (Tuesday Apr 25)
- AM: Sprint Q.2 — CAL-EXPINF-GB-BOE-ILG-SPF + Sprint P — MSC EA (paralelo se scope clean)
- PM: Sprint M2-EA-per-country start

### Day 3 (Wednesday Apr 26)
- AM: Sprint M2-EA-per-country completion
- PM: Sprint R — E1 activity start (PMI Composite)

### Day 4 (Thursday Apr 27)
- AM: Sprint R continue (GDP + Industrial Production)
- PM: Sprint S — E3 labor start

### Day 5 (Friday Apr 28)
- AM: Sprint S completion + Sprint T2 — E4 sentiment
- PM: Sprint M4-scaffold-upgrade GB/JP/CA + R3 micro-bundle + Week 11 retro

### Week 11 close target (projection conservative)
- T1 overall: ~72-75% (if Q.1 ships 6-country cascade clean + E-layer partial)
- L4 MSC EA + potentially DE/FR/IT/ES shipped
- Phase 2 fim Maio 2026 (75-80%) target: **achievable Week 12 with buffer**

---

## 6. Risk matrix Week 11

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Sprint Q.1 SDW SPF dataflow unavailable via API | Medium | High — forces scrape-based fallback | HALT-0 documented, scrape CAL opened Week 11 Day 3+ |
| Sprint Q.1 AREA_PROXY ships (not per-country) | Medium-high | Medium — 6 countries FULL with PROXY flag acceptable | Per-country BEI upgrade Week 12 |
| E-layer connectors require brand-new integrations (PMI = S&P Global, surveys fragmented) | High | Medium — adds sprint scope | Pre-sprint audit Day 3 morning identifies connector needs |
| Sprint T-Retry confirms 0 S1 upgrades | Medium | Low — methodology gap closed empirically, still value | ADR-0009 v2.3 shipped, Path 2 cohort justified Week 12 |
| Week 11 velocity drop vs Week 10 | Medium | Medium | Day 2 PM review — recalibrate if Day 1-2 <40% expected throughput |
| Paralelo Q.1 + T-Retry conflict (theoretical) | Low | Medium | Zero file overlap verified pre-arranque; merge sequence T-Retry first (shorter) then Q.1 |

---

## 7. Lesson discipline Week 11

### Week 10 permanent fixes to validate empirically Week 11
- Lesson #1 brief pre-flight ✅ (Sprint Q + Q.0.5 + Q.1 + T-Retry all auto-staged)
- Lesson #2 pre-commit double-run ✅ (all Day 1 commits)
- Lesson #4 tmux cleanup ✅ (Sprint Q kill clean Day 1)
- Lesson #5 CC arranque template ✅ (all prompts reference)
- Lesson #11 no-empty-commits ✅ (validated hook fires every commit)
- Lesson #12 Tier A/B split ✅ (briefs v3.3 compliant)
- Lesson #14 DB symlink ✅ (setup output "DB symlinked" every time)
- Lesson #15 filename convention ✅ (all Week 11 briefs compliant)

### Week 11 new Lesson candidates
- **Lesson #16** — Pre-stage pre-commit before git add (Day 3 staged-uncommitted pattern) — partially shipped, fully canonical Week 11 R3
- **Lesson #17** — Systemd StartLimitBurst reset-failed convention — discovered Day 3 late, operator discipline Week 11
- **Lesson #18** — Cohort constants per-pipeline not cross-imported (Sprint Q.0.5 Discovery #1) — documentation only
- **Lesson #19** — Pytest unraisable warnings asyncio.run interaction (Sprint Q.0.5 discovery) — testing infrastructure note

---

## 8. Changelog

- **2026-04-23 23:30 WEST**: Initial draft Day 3 late (handoff §Week-11-preview Day 3 close)
- **2026-04-24 14:00 WEST**: Integrated Sprint Q + Q.0.5 outcomes, operator answers confirmed, Q.1 + T-Retry in-flight — **this version committed main**
- **2026-04-25 (Day 2)**: To be updated post-Sprint-Q.1 + T-Retry retros with M3 FULL matrix confirmed
- **Per Day**: Progressive update as sprints ship

---

*End of plan. Operational reference for Week 11 Day 1-5. Phase 2 fim Maio 2026 trajectory validated.*
