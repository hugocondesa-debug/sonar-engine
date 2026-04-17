# SONAR v2 — Architecture

**Document purpose**: definir a arquitetura técnica do SONAR v2 com suficiente detalhe para guiar implementação, mas flexível o suficiente para permitir decisões ainda abertas (ver [BRIEF_FOR_DEBATE.md](../BRIEF_FOR_DEBATE.md)).

---

## 1. Design principles

### 1.1 Layered architecture

O SONAR segue arquitetura de cinco layers, hierarchical com feedback loops intencionais:

```
LAYER 0 — Raw data sources (external APIs, scrapes, files)
     ↓
LAYER 1 — Sub-models (yield curves, ERP, CRP, rating-spread, expected inflation)
     ↓
LAYER 2 — Cycle classification (ECS, CCCS, MSC, FCS + overlays)
     ↓
LAYER 3 — Integration (matriz 4-way, four diagnostics, cost-of-capital)
     ↓
LAYER 4 — Outputs (API, alerts, editorial pipeline, dashboard)
```

**Feedback loops explícitos**:
- Yield curve slope → MSC (monetary stance)
- ERP → FCS (financial cycle valuations)
- CRP → CCCS (credit cycle periphery)
- Expected inflation → MSC (credibility assessment)
- Rating → CCCS (sovereign credit)

Feedback é intencional, não bug — economia moderna funciona assim. Calibration histórica valida consistência.

### 1.2 Compute, don't consume

Sub-models são **computed locally** a partir de dados raw, não consumidos de sources agregados:

| ❌ Consume | ✅ Compute |
|---|---|
| Damodaran mensal ERP direto | ERP diário via DCF + analyst estimates |
| Bloomberg CRP | CRP via CDS + vol ratio |
| Bundesbank fitted curve | NSS fit próprio com Bundesbank como cross-validation |
| Shiller CAPE published | Download Shiller data, compute CAPE localmente |

**Cross-validation** de BC-published é continuous (target: Fed GSW <10bps, Bundesbank <5bps).

### 1.3 Separation of concerns

Cada layer é **isolado**:

- Connectors não conhecem schema da base de dados
- Database layer não conhece sub-models
- Sub-models não conhecem cycles (mas cycles conhecem sub-models)
- Outputs consomem, não computam

### 1.4 Idempotency & reproducibility

- Todo pipeline deve ser **idempotent** (rerun com mesmos inputs = mesmos outputs)
- Historical runs devem ser **reproduzíveis** via version-controlled methodology
- Database tem methodology_version column para recomputation selective

### 1.5 Honest uncertainty

- Todo output tem **confidence** score explícito
- Confidence intervals publicadas quando relevante
- Failure modes documentados per module
- Silent failures inaceitáveis — tudo logged e flagged

---

## 2. Technology stack

### 2.1 Proposed stack (open para debate)

| Layer | Technology | Rationale |
|---|---|---|
| Language | **Python 3.11+** | Ecosystem financeiro (pandas, numpy, scipy), ML-ready, team familiar |
| Database (local) | **SQLite** via SQLAlchemy | Simple, file-based, excellent for single-user research. Port to Postgres later if needed. |
| Alternative | **DuckDB** | If analytical queries become bottleneck — columnar, optimized for OLAP |
| Config | **pydantic-settings** | Type-safe environment config |
| ORM | **SQLAlchemy 2.0** | Mature, supports Core + ORM, migrations via Alembic |
| Migrations | **Alembic** | Schema versioning |
| HTTP client | **httpx** | Async-capable, modern |
| Scraping | **BeautifulSoup4 + lxml** | Standard for HTML scraping |
| PDF parsing | **pdfplumber** | FactSet reports, Moody's Default Study |
| Excel | **openpyxl** | Shiller ie_data.xls, Damodaran histimpl.xlsx |
| NSS fitting | **scipy.optimize** | Standard scientific computing |
| Testing | **pytest + hypothesis** | Unit + property-based tests |
| Linting | **ruff** | Fast, comprehensive |
| Type checking | **mypy** | Static types critical for correctness |
| Formatting | **ruff format** (or black) | Consistency |
| CI/CD | **GitHub Actions** | Free for private repos up to limits |
| Orchestration | **APScheduler** (simple) or **Prefect** (if complex) | Start simple, upgrade if needed |
| API (future) | **FastAPI** | Modern, type-safe, async |
| Dashboard (future) | **Streamlit** (MVP) or **React** (v2) | Start with Streamlit for speed |
| Secrets | **.env** + python-dotenv (local), GitHub Actions secrets (CI) | Standard |
| Package manager | **uv** or **pip** | uv is faster; pip safer baseline |

### 2.2 Things we deliberately don't use (yet)

- **Kubernetes/Docker Swarm** — overkill for single-user research
- **Apache Airflow** — too heavy for our orchestration needs
- **Kafka/RabbitMQ** — no real-time streaming requirements
- **PostgreSQL** — until scale demands it
- **TypeScript** — Python is sufficient; add JS only for dashboard v2

## 3. Module architecture

### 3.1 Core package layout

```
sonar/
├── __init__.py
├── settings.py                  # Pydantic settings, env vars
├── logging_config.py            # Structured logging setup
│
├── connectors/                  # Layer 0 — raw data
│   ├── __init__.py
│   ├── base.py                  # Abstract connector interface
│   ├── fred.py                  # FRED API
│   ├── ecb_sdw.py               # ECB Statistical Data Warehouse
│   ├── bis.py                   # BIS statistics
│   ├── igcp.py                  # Portuguese sovereign
│   ├── treasury_gov.py          # US Treasury daily rates
│   ├── bundesbank.py            # Bundesbank Svensson curves
│   ├── boe_yieldcurves.py       # BoE Anderson-Sleath
│   ├── shiller.py               # Shiller ie_data.xls
│   ├── damodaran.py             # Damodaran monthly (validation)
│   ├── wgb_cds.py               # World Government Bonds CDS scrape
│   ├── factset_insight.py       # FactSet Earnings Insight PDF
│   ├── spdji_buyback.py         # S&P DJI Buyback
│   ├── rating_agencies.py       # S&P, Moody's, Fitch, DBRS
│   ├── spf.py                   # Philly Fed SPF
│   └── ...
│
├── db/                          # Layer 0/1 — persistence
│   ├── __init__.py
│   ├── models.py                # SQLAlchemy ORM models
│   ├── migrations/              # Alembic migrations
│   │   └── versions/
│   ├── session.py               # DB session factory
│   └── schema_v18.sql           # Reference DDL
│
├── submodels/                   # Layer 1 — sub-models
│   ├── __init__.py
│   ├── yield_curves/
│   │   ├── __init__.py
│   │   ├── nss_fitter.py        # NSS methodology
│   │   ├── bootstrap.py         # Zero curve derivation
│   │   ├── forwards.py          # Forward curve derivation
│   │   ├── real_curves.py       # Real yield computation
│   │   └── orchestrator.py      # Per-country daily pipeline
│   ├── erp/
│   │   ├── __init__.py
│   │   ├── dcf_method.py        # Damodaran DCF
│   │   ├── gordon_method.py     # Gordon simplified
│   │   ├── earnings_yield.py    # Simple
│   │   ├── cape_method.py       # Shiller-based
│   │   └── orchestrator.py
│   ├── crp/
│   │   ├── __init__.py
│   │   ├── cds_based.py
│   │   ├── sovereign_spread.py
│   │   ├── vol_ratio.py
│   │   └── orchestrator.py
│   ├── rating_spread/
│   │   ├── __init__.py
│   │   ├── agency_scale.py      # Cross-agency conversion
│   │   ├── calibration.py       # Rating-to-spread table
│   │   └── orchestrator.py
│   └── expected_inflation/
│       ├── __init__.py
│       ├── breakevens.py        # Market-based
│       ├── surveys.py           # SPF, ECB SPF, Michigan
│       ├── derived.py           # Portugal synthesis, EM model-based
│       ├── forward_derivation.py # 5y5y forward
│       └── orchestrator.py
│
├── cycles/                      # Layer 2 — cycle classification
│   ├── __init__.py
│   ├── base.py                  # Abstract cycle class
│   ├── credit/
│   │   ├── __init__.py
│   │   ├── cccs.py              # Credit Cycle Score
│   │   └── boom_overlay.py
│   ├── monetary/
│   │   ├── __init__.py
│   │   ├── msc.py               # Monetary Stance Composite
│   │   └── dilemma_overlay.py
│   ├── economic/
│   │   ├── __init__.py
│   │   ├── ecs.py               # Economic Cycle Score
│   │   └── stagflation_overlay.py
│   └── financial/
│       ├── __init__.py
│       ├── fcs.py               # Financial Cycle Score
│       └── bubble_warning.py
│
├── integration/                 # Layer 3
│   ├── __init__.py
│   ├── matriz_4way.py           # Canonical pattern classifier
│   ├── diagnostics/
│   │   ├── __init__.py
│   │   ├── bubble_detection.py
│   │   ├── risk_appetite.py
│   │   ├── real_estate.py
│   │   └── minsky_fragility.py
│   ├── cost_of_capital.py       # Cross-border framework
│   └── alerts.py                # Threshold breach detection
│
├── outputs/                     # Layer 4
│   ├── __init__.py
│   ├── api/                     # FastAPI (future)
│   ├── cli/                     # Command-line entry points
│   ├── editorial/               # Angle generation
│   └── exporters/               # JSON, CSV, markdown
│
└── pipelines/                   # Orchestration
    ├── __init__.py
    ├── daily.py                 # Daily pipeline
    ├── weekly.py
    ├── monthly.py
    ├── quarterly.py
    └── event_driven.py          # Rating actions, etc.
```

### 3.2 Base connector interface

Every data source implements a common interface. Draft (see `templates/connectors/base.py`):

```python
from abc import ABC, abstractmethod
from datetime import date
from typing import Any
from pydantic import BaseModel

class FetchResult(BaseModel):
    data: dict[str, Any]
    source: str
    fetched_at: datetime
    data_as_of: date | None
    confidence: float
    warnings: list[str] = []

class BaseConnector(ABC):
    name: str  # "fred", "ecb_sdw", etc.
    tier: int  # 1, 2, 3

    @abstractmethod
    def fetch(self, **kwargs) -> FetchResult:
        """Fetch data from source."""
        ...

    @abstractmethod
    def validate(self, result: FetchResult) -> list[str]:
        """Return warnings/errors about data quality."""
        ...

    @abstractmethod
    def store(self, result: FetchResult) -> int:
        """Persist to database. Return rows affected."""
        ...
```

### 3.3 Data flow (canonical day)

Pipeline diário (Lisbon timezone):

```
06:00 — Morning data refresh
  connectors/treasury_gov.fetch()
  connectors/bundesbank.fetch()
  connectors/boe_yieldcurves.fetch()
  connectors/mof_japan.fetch()
  connectors/ecb_sdw.fetch() [EA country yields]
  connectors/wgb_cds.fetch()

07:00 — Portugal-specific
  connectors/igcp.fetch()
  connectors/bpstat.fetch()

08:00 — Supplementary
  connectors/fred.fetch_daily_series()
  connectors/multpl.fetch()

09:00 — Sub-model computation
  submodels/yield_curves/orchestrator.run_all_countries()
  submodels/erp/orchestrator.run_all_markets()
  submodels/crp/orchestrator.run_all_countries()
  submodels/rating_spread/orchestrator.update_if_needed()
  submodels/expected_inflation/orchestrator.run_all_countries()

10:00 — Cycle classification
  cycles/credit/cccs.compute()
  cycles/monetary/msc.compute()
  cycles/economic/ecs.compute()
  cycles/financial/fcs.compute()
  [+ overlays]

10:30 — Integration
  integration/matriz_4way.classify()
  integration/diagnostics/*.compute()
  integration/cost_of_capital.compute_for_countries(TIER_1_2)

11:00 — Outputs
  outputs/editorial/generate_daily_briefing()
  integration/alerts.evaluate_and_publish()
```

### 3.4 Error handling philosophy

- **Fail loud, fail fast** during development
- **Fail gracefully, log verbose** in production
- Never silently swallow exceptions
- Every failure tagged with connector name + timestamp
- Critical failures (database write fails, core connector down) page operator (email/Telegram)
- Non-critical failures (one country's CDS missing) flag in output metadata, continue pipeline

---

## 4. Database architecture

### 4.1 Schema versioning

Schema migrations gerenciadas via Alembic. Historical versions:
- v13: credit cycle
- v14-15: monetary cycle
- v16: economic cycle
- v17: financial cycle
- **v18** (current): sub-models (this is starting point for v2)

### 4.2 Core tables (high-level)

| Table family | Tables | Purpose |
|---|---|---|
| Raw data | `raw_fred_series`, `raw_ecb_series`, etc. | Audit trail of fetched data |
| Cycle indicators | `economic_*`, `credit_*`, `monetary_*`, `financial_*` | Per-cycle component indicators |
| Sub-model outputs | `yield_curves`, `erp_daily`, `country_risk_premium`, `sovereign_ratings`, `rating_spread_mapping`, `expected_inflation`, `cost_of_capital_daily` | Layer 1 outputs |
| Cycle scores | `economic_cycle_score`, `credit_cycle_score`, `monetary_stance_composite`, `financial_cycle_score` | Layer 2 outputs |
| Integration | `sonar_integrated_state`, `applied_diagnostics`, `alerts` | Layer 3 outputs |
| Meta | `connector_runs`, `methodology_versions`, `calibration_history` | Ops & provenance |

### 4.3 Key design patterns

**Every table has**:
- `created_at`, `updated_at` timestamps
- Source tracking (which connector, which run)
- Confidence score
- Methodology version reference

**Indexes** on `(country_code, date)` for time-series queries.

**Views** para common aggregate queries:
- `v_latest_cycle_states_per_country`
- `v_matriz_4way_history`
- `v_cost_of_capital_timeseries`

### 4.4 Backup & retention

- **Local DB**: backup daily via `sqlite3 .backup` to timestamped file
- **Retention**: full history, no deletion (historical backfill preserved)
- **Cloud backup** (future): encrypted S3/B2 daily push
- **Raw data audit**: retained 90 days minimum, then aggregated

---

## 5. Observability

### 5.1 Logging

- **Structured logging** via `structlog` or stdlib logging with JSON formatter
- All log entries include: timestamp, level, module, operation, country/market (if applicable), confidence
- Log levels:
  - DEBUG: normal operation detail
  - INFO: pipeline milestones
  - WARNING: recoverable issues (stale data, wide confidence intervals)
  - ERROR: module failures
  - CRITICAL: pipeline-wide failures

### 5.2 Metrics

Simple metrics initially (just log, no Prometheus):
- Connector success/failure rates
- Sub-model computation time
- Cross-validation deviations (Fed GSW vs SONAR NSS, Damodaran vs SONAR ERP)
- Database write rates

Future: Prometheus + Grafana if scale demands.

### 5.3 Alerting (for pipeline ops, not market alerts)

- Pipeline failures → email + Telegram
- Cross-validation drift > threshold → email
- Missing data from connector > 24h → email
- Database size alarm → email

Market alerts (ERP compression, regime shifts) são diferentes — são **outputs** editoriais, não ops alerts. Vivem em `integration/alerts.py`.

---

## 6. Testing strategy

### 6.1 Three levels

1. **Unit tests** (`tests/unit/`)
   - Connectors: parser/transformer logic (mocked HTTP)
   - Sub-models: methodology computation with synthetic inputs
   - Cycles: score calculation with known inputs
   - Target coverage: 80%+ for core computation modules

2. **Integration tests** (`tests/integration/`)
   - End-to-end pipeline with recorded fixtures
   - Database round-trips
   - Cross-validation deviations within thresholds

3. **Property tests** (`tests/property/`)
   - NSS fitter: monotonic zero curves in most cases
   - ERP: bounded range (1.5%-8.5%)
   - CRP: vol ratio bounded (1.2-2.5)
   - Fisher equation consistency
   - Conservation laws (e.g. matriz 4-way classification sums to 100%)

### 6.2 Fixture strategy

- Use `pytest fixtures` for reusable mock data
- Record real API responses once, replay in CI (via `pytest-recording` or `vcrpy`)
- Validation fixtures: known historical dates where answers are well-established

### 6.3 CI strategy

GitHub Actions workflow (`.github/workflows/ci.yml`):
- On push to any branch: lint + typecheck + unit tests
- On PR to main: + integration tests
- On merge to main: + scheduled daily pipeline tests on fixture data
- Nightly: cross-validation tests against live data

---

## 7. Security & secrets

### 7.1 Secrets never committed

Enforced via:
- `.gitignore` includes `.env`, `*.key`, `credentials.json`
- Pre-commit hook scans for suspected secrets (detect-secrets, gitleaks)
- GitHub secret scanning enabled
- CI fails if secrets detected

### 7.2 API keys

Stored in:
- Local: `.env` file (gitignored)
- CI: GitHub Actions encrypted secrets
- Production (future): cloud provider secrets manager (AWS Secrets Manager, etc.)

### 7.3 Dependency security

- `pip-audit` in CI pipeline
- Dependabot enabled on GitHub
- Major version upgrades gated via PR review

---

## 8. Deployment scenarios

### 8.1 Local-only (current default)

- Developer's laptop runs daily pipeline
- SQLite database on disk
- Scripts run via cron / APScheduler
- Sufficient for solo use + editorial pipeline

### 8.2 Cloud single-node (mid-term)

- VPS ($20-40/month): DigitalOcean, Hetzner
- Systemd for pipeline orchestration
- Automated backups to S3/B2
- Accessible via SSH tunnel
- Provides 24/7 uptime if needed

### 8.3 Cloud multi-node (fund scenario)

- Kubernetes or container orchestration
- Postgres production database
- Prometheus + Grafana
- Separate environments (dev, staging, prod)
- Only justified if fund launches and needs institutional-grade SLAs

---

## 9. Extensibility

### 9.1 Adding a new country

1. Add to `config/countries.yaml` (ISO code, tier, currency, etc.)
2. Ensure relevant connectors support the country
3. Add specific connector if country has local data source
4. Update tests to include the new country

### 9.2 Adding a new sub-model

1. Create `sonar/submodels/<new_model>/` directory
2. Implement orchestrator following pattern
3. Add database tables via Alembic migration
4. Wire into daily pipeline
5. Add to API endpoints
6. Document methodology in `docs/methodology/`

### 9.3 Adding a new data source

1. Implement `BaseConnector` subclass in `sonar/connectors/`
2. Add to connector registry
3. Add unit tests with mocked responses
4. Add to daily pipeline at appropriate timing
5. Document in `docs/data_sources/`

---

## 10. Key architectural decisions (ADRs)

Architecture Decision Records será armazenado em `docs/architecture/adr/`. Format padrão:

```
docs/architecture/adr/
├── 0001-use-python-as-primary-language.md
├── 0002-use-sqlite-for-mvp.md
├── 0003-nss-over-anderson-sleath.md
├── 0004-compute-erp-locally.md
└── 0005-portugal-aware-design.md
```

Algumas ADRs iniciais estão esboçadas em `BRIEF_FOR_DEBATE.md` e devem ser finalizadas antes de code significativo.

---

## Appendix A — Flow diagram

```
                      ┌─────────────────────────┐
                      │   EXTERNAL SOURCES      │
                      │  FRED, ECB, BIS, etc.   │
                      └────────────┬────────────┘
                                   │
                      ┌────────────▼────────────┐
                      │     CONNECTORS          │
                      │   (sonar/connectors/)   │
                      └────────────┬────────────┘
                                   │
                      ┌────────────▼────────────┐
                      │      DATABASE           │
                      │   (SQLite + SQLAlchemy) │
                      └────┬────────────────┬───┘
                           │                │
              ┌────────────▼─────┐   ┌──────▼───────────┐
              │   SUB-MODELS     │   │   CYCLES         │
              │  (submodels/)    │◄──┤  (cycles/)       │
              └────────────┬─────┘   └──────┬───────────┘
                           │                 │
                      ┌────▼─────────────────▼────┐
                      │     INTEGRATION            │
                      │  Matriz 4-way, diagnostics │
                      │  Cost of capital           │
                      └────────────┬───────────────┘
                                   │
                      ┌────────────▼────────────┐
                      │       OUTPUTS           │
                      │  API, CLI, Editorial,   │
                      │  Dashboard, Alerts      │
                      └─────────────────────────┘
```

---

*Architecture v0.1 — draft for debate. To be finalized before Phase 1 implementation.*
