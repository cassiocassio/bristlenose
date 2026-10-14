"""Screen text: what was on the participant's shared screen, read by OCR, and the screens they visited.

Plan and evidence: ``docs/design-screens.md`` (the plan), ``docs/design-screen-text-search.md`` and
``docs/design-screens-lens.md`` (the measurements), ``experiments/screen-text/`` (the spikes this
package was ported from).

Three layers, each usable without the next:

- ``engine`` — the OCR seam. One protocol, a Vision engine for macOS and a fake for tests. Nothing
  above the seam knows which engine read a frame.
- ``index`` — one recording in, a screen-text index out: lines with boxes and the runs of time
  they were on screen, chrome flagged, moments where the screen changed.
- ``screens`` — indexes and quotes in, screens out: which page each moment was, which pages are
  one screen across sessions, which quotes were said on each, and which on-screen line a quote is
  about.

Runs in serve, in the background, after the report is readable (``server/screen_text_job.py``),
never on the pipeline's path. Switched on by ``BRISTLENOSE_SCREEN_TEXT=1``, which the Mac app sets
unless the researcher turns "Read shared screens" off, and by ``serve --dev``. Unset — the CLI's
default — it does not run. The Mac app says ``0`` when the researcher has turned it off, and that is
the one value that deletes: serve starts by deleting what was read for the project
(``index.delete_at_rest``), and ``--dev`` does not turn it back on.

Privacy (``docs/design-screens.md`` §4): everything stays in the project's ``.bristlenose/``; never
in an export, never sent to an LLM, never through MCP or the chat lens. At rest the index keeps no
query strings, no fragments but an app's routes (``address.minimise``), and no chrome.
"""

from __future__ import annotations

import os
from typing import Literal

#: Bump when anything changes what an index holds: it is in every index's cache key.
INDEX_VERSION = 3

# Why something cannot be read, as a case, never a sentence: the SPA and the Mac app say it in the
# researcher's language, and the raw detail (an exception, ffmpeg's stderr) goes to the log only.

#: Why the engine cannot run on this machine (``ScreenTextEngine.available()``).
EngineUnavailable = Literal["not_macos", "vision_missing"]
#: Why the screens routes cannot read anything: the engine's reason, or serve has no job at all.
Unavailable = Literal["not_macos", "vision_missing", "no_job"]
#: Why one recording has no index. ``not_read`` is the only one that is not a failure: the job is
#: idle and did not read it (a run started mid-pass, or it never got that far), and the next pass
#: will — after a run, or when serve restarts.
ReadFailure = Literal["unreadable", "cloud_downloading", "ffprobe_failed", "read_failed", "not_read"]


def enabled() -> bool:
    """Whether serve was asked to read screens: ``BRISTLENOSE_SCREEN_TEXT=1``."""
    return os.environ.get("BRISTLENOSE_SCREEN_TEXT", "0") == "1"


def explicitly_off() -> bool:
    """Whether the researcher turned reading screens off: ``BRISTLENOSE_SCREEN_TEXT`` is exactly
    ``0``. Unset is not off in this sense — it is the CLI's default — and deletes nothing."""
    return os.environ.get("BRISTLENOSE_SCREEN_TEXT") == "0"


def wanted(dev: bool) -> bool:
    """Whether serve reads screens: asked for, or ``serve --dev``; never when explicitly off, which
    is the researcher's decision and outranks a developer flag."""
    return not explicitly_off() and (enabled() or dev)
