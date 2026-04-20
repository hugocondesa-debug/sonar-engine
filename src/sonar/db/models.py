"""SQLAlchemy 2.0 declarative models — NSS yield curve sibling tables.

Two table families coexist after migration 002:

- Week 1 (migration 001): ``yield_curves_{raw,params,fitted,metadata}`` —
  legacy bps-encoded persistence; orphaned by Day 3 AM but not yet dropped.
- Spec §8 (migration 002): ``yield_curves_{spot,zero,forwards,real}`` —
  the canonical NSS persistence layer; values stored in decimal per
  units.md, joined via ``fit_id`` UUID.

Mantém sync manual (não usamos autogenerate em Phase 1); alterações
requerem migration explícita + models edit.

Note: ``date_t`` is an alias for ``datetime.date`` to avoid name clash
with class attributes whose column name is also ``date``.
"""

from datetime import date as date_t, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class YieldCurveRaw(Base):
    __tablename__ = "yield_curves_raw"

    id: Mapped[int] = mapped_column(primary_key=True)
    country_code: Mapped[str] = mapped_column(String(2))
    observation_date: Mapped[date_t] = mapped_column(Date)
    tenor_years: Mapped[Decimal] = mapped_column(Numeric(6, 3))
    yield_bps: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(50))
    source_series_id: Mapped[str | None] = mapped_column(String(100))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class YieldCurveParams(Base):
    __tablename__ = "yield_curves_params"

    id: Mapped[int] = mapped_column(primary_key=True)
    country_code: Mapped[str] = mapped_column(String(2))
    observation_date: Mapped[date_t] = mapped_column(Date)
    beta0: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    beta1: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    beta2: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    beta3: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    tau1: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    tau2: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    rmse_bps: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    n_observations: Mapped[int] = mapped_column(Integer)
    methodology_version: Mapped[str] = mapped_column(String(10))
    flags_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    fitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class YieldCurveFitted(Base):
    __tablename__ = "yield_curves_fitted"

    id: Mapped[int] = mapped_column(primary_key=True)
    country_code: Mapped[str] = mapped_column(String(2))
    observation_date: Mapped[date_t] = mapped_column(Date)
    tenor_years: Mapped[Decimal] = mapped_column(Numeric(6, 3))
    fitted_yield_bps: Mapped[int] = mapped_column(Integer)
    methodology_version: Mapped[str] = mapped_column(String(10))


class YieldCurveMetadata(Base):
    __tablename__ = "yield_curves_metadata"

    id: Mapped[int] = mapped_column(primary_key=True)
    country_code: Mapped[str] = mapped_column(String(2))
    observation_date: Mapped[date_t] = mapped_column(Date)
    run_id: Mapped[str] = mapped_column(String(36))
    methodology_version: Mapped[str] = mapped_column(String(10))
    optimizer_status: Mapped[str | None] = mapped_column(String(20))
    optimizer_iterations: Mapped[int | None] = mapped_column(Integer)
    input_sources_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ---------------------------------------------------------------------------
# Spec §8 NSS sibling tables (migration 002). Values in decimal per units.md.
# ---------------------------------------------------------------------------


class NSSYieldCurveSpot(Base):
    __tablename__ = "yield_curves_spot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    fit_id: Mapped[str] = mapped_column(String(36), nullable=False)
    beta_0: Mapped[float] = mapped_column(Float, nullable=False)
    beta_1: Mapped[float] = mapped_column(Float, nullable=False)
    beta_2: Mapped[float] = mapped_column(Float, nullable=False)
    beta_3: Mapped[float | None] = mapped_column(Float, nullable=True)
    lambda_1: Mapped[float] = mapped_column(Float, nullable=False)
    lambda_2: Mapped[float | None] = mapped_column(Float, nullable=True)
    fitted_yields_json: Mapped[str] = mapped_column(Text, nullable=False)
    observations_used: Mapped[int] = mapped_column(Integer, nullable=False)
    rmse_bps: Mapped[float] = mapped_column(Float, nullable=False)
    xval_deviation_bps: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_connector: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_ycs_confidence"),
        UniqueConstraint(
            "country_code", "date", "methodology_version", name="uq_ycs_country_date_method"
        ),
        UniqueConstraint("fit_id", name="uq_ycs_fit_id"),
        Index("idx_ycs_cd", "country_code", "date"),
    )


class NSSYieldCurveZero(Base):
    __tablename__ = "yield_curves_zero"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    fit_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("yield_curves_spot.fit_id", ondelete="CASCADE", name="fk_ycz_fit_id"),
        nullable=False,
    )
    zero_rates_json: Mapped[str] = mapped_column(Text, nullable=False)
    derivation: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("derivation IN ('nss_derived', 'bootstrap')", name="ck_ycz_derivation"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_ycz_confidence"),
        UniqueConstraint(
            "country_code", "date", "methodology_version", name="uq_ycz_country_date_method"
        ),
        Index("idx_ycz_cd", "country_code", "date"),
        Index("idx_ycz_fitid", "fit_id"),
    )


class NSSYieldCurveForwards(Base):
    __tablename__ = "yield_curves_forwards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    fit_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("yield_curves_spot.fit_id", ondelete="CASCADE", name="fk_ycf_fit_id"),
        nullable=False,
    )
    forwards_json: Mapped[str] = mapped_column(Text, nullable=False)
    breakeven_forwards_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_ycf_confidence"),
        UniqueConstraint(
            "country_code", "date", "methodology_version", name="uq_ycf_country_date_method"
        ),
        Index("idx_ycf_cd", "country_code", "date"),
        Index("idx_ycf_fitid", "fit_id"),
    )


class NSSYieldCurveReal(Base):
    __tablename__ = "yield_curves_real"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    fit_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("yield_curves_spot.fit_id", ondelete="CASCADE", name="fk_ycr_fit_id"),
        nullable=False,
    )
    real_yields_json: Mapped[str] = mapped_column(Text, nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    linker_connector: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("method IN ('direct_linker', 'derived')", name="ck_ycr_method"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_ycr_confidence"),
        UniqueConstraint(
            "country_code", "date", "methodology_version", name="uq_ycr_country_date_method"
        ),
        Index("idx_ycr_cd", "country_code", "date"),
        Index("idx_ycr_fitid", "fit_id"),
    )


# ---------------------------------------------------------------------------
# Spec rating-spread §8 — migration 003. Storage per units.md §Spreads.
# ---------------------------------------------------------------------------


class RatingsAgencyRaw(Base):
    __tablename__ = "ratings_agency_raw"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rating_id: Mapped[str] = mapped_column(String(36), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    agency: Mapped[str] = mapped_column(String(8), nullable=False)
    rating_type: Mapped[str] = mapped_column(String(2), nullable=False)
    rating_raw: Mapped[str] = mapped_column(String(16), nullable=False)
    sonar_notch_base: Mapped[int] = mapped_column(Integer, nullable=False)
    outlook: Mapped[str] = mapped_column(String(16), nullable=False)
    watch: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notch_adjusted: Mapped[float] = mapped_column(Float, nullable=False)
    action_date: Mapped[date_t] = mapped_column(Date, nullable=False)
    source_connector: Mapped[str] = mapped_column(String(32), nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("agency IN ('SP','MOODYS','FITCH','DBRS')", name="ck_rar_agency"),
        CheckConstraint("rating_type IN ('FC','LC')", name="ck_rar_rating_type"),
        CheckConstraint("sonar_notch_base BETWEEN 0 AND 21", name="ck_rar_notch_base"),
        CheckConstraint(
            "outlook IN ('positive','stable','negative','developing')",
            name="ck_rar_outlook",
        ),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_rar_confidence"),
        UniqueConstraint(
            "country_code",
            "date",
            "agency",
            "rating_type",
            "methodology_version",
            name="uq_rar_cdarm",
        ),
        Index("idx_rar_cdt", "country_code", "date", "rating_type"),
        Index("idx_rar_rid", "rating_id"),
    )


class RatingsConsolidated(Base):
    __tablename__ = "ratings_consolidated"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rating_id: Mapped[str] = mapped_column(String(36), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    rating_type: Mapped[str] = mapped_column(String(2), nullable=False)
    consolidated_sonar_notch: Mapped[float] = mapped_column(Float, nullable=False)
    notch_fractional: Mapped[float] = mapped_column(Float, nullable=False)
    agencies_count: Mapped[int] = mapped_column(Integer, nullable=False)
    agencies_json: Mapped[str] = mapped_column(Text, nullable=False)
    outlook_composite: Mapped[str] = mapped_column(String(16), nullable=False)
    watch_composite: Mapped[str | None] = mapped_column(String(20), nullable=True)
    default_spread_bps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calibration_date: Mapped[date_t | None] = mapped_column(Date, nullable=True)
    rating_cds_deviation_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("rating_type IN ('FC','LC')", name="ck_rc_rating_type"),
        CheckConstraint("consolidated_sonar_notch BETWEEN 0 AND 21", name="ck_rc_notch"),
        CheckConstraint("agencies_count BETWEEN 0 AND 4", name="ck_rc_agencies_count"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_rc_confidence"),
        UniqueConstraint("rating_id", name="uq_rc_rating_id"),
        UniqueConstraint(
            "country_code",
            "date",
            "rating_type",
            "methodology_version",
            name="uq_rc_cdrm",
        ),
        Index("idx_rc_cdt", "country_code", "date", "rating_type"),
    )


class CostOfCapitalDaily(Base):
    __tablename__ = "cost_of_capital_daily"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    rf_local_pct: Mapped[float] = mapped_column(Float, nullable=False)
    erp_mature_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    crp_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    beta: Mapped[float] = mapped_column(Float, nullable=False)
    k_e_pct: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_kc_confidence"),
        CheckConstraint("beta > 0", name="ck_kc_beta"),
        UniqueConstraint("country_code", "date", "methodology_version", name="uq_kc_cdm"),
        Index("idx_kc_cd", "country_code", "date"),
    )


class RatingsSpreadCalibration(Base):
    __tablename__ = "ratings_spread_calibration"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    calibration_date: Mapped[date_t] = mapped_column(Date, nullable=False)
    sonar_notch_int: Mapped[int] = mapped_column(Integer, nullable=False)
    rating_equivalent: Mapped[str] = mapped_column(String(8), nullable=False)
    default_spread_bps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    range_low_bps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    range_high_bps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    moodys_pd_5y_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    calibration_source: Mapped[str] = mapped_column(String(64), nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("sonar_notch_int BETWEEN 0 AND 21", name="ck_rsc_notch"),
        UniqueConstraint(
            "calibration_date", "sonar_notch_int", "methodology_version", name="uq_rsc_dnm"
        ),
        Index("idx_rsc_notch", "sonar_notch_int", "calibration_date"),
    )


# === ERP models begin ===
# Spec docs/specs/overlays/erp-daily.md §8. Decimal storage per units.md;
# *_bps columns integer per units.md §Spreads.


class ERPDCF(Base):
    __tablename__ = "erp_dcf"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    erp_id: Mapped[str] = mapped_column(String(36), nullable=False)
    market_index: Mapped[str] = mapped_column(String(16), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    erp_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    implied_r_pct: Mapped[float] = mapped_column(Float, nullable=False)
    earnings_growth_pct: Mapped[float] = mapped_column(Float, nullable=False)
    terminal_growth_pct: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_erp_dcf_confidence"),
        UniqueConstraint("market_index", "date", "methodology_version", name="uq_erp_dcf_mdm"),
        Index("idx_erp_dcf_md", "market_index", "date"),
    )


class ERPGordon(Base):
    __tablename__ = "erp_gordon"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    erp_id: Mapped[str] = mapped_column(String(36), nullable=False)
    market_index: Mapped[str] = mapped_column(String(16), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    erp_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    dividend_yield_pct: Mapped[float] = mapped_column(Float, nullable=False)
    buyback_yield_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    g_sustainable_pct: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_erp_gordon_confidence"),
        UniqueConstraint("market_index", "date", "methodology_version", name="uq_erp_gordon_mdm"),
        Index("idx_erp_gordon_md", "market_index", "date"),
    )


class ERPEY(Base):
    __tablename__ = "erp_ey"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    erp_id: Mapped[str] = mapped_column(String(36), nullable=False)
    market_index: Mapped[str] = mapped_column(String(16), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    erp_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    forward_pe: Mapped[float] = mapped_column(Float, nullable=False)
    forward_earnings: Mapped[float] = mapped_column(Float, nullable=False)
    index_level: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_erp_ey_confidence"),
        UniqueConstraint("market_index", "date", "methodology_version", name="uq_erp_ey_mdm"),
        Index("idx_erp_ey_md", "market_index", "date"),
    )


class ERPCAPE(Base):
    __tablename__ = "erp_cape"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    erp_id: Mapped[str] = mapped_column(String(36), nullable=False)
    market_index: Mapped[str] = mapped_column(String(16), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    erp_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    cape_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    real_risk_free_pct: Mapped[float] = mapped_column(Float, nullable=False)
    real_earnings_10y_avg: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_erp_cape_confidence"),
        UniqueConstraint("market_index", "date", "methodology_version", name="uq_erp_cape_mdm"),
        Index("idx_erp_cape_md", "market_index", "date"),
    )


class ERPCanonical(Base):
    __tablename__ = "erp_canonical"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    erp_id: Mapped[str] = mapped_column(String(36), nullable=False)
    market_index: Mapped[str] = mapped_column(String(16), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    erp_median_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    erp_range_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    methods_available: Mapped[int] = mapped_column(Integer, nullable=False)
    erp_dcf_bps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    erp_gordon_bps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    erp_ey_bps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    erp_cape_bps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    forward_eps_divergence_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    xval_deviation_bps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_erp_canonical_confidence"),
        CheckConstraint("methods_available BETWEEN 1 AND 4", name="ck_erp_canonical_methods"),
        UniqueConstraint("erp_id", name="uq_erp_canonical_erp_id"),
        UniqueConstraint(
            "market_index", "date", "methodology_version", name="uq_erp_canonical_mdm"
        ),
        Index("idx_erp_canonical_md", "market_index", "date"),
    )


# === ERP models end ===


# === Indices models begin ===
# Reserved for parallel L3 indices brief. Do not append ERP models below this
# bookmark; do not modify beyond appending new Indices ORM classes inside.
# Spec docs/specs/indices/. Migration 008 — single polymorphic table per
# SESSION_CONTEXT §Distinção crítica (one row per index_code+country+date+method).


class IndexValue(Base):
    __tablename__ = "index_values"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    index_code: Mapped[str] = mapped_column(String(16), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_value: Mapped[float] = mapped_column(Float, nullable=False)
    zscore_clamped: Mapped[float] = mapped_column(Float, nullable=False)
    value_0_100: Mapped[float] = mapped_column(Float, nullable=False)
    sub_indicators_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_overlays_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("value_0_100 BETWEEN 0 AND 100", name="ck_iv_value_range"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_iv_confidence"),
        UniqueConstraint(
            "index_code",
            "country_code",
            "date",
            "methodology_version",
            name="uq_iv_codecdm",
        ),
        Index("idx_iv_code_cd", "index_code", "country_code", "date"),
        Index("idx_iv_cd", "country_code", "date"),
    )


# Credit L1-L4 dedicated tables per docs/specs/indices/credit/<L>-*.md §8.
# Migration 009. NOT polymorphic index_values — CCCS sub-indices have
# substantially different extra columns (L4 has 11 extras incl.
# annuity_factor + formula_mode + band + denominator).


class CreditGdpStock(Base):
    __tablename__ = "credit_to_gdp_stock"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    score_normalized: Mapped[float] = mapped_column(Float, nullable=False)
    score_raw: Mapped[float] = mapped_column(Float, nullable=False)
    components_json: Mapped[str] = mapped_column(Text, nullable=False)
    series_variant: Mapped[str] = mapped_column(String(2), nullable=False)
    gdp_vintage_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    lookback_years: Mapped[int] = mapped_column(Integer, nullable=False)
    structural_band: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_connector: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("series_variant IN ('Q', 'F')", name="ck_l1_cgs_series_variant"),
        CheckConstraint(
            "gdp_vintage_mode IN ('production', 'backtest')", name="ck_l1_cgs_vintage_mode"
        ),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_l1_cgs_confidence"),
        UniqueConstraint("country_code", "date", "methodology_version", name="uq_l1_cgs_cdm"),
        Index("idx_l1_cgs_cd", "country_code", "date"),
    )


class CreditGdpGap(Base):
    __tablename__ = "credit_to_gdp_gap"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    score_normalized: Mapped[float] = mapped_column(Float, nullable=False)
    score_raw: Mapped[float] = mapped_column(Float, nullable=False)
    gap_hp_pp: Mapped[float] = mapped_column(Float, nullable=False)
    gap_hamilton_pp: Mapped[float] = mapped_column(Float, nullable=False)
    trend_gdp_pct: Mapped[float] = mapped_column(Float, nullable=False)
    hp_lambda: Mapped[int] = mapped_column(Integer, nullable=False, server_default="400000")
    hamilton_horizon_q: Mapped[int] = mapped_column(Integer, nullable=False, server_default="8")
    concordance: Mapped[str] = mapped_column(String(16), nullable=False)
    phase_band: Mapped[str] = mapped_column(String(16), nullable=False)
    components_json: Mapped[str] = mapped_column(Text, nullable=False)
    lookback_years: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_connector: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "concordance IN ('both_above','both_below','divergent')",
            name="ck_l2_cgg_concordance",
        ),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_l2_cgg_confidence"),
        UniqueConstraint("country_code", "date", "methodology_version", name="uq_l2_cgg_cdm"),
        Index("idx_l2_cgg_cd", "country_code", "date"),
    )


class CreditImpulse(Base):
    __tablename__ = "credit_impulse"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    segment: Mapped[str] = mapped_column(String(4), nullable=False)
    score_normalized: Mapped[float] = mapped_column(Float, nullable=False)
    score_raw: Mapped[float] = mapped_column(Float, nullable=False)
    impulse_pp: Mapped[float] = mapped_column(Float, nullable=False)
    flow_t_lcu: Mapped[float] = mapped_column(Float, nullable=False)
    flow_t_minus4_lcu: Mapped[float] = mapped_column(Float, nullable=False)
    delta_flow_lcu: Mapped[float] = mapped_column(Float, nullable=False)
    gdp_t_minus4_lcu: Mapped[float] = mapped_column(Float, nullable=False)
    series_variant: Mapped[str] = mapped_column(String(2), nullable=False)
    smoothing: Mapped[str] = mapped_column(String(4), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    components_json: Mapped[str] = mapped_column(Text, nullable=False)
    lookback_years: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_connector: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("segment IN ('PNFS','HH','NFC')", name="ck_l3_ci_segment"),
        CheckConstraint("series_variant IN ('Q','F')", name="ck_l3_ci_series_variant"),
        CheckConstraint("smoothing IN ('raw','ma4')", name="ck_l3_ci_smoothing"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_l3_ci_confidence"),
        UniqueConstraint(
            "country_code",
            "date",
            "methodology_version",
            "segment",
            name="uq_l3_ci_cdms",
        ),
        Index("idx_l3_ci_cd", "country_code", "date"),
    )


class Dsr(Base):
    __tablename__ = "dsr"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    segment: Mapped[str] = mapped_column(String(4), nullable=False)
    score_normalized: Mapped[float] = mapped_column(Float, nullable=False)
    score_raw: Mapped[float] = mapped_column(Float, nullable=False)
    dsr_pct: Mapped[float] = mapped_column(Float, nullable=False)
    dsr_deviation_pp: Mapped[float] = mapped_column(Float, nullable=False)
    lending_rate_pct: Mapped[float] = mapped_column(Float, nullable=False)
    avg_maturity_years: Mapped[float] = mapped_column(Float, nullable=False)
    debt_to_gdp_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    annuity_factor: Mapped[float] = mapped_column(Float, nullable=False)
    formula_mode: Mapped[str] = mapped_column(String(4), nullable=False)
    band: Mapped[str] = mapped_column(String(16), nullable=False)
    denominator: Mapped[str] = mapped_column(String(32), nullable=False)
    components_json: Mapped[str] = mapped_column(Text, nullable=False)
    lookback_years: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_connector: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("segment IN ('PNFS','HH','NFC')", name="ck_l4_dsr_segment"),
        CheckConstraint("formula_mode IN ('full','o2','o1')", name="ck_l4_dsr_formula_mode"),
        CheckConstraint("band IN ('baseline','alert','critical')", name="ck_l4_dsr_band"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_l4_dsr_confidence"),
        UniqueConstraint(
            "country_code",
            "date",
            "methodology_version",
            "segment",
            name="uq_l4_dsr_cdms",
        ),
        Index("idx_l4_dsr_cd", "country_code", "date"),
    )


# === Indices models end ===


# === Ingestion models begin ===
# L0 data-ingestion bookmark zone for raw external-provider observations
# cached between a connector fetch and downstream index / overlay compute.
# Keeps raw data traceable (per-response hash) and re-computable without
# re-hitting providers.  Do NOT append non-ingestion models below this
# bookmark.


class BisCreditRaw(Base):
    """Raw quarterly observations from BIS credit-side dataflows.

    One row per ``(country_code, date, dataflow)`` triplet. ``value_raw``
    units depend on ``dataflow`` and are captured verbatim in
    ``unit_descriptor`` for audit. Downstream credit indices consume
    these observations via ``DbBackedInputsBuilder`` (see
    ``sonar.pipelines.daily_credit_indices``).
    """

    __tablename__ = "bis_credit_raw"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    dataflow: Mapped[str] = mapped_column(String(16), nullable=False)
    value_raw: Mapped[float] = mapped_column(Float, nullable=False)
    unit_descriptor: Mapped[str] = mapped_column(String(32), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )
    fetch_response_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "dataflow IN ('WS_TC','WS_DSR','WS_CREDIT_GAP')",
            name="ck_bcr_dataflow",
        ),
        UniqueConstraint("country_code", "date", "dataflow", name="uq_bcr_cdd"),
        Index("idx_bcr_cd", "country_code", "date"),
    )


# === Ingestion models end ===
