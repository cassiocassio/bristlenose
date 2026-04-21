"""Entry point for the bundled sidecar: start `bristlenose serve`.

Primarily scoped to serve mode per Track C C1. Arguments are forwarded to
the underlying Typer app so the Swift shell can pass `--port`, `--host`,
`--auth-token`, etc. directly.

**`doctor` passthrough (P2 from c3-bundle-completeness, 21 Apr 2026):**
the sidecar also accepts `doctor` and `doctor --self-test` so that
desktop/scripts/build-all.sh can verify bundle integrity at build time
(step 7a, after build-sidecar.sh, before archive). This catches the
BUG-3/4/5 class — runtime data files in source but missing from the
PyInstaller bundle. Doctor is a read-only diagnostic; safe to expose.
"""

from __future__ import annotations

import sys

from bristlenose.cli import app

# Subcommands the bundled sidecar accepts (other than the implicit "serve").
# Keep this list narrow — every entry expands the binary's surface area.
_PASSTHROUGH_COMMANDS = {"doctor"}


def main() -> None:
    # Inject "serve" unless the caller explicitly invoked an allowed
    # passthrough subcommand. Any unknown / disallowed first arg falls
    # through to "serve" injection so Swift's typical invocation
    # (--port X --no-open <path>) keeps working.
    if len(sys.argv) >= 2 and sys.argv[1] in _PASSTHROUGH_COMMANDS:
        pass  # passthrough — let Typer handle the full subcommand
    elif len(sys.argv) < 2 or sys.argv[1].startswith("-"):
        sys.argv = [sys.argv[0], "serve", *sys.argv[1:]]
    elif sys.argv[1] != "serve":
        sys.argv = [sys.argv[0], "serve", *sys.argv[1:]]
    app()


if __name__ == "__main__":
    main()
