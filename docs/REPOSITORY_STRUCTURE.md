# SONAR v2 — Repository Structure

**Status**: v2.0 · Phase 0 Bloco C em curso
**Última revisão**: 2026-04-18

Mapa navegável do repo SONAR v2. Onde vive o quê, sem redundância com [`ARCHITECTURE.md`](ARCHITECTURE.md) (que detalha camadas) ou [`ROADMAP.md`](ROADMAP.md) (que detalha fases).

## 1. Top-level

```
sonar-engine/
├── CLAUDE.md                 · pointer operacional para Claude Code (auto-loaded)
├── README.md                 · overview público (mínimo enquanto repo private)
├── Makefile                  · targets comuns (lint, test, run) · bootstrap inicial
├── pyproject.toml            · dependencies via uv · Phase 1+ activo
├── .env.example              · template secrets (real .env gitignored)
├── .gitignore
├── .pre-commit-config.yaml   · ruff + mypy + secret-scan hooks
├── .github/
│   └── workflows/            · ci.yml + daily-pipeline.yml (bootstrap; refinar Phase 1)
├── docs/                     · documentação (ver §2)
├── sonar/                    · código Python (ver §3)
├── tests/                    · pytest suite · Phase 1+ (a criar)
├── scripts/                  · utilitários ad-hoc (migrations, backfills) · Phase 1+ (a criar)
└── wiki/                     · páginas didáticas · v1 legacy, sync com GitHub Wiki Phase 3+
```

## 2. Estrutura de `docs/`

```
docs/
├── ARCHITECTURE.md                    · 9-layer canonical, DAG, padrões
├── ROADMAP.md                         · 5 fases, critério de saída por gate
├── REPOSITORY_STRUCTURE.md            · (este ficheiro)
├── MIGRATION_PLAN.md                  · lessons v1 → v2 (conceptual) · rewrite Bloco 4c
├── GLOSSARY.md                        · taxonomia canónica · a criar Bloco 4b
├── BRIEF_FOR_DEBATE.md                · 16 decisões pendentes; várias mapeiam a ADRs
│
├── adr/                               · Architecture Decision Records · a criar Bloco 5
│   ├── README.md                      · índice + template
│   ├── ADR-0001-linguagem.md
│   ├── ADR-0002-arquitectura-9-layer.md
│   ├── ADR-0003-db-path.md
│   └── ADR-0004-ai-collaboration.md
│
├── governance/                        · governança operacional · a criar Bloco 6
│   ├── README.md                      · índice
│   ├── WORKFLOW.md                    · branches, commits, PRs
│   ├── DOCUMENTATION.md               · onde vive o quê (docs/ vs wiki/ vs code)
│   ├── DECISIONS.md                   · quando criar ADR
│   ├── DATA.md                        · data governance, rate limits, secrets
│   └── AI_COLLABORATION.md            · Claude Code VPS + Claude chat roles
│
├── specs/                             · specs operacionais (source of truth) · DONE P0-P5
│   ├── template.md                    · template canónico (10 secções + §11)
│   ├── README.md                      · overview 9-layer
│   ├── conventions/                   · contratos partilhados FROZEN
│   │   ├── README.md
│   │   ├── flags.md                   · 100 flags catalog
│   │   ├── exceptions.md              · hierarquia SonarError (15 classes)
│   │   ├── units.md                   · decimal/bps/datas/timezones
│   │   ├── methodology-versions.md    · formato + bump rules
│   │   ├── patterns.md                · 3 padrões arquiteturais · a criar Bloco 7
│   │   ├── normalization.md           · clip formula · a criar Bloco 7
│   │   └── composite-aggregation.md   · fail-mode re-weighting · a criar Bloco 7
│   ├── overlays/                      · 5 specs L2
│   │   ├── nss-curves.md
│   │   ├── erp-daily.md
│   │   ├── crp.md
│   │   ├── rating-spread.md
│   │   └── expected-inflation.md
│   ├── indices/                       · 16 specs L3 (4 por ciclo) + 4 READMEs
│   │   ├── economic/                  · E1-4 + README
│   │   ├── credit/                    · L1-4 + README
│   │   ├── monetary/                  · M1-4 + README
│   │   └── financial/                 · F1-4 + README
│   ├── cycles/                        · 4 specs L4
│   │   ├── economic-ecs.md
│   │   ├── credit-cccs.md
│   │   ├── monetary-msc.md
│   │   └── financial-fcs.md
│   ├── pipelines/                     · 6 stubs L8 + master schedule README
│   │   ├── README.md
│   │   ├── daily-curves.md
│   │   ├── daily-overlays.md
│   │   ├── daily-indices.md
│   │   ├── daily-cycles.md
│   │   ├── weekly-integration.md
│   │   └── backfill-strategy.md
│   ├── integration/                   · L6 · vazio, Phase 2+
│   └── outputs/                       · L7 · vazio, Phase 3+
│
├── data_sources/                      · implementation plans · completar Bloco D Phase 0
│   ├── README.md
│   ├── economic.md
│   ├── credit.md
│   ├── monetary.md
│   └── financial.md
│
├── reference/                         · knowledge base v1 (manuais, contextual) · read-only
│   ├── README.md
│   ├── archive/                       · v1 artifacts preservados
│   │   ├── CODING_STANDARDS-v1.md
│   │   └── v1-code/                   · BaseConnector v1 + schema v18
│   │       ├── README.md
│   │       ├── connectors-base-v1.py
│   │       └── db-schema-v18.sql
│   ├── cycles/                        · 4 overviews
│   ├── indices/                       · 16 sub-indices extraídos
│   └── overlays/                      · 5 overlays + README
│
├── security/                          · security-related docs
│   └── incidents/                     · post-mortems de incidentes resolvidos
│       ├── README.md
│       └── 2026-04-17-pat-leak.md     · PAT leak bootstrap · HIGH · resolved
│
└── backlog/                           · backlogs não-roadmap · a criar Bloco 8
    ├── calibration-tasks.md           · 40 placeholders
    └── phase2-items.md                · itens Phase 2+ parkados
```

## 3. Estrutura de `sonar/`

Duas vistas: estado actual (Phase 0) e estrutura alvo (Phase 1+).

### Actual (Phase 0, pós-archive)

`sonar/` está vazia em Phase 0. Código v1 residual foi arquivado em `docs/reference/archive/v1-code/` (C1) e directórios vazios removidos (C2b, sem delta git — directórios vazios não são tracked). Phase 1 inicia a estrutura alvo abaixo.

### Alvo (Phase 1+)

```
sonar/
├── __init__.py
├── connectors/               · L0 — BaseConnector + implementations
├── db/                       · L1 — models SQLAlchemy + Alembic migrations
├── overlays/                 · L2 — 5 overlays (nss_curves/, erp_daily/, crp/, rating_spread/, expected_inflation/)
├── indices/                  · L3 — 16 indices
│   ├── economic/             ·   e1_activity/, e2_leading/, e3_labor/, e4_sentiment/
│   ├── credit/               ·   l1_credit_to_gdp_stock/, l2_credit_to_gdp_gap/, l3_credit_impulse/, l4_dsr/
│   ├── monetary/             ·   m1_effective_rates/, m2_taylor_gaps/, m3_market_expectations/, m4_fci/
│   └── financial/            ·   f1_valuations/, f2_momentum/, f3_risk_appetite/, f4_positioning/
├── cycles/                   · L4 — economic_ecs/, credit_cccs/, monetary_msc/, financial_fcs/
├── regimes/                  · L5 — Phase 2+ (v0.1 vive em colunas L4)
├── integration/              · L6 — Phase 2+
├── outputs/                  · L7 — CLI, API, editorial (Phase 2-3)
├── pipelines/                · L8 — orchestration
├── config/                   · pydantic-settings, env loading
└── core/                     · utilities (flags, exceptions, units, logging)
```

Naming: `snake_case` para packages e modules (EN); conforme [`CLAUDE.md`](../CLAUDE.md) §3.

## 4. Convenções de naming cross-repo

| Contexto | Convenção | Exemplo |
|---|---|---|
| Paths `docs/specs/` | `kebab-case.md` | `nss-curves.md`, `E1-activity.md` |
| Paths docs estratégicos (raiz `docs/`) | `UPPER_CASE.md` | `ARCHITECTURE.md`, `ROADMAP.md` |
| ADR filenames | `ADR-NNNN-kebab-case.md` | `ADR-0001-linguagem.md` |
| Python packages | `snake_case` | `sonar.overlays.nss_curves` |
| Python modules | `snake_case.py` | `base_connector.py`, `e1_activity.py` |
| Git branches | `type/kebab-case` | `feat/nss-curves`, `fix/e1-rolling` |
| Conventional Commits scope | lowercase singular | `architecture`, `specs`, `overlays` |
| SQL table names | `snake_case` plural/coherent | `yield_curves_spot`, `economic_cycle_scores` |

## 5. Paths com regra especial

- **`docs/specs/conventions/`** — FROZEN contract. Alteração = breaking change cross-spec. PR dedicado, review explícito. Ver [`CLAUDE.md`](../CLAUDE.md) §4.
- **`docs/reference/`** — read-only knowledge base importada de v1. Não editar in-place.
- **`.env`** — gitignored sempre. `.env.example` é template público. Nunca `cat .env` em output visível.
- **`data/`** — a criar Phase 1, gitignored. DB files, caches, downloads.
- **`scripts/sandbox/`** — opcional, gitignored, R&D exploratório. Não confundir com `scripts/` versionado.
- **`docs/reference/archive/`** — v1 artifacts preservados (código, docs obsoletos). Read-only; nunca editar in-place. Adicionar novos arquivos sim, modificar existentes não. Docs de `docs/reference/` que fiquem obsoletos migram para aqui com nota de replacement. Critério de remoção: Phase 2 completa.
- **`docs/security/incidents/`** — post-mortems de incidentes resolvidos, naming `YYYY-MM-DD-slug.md`. Incidentes activos em GitHub issues privadas, não aqui.
- **`wiki/`** (no repo) ≠ GitHub Wiki do mesmo repo. Conteúdo v1 legacy; sync manual com Wiki pública é Phase 3+ (decisão em BRIEF §14).

## 6. Onde não procurar o quê

Checklist anti-confusão:

- **Arquitectura conceptual** (camadas, padrões, DAG): [`ARCHITECTURE.md`](ARCHITECTURE.md), não este ficheiro.
- **Sequência de execução** (fases, gates): [`ROADMAP.md`](ROADMAP.md), não este ficheiro.
- **Decisões com rationale**: `docs/adr/` (a criar Bloco 5), não [`BRIEF_FOR_DEBATE.md`](BRIEF_FOR_DEBATE.md) (que contém apenas as decisões **pendentes**).
- **Taxonomia e definições**: [`GLOSSARY.md`](GLOSSARY.md) (a criar Bloco 4b), não prose dispersa em specs individuais.
- **Regras operacionais não-negociáveis**: [`CLAUDE.md`](../CLAUDE.md) (raiz) + [`governance/`](governance/) (a criar Bloco 6), não este ficheiro.
