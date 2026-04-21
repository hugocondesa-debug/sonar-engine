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


# F-cycle L3 indices tables per docs/specs/indices/financial/<F>-*.md §8.
# Migration 010. 4 indices: F1 Valuations, F2 Momentum, F3 Risk Appetite,
# F4 Positioning.


class FinancialValuations(Base):
    __tablename__ = "f1_valuations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    score_normalized: Mapped[float] = mapped_column(Float, nullable=False)
    score_raw: Mapped[float] = mapped_column(Float, nullable=False)
    components_json: Mapped[str] = mapped_column(Text, nullable=False)
    cape_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    erp_median_bps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    buffett_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    forward_pe: Mapped[float | None] = mapped_column(Float, nullable=True)
    property_gap_pp: Mapped[float | None] = mapped_column(Float, nullable=True)
    lookback_years: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_overlay: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("score_normalized BETWEEN 0 AND 100", name="ck_f1_score_range"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_f1_confidence"),
        UniqueConstraint("country_code", "date", "methodology_version", name="uq_f1_cdm"),
        Index("idx_f1_cd", "country_code", "date"),
    )


class FinancialMomentum(Base):
    __tablename__ = "f2_momentum"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    score_normalized: Mapped[float] = mapped_column(Float, nullable=False)
    score_raw: Mapped[float] = mapped_column(Float, nullable=False)
    components_json: Mapped[str] = mapped_column(Text, nullable=False)
    mom_3m_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    mom_6m_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    mom_12m_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    breadth_above_ma200_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    cross_asset_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    primary_index: Mapped[str] = mapped_column(String(16), nullable=False)
    lookback_years: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("score_normalized BETWEEN 0 AND 100", name="ck_f2_score_range"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_f2_confidence"),
        UniqueConstraint("country_code", "date", "methodology_version", name="uq_f2_cdm"),
        Index("idx_f2_cd", "country_code", "date"),
    )


class FinancialRiskAppetite(Base):
    __tablename__ = "f3_risk_appetite"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    score_normalized: Mapped[float] = mapped_column(Float, nullable=False)
    score_raw: Mapped[float] = mapped_column(Float, nullable=False)
    components_json: Mapped[str] = mapped_column(Text, nullable=False)
    vix_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    move_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    credit_spread_hy_bps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    credit_spread_ig_bps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fci_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    crypto_vol_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    components_available: Mapped[int] = mapped_column(Integer, nullable=False)
    lookback_years: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("score_normalized BETWEEN 0 AND 100", name="ck_f3_score_range"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_f3_confidence"),
        CheckConstraint("components_available BETWEEN 3 AND 5", name="ck_f3_components_available"),
        UniqueConstraint("country_code", "date", "methodology_version", name="uq_f3_cdm"),
        Index("idx_f3_cd", "country_code", "date"),
    )


class FinancialPositioning(Base):
    __tablename__ = "f4_positioning"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    score_normalized: Mapped[float] = mapped_column(Float, nullable=False)
    score_raw: Mapped[float] = mapped_column(Float, nullable=False)
    components_json: Mapped[str] = mapped_column(Text, nullable=False)
    aaii_bull_minus_bear_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    put_call_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    cot_noncomm_net_sp500: Mapped[int | None] = mapped_column(Integer, nullable=True)
    margin_debt_gdp_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    ipo_activity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    components_available: Mapped[int] = mapped_column(Integer, nullable=False)
    lookback_years: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("score_normalized BETWEEN 0 AND 100", name="ck_f4_score_range"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_f4_confidence"),
        CheckConstraint("components_available BETWEEN 2 AND 5", name="ck_f4_components_available"),
        UniqueConstraint("country_code", "date", "methodology_version", name="uq_f4_cdm"),
        Index("idx_f4_cd", "country_code", "date"),
    )


class E1Activity(Base):
    """Row per spec ``E1-activity.md`` §8 — coincident activity index."""

    __tablename__ = "idx_economic_e1_activity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    score_normalized: Mapped[float] = mapped_column(Float, nullable=False)
    score_raw: Mapped[float] = mapped_column(Float, nullable=False)
    components_json: Mapped[str] = mapped_column(Text, nullable=False)
    components_available: Mapped[int] = mapped_column(Integer, nullable=False)
    lookback_years: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_connectors: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("score_normalized BETWEEN 0 AND 100", name="ck_e1_score_normalized"),
        CheckConstraint("components_available BETWEEN 4 AND 6", name="ck_e1_components_available"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_e1_confidence"),
        UniqueConstraint("country_code", "date", "methodology_version", name="uq_e1_cdm"),
        Index("idx_e1_cd", "country_code", "date"),
    )


class E3Labor(Base):
    """Row per spec ``E3-labor.md`` §8 — labor market depth index."""

    __tablename__ = "idx_economic_e3_labor"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    score_normalized: Mapped[float] = mapped_column(Float, nullable=False)
    score_raw: Mapped[float] = mapped_column(Float, nullable=False)
    sahm_triggered: Mapped[int] = mapped_column(Integer, nullable=False)
    sahm_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    components_json: Mapped[str] = mapped_column(Text, nullable=False)
    components_available: Mapped[int] = mapped_column(Integer, nullable=False)
    lookback_years: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_connectors: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("score_normalized BETWEEN 0 AND 100", name="ck_e3_score_normalized"),
        CheckConstraint("sahm_triggered IN (0, 1)", name="ck_e3_sahm_triggered"),
        CheckConstraint("components_available BETWEEN 6 AND 10", name="ck_e3_components_available"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_e3_confidence"),
        UniqueConstraint("country_code", "date", "methodology_version", name="uq_e3_cdm"),
        Index("idx_e3_cd", "country_code", "date"),
        Index("idx_e3_sahm", "country_code", "sahm_triggered", "date"),
    )


class E4Sentiment(Base):
    """Row per spec ``E4-sentiment.md`` §8 — sentiment + expectations index."""

    __tablename__ = "idx_economic_e4_sentiment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    score_normalized: Mapped[float] = mapped_column(Float, nullable=False)
    score_raw: Mapped[float] = mapped_column(Float, nullable=False)
    components_json: Mapped[str] = mapped_column(Text, nullable=False)
    components_available: Mapped[int] = mapped_column(Integer, nullable=False)
    lookback_years: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_connectors: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("score_normalized BETWEEN 0 AND 100", name="ck_e4_score_normalized"),
        CheckConstraint("components_available BETWEEN 6 AND 13", name="ck_e4_components_available"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_e4_confidence"),
        UniqueConstraint("country_code", "date", "methodology_version", name="uq_e4_cdm"),
        Index("idx_e4_cd", "country_code", "date"),
    )


class M1EffectiveRatesResult(Base):
    """Row per spec ``M1-effective-rates.md`` §8 — monetary effective rates index."""

    __tablename__ = "monetary_m1_effective_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    score_normalized: Mapped[float] = mapped_column(Float, nullable=False)
    score_raw: Mapped[float] = mapped_column(Float, nullable=False)
    policy_rate_pct: Mapped[float] = mapped_column(Float, nullable=False)
    shadow_rate_pct: Mapped[float] = mapped_column(Float, nullable=False)
    real_rate_pct: Mapped[float] = mapped_column(Float, nullable=False)
    r_star_pct: Mapped[float] = mapped_column(Float, nullable=False)
    components_json: Mapped[str] = mapped_column(Text, nullable=False)
    lookback_years: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_connector: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("score_normalized BETWEEN 0 AND 100", name="ck_m1_score_normalized"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_m1_confidence"),
        UniqueConstraint("country_code", "date", "methodology_version", name="uq_m1_cdm"),
        Index("idx_m1_cd", "country_code", "date"),
    )


class M2TaylorGapsResult(Base):
    """Row per spec ``M2-taylor-gaps.md`` §8 — Taylor-rule gap index."""

    __tablename__ = "monetary_m2_taylor_gaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    score_normalized: Mapped[float] = mapped_column(Float, nullable=False)
    score_raw: Mapped[float] = mapped_column(Float, nullable=False)
    taylor_implied_pct: Mapped[float] = mapped_column(Float, nullable=False)
    taylor_gap_pp: Mapped[float] = mapped_column(Float, nullable=False)
    taylor_uncertainty_pp: Mapped[float] = mapped_column(Float, nullable=False)
    r_star_source: Mapped[str] = mapped_column(String(32), nullable=False)
    output_gap_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    variants_computed: Mapped[int] = mapped_column(Integer, nullable=False)
    components_json: Mapped[str] = mapped_column(Text, nullable=False)
    lookback_years: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_connector: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("score_normalized BETWEEN 0 AND 100", name="ck_m2_score_normalized"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_m2_confidence"),
        CheckConstraint("variants_computed BETWEEN 1 AND 4", name="ck_m2_variants_computed"),
        UniqueConstraint("country_code", "date", "methodology_version", name="uq_m2_cdm"),
        Index("idx_m2_cd", "country_code", "date"),
    )


class M4FciResult(Base):
    """Row per spec ``M4-fci.md`` §8 — financial conditions index."""

    __tablename__ = "monetary_m4_fci"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    score_normalized: Mapped[float] = mapped_column(Float, nullable=False)
    score_raw: Mapped[float] = mapped_column(Float, nullable=False)
    fci_level: Mapped[float] = mapped_column(Float, nullable=False)
    fci_change_12m: Mapped[float | None] = mapped_column(Float, nullable=True)
    fci_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    components_available: Mapped[int] = mapped_column(Integer, nullable=False)
    fci_components_json: Mapped[str] = mapped_column(Text, nullable=False)
    lookback_years: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_connector: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("score_normalized BETWEEN 0 AND 100", name="ck_m4_score_normalized"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_m4_confidence"),
        CheckConstraint(
            "fci_provider IN ('NFCI_CHICAGO','CUSTOM_SONAR','IMF_GFSR')",
            name="ck_m4_fci_provider",
        ),
        CheckConstraint("components_available BETWEEN 1 AND 7", name="ck_m4_components_available"),
        UniqueConstraint("country_code", "date", "methodology_version", name="uq_m4_cdm"),
        Index("idx_m4_cd", "country_code", "date"),
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


# === Cycle models begin ===
# L4 cycle composite bookmark zone (CCCS, FCS from Sprint 2b; ECS, MSC
# follow). One ORM per cycle — composites carry per-cycle-specific
# columns (hysteresis, overlay, audit contributions) so keep rich.


class CreditCycleScore(Base):
    """Row per spec ``cycles/credit-cccs.md`` §8 — L4 credit composite."""

    __tablename__ = "credit_cycle_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cccs_id: Mapped[str] = mapped_column(String(36), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    score_0_100: Mapped[float] = mapped_column(Float, nullable=False)
    regime: Mapped[str] = mapped_column(String(16), nullable=False)
    regime_persistence_days: Mapped[int] = mapped_column(Integer, nullable=False)
    cs_score_0_100: Mapped[float | None] = mapped_column(Float, nullable=True)
    lc_score_0_100: Mapped[float | None] = mapped_column(Float, nullable=True)
    ms_score_0_100: Mapped[float | None] = mapped_column(Float, nullable=True)
    qs_score_0_100: Mapped[float | None] = mapped_column(Float, nullable=True)
    cs_weight_effective: Mapped[float] = mapped_column(Float, nullable=False)
    lc_weight_effective: Mapped[float] = mapped_column(Float, nullable=False)
    ms_weight_effective: Mapped[float] = mapped_column(Float, nullable=False)
    components_available: Mapped[int] = mapped_column(Integer, nullable=False)
    l1_contribution_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    l2_contribution_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    l3_contribution_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    l4_contribution_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    f3_contribution_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    f4_margin_debt_contribution_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    boom_overlay_active: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    boom_trigger_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("cccs_id", name="uq_cccs_id"),
        CheckConstraint("score_0_100 BETWEEN 0 AND 100", name="ck_cccs_score"),
        CheckConstraint(
            "regime IN ('REPAIR','RECOVERY','BOOM','SPECULATION','DISTRESS')",
            name="ck_cccs_regime",
        ),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_cccs_confidence"),
        CheckConstraint(
            "components_available BETWEEN 3 AND 4", name="ck_cccs_components_available"
        ),
        CheckConstraint("boom_overlay_active IN (0, 1)", name="ck_cccs_boom_overlay_active"),
        UniqueConstraint("country_code", "date", "methodology_version", name="uq_cccs_cdm"),
        Index("idx_cccs_cd", "country_code", "date"),
    )


class FinancialCycleScore(Base):
    """Row per spec ``cycles/financial-fcs.md`` §8 — L4 financial composite."""

    __tablename__ = "financial_cycle_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fcs_id: Mapped[str] = mapped_column(String(36), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    score_0_100: Mapped[float] = mapped_column(Float, nullable=False)
    regime: Mapped[str] = mapped_column(String(16), nullable=False)
    regime_persistence_days: Mapped[int] = mapped_column(Integer, nullable=False)
    f1_score_0_100: Mapped[float | None] = mapped_column(Float, nullable=True)
    f2_score_0_100: Mapped[float | None] = mapped_column(Float, nullable=True)
    f3_score_0_100: Mapped[float | None] = mapped_column(Float, nullable=True)
    f4_score_0_100: Mapped[float | None] = mapped_column(Float, nullable=True)
    f1_weight_effective: Mapped[float] = mapped_column(Float, nullable=False)
    f2_weight_effective: Mapped[float] = mapped_column(Float, nullable=False)
    f3_weight_effective: Mapped[float] = mapped_column(Float, nullable=False)
    f4_weight_effective: Mapped[float | None] = mapped_column(Float, nullable=True)
    indices_available: Mapped[int] = mapped_column(Integer, nullable=False)
    country_tier: Mapped[int] = mapped_column(Integer, nullable=False)
    f3_m4_divergence: Mapped[float | None] = mapped_column(Float, nullable=True)
    bubble_warning_active: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bubble_warning_components_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("fcs_id", name="uq_fcs_id"),
        CheckConstraint("score_0_100 BETWEEN 0 AND 100", name="ck_fcs_score"),
        CheckConstraint(
            "regime IN ('STRESS','CAUTION','OPTIMISM','EUPHORIA')", name="ck_fcs_regime"
        ),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_fcs_confidence"),
        CheckConstraint("indices_available BETWEEN 3 AND 4", name="ck_fcs_indices_available"),
        CheckConstraint("country_tier BETWEEN 1 AND 4", name="ck_fcs_country_tier"),
        CheckConstraint("bubble_warning_active IN (0, 1)", name="ck_fcs_bubble_warning_active"),
        UniqueConstraint("country_code", "date", "methodology_version", name="uq_fcs_cdm"),
        Index("idx_fcs_cd", "country_code", "date"),
    )


class MonetaryCycleScore(Base):
    """Row per spec ``cycles/monetary-msc.md`` §8 — L4 monetary composite.

    Composite of five sub-indices (M1 ES / M2 RD / M3 EP / M4 FC / CS)
    with canonical weights 0.30/0.15/0.25/0.20/0.10. Communication
    Signal (CS) is a Phase 2+ connector path; Phase 0-1 rows fire with
    ``COMM_SIGNAL_MISSING`` flag and re-weighted four inputs. See spec
    §4 algorithm + §8 storage schema.
    """

    __tablename__ = "monetary_cycle_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    msc_id: Mapped[str] = mapped_column(String(36), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    score_0_100: Mapped[float] = mapped_column(Float, nullable=False)
    regime_6band: Mapped[str] = mapped_column(String(32), nullable=False)
    regime_3band: Mapped[str] = mapped_column(String(16), nullable=False)
    regime_persistence_days: Mapped[int] = mapped_column(Integer, nullable=False)
    m1_score_0_100: Mapped[float | None] = mapped_column(Float, nullable=True)
    m2_score_0_100: Mapped[float | None] = mapped_column(Float, nullable=True)
    m3_score_0_100: Mapped[float | None] = mapped_column(Float, nullable=True)
    m4_score_0_100: Mapped[float | None] = mapped_column(Float, nullable=True)
    cs_score_0_100: Mapped[float | None] = mapped_column(Float, nullable=True)
    m1_weight_effective: Mapped[float] = mapped_column(Float, nullable=False)
    m2_weight_effective: Mapped[float] = mapped_column(Float, nullable=False)
    m3_weight_effective: Mapped[float] = mapped_column(Float, nullable=False)
    m4_weight_effective: Mapped[float] = mapped_column(Float, nullable=False)
    cs_weight_effective: Mapped[float] = mapped_column(Float, nullable=False)
    inputs_available: Mapped[int] = mapped_column(Integer, nullable=False)
    cs_hawkish_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    fed_dissent_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dot_plot_drift_bps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dilemma_overlay_active: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dilemma_trigger_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("msc_id", name="uq_msc_id"),
        CheckConstraint("score_0_100 BETWEEN 0 AND 100", name="ck_msc_score"),
        CheckConstraint(
            "regime_6band IN ('STRONGLY_ACCOMMODATIVE','ACCOMMODATIVE',"
            "'NEUTRAL_ACCOMMODATIVE','NEUTRAL_TIGHT','TIGHT','STRONGLY_TIGHT')",
            name="ck_msc_regime_6band",
        ),
        CheckConstraint(
            "regime_3band IN ('ACCOMMODATIVE','NEUTRAL','TIGHT')",
            name="ck_msc_regime_3band",
        ),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_msc_confidence"),
        CheckConstraint("inputs_available BETWEEN 3 AND 5", name="ck_msc_inputs_available"),
        CheckConstraint("dilemma_overlay_active IN (0, 1)", name="ck_msc_dilemma_overlay_active"),
        UniqueConstraint("country_code", "date", "methodology_version", name="uq_msc_cdm"),
        Index("idx_msc_cd", "country_code", "date"),
    )


class EconomicCycleScore(Base):
    """Row per spec ``cycles/economic-ecs.md`` §8 — L4 economic composite.

    Aggregates E1 (Activity) + E2 (Leading) + E3 (Labor) + E4 (Sentiment)
    into a single 0-100 score with canonical weights 0.35/0.25/0.25/0.15.
    Policy 1 re-weight when any sub-index is unavailable; ≥ 3 of 4
    required. Hysteresis-aware 4-state regime classification
    (EXPANSION / PEAK_ZONE / EARLY_RECESSION / RECESSION) with
    |Δscore| > 5 + 3-BD persistence gate. Stagflation overlay
    (Cap 16 Trigger A — score<55 + cpi_yoy>3% + labor weakness)
    persists as a separate column alongside the regime.
    """

    __tablename__ = "economic_cycle_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ecs_id: Mapped[str] = mapped_column(String(36), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    score_0_100: Mapped[float] = mapped_column(Float, nullable=False)
    regime: Mapped[str] = mapped_column(String(16), nullable=False)
    regime_persistence_days: Mapped[int] = mapped_column(Integer, nullable=False)
    e1_score_0_100: Mapped[float | None] = mapped_column(Float, nullable=True)
    e2_score_0_100: Mapped[float | None] = mapped_column(Float, nullable=True)
    e3_score_0_100: Mapped[float | None] = mapped_column(Float, nullable=True)
    e4_score_0_100: Mapped[float | None] = mapped_column(Float, nullable=True)
    e1_weight_effective: Mapped[float] = mapped_column(Float, nullable=False)
    e2_weight_effective: Mapped[float] = mapped_column(Float, nullable=False)
    e3_weight_effective: Mapped[float] = mapped_column(Float, nullable=False)
    e4_weight_effective: Mapped[float] = mapped_column(Float, nullable=False)
    indices_available: Mapped[int] = mapped_column(Integer, nullable=False)
    stagflation_overlay_active: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stagflation_trigger_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("ecs_id", name="uq_ecs_id"),
        CheckConstraint("score_0_100 BETWEEN 0 AND 100", name="ck_ecs_score"),
        CheckConstraint(
            "regime IN ('EXPANSION','PEAK_ZONE','EARLY_RECESSION','RECESSION')",
            name="ck_ecs_regime",
        ),
        CheckConstraint("regime_persistence_days >= 1", name="ck_ecs_regime_persistence_days"),
        CheckConstraint(
            "e1_score_0_100 IS NULL OR e1_score_0_100 BETWEEN 0 AND 100",
            name="ck_ecs_e1_score",
        ),
        CheckConstraint(
            "e2_score_0_100 IS NULL OR e2_score_0_100 BETWEEN 0 AND 100",
            name="ck_ecs_e2_score",
        ),
        CheckConstraint(
            "e3_score_0_100 IS NULL OR e3_score_0_100 BETWEEN 0 AND 100",
            name="ck_ecs_e3_score",
        ),
        CheckConstraint(
            "e4_score_0_100 IS NULL OR e4_score_0_100 BETWEEN 0 AND 100",
            name="ck_ecs_e4_score",
        ),
        CheckConstraint("e1_weight_effective BETWEEN 0 AND 1", name="ck_ecs_e1_weight_effective"),
        CheckConstraint("e2_weight_effective BETWEEN 0 AND 1", name="ck_ecs_e2_weight_effective"),
        CheckConstraint("e3_weight_effective BETWEEN 0 AND 1", name="ck_ecs_e3_weight_effective"),
        CheckConstraint("e4_weight_effective BETWEEN 0 AND 1", name="ck_ecs_e4_weight_effective"),
        CheckConstraint("indices_available BETWEEN 3 AND 4", name="ck_ecs_indices_available"),
        CheckConstraint(
            "stagflation_overlay_active IN (0, 1)",
            name="ck_ecs_stagflation_overlay_active",
        ),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_ecs_confidence"),
        UniqueConstraint("country_code", "date", "methodology_version", name="uq_ecs_cdm"),
        Index("idx_ecs_cd", "country_code", "date"),
        Index("idx_ecs_regime", "country_code", "regime", "date"),
    )


# === Cycle models end ===


# === L5 Regime models ===
# Spec: docs/specs/regimes/cross-cycle-meta-regimes.md §6. L5 consolidates
# the four L4 cycle composites into a single meta-regime label per
# (country, date). FKs to the 4 cycle PKs are nullable to accommodate
# Policy 1 ≥ 3/4 fail-mode. Migration 017 creates the table.


class L5MetaRegime(Base):
    """Row per spec ``regimes/cross-cycle-meta-regimes.md`` §6."""

    __tablename__ = "l5_meta_regimes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    l5_id: Mapped[str] = mapped_column(String(36), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    meta_regime: Mapped[str] = mapped_column(String(32), nullable=False)
    ecs_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("economic_cycle_scores.ecs_id", name="fk_l5_ecs_id"),
        nullable=True,
    )
    cccs_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("credit_cycle_scores.cccs_id", name="fk_l5_cccs_id"),
        nullable=True,
    )
    fcs_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("financial_cycle_scores.fcs_id", name="fk_l5_fcs_id"),
        nullable=True,
    )
    msc_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("monetary_cycle_scores.msc_id", name="fk_l5_msc_id"),
        nullable=True,
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    classification_reason: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("l5_id", name="uq_l5_id"),
        CheckConstraint(
            "meta_regime IN ('overheating','stagflation_risk','late_cycle_bubble',"
            "'recession_risk','soft_landing','unclassified')",
            name="ck_l5_meta_regime",
        ),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_l5_confidence"),
        UniqueConstraint("country_code", "date", "methodology_version", name="uq_l5_cdm"),
        Index("idx_l5_cd", "country_code", "date"),
        Index("idx_l5_regime", "country_code", "meta_regime", "date"),
    )


# === L5 Regime models end ===
