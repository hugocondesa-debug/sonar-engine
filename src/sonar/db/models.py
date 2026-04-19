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
