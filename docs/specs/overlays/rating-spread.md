# Rating-to-Spread Mapping — Spec

> Layer L2 · overlay · slug: `rating-spread` · methodology_version: `RATING_SPREAD_v0.2` (consolidated); `RATING_AGENCY_v0.1` (per-agency raw); `RATING_CALIBRATION_v0.1` (notch→spread table).
> Last review: 2026-04-19 (Phase 0 Bloco E1)
> v0.2 rationale (breaking): remove `te_ratings` fallback — rejected em D0 audit (latest observation 2022-09; 4Y stale). Add `damodaran_annual_historical` como pre-2023 baseline backfill + agency scrape connectors forward per D0+D2 findings. Per `conventions/methodology-versions.md` — MINOR bump porque schema inalterado (fallback source swap).

## 1. Purpose

Consolidar ratings sovereign das 4 agências (S&P, Moody's, Fitch, DBRS) numa SONAR common scale `0-21` (notches fracionários com modifiers de outlook/watch) e mapear para `default_spread_bps` via calibração empírica (Moody's Annual Default Study + ICE BofA). Fonte de verdade para `overlays/crp` (gap-filling quando CDS indisponível) e input directo para `integration/cost-of-capital`.

## 2. Inputs

### Per-agency raw ratings

| Name | Type | Constraints | Source |
|---|---|---|---|
| `country_code` | `str` | ISO 3166-1 α-2 upper | config |
| `date` | `date` | business day (Europe/Lisbon) | param |
| `agency` | `Literal` | `"SP"` \| `"MOODYS"` \| `"FITCH"` \| `"DBRS"` | connector |
| `rating_raw` | `str` | agency-native token (`"AA+"`, `"Aa1"`, `"AA (high)"`) | connector |
| `rating_type` | `Literal` | `"FC"` (foreign) \| `"LC"` (local currency) | connector |
| `outlook` | `Literal` | `"positive"` \| `"stable"` \| `"negative"` \| `"developing"` | connector |
| `watch` | `Literal \| None` | `"watch_positive"` \| `"watch_negative"` \| `"watch_developing"` \| `None` | connector |
| `action_date` | `date` | last rating action date | connector |

**Primary connectors** (event-driven agency scrape polled every 4h in `pipelines/daily`; Damodaran annual pre-2023 baseline):

| Agency | Primary (forward) | Historical backfill (pre-2023) | Fallback |
|---|---|---|---|
| S&P Global Ratings | `connectors/sp_ratings` | `connectors/damodaran_annual_historical` | — (TE rejected D0 — 4Y stale) |
| Moody's Investors Service | `connectors/moodys_ratings` | `connectors/damodaran_annual_historical` | — (TE rejected D0) |
| Fitch Ratings | `connectors/fitch_ratings` | `connectors/damodaran_annual_historical` | — (TE rejected D0) |
| DBRS Morningstar | `connectors/dbrs_ratings` | `connectors/damodaran_annual_historical` | `ecb_ecaf` (EA collateral list) |

### Calibration inputs (notch → spread)

| Name | Type | Constraints | Source |
|---|---|---|---|
| `moodys_default_study_json` | `dict` | cumulative PD por Moody's grade, 1983-2024 sov + 1920-2024 corp | `connectors/moodys_default_study` (annual PDF) |
| `ice_bofa_spread_bps` | `dict[grade,int]` | 5Y rolling median OAS (AA, A, BBB, BB, B, CCC) | `connectors/fred` (`BAMLC0A0CM`, `BAMLH0A0HYM2`, `BAMLEMCBPIOAS`) |
| `damodaran_historical_ratings_xlsx` | `dict[country,year → rating]` | Damodaran `histimpl.xlsx` annual sovereign ratings since 1994 (~170 countries) | `connectors/damodaran_annual_historical` |
| `recovery_assumption` | `float` | default 0.40 (Moody's sov baseline) | config |

### Parameters (config)

- Outlook modifiers: `positive=+0.25`, `negative=−0.25`, `stable/developing=0`.
- Watch modifiers: `watch_positive=+0.50`, `watch_negative=−0.50`, `watch_developing/None=0`.
- `consolidation_rule = "median"` (ties → floor, conservative); `min_agencies_for_consolidation = 2`.
- `calibration_window_years = 5` (rolling median ICE BofA); `calibration_refresh_days = 90` (quarterly).
- `cds_divergence_threshold_pct = 50` (triggers `RATING_CDS_DIVERGE`).

### Preconditions

Invariantes antes da invocação do consolidator:

- Para um `(country, date, rating_type)`, ≥ `min_agencies_for_consolidation` rows em `ratings_agency_raw` com `action_date ≤ date`.
- `rating_raw` token pertence ao domain da agência (lookup contra reference §13.2-13.3); senão `InvalidInputError`.
- FC e LC são persistidos separadamente; consolidator opera por `rating_type`.
- `ratings_spread_calibration` contém row com `calibration_date ≤ date` e `staleness_days ≤ calibration_refresh_days`; senão flag `CALIBRATION_STALE`.
- `methodology_version` armazenada bate com runtime (senão `VersionMismatchError`).
- Connector `fetched_at` ≤ 7 dias face a `date` (ratings movem-se lentamente).

## 3. Outputs

Três classes de output, versionadas independentemente. `ratings_agency_raw` + `ratings_consolidated` partilham `rating_id` UUID para mesmo `(country, date, rating_type)`.

| Output | Storage | `methodology_version` |
|---|---|---|
| Per-agency raw notch | `ratings_agency_raw` | `RATING_AGENCY_v0.1` |
| Consolidated country notch | `ratings_consolidated` | `RATING_SPREAD_v0.2` |
| Calibrated notch → spread table | `ratings_spread_calibration` | `RATING_CALIBRATION_v0.1` |

**Downstream consumption contract** (shape target for `overlays/crp`):

- Deterministic `(country, date, rating_type) → consolidated_sonar_notch` via `ratings_consolidated`.
- Deterministic `(sonar_notch_int, calibration_date) → default_spread_bps` via `ratings_spread_calibration` (global, não per-country; regional adjustments aplicadas consumer-side).

**Canonical JSON (per-country consolidated)**:

```json
{"rating_id":"8f3c...","country":"PT","date":"2026-04-17","rating_type":"FC",
 "agencies":{"SP":15,"MOODYS":15,"FITCH":15,"DBRS":15},"consolidated_sonar_notch":15.0,
 "outlook_composite":"stable","watch_composite":null,"default_spread_bps":90,"confidence":0.85,"flags":""}
```

## 4. Algorithm

> **Units**: per-agency raw armazena `sonar_notch_*` como `REAL` (permite modifiers fracionários ±0.25 / ±0.50); calibration table armazena `default_spread_bps` como `INTEGER`; spread ranges também `INTEGER`. Decimal storage para fracções, bps como int. Full rules em [`conventions/units.md`](../conventions/units.md).

### Formulas

**Agency → SONAR base notch** (discrete lookup, cf. §13.3 da reference):

```text
sonar_notch_base = LOOKUP_TABLE[agency][rating_raw]   # int ∈ [0, 21]
```

**Outlook + watch adjustment** (additive, fracionário):

```text
notch_adjusted = sonar_notch_base + outlook_mod(outlook) + watch_mod(watch)
# outlook_mod: positive=+0.25, negative=−0.25, stable/developing=0
# watch_mod:   watch_positive=+0.50, watch_negative=−0.50, else=0
```

Modifier weights (`±0.25`, `±0.50`) são **placeholders — recalibrate after 18m of production data** contra ex-post rating action transitions.

**Consolidation**: `consolidated_sonar_notch = median(notch_adjusted_i)`; ties → `floor(median)` (conservative). Result é `REAL` (fracionário — ex: 20.5 para US AA+/Aaa split).

**Notch → spread calibration** (global, refresh quarterly):

```text
# Empirical (primary — what the table stores)
default_spread_bps = median(ICE_BofA_OAS[grade(notch_int)] over 5Y rolling)
range_low_bps, range_high_bps = p25, p75

# Actuarial floor (audit / sanity only, stored em moodys_pd_5y_pct)
actuarial_spread_bps = PD_5Y_annualized * (1 - recovery_assumption) * 10_000
```

`grade(notch_int)` mapeia integer notch → ICE BofA bucket (AAA/AA/A/BBB/BB/B/CCC). Fractional notches são interpolated linearly consumer-side.

### Pipeline per rating event (event-driven, 4h poll)

0. **Source selection** (per v0.2): if `date < 2023-01-01` use `connectors/damodaran_annual_historical` como backfill source (annual granularity — rating persistido para dates intra-year até próxima annual release); else use agency scrape connectors forward (event-driven 4h poll).
1. Poll each agency connector; diff against last stored `action_date` per `(country, agency, rating_type)`.
2. New/changed action → validate `rating_raw` domain; map → `sonar_notch_base` via LOOKUP_TABLE (§13.3 reference).
3. Apply outlook + watch modifiers → `notch_adjusted`.
4. Persist row to `ratings_agency_raw` com `rating_id = uuid4()`, trigger consolidator if ≥ `min_agencies_for_consolidation` rows exist.

### Pipeline per consolidation (daily EOD, all countries)

1. Gather latest `ratings_agency_raw` per `(country, agency, rating_type)` com `action_date ≤ date`.
2. `agencies_available < 2` → persist partial com `RATING_SINGLE_AGENCY`, cap confidence `0.60`.
3. `consolidated_sonar_notch = median(notch_adjusted_i)`; split (range ≥ 3) → `RATING_SPLIT`.
4. `outlook_composite` = majority vote (tie → `"stable"`); `watch_composite` = any agency on watch.
5. Lookup `default_spread_bps` em `ratings_spread_calibration` via `notch_int = int(round(consolidated_sonar_notch))`; expor `notch_fractional` para interp consumer-side.
6. Cross-validate vs CDS se `overlays/crp` tem row — `|rating_implied − cds_5y| / cds_5y > 0.50` → `RATING_CDS_DIVERGE`.
7. Compute `confidence` via §6; persist `ratings_consolidated` atomically.

### Pipeline per calibration refresh (quarterly)

1. Fetch Moody's Annual Default Study (if new release) + ICE BofA 5Y rolling stats via FRED.
2. Para cada integer notch `0..21`: map notch → ICE BofA bucket (AAA/AA/A/BBB/BB/B/CCC); `default_spread_bps = median(5Y_rolling_OAS)`, `range_low/high_bps = p25/p75`.
3. Write 22 rows to `ratings_spread_calibration` with new `calibration_date`; older calibrations retained para reproducibilidade.

Anchor values (April 2026 snapshot from §15.1 reference — **placeholders; recalibrate every 3m**): notch 21 → 10 bps, 18 → 35, 15 → 90, 12 → 245, 9 → 600, 6 → 1325, 3 → 3250, 0 → N/A.

## 5. Dependencies

| Package | Min version | Use |
|---|---|---|
| `numpy` | 1.26 | median, percentile |
| `pandas` | 2.1 | rolling windows, i/o |
| `pdfplumber` | 0.11 | Moody's Annual Default Study PDF parse |
| `sqlalchemy` | 2.0 | persistence |
| `pydantic` | 2.6 | rating token validation |

No network inside the algorithm — connectors pre-fetch agency releases and calibration inputs.

## 6. Edge cases

Flags → [`conventions/flags.md`](../conventions/flags.md). Exceptions → [`conventions/exceptions.md`](../conventions/exceptions.md). Confidence impact aditivo, clamp `[0,1]`, conforme `flags.md` § "Convenção de propagação".

| Trigger | Handling | Confidence |
|---|---|---|
| `rating_raw` não reconhecido | raise `InvalidInputError` | n/a |
| `agencies_available == 0` | raise `InsufficientDataError`; no persist | n/a |
| `agencies_available < 2` | persist partial; `RATING_SINGLE_AGENCY` | cap 0.60 |
| Split rating (range ≥ 3 notches) | floor(median); `RATING_SPLIT` | −0.10 |
| `action_date > 180d` em alguma agência | emit; `STALE` | −0.20 |
| Outlook `"developing"` | sem modifier; `RATING_OUTLOOK_UNCERTAIN` | −0.05 |
| Watch `"watch_developing"` | sem modifier; `RATING_WATCH_UNCERTAIN` | −0.05 |
| Calibration `staleness_days > 90` ou Moody's study > 12m | emit; `CALIBRATION_STALE` | −0.15 |
| `|rating_implied − cds_5y| / cds_5y > 0.50` | emit; `RATING_CDS_DIVERGE` | −0.10 |
| Rating `D` (notch 0) | `default_spread_bps = NULL`; `RATING_DEFAULT` | cap 0.40 |
| Country tier 4 (TR/AR/VE hyperinflation) | wider ranges; `EM_COVERAGE` | cap 0.70 |
| Stored `methodology_version` ≠ runtime | raise `VersionMismatchError` | n/a |
| Calibration row missing para `notch_int` | raise `CalibrationError`; no persist | n/a |
| Connector empty (site down) | `DataUnavailableError` → fallback `damodaran_annual_historical` (if `date < 2024-01`) else emit `OVERLAY_MISS` downstream | `OVERLAY_MISS` downstream |

## 7. Test fixtures

Stored in `tests/fixtures/rating-spread/`. Each fixture pair `input_<id>.json` + `expected_<id>.json`.

| Fixture id | Input | Expected | Tolerance |
|---|---|---|---|
| `pt_2026_04_17` | S&P A-, Moody's A3, Fitch A-, DBRS A(low); stable | `consolidated=15.0`, `spread_bps≈90`, `conf≥0.85` | ±10 bps |
| `us_2026_04_17_split` | S&P AA+, Moody's Aaa, Fitch AA+, DBRS AAA | `consolidated=20.5`, `spread_bps≈20` | ±5 bps |
| `it_2026_04_17_watch` | Moody's Baa3 neg, Fitch BBB watch_neg, S&P/DBRS BBB stable | `consolidated=12.625`; watch_composite set | — |
| `ar_2026_04_17_distressed` | S&P CCC, Moody's Ca, Fitch CCC, DBRS CCC | `consolidated=3.0` (tie→floor); `EM_COVERAGE` | ±500 bps |
| `gh_single_agency` | Only Fitch (CCC+) | `RATING_SINGLE_AGENCY`; conf ≤ 0.60 | — |
| `unknown_agency_token` | S&P "AA++" | raises `InvalidInputError` | n/a |
| `cds_divergence_it` | Rating 245 bps vs CDS 68 bps | `RATING_CDS_DIVERGE` | — |
| `calibration_stale_100d` | Calibration 100d old | `CALIBRATION_STALE` | — |
| `calibration_refresh_2026_q2` | Full ICE BofA + Moody's refresh | 22 rows; notch 15 ≈ 90 bps | ±15 bps |
| `lc_vs_fc_br` | BR FC=BB, LC=BBB- | Two rows (FC=10, LC=12), distinct `rating_id` | — |

## 8. Storage schema

Três tabelas. `ratings_agency_raw` + `ratings_consolidated` partilham `rating_id` UUID (correlação de siblings para mesmo `(country, date, rating_type)`). `ratings_spread_calibration` é global (sem `country_code`), versionada por `calibration_date`.

```sql
CREATE TABLE ratings_agency_raw (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    rating_id             TEXT    NOT NULL,               -- uuid4, shared w/ consolidated
    country_code          TEXT    NOT NULL,
    date                  DATE    NOT NULL,
    agency                TEXT    NOT NULL CHECK (agency IN ('SP','MOODYS','FITCH','DBRS')),
    rating_type           TEXT    NOT NULL CHECK (rating_type IN ('FC','LC')),
    rating_raw            TEXT    NOT NULL,
    sonar_notch_base      INTEGER NOT NULL CHECK (sonar_notch_base BETWEEN 0 AND 21),
    outlook               TEXT    NOT NULL CHECK (outlook IN ('positive','stable','negative','developing')),
    watch                 TEXT    CHECK (watch IN ('watch_positive','watch_negative','watch_developing') OR watch IS NULL),
    notch_adjusted        REAL    NOT NULL CHECK (notch_adjusted BETWEEN -1.0 AND 22.0),
    action_date           DATE    NOT NULL,
    source_connector      TEXT    NOT NULL,
    methodology_version   TEXT    NOT NULL,               -- 'RATING_AGENCY_v0.1'
    confidence            REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags                 TEXT,
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (country_code, date, agency, rating_type, methodology_version)
);
CREATE INDEX idx_rar_cdt ON ratings_agency_raw (country_code, date, rating_type);
CREATE INDEX idx_rar_rid ON ratings_agency_raw (rating_id);

CREATE TABLE ratings_consolidated (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    rating_id                TEXT    NOT NULL UNIQUE,
    country_code             TEXT    NOT NULL,
    date                     DATE    NOT NULL,
    rating_type              TEXT    NOT NULL CHECK (rating_type IN ('FC','LC')),
    consolidated_sonar_notch REAL    NOT NULL CHECK (consolidated_sonar_notch BETWEEN -1.0 AND 22.0),
    notch_fractional         REAL    NOT NULL,
    agencies_count           INTEGER NOT NULL CHECK (agencies_count BETWEEN 0 AND 4),
    agencies_json            TEXT    NOT NULL,            -- {"SP":15,"MOODYS":15,...}
    outlook_composite        TEXT    NOT NULL,
    watch_composite          TEXT,
    default_spread_bps       INTEGER,                     -- NULL if notch=0
    calibration_date         DATE,
    rating_cds_deviation_pct REAL,
    methodology_version      TEXT    NOT NULL,            -- 'RATING_SPREAD_v0.2'
    confidence               REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags                    TEXT,
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (country_code, date, rating_type, methodology_version)
);
CREATE INDEX idx_rc_cdt ON ratings_consolidated (country_code, date, rating_type);

CREATE TABLE ratings_spread_calibration (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    calibration_date      DATE    NOT NULL,
    sonar_notch_int       INTEGER NOT NULL CHECK (sonar_notch_int BETWEEN 0 AND 21),
    rating_equivalent     TEXT    NOT NULL,
    default_spread_bps    INTEGER,                        -- NULL for notch=0
    range_low_bps         INTEGER,                        -- p25
    range_high_bps        INTEGER,                        -- p75
    moodys_pd_5y_pct      REAL,                           -- audit / actuarial sanity
    calibration_source    TEXT    NOT NULL,
    methodology_version   TEXT    NOT NULL,               -- 'RATING_CALIBRATION_v0.1'
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (calibration_date, sonar_notch_int, methodology_version)
);
CREATE INDEX idx_rsc_notch ON ratings_spread_calibration (sonar_notch_int, calibration_date);
```

## 9. Consumers

| Consumer | Layer | Uses |
|---|---|---|
| `overlays/crp` | L2 | Fallback quando CDS não disponível; lookup `(country, date) → default_spread_bps` |
| `integration/cost-of-capital` | L6 | Compõe `cost_of_debt_country` quando rating é proxy primário |
| `indices/credit/L5-sovereign-risk` | L3 | Consolidated notch como sinal sovereign stress (delta vs history) |
| `cycles/credit-cccs` | L4 | Rating deltas (action count 12m) como sinal de regime shift |
| `integration/diagnostics/rating-vs-market` | L6 | `rating_cds_deviation_pct` para editorial divergence angle |
| `outputs/editorial` | L7 | Rating actions (upgrade/downgrade) como news triggers |

## 10. Reference

- **Methodology**: [`docs/reference/overlays/rating-spread.md`](../../reference/overlays/rating-spread.md) — Manual dos Sub-Modelos Parte V, caps 13-15.
- **Data sources**: [`docs/data_sources/credit.md`](../../data_sources/credit.md) §§ 1.3 (FRED ICE BofA), 2.1 (OAS por rating), §3.6 scrape agency + Damodaran annual historical; [`data_sources/D0_audit_report.md`](../../data_sources/D0_audit_report.md) (TE ratings rejected — 4Y stale finding); [`data_sources/D2_empirical_validation.md`](../../data_sources/D2_empirical_validation.md) §2.4 confirming TE path 404.
- **Architecture**: [`specs/conventions/patterns.md`](../conventions/patterns.md) §Pattern 2 (rating-spread é fallback path em CRP hierarchy); §Pattern 3 (Versioning per-table — agency/consolidated/calibration independent bumps).
- **Licensing**: [`governance/LICENSING.md`](../../governance/LICENSING.md) §2 row 17 agency press releases (factual cite + paraphrase rationale per Override 3); §3 attribution strings per agency; §4 use case matrix — historical rating database audit-internal only, not distributable.
- **Proxies**: [`specs/conventions/proxies.md`](../conventions/proxies.md) — rating-spread é input para CRP rating-implied proxy entry.
- **Papers**:
  - Moody's Investors Service (2024), "Annual Default Study: Corporate Default and Recovery Rates, 1920-2023" + "Sovereign Default and Recovery Rates, 1983-2023".
  - Elton et al. (2001), "Explaining the Rate Spread on Corporate Bonds", *J. Finance* 56(1).
  - Huang & Huang (2012), "How Much of the Corporate-Treasury Yield Spread Is Due to Credit Risk?", *RFS* 2(2).
  - Damodaran A. (2024), "Country Risk: Determinants, Measures and Implications" — annual cross-check.
- **Cross-validation**: CDS 5Y observed (primary deviation check); ICE BofA sovereign (EMBI+ stratified); Damodaran country-risk table.

## 11. Non-requirements

Scope boundaries. O que este overlay **não** faz:

- Does not emit CDS-based spreads nor bond spreads vs benchmark (Bund/UST) — ambos em `overlays/crp` (CDS é Level-1, rating é Level-4 fallback no `country_default_spread_hierarchy`).
- Does not predict rating changes — é puramente reactivo, event-driven. Forecast em `integration/diagnostics/rating-pressure`.
- Does not apply regional adjustments (EA collateral discount, oil-exporter, hyperinflation) — consumer-side em `overlays/crp` e `integration/cost-of-capital`.
- Does not interpolate dates sem rating action — rating persiste até próxima ação da agência; gap-filling em `pipelines/daily-ratings`.
- Does not reconcile FC vs LC — rows distintas; consumer escolhe conforme contexto.
- Does not emit actuarial default probabilities como contrato público — `moodys_pd_5y_pct` é diagnostic/audit only; consumers leem `default_spread_bps` (market-calibrated).
- Does not cover non-sovereign entities (corporates, supranationals, municipals) — v2 escopo é sovereign.
- Does not integrate minor agencies (Scope, R&I, JCR) — 4 majors only em v2.
- Does not re-rate em response a market moves — ratings são institutional opinions; market-implied ratings (Merton DD) são escopo separado em `integration/diagnostics`.
- Does not use TE (Trading Economics) ratings como primary ou fallback — rejected em D0 audit (2026-04-18) porque TE `/ratings/historical/{country}` endpoint retornou latest 2022-09-09 (~4Y stale). Per v0.2 bump: `damodaran_annual_historical` substitui TE para pre-2023 backfill; agency scrape forward para ≥ 2023.
