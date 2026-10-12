"""Which lenses can be selected — the one derivation (docs/design-progressive-lenses.md §3.3)."""

from __future__ import annotations

from bristlenose.server.lens_readiness import LENSES, Progress, lens_readiness


def test_no_progressive_run_means_every_lens_is_available() -> None:
    """Phase 0 ships this path only: nothing may change for a finished project,
    a re-analyse over its previous report, or a server that tracks no progress."""
    assert lens_readiness(None) == dict.fromkeys(LENSES, True)


def test_at_ingest_only_sessions() -> None:
    assert lens_readiness(Progress()) == {
        "sessions": True, "quotes": False, "signals": False,
        "codebook": False, "project": False, "discussion": False,
    }


def test_a_session_readable_is_not_a_quote() -> None:
    r = lens_readiness(Progress(readable=frozenset({"s1"})))
    assert r["sessions"] and not r["quotes"]


def test_quotes_light_at_the_first_session_with_quotes() -> None:
    assert lens_readiness(Progress(readable=frozenset({"s1"}), quoted=frozenset({"s1"})))["quotes"]


def test_a_failed_session_does_not_light_quotes() -> None:
    """FOSSDA s3: thirty minutes in quote extraction, nothing back."""
    r = lens_readiness(Progress(readable=frozenset({"s3"}), quote_failed=frozenset({"s3"})))
    assert not r["quotes"]


def test_signals_wait_for_the_barrier() -> None:
    before = lens_readiness(Progress(quoted=frozenset({"s1", "s2"})))
    after = lens_readiness(Progress(quoted=frozenset({"s1", "s2"}), joined=True))
    assert not before["signals"] and after["signals"]


def test_codebooks_and_project_wait_for_the_run_in_v1() -> None:
    r = lens_readiness(Progress(quoted=frozenset({"s1"}), joined=True, discussion_done=True))
    assert not r["codebook"] and not r["project"] and r["discussion"]
