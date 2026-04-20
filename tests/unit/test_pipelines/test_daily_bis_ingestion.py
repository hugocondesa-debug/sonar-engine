"""Unit tests for daily_bis_ingestion pipeline + persist_bis_raw_observations."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import sonar.db.session  # noqa: F401 — register fk-on pragma listener
from sonar.connectors.bis import BisObservation
from sonar.db.models import Base, BisCreditRaw
from sonar.db.persistence import persist_bis_raw_observations
from sonar.pipelines.daily_bis_ingestion import (
    DATAFLOWS,
    T1_COUNTRIES,
    UNIT_DESCRIPTOR,
    _hash_obs,
    _parse_csv_list,
    _to_raw,
    run_ingestion,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

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


def _obs(country: str = "US", year: int = 2024, q: int = 2, value: float = 255.3) -> BisObservation:
    month_end = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}[q]
    return BisObservation(
        country_code=country,
        observation_date=date(year, *month_end),
        value_pct=value,
        source="BIS_WS_TC",
        source_series_key=f"Q.{country}.P.A.M.770.A",
    )


class TestHashing:
    def test_hash_is_deterministic(self) -> None:
        a = _obs()
        assert _hash_obs(a) == _hash_obs(a)

    def test_hash_changes_on_value_change(self) -> None:
        assert _hash_obs(_obs(value=255.3)) != _hash_obs(_obs(value=256.0))

    def test_hash_stable_across_keys(self) -> None:
        # Different series_key → different hash (even if same value).
        a = _obs()
        b = BisObservation(
            country_code="US",
            observation_date=a.observation_date,
            value_pct=a.value_pct,
            source="BIS_WS_DSR",
            source_series_key="Q.US.P",
        )
        assert _hash_obs(a) != _hash_obs(b)


class TestToRaw:
    def test_unit_descriptor_applied(self) -> None:
        raw = _to_raw(_obs(), "WS_TC")
        assert raw.unit_descriptor == UNIT_DESCRIPTOR["WS_TC"]

    def test_values_propagate(self) -> None:
        raw = _to_raw(_obs(value=14.5), "WS_DSR")
        assert raw.value_raw == pytest.approx(14.5)
        assert raw.dataflow == "WS_DSR"
        assert raw.country_code == "US"


class TestParseCsv:
    def test_empty_returns_default(self) -> None:
        assert _parse_csv_list("", T1_COUNTRIES) == list(T1_COUNTRIES)

    def test_parses_csv(self) -> None:
        assert _parse_csv_list("US,DE", T1_COUNTRIES) == ["US", "DE"]

    def test_rejects_unknown(self) -> None:
        import typer  # noqa: PLC0415

        with pytest.raises(typer.BadParameter):
            _parse_csv_list("XX,YY", T1_COUNTRIES)


class TestPersistUpsert:
    def test_new_rows_counted(self, db_session: Session) -> None:
        obs = [_to_raw(_obs(country="US", q=2, value=255.0), "WS_TC")]
        counts = persist_bis_raw_observations(db_session, obs)
        assert counts == {"new": 1, "skipped": 0, "updated": 0}
        rows = db_session.execute(select(BisCreditRaw)).scalars().all()
        assert len(rows) == 1

    def test_same_hash_skipped(self, db_session: Session) -> None:
        obs1 = _to_raw(_obs(value=255.0), "WS_TC")
        persist_bis_raw_observations(db_session, [obs1])
        counts = persist_bis_raw_observations(db_session, [obs1])
        assert counts == {"new": 0, "skipped": 1, "updated": 0}

    def test_different_hash_updates(self, db_session: Session) -> None:
        obs1 = _to_raw(_obs(value=255.0), "WS_TC")
        persist_bis_raw_observations(db_session, [obs1])
        obs2 = _to_raw(_obs(value=256.5), "WS_TC")  # same triplet, different value
        counts = persist_bis_raw_observations(db_session, [obs2])
        assert counts == {"new": 0, "skipped": 0, "updated": 1}
        row = db_session.execute(select(BisCreditRaw)).scalar_one()
        assert row.value_raw == pytest.approx(256.5)

    def test_empty_input_noop(self, db_session: Session) -> None:
        assert persist_bis_raw_observations(db_session, []) == {
            "new": 0,
            "skipped": 0,
            "updated": 0,
        }


class TestRunIngestion:
    async def test_happy_multi_country(self, db_session: Session) -> None:
        fake_connector = AsyncMock()
        fake_connector.fetch_credit_stock_ratio = AsyncMock(
            side_effect=lambda c, s, e: [_obs(country=c, value=250.0 + ord(c[0]))]
        )
        fake_connector.fetch_dsr = AsyncMock(return_value=[])
        fake_connector.fetch_credit_gap = AsyncMock(return_value=[])
        report = await run_ingestion(
            session=db_session,
            connector=fake_connector,
            countries=["US", "DE"],
            dataflows=["WS_TC"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 7, 1),
        )
        assert report["successes"] == 2
        assert report["failures"] == 0
        totals = report["totals"]
        assert isinstance(totals, dict)
        assert totals["new"] == 2

    async def test_partial_failure_counted(self, db_session: Session) -> None:
        fake_connector = AsyncMock()

        async def fake_tc(country: str, s: date, e: date) -> list[BisObservation]:
            if country == "PT":
                msg = "simulated fetch error"
                raise RuntimeError(msg)
            return [_obs(country=country)]

        fake_connector.fetch_credit_stock_ratio = fake_tc
        report = await run_ingestion(
            session=db_session,
            connector=fake_connector,
            countries=["US", "PT"],
            dataflows=["WS_TC"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 7, 1),
        )
        assert report["successes"] == 1
        assert report["failures"] == 1

    async def test_dispatch_all_three_dataflows(self, db_session: Session) -> None:
        fake_connector = AsyncMock()
        fake_connector.fetch_credit_stock_ratio = AsyncMock(return_value=[_obs(country="US")])
        fake_connector.fetch_dsr = AsyncMock(return_value=[_obs(country="US", value=14.5)])
        fake_connector.fetch_credit_gap = AsyncMock(return_value=[_obs(country="US", value=-1.2)])
        report = await run_ingestion(
            session=db_session,
            connector=fake_connector,
            countries=["US"],
            dataflows=list(DATAFLOWS),
            start_date=date(2024, 1, 1),
            end_date=date(2024, 7, 1),
        )
        assert report["successes"] == 3
        fake_connector.fetch_credit_stock_ratio.assert_called_once()
        fake_connector.fetch_dsr.assert_called_once()
        fake_connector.fetch_credit_gap.assert_called_once()


class TestCli:
    def test_cli_invalid_date_exits_config(self) -> None:
        import typer  # noqa: PLC0415
        from typer.testing import CliRunner  # noqa: PLC0415

        from sonar.pipelines.daily_bis_ingestion import main  # noqa: PLC0415

        app = typer.Typer()
        app.command()(main)
        runner = CliRunner()
        result = runner.invoke(app, ["--start-date", "not-a-date"])
        assert result.exit_code == 1
        assert "Invalid date" in result.output

    def test_cli_reversed_dates_exits_config(self) -> None:
        import typer  # noqa: PLC0415
        from typer.testing import CliRunner  # noqa: PLC0415

        from sonar.pipelines.daily_bis_ingestion import main  # noqa: PLC0415

        app = typer.Typer()
        app.command()(main)
        runner = CliRunner()
        result = runner.invoke(app, ["--start-date", "2024-06-01", "--end-date", "2024-01-01"])
        assert result.exit_code == 1
        assert "after end-date" in result.output

    def test_cli_unknown_country_exits_config(self) -> None:
        import typer  # noqa: PLC0415
        from typer.testing import CliRunner  # noqa: PLC0415

        from sonar.pipelines.daily_bis_ingestion import main  # noqa: PLC0415

        app = typer.Typer()
        app.command()(main)
        runner = CliRunner()
        result = runner.invoke(
            app, ["--start-date", "2024-01-01", "--end-date", "2024-07-01", "--countries", "XX"]
        )
        assert result.exit_code == 1
