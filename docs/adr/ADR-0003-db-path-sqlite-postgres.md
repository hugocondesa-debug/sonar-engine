# ADR-0003: DB path SQLite → Postgres

**Status**: Accepted
**Data**: 2026-04-18
**Decisores**: Hugo Condesa (solo operator)
**Consultados**: Claude chat (anthropic.com), Claude Code (VPS)

## Contexto

SONAR v2 MVP é single-user research com pipeline batch diário. Volume estimado Phase 1 (2 países × 4 indices × 1 cycle × 10Y daily): < 1 GB. Volume Phase 2 (10-15 países × 5 overlays × 16 indices × 4 cycles × 10Y daily): estimativa < 10 GB. Zero concurrent writes (single operator + CI GitHub Actions sequencial). Backup é trivial se file-based (`cp *.db`).

V1 usou SQLite com sucesso até ao limite de schema drift cross-ciclo (não limite de DB engine, mas de contract). DuckDB foi considerado por analytical queries mas maturity + ecosystem SQLAlchemy menor. Decisão precisa ser tomada agora porque Phase 1 arranca com Alembic migrations + schema DDL em `sonar/db/`.

## Decisão

Adoptamos **SQLite como DB primário para Phase 0-1**. Postgres migration é conditional Phase 2+ sob gates específicos em [`../ARCHITECTURE.md`](../ARCHITECTURE.md) §10: (a) multi-user, (b) concurrent writes, (c) DB > 30 GB, (d) cloud 24/7 deployment. Se nenhum gate satisfeito quando Phase 2 completa, manter SQLite com ADR novo documenting decisão.

## Alternativas consideradas

- **SQLite** ← escolhida para MVP. File-based trivial; SQLAlchemy 2.0 + Alembic compatível; backup = `cp`; zero setup operacional.
- **PostgreSQL desde Phase 1** — rejeitada. Overhead operacional (setup, backup complexity, connection pooling, service management) não justificado sem concurrent writes ou multi-user. Migração forçada quando os gates dispararem, não antes.
- **DuckDB** — atraente para analytical queries; ecosystem SQLAlchemy menos maduro; migration path para Postgres menos directo que SQLite → Postgres. Pode ser reconsiderada Phase 3+ para read-only analytics sobre dados persistidos (ADR novo nessa altura).

## Consequências

### Positivas

- Zero infra: Phase 1 arranca sem deploy de service de DB.
- Backup trivial: `cp *.db` → S3/B2. Rotas de recuperação simples.
- SQLAlchemy 2.0 + Alembic abstrai engine; migration futura para Postgres é relativamente indolor (dialect-level, não schema-level).

### Negativas / trade-offs aceites

- Concurrent writes bloqueantes. Aceitável: single writer + single reader, sem concurrency real.
- Analytical query performance inferior a DuckDB/Postgres em full-table scans grandes. Mitigação: daily batch size é < 10k rows persistidas em Phase 1-2.
- Migration futura a Postgres tem custo, embora delimitado por design (SQLAlchemy agnóstica + Alembic migrations reutilizáveis com dialect swap).

### Follow-ups requeridos

- Phase 1: Alembic migrations desde o primeiro model; zero DDL manual fora de migrations.
- Phase 1: `pyproject.toml` inclui `sqlalchemy>=2.0`, `alembic`.
- Phase 1: `docs/governance/DATA.md` (Bloco 6) documenta backup strategy específica SQLite.
- Phase 2 gate review: avaliar as 4 condições de [`../ARCHITECTURE.md`](../ARCHITECTURE.md) §10 e emitir ADR novo (`ADR-00NN: Postgres migration decided` OU `ADR-00NN: SQLite retained for Phase 2+`).

## Referências

- [`../BRIEF_FOR_DEBATE.md`](../BRIEF_FOR_DEBATE.md) §2 Database choice
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md) §3 L1 + §10 Out-of-scope (Postgres gates)
- [`../ROADMAP.md`](../ROADMAP.md) §Phase 2 Horizontal Expansion (gate avaliação)
