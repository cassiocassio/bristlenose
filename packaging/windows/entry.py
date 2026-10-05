"""Entry point for the frozen Windows build of the Bristlenose CLI.

Unlike the Mac sidecar's entry (desktop/sidecar_entry.py), this is the whole
CLI: no rewrite of a bare call to `serve`, no host gate on `run`.
"""

import multiprocessing


def main() -> None:
    # A dependency's worker processes re-execute the frozen binary; without this
    # they fall through to the CLI and die on interpreter flags (the Mac sidecar
    # learned this the hard way, desktop/CLAUDE.md "freeze_support").
    multiprocessing.freeze_support()

    from bristlenose.cli import app

    app()


if __name__ == "__main__":
    main()
