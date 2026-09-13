"""Guards on the anonymisation boundary — export embed, importer, and `analyze`.

These pin a leak that every other gate missed: an *anonymised* export rendered
``My name is [NAME].`` while its embedded JSON carried
``"words":[{"t":"Jane",...}]``.  Redaction clears ``words`` at the point it
redacts, but ``session_segments.json`` predates stage 7 and the serve importer
backfilled from it — so the participant's name reached the DB, the transcript
route, and the file a researcher emails to a client.

Neither of these needs the frontend build, so unlike ``test_serve_export_api``
they run in CI.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from bristlenose.server.importer import _enrich_words_from_intermediate
from bristlenose.server.routes.export import _anonymise_data


def _endpoints_with_word_timings() -> dict[str, Any]:
    """An embed payload shaped like the real one, carrying word-level text."""
    return {
        "/people": {"p1": {"full_name": "Jane Doe", "short_name": "Jane", "role": "Nurse"}},
        "/transcripts/s1": {
            "speakers": [{"code": "p1", "name": "Jane Doe"}],
            "segments": [
                {
                    "speaker_code": "p1",
                    "text": "My name is [NAME].",
                    "words": [
                        {"text": "My", "start": 0.1, "end": 0.3},
                        {"text": "Jane", "start": 0.9, "end": 1.2},
                    ],
                },
                {"speaker_code": "m1", "text": "Thanks.", "words": None},
            ],
        },
    }


class TestAnonymisedExportDropsWordTimings:
    def test_no_word_timings_survive(self) -> None:
        endpoints = _endpoints_with_word_timings()
        _anonymise_data(endpoints)
        for seg in endpoints["/transcripts/s1"]["segments"]:
            assert "words" not in seg, (
                "word-level timings carry participant speech verbatim and must "
                "not survive into an anonymised export"
            )

    def test_the_participant_name_is_absent_from_the_serialised_embed(self) -> None:
        """The end-to-end shape of the leak: grep the JSON a client receives."""
        endpoints = _endpoints_with_word_timings()
        _anonymise_data(endpoints)
        assert "Jane" not in json.dumps(endpoints)

    def test_speaker_names_are_still_stripped(self) -> None:
        """The pre-existing guarantee must not regress alongside the new one."""
        endpoints = _endpoints_with_word_timings()
        _anonymise_data(endpoints)
        assert endpoints["/people"]["p1"]["full_name"] == ""
        assert endpoints["/transcripts/s1"]["speakers"][0]["name"] == ""


class _ExplodingIfTouched:
    """Any attribute access fails the test — proves the guard returned early."""

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"word backfill touched the database ({name})")


class TestImporterRefusesToBackfillARedactedProject:
    def test_redacted_project_skips_the_backfill(self, tmp_path: Path) -> None:
        """No session map, so there is nothing to remediate and nothing to fill."""
        intermediate = tmp_path / ".bristlenose" / "intermediate"
        intermediate.mkdir(parents=True)
        (intermediate / "session_segments.json").write_text(
            json.dumps(
                {"s1": [{"segment_index": 0,
                         "words": [{"text": "Jane", "start_time": 0.9, "end_time": 1.2}]}]}
            ),
            encoding="utf-8",
        )
        (tmp_path / "transcripts-cooked").mkdir()  # the redaction signal

        # Would raise on any DB access; with no sessions the guard must return
        # before touching it.
        _enrich_words_from_intermediate(_ExplodingIfTouched(), {}, tmp_path)  # type: ignore[arg-type]

    def test_a_redacted_project_clears_word_rows_a_pre_fix_import_left(
        self, tmp_path: Path
    ) -> None:
        """Skipping the backfill does not help a project imported before the guard.

        `_import_transcript_segments` returns early for a session that already
        has segments, so those rows persist for ever and the live transcript
        route keeps serving pre-redaction word text.
        """
        from unittest.mock import MagicMock

        (tmp_path / "transcripts-cooked").mkdir()
        db = MagicMock()
        db.query.return_value.filter.return_value.update.return_value = 7
        sess = MagicMock()
        sess.id = 42

        _enrich_words_from_intermediate(db, {"s1": sess}, tmp_path)

        update = db.query.return_value.filter.return_value.update
        update.assert_called_once()
        assert update.call_args.args[0] == {"words_json": None}
        db.commit.assert_called_once()

    def test_an_unredacted_project_still_reaches_the_backfill(self, tmp_path: Path) -> None:
        """The guard must be keyed on redaction, not simply always-off."""
        intermediate = tmp_path / ".bristlenose" / "intermediate"
        intermediate.mkdir(parents=True)
        (intermediate / "session_segments.json").write_text(
            json.dumps(
                {"s1": [{"segment_index": 0,
                         "words": [{"text": "Jane", "start_time": 0.9, "end_time": 1.2}]}]}
            ),
            encoding="utf-8",
        )
        # No transcripts-cooked/ -> not redacted -> the function proceeds and
        # consults session_map, which is empty, so it is a clean no-op.
        with pytest.raises(AssertionError, match="touched the database"):
            _enrich_words_from_intermediate(
                _ExplodingIfTouched(), {"s1": _ExplodingIfTouched()}, tmp_path  # type: ignore[arg-type]
            )


class TestAnalyzeRefusesToSilentlySkipRedaction:
    """`analyze` starts after stage 7, so it cannot redact — only honour or betray.

    `pii_enabled` is reachable by env (``BRISTLENOSE_PII_ENABLED=1``), and before
    the guard every transcript went to the language model unredacted with nothing
    anywhere reporting that redaction had not run.
    """

    @staticmethod
    def _settings(*, pii_enabled: bool) -> Any:
        from unittest.mock import MagicMock

        st = MagicMock()
        st.project_name = "test-analyze-pii-guard"
        st.llm_provider = "anthropic"
        st.llm_model = "claude-sonnet-4-5-20250929"
        st.anthropic_api_key = "sk-fake"
        st.write_intermediate = True
        st.llm_concurrency = 1
        st.color_scheme = "default"
        st.pii_enabled = pii_enabled
        return st

    @staticmethod
    def _transcripts_at(path: Path) -> Path:
        path.mkdir(parents=True)
        (path / "s1.txt").write_text(
            "# Transcript: s1\n# Source: s1.wav\n# Date: 2026-09-12\n"
            "# Duration: 00:00:10\n\n[00:00] [m1] Hello.\n[00:05] [p1] Hi there.\n",
            encoding="utf-8",
        )
        return path

    def test_raw_transcripts_with_redaction_enabled_are_refused(self, tmp_path: Path) -> None:
        import asyncio

        from bristlenose.pipeline import Pipeline

        tx = self._transcripts_at(tmp_path / "transcripts-raw")
        pipeline = Pipeline(self._settings(pii_enabled=True))
        with pytest.raises(ValueError, match="cannot redact"):
            asyncio.run(pipeline.run_analysis_only(tx, tmp_path / "out"))

    def test_the_cooked_directory_is_accepted(self, tmp_path: Path) -> None:
        """Keyed on redaction actually having happened — not simply always-refuse."""
        import asyncio

        from bristlenose.pipeline import Pipeline

        tx = self._transcripts_at(tmp_path / "transcripts-cooked")
        pipeline = Pipeline(self._settings(pii_enabled=True))
        # Proceeds past the guard and fails later on the fake key; what matters
        # is that it is not the guard's refusal.
        with pytest.raises(Exception) as exc:  # noqa: B017 - any later failure is fine
            asyncio.run(pipeline.run_analysis_only(tx, tmp_path / "out"))
        assert "cannot redact" not in str(exc.value)

    def test_redaction_off_is_untouched(self, tmp_path: Path) -> None:
        import asyncio

        from bristlenose.pipeline import Pipeline

        tx = self._transcripts_at(tmp_path / "transcripts-raw")
        pipeline = Pipeline(self._settings(pii_enabled=False))
        with pytest.raises(Exception) as exc:  # noqa: B017
            asyncio.run(pipeline.run_analysis_only(tx, tmp_path / "out"))
        assert "cannot redact" not in str(exc.value)


class TestAnalyzePreflightDoesNotProbeThePiiStack:
    """`pii` was added to the analyze preflight on 12 Sep 2026 and reverted the
    same day. `check_pii` probes presidio and a *loadable* spaCy model, and
    `analyze` starts at stage 8 and touches neither — so it never surfaced the
    wrong-directory refusal it was added for, and it newly refused a legitimate
    `analyze <out>/transcripts-cooked` on any machine without the 400 MB model
    (redact on one Mac, analyse on another). The refusal that belongs in
    preflight is a directory predicate, not a dependency probe."""

    def test_pii_is_deliberately_absent(self) -> None:
        from bristlenose.doctor import _COMMAND_CHECKS

        assert "pii" not in _COMMAND_CHECKS["analyze"], (
            "check_pii probes a model `analyze` never loads — adding it refuses "
            "runs that would have worked. See this class's docstring."
        )

    def test_run_does_still_probe_it(self) -> None:
        """The guard is specific to analyze — `run` genuinely needs the stack."""
        from bristlenose.doctor import _COMMAND_CHECKS

        assert "pii" in _COMMAND_CHECKS["run"]


class TestTheReportSaysWhenItWasRedacted:
    """`Project.pii_redacted` — the one field the header reads.

    There was no user-visible sign anywhere that a project had been redacted
    (verified 13 Sep 2026 across the SPA, report, export, static renderer and
    the Mac). This is that field. It rides on `/info`, which is one of the
    payloads baked into the offline HTML export, so the same value serves the
    live report and the file a researcher hands over.

    It must FOLLOW the setting, not latch: the whole reason it can be trusted
    is that a run which does not redact clears `transcripts-cooked/`, so the
    signal can no longer outlive the setting.
    """

    @staticmethod
    def _project_dir(tmp_path: Path, *, redacted: bool) -> Path:
        out = tmp_path / "bristlenose-output"
        (out / ".bristlenose" / "intermediate").mkdir(parents=True, exist_ok=True)
        raw = out / "transcripts-raw"
        raw.mkdir(exist_ok=True)
        (raw / "s1.txt").write_text(
            "# Transcript: s1\n\n[00:02] [p1] Hello there.\n", encoding="utf-8",
        )
        cooked = out / "transcripts-cooked"
        if redacted:
            cooked.mkdir(exist_ok=True)
            (cooked / "s1.txt").write_text(
                "# Transcript: s1\n\n[00:02] [p1] Hello there.\n", encoding="utf-8",
            )
        elif cooked.exists():
            import shutil

            shutil.rmtree(cooked)
        return tmp_path

    @staticmethod
    def _import(project_dir: Path):
        from bristlenose.server.db import create_session_factory, get_engine, init_db
        from bristlenose.server.importer import import_project

        engine = get_engine("sqlite://")
        init_db(engine)
        db = create_session_factory(engine)()
        return db, import_project(db, project_dir)

    def test_true_for_a_redacted_project(self, tmp_path: Path) -> None:
        _, project = self._import(self._project_dir(tmp_path, redacted=True))
        assert project.pii_redacted is True

    def test_false_when_nothing_was_redacted(self, tmp_path: Path) -> None:
        """The default, and the overwhelmingly common case — redaction is opt-in.

        False must mean the header says *nothing*, not that it claims the
        negative: a "not redacted" line on every report is noise, and faintly
        alarming to a client who never asked the question.
        """
        _, project = self._import(self._project_dir(tmp_path, redacted=False))
        assert project.pii_redacted is False

    def test_it_follows_the_setting_rather_than_latching(
        self, tmp_path: Path
    ) -> None:
        """Redact, then re-run without — the row must come back to False.

        A latching flag would leave the report claiming redaction over text
        that is no longer redacted, which is the false privacy claim this
        whole change exists to avoid.
        """
        from bristlenose.server.importer import import_project

        proj = self._project_dir(tmp_path, redacted=True)
        db, project = self._import(proj)
        assert project.pii_redacted is True

        self._project_dir(tmp_path, redacted=False)   # stage 7 cleared cooked/
        project = import_project(db, proj)

        assert project.pii_redacted is False, (
            "the report would go on claiming redaction over un-redacted text"
        )


class TestInfoEndpointCarriesTheRedactionFlag:
    """`/info` is the carrier, and it is embedded in the offline export."""

    def test_info_reports_the_flag(self) -> None:
        from fastapi.testclient import TestClient  # noqa: F401  (via AuthTestClient)

        from bristlenose.server.app import create_app
        from tests.conftest import AuthTestClient

        fixture = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
        client = AuthTestClient(create_app(project_dir=fixture, dev=True, db_url="sqlite://"))

        data = client.get("/api/projects/1/info").json()
        assert "pii_redacted" in data, (
            "the header has no way to know; the flag never reaches the export embed"
        )
        # The smoke fixture has no transcripts-cooked/, so this is the honest
        # negative — and the header renders nothing for it.
        assert data["pii_redacted"] is False


class TestTurningRedactionOffGivesTheParticipantsWordsBack:
    """The mirror of `TestReanalysingWithRedactionReplacesTheText`.

    That one fixed raw-rows-then-redact (12 Sep). Its mirror stayed open, and
    the one-directional test could not see it: the skip asked *which directory
    am I reading*, when the question is *which vintage is already in the DB* —
    which no column records.

    Turning redaction off and re-analysing: stage 7 clears
    `transcripts-cooked/`, so the importer correctly reads raw — then skipped,
    and kept the redacted rows. Quotes came back un-redacted (they re-import
    from `extracted_quotes.json`, regenerated because `pii_enabled` is in the
    topic stage's input hashes); transcript pages did not. One project, two
    vintages. Real SQLite, because the whole point is what the rows say.
    """

    REAL = "My name is Martin and I live in London."
    COOKED = "My name is [NAME] and I live in [LOCATION]."

    @staticmethod
    def _db():
        from bristlenose.server.db import create_session_factory, get_engine, init_db

        engine = get_engine("sqlite://")
        init_db(engine)
        return create_session_factory(engine)()

    @staticmethod
    def _session(db):
        from bristlenose.server.models import Project
        from bristlenose.server.models import Session as SessionModel

        project = Project(name="p", input_dir="/in", output_dir="/out")
        db.add(project)
        db.flush()
        sess = SessionModel(project_id=project.id, session_id="s1", session_number=1)
        db.add(sess)
        db.flush()
        return {"s1": sess}

    @classmethod
    def _write(cls, dirpath: Path, text: str) -> Path:
        dirpath.mkdir(parents=True, exist_ok=True)
        (dirpath / "s1.txt").write_text(
            f"# Transcript: s1\n\n[00:02] [p1] {text}\n", encoding="utf-8",
        )
        return dirpath

    def _texts(self, db, session_map):
        from bristlenose.server.models import TranscriptSegment

        return [
            r.text for r in db.query(TranscriptSegment)
            .filter_by(session_id=session_map["s1"].id)
            .order_by(TranscriptSegment.segment_index)
        ]

    def test_the_db_does_not_keep_redacted_rows_after_redaction_is_turned_off(
        self, tmp_path: Path
    ) -> None:
        from bristlenose.server.importer import _import_transcript_segments

        db = self._db()
        session_map = self._session(db)

        # Run 1, redacted: rows come from transcripts-cooked/.
        cooked = self._write(tmp_path / "transcripts-cooked", self.COOKED)
        _import_transcript_segments(db, session_map, cooked)
        db.commit()
        assert self._texts(db, session_map) == [self.COOKED]

        # Run 2, redaction off: stage 7 has cleared cooked, so the importer
        # reads raw. The rows must follow.
        raw = self._write(tmp_path / "transcripts-raw", self.REAL)
        _import_transcript_segments(db, session_map, raw)
        db.commit()

        assert self._texts(db, session_map) == [self.REAL], (
            "the DB kept the redacted text after redaction was turned off — "
            "quotes re-import un-redacted while transcript pages still read "
            "[NAME], so one project serves two vintages"
        )

    def test_the_other_direction_still_holds(self, tmp_path: Path) -> None:
        """Raw first, then redacted — the 12 Sep fix must not regress."""
        from bristlenose.server.importer import _import_transcript_segments

        db = self._db()
        session_map = self._session(db)

        raw = self._write(tmp_path / "transcripts-raw", self.REAL)
        _import_transcript_segments(db, session_map, raw)
        db.commit()

        cooked = self._write(tmp_path / "transcripts-cooked", self.COOKED)
        _import_transcript_segments(db, session_map, cooked)
        db.commit()

        assert self._texts(db, session_map) == [self.COOKED]

    def test_reimporting_the_same_directory_is_idempotent(
        self, tmp_path: Path
    ) -> None:
        """Replacing unconditionally must not duplicate rows on a plain re-serve."""
        from bristlenose.server.importer import _import_transcript_segments

        db = self._db()
        session_map = self._session(db)
        raw = self._write(tmp_path / "transcripts-raw", self.REAL)

        for _ in range(3):
            _import_transcript_segments(db, session_map, raw)
            db.commit()

        assert self._texts(db, session_map) == [self.REAL]


class TestTurningRedactionOffClearsTheRedactedCopy:
    """The mirror of the class below: redaction state outliving the setting.

    Three readers infer "is this project redacted?" from "does
    ``transcripts-cooked/`` exist?" — the serve importer's
    ``_find_transcripts_dir``, ``run_render_only``'s coverage loader, and the
    importer's word-timing guard. Sound only while that directory cannot
    outlive the setting; it could. Measured 13 Sep 2026: a project redacted
    over 2 sessions, then re-run un-redacted with a 3rd added, served the
    **earlier run's redacted text with session 3 absent** — and said nothing.

    Rather than teach three readers to consult the manifest, stage 7 clears the
    directory when it does not redact, which makes the inference they already
    make true. ``transcripts-raw/`` is never touched (D4).
    """

    @staticmethod
    def _project(tmp_path: Path, *, cooked: list[str], raw: list[str]) -> Path:
        out = tmp_path / "bristlenose-output"
        (out / ".bristlenose").mkdir(parents=True)
        for name, sids in (("transcripts-cooked", cooked), ("transcripts-raw", raw)):
            d = out / name
            d.mkdir()
            for sid in sids:
                (d / f"{sid}.txt").write_text(f"[p1] {name} {sid}\n", encoding="utf-8")
        (out / ".bristlenose" / "pii_summary.txt").write_text(
            "Jane Smith -> [NAME] at 00:02\n", encoding="utf-8",
        )
        return out

    def test_clears_the_cooked_copy_and_the_reidentification_key(
        self, tmp_path: Path
    ) -> None:
        from bristlenose.pipeline import _discard_stale_redaction

        out = self._project(tmp_path, cooked=["s1", "s2"], raw=["s1", "s2", "s3"])
        _discard_stale_redaction(out)

        assert not (out / "transcripts-cooked").exists()
        assert not (out / ".bristlenose" / "pii_summary.txt").exists(), (
            "pii_summary.txt lists every original PII value with timecodes; "
            "once the transcripts it describes are gone it audits nothing and "
            "is only a re-identification key left in the project"
        )

    def test_never_touches_the_originals(self, tmp_path: Path) -> None:
        """D4: redaction protects the onward artefact, not the disk."""
        from bristlenose.pipeline import _discard_stale_redaction

        out = self._project(tmp_path, cooked=["s1", "s2"], raw=["s1", "s2", "s3"])
        _discard_stale_redaction(out)

        raw = out / "transcripts-raw"
        assert sorted(p.name for p in raw.glob("*.txt")) == ["s1.txt", "s2.txt", "s3.txt"]

    def test_the_serve_importer_then_reads_the_current_transcripts(
        self, tmp_path: Path
    ) -> None:
        """The outcome that matters, not the rule that produces it.

        Before: the importer picked transcripts-cooked/ and read 2 stale files
        while 3 current ones sat beside it. This asserts the reader's answer,
        so it keeps biting if the cleanup ever moves or is reimplemented.
        """
        from bristlenose.pipeline import _discard_stale_redaction
        from bristlenose.server.importer import _find_transcripts_dir

        out = self._project(tmp_path, cooked=["s1", "s2"], raw=["s1", "s2", "s3"])
        assert _find_transcripts_dir(out.parent, out).name == "transcripts-cooked"

        _discard_stale_redaction(out)

        chosen = _find_transcripts_dir(out.parent, out)
        assert chosen.name == "transcripts-raw"
        assert sorted(p.name for p in chosen.glob("*.txt")) == [
            "s1.txt", "s2.txt", "s3.txt",
        ], "session 3 must not be missing from the report"

    def test_is_a_no_op_on_a_project_that_was_never_redacted(
        self, tmp_path: Path
    ) -> None:
        """The overwhelmingly common path — redaction is off by default."""
        from bristlenose.pipeline import _discard_stale_redaction

        out = tmp_path / "bristlenose-output"
        (out / "transcripts-raw").mkdir(parents=True)
        (out / "transcripts-raw" / "s1.txt").write_text("[p1] hi\n", encoding="utf-8")

        _discard_stale_redaction(out)  # must not raise

        assert (out / "transcripts-raw" / "s1.txt").exists()

    def test_a_failed_removal_warns_and_does_not_kill_the_run(
        self, tmp_path: Path, capsys
    ) -> None:
        """Cleanup must never fail a run — but must not shrug either.

        The surviving directory is exactly what makes the three readers wrong,
        so the warning names that consequence rather than reporting an errno.
        """
        from unittest.mock import patch

        from bristlenose.pipeline import _discard_stale_redaction

        out = self._project(tmp_path, cooked=["s1"], raw=["s1"])
        with patch("bristlenose.pipeline.shutil.rmtree", side_effect=OSError("nope")):
            _discard_stale_redaction(out)  # must not raise

        assert "previous run's redacted text" in capsys.readouterr().out


class TestReanalysingWithRedactionReplacesTheText:
    """The DB must not outlive the redaction it predates.

    `_import_transcript_segments` skips any session that already has rows. So a
    project analysed once WITHOUT redaction and then re-analysed WITH it landed
    `transcripts-cooked/` and `pii_summary.txt`, `status` said redaction ran —
    and the served report, the export and the MCP endpoint kept the original
    text. The words_json remediation above patched the timing half of exactly
    this hole and left the text half. Real SQLite, because the whole point is
    what the rows say afterwards.
    """

    NAME = "Aoife Nic Dhonnchadha"

    @staticmethod
    def _db():
        from bristlenose.server.db import create_session_factory, get_engine, init_db

        engine = get_engine("sqlite://")
        init_db(engine)
        return create_session_factory(engine)()

    @classmethod
    def _session(cls, db):
        from bristlenose.server.models import Project
        from bristlenose.server.models import Session as SessionModel

        project = Project(name="p", input_dir="/in", output_dir="/out")
        db.add(project)
        db.flush()
        sess = SessionModel(project_id=project.id, session_id="s1", session_number=1)
        db.add(sess)
        db.flush()
        return {"s1": sess}

    @staticmethod
    def _write(dirpath: Path, text: str) -> Path:
        dirpath.mkdir(parents=True, exist_ok=True)
        (dirpath / "s1.txt").write_text(
            f"# Transcript: s1\n\n[00:02] [p1] {text}\n[00:10] [m1] And then?\n",
            encoding="utf-8",
        )
        return dirpath

    def test_cooked_replaces_rows_a_raw_import_left(self, tmp_path: Path) -> None:
        from bristlenose.server.importer import _import_transcript_segments
        from bristlenose.server.models import TranscriptSegment

        db = self._db()
        session_map = self._session(db)

        _import_transcript_segments(
            db, session_map, self._write(tmp_path / "transcripts-raw", f"I am {self.NAME}.")
        )
        db.commit()
        assert self.NAME in db.query(TranscriptSegment).first().text  # the pre-state

        _import_transcript_segments(
            db, session_map, self._write(tmp_path / "transcripts-cooked", "I am [NAME].")
        )
        db.commit()

        texts = [s.text for s in db.query(TranscriptSegment).all()]
        assert all(self.NAME not in t for t in texts), (
            f"the participant's name survived a redacted re-import: {texts!r}"
        )
        assert any("[NAME]" in t for t in texts)
        assert len(texts) == 2, "replace, not append — the row count must not grow"

    def test_raw_over_raw_takes_the_newer_text(self, tmp_path: Path) -> None:
        """A re-import picks up a changed transcript, and does not duplicate rows.

        This test used to be `test_raw_over_raw_still_skips` and asserted the
        opposite — that the FIRST import's text survives a second one carrying
        different text. Its docstring called that "a shortcut for the idempotent
        case", but its own fixture writes *different* text on the second pass,
        so what it pinned was staleness, not idempotence: a re-transcribed or
        hand-corrected session never reached the DB. It also asserted stable row
        **ids**, which is not a contract — no FK targets `transcript_segments`
        and quotes locate a segment by `(session_id, segment_index)`.

        Rewritten rather than deleted (13 Sep 2026): the idempotence half is
        real and still worth a guard, so it is asserted below on row count.
        """
        from bristlenose.server.importer import _import_transcript_segments
        from bristlenose.server.models import TranscriptSegment

        db = self._db()
        session_map = self._session(db)
        raw = self._write(tmp_path / "transcripts-raw", "first import")
        _import_transcript_segments(db, session_map, raw)
        db.commit()
        first_count = db.query(TranscriptSegment).count()

        self._write(tmp_path / "transcripts-raw", "second import, same session")
        _import_transcript_segments(db, session_map, raw)
        db.commit()

        rows = db.query(TranscriptSegment).all()
        assert len(rows) == first_count, "replace, not append"
        assert any("second import" in r.text for r in rows), (
            "the file on disk must win — otherwise a corrected transcript "
            "never reaches the served report"
        )
