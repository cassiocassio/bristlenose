"""`bristlenose pipeline` — render the mixture-of-models view.

Read-only CLI surface. v1.5: adds an "LLM backends available on this host"
summary card at the top + per-stage alternatives for transcription and
anonymisation. Reasons render inline beneath unavailable options (matches
the React surface; no hover-only tooltips).
"""

from __future__ import annotations

import sys

import typer
from rich.console import Console
from rich.table import Table

from bristlenose.config import load_settings
from bristlenose.pipeline_view.catalogue import find_stage
from bristlenose.pipeline_view.render import BackendAvailability, build_pipeline_view

console = Console()

# English fallback strings used by the CLI surface. Mirrors the
# `pipeline.reasons.*` keys in `bristlenose/locales/*/preflight.json`.
# Catalogue/eligibility return translation keys; CLI maps them to English.
_REASON_TEXT: dict[str, str] = {
    "pipeline.reasons.no_anthropic_key": "no Claude API key set",
    "pipeline.reasons.no_openai_key": "no ChatGPT API key set",
    "pipeline.reasons.no_azure_key": "no Azure OpenAI key set",
    "pipeline.reasons.no_azure_endpoint": "Azure endpoint not set",
    "pipeline.reasons.no_azure_deployment": "Azure deployment not set",
    "pipeline.reasons.no_google_key": "no Gemini API key set",
    "pipeline.reasons.ollama_not_running": "Ollama not running",
    "pipeline.reasons.apple_fm_check_desktop": "check in the desktop app",
    "pipeline.reasons.requires_apple_silicon": "requires Apple Silicon",
    "pipeline.reasons.mlx_whisper_not_installed": "mlx_whisper not installed",
    "pipeline.reasons.ctranslate2_not_installed": "ctranslate2 not installed",
    "pipeline.reasons.presidio_not_installed": "presidio_analyzer not installed",
    "pipeline.reasons.spacy_model_missing": "spaCy en_core_web_lg not installed",
    "pipeline.reasons.pii_disabled": "PII redaction is off",
}

_LOCAL_OLLAMA_LABEL = "Local (Ollama)"
_BUILTIN_ANONYMISER_LABEL = "Built-in anonymiser"

_DISPLAY_KEY_TEXT: dict[str, str] = {
    "pipeline.backends.local_ollama": _LOCAL_OLLAMA_LABEL,
    "pipeline.backends.builtin_anonymiser": _BUILTIN_ANONYMISER_LABEL,
}


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


def _display_text(display: str, display_key: str | None) -> str:
    if display_key and display_key in _DISPLAY_KEY_TEXT:
        return _DISPLAY_KEY_TEXT[display_key]
    return display


def _format_alternatives(alts: list[BackendAvailability]) -> tuple[str, list[str]]:
    """Return `(available_line, reason_lines)` for an alternatives list.

    available_line: e.g. "Available: ✓ Claude · ✓ ChatGPT · ✓ Gemini".
    reason_lines: one per unavailable option, e.g.
        "Unavailable: Azure OpenAI (no Azure key set)".
    """
    available = [a for a in alts if a.available]
    unavailable = [a for a in alts if not a.available]
    if available:
        labels = " · ".join(
            f"[green]✓[/green] {_display_text(a.display, a.display_key)}" for a in available
        )
        available_line = f"Available: {labels}"
    else:
        available_line = "Available: [dim]none[/dim]"
    reason_lines: list[str] = []
    for a in unavailable:
        reason_text = _REASON_TEXT.get(a.reason or "", a.reason or "unavailable")
        reason_lines.append(
            f"[dim]✗ {_display_text(a.display, a.display_key)} — {reason_text}[/dim]"
        )
    return available_line, reason_lines


def _render_table(view) -> None:  # type: ignore[no-untyped-def]
    """Render the Pipeline view as a two-column definition-list-style table.

    v1.5: the LLM summary card renders first; the per-stage LLM rows show
    only the chosen backend. Transcription / anonymisation rows render
    their per-stage alternatives directly.
    """
    if view.llm_summary:
        avail_line, reason_lines = _format_alternatives(view.llm_summary)
        console.print("[bold]LLM backends on this host[/bold]")
        console.print(f"  {avail_line}")
        for line in reason_lines:
            console.print(f"  {line}")
        console.print()

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
        if sel.alternatives:
            avail_line, reason_lines = _format_alternatives(sel.alternatives)
            backend_block += f"\n{avail_line}"
            for line in reason_lines:
                backend_block += f"\n{line}"
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
