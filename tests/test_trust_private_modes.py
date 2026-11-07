"""Trust gate: re-identification keys and secrets are written owner-only (0o600).

Each file here is produced by its real writer, never by hand, and the mode is
read back from disk. The umask is pinned to 0o022 (the common default) so a
writer that leans on the umask instead of an explicit mode reads as 0o644.

Files covered, and why each is private:
- the config ``.env`` (``FileCredentialStore``): provider API keys;
- the preflight ``state.json``: validation timestamps and provider list;
- ``events.jsonl``: OS username and hostname in the process envelope;
- ``llm-calls.jsonl`` (and its trimmed rewrite): a per-call fingerprint;
- the desktop shoal feed: verbatim participant words;
- ``pii_summary.txt``: the original personal data PII removal took out;
- the turn-frames record: JPEGs of the participant's screen, one per speaker turn;
- ``people.yaml``: the researcher's own file of participants' real names, whichever writer
  touched it last (the pipeline's, or serve's write-through, which already made it 0o600).
"""

from __future__ import annotations

import os
import stat
from collections.abc import Iterator
from pathlib import Path

import pytest

import bristlenose

_OWNER_ONLY = 0o600
# What ``stat`` reads back after ``chmod(0o600)``. Windows has no owner bits:
# ``os.chmod`` there only sets or clears the read-only flag, and a writable
# file reads as 0o666 whatever it was asked for (CI, 6 Nov 2026). Privacy on
# Windows is the user profile's ACL, which these writers do not touch; what
# the assertion still proves there is that none of them left a file read-only,
# which the log trim and the store's rewrite would then fail on.
_OWNER_ONLY_AS_READ = 0o666 if os.name == "nt" else _OWNER_ONLY


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


@pytest.fixture(autouse=True)
def _umask_022() -> Iterator[None]:
    old = os.umask(0o022)
    try:
        yield
    finally:
        os.umask(old)


def test_imports_this_tree() -> None:
    assert Path(bristlenose.__file__).is_relative_to(Path(__file__).parents[1])


# -- credentials ------------------------------------------------------------


def test_file_credential_store_writes_owner_only(tmp_path: Path) -> None:
    from bristlenose.credentials import FileCredentialStore

    store = FileCredentialStore(path=tmp_path / "cfg" / ".env")
    store.set("anthropic", "not-a-real-token-1")
    assert store.path.is_file()
    assert _mode(store.path) == _OWNER_ONLY_AS_READ


def test_file_credential_store_tightens_a_preexisting_loose_file(tmp_path: Path) -> None:
    from bristlenose.credentials import FileCredentialStore

    store = FileCredentialStore(path=tmp_path / ".env")
    store.set("anthropic", "not-a-real-token-2")
    os.chmod(store.path, 0o644)  # a file left loose by an older writer or a user
    store.set("openai", "not-a-real-token-3")
    assert _mode(store.path) == _OWNER_ONLY_AS_READ


# -- preflight state ----------------------------------------------------------


@pytest.fixture
def _state_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    from bristlenose.preflight import api_key

    path = api_key.state_path()
    assert path.is_relative_to(tmp_path)
    return path


def test_preflight_state_written_owner_only(_state_home: Path) -> None:
    from bristlenose.preflight.api_key import write_state

    write_state({"version": 1, "first_run": False, "providers": {}})
    assert _mode(_state_home) == _OWNER_ONLY_AS_READ


def test_preflight_state_tightens_a_preexisting_loose_file(_state_home: Path) -> None:
    from bristlenose.preflight.api_key import write_state

    write_state({"version": 1, "first_run": False, "providers": {}})
    os.chmod(_state_home, 0o644)
    write_state({"version": 1, "first_run": False, "providers": {}})
    assert _mode(_state_home) == _OWNER_ONLY_AS_READ


# -- events log -------------------------------------------------------------


def test_events_log_written_owner_only(tmp_path: Path) -> None:
    from bristlenose.events import (
        KindEnum,
        Process,
        RunStartedEvent,
        _now_iso,
        append_event,
        events_path,
    )

    now = _now_iso()
    path = events_path(tmp_path)
    append_event(path, RunStartedEvent(
        ts=now, run_id="run-1", kind=KindEnum.RUN, started_at=now,
        process=Process(pid=1, start_time="seed", hostname="fixture-host", user="fixture-user",
                        bristlenose_version="0", python_version="3.12", os="test")))
    assert path.is_file()
    assert _mode(path) == _OWNER_ONLY_AS_READ


# -- llm-calls.jsonl --------------------------------------------------------


def _record(telemetry) -> None:
    telemetry.record_call(
        provider="anthropic",
        request_model="test-model",
        response_model="test-model",
        input_chars=10,
        elapsed_ms=1,
        outcome="ok",
        price_table_version="2026-04-25",
        stage_override="s09_quote_extraction",
    )


def test_llm_calls_log_written_owner_only(tmp_path: Path, monkeypatch) -> None:
    from bristlenose.llm import telemetry

    monkeypatch.delenv("BRISTLENOSE_LLM_TELEMETRY", raising=False)
    run_dir = tmp_path / ".bristlenose"
    tokens = telemetry.set_run_context("run-1", run_dir)
    try:
        _record(telemetry)
    finally:
        telemetry.reset_run_context(tokens)
    path = run_dir / telemetry.JSONL_FILENAME
    assert path.is_file()
    assert _mode(path) == _OWNER_ONLY_AS_READ


def test_llm_calls_log_stays_owner_only_after_trim(tmp_path: Path, monkeypatch) -> None:
    from bristlenose.llm import telemetry

    monkeypatch.delenv("BRISTLENOSE_LLM_TELEMETRY", raising=False)
    run_dir = tmp_path / ".bristlenose"
    tokens = telemetry.set_run_context("run-1", run_dir)
    try:
        for _ in range(5):
            _record(telemetry)
    finally:
        telemetry.reset_run_context(tokens)
    path = run_dir / telemetry.JSONL_FILENAME
    assert telemetry.trim_to_cap(path, cap=2) == 2
    assert _mode(path) == _OWNER_ONLY_AS_READ


# -- shoal feed -------------------------------------------------------------


def test_shoal_feed_written_owner_only(tmp_path: Path, monkeypatch) -> None:
    from bristlenose import shoal_feed

    monkeypatch.setattr(shoal_feed, "hosted_by_desktop", lambda: True)
    shoal_feed.start(tmp_path)
    shoal_feed.emit_words(tmp_path, ["the onboarding checklist was confusing honestly"])
    path = shoal_feed._feed_path(tmp_path)
    assert path.is_file()
    assert path.read_text(encoding="utf-8").strip(), "the feed should hold a word batch"
    assert _mode(path) == _OWNER_ONLY_AS_READ


# -- pii_summary.txt --------------------------------------------------------


def test_pii_summary_written_owner_only(tmp_path: Path) -> None:
    from bristlenose.stages.s07_pii_removal import PiiRedaction, write_pii_summary

    path = write_pii_summary(
        [PiiRedaction(entity_type="PERSON", original_text="Zephyrine Quillfeather",
                      replacement="[NAME]", score=0.9, timecode=0.0)],
        tmp_path,
    )
    assert path is not None and path.is_file()
    assert _mode(path) == _OWNER_ONLY_AS_READ


def test_pii_summary_tightens_a_preexisting_loose_file(tmp_path: Path) -> None:
    """The mode passed at open applies only on create: a summary left 0o644 by an older run must be tightened."""
    from bristlenose.stages.s07_pii_removal import PiiRedaction, write_pii_summary

    redactions = [PiiRedaction(entity_type="PERSON", original_text="Zephyrine Quillfeather",
                               replacement="[NAME]", score=0.9, timecode=0.0)]
    path = write_pii_summary(redactions, tmp_path)
    assert path is not None
    os.chmod(path, 0o644)
    write_pii_summary(redactions, tmp_path)
    assert _mode(path) == _OWNER_ONLY_AS_READ


# -- the log file ---------------------------------------------------------------


def test_the_log_file_and_its_rotations_are_owner_only(tmp_path: Path) -> None:
    """T26 (trust map row 58): bristlenose.log took the umask default (0o644). It is debug
    output and must not carry names, but it still names the machine, the paths and the
    providers, so it is private like the other files here, and so is each file a rotation
    starts."""
    import logging

    from bristlenose import logging as bn_logging

    bn_logging.setup_logging(output_dir=tmp_path, verbose=False)
    try:
        log = tmp_path / ".bristlenose" / "bristlenose.log"
        logging.getLogger("bristlenose.test").info("a line")
        logging.getLogger().handlers[-1].flush()
        assert _mode(log) == _OWNER_ONLY_AS_READ

        file_handler = next(
            h for h in logging.getLogger().handlers if isinstance(h, logging.FileHandler)
        )
        file_handler.doRollover()  # type: ignore[attr-defined]
        logging.getLogger("bristlenose.test").info("a line after the rotation")
        file_handler.flush()
        assert _mode(log) == _OWNER_ONLY_AS_READ
        assert _mode(log.with_name("bristlenose.log.1")) == _OWNER_ONLY_AS_READ
    finally:
        for h in logging.getLogger().handlers[:]:
            logging.getLogger().removeHandler(h)
            h.close()


def test_loose_older_rotations_are_tightened_and_a_symlink_target_is_left_alone(
    tmp_path: Path,
) -> None:
    """Fable review, 7 Nov 2026: backups an older version rotated stay at 0o644 unless the
    handler tightens them, and a chmod by path would follow a symlink planted at the log path
    into whatever it points at."""
    import logging

    from bristlenose import logging as bn_logging

    run_dir = tmp_path / ".bristlenose"
    run_dir.mkdir()
    for name in ("bristlenose.log.1", "bristlenose.log.2"):
        (run_dir / name).write_text("old\n", encoding="utf-8")
        os.chmod(run_dir / name, 0o644)
    bn_logging.setup_logging(output_dir=tmp_path, verbose=False)
    try:
        assert _mode(run_dir / "bristlenose.log.1") == _OWNER_ONLY_AS_READ
        assert _mode(run_dir / "bristlenose.log.2") == _OWNER_ONLY_AS_READ
    finally:
        for h in logging.getLogger().handlers[:]:
            logging.getLogger().removeHandler(h)
            h.close()

    if os.name == "nt":
        return  # symlinks need a privilege there
    target = tmp_path / "someone-elses-file"
    target.write_text("x\n", encoding="utf-8")
    os.chmod(target, 0o644)
    other = tmp_path / "other"
    (other / ".bristlenose").mkdir(parents=True)
    (other / ".bristlenose" / "bristlenose.log").symlink_to(target)
    bn_logging.setup_logging(output_dir=other, verbose=False)
    try:
        assert _mode(target) == 0o644, "the symlink's target is not ours to chmod"
    finally:
        for h in logging.getLogger().handlers[:]:
            logging.getLogger().removeHandler(h)
            h.close()


# -- turn frames --------------------------------------------------------------


def test_turn_frames_record_is_owner_only(tmp_path: Path) -> None:
    """The record carries the participant's screen as base64 JPEGs, so it is a re-identification
    key of its own kind (docs/design-screens.md): written 0o600, and a loose one is tightened."""
    from bristlenose.utils import turn_frames as tf

    video = tmp_path / "v.mp4"
    video.write_bytes(b"x")
    frames = tf.select_frames([(10.0, 50.0)], [])
    out = tmp_path / "out"
    path = tf.extract_turn_frames("s1", video, frames, out, grabber=lambda v, t: b"\xff\xd8jpeg")
    assert path is not None and path.is_file()
    assert _mode(path) == _OWNER_ONLY_AS_READ
    assert not list(out.glob("*.tmp")), "the temporary file was left behind"
    os.chmod(path, 0o644)  # left loose by an older writer
    other = tf.select_frames([(10.0, 52.0)], [])  # a speaker edit: new selection, new write
    path2 = tf.extract_turn_frames("s1", video, other, out, grabber=lambda v, t: b"\xff\xd8jpeg")
    assert path2 is not None
    assert _mode(path2) == _OWNER_ONLY_AS_READ


# -- people.yaml ---------------------------------------------------------------


def test_people_file_is_owner_only_and_a_loose_one_is_tightened(tmp_path: Path) -> None:
    from datetime import datetime, timezone

    from bristlenose.models import PeopleFile, PersonComputed, PersonEditable, PersonEntry
    from bristlenose.people import write_people_file

    people = PeopleFile(participants={"p1": PersonEntry(
        computed=PersonComputed(
            participant_id="p1", session_id="s1",
            session_date=datetime(2026, 1, 1, tzinfo=timezone.utc), duration_seconds=60.0,
            words_spoken=100, pct_words=50.0, pct_time_speaking=50.0, source_file="a.vtt",
        ),
        editable=PersonEditable(full_name="Not A Real Name"),
    )})
    path = write_people_file(people, tmp_path)
    assert _mode(path) == _OWNER_ONLY_AS_READ
    os.chmod(path, 0o644)  # left loose by an older writer
    write_people_file(people, tmp_path)
    assert _mode(path) == _OWNER_ONLY_AS_READ
    assert "Not A Real Name" in path.read_text(encoding="utf-8")
