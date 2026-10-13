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
when the Diagnostics preference is on, and by ``serve --dev``. Rough and diagnostics-only for now.

Privacy (``docs/design-screens.md`` §4): everything stays in the project's ``.bristlenose/``; never
in an export, never sent to an LLM, never through MCP or the chat lens.
"""

from __future__ import annotations

import os

#: Bump when anything changes what an index holds: it is in every index's cache key.
INDEX_VERSION = 1


def enabled() -> bool:
    """Whether serve should read screens at all. Off unless asked for."""
    return os.environ.get("BRISTLENOSE_SCREEN_TEXT", "0") == "1"
