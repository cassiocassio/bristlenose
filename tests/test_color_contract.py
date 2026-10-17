"""Validate that all palette CSS files define every token in the color contract.

The contract file (bristlenose/theme/colors/_contract.css) lists every
--bn-colour-* token that a palette must define.  This test parses the
contract comments and checks each palette-*.css file against them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_COLORS_DIR = Path(__file__).resolve().parent.parent / "bristlenose" / "theme" / "colors"
_CONTRACT_PATH = _COLORS_DIR / "_contract.css"

# Match lines like: --bn-colour-bg                  Page background
_CONTRACT_TOKEN_RE = re.compile(r"^(--bn-[\w-]+)\s+", re.MULTILINE)

# Match CSS custom property declarations: --bn-colour-bg: ...
_CSS_TOKEN_RE = re.compile(r"(--bn-[\w-]+)\s*:")


def _parse_contract_tokens() -> set[str]:
    """Extract required token names from the contract file."""
    text = _CONTRACT_PATH.read_text(encoding="utf-8")
    return set(_CONTRACT_TOKEN_RE.findall(text))


def _parse_palette_tokens(path: Path) -> set[str]:
    """Extract all token declarations from a palette CSS file."""
    text = path.read_text(encoding="utf-8")
    return set(_CSS_TOKEN_RE.findall(text))


def _parse_dark_block(path: Path) -> dict[str, str]:
    """Token → value inside the palette's @supports (light-dark) block."""
    text = path.read_text(encoding="utf-8")
    start = text.find("@supports (color: light-dark(")
    if start < 0:
        return {}
    return dict(re.findall(r"(--bn-[\w-]+)\s*:\s*([^;]+);", text[start:]))


def _palette_files() -> list[Path]:
    """List all palette-*.css files in the colors directory."""
    return sorted(_COLORS_DIR.glob("palette-*.css"))


class TestColorContract:
    """Every palette file must define all tokens listed in _contract.css."""

    def test_contract_file_exists(self) -> None:
        assert _CONTRACT_PATH.is_file(), f"Contract file not found: {_CONTRACT_PATH}"

    def test_contract_has_tokens(self) -> None:
        tokens = _parse_contract_tokens()
        assert len(tokens) >= 30, f"Contract only has {len(tokens)} tokens — seems incomplete"

    def test_at_least_two_palettes(self) -> None:
        palettes = _palette_files()
        assert len(palettes) >= 2, f"Expected >=2 palettes, found {len(palettes)}"

    @pytest.mark.parametrize(
        "palette_path",
        _palette_files(),
        ids=[p.name for p in _palette_files()],
    )
    def test_palette_defines_all_contract_tokens(self, palette_path: Path) -> None:
        contract = _parse_contract_tokens()
        defined = _parse_palette_tokens(palette_path)
        missing = contract - defined
        assert not missing, (
            f"{palette_path.name} is missing {len(missing)} contract token(s):\n"
            + "\n".join(f"  {t}" for t in sorted(missing))
        )

    @pytest.mark.parametrize(
        "palette_path",
        _palette_files(),
        ids=[p.name for p in _palette_files()],
    )
    def test_palette_has_light_and_dark(self, palette_path: Path) -> None:
        """Every palette comes in both appearances: Appearance and palette are
        independent settings, so a light-only palette would show its light
        values in dark mode. The two shadows are the same in both by design."""
        decl = _parse_dark_block(palette_path)
        same_in_both = {"--bn-focus-shadow", "--bn-overlay-shadow"}
        missing = sorted(
            t
            for t in _parse_contract_tokens() - same_in_both
            if "light-dark(" not in decl.get(t, "")
        )
        assert not missing, (
            f"{palette_path.name} has no dark value for {len(missing)} token(s):\n"
            + "\n".join(f"  {t}" for t in missing)
        )

    @pytest.mark.parametrize(
        "palette_path",
        _palette_files(),
        ids=[p.name for p in _palette_files()],
    )
    def test_light_dark_wraps_colours_only(self, palette_path: Path) -> None:
        """light-dark() takes colours. Wrapped round a whole shadow it is
        invalid, and box-shadow computes to none in both appearances (measured
        in Chromium and WebKit, 17 Oct 2026). Put it on the shadow's colour."""
        bad = sorted(
            t
            for t, v in _parse_dark_block(palette_path).items()
            if v.lstrip().startswith("light-dark(") and re.search(r"\dpx", v)
        )
        assert not bad, f"{palette_path.name}: light-dark() wraps a shadow in {bad}"

    def test_default_palette_is_root_fallback(self) -> None:
        """palette-default.css must set tokens on :root (not just [data-color-theme])."""
        default_path = _COLORS_DIR / "palette-default.css"
        text = default_path.read_text(encoding="utf-8")
        assert ":root" in text, "palette-default.css must define tokens on :root"
