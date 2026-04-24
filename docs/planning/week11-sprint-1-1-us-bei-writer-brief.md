# Sprint 1.1 — US BEI Writer (Micro)

**Date**: 2026-04-24 · Week 11 Day 1+ spec-compliant
**Spec reference**: [`docs/specs/overlays/expected-inflation.md`](https://github.com/hugocondesa-debug/sonar-engine/blob/main/docs/specs/overlays/expected-inflation.md) v0.1 §2 hierarchy table + §4 BEI branch
**Budget**: 1-2h CC autonomous work (MICRO sprint)
**Branch**: `sprint-1-1-us-bei-writer`

---

## 1. Problem statement

Sprint 1 shipped L2 EXPINF canonical for 9/10 countries — **US missing** (0 rows). Cause: no `exp_inflation_bei` rows exist for US despite FRED connector having the required series (`T5YIE`, `T10YIE`, `T20YIE`, `T30YIE`, `DFII5`, `DFII10`, `DFII30`).

Per spec §2 hierarchy table, US EXPINF uses **BEI primary for 5Y/10Y/30Y tenors** (+ SURVEY for 1Y/2Y). Sprint Q.2 Day 1 shipped BEI writer but scoped to **GB only** (Sprint name was "CAL-EXPINF-GB-BOE-ILG-SPF" — GB-specific by design). US BEI never shipped.

Sprint 1.1 extends existing BEI writer to US using FRED existing connector. Zero new connectors. Result: US canonical populated → unblocks Sprint 4 (M1 rebuild US spec-compliant) + full 10-country coverage for downstream M3/M4/MSC.

---

## 2. Scope (in / out)

### In scope

1. Extend existing BEI writer (`src/sonar/overlays/expected_inflation/bei.py` or similar — verify location) to handle US path
2. Backfill US BEI for recent 60 bd (matching Sprint 1 canonical date range)
3. Rerun canonical orchestrator for US only (no changes to canonical writer itself)
4. Tier B verification: US canonical row count = 60

### Out of scope

- Other countries BEI extension (DE/FR/IT etc already served by SPF SURVEY path via Sprint 1)
- US SURVEY writer (Philly SPF `EXPINF10YR`, Michigan `MICH`/`MICH5Y`) — defer Sprint 3 connectors batch
- BEI SHORT_SEASONALITY flag for 1Y/2Y US tenors — spec §6 documents but 1Y/2Y US canonical uses SURVEY primary, not BEI, so non-blocking
- IRP haircut configuration — spec §4 step 8.5 optional; defer

---

## 3. Specs referenced (verbatim)

### Spec §2 — US hierarchy (verbatim)

| Country | 1Y/2Y | 5Y/10Y/30Y | 5y5y | Linker connector |
|---|---|---|---|---|
| **US** | SPF/Michigan → BEI | **BEI (`DFII5/10`, `T5YIE/T10YIE/T30YIE`)** | BEI-derived (xval `T5YIFR`) | `fred` |

Spec §2 inputs table (data inputs):

| Input | Source connector | Freq | Used by |
|---|---|---|---|
| `nominal_yield(τ)` decimal | `overlays/nss-curves.yield_curves_spot` | daily | BEI (subtrahend) |
| `linker_real_yield(τ)` decimal | per-country linker connector | daily | BEI direct |

### Spec §4 — BEI formula (verbatim)

> **BEI (`EXP_INF_BEI_v0.1`)** — `BEI(τ) = nominal_yield(τ) − linker_real_yield(τ)`. Linker real é fetched directly (linker tenors alinhados ao grid via linear interp interno quando diferem; NÃO refit NSS aqui).

**Tenors canonical US** per spec §4.6 Expected-inflation overlay table:
- `T5YIE` (5Y breakeven, daily)
- `T10YIE` (10Y)
- `T20YIE` (20Y)
- `T30YIE` (30Y)

OR equivalently compute from:
- `DGS5/DGS10/DGS30` (nominal yields US, existing FRED connector)
- `DFII5/DFII10/DFII30` (TIPS real yields, existing FRED connector)
- `BEI(τ) = DGS(τ) − DFII(τ)` per spec §4 formula

### Spec §4 step 2 — BEI branch pipeline (verbatim)

> 2. **BEI**: se linker disponível → compute `BEI(τ)` para tenors ∈ grid ∩ coverage; derive `5y5y` (compounded); inherit `flags` de `yield_curves_spot`.

### Spec §4 5y5y formula (verbatim)

> **5y5y forward** (compounded, em qualquer method com `5Y` + `10Y`):
> ```
> 5y5y = [ (1 + rate_10Y)^10 / (1 + rate_5Y)^5 ]^(1/5) − 1
> ```
> Forma linear `(10·r10 − 5·r5)/5` do reference é aproximação; **NÃO usar em storage**.

### Spec §8 — exp_inflation_bei storage (verbatim)

```sql
CREATE TABLE exp_inflation_bei (
    /* + common preamble */
    nominal_yields_json       TEXT NOT NULL,            -- {"5Y":0.0415,"10Y":0.0425,...}
    linker_real_yields_json   TEXT NOT NULL,
    bei_tenors_json           TEXT NOT NULL,            -- {"5Y":0.0230,"10Y":0.0242,"5y5y":0.0254}
    linker_connector          TEXT NOT NULL,
    nss_fit_id                TEXT NOT NULL             -- FK to yield_curves_spot.fit_id
);
```

Critical: `nss_fit_id` FK → requires `yield_curves_spot` row for US to exist. Verify before running.

### Spec §7 — US BEI fixtures (verbatim)

- **`us_2024_01_02_bei`**: UST 5/10/30Y + DFII5/10/30 → `BEI_5Y≈0.0230`, `BEI_10Y≈0.0242`, `5y5y≈0.0254` (matches `T5YIFR`); tolerance ±10 bps

---

## 4. Implementation steps (deterministic)

### Step 1 — Audit (10min)

```bash
# Verify FRED connector has required series in catalog
grep -E "DFII|DGS|T5YIE|T10YIE|T20YIE|T30YIE" src/sonar/connectors/fred.py | head -20

# Check existing BEI writer location and structure
find src/sonar/overlays/expected_inflation/ -type f -name "*.py"
grep -l "bei\|BEI" src/sonar/overlays/expected_inflation/*.py 2>/dev/null

# Verify US has yield_curves_spot rows (BEI needs nss_fit_id FK)
sqlite3 data/sonar-dev.db "SELECT COUNT(*), MIN(date), MAX(date) FROM yield_curves_spot WHERE country_code='US';"
# Expected: ≥4 rows per Week 10 history

# Verify US has no BEI rows currently
sqlite3 data/sonar-dev.db "SELECT COUNT(*) FROM exp_inflation_bei WHERE country_code='US';"
# Expected: 0
```

Report findings before proceeding if:
- FRED catalog missing DFII/T*YIE series → need to add to catalog first
- US spot rows < 60 → Sprint 2 tenor backfill dependency; may need to run after Sprint 2
- US BEI rows > 0 → already populated, skip to canonical rerun

### Step 2 — Extend existing BEI writer for US (45min)

Locate existing BEI writer (likely `src/sonar/overlays/expected_inflation/bei.py` per Sprint Q.2 Day 1 pattern). Extend country-dispatch logic to handle US:

```python
# In existing BEI writer, add US connector mapping

US_BEI_SERIES_MAP = {
    # Direct breakeven series (T{N}YIE) — FRED publishes these directly
    "5Y": "T5YIE",
    "10Y": "T10YIE",
    "20Y": "T20YIE",
    "30Y": "T30YIE",
}
# Alternative: compute from DGS{N} − DFII{N}
US_NOMINAL_SERIES_MAP = {"5Y": "DGS5", "10Y": "DGS10", "20Y": "DGS20", "30Y": "DGS30"}
US_TIPS_SERIES_MAP = {"5Y": "DFII5", "10Y": "DFII10", "20Y": "DFII20", "30Y": "DFII30"}


def build_us_bei_row(session, target_date: date) -> ExpInflationBeiRow:
    """Build US BEI row per spec §4 step 2.

    Strategy: prefer direct T{N}YIE breakeven series (FRED publishes these daily).
    Fallback: compute BEI(τ) = DGS(τ) − DFII(τ) from components.
    """
    # Fetch nominal yields from existing FRED connector
    nominal_yields = {}
    tips_yields = {}
    bei_tenors = {}

    for tenor, tyie_series in US_BEI_SERIES_MAP.items():
        try:
            # Direct BEI from FRED T{N}YIE series
            bei_value = fred_connector.fetch_observation(tyie_series, target_date)
            if bei_value is not None:
                bei_tenors[tenor] = bei_value

            # Also persist nominal + real components for audit
            nominal_yields[tenor] = fred_connector.fetch_observation(
                US_NOMINAL_SERIES_MAP[tenor], target_date
            )
            tips_yields[tenor] = fred_connector.fetch_observation(
                US_TIPS_SERIES_MAP[tenor], target_date
            )
        except Exception as e:
            log.debug("bei.us.tenor_skip tenor=%s reason=%s", tenor, e)

    if not bei_tenors:
        raise InsufficientDataError(f"No BEI tenors fetched for US {target_date}")

    # Compute 5y5y compounded per spec §4
    if "5Y" in bei_tenors and "10Y" in bei_tenors:
        r5 = bei_tenors["5Y"]
        r10 = bei_tenors["10Y"]
        bei_tenors["5y5y"] = ((1 + r10) ** 10 / (1 + r5) ** 5) ** (1/5) - 1

    # Lookup nss_fit_id from yield_curves_spot (spec §8 FK requirement)
    spot_row = session.query(NSSYieldCurveSpot).filter_by(
        country_code="US", date=target_date
    ).first()

    if spot_row is None:
        raise InsufficientDataError(
            f"No yield_curves_spot for US {target_date} — nss_fit_id FK required"
        )

    # Confidence: 0.90 if all 4 tenors fresh; −0.10 per missing tenor
    tenor_count = len([t for t in ["5Y", "10Y", "20Y", "30Y"] if t in bei_tenors])
    confidence = 0.90 - 0.10 * (4 - tenor_count)
    confidence = max(0.50, confidence)

    # Cross-val vs T5YIFR if available
    flags = []
    try:
        t5yifr = fred_connector.fetch_observation("T5YIFR", target_date)
        if t5yifr is not None and "5y5y" in bei_tenors:
            xval_bps = abs(bei_tenors["5y5y"] - t5yifr) * 10_000
            if xval_bps > 10:
                flags.append("XVAL_DRIFT")
    except Exception:
        pass

    return ExpInflationBeiRow(
        exp_inf_id=uuid4().hex,
        country_code="US",
        date=target_date,
        methodology_version="EXP_INF_BEI_v0.1",
        nominal_yields_json=json.dumps(nominal_yields),
        linker_real_yields_json=json.dumps(tips_yields),
        bei_tenors_json=json.dumps(bei_tenors),
        linker_connector="fred",
        nss_fit_id=spot_row.fit_id,
        confidence=confidence,
        flags=",".join(sorted(flags)) if flags else None,
        source_connector="fred",
    )
```

Integrate with existing dispatch:

```python
# In bei writer main entry
def build_bei_row(session, country_code: str, target_date: date):
    if country_code == "US":
        return build_us_bei_row(session, target_date)
    elif country_code == "GB":
        return build_gb_bei_row(session, target_date)  # existing Sprint Q.2
    elif country_code in ("DE", "IT", "FR"):
        # Defer: these use SPF SURVEY primary via Sprint 1; BEI for these is Sprint 2+
        raise NotImplementedError(f"BEI for {country_code} not yet shipped")
    else:
        raise NotImplementedError(f"BEI unsupported for {country_code}")
```

### Step 3 — Backfill orchestrator for US (20min)

Add to existing EXPINF backfill OR create micro-entry:

```python
def backfill_us_bei(session, start_date, end_date):
    """Sprint 1.1: US BEI backfill + canonical rerun."""
    success_count = 0
    error_count = 0

    for target_date in business_days(start_date, end_date):
        try:
            bei_row = build_us_bei_row(session, target_date)
            session.merge(bei_row)
            success_count += 1
        except InsufficientDataError as e:
            log.warning("bei.us.skip date=%s reason=%s", target_date, e)
            error_count += 1

    session.commit()
    log.info("bei.us.backfill.done success=%d errors=%d", success_count, error_count)

    # Rerun canonical for US
    from sonar.overlays.expected_inflation.canonical import build_canonical
    for target_date in business_days(start_date, end_date):
        try:
            canonical_row = build_canonical(session, "US", target_date)
            session.merge(canonical_row)
        except InsufficientDataError:
            pass

    session.commit()
```

CLI entrypoint: `sonar backfill expinf-us-bei --start 2026-02-01 --end 2026-04-24`

### Step 4 — Test fixture (20min)

Create `tests/unit/test_overlays/test_expected_inflation_us_bei.py`:

Implement fixture `us_2024_01_02_bei` per spec §7:
- Input: UST 5/10/30Y from FRED + DFII5/10/30 TIPS from FRED
- Expected: `BEI_5Y≈0.0230`, `BEI_10Y≈0.0242`, `5y5y≈0.0254`
- Tolerance: ±10 bps per spec §7
- Assertions:
  - `bei_tenors["5Y"]` within ±0.0010 of 0.0230
  - `bei_tenors["10Y"]` within ±0.0010 of 0.0242
  - `bei_tenors["5y5y"]` within ±0.0010 of 0.0254
  - `linker_connector == "fred"`
  - `nss_fit_id` equals US spot row fit_id for same date

### Step 5 — Tier B verification (5min)

```bash
# Verify US BEI populated
sqlite3 data/sonar-dev.db "SELECT COUNT(*), MIN(date), MAX(date) FROM exp_inflation_bei WHERE country_code='US';"
# Expected: ~60 rows

# Verify US canonical populated after rerun
sqlite3 data/sonar-dev.db "SELECT COUNT(*) FROM exp_inflation_canonical WHERE country_code='US';"
# Expected: ~60 rows (match US BEI count)

# Verify canonical source_method is BEI for 5Y/10Y/30Y US
sqlite3 data/sonar-dev.db "
SELECT date, source_method_per_tenor_json
FROM exp_inflation_canonical
WHERE country_code='US'
ORDER BY date DESC
LIMIT 3;
"
# Expected: {"5Y":"BEI","10Y":"BEI","30Y":"BEI","5y5y":"BEI",...}

# Full 10 countries canonical check
sqlite3 data/sonar-dev.db "SELECT country_code, COUNT(*) FROM exp_inflation_canonical GROUP BY country_code ORDER BY country_code;"
# Expected: 10 countries populated (CA/DE/EA/ES/FR/GB/IT/JP/PT/US)
```

---

## 5. Acceptance criteria

### Must pass
1. ✅ `exp_inflation_bei` US rows ≥ 40 (60 bd target, some gaps acceptable)
2. ✅ `exp_inflation_canonical` US rows ≥ 40 (matches BEI count after canonical rerun)
3. ✅ 10 countries populated in canonical (US + 9 from Sprint 1)
4. ✅ US source_method_per_tenor_json shows BEI for 5Y/10Y/30Y (per spec §2 hierarchy)
5. ✅ Fixture test `us_2024_01_02_bei` passes within ±10 bps tolerance
6. ✅ Pre-commit + pytest green
7. ✅ Merged via sprint_merge.sh

### Out of scope for this sprint
- US 1Y/2Y tenors via SURVEY (Sprint 3 connectors batch)
- Cross-validation vs Damodaran (ERP concern, not EXPINF)

---

## 6. Risks + mitigations

| Risk | Mitigation |
|---|---|
| FRED connector missing T{N}YIE series in catalog | Check `_fred_util.py` or FRED_SERIES_TENORS — if missing, add to catalog first (5min fix) |
| US yield_curves_spot rows <60 (nss_fit_id FK fails) | Run after Sprint 2 (which backfills US spot to 60 bd) OR run in parallel accepting partial US BEI until Sprint 2 completes |
| `T5YIFR` xval drift triggers on most dates | Accept — editorial signal per spec §4 step 8; not a blocker |
| Existing BEI writer structure doesn't support extension | Create new `us_bei.py` module as sibling; wire to dispatch |

---

## 7. CC prompt template

```
Sprint 1.1 — US BEI Writer (Micro)

Read spec: docs/specs/overlays/expected-inflation.md v0.1 §2 (US hierarchy) + §4 (BEI branch) + §7 (us_2024_01_02_bei fixture)
Read brief: docs/sprints/week11-sprint-1-1-us-bei-writer-brief.md

Execute 5 steps per brief §4:
1. Audit FRED catalog has DFII/T*YIE series + US yield_curves_spot rows exist + US BEI currently empty
2. Extend BEI writer for US (build_us_bei_row) — prefer direct T{N}YIE FRED series, fallback DGS-DFII
3. Implement US BEI backfill orchestrator + canonical rerun for US (60 bd recent)
4. Fixture test us_2024_01_02_bei per spec §7 tolerances (±10 bps)
5. Tier B verification (4 SQL queries from brief §4 step 5)

Critical rules:
- Use T{N}YIE direct FRED series primary (DGS-DFII fallback only if T*YIE missing from catalog)
- 5y5y compounded formula per spec §4 (NOT linear)
- nss_fit_id FK to yield_curves_spot.fit_id (spec §8); if US spot row missing for date, skip BEI row
- Inherit upstream flags from yield_curves_spot
- Confidence 0.90 base −0.10 per missing tenor, floor 0.50
- Cross-val T5YIFR emit XVAL_DRIFT flag if >10 bps

Run pytest + pre-commit + sprint_merge.sh.

Tier B verification at end:
  sqlite3 data/sonar-dev.db "SELECT COUNT(*) FROM exp_inflation_bei WHERE country_code='US';"  -- expect ≥40
  sqlite3 data/sonar-dev.db "SELECT COUNT(*) FROM exp_inflation_canonical WHERE country_code='US';"  -- expect ≥40
  sqlite3 data/sonar-dev.db "SELECT country_code, COUNT(*) FROM exp_inflation_canonical GROUP BY country_code ORDER BY country_code;"  -- expect 10 countries

Commit message: "Sprint 1.1: US BEI writer (micro) — fills US canonical gap"
Merge via sprint_merge.sh when green.

START.
```

---

**END BRIEF**
