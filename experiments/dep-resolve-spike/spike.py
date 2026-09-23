#!/usr/bin/env python3
"""Spike: which dependency-resolution design survives which release scenario?

WHY

Five releases in a row have failed or nearly failed on one thing: the
committed supply-chain inventory disagreeing with the closure the release
actually built. 0.31.2 hit it TWICE in one release, ten minutes apart, on
different packages — so the window is not "rare", it is "any gap at all".

Rather than implement a fix and find the edge cases in production at 3am, this
models the release as a timeline, manufactures every failure mode we have seen
or can think of, and scores candidate designs against all of them.

WHAT IT MODELS

  index      what PyPI would serve right now (package -> version)
  resolve()  what a `pip install --no-cache-dir` would produce at that instant
  steps      preflight, bump, build-all, build-dmg, tag
  designs    strategies for WHEN to resolve and WHAT to record
  scenarios  scripted mutations of the index (and of the world) between steps

WHAT IT SCORES  — the ranking is deliberate, worst first:

  SILENT_WRONG  shipped an inventory that does not describe what shipped,
                or two channels carrying different closures, with nothing
                failing. The house defect: a check that reports success while
                seeing nothing.
  CAUGHT        something failed loudly. Costs a retry; costs no trust.
  OK            first time, correct.

A design with fewer SILENT_WRONG always beats one with fewer CAUGHT.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Callable

STEPS = ["preflight", "bump", "build-all", "build-dmg", "tag"]


class Yanked(Exception):
    """The lane asked for a pinned version that PyPI no longer serves."""


class Unreachable(Exception):
    """The index could not be reached for this resolve."""


@dataclass
class World:
    """Everything a resolve depends on, and everything a scenario can break."""

    index: dict[str, str] = field(default_factory=lambda: {"httpx": "2.13.0", "starlette": "1.6.0"})
    # PyInstaller `excludes` / `collect_*`: what the FREEZE drops from the venv.
    # The inventory is generated from the venv and never from the bundle, so
    # this gap is invisible to every design here. Review found it; the spike
    # could not. CLAUDE.md records a real instance — presidio_analyzer's
    # dist-info in _internal/ with no package directory (5 Sep 2026).
    spec_excludes: set[str] = field(default_factory=set)
    reachable: bool = True
    venv: dict[str, str] | None = None          # the sidecar venv's closure
    venv_valid: bool = True                     # False = deleted / half-installed
    pyproject_rev: int = 0                      # bumped when constraints change
    venv_pyproject_rev: int = 0                 # what the venv was built against
    yanked: set[tuple[str, str]] = field(default_factory=set)

    def resolve(self) -> dict[str, str]:
        if not self.reachable:
            raise Unreachable("index unreachable")
        self.venv = dict(self.index)
        self.venv_valid = True
        self.venv_pyproject_rev = self.pyproject_rev
        return dict(self.venv)

    def install_from_lock(self, lock: dict[str, str]) -> dict[str, str]:
        if not self.reachable:
            raise Unreachable("index unreachable")
        for pkg, ver in lock.items():
            if (pkg, ver) in self.yanked:
                raise Yanked(f"{pkg}=={ver} was yanked")
        self.venv = dict(lock)
        self.venv_valid = True
        self.venv_pyproject_rev = self.pyproject_rev
        return dict(self.venv)

    def venv_is_usable(self) -> bool:
        return self.venv_valid and self.venv is not None and self.venv_pyproject_rev == self.pyproject_rev


@dataclass
class Outcome:
    verdict: str          # OK | CAUGHT | SILENT_WRONG
    detail: str


@dataclass
class Design:
    name: str
    blurb: str
    run: Callable[[World, dict], Outcome]


def _finish(world: World, inventory: dict | None, pkg: dict | None, dmg: dict | None) -> Outcome:
    """The three questions that decide whether a release was honest."""
    if inventory is None or pkg is None or dmg is None:
        return Outcome("CAUGHT_LATE", "a step refused; nothing shipped")
    if pkg != dmg:
        return Outcome("SILENT_WRONG", f"channels differ: pkg={_s(pkg)} dmg={_s(dmg)}")
    # What SHIPS is the frozen bundle, not the venv the inventory was read from.
    # Review found this; no design in this spike could, because they all measure
    # a resolve. CLAUDE.md records a real instance: presidio_analyzer's
    # dist-info in _internal/ with no package directory (5 Sep 2026).
    shipped = {k: v for k, v in pkg.items() if k not in world.spec_excludes}
    if inventory != shipped:
        return Outcome("SILENT_WRONG", f"inventory {_s(inventory)} != bundle {_s(shipped)}")
    return Outcome("OK", "inventory describes what both channels carry")


def _s(d: dict[str, str]) -> str:
    return ",".join(f"{k}{v}" for k, v in sorted(d.items()))


# ---------------------------------------------------------------------------
# The designs
# ---------------------------------------------------------------------------
# Each returns (inventory, pkg_closure, dmg_closure); None anywhere = refused.
# `hooks` maps a step name to a callable the scenario uses to mutate the world
# AFTER that step runs.


def _tick(world: World, hooks: dict, step: str) -> None:
    for fn in hooks.get(step, []):
        fn(world)


def design_today(world: World, hooks: dict) -> Outcome:
    """0.31.0 and earlier: preflight READS the venv; both lanes re-resolve.

    The four-occurrence baseline. Preflight cannot see drift the release itself
    causes, because it measures a venv the release is about to throw away.
    """
    inventory = dict(world.venv) if world.venv else {}      # committed as-is
    _tick(world, hooks, "preflight")
    _tick(world, hooks, "bump")
    try:
        pkg = world.resolve()
    except (Unreachable, Yanked) as e:
        return Outcome("CAUGHT_LATE", f"build-all: {e}")
    if pkg != inventory:
        return Outcome("CAUGHT_LATE", "build-all refused — after bump, push and dispatch")
    _tick(world, hooks, "build-all")
    try:
        dmg = world.resolve()
    except (Unreachable, Yanked) as e:
        return Outcome("CAUGHT_LATE", f"build-dmg: {e}")
    _tick(world, hooks, "build-dmg")
    # build-dmg runs NO inventory check today — measured, build-all.sh:396 only.
    return _finish(world, inventory, pkg, dmg)


def _preflight_resolve(world: World, committed: dict):
    """Resolve live and compare to the COMMITTED file — the shipped behaviour.

    Returns the inventory to use, or an Outcome if preflight refused. Refusing
    here is the cheap failure: nothing has been bumped, pushed or dispatched,
    so the fix is a regenerate and a re-run of one 3-minute step.
    """
    try:
        live = world.resolve()
    except (Unreachable, Yanked) as e:
        return Outcome("CAUGHT_EARLY", f"preflight: {e}")
    if live != committed:
        return Outcome("CAUGHT_EARLY", "preflight refused — regenerate, before the bump")
    return live


def design_shipped(world: World, hooks: dict) -> Outcome:
    """What I shipped this morning: preflight RESOLVES, then checks. Lanes still force.

    Moves discovery before the bump. Does not stop the lanes disagreeing.
    """
    committed = dict(world.venv or {})
    got = _preflight_resolve(world, committed)
    if isinstance(got, Outcome):
        return got
    inventory = got
    _tick(world, hooks, "preflight")
    _tick(world, hooks, "bump")
    try:
        pkg = world.resolve()
    except (Unreachable, Yanked) as e:
        return Outcome("CAUGHT_LATE", f"build-all: {e}")
    if pkg != inventory:
        return Outcome("CAUGHT_LATE", "build-all refused — after bump, push and dispatch")
    _tick(world, hooks, "build-all")
    try:
        dmg = world.resolve()
    except (Unreachable, Yanked) as e:
        return Outcome("CAUGHT_LATE", f"build-dmg: {e}")
    _tick(world, hooks, "build-dmg")
    return _finish(world, inventory, pkg, dmg)


def design_reuse(world: World, hooks: dict) -> Outcome:
    """Design A — preflight resolves; the lanes REUSE the venv instead of forcing.

    One resolve per release. The lanes still rebuild the frontend and the
    freeze; only layer V is skipped, gated on the existing deps fingerprint.
    """
    committed = dict(world.venv or {})
    got = _preflight_resolve(world, committed)
    if isinstance(got, Outcome):
        return got
    inventory = got
    _tick(world, hooks, "preflight")
    _tick(world, hooks, "bump")

    def reuse_or_resolve(stage: str):
        # The V gate: reuse when the venv is intact AND still matches pyproject.
        if world.venv_is_usable():
            return dict(world.venv)
        # Fingerprint says stale -> falls back to a live re-resolve. SILENTLY,
        # which is the whole risk of this design.
        return world.resolve()

    try:
        pkg = reuse_or_resolve("build-all")
    except (Unreachable, Yanked) as e:
        return Outcome("CAUGHT_LATE", f"build-all: {e}")
    if pkg != inventory:
        return Outcome("CAUGHT_LATE", "build-all refused — after bump, push and dispatch")
    _tick(world, hooks, "build-all")
    try:
        dmg = reuse_or_resolve("build-dmg")
    except (Unreachable, Yanked) as e:
        return Outcome("CAUGHT_LATE", f"build-dmg: {e}")
    _tick(world, hooks, "build-dmg")
    return _finish(world, inventory, pkg, dmg)


def design_lock(world: World, hooks: dict) -> Outcome:
    """Design B — preflight resolves ONCE and writes a per-release lock;
    both lanes install from the lock, and each verifies what it got.

    Not a permanent lockfile (project policy is floor-only): the lock lives in
    the run dir and dies with the release. Its job is that the two channels and
    the inventory are the same closure BY CONSTRUCTION rather than by gate.
    """
    committed = dict(world.venv or {})
    got = _preflight_resolve(world, committed)
    if isinstance(got, Outcome):
        return got
    lock = got
    inventory = dict(lock)
    _tick(world, hooks, "preflight")
    _tick(world, hooks, "bump")

    def install(stage: str):
        got = world.install_from_lock(lock)
        if got != lock:                      # belt and braces; cannot happen today
            raise Yanked(f"{stage}: install did not match the lock")
        return got

    try:
        pkg = install("build-all")
    except (Unreachable, Yanked) as e:
        return Outcome("CAUGHT_LATE", f"build-all: {e}")
    _tick(world, hooks, "build-all")
    try:
        dmg = install("build-dmg")
    except (Unreachable, Yanked) as e:
        return Outcome("CAUGHT_LATE", f"build-dmg: {e}")
    _tick(world, hooks, "build-dmg")
    return _finish(world, inventory, pkg, dmg)


def _with_dmg_check(inner):
    """Wrap a design so build-dmg ALSO checks its closure against the inventory.

    Today only build-all does (build-all.sh:396). The spike's whole S2 family
    exists because of that asymmetry, so this isolates what the missing check
    is worth on its own, independently of which resolve strategy wins.
    """

    def run(world: World, hooks: dict) -> Outcome:
        out = inner(world, hooks)
        # ONLY what a venv-reading check can actually see. The real check is
        # `generate-third-party-binaries.py --check`, which inventories the
        # SIDECAR VENV — so it catches a lane whose closure moved, and is blind
        # by construction to anything the FREEZE then drops (S16). An earlier
        # draft converted every SILENT_WRONG here and recommended this design
        # on the strength of a catch it cannot perform; review called it, and
        # it was the same post-hoc-rewrite shape the house defect always takes.
        if out.verdict == "SILENT_WRONG" and "channels differ" in out.detail:
            return Outcome("CAUGHT_LATE", "build-dmg's inventory check refused")
        return out

    return run


DESIGNS = [
    Design("today", "preflight reads the venv; both lanes re-resolve", design_today),
    Design("today+dmg", "today, plus the missing build-dmg inventory check",
           _with_dmg_check(design_today)),
    Design("A+dmg", "reuse, plus the missing build-dmg inventory check",
           _with_dmg_check(design_reuse)),
    Design("shipped", "preflight resolves + checks; lanes still force", design_shipped),
    Design("A reuse", "preflight resolves; lanes reuse via the fingerprint gate", design_reuse),
    Design("B lock", "preflight resolves once; lanes install from a per-release lock", design_lock),
]


# ---------------------------------------------------------------------------
# The scenarios — SEEN ones are dated; the rest are manufactured
# ---------------------------------------------------------------------------
def pub(pkg: str, ver: str):
    def go(w: World) -> None:
        w.index[pkg] = ver
    return go


def add_pkg(pkg: str, ver: str):
    return pub(pkg, ver)


def drop_pkg(pkg: str):
    def go(w: World) -> None:
        w.index.pop(pkg, None)
    return go


def yank(pkg: str, ver: str):
    def go(w: World) -> None:
        w.yanked.add((pkg, ver))
        w.index[pkg] = ver.rsplit(".", 1)[0] + ".99"   # a replacement exists
    return go


def unreachable(w: World) -> None:
    w.reachable = False


def kill_venv(w: World) -> None:
    w.venv_valid = False


def edit_pyproject(w: World) -> None:
    w.pyproject_rev += 1


SCENARIOS: list[tuple[str, dict, str]] = [
    ("clean run — nothing publishes", {}, "the control: every design must pass"),

    ("S1 patch publishes between preflight and build-all",
     {"bump": [pub("httpx", "2.13.1")]},
     "SEEN 23 Sep 2026, 0.31.2 attempt 2 — httpx2+httpcore2 in a 4-minute gap"),

    ("S2 patch publishes between build-all and build-dmg",
     {"build-all": [pub("httpx", "2.13.1")]},
     "the .dmg ships a closure NOTHING checks: build-dmg has no inventory gate"),

    ("S3 major publishes before build-all",
     {"bump": [pub("starlette", "2.0.0")]},
     "SEEN 0.27.0 #5 — openai >=1.50 resolved to 3.0.0 mid-release"),

    ("S4 a NEW transitive appears in the closure",
     {"bump": [add_pkg("anyio", "4.15.1")]},
     "a package nobody added shows up; licence review owes an opinion"),

    ("S5 a package LEAVES the closure",
     {"bump": [drop_pkg("starlette")]},
     "an upstream drops a dep; the inventory keeps describing it"),

    ("S6 the resolved version is YANKED before the lane installs",
     {"bump": [yank("httpx", "2.13.0")]},
     "only bites a design that PINS; a re-resolve just takes the replacement"),

    ("S7 pyproject edited between preflight and build-all",
     {"bump": [edit_pyproject]},
     "a concurrent session moves a floor; does the design notice?"),

    ("S8 the sidecar venv is destroyed after preflight",
     {"bump": [kill_venv]},
     "half-install, robust_rmrf crash, or a human deleting it"),

    ("S9 the index is unreachable at build time",
     {"bump": [unreachable]},
     "PyPI 503 / no network on the build host"),

    ("S10 publishes in BOTH gaps",
     {"bump": [pub("httpx", "2.13.1")], "build-all": [pub("starlette", "1.7.0")]},
     "SEEN in spirit 23 Sep — two drifts inside one release"),

    ("S11 a publish lands between build-dmg and the tag",
     {"build-dmg": [pub("httpx", "2.99.0")]},
     "nothing has re-resolved; must be a no-op for every design"),

    ("S0 a package published since the LAST release",
     {"start": [pub("starlette", "1.7.0")]},
     "SEEN 23 Sep, 0.31.2 attempt 1 — the case --resolve was built for"),

    ("S16 the freeze DROPS a package the inventory lists",
     {"start": [lambda w: w.spec_excludes.add("starlette")]},
     "review found what the spike could not: the inventory is read from the "
     "VENV, never from the bundle. CLAUDE.md records presidio_analyzer's "
     "dist-info shipping with no package directory"),

    # --- the cases that exist ONLY to break the design I like best ----------
    # A reuse scored 12/12 on the first pass, which is the tell that the
    # scenarios were written by the same head that liked the design. Its one
    # weakness is structural: when its fingerprint says "stale" it falls back
    # to a LIVE re-resolve, silently — and build-dmg has no inventory check to
    # catch the result. So aim squarely at that.

    ("S12 venv dies between the lanes AND a publish lands",
     {"build-all": [kill_venv, pub("httpx", "2.13.1")]},
     "A re-resolves at build-dmg, where NOTHING checks the closure"),

    ("S13 pyproject edited between the lanes AND a publish lands",
     {"build-all": [edit_pyproject, pub("httpx", "2.13.1")]},
     "same hole, reached by a concurrent session instead of a crash"),

    ("S14 venv dies before build-all AND a publish lands",
     {"bump": [kill_venv, pub("httpx", "2.13.1")]},
     "the same fallback, but build-all DOES check — so this must be caught"),

    ("S15 unreachable at build-dmg after the venv died",
     {"build-all": [kill_venv, unreachable]},
     "cannot answer; must refuse rather than ship a guess"),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
RANK = {"SILENT_WRONG": 0, "CAUGHT_LATE": 1, "CAUGHT_EARLY": 2, "OK": 3}
MARK = {"SILENT_WRONG": "!!", "CAUGHT_LATE": " ~", "CAUGHT_EARLY": " -", "OK": " ."}


def run_one(design: Design, hooks: dict) -> Outcome:
    world = World()
    world.venv = dict(world.index)        # a venv resolved at some earlier time
    # "start" = what changed since the LAST release, i.e. before anyone typed
    # a version. Without this the model cannot express the case the 23 Sep
    # change was built for, and it scored `shipped` identically to `today`.
    for fn in hooks.get("start", []):
        fn(world)
    try:
        return design.run(world, hooks)
    except Exception as e:                # a design that blows up is a design that fails
        return Outcome("CAUGHT_LATE", f"raised {type(e).__name__}: {e}")


def main() -> int:
    width = max(len(d.name) for d in DESIGNS) + 2
    print("\nDEPENDENCY-RESOLUTION SPIKE — which design survives which scenario\n")
    print("  !! shipped a lie   ~ refused LATE (after bump+push)   - refused EARLY (preflight)   . first time\n")
    header = " " * 52 + "".join(f"{d.name:>{width}}" for d in DESIGNS)
    print(header)
    print(" " * 52 + "".join(f"{'-' * (width - 1):>{width}}" for _ in DESIGNS))

    tally = {d.name: {"OK": 0, "CAUGHT_EARLY": 0, "CAUGHT_LATE": 0, "SILENT_WRONG": 0} for d in DESIGNS}
    details: list[str] = []
    for title, hooks, why in SCENARIOS:
        row = f"  {title[:48]:<50}"
        for d in DESIGNS:
            out = run_one(d, {k: list(v) for k, v in hooks.items()})
            tally[d.name][out.verdict] += 1
            row += f"{MARK[out.verdict]:>{width}}"
            if out.verdict != "OK":
                details.append(f"    {d.name:<9} {title[:44]:<46} {out.detail}")
        print(row)
        details.append(f"    {'':9} └ {why}")

    print("\n  TALLY (worst first: a silent wrong beats any number of loud failures)\n")
    print(f"    {'design':<11} {'silent-wrong':>13} {'late':>6} {'early':>6} {'first-time':>11}   verdict")
    ordered = sorted(
        DESIGNS,
        key=lambda d: (tally[d.name]["SILENT_WRONG"], tally[d.name]["CAUGHT_LATE"],
                       tally[d.name]["CAUGHT_EARLY"], -tally[d.name]["OK"]),
    )
    for d in ordered:
        t = tally[d.name]
        verdict = (
            "UNSAFE — ships lies" if t["SILENT_WRONG"]
            else "safe, costly" if t["CAUGHT_LATE"] > 3
            else "safe"
        )
        print(f"    {d.name:<11} {t['SILENT_WRONG']:>13} {t['CAUGHT_LATE']:>6} "
              f"{t['CAUGHT_EARLY']:>6} {t['OK']:>11}   {verdict}")

    print("\n  WHY EACH NON-OK CELL\n")
    for line in details:
        print(line)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
