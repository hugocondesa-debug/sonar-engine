# SESSION_STATE — SONAR Engine

*Auto-updated post-sprint per `governance/WORKFLOW.md` mandate.*
*Companion to claude.ai Project knowledge `SESSION_CONTEXT.md` (narrative / decisions).*
*Last updated: 2026-04-26T22:35Z by Sprint 8 (test pollution root-cause diagnosis).*

---

## Phase

- **Current**: Phase 2 T1 horizontal expansion
- **Completion estimate**: ~62-65 %
- **Target**: ~80-85 % T1 fim Maio 2026

## Last sprint shipped

- **ID**: Sprint 8 — test pollution root-cause diagnosis (continuation Sprint A)
- **Branch**: `sprint-8-test-pollution-rootcause`
- **SHA range**: `7b7cea5..546ceca` (Commits 1-4; retrospective commit pending)
- **Outcome**: **A** (root cause + single fix). pytest-asyncio orphan event-loop leak diagnosed via PYTHONTRACEMALLOC=10 (`pytest_asyncio/plugin.py:618` + Python 3.12 default policy auto-create). Fix: autouse session-scoped fixture em `tests/conftest.py` (`b37b29e`). Verificação: 5/5 consecutive full-suite PASS clean (was 5/5 fail pre-fix). CAL-TEST-CYCLES-FIXTURE-FLAKE-AND-FAIL residuais marcados closed.

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

- Pre-push gate: **green clean** post Sprint 8 fix (`b37b29e`)
- Full-suite (`pytest -m "not slow"`): 2322 passed, 0 failed, 5/5 consecutive runs clean
- Targeted subset (`tests/unit/test_cycles/ tests/unit/test_connectors/test_te_indicator.py`): 304 passed, 3/3 consecutive clean
- Coverage: 83.44 % TOTAL post-fix
- Active flakes: **none known** (all Sprint A residuais resolvidos por Sprint 8)
- Closed CAL (residuais incluídos): CAL-TEST-CYCLES-FIXTURE-FLAKE-AND-FAIL (2026-04-26 via Sprint A + Sprint 8)
- Test-infra fix: `tests/conftest.py` autouse session-scoped fixture defines `policy._local._set_called = True` para suprimir asyncio default policy auto-create branch (Python 3.12 + pytest-asyncio 1.3.0 + filterwarnings=error interaction)

## TE quota

- Tier: 5000 / mês
- Consumption Week 11 post-Sprint 7B: ~41-42 %
- Sprint A delta: 0 (governance + test-only sprint, sem live calls)
- Sprint 8 delta: 0 (test infrastructure fix, sem live calls)

## Pipelines production (systemd timers, 06:00-07:30 WEST)

- `sonar-daily-curves.service` (12 T1 países live)
- `sonar-daily-monetary-indices.service` (M1 16 / M2 11 / M4 8 FULL)
- `sonar-daily-cost-of-capital.service` (US canonical + Damodaran fallback)
- `sonar-daily-bis-ingestion.service`
- `sonar-daily-cycles.service`
- `sonar-daily-credit-indices.service`
- (timer install gated on Hugo authorisation post-merge — `deploy/systemd/`)

## Active worktrees + tmux

- `/home/macro/projects/sonar-wt-8-test-pollution-rootcause` — Sprint 8 (retrospective commit pending; cleanup post-merge)
- (auto-populated post-update; clear if no active sprint at next refresh)

## Next sprint candidates

- CAL-EXPINF-T1-AUDIT (HIGH priority — closes biggest L2 gap)
- CAL-M3-T1-EXPANSION (curves-derived; 12 curves available)
- L4 cross-country composites (MSC + CCCS + ECS + FCS first cross-country runs)
- (Pre-existing test flakes consolidation — RESOLVED Sprint 8; sem follow-up necessário)
