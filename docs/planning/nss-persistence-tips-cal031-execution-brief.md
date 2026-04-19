# NSS Persistence + FRED TIPS + CAL-031 — Execution Brief

**Target session**: Phase 1 Week 2, Day 3 AM
**Priority**: HIGH (Week 2 critical path — M1 L1 persistence + L2 real curve closure)
**Time budget**: 90–120 min
**Authority**: Full autonomy per decision authority rule; HALT triggers §9 atomic — "user authorized in principle" does NOT count as pre-authorization for specific trigger (CAL-032 calibration from Day 2 AM)
**Commit count**: 3 (TIPS connector + persistence + real curve integration)
**Base commit**: `3b59612` (main HEAD Day 2 AM close)
**Predecessor**: NSS math core (`e0b71d4`, `065f811`); spec nss-curves.md @ NSS_v0.1

---

## 1. Scope

**In-scope**:
- Commit 1: FRED connector refactor — extract generic `fetch_series(series_id)` + add TIPS wrappers (DFII5, DFII10, DFII20, DFII30)
- Commit 2: Alembic migration 002 + SQLAlchemy models for `yield_curves_{spot,zero,forwards,real}` + `persist_nss_fit_result()` with atomic transaction semantics + `DuplicatePersistError`
- Commit 3: Real curve direct-linker live integration (connector → fit → derive_real_curve) + CAL-031 fixture live fetch resolution

**Out-of-scope** (Day 3 PM / Day 4+):
- Fed GSW cross-validation hook
- Pipeline `daily-curves` (L8) — persistence functions built here; pipeline orchestration separate
- `treasury_gov` connector (P2-026 LOW)
- Upsert/overwrite mode for persistence (Phase 2+ — caller decides via explicit flag, not implicit)
- Multi-country (DE, JP) — Week 3+

---

## 2. Canonical invariants

**Hard-locked** (do not modify):
- `docs/specs/overlays/nss-curves.md` @ NSS_v0.1
- Week 1 stack: `src/sonar/db/models.py::Observation`, Alembic migration 001, FRED connector public surface (`FREDConnector` instantiation pattern — refactor internal, not external)
- Confidence algorithm (`_compute_confidence`) — flags.md-compliant per Day 2 AM

**Newly hard-locked by this brief** (CAL-032 transition — first external consumer lands this session):
- `NSSFitResult` / `SpotCurve` / `ZeroCurve` / `ForwardCurve` / `RealCurve` / `NSSParams` dataclass shapes — from this commit forward, field additions require migration + consumer updates; renames require formal contract review

**Still soft** (pre-consumer):
- Persistence function signatures (`persist_nss_fit_result` etc.) — can evolve until pipeline L8 lands

---

## 3. Commit 1 — FRED TIPS connector (extract + extend)

### 3.1 Refactor goal

Current `src/sonar/connectors/fred.py` (from `cbdd516`) fetches FRED series. Pattern likely fused "fetch + domain semantics". Refactor to:

- **Generic layer**: `fetch_series(series_id: str, observation_date: date | None = None) -> list[Observation]` — low-level; returns raw observations for any FRED series
- **Domain wrappers**: `fetch_yield_curve_nominal(country: str, observation_date: date) -> dict[str, Observation]` — returns `{"1M": obs, "3M": obs, ...}` keyed by standard tenor labels
- **New**: `fetch_yield_curve_linker(country: str, observation_date: date) -> dict[str, Observation]` — TIPS counterpart

### 3.2 TIPS series mapping

```python
# src/sonar/connectors/fred_series.py (new file OR extend fred.py)

US_NOMINAL_SERIES: dict[str, str] = {
    "1M": "DGS1MO", "3M": "DGS3MO", "6M": "DGS6MO",
    "1Y": "DGS1", "2Y": "DGS2", "3Y": "DGS3",
    "5Y": "DGS5", "7Y": "DGS7", "10Y": "DGS10",
    "20Y": "DGS20", "30Y": "DGS30",
}

US_LINKER_SERIES: dict[str, str] = {
    "5Y": "DFII5",
    "7Y": "DFII7",
    "10Y": "DFII10",
    "20Y": "DFII20",
    "30Y": "DFII30",
}
```

Note: TIPS has fewer tenors than nominal (5 vs 11). Short-end TIPS liquidity is thin; Fed publishes 5Y+. This limits real curve to 5 obs — at the edge of `MIN_OBSERVATIONS = 6`. **Real curve direct-linker for US will need 4-param NS reduced fit when TIPS data limited to 5 tenors, OR InsufficientDataError raised.**

### 3.3 Scope of fit on linker data

Spec §6 row 1: `n_obs < 6 → InsufficientDataError`. With 5 TIPS tenors, US real curve fit raises.

**Decision** (I take it; flag if disagree before Claude Code runs):
- Check if DFII7 exists in FRED (I'm uncertain — verify via live fetch; if absent, 4 tenors = hard fail)
- If DFII7 exists → 5 tenors still < 6 → InsufficientDataError per spec
- Real curve for US Week 2 remains **stubbed (None)** in this brief even with TIPS connector; the connector is built and tested, but integration into `derive_real_curve` returns None due to MIN_OBSERVATIONS
- **Raise CAL-033** (new): "US real curve direct-linker path blocked by TIPS 5-tenor coverage < MIN_OBSERVATIONS=6. Options: (a) relax MIN_OBSERVATIONS to 5 for linker curves only; (b) add synthetic short-end TIPS proxy via nominal − breakeven; (c) derived path via expected-inflation overlay." Defer resolution to Day 3 PM or Week 3.

This is an empirical finding that invalidates part of brief §1 Commit 3 scope. Adjust Commit 3 accordingly (§5.4 below).

### 3.4 Commit 1 body

```
feat(connectors): FRED TIPS linker series + generic fetch_series refactor

Extract low-level fetch_series(series_id) from FREDConnector; add thin
domain wrappers:
- fetch_yield_curve_nominal(country, date): DGS* → {tenor: Observation}
- fetch_yield_curve_linker(country, date): DFII* → {tenor: Observation}

TIPS series dict (US_LINKER_SERIES) covers DFII5/7/10/20/30 (5 tenors).
Short-end TIPS (<5Y) not published by Fed; real curve direct-linker path
consequently below MIN_OBSERVATIONS=6 threshold — raises CAL-033 for
resolution strategy (relax threshold for linkers, synthetic short-end,
or derived path).

Test: pytest-httpx cassette replay for all series (no live network in CI).
One live canary test marked @pytest.mark.live — manual run.

Ref: spec §2 T1 US connector hierarchy.
```

### 3.5 Commit 1 tests

Cassette replay pattern established Week 1:

- `tests/unit/test_connectors/test_fred_nominal.py` — existing tests migrate to new `fetch_yield_curve_nominal` wrapper without behavior change
- `tests/unit/test_connectors/test_fred_linker.py` — new; 5 DFII series covered
- `tests/integration/test_fred_linker_live.py` — `@pytest.mark.live`; hit FRED once, validate Observation schema + non-empty

Coverage target: `src/sonar/connectors/` stays ≥ 95% hard gate per `phase1-coverage-policy.md`.

---

## 4. Commit 2 — Persistence layer

### 4.1 Alembic migration 002

`alembic/versions/002_yield_curves.py` — create 4 tables per spec §8 verbatim (+ 3 FK indexes from `957e765` sweep).

```python
"""yield_curves_{spot,zero,forwards,real} schemas

Revision ID: 002_yield_curves
Revises: 001_initial_yield_curves
Create Date: 2026-04-20 ...
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "002_yield_curves"
down_revision: str = "001_initial_yield_curves"


def upgrade() -> None:
    op.create_table(
        "yield_curves_spot",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), nullable=False),  # alpha-2 post P2-023
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("fit_id", sa.String(36), nullable=False),  # UUID4 str
        sa.Column("beta_0", sa.Float, nullable=False),
        sa.Column("beta_1", sa.Float, nullable=False),
        sa.Column("beta_2", sa.Float, nullable=False),
        sa.Column("beta_3", sa.Float, nullable=True),
        sa.Column("lambda_1", sa.Float, nullable=False),
        sa.Column("lambda_2", sa.Float, nullable=True),
        sa.Column("fitted_yields_json", sa.Text, nullable=False),
        sa.Column("observations_used", sa.Integer, nullable=False),
        sa.Column("rmse_bps", sa.Float, nullable=False),
        sa.Column("xval_deviation_bps", sa.Float, nullable=True),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),  # CSV of flag codes
        sa.Column("source_connector", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.current_timestamp()),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_ycs_confidence"),
        sa.UniqueConstraint("country_code", "date", "methodology_version",
                            name="uq_ycs_country_date_method"),
    )
    op.create_index("idx_ycs_cd", "yield_curves_spot", ["country_code", "date"])

    # yield_curves_zero
    op.create_table(
        "yield_curves_zero",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("fit_id", sa.String(36), nullable=False),
        sa.Column("zero_rates_json", sa.Text, nullable=False),
        sa.Column("derivation", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("flags", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.current_timestamp()),
        sa.CheckConstraint("derivation IN ('nss_derived', 'bootstrap')",
                           name="ck_ycz_derivation"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_ycz_confidence"),
        sa.UniqueConstraint("country_code", "date", "methodology_version",
                            name="uq_ycz_country_date_method"),
    )
    op.create_index("idx_ycz_cd", "yield_curves_zero", ["country_code", "date"])
    op.create_index("idx_ycz_fitid", "yield_curves_zero", ["fit_id"])

    # yield_curves_forwards — same pattern
    # yield_curves_real — same pattern with method + linker_connector cols

    # ... (full definitions mirror spec §8)


def downgrade() -> None:
    op.drop_table("yield_curves_real")
    op.drop_table("yield_curves_forwards")
    op.drop_table("yield_curves_zero")
    op.drop_table("yield_curves_spot")
```

Full migration: expand forwards + real tables per spec §8. Note FKs to `yield_curves_spot.fit_id` via spec §8 schema — **but** SQLite FK constraints require explicit `PRAGMA foreign_keys=ON`. Claude Code verifies this is set in session setup; if not, add to `alembic/env.py`.

**Caveat**: spec §8 shows FKs pointing to `yield_curves_spot(fit_id)` but `fit_id` in spot table is not itself UNIQUE (only composite `country_code, date, methodology_version` is). Cannot FK to non-unique column. Two options:
- (a) Add `UNIQUE (fit_id)` to `yield_curves_spot` — enables FK
- (b) Drop FK constraints in migration 002; enforce referential integrity at application layer via `persist_nss_fit_result` atomic transaction

**Decision**: (a). FK at DB level is safer; cost is trivial UNIQUE index on UUID column. Add `sa.UniqueConstraint("fit_id", name="uq_ycs_fit_id")` to spot table. This is a legitimate spec tightening — flag for chat triage as spec §8 minor amendment (doc-only, no version bump, fit_id was always implicitly unique).

### 4.2 SQLAlchemy models

Append to `src/sonar/db/models.py`:

```python
class NSSYieldCurveSpot(Base):
    __tablename__ = "yield_curves_spot"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    fit_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    beta_0: Mapped[float] = mapped_column(Float, nullable=False)
    # ... (all cols from migration)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    __table_args__ = (
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_ycs_confidence"),
        UniqueConstraint("country_code", "date", "methodology_version",
                         name="uq_ycs_country_date_method"),
        UniqueConstraint("fit_id", name="uq_ycs_fit_id"),
        Index("idx_ycs_cd", "country_code", "date"),
    )


# NSSYieldCurveZero, NSSYieldCurveForwards, NSSYieldCurveReal — analogous
```

### 4.3 Persistence function

`src/sonar/db/persistence.py` (new):

```python
"""Persistence functions for L2 overlay outputs."""
from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from sonar.db.models import (
    NSSYieldCurveForwards, NSSYieldCurveReal,
    NSSYieldCurveSpot, NSSYieldCurveZero,
)
from sonar.overlays.nss import NSSFitResult


class DuplicatePersistError(Exception):
    """Raised when persisting a fit result whose (country, date, methodology)
    tuple already exists. Caller decides overwrite policy; no silent upsert."""


def persist_nss_fit_result(session: Session, result: NSSFitResult) -> None:
    """Persist all 4 sibling rows atomically.

    On ANY failure (UNIQUE violation, constraint check, IO), transaction
    rolls back fully. No partial persist.

    Raises:
        DuplicatePersistError: when the triplet already exists.
        SQLAlchemyError: on other DB errors (caller handles).
    """
    spot_row = _to_spot_row(result)
    zero_row = _to_zero_row(result)
    forwards_row = _to_forwards_row(result)
    real_row = _to_real_row(result) if result.real is not None else None

    try:
        with session.begin():
            session.add(spot_row)
            session.add(zero_row)
            session.add(forwards_row)
            if real_row is not None:
                session.add(real_row)
            session.flush()
    except IntegrityError as e:
        # SQLite raises "UNIQUE constraint failed" on conflict.
        if "UNIQUE constraint" in str(e.orig) or "unique constraint" in str(e.orig).lower():
            raise DuplicatePersistError(
                f"Fit already persisted: country={result.country_code}, "
                f"date={result.observation_date}, version={result.methodology_version}"
            ) from e
        raise


def _to_spot_row(r: NSSFitResult) -> NSSYieldCurveSpot:
    return NSSYieldCurveSpot(
        country_code=r.country_code,
        date=r.observation_date,
        methodology_version=r.methodology_version,
        fit_id=str(r.fit_id),
        beta_0=r.spot.params.beta_0,
        beta_1=r.spot.params.beta_1,
        beta_2=r.spot.params.beta_2,
        beta_3=r.spot.params.beta_3,
        lambda_1=r.spot.params.lambda_1,
        lambda_2=r.spot.params.lambda_2,
        fitted_yields_json=json.dumps(r.spot.fitted_yields),  # units.md: decimal
        observations_used=r.spot.observations_used,
        rmse_bps=r.spot.rmse_bps,
        xval_deviation_bps=None,  # Day 3 PM xval adds
        confidence=r.spot.confidence,
        flags=",".join(r.spot.flags) if r.spot.flags else None,
        source_connector="fred",  # hardcoded Week 2; refactor Week 3
    )


# _to_zero_row, _to_forwards_row, _to_real_row — analogous JSON-encoding pattern
```

### 4.4 Fit ID generation

`NSSFitResult` assembly (assuming already in nss.py or add utility):

```python
from uuid import uuid4

def assemble_nss_fit_result(
    country_code: str,
    observation_date: date_type,
    spot: SpotCurve,
    zero: ZeroCurve,
    forward: ForwardCurve,
    real: RealCurve | None,
) -> NSSFitResult:
    return NSSFitResult(
        fit_id=uuid4(),
        country_code=country_code,
        observation_date=observation_date,
        methodology_version=METHODOLOGY_VERSION,
        spot=spot, zero=zero, forward=forward, real=real,
    )
```

### 4.5 Commit 2 tests

`tests/unit/test_db/test_persistence.py`:

- `test_persist_nss_fit_result_all_four_tables`: assemble mock NSSFitResult (real=None), persist, query all 4 tables, verify rows via `fit_id` join
- `test_persist_nss_fit_result_without_real`: real=None → real table has no row, other 3 persisted
- `test_duplicate_raises_specific_exception`: persist same triplet twice → `DuplicatePersistError`
- `test_partial_failure_rollback`: inject failure mid-transaction (mock), verify no rows persisted in any table
- `test_fit_id_unique_constraint`: two different country-date pairs with same (artificially duped) fit_id → IntegrityError on second

Use in-memory SQLite (`:memory:`) via pytest fixture; Alembic upgrades migrations 001+002 at session setup.

### 4.6 Commit 2 body

```
feat(db): yield_curves_* schemas + persistence layer (migration 002)

Alembic migration 002 creates yield_curves_{spot,zero,forwards,real}
per spec §8. FK references yield_curves_spot.fit_id (UNIQUE constraint
added — spec §8 implicit; doc-only clarification, no NSS_v0.1 bump).

SQLAlchemy ORM models in src/sonar/db/models.py.

src/sonar/db/persistence.py:
- persist_nss_fit_result(session, NSSFitResult): atomic 4-row transaction
  via session.begin(); partial failure rolls back all.
- DuplicatePersistError: raised on UNIQUE violation of
  (country, date, methodology_version) triplet. Caller decides overwrite
  policy (no implicit upsert, per ship-first philosophy).

Tests cover happy path, real=None branch, duplicate detection,
partial-failure rollback, fit_id uniqueness.

Ref: spec §8; brief §4.

Hard-locks NSSFitResult dataclass shape from this commit forward
(first external consumer — persistence layer depends on field names
and types).
```

---

## 5. Commit 3 — Real curve integration + CAL-031 resolution

### 5.1 CAL-031 resolution procedure

Goal: replace indicative `us_2024_01_02.json` yields with live FRED H.15.

```python
# One-off script OR manual steps in Claude Code session
from datetime import date
from sonar.connectors.fred import FREDConnector

conn = FREDConnector(api_key=settings.fred_api_key)
nominals = conn.fetch_yield_curve_nominal(country="US", observation_date=date(2024, 1, 2))
# nominals: {"1M": Observation(value=0.0552, ...), "3M": ..., ...}

# Build fixture payload
tenors = [0.08333, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 20.0, 30.0]
yields = [nominals[label].value for label in ["1M","3M","6M","1Y","2Y","3Y","5Y","7Y","10Y","20Y","30Y"]]
# Note: yields already in decimal per units.md; fixture stored as decimal
```

### 5.2 Fixture update + test re-run

1. Capture live FRED values for 2024-01-02
2. Update `tests/fixtures/nss-curves/us_2024_01_02.json` — fields `input.yields` (decimal) and meta.source = "FRED H.15 DGS* 2024-01-02 live fetch"
3. Save pytest-httpx cassette: `tests/fixtures/cassettes/fred_us_2024_01_02.yaml`
4. Re-run `pytest tests/unit/test_overlays/test_nss_behavior.py::TestFitUSCanonical -v`
5. Branch:
   - **5a**: if RMSE ≤ 5 bps → update fixture `rmse_bps_max` = 5, close CAL-031
   - **5b**: if RMSE > 5 bps → update fixture `rmse_bps_max` = ceil(actual_rmse_bps + 2), close CAL-031, raise CAL-034 "Spec §7 tolerance revision" (separate task — evaluate Fed GSW benchmark and propose realistic threshold)

### 5.3 Real curve integration — US Week 2 final position

Per §3.3 finding, US TIPS provides 5 tenors — below `MIN_OBSERVATIONS=6`. Real curve direct-linker fit for US raises `InsufficientDataError`. Therefore:

- `derive_real_curve` implementation unchanged from Day 2 AM (already handles `linker_yields=None → None`)
- Add test: when `linker_yields` has 5 or fewer obs, `derive_real_curve` internally raises `InsufficientDataError` → caller catches + returns `RealCurve` with method="derived", but derived path needs E[π] which is unavailable this week → returns `None`
- **Net**: US real curve = None for Week 2 regardless of TIPS connector availability
- CAL-033 raised for strategy resolution

**Practical**: Commit 3 deliverables shrink vs initial plan:
- TIPS connector fully functional (Commit 1 delivers)
- `derive_real_curve` receives linker_yields param wired through but observes InsufficientDataError path
- One integration test added: fetch TIPS → attempt fit → expect InsufficientDataError → overall result real=None

### 5.4 Integration test — M1 vertical slice

`tests/integration/test_nss_vertical_slice.py`:

```python
@pytest.mark.integration
def test_us_2024_01_02_end_to_end_persist(in_memory_db, fred_cassette):
    """L0 → L2 → L1 vertical slice for US on canonical date.

    Fetches live (cassette-replayed) FRED nominal + linker; fits NSS;
    derives zero + forward; attempts real (expected None due to
    MIN_OBSERVATIONS); persists to DB; queries back.
    """
    obs_date = date(2024, 1, 2)
    conn = FREDConnector(api_key="test")

    nominals = conn.fetch_yield_curve_nominal(country="US", observation_date=obs_date)
    linkers = conn.fetch_yield_curve_linker(country="US", observation_date=obs_date)

    # Build NSSInput from nominals
    tenor_labels = sorted(nominals.keys(), key=_label_to_years)
    nss_input = NSSInput(
        tenors_years=np.array([_label_to_years(t) for t in tenor_labels]),
        yields=np.array([nominals[t].value for t in tenor_labels]),
        country_code="US",
        observation_date=obs_date,
        curve_input_type="par",
    )

    spot = fit_nss(nss_input)
    zero = derive_zero_curve(spot)
    forward = derive_forward_curve(zero)
    linker_yields_dict = {t: linkers[t].value for t in linkers}
    real = derive_real_curve(spot, linker_yields=linker_yields_dict)  # expect None

    assert real is None  # CAL-033 limitation

    result = assemble_nss_fit_result(
        country_code="US", observation_date=obs_date,
        spot=spot, zero=zero, forward=forward, real=real,
    )
    persist_nss_fit_result(in_memory_db, result)

    # Query back
    persisted = in_memory_db.query(NSSYieldCurveSpot).filter_by(
        country_code="US", date=obs_date
    ).one()
    assert persisted.fit_id == str(result.fit_id)
    assert persisted.rmse_bps == spot.rmse_bps
```

### 5.5 Commit 3 body

```
feat(overlays): real curve direct-linker integration + CAL-031 fixture fetch

CAL-031 resolution: us_2024_01_02.json fixture updated with live FRED
H.15 DGS* values @ 2024-01-02 close. Cassette saved for CI replay.
Actual RMSE: [X.XX] bps [vs nominal 5 bps tolerance → branch A close |
branch B raise CAL-034 for spec §7 tolerance revision].

Real curve direct-linker integration: derive_real_curve wired through
with TIPS yields from fetch_yield_curve_linker. US TIPS publishes 5
tenors (DFII5/7/10/20/30) — below MIN_OBSERVATIONS=6 per spec §6 row 1.
Real curve for US returns None. CAL-033 raised for resolution
(relax threshold for linkers / synthetic short-end / derived path).

Integration test: tests/integration/test_nss_vertical_slice.py — L0
connectors → L2 overlays fit+derive → L1 persistence → query back.
Cassette-replayed; @pytest.mark.integration scope.

Closes CAL-031. Opens CAL-033, maybe CAL-034.
```

---

## 6. New backlog items to create (same commit 3 or separate)

Consolidate into commit 3 body — track list for end-of-day backlog sweep (Day 3 PM or chat closes):

- **CAL-033 (MEDIUM)**: "US real curve direct-linker blocked by TIPS 5-tenor coverage < MIN_OBSERVATIONS=6. Resolution options A/B/C."
- **CAL-034 (MEDIUM, conditional)**: only if §5.2 branch B fires — "Spec §7 us_2024_01_02 RMSE tolerance revision vs Fed GSW benchmark"

Do not create entries inline in Commit 3. Dedicated `docs(backlog)` commit at end of Day 3 AM consolidates both.

---

## 7. Execution sequence

1. **Commit 1 (TIPS)**:
   - Refactor `src/sonar/connectors/fred.py` — extract `fetch_series`, add domain wrappers
   - Add `US_NOMINAL_SERIES`, `US_LINKER_SERIES` dicts
   - Write `fetch_yield_curve_linker` + tests (cassette)
   - Migrate existing nominal tests to new wrapper (compatibility)
   - `pre-commit`, `pytest`, push
2. **Commit 2 (persistence)**:
   - Write Alembic migration 002 (4 tables, FK constraints, `fit_id` UNIQUE)
   - Run `uv run alembic upgrade head` in dev DB — verify
   - Write SQLAlchemy models (append to `models.py`)
   - Write `persistence.py` with `persist_nss_fit_result` + `DuplicatePersistError`
   - Write `assemble_nss_fit_result` helper (in `nss.py` or `persistence.py` — Claude Code chooses)
   - Write 5 persistence tests
   - `pre-commit`, `pytest`, push
3. **Commit 3 (real curve + CAL-031)**:
   - Live fetch FRED DGS* for 2024-01-02; update fixture yields + save cassette
   - Live fetch FRED DFII* for 2024-01-02; save cassette
   - Re-run TestFitUSCanonical — branch A or B per §5.2
   - Wire `derive_real_curve` call into integration test
   - Write `test_nss_vertical_slice.py`
   - `pre-commit`, `pytest`, push

After 3 commits: manual backlog sweep creates CAL-033 (+ CAL-034 conditional) — separate `docs(backlog)` commit, or defer to end-of-day chat.

---

## 8. Acceptance checklist

### Commit 1
- [ ] `fetch_series(series_id)` generic function extracted
- [ ] `fetch_yield_curve_nominal`, `fetch_yield_curve_linker` wrappers
- [ ] Cassette tests green for both nominal and linker
- [ ] `src/sonar/connectors/` coverage ≥ 95% (hard gate)
- [ ] Existing nominal tests still pass

### Commit 2
- [ ] Alembic migration 002 upgrades cleanly on fresh dev DB
- [ ] `alembic downgrade base && alembic upgrade head` round-trip clean
- [ ] 4 SQLAlchemy models registered
- [ ] `persist_nss_fit_result` atomic transaction semantics verified
- [ ] `DuplicatePersistError` raised on UNIQUE violation
- [ ] 5 persistence tests green
- [ ] `src/sonar/db/` coverage ≥ 90% per-module

### Commit 3
- [ ] `us_2024_01_02.json` updated with live FRED values (decimal, units.md-compliant)
- [ ] Cassettes saved for nominal + linker fetches
- [ ] `TestFitUSCanonical` suite green with new fixture (branch A or B)
- [ ] `test_nss_vertical_slice.py` integration test green
- [ ] Real curve explicitly None for US (CAL-033 limitation)

### Global
- [ ] All hooks pass no `--no-verify`
- [ ] 3 commits pushed; local HEAD matches remote
- [ ] Global `src/sonar` coverage ≥ 75% soft gate

---

## 9. HALT triggers (atomic — no "authorized in principle")

Pause + report without pushing if any fires:

1. FRED live fetch for 2024-01-02 returns 4xx/5xx or unexpected schema (connector layer issue — Day 3 unblocker, real decision)
2. DFII7 series does not exist in FRED (assumed above; validate live) — if absent, `US_LINKER_SERIES` drops to 4 tenors, CAL-033 urgency raises but brief can still ship Commit 1 with 4 tenors
3. Alembic migration 002 upgrade fails on clean dev DB (SQLite FK constraints, CheckConstraint syntax, or reference to non-existent table)
4. spec §8 FK constraint to non-unique `fit_id` surfaces a contradiction with existing `Observation` or other Week 1 schema → scope call to chat
5. Persistence atomic transaction fails to roll back partially — data integrity issue, HIGH severity
6. Live FRED fetch returns RMSE > 20 bps (implausible — data corruption or fit bug)
7. Coverage regression > 3pp on any per-module scope
8. **Any decision Claude Code feels tempted to take citing "user pre-authorization"** — that phrase only covers D-Day3-3 and scope option B. Anything else requires explicit HALT. (CAL-032 calibration from Day 2 AM.)

---

## 10. Report-back (paste to chat)

1. 3 commit SHAs + `git log --oneline -3`
2. Coverage deltas per scope (connectors, db, overlays, global)
3. Test count: `pytest tests/ --collect-only -q | tail -5`
4. CAL-031 branch taken (A or B) + actual RMSE for us_2024_01_02 live fit
5. Did DFII7 exist? Linker tenor count
6. Real curve status for US vertical slice test (expected None — confirm)
7. Timer actual vs 90–120 min budget
8. HALT triggers resolved mid-flight
9. Backlog items to create: CAL-033 (always), CAL-034 (conditional)
10. Any spec §8 FK `fit_id` UNIQUE addition flagged (doc-only amendment or spec revision?)

---

*End of brief. Proceed.*
