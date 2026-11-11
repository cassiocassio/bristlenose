"""scripts/snap-store-status.py: the latest status per component decides, not the first seen."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_P = Path(__file__).resolve().parent.parent / "scripts" / "snap-store-status.py"
_spec = importlib.util.spec_from_file_location("snap_store_status", _P)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
sys.modules["snap_store_status"] = mod  # a path-loaded module goes into sys.modules first
_spec.loader.exec_module(mod)


def _feed(*items: tuple[str, str]) -> str:
    body = "".join(
        f"<item><title>{t}</title><pubDate>{d}</pubDate></item>" for t, d in items
    )
    return f'<?xml version="1.0"?><rss version="2.0"><channel>{body}</channel></rss>'


def test_an_open_outage_is_an_incident() -> None:
    v = mod.verdict(mod.parse(_feed(("api.snapcraft.io - refresh - Major Outage",
                                     "Wed, 11 Nov 2026 11:55:44 +0000"))))
    assert v["ok"] is False
    assert "api.snapcraft.io - refresh" in v["down"]


def test_a_later_operational_item_clears_an_earlier_outage() -> None:
    v = mod.verdict(mod.parse(_feed(
        ("Serial Vault - Major Outage", "Wed, 11 Nov 2026 12:54:45 +0000"),
        ("Serial Vault - Operational", "Wed, 11 Nov 2026 13:30:00 +0000"),
    )))
    assert v["ok"] is True


def test_item_order_in_the_feed_does_not_matter() -> None:
    v = mod.verdict(mod.parse(_feed(
        ("Serial Vault - Operational", "Wed, 11 Nov 2026 13:30:00 +0000"),
        ("Serial Vault - Major Outage", "Wed, 11 Nov 2026 12:54:45 +0000"),
    )))
    assert v["ok"] is True


def test_an_unreadable_feed_is_not_reported_as_all_clear(monkeypatch) -> None:
    def boom() -> str:
        raise OSError("no route")

    monkeypatch.setattr(mod, "fetch", boom)
    assert mod.main([]) == mod.UNREADABLE
