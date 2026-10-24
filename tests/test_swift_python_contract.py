"""Cross-language contracts between the Swift desktop host and the Python sidecar.

Some invariants live on *both* sides of the Swift/Python boundary and are kept
in sync only by a hand-maintained constant plus a "grep this if it changes"
comment. Those are exactly the contracts where divergence is silent and
expensive: a wrong default here means the host injects the wrong provider's API
key into the sidecar environment, producing a provider/endpoint mismatch 404 at
the first LLM call (the overnight Ikea-run failure mode, 8 Jun 2026).

Why a *Python* test reads *Swift* source: the contract's authoritative side is
Python (`config.py` owns the real default), and the pytest suite is the only one
that runs in CI today — there is no `desktop-build` Swift-test job yet. Reading
the tracked Swift source as text (no build, no simulator, no `.app`) is the
parsimonious channel that actually fires on every push. If/when Swift tests run
in CI, this can move to a `@Test` that reads `config.py` instead.

See docs/design-test-philosophy.md § "Testing across the Swift/Python boundary".
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from bristlenose.config import BristlenoseSettings

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SHARED_SWIFT = (
    _REPO_ROOT / "desktop" / "Bristlenose" / "Bristlenose" / "BristlenoseShared.swift"
)

# Mirrors `static let pythonDefaultProvider = "anthropic"`. A rename or removal
# of the constant fails the match below — which is correct: the contract anchor
# moved, and the test should go red until both sides are reconciled.
_PYTHON_DEFAULT_PROVIDER_RE = re.compile(
    r'static\s+let\s+pythonDefaultProvider\s*=\s*"([^"]+)"'
)


def _swift_python_default_provider() -> str:
    text = _SHARED_SWIFT.read_text(encoding="utf-8")
    match = _PYTHON_DEFAULT_PROVIDER_RE.search(text)
    assert match is not None, (
        "BristlenoseShared.swift no longer declares "
        "`static let pythonDefaultProvider = \"...\"`. The Swift host mirrors "
        "Python's config.py llm_provider default to inject the matching API key "
        "when no provider is explicitly active; if the constant was renamed, "
        "update this test's regex AND confirm the value still matches the "
        "Python default."
    )
    return match.group(1)


class TestProviderDefaultContract:
    """`BristlenoseShared.pythonDefaultProvider` must equal Python's default.

    The Swift host has no way to read pydantic-settings; it hard-codes the
    Python default so `overlayAPIKeys` can fetch the right Keychain key for a
    defaulted run. If config.py's default ever changes and the Swift constant
    doesn't, a default-provider run injects the wrong key -> 404.
    """

    def test_swift_constant_matches_python_default(self) -> None:
        if not _SHARED_SWIFT.exists():
            pytest.skip(
                "desktop/ tree not present (sdist-only checkout); "
                "cross-language contract only checkable from a full repo checkout"
            )
        swift_value = _swift_python_default_provider()
        python_default = BristlenoseSettings.model_fields["llm_provider"].default
        assert swift_value == python_default, (
            f"Swift BristlenoseShared.pythonDefaultProvider = {swift_value!r} but "
            f"Python config.py llm_provider default = {python_default!r}. These "
            f"must match — the host injects BRISTLENOSE_<PROVIDER>_API_KEY for a "
            f"defaulted run using the Swift constant. Update "
            f"desktop/Bristlenose/Bristlenose/BristlenoseShared.swift "
            f"(pythonDefaultProvider) to {python_default!r}."
        )


# ---------------------------------------------------------------------------
# Keys kept in both keychains
# ---------------------------------------------------------------------------

_KEYCHAIN_HELPER_SWIFT = (
    _REPO_ROOT / "desktop" / "Bristlenose" / "Bristlenose" / "KeychainHelper.swift"
)

# Mirrors `static let sharedWithCLI: Set<String> = [ ... ]`.
_SHARED_WITH_CLI_RE = re.compile(
    r"static\s+let\s+sharedWithCLI\s*:\s*Set<String>\s*=\s*\[([^\]]*)\]", re.S
)


class TestSharedKeychainContract:
    """`KeychainHelper.sharedWithCLI` must equal the keys Python reads.

    The Mac app keeps a login-keychain copy of every key in that set so
    `bristlenose run` can read a key saved in the app (`docs/design-keychain.md`
    § "One keyspace, two keychains"). A key in Python's `SERVICE_NAMES` that the
    Swift set omits is written to the synced keychain alone — invisible to the
    CLI from the moment it is entered, with nothing red on either side. The
    Swift suite pins the same set from its side; this is the one that runs in CI.
    """

    def test_swift_shares_exactly_the_keys_python_reads(self) -> None:
        from bristlenose.credentials_macos import MacOSCredentialStore

        text = _KEYCHAIN_HELPER_SWIFT.read_text(encoding="utf-8")
        match = _SHARED_WITH_CLI_RE.search(text)
        assert match is not None, (
            "KeychainHelper.swift no longer declares "
            "`static let sharedWithCLI: Set<String> = [...]`; if the constant "
            "was renamed, update this regex AND confirm the set still matches "
            "MacOSCredentialStore.SERVICE_NAMES."
        )
        swift_keys = set(re.findall(r'"([^"]+)"', match.group(1)))
        assert swift_keys == set(MacOSCredentialStore.SERVICE_NAMES), (
            f"Swift shares {sorted(swift_keys)} with the CLI; Python reads "
            f"{sorted(MacOSCredentialStore.SERVICE_NAMES)}. A key on one side "
            "only is a key one tool cannot see."
        )


# Mirrors the `"key": "Service Name",` entries of `static let serviceNames`.
_SWIFT_SERVICE_NAMES_RE = re.compile(
    r"static\s+let\s+serviceNames\s*:\s*\[String:\s*String\]\s*=\s*\[(.*?)\n\s*\]", re.S
)
_SWIFT_NATIVE_ENV_RE = re.compile(r"let\s+nativeEnvNames\s*=\s*\[(.*?)\n\s*\]", re.S)
_SWIFT_PAIR_RE = re.compile(r'"([^"]+)"\s*:\s*"([^"]+)"')


def _swift_pairs(pattern: re.Pattern[str], what: str) -> dict[str, str]:
    text = _KEYCHAIN_HELPER_SWIFT.read_text(encoding="utf-8")
    match = pattern.search(text)
    assert match is not None, f"KeychainHelper.swift no longer declares {what}"
    return dict(_SWIFT_PAIR_RE.findall(match.group(1)))


class TestCredentialNamesContract:
    """`CREDENTIALS` is the one table of credential names, and Swift mirrors it.

    Swift cannot import Python, so `KeychainHelper.serviceNames` and
    `hasAnyAPIKey`'s `nativeEnvNames` are hand-written copies. These fail when
    a name changes on one side only — which turns "remember to update the
    mirror" into a red CI run.
    """

    def test_swift_service_names_match_the_registry(self) -> None:
        from bristlenose.providers import CREDENTIALS

        swift = _swift_pairs(_SWIFT_SERVICE_NAMES_RE, "`static let serviceNames`")
        for key, spec in CREDENTIALS.items():
            assert swift.get(key) == spec.keychain_service, (
                f"KeychainHelper.serviceNames[{key!r}] is {swift.get(key)!r}; "
                f"CREDENTIALS says {spec.keychain_service!r}"
            )

    def test_swift_native_env_names_match_the_registry(self) -> None:
        from bristlenose.providers import CREDENTIALS

        swift = _swift_pairs(_SWIFT_NATIVE_ENV_RE, "`nativeEnvNames` in hasAnyAPIKey")
        for key, env_var in swift.items():
            assert CREDENTIALS[key].env_var == env_var, (
                f"nativeEnvNames[{key!r}] is {env_var!r}; CREDENTIALS says "
                f"{CREDENTIALS[key].env_var!r}"
            )


# ---------------------------------------------------------------------------
# PII model pack — the Swift→Python handoff
# ---------------------------------------------------------------------------

_PII_PACK_SWIFT = (
    Path(__file__).resolve().parent.parent
    / "desktop" / "Bristlenose" / "Bristlenose" / "PIIModelPack.swift"
)


class TestPIIModelPackContract:
    """`PIIModelPack.swift` hands the sidecar a model directory. Two constants
    have to agree across the boundary, and both fail silently if they drift.

    The Swift suite covers the behaviour, but it is **ungated by CI** — a Swift
    regression can sit red on `main` indefinitely (see `desktop/CLAUDE.md`). So
    the drift gate lives here, in the suite that actually runs on every push,
    for the same reason the provider-default contract above does.
    """

    def test_the_env_var_name_matches_pythons(self) -> None:
        """A typo means the pack is acquired and then never found.

        Nothing raises: `resolve_spacy_model()` sees no override, returns the
        package name, and Presidio's engine builder shells out to `pip install`
        for a name it cannot resolve — a §2.5.2 violation inside a sandboxed App
        Store binary, reached by a spelling mistake.
        """
        from bristlenose.stages.s07_pii_removal import PII_MODEL_DIR_ENV

        assert _PII_PACK_SWIFT.exists(), f"{_PII_PACK_SWIFT} is gone"
        text = _PII_PACK_SWIFT.read_text(encoding="utf-8")
        assert f'"{PII_MODEL_DIR_ENV}"' in text, (
            f"Swift does not set {PII_MODEL_DIR_ENV}; the acquired pack would "
            f"never be found and redaction would silently fall back to the "
            f"package name"
        )

    def test_the_enabled_flag_maps_to_the_settings_field(self) -> None:
        """`env_prefix` is what makes the flag arrive — assert, don't assume."""
        from bristlenose.config import BristlenoseSettings

        text = _PII_PACK_SWIFT.read_text(encoding="utf-8")
        assert '"BRISTLENOSE_PII_ENABLED"' in text

        prefix = BristlenoseSettings.model_config["env_prefix"]
        assert "BRISTLENOSE_PII_ENABLED" == f"{prefix}PII_ENABLED".upper()
        assert "pii_enabled" in BristlenoseSettings.model_fields

    def test_the_liveness_pair_matches_pythons(self) -> None:
        """Both files, because spaCy reads meta.json *first*.

        If Swift checked only `config.cfg` it would hand over a half-unpacked
        directory that then dies inside spaCy with an opaque `E053`, which is
        the failure Python's own check was written to replace. The two lists
        must stay identical or the Swift side re-introduces it.
        """
        import re

        text = _PII_PACK_SWIFT.read_text(encoding="utf-8")
        match = re.search(r"requiredFiles\s*=\s*\[(.*?)\]", text, re.S)
        assert match, "requiredFiles is gone from PIIModelPack.swift"
        swift_files = re.findall(r'"([^"]+)"', match.group(1))

        # Python's pair, read from the source of truth rather than retyped.
        py_src = (
            Path(__file__).resolve().parent.parent
            / "bristlenose" / "stages" / "s07_pii_removal.py"
        ).read_text(encoding="utf-8")
        py_match = re.search(
            r'for f in \((.*?)\)\)', py_src, re.S
        )
        assert py_match, "the liveness pair moved in s07_pii_removal.py"
        py_files = re.findall(r'"([^"]+)"', py_match.group(1))

        assert swift_files == py_files, (
            f"Swift checks {swift_files}, Python checks {py_files} — a "
            f"directory one side calls loadable and the other does not"
        )


class TestProgressStageVocabularyContract:
    """`RunProgressSubtitle.knownStages` is a hand-maintained mirror of
    `timing.py PROGRESS_STAGES` (ALL_STAGES plus the first-run download). An id on the Python side that Swift lacks is
    silently dropped — the verb never renders and the sidebar shows the
    previous stage frozen — which is exactly how redaction shipped invisible
    until 12 Sep 2026. The Swift suite pins the literal set, but it is ungated
    by CI; this is the copy that runs on every push.
    """

    def test_swift_known_stages_equal_python_all_stages(self) -> None:
        import re

        from bristlenose.timing import PROGRESS_STAGES

        swift = (
            Path(__file__).resolve().parent.parent
            / "desktop" / "Bristlenose" / "Bristlenose" / "RunProgressSubtitle.swift"
        ).read_text(encoding="utf-8")
        m = re.search(r"knownStages: Set<String> = \[(.*?)\]", swift, re.S)
        assert m, "knownStages literal not found"
        swift_set = set(re.findall(r'"([^"]+)"', m.group(1)))
        assert swift_set == set(PROGRESS_STAGES), (
            f"Swift knows {sorted(swift_set)}, Python emits {sorted(PROGRESS_STAGES)} — "
            f"a stage in the difference renders no verb"
        )


_PIPELINE_RUNNER_SWIFT = (
    _REPO_ROOT / "desktop" / "Bristlenose" / "Bristlenose" / "PipelineRunner.swift"
)
# Mirrors `static let cancelLadder: [(signal: Int32, after: Duration)] = [ ... ]`.
_CANCEL_LADDER_RE = re.compile(r"static\s+let\s+cancelLadder\b[^=]*=\s*\[(.*?)\n\s*\]", re.S)
_LADDER_STEP_RE = re.compile(r"\((SIG[A-Z]+),\s*\.seconds\((\d+(?:\.\d+)?)\)\)")


def swift_cancel_ladder() -> list[tuple[str, float]]:
    """Stop's escalation after SIGINT, as `(signal name, seconds after the last step)`."""
    text = _PIPELINE_RUNNER_SWIFT.read_text(encoding="utf-8")
    match = _CANCEL_LADDER_RE.search(text)
    assert match is not None, "PipelineRunner.swift no longer declares `cancelLadder`"
    steps = [(name, float(s)) for name, s in _LADDER_STEP_RE.findall(match.group(1))]
    assert steps, "cancelLadder holds no `(SIGNAL, .seconds(n))` steps this test can read"
    return steps


def _swift_seconds(name: str) -> float:
    text = _PIPELINE_RUNNER_SWIFT.read_text(encoding="utf-8")
    match = re.search(
        rf"static\s+let\s+{name}\s*:\s*Duration\s*=\s*\.seconds\((\d+(?:\.\d+)?)\)", text,
    )
    assert match is not None, f"PipelineRunner.swift no longer declares `{name}: Duration`"
    return float(match.group(1))


class TestStopLadderContract:
    """Stop's SIGKILL lands after Python's hosted backstop could record the stop.

    A desktop-hosted run that is still stopping `_HOSTED_STOP_GRACE_S` after the
    signal writes its own `run_cancelled` and exits. SIGKILL writes nothing, so a
    ladder that kills first leaves the log ending on `run_started` with a dead pid,
    which the app reads as "stopped unexpectedly" and the next run records as a
    failure (R20 follow-up, 20 Oct 2026). The Swift suite pins the order from its
    side; this is the copy that runs on every push.
    """

    def test_swift_mirrors_the_backstop_constants(self) -> None:
        import bristlenose.run_lifecycle as rl

        assert _swift_seconds("pythonHostedStopGrace") == rl._HOSTED_STOP_GRACE_S
        assert _swift_seconds("pythonBackstopLockWait") == rl._BACKSTOP_LOCK_TIMEOUT_S

    def test_sigkill_lands_after_the_backstop_could_write(self) -> None:
        import bristlenose.run_lifecycle as rl

        ladder = swift_cancel_ladder()
        assert ladder[-1][0] == "SIGKILL", f"Stop's last resort is not SIGKILL: {ladder}"
        steps = [name for name, _ in ladder]
        first_kill = steps.index("SIGKILL")
        kill_at = sum(after for _, after in ladder[: first_kill + 1])
        latest_write = rl._HOSTED_STOP_GRACE_S + rl._BACKSTOP_LOCK_TIMEOUT_S
        assert kill_at > latest_write, (
            f"Stop sends SIGKILL {kill_at:g} s after SIGINT; the backstop may still be "
            f"writing its run_cancelled until {latest_write:g} s. Lengthen the SIGKILL "
            "step in PipelineRunner.cancelLadder."
        )


_EVENT_LOG_READER_SWIFT = _PIPELINE_RUNNER_SWIFT.with_name("EventLogReader.swift")


class TestQuitAndStopLeaveDifferentRecords:
    """The Mac tells "Analysis interrupted" from "Analysis stopped" by the first
    signal a run took (24 Oct 2026). Python records it as
    ``run_cancelled.cause.signal_name``; Stop sends SIGINT, Quit must not, and
    the reader must call only SIGINT the researcher's Stop."""

    def test_quit_does_not_send_stops_signal(self) -> None:
        text = _PIPELINE_RUNNER_SWIFT.read_text(encoding="utf-8")
        match = re.search(r"static\s+let\s+quitSignal\s*:\s*Int32\s*=\s*(SIG[A-Z]+)", text)
        assert match is not None, "PipelineRunner.swift no longer declares `quitSignal`"
        assert match.group(1) == "SIGTERM", (
            f"Quit sends {match.group(1)}; a SIGINT cancel reads as the researcher's Stop"
        )
        assert "sendSignal(target, Self.quitSignal)" in text, "stopAllForQuit no longer sends quitSignal"

    def test_the_reader_names_sigint_as_the_stop(self) -> None:
        import signal

        text = _EVENT_LOG_READER_SWIFT.read_text(encoding="utf-8")
        match = re.search(r"func\s+endedByLeaving\b.*?\n    \}", text, re.S)
        assert match is not None, "EventLogReader.swift no longer declares `endedByLeaving`"
        assert f'"{signal.Signals(signal.SIGINT).name}"' in match.group(0)


# ---------------------------------------------------------------------------
# The stage budget on run_progress — the ring slice (R27)
# ---------------------------------------------------------------------------

_EVENT_LOG_READER_SWIFT = (
    _REPO_ROOT / "desktop" / "Bristlenose" / "Bristlenose" / "EventLogReader.swift"
)
_RUN_PROGRESS_MATH_SWIFT = (
    _REPO_ROOT / "desktop" / "Bristlenose" / "Bristlenose" / "RunProgressMath.swift"
)
# The three wire fields that carry the slice of the ring a stage owns.
_STAGE_BUDGET_FIELDS = ("stage_base", "stage_span", "stage_expected_seconds")


class TestStageBudgetContract:
    """`stage_base` / `stage_span` / `stage_expected_seconds` are written by
    Python (`RunHandle.progress`, `RunProgressEvent`) and read by two Swift
    sites: the `CodingKeys` of `EventLogReader.Event` and the parameters of
    `RunProgressMath.apply`. A name wrong on one side decodes as nil, and the
    ring quietly keeps the whole-run time fill — the bug returns with nothing
    red. The reader must take the fields as optional, because a sidecar that
    predates them sends none; the Swift suite pins the end-to-end fold
    (`RunProgressSliceTests`), and this is the copy that runs on every push.
    """

    def test_python_writes_the_fields(self) -> None:
        import inspect

        from bristlenose.events import RunProgressEvent
        from bristlenose.run_lifecycle import RunHandle

        for name in _STAGE_BUDGET_FIELDS:
            assert name in RunProgressEvent.model_fields
            assert RunProgressEvent.model_fields[name].default is None
            assert name in inspect.signature(RunHandle.progress).parameters

    def test_swift_decodes_the_fields_by_the_same_names(self) -> None:
        text = _EVENT_LOG_READER_SWIFT.read_text(encoding="utf-8")
        # The file holds more than one CodingKeys enum; only Event's counts.
        m = re.search(r"struct Event\s*:\s*Codable.*?\n    \}\n", text, re.S)
        assert m, "EventLogReader.swift no longer declares `struct Event: Codable`"
        event = m.group(0)
        keys = dict(re.findall(r'case\s+(\w+)\s*=\s*"([^"]+)"', event))
        wire = {v: k for k, v in keys.items()}
        for name in _STAGE_BUDGET_FIELDS:
            assert name in wire, f"EventLogReader.Event has no CodingKey for {name!r}"
            prop = wire[name]
            assert re.search(rf"let\s+{prop}\s*:\s*Double\?", event), (
                f"EventLogReader.Event.{prop} must be `Double?` — an older "
                "sidecar sends no budget, and a non-optional would fail the decode"
            )

    def test_swift_apply_takes_the_fields(self) -> None:
        text = _RUN_PROGRESS_MATH_SWIFT.read_text(encoding="utf-8")
        m = re.search(r"static\s+func\s+apply\s*\((.*?)\)\s*->\s*PipelineProgress", text, re.S)
        assert m, "RunProgressMath.apply is gone"
        for prop in ("stageBase", "stageSpan", "stageExpectedSeconds"):
            assert re.search(rf"{prop}\s*:\s*Double\?", m.group(1)), (
                f"RunProgressMath.apply has no `{prop}: Double?` parameter"
            )


# ---------------------------------------------------------------------------
# The Mac's count of sessions owed a re-analysis after a recode (§J7 R3)
# ---------------------------------------------------------------------------

_SOURCE_FILES_READER = (
    _REPO_ROOT / "desktop" / "Bristlenose" / "Bristlenose" / "SourceFilesReader.swift"
)


def _swift_recoded_session_sql() -> str:
    text = _SOURCE_FILES_READER.read_text(encoding="utf-8")
    match = re.search(
        r"// BEGIN recoded-session-sql\n\s*static let recodedSessionSQL = \"\"\"\n(.*?)\n\s*\"\"\"\n"
        r"\s*// END recoded-session-sql",
        text, re.S,
    )
    assert match is not None, (
        "SourceFilesReader.swift no longer carries the marked recodedSessionSQL; "
        "the Mac's owed-session count must stay held to needs_reanalysis"
    )
    return match.group(1).replace("\\(reportProjectID)", "1")


class TestRecodedSessionSqlContract:
    """The sidebar offers Analyse for a session a recode left owed (owner, 23 Oct
    2026). It counts them in SQL, from an immutable read of the database; serve
    decides the same thing with ``needs_reanalysis``. If the two drift, the Mac
    offers an Analyse that changes nothing, or hides one that is owed."""

    @staticmethod
    def _cases() -> list[tuple[str, str]]:
        """Every role ``kind_prefix`` knows (read from it, so a new role is a new
        case), one it never maps, the empty role, and every tag letter."""
        from bristlenose.server.speaker_slots import _ROLE_PREFIX

        roles = [*_ROLE_PREFIX, "unknown", ""]
        return [(code, role) for code in ("p1", "m1", "o1", "P1") for role in roles]

    @pytest.mark.skipif(not _SOURCE_FILES_READER.exists(), reason="desktop/ not in this checkout")
    def test_the_swift_count_is_needs_reanalysis(self) -> None:
        import sqlite3
        from types import SimpleNamespace

        from bristlenose.server.routes.reanalyse import needs_reanalysis

        sql = _swift_recoded_session_sql()
        for code, role in self._cases():
            db = sqlite3.connect(":memory:")
            db.executescript(
                "CREATE TABLE sessions (id INTEGER PRIMARY KEY, project_id INTEGER);"
                "CREATE TABLE session_speakers (id INTEGER PRIMARY KEY, session_id INTEGER,"
                " speaker_code TEXT, speaker_role TEXT);"
                "INSERT INTO sessions VALUES (1, 1);"
            )
            db.execute("INSERT INTO session_speakers VALUES (1, 1, ?, ?)", (code, role))
            (swift,) = db.execute(sql).fetchone()
            row = SimpleNamespace(speaker_code=code, speaker_role=role)
            python = needs_reanalysis(SimpleNamespace(slot_code=code, row=row))
            assert swift == int(python), f"{code}/{role!r}: Swift {swift}, Python {python}"

    @pytest.mark.skipif(not _SOURCE_FILES_READER.exists(), reason="desktop/ not in this checkout")
    def test_the_swift_count_names_real_columns(self) -> None:
        from bristlenose.server.models import Session, SessionSpeaker

        sql = _swift_recoded_session_sql()
        assert Session.__tablename__ in sql and SessionSpeaker.__tablename__ in sql
        for column in ("session_id", "speaker_code", "speaker_role"):
            assert column in SessionSpeaker.__table__.columns, column
        assert "project_id" in Session.__table__.columns


# ---------------------------------------------------------------------------
# Feedback URLs: the Mac sheet's compile-time copies of health.py's defaults
# ---------------------------------------------------------------------------

_FEEDBACK_SUBMISSION_SWIFT = (
    _REPO_ROOT / "desktop" / "Bristlenose" / "Bristlenose" / "FeedbackSubmission.swift"
)


class TestFeedbackURLContract:
    """`FeedbackEndpoint` mirrors the defaults in `routes/health.py`.

    The sheet POSTs to `defaultURL` when it has no serve, and a failed send
    tells the researcher to paste into `issuesURL` (R80). Neither reads
    `/api/health` for these, so a change on one side alone would send
    feedback, or the researcher, somewhere else with nothing to say so.
    """

    @pytest.mark.parametrize(
        ("swift_name", "python_name"),
        [
            ("defaultURL", "DEFAULT_FEEDBACK_URL"),
            ("issuesURL", "DEFAULT_GITHUB_ISSUES_URL"),
        ],
    )
    def test_swift_constant_equals_python_default(
        self, swift_name: str, python_name: str
    ) -> None:
        from bristlenose.server.routes import health

        text = _FEEDBACK_SUBMISSION_SWIFT.read_text(encoding="utf-8")
        match = re.search(
            rf'static\s+let\s+{swift_name}\s*=\s*URL\(string:\s*"([^"]+)"\)!', text
        )
        assert match is not None, f"FeedbackSubmission.swift no longer declares {swift_name}"
        assert match.group(1) == getattr(health, python_name)


class TestPlayerPathContract:
    """`PopoutPolicy.playerPath` is the serve's `player_url`.

    The Mac opens the popout player window only for that page and refuses a
    new window for every other report page. A change to `player_url` alone
    would leave the app refusing the player itself: timecodes would stop
    playing, with nothing to say why.
    """

    def test_swift_player_path_equals_serve_player_url(self) -> None:
        webview = _REPO_ROOT / "desktop" / "Bristlenose" / "Bristlenose" / "WebView.swift"
        swift = re.search(
            r'static\s+let\s+playerPath\s*=\s*"([^"]+)"', webview.read_text(encoding="utf-8")
        )
        assert swift is not None, "WebView.swift no longer declares PopoutPolicy.playerPath"
        sessions = _REPO_ROOT / "bristlenose" / "server" / "routes" / "sessions.py"
        served = re.search(r'player_url="([^"]+)"', sessions.read_text(encoding="utf-8"))
        assert served is not None, "routes/sessions.py no longer sets player_url as a literal"
        assert swift.group(1) == served.group(1)
