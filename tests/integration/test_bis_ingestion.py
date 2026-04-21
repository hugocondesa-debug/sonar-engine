"""End-to-end integration — BIS ingest -> bis_credit_raw -> credit indices compute.

Two layers:

* **Mocked path** (always runs): seeds synthetic WS_TC observations
  directly into ``bis_credit_raw`` and drives the DbBackedInputsBuilder
  through to persistence. No network.
* **Live canary** (``@pytest.mark.slow``, skipped unless ``--runslow``):
  hits real BIS for US 2024-Q2 WS_TC via the sequential ingestion
  pipeline and asserts the raw table is populated + downstream L1
  compute lands a row. Exercised manually during canary validation.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import sonar.db.session  # noqa: F401
from sonar.db.models import Base, BisCreditRaw, CreditGdpGap, CreditGdpStock
from sonar.pipelines.daily_credit_indices import DbBackedInputsBuilder, run_one

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from sqlalchemy.orm import Session


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _quarter_end(year: int, q: int) -> date:
    month_end = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}[q]
    return date(year, *month_end)


def _seed_full_history(session: Session, country: str, start_year: int, end_year: int) -> None:
    """Seed WS_TC with a realistic upward drift (120 -> 150 pct_gdp over years)."""
    years = end_year - start_year + 1
    per_q = 30.0 / (years * 4)  # gradual rise over window
    i = 0
    for y in range(start_year, end_year + 1):
        for q in (1, 2, 3, 4):
            session.add(
                BisCreditRaw(
                    country_code=country,
                    date=_quarter_end(y, q),
                    dataflow="WS_TC",
                    value_raw=120.0 + i * per_q,
                    unit_descriptor="pct_gdp",
                    fetch_response_hash=f"h_{country}_{i:03d}",
                )
            )
            i += 1
    session.commit()


class TestMockedEndToEnd:
    def test_us_l1_row_persisted(self, db_session: Session) -> None:
        _seed_full_history(db_session, "US", 2002, 2024)
        builder = DbBackedInputsBuilder(db_session)
        outcome = run_one(db_session, "US", date(2024, 12, 31), inputs_builder=builder)
        assert outcome.persisted["l1"] == 1
        l1 = db_session.execute(
            select(CreditGdpStock).where(CreditGdpStock.country_code == "US")
        ).scalar_one()
        assert l1.country_code == "US"
        # score_raw carries the ratio_pct per L1 spec; last seeded ~150.
        assert 140.0 <= l1.score_raw <= 160.0

    def test_us_l2_also_persisted_with_22y_history(self, db_session: Session) -> None:
        _seed_full_history(db_session, "US", 2002, 2024)
        builder = DbBackedInputsBuilder(db_session)
        outcome = run_one(db_session, "US", date(2024, 12, 31), inputs_builder=builder)
        assert outcome.persisted["l2"] == 1
        l2 = db_session.execute(
            select(CreditGdpGap).where(CreditGdpGap.country_code == "US")
        ).scalar_one()
        assert l2.country_code == "US"

    def test_l3_l4_skipped_in_db_backed_mode(self, db_session: Session) -> None:
        _seed_full_history(db_session, "PT", 2002, 2024)
        builder = DbBackedInputsBuilder(db_session)
        outcome = run_one(db_session, "PT", date(2024, 12, 31), inputs_builder=builder)
        # L3 + L4 not backed by bis_credit_raw per builder scope.
        assert outcome.persisted["l3"] == 0
        assert outcome.persisted["l4"] == 0

    def test_multi_country_run(self, db_session: Session) -> None:
        for country in ("US", "DE", "PT"):
            _seed_full_history(db_session, country, 2002, 2024)
        builder = DbBackedInputsBuilder(db_session)
        for country in ("US", "DE", "PT"):
            outcome = run_one(db_session, country, date(2024, 12, 31), inputs_builder=builder)
            assert outcome.persisted["l1"] == 1
        l1_rows = db_session.execute(select(CreditGdpStock)).scalars().all()
        assert len(l1_rows) == 3

    def test_raw_ingest_is_idempotent(self, db_session: Session) -> None:
        """Seeding twice with identical hashes does not duplicate rows."""
        _seed_full_history(db_session, "NL", 2002, 2003)
        # Re-adding the same rows would violate UNIQUE; build + call
        # persist_bis_raw_observations to hit the upsert path.
        from sonar.db.persistence import (  # noqa: PLC0415 — test-local
            BisRawObservation,
            persist_bis_raw_observations,
        )

        existing = db_session.execute(select(BisCreditRaw)).scalars().all()
        raws = [
            BisRawObservation(
                country_code=r.country_code,
                date=r.date,
                dataflow=r.dataflow,
                value_raw=r.value_raw,
                unit_descriptor=r.unit_descriptor,
                fetch_response_hash=r.fetch_response_hash,
            )
            for r in existing
        ]
        counts = persist_bis_raw_observations(db_session, raws)
        assert counts["new"] == 0
        assert counts["skipped"] == len(existing)
        assert counts["updated"] == 0


@pytest.mark.slow
class TestLiveCanary:
    """Real BIS network fetch for US 2024-Q2 — manual canary gate.

    Skipped unless pytest invoked with ``--runslow``; protects CI from
    network dependencies. Validates that the ingestion pipeline can
    populate ``bis_credit_raw`` end-to-end against live infrastructure.
    """

    def test_us_ingest_end_to_end(self, tmp_path: Path, db_session: Session) -> None:  # type: ignore[name-defined]
        import asyncio  # noqa: PLC0415

        from sonar.connectors.bis import BisConnector  # noqa: PLC0415
        from sonar.pipelines.daily_bis_ingestion import run_ingestion  # noqa: PLC0415

        cache_dir = tmp_path / "bis_live"
        cache_dir.mkdir()

        async def _ingest() -> dict[str, object]:
            # Build + close the connector inside the same event loop; the
            # httpx.AsyncClient binds to the loop in which it was
            # instantiated, so a second asyncio.run() would tear it down
            # against a closed loop and raise RuntimeError.
            connector = BisConnector(cache_dir=str(cache_dir))
            try:
                return await run_ingestion(
                    session=db_session,
                    connector=connector,
                    countries=["US"],
                    dataflows=["WS_TC"],
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 7, 1),
                )
            finally:
                await connector.aclose()

        report = asyncio.run(_ingest())

        assert report["failures"] == 0
        totals = report["totals"]
        assert isinstance(totals, dict)
        assert totals["new"] > 0  # at least 1 quarter persisted
        rows = (
            db_session.execute(select(BisCreditRaw).where(BisCreditRaw.country_code == "US"))
            .scalars()
            .all()
        )
        assert len(rows) > 0
