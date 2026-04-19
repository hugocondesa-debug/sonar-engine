# NSS Fit Algorithm — Execution Brief

**Target session**: Phase 1 Week 2, Day 2 AM
**Priority**: HIGH (Week 2 critical path — core math)
**Time budget**: 90–120 min
**Authority**: Full autonomy per decision authority rule; HALT only on §8 triggers
**Commit count**: 2 (math core + behavioral tests)
**Base commit**: `d429ec1` (main HEAD Day 1 close)
**Predecessor artefacts**: `src/sonar/overlays/nss.py` skeleton (`8082319`); spec `docs/specs/overlays/nss-curves.md` @ `NSS_v0.1` (post-sweep `957e765`)

---

## 1. Scope

**In-scope**:
- Declare `scipy>=1.17` and `numpy>=2.4` explicit floors in `pyproject.toml` (deferred item from Day 1 PM)
- Implement `fit_nss()` — scipy L-BFGS-B fit per spec §4, with 4-param NS reduced fallback for `6 ≤ n_obs < 9` per spec §6
- Implement `derive_zero_curve()` — spec §4 step 4
- Implement `derive_forward_curve()` — spec §4 step 5, six keys per `STANDARD_FORWARD_KEYS`
- Implement `derive_real_curve()` — spec §4 step 6, direct-linker path (derived path is stub returning None if `expected_inflation_pct is None`)
- Implement confidence + flag emission per spec §6 (subject to `conventions/flags.md` authoritative propagation rules)
- Exception flows: `InsufficientDataError`, `ConvergenceError`
- Create test fixtures: `tests/fixtures/nss-curves/{us_2024_01_02,us_sparse_5,synthetic_multi_hump}.json`
- Replace contract tests with behavioral test suite (`test_nss_behavior.py`); keep constant/dataclass contract tests (move to `test_nss_contracts.py` trimmed)

**Out-of-scope** (defer):
- Cross-validation vs BC-published curves — live xval logic Day 3 AM
- Persistence to `yield_curves_*` tables — Day 3 AM
- FRED TIPS connector for real curve (DFII5/10/20/30) — Day 3 AM
- Expected-inflation overlay integration (`derive_real_curve` derived path) — Phase 1 later
- `treasury_gov` connector (P2-026 LOW)
- β0 bounds relaxation for negative yields (CAL-030 LOW, pre-Week 3 DE/JP)
- Tier-aware confidence caps (T2/T3/T4) — Week 3+

---

## 2. Canonical invariants — do not modify

- `docs/specs/overlays/nss-curves.md` (locked at NSS_v0.1 post-sweep)
- `src/sonar/db/models.py` (Observation schema stable post P2-023)
- `src/sonar/connectors/` (stable Week 1)
- `src/sonar/overlays/exceptions.py` (complete; add no new exceptions unless spec §6 demands)
- Dataclass shapes in `src/sonar/overlays/nss.py` (contract locked Day 1 PM via scaffolding)

Dataclass bodies may add computed properties (e.g. `@property breakeven_5y5y` on `ForwardCurve`) only if spec §3/§9 reference them. No field additions.

---

## 3. Pyproject floors declaration (deferred from Day 1 PM)

Inspect `pyproject.toml`. If `scipy` and `numpy` are not in `[project.dependencies]`, add:

```toml
"scipy>=1.17",
"numpy>=2.4",
```

(Floors match Day 1 PM installed versions: scipy 1.17.1, numpy 2.4.4. This makes the transitive dependency explicit per overlays' direct usage.)

```bash
uv lock
uv sync
uv run python -c "import scipy, numpy; print(scipy.__version__, numpy.__version__)"
```

Expect no version change (floors ≤ installed).

---

## 4. Unit convention

**Critical implementation decision**: spec §4 has latent ambiguity between `yields_pct` (percent, e.g. 4.32) and bounds (decimal, e.g. 0.20 for β0). The fit must be internally consistent.

**Prescribed convention**:
- `NSSInput.yields_pct` is **percent** (4.32 for 4.32%), per spec §2
- `NSSInput.tenors_years` is **years** as float (0.25 for 3M, 10.0 for 10Y), per spec §2
- **Fit operates internally on decimal** — convert yields to decimal (`yields / 100.0`) before optimizer; convert back on output
- `SpotCurve.fitted_yields_pct` stores **percent** (consumers expect percent per spec §3 display examples: `"3M": 2.68`, `"5Y": 2.68%` fitted)
- `NSSParams` β/λ stored in **decimal** throughout (internal math quantities)
- `rmse_bps` computed on decimal residuals: `sqrt(mean((ŷ_decimal − y_decimal)²)) × 10000`

All public dataclass instances expose percent for yields (consumer-friendly); parameters (β0..β3, λ1, λ2) stored raw decimal (dimensional correctness).

Before committing: read `docs/specs/conventions/units.md` if it exists; if it prescribes different convention, that is authoritative — flag mid-flight and ask chat.

---

## 5. Math implementation

### 5.1 NSS evaluation function (private helper)

Numerical-safe evaluation handling τ/λ → 0 limit (series expansion gives 1.0):

```python
def _nss_eval(
    tenors_years: np.ndarray,
    beta_0: float,
    beta_1: float,
    beta_2: float,
    beta_3: float | None,
    lambda_1: float,
    lambda_2: float | None,
) -> np.ndarray:
    """Evaluate NSS at given tenors. Returns yields in decimal.

    When beta_3 is None and lambda_2 is None, collapses to 4-param
    Nelson-Siegel (reduced fit for sparse obs, spec §6 row 2).
    """
    tau = np.asarray(tenors_years, dtype=np.float64)
    x1 = tau / lambda_1

    # Stable (1 - exp(-x)) / x via expm1: handles x → 0 cleanly.
    # expm1(-x) = exp(-x) - 1, so -(expm1(-x))/x = (1 - exp(-x))/x.
    # At x == 0, replace with 1.0 (limit).
    with np.errstate(divide="ignore", invalid="ignore"):
        term1_load = np.where(x1 == 0, 1.0, -np.expm1(-x1) / x1)
    term2_load = term1_load - np.exp(-x1)

    y = beta_0 + beta_1 * term1_load + beta_2 * term2_load

    if beta_3 is not None and lambda_2 is not None:
        x2 = tau / lambda_2
        with np.errstate(divide="ignore", invalid="ignore"):
            term3_load_a = np.where(x2 == 0, 1.0, -np.expm1(-x2) / x2)
        term3_load = term3_load_a - np.exp(-x2)
        y = y + beta_3 * term3_load

    return y
```

### 5.2 Fit function

```python
def fit_nss(inputs: NSSInput) -> SpotCurve:
    # Validate inputs per spec §6 row 1.
    _validate_inputs(inputs)

    # Decide fit mode per spec §6 row 2.
    n_obs = len(inputs.tenors_years)
    reduced = n_obs < MIN_OBSERVATIONS_FOR_SVENSSON  # 6 ≤ n_obs < 9

    yields_dec = inputs.yields_pct / 100.0
    tenors = np.asarray(inputs.tenors_years, dtype=np.float64)

    flags: list[str] = []

    try:
        if reduced:
            params, rmse_dec = _fit_ns_4param(tenors, yields_dec)
            flags.append("NSS_REDUCED")
        else:
            params, rmse_dec = _fit_nss_6param(tenors, yields_dec)
    except ConvergenceError:
        # Per spec §6 row 3: caller (pipeline) applies linear interp
        # fallback. Fit itself raises; flags + confidence cap applied
        # at persistence layer.
        raise

    rmse_bps = rmse_dec * 10000.0

    # Emit HIGH_RMSE flag per spec §6 row 4 (Tier 1 threshold 15 bps).
    # Tier lookup deferred to Day 3 (country_tiers.yaml read);
    # Week 2 US hardcoded T1.
    if inputs.country_code == "US" and rmse_bps > 15.0:
        flags.append("HIGH_RMSE")

    fitted_decimal = _nss_eval(tenors, *_params_as_args(params))
    fitted_pct = {
        _tenor_years_to_label(t): float(y * 100.0)
        for t, y in zip(tenors, fitted_decimal, strict=True)
    }

    confidence = _compute_confidence(flags, tier="T1")

    return SpotCurve(
        params=params,
        fitted_yields_pct=fitted_pct,
        rmse_bps=float(rmse_bps),
        confidence=float(confidence),
        flags=tuple(flags),
        observations_used=n_obs,
    )
```

Helpers `_validate_inputs`, `_fit_nss_6param`, `_fit_ns_4param`, `_params_as_args`, `_tenor_years_to_label`, `_compute_confidence` — module-private.

### 5.3 Optimizer configuration

Per spec §4, L-BFGS-B:

```python
def _fit_nss_6param(
    tenors: np.ndarray, yields_dec: np.ndarray
) -> tuple[NSSParams, float]:
    x0 = np.array([
        yields_dec[-1],                     # β0 ≈ long-end yield
        yields_dec[0] - yields_dec[-1],     # β1 ≈ short-long slope
        0.0,                                # β2 curvature seed
        0.0,                                # β3 second-hump seed
        1.5,                                # λ1 seed
        5.0,                                # λ2 seed
    ])
    bounds = FIT_BOUNDS  # already in module constants

    def loss(x: np.ndarray) -> float:
        b0, b1, b2, b3, l1, l2 = x
        fitted = _nss_eval(tenors, b0, b1, b2, b3, l1, l2)
        residuals = fitted - yields_dec
        return float(np.sum(residuals ** 2))

    result = scipy.optimize.minimize(
        loss,
        x0,
        method="L-BFGS-B",
        bounds=bounds,
        options={"maxiter": 500, "ftol": 1e-10, "gtol": 1e-8},
    )

    if not result.success:
        raise ConvergenceError(
            f"NSS 6-param fit did not converge: {result.message}"
        )

    b0, b1, b2, b3, l1, l2 = result.x
    params = NSSParams(
        beta_0=float(b0), beta_1=float(b1), beta_2=float(b2),
        beta_3=float(b3), lambda_1=float(l1), lambda_2=float(l2),
    )
    rmse_dec = float(np.sqrt(result.fun / len(tenors)))
    return params, rmse_dec
```

`_fit_ns_4param` is analogous with `x0 = x0[:4]` equivalent (adapted: `[yields[-1], yields[0]-yields[-1], 0.0, 1.5]`) and `bounds = FIT_BOUNDS[0:3] + (FIT_BOUNDS[4],)` — drops β3 and λ2 slots. Returns `NSSParams(..., beta_3=None, lambda_2=None)`.

### 5.4 Input validation

```python
def _validate_inputs(inputs: NSSInput) -> None:
    n = len(inputs.tenors_years)
    if n < MIN_OBSERVATIONS:  # 6
        raise InsufficientDataError(
            f"NSS requires ≥{MIN_OBSERVATIONS} observations, got {n}"
        )
    if len(inputs.yields_pct) != n:
        raise InsufficientDataError(
            f"tenors ({n}) and yields ({len(inputs.yields_pct)}) length mismatch"
        )
    if not np.all(np.isfinite(inputs.tenors_years)):
        raise InsufficientDataError("Non-finite tenor values")
    if not np.all(np.isfinite(inputs.yields_pct)):
        raise InsufficientDataError("Non-finite yield values (NaN or inf)")
    lo, hi = YIELD_RANGE_PCT  # (-5.0, 30.0)
    if np.any(inputs.yields_pct < lo) or np.any(inputs.yields_pct > hi):
        raise InsufficientDataError(
            f"Yields outside [{lo}, {hi}]% range"
        )
    if not np.all(np.diff(inputs.tenors_years) > 0):
        raise InsufficientDataError("Tenors must be strictly ascending")
```

### 5.5 Confidence computation

Before writing `_compute_confidence`, **read `docs/specs/conventions/flags.md`** to find the authoritative propagation convention. Spec §6 references "Convenção de propagação" there. Implementation must align.

Default algorithm if flags.md prescribes generic deduction-then-cap semantics:

```python
def _compute_confidence(flags: list[str], tier: str = "T1") -> float:
    base = 1.0
    deduction = 0.0
    cap = 1.0

    # Cap rules (take min across applicable caps)
    if "NSS_REDUCED" in flags:
        cap = min(cap, 0.75)
    if "NSS_FAIL" in flags:
        cap = min(cap, 0.50)
    if "EM_REGIME_BREAK" in flags:
        cap = min(cap, 0.60)
    if tier == "T4":
        cap = min(cap, 0.70)

    # Deduction rules (additive)
    if "HIGH_RMSE" in flags:
        deduction += 0.20
    if "XVAL_DRIFT" in flags:
        deduction += 0.10
    if "NEG_FORWARD" in flags:
        deduction += 0.15
    if "EXTRAPOLATED" in flags:
        deduction += 0.10
    if "STALE" in flags:
        deduction += 0.20
    if "COMPLEX_SHAPE" in flags:
        deduction += 0.10

    return float(max(0.0, min(cap, base - deduction)))
```

If `flags.md` prescribes different order/semantics, implement per spec and note deviation in commit message.

---

## 6. Derivation functions

### 6.1 Zero curve

Per spec §4 step 4. For Phase 1, simplification: treat NSS-fitted par yields as proxy for continuously compounded zero rates directly. Full bootstrap is Phase 2.

```python
def derive_zero_curve(spot: SpotCurve) -> ZeroCurve:
    # NSS params evaluated at STANDARD_OUTPUT_TENORS.
    tenor_years = np.array([_label_to_years(t) for t in STANDARD_OUTPUT_TENORS])
    zeros_decimal = _nss_eval(tenor_years, *_params_as_args(spot.params))
    zero_rates_pct = {
        label: float(z * 100.0)
        for label, z in zip(STANDARD_OUTPUT_TENORS, zeros_decimal, strict=True)
    }
    return ZeroCurve(zero_rates_pct=zero_rates_pct, derivation="nss_derived")
```

### 6.2 Forward curve

Per spec §4 step 5. Key parser reads `"AyBy"` as `(start=A, tenor=B) → (t1=A, t2=A+B)`:

```python
_FORWARD_KEY_PATTERN = re.compile(r"^(\d+)y(\d+)y$")

def _parse_forward_key(key: str) -> tuple[int, int]:
    m = _FORWARD_KEY_PATTERN.match(key)
    if m is None:
        raise ValueError(f"Invalid forward key: {key}")
    start, tenor = int(m.group(1)), int(m.group(2))
    return start, start + tenor  # (t1, t2)

def derive_forward_curve(zero: ZeroCurve) -> ForwardCurve:
    zero_years = {_label_to_years(k): v / 100.0
                  for k, v in zero.zero_rates_pct.items()}
    # Interpolate linearly on zero curve grid for arbitrary t1, t2.
    years_sorted = sorted(zero_years)
    rates_sorted = [zero_years[y] for y in years_sorted]

    def _z(t: float) -> float:
        return float(np.interp(t, years_sorted, rates_sorted))

    forwards_pct: dict[str, float] = {}
    for key in STANDARD_FORWARD_KEYS:
        t1, t2 = _parse_forward_key(key)
        z1, z2 = _z(float(t1)), _z(float(t2))
        # f = [((1+z2)^t2) / ((1+z1)^t1)]^(1/(t2-t1)) - 1
        f = ((1 + z2) ** t2 / (1 + z1) ** t1) ** (1 / (t2 - t1)) - 1
        forwards_pct[key] = float(f * 100.0)

    return ForwardCurve(forwards_pct=forwards_pct, breakeven_forwards_pct=None)
```

Breakeven forwards require real curve — set `None` here; populate downstream when real + nominal forward pair assembled (Day 3).

### 6.3 Real curve — direct linker path only

Per spec §4 step 6. Week 2 implements direct-linker path. Derived path (nominal − E[π]) stubbed as `None`.

```python
def derive_real_curve(
    nominal_spot: SpotCurve,  # noqa: ARG001 — unused in direct path, kept for contract
    linker_yields_pct: dict[str, float] | None = None,
    expected_inflation_pct: dict[str, float] | None = None,  # noqa: ARG001
) -> RealCurve | None:
    if linker_yields_pct is None:
        # Derived path Phase 1 later; returning None is spec-compliant.
        return None

    # Direct-linker path: fit NSS to linker yields.
    tenor_labels = list(linker_yields_pct.keys())
    tenors = np.array([_label_to_years(t) for t in tenor_labels])
    yields = np.array([linker_yields_pct[t] for t in tenor_labels])

    # Sort by tenor (fit requires ascending).
    order = np.argsort(tenors)
    tenors, yields = tenors[order], yields[order]

    linker_input = NSSInput(
        tenors_years=tenors,
        yields_pct=yields,
        country_code="US",  # direct linker path restricted to {US,UK,DE,IT,FR,CA,AU}
        observation_date=...,  # caller passes through
        curve_input_type="linker_real",
    )
    # Re-fit on linker data.
    linker_fit = fit_nss(linker_input)

    # Evaluate at standard tenors.
    std_years = np.array([_label_to_years(t) for t in STANDARD_OUTPUT_TENORS])
    real_decimal = _nss_eval(std_years, *_params_as_args(linker_fit.params))
    real_pct = {
        label: float(r * 100.0)
        for label, r in zip(STANDARD_OUTPUT_TENORS, real_decimal, strict=True)
    }
    return RealCurve(
        real_yields_pct=real_pct,
        method="direct_linker",
        linker_connector="fred",  # TIPS via FRED DFII* (hardcoded Week 2; refactor Day 3)
    )
```

**Known ugliness** — `derive_real_curve` currently requires `observation_date` via caller; dataclass signature doesn't accept it. Accept this as Week 2 hack; Day 3 refactor when persistence layer wires full NSSFitResult assembly. Note as inline comment.

---

## 7. Helpers — tenor label ↔ years

Standard label encoding used across codebase:

```python
_TENOR_LABEL_TO_YEARS: dict[str, float] = {
    "1M": 1 / 12, "3M": 0.25, "6M": 0.5,
    "1Y": 1.0, "2Y": 2.0, "3Y": 3.0,
    "5Y": 5.0, "7Y": 7.0, "10Y": 10.0,
    "15Y": 15.0, "20Y": 20.0, "30Y": 30.0,
}
_TENOR_YEARS_TO_LABEL: dict[float, str] = {v: k for k, v in _TENOR_LABEL_TO_YEARS.items()}

def _label_to_years(label: str) -> float:
    return _TENOR_LABEL_TO_YEARS[label]

def _tenor_years_to_label(years: float) -> str:
    # Round to handle float jitter (0.0833 vs 1/12).
    key = min(_TENOR_YEARS_TO_LABEL, key=lambda v: abs(v - years))
    if abs(key - years) > 0.01:
        raise ValueError(f"Non-standard tenor {years}y cannot be labeled")
    return _TENOR_YEARS_TO_LABEL[key]
```

---

## 8. HALT triggers

Pause + report without pushing if any fires:

1. `docs/specs/conventions/flags.md` propagation rules materially differ from §5.5 default algorithm (e.g. multiplicative instead of cap-then-deduct) → scope call
2. `docs/specs/conventions/units.md` prescribes different yields/decimal convention than §4 → scope call
3. Week 1 test suite regression after scipy/numpy floor declaration
4. `us_2024_01_02` fixture fit fails to converge OR produces rmse_bps > 5 (spec §7 tolerance)
5. Unresolvable ruff/mypy error from scipy type stubs (expected: scipy-stubs or `# type: ignore[import-untyped]` needed — preferred: `[[tool.mypy.overrides]]` for `scipy.*` module in pyproject.toml)
6. Coverage drops > 3pp on `src/sonar/overlays` scope (should **rise** toward 95%+ on this scope as NotImplementedError gets replaced with tested code paths)

---

## 9. Execution sequence

1. Pyproject floors declaration (§3); `uv lock && uv sync`
2. Read `docs/specs/conventions/flags.md` and `units.md` (if exists); note any deviation from §4/§5.5 defaults
3. Implement `_nss_eval`, `_validate_inputs`, `_fit_nss_6param`, `_fit_ns_4param`, `fit_nss`, `_compute_confidence` in `src/sonar/overlays/nss.py`
4. Implement `derive_zero_curve`, `derive_forward_curve`, `derive_real_curve` (direct linker + None for derived)
5. Run pre-existing contract tests — some will now fail (`NotImplementedError` no longer raised). Expected; fix in test commit.
6. Create fixtures directory + JSON files (§10)
7. Write behavioral test suite (§11)
8. Trim `test_nss_contracts.py` — remove `TestFunctionSignatures` class (superseded by behavioral tests)
9. Run full suite: `uv run pytest tests/ -x`
10. Coverage: `uv run pytest --cov=src/sonar/overlays --cov-report=term-missing tests/unit/test_overlays/` — target ≥ 90% per `phase1-coverage-policy.md` per-module hard gate
11. `uv run mypy src/sonar/overlays/` — clean
12. `pre-commit run --all-files`
13. Two commits per §12; push after each

---

## 10. Test fixtures

Create `tests/fixtures/nss-curves/` with three JSON files.

### 10.1 `us_2024_01_02.json` — canonical US fit

Per spec §7 row 1. Data from FRED H.15 historical (DGS1MO/3MO/6MO/1/2/3/5/7/10/20/30 on 2024-01-02):

```json
{
  "meta": {
    "fixture_id": "us_2024_01_02",
    "source": "FRED H.15 DGS* 2024-01-02",
    "curve_input_type": "par"
  },
  "input": {
    "tenors_years": [0.08333, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 20.0, 30.0],
    "yields_pct": [5.52, 5.40, 5.26, 4.80, 4.33, 4.05, 3.93, 3.97, 3.95, 4.22, 4.08],
    "country_code": "US",
    "observation_date": "2024-01-02"
  },
  "expected": {
    "beta_0_approx": 0.0415,
    "rmse_bps_max": 5.0,
    "fitted_10Y_pct_approx": 3.95,
    "confidence_min": 0.80
  },
  "tolerance": {
    "beta_relative_pct": 10,
    "rmse_bps": 2.0,
    "fitted_pct_bps": 5.0
  }
}
```

**Values shown are indicative** — Claude Code should fetch actual FRED DGS series at 2024-01-02 and populate `yields_pct` with true H.15 closing values. If unavailable via connector at implementation time, use values above (they are within realistic range for that date).

### 10.2 `us_sparse_5.json` — InsufficientDataError

```json
{
  "meta": {
    "fixture_id": "us_sparse_5",
    "source": "synthetic, 5 tenors < MIN_OBSERVATIONS",
    "curve_input_type": "par"
  },
  "input": {
    "tenors_years": [0.25, 1.0, 5.0, 10.0, 30.0],
    "yields_pct": [5.40, 4.80, 3.93, 3.95, 4.08],
    "country_code": "US",
    "observation_date": "2024-01-02"
  },
  "expected": {
    "raises": "InsufficientDataError"
  }
}
```

### 10.3 `synthetic_multi_hump.json` — ConvergenceError / NSS_FAIL

Adversarial input designed to challenge L-BFGS-B — multiple curvature inversions. If L-BFGS-B still converges (well-regularized bounds often rescue pathological cases), expected field becomes `{"flags_contain": "HIGH_RMSE"}` instead:

```json
{
  "meta": {
    "fixture_id": "synthetic_multi_hump",
    "source": "synthetic stress test",
    "curve_input_type": "par"
  },
  "input": {
    "tenors_years": [0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 20.0, 30.0],
    "yields_pct": [5.0, 2.0, 8.0, 1.0, 9.0, 0.5, 10.0, 0.0, 11.0, -0.5],
    "country_code": "US",
    "observation_date": "2024-01-02"
  },
  "expected": {
    "either": {
      "raises": "ConvergenceError",
      "or_flags_contains": "HIGH_RMSE"
    }
  }
}
```

Test handles both branches.

---

## 11. Behavioral test suite

`tests/unit/test_overlays/test_nss_behavior.py`:

```python
"""Behavioral tests for NSS overlay fit + derivations.

Contract-level tests (constants, dataclass immutability) remain in
test_nss_contracts.py. This file verifies actual fit math and spec §7
fixture acceptance.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from sonar.overlays import ConvergenceError, InsufficientDataError
from sonar.overlays import nss


FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "nss-curves"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text())


def _make_input(fx: dict) -> nss.NSSInput:
    i = fx["input"]
    return nss.NSSInput(
        tenors_years=np.array(i["tenors_years"]),
        yields_pct=np.array(i["yields_pct"]),
        country_code=i["country_code"],
        observation_date=date.fromisoformat(i["observation_date"]),
        curve_input_type="par",
    )


class TestFitUSCanonical:
    @pytest.fixture
    def fixture_data(self) -> dict:
        return _load_fixture("us_2024_01_02")

    def test_fit_converges(self, fixture_data: dict) -> None:
        spot = nss.fit_nss(_make_input(fixture_data))
        assert isinstance(spot, nss.SpotCurve)

    def test_rmse_within_tolerance(self, fixture_data: dict) -> None:
        spot = nss.fit_nss(_make_input(fixture_data))
        max_rmse = fixture_data["expected"]["rmse_bps_max"]
        assert spot.rmse_bps <= max_rmse, \
            f"rmse_bps={spot.rmse_bps} exceeds spec §7 tolerance {max_rmse}"

    def test_beta_0_approx(self, fixture_data: dict) -> None:
        spot = nss.fit_nss(_make_input(fixture_data))
        expected = fixture_data["expected"]["beta_0_approx"]
        tol_pct = fixture_data["tolerance"]["beta_relative_pct"] / 100.0
        assert abs(spot.params.beta_0 - expected) / expected <= tol_pct

    def test_fitted_10y(self, fixture_data: dict) -> None:
        spot = nss.fit_nss(_make_input(fixture_data))
        expected = fixture_data["expected"]["fitted_10Y_pct_approx"]
        tol_bps = fixture_data["tolerance"]["fitted_pct_bps"]
        actual = spot.fitted_yields_pct["10Y"]
        assert abs(actual - expected) * 100 <= tol_bps

    def test_confidence_above_floor(self, fixture_data: dict) -> None:
        spot = nss.fit_nss(_make_input(fixture_data))
        assert spot.confidence >= fixture_data["expected"]["confidence_min"]

    def test_observations_used(self, fixture_data: dict) -> None:
        spot = nss.fit_nss(_make_input(fixture_data))
        assert spot.observations_used == 11

    def test_no_reduced_flag(self, fixture_data: dict) -> None:
        # 11 obs ≥ 9 → Svensson full, no NSS_REDUCED.
        spot = nss.fit_nss(_make_input(fixture_data))
        assert "NSS_REDUCED" not in spot.flags

    def test_params_full_svensson(self, fixture_data: dict) -> None:
        spot = nss.fit_nss(_make_input(fixture_data))
        assert spot.params.beta_3 is not None
        assert spot.params.lambda_2 is not None


class TestInsufficientData:
    def test_sparse_5_raises(self) -> None:
        fx = _load_fixture("us_sparse_5")
        with pytest.raises(InsufficientDataError):
            nss.fit_nss(_make_input(fx))

    def test_nan_yields_raises(self) -> None:
        inp = nss.NSSInput(
            tenors_years=np.array([0.25, 1.0, 2.0, 5.0, 10.0, 30.0]),
            yields_pct=np.array([4.0, 4.2, np.nan, 4.4, 4.5, 4.6]),
            country_code="US",
            observation_date=date(2024, 1, 2),
            curve_input_type="par",
        )
        with pytest.raises(InsufficientDataError, match="Non-finite"):
            nss.fit_nss(inp)

    def test_yield_out_of_range_raises(self) -> None:
        inp = nss.NSSInput(
            tenors_years=np.array([0.25, 1.0, 2.0, 5.0, 10.0, 30.0]),
            yields_pct=np.array([4.0, 4.2, 4.3, 4.4, 4.5, 50.0]),  # 50% > 30
            country_code="US",
            observation_date=date(2024, 1, 2),
            curve_input_type="par",
        )
        with pytest.raises(InsufficientDataError):
            nss.fit_nss(inp)


class TestMultiHumpStress:
    def test_either_converges_degraded_or_raises(self) -> None:
        fx = _load_fixture("synthetic_multi_hump")
        try:
            spot = nss.fit_nss(_make_input(fx))
        except ConvergenceError:
            return  # Acceptable per fixture expected.either
        # If converged, RMSE must be bad enough to flag.
        assert "HIGH_RMSE" in spot.flags


class TestReducedFit:
    def test_7_obs_triggers_reduced(self) -> None:
        # 7 observations: 6 ≤ n < 9 → NSS_REDUCED.
        inp = nss.NSSInput(
            tenors_years=np.array([0.25, 1.0, 2.0, 3.0, 5.0, 10.0, 30.0]),
            yields_pct=np.array([5.40, 4.80, 4.33, 4.05, 3.93, 3.95, 4.08]),
            country_code="US",
            observation_date=date(2024, 1, 2),
            curve_input_type="par",
        )
        spot = nss.fit_nss(inp)
        assert "NSS_REDUCED" in spot.flags
        assert spot.params.beta_3 is None
        assert spot.params.lambda_2 is None
        assert spot.confidence <= 0.75  # cap per §6 row 2


class TestDerivations:
    @pytest.fixture
    def us_spot(self) -> nss.SpotCurve:
        return nss.fit_nss(_make_input(_load_fixture("us_2024_01_02")))

    def test_zero_curve_shape(self, us_spot: nss.SpotCurve) -> None:
        z = nss.derive_zero_curve(us_spot)
        assert set(z.zero_rates_pct.keys()) == set(nss.STANDARD_OUTPUT_TENORS)
        assert z.derivation == "nss_derived"

    def test_zero_curve_values_realistic(self, us_spot: nss.SpotCurve) -> None:
        z = nss.derive_zero_curve(us_spot)
        for tenor_label, rate_pct in z.zero_rates_pct.items():
            assert -5.0 <= rate_pct <= 30.0, \
                f"Zero rate {tenor_label}={rate_pct}% out of sane range"

    def test_forward_curve_keys(self, us_spot: nss.SpotCurve) -> None:
        z = nss.derive_zero_curve(us_spot)
        f = nss.derive_forward_curve(z)
        assert set(f.forwards_pct.keys()) == set(nss.STANDARD_FORWARD_KEYS)

    def test_forward_5y5y_within_sane_bounds(self, us_spot: nss.SpotCurve) -> None:
        z = nss.derive_zero_curve(us_spot)
        f = nss.derive_forward_curve(z)
        # 5y5y for US 2024-01-02 historically ~ 3.8-4.0%
        assert 2.0 <= f.forwards_pct["5y5y"] <= 6.0

    def test_real_curve_none_without_inputs(self, us_spot: nss.SpotCurve) -> None:
        # Derived path without E[π] → None acceptable.
        r = nss.derive_real_curve(us_spot, linker_yields_pct=None)
        assert r is None


class TestConfidencePropagation:
    def test_base_confidence_no_flags(self) -> None:
        c = nss._compute_confidence([], tier="T1")
        assert c == 1.0

    def test_reduced_caps_at_075(self) -> None:
        c = nss._compute_confidence(["NSS_REDUCED"], tier="T1")
        assert c <= 0.75

    def test_high_rmse_deducts_020(self) -> None:
        c = nss._compute_confidence(["HIGH_RMSE"], tier="T1")
        assert abs(c - 0.80) < 1e-9

    def test_stacking_reduced_plus_high_rmse(self) -> None:
        # Cap 0.75 + deduction 0.20 → min(0.75, 1.0 - 0.20) = 0.75
        c = nss._compute_confidence(["NSS_REDUCED", "HIGH_RMSE"], tier="T1")
        assert c == pytest.approx(0.75)

    def test_tier_4_cap(self) -> None:
        c = nss._compute_confidence([], tier="T4")
        assert c <= 0.70
```

---

## 12. Commit structure

### Commit 1/2 — math core

```
feat(overlays): NSS fit + zero/forward/real derivations (NSS_v0.1)

Implement src/sonar/overlays/nss.py bodies per
docs/specs/overlays/nss-curves.md @ NSS_v0.1:

- fit_nss: scipy.optimize.minimize L-BFGS-B, 6-param Svensson with
  4-param NS reduced fallback for 6 ≤ n_obs < 9 (spec §6 row 2).
- _validate_inputs: spec §6 row 1 (n_obs, finite, range, ascending).
- _nss_eval: numerically stable via np.expm1, handles τ/λ → 0 limit.
- derive_zero_curve: evaluate NSS at STANDARD_OUTPUT_TENORS (spec §4.4).
- derive_forward_curve: bootstrap from zero per spec §4.5,
  six STANDARD_FORWARD_KEYS.
- derive_real_curve: direct_linker path (fit NSS to linker yields);
  derived path returns None for Week 2 (expected-inflation overlay
  integration deferred).
- _compute_confidence: spec §6 cap-then-deduct per flags.md propagation
  rules (or authoritative deviation if flags.md differs — see body).

Unit convention (inputs percent / internal decimal): fit internally
operates in decimal; outputs percent per consumer contract.

pyproject.toml: explicit floors scipy>=1.17, numpy>=2.4
(deferred item from Day 1 PM — match installed versions, protect from
transitive drift).

No persistence, no connector fetches, no xval — Day 3 AM scope.
```

### Commit 2/2 — fixtures + behavioral tests

```
test(overlays): NSS behavioral suite + spec §7 fixtures

Replace contract tests with behavioral suite in test_nss_behavior.py:
- US 2024-01-02 canonical fit (rmse_bps ≤ 5, β0 ≈ 4.15%, 10Y ≈ 3.95%)
- InsufficientDataError paths (sparse, NaN, out-of-range)
- Multi-hump synthetic stress (either ConvergenceError or HIGH_RMSE flag)
- Reduced fit (7 obs → NSS_REDUCED, confidence ≤ 0.75)
- Derivation shape + sanity tests (zero/forward/real)
- Confidence propagation matrix

test_nss_contracts.py trimmed: removed TestFunctionSignatures
(NotImplementedError tests superseded).

Fixtures in tests/fixtures/nss-curves/:
- us_2024_01_02.json (FRED H.15)
- us_sparse_5.json (synthetic)
- synthetic_multi_hump.json (adversarial)

Coverage src/sonar/overlays/ scope target ≥ 90% per
phase1-coverage-policy.md per-module hard gate.
```

---

## 13. Acceptance checklist

- [ ] `pyproject.toml` explicit scipy/numpy floors declared
- [ ] `uv lock` regenerated and committed
- [ ] `fit_nss` implemented (6-param + 4-param reduced paths)
- [ ] `_validate_inputs` covers spec §6 row 1 cases
- [ ] `_nss_eval` uses `np.expm1` for numerical stability
- [ ] `derive_zero_curve`, `derive_forward_curve`, `derive_real_curve` implemented
- [ ] `_compute_confidence` implemented per flags.md (or documented deviation)
- [ ] 3 fixture files created under `tests/fixtures/nss-curves/`
- [ ] `test_nss_behavior.py` created with ≥ 20 tests covering sections in §11
- [ ] `test_nss_contracts.py` trimmed (no NotImplementedError tests)
- [ ] `uv run pytest tests/ -x` → full green
- [ ] `uv run pytest --cov=src/sonar/overlays` → ≥ 90%
- [ ] `uv run mypy src/sonar/overlays/` → clean (scipy untyped-imports resolved via pyproject override if needed)
- [ ] `pre-commit run --all-files` → clean
- [ ] 2 commits pushed per §12
- [ ] Local HEAD matches remote

---

## 14. Report-back (paste to chat)

1. Both commit SHAs + `git log --oneline -2`
2. Test count + pass rate: `pytest tests/unit/test_overlays/ -v | tail -5`
3. `uv run pytest --cov=src/sonar/overlays --cov-report=term tests/ | tail -5`
4. For `us_2024_01_02` fixture: actual `(beta_0, rmse_bps, fitted_10Y_pct, confidence)` tuple
5. flags.md propagation — did default §5.5 algorithm apply, or was deviation needed? Link to line in flags.md if deviated.
6. units.md — did `yields_pct`/`decimal` convention hold, or deviation?
7. Timer actual vs 90–120 min budget
8. HALT triggers resolved mid-flight (narrate)
9. Out-of-scope items surfaced for triage

---

*End of brief. Proceed.*
