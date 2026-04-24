"""SWAP method — zero-coupon inflation swap tape.

Spec: ``docs/specs/overlays/expected-inflation.md`` §4 (SWAP
``EXP_INF_SWAP_v0.1``) + §8 ``exp_inflation_swap`` schema.

Sprint 1 (Week 11 Sprint 1) ships the writer contract + the compute
primitive. The EA backfill consumes ECB SDW swap-tape rates when the
connector fetch is wired (CAL-EXPINF-SWAP-EA pending); until then the
backfill orchestrator falls back to the EA SPF long-term anchor as a
SWAP_PLACEHOLDER_SYNTHETIC proxy so the hierarchy cascade + canonical
composition can be exercised end-to-end.

Per spec §4 step 6, SWAP inherits no upstream flags (fresh from
connector). Confidence baseline 1.0; ``-0.20`` deduction when emitted
with ``STALE`` (quote > 5bd).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

import structlog
from sqlalchemy import text

from sonar.overlays.expected_inflation import compute_5y5y

if TYPE_CHECKING:
    from datetime import date as date_t

    from sqlalchemy.orm import Session

log = structlog.get_logger()

__all__ = [
    "METHODOLOGY_VERSION_SWAP",
    "ExpInfSwap",
    "compute_swap",
    "persist_swap_row",
]

METHODOLOGY_VERSION_SWAP: str = "EXP_INF_SWAP_v0.1"


@dataclass(frozen=True, slots=True)
class ExpInfSwap:
    """SWAP method row — zero-coupon inflation swap rates per tenor."""

    country_code: str
    observation_date: date_t
    swap_rates: dict[str, float]
    swap_provider: str
    confidence: float
    flags: tuple[str, ...]


def compute_swap(
    country_code: str,
    swap_rates: dict[str, float],
    *,
    observation_date: date_t,
    swap_provider: str,
    confidence: float = 1.0,
    flags: tuple[str, ...] = (),
) -> ExpInfSwap:
    """Build :class:`ExpInfSwap` from connector-sourced tenor rates.

    Adds compounded ``5y5y`` when both ``5Y`` and ``10Y`` are present
    (spec §4 forward formula). Rates decimal per
    ``conventions/units.md`` §Yields.
    """
    rates = dict(swap_rates)
    if "5Y" in rates and "10Y" in rates and "5y5y" not in rates:
        rates["5y5y"] = compute_5y5y(rates["5Y"], rates["10Y"])
    return ExpInfSwap(
        country_code=country_code,
        observation_date=observation_date,
        swap_rates=rates,
        swap_provider=swap_provider,
        confidence=confidence,
        flags=flags,
    )


_INSERT_SWAP_SQL = text(
    """
    INSERT OR IGNORE INTO exp_inflation_swap (
        exp_inf_id,
        country_code,
        date,
        methodology_version,
        confidence,
        flags,
        swap_rates_json,
        swap_provider
    ) VALUES (
        :exp_inf_id,
        :country_code,
        :date,
        :methodology_version,
        :confidence,
        :flags,
        :swap_rates_json,
        :swap_provider
    )
    """,
)


def persist_swap_row(
    session: Session,
    swap: ExpInfSwap,
    *,
    methodology_version: str = METHODOLOGY_VERSION_SWAP,
) -> bool:
    """Upsert a single :class:`ExpInfSwap` row into ``exp_inflation_swap``.

    Returns ``True`` if a new row was inserted, ``False`` if the unique
    key ``(country_code, date, methodology_version)`` matched an
    existing row (idempotent retry / backfill per ADR-0011 P1). Caller
    commits. Flags stored CSV lexicographic-sorted per
    ``conventions/flags.md``.
    """
    if not swap.swap_rates:
        msg = (
            f"persist_swap_row: empty swap_rates for {swap.country_code!r} "
            f"{swap.observation_date.isoformat()}"
        )
        raise ValueError(msg)
    flags_csv = ",".join(sorted(swap.flags)) if swap.flags else None
    params = {
        "exp_inf_id": str(uuid4()),
        "country_code": swap.country_code,
        "date": swap.observation_date.isoformat(),
        "methodology_version": methodology_version,
        "confidence": float(swap.confidence),
        "flags": flags_csv,
        "swap_rates_json": json.dumps(swap.swap_rates, sort_keys=True),
        "swap_provider": swap.swap_provider,
    }
    result = session.execute(_INSERT_SWAP_SQL, params)
    rowcount = getattr(result, "rowcount", None) or 0
    inserted = rowcount > 0
    result.close()
    if inserted:
        log.info(
            "exp_inflation_writers.swap.inserted",
            country=swap.country_code,
            date=params["date"],
            provider=swap.swap_provider,
            tenors=sorted(swap.swap_rates),
        )
    else:
        log.debug(
            "exp_inflation_writers.swap.duplicate_skipped",
            country=swap.country_code,
            date=params["date"],
            methodology_version=methodology_version,
        )
    return inserted
