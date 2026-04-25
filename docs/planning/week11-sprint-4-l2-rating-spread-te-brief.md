# Sprint 4 — L2 Rating-Spread via TE Premium API

**Date**: 2026-04-25 · Week 11 Day 2
**Spec reference**: [`docs/specs/overlays/rating-spread.md`](https://github.com/hugocondesa-debug/sonar-engine/blob/main/docs/specs/overlays/rating-spread.md) v0.2 (`RATING_SPREAD_v0.2`, `RATING_AGENCY_v0.1`, `RATING_CALIBRATION_v0.1`)
**Budget**: 4-5h CC autonomous work
**Branch**: `sprint-4-l2-rating-spread-te`

---

## 1. Problem statement

L2 rating-spread compute infrastructure shipped Week 3 (391 LOC `overlays/rating_spread.py` + 3 ORM classes + lookup tables for 4 agencies). 3 tables empty in engine DB:

```
ratings_agency_raw       0 rows
ratings_consolidated     0 rows
ratings_spread_calibration 0 rows
```

Spec §2 v0.2 designated agency scrape connectors as primary forward source. **TE Premium API ratings endpoint provides comprehensive baseline** — confirmed empirically 2026-04-25:

- `/ratings` (current snapshot): **160 countries × 4 agencies** (SP, Moody's, Fitch, DBRS)
- `/ratings/historical/{country}` (per-country time series): **deep history** (Portugal: 96 actions from 1986-11-18 to 2026-03-06)
- TE Premium subscription **already operational** (other connectors use TE_API_KEY)

Spec D0 audit (Phase 0) flagged TE ratings as "4Y stale (latest 2022-09)". **Reality 2026-04-25: TE Premium endpoint is current** (latest action 2026-03-06 Portugal). Spec note refresh required as part of Sprint 4 retrospective (CAL-SPEC-RATING-TE-REFRESH).

Sprint 4 ships TE-driven backfill of `ratings_agency_raw` + consolidation via existing `consolidate()` function + `ratings_spread_calibration` baseline using existing `APRIL_2026_CALIBRATION` constant.

---

## 2. Scope (in / out)

### In scope

1. Extend existing `connectors/te.py` with sovereign ratings methods:
   - `fetch_sovereign_ratings_current()` → list of TERatingCurrent (160 countries snapshot)
   - `fetch_sovereign_ratings_historical(country)` → list of TERatingHistorical (per-country time series)
2. Backfill orchestrator `overlays/rating_spread/backfill.py` (NEW directory wrapping existing `rating_spread.py` module):
   - Step A: fetch current snapshot via TE API
   - Step B: persist to `ratings_agency_raw` (wide → long pivot)
   - Step C: fetch historical for each country (loop over 160 countries)
   - Step D: persist historical actions to `ratings_agency_raw`
   - Step E: invoke existing `consolidate()` function for each (country, action_date, rating_type)
   - Step F: persist `ratings_consolidated` rows
   - Step G: seed `ratings_spread_calibration` from existing `APRIL_2026_CALIBRATION` constant
3. CLI extension: `sonar backfill rating-spread --include-historical`
4. Tests: 4 fixture tests
5. Tier B verification

### Out of scope (defer)

- TE proprietary score (`TE: 40` field) — NOT a sovereign credit rating per spec; xval reference future sprint
- Damodaran historical xlsx complement — TE Premium covers comprehensively; defer
- Live event-driven 4h polling per spec §pipeline (forward updates) — Sprint 4 ships one-shot baseline; future cron Sprint adds polling
- ECB ECAF EU collateral list — TE covers EA broadly; defer fallback
- Calibration refresh quarterly automation — Sprint 4 uses static APRIL_2026_CALIBRATION; future Sprint adds refresh
- Real CDS divergence cross-validation — depends Sprint 5 CRP shipping

---

## 3. Specs referenced (verbatim)

### TE API empirical findings (2026-04-25 audit)

**Current endpoint** (`/ratings`):
```
GET https://api.tradingeconomics.com/ratings?c={api_key}&f=json
Status: 200
Count: 160 countries
Schema (per row):
{
  "Country": "Albania",
  "TE": "40", "TE_Outlook": "Stable",        ← TE proprietary score (ignore for SONAR)
  "SP": "BB", "SP_Outlook": "Stable",
  "Moodys": "Ba3", "Moodys_Outlook": "Stable",
  "Fitch": "", "Fitch_Outlook": "",          ← empty when agency doesn't rate country
  "DBRS": "", "DBRS_Outlook": ""
}
```

**Historical endpoint** (`/ratings/historical/{country}`):
```
GET https://api.tradingeconomics.com/ratings/historical/portugal?c={api_key}&f=json
Status: 200
Schema (per row, descending by date):
{
  "Country": "Portugal",
  "Date": "3/6/2026",                       ← MM/DD/YYYY format
  "Agency": "Fitch",                         ← single agency per row
  "Rating": "A",
  "Outlook": "Positive"
}
```

**Sample coverage** (Portugal, 96 actions):
- Earliest: 1986-11-18 Moody's A1 Stable
- Latest: 2026-03-06 Fitch A Positive

### Spec rating-spread.md §2 — Inputs (verbatim)

Per-agency raw fields (matched against TE response):

| Spec field | TE API mapping |
|---|---|
| `country_code` ISO α-2 upper | Country name → ISO α-2 lookup (existing `_canonicalize_country_iso` in te.py) |
| `date` business day | TE `Date` (parse MM/DD/YYYY → date) |
| `agency` `"SP" \| "MOODYS" \| "FITCH" \| "DBRS"` | TE `Agency` (S&P/Moody's/Fitch/DBRS → SP/MOODYS/FITCH/DBRS uppercase normalized) |
| `rating_raw` agency-native token | TE `Rating` (already in agency-native format) |
| `rating_type` `"FC" \| "LC"` | **NOT in TE API** — assume "FC" (foreign currency), spec §2 hierarchy column primary |
| `outlook` `"positive" \| "stable" \| "negative" \| "developing"` | TE `Outlook` lowercase normalized |
| `watch` `"watch_positive" \| "watch_negative" \| None` | TE `Outlook` parse for "Watch" suffix |
| `action_date` last rating action date | TE `Date` (same as field above) |

### Spec §2 — Calibration inputs (Sprint 4 simplified)

Spec specifies:
```
| moodys_default_study_json | dict | connectors/moodys_default_study (annual PDF) |
| ice_bofa_spread_bps      | dict[grade,int] | connectors/fred (BAMLC0A0CM, BAMLH0A0HYM2) |
| damodaran_historical_ratings_xlsx | dict | connectors/damodaran_annual_historical |
```

**Sprint 4 simplification**: use existing `APRIL_2026_CALIBRATION` constant from `rating_spread.py` (already populated with anchor values per spec §15.1: notch 21→10bps, 18→35, 15→90, 12→245, 9→600, 6→1325, 3→3250). Empirical refresh from FRED ICE BAML deferred to dedicated calibration Sprint.

### Spec §4 — Algorithm (verbatim, what existing `consolidate()` already does)

```text
Agency → SONAR base notch:
  sonar_notch_base = LOOKUP_TABLE[agency][rating_raw]   # int ∈ [0, 21]

Outlook + watch adjustment:
  notch_adjusted = sonar_notch_base + outlook_mod(outlook) + watch_mod(watch)

Consolidation:
  consolidated_sonar_notch = median(notch_adjusted_i)
  ties → floor(median)
```

Existing `_SP_FITCH_LOOKUP`, `_MOODYS_LOOKUP`, `_DBRS_LOOKUP`, `MODIFIER_OUTLOOK`, `MODIFIER_WATCH` constants in `rating_spread.py` lines 75-200. **Reused verbatim by Sprint 4 backfill orchestrator** — no new compute logic.

### Spec §6 — Edge cases (relevant subset)

| Trigger | Handling |
|---|---|
| `agencies_available < 2` | persist partial with `RATING_SINGLE_AGENCY` flag, cap confidence 0.60 |
| `consolidated_sonar_notch` range ≥ 3 across agencies | flag `RATING_SPLIT` |
| Historical `action_date < 2023-01-01` AND used as primary forward | flag `BACKFILL_STALE` (spec §2 v0.2 source selection) |
| `methodology_version` armazenada ≠ runtime | `VersionMismatchError` |
| Connector `fetched_at` > 7 days from `date` | per spec §2 precondition; for backfill ALL historical actions, use `fetched_at = today`; flag `HISTORICAL_REFETCH` informational |

### Spec §8 — Storage schema (verbatim, 3 tables)

```sql
CREATE TABLE ratings_agency_raw (
    id INTEGER NOT NULL PRIMARY KEY,
    rating_id VARCHAR(36) NOT NULL,         -- uuid4, shared across consolidation
    country_code VARCHAR(2) NOT NULL,
    date DATE NOT NULL,
    agency VARCHAR(8) NOT NULL,             -- 'SP' | 'MOODYS' | 'FITCH' | 'DBRS'
    rating_raw VARCHAR(16) NOT NULL,
    sonar_notch_base INTEGER NOT NULL,
    sonar_notch_adjusted REAL NOT NULL,
    rating_type VARCHAR(2) NOT NULL,        -- 'FC' | 'LC'
    outlook VARCHAR(16) NOT NULL,
    watch VARCHAR(20),
    action_date DATE NOT NULL,
    methodology_version VARCHAR(32) NOT NULL,
    confidence FLOAT NOT NULL,
    flags TEXT,
    -- ... (see existing models.py:242)
);

CREATE TABLE ratings_consolidated (
    id INTEGER NOT NULL PRIMARY KEY,
    rating_id VARCHAR(36) NOT NULL UNIQUE,
    country_code VARCHAR(2) NOT NULL,
    date DATE NOT NULL,
    rating_type VARCHAR(2) NOT NULL,
    consolidated_sonar_notch FLOAT NOT NULL,
    notch_fractional FLOAT NOT NULL,
    agencies_count INTEGER NOT NULL,
    agencies_json TEXT NOT NULL,
    outlook_composite VARCHAR(16) NOT NULL,
    watch_composite VARCHAR(20),
    default_spread_bps INTEGER,             -- from calibration lookup
    calibration_date DATE,
    rating_cds_deviation_pct FLOAT,
    methodology_version VARCHAR(32) NOT NULL,
    confidence FLOAT NOT NULL,
    flags TEXT,
    UNIQUE (country_code, date, rating_type, methodology_version)
    -- already in models.py:287
);

CREATE TABLE ratings_spread_calibration (
    -- already in models.py:354
    -- 22 rows expected (notch 0-21) per calibration_date
);
```

---

## 4. Implementation steps (deterministic)

### Step 0 — Worktree seed (5min)

```bash
cd /home/macro/projects/sonar-sprint-4
mkdir -p data
ln -sf /home/macro/projects/sonar-engine/data/sonar-dev.db data/sonar-dev.db
ln -sf /home/macro/projects/sonar-engine/.env .env
ln -sf /home/macro/projects/sonar-engine/.venv .venv
source .venv/bin/activate
which sonar
python -c "import sonar; print(sonar.__file__)"
# Expected: /home/macro/projects/sonar-engine/src/sonar/__init__.py
```

### Step 1 — Audit current state (15min)

```bash
# 1. Confirm TE_API_KEY present in .env
grep "TE_API_KEY" .env | head -1

# 2. Verify TE connector exists + has BASE_URL
grep -n "BASE_URL\|tradingeconomics.com" src/sonar/connectors/te.py | head -10

# 3. Check existing rating_spread.py constants (will be reused)
grep -n "_SP_FITCH_LOOKUP\|_MOODYS_LOOKUP\|_DBRS_LOOKUP\|APRIL_2026_CALIBRATION\|MODIFIER_OUTLOOK\|MODIFIER_WATCH" src/sonar/overlays/rating_spread.py | head -10

# 4. Verify ORM classes present
grep -n "^class.*Rating\|^class.*Spread" src/sonar/db/models.py

# 5. Verify all 3 tables empty
sqlite3 data/sonar-dev.db <<'EOF'
SELECT 'agency_raw' tbl, COUNT(*) FROM ratings_agency_raw
UNION ALL SELECT 'consolidated', COUNT(*) FROM ratings_consolidated
UNION ALL SELECT 'calibration', COUNT(*) FROM ratings_spread_calibration;
EOF

# 6. Check existing TE connector country canonicalization (need this for ISO α-2)
grep -n "_canonicalize_country_iso\|TE_COUNTRY_NAME_MAP" src/sonar/connectors/te.py | head -5

# 7. Check overlays/rating_spread/ doesn't exist (we create as directory)
ls src/sonar/overlays/rating_spread/ 2>&1
```

Report findings before Step 2. **Critical**: if TE_COUNTRY_NAME_MAP only covers ~15 countries (per audit context), Sprint 4 needs to extend mapping for 160 countries OR use TE country name → ISO α-2 fallback strategy.

### Step 2 — Extend TE connector (90min)

Add to `src/sonar/connectors/te.py` (alongside existing `fetch_sovereign_yield_historical`, `fetch_indicator`, etc.):

```python
@dataclass(frozen=True, slots=True)
class TERatingCurrent:
    """Current sovereign rating snapshot per /ratings endpoint."""
    country: str
    te_score: int | None  # TE proprietary 0-100 (ignore for SONAR consolidation)
    te_outlook: str
    sp_rating: str          # raw token (e.g. "AA+", "BB-") or empty
    sp_outlook: str
    moodys_rating: str      # raw token (e.g. "Aa1", "Baa3") or empty
    moodys_outlook: str
    fitch_rating: str
    fitch_outlook: str
    dbrs_rating: str        # raw token (e.g. "AA (high)", "BBB (low)") or empty
    dbrs_outlook: str


@dataclass(frozen=True, slots=True)
class TERatingHistoricalAction:
    """Single historical rating action per /ratings/historical/{country} endpoint."""
    country: str
    action_date: date
    agency: str             # 'S&P' | "Moody's" | 'Fitch' | 'DBRS'
    rating_raw: str
    outlook: str            # may include 'Watch' suffix


class TEConnector:
    # ... existing code ...

    async def fetch_sovereign_ratings_current(self) -> list[TERatingCurrent]:
        """Fetch current sovereign ratings snapshot for all 160 countries.

        Endpoint: GET /ratings
        Cached aggressively (refresh daily; ratings move slowly).
        """
        cache_key = f"te:ratings:current"
        cached = self.cache.get(cache_key)
        if cached is not None:
            log.debug("te.ratings.current.cache_hit")
            return cast(list[TERatingCurrent], cached)

        url = f"{self.BASE_URL}/ratings"
        params = {"c": self.api_key, "f": "json"}

        r = await self.client.get(url, params=params)
        r.raise_for_status()
        data = r.json()

        results = []
        for item in data:
            results.append(TERatingCurrent(
                country=item.get("Country", ""),
                te_score=int(item["TE"]) if item.get("TE") else None,
                te_outlook=item.get("TE_Outlook", ""),
                sp_rating=item.get("SP", ""),
                sp_outlook=item.get("SP_Outlook", ""),
                moodys_rating=item.get("Moodys", ""),
                moodys_outlook=item.get("Moodys_Outlook", ""),
                fitch_rating=item.get("Fitch", ""),
                fitch_outlook=item.get("Fitch_Outlook", ""),
                dbrs_rating=item.get("DBRS", ""),
                dbrs_outlook=item.get("DBRS_Outlook", ""),
            ))

        self.cache.set(cache_key, results, ttl=24 * 3600)  # 24h
        log.info("te.ratings.current.fetched", count=len(results))
        return results

    async def fetch_sovereign_ratings_historical(
        self, country: str
    ) -> list[TERatingHistoricalAction]:
        """Fetch historical rating actions for a single country.

        Endpoint: GET /ratings/historical/{country}
        country: TE-canonical lowercase name (e.g. 'portugal', 'united states')
        Returns: list of actions in API order (typically descending by date).
        Cached aggressively (refresh weekly per country; historical immutable).
        """
        cache_key = f"te:ratings:historical:{country.lower()}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            log.debug("te.ratings.historical.cache_hit", country=country)
            return cast(list[TERatingHistoricalAction], cached)

        url = f"{self.BASE_URL}/ratings/historical/{country.lower()}"
        params = {"c": self.api_key, "f": "json"}

        r = await self.client.get(url, params=params)
        if r.status_code == 404:
            log.info("te.ratings.historical.no_data", country=country)
            return []
        r.raise_for_status()
        data = r.json()

        results = []
        for item in data:
            try:
                # TE date format: "MM/DD/YYYY"
                date_str = item["Date"]
                m, d, y = date_str.split("/")
                action_date = date(int(y), int(m), int(d))

                results.append(TERatingHistoricalAction(
                    country=item.get("Country", country),
                    action_date=action_date,
                    agency=item.get("Agency", ""),
                    rating_raw=item.get("Rating", ""),
                    outlook=item.get("Outlook", ""),
                ))
            except (KeyError, ValueError) as e:
                log.warning("te.ratings.historical.parse_error", item=item, error=str(e))
                continue

        self.cache.set(cache_key, results, ttl=7 * 24 * 3600)  # 7d
        log.info("te.ratings.historical.fetched", country=country, actions=len(results))
        return results
```

Test smoke against Portugal + 2 other countries (US, Argentina) before backfill.

### Step 3 — Country name → ISO α-2 mapping (30min)

TE API returns country names ("Portugal", "United States", etc.). Spec requires ISO α-2 ("PT", "US", etc.). Existing `TE_COUNTRY_NAME_MAP` in te.py covers ~15 countries (audit Step 1).

For Sprint 4, **extend mapping to 160 countries** OR build `_te_country_to_iso(name) → str | None` helper using `pycountry` library:

```python
# Option A: extend TE_COUNTRY_NAME_MAP manually (~160 entries)
# Option B: use pycountry library for fuzzy match
import pycountry

def _te_country_to_iso(name: str) -> str | None:
    """Map TE country name to ISO α-2."""
    # Manual overrides for TE-specific names
    overrides = {
        "United States": "US",
        "Czech Republic": "CZ",
        "South Korea": "KR",
        "Russia": "RU",
        # ... add as discovered during testing
    }
    if name in overrides:
        return overrides[name]

    try:
        country = pycountry.countries.search_fuzzy(name)[0]
        return country.alpha_2
    except (LookupError, IndexError):
        return None
```

**Recommendation**: Option B (`pycountry`) for breadth + add overrides for edge cases. Add `pycountry` dependency only if not already present.

**Critical**: handle TE country names that don't map cleanly. Log warnings + skip those rows. Sprint 4 acceptance allows ~5 unmapped countries gracefully.

### Step 4 — Outlook + Watch parsing (30min)

TE returns `Outlook` field as combined string. Examples observed:
- "Stable"
- "Positive"
- "Negative"
- "N/A" (treat as "stable")
- "Negative Watch" (combined outlook + watch flag)
- "Stable Watch"
- (empty)

Parse logic:

```python
def _parse_te_outlook(outlook_raw: str) -> tuple[str, str | None]:
    """Parse TE outlook field into (outlook, watch).

    Returns:
        (outlook, watch) where:
        - outlook ∈ {'positive', 'stable', 'negative', 'developing'}
        - watch ∈ {'watch_positive', 'watch_negative', 'watch_developing', None}
    """
    raw = outlook_raw.strip().lower()

    if not raw or raw == "n/a":
        return ("stable", None)

    # Detect watch
    watch = None
    if "watch" in raw:
        if "positive" in raw:
            watch = "watch_positive"
        elif "negative" in raw:
            watch = "watch_negative"
        elif "developing" in raw:
            watch = "watch_developing"
        # Strip 'watch' from raw for outlook extraction
        raw = raw.replace("watch", "").strip()

    # Extract outlook
    if "positive" in raw:
        outlook = "positive"
    elif "negative" in raw:
        outlook = "negative"
    elif "developing" in raw:
        outlook = "developing"
    else:
        outlook = "stable"

    return (outlook, watch)
```

### Step 5 — Backfill orchestrator (90min)

Create `src/sonar/overlays/rating_spread/__init__.py` (NEW — convert flat module to directory):

```python
"""L2 rating-spread overlay package.

Re-exports public surface from existing rating_spread.py module
(to be renamed to _core.py post-Sprint 4 if package convention adopted).

Sprint 4 adds:
- backfill orchestrator
- TE-driven population
"""
from sonar.overlays.rating_spread._core import (
    AGENCY_LOOKUP,
    APRIL_2026_CALIBRATION,
    METHODOLOGY_VERSION_AGENCY,
    METHODOLOGY_VERSION_CALIBRATION,
    METHODOLOGY_VERSION_CONSOLIDATED,
    MODIFIER_OUTLOOK,
    MODIFIER_WATCH,
    ConsolidatedRating,
    InvalidRatingTokenError,
    RatingAgencyRaw,
    consolidate,
    lookup_default_spread_bps,
    notch_to_grade,
)
from sonar.overlays.rating_spread.backfill import (
    backfill_te_current_snapshot,
    backfill_te_historical,
    backfill_calibration_april_2026,
    TERatingsBackfillResult,
)

__all__ = [
    # existing exports
    "AGENCY_LOOKUP", "APRIL_2026_CALIBRATION",
    "METHODOLOGY_VERSION_AGENCY", "METHODOLOGY_VERSION_CALIBRATION",
    "METHODOLOGY_VERSION_CONSOLIDATED",
    "MODIFIER_OUTLOOK", "MODIFIER_WATCH",
    "ConsolidatedRating", "InvalidRatingTokenError", "RatingAgencyRaw",
    "consolidate", "lookup_default_spread_bps", "notch_to_grade",
    # new Sprint 4 exports
    "backfill_te_current_snapshot", "backfill_te_historical",
    "backfill_calibration_april_2026", "TERatingsBackfillResult",
]
```

**Critical decision**: rename existing `rating_spread.py` → `rating_spread/_core.py` to convert flat module to package. **Risk**: 9 import sites in repo (per Sprint 4 audit). Decision per Sprint 3 lesson: **defer rename** (Path B blast radius).

**Alternative simpler**: keep `rating_spread.py` as flat module, create **separate** `rating_spread_backfill.py` flat sibling. Less elegant but zero refactor.

Brief recommends **flat sibling** approach to match Sprint 2 NSS pattern (nss.py + nss_real_writer.py + nss_curves_backfill.py — all flat).

Create `src/sonar/overlays/rating_spread_backfill.py`:

```python
"""TE-driven rating-spread backfill orchestrator.

Sprint 4 scope:
- Step A: fetch TE current snapshot (160 countries × 4 agencies)
- Step B: persist agency_raw rows for current snapshot
- Step C: fetch TE historical per country (loop)
- Step D: persist historical actions
- Step E: invoke consolidate() for each (country, action_date, rating_type)
- Step F: persist ratings_consolidated rows
- Step G: seed ratings_spread_calibration from APRIL_2026_CALIBRATION

Idempotent via UNIQUE constraints on all 3 tables.
"""

from datetime import date as date_type, datetime
from dataclasses import dataclass
from uuid import uuid4
from typing import Optional

import structlog
from sqlalchemy.orm import Session

from sonar.connectors.te import (
    TEConnector,
    TERatingCurrent,
    TERatingHistoricalAction,
)
from sonar.db.models import (
    RatingsAgencyRaw,
    RatingsConsolidated,
    RatingsSpreadCalibration,
)
from sonar.overlays.rating_spread import (
    AGENCY_LOOKUP,
    APRIL_2026_CALIBRATION,
    METHODOLOGY_VERSION_AGENCY,
    METHODOLOGY_VERSION_CALIBRATION,
    METHODOLOGY_VERSION_CONSOLIDATED,
    MODIFIER_OUTLOOK,
    MODIFIER_WATCH,
    consolidate,
    InvalidRatingTokenError,
)
from sonar.overlays.exceptions import InsufficientDataError

log = structlog.get_logger()


@dataclass(frozen=True)
class TERatingsBackfillResult:
    agency_raw_persisted: int
    agency_raw_skipped_existing: int
    agency_raw_skipped_invalid: int
    consolidated_persisted: int
    consolidated_skipped_insufficient: int
    countries_processed: int
    countries_unmappable: int
    historical_actions_persisted: int


# Manual ISO α-2 overrides for TE country names not in pycountry standard
TE_COUNTRY_OVERRIDES = {
    "United States": "US",
    "United Kingdom": "GB",
    "South Korea": "KR",
    "Czech Republic": "CZ",
    # ... extend during testing
}


def _te_country_to_iso(te_name: str) -> Optional[str]:
    """Map TE country name to ISO α-2."""
    if te_name in TE_COUNTRY_OVERRIDES:
        return TE_COUNTRY_OVERRIDES[te_name]
    try:
        import pycountry
        results = pycountry.countries.search_fuzzy(te_name)
        if results:
            return results[0].alpha_2
    except (LookupError, ImportError):
        pass
    log.warning("te.country.unmappable", te_name=te_name)
    return None


def _parse_te_outlook(outlook_raw: str) -> tuple[str, Optional[str]]:
    """Parse TE outlook into (outlook, watch). See brief Step 4."""
    # ... implementation per Step 4 ...


async def backfill_te_current_snapshot(
    session: Session, *, te_connector: TEConnector
) -> TERatingsBackfillResult:
    """Step A+B: fetch current snapshot, persist agency_raw."""

    snapshot_date = date_type.today()  # current snapshot uses today as effective date
    snapshot = await te_connector.fetch_sovereign_ratings_current()

    persisted = 0
    skipped_existing = 0
    skipped_invalid = 0
    countries_unmappable = 0

    for ranking in snapshot:
        country_iso = _te_country_to_iso(ranking.country)
        if country_iso is None:
            countries_unmappable += 1
            continue

        rating_id = uuid4().hex

        # Loop over 4 agencies
        for agency_te, rating_raw, outlook_raw in [
            ("SP", ranking.sp_rating, ranking.sp_outlook),
            ("MOODYS", ranking.moodys_rating, ranking.moodys_outlook),
            ("FITCH", ranking.fitch_rating, ranking.fitch_outlook),
            ("DBRS", ranking.dbrs_rating, ranking.dbrs_outlook),
        ]:
            if not rating_raw:  # empty = agency doesn't rate this country
                continue

            try:
                lookup_table = AGENCY_LOOKUP[agency_te]
                sonar_notch_base = lookup_table[rating_raw]
            except (KeyError, InvalidRatingTokenError):
                log.warning(
                    "te.snapshot.invalid_token",
                    country=country_iso, agency=agency_te, rating_raw=rating_raw,
                )
                skipped_invalid += 1
                continue

            outlook, watch = _parse_te_outlook(outlook_raw)

            outlook_mod = MODIFIER_OUTLOOK.get(outlook, 0.0)
            watch_mod = MODIFIER_WATCH.get(watch, 0.0) if watch else 0.0
            sonar_notch_adjusted = sonar_notch_base + outlook_mod + watch_mod

            # Idempotency check
            existing = session.query(RatingsAgencyRaw).filter_by(
                country_code=country_iso,
                date=snapshot_date,
                agency=agency_te,
                rating_type="FC",
                methodology_version=METHODOLOGY_VERSION_AGENCY,
            ).first()

            if existing:
                skipped_existing += 1
                continue

            row = RatingsAgencyRaw(
                rating_id=rating_id,
                country_code=country_iso,
                date=snapshot_date,
                agency=agency_te,
                rating_raw=rating_raw,
                sonar_notch_base=sonar_notch_base,
                sonar_notch_adjusted=sonar_notch_adjusted,
                rating_type="FC",
                outlook=outlook,
                watch=watch,
                action_date=snapshot_date,  # snapshot date for current
                methodology_version=METHODOLOGY_VERSION_AGENCY,
                confidence=0.85,
                flags=None,
                fetched_at=datetime.utcnow(),
            )
            session.merge(row)
            persisted += 1

    session.commit()

    return TERatingsBackfillResult(
        agency_raw_persisted=persisted,
        agency_raw_skipped_existing=skipped_existing,
        agency_raw_skipped_invalid=skipped_invalid,
        consolidated_persisted=0,  # done in separate step
        consolidated_skipped_insufficient=0,
        countries_processed=len(snapshot),
        countries_unmappable=countries_unmappable,
        historical_actions_persisted=0,
    )


async def backfill_te_historical(
    session: Session, *, te_connector: TEConnector, country_iso_list: list[str]
) -> TERatingsBackfillResult:
    """Step C+D: fetch historical per country, persist actions."""

    persisted = 0

    for country_iso in country_iso_list:
        # Map back ISO → TE name (need reverse lookup)
        te_name = _iso_to_te_name(country_iso)
        if not te_name:
            continue

        actions = await te_connector.fetch_sovereign_ratings_historical(te_name)

        for action in actions:
            agency_norm = _normalize_agency(action.agency)  # 'S&P' → 'SP', "Moody's" → 'MOODYS'

            try:
                lookup_table = AGENCY_LOOKUP[agency_norm]
                sonar_notch_base = lookup_table[action.rating_raw]
            except (KeyError, InvalidRatingTokenError):
                log.warning(
                    "te.historical.invalid_token",
                    country=country_iso, agency=agency_norm, rating_raw=action.rating_raw,
                )
                continue

            outlook, watch = _parse_te_outlook(action.outlook)
            outlook_mod = MODIFIER_OUTLOOK.get(outlook, 0.0)
            watch_mod = MODIFIER_WATCH.get(watch, 0.0) if watch else 0.0
            sonar_notch_adjusted = sonar_notch_base + outlook_mod + watch_mod

            # Use action_date as both date and action_date
            existing = session.query(RatingsAgencyRaw).filter_by(
                country_code=country_iso,
                date=action.action_date,
                agency=agency_norm,
                rating_type="FC",
            ).first()

            if existing:
                continue

            row = RatingsAgencyRaw(
                rating_id=uuid4().hex,
                country_code=country_iso,
                date=action.action_date,
                agency=agency_norm,
                rating_raw=action.rating_raw,
                sonar_notch_base=sonar_notch_base,
                sonar_notch_adjusted=sonar_notch_adjusted,
                rating_type="FC",
                outlook=outlook,
                watch=watch,
                action_date=action.action_date,
                methodology_version=METHODOLOGY_VERSION_AGENCY,
                confidence=0.85,
                flags="HISTORICAL_REFETCH" if action.action_date < date_type(2023, 1, 1) else None,
                fetched_at=datetime.utcnow(),
            )
            session.merge(row)
            persisted += 1

    session.commit()
    return TERatingsBackfillResult(
        # ... fill counters
    )


async def backfill_consolidate(session: Session) -> TERatingsBackfillResult:
    """Step E+F: invoke consolidate() for each (country, action_date) tuple where ≥2 agencies present.

    For each unique (country_code, date, rating_type) in ratings_agency_raw with ≥ MIN_AGENCIES_FOR_CONSOLIDATION agencies present, build ConsolidatedRating + persist.
    """

    # Identify candidate (country, date, rating_type) tuples
    from sqlalchemy import select, func

    candidates = session.query(
        RatingsAgencyRaw.country_code,
        RatingsAgencyRaw.date,
        RatingsAgencyRaw.rating_type,
        func.count().label("n_agencies"),
    ).group_by(
        RatingsAgencyRaw.country_code,
        RatingsAgencyRaw.date,
        RatingsAgencyRaw.rating_type,
    ).having(func.count() >= 2).all()

    persisted = 0

    for country_iso, action_date, rating_type, n_agencies in candidates:
        # Fetch all agency rows for this tuple
        rows = session.query(RatingsAgencyRaw).filter_by(
            country_code=country_iso,
            date=action_date,
            rating_type=rating_type,
        ).all()

        # Build inputs for existing consolidate() function
        agency_inputs = [
            RatingAgencyRaw(
                country_code=r.country_code,
                date=r.date,
                agency=r.agency,
                rating_raw=r.rating_raw,
                rating_type=r.rating_type,
                outlook=r.outlook,
                watch=r.watch,
                action_date=r.action_date,
            )
            for r in rows
        ]

        try:
            consolidated = consolidate(
                agency_inputs,
                calibration=APRIL_2026_CALIBRATION,
            )
        except InsufficientDataError:
            continue

        # Idempotency check
        existing = session.query(RatingsConsolidated).filter_by(
            country_code=country_iso,
            date=action_date,
            rating_type=rating_type,
            methodology_version=METHODOLOGY_VERSION_CONSOLIDATED,
        ).first()

        if existing:
            continue

        # Persist consolidated row (use existing rating_spread.persist helpers)
        # ... (mirror existing pattern from db/persistence.py)
        persisted += 1

    session.commit()
    return TERatingsBackfillResult(
        # ...
    )


def backfill_calibration_april_2026(session: Session) -> int:
    """Step G: seed ratings_spread_calibration from APRIL_2026_CALIBRATION constant."""

    calibration_date = date_type(2026, 4, 1)
    persisted = 0

    for notch_int in range(0, 22):  # 0-21 notches
        existing = session.query(RatingsSpreadCalibration).filter_by(
            notch_int=notch_int,
            calibration_date=calibration_date,
            methodology_version=METHODOLOGY_VERSION_CALIBRATION,
        ).first()

        if existing:
            continue

        # Lookup spread_bps from APRIL_2026_CALIBRATION constant
        # APRIL_2026_CALIBRATION format: dict[notch_int → spread_bps]
        spread_bps = APRIL_2026_CALIBRATION.get(notch_int)
        if spread_bps is None:
            continue

        # Build calibration row (mirror existing models.py:354 schema)
        row = RatingsSpreadCalibration(
            notch_int=notch_int,
            calibration_date=calibration_date,
            default_spread_bps=spread_bps,
            # ... other fields per schema
            methodology_version=METHODOLOGY_VERSION_CALIBRATION,
        )
        session.merge(row)
        persisted += 1

    session.commit()
    return persisted
```

### Step 6 — CLI subcommand (15min)

Extend `src/sonar/cli/backfill.py`:

```python
@app.command(name="rating-spread")
def rating_spread(
    include_historical: bool = typer.Option(
        False,
        "--include-historical",
        help="Fetch historical actions per country (slower; ~30min for 160 countries)",
    ),
    countries: Optional[str] = typer.Option(
        None,
        help="Comma-separated ISO α-2 codes; empty = all 160 countries",
    ),
):
    """Backfill rating-spread tables via TE Premium API."""
    import asyncio
    from sonar.overlays.rating_spread_backfill import (
        backfill_te_current_snapshot,
        backfill_te_historical,
        backfill_consolidate,
        backfill_calibration_april_2026,
    )

    session = get_session()

    # ... wire calls to backfill functions
    typer.echo("Sprint 4 rating-spread backfill complete")
```

### Step 7 — Tests (60min)

Create `tests/unit/test_overlays/test_rating_spread_te.py` — 4 fixtures:

1. **`te_snapshot_pt_current_canonical`** — Portugal snapshot row → 4 agency raw rows (S&P A+ Pos, Moody's A2, Fitch A Pos, DBRS A) + consolidated notch
2. **`te_snapshot_partial_2_agencies`** — small country (e.g. Albania) with 2 agencies present → consolidated with `RATING_SINGLE_AGENCY` flag if <2 agencies, OR partial consolidation if ≥2
3. **`te_outlook_parse_watch`** — TE outlook strings: "Stable", "Negative Watch", "Positive", "N/A" → correct (outlook, watch) tuples
4. **`te_country_unmappable`** — TE country name not in pycountry/overrides → row skipped + warning logged

### Step 8 — Execute backfill against engine DB (5-10 min)

After commit + sprint_merge.sh + on engine main:

```bash
cd /home/macro/projects/sonar-engine
source .venv/bin/activate

# Step 1: current snapshot only first (5 sec)
sonar backfill rating-spread

# Step 2: full historical (30-60min)
sonar backfill rating-spread --include-historical
```

### Step 9 — Tier B verification

```bash
sqlite3 /home/macro/projects/sonar-engine/data/sonar-dev.db <<'EOF'
.mode column
.headers on

-- Coverage
SELECT 'agency_raw' tbl, COUNT(*) FROM ratings_agency_raw
UNION ALL SELECT 'consolidated', COUNT(*) FROM ratings_consolidated
UNION ALL SELECT 'calibration', COUNT(*) FROM ratings_spread_calibration;

-- Country coverage
SELECT COUNT(DISTINCT country_code) AS n_countries FROM ratings_agency_raw;

-- Agency distribution (should show SP/MOODYS/FITCH/DBRS)
SELECT agency, COUNT(*) FROM ratings_agency_raw GROUP BY agency ORDER BY agency;

-- Date range historical
SELECT
  MIN(action_date) AS earliest,
  MAX(action_date) AS latest,
  COUNT(*) AS total_actions
FROM ratings_agency_raw;

-- Sample consolidated (recent 5)
SELECT date, country_code, consolidated_sonar_notch, default_spread_bps, agencies_count, flags
FROM ratings_consolidated
ORDER BY date DESC
LIMIT 5;

-- Calibration check (should be 22 rows)
SELECT calibration_date, COUNT(*) AS n_notches FROM ratings_spread_calibration GROUP BY calibration_date;
EOF
```

Expected:
- `agency_raw`: ~5000+ rows (160 countries × current + ~30 historical actions per country)
- `consolidated`: ~3000+ rows (countries × dates with ≥2 agencies)
- `calibration`: 22 rows (notch 0-21 × 1 calibration_date 2026-04-01)
- `n_countries`: ~155 (5 unmappable acceptable)
- All 4 agencies represented
- Date range: 1986-11-18 to 2026-04-25 (or similar)

---

## 5. Acceptance criteria

### Must pass

1. ✅ `ratings_agency_raw` ≥ 4000 rows
2. ✅ `ratings_consolidated` ≥ 2000 rows (countries × dates with consolidation)
3. ✅ `ratings_spread_calibration` = 22 rows (notch 0-21 × 1 calibration_date)
4. ✅ ≥ 150 distinct countries in agency_raw
5. ✅ All 4 agencies (SP, MOODYS, FITCH, DBRS) represented
6. ✅ 4 fixture tests pass
7. ✅ Pre-commit + pytest green
8. ✅ Merged via sprint_merge.sh

### Out of scope

- TE proprietary score consumption (defer)
- Damodaran historical complement (defer)
- Quarterly calibration refresh automation (defer)
- CDS divergence cross-validation (depends Sprint 5)

### Known limitations

- ~5 countries unmappable (TE name → ISO α-2 fail) — graceful skip + warning
- TE Outlook parsing edge cases logged (~rare malformed strings)
- Forward updates require manual re-run OR future event-driven Sprint
- Spec D0 audit note "TE 4Y stale" must be refreshed in spec doc (CAL-SPEC-RATING-TE-REFRESH)

---

## 6. Risks + mitigations

| Risk | Mitigation |
|---|---|
| TE API rate limit during 160-country historical fetch | Connector cache 7d per country; sequential fetch + 0.5s delay between countries |
| `pycountry` dependency missing — `uv add` would break venv | Check pyproject.toml first; if missing, halt + ask user before adding |
| TE country names with non-standard fuzzy match | Manual TE_COUNTRY_OVERRIDES dict + log warnings for misses |
| TE outlook field unexpected values (per country/agency variations) | Parser defaults to "stable" + None watch when ambiguous |
| Historical action_date < spec freshness threshold (7 days) | Emit `HISTORICAL_REFETCH` flag on rows with action_date < 2023-01-01; informational only |
| Existing `consolidate()` function signature mismatch with spec §4 step 5 | Verified during audit; existing `RatingAgencyRaw` dataclass + `consolidate()` already spec-compliant |
| Migration not needed — 3 tables already exist in DB | Skip Alembic; just populate |
| Spec D0 audit note "TE 4Y stale" outdated | Open CAL-SPEC-RATING-TE-REFRESH per Sprint 4 retrospective |

---

## 7. Dependencies

- **Spec**: [`rating-spread.md`](https://github.com/hugocondesa-debug/sonar-engine/blob/main/docs/specs/overlays/rating-spread.md) v0.2
- **Existing infrastructure**:
  - `connectors/te.py` (extend with 2 new methods)
  - `overlays/rating_spread.py` (391 LOC, untouched — flat sibling pattern)
  - 3 ORM classes (`db/models.py:242, 287, 354`) — schema unchanged
  - Lookup tables `_SP_FITCH_LOOKUP`, `_MOODYS_LOOKUP`, `_DBRS_LOOKUP` reused
  - `APRIL_2026_CALIBRATION` constant reused
- **TE API**: Premium tier confirmed via empirical test (160 countries current + 96 actions Portugal historical 2026-04-25)
- **No new external dependencies** beyond optional `pycountry` (verify before add)

---

## 8. CC prompt template

```
Sprint 4 — L2 Rating-Spread via TE Premium API

Read spec: docs/specs/overlays/rating-spread.md v0.2
Read brief: docs/planning/week11-sprint-4-l2-rating-spread-te-brief.md

Execute 9 steps per brief §4.

Step 0 — Worktree seed (3 symlinks + venv activate; verify TE_API_KEY present in .env).

Step 1 — Audit (7 commands per brief §4 step 1; report findings before Step 2):
- Confirm TE_API_KEY in .env (exists per audit 2026-04-25)
- Verify TE connector BASE_URL
- Check existing rating_spread.py constants (lookup tables, modifiers, calibration)
- Verify 3 ORM classes present (RatingsAgencyRaw, RatingsConsolidated, RatingsSpreadCalibration)
- Confirm 3 tables empty in engine DB
- Check existing TE country canonicalization (TE_COUNTRY_NAME_MAP scope)
- Verify overlays/rating_spread/ directory does NOT exist (use flat sibling pattern, NOT directory refactor)

Step 2 — Extend src/sonar/connectors/te.py with 2 methods:
- fetch_sovereign_ratings_current() → list[TERatingCurrent] (160 countries)
- fetch_sovereign_ratings_historical(country) → list[TERatingHistoricalAction]
- Add 2 dataclasses: TERatingCurrent + TERatingHistoricalAction
- Use existing httpx.AsyncClient + cache pattern from te.py
- 24h cache for current; 7d cache per country for historical
- Error handle: 404 = empty list (some countries unmapped); other = raise

Step 3 — Country name → ISO α-2 mapping helper:
- TE_COUNTRY_OVERRIDES dict (manual for ambiguous names)
- _te_country_to_iso(name) → str | None using pycountry fuzzy match
- IF pycountry not in pyproject.toml → halt + ask user before uv add (Sprint 3 lesson)
- Log warning for unmappable; gracefully skip

Step 4 — Outlook + watch parsing:
- _parse_te_outlook(outlook_raw) → (outlook, watch) tuple
- Handle: 'Stable', 'Positive', 'Negative Watch', 'N/A', empty
- Default to ('stable', None) when ambiguous

Step 5 — Backfill orchestrator src/sonar/overlays/rating_spread_backfill.py (FLAT SIBLING):
- DO NOT convert rating_spread.py to package directory (defer per Sprint 3 lesson)
- backfill_te_current_snapshot(session, te_connector) → TERatingsBackfillResult
- backfill_te_historical(session, te_connector, country_iso_list)
- backfill_consolidate(session) — invoke existing consolidate() for each (country, action_date) tuple
- backfill_calibration_april_2026(session) — seed 22 notches from APRIL_2026_CALIBRATION
- Idempotent via UNIQUE constraints

Step 6 — CLI extension src/sonar/cli/backfill.py:
- Add @app.command(name="rating-spread")
- Args: --include-historical, --countries
- Mirror existing pattern from nss-curves, expinf-us-bei, erp-daily, erp-external

Step 7 — Tests src/sonar/overlays/test_rating_spread_te.py:
- 4 fixtures per brief §4 step 7
- Mock TE responses (synthetic dict→TERatingCurrent/TERatingHistoricalAction)
- Test outlook parsing edge cases
- Test country mapping with overrides + fuzzy

Step 8 — Execute backfill (post-merge, on engine main):
sonar backfill rating-spread (current snapshot only first)
sonar backfill rating-spread --include-historical (then full)

Step 9 — Tier B verification (engine DB):
SQL queries from brief §4 step 9 — expected ~5000 agency_raw, ~2000 consolidated, 22 calibration.

Critical rules:
- KEEP rating_spread.py FLAT — do NOT refactor to directory (Path B blast radius)
- USE existing consolidate() function from rating_spread.py — do NOT reimplement
- USE existing AGENCY_LOOKUP, MODIFIER_OUTLOOK, MODIFIER_WATCH, APRIL_2026_CALIBRATION constants
- TE proprietary score (TE: 40 field) IGNORED for consolidation (spec §2 lists 4 named agencies only)
- venv handling: do NOT run `uv add` from worktree (Sprint 3 lesson). pycountry check pyproject.toml first; halt if missing.
- HALT before commit per CLAUDE.md §5/§7. Report deliverables + tests + Tier B + spec deviations. Await authorization.

Run pytest + pre-commit + sprint_merge.sh (post-authorization).

Tier B targets:
- ratings_agency_raw ≥ 4000 rows
- ratings_consolidated ≥ 2000 rows
- ratings_spread_calibration = 22 rows
- ≥ 150 distinct countries
- All 4 agencies represented

START Step 0 worktree seed. Report Step 1 audit findings before Step 2.
```

---

## 9. Sprint 4 → Sprint 5 (next)

After Sprint 4 merge + Tier B green:

**L2 status**: 4/5 overlays complete (NSS ✓ EXPINF ✓ ERP ✓ rating-spread ✓; CRP remaining)

**Sprint 5** — L2 CRP (4-5h):
- CRP RATING branch consumes Sprint 4 ratings_consolidated → ratings_spread_calibration lookup
- CRP SOV_SPREAD branch consumes NSS Sprint 2 yield_curves_spot
- CRP CDS branch — depends connectors/wgb status check
- Hierarchy best-of: CDS > SOV_SPREAD > RATING

**L2 closure post-Sprint 5** = 5/5 overlays complete. Ready for L0 connectors batch (Wu-Xia/Krippner/HLW/IMF WEO) + L3 monetary M1-M4 rebuild + L3 economic/credit/financial + L4 cycles.

---

**END BRIEF**
