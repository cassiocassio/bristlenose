"""`bristlenose pipeline` — render the mixture-of-models view.

The one new CLI verb shipped by the pipeline-view-v1 branch. Read-only.
"""

from __future__ import annotations

import sys

import typer
from rich.console import Console
from rich.table import Table

from bristlenose.config import load_settings
from bristlenose.pipeline_view.catalogue import find_stage
from bristlenose.pipeline_view.render import build_pipeline_view

console = Console()


def pipeline_command(
    json_output: bool = typer.Option(
        False, "--json", help="Machine-readable JSON output (consumed by the React tab)."
    ),
    stage: str | None = typer.Option(
        None, "--stage", help="Focus on one stage by id (e.g. quote_extraction)."
    ),
) -> None:
    """Show what models Bristlenose currently uses for each pipeline stage.

    Read-only. To change a backend, set the relevant environment variable
    (`BRISTLENOSE_LLM_PROVIDER`, `BRISTLENOSE_WHISPER_BACKEND`, etc.) or edit
    your .env file. The Settings → Pipeline tab in the React UI shows the same
    information.
    """
    settings = load_settings()
    view = build_pipeline_view(settings)

    if stage:
        if find_stage(stage) is None:
            console.print(f"[red]Unknown stage:[/red] {stage}")
            available = ", ".join(s.id for s in view.catalogue)
            console.print(f"[dim]Available stages: {available}[/dim]")
            raise typer.Exit(code=2)
        view = view.model_copy(
            update={"catalogue": [s for s in view.catalogue if s.id == stage]}
        )

    if json_output:
        sys.stdout.write(view.model_dump_json(indent=2))
        sys.stdout.write("\n")
        return

    _render_table(view)


def _render_table(view) -> None:  # type: ignore[no-untyped-def]
    """Render the Pipeline view as a two-column definition-list-style table."""
    table = Table(
        title="Pipeline — currently used models",
        show_header=False,
        box=None,
        pad_edge=False,
        padding=(0, 2),
    )
    table.add_column("Stage", style="bold", no_wrap=False)
    table.add_column("Backend", no_wrap=False)

    for sel in view.catalogue:
        if sel.available:
            backend_block = f"{sel.chosen}\n[dim]{sel.notes}[/dim]"
        else:
            backend_block = f"[dim]{sel.chosen}[/dim]\n[dim]{sel.notes}[/dim]"
        table.add_row(sel.name, backend_block)
        table.add_row("", "")  # blank spacer row between stages

    console.print(table)
    console.print()
    _render_host_footer(view.host)


def _render_host_footer(host) -> None:  # type: ignore[no-untyped-def]
    """Print a short host context line beneath the table."""
    keys = ", ".join(p for p, present in host.keys_present.items() if present) or "none"
    parts = [
        f"OS: {host.os} {host.arch}",
    ]
    if host.memory_gb is not None:
        parts.append(f"RAM: {host.memory_gb} GB")
    parts.append(f"keys: {keys}")
    parts.append(f"ollama: {'running' if host.ollama_running else 'not detected'}")
    parts.append(f"network: {'reachable' if host.network_reachable else 'air-gapped'}")
    console.print("[dim]" + " · ".join(parts) + "[/dim]")
