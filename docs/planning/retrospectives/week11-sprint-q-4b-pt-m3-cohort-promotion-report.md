# Sprint Q.4b — PT M3 FULL Promotion (Cohort Extension) — Retrospective

**Data close**: 2026-04-24 (Week 11 Day 1 PM)
**Branch**: `sprint-q-4b-pt-m3-cohort-promotion`
**Brief**: `docs/planning/week11-sprint-q-4b-pt-m3-cohort-promotion-brief.md`
**Parent**: Sprint Q.1 (PT SPF row populated via SPF_AREA_PROXY) + Sprint Q.1.1 (classifier survey fallback) + Sprint Q.3 (retro identificou PT promotion como "free")
**Duração efectiva CC**: ~20 min (dentro best-case do brief)
**Outcome**: **SHIPPED — Tier A completo; PT M3 NOT_IMPLEMENTED → FULL via cascade existente; 9 FULL → 10 FULL no T1 cohort**

---

## §1 Scope delivered

Sprint Q.4b promove PT no M3 T1 classifier estendendo `M3_T1_COUNTRIES`
de 9 para 10 países. Não há código novo de connector, builder, writer
ou helper — apenas a constante de cohort. A cascade survey-fallback
shipped em Sprint Q.1.1 + a row `SPF_AREA_PROXY` shipped em Sprint Q.1
fazem o resto: classifier vê PT membership → procura forwards (presente)
→ procura canonical EXPINF (ausente para PT) → procura survey row
(presente, `SPF_AREA_PROXY`) → uplift para FULL.

### M3 matrix — pre/post

| Country | Pre-Q.4b | Post-Q.4b | Source |
|---|---|---|---|
| US | FULL (canonical) | FULL (canonical) | unchanged |
| DE | FULL (survey, SPF_AREA_PROXY) | FULL (survey, SPF_AREA_PROXY) | unchanged |
| EA | FULL (survey) | FULL (survey) | unchanged |
| GB | FULL (BEI) | FULL (BEI) | unchanged |
| JP | FULL (TANKAN_LT_AS_ANCHOR) | FULL (TANKAN_LT_AS_ANCHOR) | unchanged |
| CA | FULL (CES_LT_AS_ANCHOR) | FULL (CES_LT_AS_ANCHOR) | unchanged |
| IT | FULL (survey, SPF_AREA_PROXY) | FULL (survey, SPF_AREA_PROXY) | unchanged |
| ES | FULL (survey, SPF_AREA_PROXY) | FULL (survey, SPF_AREA_PROXY) | unchanged |
| FR | FULL (survey, SPF_AREA_PROXY) | FULL (survey, SPF_AREA_PROXY) | unchanged |
| **PT** | **NOT_IMPLEMENTED** | **FULL** (`M3_EXPINF_FROM_SURVEY`, `SPF_AREA_PROXY`) | **Q.4b new** |
| NL | NOT_IMPLEMENTED | NOT_IMPLEMENTED | outside `M3_T1_COUNTRIES` (curves blocked Sprint M) |
| AU | NOT_IMPLEMENTED | NOT_IMPLEMENTED | outside `M3_T1_COUNTRIES` (Week 11+ probe) |

Resumo: **10 FULL / 0 DEGRADED / 2 NOT_IMPLEMENTED** (meta Tier B).
T1 coverage M3 ~75% → ~83% (+1 country / +8pp). T1 overall ~76-78%.

### CLI verify (Acceptance §5.2)

```
country=PT flags=('PT_M3_T1_TIER', 'SPF_LT_AS_ANCHOR', 'SPF_AREA_PROXY',
                  'M3_EXPINF_FROM_SURVEY', 'M3_FULL_LIVE')
mode=FULL observation_date=2026-04-23
```

Regression — 9 outros FULL countries (US/DE/EA/GB/JP/CA/IT/ES/FR)
re-corridos com `--backend default`: todos `mode=FULL` com flags
inalteradas. Zero bleed.

### Ficheiros tocados

| Ficheiro | Mudança |
|---|---|
| `src/sonar/indices/monetary/m3_country_policies.py` | `M3_T1_COUNTRIES` frozenset estendida com `"PT"` (9→10). Module docstring + sparsity-comment + `NOT_IMPLEMENTED` mode docstring actualizadas para reflectir que PT já não está fora do cohort. Zero alteração funcional ao classifier — a cascade survey-fallback (Sprint Q.1.1, lines 186-209) trata PT exactamente como trata IT/ES/FR. |
| `src/sonar/pipelines/daily_monetary_indices.py` | 1 linha de comentário (T1_COUNTRIES per-country mode table): `PT M3 NOT_IMPLEMENTED, M4 FULL` → `PT M3 FULL (Sprint Q.4b via SPF_AREA_PROXY), M4 FULL (Sprint J)`. |
| `tests/unit/test_pipelines/test_m3_builders.py` | Module docstring 9-country → 10-country. `test_country_m3_flags_empty_for_non_cohort` — PT removido (já não non-cohort). `test_t1_m3_countries_alias_resolves_to_unified_cohort` — diff set `{"AU","NL","PT"}` → `{"AU","NL"}` + assertion explícita `len(M3_T1_COUNTRIES) == 10`. `test_classifier_not_implemented_pt` removido (PT já não NOT_IMPLEMENTED). `test_run_one_m3_compute_mode_not_implemented_for_pt` repurposed → `test_run_one_m3_compute_mode_not_implemented_for_au` (preserva Lesson #7 systemd-verify contract usando AU que continua NOT_IMPLEMENTED). NOVO: `test_pt_resolves_via_spf_area_proxy` — seed forwards + SPF_AREA_PROXY survey → assert FULL com flags propagadas. |

**Zero touch**:
- `src/sonar/indices/monetary/db_backed_builder.py` (cascade priority lógica)
- `src/sonar/indices/monetary/exp_inflation_writers.py` (Sprint Q.1 writer já persiste PT row)
- `src/sonar/indices/monetary/m3_market_expectations.py` (compute interno)
- Connectors (zero novos)
- DB schema / migrations

Lesson #20 #6 graduado em Sprint Q.3 → aplicado preventivamente: o
único cascade site verdadeiro era `M3_T1_COUNTRIES` (frozenset), e a
sua extensão é a totalidade do scope de implementação. Test surface
coupling identificado abaixo (§3).

---

## §2 DB state — verificação pre-flight

```
sqlite> SELECT country_code, survey_name, COUNT(*), flags
        FROM exp_inflation_survey WHERE country_code='PT' GROUP BY ...;
PT|ECB_SPF_HICP|5|SPF_LT_AS_ANCHOR,SPF_AREA_PROXY
```

PT survey row presente desde Sprint Q.1 (5 observations, 2026-02-15 →
2026-04-24, todas com `SPF_AREA_PROXY` flag). Forwards row para
2026-04-23 confirmado. M1/M2 PT = 0 rows (estructural — PT é EA-member,
roteia via EA policy rate; idêntico a IT/ES/FR/DE/NL); M4 PT = 3 rows.
Brief §2.1 HALT-0 condicional sobre M1/M2 ausentes foi
**conservador-demais** dada a arquitectura EA-routing — IT/ES/FR já FULL
com mesma estrutura. HALT não accionado, escalação não necessária.

---

## §3 Lessons & observations

### §3.1 Lesson #20 #6 cohort cascade — confirmado

A grad de Lesson #20 #6 em Sprint Q.3 ("classifier cohort sites devem
ter inventory completo antes do code touch") foi aqui validada
prospectivamente: o `grep -rn "M3_T1_COUNTRIES"` deu 5 hits em src/, todos
no mesmo módulo (definição + 2 docstrings + 2 referências `if country
not in ...`). Cohort cascade **single-site clean** — a constante é
verdadeiramente o único cascade point. Zero risk de drift.

### §3.2 Test surface coupling — não é "1 line + 1 test"

Brief framing "1-line + 1 test" subestimou o test surface coupling: a
extensão da cohort de 9 para 10 quebrou 4 test sites distintos:

1. `test_country_m3_flags_empty_for_non_cohort` — PT estava na lista non-cohort
2. `test_t1_m3_countries_alias_resolves_to_unified_cohort` — diff set hardcoded `{"AU","NL","PT"}`
3. `test_classifier_not_implemented_pt` — teste explícito do mode NOT_IMPLEMENTED para PT
4. `test_run_one_m3_compute_mode_not_implemented_for_pt` — teste explícito do log emit para PT NOT_IMPLEMENTED

Mais o NOVO `test_pt_resolves_via_spf_area_proxy`. Total: 5 test
edits (1 add, 2 update, 1 delete, 1 repurpose). Não é overhead bug — é
a **medida correcta** do contrato de cohort exposto pelos testes
existentes. Para futuros cohort extensions (NL post-Sprint M):

- Pre-flight: `grep -rn "<COUNTRY>" tests/` + `grep -rn "{...,'<COUNTRY>'}" tests/` → contar test sites antes de estimar budget.
- Heuristic: 1 country promotion = 4-6 test edits (cohort assertion + non-cohort assertion + dedicated NOT_IMPLEMENTED test + dedicated log-emit test + new FULL test + parametric tests auto-pickup).
- Budget realista: 20-30 min, não 15 min. Brief Q.4b previu 20 min median e shippou em ~20 min — calibração correcta apesar do framing "1-line".

### §3.3 HALT-0 conservatism — `M1/M2/M4 inputs` check é over-trigger

Brief §2.1 incluiu pre-flight de PT M1/M2/M4 inputs com HALT-0 se
ausentes. M1/M2 retornaram 0 — mas isto é **estrutural** (EA-member
countries não têm policy-rate independente). IT/ES/FR/DE têm o mesmo
estado e são FULL. Future briefs para EA-periphery countries:

- M1/M2 ausência **só é HALT** para non-EA countries.
- M4 presence é o sinal verdadeiro de "country participates in monetary indices runtime".

Reportado para PT post-merge: M3 persistiu 1 row (PT EXPINF cascade FULL
funciona standalone). M1/M2 skipped por "no inputs provided" (esperado,
EA-routing). M4 = 3 rows existentes (Sprint J).

### §3.4 Calibração brief vs execução — dentro de target

Brief budget: 20-30 min, best 15 min, hard stop 30 min. Execução: ~20
min (incluindo regression sweep + pre-commit double-run + retro draft).
**Brief framing accurate**, mesmo subestimando test coupling. Confiança
em estimativas de cohort-extension calibrated upwards: future PT/NL/AU
M3 promotion sprints podem usar Q.4b como baseline de 20 min.

---

## §4 Acceptance status

### Tier A — todos verde

1. ✅ PT em `M3_T1_COUNTRIES` (frozenset size = 10)
2. ✅ CLI PT `mode=FULL` com `SPF_AREA_PROXY` + `M3_EXPINF_FROM_SURVEY` (CLI verify §1)
3. ✅ Regression — 9 outros FULL countries inalterados (CLI sweep §1)
4. ✅ Tests pass — 50 test_m3_builders.py / 107 broader monetary
5. ✅ Pre-commit clean double-run

### Tier B — pending systemd verify

10 FULL / 0 DEGRADED / 2 NOT_IMPLEMENTED — a confirmar em próximo
systemd run (não bloqueador, dependent of timer fire).

---

## §5 Follow-ups

Nenhum CAL aberto por Q.4b. NL M3 promotion bloqueada em Sprint M
(curves probe pendente — NL sem yield_curves_forwards row). AU M3
promotion = Week 11+ sparse probe (separate scope).

Sprint Q.4b conclui as quick-wins de cohort extension a partir das
fundações Q.1/Q.1.1/Q.3. Próximo target M3 uplift requer connector new
(NL forwards) ou probe (AU) — não há mais "free" extensions disponíveis.

---

*Sprint mínimo. 1 linha de cohort + 5 test edits + 1 docstring touch
no pipeline. Ship 20 min. Lesson #20 #6 prospectivamente validado.*
