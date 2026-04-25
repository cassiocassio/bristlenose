"""Tests for bristlenose.events — Phase 4a-pre run-level event log.

Slice 1: pure data layer. Pydantic round-trip, append-only writer,
crash/NUL recovery, concurrent appends, message capping, tail reader.
Lifecycle / signal handling / PID files belong to Slice 2.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from bristlenose.events import (
    CAUSE_MESSAGE_MAX,
    SCHEMA_VERSION,
    Cause,
    CauseCategoryEnum,
    KindEnum,
    OutcomeEnum,
    Process,
    RunCancelledEvent,
    RunCompletedEvent,
    RunFailedEvent,
    RunStartedEvent,
    _now_iso,
    _parse_event_line,
    append_event,
    events_path,
    is_retryable,
    new_run_id,
    read_events,
    tail_run_state,
)
from bristlenose.manifest import (
    STAGE_INGEST,
    SessionRecord,
    StageStatus,
    create_manifest,
    mark_stage_complete,
    write_manifest,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_started(run_id: str | None = None, kind: KindEnum = KindEnum.RUN) -> RunStartedEvent:
    rid = run_id or new_run_id()
    now = _now_iso()
    return RunStartedEvent(
        ts=now,
        run_id=rid,
        kind=kind,
        started_at=now,
        process=Process(
            pid=12345,
            start_time=now,
            hostname="testhost",
            user="tester",
            bristlenose_version="0.0.0-test",
            python_version="3.12.3",
            os="darwin-arm64",
        ),
    )


def _make_completed(started: RunStartedEvent) -> RunCompletedEvent:
    now = _now_iso()
    return RunCompletedEvent(
        ts=now,
        run_id=started.run_id,
        kind=started.kind,
        started_at=started.started_at,
        ended_at=now,
        input_tokens=12000,
        output_tokens=5000,
        cost_usd_estimate=0.42,
        price_table_version="2026-04-25",
    )


def _make_cancelled(started: RunStartedEvent) -> RunCancelledEvent:
    now = _now_iso()
    return RunCancelledEvent(
        ts=now,
        run_id=started.run_id,
        kind=started.kind,
        started_at=started.started_at,
        ended_at=now,
        cause=Cause(
            category=CauseCategoryEnum.USER_SIGNAL,
            signal=2,
            signal_name="SIGINT",
            stage="transcribe",
        ),
    )


def _make_failed(
    started: RunStartedEvent,
    category: CauseCategoryEnum = CauseCategoryEnum.QUOTA,
) -> RunFailedEvent:
    now = _now_iso()
    return RunFailedEvent(
        ts=now,
        run_id=started.run_id,
        kind=started.kind,
        started_at=started.started_at,
        ended_at=now,
        cause=Cause(
            category=category,
            code="rate_limit_exceeded",
            message="Anthropic 429: rate limit exceeded.",
            provider="anthropic",
            stage="quote_extraction",
        ),
    )


# ---------------------------------------------------------------------------
# Enum + retryable rule
# ---------------------------------------------------------------------------


def test_cause_category_matches_swift_enum():
    """Names must match shipped Swift PipelineFailureCategory exactly.

    Existing cases (auth/network/quota/disk/whisper/unknown) preserved;
    new cases additive. Cross-boundary rename was rejected — see design
    doc round-2 changelog.
    """
    expected = {
        "user_signal", "auth", "quota", "api_request", "api_server",
        "network", "whisper", "missing_dep", "disk", "unknown",
    }
    actual = {c.value for c in CauseCategoryEnum}
    assert actual == expected


def test_kind_enum_does_not_include_render():
    """Render does NOT write the events log — see design doc round-2."""
    values = {k.value for k in KindEnum}
    assert "render" not in values
    assert values == {"run", "analyze", "transcribe-only"}


def test_is_retryable_rule():
    assert is_retryable(CauseCategoryEnum.USER_SIGNAL) is True
    assert is_retryable(CauseCategoryEnum.AUTH) is False
    assert is_retryable(CauseCategoryEnum.MISSING_DEP) is False
    assert is_retryable(CauseCategoryEnum.DISK) is False
    assert is_retryable(CauseCategoryEnum.QUOTA) is True
    assert is_retryable(CauseCategoryEnum.NETWORK) is True
    assert is_retryable(CauseCategoryEnum.UNKNOWN) is True


# ---------------------------------------------------------------------------
# ULID generator
# ---------------------------------------------------------------------------


def test_new_run_id_format():
    rid = new_run_id()
    assert len(rid) == 26
    # Crockford base32 alphabet, no I/L/O/U.
    allowed = set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
    assert set(rid) <= allowed


def test_new_run_id_uniqueness_and_sortability():
    """ULIDs are time-prefixed; later IDs sort >= earlier ones lexicographically."""
    ids = [new_run_id() for _ in range(50)]
    assert len(set(ids)) == 50  # uniqueness
    # Sortability holds across same millisecond modulo random component;
    # check on a coarse 10ms gap.
    import time
    a = new_run_id()
    time.sleep(0.01)
    b = new_run_id()
    assert b > a


# ---------------------------------------------------------------------------
# Pydantic round-trip
# ---------------------------------------------------------------------------


def test_run_started_round_trip():
    ev = _make_started()
    raw = ev.model_dump_json()
    parsed = RunStartedEvent.model_validate_json(raw)
    assert parsed == ev
    assert parsed.schema_version == SCHEMA_VERSION
    assert parsed.process.pid == 12345


def test_run_completed_round_trip():
    started = _make_started()
    ev = _make_completed(started)
    parsed = RunCompletedEvent.model_validate_json(ev.model_dump_json())
    assert parsed == ev
    assert parsed.outcome == OutcomeEnum.COMPLETED
    assert parsed.cause is None


def test_run_cancelled_round_trip():
    started = _make_started()
    ev = _make_cancelled(started)
    parsed = RunCancelledEvent.model_validate_json(ev.model_dump_json())
    assert parsed == ev
    assert parsed.cause.category == CauseCategoryEnum.USER_SIGNAL
    assert parsed.cause.signal == 2


@pytest.mark.parametrize(
    "category",
    [
        CauseCategoryEnum.AUTH,
        CauseCategoryEnum.QUOTA,
        CauseCategoryEnum.API_REQUEST,
        CauseCategoryEnum.API_SERVER,
        CauseCategoryEnum.NETWORK,
        CauseCategoryEnum.WHISPER,
        CauseCategoryEnum.MISSING_DEP,
        CauseCategoryEnum.DISK,
        CauseCategoryEnum.UNKNOWN,
    ],
)
def test_run_failed_round_trip_per_category(category):
    started = _make_started()
    ev = _make_failed(started, category=category)
    parsed = RunFailedEvent.model_validate_json(ev.model_dump_json())
    assert parsed == ev
    assert parsed.cause.category == category


def test_run_failed_requires_cause_message_for_non_user_signal():
    """Writer rule: message required unless category=user_signal."""
    started = _make_started()
    now = _now_iso()
    with pytest.raises(ValueError, match="message is required"):
        RunFailedEvent(
            ts=now,
            run_id=started.run_id,
            kind=started.kind,
            started_at=started.started_at,
            ended_at=now,
            cause=Cause(category=CauseCategoryEnum.AUTH),  # no message
        )


def test_cause_message_capped_at_4kb():
    huge = "x" * (CAUSE_MESSAGE_MAX * 16)  # 64 KB input
    c = Cause(category=CauseCategoryEnum.UNKNOWN, message=huge)
    assert c.message is not None
    assert len(c.message.encode("utf-8")) <= CAUSE_MESSAGE_MAX


def test_cause_message_empty_string_treated_as_missing():
    """Empty string fails the writer rule (it's not a meaningful message)."""
    started = _make_started()
    now = _now_iso()
    with pytest.raises(ValueError):
        RunFailedEvent(
            ts=now,
            run_id=started.run_id,
            kind=started.kind,
            started_at=started.started_at,
            ended_at=now,
            cause=Cause(category=CauseCategoryEnum.AUTH, message=""),
        )


# ---------------------------------------------------------------------------
# Append-only writer
# ---------------------------------------------------------------------------


def test_append_event_creates_directory_and_file(tmp_path: Path):
    f = events_path(tmp_path)
    assert not f.exists()
    started = _make_started()
    append_event(f, started)
    assert f.exists()
    assert f.parent.name == ".bristlenose"


def test_append_event_round_trip_100(tmp_path: Path):
    f = events_path(tmp_path)
    written = []
    for _ in range(100):
        started = _make_started()
        append_event(f, started)
        written.append(started)
    read_back = read_events(f)
    assert len(read_back) == 100
    for w, r in zip(written, read_back):
        assert isinstance(r, RunStartedEvent)
        assert r.run_id == w.run_id


def test_append_event_lines_end_with_newline(tmp_path: Path):
    f = events_path(tmp_path)
    append_event(f, _make_started())
    append_event(f, _make_started())
    raw = f.read_bytes()
    assert raw.endswith(b"\n")
    # Two complete lines.
    assert raw.count(b"\n") == 2


# ---------------------------------------------------------------------------
# Crash / corruption recovery
# ---------------------------------------------------------------------------


def test_reader_recovers_from_partial_trailing_line(tmp_path: Path):
    """Crash mid-write leaves a line without trailing \\n. Drop and recover."""
    f = events_path(tmp_path)
    started = _make_started()
    append_event(f, started)
    # Append a partial / torn line (simulate crash mid-write).
    with open(f, "ab") as fh:
        fh.write(b'{"schema_version":1,"event":"run_started","run_id":"BROKEN')  # no \n
    events = read_events(f)
    # The good line still parses; the partial is silently dropped.
    assert len(events) == 1
    assert events[0].run_id == started.run_id


def test_reader_recovers_from_nul_padded_tail(tmp_path: Path):
    """Power-loss tail: trailing NUL padding. Strip and recover."""
    f = events_path(tmp_path)
    append_event(f, _make_started())
    with open(f, "ab") as fh:
        fh.write(b"\x00" * 4096)
    events = read_events(f)
    assert len(events) == 1


def test_reader_recovers_from_malformed_json_line(tmp_path: Path):
    """Garbage middle line — skipped, surrounding lines still parse."""
    f = events_path(tmp_path)
    a = _make_started()
    b = _make_started()
    append_event(f, a)
    with open(f, "ab") as fh:
        fh.write(b"{this is not json}\n")
    append_event(f, b)
    events = read_events(f)
    assert len(events) == 2
    assert events[0].run_id == a.run_id
    assert events[1].run_id == b.run_id


def test_parse_event_line_returns_none_for_bad_input():
    assert _parse_event_line("") is None
    assert _parse_event_line("\x00\x00") is None
    assert _parse_event_line("not-json") is None
    assert _parse_event_line('{"event":"unknown_type","run_id":"x"}') is None


def test_reader_returns_empty_for_missing_file(tmp_path: Path):
    f = events_path(tmp_path)
    assert read_events(f) == []


# ---------------------------------------------------------------------------
# Tail reader / RunState derivation
# ---------------------------------------------------------------------------


def test_tail_run_state_empty_log(tmp_path: Path):
    state = tail_run_state(events_path(tmp_path))
    assert state.last_event is None
    assert state.in_flight is False
    assert state.stages_complete == []


def test_tail_run_state_only_run_started(tmp_path: Path):
    f = events_path(tmp_path)
    started = _make_started()
    append_event(f, started)
    state = tail_run_state(f)
    assert isinstance(state.last_event, RunStartedEvent)
    assert state.in_flight is True


def test_tail_run_state_started_then_completed(tmp_path: Path):
    f = events_path(tmp_path)
    started = _make_started()
    append_event(f, started)
    append_event(f, _make_completed(started))
    state = tail_run_state(f)
    assert isinstance(state.last_event, RunCompletedEvent)
    assert state.in_flight is False


def test_tail_run_state_orphaned_started_after_prior_completed(tmp_path: Path):
    """Stranded run_started after a previous completed run — in-flight from new run's perspective."""
    f = events_path(tmp_path)
    s1 = _make_started()
    append_event(f, s1)
    append_event(f, _make_completed(s1))
    s2 = _make_started()
    append_event(f, s2)
    state = tail_run_state(f)
    assert isinstance(state.last_event, RunStartedEvent)
    assert state.last_event.run_id == s2.run_id
    assert state.in_flight is True


def test_tail_run_state_reads_stages_complete_from_manifest(tmp_path: Path):
    # Create a manifest with one stage complete.
    manifest = create_manifest("test", "0.0.0")
    mark_stage_complete(manifest, STAGE_INGEST)
    write_manifest(manifest, tmp_path)
    # And a completed run in the events log.
    f = events_path(tmp_path)
    started = _make_started()
    append_event(f, started)
    append_event(f, _make_completed(started))
    manifest_file = tmp_path / ".bristlenose" / "pipeline-manifest.json"
    state = tail_run_state(f, manifest_file)
    assert STAGE_INGEST in state.stages_complete


# ---------------------------------------------------------------------------
# SessionRecord cost-fields extension (additive — Phase 1f)
# ---------------------------------------------------------------------------


def test_session_record_cost_fields_default_none():
    """Old records load with None — additive change."""
    sr = SessionRecord(status=StageStatus.COMPLETE, session_id="s1")
    assert sr.input_tokens is None
    assert sr.output_tokens is None
    assert sr.cost_usd_estimate is None
    assert sr.price_table_version is None


def test_session_record_cost_fields_round_trip():
    sr = SessionRecord(
        status=StageStatus.COMPLETE,
        session_id="s1",
        input_tokens=12000,
        output_tokens=5000,
        cost_usd_estimate=0.42,
        price_table_version="2026-04-25",
    )
    parsed = SessionRecord.model_validate_json(sr.model_dump_json())
    assert parsed == sr


def test_session_record_old_json_loads_with_none_cost_fields():
    """Forward-compat: a SessionRecord JSON without cost fields still loads."""
    old = json.dumps({
        "status": "complete",
        "session_id": "s1",
        "completed_at": "2026-01-01T00:00:00Z",
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
    })
    sr = SessionRecord.model_validate_json(old)
    assert sr.cost_usd_estimate is None


# ---------------------------------------------------------------------------
# Concurrent O_APPEND (subprocess test)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n_writers,events_per", [(2, 100)])
def test_concurrent_o_append_does_not_tear_lines(tmp_path: Path, n_writers: int, events_per: int):
    """Two subprocesses appending in parallel: all lines parse, none torn.

    POSIX O_APPEND guarantees seek-to-end-and-write atomically per write()
    on regular files. Verify the guarantee holds at JSONL line size on the
    current platform (macOS APFS or Linux ext4 in CI).
    """
    f = events_path(tmp_path)
    f.parent.mkdir(parents=True, exist_ok=True)

    # Each subprocess appends events_per RunStartedEvent lines via the same writer.
    script = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {str(Path(__file__).parent.parent)!r})
        from pathlib import Path
        from bristlenose.events import append_event, new_run_id, _now_iso
        from bristlenose.events import RunStartedEvent, KindEnum, Process

        f = Path({str(f)!r})
        for _ in range({events_per}):
            now = _now_iso()
            ev = RunStartedEvent(
                ts=now, run_id=new_run_id(), kind=KindEnum.RUN, started_at=now,
                process=Process(
                    pid=1, start_time=now, hostname="h", user="u",
                    bristlenose_version="0", python_version="3", os="x",
                ),
            )
            append_event(f, ev)
    """)

    procs = [
        subprocess.Popen([sys.executable, "-c", script], env={**os.environ})
        for _ in range(n_writers)
    ]
    for p in procs:
        rc = p.wait(timeout=60)
        assert rc == 0

    events = read_events(f)
    assert len(events) == n_writers * events_per
    # All run_ids must be unique (no torn / merged lines).
    run_ids = {e.run_id for e in events}
    assert len(run_ids) == n_writers * events_per
