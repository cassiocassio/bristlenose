"""Why an input file is not in the report.

A file can miss the report for two different reasons — Bristlenose **declined**
it (a format we don't accept) or Bristlenose **couldn't read** it (empty,
truncated, not actually a recording). Those are different causes with the *same*
consequence for the researcher: a participant whose recording isn't in the
findings. So they share one cause category and one visual weight, and differ
only in what the message says. See ``docs/design-analysis-lifecycle.md`` §5.

**A refusal is a pass, not a failure.** Outcome 2 in that document's taxonomy —
"refused by name, with a reason" — is an acceptable outcome. The run carries on
and succeeds; these entries ride on the terminus summary so the researcher can
see which files are missing and why, and they must never be mistaken for the
run having died.

**Messages are built from structured constants only — never from file content
or paths.** ``pipeline-events.jsonl`` is a named re-identification surface (see
the root ``CLAUDE.md``), and the basename already has a home in
``StageFailure.source_file``, which the Swift side matches on. A message here is
the reason and nothing else.
"""

from __future__ import annotations

from pathlib import Path

from bristlenose.events import Cause, CauseCategoryEnum, StageFailure, UnusableReason

#: Re-exported so the many ``from bristlenose.refusals import UnusableReason``
#: call sites keep working. The definition moved to ``events.py`` in Aug 2026
#: because the reason is now **on the wire** (``Cause.reason``) and ``refusals``
#: imports ``events``, so it could not stay here without a cycle.
__all__ = [
    "MESSAGES",
    "UnusableReason",
    "classify_unreadable",
    "looks_like_a_recording",
    "stage_failure",
]


#: One short sentence per reason. Deliberately specific — "the file is empty"
#: and "isn't a recording" send the researcher to different places (re-request
#: the upload / check what they actually attached), which a shared "couldn't be
#: read" would not.
#:
#: English-only, like every other `Cause.message` — the events log is a forensic
#: record, so a run analysed while the UI was German must not read as German
#: forever. The user-facing surfaces localise from `Cause.reason`, not from this
#: text: `desktop.pipeline.diagnostic.reason.<value>` in the locale files, keyed
#: by the same enum. **This text stays the English source of truth** for the CLI
#: (`_print_refusals`), the log lines in s01/s02, and any reader that predates
#: the `reason` field.
#:
#: Keep the two in step: a new reason needs an entry here *and* a key in all 21
#: full locales. `tests/test_pipeline_diagnostic_locale_keys.py` enforces the
#: second half and `test_refusals.py` the first.
MESSAGES: dict[UnusableReason, str] = {
    UnusableReason.UNSUPPORTED_FORMAT: "Not a format Bristlenose reads.",
    UnusableReason.EMPTY: "The file is empty — the transfer produced no data.",
    UnusableReason.INCOMPLETE: "The file is incomplete — the transfer stopped early.",
    UnusableReason.NOT_A_RECORDING: "Not a recording, despite the file extension.",
    UnusableReason.NO_AUDIO: "No sound in this file — there is nothing to transcribe.",
    UnusableReason.NO_SPEECH: "No speech found — nothing was said in this recording.",
    UnusableReason.UNREADABLE_FOLDER: "This folder couldn't be opened.",
    UnusableReason.UNREADABLE: "The file couldn't be read.",
}

#: Leading bytes that identify a media container. Enough to answer the only
#: question being asked — "is this a recording at all?" — not to identify the
#: format, which ffprobe already does when the file is whole.
#:
#: The ISO base-media family (mp4/m4v/mov/3gp/m4a) is the exception: its marker
#: is at offset 4, after the box length, so it is checked separately.
_CONTAINER_MAGIC: tuple[bytes, ...] = (
    b"\x1a\x45\xdf\xa3",  # Matroska / WebM (EBML)
    b"RIFF",              # AVI, WAV
    b"OggS",              # Ogg (Vorbis, Opus, Theora)
    b"fLaC",              # FLAC
    b"\x30\x26\xb2\x75",  # ASF / WMV
    b"\x00\x00\x01\xba",  # MPEG program stream (.mpg, VOB)
    b"\x00\x00\x01\xb3",  # MPEG video elementary stream
    b"FLV\x01",           # Flash video
    b"FORM",              # AIFF
    b"caff",              # CAF
    b"ID3",               # MP3 with an ID3 tag
    b"\x00\x00\x00\x1cf",  # some m4a writers; harmless overlap with ftyp check
)

_SNIFF_BYTES = 16


def looks_like_a_recording(path: Path) -> bool:
    """Whether *path* starts with any container header we recognise.

    The question is deliberately coarse. A truncated recording keeps its header
    — truncation removes the tail — so a file that has one and still won't
    decode is *incomplete*; a file with none was never a recording. That
    distinction is what lets the two get different sentences instead of a shared
    shrug, and it is exactly the difference between "ask the participant to
    re-send" and "check what you attached".

    Unreadable ⇒ ``False`` is deliberate: the caller has already established the
    file won't decode, so the worse label to guess wrong is "incomplete", which
    invites a pointless re-request.
    """
    try:
        with path.open("rb") as fh:
            head = fh.read(_SNIFF_BYTES)
    except OSError:
        return False
    if len(head) >= 8 and head[4:8] == b"ftyp":
        return True
    # MPEG transport streams start each 188-byte packet with 0x47. Cheap, and
    # `.ts` is not accepted anyway (macOS calls TypeScript a movie — see the
    # root CLAUDE.md), so this only matters for `.mts` / `.m2ts`.
    if head[:1] == b"\x47":
        return True
    return any(head.startswith(magic) for magic in _CONTAINER_MAGIC)


def classify_unreadable(path: Path) -> UnusableReason:
    """Say *why* a file that won't decode won't decode.

    Ordered by certainty: an empty file is a fact from ``stat``; everything
    after it is inference from the leading bytes. Never raises — a classifier
    that throws while explaining a failure has made the situation worse.
    """
    try:
        if path.stat().st_size == 0:
            return UnusableReason.EMPTY
    except OSError:
        return UnusableReason.UNREADABLE
    return (
        UnusableReason.INCOMPLETE
        if looks_like_a_recording(path)
        else UnusableReason.NOT_A_RECORDING
    )


def stage_failure(
    *, source_file: str, reason: UnusableReason, stage: str, session_id: str | None = None
) -> StageFailure:
    """One entry for the ingest stage's outcome.

    ``source_file`` is a **basename**. The caller is responsible for that: a
    full path here would put directory structure into a diagnostic the
    researcher can copy out of the popover.
    """
    return StageFailure(
        session_id=session_id,
        source_file=source_file,
        cause=Cause(
            category=CauseCategoryEnum.UNUSABLE_INPUT,
            message=MESSAGES[reason],
            # Both, deliberately. `reason` is what the desktop localises from;
            # `message` is the English a CLI user reads, an older desktop build
            # falls back to, and a bug report gets pasted with.
            reason=reason,
            stage=stage,
            session_id=session_id,
        ),
    )
