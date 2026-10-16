"""A section's or theme's name as the researcher sees it.

The pipeline names each section (screen cluster) and theme; the researcher may
rename either. A rename is a ``HeadingEdit`` row keyed on the durable
cluster/theme id (``section-cluster-{id}:title``, ``theme-group-{id}:title``,
and ``:desc`` for the description), so it survives the pipeline relabelling the
group. The pipeline's name stays on the cluster row for reset-to-original and
the "edited" indicator. Once renamed, it is never what a surface shows (owner's
rule, 16 Oct 2026): every lens, export and agent surface reads names through
:class:`HeadingNames`, the one resolution.

A rename is the stored edit when there is one, an empty one included, which is
the frontend's ``edited_label ?? screen_label``.

Anchors key on the id too (``section_anchor``), so renaming a section never
moves the link to it. ``groupAnchor`` in ``frontend/src/utils/quoteGroups.ts``
builds the same strings.
"""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy.orm import Session

from bristlenose.server.models import HeadingEdit, ScreenCluster, ThemeGroup


def section_anchor(cluster_id: int) -> str:
    """The Quotes lens's scroll anchor for a section."""
    return f"section-{cluster_id}"


def theme_anchor(theme_id: int) -> str:
    """The Quotes lens's scroll anchor for a theme."""
    return f"theme-{theme_id}"


class HeadingNames:
    """A project's heading renames, loaded once per request."""

    def __init__(self, edits: Mapping[str, str]) -> None:
        self._edits = edits

    @classmethod
    def load(cls, db: Session, project_id: int) -> HeadingNames:
        return cls({
            he.heading_key: he.edited_text
            for he in db.query(HeadingEdit).filter_by(project_id=project_id).all()
        })

    def section_edit(self, cluster_id: int) -> str | None:
        """The researcher's title for a section, or None if not renamed."""
        return self._edits.get(f"section-cluster-{cluster_id}:title")

    def section_desc_edit(self, cluster_id: int) -> str | None:
        return self._edits.get(f"section-cluster-{cluster_id}:desc")

    def theme_edit(self, theme_id: int) -> str | None:
        """The researcher's title for a theme, or None if not renamed."""
        return self._edits.get(f"theme-group-{theme_id}:title")

    def theme_desc_edit(self, theme_id: int) -> str | None:
        return self._edits.get(f"theme-group-{theme_id}:desc")

    def section(self, cluster: ScreenCluster) -> str:
        """The section's name as shown: the rename, else the pipeline's."""
        edit = self.section_edit(cluster.id)
        return cluster.screen_label if edit is None else edit

    def theme(self, theme: ThemeGroup) -> str:
        """The theme's name as shown: the rename, else the pipeline's."""
        edit = self.theme_edit(theme.id)
        return theme.theme_label if edit is None else edit
