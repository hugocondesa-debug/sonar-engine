# Retrospectives — index

Report-back artifacts produced at the close of each execution brief.
Each report follows the brief's §Report-back structure: summary,
commits, coverage delta, validation outcomes, deviations, new
backlog items, blockers for next work.

Sorted newest-first within each phase.

## Phase 1 — Week 9 — Completionist M2 T1 Arc

| File | Phase / Week | Summary | Date |
|---|---|---|---|
| [`week9-retrospective.md`](./week9-retrospective.md) | Phase 1 — Week 9 exhaustive synthesis | Meta-retro: 9 sprints (P + S-CA + AA + T-AU + U-NZ + V-CH + W-SE + X-NO + Y-DK) + 50+ commits + CAL evolution (74 → ~120) + production deployment first-fires. Day-by-day breakdown, 3 pattern matrices, 8 lessons, Week 10+ priorities. M2 T1 progression 8 → 12 countries monetary M1 live (projected 13 post-Y-DK, or 16 incl. EA-periphery). | 2026-04-22 |
| [`week9-sprint-x-no-connector-report.md`](./week9-sprint-x-no-connector-report.md) | Phase 1 — Week 9 Sprint X-NO (parallel to Sprint W-SE) | 6 commits delivering Norges Bank DataAPI SDMX-JSON connector + M1 NO cascade. First SDMX-JSON native; first fully-positive country across full history; YAML 1.1 `NO` bareword gotcha documented. | 2026-04-22 |
| [`week9-sprint-w-se-connector-report.md`](./week9-sprint-w-se-connector-report.md) | Phase 1 — Week 9 Sprint W-SE (parallel to Sprint X-NO) | 6 commits delivering Riksbank Swea JSON REST connector + M1 SE cascade. Second negative-rate country (-0.50% floor, 58 obs); first daily-cadence native secondary; FRED OECD SE mirror discontinued 2020-10-01. | 2026-04-22 |
| [`week9-sprint-v-ch-connector-report.md`](./week9-sprint-v-ch-connector-report.md) | Phase 1 — Week 9 Sprint V-CH (parallel to Sprint U-NZ) | 6 commits delivering SNB data-portal semicolon-CSV connector + M1 CH cascade. First negative-rate country (-0.75% floor, 93 obs); SNB has no dedicated policy-rate cube (SARON proxy); ZLB compute gap surfaced (Krippner Phase 2+). | 2026-04-21 |
| [`week9-sprint-u-nz-connector-report.md`](./week9-sprint-u-nz-connector-report.md) | Phase 1 — Week 9 Sprint U-NZ (parallel to Sprint V-CH) | 6 commits delivering RBNZ B2 CSV connector scaffold + M1 NZ cascade. First perimeter-blocked native (host/IP 403 on every path + every UA); CAL-NZ-RBNZ-TABLES tracks operator remediation. | 2026-04-21 |
| [`week9-sprint-t-au-connector-report.md`](./week9-sprint-t-au-connector-report.md) | Phase 1 — Week 9 Sprint T-AU (parallel to Sprint AA) | 6 commits delivering RBA F1/F2 statistical-tables CSV connector + M1 AU cascade. First CSV-shaped native; Akamai-edge UA gate (`Mozilla/5.0` 403, `SONAR/2.0` clears). | 2026-04-21 |
| [`week9-sprint-aa-bis-v2-migration-report.md`](./week9-sprint-aa-bis-v2-migration-report.md) | Phase 1 — Week 9 Sprint AA BIS v2 fix (production-fire response) | 6 commits resolving BIS credit-indices outage. URL migration already landed Week 8 `7abded7`; real blocker was `DEFAULT_LOOKBACK_DAYS=90` vs 2-quarter publication lag → 540. CAL-136 CLOSED; CAL-137 OPEN (weekly canary). | 2026-04-21 |
| [`week9-sprint-s-ca-connector-report.md`](./week9-sprint-s-ca-connector-report.md) | Phase 1 — Week 9 Sprint S-CA (parallel to Sprint P) | 6 commits delivering BoC Valet public JSON REST connector + M1 CA cascade. First reachable native in the cascade family; net side-fix of JP FRED-fallback (`FRED_SERIES_TENORS` missing entries). | 2026-04-21 |
| [`week9-sprint-p-cal-128-followup-report.md`](./week9-sprint-p-cal-128-followup-report.md) | Phase 1 — Week 9 Sprint P CAL-128-FOLLOWUP (parallel to Sprint S-CA) | 6 commits delivering strict 4-file overlay/cycle/cost-of-capital UK→GB canonical sweep. `_DEPRECATED_COUNTRY_ALIASES` + `_normalize_country_code()` with structlog warnings; alias removal scheduled Week 10 Day 1 per ADR-0007. | 2026-04-21 |

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
