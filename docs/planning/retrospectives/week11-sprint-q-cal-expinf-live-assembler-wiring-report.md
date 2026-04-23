# Sprint Q — CAL-EXPINF-LIVE-ASSEMBLER-WIRING (M3 FULL P0 Unlock) — Retrospective

**Sprint**: Week 11 Day 1 Sprint Q
**Branch**: `sprint-q-cal-expinf-live-assembler-wiring`
**Worktree**: `/home/macro/projects/sonar-wt-q-cal-expinf-live-assembler-wiring`
**Data**: 2026-04-23 late (early arranque vs Day 1 morning target per brief §9; wall-clock ~1h vs 4-6h budget)
**Operator**: Hugo Condesa (reviewer) + Claude Code (executor autónomo per SESSION_CONTEXT)
**Parent audit**: `docs/backlog/audits/sprint-o-m3-exp-inflation-audit.md` (Sprint O opened CAL-EXPINF-LIVE-ASSEMBLER-WIRING 2026-04-22)
**Outcome**: 7 commits (this retro = C8), US M3 live-wired DEGRADED→FULL, 248+ regression pass, 18 new tests green, revised target hit (1/9 FULL = US; brief aspiration 3/9 disproved by connector reality).

---

## 1. Scope shipped

| Commit | Scope | Ficheiros |
|---|---|---|
| **C1** | docs(backlog): Sprint Q pre-flight audit | `docs/backlog/audits/sprint-q-expinf-wiring-audit.md` |
| **C2** | feat(indices): EXPINF live loader | `src/sonar/indices/monetary/exp_inflation_loader.py` |
| **C3** | refactor(overlays,pipelines): `LiveConnectorSuite.fred` + `LiveInputsBuilder._run` wiring + `daily_overlays._live_inputs_builder_factory` plumbing | `src/sonar/overlays/live_assemblers.py`, `src/sonar/pipelines/daily_overlays.py` |
| **C4** | (no-op) M3 classifier unchanged — reads `index_values(EXPINF_CANONICAL)` already; FULL promotion happens automatically post-C3 | — |
| **C5** | test: loader + bundle-wiring regression | `tests/unit/test_pipelines/test_expinf_wiring.py` (18 tests, 14 parametric across 9 countries + error legs) |
| **C6** | ops: backfill 3-day (Apr 21/22/23) + M3 classifier verify | dev-DB `index_values` populated; 3/3 dates FULL for US |
| **C7** | docs(backlog): CAL-EXPINF-LIVE-ASSEMBLER-WIRING closure + 6 per-country follow-up CALs | `docs/backlog/calibration-tasks.md` |
| **C8** (this) | docs(planning): retrospective + coverage matrix | this file |

**Scope respected**: zero new connectors, zero schema migration, zero touch on E1/E3/E4, zero classifier churn (§4 scope locks all clean).

---

## 2. Architectural reality vs brief premise — discovery #2

Sprint O retro documented the first layer of this gap ("4/16 FULL" was code-capability, not runtime). Sprint Q audit (§1 executive summary) surfaced a **second premise mismatch** the brief did not anticipate:

**Brief §1 + §2.1.3 expected** "Tier 1 (FULL-capable): US, EA, GB — likely have BEI + swap + survey" and Sprint O §4 projected FULL-candidate for DE + FR too once CAL-EXPINF-LIVE-ASSEMBLER-WIRING closes.

**Reality** (audit §3.3): only the FRED connector exposes live BEI + survey endpoints, and its BEI/survey methods raise `ValueError` for any country other than US. ECB SDW: no inflation endpoint (`ecb_sdw.py:373` explicit). BoE: no BEI/SPF in current `BoEDatabaseConnector` surface. Bundesbank / Banca d'Italia / Banco España / Banque de France `fetch_yield_curve_linker`: stubs raising deferral errors. The `exp_inflation_{bei,swap,survey,derived,canonical}` DB tables exist via alembic 004 but have no ORM models, no writers, no rows — dormant infrastructure, not the canonical read path.

**Sprint Q shippable**: US-only wiring. DE/EA/GB/JP/CA/IT/ES/FR stay DEGRADED because the live BEI/survey data they'd need simply is not reachable from our current connector surface. Retro opens 6 follow-up CALs (§8 below) to land the per-country connectors in future sprints; once any of those lands, extending the loader's per-country dispatch is a line-level change.

Brief §5.1 item 4 acceptance "≥3 FULL (US/EA/GB)" revised **downward to ≥1 FULL (US)** with full documentation in audit §4 revised classification matrix. Tier A acceptance §5 satisfied under the revised target.

---

## 3. M3 coverage matrix — before / after

| Country | Pre-Q (after Sprint O) | Post-Q (this sprint) | Sprint Q delta | Longer-run target (per Sprint O + audit §4) |
|---|---|---|---|---|
| **US** | DEGRADED `M3_EXPINF_MISSING` | **FULL** `M3_FULL_LIVE` | **DEGRADED→FULL** ✅ | FULL (maintained) |
| DE | DEGRADED `M3_EXPINF_MISSING` | DEGRADED `M3_EXPINF_MISSING` | no-op | FULL post-CAL-EXPINF-DE-BUNDESBANK-LINKER |
| EA | DEGRADED `M3_EXPINF_MISSING` | DEGRADED `M3_EXPINF_MISSING` | no-op | FULL post-CAL-EXPINF-EA-ECB-SPF |
| GB | DEGRADED `M3_EXPINF_MISSING` | DEGRADED `M3_EXPINF_MISSING` | no-op | FULL post-CAL-EXPINF-GB-BOE-ILG-SPF |
| JP | DEGRADED + `JP_M3_BEI_LINKER_THIN_EXPECTED` | DEGRADED + `JP_M3_BEI_LINKER_THIN_EXPECTED` | no-op | DEGRADED (structural) post-CAL-EXPINF-SURVEY-JP-CA |
| CA | DEGRADED + `CA_M3_BEI_RRB_LIMITED_EXPECTED` | DEGRADED + `CA_M3_BEI_RRB_LIMITED_EXPECTED` | no-op | DEGRADED (structural) post-CAL-EXPINF-SURVEY-JP-CA |
| IT | DEGRADED + `IT_M3_BEI_BTP_EI_SPARSE_EXPECTED` | DEGRADED + `IT_M3_BEI_BTP_EI_SPARSE_EXPECTED` | no-op | DEGRADED (structural) post-CAL-EXPINF-EA-PERIPHERY-LINKERS |
| ES | DEGRADED + `ES_M3_BEI_BONOS_EI_LIMITED_EXPECTED` | DEGRADED + `ES_M3_BEI_BONOS_EI_LIMITED_EXPECTED` | no-op | DEGRADED (structural) post-CAL-EXPINF-EA-PERIPHERY-LINKERS |
| FR | DEGRADED `M3_EXPINF_MISSING` | DEGRADED `M3_EXPINF_MISSING` | no-op | FULL post-CAL-EXPINF-FR-BDF-OATI-LINKER |

Runtime M3 FULL coverage: **0/9 → 1/9** (US). Observability 9/9 preserved (all 9 emit `monetary_pipeline.m3_compute_mode`).

### Verified E2E (2026-04-23 backfill)

```
$ sqlite3 data/sonar-dev.db "SELECT date, country_code, confidence, raw_value
   FROM index_values WHERE index_code='EXPINF_CANONICAL' ORDER BY date;"
2026-04-21|US|1.0|0.0238
2026-04-22|US|1.0|0.0238
2026-04-23|US|1.0|0.0242
```

M3 classifier output on 2026-04-23 (excerpt from pipeline journal):

```
m3_compute_mode country=US mode=FULL     flags=('US_M3_T1_TIER', 'M3_FULL_LIVE')
m3_compute_mode country=DE mode=DEGRADED flags=('DE_M3_T1_TIER', 'M3_EXPINF_MISSING')
m3_compute_mode country=EA mode=DEGRADED flags=('EA_M3_T1_TIER', 'M3_EXPINF_MISSING')
m3_compute_mode country=GB mode=DEGRADED flags=('GB_M3_T1_TIER', 'M3_EXPINF_MISSING')
m3_compute_mode country=JP mode=DEGRADED flags=('JP_M3_T1_TIER', 'JP_M3_BEI_LINKER_THIN_EXPECTED', 'M3_EXPINF_MISSING')
m3_compute_mode country=CA mode=DEGRADED flags=('CA_M3_T1_TIER', 'CA_M3_BEI_RRB_LIMITED_EXPECTED', 'M3_EXPINF_MISSING')
m3_compute_mode country=IT mode=DEGRADED flags=('IT_M3_T1_TIER', 'IT_M3_BEI_BTP_EI_SPARSE_EXPECTED', 'M3_EXPINF_MISSING')
m3_compute_mode country=ES mode=DEGRADED flags=('ES_M3_T1_TIER', 'ES_M3_BEI_BONOS_EI_LIMITED_EXPECTED', 'M3_EXPINF_MISSING')
m3_compute_mode country=FR mode=DEGRADED flags=('FR_M3_T1_TIER', 'M3_EXPINF_MISSING')
```

Matches audit §4 predicted matrix exactly — no surprises at runtime.

---

## 4. Phase 2 T1 coverage delta — reality check

Brief §6 retro scope projected:

- Pre-Q T1 overall: ~57.5%
- Post-Q T1 overall: projected ~67-72% (+10-15pp from M3 FULL × Tier 1-3 countries)

Reality with 1/9 FULL (US only):

- +1 country × M3 layer = **~+1-2pp T1 overall** (depends on layer-weighting convention; M3 is one of ~5 monetary layers, so M3 FULL for US alone ≈ 0.02 × 0.5 weighting at most).
- Post-Q T1 overall: ~58-59%, not 67-72%.

Phase 2 fim-Maio target (75-80%) now requires landing 3-5 of the 6 per-country EXPINF CALs opened today to close the M3 gap — total projected effort ~3-4 sprints (one per Priority-MEDIUM CAL). CAL-EXPINF-EA-ECB-SPF has the highest leverage (single ship unblocks EA + DE + FR + IT + ES + NL + PT M3 SURVEY leg concurrently via shared ECB SPF anchor).

Revised Phase 2 path: Week 11 remaining days + Week 12 = likely 2-3 EXPINF country sprints + remaining non-M3 gaps. Reaching 75% is plausible; 80% is tighter.

---

## 5. Execution notes — what went well, what surprised

### Went well

- **Audit-first discipline** (Sprint O Lesson #3 reinforced): the §3 connector inventory caught the premise mismatch before any code was written. 30 min audit saved 2+h of speculative non-US wiring that would have silently returned None in production — or worse, crashed when invoking stub connectors.
- **Graceful fallback design**: the loader returns `None` for any country/error path; assembler wraps the await in `_ConnectorErrors`; `OverlayBundle.expected_inflation=None` is an already-supported state in `_compute_expected_inflation`. Net: non-US countries see zero regression risk.
- **Minimal diff**: 1 new module (~170 LOC), 1 new test file (~250 LOC), 2 edits to existing files (<20 LOC total). No classifier change, no builder signature change, no pipeline orchestration change. Every scope lock in §4 respected.
- **End-to-end verification from dev DB**: no mocking required post-C3 — live FRED API key present in sonar-engine/.env, dev DB symlinked, 3-day backfill landed real EXPINF rows, M3 classifier picked them up, FULL emitted. Full runtime loop validated.
- **Test flakiness caught early**: first cut of wiring tests mixed sync builder invocation (nested `asyncio.run` under pytest-asyncio AUTO mode) + async loader tests → ResourceWarning leak between tests → intermittent fails under `filterwarnings = error`. Refactored to exercise `LiveInputsBuilder._run` directly (async) — isolation clean, 18/18 stable.
- **Wall-clock**: ~1h vs 4-6h budget (~75-85% under). Audit discovery cut the sprint to US-only; US wiring itself is a 3-file change.

### Surprised

- **The `exp_inflation_*` DB tables are dormant**: alembic 004 shipped 5 tables (bei / swap / survey / derived / canonical) with full schemas + constraints, but no ORM models, no writers, no readers. They are future-persistence scaffolding. Brief §2.3 loader design ("Query `exp_inflation_canonical` primary source / Fallback hierarchy: canonical → derived → (BEI + swap synthesis) → survey") would have aimed the loader at the wrong layer. Correct canonical read path is `index_values` WHERE `index_code='EXPINF_CANONICAL'` (compute live, persist to generic index_values, M3 classifier reads there). Audit §3.1 corrected the assumption; loader design §6.1 updated accordingly.
- **ADR-0011 P6 event-loop warning from `live_assemblers.risk_free_error`**: `risk_free_resolver` (factory at `daily_overlays.py:665`) calls `asyncio.run(fred.fetch_...)` inside the sync resolver, which the outer `LiveInputsBuilder.__call__` then wraps in another `asyncio.run` via `_run`. Nested event loops → "Event loop is closed" warning on the *inner* FRED client. Only affects ERP (resolver provides US risk-free); does not affect EXPINF wiring (EXPINF path runs fully inside `_run`'s single event loop, no nesting). Noted as pre-existing architecture debt — not introduced by Sprint Q. Likely needs an ADR-0011 P6 amendment or a resolver signature refactor in a future sprint.
- **CLI flag naming in brief vs actual**: brief §2.6 used `--indices m3 --all-t1` but the actual `daily_monetary_indices` CLI has `--m3-t1-cohort` + no `--indices` flag. Adjusted the backfill command to match reality (§2.6 revised in retro's "shipped" description).
- **Daily-overlays + daily-monetary-indices ordering**: brief §2.6 listed backfill as a single daily_monetary_indices loop, but daily_overlays must run first to persist EXPINF_CANONICAL rows into `index_values` before the M3 classifier can read them. Order matters for E2E verify; brief omitted this step.

---

## 6. Lessons — candidates for Week 11 lessons list

**L-Q1 — Connector-surface audit precedes wiring audit** (reinforces Sprint O L-O1): a wiring gap is only closeable when upstream connectors actually expose the endpoints the wiring feeds off. Audit §2.1 gap-location is necessary but not sufficient; §3 connector inventory ("what data can we actually fetch per country?") is the real gating question. Future upstream-wiring sprints (E1/E3/E4 classifiers+wiring) should explicitly include a "connector surface" audit stage before scoping.

**L-Q2 — DB schema shipment ≠ read path**: five `exp_inflation_*` tables shipped via alembic 004 proved to be dormant — no ORM, no writers, no callers. A brief's assumption that "tables exist = canonical source" can be disproved simply by `grep -l <table_name> src/sonar/db/ src/sonar/connectors/ src/sonar/pipelines/` — if nothing matches, the table is infrastructure scaffold, not data. Adds a new pre-flight check to brief-format v3.x audit checklist: "For any DB table named as a read target, grep for ORM + writer + reader; if all three are absent, that table is not the source."

**L-Q3 — Graceful-fallback design pays off at acceptance revision time**: because the loader + assembler both return None cleanly for any gap, revising acceptance §5.1 item 4 from "≥3 FULL" down to "≥1 FULL" did not require any code change — only doc updates. Design principle: return None on any upstream gap, never raise at the overlay boundary. Consumers already handle None via structured skip. Future loaders should follow the same pattern.

**L-Q4 — Pytest-asyncio AUTO + nested asyncio.run = ResourceWarning leak**: `filterwarnings = error` in pyproject.toml turns pytest-asyncio wrapper-on-sync-test leaks into test failures. Solution: test async methods directly (`await builder._run(...)`) rather than the sync façade (`builder(...)` which wraps `asyncio.run`). New tests should default to exercising async APIs directly when the code under test has both surfaces.

---

## 7. ADR-0011 Principle 8 — observability-before-wiring anti-pattern (deferred)

Brief §2.7 offered Principle 8 as optional (20-min budget if pattern emerges). Decision: **defer**. Rationale:

- The pattern is already well-documented by Sprint O's audit-first discipline + this Sprint Q retro. Promoting it to a named ADR principle now would be ceremonial rather than informative.
- The pattern's generalizability to E1/E3/E4 is plausible but untested. Wait until at least one of those sprints hits the same "classifier shipped, runtime degraded" pattern before codifying.
- Sprint O's L-O1 "Audit before scaffold" + this retro's L-Q1 + L-Q2 cover the same design guidance at a finer grain.

If E1 or E3 lands a classifier with "ghost FULL" (observability emit but runtime DEGRADED), re-open the Principle 8 write-up.

---

## 8. CAL items (opened / closed)

### Closed

- **CAL-EXPINF-LIVE-ASSEMBLER-WIRING** (P0 Week 11) — US live-wired DEGRADED→FULL; 8 non-US T1 countries correctly stay DEGRADED (no live data) and land in per-country follow-up CALs.

### Opened

All added to `docs/backlog/calibration-tasks.md` under the CAL-M3-T1-EXPANSION section:

| CAL | Country | Priority | Dependency | Unblocks |
|---|---|---|---|---|
| **CAL-EXPINF-DE-BUNDESBANK-LINKER** | DE | MEDIUM | — | DE M3 FULL |
| **CAL-EXPINF-EA-ECB-SPF** | EA (shared) | MEDIUM | — | EA + periphery EA members (DE/FR/IT/ES/PT/NL) M3 SURVEY leg |
| **CAL-EXPINF-GB-BOE-ILG-SPF** | GB | MEDIUM | — | GB M3 FULL |
| **CAL-EXPINF-FR-BDF-OATI-LINKER** | FR | MEDIUM | EA-ECB-SPF | FR M3 FULL (highest leverage after EA) |
| **CAL-EXPINF-EA-PERIPHERY-LINKERS** | IT + ES | LOW-MEDIUM | EA-ECB-SPF | IT/ES structural-DEGRADED (softer fail) |
| **CAL-EXPINF-SURVEY-JP-CA** | JP + CA | LOW | — | JP/CA structural-DEGRADED |
| **CAL-M3-DEGRADED-MODE-UPLIFT** | umbrella | tracking | all 6 above | — |

Highest-leverage CAL: **CAL-EXPINF-EA-ECB-SPF** — single ECB SDW connector extension unlocks SURVEY leg for the entire 7-country EA/member cohort, potentially promoting EA aggregate M3 to FULL with only an EA+EA-member survey anchor (BEI leg optional but improves confidence).

---

## 9. Sprint P unblock reflection

Brief §8 notes Sprint P (MSC EA composite) is unblocked once M3 EA reaches FULL. Sprint Q did NOT promote EA to FULL (no EA BEI/survey connector available today). Sprint P blocker persists, now explicitly traceable to **CAL-EXPINF-EA-ECB-SPF**.

Week 11 Day 2+ sequencing suggestion: if Phase 2 fim-Maio trajectory matters, prioritize CAL-EXPINF-EA-ECB-SPF next — its single-connector ship unlocks EA M3 FULL + enables Sprint P (MSC EA composite) + improves 6 EA-member SURVEY legs.

---

## 10. Week 11 Day 1 sequencing reflection

Brief §9 budget was 4-6h; actual wall-clock ~1h. Arranque was earlier than Day 1 morning target (executed late Day 0 rather than Monday morning); did not constitute a problem because the sprint is fully standalone and does not depend on same-day neighbors.

Key budget consumers:
- Audit discovery + doc writing: ~25 min
- Loader + wiring code: ~15 min
- Test design + refactor (pytest-asyncio leak) + ruff fixups: ~10 min
- Backfill + E2E verify: ~5 min
- CAL ledger + retro: ~20 min

**Under-budget reason**: audit-first discovered the US-only reality, which collapsed the sprint from "9-country wiring" to "1-country wiring" — most of the effort vanished because 8 countries are no-op. The brief's original 4-6h budget anticipated multi-country differences to reconcile per-country (different BEI sources, different survey timings). Reality: none of them shippable without new connectors.

Signal for future briefs: if a sprint's plan says "N-country wiring" but the audit can collapse to "1-country wiring", the budget should flex downward proportionally. Don't pad.

---

*End of retrospective. Sprint Q: US M3 live, 8-country DEGRADED traceable to 6 opened CALs, Phase 2 trajectory preserved but now visibly gated on per-country EXPINF connector work. Ship disciplined.*
