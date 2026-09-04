"""Command-line interface for Bristlenose."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from bristlenose import __version__
from bristlenose.config import load_settings
from bristlenose.cost import compute_run_cost
from bristlenose.events import KindEnum, PipelineAbandonedError
from bristlenose.i18n import SUPPORTED_LOCALES as _I18N_LOCALES
from bristlenose.i18n import set_locale as _set_locale
from bristlenose.preflight import PreflightAbortedError
from bristlenose.preflight.whisper import WHISPER_SIZE_HUMAN
from bristlenose.run_lifecycle import ConcurrentRunError, run_lifecycle
from bristlenose.ui_kinds import MessageKind, cli_prefix
from bristlenose.utils.text import count_noun

# Known commands — used by _maybe_inject_run() to detect bare directory arguments
_COMMANDS = {
    "run", "transcribe", "analyze", "analyse", "render", "doctor", "help", "configure", "use",
    "serve", "status", "codebooks", "pipeline",
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


def _say(kind: MessageKind, message: str, *, indent: str = "") -> None:
    """Print a status line prefixed with the canonical glyph for ``kind``.

    Glyph and colour come from :mod:`bristlenose.ui_kinds`. Use for any
    line that communicates state ("X happened" / "Y failed"); decorative
    ``[dim]…[/dim]`` annotations stay as plain ``console.print``.
    """
    console.print(f"{indent}{cli_prefix(kind)} {message}")


def _validate_codebook_slug(slug: str) -> None:
    """Raise ``typer.Exit(2)`` with the available-slugs list when ``slug`` is unknown.

    Cheap probe via :func:`bristlenose.server.codebook.get_template`; on miss,
    prints the recognised slugs and a pointer to ``bristlenose codebooks``.
    """
    from bristlenose.server.codebook import get_template, list_available_slugs

    if get_template(slug) is not None:
        return
    available = list_available_slugs()
    _say(MessageKind.ERROR, f"Unknown codebook: {slug!r}")
    if available:
        console.print(f"  Available: {', '.join(available)}")
    console.print("  Run [bold]bristlenose codebooks[/bold] for full details.")
    raise typer.Exit(2)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"bristlenose {__version__}")
        raise typer.Exit()


def _lang_callback(value: str | None) -> None:
    if value:
        _set_locale(value)


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
    lang: Annotated[
        str | None,
        typer.Option(
            "--lang",
            envvar="BRISTLENOSE_LANG",
            help=f"UI language ({', '.join(_I18N_LOCALES)}).",
            callback=_lang_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """User-research transcription and quote extraction engine."""


# ---------------------------------------------------------------------------
# Doctor helpers (needed by pipeline commands)
# ---------------------------------------------------------------------------

_DOCTOR_SENTINEL_DIR = Path("~/.config/bristlenose").expanduser()
_DOCTOR_SENTINEL_FILE = _DOCTOR_SENTINEL_DIR / ".doctor-ran"


def _doctor_sentinel_dir() -> Path:
    """Return sentinel directory, respecting $SNAP_USER_COMMON."""

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

    Skipped for every packaged install — snap, Homebrew and the Fedora RPM all
    install their own man page, and a second copy in the user's home is worse
    than none. `man` searches ~/.local/share/man BEFORE /usr/share/man, so the
    unowned copy wins; and because no package owns it, `dnf remove` (or
    `snap remove`, or `brew uninstall`) leaves it behind, so `man bristlenose`
    goes on working after the tool is gone, showing whatever version last
    wrote it. Observed on a Copr install, 27 Aug 2026.
    """
    import shutil

    from bristlenose.doctor_fixes import detect_install_method

    # One source of truth rather than a second set of sniffs — and a future
    # packager that drops the .install-method marker is covered automatically.
    if detect_install_method() != "pip":
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
            icon = cli_prefix(MessageKind.SUCCESS)
        elif result.status == CheckStatus.WARN:
            icon = cli_prefix(MessageKind.WARNING)
        elif result.status == CheckStatus.FAIL:
            icon = cli_prefix(MessageKind.ERROR)
        else:
            icon = cli_prefix(MessageKind.SKIPPED)

        label = f"{result.label:<16}"
        detail = f"[dim]{result.detail}[/dim]" if result.detail else ""
        console.print(f" {icon} {label}{detail}")


def _print_doctor_fixes(
    report: object, *, skip_keys: set[str] | None = None
) -> None:
    """Print fix instructions for failures and warnings.

    The table already shows what passed/failed/skipped with details.
    ``skip_keys`` lets the caller suppress fix messages that were already
    handled interactively (e.g. MLX auto-install prompt).
    """
    from bristlenose.doctor import DoctorReport
    from bristlenose.doctor_fixes import get_fix

    assert isinstance(report, DoctorReport)

    failures = report.failures
    warnings = report.warnings

    all_fixable = failures + warnings
    if skip_keys:
        all_fixable = [r for r in all_fixable if r.fix_key not in skip_keys]
    if all_fixable:
        console.print()  # Blank line after table
        for result in all_fixable:
            fix = get_fix(result.fix_key)
            if fix:
                # markup=False so e.g. `'bristlenose[serve]'` isn't parsed as
                # a Rich style tag and silently stripped from the output.
                console.print(fix, markup=False)
                console.print()  # Blank line between fixes


def _maybe_offer_mlx_install(report: object) -> bool:
    """Offer to install MLX if the report contains the mlx_not_installed warning.

    Only prompts in interactive terminals (skips CI, piped output).
    Returns ``True`` if the warning was handled (accepted or declined
    interactively) so the caller can suppress the duplicate fix text.
    """
    from bristlenose.doctor import CheckStatus, DoctorReport

    assert isinstance(report, DoctorReport)

    mlx_warn = next(
        (
            r
            for r in report.results
            if r.fix_key == "mlx_not_installed" and r.status == CheckStatus.WARN
        ),
        None,
    )
    if mlx_warn is None:
        return False

    if not sys.stdout.isatty():
        return False

    console.print()
    console.print(
        "Apple Silicon detected but MLX not installed.\n"
        "[dim]MLX enables GPU-accelerated transcription (faster)."
        " CPU works fine without it.[/dim]"
    )
    console.print()

    try:
        answer = input("Install MLX for GPU-accelerated transcription? [Y/n] ")
    except (EOFError, KeyboardInterrupt):
        console.print()
        return True

    if answer.strip().lower() in ("n", "no"):
        from bristlenose.doctor_fixes import get_fix

        fix = get_fix("mlx_not_installed")
        if fix:
            console.print()
            console.print(fix)
        return True

    from bristlenose.doctor_fixes import get_mlx_install_command, install_mlx, verify_mlx_installed

    _cmd, display = get_mlx_install_command()
    console.print()
    console.print(f"[dim]Running: {display}[/dim]")
    console.print()

    if install_mlx() and verify_mlx_installed():
        console.print()
        _say(MessageKind.SUCCESS, "MLX installed. GPU transcription is now available.", indent="  ")
    else:
        console.print()
        _say(MessageKind.ERROR, "Installation failed. Try manually:", indent="  ")
        console.print(f"  {display}")

    return True


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
    mlx_handled = _maybe_offer_mlx_install(report)

    if report.has_failures:
        skip = {"mlx_not_installed"} if mlx_handled else None
        _print_doctor_fixes(report, skip_keys=skip)
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
    mlx_handled = _maybe_offer_mlx_install(report)

    if report.has_failures:
        skip = {"mlx_not_installed"} if mlx_handled else None
        _print_doctor_fixes(report, skip_keys=skip)
        console.print()
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Interactive first-run provider selection
# ---------------------------------------------------------------------------


# User-typed CLI spelling for each canonical provider id (the reverse of the
# alias map): what to show in "bristlenose use <x>" / "bristlenose configure <x>"
# suggestions.
_CANONICAL_TO_CLI = {
    "anthropic": "claude",
    "openai": "chatgpt",
    "google": "gemini",
    "azure": "azure",
    "local": "local",
}


def _is_tty() -> bool:
    """True when both stdin and stdout are terminals (safe to print guidance)."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def _print_provider_guidance() -> None:
    """Show how to set up an LLM provider — teach ``configure``, no numbered menu.

    First-run guidance: where to get a key for each cloud provider, and the one
    command that validates and persists it. The store name is resolved live
    (``get_credential_store_label``) so it's correct per platform — Keychain /
    Secret Service / config file — never hardcoded to "Keychain".
    """
    from bristlenose.credentials import get_credential_store_label

    store = get_credential_store_label()

    console.print()
    console.print("[bold]No LLM provider configured.[/bold]")
    console.print()
    console.print(
        "Set one up once — [bold cyan]bristlenose configure <provider>[/bold cyan] validates your",
        highlight=False,
    )
    console.print(
        f"key and stores it securely ({store}):",
        highlight=False,
    )
    console.print()
    for name, url in (
        ("Claude", "https://console.anthropic.com/settings/keys"),
        ("ChatGPT", "https://platform.openai.com/api-keys"),
        ("Gemini", "https://aistudio.google.com/apikey"),
        ("Azure", "https://portal.azure.com"),
    ):
        console.print(f"  {name.ljust(9)}[link={url}]{url}[/link]")
    console.print()
    console.print(
        "For local models via Ollama:  [bold cyan]bristlenose configure local[/bold cyan]",
        highlight=False,
    )
    console.print()


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
        _say(MessageKind.INFO, "Ollama is not running.")

        if is_ollama_installed():
            console.print()
            console.print("Starting Ollama...")
            if start_ollama_serve():
                _say(MessageKind.SUCCESS, "Ollama started.")
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
                        _say(MessageKind.SUCCESS, "Ollama installed.")
                        console.print("Starting Ollama...")
                        if start_ollama_serve():
                            _say(MessageKind.SUCCESS, "Ollama started.")
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
                        _say(MessageKind.ERROR, "Installation failed.")
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
        _say(MessageKind.WARNING, "Ollama is running but no suitable model found.")
        console.print()

        if Confirm.ask(f"Download {DEFAULT_MODEL} (2 GB)?", default=True):
            console.print()
            if pull_model(DEFAULT_MODEL):
                console.print()
                _say(MessageKind.SUCCESS, f"Downloaded {DEFAULT_MODEL}")
                return "local"
            else:
                console.print()
                _say(MessageKind.ERROR, "Download failed.")
                console.print("Try manually: [bold]ollama pull llama3.2[/bold]")
                return None
        return None

    # Ready to go
    console.print()
    _say(MessageKind.SUCCESS, f"Using local AI ({status.recommended_model})")
    console.print("[dim]This is slower than cloud APIs but completely free and private.[/dim]")
    console.print("[dim]For production quality: export BRISTLENOSE_ANTHROPIC_API_KEY=...[/dim]")
    console.print()

    return "local"


def _maybe_guide_provider_setup(settings: object) -> None:
    """Stop before the run when the provider can't be resolved. Never prompts.

    ``run``/``analyze`` are non-interactive by contract — the only interactive
    step anywhere is the key paste inside ``configure``. Reads the resolution
    recorded by ``load_settings()`` (see ``ProviderResolution``):

    - ``none``      — no choice, no keys: setup guidance (TTY, exit 0) or a
      terse actionable error (non-TTY, exit 2).
    - ``ambiguous`` — 2+ providers have keys and none is chosen: name them and
      the two ways to choose; exit 2. Never resolved by a vendor default.
    - ``explicit``  — the chosen provider must have its key; if missing, name
      the exact gap (not "no provider configured") and exit 2.
    - ``derived`` / ``hosted`` — nothing to do.
    """
    from bristlenose.config import (
        _CLOUD_KEY_FIELDS,
        BristlenoseSettings,
        get_provider_resolution,
    )
    from bristlenose.providers import PROVIDERS, get_provider_aliases

    assert isinstance(settings, BristlenoseSettings)

    res = get_provider_resolution()
    if res is None or res.status in ("hosted", "derived"):
        return

    if res.status == "none":
        if _is_tty():
            _print_provider_guidance()
            raise typer.Exit(0)
        _say(MessageKind.ERROR, "No AI provider configured.")
        console.print(
            "Run bristlenose configure <claude|chatgpt|gemini|azure|local>, "
            "or set BRISTLENOSE_LLM_PROVIDER and its key.",
        )
        raise typer.Exit(2)

    if res.status == "ambiguous":
        names = ", ".join(
            PROVIDERS[p].display_name for p in res.configured if p in PROVIDERS
        )
        cli_names = "|".join(
            _CANONICAL_TO_CLI.get(p, p) for p in res.configured
        )
        first = _CANONICAL_TO_CLI.get(res.configured[0], res.configured[0])
        _say(
            MessageKind.ERROR,
            f"{count_noun(len(res.configured), 'AI provider')} are configured "
            f"({names}) and none is selected.",
        )
        console.print(f"  Pick one to stay current:  [bold]bristlenose use {cli_names}[/bold]")
        console.print(f"  Or just for this run:      [bold]--llm {first}[/bold]")
        raise typer.Exit(2)

    # status == "explicit": the chosen provider must actually have a key.
    aliases = get_provider_aliases()
    canonical = aliases.get(res.provider, res.provider)
    if canonical == "local":
        return  # Ollama has no key; its own preflight covers readiness
    if canonical not in PROVIDERS:
        _say(MessageKind.ERROR, f"Unknown AI provider: {res.provider}")
        console.print("Valid choices: claude, chatgpt, gemini, azure, local")
        raise typer.Exit(2)
    key_field = _CLOUD_KEY_FIELDS.get(canonical)
    if key_field and not getattr(settings, key_field):
        display = PROVIDERS[canonical].display_name
        cli_name = _CANONICAL_TO_CLI.get(canonical, canonical)
        _say(
            MessageKind.ERROR,
            f"{display} is selected but no {display} key is configured.",
        )
        console.print(f"  Run:  [bold]bristlenose configure {cli_name}[/bold]")
        raise typer.Exit(2)


# ---------------------------------------------------------------------------
# Pipeline header and summary output
# ---------------------------------------------------------------------------


def _print_header(settings: object, *, show_provider: bool = True, show_hardware: bool = True) -> None:
    """Print the Bristlenose version + provider + hardware header line."""
    from bristlenose._build import build_label
    from bristlenose.providers import PROVIDERS
    from bristlenose.utils.hardware import detect_hardware

    parts: list[str] = [f"v{__version__}"]
    label = build_label()
    if label:
        parts.append(label)
    if show_provider:
        provider_name = PROVIDERS.get(
            settings.llm_provider, PROVIDERS["anthropic"]
        ).display_name
        parts.append(provider_name)
    if show_hardware:
        hw = detect_hardware()
        parts.append(hw.label)
    console.print(f"\nBristlenose [dim]{' · '.join(parts)}[/dim]\n")


def _named_participant_summary(people: object, n_participants: int) -> str:
    """Build a short summary of named participants for the stats line.

    Returns the short names joined by comma (e.g. "Martin, Sarah, Fred, Fritz")
    when all participants are named, or "3 of 5 named" when partial, or ""
    when no names exist.  Only considers participant codes (p1, p2, ...)
    — moderators and observers are excluded.
    """
    if people is None:
        return ""
    participants = getattr(people, "participants", None)
    if not participants:
        return ""

    named: list[str] = []
    total = 0
    for pid, entry in participants.items():
        if not pid.startswith("p"):
            continue
        total += 1
        ed = getattr(entry, "editable", None)
        if ed:
            short = getattr(ed, "short_name", "") or getattr(ed, "full_name", "")
            if short:
                named.append(short)

    if not named:
        return ""
    if len(named) == total and total <= 8:
        return ", ".join(named)
    return f"{len(named)} of {total} named"


def _print_pipeline_summary(
    result: object,
    *,
    serve_url: str | None = None,
    quiet_errors: bool = False,
) -> None:
    """Print a clean summary after any pipeline command.

    Adapts to the fields available on the result (LLM usage, timing, etc.).
    When *serve_url* is given, prints the serve URL instead of a file:// link.

    When *quiet_errors* is True, suppresses the "Finished with errors" speech
    act so the caller can render its own researcher-facing banner (used by
    the legacy 0-quotes path post-A3 which says "no usable content found"
    rather than blaming API credits).
    """
    from bristlenose.llm.pricing import PRICING_URLS, estimate_cost
    from bristlenose.pipeline import _format_duration

    # Stats line — build dynamically from what's available
    parts: list[str] = []
    participants = getattr(result, "participants", [])
    if participants:
        people = getattr(result, "people", None)
        named = _named_participant_summary(people, len(participants))
        if named:
            parts.append(f"{count_noun(len(participants), 'participant')} ({named})")
        else:
            parts.append(count_noun(len(participants), "participant"))
    screen_clusters = getattr(result, "screen_clusters", [])
    if screen_clusters:
        parts.append(count_noun(len(screen_clusters), "screen"))
    theme_groups = getattr(result, "theme_groups", [])
    if theme_groups:
        parts.append(count_noun(len(theme_groups), "theme"))
    total_quotes = getattr(result, "total_quotes", 0)
    if total_quotes:
        parts.append(count_noun(total_quotes, "quote"))
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

    # Done / error line
    elapsed = getattr(result, "elapsed_seconds", 0.0)
    llm_ran = getattr(result, "llm_calls", 0) > 0
    no_quotes = getattr(result, "total_quotes", 0) == 0
    has_errors = llm_ran and no_quotes

    if has_errors and not quiet_errors:
        time_str = f" in {_format_duration(elapsed)}" if elapsed else ""
        p_error = getattr(result, "pipeline_error", "")
        p_error_link = getattr(result, "pipeline_error_link", "")
        if p_error:
            console.print()
            _say(MessageKind.ERROR, f"Finished with errors{time_str} — {p_error}", indent="  ")
            if p_error_link:
                console.print(
                    f"  [dim]Billing → [link={p_error_link}]{p_error_link}[/link][/dim]"
                )
        else:
            console.print()
            _say(
                MessageKind.ERROR,
                f"Finished with errors{time_str} — 0 quotes extracted (check API credits or logs)",
                indent="  ",
            )
        console.print("  [dim]Run [bold]bristlenose doctor[/bold] to diagnose[/dim]")
    elif has_errors and quiet_errors:
        # Caller will print the researcher-facing banner. We still show the
        # elapsed-time line so the user has timing context.
        if elapsed:
            console.print()
            _say(MessageKind.WARNING, f"Finished in {_format_duration(elapsed)}", indent="  ")
    elif getattr(result, "pipeline_warning", ""):
        p_warning = getattr(result, "pipeline_warning", "")
        time_str = f" in {_format_duration(elapsed)}" if elapsed else ""
        console.print()
        _say(MessageKind.WARNING, f"Done with warnings{time_str} — {p_warning}", indent="  ")
    elif elapsed:
        console.print()
        _say(MessageKind.SUCCESS, f"Done in {_format_duration(elapsed)}", indent="  ")
    else:
        console.print()
        _say(MessageKind.SUCCESS, "Done.", indent="  ")

    # Report line — only print when serving. The static HTML still exists on
    # disk as a sealed byproduct of stage 12, but it's not the product and we
    # don't surface its path. Failure paths print no Report: line at all.
    if serve_url:
        console.print(f"\n  Report:  [bold cyan]{serve_url}[/bold cyan]")
        from urllib.parse import urlparse

        _print_mcp_connect(urlparse(serve_url).port or 8150)


def _print_pipeline_failure(cause: object, input_dir: Path, settings: object) -> None:
    """Print a researcher-facing failure banner from a structured Cause.

    Maps cause.category to actionable copy; falls back to cause.message for
    categories without a custom mapping. Never prints engineer text like
    'category=QUOTA' or stack traces. Naming the user's actual folder in
    retry hints (`bristlenose run interviews/`) matches their mental model.

    Intentional minimalism — only the banner, no stats line, no elapsed
    time, no LLM cost. When the pipeline abandons (QUOTA, AUTH, NETWORK,
    etc.), the researcher's question is "what do I do?", not "how many
    sessions made it through?". Partial-run details remain available in
    `pipeline-events.jsonl` for diagnostic follow-up; the CLI banner is
    deliberately scoped to recovery action. If a future cohort tester
    asks for partial-run context in mid-run DISK / MISSING_BINARY cases,
    surface it via a `--verbose` flag on `run`, not by default.
    """
    from bristlenose.events import CauseCategoryEnum
    from bristlenose.llm.billing_hints import billing_for
    from bristlenose.providers import PROVIDERS

    folder = input_dir.name or str(input_dir)
    retry_cmd = f"bristlenose run {folder}/"
    category = getattr(cause, "category", None)
    message = getattr(cause, "message", "") or ""
    provider_key = getattr(cause, "provider", None) or getattr(settings, "llm_provider", None)
    provider_display = (
        PROVIDERS[provider_key].display_name
        if provider_key and provider_key in PROVIDERS
        else "the API"
    )

    console.print()
    if category == CauseCategoryEnum.OUT_OF_CREDIT:
        _say(MessageKind.ERROR, f"Your {provider_display} account ran out of credit.")
        billing = billing_for(provider_key) if provider_key else None
        if billing:
            console.print(f"  Top up at {billing.billing_url}")
        console.print(f"  then run  [bold]{retry_cmd}[/bold]  again.")
    elif category == CauseCategoryEnum.QUOTA:
        # QUOTA is now the transient rate-limit / throttling bucket (billing
        # exhaustion routes to OUT_OF_CREDIT above). Waiting helps here.
        _say(MessageKind.ERROR, f"Rate-limited by {provider_display}.")
        console.print(f"  Wait a minute and run  [bold]{retry_cmd}[/bold]  again.")
    elif category == CauseCategoryEnum.API_REQUEST:
        _say(MessageKind.ERROR, f"{provider_display} rejected the request.")
        console.print("  This can happen with an unsupported model or malformed input.")
    elif category == CauseCategoryEnum.API_SERVER:
        _say(MessageKind.ERROR, f"{provider_display} had a server error.")
        console.print("  Try again in a few minutes.")
    elif category == CauseCategoryEnum.NETWORK:
        _say(MessageKind.ERROR, f"Couldn't reach {provider_display}.")
        console.print("  Check your network connection.")
    elif category == CauseCategoryEnum.AUTH:
        suffix = _active_api_key_suffix(settings, provider_key)
        suffix_part = f" (…{suffix})" if suffix else ""
        _say(MessageKind.ERROR, f"{provider_display} rejected your API key{suffix_part}.")
        console.print("  Run  [bold]bristlenose configure[/bold]  to set a new key.")
    elif category == CauseCategoryEnum.DISK:
        _say(MessageKind.ERROR, "Ran out of disk space.")
        if message:
            console.print(f"  {message}")
    elif category in (
        CauseCategoryEnum.MISSING_BINARY,
        CauseCategoryEnum.MISSING_DEP,
        CauseCategoryEnum.MISSING_INPUT,
    ):
        _say(MessageKind.ERROR, message or "Required component missing.")
    else:
        _say(MessageKind.ERROR, message or "Pipeline failed.")


def _active_api_key_suffix(settings: object, provider: str | None) -> str:
    """Return the last 3 chars of the active provider's API key, or empty.

    Reads the key from settings (already populated from keychain / env / .env
    by ``load_settings`` — including any ``BRISTLENOSE_*_API_KEY`` env-var
    overrides via pydantic-settings; the doctor table uses the same source).
    Returns empty string for providers without a key-bearing concept (local)
    or when the key isn't set.

    Suffix length matches ``bristlenose doctor``'s key masking
    (`doctor.py:351,385,435,470` — all `key[-3:]`). A3's banner names the
    provider in the surrounding sentence ("Claude rejected your API key
    (…wAA)") so we don't repeat the doctor table's provider-stem prefix.
    """
    if not provider:
        return ""
    field_map = {
        "anthropic": "anthropic_api_key",
        "openai": "openai_api_key",
        "azure": "azure_api_key",
        "google": "google_api_key",
    }
    field = field_map.get(provider)
    if not field:
        return ""
    key = getattr(settings, field, "") or ""
    if len(key) < 3:
        return ""
    return key[-3:]


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


def _has_no_deliverable(output_dir: Path) -> bool:
    """True when *output_dir* holds no analysis worth protecting — only state.

    A run that dies before producing anything still leaves a directory behind,
    and that detritus must not wall off the user's next attempt with "Output
    directory already exists". The advice attached to that refusal — *use
    --clean* — is unusable from the desktop app, which has no way to pass a
    flag, so a researcher who hits it is simply stuck.

    **The test is "is there a deliverable?", not "which files are these?"**
    This was previously an allowlist of one filename prefix (`bristlenose.log`
    and its rotations), which meant any run that got marginally further defeated
    it. A hung run on 19 Aug 2026 left a db, an events file, a shoal feed and a
    `last-run-failure.log` beside the log; every one of those is state or
    telemetry, none is an analysis, and the allowlist refused all of them —
    walling off the retry in exactly the way this function exists to prevent.

    Everything Bristlenose *produces* — the report, `sessions/`,
    `transcripts-raw/`, `assets/` — lands at the top level of the output
    directory. Everything under `.bristlenose/` is internal state. So a folder
    containing nothing but `.bristlenose/` has nothing to lose, whatever is
    inside it. The resume path (a valid manifest) is handled by the caller
    before this is reached.
    """
    from bristlenose.utils.fs import is_os_metadata

    for entry in output_dir.iterdir():
        if is_os_metadata(entry):
            continue
        if entry.name != ".bristlenose" or not entry.is_dir():
            return False
    return True


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
        str | None,
        typer.Option("--llm", "-l", help="LLM provider: claude, chatgpt, azure, gemini, local."),
    ] = None,
    codebook: Annotated[
        str | None,
        typer.Option(
            "--codebook",
            help="Codebook framework for AutoCode (run `bristlenose codebooks` to list).",
        ),
    ] = None,
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
    no_serve: Annotated[
        bool,
        typer.Option(
            "--no-serve",
            help=(
                "Don't auto-start the local web server when the pipeline finishes. "
                "Used by the macOS desktop sidecar (the desktop app manages its own "
                "serve lifecycle separately). Hidden — not part of the CLI happy path."
            ),
            hidden=True,
        ),
    ] = False,
    clean: Annotated[
        bool,
        typer.Option("--clean", help="Delete output directory before running."),
    ] = False,
    dev: Annotated[
        bool,
        typer.Option("--dev", help="Development mode: enable responsive playground in served report."),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logging."),
    ] = False,
    no_fetch: Annotated[
        bool,
        typer.Option(
            "--no-fetch",
            help="Abort instead of downloading missing models (Whisper, spaCy). "
            "Run `bristlenose doctor --fetch` first to pre-warm the cache.",
        ),
    ] = False,
) -> None:
    """Analyse a folder of interviews and open the report in your browser."""
    # Default output location: inside the input folder
    if output_dir is None:
        output_dir = input_dir / "bristlenose-output"

    # A hard crash runs no handler, so the previous run's report may still be
    # sitting in a stashed backup with nothing pointing at it. Recover it BEFORE
    # anything inspects the output directory — `output_exists` and the resume
    # branch below both read the disk, and both would read the wrong thing if a
    # restore happened after them. See utils/output_backup.py.
    from bristlenose.utils import output_backup

    _reclaim = output_backup.reclaim_stale(output_dir)
    if _reclaim is output_backup.RestoreOutcome.FAILED:
        # The only surviving copy of a previous report is stranded, and the
        # stash below would sweep it. Refuse rather than destroy it.
        _say(
            MessageKind.ERROR,
            f"A previous report is stranded at "
            f"{output_backup.backup_path_for(output_dir)} and could not be "
            f"recovered. Move it somewhere safe, then re-run.",
        )
        raise typer.Exit(1)

    # Fail early if output exists and --clean not given — but allow resume
    # when a pipeline manifest exists (Phase 1c/1d crash recovery).
    output_exists = output_dir.exists() and any(output_dir.iterdir())
    if output_exists and not clean:
        from bristlenose.manifest import load_manifest

        if load_manifest(output_dir) is not None:
            # Print a one-line resume summary from the manifest (Phase 1e)
            from bristlenose.status import format_resume_summary, get_project_status

            _status = get_project_status(output_dir)
            if _status is not None:
                console.print(f"[dim]{format_resume_summary(_status)}[/dim]")
            else:
                console.print("[dim]Resuming from previous run...[/dim]")
        elif _has_no_deliverable(output_dir):
            # Nothing but internal state survives from a run that produced no
            # analysis. Reuse the directory silently — demanding --clean here
            # walls off the user's second attempt, and the desktop app has no
            # way to pass --clean at all.
            output_exists = False
        else:
            console.print(
                f"[red]Output directory already exists: {output_dir}[/red]\n"
                f"Use [bold]--clean[/bold] to delete it and re-run."
            )
            raise typer.Exit(1)

    if redact_pii and retain_pii:
        _say(MessageKind.ERROR, "Cannot use both --redact-pii and --retain-pii.")
        raise typer.Exit(1)

    if codebook is not None:
        _validate_codebook_slug(codebook)

    if project_name is None:
        project_name = input_dir.resolve().name

    settings_kwargs: dict[str, object] = {
        "input_dir": input_dir,
        "output_dir": output_dir,
        "project_name": project_name,
        "skip_transcription": skip_transcription,
        "pii_enabled": redact_pii,
        "no_fetch": no_fetch,
    }
    # Only pass these as overrides when explicitly set on the CLI — otherwise let
    # injected env vars (BRISTLENOSE_LLM_PROVIDER/MODEL, BRISTLENOSE_WHISPER_*)
    # or config-file defaults take effect. A non-None llm_provider default here
    # would override the desktop-injected BRISTLENOSE_LLM_PROVIDER: the desktop
    # injects openai, the old `--llm` default "claude" beat it (cli-override),
    # and the model env var (gpt-4o) rode along → anthropic endpoint + gpt-4o
    # → 404. See docs/private/ikea-run-debug-log.md.
    if llm_provider is not None:
        settings_kwargs["llm_provider"] = llm_provider
    if whisper_backend is not None:
        settings_kwargs["whisper_backend"] = whisper_backend
    if whisper_model is not None:
        settings_kwargs["whisper_model"] = whisper_model
    if codebook is not None:
        settings_kwargs["codebook"] = codebook
    # Record the forward-or-not decision in the resolution ledger BEFORE resolving,
    # attributed to this CLI layer. load_settings only sees the result (llm_provider
    # present in overrides or not); this names the actor that chose. See the 8 Jun
    # 404: a non-None --llm default silently beat the desktop-injected env var.
    from bristlenose.config import (
        describe_cli_provider_decision,
        hosted_by_desktop,
        note_resolution_input,
    )

    note_resolution_input(
        describe_cli_provider_decision(
            llm_provider, hosted=hosted_by_desktop(), command="run"
        )
    )
    settings = load_settings(**settings_kwargs)

    # First-run: no provider configured → print setup guidance and exit.
    # Runs BEFORE setup_logging so the gated exit creates nothing on disk —
    # setup_logging mkdirs <output>/.bristlenose, and that leftover made the
    # post-configure second run fail with "Output directory already exists".
    _maybe_guide_provider_setup(settings)

    # Configure logging BEFORE preflight so the provider/model resolution ledger
    # and the api-key preflight call (where a provider/model-mismatch 404 fires)
    # land in <output>/.bristlenose/bristlenose.log. Without this, both run
    # before pipeline._configure_logging attaches the file handler and are lost.
    from bristlenose.config import log_resolution_trace
    from bristlenose.logging import setup_logging

    setup_logging(output_dir=output_dir, verbose=verbose)
    log_resolution_trace()

    # Header is the first visible output
    _print_header(settings)

    if not _maybe_auto_doctor(settings, "run"):
        _run_preflight(settings, "run", skip_transcription=skip_transcription)

    # API-key validation against billing. Runs after _maybe_guide_provider_setup
    # so a freshly-pasted key gets validated immediately. Aborts cleanly with
    # provider-specific recovery copy on invalid-key / billing-empty / etc.
    from bristlenose.preflight.api_key import (
        ApiKeyPreflightAbortedError,
        preflight_api_key,
    )

    try:
        preflight_api_key(settings=settings, console=console)
    except ApiKeyPreflightAbortedError as exc:
        _say(MessageKind.ERROR, str(exc))
        raise typer.Exit(2) from exc

    # Clean after checks so user sees setup context first.
    #
    # "Clean" MOVES the previous report aside; it does not destroy it. The old
    # `shutil.rmtree` here ran before the pipeline had demonstrated it could do
    # anything, so a crash seconds later left the project with neither its old
    # report nor a new one — which is exactly what happened twice on 30 Aug 2026
    # (docs/sidecar-transcription-crash.md). The backup is discarded once the run
    # succeeds, and restored if it doesn't. See utils/output_backup.py.
    output_stash: Path | None = None
    if output_exists and clean:
        output_stash = output_backup.stash(
            output_dir, previous_backup_is_spent=_reclaim.report_is_back
        )
        if output_stash is not None:
            console.print(f"\n[dim]Cleaned {output_dir}[/dim]")
        else:
            # `stash` returns None when the move failed (cross-device,
            # permissions) and deliberately does NOT fall back to deleting. The
            # run then writes over the previous output, so saying "Cleaned"
            # would be the opposite of what happened.
            console.print(
                f"\n[dim]Could not set {output_dir} aside — "
                f"this run will write over it[/dim]"
            )

    from bristlenose.pipeline import Pipeline

    estimator, on_event = _build_estimator(settings)
    pipeline = Pipeline(
        settings, verbose=verbose, on_event=on_event,
        estimator=estimator,
    )
    # The stash is settled in `finally`, not in the handlers: the failure paths
    # below each raise `typer.Exit`, and every one of them — plus KeyboardInterrupt,
    # which is the single most likely way a run ends early — has to reach the same
    # decision. One place to get right rather than four.
    run_produced_a_report = False
    try:
        with run_lifecycle(output_dir, KindEnum.RUN) as _run_handle:
            pipeline.set_progress_sink(_run_handle.progress)
            result = asyncio.run(pipeline.run(input_dir, output_dir))
            _run_handle.set_cost(compute_run_cost(
                result.llm_model,
                result.llm_input_tokens,
                result.llm_output_tokens,
            ))
            _run_handle.set_summary(result.summary)
        # ASSERT THE THING, NOT A PROXY. "No exception" is not "a report
        # exists": fifteen lines below is the documented path where the
        # pipeline runs cleanly and produces zero quotes (silent audio, an
        # unsupported codec, a transcription backend that produced nothing).
        # Keyed on the absence of an exception, that path discarded the
        # previous report and then told the researcher nothing was found —
        # the original incident, living inside its own fix.
        run_produced_a_report = getattr(result, "total_quotes", 0) > 0
    except ConcurrentRunError as exc:
        # NOT a restore case, and the only one: another process owns this output
        # directory and is writing to it right now. Putting our stash back would
        # trample a live run. Drop the reference so `finally` leaves it alone —
        # `reclaim_stale` on the next run is the recovery path instead.
        output_stash = None
        _say(MessageKind.ERROR, str(exc))
        raise typer.Exit(1) from exc
    except PreflightAbortedError as exc:
        _say(MessageKind.ERROR, str(exc))
        raise typer.Exit(2) from exc
    except PipelineAbandonedError as exc:
        _print_pipeline_failure(exc.cause, input_dir, settings)
        raise typer.Exit(1) from exc
    finally:
        if run_produced_a_report:
            # Only now is the old report spent.
            output_backup.discard(output_stash)
        else:
            outcome = output_backup.restore(output_stash, output_dir)
            if outcome is not output_backup.RestoreOutcome.NOTHING_TO_DO:
                # The root file handler still points at the tree `restore` just
                # renamed away, so every line logged from here — including the
                # one a post-mortem would look for — would land in the wrong
                # file. Re-attach before saying anything.
                setup_logging(output_dir=output_dir, verbose=verbose)
            if outcome is output_backup.RestoreOutcome.RESTORED:
                _say(
                    MessageKind.INFO,
                    "Your previous report is still here — this run changed nothing.",
                    indent="  ",
                )
            elif outcome is output_backup.RestoreOutcome.RESTORED_WITHOUT_HISTORY:
                # The events tail is the OLD run_completed, so the project will
                # read as having succeeded. Say so rather than let the UI lie.
                _say(
                    MessageKind.WARNING,
                    "Your previous report is back, but this run's history could "
                    "not be preserved — the project may still show as completed.",
                    indent="  ",
                )
            elif outcome is output_backup.RestoreOutcome.FAILED:
                _say(
                    MessageKind.ERROR,
                    f"Could not put your previous report back. It is safe at "
                    f"{output_backup.backup_path_for(output_dir)} — the next "
                    f"run will recover it.",
                    indent="  ",
                )
        output_stash = None

    # Legacy path: pipeline ran cleanly but produced zero usable quotes
    # (silent audio, no spoken content). Not an abandon — just empty input.
    llm_ran = getattr(result, "llm_calls", 0) > 0
    pipeline_errored = llm_ran and getattr(result, "total_quotes", 0) == 0

    if pipeline_errored:
        _print_pipeline_summary(result, quiet_errors=True)
        console.print()
        _say(MessageKind.WARNING, "No usable content found in this folder.", indent="  ")
        console.print(
            "  Bristlenose looks for spoken interviews. If this folder contains them,"
        )
        console.print(
            "  the audio may be too quiet or in an unsupported format. Try:"
        )
        console.print("    [bold]bristlenose doctor[/bold]")
        console.print("  to check your install.")
        raise typer.Exit(1)

    # uvicorn is guaranteed importable here — preflight gates `serve_deps`.

    # `--no-serve` is the desktop sidecar's escape hatch: pipeline runs, summary
    # prints, then exit cleanly without binding a server port. The desktop app
    # manages its own serve lifecycle through ServeManager. Hidden from --help.
    if no_serve:
        _print_pipeline_summary(result)
        return

    try:
        port = _find_open_port()
    except RuntimeError:
        _print_pipeline_summary(result)
        _say(MessageKind.WARNING, "No available port (8150–8159)", indent="  ")
        return

    serve_url = f"http://127.0.0.1:{port}/report/"
    if port != 8150:
        console.print(f"  [dim]Port 8150 in use, trying {port}… ok[/dim]")
    _print_pipeline_summary(result, serve_url=serve_url)
    if dev:
        console.print("  [dim]Dev mode: responsive playground enabled[/dim]")
    console.print("  [dim]Press Ctrl-C to stop the server[/dim]")

    try:
        _start_server(input_dir, port=port, open_browser=False, dev=dev, verbose=verbose)
    except Exception as exc:
        console.print()
        _say(MessageKind.WARNING, f"Could not start server: {exc}", indent="  ")
        # Show file link as fallback
        report_path = getattr(result, "report_path", None)
        if report_path and report_path.exists():
            file_url = f"file://{report_path.resolve()}"
            try:
                display_path = report_path.resolve().relative_to(Path.cwd())
            except ValueError:
                display_path = report_path.name
            console.print(f"  Report:  [link={file_url}]{display_path}[/link]")


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
    no_fetch: Annotated[
        bool,
        typer.Option(
            "--no-fetch",
            help="Abort instead of downloading missing models. "
            "Run `bristlenose doctor --fetch` first to pre-warm the cache.",
        ),
    ] = False,
) -> None:
    """Only run transcription (no LLM analysis). Produces raw transcripts."""
    # Default output location: inside the input folder
    if output_dir is None:
        output_dir = input_dir / "bristlenose-output"

    settings_kwargs: dict[str, object] = {
        "output_dir": output_dir,
        "skip_transcription": False,
        "no_fetch": no_fetch,
    }
    if whisper_model is not None:
        settings_kwargs["whisper_model"] = whisper_model
    settings = load_settings(**settings_kwargs)

    _print_header(settings, show_provider=False)

    if not _maybe_auto_doctor(settings, "transcribe-only"):
        _run_preflight(settings, "transcribe-only")

    from bristlenose.pipeline import Pipeline

    pipeline = Pipeline(settings, verbose=verbose)
    try:
        with run_lifecycle(output_dir, KindEnum.TRANSCRIBE_ONLY) as _run_handle:
            result = asyncio.run(pipeline.run_transcription_only(input_dir, output_dir))
            _run_handle.set_summary(result.summary)
    except ConcurrentRunError as exc:
        _say(MessageKind.ERROR, str(exc))
        raise typer.Exit(1) from exc
    except PreflightAbortedError as exc:
        _say(MessageKind.ERROR, str(exc))
        raise typer.Exit(2) from exc

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
        str | None,
        typer.Option("--llm", "-l", help="LLM provider: claude, chatgpt, azure, gemini, local."),
    ] = None,
    codebook: Annotated[
        str | None,
        typer.Option(
            "--codebook",
            help="Codebook framework for AutoCode (run `bristlenose codebooks` to list).",
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logging."),
    ] = False,
    no_fetch: Annotated[
        bool,
        typer.Option(
            "--no-fetch",
            help="Abort instead of downloading missing models. "
            "Run `bristlenose doctor --fetch` first to pre-warm the cache.",
        ),
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

    if codebook is not None:
        _validate_codebook_slug(codebook)

    if project_name is None:
        project_name = transcripts_dir.resolve().name

    settings_kwargs: dict[str, object] = {
        "output_dir": output_dir,
        "project_name": project_name,
        "no_fetch": no_fetch,
    }
    # Only override provider when explicitly set — otherwise honour the injected
    # BRISTLENOSE_LLM_PROVIDER env var / config default (see run() for rationale).
    if llm_provider is not None:
        settings_kwargs["llm_provider"] = llm_provider
    if codebook is not None:
        settings_kwargs["codebook"] = codebook
    # See run() — record the --llm forward-or-not decision in the ledger, attributed
    # to this CLI layer, before load_settings resolves the winner.
    from bristlenose.config import (
        describe_cli_provider_decision,
        hosted_by_desktop,
        note_resolution_input,
    )

    note_resolution_input(
        describe_cli_provider_decision(
            llm_provider, hosted=hosted_by_desktop(), command="analyze"
        )
    )
    settings = load_settings(**settings_kwargs)

    # First-run: no provider configured → print setup guidance and exit
    _maybe_guide_provider_setup(settings)

    _print_header(settings)

    if not _maybe_auto_doctor(settings, "analyze"):
        _run_preflight(settings, "analyze")

    from bristlenose.pipeline import Pipeline

    estimator, on_event = _build_estimator(settings)
    pipeline = Pipeline(
        settings, verbose=verbose, on_event=on_event,
        estimator=estimator,
    )
    try:
        with run_lifecycle(output_dir, KindEnum.ANALYZE) as _run_handle:
            pipeline.set_progress_sink(_run_handle.progress)
            result = asyncio.run(pipeline.run_analysis_only(transcripts_dir, output_dir))
            _run_handle.set_cost(compute_run_cost(
                result.llm_model,
                result.llm_input_tokens,
                result.llm_output_tokens,
            ))
            _run_handle.set_summary(result.summary)
    except ConcurrentRunError as exc:
        _say(MessageKind.ERROR, str(exc))
        raise typer.Exit(1) from exc
    except PreflightAbortedError as exc:
        _say(MessageKind.ERROR, str(exc))
        raise typer.Exit(2) from exc

    _print_pipeline_summary(result)


# British English alias for analyze
analyse = app.command(name="analyse", hidden=True)(analyze)


@app.command(
    name="render",
    hidden=True,
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def render(ctx: typer.Context) -> None:
    """Removed — use `bristlenose run` or `bristlenose serve`."""
    _say(MessageKind.ERROR, "bristlenose render was removed.")
    console.print()
    console.print("  To analyse interviews:        [bold]bristlenose run[/bold] <folder>")
    console.print("  To open a previous report:    [bold]bristlenose serve[/bold] <folder>")
    raise typer.Exit(2)


def _find_open_port(start: int = 8150, attempts: int = 10) -> int:
    """Find an available port starting from *start*.

    Tries *attempts* consecutive ports.  Raises RuntimeError if all are taken.
    """
    import socket

    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    msg = f"No available port in {start}–{start + attempts - 1}"
    raise RuntimeError(msg)


def _start_server(
    project_dir: Path,
    *,
    port: int,
    open_browser: bool = True,
    dev: bool = False,
    verbose: bool = False,
) -> None:
    """Start the FastAPI server (blocking).  Used by both serve() and run().

    Two paths:

    - ``port != 0``: classic ``uvicorn.run(app, port=port)``. Caller knows the
      port up-front (CLI's djb2-derived choice, or an explicit ``--port``).
    - ``port == 0``: kernel-assigned port via ``bind(0)`` — needed when the
      desktop host spawns the sidecar and reads the chosen port from
      stdout. Uses the programmatic ``uvicorn.Config`` + ``Server`` API so
      we can read the bound port from the socket and emit the ``Report:``
      line *after* the bind succeeds (the host parses that URL for both
      readiness and the actual port).

    Independent of port path:

    - ``install_exit_logger`` is always called — one structured INFO line
      on every exit makes "why did it die?" a single-grep question.
    - ``install_parent_death_watcher`` runs only when
      ``_BRISTLENOSE_HOSTED_BY_DESKTOP=1`` is set by the caller. CLI users
      may ``nohup`` and outlive their starting shell; desktop users
      shouldn't have an orphan sidecar after a host crash.
    """
    import uvicorn

    from bristlenose.server.app import create_app
    from bristlenose.server.lifecycle import (
        install_exit_logger,
        install_parent_death_watcher,
    )

    install_exit_logger()
    if os.environ.get("_BRISTLENOSE_HOSTED_BY_DESKTOP") == "1":
        install_parent_death_watcher()

    if port == 0:
        _serve_dynamic_port(project_dir, dev=dev, verbose=verbose)
        return

    report_url = f"http://127.0.0.1:{port}/report/"
    if open_browser:
        _schedule_browser_open(report_url)

    app_instance = create_app(project_dir=project_dir, dev=dev, verbose=verbose)
    uvicorn.run(
        app_instance,
        host="127.0.0.1",
        port=port,
        log_level="info" if verbose else "warning",
    )


def _schedule_browser_open(report_url: str, *, delay_sec: float = 1.0) -> None:
    """Open the report URL in the default browser after a short delay."""
    import threading
    import time
    import webbrowser

    def _open() -> None:
        time.sleep(delay_sec)
        webbrowser.open(report_url)

    threading.Thread(target=_open, daemon=True).start()


def _print_mcp_connect(port: int) -> None:
    """Vendor-neutral MCP connect block (design-mcp-server.md §9a).

    Prints the two primitives (URL + assembled Authorization header) and the
    permanent docs URL — never a vendor's command: dialects rot, so they
    live in the manual (and the Mac sheet) where they can update. Gated on
    ``import mcp`` succeeding — the same probe ``mount_mcp_server`` uses, so
    a present-but-broken install prints the unavailable line rather than a
    working-looking block over a dead endpoint.
    """
    if os.environ.get("_BRISTLENOSE_HOSTED_BY_DESKTOP") == "1":
        # The desktop-hosted sidecar's stdout is a machine channel
        # (ServeManager parses it; "Copy error details" pastes it) and Mac
        # exposure is a later cycle — keep the block out of that buffer.
        return
    try:
        import mcp  # noqa: F401
    except ImportError:
        console.print("  [dim]MCP:    unavailable — pip install 'bristlenose\\[mcp]'[/dim]")
        return
    # Pre-mint the auth token if no serve has minted one yet (the run path
    # prints this block BEFORE create_app runs). create_app recovers this
    # env var, so the printed header is always the served one.
    import secrets as _secrets

    os.environ.setdefault("_BRISTLENOSE_AUTH_TOKEN", _secrets.token_urlsafe(32))
    docs_url = "https://bristlenose.app/docs/connect-an-agent.html"
    console.print(f"  MCP:    [bold cyan]http://127.0.0.1:{port}/mcp/[/bold cyan]")
    console.print()
    console.print(
        "  [dim]Connect an agent — give it the MCP URL and this header. Works with any\n"
        "  MCP-compatible agent (Claude, ChatGPT, Codex). Sends the quotes in your\n"
        "  report, speaker codes in place of names; quote text is verbatim. How-to:[/dim]"
    )
    console.print(f"  [link={docs_url}]{docs_url}[/link]")
    token = os.environ.get("_BRISTLENOSE_AUTH_TOKEN", "")
    if token:
        # markup=False: this line must be byte-exact. A minted token is
        # bracket-free, but an inherited env token might not be, and Rich
        # would silently eat [\w]+ sequences as style tags.
        console.print(f"\n    Authorization: Bearer {token}", markup=False)
    console.print()


def _serve_dynamic_port(
    project_dir: Path,
    *,
    dev: bool,
    verbose: bool,
) -> None:
    """Bind to a kernel-assigned port and print it after the socket is ready.

    Used when the caller passed ``--port 0`` (the desktop host does this
    so it can never collide with a slow-dying orphan sidecar — every
    launch gets a fresh port). Prints the ``Report:`` line *after* bind
    so the URL the host reads is the one actually accepting connections.
    """
    import asyncio

    import uvicorn

    from bristlenose.server.app import create_app

    app_instance = create_app(project_dir=project_dir, dev=dev, verbose=verbose)
    config = uvicorn.Config(
        app_instance,
        host="127.0.0.1",
        port=0,
        log_level="info" if verbose else "warning",
    )
    server = uvicorn.Server(config)

    async def _run() -> None:
        # Run uvicorn in the background so we can read the assigned port
        # as soon as the socket is bound. ``server.started`` flips True
        # after the lifespan startup completes, by which point
        # ``server.servers[0].sockets`` is populated.
        serve_task = asyncio.create_task(server.serve())
        # Bounded wait — kernel bind on loopback is instant; if we don't
        # see a started server in 10s, something else is wrong (e.g.
        # lifespan failed). Surface by letting serve_task raise.
        for _ in range(200):  # 200 * 50ms = 10s
            if server.started and server.servers and server.servers[0].sockets:
                break
            await asyncio.sleep(0.05)
        if server.started and server.servers and server.servers[0].sockets:
            actual_port = server.servers[0].sockets[0].getsockname()[1]
            console.print(
                f"\n  Report: [bold cyan]http://127.0.0.1:{actual_port}/report/[/bold cyan]\n"
            )
            _print_mcp_connect(actual_port)
        await serve_task

    asyncio.run(_run())


def _auto_render(project_dir: Path) -> None:
    """Re-render the HTML report from intermediate data before serving.

    Fast (<0.1s) and ensures the served HTML always matches the current
    render/ package code — no stale mount-point markers or missing CSS.
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
    from bristlenose.stages.s12_render_output import read_pipeline_metadata

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
    console.print(
        f" {cli_prefix(MessageKind.SUCCESS)} [dim]Rendered report[/dim]"
        f"  {count_noun(result.total_quotes, 'quote')}"
    )




def _available_palettes() -> list[str]:
    """Colour-palette identifiers, discovered from the theme's palette-*.css files.

    Mirrors the CSS palette files (and the frontend ``PALETTES`` list) so a new
    ``palette-<name>.css`` is a valid ``--palette`` value with no edit here.
    """
    colors_dir = Path(__file__).resolve().parent / "theme" / "colors"
    return sorted(p.stem.removeprefix("palette-") for p in colors_dir.glob("palette-*.css"))


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
    palette: Annotated[
        str | None,
        typer.Option(
            "--palette",
            envvar="BRISTLENOSE_PALETTE",
            help="Colour palette for the report (e.g. default, edo).",
        ),
    ] = None,
    open_browser: Annotated[
        bool,
        typer.Option("--open/--no-open", help="Open the report in the default browser."),
    ] = True,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logging."),
    ] = False,
) -> None:
    """Open a previous report in your browser (no analysis)."""
    # --palette / BRISTLENOSE_PALETTE → env for app.py._html_root_attrs, which
    # renders data-color-theme onto <html>. The internal attribute keeps its
    # name; only the user-facing --palette / BRISTLENOSE_PALETTE spelling is new.
    if palette is not None:
        _allowed = _available_palettes()
        if palette not in _allowed:
            from rich.markup import escape

            console.print(
                f"[red]Unknown palette '{escape(palette)}'.[/red] "
                f"Available: {', '.join(_allowed)}"
            )
            raise typer.Exit(2)
        os.environ["BRISTLENOSE_PALETTE"] = palette
    settings = load_settings()
    _run_preflight(settings, "serve")
    import uvicorn  # noqa: F401 — needed in the dev-mode branch below

    # Re-render the HTML report before serving so it always matches the
    # current code (templates, CSS, JS).  This is fast (<0.1s) and avoids
    # stale-HTML surprises (e.g. missing mount-point markers).
    if project_dir is not None:
        _auto_render(project_dir)

    # ``--port 0`` defers the Report: line to ``_serve_dynamic_port`` because
    # the actual port isn't known until uvicorn binds the socket. Used by the
    # macOS desktop host to avoid orphan-port collisions.
    if port == 0 and dev:
        console.print(
            "[red]--port 0 is not supported with --dev[/red] — "
            "uvicorn reload spawns workers that need a fixed port."
        )
        raise typer.Exit(1)
    if port != 0:
        report_url = f"http://127.0.0.1:{port}/report/"
        console.print(f"\n  Report: [bold cyan]{report_url}[/bold cyan]")
        _print_mcp_connect(port)
        if dev:
            console.print("  [dim]Dev mode: responsive playground enabled[/dim]")
        console.print()

    if dev:
        import atexit
        import signal
        import socket
        import subprocess
        import threading
        import webbrowser

        # Open browser for dev mode (non-dev uses _start_server which handles this)
        def _open_browser_fn() -> None:
            import time

            time.sleep(1.0)
            webbrowser.open(report_url)

        if open_browser:
            threading.Thread(target=_open_browser_fn, daemon=True).start()

        # Start Vite dev server as a subprocess (unless already running).
        vite_proc: subprocess.Popen[bytes] | None = None
        frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
        if frontend_dir.is_dir():
            vite_port = 5173
            # Check if Vite is already running on the port.
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                port_in_use = sock.connect_ex(("127.0.0.1", vite_port)) == 0
            if port_in_use:
                console.print(f"  [dim]Vite already running on :{vite_port}[/dim]")
            else:
                console.print(f"  [dim]Starting Vite dev server on :{vite_port}[/dim]")
                vite_proc = subprocess.Popen(
                    ["npx", "vite", "--port", str(vite_port)],
                    cwd=str(frontend_dir),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

                def _cleanup_vite() -> None:
                    if vite_proc and vite_proc.poll() is None:
                        vite_proc.send_signal(signal.SIGINT)
                        try:
                            vite_proc.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            vite_proc.kill()

                atexit.register(_cleanup_vite)

        # In dev mode uvicorn uses a string factory and calls create_app()
        # itself (needed for reload). Stash project_dir in the environment
        # so the factory can recover it.
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
        _start_server(
            project_dir or Path("."),
            port=port,
            open_browser=open_browser,
            verbose=verbose,
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
    _report_stashed_output(output_dir)


def _report_stashed_output(output_dir: Path) -> None:
    """Name any stashed or kept-failed tree sitting beside the output.

    Both are dot-prefixed so Bristlenose cannot re-ingest a stashed report as
    interview material — which also means Finder never shows them. They hold a
    full copy of the output directory, `pii_summary.txt` included, so a
    researcher deleting a project needs to be told they are there. `SECURITY.md`
    says `status` reports them; this is that.
    """
    from bristlenose.utils import output_backup

    for path, note in (
        (output_backup.backup_path_for(output_dir), "your previous report, kept while a run is in flight"),
        (output_backup.failed_path_for(output_dir), "a failed run's work, kept so a retry can resume"),
    ):
        if path.exists():
            _say(MessageKind.INFO, f"{path.name} — {note}")
            console.print(f"    Delete with: [bold]rm -rf {path}[/bold]")


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
            icon = cli_prefix(MessageKind.SUCCESS)
        elif info.status in (StageStatus.PARTIAL, StageStatus.RUNNING):
            icon = cli_prefix(MessageKind.WARNING)
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
                            cli_prefix(MessageKind.SUCCESS)
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


def _set_current_provider(canonical: str) -> None:
    """Record ``canonical`` as the current analysis provider (user-level config).

    The CLI mirror of the macOS app's behaviour: the provider stays whatever
    you last set, until you set another. Written to the user-level config .env
    (lowest priority — a project ``.env``, ``BRISTLENOSE_LLM_PROVIDER``, or
    ``--llm`` still overrides per run). Loud by design: switching happens in
    the same breath as the user's own configure/use action, never silently.
    """
    from bristlenose.config import hosted_by_desktop
    from bristlenose.credentials import read_user_config_var, write_user_config_var
    from bristlenose.providers import PROVIDERS

    if hosted_by_desktop():  # GUI owns provider choice on the desktop
        return

    previous = read_user_config_var("BRISTLENOSE_LLM_PROVIDER")
    write_user_config_var("BRISTLENOSE_LLM_PROVIDER", canonical)

    display = PROVIDERS[canonical].display_name if canonical in PROVIDERS else canonical
    if previous and previous != canonical and previous in PROVIDERS:
        was = PROVIDERS[previous].display_name
        console.print(f"{display} is now your provider for analysis (was {was}).")
        console.print(
            f"Switch back any time:  [bold]bristlenose use "
            f"{_CANONICAL_TO_CLI.get(previous, previous)}[/bold]"
        )
    else:
        console.print(f"{display} is now your provider for analysis.")

    env_override = os.environ.get("BRISTLENOSE_LLM_PROVIDER")
    if env_override and env_override != canonical:
        _say(
            MessageKind.WARNING,
            f"BRISTLENOSE_LLM_PROVIDER={env_override} is set in your environment "
            "and overrides this choice — unset it to make this stick.",
        )


@app.command()
def use(
    provider: Annotated[
        str,
        typer.Argument(
            help="Provider to use for analysis: claude, chatgpt, gemini, azure, or local."
        ),
    ],
) -> None:
    """Choose which AI provider runs the analysis.

    Persists the choice in your user-level config — the CLI equivalent of the
    macOS app keeping the provider you last set. Keys stay stored; switch any
    time. --llm and BRISTLENOSE_LLM_PROVIDER still override per run.
    """
    from bristlenose.config import _CLOUD_KEY_FIELDS
    from bristlenose.providers import PROVIDERS, get_provider_aliases

    aliases = get_provider_aliases()
    name = provider.lower()
    canonical = aliases.get(name, name)
    if canonical not in PROVIDERS:
        _say(MessageKind.ERROR, f"Unknown provider: {provider}")
        console.print("Available: claude, chatgpt, gemini, azure, local")
        raise typer.Exit(1)

    if canonical == "local":
        _set_current_provider("local")
        console.print(
            "If Ollama isn't set up yet:  [bold]bristlenose configure local[/bold]"
        )
        return

    settings = load_settings()
    display = PROVIDERS[canonical].display_name
    if not getattr(settings, _CLOUD_KEY_FIELDS[canonical]):
        _say(MessageKind.ERROR, f"No {display} key is configured.")
        console.print(
            f"  Run:  [bold]bristlenose configure "
            f"{_CANONICAL_TO_CLI.get(canonical, canonical)}[/bold]"
        )
        raise typer.Exit(1)

    _set_current_provider(canonical)


@app.command()
def configure(
    provider: Annotated[
        str,
        typer.Argument(
            help="Provider to configure: claude, chatgpt, gemini, azure, local, or miro."
        ),
    ],
    key: Annotated[
        str | None,
        typer.Option("--key", "-k", help="API key (if not provided, prompts interactively)."),
    ] = None,
) -> None:
    """Set up API credentials for an LLM provider.

    Validates the key with a test API call, then stores it securely in your
    system credential store (macOS Keychain or Linux Secret Service). When no
    keyring is available (e.g. a headless server), it persists the key to a
    protected config file instead — so the command always leaves you configured.
    """
    from bristlenose.credentials import (
        EnvCredentialStore,
        FileCredentialStore,
        get_credential_store,
    )
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
        "local": "local",
        "ollama": "local",
        "miro": "miro",
    }
    canonical = provider_map.get(provider)
    if canonical is None:
        _say(MessageKind.ERROR, f"Unknown provider: {provider}")
        console.print("Available: claude, chatgpt, gemini, azure, local, miro")
        raise typer.Exit(1)

    # Local (Ollama) has no key to store — set up the runtime instead, so the
    # `configure <provider>` verb is uniform across every provider.
    if canonical == "local":
        if _setup_local_provider() is None:
            raise typer.Exit(1)
        _set_current_provider("local")
        console.print("Run it with:  [bold]bristlenose run <folder>[/bold]")
        return

    display_names = {
        "anthropic": "Claude",
        "openai": "ChatGPT",
        "azure": "Azure OpenAI",
        "google": "Gemini",
        "miro": "Miro",
    }
    display_name = display_names.get(canonical, canonical.title())

    # Get key from option or prompt
    if key is None:
        console.print()
        prompt_label = (
            f"Enter your {display_name} access token"
            if canonical == "miro"
            else f"Enter your {display_name} API key"
        )
        key = typer.prompt(prompt_label, hide_input=True)

    if not key.strip():
        _say(MessageKind.ERROR, "No key entered")
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
    elif canonical == "miro":
        from bristlenose.miro_client import validate_miro_token

        is_valid, error = validate_miro_token(key)
    else:
        # Azure needs endpoint+deployment to validate fully; skip for now
        is_valid, error = None, "needs endpoint and deployment to validate"

    if is_valid is False:
        _say(MessageKind.ERROR, f"Invalid — {error}")
        raise typer.Exit(1)
    elif is_valid is None:
        _say(MessageKind.WARNING, f"Could not validate: {error}")
        console.print("Storing anyway...")
    else:
        _say(MessageKind.SUCCESS, "Valid")

    # Store it — keyring if available, else the persisting config file.
    store = get_credential_store()
    try:
        store.set(canonical, key)
    except NotImplementedError:
        # No writable store at all (a bare read-only EnvCredentialStore). This
        # should not happen now the fallback persists to a file, but keep a
        # last-resort manual path rather than losing the validated key silently.
        console.print()
        _say(MessageKind.WARNING, "No writable credential store available.")
        console.print("Add this to your .env file or shell profile:")
        console.print()
        env_vars = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "azure": "AZURE_API_KEY",
            "google": "GOOGLE_API_KEY",
            "miro": "MIRO_ACCESS_TOKEN",
        }
        env_var = env_vars.get(canonical, f"{canonical.upper()}_API_KEY")
        console.print(f"  export BRISTLENOSE_{env_var}={key}", markup=False)
        console.print()
        console.print("[dim](The key is not stored anywhere — save it yourself)[/dim]")
        raise typer.Exit(0)

    service_name = (
        f"Bristlenose {display_name} Access Token"
        if canonical == "miro"
        else f"Bristlenose {display_name} API Key"
    )
    if isinstance(store, FileCredentialStore):
        # Persisted to the config .env — name the file so it's not a black box.
        from rich.markup import escape

        try:
            loc = "~/" + str(store.path.relative_to(Path.home()))
        except ValueError:
            loc = str(store.path)
        _say(MessageKind.SUCCESS, f"Saved to {escape(loc)}")
    elif not isinstance(store, EnvCredentialStore):
        from bristlenose.credentials import get_credential_store_label

        store_label = get_credential_store_label()
        _say(MessageKind.SUCCESS, f'Stored in {store_label} as "{service_name}"')

    # Azure needs additional config beyond the API key
    if canonical == "azure":
        console.print()
        console.print("[dim]Azure OpenAI also needs endpoint and deployment name.[/dim]")
        console.print("[dim]Add to .env or environment:[/dim]")
        console.print()
        console.print("  BRISTLENOSE_AZURE_ENDPOINT=https://your-resource.openai.azure.com/")
        console.print("  BRISTLENOSE_AZURE_DEPLOYMENT=your-deployment-name")

    console.print()
    if canonical == "miro":
        # The panel shipped; this line said it had not, for long enough to be
        # logged twice as a known discrepancy and fixed neither time. It told a
        # researcher who had just saved a token that the thing they saved it
        # for did not exist — the one moment they are certain to read it.
        #
        # Scoped to the browser deliberately: `AppLayout` renders the NavBar
        # (and so Send to Miro) only when NOT embedded, so the Mac app has no
        # route to this panel and naming one would repeat the defect inverted.
        console.print(
            "Miro access token saved. Open a report with "
            "[bold]bristlenose serve[/bold] and choose [bold]Send to Miro[/bold] "
            "in the report toolbar."
        )
    else:
        _set_current_provider(canonical)
        console.print("You can now run: [bold]bristlenose run interviews[/bold]")


@app.command()
def doctor(
    self_test: Annotated[
        bool,
        typer.Option(
            "--self-test",
            help="Run bundle-integrity checks only (for build-all.sh pre-archive).",
        ),
    ] = False,
    fetch: Annotated[
        bool,
        typer.Option(
            "--fetch",
            help=(
                f"Pre-download the Whisper transcription model "
                f"({WHISPER_SIZE_HUMAN}) so transcription works offline or "
                "with --no-fetch."
            ),
        ),
    ] = False,
) -> None:
    """Check dependencies, API keys, and system configuration.

    With --self-test, runs only the bundle-integrity checks — asserts every
    runtime-data file the code will look for (React SPA, codebook YAMLs,
    LLM prompts, locales, theme, Alembic) is present and non-trivial.
    Exits non-zero on any failure. Used by desktop/scripts/build-all.sh
    step 7a to catch BUG-3/4/5-class packaging bugs at build time.
    """
    if fetch:
        from bristlenose.preflight.whisper import preflight_whisper
        settings = load_settings()
        preflight_whisper(
            settings=settings, console=console, status=None, allow_fetch=True,
        )
        return

    if self_test:
        from bristlenose.doctor import run_bundle_integrity
        report = run_bundle_integrity()
        _format_doctor_table(report)
        if report.has_failures:
            console.print("\n[bold red]Bundle integrity: FAIL[/bold red]")
            console.print(
                "One or more runtime-data dirs are missing or truncated. "
                "This build is NOT shippable. "
                "Check `desktop/bristlenose-sidecar.spec` `datas`, then "
                "rebuild via `desktop/scripts/build-sidecar.sh`."
            )
            import sys
            sys.exit(1)
        console.print("\n[dim green]Bundle integrity: OK[/dim green]\n")
        return

    from bristlenose.doctor import run_all

    settings = load_settings()

    console.print(f"\nbristlenose {__version__}\n")

    report = run_all(settings)
    _format_doctor_table(report)
    mlx_handled = _maybe_offer_mlx_install(report)

    if not report.has_failures and not report.has_warnings:
        console.print("\n[dim green]All clear.[/dim green]")
    else:
        skip = {"mlx_not_installed"} if mlx_handled else None
        _print_doctor_fixes(report, skip_keys=skip)

    # Always update sentinel on explicit doctor
    _write_doctor_sentinel()
    console.print()


@app.command()
def codebooks() -> None:
    """List available codebook frameworks for AutoCode."""
    from rich.markup import escape

    from bristlenose.server.codebook import list_available_templates

    enabled = list_available_templates()

    console.print()
    for t in enabled:
        author_part = f" — {escape(t.author)}" if t.author else ""
        console.print(f"  [bold]{escape(t.id)}[/bold]  {escape(t.title)}{author_part}")
        if t.description:
            console.print(f"    [dim]{escape(t.description)}[/dim]")
    console.print()
    console.print(
        f"  [dim]{count_noun(len(enabled), 'codebook')} available. "
        f"Use [bold]--codebook=<id>[/bold] with [bold]run[/bold] or [bold]analyze[/bold].[/dim]"
    )
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
        _say(MessageKind.ERROR, f"Unknown topic: {topic}")
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
    console.print("[bold]bristlenose configure[/bold] <provider>")
    console.print("  Store an API key securely and make that provider current.")
    console.print("  claude | chatgpt | gemini | azure | local | miro")
    console.print()
    console.print("[bold]bristlenose use[/bold] <provider>")
    console.print("  Switch the current analysis provider. Keys stay stored.")
    console.print("  claude | chatgpt | gemini | azure | local")
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
    console.print("  BRISTLENOSE_LLM_MODEL            Model name (default: the provider's recommended model)")
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
    console.print("  Audio: .wav .mp3 .m4a .flac .ogg .wma .aac .aiff .aif .caf")
    console.print("  Video: .mp4 .m4v .mov .avi .mkv .webm .wmv .asf .mts .m2ts")
    console.print("         .3gp .flv .mpg .mpeg")
    console.print("  Subtitles: .srt .vtt")
    console.print("  Transcripts: .docx (Teams exports), .txt (plain text)")
    console.print("  Files sharing a name stem are treated as one session.")
    console.print()


# `bristlenose pipeline` — read-only mixture-of-models view.
# The command body lives in bristlenose.pipeline.cli so the catalogue + render
# stay isolated from the 2k-line main CLI module.
from bristlenose.pipeline_view.cli import pipeline_command as _pipeline_command  # noqa: E402

app.command(name="pipeline")(_pipeline_command)
