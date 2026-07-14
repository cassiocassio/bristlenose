#!/usr/bin/env python3
"""Static mock of a best-in-class build-all.sh report, rendered with Rich.

PROTOTYPE ONLY — canned data, to design the output style. Nothing here
touches the real build-all.sh yet.

Data provenance (2026-07-14 build):
  REAL   — bundle id, signing identity, team, .pkg size (223,281,163 B),
           220 signed Mach-O binaries, gate results, app-store→notarise skip,
           and the failure case (dev-literal leak caught at step 7 — the bug
           this build's step-7 fix actually closed).
  REPRES — per-step durations for opaque subprocesses (sidecar / archive /
           export) are representative; a wired version shows live elapsed +
           a learned ETA (Welford, bristlenose/timing.py).

Run:
  python3 build_report_mock.py               # animated success (real terminal)
  python3 build_report_mock.py --frame       # static success frame
  python3 build_report_mock.py --fail        # static failure frame
  python3 build_report_mock.py --svg a.svg [--fail]   # colour SVG of a frame
"""
from __future__ import annotations

import sys
import textwrap
import time
from dataclasses import dataclass, field
from enum import Enum

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

WIDTH = 92
IND = "        "   # content indent, under the glyph column

# ── house glyph vocabulary (mirrors bristlenose/ui_kinds.py) ──────────────
GLYPH = {"ok": "✓", "info": "ℹ", "warn": "⚠", "fail": "✗", "skip": "—", "run": "○"}
STYLE = {"ok": "green", "info": "blue", "warn": "yellow", "fail": "red",
         "skip": "dim", "run": "cyan"}


class St(str, Enum):
    OK = "ok"
    INFO = "info"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"
    RUN = "run"


# ── schema: three section types ───────────────────────────────────────────
@dataclass
class Check:
    """A leaf gate under a step: {label, result, evidence}."""
    label: str
    result: St
    evidence: str = ""


@dataclass
class Step:
    """A phase row: {tag, phase, name, status, elapsed, …}."""
    tag: str                     # script index, kept for log grepping: [5], [2a]
    phase: str
    name: str
    status: St
    elapsed: float | None = None
    detail: str = ""             # short evidence, shown on the indented line
    narrative: str = ""          # one-liner for a first-time contributor
    checks: list[Check] = field(default_factory=list)
    bar: tuple[int, int] | None = None       # (done, total) determinate work
    log_tail: list[str] = field(default_factory=list)   # shown on failure


@dataclass
class Gate:
    """Final readiness battery row: {id, desc, result, evidence}."""
    id: str
    desc: str
    result: St
    evidence: str


# ── the real build, as data ───────────────────────────────────────────────
IDENTITY = "Apple Distribution: Martin Storey (Z56GZVA2QB)"
TEAM = "Z56GZVA2QB"
BUNDLE = "app.bristlenose"
PKG_BYTES = 223_281_163

STEPS = [
    Step("1", "Pre-flight", "Pre-flight", St.OK, 1.8,
         narrative="Fails fast before any expensive work — identities, profiles, hygiene.",
         checks=[
             Check("logging hygiene", St.OK, "no credential-shaped log calls"),
             Check("bundle manifest", St.OK, "every runtime dir covered by spec"),
             Check("signing identity", St.OK, "found in keychain"),
             Check("provisioning profile", St.OK, "Bristlenose Mac App Store"),
         ]),
    Step("2", "Build", "Sidecar — fetch · build · sign", St.OK, 281.0,
         detail="220 binaries signed", bar=(220, 220),
         narrative="Freezes the Python engine (PyInstaller), bundles FFmpeg, and signs "
                   "every Mach-O under your identity."),
    Step("2a", "Build", "Bundle self-test", St.OK, 2.4,
         detail="doctor --self-test: all runtime data present in bundle"),
    Step("2b", "Build", "Supply-chain inventory", St.OK, 0.9,
         detail="THIRD-PARTY-BINARIES.md fresh"),
    Step("5", "Build", "Xcode archive", St.OK, 118.0,
         detail="Release · manual-signed · Bristlenose.xcarchive",
         narrative="Compiles + signs the native app shell. Opaque subprocess — live "
                   "elapsed here; full stream in xcodebuild-archive.log."),
    Step("6", "Package", "Export → .pkg", St.OK, 125.0,
         detail="Bristlenose.pkg · 213 MB",
         narrative="Wraps the signed app in an App Store installer "
                   "(method=app-store-connect)."),
    Step("7", "Verify", "Release-binary scan", St.OK, 3.1,
         detail="no BRISTLENOSE_DEV_* literals · no get-task-allow"),
    Step("8", "Verify", "Provisioning profile", St.OK, 0.5,
         detail=f"{TEAM}.{BUNDLE} / {TEAM}"),
    Step("9", "Verify", "Notarisation", St.SKIP, None,
         detail="method=app-store-connect",
         narrative="App Store Connect validates server-side after upload — local "
                   "notarisation is neither needed nor accepted for this method."),
]

GATES = [
    Gate("a", "Notarisation staple", St.SKIP, "App Store validates server-side"),
    Gate("b", "Installer signature", St.OK, "signed, trusted for current user"),
    Gate("c", "Code signature", St.OK, "--deep --strict valid"),
    Gate("d", "get-task-allow", St.OK, "absent (debug entitlement)"),
    Gate("d2", "Hardened Runtime", St.OK, "flags=0x10000(runtime)"),
    Gate("e", "Designated requirement", St.OK, f"references Team {TEAM}"),
    Gate("f", "Privacy manifests", St.OK, "host + sidecar present, lint-clean"),
]

# The failure this build actually hit before the step-7 fix landed.
FAIL_STEP_TAG = "7"
FAIL_TAIL = [
    "scanning 3 Mach-O binaries in Bristlenose.app …",
    "Contents/MacOS/Bristlenose:",
    "  ✗ dev escape-hatch literal: BRISTLENOSE_DEV_UNSAFE_SKIP_SANDBOX",
    "error: 1 disallowed string in a shipping binary (App Store would reject)",
]


# ── rendering helpers ──────────────────────────────────────────────────────
def fmt_elapsed(s: float | None) -> str:
    if s is None:
        return ""
    return f"{s:.1f}s" if s < 60 else f"{int(s // 60)}m {int(s % 60):02d}s"


def leader_line(n: int, status: St, name: str, tag: str, right: str) -> Text:
    """`n  glyph  NAME · · · · · · · · · · · [tag]  elapsed` — airy leader."""
    line = Text()
    line.append(f"{n:>3}  ", style="dim")
    line.append(GLYPH[status.value] + "  ", style=STYLE[status.value])
    line.append(name, style="bold" if status not in (St.SKIP,) else "dim")
    tail = Text.assemble((f"[{tag}]", "dim"), ("  ", ""), (right, "dim"))
    fill = max(1, WIDTH - line.cell_len - tail.cell_len - 2)
    leader = "".join("·" if k % 2 == 0 else " " for k in range(fill))
    line.append(" " + leader + " ", style="dim")
    line.append(tail)
    return line


def phase_header(console: Console, phase: str, count: int) -> None:
    label = Text()
    label.append(f"  {phase.upper()}  ", style="bold cyan")
    label.append(f"· {count} step{'s' if count != 1 else ''}", style="dim")
    console.print()
    console.print(label)


def emit_step(console: Console, n: int, st: Step, failing: bool = False) -> None:
    status = St.FAIL if failing else st.status
    right = ("FAILED" if failing else fmt_elapsed(st.elapsed)
             or ("skipped" if status == St.SKIP else ""))
    console.print(leader_line(n, status, st.name, st.tag, right))

    if failing:
        for i, ln in enumerate(st.log_tail):
            edge = "└" if i == len(st.log_tail) - 1 else "│"
            sty = "red" if ln.lstrip().startswith(("✗", "error")) else "dim"
            console.print(Text(f"      {edge} ", style="dim") + Text(ln, style=sty))
        return

    if st.detail and not st.bar:
        console.print(Text(IND + st.detail, style="dim"))
    if st.bar:
        done, total = st.bar
        gt = Table.grid()
        gt.add_column(no_wrap=True)
        gt.add_column(no_wrap=True)
        gt.add_column(no_wrap=True)
        gt.add_row(Text(IND[:-1]),
                   ProgressBar(total=total, completed=done, width=32,
                               complete_style="green", finished_style="green"),
                   Text(f"  {done}/{total}  {st.detail}", style="dim"))
        console.print(gt)
    if st.narrative:
        for wl in textwrap.wrap(st.narrative, width=WIDTH - len(IND)):
            console.print(Text(IND + wl, style="dim italic"))
    for c in st.checks:
        row = Text(IND)
        row.append(GLYPH[c.result.value] + " ", style=STYLE[c.result.value])
        row.append(c.label.ljust(22), style="dim")
        row.append(c.evidence, style="dim")
        console.print(row)


def header() -> Panel:
    t = Table.grid(padding=(0, 2))
    t.add_column(style="dim", justify="right")
    t.add_column()
    t.add_row("target", "macOS · arm64 · App Store Connect (.pkg)")
    t.add_row("identity", IDENTITY)
    t.add_row("bundle", f"{BUNDLE}  ·  team {TEAM}")
    t.add_row("logs", "desktop/build/  ·  [dim]tail -f xcodebuild-archive.log[/dim]")
    return Panel(t, title="[bold]Bristlenose.app — release build[/bold]",
                 title_align="left", border_style="cyan", padding=(1, 2))


def gate_table() -> Table:
    t = Table.grid(padding=(0, 1))
    t.add_column(width=3, justify="right", style="dim")
    t.add_column(width=1)
    t.add_column(width=24)
    t.add_column(ratio=1, style="dim")
    for ga in GATES:
        t.add_row(ga.id, Text(GLYPH[ga.result.value], style=STYLE[ga.result.value]),
                  Text(ga.desc, style="dim" if ga.result == St.SKIP else ""),
                  ga.evidence)
    return t


def ok_footer() -> Panel:
    t = Table.grid(padding=(0, 2))
    t.add_column(style="dim", justify="right")
    t.add_column()
    t.add_row("artifact", "desktop/build/export/Bristlenose.pkg")
    t.add_row("size", f"213 MB  [dim]({PKG_BYTES:,} bytes)[/dim]")
    t.add_row("signed", IDENTITY)
    t.add_row("next", "drag into Transporter.app, or:")
    t.add_row("", "[dim]xcrun altool --upload-app -f Bristlenose.pkg --type macos \\\n"
                  "  --apiKey <KEY_ID> --apiIssuer <ISSUER_ID>[/dim]")
    return Panel(t, title="[bold green]✓ Ready for App Store Connect[/bold green]",
                 title_align="left", border_style="green", padding=(1, 2))


def fail_footer(n: int, st: Step) -> Panel:
    t = Table.grid(padding=(0, 2))
    t.add_column(style="dim", justify="right")
    t.add_column()
    t.add_row("failed at", f"step {n} · {st.name}  [dim][{st.tag}][/dim]")
    t.add_row("reason", "dev escape-hatch literal in a shipping binary")
    t.add_row("log", "desktop/build/  ·  check-release-binary output above")
    t.add_row("nothing", "uploaded — bailed before export was published")
    t.add_row("next", "strip the literal, rebuild; the scan re-runs on the fixed binary")
    return Panel(t, title="[bold red]✗ Build failed[/bold red]",
                 title_align="left", border_style="red", padding=(1, 2))


# ── frames ─────────────────────────────────────────────────────────────────
def _by_phase() -> list[tuple[str, list[tuple[int, Step]]]]:
    numbered = list(enumerate(STEPS, start=1))
    out: list[tuple[str, list[tuple[int, Step]]]] = []
    for n, st in numbered:
        if not out or out[-1][0] != st.phase:
            out.append((st.phase, []))
        out[-1][1].append((n, st))
    return out


def render_frame(console: Console, fail: bool = False) -> None:
    console.print()
    console.print(header())
    for phase, group in _by_phase():
        phase_header(console, phase, len(group))
        for n, st in group:
            failing = fail and st.tag == FAIL_STEP_TAG
            if failing:
                st = Step(**{**st.__dict__, "log_tail": FAIL_TAIL})
            emit_step(console, n, st, failing=failing)
            if failing:
                console.print()
                console.print(fail_footer(n, st))
                return
    console.print()
    console.print(Text("  RELEASE GATE  ", style="bold cyan")
                  + Text("· App Store readiness", style="dim"))
    console.print(gate_table())
    console.print()
    total = sum(s.elapsed for s in STEPS if s.elapsed)
    console.print(Text.assemble(
        (f"  {len(STEPS)} steps · {len(GATES)} gates · ", "dim"),
        (f"{fmt_elapsed(total)} total", "bold"),
        ("  ·  sidecar dominates the tail", "dim")))
    console.print()
    console.print(ok_footer())
    console.print()


def run_live(console: Console) -> None:
    console.print()
    console.print(header())
    steps = list(enumerate(STEPS, start=1))
    for phase, group in _by_phase():
        phase_header(console, phase, len(group))
        for n, st in group:
            label = (f"[dim]{n:>3}[/dim]  [bold]{st.name}[/bold] "
                     f"[dim][{n}/{len(steps)}][/dim]")
            if st.status == St.SKIP:
                console.print(f"{n:>3}  [dim]{GLYPH['skip']} {st.name} — {st.detail}[/dim]")
                continue
            if st.bar:
                done, total = st.bar
                with Progress(TextColumn(label), BarColumn(bar_width=24),
                              TextColumn("[dim]{task.completed}/{task.total}[/dim]"),
                              TimeElapsedColumn(), console=console,
                              transient=True) as p:
                    task = p.add_task("", total=total)
                    for _ in range(total):
                        time.sleep(0.003)
                        p.advance(task)
            else:
                with Progress(SpinnerColumn(), TextColumn(label), TimeElapsedColumn(),
                              console=console, transient=True) as p:
                    p.add_task("", total=None)
                    time.sleep(min(1.0, (st.elapsed or 1) / 120))
            emit_step(console, n, st)
    console.print()
    console.print(Text("  RELEASE GATE  ", style="bold cyan")
                  + Text("· App Store readiness", style="dim"))
    console.print(gate_table())
    console.print()
    console.print(ok_footer())
    console.print()


def main() -> None:
    fail = "--fail" in sys.argv
    if "--svg" in sys.argv:
        path = sys.argv[sys.argv.index("--svg") + 1]
        rec = Console(record=True, width=WIDTH, force_terminal=True)
        render_frame(rec, fail=fail)
        rec.save_svg(path, title="build-all.sh")
        print(f"wrote {path}")
        return
    console = Console(width=WIDTH)
    if fail or "--frame" in sys.argv or not console.is_terminal:
        render_frame(console, fail=fail)
    else:
        run_live(console)


if __name__ == "__main__":
    main()
