"""Pipeline orchestrator: runs all stages in sequence."""

from __future__ import annotations

import logging
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from bristlenose.config import BristlenoseSettings
from bristlenose.models import (
    FileType,
    InputSession,
    PiiCleanTranscript,
    PipelineResult,
    TranscriptSegment,
)

logger = logging.getLogger(__name__)
console = Console()


class Pipeline:
    """Orchestrates the full Bristlenose processing pipeline."""

    def __init__(self, settings: BristlenoseSettings, verbose: bool = False) -> None:
        self.settings = settings
        self.verbose = verbose

        # Configure logging
        log_level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="%(levelname)s | %(name)s | %(message)s",
        )

    async def run(self, input_dir: Path, output_dir: Path) -> PipelineResult:
        """Run the full pipeline: ingest → transcribe → analyse → output.

        Args:
            input_dir: Directory containing input files.
            output_dir: Directory for all output.

        Returns:
            PipelineResult with all data and paths.
        """
        from bristlenose.llm.client import LLMClient
        from bristlenose.stages.extract_audio import extract_audio_for_sessions
        from bristlenose.stages.identify_speakers import (
            identify_speaker_roles_heuristic,
            identify_speaker_roles_llm,
        )
        from bristlenose.stages.ingest import ingest
        from bristlenose.stages.merge_transcript import (
            merge_transcripts,
            write_raw_transcripts,
        )
        from bristlenose.stages.pii_removal import (
            remove_pii,
            write_cooked_transcripts,
            write_pii_summary,
        )
        from bristlenose.stages.quote_clustering import cluster_by_screen
        from bristlenose.stages.quote_extraction import extract_quotes
        from bristlenose.stages.render_html import render_html
        from bristlenose.stages.render_output import (
            render_markdown,
            write_intermediate_json,
        )
        from bristlenose.stages.thematic_grouping import group_by_theme
        from bristlenose.stages.topic_segmentation import segment_topics

        output_dir.mkdir(parents=True, exist_ok=True)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:

            # ── Stage 1: Ingest ──────────────────────────────────────
            task = progress.add_task("Ingesting files...", total=None)
            sessions = ingest(input_dir)
            if not sessions:
                console.print("[red]No supported files found.[/red]")
                return self._empty_result(output_dir)
            progress.update(task, description=f"Ingested {len(sessions)} sessions")
            progress.remove_task(task)

            # ── Stage 2: Extract audio from video ────────────────────
            task = progress.add_task("Extracting audio...", total=None)
            temp_dir = output_dir / "temp"
            sessions = extract_audio_for_sessions(sessions, temp_dir)
            progress.remove_task(task)

            # ── Stages 3-5: Parse existing transcripts + Transcribe ──
            task = progress.add_task("Transcribing...", total=None)
            session_segments = await self._gather_all_segments(sessions, progress)
            progress.remove_task(task)

            # ── Stage 5b: Speaker role identification ────────────────
            task = progress.add_task("Identifying speakers...", total=None)
            llm_client = LLMClient(self.settings)

            for pid, segments in session_segments.items():
                # Heuristic pass first
                identify_speaker_roles_heuristic(segments)
                # LLM refinement
                await identify_speaker_roles_llm(segments, llm_client)

            progress.remove_task(task)

            # ── Stage 6: Merge and write raw transcripts ─────────────
            task = progress.add_task("Merging transcripts...", total=None)
            transcripts = merge_transcripts(sessions, session_segments)
            raw_dir = output_dir / "raw_transcripts"
            write_raw_transcripts(transcripts, raw_dir)
            progress.remove_task(task)

            # ── Stage 7: PII removal ────────────────────────────────
            if self.settings.pii_enabled:
                task = progress.add_task("Removing PII...", total=None)
                clean_transcripts, pii_redactions = remove_pii(transcripts, self.settings)
                cooked_dir = output_dir / "cooked_transcripts"
                write_cooked_transcripts(clean_transcripts, cooked_dir)
                write_pii_summary(pii_redactions, output_dir)
                progress.remove_task(task)
            else:
                # Pass through without PII removal
                clean_transcripts = [
                    PiiCleanTranscript(
                        participant_id=t.participant_id,
                        source_file=t.source_file,
                        session_date=t.session_date,
                        duration_seconds=t.duration_seconds,
                        segments=t.segments,
                    )
                    for t in transcripts
                ]

            # ── Stage 8: Topic segmentation ──────────────────────────
            task = progress.add_task("Segmenting topics...", total=None)
            topic_maps = await segment_topics(clean_transcripts, llm_client)
            if self.settings.write_intermediate:
                write_intermediate_json(topic_maps, "topic_boundaries.json", output_dir)
            progress.remove_task(task)

            # ── Stage 9: Quote extraction ────────────────────────────
            task = progress.add_task("Extracting quotes...", total=None)
            all_quotes = await extract_quotes(
                clean_transcripts,
                topic_maps,
                llm_client,
                min_quote_words=self.settings.min_quote_words,
            )
            if self.settings.write_intermediate:
                write_intermediate_json(all_quotes, "extracted_quotes.json", output_dir)
            progress.remove_task(task)

            # ── Stage 10: Cluster by screen ──────────────────────────
            task = progress.add_task("Clustering by screen...", total=None)
            screen_clusters = await cluster_by_screen(all_quotes, llm_client)
            if self.settings.write_intermediate:
                write_intermediate_json(screen_clusters, "screen_clusters.json", output_dir)
            progress.remove_task(task)

            # ── Stage 11: Thematic grouping ──────────────────────────
            task = progress.add_task("Grouping themes...", total=None)
            theme_groups = await group_by_theme(all_quotes, llm_client)
            if self.settings.write_intermediate:
                write_intermediate_json(theme_groups, "theme_groups.json", output_dir)
            progress.remove_task(task)

            # ── Stage 12: Render output ──────────────────────────────
            task = progress.add_task("Rendering output...", total=None)
            render_markdown(
                screen_clusters,
                theme_groups,
                sessions,
                self.settings.project_name,
                output_dir,
                all_quotes=all_quotes,
            )
            render_html(
                screen_clusters,
                theme_groups,
                sessions,
                self.settings.project_name,
                output_dir,
                all_quotes=all_quotes,
            )
            progress.remove_task(task)

        return PipelineResult(
            project_name=self.settings.project_name,
            participants=sessions,
            raw_transcripts=transcripts,
            clean_transcripts=clean_transcripts,
            screen_clusters=screen_clusters,
            theme_groups=theme_groups,
            output_dir=output_dir,
        )

    async def run_transcription_only(
        self, input_dir: Path, output_dir: Path
    ) -> PipelineResult:
        """Run only ingestion and transcription (no LLM analysis).

        Useful for producing raw transcripts without needing an API key.
        """
        from bristlenose.stages.extract_audio import extract_audio_for_sessions
        from bristlenose.stages.identify_speakers import identify_speaker_roles_heuristic
        from bristlenose.stages.ingest import ingest
        from bristlenose.stages.merge_transcript import merge_transcripts, write_raw_transcripts

        output_dir.mkdir(parents=True, exist_ok=True)

        sessions = ingest(input_dir)
        if not sessions:
            return self._empty_result(output_dir)

        temp_dir = output_dir / "temp"
        sessions = extract_audio_for_sessions(sessions, temp_dir)

        session_segments = await self._gather_all_segments(sessions)

        # Heuristic speaker identification only (no LLM)
        for pid, segments in session_segments.items():
            identify_speaker_roles_heuristic(segments)

        transcripts = merge_transcripts(sessions, session_segments)
        raw_dir = output_dir / "raw_transcripts"
        write_raw_transcripts(transcripts, raw_dir)

        return PipelineResult(
            project_name=self.settings.project_name,
            participants=sessions,
            raw_transcripts=transcripts,
            clean_transcripts=[],
            screen_clusters=[],
            theme_groups=[],
            output_dir=output_dir,
        )

    async def run_analysis_only(
        self, transcripts_dir: Path, output_dir: Path
    ) -> PipelineResult:
        """Run LLM analysis on existing transcript files.

        Loads .txt transcripts from a directory and runs stages 8-12.
        """
        from bristlenose.llm.client import LLMClient
        from bristlenose.stages.quote_clustering import cluster_by_screen
        from bristlenose.stages.quote_extraction import extract_quotes
        from bristlenose.stages.render_html import render_html
        from bristlenose.stages.render_output import render_markdown, write_intermediate_json
        from bristlenose.stages.thematic_grouping import group_by_theme
        from bristlenose.stages.topic_segmentation import segment_topics

        output_dir.mkdir(parents=True, exist_ok=True)

        # Load existing transcripts from text files
        clean_transcripts = _load_transcripts_from_dir(transcripts_dir)
        if not clean_transcripts:
            console.print("[red]No transcript files found.[/red]")
            return self._empty_result(output_dir)

        llm_client = LLMClient(self.settings)

        topic_maps = await segment_topics(clean_transcripts, llm_client)
        if self.settings.write_intermediate:
            write_intermediate_json(topic_maps, "topic_boundaries.json", output_dir)

        all_quotes = await extract_quotes(
            clean_transcripts, topic_maps, llm_client,
            min_quote_words=self.settings.min_quote_words,
        )
        if self.settings.write_intermediate:
            write_intermediate_json(all_quotes, "extracted_quotes.json", output_dir)

        screen_clusters = await cluster_by_screen(all_quotes, llm_client)
        theme_groups = await group_by_theme(all_quotes, llm_client)

        render_markdown(
            screen_clusters, theme_groups, [],
            self.settings.project_name, output_dir,
            all_quotes=all_quotes,
        )
        render_html(
            screen_clusters, theme_groups, [],
            self.settings.project_name, output_dir,
            all_quotes=all_quotes,
        )

        return PipelineResult(
            project_name=self.settings.project_name,
            participants=[],
            raw_transcripts=[],
            clean_transcripts=clean_transcripts,
            screen_clusters=screen_clusters,
            theme_groups=theme_groups,
            output_dir=output_dir,
        )

    async def _gather_all_segments(
        self,
        sessions: list[InputSession],
        progress: object | None = None,
    ) -> dict[str, list[TranscriptSegment]]:
        """Gather transcript segments from all sources (subtitle, docx, whisper).

        Args:
            sessions: Input sessions.
            progress: Optional Rich progress bar.

        Returns:
            Dict mapping participant_id to list of TranscriptSegments.
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
                            session.participant_id,
                            len(subs),
                            f.path.name,
                        )
                    except Exception as exc:
                        logger.error(
                            "%s: Failed to parse %s: %s",
                            session.participant_id,
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
                            session.participant_id,
                            len(docs),
                            f.path.name,
                        )
                    except Exception as exc:
                        logger.error(
                            "%s: Failed to parse %s: %s",
                            session.participant_id,
                            f.path.name,
                            exc,
                        )

            if segments:
                session_segments[session.participant_id] = segments
            # If no existing transcript, audio will be transcribed below

        # Transcribe sessions that still need it
        if not self.settings.skip_transcription:
            needs_transcription = [
                s for s in sessions
                if s.participant_id not in session_segments and s.audio_path is not None
            ]
            if needs_transcription:
                whisper_results = transcribe_sessions(needs_transcription, self.settings)
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

        from bristlenose.models import ExtractedQuote, ScreenCluster, ThemeGroup
        from bristlenose.stages.render_html import render_html
        from bristlenose.stages.render_output import render_markdown

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

        # --- Render ---
        render_markdown(
            screen_clusters, theme_groups, sessions,
            self.settings.project_name, output_dir,
            all_quotes=all_quotes,
        )
        render_html(
            screen_clusters, theme_groups, sessions,
            self.settings.project_name, output_dir,
            all_quotes=all_quotes,
        )

        return PipelineResult(
            project_name=self.settings.project_name,
            participants=sessions,
            raw_transcripts=[],
            clean_transcripts=[],
            screen_clusters=screen_clusters,
            theme_groups=theme_groups,
            output_dir=output_dir,
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


def _load_transcripts_from_dir(
    transcripts_dir: Path,
) -> list[PiiCleanTranscript]:
    """Load transcript .txt files from a directory into PiiCleanTranscript objects.

    Expects files named like p1_raw.txt or p1_cooked.txt with the format:
        # Transcript: p1
        # Source: ...
        # Date: ...
        # Duration: ...

        [HH:MM:SS] [ROLE] text...
    """
    import re
    from datetime import datetime, timezone

    from bristlenose.models import SpeakerRole
    from bristlenose.utils.timecodes import parse_timecode

    transcripts: list[PiiCleanTranscript] = []

    for path in sorted(transcripts_dir.glob("*.txt")):
        segments: list[TranscriptSegment] = []
        participant_id = ""
        source_file = ""
        session_date = datetime.now(tz=timezone.utc)
        duration = 0.0

        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue

            # Parse header comments
            if line.startswith("# Transcript"):
                match = re.search(r":\s*(p\d+)", line)
                if match:
                    participant_id = match.group(1)
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

            # Parse transcript lines: [HH:MM:SS] [ROLE] text
            match = re.match(
                r"\[(\d{2}:\d{2}:\d{2})\]\s*(?:\[(\w+)\])?\s*(.*)", line
            )
            if match:
                tc_str, role_str, text = match.groups()
                start_time = parse_timecode(tc_str)
                role = SpeakerRole.UNKNOWN
                if role_str:
                    try:
                        role = SpeakerRole(role_str.lower())
                    except ValueError:
                        pass
                segments.append(
                    TranscriptSegment(
                        start_time=start_time,
                        end_time=start_time,
                        text=text,
                        speaker_role=role,
                        source="file",
                    )
                )

        if not participant_id:
            # Derive from filename
            stem = path.stem.replace("_raw", "").replace("_cooked", "").replace("_clean", "")
            participant_id = stem

        if segments:
            transcripts.append(
                PiiCleanTranscript(
                    participant_id=participant_id,
                    source_file=source_file,
                    session_date=session_date,
                    duration_seconds=duration,
                    segments=segments,
                )
            )

    return transcripts
