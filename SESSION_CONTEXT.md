# SESSION_CONTEXT — Week 9 close snapshot (in-repo proposal)

> **Scope note** — CLAUDE.md §8 declares the canonical `SESSION_CONTEXT.md`
> external to this repo (lives in the claude.ai project). Sprint
> Z-WEEK9-RETRO (brief §4 Commit 4) requested an in-repo update. This
> file is the **Week 9 close-state proposal** drafted in-repo so Hugo
> can merge it against the external authoritative copy at his
> discretion. Prior-week sections are intentionally not reproduced here
> — the retro artefact
> (`docs/planning/retrospectives/week9-retrospective.md`) is the
> canonical in-repo source of truth for Week 9 content.

## Phase 1 progress snapshot — 2026-04-22 (Week 9 close)

**Milestone** — **M2 T1 COMPLETE (projected)**: 12 countries monetary
M1 live at Week 9 close *pre*-Sprint-Y-DK (7 EA-periphery + GB + JP +
CA + AU + NZ + CH + SE + NO). Sprint Y-DK adds a 13th (or 16th if the
EA-periphery path is counted explicitly) post-merge.

Component status (post Week 9 Sprint X-NO close, pre Sprint Y-DK):

- **L0 connectors** — 22+ operational, **+6 native-CB this week**:
  BoC Valet (CA, JSON REST), RBA F-tables (AU, static CSV), RBNZ B2
  scaffold (NZ, perimeter-blocked), SNB data-portal (CH,
  semicolon-CSV), Riksbank Swea (SE, JSON REST), Norges Bank DataAPI
  (NO, SDMX-JSON). Nationalbanken (DK) pending Sprint Y-DK.
- **L1 persistence** — 16 migrations; SQLite MVP.
- **L2 overlays** — 5/5 live (NSS, ERP US, CRP, rating-spread v0.2,
  expinf) + ISO-3166 canonicalisation complete on overlay consumer
  surfaces (Sprint P). Alias surfaces scheduled for removal Week 10
  Day 1 per ADR-0007.
- **L3 indices** — 16/16 compute + DB-backed readers; Week 9
  monetary expansion adds M1 cascade for 6 new countries (CA, AU,
  NZ, CH, SE, NO); DK pending. M2 + M4 ship as wire-ready scaffolds
  per country (raise `InsufficientDataError` until the per-country
  CAL-*-GAP / CAL-*-M4-FCI / CAL-*-CPI / CAL-*-INFL-FORECAST items
  close).
- **L4 cycles** — 4/4 live (CCCS + FCS + MSC + ECS).
- **L5 regimes** — scaffold + classifier + CLI wiring shipped Week 8
  (Sprint H + K); overlay / cycle composite integration Phase 2+.
- **L6 integration** — ERP composition live.
- **L7 outputs** — Phase 2+.
- **L8 pipelines** — 9 daily pipelines operational; systemd timers
  enabled early Week 9; see "Production deployment state" below.
- **CLI** — `sonar status` + `sonar health` + `sonar retention` live
  (shipped Week 7 Sprint G).

Cobertura: US primário + GB + JP + CA + AU + NZ + CH + SE + NO + DE/PT/IT/ES/FR/NL
partial via Eurostat + ECB SDW + BIS. DK pending Sprint Y-DK.

## Production deployment state — first natural-fire observations

Week 8 Sprint N wired the nine daily pipelines to systemd
(`deploy/systemd/`); operator enabled early Week 9. First live cascade
cycle fired from Day 2 onward. Two latent issues surfaced via the
timers (not via mocked tests):

1. **BIS credit-indices silent outage** — `DEFAULT_LOOKBACK_DAYS=90`
   vs BIS ~2-quarter publication lag. Resolved Sprint AA (Day 2) with
   lookback bump to 540d. Weekly live canary opened as CAL-137.
2. **`daily_curves` US-only scope** — Service attempted `--all-t1`
   unsupported by the CLI; pipeline reverted safe to US-only.
   Discovered Day 4 07:00 WEST. CAL-138 opened HIGH; Week 10 P1.

Systemd-driven live canary is now the only true end-to-end gate.
Mocked tests stayed green through both outages.

## Outstanding backlog — Week 10 priorities

Canonical list (per week9-retrospective.md §8):

1. **P1 — CAL-138**: `daily_curves` multi-country (HIGH). Unblocks
   overlay + cost-of-capital for 6 T1 countries.
2. **P2 — ADR-0007 alias removal** (Week 10 Day 1). Strip
   `_DEPRECATED_COUNTRY_ALIASES` + `_normalize_country_code()` across
   Sprint O + P + chore surfaces.
3. **P3 — CAL-060 BIS L4 DSR + CAL-059 Credit Impulse L3** (MEDIUM).
4. **P4 — CAL-KRIPPNER** shadow-rate connector (MEDIUM). Unblocks M1
   compute at ZLB for CH + SE + DK.
5. **P5 — F-cycle canary backfill** (CAL-071 OPEN).
6. **P6 — L5 regime-classifier full integration** (Week 10-11 cand.).

Phase 2+ deferred: Postgres migration, Krippner / full-HLW r* work
(CAL-095 / CAL-099), systemd-driven live canary timer for BIS
(CAL-137), UK tier integration test coverage, L7 dashboards / PDFs.

## CAL balance (Week 9 close)

- Week 7 close (Phase 1 M1-US milestone): 62
- Week 8 close: 74 (+12)
- Week 9 close (pre-Y-DK): **120** (+46)
- Week 9 close (projected post-Y-DK): ~127 (+53)

Week 9 full closures: **CAL-128**, **CAL-128-FOLLOWUP**, **CAL-136**.
Partial closures at M1 level: CAL-129 (CA), CAL-AU, CAL-NZ, CAL-CH,
CAL-SE, CAL-NO; CAL-DK projected post-Y-DK.

New this week: ~46 sub-CALs (6-7 per country × 6 countries) + CAL-137
(BIS weekly canary) + CAL-138 (daily_curves multi-country).

## Log de sessões — Week 9 summary entry (prose)

Week 9 closed the advanced-economy monetary M1 arc in five days: six
native-CB connectors + BIS SDMX v2 migration fix + UK→GB overlay/cycle
sweep + first production natural-fire cycle since Week 8 Sprint N.
Eight isolated worktrees ran in parallel with zero filesystem
collisions; three rebase incidents traced uniformly to bundled
merge-and-cleanup shell scripts (lesson captured — merge and cleanup
are separate verbs). TE-primary cascade held across every country
expansion without structural deviation; the flag vocabulary grew by
one new axis (post-resolution value-attached augmentation for
negative-rate eras). Cascade native-reachability reached 5/9 by week
close (GB / JP gated, CA / AU / SE / NO success, NZ blocked, CH
partial, DK pending).

Two production fires: BIS lookback-vs-publication-lag (7-day silent
outage, Sprint AA ~2h resolution); `daily_curves` US-only from Week 2
scope (Sprint X-NO Day 4 discovery, CAL-138 Week 10 P1). Mean-time-to-
detect on the BIS fire was operator triage, not automation — CAL-137
closes that gap.

Full day-by-day + pattern matrices + lessons:
`docs/planning/retrospectives/week9-retrospective.md`.

## Preserve from prior weeks

Sections from Week 7 / Week 8 / prior phases in the canonical external
SESSION_CONTEXT.md should be preserved intact — this file only
touches the Week 9 snapshot, production deployment state, Week 10
priorities refresh, CAL balance, and the Week 9 log entry. No other
content proposed.
