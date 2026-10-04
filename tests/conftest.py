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
