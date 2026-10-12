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
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bristlenose.manifest import PipelineManifest

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


def readable_in_manifest(manifest: PipelineManifest | None) -> frozenset[str]:
    """Sessions the run has made readable: their merged transcript is written.

    The pipeline records a session merged only after its transcript files are
    whole (``readable_chain.py``, and stage 6 for the rest), so the server can
    import exactly these.
    """
    from bristlenose.manifest import (
        STAGE_MERGE_TRANSCRIPT,
        STAGE_PII_REMOVAL,
        get_completed_session_ids,
    )

    # Under redaction a transcript is readable once it is redacted: the run
    # records no per-session merge then (those files are the unredacted ones),
    # and the redaction stage records each session it wrote.
    if manifest is not None and STAGE_PII_REMOVAL in manifest.stages:
        return frozenset(get_completed_session_ids(manifest, STAGE_PII_REMOVAL))
    return frozenset(get_completed_session_ids(manifest, STAGE_MERGE_TRANSCRIPT))


def quoted_in_manifest(manifest: PipelineManifest | None) -> frozenset[str]:
    """Sessions whose quote extraction is recorded done, quotes on disk.

    Zero-quote sessions are included; the server lights the Quotes lens from
    the quotes it actually imported, not from this set.
    """
    from bristlenose.manifest import STAGE_QUOTE_EXTRACTION, get_completed_session_ids

    return frozenset(get_completed_session_ids(manifest, STAGE_QUOTE_EXTRACTION))


#: A row in the Sessions grid during a run (§2): open it, it is being worked
#: on now, or it exists and is waiting its turn.
READABLE, PROCESSING, WAITING = "readable", "processing", "waiting"


def session_states(
    facts: list[dict[str, object]], readable: frozenset[str],
) -> dict[str, str]:
    """Each ingested session's state, in session order.

    One session is processing: the first not yet readable after the last one
    that is, provided Whisper takes it (``transcribes``). A platform transcript
    is read the moment it is parsed, so it never shimmers (§2). A session that
    failed to transcribe stays waiting; its outcome is the run's to state.
    """
    states: dict[str, str] = {}
    last_readable = max(
        (i for i, f in enumerate(facts) if f.get("session_id") in readable), default=-1,
    )
    processing_taken = False
    for i, f in enumerate(facts):
        sid = str(f.get("session_id", ""))
        if sid in readable:
            states[sid] = READABLE
        elif not processing_taken and i > last_readable and f.get("transcribes"):
            states[sid] = PROCESSING
            processing_taken = True
        else:
            states[sid] = WAITING
    return states


def read_ingest_facts(output_dir: Path) -> list[dict[str, object]]:
    """The session list ingest wrote, or empty when there is none to read."""
    import json

    from bristlenose.readable_chain import INGEST_FACTS

    path = output_dir / ".bristlenose" / "intermediate" / INGEST_FACTS
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    sessions = data.get("sessions") if isinstance(data, dict) else None
    return [s for s in sessions if isinstance(s, dict)] if isinstance(sessions, list) else []
