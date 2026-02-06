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

from bristlenose.config import BristlenoseSettings
from bristlenose.models import (
    FileType,
    InputSession,
    PiiCleanTranscript,
    PipelineResult,
    SpeakerRole,
    TranscriptSegment,
)

logger = logging.getLogger(__name__)
console = Console(width=min(80, Console().width))


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


class Pipeline:
    """Orchestrates the full Bristlenose processing pipeline."""

    def __init__(self, settings: BristlenoseSettings, verbose: bool = False) -> None:
        self.settings = settings
        self.verbose = verbose

        # Configure logging: suppress at default verbosity, show at -v
        log_level = logging.DEBUG if verbose else logging.WARNING
        logging.basicConfig(
            level=log_level,
            format="%(levelname)s | %(name)s | %(message)s",
            force=True,
        )
        # Always suppress noisy third-party loggers, even with -v
        for name in ("httpx", "presidio-analyzer", "presidio_analyzer", "faster_whisper"):
            logging.getLogger(name).setLevel(logging.WARNING)

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

        from bristlenose import __version__
        from bristlenose.llm.client import LLMClient
        from bristlenose.stages.extract_audio import extract_audio_for_sessions
        from bristlenose.stages.identify_speakers import (
            SpeakerInfo,
            identify_speaker_roles_heuristic,
            identify_speaker_roles_llm,
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
        from bristlenose.utils.hardware import detect_hardware

        pipeline_start = time.perf_counter()
        _printed_warnings.clear()
        output_dir.mkdir(parents=True, exist_ok=True)
        write_pipeline_metadata(output_dir, self.settings.project_name)

        with console.status("", spinner="dots") as status:
            status.renderable.frames = [" " + f for f in status.renderable.frames]

            # ── Stage 1: Ingest ──────────────────────────────────────
            status.update("[dim]Ingesting files...[/dim]")
            t0 = time.perf_counter()
            sessions = ingest(input_dir)
            if not sessions:
                console.print("[red]No supported files found.[/red]")
                return self._empty_result(output_dir)

            ingest_elapsed = time.perf_counter() - t0

            # ── Print header, then ingest checkmark ──
            hw = detect_hardware()
            provider_name = (
                "Claude" if self.settings.llm_provider == "anthropic" else "ChatGPT"
            )
            console.print(
                f"\nBristlenose [dim]v{__version__} · "
                f"{len(sessions)} sessions · {provider_name} · {hw.label}[/dim]\n",
            )
            type_counts = Counter(
                f.file_type.value for s in sessions for f in s.files
            )
            type_parts = [f"{n} {t}" for t, n in type_counts.most_common()]
            _print_step(
                f"Ingested {len(sessions)} sessions ({', '.join(type_parts)})",
                ingest_elapsed,
            )

            # ── Stage 2: Extract audio from video ────────────────────
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

            # ── Stages 3-5: Parse existing transcripts + Transcribe ──
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

            # ── Stage 5b: Speaker role identification ────────────────
            status.update("[dim]Identifying speakers...[/dim]")
            t0 = time.perf_counter()
            llm_client = LLMClient(self.settings)
            concurrency = self.settings.llm_concurrency

            # Heuristic pass (synchronous) for all sessions first
            for segments in session_segments.values():
                identify_speaker_roles_heuristic(segments)

            # LLM refinement concurrently (bounded by llm_concurrency)
            _sem_5b = asyncio.Semaphore(concurrency)
            _speaker_errors: list[str] = []

            async def _identify(
                sid: str, segments: list[TranscriptSegment],
            ) -> tuple[str, list]:
                async with _sem_5b:
                    infos = await identify_speaker_roles_llm(
                        segments, llm_client, errors=_speaker_errors,
                    )
                    return sid, infos

            _results_5b = await asyncio.gather(
                *(_identify(s, segs) for s, segs in session_segments.items())
            )
            all_speaker_infos: dict[str, list] = dict(_results_5b)

            # Assign per-segment speaker codes with global participant numbering
            from bristlenose.stages.identify_speakers import assign_speaker_codes

            all_label_code_maps: dict[str, dict[str, str]] = {}
            next_pnum = 1
            for session in sessions:
                sid = session.session_id
                segments = session_segments.get(sid, [])
                if not segments:
                    continue
                label_map, next_pnum = assign_speaker_codes(next_pnum, segments)
                all_label_code_maps[sid] = label_map
                # Update session's participant_id from assigned codes
                p_codes = [c for c in label_map.values() if c.startswith("p")]
                if p_codes:
                    session.participant_id = p_codes[0]
                    session.participant_number = int(p_codes[0][1:])

            _print_step("Identified speakers", time.perf_counter() - t0)
            if _speaker_errors:
                _print_warn(*_short_reason(_speaker_errors, self.settings.llm_provider))

            # ── Stage 6: Merge and write raw transcripts ─────────────
            status.update("[dim]Merging transcripts...[/dim]")
            t0 = time.perf_counter()
            transcripts = merge_transcripts(sessions, session_segments)
            raw_dir = output_dir / "transcripts-raw"
            write_raw_transcripts(transcripts, raw_dir)
            write_raw_transcripts_md(transcripts, raw_dir)
            _print_step("Merged transcripts", time.perf_counter() - t0)

            # ── Stage 7: PII removal ────────────────────────────────
            if self.settings.pii_enabled:
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
            status.update("[dim]Segmenting topics...[/dim]")
            t0 = time.perf_counter()
            _seg_errors: list[str] = []
            topic_maps = await segment_topics(
                clean_transcripts, llm_client, concurrency=concurrency,
                errors=_seg_errors,
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
            if _seg_errors:
                _print_warn(*_short_reason(_seg_errors, self.settings.llm_provider))

            # ── Stage 9: Quote extraction ────────────────────────────
            status.update("[dim]Extracting quotes...[/dim]")
            t0 = time.perf_counter()
            _quote_errors: list[str] = []
            all_quotes = await extract_quotes(
                clean_transcripts,
                topic_maps,
                llm_client,
                min_quote_words=self.settings.min_quote_words,
                concurrency=concurrency,
                errors=_quote_errors,
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
            if _quote_errors:
                _print_warn(*_short_reason(_quote_errors, self.settings.llm_provider))

            # ── Stages 10+11: Cluster by screen + thematic grouping ──
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
            status.update("[dim]Rendering output...[/dim]")
            t0 = time.perf_counter()
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
            )
            _print_step("Rendered report", time.perf_counter() - t0)

        elapsed = time.perf_counter() - pipeline_start

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
            llm_input_tokens=llm_client.tracker.input_tokens,
            llm_output_tokens=llm_client.tracker.output_tokens,
            llm_calls=llm_client.tracker.calls,
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

        from bristlenose import __version__
        from bristlenose.stages.extract_audio import extract_audio_for_sessions
        from bristlenose.stages.identify_speakers import identify_speaker_roles_heuristic
        from bristlenose.stages.ingest import ingest
        from bristlenose.stages.merge_transcript import (
            merge_transcripts,
            write_raw_transcripts,
            write_raw_transcripts_md,
        )
        from bristlenose.utils.hardware import detect_hardware

        pipeline_start = time.perf_counter()
        output_dir.mkdir(parents=True, exist_ok=True)

        with console.status("", spinner="dots") as status:
            status.renderable.frames = [" " + f for f in status.renderable.frames]

            # ── Stage 1: Ingest ──
            status.update("[dim]Ingesting files...[/dim]")
            t0 = time.perf_counter()
            sessions = ingest(input_dir)
            if not sessions:
                console.print("[red]No supported files found.[/red]")
                return self._empty_result(output_dir)

            ingest_elapsed = time.perf_counter() - t0

            # ── Print header, then ingest checkmark ──
            hw = detect_hardware()
            console.print(
                f"\nBristlenose [dim]v{__version__} · "
                f"{len(sessions)} sessions · {hw.label}[/dim]\n",
            )
            type_counts = Counter(
                f.file_type.value for s in sessions for f in s.files
            )
            type_parts = [f"{n} {t}" for t, n in type_counts.most_common()]
            _print_step(
                f"Ingested {len(sessions)} sessions ({', '.join(type_parts)})",
                ingest_elapsed,
            )

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

        from bristlenose import __version__
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
        write_pipeline_metadata(output_dir, self.settings.project_name)

        # Load existing transcripts from text files
        clean_transcripts = load_transcripts_from_dir(transcripts_dir)
        if not clean_transcripts:
            console.print("[red]No transcript files found.[/red]")
            return self._empty_result(output_dir)

        llm_client = LLMClient(self.settings)
        concurrency = self.settings.llm_concurrency

        provider_name = (
            "Claude" if self.settings.llm_provider == "anthropic" else "ChatGPT"
        )
        console.print(
            f"\nBristlenose [dim]v{__version__} · "
            f"{len(clean_transcripts)} transcripts · {provider_name}[/dim]\n",
        )

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
