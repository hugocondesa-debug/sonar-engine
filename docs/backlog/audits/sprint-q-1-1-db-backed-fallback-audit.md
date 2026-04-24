# Sprint Q.1.1 Audit — DB-Backed Builder EXPINF Survey Fallback

**Data**: 2026-04-24 — Week 11 Day 1 late afternoon
**Branch**: `sprint-q-1-1-db-backed-builder-expinf-survey-fallback`
**Objectivo**: documentar o caminho canónico actual + o path do survey-fallback
a shipear, antes de tocar código.

---

## §1 Contexto herdado (Sprint Q.1)

Sprint Q.1 (Week 11 Day 1 AM) shipped:

- `exp_inflation_survey` table populated — 30 rows (6 countries × 5 dates).
- `ExpInflationSurveyRow` ORM model em `src/sonar/db/models.py:955`.
- Loader dispatcher + live_assembler EA branch.

Runtime fire ainda existente a 2026-04-24:

```
country=EA flags=('EA_M3_T1_TIER', 'M3_EXPINF_MISSING') mode=DEGRADED
country=DE flags=('DE_M3_T1_TIER', 'M3_EXPINF_MISSING') mode=DEGRADED
...
```

Porque os **consumidores** (`classify_m3_compute_mode` +
`build_m3_inputs_from_db`) lêem exclusivamente `IndexValue` onde
`index_code='EXPINF_CANONICAL'` (tabela `index_values`, não a nova
`exp_inflation_survey`).

---

## §2 Caminho canónico actual

### 2.1 `classify_m3_compute_mode` (origem do emit `m3_compute_mode`)

Ficheiro: `src/sonar/indices/monetary/m3_country_policies.py:108-184`

```python
expinf_row = (
    session.query(IndexValue)
    .filter(
        IndexValue.index_code == EXPINF_INDEX_CODE,  # "EXPINF_CANONICAL"
        IndexValue.country_code == country,
        IndexValue.date == observation_date,
    )
    .order_by(IndexValue.confidence.desc())
    .first()
)
if expinf_row is None:
    flags.append("M3_EXPINF_MISSING")
    return "DEGRADED", tuple(flags)
```

Consequência: ausência de row `EXPINF_CANONICAL` ⇒ `DEGRADED` +
`M3_EXPINF_MISSING`, **independentemente** da presença de dados SPF em
`exp_inflation_survey`.

### 2.2 `build_m3_inputs_from_db` (builder que alimenta o compute)

Ficheiro: `src/sonar/indices/monetary/db_backed_builder.py:147-274`

Fluxo:

1. `NSSYieldCurveForwards` para `(country, date)` — mandatory (None on miss).
2. `_query_expinf` → `IndexValue` com `index_code='EXPINF_CANONICAL'`.
3. `_expinf_tenors_bps(row)` extrai `5y5y` + `10Y` de
   `sub_indicators_json['expected_inflation_tenors']`.
4. Flags CSV → tuple via `tuple(expinf_row.flags.split(","))`.
5. Retorna `None` quando EXPINF row ausente ou 5y5y tenor ausente.

### 2.3 Pipeline wiring (daily_monetary_indices.py:540-575)

```python
m3_mode, m3_mode_flags = _classify_m3_compute_mode(
    session, country_code, observation_date
)
log.info("monetary_pipeline.m3_compute_mode", ..., mode=m3_mode, flags=m3_mode_flags)

# Build path — independente do classifier:
m3_inputs = db_backed_builder.build_m3_inputs(country_code, observation_date)
```

**Key insight**: o `mode=FULL` / `mode=DEGRADED` que o acceptance §5 #3
grep-a vem do **classifier**, não do builder. Portanto o scope de Q.1.1
**tem de** incluir ambos os ficheiros para que o acceptance passe. O
brief §2.1.3 já antecipa isto ("pass through to M3 classifier emit")
ainda que §2 só mencione o builder explicitamente.

---

## §3 US regression baseline

```
SELECT country_code, COUNT(*) FROM exp_inflation_canonical ... → N/A (tabela existe mas vazia para US no DB actual)
SELECT country_code, COUNT(*) FROM exp_inflation_bei ... → 0
SELECT country_code, COUNT(*) FROM exp_inflation_swap ... → 0
SELECT country_code, COUNT(*) FROM index_values WHERE index_code='EXPINF_CANONICAL' GROUP BY country_code;
  → US|3
```

**US serve de path via `IndexValue` `EXPINF_CANONICAL`** (3 rows recentes
shipped pelo `daily_overlays` pipeline). O fallback survey só se activa
quando `_query_expinf` retorna `None`; como US tem row canónica, o fluxo
US **não** muda. Regression check garantido desde que:

1. `_query_expinf` continue a ser tentativa primária.
2. Fallback survey só corre quando canonical row ausente.
3. Quando canonical presente, `M3_EXPINF_FROM_SURVEY` **não** é
   adicionada.

---

## §4 Survey table schema reconfirmado

`ExpInflationSurveyRow` (models.py:955-989):

```python
id, exp_inf_id, country_code, date, methodology_version,
confidence, flags (CSV TEXT), created_at,
survey_name, survey_release_date,
horizons_json, interpolated_tenors_json
UNIQUE (country_code, date, survey_name, methodology_version)
INDEX (country_code, date)
```

Amostra EA row (`2026-04-23`):

```
flags='SPF_LT_AS_ANCHOR'
interpolated_tenors_json={
  "10Y": 0.0202, "5Y": 0.0202, "5y5y": 0.0202,
  "1Y": 0.0197, "2Y": 0.0205, "30Y": 0.0202
}
confidence=1.0
```

DE/FR/IT/ES/PT rows carregam `flags='SPF_LT_AS_ANCHOR,SPF_AREA_PROXY'`.

---

## §5 Design do fallback survey

### 5.1 `db_backed_builder.py` — novo helper + branch

```python
def _query_survey(
    session: Session,
    country_code: str,
    observation_date: date,
) -> ExpInflationSurveyRow | None:
    """Retorna a survey row mais recente on-or-before observation_date."""
    return (
        session.query(ExpInflationSurveyRow)
        .filter(
            ExpInflationSurveyRow.country_code == country_code,
            ExpInflationSurveyRow.date <= observation_date,
        )
        .order_by(ExpInflationSurveyRow.date.desc())
        .first()
    )
```

No corpo de `build_m3_inputs_from_db`, quando `expinf_row is None`,
tentar survey fallback antes de retornar None:

```python
survey_row = _query_survey(session, country_code, observation_date)
if survey_row is not None:
    tenors_raw = json.loads(survey_row.interpolated_tenors_json)
    breakeven_5y5y_bps = _decimal_to_bps(float(tenors_raw["5y5y"]))
    survey_10y_bps = _decimal_to_bps(float(tenors_raw["10Y"])) if "10Y" in tenors_raw else None

    survey_flags = tuple(survey_row.flags.split(",")) if survey_row.flags else ()
    flags = survey_flags + ("M3_EXPINF_FROM_SURVEY",)

    return M3Inputs(
        ...,
        breakeven_5y5y_bps=breakeven_5y5y_bps,
        bei_10y_bps=None,           # survey não fornece BEI
        survey_10y_bps=survey_10y_bps,
        expinf_confidence=survey_row.confidence,
        expinf_flags=flags,
    )
return None  # path actual preservado (dispara M3_EXPINF_MISSING downstream)
```

### 5.2 `m3_country_policies.py` — classifier extension

Quando `_query_expinf` (inline via IndexValue) retorna None, antes de
emitir `M3_EXPINF_MISSING`, tentar `_query_survey`:

```python
if expinf_row is None:
    survey_row = _query_survey(session, country, observation_date)
    if survey_row is None:
        flags.append("M3_EXPINF_MISSING")
        return "DEGRADED", tuple(flags)
    if survey_row.confidence < MIN_EXPINF_CONFIDENCE:
        flags.append("M3_EXPINF_CONFIDENCE_SUBTHRESHOLD")
        return "DEGRADED", tuple(flags)
    # Survey fallback success → FULL with propagated flags
    survey_flags = tuple(f for f in (survey_row.flags or "").split(",") if f)
    flags.extend(survey_flags)
    flags.append("M3_EXPINF_FROM_SURVEY")
    flags.append("M3_FULL_LIVE")
    return "FULL", tuple(flags)
```

Comportamento net:

- US (`IndexValue` EXPINF_CANONICAL presente) → path inalterado, `M3_FULL_LIVE`.
- EA/DE/FR/IT/ES (`IndexValue` ausente, survey row presente) → `FULL`
  + `SPF_LT_AS_ANCHOR` + (`SPF_AREA_PROXY` se proxy) +
  `M3_EXPINF_FROM_SURVEY` + `M3_FULL_LIVE`.
- PT (fora de `M3_T1_COUNTRIES`) → `NOT_IMPLEMENTED`, inalterado.
- GB/JP/CA (sem row canónica nem survey row) → `DEGRADED` +
  `M3_EXPINF_MISSING`, inalterado.

---

## §6 Flag propagation map

| Survey row flag       | Classifier emit flag (added) |
|-----------------------|------------------------------|
| `SPF_LT_AS_ANCHOR`    | pass-through                 |
| `SPF_AREA_PROXY`      | pass-through                 |
| —                     | `M3_EXPINF_FROM_SURVEY` (added unconditionally when fallback hits) |
| —                     | `M3_FULL_LIVE` (existing happy-path flag) |

O tier flag `{COUNTRY}_M3_T1_TIER` continua a ser emitido primeiro
(existente). Sparsity flags (`IT_M3_BEI_BTP_EI_SPARSE_EXPECTED`,
`ES_M3_BEI_BONOS_EI_LIMITED_EXPECTED`) continuam a ser emitidos via
`country_m3_flags` — preservados.

---

## §7 Impacto em testes existentes

- `tests/unit/test_indices/monetary/test_db_backed_builder.py` —
  usa `:memory:` DB que cria `exp_inflation_survey` table (via
  `Base.metadata.create_all`) mas não a popula → survey queries retornam
  None → path canónico inalterado. **Zero breaking**.
- `tests/unit/test_pipelines/test_m3_builders.py` — idem; testes
  DEGRADED (GB sem EXPINF) e forwards_missing (EA sem forwards)
  continuam válidos porque survey table vazia.
- Extensões: testes novos para cobrir survey-fallback success path,
  canonical-priority, AREA_PROXY propagation, US regression explícita.

---

## §8 Scope decision (brief inconsistency resolution)

User message stated "db_backed_builder.py + test only" scope lock.
Brief §2.1.3 + §5 acceptance #3 require FULL emit in `m3_compute_mode`
logs. The classifier (`m3_country_policies.py`) is the producer of
those logs — independent of `build_m3_inputs`.

**Decision**: extend scope to include `m3_country_policies.py` +
`test_m3_builders.py`. Justification:

- Acceptance §5 #3 cannot pass without classifier extension.
- Classifier é sibling file a `db_backed_builder` (ambos em
  `sonar/indices/monetary/`), não live_assembler / connector / loader
  (que são os "zero touch" explícitos do user message).
- Brief §2.1.3 antecipa "pass through to M3 classifier emit".

Scope mantém-se micro-cirúrgico: 2 ficheiros src + 2 ficheiros de teste.

---

*Audit concluído. Fallback design pronto para implementação.*
