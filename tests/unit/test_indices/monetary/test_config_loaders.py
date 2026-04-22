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

    def test_au_direct_with_proxy_flag(self) -> None:
        """AU has its own entry marked ``proxy: true`` (RBA SMP Feb 2025 estimate)."""
        r_star, is_proxy = resolve_r_star("AU")
        assert r_star == pytest.approx(0.0075)
        assert is_proxy is True

    def test_au_entry_has_source_metadata(self) -> None:
        values = load_r_star_values()
        au = values["AU"]
        assert "source" in au
        assert "RBA" in str(au["source"])
        assert au.get("proxy") is True

    def test_nz_direct_with_proxy_flag(self) -> None:
        """NZ has its own entry marked ``proxy: true`` (RBNZ Bulletin 2023-2024 estimate)."""
        r_star, is_proxy = resolve_r_star("NZ")
        assert r_star == pytest.approx(0.0175)
        assert is_proxy is True

    def test_nz_entry_has_source_metadata(self) -> None:
        values = load_r_star_values()
        nz = values["NZ"]
        assert "source" in nz
        assert "RBNZ" in str(nz["source"])
        assert nz.get("proxy") is True

    def test_ch_direct_with_proxy_flag(self) -> None:
        """CH has its own entry marked ``proxy: true`` — Swiss r* is
        structurally low (CHF safe-haven compression). Value anchored
        to SNB WP 2024-09 posterior median (0.25 % real)."""
        r_star, is_proxy = resolve_r_star("CH")
        assert r_star == pytest.approx(0.0025)
        assert is_proxy is True

    def test_ch_entry_has_source_metadata(self) -> None:
        values = load_r_star_values()
        ch = values["CH"]
        assert "source" in ch
        assert "SNB" in str(ch["source"])
        assert ch.get("proxy") is True

    def test_no_direct_with_proxy_flag(self) -> None:
        """NO has its own entry marked ``proxy: true`` — Norges Bank does
        not publish an HLW-equivalent. Value anchored to Norges Bank
        MPR 1/2024 + Staff Memo 7/2023 neutral-range mid (1.25 % real)."""
        r_star, is_proxy = resolve_r_star("NO")
        assert r_star == pytest.approx(0.0125)
        assert is_proxy is True

    def test_no_entry_has_source_metadata(self) -> None:
        values = load_r_star_values()
        no = values["NO"]
        assert "source" in no
        assert "Norges Bank" in str(no["source"])
        assert no.get("proxy") is True

    def test_se_direct_with_proxy_flag(self) -> None:
        """SE has its own entry marked ``proxy: true`` — Swedish r*
        anchored at the Riksbank MPR March 2026 neutral-range midpoint
        (0.75 % real); Nordic low-r* cluster but above CH because SE
        lacks the CHF safe-haven compression."""
        r_star, is_proxy = resolve_r_star("SE")
        assert r_star == pytest.approx(0.0075)
        assert is_proxy is True

    def test_se_entry_has_source_metadata(self) -> None:
        values = load_r_star_values()
        se = values["SE"]
        assert "source" in se
        assert "Riksbank" in str(se["source"])
        assert se.get("proxy") is True


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

    def test_nz_resolves_to_rbnz_target(self) -> None:
        """NZ monetary inputs resolve to RBNZ 2 % midpoint of 1-3 % band."""
        assert resolve_inflation_target("NZ") == pytest.approx(0.02)
        assert load_country_to_target()["NZ"] == "RBNZ"

    def test_ch_resolves_to_snb_band_midpoint(self) -> None:
        """CH monetary inputs resolve to the SNB 0-2 % band midpoint (1 %).

        SNB defines price stability as CPI inflation below 2 % — the
        0-2 % band. The midpoint representation matches how AU's 2-3 %
        band surfaces at 2.5 % above. Downstream M1 CH emits
        ``CH_INFLATION_TARGET_BAND`` to flag the midpoint convention.
        """
        assert resolve_inflation_target("CH") == pytest.approx(0.01)
        assert load_country_to_target()["CH"] == "SNB"

    def test_no_resolves_to_norges_bank_target(self) -> None:
        """NO monetary inputs resolve to Norges Bank 2 % CPI target (post-2018).

        Target reduced from 2.5 % → 2.0 % on 2018-03-02 (Forskrift §2).
        The 2.0 % current value applies to all Sprint X-NO cadence
        points; pre-2018 backtesting work can swap the YAML value
        without touching resolver logic.
        """
        assert resolve_inflation_target("NO") == pytest.approx(0.02)
        assert load_country_to_target()["NO"] == "Norges Bank"

    def test_se_resolves_to_riksbank_target(self) -> None:
        """SE monetary inputs resolve to the Riksbank 2 % CPIF target
        (explicit point target since 1993; CPIF basis since 2017 to
        remove the mechanical impact of the policy rate on the target
        measure). Unlike CH's 0-2 % band, the Riksbank ships a clean
        point target — no SE-specific band flag is emitted.
        """
        assert resolve_inflation_target("SE") == pytest.approx(0.02)
        assert load_country_to_target()["SE"] == "Riksbank"

    def test_targets_dict_ten_central_banks(self) -> None:
        targets = load_bc_targets()
        assert {
            "Fed",
            "ECB",
            "BoE",
            "BoJ",
            "RBA",
            "BoC",
            "RBNZ",
            "SNB",
            "Norges Bank",
            "Riksbank",
        } <= set(targets.keys())


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
