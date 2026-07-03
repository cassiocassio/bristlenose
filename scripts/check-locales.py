#!/usr/bin/env python3
"""Validate locale files for completeness, consistency, and correctness.

Checks:
1. All locale JSON files are valid JSON
2. Every key in English exists in each locale — accounting for two things the
   runtime does at lookup time, so the report reflects what users actually see:
     - Fallback chains: a thin-override locale (e.g. ``zh-Hant-HK``) borrows
       missing keys from its base (``zh-Hant``) before English, so a key present
       in the base is NOT a gap. Mirrors i18next ``fallbackLng`` / Python
       ``_FALLBACK_CHAINS`` / Swift ``fallbackBase``.
     - CLDR plurals: single-form locales (ja/ko/zh) legitimately omit ``_one`` /
       ``_few`` / … and keep only ``_other``, so a missing plural-suffix key is
       not a genuine gap. (Multi-form plural completeness for the diagnostic
       namespace is enforced separately by
       ``tests/test_pipeline_diagnostic_locale_keys.py``.)
3. No orphan keys in non-English locales (keys English doesn't have)
4. No empty string values
5. Interpolation placeholders ({{ var }}) in English exist in translations

A *genuine* missing key — non-plural and not covered by a fallback base — renders
English silently. It is a WARNING by default and an ERROR under ``--strict``.
Placeholder mismatch and invalid JSON are always errors.

Exit code 0: all checks pass (warnings are OK unless --strict)
Exit code 1: errors found
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

LOCALES_DIR = Path(__file__).resolve().parent.parent / "bristlenose" / "locales"
SOURCE_LANG = "en"
PLACEHOLDER_RE = re.compile(r"\{\{.*?\}\}")

# Mirror of the runtime fallback chains. A locale here borrows missing keys from
# its base before English; keep in lockstep with i18next/Python/Swift.
FALLBACK_BASE = {"zh-Hant-HK": "zh-Hant"}

# Locales whose CLDR `one` category recurs at 21/31/101 (rule n%10==1 ∧ n%100!=11).
# A count-driven `_one` in these MUST interpolate {{count}} — hardcoding "1" would
# render "1 …" for count 21. Polish is deliberately NOT here (pl `one` = n==1 only,
# so its `_one` may hardcode "1" like English). See design-i18n.md § pl/ru/uk plurals.
RECURRING_ONE_LOCALES = {"ru", "uk"}

# CLDR plural-form suffixes. ``_other`` is the base form (always required); the
# rest are conditional on the locale's plural rules, so a single-form locale
# (ja/ko/zh) legitimately omits them.
PLURAL_SUFFIXES = ("_one", "_two", "_few", "_many", "_zero")


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


def load_locale(lang: str, namespace: str):
    """Load and flatten a locale file. None if missing; the error if invalid."""
    path = LOCALES_DIR / lang / f"{namespace}.json"
    if not path.exists():
        return None
    try:
        with open(path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return e
    return flatten(data)


def _is_plural_suffix(key: str) -> bool:
    return key.endswith(PLURAL_SUFFIXES)


# All CLDR plural-form suffixes including ``_other`` — used to group a plural
# base for placeholder comparison (distinct from ``_is_plural_suffix``, which
# excludes ``_other`` for missing-key leniency).
_PLURAL_FORM_SUFFIXES = ("_one", "_two", "_few", "_many", "_zero", "_other")


def _plural_base(key: str):
    """Return the base of a plural key (``quotes_one`` → ``quotes``), else None."""
    for suffix in _PLURAL_FORM_SUFFIXES:
        if key.endswith(suffix):
            return key[: -len(suffix)]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Bristlenose locale files.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat genuine (non-plural, non-fallback-covered) missing keys as errors",
    )
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

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

    genuine_total = 0

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
                # A fallback locale legitimately ships only some namespaces.
                if lang in FALLBACK_BASE:
                    continue
                warnings.append(f"{lang}/{ns}.json: file not found (skipping)")
                continue

            if isinstance(tr_keys, json.JSONDecodeError):
                errors.append(f"{lang}/{ns}.json: invalid JSON — {tr_keys}")
                continue

            # Effective coverage = the locale's own keys plus its fallback base's.
            effective = set(tr_keys)
            base = FALLBACK_BASE.get(lang)
            if base:
                base_keys = load_locale(base, ns)
                if isinstance(base_keys, dict):
                    effective |= set(base_keys)

            missing = set(en_keys) - effective
            genuine = sorted(k for k in missing if not _is_plural_suffix(k))
            # Plural-suffix misses are informational: single-form locales omit
            # them legitimately, and multi-form completeness is tested elsewhere.

            if genuine:
                genuine_total += len(genuine)
                warnings.append(
                    f"{lang}/{ns}.json: {len(genuine)} genuine missing key(s): "
                    + ", ".join(genuine[:5])
                    + ("..." if len(genuine) > 5 else "")
                )

            # Orphan keys (warn — some are legitimate, e.g. `_short` overflow
            # variants that only exist where the full label is too long).
            orphans = set(tr_keys) - set(en_keys)
            # CLDR plural enrichment is NOT an orphan: a four-form locale
            # (pl/ru/uk) legitimately adds `_few`/`_many` to a base en carries
            # only as `_one`/`_other`. Don't flag those.
            en_plural_bases = {
                _plural_base(k) for k in en_keys if _plural_base(k) is not None
            }
            orphans = {o for o in orphans if _plural_base(o) not in en_plural_bases}
            if orphans:
                warnings.append(
                    f"{lang}/{ns}.json: {len(orphans)} orphan key(s): "
                    + ", ".join(sorted(orphans)[:5])
                    + ("..." if len(orphans) > 5 else "")
                )

            # Empty values (warn)
            empty = [k for k in tr_keys if tr_keys[k].strip() == ""]
            if empty:
                warnings.append(
                    f"{lang}/{ns}.json: {len(empty)} empty value(s): "
                    + ", ".join(sorted(empty)[:5])
                    + ("..." if len(empty) > 5 else "")
                )

            # Interpolation placeholders (error) — skip empty stubs.
            # Plural forms are compared against the en GROUP's placeholder union,
            # not the same-suffix en key: en's `_one` often hardcodes "1" (no
            # {{count}}) while `_other` carries {{count}}, and a locale whose
            # `one` category recurs (ru/uk) correctly puts {{count}} in `_one`.
            # So for plural forms we forbid only UNKNOWN placeholders (must be a
            # subset of the group union); non-plural keys keep strict equality.
            en_group_ph: dict[str, set] = {}
            for k, v in en_keys.items():
                b = _plural_base(k)
                if b is not None:
                    en_group_ph.setdefault(b, set()).update(PLACEHOLDER_RE.findall(v))
            for key in set(en_keys) & set(tr_keys):
                if tr_keys[key].strip() == "":
                    continue  # empty stub — Weblate will fill it
                tr_placeholders = set(PLACEHOLDER_RE.findall(tr_keys[key]))
                base = _plural_base(key)
                if base is not None:
                    unknown = tr_placeholders - en_group_ph.get(base, set())
                    if unknown:
                        errors.append(
                            f"{lang}/{ns}.json: unknown placeholder(s) {unknown} in "
                            f"plural key '{key}' (not in the en '{base}_*' group)"
                        )
                    continue
                en_placeholders = set(PLACEHOLDER_RE.findall(en_keys[key]))
                if en_placeholders != tr_placeholders:
                    errors.append(
                        f"{lang}/{ns}.json: placeholder mismatch in '{key}': "
                        f"en={en_placeholders} vs {lang}={tr_placeholders}"
                    )

            # Recurring-`one` locales (ru/uk): a count-driven `_one` must
            # interpolate {{count}} — the `one` category recurs at 21/31/101, so
            # a hardcoded "1" renders wrong (e.g. "1 …" for count 21). Error.
            if lang in RECURRING_ONE_LOCALES:
                for key in tr_keys:
                    if not key.endswith("_other"):
                        continue
                    one_key = f"{key[:-len('_other')]}_one"
                    if one_key not in tr_keys:
                        continue
                    if "{{count}}" in tr_keys[key] and "{{count}}" not in tr_keys[one_key]:
                        errors.append(
                            f"{lang}/{ns}.json: '{one_key}' must interpolate "
                            "{{count}} — in ru/uk the `one` form recurs at 21/31/101, "
                            "so a hardcoded number renders wrong for those counts."
                        )

    if args.strict and genuine_total:
        errors.append(
            f"{genuine_total} genuine missing key(s) across locales (--strict). "
            "Each renders English silently — seed the key or give the locale a "
            "fallback base."
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
