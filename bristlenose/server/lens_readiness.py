"""Which lenses have something true to show — derived, never stored.

Progressive lenses (``docs/design-progressive-lenses.md`` §3.3): while a first
analysis runs, the Sessions lens is usable from the first second and every other
lens lights when it has content. This is the one derivation; the condition
endpoint serves it, the SPA's nav and the Mac's lens rail read it.

``progress`` is the per-session overlay the server reads from the manifest
(§3.1). ``None`` means no progressive run is in play — a finished project, a
re-analyse showing its previous report, or a server that does not track
progress yet — and then every lens is available, exactly as before.

Keys are the lens ids the SPA routes and the Mac's ``Tab`` raw values share.
"""

from __future__ import annotations

from dataclasses import dataclass, field

LENSES = ("project", "sessions", "quotes", "codebook", "signals", "discussion")


@dataclass(frozen=True)
class Progress:
    """Per-session facts about the run in progress (the manifest overlay)."""

    readable: frozenset[str] = field(default_factory=frozenset)
    #: Sessions whose quote extraction returned at least one quote.
    quoted: frozenset[str] = field(default_factory=frozenset)
    quote_failed: frozenset[str] = field(default_factory=frozenset)
    #: Sections and themes are written — the barrier.
    joined: bool = False
    discussion_done: bool = False


def lens_readiness(progress: Progress | None) -> dict[str, bool]:
    """Each lens id → whether it can be selected now."""
    if progress is None:
        return dict.fromkeys(LENSES, True)
    return {
        # The session list is known at ingest; the grid shows every true fact.
        "sessions": True,
        "quotes": bool(progress.quoted),
        "signals": progress.joined,
        # Owner decisions (§2, §7): Codebooks waits for the run in v1; the
        # Project lens's place during a run is not decided, so it waits too.
        "codebook": False,
        "project": False,
        "discussion": progress.discussion_done,
    }
