"""Bristlenose: User-research transcription and quote extraction engine.

Copyright (C) 2025-2026 Martin Storey <martin@cassiocassio.co.uk>
SPDX-License-Identifier: AGPL-3.0-only
"""

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
import mimetypes as _mimetypes

_mimetypes.knownfiles = []
_mimetypes.add_type("application/javascript", ".js")
_mimetypes.add_type("text/css", ".css")
_mimetypes.add_type("text/html", ".html")
_mimetypes.add_type("application/json", ".json")
_mimetypes.add_type("image/svg+xml", ".svg")
_mimetypes.add_type("font/woff2", ".woff2")
del _mimetypes

__version__ = "0.15.3"
