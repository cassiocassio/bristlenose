"""A palette as a table: token -> (light, dark), read from and written to the shipped CSS.

The shipped palette files are the source of truth for what the app does, so the
workbench starts from them (`Table.from_css`) rather than from a second copy of the
colours. An iteration is a table with some cells changed; `to_css` writes it back in the
same two-block layout every palette uses (plain light values, then a `light-dark()` block).

A token whose value is the same in both appearances (the shadows) is held as one value.
A token with a `light-dark()` pair inside a longer value (the focus ring) is split by
textual substitution, so any CSS value shape round-trips.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

TOKEN = re.compile(r"(--bn-[\w-]+)\s*:\s*((?:[^;/]|/(?!\*))*?)\s*;(?:[ \t]*/\*\s*(.*?)\s*\*/)?", re.S)


def _split_ld(value: str) -> tuple[str, str]:
    """Replace every light-dark(a, b) in `value` by a (light) or by b (dark)."""
    out = {"light": [], "dark": []}
    i = 0
    while True:
        j = value.find("light-dark(", i)
        if j < 0:
            for k in out:
                out[k].append(value[i:])
            break
        for k in out:
            out[k].append(value[i:j])
        depth, k2, args, cur = 0, j + len("light-dark("), [], []
        s = k2
        while True:
            c = value[k2]
            if c == "(":
                depth += 1
            elif c == ")":
                if depth == 0:
                    args.append(value[s:k2].strip())
                    break
                depth -= 1
            elif c == "," and depth == 0:
                args.append(value[s:k2].strip())
                s = k2 + 1
            k2 += 1
        out["light"].append(args[0])
        out["dark"].append(args[1])
        i = k2 + 1
    return "".join(out["light"]), "".join(out["dark"])


@dataclass
class Cell:
    light: str
    dark: str
    note: str = ""


@dataclass
class Table:
    cells: dict[str, Cell] = field(default_factory=dict)
    header: str = ""
    key: str = ""

    # ── reading ──
    @classmethod
    def from_css(cls, path: Path, key: str | None = None) -> Table:
        text = path.read_text(encoding="utf-8")
        head = text[: text.index("*/") + 2] if text.lstrip().startswith("/*") else ""
        sup = text.find("@supports (color: light-dark(")
        base_text = text[len(head): sup if sup >= 0 else len(text)]
        sup_text = text[sup:] if sup >= 0 else ""
        t = cls(header=head, key=key or path.stem.removeprefix("palette-"))
        for name, val, note in TOKEN.findall(base_text):
            t.cells[name] = Cell(val.strip(), val.strip(), note)
        for name, val, note in TOKEN.findall(sup_text):
            lo, da = _split_ld(val.strip())
            old = t.cells.get(name)
            t.cells[name] = Cell(lo, da, note or (old.note if old else ""))
        return t

    # ── editing (every call returns a new table; iterations never mutate their base) ──
    def copy(self) -> Table:
        return Table({k: Cell(c.light, c.dark, c.note) for k, c in self.cells.items()}, self.header, self.key)

    def set(self, token: str, light: str | None = None, dark: str | None = None, note: str | None = None) -> Table:
        if token not in self.cells:
            raise KeyError(f"{token} is not in the palette (typo, or a new token: add it to _contract.css first)")
        c = self.cells[token]
        if light is not None:
            c.light = light
        if dark is not None:
            c.dark = dark
        if note is not None:
            c.note = note
        return self

    def both(self, token: str, value: str) -> Table:
        return self.set(token, value, value)

    # ── comparing ──
    def diff(self, other: Table) -> list[tuple[str, Cell | None, Cell | None]]:
        rows = []
        for k in sorted(set(self.cells) | set(other.cells)):
            a, b = self.cells.get(k), other.cells.get(k)
            if a is None or b is None or (a.light, a.dark) != (b.light, b.dark):
                rows.append((k, a, b))
        return rows

    # ── writing ──
    def to_css(self, key: str | None = None, header: str | None = None) -> str:
        key = key or self.key
        sel = f'[data-color-theme="{key}"]'
        out = [(header if header is not None else self.header).rstrip() + "\n", f"{sel} {{"]
        for name, c in self.cells.items():
            out.append(f"    {name}: {c.light};" + (f"  /* {c.note} */" if c.note else ""))
        out += ["}", "", "@supports (color: light-dark(#000, #fff)) {", f"    {sel} {{"]
        for name, c in self.cells.items():
            if c.light != c.dark:
                out.append(f"        {(name + ':').ljust(32)}{_join_ld(c.light, c.dark)};")
        out += ["    }", "}", ""]
        return "\n".join(out)


def _join_ld(light: str, dark: str) -> str:
    """light-dark(a, b), or per-part when both sides share the same wrapper
    (`0 0 0 2px rgba(..)` / `0 0 0 2px rgba(..)` -> `0 0 0 2px light-dark(rgba(..), rgba(..))`)."""
    if light.startswith("0 0 0 ") and dark.startswith("0 0 0 "):
        lp, lt = light.split(" rgba", 1)
        dp, dt = dark.split(" rgba", 1)
        if lp == dp:
            return f"{lp} light-dark(rgba{lt}, rgba{dt})"
    return f"light-dark({light}, {dark})"


# ── colour maths, shared by iterations and the lab ──
def rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def hexc(c) -> str:
    return "#" + "".join(f"{max(0, min(255, round(v))):02x}" for v in c)


def mix(a: str, b: str, t: float) -> str:
    """t of a into b."""
    ra, rb = rgb(a), rgb(b)
    return hexc(tuple(ra[i] * t + rb[i] * (1 - t) for i in range(3)))


def lum(h: str) -> float:
    def ch(v: float) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def is_hex(v: str) -> bool:
    return bool(re.fullmatch(r"#[0-9a-fA-F]{6}", v))
