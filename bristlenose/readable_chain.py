"""Make each session readable as soon as Whisper hands it over.

docs/design-progressive-lenses.md, Phase 1. On a first analysis the researcher
can read session 1's transcript while session 2 is still being transcribed. So
between one Whisper file and the next, this runs the rest of what a readable
transcript needs for the session just finished: speaker identification, its
participant codes, the merge, the transcript files, and the manifest record
the server reads to import it.

It writes exactly the artefacts the batch stages would have written, in the
form their per-session resume already reads: stage 5b finds the session in the
speaker cache and loads it rather than paying for it again, and stage 6
rewrites the transcript file with the same content. A session the chain could
not finish is left to those stages, which do it the ordinary way — the chain
is an early delivery, never a second source of truth.

**In session order, with a hold.** Participant codes are a sequential fold
(``assign_speaker_codes`` threads the next participant number), so session N
waits for N−1 even when N's transcript was parsed first.

**On the event loop, between Whisper files.** Transcription is a blocking
call; the chain's LLM calls run while it is between files. No thread, so
Ctrl-C and the GIL behave as before; the cost is that session N's speaker pass
delays Whisper on N+1 by its own latency. Each session's speaker pass starts as
soon as its transcript is handed over and runs concurrently with the others
behind the pass's own semaphores — a project of platform transcripts, all
parsed before Whisper starts, is not made slower than the batch — and only the
delivery waits its turn.

**A failure stops the chain.** A session the chain could not deliver is left
to stage 5b, and so is every session after it: delivering session N+1 past a
failed N would number N+1's participant before N's, and the registry keeps
codes for good.

**Not under redaction.** A transcript is readable only once it is redacted, and
the PII engines load once per run, so the chain stays off when ``pii_enabled``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from bristlenose.manifest import (
    STAGE_IDENTIFY_SPEAKERS,
    STAGE_MERGE_TRANSCRIPT,
    STAGE_TRANSCRIBE,
    PipelineManifest,
    mark_session_complete,
    write_manifest,
)

if TYPE_CHECKING:
    from bristlenose.config import BristlenoseSettings
    from bristlenose.models import InputSession, TranscriptSegment
    from bristlenose.session_registry import SessionRegistry
    from bristlenose.speaker_pass import SpeakerPass
    from bristlenose.stages.s05b_identify_speakers import SpeakerInfo

logger = logging.getLogger(__name__)


def speaker_cache_bytes(
    infos: Sequence[SpeakerInfo],
    segments: list[TranscriptSegment],
    split_record: dict[str, object] | None,
) -> bytes:
    """The speaker cache file for one session, as stage 5b writes it."""
    from bristlenose.stages.s05b_identify_speakers import speaker_info_to_dict

    data = {
        "speaker_infos": [speaker_info_to_dict(info) for info in infos],
        "segments_with_roles": [seg.model_dump(mode="json") for seg in segments],
        "speaker_split": split_record,
    }
    return json.dumps(data, indent=2).encode("utf-8")


class ReadableChain:
    """Ordered, per-session delivery of readable transcripts during transcription."""

    def __init__(
        self,
        *,
        order: list[InputSession],
        settings: BristlenoseSettings,
        speaker_pass: SpeakerPass,
        manifest: PipelineManifest,
        output_dir: Path,
        input_dir: Path,
        registry: SessionRegistry,
        sentence_paragraphs: set[str],
        languages: Callable[[], tuple[dict[str, str], dict[str, str]]],
        fingerprint: Callable[[list[TranscriptSegment]], str],
        assign_codes: Callable[..., object],
        tx_fingerprints: dict[str, str],
        segments_path: Path,
        emit: Callable[[int], None],
    ) -> None:
        self._order = order
        self._next = 0
        self._pending: dict[str, list[TranscriptSegment] | None] = {}
        self.settings = settings
        self.speaker_pass = speaker_pass
        self._manifest = manifest
        self._output_dir = output_dir
        self._input_dir = input_dir
        self._raw_dir = output_dir / "transcripts-raw"
        self._si_dir = output_dir / ".bristlenose" / "intermediate" / "speaker-info"
        self._registry = registry
        self.sentence_paragraphs = sentence_paragraphs
        self._languages = languages
        self._fingerprint = fingerprint
        self._assign_codes = assign_codes
        self._tx_fps = tx_fingerprints
        self._segments_path = segments_path
        self._emit = emit
        #: The raw transcription of each session the chain received, for the
        #: incremental ``session_segments.json`` a resume reads.
        self._raw: dict[str, list[TranscriptSegment]] = {}
        #: Session → fingerprint of the raw segments its speaker cache was
        #: computed from. Stage 5b reuses an entry only while it still matches.
        self.identified: dict[str, str] = {}
        #: Sessions whose transcript files are written and recorded.
        self.readable: list[str] = []
        #: Wall time the chain held the transcription stage up — mostly
        #: speaker identification, which the run's timings move from
        #: transcription back to the speakers stage.
        self.seconds = 0.0
        #: Speaker passes started on hand-over, by session (strong references:
        #: the loop holds tasks weakly).
        self._speakers: dict[str, asyncio.Task[tuple[list[TranscriptSegment], list[SpeakerInfo]]]] = {}
        self._stopped = False
        # One drain at a time: offers made together (the parsed transcripts,
        # handed over before Whisper starts) start their speaker passes at
        # once, and deliver one by one in session order.
        self._drain = asyncio.Lock()

    async def offer(self, sid: str, segments: list[TranscriptSegment] | None) -> None:
        """Hand over one session's transcription (None: it produced nothing)."""
        self._pending[sid] = segments
        if segments and not self._stopped:
            self._speakers[sid] = asyncio.create_task(self._identify(sid, segments))
        async with self._drain:
            await self._deliver_ready()

    async def _deliver_ready(self) -> None:
        while self._next < len(self._order) and not self._stopped:
            head = self._order[self._next].session_id
            if head not in self._pending:
                return  # held: an earlier session is not transcribed yet
            got = self._pending.pop(head)
            session = self._order[self._next]
            self._next += 1
            if not got:
                continue
            t0 = time.perf_counter()
            try:
                await self._deliver(session, got)
            except Exception:
                self.stop()
                logger.warning(
                    "readable_chain | %s could not be delivered early; it and every "
                    "session after it are left to the batch stages", head, exc_info=True,
                )
            finally:
                self.seconds += time.perf_counter() - t0

    def stop(self) -> None:
        """Deliver nothing more; cancel the speaker passes not yet delivered."""
        self._stopped = True
        for task in self._speakers.values():
            task.cancel()
        self._speakers.clear()

    async def _identify(
        self, sid: str, raw: list[TranscriptSegment],
    ) -> tuple[list[TranscriptSegment], list[SpeakerInfo]]:
        # On a copy: the raw transcription is what the cache and every
        # fingerprint are computed from.
        work = [seg.model_copy(deep=True) for seg in raw]
        return work, await self.speaker_pass.run(sid, work)

    async def _deliver(self, session: InputSession, raw: list[TranscriptSegment]) -> None:
        from bristlenose.hashing import hash_bytes
        from bristlenose.stages.s06_merge_transcript import (
            merge_transcripts,
            write_raw_transcripts,
            write_raw_transcripts_md,
        )

        sid = session.session_id
        # Transcription, recorded per session with the segments a resume reads.
        # The record must never get ahead of the file: a recorded session the
        # file lacks is dropped from a resumed run without a word.
        self._raw[sid] = raw
        self._write_segments()
        mark_session_complete(
            self._manifest, STAGE_TRANSCRIBE, sid, input_hash=self._tx_fps.get(sid),
        )

        fp = self._fingerprint(raw)
        task = self._speakers.pop(sid, None)
        if task is None:
            task = asyncio.create_task(self._identify(sid, raw))
        work, infos = await task
        data = speaker_cache_bytes(infos, work, self.speaker_pass.split_records.get(sid))
        self._si_dir.mkdir(parents=True, exist_ok=True)
        (self._si_dir / f"{sid}.json").write_bytes(data)
        mark_session_complete(
            self._manifest, STAGE_IDENTIFY_SPEAKERS, sid,
            provider=self.settings.llm_provider, model=self.settings.llm_model,
            content_hash=hash_bytes(data), input_hash=fp,
        )
        self.identified[sid] = fp

        # Codes, then the transcript files. No placeholder participant here: a
        # placeholder number taken now could be one a later session's real
        # participant needs, and stage 5b assigns placeholders after its loop.
        coded = [seg.model_copy(deep=True) for seg in work]
        self._assign_codes([session], {sid: coded}, self._registry, None, placeholders=False)
        self._registry.save()
        detected, pinned = self._languages()
        transcripts = merge_transcripts(
            [session], {sid: coded}, self._input_dir,
            session_languages=detected, pinned_languages=pinned,
            sentence_paragraphs=self.sentence_paragraphs,
        )
        write_raw_transcripts(transcripts, self._raw_dir, sentence_paragraphs=self.sentence_paragraphs)
        write_raw_transcripts_md(
            transcripts, self._raw_dir, sentence_paragraphs=self.sentence_paragraphs,
        )
        # Last: the server imports a session the manifest calls merged, so the
        # files are whole before the record says so.
        mark_session_complete(self._manifest, STAGE_MERGE_TRANSCRIPT, sid)
        write_manifest(self._manifest, self._output_dir)
        self.readable.append(sid)
        logger.info("readable_chain | session=%s | readable (%d so far)", sid, len(self.readable))
        try:
            self._emit(len(self.readable))
        except Exception:  # noqa: BLE001 — the session is delivered; a lost count is not a lost session
            logger.warning("readable_chain | progress line for %s not written", sid, exc_info=True)

    def _write_segments(self) -> None:
        """``session_segments.json`` for the sessions transcribed so far."""
        self._segments_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            sid: [seg.model_dump(mode="json") for seg in segs]
            for sid, segs in self._raw.items()
        }
        tmp = self._segments_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(self._segments_path)


#: The session list as ingest found it, beside the other intermediates. Not
#: ``.bristlenose/sessions.json``, which is the session registry (identity and
#: pins). The serve reads it to show every session from the first second.
INGEST_FACTS = "ingest-facts.json"


def ingest_facts(sessions: list[InputSession]) -> list[dict[str, object]]:
    """Every true fact ingest knows about each session; unknown facts absent."""
    from bristlenose.models import FileType

    media = (FileType.AUDIO, FileType.VIDEO)
    out: list[dict[str, object]] = []
    for s in sessions:
        durations = [f.duration_seconds for f in s.files if f.file_type in media and f.duration_seconds]
        named = next((f for f in s.files if f.file_type in media), s.files[0] if s.files else None)
        entry: dict[str, object] = {
            "session_id": s.session_id,
            "session_number": s.session_number,
            "start": s.session_date.isoformat(),
            "has_video": s.has_video,
            # Whisper will take it: the readable transcript arrives after
            # decoding. A platform transcript is read as soon as it is parsed.
            "transcribes": not s.has_existing_transcript and (s.has_audio or s.has_video),
        }
        if named is not None:
            entry["source"] = named.path.name
        if durations:
            entry["duration_seconds"] = max(durations)
        out.append(entry)
    return out


def write_ingest_facts(output_dir: Path, sessions: list[InputSession]) -> None:
    path = output_dir / ".bristlenose" / "intermediate" / INGEST_FACTS
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"sessions": ingest_facts(sessions)}, indent=2), encoding="utf-8")
    tmp.replace(path)
