# Decisões — fluxo e lifecycle

Como uma decisão nasce, matura, consagra-se e é referenciada. Complementa [`../adr/README.md`](../adr/README.md) (critério "quando criar ADR") com workflow operacional.

## Quatro artefactos, uma vida

Uma decisão estrutural passa tipicamente por quatro artefactos:

1. **[`../BRIEF_FOR_DEBATE.md`](../BRIEF_FOR_DEBATE.md)** — onde decisões nascem como *open question*. Formato: problema, alternativas, recomendação, campo "Decision: ___" vazio. Sem compromisso.
2. **Claude chat (sessão)** — debate, trade-offs, escolha. Vive em `SESSION_CONTEXT.md` enquanto não consagrada.
3. **ADR-NNNN** — consagração formal. `Status: Accepted`, rationale, alternativas rejeitadas, consequências, follow-ups.
4. **Spec / governance / code** — implementação. Refere ADR como canonical source ("conforme ADR-0003").

## Quando escalar para ADR

Criar ADR quando decisão:

- Constrange opções futuras (lock-in técnico, vendor, arquitectural).
- Tem ≥ 2 alternativas sérias com trade-offs explícitos.
- É estrutural (linguagem, DB, arquitectura, stack, governance processual).
- Revoga ou revê ADR anterior.

**Não** criar ADR para:

- Fixes (path stale, typo, dependency patch sem breaking change).
- Cosmético (formatting, naming de variáveis internas).
- Refactors que preservam contract.

## Fluxo operacional — caminho canónico

```
[open question emerge]
  ↓
BRIEF_FOR_DEBATE.md §N · "Decision: ___"
  ↓
Claude chat debate (Hugo + AI) → escolha
  ↓
ADR-NNNN draft · Status: Proposed
  ↓
Hugo review → Status: Accepted · commit docs(adr): ...
  ↓
Spec / governance / código referem ADR-NNNN
  ↓
BRIEF_FOR_DEBATE.md §N · "Decision: ADR-NNNN · YYYY-MM-DD"
```

## Fluxo alternativo — lightweight (decisão emergente)

Quando decisão emerge durante execução sem passar por BRIEF:

```
[decisão reconhecida em chat/execução]
  ↓
Hugo identifica impacto estrutural
  ↓
ADR-NNNN directo · Status: Accepted
  ↓
BRIEF_FOR_DEBATE.md actualizado (adicionar § se não existia)
```

Exemplo Phase 0: ADR-0002 (arquitectura 9-layer) emergiu por convergência durante specs P0-P5, não como open question pré-debate.

## Superseding

Quando ADR-A precisa revisão:

1. Criar ADR-B com `Status: Accepted` + `Supersedes ADR-A` no header.
2. ADR-B §Contexto: porque ADR-A já não aplica + lessons aprendidas.
3. Actualizar ADR-A: `Status: Superseded by ADR-B`.
4. **Single commit** cobre ambos os ficheiros + actualização do índice [`../adr/README.md`](../adr/README.md).

ADRs **não se deletam**. Histórico de decisões é valor auditável permanente.

## Actualizar BRIEF_FOR_DEBATE.md

- Decisão consagrada em ADR → campo `Decision: ADR-NNNN · YYYY-MM-DD` no § correspondente.
- Nova decisão pendente descoberta → adicionar novo §.
- Decisão revogada → marcar `Superseded by ADR-NNNN`.

`BRIEF` é live document que cresce com o projecto. Não reescrever — append + reference.

## Distinção rápida — onde procurar o quê

| Pergunta | Artefacto | Scope |
|---|---|---|
| "O que é esta camada?" | [`../ARCHITECTURE.md`](../ARCHITECTURE.md) ou spec | técnico descritivo |
| "Porquê escolhemos SQLite?" | ADR-0003 | estrutural — com rationale |
| "Que contratos partilhamos?" | [`../specs/conventions/`](../specs/conventions/) | técnico canónico |
| "Como fazemos commits?" | [`WORKFLOW.md`](WORKFLOW.md) | processo operacional |
| "Onde vive spec de cycle?" | [`../REPOSITORY_STRUCTURE.md`](../REPOSITORY_STRUCTURE.md) | mapa |
| "Quando criar ADR?" | este ficheiro + [`../adr/README.md`](../adr/README.md) | processo decisional |
| "Como colabora AI?" | ADR-0004 + [`AI_COLLABORATION.md`](AI_COLLABORATION.md) | processo operacional |

## Referências

- [`../adr/README.md`](../adr/README.md) — índice ADRs + critério "quando criar".
- [`../BRIEF_FOR_DEBATE.md`](../BRIEF_FOR_DEBATE.md) — decisões abertas.
- [`../../CLAUDE.md`](../../CLAUDE.md) §2 ordem de consulta.
- [`DOCUMENTATION.md`](DOCUMENTATION.md) — onde vive cada tipo de info.
- [`WORKFLOW.md`](WORKFLOW.md) — commits para aplicar decisões.
