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


@pytest.mark.parametrize("path", sorted(_COLORS.glob("palette-*.css")), ids=lambda p: p.stem)
def test_shipped_palette_round_trips(path: Path, tmp_path: Path) -> None:
    key = path.stem.removeprefix("palette-")
    first = palette_table.Table.from_css(path, key)
    assert len(first.cells) >= 45
    out = tmp_path / path.name
    out.write_text(first.to_css(key), encoding="utf-8")
    assert first.diff(palette_table.Table.from_css(out, key)) == []


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_neutral_knobs_leave_the_palette_alone(tmp_path: Path) -> None:
    base = palette_table.Table.from_css(_COLORS / "palette-edo.css", "edo")
    (tmp_path / "b.json").write_text(
        json.dumps({k: {"light": c.light, "dark": c.dark} for k, c in base.cells.items()}))
    (tmp_path / "k.json").write_text("{}")
    r = subprocess.run(["node", str(_BP / "knobs.mjs"), str(tmp_path / "b.json"), str(tmp_path / "k.json")],
                       capture_output=True, text=True, check=True)
    out = json.loads(r.stdout)["table"]
    moved = [
        k for k, c in base.cells.items() for m in ("light", "dark")
        if out[k][m].replace("0.10", "0.1") != getattr(c, m).replace("0.10", "0.1")
    ]
    assert moved == []


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_a_single_token_override_beats_the_sliders(tmp_path: Path) -> None:
    base = palette_table.Table.from_css(_COLORS / "palette-edo.css", "edo")
    (tmp_path / "b.json").write_text(
        json.dumps({k: {"light": c.light, "dark": c.dark} for k, c in base.cells.items()}))
    (tmp_path / "k.json").write_text(json.dumps({"dark": {"paperHue": 120, "accentChroma": 1.5}}))
    (tmp_path / "o.json").write_text(json.dumps({"--bn-colour-accent": {"dark": "#123456"}}))
    r = subprocess.run(
        ["node", str(_BP / "knobs.mjs"), *(str(tmp_path / n) for n in ("b.json", "k.json", "o.json"))],
        capture_output=True, text=True, check=True)
    out = json.loads(r.stdout)["table"]
    assert out["--bn-colour-accent"]["dark"] == "#123456"          # the override, not the nudged accent
    assert out["--bn-colour-accent"]["light"] == base.cells["--bn-colour-accent"].light  # other mode untouched
    assert out["--bn-colour-bg"]["dark"] != base.cells["--bn-colour-bg"].dark  # the sliders still moved the rest
