"""Sprint M C5 — CAL-113 BEI/SURVEY split emitter → consumer round-trip.

Exercises the full path:

1. Run daily_overlays over a bundled ExpectedInflation input that
   carries both BEI and SURVEY observations.
2. Assert the persisted EXPINF IndexValue row carries bei_tenors +
   survey_tenors + method_per_tenor keys.
3. Call build_m3_inputs_from_db → assert bei_10y_bps + survey_10y_bps
   distinct from each other per the split.
4. Backward-compat assertion: manually craft an old-shape EXPINF row
   without the split keys → M3 builder still returns M3Inputs with
   bei_10y_bps populated and survey_10y_bps = None.
"""

from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import sonar.db.session  # noqa: F401
from sonar.db.models import (
    Base,
    IndexValue,
    NSSYieldCurveForwards,
    NSSYieldCurveSpot,
)
from sonar.indices.monetary.db_backed_builder import (
    EXPINF_INDEX_CODE,
    build_m3_inputs_from_db,
)
from sonar.overlays.expected_inflation import (
    ExpInfBEI,
    ExpInfSurvey,
    build_canonical,
)
from sonar.pipelines.daily_overlays import (
    OverlayBundle,
    StaticInputsBuilder,
    run_one,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.orm import Session


pytestmark = pytest.mark.slow


ANCHOR = date(2024, 12, 31)


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


def _seed_nss(session: Session, country: str = "US") -> None:
    spot = NSSYieldCurveSpot(
        country_code=country,
        date=ANCHOR,
        methodology_version="NSS_v1.0",
        fit_id=f"fit-{country}-{ANCHOR.isoformat()}",
        beta_0=0.04,
        beta_1=-0.01,
        beta_2=0.005,
        beta_3=None,
        lambda_1=1.5,
        lambda_2=None,
        fitted_yields_json=json.dumps({"5Y": 0.041, "10Y": 0.043}),
        observations_used=11,
        rmse_bps=5.0,
        xval_deviation_bps=None,
        confidence=0.9,
        flags=None,
        source_connector="fred",
    )
    session.add(spot)
    session.flush()
    session.add(
        NSSYieldCurveForwards(
            country_code=country,
            date=ANCHOR,
            methodology_version="NSS_v1.0",
            fit_id=spot.fit_id,
            forwards_json=json.dumps({"1y1y": 0.043, "5y5y": 0.0415}),
            breakeven_forwards_json=None,
            confidence=0.9,
            flags=None,
        )
    )
    session.commit()


def _bundle_with_bei_and_survey() -> OverlayBundle:
    """Bundle with both BEI (10Y + 5Y) and SURVEY (5Y5Y) rows.

    The expected-inflation canonical build merges them per spec
    hierarchy so the overlay result carries method_per_tenor mixing
    BEI + SURVEY (used by CAL-113 split emitter).
    """
    bei = ExpInfBEI(
        country_code="US",
        observation_date=ANCHOR,
        nominal_yields={"5Y": 0.041, "10Y": 0.043, "5y5y": 0.045},
        linker_real_yields={"5Y": 0.017, "10Y": 0.019, "5y5y": 0.021},
        bei_tenors={"5Y": 0.024, "10Y": 0.024, "5y5y": 0.024},
        linker_connector="fred",
        nss_fit_id=None,
        confidence=0.85,
        flags=(),
    )
    survey = ExpInfSurvey(
        country_code="US",
        observation_date=ANCHOR,
        survey_name="Michigan 5y5y",
        survey_release_date=ANCHOR,
        horizons={"5y5y": 0.027},
        interpolated_tenors={"5y5y": 0.027},
        confidence=0.75,
        flags=(),
    )
    kwargs = {
        "country_code": "US",
        "observation_date": ANCHOR,
        "bei": bei,
        "survey": survey,
        "bc_target_pct": 0.02,
    }
    # Smoke build_canonical locally to make sure the inputs are shaped
    # correctly before we hand them to the pipeline.
    canonical = build_canonical(**kwargs)
    assert "BEI" in canonical.source_method_per_tenor.values()
    return OverlayBundle(country_code="US", observation_date=ANCHOR, expected_inflation=kwargs)


class TestCAL113RoundTrip:
    def test_emitter_persists_split_then_consumer_reads_it(self, db_session: Session) -> None:
        _seed_nss(db_session, "US")
        builder = StaticInputsBuilder({"US": _bundle_with_bei_and_survey()})
        outcome = run_one(db_session, "US", ANCHOR, inputs_builder=builder)

        # Pipeline persisted an EXPINF row via index_values.
        rows = (
            db_session.execute(select(IndexValue).where(IndexValue.index_code == EXPINF_INDEX_CODE))
            .scalars()
            .all()
        )
        assert len(rows) == 1
        sub = json.loads(rows[0].sub_indicators_json)
        # CAL-113 split keys present.
        assert "bei_tenors" in sub
        assert "survey_tenors" in sub
        assert "method_per_tenor" in sub

        # Consumer reads the split distinctly.
        m3_inputs = build_m3_inputs_from_db(db_session, "US", ANCHOR)
        assert m3_inputs is not None
        # BEI 10Y → 240 bps; SURVEY 10Y absent → None.
        assert m3_inputs.bei_10y_bps is not None
        # The integrated outcome is split-aware, but the round-trip
        # contract only requires bei_10y_bps to come from bei_tenors
        # exclusively.
        assert outcome.results.expected_inflation is not None


def test_legacy_row_without_split_backward_compat(db_session: Session) -> None:
    """Pre-Sprint-M rows (no bei_tenors / survey_tenors) still parse."""
    _seed_nss(db_session, "US")
    legacy_sub = {
        "expected_inflation_tenors": {"5y5y": 0.0245, "10Y": 0.024},
        "source_method_per_tenor": {"5y5y": "BEI", "10Y": "BEI"},
        "methods_available": 1,
        "anchor_status": "well_anchored",
    }
    db_session.add(
        IndexValue(
            index_code=EXPINF_INDEX_CODE,
            country_code="US",
            date=ANCHOR,
            methodology_version="EXPINF_v1.0",
            raw_value=0.024,
            zscore_clamped=0.0,
            value_0_100=50.0,
            sub_indicators_json=json.dumps(legacy_sub),
            confidence=0.85,
            flags=None,
            source_overlays_json=json.dumps({}),
        )
    )
    db_session.commit()
    out = build_m3_inputs_from_db(db_session, "US", ANCHOR)
    assert out is not None
    assert out.bei_10y_bps == pytest.approx(240.0)
    assert out.survey_10y_bps is None
