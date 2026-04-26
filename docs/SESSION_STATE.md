# SESSION_STATE — SONAR Engine

*Auto-updated post-sprint per `governance/WORKFLOW.md` mandate.*
*Companion to claude.ai Project knowledge `SESSION_CONTEXT.md` (narrative / decisions).*
*Last updated: 2026-04-26T21:40Z by Sprint A (test-hygiene + SESSION_STATE.md hybrid governance).*

---

## Phase

- **Current**: Phase 2 T1 horizontal expansion
- **Completion estimate**: ~62-65 %
- **Target**: ~80-85 % T1 fim Maio 2026

## Last sprint shipped

- **ID**: Sprint A — test-hygiene + SESSION_STATE.md hybrid governance
- **Branch**: `sprint-a-test-hygiene-and-session-state`
- **SHA range**: `daa3e9d..` (HEAD ao fechar)
- **Outcome**: Issue 1 (`_seed_all` schema mismatch) fixed; Issue 2 NOT-REPRODUCIBLE post-fix; CAL-TEST-CYCLES-FIXTURE-FLAKE-AND-FAIL closed; SESSION_STATE.md infra shipped.

## Coverage by overlay / layer (T1 = 16 países canonical)

| Layer | T1 % | Countries live | Gaps |
|---|---|---|---|
| L0 connectors | ~95 % functional | 25+ | TE Path 1 + Path 2 emerging |
| L1 persistence | 100 % | head 019 | — |
| L2 NSS curves | 75 % | 12/16 | NL/NZ/CH/SE Path 2 deferred |
| L2 ERP | 100 % methodology | 1 native + 15 proxy | acceptable |
| L2 CRP | 75 % | 12/16 viável | follows NSS gap |
| L2 Rating-spread | 94 % | 15/16 | DK Phase 5+ |
| L2 EXPINF | unaudited | 4/16 confirmed | CAL-EXPINF-T1-AUDIT |
| L3 M1 | 100 % | 16/16 | — |
| L3 M2 | 69 % | 11/16 FULL | EA per-country pending |
| L3 M3 | 25 % | 4/16 | curves-derived expansion |
| L3 M4 | 47 % FULL | 8/17 | SCAFFOLD upgrade pending |
| L3 Credit/Financial | shipped Week 4 | 4+4 | — |
| L3 E1/E3/E4 | 0 % | 0/16 each | from-zero pending |
| L4 cycles | 6 % cross-country | US only | 15 países pending each |

## Path 2 cohort (Phase 2.5+ deferred)

- NL — CAL-CURVES-NL-DNB-PROBE
- NZ — CAL-CURVES-NZ-PATH-2
- CH — CAL-CURVES-CH-PATH-2
- SE — CAL-CURVES-SE-PATH-2

## Active high-priority CALs

- CAL-EXPINF-T1-AUDIT (filed 2026-04-26)
- CAL-RATING-DK-PHASE5 (Phase 5+ candidate)
- CAL-RATING-COHORT-TARGET-CALIBRATION (low priority)

## Test infrastructure

- Pre-push gate: green for Issue 1 + Issue 2 targets post Sprint A
- `test_us_smoke_end_to_end`: PASS isolated + 5x consecutive full-suite
- `test_us_full_stack`: PASS 5x consecutive full-suite (Issue 2 NOT-REPRODUCIBLE)
- Active flakes (out-of-scope, candidatos a CAL filing):
  - `test_te_indicator.py` cassette tests (CA/SE/EA — TE rate-limit cumulative_calls bleed)
  - `test_economic_ecs::test_fixture_us_2020_03_23_recession` (intermittent ~1/5)
  - `test_credit_cccs::TestComputeCccsEndToEnd::test_happy_full_stack` (intermittent ~1/5)
- Closed CAL: CAL-TEST-CYCLES-FIXTURE-FLAKE-AND-FAIL (2026-04-26 via Sprint A)

## TE quota

- Tier: 5000 / mês
- Consumption Week 11 post-Sprint 7B: ~41-42 %
- Sprint A delta: 0 (governance + test-only sprint, sem live calls)

## Pipelines production (systemd timers, 06:00-07:30 WEST)

- `sonar-daily-curves.service` (12 T1 países live)
- `sonar-daily-monetary-indices.service` (M1 16 / M2 11 / M4 8 FULL)
- `sonar-daily-cost-of-capital.service` (US canonical + Damodaran fallback)
- `sonar-daily-bis-ingestion.service`
- `sonar-daily-cycles.service`
- `sonar-daily-credit-indices.service`
- (timer install gated on Hugo authorisation post-merge — `deploy/systemd/`)

## Active worktrees + tmux

- `/home/macro/projects/sonar-wt-a-test-hygiene-and-session-state` — Sprint A (closing 2026-04-26)
- (auto-populated post-update; clear if no active sprint at next refresh)

## Next sprint candidates

- CAL-EXPINF-T1-AUDIT (HIGH priority — closes biggest L2 gap)
- CAL-M3-T1-EXPANSION (curves-derived; 12 curves available)
- L4 cross-country composites (MSC + CCCS + ECS + FCS first cross-country runs)
- Pre-existing test flakes consolidation (TE cassettes + cycles intermittents) — separate CAL filing if persisting
