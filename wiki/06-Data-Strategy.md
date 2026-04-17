# 06 · Data Strategy

Como o SONAR recolhe, valida e armazena dados. Ver [docs/data_sources/](../docs/data_sources/) para os planos operacionais detalhados por módulo.

## Filosofia

### Compute, don't consume

Princípio central: SONAR **calcula** outputs localmente a partir de dados raw, não consume outputs agregados.

| ❌ Consume | ✅ Compute |
|---|---|
| Damodaran ERP mensal | ERP diária via DCF local |
| Bloomberg CRP | CRP local via CDS + vol ratio |
| Bundesbank fitted curve | NSS fit local (Bundesbank = cross-validation) |
| Shiller CAPE published | Parse ie_data.xls, compute localmente |

**Benefits**:
- Daily frequency (não constrained by source cadence)
- Methodology transparency
- No external subscription dependency for core
- Cross-validation continuous (detect regressions)

### Minimal external dependencies

Tier 1 MVP é **$0 adicional** — todas as fontes são gratuitas ou shared com planos anteriores.

### Provenance tracking

Todo data point tem metadata:
- Source connector
- Fetch timestamp
- Data as-of date
- Confidence score
- Methodology version
- Cross-validation status

## Tiers de fontes

### Tier 1 — MVP (free)

**Grandes agregadores**:
- **FRED** (Federal Reserve St. Louis) — 800k+ US series
- **ECB SDW** — Euro area statistics
- **BIS** — international settlements, credit gaps, CDS
- **Eurostat** — EU statistical office
- **OECD** — cross-country data
- **IMF WEO** — projections

**Central banks**:
- **Fed** (US) — yield curves, policy
- **ECB** — policy, statistics
- **BoE** (UK) — Anderson-Sleath curves (best in world)
- **BoJ** (Japan) — policy, JGB data
- **BdP** — Portuguese central bank
- **Bundesbank** — Svensson curves
- **BdF, BdE, BdI** — France, Spain, Italy

**National stats**:
- **INE** Portugal
- **BPStat** Portugal
- **IGCP** Portuguese sovereign debt
- **Destatis** Germany
- **ONS** UK
- Various by country

**Specialized**:
- **Shiller data** — Yale (CAPE historical)
- **Damodaran** — NYU Stern (ERP monthly, data tables)
- **World Government Bonds** — CDS scrape
- **multpl.com** — PE/PB/PS/yields
- **S&P DJI** — buyback indices

**Rating agencies**:
- S&P Global Ratings
- Moody's Investors Service (+ Annual Default Study)
- Fitch Ratings
- DBRS Morningstar

**Surveys**:
- Philadelphia Fed SPF
- ECB SPF
- BoE Decision Maker Panel
- University of Michigan
- BoJ Tankan

### Tier 2 — Enhanced (mid-term)

- **Trading Economics** (shared subscription) — broad coverage
- **FactSet Earnings Insight** — analyst estimates
- **Glassnode** — crypto on-chain (for FCS)
- **Alternative data** — news sentiment, satellite (if editorial justifies)

### Tier 3 — Professional (fund scenario)

- **Bloomberg Terminal** — $24k/ano
- **Refinitiv Eikon** — $22k/ano
- **S&P Global Markit** CDS — institutional
- **LSEG Datastream** — deep historical

## Pipeline diário

### Schedule (Lisbon time)

```
06:00 — Morning data refresh
  ├── Treasury.gov daily rates
  ├── Bundesbank Svensson
  ├── BoE yield curves
  ├── MoF Japan JGBs
  ├── ECB SDW (EA country yields)
  └── World Government Bonds CDS scrape

07:00 — Portugal-specific
  ├── IGCP Portuguese sovereign
  ├── BPStat updates
  └── INE updates (when available)

08:00 — Supplementary
  ├── FRED daily series (TIPS, breakevens, corporate)
  ├── Multpl.com scrape
  └── Equity indices close data (previous day)

09:00 — Sub-model computation
  ├── Yield curves NSS fitting (15+ countries)
  ├── Cross-validation vs BC-published
  ├── Bootstrap zero curves
  └── Derive forward curves

09:15 — ERP computation
  ├── DCF Damodaran method (primary)
  ├── Gordon, earnings yield, CAPE cross-checks
  └── Multi-market (US, EA, UK, JP)

09:45 — CRP computation
  ├── CDS primary (WGB data)
  ├── Sovereign spread fallback
  ├── Vol ratio (5Y rolling)
  └── 30+ countries

10:00 — Cycle classification
  ├── ECS, CCCS, MSC, FCS compute
  └── Overlays evaluation

10:15 — Expected inflation
  ├── Market breakevens (TIPS, ILGs, BTP€i, etc.)
  ├── Portugal synthesis (EA + differential)
  ├── 5y5y forward derivation
  └── Anchoring assessment

10:30 — Integration
  ├── Matriz 4-way classification
  ├── Four diagnostics computation
  ├── Cost of capital per country
  └── Alerts evaluation

11:00 — Outputs
  ├── Editorial briefing generation
  ├── Alert publishing
  ├── API cache refresh
  └── Dashboard data update
```

### Weekly (Friday end-of-week)

- PT-EA historical differential recompute (for expected inflation synthesis)
- Vol ratio recomputation (5Y rolling windows)
- Calibration drift checks

### Monthly (first week)

- Shiller ie_data.xls download
- Damodaran monthly ERP cross-validation
- Michigan 1Y/5Y expectations (via FRED)
- Methodology version review

### Quarterly

- S&P DJI buyback report
- Philadelphia Fed SPF
- ECB SPF
- BoJ Tankan
- Rating-to-spread table recalibration
- BIS quarterly data

### Event-driven (anytime)

- Rating agency actions (polled every 4h)
- Central bank policy decisions
- Major economic releases (NFP, CPI, GDP)

## Database architecture

### Schema v18 (current baseline)

~25 tables organizadas em:
- **Raw data audit** — connector outputs preserved
- **Cycle indicators** — per-cycle components
- **Sub-model outputs** — 5 sub-models
- **Cycle scores** — composite scores
- **Integration** — matriz 4-way, diagnostics
- **Meta** — runs, methodology versions, calibrations

### Indexing strategy

- `(country_code, date)` em todas as tabelas time-series
- `(agency, date)` em rating tables
- `(sonar_notch, calibration_date)` em rating-to-spread mapping

### Backup

- **Local**: daily SQLite snapshot to timestamped file
- **Cloud** (future): encrypted S3/B2 weekly push
- **Retention**: full history, no purge

## Data quality

### Validation layers

1. **Connector level** — response format, expected fields, sanity ranges
2. **Computation level** — numerical stability, NaN/inf checks
3. **Cross-validation** — vs BC-published (Fed GSW <10bps target)
4. **Historical comparison** — day-over-day change reasonableness
5. **Regime check** — value within plausible range given regime

### Flags

Every data point can have flags:
- `STALE` — data older than expected
- `OUT_OF_RANGE` — outside historical norms
- `CROSS_VALIDATION_FAIL` — divergence from reference
- `METHODOLOGY_FLAGGED` — known issue with computation
- `INCOMPLETE` — some inputs missing, partial output

Flags propagate up — if input has `STALE`, downstream computation is `CONFIDENCE_REDUCED`.

### Confidence scoring

Every output has `confidence` 0-1:
- 1.0: all inputs fresh, all validations pass
- 0.9: minor input issues, computation sound
- 0.8: one validation flag, output reasonable
- 0.7: material concerns, usable with caveats
- <0.7: quality degraded, investigation needed

## Portugal-aware specifics

Portugal não tem linker bond market, so specific synthesis required:

### Expected inflation

```
E[π_PT(tenor)] = EA_aggregate_BEI(tenor) + PT-EA_historical_differential
```

Differential computed from 5Y rolling HICP differences (INE vs Eurostat).

### Yield curve

Primary: IGCP
Secondary: ECB SDW EA sovereigns (PT slice)
Cross-check: MTS Portugal (if subscription)

### Rating

Four agencies consolidated:
- S&P: A-
- Moody's: A3
- Fitch: A-
- DBRS: A (low)
- SONAR median notch: 15 (A-)

### Real estate

BIS property gap + INE house prices + Golden Visa impact model.

---

*Next: [07 · Development Guide](07-Development-Guide)*
