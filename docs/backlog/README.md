# Backlog

Inventários canónicos de dívida consciente — items diferidos com racional + critério de activação. **Não é backlog Agile**; é registo auditável para auto-Hugo+12m, Claude Code em sessão fresca, auditor.

## Ficheiros

- [`calibration-tasks.md`](calibration-tasks.md) — **20 placeholders** declarados em specs P3-P5, agrupados por horizonte de recalibração. Phase 4 é gate de activação (≥ 24m production data para maioria).
- [`phase2-items.md`](phase2-items.md) — 14 items arquiteturais/operacionais parkados para Phase 2+, organizados por categoria (arquitectura, integration, outputs, infra, docs, data, connectors).

## Convenções dos inventários

- **ID estável**: `CAL-NNN` para calibração, `P2-NNN` para phase2. Sequential zero-padded, nunca reciclados.
- **Status enum**: `pending` (default) / `in-progress` / `done` / `cancelled` (com rationale).
- **Critério de activação explícito** — "≥ 24m production data", "Phase 2 completa", "evidence de X", etc.
- **Spec owner** (calibration) ou **target phase** (phase2) como referência canónica.

## Lifecycle

Items tornam-se actionable quando critério de activação satisfeito. Trabalho real → PR dedicado que actualiza status + regista valor final/decisão + linka o commit. Items `cancelled` permanecem no registo com rationale; nunca apagados.

## Referências

- [`../ROADMAP.md`](../ROADMAP.md) §Phase 2-4 gates
- [`../governance/DECISIONS.md`](../governance/DECISIONS.md) — quando calibração empírica exige ADR (ex: MAJOR bump `methodology_version`).
