#!/usr/bin/env python3
"""Prove check-bundle-budget can go red — and cannot go green on a broken build.

WHY THIS SHAPE

The gate it replaces was green on a build that shipped MORE than the budget
allowed (it excluded eagerly-loaded locale chunks) and red on one that shipped
less (it counted a chunk 8.2 had merged). So the cases that matter here are not
"does it add up" — they are the ways a bundle-size number can be small for the
wrong reason. Every one of those reads as an improvement.

    an unbuilt tree            -> 0 kB, the best score possible
    index.html with no scripts -> 0 kB again
    a reference to a file that is not there -> a smaller total, silently
    a chunk gone lazy          -> a real improvement, and must still be visible

The first three are failures wearing a green coat, and they are what this pins.

Everything runs against synthetic temp dirs. No build required, so this is
runnable on a clean checkout and in CI before the frontend exists.

Usage: .venv/bin/python scripts/test-bundle-budget.py
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import pathlib
import random
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("cbb", HERE / "check-bundle-budget.py")
cbb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cbb)

FAILURES: list[str] = []


def check(label: str, cond, detail: str = "") -> None:
    try:
        ok, why = bool(cond()), detail
    except Exception as e:  # noqa: BLE001
        ok, why = False, f"{type(e).__name__}: {e}"
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}")
    if not ok:
        FAILURES.append(f"{label}{' — ' + why if why else ''}")


def build(refs: str, files: dict[str, int], *, html: bool = True) -> pathlib.Path:
    """A synthetic static dir. `files` maps chunk name -> uncompressed size."""
    d = pathlib.Path(tempfile.mkdtemp())
    (d / "assets").mkdir()
    for name, size in files.items():
        # Genuinely incompressible bytes. The obvious `bytes(range(256)) * n`
        # is NOT: gzip eats a repeated 256-byte pattern almost entirely, so a
        # 900 kB "big" chunk compressed under a 60 kB budget and the eager-vs-
        # lazy case below passed in both directions. A size test needs data
        # whose gzipped size tracks its raw size.
        (d / "assets" / name).write_bytes(random.randbytes(size))
    if html:
        (d / "index.html").write_text(f"<!doctype html><html><head>{refs}</head></html>")
    return d


def run(static: pathlib.Path, *argv: str) -> tuple[int, str]:
    real = sys.argv
    sys.argv = ["check-bundle-budget.py", "--static", str(static), *argv]
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            code = cbb.main()
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
        buf.write(str(e.code) if not isinstance(e.code, int) else "")
    finally:
        sys.argv = real
    return code, buf.getvalue()


SCRIPT = '<script type="module" crossorigin src="/assets/main-abc.js"></script>'
PRELOAD = '<link rel="modulepreload" crossorigin href="/assets/vendor-def.js">'

print("\n\033[1mthe reference forms index.html actually emits\033[0m")
d = build(SCRIPT + PRELOAD, {"main-abc.js": 1000, "vendor-def.js": 1000})
check("both <script src> and <link modulepreload href> are counted",
      lambda: len(cbb.eager_chunks(d / "index.html")) == 2)
d2 = build('<script src="./assets/a.js"></script><script src="assets/b.js"></script>',
           {"a.js": 100, "b.js": 100})
check("relative and bare paths too (./assets/ and assets/)",
      lambda: len(cbb.eager_chunks(d2 / "index.html")) == 2,
      "vite emits /assets/; a base-path change would emit the others")

print("\n\033[1mthe ways a bundle number goes small for the wrong reason\033[0m")
d = build("", {}, html=False)
code, out = run(d)
check("an UNBUILT tree is an error, not a 0 kB pass", lambda: code != 0, f"exit {code}")
check("...and it says how to build", lambda: "npm run build" in out, out.strip()[:80])

d = build("<p>no scripts here</p>", {"orphan.js": 5000})
code, out = run(d)
check("index.html with NO js refs is an error, not a 0 kB pass",
      lambda: code != 0, f"exit {code}")

d = build(SCRIPT + PRELOAD, {"main-abc.js": 1000})   # vendor-def.js never written
code, out = run(d)
check("a reference to a MISSING chunk is red, not a smaller total",
      lambda: code == 1, f"exit {code}")
check("...and it names the missing file",
      lambda: "vendor-def.js" in out,
      "otherwise a half-written build reads as an improvement")

print("\n\033[1mthe budget itself\033[0m")
d = build(SCRIPT, {"main-abc.js": 400_000})
code, out = run(d, "--budget", "1000")
check("over budget -> exit 1", lambda: code == 1, f"exit {code}")
check("...and it says by how much", lambda: "OVER BUDGET by" in out)
check("...and it warns about the lazy->eager case first",
      lambda: "become eagerly referenced" in out,
      "the likeliest cause of a jump, and not fixed by raising the number")

# 500k, not 400k: gzip on incompressible input is slightly LARGER than the
# input, so a budget equal to the raw size is already exceeded.
code, out = run(d, "--budget", "500000")
check("under budget -> exit 0", lambda: code == 0, f"exit {code}")
check("...and it reports headroom", lambda: "headroom" in out)

print("\n\033[1mlazy chunks are out, and going lazy is visible\033[0m")
eager_only = build(SCRIPT, {"main-abc.js": 2000, "LazyRoute-xyz.js": 900_000})
code, out = run(eager_only, "--budget", "1000000")
check("a chunk on disk but NOT referenced is not counted",
      lambda: "LazyRoute" not in out,
      "this is the whole locale-split argument; it must hold by construction")
big = build(SCRIPT + '<link rel="modulepreload" href="/assets/LazyRoute-xyz.js">',
            {"main-abc.js": 2000, "LazyRoute-xyz.js": 900_000})
c1, _ = run(eager_only, "--budget", "60000")
c2, _ = run(big, "--budget", "60000")
check("the same chunk turning EAGER flips the verdict",
      lambda: c1 == 0 and c2 == 1,
      f"lazy exit {c1}, eager exit {c2} — the regression the old gate could not see")

print("\n\033[1mit measures bytes, not names\033[0m")
a = build(SCRIPT, {"main-abc.js": 50_000})
b = build('<script src="/assets/wildly-renamed-999.js"></script>',
          {"wildly-renamed-999.js": 50_000})
check("renaming every chunk does not move the number",
      lambda: sum(n for n, _ in cbb.measure(a)[0]) == sum(n for n, _ in cbb.measure(b)[0]),
      "the property the 22-negation allow-list did not have")

print()
if FAILURES:
    print(f"\033[31m{len(FAILURES)} case(s) failed\033[0m", file=sys.stderr)
    for f in FAILURES:
        print(f"  - {f}", file=sys.stderr)
    raise SystemExit(1)
print("\033[32mall cases passed\033[0m — the budget can go red, and cannot go green "
      "on an unbuilt, empty, or half-written tree")
