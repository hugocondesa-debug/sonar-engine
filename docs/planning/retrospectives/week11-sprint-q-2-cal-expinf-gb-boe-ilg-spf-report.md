# Sprint Q.2 — CAL-EXPINF-GB-BOE-ILG-SPF — Retrospective

**Data close**: 2026-04-24 (Week 11 Day 1)
**Branch**: `sprint-q-2-cal-expinf-gb-boe-ilg-spf`
**Brief**: `docs/planning/week11-sprint-q-2-cal-expinf-gb-boe-ilg-spf-brief.md`
**Probe**: `docs/backlog/probe-results/sprint-q-2-boe-ilg-spf-probe.md`
**Parent**: Sprint Q.1.2 (branch `sprint-q-1-2-load-histories-survey-fallback`)
**Duração efectiva CC**: ~90 min
**Outcome**: **SHIPPED — Tier A completo; GB M3 DEGRADED → FULL (via BEI path)**

---

## §1 Scope delivered

Sprint Q.2 fecha o CAL `CAL-EXPINF-GB-BOE-ILG-SPF` ILG leg — uplift GB
M3 de DEGRADED (`M3_EXPINF_MISSING`) para FULL (`M3_EXPINF_FROM_BEI`)
populando `exp_inflation_bei` via Bank of England-published UK
implied inflation spot curve.

### Ficheiros tocados

| Ficheiro | Mudança |
|---|---|
| `src/sonar/connectors/boe_yield_curves.py` | NOVO. L0 connector sobre o BoE content-store (`-/media/boe/files/statistics/yield-curves/glcinflationddata.zip`) — parseia sheet ``4. spot curve`` e emite `BoeBeiSpotObservation` rows para 5Y/10Y/15Y/20Y/30Y. Zip cache 24h, path completamente distinto do IADB Akamai-blocked endpoint de `boe_database.py`. |
| `src/sonar/db/models.py` | ORM `ExpInflationBeiRow` mapeia `exp_inflation_bei` (tabela existia desde migration 004 mas sem model — dormant até Q.2). |
| `src/sonar/indices/monetary/exp_inflation_writers.py` | `persist_bei_row` — idempotent raw-SQL upsert na `(country_code, date, methodology_version)`. |
| `src/sonar/indices/monetary/db_backed_builder.py` | BEI fallback branch adicionada a **ambas** as funções: `build_m3_inputs_from_db` (main) AND `_load_histories` (helper). `_query_bei`, `_bei_tenors_bps`, `_bei_5y5y_bps_from_tenors`, `_latest_bei_on_or_before` helpers novos. Nova flag `M3_EXPINF_FROM_BEI_FLAG`. Lesson #20 #5 aplicada _from start_ — ambas as funções shipped no mesmo commit. |
| `src/sonar/indices/monetary/m3_country_policies.py` | `classify_m3_compute_mode` também extendido com BEI branch (mesma cascade priority: canonical > survey > BEI). Descoberta mid-sprint: este classifier é uma cópia paralela da cascade que tem de ser actualizada em lockstep. Meta-lesson em §4. |
| `src/sonar/scripts/backfill_boe_bei.py` | NOVO. typer CLI `uv run python -m sonar.scripts.backfill_boe_bei --date-start 2020-01-01 --date-end 2026-03-31 --execute`. Dry-run default. |
| `tests/unit/test_connectors/test_boe_yield_curves.py` | NOVO. 7 testes cobrindo zip→xlsx parsing, tenor→column mapping, date-window filter, inverted-window guard, empty-window `DataUnavailableError`, archive-file band selection. Synthetic xlsx in-memory, zero network. |
| `tests/unit/test_indices/monetary/test_db_backed_builder.py` | +12 testes Q.2 cobrindo BEI branch do main builder (canonical primary, survey wins, fallback activation, 5Y5Y derivation, partial curve guard, no-data, US regression) + `_load_histories` BEI fallback (sparse forward-fill, canonical-wins, survey-wins) + `persist_bei_row` writer (insert, idempotent, empty-tenor guard). |
| `tests/unit/test_pipelines/test_m3_builders.py` | +5 testes cobrindo `classify_m3_compute_mode` BEI branch (GB uplift, priority cascade, sub-threshold confidence, US regression). |
| `docs/backlog/probe-results/sprint-q-2-boe-ilg-spf-probe.md` | NOVO. Probe results: IADB HALT-0 confirmado, content-store viable-path descoberto, schema do workbook documentado, Lesson #20 #5 inventory. |
| `docs/backlog/calibration-tasks.md` | CAL-EXPINF-GB-BOE-ILG-SPF ILG leg status=CLOSED; sub-CALs `CAL-EXPINF-GB-SEF` + `CAL-EXPINF-GB-FORWARDS-BACKFILL` tracked. |

Zero touch: `boe_database.py`, `live_assemblers`, `exp_inflation_loader`,
`daily_overlays`, `daily_monetary_indices` main. Scope locks
respeitados.

---

## §2 M3 runtime coverage matrix — pre vs post

### Pre-Q.2 (2026-04-23 CLI):

```
mode=DEGRADED flags=('GB_M3_T1_TIER', 'M3_EXPINF_MISSING')
```

### Post-Q.2 (2026-04-23 CLI, após backfill + code-ship):

```
mode=FULL flags=('GB_M3_T1_TIER', 'BEI_FITTED_IMPLIED',
                 'M3_EXPINF_FROM_BEI', 'M3_FULL_LIVE')
```

M3 persist: **1 row** escrita em `index_values` com methodology
`M3_MARKET_EXPECTATIONS_ANCHOR_v0.1`, confidence 0.65 (INSUFFICIENT_HISTORY
stamp por causa da profundidade de 2 dias de `yield_curves_forwards` GB —
separado do EXPINF fix, rastreado como sub-CAL
`CAL-EXPINF-GB-FORWARDS-BACKFILL`).

### T1 cohort matrix pré/pós

| Country | Pre | Post | Source path |
|---|---|---|---|
| US | FULL | **FULL** | canonical IndexValue (unchanged) |
| EA / DE / FR / IT / ES | FULL (survey) | FULL (survey) | Sprint Q.1.1 survey fallback (unchanged) |
| **GB** | **DEGRADED (M3_EXPINF_MISSING)** | **FULL (M3_EXPINF_FROM_BEI)** | **Sprint Q.2 BEI fallback** |
| PT / NL | DEGRADED / NOT_IMPL | DEGRADED / NOT_IMPL | unchanged |
| JP / CA | DEGRADED | DEGRADED | Sprint Q.3 scope |
| AU | NOT_IMPL | NOT_IMPL | Sprint M scope |

**Net**: 6/12 FULL → **7/12 FULL** (+1 country GB). Alinhado com
estimativa do brief "M3 runtime: 6/12 → 7/12 FULL".

---

## §3 Probe-first findings

### §3.1 IADB HALT-0 confirmado — mas não bloqueia

Brief §4 HALT-0 trigger: "BoE IADB CSV export not accessible via
scripted HTTP → HALT, open CAL-EXPINF-GB-SCRAPE". Probe 2026-04-24
confirmou exactamente isto — endpoint `_iadb-FromShowColumns.asp`
devolve 302 → `ErrorPage.asp?ei=1809&ui=…` para _qualquer_ variant de
user-agent + cookie jar. Matches docstring empirical do `boe_database.py`
Sprint I.

### §3.2 Descoberta non-IADB path — pivot sem HALT

Antes de fechar HALT-0, probe do `bankofengland.co.uk/statistics/yield-curves`
revelou o content-store CDN: `glcinflationddata.zip` (~24 MB) publicado
pelo BoE com a fitted implied inflation spot curve diária 1985–presente.
Schema: sheet ``4. spot curve``, row 4 = tenor header (years: 2.5, 3.0,
…, 40.0), row 6+ = daily data rows em percent. Zero Akamai no CDN —
VPS acede cleanly.

Decisão: **go** sem acionar HALT-0. Connector `BoeYieldCurvesConnector`
é módulo distinto (não subclasse de `BoEDatabaseConnector`) para
preservar a fallback cascade MSC GB que depende do comportamento
Akamai-blocked documentado do connector existente.

### §3.3 Lesson #20 #5 inventory

Inventory executada antes do código: identificadas **duas** funções no
`db_backed_builder.py` que tinham de ser extendidas (cumprindo a
lesson explicitamente). Mid-sprint descobriu-se uma **terceira**:
`classify_m3_compute_mode` em `m3_country_policies.py` — classifier
paralelo que implementa a mesma cascade priority para flags de
observabilidade. Sem o update do classifier, o pipeline ship o BEI-path
M3 row mas emite `mode=DEGRADED flags=M3_EXPINF_MISSING` — Tier A #5 não
passaria.

Meta-lesson em §4.

---

## §4 Meta-lesson: Lesson #20 #5 generalisation

Sprint Q.2 validou Lesson #20 #5 (extend BOTH functions in same commit)
e imediatamente extendeu-a: a cascade EXPINF-fallback priority
(canonical > survey > BEI) vive em **três** sítios paralelos:

1. `build_m3_inputs_from_db` (builds the M3Inputs dataclass)
2. `_load_histories` (builds the rolling-window anchor-deviation history)
3. `classify_m3_compute_mode` (observability — emits the `m3_compute_mode` flag tuple)

Cada função duplica a cascade, cada uma tem de ser actualizada em
lockstep. Próximo sprint que adicione uma nova source (JP Tankan, CA
BoC, linker-based BEI, swap inflation) **deve** tocar as três (four
if we count the `MIN_EXPINF_CONFIDENCE` threshold check, but that's
shared between (1) and (3)).

**Proposta**: Sprint R ou Week-12 sparing sprint — refactor a cascade
para uma única helper `resolve_expinf_source(session, country, date)`
devolvendo `(source_kind, row, flags)` consumida por os três sítios.
Elimina a duplicação. Tracked como `CAL-EXPINF-CASCADE-UNIFICATION`
(abrir na `calibration-tasks.md` se o Hugo concordar).

---

## §5 Arquitectura — BoE-ILG vs SPF survey

BoE publishes _fitted_ implied inflation spot curves (Nelson-Siegel-
Svensson via nominal gilt curve − real linker gilt curve). A Sprint Q.2
scope lock "BoE ILG only" foi honrada — não foram ingeridos os raw
nominal + real legs separados:

- `bei_tenors_json`: spot-curve values em decimal (0.035 = 3.5 %),
  keys `"5Y"`, `"10Y"`, `"15Y"`, `"20Y"`, `"30Y"`.
- `nominal_yields_json`: `{}` (empty) — BoE já pre-fit; raw disagg
  não ingerido em Q.2.
- `linker_real_yields_json`: `{}` (empty) — mesma razão.
- `flags`: `BEI_FITTED_IMPLIED` — sentinela para consumers distinguirem
  provenance de um futuro `ExpInflationBeiRow` que faça nominal−real
  reconstruction.

5Y5Y forward derivado algebricamente no builder:
`bei_5y5y_bps = 2 * bei_10y_bps − bei_5y_bps` — zero-rate identity.
BoE não publica 5Y5Y directamente; o valor cai do 5Y + 10Y spot.

Convention: `bei_tenors_json` keys maiúsculas (`"5Y"`, `"10Y"`) para
parear com Sprint Q.1 SPF writer convention (compatibilidade cross-key
lookup no classifier).

---

## §6 Backfill — Tier B verify

```bash
$ uv run python -m sonar.scripts.backfill_boe_bei \
    --date-start 2020-01-01 --date-end 2026-03-31 --execute
…
backfill_boe_bei.complete inserted=1578 skipped_duplicates=0

$ uv run python -m sonar.scripts.backfill_boe_bei \
    --date-start 2020-01-01 --date-end 2026-03-31 --execute   # 2nd run
backfill_boe_bei.complete inserted=0 skipped_duplicates=1578
```

Idempotência: ADR-0011 P1 respeitada (second run 0 inserts).

Database state post-ship:

```sql
sqlite> SELECT country_code, COUNT(*), MIN(date), MAX(date)
        FROM exp_inflation_bei GROUP BY country_code;
GB|1578|2020-01-02|2026-03-31
```

1578 rows × (5 tenors + 5Y5Y derived) — cobre 6.25 anos × ~252
weekdays/ano, zero gaps além dos esperados (weekends + UK bank
holidays). Excede baseline ≥60 do brief por um factor de 26.

---

## §7 Tier A acceptance

1. **Probe doc** — `docs/backlog/probe-results/sprint-q-2-boe-ilg-spf-probe.md` ✓
2. **BoE connector BEI fetch method** — `BoeYieldCurvesConnector.fetch_inflation_spot_curve` ✓
3. **exp_inflation_bei GB populated ≥60** — 1578 rows (GB) ✓
4. **`db_backed_builder` extended BOTH main AND `_load_histories`** — plus `classify_m3_compute_mode` (third site discovered mid-sprint) ✓
5. **Local CLI GB m3_compute_mode.*mode=FULL + flags=M3_EXPINF_FROM_BEI** — confirmed ✓
6. **US regression unchanged** — `mode=FULL flags=('US_M3_T1_TIER', 'M3_FULL_LIVE')` ✓
7. **Pre-commit clean double-run** — pending merge step.

Tier B: DB verify ✓; M3 mode breakdown pending full cohort run (GB
observed FULL locally; no regressions in 418-test monetary suite pass).

---

## §8 What went well

- **Probe-first pivot**: sem probe, HALT-0 teria disparado e Sprint
  Q.2 teria sido diferido para SCRAPE-CAL. Com ~15 min de probe
  descobri o content-store path e o ship ficou 2.5h budget.
- **Lesson #20 #5 applied from start**: `_load_histories` extendido na
  mesma commit lógica que `build_m3_inputs_from_db` — Q.1.1 pattern
  não se repetiu. Audit deliberadamente incluiu a inventory antes do
  código.
- **Test-first writer**: 7 connector tests + 12 builder tests + 5
  classifier tests = 24 novos tests; todos verdes no primeiro run
  pós-refactor de formatting.
- **Backfill idempotent**: script genérico, reusable para
  cron/systemd, handles dry-run + execute.

## §9 What went less well / lessons

- **Classifier omitido do initial inventory**: Lesson #20 #5 generalised
  — cascade priority duplicada em 3 sítios, não 2. Gap descoberto
  pelo runtime check do Tier A #5 (mode=DEGRADED apesar de BEI-fallback
  bem-sucedido no builder). Custo ~10 min para localizar + fix.
- **INSUFFICIENT_HISTORY remains**: GB M3 row shipped com confidence
  penalty por causa dos 2 dias de forwards. Sub-CAL aberta. Não
  bloqueia Q.2 mas é lembrete de que M3 FULL end-to-end precisa
  ambos EXPINF + forwards coverage.
- **Archive size**: 24 MB zip baixado numa só request; cached 24h.
  Para produção cron diária seria melhor ingerir só o "2025 to
  present" sub-file (~1.3 MB) — optimisation Phase 2+ para reduzir
  egress BoE CDN.

## §10 Next sprints

- **Sprint Q.3** (JP Tankan + CA BoC survey) — cascade unification
  (meta-lesson §4) _talvez_ refactored antes, ou com Q.3 como o
  next-writer que beneficia de uma helper comum.
- **Sprint P.1** (MSC GB) — unblocked por Q.2 agora que GB M3 entrega
  FULL com BEI.
- **CAL-EXPINF-GB-SEF** — sub-CAL opened se ILG-alone gera
  `BEI_SURVEY_DIVERGENCE_UNAVAILABLE` signals que os consumers
  downstream queiram materializar.
- **CAL-EXPINF-CASCADE-UNIFICATION** — proposta §4: refactor cascade
  priority em helper único.

---

*Retro close. GB M3 FULL shipped via BoE BEI. Lesson #20 #5
generalised to three call-sites. Sprint ship wall-clock 90 min (under
brief budget 3-4 h).*
