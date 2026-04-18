# Phase 2+ items — backlog parkado

Items arquiteturais, operacionais e documentacionais deferidos para fases posteriores. Organizados por categoria temática. Cada item: descrição curta · target phase · dependency · critério de activação.

## Sumário por categoria

| Categoria | Count | Target phase dominante |
|---|---|---|
| Arquitectura | 4 | Phase 2-3 |
| Integration & outputs | 3 | Phase 3 |
| Infrastructure | 2 | Phase 4+ |
| Documentation | 3 | Phase 3+ |
| Data reconsiderations | 1 | Phase 3+ |
| Connectors unspeced | 1 | Phase 1-2 |

**14 items total** (P2-001 a P2-014).

## Arquitectura

### P2-001 — L5 Regimes migration (colunas L4 → tabela própria)

**Status**: pending
**Target phase**: Phase 2
**Descrição**: overlay booleans (Stagflation, Boom, Dilemma, Bubble Warning) vivem como colunas em `*_cycle_scores` em v0.1. Phase 2+ reifica como tabela `regimes/` com `active`, `intensity`, `duration_days`, transition probabilities.
**Dependency**: L4 cycles estáveis em produção (≥ 12m observations).
**Critério activação**: Phase 2 arranca OR ≥ 30 regime transitions observadas combinadas em ECS+CCCS+MSC+FCS.
**Decisão pendente**: transition probability model (Markov simples vs HMM vs empirical frequencies). Registar em ADR novo quando activar.

### P2-002 — F3 ↔ M4 reconciliation v0.2

**Status**: conditional
**Target phase**: Phase 2+ (evidence-dependent)
**Descrição**: `indices/monetary/M4-fci` e `indices/financial/F3-risk-appetite` consomem inputs parcialmente sobrepostos (NFCI, CISS, VIX). v0.1 lêem independentemente com z-scores próprios. v0.2 candidate: reconciliar para shared source com single normalization.
**Dependency**: `F3_M4_DIVERGENCE` flag tracked (persistido em v0.2 FCS scope).
**Critério activação**: se `F3_M4_DIVERGENCE` fire > X% de dias em janela rolling 12m (threshold X por definir, placeholder typical 15-20%), abrir RFC + decidir reconciliation. Se fire < X%, manter independentes (observability signal suficiente).

### P2-003 — Postgres migration gate review

**Status**: pending (conditional)
**Target phase**: Phase 2 final gate
**Descrição**: 4 gates documentados em [`../ARCHITECTURE.md`](../ARCHITECTURE.md) §10 e [`../adr/ADR-0003-db-path-sqlite-postgres.md`](../adr/ADR-0003-db-path-sqlite-postgres.md): (a) multi-user, (b) concurrent writes, (c) DB > 30 GB, (d) cloud 24/7. Phase 2 final tem review formal.
**Dependency**: Phase 2 scope complete.
**Critério activação**: gate review produz ADR novo — "Postgres migration decided" OR "SQLite retained Phase 3+".

### P2-004 — Cross-cycle composite `matriz-4way` (L6)

**Status**: pending
**Target phase**: Phase 3
**Descrição**: L6 integration layer com classificação canonical `ECS × CCCS × MSC × FCS → 16 estados canónicos + outliers`. Directório `docs/specs/integration/` actualmente vazio.
**Dependency**: L4 cycles em produção ≥ 6m.
**Critério activação**: Phase 3 arranca.

## Integration & outputs

### P2-005 — L6 `cost-of-capital` composite

**Status**: pending
**Target phase**: Phase 3
**Descrição**: composite per country `cost_of_equity_country = risk_free_country + β·ERP_mature + CRP_country`. β sourcing documentado (placeholder — decisão entre raw/Blume/Vasicek adjusted).
**Dependency**: overlays NSS + ERP + CRP estáveis (Phase 2 complete).

### P2-006 — L6 `diagnostics/` composites

**Status**: pending
**Target phase**: Phase 3
**Descrição**: 4 composites diagnostic em [`../specs/integration/`](../specs/integration/) (a criar Phase 3): `bubble-detection` (FCS + BIS credit gap + property gap), `minsky-fragility` (CCCS + DSR z-score), `real-estate-cycle` (property gap + mortgage rates + CRE REIT), `risk-appetite-regime` (F3 + VIX + credit spreads).

### P2-007 — L7 outputs rich (CLI + API + editorial + alerts + dashboard)

**Status**: pending
**Target phase**: Phase 3
**Descrição**: 5 sub-systems — Typer CLI completo, FastAPI JSON endpoints, editorial pipeline (angle detection + briefing generator + markdown templates para Substack), alerts (threshold breach, regime shift via email/Telegram), Streamlit dashboard MVP interno.
**Dependency**: L4 + L6 estáveis.
**Decisão pendente**: BRIEF §4 dashboard tech (Streamlit MVP confirmed; React Phase 4+ conditional).

## Infrastructure

### P2-008 — MCP server exposure (Cloudflare tunnel)

**Status**: pending
**Target phase**: Phase 4+
**Descrição**: `cloudflared` tunnel preservado em `/etc/cloudflared/` (inactive). Hostnames `sonar.hugocondesa.com` + `mcp.hugocondesa.com`. Reactivate quando L7 outputs em produção.
**Dependency**: L7 FastAPI + MCP server implementado.
**Critério activação**: autorização explícita do Hugo + L7 estável.

### P2-009 — React/TypeScript dashboard produção

**Status**: conditional
**Target phase**: Phase 4+
**Descrição**: substituto Streamlit MVP. Conditional a (a) fund launch OR (b) Streamlit limitations hit (performance, embedding, multi-user).
**Decisão pendente**: ADR novo quando activar.

## Documentation

### P2-010 — README.md raiz rewrite

**Status**: pending
**Target phase**: Phase 3+ (quando repo for considerado para público)
**Descrição**: `README.md` actual tem 3 refs stale detectadas no Bloco 4a: linha 92 (`sonar/submodels/`), linha 118 e 149 (`CODING_STANDARDS.md`). Phase 3+ rewrite quando repo visibility re-avaliada.
**Dependency**: ADR de licensing (BRIEF §5) + visibility (BRIEF §11).

### P2-011 — Wiki público sync

**Status**: pending
**Target phase**: Phase 3+
**Descrição**: `wiki/` no repo (v1 legacy, 9 ficheiros com naming pré-rename) ≠ GitHub Wiki do repo. Sync manual quando conteúdo conceptual for aberto publicamente.
**Dependency**: decisão licensing (BRIEF §5, ADR futuro).

### P2-012 — ASCII DAG alignment (cosmético)

**Status**: micro-débito
**Target phase**: oportunista
**Descrição**: diagrama DAG em `ARCHITECTURE.md §6` tem caracteres box-drawing (`├`, `│`, `└`, `─`) ligeiramente desalinhados após edit B6 do Bloco 1 (rename `L1 L2 L3 L4` → `credit/L1 credit/L2 credit/L3 credit/L4`). Monospaced renderers continuam legíveis; débito registado mas não bloqueante.

## Data reconsiderations

### P2-013 — DuckDB analytics read-only

**Status**: conditional
**Target phase**: Phase 3+ (reconsideration)
**Descrição**: DuckDB considerado e rejeitado para MVP em [`../adr/ADR-0003-db-path-sqlite-postgres.md`](../adr/ADR-0003-db-path-sqlite-postgres.md) (maturity SQLAlchemy menor, migration path indirecto). Reconsideration Phase 3+ para read-only analytics sobre dados persistidos — ADR novo nessa altura.
**Dependency**: dados persistidos em Postgres OR SQLite (Phase 2 gate decidido).

## Connectors unspeced

### P2-014 — Communication Signal connectors

**Status**: pending
**Target phase**: Phase 1+ (MSC CS component)
**Descrição**: `connectors/central_bank_nlp`, `connectors/fed_dissent`, `connectors/dot_plot` mencionados em [`../ARCHITECTURE.md`](../ARCHITECTURE.md) §6 call-out "CS de MSC" mas não speced. Em Phase 0-1, `COMM_SIGNAL_MISSING` é expected default; MSC aplica Policy 1 re-weight sem bloquear.
**Dependency**: Phase 1 MSC em produção com `COMM_SIGNAL_MISSING` baseline; Phase 2+ decide se CS merece specs formais ou continua opcional.

## Workflow de desparking

1. Item reaches target phase OR critério satisfeito.
2. Item escalated: PR dedicado cria spec (se aplicável) OR ADR (se decisão estrutural) OR código (se implementation).
3. Este ficheiro actualiza: status pending → in-progress → done.
4. Item `cancelled`: rationale obrigatório + preserva-se no registo.

## Referências

- [`../ROADMAP.md`](../ROADMAP.md) §Phase 2-4 + §Não-fases
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md) §10 Out-of-scope
- [`../BRIEF_FOR_DEBATE.md`](../BRIEF_FOR_DEBATE.md) — decisões pendentes que alimentam items
- [`calibration-tasks.md`](calibration-tasks.md) — sister doc, calibração empírica
