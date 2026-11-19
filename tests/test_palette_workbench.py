"""The palette workbench (experiments/brand-palettes) must reproduce the shipped palettes.

Two guarantees the toolkit rests on: a palette read from CSS and written back is the same
palette (so iterations start from what the app really ships), and neutral knobs change
nothing (so a nudge moves only what you moved).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_BP = Path(__file__).resolve().parent.parent / "experiments" / "brand-palettes"
_COLORS = Path(__file__).resolve().parent.parent / "bristlenose" / "theme" / "colors"
sys.path.insert(0, str(_BP))
import table as palette_table  # noqa: E402


@pytest.fixture
def node() -> None:
    """Every test that runs the workbench's JavaScript asks for this: one skip, not
    one per test (the shape of the `symlinks` fixture, 7d32124a), so the skip-site
    ratchet counts it once. They run wherever node is on PATH, as the six per-test
    decorators did."""
    if shutil.which("node") is None:
        pytest.skip("node not installed")


@pytest.mark.parametrize("path", sorted(_COLORS.glob("palette-*.css")), ids=lambda p: p.stem)
def test_shipped_palette_round_trips(path: Path, tmp_path: Path) -> None:
    key = path.stem.removeprefix("palette-")
    first = palette_table.Table.from_css(path, key)
    assert len(first.cells) >= 45
    out = tmp_path / path.name
    out.write_text(first.to_css(key), encoding="utf-8")
    assert first.diff(palette_table.Table.from_css(out, key)) == []


@pytest.mark.usefixtures("node")
def test_neutral_knobs_leave_the_palette_alone(tmp_path: Path) -> None:
    base = palette_table.Table.from_css(_COLORS / "palette-edo.css", "edo")
    (tmp_path / "b.json").write_text(
        json.dumps({k: {"light": c.light, "dark": c.dark} for k, c in base.cells.items()}), encoding="utf-8")
    (tmp_path / "k.json").write_text("{}", encoding="utf-8")
    r = subprocess.run(["node", str(_BP / "knobs.mjs"), str(tmp_path / "b.json"), str(tmp_path / "k.json")],
                       capture_output=True, text=True, check=True)
    out = json.loads(r.stdout)["table"]
    moved = [
        k for k, c in base.cells.items() for m in ("light", "dark")
        if out[k][m].replace("0.10", "0.1") != getattr(c, m).replace("0.10", "0.1")
    ]
    assert moved == []


@pytest.mark.usefixtures("node")
def test_a_single_token_override_beats_the_sliders(tmp_path: Path) -> None:
    base = palette_table.Table.from_css(_COLORS / "palette-edo.css", "edo")
    (tmp_path / "b.json").write_text(
        json.dumps({k: {"light": c.light, "dark": c.dark} for k, c in base.cells.items()}), encoding="utf-8")
    (tmp_path / "k.json").write_text(json.dumps({"dark": {"paperHue": 120, "accentChroma": 1.5}}), encoding="utf-8")
    (tmp_path / "o.json").write_text(json.dumps({"--bn-colour-accent": {"dark": "#123456"}}), encoding="utf-8")
    r = subprocess.run(
        ["node", str(_BP / "knobs.mjs"), *(str(tmp_path / n) for n in ("b.json", "k.json", "o.json"))],
        capture_output=True, text=True, check=True)
    out = json.loads(r.stdout)["table"]
    assert out["--bn-colour-accent"]["dark"] == "#123456"          # the override, not the nudged accent
    assert out["--bn-colour-accent"]["light"] == base.cells["--bn-colour-accent"].light  # other mode untouched
    assert out["--bn-colour-bg"]["dark"] != base.cells["--bn-colour-bg"].dark  # the sliders still moved the rest


def _apply(tmp_path: Path, knobs: dict, overrides: dict) -> tuple[dict, dict]:
    base = palette_table.Table.from_css(_COLORS / "palette-edo.css", "edo")
    raw = {k: {"light": c.light, "dark": c.dark} for k, c in base.cells.items()}
    (tmp_path / "b.json").write_text(json.dumps(raw), encoding="utf-8")
    (tmp_path / "k.json").write_text(json.dumps(knobs), encoding="utf-8")
    (tmp_path / "o.json").write_text(json.dumps(overrides), encoding="utf-8")
    r = subprocess.run(
        ["node", str(_BP / "knobs.mjs"), *(str(tmp_path / n) for n in ("b.json", "k.json", "o.json"))],
        capture_output=True, text=True, check=True)
    return raw, json.loads(r.stdout)["table"]


@pytest.mark.usefixtures("node")
def test_accent_lightness_leaves_the_selection_wash_pale(tmp_path: Path) -> None:
    raw, out = _apply(tmp_path, {"light": {"accentLight": 0.08}}, {})
    assert out["--bn-colour-accent"]["light"] != raw["--bn-colour-accent"]["light"]   # the accent moved
    assert out["--bn-selection-bg"]["light"] == raw["--bn-selection-bg"]["light"]     # the wash did not
    assert out["--bn-colour-suggestion-bg"]["light"] == raw["--bn-colour-suggestion-bg"]["light"]


@pytest.mark.usefixtures("node")
def test_an_accent_override_carries_its_family(tmp_path: Path) -> None:
    raw, out = _apply(tmp_path, {}, {"--bn-colour-accent": {"light": "#4191e2"}})
    assert out["--bn-colour-accent"]["light"] == "#4191e2"
    assert out["--bn-selection-border"]["light"] == "#4191e2"       # a direct use of the accent follows it exactly
    assert out["--bn-colour-suggestion"]["light"] == "#4191e2"
    assert out["--bn-glow-colour"]["light"].startswith("rgba(65, 145, 226")  # so does the translucent glow
    assert out["--bn-selection-bg"]["light"] != raw["--bn-selection-bg"]["light"]  # the wash took the new hue
    assert out["--bn-colour-accent"]["dark"] == raw["--bn-colour-accent"]["dark"]  # the other appearance untouched


@pytest.mark.usefixtures("node")
def test_an_explicit_override_still_beats_the_family(tmp_path: Path) -> None:
    _, out = _apply(tmp_path, {}, {"--bn-colour-accent": {"light": "#4191e2"},
                                   "--bn-selection-border": {"light": "#123456"}})
    assert out["--bn-selection-border"]["light"] == "#123456"


def test_register_and_unregister_round_trip_on_the_real_sites(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every place the app lists palettes still has the anchor `register` edits, and undoing it is exact.

    Works on a copy of the real files, so it fails the day someone reshapes one of those lists
    (the symptom would otherwise be a variant that works in the web report but not the Mac picker).
    """
    import register

    repo = Path(__file__).resolve().parent.parent

    def mirror(real: Path) -> Path:
        dst = tmp_path / real.relative_to(repo)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(real.read_text(encoding="utf-8"), encoding="utf-8")
        return dst

    py = [mirror(p) for p in register.PY_LISTS]
    ts = [mirror(p) for p in register.TS_LISTS]
    picker = mirror(register.SWIFT / "AppearanceSettingsView.swift")
    tint = mirror(register.SWIFT / "SidebarPalette.swift")
    locales = [mirror(p) for p in sorted(register.LOCALES.glob("*/settings.json")) if p.parent.name != "zh-Hant-HK"]
    before = {p: p.read_text(encoding="utf-8") for p in py + ts + [picker, tint] + locales}

    monkeypatch.setattr(register, "REPO", tmp_path)
    monkeypatch.setattr(register, "PY_LISTS", py)
    monkeypatch.setattr(register, "TS_LISTS", ts)
    monkeypatch.setattr(register, "SWIFT", picker.parent)
    monkeypatch.setattr(register, "LOCALES", tmp_path / "bristlenose/locales")
    monkeypatch.setattr(register, "COLORS", tmp_path / "colors")
    monkeypatch.setattr(register, "ASSETS", tmp_path / "assets")

    edited = register.register("edo9")
    assert len(edited) == len(before)                       # every site took the new palette
    assert all("edo9" in p.read_text(encoding="utf-8") for p in before)
    assert register.register("edo9") == []                  # idempotent
    register.unregister("edo9")
    assert {p: p.read_text(encoding="utf-8") for p in before} == before   # byte-identical


@pytest.mark.usefixtures("node")
def test_the_guard_leaves_an_inherited_failure_alone(tmp_path: Path) -> None:
    """A base that already fails a pair on purpose (a bright accent) must not be 'fixed' by a later nudge."""
    base = palette_table.Table.from_css(_COLORS / "palette-edo.css", "edo")
    raw = {k: {"light": c.light, "dark": c.dark} for k, c in base.cells.items()}
    raw["--bn-colour-accent"]["light"] = "#4191e2"     # fails 4.5:1 on the page, deliberately
    (tmp_path / "b.json").write_text(json.dumps(raw), encoding="utf-8")
    (tmp_path / "k.json").write_text("{}", encoding="utf-8")
    (tmp_path / "o.json").write_text("{}", encoding="utf-8")
    r = subprocess.run(["node", str(_BP / "knobs.mjs"), *(str(tmp_path / n) for n in ("b.json", "k.json", "o.json"))],
                       capture_output=True, text=True, check=True)
    assert json.loads(r.stdout)["table"]["--bn-colour-accent"]["light"] == "#4191e2"
