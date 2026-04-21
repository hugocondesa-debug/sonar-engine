"""Tests for MetaRegimeClassifier + 8 canonical fixtures.

Each fixture mirrors a scenario from
``docs/specs/regimes/cross-cycle-meta-regimes.md`` §7. They are
authored as builders here (not JSON) to keep the test self-contained;
the contract is that a classifier returning different
``meta_regime`` or ``classification_reason`` values for any of these
8 inputs has a bug in the decision tree.
"""

# ruff: noqa: FBT003 — Snapshot positional booleans are intentional in test builders

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from sonar.regimes import (
    InsufficientL4DataError,
    L5RegimeInputs,
    MetaRegime,
    MetaRegimeClassifier,
)
from sonar.regimes.meta_regime_classifier import (
    CONFIDENCE_CAP_ONE_MISSING,
    MIN_L4_CYCLES,
)
from sonar.regimes.types import (
    CccsSnapshot,
    EcsSnapshot,
    FcsSnapshot,
    MscSnapshot,
)

ANCHOR = date(2024, 12, 31)


def _fixture_overheating() -> L5RegimeInputs:
    """Fixture 1 — US 2021-Q2 style peak + boom + optimism."""
    return L5RegimeInputs(
        country_code="US",
        date=ANCHOR,
        ecs=EcsSnapshot("ecs-1", 75.0, "PEAK_ZONE", False, 0.85),
        cccs=CccsSnapshot("cccs-1", 78.0, "BOOM", True, 0.85),
        fcs=FcsSnapshot("fcs-1", 72.0, "OPTIMISM", False, 0.85),
        msc=MscSnapshot("msc-1", 58.0, "NEUTRAL", False, 0.85),
    )


def _fixture_stagflation_risk() -> L5RegimeInputs:
    """Fixture 2 — US 1974 style stagflation + dilemma."""
    return L5RegimeInputs(
        country_code="US",
        date=ANCHOR,
        ecs=EcsSnapshot("ecs-2", 48.0, "EARLY_RECESSION", True, 0.85),
        cccs=CccsSnapshot("cccs-2", 45.0, "REPAIR", False, 0.85),
        fcs=FcsSnapshot("fcs-2", 35.0, "STRESS", False, 0.85),
        msc=MscSnapshot("msc-2", 72.0, "TIGHT", True, 0.85),
    )


def _fixture_late_cycle_bubble() -> L5RegimeInputs:
    """Fixture 3 — US 2007-Q2 euphoria + bubble warning + speculation."""
    return L5RegimeInputs(
        country_code="US",
        date=ANCHOR,
        ecs=EcsSnapshot("ecs-3", 68.0, "PEAK_ZONE", False, 0.85),
        cccs=CccsSnapshot("cccs-3", 85.0, "SPECULATION", True, 0.85),
        fcs=FcsSnapshot("fcs-3", 92.0, "EUPHORIA", True, 0.85),
        msc=MscSnapshot("msc-3", 55.0, "NEUTRAL", False, 0.85),
    )


def _fixture_recession_risk() -> L5RegimeInputs:
    """Fixture 4 — US 2009-Q1 recession + distress."""
    return L5RegimeInputs(
        country_code="US",
        date=ANCHOR,
        ecs=EcsSnapshot("ecs-4", 25.0, "RECESSION", False, 0.85),
        cccs=CccsSnapshot("cccs-4", 20.0, "DISTRESS", False, 0.85),
        fcs=FcsSnapshot("fcs-4", 22.0, "STRESS", False, 0.85),
        msc=MscSnapshot("msc-4", 28.0, "ACCOMMODATIVE", False, 0.85),
    )


def _fixture_soft_landing() -> L5RegimeInputs:
    """Fixture 5 — US 2015 expansion + recovery + neutral MSC."""
    return L5RegimeInputs(
        country_code="US",
        date=ANCHOR,
        ecs=EcsSnapshot("ecs-5", 60.0, "EXPANSION", False, 0.85),
        cccs=CccsSnapshot("cccs-5", 58.0, "RECOVERY", False, 0.85),
        fcs=FcsSnapshot("fcs-5", 62.0, "OPTIMISM", False, 0.85),
        msc=MscSnapshot("msc-5", 50.0, "NEUTRAL", False, 0.85),
    )


def _fixture_unclassified() -> L5RegimeInputs:
    """Fixture 6 — transitional mixed-signals configuration."""
    # ECS peak but CCCS still in repair + FCS caution + MSC accommodative.
    # No single branch matches decisively.
    return L5RegimeInputs(
        country_code="US",
        date=ANCHOR,
        ecs=EcsSnapshot("ecs-6", 65.0, "PEAK_ZONE", False, 0.85),
        cccs=CccsSnapshot("cccs-6", 42.0, "REPAIR", False, 0.85),
        fcs=FcsSnapshot("fcs-6", 55.0, "CAUTION", False, 0.85),
        msc=MscSnapshot("msc-6", 45.0, "ACCOMMODATIVE", False, 0.85),
    )


def _fixture_ecs_missing() -> L5RegimeInputs:
    """Fixture 7 — 3/4 cycles (ECS slot None) → unclassified + L5_ECS_MISSING."""
    base = _fixture_soft_landing()
    return replace(base, ecs=None)


def _fixture_insufficient() -> L5RegimeInputs:
    """Fixture 8 — 2/4 cycles → InsufficientL4DataError."""
    base = _fixture_soft_landing()
    return replace(base, ecs=None, msc=None)


# ---------------------------------------------------------------------------
# Parametrised happy-path classifications
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("factory", "expected_regime", "expected_reason"),
    [
        (_fixture_overheating, MetaRegime.OVERHEATING, "peak+boom+optimism"),
        (_fixture_stagflation_risk, MetaRegime.STAGFLATION_RISK, "stagflation+dilemma"),
        (
            _fixture_late_cycle_bubble,
            MetaRegime.LATE_CYCLE_BUBBLE,
            "euphoria+bubble+speculation",
        ),
        (_fixture_recession_risk, MetaRegime.RECESSION_RISK, "recession+distress"),
        (_fixture_soft_landing, MetaRegime.SOFT_LANDING, "expansion+neutral"),
        (_fixture_unclassified, MetaRegime.UNCLASSIFIED, "default"),
    ],
)
def test_canonical_fixture_classifies_as_expected(
    factory: object,
    expected_regime: MetaRegime,
    expected_reason: str,
) -> None:
    inputs = factory()  # type: ignore[operator]
    result = MetaRegimeClassifier().classify(inputs)
    assert result.meta_regime == expected_regime, (
        f"expected {expected_regime}, got {result.meta_regime} "
        f"(reason={result.classification_reason})"
    )
    assert result.classification_reason == expected_reason


# ---------------------------------------------------------------------------
# Policy 1 + confidence semantics
# ---------------------------------------------------------------------------


def test_three_of_four_applies_confidence_cap() -> None:
    inputs = _fixture_ecs_missing()
    result = MetaRegimeClassifier().classify(inputs)
    # With ECS missing the decision tree now routes through the default
    # branch (no branch predicate references ECS→None as a positive match
    # except `soft_landing`, which needs ECS=EXPANSION → fails → default).
    assert result.meta_regime == MetaRegime.UNCLASSIFIED
    assert result.confidence <= CONFIDENCE_CAP_ONE_MISSING
    assert "L5_ECS_MISSING" in result.flags
    assert result.ecs_id is None


def test_fewer_than_three_raises() -> None:
    with pytest.raises(InsufficientL4DataError, match=str(MIN_L4_CYCLES)):
        MetaRegimeClassifier().classify(_fixture_insufficient())


def test_regime_flag_always_emitted() -> None:
    """Every successful classification carries exactly one L5_* regime flag."""
    factories = [
        _fixture_overheating,
        _fixture_stagflation_risk,
        _fixture_late_cycle_bubble,
        _fixture_recession_risk,
        _fixture_soft_landing,
        _fixture_unclassified,
    ]
    for factory in factories:
        result = MetaRegimeClassifier().classify(factory())
        regime_flags = [f for f in result.flags if f.startswith("L5_") and "MISSING" not in f]
        assert len(regime_flags) == 1, f"expected 1 regime flag, got {regime_flags}"


def test_methodology_version_stamped() -> None:
    result = MetaRegimeClassifier().classify(_fixture_soft_landing())
    assert result.methodology_version == "L5_META_REGIME_v0.1"


def test_fk_ids_propagate() -> None:
    result = MetaRegimeClassifier().classify(_fixture_soft_landing())
    assert result.ecs_id == "ecs-5"
    assert result.cccs_id == "cccs-5"
    assert result.fcs_id == "fcs-5"
    assert result.msc_id == "msc-5"


def test_priority_ordering_stagflation_beats_recession() -> None:
    """Stagflation predicate is higher priority than recession_risk — test
    by constructing inputs that would match both and asserting stagflation
    wins."""
    # ECS in early recession with stagflation active + CCCS distress + MSC
    # dilemma active. Both stagflation_risk and recession_risk predicates
    # evaluate True; stagflation_risk must win (priority 1 vs 2).
    inputs = L5RegimeInputs(
        country_code="US",
        date=ANCHOR,
        ecs=EcsSnapshot("ecs-x", 40.0, "EARLY_RECESSION", True, 0.80),
        cccs=CccsSnapshot("cccs-x", 30.0, "DISTRESS", False, 0.80),
        fcs=FcsSnapshot("fcs-x", 28.0, "STRESS", False, 0.80),
        msc=MscSnapshot("msc-x", 75.0, "TIGHT", True, 0.80),
    )
    result = MetaRegimeClassifier().classify(inputs)
    assert result.meta_regime == MetaRegime.STAGFLATION_RISK


def test_min_confidence_applied() -> None:
    """Base confidence = min across present cycles before Policy 1 cap."""
    low_conf = MscSnapshot("msc-low", 50.0, "NEUTRAL", False, 0.50)
    inputs = replace(_fixture_soft_landing(), msc=low_conf)
    result = MetaRegimeClassifier().classify(inputs)
    # All 4 cycles present → no Policy 1 cap. Confidence = min(0.85, 0.85, 0.85, 0.50).
    assert result.confidence == pytest.approx(0.50)
