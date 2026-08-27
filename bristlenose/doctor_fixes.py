"""Install-method-aware fix messages for doctor checks.

Each fix_key maps to a function that returns a string with the fix instruction,
tailored to the detected install method (snap, rpm, brew, pip).
"""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

#: Written into the private prefix by a packaging recipe that wants to be
#: recognised without a sniff. The RPM (rpm/bristlenose.spec.in) drops it; any
#: future packager can do the same rather than adding another heuristic here.
INSTALL_MARKER = ".install-method"

#: Values a marker file is allowed to carry. An unrecognised one is ignored
#: rather than trusted — a typo in a spec must not invent an install method
#: that no fix message handles.
_MARKER_METHODS = frozenset({"rpm"})


def detect_install_method() -> str:
    """Detect how bristlenose was installed.

    Returns one of: "snap", "rpm", "brew", "pip".
    """
    # Snap: $SNAP env var is set
    if os.environ.get("SNAP"):
        return "snap"

    # A packaged install can just say so. Checked before the sniffs because it
    # is the exact answer rather than an inference: the RPM lives at
    # /usr/lib64/bristlenose, which no path heuristic distinguishes from any
    # other venv, and guessing "pip" there tells a Fedora user to run pip —
    # which on Fedora installs a SECOND bristlenose into ~/.local/bin that
    # then shadows the packaged one on PATH.
    try:
        marker = Path(sys.prefix) / INSTALL_MARKER
        if marker.is_file():
            value = marker.read_text(encoding="utf-8").strip()
            if value in _MARKER_METHODS:
                return value
    except OSError:
        pass

    # Homebrew: Python executable under Homebrew prefixes
    exe = sys.executable
    if "/opt/homebrew/" in exe or "/usr/local/Cellar/" in exe:
        return "brew"

    # Default to pip (covers pipx, uv, plain pip, editable installs)
    return "pip"


def _get_cloud_fallback_hint() -> str:
    """Return a cloud provider hint based on available API keys.

    Checks which cloud API keys are configured and suggests the appropriate
    fallback. Only suggests providers the user can actually use.
    """
    from bristlenose.config import load_settings

    try:
        settings = load_settings()
        has_anthropic = bool(settings.anthropic_api_key)
        has_openai = bool(settings.openai_api_key)
        has_azure = bool(settings.azure_api_key and settings.azure_endpoint)
        has_google = bool(settings.google_api_key)

        options = []
        if has_anthropic:
            options.append("--llm claude")
        if has_openai:
            options.append("--llm chatgpt")
        if has_azure:
            options.append("--llm azure")
        if has_google:
            options.append("--llm gemini")
        if len(options) == 1:
            return f"Or use a cloud API: {options[0]}"
        if options:
            last = options[-1]
            rest = ", ".join(options[:-1])
            return f"Or use a cloud API: {rest} (or {last})"
        # No keys configured — point at provider setup without naming a favourite
        return "Or set up a cloud provider: bristlenose configure <claude|chatgpt|gemini|azure>"
    except Exception:
        # If settings fail to load, fall back to generic suggestion
        return "Or use a cloud API: bristlenose configure <provider>"


def get_fix(fix_key: str, install_method: str | None = None) -> str:
    """Get the fix instruction for a given fix_key and install method."""
    if install_method is None:
        install_method = detect_install_method()

    fn = _FIX_TABLE.get(fix_key)
    if fn is None:
        return ""
    return fn(install_method)


# ---------------------------------------------------------------------------
# Fix functions
# ---------------------------------------------------------------------------


def _fix_ffmpeg_missing(method: str) -> str:
    if method == "rpm":
        return (
            "FFmpeg not found — this is a bug in the RPM package, which\n"
            "requires /usr/bin/ffmpeg.\n"
            "  sudo dnf reinstall bristlenose\n"
            "If it persists: github.com/cassiocassio/bristlenose/issues"
        )
    if method == "snap":
        return (
            "FFmpeg not found — this is a bug in the snap package.\n"
            "  sudo snap refresh bristlenose\n"
            "If it persists: github.com/cassiocassio/bristlenose/issues"
        )
    if method == "brew":
        return (
            "bristlenose needs FFmpeg to extract audio from video files.\n\n"
            "  brew install ffmpeg"
        )
    # pip — show distro-specific instructions
    lines = ["bristlenose needs FFmpeg to extract audio from video files.\n"]
    if platform.system() == "Linux":
        lines.append("  Ubuntu/Debian:  sudo apt install ffmpeg")
        lines.append("  Fedora:         sudo dnf install ffmpeg")
        lines.append("  Arch:           sudo pacman -S ffmpeg")
    elif platform.system() == "Darwin":
        lines.append("  brew install ffmpeg")
    else:
        lines.append("  Install FFmpeg from https://ffmpeg.org/download.html")
    return "\n".join(lines)


def _fix_backend_import_fail(method: str) -> str:
    if method == "rpm":
        return (
            "Transcription backend failed to load — this is a bug in the RPM package.\n"
            "  sudo dnf reinstall bristlenose\n"
            "If it persists: github.com/cassiocassio/bristlenose/issues"
        )
    if method == "snap":
        return (
            "Transcription backend failed to load — this is a bug in the snap package.\n"
            "  sudo snap refresh bristlenose\n"
            "If it persists: github.com/cassiocassio/bristlenose/issues"
        )
    if method == "brew":
        return (
            "Transcription backend failed to load.\n\n"
            "  $(brew --prefix bristlenose)/libexec/bin/python -m pip install "
            "--upgrade ctranslate2 faster-whisper\n\n"
            "If that doesn't help: github.com/cassiocassio/bristlenose/issues"
        )
    return (
        "Transcription backend failed to load.\n\n"
        "  pipx inject bristlenose ctranslate2 faster-whisper\n\n"
        "If you used a venv, activate it first then: pip install ctranslate2 faster-whisper\n\n"
        "If that doesn't help: github.com/cassiocassio/bristlenose/issues"
    )


def _credential_store_hint() -> str:
    """Describe where ``configure`` will actually store the key.

    Availability-aware, not just platform-aware: on a Linux box with no Secret
    Service the key lands in the config-file fallback, so we must not promise
    "Secret Service" there. Keyed off the same label the store itself reports.
    """
    label = _credential_store_label()
    if label == "Keychain":
        return "This stores your key securely in your macOS Keychain."
    if label == "Secret Service":
        return "This stores your key securely via Secret Service (GNOME Keyring / KDE Wallet)."
    return "This stores your key in a protected config file (~/.config/bristlenose/.env)."


def _credential_store_label() -> str:
    """Short label for the credential store — the real one, availability-aware."""
    from bristlenose.credentials import get_credential_store_label

    return get_credential_store_label()


def _fix_api_key_missing_anthropic(_method: str) -> str:
    return (
        "bristlenose needs an API key to analyse transcripts.\n"
        "Get a Claude API key from console.anthropic.com, then:\n\n"
        "  bristlenose configure claude\n\n"
        f"{_credential_store_hint()}\n\n"
        "To use ChatGPT instead:  bristlenose run <input> --llm chatgpt\n"
        "To only transcribe:      bristlenose transcribe <input>"
    )


def _fix_api_key_missing_openai(_method: str) -> str:
    return (
        "bristlenose needs an API key to analyse transcripts.\n"
        "Get a ChatGPT API key from platform.openai.com, then:\n\n"
        "  bristlenose configure chatgpt\n\n"
        f"{_credential_store_hint()}\n\n"
        "To use Claude instead:  bristlenose run <input> --llm claude\n"
        "To only transcribe:     bristlenose transcribe <input>"
    )


def _fix_api_key_invalid_anthropic(_method: str) -> str:
    return (
        "Your Claude API key was rejected. Get a new key from\n"
        "console.anthropic.com/settings/keys, then:\n\n"
        "  bristlenose configure claude"
    )


def _fix_api_key_invalid_openai(_method: str) -> str:
    return (
        "Your ChatGPT API key was rejected. Get a new key from\n"
        "platform.openai.com/api-keys, then:\n\n"
        "  bristlenose configure chatgpt"
    )


def _fix_api_key_missing_google(_method: str) -> str:
    return (
        "bristlenose needs an API key to analyse transcripts.\n"
        "Get a Gemini API key from aistudio.google.com/apikey, then:\n\n"
        "  bristlenose configure gemini\n\n"
        f"{_credential_store_hint()}\n\n"
        "To use Claude instead:  bristlenose run <input> --llm claude\n"
        "To only transcribe:     bristlenose transcribe <input>"
    )


def _fix_api_key_invalid_google(_method: str) -> str:
    return (
        "Your Gemini API key was rejected. Get a new key from\n"
        "aistudio.google.com/apikey, then:\n\n"
        "  bristlenose configure gemini"
    )


def _fix_api_key_missing_azure(_method: str) -> str:
    return (
        "bristlenose needs Azure OpenAI credentials to analyse transcripts.\n"
        "From your Azure portal, set these environment variables:\n\n"
        "  export BRISTLENOSE_AZURE_ENDPOINT=https://your-resource.openai.azure.com/\n"
        "  export BRISTLENOSE_AZURE_API_KEY=your-key-here\n"
        "  export BRISTLENOSE_AZURE_DEPLOYMENT=your-deployment-name\n\n"
        f"Or add them to a .env file. To store the key in your {_credential_store_label()}:\n\n"
        "  bristlenose configure azure\n\n"
        "To use Claude instead:  bristlenose run <input> --llm claude\n"
        "To only transcribe:     bristlenose transcribe <input>"
    )


def _fix_api_key_invalid_azure(_method: str) -> str:
    return (
        "Your Azure OpenAI credentials were rejected. Check:\n\n"
        "  1. API key is correct (Azure portal > your OpenAI resource > Keys)\n"
        "  2. Endpoint URL matches your resource (https://NAME.openai.azure.com/)\n"
        "  3. Deployment name exists in your resource\n\n"
        "Then re-run: bristlenose configure azure"
    )


def _fix_network_unreachable(_method: str) -> str:
    return (
        "Check your internet connection. If you're behind a proxy:\n"
        "  export HTTPS_PROXY=http://proxy:port"
    )


def _fix_spacy_model_missing(method: str) -> str:
    if method == "rpm":
        return (
            "spaCy model not found — this is a bug in the RPM package, which\n"
            "bundles en_core_web_sm.\n"
            "  sudo dnf reinstall bristlenose\n"
            "If it persists: github.com/cassiocassio/bristlenose/issues"
        )
    if method == "snap":
        return (
            "spaCy model not found — this is a bug in the snap package.\n"
            "  sudo snap refresh bristlenose\n"
            "If it persists: github.com/cassiocassio/bristlenose/issues"
        )
    if method == "brew":
        return (
            "PII redaction needs a spaCy language model.\n\n"
            "  $(brew --prefix bristlenose)/libexec/bin/python "
            "-m spacy download en_core_web_sm\n\n"
            "Or ignore this if you don't need PII redaction."
        )
    return (
        "PII redaction needs a spaCy language model.\n\n"
        "  python3 -m spacy download en_core_web_sm\n\n"
        "Or ignore this if you don't need PII redaction."
    )


def _fix_presidio_missing(method: str) -> str:
    if method == "rpm":
        return (
            "presidio-analyzer not found — this is a bug in the RPM package,\n"
            "which bundles it.\n"
            "  sudo dnf reinstall bristlenose\n"
            "If it persists: github.com/cassiocassio/bristlenose/issues"
        )
    if method == "brew":
        return (
            "PII redaction requires presidio-analyzer.\n\n"
            "  $(brew --prefix bristlenose)/libexec/bin/python -m pip install "
            "presidio-analyzer presidio-anonymizer\n\n"
            "Then re-run. Or drop --redact-pii if you don't need it."
        )
    return (
        "PII redaction requires presidio-analyzer.\n\n"
        "  pipx inject bristlenose presidio-analyzer presidio-anonymizer\n\n"
        "If you used a venv, activate it first then: pip install presidio-analyzer presidio-anonymizer\n\n"
        "Then re-run. Or drop --redact-pii if you don't need it."
    )


def get_mlx_install_command() -> tuple[list[str], str]:
    """Get the pip command to install MLX.

    Uses ``sys.executable`` so the command targets the same Python that is
    running bristlenose (correct for brew, pipx, and plain-venv installs).

    Returns ``(command_list, display_string)``.
    """
    cmd = [sys.executable, "-m", "pip", "install", "mlx", "mlx-whisper"]
    display = f"{sys.executable} -m pip install mlx mlx-whisper"
    return cmd, display


def install_mlx() -> bool:
    """Install MLX and mlx-whisper via pip.

    Runs a subprocess with stdout/stderr forwarded so the user sees progress.
    Returns ``True`` on success.
    """
    import subprocess

    cmd, _display = get_mlx_install_command()
    try:
        result = subprocess.run(cmd)
        return result.returncode == 0
    except Exception:
        return False


def verify_mlx_installed() -> bool:
    """Verify that mlx-whisper is importable after installation.

    Uses a subprocess because packages installed by pip during the current
    process are not guaranteed to be importable in-process.
    """
    import subprocess

    try:
        result = subprocess.run(
            [sys.executable, "-c", "import mlx_whisper"],
            capture_output=True,
            timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False


def _fix_mlx_not_installed(method: str) -> str:
    if method == "brew":
        return (
            "Apple Silicon detected but MLX not installed. Transcription will\n"
            "use CPU (works fine, GPU is faster).\n\n"
            "  $(brew --prefix bristlenose)/libexec/bin/python -m pip install mlx mlx-whisper"
        )
    return (
        "Apple Silicon detected but MLX not installed. Transcription will\n"
        "use CPU (works fine, GPU is faster).\n\n"
        "  pipx inject bristlenose mlx mlx-whisper\n\n"
        "If you used a venv instead of pipx, activate it first then:\n"
        "  pip install mlx mlx-whisper"
    )


def _fix_cuda_not_available(_method: str) -> str:
    return (
        "NVIDIA GPU found but CUDA libraries aren't accessible.\n"
        "Transcription will work on CPU but will be slower.\n\n"
        "To enable GPU acceleration:\n"
        "  1. Install CUDA 12.x: nvidia.com/cuda-downloads\n"
        "  2. Set: export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH"
    )


def _fix_low_disk_space(_method: str) -> str:
    return (
        "bristlenose needs approximately 2 GB for the Whisper model download\n"
        "and working files. Free up space or use a smaller model:\n\n"
        "  bristlenose run <input> -w tiny      (75 MB model)\n"
        "  bristlenose run <input> -w small     (500 MB model)"
    )


def _fix_ollama_not_running(_method: str) -> str:
    from bristlenose.ollama import get_start_command

    hint = _get_cloud_fallback_hint()
    _cmd, display_cmd = get_start_command()
    return (
        "Start Ollama:\n\n"
        f"  {display_cmd}\n\n"
        f"Then re-run bristlenose. {hint}\n\n"
        "For interactive setup: bristlenose doctor"
    )


def _fix_ollama_not_installed(_method: str) -> str:
    hint = _get_cloud_fallback_hint()
    # Can't know the start command before install, so give generic advice
    return (
        "Install Ollama from https://ollama.ai (free, no account needed).\n\n"
        "After installing, bristlenose will start it automatically.\n\n"
        f"{hint}\n\n"
        "For interactive setup: bristlenose doctor"
    )


def _fix_ollama_model_missing(_method: str) -> str:
    hint = _get_cloud_fallback_hint()
    return (
        "Download the model:\n\n"
        "  ollama pull llama3.2\n\n"
        f"{hint}\n\n"
        "For interactive setup: bristlenose doctor"
    )


def _fix_serve_deps_missing(method: str) -> str:
    # Single quotes around the package spec so zsh doesn't interpret the
    # brackets as a glob character class — without them, pip gets a mangled
    # argument and the user sees "no matches found".
    if method == "rpm":
        # NOT the pip fallback below. On Fedora that either refuses with
        # EXTERNALLY-MANAGED or installs a second bristlenose into
        # ~/.local/bin, which shadows /usr/bin/bristlenose on PATH — leaving
        # the user running a different copy than the one they packaged.
        return (
            "`bristlenose serve` deps missing — this is a bug in the RPM package,\n"
            "which installs the serve extras.\n"
            "  sudo dnf reinstall bristlenose\n"
            "If it persists: github.com/cassiocassio/bristlenose/issues"
        )
    if method == "snap":
        return (
            "`bristlenose serve` deps missing — this is a bug in the snap package.\n"
            "  sudo snap refresh bristlenose\n"
            "If it persists: github.com/cassiocassio/bristlenose/issues"
        )
    if method == "brew":
        # Fully-qualified, not the `bristlenose` short name: since Homebrew 6.0
        # a short name that resolves to an untrusted tap is refused outright
        # ("Refusing to load formula ... from untrusted tap"), which would fail
        # for precisely the users who need this message. The qualified form is
        # allowed by the ARGV rule whether or not the tap is trusted.
        return (
            "`bristlenose serve` needs extras that weren't installed.\n\n"
            "  brew upgrade cassiocassio/bristlenose/bristlenose"
        )
    # pip / pipx / uv. Pipx venvs have "pipx" in sys.prefix; suggest the
    # right command for re-installing in place.
    if "pipx" in sys.prefix:
        return (
            "`bristlenose serve` needs extras that weren't installed.\n\n"
            "  pipx install --force 'bristlenose[serve]'"
        )
    return (
        "`bristlenose serve` needs extras that weren't installed.\n\n"
        "  pip install 'bristlenose[serve]'"
    )


def _fix_brew_tap_untrusted(method: str) -> str:
    # The check that raises this only fires on a Homebrew keg install, so the
    # `method` argument is unused — the fix is the same command regardless of
    # what detect_install_method() would have guessed.
    del method
    return (
        "Homebrew 6.0 skips untrusted third-party taps during `brew upgrade`,\n"
        "so Bristlenose installs fine but stops receiving updates.\n\n"
        "  brew trust --formula cassiocassio/bristlenose/bristlenose\n\n"
        "One-off. Then `brew upgrade` picks up new versions as normal."
    )


def _fix_auth_token_env_set(_method: str) -> str:
    return (
        "_BRISTLENOSE_AUTH_TOKEN is set in your shell. `bristlenose serve` "
        "will use this value as the auth token instead of generating a fresh "
        "random one, which is usually not what you want outside CI.\n\n"
        "Unset it:\n\n"
        "  unset _BRISTLENOSE_AUTH_TOKEN\n\n"
        "If this is a CI or test shell, you can ignore this warning. Also "
        "check your shell config (.zshrc, .bashrc, direnv, etc.) in case "
        "it's being exported automatically."
    )


# ---------------------------------------------------------------------------
# Lookup table
# ---------------------------------------------------------------------------

_FIX_TABLE: dict[str, object] = {
    "ffmpeg_missing": _fix_ffmpeg_missing,
    "backend_import_fail": _fix_backend_import_fail,
    "api_key_missing_anthropic": _fix_api_key_missing_anthropic,
    "api_key_missing_openai": _fix_api_key_missing_openai,
    "api_key_invalid_anthropic": _fix_api_key_invalid_anthropic,
    "api_key_invalid_openai": _fix_api_key_invalid_openai,
    "api_key_missing_google": _fix_api_key_missing_google,
    "api_key_invalid_google": _fix_api_key_invalid_google,
    "api_key_missing_azure": _fix_api_key_missing_azure,
    "api_key_invalid_azure": _fix_api_key_invalid_azure,
    "network_unreachable": _fix_network_unreachable,
    "spacy_model_missing": _fix_spacy_model_missing,
    "presidio_missing": _fix_presidio_missing,
    "mlx_not_installed": _fix_mlx_not_installed,
    "cuda_not_available": _fix_cuda_not_available,
    "low_disk_space": _fix_low_disk_space,
    "ollama_not_running": _fix_ollama_not_running,
    "ollama_not_installed": _fix_ollama_not_installed,
    "ollama_model_missing": _fix_ollama_model_missing,
    "auth_token_env_set": _fix_auth_token_env_set,
    "serve_deps_missing": _fix_serve_deps_missing,
    "brew_tap_untrusted": _fix_brew_tap_untrusted,
}
