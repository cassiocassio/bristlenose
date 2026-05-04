"""Boundary helper for wrapping untrusted user content in LLM prompts.

Bristlenose feeds participant transcript text into LLM prompts at several
stages. A participant who knows their words will be analysed by an LLM
could craft an utterance designed to override the system prompt or distort
the structured output. To bound that risk we wrap untrusted input in a
sentinel-tag envelope with a per-call random nonce, and escape any
closing-tag-shaped substrings inside the content as defence-in-depth.

The envelope looks like:

    <untrusted_transcript_a8f3>
    ...content with </untrusted_*> sequences neutralised...
    </untrusted_transcript_a8f3>

A unit test in ``tests/test_prompt_boundary.py`` enforces that every render
call site for an untrusted variable routes through ``wrap_untrusted()``.

See ``docs/design-prompt-injection-defence.md`` for the threat model and
why this is M1 (Phase A) rather than something heavier.
"""

from __future__ import annotations

import re
import secrets

# Match any closing-tag-shaped substring that targets our envelope. We don't
# care about valid markup — we care about anything a model might tokenise as
# a closing tag for our sentinel. The trailing ``[^>]*>`` swallows the rest
# of the would-be tag. Case-insensitive as belt-and-braces: today every
# caller passes a lowercase ``name`` (and ``wrap_untrusted`` lower-cases it
# below) so the IGNORECASE flag has no observable effect, but a future
# mixed-case caller cannot silently break the escape.
_CLOSING_TAG_RE = re.compile(r"</untrusted_[A-Za-z0-9_]*[^>]*>", re.IGNORECASE)


def _make_nonce() -> str:
    """Return a 4-hex-char random nonce. ~16 bits of entropy per call.

    Cryptographic strength is not the goal — the nonce only needs to be
    unguessable at prompt-construction time so a participant cannot embed
    the matching closing tag verbatim. ``secrets`` rather than ``random``
    so the choice is not predictable from prior calls.
    """
    return secrets.token_hex(2)


def _escape_closing_tags(content: str) -> str:
    """Neutralise any ``</untrusted_*>`` substrings in the content.

    Replaces ``</`` with ``<\\/`` so the tokeniser sees text rather than a
    closing tag. Belt-and-braces alongside the per-call nonce — even if a
    model ever echoes the nonce, the escape stops a verbatim-quoted closing
    tag from breaking the envelope.
    """
    return _CLOSING_TAG_RE.sub(lambda m: m.group(0).replace("</", "<\\/", 1), content)


def wrap_untrusted(name: str, content: str) -> str:
    """Wrap ``content`` in an ``<untrusted_{name}_{nonce}>`` envelope.

    Args:
        name: Short identifier for the boundary (e.g. ``"transcript"``,
            ``"quotes"``, ``"signals"``). Letters and underscores only;
            keep it short and human-meaningful.
        content: Untrusted text to wrap. Closing-tag-shaped substrings are
            escaped before wrapping.

    Returns:
        The wrapped block, ready to be substituted into a prompt template
        via ``str.format()``.

    Raises:
        ValueError: If ``name`` is empty or contains characters outside
            ``[A-Za-z_]``.
    """
    if not name or not re.fullmatch(r"[A-Za-z_]+", name):
        raise ValueError(
            f"wrap_untrusted name must be non-empty letters/underscores only, got {name!r}"
        )
    name = name.lower()
    nonce = _make_nonce()
    escaped = _escape_closing_tags(content)
    return f"<untrusted_{name}_{nonce}>\n{escaped}\n</untrusted_{name}_{nonce}>"
