#!/usr/bin/env python3
"""Derive the zh-Hant-HK thin override from zh-Hant via a TW→HK term table.

zh-Hant-HK (Hong Kong) ships ONLY the keys whose Hong Kong wording differs from
the Taiwan base (zh-Hant). Everything else resolves through the fallback chain
zh-Hant-HK → zh-Hant → en, which is wired in all three surfaces:
  - i18next  `fallbackLng` map        (frontend/src/i18n/index.ts)
  - Python   `_FALLBACK_CHAINS`       (bristlenose/i18n.py)
  - Swift    `fallbackBase`           (desktop/.../I18n.swift)

Both variants are Traditional Chinese — there is NO script conversion, only a
small set of HK-vs-TW lexical swaps, so the override is cheap. This is a MACHINE
SEED: the HK wording is UNREVIEWED until a Hong Kong reviewer signs off. The term
table is deliberately small and high-confidence; the reviewer expands it.

Re-runnable: regenerates bristlenose/locales/zh-Hant-HK/*.json from zh-Hant.
"""

from __future__ import annotations

import json
from pathlib import Path

_LOCALES = Path(__file__).resolve().parent.parent / "bristlenose" / "locales"
_BASE = "zh-Hant"
_TARGET = "zh-Hant-HK"

# Taiwan → Hong Kong Traditional Chinese term substitutions. Software register,
# high-confidence only. Both sides are Traditional (no 繁↔簡 conversion).
# UNREVIEWED scaffold — a Hong Kong reviewer expands and corrects this table.
_TW_TO_HK: dict[str, str] = {
    "軟體": "軟件",  # software
    "網路": "網絡",  # network
    "解析度": "解像度",  # resolution
    "論壇": "討論區",  # forum
    "筆記型電腦": "手提電腦",  # laptop
    "品質": "質素",  # quality
    "資訊": "資訊",  # information (same — placeholder for reviewer)
}


def _substitute(text: str) -> str:
    for tw, hk in _TW_TO_HK.items():
        text = text.replace(tw, hk)
    return text


def _derive(obj: object) -> object | None:
    """Return only the leaves whose value changed under substitution, preserving
    nesting. None means nothing changed in this subtree (so it is omitted)."""
    if isinstance(obj, dict):
        out: dict[str, object] = {}
        for key, value in obj.items():
            sub = _derive(value)
            if sub is not None:
                out[key] = sub
        return out or None
    if isinstance(obj, str):
        hk = _substitute(obj)
        return hk if hk != obj else None
    return None


def _count_leaves(obj: object) -> int:
    if isinstance(obj, dict):
        return sum(_count_leaves(v) for v in obj.values())
    return 1


def main() -> int:
    base_dir = _LOCALES / _BASE
    target_dir = _LOCALES / _TARGET
    target_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    for path in sorted(base_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        overrides = _derive(data)
        out_path = target_dir / path.name
        if overrides:
            out_path.write_text(
                json.dumps(overrides, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            written += 1
            print(f"  {path.name}: {_count_leaves(overrides)} override(s)")
        elif out_path.exists():
            out_path.unlink()  # no HK delta — fallback chain serves zh-Hant

    print(f"wrote {written} override file(s) to {target_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
