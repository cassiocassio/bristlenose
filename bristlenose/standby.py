"""A standby ``serve``: boot and import now, learn which study later.

The Mac app starts one of these shortly after launch so that opening a study does not pay for the
interpreter and the imports, which do not depend on the study (docs/design-standby-sidecar.md).
It waits on stdin for one claim line, then ``serve`` carries on exactly as if it had been started
with the study's path.

Before the claim it must do nothing a cold start would do for a study: no port, no token, no file.
It keeps default signal handling on purpose: ``install_exit_logger`` swallows SIGTERM when it is
installed before uvicorn, and a waiting process that ignores SIGTERM cannot be stopped. It ends on
SIGTERM, SIGINT or stdin closing (the app quitting).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from bristlenose import startup_trace

CLAIM_VERSION = 1
READY_LINE = "[bristlenose] standby-ready"


def _refuse_claim() -> None:
    # A fixed line: the claim holds a token, so it is never echoed.
    print("[bristlenose] standby: the claim could not be read", file=sys.stderr, flush=True)
    raise SystemExit(2)


def parse_claim(line: str) -> tuple[Path, str]:
    """The study path and MCP token a claim line carries; a bad claim ends the process."""
    try:
        claim = json.loads(line)
    except ValueError:
        _refuse_claim()
    if not isinstance(claim, dict) or claim.get("v") != CLAIM_VERSION:
        _refuse_claim()
    project, token = claim.get("project"), claim.get("mcp_token", "")
    if not isinstance(project, str) or not project or not isinstance(token, str):
        _refuse_claim()
    return Path(project), token


def await_claim() -> Path:
    """Warm the imports, announce readiness, and wait for the study. Exits 0 if stdin closes."""
    # The two modules `serve` imports after it knows the study: the cost this exists to pay early.
    import uvicorn  # noqa: F401

    import bristlenose.server.app  # noqa: F401

    print(READY_LINE, flush=True)
    startup_trace.mark("standby-ready")
    try:
        line = sys.stdin.readline()
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    if not line.strip():
        raise SystemExit(0)  # the app closed the pipe: nobody is coming
    project, token = parse_claim(line)
    if token:
        os.environ["_BRISTLENOSE_MCP_TOKEN"] = token
    startup_trace.mark("claim-received")
    return project
