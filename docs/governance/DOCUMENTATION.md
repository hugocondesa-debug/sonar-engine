# Documentation

Onde vive cada tipo de documentação. Resposta canónica a "devo pôr isto em `docs/`, `wiki/`, código ou `SESSION_CONTEXT`?"

## Princípio

Informação vive **o mais próximo possível do código/contrato que governa**. Specs em `docs/specs/`, ADRs em `docs/adr/`, comments em código para o que é local a uma função. Tudo replicado em 2 sítios é debt — uma fonte canónica, outras apontam.

## Tabela de decisão

| Tipo de informação | Onde vive | Exemplo |
|---|---|---|
| Arquitectura (camadas, DAG) | [`../ARCHITECTURE.md`](../ARCHITECTURE.md) | 9-layer, cross-cycle deps |
| Sequência de fases | [`../ROADMAP.md`](../ROADMAP.md) | Phase 0-4 gates |
| Spec operacional (algoritmo) | [`../specs/{overlays,indices,cycles}/`](../specs/) | NSS fitting algorithm |
| Contrato partilhado (flags, exceptions) | [`../specs/conventions/`](../specs/conventions/) | `flags.md` |
| Decisão estrutural com rationale | [`../adr/`](../adr/) | ADR-0003 SQLite |
| Governance operacional | `docs/governance/` | este ficheiro |
| Knowledge base v1 (conceptual) | [`../reference/`](../reference/) | manuais conceptuais |
| Backlog (calibração, Phase 2+) | `docs/backlog/` (a criar Bloco 8) | 40 placeholders |
| Taxonomia | [`../GLOSSARY.md`](../GLOSSARY.md) | definições canónicas |
| Inventário de fontes | [`../data_sources/`](../data_sources/) | endpoints FRED, IGCP, BIS |
| Contexto chat (projecto, sessões) | `SESSION_CONTEXT.md` em Claude.ai (externo) | histórico decisões + infra VPS |
| Pointer operacional Claude Code | [`../../CLAUDE.md`](../../CLAUDE.md) (raiz) | regras + ordem consulta |
| Comments de implementação | inline no código | porquê um edge case |
| Docstrings (Python) | inline | API pública de funções |
| Page didáctica / tutorial | `wiki/` (repo) ≠ GitHub Wiki | v1 legacy, sync Phase 3+ |
| Post-mortems de incidentes | [`../security/incidents/`](../security/incidents/) | `2026-04-17-pat-leak.md` |
| Relatório de bug Phase 1+ | GitHub issue | — |

## Anti-patterns

- **Duplicar regras** em 2 ficheiros. Ex: convenção de naming em `CLAUDE.md` + `REPOSITORY_STRUCTURE.md` + `WORKFLOW.md`. Uma fonte, outras apontam.
- **Docs em chat/DMs/emails**. Se é decisão, merece ADR. Se é processo, governance. Se é contexto de sessão, `SESSION_CONTEXT.md`.
- **Stale refs** a paths antigos. Quando algo move, `grep -rn old_path docs/` + update refs no mesmo commit (precedente: Bloco 4a C1+C2+C2c fix cluster).
- **Prose redundante com config**. Ex: documentar regras `ruff` em prose quando `pyproject.toml` é source of truth.
- **ADR sem follow-up**. ADR Accepted deve ter follow-ups concretos em specs/governance/código que implementam a decisão.

## `SESSION_CONTEXT.md` — regra especial

Vive **externo ao repo** (Claude.ai project knowledge). Contém:

- Contexto de projecto (7365 Capital, infra VPS, decisões de alto nível).
- Log de sessões (decisões conversacionais não consagradas em ADR).
- Pointers a workflow operacional Claude chat ↔ Claude Code (canonical em ADR-0004 + [`AI_COLLABORATION.md`](AI_COLLABORATION.md)).

**Não é source of truth canónica.** Se algo matura em `SESSION_CONTEXT`, migra para `docs/` conforme natureza (ADR, governance, ou spec). Claude Code **não tem acesso** a `SESSION_CONTEXT.md` — Hugo transcreve contexto relevante.

## Wiki: repo `wiki/` vs GitHub Wiki

- **`wiki/`** dentro do repo: ficheiros markdown versionados com código. Phase 0-1: v1 legacy, effectively read-only. Conteúdo desactualizado (nomenclatura pré-9-layer).
- **GitHub Wiki** (https://github.com/hugocondesa-debug/sonar-engine/wiki): público, actualmente não populado.
- **Sync entre os dois**: Phase 3+ decisão (BRIEF §14). Por agora, `wiki/` repo é arquivo histórico v1.

## Lifecycle documentacional

- **Docs estratégicos top-level** (`ARCHITECTURE`, `ROADMAP`, `GLOSSARY`, `MIGRATION_PLAN`, `REPOSITORY_STRUCTURE`): live documents. Revisão a cada phase gate.
- **Specs operacionais** ([`../specs/`](../specs/)): live pre-implementation; effective-frozen após primeira implementação (rewrite requer bump `methodology_version`).
- **ADRs Accepted**: read-only (excepto typos / links quebrados). Revisões materiais via Supersede ([`DECISIONS.md`](DECISIONS.md)).
- **Governance**: actualização material → commit `docs(governance)` dedicado. Não a cada commit.
- **Reference (v1)**: read-only permanente. Adicionar arquivos sim, modificar existentes não ([`../REPOSITORY_STRUCTURE.md`](../REPOSITORY_STRUCTURE.md) §5).
- **Incidents**: post-mortems read-only uma vez fechados.

## Referências

- [`../../CLAUDE.md`](../../CLAUDE.md) §2 ordem de consulta.
- [`../REPOSITORY_STRUCTURE.md`](../REPOSITORY_STRUCTURE.md) §2 mapa completo `docs/`.
- [`DECISIONS.md`](DECISIONS.md) — fluxo ADR vs spec vs governance.
- [`WORKFLOW.md`](WORKFLOW.md) — commit types + scopes para `docs(…)`.
