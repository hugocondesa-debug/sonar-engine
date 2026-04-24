# Sprint Q.1.2 Audit — `_load_histories` Survey Fallback Gap

**Data**: 2026-04-24 — Week 11 Day 1 late evening
**Branch**: `sprint-q-1-2-load-histories-survey-fallback`
**Parent**: Sprint Q.1.1 (commit `c277703`) — builder main path survey fallback
shipped; Tier B regression discovered: persist step fails for EA cohort despite
classifier FULL emit.
**Objectivo**: documentar o gap exacto em `_load_histories` e o design
forward-fill que o fecha, antes de tocar código.

---

## §1 Evidência empírica (pre-fix)

### 1.1 CLI local run — `sonar-daily-monetary-indices` @ 2026-04-23

Comando:

```bash
set -a; . /home/macro/projects/sonar-engine/.env; set +a
uv run python -m sonar.pipelines.daily_monetary_indices \
  --all-t1 --date 2026-04-23
```

Output relevante (últimas linhas):

```
info  m3_db_backed.survey_fallback   country=PT date=2026-04-23
      survey_date=2026-04-23 survey_name=ECB_SPF_HICP
error monetary_pipeline.country_failed country=PT
      error='history series too short for z-score baseline'
      error_type=InsufficientInputsError
info  monetary_pipeline.summary
      countries_duplicate=['US', 'GB', 'JP', 'CA', 'NL', 'AU']
      countries_failed=['DE', 'EA', 'IT', 'ES', 'FR', 'PT']
      n_duplicate=6 n_failed=6 n_no_inputs=0 n_persisted=0
```

Interpretação:

- Q.1.1 fallback de `build_m3_inputs_from_db` DISPARA correctamente
  (`survey_fallback` log emitted, `breakeven_5y5y_bps` populado).
- M3Inputs monta-se mas o downstream `m3_market_expectations.build()`
  rejeita: `InsufficientInputsError("history series too short for z-score
  baseline")`.
- 6 countries (DE/EA/IT/ES/FR/PT) caem na classificação `FULL` mas nunca
  persistem. Os restantes 6 são `duplicate` (já persistidos por runs
  anteriores a Q.1.1 ship).

### 1.2 Origem do erro

`src/sonar/indices/monetary/m3_market_expectations.py:124`:

```python
if (
    len(inputs.nominal_5y5y_history_bps) < 2
    or len(inputs.anchor_deviation_abs_history_bps) < 2
):
    raise InsufficientInputsError("history series too short for z-score baseline")
```

M3 compute precisa ≥2 pontos em ambas as séries para calcular z-score
baseline. Para a EA cohort, `anchor_deviation_abs_history_bps` vem
vazio — logo o guard dispara.

---

## §2 `_load_histories` — estrutura actual (Q.1.1 baseline)

Ficheiro: `src/sonar/indices/monetary/db_backed_builder.py:377-439`.

### 2.1 Assinatura

```python
def _load_histories(
    session: Session,
    country_code: str,
    *,
    start: date,
    end: date,
    bc_target_bps: float | None,
) -> tuple[list[float], list[float]]:
```

Retorna `(nominal_5y5y_history_bps, anchor_deviation_abs_history_bps)`.

### 2.2 Queries internas

1. `NSSYieldCurveForwards` filtrada por `(country_code, date BETWEEN start AND end)`,
   ordenada ascending por `date`.
2. `IndexValue` filtrada por `(index_code='EXPINF_CANONICAL', country_code,
   date BETWEEN start AND end)`, ordenada ascending. Indexada por `row.date`
   para lookup O(1).

### 2.3 Loop `for fwd in forwards`

Para cada forwards row:

- Extrai `5y5y` do `forwards_json` → append em `nominal_hist` como bps.
- Se `bc_target_bps is None`: `continue` (EA/ES/... sem target central
  bank não entra — ver §5 edge case análise).
- Lookup `expinf_by_date.get(fwd.date)`:
  - `None` → `continue` (**o gap Sprint Q.1.2**).
  - Não-None → extrai `5y5y` de `_expinf_tenors_bps(expinf_row)` → append
    `abs(be_5y5y - bc_target_bps)` em `anchor_hist`.

### 2.4 Falha para EA cohort

Para DE/EA/FR/IT/ES no window 5Y:

- `expinf_rows = []` porque `IndexValue(EXPINF_CANONICAL, country=EA, ...)`
  está vazio (SPF vive em `exp_inflation_survey`, não em `index_values`).
- `expinf_by_date = {}`.
- Loop: `nominal_hist` preenche (forwards persistidos desde Sprint C).
  `anchor_hist` fica `[]` porque `expinf_row is None` sempre.

Resultado: `nominal_5y5y_history_bps = (n1, n2)` (len 2 ✓) +
`anchor_deviation_abs_history_bps = ()` (len 0 ✗). Downstream raise.

---

## §3 Design forward-fill survey fallback

### 3.1 Princípio

Quando `expinf_rows = []` (canonical empty no window), fetch em bulk as
linhas de `exp_inflation_survey` no mesmo window e use forward-fill
per-forwards-date (most recent survey row `<=` forwards date).

Porquê forward-fill:

- Survey (SPF) cadence é quarterly. 5Y window ≈ 20 linhas survey + ~1250
  forwards rows (daily). Cada forwards date precisa mapear à release
  survey mais recente disponível.
- Alinhado com `_query_survey` (Q.1.1) que usa `on-or-before` semantics
  para o data point único — agora estendido para history window.

### 3.2 Pseudo-algoritmo

```
survey_rows = []
if not expinf_rows:
    survey_rows = query(ExpInflationSurveyRow, country, start..end, asc by date)

for fwd in forwards:
    # nominal path unchanged
    nominal_hist.append(...)

    if bc_target_bps is None:
        continue

    # canonical-first (unchanged)
    expinf_row = expinf_by_date.get(fwd.date)
    be_5y5y = None
    if expinf_row:
        be_5y5y = _expinf_tenors_bps(expinf_row).get("5y5y")
    elif survey_rows:
        matched = _latest_survey_on_or_before(survey_rows, fwd.date)
        if matched:
            be_5y5y = _survey_tenors_bps(matched).get("5y5y")

    if be_5y5y is None:
        continue
    anchor_hist.append(abs(be_5y5y - bc_target_bps))
```

### 3.3 Helper novo `_latest_survey_on_or_before`

Linear scan sobre `survey_rows` (pre-sorted ascending). Mantém o último
match com `date <= target`. Early-break quando se ultrapassa o target.

Complexity: O(S × F) worst-case onde S=|survey_rows| (≤20 em 5Y),
F=|forwards| (~1250). Total ~25k ops — trivial. Binary search ou
pointer-walk possível como optimization mas HALT per §4 do brief
(nice-to-have, linear OK).

### 3.4 Invariância canonical-path

Quando `expinf_rows` não está vazio, `survey_rows` nunca é populado
(query nem corre). US continua bit-identical ao pré-Q.1.2 baseline.
Este é o invariante crítico — o test 5 do acceptance tier A valida.

---

## §4 Edge cases considerados

### 4.1 `bc_target_bps is None` (EA members sem BC próprio)

EA cohort: ES/IT/PT/NL mapeiam para ECB via `load_country_to_target()`.
EA agregado idem. FR/DE idem. Nenhum dos 6 afectados tem `bc_target=None`;
todos passam o guard `if bc_target_bps is None: continue`. Logo o
fallback path executa para todos 6.

### 4.2 `survey_rows = []` (window sem releases)

Se window 5Y tem zero survey releases (improvável — SPF corre desde 1999),
`survey_rows = []` e o loop `for fwd in forwards` simplesmente não
alimenta `anchor_hist`. Retorno `(nominal_hist, [])` — downstream M3
raise `InsufficientInputsError`. Comportamento idêntico ao pré-fix;
aceitável per brief §4 HALT-material.

### 4.3 Canonical parcial + survey residual

Se `expinf_rows = [row@D1, row@D3]` (parcial) e survey também tem `[s@D2]`:
o `if not expinf_rows` é `False` → `survey_rows` não é consultado.
Consequência: `D2` fica sem anchor (nem canonical match, nem survey
inspecionado). Aceita-se — aumenta só o gap pré-existente, não regressão.

**Alternativa rejeitada**: fetch survey sempre e intercalar per-date
(canonical-first, survey-fallback per date). Scope-creep; brief §4
HALT-scope explicita minimum change.

### 4.4 Forward-fill de release tardia

Se survey release @D5 e forwards @D3,D4,D5,D6: D3 e D4 não têm match
(release ainda não aconteceu). D5 e D6 usam s@D5. Semântica "release
as of" preservada.

---

## §5 Verificação esperada post-fix

### 5.1 Local CLI

```
info  monetary_pipeline.summary
      countries_duplicate=['US', 'GB', 'JP', 'CA', 'NL', 'AU']
      countries_failed=[]
      countries_persisted=['DE', 'EA', 'IT', 'ES', 'FR', 'PT']
      n_duplicate=6 n_failed=0 n_persisted=6
```

### 5.2 US regression

`mode=FULL` unchanged. Test 500
(`test_survey_fallback_us_regression_unchanged`) cobre M3Inputs bit-identical
pelo caminho canónico. Novo test Q.1.2 equivalent cobre `_load_histories`
canonical path bit-identical.

### 5.3 Systemd follow-up (Tier B, operator)

`sudo systemctl start sonar-daily-monetary-indices.service` → 6/12 M3 FULL
persistently operational (US + EA/DE/FR/IT/ES via survey path).

---

## §6 Pattern reference — Lesson #20 iteration #5

"Shipping path ≠ consuming path" revisitado:

| Iteração | Sprint | Gap                                          |
|----------|--------|----------------------------------------------|
| #1       | Q      | classifier path ≠ builder path               |
| #2       | Q.0.5  | emit cohort ≠ persist cohort                 |
| #3       | Q.1    | loader dispatcher ≠ live_assembler           |
| #4       | Q.1.1  | data-point extraction ≠ history reconstruction (shipped main, missed helper) |
| **#5**   | **Q.1.2** | **helper `_load_histories` extensão**   |

**Refinamento**: Sprint Q.1.1 shipped o data-point branch (`build_m3_inputs_from_db`
main) mas não extendeu `_load_histories` helper. Ambos lêem EXPINF; o
fallback tem de cobrir os dois. Regra emergente: **"extend all helper
functions along the data flow path, not just the entry point"**.

Candidato para ADR-0011 Principle 8 combinado com
"observability-before-wiring" — Week 11 R3 cleanup.

---

*End of audit. Design approved by operator via brief §2 (self-authored by
Hugo pre-Q.1.2 kickoff).*
