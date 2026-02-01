"""Command-line interface for Bristlenose."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from bristlenose import __version__
from bristlenose.config import load_settings

app = typer.Typer(
    name="bristlenose",
    help="User-research transcription and quote extraction engine.",
    no_args_is_help=True,
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"bristlenose {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version", "-V",
            help="Show version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """User-research transcription and quote extraction engine."""


@app.command()
def help(
    topic: Annotated[
        str | None,
        typer.Argument(help="Topic: commands, config, workflows, or a command name."),
    ] = None,
) -> None:
    """Show detailed help on commands, configuration, and common workflows."""
    if topic is None:
        _help_overview()
    elif topic == "commands":
        _help_commands()
    elif topic == "config":
        _help_config()
    elif topic == "workflows":
        _help_workflows()
    elif topic in ("run", "transcribe-only", "analyze", "render", "doctor", "help"):
        import subprocess
        import sys

        subprocess.run([sys.argv[0], topic, "--help"])
    else:
        console.print(f"[red]Unknown topic:[/red] {topic}")
        console.print("Try: bristlenose help commands | config | workflows")
        raise typer.Exit(1)


def _help_overview() -> None:
    console.print(f"\n[bold]bristlenose[/bold] {__version__}")
    console.print("User-research transcription and quote extraction engine.\n")
    console.print("[bold]Commands[/bold]")
    console.print("  run               Full pipeline: transcribe → analyse → render")
    console.print("  transcribe-only   Transcription only, no LLM calls")
    console.print("  analyze           LLM analysis on existing transcripts")
    console.print("  render            Re-render reports from intermediate JSON")
    console.print("  doctor            Check dependencies and configuration")
    console.print("  help              This help (try: help commands, help config, help workflows)")
    console.print()
    console.print("[bold]Quick start[/bold]")
    console.print("  bristlenose run ./interviews/ -o ./results/")
    console.print()
    console.print("[bold]More info[/bold]")
    console.print("  bristlenose help commands     All commands and their options")
    console.print("  bristlenose help config       Environment variables and config files")
    console.print("  bristlenose help workflows    Common usage patterns")
    console.print("  bristlenose <command> --help  Detailed options for a command")
    console.print()
    console.print("[dim]By Martin Storey · https://github.com/cassiocassio/bristlenose[/dim]")


def _help_commands() -> None:
    console.print("\n[bold]Commands[/bold]\n")
    console.print("[bold]bristlenose run[/bold] <input-dir> [options]")
    console.print("  Full pipeline. Transcribes recordings, extracts and enriches quotes")
    console.print("  via LLM, groups by screen and theme, renders HTML + Markdown reports.")
    console.print("  -o, --output DIR         Output directory (default: output)")
    console.print("  -p, --project NAME       Project name for the report header")
    console.print("  -b, --whisper-backend    auto | mlx | faster-whisper")
    console.print("  -w, --whisper-model      tiny | base | small | medium | large-v3 | large-v3-turbo")
    console.print("  -l, --llm               anthropic (Claude) | openai (ChatGPT)")
    console.print("  --redact-pii            Redact personally identifying information")
    console.print("  --retain-pii            Retain PII in transcripts (default)")
    console.print("  --clean                 Delete output dir before running")
    console.print("  -v, --verbose           Verbose logging")
    console.print()
    console.print("[bold]bristlenose transcribe-only[/bold] <input-dir> [options]")
    console.print("  Transcription only. No LLM calls, no API key needed.")
    console.print("  Produces raw transcripts in output/raw_transcripts/.")
    console.print("  -o, --output DIR         Output directory")
    console.print("  -w, --whisper-model      Whisper model size")
    console.print("  -v, --verbose           Verbose logging")
    console.print()
    console.print("[bold]bristlenose analyze[/bold] <transcripts-dir> [options]")
    console.print("  LLM analysis on existing .txt transcripts. Skips transcription.")
    console.print("  -o, --output DIR         Output directory")
    console.print("  -p, --project NAME       Project name")
    console.print("  -l, --llm               LLM provider")
    console.print("  -v, --verbose           Verbose logging")
    console.print()
    console.print("[bold]bristlenose render[/bold] <input-dir> [options]")
    console.print("  Re-render reports from intermediate/ JSON. No transcription,")
    console.print("  no LLM calls, no API key needed. Useful after CSS/JS changes.")
    console.print("  -o, --output DIR         Output directory (must contain intermediate/)")
    console.print("  -p, --project NAME       Project name")
    console.print("  -v, --verbose           Verbose logging")
    console.print()
    console.print("[bold]bristlenose doctor[/bold]")
    console.print("  Check dependencies, API keys, and system configuration.")
    console.print("  Runs automatically on first use; re-run anytime to diagnose issues.")
    console.print()


def _help_config() -> None:
    console.print("\n[bold]Configuration[/bold]\n")
    console.print("Settings are loaded in order (last wins):")
    console.print("  1. Defaults")
    console.print("  2. .env file (searched upward from CWD)")
    console.print("  3. Environment variables (prefix BRISTLENOSE_)")
    console.print("  4. CLI flags")
    console.print()
    console.print("[bold]Environment variables[/bold]\n")
    console.print("  [bold]API keys[/bold] (you only need one)")
    console.print("  BRISTLENOSE_ANTHROPIC_API_KEY    Claude API key (from console.anthropic.com)")
    console.print("  BRISTLENOSE_OPENAI_API_KEY       ChatGPT API key (from platform.openai.com)")
    console.print()
    console.print("  [bold]LLM[/bold]")
    console.print("  BRISTLENOSE_LLM_PROVIDER         anthropic (Claude) | openai (ChatGPT)")
    console.print("  BRISTLENOSE_LLM_MODEL            Model name (default: claude-sonnet-4-20250514)")
    console.print("  BRISTLENOSE_LLM_MAX_TOKENS       Max response tokens (default: 8192)")
    console.print("  BRISTLENOSE_LLM_TEMPERATURE      Temperature (default: 0.1)")
    console.print("  BRISTLENOSE_LLM_CONCURRENCY      Parallel LLM calls (default: 3)")
    console.print()
    console.print("  [bold]Transcription[/bold]")
    console.print("  BRISTLENOSE_WHISPER_BACKEND      auto | mlx | faster-whisper")
    console.print("  BRISTLENOSE_WHISPER_MODEL         Model size (default: large-v3-turbo)")
    console.print("  BRISTLENOSE_WHISPER_LANGUAGE      Language code (default: en)")
    console.print("  BRISTLENOSE_WHISPER_DEVICE        cpu | cuda | auto (faster-whisper only)")
    console.print("  BRISTLENOSE_WHISPER_COMPUTE_TYPE  int8 | float16 | float32")
    console.print()
    console.print("  [bold]PII[/bold]")
    console.print("  BRISTLENOSE_PII_ENABLED           true | false (default: false)")
    console.print("  BRISTLENOSE_PII_LLM_PASS          Extra LLM PII pass (default: false)")
    console.print("  BRISTLENOSE_PII_CUSTOM_NAMES      Comma-separated names to redact")
    console.print()
    console.print("  [bold]Pipeline[/bold]")
    console.print("  BRISTLENOSE_MIN_QUOTE_WORDS       Minimum words per quote (default: 5)")
    console.print("  BRISTLENOSE_MERGE_SPEAKER_GAP_SECONDS  Speaker merge gap (default: 2.0)")
    console.print()
    console.print("See .env.example in the repository for a template.")
    console.print()


def _help_workflows() -> None:
    console.print("\n[bold]Common workflows[/bold]\n")
    console.print("[bold]1. Full run[/bold] (most common)")
    console.print("   bristlenose run ./interviews/ -o ./results/ -p 'Q1 Study'")
    console.print("   → transcribe → analyse → render")
    console.print()
    console.print("[bold]2. Transcribe first, analyse later[/bold]")
    console.print("   bristlenose transcribe-only ./interviews/ -o ./results/")
    console.print("   # review raw_transcripts/, then:")
    console.print("   bristlenose analyze ./results/raw_transcripts/ -o ./results/")
    console.print()
    console.print("[bold]3. Re-render after CSS/JS changes[/bold]")
    console.print("   bristlenose render ./interviews/ -o ./results/")
    console.print("   # no LLM calls, no API key needed")
    console.print()
    console.print("[bold]4. Use ChatGPT instead of Claude[/bold]")
    console.print("   bristlenose run ./interviews/ -o ./results/ --llm openai")
    console.print()
    console.print("[bold]5. Smaller Whisper model (faster, less accurate)[/bold]")
    console.print("   bristlenose run ./interviews/ -o ./results/ -w small")
    console.print()
    console.print("[bold]6. Redact PII from transcripts[/bold]")
    console.print("   bristlenose run ./interviews/ -o ./results/ --redact-pii")
    console.print()
    console.print("[bold]7. Check your setup[/bold]")
    console.print("   bristlenose doctor")
    console.print()
    console.print("[bold]Input files[/bold]")
    console.print("  Audio: .wav .mp3 .m4a .flac .ogg .wma .aac")
    console.print("  Video: .mp4 .mov .avi .mkv .webm")
    console.print("  Subtitles: .srt .vtt")
    console.print("  Transcripts: .docx (Teams exports)")
    console.print("  Files sharing a name stem are treated as one session.")
    console.print()


# ---------------------------------------------------------------------------
# Doctor
# ---------------------------------------------------------------------------

_DOCTOR_SENTINEL_DIR = Path("~/.config/bristlenose").expanduser()
_DOCTOR_SENTINEL_FILE = _DOCTOR_SENTINEL_DIR / ".doctor-ran"


def _doctor_sentinel_dir() -> Path:
    """Return sentinel directory, respecting $SNAP_USER_COMMON."""
    import os

    snap_common = os.environ.get("SNAP_USER_COMMON")
    if snap_common:
        return Path(snap_common)
    return _DOCTOR_SENTINEL_DIR


def _doctor_sentinel_file() -> Path:
    return _doctor_sentinel_dir() / ".doctor-ran"


def _should_auto_doctor() -> bool:
    """Check if auto-doctor should run (first run or version changed)."""
    sentinel = _doctor_sentinel_file()
    if not sentinel.exists():
        return True
    try:
        content = sentinel.read_text().strip()
        return content != __version__
    except OSError:
        return True


def _write_doctor_sentinel() -> None:
    """Write the sentinel file after a successful auto-doctor."""
    sentinel = _doctor_sentinel_file()
    try:
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text(__version__)
    except OSError:
        pass  # non-critical


def _format_doctor_table(report: object) -> None:
    """Print the doctor results table using Rich."""
    from bristlenose.doctor import CheckStatus, DoctorReport

    assert isinstance(report, DoctorReport)

    for result in report.results:
        if result.status == CheckStatus.OK:
            status = "[dim green]ok[/dim green]"
        elif result.status == CheckStatus.WARN:
            status = "[bold yellow]!![/bold yellow]"
        elif result.status == CheckStatus.FAIL:
            status = "[bold yellow]!![/bold yellow]"
        else:
            status = "[dim]--[/dim]"

        label = f"{result.label:<16}"
        detail = f"[dim]{result.detail}[/dim]" if result.detail else ""
        console.print(f"  {label}{status}   {detail}")


def _print_doctor_fixes(report: object) -> None:
    """Print fix instructions for failures and notes for skipped checks."""
    from bristlenose.doctor import DoctorReport
    from bristlenose.doctor_fixes import get_fix

    assert isinstance(report, DoctorReport)

    failures = report.failures
    warnings = report.warnings
    notes = report.notes

    if failures:
        count = len(failures)
        label = "issue" if count == 1 else "issues"
        console.print(f"\n{count} {label}:\n")
        for result in failures:
            fix = get_fix(result.fix_key)
            if fix:
                console.print(f"  [bold]{result.label}[/bold]: {fix}\n")

    if warnings:
        count = len(warnings)
        label = "warning" if count == 1 else "warnings"
        console.print(f"\n{count} {label}:\n")
        for result in warnings:
            fix = get_fix(result.fix_key)
            if fix:
                console.print(f"  [bold]{result.label}[/bold]: {fix}\n")

    if notes:
        count = len(notes)
        label = "note" if count == 1 else "notes"
        console.print(f"\n{count} {label}:\n")
        for result in notes:
            if result.detail:
                console.print(f"  {result.label}: {result.detail}")


@app.command()
def doctor() -> None:
    """Check dependencies, API keys, and system configuration."""
    from bristlenose.doctor import run_all

    settings = load_settings()

    console.print(f"\nbristlenose {__version__}\n")

    report = run_all(settings)
    _format_doctor_table(report)

    if not report.has_failures and not report.has_warnings:
        console.print("\n[dim green]All clear.[/dim green]")
    else:
        _print_doctor_fixes(report)

    # Always update sentinel on explicit doctor
    _write_doctor_sentinel()
    console.print()


def _maybe_auto_doctor(settings: object, command: str) -> None:
    """Run auto-doctor on first invocation or after version change.

    If any check fails, print the table and exit. If all pass, write the
    sentinel and continue silently.
    """
    from bristlenose.config import BristlenoseSettings
    from bristlenose.doctor import run_preflight

    assert isinstance(settings, BristlenoseSettings)

    if not _should_auto_doctor():
        return

    console.print("\n[dim]First run — checking your setup.[/dim]\n")

    report = run_preflight(settings, command)
    _format_doctor_table(report)

    if report.has_failures:
        _print_doctor_fixes(report)
        console.print()
        raise typer.Exit(1)

    # Passed — write sentinel
    _write_doctor_sentinel()
    console.print("\n[dim green]All clear.[/dim green]\n")


def _run_preflight(settings: object, command: str, *, skip_transcription: bool = False) -> None:
    """Run pre-flight checks on every pipeline invocation.

    Unlike auto-doctor, this is terse: only prints the first failure and exits.
    """
    from bristlenose.config import BristlenoseSettings
    from bristlenose.doctor import run_preflight

    assert isinstance(settings, BristlenoseSettings)

    report = run_preflight(settings, command, skip_transcription=skip_transcription)

    if not report.has_failures:
        return

    # Terse output: first failure only, with fix
    from bristlenose.doctor_fixes import get_fix

    failure = report.failures[0]
    console.print()
    console.print(f"[bold yellow]{failure.detail}[/bold yellow]")
    fix = get_fix(failure.fix_key)
    if fix:
        console.print(f"\n{fix}")
    console.print(
        "\n[dim]Run [bold]bristlenose doctor[/bold] for full diagnostics.[/dim]"
    )
    console.print()
    raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Pipeline commands
# ---------------------------------------------------------------------------


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
        typer.Option("--llm", "-l", help="LLM provider: anthropic (Claude) or openai (ChatGPT)."),
    ] = "anthropic",
    skip_transcription: Annotated[
        bool,
        typer.Option("--skip-transcription", help="Skip audio transcription."),
    ] = False,
    redact_pii: Annotated[
        bool,
        typer.Option("--redact-pii", help="Redact personally identifying information from transcripts."),
    ] = False,
    retain_pii: Annotated[
        bool,
        typer.Option("--retain-pii", help="Retain PII in transcripts (default behaviour)."),
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

    if redact_pii and retain_pii:
        console.print("[red]Cannot use both --redact-pii and --retain-pii.[/red]")
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
        pii_enabled=redact_pii,
    )

    _maybe_auto_doctor(settings, "run")
    _run_preflight(settings, "run", skip_transcription=skip_transcription)

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

    _maybe_auto_doctor(settings, "transcribe-only")
    _run_preflight(settings, "transcribe-only")

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
        typer.Option("--llm", "-l", help="LLM provider: anthropic (Claude) or openai (ChatGPT)."),
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

    _maybe_auto_doctor(settings, "analyze")
    _run_preflight(settings, "analyze")

    from bristlenose.pipeline import Pipeline

    pipeline = Pipeline(settings, verbose=verbose)
    result = asyncio.run(pipeline.run_analysis_only(transcripts_dir, output_dir))

    console.print(f"\n[bold green]Done.[/bold green] Output written to {result.output_dir}")
    console.print(f"  Screen clusters: {len(result.screen_clusters)}")
    console.print(f"  Themes: {len(result.theme_groups)}")
    console.print(f"  Final report: {result.output_dir / 'research_report.md'}")
    console.print(f"  HTML report:  {result.output_dir / 'research_report.html'}")


@app.command()
def render(
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
        typer.Option("--output", "-o", help="Output directory (must contain intermediate/ JSON from a previous run)."),
    ] = Path("output"),
    project_name: Annotated[
        str | None,
        typer.Option("--project", "-p", help="Name of the research project (defaults to input folder name)."),
    ] = None,
    clean: Annotated[
        bool,
        typer.Option("--clean", help="Accepted for consistency but ignored — render is always non-destructive."),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logging."),
    ] = False,
) -> None:
    """Re-render the HTML and Markdown reports from existing intermediate data.

    No transcription or LLM calls. Useful after CSS/JS changes or to regenerate
    reports without re-processing.
    """
    if clean:
        console.print(
            "[dim]--clean ignored — render is always non-destructive "
            "(overwrites reports only, never touches transcripts, "
            "people.yaml, or intermediate data).[/dim]"
        )
    if project_name is None:
        project_name = input_dir.resolve().name

    settings = load_settings(
        output_dir=output_dir,
        project_name=project_name,
    )

    # render: no auto-doctor, no pre-flight (reads JSON, writes HTML, needs nothing external)

    from bristlenose.pipeline import Pipeline

    pipeline = Pipeline(settings, verbose=verbose)
    result = pipeline.run_render_only(output_dir, input_dir)

    console.print(f"\n[bold green]Done.[/bold green] Reports re-rendered in {result.output_dir}")
    console.print(f"  Screen clusters: {len(result.screen_clusters)}")
    console.print(f"  Themes: {len(result.theme_groups)}")
    console.print(f"  Final report: {result.output_dir / 'research_report.md'}")
    console.print(f"  HTML report:  {result.output_dir / 'research_report.html'}")
