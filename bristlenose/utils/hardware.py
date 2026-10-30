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
            logger.info(
                "Apple Silicon detected (%s) but mlx-whisper not installed. "
                "Install with: pip install bristlenose[apple]",
                info.chip_name,
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

def _check_cuda_available() -> bool:
    """Check if CUDA is available via ctranslate2.

    Never on the frozen Windows build: it ships CPU-only, without the cuBLAS and
    cuDNN DLLs ctranslate2 loads for CUDA, yet ctranslate2 still counts an NVIDIA
    GPU when a driver is present — so the first transcription would fail on a
    missing DLL (docs/design-winget.md).
    """
    import sys

    if sys.platform == "win32" and getattr(sys, "frozen", False):
        return False
    try:
        import ctranslate2
        count: int = ctranslate2.get_cuda_device_count()
        return count > 0
    except (ImportError, Exception):
        return False


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
