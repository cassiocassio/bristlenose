#!/usr/bin/env python3
"""Validate locale files for completeness, consistency, and correctness.

Checks:
1. All locale JSON files are valid JSON
2. Every key in English exists in all other locales (warns for missing)
3. No orphan keys in non-English locales (keys English doesn't have)
4. No empty string values
5. Interpolation placeholders ({{ var }}) in English exist in translations

Exit code 0: all checks pass (warnings are OK)
Exit code 1: errors found (invalid JSON, orphan keys, placeholder mismatch)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

LOCALES_DIR = Path(__file__).resolve().parent.parent / "bristlenose" / "locales"
SOURCE_LANG = "en"
PLACEHOLDER_RE = re.compile(r"\{\{.*?\}\}")


def flatten(obj: dict, prefix: str = "") -> dict[str, str]:
    """Flatten nested JSON into dotted keys."""
    result: dict[str, str] = {}
    for key, value in obj.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.update(flatten(value, full_key))
        else:
            result[full_key] = str(value)
    return result


def load_locale(lang: str, namespace: str) -> dict[str, str] | None:
    """Load and flatten a locale file. Returns None if file doesn't exist."""
    path = LOCALES_DIR / lang / f"{namespace}.json"
    if not path.exists():
        return None
    try:
        with open(path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return e  # type: ignore[return-value]
    return flatten(data)


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    # Discover languages and namespaces
    en_dir = LOCALES_DIR / SOURCE_LANG
    if not en_dir.is_dir():
        print(f"ERROR: English locale directory not found: {en_dir}")
        return 1

    namespaces = sorted(p.stem for p in en_dir.glob("*.json"))
    languages = sorted(
        d.name
        for d in LOCALES_DIR.iterdir()
        if d.is_dir() and d.name != SOURCE_LANG and not d.name.startswith(".")
    )

    print(f"Source: {SOURCE_LANG}")
    print(f"Languages: {', '.join(languages)}")
    print(f"Namespaces: {', '.join(namespaces)}")
    print()

    for ns in namespaces:
        en_keys = load_locale(SOURCE_LANG, ns)
        if en_keys is None:
            errors.append(f"{SOURCE_LANG}/{ns}.json: file not found")
            continue
        if isinstance(en_keys, json.JSONDecodeError):
            errors.append(f"{SOURCE_LANG}/{ns}.json: invalid JSON — {en_keys}")
            continue

        for lang in languages:
            tr_keys = load_locale(lang, ns)

            if tr_keys is None:
                warnings.append(f"{lang}/{ns}.json: file not found (skipping)")
                continue

            if isinstance(tr_keys, json.JSONDecodeError):
                errors.append(f"{lang}/{ns}.json: invalid JSON — {tr_keys}")
                continue

            # Check for missing keys (warn)
            missing = set(en_keys) - set(tr_keys)
            if missing:
                warnings.append(
                    f"{lang}/{ns}.json: {len(missing)} missing key(s): "
                    + ", ".join(sorted(missing)[:5])
                    + ("..." if len(missing) > 5 else "")
                )

            # Check for orphan keys (warn — some are legitimate, e.g. _short
            # variants that only exist in languages where the full label overflows)
            orphans = set(tr_keys) - set(en_keys)
            if orphans:
                warnings.append(
                    f"{lang}/{ns}.json: {len(orphans)} orphan key(s): "
                    + ", ".join(sorted(orphans)[:5])
                    + ("..." if len(orphans) > 5 else "")
                )

            # Check for empty values (warn)
            empty = [k for k in tr_keys if tr_keys[k].strip() == ""]
            if empty:
                warnings.append(
                    f"{lang}/{ns}.json: {len(empty)} empty value(s): "
                    + ", ".join(sorted(empty)[:5])
                    + ("..." if len(empty) > 5 else "")
                )

            # Check interpolation placeholders (error) — skip empty stubs
            for key in set(en_keys) & set(tr_keys):
                if tr_keys[key].strip() == "":
                    continue  # empty stub — Weblate will fill it
                en_placeholders = set(PLACEHOLDER_RE.findall(en_keys[key]))
                tr_placeholders = set(PLACEHOLDER_RE.findall(tr_keys[key]))
                if en_placeholders != tr_placeholders:
                    errors.append(
                        f"{lang}/{ns}.json: placeholder mismatch in '{key}': "
                        f"en={en_placeholders} vs {lang}={tr_placeholders}"
                    )

    # Report
    if warnings:
        print(f"WARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"  ⚠  {w}")
        print()

    if errors:
        print(f"ERRORS ({len(errors)}):")
        for e in errors:
            print(f"  ✗  {e}")
        print()
        print("FAILED")
        return 1

    print("✓ All locale checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
