"""Is this URL safe to put in an ``href`` we hand a researcher?

**The threat.** URLs reach the report from config the maintainer does not
necessarily write -- today the nine codebook YAMLs in
``bristlenose/server/codebook/``, and in future any community-submitted codebook
(the public-library item in the 100-day inventory).  A string from that file is
rendered as a clickable link inside the researcher's app.  ``html.escape`` does
**not** help: it neutralises markup, and ``javascript:alert(1)`` contains none.

**The rule, and it is not ours.** Allowlist the scheme, never denylist it --
OWASP's standing guidance, and the reason is that a denylist has to be complete
forever while an allowlist only has to be right once.  We permit ``http``,
``https`` and ``mailto``.

**The parsing is the platform's; only the policy is ours.** ``urlparse`` handles
the grammar, the whitespace stripping and the case folding that hand-rolled
checks get wrong (``JaVaScRiPt:``, ``java\\tscript:``, a leading NUL).  Writing
our own parser would be inventing the hard half.

**Why no library.** ``bleach`` -- the obvious Python answer -- was deprecated in
2023.  DOMPurify is the JS standard but sanitises *HTML*, at ~20 KB, for a check
that is one function.  Both would be a dependency carrying far more surface than
the twenty lines it replaces.  The borrowed part is the rule; the code is small
on purpose.

**Three implementations, one contract.** Swift already does this in
``WebView.swift::openExternal`` (http/https/mailto, guarding ``NSWorkspace``
against ``file://`` app-launches), and Python already did it locally in
``server/miro_export.py::_clip_url``.  This module is the shared Python half;
``frontend/src/utils/safeUrl.ts`` is the TypeScript half; and
``tests/fixtures/safe-url-contract.json`` pins them to the same answers.  See
``docs/design-shared-formats.md`` for why a format with three implementations
gets a fixture rather than trust.
"""

from __future__ import annotations

from urllib.parse import urlparse

#: Schemes we will render as a link. Anything else is dropped, not escaped.
#:
#: ``mailto`` is included because Swift's ``openExternal`` already allows it and
#: the two must agree; no shipped surface emits one yet.
ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https", "mailto"})

#: Characters a browser strips *before* resolving a scheme, so a check that does
#: not strip them first can be walked straight past: ``java\tscript:alert(1)``
#: is ``javascript:alert(1)`` to the parser. Matches the WHATWG URL spec's
#: leading/trailing C0-control-and-space removal, plus tab/CR/LF anywhere.
_STRIPPED = "".join(chr(c) for c in range(0x21)) + "\x7f"


def _normalise(raw: str) -> str:
    """Strip what a browser strips, before anyone looks at the scheme."""
    return raw.strip(_STRIPPED).replace("\t", "").replace("\n", "").replace("\r", "")


#: Tighter set for URLs that arrive in *config we did not write* -- the codebook
#: YAML today, community submissions later. All 22 shipped author links are
#: already https, and plain http in a submitted codebook is a downgrade with no
#: benefit: these point at books and websites, not at anything that needs it.
#:
#: Deliberately narrower than ``ALLOWED_SCHEMES``. That set answers "may this be
#: an href at all", which is the right question for a URL the *researcher*
#: reached; this one answers "may a stranger put this in our corpus", which is
#: not the same question and should not inherit the same answer.
CONFIG_SCHEMES: frozenset[str] = frozenset({"https"})


def is_safe_url(raw: str | None, allowed: frozenset[str] | None = None) -> bool:
    """True when ``raw`` may be rendered as an ``href``.

    Requires a netloc for http(s): a scheme with no host is not a destination,
    and ``http:///`` or ``https:evil`` are not links a researcher meant to
    follow. ``mailto`` has no netloc by design, so it is checked on its path.

    ``allowed`` narrows the scheme set -- pass :data:`CONFIG_SCHEMES` for values
    that came from a file we did not write.
    """
    if not raw or not isinstance(raw, str):
        return False
    candidate = _normalise(raw)
    if not candidate:
        return False
    try:
        parsed = urlparse(candidate)
    except ValueError:
        # urlparse raises on some malformed IPv6 literals. A URL we cannot parse
        # is a URL we will not render.
        return False
    scheme = parsed.scheme.lower()
    if scheme not in (ALLOWED_SCHEMES if allowed is None else allowed):
        return False
    if scheme == "mailto":
        return bool(parsed.path.strip())
    return bool(parsed.netloc)


def safe_url_or_none(
    raw: str | None, allowed: frozenset[str] | None = None
) -> str | None:
    """The normalised URL when it is safe, else ``None``.

    Returns the *normalised* form rather than the input: if the value was safe
    only because we stripped a tab out of it, the caller must render the
    stripped version, not the original.
    """
    if not is_safe_url(raw, allowed):
        return None
    assert raw is not None
    return _normalise(raw)
