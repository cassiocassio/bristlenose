"""Install-method-aware fix messages for doctor checks.

Each fix_key maps to a function that returns a string with the fix instruction,
tailored to the detected install method (snap, brew, pip).
"""

from __future__ import annotations

import os
import platform
import sys


def detect_install_method() -> str:
    """Detect how bristlenose was installed.

    Returns one of: "snap", "brew", "pip", "unknown".
    """
    # Snap: $SNAP env var is set
    if os.environ.get("SNAP"):
        return "snap"

    # Homebrew: Python executable under Homebrew prefixes
    exe = sys.executable
    if "/opt/homebrew/" in exe or "/usr/local/Cellar/" in exe:
        return "brew"

    # Default to pip (covers pipx, uv, plain pip, editable installs)
    return "pip"


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
    if method == "snap":
        return (
            "Transcription backend failed to load — this is a bug in the snap package.\n"
            "  sudo snap refresh bristlenose\n"
            "If it persists: github.com/cassiocassio/bristlenose/issues"
        )
    return (
        "Transcription backend failed to load.\n\n"
        "  pip install --upgrade ctranslate2 faster-whisper\n\n"
        "If that doesn't help: github.com/cassiocassio/bristlenose/issues"
    )


def _fix_api_key_missing_anthropic(_method: str) -> str:
    return (
        "bristlenose needs an API key to analyse transcripts.\n"
        "Get a Claude API key from console.anthropic.com, then:\n\n"
        "  export BRISTLENOSE_ANTHROPIC_API_KEY=sk-ant-...\n\n"
        "Or add it to a .env file in your project directory.\n\n"
        "To use ChatGPT instead:  bristlenose run <input> --llm openai\n"
        "To only transcribe:      bristlenose transcribe-only <input>"
    )


def _fix_api_key_missing_openai(_method: str) -> str:
    return (
        "bristlenose needs an API key to analyse transcripts.\n"
        "Get a ChatGPT API key from platform.openai.com, then:\n\n"
        "  export BRISTLENOSE_OPENAI_API_KEY=sk-...\n\n"
        "Or add it to a .env file in your project directory.\n\n"
        "To use Claude instead:  bristlenose run <input> --llm anthropic\n"
        "To only transcribe:     bristlenose transcribe-only <input>"
    )


def _fix_api_key_invalid_anthropic(_method: str) -> str:
    return "Your Claude API key was rejected. Check it at console.anthropic.com/settings/keys."


def _fix_api_key_invalid_openai(_method: str) -> str:
    return "Your ChatGPT API key was rejected. Check it at platform.openai.com/api-keys."


def _fix_network_unreachable(_method: str) -> str:
    return (
        "Check your internet connection. If you're behind a proxy:\n"
        "  export HTTPS_PROXY=http://proxy:port"
    )


def _fix_spacy_model_missing(method: str) -> str:
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
            "Then re-run. Or drop --redact-pii if you don't need it."
        )
    return (
        "PII redaction needs a spaCy language model.\n\n"
        "  python3 -m spacy download en_core_web_sm\n\n"
        "Then re-run. Or drop --redact-pii if you don't need it."
    )


def _fix_presidio_missing(_method: str) -> str:
    return (
        "PII redaction requires presidio-analyzer.\n\n"
        "  pip install presidio-analyzer presidio-anonymizer\n\n"
        "Then re-run. Or drop --redact-pii if you don't need it."
    )


def _fix_mlx_not_installed(method: str) -> str:
    if method == "brew":
        return (
            "Apple Silicon detected but MLX not installed. Transcription will\n"
            "use CPU (works fine, GPU is faster).\n\n"
            "  $(brew --prefix bristlenose)/libexec/bin/pip "
            "install 'bristlenose[apple]'"
        )
    return (
        "Apple Silicon detected but MLX not installed. Transcription will\n"
        "use CPU (works fine, GPU is faster).\n\n"
        "  pip install 'bristlenose[apple]'"
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
    return (
        "Start Ollama:\n\n"
        "  ollama serve\n\n"
        "Then re-run bristlenose. Or use a cloud API: --llm claude"
    )


def _fix_ollama_not_installed(_method: str) -> str:
    return (
        "Install Ollama from https://ollama.ai (free, no account needed).\n\n"
        "Then start it:\n\n"
        "  ollama serve\n\n"
        "Or use a cloud API: --llm claude"
    )


def _fix_ollama_model_missing(_method: str) -> str:
    return (
        "Download the model:\n\n"
        "  ollama pull llama3.2\n\n"
        "Or use a cloud API: --llm claude"
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
    "network_unreachable": _fix_network_unreachable,
    "spacy_model_missing": _fix_spacy_model_missing,
    "presidio_missing": _fix_presidio_missing,
    "mlx_not_installed": _fix_mlx_not_installed,
    "cuda_not_available": _fix_cuda_not_available,
    "low_disk_space": _fix_low_disk_space,
    "ollama_not_running": _fix_ollama_not_running,
    "ollama_not_installed": _fix_ollama_not_installed,
    "ollama_model_missing": _fix_ollama_model_missing,
}
