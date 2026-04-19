# NSS Overlay Scaffolding — Execution Brief

**Target session**: Phase 1 Week 2, Day 1 PM
**Priority**: HIGH (Week 2 critical path)
**Time budget**: 60–90 min
**Authority**: Full autonomy per decision authority rule; HALT only on §7 triggers
**Commit count**: 2 (strict per regra #2)
**Base commit**: `c15a905` (main HEAD)
**Predecessor spec**: `docs/specs/overlays/nss-curves.md` @ `NSS_v0.1` (post-sweep)

---

## 1. Scope — what this brief covers

**In-scope**:
- Add `scipy` + `numpy` versioned dependencies to `pyproject.toml`
- Create `src/sonar/overlays/` package (new module tree)
- Create `src/sonar/overlays/nss.py` **skeleton**: module-level constants, type aliases, dataclasses for inputs/outputs, function signatures with docstrings, `NotImplementedError` bodies
- Create `src/sonar/overlays/exceptions.py`: `InsufficientDataError`, `ConvergenceError` (per spec §6)
- Create `src/sonar/overlays/__init__.py` with explicit exports
- Create `tests/unit/test_overlays/test_nss_contracts.py`: signature + import smoke tests (verify module loads, types match spec)
- Update `pyproject.toml` coverage config if needed for new package tree

**Out-of-scope** (deferred to Day 2 AM brief):
- NSS fit algorithm (`scipy.optimize.minimize` call)
- Spot/zero/forward/real curve derivation math
- Confidence computation (§6 matrix)
- Cross-validation logic
- Database persistence (`yield_curves_*` writes)
- Flag emission
- Integration tests live FRED → fit → persist

Scaffolding ships the **typed interface surface** that Day 2 AM fit logic fills in. Zero executable fit paths.

---

## 2. Canonical invariants — do not modify

- `docs/specs/overlays/nss-curves.md` (spec locked at NSS_v0.1 post-sweep; any deviation surfaced during scaffolding → HALT trigger §7.4)
- `src/sonar/db/models.py` (Observation schema just reverted in P2-023; no further changes)
- `src/sonar/connectors/` (stable Week 1 baseline)
- `.pre-commit-config.yaml`
- `alembic/` (migrations untouched this commit)

---

## 3. Dependency additions

Inspect `pyproject.toml` existing `[project.dependencies]` or `[tool.uv]` block. Add:

```toml
"scipy>=1.11",
"numpy>=1.26",
```

If `numpy` already pulled transitively (via pandas), still pin explicitly — overlays module takes direct dependency.

After edit:
```bash
uv lock
uv sync
```

Verify:
```bash
uv run python -c "import scipy; import numpy; print(scipy.__version__, numpy.__version__)"
```

Expect `scipy >= 1.11`, `numpy >= 1.26`.

---

## 4. Module structure to create

```
src/sonar/overlays/
├── __init__.py
├── exceptions.py
└── nss.py

tests/unit/test_overlays/
├── __init__.py
└── test_nss_contracts.py
```

### 4.1 `src/sonar/overlays/exceptions.py`

```python
"""Exception types for L2 overlay layer.

Per spec conventions/exceptions.md and individual overlay specs.
"""
from __future__ import annotations


class OverlayError(Exception):
    """Base exception for all L2 overlay failures."""


class InsufficientDataError(OverlayError):
    """Raised when observation count or quality falls below fit minimum.

    Per nss-curves.md §6: n_obs < 6, non-finite values, or out-of-range
    yields [-5%, 30%] trigger this exception.
    """


class ConvergenceError(OverlayError):
    """Raised when optimizer fails to converge on NSS parameters.

    Per nss-curves.md §6 row 3: downstream handler falls back to linear
    interpolation, flags NSS_FAIL, caps confidence at 0.50, and persists
    degraded row.
    """
```

### 4.2 `src/sonar/overlays/nss.py` — skeleton

Contracts derived verbatim from `nss-curves.md` §2 (inputs), §3 (outputs), §4 (algorithm signature). Fit body is `NotImplementedError`.

```python
"""Nelson-Siegel-Svensson yield curve overlay (L2).

Spec: docs/specs/overlays/nss-curves.md
Methodology version: NSS_v0.1
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal
from uuid import UUID

import numpy as np

from sonar.overlays.exceptions import ConvergenceError, InsufficientDataError

__all__ = [
    "METHODOLOGY_VERSION",
    "STANDARD_OUTPUT_TENORS",
    "STANDARD_FORWARD_KEYS",
    "NSSInput",
    "NSSParams",
    "SpotCurve",
    "ZeroCurve",
    "ForwardCurve",
    "RealCurve",
    "NSSFitResult",
    "fit_nss",
    "derive_zero_curve",
    "derive_forward_curve",
    "derive_real_curve",
]

# ---------------------------------------------------------------------------
# Constants (spec §3, §4)
# ---------------------------------------------------------------------------

METHODOLOGY_VERSION: str = "NSS_v0.1"

STANDARD_OUTPUT_TENORS: tuple[str, ...] = (
    "1M", "3M", "6M", "1Y", "2Y", "3Y",
    "5Y", "7Y", "10Y", "15Y", "20Y", "30Y",
)

STANDARD_FORWARD_KEYS: tuple[str, ...] = (
    "1y1y", "2y1y", "1y2y", "1y5y", "5y5y", "10y10y",
)

# NSS fit bounds per spec §4 (β0 lower=0 for Week 2 US; CAL-030 pre-Week 3 DE/JP).
FIT_BOUNDS: tuple[tuple[float, float], ...] = (
    (0.0, 0.20),    # β0
    (-0.15, 0.15),  # β1
    (-0.15, 0.15),  # β2
    (-0.15, 0.15),  # β3
    (0.1, 10.0),    # λ1
    (0.1, 30.0),    # λ2
)

MIN_OBSERVATIONS: int = 6
MIN_OBSERVATIONS_FOR_SVENSSON: int = 9  # below this, use 4-param NS (spec §6)
YIELD_RANGE_PCT: tuple[float, float] = (-5.0, 30.0)

CurveInputType = Literal["par", "zero", "linker_real"]
RealCurveMethod = Literal["direct_linker", "derived"]
ZeroCurveDerivation = Literal["nss_derived", "bootstrap"]


# ---------------------------------------------------------------------------
# Input / Output dataclasses (spec §2, §3)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class NSSInput:
    """Per spec §2.

    tenors_years: maturity in years, ∈ grid of spec §2 constraint.
    yields_pct: corresponding yields in percent (e.g. 4.32 for 4.32%).
    """

    tenors_years: np.ndarray
    yields_pct: np.ndarray
    country_code: str  # ISO 3166-1 alpha-2 (post P2-023)
    observation_date: date
    curve_input_type: CurveInputType


@dataclass(frozen=True, slots=True)
class NSSParams:
    """Fitted NSS parameters per spec §4."""

    beta_0: float
    beta_1: float
    beta_2: float
    beta_3: float | None  # None if 4-param reduced fit
    lambda_1: float
    lambda_2: float | None  # None if 4-param reduced fit


@dataclass(frozen=True, slots=True)
class SpotCurve:
    """Per spec §3 / §8 yield_curves_spot."""

    params: NSSParams
    fitted_yields_pct: dict[str, float]  # {"3M": 2.68, ...}
    rmse_bps: float
    confidence: float
    flags: tuple[str, ...]
    observations_used: int


@dataclass(frozen=True, slots=True)
class ZeroCurve:
    """Per spec §3 / §8 yield_curves_zero."""

    zero_rates_pct: dict[str, float]
    derivation: ZeroCurveDerivation


@dataclass(frozen=True, slots=True)
class ForwardCurve:
    """Per spec §3 / §8 yield_curves_forwards."""

    forwards_pct: dict[str, float]  # keys in STANDARD_FORWARD_KEYS
    breakeven_forwards_pct: dict[str, float] | None


@dataclass(frozen=True, slots=True)
class RealCurve:
    """Per spec §3 / §8 yield_curves_real."""

    real_yields_pct: dict[str, float]
    method: RealCurveMethod
    linker_connector: str | None


@dataclass(frozen=True, slots=True)
class NSSFitResult:
    """Composite output for one country-date; shares fit_id across siblings."""

    fit_id: UUID
    country_code: str
    observation_date: date
    methodology_version: str
    spot: SpotCurve
    zero: ZeroCurve
    forward: ForwardCurve
    real: RealCurve | None  # None if country lacks linker and E[π] unavailable


# ---------------------------------------------------------------------------
# Public functions — signatures only (Day 2 AM fills bodies)
# ---------------------------------------------------------------------------

def fit_nss(inputs: NSSInput) -> SpotCurve:
    """Fit Nelson-Siegel-Svensson 6-param to observed yields.

    Reduces to 4-param Nelson-Siegel when 6 <= n_obs < 9 (spec §6 row 2).

    Args:
        inputs: NSSInput with tenors, yields, country, date.

    Returns:
        SpotCurve with fitted params, rmse_bps, confidence, flags.

    Raises:
        InsufficientDataError: n_obs < 6, non-finite values, or yields
            outside [-5%, 30%] (spec §6 row 1).
        ConvergenceError: optimizer fails to converge (spec §6 row 3);
            downstream handler applies linear interp fallback.
    """
    raise NotImplementedError("Day 2 AM implementation")


def derive_zero_curve(spot: SpotCurve) -> ZeroCurve:
    """Derive zero rates from fitted NSS spot curve.

    Per spec §4 step 4: evaluate NSS at STANDARD_OUTPUT_TENORS treated as
    continuously compounded → zero rates.
    """
    raise NotImplementedError("Day 2 AM implementation")


def derive_forward_curve(zero: ZeroCurve) -> ForwardCurve:
    """Derive forward rates from zero curve.

    Per spec §4 step 5: f(t1, t2) = [((1+z2)^t2) / ((1+z1)^t1)]^(1/(t2-t1)) - 1
    Keys: STANDARD_FORWARD_KEYS.
    """
    raise NotImplementedError("Day 2 AM implementation")


def derive_real_curve(
    nominal_spot: SpotCurve,
    linker_yields_pct: dict[str, float] | None = None,
    expected_inflation_pct: dict[str, float] | None = None,
) -> RealCurve | None:
    """Derive real yield curve.

    Per spec §4 step 6:
    - If country in {US,UK,DE,IT,FR,CA,AU} → fit NSS to linker yields.
    - Else → real(τ) = nominal(τ) − E[π(τ)] from overlays/expected-inflation.
    - Returns None if neither path available.
    """
    raise NotImplementedError("Day 2 AM implementation")
```

### 4.3 `src/sonar/overlays/__init__.py`

```python
"""L2 overlay layer — mathematical primitives computed from L0/L1 data."""
from sonar.overlays.exceptions import (
    ConvergenceError,
    InsufficientDataError,
    OverlayError,
)

__all__ = ["OverlayError", "InsufficientDataError", "ConvergenceError"]
```

### 4.4 `tests/unit/test_overlays/__init__.py`

Empty file (package marker).

### 4.5 `tests/unit/test_overlays/test_nss_contracts.py`

Smoke + contract tests. Zero fit logic tested (Day 2 AM adds behavioral tests).

```python
"""Contract tests for NSS overlay module.

Verifies module structure, type contracts, and constant values match
spec nss-curves.md. Does NOT test fit behavior (Day 2 AM implementation).
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from sonar.overlays import ConvergenceError, InsufficientDataError, OverlayError
from sonar.overlays import nss


class TestConstants:
    def test_methodology_version(self) -> None:
        assert nss.METHODOLOGY_VERSION == "NSS_v0.1"

    def test_standard_output_tenors_count(self) -> None:
        # Spec §3: 12 standard output tenors.
        assert len(nss.STANDARD_OUTPUT_TENORS) == 12

    def test_standard_output_tenors_content(self) -> None:
        expected = ("1M", "3M", "6M", "1Y", "2Y", "3Y",
                    "5Y", "7Y", "10Y", "15Y", "20Y", "30Y")
        assert nss.STANDARD_OUTPUT_TENORS == expected

    def test_standard_forward_keys_includes_2y1y(self) -> None:
        # Spec §3 post-sweep (957e765): 2y1y required for M3 consumer.
        assert "2y1y" in nss.STANDARD_FORWARD_KEYS

    def test_standard_forward_keys_complete(self) -> None:
        expected = ("1y1y", "2y1y", "1y2y", "1y5y", "5y5y", "10y10y")
        assert nss.STANDARD_FORWARD_KEYS == expected

    def test_fit_bounds_shape(self) -> None:
        assert len(nss.FIT_BOUNDS) == 6  # 6 NSS parameters

    def test_fit_bounds_beta_0_week2(self) -> None:
        # Spec §4: (0, 0.20) for Week 2. CAL-030 addresses negative yields pre-Week 3.
        assert nss.FIT_BOUNDS[0] == (0.0, 0.20)

    def test_min_observations(self) -> None:
        assert nss.MIN_OBSERVATIONS == 6

    def test_yield_range(self) -> None:
        assert nss.YIELD_RANGE_PCT == (-5.0, 30.0)


class TestExceptionHierarchy:
    def test_insufficient_data_is_overlay_error(self) -> None:
        assert issubclass(InsufficientDataError, OverlayError)

    def test_convergence_is_overlay_error(self) -> None:
        assert issubclass(ConvergenceError, OverlayError)


class TestDataclassContracts:
    def test_nss_input_frozen(self) -> None:
        inp = nss.NSSInput(
            tenors_years=np.array([0.25, 1.0, 10.0]),
            yields_pct=np.array([4.0, 4.5, 4.3]),
            country_code="US",  # alpha-2 post P2-023
            observation_date=date(2026, 4, 17),
            curve_input_type="par",
        )
        with pytest.raises(AttributeError):
            inp.country_code = "DE"  # type: ignore[misc]

    def test_nss_params_allows_none_for_4param(self) -> None:
        # 4-param Nelson-Siegel reduced fit: beta_3 and lambda_2 are None.
        p = nss.NSSParams(
            beta_0=0.04, beta_1=-0.01, beta_2=0.005,
            beta_3=None, lambda_1=1.5, lambda_2=None,
        )
        assert p.beta_3 is None
        assert p.lambda_2 is None


class TestFunctionSignatures:
    def test_fit_nss_not_implemented(self) -> None:
        inp = nss.NSSInput(
            tenors_years=np.array([0.25, 1.0, 2.0, 5.0, 10.0, 30.0]),
            yields_pct=np.array([4.0, 4.2, 4.3, 4.4, 4.5, 4.6]),
            country_code="US",
            observation_date=date(2026, 4, 17),
            curve_input_type="par",
        )
        with pytest.raises(NotImplementedError):
            nss.fit_nss(inp)

    def test_derive_zero_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError):
            nss.derive_zero_curve(None)  # type: ignore[arg-type]

    def test_derive_forward_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError):
            nss.derive_forward_curve(None)  # type: ignore[arg-type]

    def test_derive_real_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError):
            nss.derive_real_curve(None)  # type: ignore[arg-type]
```

---

## 5. Execution sequence

1. Read current `pyproject.toml`; add `scipy>=1.11`, `numpy>=1.26` to dependencies
2. `uv lock && uv sync`
3. Verify: `uv run python -c "import scipy; import numpy; print(scipy.__version__)"`
4. Create `src/sonar/overlays/` tree (exceptions.py, nss.py, __init__.py)
5. Create `tests/unit/test_overlays/` tree (__init__.py, test_nss_contracts.py)
6. `uv run pytest tests/unit/test_overlays/ -x -v` — all pass (13 tests expected)
7. `uv run pytest tests/ -x` — full suite green (regression check)
8. `uv run mypy src/sonar/overlays/` — clean
9. Coverage check: `uv run pytest --cov=src/sonar --cov-report=term-missing tests/`
   - Expected: slight dip (NSS bodies are `NotImplementedError` = technically covered via `pytest.raises`, but dataclass definitions add coverable lines). Target: ≥ 94%.
10. `pre-commit run --all-files` — all hooks pass
11. `git add -p` review; two commits per §6
12. Push after each commit

---

## 6. Commit structure

### Commit 1/2 — dependencies + exceptions

```
feat(overlays): add L2 overlay package + scipy/numpy deps

Introduce src/sonar/overlays/ module tree for L2 mathematical overlays
per spec ARCHITECTURE.md §L2. First overlay (NSS) scaffolds in commit 2/2.

- pyproject.toml: scipy>=1.11, numpy>=1.26 added
- src/sonar/overlays/__init__.py: package marker + exception exports
- src/sonar/overlays/exceptions.py: OverlayError base + InsufficientDataError
  + ConvergenceError (per nss-curves.md §6)
- uv.lock: regenerated

No behavioral code yet. Scaffolding only.
```

### Commit 2/2 — NSS skeleton + contract tests

```
feat(overlays): NSS skeleton + contract tests (nss-curves.md v0.1)

Scaffold src/sonar/overlays/nss.py with typed interface surface per
docs/specs/overlays/nss-curves.md @ NSS_v0.1. Fit logic deferred to
Day 2 AM; function bodies raise NotImplementedError.

Module exports:
- Constants: METHODOLOGY_VERSION, STANDARD_OUTPUT_TENORS (12),
  STANDARD_FORWARD_KEYS (6 incl. 2y1y), FIT_BOUNDS, MIN_OBSERVATIONS
- Dataclasses: NSSInput, NSSParams, SpotCurve, ZeroCurve, ForwardCurve,
  RealCurve, NSSFitResult (all frozen + slotted)
- Functions: fit_nss, derive_zero_curve, derive_forward_curve,
  derive_real_curve (signatures only)

Tests: 13 contract tests in tests/unit/test_overlays/test_nss_contracts.py
verifying constants, exception hierarchy, dataclass immutability,
NotImplementedError surfacing.

Refs: spec 957e765 (post-sweep).
```

---

## 7. HALT triggers

Pause and report without pushing if **any** fires:

1. `uv sync` fails due to dependency conflict (scipy/numpy vs existing pandas/sqlalchemy pins)
2. mypy surfaces errors in modules not touched (indicates latent type issue surfaced by new scipy/numpy imports)
3. Existing test suite regression (any Week 1 test fails after deps upgrade)
4. Spec contradiction surfaces during scaffolding (e.g. `NSSFitResult` composition cannot be expressed with spec's §8 schema shape) → scope decision, requires chat
5. Coverage drop > 3pp from 96.59%
6. Any hook fail not resolvable by auto-fix (regra #4: no force-fix)

---

## 8. Acceptance checklist

- [ ] `pyproject.toml` has `scipy>=1.11` and `numpy>=1.26`
- [ ] `uv lock` regenerated; committed
- [ ] `src/sonar/overlays/{__init__,exceptions,nss}.py` created
- [ ] `tests/unit/test_overlays/{__init__,test_nss_contracts}.py` created
- [ ] `uv run pytest tests/unit/test_overlays/ -v` → 13/13 pass
- [ ] `uv run pytest tests/ -x` → full suite green
- [ ] `uv run mypy src/sonar/overlays/` → clean
- [ ] Coverage ≥ 94%
- [ ] `pre-commit run --all-files` → clean
- [ ] 2 commits pushed per §6; local HEAD matches remote

---

## 9. Report-back (paste to chat after push)

1. Both commit SHAs + `git log --oneline -2` output
2. `uv pip list | grep -E 'scipy|numpy'` output (confirm versions)
3. Test counts: `pytest tests/unit/test_overlays/ --collect-only -q | tail -3`
4. Coverage delta: before 96.59% / after XX.XX%
5. Timer actual vs 60–90 min budget
6. Any §7 HALT trigger resolved mid-flight (narrate)
7. Any out-of-scope surface for chat triage

---

*End of brief. Proceed.*
