"""`bristlenose pipeline` — render the mixture-of-models view.

Read-only CLI surface. v2: a sectioned-flat matrix grouped by stage-profile
cluster. Stages whose quality columns are byte-identical merge under one
heading (today: {speaker id, topic segmentation} and {quote extraction, quote
clustering, thematic grouping}). Four columns per row — Provider/Model ·
Availability · Quality · Why. Providers collapse to a single line when every
model shares the same provider-level failure; expand to per-model rows
otherwise. Reasons / editorial caveats render inline in the Why column (no
hover-only tooltips).
"""

from __future__ import annotations

import sys

import typer
from rich.console import Console
from rich.table import Table

from bristlenose.config import load_settings
from bristlenose.pipeline_view.catalogue import STAGES, UNTESTED_NOTE_KEY, find_stage
from bristlenose.pipeline_view.render import (
    ModelAvailability,
    PipelineView,
    StageSelection,
    build_pipeline_view,
)
from bristlenose.ui_kinds import MessageKind, cli_prefix

console = Console()

# English fallback strings used by the CLI surface. Mirrors the
# `pipeline.reasons.*` keys in `bristlenose/locales/*/settings.json`.
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

# English fallback for the editorial quality notes (Why column). Mirrors the
# `pipeline.quality.*` keys in the locale files.
_NOTE_TEXT: dict[str, str] = {
    "pipeline.quality.untested": "untested — no editorial signal yet",
    "pipeline.quality.local_speaker_id_acceptable": (
        "Local models handle speaker identification well"
    ),
    "pipeline.quality.local_topic_segmentation_acceptable": (
        "Local models handle topic segmentation well"
    ),
    "pipeline.quality.local_quote_extraction_miss_rate": (
        "small models miss multi-clause quotes"
    ),
    "pipeline.quality.local_quote_clustering_drift": (
        "small models cluster quotes inconsistently"
    ),
    "pipeline.quality.local_thematic_grouping_drift": (
        "small models drift on thematic synthesis"
    ),
    "pipeline.quality.mlx_whisper_apple_silicon_optimal": "optimal on Apple Silicon",
    "pipeline.quality.faster_whisper_cpu_baseline": "solid CPU baseline; no GPU required",
}

_LOCAL_OLLAMA_LABEL = "Local (Ollama)"
_BUILTIN_ANONYMISER_LABEL = "Built-in anonymiser"

_DISPLAY_KEY_TEXT: dict[str, str] = {
    "pipeline.backends.local_ollama": _LOCAL_OLLAMA_LABEL,
    "pipeline.backends.builtin_anonymiser": _BUILTIN_ANONYMISER_LABEL,
}

# Editorial quality vocabulary — distinct from MessageKind by design (a cell's
# fitness is orthogonal to whether it can run). Empty when the row is ✗ or —.
_QUALITY_GLYPH: dict[str, str] = {
    "excellent": "●",
    "good": "○",
    "marginal": "⚠",
    "avoid": "✗",
}
_QUALITY_COLOUR: dict[str, str] = {
    "excellent": "green",
    "good": "green",
    "marginal": "yellow",
    "avoid": "red",
}

# Provider display labels + qualifier keys, sourced from the catalogue.
_PROVIDER_DISPLAY: dict[str, str] = {}
_PROVIDER_DISPLAY_KEY: dict[str, str | None] = {}
for _stage in STAGES:
    for _backend in _stage.viable_backends:
        _PROVIDER_DISPLAY[_backend.id] = _backend.display
        _PROVIDER_DISPLAY_KEY[_backend.id] = _backend.display_key


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


def _avail_glyph(row: ModelAvailability) -> str:
    """MessageKind glyph for the Availability column.

    ✗ (ERROR) for fixable failures (an `action_key` exists); — (SKIPPED) for
    structural ones (hardware / OS version — no user action). ✓ when available.
    """
    if row.available:
        kind = MessageKind.SUCCESS
    elif row.action_key is not None:
        kind = MessageKind.ERROR
    else:
        kind = MessageKind.SKIPPED
    return cli_prefix(kind)


def _quality_glyph(row: ModelAvailability) -> str:
    """Editorial quality glyph. Empty when the row can't run."""
    if not row.available:
        return ""
    if row.quality is None:
        return "[dim]?[/dim]"
    glyph = _QUALITY_GLYPH.get(row.quality, "?")
    colour = _QUALITY_COLOUR.get(row.quality, "dim")
    return f"[{colour}]{glyph}[/{colour}]"


def _why_text(row: ModelAvailability) -> str:
    """Unified Why text: failure reason (✗/—), editorial caveat (✓⚠), or
    untested explanation (✓?). Empty for ✓●/✓○ — no caveat to surface."""
    if not row.available:
        return _REASON_TEXT.get(row.reason_key or "", row.reason_key or "")
    if row.quality is None:
        return _NOTE_TEXT.get(UNTESTED_NOTE_KEY, "untested")
    if row.quality in ("marginal", "avoid") and row.quality_note:
        return _NOTE_TEXT.get(row.quality_note, row.quality_note)
    return ""


def _badges(row: ModelAvailability, is_current: bool) -> str:
    parts: list[str] = []
    if row.default:
        parts.append("default")
    if is_current:
        parts.append("current")
    return f"  ({' · '.join(parts)})" if parts else ""


def _by_provider(alts: list[ModelAvailability]) -> list[list[ModelAvailability]]:
    """Bucket a flat alternatives list into per-provider groups (order-preserving)."""
    groups: list[list[ModelAvailability]] = []
    current_pid: str | None = None
    bucket: list[ModelAvailability] = []
    for a in alts:
        if a.provider_id != current_pid:
            if bucket:
                groups.append(bucket)
            bucket = [a]
            current_pid = a.provider_id
        else:
            bucket.append(a)
    if bucket:
        groups.append(bucket)
    return groups


def _collapse(
    provider_rows: list[ModelAvailability],
) -> tuple[bool, ModelAvailability]:
    """Return `(collapsed, representative_row)` for one provider's rows.

    Collapses to a single line when there's no model granularity, or when no
    model is available AND every failure shares the same provider-level reason.
    """
    if len(provider_rows) == 1 and provider_rows[0].model_id is None:
        return True, provider_rows[0]
    if all(not r.available for r in provider_rows):
        reasons = {r.reason_key for r in provider_rows}
        if len(reasons) == 1:
            return True, provider_rows[0]
    return False, provider_rows[0]


def _provider_block(
    provider_rows: list[ModelAvailability],
    sel: StageSelection,
) -> list[tuple[str, str, str, str]]:
    """Render one provider's rows as (name, avail, quality, why) tuples."""
    pid = provider_rows[0].provider_id
    pdisplay = _display_text(
        _PROVIDER_DISPLAY.get(pid, pid), _PROVIDER_DISPLAY_KEY.get(pid)
    )
    collapsed, rep = _collapse(provider_rows)
    if collapsed:
        # Transcription/anonymisation collapse to a flat provider row but can
        # still carry a quality rating (MLX ●, faster-whisper ○). `_quality_glyph`
        # returns "" when the row is unavailable, so failed LLM providers stay
        # quality-blank.
        return [(f"  {pdisplay}", _avail_glyph(rep), _quality_glyph(rep), _why_text(rep))]

    out: list[tuple[str, str, str, str]] = [(f"  [bold]{pdisplay}[/bold]", "", "", "")]
    for row in provider_rows:
        is_current = (
            row.provider_id == sel.chosen_id and row.model_id == sel.chosen_model_id
        )
        name = f"    {row.display}{_badges(row, is_current)}"
        out.append((name, _avail_glyph(row), _quality_glyph(row), _why_text(row)))
    return out


def _cluster_signature(sel: StageSelection) -> tuple:  # type: ignore[type-arg]
    """Hashable signature of a stage's per-model column for stage-group dedup.

    Stages with byte-identical availability + quality-*level* columns share a
    heading. Availability is uniform across LLM stages (same host); the quality
    *level* varies (Local is good for structural stages, marginal for synthesis)
    — that's the axis the clustering surfaces. The per-stage `quality_note` is
    deliberately excluded: the three synthesis stages carry distinct notes
    ("miss multi-clause quotes" / "cluster inconsistently" / "drift on
    synthesis") yet merge into one group, the first stage in declaration order
    contributing the displayed note (matches the canonical mockup).
    """
    return tuple(
        (
            a.provider_id,
            a.model_id,
            a.available,
            a.reason_key,
            a.quality,
            a.default,
            a.recommended,
        )
        for a in sel.alternatives
    )


def _render_table(view: PipelineView) -> None:
    """Render the sectioned-flat matrix: stage-group headings, per-provider rows."""
    llm_groups: list[tuple[list[str], StageSelection]] = []
    llm_index: dict[tuple, tuple[list[str], StageSelection]] = {}  # type: ignore[type-arg]
    non_llm_groups: list[tuple[list[str], StageSelection]] = []

    for sel in view.catalogue:
        if not sel.alternatives:
            continue  # e.g. the apple_foundation_models stub (Apple FM is a row above)
        if sel.kind == "llm":
            sig = _cluster_signature(sel)
            if sig in llm_index:
                llm_index[sig][0].append(sel.name)
            else:
                group = ([sel.name], sel)
                llm_index[sig] = group
                llm_groups.append(group)
        else:
            non_llm_groups.append(([sel.name], sel))

    ordered = llm_groups + non_llm_groups

    table = Table(show_header=False, box=None, pad_edge=False, padding=(0, 1))
    table.add_column("name", no_wrap=False)
    table.add_column("avail", justify="center", no_wrap=True)
    table.add_column("quality", justify="center", no_wrap=True)
    table.add_column("why", no_wrap=False, style="dim")

    for names, sel in ordered:
        heading = ", ".join(names).upper()
        table.add_row(f"[bold]{heading}[/bold]", "", "", "")
        for provider_rows in _by_provider(sel.alternatives):
            for name, avail, quality, why in _provider_block(provider_rows, sel):
                table.add_row(name, avail, quality, why)
        table.add_row("", "", "", "")  # spacer between groups

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
