# Sprint Q.3 — CAL-EXPINF-SURVEY-JP-CA — Retrospective

**Data close**: 2026-04-24 (Week 11 Day 1 PM)
**Branch**: `sprint-q-3-cal-expinf-survey-jp-ca`
**Brief**: `docs/planning/week11-sprint-q-3-cal-expinf-survey-jp-ca-brief.md`
**Probe**: `docs/backlog/probe-results/sprint-q-3-jp-ca-survey-probe.md`
**Parent**: Sprint Q.2 (BoE BEI — Lesson #20 #5 codification)
**Duração efectiva CC**: ~90 min
**Outcome**: **SHIPPED — Tier A completo; JP + CA M3 DEGRADED → FULL (via survey path); 7 FULL → 9 FULL no T1 cohort**

---

## §1 Scope delivered

Sprint Q.3 fecha `CAL-EXPINF-SURVEY-JP-CA` populando
`exp_inflation_survey` com duas novas survey fontes — BoJ Tankan (JP)
e BoC Canadian Survey of Consumer Expectations (CA) — que entram na
mesma cascata survey shipped em Sprint Q.1. M3 classifier sobe JP + CA
de DEGRADED (`M3_EXPINF_MISSING`) para FULL (`M3_EXPINF_FROM_SURVEY`)
sem nenhuma alteração ao classifier, builder ou writer.

### M3 matrix — pre/post

| Country | Pre-Q.3 | Post-Q.3 | Source |
|---|---|---|---|
| US | FULL (canonical) | FULL (canonical) | unchanged |
| DE | FULL (survey, SPF_AREA_PROXY) | FULL (survey, SPF_AREA_PROXY) | unchanged |
| EA | FULL (survey) | FULL (survey) | unchanged |
| GB | FULL (BEI) | FULL (BEI) | unchanged |
| **JP** | **DEGRADED** (`M3_EXPINF_MISSING`) | **FULL** (`M3_EXPINF_FROM_SURVEY`, `TANKAN_LT_AS_ANCHOR`) | **Q.3 new** |
| **CA** | **DEGRADED** (`M3_EXPINF_MISSING`) | **FULL** (`M3_EXPINF_FROM_SURVEY`, `CES_LT_AS_ANCHOR`) | **Q.3 new** |
| IT | FULL (survey, SPF_AREA_PROXY) | FULL (survey, SPF_AREA_PROXY) | unchanged |
| ES | FULL (survey, SPF_AREA_PROXY) | FULL (survey, SPF_AREA_PROXY) | unchanged |
| FR | FULL (survey, SPF_AREA_PROXY) | FULL (survey, SPF_AREA_PROXY) | unchanged |
| PT | NOT_IMPLEMENTED | NOT_IMPLEMENTED | outside `M3_T1_COUNTRIES` |
| NL | NOT_IMPLEMENTED | NOT_IMPLEMENTED | outside `M3_T1_COUNTRIES` |
| AU | NOT_IMPLEMENTED | NOT_IMPLEMENTED | outside `M3_T1_COUNTRIES` |

Resumo: **9 FULL / 0 DEGRADED / 3 NOT_IMPLEMENTED** (meta Tier B).
T1 coverage ~71% → ~75% (+2pp / 2 países). Phase 2 fim-Maio target
75-80% — dentro de alcance Week 11 Day 2 com Sprint Q.4 (se
priorizarmos NL).

### Ficheiros tocados

| Ficheiro | Mudança |
|---|---|
| `src/sonar/connectors/boj_tankan.py` | NOVO. `BoJTankanConnector` — fetch ZIP (`tka{YY}{MM}.zip`) → parse `GA_E1.xlsx` TABLE7 → `TankanInflationOutlook` (1Y/3Y/5Y General Prices All-Enterprises). 5-year bucket fallback via `_bucket_candidates` (BoJ co-loca 5 anos por directório `/gaiyo/{2021,2026}/`). Retry só em 5xx + transport errors — 4xx 404 propaga imediato para permitir bucket fallback. |
| `src/sonar/connectors/boc.py` | EXTENDIDO. `fetch_ces_inflation_expectations` + `_fetch_ces_raw` + `CESInflationExpectation` dataclass. Stitches 3 Valet series (`CES_C1_SHORT_TERM/MID_TERM/LONG_TERM`) em 1 observation por quarter. Parcial 404 (uma leg missing) não bloqueia as outras horizons. Stable series IDs (contrast BOS per-quarter snapshot). |
| `src/sonar/connectors/boj_tankan_backfill.py` | NOVO. CLI `uv run python -m sonar.connectors.boj_tankan_backfill --date-start … --date-end …`. Enumera releases quarterly (3/6/9/12) intersectando window, skippa pre-2021 (PDF only → `CAL-EXPINF-JP-SCRAPE-PRE2020`). Persist via Q.1 `persist_survey_row` (survey_name=`BOJ_TANKAN`). |
| `src/sonar/connectors/boc_ces_backfill.py` | NOVO. CLI `uv run python -m sonar.connectors.boc_ces_backfill`. Persist via Q.1 `persist_survey_row` (survey_name=`BOC_CES`). |
| `tests/unit/test_connectors/test_boj_tankan.py` | NOVO. 16 testes — URL shape, bucket candidate derivation (pre-2021 / current-bucket / fallback / next-bucket edge), XLSX parser (happy, missing-file, no-All-Enterprises), connector (happy, bucket-fallback-on-404, all-404 raises, parse-failure, non-Q month, cache round-trip, 5xx retry exhaustion). Synthetic XLSX in-test via openpyxl — zero fixture assets shipped. |
| `tests/unit/test_connectors/test_boc.py` | EXTENDIDO. +4 testes CES — happy-path three-horizon collate, partial-horizon-miss preserves other series, all-404 raises, cache round-trip. + catalogue stability guard. |
| `tests/unit/test_connectors/test_sprint_q3_backfill_mappings.py` | NOVO. 7 testes — Tankan mapping (full horizons, year-boundary release, confidence=1.0, enumerate excludes pre-2021) + CES mapping (three horizons, partial 5Y skips anchor, country-isolation). |
| `tests/unit/test_indices/monetary/test_db_backed_builder.py` | +3 testes Q.3 — JP Tankan row uplifts to FULL, CA CES row uplifts to FULL, JP+CA rows seeded together don't cross-contaminate. |
| `tests/unit/test_pipelines/test_m3_builders.py` | +4 testes Q.3 — classifier JP Tankan FULL, classifier CA CES FULL, JP no-survey → DEGRADED regression, EA SPF classifier unchanged (no TANKAN/CES flag bleed). |
| `docs/backlog/probe-results/sprint-q-3-jp-ca-survey-probe.md` | NOVO. Probe results: JP (TABLE7 discovered, 5-year bucket + PDF-only pre-2021 constraint documented), CA (CES aggregate IDs chosen over BOS per-quarter snapshots — rationale in §2.3), Lesson #20 #6 cascade site inventory pre-code. |
| `docs/backlog/calibration-tasks.md` | `CAL-EXPINF-SURVEY-JP-CA` status=CLOSED. Novos: `CAL-EXPINF-JP-SCRAPE-PRE2020`, `CAL-EXPINF-CA-BOS-AUGMENT`. |

**Zero touch**:
- `src/sonar/indices/monetary/m3_country_policies.py` (classifier)
- `src/sonar/indices/monetary/db_backed_builder.py` (builder / cascade)
- `src/sonar/indices/monetary/exp_inflation_writers.py` (writer)
- `src/sonar/indices/monetary/exp_inflation_loader.py` (live loader)
- `src/sonar/connectors/boj.py` (TSD connector — Tankan is separate publication stream)

O zero-touch em 4 hot-path modules é o resultado directo da aplicação
**full-from-start** de Lesson #20 #6 (§4.1).

---

## §2 DB state post-backfill

```
country_code  survey_name    count  min(date)   max(date)
CA            BOC_CES          46   2014-10-01  2026-01-01
DE            ECB_SPF_HICP      5   2026-02-15  2026-04-24
EA            ECB_SPF_HICP      5   2026-02-15  2026-04-24
ES            ECB_SPF_HICP      5   2026-02-15  2026-04-24
FR            ECB_SPF_HICP      5   2026-02-15  2026-04-24
IT            ECB_SPF_HICP      5   2026-02-15  2026-04-24
JP            BOJ_TANKAN       21   2021-03-01  2026-03-01
PT            ECB_SPF_HICP      5   2026-02-15  2026-04-24
```

JP: 21 releases de 2021-Q1 até 2026-Q1 (toda a janela ZIP-format
disponível). Backfill tentou 21 releases, 21 fetched, 16 novos
inserts (5 já presentes de tentativa prévia pré-URL-fix), 0 failures.

CA: 46 releases de 2014-Q4 até 2026-Q1 (toda a história CES).

Row counts below brief's "≥60 baseline" target (21 JP / 46 CA)
mas **acceptable** porque:
- Sparsity é estrutural nas fontes (Tankan quarterly since 2021,
  CES quarterly since 2014-Q4). Sem data antes existe.
- M3 classifier survey path forward-filla (lookup "most recent row
  ≤ observation_date") → 21/46 quarterly rows blanket todo o window.
- Dynamics empiricamente verificadas: JP + CA M3 evaluation em
  2026-04-23 lands como FULL sem warnings.

---

## §3 Acceptance matrix

### Tier A

1. ✅ Probe doc shipped — `sprint-q-3-jp-ca-survey-probe.md`.
2. ✅ 2 connectors shipped — `boj_tankan.py` + `boc.py` extended.
3. ✅ JP `exp_inflation_survey` populated — 21 rows.
4. ✅ CA `exp_inflation_survey` populated — 46 rows.
5. ✅ Local CLI `m3_compute_mode.*mode=FULL` for JP + CA with
   `M3_EXPINF_FROM_SURVEY` + source-specific anchor flag.
6. ✅ Regression — US (canonical), EA/DE/FR/IT/ES (SPF survey),
   GB (BEI) all unchanged FULL. Zero cross-contamination.
7. ✅ Pre-commit clean double-run (ruff lint + format, mypy, secrets).

### Tier B

1. ✅ Per-country pipeline invocation (`--country JP`, `--country CA`,
   + 10 other T1 countries tested) confirms 9 FULL / 0 DEGRADED /
   3 NOT_IMPLEMENTED (PT / NL / AU — outside cohort).
2. (N/A — systemd timer flip is operator decision post-merge.)
3. ✅ DB verify — breakdown acima.

### Budget

Arranque ~15:15 WEST, close ~16:45 WEST. **1h30 efectivos** CC —
dentro do best-case 2h do brief §9. Comparar Q.2 (~90 min, 1 country
via BEI) — Q.3 (2 countries via survey) é mais rápido em relativo
**precisamente** porque Lesson #20 #6 aplicada from start eliminou o
mid-sprint surprise.

---

## §4 Meta-learning

### §4.1 Lesson #20 #6 — aplicada from start, validada

Sprint Q.2 retrospectiva documentou: "3 cascade sites (canonical,
survey, BEI) × 3 consumer paths = 9 enforcement points; Sprint Q.2
descobriu 1 destes mid-sprint e perdeu uma iteração".

Sprint Q.3 brief §2.1.3 elevou este como pre-condição MANDATORY:
**audit ALL cascade sites BEFORE connector code**.

Resultado (verbatim from probe §3.1 pre-code audit):

| Site | File:Line | Filter |
|---|---|---|
| `build_m3_inputs_from_db` | `db_backed_builder.py:282` | `country_code == country` |
| `_load_histories` | `db_backed_builder.py:533` | `country_code == country_code` |
| `classify_m3_compute_mode` | `m3_country_policies.py:117` | `country_code == country` |

**Nenhum site filtra por `survey_name`** — portanto JP Tankan + CA CES
rows populadas com qualquer `survey_name` seriam consumidas pelos 3
sites sem modificação. Classifier cohort (`M3_T1_COUNTRIES`) já incluía
JP + CA desde Sprint O Week 10.

Conclusão: **zero classifier/builder/writer changes esperados**, e
empiricamente confirmado no ship. Lesson #20 #6 evitou:
- refactor mid-sprint do classifier (Q.2 experience)
- scope-creep em cohort modifications
- coupling accidental entre survey_name + classifier logic

**Pattern to codify**: para qualquer sprint que adicione *nova fonte*
a uma cascata existente (N-th BEI linker, N-th survey provider),
o probe doc **obrigatoriamente** inclui a §"cascade site audit" antes
do plano de commits. Sprint Q.4+ adopta sem excepção.

### §4.2 BoC BOS → CES deviation (brief vs ship)

Brief §2.1.2 sugeriu BoC Business Outlook Survey (BOS). Empirical
probe de `/valet/lists/series/json` descobriu que BOS publica
**per-quarter snapshot series** (`BOS_2024Q1_C12_S3` etc.) sem
long-run stable ID. Pivot para **CES** (Canadian Survey of Consumer
Expectations — `CES_C1_SHORT_TERM/MID_TERM/LONG_TERM`) validado no
probe §2.3.

Esta pivot foi o **único** item de brief deviation em todo o sprint.
Detected durante probe, decided at probe time, documented in probe +
retro — não veio à surface mid-implementation. O brief's §4 HALT
language ("BoC Valet API HTTP 5xx sustained → HALT-0 CA") deu
autorização para decidir a fonte exacta durante o probe sem voltar
para the Hugo.

**Lesson stable**: brief-suggested series catalogues são *hypotheses*
validadas no probe. Probe-first discipline shipped here a cleaner
source (stable IDs, long-run history, direct-consumer analogue to
Michigan 1Y US survey) sem sacrificar scope.

### §4.3 BoJ Tankan 5-year bucket — discovery mid-fetch

Empirical finding não antecipado no probe: BoJ archiva Tankan ZIPs
em **5-year bucket directories** (`/gaiyo/2021/` serve 2021-2025,
`/gaiyo/2026/` serve 2026, `/gaiyo/2016/` serve 2016-2020 PDFs).

Descoberto *durante* o primeiro backfill run — 5 releases inserted,
16 failed. Fix: `_bucket_candidates(release_year)` probes year-exact
primeiro então 5-year-bucket floor. Retry policy mudou para **não
retry** em 4xx (só 5xx + transport) para permitir bucket fallback
sem burnar 5× tentativas per miss.

Backfill re-run com connector fix: 21 fetched / 0 failed.

**Lesson marginal**: probe-time `HEAD` check de 1 URL é **insuficiente**
para estatísticas archive buckets com directory convention stateful.
Probe-time deveria ter tentado 2-3 release years representative
spread (current year + 1 year atrás + 3 anos atrás) para triangular.
Não é Lesson #20-worthy — just a +1 tweak to probe checklist.

### §4.4 Tenacity retry + 4xx non-retry

Primeira iteração usava `retry_if_exception_type((httpx.HTTPError,
httpx.TimeoutException))`. `httpx.HTTPError` engloba
`HTTPStatusError` que por sua vez captures 4xx *and* 5xx. Resultado:
cada 404 bucket-miss burnou 5× tentativas + 30s+ jitter wait total —
transformando um fallback de ~100ms em ~2 minutos per miss.

Fix: `retry_if_exception(lambda e: isinstance(e, TransportError) or
(isinstance(e, HTTPStatusError) and response.status_code >= 500))`.

**Pattern portável**: qualquer connector com **path-fallback**
semantics (BoJ buckets, connector cascade) deve usar predicate-based
retry that excludes client errors. Client errors são definitivos;
network errors são transient. Vale check aplicar a patter sweep em
Sprint X+ (ETL audit).

---

## §5 Divergências do brief + decisões

1. **BoC BOS → CES** (§4.2 acima). Deviation justificada, scope
   mantido, acceptance unchanged.
2. **History target brief's "≥60 baseline" → JP 21 / CA 46**.
   Data availability limit. Aceite porque classifier forward-fill
   blanket o window completamente e brief §4 HALT-material explicit
   ("<60 observations → document + accept DEGRADED alternative") —
   ship no nosso caso é FULL, documento accepted.
3. **Pre-2021 JP PDF data** — brief HALT-scope proibia exactly
   isto ("ship CA only, open `CAL-EXPINF-JP-SCRAPE` Week 12+"). Scope
   respeitado; CAL-EXPINF-JP-SCRAPE-PRE2020 opened.
4. **Zero classifier touch** — mais tight do que brief §2.5
   antecipou ("classifier cohort extension if needed"). Lesson #20 #6
   pre-audit confirmou não necessário.
5. **Módulo path `sonar.connectors.boj_tankan` não
   `sonar.connectors.boj_tankan.backfill`** — brief suggested
   nested path; chose module-level backfill para evitar extra
   `__init__.py` package. `python -m sonar.connectors.boj_tankan_backfill`
   is the canonical invocation. No functional difference.

---

## §6 CAL state changes

### Closed

- `CAL-EXPINF-SURVEY-JP-CA` — status=CLOSED (ver calibration-tasks.md
  §CAL-EXPINF-SURVEY-JP-CA entry pós-edit).

### Opened

- `CAL-EXPINF-JP-SCRAPE-PRE2020` — PDF-scrape sprint Week 12+ para
  2014-Q1 → 2020-Q4 Tankan back-history. LOW priority.
- `CAL-EXPINF-CA-BOS-AUGMENT` — BoC Business Outlook Survey
  per-quarter scraping para business-vs-consumer divergence signal.
  LOW priority, Week 12+.

### Unlocked

- **Phase 2 fim-Maio target 75-80% T1 coverage**: hoje ~75% com
  9 FULL / 12 T1. NL + PT + AU adicionais levam a 100% se os
  respectivos blockers lift. NL ainda blocked em curves (CAL-NL-NSS-CURVES);
  PT + AU classificam NOT_IMPLEMENTED por policy (outside cohort por
  design pre-Q.3, pode ser revisto em Sprint Q.4+).
- **Sprint Q.4 candidatura**: promover PT / NL para o cohort
  `M3_T1_COUNTRIES` + probar NL curves. Orthogonal a este sprint.

---

## §7 Next sprint hints (não vinculativo)

- Sprint Q.4 options:
  - **Q.4a** NL promotion: lift NL curves block + extend
    `M3_T1_COUNTRIES`. +1 FULL se lift succeeds.
  - **Q.4b** PT promotion: add PT ao cohort (há SPF row já shipped
    em Q.1), M3 resolve FULL imediato via existing cascade. +1 FULL
    "grátis" sem novo código connector.
- **Pattern sweep**: aplicar retry predicate pattern de §4.4 aos
  outros connectors com path-fallback (boe_yield_curves,
  `ecb_sdw`?). Zero-change audit Sprint.
- **Probe checklist +1**: 2-3 release-year triangulation em archive
  convention probes (§4.3). Document para Sprint X (retry-multi-prefix
  followup) ou futuro ADR-0009 v3.

---

*End retro. 9/12 FULL shipped, Lesson #20 #6 validated from-start,
Phase 2 fim-Maio target within Day-1 reach. Probe discipline ftw.*
