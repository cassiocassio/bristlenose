"""Bristlenose: User-research transcription and quote extraction engine.

Copyright (C) 2025-2026 Martin Storey <martin@cassiocassio.co.uk>
SPDX-License-Identifier: AGPL-3.0-only
"""

# Suppress tqdm / huggingface_hub progress bars at the earliest point the
# bristlenose package is imported. Both env vars must be set BEFORE the
# corresponding library is first imported:
#
# - `huggingface_hub.constants` captures HF_HUB_DISABLE_PROGRESS_BARS into a
#   module-level constant at import time. Once frozen, env-var changes have
#   no effect.
# - `tqdm.std.tqdm.__init__` uses `@envwrap("TQDM_", ...)` which reads
#   TQDM_DISABLE at each instantiation; explicit `disable=` kwargs still win,
#   but the env var catches the "left as default" cases.
#
# Setting these in `bristlenose/pipeline.py` was too late: the doctor
# preflight (`bristlenose.doctor._check_whisper_model`) imports
# `huggingface_hub` before pipeline.py loads, freezing
# HF_HUB_DISABLE_PROGRESS_BARS as None. That allowed `Fetching N files:` and
# `Download complete: : 0.00B` from `snapshot_download` to leak past
# suppression (BUG hit 12 May 2026, A4 happy-path run).
#
# Defence-in-depth: callers that touch huggingface_hub (s05_transcribe,
# preflight/whisper) also call `disable_progress_bars()` programmatically
# right before the HF call. Either suppression alone is sufficient; both
# protect against dep updates that introduce a new env-var bypass.
#
# See `docs/design-pipeline-resilience.md` ("Progress Bar Dead Ends").
import os as _os

_os.environ.setdefault("TQDM_DISABLE", "1")
_os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
del _os

# Drop mimetypes.knownfiles before any submodule loads. CPython's mimetypes
# lazy-init walks /etc/mime.types and friends; under macOS App Sandbox those
# reads raise PermissionError, which init() doesn't catch — mimetypes._db
# stays poisoned and every subsequent guess_type() raises. Note: passing
# files=[] to init() does NOT skip the walk in Python 3.12+ — line 378 of
# CPython's mimetypes.py does `files = knownfiles + list(files)`, so init([])
# still reads the system list. The reliable escape hatch is to empty
# knownfiles before any init (lazy or explicit) fires. We then pre-register
# the extensions the React bundle actually serves so we never depend on
# platform defaults.
import mimetypes as _mimetypes  # noqa: E402

_mimetypes.knownfiles = []
_mimetypes.add_type("application/javascript", ".js")
_mimetypes.add_type("text/css", ".css")
_mimetypes.add_type("text/html", ".html")
_mimetypes.add_type("application/json", ".json")
_mimetypes.add_type("image/svg+xml", ".svg")
_mimetypes.add_type("font/woff2", ".woff2")
del _mimetypes

# Make bundled ffmpeg/ffprobe reachable to subpackages that shell out via
# bare-name argv (e.g. mlx_whisper.audio.load_audio runs
# `subprocess.run(["ffmpeg", …])`). Under macOS App Sandbox the inherited
# PATH doesn't include Homebrew, so the bare lookup fails with ENOENT.
# Prepending the bundled directory is a one-line fix that covers every
# transitive shell-out without monkey-patching each upstream caller.
# No-op outside the bundle (CLI / pip / Homebrew installs).
from bristlenose.utils.bundled_binary import prepend_bundled_to_path as _prepend  # noqa: E402

_prepend()
del _prepend

__version__ = "0.15.19"
