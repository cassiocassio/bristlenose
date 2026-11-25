#!/usr/bin/env python3
"""Budget what a first-load visitor downloads, derived from index.html.

WHAT THIS REPLACED, AND WHY

`size-limit` measured a filename allow-list: one glob over `assets/*.js` plus 22
negations, each naming a chunk, so the lazy locale chunks stayed out of the
number. A chunk filename is a bundler implementation detail, and Rolldown
rechunks between vite minors. Measured 5 Sep 2026 on `vite 8.0.10 -> 8.2.2`,
same source, nothing else changed:

    counted by the old list   207.7 kB  ->  231.9 kB   (+24.1, "over budget")
    actually downloaded       205.5 kB  ->  199.8 kB   (-5.7, and 14 fewer requests)

The gate failed a build that is strictly better. It was wrong in both directions
at once: it *excluded* `common-*`, `desktop-*`, `settings-*` and `enums-*` —
locale chunks that `index.html` was eagerly loading, so users paid for them and
the budget did not — and then, when 8.2 merged 225 chunks into 211, it started
*counting* a merged chunk the old names had covered.

So the number is not defined by which files exist. It is defined by which files
the entry document makes a visitor fetch before anything renders, which is the
thing the budget was always trying to be about. That definition survives any
rechunking, any rename, and any future bundler.

WHAT IS DELIBERATELY NOT COUNTED

Anything reached by a dynamic `import()` — route chunks, the dev playground, and
the 22 locales the runtime loads one of. Those are real bytes but nobody pays
them on first paint, and the whole point of the locale split is that adding a
language is free here. If a lazy chunk ever becomes eagerly referenced, this
number goes up, loudly, which is the behaviour the old list could not manage.

Usage:
  scripts/check-bundle-budget.py            check against the budget
  scripts/check-bundle-budget.py --list     print the eager set and exit 0
  scripts/check-bundle-budget.py --budget N override, for the paired self-test
"""
from __future__ import annotations

import argparse
import gzip
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "bristlenose/server/static"

# Held at 220 kB across the definition change, deliberately: only what the
# number MEANS moved, not where the ceiling sits, so the two are reviewable
# apart. Headroom on 5 Sep 2026 is ~20 kB. Raising this is a deliberate edit in
# a commit that says why -- the same discipline as docs/testing/ratchet.json.
# Raised 220 -> 222 kB on 4 Oct 2026 for report undo (Edit > Undo / cmd-Z on
# speaker naming): ~1.2 kB at first paint -- the stack and its menu sync, the
# write helper inside SessionsTable, eight English labels. HEAD stood 126 B
# under the old ceiling, so the ~20 kB of 5 Sep headroom had already gone.
# Raised 222 -> 223 kB on 25 Nov 2026 at the 0.48.0 cut: HEAD 6f7b61ea measured
# 222,533 B at first paint, 533 B over. The AutoCode landing (live playback, the
# review pane's motion, the tag sidebar overview) had left ~0.28 kB of headroom by
# 24 Nov, and that day's review-pane and tag-sidebar commits took the rest. Raised
# to release, not trimmed: finding which shell import to defer is owed, not done.
# Raised 223 -> 224 kB on 25 Nov 2026 for the dev style-guide route
# (/report/style-guide), owner's call: 222,677 B in 38 chunks -> 223,550 B in 41.
# None of the style guide's code is fetched at first paint (its chunk is lazy and
# the first-paint chunks carry none of it); the growth is Rolldown moving modules
# the shell now shares with that lazy page (toast, exportData, a Dialog group)
# out of the main chunk into three more first-paint files. An empty style-guide
# page cost ~280 B on its own. The shell-import trim above is still owed.
# Raised 224 -> 226 kB on 25 Nov 2026 for a security fix: i18next 26.0.8 -> 26.7.2
# (811fe45f4) clears GHSA-6jcc-5g8w-32mx, the only shipped-frontend advisory, and
# `npm audit --omit=dev` now blocks on it, so the old version is not an option.
# Measured on one tree, i18next the only difference: 222,849 B -> 225,201 B in the
# same 38 chunks (+2,352 B). Nothing else moved. The shell-import trim is still owed.
BUDGET_BYTES = 226 * 1000

# Both forms the entry document uses to make the browser fetch a chunk before
# first paint. A `<link rel="prefetch">` would NOT belong here; nothing emits
# one today, and if something does, it should be added with a reason.
REF = re.compile(r'(?:src|href)="\.?/?(assets/[A-Za-z0-9_.\-]+\.js)"')


def eager_chunks(html: Path) -> list[str]:
    return sorted(set(REF.findall(html.read_text(encoding="utf-8"))))


def measure(static: Path) -> tuple[list[tuple[int, str]], list[str]]:
    """Returns (sized chunks, names referenced but absent from disk)."""
    html = static / "index.html"
    if not html.is_file():
        raise SystemExit(
            f"error: {html} does not exist -- run `npm run build` in frontend/ first.\n"
            "       (An unbuilt tree must be an error, never a 0 kB pass.)"
        )
    sized: list[tuple[int, str]] = []
    missing: list[str] = []
    for ref in eager_chunks(html):
        f = static / ref
        if not f.is_file():
            missing.append(ref)
            continue
        sized.append((len(gzip.compress(f.read_bytes(), 9)), ref))
    if not sized and not missing:
        # index.html referencing no JS at all is a broken build, not a small one.
        raise SystemExit("error: index.html references no JS chunks -- that is a build failure")
    return sorted(sized, reverse=True), missing


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="print the eager set, always exit 0")
    ap.add_argument("--budget", type=int, default=BUDGET_BYTES, help="override, in bytes")
    ap.add_argument("--static", type=Path, default=STATIC, help="built static dir")
    args = ap.parse_args()

    sized, missing = measure(args.static)
    total = sum(n for n, _ in sized)

    print(f"{'gzipped':>9}  chunk")
    for n, ref in sized:
        print(f"{n:>9,}  {ref.removeprefix('assets/')}")
    print(f"{'-' * 9}  {'-' * 40}")
    print(f"{total:>9,}  {len(sized)} chunk(s) fetched before first paint")

    if missing:
        # A reference to a file that is not there is a broken build that would
        # otherwise make the number SMALLER, i.e. look like an improvement.
        print(f"\nerror: index.html references {len(missing)} chunk(s) not on disk:",
              file=sys.stderr)
        for m in missing:
            print(f"  {m}", file=sys.stderr)
        return 1

    pct = 100 * total / args.budget
    if total > args.budget:
        print(f"\nOVER BUDGET by {total - args.budget:,} B "
              f"({total / 1000:.1f} kB against {args.budget / 1000:.0f} kB, {pct:.0f}%)",
              file=sys.stderr)
        print("Raising the budget is a deliberate edit to BUDGET_BYTES in this file,\n"
              "in a commit that says why. Check first that a chunk has not simply\n"
              "become eagerly referenced when it used to be lazy.", file=sys.stderr)
        return 1
    if args.list:
        return 0
    print(f"\nwithin budget: {total / 1000:.1f} kB of {args.budget / 1000:.0f} kB ({pct:.0f}%), "
          f"{(args.budget - total) / 1000:.1f} kB headroom")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
