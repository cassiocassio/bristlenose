"""The one place the serve port is written down.

Python reads it from here (``cli.py``, ``server/app.py``). Files that cannot
import Python carry a copy — vite proxy, e2e config, the Settings table,
``.claude/launch.json``, the Xcode "External Server" scheme — and
``tests/test_default_port.py`` fails if any of them drifts from this value.

8484: a pair that halves (8-4-8-4), unassigned by IANA, and clear of the
8080/8888 crowd.
"""

DEFAULT_SERVE_PORT = 8484

# ``_find_open_port`` tries this many consecutive ports from the default.
PORT_SCAN_ATTEMPTS = 10
