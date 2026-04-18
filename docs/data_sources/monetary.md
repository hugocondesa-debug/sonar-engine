# SONAR v2 · Data sources — Monetary cycle (MSC)

> **Layer scope:** L3 indices `M1..M4` + L4 `cycles/monetary-msc` + L2 overlays `nss-curves`, `expected-inflation`.
> **Phase 0 Bloco D1** — rewrite baseado em `D1_coverage_matrix.csv` (2026-04-18) + D0 audit.
> **Status:** doc canónico. Substitui v1 monetary.md (786 linhas).

Documento alinhado com:
- `docs/specs/cycles/monetary-msc.md` (MSC = 0.30·M1 + 0.15·M2 + 0.25·M3 + 0.20·M4 + 0.10·CS).
- `docs/specs/indices/monetary/{M1..M4}.md`.
- `docs/specs/overlays/{nss-curves,expected-inflation}.md`.
- `docs/data_sources/country_tiers.yaml`.
- `docs/data_sources/D1_coverage_matrix.csv`.
- `docs/data_sources/D0_audit_report.md`.

---

## 1. Overview e hierarquia de fontes

### 1.1 Mandato do ciclo

O Monetary Stance Score (MSC) mede a orientação da política monetária (0 = ultra-tight, 100 = ultra-loose; Phase 1 usa convenção inversa via z-sign — ver spec §2).

| Index | Sub-index | Peso MSC | Mandato |
|-------|-----------|----------|---------|
| M1-effective-rates | ER | 0.30 | Policy rate + shadow rate (ZLB-aware) |
| M2-taylor-gaps | TG | 0.15 | Policy gap vs Taylor rule + HLW r* |
| M3-market-expectations | ME | 0.25 | Forward curves + breakeven inflation + SPF |
| M4-fci | FCI | 0.20 | Chicago Fed NFCI + ECB CISS + derived |
| CS (cross-cycle) | — | 0.10 | Communication signal from CB speeches (CCCS produces) |

**Lookback canónico:** 30Y (monetary moves slowly; secular regime changes pós-1990s Bretton Woods).

### 1.2 Hierarquia de fontes (5 níveis)

```
1. PRIMARY          FRED + Central banks nativos
   └── FRED é hub para most T1 series; ECB SDW / BoE / BoJ / ... directos
2. OVERRIDE T1      Native central bank quando FRED não mirror
   └── Bundesbank (Svensson curve), BoE (A-S curve), BoJ, SNB, Riksbank
3. SECONDARY breadth TE
   └── policy rates breadth T2-T3 via /country/{c}/indicators Cat=Money
4. SECONDARY EM     TCMB, BCB, RBI natives
   └── EM central banks onde TE parcial
5. TERTIARY         Academic scrapes
   └── Krippner (shadow rate), Wu-Xia (Atlanta Fed), HLW (NY Fed)
```

**Overlays críticos:**
- **NSS curves** é entry point para M3 (market expectations) + E2 (yield slope) + CRP (spread vs bench). Deve ser implementado primeiro no Phase 1 sequencing (ver spec §3 dependency graph).
- **Expected-inflation** é entry point para M2 (Taylor gap usa π_expected) + M3 (breakevens) + ERP overlay (real rates).

**Não usadas:**
- **BIS** — foco credit/FX (não monetary directly; BIS WS_LONG_CPP apenas consumer prices long-run, não breakeven/curves).
- **FMP** — `/api/stable/` 403. Sem path monetary (treasury endpoint testou 403).
- **TCMB** — bloqueado D1 (endpoint discovery failed). Turkey via TE.

### 1.3 Critério de escolha

```
If series in FRED_CATALOG and (country == US OR FRED mirror exists):
    primary = FRED
elif country in ECB_EA and series in ECB_SDW:
    primary = ECB_SDW
elif series is central-bank-specific (shadow rate, curve Svensson, etc.):
    primary = NATIVE CB (scrape or direct API)
elif country in TE_BREADTH:
    primary = TE
else:
    primary = GAP
```

---

## 2. Country tier coverage

### 2.1 Tabela

| Tier | Count | M1 policy rate | M1 shadow rate | M2 Taylor+HLW | M3 forwards | M3 breakeven | M4 FCI | MSC viável? |
|------|-------|----------------|----------------|----------------|-------------|--------------|--------|-------------|
| T1 | 16 | ✓ full | ~ 4 (US EA UK JP) | ~ 4 (US EA UK CA) | ✓ derived NSS | ~ 7 (linker countries) | ~ 2 (US EA) | Sim — full para US+EA |
| T2 | 30 | ✓ TE breadth | ✗ | ✗ | ~ partial (depends NSS) | ✗ | ✗ | Parcial — M1 only |
| T3 | 43 | ~ TE partial | ✗ | ✗ | ✗ | ✗ | ✗ | Não — M1 degraded |
| T4 | ~110 | ~ annual | ✗ | ✗ | ✗ | ✗ | ✗ | Não |

**Observação:** MSC é **fortemente US+EA-centric** por design — M2/M3/M4 requerem data académica e forward-curve markets que só existem em ~4-8 países. Specs documentam este viés como by-design (ver `cycles/monetary-msc.md §2`).

### 2.2 País-chave por sub-index

| Sub-index | T1 full support | T1 partial | T2+ |
|-----------|-----------------|------------|-----|
| M1 ER policy rate | Todos 16 | — | TE breadth 30+ |
| M1 ER shadow rate | US (Wu-Xia), EA+UK+JP (Krippner) | CA, AU, SE, CH implied (Krippner extended) | ✗ |
| M2 Taylor+HLW | US, EA, UK, CA | JP (r* derived; Taylor sensitivity) | ✗ |
| M3 breakeven | US, UK, FR, DE, IT, CA, AU (linkers) | JP experimental | ✗ |
| M3 5y5y forward | US, EA | — | ✗ (derivable se NSS cobre) |
| M4 FCI | US (NFCI), EA (CISS) | — | ✗ |

### 2.3 Degradação T2/T3

MSC para T2+ emite usando apenas M1 (policy rate normalized vs 10Y rolling). Outras sub-indices NULL → Policy 1 re-weight requer ≥3/4+CS → **fail**. Output: `MSC = NULL, flags = [M2_M3_M4_MISSING, T2_DEGRADED]`.

**Exceção** (spec §4): MSC simplified score para T2 disponível via `M1_only_mode`:
```
MSC_T2 = normalize(policy_rate, lookback_10y) × 100
confidence = 0.40  # low — only reflects level, não stance completo
```

---

## 3. Endpoints por fonte

### 3.1 FRED — monetary backbone

**Base + auth** igual a economic.md §3.2.

| Consumer | Series ID | Freq | Notes |
|----------|-----------|------|-------|
| M1 US policy rate | `DFEDTAR` (target range midpoint), `FEDFUNDS` (effective) | Daily | Fed Funds |
| M1 EA policy rate | `ECBMRRFR` (MRO rate) | Daily | Mirror ECB |
| M1 UK policy rate | `IR3TIB01GBM156N` (OECD mirror BoE) | Monthly | — |
| M1 JP policy rate | `INTDSRJPM193N` | Monthly | — |
| M1 US shadow rate (Wu-Xia) | — | — | **Não em FRED** — Atlanta Fed direct CSV |
| M1 EA/UK/JP shadow (Krippner) | — | — | **Não em FRED** — Krippner site scrape |
| M2 US r* HLW | — | — | **Não em FRED** — NY Fed CSV direct |
| M3 US breakeven | `T5YIE`, `T10YIE`, `T20YIE`, `T30YIE` | Daily | Daily breakeven |
| M3 US forward 5y5y | `T5YIFR` (5Y forward 5Y inflation) | Daily | |
| M3 US TIPS real yields | `DFII5`, `DFII10`, `DFII30` | Daily | For real curve |
| M3 SPF US | `EXPINF10YR` (10Y inflation expectation) | Quarterly | Philly Fed SPF |
| M4 US FCI | `NFCI` (Chicago Fed National FCI) | Weekly | Published Wed |
| M4 US FCI (alt) | `ANFCI` (Adjusted NFCI) | Weekly | Macro-adjusted |

**Nominal yield curve US** (for NSS input):
`DGS3MO`, `DGS6MO`, `DGS1`, `DGS2`, `DGS5`, `DGS7`, `DGS10`, `DGS20`, `DGS30` — 9 tenors daily.

### 3.2 ECB SDW — EA monetary

**Base:** `https://data-api.ecb.europa.eu/service/data`

| Consumer | Dataflow | Key example | Notes |
|----------|----------|-------------|-------|
| M1 EA policy | `FM` | `D.U2.EUR.4F.KR.MRR_FR.LEV` | MRO fixed rate |
| M1 EA deposit/lending facility | `FM` | `D.U2.EUR.4F.KR.DFR.LEV` / `MLFR.LEV` | — |
| M3 EA inflation swap | `FM` | `D.U2.EUR.RT.MM.EURIRS1Y.LEV` | — |
| M3 EA breakeven | `YC` | `B.U2.EUR.4F.G_N_A.SV_C_YM.BREAK.{T}Y` | Yield curve breakeven |
| M3 EA nominal yield curve | `YC` | `B.U2.EUR.4F.G_N_A.SV_C_YM.SR_{T}Y` | Svensson-fitted |
| M4 EA CISS | `CISS` | `D.U2.Z0Z.4F.EC.SOV_CISS.IDX` | Composite Indicator Systemic Stress |
| Expected-inflation SPF EA | `RFI` | — | Quarterly survey |

**Rate limit:** undocumented public service; 1 req/sec polite.

### 3.3 Central bank natives (T1 overrides)

| CB | Data endpoint | Consumer |
|----|--------------|----------|
| Bundesbank | `https://api.statistiken.bundesbank.de/rest/data/BBSIS/...` | DE yield curve (Svensson — pré-fitted, published daily) |
| BoE | `https://www.bankofengland.co.uk/boeapps/database/...` CSV downloads | UK A-S yield curve (Anderson-Sleath model) |
| BoJ | `https://www.stat-search.boj.or.jp/ssi/mtshtml/...` CSV | JP policy + yield data |
| SNB | `https://data.snb.ch/api/cube/...` | CH rates |
| Riksbank | `https://api.riksbank.se/api/swea/v1/...` | SE rates |
| MoF JP | `https://www.mof.go.jp/english/policy/jgbs/...` CSV | JGB yields |
| Atlanta Fed (Wu-Xia) | `https://www.atlantafed.org/cqer/research/wu-xia-shadow-federal-funds-rate` CSV | US shadow rate |
| NY Fed (HLW) | `https://www.newyorkfed.org/research/policy/rstar` CSV | US+EA+UK+CA r* |
| Krippner (RBNZ sponsored) | `https://www.ljkmfa.com/...` CSV | Shadow rates 4 economies |

**Status D1:** endpoints listed são discovery baseline. Phase 1 connector implementation validates (smoke + parse). Atlanta Fed + NY Fed CSV paths historically stable.

### 3.4 TCMB EVDS — Turkey

**Status D1: BLOCKED** (ver economic.md §3.7 detalhe).

**Target series monetary (quando recuperado):**
- M1 Turkey policy: `TP.AOFOPO03` (overnight lending O/N policy)
- M3 Turkey expectations: `TP.SURVEYS*` family

Turkey fallback: TE `/country/turkey/indicators` Cat=Money → policy rate OK; sub-indices M2-M4 não aplicáveis (T2 `M1_only_mode`).

### 3.5 TE — breadth para M1 policy rates

**Base + auth** igual a economic.md §3.1.

```
GET /country/{c}/indicators?c={KEY}&f=json
  → filter Category="Money" subfilter "Interest Rate"
```

**Coverage:** ~90 países com policy rate tracked (inclui quase todos os 160 ISO-3 countries).

### 3.6 Shadow rates (academic scrapes)

**Wu-Xia US shadow rate:**
- URL: `https://www.atlantafed.org/-/media/documents/cqer/researchcq/shadow_rate.xlsx`
- Frequency: monthly update
- Method: Wu-Xia 2016 (Journal of Money, Credit and Banking)
- Scope: US only

**Krippner shadow rate:**
- URL: `https://www.ljkmfa.com/wp-content/uploads/2024/XX/...pdf` (monthly PDF — parse issue)
- Alternative: RBNZ research page indirect
- Scope: US, EA, UK, JP (+ extensions to AU, CA, CH, NZ, SE)
- Method: Krippner 2012, 2015 (multi-factor shadow rate model)

**Cross-validation (spec M1 §4):** usar BOTH Wu-Xia e Krippner US como xval; emit warning se |WuXia - Krippner| > 50 bps.

### 3.7 HLW r* (academic)

**URL:** `https://www.newyorkfed.org/medialibrary/media/research/policy/rstar/Laubach_Williams_current_estimates.xlsx`
**Frequency:** quarterly update (published with Fed SEP lag ~60 dias)
**Coverage:** US (canonical) + EA + UK + CA (Holston-Laubach-Williams 2017 extension)
**Method:** HLW state-space Kalman filter.

**Cross-validation:** Lubik-Matthes (Richmond Fed) DSGE estimates são secondary. Phase 2 P2-012.

### 3.8 Expected-inflation alternatives

| Source | URL | Scope | Notes |
|--------|-----|-------|-------|
| FRED breakeven | `T5YIE`, `T10YIE`, `T20YIE`, `T30YIE` | US | Daily |
| FRED TIPS | `DFII*` | US | Real yield (compute BEI = nominal - TIPS) |
| ECB SDW breakeven | `YC` dataflow BREAK.{T}Y | EA | Daily |
| BoE | `IUDSBXXX` (implied infl RPI 5y) | UK | Daily |
| Bloomberg Tier 3 | — | UK/JP gaps | Out-of-scope Phase 1 |
| ECB SPF | ECB SDW `RFI` dataflow | EA survey | Quarterly |
| US Philly SPF | FRED `EXPINF10YR` | US survey | Quarterly |
| BoJ Tankan | BoJ CSV | JP survey | Quarterly |

**Hierarchy per spec `expected-inflation.md`** (pattern "hierarchy best-of"):
```
1. Breakeven (market-implied) — daily
2. Inflation swap — daily
3. SPF (survey) — quarterly
4. Realised CPI YoY (proxy) — monthly
```

---

## 4. Série catalog — por index / overlay

### 4.1 M1 — Effective rates

| Série | Pri | Ovr | Freq | Lat |
|-------|-----|-----|------|-----|
| `policy_rate` | FRED `FEDFUNDS` (US); ECB SDW `FM` (EA); native CB direct | TE breadth non-T1 | D | 1 |
| `shadow_rate_krippner_wu_xia` | Atlanta Fed XLS (US Wu-Xia); Krippner site (EA/UK/JP) | — | M | 30 |

**M1 derivation (spec §3):**
```
effective_rate = max(shadow_rate, policy_rate) if ZLB else policy_rate
zlb_flag = (policy_rate ≤ 0.50)
```

**Cross-check:** `|wu_xia_us - krippner_us| > 50bps → warning`.

### 4.2 M2 — Taylor gaps + r*

| Série | Pri | Ovr | Freq | Lat |
|-------|-----|-----|------|-----|
| `r_star_hlw` | NY Fed XLS (quarterly) | Lubik-Matthes (P2-012) | Q | 60 |
| `taylor_rule_prescribed` | Derived: `r* + π_expected + 0.5·(π - π_target) + 0.5·gdp_gap` | — | Q | derived |
| `taylor_gap_pp` | `policy_rate - taylor_rule_prescribed` | — | Q | derived |

**Inputs needed:**
- `r*` → HLW
- `π_expected` → expected-inflation overlay (SPF preferível)
- `π_target` → 2.0% Fed/ECB; spec M2 §5 documenta per-country overrides
- `gdp_gap` → derived from E1 + OECD output gap (FRED `NROUST` for US natural rate)

### 4.3 M3 — Market expectations

| Série | Pri | Ovr | Freq | Lat |
|-------|-----|-----|------|-----|
| `five_year_forward_breakeven` | FRED `T5YIFR` (US); derived from NSS (EA) | — | D | 1 |
| `spf_inflation_expectation` | FRED `EXPINF10YR` (US); ECB SPF (EA) | — | Q | 45 |

**M3 composite** pondera forwards (weight=0.60) + SPF (0.40). Ver spec M3 §4.

### 4.4 M4 — Financial Conditions Indices

| Série | Pri | Ovr | Freq | Lat |
|-------|-----|-----|------|-----|
| `chicago_fed_nfci` | FRED `NFCI` | — | W | 5 |
| `ecb_ciss` | ECB SDW CISS dataflow | — | D | 1 |

**M4 country-specific:** Phase 1 emite FCI apenas para US (NFCI) + EA (CISS). Para T1 ex-US/EA spec §5 recomenda building domestic FCI via PCA of (policy_rate_spread, credit_spread, equity_vol, sovereign_vol). Phase 2 backlog P2-006.

### 4.5 Overlay L2 — NSS curves

| Série | Pri | Ovr | Freq | Lat |
|-------|-----|-----|------|-----|
| `sovereign_yield_{tenor}` | TE `/country/{c}/indicators` Cat=Money | FRED `DGS*` (US); Bundesbank Svensson (DE); BoE A-S (UK); MoF (JP) | D | 1 |
| `tips_real_yield_{tenor}` | FRED `DFII5`/`DFII10`/`DFII30` (US) | ECB SDW (EA linkers); BoE (UK ILG) | D | 1 |

**Tenors canónicos:** 3M, 6M, 1Y, 2Y, 5Y, 7Y, 10Y, 20Y, 30Y (9 tenors).

**NSS fitting** (spec §3):
- Requires ≥6 tenors per country per day.
- Nelson-Siegel-Svensson 6-parameter model: β0, β1, β2, β3, τ1, τ2.
- Optimizer: scipy.optimize.least_squares with bounded τ ∈ [0.5, 10].
- Output: fitted curve function → consumable point estimates em any tenor.

**T1 override strategy** (per CSV row 2-10):
- US: FRED `DGS*` native daily (9 tenors).
- DE: Bundesbank Svensson pré-fitted (preferível — curve model-consistent).
- UK: BoE Anderson-Sleath pré-fitted.
- JP: MoF Jp Government Bond yields + fit local NSS.
- Other T1 (EA members, CA, AU, ...): TE + fit local.

**T4 degraded path:** se país tem < 6 tenores → NSS não fitable → emit spot observations com flag `NSS_SPARSE`.

### 4.6 Overlay L2 — Expected-inflation

| Série | Pri | Ovr | Freq | Lat |
|-------|-----|-----|------|-----|
| `breakeven_inflation_bei` | FRED `T{T}YIE` (US); ECB SDW (EA); BoE (UK) | — | D | 1 |
| `inflation_swap_rate` | ECB SDW `FM` swap dataflow (EA); partial FRED `FII*` (US) | — | D | 1 |
| `hicp_yoy` | Eurostat `prc_hicp_manr` (EA); ECB SDW | TE breadth T3-T4 | M | 30 |
| `cpi_yoy` | FRED `CPIAUCSL` (US); TE breadth; TCMB `TP.FG.J0` (TR) | — | M | 15 |
| `spf_inflation_expectation` | FRED `EXPINF10YR` (US); ECB SPF (EA) | BoJ Tankan (JP) | Q | 45 |

**Expected-inflation hierarchy** (spec patterns "hierarchy best-of"):
```
per (country, tenor):
    if country has liquid linker AND breakeven available:
        primary = breakeven
    elif country has inflation swap market:
        primary = swap
    elif country has SPF:
        primary = SPF
    else:
        primary = CPI YoY trailing (proxy)
```

**HICP vs CPI:** EA countries usam HICP (harmonised); non-EU usam CPI nacional. Emit source flag para downstream consumers (rating-spread, ERP real-rate conversion).

---

## 5. Fallback hierarchy

### 5.1 Árvore de decisão MSC

```
Para cada (series, country):
    1. IF series in FRED AND (country == US OR mirror):
         → FRED
    2. ELIF country in ECB_EA AND series in ECB_SDW:
         → ECB SDW
    3. ELIF series is academic (shadow_rate, r*):
         → scrape academic (Atlanta Fed, NY Fed, Krippner)
    4. ELIF country in TE_BREADTH AND series = policy_rate:
         → TE (M1 only)
    5. ELSE:
         → flag + degraded / M1_only_mode
```

### 5.2 Policy 1 re-weight MSC

MSC tem 4 sub-indices + CS (cross-cycle). Re-weight quando 1 sub-index missing:

```
valid = {M1, M3, M4, CS}  # example: M2 missing
weights_valid = {0.30, 0.25, 0.20, 0.10}  # total 0.85
re-weighted = {M1: 0.30/0.85, M3: 0.25/0.85, M4: 0.20/0.85, CS: 0.10/0.85}
MSC = sum
confidence = min(0.75, base)
```

**M1_only_mode** para T2+ é special-case: apenas M1 disponível; confidence = 0.40; flag `M1_ONLY_MODE` emitted.

### 5.3 Override conditions

- **FRED primary US** always.
- **ECB SDW primary EA** always (não TE fallback — ECB SDW é authoritative).
- **Bundesbank override DE yield curve** — Svensson model-consistent (preferir sobre TE spot points).
- **BoE override UK yield curve** — A-S model idem.
- **Shadow rate cross-check** US: Wu-Xia + Krippner both required → discrepancy warning.

---

## 6. Known gaps e backlog

### 6.1 Gaps críticos (BLOCKING)

| Gap | Impacto | Mitigação | Backlog |
|-----|---------|-----------|---------|
| Shadow rate coverage | Apenas US+EA+UK+JP — resto T1 sem shadow | ZLB flag-only sem shadow numeric | `P2-004` |
| HLW r* country coverage | 4 países only | Lubik-Matthes DSGE alternative | `P2-012` |
| TCMB endpoint | Turkey policy via TE só | `M1_only_mode` | `CAL-018` |
| Krippner parse (PDF) | Site format muda periodicamente | Manual monitoring; alert on parse fail | — |
| MSC non-US/EA | Design-limited (spec §2 acknowledged) | By-design; expandir em Phase 4 | `CAL-015` |

### 6.2 Gaps de qualidade (CORE)

- **Wu-Xia monthly vs daily policy rate:** shadow rate monthly; effective rate daily. Spec §3 resolves mixing: effective_rate emitted daily usando last shadow rate até release next.
- **π_target cross-country:** spec §5 assume 2% inflation target. Paises com different targets (Turkey historically 5-12%, EMs 3-4%) precisa per-country override.
- **Breakeven inflation risk premium:** BEI contains IRP — not pure expected inflation. Spec `expected-inflation.md §6` documenta; Phase 2 decomposition P2-005.
- **NSS convergence failures:** para países com ≤6 tenores NSS fails → fallback to linear interp. Quality degradation silent — need explicit flag.

### 6.3 Out-of-scope Phase 0 / Phase 1

- **Communication signal (CS)** — text NLP on CB speeches. Phase 2+ `P2-008`. Phase 1 uses `CS = 50` neutral stub.
- **Balance sheet dynamics** — QE/QT tracking via weekly central bank balance sheet. Phase 2 `P2-006`.
- **Yield curve fitting sub-components** — Dai-Singleton, multi-factor affine. Out-of-scope.
- **Real rate decomposition** — term premia (Kim-Wright, ACM). Out-of-scope.

### 6.4 Calibration tasks

- `CAL-005` — MSC weights (0.30/0.15/0.25/0.20/0.10) empirical validation.
- `CAL-007` — shadow rate cross-validation (Wu-Xia vs Krippner).
- `CAL-015` — MSC extension to T2 EMs (design decision Phase 4).
- `CAL-018` — TCMB endpoint recovery.

---

## 7. Licensing status

| Fonte | Licença | Uso |
|-------|---------|-----|
| FRED | Public domain | Sem restrições |
| ECB SDW | ECB re-use | Attribution |
| Bundesbank | CC-BY-4.0 | Attribution |
| BoE | Open Government Licence | Attribution |
| BoJ | Free research use | Attribution |
| MoF JP | Government data — free | — |
| NY Fed (HLW) | Public domain | — |
| Atlanta Fed (Wu-Xia) | Public domain | — |
| Krippner (ljkmfa.com) | Free research use | Attribution "Krippner 2015" |
| TE | Commercial (tier pending) | Internal-only |
| TCMB EVDS | Academic free | — |

---

## 8. Cross-refs

### 8.1 Specs consumer

- `docs/specs/indices/monetary/M1-effective-rates.md`.
- `docs/specs/indices/monetary/M2-taylor-gaps.md`.
- `docs/specs/indices/monetary/M3-market-expectations.md`.
- `docs/specs/indices/monetary/M4-fci.md`.
- `docs/specs/cycles/monetary-msc.md`.
- `docs/specs/overlays/nss-curves.md`.
- `docs/specs/overlays/expected-inflation.md`.

### 8.2 Outros cycles

- `cycles/economic-ecs.md §5 E2` — consome yield slope derived from NSS.
- `cycles/financial-fcs.md §6` — F3 consome TIPS real yields via expected-inflation overlay.
- `cycles/credit-cccs.md §6` — CCCS lê CS cross-cycle from MSC (Phase 2 bidirectional).

### 8.3 Overlays partilhados

- `nss-curves` emits yield curve → downstream: E2 (slope), F3 (real yields), CRP (spread).
- `expected-inflation` emits π_e → downstream: M2 (Taylor input), M3 (breakeven raw), ERP daily (real rate).

### 8.4 Conventions

- `conventions/normalization.md` — z-score lookback 30Y.
- `conventions/composite-aggregation.md` — Policy 1 + M1_only_mode special-case.
- `conventions/patterns.md` — NSS fit cache; hierarchy best-of for expected-inflation.
- `conventions/flags.md` — emitidos: `ZLB_ACTIVE`, `SHADOW_RATE_MISSING`, `NSS_SPARSE`, `WU_XIA_KRIPPNER_DIVERGE`, `M1_ONLY_MODE`, `T2_DEGRADED`, `BEI_RISK_PREMIUM_UNADJUSTED`.

### 8.5 Architecture / ADRs

- `docs/ARCHITECTURE.md §L3 monetary`.
- `docs/adr/ADR-0002` — nine-layer.

### 8.6 Governance / backlog

- `docs/backlog/calibration-tasks.md` — `CAL-005`, `CAL-007`, `CAL-015`, `CAL-018`.
- `docs/backlog/phase2-items.md` — `P2-004` (shadow rate expand), `P2-005` (BEI decomp), `P2-006` (FCI country-domestic), `P2-008` (CS NLP), `P2-012` (Lubik-Matthes).
- `docs/data_sources/D0_audit_report.md` — TCMB finding.
- `docs/data_sources/D1_coverage_matrix.csv` — rows 2-11 (NSS), 26-30 (expected-inflation), 49-54 (M1-M4).

---

*Última revisão: 2026-04-18 (Phase 0 Bloco D1 rewrite).*
