# Sprint P.2 — GB Yield Curves Forwards Backfill (Ops)

**Branch**: `sprint-p-2-gb-forwards-backfill`
**Worktree**: `/home/macro/projects/sonar-wt-p-2-gb-forwards-backfill`
**Data**: Week 11 Day 1 — arranque ~17:15 WEST (paralelo com Q.4b)
**Budget**: 30-60min
**Priority**: P2 — M3 GB quality uplift (stamp out INSUFFICIENT_HISTORY)
**Parent**: Sprint Q.2 retro sub-CAL `CAL-EXPINF-GB-FORWARDS-BACKFILL`

---

## §1 Scope

Sprint Q.2 retro identified:
> *"GB gilt curve only has 2 days in DB — separate ops concern — stamps INSUFFICIENT_HISTORY on the M3 row."*

**Current state**: GB `yield_curves_forwards` has ~2 rows. `_load_histories` produces short `nominal_5y5y_history_bps` for GB → M3 stamps `INSUFFICIENT_HISTORY` flag despite `mode=FULL`.

**Objectivo**: backfill GB gilt forwards 2020-01 → 2026-04. Quality uplift, not runtime mode change.

### Expected impact
- GB M3 **quality flag** removed (stamp `INSUFFICIENT_HISTORY` disappears)
- Z-score baseline robust (≥60 observations vs current 2)
- No M3 mode change (GB already FULL via BEI)
- No T1 coverage delta (coverage measures mode, not quality flags)

---

## §2 Spec

### 2.1 Pre-flight
```bash
cd /home/macro/projects/sonar-wt-p-2-gb-forwards-backfill

# Current GB forwards state
sqlite3 data/sonar-dev.db \
  "SELECT country_code, COUNT(*), MIN(date), MAX(date)
   FROM yield_curves_forwards
   WHERE country_code='GB';"
# Expected: 2 rows only

# Check existing curves pipeline for GB
grep -rn "GB\|UK\|gilt\|boe" src/sonar/pipelines/daily_curves.py | head -10

# Verify BoE yield-curves connector (Sprint Q.2 shipped)
grep "fetch_nominal\|fetch_spot\|BoeYieldCurvesConnector" src/sonar/connectors/boe_yield_curves.py | head -10
```

### 2.2 Discovery — does connector support historical fetch?

Sprint Q.2 shipped `BoeYieldCurvesConnector` for BEI. Verify it also fetches **nominal** yield curves (for `forwards_json` population), not just BEI.

```bash
grep -rn "fetch\|nominal\|real\|glcnom\|glcreal" src/sonar/connectors/boe_yield_curves.py | head -20
```

Paths possíveis:
- **Path A (best case)**: Q.2 connector já fetches nominal — only orchestration needed (loop dates → persist)
- **Path B**: Connector fetches BEI only — extend to fetch nominal OR use BoE `glcnominalddata.zip` CDN
- **Path C HALT**: BoE nominal yields not in content-store → scope expand materially

Document Path in probe (§2.1 output).

### 2.3 Backfill script

**File**: `scripts/ops/backfill_gb_forwards.py` (new OR extend existing pipeline CLI)

Pseudocode:
```python
import asyncio
from datetime import date, timedelta
from sonar.connectors.boe_yield_curves import BoeYieldCurvesConnector
from sonar.indices.market_state.yield_curves_nss import fit_nss
from sonar.db import session_scope

async def backfill_gb_forwards(date_start: date, date_end: date):
    async with BoeYieldCurvesConnector() as conn:
        data = await conn.fetch_nominal_history(date_start, date_end)  # Path A
        # OR: iterate daily, fetch CSV per date (Path B)

    with session_scope() as session:
        for obs_date, curve_data in data:
            # Fit NSS, compute forwards (5y5y, etc)
            nss_params = fit_nss(curve_data)
            forwards_json = compute_forwards(nss_params)

            # Persist via existing NSSYieldCurveForwards model
            persist_forwards_row(session, "GB", obs_date, forwards_json, ...)
            session.commit()  # or batch commit
```

**Idempotency** (ADR-0011 P1): existing row same (country, date) → skip write. Existing writer infrastructure should handle this.

### 2.4 Execution
```bash
uv run python scripts/ops/backfill_gb_forwards.py --date-start 2020-01-01 --date-end 2026-04-24
```

Expected output: ~1500 trading days populated (6 years × ~250 trading days/year).

### 2.5 Verify
```bash
# Post-backfill state
sqlite3 data/sonar-dev.db \
  "SELECT country_code, COUNT(*), MIN(date), MAX(date)
   FROM yield_curves_forwards
   WHERE country_code='GB';"
# Expected: ~1500 rows, 2020-01-02 → 2026-04-24

# Verify INSUFFICIENT_HISTORY flag gone
uv run python -m sonar.pipelines.daily_monetary_indices --country GB --date 2026-04-23 2>&1 | \
  grep "m3_compute_mode.*country=GB"
# Expected: flags NOT include INSUFFICIENT_HISTORY
```

---

## §3 Commits plan

2-3 commits:
1. `feat(ops): backfill script GB yield curves forwards` (if new script)
2. `ops: GB forwards 2020-2026 backfill executed` (no commit — just log in retro)
3. `docs(planning): Sprint P.2 GB forwards backfill retrospectiva`

---

## §4 HALT

**HALT-0**:
- BoE connector doesn't fetch nominal → Path B/C, scope materially exceeds 60min budget. Open `CAL-GB-FORWARDS-BACKFILL-CONNECTOR-EXTEND` Week 12+, ship Sprint P.2 partial (documentation of gap).
- NSS fit fails for historical dates (data format changes pre-2022 etc) → document + ship from earliest fittable date.

**HALT-material**:
- Existing `yield_curves_forwards` writer rejects backfill rows (constraint violation) → audit schema, may need writer extension. Escalate.
- Backfill triggers pipeline re-fire of downstream (M3 history re-compute expensive) → disable cascading, just insert raw rows.

**HALT-scope**:
- Temptation to backfill EA/DE/FR/IT/ES/PT curves simultaneously → STOP, separate sprints per country.
- Temptation to add real yield backfill (not just nominal) → STOP, scope this sprint = nominal only.

---

## §5 Acceptance

### Tier A
1. Pre-flight probe confirms Path A/B
2. Backfill script shipped (or extension to existing pipeline CLI)
3. GB forwards rows ≥1000 (6 years × ~250 trading days minimum)
4. GB M3 FULL emit no longer stamps INSUFFICIENT_HISTORY
5. Pre-commit clean double-run

### Tier B
Systemd re-run — M3 GB flags clean, no quality regression other countries.

---

## §6 Time budget

Arranque ~17:15 WEST. Hard stop 18:15 WEST (1h).

- Best 30min: Path A (Q.2 connector already fetches nominal) + existing writer handles backfill
- Median 45min: Path B (connector extension) OR existing writer quirk
- Worst 1h HALT: Path C escalate, ship doc-only

**Paralelo com Q.4b** — zero file overlap (Q.4b classifier constant; P.2 ops script + forwards table).

---

*Ops-focused. Quality uplift GB M3. 60min cap.*
