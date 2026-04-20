"""M1 Effective Rates — monetary stance index.

Spec: docs/specs/indices/monetary/M1-effective-rates.md @
``M1_EFFECTIVE_RATES_v0.2``.

3-sub-component weighted composite::

    real_shadow_rate     = shadow_rate - expected_inflation_5y
    stance_vs_neutral    = real_shadow_rate - r_star          # score_raw
    balance_sheet_signal = -(BS_GDP_t - BS_GDP_{t-12m})

    ES_raw = 0.50*z(real_shadow_rate)
           + 0.35*z(stance_vs_neutral)
           + 0.15*z(balance_sheet_signal)

    score_normalized = clip(50 + 16.67 * ES_raw, 0, 100)

Higher = tighter monetary stance. 30Y rolling z-score window
(canonical; 15Y Tier-4 fallback). Shadow-rate workaround: when
``policy_rate > 0.5 %`` (outside ZLB) the spec §2 precondition
allows ``shadow_rate := policy_rate`` directly; current US + EA are
above ZLB so this module uses that path. r* supplied externally via
hardcoded YAML config (Phase 1 workaround until HLW connector).
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

METHODOLOGY_VERSION: str = "M1_EFFECTIVE_RATES_v0.2"
DEFAULT_LOOKBACK_YEARS: int = 30
TIER4_LOOKBACK_YEARS: int = 15
ZLB_THRESHOLD_PCT: float = 0.005  # 0.5 % cutoff per spec §4 step 2

SUBSCORE_WEIGHTS: dict[str, float] = {
    "real_shadow_rate": 0.50,
    "stance_vs_neutral": 0.35,
    "balance_sheet_signal": 0.15,
}


@dataclass(frozen=True, slots=True)
class M1EffectiveRatesInputs:
    """Inputs for a single (country, date) M1 compute."""

    country_code: str
    observation_date: date
    policy_rate_pct: float  # decimal, e.g. 0.0525 for 5.25%
    expected_inflation_5y_pct: float  # decimal
    r_star_pct: float  # decimal
    balance_sheet_pct_gdp_current: float  # BS/GDP now (decimal, e.g. 0.30 = 30%)
    balance_sheet_pct_gdp_12m_ago: float  # BS/GDP 12 months ago
    real_shadow_rate_history: Sequence[float] = field(default_factory=tuple)
    stance_vs_neutral_history: Sequence[float] = field(default_factory=tuple)
    balance_sheet_signal_history: Sequence[float] = field(default_factory=tuple)
    shadow_rate_pct: float | None = None  # None → use policy_rate (spec §4 step 2)
    lookback_years: int = DEFAULT_LOOKBACK_YEARS
    source_connector: tuple[str, ...] = ()
    upstream_flags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class M1EffectiveRatesResult:
    """Canonical M1 output contract — mirrors ``monetary_m1_effective_rates`` schema."""

    country_code: str
    date: date
    methodology_version: str
    score_normalized: float
    score_raw: float  # stance_vs_neutral in pp
    policy_rate_pct: float
    shadow_rate_pct: float
    real_rate_pct: float
    r_star_pct: float
    components_json: str
    lookback_years: int
    confidence: float
    flags: tuple[str, ...]
    source_connector: str


def compute_m1_effective_rates(inputs: M1EffectiveRatesInputs) -> M1EffectiveRatesResult:
    """Compute M1 effective rates index per spec §4."""
    flags: list[str] = list(inputs.upstream_flags)

    # Step 2: resolve shadow rate.
    if inputs.shadow_rate_pct is not None:
        shadow_rate = inputs.shadow_rate_pct
    elif inputs.policy_rate_pct > ZLB_THRESHOLD_PCT:
        shadow_rate = inputs.policy_rate_pct
    else:
        # ZLB regime without Krippner — spec §6 flags SHADOW_RATE_UNAVAILABLE
        # and caller typically skips M1 at that point.
        msg = (
            f"M1 requires shadow_rate for country={inputs.country_code} at ZLB "
            f"(policy_rate={inputs.policy_rate_pct}); Krippner connector not shipped"
        )
        raise InsufficientDataError(msg)

    # Step 3-4: real_shadow_rate = shadow - E[π]_5Y.
    real_shadow_rate = shadow_rate - inputs.expected_inflation_5y_pct

    # Step 6: stance_vs_neutral = real_shadow - r_star (score_raw).
    stance_vs_neutral = real_shadow_rate - inputs.r_star_pct

    # Step 7: balance_sheet_signal = -(BS/GDP_t - BS/GDP_{t-12m}).
    balance_sheet_signal = -(
        inputs.balance_sheet_pct_gdp_current - inputs.balance_sheet_pct_gdp_12m_ago
    )

    # Step 8: z-scores per component over 30Y rolling.
    z_real_shadow, _mu_rs, _sig_rs, n_rs = rolling_zscore(
        inputs.real_shadow_rate_history, current=real_shadow_rate
    )
    z_stance, _mu_st, _sig_st, n_st = rolling_zscore(
        inputs.stance_vs_neutral_history, current=stance_vs_neutral
    )
    z_bs, _mu_bs, _sig_bs, n_bs = rolling_zscore(
        inputs.balance_sheet_signal_history, current=balance_sheet_signal
    )

    hist_floor = int(inputs.lookback_years * 12 * 0.8)  # monthly obs approx
    insufficient = [
        name
        for name, n in (
            ("real_shadow_rate", n_rs),
            ("stance_vs_neutral", n_st),
            ("balance_sheet_signal", n_bs),
        )
        if n < hist_floor
    ]
    if insufficient:
        flags.append("INSUFFICIENT_HISTORY")

    # Step 9-10: aggregate ES_raw and map to [0, 100].
    es_raw = (
        SUBSCORE_WEIGHTS["real_shadow_rate"] * z_real_shadow
        + SUBSCORE_WEIGHTS["stance_vs_neutral"] * z_stance
        + SUBSCORE_WEIGHTS["balance_sheet_signal"] * z_bs
    )
    score_normalized = max(0.0, min(100.0, 50.0 + 16.67 * es_raw))

    components: dict[str, object] = {
        "real_shadow_rate_pct": real_shadow_rate,
        "shadow_rate_minus_rstar_pct": stance_vs_neutral,
        "balance_sheet_pct_gdp_yoy": inputs.balance_sheet_pct_gdp_current
        - inputs.balance_sheet_pct_gdp_12m_ago,
        "es_subscore_real_shadow": round(50.0 + 16.67 * z_real_shadow, 4),
        "es_subscore_rstar_gap": round(50.0 + 16.67 * z_stance, 4),
        "es_subscore_balance_sheet": round(50.0 + 16.67 * z_bs, 4),
        "weights": {
            "real_shadow": SUBSCORE_WEIGHTS["real_shadow_rate"],
            "rstar_gap": SUBSCORE_WEIGHTS["stance_vs_neutral"],
            "balance_sheet": SUBSCORE_WEIGHTS["balance_sheet_signal"],
        },
    }

    confidence = 1.0 - 0.10 * len(insufficient)
    confidence = max(0.0, min(1.0, confidence))

    return M1EffectiveRatesResult(
        country_code=inputs.country_code,
        date=inputs.observation_date,
        methodology_version=METHODOLOGY_VERSION,
        score_normalized=score_normalized,
        score_raw=stance_vs_neutral,
        policy_rate_pct=inputs.policy_rate_pct,
        shadow_rate_pct=shadow_rate,
        real_rate_pct=real_shadow_rate,
        r_star_pct=inputs.r_star_pct,
        components_json=json.dumps(components, sort_keys=True),
        lookback_years=inputs.lookback_years,
        confidence=confidence,
        flags=tuple(sorted(set(flags))),
        source_connector=",".join(sorted(inputs.source_connector))
        if inputs.source_connector
        else "",
    )


__all__ = [
    "DEFAULT_LOOKBACK_YEARS",
    "METHODOLOGY_VERSION",
    "SUBSCORE_WEIGHTS",
    "TIER4_LOOKBACK_YEARS",
    "ZLB_THRESHOLD_PCT",
    "M1EffectiveRatesInputs",
    "M1EffectiveRatesResult",
    "compute_m1_effective_rates",
]
