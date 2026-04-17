# 99 · Glossary

Referência rápida de terminologia SONAR.

## Framework terms

**SONAR** — Systematic Observatory of National Activity and Risk. Motor analítico de ciclos macro + sub-modelos quantitativos.

**7365 Capital** — marca institucional. 7365 = dias numa década, referenciando horizonte de investimento.

**"A Equação"** — programa editorial associado (Substack, YouTube, LinkedIn).

**Matriz 4-way** — classificação integrada cruzando os quatro ciclos em padrões canónicos + configurações críticas.

**Four diagnostics aplicados** — bubble detection, risk appetite regime, real estate cycle phase, Minsky fragility.

## Ciclos

**ECS** — Economic Cycle Score. Classificação de expansão/contração. Range 0-100.

**CCCS** — Credit Cycle Score. Fase do credit cycle (Minsky-inspired). Range 0-100.

**MSC** — Monetary Stance Composite. BC stance (accommodative/neutral/tight). Range 0-100.

**FCS** — Financial Cycle Score. Valuations/momentum/risk/positioning. Range 0-100.

### Overlays

**Stagflation overlay** — ECS overlay ativo quando economia slowing + inflation high.

**Boom overlay** — CCCS overlay quando credit expansion excessiva.

**Dilemma overlay** — MSC overlay quando BC pressured entre inflação e growth.

**Bubble Warning overlay** — FCS medium-term overlay via BIS credit/property gaps.

## Sub-models

**NSS** — Nelson-Siegel-Svensson. Metodologia standard para fitting yield curves, 6 parâmetros (β_0, β_1, β_2, β_3, λ_1, λ_2).

**ERP** — Equity Risk Premium. Retorno esperado extra acima do risk-free para equity. SONAR compute daily via 4 métodos.

**CRP** — Country Risk Premium. Premium adicional para risco soberano além do default spread. `CRP = default_spread × vol_ratio`.

**Default spread** — yield differential entre soverano e risk-free benchmark (US Treasury ou Bund).

**Vol ratio** — `σ_equity / σ_bond`. Damodaran default 1.5x; SONAR country-specific 5Y rolling.

**CDS** — Credit Default Swap. Insurance against sovereign default. 5Y CDS é benchmark.

**BEI / Breakeven inflation** — implied inflation expectation via nominal−real bond yields.

**5y5y forward** — implied 5-year inflation expectation starting 5 years out. Critical BC credibility indicator.

**PPP** — Purchasing Power Parity. FX tends to inflation differential long-run.

**Fisher equation** — `(1 + nominal) = (1 + real) × (1 + inflation)`.

**SONAR notch** — common scale 0-21 integrating S&P/Moody's/Fitch/DBRS ratings. AAA=21, D=0.

## Computational terms

**Bootstrap (curve)** — derivation of zero-coupon curve from coupon bond yields. Not related to statistical bootstrap.

**Forward curve** — implied future spot rates.

**Real curve** — inflation-adjusted yield curve, from linkers direct or derived.

**Swap curve** — OIS-based curve (SOFR, €STR, SONIA, TONAR).

**Duration** — bond price sensitivity to yield changes. Modified duration used for vol conversion.

**Payout yield** — dividend yield + buyback yield. Total shareholder cash return.

**CAPE / Shiller PE** — Cyclically Adjusted PE ratio. Price / 10Y real earnings avg.

**Tobin's Q** — market value / replacement cost of assets.

## Cycle states (canonical)

**Early Recovery** — emerging from recession, BC easing, growth picking up.

**Mid Expansion** — consolidated growth, balanced risks, neutral stance.

**Late Cycle** — mature expansion, tightening, valuations elevated.

**Slowdown** — momentum fading, tension between cycles.

**Recession** — contraction synchronized, credit stress.

**Stabilization** — bottom-finding, early signs of recovery.

### Critical configurations

**Bubble Warning** — FCS Euphoria + BIS overlay active.

**Stagflation Trap** — ECS weak + Stagflation overlay + MSC Dilemma.

**Credit Boom** — CCCS Boom overlay + expansion synchronized.

**Minsky Transition** — Fragility high + BC turning tight.

**Synchronized Easing** — all cycles declining + MSC accommodative (opportunity).

## Data terms

**Connector** — adapter for external data source (API, scrape, file).

**Tier 1/2/3/4** — country priority for coverage:
- Tier 1: US, Germany, UK, Japan
- Tier 2: France, Italy, Spain, Canada, Australia
- Tier 3: Portugal, Ireland, Netherlands, Sweden, Switzerland
- Tier 4: EM (China, India, Brazil, Turkey, Mexico, South Africa, Indonesia)

**Confidence score** — 0-1 quality metric on every SONAR output.

**Methodology version** — versioned computation method stored with output for reproducibility.

**Cross-validation** — SONAR output vs BC-published reference (Fed GSW, Bundesbank Svensson, BoE Anderson-Sleath).

## Portugal-specific

**IGCP** — Instituto de Gestão da Tesouraria e do Crédito Público. Portuguese debt agency.

**BPStat** — Banco de Portugal statistics system.

**INE** — Instituto Nacional de Estatística.

**PSI-20** — Portuguese Stock Index 20.

**OT** — Obrigações do Tesouro. Portuguese government bonds.

**BdP** — Banco de Portugal.

**MTS Portugal** — electronic trading platform for Portuguese sovereign debt.

**Golden Visa** — Portuguese residence-by-investment program (real estate context).

**PT-EA differential** — 5Y rolling inflation difference between Portugal and euro area.

## Institutional entities

**Fed** — Federal Reserve (US central bank).

**ECB** — European Central Bank.

**BoE** — Bank of England.

**BoJ** — Bank of Japan.

**BCB** — Banco Central do Brasil.

**Bundesbank** — Deutsche Bundesbank (German central bank).

**BIS** — Bank for International Settlements (central bank of central banks).

**IMF / WEO** — International Monetary Fund / World Economic Outlook.

**OECD** — Organisation for Economic Co-operation and Development.

**SPF** — Survey of Professional Forecasters (Philly Fed, ECB).

**NBER** — National Bureau of Economic Research (US recession dating).

**CEPR** — Centre for Economic Policy Research (EA recession dating).

## Rating agencies

**S&P Global Ratings** — one of Big 3 credit rating agencies.

**Moody's Investors Service** — Big 3.

**Fitch Ratings** — Big 3.

**DBRS Morningstar** — fourth major (relevant for ECB collateral framework).

## Editorial / brand

**A Equação** — YouTube programme + Substack column.

**SONAR Research** — brand for technical analytical outputs.

**27+ editorial angles** — catalog of content templates triggered by SONAR data states.

## Technical

**Pagan-Sossounov** — algorithm for cycle peak/trough dating.

**Anderson-Sleath** — BoE's smoothing spline methodology for yield curves.

**Gurkaynak-Sack-Wright (GSW)** — Fed's NSS parameters published daily (validation reference).

**Damodaran framework** — Aswath Damodaran (NYU Stern) valuation framework, foundational for ERP/CRP in SONAR.

**Minsky framework** — Hyman Minsky's financial instability hypothesis (hedge → speculative → Ponzi).

**Borio-Drehmann** — BIS researchers, developed credit gap methodology.

**Reinhart-Rogoff** — "This Time Is Different", crisis historical analysis.

---

*Glossary to be expanded as project evolves.*

*End of wiki main pages. Return to [Home](Home).*
