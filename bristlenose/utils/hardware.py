"""Hardware detection for choosing the optimal transcription backend.

Detects:
- Apple Silicon (M1/M2/M3/M4 and all variants) via platform + chip query
- NVIDIA GPU (CUDA) via ctranslate2
- CPU fallback

This is future-proof: any Apple Silicon chip exposes the same Metal GPU API
that MLX targets, so M1 through M4 Ultra (and beyond) all work the same way.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from bristlenose.utils.safe_which import safe_which

logger = logging.getLogger(__name__)


class AcceleratorType(str, Enum):
    APPLE_SILICON = "apple_silicon"
    CUDA = "cuda"
    CPU = "cpu"


@dataclass
class HardwareInfo:
    """Detected hardware capabilities."""

    accelerator: AcceleratorType
    chip_name: str | None = None  # e.g. "Apple M2 Max", "NVIDIA RTX 4090"
    gpu_cores: int | None = None
    memory_gb: float | None = None
    mlx_available: bool = False
    cuda_available: bool = False

    # The two recommendations below are interim model pickers: fix, don't
    # grow (docs/design-pluggable-llm-routing.md §Interim model pickers).
    @property
    def recommended_whisper_backend(self) -> str:
        """Return the recommended whisper backend for this hardware."""
        if self.accelerator == AcceleratorType.APPLE_SILICON and self.mlx_available:
            return "mlx"
        return "faster-whisper"

    @property
    def recommended_whisper_model(self) -> str:
        """Suggest a whisper model size based on available memory."""
        if self.memory_gb is not None:
            if self.memory_gb >= 32:
                return "large-v3"
            if self.memory_gb >= 16:
                return "large-v3-turbo"
            if self.memory_gb >= 8:
                return "medium"
        return "small"

    @property
    def label(self) -> str:
        """Short label for CLI header: 'Apple M2 Max · MLX' or 'RTX 4090 · CUDA'."""
        name = self.chip_name or self.accelerator.value
        if self.accelerator == AcceleratorType.APPLE_SILICON:
            backend = "MLX" if self.mlx_available else "CPU"
        elif self.accelerator == AcceleratorType.CUDA:
            backend = "CUDA"
        else:
            backend = "CPU"
        if name.lower() == backend.lower():  # no chip name: "cpu · CPU"
            return backend
        return f"{name} · {backend}"

    def summary(self) -> str:
        """Human-readable summary of detected hardware."""
        parts = [f"Accelerator: {self.accelerator.value}"]
        if self.chip_name:
            parts.append(f"Chip: {self.chip_name}")
        if self.memory_gb:
            parts.append(f"Memory: {self.memory_gb:.0f}GB")
        parts.append(f"Backend: {self.recommended_whisper_backend}")
        parts.append(f"Model suggestion: {self.recommended_whisper_model}")
        return " | ".join(parts)


_CACHE_DIR = Path("~/.config/bristlenose").expanduser()
_CACHE_FILE = _CACHE_DIR / ".hardware-cache.json"
_CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 hours


def _load_hardware_cache() -> dict[str, Any] | None:
    """Load cached hardware data if it exists and is fresh (within TTL)."""
    try:
        if not _CACHE_FILE.exists():
            return None
        data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            logger.debug("Hardware cache is not a JSON object, re-detecting")
            return None
        if time.time() - data.get("timestamp", 0) < _CACHE_TTL_SECONDS:
            logger.debug("Using cached hardware info (age: %.0fs)", time.time() - data["timestamp"])
            return data
        logger.debug("Hardware cache expired, re-detecting")
    except Exception:
        logger.debug("Could not read hardware cache, re-detecting")
    return None


def _save_hardware_cache(
    chip_name: str | None, gpu_cores: int | None, memory_gb: float | None
) -> None:
    """Persist hardware detection results to disk."""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "chip_name": chip_name,
            "gpu_cores": gpu_cores,
            "memory_gb": memory_gb,
            "timestamp": time.time(),
        }
        _CACHE_FILE.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        logger.debug("Could not write hardware cache")


def detect_hardware() -> HardwareInfo:
    """Detect the current hardware and available acceleration.

    Returns a HardwareInfo with the best available accelerator.
    Detection order: Apple Silicon (MLX) > NVIDIA (CUDA) > CPU.

    Static hardware properties (chip name, GPU cores, memory) are cached
    to ~/.config/bristlenose/.hardware-cache.json with a 24h TTL to avoid
    repeated slow system_profiler calls on macOS.
    """
    info = HardwareInfo(accelerator=AcceleratorType.CPU)

    # Check for Apple Silicon
    if _is_apple_silicon():
        info.accelerator = AcceleratorType.APPLE_SILICON

        cached = _load_hardware_cache()
        if cached:
            info.chip_name = cached.get("chip_name")
            info.gpu_cores = cached.get("gpu_cores")
            info.memory_gb = cached.get("memory_gb")
        else:
            info.chip_name = _get_apple_chip_name()
            info.gpu_cores = _get_apple_gpu_cores()
            info.memory_gb = _get_system_memory_gb()
            _save_hardware_cache(info.chip_name, info.gpu_cores, info.memory_gb)

        info.mlx_available = _check_mlx_available()

        if not info.mlx_available:
            from bristlenose.utils.install_channel import add_extra_command

            logger.info(
                "Apple Silicon detected (%s) but mlx-whisper not installed. "
                "Install with: %s",
                info.chip_name,
                add_extra_command("apple"),
            )
    else:
        # Check for NVIDIA CUDA
        info.cuda_available = _check_cuda_available()
        if info.cuda_available:
            info.accelerator = AcceleratorType.CUDA
            info.chip_name = _get_cuda_device_name()

    info.memory_gb = info.memory_gb or _get_system_memory_gb()

    logger.info("Hardware detected: %s", info.summary())
    return info


def _is_apple_silicon() -> bool:
    """Check if running on Apple Silicon (any M-series chip)."""
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def _get_apple_chip_name() -> str | None:
    """Get the Apple chip name (e.g. 'Apple M2 Max') via system_profiler."""
    try:
        result = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Fallback: system_profiler (slower but more detailed)
    try:
        result = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            timeout=10,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if "Chip" in line and ":" in line:
                    return line.split(":", 1)[1].strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return "Apple Silicon (unknown model)"


def _get_apple_gpu_cores() -> int | None:
    """Get the GPU core count on Apple Silicon."""
    try:
        result = subprocess.run(
            ["system_profiler", "SPDisplaysDataType"],
            capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            timeout=10,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if "Total Number of Cores" in line and ":" in line:
                    cores_str = line.split(":", 1)[1].strip()
                    # Parse "38" or "38 (plus 2 raytracing)" etc.
                    digits = "".join(c for c in cores_str.split()[0] if c.isdigit())
                    if digits:
                        return int(digits)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def _get_system_memory_gb() -> float | None:
    """Get total system memory in GB."""

    try:
        if platform.system() == "Darwin":
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True,
                text=True, encoding="utf-8", errors="replace",
                timeout=5,
            )
            if result.returncode == 0:
                return int(result.stdout.strip()) / (1024 ** 3)
        else:
            # Linux / Windows
            import shutil
            _ = shutil.disk_usage("/").total  # not memory, but a fallback
            # Better: read /proc/meminfo on Linux
            if platform.system() == "Linux":
                with open("/proc/meminfo", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            kb = int(line.split()[1])
                            return kb / (1024 ** 2)
    except Exception:
        pass
    return None


def module_installed(name: str) -> bool:
    """Whether ``name`` is installed, without importing it.

    ``import mlx_whisper`` creates the Metal device, and when that fails the process
    dies on a native abort (SIGTRAP) that no ``except`` can catch. Whether Whisper is
    on disk, and whether a run may start, must not depend on the GPU answering: found
    on a clean macOS 15 guest, 30 Oct 2026, where it turned the launch probe, every
    Retry and the ``run`` preflight into an instant crash. Stage 5 imports the module
    when it transcribes, which is where a Mac that cannot start MLX should fail.
    """
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError) as exc:
        # A module in sys.modules with no __spec__, or a broken parent package: the
        # install is damaged, which is not the same as absent.
        logger.warning("module_installed(%s): the import system cannot say: %s", name, exc)
        return False


def _check_mlx_available() -> bool:
    """Check if mlx and mlx-whisper are installed (not imported: see
    :func:`module_installed`)."""
    return module_installed("mlx") and module_installed("mlx_whisper")



@dataclass(frozen=True)
class MlxProbe:
    """Whether MLX can start on this Mac, asked of a child process."""

    ok: bool
    detail: str = ""


def _self_command() -> list[str]:
    """Run this program again: the frozen sidecar re-executes itself (it has no ``python
    -c``: its entry point rewrites unknown arguments to ``serve``), anything else runs the
    package as a module."""
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, "-m", "bristlenose"]


def probe_mlx_starts(timeout: float = 60.0) -> MlxProbe:
    """Ask a CHILD process whether MLX starts (``doctor --mlx-probe``).

    Importing MLX creates the Metal device, and where that fails the process dies on a
    native abort that no ``except`` can catch (a macOS 26 build on macOS 15, 30 Oct 2026).
    Run in-process that would kill the caller, so the question goes to a child and a
    death by signal is the answer "no". A timeout or a child that cannot be launched is
    *inconclusive* and passes: a cold first launch on a fresh Mac took 25 s to start the
    sidecar at all, and a slow disk is not a broken GPU.
    """
    try:
        proc = subprocess.run(
            [*_self_command(), "doctor", "--mlx-probe"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        logger.warning("probe_mlx_starts: no answer in %.0f s; not holding it against MLX", timeout)
        return MlxProbe(ok=True)
    except OSError as exc:
        logger.warning("probe_mlx_starts: could not run the probe: %s", exc)
        return MlxProbe(ok=True)
    if proc.returncode == 0:
        return MlxProbe(ok=True)
    if proc.returncode < 0:
        return MlxProbe(ok=False, detail=f"the probe was stopped by signal {-proc.returncode}")
    tail = (proc.stderr or "").strip().splitlines()[-1:] or [f"exit {proc.returncode}"]
    return MlxProbe(ok=False, detail=tail[0][:200])

# The CUDA libraries ctranslate2 loads at run time, read from its wheels on
# 19 Nov 2026 (Windows 4.0.0-4.9.0, Linux 4.0.0-4.9.0): cuBLAS 12 throughout 4.x;
# cuDNN 8 up to 4.4, cuDNN 9 in 4.5 and 4.6, and no cuDNN from 4.7.0. faster-whisper
# allows any 4.x, so the list follows the installed version. The driver brings
# nvcuda.dll / libcuda.so.1; cuBLAS (and cuDNN) come only with NVIDIA's toolkits or
# pip wheels. So a laptop with the GPU and the driver alone has a GPU ctranslate2
# counts and a first transcription that would fail to load them. cuBLASLt is a
# dependency of cuBLAS rather than a name ctranslate2 loads; it is listed because a
# cuBLAS without it does not load. tests/test_hardware.py pins the Linux cuBLAS name
# against the installed wheel.
_CUBLAS: dict[str, tuple[str, ...]] = {
    "win32": ("cublas64_12.dll", "cublasLt64_12.dll"),
    "linux": ("libcublas.so.12", "libcublasLt.so.12"),
}
_CUDNN_9: dict[str, tuple[str, ...]] = {
    "win32": ("cudnn_ops64_9.dll", "cudnn_cnn64_9.dll"),
    "linux": ("libcudnn_ops.so.9", "libcudnn_cnn.so.9"),
}
_CUDNN_8: dict[str, tuple[str, ...]] = {
    "win32": ("cudnn_ops_infer64_8.dll", "cudnn_cnn_infer64_8.dll"),
    "linux": ("libcudnn_ops_infer.so.8", "libcudnn_cnn_infer.so.8"),
}


def cuda_libraries_for(ct2_version: str, platform_key: str) -> tuple[str, ...]:
    """The CUDA libraries ctranslate2 *ct2_version* loads on *platform_key*
    (``sys.platform``); unknown versions are treated as the newest."""
    import re

    match = re.match(r"(\d+)\.(\d+)", ct2_version or "")
    major, minor = (int(match.group(1)), int(match.group(2))) if match else (99, 0)
    names = _CUBLAS.get(platform_key, ())
    if major == 4 and minor < 5:
        names += _CUDNN_8.get(platform_key, ())
    elif major == 4 and minor < 7:
        names += _CUDNN_9.get(platform_key, ())
    return names


def _windows_dll_dirs(ct2_dir: Path | None) -> list[Path]:
    """Where Windows' loader would find a DLL ctranslate2 loads by name: its own
    folder (it preloads every DLL there), Python's folder, System32, then PATH. The
    current folder is left out on purpose: a DLL planted beside a user's recordings
    must not count, and nothing here loads what it finds (``safe_which`` reasons the
    same way for executables)."""
    import os

    dirs: list[Path] = []
    if ct2_dir is not None:
        dirs.append(ct2_dir)
    dirs.append(Path(sys.executable).parent)
    system_root = os.environ.get("SystemRoot")
    if system_root:
        dirs.append(Path(system_root) / "System32")
    dirs.extend(Path(entry) for entry in os.environ.get("PATH", "").split(os.pathsep) if entry)
    return dirs


def _linux_library_dirs(ct2_dir: Path | None) -> list[Path]:
    """Where ``dlopen`` looks for a library libctranslate2 names, cache aside: the
    library's own RPATH (``$ORIGIN``, the ``ctranslate2.libs`` folder beside the
    package), ``LD_LIBRARY_PATH``, then the default folders."""
    import os

    dirs: list[Path] = []
    if ct2_dir is not None:
        dirs.append(ct2_dir.parent / "ctranslate2.libs")
    dirs.extend(Path(entry) for entry in os.environ.get("LD_LIBRARY_PATH", "").split(":") if entry)
    dirs.extend(Path(p) for p in ("/lib", "/usr/lib", "/lib64", "/usr/lib64"))
    return dirs


_LDCONFIG_PATHS = ("/sbin/ldconfig", "/usr/sbin/ldconfig")


def _ld_cache_names() -> set[str]:
    """The sonames in the dynamic loader's cache (``ldconfig -p``), or none."""
    import os

    ldconfig = next((p for p in _LDCONFIG_PATHS if os.path.exists(p)), None)
    if ldconfig is None:
        return set()
    try:
        out = subprocess.run(
            [ldconfig, "-p"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=5,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return set()
    return {line.split()[0] for line in out.splitlines()[1:] if line.strip()}


def _library_loads(
    name: str, ct2_dir: Path | None = None, ld_cache: set[str] | None = None,
) -> bool:
    """Whether *name* is where ctranslate2 would load it from: a file in the
    loader's search folders, never a load. Loading cuBLAS to answer the question
    mapped about 150 MB into every process that asked (measured 19 Nov 2026 with
    NVIDIA's cuBLAS 12.9 wheel), including a long-lived ``serve`` that never
    transcribes, and on Windows it would run third-party code. A file that is
    present but broken passes here and fails at transcription, as before."""
    try:
        if sys.platform == "win32":
            return any((folder / name).is_file() for folder in _windows_dll_dirs(ct2_dir))
        if any((folder / name).is_file() for folder in _linux_library_dirs(ct2_dir)):
            return True
        return name in (ld_cache if ld_cache is not None else _ld_cache_names())
    except Exception:  # noqa: BLE001 - a probe answers "not here", it never raises
        return False


def cuda_libraries_missing() -> list[str]:
    """The CUDA libraries the installed ctranslate2 needs that are not here."""
    try:
        import ctranslate2

        version = str(getattr(ctranslate2, "__version__", ""))
        location = getattr(ctranslate2, "__file__", None)
        ct2_dir = Path(location).parent if isinstance(location, str) else None
    except Exception:  # noqa: BLE001 - no ctranslate2, no CUDA question to answer
        return []
    names = cuda_libraries_for(version, sys.platform)
    if not names:
        return []
    ld_cache = _ld_cache_names() if sys.platform.startswith("linux") else set()
    return [name for name in names if not _library_loads(name, ct2_dir, ld_cache)]


def _check_cuda_available() -> bool:
    """Check if CUDA is available via ctranslate2.

    Never on the frozen Windows build: it ships CPU-only, without the CUDA
    libraries ctranslate2 loads for it, yet ctranslate2 still counts an NVIDIA
    GPU when a driver is present, so the first transcription would fail on a
    missing DLL (docs/design-winget.md).

    Elsewhere, a counted GPU is used only if the CUDA libraries the installed
    ctranslate2 loads are there too (:func:`cuda_libraries_for`): a driver alone is
    the common case on a laptop with an NVIDIA GPU, and it would fail the same way
    (docs/design-windows-linux-hardware-testing.md §5).
    """
    import sys

    if sys.platform == "win32" and getattr(sys, "frozen", False):
        return False
    try:
        import ctranslate2
        count: int = ctranslate2.get_cuda_device_count()
    except (ImportError, Exception):
        return False
    if count <= 0:
        return False
    missing = cuda_libraries_missing()
    if missing:
        logger.info(
            "NVIDIA GPU found but %s cannot be loaded: transcribing on the CPU",
            ", ".join(missing),
        )
        return False
    return True


WHISPER_DEVICES = ("auto", "cpu", "cuda")


def requested_whisper_device(settings: object) -> str:
    """``BRISTLENOSE_WHISPER_DEVICE`` as asked for: cpu, cuda or auto (anything
    else reads as auto; the stage that transcribes says so in the log)."""
    requested = str(getattr(settings, "whisper_device", "auto") or "auto").strip().lower()
    return requested if requested in WHISPER_DEVICES else "auto"


def effective_whisper_device(settings: object, cuda_available: bool) -> str:
    """"cuda" or "cpu": what faster-whisper runs on, given the setting and whether
    the hardware check found a usable GPU. Never "cuda" on macOS: ctranslate2's Mac
    build has no CUDA, and faster-whisper still runs there when MLX is absent or
    the backend is pinned, so a .env shared with a Linux GPU box must not fail it."""
    if sys.platform == "darwin":
        return "cpu"
    requested = requested_whisper_device(settings)
    return "cuda" if requested == "cuda" or (requested == "auto" and cuda_available) else "cpu"


def effective_accelerator(hw: HardwareInfo, settings: object) -> AcceleratorType:
    """The accelerator transcription will actually use: the hardware's, unless
    ``BRISTLENOSE_WHISPER_DEVICE`` overrides it (faster-whisper only, and never to
    CUDA on macOS). The one answer for the stage, doctor, the header and the
    timing key, so none of them says CUDA for a CPU run."""
    if hw.accelerator is AcceleratorType.APPLE_SILICON:
        return hw.accelerator
    if effective_whisper_device(settings, hw.cuda_available) == "cuda":
        return AcceleratorType.CUDA
    return AcceleratorType.CPU


def _get_cuda_device_name() -> str | None:
    """Get the CUDA GPU device name."""
    # Resolved, never the bare name: on Windows that would be looked up in the
    # current directory first (utils.safe_which).
    nvidia_smi = safe_which("nvidia-smi")
    if nvidia_smi is None:
        return None
    try:
        result = subprocess.run(
            [nvidia_smi, "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip().split("\n")[0]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None
