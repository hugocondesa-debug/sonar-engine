# Governance

Camada de **processo operacional** entre ADRs (decisões estruturais canónicas) e specs (contratos técnicos). Responde "como trabalhar neste repo", não "o que é o repo" nem "porquê escolhemos X".

## Âmbito

Cinco documentos operacionais:

- [`WORKFLOW.md`](WORKFLOW.md) — branches, commits, PRs, code quality gates, CI, release tags.
- [`DOCUMENTATION.md`](DOCUMENTATION.md) — onde vive cada tipo de documentação (docs vs wiki vs code vs SESSION_CONTEXT).
- [`DECISIONS.md`](DECISIONS.md) — fluxo decisional (BRIEF → debate → ADR → spec/governance/code) e lifecycle.
- [`DATA.md`](DATA.md) — secrets, rate limits, backup, licensing, PII, data retention.
- [`AI_COLLABORATION.md`](AI_COLLABORATION.md) — operacional de ADR-0004 (prompt patterns, QC workflow, failure modes, exemplos Phase 0).

## Complementaridade das quatro camadas documentais

| Camada | Artefacto | Natureza | Exemplo |
|---|---|---|---|
| Arquitectura | [`../ARCHITECTURE.md`](../ARCHITECTURE.md) | O que é o sistema | 9-layer L0-L8 |
| Decisão estrutural | [`../adr/`](../adr/) | Porquê escolhemos X | ADR-0003 SQLite |
| Regra técnica | [`../specs/conventions/`](../specs/conventions/) | Contratos partilhados | `flags.md`, `methodology-versions.md` |
| Processo operacional | `docs/governance/` (este) | Como trabalhamos | `WORKFLOW.md` |

As quatro camadas são ortogonais. Informação vive no ficheiro canónico; outras camadas apontam, não duplicam.

## Quando actualizar governance

- Governance evolui com aprendizagem operacional, não a cada commit.
- Actualização material (nova regra, mudança de workflow) → commit `docs(governance): ...` dedicado.
- Typos ou links quebrados → commit normal.
- Mudança estrutural (ex: adoptar CI tool novo, trocar orchestrator) → ADR primeiro, governance reflecte depois.

## Cadence de review

Trimestral (placeholder — Phase 1+ activa). Hugo + Claude chat revêem governance contra friction observada em execução real. Failure modes novos em [`AI_COLLABORATION.md`](AI_COLLABORATION.md) acumulam como aprendizagem.

## Referências

- [`../adr/README.md`](../adr/README.md) — índice + critério "quando criar ADR".
- [`../../CLAUDE.md`](../../CLAUDE.md) — pointer operacional Claude Code.
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md) — arquitectura canónica.
- [`../ROADMAP.md`](../ROADMAP.md) — fases e gates.
