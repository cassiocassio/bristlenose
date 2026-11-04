"""``BRISTLENOSE_STARTUP_TRACE=1`` stamps each serve-start stage on stderr; off, nothing."""

from __future__ import annotations

import os
import re
import subprocess
import sys


def _run(trace: str | None) -> str:
    env = {k: v for k, v in os.environ.items() if k != "BRISTLENOSE_STARTUP_TRACE"}
    if trace is not None:
        env["BRISTLENOSE_STARTUP_TRACE"] = trace
    code = "from bristlenose import startup_trace as t; t.mark('a'); t.mark('b')"
    return subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True).stderr


def test_on_prints_one_epoch_millisecond_stamp_per_mark() -> None:
    lines = _run("1").splitlines()
    assert [re.fullmatch(r"@startup-stage (a|b) \d{13}", line) is not None for line in lines] == [True, True]
    assert [line.split()[1] for line in lines] == ["a", "b"]


def test_off_prints_nothing() -> None:
    assert _run(None) == ""
    assert _run("0") == ""
