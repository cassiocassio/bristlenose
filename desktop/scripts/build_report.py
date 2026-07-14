#!/usr/bin/env python3
"""Renderer for the desktop build-script report — see REPORT-STYLE.md.

Reads a stream of `@bn …` sentinel events on stdin (emitted by build-all.sh via
report.sh) and draws the one-system report: header panel, phase-grouped steps
with glyphs / narrative / determinate bars, a release-gate battery, and a
success/failure footer.

Design (frozen in REPORT-STYLE.md):
  • Scripts stay dumb about presentation; this file owns the entire look.
  • Append-only: each step resolves to a final line when it completes. A step
    that streams `@bn bar` events animates a real determinate bar; an opaque
    step shows a "running · tail <log>" line, never a faked fraction.
  • Degrades to plain on non-TTY / NO_COLOR / TERM=dumb (Rich handles this);
    no ANSI is ever written to the redirected per-step log files.

Self-test (no build needed):
  python3 build_report.py --demo         # canned success stream
  python3 build_report.py --demo-fail    # canned failure stream
  <emitter> | python3 build_report.py    # real use, piped from build-all.sh
"""
from __future__ import annotations

import shlex
import sys
import textwrap
from dataclasses import dataclass, field
from enum import Enum

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

WIDTH = 92
IND = "        "

# Glyph + colour vocabulary — mirrors bristlenose/ui_kinds.py. Never invent new.
GLYPH = {"ok": "✓", "info": "ℹ", "warn": "⚠", "fail": "✗", "skip": "—", "run": "○"}
STYLE = {"ok": "green", "info": "blue", "warn": "yellow", "fail": "red",
         "skip": "dim", "run": "cyan"}
PHASE_ORDER = ["Pre-flight", "Build", "Package", "Verify"]


class St(str, Enum):
    OK = "ok"
    INFO = "info"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"
    RUN = "run"


@dataclass
class Check:
    label: str
    result: St
    evidence: str = ""


@dataclass
class Step:
    tag: str
    phase: str
    name: str
    status: St = St.RUN
    elapsed: float | None = None
    detail: str = ""
    narrative: str = ""
    log: str = ""
    checks: list[Check] = field(default_factory=list)
    bar: tuple[int, int] | None = None


@dataclass
class Gate:
    id: str
    desc: str
    result: St
    evidence: str


# ── event parsing ──────────────────────────────────────────────────────────
def parse_event(line: str) -> tuple[str, dict[str, str]] | None:
    """`@bn <kind> k=v k="v w/ spaces" …` → (kind, fields). None if not an event."""
    if not line.startswith("@bn "):
        return None
    try:
        toks = shlex.split(line[4:].strip())
    except ValueError:
        return None
    if not toks:
        return None
    kind, rest = toks[0], toks[1:]
    fields: dict[str, str] = {}
    for tok in rest:
        if "=" in tok:
            k, _, v = tok.partition("=")
            fields[k] = v
    return kind, fields


def _st(v: str) -> St:
    try:
        return St(v)
    except ValueError:
        return St.INFO


# ── shared rendering (same look as the mock) ───────────────────────────────
def leader_line(n: int, status: St, name: str, tag: str, right: str) -> Text:
    line = Text()
    line.append(f"{n:>3}  ", style="dim")
    line.append(GLYPH[status.value] + "  ", style=STYLE[status.value])
    line.append(name, style="bold" if status != St.SKIP else "dim")
    tail = Text.assemble((f"[{tag}]", "dim"), ("  ", ""), (right, "dim"))
    fill = max(1, WIDTH - line.cell_len - tail.cell_len - 2)
    leader = "".join("·" if k % 2 == 0 else " " for k in range(fill))
    line.append(" " + leader + " ", style="dim")
    line.append(tail)
    return line


def fmt_elapsed(s: float | None) -> str:
    if s is None:
        return ""
    return f"{s:.1f}s" if s < 60 else f"{int(s // 60)}m {int(s % 60):02d}s"


def running_renderable(n: int, st: Step) -> Text:
    right = "running"
    if st.log:
        right += f" · tail {st.log}"
    return leader_line(n, St.RUN, st.name, st.tag, right)


def bar_renderable(n: int, st: Step) -> Table:
    done, total = st.bar  # type: ignore[misc]
    gt = Table.grid()
    for _ in range(3):
        gt.add_column(no_wrap=True)
    gt.add_row(
        Text(f"{n:>3}  ", style="dim") + Text(st.name + " ", style="bold"),
        ProgressBar(total=total, completed=done, width=28,
                    complete_style="cyan", finished_style="green"),
        Text(f"  {done}/{total}", style="dim"))
    return gt


class Renderer:
    def __init__(self, console: Console) -> None:
        self.c = console
        self.meta: dict[str, str] = {}
        self.printed_header = False
        self.cur_phase: str | None = None
        self.gates: list[Gate] = []
        self.arts: list[tuple[str, str]] = []
        self.step: Step | None = None
        self.step_n = 0
        self.live: Live | None = None

    # header ----------------------------------------------------------------
    def _header(self) -> None:
        t = Table.grid(padding=(0, 2))
        t.add_column(style="dim", justify="right")
        t.add_column()
        for key in ("target", "identity", "bundle", "team", "logs"):
            if key in self.meta:
                t.add_row(key, self.meta[key])
        title = self.meta.get("title", "Bristlenose.app — release build")
        self.c.print()
        self.c.print(Panel(t, title=f"[bold]{title}[/bold]", title_align="left",
                           border_style="cyan", padding=(1, 2)))
        self.printed_header = True

    def _phase_header(self, phase: str) -> None:
        self.c.print()
        self.c.print(Text(f"  {phase.upper()}  ", style="bold cyan"))

    # live running line -----------------------------------------------------
    def _start_live(self) -> None:
        # Non-TTY (CI, piped): no running line — the completion line prints once
        # when the step finishes. Animation only on a real terminal (clig.dev).
        if not self.c.is_terminal or self.step is None:
            return
        self.live = Live(running_renderable(self.step_n, self.step),
                         console=self.c, refresh_per_second=12, transient=True)
        self.live.start()

    def _update_live(self) -> None:
        if self.live is not None and self.step is not None:
            r = bar_renderable(self.step_n, self.step) if self.step.bar \
                else running_renderable(self.step_n, self.step)
            self.live.update(r)

    def _stop_live(self) -> None:
        if self.live is not None:
            self.live.stop()
            self.live = None

    # finalise a step -------------------------------------------------------
    def _emit_final(self) -> None:
        st = self.step
        assert st is not None
        if st.status == St.FAIL:
            right = "FAILED"
        else:
            right = fmt_elapsed(st.elapsed) or ("skipped" if st.status == St.SKIP else "")
        self.c.print(leader_line(self.step_n, st.status, st.name, st.tag, right))
        if st.status == St.FAIL and st.log:
            self.c.print(Text(f"{IND}see {st.log}", style="red"))
        if st.detail and not st.bar:
            self.c.print(Text(IND + st.detail, style="dim"))
        if st.bar:
            done, total = st.bar
            gt = Table.grid()
            for _ in range(3):
                gt.add_column(no_wrap=True)
            gt.add_row(Text(IND[:-1]),
                       ProgressBar(total=total, completed=done, width=32,
                                   complete_style="green", finished_style="green"),
                       Text(f"  {done}/{total}  {st.detail}", style="dim"))
            self.c.print(gt)
        if st.narrative:
            for wl in textwrap.wrap(st.narrative, width=WIDTH - len(IND)):
                self.c.print(Text(IND + wl, style="dim italic"))
        for ch in st.checks:
            row = Text(IND)
            row.append(GLYPH[ch.result.value] + " ", style=STYLE[ch.result.value])
            row.append(ch.label.ljust(22), style="dim")
            row.append(ch.evidence, style="dim")
            self.c.print(row)

    # dispatch --------------------------------------------------------------
    def event(self, kind: str, f: dict[str, str]) -> None:
        if kind == "meta":
            self.meta.update(f)
        elif kind == "step":
            self._on_step(f)
        elif kind == "check" and self.step is not None:
            self.step.checks.append(Check(f.get("label", ""), _st(f.get("result", "ok")),
                                          f.get("evidence", "")))
        elif kind == "bar" and self.step is not None:
            self.step.bar = (int(f.get("done", 0)), int(f.get("total", 1)))
            self._update_live()
        elif kind == "gate":
            self.gates.append(Gate(f.get("id", ""), f.get("desc", ""),
                                   _st(f.get("result", "ok")), f.get("evidence", "")))
        elif kind == "art":
            self.arts.append((f.get("key", ""), f.get("value", "")))
        elif kind == "done":
            self._on_done(f.get("status", "ok"))

    def _on_step(self, f: dict[str, str]) -> None:
        status = f.get("status", "start")
        if status == "start":
            if not self.printed_header:
                self._header()
            phase = f.get("phase", "")
            if phase and phase != self.cur_phase:
                self.cur_phase = phase
                self._phase_header(phase)
            self.step_n += 1
            self.step = Step(f.get("id", "?"), phase, f.get("name", ""),
                             detail=f.get("detail", ""), narrative=f.get("narrative", ""),
                             log=f.get("log", ""))
            self._start_live()
        else:  # ok | skip | fail — completion for the current step
            if self.step is None:  # completion without a start (compact steps)
                if not self.printed_header:
                    self._header()
                phase = f.get("phase", "")
                if phase and phase != self.cur_phase:
                    self.cur_phase = phase
                    self._phase_header(phase)
                self.step_n += 1
                self.step = Step(f.get("id", "?"), phase, f.get("name", ""),
                                 detail=f.get("detail", ""),
                                 narrative=f.get("narrative", ""), log=f.get("log", ""))
            self.step.status = _st(status)
            if "elapsed" in f:
                try:
                    self.step.elapsed = float(f["elapsed"])
                except ValueError:
                    pass
            for k in ("detail", "narrative", "log"):
                if f.get(k):
                    setattr(self.step, k, f[k])
            self._stop_live()
            self._emit_final()
            self.step = None

    def _on_done(self, status: str) -> None:
        self._stop_live()
        if status == "fail":
            self._footer_fail()
            return
        if self.gates:
            self.c.print()
            self.c.print(Text("  RELEASE GATE  ", style="bold cyan")
                         + Text("· App Store readiness", style="dim"))
            gt = Table.grid(padding=(0, 1))
            gt.add_column(width=3, justify="right", style="dim")
            gt.add_column(width=1)
            gt.add_column(width=24)
            gt.add_column(ratio=1, style="dim")
            for ga in self.gates:
                gt.add_row(ga.id, Text(GLYPH[ga.result.value], style=STYLE[ga.result.value]),
                           Text(ga.desc, style="dim" if ga.result == St.SKIP else ""),
                           ga.evidence)
            self.c.print(gt)
        self._footer_ok()

    def _footer_ok(self) -> None:
        t = Table.grid(padding=(0, 2))
        t.add_column(style="dim", justify="right")
        t.add_column()
        for k, v in self.arts:
            t.add_row(k, v)
        title = self.meta.get("done_title", "✓ Ready for App Store Connect")
        self.c.print()
        self.c.print(Panel(t, title=f"[bold green]{title}[/bold green]",
                           title_align="left", border_style="green", padding=(1, 2)))
        self.c.print()

    def _footer_fail(self) -> None:
        t = Table.grid(padding=(0, 2))
        t.add_column(style="dim", justify="right")
        t.add_column()
        for k, v in self.arts:
            t.add_row(k, v)
        self.c.print()
        self.c.print(Panel(t, title="[bold red]✗ Build failed[/bold red]",
                           title_align="left", border_style="red", padding=(1, 2)))
        self.c.print()


def run(stream, console: Console) -> int:
    r = Renderer(console)
    fail = False
    for raw in stream:
        ev = parse_event(raw.rstrip("\n"))
        if ev is None:
            if "--verbose" in sys.argv and raw.strip():
                console.print(Text("  " + raw.rstrip("\n"), style="dim"))
            continue
        kind, f = ev
        if kind == "done" and f.get("status") == "fail":
            fail = True
        r.event(kind, f)
    return 1 if fail else 0


# ── canned self-test streams ───────────────────────────────────────────────
DEMO = """\
@bn meta title="Bristlenose.app — release build" target="macOS · arm64 · App Store Connect (.pkg)" identity="Apple Distribution: Martin Storey (Z56GZVA2QB)" bundle="app.bristlenose  ·  team Z56GZVA2QB" logs="desktop/build/  ·  tail -f xcodebuild-archive.log"
@bn step id=1 phase="Pre-flight" name="Pre-flight" status=ok elapsed=1.8 narrative="Fails fast before any expensive work — identities, profiles, hygiene."
@bn check parent=1 label="logging hygiene" result=ok evidence="no credential-shaped log calls"
@bn check parent=1 label="bundle manifest" result=ok evidence="every runtime dir covered by spec"
@bn check parent=1 label="signing identity" result=ok evidence="found in keychain"
@bn check parent=1 label="provisioning profile" result=ok evidence="Bristlenose Mac App Store"
@bn step id=2 phase="Build" name="Sidecar — fetch · build · sign" status=start narrative="Freezes the Python engine (PyInstaller), bundles FFmpeg, and signs every Mach-O under your identity."
@bn bar parent=2 done=220 total=220
@bn step id=2 phase="Build" name="Sidecar — fetch · build · sign" status=ok elapsed=281 detail="220 binaries signed"
@bn step id=2a phase="Build" name="Bundle self-test" status=ok elapsed=2.4 detail="doctor --self-test: all runtime data present in bundle"
@bn step id=2b phase="Build" name="Supply-chain inventory" status=ok elapsed=0.9 detail="THIRD-PARTY-BINARIES.md fresh"
@bn step id=5 phase="Build" name="Xcode archive" status=ok elapsed=118 detail="Release · manual-signed · Bristlenose.xcarchive" narrative="Compiles + signs the native app shell. Opaque subprocess — live elapsed here; full stream in xcodebuild-archive.log."
@bn step id=6 phase="Package" name="Export → .pkg" status=ok elapsed=125 detail="Bristlenose.pkg · 213 MB" narrative="Wraps the signed app in an App Store installer (method=app-store-connect)."
@bn step id=7 phase="Verify" name="Release-binary scan" status=ok elapsed=3.1 detail="no BRISTLENOSE_DEV_* literals · no get-task-allow"
@bn step id=8 phase="Verify" name="Provisioning profile" status=ok elapsed=0.5 detail="Z56GZVA2QB.app.bristlenose / Z56GZVA2QB"
@bn step id=9 phase="Verify" name="Notarisation" status=skip detail="method=app-store-connect" narrative="App Store Connect validates server-side after upload — local notarisation is neither needed nor accepted for this method."
@bn gate id=a desc="Notarisation staple" result=skip evidence="App Store validates server-side"
@bn gate id=b desc="Installer signature" result=ok evidence="signed, trusted for current user"
@bn gate id=c desc="Code signature" result=ok evidence="--deep --strict valid"
@bn gate id=d desc="get-task-allow" result=ok evidence="absent (debug entitlement)"
@bn gate id=d2 desc="Hardened Runtime" result=ok evidence="flags=0x10000(runtime)"
@bn gate id=e desc="Designated requirement" result=ok evidence="references Team Z56GZVA2QB"
@bn gate id=f desc="Privacy manifests" result=ok evidence="host + sidecar present, lint-clean"
@bn art key="artifact" value="desktop/build/export/Bristlenose.pkg"
@bn art key="size" value="213 MB (223,281,163 bytes)"
@bn art key="signed" value="Apple Distribution: Martin Storey (Z56GZVA2QB)"
@bn art key="next" value="drag into Transporter.app, or: xcrun altool --upload-app -f Bristlenose.pkg --type macos"
@bn done status=ok
"""

DEMO_FAIL = """\
@bn meta title="Bristlenose.app — release build" target="macOS · arm64 · App Store Connect (.pkg)" identity="Apple Distribution: Martin Storey (Z56GZVA2QB)" bundle="app.bristlenose  ·  team Z56GZVA2QB" logs="desktop/build/  ·  tail -f xcodebuild-archive.log"
@bn step id=1 phase="Pre-flight" name="Pre-flight" status=ok elapsed=1.8 narrative="Fails fast before any expensive work — identities, profiles, hygiene."
@bn check parent=1 label="logging hygiene" result=ok evidence="no credential-shaped log calls"
@bn step id=2 phase="Build" name="Sidecar — fetch · build · sign" status=ok elapsed=281 detail="220 binaries signed"
@bn step id=5 phase="Build" name="Xcode archive" status=ok elapsed=118 detail="Release · manual-signed · Bristlenose.xcarchive"
@bn step id=6 phase="Package" name="Export → .pkg" status=ok elapsed=125 detail="Bristlenose.pkg · 213 MB"
@bn step id=7 phase="Verify" name="Release-binary scan" status=fail elapsed=2.9 log="desktop/build/check-release-binary.log" detail="dev escape-hatch literal BRISTLENOSE_DEV_UNSAFE in Contents/MacOS/Bristlenose"
@bn art key="failed at" value="step 7 · Release-binary scan [7]"
@bn art key="reason" value="dev escape-hatch literal in a shipping binary (App Store would reject)"
@bn art key="nothing" value="uploaded — bailed before export was published"
@bn art key="next" value="strip the literal, rebuild; the scan re-runs on the fixed binary"
@bn done status=fail
"""


def main() -> int:
    console = Console(width=WIDTH)
    if "--demo" in sys.argv:
        return run(DEMO.splitlines(), console)
    if "--demo-fail" in sys.argv:
        return run(DEMO_FAIL.splitlines(), console)
    return run(sys.stdin, console)


if __name__ == "__main__":
    raise SystemExit(main())
