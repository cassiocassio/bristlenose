#!/usr/bin/env python3
"""Generate SVG mockups of the proposed auto-serve CLI output.

Run:  python docs/mockups/cli-serve-mockup.py
Creates: docs/mockups/cli-serve-*.svg

Open the SVGs in a browser or Preview to review. Edit the scenario
functions below and re-run to iterate on the layout.
"""

from pathlib import Path

from rich.console import Console

OUT = Path(__file__).parent

# ── shared fragments ──────────────────────────────────────────────────

# Relative path from cwd — what the user actually sees for file links
REPORT_REL = "bristlenose-output/bristlenose-project-ikea-report.html"
REPORT_ABS = "file:///Users/cassio/trial-runs/project-ikea/bristlenose-output/bristlenose-project-ikea-report.html"

STAGE_LINES = """\
[dim]4 sessions in project-ikea/[/dim]

 [green]✓[/green] Ingested 4 sessions (4 video)                            [dim]0.8s[/dim]

   [dim]Estimated time: ~3 min (±90 sec)[/dim]

 [green]✓[/green] Extracted audio from 4 sessions                          [dim]1.3s[/dim]
 [green]✓[/green] Transcribed 4 sessions (229 segments)                 [dim](cached)[/dim]
 [green]✓[/green] Identified speakers for 4 sessions                    [dim](cached)[/dim]
 [green]✓[/green] Merged transcripts for 4 sessions                     [dim](cached)[/dim]
 [green]✓[/green] Segmented 4 transcripts into 37 topics                   [dim]4.2s[/dim]
 [green]✓[/green] Extracted 51 quotes from 4 sessions                      [dim]8.1s[/dim]
 [green]✓[/green] Clustered quotes into 4 themes (8 screens)               [dim]3.7s[/dim]
 [green]✓[/green] Rendered report                                          [dim]0.2s[/dim]"""

SUMMARY = """\

  [dim]4 participants (Sarah, James, Randolph, +1) · 8 screens · 4 themes · 51 quotes[/dim]
  [dim]LLM: 42,180 in · 8,340 out · ~$0.12 (claude-sonnet-4-20250514)[/dim]"""


# ── scenario 1: happy path (auto-serve) ──────────────────────────────

def scenario_happy(c: Console) -> None:
    c.print(STAGE_LINES)
    c.print(SUMMARY)
    c.print()
    c.print("  [green]Done[/green] in 18.6s")
    c.print()
    c.print("  Report:  [bold cyan]http://127.0.0.1:8150/report/[/bold cyan]")
    c.print("  [dim]Press Ctrl-C to stop the server[/dim]")


# ── scenario 2: --static (file:// link, no server) ──────────────────

def scenario_static(c: Console) -> None:
    c.print(STAGE_LINES)
    c.print(SUMMARY)
    c.print()
    c.print("  [green]Done[/green] in 18.6s")
    c.print()
    c.print(f"  Report:  [link={REPORT_ABS}]{REPORT_REL}[/link]")


# ── scenario 3: port fallback (8150 in use, found 8152) ─────────────

def scenario_port_fallback(c: Console) -> None:
    c.print(STAGE_LINES)
    c.print(SUMMARY)
    c.print()
    c.print("  [green]Done[/green] in 18.6s")
    c.print()
    c.print("  [dim]Port 8150 in use, trying 8151… 8152… ok[/dim]")
    c.print("  Report:  [bold cyan]http://127.0.0.1:8152/report/[/bold cyan]")
    c.print("  [dim]Press Ctrl-C to stop the server[/dim]")


# ── scenario 4: serve deps missing ──────────────────────────────────

def scenario_no_deps(c: Console) -> None:
    c.print(STAGE_LINES)
    c.print(SUMMARY)
    c.print()
    c.print("  [green]Done[/green] in 18.6s")
    c.print()
    c.print(f"  Report:  [link={REPORT_ABS}]{REPORT_REL}[/link]")
    c.print("  [dim]Tip: pip install bristlenose\\[serve] for the interactive report[/dim]")


# ── scenario 5: server startup failure ───────────────────────────────

def scenario_server_error(c: Console) -> None:
    c.print(STAGE_LINES)
    c.print(SUMMARY)
    c.print()
    c.print("  [green]Done[/green] in 18.6s")
    c.print()
    c.print("  [yellow]⚠[/yellow] Could not start server: database import failed")
    c.print(f"  Report:  [link={REPORT_ABS}]{REPORT_REL}[/link]")


# ── scenario 6: pipeline errors (0 quotes) ──────────────────────────

def scenario_pipeline_error(c: Console) -> None:
    c.print("""\
[dim]4 sessions in project-ikea/[/dim]

 [green]✓[/green] Ingested 4 sessions (4 video)                            [dim]0.8s[/dim]
 [green]✓[/green] Extracted audio from 4 sessions                          [dim]1.3s[/dim]
 [green]✓[/green] Transcribed 4 sessions (229 segments)                 [dim](cached)[/dim]
 [green]✓[/green] Identified speakers for 4 sessions                    [dim](cached)[/dim]
 [green]✓[/green] Merged transcripts for 4 sessions                     [dim](cached)[/dim]
 [green]✓[/green] Segmented 4 transcripts into 37 topics                   [dim]4.2s[/dim]
 [green]✓[/green] Extracted 0 quotes from 4 sessions                       [dim]8.1s[/dim]
 [green]✓[/green] Rendered report                                          [dim]0.1s[/dim]""")
    c.print()
    c.print("  [red]Finished with errors[/red] in 14.5s — 0 quotes extracted (check API credits or logs)")
    c.print("  [dim]Run [bold]bristlenose doctor[/bold] to diagnose[/dim]")


# ── render all scenarios ─────────────────────────────────────────────

SCENARIOS = [
    ("cli-serve-1-happy", "bristlenose run  (auto-serve, happy path)", scenario_happy),
    ("cli-serve-2-static", "bristlenose run --static  (file link, no server)", scenario_static),
    ("cli-serve-3-port-fallback", "bristlenose run  (port 8150 busy, falls back to 8152)", scenario_port_fallback),
    ("cli-serve-4-no-deps", "bristlenose run  (serve extras not installed)", scenario_no_deps),
    ("cli-serve-5-server-error", "bristlenose run  (server fails to start)", scenario_server_error),
    ("cli-serve-6-pipeline-error", "bristlenose run  (pipeline errors, no auto-serve)", scenario_pipeline_error),
]

if __name__ == "__main__":
    for filename, title, fn in SCENARIOS:
        c = Console(record=True, width=88, force_terminal=True)
        c.print("[bold]$ bristlenose run trial-runs/project-ikea/[/bold]")
        if "static" in filename and "static" in title:
            c.print("[bold]  (with --static)[/bold]")
        c.print()
        fn(c)
        c.print()  # trailing blank line

        svg_path = OUT / f"{filename}.svg"
        c.save_svg(str(svg_path), title=title)
        print(f"  ✓ {svg_path}")

    print(f"\nDone — {len(SCENARIOS)} mockups in {OUT}/")
