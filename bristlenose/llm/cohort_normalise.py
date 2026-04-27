"""Normalise provider/model strings to a (family, major) cohort key.

Telemetry rows carry the raw response model string from the provider
(e.g. ``claude-sonnet-4-20250514``, ``gpt-4o-2024-08-06``). For cohort
lookup we need a stable key that survives minor model revisions —
``(family, major)`` like ``("claude-sonnet", "4")``.

Pure stdlib, no SDK imports. Table-driven per provider; unknown
providers raise ``ValueError``.
"""

from __future__ import annotations

import re

_KNOWN_PROVIDERS = frozenset({"anthropic", "openai", "azure", "google", "local"})

# Anthropic: claude-<family>-<major>[-<date>]
# e.g. claude-sonnet-4-20250514 → ("claude-sonnet", "4")
#      claude-opus-4-7         → ("claude-opus", "4")
#      claude-haiku-4-5        → ("claude-haiku", "4")
_ANTHROPIC_RE = re.compile(
    r"^claude-(?P<family>opus|sonnet|haiku)-(?P<major>\d+)",
    re.IGNORECASE,
)

# OpenAI: gpt-<major>[suffix][-<date>]
# e.g. gpt-4o, gpt-4o-mini → ("gpt-4o", "4") / ("gpt-4o-mini", "4")
#      gpt-5, gpt-5-mini   → ("gpt-5", "5")
#      o1, o3-mini          → ("o1", "1") / ("o3-mini", "3")
_OPENAI_GPT_RE = re.compile(
    r"^(?P<family>gpt-\d+[a-z]*(?:-mini|-nano|-turbo)?)(?:-\d{4}-\d{2}-\d{2})?$",
    re.IGNORECASE,
)
_OPENAI_O_RE = re.compile(
    r"^(?P<family>o\d+(?:-mini|-pro)?)(?:-\d{4}-\d{2}-\d{2})?$",
    re.IGNORECASE,
)
_OPENAI_MAJOR_RE = re.compile(r"(\d+)")

# Google: gemini-<major>.<minor>-<family>[-...]
# e.g. gemini-2.5-pro → ("gemini-pro", "2")
#      gemini-2.5-flash → ("gemini-flash", "2")
#      gemini-1.5-pro → ("gemini-pro", "1")
_GEMINI_RE = re.compile(
    r"^gemini-(?P<major>\d+)(?:\.\d+)?-(?P<family>pro|flash|ultra|nano)",
    re.IGNORECASE,
)

# Local (Ollama): <name>[:<tag>]
# e.g. llama3.2:3b → ("llama", "3")
#      mistral:7b → ("mistral", "0")
#      qwen2.5:7b → ("qwen", "2")
_LOCAL_RE = re.compile(
    r"^(?P<family>[a-z]+)(?P<major>\d+)?",
    re.IGNORECASE,
)


def normalise_model(provider: str, response_model: str) -> tuple[str, str]:
    """Return a stable ``(family, major)`` cohort key.

    Args:
        provider: Canonical provider name — one of
            ``anthropic``, ``openai``, ``azure``, ``google``, ``local``.
        response_model: The provider's response-side model string
            (post-aliasing, post-deployment-resolution).

    Returns:
        ``(family, major)`` — both strings, both lowercase.

    Raises:
        ValueError: If ``provider`` is not a known provider.
    """
    if provider not in _KNOWN_PROVIDERS:
        msg = f"unknown provider {provider!r}"
        raise ValueError(msg)

    model = response_model.strip()
    if not model:
        return ("unknown", "0")

    if provider == "anthropic":
        m = _ANTHROPIC_RE.match(model)
        if m:
            return (f"claude-{m.group('family').lower()}", m.group("major"))
        return (model.lower(), "0")

    if provider == "openai":
        m = _OPENAI_GPT_RE.match(model) or _OPENAI_O_RE.match(model)
        if m:
            family = m.group("family").lower()
            major_match = _OPENAI_MAJOR_RE.search(family)
            major = major_match.group(1) if major_match else "0"
            return (family, major)
        return (model.lower(), "0")

    if provider == "azure":
        # Deployment names are user-defined opaque strings.
        # Treat the whole string as the family; major is "0".
        return (model.lower(), "0")

    if provider == "google":
        m = _GEMINI_RE.match(model)
        if m:
            return (f"gemini-{m.group('family').lower()}", m.group("major"))
        return (model.lower(), "0")

    # local (Ollama)
    base = model.split(":", 1)[0]
    m = _LOCAL_RE.match(base)
    if m:
        family = m.group("family").lower()
        major = m.group("major") or "0"
        return (family, major)
    return (base.lower(), "0")
