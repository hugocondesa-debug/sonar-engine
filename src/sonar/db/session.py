"""SQLAlchemy engine + sessionmaker singletons.

Phase 1 MVP: sync engine apontando para SQLite via settings.database_url.
Async engine + session factory virão quando primeiro connector/overlay
requerer async DB access (Phase 2+).

SQLite FK enforcement is OFF by default — we register a connect-event
listener that issues ``PRAGMA foreign_keys=ON`` for every new connection
so spec §8 FK constraints (yield_curves_{zero,forwards,real}.fit_id →
yield_curves_spot.fit_id) are actually enforced. Listener is registered
at module import time and applies to **every** Engine created after that
point (including ad-hoc test engines).
"""

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from sonar.config import settings


@event.listens_for(Engine, "connect")
def _enable_sqlite_fk(dbapi_connection: object, _connection_record: object) -> None:
    # Skip non-SQLite drivers (Postgres etc. ignore PRAGMA but raise on .cursor()
    # of a non-SQLite connection variants in some cases).
    driver = type(dbapi_connection).__module__
    if "sqlite" not in driver.lower():
        return
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
