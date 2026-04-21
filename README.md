# SONAR

> **S**ystematic **O**bservatory of **N**ational **A**ctivity and **R**isk
>
> Motor analítico de quatro ciclos macro + cinco sub-modelos quantitativos, com cobertura cross-country e foco em aplicação editorial e de investimento.

**Maintainer**: Hugo · 7365 Capital
**Status**: Phase 1 Week 7 CLOSED — **M1 US milestone ~95 %** (implementation scope complete)
**License**: Proprietary (to be determined)

---

## O que é o SONAR

SONAR **não é** uma plataforma de visualização de indicadores macro ao estilo Trading Economics ou CEIC.

SONAR **é** um motor analítico que produz:

1. **Classificação probabilística de quatro ciclos macro em tempo quase real**
   - Economic Cycle Score (ECS) + Stagflation overlay
   - Credit Cycle Score (CCCS) + Boom overlay
   - Monetary Stance Composite (MSC) + Dilemma overlay
   - Financial Cycle Score (FCS) + Bubble Warning overlay

2. **Cinco sub-modelos quantitativos derivados, operacionais daily**
   - Yield curves por país (NSS methodology, 5 output families)
   - Equity Risk Premium diária computada (não consumida de Damodaran)
   - Country Risk Premium (30+ países, CDS + sovereign spread + vol ratio)
   - Rating-to-spread mapping (22 notches cross-agency)
   - Expected inflation cross-country term structure

3. **Integração — matriz 4-way + quatro diagnósticos aplicados**
   - Seis padrões canónicos + cinco configurações críticas
   - Bubble detection, risk appetite regime, real estate cycle, Minsky fragility
   - Cost of capital cross-border framework

4. **Outputs operacionais**
   - API interna com endpoints por módulo e integrados
   - Alerts de threshold breach e regime shift
   - Editorial pipeline com 27+ ângulos automaticamente triggerable
   - Pipeline diário orquestrado (timezone Lisboa)

## Quem usa

- **Editorial** — coluna "A Equação" e institutional commentary
- **Valuation** — Portuguese equity DCF e cross-border analysis
- **Portfolio** — cycle-informed allocation (futuro)
- **Fund** — 7365 Capital discretionary macro fund (eventual)

## Filosofia

Cinco princípios não-negociáveis:

1. **Compute, don't consume** — ERP, CRP, yield curves, expected inflation são **calculados** pelo SONAR, não copiados de fontes externas. Damodaran/Bloomberg/Bundesbank servem como **cross-validation**, não como input primário.

2. **Metodologia transparente** — toda computação documentada, versionada, replicável. O competitive advantage é transparência, não secrecy.

3. **Portugal-aware by design** — cada sub-model tem derivação específica para Portugal. PT yield curve via IGCP, PT CRP daily, PT expected inflation via EA + differential synthesis, PT rating consolidado cross-agency.

4. **Cross-border coherence** — framework cost-of-capital funciona para Portuguese equity, Brazilian bank cross-border DCF, emerging market valuation, com currency handling rigoroso (Fisher equation + PPP).

5. **Honest calibration** — confidence intervals explícitos, claims vs non-claims documentados, failure modes reconhecidos. Framework é probabilistic, não deterministic.

## Estado — Phase 1 Week 7 (M1 US)

Phase 1 encerra com **M1 US = single-country end-to-end**:

- **L0 connectors**: 22+ operacionais (FRED, Eurostat, BIS, ECB SDW,
  IGCP, Bundesbank, BoE, Shiller, Damodaran, FMP, Multpl, CBOE, CFTC,
  FINRA, Chicago Fed NFCI, Moody's, Yahoo, TE, AAII, Factset Insight,
  ICE BofA, MOVE, CBO, SPDJI Buyback, Yardeni).
- **L1 persistence**: 16 migrations Alembic; SQLite MVP (Postgres Phase 2+).
- **L2 overlays**: 5/5 shipped (NSS curves, ERP US, CRP, rating-spread v0.2,
  expected-inflation canonical).
- **L3 indices**: 16/16 compute; 14-16 real-data (E2 + M3 landam via
  DB-backed readers quando daily_curves + daily_overlays têm upstream rows).
- **L4 cycles**: 4/4 operacionais (CCCS, FCS, MSC, ECS) com overlays
  (boom, bubble, dilemma, stagflation).
- **L5 regimes**: Phase 2+ scope — spec stub apenas.
- **L6 integration**: ERP composition live via `daily_cost_of_capital`.
- **L8 pipelines**: 9 daily pipelines operacionais com graceful
  degradation + structured logs + exit codes tipados.

Ver [`docs/milestones/m1-us.md`](docs/milestones/m1-us.md) para
scorecard completo + coverage matrix por país + CLI quickstart.
Deltas spec-vs-implementação em
[`docs/milestones/m1-us-gap-analysis.md`](docs/milestones/m1-us-gap-analysis.md).

### Quickstart operacional

```bash
uv sync
cp .env.example .env   # populate API keys

# Pipeline diário (US example)
uv run python -m sonar.pipelines.daily_curves   --country US --date 2024-12-31
uv run python -m sonar.pipelines.daily_overlays --country US --date 2024-12-31
uv run python -m sonar.pipelines.daily_cycles   --country US --date 2024-12-31

# CLI operacional
uv run sonar status --country US
uv run sonar health
uv run sonar retention run --dry-run
```

Cobertura cross-country: US (primário) + DE/PT/IT/ES/FR/NL (parcial via
Eurostat + ECB SDW + BIS). UK + JP no próximo milestone (M2 T1 Core).

## Estado documentacional (v1)

Antes do rewrite v2, a arquitetura conceptual foi documentada completa:

- **5 manuais** em 6 partes cada (~18.700 parágrafos total): Crédito, Monetário, Económico, Financeiro, Sub-Modelos
- **5 masters** consolidados (um por módulo, cada ~150-350KB)
- **5 planos** de fontes de dados (operationalization technical)

Esta documentação está em `/docs/methodology/` e serve como source of truth para a implementação v2.

## Estrutura do repo

Ver [REPOSITORY_STRUCTURE.md](docs/REPOSITORY_STRUCTURE.md) para layout detalhado.

Resumo:

```
sonar/
├── README.md                    # Este ficheiro
├── docs/                        # Documentação metodológica + técnica
│   ├── methodology/             # 5 manuais + masters
│   ├── data_sources/            # 5 planos
│   ├── architecture/            # Docs técnicos
│   └── wiki/                    # GitHub Wiki mirror
├── sonar/                       # Package Python principal
│   ├── connectors/              # Data source connectors
│   ├── db/                      # Schema + migrations
│   ├── cycles/                  # 4 cycle classifications
│   ├── submodels/               # 5 quantitative sub-models
│   ├── integration/             # Matriz 4-way + diagnostics
│   ├── outputs/                 # API layer
│   └── pipelines/               # Orchestration
├── tests/
├── scripts/                     # CLI entry points
├── notebooks/                   # Exploratory analysis
└── data/                        # Gitignored local DB + cache
```

## Roadmap

Ver [ROADMAP.md](docs/ROADMAP.md) para phases detalhadas.

Phase summary:

- **Phase 0** (in progress): bootstrap — arquivar v1, criar v2 foundations, wiki, CI/CD skeleton
- **Phase 1**: data foundation — schema v18, 5-7 core connectors (FRED, ECB, BIS, IGCP, WGB CDS, Shiller, Damodaran monthly for validation)
- **Phase 2**: sub-models — yield curves NSS, ERP daily, CRP, rating-to-spread, expected inflation. Portugal first, then expand.
- **Phase 3**: cycles — ECS, CCCS, MSC, FCS + overlays
- **Phase 4**: integration — matriz 4-way, diagnostics, cost of capital API
- **Phase 5**: dashboard — HTML/React prototype
- **Phase 6**: operationalization — alerts, backtesting, editorial pipeline automation

## Development

Ver [CODING_STANDARDS.md](docs/CODING_STANDARDS.md) para conventions.

Quick start (after Phase 0):
```bash
git clone <repo>
cd sonar
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
cp .env.example .env         # and fill in API keys
pytest                        # run tests
sonar-cli pipeline daily      # run daily pipeline
```

## Contributing

This is a personal project. See [CONTRIBUTING.md](docs/CONTRIBUTING.md) — primarily a solo repo with eventual potential for trusted collaborators.

## License

TBD (see [BRIEF_FOR_DEBATE.md](BRIEF_FOR_DEBATE.md) section on licensing). Default: proprietary, all rights reserved.

---

## Links úteis

- [Architecture overview](docs/ARCHITECTURE.md)
- [Repository structure rationale](docs/REPOSITORY_STRUCTURE.md)
- [Development roadmap](docs/ROADMAP.md)
- [Migration from v1 repo](docs/MIGRATION_PLAN.md)
- [Key decisions for debate](BRIEF_FOR_DEBATE.md)
- [Coding standards](docs/CODING_STANDARDS.md)
- [Wiki home](wiki/Home.md)

---

*7365 Capital · SONAR Research · 2026*
