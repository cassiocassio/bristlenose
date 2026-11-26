"""The shared palette (scripts/board-tokens.css) keeps small text readable: WCAG 2.2 AA 4.5:1.

The light values of --mute, --ok, --warn and --now measured 2.4 to 3.4 against the panel before
26 Nov 2026 (accessibility review of the home page). This holds the fix, in both themes.
"""
import re
from pathlib import Path

CSS = (Path(__file__).resolve().parent.parent / "scripts" / "board-tokens.css").read_text(encoding="utf-8")
TEXT_ON_PANEL = ("ink-2", "mute", "ok", "warn", "bad", "unknown", "now")
TEXT_ON_OWN_TINT = ("ok", "warn", "bad", "unknown", "now")   # the pills: --x on --x-bg


def block(selector_start):
    i = CSS.index(selector_start)
    j = CSS.index("--hatch", i)
    return CSS[i:j]


def hex6(h):
    return "#" + "".join(c * 2 for c in h[1:]) if len(h) == 4 else h


def tokens(b):
    return {k: hex6(v) for k, v in re.findall(r"--([a-z0-9-]+):\s*(#[0-9a-fA-F]{3,6})\b", b)}


def lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


LIGHT = tokens(block(":root{"))
DARK = tokens(block(':root[data-theme="dark"]{'))


def check(theme, name):
    fails = []
    for t in TEXT_ON_PANEL:
        r = ratio(theme[t], theme["panel"])
        if r < 4.5:
            fails.append(f"--{t} on --panel {r:.2f}")
    for t in TEXT_ON_OWN_TINT:
        r = ratio(theme[t], theme[t + "-bg"])
        if r < 4.5:
            fails.append(f"--{t} on --{t}-bg {r:.2f}")
    r = ratio(theme["mute"], theme["bg"])
    if r < 4.5:
        fails.append(f"--mute on --bg {r:.2f}")
    assert not fails, f"{name}: " + "; ".join(fails)


def test_light_small_text_reaches_4_5_to_1():
    check(LIGHT, "light")


def test_dark_small_text_reaches_4_5_to_1():
    check(DARK, "dark")


def test_the_parser_found_both_palettes():
    assert len(LIGHT) > 20 and len(DARK) > 20 and LIGHT["panel"] != DARK["panel"]
