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
