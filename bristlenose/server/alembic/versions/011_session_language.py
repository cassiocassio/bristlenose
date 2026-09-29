"""Record each session's spoken language.

Adds ``sessions.language``: the spoken language (ISO 639-1), read at import
from the transcript header's ``# Language: xx (detected)`` line, which stage 6
has written since 0.31.0 (``cca68462``), or ``xx (set)`` for a run pinned with
``--whisper-language``.

Why it is stored: an exported clip's subtitle track must carry a language,
or macOS players cannot match it to the viewer's "subtitles in my language"
setting. Measured 29 Sep 2026: tagged ``und``, QuickTime's *Subtitles ▸ On*
selected an empty "Forced" variant and showed nothing; tagged ``eng``, it
showed the track and offered a live translation. The language was known
upstream and lost at import.

Nullable, no default: ``None`` is the honest value for every project that
predates the header and for transcripts nothing knew the language of
(platform, docx). The clip export falls back to the app's language for those.

Guarded per the Alembic discipline: ``upgrade()`` runs on a fresh DB too, but
``_has_column`` skips the ALTER there (``create_all()`` already made it).

Revision ID: 011
Revises: 010
Create Date: 2026-09-29
"""

import sqlalchemy as sa
from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    columns = sa.inspect(op.get_bind()).get_columns(table)
    return any(c["name"] == column for c in columns)


def upgrade() -> None:
    if _has_column("sessions", "language"):
        return
    op.add_column("sessions", sa.Column("language", sa.String(20), nullable=True))


def downgrade() -> None:
    if _has_column("sessions", "language"):
        op.drop_column("sessions", "language")
