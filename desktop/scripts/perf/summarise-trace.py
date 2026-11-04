#!/usr/bin/env python3
"""Summarise an xctrace Time Profiler recording of the app's main thread.

  summarise-trace.py run.trace [--json out.json]
  summarise-trace.py --compare a.json b.json [c.json ...]

Exports the time-profile table with `xctrace export`, then reports the main thread's busy
time and the inclusive time of a fixed list of frames (the ones a window drag has been seen
to spend time in). Compare mode prints one column per recording. Numbers from a Debug build
are inflated, so compare Debug with Debug and Release with Release, never across.
"""
import collections
import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

KEY_FRAMES = [
    ("window resize call", "-[NSWindow _setFrameCommon:display:fromServer:]"),
    ("sidebar table layout", "-[NSTableView layout]"),
    ("row views built", "-[NSTableRowData _addRowViewForVisibleRow:withPriorView:]"),
    ("our cells (viewFor)", "@objc SidebarOutlineController.outlineView(_:viewFor:item:)"),
    ("outline reload", "SidebarOutlineController.reloadAndRestore()"),
    ("outline update", "ProjectSidebarOutline.updateNSViewController(_:context:)"),
    ("ContentView.body", "ContentView.body.getter"),
    ("NSHostingView.layout", "@objc NSHostingView.layout()"),
    ("AttributeGraph update", "AG::Graph::UpdateStack::update()"),
    ("toolbar inset sync", "BridgeHandler.syncToolbarInset()"),
    ("click monitor (handle)", "SidebarDeselectMonitor.Coordinator.handle(_:)"),
    ("click monitor tree walk", "~sidebarTableView"),
    ("WebKit frames (any)", "~WebKit"),
    ("WKWebView frames", "~WKWebView"),
]

def export(trace: Path) -> Path:
    out = Path(tempfile.mkdtemp()) / "tp.xml"
    subprocess.run(["xctrace", "export", "--input", str(trace), "--xpath",
                    '/trace-toc/run[1]/data/table[@schema="time-profile"]', "--output", str(out)],
                   check=True, capture_output=True)
    return out

def summarise(xml: Path) -> dict:
    root = ET.parse(xml).getroot()
    ids = {e.get("id"): e for e in root.iter() if e.get("id")}

    def res(e):
        return ids[e.get("ref")] if e.get("ref") else e

    incl = collections.Counter()
    main = 0
    samples = 0
    node = root.find(".//node")
    if node is None:
        raise SystemExit("no time-profile rows in the recording")
    for row in node.findall("row"):
        th = w = bt = None
        for c in row:
            c = res(c)
            if c.tag == "thread":
                th = c.get("fmt")
            elif c.tag == "weight":
                w = int(c.text)
            elif c.tag == "tagged-backtrace":
                bt = c
        if th and "Main Thread" in th and bt is not None:
            main += w
            samples += 1
            names = {res(f).get("name") or "?" for f in bt.findall("frame")}
            for n in names:
                incl[n] += w
            for _, sym in KEY_FRAMES:
                if sym.startswith("~") and any(sym[1:] in n for n in names):
                    incl[sym] += w

    def ms(v):
        return round(v / 1e6)

    return {"main_busy_ms": ms(main), "main_samples": samples,
            "frames_ms": {label: ms(incl.get(sym, 0)) for label, sym in KEY_FRAMES}}

def compare(paths):
    runs = [json.loads(Path(p).read_text()) for p in paths]
    names = [r.get("label") or Path(p).stem for r, p in zip(runs, paths, strict=True)]
    print(f'{"":26}' + "".join(f"{n[:14]:>15}" for n in names))
    print(f'{"main thread busy (ms)":26}' + "".join(f'{r["main_busy_ms"]:>15}' for r in runs))
    for label, _ in KEY_FRAMES:
        print(f"{label:26}" + "".join(str(r["frames_ms"].get(label, "-")).rjust(15) for r in runs))
    if all("drag" in r for r in runs):
        for key, lab in [("updates_per_s", "window updates / s"), ("gap_p50_ms", "update gap p50 (ms)"),
                         ("gap_p95_ms", "update gap p95 (ms)"), ("gap_max_ms", "update gap max (ms)")]:
            print(f"{lab:26}" + "".join(str(r["drag"].get(key, "-")).rjust(15) for r in runs))
        print(f'{"drag: width range (pt)":26}' + "".join(
            f'{r["drag"].get("min_width_seen", "?")}-{r["drag"].get("max_width_seen", "?")}'.rjust(15) for r in runs))

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        raise SystemExit(__doc__)
    if a[0] == "--compare":
        compare(a[1:])
    else:
        result = summarise(export(Path(a[0])))
        if "--json" in a:
            Path(a[a.index("--json") + 1]).write_text(json.dumps(result, indent=1))
        print(json.dumps(result, indent=1))
