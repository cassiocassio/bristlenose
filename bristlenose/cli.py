"""Command-line interface for Bristlenose."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from bristlenose.config import load_settings

app = typer.Typer(
    name="bristlenose",
    help="User-research transcription and quote extraction engine.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def run(
    input_dir: Annotated[
        Path,
        typer.Argument(
            help="Directory containing audio, video, subtitle, or docx files.",
            exists=True,
            file_okay=False,
            dir_okay=True,
        ),
    ],
    output_dir: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output directory for results."),
    ] = Path("output"),
    project_name: Annotated[
        str | None,
        typer.Option("--project", "-p", help="Name of the research project (defaults to input folder name)."),
    ] = None,
    whisper_backend: Annotated[
        str,
        typer.Option(
            "--whisper-backend",
            "-b",
            help="Transcription backend: auto (detect hardware), mlx (Apple Silicon GPU), faster-whisper (CUDA/CPU).",
        ),
    ] = "auto",
    whisper_model: Annotated[
        str,
        typer.Option(
            "--whisper-model",
            "-w",
            help="Whisper model size: tiny, base, small, medium, large-v3, large-v3-turbo.",
        ),
    ] = "large-v3-turbo",
    llm_provider: Annotated[
        str,
        typer.Option("--llm", "-l", help="LLM provider: anthropic, openai."),
    ] = "anthropic",
    skip_transcription: Annotated[
        bool,
        typer.Option("--skip-transcription", help="Skip audio transcription."),
    ] = False,
    no_pii: Annotated[
        bool,
        typer.Option("--no-pii", help="Disable PII removal pass."),
    ] = False,
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to bristlenose.toml config file."),
    ] = None,
    clean: Annotated[
        bool,
        typer.Option("--clean", help="Delete output directory before running."),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logging."),
    ] = False,
) -> None:
    """Process a folder of user-research recordings into themed, timestamped quotes."""
    if output_dir.exists() and any(output_dir.iterdir()):
        if clean:
            import shutil

            shutil.rmtree(output_dir)
            console.print(f"[dim]Cleaned {output_dir}[/dim]")
        else:
            console.print(
                f"[red]Output directory already exists: {output_dir}[/red]\n"
                f"Use [bold]--clean[/bold] to delete it and re-run."
            )
            raise typer.Exit(1)

    if project_name is None:
        project_name = input_dir.resolve().name

    settings = load_settings(
        input_dir=input_dir,
        output_dir=output_dir,
        project_name=project_name,
        whisper_backend=whisper_backend,
        whisper_model=whisper_model,
        llm_provider=llm_provider,
        skip_transcription=skip_transcription,
        pii_enabled=not no_pii,
    )

    from bristlenose.pipeline import Pipeline

    pipeline = Pipeline(settings, verbose=verbose)
    result = asyncio.run(pipeline.run(input_dir, output_dir))

    console.print(f"\n[bold green]Done.[/bold green] Output written to {result.output_dir}")
    console.print(f"  Participants: {len(result.participants)}")
    console.print(f"  Screen clusters: {len(result.screen_clusters)}")
    console.print(f"  Themes: {len(result.theme_groups)}")
    console.print(f"  Final report: {result.output_dir / 'research_report.md'}")
    console.print(f"  HTML report:  {result.output_dir / 'research_report.html'}")


@app.command()
def transcribe_only(
    input_dir: Annotated[
        Path,
        typer.Argument(
            help="Directory containing audio, video, subtitle, or docx files.",
            exists=True,
            file_okay=False,
            dir_okay=True,
        ),
    ],
    output_dir: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output directory for transcripts."),
    ] = Path("output"),
    whisper_model: Annotated[
        str,
        typer.Option("--whisper-model", "-w", help="Whisper model size."),
    ] = "large-v3-turbo",
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logging."),
    ] = False,
) -> None:
    """Only run transcription (no LLM analysis). Produces raw transcripts."""
    settings = load_settings(
        output_dir=output_dir,
        whisper_model=whisper_model,
        skip_transcription=False,
    )

    from bristlenose.pipeline import Pipeline

    pipeline = Pipeline(settings, verbose=verbose)
    result = asyncio.run(pipeline.run_transcription_only(input_dir, output_dir))

    console.print(f"\n[bold green]Done.[/bold green] Transcripts written to {result.output_dir}")
    console.print(f"  Participants: {len(result.participants)}")


@app.command()
def analyze(
    transcripts_dir: Annotated[
        Path,
        typer.Argument(
            help="Directory of existing transcript .txt files to analyze.",
            exists=True,
            file_okay=False,
            dir_okay=True,
        ),
    ],
    output_dir: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output directory for results."),
    ] = Path("output"),
    project_name: Annotated[
        str | None,
        typer.Option("--project", "-p", help="Name of the research project (defaults to input folder name)."),
    ] = None,
    llm_provider: Annotated[
        str,
        typer.Option("--llm", "-l", help="LLM provider: anthropic, openai."),
    ] = "anthropic",
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logging."),
    ] = False,
) -> None:
    """Run LLM analysis on existing transcripts (skip ingestion and transcription)."""
    if project_name is None:
        project_name = transcripts_dir.resolve().name

    settings = load_settings(
        output_dir=output_dir,
        project_name=project_name,
        llm_provider=llm_provider,
    )

    from bristlenose.pipeline import Pipeline

    pipeline = Pipeline(settings, verbose=verbose)
    result = asyncio.run(pipeline.run_analysis_only(transcripts_dir, output_dir))

    console.print(f"\n[bold green]Done.[/bold green] Output written to {result.output_dir}")
    console.print(f"  Screen clusters: {len(result.screen_clusters)}")
    console.print(f"  Themes: {len(result.theme_groups)}")
    console.print(f"  Final report: {result.output_dir / 'research_report.md'}")
    console.print(f"  HTML report:  {result.output_dir / 'research_report.html'}")
