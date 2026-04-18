"""Entry point for the bundled sidecar: start `bristlenose serve`.

Scoped to serve mode per Track C C1. Arguments are forwarded to the
underlying Typer app so the Swift shell can pass `--port`, `--host`,
`--auth-token`, etc. directly.
"""

from __future__ import annotations

import sys

from bristlenose.cli import app


def main() -> None:
    # Inject "serve" as argv[1] if the caller didn't supply a subcommand.
    # This makes the binary single-purpose: it runs `bristlenose serve`
    # regardless of how Swift invokes it.
    if len(sys.argv) < 2 or sys.argv[1].startswith("-"):
        sys.argv = [sys.argv[0], "serve", *sys.argv[1:]]
    elif sys.argv[1] != "serve":
        sys.argv = [sys.argv[0], "serve", *sys.argv[1:]]
    app()


if __name__ == "__main__":
    main()
