# Sprint 3.1 — L2 ERP External Reference (Damodaran)

**Date**: 2026-04-25 · Week 11 Day 2 · Path 2 (Hybrid 2+3 sequential)
**Spec reference**: New table aligned with [`docs/specs/overlays/erp-daily.md`](https://github.com/hugocondesa-debug/sonar-engine/blob/main/docs/specs/overlays/erp-daily.md) §11 separation of concerns ("compute, don't consume"); external reference is **adjacent** to computed ERP, not replacement.
**Budget**: 2-3h CC autonomous work
**Branch**: `sprint-3-1-erp-external-reference`

---

## 1. Problem statement

Sprint 3 shipped L2 ERP US 4 methods + canonical infrastructure (65 rows × 5 tables). However, output editorially unusable due to data feed staleness (Shiller 22 months stale, FactSet not wired into backfill path). All 65 rows fire `ERP_METHOD_DIVERGENCE` flag (range >400 bps) — spec-compliant signal that upstream data needs upgrade.

Sprint 3.1 ships **adjacent** infrastructure — Damodaran monthly Implied ERP as external reference. Damodaran (NYU Stern, Aswath Damodaran) is industry gold standard for US ERP monthly snapshots; Bloomberg/GS/asset managers all reference it.

**Hybrid Path 2+3 strategy**:
- Sprint 3.1 (this): Damodaran external reference table, immediately editorial-usable
- Sprint 3.2 (next): Wire live FactSet/Yardeni into computed canonical, fix data feeds, achieve methodology convergence vs Damodaran benchmark

Post-3.2: both layers operational. Editorial cites Damodaran (gold standard). Computed canonical signals methodology range_bps. Comparative `computed vs Damodaran` becomes permanent benchmarking infrastructure.

---

## 2. Scope (in / out)

### In scope

1. New ORM class `ERPExternalReferenceRow` + Alembic migration
2. New writer `overlays/erp_external/damodaran.py` consuming existing `connectors/damodaran.fetch_monthly_implied_erp()`
3. Backfill orchestrator `overlays/erp_external/backfill.py` — Damodaran monthly US 2008-09 to 2026-03 (~210 months)
4. CLI extension: `sonar backfill erp-external --source damodaran --start --end`
5. 3 fixture tests
6. Engine DB execution + Tier B verification

### Out of scope

- Bloomberg / Goldman Sachs / Reuters external sources (defer; extensible via `source` column)
- EA/UK/JP external references (defer; Damodaran is US-only)
- Damodaran annual fallback (annual `histimpl.xlsx` covers 1960+; monthly available 2008-09+; for Sprint 3.1 only monthly)
- Live FactSet / Yardeni wire-in (Sprint 3.2)
- Modify `erp_canonical` (Sprint 3 unchanged; spec §11 "compute don't consume" preserved)

---

## 3. Specs referenced

### Damodaran connector (existing, audited 2026-04-25)

```
src/sonar/connectors/damodaran.py:
  HISTIMPL_URL: https://pages.stern.nyu.edu/~adamodar/pc/datasets/histimpl.xlsx (annual since 1960)
  IMPLPREM_URL_TEMPLATE: https://pages.stern.nyu.edu/~adamodar/pc/implprem/ERP{mon}{yy}.xlsx (monthly since 2008-09)

  fetch_annual_erp(year) → DamodaranERPRow | None
  fetch_monthly_implied_erp(year, month) → DamodaranMonthlyERPRow | None
```

### Spec erp-daily.md §11 (verbatim, separation of concerns)

> "Does not consume Damodaran monthly como input — só cross-validation. `overlays/erp-daily` é *computed*, não *consumed* (princípio `compute, don't consume`)."

**Sprint 3.1 respects this**: `erp_canonical` continues 100% computed (4 methods median). New `erp_external_reference` is **separate adjacent table** for editorial / benchmarking. Spec §11 not violated.

### Spec erp-daily.md §4 step 8 (Damodaran cross-val context)

> "Se `histimpl.xlsx` tem row para `date.month`: compute `xval_deviation_bps = |erp_dcf_bps − damodaran_us_erp_bps|` (US only); flag `XVAL_DRIFT` se `> 20 bps`."

Sprint 3 already uses Damodaran annual for xval (`xval_deviation_bps` in `erp_canonical`). Sprint 3.1 adds **monthly Damodaran as standalone reference** — same source, different granularity, different purpose (xval vs reference).

### Pattern conventions

- **Hierarchy best-of**: `erp_external_reference.source` column extensible (future: bloomberg, gs_research, reuters_consensus)
- **Versioning per-table**: `methodology_version='DAMODARAN_MONTHLY_v0.1'`
- **Units convention**: `erp_bps INTEGER`, `int(round(decimal × 10_000))` per `conventions/units.md`

---

## 4. Implementation steps (deterministic)

### Step 0 — Worktree seed (5min)

```bash
cd /home/macro/projects/sonar-sprint-3-1
mkdir -p data
ln -sf /home/macro/projects/sonar-engine/data/sonar-dev.db data/sonar-dev.db
ln -sf /home/macro/projects/sonar-engine/.env .env
ln -sf /home/macro/projects/sonar-engine/.venv .venv
source .venv/bin/activate
which sonar
```

Verify Sprint 3 already merged (engine main has `erp_canonical` populated 65 rows):

```bash
sqlite3 data/sonar-dev.db "SELECT COUNT(*) FROM erp_canonical WHERE country_code='US';"
# Expected: 65
```

If 0 → Sprint 3 not merged; halt + investigate.

### Step 1 — Audit current state (10min)

```bash
# 1. Check if erp_external_reference table already exists
sqlite3 data/sonar-dev.db ".tables" | grep -i external

# 2. Verify Damodaran connector entry points
grep -n "fetch_monthly_implied_erp\|DamodaranMonthlyERPRow" src/sonar/connectors/damodaran.py | head -10

# 3. Check Alembic migration directory + last revision
ls alembic/versions/ | tail -5
sqlite3 data/sonar-dev.db "SELECT version_num FROM alembic_version;"

# 4. Verify no existing erp_external module
ls src/sonar/overlays/erp_external/ 2>&1

# 5. Check Sprint 3 erp_daily structure (reference pattern)
ls src/sonar/overlays/erp_daily/
cat src/sonar/overlays/erp_daily/__init__.py
```

Report findings before Step 2.

### Step 2 — ORM class + Alembic migration (30min)

Add class to `src/sonar/db/models.py` (after existing ERPCanonical class):

```python
class ERPExternalReferenceRow(Base):
    """External-reference ERP from third-party providers (e.g. Damodaran).

    Separate from computed erp_canonical (spec §11 "compute, don't consume").
    Editorial + benchmarking purposes.

    Sprint 3.1: Damodaran monthly US (2008-09 onwards).
    Future: extensible via source column to Bloomberg/GS/Reuters.
    """

    __tablename__ = "erp_external_reference"

    id = Column(Integer, primary_key=True, autoincrement=True)
    market_index = Column(String, nullable=False)
    country_code = Column(String(2), nullable=False)
    date = Column(Date, nullable=False)
    source = Column(String, nullable=False)  # 'damodaran_monthly' | future extensible
    erp_bps = Column(Integer, nullable=False)
    publication_date = Column(Date)  # when source published
    source_file = Column(String)  # e.g. 'ERPFeb26.xlsx' for traceability
    methodology_version = Column(String(48), nullable=False)  # 'DAMODARAN_MONTHLY_v0.1'
    confidence = Column(Float, nullable=False)
    flags = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "market_index", "date", "source",
            name="uq_erp_external_mds",
        ),
        CheckConstraint(
            "confidence BETWEEN 0 AND 1",
            name="ck_erp_external_conf",
        ),
        Index("idx_erp_external_md", "market_index", "date", "source"),
    )
```

Create Alembic migration:

```bash
alembic revision --autogenerate -m "Sprint 3.1: erp_external_reference table"
# Inspect generated migration; trim to only erp_external_reference creation
alembic upgrade head
```

Verify schema:
```bash
sqlite3 data/sonar-dev.db ".schema erp_external_reference"
```

### Step 3 — Damodaran writer (45min)

Create `src/sonar/overlays/erp_external/__init__.py`:

```python
"""L2 ERP external reference overlay.

Sprint 3.1: Damodaran monthly US.
Future extensible: Bloomberg, GS, Reuters consensus (via source column).
"""

from sonar.overlays.erp_external.damodaran import build_damodaran_external_row

__all__ = ["build_damodaran_external_row"]
```

Create `src/sonar/overlays/erp_external/damodaran.py`:

```python
"""Damodaran monthly ERP external reference writer.

Consumes connectors/damodaran.fetch_monthly_implied_erp.
Emits ERPExternalReferenceRow with source='damodaran_monthly'.
"""

from datetime import date as date_type, datetime
from sqlalchemy.orm import Session

from sonar.connectors.damodaran import DamodaranConnector, DamodaranMonthlyERPRow
from sonar.db.models import ERPExternalReferenceRow
from sonar.overlays.exceptions import DataUnavailableError, InsufficientDataError


def build_damodaran_external_row(
    *,
    year: int,
    month: int,
    damodaran_row: DamodaranMonthlyERPRow,
) -> ERPExternalReferenceRow:
    """Build ERPExternalReferenceRow from a Damodaran monthly snapshot.

    Args:
        year: Calendar year of the Damodaran snapshot.
        month: 1-12.
        damodaran_row: Result from DamodaranConnector.fetch_monthly_implied_erp.

    Returns:
        ERPExternalReferenceRow ready for session.merge.

    Raises:
        InsufficientDataError if implied_erp_decimal is None or invalid.
    """
    if damodaran_row.implied_erp_decimal is None:
        raise InsufficientDataError(
            f"Damodaran monthly row {year}-{month:02d}: implied_erp_decimal is None"
        )

    erp_bps = int(round(damodaran_row.implied_erp_decimal * 10_000))

    # Damodaran row is for start-of-month
    snapshot_date = date_type(year, month, 1)

    # Confidence: 0.95 base (Damodaran gold-standard for US monthly ERP)
    # Deduct 0.05 if source_file naming irregular OR fields incomplete
    confidence = 0.95
    flags = []

    return ERPExternalReferenceRow(
        market_index="SPX",  # Damodaran covers US S&P 500
        country_code="US",
        date=snapshot_date,
        source="damodaran_monthly",
        erp_bps=erp_bps,
        publication_date=damodaran_row.publication_date if hasattr(damodaran_row, 'publication_date') else None,
        source_file=damodaran_row.source_file,
        methodology_version="DAMODARAN_MONTHLY_v0.1",
        confidence=confidence,
        flags=",".join(sorted(flags)) if flags else None,
    )
```

### Step 4 — Backfill orchestrator (30min)

Create `src/sonar/overlays/erp_external/backfill.py`:

```python
"""Damodaran monthly ERP backfill orchestrator.

Iterates calendar months in window, fetches via existing connector,
persists via build_damodaran_external_row.

Idempotent via UNIQUE (market_index, date, source).
"""

from datetime import date as date_type
from dataclasses import dataclass

import structlog
from sqlalchemy.orm import Session

from sonar.connectors.damodaran import DamodaranConnector
from sonar.connectors.cache import ConnectorCache
from sonar.db.models import ERPExternalReferenceRow
from sonar.overlays.erp_external.damodaran import build_damodaran_external_row
from sonar.overlays.exceptions import DataUnavailableError, InsufficientDataError

log = structlog.get_logger()


@dataclass(frozen=True)
class DamodaranBackfillResult:
    persisted: int
    skipped_existing: int
    skipped_unavailable: int
    skipped_insufficient: int
    errors: int


# Damodaran monthly ERP series starts Sep 2008
DAMODARAN_MONTHLY_START = date_type(2008, 9, 1)


def _iter_months(start: date_type, end: date_type):
    """Yield (year, month) tuples from start month to end month inclusive."""
    y, m = start.year, start.month
    end_y, end_m = end.year, end.month
    while (y, m) <= (end_y, end_m):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


async def backfill_damodaran_monthly(
    session: Session,
    *,
    cache_dir,
    start: date_type,
    end: date_type,
) -> DamodaranBackfillResult:
    """Backfill Damodaran monthly external reference for date range.

    Args:
        session: SQLAlchemy session
        cache_dir: Path for connector cache
        start: Earliest month (clamped to DAMODARAN_MONTHLY_START)
        end: Latest month (typically <= today; lag ~2 months for current)

    Returns:
        DamodaranBackfillResult counts.
    """
    if start < DAMODARAN_MONTHLY_START:
        log.warning(
            "damodaran.backfill.start_clamped",
            requested=start.isoformat(),
            clamped_to=DAMODARAN_MONTHLY_START.isoformat(),
        )
        start = DAMODARAN_MONTHLY_START

    connector = DamodaranConnector(cache_dir=cache_dir)
    persisted = skipped_existing = skipped_unavailable = skipped_insufficient = errors = 0

    try:
        for year, month in _iter_months(start, end):
            target_date = date_type(year, month, 1)

            # Idempotency check
            existing = session.query(ERPExternalReferenceRow).filter_by(
                market_index="SPX",
                country_code="US",
                date=target_date,
                source="damodaran_monthly",
            ).first()
            if existing:
                skipped_existing += 1
                continue

            try:
                damodaran_row = await connector.fetch_monthly_implied_erp(year, month)
                if damodaran_row is None:
                    log.info("damodaran.month.unavailable", year=year, month=month)
                    skipped_unavailable += 1
                    continue
            except DataUnavailableError as exc:
                log.warning(
                    "damodaran.fetch.error",
                    year=year, month=month, error=str(exc),
                )
                skipped_unavailable += 1
                continue

            try:
                row = build_damodaran_external_row(
                    year=year, month=month, damodaran_row=damodaran_row,
                )
                session.merge(row)
                persisted += 1
                log.info(
                    "damodaran.persisted",
                    year=year, month=month, erp_bps=row.erp_bps,
                )
            except InsufficientDataError as exc:
                log.warning(
                    "damodaran.insufficient",
                    year=year, month=month, error=str(exc),
                )
                skipped_insufficient += 1

        session.commit()
    finally:
        await connector.aclose()

    return DamodaranBackfillResult(
        persisted=persisted,
        skipped_existing=skipped_existing,
        skipped_unavailable=skipped_unavailable,
        skipped_insufficient=skipped_insufficient,
        errors=errors,
    )
```

### Step 5 — CLI extension (15min)

Extend `src/sonar/cli/backfill.py` (existing typer subapp). Add:

```python
@app.command(name="erp-external")
def erp_external(
    source: str = typer.Option(
        "damodaran",
        help="External source: damodaran (only option Sprint 3.1)",
    ),
    start: str = typer.Option(
        "2008-09-01",
        help="Start month (YYYY-MM-DD; clamped to Damodaran 2008-09 monthly start)",
    ),
    end: str = typer.Option(
        ...,
        help="End month (YYYY-MM-DD; typically last published month, ~2-month lag)",
    ),
):
    """Backfill external ERP reference table (Damodaran monthly US)."""
    if source != "damodaran":
        typer.echo(f"Unsupported source: {source}. Available: damodaran", err=True)
        raise typer.Exit(1)

    from sonar.overlays.erp_external.backfill import backfill_damodaran_monthly

    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)

    session = get_session()
    cache_dir = Path(os.environ.get("SONAR_CACHE_DIR", "/tmp/sonar-cache"))

    result = asyncio.run(
        backfill_damodaran_monthly(
            session=session,
            cache_dir=cache_dir,
            start=start_date,
            end=end_date,
        )
    )

    typer.echo(f"Damodaran monthly backfill: {start_date}..{end_date}")
    typer.echo(f"  persisted:           {result.persisted}")
    typer.echo(f"  skipped_existing:    {result.skipped_existing}")
    typer.echo(f"  skipped_unavailable: {result.skipped_unavailable}")
    typer.echo(f"  skipped_insufficient:{result.skipped_insufficient}")
    typer.echo(f"  errors:              {result.errors}")
```

Mirror imports + helpers from existing `nss-curves` and `expinf-us-bei` subcommands.

### Step 6 — Tests (45min)

Create `tests/unit/test_overlays/test_erp_external_damodaran.py`:

```python
"""Tests for Damodaran external reference writer + backfill."""

import pytest
from datetime import date

from sonar.connectors.damodaran import DamodaranMonthlyERPRow
from sonar.db.models import ERPExternalReferenceRow
from sonar.overlays.erp_external.damodaran import build_damodaran_external_row
from sonar.overlays.exceptions import InsufficientDataError


class TestDamodaranExternalWriter:
    """Spec §3 fixture-based tests."""

    def test_build_row_2024_01_canonical(self):
        """Damodaran Jan 2024 monthly snapshot.

        Damodaran ERPJan24.xlsx published implied ERP ~5.50% per public NYU file.
        Use representative value; exact match not required (data fixture).
        """
        damodaran_row = DamodaranMonthlyERPRow(
            year=2024,
            month=1,
            implied_erp_decimal=0.0550,
            source_file="ERPJan24.xlsx",
        )

        row = build_damodaran_external_row(
            year=2024, month=1, damodaran_row=damodaran_row,
        )

        assert row.market_index == "SPX"
        assert row.country_code == "US"
        assert row.date == date(2024, 1, 1)
        assert row.source == "damodaran_monthly"
        assert row.erp_bps == 550  # 0.0550 * 10_000
        assert row.source_file == "ERPJan24.xlsx"
        assert row.methodology_version == "DAMODARAN_MONTHLY_v0.1"
        assert row.confidence == 0.95
        assert row.flags is None

    def test_build_row_none_implied_erp_raises(self):
        """Spec §6: missing implied_erp_decimal raises InsufficientDataError."""
        damodaran_row = DamodaranMonthlyERPRow(
            year=2024, month=2,
            implied_erp_decimal=None,
            source_file="ERPFeb24.xlsx",
        )
        with pytest.raises(InsufficientDataError, match="implied_erp_decimal is None"):
            build_damodaran_external_row(
                year=2024, month=2, damodaran_row=damodaran_row,
            )

    def test_build_row_2025_12_recent_freshness(self):
        """Recent monthly snapshot (Dec 2025; ~2-month publication lag)."""
        damodaran_row = DamodaranMonthlyERPRow(
            year=2025,
            month=12,
            implied_erp_decimal=0.0480,
            source_file="ERPDec25.xlsx",
        )

        row = build_damodaran_external_row(
            year=2025, month=12, damodaran_row=damodaran_row,
        )

        assert row.erp_bps == 480
        assert row.date == date(2025, 12, 1)
        assert row.source_file == "ERPDec25.xlsx"
```

Add backfill orchestrator tests as time permits (CAL-Sprint-3.1-A: defer if scope crunch).

### Step 7 — Execute backfill against engine DB (10min)

After Sprint 3.1 commit + sprint_merge.sh + back on engine main:

```bash
cd /home/macro/projects/sonar-engine
source .venv/bin/activate

# Damodaran monthly: Sep 2008 to Feb 2026 (~2-month publication lag)
sonar backfill erp-external \
    --source damodaran \
    --start 2008-09-01 \
    --end 2026-02-28
```

Expected runtime: ~5-10 min (210 monthly fetches; cache hits after first iteration). Most monthly Damodaran files are cached on his website permanently — fast-fetch.

### Step 8 — Tier B verification (5min)

```bash
sqlite3 /home/macro/projects/sonar-engine/data/sonar-dev.db <<'EOF'
.mode column
.headers on

-- Coverage check
SELECT
  source,
  COUNT(*) AS n_rows,
  MIN(date) AS earliest,
  MAX(date) AS latest,
  ROUND(AVG(erp_bps)) AS avg_erp_bps,
  MIN(erp_bps) AS min_erp_bps,
  MAX(erp_bps) AS max_erp_bps
FROM erp_external_reference
GROUP BY source;

-- Recent samples
SELECT date, source, erp_bps, methodology_version, confidence, source_file, flags
FROM erp_external_reference
WHERE source='damodaran_monthly'
ORDER BY date DESC
LIMIT 12;

-- Gaps detection (months with 0 rows in expected window)
SELECT 'monthly_count' AS check, COUNT(*) AS expected
FROM (SELECT date FROM erp_external_reference WHERE source='damodaran_monthly');
-- Expected: ~210 rows for 2008-09 to 2026-02 inclusive (17.5 years × 12 months)
EOF
```

Expected:
- ~210 rows (some months may be unavailable; 0-5 missing acceptable)
- Date range 2008-09-01 to 2026-02-01
- ERP range 300-700 bps historical (US Implied ERP varies 3-7% range)
- All confidence = 0.95
- methodology_version = 'DAMODARAN_MONTHLY_v0.1'

---

## 5. Acceptance criteria

### Must pass
1. ✅ `erp_external_reference` table populated with `damodaran_monthly` source ≥190 rows
2. ✅ Date range 2008-09 to 2026-02 (or latest Damodaran-published month)
3. ✅ All rows: `market_index='SPX'`, `country_code='US'`, `confidence=0.95`
4. ✅ `methodology_version='DAMODARAN_MONTHLY_v0.1'` consistent
5. ✅ 3 fixture tests pass
6. ✅ Pre-commit + pytest green
7. ✅ Merged via sprint_merge.sh
8. ✅ Recent month sample shows current Damodaran ERP (sanity: should be in 400-600 bps range for 2025-2026)

### Out of scope (defer)
- Bloomberg / GS / Reuters source extension
- EA/UK/JP markets (Damodaran covers US only)
- Backfill orchestrator unit tests (CAL-Sprint-3.1-A; only fixture tests Sprint 3.1)
- Cross-source consistency check (CAL-Sprint-3.1-B; future when 2+ sources exist)

---

## 6. Risks + mitigations

| Risk | Mitigation |
|---|---|
| Damodaran URL pattern changed since last connector verification | Smoke test: fetch one recent month before backfill (e.g. 2025-12) — if 404, halt + investigate |
| Older Damodaran files (2008-2010) may have different schema | Connector parser already handles multi-format per existing implementation; defer if specific failure |
| Network timeouts during 210-month backfill | Connector has retry logic + cache; skipped_unavailable counted, log warning |
| Damodaran row missing implied_erp_decimal field | Skip with InsufficientDataError + skipped_insufficient counter; non-blocker |
| URL clamp earlier than 2008-09 | Backfill orchestrator clamps automatically with WARNING log |
| Migration conflicts with Sprint 3 head revision | Run `alembic upgrade head` first; if conflict, alembic merge; report before proceeding |

---

## 7. Dependencies

- **Connector**: `connectors/damodaran.py` existing (Week 10 Sprint B Commit 2 shipped)
- **URL pattern**: `https://pages.stern.nyu.edu/~adamodar/pc/implprem/ERP{mon}{yy}.xlsx` (verified 2026-04-25)
- **Sprint 3 merge**: must complete before Sprint 3.1 (Sprint 3.1 modifies models.py post-Sprint 3 changes)
- **Engine DB state**: erp_canonical 65 rows (Sprint 3 backfill) — Sprint 3.1 doesn't touch this table

---

## 8. CC prompt template

```
Sprint 3.1 — L2 ERP External Reference (Damodaran)

Read brief: docs/planning/week11-sprint-3-1-erp-external-reference-brief.md

Execute 8 steps per brief §4:

Step 0 — Worktree seed (3 symlinks + venv activate; verify Sprint 3 merged via sqlite3 check on erp_canonical US 65 rows)

Step 1 — Audit (5 commands; report findings before Step 2)

Step 2 — ORM class ERPExternalReferenceRow + Alembic migration:
  - Add to src/sonar/db/models.py per brief schema
  - alembic revision --autogenerate -m "Sprint 3.1: erp_external_reference table"
  - Inspect generated migration; trim to only erp_external_reference creation if other models touched
  - alembic upgrade head
  - Verify schema via sqlite3 .schema

Step 3 — Damodaran writer (src/sonar/overlays/erp_external/damodaran.py + __init__.py):
  - build_damodaran_external_row(year, month, damodaran_row) per brief pseudocode
  - methodology_version='DAMODARAN_MONTHLY_v0.1'
  - confidence=0.95 base
  - market_index='SPX', country_code='US'

Step 4 — Backfill orchestrator (src/sonar/overlays/erp_external/backfill.py):
  - backfill_damodaran_monthly() per brief
  - Idempotent via session.query existing check
  - DAMODARAN_MONTHLY_START = date(2008, 9, 1) clamp
  - DamodaranBackfillResult dataclass

Step 5 — CLI extension (src/sonar/cli/backfill.py):
  - sonar backfill erp-external --source --start --end
  - Mirror existing nss-curves + expinf-us-bei pattern

Step 6 — Tests (tests/unit/test_overlays/test_erp_external_damodaran.py):
  - 3 fixture tests per brief Step 6 pseudocode
  - Synthetic DamodaranMonthlyERPRow inputs (no live FRED/Damodaran fetch in tests; hermetic)

Step 7 — Execute backfill (post-merge, on engine main):
  sonar backfill erp-external --source damodaran --start 2008-09-01 --end 2026-02-28

Step 8 — Tier B verification against ENGINE DB (queries from brief §4 step 8)

Critical rules:
- DO NOT modify erp_canonical table (Sprint 3 unchanged; spec §11 "compute don't consume" preserved)
- erp_external_reference is ADJACENT to computed canonical, not replacement
- Source column extensible (Sprint 3.1 only 'damodaran_monthly'; future Bloomberg/GS/Reuters)
- Idempotent backfill via UNIQUE (market_index, date, source)
- Confidence=0.95 base (Damodaran gold-standard)
- methodology_version='DAMODARAN_MONTHLY_v0.1'
- HALT before commit per CLAUDE.md §5/§7. Report deliverables + tests + Tier B + spec deviations. Await authorization.

Run pytest + pre-commit + sprint_merge.sh.

Tier B: Damodaran monthly ≥190 rows from 2008-09 to 2026-02.

START Step 0 worktree seed. Report Step 1 audit findings before Step 2.
```

---

## 9. Sprint 3.1 → Sprint 3.2 (next)

After Sprint 3.1 merge + Tier B green:

**Sprint 3.2** — Fix data feeds for computed canonical (4-5h):
- Wire `factset_insight.fetch_latest_snapshot()` into `erp_daily/backfill.py`
- Wire `yardeni.fetch_latest_snapshot()` for cross-val
- Decide Shiller fallback (use FactSet trailing OR explicit `STALE` escalation)
- Re-run computed canonical backfill 60 bd
- Validate: ERP_METHOD_DIVERGENCE incidence drops <20%, EY positive, computed ≈ Damodaran ±50 bps

**Both layers operational post-3.2**:
- `erp_canonical` (computed 4 methods + median + range)
- `erp_external_reference` (Damodaran benchmark)
- Comparative analysis: `computed vs damodaran` permanent benchmarking infrastructure

**L2 ERP US fully editorial-grade.** Ready for Sprint 4 (L2 rating-spread).

---

**END BRIEF**
