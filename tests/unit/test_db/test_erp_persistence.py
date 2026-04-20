"""Unit tests for persist_erp_fit_result — in-memory SQLite."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from sonar.db.models import ERPCAPE, ERPDCF, ERPEY, ERPCanonical, ERPGordon
from sonar.db.persistence import DuplicatePersistError, persist_erp_fit_result
from sonar.overlays.erp import ERPInput, fit_erp_us

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _us_inputs(**overrides: object) -> ERPInput:
    base: dict[str, object] = {
        "market_index": "SPX",
        "country_code": "US",
        "observation_date": date(2024, 1, 2),
        "index_level": 4742.83,
        "trailing_earnings": 221.41,
        "forward_earnings_est": 243.73,
        "dividend_yield_pct": 0.0155,
        "buyback_yield_pct": 0.025,
        "cape_ratio": 31.5,
        "risk_free_nominal": 0.0415,
        "risk_free_real": 0.0175,
        "consensus_growth_5y": 0.10,
        "retention": 0.60,
        "roe": 0.20,
        "risk_free_confidence": 0.95,
        "upstream_flags": (),
    }
    base.update(overrides)
    return ERPInput(**base)  # type: ignore[arg-type]


class TestPersistErpFit:
    def test_happy_path_persists_5_rows(self, db_session: Session) -> None:
        inputs = _us_inputs()
        result = fit_erp_us(inputs)
        assert result.canonical.methods_available == 4
        persist_erp_fit_result(db_session, result, inputs)

        dcf_rows = db_session.execute(select(ERPDCF)).scalars().all()
        gordon_rows = db_session.execute(select(ERPGordon)).scalars().all()
        ey_rows = db_session.execute(select(ERPEY)).scalars().all()
        cape_rows = db_session.execute(select(ERPCAPE)).scalars().all()
        canonical_rows = db_session.execute(select(ERPCanonical)).scalars().all()

        assert len(dcf_rows) == 1
        assert len(gordon_rows) == 1
        assert len(ey_rows) == 1
        assert len(cape_rows) == 1
        assert len(canonical_rows) == 1

        canonical = canonical_rows[0]
        assert canonical.erp_id == str(result.erp_id)
        assert canonical.market_index == "SPX"
        assert canonical.methods_available == 4
        assert canonical.erp_dcf_bps is not None

    def test_three_methods_persists_4_rows(self, db_session: Session) -> None:
        # Zero payout kills DCF → 3 method rows + 1 canonical = 4 total.
        inputs = _us_inputs(dividend_yield_pct=0.0, buyback_yield_pct=0.0)
        result = fit_erp_us(inputs)
        assert result.dcf is None
        persist_erp_fit_result(db_session, result, inputs)

        assert db_session.execute(select(ERPDCF)).scalars().all() == []
        canonical = db_session.execute(select(ERPCanonical)).scalar_one()
        assert canonical.methods_available == 3
        assert canonical.erp_dcf_bps is None

    def test_duplicate_raises_and_rolls_back(self, db_session: Session) -> None:
        inputs = _us_inputs()
        result = fit_erp_us(inputs)
        persist_erp_fit_result(db_session, result, inputs)

        # Re-persist with same UUID would collide on the canonical
        # uq_erp_canonical_erp_id as well as method-table uq_*_mdm triplets.
        with pytest.raises(DuplicatePersistError, match="ERP fit already persisted"):
            persist_erp_fit_result(db_session, result, inputs)

    def test_xval_field_stored(self, db_session: Session) -> None:
        inputs = _us_inputs()
        # Damodaran ERP 5.00% — compare vs our DCF erp.
        result = fit_erp_us(inputs, damodaran_erp_decimal=0.05)
        persist_erp_fit_result(db_session, result, inputs)
        canonical = db_session.execute(select(ERPCanonical)).scalar_one()
        assert canonical.xval_deviation_bps is not None

    def test_canonical_bps_matches_result(self, db_session: Session) -> None:
        inputs = _us_inputs()
        result = fit_erp_us(inputs)
        persist_erp_fit_result(db_session, result, inputs)
        canonical = db_session.execute(select(ERPCanonical)).scalar_one()
        assert canonical.erp_median_bps == result.canonical.erp_median_bps
