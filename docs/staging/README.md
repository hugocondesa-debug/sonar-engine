# SONAR

> **S**ystematic **O**bservatory of **N**ational **A**ctivity and **R**isk
>
> Motor analítico de quatro ciclos macro + cinco sub-modelos quantitativos, com cobertura cross-country e foco em serviço programático + consumo público.

**Maintainer**: Hugo · 7365 Capital
**Status**: Phase 1 Week 9 in progress — **M2 T1 Core ~90 %** (16 países monetary M1 live; curves + overlays T1 expansion pendente)
**License**: Proprietary (to be determined)

---

## O que é o SONAR

SONAR **não é** uma plataforma de visualização de indicadores macro ao estilo Trading Economics ou CEIC.

SONAR **é** um motor analítico que produz:

1. **Classificação probabilística de quatro ciclos macro em tempo quase real**

   * Economic Cycle Score (ECS) + Stagflation overlay
   * Credit Cycle Score (CCCS) + Boom overlay
   * Monetary Stance Composite (MSC) + Dilemma overlay
   * Financial Cycle Score (FCS) + Bubble Warning overlay
2. **Cinco sub-modelos quantitativos derivados, operacionais daily**

   * Yield curves por país (NSS methodology, 5 output families)
   * Equity Risk Premium diária computada (não consumida de Damodaran)
   * Country Risk Premium (30+ países, CDS + sovereign spread + vol ratio)
   * Rating-to-spread mapping (22 notches cross-agency)
   * Expected inflation cross-country term structure
3. **Integração — matriz 4-way + quatro diagnósticos aplicados**

   * Seis padrões canónicos + cinco configurações críticas
   * Bubble detection, risk appetite regime, real estate cycle, Minsky fragility
   * Cost of capital cross-border framework

## Consumidores

SONAR expõe outputs via **dois canais**:

### 1. MCP / API privado (Hugo)

Interface programático para consumo dos outputs nos workflows de valuation:

* Cost of capital cross-country composites (k_e por país, ERP, CRP)
* Yield curves NSS (spot/zero/forward/real) por país
* Rating-spread implícito (22 notches cross-agency)
* Expected inflation term structure
* Cycle classifications + regimes + overlay triggers
* Composites cross-cycle (matriz 4-way + diagnostics)

Uso: DCF workflows em qualquer company — PT, internacional, cross-border, emerging markets. Cross-country **universal** cost-of-capital + curves engine, servido via MCP server + REST API.

### 2. Website público (sonar.hugocondesa.com)

Consumo público dos outputs computados — **não inputs raw** (licensing constraints BIS, TE paid tiers, FRED agreements).

Superfície pública:

* Cycle scores + regime classifications (live)
* Overlay activations (Stagflation, Boom, Dilemma, Bubble Warning)
* Yield curves rendering (derived output, not raw quotes)
* Cross-country comparison dashboards
* Editorial commentary triggered por regime shifts
* Methodology transparency pages

Frontend tech stack: TBD (Phase 2.5 decision — React vs static SSG vs hybrid).

## Filosofia

Cinco princípios não-negociáveis:

1. **Compute, don't consume** — ERP, CRP, yield curves, expected inflation são **calculados** pelo SONAR, não copiados de fontes externas. Damodaran/Bloomberg/Bundesbank servem como **cross-validation**, não como input primário.
2. **Metodologia transparente** — toda computação documentada, versionada, replicável. O competitive advantage é transparência, não secrecy.
3. **Cross-country uniform coverage** — T1 coverage (16 países) deve ser genuinamente uniform; não há country-privileged treatment. Portugal ingerido via Eurostat + ECB SDW + IGCP como qualquer outro T1 country.
4. **Cross-border coherence** — framework cost-of-capital funciona consistentemente para equity analysis em qualquer país T1/T2, com currency handling rigoroso (Fisher equation + PPP).
5. **Honest calibration** — confidence intervals explícitos, claims vs non-claims documentados, failure modes reconhecidos. Framework é probabilistic, não deterministic.

## Estado — Phase 1 Week 9 (M2 T1 Core em execução)

### Engine interno (L0-L4): essencialmente fechado

* **L0 connectors**: 28+ operacionais (FRED, Eurostat, BIS v2, ECB SDW, IGCP, Bundesbank, BoE, Shiller, Damodaran, FMP, Multpl, CBOE, CFTC, FINRA, Chicago Fed NFCI, Moody's, Yahoo, TE, AAII, Factset Insight, ICE BofA, MOVE, CBO, SPDJI Buyback, Yardeni, BoC Valet, RBA tables, Riksbank Swea, Norges Bank DataAPI, SNB data portal, Nationalbanken Statbank).
* **L1 persistence**: 18+ migrations Alembic; SQLite MVP (Postgres Phase 2+).
* **L2 overlays**: 5/5 shipped (NSS curves, ERP, CRP, rating-spread v0.2, expected-inflation canonical).
* **L3 indices**: 16/16 compute operational.
* **L4 cycles**: 4/4 operational (CCCS, FCS, MSC, ECS) com overlays (boom, bubble, dilemma, stagflation).
* **L5 regimes**: Phase 2+ scope — overlay booleans persistidos em cycle scores; tabela dedicada pendente.
* **L6 integration**: k_e US live via `daily_cost_of_capital`; cross-country composition pendente.
* **L8 pipelines**: 9 daily pipelines daemonized systemd operacionais.

### Coverage geográfica (M2 T1 Core)

| Layer | US | EA members (DE/FR/IT/ES/NL/PT) | GB | JP | CA | AU | NZ | CH | SE | NO | DK |
|-------|----|----|----|----|----|----|----|----|----|----|-----|
| M1 monetary | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Day 5 target |
| NSS curves | ✓ | — | — | — | — | — | — | — | — | — | — |
| ERP | ✓ | proxy | proxy | proxy | — | — | — | — | — | — | — |
| CRP | ✓ | ✓ | — | — | — | — | — | — | — | — | — |
| Cycles L4 | ✓ | partial | — | — | — | — | — | — | — | — | — |

M2 T1 Core complete quando **curves + overlays + cycles T1 uniform** (CAL-138 scope para Week 10).

### Camada externa (L7): não iniciada

L7 API + Website são o **unlock principal** para Phase 3. Actualmente zero implementation — engine corre em SQLite com CLI quickstart apenas.

### Quickstart operacional

```
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

Ver [`docs/milestones/m1-us.md`](docs/milestones/m1-us.md) para scorecard M1 US. Deltas spec-vs-implementação em [`docs/milestones/m1-us-gap-analysis.md`](docs/milestones/m1-us-gap-analysis.md).

## Estado documentacional (v1)

Antes do rewrite v2, a arquitetura conceptual foi documentada completa:

* **5 manuais** em 6 partes cada (~18.700 parágrafos total): Crédito, Monetário, Económico, Financeiro, Sub-Modelos
* **5 masters** consolidados (um por módulo, cada ~150-350KB)
* **5 planos** de fontes de dados (operationalization technical)

Esta documentação está em `/docs/methodology/` e serve como source of truth para a implementação v2.

## Estrutura do repo

Ver [REPOSITORY_STRUCTURE.md](docs/REPOSITORY_STRUCTURE.md) para layout detalhado.

## Roadmap

Ver [ROADMAP.md](docs/ROADMAP.md) para phases detalhadas.

Phase summary (revised 2026-04-22):

* **Phase 0** — Bootstrap & Specs — **COMPLETE** (2026-04-18)
* **Phase 1** — Vertical Slice L0→L4 + M1 US — **COMPLETE** (2026-04-20 Week 7)
* **Phase 2** — Horizontal Expansion — **IN PROGRESS** (M2 T1 Core ~90%; T2/T3 pending)
* **Phase 2.5** — L5 Regimes + L7 Infrastructure Prep — pending
* **Phase 3** — L7 API + Website Launch — pending (primary unlock milestone)
* **Phase 4** — Calibração Empírica + Scale — gated by 24m production data (earliest 2028-Q2)

## Development

Ver [CODING_STANDARDS.md](docs/CODING_STANDARDS.md) para conventions.

```
git clone <repo>
cd sonar-engine
uv sync
cp .env.example .env
uv run pytest
uv run sonar health
```

## Contributing

This is a personal project. See [CONTRIBUTING.md](docs/CONTRIBUTING.md) — primarily a solo repo with eventual potential for trusted collaborators.

## License

TBD (see [BRIEF_FOR_DEBATE.md](BRIEF_FOR_DEBATE.md) section on licensing). Default: proprietary, all rights reserved.

---

## Links úteis

* [Architecture overview](docs/ARCHITECTURE.md)
* [Repository structure rationale](docs/REPOSITORY_STRUCTURE.md)
* [Development roadmap](docs/ROADMAP.md)
* [M1 US milestone](docs/milestones/m1-us.md)
* [M1 US gap analysis](docs/milestones/m1-us-gap-analysis.md)
* [Key decisions for debate](BRIEF_FOR_DEBATE.md)
* [Coding standards](docs/CODING_STANDARDS.md)
* [Wiki home](wiki/Home.md)

---

*7365 Capital · SONAR Research · 2026*
