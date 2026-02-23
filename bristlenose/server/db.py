"""SQLAlchemy database setup — SQLite for now, Postgres later."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

_CONFIG_DIR = Path("~/.config/bristlenose").expanduser()


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _default_db_url() -> str:
    """Fallback DB URL when no project directory is available."""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    db_path = _CONFIG_DIR / "bristlenose.db"
    return f"sqlite:///{db_path}"


def db_url_for_project(project_dir: Path) -> str:
    """Return the SQLite URL for a per-project database.

    The DB lives at ``<output_dir>/.bristlenose/bristlenose.db`` so each
    project gets its own database with no cross-project contamination.
    """
    output_dir = project_dir / "bristlenose-output"
    if not output_dir.is_dir():
        output_dir = project_dir  # caller already pointed at the output dir
    db_path = output_dir / ".bristlenose" / "bristlenose.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


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

    # v0.11.x — Quote and TranscriptSegment gain segment_index (INTEGER, default -1)
    if "quotes" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("quotes")}
        if "segment_index" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE quotes ADD COLUMN segment_index INTEGER DEFAULT -1")
                )
    if "transcript_segments" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("transcript_segments")}
        if "segment_index" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE transcript_segments"
                        " ADD COLUMN segment_index INTEGER DEFAULT -1"
                    )
                )

    # v0.10.3 — Session gains thumbnail_path (VARCHAR 500, nullable)
    if "sessions" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("sessions")}
        if "thumbnail_path" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE sessions ADD COLUMN thumbnail_path VARCHAR(500)")
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
