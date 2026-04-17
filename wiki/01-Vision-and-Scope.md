# 01 · Vision and Scope

## O problema

Analistas macro e gestores de investimento trabalham com ferramentas dispersas:
- **Trading Economics / CEIC** para indicadores brutos (mas sem framework analítico integrado)
- **Bloomberg / Refinitiv** para dados institucionais ($24k+/ano, outputs silo)
- **Damodaran** para ERP/CRP/rating spread (mensal, US-centric, não cross-integrated)
- **Shiller** para CAPE e historical (monthly, sem context atual)
- **Central banks** para yield curves fitted (per-country, metodologias inconsistentes)
- **Research houses** para cycle frameworks (qualitativos, não quantitativos)

Ninguém integra esses outputs num framework coerente, diário, cross-country, com metodologia transparente e Portugal-aware.

## A solução

**SONAR** é motor analítico que integra quatro ciclos macro + cinco sub-modelos quantitativos, produzindo outputs daily usáveis para:

1. **Editorial** — coluna "A Equação" com rigor quantitativo
2. **Valuation** — Portuguese equity DCF e cross-border analysis
3. **Allocation** — cycle-informed portfolio (futuro)
4. **Fund** — 7365 Capital discretionary macro (eventual)

## Escopo v2

### In scope

- **Quatro ciclos macro** com classification + overlays
  - Economic (ECS) + Stagflation
  - Credit (CCCS) + Boom
  - Monetary (MSC) + Dilemma
  - Financial (FCS) + Bubble Warning

- **Cinco sub-modelos quantitativos**
  - Yield curves por país (NSS methodology)
  - ERP diária computada (não consumida)
  - Country Risk Premium (30+ países)
  - Rating-to-spread mapping
  - Expected inflation cross-country

- **Integração**
  - Matriz 4-way (seis padrões canónicos)
  - Quatro diagnósticos aplicados (bubble, risk, real estate, Minsky)
  - Cost-of-capital framework cross-border

- **Cobertura**
  - 15+ países Tier 1-3 (core)
  - 4+ países Tier 4 (experimental)
  - Portugal-aware throughout

- **Outputs**
  - API interna
  - Alerts automáticos
  - Editorial pipeline (27+ ângulos catalogados)
  - Dashboard (MVP Streamlit, later React)

### Out of scope (v2)

- **Alta frequência (intraday)** — daily é suficiente
- **Trading automation** — SONAR informa, não executa
- **Multi-user platform** — single user, eventual fund
- **Crypto derivatives detail** — BTC/ETH on-chain via FCS, não full coverage
- **Sector-level granularity** — country-level prioritized
- **Technical analysis** — fundamentally-driven framework
- **Options pricing engine** — uses market data, not own pricing

### Future (v3+)

- Multi-asset strategy engine
- Portfolio construction automation
- Institutional features (SSO, audit, multi-user)
- ML-augmented signal detection

## Users

### Primary (MVP)

**Hugo** (solo operator, 7365 Capital CBO)
- Daily usage para editorial column prep
- Research tool for investment theses
- Content pipeline generator

### Secondary (mid-term)

**Clientes editoriais** de "A Equação"
- Consume output via column, newsletter
- Not direct SONAR users
- Indirect beneficiaries of quantitative rigor

### Tertiary (long-term, se fund)

**Institutional partners / limited audience**
- Access to specific outputs
- Under licensing agreement
- Not full SONAR access

## Princípios

Cinco princípios não-negociáveis:

### 1. Compute, don't consume

Sub-models são **calculados localmente** a partir de dados raw. Damodaran/Bloomberg/Bundesbank servem como **cross-validation**, não input primário.

**Exemplo**: ERP não é copiada do Damodaran mensal — SONAR compute daily usando S&P 500 + analyst estimates + buybacks + Treasury, com Damodaran como validação (<20bps target).

### 2. Metodologia transparente

Toda computação é documented, versioned, replicable.

- Manuais em `docs/methodology/` (source of truth)
- ADRs para decisões arquiteturais
- Confidence intervals explícitos em outputs
- Methodology versions em database

### 3. Portugal-aware by design

Cada sub-model tem derivação específica para Portugal:
- PT yield curve via IGCP + ECB SDW + MTS Portugal
- PT CRP daily via CDS 35bps + PSI-20/bond vol ratio
- PT expected inflation via EA + historical differential (sem linker mercado direto)
- PT rating consolidado quatro agencies
- Use cases portugueses priorizados (EDP DCF detalhado)

### 4. Cross-border coherence

Framework cost-of-capital funciona:
- Portuguese equity (e.g., EDP) em EUR
- Brazilian bank cross-border em EUR ou BRL (com FX handling)
- EM equity em USD ou local currency
- Fisher equation + PPP forecasting integrated

### 5. Honest calibration

Framework é **probabilistic**, não deterministic:
- Confidence scores
- Range de resultados
- Claims vs non-claims documented
- Failure modes acknowledged

## Non-goals

- **Não substituir judgment humano** — SONAR informa decisões, não as toma
- **Não replace Bloomberg** — SONAR integra, não compete em coverage bruto
- **Não ser accurate 100%** — framework é probabilistic, assume incerteza
- **Não ser real-time** — daily é suficiente e seguro

## Diferenciação competitiva

Vs Bloomberg:
- **Transparência total** metodológica
- **Cross-integrated** (cycle + sub-model + diagnostics in one framework)
- **Portugal-aware** especificamente
- **Custo operacional** fraction (<$50/mo vs $24k/ano)

Vs Damodaran:
- **Daily frequency** (vs mensal)
- **Cross-integrated** com cycle framework
- **Cost of capital workflow** end-to-end
- **Metodologia replicable**

Vs Research houses:
- **Quantitative rigor** (vs qualitativo-primary)
- **Systematic coverage** (vs seletivo)
- **Operacional para analyst use**, não só reading

## Sucesso — como medir

### Phase 1-3 (MVP)

- [x] Framework conceptual documented (5 manuais completos)
- [ ] First connector operacional + DB + CLI
- [ ] Yield curve para Portugal daily
- [ ] ERP US daily
- [ ] CRP para 30+ países

### Phase 4-6 (Full v2)

- [ ] Quatro ciclos operacionais
- [ ] Cost of capital API para Portugal + EA core
- [ ] Primeira coluna "A Equação" SONAR-powered published
- [ ] Dashboard MVP shareable

### Phase 7-9 (Complete)

- [ ] 30 days stable operation com automated pipeline
- [ ] Backtesting validates 87%+ agreement Pagan-Sossounov (per manual target)
- [ ] Editorial pipeline generates 4+ angles/week
- [ ] Ready para fund-preparation discussions

---

*Next: [02 · Architecture Overview](02-Architecture-Overview)*
