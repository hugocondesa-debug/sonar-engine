"""Monetary orchestrator tests (week6 sprint 2b C6)."""

from __future__ import annotations

from datetime import date

from sonar.connectors.ecb_sdw import EcbMonetaryObservation
from sonar.indices.monetary.builders import build_m1_ea_inputs
from sonar.indices.monetary.m4_fci import M4FciInputs
from sonar.indices.monetary.orchestrator import (
    MonetaryIndicesInputs,
    compute_all_monetary_indices,
)


def test_all_skips_when_no_inputs() -> None:
    results = compute_all_monetary_indices(
        MonetaryIndicesInputs(country_code="US", observation_date=date(2024, 12, 31))
    )
    assert results.m1 is None
    assert results.m2 is None
    assert results.m4 is None
    assert set(results.skips) == {"m1", "m2", "m4"}
    assert results.available() == []


def test_partial_availability_populates_skips() -> None:
    inputs = MonetaryIndicesInputs(
        country_code="US",
        observation_date=date(2024, 12, 31),
        m4=M4FciInputs(
            country_code="US",
            observation_date=date(2024, 12, 31),
            nfci_level=-0.5,
            fci_level_12m_ago=-0.4,
        ),
    )
    results = compute_all_monetary_indices(inputs)
    assert results.m4 is not None
    assert results.m1 is None
    assert results.m2 is None
    assert "m1" in results.skips
    assert results.available() == ["m4"]


class _FakeEcb:
    async def fetch_dfr_rate(self, _start: date, _end: date) -> list[object]:
        return [
            EcbMonetaryObservation(
                observation_date=date(2024, 12, 1),
                value=3.0,
                dataflow="FM",
                source_series_id="D.U2.EUR.4F.KR.DFR.LEV",
            )
        ]

    async def fetch_eurosystem_balance_sheet(self, _start: date, _end: date) -> list[object]:
        return [
            EcbMonetaryObservation(
                observation_date=date(2024, 12, 13),
                value=6_400_000.0,
                dataflow="ILM",
                source_series_id="W.U2.C.T000000.Z5.Z01",
            ),
            EcbMonetaryObservation(
                observation_date=date(2023, 12, 15),
                value=6_800_000.0,
                dataflow="ILM",
                source_series_id="W.U2.C.T000000.Z5.Z01",
            ),
        ]


async def test_ea_m1_inputs_flow_through_orchestrator() -> None:
    m1_inputs = await build_m1_ea_inputs(_FakeEcb(), date(2024, 12, 31), history_years=2)  # type: ignore[arg-type]
    results = compute_all_monetary_indices(
        MonetaryIndicesInputs(
            country_code="EA",
            observation_date=date(2024, 12, 31),
            m1=m1_inputs,
        )
    )
    assert results.m1 is not None
    assert 0 <= results.m1.score_normalized <= 100
