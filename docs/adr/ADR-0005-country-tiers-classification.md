# ADR-0005: Country tiers classification

**Status**: Accepted
**Data**: 2026-04-18
**Decisores**: Hugo Condesa (solo operator)
**Consultados**: Claude chat (arquitectura), Claude Code (D1+D2 empirical validation)

## Contexto

SONAR v2 scope editorial é global — ~196 países ISO 3166-1 em princípio. Na prática, **cobertura de data não é uniforme**:

- Sovereign bond markets líquidos com ≥6 tenors daily existem para ~45-50 países (T1-T2 universe).
- Macro indicators completos (GDP QoQ, CPI, unemployment, PMI) via TE breadth cobrem ~75-100 países.
- BIS WS_DSR cobre 32 países pre-computed; WS_TC estende para 43.
- Financial market depth (AAII, COT, FINRA, ICE BofA spreads) é essencialmente US-only.
- Shadow rates (Krippner, Wu-Xia) só disponíveis em 4 economias (US, EA, UK, JP).
- Survey data (SPF, UMich, ECB SPF) cobre US + EA.

Specs layer L2 (overlays) + L3 (indices) + L4 (cycles) foram escritos em Phase 0 Bloco B com **assunções G10 implícitas** (full coverage disponível). D1 (data discovery) e D2 (empirical validation) expuseram sistematicamente os gaps: T4 países não têm cycles operacionais; T3 têm FCS degraded; T2 têm MSC parcial.

Phase 0 Bloco D1 produziu `docs/data_sources/country_tiers.yaml` (commit 3934fb22) como artefacto operacional — 89 países explícitos + T4 default catch-all. D2 validou empiricamente a cobertura:

| Tier | Coverage estimada overall |
|------|---------------------------|
| T1 | ~85% |
| T2 | ~50% |
| T3 | ~25% |
| T4 | ~0% (só rating-spread + CRP) |

Falta formalizar a classificação como **decisão arquitectural estável** que specs podem referenciar, pipeline pode consumir para scheduling, e fail-mode (Policy 1) pode usar para confidence caps. Sem ADR, o artefacto YAML é operacional mas a decisão que o motiva é tácita.

## Decisão

Adoptamos **classificação explícita de 4 tiers T1-T4** conforme `docs/data_sources/country_tiers.yaml`, com semântica canónica:

- **T1 (16 países)** — full coverage obrigatório. Todos os 4 cycles (ECS, CCCS, MSC, FCS) operacionais. Fixtures historical required. Pipeline daily processa T1 sempre.
- **T2 (30 países)** — best-effort coverage. Cycles podem ter indices degradados com flags (`F4_COVERAGE_SPARSE`, `MSC_M1_ONLY_MODE`, etc.). Pipeline daily best-effort; flags toleradas sem block.
- **T3 (43 países)** — partial coverage. ECS + CCCS + MSC + CRP esperados; FCS frequentemente degraded. Pipeline weekly batch; on-demand daily se consumer solicita.
- **T4 (~110 países)** — rating-spread + CRP only. Outros overlays opt-in per spec. Pipeline on-demand; no default scheduling.

## Alternativas consideradas

- **4-tier T1-T4** ← escolhida. Granularidade suficiente para specs referenciarem sem over-specification; mapping directo para pipeline scheduling (daily / best-effort / weekly / on-demand); aligned com empirical coverage gradient observed D1+D2.

- **2-tier (supported / unsupported)** — rejeitada. Coarse-grain; colapsa T2 (30 países EM viáveis best-effort) com T4 (frontier ~110); perde signal editorial para priorization.

- **3-tier (core / extended / frontier)** — rejeitada marginalmente. Não captura distinção operacional entre T1 (full) e T2 (best-effort-com-flags) que é material para Policy 1 re-weight + confidence cap. 4 tiers é o sweet spot.

- **N-tier per cycle** (e.g. T1-cycle-specific) — rejeitada. Complexity explosion; cada cycle teria tier map próprio; contradiction com YAML single-source. Preserva-se single-tier-per-country; cycles referenciam o mesmo tier.

- **Dynamic tier promotion** via empirical thresholds (e.g. if coverage ≥80% → promote T3→T2) — rejeitada Phase 1. Risk: flapping tier assignments quebra pipeline scheduling. Phase 2+ considerável.

## Consequências

### Positivas

- **Specs podem assumir T1 full** sem defensive guards para cada sub-index. Simplifica spec writing + test fixtures focados em T1.
- **Pipeline scheduling é determinístico**: T1 daily mandatory, T2 best-effort (flags-tolerated), T3 weekly, T4 on-demand. Observability alerts por tier (T1 SLO estrito, T4 nenhum).
- **Policy 1 confidence cap aplicável por tier**: T2 confidence cap 0.85, T3 cap 0.65, T4 cap 0.40 (via convention `composite-aggregation.md` integration future).
- **D1/D2 evidence base**: classification é data-driven não arbitrária — `D1_coverage_matrix.csv` + `D2_empirical_validation.md` documentam rationale per country × cycle.
- **Operator UX**: Hugo consulta YAML como single-source-of-truth per país; no need grep de specs individuais.

### Negativas / trade-offs aceites

- **T4 users (~110 países) não recebem ciclos operacionais** em Phase 1. Editorial coverage limitada a rating-spread + CRP (appropriate para T4 scope de frontier markets onde dados completos não existem).
- **Rigid boundaries**: QA, KW, IL em T3 mas são mercados sophisticated; OQ6 do D1 (backlog) revisita promotion to T2 baseado em empirical coverage measurements Phase 1.
- **YAML como fonte de verdade operacional** significa update via PR dedicado (Hugo must explicitly bump tier). Não é auto-discovered.
- **Cycle-agnostic tier**: um país T1 em ECS mas T3 em FCS é impossível neste schema. Aceito simplification; Policy 1 mitiga via per-index-missing flags.

### Follow-ups requeridos

- [`../specs/conventions/composite-aggregation.md`](../specs/conventions/composite-aggregation.md) — Phase 1 pode adicionar per-tier confidence cap integration (e.g. T2 cap 0.85 default ontop of Policy 1 re-weight).
- Phase 1 pipeline L8: schedule rules must consume `country_tiers.yaml` — implementation detail spec-level.
- Phase 2+ review triggers documentados em §Review triggers abaixo.
- [`../specs/conventions/patterns.md`](../specs/conventions/patterns.md) Pattern 4 (TE primary + native overrides) refere tier-aware decisions: T1 has native override mandatory; T2+ TE breadth é accepted primary.

## Review triggers

Este ADR é re-visitado (não auto-superseded) quando:

1. **Phase 2+ horizontal expansion** para países T3-T4. Criteria: T3 país com ≥3 cycles production-ready por 6m consecutive → candidate para T2 promotion.
2. **TE breadth expansion**: se TE adicionar países não listados, tier assignment novo requerido — ADR-0006 ou addendum.
3. **OQ6 pending**: QA, KW, IL em T3 mas são mercados sophisticated — D1 backlog item para revisit promotion to T2 em H2 2026.
4. **D2-surfaced gaps fechados** (CAL-018 TCMB, CAL-022 INE, CAL-023 LEI US): quando resolvidos, tier integrity dos países afectados pode melhorar e trigger reclassification.

## Implementation references

- [`../data_sources/country_tiers.yaml`](../data_sources/country_tiers.yaml) — operational artifact (canonical tier assignments).
- [`../data_sources/D1_coverage_matrix.csv`](../data_sources/D1_coverage_matrix.csv) — coverage evidence per series × country.
- [`../data_sources/D2_empirical_validation.md`](../data_sources/D2_empirical_validation.md) — tier coverage rates empirically validated.
- [`../specs/conventions/composite-aggregation.md`](../specs/conventions/composite-aggregation.md) — Policy 1 fail-mode aplicável per tier degradation.
- [`../specs/conventions/patterns.md`](../specs/conventions/patterns.md) §Pattern 4 — TE primary + native overrides: tier-aware override matrix.

## Decision makers

- **Hugo Condesa** (solo operator, 7365 Capital): autoriza classification + future promotions.
- **Claude chat**: arquitectura + alternatives trade-off analysis (Phase 0 Blocos D1+D2+D3).

## Referências

- [`ADR-0002-arquitectura-9-layer.md`](ADR-0002-arquitectura-9-layer.md) — 9-layer architecture; tiers são cross-cutting attribute, não nova layer.
- [`ADR-0004-ai-collaboration-model.md`](ADR-0004-ai-collaboration-model.md) — decision-making workflow usado para este ADR.
- [`../specs/conventions/patterns.md`](../specs/conventions/patterns.md) Pattern 4.
- [`../specs/conventions/proxies.md`](../specs/conventions/proxies.md) — proxies registry (tiers affect proxy applicability).
- [`../data_sources/country_tiers.yaml`](../data_sources/country_tiers.yaml) — operational source.
- [`../backlog/phase2-items.md`](../backlog/phase2-items.md) — Phase 2 horizontal expansion scope.
- [`../ROADMAP.md`](../ROADMAP.md) §Phase 2 — horizontal expansion gate.
