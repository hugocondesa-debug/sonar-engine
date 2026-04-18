# ADR-0004: AI collaboration model

**Status**: Accepted
**Data**: 2026-04-18
**Decisores**: Hugo Condesa (solo operator)
**Consultados**: Claude chat (anthropic.com), Claude Code (VPS)

## Contexto

Hugo é solo operator sem equipa. Produtividade requer AI como multiplicador estruturado, não ad-hoc. Dois produtos Claude (Anthropic) têm papéis distintos: (a) **Claude chat** (claude.ai) — interface conversacional, stateless entre chats mas com project knowledge, bom para decisões arquiteturais + revisão + contexto alargado; (b) **Claude Code** (CLI no VPS) — agentic com tool use, corre no sistema de ficheiros real, bom para execução de tarefas estruturadas.

Em Phase 0, ambos foram usados em divisão de trabalho estável (specs, docs, cleanup) com resultados replicáveis. Decisão formaliza o padrão para que Bloco 6 `governance/AI_COLLABORATION.md` possa referenciar este ADR como fonte canónica.

## Decisão

Adoptamos **modelo colaborativo explícito em três papéis**:

- **Claude chat** (anthropic.com): decisões arquiteturais, desenho de prompts, review de outputs, resolução de ambiguidades, project context (`SESSION_CONTEXT.md`, externo ao repo).
- **Claude Code** (CLI no VPS `macro@46.225.168.251`): execução — criar/editar ficheiros, correr `grep`/`find`/`git`, aplicar `str_replace`, verificar output. Autenticado via `gh` CLI. **Nunca commit sem autorização explícita** ([`../../CLAUDE.md`](../../CLAUDE.md) §5).
- **Humano (Hugo)**: last mile — autoriza commits e push, resolve ambiguidades, aprova scope changes, decide trade-offs que requerem taste editorial.

## Alternativas consideradas

- **Modelo explícito (chat + Code + humano)** ← escolhida. Phase 0 validou o padrão; divisão clara de responsabilidades; rastreabilidade completa.
- **Só Claude chat com copy-paste manual** — rejeitada. Friction operacional alta; copy-paste introduz erros; Hugo dispensável como filtro em steps mecânicos.
- **Só Claude Code autónomo** — rejeitada. Decisões arquiteturais requerem contexto project-level + taste editorial que o agentic loop não tem sem prompt robusto; escala mal para multi-file decisions.
- **GitHub Copilot inline** — não rejeitada absolutamente; fica como opção complementar para Phase 1+ quando houver código substancial. Não é parte do workflow core.

## Consequências

### Positivas

- Divisão de trabalho auditável: cada edit tem signature clara (prompt Claude chat → execução Claude Code → approve Hugo → commit).
- Stack resiliente a falha de um componente: se Claude Code down, Hugo tem outputs prontos do chat para executar manualmente.
- Rastreabilidade: commits têm autor humano; prompts + decisões vivem em `SESSION_CONTEXT.md` (chat) e [`../../CLAUDE.md`](../../CLAUDE.md) (VPS).

### Negativas / trade-offs aceites

- Round-trips entre chat e VPS (copy/paste de prompts, scp ocasional): overhead ~30% vs fluxo single-agent. Aceitável: qualidade > velocidade.
- Dependência da Anthropic como vendor. Mitigação: prompts e outputs são prose/code portáveis a outro LLM se necessário.
- Hugo como bottleneck no commit gate: intencional, não bug.

### Follow-ups requeridos

- `docs/governance/AI_COLLABORATION.md` (Bloco 6) detalha este modelo operacionalmente (prompt patterns, QC workflow, failure modes, 2-3 exemplos concretos extraídos de Phase 0 Blocos 1-5).
- Re-avaliar ADR se Claude Code capabilities mudarem substancialmente (ex: autorização de commit via approval externa assinada).

## Referências

- [`../BRIEF_FOR_DEBATE.md`](../BRIEF_FOR_DEBATE.md) §15 AI assistance workflow
- [`../../CLAUDE.md`](../../CLAUDE.md) §5 Git rules (commit gate), §6 Tools
- `SESSION_CONTEXT.md` (external, claude.ai project knowledge) — log da divisão de trabalho Phase 0 Blocos 1-5
