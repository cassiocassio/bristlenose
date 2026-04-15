"""SQLAlchemy database setup — SQLite for now, Postgres later."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event, inspect
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


def run_migrations(engine: Engine) -> None:
    """Run Alembic migrations. Handles fresh, pre-Alembic, and managed DBs.

    Detection logic:
    - ``alembic_version`` exists → already managed, upgrade to head
    - No ``alembic_version`` + user tables exist → pre-Alembic DB, stamp
      at baseline (001) then upgrade to head
    - No ``alembic_version`` + no user tables → brand-new DB,
      ``create_all()`` already ran, stamp at head
    """
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config()
    alembic_cfg.set_main_option(
        "script_location", str(Path(__file__).parent / "alembic")
    )

    with engine.begin() as connection:
        alembic_cfg.attributes["connection"] = connection

        insp = inspect(engine)
        tables = set(insp.get_table_names())
        has_alembic = "alembic_version" in tables

        if has_alembic:
            # Already managed — upgrade to head
            command.upgrade(alembic_cfg, "head")
        elif tables:
            # Pre-Alembic DB: tables exist from create_all() + old _migrate_schema()
            command.stamp(alembic_cfg, "001")
            command.upgrade(alembic_cfg, "head")
        else:
            # Brand-new empty DB: create_all() just ran, stamp at head
            command.stamp(alembic_cfg, "head")


def init_db(engine: Engine) -> None:
    """Create all tables and run migrations. Safe to call repeatedly."""
    from bristlenose.server import models  # noqa: F401 — registers all tables

    Base.metadata.create_all(bind=engine)
    run_migrations(engine)


def get_db(engine: Engine) -> Generator[Session, None, None]:
    """Dependency that yields a database session and closes it after use."""
    session_factory = create_session_factory(engine)
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
