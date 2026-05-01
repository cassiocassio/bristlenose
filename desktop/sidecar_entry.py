"""Entry point for the bundled sidecar.

The bundled binary accepts three subcommands:

- (default) — implicit `serve`. Args without a recognised first token are
  rewritten to `serve <args...>`. This is what the Swift host invokes for
  every project workspace.
- `doctor` — read-only diagnostic. Used by `desktop/scripts/build-all.sh`
  to verify bundle integrity at build time (BUG-3/4/5 class: runtime data
  files in source but missing from the PyInstaller bundle). Safe to
  expose because it doesn't write outside `<output_dir>/.bristlenose/`
  and doesn't reach the network.
- `run` — full pipeline execution (transcription, LLM calls, FFmpeg,
  file I/O on a user-supplied directory). State-changing and network-
  egressing, so it is **host-gated** on the `_BRISTLENOSE_HOSTED_BY_DESKTOP=1`
  env var that the Swift host sets when it spawns this binary. Third-
  party callers (anything else on the user's account that finds the
  signed binary in the `.app` bundle) don't set it; the host does.
  Confused-deputy mitigation: pre-A1c sandbox flip the bundled binary is
  exec'able by anything on the user's account, so the env-var handshake
  is the only access control between merge and A1c. After A1c, sandbox
  enforces caller-inherits-sandbox semantics and the gate becomes
  belt-and-braces.

Keep `_PASSTHROUGH_COMMANDS` narrow — every entry expands the binary's
surface area.
"""

# TODO(shape-b): remove "run" passthrough when PipelineRunner moves to the
# serve HTTP API. Single process per project, no second subprocess to gate.
# See docs/private/plan-pipeline-runner-sidecar-mode.md "Architectural
# decision — Shape B" for the rationale.

from __future__ import annotations

import os
import sys

from bristlenose.cli import app

# Subcommands the bundled sidecar accepts (other than the implicit "serve").
# Keep this list narrow — every entry expands the binary's surface area.
_PASSTHROUGH_COMMANDS = {"doctor", "run"}

# Subcommands that are state-changing or network-egressing and therefore
# require the host-gate env var. `doctor` is read-only and ungated.
_HOST_GATED_COMMANDS = {"run"}


def main() -> None:
    # Inject "serve" unless the caller explicitly invoked an allowed
    # passthrough subcommand. Any unknown / disallowed first arg falls
    # through to "serve" injection so Swift's typical invocation
    # (--port X --no-open <path>) keeps working.
    if len(sys.argv) >= 2 and sys.argv[1] in _PASSTHROUGH_COMMANDS:
        if sys.argv[1] in _HOST_GATED_COMMANDS:
            if os.environ.get("_BRISTLENOSE_HOSTED_BY_DESKTOP") != "1":
                sys.stderr.write(
                    f"bristlenose-sidecar: '{sys.argv[1]}' is desktop-host-only. "
                    "Use the PyPI/Homebrew CLI for command-line pipeline runs.\n"
                )
                sys.exit(2)
        # passthrough — let Typer handle the full subcommand
    elif len(sys.argv) < 2 or sys.argv[1].startswith("-"):
        sys.argv = [sys.argv[0], "serve", *sys.argv[1:]]
    elif sys.argv[1] != "serve":
        sys.argv = [sys.argv[0], "serve", *sys.argv[1:]]
    app()


if __name__ == "__main__":
    main()
