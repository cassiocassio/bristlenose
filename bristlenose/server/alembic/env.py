"""Alembic environment — fully programmatic, no alembic.ini.

The connection is passed via ``config.attributes["connection"]`` by
``run_migrations()`` in ``db.py``.  This avoids URL resolution entirely,
which is critical for in-memory SQLite tests (StaticPool shares one
connection — creating a new one from a URL would get a different empty DB).
"""

from __future__ import annotations

from alembic import context

from bristlenose.server.db import Base


def run_migrations_online() -> None:
    """Run migrations using the connection injected by db.run_migrations()."""
    connection = config.attributes["connection"]
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


config = context.config
run_migrations_online()
