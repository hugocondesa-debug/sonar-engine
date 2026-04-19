"""Fixtures for db unit tests — in-memory SQLite + spec §8 schema."""

from collections.abc import Iterator
from datetime import date

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Import session module so the connect-event listener gets registered before
# we create our own engine — guarantees PRAGMA foreign_keys=ON.
import sonar.db.session  # noqa: F401
from sonar.db.models import Base
from sonar.overlays.nss import (
    ForwardCurve,
    NSSFitResult,
    NSSInput,
    RealCurve,
    SpotCurve,
    ZeroCurve,
    assemble_nss_fit_result,
    derive_forward_curve,
    derive_zero_curve,
    fit_nss,
)


@pytest.fixture
def db_session() -> Iterator[Session]:
    """Fresh in-memory SQLite + Base.metadata.create_all per test."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def us_fit_result() -> NSSFitResult:
    """Realistic NSSFitResult for US 2024-01-02 — drives multi-table persist tests."""
    inp = NSSInput(
        tenors_years=np.array([1 / 12, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 20.0, 30.0]),
        yields=np.array(
            [0.0552, 0.0540, 0.0526, 0.0480, 0.0433, 0.0405, 0.0393, 0.0397, 0.0395, 0.0422, 0.0408]
        ),
        country_code="US",
        observation_date=date(2024, 1, 2),
        curve_input_type="par",
    )
    spot: SpotCurve = fit_nss(inp)
    zero: ZeroCurve = derive_zero_curve(spot)
    forward: ForwardCurve = derive_forward_curve(zero)
    real: RealCurve | None = None
    return assemble_nss_fit_result(
        country_code="US",
        observation_date=date(2024, 1, 2),
        spot=spot,
        zero=zero,
        forward=forward,
        real=real,
    )
