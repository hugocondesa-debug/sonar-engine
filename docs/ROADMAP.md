# SONAR v2 — Roadmap

Plano de desenvolvimento faseado. Cada phase tem deliverables, critérios de aceite e estimativa de esforço.

---

## Phase 0 — Bootstrap (1-2 semanas)

**Goal**: estabelecer foundations antes de escrever código significativo.

### Deliverables

- [ ] Security: PAT revogado, novo token criado (fine-grained)
- [ ] V1 repo arquivado (renomeado, marcado read-only)
- [ ] V2 repo criado fresh
- [ ] Repository structure scaffolded
- [ ] Documentation base commitada (README, ARCHITECTURE, etc.)
- [ ] `pyproject.toml` configurado
- [ ] CI skeleton (lint + test runners)
- [ ] Pre-commit hooks setup
- [ ] `.env.example` template
- [ ] GitHub Wiki criada com páginas base
- [ ] Manuais v1 migrados para `docs/methodology/`
- [ ] Data plans v1 migrados para `docs/data_sources/`
- [ ] BRIEF_FOR_DEBATE resolvido — decisões chave tomadas
- [ ] ADRs iniciais escritos (linguagem, DB, orquestração, licensing)

### Critérios de aceite

- Repo clona, `pip install -e ".[dev]"` funciona
- `pytest` corre (zero tests ainda, mas não erra)
- `ruff check` e `mypy` passam em código vazio
- CI triggera em push e passa
- Documentação renderiza em GitHub (README + wiki)
- Todos os decisores do BRIEF_FOR_DEBATE têm ADR assinado

### Esforço

Principalmente write/review documentation. ~20-30 horas.

---

## Phase 1 — Data foundation (3-4 semanas)

**Goal**: pipeline end-to-end com um connector completo, uma tabela na DB, um output simples. Prove que a arquitetura funciona.

### Deliverables

- [ ] `sonar/settings.py` com pydantic config completo
- [ ] `sonar/db/models.py` com schema v18 mínimo (5 tables)
- [ ] Alembic migrations setup, first migration
- [ ] `sonar/connectors/base.py` — abstract interface
- [ ] `sonar/connectors/fred.py` — fully implemented
- [ ] Unit tests para FRED connector (mocked HTTP)
- [ ] Integration test: fetch real data, store to SQLite, verify
- [ ] CLI command: `sonar fetch fred --series DGS10 --date 2026-04-17`
- [ ] Logging estruturado
- [ ] `.env.example` com todas as API keys documentadas
- [ ] Dev environment documented in `docs/operations/DEV_SETUP.md`

### Critérios de aceite

- `sonar fetch fred --series DGS10` retorna yield e armazena em DB
- Query SQL direta à DB mostra dados corretos
- Unit tests coverage >80% em módulo FRED
- Integration test corre e passa em CI (com API key secret)
- Logs são human-readable e debugging-useful

### Esforço

~40-60 horas. Maior parte é setup infra e learning curve.

---

## Phase 2 — Connectors expansion (3-4 semanas)

**Goal**: coverage dos data sources essenciais para Tier 1 MVP.

### Deliverables — connectors

- [ ] `ecb_sdw.py` — ECB Statistical Data Warehouse
- [ ] `bis.py` — BIS statistics
- [ ] `eurostat.py`
- [ ] `bpstat.py` — Banco de Portugal
- [ ] `igcp.py` — Portuguese sovereign
- [ ] `treasury_gov.py` — US Treasury daily
- [ ] `bundesbank.py` — Svensson fitted curves
- [ ] `boe.py` — BoE Anderson-Sleath curves
- [ ] `shiller.py` — ie_data.xls download
- [ ] `damodaran.py` — monthly histimpl.xlsx (validation only)
- [ ] `wgb_cds.py` — worldgovernmentbonds.com scrape
- [ ] `multpl.py` — multpl.com scrape

### Deliverables — infra

- [ ] Connector registry + auto-discovery
- [ ] Rate limiting wrapper (httpx + asyncio)
- [ ] Cache layer (disk + TTL)
- [ ] Retry logic with exponential backoff
- [ ] Error handling consistent across connectors
- [ ] Metrics: success/fail rate per connector

### Critérios de aceite

- Todos connectors têm >80% unit test coverage
- Integration tests pass em CI weekly (full fetch)
- Pipeline diário completa em <15 min para todos connectors
- DB populada com histórico de 1 ano para sanity-check

### Esforço

~80-120 horas. Muitas fontes similares após primeiras 3-4.

---

## Phase 3 — Sub-models (4-6 semanas)

**Goal**: cinco sub-models operacionais, Portugal coverage incluído.

### Phase 3a — Yield curves (2 semanas)

- [ ] `nss_fitter.py` — Python library with scipy
- [ ] `bootstrap.py` — zero curve derivation
- [ ] `forwards.py` — forward rate computation
- [ ] `real_curves.py` — real yield (direct + derived)
- [ ] `validation.py` — cross-check vs Fed GSW, Bundesbank, BoE
- [ ] Orchestrator: fit all 15+ countries daily
- [ ] Portugal curve via IGCP + ECB SDW working
- [ ] Cross-validation target met: RMSE <5bps, vs BC-published <10bps

### Phase 3b — ERP daily (2 semanas)

- [ ] Four methods implemented (DCF, Gordon, simple, CAPE)
- [ ] S&P 500 (US) primary implementation
- [ ] STOXX 600, FTSE, TOPIX extensions
- [ ] Damodaran monthly cross-validation working (<20bps deviation target)
- [ ] FactSet Earnings Insight scraper operational
- [ ] S&P DJI buyback quarterly integrated

### Phase 3c — CRP (1 semana)

- [ ] CDS-based approach primary
- [ ] Sovereign spread fallback
- [ ] Vol ratio computation per country (5Y rolling)
- [ ] CRP for 30+ countries
- [ ] Portugal CRP ~54bps validated

### Phase 3d — Rating + expected inflation (1-2 semanas)

- [ ] Rating agency scrapers (S&P, Moody's, Fitch, DBRS)
- [ ] SONAR common scale conversion
- [ ] Moody's Annual Default Study parsing
- [ ] Rating-to-spread table calibrated
- [ ] Expected inflation via breakevens (direct countries)
- [ ] Expected inflation derived for Portugal (EA + differential)
- [ ] 5y5y forward computation
- [ ] SPF + Michigan + ECB SPF surveys integrated

### Critérios de aceite Phase 3

- All five sub-models produce daily outputs
- Portugal coverage complete (all five)
- Cross-validations within targets documented in manual
- DB has historical backfill where possible (US yield curves 1990+, etc.)
- Cost of capital can be computed end-to-end for Portugal equity

### Esforço

~160-200 horas. The methodology-heavy phase.

---

## Phase 4 — Cycle classification (4-5 semanas)

**Goal**: quatro ciclos com scores + overlays, integrating sub-model outputs.

### Deliverables

- [ ] ECS (Economic Cycle Score)
  - [ ] E1 Activity, E2 Leading, E3 Labor, E4 Sentiment sub-components
  - [ ] Composite scoring 0-100
  - [ ] Stagflation overlay
- [ ] CCCS (Credit Cycle Score)
  - [ ] Credit expansion metrics
  - [ ] Delinquency, charge-offs
  - [ ] Bank lending standards
  - [ ] Boom overlay
- [ ] MSC (Monetary Stance Composite)
  - [ ] Policy rate vs neutral
  - [ ] Yield curve slope (from sub-model!)
  - [ ] BC balance sheet metrics
  - [ ] Dilemma overlay
- [ ] FCS (Financial Cycle Score)
  - [ ] F1 Valuations (uses ERP from sub-model!)
  - [ ] F2 Momentum
  - [ ] F3 Risk appetite
  - [ ] F4 Positioning
  - [ ] Bubble Warning overlay (uses BIS credit gap)

### Critérios de aceite

- Each cycle has testable score given known historical inputs
- Cross-validation vs manual-documented historical states
- Pipeline computes all four daily in <5 min
- Portugal-specific CCCS produces sensible trajectory 2005-2026

### Esforço

~100-140 horas.

---

## Phase 5 — Integration (2-3 semanas)

**Goal**: unify cycles + sub-models em integrated state + diagnostics.

### Deliverables

- [ ] Matriz 4-way classifier
  - [ ] Six canonical patterns detection
  - [ ] Five critical configurations detection
  - [ ] Transition probability (basic)
- [ ] Four diagnostics aplicados:
  - [ ] Bubble detection composite
  - [ ] Risk appetite regime (R1-R4)
  - [ ] Real estate cycle phase
  - [ ] Minsky fragility composite
- [ ] Cost of capital framework
  - [ ] Country-specific computation (Portuguese equity, Brazilian bank, etc.)
  - [ ] Real vs nominal options
  - [ ] Currency-aware (EUR, USD, BRL, etc.)
- [ ] Alerts system
  - [ ] Threshold breach detection
  - [ ] Regime shift detection
  - [ ] Alert publishing (log + email/Telegram stub)

### Critérios de aceite

- EDP DCF worked example produces cost of equity 7.55% (matches manual)
- Brazilian bank cross-border DCF framework validated
- Current (April 2026) integrated state matches manual's described state for Portugal

### Esforço

~80-100 horas.

---

## Phase 6 — Outputs & editorial pipeline (3-4 semanas)

**Goal**: make SONAR outputs consumable — API, CLI, briefings, charts.

### Deliverables

- [ ] CLI completa via Typer
  - [ ] `sonar pipeline daily`
  - [ ] `sonar pipeline event <type>`
  - [ ] `sonar query cycle <country> <date>`
  - [ ] `sonar query cost-of-capital <country>`
  - [ ] `sonar briefing daily`
  - [ ] `sonar validate connectors`
- [ ] FastAPI internal API
  - [ ] `/cycles/{country}/latest`
  - [ ] `/submodels/{submodel}/{country}/latest`
  - [ ] `/integration/cost_of_capital/{country}`
  - [ ] `/alerts/active`
  - [ ] OpenAPI docs auto-generated
- [ ] Editorial pipeline
  - [ ] Angle detection based on data state
  - [ ] Daily briefing generator
  - [ ] Angle templates (markdown)
  - [ ] Chart generation (matplotlib/plotly)
- [ ] Exporters
  - [ ] JSON for integration
  - [ ] Markdown for documentation
  - [ ] CSV for Excel analysis

### Critérios de aceite

- Can run daily pipeline and get editorial briefing output
- API endpoints return data matching DB
- First editorial angle produces publishable draft

### Esforço

~80-100 horas.

---

## Phase 7 — Dashboard v1 (3-4 semanas)

**Goal**: Streamlit MVP dashboard para uso pessoal e demo.

### Deliverables

- [ ] Streamlit app structure
- [ ] Home page: SONAR integrated state snapshot
- [ ] Cycle pages: one per cycle with history + current
- [ ] Sub-model pages: yield curves, ERP, CRP, expected inflation
- [ ] Matriz 4-way visualization
- [ ] Cost of capital calculator (interactive)
- [ ] Country comparison tool
- [ ] Historical animation
- [ ] Alerts panel

### Critérios de aceite

- Dashboard deployable locally (`streamlit run`)
- All data loads from SONAR DB
- Interactive charts responsive
- Portugal focus clear

### Esforço

~60-80 horas.

---

## Phase 8 — Operationalization (2-3 semanas)

**Goal**: production-grade operations.

### Deliverables

- [ ] Automated daily pipeline
  - [ ] Cron or GitHub Actions
  - [ ] Failure alerting (email + Telegram)
  - [ ] Success metrics logged
- [ ] Monitoring dashboard
  - [ ] Connector health
  - [ ] Sub-model drift vs validations
  - [ ] DB size tracking
- [ ] Backup strategy
  - [ ] Daily SQLite backup
  - [ ] Weekly encrypted cloud push (S3/B2)
  - [ ] Restore runbook tested
- [ ] Documentation
  - [ ] Operations runbooks
  - [ ] Troubleshooting guide
  - [ ] Common issues + fixes

### Critérios de aceite

- Pipeline runs reliably for 30 days without manual intervention
- Backup + restore tested successfully
- Runbooks allow recovery from common failures

### Esforço

~40-60 horas.

---

## Phase 9 — Backtesting framework (3-4 semanas)

**Goal**: validate SONAR historical signal quality.

### Deliverables

- [ ] Historical backfill complete (where data permits)
- [ ] Backtesting engine
  - [ ] Compute historical cycle states
  - [ ] Simulate forward returns
  - [ ] Compare vs benchmarks
- [ ] Performance reports
  - [ ] Signal quality per cycle
  - [ ] Matriz 4-way predictive power
  - [ ] Portfolio simulation per playbook
- [ ] Statistical validation
  - [ ] Pagan-Sossounov agreement (>87% target per manual)
  - [ ] ERP predictive power (correlation with forward returns)
  - [ ] CRP stability analysis

### Critérios de aceite

- Backtests match manual-documented historical episodes
- Signal quality documented per sub-module
- Credibility established for potential fund launch

### Esforço

~80-100 horas.

---

## Phase 10+ — Future expansions

### v2.5 — EM expansion
- Frontier market coverage
- Alternative data sources (news sentiment, satellite)
- Political risk scoring

### v3 — Fund-ready
- Multi-asset strategy engine
- Portfolio construction automation
- Transaction cost integration
- Institutional reporting

### v3.5 — Dashboard production
- React + TypeScript
- Deployed to cloud
- Multi-user (if needed)
- Enterprise features (SSO, audit logs)

### v4 — AI augmentation
- LLM-powered editorial angle generation
- Automated research summarization
- Anomaly detection ML
- Narrative context synthesis

---

## Critical path

Fases que bloqueiam seguintes:

```
Phase 0 (Bootstrap)
   ↓
Phase 1 (Data foundation)
   ↓
Phase 2 (Connectors) ─┬─ Phase 3 (Sub-models)
                       │        ↓
                       └─ Phase 4 (Cycles)
                              ↓
                         Phase 5 (Integration)
                              ↓
                         Phase 6 (Outputs) ─── Phase 7 (Dashboard)
                              ↓
                         Phase 8 (Ops)
                              ↓
                         Phase 9 (Backtesting)
```

## Estimativa agregada

Assumindo 10-15 horas/semana de desenvolvimento:

| Range | Total effort | Duration (at 10-15h/wk) |
|---|---|---|
| Phase 0-3 (MVP) | ~300-400h | 5-7 meses |
| Phase 0-6 (full v2) | ~600-800h | 10-14 meses |
| Phase 0-9 (complete) | ~800-1000h | 14-20 meses |

**Recommendation**: target Phase 0-3 as MVP (~6 months), then iterate based on which of Phase 4-9 delivers most value for editorial and fund-preparation goals.

## Parallel work possible

Com time extra ou colaboração:
- Phase 3a, 3b, 3c, 3d podem paralelizar
- Phase 7 (dashboard) pode começar logo que Phase 5 entregue algo
- Phase 9 (backtesting) pode começar em paralelo com Phase 4-5

## Risk mitigation

Potential risks + mitigations:

| Risk | Mitigation |
|---|---|
| Rating agency scrapers break | Build multiple fallback strategies, graceful degradation |
| Damodaran stops publishing | SONAR has own computation — validation only |
| FactSet PDF format changes | Monitor, alert, manual fallback |
| API rate limits hit | Caching layer, scheduling spread, backup sources |
| Methodology drift over time | Version control, regular calibration reviews |
| Portugal data quality issues | Cross-check multiple sources (IGCP, ECB SDW, MTS) |
| Single-person bottleneck | Prioritize documentation, run-books, automation |

---

*Roadmap v0.1 — to be refined continuously. Tracked as GitHub Milestones.*
