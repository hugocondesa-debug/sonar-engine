# SONAR v2 — Roadmap

**Status**: Phase 2 em execução · M2 T1 Core ~90%
**Última revisão**: 2026-04-22

Sequência de fases SONAR v2. Sem datas absolutas — solo operator, critério de saída por fase é o gate. Fase seguinte arranca quando anterior satisfaz critério, não por calendário. Ficheiro live; revisão a cada phase gate.

**Revisão 2026-04-22**: consumer model clarificado (ver README §Consumidores). Phase 3 scope reframed em torno de L7 API + Website. Phase 2.5 introduzida como bridge preparatório. Editorial pipeline standalone, alerts email/Telegram, Streamlit dashboard MVP, PT-vertical trabalho dedicado — todos deprecated.

## Princípios do roadmap

* **Ship-first**: vertical slice antes de horizontal expansion. Engine interno funcional antes de camada externa.
* **Consumer-aligned priorities**: scope Phase 3+ driven por necessidades reais de Consumer A (MCP/API privado) + Consumer B (website público), não por feature catalog abstrato.
* **Compute-before-calibrate**: placeholders declarados em specs ficam placeholders até ≥ 24m de production data existir para recalibração empírica. Recalibração é Phase 4, não antes.
* **Specs precede code**: cada fase tem specs mergeáveis como pre-requisito.
* **Dependências respeitam 9-layer ordering**: L0 → L1 → L2 → L3 → L4 → L5 → L6 → L7 → L8. Pular camadas só quando documentado.
* **Cross-country uniform**: T1 coverage deve ser uniform; no country-privileged treatment.
* **Out-of-scope explícito por fase**: evita scope creep e mantém gates tractable.

## Phase 0 — Bootstrap & Specs — **COMPLETE** (2026-04-18)

Fundações + specs + data discovery + conventions frozen. Ver histórico em commits `97ee9ae`, `1a66686`, `95744d3` + Bloco D connector inventory.

## Phase 1 — Vertical Slice L0 → L4 + M1 US — **COMPLETE** (2026-04-20 Week 7)

M1 US single-country end-to-end declarado completo Week 7 Sprint G. 100% Phase 1 planned features shipped; ~70-75% spec catalog implementado. Deltas catalogados em [`docs/milestones/m1-us-gap-analysis.md`](milestones/m1-us-gap-analysis.md).

**Entregáveis**:
- L0: 22+ connectors operacionais
- L1: 16 Alembic migrations; SQLite MVP
- L2: 5/5 overlays shipped (US canonical)
- L3: 16/16 indices compute
- L4: 4/4 cycles operacionais com overlays
- L8: 9 daily pipelines operacionais

## Phase 2 — Horizontal Expansion (L2-L4 uniform T1 coverage) — **IN PROGRESS**

**Foco**: expansão geográfica + uniformidade T1 + cobertura cross-country genuína do engine interno.

**Critério de saída** (gate para Phase 2.5):

* **L2 overlays T1 uniform** — NSS curves, ERP, CRP, rating-spread, expected-inflation operacionais para 16 T1 countries (CAL-138 curves multi-country é blocker principal).
* **L3 indices T1 uniform** — 16 indices operacionais em 16 T1 countries (actualmente M1 completo; outros indices US-primary + partial EA).
* **L4 cycles T1 uniform** — 4 cycles operacionais em 16 T1 countries com composite + regime classification + overlays em todos.
* **Cobertura países T1** — 16 confirmados: US, DE, FR, IT, ES, NL, PT, GB, JP, CA, AU, NZ, CH, SE, NO, DK.
* **Per-country ERP live paths** — substituir `MATURE_ERP_PROXY_US` flag por per-market ERPInput assemblers (EA/GB/JP live; outros T1 priority).
* **Postgres migration** — **condicional**; executar apenas se um dos gates [`ARCHITECTURE.md §10`](ARCHITECTURE.md) satisfeito (multi-user OR concurrent writes OR DB > 30 GB OR cloud 24/7 deployment). Se nenhum: ficar em SQLite e documentar decisão.
* **F4 tier policy enforcement** — T1 required; T2-3 best-effort com `F4_COVERAGE_SPARSE`.
* **F3 ↔ M4 divergence diagnostic** — `f3_m4_divergence` column persistida; flag emitted quando `|divergence| > 15`.
* **Walk-forward backtest infrastructure** — harness pronto sem calibração final aplicada (calibração é Phase 4).

**Estado actual Week 9**: M1 monetary T1 uniform **shipped** (16 países). Outras camadas em progressão.

**Scope**: implementation em velocity com padrões do vertical slice Phase 1. Specs já existem — é tradução para código + expansion geográfica.

**Out-of-scope nesta fase**: L5 regime tabela dedicada, L6 integration full (matriz-4way, diagnostics, cost-of-capital cross-country), L7 API + Website, calibração empírica.

**Dependências**: Phase 1 done.

## Phase 2.5 — L5 Regimes + L6 Integration + L7 Infrastructure Prep — **NEW**

**Foco**: Phase 2 closeout + bridge preparatório para Phase 3 (API + Website).

**Critério de saída** (gate para Phase 3):

* **L5 regimes tabela dedicada** — migração de overlays booleanos em cycle scores para `regimes/` table com `active`, `intensity`, `duration_days`, `transition_probability`. Spec formal L5 (Phase 0 não definiu).
* **L6 matriz 4-way** — classificação `ECS × CCCS × MSC × FCS → 16 estados canónicos + outliers` persistida diariamente.
* **L6 cost-of-capital cross-country** — composite `risk_free_country + β · ERP_mature + CRP_country` para T1 + T2, com β sourcing documentado.
* **L6 diagnostics** — 4 composites: `bubble-detection`, `minsky-fragility`, `real-estate-cycle`, `risk-appetite-regime`.
* **Walk-forward backtests harness executados** — ECS vs NBER, FCS Pagan-Sossounov, MSC transition frequencies, CCCS AUC.
* **T2 coverage expansion** — 30 países T2 best-effort operational (IE, AT, BE, FI, GR + 25 outros).
* **OpenAPI spec v0.1** — contract draft para L7 API (schema stable antes de implementation).
* **L7 tech stack decisions** — MCP server framework, REST API framework (FastAPI confirmado), website tech stack (React/Next vs static SSG vs hybrid), auth model (API key private + public routes), hosting (VPS current vs CDN edge).

**Scope**: completion do engine interno (todas L1-L6 funcionais cross-country) + preparação contract + tech para L7 implementation.

**Out-of-scope**: L7 implementation propriamente dita (fica Phase 3), T3/T4 expansion (Phase 4).

**Dependências**: Phase 2 done.

## Phase 3 — L7 API + Website Launch — **PRIMARY UNLOCK MILESTONE**

**Foco**: tornar SONAR **useful externally**. Engine interno está closed — Phase 3 ship significa SONAR passa a ser consumido pelos dois consumidores reais.

**Critério de saída** (gate para Phase 4):

### Consumer A — MCP / API privado (Hugo DCF workflows)

* **MCP server live** — exposição via cloudflared tunnel `mcp.hugocondesa.com`, autorização explícita, endpoints:
  * `sonar.cost_of_capital(country, date)` — k_e composite
  * `sonar.yield_curve(country, date, tenor)` — NSS 4 families
  * `sonar.crp(country, date)` — Country Risk Premium
  * `sonar.rating_spread(rating, date)` — implied spread
  * `sonar.expected_inflation(country, date, tenor)` — term structure
  * `sonar.cycle_status(country, date)` — ECS/CCCS/MSC/FCS scores
  * `sonar.regime_active(country, date)` — overlay triggers
  * `sonar.matriz_4way(country, date)` — 16-state classification
  * `sonar.diagnostic(slug, country, date)` — bubble/minsky/real-estate/risk-appetite
* **REST API live** — FastAPI on `api.sonar.hugocondesa.com` (ou rota dedicada), JSON endpoints equivalentes a MCP, OpenAPI auto-gen em `/docs`.
* **Auth model** — API key em header; rate limit per key; private-vs-public endpoint distinction documented.
* **CLI upgrade** — Typer completo (`sonar query`, `sonar export`, `sonar diagnose`, `sonar replay <date-range>`).

### Consumer B — Website público (sonar.hugocondesa.com)

* **Website live** — frontend consumindo REST API interna, páginas:
  * **Home** — current cycle status across T1 countries + active regimes + recent transitions
  * **Cycles** — per-country ECS/CCCS/MSC/FCS timelines com overlay activations
  * **Curves** — NSS yield curves rendering + cross-country comparison
  * **Cost of capital** — k_e lookup por país + breakdown components (r_f + β·ERP + CRP)
  * **Matriz 4-way** — current state + historical heatmap
  * **Diagnostics** — 4 composites por país
  * **Methodology** — transparency pages (docs/methodology consumption)
  * **Editorial** — commentary triggered por regime shifts (não push/email, consumed ao visitar site)
* **Licensing de outputs** — decisão P3 ADR por dataset: quais outputs publishable (derived) vs API-only (per licensing constraints BIS/TE/paid sources).
* **Cloudflare tunnel reactivated** — `sonar.hugocondesa.com` + `mcp.hugocondesa.com` live.

### Infrastructure shared

* **Deployment pipeline** — CI/CD deploys API + website em commit-to-main.
* **Monitoring** — structured logs + basic health dashboard (uptime, request rate, error rate).
* **Versioning** — API v1 frozen; breaking changes via v2 prefix (not Phase 3 scope yet).

**Scope**: human + machine consumption. Dois consumers servidos por single API layer.

**Out-of-scope nesta fase**: calibração empírica dos 40 placeholders, public open-source transition (pending licensing ADR), alerts push (email/webhook — Phase 4 se justificar).

**Dependências**: Phase 2.5 done + ≥ 12 meses de production data acumulados (dá histórico suficiente para website timelines + editorial contextualization).

**Decisões pendentes**:
* BRIEF §4 — website tech stack final (React/Next vs static SSG)
* §5 — licensing (proprietary vs source-available vs open-core)
* §11 — repo visibility (Phase 4 decision; Phase 3 stays public as-is)
* §16 — editorial workflow (site-triggered content vs manual Hugo drafting)

## Phase 4 — Calibração Empírica & Scale

**Foco**: substituir placeholders por calibração real + production-grade ops + abertura condicional do projecto.

**Critério de saída** (não há Phase 5 formal — Phase 4 é steady state com backlog perpétuo):

* **40 placeholders recalibrados** com ≥ 24m production data: 20 index bands, 8 cycle weights + regime bands, 5 credit phase bands per country, 4 overlay params, 3 monetary params.
* **Walk-forward backtests** executados formalmente:
  * ECS: hit-ratio vs NBER (US) + CEPR (EA), target ≥ 87% Pagan-Sossounov agreement.
  * FCS: Pagan-Sossounov bear/bull dating, bubble episodes 1998/2007/2021.
  * MSC: transition frequencies vs regime changes (2004-06 Fed hike, 2013 taper tantrum, 2019 cut, 2022 hiking).
  * CCCS: crisis-prediction AUC vs Moody's default study events.
* **Cycle weights re-optimized** se backtest justificar MAJOR bump de `methodology_version`.
* **T3/T4 expansion** — coverage progressiva para ~50 países adicionais (EM focus).
* **Repo visibility** re-avaliado conforme decisão de licensing.
* **Alerts push** (opcional) — email + webhook se consumer demand justificar.

**Scope**: maturação operacional + production-hardened calibration + opcionalmente abertura do projecto.

**Out-of-scope nesta fase**:
* Expansão agressiva Tier 4 EM — oportunística, caso-a-caso.
* F3 ↔ M4 reconciliation v0.2 — conditional a evidence de systematic drift.

**Dependências**: Phase 3 done + ≥ 24m de production data (contado desde Phase 1 go-live 2026-04-15 approx; earliest 2028-Q2).

**Decisões pendentes**:
* BRIEF §5 — licensing final.
* §11 — repo visibility (private / public / hybrid).
* §13 — naming final.

## Deprecated (não são scope)

Items removidos após consumer model clarification (2026-04-22):

* **Editorial pipeline standalone** — substituído por website editorial pages
* **Alerts email + Telegram** — consumer model é pull (API + site), não push; defer Phase 4 conditional
* **Streamlit dashboard MVP** — skip; Phase 3 ship directly website público
* **PT Valuation Stack vertical dedicado** — T1 uniform coverage serves PT along with other T1
* **React dashboard interna** — Phase 3 website é o dashboard (público)

## Não-fases (backlog perpétuo fora do roadmap)

Itens que **não são fase** mas vivem como backlog oportunista:

* **F3 ↔ M4 reconciliation v0.2** — conditional a evidence de systematic drift.
* **T4 EM deep coverage** — oportunística, caso-a-caso; driven por API consumer demand.
* **Governance review cadence** — trimestral; vive em [`governance/REVIEW.md`](governance/REVIEW.md).
* **Spec template evolution** — iterativo.
* **Conventions catalog growth** — `flags.md`, `exceptions.md` crescem organicamente.

## Mapping fase ↔ documentos

| Phase | Specs relevantes | Docs estratégicos | ADRs |
| --- | --- | --- | --- |
| 0 | [`conventions/`](specs/conventions) | `ARCHITECTURE.md`, `../CLAUDE.md`, este ROADMAP, `REPOSITORY_STRUCTURE.md`, `MIGRATION_PLAN.md`, `GLOSSARY.md` | ADR-0001/2/3/4/5 |
| 1 | [`overlays/`](specs/overlays), [`indices/`](specs/indices), [`cycles/`](specs/cycles), [`pipelines/daily-*`](specs/pipelines) | `governance/WORKFLOW.md` | ADRs P1 |
| 2 | 5 overlays + 16 indices + 4 cycles T1 uniform | `governance/DATA.md` | ADRs P2 (Postgres gate, L5 regime schema, F4 tier) |
| 2.5 | [`integration/`](specs/integration) (a criar), regimes spec | OpenAPI draft | ADRs P2.5 (regime taxonomy, integration composites) |
| 3 | [`outputs/`](specs/outputs) (a criar), L7 API spec | `governance/AI_COLLABORATION.md` | ADRs P3 (API framework, website stack, editorial workflow, licensing by output) |
| 4 | (sem specs novas — bumps MAJOR) | [`backlog/calibration-tasks.md`](backlog/calibration-tasks.md) | ADRs P4 (licensing final, repo visibility, MCP exposure, push alerts) |

## Como este ficheiro é actualizado

`ROADMAP.md` é **live document**. Três tipos de update:

* **Phase gate satisfied** — atualizar header + histórico. Commit: `docs(roadmap): phase N gate passed`.
* **Scope move entre fases** — exige ADR. Commit: `docs(roadmap): move <item> de Phase N para Phase M (ADR-XXXX)`.
* **Consumer model revision** — exige strategic alignment check. Commit: `docs(roadmap): consumer model revised (YYYY-MM-DD)`.

Estado actual (2026-04-22 Week 9 Day 5): **Phase 2 em execução, M2 T1 Core ~90%**. Phase 1 complete Week 7. M2 T1 monetary expansion (CA/AU/NZ/CH/SE/NO/DK) Week 9 Day 5 arranque. Curves multi-country (CAL-138) + L3 T1 uniformity + L4 T1 uniformity são scope Phase 2 closeout.

**Próximos milestones visíveis**:
1. Week 9 Day 5 close — M2 T1 monetary complete (16 países)
2. Week 10 — CAL-138 curves multi-country sprint
3. Week 10-12 — L3 T1 uniformity + per-country ERP live paths
4. Week 13+ — L4 cycles T1 uniformity
5. Phase 2 gate — T1 uniform coverage completo (target Q3 2026)
6. Phase 2.5 gate — L5 regimes + L6 integration + OpenAPI spec (target Q4 2026)
7. **Phase 3 gate — L7 API + Website live (target Q1-Q2 2027)** — primary unlock milestone
8. Phase 4 — calibração empírica (gated 2028-Q2)
