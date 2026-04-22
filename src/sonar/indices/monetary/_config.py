"""YAML config loaders for M-indices: r* values + central-bank targets.

Both YAMLs live under ``src/sonar/config/`` (data directory parallel to
``sonar.config`` Pydantic-Settings module — not a Python package). This
module is the read-only access layer.

Staleness rule per CCCS spec §2 precondition: r* ``last_updated``
> :data:`R_STAR_STALENESS_DAYS` triggers ``CALIBRATION_STALE`` flag at
the consumer.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
import yaml

if TYPE_CHECKING:
    from collections.abc import Mapping

log = structlog.get_logger()

CONFIG_DIR: Path = Path(__file__).resolve().parents[2] / "config"
R_STAR_PATH: Path = CONFIG_DIR / "r_star_values.yaml"
BC_TARGETS_PATH: Path = CONFIG_DIR / "bc_targets.yaml"

R_STAR_STALENESS_DAYS: int = 95
EA_PROXY_COUNTRIES: frozenset[str] = frozenset({"PT", "IT", "ES", "FR", "NL", "DE", "IE"})

# Deprecated country-code aliases → canonical ISO 3166-1 alpha-2 per
# ADR-0007. Lookups for the alias succeed but emit a structlog
# deprecation warning so operators can migrate call sites before the
# Week 10 removal window.
_DEPRECATED_COUNTRY_ALIASES: dict[str, str] = {"UK": "GB"}


def _canonicalize_country_code(country_code: str) -> str:
    """Return canonical ISO alpha-2 code; warn on deprecated alias."""
    if country_code in _DEPRECATED_COUNTRY_ALIASES:
        canonical = _DEPRECATED_COUNTRY_ALIASES[country_code]
        log.warning(
            "config.country_alias_deprecated",
            input=country_code,
            canonical=canonical,
            source="sonar.indices.monetary._config",
        )
        return canonical
    return country_code


@lru_cache(maxsize=1)
def load_r_star_values() -> dict[str, dict[str, object]]:
    """Return the parsed r* YAML keyed by country code."""
    with R_STAR_PATH.open() as f:
        return yaml.safe_load(f)  # type: ignore[no-any-return]


@lru_cache(maxsize=1)
def _load_bc_targets() -> dict[str, dict[str, object]]:
    with BC_TARGETS_PATH.open() as f:
        return yaml.safe_load(f)  # type: ignore[no-any-return]


def load_bc_targets() -> dict[str, float]:
    """Return ``{cb_name: target}`` map."""
    raw = _load_bc_targets()["targets"]
    assert isinstance(raw, dict)
    return {str(k): float(v) for k, v in raw.items()}  # type: ignore[arg-type]


def load_country_to_target() -> Mapping[str, str]:
    """Return ``{country_code: cb_name}`` map."""
    raw = _load_bc_targets()["country_to_target"]
    assert isinstance(raw, dict)
    return {str(k): str(v) for k, v in raw.items()}


def load_target_conventions() -> Mapping[str, str]:
    """Return ``{country_code: convention}`` map.

    Countries absent default to ``"domestic"`` (the country's central
    bank publishes the point or band-midpoint target the country
    tracks). Sprint Y-DK introduces ``"imported_eur_peg"`` for DK to
    capture the EUR-peg-coupling story — Nationalbanken's mandate is
    exchange-rate stability + the de-facto inflation anchor is
    imported from the ECB's 2 % HICP target via the DKK/EUR peg.
    """
    raw = _load_bc_targets().get("target_conventions") or {}
    assert isinstance(raw, dict)
    return {str(k): str(v) for k, v in raw.items()}


def resolve_inflation_target_convention(country_code: str) -> str:
    """Return the target-resolution convention for the country.

    Defaults to ``"domestic"``. Returns ``"imported_eur_peg"`` for DK
    (and any future country with the same ERM-II-style fixed-rate
    regime). Cascade builders use this to pick the right flag —
    ``EXPECTED_INFLATION_CB_TARGET`` for domestic vs
    ``DK_INFLATION_TARGET_IMPORTED_FROM_EA`` for imported_eur_peg.
    """
    canonical = _canonicalize_country_code(country_code)
    return load_target_conventions().get(canonical, "domestic")


def resolve_r_star(country_code: str) -> tuple[float, bool]:
    """Return ``(r_star_pct, is_proxy)`` for the country.

    EA periphery countries (PT/IT/ES/FR/NL/DE/IE) get the EA r* with
    ``is_proxy=True`` so callers can emit ``R_STAR_PROXY`` flag. An
    explicit ``proxy: true`` marker on a country entry (e.g. GB) also
    flags the return tuple; consumers treat both paths identically.

    Legacy input ``"UK"`` aliases to ``"GB"`` per ADR-0007 and emits a
    deprecation warning.
    """
    canonical = _canonicalize_country_code(country_code)
    values = load_r_star_values()
    if canonical in values:
        entry = values[canonical]
        is_proxy = bool(entry.get("proxy", False))
        return float(entry["r_star_pct"]), is_proxy  # type: ignore[arg-type]
    if canonical in EA_PROXY_COUNTRIES:
        return float(values["EA"]["r_star_pct"]), True  # type: ignore[arg-type]
    msg = f"No r* value or EA-proxy mapping for country={country_code}"
    raise KeyError(msg)


def resolve_inflation_target(country_code: str) -> float:
    """Return the central-bank inflation target for the country.

    Legacy input ``"UK"`` aliases to ``"GB"`` per ADR-0007 and emits a
    deprecation warning.
    """
    canonical = _canonicalize_country_code(country_code)
    mapping = load_country_to_target()
    if canonical not in mapping:
        msg = f"No inflation-target mapping for country={country_code}"
        raise KeyError(msg)
    cb_name = mapping[canonical]
    targets = load_bc_targets()
    return float(targets[cb_name])


def is_r_star_stale(country_code: str, today: date) -> bool:
    """``True`` when ``last_updated`` for ``country_code``'s r* is over the staleness window."""
    canonical = _canonicalize_country_code(country_code)
    values = load_r_star_values()
    src = canonical if canonical in values else "EA"
    last_updated_raw = values[src]["last_updated"]
    if isinstance(last_updated_raw, date):
        last_updated = last_updated_raw
    else:
        last_updated = date.fromisoformat(str(last_updated_raw))
    return (today - last_updated).days > R_STAR_STALENESS_DAYS


__all__ = [
    "BC_TARGETS_PATH",
    "CONFIG_DIR",
    "EA_PROXY_COUNTRIES",
    "R_STAR_PATH",
    "R_STAR_STALENESS_DAYS",
    "is_r_star_stale",
    "load_bc_targets",
    "load_country_to_target",
    "load_r_star_values",
    "load_target_conventions",
    "resolve_inflation_target",
    "resolve_inflation_target_convention",
    "resolve_r_star",
]
