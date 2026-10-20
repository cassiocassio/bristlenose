"""The guest walk's morning page: what it counts as changed, and its masks.

`desktop/scripts/guest-walk/report.py` compares two walks of the Mac app
(docs/design-guest-walk.md). The failures that matter are a page that lies: a
menu change it cannot see, a mask that silently excludes nothing because its
screen was renamed, a mask nobody can explain. The pixel diff itself is the
walker's (Swift, CoreGraphics) and is exercised by the walk, not here.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WALK_DIR = ROOT / "desktop" / "scripts" / "guest-walk"


def _load_report():
    spec = importlib.util.spec_from_file_location("guest_walk_report", WALK_DIR / "report.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


report = _load_report()


def _menus(**items: dict) -> dict[str, dict]:
    base = {"enabled": True, "shortcut": "", "checked": False}
    return {path: {**base, "path": path, **fields} for path, fields in items.items()}


def test_menu_diff_names_each_kind_of_change() -> None:
    a = _menus(**{"File ▸ Export Report…": {}, "Project ▸ Re-analyse…": {}, "View ▸ Tidy": {}})
    b = _menus(**{
        "File ▸ Export Report…": {"shortcut": "⇧⌘E"},
        "Project ▸ Re-analyse…": {"enabled": False},
        "File ▸ Export Screens…": {},
    })
    rows = report.menu_diff(a, b)
    assert any("Re-analyse" in r and "enabled True → False" in r for r in rows)
    assert any("Export Report" in r and "shortcut" in r for r in rows)
    assert any("Export Screens" in r and "new item" in r for r in rows)
    assert any("View ▸ Tidy" in r and "gone" in r for r in rows)


def test_menu_diff_of_identical_trees_is_empty() -> None:
    a = _menus(**{"File ▸ New Project": {}, "Edit ▸ Undo": {"enabled": False}})
    assert report.menu_diff(a, dict(a)) == []


def test_a_menu_mask_hides_only_its_own_item() -> None:
    # Edit ▸ Paste follows the host clipboard (tart shares it); nothing else may hide.
    a = _menus(**{"Edit ▸ Paste": {"enabled": False}, "Edit ▸ Copy": {"enabled": False}})
    b = _menus(**{"Edit ▸ Paste": {"enabled": True}, "Edit ▸ Copy": {"enabled": True}})
    rows = report.menu_diff(a, b)
    assert not any("Paste" in r for r in rows)
    assert any("Copy" in r for r in rows)


def _walk_steps() -> set[str]:
    """Every screen name walk.sh can capture, from its `shot` calls."""
    src = (WALK_DIR / "walk.sh").read_text()
    names = set(re.findall(r'^\s*shot ([a-z][a-z0-9-]*)', src, re.MULTILINE))
    # The loops build names from a list: settings-<tab> and lens-<lens>.
    for tab in re.findall(r'for tab in ([^;]+);', src)[0].replace('"', "").split():
        names.add(f"settings-{tab.lower()}")
    names |= {"settings-llm-provider", "settings-mcp-agents"}
    names |= {f"lens-{lens.lower()}" for lens in re.findall(r'for lens in ([^;]+);', src)[0].split()}
    return names


def test_every_mask_names_a_screen_the_walk_takes_and_says_why() -> None:
    # A mask whose screen was renamed excludes nothing, silently; one with no
    # reason is a hole nobody can review.
    steps = _walk_steps()
    for key, regions in report.MASKS.items():
        screen = re.sub(r"-\d+$", "", key)
        assert screen in steps, f"mask {key!r} names no screen walk.sh captures"
        assert regions, f"mask {key!r} has no regions"
        for (_x, _y, w, h), why in regions:
            assert w > 0 and h > 0, f"mask {key!r} has an empty region"
            assert why.strip(), f"mask {key!r} has no reason"


def test_every_menu_mask_says_why() -> None:
    for path, why in report.MENU_MASKS.items():
        assert "▸" in path and why.strip()
