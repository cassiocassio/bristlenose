#!/usr/bin/env python3
"""SPIKE — autogenerate light/dark hero shots of the native Bristlenose window.

Why native rather than a browser tab: the docs double as a brochure, so the Mac
frame is part of what's being sold — and the native window already contains the
SPA, so one capture gets both the chrome and the report content.

    uv run --with pyobjc-framework-Quartz python capture.py --list
    uv run --with pyobjc-framework-Quartz python capture.py --out shots

APPEARANCE — we drive the app's OWN preference, not the system's.
The app stores `appearance` (auto|light|dark) via @AppStorage in the
`app.bristlenose` domain (AppearanceSettingsView.swift). Flipping the *system*
appearance does nothing when the user has pinned the app to light or dark —
which is exactly what happened on the first run of this spike: both captures
came back byte-identical. Driving the app pref also avoids needing Automation
▸ System Events and avoids yanking the user's whole desktop between modes.

Open question this spike exists to answer: whether @AppStorage notices an
external `defaults write` while the app is running. cfprefsd caching makes it
unreliable. If the captures still come back identical, pass --relaunch to
quit and reopen the app between modes (slow but deterministic). The durable
fix is app-side — see --screenshot-mode in docs/design-docs-system.md D4.

What is STUBBED: driving the app into a given state. `setup` is AppleScript run
before capture; only trivial menu-poking is proven, and addressing a SwiftUI
toolbar button through the accessibility hierarchy is fragile. Don't chase it
with more AppleScript — that's the signal to do it app-side.

PERMISSIONS: Screen Recording, for screencapture and for window titles from
Quartz. Grant it to whichever terminal runs this. Note it is granted per
process — a terminal that has it does not confer it on other tools.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

APP = "Bristlenose"
# One constant, deliberately: a Mac app's UserDefaults domain IS its bundle
# identifier, so `defaults read/write` and `open -b` take the same string.
# Holding it twice is how this drifted — the second copy sat on the retired
# `research.bristlenose.app` (a non-existent `.research` TLD, replaced by
# `app.bristlenose` on 25 Mar 2026; see desktop/CLAUDE.md § Key conventions),
# which silently broke --relaunch while the `defaults` half kept working.
BUNDLE_ID = "app.bristlenose"

# One entry per docs section that wants a hero. `setup` is AppleScript run
# against the app before the shot; None means "capture as-is".
SHOTS: list[dict] = [
    {"id": "report-quotes", "setup": None,
     "doc": "run-an-analysis — the report as the reader will first meet it"},
    {"id": "export-menu", "doc": "share-report / send-to-miro — the Export menu open",
     "setup": 'tell application "System Events" to tell process "Bristlenose" '
              'to click button 1 of group 2 of toolbar 1 of window 1'},
]


def sh(*cmd: str) -> str:
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()


def osa(script: str) -> tuple[int, str]:
    p = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return p.returncode, (p.stderr or p.stdout).strip()


def read_appearance() -> str:
    return sh("defaults", "read", BUNDLE_ID, "appearance") or "auto"


def set_appearance(value: str, relaunch: bool) -> None:
    subprocess.run(["defaults", "write", BUNDLE_ID, "appearance", "-string", value], check=True)
    if relaunch:
        # quit is tolerant — the app legitimately may not be running yet.
        osa(f'tell application id "{BUNDLE_ID}" to quit')
        time.sleep(1.2)
        # open is NOT tolerant. --relaunch exists to beat cfprefsd caching, so a
        # relaunch that silently didn't happen returns two identical captures —
        # the exact symptom it was added to cure. check=True keeps a wrong or
        # uninstalled bundle id loud.
        subprocess.run(["open", "-b", BUNDLE_ID], check=True)
        time.sleep(4.0)  # sidecar boot + WKWebView first paint


def windows() -> list[tuple[int, str, int, int]]:
    """(window_id, title, w, h) for on-screen windows owned by the app."""
    import Quartz
    info = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID,
    )
    out = []
    for w in info or []:
        if w.get("kCGWindowOwnerName") != APP:
            continue
        b = w.get("kCGWindowBounds", {})
        # Skip the shadow/helper surfaces the app also owns.
        if b.get("Width", 0) < 400 or b.get("Height", 0) < 300:
            continue
        out.append((int(w["kCGWindowNumber"]), w.get("kCGWindowName") or "(untitled)",
                    int(b["Width"]), int(b["Height"])))
    return out


def capture(win_id: int, dest: Path, shadow: bool) -> bool:
    cmd = ["screencapture", "-x", f"-l{win_id}"]
    if not shadow:
        cmd.append("-o")
    cmd.append(str(dest))
    ok = subprocess.run(cmd).returncode == 0 and dest.exists()
    if not ok:
        print(f"  ! screencapture failed for window {win_id} — is Screen Recording "
              f"granted to THIS terminal?", file=sys.stderr)
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="show candidate windows and exit")
    ap.add_argument("--out", type=Path, default=Path("shots"))
    ap.add_argument("--no-shadow", action="store_true",
                    help="omit the window shadow (tighter crop, no transparent margin)")
    ap.add_argument("--relaunch", action="store_true",
                    help="quit+reopen the app between modes, if the live pref write "
                         "doesn't repaint it")
    ap.add_argument("--settle", type=float, default=1.5,
                    help="seconds to wait after an appearance change before capturing")
    args = ap.parse_args()

    wins = windows()
    if args.list or not wins:
        for wid, title, w, h in wins:
            print(f"{wid:>8}  {w}x{h}  {title}")
        if not wins:
            print(f"no on-screen {APP} windows found — is the app running and unminimised?")
        return 0 if wins else 1

    args.out.mkdir(parents=True, exist_ok=True)
    original = read_appearance()
    print(f"app appearance was: {original}")
    written: list[Path] = []

    try:
        for mode in ("light", "dark"):
            set_appearance(mode, relaunch=args.relaunch)
            time.sleep(args.settle)  # let the whole window redraw, WKWebView included
            # Re-resolve: a relaunch mints a new window id.
            live = windows()
            if not live:
                print(f"  ! no window after switching to {mode}", file=sys.stderr)
                continue
            win_id = live[0][0]
            for shot in SHOTS:
                if shot["setup"]:
                    rc, err = osa(shot["setup"])
                    if rc != 0:
                        print(f"  ! setup failed for {shot['id']}: {err}", file=sys.stderr)
                        continue
                    time.sleep(0.35)
                dest = args.out / f"{shot['id']}-{mode}@2x.png"
                if capture(win_id, dest, shadow=not args.no_shadow):
                    print(f"  {dest}")
                    written.append(dest)
                if shot["setup"]:
                    osa('tell application "System Events" to key code 53')  # esc
                    time.sleep(0.2)
    finally:
        set_appearance(original, relaunch=False)
        print(f"app appearance restored to: {original}")

    # The failure this spike was built to catch: a mode switch that didn't take
    # produces byte-identical pairs, which look like success in a file listing.
    for shot in SHOTS:
        pair = [args.out / f"{shot['id']}-{m}@2x.png" for m in ("light", "dark")]
        if all(p.exists() for p in pair) and pair[0].read_bytes() == pair[1].read_bytes():
            print(f"  ! {shot['id']}: light and dark are IDENTICAL — the appearance "
                  f"change did not reach the app. Try --relaunch.", file=sys.stderr)

    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
