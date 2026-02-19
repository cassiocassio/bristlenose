"""SQLAlchemy database setup — SQLite for now, Postgres later."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

_CONFIG_DIR = Path("~/.config/bristlenose").expanduser()
_DB_PATH = _CONFIG_DIR / "bristlenose.db"


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _default_db_url() -> str:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{_DB_PATH}"


def get_engine(db_url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine.

    Args:
        db_url: Database URL. Defaults to the standard SQLite path.
                Pass "sqlite://" for an in-memory database (tests).
    """
    url = db_url or _default_db_url()
    # In-memory SQLite needs StaticPool so all connections share the
    # same database (otherwise each connection gets its own empty DB).
    if url == "sqlite://":
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_engine(url, connect_args={"check_same_thread": False})


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):  # type: ignore[no-untyped-def]
    """Enable WAL mode and foreign keys for SQLite connections."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a sessionmaker bound to the given engine."""
    return sessionmaker(bind=engine)


def _migrate_schema(engine: Engine) -> None:
    """Add columns introduced after initial schema creation.

    SQLAlchemy's ``create_all`` only creates *new* tables — it never alters
    existing ones.  This helper inspects the live schema and issues ALTER TABLE
    statements for any missing columns so that existing databases pick up new
    fields without requiring a full Alembic migration stack.
    """
    insp = inspect(engine)

    # v0.10.x — CodebookGroup gains framework_id (VARCHAR 50, nullable)
    if "codebook_groups" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("codebook_groups")}
        if "framework_id" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE codebook_groups ADD COLUMN framework_id VARCHAR(50)")
                )


def init_db(engine: Engine) -> None:
    """Create all tables. Safe to call repeatedly (CREATE IF NOT EXISTS)."""
    from bristlenose.server import models  # noqa: F401 — registers all tables

    Base.metadata.create_all(bind=engine)
    _migrate_schema(engine)


def get_db(engine: Engine) -> Generator[Session, None, None]:
    """Dependency that yields a database session and closes it after use."""
    session_factory = create_session_factory(engine)
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
