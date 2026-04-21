"""Unit tests for monetary _config YAML loaders."""

from __future__ import annotations

from datetime import date

import pytest

from sonar.indices.monetary._config import (
    EA_PROXY_COUNTRIES,
    R_STAR_STALENESS_DAYS,
    is_r_star_stale,
    load_bc_targets,
    load_country_to_target,
    load_r_star_values,
    resolve_inflation_target,
    resolve_r_star,
)


class TestRStarLoader:
    def test_us_direct(self) -> None:
        r_star, is_proxy = resolve_r_star("US")
        assert r_star == pytest.approx(0.008)
        assert is_proxy is False

    def test_pt_uses_ea_proxy(self) -> None:
        r_star, is_proxy = resolve_r_star("PT")
        assert r_star == pytest.approx(-0.005)
        assert is_proxy is True

    def test_unknown_country_raises(self) -> None:
        with pytest.raises(KeyError, match="No r\\* value"):
            resolve_r_star("XX")

    def test_yaml_keys_present(self) -> None:
        values = load_r_star_values()
        assert "US" in values
        assert "EA" in values
        assert "GB" in values
        assert "r_star_pct" in values["US"]

    def test_gb_direct_with_proxy_flag(self) -> None:
        """GB has its own entry marked ``proxy: true`` (no HLW-GB series)."""
        r_star, is_proxy = resolve_r_star("GB")
        assert r_star == pytest.approx(0.005)
        assert is_proxy is True

    def test_uk_alias_resolves_to_gb(self) -> None:
        """Legacy ``"UK"`` input routes to GB entry per ADR-0007 alias."""
        r_star, is_proxy = resolve_r_star("UK")
        assert r_star == pytest.approx(0.005)
        assert is_proxy is True

    def test_jp_direct_with_proxy_flag(self) -> None:
        """JP has its own entry marked ``proxy: true`` (BoJ QQE-era estimate)."""
        r_star, is_proxy = resolve_r_star("JP")
        assert r_star == pytest.approx(0.000)
        assert is_proxy is True

    def test_jp_entry_has_source_metadata(self) -> None:
        values = load_r_star_values()
        jp = values["JP"]
        assert "source" in jp
        assert "BoJ" in str(jp["source"])
        assert jp.get("proxy") is True

    def test_ca_direct_with_proxy_flag(self) -> None:
        """CA has its own entry marked ``proxy: true`` (BoC Staff 2024 estimate)."""
        r_star, is_proxy = resolve_r_star("CA")
        assert r_star == pytest.approx(0.0075)
        assert is_proxy is True

    def test_ca_entry_has_source_metadata(self) -> None:
        values = load_r_star_values()
        ca = values["CA"]
        assert "source" in ca
        assert "BoC" in str(ca["source"])
        assert ca.get("proxy") is True


class TestBcTargetsLoader:
    def test_us_to_fed(self) -> None:
        assert resolve_inflation_target("US") == pytest.approx(0.02)

    def test_pt_to_ecb(self) -> None:
        assert resolve_inflation_target("PT") == pytest.approx(0.02)

    def test_au_to_rba(self) -> None:
        assert resolve_inflation_target("AU") == pytest.approx(0.025)

    def test_unknown_country_raises(self) -> None:
        with pytest.raises(KeyError, match="No inflation-target"):
            resolve_inflation_target("CN")  # CN intentionally absent

    def test_country_to_target_includes_t1(self) -> None:
        mapping = load_country_to_target()
        for c in ("US", "DE", "PT", "IT", "ES", "FR", "NL", "GB"):
            assert c in mapping

    def test_uk_alias_resolves_to_boe(self) -> None:
        """Legacy ``"UK"`` input routes to the GB → BoE entry."""
        assert resolve_inflation_target("UK") == pytest.approx(0.02)

    def test_gb_canonical_resolves_to_boe(self) -> None:
        assert resolve_inflation_target("GB") == pytest.approx(0.02)

    def test_jp_resolves_to_boj_target(self) -> None:
        """JP monetary inputs resolve to BoJ 2 % CPI target (post-2013)."""
        assert resolve_inflation_target("JP") == pytest.approx(0.02)
        assert load_country_to_target()["JP"] == "BoJ"

    def test_ca_resolves_to_boc_target(self) -> None:
        """CA monetary inputs resolve to BoC 2 % CPI target."""
        assert resolve_inflation_target("CA") == pytest.approx(0.02)
        assert load_country_to_target()["CA"] == "BoC"

    def test_targets_dict_six_central_banks(self) -> None:
        targets = load_bc_targets()
        assert {"Fed", "ECB", "BoE", "BoJ", "RBA", "BoC"} <= set(targets.keys())


class TestStaleness:
    def test_far_future_marks_stale(self) -> None:
        # Yaml last_updated 2025-01-15; 95 days later is 2025-04-20.
        assert is_r_star_stale("US", date(2025, 5, 1)) is True
        assert is_r_star_stale("US", date(2026, 4, 20)) is True

    def test_recent_not_stale(self) -> None:
        assert is_r_star_stale("US", date(2025, 1, 20)) is False

    def test_proxy_country_uses_ea_timestamp(self) -> None:
        assert is_r_star_stale("PT", date(2026, 4, 20)) is True

    def test_staleness_threshold_constant(self) -> None:
        assert R_STAR_STALENESS_DAYS == 95


class TestEaProxySet:
    def test_periphery_in_proxy_set(self) -> None:
        assert {"PT", "IT", "ES", "FR", "NL", "DE", "IE"} <= EA_PROXY_COUNTRIES

    def test_us_not_in_proxy_set(self) -> None:
        assert "US" not in EA_PROXY_COUNTRIES
