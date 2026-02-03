"""Dependency health checks and pre-flight validation.

Pure check logic — no UI, no Rich formatting. Each check function returns a
CheckResult. The CLI layer (cli.py) handles display.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bristlenose.config import BristlenoseSettings

logger = logging.getLogger(__name__)


class CheckStatus(str, Enum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "--"


@dataclass
class CheckResult:
    """Result of a single health check."""

    status: CheckStatus
    label: str
    detail: str = ""
    fix_key: str = ""


@dataclass
class DoctorReport:
    """Aggregate result of all checks."""

    results: list[CheckResult] = field(default_factory=list)

    @property
    def has_failures(self) -> bool:
        return any(r.status == CheckStatus.FAIL for r in self.results)

    @property
    def has_warnings(self) -> bool:
        return any(r.status == CheckStatus.WARN for r in self.results)

    @property
    def failures(self) -> list[CheckResult]:
        return [r for r in self.results if r.status == CheckStatus.FAIL]

    @property
    def warnings(self) -> list[CheckResult]:
        return [r for r in self.results if r.status == CheckStatus.WARN]

    @property
    def notes(self) -> list[CheckResult]:
        return [r for r in self.results if r.status == CheckStatus.SKIP]


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def check_ffmpeg() -> CheckResult:
    """Check whether FFmpeg is installed and in PATH."""
    path = shutil.which("ffmpeg")
    if path is None:
        return CheckResult(
            status=CheckStatus.FAIL,
            label="FFmpeg",
            detail="not found",
            fix_key="ffmpeg_missing",
        )

    # Try to get version
    version = ""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            first_line = result.stdout.split("\n")[0]
            # "ffmpeg version 6.1.1 Copyright ..." → "6.1.1"
            parts = first_line.split()
            if len(parts) >= 3:
                version = parts[2]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    detail = f"{version} ({path})" if version else path
    return CheckResult(status=CheckStatus.OK, label="FFmpeg", detail=detail)


def check_backend() -> CheckResult:
    """Check whether faster-whisper and ctranslate2 are importable."""
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        return CheckResult(
            status=CheckStatus.FAIL,
            label="Transcription",
            detail="faster-whisper not installed",
            fix_key="backend_import_fail",
        )
    except Exception as exc:
        return CheckResult(
            status=CheckStatus.FAIL,
            label="Transcription",
            detail=f"faster-whisper failed to load: {exc}",
            fix_key="backend_import_fail",
        )

    # ctranslate2 version and GPU info
    ct2_version = ""
    accel = "CPU"
    try:
        import ctranslate2

        ct2_version = getattr(ctranslate2, "__version__", "")
        try:
            if ctranslate2.get_cuda_device_count() > 0:
                accel = "CUDA"
        except Exception:
            pass
    except ImportError:
        return CheckResult(
            status=CheckStatus.FAIL,
            label="Transcription",
            detail="ctranslate2 not installed",
            fix_key="backend_import_fail",
        )
    except Exception as exc:
        return CheckResult(
            status=CheckStatus.FAIL,
            label="Transcription",
            detail=str(exc),
            fix_key="backend_import_fail",
        )

    fw_version = ""
    try:
        import faster_whisper as _fw

        fw_version = getattr(_fw, "__version__", "")
    except Exception:
        pass

    # Check for MLX on Apple Silicon
    import platform as _platform

    has_mlx = False
    is_apple_silicon = (
        _platform.system() == "Darwin" and _platform.machine() == "arm64"
    )
    if is_apple_silicon:
        try:
            import mlx_whisper  # noqa: F401

            has_mlx = True
            accel = "MLX"
        except ImportError:
            pass

    parts = []
    if fw_version:
        parts.append(f"faster-whisper {fw_version}")
    else:
        parts.append("faster-whisper")
    if ct2_version:
        parts.append(f"ctranslate2 {ct2_version}")
    parts.append(f"({accel})")

    detail = ", ".join(parts[:-1]) + f" {parts[-1]}" if len(parts) > 1 else parts[0]

    # Warn if Apple Silicon without MLX
    if is_apple_silicon and not has_mlx:
        return CheckResult(
            status=CheckStatus.WARN,
            label="Transcription",
            detail=f"{detail.rstrip(')')}, Apple Silicon, CPU mode)",
            fix_key="mlx_not_installed",
        )

    # Warn if NVIDIA GPU detected but CUDA not available
    if accel == "CPU":
        nvidia_detected = shutil.which("nvidia-smi") is not None
        if nvidia_detected:
            return CheckResult(
                status=CheckStatus.WARN,
                label="Transcription",
                detail=(
                    f"{detail.rstrip(')')}, NVIDIA GPU detected "
                    "but CUDA runtime not available — using CPU)"
                ),
                fix_key="cuda_not_available",
            )

    return CheckResult(status=CheckStatus.OK, label="Transcription", detail=detail)


def check_whisper_model(settings: BristlenoseSettings) -> CheckResult:
    """Check whether the configured Whisper model is already cached."""
    model_name = settings.whisper_model

    # Try huggingface_hub cache scan first
    try:
        from huggingface_hub import scan_cache_dir

        cache_info = scan_cache_dir()
        # faster-whisper models are stored as "Systran/faster-whisper-{model}"
        repo_id = f"Systran/faster-whisper-{model_name}"
        cached_repos = {r.repo_id for r in cache_info.repos}
        if repo_id in cached_repos:
            # Find size
            for repo in cache_info.repos:
                if repo.repo_id == repo_id:
                    size_gb = repo.size_on_disk / (1024**3)
                    return CheckResult(
                        status=CheckStatus.OK,
                        label="Whisper model",
                        detail=f"{model_name} cached ({size_gb:.1f} GB)",
                    )
    except ImportError:
        pass
    except Exception:
        pass

    # Model not cached — this is informational, not a failure
    return CheckResult(
        status=CheckStatus.SKIP,
        label="Whisper model",
        detail=f"{model_name} not cached (~1.5 GB download on first run)",
    )


def check_api_key(settings: BristlenoseSettings) -> CheckResult:
    """Check whether an API key is configured for the selected LLM provider."""
    from bristlenose.credentials import get_credential_source

    provider = settings.llm_provider

    if provider == "anthropic":
        key = settings.anthropic_api_key
        if not key:
            return CheckResult(
                status=CheckStatus.FAIL,
                label="API key",
                detail="No Anthropic API key",
                fix_key="api_key_missing_anthropic",
            )
        masked = f"sk-ant-...{key[-3:]}" if len(key) > 10 else "(set)"
        source = get_credential_source("anthropic")
        source_label = " (Keychain)" if source == "keychain" else ""
        # Validate key with a cheap API call
        valid, err = _validate_anthropic_key(key)
        if valid is False:
            return CheckResult(
                status=CheckStatus.FAIL,
                label="API key",
                detail=f"Anthropic key rejected ({err})",
                fix_key="api_key_invalid_anthropic",
            )
        if valid is None:
            # Couldn't validate (network issue) — key is present, warn
            return CheckResult(
                status=CheckStatus.OK,
                label="API key",
                detail=f"Anthropic ({masked}){source_label} (could not validate: {err})",
            )
        return CheckResult(
            status=CheckStatus.OK,
            label="API key",
            detail=f"Anthropic ({masked}){source_label}",
        )

    if provider == "openai":
        key = settings.openai_api_key
        if not key:
            return CheckResult(
                status=CheckStatus.FAIL,
                label="API key",
                detail="No OpenAI API key",
                fix_key="api_key_missing_openai",
            )
        masked = f"sk-...{key[-3:]}" if len(key) > 10 else "(set)"
        source = get_credential_source("openai")
        source_label = " (Keychain)" if source == "keychain" else ""
        valid, err = _validate_openai_key(key)
        if valid is False:
            return CheckResult(
                status=CheckStatus.FAIL,
                label="API key",
                detail=f"OpenAI key rejected ({err})",
                fix_key="api_key_invalid_openai",
            )
        if valid is None:
            return CheckResult(
                status=CheckStatus.OK,
                label="API key",
                detail=f"OpenAI ({masked}){source_label} (could not validate: {err})",
            )
        return CheckResult(
            status=CheckStatus.OK,
            label="API key",
            detail=f"OpenAI ({masked}){source_label}",
        )

    if provider == "local":
        # Local provider doesn't need an API key, but needs Ollama running
        return check_local_provider(settings)

    return CheckResult(
        status=CheckStatus.FAIL,
        label="API key",
        detail=f"Unknown LLM provider: {provider}",
        fix_key="api_key_missing_anthropic",
    )


def check_local_provider(settings: BristlenoseSettings) -> CheckResult:
    """Check whether Ollama is running and has a suitable model."""
    from bristlenose.ollama import validate_local_endpoint

    url = settings.local_url
    model = settings.local_model

    valid, err = validate_local_endpoint(url, model)

    if valid is True:
        return CheckResult(
            status=CheckStatus.OK,
            label="LLM provider",
            detail=f"Local ({model} via Ollama)",
        )
    if valid is False:
        return CheckResult(
            status=CheckStatus.FAIL,
            label="LLM provider",
            detail=err,
            fix_key="ollama_model_missing",
        )
    # valid is None — couldn't connect
    # Determine appropriate fix based on error message
    if "not installed" in err:
        fix_key = "ollama_not_installed"
    else:
        fix_key = "ollama_not_running"
    return CheckResult(
        status=CheckStatus.FAIL,
        label="LLM provider",
        detail=err,
        fix_key=fix_key,
    )


def check_network(settings: BristlenoseSettings) -> CheckResult:
    """Quick HTTPS connectivity check to the API endpoint."""
    import urllib.error
    import urllib.request

    provider = settings.llm_provider

    # Local provider doesn't need network connectivity to cloud APIs
    if provider == "local":
        return CheckResult(
            status=CheckStatus.SKIP,
            label="Network",
            detail="local provider (no cloud API needed)",
        )

    if provider == "anthropic":
        url = "https://api.anthropic.com"
        host = "api.anthropic.com"
    elif provider == "openai":
        url = "https://api.openai.com"
        host = "api.openai.com"
    else:
        url = "https://api.anthropic.com"
        host = "api.anthropic.com"

    try:
        import time

        start = time.monotonic()
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=5):
            pass
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return CheckResult(
            status=CheckStatus.OK,
            label="Network",
            detail=f"{host} reachable ({elapsed_ms}ms)",
        )
    except urllib.error.HTTPError:
        # Any HTTP response (even 404) means the host is reachable.
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return CheckResult(
            status=CheckStatus.OK,
            label="Network",
            detail=f"{host} reachable ({elapsed_ms}ms)",
        )
    except urllib.error.URLError:
        return CheckResult(
            status=CheckStatus.FAIL,
            label="Network",
            detail=f"Can't reach {host}",
            fix_key="network_unreachable",
        )
    except Exception:
        return CheckResult(
            status=CheckStatus.FAIL,
            label="Network",
            detail=f"Can't reach {host}",
            fix_key="network_unreachable",
        )


def check_pii(settings: BristlenoseSettings) -> CheckResult:
    """Check PII redaction dependencies (only when --redact-pii is active)."""
    if not settings.pii_enabled:
        return CheckResult(
            status=CheckStatus.SKIP,
            label="PII redaction",
            detail="off (use --redact-pii to enable)",
        )

    # Check presidio
    try:
        import presidio_analyzer  # noqa: F401
    except ImportError:
        return CheckResult(
            status=CheckStatus.FAIL,
            label="PII redaction",
            detail="presidio-analyzer not installed",
            fix_key="presidio_missing",
        )

    presidio_version = ""
    try:
        import importlib.metadata

        presidio_version = importlib.metadata.version("presidio-analyzer")
    except Exception:
        pass

    # Check spaCy model
    try:
        import spacy

        spacy.load("en_core_web_sm")
    except ImportError:
        return CheckResult(
            status=CheckStatus.FAIL,
            label="PII redaction",
            detail="spaCy not installed",
            fix_key="spacy_model_missing",
        )
    except OSError:
        return CheckResult(
            status=CheckStatus.FAIL,
            label="PII redaction",
            detail="spaCy model en_core_web_sm not found",
            fix_key="spacy_model_missing",
        )

    spacy_model_version = ""
    try:
        nlp = spacy.load("en_core_web_sm")
        spacy_model_version = nlp.meta.get("version", "")
    except Exception:
        pass

    parts = []
    if presidio_version:
        parts.append(f"presidio {presidio_version}")
    else:
        parts.append("presidio")
    if spacy_model_version:
        parts.append(f"spaCy en_core_web_sm {spacy_model_version}")
    else:
        parts.append("spaCy en_core_web_sm")

    return CheckResult(
        status=CheckStatus.OK,
        label="PII redaction",
        detail=", ".join(parts),
    )


def check_disk_space(settings: BristlenoseSettings) -> CheckResult:
    """Check available disk space in the output directory."""
    output_path = settings.output_dir
    # Use parent if output dir doesn't exist yet
    check_path = output_path if output_path.exists() else output_path.parent
    if not check_path.exists():
        check_path = output_path.parent
        while not check_path.exists() and check_path != check_path.parent:
            check_path = check_path.parent

    try:
        usage = shutil.disk_usage(check_path)
        free_gb = usage.free / (1024**3)

        if free_gb < 2.0:
            free_mb = int(usage.free / (1024**2))
            return CheckResult(
                status=CheckStatus.WARN,
                label="Disk space",
                detail=f"{free_mb} MB free",
                fix_key="low_disk_space",
            )
        return CheckResult(
            status=CheckStatus.OK,
            label="Disk space",
            detail=f"{free_gb:.0f} GB free",
        )
    except OSError:
        return CheckResult(
            status=CheckStatus.OK,
            label="Disk space",
            detail="(could not check)",
        )


# ---------------------------------------------------------------------------
# Aggregators
# ---------------------------------------------------------------------------

# Which checks each command needs
_COMMAND_CHECKS: dict[str, list[str]] = {
    "run": [
        "ffmpeg", "backend", "whisper_model", "api_key", "network", "pii", "disk_space",
    ],
    "run_skip_tx": ["api_key", "network", "pii", "disk_space"],
    "transcribe-only": ["ffmpeg", "backend", "whisper_model", "disk_space"],
    "analyze": ["api_key", "network", "disk_space"],
    "render": [],  # no pre-flight needed
}


def run_all(settings: BristlenoseSettings) -> DoctorReport:
    """Run all seven checks (used by explicit `bristlenose doctor`)."""
    return DoctorReport(results=[
        check_ffmpeg(),
        check_backend(),
        check_whisper_model(settings),
        check_api_key(settings),
        check_network(settings),
        check_pii(settings),
        check_disk_space(settings),
    ])


def run_preflight(
    settings: BristlenoseSettings,
    command: str,
    *,
    skip_transcription: bool = False,
) -> DoctorReport:
    """Run only the checks relevant to a specific command."""
    if command == "run" and skip_transcription:
        check_names = _COMMAND_CHECKS["run_skip_tx"]
    else:
        check_names = _COMMAND_CHECKS.get(command, [])

    if not check_names:
        return DoctorReport()

    _check_fns: dict[str, object] = {
        "ffmpeg": lambda: check_ffmpeg(),
        "backend": lambda: check_backend(),
        "whisper_model": lambda: check_whisper_model(settings),
        "api_key": lambda: check_api_key(settings),
        "network": lambda: check_network(settings),
        "pii": lambda: check_pii(settings),
        "disk_space": lambda: check_disk_space(settings),
    }

    results = []
    for name in check_names:
        fn = _check_fns.get(name)
        if fn is not None:
            results.append(fn())  # type: ignore[operator]

    return DoctorReport(results=results)


# ---------------------------------------------------------------------------
# API key validation helpers (cheap calls)
# ---------------------------------------------------------------------------


def _validate_anthropic_key(key: str) -> tuple[bool | None, str]:
    """Validate an Anthropic API key with a cheap API call.

    Returns (True, "") if valid, (False, error) if rejected,
    (None, error) if we couldn't check (network issue).
    """
    import json
    import urllib.error
    import urllib.request

    try:
        # Use the messages endpoint with a minimal request to validate the key.
        # The count_tokens endpoint or models list would be lighter, but
        # the messages endpoint with max_tokens=1 is universally available.
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            method="POST",
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            data=json.dumps({
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "hi"}],
            }).encode(),
        )
        with urllib.request.urlopen(req, timeout=10):
            pass
        return (True, "")
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return (False, "401 Unauthorized")
        if exc.code == 403:
            return (False, "403 Forbidden")
        # 400, 429, 500 etc — key is valid, API just returned an error
        if exc.code in (400, 429, 500, 503, 529):
            return (True, "")
        return (None, f"HTTP {exc.code}")
    except urllib.error.URLError as exc:
        return (None, str(exc.reason))
    except Exception as exc:
        return (None, str(exc))


def _validate_openai_key(key: str) -> tuple[bool | None, str]:
    """Validate an OpenAI API key with a cheap API call.

    Returns (True, "") if valid, (False, error) if rejected,
    (None, error) if we couldn't check (network issue).
    """
    import urllib.error
    import urllib.request

    try:
        req = urllib.request.Request(
            "https://api.openai.com/v1/models",
            method="GET",
            headers={"Authorization": f"Bearer {key}"},
        )
        with urllib.request.urlopen(req, timeout=10):
            pass
        return (True, "")
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return (False, "401 Unauthorized")
        if exc.code in (429, 500, 503):
            return (True, "")
        return (None, f"HTTP {exc.code}")
    except urllib.error.URLError as exc:
        return (None, str(exc.reason))
    except Exception as exc:
        return (None, str(exc))
