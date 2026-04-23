# DB Schema Reference (canonical table + column names)

**Status**: Canonical reference (Week 10 Sprint T0, 2026-04-23)
**Scope**: SQLite MVP Phase 1 — tables touched by L1-L8 pipelines, overlays,
indices, and cycles.
**Authoritative source**: `alembic` migrations in `alembic/versions/`. When
this doc diverges from the migration output, the migration wins — file a
fix PR.

---

## Propósito

Documento existe para prevenir handoff drift (ex: Day 3 Week 10 handoff
referenciou `nss_yield_curves_spot` / `indices_spot`, ambos nomes
inexistentes em prod). Single source of truth para:

- Nome da tabela por entity.
- Coluna de data usada para filtering.
- UNIQUE constraint por tabela (crítico para idempotency — ver ADR-0011).
- Identificador de country (ISO 3166-1 alpha-2 canónico ADR-0007).

Uso: qualquer novo builder / pipeline / query SQL que mencione uma tabela
L1 verifica este doc antes. Qualquer handoff que refira tabela valida
contra `.schema <table>` via `sqlite3`.

---

## Tabelas canónicas

### L2 curves (`yield_curves_*`)

| Entity | Table | Date column | Unique | Notas |
|---|---|---|---|---|
| Spot NSS fit | `yield_curves_spot` | `date` | `uq_ycs_country_date_method (country_code, date, methodology_version)` + `uq_ycs_fit_id (fit_id)` | Parent para zero / forwards / real via `fit_id` FK |
| Zero curve | `yield_curves_zero` | `date` | `uq_ycz_country_date_method (country_code, date, methodology_version)` | FK → `yield_curves_spot.fit_id` (ON DELETE CASCADE) |
| Forward curve | `yield_curves_forwards` | `date` | `uq_ycf_country_date_method (country_code, date, methodology_version)` | FK → `yield_curves_spot.fit_id` (ON DELETE CASCADE) |
| Real curve (linkers) | `yield_curves_real` | `date` | *(triplet UNIQUE; see migration)* | Populated when `NSSFitResult.real is not None` |
| Curve raw observations | `yield_curves_raw` | `date` | — | L0 connector raw tape; pre-fit |
| Fitted curve (legacy) | `yield_curves_fitted` | — | — | Legacy; not used by new pipelines |
| Curve metadata | `yield_curves_metadata` | — | — | Methodology version registry |
| Curve params (legacy) | `yield_curves_params` | — | — | Legacy; not used |

### L2 overlays (ERP / CRP / expected inflation / ratings)

| Entity | Table | Date column | Unique |
|---|---|---|---|
| ERP canonical | `erp_canonical` | `date` | *(market_index, date, methodology_version)* |
| ERP CAPE | `erp_cape` | `date` | *(market_index, date, ...)* |
| ERP DCF | `erp_dcf` | `date` | *(market_index, date, ...)* |
| ERP EY | `erp_ey` | `date` | *(market_index, date, ...)* |
| ERP Gordon | `erp_gordon` | `date` | *(market_index, date, ...)* |
| CRP canonical | `crp_canonical` | `date` | *(country_code, date, methodology_version)* |
| CRP CDS | `crp_cds` | `date` | — |
| CRP rating | `crp_rating` | `date` | — |
| CRP sov spread | `crp_sov_spread` | `date` | — |
| Expected inflation canonical | `exp_inflation_canonical` | `date` | *(country_code, tenor, date, ...)* |
| Expected inflation BEI | `exp_inflation_bei` | `date` | — |
| Expected inflation survey | `exp_inflation_survey` | `date` | — |
| Expected inflation swap | `exp_inflation_swap` | `date` | — |
| Expected inflation derived | `exp_inflation_derived` | `date` | — |
| Ratings agency raw | `ratings_agency_raw` | `date` | *(country_code, date, agency, rating_type, methodology_version)* |
| Ratings consolidated | `ratings_consolidated` | `date` | *(country_code, date, rating_type, methodology_version)* |
| Ratings spread calibration | `ratings_spread_calibration` | `calibration_date` | — |
| BIS credit raw | `bis_credit_raw` | `date` | — |

### L3 monetary indices

| Entity | Table | Date column | Unique |
|---|---|---|---|
| M1 effective rates | `monetary_m1_effective_rates` | `date` | `uq_m1_cdm (country_code, date, methodology_version)` |
| M2 Taylor gaps | `monetary_m2_taylor_gaps` | `date` | `uq_m2_cdm (country_code, date, methodology_version)` |
| M3 Market expectations | *(builder-only, derives from `yield_curves_forwards` + `exp_inflation_canonical`; persisted as IndexValue row)* | — | — |
| M4 FCI | `monetary_m4_fci` | `date` | `uq_m4_cdm (country_code, date, methodology_version)` |

**Note**: M3 does not have a dedicated table. Results persist via the
generic `index_values` table (below). The `MonetaryDbBackedInputsBuilder`
reads `yield_curves_forwards` at runtime to compute M3 on-the-fly
(CAL-108).

### L3 economic indices

| Entity | Table | Date column | Unique |
|---|---|---|---|
| E1 activity | `idx_economic_e1_activity` | `date` | `uq_e1_cdm (country_code, date, methodology_version)` |
| E2 inflation | *(builder-only; persisted as IndexValue row)* | — | — |
| E3 labor | `idx_economic_e3_labor` | `date` | `uq_e3_cdm (country_code, date, methodology_version)` |
| E4 sentiment | `idx_economic_e4_sentiment` | `date` | `uq_e4_cdm (country_code, date, methodology_version)` |

### L3 credit indices

| Entity | Table | Date column | Unique |
|---|---|---|---|
| Credit-to-GDP stock (L1) | `credit_to_gdp_stock` | `date` | `uq_l1_cgs_cdm (country_code, date, methodology_version)` |
| Credit-to-GDP gap (L2) | `credit_to_gdp_gap` | `date` | `uq_l2_cgg_cdm (country_code, date, methodology_version)` |
| Credit impulse (L3) | `credit_impulse` | `date` | `uq_l3_ci_cdms (country_code, date, methodology_version, segment)` |
| DSR (L4) | `dsr` | `date` | `uq_l4_dsr_cdms (country_code, date, methodology_version, segment)` |

### L3 financial indices

| Entity | Table | Date column | Unique |
|---|---|---|---|
| F1 valuations | `f1_valuations` | `date` | `uq_f1_cdm (country_code, date, methodology_version)` |
| F2 momentum | `f2_momentum` | `date` | `uq_f2_cdm (country_code, date, methodology_version)` |
| F3 risk appetite | `f3_risk_appetite` | `date` | `uq_f3_cdm (country_code, date, methodology_version)` |
| F4 positioning | `f4_positioning` | `date` | `uq_f4_cdm (country_code, date, methodology_version)` |

### L4 cycles

| Entity | Table | Date column | Unique |
|---|---|---|---|
| MSC Monetary Cycle | `monetary_cycle_scores` | `date` | `uq_msc_cdm (country_code, date, methodology_version)` + `uq_msc_id (msc_id)` |
| FCS Financial Cycle | `financial_cycle_scores` | `date` | `uq_fcs_cdm (country_code, date, methodology_version)` + `uq_fcs_id (fcs_id)` |
| CCCS Credit Cycle | `credit_cycle_scores` | `date` | `uq_cccs_cdm (country_code, date, methodology_version)` + `uq_cccs_id (cccs_id)` |
| ECS Economic Cycle | `economic_cycle_scores` | `date` | *(country_code, date, methodology_version)* + cycle-id UNIQUE |

### L5 regimes (Phase 2+ scaffold)

| Entity | Table | Date column | Unique |
|---|---|---|---|
| L5 meta regimes | `l5_meta_regimes` | `date` | *(country_code, date, methodology_version)* |

### L6 integration — cost of capital

| Entity | Table | Date column | Unique |
|---|---|---|---|
| Cost of capital daily | `cost_of_capital_daily` | `date` | `uq_kc_cdm (country_code, date, methodology_version)` |

### Generic index persistence

| Entity | Table | Date column | Unique |
|---|---|---|---|
| Index values (generic) | `index_values` | `date` | *(index_code, country_code, date, methodology_version)* |

---

## Canonical naming invariants

Shared conventions across every L1-L6 table in this project:

1. **Country**: column name is `country_code`; type `VARCHAR(2)`; values
   ISO 3166-1 alpha-2 canonical (ADR-0007). "UK" is a deprecated alias
   for "GB" handled at ingress only; persisted rows always carry "GB".
2. **Date**: column name is `date`; type `DATE`. Never `obs_date`,
   `observation_date` (Python-side dataclasses use `observation_date`
   but the ORM mapping writes `date`).
3. **Methodology version**: column name is `methodology_version`;
   type `VARCHAR(32)`; format `{MODULE}_{VARIANT?}_v{MAJOR}.{MINOR}`
   per CLAUDE.md §4.
4. **Primary idempotency key**: every L2-L4 scored table includes a
   UNIQUE constraint on `(country_code, date, methodology_version)` —
   with optional `segment` 4th column for credit_impulse + dsr.

Idempotency consequences: pipelines that re-run for the same
`(country_code, date)` must either skip (pre-check) or handle the
UNIQUE violation as a benign duplicate. Never fatal. See ADR-0011.

---

## Tables omitted

Not listed because not touched by daily pipelines in Sprint T0 scope:

- `alembic_version` — migration state.
- Auxiliary lookup tables (if any) — see `alembic` migrations.

---

## Maintenance

- Update on new table: any migration that adds a persisted entity adds
  a row to the relevant section above in the same commit.
- Update on rename: any column rename triggers a canonical review
  (UNIQUE constraint naming is part of the schema contract; renames
  are breaking changes per CLAUDE.md §4).
- Verify on doubt: `sqlite3 data/sonar-dev.db ".schema <table>"` is
  authoritative.

---

## Referências

- ADR-0002 — arquitectura 9-layer (L1 persistence canonical).
- ADR-0007 — ISO country codes (UK → GB alias deprecation).
- ADR-0011 — systemd service idempotency + partial-persist recovery.
- `alembic/versions/` — migrations (16 active).
- `src/sonar/db/models.py` — SQLAlchemy ORM mapping.
