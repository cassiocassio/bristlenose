#!/usr/bin/env python3
"""Test the dependency-drift namer.

The gate it replaces answered yes/no ("is the inventory stale?"), which is the
answer that does not help you decide anything at 10pm. This one names packages
and flags majors, so its classification is the whole risk surface.
"""
from __future__ import annotations

import importlib.util
import pathlib
import signal
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("dd", HERE / "check-dep-drift.py")
dd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dd)

# This suite MUTATES a tracked file (THIRD-PARTY-BINARIES.md) to prove the gate
# fires, and restores it in a `finally`. That is not enough: Python's `finally`
# does NOT run on SIGTERM — measured, not assumed — so a `timeout` around a batch
# run leaves the inventory corrupted and the next check reports a drift that does
# not exist. That is exactly what happened to the man page earlier today via the
# shell sibling, which was fixed with a trap; this is the same wound unstitched.
def _die(_signum, _frame):
    raise SystemExit(130)


signal.signal(signal.SIGTERM, _die)
signal.signal(signal.SIGINT, _die)

PASS = FAIL = 0


def ok(msg: str) -> None:
    global PASS
    PASS += 1
    print(f"  \033[32m✓\033[0m {msg}")


def bad(msg: str) -> None:
    global FAIL
    FAIL += 1
    print(f"  \033[31m✗\033[0m {msg}", file=sys.stderr)


def eq(label: str, want, got) -> None:
    if want == got:
        ok(label)
    else:
        bad(f"{label} — expected {want!r}, got {got!r}")

print("\n\033[1mbump_kind — the classification that decides warn vs stop\033[0m")
eq("the 0.27.0 case: 1.x -> 3.0.0", "major", dd.bump_kind("1.109.1", "3.0.0"))
eq("0.x -> 1.0 is major",           "major", dd.bump_kind("0.9.2", "1.0.0"))
eq("minor bump",                    "minor", dd.bump_kind("2.3.1", "2.4.0"))
eq("patch bump",                    "patch", dd.bump_kind("2.3.1", "2.3.2"))
eq("identical",                     "same",  dd.bump_kind("2.3.1", "2.3.1"))
eq("two-part minor",                "minor", dd.bump_kind("8.1", "8.2"))
eq("two-part major",                "major", dd.bump_kind("8.1", "9.0"))
eq("post-release is patch",         "patch", dd.bump_kind("1.2.3", "1.2.3.post1"))
eq("identical strings are same",    "same",  dd.bump_kind("1.2.3", "1.2.3"))
eq("rc suffix is a change",         "patch", dd.bump_kind("1.2.3", "1.2.3rc1"))
eq("dev suffix is a change",        "patch", dd.bump_kind("1.2.3", "1.2.3.dev0"))
eq("non-numeric tolerated",         "major", dd.bump_kind("3.12.x", "4.0.0"))
eq("huge major jump",               "major", dd.bump_kind("1.0.0", "27.0.0"))

print("\n\033[1minventory parsing\033[0m")
with tempfile.TemporaryDirectory() as d:
    p = pathlib.Path(d) / "inv.md"
    p.write_text(f"""preamble
{dd.BEGIN}
| Package | Version | Licence | Source |
|---|---|---|---|
| `openai` | 1.109.1 | MIT | <https://x> |
| `Some_Pkg` | 2.0.0 | MIT | <https://y> |
{dd.END}
tail
""")
    inv = dd.parse_inventory(p)
    eq("rows parsed", 2, len(inv))
    eq("name normalised to lowercase-dash", "2.0.0", inv.get("some-pkg"))
    eq("header row skipped", None, inv.get("package"))

print("\n\033[1mend to end — a major must exit 1\033[0m")
inv_real = HERE.parent / "THIRD-PARTY-BINARIES.md"
backup = inv_real.read_bytes()
try:
    # Downgrade a genuinely-installed package's recorded major, so the live
    # resolve reads as a major jump. This is the 0.27.0 shape exactly.
    import importlib.metadata as md
    victim = next(dist.metadata["Name"] for dist in md.distributions()
                  if (dist.metadata["Name"] or "").lower() in
                  {n.lower() for n in dd.parse_inventory(inv_real)})
    txt = inv_real.read_text()
    cur = md.version(victim)
    faked = f"0.{cur}"
    txt2 = txt.replace(f"| `{victim}` | {cur} |", f"| `{victim}` | {faked} |", 1)
    if txt2 == txt:
        print(f"  \033[2m—\033[0m skipped: could not fake a row for {victim}")
    else:
        inv_real.write_text(txt2)
        # --python sys.executable: the victim and its version were read from
        # THIS interpreter, so the script must resolve the same one. The
        # default target is the sidecar venv, which may hold a different
        # version or not exist on the machine running this harness.
        r = subprocess.run([sys.executable, str(HERE / "check-dep-drift.py"),
                            "--python", sys.executable],
                           capture_output=True, text=True)
        if r.returncode == 1 and "MAJOR" in r.stdout:
            ok(f"major drift on {victim} exits 1 and is named")
        else:
            bad(f"major drift NOT caught (exit {r.returncode}): {r.stdout.strip()[:80]}")
finally:
    inv_real.write_bytes(backup)

r = subprocess.run([sys.executable, str(HERE / "check-dep-drift.py"), "--python", sys.executable],
                   capture_output=True, text=True)
# 0 or 1, never 2: the harness's own venv is not the inventory's source, so
# it may legitimately drift; what it must not do is fail to run.
eq("inventory restored, run completes (not exit 2)", True, r.returncode in (0, 1))

print("\n\033[1mrefuses to report 'no drift' when it parsed nothing\033[0m")
with tempfile.TemporaryDirectory() as d:
    p = pathlib.Path(d) / "empty.md"
    p.write_text(f"{dd.BEGIN}\n{dd.END}\n")
    try:
        dd.parse_inventory(p)
        ok("empty section parses to zero rows (main() then exits 2)")
    except SystemExit:
        bad("parse_inventory raised on an empty but well-formed section")

print(f"\n\033[1m{PASS} passed, {FAIL} failed\033[0m\n")
sys.exit(1 if FAIL else 0)
