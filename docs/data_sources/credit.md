# SONAR v2 · Data sources — Credit cycle (CCCS)

> **Layer scope:** L3 indices `L1..L4` (credit stock/gap/impulse/DSR) + L4 `cycles/credit-cccs` + L2 overlays `rating-spread`, `crp`.
> **Phase 0 Bloco D1** — rewrite baseado em `D1_coverage_matrix.csv` (2026-04-18) + D0 audit findings.
> **Status:** doc canónico. Substitui v1 credit.md (607 linhas).

Documento alinhado com:
- `docs/specs/cycles/credit-cccs.md` (composite `CCCS_v0.1 = 0.44·CS + 0.33·LC + 0.22·MS` — QS omitido Phase 1).
- `docs/specs/indices/credit/{L1,L2,L3,L4}.md`.
- `docs/specs/overlays/{rating-spread,crp}.md`.
- `docs/data_sources/country_tiers.yaml` (BIS universe = T1+T2 mostly).
- `docs/data_sources/D1_coverage_matrix.csv`.
- `docs/data_sources/D0_audit_report.md` (critical finding: TE ratings 4Y stale → TE rejected para rating-spread).

---

## 1. Overview e hierarquia de fontes

### 1.1 Mandato do ciclo

O Credit Cycle Score (CCCS) mede a fase cíclica do crédito privado non-financial. Consome 4 sub-indices (Phase 1 usa 3):

| Index | Sub-index | Peso CCCS v0.1 | Mandato |
|-------|-----------|----------------|---------|
| L1-credit-to-gdp-stock | CS (Credit Stock) | 0.44 | Nível Credit/GDP ratio (slow-moving) |
| L2-credit-to-gdp-gap | — | — | Input para CS via one-sided HP filter (Basel III) |
| L3-credit-impulse | LC (Loan Cycle) | 0.33 | Credit impulse (Biggs-Mayer-Pick) + growth |
| L4-dsr | MS (Marginal Stress) | 0.22 | Debt service ratio (Drehmann-Juselius) |
| — (Phase 2+) | QS (Quality Stress) | 0 v0.1 | NPL + credit quality — **omitido** MVP |

Ver spec `cycles/credit-cccs.md §2` para rationale QS omitido (NPL data latency ~90 dias + coverage BIS parcial não viable realtime).

### 1.2 Hierarquia de fontes (5 níveis canónicos)

```
1. PRIMARY          BIS (Bank for International Settlements)
   └── WS_TC (credit-to-GDP), WS_DSR (pre-computed DSR 32 países),
       WS_CREDIT_GAP (one-sided HP gap)
2. OVERRIDE T1      FRED (US derivations) / Central banks nativos
   └── TDSP (US household DSR), QUSPAMUSQTMKTP (US credit), CARDS
3. SECONDARY EU     ECB SDW (EA credit counterparts)
   └── BSI + MIR dataflows
4. SECONDARY EM     BCB (Brazil), BOK (Korea), RBI (India) — Phase 2
   └── native central banks onde BIS tem latency/gap
5. TERTIARY         Scrape agency rating sites + Damodaran (annual)
   └── S&P, Moody's, Fitch, DBRS press releases (rating-spread overlay)
```

**BIS dominance no CCCS** é estrutural: BIS publica a série canónica `credit-to-GDP` em base SNA harmonizada (non-financial private sector). D1 smoke test confirmou WS_DSR responsive (PT historical disponível). WS_TC key pattern resolved 2026-04-20 (CAL-019 closed): 7-dimension SDMX v2 structure `BIS_TOTAL_CREDIT(2.0)` — see §3.1 below.

**Não usadas no CCCS:**
- **FMP** — `/api/stable/` 403 em todos endpoints tested. Sem alternative path para credit data.
- **TE** — breadth disponível mas BIS é authoritative para credit-to-GDP (TE value frequently delayed + aggregation method unclear).
- **Shiller/multpl/aaii** — equity/sentiment, não credit.

### 1.3 Critério de escolha primary vs override

```
If country in BIS_43_UNIVERSE and series in BIS_DATAFLOW_catalog:
    primary = BIS
elif country == "US" and series has FRED_NATIVE:
    primary = FRED (e.g. TDSP)
elif country in ECB_EA and series in ECB_SDW_BSI:
    primary = ECB_SDW
elif country in TE_BREADTH_T1_T3:
    primary = TE (private credit rate, loan growth)
else:
    primary = GAP
```

---

## 2. Country tier coverage

### 2.1 Tabela de cobertura esperada

| Tier | Count | L1 credit-to-GDP | L2 gap | L3 impulse | L4 DSR | CCCS viável? |
|------|-------|------------------|--------|------------|--------|--------------|
| T1 | 16 | ✓ BIS universe | ✓ | ✓ derived | ✓ (32 pre-computed) | Sim — full confidence |
| T2 | 30 | ✓ BIS 43 covers most | ~ BIS partial | ~ derivable | ~ BIS 32 partial | Sim — T2 EM via BIS |
| T3 | 43 | ✗ maioria fora BIS 43 | ✗ | ✗ | ✗ | Não — flag `COVERAGE_INSUFFICIENT` |
| T4 | ~110 | ✗ | ✗ | ✗ | ✗ | Não |

**BIS 43 country universe** (confirmado WS_TC metadata): AR, AU, AT, BE, BR, CA, CL, CN, CO, CZ, DK, EA, FI, FR, DE, GR, HK, HU, IN, ID, IE, IL, IT, JP, KR, LU, MY, MX, NL, NZ, NO, PL, PT, RU, SA, SG, ZA, ES, SE, CH, TH, TR, UK, US.

**BIS WS_DSR 32 countries** (pre-computed DSR): subset do WS_TC — foco G10 + majorel EMs. PT presente (confirmed D1-T2 smoke 200 OK).

### 2.2 Override nativo por país

| Country | Native | Series |
|---------|--------|--------|
| US | FRED | `TDSP` (household DSR), `QUSPAMUSQTMKTP` (credit-to-GDP market series), `DRTSCLCC` (credit card delinquency) |
| EA | ECB SDW | `BSI.M.{C}.N.A.L20.A.1.U2.2240.Z01.E` (total loans), `MIR` series (interest rates) |
| PT | BdP (BPstat) | BPstat séries directas para loans; redundante vs ECB SDW |
| UK | BoE | Bankstats download |
| JP | BoJ | Flow of Funds |
| TR | TCMB | TP.KR* family — **bloqueado D1** (ver economic.md §3.7) |

### 2.3 Degradação T3/T4

Para países fora BIS 43:
- L1 CS via TE `/country/{c}/indicators` Cat=Money subfilter "Private credit" — qualidade variável.
- L3 LC via loan growth TE — typically OK.
- L4 MS via DSR computed locally se temos total debt stock + total interest payments.
- Se ≥2 sub-indices unavailable → CCCS emite `NULL` + flag `COVERAGE_INSUFFICIENT`.

---

## 3. Endpoints por fonte

### 3.1 BIS — SDMX v2 API

**Base:** `https://stats.bis.org/api/v2`
**Auth:** none (public).
**Format:** default XML; `?format=jsondata` → SDMX-JSON 1.0.
**Accept header recommended:** `application/vnd.sdmx.data+json;version=1.0.0, application/json`.

**Data endpoint pattern (SDMX v2):**
```
GET /data/dataflow/BIS/{FLOW}/{VERSION}/{KEY}?format=jsondata
    &startPeriod=YYYY-Qn&endPeriod=YYYY-Qn
```

**Dataflows relevantes:**

| Dataflow | Versão | Contents | CCCS consumer |
|----------|--------|----------|---------------|
| `WS_TC` | 1.0 | Credit statistics total credit to non-financial sector | L1 credit-to-GDP |
| `WS_DSR` | 1.0 | Debt service ratios pre-computed | L4 DSR |
| `WS_CREDIT_GAP` | 1.0 | Credit-to-GDP gap (BIS pre-computed one-sided HP) | L2 gap |
| `WS_LBS_D_PUB` | 1.0 | Locational banking statistics (property prices cross) | F1 financial |
| `WS_LONG_CPP` | 1.0 | Consumer prices long series | (not CCCS) |

**Key structure WS_TC** (7 dimensions — resolved 2026-04-20, CAL-019 closed):
```
{FREQ}.{BORROWERS_CTY}.{TC_BORROWERS}.{TC_LENDERS}.{VALUATION}.{UNIT_TYPE}.{TC_ADJUST}
```
Exemplo canónico `Q.PT.P.A.M.770.A`:
- FREQ = Q (quarterly) per `CL_FREQ`
- BORROWERS_CTY = PT per `CL_AREA` (ISO-2 + 86 other BIS area aggregates)
- TC_BORROWERS = P (Private non-financial sector) per `CL_TC_BORROWERS` (valid: C/G/H/N/P)
- TC_LENDERS = A (All sectors) per `CL_TC_LENDERS` (valid: A/B — **not `M` as previously documented**)
- VALUATION = M (Market value) per `CL_VALUATION` (valid: M/N)
- UNIT_TYPE = 770 (Percentage of GDP) per `CL_BIS_UNIT` (code `770A` previously documented was invalid — true code is integer `770`)
- TC_ADJUST = A (Adjusted for breaks) per `CL_ADJUST` (valid: 0/1/A/U)

DataStructure reference: `BIS:BIS_TOTAL_CREDIT(2.0)` (SDMX v2; the old v1 docs that referenced 5 dimensions were for a superseded structure).

**CAL-019 resolution (2026-04-20)**: smoke test per Commit 1 of credit-indices-brief-v3 with new 7-dim key returned **200 OK for 7/7 T1 countries** (US/DE/PT/IT/ES/FR/NL) with plausible credit-to-GDP values 2023-Q4 → 2024-Q2:

| Country | 2023-Q4 | 2024-Q1 | 2024-Q2 |
|---|---|---|---|
| PT | 136.1 | 133.9 | 132.9 |
| US | 147.0 | 146.0 | 145.1 |
| DE | 139.6 | 139.1 | 138.9 |
| IT | 98.0 | 96.6 | 95.8 |
| ES | 130.1 | 129.1 | 128.4 |
| FR | 216.6 | 214.2 | 214.3 |
| NL | 285.3 | 279.7 | 276.0 |

Cached structure responses: `tests/fixtures/bis/ws_tc_structure.json` (full dimensions+codelists) + `ws_tc_PT_sample.json` (3-quarter sample). Requires `Accept: application/vnd.sdmx.data+json;version=1.0.0, application/json` header.

**Key structure WS_DSR** (3 dimensions, dataflow version 1.0 — validated 2026-04-20):
```
{FREQ}.{BORROWERS_CTY}.{DSR_BORROWERS}
```
Exemplo canónico `Q.US.P`:
- FREQ = Q
- BORROWERS_CTY = US
- DSR_BORROWERS = P (Private non-financial sector)

DataStructure reference: `BIS:BIS_DSR(1.0)`. US 2024-Q2 DSR = 14.5%. 7/7 T1 validated (requires explicit Accept header; omission returns 406).

**Key structure WS_CREDIT_GAP** (5 dimensions, dataflow version 1.0 — validated 2026-04-20):
```
{FREQ}.{BORROWERS_CTY}.{TC_BORROWERS}.{TC_LENDERS}.{CG_DTYPE}
```
CG_DTYPE enumeration:
- A = Credit-to-GDP ratios (actual data)
- B = Credit-to-GDP trend (BIS one-sided HP)
- C = Credit-to-GDP gaps (actual-trend)

For L2 gap consumer, canonical key `Q.PT.P.A.C` → PT private non-financial credit gap pp (2024-Q2 = -38 pp, deleveraging). DataStructure reference: `BIS:BIS_CREDIT_GAP(1.0)`.

**Structure endpoint (para descoberta):**
```
GET /structure/dataflow/BIS/{FLOW}?detail=allstubs&format=json
```

**Rate limit:** undocumented; BIS público "polite use" — 1 req/sec adequate.

### 3.2 FRED — credit secondary

| Consumer | Series ID | Frequency | Notes |
|----------|-----------|-----------|-------|
| L1 US credit-to-GDP derivation | `QUSPAMUSQTMKTP` | Quarterly | Total credit market; compare vs GDP |
| L4 US household DSR | `TDSP` | Quarterly | Fed Financial Obligations Ratio — primary US path |
| L4 US consumer DSR | `CDSP` | Quarterly | Consumer-only variant |
| Credit card delinquency | `DRCCLACBS` | Quarterly | NPL proxy — QS Phase 2+ |
| C&I loan delinquency | `DRTSCIS` | Quarterly | Business loans NPL |
| Commercial mortgage delinquency | `DRCRELEXFACBS` | Quarterly | CRE NPL |

**Consumer credit outstanding:** `TOTALSL` (total consumer credit), `REVOLSL` (revolving credit card), `NONREVSL` (non-revolving — auto, student).

### 3.3 ECB SDW — EA credit

**Base:** `https://data-api.ecb.europa.eu/service/data`

| Dataflow | Example key | Contents |
|----------|-------------|----------|
| `BSI` (Balance Sheet Items) | `M.{C}.N.A.L20.A.1.U2.2240.Z01.E` | Total loans NFC + household |
| `MIR` (MFI Interest Rates) | `M.{C}.B.{A2Z}.EUR.LEUR` | Loan interest rates EA |
| `RPP` (Residential Property Prices) | `Q.{C}.N.TD.00.4.00` | For F1 valuations cross-cycle |

### 3.4 BdP BPstat — Portugal

**Base:** `https://bpstat.bportugal.pt/data/v1`
**Auth:** none (public open data).
**Format:** JSON direct.

| Series | BPstat ID | Notes |
|--------|-----------|-------|
| PT private credit | `12559601` | Total loans to non-financial private |
| PT household DSR proxy | derived via loans × implicit rate | Not published directly |

**Redundant vs ECB SDW** — use ECB SDW como primary para consistency cross-country; BPstat fallback se ECB SDW unreachable.

### 3.5 TE — credit breadth T2-T3

**Base:** `https://api.tradingeconomics.com`

| Consumer | Endpoint | Notes |
|----------|----------|-------|
| Private credit (T3 breadth) | `/country/{c}/indicators` Cat=Money subfilter "Private debt" | Variable coverage |
| Loan growth | `/country/{c}/indicators` Cat=Money subfilter "Loans" | Monthly/quarterly |
| Banking sector indicators | `/country/{c}/indicators` Cat=Money subfilter NPL | Mix — T1 confiável, T3 sparse |

**Caveat:** TE `Private debt` é frequently a stock em local currency sem GDP ratio. Need to compute ratio locally vs GDP series (ver E1-activity). Fragile — prefer BIS.

### 3.6 Scrape — rating agency press releases

**Status:** **primary path para rating-spread overlay forward** (Phase 1 implementation).

Per D0 audit TE `/ratings/historical/{country}` retorna latest 2022-09-09 (4Y stale) → **rejected**.

**Source hierarchy (rewrite pendente per CSV rating-spread rows):**

1. **Damodaran annual** — `pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ctryprem.html`
   - File: `histimpl.xlsx` (historical implied country risk premium, annual since ~1994)
   - Coverage: ~170 countries
   - Licence: academic free with attribution
   - Usage: **historical backfill only** (annual freq inadequate para daily overlay emissions; serve como sanity baseline).

2. **S&P Global Ratings press releases** — `www.spglobal.com/ratings/en/research-insights/`
   - Ethical scrape: polite rate ≤1 req/min, User-Agent identifying, respect robots.txt.
   - Coverage: sovereign + corporate; filter por "sovereign rating action".
   - Format: HTML — parse date, country, rating from/to, outlook, watchlist.
   - Scope: recent (last 90 days free; historical paywalled).

3. **Moody's** — `www.moodys.com/research` similar.
4. **Fitch** — `www.fitchratings.com/research/sovereigns` similar.
5. **DBRS** — `www.dbrsmorningstar.com/research` similar.

**Backlog spec rewrite:** rating-spread overlay ainda contem fallback TE no spec v0.1. Bloco E planeia rewrite strip TE + add Damodaran + agency scrape. Ver `backlog/calibration-tasks.md CAL-001`.

### 3.7 Scrape — CDS (overlay CRP)

**Source:** `worldgovernmentbonds.com` — path único free para sovereign CDS 5Y em ~45 países.

**Constraint:** scrape polite + ethical rate ≤1 req/5min (site não-industrial). Attribution required.

**Alternative (Tier 3 pago):** Markit/S&P CDS Index, Bloomberg. Out-of-scope Phase 1.

**D1 finding:** site responsive; structure stable last 18mo (scrape pattern documentable). Phase 1 implementação requer CSS-selector-based parser.

---

## 4. Série catalog — por index / overlay

Legenda igual a economic.md.

### 4.1 L1 — Credit-to-GDP stock

| Série | Pri | Ovr | Freq | Lat | Spec § |
|-------|-----|-----|------|-----|--------|
| `credit_to_gdp_ratio` | BIS `WS_TC` (Q.{C}.P.M.{unit}) | FRED `QUSPAMUSQTMKTP` (US); ECB SDW BSI (EA members) | Q | 90 | L1 §2.1 |

**Input for L2 gap computation** (Basel III one-sided HP filter λ=400 000).

**D1 blocker:** WS_TC key unit code pending — see §3.1 note. L1 spec §7 adia implementação de real-value keys para fase de connector dev.

### 4.2 L2 — Credit-to-GDP gap

| Série | Pri | Ovr | Freq | Lat | Spec § |
|-------|-----|-----|------|-----|--------|
| `credit_gap_hp_filtered` | BIS `WS_CREDIT_GAP` (pre-computed) | Compute locally from L1 raw | Q | 90 | L2 §2.1 |

**Computation local (fallback):**
```python
from statsmodels.tsa.filters.hp_filter import hpfilter
trend, _ = hpfilter(credit_to_gdp_log_quarterly, lamb=400_000)
gap_pp = (credit_to_gdp - trend) × 100  # expressed in pp of GDP
```

**Basel III calibration** (BIS Working Paper 355): `λ = 400 000` para quarterly data (equivalent suavidade 30-year cycle).

**Caching:** HP filter é expensive recomputação — cache per (country, vintage) key (ver spec `conventions/patterns.md` HP cache policy).

### 4.3 L3 — Credit impulse

| Série | Pri | Ovr | Freq | Lat | Spec § |
|-------|-----|-----|------|-----|--------|
| `credit_impulse` | BIS `WS_TC` derived | Local compute | Q | 90 | L3 §2.1 |

**Definição (Biggs-Mayer-Pick 2010):**
```
credit_impulse_t = (flow_credit_t - flow_credit_{t-4}) / GDP_t
  where flow_credit_t = stock_credit_t - stock_credit_{t-1}
```

Segunda derivada do stock — captura mudanças de acceleração, não level.

### 4.4 L4 — Debt service ratio (DSR)

| Série | Pri | Ovr | Freq | Lat | Spec § |
|-------|-----|-----|------|-----|--------|
| `debt_service_ratio` | BIS `WS_DSR` Q.{C}.P | FRED `TDSP` (US household); compute localmente para non-BIS-32 | Q | 90 | L4 §2.1 |

**BIS WS_DSR universe (32 países):** AR, AU, BE, BR, CA, CN, DE, DK, EA, ES, FI, FR, GB, GR, HK, ID, IE, IL, IN, IT, JP, KR, MX, NL, NO, PL, PT, RU, SE, TH, TR, US, ZA.

**Computation local** (quando fora BIS 32):
```
DSR_t = (interest_payments_t + principal_repayments_t) / disposable_income_t
```

**Spec L4 §5:** QS (quality stress) via NPL é Phase 2+. MS (marginal stress) via DSR approaching thresholds é Phase 1 (implementação parcial).

### 4.5 Overlay L2 — rating-spread

| Série | Pri | Freq | Notes |
|-------|-----|------|-------|
| `rating_actions_sp` | Scrape S&P (Damodaran annual backfill) | Event-driven + annual | Emit daily overlay; hold between events |
| `rating_actions_moodys` | Scrape Moody's | idem | idem |
| `rating_actions_fitch` | Scrape Fitch | idem | idem |
| `rating_actions_dbrs` | Scrape DBRS | idem | idem |
| `notch_spread_calibration` | FRED `BAMLC0A0CM` + `BAMLH0A0HYM2` calibrated annually | Daily (ICE indices) | Global lookup table rating notch → spread bps |

**Spec rewrite pending (Bloco E):** versão v0.1 do rating-spread spec assume TE fallback. Per D0 rejeitado. Bloco E planeia:
- Remover fallback TE.
- Add Damodaran annual (`histimpl.xlsx`) para backfill pre-2023.
- Add scrape forward para eventos 2023+.
- Calibrar `notch_spread_calibration` via regression of ICE BofA spreads on rating (CAL-020).

**Licensing:** scrape press releases público via robots.txt compliance. Damodaran academic free.

### 4.6 Overlay L2 — CRP (Country Risk Premium)

| Série | Pri | Freq | Notes |
|-------|-----|------|-------|
| `cds_5y_sovereign` | Scrape `worldgovernmentbonds.com` | Daily | ~45 países live; ethical scrape |
| `sovereign_yield_spread_vs_bench` | Derived from TE + FRED Bund/UST | Daily | Country 10Y − Bund (EA) / UST (USD) |
| `equity_returns_vol` | TE `/markets/historical/{symbol}` + compute 5Y rolling σ | Daily → derived | Non-US indices via TE |
| `sovereign_bond_returns_vol` | Derived — yfinance ETF proxy (`TLT`, `IEF`, ...) | Daily → derived | Phase 1 uses ETF proxy |

**CRP overlay pattern:** "hierarchy best-of" (ver `conventions/patterns.md`):
1. CDS se disponível (liquid ~45 países).
2. Spread vs benchmark se yield data completa mas CDS illiquid.
3. Equity/bond σ ratio × ERP (Damodaran method) como tertiary.

**Consumer specs:** `cycles/credit-cccs.md §6` + overlay spec `crp.md`.

---

## 5. Fallback hierarchy

### 5.1 Árvore de decisão CCCS

```
Para cada (series, country):
    1. IF country in BIS_UNIVERSE AND series in BIS_DATAFLOW:
         → BIS
    2. ELIF country == "US" AND series has FRED native:
         → FRED (TDSP, QUSPAMUSQTMKTP)
    3. ELIF country in ECB_EA AND series in BSI/MIR:
         → ECB SDW
    4. ELIF country in TE_BREADTH AND TE covers:
         → TE (breadth T2-T3)
    5. ELSE:
         → flag {SERIES}_{COUNTRY}_MISSING + CCCS degraded
```

### 5.2 Policy 1 aplicado

Se CCCS tem 2 dos 3 sub-indices (CS, LC, MS) válidos (threshold P1):
```
valid = {CS, LC}  # hypothesis: MS missing
total_weight_valid = 0.44 + 0.33 = 0.77
re-weighted = {CS: 0.44/0.77, LC: 0.33/0.77}
CCCS = 0.571 × CS + 0.429 × LC
confidence = min(0.75, base)
flag = [MS_MISSING, CCCS_REWEIGHTED]
```

Se ≥2 sub-indices missing → `CCCS = NULL`, flag `COVERAGE_INSUFFICIENT`.

### 5.3 Override conditions

- **BIS primary sempre** se country in BIS universe (latency aceitável; authoritative).
- **FRED US override** para DSR (TDSP) — BIS WS_DSR US presente mas FRED TDSP tem finer granularity (household vs all-private).
- **ECB SDW EA override** — EA aggregate BIS lagged; SDW fresher.

---

## 6. Known gaps e backlog

### 6.1 Gaps críticos (BLOCKING)

| Gap | Impacto | Mitigação | Backlog |
|-----|---------|-----------|---------|
| BIS WS_TC key unit code | L1 credit-to-GDP failing smoke test | Debug dimension code in Phase 1 connector dev | `CAL-019` |
| TE rating data 4Y stale | Rating-spread overlay cannot use TE | Scrape agency + Damodaran | spec rewrite Bloco E, `CAL-001` |
| FMP /api/stable 403 | Sem commodities/financial breadth | Parked P2+; no credit impact | `P2-014` |
| BIS 43 universe gap (T3) | 43 T3 countries sem credit data nativo | Flag + CCCS degraded | — |
| CDS scrape fragility | worldgovernmentbonds.com único path free | Monitor breakage; consider Tier 3 pago se fail | — |

### 6.2 Gaps de qualidade (CORE)

- **BIS publication lag:** BIS publica credit data Q+90 dias typical. CCCS cannot be daily-fresh; emit daily but cycle state changes only upon Q release.
- **One-sided vs two-sided HP filter:** Basel III official é one-sided (eliminating future-leakage). `WS_CREDIT_GAP` é one-sided. Local compute deve replicar (`hpfilter` default é two-sided — fix: custom one-sided implementation).
- **DSR local compute accuracy:** para países fora BIS-32, DSR depends on interest rates + debt stock + income. TE interest rates quality variable → accuracy bias.

### 6.3 Out-of-scope Phase 0 / Phase 1

- **QS (Quality Stress) sub-index** — NPL + default rates. Coverage BIS parcial + latency >90 dias. Phase 2 `P2-001` reintroduz QS.
- **Sectorial granularity** (mortgage vs consumer vs C&I vs corporate bonds) — aggregate only Phase 1.
- **Housing cycle** — parte de F1-valuations (financial.md), não CCCS.
- **Minsky fragility layer** — Phase 3+, cross-cycle composite FCS.

### 6.4 Calibration tasks

- `CAL-001` — rating-spread spec rewrite (Bloco E).
- `CAL-004` — CCCS weights empirical validation (v0.1 = BIS WP 355 derived).
- `CAL-009` — HP filter λ sensitivity test.
- `CAL-019` — BIS WS_TC key unit code debug.
- `CAL-020` — notch→spread calibration (quarterly).

---

## 7. Licensing status

| Fonte | Licença | Uso permitido |
|-------|---------|--------------|
| BIS | CC-BY-4.0 (public data mandate) | Full re-use with attribution |
| FRED | Public domain | Sem restrições |
| ECB SDW | ECB re-use (≈CC-BY) | Attribution |
| BPstat | Open Data PT | Attribution |
| TE | Commercial (tier pending) | Internal-only |
| Damodaran | Academic free | Attribution "Damodaran, NYU Stern" |
| S&P / Moody's / Fitch / DBRS press | Copyright — **scrape headlines + metadata only** | Cite agency; no full-text redistribution |
| worldgovernmentbonds.com | Website TOS (attribution) | Polite rate + source cite |

**Ethical scrape policy** (reminder governance/DATA.md): User-Agent identifies SONAR research; honor robots.txt; rate ≤1 req/min para non-industrial sites; cache aggressively para minimize requests.

---

## 7.5 Ingestion cadence — BIS credit side (CAL-058)

BIS quarterly observations for WS_TC / WS_DSR / WS_CREDIT_GAP are
pulled into `bis_credit_raw` by a daily pass.

- **Pipeline**: `python -m sonar.pipelines.daily_bis_ingestion`
- **Defaults**: last 90 days back from today, all 7 T1 countries,
  all 3 dataflows (21 fetches / pass, ~21 s wall clock at BIS
  polite-use 1 req/sec pacing).
- **Semantics**: idempotent upsert. `persist_bis_raw_observations`
  per-row SELECT-then-INSERT/UPDATE by `(country, date, dataflow)`;
  existing rows with matching `fetch_response_hash` are skipped,
  mismatching hash triggers in-place update with a
  `BIS_DATA_REVISION` warning log. Returns `{new, skipped, updated}`
  counts.
- **Revision detection**: `fetch_response_hash` is sha256 over
  `(country, date, value_pct, series_key)` — narrow hash, not
  full-response, because BIS embeds request timestamps that would
  otherwise break hash stability.
- **Consumer**: `daily_credit_indices --backend=db` drives a
  `DbBackedInputsBuilder` that reads 22Y of WS_TC history per
  `(country, date)` and assembles L1 + L2 inputs (L3 + L4 remain
  scope-trimmed pending CAL-059 / CAL-060).

---

## 8. Cross-refs

### 8.1 Specs consumer

- `docs/specs/indices/credit/L1-credit-to-gdp-stock.md`.
- `docs/specs/indices/credit/L2-credit-to-gdp-gap.md`.
- `docs/specs/indices/credit/L3-credit-impulse.md`.
- `docs/specs/indices/credit/L4-dsr.md`.
- `docs/specs/cycles/credit-cccs.md`.
- `docs/specs/overlays/rating-spread.md` (rewrite pendente Bloco E).
- `docs/specs/overlays/crp.md`.

### 8.2 Outros cycles

- `docs/specs/cycles/financial-fcs.md §6` — FCS F1 consome credit-to-GDP (bubble warning).
- `docs/specs/cycles/monetary-msc.md §7` — MSC consulta spread via CRP overlay.

### 8.3 Overlays partilhados

- `crp.md` emite CRP daily → consumido em rating-spread + FCS F1.
- `rating-spread.md` emite notch spread bps → feed default-spread lookup in CRP.

### 8.4 Conventions

- `conventions/normalization.md` — z-score + clip.
- `conventions/composite-aggregation.md` — Policy 1 CCCS re-weight.
- `conventions/patterns.md` — HP filter cache + versioning per-table rating.
- `conventions/flags.md` — emitidos: `MS_MISSING`, `CCCS_REWEIGHTED`, `BIS_KEY_FAIL`, `CDS_SCRAPE_FAIL`, `RATING_STALE`, `COVERAGE_INSUFFICIENT`.

### 8.5 Architecture / ADRs

- `docs/ARCHITECTURE.md §L3 credit`.
- `docs/adr/ADR-0002` — nine-layer.
- `docs/adr/ADR-0003` — storage (credit tables quarterly frequency).

### 8.6 Governance / backlog

- `docs/governance/DATA.md` — scrape ethics.
- `docs/backlog/calibration-tasks.md` — `CAL-001`, `CAL-004`, `CAL-009`, `CAL-019`, `CAL-020`.
- `docs/backlog/phase2-items.md` — `P2-001` (QS), `P2-014` (FMP reactivation).
- `docs/data_sources/D0_audit_report.md` — TE ratings stale finding.
- `docs/data_sources/D1_coverage_matrix.csv` — rows 17-25 (CRP + rating-spread) + 45-48 (L1-L4).

---

*Última revisão: 2026-04-18 (Phase 0 Bloco D1 rewrite).*
