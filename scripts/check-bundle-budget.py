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
BUDGET_BYTES = 220 * 1000

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
