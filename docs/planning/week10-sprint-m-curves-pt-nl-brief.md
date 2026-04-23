# Sprint M — Curves PT + NL Probe via TE Path 1

**Branch**: `sprint-m-curves-pt-nl`
**Worktree**: `/home/macro/projects/sonar-wt-m-curves-pt-nl`
**Data**: 2026-04-23 Day 3 late (~19:30 WEST arranque)
**Operator**: Hugo Condesa (reviewer) + CC (executor, full autonomy per SESSION_CONTEXT)
**Budget**: 4-6h solo
**ADR-0010 tier scope**: T1 ONLY (PT + NL são T1 — EA periphery members)
**ADR-0009 v2 TE Path 1 probe**: **MANDATORY** — canonical empirical probe-before-scaffold discipline
**Systemd services affected**: `sonar-daily-curves.service` (tuple expansion 9 → 11 countries)
**Parent**: Week 10 Day 4 plano original (promoted to Day 3 late post T0/T0.1/R1 shipping)

---

## §1 Scope (why)

**Gap identificado**: Week 10 Day 2 close ship 9/16 T1 curves (US/DE/EA/GB/JP/CA/IT/ES/FR). Missing PT + NL — EA periphery members com profile data variável. Sprint H (IT) + Sprint I (FR) provaram ADR-0009 v2 canónico: **TE Path 1 primeiro, fallback Path 2/3 apenas se HALT-0**. 3 HALT-0 inversions validaram discipline.

**Objectivo Sprint M**: probe PT + NL via TE Path 1. Se ambos PASS (≥6 daily tenors cada + yield data consistent) → cascade direto mirroring Sprint H IT+ES pattern. Se um ou ambos HALT-0 → scaffold + pattern library extension para Path 2 (BPstat para PT, DNB para NL).

**Hipótese empírica**:
- **PT**: TE coverage provável PASS. PT OT (Obrigações do Tesouro) são major EA sovereign issuance (~€250B outstanding). TE historicamente cobre PT com ~6-8 tenors daily desde 1994.
- **NL**: TE coverage incerto. DSL (Dutch State Loans) menor emissão que BTPs/Bonos/OATs, mas AAA-rated core country. Pode ter coverage thin em tenors curtos.

---

## §2 Spec (what)

### 2.1 Pre-flight probe matrix (ADR-0009 v2 mandatory)

CC PRIMEIRO executa probe matrix **antes** de qualquer code edit:

| Path | Source | Probe method | Success criterion |
|---|---|---|---|
| **1** | Trading Economics (TE) | `curl https://api.tradingeconomics.com/historical/country/portugal/indicator/government%20bond%20{tenor}y` para PT, idem Netherlands NL | ≥6 daily tenors disponíveis, cada com ≥500 data points recent, LastUpdate <7 dias |
| **2** | Banco de Portugal BPstat API (PT) / De Nederlandsche Bank (NL) | `curl https://bpstat.bportugal.pt/data/...` / `curl https://data.dnb.nl/...` | API responsive, schema compatible com `yield_curves_spot` unique constraint |
| **3** | ECB SDW yields (EA aggregated) | Already connected — degraded quality per country | Fallback last resort |

**Probe execution** (CC must run + document):

```bash
# PT TE probe
for tenor in 1 2 3 5 7 10 15 20 30; do
  curl -s "https://api.tradingeconomics.com/historical/country/portugal/indicator/government%20bond%20${tenor}y?c=${TE_API_KEY}&format=json&d1=2024-01-01&d2=2026-04-22" | \
    jq "length" | awk -v t=$tenor '{print "PT "t"Y: "$1" points"}'
done

# NL TE probe (idem Netherlands)
for tenor in 1 2 3 5 7 10 15 20 30; do
  curl -s "https://api.tradingeconomics.com/historical/country/netherlands/indicator/government%20bond%20${tenor}y?c=${TE_API_KEY}&format=json&d1=2024-01-01&d2=2026-04-22" | \
    jq "length" | awk -v t=$tenor '{print "NL "t"Y: "$1" points"}'
done
```

**Document probe output** em `docs/backlog/probe-results/sprint-m-pt-nl-te-probe.md` (new dir) com raw data + decision.

### 2.2 TE quota pre-check (Lesson #8 proactive mitigation)

Antes de iniciar probe, verify quota via TE dashboard ou headers:

```bash
# Headers check
curl -s -I "https://api.tradingeconomics.com/markets/historical/country/portugal:rating?c=${TE_API_KEY}" 2>&1 | grep -iE "x-ratelimit|x-request-remaining" || echo "No quota headers visible"
```

Se quota <80% remaining monthly (ou <20% daily burst), **HALT-pre-flight** e report. Sprint M re-schedule Day 4.

**Baseline expected**: 23.32% / 5000 consumption April per Day 3 dashboard screenshot. Sprint M provável consumption: ~40-60 calls (probe + backfill both countries). Zero risk exhaust.

### 2.3 TE symbols table (if Path 1 PASS)

Extender `src/sonar/connectors/te.py` `TE_YIELD_CURVE_SYMBOLS` dict with PT + NL:

```python
TE_YIELD_CURVE_SYMBOLS = {
    ...existing...,
    "PT": {
        "1Y": "GSPT1YR:IND",  # Portugal 1Y
        "2Y": "GSPT2YR:IND",
        "5Y": "GSPT5YR:IND",
        "10Y": "GSPT10YR:IND",
        "30Y": "GSPT30YR:IND",
        # Add all tenors confirmed ≥500 points recent
    },
    "NL": {
        "1Y": "GNTH1YR:IND",  # Netherlands 1Y (confirm exact symbol via TE probe)
        "10Y": "GNTH10YR:IND",
        # Sub-set per probe results
    },
}
```

**Exact symbols**: CC must verify via TE probe (symbol name convention pode variar — Italy uses `GBTPGR10:IND`, US uses `GT10:IND`). Não assumir pattern — confirm each.

### 2.4 daily_curves.py tuple expansion

`src/sonar/pipelines/daily_curves.py` — extend T1 tuple from 9 → 11 countries:

```python
T1_COUNTRIES = ("US", "DE", "EA", "GB", "JP", "CA", "IT", "ES", "FR", "PT", "NL")
```

Verificar todos os downstream consumers (cost_of_capital, M3 builder-if-exists, L4 MSC) — extend esses para 11 também.

### 2.5 Dispatcher per-country logic

Se PT ou NL HALT-0 individualmente (Path 1 insufficient data), dispatcher **skip gracefully** com log:

```python
if country not in TE_YIELD_CURVE_SYMBOLS:
    log.warning("daily_curves.country_not_configured", country=country, reason="TE symbols missing")
    continue  # skip, não raise
```

ADR-0011 Principle 2 (per-country isolation) já shipped — reuse.

### 2.6 Backfill Apr 21-23 para PT + NL (if Path 1 PASS)

Post-code ship, backfill manual:

```bash
for date in 2026-04-21 2026-04-22 2026-04-23; do
  uv run python -m sonar.pipelines.daily_curves --countries PT NL --date $date
done
```

Verify:
```bash
sqlite3 data/sonar-dev.db "SELECT country_code, MAX(date) AS latest, COUNT(*) AS n FROM yield_curves_spot WHERE country_code IN ('PT','NL') GROUP BY country_code;"
```
Expected: PT + NL com latest=2026-04-23 se PASS. Se HALT-0 mid-probe, expected absent (OK).

### 2.7 ADR-0009 addendum (se inversion encontrado)

Se **um dos dois** HALT-0 Path 1, adiciona addendum a `docs/adr/ADR-0009-national-cb-connectors-ea-periphery.md`:
- 4th HALT-0 inversion documented (PT or NL whichever failed)
- Empirical observation on TE coverage of EA core vs periphery sovereigns
- CAL opened for Path 2 probe (BPstat ou DNB)

Se **ambos** PASS, ADR-0009 v2 untouched (desired outcome — canonical reinforced).

---

## §3 Commits plan

| Commit | Scope | Ficheiros esperados |
|---|---|---|
| **C1** | docs(planning): Sprint M brief + pre-flight probe matrix | `docs/planning/week10-sprint-m-curves-pt-nl-brief.md` (staged via sprint_setup.sh Lesson #1 fix) |
| **C2** | docs(probes): TE Path 1 probe results PT + NL (documentation BEFORE code) | `docs/backlog/probe-results/sprint-m-pt-nl-te-probe.md` |
| **C3** | feat(connectors): te.py PT + NL yield curve symbols | `src/sonar/connectors/te.py` (CONDITIONAL — only if probe PASS) |
| **C4** | feat(pipelines): daily_curves T1 tuple 9 → 11 (PT + NL) | `src/sonar/pipelines/daily_curves.py` (CONDITIONAL) |
| **C5** | test: regression coverage PT + NL cascade | `tests/unit/test_pipelines/test_daily_curves.py` (CONDITIONAL) |
| **C6** | ops: backfill Apr 21-23 PT + NL verification | logs + summary (CONDITIONAL) |
| **C7** | docs: Sprint M retrospective + ADR-0009 v2 addendum (if inversion) | `docs/planning/retrospectives/week10-sprint-m-report.md` + eventual ADR-0009 addendum |

**If HALT-0 both**: Commits C3-C6 skipped, C7 retro documents the HALT decision + opens CAL-CURVES-PT-BPSTAT-PROBE + CAL-CURVES-NL-DNB-PROBE Path 2 for Week 11.

---

## §4 HALT triggers

**HALT-0 (structural — expected outcome for EA periphery per ADR-0009 v2)**:
- PT TE probe: <6 tenors daily OR <500 points per tenor OR LastUpdate >7 days stale → HALT-0 PT
- NL TE probe: idem → HALT-0 NL
- Either or both: document in probe results doc, skip that country's Commits C3-C6, continue with other country if one PASS
- Both HALT-0: full sprint HALT-0, retro only (C7), CALs opened for Week 11

**HALT-pre-flight**:
- TE quota <80% monthly remaining at probe time → HALT immediate, defer Day 4 or Week 11
- TE HTTP 403 sustained >5 min on valid probe URL → HALT, escalate manually to Hugo

**HALT-material**:
- TE probe PASS but downstream NSS curve fitting fails (rmse_bps > threshold, confidence < 0.5) for PT or NL → HALT that country, investigate data quality before ship
- DB unique constraint violation on backfill (`yield_curves_spot.uq_ycs_country_date_method`) → ADR-0011 Principle 1 should handle via skip, but flag if not

**HALT-scope**:
- Qualquer tentação de shippar GB M4 upgrade ou outras non-PT/non-NL work → STOP (scope lock strict PT + NL only)
- Tentação de tocar M3 builder (Sprint O paralelo) → STOP, zero overlap tolerated

**HALT-security**: standard.

---

## §5 Acceptance

### Primary — if both PASS (happy path)

**DB coverage**:
```bash
sqlite3 data/sonar-dev.db "SELECT country_code, MAX(date) AS latest, COUNT(*) AS n FROM yield_curves_spot WHERE country_code IN ('PT','NL') GROUP BY country_code;"
```
Expected: PT + NL both present with `latest=2026-04-23`, `n>=3` (Apr 21-23 backfilled).

**Systemd verify** (ADR-0011 discipline, Lesson #7 canonical):
```bash
sudo systemctl start sonar-daily-curves.service
sleep 120
systemctl is-active sonar-daily-curves.service   # expect: inactive (exit 0)
sudo journalctl -u sonar-daily-curves.service --since "-3 min" --no-pager | \
  grep "daily_curves.summary"
```
Expected: summary shows 11/11 countries processed (persist or skip_existing), n_failed=0.

**Regression tests**:
```bash
uv run pytest tests/unit/test_pipelines/test_daily_curves.py -v
```
Expected: all pass including new PT + NL coverage tests.

### Partial PASS (one country PASS, one HALT-0)

- PASS country: all primary criteria above met for that country
- HALT-0 country: probe results doc complete + CAL opened + ADR-0009 addendum shipped

### Full HALT-0 (both)

- Probe results doc complete with raw data
- 2 CALs opened (`CAL-CURVES-PT-BPSTAT-PROBE`, `CAL-CURVES-NL-DNB-PROBE`)
- ADR-0009 addendum shipped (4th + 5th inversion documented)
- Retro shipped

### Tertiary (all scenarios)

- Pre-commit clean double-run
- sprint_merge.sh Step 10 cleanup (worktree + tmux)
- Brief format v3.1 compliance (header metadata complete)

---

## §6 Retro scope

Documentar em `docs/planning/retrospectives/week10-sprint-m-report.md`:

1. **Probe results**: raw TE response counts per tenor per country
2. **Decision matrix**: PASS/HALT per country with criteria satisfied or not
3. **Pattern reusability**: if both PASS, confirm Sprint H cascade pattern replicable (Italy + Spain). If inversion, document which path worked.
4. **ADR-0009 v2 status**: unchanged (both PASS = canonical holds) OR 4th/5th inversion (addendum)
5. **Week 10 close implications**: T1 curves completion % delta (9/16 → 10/16 or 11/16)
6. **Week 11 implications**: CALs for Path 2 probes if HALT-0, or sparse T1 probes next (AU/NZ/CH/SE/NO/DK) if Sprint M clean

---

## §7 Execution notes

- **Probe BEFORE code**: C2 (probe results doc) must precede C3 (te.py edit). Non-negotiable ADR-0009 v2 discipline.
- **TE symbols exact**: verify each symbol via probe response `HistoricalDataSymbol` field, não assumir convention
- **Per-country independence**: PT PASS + NL HALT-0 is legitimate partial ship — don't bundle into single HALT
- **Backfill idempotency**: ADR-0011 Principle 1 should handle duplicate on retry; verify `daily_curves.skip_existing` fires if re-run
- **Pre-commit double-run** (Week 10 Lesson #2)
- **sprint_merge.sh Step 10** cleanup (Week 10 Lesson #4)
- **CC arranque template** `docs/templates/cc-arranque-prompt.md` (Week 10 Lesson #5)
- **Paralelo awareness**: Sprint O running in parallel touches `daily_monetary_indices.py` + M3 builder. Zero overlap with Sprint M files. If conflicts emerge, HALT-material and coordinate with Hugo.

---

## §8 Dependencies & CAL interactions

### Parent sprint
Week 10 Day 4 original plan (promoted to Day 3 late)

### CAL items closed by this sprint (if both PASS)
- `CAL-CURVES-PT-BPSTAT` (closed as TE Path 1 resolved need for BPstat fallback)
- `CAL-CURVES-NL-DNB` (closed as TE Path 1 resolved need for DNB fallback)

### CAL items opened by this sprint (if HALT-0)
- `CAL-CURVES-PT-BPSTAT-PROBE` (Path 2 probe Week 11)
- `CAL-CURVES-NL-DNB-PROBE` (Path 2 probe Week 11)

### Sprints blocked by this sprint
- **None immediately** — curves PT/NL completion not gating any Week 10 residual sprint

### Sprints unblocked by this sprint (if PASS)
- Any future sprint consuming 11-country curves aggregate (L4 MSC cross-country for PT/NL coverage, future CRP+ERP expansion)
- M3 Sprint O downstream: if PT/NL curves persist forwards, M3 builder-only pattern trivially includes them (zero Sprint O scope change)

---

*End of brief. Probe-before-scaffold discipline. Ship empirical.*
