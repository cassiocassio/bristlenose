"""Register an experimental palette in every place the app lists palettes, and take it out again.

A variant ("edo2", "edo3", ...) has to be selectable in the Mac app and the web report to be judged for real.
That is ten edits across Python, TypeScript, Swift and 21 locale files; doing them by hand per variant is how one
gets missed. `register` makes them, `unregister` reverses them, and `finish` ends the experiment: the winner is
promoted over `edo`, every variant is unregistered and its files deleted. All edits are idempotent text edits
anchored on the line that lists `catppuccin` (variants sit between `edo` and `catppuccin`).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
COLORS = REPO / "bristlenose/theme/colors"
ASSETS = REPO / "desktop/Bristlenose/Bristlenose/Assets.xcassets"
SWIFT = REPO / "desktop/Bristlenose/Bristlenose"
LOCALES = REPO / "bristlenose/locales"
PY_LISTS = [REPO / "bristlenose/stages/s12_render/theme_assets.py", REPO / "scripts/gen-welcome-timeline.py"]
TS_LISTS = [REPO / "frontend/src/utils/bootPalette.ts", REPO / "frontend/index.html", REPO / "frontend/src/utils/bootPalette.test.ts"]
VARIANT = re.compile(r"^edo\d+$")


def _edit(path: Path, fn) -> bool:
    old = path.read_text(encoding="utf-8")
    new = fn(old)
    if new != old:
        path.write_text(new, encoding="utf-8")
    return new != old


def stem(key: str) -> str:
    return "".join(p.capitalize() for p in key.split("-"))


def variants() -> list[str]:
    return sorted((p.stem.removeprefix("palette-") for p in COLORS.glob("palette-edo[0-9]*.css")),
                  key=lambda k: int(k[3:]))


def register(key: str) -> list[str]:
    done = []

    def add_py(s: str) -> str:
        line = f'    "colors/palette-{key}.css",\n'
        return s if line in s else s.replace('    "colors/palette-catppuccin.css",\n', line + '    "colors/palette-catppuccin.css",\n', 1)
    for p in PY_LISTS:
        if _edit(p, add_py):
            done.append(p.relative_to(REPO).as_posix())

    def add_ts(s: str) -> str:
        return s if f'"{key}", "catppuccin"' in s else s.replace('"catppuccin"', f'"{key}", "catppuccin"', 1)
    for p in TS_LISTS:
        if _edit(p, add_ts):
            done.append(p.relative_to(REPO).as_posix())

    def add_picker(s: str) -> str:
        line = f'                    Text(i18n.t("settings.palette.{key}")).tag("{key}")\n'
        anchor = '                    Text(i18n.t("settings.palette.catppuccin")).tag("catppuccin")\n'
        return s if line in s else s.replace(anchor, line + anchor, 1)
    if _edit(SWIFT / "AppearanceSettingsView.swift", add_picker):
        done.append("desktop/.../AppearanceSettingsView.swift")

    def add_tint(s: str) -> str:
        return s if f'"{key}", "catppuccin"' in s else s.replace('"catppuccin"', f'"{key}", "catppuccin"', 1)
    if _edit(SWIFT / "SidebarPalette.swift", add_tint):
        done.append("desktop/.../SidebarPalette.swift")

    n = re.sub(r"\D", "", key)
    for loc in sorted(LOCALES.iterdir()):
        f = loc / "settings.json"
        if not f.is_file() or loc.name == "zh-Hant-HK":
            continue

        def add_label(s: str, n=n) -> str:
            if f'"{key}":' in s:
                return s
            m = re.search(r'^(\s*)"edo": "(.*)",\n', s, re.M)
            if not m:
                return s
            return s[:m.end()] + f'{m.group(1)}"{key}": "{m.group(2)} {n}",\n' + s[m.end():]
        if _edit(f, add_label):
            done.append(f"locales/{loc.name}/settings.json")
    return done


def unregister(key: str) -> list[str]:
    done = []
    rx_py = re.compile(rf'    "colors/palette-{re.escape(key)}.css",\n')
    for p in PY_LISTS:
        if _edit(p, lambda s: rx_py.sub("", s)):
            done.append(p.relative_to(REPO).as_posix())
    for p in TS_LISTS:
        if _edit(p, lambda s: s.replace(f'"{key}", ', "")):
            done.append(p.relative_to(REPO).as_posix())
    if _edit(SWIFT / "AppearanceSettingsView.swift", lambda s: s.replace(
            f'                    Text(i18n.t("settings.palette.{key}")).tag("{key}")\n', "")):
        done.append("desktop/.../AppearanceSettingsView.swift")
    if _edit(SWIFT / "SidebarPalette.swift", lambda s: s.replace(f'"{key}", ', "")):
        done.append("desktop/.../SidebarPalette.swift")
    rx_loc = re.compile(rf'^\s*"{re.escape(key)}": ".*",\n', re.M)
    for loc in sorted(LOCALES.iterdir()):
        f = loc / "settings.json"
        if f.is_file() and _edit(f, lambda s: rx_loc.sub("", s)):
            done.append(f"locales/{loc.name}/settings.json")
    css = COLORS / f"palette-{key}.css"
    if css.exists():
        css.unlink()
        done.append(f"theme/colors/palette-{key}.css (deleted)")
    for d in ASSETS.glob(f"Palette{stem(key)}*.colorset"):
        shutil.rmtree(d)
        done.append(f"{d.name} (deleted)")
    prov = Path(__file__).parent / "promoted.json"
    if prov.exists():
        data = json.loads(prov.read_text())
        if data.pop(key, None) is not None:
            prov.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    return done


def regenerate() -> None:
    r = subprocess.run([sys.executable, str(REPO / "scripts/gen-welcome-timeline.py")], capture_output=True, text=True, cwd=REPO)
    print((r.stdout + r.stderr).strip() or "regenerated the welcome timeline")
