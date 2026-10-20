"""One session's speaker identification, shared by stage 5b and the readable chain.

Stage 5b used to run its passes across every session at once: gate them all,
split them all, heuristic over them all, then the LLM role pass over them all.
Each pass is per session, though, and no session reads another's result, so the
same work composes per session. That is what lets the progressive run identify
session 1's speakers while session 2 is still with Whisper
(docs/design-progressive-lenses.md, Phase 1 step 2), and lets stage 5b run the
very same code for the sessions the chain did not reach.

One instance per run. The voice model is resolved and loaded once, the first
time a session needs the split, and every session after shares it.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from rich.markup import escape as rich_escape

from bristlenose.llm import telemetry as _llm_telemetry

if TYPE_CHECKING:
    from bristlenose.config import BristlenoseSettings
    from bristlenose.models import TranscriptSegment
    from bristlenose.stages.s05b_identify_speakers import SpeakerInfo

logger = logging.getLogger(__name__)

TELEMETRY_STAGE = "s05b_identify_speakers"


class SpeakerPass:
    """Split gate, LLM split + voice check, heuristic, LLM roles — per session.

    ``warn`` prints a researcher-facing warning line; ``status`` updates the
    live status text. Both belong to the caller's console.
    """

    def __init__(
        self,
        settings: BristlenoseSettings,
        llm_client: object,
        audio_for: dict[str, Path | None],
        *,
        warn: Callable[[str], None],
        status: Callable[[str], None],
    ) -> None:
        self.settings = settings
        self.llm_client = llm_client
        self._audio_for = audio_for
        self._warn = warn
        self._status = status
        concurrency = settings.llm_concurrency
        self._sem_split = asyncio.Semaphore(concurrency)
        self._sem_roles = asyncio.Semaphore(concurrency)
        # The voice pass is CPU-bound and multithreaded inside onnxruntime: one
        # session at a time, off the event loop.
        self._sem_voice = asyncio.Semaphore(1)
        self._voice_lock = asyncio.Lock()
        self._voice_ready = False
        self._voice_model: Path | None = None
        self._voice_off = ""
        #: Errors from the LLM passes, for the stage's one summary warning.
        self.errors: list[str] = []
        #: Sessions whose split or role call failed: their heuristic roles
        #: stand for this run, and they are recorded failed so the next run
        #: asks again (R97).
        self.failed: set[str] = set()
        #: What produced each session's speaker labels, written to the speaker
        #: cache so a later stage (or a person) can tell a voice-checked split
        #: from a text-only one.
        self.split_records: dict[str, dict[str, object]] = {}

    def gate(self, sid: str, segments: list[TranscriptSegment]) -> bool:
        """Whether this session takes the split. Records and states the rest.

        Never a platform transcript that names its speakers, and never a cloud
        transcript whose writer said it could not separate them. ``split_gate``
        holds the rule; a session it keeps whole is stated, because the
        researcher will see one voice where there were two and must know why.
        """
        from bristlenose.stages.s05b_identify_speakers import (
            SplitGate,
            real_speaker_names,
            split_gate,
        )

        gate = split_gate(segments)
        if gate is SplitGate.SEPARATED:
            self.split_records[sid] = {"method": "transcript-labels"}
        elif gate is SplitGate.NOT_SEPARATED:
            self.split_records[sid] = {"method": "not-separated"}
            # NOT_SEPARATED is only ever a single real name now.
            name = next(iter(real_speaker_names(segments)))
            msg = (
                f"{sid}: speakers not separated — the transcript names "
                f"one speaker ({name}); kept as the platform wrote it, not split"
            )
            logger.warning(msg)
            self._warn(msg)
        return gate is SplitGate.SPLIT

    async def _ensure_voice(self) -> None:
        """Resolve and load the voice model once, the first time it is wanted.

        Marked ready only once the attempt is over, success or not, so a
        failure is said once and every later session runs text-only with the
        reason on its speaker record — never silently, never retried per session.
        """
        async with self._voice_lock:
            if self._voice_ready:
                return
            try:
                await self._prepare_voice()
            except Exception as exc:
                # Every session after this runs text-only; say so once, with why.
                self._voice_model = None
                self._voice_off = f"voice pass failed to start: {type(exc).__name__}"
                logger.warning("voice pass failed to start", exc_info=True)
                self._warn(rich_escape(f"Voice pass skipped: {self._voice_off}"))
            finally:
                self._voice_ready = True

    async def _prepare_voice(self) -> None:
        from bristlenose.stages.s05b_voice import (
            load_voice_model,
            resolve_voice_model,
            voice_install_hint,
            voice_runtime_available,
        )

        if not self.settings.voice_pass:
            self._voice_off = "voice pass switched off (BRISTLENOSE_VOICE_PASS)"
            return
        if not voice_runtime_available():
            self._voice_off = f"voice extra not installed ({voice_install_hint()})"
            return
        self._status("[dim]Preparing the voice pass...[/dim]")
        self._voice_model, self._voice_off = await asyncio.to_thread(
            resolve_voice_model, allow_fetch=not self.settings.no_fetch,
        )
        fetchable = self._voice_model is None
        if self._voice_model is not None:
            # Load once, here: a model or runtime that will not load must be
            # one visible warning, not a quiet text-only fallback in every
            # session.
            self._voice_off = await asyncio.to_thread(load_voice_model, self._voice_model)
            if self._voice_off:
                self._voice_model = None
        self._status("[dim]Identifying speakers...[/dim]")
        if self._voice_model is None:
            # The researcher installed the extra to get this; a decline they
            # cannot see reads as "voice ran".
            self._warn(rich_escape(f"Voice pass skipped: {self._voice_off}"))
            self._warn(
                "Speakers told apart from the text alone; "
                "`bristlenose doctor --fetch` fetches the model"
                if fetchable else
                "Speakers told apart from the text alone"
            )

    async def run(self, sid: str, segments: list[TranscriptSegment]) -> list[SpeakerInfo]:
        """Identify one session's speakers, in place on *segments*."""
        # This session's errors, apart from the shared list, so a failure is
        # known per session while sessions run concurrently.
        errors: list[str] = []
        try:
            return await self._run(sid, segments, errors)
        finally:
            self.errors.extend(errors)
            if errors:
                self.failed.add(sid)

    async def _run(
        self, sid: str, segments: list[TranscriptSegment], errors: list[str],
    ) -> list[SpeakerInfo]:
        from bristlenose.stages.s05b_identify_speakers import (
            identify_speaker_roles_heuristic,
            identify_speaker_roles_llm,
            split_single_speaker_llm,
        )
        from bristlenose.stages.s05b_voice import refine_speakers_by_voice

        with _llm_telemetry.stage(TELEMETRY_STAGE), _llm_telemetry.session(sid):
            if self.gate(sid, segments):
                await self._ensure_voice()
                async with self._sem_split:
                    await split_single_speaker_llm(
                        segments, self.llm_client, errors=errors,
                    )
                async with self._sem_voice:
                    rec = await asyncio.to_thread(
                        refine_speakers_by_voice,
                        segments, self._audio_for.get(sid), self._voice_model,
                        unavailable_reason=self._voice_off,
                    )
                self.split_records[sid] = rec.to_dict()
                logger.info(
                    "voice_pass | session=%s | method=%s | elapsed_ms=%d"
                    " | segments=%d | verdicts=%d | relabelled=%d"
                    " | centroid_cos=%s | reason=%s",
                    sid, rec.method, rec.elapsed_ms, rec.segments,
                    rec.voice_verdicts, rec.relabelled, rec.centroid_cos,
                    rec.reason or "-",
                )
            identify_speaker_roles_heuristic(segments)
            async with self._sem_roles:
                return await identify_speaker_roles_llm(
                    segments, self.llm_client, errors=errors,
                )
