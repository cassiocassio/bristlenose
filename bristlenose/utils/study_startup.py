"""Conservative, read-only admission evidence for an ordinary study startup.

Not a distributed lock or a promise about an already-open study. This only
classifies locally visible unfinished activity; it never repairs the evidence.
Ordinary entry points must call require_study_startup before study writers.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from bristlenose.events import _parse_event_line, events_path
from bristlenose.run_condition import RunStateEnum, read_condition, reduce_lines
from bristlenose.run_lifecycle import _read_pid_file, pid_file_path
from bristlenose.utils.machine_identity import has_unsafe_display_character, machine_id
from bristlenose.utils.output_backup import SetAside, set_aside_owner

# Native must distinguish a refusal even when pipe output has not drained.
STUDY_STARTUP_REFUSAL_EXIT_CODE = 75


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
            if marker_present or nonempty_history:
                return unknown
            # A report set aside and no run named since: the owner note says
            # whose (`set_aside_owner`). This Mac's, live or dead, is the
            # ordinary flow: a run still starting, or one the reclaim after
            # this puts back. Refusing it locked a study for good (9 Nov 2026).
            set_aside = set_aside_owner(output_dir)
            if set_aside is SetAside.FOREIGN:
                return StartupRefusal.FOREIGN_UNFINISHED
            return unknown if set_aside is SetAside.UNPROVEN else None
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


class StudyStartupRefusedError(RuntimeError):
    """Startup refusal, distinct from a failed analysis or a dead local run."""

    def __init__(self, reason: StartupRefusal, *, machine_name: str | None = None, started_at: str | None = None):
        self.reason = reason
        self.machine_name = machine_name
        self.started_at = started_at
        sentence = (
            "Analysis started on another Mac."
            if reason is StartupRefusal.FOREIGN_UNFINISHED
            else "An unfinished analysis was found, but the Mac that started it could not be verified."
        )
        super().__init__(sentence + " This study cannot be viewed or edited here.")


def require_study_startup(output_dir: Path) -> None:
    """Refuse before writable startup; never append failure to a foreign run."""
    reason = startup_refusal(output_dir)
    if reason is not None:
        name: str | None = None
        started: str | None = None
        if reason is StartupRefusal.FOREIGN_UNFINISHED:
            # Diagnostic metadata only: missing/stale detail cannot change the
            # refusal. Pair the name and time with the same observed attempt.
            try:
                marker = _read_pid_file(output_dir)
                latest = read_condition(output_dir, liveness=lambda _: False).latest
                if marker and latest and marker.get("run_id") == latest.run_id:
                    candidate = marker.get("machine_name")
                    if (isinstance(candidate, str) and 0 < len(candidate) <= 256
                            and not has_unsafe_display_character(candidate)):
                        name = candidate
                    if latest.started_at is not None and len(latest.started_at) <= 64:
                        started = latest.started_at
            except (OSError, UnicodeError, ValueError):
                pass  # Preserve refusal; diagnostic metadata is optional.
        raise StudyStartupRefusedError(reason, machine_name=name, started_at=started)
