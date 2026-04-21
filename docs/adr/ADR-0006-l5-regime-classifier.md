# ADR-0006: L5 Regime Classifier — Cross-Cycle Meta-Regimes

**Status**: Accepted
**Data**: 2026-04-22
**Decisores**: Hugo Condesa (solo operator)
**Consultados**: Claude chat (design taxonomy), Claude Code (implementation scaffold)

## Contexto

Phase 1 fechou Week 7 com 4 L4 cycle composites operacionais (CCCS,
FCS, MSC, ECS) — cada um com score 0-100, regime enumerado, e overlay
embedded (boom, bubble, dilemma, stagflation). Cada cycle é
**auto-contido**: responde à pergunta "em que estado está este
cycle?" mas não informa **qual configuração macro global** o país
ocupa.

Na v1 documentacional o framework previa uma **camada L5 de
meta-regimes** para consolidar os 4 cycles em labels cross-cycle
interpretáveis ("overheating", "soft landing", etc.). A camada nunca
foi especificada em Phase 0 — ECS spec §3 apenas referencia "UUID
`ecs_id` permite linkage futura a L5 regime rows (Phase 2+)" como
placeholder.

Falta decidir:

1. **Onde vive L5 na arquitectura** — camada separada sobre L4, ou
   extensão dos próprios specs de cycle?
2. **Que taxonomy de meta-regimes usar** — quantos labels, rule-based
   vs ML, scope Phase 1 vs Phase 2+?
3. **Como integrar com Policy 1** — ≥ 3/4 cycles required (à la L4
   sub-indices) ou strict 4/4?
4. **FK design** — L5 row carries L4 ids ou recomputa? Persistência
   separada ou embedded em cycles?

Sem ADR, qualquer implementação Week 8+ inventa estas decisões
ad-hoc e os specs dos cycles não podem referenciar L5 de forma
estável.

## Decisão

Adoptamos **L5 como camada separada read-only** sobre os 4 cycles L4,
com as seguintes escolhas canónicas:

### 1. Arquitectura

- L5 é uma **camada L5** explícita (extensão à 9-layer architecture
  em ARCHITECTURE.md) — não é extensão inline dos specs L4.
- L5 **lê** L4 persistido via foreign keys; **nunca recomputa** cycle
  scores. Single-source-of-truth para cycle scores fica nas tabelas
  L4.
- Package Python: `src/sonar/regimes/` com submódulos
  `base / types / meta_regime_classifier / exceptions`.

### 2. Taxonomy

- **6 canonical meta-regimes** Phase 1 (Option B Simple):
  `overheating`, `stagflation_risk`, `late_cycle_bubble`,
  `recession_risk`, `soft_landing`, `unclassified`.
- **Classificação rule-based** via decision tree priority-ordered
  (primeira regra que match ganha). Decisão tree documentada em
  `docs/specs/regimes/cross-cycle-meta-regimes.md` §3.
- `unclassified` é o default — apanha transições + configurações que
  não match nenhum branch decisivo. Não é "erro" — é um meta-regime
  legítimo.
- Phase 2+ pode substituir rule tree por ML classifier quando ≥ 24m
  de production cycle data existirem para training. Interface
  (`RegimeClassifier` ABC) não muda.

### 3. Policy 1 integration

- **≥ 3/4 cycles** required para classificação (extensão do Policy 1
  de composite-aggregation.md). Abaixo de 3 cycles raises
  `InsufficientL4DataError` — **não produz row**.
- **Confidence cap** 0.75 quando 1 cycle missing. 2-missing é
  unreachable (exception fires) mas documentamos cap 0.60 para
  forward-compatibility.
- Flags `L5_{CYCLE}_MISSING` propagam quando cycle ausente mas L5 foi
  classificável com os restantes ≥ 3.

### 4. FK design

- `l5_meta_regimes` table (migration 017) com 4 foreign keys
  nullable (`ecs_id`, `cccs_id`, `fcs_id`, `msc_id`) apontando para
  as respectivas PKs L4.
- Unique constraint `(country_code, date, methodology_version)` —
  re-classificação com mesma methodology produz mesma row
  (idempotent) e triggera `DuplicatePersistError` no re-persist
  (consistente com L4 persistence).
- Methodology bump (v0.1 → v0.2) produz nova row sem collision.

### 5. Auditability

- Cada L5 row carries `classification_reason` string identificando o
  branch do decision tree que match. Exemplo:
  `peak+boom+optimism` para `overheating`.
- Flags CSV incluem regime-level (exactly one de 6) + missing-cycle
  (0-1 de 4).
- L4 ids são FK, permitindo drill-down 1-step para as cycle rows
  subjacentes.

## Consequências

### Positivas

- **Auditable classification** — toda L5 row é rastreável aos 4
  cycle ids e ao branch da decision tree que match. Facilita
  explicabilidade editorial e cross-check manual.
- **Forward-compatible com calibração** — thresholds do decision
  tree vivem no código (`meta_regime_classifier.py`); Phase 2+
  pode ajustar sem mudar schema.
- **Interface ABC** — permite swap para ML classifier Phase 2+ sem
  tocar orchestrator.
- **Policy 1 extension coerente** — ≥ 3/4 pattern é consistente com
  L4 sub-indices.
- **Read-only semantics** — L5 não introduz duplicação de cycle
  scores. Single source of truth preservado.

### Negativas

- **Rule-based classifier pode falhar nuances** — ex.: configurações
  mistas (part stagflation + part overheating) vão cair em
  `unclassified` em Phase 1. Aceitável porque audit trail está claro.
- **Requires ≥ 3/4 cycles** — T3/T4 countries com FCS degraded
  frequentemente caem abaixo da threshold. Expected por §2 — L5 é
  para T1-T2 primariamente.
- **Decision tree maintenance** — thresholds e predicados estão
  hardcoded; ajustes empíricos requerem code-change + methodology
  bump (não YAML-tunable em v0.1).

## Alternativas consideradas

### A — ML classifier (rejected Phase 1)

Treinar classifier (random forest / gradient boosting) em histórico
labeled. Rejeitado porque:

- Zero labeled data production cycles Phase 1 (specs shipped 2026-04;
  daily cycles operacionais < 1 mês).
- Sem data, ML é overfit garantido.
- Rule-based é auditable; ML introduz black-box risk editorial.

Phase 2+ revisit: quando ≥ 24m daily cycle rows em produção,
training set viável. ABC interface foi desenhada para permitir swap
sem tocar orchestrator.

### B — Simple score-average meta-regime (rejected)

`meta_score = (cccs + fcs + msc + ecs) / 4` → bands. Rejeitado
porque:

- Descarta o sinal dos **regimes** discretos (perde boom overlay,
  stagflation trigger, etc.).
- Scores composite averagiar num score único mata informação — um
  país pode ter ECS=55 (neutral) + FCS=80 (euphoria) + CCCS=70
  (boom) + MSC=40 (accommodative) → média ≈ 61 (nothing-burger)
  mas a configuração real é **late-cycle bubble** que merece label
  próprio.
- Quebra a semântica "first match wins" do decision tree que é
  explicitamente editorial-friendly.

### C — Inline regime extension em cycle specs (rejected)

Embedder meta-regime em cada cycle (ex.: ECS regime expands to 8
labels incluindo cross-cycle context). Rejeitado porque:

- Viola single-responsibility dos specs L4 (cada cycle fica
  auto-contido).
- Cross-cycle interaction é inerentemente L5 concern — forçar em L4
  acopla cycles uns aos outros.
- Re-classification requires changing 4 cycle specs simultaneously;
  L5 separate aloja mudança num só lugar.

### D — 12+ meta-regimes taxonomy (deferred)

V1 documentacional previa ~12-18 regimes (Kindleberger + Minsky
phases + Aghion growth cycles + Brunnermeier bubble cascades).
Adiado porque:

- Phase 1 scope: 6 regimes cobrem 80% dos casos editorial
  relevantes.
- ≥ 12 regimes requer empirical calibration não disponível.
- Expansão Phase 2+ é bump v0.1 → v0.2 (não breaking change) — taxa
  de churn esperada baixa.

## Referências

- [`../specs/regimes/README.md`](../specs/regimes/README.md) —
  layer overview.
- [`../specs/regimes/cross-cycle-meta-regimes.md`](../specs/regimes/cross-cycle-meta-regimes.md)
  — inputs + decision tree + outputs schema.
- [`../specs/regimes/integration-with-l4.md`](../specs/regimes/integration-with-l4.md)
  — FK pattern + Policy 1 extension.
- [`../specs/conventions/composite-aggregation.md`](../specs/conventions/composite-aggregation.md)
  — Policy 1 base this ADR extends.
- [`ADR-0002-arquitectura-9-layer.md`](ADR-0002-arquitectura-9-layer.md)
  — 9-layer architecture; L5 slot was reserved there.
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md) — layer graph.
