"""Pipeline orchestrator: runs all stages in sequence."""

from __future__ import annotations

import asyncio
import logging
import os as _os
from pathlib import Path

from rich.console import Console

# Suppress all tqdm/huggingface_hub progress bars at module level.
# Must be set before any tqdm import; setting inside __init__() is too late.
_os.environ.setdefault("TQDM_DISABLE", "1")
_os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

from bristlenose import __version__
from bristlenose.config import BristlenoseSettings
from bristlenose.manifest import (
    STAGE_CLUSTER_AND_GROUP,
    STAGE_EXTRACT_AUDIO,
    STAGE_IDENTIFY_SPEAKERS,
    STAGE_INGEST,
    STAGE_MERGE_TRANSCRIPT,
    STAGE_PII_REMOVAL,
    STAGE_QUOTE_EXTRACTION,
    STAGE_TOPIC_SEGMENTATION,
    PipelineManifest,
    StageStatus,
    create_manifest,
    get_completed_session_ids,
    load_manifest,
    mark_session_complete,
    mark_stage_complete,
    mark_stage_running,
    write_manifest,
)
from bristlenose.manifest import STAGE_RENDER as _M_STAGE_RENDER
from bristlenose.manifest import STAGE_TRANSCRIBE as _M_STAGE_TRANSCRIBE
from bristlenose.models import (
    ExtractedQuote,
    FileType,
    InputSession,
    PiiCleanTranscript,
    PipelineResult,
    ScreenCluster,
    SessionTopicMap,
    SpeakerRole,
    ThemeGroup,
    TranscriptSegment,
)

logger = logging.getLogger(__name__)
console = Console(width=min(80, Console().width))

_MAX_SESSIONS_NO_CONFIRM = 16


# ---------------------------------------------------------------------------
# CLI output helpers
# ---------------------------------------------------------------------------


def _format_duration(seconds: float) -> str:
    """Format seconds as '0.1s' or '3m 41s'."""
    if seconds >= 60:
        m, s = divmod(int(seconds), 60)
        return f"{m}m {s:02d}s"
    return f"{seconds:.1f}s"


def _print_step(message: str, elapsed: float) -> None:
    """Print a completed pipeline step with green ✓ and right-aligned timing."""
    time_str = _format_duration(elapsed)
    padding = max(1, 58 - len(message))
    console.print(f" [green]✓[/green] {message}{' ' * padding}[dim]{time_str}[/dim]")


def _print_cached_step(message: str) -> None:
    """Print a cached pipeline step with green ✓ and right-aligned '(cached)'."""
    padding = max(1, 58 - len(message))
    console.print(f" [green]✓[/green] {message}{' ' * padding}[dim](cached)[/dim]")


def _is_stage_cached(manifest: PipelineManifest | None, stage: str) -> bool:
    """Return True if *stage* is marked complete in an existing manifest."""
    if manifest is None:
        return False
    record = manifest.stages.get(stage)
    return record is not None and record.status == StageStatus.COMPLETE


_printed_warnings: set[str] = set()


def _print_warn(message: str, link: str = "") -> None:
    """Print a warning line below the most recent step (deduplicated)."""
    if message in _printed_warnings:
        return
    _printed_warnings.add(message)
    console.print(f"   [dim yellow]{message}[/dim yellow]")
    if link:
        console.print(f"   [dim yellow][link={link}]{link}[/link][/dim yellow]")


_MAX_WARN_LEN = 74  # 80 col - 3 indent - small margin


_BILLING_URLS: dict[str, str] = {
    "anthropic": "https://platform.claude.com/settings/billing",
    "openai": "https://platform.openai.com/settings/organization/billing",
    "azure": "https://portal.azure.com/#view/Microsoft_Azure_Billing",
}


def _short_reason(errors: list[str], provider: str = "") -> tuple[str, str]:
    """Extract a short human-readable reason from the first error message.

    Returns:
        (message, link) — link is a billing URL when applicable, else "".
    """
    if not errors:
        return "", ""
    msg = errors[0]
    link = ""
    # Anthropic API errors embed a JSON 'message' field
    if "'message':" in msg:
        import re
        m = re.search(r"'message':\s*'([^']+)'", msg)
        if m:
            msg = m.group(1)
    # Detect billing issues and provide a direct link
    if "credit balance" in msg.lower() and provider in _BILLING_URLS:
        link = _BILLING_URLS[provider]
        msg = "API credit balance too low"
    if len(msg) > _MAX_WARN_LEN:
        msg = msg[:_MAX_WARN_LEN - 1] + "\u2026"
    return msg, link


def _compute_analysis(
    screen_clusters: list[ScreenCluster],
    theme_groups: list[ThemeGroup],
    all_quotes: list[ExtractedQuote],
    sessions: list[InputSession] | None = None,
) -> object | None:
    """Compute analysis data if quotes have sentiments.

    Returns an AnalysisResult or None if no sentiment data is available.
    Pure computation — no LLM calls.
    """
    if not screen_clusters and not theme_groups:
        return None
    if not any(q.sentiment is not None for q in all_quotes):
        return None

    from bristlenose.analysis.matrix import build_section_matrix, build_theme_matrix
    from bristlenose.analysis.signals import detect_signals

    section_matrix = build_section_matrix(screen_clusters)
    theme_matrix = build_theme_matrix(theme_groups)

    if sessions:
        total_participants = sum(1 for s in sessions if s.participant_id.startswith("p"))
    else:
        total_participants = len({q.participant_id for q in all_quotes if q.participant_id.startswith("p")})

    return detect_signals(
        section_matrix, theme_matrix,
        screen_clusters, theme_groups,
        total_participants,
    )


class Pipeline:
    """Orchestrates the full Bristlenose processing pipeline."""

    def __init__(
        self,
        settings: BristlenoseSettings,
        verbose: bool = False,
        on_event: object | None = None,
        estimator: object | None = None,
        skip_confirm: bool = False,
    ) -> None:
        self.settings = settings
        self.verbose = verbose
        # Callable[[PipelineEvent], None] — typed as object to avoid
        # importing timing at module level (lazy import pattern).
        self._on_event = on_event
        # TimingEstimator — typed as object for the same reason.
        self._estimator = estimator
        self._skip_confirm = skip_confirm

        # Logging is configured later (once output_dir is known) via
        # _configure_logging().  Pipeline methods call it at the top of
        # run() / run_analysis_only() / run_transcription_only() /
        # run_render_only() where output_dir is available.
        self._logging_configured = False

    def _configure_logging(self, output_dir: Path) -> None:
        """Set up terminal + log file handlers (idempotent)."""
        if self._logging_configured:
            return
        from bristlenose.logging import setup_logging

        setup_logging(output_dir=output_dir, verbose=self.verbose)
        self._logging_configured = True

    def _emit(self, event: object) -> None:
        """Fire a PipelineEvent to the registered callback (if any)."""
        if self._on_event is not None:
            self._on_event(event)  # type: ignore[operator]

    def _emit_remaining(self, stage: str, elapsed: float) -> None:
        """Emit a revised remaining-time estimate after a stage completes."""
        if self._estimator is None:
            return
        from bristlenose.timing import PipelineEvent

        remaining = self._estimator.stage_completed(stage, elapsed)  # type: ignore[union-attr]
        if remaining is not None:
            self._emit(PipelineEvent(
                kind="remaining", stage=stage, elapsed=elapsed,
                estimate=remaining,
            ))

    def _confirm_large_session_count(self, count: int, source_dir: Path) -> bool:
        """Prompt for confirmation when session count exceeds threshold.

        Returns True to proceed, False to abort.
        """
        from rich.prompt import Confirm

        console.print(
            f"\n[yellow]Found {count} sessions in {source_dir.name}/.[/yellow]"
        )
        return Confirm.ask("Continue?", default=True)

    async def run(self, input_dir: Path, output_dir: Path) -> PipelineResult:
        """Run the full pipeline: ingest → transcribe → analyse → output.

        Args:
            input_dir: Directory containing input files.
            output_dir: Directory for all output.

        Returns:
            PipelineResult with all data and paths.
        """
        import time
        from collections import Counter

        from bristlenose.llm.client import LLMClient
        from bristlenose.stages.extract_audio import extract_audio_for_sessions
        from bristlenose.stages.identify_speakers import (
            SpeakerInfo,
            assign_speaker_codes,
            identify_speaker_roles_heuristic,
            identify_speaker_roles_llm,
            speaker_info_from_dict,
            speaker_info_to_dict,
        )
        from bristlenose.stages.ingest import ingest
        from bristlenose.stages.merge_transcript import (
            merge_transcripts,
            write_raw_transcripts,
            write_raw_transcripts_md,
        )
        from bristlenose.stages.pii_removal import (
            remove_pii,
            write_cooked_transcripts,
            write_cooked_transcripts_md,
            write_pii_summary,
        )
        from bristlenose.stages.quote_clustering import cluster_by_screen
        from bristlenose.stages.quote_extraction import extract_quotes
        from bristlenose.stages.render_html import render_html
        from bristlenose.stages.render_output import (
            render_markdown,
            write_intermediate_json,
            write_pipeline_metadata,
        )
        from bristlenose.stages.thematic_grouping import group_by_theme
        from bristlenose.stages.topic_segmentation import segment_topics

        pipeline_start = time.perf_counter()
        _printed_warnings.clear()
        output_dir.mkdir(parents=True, exist_ok=True)
        self._configure_logging(output_dir)
        write_pipeline_metadata(output_dir, self.settings.project_name)

        # ── Manifest tracking ────────────────────────────────────
        # Load existing manifest for resume, or create fresh.
        _prev_manifest = load_manifest(output_dir) if output_dir.exists() else None
        manifest = create_manifest(self.settings.project_name, __version__)

        # ── Stage 1: Ingest ──────────────────────────────────────
        # Runs before the spinner — ingest is fast (directory scan) and
        # the session-count guard needs terminal input if triggered.
        mark_stage_running(manifest, STAGE_INGEST)
        t0 = time.perf_counter()
        sessions = ingest(input_dir)
        if not sessions:
            console.print("[red]No supported files found.[/red]")
            return self._empty_result(output_dir)

        ingest_elapsed = time.perf_counter() - t0

        # ── Session-count guard ───────────────────────────────────
        if len(sessions) > _MAX_SESSIONS_NO_CONFIRM and not self._skip_confirm:
            if not self._confirm_large_session_count(len(sessions), input_dir):
                return self._empty_result(output_dir)

        # ── Print found-sessions line, then ingest checkmark ──
        console.print(
            f"[dim]{len(sessions)} sessions in {input_dir.name}/[/dim]\n",
        )
        type_counts = Counter(
            f.file_type.value for s in sessions for f in s.files
        )
        type_parts = [f"{n} {t}" for t, n in type_counts.most_common()]
        _print_step(
            f"Ingested {len(sessions)} sessions ({', '.join(type_parts)})",
            ingest_elapsed,
        )
        mark_stage_complete(manifest, STAGE_INGEST)
        write_manifest(manifest, output_dir)

        with console.status("", spinner="dots") as status:
            status.renderable.frames = [" " + f for f in status.renderable.frames]

            # ── Time estimate ────────────────────────────────────────
            from bristlenose.timing import (
                STAGE_CLUSTER,
                STAGE_QUOTES,
                STAGE_RENDER,
                STAGE_SPEAKERS,
                STAGE_TOPICS,
                STAGE_TRANSCRIBE,
                PipelineEvent,
                StageActual,
            )

            total_audio_mins = sum(
                (f.duration_seconds or 0) for s in sessions for f in s.files
            ) / 60.0

            if self._estimator is not None:
                _est = self._estimator.initial_estimate(
                    total_audio_mins, len(sessions),
                    skip_transcription=self.settings.skip_transcription,
                )
                if _est is not None:
                    self._emit(PipelineEvent(
                        kind="estimate", estimate=_est,
                    ))

            _stage_actuals: dict[str, StageActual] = {}
            _n_sessions = float(len(sessions))

            # ── Stage 2: Extract audio from video ────────────────────
            mark_stage_running(manifest, STAGE_EXTRACT_AUDIO)
            status.update("[dim]Extracting audio...[/dim]")
            t0 = time.perf_counter()
            # Temp files go in .bristlenose/temp/
            temp_dir = output_dir / ".bristlenose" / "temp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            sessions = await extract_audio_for_sessions(sessions, temp_dir)
            _print_step(
                f"Extracted audio from {len(sessions)} sessions",
                time.perf_counter() - t0,
            )
            mark_stage_complete(manifest, STAGE_EXTRACT_AUDIO)
            write_manifest(manifest, output_dir)

            # ── Intermediate directory for cached JSON ────────────────
            intermediate = output_dir / ".bristlenose" / "intermediate"

            # ── Stages 3-5: Parse existing transcripts + Transcribe ──
            _ss_path = intermediate / "session_segments.json"
            if (
                _is_stage_cached(_prev_manifest, _M_STAGE_TRANSCRIBE)
                and _ss_path.exists()
            ):
                import json as _json

                _ss_raw = _json.loads(_ss_path.read_text(encoding="utf-8"))
                session_segments = {
                    sid: [TranscriptSegment.model_validate(s) for s in segs]
                    for sid, segs in _ss_raw.items()
                }
                total_segments = sum(len(s) for s in session_segments.values())
                _print_cached_step(
                    f"Transcribed {len(sessions)} sessions"
                    f" ({total_segments} segments)",
                )
            else:
                import json as _json

                # Per-session resume: load cached segments for completed
                # sessions and only transcribe the remaining ones.
                _cached_tx_sids = get_completed_session_ids(
                    _prev_manifest, _M_STAGE_TRANSCRIBE,
                )
                _cached_segments: dict[str, list[TranscriptSegment]] = {}
                if _cached_tx_sids and _ss_path.exists():
                    _ss_raw = _json.loads(
                        _ss_path.read_text(encoding="utf-8"),
                    )
                    _cached_segments = {
                        sid: [
                            TranscriptSegment.model_validate(s) for s in segs
                        ]
                        for sid, segs in _ss_raw.items()
                        if sid in _cached_tx_sids
                    }

                _remaining_sessions = [
                    s for s in sessions
                    if s.session_id not in _cached_tx_sids
                ]

                mark_stage_running(manifest, _M_STAGE_TRANSCRIBE)
                # Carry forward session records from previous manifest
                if _cached_tx_sids and _prev_manifest is not None:
                    _prev_tx_rec = _prev_manifest.stages.get(
                        _M_STAGE_TRANSCRIBE,
                    )
                    if _prev_tx_rec and _prev_tx_rec.sessions:
                        rec_tx = manifest.stages[_M_STAGE_TRANSCRIBE]
                        rec_tx.sessions = {
                            sid: sr
                            for sid, sr in _prev_tx_rec.sessions.items()
                            if sr.status == StageStatus.COMPLETE
                        }

                status.update("[dim]Transcribing...[/dim]")
                t0 = time.perf_counter()

                if _remaining_sessions:
                    def _on_transcribe_progress(
                        current: int, total: int,
                    ) -> None:
                        status.update(
                            f"[dim]Transcribing..."
                            f" ({current}/{total} files)[/dim]"
                        )

                    _fresh_segments = await self._gather_all_segments(
                        _remaining_sessions,
                        on_progress=_on_transcribe_progress,
                    )
                    for sid in _fresh_segments:
                        mark_session_complete(
                            manifest, _M_STAGE_TRANSCRIBE, sid,
                        )
                else:
                    _fresh_segments = {}

                session_segments = {**_cached_segments, **_fresh_segments}

                # Write intermediate JSON for resume
                if self.settings.write_intermediate:
                    intermediate.mkdir(parents=True, exist_ok=True)
                    _ss_data = {
                        sid: [seg.model_dump(mode="json") for seg in segs]
                        for sid, segs in session_segments.items()
                    }
                    _ss_path.write_text(
                        _json.dumps(_ss_data, indent=2), encoding="utf-8",
                    )

                total_segments = sum(
                    len(s) for s in session_segments.values()
                )
                total_audio = sum(
                    f.duration_seconds or 0
                    for s in sessions for f in s.files
                )
                audio_str = (
                    _format_duration(total_audio) if total_audio else ""
                )
                _n_new_tx = len(_remaining_sessions)
                if _cached_segments and _n_new_tx:
                    msg = (
                        f"Transcribed {len(sessions)} sessions"
                        f" ({total_segments} segments,"
                        f" {_n_new_tx} new sessions)"
                    )
                else:
                    msg = (
                        f"Transcribed {len(sessions)} sessions"
                        f" ({total_segments} segments"
                    )
                    if audio_str:
                        msg += f", {audio_str} audio"
                    msg += ")"
                _transcribe_elapsed = time.perf_counter() - t0
                _print_step(msg, _transcribe_elapsed)
                _stage_actuals[STAGE_TRANSCRIBE] = StageActual(
                    elapsed=_transcribe_elapsed,
                    input_size=total_audio_mins,
                )
                self._emit_remaining(STAGE_TRANSCRIBE, _transcribe_elapsed)
            mark_stage_complete(manifest, _M_STAGE_TRANSCRIBE)
            write_manifest(manifest, output_dir)

            # ── Cost estimate before LLM stages ──────────────────────
            from bristlenose.llm.pricing import estimate_pipeline_cost

            est = estimate_pipeline_cost(self.settings.llm_model, len(sessions))
            if est is not None:
                console.print(
                    f"  [dim]Estimated LLM cost: ~${est:.2f}"
                    f" for {len(sessions)} sessions"
                    f" ({self.settings.llm_model})[/dim]\n"
                )

            # ── Stage 5b: Speaker role identification ────────────────
            import json as _json

            _si_dir = intermediate / "speaker-info"
            llm_client: LLMClient | None = None
            concurrency = self.settings.llm_concurrency

            # Check for fully cached speaker ID stage
            if (
                _is_stage_cached(_prev_manifest, STAGE_IDENTIFY_SPEAKERS)
                and _si_dir.is_dir()
                and all(
                    (_si_dir / f"{s.session_id}.json").exists()
                    for s in sessions
                    if s.session_id in session_segments
                )
            ):
                # Load all cached speaker info + segments with roles
                all_speaker_infos: dict[str, list] = {}
                for s in sessions:
                    sid = s.session_id
                    if sid not in session_segments:
                        continue
                    _si_data = _json.loads(
                        (_si_dir / f"{sid}.json").read_text(encoding="utf-8")
                    )
                    all_speaker_infos[sid] = [
                        speaker_info_from_dict(d)
                        for d in _si_data["speaker_infos"]
                    ]
                    # Restore segments with speaker roles
                    session_segments[sid] = [
                        TranscriptSegment.model_validate(seg)
                        for seg in _si_data["segments_with_roles"]
                    ]
                _print_cached_step("Identified speakers")
            else:
                # Per-session resume: load cached speaker info for completed
                # sessions and only run LLM on the remaining ones.
                _cached_si_sids = get_completed_session_ids(
                    _prev_manifest, STAGE_IDENTIFY_SPEAKERS,
                )
                all_speaker_infos = {}
                if _cached_si_sids and _si_dir.is_dir():
                    for sid in _cached_si_sids:
                        _si_file = _si_dir / f"{sid}.json"
                        if _si_file.exists():
                            _si_data = _json.loads(
                                _si_file.read_text(encoding="utf-8"),
                            )
                            all_speaker_infos[sid] = [
                                speaker_info_from_dict(d)
                                for d in _si_data["speaker_infos"]
                            ]
                            # Restore segments with speaker roles
                            session_segments[sid] = [
                                TranscriptSegment.model_validate(seg)
                                for seg in _si_data["segments_with_roles"]
                            ]

                _remaining_si_sids = {
                    sid for sid in session_segments
                    if sid not in _cached_si_sids
                }

                mark_stage_running(manifest, STAGE_IDENTIFY_SPEAKERS)
                # Carry forward session records from previous manifest
                if _cached_si_sids and _prev_manifest is not None:
                    _prev_si_rec = _prev_manifest.stages.get(
                        STAGE_IDENTIFY_SPEAKERS,
                    )
                    if _prev_si_rec and _prev_si_rec.sessions:
                        rec_si = manifest.stages[STAGE_IDENTIFY_SPEAKERS]
                        rec_si.sessions = {
                            sid: sr
                            for sid, sr in _prev_si_rec.sessions.items()
                            if sr.status == StageStatus.COMPLETE
                        }

                status.update("[dim]Identifying speakers...[/dim]")
                t0 = time.perf_counter()
                llm_client = LLMClient(self.settings)
                _speaker_errors: list[str] = []

                if _remaining_si_sids:
                    # Heuristic pass for remaining sessions
                    for sid in _remaining_si_sids:
                        identify_speaker_roles_heuristic(
                            session_segments[sid],
                        )

                    # LLM refinement concurrently
                    _sem_5b = asyncio.Semaphore(concurrency)

                    async def _identify(
                        sid: str, segments: list[TranscriptSegment],
                    ) -> tuple[str, list]:
                        async with _sem_5b:
                            infos = await identify_speaker_roles_llm(
                                segments, llm_client,
                                errors=_speaker_errors,
                            )
                            return sid, infos

                    _results_5b = await asyncio.gather(*(
                        _identify(sid, session_segments[sid])
                        for sid in _remaining_si_sids
                    ))
                    for sid, infos in _results_5b:
                        all_speaker_infos[sid] = infos
                        mark_session_complete(
                            manifest, STAGE_IDENTIFY_SPEAKERS, sid,
                            provider=self.settings.llm_provider,
                            model=self.settings.llm_model,
                        )

                    # Write speaker info cache for fresh sessions
                    if self.settings.write_intermediate:
                        _si_dir.mkdir(parents=True, exist_ok=True)
                        for sid in _remaining_si_sids:
                            _si_data = {
                                "speaker_infos": [
                                    speaker_info_to_dict(info)
                                    for info in all_speaker_infos.get(sid, [])
                                ],
                                "segments_with_roles": [
                                    seg.model_dump(mode="json")
                                    for seg in session_segments[sid]
                                ],
                            }
                            (_si_dir / f"{sid}.json").write_text(
                                _json.dumps(_si_data, indent=2),
                                encoding="utf-8",
                            )

                _speakers_elapsed = time.perf_counter() - t0
                _n_new_si = len(_remaining_si_sids)
                if _cached_si_sids and _n_new_si:
                    _print_step(
                        f"Identified speakers ({_n_new_si} new sessions)",
                        _speakers_elapsed,
                    )
                else:
                    _print_step("Identified speakers", _speakers_elapsed)
                _stage_actuals[STAGE_SPEAKERS] = StageActual(
                    elapsed=_speakers_elapsed, input_size=_n_sessions,
                )
                self._emit_remaining(STAGE_SPEAKERS, _speakers_elapsed)
                if _speaker_errors:
                    _print_warn(
                        *_short_reason(
                            _speaker_errors, self.settings.llm_provider,
                        )
                    )

            # assign_speaker_codes() always re-runs — global numbering
            all_label_code_maps: dict[str, dict[str, str]] = {}
            next_pnum = 1
            for session in sessions:
                sid = session.session_id
                segments = session_segments.get(sid, [])
                if not segments:
                    continue
                label_map, next_pnum = assign_speaker_codes(
                    next_pnum, segments,
                )
                all_label_code_maps[sid] = label_map
                # Update session's participant_id from assigned codes
                p_codes = [
                    c for c in label_map.values() if c.startswith("p")
                ]
                if p_codes:
                    session.participant_id = p_codes[0]
                    session.participant_number = int(p_codes[0][1:])

            mark_stage_complete(manifest, STAGE_IDENTIFY_SPEAKERS)
            write_manifest(manifest, output_dir)

            # ── Stage 6: Merge and write raw transcripts ─────────────
            mark_stage_running(manifest, STAGE_MERGE_TRANSCRIPT)
            status.update("[dim]Merging transcripts...[/dim]")
            t0 = time.perf_counter()
            transcripts = merge_transcripts(sessions, session_segments)
            raw_dir = output_dir / "transcripts-raw"
            write_raw_transcripts(transcripts, raw_dir)
            write_raw_transcripts_md(transcripts, raw_dir)
            _print_step("Merged transcripts", time.perf_counter() - t0)
            mark_stage_complete(manifest, STAGE_MERGE_TRANSCRIPT)
            write_manifest(manifest, output_dir)

            # ── Stage 7: PII removal ────────────────────────────────
            if self.settings.pii_enabled:
                mark_stage_running(manifest, STAGE_PII_REMOVAL)
                status.update("[dim]Removing PII...[/dim]")
                t0 = time.perf_counter()
                clean_transcripts, pii_redactions = remove_pii(
                    transcripts, self.settings,
                )
                cooked_dir = output_dir / "transcripts-cooked"
                write_cooked_transcripts(clean_transcripts, cooked_dir)
                write_cooked_transcripts_md(clean_transcripts, cooked_dir)
                write_pii_summary(pii_redactions, output_dir)
                _print_step(
                    f"Redacted PII ({len(pii_redactions)} entities)",
                    time.perf_counter() - t0,
                )
                mark_stage_complete(manifest, STAGE_PII_REMOVAL)
                write_manifest(manifest, output_dir)
            else:
                # Pass through without PII removal
                clean_transcripts = [
                    PiiCleanTranscript(
                        session_id=t.session_id,
                        participant_id=t.participant_id,
                        source_file=t.source_file,
                        session_date=t.session_date,
                        duration_seconds=t.duration_seconds,
                        segments=t.segments,
                    )
                    for t in transcripts
                ]

            # ── Stage 8: Topic segmentation ──────────────────────────
            _tb_path = intermediate / "topic_boundaries.json"
            if (
                _is_stage_cached(_prev_manifest, STAGE_TOPIC_SEGMENTATION)
                and _tb_path.exists()
            ):
                import json as _json

                topic_maps = [
                    SessionTopicMap.model_validate(obj)
                    for obj in _json.loads(_tb_path.read_text(encoding="utf-8"))
                ]
                total_boundaries = sum(len(m.boundaries) for m in topic_maps)
                _print_cached_step(
                    f"Segmented {total_boundaries} topic boundaries",
                )
            else:
                # Per-session resume: load cached topic maps for completed
                # sessions and only run LLM on the remaining ones.
                import json as _json

                _cached_topic_sids = get_completed_session_ids(
                    _prev_manifest, STAGE_TOPIC_SEGMENTATION,
                )
                _cached_topic_maps: list[SessionTopicMap] = []
                if _cached_topic_sids and _tb_path.exists():
                    _cached_topic_maps = [
                        SessionTopicMap.model_validate(obj)
                        for obj in _json.loads(
                            _tb_path.read_text(encoding="utf-8")
                        )
                        if obj.get("session_id") in _cached_topic_sids
                    ]

                _remaining_transcripts = [
                    t for t in clean_transcripts
                    if t.session_id not in _cached_topic_sids
                ]

                mark_stage_running(manifest, STAGE_TOPIC_SEGMENTATION)
                # Carry forward session records from previous manifest
                if _cached_topic_sids and _prev_manifest is not None:
                    _prev_rec = _prev_manifest.stages.get(
                        STAGE_TOPIC_SEGMENTATION,
                    )
                    if _prev_rec and _prev_rec.sessions:
                        rec = manifest.stages[STAGE_TOPIC_SEGMENTATION]
                        rec.sessions = {
                            sid: sr
                            for sid, sr in _prev_rec.sessions.items()
                            if sr.status == StageStatus.COMPLETE
                        }

                status.update("[dim]Segmenting topics...[/dim]")
                t0 = time.perf_counter()
                _seg_errors: list[str] = []

                if _remaining_transcripts:
                    _fresh_topic_maps = await segment_topics(
                        _remaining_transcripts, llm_client,
                        concurrency=concurrency, errors=_seg_errors,
                    )
                    # Record per-session completion
                    for tm in _fresh_topic_maps:
                        mark_session_complete(
                            manifest, STAGE_TOPIC_SEGMENTATION,
                            tm.session_id,
                            provider=self.settings.llm_provider,
                            model=self.settings.llm_model,
                        )
                else:
                    _fresh_topic_maps = []

                topic_maps = _cached_topic_maps + _fresh_topic_maps

                if self.settings.write_intermediate:
                    write_intermediate_json(
                        topic_maps, "topic_boundaries.json", output_dir,
                        self.settings.project_name,
                    )
                total_boundaries = sum(len(m.boundaries) for m in topic_maps)
                _topics_elapsed = time.perf_counter() - t0

                _n_new = len(_remaining_transcripts)
                if _cached_topic_maps and _n_new:
                    _msg_8 = (
                        f"Segmented {total_boundaries} topic boundaries"
                        f" ({_n_new} new sessions)"
                    )
                else:
                    _msg_8 = f"Segmented {total_boundaries} topic boundaries"
                _print_step(_msg_8, _topics_elapsed)

                _stage_actuals[STAGE_TOPICS] = StageActual(
                    elapsed=_topics_elapsed, input_size=_n_sessions,
                )
                self._emit_remaining(STAGE_TOPICS, _topics_elapsed)
                if _seg_errors:
                    _print_warn(*_short_reason(_seg_errors, self.settings.llm_provider))
            mark_stage_complete(manifest, STAGE_TOPIC_SEGMENTATION)
            write_manifest(manifest, output_dir)

            # ── Stage 9: Quote extraction ────────────────────────────
            _eq_path = intermediate / "extracted_quotes.json"
            if (
                _is_stage_cached(_prev_manifest, STAGE_QUOTE_EXTRACTION)
                and _eq_path.exists()
            ):
                import json as _json

                all_quotes = [
                    ExtractedQuote.model_validate(obj)
                    for obj in _json.loads(_eq_path.read_text(encoding="utf-8"))
                ]
                _print_cached_step(f"Extracted {len(all_quotes)} quotes")
            else:
                # Per-session resume: load cached quotes for completed
                # sessions and only run LLM on the remaining ones.
                import json as _json

                _cached_quote_sids = get_completed_session_ids(
                    _prev_manifest, STAGE_QUOTE_EXTRACTION,
                )
                _cached_quotes: list[ExtractedQuote] = []
                if _cached_quote_sids and _eq_path.exists():
                    _cached_quotes = [
                        ExtractedQuote.model_validate(obj)
                        for obj in _json.loads(
                            _eq_path.read_text(encoding="utf-8")
                        )
                        if obj.get("session_id") in _cached_quote_sids
                    ]

                _remaining_transcripts_q = [
                    t for t in clean_transcripts
                    if t.session_id not in _cached_quote_sids
                ]
                _remaining_topic_maps = [
                    tm for tm in topic_maps
                    if tm.session_id not in _cached_quote_sids
                ]

                mark_stage_running(manifest, STAGE_QUOTE_EXTRACTION)
                # Carry forward session records from previous manifest
                if _cached_quote_sids and _prev_manifest is not None:
                    _prev_rec_q = _prev_manifest.stages.get(
                        STAGE_QUOTE_EXTRACTION,
                    )
                    if _prev_rec_q and _prev_rec_q.sessions:
                        rec_q = manifest.stages[STAGE_QUOTE_EXTRACTION]
                        rec_q.sessions = {
                            sid: sr
                            for sid, sr in _prev_rec_q.sessions.items()
                            if sr.status == StageStatus.COMPLETE
                        }

                status.update("[dim]Extracting quotes...[/dim]")
                t0 = time.perf_counter()
                _quote_errors: list[str] = []

                if _remaining_transcripts_q:
                    _fresh_quotes = await extract_quotes(
                        _remaining_transcripts_q,
                        _remaining_topic_maps,
                        llm_client,
                        min_quote_words=self.settings.min_quote_words,
                        concurrency=concurrency,
                        errors=_quote_errors,
                    )
                    # Record per-session completion — derive session_ids
                    # from the transcripts that were processed.
                    for t in _remaining_transcripts_q:
                        mark_session_complete(
                            manifest, STAGE_QUOTE_EXTRACTION,
                            t.session_id,
                            provider=self.settings.llm_provider,
                            model=self.settings.llm_model,
                        )
                else:
                    _fresh_quotes = []

                all_quotes = _cached_quotes + _fresh_quotes

                if self.settings.write_intermediate:
                    write_intermediate_json(
                        all_quotes, "extracted_quotes.json", output_dir,
                        self.settings.project_name,
                    )
                _quotes_elapsed = time.perf_counter() - t0

                _n_new_q = len(_remaining_transcripts_q)
                if _cached_quotes and _n_new_q:
                    _msg_9 = (
                        f"Extracted {len(all_quotes)} quotes"
                        f" ({_n_new_q} new sessions)"
                    )
                else:
                    _msg_9 = f"Extracted {len(all_quotes)} quotes"
                _print_step(_msg_9, _quotes_elapsed)

                _stage_actuals[STAGE_QUOTES] = StageActual(
                    elapsed=_quotes_elapsed, input_size=_n_sessions,
                )
                self._emit_remaining(STAGE_QUOTES, _quotes_elapsed)
                if _quote_errors:
                    _print_warn(*_short_reason(_quote_errors, self.settings.llm_provider))
            mark_stage_complete(manifest, STAGE_QUOTE_EXTRACTION)
            write_manifest(manifest, output_dir)

            # ── Stages 10+11: Cluster by screen + thematic grouping ──
            _sc_path = intermediate / "screen_clusters.json"
            _tg_path = intermediate / "theme_groups.json"
            if (
                _is_stage_cached(_prev_manifest, STAGE_CLUSTER_AND_GROUP)
                and _sc_path.exists()
                and _tg_path.exists()
            ):
                import json as _json

                screen_clusters = [
                    ScreenCluster.model_validate(obj)
                    for obj in _json.loads(_sc_path.read_text(encoding="utf-8"))
                ]
                theme_groups = [
                    ThemeGroup.model_validate(obj)
                    for obj in _json.loads(_tg_path.read_text(encoding="utf-8"))
                ]
                _print_cached_step(
                    f"Clustered {len(screen_clusters)} screens"
                    f" · Grouped {len(theme_groups)} themes",
                )
            else:
                mark_stage_running(manifest, STAGE_CLUSTER_AND_GROUP)
                status.update("[dim]Clustering and grouping...[/dim]")
                t0 = time.perf_counter()
                screen_clusters, theme_groups = await asyncio.gather(
                    cluster_by_screen(all_quotes, llm_client),
                    group_by_theme(all_quotes, llm_client),
                )
                if self.settings.write_intermediate:
                    write_intermediate_json(
                        screen_clusters, "screen_clusters.json", output_dir,
                        self.settings.project_name,
                    )
                    write_intermediate_json(
                        theme_groups, "theme_groups.json", output_dir,
                        self.settings.project_name,
                    )
                _cluster_elapsed = time.perf_counter() - t0
                _print_step(
                    f"Clustered {len(screen_clusters)} screens"
                    f" · Grouped {len(theme_groups)} themes",
                    _cluster_elapsed,
                )
                _stage_actuals[STAGE_CLUSTER] = StageActual(
                    elapsed=_cluster_elapsed, input_size=_n_sessions,
                )
                self._emit_remaining(STAGE_CLUSTER, _cluster_elapsed)
            mark_stage_complete(manifest, STAGE_CLUSTER_AND_GROUP)
            write_manifest(manifest, output_dir)

            # ── People file ───────────────────────────────────────────
            status.update("[dim]Updating people file...[/dim]")
            from bristlenose.people import (
                auto_populate_names,
                build_display_name_map,
                compute_participant_stats,
                extract_names_from_labels,
                load_people_file,
                merge_people,
                suggest_short_names,
                write_people_file,
            )

            existing_people = load_people_file(output_dir)
            computed_stats = compute_participant_stats(sessions, transcripts)
            people = merge_people(existing_people, computed_stats)

            # Auto-populate names from speaker labels and LLM extraction.
            label_names = extract_names_from_labels(transcripts)
            pid_speaker_info: dict[str, SpeakerInfo] = {}
            for sid, infos in all_speaker_infos.items():
                label_code_map = all_label_code_maps.get(sid, {})
                for info in infos:
                    code = label_code_map.get(info.speaker_label, "")
                    if not code:
                        continue
                    if info.role == SpeakerRole.PARTICIPANT:
                        pid_speaker_info[code] = info
                    elif info.role == SpeakerRole.RESEARCHER and code.startswith("m"):
                        pid_speaker_info[code] = info
            auto_populate_names(people, pid_speaker_info, label_names)
            suggest_short_names(people)

            write_people_file(people, output_dir)
            display_names = build_display_name_map(people)

            # ── Stage 12: Render output ──────────────────────────────
            mark_stage_running(manifest, _M_STAGE_RENDER)
            status.update("[dim]Rendering output...[/dim]")
            t0 = time.perf_counter()
            analysis = _compute_analysis(
                screen_clusters, theme_groups, all_quotes, sessions,
            )
            render_markdown(
                screen_clusters,
                theme_groups,
                sessions,
                self.settings.project_name,
                output_dir,
                all_quotes=all_quotes,
                display_names=display_names,
                people=people,
            )
            report_path = render_html(
                screen_clusters,
                theme_groups,
                sessions,
                self.settings.project_name,
                output_dir,
                all_quotes=all_quotes,
                color_scheme=self.settings.color_scheme,
                display_names=display_names,
                people=people,
                transcripts=transcripts,
                analysis=analysis,
            )
            _render_elapsed = time.perf_counter() - t0
            _print_step("Rendered report", _render_elapsed)
            _stage_actuals[STAGE_RENDER] = StageActual(
                elapsed=_render_elapsed, input_size=_n_sessions,
            )
            mark_stage_complete(manifest, _M_STAGE_RENDER)
            write_manifest(manifest, output_dir)

        elapsed = time.perf_counter() - pipeline_start

        # Record actuals for future estimates.
        if self._estimator is not None:
            self._estimator.record_run(_stage_actuals)  # type: ignore[union-attr]

        return PipelineResult(
            project_name=self.settings.project_name,
            participants=sessions,
            raw_transcripts=transcripts,
            clean_transcripts=clean_transcripts,
            screen_clusters=screen_clusters,
            theme_groups=theme_groups,
            output_dir=output_dir,
            report_path=report_path,
            people=people,
            elapsed_seconds=elapsed,
            llm_input_tokens=llm_client.tracker.input_tokens if llm_client else 0,
            llm_output_tokens=llm_client.tracker.output_tokens if llm_client else 0,
            llm_calls=llm_client.tracker.calls if llm_client else 0,
            llm_model=self.settings.llm_model,
            llm_provider=self.settings.llm_provider,
            total_quotes=len(all_quotes),
        )

    async def run_transcription_only(
        self, input_dir: Path, output_dir: Path
    ) -> PipelineResult:
        """Run only ingestion and transcription (no LLM analysis).

        Useful for producing raw transcripts without needing an API key.
        """
        import time
        from collections import Counter

        from bristlenose.stages.extract_audio import extract_audio_for_sessions
        from bristlenose.stages.identify_speakers import identify_speaker_roles_heuristic
        from bristlenose.stages.ingest import ingest
        from bristlenose.stages.merge_transcript import (
            merge_transcripts,
            write_raw_transcripts,
            write_raw_transcripts_md,
        )

        pipeline_start = time.perf_counter()
        output_dir.mkdir(parents=True, exist_ok=True)
        self._configure_logging(output_dir)

        # ── Stage 1: Ingest ──
        t0 = time.perf_counter()
        sessions = ingest(input_dir)
        if not sessions:
            console.print("[red]No supported files found.[/red]")
            return self._empty_result(output_dir)

        ingest_elapsed = time.perf_counter() - t0

        # ── Session-count guard ───────────────────────────────────
        if len(sessions) > _MAX_SESSIONS_NO_CONFIRM and not self._skip_confirm:
            if not self._confirm_large_session_count(len(sessions), input_dir):
                return self._empty_result(output_dir)

        # ── Print found-sessions line, then ingest checkmark ──
        console.print(
            f"[dim]{len(sessions)} sessions in {input_dir.name}/[/dim]\n",
        )
        type_counts = Counter(
            f.file_type.value for s in sessions for f in s.files
        )
        type_parts = [f"{n} {t}" for t, n in type_counts.most_common()]
        _print_step(
            f"Ingested {len(sessions)} sessions ({', '.join(type_parts)})",
            ingest_elapsed,
        )

        with console.status("", spinner="dots") as status:
            status.renderable.frames = [" " + f for f in status.renderable.frames]

            # ── Stage 2: Extract audio ──
            status.update("[dim]Extracting audio...[/dim]")
            t0 = time.perf_counter()
            temp_dir = output_dir / ".bristlenose" / "temp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            sessions = await extract_audio_for_sessions(sessions, temp_dir)
            _print_step(
                f"Extracted audio from {len(sessions)} sessions",
                time.perf_counter() - t0,
            )

            # ── Stages 3-5: Transcribe ──
            status.update("[dim]Transcribing...[/dim]")
            t0 = time.perf_counter()

            def _on_transcribe_progress(current: int, total: int) -> None:
                status.update(f"[dim]Transcribing... ({current}/{total} files)[/dim]")

            session_segments = await self._gather_all_segments(
                sessions, on_progress=_on_transcribe_progress
            )
            total_segments = sum(len(s) for s in session_segments.values())
            total_audio = sum(
                f.duration_seconds or 0 for s in sessions for f in s.files
            )
            audio_str = _format_duration(total_audio) if total_audio else ""
            msg = f"Transcribed {len(sessions)} sessions ({total_segments} segments"
            if audio_str:
                msg += f", {audio_str} audio"
            msg += ")"
            _print_step(msg, time.perf_counter() - t0)

            # ── Heuristic speaker identification (no LLM) ──
            status.update("[dim]Identifying speakers...[/dim]")
            t0 = time.perf_counter()
            for pid, segments in session_segments.items():
                identify_speaker_roles_heuristic(segments)
            _print_step("Identified speakers (heuristic)", time.perf_counter() - t0)

            # ── Merge and write transcripts ──
            status.update("[dim]Merging transcripts...[/dim]")
            t0 = time.perf_counter()
            transcripts = merge_transcripts(sessions, session_segments)
            raw_dir = output_dir / "transcripts-raw"
            write_raw_transcripts(transcripts, raw_dir)
            write_raw_transcripts_md(transcripts, raw_dir)
            _print_step("Merged transcripts", time.perf_counter() - t0)

        # People file (stats only, no rendering)
        from bristlenose.people import (
            auto_populate_names,
            compute_participant_stats,
            extract_names_from_labels,
            load_people_file,
            merge_people,
            suggest_short_names,
            write_people_file,
        )

        existing_people = load_people_file(output_dir)
        computed_stats = compute_participant_stats(sessions, transcripts)
        people = merge_people(existing_people, computed_stats)

        label_names = extract_names_from_labels(transcripts)
        auto_populate_names(people, {}, label_names)
        suggest_short_names(people)

        write_people_file(people, output_dir)

        elapsed = time.perf_counter() - pipeline_start

        return PipelineResult(
            project_name=self.settings.project_name,
            participants=sessions,
            raw_transcripts=transcripts,
            clean_transcripts=[],
            screen_clusters=[],
            theme_groups=[],
            output_dir=output_dir,
            people=people,
            elapsed_seconds=elapsed,
        )

    async def run_analysis_only(
        self, transcripts_dir: Path, output_dir: Path
    ) -> PipelineResult:
        """Run LLM analysis on existing transcript files.

        Loads .txt transcripts from a directory and runs stages 8-12.
        """
        import time

        from bristlenose.llm.client import LLMClient
        from bristlenose.stages.quote_clustering import cluster_by_screen
        from bristlenose.stages.quote_extraction import extract_quotes
        from bristlenose.stages.render_html import render_html
        from bristlenose.stages.render_output import (
            render_markdown,
            write_intermediate_json,
            write_pipeline_metadata,
        )
        from bristlenose.stages.thematic_grouping import group_by_theme
        from bristlenose.stages.topic_segmentation import segment_topics

        pipeline_start = time.perf_counter()
        _printed_warnings.clear()
        output_dir.mkdir(parents=True, exist_ok=True)
        self._configure_logging(output_dir)
        write_pipeline_metadata(output_dir, self.settings.project_name)

        # Load existing transcripts from text files
        clean_transcripts = load_transcripts_from_dir(transcripts_dir)
        if not clean_transcripts:
            console.print("[red]No transcript files found.[/red]")
            return self._empty_result(output_dir)

        # ── Session-count guard ───────────────────────────────────
        if len(clean_transcripts) > _MAX_SESSIONS_NO_CONFIRM and not self._skip_confirm:
            if not self._confirm_large_session_count(
                len(clean_transcripts), transcripts_dir
            ):
                return self._empty_result(output_dir)

        llm_client = LLMClient(self.settings)
        concurrency = self.settings.llm_concurrency

        console.print(
            f"[dim]{len(clean_transcripts)} transcripts in"
            f" {transcripts_dir.name}/[/dim]",
        )

        from bristlenose.llm.pricing import estimate_pipeline_cost

        est = estimate_pipeline_cost(
            self.settings.llm_model, len(clean_transcripts),
        )
        if est is not None:
            console.print(
                f"  [dim]Estimated LLM cost: ~${est:.2f}"
                f" for {len(clean_transcripts)} sessions"
                f" ({self.settings.llm_model})[/dim]\n"
            )
        else:
            console.print()  # blank line before stages

        with console.status("", spinner="dots") as status:
            status.renderable.frames = [" " + f for f in status.renderable.frames]

            # ── Topic segmentation ──
            status.update("[dim]Segmenting topics...[/dim]")
            t0 = time.perf_counter()
            _seg_errors_a: list[str] = []
            topic_maps = await segment_topics(
                clean_transcripts, llm_client, concurrency=concurrency,
                errors=_seg_errors_a,
            )
            if self.settings.write_intermediate:
                write_intermediate_json(
                    topic_maps, "topic_boundaries.json", output_dir,
                    self.settings.project_name,
                )
            total_boundaries = sum(len(m.boundaries) for m in topic_maps)
            _print_step(
                f"Segmented {total_boundaries} topic boundaries",
                time.perf_counter() - t0,
            )
            if _seg_errors_a:
                _print_warn(*_short_reason(_seg_errors_a, self.settings.llm_provider))

            # ── Quote extraction ──
            status.update("[dim]Extracting quotes...[/dim]")
            t0 = time.perf_counter()
            _quote_errors_a: list[str] = []
            all_quotes = await extract_quotes(
                clean_transcripts, topic_maps, llm_client,
                min_quote_words=self.settings.min_quote_words,
                concurrency=concurrency,
                errors=_quote_errors_a,
            )
            if self.settings.write_intermediate:
                write_intermediate_json(
                    all_quotes, "extracted_quotes.json", output_dir,
                    self.settings.project_name,
                )
            _print_step(
                f"Extracted {len(all_quotes)} quotes",
                time.perf_counter() - t0,
            )
            if _quote_errors_a:
                _print_warn(*_short_reason(_quote_errors_a, self.settings.llm_provider))

            # ── Cluster + group ──
            status.update("[dim]Clustering and grouping...[/dim]")
            t0 = time.perf_counter()
            screen_clusters, theme_groups = await asyncio.gather(
                cluster_by_screen(all_quotes, llm_client),
                group_by_theme(all_quotes, llm_client),
            )
            if self.settings.write_intermediate:
                write_intermediate_json(
                    screen_clusters, "screen_clusters.json", output_dir,
                    self.settings.project_name,
                )
                write_intermediate_json(
                    theme_groups, "theme_groups.json", output_dir,
                    self.settings.project_name,
                )
            _print_step(
                f"Clustered {len(screen_clusters)} screens"
                f" · Grouped {len(theme_groups)} themes",
                time.perf_counter() - t0,
            )

            # ── Render ──
            status.update("[dim]Rendering output...[/dim]")
            t0 = time.perf_counter()

            from bristlenose.people import build_display_name_map, load_people_file

            people = load_people_file(output_dir)
            display_names = build_display_name_map(people) if people else {}

            analysis = _compute_analysis(
                screen_clusters, theme_groups, all_quotes,
            )
            render_markdown(
                screen_clusters, theme_groups, [],
                self.settings.project_name, output_dir,
                all_quotes=all_quotes,
                display_names=display_names,
                people=people,
            )
            report_path = render_html(
                screen_clusters, theme_groups, [],
                self.settings.project_name, output_dir,
                all_quotes=all_quotes,
                color_scheme=self.settings.color_scheme,
                display_names=display_names,
                people=people,
                transcripts=clean_transcripts,
                analysis=analysis,
            )
            _print_step("Rendered report", time.perf_counter() - t0)

        elapsed = time.perf_counter() - pipeline_start

        return PipelineResult(
            project_name=self.settings.project_name,
            participants=[],
            raw_transcripts=[],
            clean_transcripts=clean_transcripts,
            screen_clusters=screen_clusters,
            theme_groups=theme_groups,
            output_dir=output_dir,
            report_path=report_path,
            people=people,
            elapsed_seconds=elapsed,
            llm_input_tokens=llm_client.tracker.input_tokens,
            llm_output_tokens=llm_client.tracker.output_tokens,
            llm_calls=llm_client.tracker.calls,
            llm_model=self.settings.llm_model,
            llm_provider=self.settings.llm_provider,
            total_quotes=len(all_quotes),
        )

    async def _gather_all_segments(
        self,
        sessions: list[InputSession],
        *,
        on_progress: object | None = None,
    ) -> dict[str, list[TranscriptSegment]]:
        """Gather transcript segments from all sources (subtitle, docx, whisper).

        Args:
            sessions: Input sessions.
            on_progress: Optional callback(current, total) for transcription progress.

        Returns:
            Dict mapping session_id to list of TranscriptSegments.
        """
        from bristlenose.stages.parse_docx import parse_docx_file
        from bristlenose.stages.parse_subtitles import parse_subtitle_file
        from bristlenose.stages.transcribe import transcribe_sessions

        session_segments: dict[str, list[TranscriptSegment]] = {}

        for session in sessions:
            segments: list[TranscriptSegment] = []

            # Try subtitle files first
            for f in session.files:
                if f.file_type in (FileType.SUBTITLE_SRT, FileType.SUBTITLE_VTT):
                    try:
                        subs = parse_subtitle_file(f)
                        segments.extend(subs)
                        logger.info(
                            "%s: Parsed %d segments from %s",
                            session.session_id,
                            len(subs),
                            f.path.name,
                        )
                    except Exception as exc:
                        logger.error(
                            "%s: Failed to parse %s: %s",
                            session.session_id,
                            f.path.name,
                            exc,
                        )

            # Try docx files
            for f in session.files:
                if f.file_type == FileType.DOCX:
                    try:
                        docs = parse_docx_file(f)
                        segments.extend(docs)
                        logger.info(
                            "%s: Parsed %d segments from %s",
                            session.session_id,
                            len(docs),
                            f.path.name,
                        )
                    except Exception as exc:
                        logger.error(
                            "%s: Failed to parse %s: %s",
                            session.session_id,
                            f.path.name,
                            exc,
                        )

            if segments:
                session_segments[session.session_id] = segments
            # If no existing transcript, audio will be transcribed below

        # Transcribe sessions that still need it
        if not self.settings.skip_transcription:
            needs_transcription = [
                s for s in sessions
                if s.session_id not in session_segments and s.audio_path is not None
            ]
            if needs_transcription:
                whisper_results = transcribe_sessions(
                    needs_transcription,
                    self.settings,
                    on_progress=on_progress,
                )
                session_segments.update(whisper_results)

        return session_segments

    def run_render_only(
        self,
        output_dir: Path,
        input_dir: Path,
    ) -> PipelineResult:
        """Re-render reports from existing intermediate JSON.

        No transcription or LLM calls — just reads the JSON files written by
        a previous pipeline run and regenerates the HTML and Markdown output.

        Args:
            output_dir: Output directory containing ``intermediate/`` JSON.
            input_dir:  Original input directory. Sessions are re-ingested
                        (fast, no transcription) so the report can link
                        clickable timecodes to video files.

        Returns:
            PipelineResult (with empty transcripts — only clusters/themes populated).
        """
        import json as _json
        import time

        from bristlenose.models import ExtractedQuote, ScreenCluster, ThemeGroup
        from bristlenose.stages.render_html import render_html
        from bristlenose.stages.render_output import render_markdown

        self._configure_logging(output_dir)

        # Try new layout first (.bristlenose/intermediate/), fall back to legacy (intermediate/)
        intermediate = output_dir / ".bristlenose" / "intermediate"
        if not intermediate.is_dir():
            intermediate = output_dir / "intermediate"

        # --- Load intermediate JSON ---
        sc_path = intermediate / "screen_clusters.json"
        tg_path = intermediate / "theme_groups.json"
        eq_path = intermediate / "extracted_quotes.json"

        if not sc_path.exists() or not tg_path.exists():
            console.print(
                "[red]Missing intermediate files.[/red] "
                "Expected screen_clusters.json and theme_groups.json in "
                f"{intermediate}"
            )
            return self._empty_result(output_dir)

        screen_clusters = [
            ScreenCluster.model_validate(obj)
            for obj in _json.loads(sc_path.read_text(encoding="utf-8"))
        ]
        theme_groups = [
            ThemeGroup.model_validate(obj)
            for obj in _json.loads(tg_path.read_text(encoding="utf-8"))
        ]
        all_quotes: list[ExtractedQuote] = []
        if eq_path.exists():
            all_quotes = [
                ExtractedQuote.model_validate(obj)
                for obj in _json.loads(eq_path.read_text(encoding="utf-8"))
            ]

        # --- Re-ingest input files for video linking ---
        from bristlenose.stages.ingest import ingest

        sessions = ingest(input_dir)

        # --- Load existing people file for display names ---
        from bristlenose.people import build_display_name_map, load_people_file

        people = load_people_file(output_dir)
        display_names = build_display_name_map(people) if people else {}

        # --- Load transcripts for coverage calculation ---
        # Use same preference as render_transcript_pages: cooked > raw
        # Try new layout first (transcripts-cooked/), fall back to legacy (cooked_transcripts/)
        cooked_dir = output_dir / "transcripts-cooked"
        if not cooked_dir.is_dir():
            cooked_dir = output_dir / "cooked_transcripts"
        raw_dir = output_dir / "transcripts-raw"
        if not raw_dir.is_dir():
            raw_dir = output_dir / "raw_transcripts"
        if cooked_dir.is_dir() and any(cooked_dir.glob("*.txt")):
            transcripts_dir = cooked_dir
        elif raw_dir.is_dir():
            transcripts_dir = raw_dir
        else:
            transcripts_dir = None
        transcripts = (
            load_transcripts_from_dir(transcripts_dir)
            if transcripts_dir
            else []
        )

        # --- Render ---
        t0 = time.perf_counter()
        analysis = _compute_analysis(
            screen_clusters, theme_groups, all_quotes, sessions,
        )
        render_markdown(
            screen_clusters, theme_groups, sessions,
            self.settings.project_name, output_dir,
            all_quotes=all_quotes,
            display_names=display_names,
            people=people,
        )
        report_path = render_html(
            screen_clusters, theme_groups, sessions,
            self.settings.project_name, output_dir,
            all_quotes=all_quotes,
            color_scheme=self.settings.color_scheme,
            display_names=display_names,
            people=people,
            transcripts=transcripts,
            analysis=analysis,
        )
        _print_step("Rendered report", time.perf_counter() - t0)

        return PipelineResult(
            project_name=self.settings.project_name,
            participants=sessions,
            raw_transcripts=[],
            clean_transcripts=[],
            screen_clusters=screen_clusters,
            theme_groups=theme_groups,
            output_dir=output_dir,
            report_path=report_path,
            people=people,
            total_quotes=len(all_quotes),
        )

    def _empty_result(self, output_dir: Path) -> PipelineResult:
        """Return an empty pipeline result."""
        return PipelineResult(
            project_name=self.settings.project_name,
            participants=[],
            raw_transcripts=[],
            clean_transcripts=[],
            screen_clusters=[],
            theme_groups=[],
            output_dir=output_dir,
        )


def load_transcripts_from_dir(
    transcripts_dir: Path,
) -> list[PiiCleanTranscript]:
    """Load transcript .txt files from a directory into PiiCleanTranscript objects.

    Expects files named like s1.txt (new layout) or s1_raw.txt (legacy layout)
    with the format::

        # Transcript: s1
        # Source: ...
        # Date: ...
        # Duration: ...

        [HH:MM:SS] [p1] text...

    The bracket token after the timecode is the speaker code (e.g. ``p1``,
    ``m1``).  Legacy files with speaker roles (e.g. ``[PARTICIPANT]``) are
    also accepted.
    """
    import re
    from datetime import datetime, timezone

    from bristlenose.models import SpeakerRole
    from bristlenose.utils.timecodes import parse_timecode

    transcripts: list[PiiCleanTranscript] = []

    for path in sorted(transcripts_dir.glob("*.txt")):
        segments: list[TranscriptSegment] = []
        session_id = ""
        source_file = ""
        session_date = datetime.now(tz=timezone.utc)
        duration = 0.0

        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue

            # Parse header comments
            if line.startswith("# Transcript"):
                # Accept both "s1" (new) and "p1" (legacy) in header
                match = re.search(r":\s*([sp]\d+)", line)
                if match:
                    session_id = match.group(1)
                continue
            if line.startswith("# Source:"):
                source_file = line.split(":", 1)[1].strip()
                continue
            if line.startswith("# Date:"):
                try:
                    date_str = line.split(":", 1)[1].strip()
                    session_date = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
                except ValueError:
                    pass
                continue
            if line.startswith("# Duration:"):
                try:
                    duration = parse_timecode(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
                continue
            if line.startswith("#"):
                continue

            # Parse transcript lines: [MM:SS] or [HH:MM:SS] [speaker_code] text
            # The bracket token is the speaker code (p1, m1, o1, ...) or
            # a legacy speaker role (PARTICIPANT, RESEARCHER, etc.).
            match = re.match(
                r"\[(\d{2}:\d{2}(?::\d{2})?)\]\s*(?:\[(\w+)\])?\s*(.*)", line
            )
            if match:
                tc_str, bracket_token, text = match.groups()
                start_time = parse_timecode(tc_str)

                # Interpret bracket token: moderator codes (m1, m2),
                # observer codes (o1), participant codes (p1), or
                # legacy speaker roles (PARTICIPANT, RESEARCHER).
                role = SpeakerRole.UNKNOWN
                speaker_code = ""
                if bracket_token:
                    if bracket_token[0] == "m" and bracket_token[1:].isdigit():
                        role = SpeakerRole.RESEARCHER
                        speaker_code = bracket_token
                    elif bracket_token[0] == "o" and bracket_token[1:].isdigit():
                        role = SpeakerRole.OBSERVER
                        speaker_code = bracket_token
                    elif bracket_token[0] == "p" and bracket_token[1:].isdigit():
                        speaker_code = bracket_token
                    else:
                        try:
                            role = SpeakerRole(bracket_token.lower())
                        except ValueError:
                            pass

                segments.append(
                    TranscriptSegment(
                        start_time=start_time,
                        end_time=start_time,
                        text=text,
                        speaker_role=role,
                        speaker_code=speaker_code,
                        source="file",
                    )
                )

        if not session_id:
            # Derive from filename (s1_raw.txt → s1, legacy p1_raw.txt → p1)
            stem = path.stem.replace("_raw", "").replace("_cooked", "").replace("_clean", "")
            session_id = stem

        # Derive primary participant_id from first p-code in segments
        participant_id = ""
        for seg in segments:
            if seg.speaker_code.startswith("p"):
                participant_id = seg.speaker_code
                break
        if not participant_id:
            # Legacy fallback: if session_id is a p-code, use it
            participant_id = session_id if session_id.startswith("p") else ""

        if segments:
            transcripts.append(
                PiiCleanTranscript(
                    session_id=session_id,
                    participant_id=participant_id,
                    source_file=source_file,
                    session_date=session_date,
                    duration_seconds=duration,
                    segments=segments,
                )
            )

    return transcripts
