"""A damaged progress record reads as no record, never as a crash (R111).

`pipeline-manifest.json` is rewritten after every stage. A power cut, a full
disk or a hand edit can leave it truncated, and until 20 Oct 2026 every reader
raised a pydantic ValidationError: `run` and `status` printed a traceback and
went on doing so until the file was deleted by hand. The held resume copy was
already read this way (`resume_manifest`); the manifest itself now is too.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bristlenose.cli import app
from bristlenose.manifest import (
    MANIFEST_FILENAME,
    create_manifest,
    hold_for_resume,
    load_manifest,
    resume_manifest,
    write_manifest,
)

_TRUNCATED = '{"schema_version": 1, "project_name": "x", "stag'


def _corrupt(output_dir: Path) -> Path:
    path = output_dir / ".bristlenose" / MANIFEST_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_TRUNCATED, encoding="utf-8")
    return path


class TestTheReader:
    def test_a_truncated_manifest_reads_as_absent_and_says_so(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture,
    ) -> None:
        path = _corrupt(tmp_path)
        with caplog.at_level(logging.WARNING, logger="bristlenose.manifest"):
            assert load_manifest(tmp_path) is None
        assert any(str(path) in r.getMessage() for r in caplog.records)

    def test_strict_still_raises_for_the_reader_that_waits(self, tmp_path: Path) -> None:
        """The progressive importer tells "not yet readable" from "absent"."""
        _corrupt(tmp_path)
        with pytest.raises(ValueError):
            load_manifest(tmp_path, strict=True)

    def test_resume_falls_back_to_the_held_copy(self, tmp_path: Path) -> None:
        held = create_manifest("p", "1.0")
        hold_for_resume(held, tmp_path)
        _corrupt(tmp_path)
        got = resume_manifest(tmp_path)
        assert got is not None and got.project_name == "p"

    def test_a_write_replaces_the_damaged_file(self, tmp_path: Path) -> None:
        _corrupt(tmp_path)
        write_manifest(create_manifest("p", "1.0"), tmp_path)
        assert load_manifest(tmp_path, strict=True) is not None


@pytest.fixture
def cli_to_pipeline(monkeypatch):
    monkeypatch.setattr("bristlenose.config._populate_keys_from_keychain", lambda s: s)
    monkeypatch.setattr("bristlenose.cli._maybe_guide_provider_setup", lambda s: None)
    monkeypatch.setattr("bristlenose.cli._maybe_auto_doctor", lambda s, c: True)
    monkeypatch.setattr("bristlenose.preflight.api_key.preflight_api_key", lambda **kw: None)
    return CliRunner()


class TestTheCommands:
    def test_status_says_there_is_no_record(self, tmp_path: Path) -> None:
        out = tmp_path / "interviews" / "bristlenose-output"
        _corrupt(out)
        result = CliRunner().invoke(app, ["status", str(tmp_path / "interviews")])
        assert result.exception is None or isinstance(result.exception, SystemExit), (
            result.exception
        )
        assert "No pipeline manifest" in result.output

    def test_run_resumes_into_the_folder_instead_of_crashing(
        self, cli_to_pipeline: CliRunner, tmp_path: Path, monkeypatch,
    ) -> None:
        """A previous run was here: the folder is reused, not walled off.

        Treating the file as absent at the guard would answer "Output directory
        already exists — use --clean", which the Mac app cannot pass and which
        deletes the researcher's report. The file's presence still says a run
        was here; only its contents are not trusted.
        """
        input_dir = tmp_path / "interviews"
        out = input_dir / "bristlenose-output"
        out.mkdir(parents=True)
        (out / "bristlenose-report.html").write_text("old", encoding="utf-8")
        (out / ".bristlenose").mkdir()
        (out / ".bristlenose" / "pipeline-events.jsonl").write_text(
            json.dumps({"event": "run_completed", "run_id": "old"}) + "\n", encoding="utf-8",
        )
        _corrupt(out)
        reached: list[Path] = []

        async def _fake_run(self, input_dir, output_dir):
            reached.append(output_dir)
            raise RuntimeError("stop here")

        monkeypatch.setattr("bristlenose.pipeline.Pipeline.run", _fake_run)
        result = cli_to_pipeline.invoke(app, ["run", str(input_dir), "--no-serve"])
        assert reached, result.output
        assert "already exists" not in result.output


def test_the_progressive_importer_waits_on_an_unreadable_manifest(tmp_path: Path) -> None:
    """While a run writes it, an unreadable manifest is "not yet", not "nothing".

    `_manifest_sets` returns None (import nothing this pass, read again next
    time) for an unreadable file and empty sets for an absent one, so it reads
    the manifest strictly rather than through the tolerant default.
    """
    from bristlenose.server.progressive import ProgressiveImport

    project = tmp_path / "interviews"
    _corrupt(project / "bristlenose-output")
    follower = ProgressiveImport(object(), lambda: None, project)  # type: ignore[arg-type]
    assert follower._manifest_sets(None) is None


def test_the_manifest_is_on_disk_before_it_replaces_the_old_one(
    tmp_path: Path, monkeypatch,
) -> None:
    """Without the fsync a power cut can leave the renamed file empty."""
    import bristlenose.manifest as m

    synced: list[int] = []
    monkeypatch.setattr(m.os, "fsync", lambda fd: synced.append(fd))
    write_manifest(create_manifest("p", "1.0"), tmp_path)
    assert synced
