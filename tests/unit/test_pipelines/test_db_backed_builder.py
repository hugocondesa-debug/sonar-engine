"""Unit tests for DbBackedInputsBuilder (CAL-058 c4/6)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sonar.db.session  # noqa: F401
from sonar.db.models import Base, BisCreditRaw
from sonar.pipelines.daily_credit_indices import (
    L1_L2_LOOKBACK_YEARS,
    MIN_L1_HISTORY_QUARTERS,
    DbBackedInputsBuilder,
    InsufficientInputsError,
    _interpolate_quarterly,
    _quarters_between,
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


def _quarter_end(year: int, q: int) -> date:
    month_end = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}[q]
    return date(year, *month_end)


def _seed_ws_tc(
    session: Session,
    country: str,
    start_year: int,
    end_year: int,
    base: float = 100.0,
    *,
    skip: set[date] | None = None,
) -> None:
    """Seed quarterly WS_TC observations from ``start_year`` Q1 through ``end_year`` Q4."""
    skip = skip or set()
    i = 0
    for y in range(start_year, end_year + 1):
        for q in (1, 2, 3, 4):
            d = _quarter_end(y, q)
            if d in skip:
                i += 1
                continue
            session.add(
                BisCreditRaw(
                    country_code=country,
                    date=d,
                    dataflow="WS_TC",
                    value_raw=base + i * 0.5,
                    unit_descriptor="pct_gdp",
                    fetch_response_hash=f"hash_{country}_{i:03d}",
                )
            )
            i += 1
    session.commit()


class TestQuartersBetween:
    def test_same_year_one_quarter(self) -> None:
        assert _quarters_between(_quarter_end(2024, 1), _quarter_end(2024, 2)) == 1

    def test_across_year(self) -> None:
        assert _quarters_between(_quarter_end(2023, 4), _quarter_end(2024, 1)) == 1

    def test_multiple_quarters(self) -> None:
        assert _quarters_between(_quarter_end(2023, 1), _quarter_end(2024, 1)) == 4


class TestInterpolateQuarterly:
    def test_empty_input(self) -> None:
        assert _interpolate_quarterly([]) == []

    def test_dense_series_passthrough(self) -> None:
        pts = [(_quarter_end(2024, q), 100.0 + q) for q in (1, 2, 3, 4)]
        assert _interpolate_quarterly(pts) == [101.0, 102.0, 103.0, 104.0]

    def test_single_gap_interpolated(self) -> None:
        # Skip Q2 2024 → Q1 value 100, Q3 value 104 → Q2 interpolated to 102.
        pts = [
            (_quarter_end(2024, 1), 100.0),
            (_quarter_end(2024, 3), 104.0),
            (_quarter_end(2024, 4), 106.0),
        ]
        result = _interpolate_quarterly(pts)
        assert result == [100.0, 102.0, 104.0, 106.0]

    def test_multi_quarter_gap_raises(self) -> None:
        # 3-quarter gap — above tolerance.
        pts = [
            (_quarter_end(2023, 1), 100.0),
            (_quarter_end(2024, 1), 110.0),
        ]
        with pytest.raises(InsufficientInputsError, match="Gap of 4 quarters"):
            _interpolate_quarterly(pts)


class TestDbBackedBuilder:
    def test_no_ws_tc_raises(self, db_session: Session) -> None:
        builder = DbBackedInputsBuilder(db_session)
        with pytest.raises(InsufficientInputsError, match="No WS_TC"):
            builder.build("US", date(2024, 6, 30))

    def test_history_too_short_raises(self, db_session: Session) -> None:
        # 4 quarters only — well under MIN_L1_HISTORY_QUARTERS.
        _seed_ws_tc(db_session, "US", 2023, 2023)
        builder = DbBackedInputsBuilder(db_session)
        with pytest.raises(InsufficientInputsError, match="too short"):
            builder.build("US", date(2023, 12, 31))

    def test_l1_populated_l2_l3_l4_none_when_under_l2_threshold(self, db_session: Session) -> None:
        # Exactly MIN_L1_HISTORY_QUARTERS quarters of history (5Y).
        _seed_ws_tc(db_session, "US", 2020, 2024)  # 20 quarters
        builder = DbBackedInputsBuilder(db_session)
        inputs = builder.build("US", date(2024, 12, 31))
        assert inputs.l1 is not None
        assert len(inputs.l1.ratio_pct_history) >= MIN_L1_HISTORY_QUARTERS
        # 20 quarters < 80 (L2 threshold) → L2 should be None.
        assert inputs.l2 is None
        assert inputs.l3 is None
        assert inputs.l4 is None

    def test_l1_and_l2_populated_with_sufficient_history(self, db_session: Session) -> None:
        # 22Y * 4 = 88 quarters — exceeds L2 80-quarter minimum.
        _seed_ws_tc(db_session, "PT", 2002, 2024)
        builder = DbBackedInputsBuilder(db_session)
        inputs = builder.build("PT", date(2024, 12, 31))
        assert inputs.l1 is not None
        assert inputs.l2 is not None
        assert len(inputs.l2.ratio_pct_history) >= 80

    def test_cutoff_respected(self, db_session: Session) -> None:
        # Seed 30 years; builder's lookback is L1_L2_LOOKBACK_YEARS (22).
        _seed_ws_tc(db_session, "DE", 1995, 2024)
        builder = DbBackedInputsBuilder(db_session)
        inputs = builder.build("DE", date(2024, 12, 31))
        # Expected cut: observation_date - 22Y = 2002-12-31 boundary.
        # 22 * 4 + 1 ~ 89 quarters returned at most.
        assert inputs.l1 is not None
        assert len(inputs.l1.ratio_pct_history) <= L1_L2_LOOKBACK_YEARS * 4 + 1

    def test_gap_interpolation_end_to_end(self, db_session: Session) -> None:
        # 22Y minus one interior quarter → builder fills via interp.
        skip = {_quarter_end(2015, 2)}
        _seed_ws_tc(db_session, "IT", 2002, 2024, skip=skip)
        builder = DbBackedInputsBuilder(db_session)
        inputs = builder.build("IT", date(2024, 12, 31))
        assert inputs.l1 is not None
        assert inputs.l2 is not None
