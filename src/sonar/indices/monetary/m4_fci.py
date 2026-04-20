"""M4 FCI — financial conditions index.

Spec: docs/specs/indices/monetary/M4-fci.md @ ``M4_FCI_v0.1``.

Provider hierarchy:

* **US + NFCI available**: use Chicago Fed NFCI directly (already
  z-scored by Chicago Fed); ``fci_level = NFCI``.
* Otherwise: custom 7-component composite per spec Cap 10.6 weights::

      fci_level = 0.30*z(credit_spread_bps)
                + 0.25*z(vol_index)
                + 0.20*z(gov_10y_yield_pct)
                + 0.15*z(fx_neer_pct)
                + 0.10*z(mortgage_rate_pct)

FC sub-index per spec Cap 15.5 combines level + momentum + cross-
asset stress::

    fci_change_12m     = fci_level_t - fci_level_{t-252bd}
    cross_asset_stress = max(z(...)) - min(z(...)) over the cluster
    FC_raw             = 0.55*fci_level + 0.25*fci_change_12m
                       + 0.20*cross_asset_stress
    score_normalized   = clip(50 + 16.67*FC_raw, 0, 100)

Higher = tighter financial conditions. Custom path requires >= 5/7
components or raises.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sonar.indices._helpers.z_score_rolling import rolling_zscore
from sonar.overlays.exceptions import InsufficientDataError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date

METHODOLOGY_VERSION: str = "M4_FCI_v0.1"
DEFAULT_LOOKBACK_YEARS: int = 30
TIER4_LOOKBACK_YEARS: int = 15
MIN_CUSTOM_COMPONENTS: int = 5  # spec §4 step 3

CUSTOM_COMPONENT_WEIGHTS: dict[str, float] = {
    "credit_spread_bps": 0.30,
    "vol_index": 0.25,
    "gov_10y_yield_pct": 0.20,
    "fx_neer_pct": 0.15,
    "mortgage_rate_pct": 0.10,
}

FC_AGGREGATE_WEIGHTS: dict[str, float] = {
    "fci_level": 0.55,
    "fci_change_12m": 0.25,
    "cross_asset_stress": 0.20,
}


@dataclass(frozen=True, slots=True)
class M4FciInputs:
    """Inputs for a single (country, date) M4 compute."""

    country_code: str
    observation_date: date
    # Direct NFCI path (US primary).
    nfci_level: float | None = None
    nfci_history: Sequence[float] = field(default_factory=tuple)
    # Custom path components.
    credit_spread_bps: float | None = None
    credit_spread_bps_history: Sequence[float] = field(default_factory=tuple)
    vol_index: float | None = None
    vol_index_history: Sequence[float] = field(default_factory=tuple)
    gov_10y_yield_pct: float | None = None
    gov_10y_yield_pct_history: Sequence[float] = field(default_factory=tuple)
    fx_neer_pct: float | None = None
    fx_neer_pct_history: Sequence[float] = field(default_factory=tuple)
    mortgage_rate_pct: float | None = None
    mortgage_rate_pct_history: Sequence[float] = field(default_factory=tuple)
    # Prior fci_level 12m ago for momentum.
    fci_level_12m_ago: float | None = None
    lookback_years: int = DEFAULT_LOOKBACK_YEARS
    source_connector: tuple[str, ...] = ()
    upstream_flags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class M4FciResult:
    """Canonical M4 output — mirrors ``monetary_m4_fci`` schema."""

    country_code: str
    date: date
    methodology_version: str
    score_normalized: float
    score_raw: float  # fci_level
    fci_level: float
    fci_change_12m: float | None
    fci_provider: str
    components_available: int
    fci_components_json: str
    lookback_years: int
    confidence: float
    flags: tuple[str, ...]
    source_connector: str


def _compute_custom_fci(
    inputs: M4FciInputs,
) -> tuple[float, dict[str, float], int, list[str]]:
    """Return (fci_level, component_z_dict, n_components, flags).

    Raises InsufficientDataError when < MIN_CUSTOM_COMPONENTS.
    """
    flags: list[str] = []
    triples = [
        ("credit_spread_bps", inputs.credit_spread_bps, inputs.credit_spread_bps_history),
        ("vol_index", inputs.vol_index, inputs.vol_index_history),
        ("gov_10y_yield_pct", inputs.gov_10y_yield_pct, inputs.gov_10y_yield_pct_history),
        ("fx_neer_pct", inputs.fx_neer_pct, inputs.fx_neer_pct_history),
        ("mortgage_rate_pct", inputs.mortgage_rate_pct, inputs.mortgage_rate_pct_history),
    ]
    hist_floor = int(inputs.lookback_years * 12 * 0.8)
    available: list[tuple[str, float]] = []
    insufficient_count = 0
    for name, current, history in triples:
        if current is None:
            continue
        z, _mu, _sigma, n = rolling_zscore(history, current=current)
        if n < hist_floor:
            insufficient_count += 1
        available.append((name, z))

    if len(available) < MIN_CUSTOM_COMPONENTS:
        msg = f"M4 custom path requires >= {MIN_CUSTOM_COMPONENTS} components; got {len(available)}"
        raise InsufficientDataError(msg)

    weight_sum = sum(CUSTOM_COMPONENT_WEIGHTS[name] for name, _ in available)
    fci_level = 0.0
    z_dict: dict[str, float] = {}
    for name, z in available:
        w_effective = CUSTOM_COMPONENT_WEIGHTS[name] / weight_sum
        fci_level += w_effective * z
        z_dict[f"{name}_z"] = z

    if insufficient_count > 0:
        flags.append("INSUFFICIENT_HISTORY")
    if len(available) < len(triples):
        flags.append("CUSTOM_FCI_DEGRADED")
    return fci_level, z_dict, len(available), flags


def compute_m4_fci(inputs: M4FciInputs) -> M4FciResult:
    """Compute M4 FCI per spec §4 (NFCI-primary for US, custom otherwise)."""
    flags: list[str] = list(inputs.upstream_flags)

    # Step 1: resolve provider.
    use_nfci = inputs.country_code == "US" and inputs.nfci_level is not None
    if use_nfci:
        fci_level = float(inputs.nfci_level)  # type: ignore[arg-type]
        provider = "NFCI_CHICAGO"
        components_available = 1
        z_dict: dict[str, float] = {"nfci_z": fci_level}
    else:
        fci_level, z_dict, components_available, custom_flags = _compute_custom_fci(inputs)
        provider = "CUSTOM_SONAR"
        flags.extend(custom_flags)

    # Step 4: fci_change_12m (momentum).
    fci_change_12m: float | None = None
    if inputs.fci_level_12m_ago is not None:
        fci_change_12m = fci_level - inputs.fci_level_12m_ago

    # Step 5: cross_asset_stress (dispersion across z-scores).
    if len(z_dict) >= 2:
        z_values = list(z_dict.values())
        cross_asset_stress = max(z_values) - min(z_values)
    else:
        cross_asset_stress = 0.0

    # Step 6: aggregate FC_raw.
    if fci_change_12m is None:
        # Re-normalize the two remaining terms (level + cross-asset).
        w_level = FC_AGGREGATE_WEIGHTS["fci_level"]
        w_cross = FC_AGGREGATE_WEIGHTS["cross_asset_stress"]
        total = w_level + w_cross
        fc_raw = (w_level / total) * fci_level + (w_cross / total) * cross_asset_stress
        flags.append("FCI_MOMENTUM_MISSING")
    else:
        fc_raw = (
            FC_AGGREGATE_WEIGHTS["fci_level"] * fci_level
            + FC_AGGREGATE_WEIGHTS["fci_change_12m"] * fci_change_12m
            + FC_AGGREGATE_WEIGHTS["cross_asset_stress"] * cross_asset_stress
        )

    score_normalized = max(0.0, min(100.0, 50.0 + 16.67 * fc_raw))

    components_json = json.dumps(
        {
            **z_dict,
            "fci_level": fci_level,
            "fci_change_12m": fci_change_12m,
            "cross_asset_stress": cross_asset_stress,
            "provider": provider,
            "weights": dict(FC_AGGREGATE_WEIGHTS),
        },
        sort_keys=True,
    )

    confidence = (
        1.0
        - 0.05 * flags.count("INSUFFICIENT_HISTORY")
        - 0.10 * flags.count("CUSTOM_FCI_DEGRADED")
        - 0.10 * flags.count("FCI_MOMENTUM_MISSING")
    )
    confidence = max(0.0, min(1.0, confidence))

    return M4FciResult(
        country_code=inputs.country_code,
        date=inputs.observation_date,
        methodology_version=METHODOLOGY_VERSION,
        score_normalized=score_normalized,
        score_raw=fci_level,
        fci_level=fci_level,
        fci_change_12m=fci_change_12m,
        fci_provider=provider,
        components_available=components_available,
        fci_components_json=components_json,
        lookback_years=inputs.lookback_years,
        confidence=confidence,
        flags=tuple(sorted(set(flags))),
        source_connector=",".join(sorted(inputs.source_connector))
        if inputs.source_connector
        else "",
    )


__all__ = [
    "CUSTOM_COMPONENT_WEIGHTS",
    "DEFAULT_LOOKBACK_YEARS",
    "FC_AGGREGATE_WEIGHTS",
    "METHODOLOGY_VERSION",
    "MIN_CUSTOM_COMPONENTS",
    "TIER4_LOOKBACK_YEARS",
    "M4FciInputs",
    "M4FciResult",
    "compute_m4_fci",
]
