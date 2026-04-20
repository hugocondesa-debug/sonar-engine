# Retrospectives — index

Report-back artifacts produced at the close of each execution brief.
Each report follows the brief's §Report-back structure: summary,
commits, coverage delta, validation outcomes, deviations, new
backlog items, blockers for next work.

Sorted newest-first within each phase.

## Phase 1 — Week 6

| File | Phase / Week | Summary | Date |
|---|---|---|---|
| [`week6-sprint-1b-msc-indices-report.md`](./week6-sprint-1b-msc-indices-report.md) | Phase 1 — Week 6 Sprint 1b MSC monetary indices (parallel to TE extension) | 4 commits delivering M1 / M2 / M4 compute layers per spec §4 + ORMs + migration 014 + r* and CB-targets YAML loaders. Connectors descoped to CAL-095..100 follow-ups. Brief 10-13 commits trimmed to 4 per established Week 5 ECS / Sprint 2b pattern. | 2026-04-20 |

## Phase 1 — Week 5

| File | Phase / Week | Summary | Date |
|---|---|---|---|
| [`week5-sprint-2b-cccs-fcs-report.md`](./week5-sprint-2b-cccs-fcs-report.md) | Phase 1 — Week 5 Sprint 2b CCCS + FCS composites (parallel to Sprint 2a) | 7 commits delivering CCCS + FCS L4 cycle composites per spec §4 + Policy 1 fail-mode helper + migration 013. Hysteresis + boom overlay + tier-conditional Policy 4 shipped. Pre-flight HALT #0 fired + reconciled (Option B spec-authoritative). | 2026-04-20 |
| [`week5-ecs-indices-report.md`](./week5-ecs-indices-report.md) | Phase 1 — Week 5 ECS (parallel to Sprint 1 F-cycle) | 5 commits delivering E1 Activity + E3 Labor + E4 Sentiment compute layers per spec §4 + ORM + migration 012. Connector commits descoped to CAL-080..090 per user §7 pre-auth trim. Pre-flight HALT #0 fired + reconciled. | 2026-04-20 |

## Phase 1 — Week 3.5

| File | Phase / Week | Summary | Date |
|---|---|---|---|
| [`cal-058-bis-ingestion-report.md`](./cal-058-bis-ingestion-report.md) | Phase 1 — CAL-058 BIS ingestion brief (post-credit-track) | 6 commits delivering `bis_credit_raw` ORM + migration 011 + daily ingestion pipeline + `DbBackedInputsBuilder` (L1+L2). Parallel track to F-cycle. Closes CAL-058; surfaces CAL-059/060/061. | 2026-04-20 |
| [`erp-us-implementation-report.md`](./erp-us-implementation-report.md) | Phase 1 — ERP US brief (post-Week-3.5) | 8 commits delivering ERP 4-method compute + 6 connectors + persistence + pipeline wiring; US `k_e` stub → computed (−228 bps). Closes CAL-048. | 2026-04-20 |
| [`l3-indices-implementation-report.md`](./l3-indices-implementation-report.md) | Phase 1 — L3 indices brief (post-Week-3.5) | L3 scaffolding + migration 008 + E2 Leading slope subset + M3 anchor subset + orchestrator. Parallel track to ERP US brief; surfaces CAL-051..055. | 2026-04-20 |
| [`week3-5-sprint-final-report.md`](./week3-5-sprint-final-report.md) | Phase 1 — Week 3.5 | Final consolidated report. 3 of 6 sub-sprints delivered (3.5A, 3.5C, 3.5F); 3.5B/D/E deferred to CAL-048/049/050. | 2026-04-20 |
| [`week3-5-sprint-F-report.md`](./week3-5-sprint-F-report.md) | Phase 1 — Week 3.5F | Daily cost-of-capital L6 pipeline skeleton; 5.5 % Damodaran ERP stub. Closes CAL-047. | 2026-04-20 |
| [`week3-5-sprint-C-report.md`](./week3-5-sprint-C-report.md) | Phase 1 — Week 3.5C | CRP country-specific `vol_ratio` from equity + bond histories; Damodaran 1.5 fallback when out of bounds. | 2026-04-20 |
| [`week3-5-sprint-A-report.md`](./week3-5-sprint-A-report.md) | Phase 1 — Week 3.5A | Connectors foundation for the Week 3.5 consumer overlays. | 2026-04-20 |
| [`week3-5-spec-sweep-report.md`](./week3-5-spec-sweep-report.md) | Phase 1 — Week 3.5 pre-sprint | Spec sweep preparing CRP + ERP specs for the Week 3.5 sub-sprint set. | 2026-04-20 |

## Conventions

- Report filename: `<scope>-report.md` (or `<scope>-implementation-report.md` for multi-commit briefs).
- Place post-hoc reports here, not in the brief file itself — briefs are pre-execution plans, retrospectives are outcomes.
- New entries: add to the table above in reverse-chronological order within their phase grouping.
