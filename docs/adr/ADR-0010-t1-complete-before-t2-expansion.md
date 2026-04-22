# ADR-0010: T1 Complete Product Before T2 Expansion

**Status**: Active
**Date**: 2026-04-22
**Authors**: Hugo Condesa (7365 Capital)
**Supersedes**: Implicit scope assumption in ADR-0005 (Country Tiers) that T1 and T2 expansion could proceed interleaved.
**Related**: ADR-0005 (Country Tiers), ADR-0008 (Per-country ERP Data Constraints), ADR-0009 (National-CB Connectors EA Periphery), ROADMAP.md consumer model revision (2026-04-22 Day 0 Week 10)

---

## Context

SONAR v2 Phase 2 is in progress shipping T1 horizontal coverage (16 countries). As of Day 1 Week 10 (2026-04-22), L3 indices are ~70% complete across T1, with multiple parallel tracks advancing per-country connectors, overlays, and index assemblers.

Strategic question surfaced mid-Day-1 Week 10: **should Phase 2.5 + Phase 3 include T2 expansion (30 countries best-effort) in parallel with T1 finalization, or should T2 be explicitly deferred until T1 is shipped end-to-end as a complete product?**

Relevant context for decision:

1. **Consumer A (MCP/API privado, 7365 Capital DCF workflows)** operates primarily T1: Portuguese equity (PT + EA), European banks (GB/DE/FR), US tech (US), Japanese conglomerates (JP). T2 use cases (Brazilian retailer DCF, Korean chip DCF, Polish bank DCF) are nice-to-have, not essential for Hugo's core valuation work.

2. **Consumer B (sonar.hugocondesa.com público)** serves educated financial audience. Editorial angles focus ~98% on T1 markets (US Fed policy, EA fragmentation, UK fiscal, JP deflation exit, etc.). T2 content (Turkish lira stress, Brazilian fiscal, Indian growth) is value-add but not MVP.

3. **Solo operator constraints** (Hugo + paralelo CC): cognitive bandwidth for validation is highest on markets Hugo knows intimately (T1). T2 sanity-checking harder — errors slip, bugs compound.

4. **Breadth-first risk**: horizontal T1+T2 simultaneously in Phase 2.5 would create inconsistent state (T1 has L6 integration, T2 has only L2 overlays), complicating L7 output layer design and API versioning.

5. **Depth-first dividend**: Day 1 Week 10 empirically demonstrated that focused paralelo sprints on T1 expansion shipped 6 sprints in one day (3.5x previous velocity). Pattern-proven machine + pattern template per country class (TE cascade, national CB probe-before-scaffold, OECD EO shared connector) enables **mass T2 production sequential** post-T1 maturity.

6. **Generic connector coverage**: TE + BIS v2 + FRED OECD + Damodaran annual already cover T2 countries structurally (~30+ countries via generic endpoints). Activation is per-country wrapper work, not infrastructure.

---

## Decision

**SONAR will ship T1 as a complete, end-to-end product before commencing T2 expansion.**

Specifically:

### Phases 2 + 2.5 + 3 + 4 = T1 ONLY

All work through Phase 4 (empirical calibration, earliest 2028-Q2) restricts scope to **T1 (16 countries)**:

- Phase 2: T1 L2-L3 horizontal complete (curves + M1-M4 + E1-E4 + F1-F4 + ERP per-country)
- Phase 2.5: T1 L5 regimes + L6 integration + backtest harness + OpenAPI spec + L7 tech decisions
- Phase 3: T1 L7 API (MCP + REST) + Website launch + Cloudflare tunnel
- Phase 4: T1 empirical calibration (24m production data backtests)

### Phase 5+ = T2 Expansion

T2 expansion begins **after** Phase 4 open (earliest 2028-Q2), subject to revision if consumer demand or operator priorities shift:

- Phase 5: T2 bulk activation (~30 countries best-effort with flags + confidence caps)
- Phase 6: T3 partial coverage (~43 countries, rating-spread + CRP driven)
- Phase 7: T4 global (~110 countries, Damodaran annual-only)

### Defined scope "T1 Complete Product"

Product ships at Phase 3 exit (~Q1 2027) when:

1. All 16 T1 countries have L2-L6 full stack operational
2. Consumer A (MCP server) serves cross-country k_e queries for all 16 T1
3. Consumer B (website) renders cycle scores + curves + cost-of-capital + matriz 4-way + diagnostics for all 16 T1
4. Pipelines run daily without degradation for all 16 T1
5. Coverage matrix published + auditable per country

At this point, SONAR is a **shippable product** — not a horizontal work-in-progress.

---

## Rationale

### Why T1-complete-first beats T1+T2-horizontal

**Coherence**: Shipping T1 complete end-to-end means Hugo can actually use SONAR for DCF workflows, and readers can actually consume the website. Horizontal partial state (T1+T2 both at L2-L3, neither reaching L7) never produces a deliverable.

**Pattern template dividend**: Every T1 sprint produces reusable infrastructure (connectors, dispatchers, flag taxonomy, tier-aware logic). T2 expansion post-T1 maturity is **~3-4x faster per country** because machine is proven, not invented per country.

**Validation bandwidth**: Solo operator can sanity-check 16 T1 countries (markets Hugo knows). 46 countries T1+T2 would exceed cognitive capacity for careful validation — risk of shipping subtle bugs to Consumer A/B.

**Product definition clarity**: T1-complete has clear exit criterion. T1+T2-horizontal has ambiguous scope, drifts over time, ships nothing.

**Consumer alignment**: Neither Consumer A nor Consumer B needs T2 for MVP. 7365 Capital DCF workflows are T1-centric. Editorial is T1-centric.

### Why not start T2 never / defer indefinitely

Explicitly: **T2 is valuable and will ship.** This decision defers T2 to after T1 maturity, not cancels it.

Post-Phase-4 context will include:
- Proven machine (connectors + dispatchers + flag taxonomy validated via 24m T1 operation)
- Clearer demand signal from consumers (Consumer A usage patterns reveal which T2 countries justify priority)
- Lower per-country cost (pattern template + bulk sprint discipline)

T2 will be **additive**, not disruptive, when shipped.

### Why Phase 5 (Q3 2027) and not earlier

Gated 2028-Q2 for Phase 4 empirical backtest start. Phase 4 needs 24m of T1 production data accumulation post Phase 3 launch. T2 during Phase 4 would compound methodology uncertainty (is deviation T1 vs Damodaran due to method or data?).

T2 activation post Phase 4 open means:
- T1 backtests validate methodology independently
- T2 expansion uses proven methodology with confidence caps
- Consumer A/B API versioning clean (v1 T1, v2 T1+T2)

---

## Consequences

### Positive

1. **Product ships Q1 2027** — clear deliverable milestone (Consumer A + Consumer B both live for T1)
2. **Reduced cognitive load during Phase 2-3** — Hugo validates only T1 markets he knows
3. **Machine pattern template dividend** — T2 expansion Phase 5 uses proven infrastructure, ~3-4x faster per country
4. **Cleaner API versioning** — v1 T1-only, v2 T1+T2 when shipped
5. **Consumer-aligned prioritization** — Hugo's core DCF universe + editorial audience both T1-centric
6. **Reduced merge complexity** — no tier-aware logic needed in pipelines/indices until Phase 5
7. **Budget honesty** — T2 sprint effort estimated against proven T1 baseline, not speculation

### Negative

1. **T2 deferred 6-9 months** vs previous implicit roadmap — some editorial opportunities (Turkey 2026, Brazil 2027 fiscal) not available
2. **Consumer perception** — users may expect global coverage; T1-only messaging needs clarity on website
3. **Static proxies only for T2** until Phase 5 — anyone querying T2 country via API gets Damodaran annual + generic flag, not live compute
4. **Methodology cross-val opportunity cost** — T2 early adoption would stress-test methodology against diverse markets; deferred

### Neutral

1. **Existing T2-capable infrastructure** (TE generic, BIS v2, FRED OECD, Damodaran annual) remains available but not activated — no code removal, just scope lock
2. **Per-country CAL items** already opened for T2 countries stay in backlog, marked Phase 5 deferred
3. **ADR-0005 country_tiers.yaml** remains canonical tier definition — no change

---

## Alternatives Considered

### Alternative A: T1+T2 Horizontal in Phase 2.5

**Pros**: Broader coverage earlier, more consumer-ready signal diversity.

**Cons**: Split attention, validation bandwidth exhausted, product never ships complete, L6/L7 design complicated by tier-aware branching.

**Rejected**: Breadth beats depth only in well-staffed teams. Solo operator + paralelo CC demands depth-first discipline.

### Alternative B: T2 Priority Subset (e.g., IL + KR + CZ + PL)

**Pros**: Limited T2 sampling validates methodology cross-diverse markets early.

**Cons**: Arbitrary subset, justifies poorly, creates T2-partial state that's harder to manage than "not started yet".

**Rejected**: If T2 starts, do it properly (bulk 30). If not, don't start. No middle ground worth complexity cost.

### Alternative C: T2 Parallel to Phase 3 L7 Launch

**Pros**: Website ships T1 complete + T2 "roadmap visible" as credibility.

**Cons**: L7 launch + T2 expansion simultaneous = 2x operator load at most critical product launch moment.

**Rejected**: Product launch is focus-intensive. T2 expansion can follow after launch stable.

### Alternative D (chosen): T1 Complete Through Phase 4, T2 Phase 5+

**Chosen**. Product ships clean, T2 additive post-maturity, sequential discipline preserved.

---

## Implementation

### Immediate (Day 2 Week 10+)

1. **Update ROADMAP.md** with revised Phase 5/6/7 for T2/T3/T4
2. **Update brief format v3** to include explicit `**Tier scope**: T1 ONLY` header in all Week 10+ briefs
3. **CAL backlog audit**: any T2-related CAL items get `Status: Phase 5 deferred per ADR-0010`
4. **Update README.md** with consumer model + T1-first scope clarity
5. **CLAUDE.md §Decision authority**: add "T2 expansion attempts require explicit Hugo re-authorization" to HALT triggers

### Brief template header addition

```
**Tier scope**: T1 ONLY (16 countries). T2 expansion deferred to Phase 5 per ADR-0010.
```

### CC delegation guardrail

CC operating under full autonomy per SESSION_CONTEXT §Decision authority should HALT + surface if:
- User request explicitly or implicitly includes T2 country work
- CAL item dependency points to T2-specific data source
- Generalization pattern suggests T2 activation

CC should not autonomously expand country scope beyond T1 set defined in `country_tiers.yaml`.

### Phase 5 re-activation trigger

ADR-0010 revisits naturally at Phase 4 open (earliest 2028-Q2). At that point:
- T1 product maturity validated via 24m backtests
- Consumer A/B usage telemetry available
- T2 bulk sprint design finalized
- T2 priority order decided based on empirical Consumer signal

Re-activation requires formal ADR-00XX supersedes note, not silent drift.

---

## Related Decisions

- **ADR-0005 Country Tiers**: canonical T1/T2/T3/T4 definitions
- **ADR-0008 Per-country ERP Data Constraints**: narrows T1 ERP scope to 5 markets + Damodaran fallback for others (still T1 scope, respects ADR-0010)
- **ADR-0009 National-CB Connectors EA Periphery**: probe-before-scaffold discipline for T1 EA periphery national CB work
- **ROADMAP.md consumer model revision (2026-04-22)**: consumer A (MCP/API) + consumer B (website) framework

---

## Success Metrics

ADR-0010 succeeds when:

1. **Phase 3 exit Q1 2027**: Consumer A + Consumer B both live for all 16 T1 countries
2. **Zero accidental T2 work** during Phase 2.5 + 3 + 4 (measured via CAL audits per phase close)
3. **Phase 5 T2 velocity**: first T2 bulk sprint ships ≥ 6 countries in 1 day (matching Week 10 Day 1 T1 velocity)
4. **Product usability**: Hugo executes 5+ Portuguese/European/US equity DCF workflows via Consumer A in first month post-Phase-3 launch

---

## Revision History

- **2026-04-22**: Initial version — T1 complete product before T2 expansion (Day 1 Week 10 close, post Sprint D merge)

---

*End of ADR-0010. Scope lock: T1 through Phase 4. T2 Phase 5+. Product focus over horizontal breadth.*
