"""Ollama detection and model management.

Provides functions to check if Ollama is running, find suitable models,
and pull models on demand.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Models known to work well with structured output, in preference order.
# Based on Ollama's structured output documentation.
PREFERRED_MODELS = [
    "llama3.2:3b",  # Default — 2 GB download, ~4 GB RAM, good for most laptops
    "llama3.2",  # Alias for latest llama3.2
    "llama3.2:1b",  # Smaller, for constrained environments
    "llama3.1:8b",  # Larger, better quality
    "mistral:7b",  # Good alternative
    "qwen2.5:7b",  # Good multilingual support
]

DEFAULT_MODEL = "llama3.2:3b"
OLLAMA_API_URL = "http://localhost:11434"


@dataclass
class OllamaStatus:
    """Result of checking Ollama availability."""

    is_running: bool
    has_suitable_model: bool
    recommended_model: str | None
    available_models: list[str]
    message: str


def check_ollama() -> OllamaStatus:
    """Check if Ollama is running and has a suitable model.

    Returns:
        OllamaStatus with availability information.
    """
    import urllib.error
    import urllib.request

    try:
        # Check Ollama is running by hitting the tags endpoint
        req = urllib.request.Request(f"{OLLAMA_API_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            import json

            data = json.loads(resp.read().decode())
            models = data.get("models", [])
            available = [m.get("name", "") for m in models]

            # Look for suitable models in priority order
            for preferred in PREFERRED_MODELS:
                # Check for exact match or prefix match (llama3.2 matches llama3.2:3b)
                for model in available:
                    if model == preferred or model.startswith(preferred.split(":")[0] + ":"):
                        return OllamaStatus(
                            is_running=True,
                            has_suitable_model=True,
                            recommended_model=model,
                            available_models=available,
                            message=f"Found {model}",
                        )

            # Check for any llama/mistral/qwen model
            suitable = [
                m
                for m in available
                if any(m.startswith(p) for p in ["llama", "mistral", "qwen"])
            ]
            if suitable:
                return OllamaStatus(
                    is_running=True,
                    has_suitable_model=True,
                    recommended_model=suitable[0],
                    available_models=available,
                    message=f"Found {suitable[0]}",
                )

            # Ollama is running but no suitable model
            return OllamaStatus(
                is_running=True,
                has_suitable_model=False,
                recommended_model=None,
                available_models=available,
                message="No suitable model found",
            )

    except urllib.error.URLError:
        return OllamaStatus(
            is_running=False,
            has_suitable_model=False,
            recommended_model=None,
            available_models=[],
            message="Ollama not running",
        )
    except Exception as e:
        logger.debug("Error checking Ollama: %s", e)
        return OllamaStatus(
            is_running=False,
            has_suitable_model=False,
            recommended_model=None,
            available_models=[],
            message=f"Error: {e}",
        )


def is_ollama_installed() -> bool:
    """Check if the ollama command is available in PATH."""
    import shutil

    return shutil.which("ollama") is not None


def pull_model(model: str = DEFAULT_MODEL) -> bool:
    """Pull a model from the Ollama registry.

    Shows progress to the user via Ollama's own output.

    Returns:
        True if successful, False otherwise.
    """
    try:
        result = subprocess.run(
            ["ollama", "pull", model],
            stdout=sys.stdout,  # Show Ollama's progress bar
            stderr=sys.stderr,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False
    except Exception as e:
        logger.debug("Error pulling model: %s", e)
        return False


def validate_local_endpoint(url: str, model: str) -> tuple[bool | None, str]:
    """Validate that a local endpoint is reachable and has the specified model.

    Returns:
        (True, "") if valid,
        (False, error) if endpoint is reachable but model not found,
        (None, error) if endpoint is unreachable.
    """
    import json
    import urllib.error
    import urllib.request

    # Normalise URL to API endpoint
    base_url = url.rstrip("/")
    if base_url.endswith("/v1"):
        base_url = base_url[:-3]

    try:
        req = urllib.request.Request(f"{base_url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            models = data.get("models", [])
            available = [m.get("name", "") for m in models]

            # Check if the requested model is available
            if model in available:
                return (True, "")

            # Check for partial match (e.g. "llama3.2" matches "llama3.2:3b")
            model_base = model.split(":")[0]
            for m in available:
                if m.startswith(model_base):
                    return (True, "")

            return (False, f"Model '{model}' not found. Run: ollama pull {model}")

    except urllib.error.URLError:
        return (None, "Cannot connect to local model server. Is Ollama running?")
    except Exception as e:
        return (None, str(e))
