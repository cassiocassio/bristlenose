"""Hardware detection for choosing the optimal transcription backend.

Detects:
- Apple Silicon (M1/M2/M3/M4 and all variants) via platform + chip query
- NVIDIA GPU (CUDA) via ctranslate2
- CPU fallback

This is future-proof: any Apple Silicon chip exposes the same Metal GPU API
that MLX targets, so M1 through M4 Ultra (and beyond) all work the same way.
"""

from __future__ import annotations

import logging
import platform
import subprocess
from dataclasses import dataclass
from enum import Enum

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


def detect_hardware() -> HardwareInfo:
    """Detect the current hardware and available acceleration.

    Returns a HardwareInfo with the best available accelerator.
    Detection order: Apple Silicon (MLX) > NVIDIA (CUDA) > CPU.
    """
    info = HardwareInfo(accelerator=AcceleratorType.CPU)

    # Check for Apple Silicon
    if _is_apple_silicon():
        info.accelerator = AcceleratorType.APPLE_SILICON
        info.chip_name = _get_apple_chip_name()
        info.gpu_cores = _get_apple_gpu_cores()
        info.memory_gb = _get_system_memory_gb()
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
            text=True,
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
            text=True,
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
            text=True,
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
                text=True,
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
                with open("/proc/meminfo") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            kb = int(line.split()[1])
                            return kb / (1024 ** 2)
    except Exception:
        pass
    return None


def _check_mlx_available() -> bool:
    """Check if mlx and mlx-whisper are installed and importable."""
    try:
        import mlx  # noqa: F401
        import mlx_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def _check_cuda_available() -> bool:
    """Check if CUDA is available via ctranslate2."""
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except (ImportError, Exception):
        return False


def _get_cuda_device_name() -> str | None:
    """Get the CUDA GPU device name."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip().split("\n")[0]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None
