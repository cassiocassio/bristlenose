"""Command-line interface for Bristlenose."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from bristlenose import __version__
from bristlenose.config import load_settings

# Known commands — used by _maybe_inject_run() to detect bare directory arguments
_COMMANDS = {"run", "transcribe", "analyze", "analyse", "render", "doctor", "help"}


def _maybe_inject_run() -> None:
    """If the first argument is a directory (not a command), inject 'run'.

    This allows `bristlenose project-ikea` as shorthand for `bristlenose run project-ikea`.
    """
    if len(sys.argv) < 2:
        return  # No arguments — let Typer show help

    first_arg = sys.argv[1]

    # Skip if it's a known command or a flag
    if first_arg in _COMMANDS or first_arg.startswith("-"):
        return

    # Check if it's an existing directory
    if Path(first_arg).is_dir():
        sys.argv.insert(1, "run")


# Inject 'run' before Typer parses arguments
_maybe_inject_run()

app = typer.Typer(
    name="bristlenose",
    help="User-research transcription and quote extraction engine.",
    no_args_is_help=True,
)
console = Console(width=min(80, Console().width))


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


# ---------------------------------------------------------------------------
# Doctor helpers (needed by pipeline commands)
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


def _install_man_page() -> None:
    """Install man page to ~/.local/share/man/man1/ for pip/pipx users.

    Skipped inside snap and Homebrew — those package managers handle their own
    man page installation.
    """
    import os
    import shutil
    import sys

    # Snap runtime installs man page via snapcraft.yaml.
    if os.environ.get("SNAP"):
        return

    # Homebrew installs man page via formula.
    exe = sys.executable or ""
    if "/homebrew/" in exe.lower() or "/Cellar/" in exe:
        return

    source = Path(__file__).resolve().parent / "data" / "bristlenose.1"
    if not source.exists():
        return

    man_dir = Path.home() / ".local" / "share" / "man" / "man1"
    try:
        man_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, man_dir / "bristlenose.1")
    except OSError:
        pass  # non-critical


def _write_doctor_sentinel() -> None:
    """Write the sentinel file after a successful auto-doctor."""
    sentinel = _doctor_sentinel_file()
    try:
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text(__version__)
    except OSError:
        pass  # non-critical
    _install_man_page()


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
    """Print fix instructions for failures only.

    The table already shows what passed/failed/skipped with details.
    We only need to print actionable fix instructions for failures.
    Notes and warnings are already visible in the table — no need to repeat.
    """
    from bristlenose.doctor import DoctorReport
    from bristlenose.doctor_fixes import get_fix

    assert isinstance(report, DoctorReport)

    failures = report.failures
    warnings = report.warnings

    # Only print fixes for failures — the table already shows the status
    all_fixable = failures + warnings
    if all_fixable:
        console.print()  # Blank line after table
        for result in all_fixable:
            fix = get_fix(result.fix_key)
            if fix:
                console.print(fix)
                console.print()  # Blank line between fixes


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
# Interactive first-run provider selection
# ---------------------------------------------------------------------------


def _needs_provider_prompt(settings: object) -> bool:
    """Check if we need to prompt the user to choose an LLM provider.

    Returns True ONLY if:
    - Provider is 'anthropic' (the default) AND no Anthropic key is set

    This catches the "no config at all" case where a first-time user runs
    bristlenose without any API key or provider choice.

    Note: We don't prompt for 'openai' or 'local' — if the user explicitly
    chose those (via --llm or env var), they know what they want. If it's
    not ready, preflight will catch it with a specific error.
    """
    from bristlenose.config import BristlenoseSettings

    assert isinstance(settings, BristlenoseSettings)

    # Only prompt for the default case: anthropic with no key
    # If user chose openai or local explicitly, don't second-guess them
    if settings.llm_provider == "anthropic" and not settings.anthropic_api_key:
        return True
    return False


def _prompt_for_provider() -> str | None:
    """Interactive prompt when no provider is configured.

    Returns the chosen provider name, or None if the user needs to
    set up an API key first.
    """
    from rich.prompt import Prompt


    console.print()
    console.print("[bold]No LLM provider configured.[/bold] Choose one:")
    console.print()
    console.print("  [1] Local AI (free, private, slower)")
    console.print("      [dim]Requires Ollama — https://ollama.ai[/dim]")
    console.print()
    console.print("  [2] Claude API (best quality, ~$1.50/study)")
    console.print("      [dim]Get a key from console.anthropic.com[/dim]")
    console.print()
    console.print("  [3] ChatGPT API (good quality, ~$1.00/study)")
    console.print("      [dim]Get a key from platform.openai.com[/dim]")
    console.print()

    choice = Prompt.ask("Choice", choices=["1", "2", "3"], default="1")

    if choice == "1":
        return _setup_local_provider()
    elif choice == "2":
        console.print()
        console.print("Get your API key from: [link]https://console.anthropic.com/settings/keys[/link]")
        console.print("Then run:")
        console.print()
        console.print("  [bold]export BRISTLENOSE_ANTHROPIC_API_KEY=sk-ant-...[/bold]")
        console.print()
        console.print("Or add it to a .env file in your project directory.")
        return None
    else:  # choice == "3"
        console.print()
        console.print("Get your API key from: [link]https://platform.openai.com/api-keys[/link]")
        console.print("Then run:")
        console.print()
        console.print("  [bold]export BRISTLENOSE_OPENAI_API_KEY=sk-...[/bold]")
        console.print()
        console.print("Or add it to a .env file in your project directory.")
        return None


def _setup_local_provider() -> str | None:
    """Set up local provider, installing Ollama and pulling model if needed.

    Returns 'local' if ready, or None if setup failed.
    """
    import webbrowser

    from rich.prompt import Confirm

    from bristlenose.ollama import (
        DEFAULT_MODEL,
        check_ollama,
        get_install_method,
        install_ollama,
        is_ollama_installed,
        pull_model,
        start_ollama_serve,
    )

    status = check_ollama()

    if not status.is_running:
        console.print()
        console.print("[yellow]Ollama is not running.[/yellow]")

        if is_ollama_installed():
            console.print()
            console.print("Starting Ollama...")
            if start_ollama_serve():
                console.print("[green]Ollama started.[/green]")
                status = check_ollama()  # Re-check status
            else:
                console.print()
                console.print("Could not start automatically. Run manually:")
                console.print()
                console.print("  [bold]ollama serve[/bold]")
                console.print()
                console.print("Then try again.")
                return None
        else:
            # Ollama not installed — offer to install it
            method = get_install_method()
            if method is not None:
                console.print()
                console.print("Ollama is not installed.")
                console.print("[dim](Free, open-source, no account needed)[/dim]")
                console.print()

                # Show what we'll run
                if method == "brew":
                    install_cmd = "brew install ollama"
                elif method == "snap":
                    install_cmd = "sudo snap install ollama"
                else:
                    install_cmd = "curl -fsSL https://ollama.ai/install.sh | sh"

                if Confirm.ask("Install Ollama now?", default=True):
                    console.print()
                    console.print(f"[dim]Running: {install_cmd}[/dim]")
                    console.print()
                    if install_ollama(method):
                        console.print()
                        console.print("[green]Ollama installed.[/green]")
                        console.print("Starting Ollama...")
                        if start_ollama_serve():
                            console.print("[green]Ollama started.[/green]")
                            status = check_ollama()
                        else:
                            console.print()
                            console.print("Installed but could not start. Run manually:")
                            console.print()
                            console.print("  [bold]ollama serve[/bold]")
                            console.print()
                            console.print("Then try again.")
                            return None
                    else:
                        # Installation failed — fall back to download page
                        console.print()
                        console.print("[red]Installation failed.[/red]")
                        console.print("Install manually from: [link]https://ollama.ai[/link]")
                        if Confirm.ask("Open the download page?", default=True):
                            webbrowser.open("https://ollama.ai")
                        return None
                else:
                    return None
            else:
                # No install method available (Windows or missing tools)
                console.print()
                console.print("Install Ollama from: [link]https://ollama.ai[/link]")
                console.print("[dim](Single download, no account needed)[/dim]")
                console.print()
                console.print("After installing, run:")
                console.print()
                console.print("  [bold]ollama pull llama3.2[/bold]")
                console.print()
                console.print("Then try again.")
                console.print()
                if Confirm.ask("Open the download page?", default=True):
                    webbrowser.open("https://ollama.ai")
                return None

    if not status.has_suitable_model:
        console.print()
        console.print("[yellow]Ollama is running but no suitable model found.[/yellow]")
        console.print()

        if Confirm.ask(f"Download {DEFAULT_MODEL} (2 GB)?", default=True):
            console.print()
            if pull_model(DEFAULT_MODEL):
                console.print()
                console.print(f"[green]Downloaded {DEFAULT_MODEL}[/green]")
                return "local"
            else:
                console.print()
                console.print("[red]Download failed.[/red]")
                console.print("Try manually: [bold]ollama pull llama3.2[/bold]")
                return None
        return None

    # Ready to go
    console.print()
    console.print(f"[green]Using local AI ({status.recommended_model})[/green]")
    console.print("[dim]This is slower than cloud APIs but completely free and private.[/dim]")
    console.print("[dim]For production quality: export BRISTLENOSE_ANTHROPIC_API_KEY=...[/dim]")
    console.print()

    return "local"


def _maybe_prompt_for_provider(settings: object) -> object:
    """Check if provider prompt is needed and return updated settings if so.

    Returns the original settings if no prompt needed, or new settings with
    the chosen provider if the user selected local.
    """
    from bristlenose.config import BristlenoseSettings, load_settings

    assert isinstance(settings, BristlenoseSettings)

    if not _needs_provider_prompt(settings):
        return settings

    provider = _prompt_for_provider()
    if provider is None:
        raise typer.Exit(0)

    # Reload settings with the chosen provider
    return load_settings(
        llm_provider=provider,
        input_dir=settings.input_dir,
        output_dir=settings.output_dir,
        project_name=settings.project_name,
        whisper_backend=settings.whisper_backend,
        whisper_model=settings.whisper_model,
        skip_transcription=settings.skip_transcription,
        pii_enabled=settings.pii_enabled,
    )


# ---------------------------------------------------------------------------
# Pipeline summary output
# ---------------------------------------------------------------------------


def _print_pipeline_summary(result: object) -> None:
    """Print a clean summary after any pipeline command.

    Adapts to the fields available on the result (LLM usage, timing, etc.).
    """
    from bristlenose.llm.pricing import PRICING_URLS, estimate_cost
    from bristlenose.pipeline import _format_duration

    elapsed = getattr(result, "elapsed_seconds", 0.0)
    if elapsed:
        console.print(f"\n  [green]Done[/green] in {_format_duration(elapsed)}\n")
    else:
        console.print("\n  [green]Done.[/green]\n")

    # Stats line — build dynamically from what's available
    parts: list[str] = []
    participants = getattr(result, "participants", [])
    if participants:
        parts.append(f"{len(participants)} participants")
    screen_clusters = getattr(result, "screen_clusters", [])
    if screen_clusters:
        parts.append(f"{len(screen_clusters)} screens")
    theme_groups = getattr(result, "theme_groups", [])
    if theme_groups:
        parts.append(f"{len(theme_groups)} themes")
    total_quotes = getattr(result, "total_quotes", 0)
    if total_quotes:
        parts.append(f"{total_quotes} quotes")
    if parts:
        console.print(f"  [dim]{' · '.join(parts)}[/dim]")

    # LLM usage line
    llm_calls = getattr(result, "llm_calls", 0)
    if llm_calls > 0:
        llm_in = getattr(result, "llm_input_tokens", 0)
        llm_out = getattr(result, "llm_output_tokens", 0)
        model = getattr(result, "llm_model", "")
        provider = getattr(result, "llm_provider", "")
        cost = estimate_cost(model, llm_in, llm_out)
        cost_str = f" · ~${cost:.2f}" if cost is not None else ""
        console.print(
            f"  [dim]LLM: {llm_in:,} in · {llm_out:,} out{cost_str} ({model})[/dim]"
        )
        url = PRICING_URLS.get(provider, "")
        if url:
            console.print(f"  [dim]Verify pricing → [link={url}]{url}[/link][/dim]")

    # Report path with OSC 8 file:// hyperlink
    output_dir = getattr(result, "output_dir", None)
    if output_dir:
        report_path = output_dir / "research_report.html"
        if report_path.exists():
            file_url = f"file://{report_path.resolve()}"
            console.print(f"\n  Report:  [link={file_url}]{report_path}[/link]")


# ---------------------------------------------------------------------------
# Pipeline commands (run, transcribe, analyze, render)
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
        Path | None,
        typer.Option("--output", "-o", help="Output directory (default: bristlenose-output/ inside input folder)."),
    ] = None,
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
        typer.Option("--llm", "-l", help="LLM provider: claude, chatgpt, local (or anthropic, openai, ollama)."),
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
    # Default output location: inside the input folder
    if output_dir is None:
        output_dir = input_dir / "bristlenose-output"

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

    # Offer provider selection if no API key / local provider is not ready
    settings = _maybe_prompt_for_provider(settings)

    _maybe_auto_doctor(settings, "run")
    _run_preflight(settings, "run", skip_transcription=skip_transcription)

    from bristlenose.pipeline import Pipeline

    pipeline = Pipeline(settings, verbose=verbose)
    result = asyncio.run(pipeline.run(input_dir, output_dir))

    _print_pipeline_summary(result)


@app.command(name="transcribe")
def transcribe(
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
        Path | None,
        typer.Option("--output", "-o", help="Output directory (default: bristlenose-output/ inside input folder)."),
    ] = None,
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
    # Default output location: inside the input folder
    if output_dir is None:
        output_dir = input_dir / "bristlenose-output"

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

    _print_pipeline_summary(result)
    # Transcript-specific: point to the transcripts dir, not the report
    raw_dir = result.output_dir / "transcripts-raw"
    if raw_dir.exists():
        console.print(f"\n  Transcripts  {raw_dir}")


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
        Path | None,
        typer.Option("--output", "-o", help="Output directory (default: parent of transcripts_dir, or bristlenose-output/ if transcripts_dir is named transcripts-raw)."),
    ] = None,
    project_name: Annotated[
        str | None,
        typer.Option("--project", "-p", help="Name of the research project (defaults to input folder name)."),
    ] = None,
    llm_provider: Annotated[
        str,
        typer.Option("--llm", "-l", help="LLM provider: claude, chatgpt, local (or anthropic, openai, ollama)."),
    ] = "anthropic",
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logging."),
    ] = False,
) -> None:
    """Run LLM analysis on existing transcripts (skip ingestion and transcription)."""
    # Default output location: if transcripts_dir is transcripts-raw/ inside a bristlenose-output,
    # use the parent; otherwise create bristlenose-output/ alongside transcripts_dir
    if output_dir is None:
        if transcripts_dir.name in ("transcripts-raw", "transcripts-cooked", "raw_transcripts", "cooked_transcripts"):
            output_dir = transcripts_dir.parent
        else:
            output_dir = transcripts_dir.parent / "bristlenose-output"

    if project_name is None:
        project_name = transcripts_dir.resolve().name

    settings = load_settings(
        output_dir=output_dir,
        project_name=project_name,
        llm_provider=llm_provider,
    )

    # Offer provider selection if no API key / local provider is not ready
    settings = _maybe_prompt_for_provider(settings)

    _maybe_auto_doctor(settings, "analyze")
    _run_preflight(settings, "analyze")

    from bristlenose.pipeline import Pipeline

    pipeline = Pipeline(settings, verbose=verbose)
    result = asyncio.run(pipeline.run_analysis_only(transcripts_dir, output_dir))

    _print_pipeline_summary(result)


# British English alias for analyze
analyse = app.command(name="analyse", hidden=True)(analyze)


@app.command()
def render(
    output_dir: Annotated[
        Path | None,
        typer.Argument(
            help="Output directory containing .bristlenose/intermediate/ from a previous run. "
                 "Defaults to ./bristlenose-output/ if it exists.",
        ),
    ] = None,
    input_dir: Annotated[
        Path | None,
        typer.Option("--input", "-i", help="Original input directory (for video linking). Auto-detected if possible."),
    ] = None,
    project_name: Annotated[
        str | None,
        typer.Option("--project", "-p", help="Name of the research project (defaults to directory name)."),
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
    # Auto-detect output directory
    if output_dir is None:
        # New layout: bristlenose-output/.bristlenose/intermediate/
        if (Path.cwd() / "bristlenose-output" / ".bristlenose" / "intermediate").exists():
            output_dir = Path("bristlenose-output")
        # Legacy layout: output/intermediate/ or output/.bristlenose/intermediate/
        elif (Path.cwd() / "output" / ".bristlenose" / "intermediate").exists():
            output_dir = Path("output")
        elif (Path.cwd() / "output" / "intermediate").exists():
            output_dir = Path("output")
        elif (Path.cwd() / ".bristlenose" / "intermediate").exists():
            output_dir = Path.cwd()
        elif (Path.cwd() / "intermediate").exists():
            output_dir = Path.cwd()
        else:
            console.print("[red]No intermediate data found.[/red]")
            console.print(
                "Run from a directory containing bristlenose-output/, "
                "or specify the output path as an argument."
            )
            raise typer.Exit(1)

    # Validate that intermediate exists (try new layout first, then legacy)
    intermediate_dir = output_dir / ".bristlenose" / "intermediate"
    if not intermediate_dir.exists():
        intermediate_dir = output_dir / "intermediate"
    if not intermediate_dir.exists():
        console.print(f"[red]No intermediate data in {output_dir}[/red]")
        console.print("Run 'bristlenose run' first to generate intermediate data.")
        raise typer.Exit(1)

    # Auto-detect input directory if not specified
    if input_dir is None:
        # New layout: output is inside input (interviews/bristlenose-output/)
        if output_dir.name == "bristlenose-output":
            input_dir = output_dir.resolve().parent
        else:
            # Legacy layout: input_dir is sibling of output_dir
            # e.g., project/interviews/ and project/output/
            project_root = output_dir.resolve().parent
            candidates = [
                d for d in project_root.iterdir()
                if d.is_dir() and d.name != output_dir.name and d.name not in ("output", "bristlenose-output")
            ]
            # Look for directories with media files
            for candidate in candidates:
                media_exts = {".mp4", ".mov", ".mp3", ".wav", ".m4a", ".vtt", ".srt", ".docx"}
                try:
                    if any(f.suffix.lower() in media_exts for f in candidate.iterdir() if f.is_file()):
                        input_dir = candidate
                        break
                except PermissionError:
                    continue

            if input_dir is None:
                # Fall back to project root (render will work but no video linking)
                input_dir = project_root

    if clean:
        console.print(
            "[dim]--clean ignored — render is always non-destructive "
            "(overwrites reports only, never touches transcripts, "
            "people.yaml, or intermediate data).[/dim]"
        )

    # Derive project name from the output directory's parent (the project root)
    if project_name is None:
        # If output_dir is "output", use parent dir name; otherwise use output_dir name
        if output_dir.name == "output":
            project_name = output_dir.resolve().parent.name
        else:
            project_name = output_dir.resolve().name

    settings = load_settings(
        output_dir=output_dir,
        project_name=project_name,
    )

    # render: no auto-doctor, no pre-flight (reads JSON, writes HTML, needs nothing external)

    from bristlenose.pipeline import Pipeline

    pipeline = Pipeline(settings, verbose=verbose)
    result = pipeline.run_render_only(output_dir, input_dir)

    _print_pipeline_summary(result)


# ---------------------------------------------------------------------------
# Utility commands (doctor, help)
# ---------------------------------------------------------------------------


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


@app.command(name="help")
def help_cmd(
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
    elif topic in ("run", "transcribe", "analyze", "analyse", "render", "doctor", "help"):
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
    console.print("  transcribe        Transcription only, no LLM calls")
    console.print("  analyze           LLM analysis on existing transcripts")
    console.print("  render            Re-render reports from intermediate JSON")
    console.print("  doctor            Check dependencies and configuration")
    console.print("  help              This help (try: help commands, help config, help workflows)")
    console.print()
    console.print("[bold]Quick start[/bold]")
    console.print("  bristlenose ./interviews/ -o ./results/")
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
    console.print("  -l, --llm               claude | chatgpt (or anthropic | openai)")
    console.print("  --redact-pii            Redact personally identifying information")
    console.print("  --retain-pii            Retain PII in transcripts (default)")
    console.print("  --clean                 Delete output dir before running")
    console.print("  -v, --verbose           Verbose logging")
    console.print()
    console.print("[bold]bristlenose transcribe[/bold] <input-dir> [options]")
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
    console.print("[bold]bristlenose render[/bold] [output-dir] [options]")
    console.print("  Re-render reports from intermediate/ JSON. No transcription,")
    console.print("  no LLM calls, no API key needed. Useful after CSS/JS changes.")
    console.print("  output-dir               Output directory (default: ./output/ if exists)")
    console.print("  -i, --input DIR          Original input directory (auto-detected)")
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
    console.print("  BRISTLENOSE_LLM_PROVIDER         claude | chatgpt (or anthropic | openai)")
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
    console.print("   bristlenose ./interviews/ -o ./results/ -p 'Q1 Study'")
    console.print("   → transcribe → analyse → render")
    console.print()
    console.print("[bold]2. Transcribe first, analyse later[/bold]")
    console.print("   bristlenose transcribe ./interviews/ -o ./results/")
    console.print("   # review raw_transcripts/, then:")
    console.print("   bristlenose analyze ./results/raw_transcripts/ -o ./results/")
    console.print()
    console.print("[bold]3. Re-render after CSS/JS changes[/bold]")
    console.print("   cd project-folder && bristlenose render")
    console.print("   # or: bristlenose render ./results/")
    console.print("   # no LLM calls, no API key needed")
    console.print()
    console.print("[bold]4. Use ChatGPT instead of Claude[/bold]")
    console.print("   bristlenose ./interviews/ --llm chatgpt")
    console.print()
    console.print("[bold]5. Smaller Whisper model (faster, less accurate)[/bold]")
    console.print("   bristlenose ./interviews/ -w small")
    console.print()
    console.print("[bold]6. Redact PII from transcripts[/bold]")
    console.print("   bristlenose ./interviews/ --redact-pii")
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
