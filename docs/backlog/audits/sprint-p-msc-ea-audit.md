# Sprint P Audit — MSC US Pattern + EA Cross-Country Readiness

**Data**: 2026-04-24 — Week 11 Day 1 early afternoon
**Branch**: `sprint-p-msc-ea-l4-cross-country`
**Parent**: Sprint Q.1.2 (M3 EA FULL persist shipped) + Sprint J (M4 EA-custom) +
Sprint L (M2 EA Taylor gaps)
**Objectivo**: documentar o pattern MSC US actual, confirmar disponibilidade de
inputs EA, e decidir Path A (wrapper) vs Path B (refactor) antes de tocar código.

---

## §1 MSC US builder — estado actual

### 1.1 Módulo alvo

`src/sonar/cycles/monetary_msc.py` — spec `MSC_COMPOSITE_v0.1`. Entry point:

```python
def compute_msc(
    session: Session,
    country_code: str,
    observation_date: date,
) -> MscComputedResult: ...

def persist_msc_result(session: Session, result: MscComputedResult) -> None: ...
```

### 1.2 Path classification — A (pure function)

O `compute_msc` **já aceita** `country_code` como parâmetro. Leituras sub-index:

| Sub-index | Source                                          | Country filter                    |
|-----------|-------------------------------------------------|-----------------------------------|
| M1        | `M1EffectiveRatesResult` (`monetary_m1_effective_rates`) | `country_code == <param>` |
| M2        | `M2TaylorGapsResult` (`monetary_m2_taylor_gaps`)        | `country_code == <param>` |
| M3        | `IndexValue` (`index_values`, `index_code='M3_MARKET_EXPECTATIONS'`) | `country_code == <param>` |
| M4        | `M4FciResult` (`monetary_m4_fci`)                       | `country_code == <param>` |
| CS        | (not shipped Phase 0-1) — always `None`, flag `COMM_SIGNAL_MISSING` |                   |

Nenhum hardcoded US: nenhum `country_code="US"` literal, nenhum `FRED_SERIES_ID`
hardcoded, nenhum regime label US-specific. Os labels 6-band
(`STRONGLY_ACCOMMODATIVE` … `STRONGLY_TIGHT`) e 3-band (`ACCOMMODATIVE` / `NEUTRAL`
/ `TIGHT`) são universais.

**Conclusão**: **Path A** (thin EA wrapper) aplicável. Zero refactor do builder.
Nenhum CAL-MSC-REFACTOR-CROSS-COUNTRY necessário.

### 1.3 Policy 1 re-weight — efeito EA

Qualquer sub-index ausente dispara re-weight com `min_required = 3` de 5. EA com
M1+M2+M3+M4 = 4/5 (CS sempre ausente) → re-weight válido, `inputs_available=4`,
confidence capped at `REWEIGHT_CONFIDENCE_CAP`.

### 1.4 Dilemma overlay — Phase 0-1

`score > 60` + M3 anchor drifting/unanchored + ECS available. EA MSC @ 2026-04-23
score ~44 → threshold não disparado. ECS ausente → `DILEMMA_NO_ECS` flag se o
score excedesse. Nenhum ajuste necessário.

---

## §2 EA inputs availability — 2026-04-23

### 2.1 Contagem persistida (pre-Sprint-P baseline)

```sql
SELECT COUNT(*) FROM monetary_m1_effective_rates WHERE country_code='EA' AND date='2026-04-23';
SELECT COUNT(*) FROM monetary_m2_taylor_gaps    WHERE country_code='EA' AND date='2026-04-23';
SELECT COUNT(*) FROM monetary_m4_fci            WHERE country_code='EA' AND date='2026-04-23';
SELECT COUNT(*) FROM index_values               WHERE country_code='EA' AND index_code='M3_MARKET_EXPECTATIONS' AND date='2026-04-23';
```

| Sub-index | Pre-audit  | Post-repopulate |
|-----------|-----------:|----------------:|
| M1 EA     | 1          | 1               |
| M2 EA     | 1          | 1               |
| M3 EA     | 0 (missing)| 1 (FULL)        |
| M4 EA     | 1          | 1               |

### 2.2 M3 EA gap — remediation

`index_values` estava vazio para EA / M3 no baseline worktree. O M3 builder já
está shipped (Sprint Q.1.2), mas a persistência só ocorre quando
`daily_monetary_indices` corre com o pipeline completo. Remediation in-scope para
Sprint P:

```bash
uv run python -m sonar.pipelines.daily_monetary_indices \
  --country EA --date 2026-04-23 --backend default
```

Output:

```
monetary_pipeline.m3_compute_mode country=EA mode=FULL
  flags=('EA_M3_T1_TIER', 'SPF_LT_AS_ANCHOR', 'M3_EXPINF_FROM_SURVEY', 'M3_FULL_LIVE')
m3_db_backed.survey_fallback country=EA date=2026-04-23
  survey_date=2026-04-23 survey_name=ECB_SPF_HICP
monetary_pipeline.persisted country=EA persisted={'m1': 0, 'm2': 0, 'm3': 1, 'm4': 0}
```

M3 EA row persistido @ 2026-04-23, `value_0_100=50.0`, `confidence=0.65`,
flags=`INSUFFICIENT_HISTORY,M3_EXPINF_FROM_SURVEY,SPF_LT_AS_ANCHOR`.

A divergência entre brief (§2.1.2 M3 note "builder-only") e realidade (persist
via `persist_many_monetary_results` em `src/sonar/db/persistence.py` L1205-1207)
é redundância do próprio brief: a persistência **existe**; o que estava em falta
no baseline era apenas a invocação do pipeline monetário para EA no target date.
Sprint P não precisa de in-flight build; basta garantir o M3 row está persistido
antes do `compute_msc`.

---

## §3 MSC EA dry-run — 2026-04-23

### 3.1 Comando

```bash
uv run python -m sonar.cycles.orchestrator --country EA --date 2026-04-23
```

### 3.2 Output (post-M3-persist)

```
cycles.cccs.skipped country=EA error="Composite requires >= 3 sub-indices; got 0 (missing: ['CS', 'LC', 'MS'])"
cycles.fcs.skipped  country=EA error="Composite requires >= 3 sub-indices; got 0 (missing: ['F1', 'F2', 'F3', 'F4'])"
cycles.ecs.skipped  country=EA error="Composite requires >= 3 sub-indices; got 0 (missing: ['E1', 'E2', 'E3', 'E4'])"
cycles.orchestrator.complete
  country=EA date=2026-04-23
  msc_score=44.17  msc_regime_6band=NEUTRAL_ACCOMMODATIVE  msc_regime_3band=NEUTRAL
```

MSC EA persist confirmado:

| Campo             | Valor                                                             |
|-------------------|-------------------------------------------------------------------|
| score_0_100       | 44.17                                                             |
| regime_6band      | NEUTRAL_ACCOMMODATIVE                                             |
| regime_3band      | NEUTRAL                                                           |
| m1_score_0_100    | 65.84                                                             |
| m2_score_0_100    | 50.0                                                              |
| m3_score_0_100    | 50.0                                                              |
| m4_score_0_100    | 0.0                                                               |
| cs_score_0_100    | NULL (`COMM_SIGNAL_MISSING`)                                      |
| inputs_available  | 4                                                                 |
| confidence        | 0.48                                                              |
| flags             | inclui `M3_EXPINF_FROM_SURVEY`, `SPF_LT_AS_ANCHOR` (spec §5 esperado) |

### 3.3 Sanity — regime plausível

ECB policy rate 2026-04 moderadamente acomodatícia (DFR ~2.5%). M4 FCI EA-custom
@ 0.0 sinaliza condições muito acomodatícias. M3 anchoring @ 50 neutro. M1 @
65.84 ligeiramente restrictive. Composto 44.17 → NEUTRAL_ACCOMMODATIVE bucket
(35-50) coerente com o stance híbrido.

CCCS / FCS / ECS graceful skip via `InsufficientCycleInputsError` (EA não tem
sub-indices dessas famílias — fora de scope Sprint P). Orquestrador retorna exit
0.

---

## §4 Dispatcher — decisão

### 4.1 Constante `T1_7_COUNTRIES` vs Sprint Q.0.5 unificação

`src/sonar/pipelines/daily_cycles.py` ainda carrega o tuple legado:

```python
T1_7_COUNTRIES: tuple[str, ...] = ("US", "DE", "PT", "IT", "ES", "FR", "NL")
```

Sprint Q.0.5 unificou em `daily_monetary_indices.py` para
`T1_COUNTRIES = (..., "EA", "GB", "JP", ...)`. Os pipelines CCCS / FCS / ECS
(credit, financial, economic, cost-of-capital) ainda usam `T1_7_COUNTRIES` (7
sovereigns). Alinhar daily_cycles com a unificação Q.0.5 é scope válido para
Week 12+ (`CAL-COHORT-CONSTANT-CLEANUP` já aberto) — **não** Sprint P.

### 4.2 Sprint P minimum viable dispatch

O CLI actual `daily_cycles --country EA --date 2026-04-23` já despacha MSC EA
sem alterações (via `run_one` → `compute_all_cycles` → `compute_msc`). A
"dispatcher extension" Sprint P consiste em:

1. Expor constante `MSC_CROSS_COUNTRY_COHORT: tuple[str, ...] = ("US", "EA")`
   em `daily_cycles.py` para documentar o escopo MSC L4 cross-country (separado
   do `T1_7_COUNTRIES` all-cycles cohort).
2. Actualizar docstring do módulo para reflectir que MSC passa a cobrir EA em
   paralelo com US.
3. **Não** adicionar novo flag CLI (`--all-msc`) — scope creep. Systemd
   dispatch EA schedulable via invocações explícitas `--country EA`.
4. **Não** tocar em `T1_7_COUNTRIES` — 5 test suites dependem do tuple exacto
   de 7 sovereigns (`test_daily_cycles`, `test_daily_credit_indices`,
   `test_daily_economic_indices`, `test_daily_financial_indices`,
   `test_daily_overlays`, `test_daily_cost_of_capital`, `test_status`).

### 4.3 US regression — pre-Sprint-P row unchanged

A row `monetary_cycle_scores` (US, 2026-04-23) pre-existia (score 55.82,
NEUTRAL_TIGHT, 3/5 inputs, flag `M3_MISSING`). **Não é recomputada em Sprint P**
— o unique constraint `(country_code, date)` bloquearia re-persist. A row US
reflecte o estado pre-M3-persist-US para essa data; o builder logic está
unchanged, que é o acceptance real de "US regression unchanged" (Tier A #5).

Tests MSC US existentes validam o builder logic; passar esses tests é a
acceptance evidence.

---

## §5 Flags inheritance — confirmação

Spec §2.4 requer propagação upstream. Lista EA MSC @ 2026-04-23:

```
COMM_SIGNAL_MISSING                  ← compute_msc (CS sempre ausente Phase 0-1)
EA_M2_CPI_TE_LIVE                    ← M2 EA
EA_M2_FULL_COMPUTE_LIVE              ← M2 EA
EA_M2_INFLATION_FORECAST_TE_LIVE     ← M2 EA
EA_M2_OUTPUT_GAP_OECD_EO_LIVE        ← M2 EA
EA_M2_POLICY_RATE_ECB_DFR_LIVE       ← M2 EA
EA_M4_10Y_YIELD_LIVE                 ← M4 EA
EA_M4_CREDIT_SPREAD_FRED_OAS_LIVE    ← M4 EA
EA_M4_FULL_COMPUTE_LIVE              ← M4 EA
EA_M4_MORTGAGE_ECB_MIR_LIVE          ← M4 EA
EA_M4_NEER_BIS_LIVE                  ← M4 EA
EA_M4_NEER_MONTHLY_CADENCE           ← M4 EA
EA_M4_VOL_TE_LIVE                    ← M4 EA
EXPECTED_INFLATION_PROXY             ← M2 EA
INSUFFICIENT_HISTORY                 ← M3 EA + compute_msc
M3_EXPINF_FROM_SURVEY                ← M3 EA (Sprint Q.1.x)
SPF_LT_AS_ANCHOR                     ← M3 EA (Sprint Q.1.x)
TAYLOR_VARIANT_DIVERGE               ← M2 EA
```

Spec §2.4 checklist Tier B #4:
- [x] `M3_EXPINF_FROM_SURVEY` presente
- [x] `SPF_LT_AS_ANCHOR` presente
- [x] M4 EA-custom flags presentes (cover flags de Sprint J)
- [ ] `SPF_AREA_PROXY` — não presente (EA é target directo do ECB_SPF, não proxy; ausência é correcta)

---

## §6 HALT review

- **HALT-0** (EA M2/M4 missing): ✗ não disparado — M2/M4 presentes.
- **HALT-0** (MSC US-hardcoded Path B 2x scope): ✗ não disparado — Path A confirmado.
- **HALT-material** (US regression): ✗ não disparado — builder untouched.
- **HALT-material** (M3 in-flight build fails): ✗ não aplicável — M3 persistido upstream, não in-flight.
- **HALT-material** (M4 EA-custom partial): ✗ não disparado — M4 FULL.
- **HALT-scope** (MSC DE/FR/IT/ES tentation): mantido — Sprint P.1+ separate.

Nenhum HALT activo. Green light para implementation (commits C3-C6).

---

## §7 Decisão final

- **Path A** confirmado (thin wrapper zero refactor).
- **Dispatcher**: adicionar `MSC_CROSS_COUNTRY_COHORT` constant + docstring
  update em `daily_cycles.py`. Zero CLI flag novo. Zero toque em
  `T1_7_COUNTRIES`.
- **M3 EA**: remediation via single-shot `daily_monetary_indices --country EA`
  run (documentado em §2.2). Não requer in-flight build MSC-side.
- **US regression**: validated via builder test preservation; pre-existing
  `monetary_cycle_scores(US, 2026-04-23)` row preservada (unique constraint).
- **Tests**: add MSC EA composite + MSC_CROSS_COUNTRY_COHORT constant assertion.
- **Retro**: L4 coverage 1/16 → 2/16 (+6pp); T1 overall estimate +1-2pp.

Sprint P proceeds C3 → C4 → C5 → C6.

*End audit.*
