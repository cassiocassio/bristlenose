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
