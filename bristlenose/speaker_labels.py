"""The speaker label a raw transcript line carries, which is not what was said.

The raw ``.txt`` writer puts each line's speaker label after its code,
``[00:14] [p1] (Speaker B) Okay…`` (``utils/markdown.format_raw_segment_txt``),
and a platform transcript's label is the person's real name. Two readers take it
off the words: the serve importer (since 8 Oct 2026, ``4256a8925``) and the
pipeline's ``load_transcripts_from_dir`` for ``analyze`` (since 27 Nov 2026,
after a local model copied "(Speaker A)" into 58 of 105 quotes' excerpts).

Only a label the pipeline recorded for the session is taken, so a transcript's
own "(laughs)" stays: the record is the exact key, and the file alone cannot say
whether a leading bracket is a label. Kept out of ``server/`` so the pipeline
can use it without importing SQLAlchemy.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def session_speaker_labels(output_dir: Path, sid: str) -> set[str]:
    """The speaker labels the pipeline gave this session — the exact set the
    ``.txt`` writer put in front of its lines. From the identify stage's
    ``speaker-info/<sid>.json`` (its speakers, and each segment's label) and the
    session registry. Empty when neither
    knows, and then nothing is stripped."""
    labels: set[str] = set()
    info = output_dir / ".bristlenose" / "intermediate" / "speaker-info" / f"{sid}.json"
    try:
        data = json.loads(info.read_text(encoding="utf-8"))
        # A split recording names its labels in speaker_infos; a platform
        # transcript (VTT voice tags) leaves that empty and carries them on
        # each segment.
        labels |= {
            str(s.get("speaker_label")).strip()
            for key in ("speaker_infos", "segments_with_roles")
            for s in data.get(key, [])
            if s.get("speaker_label")
        }
    except FileNotFoundError:
        pass
    except (OSError, ValueError, AttributeError) as exc:
        # Unreadable, not absent: the session's labels stay in its words.
        logger.warning(
            "speaker_info_unreadable | file=speaker-info/%s.json | error=%s: %s",
            sid, type(exc).__name__, exc,
        )
    try:
        from bristlenose.session_registry import NO_PARTICIPANT_LABEL, SessionRegistry

        held = SessionRegistry.load(output_dir).speakers.get(sid, {})
        labels |= {
            label for label in held
            if not label.startswith("\u0000") and label != NO_PARTICIPANT_LABEL
        }
    except (OSError, ValueError, ImportError):
        pass
    return labels


def split_speaker_label(text: str, labels: set[str]) -> tuple[str | None, str]:
    """``(label, words)``: the session label in front of a line's words, and the words.

    Only one of this session's own labels is taken, so a transcript's
    "(laughs)" stays. Matched literally, longest first, so a label holding
    brackets of its own — "Jo (Acme (UK))", "Smith (Acme" — goes whole. A line
    that is only a label keeps it as its words. ``(None, text)`` otherwise.
    """
    for label in sorted(labels, key=len, reverse=True):
        lead = f"({label})"
        if label and text.startswith(lead) and text[len(lead):].strip():
            return label, text[len(lead):].lstrip()
    return None, text


def without_speaker_label(text: str, labels: set[str]) -> str:
    """A paragraph's words without the speaker label the ``.txt`` carries in
    front of them (6 Oct 2026: "(Speaker B)" was drawn in the transcript, and a
    platform transcript's real name with it, past anonymisation)."""
    return split_speaker_label(text, labels)[1]
