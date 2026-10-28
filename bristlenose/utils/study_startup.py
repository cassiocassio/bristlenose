"""Conservative, read-only admission evidence for an ordinary study startup.

Not a distributed lock or a promise about an already-open study. This only
classifies locally visible unfinished activity; it never repairs the evidence.
Production entry-point wiring awaits the startup-refusal UX review.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from bristlenose.events import _parse_event_line, events_path
from bristlenose.run_condition import RunStateEnum, reduce_lines
from bristlenose.run_lifecycle import _read_pid_file, pid_file_path
from bristlenose.utils.machine_identity import machine_id
from bristlenose.utils.output_backup import backup_path_for


class StartupRefusal(str, Enum):
    FOREIGN_UNFINISHED = "foreign_unfinished"
    UNVERIFIED_UNFINISHED = "unverified_unfinished"


def startup_refusal(output_dir: Path) -> StartupRefusal | None:
    """Return the reason to refuse, or None for the existing ordinary flow.

    Completed/failed/cancelled attempts need no machine ownership: they are no
    longer unfinished. A leftover marker must still identify that attempt.
    Only a matching local marker permits ordinary unfinished-run handling;
    process-table liveness is deliberately irrelevant to machine ownership.
    """
    unknown = StartupRefusal.UNVERIFIED_UNFINISHED
    try:
        marker_path = pid_file_path(output_dir)
        if marker_path.is_symlink():
            return unknown
        try:
            marker_path.stat()
            marker_present = True
        except FileNotFoundError:
            marker_present = False
        marker = _read_pid_file(output_dir) if marker_present else None
        # Do not use this machine's process table to classify foreign activity.
        try:
            raw_history = events_path(output_dir).read_bytes()
        except FileNotFoundError:
            raw_history = b""
        if raw_history and (not raw_history.endswith(b"\n") or b"\0" in raw_history):
            return unknown
        lines = raw_history.decode("utf-8").splitlines()
        # Display reducers deliberately tolerate torn telemetry; admitting
        # writers cannot use an older completion behind damaged new evidence.
        if any(line.strip() and _parse_event_line(line) is None for line in lines):
            return unknown
        condition = reduce_lines(lines, liveness=lambda _: False)
        if not condition.decodable:
            return unknown
        latest = condition.latest
        if latest is None:
            # Empty/new folders are normal. Nonempty but uninterpretable
            # history or an orphan marker is not evidence of a clean study.
            nonempty_history = bool(raw_history.strip())
            try:
                backup_path_for(output_dir).stat()
                backup_present = True
            except FileNotFoundError:
                backup_present = False
            return unknown if marker_present or nonempty_history or backup_present else None
        if marker_present and (marker is None or marker.get("run_id") != latest.run_id):
            return unknown
        if latest.state not in {RunStateEnum.IN_PROGRESS, RunStateEnum.STRANDED}:
            return None
        if (
            marker is None
            or type(marker.get("pid")) is not int
            or marker["pid"] <= 0
            or not isinstance(marker.get("start_time"), str)
            or not marker["start_time"].strip()
        ):
            return unknown
        local = machine_id()
        owner = marker.get("machine_id")
        if not local or not isinstance(owner, str) or not owner:
            return unknown
        if owner != local:
            return StartupRefusal.FOREIGN_UNFINISHED
        return None
    except (OSError, UnicodeError, ValueError):
        return unknown
