"""SQLAlchemy 2.0 declarative models — NSS yield curve sibling tables.

Schema mirror da migration alembic 001_nss_schema. Mantém sync manual
(não usamos autogenerate em Phase 1); alterações requerem migration
explícita + models edit.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, Date, DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class YieldCurveRaw(Base):
    __tablename__ = "yield_curves_raw"

    id: Mapped[int] = mapped_column(primary_key=True)
    country_code: Mapped[str] = mapped_column(String(3))
    observation_date: Mapped[date] = mapped_column(Date)
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
    country_code: Mapped[str] = mapped_column(String(3))
    observation_date: Mapped[date] = mapped_column(Date)
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
    country_code: Mapped[str] = mapped_column(String(3))
    observation_date: Mapped[date] = mapped_column(Date)
    tenor_years: Mapped[Decimal] = mapped_column(Numeric(6, 3))
    fitted_yield_bps: Mapped[int] = mapped_column(Integer)
    methodology_version: Mapped[str] = mapped_column(String(10))


class YieldCurveMetadata(Base):
    __tablename__ = "yield_curves_metadata"

    id: Mapped[int] = mapped_column(primary_key=True)
    country_code: Mapped[str] = mapped_column(String(3))
    observation_date: Mapped[date] = mapped_column(Date)
    run_id: Mapped[str] = mapped_column(String(36))
    methodology_version: Mapped[str] = mapped_column(String(10))
    optimizer_status: Mapped[str | None] = mapped_column(String(20))
    optimizer_iterations: Mapped[int | None] = mapped_column(Integer)
    input_sources_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
