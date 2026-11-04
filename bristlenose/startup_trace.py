"""Opt-in stage stamps for the serve start, so the time before ``Report:`` can be split.

``BRISTLENOSE_STARTUP_TRACE=1`` makes each mark print ``@startup-stage <name> <epoch_ms>`` on
stderr, which the Mac host already captures from the sidecar. Epoch milliseconds so a host
that stamped its own spawn time can line the two up. Off, a mark is one dict lookup and
prints nothing. Dependency-free on purpose: it is imported before anything heavy, to stamp
the point at which Python and the bundle loader have finished.
"""

from __future__ import annotations

import os
import sys
import time

_ON = os.environ.get("BRISTLENOSE_STARTUP_TRACE") == "1"


def mark(stage: str) -> None:
    if _ON:
        print(f"@startup-stage {stage} {time.time() * 1000:.0f}", file=sys.stderr, flush=True)
