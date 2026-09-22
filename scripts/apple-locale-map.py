#!/usr/bin/env python3
"""Resolve our locale codes to Apple's, by probing the .loctable corpus.

Why this exists
---------------
An i18n pass cross-checks our wording against Apple's own translations in
``/System/Library/{Frameworks,PrivateFrameworks}/**/*.loctable``.  That needs a
map from our codes to Apple's, and Apple's differ: ``nb``->``no``,
``pt-BR``->``pt_BR``, ``zh-Hant``->``zh_TW``.

The map used to live in prose, and prose is not recomputed.  ``pt-BR``->``pt``
was written down, was wrong, and could not fail: bare ``pt`` is a *real* Apple
code (Brazilian Portuguese in the legacy spelling) carrying 454 tables to
``pt_BR``'s 2,589, and the two never co-occur in one file.  So the lookup
succeeded, found nothing for the key, and the audit concluded "Apple ships no
translation here" for strings Apple does ship.

Existence is therefore NOT the test.  Three of our codes -- ``nb``,
``zh-Hant``, ``pt-PT`` -- exist verbatim as Apple codes holding ~75 keys each,
against ~211,000 for the correct alias.  A resolver that merely checked "does a
table with this name exist?" would bless all three and keep missing everything.
The test is COVERAGE: a candidate must carry a serious share of the corpus.

Usage
-----
    scripts/apple-locale-map.py --write      # regenerate the checked-in map
    scripts/apple-locale-map.py --check      # verify the map against the corpus
    scripts/apple-locale-map.py              # print the census and resolution
"""

from __future__ import annotations

import argparse
import json
import pathlib
import plistlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
MAP_PATH = REPO / "scripts" / "apple-locale-map.json"

SEARCH_ROOTS = (
    pathlib.Path("/System/Library/Frameworks"),
    pathlib.Path("/System/Library/PrivateFrameworks"),
)

# A candidate must carry at least this share of the best-covered locale's key
# count to be believed.  The decoys sit at ~0.04%; every real locale sits above
# 24%.  The gap is three orders of magnitude, so the threshold is not delicate.
COVERAGE_FLOOR = 0.10

# We never lift English from Apple: we ship British spellings where Apple ships
# American ones.  Kept in the map so the corpus is fully classified, and marked
# so the cross-check skips it.
NEVER_LIFT = {"en"}


def our_locales() -> list[str]:
    """The locale codes we ship, read from the Python SSOT."""
    sys.path.insert(0, str(REPO))
    from bristlenose.i18n import SUPPORTED_LOCALES

    return list(SUPPORTED_LOCALES)


def loctables() -> list[pathlib.Path]:
    """Every distinct .loctable.

    Deliberately does not follow symlinks.  A framework's Resources directory is
    reachable as both ``Foo.framework/Resources`` and
    ``Foo.framework/Versions/A/Resources``, so ``find -L`` reports 10,448 files
    where 3,275 distinct ones exist -- a 3.19x inflation that makes every
    absolute count wrong while leaving the ratios intact.
    """
    out: list[pathlib.Path] = []
    for root in SEARCH_ROOTS:
        if root.is_dir():
            out.extend(root.rglob("*.loctable"))
    return out


def census(files: list[pathlib.Path]) -> dict[str, dict[str, int]]:
    """Apple code -> {tables, keys} across the corpus."""
    tables: dict[str, int] = {}
    keys: dict[str, int] = {}
    for f in files:
        try:
            with open(f, "rb") as fh:
                data = plistlib.load(fh)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        for code, table in data.items():
            if not isinstance(table, dict):
                continue
            tables[code] = tables.get(code, 0) + 1
            keys[code] = keys.get(code, 0) + len(table)
    return {c: {"tables": tables[c], "keys": keys[c]} for c in tables}


def candidates(ours: str) -> list[str]:
    """Apple spellings that might carry our locale, best guess first.

    Generated mechanically rather than listed, so a new language proposes its
    own candidates.  Resolution is still decided by measured coverage.
    """
    out = [ours, ours.replace("-", "_")]
    if "-" in ours:
        lang, _, region = ours.partition("-")
        # zh-Hant is a script, not a region; Apple spells its scripts as the
        # territory where that script is the norm.
        out += {"Hant": ["zh_TW"], "Hans": ["zh_CN"], "Hant-HK": ["zh_HK"]}.get(region, [])
        out += [f"{lang}_{region.upper()}", lang]
    # Apple keeps Norwegian under the macrolanguage code.
    out += {"nb": ["no"], "nn": ["no"]}.get(ours, [])
    seen: set[str] = set()
    return [c for c in out if not (c in seen or seen.add(c))]


def resolve(ours: str, cen: dict[str, dict[str, int]], best: int) -> dict:
    """Pick the Apple code for one of our locales, or record why we could not."""
    tried = []
    for cand in candidates(ours):
        got = cen.get(cand)
        share = (got["keys"] / best) if got else 0.0
        tried.append({"code": cand, "keys": got["keys"] if got else 0, "share": round(share, 4)})
        if got and share >= COVERAGE_FLOOR:
            return {
                "apple": cand,
                "tables": got["tables"],
                "keys": got["keys"],
                "share": round(share, 4),
                "rejected": tried[:-1],
            }
    return {"apple": None, "rejected": tried}


def build() -> dict:
    files = loctables()
    if not files:
        raise SystemExit(
            "no .loctable files found under /System/Library -- this probe only "
            "runs on macOS. The checked-in map is the artefact for other platforms."
        )
    cen = census(files)
    best = max(v["keys"] for v in cen.values())
    resolved = {ours: resolve(ours, cen, best) for ours in our_locales()}
    return {
        "_comment": (
            "GENERATED by scripts/apple-locale-map.py -- do not hand-edit. "
            "Maps our locale codes to Apple's .loctable codes for translation "
            "cross-checks. Regenerate with --write, verify with --check."
        ),
        "corpus": {"distinct_loctables": len(files), "best_locale_keys": best},
        "coverage_floor": COVERAGE_FLOOR,
        "never_lift": sorted(NEVER_LIFT),
        "map": {k: v["apple"] for k, v in resolved.items()},
        "evidence": resolved,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="regenerate the checked-in map")
    ap.add_argument("--check", action="store_true", help="verify the map against the corpus")
    args = ap.parse_args()

    built = build()
    unresolved = [k for k, v in built["map"].items() if v is None]

    if args.check:
        if not MAP_PATH.exists():
            print(f"FAIL: {MAP_PATH} missing -- run --write", file=sys.stderr)
            return 1
        stored = json.loads(MAP_PATH.read_text())
        if stored["map"] != built["map"]:
            print("FAIL: checked-in map disagrees with the corpus", file=sys.stderr)
            for k in sorted(set(stored["map"]) | set(built["map"])):
                if stored["map"].get(k) != built["map"].get(k):
                    print(f"  {k}: stored={stored['map'].get(k)} measured={built['map'].get(k)}", file=sys.stderr)
            return 1
        print(f"ok: {len(built['map'])} locales resolve as recorded")
        return 1 if unresolved else 0

    if args.write:
        MAP_PATH.write_text(json.dumps(built, indent=2, ensure_ascii=True) + "\n")
        print(f"wrote {MAP_PATH.relative_to(REPO)}")

    width = max(len(k) for k in built["map"])
    print(f"\ncorpus: {built['corpus']['distinct_loctables']} distinct loctables\n")
    print(f"{'ours':<{width}}  {'apple':<10}{'tables':>8}{'keys':>9}  rejected")
    for ours, ev in built["evidence"].items():
        rej = ", ".join(f"{r['code']}({r['keys']})" for r in ev.get("rejected", [])) or "-"
        if ev["apple"] is None:
            print(f"{ours:<{width}}  {'** NONE **':<10}{'':>8}{'':>9}  {rej}")
        else:
            note = "  [never lifted]" if ours in NEVER_LIFT else ""
            print(f"{ours:<{width}}  {ev['apple']:<10}{ev['tables']:>8}{ev['keys']:>9}  {rej}{note}")

    if unresolved:
        print(f"\nUNRESOLVED: {', '.join(unresolved)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
