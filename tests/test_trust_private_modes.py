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
- ``pii_summary.txt``: the original personal data PII removal took out.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Iterator
from pathlib import Path

import pytest

import bristlenose

_OWNER_ONLY = 0o600


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
    assert _mode(store.path) == _OWNER_ONLY


def test_file_credential_store_tightens_a_preexisting_loose_file(tmp_path: Path) -> None:
    from bristlenose.credentials import FileCredentialStore

    store = FileCredentialStore(path=tmp_path / ".env")
    store.set("anthropic", "not-a-real-token-2")
    os.chmod(store.path, 0o644)  # a file left loose by an older writer or a user
    store.set("openai", "not-a-real-token-3")
    assert _mode(store.path) == _OWNER_ONLY


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
    assert _mode(_state_home) == _OWNER_ONLY


@pytest.mark.xfail(
    strict=True,
    reason="write_state opens with O_CREAT|O_TRUNC 0o600 but never chmods: the mode "
    "applies only on create, so a state.json that already exists 0o644 stays 0o644",
)
def test_preflight_state_tightens_a_preexisting_loose_file(_state_home: Path) -> None:
    from bristlenose.preflight.api_key import write_state

    write_state({"version": 1, "first_run": False, "providers": {}})
    os.chmod(_state_home, 0o644)
    write_state({"version": 1, "first_run": False, "providers": {}})
    assert _mode(_state_home) == _OWNER_ONLY


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
    assert _mode(path) == _OWNER_ONLY


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
    assert _mode(path) == _OWNER_ONLY


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
    assert _mode(path) == _OWNER_ONLY


# -- shoal feed -------------------------------------------------------------


def test_shoal_feed_written_owner_only(tmp_path: Path, monkeypatch) -> None:
    from bristlenose import shoal_feed

    monkeypatch.setattr(shoal_feed, "hosted_by_desktop", lambda: True)
    shoal_feed.start(tmp_path)
    shoal_feed.emit_words(tmp_path, ["the onboarding checklist was confusing honestly"])
    path = shoal_feed._feed_path(tmp_path)
    assert path.is_file()
    assert path.read_text(encoding="utf-8").strip(), "the feed should hold a word batch"
    assert _mode(path) == _OWNER_ONLY


# -- pii_summary.txt --------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason="write_pii_summary uses Path.write_text, so pii_summary.txt (original "
    "personal data, a re-identification key) takes the umask default 0o644",
)
def test_pii_summary_written_owner_only(tmp_path: Path) -> None:
    from bristlenose.stages.s07_pii_removal import PiiRedaction, write_pii_summary

    path = write_pii_summary(
        [PiiRedaction(entity_type="PERSON", original_text="Zephyrine Quillfeather",
                      replacement="[NAME]", score=0.9, timecode=0.0)],
        tmp_path,
    )
    assert path is not None and path.is_file()
    assert _mode(path) == _OWNER_ONLY
