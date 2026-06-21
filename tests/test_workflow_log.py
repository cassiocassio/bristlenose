"""Tests for the workflow-skill logger (.claude/skills/_shared/wflog.sh).

The logger is instrumentation shared by the bookend workflow skills. It must:
- append exactly one valid JSON line per call,
- carry skill / step / detail / ts / branch fields,
- JSON-escape arbitrary detail (quotes, backslashes, unicode),
- honour BRISTLENOSE_WORKFLOW_LOG and BRISTLENOSE_WORKFLOW_DEBUG,
- never fail the calling skill (always exit 0), even with no args.

Environment-independent: points the log at a tmp file, tolerates missing git.
"""

import json
import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "_shared" / "wflog.sh"


def run(args, log_path, debug=False):
    env = dict(os.environ)
    env["BRISTLENOSE_WORKFLOW_LOG"] = str(log_path)
    if debug:
        env["BRISTLENOSE_WORKFLOW_DEBUG"] = "1"
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
    )


def test_script_exists():
    assert SCRIPT.exists(), f"logger not found at {SCRIPT}"


def test_appends_valid_json_line(tmp_path):
    log = tmp_path / "wf.jsonl"
    result = run(["new-feature", "start", "hello world"], log)
    assert result.returncode == 0
    lines = log.read_text().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["skill"] == "new-feature"
    assert rec["step"] == "start"
    assert rec["detail"] == "hello world"
    assert "ts" in rec
    assert "branch" in rec


def test_appends_not_overwrites(tmp_path):
    log = tmp_path / "wf.jsonl"
    run(["close-feature", "start"], log)
    run(["close-feature", "done"], log)
    lines = log.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[1])["step"] == "done"


def test_detail_with_special_chars_is_escaped(tmp_path):
    log = tmp_path / "wf.jsonl"
    nasty = 'has "quotes" and \\ backslash and 日本語'
    run(["new-release", "version", nasty], log)
    rec = json.loads(log.read_text().splitlines()[0])  # must parse cleanly
    assert rec["detail"] == nasty


def test_debug_mode_echoes_to_stderr(tmp_path):
    log = tmp_path / "wf.jsonl"
    result = run(["new-feature", "ready"], log, debug=True)
    # Assert the invariant (debug emits skill + step to stderr), not the exact format.
    assert "new-feature" in result.stderr
    assert "ready" in result.stderr


def test_non_debug_is_quiet(tmp_path):
    log = tmp_path / "wf.jsonl"
    result = run(["new-feature", "ready"], log)
    assert result.stderr.strip() == ""


def test_never_fails_with_missing_args(tmp_path):
    log = tmp_path / "wf.jsonl"
    result = run([], log)
    assert result.returncode == 0  # must never crash the calling skill
    rec = json.loads(log.read_text().splitlines()[0])
    assert rec["skill"] == "?"
    assert rec["step"] == "?"


def test_creates_parent_dir(tmp_path):
    log = tmp_path / "nested" / "dir" / "wf.jsonl"
    result = run(["s", "step"], log)
    assert result.returncode == 0
    assert log.exists()
