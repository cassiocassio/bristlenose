"""Preflight checks run before pipeline stages to surface fetchable dependencies upfront.

Each submodule owns one preflight (Whisper model, ffmpeg, API key). Per the
"front-load all decisions" architectural principle (see ``docs/design-cli-just-works.md``),
all preflights run as a single block after ingest, before stage 2.
"""


class PreflightAbortedError(RuntimeError):
    """A preflight check decided the pipeline cannot proceed.

    Carries the recovery message to surface to the user. Used by all three
    preflights — whisper (``--no-fetch`` + missing model), ffmpeg (missing
    binary, auto-install declined or unavailable), and api_key (invalid key,
    billing-empty, etc.). The CLI catches this once at the pipeline-run call
    site and exits 2.
    """
