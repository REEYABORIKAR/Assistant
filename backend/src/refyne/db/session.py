from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from refyne.config import get_settings


def create_database_engine():
    database_url = get_settings().database_url
    if not database_url:
        raise RuntimeError("DATABASE_URL must be configured before using persistence")
    return create_engine(database_url, pool_pre_ping=True)


# Create a sessionmaker for the entire application
SessionLocal = sessionmaker(
    bind=create_database_engine(),
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
