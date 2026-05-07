"""Tests for the serve-mode event watcher (re-import on run_completed)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from bristlenose.events import (
    Cause,
    CauseCategoryEnum,
    KindEnum,
    Process,
    RunCompletedEvent,
    RunFailedEvent,
    RunStartedEvent,
    append_event,
    events_path,
    new_run_id,
)
from bristlenose.server.event_watcher import run_event_watcher

_TS = "2026-05-07T13:00:00Z"


def _process() -> Process:
    return Process(
        pid=1234,
        start_time=_TS,
        hostname="testhost",
        user="tester",
        bristlenose_version="0.0.0-test",
        python_version="3.12",
        os="darwin-arm64",
    )


def _started(run_id: str) -> RunStartedEvent:
    return RunStartedEvent(
        ts=_TS,
        run_id=run_id,
        kind=KindEnum.RUN,
        started_at=_TS,
        process=_process(),
    )


def _completed(run_id: str) -> RunCompletedEvent:
    return RunCompletedEvent(
        ts=_TS,
        run_id=run_id,
        kind=KindEnum.RUN,
        started_at=_TS,
        ended_at=_TS,
    )


def _failed(run_id: str) -> RunFailedEvent:
    return RunFailedEvent(
        ts=_TS,
        run_id=run_id,
        kind=KindEnum.RUN,
        started_at=_TS,
        ended_at=_TS,
        cause=Cause(category=CauseCategoryEnum.UNKNOWN, message="boom"),
    )


@pytest.mark.asyncio
async def test_dispatches_on_new_run_completed(tmp_path: Path) -> None:
    output_dir = tmp_path / "bristlenose-output"
    events_file = events_path(output_dir)
    calls: list[None] = []

    async def cb() -> None:
        calls.append(None)

    task = asyncio.create_task(
        run_event_watcher(events_file, cb, poll_interval=0.05),
    )
    try:
        await asyncio.sleep(0.1)
        run_id = new_run_id()
        append_event(events_file, _started(run_id))
        append_event(events_file, _completed(run_id))
        await asyncio.sleep(0.25)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert len(calls) == 1


@pytest.mark.asyncio
async def test_skips_events_written_before_watcher_started(tmp_path: Path) -> None:
    """Events on disk at watcher-start are baseline — startup import covers them."""
    output_dir = tmp_path / "bristlenose-output"
    events_file = events_path(output_dir)
    run_id = new_run_id()
    append_event(events_file, _started(run_id))
    append_event(events_file, _completed(run_id))

    calls: list[None] = []

    async def cb() -> None:
        calls.append(None)

    task = asyncio.create_task(
        run_event_watcher(events_file, cb, poll_interval=0.05),
    )
    try:
        await asyncio.sleep(0.25)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert calls == []


@pytest.mark.asyncio
async def test_ignores_run_failed(tmp_path: Path) -> None:
    """Only run_completed triggers re-import; failures have nothing new to import."""
    output_dir = tmp_path / "bristlenose-output"
    events_file = events_path(output_dir)
    calls: list[None] = []

    async def cb() -> None:
        calls.append(None)

    task = asyncio.create_task(
        run_event_watcher(events_file, cb, poll_interval=0.05),
    )
    try:
        await asyncio.sleep(0.1)
        run_id = new_run_id()
        append_event(events_file, _started(run_id))
        append_event(events_file, _failed(run_id))
        await asyncio.sleep(0.25)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert calls == []


@pytest.mark.asyncio
async def test_callback_failure_does_not_kill_watcher(tmp_path: Path) -> None:
    """A transient import failure shouldn't blind us to the next run."""
    output_dir = tmp_path / "bristlenose-output"
    events_file = events_path(output_dir)
    calls: list[int] = []

    async def cb() -> None:
        calls.append(len(calls))
        if len(calls) == 1:
            raise RuntimeError("first call fails")

    task = asyncio.create_task(
        run_event_watcher(events_file, cb, poll_interval=0.05),
    )
    try:
        await asyncio.sleep(0.1)
        rid1 = new_run_id()
        append_event(events_file, _started(rid1))
        append_event(events_file, _completed(rid1))
        await asyncio.sleep(0.25)
        rid2 = new_run_id()
        append_event(events_file, _started(rid2))
        append_event(events_file, _completed(rid2))
        await asyncio.sleep(0.25)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert len(calls) == 2


@pytest.mark.asyncio
async def test_handles_missing_events_file(tmp_path: Path) -> None:
    """Project that has never run a pipeline yet — file appears later."""
    output_dir = tmp_path / "bristlenose-output"
    events_file = events_path(output_dir)
    calls: list[None] = []

    async def cb() -> None:
        calls.append(None)

    task = asyncio.create_task(
        run_event_watcher(events_file, cb, poll_interval=0.05),
    )
    try:
        await asyncio.sleep(0.15)  # file does not exist yet
        run_id = new_run_id()
        append_event(events_file, _started(run_id))
        append_event(events_file, _completed(run_id))
        await asyncio.sleep(0.25)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert len(calls) == 1
