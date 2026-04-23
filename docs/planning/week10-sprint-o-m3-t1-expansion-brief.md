# Sprint O — M3 T1 Expansion (9 Countries Market Expectations)

**Branch**: `sprint-o-m3-t1-expansion`
**Worktree**: `/home/macro/projects/sonar-wt-o-m3-t1-expansion`
**Data**: 2026-04-23 Day 3 late (~19:30 WEST arranque, paralelo com Sprint M)
**Operator**: Hugo Condesa (reviewer) + CC (executor, full autonomy per SESSION_CONTEXT)
**Budget**: 6-8h solo (paralelo with Sprint M → wall-clock ~6-8h)
**ADR-0010 tier scope**: T1 ONLY (9 countries with curves FULL)
**ADR-0009 v2 TE Path 1 probe**: N/A (builder-only, no new country-data fetch — derives from existing `yield_curves_forwards` + `exp_inflation_*`)
**Systemd services affected**: `sonar-daily-monetary-indices.service` (M3 builder path activation per country)
**Parent**: Week 10 Day 4 plano original (promoted to Day 3 late)

---

## §1 Scope (why)

**Gap identificado Week 10 Day 2 close**: M3 (market expectations) shipped apenas 4/16 countries FULL — US/DE/EA/PT. Handoff §3 reporta "L3 indices M3: 4/16". Pattern é **builder-only** (Day 3 schema discovery confirmed): M3 derives from `yield_curves_forwards` + `exp_inflation_*` tables, **no own table**.

**Implication crítica**: com curves T1 a 9/16 FULL (US/DE/EA/GB/JP/CA/IT/ES/FR), **M3 é trivialmente expansível** para todos os 9 — não requer novos connectors, não requer schema migration, apenas builder dispatcher extension + per-country tests.

**Objectivo Sprint O**: M3 builder dispatcher + canonical pattern replicar Sprint F M2 approach (US + EA + 9 non-EA). Target: M3 FULL coverage = 9/16 countries (US/DE/EA/GB/JP/CA/IT/ES/FR). Gap residual 7/16 (PT + NL via Sprint M if PASS; AU/NZ/CH/SE/NO/DK sparse T1 Week 11+).

**Hipótese empírica**:
- `yield_curves_forwards` persisted for 9 T1 countries via `daily_curves.py` (validated Day 2 close + Day 3 T0 backfill).
- `exp_inflation_*` tables (BEI, swaps, survey, derived) populate via existing ECB + FRED + Shiller connectors.
- M3 components per spec: forward inflation + term premium + real rate decomposition via NSS + BEI + inflation swap.
- Bottleneck potencial: `exp_inflation_bei` coverage — só US tem TIPS, UK tem ILGs, EA aggregate tem HICP linkers. DE/IT/ES/FR individual BEI via BTP€i/Bonos indexados/OATi — **pode ter gaps**.

---

## §2 Spec (what)

### 2.1 Pre-flight audit — exp_inflation coverage

CC PRIMEIRO audits `exp_inflation_*` tables para 9 countries antes de builder dispatcher edit:

```bash
sqlite3 data/sonar-dev.db << 'EOF'
-- BEI coverage
SELECT country_code, MAX(date) AS latest, COUNT(*) AS n
FROM exp_inflation_bei
GROUP BY country_code ORDER BY country_code;

-- Swap coverage
SELECT country_code, MAX(date) AS latest, COUNT(*) AS n
FROM exp_inflation_swap
GROUP BY country_code ORDER BY country_code;

-- Survey coverage
SELECT country_code, MAX(date) AS latest, COUNT(*) AS n
FROM exp_inflation_survey
GROUP BY country_code ORDER BY country_code;

-- Derived canonical
SELECT country_code, MAX(date) AS latest, COUNT(*) AS n
FROM exp_inflation_canonical
GROUP BY country_code ORDER BY country_code;

-- Forwards (M3 primary input)
SELECT country_code, MAX(date) AS latest, COUNT(*) AS n
FROM yield_curves_forwards
GROUP BY country_code ORDER BY country_code;
EOF
```

**Decision matrix per country**:

| Country | Forwards | BEI/Swap | Survey | M3 feasibility |
|---|---|---|---|---|
| US | ✓ (Sprint T0 backfill) | ✓ (TIPS) | ✓ (SPF/UMich) | FULL expected |
| DE | ✓ | ?? (Bund linkers) | ✓ (ECB SPF) | FULL or degraded |
| EA | ✓ | ✓ (HICPxT linkers) | ✓ (ECB SPF) | FULL expected |
| GB | ✓ | ✓ (ILGs) | ✓ (BoE SPF) | FULL expected |
| JP | ✓ | ?? (JGB linkers thin) | ?? (BOJ Tankan) | FULL or degraded |
| CA | ✓ | ?? (RRB linkers) | ?? | Check actual data |
| IT | ✓ (Sprint H backfill) | ?? (BTP€i) | ?? | Check |
| ES | ✓ (Sprint H backfill) | ?? (Bonos €i limited) | ?? | Likely degraded |
| FR | ✓ (Sprint I backfill) | ?? (OATi/OATei) | ?? | Check |

Document audit output em `docs/backlog/audits/sprint-o-m3-exp-inflation-audit.md`.

### 2.2 M3 builder canonical pattern

Localize actual M3 builder in `src/sonar/`:

```bash
find src/sonar/ -name "*.py" | xargs grep -l "m3\|M3\|market_expectations\|forward_inflation" 2>/dev/null | head -10
```

Expected locations (verify):
- `src/sonar/pipelines/daily_monetary_indices.py` — dispatcher with M3 branch
- `src/sonar/indices/m3_*.py` or similar — builder logic
- Existing US/DE/EA/PT builders as templates

**Refactor target** — dispatcher-based pattern mirror Sprint F M2:

```python
# Pseudocode — adapt to actual code structure
M3_BUILDERS = {
    "US": build_m3_us,
    "DE": build_m3_de,
    "EA": build_m3_ea,
    "GB": build_m3_gb,     # NEW
    "JP": build_m3_jp,     # NEW
    "CA": build_m3_ca,     # NEW
    "IT": build_m3_it,     # NEW
    "ES": build_m3_es,     # NEW
    "FR": build_m3_fr,     # NEW
    # PT already in (handoff §3 lists M3 4/16 includes PT)
    # NL pending Sprint M success
}

def build_m3(country: str, date: date) -> M3Output | None:
    builder = M3_BUILDERS.get(country)
    if builder is None:
        log.warning("m3_builder.not_implemented", country=country)
        return None
    return builder(date)
```

### 2.3 Per-country builder implementation

For each of GB/JP/CA/IT/ES/FR (6 new builders), implement per spec:

```python
def build_m3_<country>(date: date) -> M3Output:
    # 1. Forwards input
    forwards = load_yield_curves_forwards(country, date)

    # 2. Expected inflation input
    bei = load_exp_inflation_bei(country, date)  # may be None
    swap = load_exp_inflation_swap(country, date)  # may be None
    survey = load_exp_inflation_survey(country, date)  # may be None

    # 3. Canonical inflation expectation
    exp_inf = canonicalize_exp_inflation(bei, swap, survey)

    # 4. Real rate decomposition
    real_rate = nominal_forward - exp_inf

    # 5. Term premium decomposition (per NSS)
    term_premium = compute_term_premium(forwards, exp_inf)

    return M3Output(
        country=country,
        date=date,
        forward_inflation=exp_inf,
        real_rate=real_rate,
        term_premium=term_premium,
        flags=build_flags(bei, swap, survey),  # e.g., "BEI_MISSING", "SURVEY_DEGRADED"
    )
```

**Pattern reuse**: if US or EA builder exists, extract common logic to `build_m3_generic(country, ...)` + country-specific wrapper for flags/sources.

**Degradation handling**: If BEI missing but swap present → use swap. If both missing but survey present → use survey (flag DEGRADED). If all 3 missing → return None + log warning (country listed as M3 degraded/scaffold).

### 2.4 Monetary pipeline dispatcher extension

`src/sonar/pipelines/daily_monetary_indices.py` — extend M3 dispatch:

```python
def _classify_m3_compute_mode(country: str, date: date) -> tuple[str, list[str]]:
    """Mirror Sprint J M4 FCI classifier pattern."""
    flags = []
    if country in M3_BUILDERS:
        # Check input availability
        if has_forwards(country, date) and has_exp_inflation(country, date):
            flags.append("M3_FULL_LIVE")
            return "FULL", flags
        elif has_forwards(country, date):
            flags.append("M3_DEGRADED_EXPINF_MISSING")
            return "DEGRADED", flags
    return "NOT_IMPLEMENTED", flags
```

Status emitted in `monetary_pipeline.m3_compute_mode` log (mirror M2/M4 patterns Sprint F/J).

### 2.5 Regression tests

New tests in `tests/unit/test_pipelines/test_m3_builders.py`:

- `test_m3_us_canonical` — US with full inputs (TIPS BEI + UMich survey) → expected output shape
- `test_m3_degraded_bei_missing` — country with only survey input → flag DEGRADED present
- `test_m3_not_implemented_country` — country not in M3_BUILDERS → returns None, warning logged, no raise
- `test_m3_dispatcher_9_countries` — parametric test over 9 T1 countries, assert each resolves to FULL or DEGRADED (no NOT_IMPLEMENTED)
- `test_m3_async_lifecycle_compatible` — integration with T0.1 ADR-0011 P6 async pattern, single asyncio.run() context

### 2.6 Backfill Apr 21-23

Post-ship, backfill M3 for 9 countries × 3 days = 27 M3 observations:

```bash
for date in 2026-04-21 2026-04-22 2026-04-23; do
  uv run python -m sonar.pipelines.daily_monetary_indices --indices m3 --all-t1 --date $date
done
```

Verify via indices persisted (if M3 persisted to table) OR via log summary (if builder-only):

```bash
sudo journalctl -u sonar-daily-monetary-indices.service --since "-10 min" --no-pager | \
  grep "m3_compute_mode" | tail -30
```
Expected: 9 country × 3 date = ~27 entries, mode=FULL or DEGRADED (non NOT_IMPLEMENTED).

### 2.7 ADR-0009 v2 compliance — no country-data fetch

Sprint O is **builder-only** — zero new TE/connector calls for country-specific data. Pre-flight probe matrix N/A. TE calls only in service of existing connectors already wired (expected inflation swap if any new symbols needed, but likely all already wired via Sprint F/J).

---

## §3 Commits plan

| Commit | Scope | Ficheiros esperados |
|---|---|---|
| **C1** | docs(planning): Sprint O brief + exp_inflation audit | `docs/planning/week10-sprint-o-m3-t1-expansion-brief.md` + `docs/backlog/audits/sprint-o-m3-exp-inflation-audit.md` |
| **C2** | feat(indices): M3 builders GB + JP + CA (3 non-EA T1) | `src/sonar/indices/m3_*.py` or `src/sonar/indices/builders.py` |
| **C3** | feat(indices): M3 builders IT + ES + FR (3 EA periphery T1) | idem |
| **C4** | refactor(pipelines): daily_monetary_indices M3 dispatcher + classifier | `src/sonar/pipelines/daily_monetary_indices.py` |
| **C5** | test: M3 builders regression coverage (9 country parametric) | `tests/unit/test_pipelines/test_m3_builders.py` |
| **C6** | ops: backfill Apr 21-23 + summary verification | logs |
| **C7** | docs: Sprint O retrospective + M3 coverage matrix | `docs/planning/retrospectives/week10-sprint-o-report.md` |

---

## §4 HALT triggers

**HALT-0 (structural input gap)**:
- `yield_curves_forwards` empty or stale for any of 9 T1 countries → HALT. Root cause = upstream curves pipeline issue, triage before M3 expansion.
- `exp_inflation_*` all tables empty for any country → HALT that country, scaffold with NOT_IMPLEMENTED, open CAL for Week 11 exp_inflation expansion.

**HALT-material**:
- M3 builder canonical computation produces nonsense (negative term premium consistently, real rates >50% for major economies) → HALT. Methodology issue, not plumbing issue. Hugo reviews formulas.
- Test failure rate >2 countries → HALT. Pattern generalization gap.

**HALT-scope**:
- Tentação de build PT/NL M3 before Sprint M ships → STOP. PT is existing (handoff M3 4/16 includes PT), NL blocked on Sprint M curves ship. Wait for Sprint M merge.
- Tentação de touch `daily_curves.py` → STOP (Sprint M paralelo).
- Tentação de new connector → STOP. Sprint O is builder-only.

**HALT-security**: standard.

---

## §5 Acceptance

### Primary — builder coverage

```bash
# Verify all 9 builders resolve
uv run python -c "
from sonar.pipelines.daily_monetary_indices import _classify_m3_compute_mode
from datetime import date
d = date(2026, 4, 22)
for c in ['US', 'DE', 'EA', 'GB', 'JP', 'CA', 'IT', 'ES', 'FR']:
    mode, flags = _classify_m3_compute_mode(c, d)
    print(f'{c}: {mode} {flags}')
"
```
Expected: all 9 resolve to FULL or DEGRADED, none NOT_IMPLEMENTED.

### Secondary — systemd verify (ADR-0011 Lesson #7 compliance)

```bash
sudo systemctl start sonar-daily-monetary-indices.service
sleep 180
systemctl is-active sonar-daily-monetary-indices.service   # expect: inactive (exit 0)
sudo journalctl -u sonar-daily-monetary-indices.service --since "-3 min" --no-pager | \
  grep -iE "event loop is closed|connector_aclose_error|country_failed" | wc -l   # expect: 0
sudo journalctl -u sonar-daily-monetary-indices.service --since "-3 min" --no-pager | \
  grep "monetary_pipeline.m3_compute_mode" | wc -l   # expect: >=9 (one per T1 country)
```

### Tertiary — regression tests

```bash
uv run pytest tests/unit/test_pipelines/test_m3_builders.py -v
```
Expected: all pass, coverage delta positive.

### Quaternary — docs + merge hygiene

- Sprint O retrospective shipped with M3 coverage matrix (before/after)
- ADR-0009 v2 untouched (no country-data probe)
- ADR-0010 untouched (tier scope T1 only)
- Pre-commit clean double-run
- sprint_merge.sh Step 10 cleanup

### Final full-system verify (after BOTH Sprint M and O merge)

```bash
echo "=== 3 services status ==="
for svc in sonar-daily-curves sonar-daily-monetary-indices sonar-daily-cost-of-capital; do
  sudo systemctl start $svc.service
  sleep 120
  printf "%-45s %s\n" "$svc" "$(systemctl is-active $svc)"
done

echo "=== T1 coverage ==="
sqlite3 data/sonar-dev.db << 'EOF'
SELECT 'curves' AS layer, COUNT(DISTINCT country_code) AS n FROM yield_curves_spot;
SELECT 'M3 FULL' AS layer, COUNT(*) AS n_builders FROM (SELECT 1);  -- approximation
EOF
```
Expected: 3 services green, curves ≥ 10 countries (if Sprint M PT or NL PASS), M3 builders 9.

---

## §6 Retro scope

Documentar em `docs/planning/retrospectives/week10-sprint-o-report.md`:

1. **exp_inflation audit findings**: per-country data availability matrix, identifying structural gaps (e.g., IT BTP€i sparse → DEGRADED mode expected)
2. **Pattern generalization**: how cleanly Sprint F M2 pattern translated to M3 — anti-patterns encountered?
3. **M3 coverage matrix before/after**: 4/16 → 9/16 (+5pp contribution to T1 completion Week 10)
4. **T0.1 ADR-0011 P6 compatibility**: M3 builders async-lifecycle clean under AsyncExitStack? Pattern holds?
5. **Week 11 implications**: sparse T1 M3 (AU/NZ/CH/SE/NO/DK) feasibility depends on curves ship Week 11 + exp_inflation availability (likely DEGRADED mode for most)
6. **CAL items**: any new exp_inflation per-country gaps discovered open as CAL

---

## §7 Execution notes

- **Audit BEFORE builder code**: C1 audit doc must precede C2/C3 builder implementations. Informs degradation flags.
- **Builder pattern reuse**: extract common logic aggressive — 6 new builders should share canonical core + 6 small wrappers
- **Async lifecycle compliance**: M3 builder path in monetary pipeline MUST use AsyncExitStack (T0.1 ADR-0011 P6). If any new connector call emerges (unlikely), it rides existing infrastructure.
- **Test parametric approach**: rather than 9 separate test functions, use `pytest.mark.parametrize("country", ["US", "DE", ...])` — cleaner, easier extension for PT/NL future.
- **Pre-commit double-run** (Week 10 Lesson #2)
- **sprint_merge.sh Step 10** (Week 10 Lesson #4)
- **CC arranque template** (Week 10 Lesson #5 — apply to this CC session from start)
- **Paralelo awareness**: Sprint M running in parallel touches `te.py` + `daily_curves.py`. Zero overlap with Sprint O files (`indices/*.py`, `daily_monetary_indices.py`, M3 tests). If overlap emerges, HALT-material.

---

## §8 Dependencies & CAL interactions

### Parent sprint
Week 10 Day 4 original plan (promoted Day 3 late)

### CAL items closed by this sprint (if happy path)
- `CAL-M3-T1-EXPANSION` (explicitly listed in handoff §4 Day 3)

### CAL items opened by this sprint (likely, conditional on audit findings)
- `CAL-EXP-INFLATION-BEI-EA-PERIPHERY` — if IT/ES/FR BEI sparse, open for Week 11 national linker connector probe (BTP€i / Bonos €i / OATi)
- `CAL-EXP-INFLATION-SURVEY-JP-CA` — if Tankan / BoC surveys gaps surface
- `CAL-M3-DEGRADED-MODE-UPLIFT` — tracking future uplifts from DEGRADED to FULL as exp_inflation coverage improves

### Sprints blocked by this sprint
- **None** — M3 coverage completion not gating any Week 10 residual sprint

### Sprints unblocked by this sprint
- **L4 MSC cross-country composite** — MSC (Monetary State Composite) requires M1 + M2 + M3 + M4 all FULL per country. Post Sprint O, countries with all 4 FULL: expand from US-only (Week 9 close) to eventually 4-6 countries (pending M4 FCI and M1 effective rates coverage — M4 has 8/17, M1 has 16/16).
- **Sprint M (PT/NL curves)** if shipped → M3 for PT/NL automatically derivable next run, zero extra work for Sprint O to account for it

---

*End of brief. Builder-only, zero data probe. Pattern generalization from Sprint F. Ship pragmatic.*
