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
_COMMANDS = {
    "run", "transcribe", "analyze", "analyse", "render", "doctor", "help", "configure", "serve",
    "status",
}


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


def _maybe_auto_doctor(settings: object, command: str) -> bool:
    """Run auto-doctor on first invocation or after version change.

    If any check fails, print the table and exit. If all pass, write the
    sentinel and continue.

    Returns True if auto-doctor ran (so the caller can skip the preflight,
    which would duplicate the same checks).
    """
    from bristlenose.config import BristlenoseSettings
    from bristlenose.doctor import run_preflight

    assert isinstance(settings, BristlenoseSettings)

    if not _should_auto_doctor():
        return False

    console.print("[dim]Checking your setup[/dim]")

    report = run_preflight(settings, command)
    _format_doctor_table(report)

    if report.has_failures:
        _print_doctor_fixes(report)
        console.print()
        raise typer.Exit(1)

    # Passed — write sentinel
    _write_doctor_sentinel()
    return True


def _run_preflight(settings: object, command: str, *, skip_transcription: bool = False) -> None:
    """Run pre-flight checks on every pipeline invocation.

    Always prints the full doctor table so the user sees their setup context.
    Exits on failure with fix instructions.
    """
    from bristlenose.config import BristlenoseSettings
    from bristlenose.doctor import run_preflight

    assert isinstance(settings, BristlenoseSettings)

    console.print("[dim]Checking your setup[/dim]")

    report = run_preflight(settings, command, skip_transcription=skip_transcription)
    _format_doctor_table(report)

    if report.has_failures:
        _print_doctor_fixes(report)
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
    console.print("  [1] Claude API (best quality, ~$1.50/study)")
    console.print("      [dim]Get a key from console.anthropic.com[/dim]")
    console.print()
    console.print("  [2] ChatGPT API (good quality, ~$1.00/study)")
    console.print("      [dim]Get a key from platform.openai.com[/dim]")
    console.print()
    console.print("  [3] Azure OpenAI (enterprise)")
    console.print("      [dim]Requires Azure subscription[/dim]")
    console.print()
    console.print("  [4] Gemini API (budget, ~$0.20/study)")
    console.print("      [dim]Get a key from aistudio.google.com[/dim]")
    console.print()
    console.print("  [5] Local AI (free, private, slower)")
    console.print("      [dim]Requires Ollama — https://ollama.ai[/dim]")
    console.print()

    choice = Prompt.ask("Choice", choices=["1", "2", "3", "4", "5"], default="1")

    if choice == "1":
        console.print()
        console.print("Get your API key from: [link]https://console.anthropic.com/settings/keys[/link]")
        console.print("Then run:")
        console.print()
        console.print("  [bold]bristlenose configure claude[/bold]")
        console.print()
        return None
    elif choice == "2":
        console.print()
        console.print("Get your API key from: [link]https://platform.openai.com/api-keys[/link]")
        console.print("Then run:")
        console.print()
        console.print("  [bold]bristlenose configure chatgpt[/bold]")
        console.print()
        return None
    elif choice == "3":
        console.print()
        console.print("Set your Azure OpenAI credentials:")
        console.print()
        console.print("  [bold]export BRISTLENOSE_AZURE_ENDPOINT=https://your-resource.openai.azure.com/[/bold]")
        console.print("  [bold]export BRISTLENOSE_AZURE_DEPLOYMENT=your-deployment-name[/bold]")
        console.print("  [bold]bristlenose configure azure[/bold]")
        console.print()
        return None
    elif choice == "4":
        console.print()
        console.print("Get your API key from: [link]https://aistudio.google.com/apikey[/link]")
        console.print("Then run:")
        console.print()
        console.print("  [bold]bristlenose configure gemini[/bold]")
        console.print()
        return None
    else:  # choice == "5"
        return _setup_local_provider()


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
# Pipeline header and summary output
# ---------------------------------------------------------------------------


def _print_header(settings: object, *, show_provider: bool = True, show_hardware: bool = True) -> None:
    """Print the Bristlenose version + provider + hardware header line."""
    from bristlenose.providers import PROVIDERS
    from bristlenose.utils.hardware import detect_hardware

    parts: list[str] = [f"v{__version__}"]
    if show_provider:
        provider_name = PROVIDERS.get(
            settings.llm_provider, PROVIDERS["anthropic"]  # type: ignore[union-attr]
        ).display_name
        parts.append(provider_name)
    if show_hardware:
        hw = detect_hardware()
        parts.append(hw.label)
    console.print(f"\nBristlenose [dim]{' · '.join(parts)}[/dim]\n")


def _print_pipeline_summary(result: object) -> None:
    """Print a clean summary after any pipeline command.

    Adapts to the fields available on the result (LLM usage, timing, etc.).
    """
    from bristlenose.llm.pricing import PRICING_URLS, estimate_cost
    from bristlenose.pipeline import _format_duration

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
        console.print(f"\n  [dim]{' · '.join(parts)}[/dim]")

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
            console.print(f"  [dim]Pricing → [link={url}]{url}[/link][/dim]")

    # Report path with OSC 8 file:// hyperlink (show filename only, link resolves)
    report_path = getattr(result, "report_path", None)
    if report_path and report_path.exists():
        file_url = f"file://{report_path.resolve()}"
        console.print(f"\n  Report:  [link={file_url}]{report_path.name}[/link]")

    # Done line — always last
    elapsed = getattr(result, "elapsed_seconds", 0.0)
    llm_ran = getattr(result, "llm_calls", 0) > 0
    no_quotes = getattr(result, "total_quotes", 0) == 0
    has_errors = llm_ran and no_quotes

    if has_errors:
        time_str = f" in {_format_duration(elapsed)}" if elapsed else ""
        console.print(
            f"\n  [red]Finished with errors[/red]{time_str}"
            " — 0 quotes extracted (check API credits or logs)"
        )
    elif elapsed:
        console.print(f"\n  [green]Done[/green] in {_format_duration(elapsed)}")
    else:
        console.print("\n  [green]Done.[/green]")


# ---------------------------------------------------------------------------
# Time estimation
# ---------------------------------------------------------------------------


def _build_estimator(settings: object) -> tuple[object, object]:
    """Build a TimingEstimator and an event callback for printing estimates.

    Returns (estimator, on_event) — both may be None if something goes wrong.
    """
    from bristlenose.timing import PipelineEvent, TimingEstimator, build_hardware_key

    try:
        hw_key = build_hardware_key(settings)  # type: ignore[arg-type]
        config_dir = _doctor_sentinel_dir()
        estimator = TimingEstimator(hw_key, config_dir)
    except Exception:
        return None, None

    def _on_event(event: PipelineEvent) -> None:
        if event.kind == "estimate" and event.estimate is not None:
            console.print(f"\n   [dim]Estimated time: {event.estimate.range_str}[/dim]\n")
        # "remaining" events are still emitted (for future progress-bar UI)
        # but not printed to the CLI — the per-stage recalculation adds
        # visual noise without enough accuracy to be useful as text.

    return estimator, _on_event


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
        str | None,
        typer.Option(
            "--whisper-backend",
            "-b",
            help="Transcription backend: auto (detect hardware), mlx (Apple Silicon GPU), faster-whisper (CUDA/CPU). [default: auto]",
        ),
    ] = None,
    whisper_model: Annotated[
        str | None,
        typer.Option(
            "--whisper-model",
            "-w",
            help="Whisper model size: tiny, base, small, medium, large-v3, large-v3-turbo. [default: large-v3-turbo]",
        ),
    ] = None,
    llm_provider: Annotated[
        str,
        typer.Option("--llm", "-l", help="LLM provider: claude, chatgpt, azure, gemini, local."),
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

    # Fail early if output exists and --clean not given — but allow resume
    # when a pipeline manifest exists (Phase 1c/1d crash recovery).
    output_exists = output_dir.exists() and any(output_dir.iterdir())
    if output_exists and not clean:
        from bristlenose.manifest import load_manifest

        if load_manifest(output_dir) is None:
            console.print(
                f"[red]Output directory already exists: {output_dir}[/red]\n"
                f"Use [bold]--clean[/bold] to delete it and re-run."
            )
            raise typer.Exit(1)

        # Print a one-line resume summary from the manifest (Phase 1e)
        from bristlenose.status import format_resume_summary, get_project_status

        _status = get_project_status(output_dir)
        if _status is not None:
            console.print(f"[dim]{format_resume_summary(_status)}[/dim]")
        else:
            console.print("[dim]Resuming from previous run...[/dim]")

    if redact_pii and retain_pii:
        console.print("[red]Cannot use both --redact-pii and --retain-pii.[/red]")
        raise typer.Exit(1)

    if project_name is None:
        project_name = input_dir.resolve().name

    settings_kwargs: dict[str, object] = {
        "input_dir": input_dir,
        "output_dir": output_dir,
        "project_name": project_name,
        "llm_provider": llm_provider,
        "skip_transcription": skip_transcription,
        "pii_enabled": redact_pii,
    }
    # Only pass whisper options if explicitly set on the CLI — otherwise let
    # env vars (BRISTLENOSE_WHISPER_MODEL, BRISTLENOSE_WHISPER_BACKEND) or
    # config-file defaults take effect.
    if whisper_backend is not None:
        settings_kwargs["whisper_backend"] = whisper_backend
    if whisper_model is not None:
        settings_kwargs["whisper_model"] = whisper_model
    settings = load_settings(**settings_kwargs)

    # Offer provider selection if no API key / local provider is not ready
    settings = _maybe_prompt_for_provider(settings)

    # Header is the first visible output
    _print_header(settings)

    if not _maybe_auto_doctor(settings, "run"):
        _run_preflight(settings, "run", skip_transcription=skip_transcription)

    # Clean after checks so user sees setup context first
    if output_exists and clean:
        import shutil

        shutil.rmtree(output_dir)
        console.print(f"\n[dim]Cleaned {output_dir}[/dim]")

    from bristlenose.pipeline import Pipeline

    estimator, on_event = _build_estimator(settings)
    pipeline = Pipeline(settings, verbose=verbose, on_event=on_event, estimator=estimator)
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
        str | None,
        typer.Option("--whisper-model", "-w", help="Whisper model size. [default: large-v3-turbo]"),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logging."),
    ] = False,
) -> None:
    """Only run transcription (no LLM analysis). Produces raw transcripts."""
    # Default output location: inside the input folder
    if output_dir is None:
        output_dir = input_dir / "bristlenose-output"

    settings_kwargs: dict[str, object] = {
        "output_dir": output_dir,
        "skip_transcription": False,
    }
    if whisper_model is not None:
        settings_kwargs["whisper_model"] = whisper_model
    settings = load_settings(**settings_kwargs)

    _print_header(settings, show_provider=False)

    if not _maybe_auto_doctor(settings, "transcribe-only"):
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
        typer.Option("--llm", "-l", help="LLM provider: claude, chatgpt, azure, gemini, local."),
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

    _print_header(settings)

    if not _maybe_auto_doctor(settings, "analyze"):
        _run_preflight(settings, "analyze")

    from bristlenose.pipeline import Pipeline

    estimator, on_event = _build_estimator(settings)
    pipeline = Pipeline(settings, verbose=verbose, on_event=on_event, estimator=estimator)
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

    # Check that the directory actually exists first
    if not output_dir.exists():
        console.print(f"[red]Directory {output_dir} not found.[/red]")
        raise typer.Exit(1)

    # Validate that intermediate exists (try new layout first, then legacy)
    # Also handle case where user passes input dir instead of output dir
    intermediate_dir = output_dir / ".bristlenose" / "intermediate"
    if not intermediate_dir.exists():
        intermediate_dir = output_dir / "intermediate"
    if not intermediate_dir.exists():
        # User might have passed the input dir — check for bristlenose-output/ inside
        nested_output = output_dir / "bristlenose-output"
        if (nested_output / ".bristlenose" / "intermediate").exists():
            output_dir = nested_output
            intermediate_dir = nested_output / ".bristlenose" / "intermediate"
        else:
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

    # Recover project name from metadata written by a previous run
    if project_name is None:
        from bristlenose.stages.render_output import read_pipeline_metadata

        meta = read_pipeline_metadata(output_dir)
        project_name = meta.get("project_name")

    # Fallback: derive from directory name (pre-metadata output dirs)
    if project_name is None:
        if output_dir.name in ("bristlenose-output", "output"):
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
# Serve command (FastAPI web server)
# ---------------------------------------------------------------------------


def _auto_render(project_dir: Path) -> None:
    """Re-render the HTML report from intermediate data before serving.

    Fast (<0.1s) and ensures the served HTML always matches the current
    render_html.py code — no stale mount-point markers or missing CSS.
    """
    output_dir = project_dir / "bristlenose-output"
    if not output_dir.is_dir():
        output_dir = project_dir
    intermediate = output_dir / ".bristlenose" / "intermediate"
    if not intermediate.is_dir():
        intermediate = output_dir / "intermediate"
    if not intermediate.is_dir():
        return  # No intermediate data — nothing to render

    # Resolve input_dir (for video linking) — same heuristic as render command
    if output_dir.name == "bristlenose-output":
        input_dir = output_dir.resolve().parent
    else:
        input_dir = output_dir.resolve().parent

    # Recover project name from pipeline metadata
    from bristlenose.stages.render_output import read_pipeline_metadata

    meta = read_pipeline_metadata(output_dir)
    project_name = meta.get("project_name")
    if project_name is None:
        if output_dir.name in ("bristlenose-output", "output"):
            project_name = output_dir.resolve().parent.name
        else:
            project_name = output_dir.resolve().name

    settings = load_settings(output_dir=output_dir, project_name=project_name)

    from bristlenose.pipeline import Pipeline

    pipeline = Pipeline(settings, verbose=False)
    result = pipeline.run_render_only(output_dir, input_dir)
    console.print(f" [dim]✓ Rendered report[/dim]  {result.total_quotes} quotes")


@app.command()
def serve(
    project_dir: Annotated[
        Path | None,
        typer.Argument(
            help="Directory containing bristlenose-output/ from a previous run.",
        ),
    ] = None,
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port to serve on."),
    ] = 8150,
    dev: Annotated[
        bool,
        typer.Option("--dev", help="Development mode: auto-reload on Python changes."),
    ] = False,
    open_browser: Annotated[
        bool,
        typer.Option("--open/--no-open", help="Open the report in the default browser."),
    ] = True,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logging."),
    ] = False,
) -> None:
    """Launch the Bristlenose web server to browse reports interactively."""
    try:
        import uvicorn  # noqa: F401 — test that serve deps are installed
    except ImportError:
        console.print("[red]Server dependencies not installed.[/red]")
        console.print("Install with: [bold]pip install bristlenose[serve][/bold]")
        raise typer.Exit(1)

    import threading
    import webbrowser

    # Re-render the HTML report before serving so it always matches the
    # current code (templates, CSS, JS).  This is fast (<0.1s) and avoids
    # stale-HTML surprises (e.g. missing mount-point markers).
    if project_dir is not None:
        _auto_render(project_dir)

    report_url = f"http://127.0.0.1:{port}/report/"
    console.print(f"\n  Report: [bold cyan]{report_url}[/bold cyan]\n")

    # Open the report in the default browser after a short delay so the
    # server has time to start.  If the tab is already open the browser
    # will refresh it (on macOS at least).
    def _open_browser() -> None:
        import time

        time.sleep(1.0)
        webbrowser.open(report_url)

    if open_browser:
        threading.Thread(target=_open_browser, daemon=True).start()

    if dev:
        # In dev mode uvicorn uses a string factory and calls create_app()
        # itself (needed for reload). Stash project_dir in the environment
        # so the factory can recover it.
        import os

        if project_dir is not None:
            os.environ["_BRISTLENOSE_PROJECT_DIR"] = str(project_dir.resolve())
        os.environ["_BRISTLENOSE_DEV"] = "1"
        os.environ["_BRISTLENOSE_PORT"] = str(port)
        if verbose:
            os.environ["_BRISTLENOSE_VERBOSE"] = "1"

        uvicorn.run(
            "bristlenose.server.app:create_app",
            host="127.0.0.1",
            port=port,
            reload=True,
            factory=True,
            log_level="info" if verbose else "warning",
        )
    else:
        from bristlenose.server.app import create_app

        app_instance = create_app(project_dir=project_dir, verbose=verbose)

        uvicorn.run(
            app_instance,
            host="127.0.0.1",
            port=port,
            log_level="info" if verbose else "warning",
        )


# ---------------------------------------------------------------------------
# Status command
# ---------------------------------------------------------------------------


@app.command()
def status(
    project_dir: Annotated[
        Path,
        typer.Argument(help="Input directory (or output directory) from a previous run."),
    ],
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show per-session detail."),
    ] = False,
) -> None:
    """Show pipeline status for a project (read-only, no LLM calls)."""
    from bristlenose.status import get_project_status

    # Resolve output directory — accept either input dir or output dir
    output_dir = _resolve_output_dir(project_dir)
    if output_dir is None:
        console.print(
            f"No pipeline data found in [bold]{project_dir}[/bold].\n"
            f"Run [bold]bristlenose run {project_dir}[/bold] to start."
        )
        raise typer.Exit(1)

    project_status = get_project_status(output_dir)
    if project_status is None:
        console.print(
            f"No pipeline manifest in [bold]{output_dir}[/bold].\n"
            f"Run [bold]bristlenose run {project_dir}[/bold] to start."
        )
        raise typer.Exit(1)

    _print_project_status(project_status, output_dir=output_dir, verbose=verbose)


def _resolve_output_dir(project_dir: Path) -> Path | None:
    """Find the output directory from an input dir or output dir path.

    Returns the output directory (the one containing ``.bristlenose/``),
    or None if no pipeline data is found.
    """
    # Direct: project_dir is the output dir
    if (project_dir / ".bristlenose").is_dir():
        return project_dir

    # Standard layout: input_dir/bristlenose-output/
    nested = project_dir / "bristlenose-output"
    if (nested / ".bristlenose").is_dir():
        return nested

    # Legacy layout: output/ directory
    legacy = project_dir / "output"
    if (legacy / ".bristlenose").is_dir():
        return legacy

    return None


def _print_project_status(
    project_status: ProjectStatus,  # noqa: F821 — lazy import
    *,
    output_dir: Path | None = None,
    verbose: bool = False,
) -> None:
    """Print formatted project status to the console."""
    from datetime import datetime

    from bristlenose.manifest import StageStatus

    # Header
    console.print(f"\n  [bold]{project_status.project_name}[/bold]")
    console.print(f"  [dim]Pipeline v{project_status.pipeline_version}[/dim]")

    # Format last run timestamp
    try:
        dt = datetime.fromisoformat(project_status.last_run)
        last_run_str = dt.strftime("%-d %b %Y %H:%M")
    except (ValueError, TypeError):
        last_run_str = project_status.last_run
    console.print(f"  [dim]Last run: {last_run_str}[/dim]\n")

    # Stages
    for info in project_status.stages:
        if info.status == StageStatus.COMPLETE:
            icon = "[green]✓[/green]"
        elif info.status in (StageStatus.PARTIAL, StageStatus.RUNNING):
            icon = "[yellow]⚠[/yellow]"
        else:
            icon = "[dim]✗[/dim]"

        detail = f"  [dim]{info.detail}[/dim]" if info.detail else ""
        name_padded = info.name.ljust(20)
        console.print(f"  {icon} {name_padded}{detail}")

        if not info.file_exists:
            console.print(f"    [dim yellow]{info.file_missing_warning}[/dim yellow]")

        # Per-session detail in verbose mode
        if verbose and output_dir and info.session_total and info.status != StageStatus.PENDING:
            from bristlenose.manifest import load_manifest

            manifest = load_manifest(output_dir)
            if manifest:
                record = manifest.stages.get(info.stage_key)
                if record and record.sessions:
                    for sid, sr in sorted(record.sessions.items()):
                        s_icon = (
                            "[green]✓[/green]"
                            if sr.status == StageStatus.COMPLETE
                            else "[dim]✗[/dim]"
                        )
                        provider_str = f"  [dim]({sr.model})[/dim]" if sr.model else ""
                        console.print(f"      {s_icon} {sid}{provider_str}")

    # Cost
    if project_status.total_cost_usd > 0:
        console.print(
            f"\n  [dim]Cost so far: ${project_status.total_cost_usd:.2f}[/dim]"
        )

    console.print()


# ---------------------------------------------------------------------------
# Utility commands (doctor, configure, help)
# ---------------------------------------------------------------------------


@app.command()
def configure(
    provider: Annotated[
        str,
        typer.Argument(help="Provider to configure: claude, chatgpt, gemini, or azure."),
    ],
    key: Annotated[
        str | None,
        typer.Option("--key", "-k", help="API key (if not provided, prompts interactively)."),
    ] = None,
) -> None:
    """Set up API credentials for an LLM provider.

    Validates the key with a test API call and stores it securely in
    your system credential store (macOS Keychain or Linux Secret Service).
    """
    from bristlenose.credentials import EnvCredentialStore, get_credential_store
    from bristlenose.doctor import (
        _validate_anthropic_key,
        _validate_openai_key,
    )

    provider = provider.lower()

    # Normalise aliases
    provider_map = {
        "anthropic": "anthropic",
        "claude": "anthropic",
        "openai": "openai",
        "chatgpt": "openai",
        "azure": "azure",
        "azure-openai": "azure",
        "google": "google",
        "gemini": "google",
    }
    canonical = provider_map.get(provider)
    if canonical is None:
        console.print(f"[red]Unknown provider: {provider}[/red]")
        console.print("Available: claude, chatgpt, gemini, azure")
        raise typer.Exit(1)

    display_names = {
        "anthropic": "Claude",
        "openai": "ChatGPT",
        "azure": "Azure OpenAI",
        "google": "Gemini",
    }
    display_name = display_names.get(canonical, canonical.title())

    # Get key from option or prompt
    if key is None:
        console.print()
        key = typer.prompt(f"Enter your {display_name} API key", hide_input=True)

    if not key.strip():
        console.print("[red]No key entered[/red]")
        raise typer.Exit(1)

    key = key.strip()

    # Validate
    console.print("Validating...", end=" ")
    if canonical == "anthropic":
        is_valid, error = _validate_anthropic_key(key)
    elif canonical == "openai":
        is_valid, error = _validate_openai_key(key)
    elif canonical == "google":
        from bristlenose.doctor import _validate_google_key

        is_valid, error = _validate_google_key(key)
    else:
        # Azure needs endpoint+deployment to validate fully; skip for now
        is_valid, error = None, "needs endpoint and deployment to validate"

    if is_valid is False:
        console.print(f"[red]Invalid — {error}[/red]")
        raise typer.Exit(1)
    elif is_valid is None:
        console.print(f"[yellow]Could not validate: {error}[/yellow]")
        console.print("Storing anyway...")
    else:
        console.print("[green]Valid[/green]")

    # Store in keychain
    store = get_credential_store()
    try:
        store.set(canonical, key)
        # Show where it was stored
        if isinstance(store, EnvCredentialStore):
            # Shouldn't happen on set() — it raises NotImplementedError
            pass
        else:
            from bristlenose.credentials import get_credential_store_label

            store_label = get_credential_store_label()
            service_name = f"Bristlenose {display_name} API Key"
            console.print(f'[green]Stored in {store_label} as "{service_name}"[/green]')
    except NotImplementedError:
        # EnvCredentialStore — can't persist
        console.print()
        console.print("[yellow]No system credential store available.[/yellow]")
        console.print("Add this to your .env file or shell profile:")
        console.print()
        env_vars = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "azure": "AZURE_API_KEY",
            "google": "GOOGLE_API_KEY",
        }
        env_var = env_vars.get(canonical, f"{canonical.upper()}_API_KEY")
        console.print(f"  export BRISTLENOSE_{env_var}={key}")
        console.print()
        console.print("[dim](The key is not stored anywhere — save it yourself)[/dim]")
        raise typer.Exit(0)

    # Azure needs additional config beyond the API key
    if canonical == "azure":
        console.print()
        console.print("[dim]Azure OpenAI also needs endpoint and deployment name.[/dim]")
        console.print("[dim]Add to .env or environment:[/dim]")
        console.print()
        console.print("  BRISTLENOSE_AZURE_ENDPOINT=https://your-resource.openai.azure.com/")
        console.print("  BRISTLENOSE_AZURE_DEPLOYMENT=your-deployment-name")

    console.print()
    console.print("You can now run: [bold]bristlenose run ./interviews[/bold]")


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
    console.print("  -l, --llm               claude | chatgpt | azure | gemini | local")
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
    console.print("  BRISTLENOSE_AZURE_API_KEY        Azure OpenAI API key (from Azure portal)")
    console.print("  BRISTLENOSE_AZURE_ENDPOINT       Azure OpenAI endpoint URL")
    console.print("  BRISTLENOSE_AZURE_DEPLOYMENT     Azure OpenAI deployment name")
    console.print("  BRISTLENOSE_GOOGLE_API_KEY       Gemini API key (from aistudio.google.com)")
    console.print()
    console.print("  [bold]LLM[/bold]")
    console.print("  BRISTLENOSE_LLM_PROVIDER         claude | chatgpt | azure | gemini | local")
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
