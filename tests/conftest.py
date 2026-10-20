"""Shared test fixtures for Bristlenose tests."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from hypothesis import settings as hypothesis_settings

# Bypass all preflight checks by default. The front-loaded preflight block
# in Pipeline.run (Whisper / ffmpeg / API-key) aborts on CI runners that
# lack one of those binaries, even for tests that don't exercise the
# preflight contract. The env var is the documented "explicit escape
# hatch" — see bristlenose/preflight/*.py. Tests that DO exercise a
# preflight directly (tests/test_preflight_*.py) opt back in with an
# autouse `monkeypatch.delenv` fixture in those files.
os.environ.setdefault("BRISTLENOSE_SKIP_PREFLIGHT", "1")

# The voice pass (stages/s05b_voice.py) runs whenever its runtime is installed,
# which it is in the dev venv and CI, and would fetch a 40 MB model on first
# use. Forced off here (not setdefault: a shell that exports it =true would
# otherwise turn every pipeline test into a real voice pass); tests of the pass
# opt back in with monkeypatch.setenv, with the model and audio faked.
os.environ["BRISTLENOSE_VOICE_PASS"] = "false"

from bristlenose.board_progress import default_history_dir as _real_board_history_dir
from bristlenose.config import _find_env_files as _real_find_env_files
from bristlenose.credentials import CredentialStore
from bristlenose.credentials import get_credential_store as _real_get_credential_store
from bristlenose.models import (
    ExtractedQuote,
    FileType,
    FullTranscript,
    InputFile,
    InputSession,
    QuoteType,
    SpeakerRole,
    TranscriptSegment,
)

# Hypothesis profiles (property-based tests; .claude/skills/property-based-testing/).
# `ci` is derandomised: under a random seed a property can kill a bug on one run
# and miss it on the next, which is a flake in CI. Measured 11 Oct 2026, two of
# eleven mutants were killed on two seeds out of three. Locally the default
# explores fresh examples each run. No deadline in either: shared runners are
# slow, and the Windows cells slower. Never register or load a profile inside a
# test module, which silently overrides this one.
hypothesis_settings.register_profile("ci", derandomize=True, deadline=None, max_examples=200)
hypothesis_settings.register_profile("dev", deadline=None, max_examples=200)
hypothesis_settings.load_profile("ci" if os.environ.get("CI") else "dev")

# serve answers only to a loopback Host (LoopbackHostMiddleware). A bare
# TestClient against create_app must pass this, not Starlette's "testserver".
LOOPBACK_BASE_URL = "http://127.0.0.1"


class AuthTestClient(TestClient):
    """TestClient that auto-injects the Bearer token from app.state.auth_token.

    All serve-mode test fixtures should use this instead of bare TestClient
    so the auth middleware passes requests through. Defaults ``base_url`` to
    loopback: serve refuses any other ``Host`` (the DNS-rebinding gate), and
    Starlette's default ``testserver`` is not loopback.
    """

    def __init__(self, app: FastAPI, **kwargs: Any) -> None:
        kwargs.setdefault("base_url", LOOPBACK_BASE_URL)
        super().__init__(app, **kwargs)
        token = getattr(app.state, "auth_token", None)
        if token:
            self.headers = httpx.Headers({"authorization": f"Bearer {token}"})


def iter_transcribe_from(fake: Any) -> Any:
    """Turn a ``transcribe_sessions``-shaped fake into the generator the
    pipeline consumes (``iter_transcribe_sessions``, one session at a time).

    ``fake(sessions, settings, **kw)`` returns ``(results, languages, outcome)``;
    each session it names comes back as a ``SessionTranscription``, failures
    matched to their session from ``outcome.failed``.
    """
    from bristlenose.stages.s05_transcribe import SessionTranscription

    def _iter(sessions: Any, settings: Any, **kw: Any) -> Any:
        results, languages, outcome = fake(sessions, settings, **kw)
        failures = {f.session_id: f for f in outcome.failed}
        for sid, segments in results.items():
            yield SessionTranscription(sid, segments, languages.get(sid), failures.get(sid))

    return _iter


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for test outputs."""
    return tmp_path


@pytest.fixture
def sample_session() -> InputSession:
    """Create a sample InputSession for testing."""
    return InputSession(
        session_id="s1",
        session_number=1,
        participant_id="p1",
        participant_number=1,
        files=[
            InputFile(
                path=Path("/tmp/interview_01.mp4"),
                file_type=FileType.VIDEO,
                created_at=datetime(2026, 1, 10, 10, 0, 0, tzinfo=timezone.utc),
                size_bytes=100_000_000,
                duration_seconds=2700.0,
            )
        ],
        session_date=datetime(2026, 1, 10, 10, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_segments() -> list[TranscriptSegment]:
    """Create sample transcript segments with mixed speaker roles."""
    return [
        TranscriptSegment(
            start_time=0.0,
            end_time=15.0,
            text="Hi, thanks for joining us today. I'm going to show you a few screens and I'd like you to tell me what you think.",
            speaker_label="Speaker A",
            speaker_role=SpeakerRole.RESEARCHER,
            source="whisper",
        ),
        TranscriptSegment(
            start_time=16.0,
            end_time=35.0,
            text="Yeah sure, um, so I've been using this kind of tool for about two years now, you know, and it's like, honestly a bit of a nightmare sometimes.",
            speaker_label="Speaker B",
            speaker_role=SpeakerRole.PARTICIPANT,
            source="whisper",
        ),
        TranscriptSegment(
            start_time=36.0,
            end_time=42.0,
            text="Can you tell me more about what makes it a nightmare?",
            speaker_label="Speaker A",
            speaker_role=SpeakerRole.RESEARCHER,
            source="whisper",
        ),
        TranscriptSegment(
            start_time=43.0,
            end_time=70.0,
            text="Well the thing is like, you know, every morning I have to open three different apps just to figure out what I'm supposed to be working on. It's ridiculous.",
            speaker_label="Speaker B",
            speaker_role=SpeakerRole.PARTICIPANT,
            source="whisper",
        ),
    ]


@pytest.fixture
def sample_transcript(sample_segments: list[TranscriptSegment]) -> FullTranscript:
    """Create a sample FullTranscript for testing."""
    return FullTranscript(
        session_id="s1",
        participant_id="p1",
        source_file="interview_01.mp4",
        session_date=datetime(2026, 1, 10, 10, 0, 0, tzinfo=timezone.utc),
        duration_seconds=70.0,
        segments=sample_segments,
    )


@pytest.fixture
def sample_quotes() -> list[ExtractedQuote]:
    """Create sample extracted quotes for testing."""
    return [
        ExtractedQuote(
            participant_id="p1",
            start_timecode=16.0,
            end_timecode=35.0,
            text="I\u2019ve been using this kind of tool for about two years now... and it\u2019s honestly a bit of a nightmare sometimes.",
            topic_label="General context",
            quote_type=QuoteType.GENERAL_CONTEXT,
        ),
        ExtractedQuote(
            participant_id="p1",
            start_timecode=43.0,
            end_timecode=70.0,
            text="Every morning I have to open three different apps just to figure out what I\u2019m supposed to be working on. It\u2019s ridiculous.",
            topic_label="Daily workflow",
            quote_type=QuoteType.GENERAL_CONTEXT,
            researcher_context="When asked about what makes it a nightmare",
        ),
    ]


_FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(autouse=True, scope="session")
def no_log_file_in_committed_fixtures():
    """Tests never write ``bristlenose.log`` into the committed fixture tree.

    ``create_app(project_dir=<smoke-test fixture>)`` calls ``setup_logging``,
    which opened a RotatingFileHandler on the ONE fixture log from every xdist
    worker at once. At 5 MB a worker rolls over by renaming the file, and
    Windows refuses that while other workers hold it open, so a later open
    raised PermissionError. The failure moved between tests from run to run
    (0.36.0's push CI, 8 Oct 2026: green at the strict run on the same
    commit, red on the push run). It also grew a 14 MB untracked log in the
    tree on every Mac. Terminal logging is unchanged, and so is the file log for any
    other directory, which ``test_logging.py`` covers in ``tmp_path``.

    Session-scoped because module-scoped fixtures build the app before any
    per-test fixture runs: at function scope the patch arrived too late and
    the fixture log was still written.
    """
    import bristlenose.logging as bn_logging

    real = bn_logging.setup_logging

    def setup_logging(*, output_dir=None, verbose=False):
        if output_dir is not None and _FIXTURES_ROOT in Path(output_dir).resolve().parents:
            output_dir = None
        real(output_dir=output_dir, verbose=verbose)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(bn_logging, "setup_logging", setup_logging)
        yield


@pytest.fixture
def which_is_shutil_which(monkeypatch):
    """For tests that choose what is installed by stubbing ``shutil.which``.

    On Windows ``safe_which`` does not call ``shutil.which`` (it walks absolute
    PATH entries itself, so a cwd ``ffmpeg.exe`` is never found), so those stubs
    stopped reaching it and the tests read the runner's own PATH instead:
    windows-latest has Chocolatey's ffmpeg, and 20 tests failed there, green on
    every Mac (0.36.0 strict CI, 8 Oct 2026). This sends ``safe_which`` down its
    ``shutil.which`` branch on every OS. The Windows resolver itself is tested
    in ``test_windows_cwd_binaries.py``, which must not use this fixture.
    """
    import types

    import bristlenose.utils.safe_which as sw

    monkeypatch.setattr(sw, "sys", types.SimpleNamespace(platform="test-not-win32"))


@pytest.fixture
def no_discussion_stage(monkeypatch):
    """For suites that drive the whole pipeline to test OTHER stages.

    The Discussion stage is on by default, so with mocked settings or a mocked
    LLM client it ran, failed inside, and logged a traceback while the suite
    stayed green — testing a broken optional stage by accident (silent-failure
    review, 3 Oct 2026). The stage has its own suites.
    """
    from unittest.mock import AsyncMock

    from bristlenose.pipeline import Pipeline

    monkeypatch.setattr(Pipeline, "_run_discussion", AsyncMock(return_value=None))



def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "machine_config: let this test reach the real .env files, user config dir "
        "and credential store (see no_local_llm_config)",
    )


class _InMemoryCredentialStore(CredentialStore):
    """A keychain that starts empty for every test and forgets afterwards."""

    def __init__(self) -> None:
        self._items: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._items.get(key)

    def set(self, key: str, value: str) -> None:
        self._items[key] = value

    def delete(self, key: str) -> None:
        self._items.pop(key, None)


def _rebind_everywhere(
    monkeypatch: pytest.MonkeyPatch, real: Callable[..., Any], fake: Callable[..., Any]
) -> None:
    """Replace ``real`` in every loaded module that holds it under its own name.

    ``from x import f`` binds a second reference at import time, and patching
    ``x.f`` leaves it pointing at the original. ``miro.py`` holds
    ``get_credential_store`` that way, and test modules hold ``_find_env_files``.
    A fake an outer (module-scoped) isolation installed is replaced too, so a
    module imported after it — still holding ``real`` — is not missed.

    Reads each module's ``__dict__`` rather than ``getattr``: some modules
    answer every name through ``__getattr__`` (``torch.classes`` returns a
    proxy that raises on any attribute read), and only names a module actually
    binds can hold the function.
    """
    import sys
    import types

    fake._bn_isolation_fake = True  # type: ignore[attr-defined]
    name = real.__name__
    for module in list(sys.modules.values()):
        held = getattr(module, "__dict__", {}).get(name)
        if held is real or (
            isinstance(held, types.FunctionType) and getattr(held, "_bn_isolation_fake", False)
        ):
            monkeypatch.setattr(module, name, fake)


def _isolate_machine_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """No test sees the configuration of the machine the suite runs on.

    Four routes reach ``load_settings()`` from outside a test: env vars, the
    repo's own ``.env`` (found both as the package directory's and by walking
    up from cwd), the user-level config ``.env`` where ``bristlenose
    configure``/``use`` store the current provider, and the keychain. Measured
    4 Oct 2026: 1376 tests in 69 files read both ``.env`` files and most of them
    queried the real Keychain. From the repo root the gitignored ``.env`` named
    the provider three tests expected; from a worktree the stored current
    provider leaked in instead (``'google' == 'anthropic'``). CI has neither.

    The ``.env`` files reach pydantic-settings through
    ``BristlenoseSettings.model_config["env_file"]``, computed ONCE at import,
    so it is pinned off here; ``_find_env_files`` keeps only ``.env`` files a
    test wrote under its own tmp dir, so discovery tests still discover. The
    credential store is an empty in-memory one, so a test may still
    ``configure`` a key and read it back. A test that patches either again
    wins, as monkeypatch's later patch always does.

    Applied per test by ``no_local_llm_config``; a module- or session-scoped
    fixture that builds settings runs BEFORE any per-test fixture, so it calls
    this itself through ``isolate_machine_config``.
    """
    from bristlenose.config import BristlenoseSettings

    monkeypatch.setitem(BristlenoseSettings.model_config, "env_file", None)

    tmp_root = tmp_path_factory.getbasetemp().resolve()

    def _tmp_env_files_only() -> list[Path]:
        return [p for p in _real_find_env_files() if p.resolve().is_relative_to(tmp_root)]

    _rebind_everywhere(monkeypatch, _real_find_env_files, _tmp_env_files_only)

    store = _InMemoryCredentialStore()
    _rebind_everywhere(monkeypatch, _real_get_credential_store, lambda: store)

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path_factory.mktemp("xdg-config")))
    # A Miro board build keeps its call rates in the real config folder; a test's go to its own.
    board_history = tmp_path_factory.mktemp("board-timing")
    _rebind_everywhere(monkeypatch, _real_board_history_dir, lambda: board_history)
    monkeypatch.delenv("SNAP_USER_COMMON", raising=False)
    monkeypatch.delenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", raising=False)
    for name, field in BristlenoseSettings.model_fields.items():
        if not (name.startswith(("llm_", "azure_")) or name.endswith("_api_key")):
            continue
        monkeypatch.delenv(f"BRISTLENOSE_{name.upper()}", raising=False)
        for alias in getattr(field.validation_alias, "choices", ()):
            monkeypatch.delenv(str(alias), raising=False)


@pytest.fixture(scope="session")
def isolate_machine_config(
    tmp_path_factory: pytest.TempPathFactory,
) -> Callable[[pytest.MonkeyPatch], None]:
    """``_isolate_machine_config`` for fixtures wider than a test, e.g. a
    module-scoped live serve: ``with pytest.MonkeyPatch.context() as mp:
    isolate_machine_config(mp)``."""
    return lambda mp: _isolate_machine_config(mp, tmp_path_factory)


@pytest.fixture(autouse=True)
def no_local_llm_config(
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> pytest.MonkeyPatch:
    """Every test runs under ``_isolate_machine_config``.

    Exempt: ``slow`` (the paid suite needs the real keys) and ``machine_config``.
    """
    if not (
        request.node.get_closest_marker("slow") or request.node.get_closest_marker("machine_config")
    ):
        _isolate_machine_config(monkeypatch, tmp_path_factory)
    return monkeypatch


# ---------------------------------------------------------------------------
# Pinning "this machine's clock" without time.tzset (which Windows lacks)
# ---------------------------------------------------------------------------


import datetime as _dt_mod  # noqa: E402


class _LondonRule(_dt_mod.tzinfo):
    """Europe/London by its rule — GMT, BST from the last Sunday of March to
    the last Sunday of October — so a time-zone test runs the same on every
    OS with no tz database. Wall-clock boundaries are approximate by an hour
    on the two change days, which no test here touches."""

    @staticmethod
    def _last_sunday(year: int, month: int):
        import datetime as _d

        d = _d.date(year, month, 31)
        return d - _d.timedelta(days=(d.weekday() + 1) % 7)

    def dst(self, dt):
        import datetime as _d

        if dt is None:
            return _d.timedelta(0)
        start = _d.datetime.combine(self._last_sunday(dt.year, 3), _d.time(1))
        end = _d.datetime.combine(self._last_sunday(dt.year, 10), _d.time(1))
        return _d.timedelta(hours=1) if start <= dt.replace(tzinfo=None) < end else _d.timedelta(0)

    def utcoffset(self, dt):
        return self.dst(dt)

    def tzname(self, dt):
        import datetime as _d

        return "BST" if self.dst(dt) != _d.timedelta(0) else "GMT"


@pytest.fixture
def pin_local_zone(monkeypatch: pytest.MonkeyPatch):
    """Set the zone ``utils.timecodes`` treats as this machine's clock."""
    import bristlenose.utils.timecodes as _tc

    def _pin(zone):
        monkeypatch.setattr(_tc, "_local_zone", zone)

    return _pin


@pytest.fixture
def london(pin_local_zone):
    pin_local_zone(_LondonRule())


@pytest.fixture(autouse=True)
def no_run_signal_handlers_left_behind():
    """A test that runs a CLI command leaves run_lifecycle's SIGINT/SIGTERM/SIGHUP
    handlers installed, as the CLI does for the life of its process. In pytest
    that outlives the test: a later real signal became a KeyboardInterrupt, its
    caught signal turned a later run's failure into a cancel, and a hung suite
    could not be ended with a plain kill (20 Oct 2026). Put the previous
    handlers back after every test."""
    yield
    from bristlenose.run_lifecycle import _prev_handlers, _restore_signal_handlers

    if _prev_handlers:
        _restore_signal_handlers()


@pytest.fixture(autouse=True)
def no_run_log_handlers_left_behind(request):
    """`run` calls ``setup_logging``, which puts a StreamHandler on the root
    logger bound to the ``sys.stderr`` of that moment. Under ``CliRunner`` that
    is the runner's capture stream, closed when ``invoke`` returns, and a CLI
    process keeps the handler for its life. In pytest the handler outlived the
    test: the next command to log a warning (``transcribe``/``analyze``, which
    do not call ``setup_logging``) wrote to the closed stream, and logging's
    "--- Logging error ---" traceback landed in that command's output
    (test_cli_give_up_banner.py failed after any ``run`` test, 20 Oct 2026).
    Remove and close the handlers a test's ``setup_logging`` added; pytest's
    own capture handlers are subclasses, so ``type(...) in`` leaves them be.

    ``setup_logging`` also removes pytest's handlers, so in a test that asked
    for ``caplog`` it is wrapped to take them off first and put them back
    after: caplog then sees what is logged after ``create_app``. Tests without
    caplog get ``setup_logging`` unwrapped (``test_logging.py`` counts the
    root handlers). And the root level ``setup_logging`` sets to DEBUG is put
    back."""
    import logging
    from logging.handlers import RotatingFileHandler

    import bristlenose.logging as bn_logging

    root = logging.getLogger()
    before = set(root.handlers)
    level_before = root.level
    with pytest.MonkeyPatch.context() as mp:
        if "caplog" in request.fixturenames:
            real = bn_logging.setup_logging

            def setup_logging(*args, **kwargs):
                pytest_handlers = [
                    h for h in root.handlers if type(h).__module__.startswith("_pytest")
                ]
                for h in pytest_handlers:
                    root.removeHandler(h)
                try:
                    real(*args, **kwargs)
                finally:
                    for h in pytest_handlers:
                        root.addHandler(h)

            mp.setattr(bn_logging, "setup_logging", setup_logging)
        yield
    root.setLevel(level_before)
    for handler in root.handlers[:]:
        if handler not in before and type(handler) in (logging.StreamHandler, RotatingFileHandler):
            root.removeHandler(handler)
            handler.close()


@pytest.fixture(autouse=True)
def no_scene_strip_thread(monkeypatch):
    """serve's scene-strip job (server/scene_strips.py) starts a thread from the app lifespan and
    after every run_completed. On the shared in-memory connection that thread's session close is
    the documented rollback flake (server/CLAUDE.md), so it is off for every test;
    tests/test_serve_scene_strips.py opts back in."""
    monkeypatch.setenv("BRISTLENOSE_SCENE_STRIPS", "0")
