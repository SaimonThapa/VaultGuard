"""SQLAlchemy engine, session factory and declarative base."""

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import DATABASE_URL

IS_SQLITE = DATABASE_URL.startswith("sqlite")

if DATABASE_URL.startswith("sqlite:///"):
    # Make sure the folder holding the SQLite file exists.
    Path(DATABASE_URL.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    # FastAPI may serve a request on a different thread than the one that opened the connection.
    connect_args={"check_same_thread": False} if IS_SQLITE else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

if IS_SQLITE:

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):
        # SQLite ignores foreign keys (and ON DELETE CASCADE) unless this is on.
        dbapi_connection.execute("PRAGMA foreign_keys=ON")


class Base(DeclarativeBase):
    """Base class for ORM models."""


def utcnow() -> datetime:
    """Current UTC time without tzinfo. SQLite drops tzinfo, so every stored time is naive UTC."""
    return datetime.now(UTC).replace(tzinfo=None)


def iso(moment: datetime | None) -> str | None:
    """ISO-8601 UTC string with a Z suffix, as the API promises (product_backend.md §1)."""
    return None if moment is None else moment.isoformat(timespec="seconds") + "Z"


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
