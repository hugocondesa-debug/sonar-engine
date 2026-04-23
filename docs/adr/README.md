# Architecture Decision Records

Registo formal de decisões arquiteturais com contexto, alternativas e consequências. Vivem em `docs/adr/`. Formato MADR-like adaptado (ver [`template.md`](template.md)).

## Formato

Todo ADR segue [`template.md`](template.md): header (Status, Data, Decisores, Consultados) + 5 secções fixas (Contexto, Decisão, Alternativas consideradas, Consequências, Referências). Ordem estável para scan rápido.

## Quando criar um ADR

**Criar ADR para**:

- Decisões estruturais (linguagem, DB, arquitectura, stack, governance).
- Escolhas com trade-offs explícitos entre ≥ 2 alternativas sérias.
- Decisões que constrangem opções futuras (lock-in técnico, vendor, arquitectural).
- Rescisão ou revisão de ADR anterior (via "Supersedes ADR-XXXX").

**NÃO criar ADR para**:

- Escolhas cosméticas (formatting, naming de variáveis internas).
- Fixes operacionais (correcção de bug, path stale, typo).
- Bumps de dependency versions triviais (patch/minor sem breaking change).
- Refactors que preservam contracts.

Este tipo de mudança vive em commits Conventional Commits ([`../ROADMAP.md`](../ROADMAP.md) §Princípios).

## Status lifecycle

- **Proposed** — em debate; não aplicar como canónico.
- **Accepted** — decisão canónica; aplica-se.
- **Superseded by ADR-XXXX** — substituída; ADR mais recente tem rationale + back-ref.
- **Deprecated** — já não aplica mas não foi formalmente substituída.

## Naming

`ADR-NNNN-kebab-case-slug.md` · `NNNN` zero-padded sequential, nunca reciclado.

## Índice

| # | Title | Status | Data | Summary |
|---|---|---|---|---|
| 0001 | [Linguagem Python 3.11+](ADR-0001-linguagem-python.md) | Accepted | 2026-04-18 | Python 3.11+ como linguagem primária; alternativas Julia/R/Rust/Go rejeitadas. |
| 0002 | [Arquitectura 9-layer](ADR-0002-arquitectura-9-layer.md) | Accepted | 2026-04-18 | Stack L0-L8 explícito com indices L3 + regimes L5 + pipelines L8 reificados. |
| 0003 | [DB path SQLite → Postgres](ADR-0003-db-path-sqlite-postgres.md) | Accepted | 2026-04-18 | SQLite MVP Phase 0-1; Postgres condicional Phase 2+ (4 gates explícitos). |
| 0004 | [AI collaboration model](ADR-0004-ai-collaboration-model.md) | Accepted | 2026-04-18 | Claude chat (decisões) + Claude Code (execução VPS) + humano always last mile. |
| 0005 | [Country tiers classification](ADR-0005-country-tiers-classification.md) | Accepted | 2026-04-18 | 4-tier T1-T4 classification conforme `country_tiers.yaml`; Phase 1 scheduling + fail-mode integration. |
| 0011 | [Systemd service idempotency + partial-persist recovery](ADR-0011-systemd-service-idempotency.md) | Accepted | 2026-04-23 | 5 princípios canónicos para pipelines scheduled: per-row idempotency, per-unit isolation, exit-code sanitization, summary emit, partial-persist recovery. |

## Workflow

- Nova decisão estrutural → draft em branch, PR dedicado para merge (solo operator: PR auto-review + push após QC).
- Revisão de ADR Accepted → criar ADR-NNNN novo com `Supersedes ADR-XXXX`; actualizar status do superseded.
- ADRs Accepted não se editam in-place (excepto typos / links quebrados); alterações materiais fazem-se via novo ADR.
- Cada ADR merged → actualizar este índice no mesmo commit.

## Referências

- [`template.md`](template.md) — template canónico.
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md) — arquitectura 9-layer (ADR-0002 é canonical source).
- `../governance/DECISIONS.md` — workflow operacional detalhado (a criar Bloco 6).
