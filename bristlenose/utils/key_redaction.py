"""Mask API-key-shaped text before a provider's words are logged, stored or shown.

A provider's error ``str`` can carry the request back, and a proxy or gateway in
front of it can echo headers. Wherever such text leaves the call site (the run
log, ``pipeline-events.jsonl``, the AutoCode job row, the chat lens's error, the
preflight copy) it goes through :func:`redact_keys` first.

The patterns are the Mac's (``BristlenoseShared.swift``: ``keyRedactionRegex``,
``azureKeyRedactionRegex``, ``azureHexKeyRedactionRegex``), copied verbatim so the
two cannot drift: ``tests/test_key_redaction.py`` reads the Swift source and
fails if they differ. The reasoning for each shape, and what each still cannot
tell, is written once, there.

Defence in depth, not a licence to log keys: it masks shapes it knows and misses
a key whose format it does not.
"""

from __future__ import annotations

import re

#: Anthropic, OpenAI (project-scoped and historical) and Google key shapes.
KEY_PATTERN = "|".join(
    [
        r"sk-ant-(api|sid)[0-9]{2}-[A-Za-z0-9_\-]{90,}",
        r"sk-(proj|None)-[A-Za-z0-9_\-]{48,}",
        r"sk-[A-Za-z0-9]{48}",
        r"AIza[A-Za-z0-9_\-]{35}",
    ]
)

#: Azure / Foundry, the 84-character key: a whole token holding a letter and a digit.
AZURE_KEY_PATTERN = (
    r"(?<![A-Za-z0-9_./-])(?=[A-Za-z0-9_-]*[0-9])(?=[A-Za-z0-9_-]*[A-Za-z])"
    r"[A-Za-z0-9_-]{84}(?![A-Za-z0-9_/-])"
)

#: Azure, the classic 32-hex key: only directly after a key-ish word and a separator.
AZURE_HEX_KEY_PATTERN = (
    r"(?i)("
    r"(?<![a-z0-9_-])(?:[a-z0-9_-]*(?:key|secret|token|password)|authorization|azure_[a-z0-9_]*)"
    "[\"']?[ \\t]*[:=][ \\t]*[\"']?(?:bearer[ \\t]+)?"
    "|(?<![a-z0-9_-])bearer[ \\t]+[\"']?"
    r")[0-9a-f]{32}(?![0-9a-z])"
)

_MASK = "***REDACTED***"
_KEY_RE = re.compile(KEY_PATTERN)
_AZURE_KEY_RE = re.compile(AZURE_KEY_PATTERN)
_AZURE_HEX_KEY_RE = re.compile(AZURE_HEX_KEY_PATTERN)


def redact_keys(text: str) -> str:
    """``text`` with every key-shaped run replaced by ``***REDACTED***``.

    The 32-hex rule keeps the word before the key (``api-key: ***REDACTED***``),
    so the line still says which field held it.
    """
    if not text:
        return text
    masked = _KEY_RE.sub(_MASK, text)
    masked = _AZURE_KEY_RE.sub(_MASK, masked)
    return _AZURE_HEX_KEY_RE.sub(r"\1" + _MASK, masked)
