"""Tests for desktop/sidecar_entry.py — the bundled sidecar binary's argv router.

The sidecar entry script narrows what the bundled binary will respond to:
unknown first args get rewritten to "serve <args...>"; only explicitly
allowlisted subcommands (`_PASSTHROUGH_COMMANDS`) reach Typer unchanged.
This test pins the allowlist so any expansion is a deliberate, reviewable
change — not a silent drift.

Rationale (security-review, 21 Apr 2026): the bundled sidecar's argv path
is the only argv surface that can vary across invocations. Today it's
controlled by Swift's `Process()` call, but future features (URL scheme
handlers, AppleEvents, Background Assets daemons) could put user-influenced
strings into argv. A denylist-by-omission isn't enough — pin the allowlist.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


def _import_sidecar_entry():
    """Import desktop/sidecar_entry.py as a module without making it part
    of the package layout. The desktop/ directory isn't on sys.path during
    normal test runs."""
    desktop_dir = Path(__file__).parent.parent / "desktop"
    if str(desktop_dir) not in sys.path:
        sys.path.insert(0, str(desktop_dir))
    import sidecar_entry  # noqa: E402

    return sidecar_entry


class TestSidecarPassthroughAllowlist:
    """Pin the exact set of subcommands the bundled sidecar accepts."""

    def test_passthrough_set_is_doctor_and_run(self) -> None:
        """The allowlist of subcommands the bundled binary accepts (other
        than the implicit "serve" rewrite) is exactly {"doctor", "run"}.

        Any change to this set is a security-relevant widening of the
        sidecar's surface area. If you intend to add a new subcommand:
          1. Justify why the bundled binary needs to expose it.
          2. Confirm the subcommand is read-only or sandbox-safe, or
             add it to `_HOST_GATED_COMMANDS`.
          3. Update this test in the same commit.

        See c3-bundle-completeness P2 + the security-review on commit
        52024f8 + plan-pipeline-runner-sidecar-mode (1 May 2026) for
        context.
        """
        sidecar_entry = _import_sidecar_entry()
        assert sidecar_entry._PASSTHROUGH_COMMANDS == {"doctor", "run"}, (
            "Sidecar passthrough allowlist changed without updating this test. "
            "If the change is intentional, update the assertion AND add a "
            "comment here explaining why each new subcommand is bundled-safe."
        )

    def test_host_gated_set_is_run(self) -> None:
        """`run` is state-changing and network-egressing, so it requires
        the host-gate env var. `doctor` is read-only and ungated.

        If you add a new state-changing or network-egressing passthrough
        command, it MUST also go in `_HOST_GATED_COMMANDS`. Update this
        test in the same commit."""
        sidecar_entry = _import_sidecar_entry()
        assert sidecar_entry._HOST_GATED_COMMANDS == {"run"}


class TestRunHostGate:
    """The `run` passthrough rejects invocation without the desktop-host
    env-var handshake. This is the confused-deputy mitigation between
    this branch landing and the App Sandbox flip (A1c)."""

    def test_run_without_host_env_exits_non_zero(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`bristlenose-sidecar run /path` invoked without
        `_BRISTLENOSE_HOSTED_BY_DESKTOP=1` exits 2 with a stderr message."""
        sidecar_entry = _import_sidecar_entry()
        monkeypatch.delenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", raising=False)
        monkeypatch.setattr(sys, "argv", ["bristlenose-sidecar", "run", "/some/path"])

        with pytest.raises(SystemExit) as exc_info:
            sidecar_entry.main()

        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "desktop-host-only" in captured.err
        assert "run" in captured.err

    def test_run_with_wrong_host_env_exits_non_zero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Any value other than exactly "1" is rejected — the env var is
        a fixed-string handshake, not a truthy-check."""
        sidecar_entry = _import_sidecar_entry()
        monkeypatch.setenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", "true")
        monkeypatch.setattr(sys, "argv", ["bristlenose-sidecar", "run", "/some/path"])

        with pytest.raises(SystemExit) as exc_info:
            sidecar_entry.main()

        assert exc_info.value.code == 2

    def test_doctor_does_not_require_host_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`doctor` is read-only and ungated; the host-env check must not
        apply to it. We can't run the full Typer app in this test, so we
        stop just before `app()` by patching it."""
        sidecar_entry = _import_sidecar_entry()
        monkeypatch.delenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", raising=False)
        monkeypatch.setattr(sys, "argv", ["bristlenose-sidecar", "doctor", "--self-test"])

        called = {"app": False}

        def fake_app() -> None:
            called["app"] = True

        monkeypatch.setattr(sidecar_entry, "app", fake_app)
        sidecar_entry.main()

        assert called["app"], "doctor passthrough should reach app() without host-env gate"
