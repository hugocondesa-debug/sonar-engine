# SONAR v2 — Roadmap

**Status**: v2.0 · Phase 0 Bloco C em curso
**Última revisão**: 2026-04-18

Sequência de fases SONAR v2. Sem datas absolutas — solo operator, critério de saída por fase é o gate. Fase seguinte arranca quando anterior satisfaz critério, não por calendário. Ficheiro live; revisão a cada phase gate.

## Princípios do roadmap

- **Ship-first**: vertical slice Phase 1 (L0 → L4 funcional num ciclo económico completo) antes de expandir horizontal Phase 2. Prova arquitectura, descobre friction.
- **Compute-before-calibrate**: placeholders declarados em specs ficam placeholders até ≥ 24m de production data existir para recalibração empírica. Recalibração é Phase 4, não antes.
- **Specs precede code**: cada fase tem specs mergeáveis como pre-requisito. Nenhum código novo sem spec aprovado.
- **Dependências respeitam 9-layer ordering**: L0 → L1 → L2 → L3 → L4 → L5 → L6 → L7 → L8. Pular camadas só quando documentado.
- **Out-of-scope explícito por fase**: evita scope creep e mantém gates tractable.
- **Discovery precede implementation**: nenhum connector em código sem spec de fonte completa em `docs/data_sources/`. Inventário exaustivo de endpoints, autenticação, rate limits, freshness, licensing é pre-requisito de Phase 1.

## Phase 0 — Bootstrap & Specs

**Foco**: documentação arquitectural + specs operacionais completos + contratos partilhados congelados.

**Critério de saída** (gate para Phase 1):

- Bloco A (Fundações): [`ARCHITECTURE.md`](ARCHITECTURE.md), [`CLAUDE.md`](../CLAUDE.md) done.
- Bloco B (Specs): 25 specs mergeadas em `docs/specs/` (commits `97ee9ae`, `1a66686`, `95744d3`) — **done 2026-04-18**.
- Bloco C (Documentação): ROADMAP (este), `REPOSITORY_STRUCTURE.md`, `MIGRATION_PLAN.md`, `GLOSSARY.md`, 4 ADRs P0 (linguagem Python 3.11+, arquitectura 9-layer, SQLite MVP → Postgres path, AI collaboration model), `docs/governance/` (6 ficheiros: README, WORKFLOW, DOCUMENTATION, DECISIONS, DATA, AI_COLLABORATION), `docs/specs/conventions/` novas (`patterns.md`, `normalization.md`, `composite-aggregation.md`), `docs/backlog/` (`calibration-tasks.md`, `phase2-items.md`), flags refactor (compression + namespace cleanup).
- Bloco D (Data Discovery): inventário exaustivo de fontes em `docs/data_sources/` — todas as séries necessárias para L2 + L3 + L4 catalogadas com endpoint, autenticação (API key / scrape / download), rate limit conhecido, freshness (latência), histórico disponível, coverage por país, licensing/TOS flag. Pré-requisito para primeiro connector de Phase 1.

**Scope**: zero código de produção. Apenas documentação + contratos partilhados + catalogação de fontes (sem ingestão).

**Out-of-scope nesta fase**: connectors (L0), db schema DDL aplicado (L1), overlays implementation (L2), qualquer módulo em `sonar/`.

**Dependências**: nenhuma (ponto de partida).

**Decisões pendentes**: — (Phase 0 resolve as decisões P0 via ADRs).

## Phase 1 — Vertical Slice End-to-End (L0 → L4)

**Foco**: um pipeline diário completo para 1 ciclo inteiro (Economic), estreito mas funcional — prova que 9-layer arquitectura corre end-to-end com composite + regime classification de verdade.

**Critério de saída** (gate para Phase 2):

- **L2**: `overlays/nss-curves` em produção diária, emitindo 4 curve families (spot/zero/forward/real) para US + PT.
- **L3**: 4 indices economic em produção diária (US + PT): `E1-activity`, `E2-leading`, `E3-labor`, `E4-sentiment` — Economic cycle completo.
- **L4**: `cycles/economic-ecs` em produção diária com composite real (4 indices), regime classification hysteresis funcional, overlay booleans (Stagflation/Boom/Dilemma triggers quando condições satisfeitas). Policy 1 re-weight testável mas não default path.
- **Cobertura**: 2 países (US + PT). PT como first-class PT-aware validation.
- **Persistência**: SQLite com schema canónico gerido via Alembic migrations. UNIQUE constraints enforced. `methodology_version` em toda row.
- **Testing**: pytest suite com ≥ 3 fixtures históricos PT (2009 DSR peak, 2012 CCCS distress, 2019 normalização) + US reference fixture.
- **Pipelines**: `daily-curves` + `daily-indices` + `daily-cycles` funcionais, orquestrados conforme decisão BRIEF §3.
- **CI/CD**: GitHub Actions básico — lint (ruff), type-check (mypy), tests (pytest), bloqueia merge se red.
- **Commits**: Conventional Commits em PT-PT enforced (commit-msg hook opcional).

**Scope**:

- `BaseConnector` abstract class + connectors necessários ao scope economic (FRED para US macro: yields, CPI, LEI, PMI, claims, unemployment, Sahm; IGCP para PT sovereign; BPStat/INE para PT macro equivalents; ECB SDW para EA reference; OECD para CLI). Lista exacta resulta do inventário Bloco D Phase 0.
- `sonar/db/` schema + Alembic migrations para tabelas L1 + L2 + L3 + L4 necessárias ao slice.
- `sonar/overlays/nss_curves/` implementation completa conforme [`specs/overlays/nss-curves.md`](specs/overlays/nss-curves.md).
- `sonar/indices/economic/` com 4 subpackages (`e1_activity/`, `e2_leading/`, `e3_labor/`, `e4_sentiment/`) conforme respectivos specs em [`specs/indices/economic/`](specs/indices/economic/).
- `sonar/cycles/economic_ecs/` conforme [`specs/cycles/economic-ecs.md`](specs/cycles/economic-ecs.md).
- `sonar/pipelines/` orchestration (APScheduler ou cron — ver decisão).
- `sonar/cli/` Typer stub (`sonar run daily-curves`, `sonar run daily-cycles`, `sonar query ecs --country=PT --date=latest`).

**Out-of-scope nesta fase**: os outros 4 overlays (ERP, CRP, rating-spread, expected-inflation), os outros 12 indices (L1-4, M1-4, F1-4), os outros 3 cycles (CCCS, MSC, FCS), L5 regimes como tabela própria (fica como colunas booleanas em ECS), L6 integration, L7 outputs além de CLI minimum, L8 `weekly-integration` e `backfill-strategy`.

**Dependências**: Phase 0 done (gate passado).

**Decisões pendentes**:

- [`BRIEF_FOR_DEBATE.md`](BRIEF_FOR_DEBATE.md) §3 — orchestrator (cron vs APScheduler vs Prefect); decidir antes de `daily-*` em produção.
- §7 — code quality tools (ruff + mypy + pytest confirmados; validar no primeiro PR de código).
- §10 — deployment scenario (VPS + GH Actions scheduled já definido); validar no primeiro daily run.

## Phase 2 — Horizontal Expansion (L2 – L4 completos)

**Foco**: cobertura completa de overlays + indices + cycles em velocity. Aproveitar padrões validados no vertical slice.

**Critério de saída** (gate para Phase 3):

- **L2 overlays** — 5 em produção: `nss-curves`, `erp-daily`, `crp`, `rating-spread`, `expected-inflation`.
- **L3 indices** — 16 em produção: E1-4, L1-4, M1-4, F1-4.
- **L4 cycles** — 4 em produção: ECS, CCCS, MSC, FCS.
- **Cobertura países** — 10-15 (T1 + T2: US, DE, UK, JP, FR, IT, ES, CA, AU, PT, IE, NL, SE, CH; T4 EM opcional caso-a-caso).
- **Postgres migration** — **condicional**; executar apenas se um dos gates [`ARCHITECTURE.md §10`](ARCHITECTURE.md) satisfeito (multi-user OR concurrent writes OR DB > 30 GB OR cloud 24/7 deployment). Se nenhum: ficar em SQLite e documentar decisão.
- **L5 regimes** — bootstrap: Stagflation, Boom, Dilemma, Bubble Warning migrados de colunas booleanas (v0.1) para tabela própria `regimes/` com `active`, `intensity`, `duration_days`. Transition probabilities começam a ser tracked.
- **F4 tier policy enforcement** — T1 required; T2-3 best-effort com `F4_COVERAGE_SPARSE`; T4 ignored.
- **F3 ↔ M4 divergence diagnostic** — `f3_m4_divergence` column persistida em `financial_cycle_scores`; `F3_M4_DIVERGENCE` flag emitted quando `|divergence| > 15`.
- **Walk-forward backtest infrastructure** — harness pronto mesmo sem calibração final aplicada (calibração é Phase 4). Permite correr backtests sob demanda.

**Scope**: implementation em velocity com padrões do vertical slice Phase 1. Specs já existem — é tradução para código.

**Out-of-scope nesta fase**: L6 integration full (`matriz-4way`, `diagnostics/`, `cost-of-capital`), L7 outputs rich (editorial pipeline, dashboard, alerts além de logs), calibração empírica de placeholders.

**Dependências**: Phase 1 done + padrões arquiteturais validados no vertical slice (normalization formula confirmada, hysteresis state machine testada, confidence propagation funcional).

**Decisões pendentes**:

- BRIEF §2 — Postgres migration trigger avaliado contra os 4 gates.
- §9 — testing strategy para scale (property tests expansion via hypothesis, integration test fixtures).

## Phase 3 — Integration & Outputs (L6 + L7)

**Foco**: composição cross-country / cross-cycle + consumo humano e machine.

**Critério de saída** (gate para Phase 4):

- **L6 matriz-4way** — classificação `ECS × CCCS × MSC × FCS → 16 estados canónicos + outliers` persistida diariamente.
- **L6 cost-of-capital** por país — composite `risk_free_country + β · ERP_mature + CRP_country` com β sourcing documentado, emitido para T1 + T2 + PT.
- **L6 diagnostics** — 4 composites: `bubble-detection` (FCS + BIS credit gap + BIS property gap), `minsky-fragility` (CCCS + DSR z-score), `real-estate-cycle` (property gap + mortgage rates + CRE REIT), `risk-appetite-regime` (F3 + VIX + credit spreads).
- **L7 CLI** — Typer completo: `sonar query`, `sonar export`, `sonar diagnose`, `sonar run <pipeline>`, `sonar replay <date-range>`.
- **L7 FastAPI** — JSON endpoints `/v1/cycles/{country}/{date}`, `/v1/overlays/{slug}/{country}/{date}`, `/v1/matriz-4way/{country}/{date}`, OpenAPI auto-gen.
- **L7 editorial pipeline** — angle detection (regime changes, overlay activations, cross-cycle patterns) + briefing generator + markdown templates para Substack ("A Equação").
- **L7 alerts** — threshold breach (CRP spikes, CAPE extremes), regime shifts (ECS → RECESSION, FCS → EUPHORIA), via email + Telegram.
- **Dashboard** — Streamlit MVP interno com páginas: overview, cycles status, overlay breakdown, cross-country comparison, regime timeline.

**Scope**: human + machine consumption. DB backend já decidido em Phase 2 (SQLite ou Postgres).

**Out-of-scope nesta fase**: React dashboard produção, MCP server reactivate, calibração empírica dos 40 placeholders, public wiki / OSS licensing move.

**Dependências**: Phase 2 done + ≥ 12m de production data acumulados em Phase 1-2 (permite editorial pipeline ter histórico para contextualizar).

**Decisões pendentes**:

- BRIEF §4 — dashboard tech (Streamlit confirmado MVP; React é Phase 4).
- §16 — editorial workflow (semi-automated: SONAR draft, Hugo edita voice).

## Phase 4 — Calibração Empírica & Scale

**Foco**: substituir placeholders por calibração real + production-grade ops + abertura condicional do projecto.

**Critério de saída** (não há Phase 5 formal — Phase 4 é steady state com backlog perpétuo):

- **40 placeholders recalibrados** com ≥ 24m production data: 20 index bands, 8 cycle weights + regime bands, 5 credit phase bands per country, 4 overlay params, 3 monetary params. Backlog operacional em [`backlog/calibration-tasks.md`](backlog/calibration-tasks.md).
- **Walk-forward backtests** executados:
  - ECS: hit-ratio vs NBER (US) + CEPR (EA), target ≥ 87% Pagan-Sossounov agreement.
  - FCS: Pagan-Sossounov bear/bull dating, bubble episodes 1998/2007/2021.
  - MSC: transition frequencies vs regime changes identificados (2004-06 Fed hike, 2013 taper tantrum, 2019 cut, 2022 hiking).
  - CCCS: crisis-prediction AUC vs Moody's default study events.
- **Cycle weights re-optimized** se backtest justificar MAJOR bump de `methodology_version` (ex: `ECS_COMPOSITE_v0.1` → `_v1.0` com rebackfill full).
- **Dashboard produção** — React/TypeScript, condicional a (a) fund launch OR (b) Streamlit limitations hit (performance, embedding, multi-user).
- **MCP server exposure** — cloudflared tunnel reactivate, endpoints `sonar.hugocondesa.com` + `mcp.hugocondesa.com`, autorização explícita requerida.
- **Repo visibility** re-avaliado conforme decisão de licensing.

**Scope**: maturação operacional + opcionalmente abertura do projecto (OSS / source-available / open-core).

**Out-of-scope nesta fase**:

- Expansão agressiva Tier 4 EM — fica oportunística, caso-a-caso. Não é fase.
- F3 ↔ M4 reconciliation v0.2 (shared source single normalization) — conditional a evidence de systematic drift > ad-hoc `F3_M4_DIVERGENCE` events.

**Dependências**: Phase 3 done + ≥ 24m mínimo de production data (contado desde Phase 1 go-live).

**Decisões pendentes**:

- BRIEF §5 — licensing (proprietary vs source-available vs open-core).
- §11 — repo visibility (private → public condicional).
- §13 — naming final (sonar vs sonar-engine vs sonar-core).
- §14 — docs strategy (repo `docs/` source + optional wiki mirror).
- §15 — AI assistance workflow maduro (Claude Code + Claude chat + Copilot opcional).

## Não-fases (backlog perpétuo fora do roadmap)

Itens que **não são fase** mas vivem como backlog oportunista, tratados quando evidence justificar:

- **F3 ↔ M4 reconciliation v0.2** — conditional a evidence de systematic drift entre `indices/monetary/M4-fci` e `indices/financial/F3-risk-appetite`; se `F3_M4_DIVERGENCE` flag fire > X% dos dias em janela 12m, abrir RFC para shared source.
- **Tier 4 EM deep coverage** — oportunística, caso-a-caso; driven por editorial demand ou client request, não roadmap.
- **Governance review cadence** — trimestral; vive em [`governance/REVIEW.md`](governance/REVIEW.md), não aqui.
- **Spec template evolution** — melhorias iterativas a [`specs/template.md`](specs/template.md) como aprendizagens acumulam.
- **Conventions catalog growth** — `flags.md`, `exceptions.md` crescem organicamente; PR dedicado por entrada.

## Mapping fase ↔ documentos

| Phase | Specs relevantes | Docs estratégicos | ADRs |
|---|---|---|---|
| 0 | [`conventions/`](specs/conventions/) (4 files) | `ARCHITECTURE.md`, `../CLAUDE.md`, este ROADMAP, `REPOSITORY_STRUCTURE.md`, `MIGRATION_PLAN.md`, `GLOSSARY.md` | ADR-0001 linguagem · ADR-0002 9-layer · ADR-0003 db path · ADR-0004 AI collab |
| 1 | [`overlays/nss-curves`](specs/overlays/nss-curves.md), [`indices/economic/`](specs/indices/economic/) (E1-E4), [`cycles/economic-ecs`](specs/cycles/economic-ecs.md), [`pipelines/daily-*`](specs/pipelines/) | `governance/WORKFLOW.md` | ADRs P1 (orchestrator final, CI/CD, schema versioning) |
| 2 | 5 overlays + 16 indices + 4 cycles completos | `governance/DATA.md` | ADRs P2 (Postgres gate, L5 regime schema, F4 tier enforcement) |
| 3 | [`integration/`](specs/integration/) (a criar), [`outputs/`](specs/outputs/) (a criar) | `governance/AI_COLLABORATION.md` | ADRs P3 (dashboard tech final, editorial workflow, alerts stack) |
| 4 | (sem specs novas — bumps MAJOR `methodology_version` em specs existentes) | [`backlog/calibration-tasks.md`](backlog/calibration-tasks.md) | ADRs P4 (licensing, repo visibility, MCP exposure) |

## Como este ficheiro é actualizado

`ROADMAP.md` é **live document**. Três tipos de update:

- **Phase gate satisfied** — atualizar header (status + última revisão) + mover fase done para referência histórica no topo do respectivo gate. Commit: `docs(roadmap): phase N gate passed`.
- **Scope move entre fases** — exige ADR. Commit: `docs(roadmap): move <item> de Phase N para Phase M (ADR-XXXX)`.
- **Cosmetic** (tipo, link, clarificação sem mudar scope) — directo. Commit: `docs(roadmap): clarify <subject>`.

Estado actual (2026-04-18): **Phase 0 Bloco C em curso**. Bloco A (Fundações) + Bloco B (Specs) done. Bloco C parcial — ARCHITECTURE (`0308cbf`), CLAUDE.md (`3a2f863`), ROADMAP (este commit pendente) done; REPOSITORY_STRUCTURE, MIGRATION_PLAN, GLOSSARY, ADRs, governance, conventions novas, backlog, flags refactor em fila. Bloco D (Data Discovery) pendente no final de Phase 0, antes de Phase 1 arrancar.
