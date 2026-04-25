# Sprint 3 — L2 ERP US-Only Complete

**Date**: 2026-04-25 · Week 11 Day 2 spec-driven L2 closure path
**Spec reference**: [`docs/specs/overlays/erp-daily.md`](https://github.com/hugocondesa-debug/sonar-engine/blob/main/docs/specs/overlays/erp-daily.md) v0.1 (`ERP_CANONICAL_v0.1`)
**Scope**: **US S&P 500 ERP only** per spec §2 fallback ("US ships independently via FRED SP500"). EA/UK/JP defer until CAL-036 + multi-region equity data sprint.
**Budget**: 4-5h CC autonomous work
**Branch**: `sprint-3-l2-erp-us`

---

## 1. Problem statement

L2 ERP gap: 5 ERP tables (`erp_dcf`, `erp_gordon`, `erp_ey`, `erp_cape`, `erp_canonical`) all 0 rows in engine DB. ORM classes exist (`db/models.py:385-489`) since Week 10 but writers + canonical orchestrator never shipped.

L2 NSS shipped Sprint 2 → US `yield_curves_spot/real` 66 rows each (full 60bd recent). L2 EXPINF shipped Sprint 1+1.1 → US `exp_inflation_canonical` 3 rows (US BEI gap pending Sprint 1.2 micro post-Sprint 2 spot extension; not blocker for ERP — ERP uses NSS `yield_curves_spot/real` directly, not EXPINF canonical).

**Sprint 3 closes L2 ERP US-only** per spec §2 authorized path. Remaining L2 overlays (`rating-spread`, `crp`) tracked Sprint 4-5.

EA/UK/JP ERP: out of scope. Empirical audit (2026-04-25) confirmed:
- Index level: TE `/markets/historical/{SXXP,FTAS,TPX}:IND` **NOT validated** (CAL-036 still open)
- Trailing earnings: Shiller US-only; FactSet PDF US-only
- Dividend yield: multpl regex `Current S&P 500 Dividend Yield` US-only
- Buyback yield: spdji_buyback US-only stub
- CAPE: Shiller US-only

Multi-market expansion = dedicated 15-20h sprint sequence post-L2.

---

## 2. Scope (in / out)

### In scope
1. Verify ORM classes match spec §8 verbatim
2. Ship 4 method writers per spec §4:
   - `dcf.py` — Damodaran 5Y DCF + terminal (Newton root-find via scipy)
   - `gordon.py` — `(div + buyback) + g_sustainable − rf` (Gordon stub buyback handling)
   - `ey.py` — `forward_eps / index_level − rf`
   - `cape.py` — `1/CAPE − real_rf` (real-yield anchored)
3. Ship canonical orchestrator per spec §4 step 5: median + range
4. Ship US backfill orchestrator (existing 60 bd window)
5. CLI extension: `sonar backfill erp-daily --start --end`
6. Tests: 4 spec §7 fixtures (US-applicable subset):
   - `us_2024_01_02` — 4 methods median ~472 bps
   - `us_partial_3methods` — FactSet PDF down → 3 methods
   - `us_divergence_2020_03_23` — COVID range >400 bps
   - `damodaran_xval_2024_01_31` — xval Damodaran <20 bps

### Out of scope (defer)
- EA/UK/JP markets (CAL-036 + multi-region equity data)
- Pre-2020 historical backfill (US only 60 bd Sprint 3 window; extended history Sprint 3.1 if needed)
- IRP haircut to ERP (not in spec §4)
- Forward-projected ERP at 1Y/5Y (spec §11 explicit out)
- Beta-adjusted country-specific ERP (lives in `integration/cost-of-capital` L6)

---

## 3. Specs referenced (verbatim)

### Spec §1 — Purpose

> "Compute daily Equity Risk Premium para 4 mature markets (US S&P 500, EA STOXX 600, UK FTSE All-Share, JP TOPIX) via 4 independent methods (DCF, Gordon, Earnings Yield, CAPE). Canonical output é median dos 4 methods em bps; `erp_range_bps` exposto como sinal de incerteza. Damodaran monthly é cross-validation (não input)."

**Sprint 3 implements US only** per spec §2 fallback authorization.

### Spec §2 — Risk-free table (verbatim, US row)

| Market | Risk-free | NSS query (nominal) | NSS query (real) |
|---|---|---|---|
| US | UST 10Y | `yield_curves_spot · country=US · tenor=10Y` | `yield_curves_real · country=US · tenor=10Y` |

### Spec §2 — Market data (US row)

| Input | Source connector | Used by |
|---|---|---|
| `index_level` | FRED `SP500` | DCF, EY, CAPE |
| `trailing_earnings` | `shiller` ie_data.xls | CAPE denom |
| `forward_earnings_est` | `factset_insight` PDF (primary) + `yardeni` (xval) | DCF, EY |
| `dividend_yield_pct` | `multpl` | Gordon |
| `buyback_yield_pct` | `spdji_buyback` (stub — handles None gracefully) | Gordon |
| `cape_ratio` | computed from `shiller` ie_data | CAPE |

### Spec §2 — Parameters (config)

```
growth_horizon_years = 5
terminal_growth = risk_free_nominal
g_sustainable_cap = 0.06
min_methods_for_canonical = 2
divergence_threshold_bps = 400
```

### Spec §2 — Preconditions

> "All 4 NSS risk-free lookups retornam confidence ≥ 0.50 ou raise InsufficientDataError. index_level ≤ 1 business day stale. cape_ratio até 30 dias stale aceitável (Shiller releases monthly); > 30 dias → flag STALE. ≥ 2 dos 4 method-specific inputs disponíveis; senão raise InsufficientDataError. methodology_version of upstream yield_curves_spot/real matches major version of runtime (e.g. NSS_v0.* compatible within major). Minor version mismatch emits UPSTREAM_VERSION_DRIFT flag (−0.05 confidence) but proceeds. Major version mismatch raises VersionMismatchError."

### Spec §4 — Algorithm (verbatim formulas)

**Units convention**: Compute in decimal internally; convert at persistence boundary via `int(round(decimal × 10_000))`.

#### DCF (`ERP_DCF_v0.1`)

```text
Solve r in:
  P = Σ[t=1..5] (E_0 · (1+g)^t · payout) / (1+r)^t
    +            (E_0 · (1+g)^5 · (1+g_T) · payout) / ((r − g_T) · (1+r)^5)
where
  g   = analyst consensus EPS growth 5Y (FactSet)
  g_T = risk_free_nominal                    (terminal growth anchor)
  payout = dividend_yield + buyback_yield    (fallback: 1 − retention)
ERP_DCF = r − risk_free_nominal
```

Root-find via `scipy.optimize.newton`, `x0 = risk_free + 0.05`, bounded `[0, 0.30]`.

#### Gordon (`ERP_GORDON_v0.1`)

```text
ERP_Gordon = (dividend_yield + buyback_yield) + g_sustainable − risk_free_nominal
g_sustainable = min(retention · ROE, g_sustainable_cap)
```

**Buyback handling**: spdji_buyback is graceful stub (raises `DataUnavailableError`). Gordon writer **handles `None` buyback_yield**: emit row with `buyback_yield_pct = NULL`, compute `(div + 0) + g_sustainable − rf`. Flag `BUYBACK_UNAVAILABLE` per row.

#### Earnings Yield (`ERP_EY_v0.1`)

```text
ERP_EY = (forward_earnings / index_level) − risk_free_nominal
```

#### CAPE (`ERP_CAPE_v0.1`) — real-yield anchored

```text
CAPE      = index_level / mean(real_earnings, last 10Y)
ERP_CAPE  = (1 / CAPE) − real_risk_free
```

`real_earnings` from Shiller `ie_data` `Real Earnings` column (CPI-adjusted). Last 10Y = 120 monthly observations.

### Spec §4 step 5 — Canonical (verbatim)

> "5. Build canonical:
>    - `erp_*_bps = int(round(erp_*_pct · 10_000))` para cada método disponível.
>    - `erp_median_bps = median(available_bps)`.
>    - `erp_range_bps = max(available_bps) − min(available_bps)`.
>    - `methods_available = count(available)`.
>    - `confidence_canonical = min(method_confidences)`, capped by floor; then deduct `0.05 × (4 − methods_available)` per missing method (aligns with flags.md propagation: cap-then-deduct, additive). Clamp `[0, 1]`."

### Spec §4 step 8 — Damodaran xval (US only)

> "Se `histimpl.xlsx` tem row para `date.month`: compute `xval_deviation_bps = |erp_dcf_bps − damodaran_us_erp_bps|` (US only); flag `XVAL_DRIFT` se `> 20 bps`."

### Spec §4 step 8.5 — FactSet vs Yardeni (US only)

> "Cross-source forward-earnings divergence (US only, Week 3.5+): when both FactSet and Yardeni forward EPS estimates are fresh (≤ 7 days), compute `forward_eps_divergence_pct = |factset_eps − yardeni_eps| / mean(factset_eps, yardeni_eps)`. Emit flag `ERP_SOURCE_DIVERGENCE` when `> 5%`. Does not affect canonical ERP computation (use FactSet primary); editorial signal only."

### Spec §6 — Edge cases (Sprint 3 critical subset)

| Trigger | Handling | Confidence |
|---|---|---|
| Risk-free NSS missing / `confidence < 0.50` | raise `InsufficientDataError` | n/a |
| DCF Newton não convergiu | catch `ConvergenceError`; skip DCF; flag `NSS_FAIL` (reemit) | method: cap 0.50 |
| FactSet PDF scrape falha | raise `DataUnavailableError` → skip DCF + EY; flag `OVERLAY_MISS` | canonical: −0.20 |
| Shiller `ie_data` > 30 dias | flag `STALE`; compute CAPE anyway | −0.20 |
| Buyback unavailable (stub always) | Gordon uses dividend-only; flag `BUYBACK_UNAVAILABLE` | informational |
| `erp_range_bps > 400` | flag `ERP_METHOD_DIVERGENCE` | canonical: −0.10 |
| `|erp_dcf_bps − damodaran_bps| > 20` | flag `XVAL_DRIFT` | −0.10 |
| `methods_available < 2` | não persistir canonical; persistir method rows disponíveis | n/a |
| `forward_eps_divergence_pct > 5%` (FactSet vs Yardeni) | flag `ERP_SOURCE_DIVERGENCE`; no confidence impact | 0 |

### Spec §7 — Fixtures (Sprint 3 subset)

| Fixture | Input | Expected | Tolerance |
|---|---|---|---|
| `us_2024_01_02` | SPX=4742.83; UST10Y=0.0415; FactSet+Shiller+buyback fixtures | `dcf_bps≈482`, `gordon_bps≈461`, `ey_bps≈453`, `cape_bps≈495`; `median_bps≈472`; `range_bps≈42`; `methods_available=4` | ±15 bps per method; ±10 bps median |
| `us_partial_3methods` | FactSet PDF down | `methods_available=3`; canonical computed; flag `OVERLAY_MISS` | — |
| `us_divergence_2020_03_23` | COVID trough snapshot | `range_bps > 400`; flag `ERP_METHOD_DIVERGENCE` | — |
| `damodaran_xval_2024_01_31` | `histimpl` row Jan 2024 vs DCF | `|erp_dcf_bps − damodaran_bps| < 20`; no `XVAL_DRIFT` | ±20 bps |

### Spec §8 — Storage schema (verbatim, common preamble)

```sql
-- Common preamble (MANDATORY in all 5 tables):
--   id                    INTEGER PRIMARY KEY AUTOINCREMENT,
--   erp_id                TEXT    NOT NULL,           -- uuid4, shared 5 rows
--   market_index          TEXT    NOT NULL,           -- 'SPX' for US Sprint 3
--   country_code          TEXT    NOT NULL,           -- 'US' Sprint 3
--   date                  DATE    NOT NULL,
--   methodology_version   TEXT    NOT NULL,
--   risk_free_nominal_pct REAL    NOT NULL,           -- from NSS (decimal)
--   confidence            REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
--   flags                 TEXT,
--   created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--   UNIQUE (market_index, date, methodology_version)
```

### Spec §8 method tables (Sprint 3 columns)

```sql
CREATE TABLE erp_dcf (
    /* + common preamble */
    erp_bps              INTEGER NOT NULL,
    implied_r_pct        REAL NOT NULL,
    earnings_growth_pct  REAL NOT NULL,
    terminal_growth_pct  REAL NOT NULL
);

CREATE TABLE erp_gordon (
    /* + common preamble */
    erp_bps              INTEGER NOT NULL,
    dividend_yield_pct   REAL NOT NULL,
    buyback_yield_pct    REAL,                          -- NULL allowed (stub)
    g_sustainable_pct    REAL NOT NULL
);

CREATE TABLE erp_ey (
    /* + common preamble */
    erp_bps              INTEGER NOT NULL,
    forward_pe           REAL NOT NULL,
    forward_earnings     REAL NOT NULL,
    index_level          REAL NOT NULL
);

CREATE TABLE erp_cape (
    /* + common preamble */
    erp_bps                 INTEGER NOT NULL,
    cape_ratio              REAL NOT NULL,
    real_risk_free_pct      REAL NOT NULL,
    real_earnings_10y_avg   REAL NOT NULL
);

CREATE TABLE erp_canonical (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    erp_id                TEXT    NOT NULL UNIQUE,
    market_index          TEXT    NOT NULL,
    country_code          TEXT    NOT NULL,
    date                  DATE    NOT NULL,
    methodology_version   TEXT    NOT NULL,
    erp_dcf_bps           INTEGER,                      -- NULL se método indisponível
    erp_gordon_bps        INTEGER,
    erp_ey_bps            INTEGER,
    erp_cape_bps          INTEGER,
    erp_median_bps        INTEGER NOT NULL,
    erp_range_bps         INTEGER NOT NULL,
    methods_available     INTEGER NOT NULL CHECK (methods_available BETWEEN 1 AND 4),
    xval_deviation_bps    INTEGER,                      -- NULL when xval not available
    confidence            REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags                 TEXT,
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (market_index, date, methodology_version)
);
```

---

## 4. Implementation steps (deterministic)

### Step 0 — Worktree seed (5min)

Per Sprint 1.1 retrospective lesson:

```bash
cd /home/macro/projects/sonar-sprint-3
mkdir -p data
ln -sf /home/macro/projects/sonar-engine/data/sonar-dev.db data/sonar-dev.db
ln -sf /home/macro/projects/sonar-engine/.env .env
```

### Step 1 — Audit current state (15min)

```bash
# 1. Verify 5 ORM classes match spec §8 schema verbatim
grep -A 30 "^class ERPDCF" src/sonar/db/models.py | head -35
grep -A 30 "^class ERPGordon" src/sonar/db/models.py | head -35
grep -A 30 "^class ERPEY" src/sonar/db/models.py | head -35
grep -A 30 "^class ERPCAPE" src/sonar/db/models.py | head -35
grep -A 30 "^class ERPCanonical" src/sonar/db/models.py | head -40

# 2. Verify physical schema matches ORM
sqlite3 data/sonar-dev.db ".schema erp_canonical"
sqlite3 data/sonar-dev.db ".schema erp_dcf"

# 3. Verify connector entry points
grep -n "fetch_sp500\|SP500" src/sonar/connectors/fred.py | head -5
grep -n "fetch_latest_snapshot" src/sonar/connectors/factset_insight.py | head -3
grep -n "fetch_latest_snapshot" src/sonar/connectors/yardeni.py | head -3
grep -n "fetch_current_dividend_yield" src/sonar/connectors/multpl.py | head -3
grep -n "fetch_latest_buyback" src/sonar/connectors/spdji_buyback.py | head -3
grep -n "fetch_raw_xls\|cape_ratio" src/sonar/connectors/shiller.py | head -10
grep -n "fetch_annual_erp\|fetch_monthly" src/sonar/connectors/damodaran.py | head -5

# 4. Verify expected_inflation.canonical entry point (if not used directly, OK)
ls src/sonar/overlays/erp_daily/ 2>/dev/null || echo "Directory does not exist — to create"

# 5. Confirm engine DB risk-free state
sqlite3 data/sonar-dev.db "SELECT COUNT(*), MIN(date), MAX(date) FROM yield_curves_spot WHERE country_code='US';"
sqlite3 data/sonar-dev.db "SELECT COUNT(*), MIN(date), MAX(date) FROM yield_curves_real WHERE country_code='US';"
# Expected: 66 rows each, ~2026-01-24 to 2026-04-23

# 6. Confirm all 5 ERP tables empty
sqlite3 data/sonar-dev.db "SELECT 'dcf' tbl, COUNT(*) FROM erp_dcf UNION ALL SELECT 'gordon', COUNT(*) FROM erp_gordon UNION ALL SELECT 'ey', COUNT(*) FROM erp_ey UNION ALL SELECT 'cape', COUNT(*) FROM erp_cape UNION ALL SELECT 'canonical', COUNT(*) FROM erp_canonical;"
```

Report all findings before Step 2. If any divergence (ORM vs physical, missing connector method, ETC) — halt + ask.

### Step 2 — Create overlays/erp_daily/ module (30min)

Pattern: directory module per Sprint 1 EXPINF (5 sibling files).

Create `src/sonar/overlays/erp_daily/__init__.py`:

```python
"""L2 ERP overlay — 4 methods (DCF/Gordon/EY/CAPE) + canonical median per spec erp-daily.md.

Sprint 3 scope: US only. EA/UK/JP defer to multi-region sprint post-L2.
"""

from sonar.overlays.erp_daily.dcf import build_dcf_row
from sonar.overlays.erp_daily.gordon import build_gordon_row
from sonar.overlays.erp_daily.ey import build_ey_row
from sonar.overlays.erp_daily.cape import build_cape_row
from sonar.overlays.erp_daily.canonical import build_canonical_row

__all__ = [
    "build_dcf_row",
    "build_gordon_row",
    "build_ey_row",
    "build_cape_row",
    "build_canonical_row",
]
```

### Step 3 — DCF writer (90min)

Create `src/sonar/overlays/erp_daily/dcf.py`:

```python
"""DCF ERP writer per spec erp-daily.md §4 DCF method.

Damodaran 5Y projection + terminal growth.
Solve r via scipy.optimize.newton.
"""

import json
from datetime import date as date_type
from uuid import uuid4

from scipy.optimize import newton, RootResults
from sqlalchemy.orm import Session

from sonar.db.models import ERPDCF, NSSYieldCurveSpot
from sonar.overlays.exceptions import (
    InsufficientDataError,
    ConvergenceError,
)


GROWTH_HORIZON_YEARS = 5
NEWTON_X0_DELTA = 0.05  # x0 = risk_free + 0.05
NEWTON_BOUNDS = (0.0, 0.30)


def _dcf_residual(r, P, E_0, g, g_T, payout):
    """5Y DCF residual = projected_PV - observed_price."""
    pv_5y = sum(
        (E_0 * (1 + g) ** t * payout) / (1 + r) ** t
        for t in range(1, 6)
    )
    pv_terminal = (
        (E_0 * (1 + g) ** 5 * (1 + g_T) * payout)
        / ((r - g_T) * (1 + r) ** 5)
    )
    return P - (pv_5y + pv_terminal)


def build_dcf_row(
    session: Session,
    country_code: str,
    target_date: date_type,
    *,
    erp_id: str,
    market_index: str = "SPX",
    risk_free_nominal_pct: float,
    index_level: float,
    forward_eps: float,
    earnings_growth_5y: float,
    payout_ratio: float,
) -> ERPDCF:
    """Build ERPDCF row per spec §4 DCF formula."""
    g = earnings_growth_5y
    g_T = risk_free_nominal_pct  # terminal growth = nominal risk-free per spec

    try:
        r = newton(
            _dcf_residual,
            x0=risk_free_nominal_pct + NEWTON_X0_DELTA,
            args=(index_level, forward_eps, g, g_T, payout_ratio),
            tol=1e-6,
            maxiter=50,
        )
        if not (NEWTON_BOUNDS[0] <= r <= NEWTON_BOUNDS[1]):
            raise ConvergenceError(
                f"DCF Newton converged to r={r:.4f} outside bounds {NEWTON_BOUNDS}"
            )
    except (RuntimeError, ValueError) as exc:
        raise ConvergenceError(f"DCF Newton failed: {exc}") from exc

    erp_dcf_pct = r - risk_free_nominal_pct
    erp_bps = int(round(erp_dcf_pct * 10_000))

    # Confidence: 0.85 base; deductions per upstream flag inheritance
    confidence = 0.85
    flags = []

    return ERPDCF(
        erp_id=erp_id,
        market_index=market_index,
        country_code=country_code,
        date=target_date,
        methodology_version="ERP_DCF_v0.1",
        risk_free_nominal_pct=risk_free_nominal_pct,
        erp_bps=erp_bps,
        implied_r_pct=r,
        earnings_growth_pct=g,
        terminal_growth_pct=g_T,
        confidence=confidence,
        flags=",".join(sorted(flags)) if flags else None,
    )
```

Critical: catch `ConvergenceError` at orchestrator level → emit `NSS_FAIL` flag, skip DCF row.

### Step 4 — Gordon writer (45min)

Create `src/sonar/overlays/erp_daily/gordon.py`:

```python
"""Gordon ERP writer per spec erp-daily.md §4 Gordon method.

Buyback graceful: spdji stub → buyback_yield = None acceptable per spec §6.
"""

G_SUSTAINABLE_CAP = 0.06  # spec config


def build_gordon_row(
    session: Session,
    country_code: str,
    target_date: date_type,
    *,
    erp_id: str,
    market_index: str = "SPX",
    risk_free_nominal_pct: float,
    dividend_yield_pct: float,
    buyback_yield_pct: float | None,  # None when spdji stub raises
    retention_ratio: float,  # 1 - payout
    roe: float,
) -> ERPGordon:
    """Build ERPGordon row per spec §4 Gordon formula."""
    g_sustainable = min(retention_ratio * roe, G_SUSTAINABLE_CAP)

    payout_yield = dividend_yield_pct + (buyback_yield_pct or 0.0)
    erp_pct = payout_yield + g_sustainable - risk_free_nominal_pct
    erp_bps = int(round(erp_pct * 10_000))

    flags = []
    confidence = 0.80
    if buyback_yield_pct is None:
        flags.append("BUYBACK_UNAVAILABLE")  # spec §6 stub graceful

    return ERPGordon(
        erp_id=erp_id,
        market_index=market_index,
        country_code=country_code,
        date=target_date,
        methodology_version="ERP_GORDON_v0.1",
        risk_free_nominal_pct=risk_free_nominal_pct,
        erp_bps=erp_bps,
        dividend_yield_pct=dividend_yield_pct,
        buyback_yield_pct=buyback_yield_pct,  # NULL when stub
        g_sustainable_pct=g_sustainable,
        confidence=confidence,
        flags=",".join(sorted(flags)) if flags else None,
    )
```

Critical: handle `None` buyback_yield gracefully per spec §6 stub semantics. Emit `BUYBACK_UNAVAILABLE` flag.

### Step 5 — Earnings Yield writer (30min)

Create `src/sonar/overlays/erp_daily/ey.py`:

```python
"""Earnings Yield ERP writer per spec erp-daily.md §4 EY method."""


def build_ey_row(
    session: Session,
    country_code: str,
    target_date: date_type,
    *,
    erp_id: str,
    market_index: str = "SPX",
    risk_free_nominal_pct: float,
    forward_earnings: float,
    index_level: float,
) -> ERPEY:
    """Build ERPEY row per spec §4 EY formula."""
    forward_pe = index_level / forward_earnings
    earnings_yield = forward_earnings / index_level
    erp_pct = earnings_yield - risk_free_nominal_pct
    erp_bps = int(round(erp_pct * 10_000))

    confidence = 0.85
    flags = []

    return ERPEY(
        erp_id=erp_id,
        market_index=market_index,
        country_code=country_code,
        date=target_date,
        methodology_version="ERP_EY_v0.1",
        risk_free_nominal_pct=risk_free_nominal_pct,
        erp_bps=erp_bps,
        forward_pe=forward_pe,
        forward_earnings=forward_earnings,
        index_level=index_level,
        confidence=confidence,
        flags=",".join(sorted(flags)) if flags else None,
    )
```

### Step 6 — CAPE writer (60min)

Create `src/sonar/overlays/erp_daily/cape.py`:

```python
"""CAPE ERP writer per spec erp-daily.md §4 CAPE method.

CAPE = index_level / mean(real_earnings, last 10Y).
ERP_CAPE = (1 / CAPE) - real_risk_free.
"""

import numpy as np


def build_cape_row(
    session: Session,
    country_code: str,
    target_date: date_type,
    *,
    erp_id: str,
    market_index: str = "SPX",
    risk_free_nominal_pct: float,  # for common preamble
    real_risk_free_pct: float,
    index_level: float,
    real_earnings_history_10y: list[float],  # 120 monthly observations
) -> ERPCAPE:
    """Build ERPCAPE row per spec §4 CAPE formula."""
    if len(real_earnings_history_10y) < 60:  # min half-window for CAPE sanity
        raise InsufficientDataError(
            f"CAPE requires ≥60 monthly real earnings; got {len(real_earnings_history_10y)}"
        )

    real_earnings_10y_avg = float(np.mean(real_earnings_history_10y))
    cape_ratio = index_level / real_earnings_10y_avg
    erp_pct = (1.0 / cape_ratio) - real_risk_free_pct
    erp_bps = int(round(erp_pct * 10_000))

    confidence = 0.80
    flags = []

    return ERPCAPE(
        erp_id=erp_id,
        market_index=market_index,
        country_code=country_code,
        date=target_date,
        methodology_version="ERP_CAPE_v0.1",
        risk_free_nominal_pct=risk_free_nominal_pct,
        erp_bps=erp_bps,
        cape_ratio=cape_ratio,
        real_risk_free_pct=real_risk_free_pct,
        real_earnings_10y_avg=real_earnings_10y_avg,
        confidence=confidence,
        flags=",".join(sorted(flags)) if flags else None,
    )
```

### Step 7 — Canonical orchestrator (60min)

Create `src/sonar/overlays/erp_daily/canonical.py`:

```python
"""ERP canonical writer per spec erp-daily.md §4 step 5.

Median + range across 4 methods. Damodaran xval (US only).
"""

import json
from statistics import median
from uuid import uuid4

from sonar.connectors.damodaran import DamodaranConnector
from sonar.overlays.exceptions import InsufficientDataError


MIN_METHODS_FOR_CANONICAL = 2
DIVERGENCE_THRESHOLD_BPS = 400
XVAL_THRESHOLD_BPS = 20


def build_canonical_row(
    session: Session,
    country_code: str,
    target_date: date_type,
    *,
    erp_id: str,
    market_index: str = "SPX",
    risk_free_nominal_pct: float,
    method_rows: dict,  # {"dcf": ERPDCF | None, "gordon": ..., "ey": ..., "cape": ...}
) -> ERPCanonical | None:
    """Build canonical row from method outputs.

    Returns None if methods_available < MIN_METHODS_FOR_CANONICAL.
    """
    available_bps = {
        method: row.erp_bps
        for method, row in method_rows.items()
        if row is not None
    }

    if len(available_bps) < MIN_METHODS_FOR_CANONICAL:
        log.critical(
            "erp_canonical.skip country=%s date=%s methods_available=%d",
            country_code, target_date, len(available_bps),
        )
        return None

    bps_values = list(available_bps.values())
    erp_median_bps = int(round(median(bps_values)))
    erp_range_bps = max(bps_values) - min(bps_values)

    # Confidence: min(method_confidences) - 0.05 per missing method, clamped
    method_confidences = [row.confidence for row in method_rows.values() if row is not None]
    confidence = min(method_confidences) - 0.05 * (4 - len(available_bps))
    confidence = max(0.0, min(1.0, confidence))

    flags = []
    if erp_range_bps > DIVERGENCE_THRESHOLD_BPS:
        flags.append("ERP_METHOD_DIVERGENCE")
        confidence -= 0.10

    # Damodaran xval (US DCF only)
    xval_deviation_bps = None
    if country_code == "US" and "dcf" in available_bps:
        try:
            damodaran_row = DamodaranConnector(...).fetch_monthly_implied_erp(
                year=target_date.year, month=target_date.month
            )
            if damodaran_row:
                damodaran_bps = int(round(damodaran_row.implied_erp_decimal * 10_000))
                xval_deviation_bps = abs(available_bps["dcf"] - damodaran_bps)
                if xval_deviation_bps > XVAL_THRESHOLD_BPS:
                    flags.append("XVAL_DRIFT")
                    confidence -= 0.10
        except DataUnavailableError:
            pass  # xval optional per spec §6

    # Inherit upstream flags from method rows
    for row in method_rows.values():
        if row is not None and row.flags:
            flags.extend(row.flags.split(","))
    flags = sorted(set(flags))

    return ERPCanonical(
        erp_id=erp_id,
        market_index=market_index,
        country_code=country_code,
        date=target_date,
        methodology_version="ERP_CANONICAL_v0.1",
        risk_free_nominal_pct=risk_free_nominal_pct,
        erp_dcf_bps=available_bps.get("dcf"),
        erp_gordon_bps=available_bps.get("gordon"),
        erp_ey_bps=available_bps.get("ey"),
        erp_cape_bps=available_bps.get("cape"),
        erp_median_bps=erp_median_bps,
        erp_range_bps=erp_range_bps,
        methods_available=len(available_bps),
        xval_deviation_bps=xval_deviation_bps,
        confidence=max(0.0, min(1.0, confidence)),
        flags=",".join(flags) if flags else None,
    )
```

### Step 8 — Backfill orchestrator (60min)

Create `src/sonar/overlays/erp_daily/backfill.py`:

```python
"""ERP US backfill orchestrator per spec §2 fallback.

Sprint 3 scope: US S&P 500 only.
"""

from sonar.connectors import (
    fred, shiller, factset_insight, yardeni, multpl, spdji_buyback
)


T1_ERP_COUNTRIES_SPRINT3 = ["US"]


def backfill_erp_us(session, start_date, end_date):
    """Backfill US ERP for 60 bd window."""
    success_count = 0
    error_count = 0

    for target_date in business_days(start_date, end_date):
        try:
            # Fetch risk-free from NSS
            rf_nominal = _fetch_rf_nominal(session, "US", target_date)
            rf_real = _fetch_rf_real(session, "US", target_date)

            # Fetch market data
            try:
                index_level = await fred.fetch_sp500(target_date)
                forward_eps = await factset_insight.fetch_forward_eps(target_date)
                dividend_yield = await multpl.fetch_current_dividend_yield_decimal()
                try:
                    buyback_yield = await spdji_buyback.fetch_latest_buyback_yield_decimal()
                except DataUnavailableError:
                    buyback_yield = None  # graceful per spec §6
                shiller_data = await shiller.fetch_latest_snapshot(target_date)
                cape_ratio = shiller_data.cape_ratio
                real_earnings_10y = await shiller.fetch_real_earnings_history(years=10)
            except DataUnavailableError as e:
                log.warning("erp_us.market_data.skip date=%s reason=%s", target_date, e)
                error_count += 1
                continue

            # Build erp_id (shared across 5 rows)
            erp_id = uuid4().hex

            # Build 4 method rows
            method_rows = {}

            try:
                method_rows["dcf"] = build_dcf_row(
                    session, "US", target_date,
                    erp_id=erp_id, risk_free_nominal_pct=rf_nominal,
                    index_level=index_level, forward_eps=forward_eps,
                    earnings_growth_5y=...,  # from FactSet
                    payout_ratio=dividend_yield + (buyback_yield or 0),
                )
            except ConvergenceError:
                method_rows["dcf"] = None  # spec §6 NSS_FAIL

            try:
                method_rows["gordon"] = build_gordon_row(
                    session, "US", target_date,
                    erp_id=erp_id, risk_free_nominal_pct=rf_nominal,
                    dividend_yield_pct=dividend_yield,
                    buyback_yield_pct=buyback_yield,
                    retention_ratio=...,  # 1 - payout
                    roe=...,  # from financials
                )
            except DataUnavailableError:
                method_rows["gordon"] = None

            try:
                method_rows["ey"] = build_ey_row(
                    session, "US", target_date,
                    erp_id=erp_id, risk_free_nominal_pct=rf_nominal,
                    forward_earnings=forward_eps, index_level=index_level,
                )
            except DataUnavailableError:
                method_rows["ey"] = None

            try:
                method_rows["cape"] = build_cape_row(
                    session, "US", target_date,
                    erp_id=erp_id, risk_free_nominal_pct=rf_nominal,
                    real_risk_free_pct=rf_real, index_level=index_level,
                    real_earnings_history_10y=real_earnings_10y,
                )
            except (DataUnavailableError, InsufficientDataError):
                method_rows["cape"] = None

            # Build canonical
            canonical = build_canonical_row(
                session, "US", target_date,
                erp_id=erp_id, risk_free_nominal_pct=rf_nominal,
                method_rows=method_rows,
            )

            # Persist atomically
            for row in method_rows.values():
                if row is not None:
                    session.merge(row)
            if canonical is not None:
                session.merge(canonical)
            success_count += 1

        except InsufficientDataError as e:
            log.warning("erp_us.skip date=%s reason=%s", target_date, e)
            error_count += 1

    session.commit()
    log.info("erp_us.backfill.done success=%d errors=%d", success_count, error_count)
```

### Step 9 — CLI subcommand (15min)

Extend `src/sonar/cli/backfill.py` per Sprint 1.1 + Sprint 2 pattern. Add command:

```python
@app.command(name="erp-daily")
def erp_daily(
    start: date,
    end: date,
):
    """Backfill US ERP daily for date range."""
    session = get_session()
    backfill_erp_us(session, start, end)
```

### Step 10 — Tests (60min)

Create `tests/unit/test_overlays/test_erp_us.py`:

Implement 4 spec §7 fixtures (US-applicable):

1. **`us_2024_01_02`** — full 4 methods, expected median ~472 bps ±10 bps
2. **`us_partial_3methods`** — FactSet PDF down → DCF/EY skipped, methods_available=3, flag `OVERLAY_MISS`
3. **`us_divergence_2020_03_23`** — COVID range >400 bps, flag `ERP_METHOD_DIVERGENCE`
4. **`damodaran_xval_2024_01_31`** — `|erp_dcf − damodaran_bps| < 20`, no `XVAL_DRIFT`

Fixtures stored in `tests/fixtures/erp-daily/` per spec §7.

### Step 11 — Tier B verification (15min)

After backfill executes against engine DB:

```bash
sqlite3 /home/macro/projects/sonar-engine/data/sonar-dev.db <<'EOF'
.mode column
.headers on

-- Row counts per table
SELECT 'dcf' tbl, COUNT(*) FROM erp_dcf
UNION ALL SELECT 'gordon', COUNT(*) FROM erp_gordon
UNION ALL SELECT 'ey', COUNT(*) FROM erp_ey
UNION ALL SELECT 'cape', COUNT(*) FROM erp_cape
UNION ALL SELECT 'canonical', COUNT(*) FROM erp_canonical;

-- US canonical sample
SELECT date, market_index, erp_median_bps, erp_range_bps, methods_available, confidence, flags
FROM erp_canonical
WHERE country_code='US'
ORDER BY date DESC
LIMIT 5;

-- Method availability distribution
SELECT methods_available, COUNT(*) FROM erp_canonical GROUP BY methods_available;

-- ERP_METHOD_DIVERGENCE incidence
SELECT COUNT(*) AS divergence_rows FROM erp_canonical
WHERE flags LIKE '%ERP_METHOD_DIVERGENCE%';

-- XVAL_DRIFT incidence
SELECT COUNT(*) AS xval_drift_rows FROM erp_canonical
WHERE flags LIKE '%XVAL_DRIFT%';

-- erp_id integrity check
SELECT COUNT(*) AS orphan_canonical FROM erp_canonical c
WHERE NOT EXISTS (SELECT 1 FROM erp_dcf d WHERE d.erp_id = c.erp_id);
EOF
```

Expected post-backfill:
- All 5 tables ≥40 US rows (some methods may be NULL when input unavailable)
- `erp_canonical`: ≥40 US rows; `methods_available` distribution mostly 4 (full availability)
- `ERP_METHOD_DIVERGENCE` incidence: low (recent dates expect tight ERP range <400 bps)
- `XVAL_DRIFT`: distribution informative (Damodaran monthly vs daily DCF natural drift)
- 0 orphan canonical rows

---

## 5. Acceptance criteria

### Must pass
1. ✅ All 5 ERP tables populated for US with ≥40 rows each
2. ✅ `erp_canonical` US `methods_available=4` for majority of dates
3. ✅ Zero orphan canonical rows (erp_id integrity)
4. ✅ 4 fixtures tests pass within spec §7 tolerances
5. ✅ Pre-commit + pytest green
6. ✅ `BUYBACK_UNAVAILABLE` flag present on all `erp_gordon` rows (spdji stub graceful)
7. ✅ Merged via sprint_merge.sh

### Out of scope (defer)
- EA/UK/JP markets (CAL-036 unblocked)
- Pre-2020 historical (Sprint 3.1 if needed)
- ERP_SOURCE_DIVERGENCE FactSet vs Yardeni (optional editorial signal; ship if data available, else accept skip)

### Known limitations (accepted)
- Damodaran xval relies on `histimpl.xlsx` monthly data; daily DCF vs monthly damodaran natural drift expected
- spdji buyback graceful stub: Gordon dividend-only; flag `BUYBACK_UNAVAILABLE` per row
- Real earnings 10Y history: requires Shiller `ie_data.xls` parsed >120 monthly obs; fail gracefully if <60 obs

---

## 6. Risks + mitigations

| Risk | Mitigation |
|---|---|
| FactSet PDF schema changed since last parse | Connector smoke test in Step 1 audit; if parse fails, skip DCF+EY graceful per spec §6 |
| Yardeni weekly PDF stale | Optional; cross-source divergence flag editorial only, not blocker |
| DCF Newton non-convergence on extreme dates | Spec §6 catch ConvergenceError → skip DCF, emit NSS_FAIL flag |
| Shiller `ie_data.xls` cached >30 days | Spec §6 STALE flag, compute CAPE anyway with confidence -0.20 |
| `multpl` regex breaks if HTML changes | Connector existing has retry + DataUnavailableError; skip Gordon if needed |
| Damodaran historical xlsx not loadable | xval optional per spec §6, no blocker |

---

## 7. Dependencies

- **Spec**: [`erp-daily.md`](https://github.com/hugocondesa-debug/sonar-engine/blob/main/docs/specs/overlays/erp-daily.md) v0.1
- **Upstream Sprint 2**: `yield_curves_spot/real` US 66 rows (2026-01-24 to 2026-04-23)
- **Upstream Sprint 1+1.1**: `exp_inflation_canonical` US 3 rows (Sprint 1.2 micro will extend; not blocker)
- **Connectors all confirmed**: fred (SP500), shiller, factset_insight, yardeni, multpl, spdji_buyback (stub), damodaran
- **Data sources**: [`monetary.md`](https://github.com/hugocondesa-debug/sonar-engine/blob/main/docs/data_sources/monetary.md) §3.1 FRED catalog
- **Architecture**: [`patterns.md`](https://github.com/hugocondesa-debug/sonar-engine/blob/main/docs/specs/conventions/patterns.md) §Pattern 1 (Parallel equals)

---

## 8. CC prompt template

```
Sprint 3 — L2 ERP US-Only Complete

Read spec: docs/specs/overlays/erp-daily.md v0.1
Read brief: docs/planning/week11-sprint-3-l2-erp-us-brief.md

Execute 11 steps per brief §4:

Step 0 — Worktree seed (symlink DB + .env from engine main per Sprint 1.1 lesson)
Step 1 — Audit current state (8 commands; report findings before Step 2)
Step 2 — Create overlays/erp_daily/ module + __init__.py
Step 3 — DCF writer (scipy newton, spec §4 formula verbatim, ConvergenceError handling)
Step 4 — Gordon writer (handle None buyback graceful per spec §6, BUYBACK_UNAVAILABLE flag)
Step 5 — EY writer (forward_pe + earnings_yield)
Step 6 — CAPE writer (10Y rolling real earnings, ≥60 obs minimum)
Step 7 — Canonical orchestrator (median + range, Damodaran xval US-only)
Step 8 — Backfill orchestrator (US 60 bd, atomic 5-sibling persist sharing erp_id)
Step 9 — CLI extension: sonar backfill erp-daily --start --end
Step 10 — 4 fixture tests per spec §7 (us_2024_01_02 + us_partial_3methods + us_divergence_2020_03_23 + damodaran_xval_2024_01_31)
Step 11 — Execute backfill against engine DB + Tier B verification

Critical rules:
- Sprint 3 scope: US ONLY (market_index='SPX', country_code='US')
- 5 sibling rows share single erp_id UUID per (date) — atomic persist
- erp_bps = int(round(decimal × 10_000)) at persistence boundary per conventions/units.md
- 5y5y compounded NOT linear (consistent with NSS spec)
- Spec §6 edge cases verbatim: skip method on DataUnavailableError + flag; skip canonical on methods_available<2
- Confidence aggregation: min(method_confidences) - 0.05 × (4 - methods_available); clamp [0,1]
- BUYBACK_UNAVAILABLE flag MANDATORY on every erp_gordon row (spdji stub graceful)
- Damodaran xval US only; skip silent if histimpl row missing for date.month
- Inherit upstream flags from method rows to canonical (lexicographic CSV)
- HALT before commit per CLAUDE.md §5/§7. Report deliverables + tests + Tier B + spec deviations. Await authorization.

Run pytest + pre-commit + sprint_merge.sh.

Tier B verification at end (run all queries from brief §4 step 11 against ENGINE DB):
  sqlite3 /home/macro/projects/sonar-engine/data/sonar-dev.db <<'EOF'
  -- 5 tables row count, US sample, methods_available distribution, flags incidence, erp_id integrity
  EOF

Expected: all 5 tables ≥40 US rows; canonical methods_available=4 majority; 0 orphan canonical.

Commit message template:
"""
feat(overlays): Sprint 3 L2 ERP US-only complete (4 methods + canonical)

Shipped per spec overlays/erp-daily.md v0.1 §2 fallback (US ships independently):
- overlays/erp_daily/{dcf,gordon,ey,cape,canonical,backfill}.py
- 4 method writers (DCF/Gordon/EY/CAPE) + canonical median orchestrator
- US backfill orchestrator + CLI: sonar backfill erp-daily
- 4 spec §7 fixtures + tests

Spec compliance:
- Atomic 5-sibling persist sharing erp_id per (date) (spec §4 step 4)
- Median canonical + range_bps uncertainty (spec §4 step 5)
- BUYBACK_UNAVAILABLE flag per row (spdji stub graceful, spec §6)
- Damodaran xval US-only; XVAL_DRIFT flag if >20 bps (spec §4 step 8)
- ERP_METHOD_DIVERGENCE flag if range >400 bps (spec §6)

EA/UK/JP markets: out of scope. Spec §2 explicitly authorizes US-only fallback. Multi-market expansion deferred to dedicated sprint sequence post-L2 (CAL-036 TE markets validation + multi-region equity data).

Test status: 4 fixtures pass; full suite green except pre-existing live-canary failures.
Tier B baseline: US 60 bd × 5 tables = ~300 rows; canonical methods_available=4 majority.
"""

START with Step 0 worktree seed. Report Step 1 audit findings before Step 2.
```

---

## 9. Sprint 3 → Sprint 4 (next)

Após Sprint 3 merge + Tier B green:
- **L2 status**: 3/5 overlays complete (NSS ✓ + EXPINF ✓ + ERP US ✓)
- **Sprint 4**: L2 rating-spread (audit existing agency connectors first; ship consolidation + calibration writers)
- **Sprint 5**: L2 CRP (depends Sprint 4; RATING branch consumes ratings_consolidated)
- **L2 closure**: end of Sprint 5 = 5/5 overlays complete

Then L0 connectors batch (Wu-Xia, Krippner, HLW, IMF WEO) + L3 monetary M1-M4 rebuild + L3 economic/credit/financial + L4 cycles.

---

**END BRIEF**
