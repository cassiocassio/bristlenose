"""SQLAlchemy ORM models — database tables."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from bristlenose.server.db import Base


class Project(Base):
    """A research project (one study, one set of interviews)."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    input_dir: Mapped[str] = mapped_column(String(500))
    output_dir: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(default=func.now())
