# SONAR v2 — Repository Structure

Proposta de layout completo, com rationale para cada secção principal.

## Tree proposto

```
sonar/
│
├── README.md                       # Project overview + quick start
├── LICENSE                          # TBD (see BRIEF_FOR_DEBATE)
├── SECURITY.md                      # Security policy + vulnerability reporting
├── CHANGELOG.md                     # Human-readable version history
├── BRIEF_FOR_DEBATE.md             # Key decisions pending (archive once resolved)
│
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                   # Lint + test on push/PR
│   │   ├── daily-pipeline.yml       # Scheduled daily run (if using GitHub Actions)
│   │   ├── weekly-validation.yml    # Weekly cross-validation
│   │   └── release.yml              # Tagged releases
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   ├── feature_request.md
│   │   ├── new_country.md           # Template for adding country
│   │   └── new_connector.md         # Template for adding data source
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── dependabot.yml               # Auto-dep-updates
│   └── CODEOWNERS                   # Review assignments
│
├── .gitignore
├── .env.example                     # Template for environment variables
├── .pre-commit-config.yaml          # Pre-commit hooks
├── .editorconfig                    # Consistent editor settings
├── pyproject.toml                   # Build + dependencies + tool config
├── uv.lock or poetry.lock           # Lockfile (choose one tool)
├── Makefile                         # Common commands
│
├── docs/                            # Documentation (source of truth)
│   ├── README.md                    # Docs index
│   │
│   ├── architecture/
│   │   ├── ARCHITECTURE.md          # Main technical architecture
│   │   ├── REPOSITORY_STRUCTURE.md  # This file
│   │   ├── CODING_STANDARDS.md
│   │   ├── SECURITY.md
│   │   └── adr/                     # Architecture Decision Records
│   │       ├── 0001-language-choice.md
│   │       ├── 0002-database-choice.md
│   │       └── ...
│   │
│   ├── methodology/                 # Core source of truth — from v1 manuals
│   │   ├── README.md
│   │   ├── cycles/
│   │   │   ├── credit/              # Credit cycle manual content (migrated from v1)
│   │   │   ├── monetary/
│   │   │   ├── economic/
│   │   │   └── financial/
│   │   └── submodels/
│   │       ├── yield_curves.md
│   │       ├── erp.md
│   │       ├── crp.md
│   │       ├── rating_spread.md
│   │       └── expected_inflation.md
│   │
│   ├── data_sources/                # Operational plans
│   │   ├── credit_plan.md
│   │   ├── monetary_plan.md
│   │   ├── economic_plan.md
│   │   ├── financial_plan.md
│   │   └── submodels_plan.md
│   │
│   ├── operations/
│   │   ├── DAILY_PIPELINE.md
│   │   ├── BACKUP_RESTORE.md
│   │   ├── MONITORING.md
│   │   └── RUNBOOKS/
│   │
│   ├── editorial/                   # Content catalog for A Equação
│   │   ├── README.md
│   │   ├── angles_catalog.md        # 27+ angles identified
│   │   └── templates/
│   │
│   ├── wiki/                        # Mirror of GitHub Wiki (for offline ref)
│   │   └── ...
│   │
│   └── reference/
│       ├── GLOSSARY.md
│       ├── COUNTRIES.md             # Country tiers + metadata
│       ├── INDICATORS_CATALOG.md   # All 1800+ indicators with source
│       └── API_REFERENCE.md
│
├── sonar/                           # Main Python package
│   ├── __init__.py
│   ├── settings.py                  # Pydantic settings
│   ├── logging_config.py
│   ├── exceptions.py                # Custom exceptions hierarchy
│   ├── constants.py                 # Tenor grids, country lists, BC targets
│   │
│   ├── connectors/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── registry.py              # Auto-discovery
│   │   ├── fred.py
│   │   ├── ecb_sdw.py
│   │   ├── bis.py
│   │   ├── eurostat.py
│   │   ├── oecd.py
│   │   ├── bpstat.py
│   │   ├── ine.py
│   │   ├── igcp.py
│   │   ├── treasury_gov.py
│   │   ├── bundesbank.py
│   │   ├── boe.py
│   │   ├── mof_japan.py
│   │   ├── shiller.py
│   │   ├── damodaran.py
│   │   ├── multpl.py
│   │   ├── wgb_cds.py
│   │   ├── factset_insight.py
│   │   ├── spdji_buyback.py
│   │   ├── rating_sp.py
│   │   ├── rating_moodys.py
│   │   ├── rating_fitch.py
│   │   ├── rating_dbrs.py
│   │   ├── spf_philly.py
│   │   ├── michigan_inflation.py
│   │   ├── ecb_spf.py
│   │   ├── trading_economics.py
│   │   └── ...
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── models.py                # SQLAlchemy models
│   │   ├── session.py
│   │   ├── schema_v18.sql           # Reference DDL (source of truth)
│   │   └── migrations/              # Alembic
│   │       ├── env.py
│   │       ├── script.py.mako
│   │       └── versions/
│   │
│   ├── submodels/
│   │   ├── __init__.py
│   │   ├── base.py                  # Common interface
│   │   ├── yield_curves/
│   │   │   ├── __init__.py
│   │   │   ├── nss_fitter.py
│   │   │   ├── bootstrap.py
│   │   │   ├── forwards.py
│   │   │   ├── real_curves.py
│   │   │   ├── validation.py        # Cross-check vs BC-published
│   │   │   └── orchestrator.py
│   │   ├── erp/
│   │   ├── crp/
│   │   ├── rating_spread/
│   │   └── expected_inflation/
│   │
│   ├── cycles/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── credit/
│   │   ├── monetary/
│   │   ├── economic/
│   │   └── financial/
│   │
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── matriz_4way.py
│   │   ├── diagnostics/
│   │   │   ├── bubble_detection.py
│   │   │   ├── risk_appetite.py
│   │   │   ├── real_estate.py
│   │   │   └── minsky_fragility.py
│   │   ├── cost_of_capital.py
│   │   └── alerts.py
│   │
│   ├── outputs/
│   │   ├── __init__.py
│   │   ├── api/                     # FastAPI (future)
│   │   │   ├── main.py
│   │   │   └── endpoints/
│   │   ├── cli/                     # CLI via Click/Typer
│   │   │   ├── main.py
│   │   │   └── commands/
│   │   ├── editorial/
│   │   │   ├── angle_detector.py
│   │   │   ├── briefing_generator.py
│   │   │   └── templates/
│   │   └── exporters/
│   │       ├── json_exporter.py
│   │       ├── csv_exporter.py
│   │       └── markdown_exporter.py
│   │
│   └── pipelines/
│       ├── __init__.py
│       ├── base.py
│       ├── daily.py
│       ├── weekly.py
│       ├── monthly.py
│       ├── quarterly.py
│       └── event_driven.py
│
├── tests/
│   ├── conftest.py                  # Shared fixtures
│   ├── unit/
│   │   ├── connectors/
│   │   ├── submodels/
│   │   ├── cycles/
│   │   ├── integration/
│   │   └── outputs/
│   ├── integration/
│   │   ├── pipelines/
│   │   └── fixtures/                # Recorded API responses
│   ├── property/
│   │   ├── test_yield_curves_props.py
│   │   ├── test_erp_props.py
│   │   └── ...
│   └── manual_validation/           # Scripts for human-in-loop validation
│
├── scripts/                         # Standalone utilities
│   ├── init_db.py
│   ├── backfill_historical.py
│   ├── validate_connectors.py
│   ├── compare_vs_damodaran.py
│   ├── compare_vs_fed_gsw.py
│   └── generate_methodology_pdf.py
│
├── notebooks/                       # Jupyter for exploration (gitignored output)
│   ├── 01_data_exploration/
│   ├── 02_methodology_development/
│   ├── 03_backtesting/
│   └── 04_editorial_research/
│
├── config/
│   ├── countries.yaml               # Country tiers + metadata
│   ├── indicators.yaml              # Indicator catalog
│   ├── bc_targets.yaml              # Central bank inflation targets
│   ├── portfolio_playbooks.yaml    # Cycle-state playbooks
│   └── editorial_angles.yaml       # Angle templates
│
├── data/                            # Gitignored — local DB + cache
│   ├── sonar.db                     # SQLite database
│   ├── cache/                       # Raw response cache
│   ├── backups/
│   └── downloads/                   # Shiller xls, Damodaran xlsx, etc.
│
└── dashboards/                      # Future — separate sub-project
    ├── streamlit/                   # MVP dashboard
    │   ├── Home.py
    │   └── pages/
    └── react/                       # Production dashboard (later)
```

## Rationale por secção

### Why `docs/methodology/` is source of truth

O trabalho conceptual do v1 (5 manuais × 6 partes) é **a propriedade intelectual central** do SONAR. O código é **implementação** dessa metodologia. Se o código desaparece mas a metodologia está documented, conseguimos reconstruir. Se a metodologia desaparece, mesmo com código, perdemos o "why".

Recomendação: migrar os manuais v1 para este diretório (exported as markdown ou preserved as .docx), com cross-links ao código que implementa cada secção.

### Why `sonar/` package (not `src/`)

- Mais claro que `src/` para single-package repos
- Nome explícito facilita imports (`from sonar.cycles.credit import cccs`)
- Compatível com `pip install -e .`

### Why `config/` separate from `sonar/`

- Configuration é **data**, não código
- YAML facilita edição manual (versus Python dicts)
- Permite non-developers (eventually) editarem country lists sem tocar em Python
- Testable — load & validate config em tests

### Why `scripts/` outside `sonar/`

- Entry points ad-hoc e one-off tasks
- Backfills, validations, migrations manuais
- Não fazem parte do runtime core
- Mas versionados para reproduzibilidade

### Why `notebooks/` in repo

- Research exploratório
- Prototyping de novas sub-models
- Editorial research
- Gitignore output cells (via `nbstripout`) para não poluir history
- Gold-mine para documentação historical

### Why `data/` gitignored

- DB files grandes (>100MB potencialmente)
- Cache files ephemeral
- Binary — poluem git history
- Backup strategy separate from git

### Why `.github/` workflows

- GitHub Actions para CI/CD grátis (within limits)
- Daily pipeline pode correr em GH Actions OU em VPS — decision in BRIEF_FOR_DEBATE
- Templates reduzem friction quando criar issues/PRs

### Why separate `dashboards/` (future)

- Different tech stack (possibly React/TS)
- Separate deployment
- Consumes SONAR API via HTTP
- Can evolve independently

## Conventions dentro dos modules

### Every module has

- `__init__.py` com exports explícitos (public API)
- `README.md` breve explicando o módulo
- Tests em `tests/unit/<module_name>/`
- Methodology reference em `docs/methodology/`

### Naming conventions

- **Files**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions/variables**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Module prefixes**: avoid (use packages instead)

### Country codes

- ISO 3166-1 alpha-2 (`PT`, `DE`, `US`, `BR`)
- Always uppercase
- `EA` for euro area aggregate
- `EMEA`, `APAC`, `LATAM` for regional aggregates

### Date/time

- UTC for storage
- Lisbon local for pipeline scheduling
- ISO 8601 format (`2026-04-17`, `2026-04-17T09:00:00Z`)
- `date` type for daily data, `datetime` with TZ for events

### Currency codes

- ISO 4217 (`EUR`, `USD`, `GBP`, `JPY`, `BRL`)

---

## Initial implementation order

Ver [ROADMAP.md](../ROADMAP.md) para phases detalhadas. High-level:

1. **Scaffold**: create directory structure + placeholder files
2. **Foundation**: `settings.py`, `exceptions.py`, `constants.py`, `db/models.py`
3. **First connector**: FRED (simplest, proves pipeline end-to-end)
4. **First sub-model**: Yield curves US (simplest, well-documented methodology)
5. **First cycle**: MSC (smallest scope, good test case)
6. **Expand**: other connectors, sub-models, cycles
7. **Integration**: matriz 4-way, cost of capital
8. **Outputs**: CLI, then API, then dashboard

## Migration from v1

Ver [MIGRATION_PLAN.md](MIGRATION_PLAN.md) para detalhe. Resumo:

1. Archive v1 repo (rename to `sonar-v1-archive`)
2. Make repo private and read-only
3. Extract learnings document (`docs/migration/v1_learnings.md`)
4. Migrate manuals to `docs/methodology/`
5. Migrate data plans to `docs/data_sources/`
6. Create fresh v2 repo with this structure
7. Bootstrap Phase 0 scaffolding
8. Begin Phase 1

---

*Repository structure v0.1 — to be refined during Phase 0*
