# ADR-0002: Arquitectura 9-layer

**Status**: Accepted
**Data**: 2026-04-18
**Decisores**: Hugo Condesa (solo operator)
**Consultados**: Claude chat (anthropic.com), Claude Code (VPS)

## Contexto

V1 operava com 5-layer implicit (connectors + db + submodels + cycles + outputs). Debt identificado em [`../MIGRATION_PLAN.md`](../MIGRATION_PLAN.md) §2: "submodels" fundia 3 conceitos ortogonais (calculadoras universais, componentes internos de scores, cycle overlays); "cycles" fundia classificação com composição cross-country; pipelines eram scripts ad-hoc sem contract formal.

Durante bootstrap de specs (Phase 0 Blocos P0-P5), 9 camadas emergiram naturalmente por convergência: L3 indices e L5 regimes reificaram-se como camadas autónomas para resolver naming collisions; L8 pipelines ganhou specs formais (6 stubs) para substituir orquestração ad-hoc. Decisão formaliza o que as specs já assumem operacionalmente.

## Decisão

Adoptamos **arquitectura 9-layer formal**: L0 `connectors/` · L1 `db/` · L2 `overlays/` · L3 `indices/` · L4 `cycles/` · L5 `regimes/` · L6 `integration/` · L7 `outputs/` · L8 `pipelines/`. Cada camada tem I/O contracts explícitos em [`../specs/`](../specs/). Dependências fluem L0 → L8 com DAG cross-cycle documentado em [`../ARCHITECTURE.md`](../ARCHITECTURE.md) §6.

## Alternativas consideradas

- **9-layer explicit** ← escolhida. Emergiu por convergência durante specs P0-P5; cada L tem propósito distinto, I/O contracts testáveis, dependências explícitas.
- **5-layer v1-style** — rejeitada. Ambiguidade documentada em [`../MIGRATION_PLAN.md`](../MIGRATION_PLAN.md) §2.4; naming collision criou debt intractável.
- **7-layer (fundir L5 em L4 ou L6)** — rejeitada. Regimes são cenários cruzados com transition probabilities próprias; misturar em colunas L4 ou em L6 integration perderia distinção conceptual. Em v0.1 vivem como colunas booleanas em L4 por pragmatismo, mas a camada L5 é reservada e migração é Phase 2+.
- **Flat (sem layers)** — rejeitada. Solo operator, zero enforcement automático sem estrutura explícita; escala mal para >20 specs.

## Consequências

### Positivas

- I/O contracts formais por camada permitem paralelização de desenvolvimento (L2 implementável sem esperar L3).
- Testing localizado: cada layer tem fixtures próprios.
- Reasoning espacial: Hugo e Claude Code navegam "overlay NSS está em L2" sem ambiguidade.
- Specs precedem código em cada layer; template [`../specs/template.md`](../specs/template.md) enforced.

### Negativas / trade-offs aceites

- Verbosidade estrutural: 9 directórios em `sonar/` e em `docs/specs/` (Phase 1+). Custo aceitável para o scope.
- L5 regimes e L6 integration vazios em Phase 0-1; directórios reservados para namespace. Phase 2+ activa.

### Follow-ups requeridos

- Phase 1 cria `sonar/` com 9 subpackages conforme [`../REPOSITORY_STRUCTURE.md`](../REPOSITORY_STRUCTURE.md) §3 alvo.
- Novo overlay/index/cycle requer spec L-specific antes de código ([`../../CLAUDE.md`](../../CLAUDE.md) §4).
- ADR futuro requerido se decidir fundir ou separar camadas.

## Referências

- [`../ARCHITECTURE.md`](../ARCHITECTURE.md) §3 (9 camadas) + §6 (DAG + call-outs)
- [`../MIGRATION_PLAN.md`](../MIGRATION_PLAN.md) §2.4 (naming collision v1)
- [`../GLOSSARY.md`](../GLOSSARY.md) §4 Arquitectura
- [`../REPOSITORY_STRUCTURE.md`](../REPOSITORY_STRUCTURE.md) §3 (`sonar/` layout)
