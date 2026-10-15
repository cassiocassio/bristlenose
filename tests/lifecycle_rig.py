"""An end-to-end rig for a study's life: the real CLI run, the real server.

The scenario table (``test_lifecycle_scenarios.py``) drives the server and the
stash code against a fixed output folder; the pipeline tests drive
``Pipeline.run`` with ingest faked. Neither replays what the Mac app does:
spawn ``bristlenose run <folder>`` and ``bristlenose serve <folder>`` side by
side, then do it again after the researcher has moved, renamed or copied
things. The 12 Oct 2026 incident was two pieces disagreeing, which no
single-piece test could see.

This rig runs the **real** ``bristlenose run`` command (typer, preflight
skipped, ``run_lifecycle``, ``output_backup``'s stash and restore, real ingest
over real files) with only the paid or slow work replaced:

- **the fake LLM**: speaker identification, topics, quotes, clusters and themes
  return small, deterministic answers, and the LLM client is a mock;
- **fake Whisper**: a recording's "transcript" is fixed text, and every session
  handed to it is recorded, so a test can say what was transcribed and when;
- audio extraction passes the recording through.

And it serves with the **real** ``create_app`` (no ``db_url``, so the server
chooses where its database lives), whose watcher imports the run's output.

Recordings are written with distinct bytes, so each has its own content: the
rig is ready for content identity (``docs/design-project-identity.md`` §5)
before the code is.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from bristlenose.events import StageOutcome
from bristlenose.models import FileType, PiiCleanTranscript, SessionTopicMap, TranscriptSegment
from tests.conftest import iter_transcribe_from
from tests.test_serve_project_root import _app, _client, _rows, _sessions, _wait

STAGE_PATCHES = (
    "bristlenose.stages.s02_extract_audio.extract_audio_for_sessions",
    "bristlenose.preflight.whisper.preflight_whisper",
    "bristlenose.stages.s05_transcribe.iter_transcribe_sessions",
    "bristlenose.stages.s05b_identify_speakers.split_single_speaker_llm",
    "bristlenose.stages.s05b_identify_speakers.identify_speaker_roles_llm",
    "bristlenose.stages.s08_topic_segmentation.segment_topics",
    "bristlenose.stages.s09_quote_extraction.extract_quotes",
    "bristlenose.stages.s10_quote_clustering.cluster_by_screen",
    "bristlenose.stages.s11_thematic_grouping.group_by_theme",
)


def _quote(sid: str, pid: str, n: int):
    from bristlenose.models import (
        EmotionalTone,
        ExtractedQuote,
        JourneyStage,
        QuoteIntent,
        QuoteType,
    )

    text = f"Quote {n} from {sid}, long enough to clear the word floor easily."
    return ExtractedQuote(
        session_id=sid, participant_id=pid,
        start_timecode=float(10 + n * 20), end_timecode=float(15 + n * 20),
        text=text, verbatim_excerpt=text, topic_label="general",
        quote_type=QuoteType.GENERAL_CONTEXT, researcher_context="",
        intent=QuoteIntent.NARRATION, emotion=EmotionalTone.NEUTRAL,
        journey_stage=JourneyStage.OTHER,
    )


def _whisper_text(name: str) -> list[TranscriptSegment]:
    lines = [
        f"Welcome, thanks for joining us today for {name}.",
        "Happy to be here and talk about how I use the app.",
        "Tell me about the dashboard and what you check first.",
        "I open it every morning to look at the review queue.",
    ]
    return [
        TranscriptSegment(
            start_time=float(i * 20), end_time=float(i * 20 + 18), text=t,
            speaker_label=None, source="whisper",
        )
        for i, t in enumerate(lines)
    ]


@dataclass
class Study:
    """A study folder on disk, and what the fake services saw happen to it."""

    folder: Path
    work: Path
    #: Per run, the recording file names handed to (fake) Whisper.
    transcribed: list[list[str]] = field(default_factory=list)

    # ── the researcher's own acts ───────────────────────────────────────────

    def add_recording(self, name: str) -> Path:
        """Distinct bytes per name, so every recording has its own content."""
        path = self.folder / name
        path.write_bytes(b"RIFF fake recording " + name.encode("utf-8") * 64)
        return path

    def move_to(self, new_folder: Path) -> None:
        from bristlenose.logging import release_log_file

        release_log_file()
        new_folder.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(self.folder), str(new_folder))
        self.folder = new_folder

    def copy_to(self, new_folder: Path) -> Study:
        new_folder.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.folder, new_folder)
        return Study(folder=new_folder, work=self.work)

    # ── the app's acts ──────────────────────────────────────────────────────

    def run(self, *, clean: bool = False) -> None:
        """``bristlenose run <folder>`` as the Mac app spawns it."""
        recorded: list[str] = []

        async def _passthrough(sessions, _tmp, **_kw):
            for s in sessions:
                if s.audio_path is None and not s.has_existing_transcript:
                    s.audio_path = next(
                        (f.path for f in s.files
                         if f.file_type in (FileType.AUDIO, FileType.VIDEO)), None,
                    )
            return sessions

        def _transcribe(sessions, _settings, **_kw):
            names = [Path(s.audio_path or s.files[0].path).name for s in sessions]
            recorded.extend(names)
            return (
                {s.session_id: _whisper_text(n) for s, n in zip(sessions, names, strict=True)},
                {},
                StageOutcome(attempted=len(sessions), succeeded=len(sessions)),
            )

        async def _split(segments, _client, errors=None):
            for i, seg in enumerate(segments):
                seg.speaker_label = "Speaker A" if i % 2 == 0 else "Speaker B"
            return segments

        async def _roles(segments, _client, errors=None):
            return []

        async def _topics(transcripts, *_a, **_kw):
            maps = [
                SessionTopicMap(session_id=t.session_id, participant_id=t.participant_id,
                                boundaries=[])
                for t in transcripts
            ]
            return maps, StageOutcome(attempted=len(maps), succeeded=len(maps))

        async def _quotes(transcripts, *_a, **_kw):
            assert all(isinstance(t, PiiCleanTranscript) for t in transcripts)
            quotes = [_quote(t.session_id, t.participant_id, n)
                      for t in transcripts for n in range(2)]
            return quotes, StageOutcome(attempted=len(transcripts), succeeded=len(transcripts))

        async def _cluster(quotes, *_a, **_kw):
            # Every quote in one section: the importer stores only quotes that
            # sit in a section or a theme (quote exclusivity).
            from bristlenose.models import ScreenCluster

            cluster = ScreenCluster(screen_label="Dashboard", description="",
                                    display_order=1, quotes=list(quotes))
            return [cluster], StageOutcome(attempted=1, succeeded=1)

        async def _empty(*_a, **_kw):
            return [], StageOutcome(attempted=1, succeeded=1)

        fakes = (
            _passthrough, lambda **_kw: None, iter_transcribe_from(_transcribe),
            _split, _roles, _topics, _quotes, _cluster, _empty,
        )
        args = ["run", str(self.folder), "--no-serve", "--llm", "claude"]
        if clean:
            args.append("--clean")
        with _quiet_cli():
            stack = [patch(target, new=fake) for target, fake in zip(STAGE_PATCHES, fakes,
                                                                      strict=True)]
            stack.append(patch("bristlenose.llm.client.LLMClient", MagicMock()))
            for p in stack:
                p.start()
            try:
                result = CliRunner().invoke(_cli_app(), args, catch_exceptions=False)
            finally:
                for p in reversed(stack):
                    p.stop()
        self.transcribed.append(recorded)
        assert result.exit_code == 0, f"run exited {result.exit_code}:\n{result.output}"

    @contextmanager
    def serve(self) -> Iterator[object]:
        """``bristlenose serve <folder>`` as the Mac app spawns it; yields a client."""
        with _client(_app(self.folder, self.work)) as client:
            yield client

    # ── what the researcher sees ────────────────────────────────────────────

    def sessions(self, client, expect: int | None = None) -> list:
        """The report's sessions, once it shows ``expect`` of them (or any).

        Waits, because the server imports a finished run on its own poll."""
        def ready() -> bool:
            got = _sessions(client)
            return bool(got) and (expect is None or len(got) == expect)

        assert _wait(ready, timeout=10.0), (
            f"the report shows {len(_sessions(client))} sessions, want {expect}"
        )
        return _sessions(client)

    def assert_healthy(self) -> None:
        """The scenario table's storage checks, for this study's folder: the
        database is under the output folder, nothing is littered in the
        interview folder, and there is exactly one project row — the one the
        report reads. A fork leaves a stale row 1 that still answers, which is
        how a move once looked healthy to every other assertion here."""
        db = self.folder / "bristlenose-output" / ".bristlenose" / "bristlenose.db"
        assert db.exists(), "the database is not under bristlenose-output/.bristlenose/"
        assert not (self.folder / ".bristlenose").exists(), "litter in the interview folder"
        rows = _rows(db)
        assert len(rows) == 1, f"{len(rows)} project rows (want 1): {rows}"

    @staticmethod
    def quote_ids(client) -> list[str]:
        """Every quote id the report shows, in a stable order."""
        def _read() -> list[str]:
            resp = client.get("/api/projects/1/quotes")
            if resp.status_code != 200:
                return []
            ids: list[str] = []

            def walk(node) -> None:
                if isinstance(node, dict):
                    qid = node.get("dom_id")
                    if isinstance(qid, str) and qid.startswith("q-"):
                        ids.append(qid)
                    for v in node.values():
                        walk(v)
                elif isinstance(node, list):
                    for v in node:
                        walk(v)

            walk(resp.json())
            return sorted(set(ids))

        assert _wait(lambda: bool(_read()), timeout=10.0), "the report shows no quotes"
        return _read()

    @staticmethod
    def star(client, quote_id: str) -> None:
        resp = client.put("/api/projects/1/starred", json={quote_id: True})
        assert resp.status_code == 200, resp.text

    @staticmethod
    def starred(client) -> set[str]:
        resp = client.get("/api/projects/1/starred")
        if resp.status_code != 200:
            return set()
        return {k for k, v in resp.json().items() if v}


def _cli_app():
    from bristlenose.cli import app

    return app


@contextmanager
def _quiet_cli() -> Iterator[None]:
    """Reach the pipeline: no keychain, no preflight, no provider set-up, no key
    check. Same seams as ``test_cli_output_backup_wiring.cli_to_pipeline``."""
    with (
        patch("bristlenose.config._populate_keys_from_keychain", lambda s: s),
        patch("bristlenose.cli._maybe_guide_provider_setup", lambda s: None),
        patch("bristlenose.cli._maybe_auto_doctor", lambda s, c: True),
        patch("bristlenose.preflight.api_key.preflight_api_key", lambda **kw: None),
        # The Discussion lens makes its own LLM calls through the client, which
        # is a mock here; it is optional and fails soft, but noisily.
        patch.dict(os.environ, {"BRISTLENOSE_ANTHROPIC_API_KEY": "sk-ant-test-rig",
                                "BRISTLENOSE_DISCUSSION_LENS": "false"}),
    ):
        yield


def new_study(tmp_path: Path, *recordings: str) -> Study:
    folder = tmp_path / "Studies" / "Talismanic"
    folder.mkdir(parents=True)
    work = tmp_path / "work"
    work.mkdir()
    study = Study(folder=folder, work=work)
    for name in recordings:
        study.add_recording(name)
    return study
