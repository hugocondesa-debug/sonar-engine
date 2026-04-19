"""SQLAlchemy engine + sessionmaker singletons.

Phase 1 MVP: sync engine apontando para SQLite via settings.database_url.
Async engine + session factory virão quando primeiro connector/overlay
requerer async DB access (Phase 2+).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sonar.config import settings

engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
