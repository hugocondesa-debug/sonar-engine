"""Tests for the financial-cycle orchestrator + --all-cycles CLI."""

from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING

from sonar.indices.orchestrator import (
    FinancialIndicesInputs,
    _synthetic_financial_inputs,
    compute_all_financial_indices,
    main,
)

if TYPE_CHECKING:
    import pytest


def test_compute_all_financial_with_synthetic_us() -> None:
    inputs = _synthetic_financial_inputs("US", date(2024, 1, 2))
    results = compute_all_financial_indices(inputs)
    assert results.f1 is not None
    assert results.f2 is not None
    assert results.f3 is not None
    assert results.f4 is not None
    assert results.available() == ["f1", "f2", "f3", "f4"]
    # Scores should be in the canonical [0, 100] range.
    for r in (results.f1, results.f2, results.f3, results.f4):
        assert 0.0 <= r.score_normalized <= 100.0


def test_compute_all_financial_empty_inputs_skip() -> None:
    inputs = FinancialIndicesInputs(country_code="US", observation_date=date(2024, 1, 2))
    results = compute_all_financial_indices(inputs)
    assert results.f1 is None
    assert results.f2 is None
    assert results.f3 is None
    assert results.f4 is None
    assert set(results.skips.keys()) == {"f1", "f2", "f3", "f4"}


def test_compute_all_financial_skip_preserves_success() -> None:
    """Partial bundle: only F1 present. F2/F3/F4 absent → skipped."""
    inputs = FinancialIndicesInputs(
        country_code="XX",
        observation_date=date(2024, 1, 2),
        f1=_synthetic_financial_inputs("XX", date(2024, 1, 2)).f1,
    )
    results = compute_all_financial_indices(inputs)
    assert results.f1 is not None
    assert results.f2 is None
    assert results.available() == ["f1"]


def test_cli_financial_only(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["--country", "US", "--date", "2024-01-02", "--financial-only"])
    assert rc == 0
    stdout = capsys.readouterr().out
    payload = json.loads(stdout)
    assert "financial_indices" in payload
    for key in ("f1", "f2", "f3", "f4"):
        assert key in payload["financial_indices"]
        assert payload["financial_indices"][key] is not None


def test_cli_all_cycles(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["--country", "US", "--date", "2024-01-02", "--all-cycles"])
    assert rc == 0
    stdout = capsys.readouterr().out
    payload = json.loads(stdout)
    # All three tracks present.
    assert "indices" in payload
    assert "credit_indices" in payload
    assert "financial_indices" in payload
    assert {"f1", "f2", "f3", "f4"} <= set(payload["financial_indices"].keys())


def test_cli_default_lacks_financial(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["--country", "US", "--date", "2024-01-02"])
    assert rc == 0
    stdout = capsys.readouterr().out
    payload = json.loads(stdout)
    assert "financial_indices" not in payload  # only appears with --all-cycles
