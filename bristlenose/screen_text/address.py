"""Addresses on a shared screen: read for screen keys, and kept at rest only as much as they need.

``url_norm`` reads an address bar's text as host, path and fragment; ``screens.py`` keys screens on
it. ``minimise`` is what the index stores instead of the line as read (``docs/design-screens.md``
§4.3): every address in a line loses its query string, and its fragment unless the fragment is a
single-page app's route, which is kept with its identifiers masked. Pure functions; no I/O.
"""

from __future__ import annotations

import re

HOST = re.compile(r"((?:[a-z0-9-]+\.)+(?:com|co\.uk|de|org|net|io|app|uk|eu|fr|es|it|nl|se|dk|no|fi|pl|cz|jp|kr|br|pt|ca|au|gov|edu)(?:/[^\s]*)?)", re.I)


def url_norm(text: str) -> dict[str, str] | None:
    """An address bar's text as host, path and fragment; None when it is not an address."""
    t = re.sub(r"^[^a-z0-9]+", "", text.strip().lower())
    t = re.sub(r"^https?://", "", t).rstrip("|/ ") + "/"
    t = re.sub(r"^(?:[^\s]{1,2}\s+)", "", t) if " " in t else t
    if " " in t.strip():
        return None
    m = HOST.search(t)
    if not m or m.start() > 0:
        return None
    u = re.sub(r"^www\.", "", m.group(1).lower())
    path, _, frag = u.partition("#")
    path = path.partition("?")[0]
    host, _, p = path.partition("/")
    return {"host": host, "path": "/" + p.rstrip("/"), "frag": re.sub(r"\d{4,}", "#", frag.split("?")[0].rstrip("/"))}


# Any address, not only the ones ``url_norm`` keys on: wider than ``HOST`` (any top-level domain,
# a scheme, a port), because what is dropped here is dropped for privacy, wherever it was read —
# the address bar, or a link shown on the page.
_ADDRESS = re.compile(
    r"(?P<base>(?:[a-z][a-z0-9+.-]*://)?"
    # a dotted host; or the hosts of internal tools and staging, which UX research often runs
    # against: localhost, an IPv4 address, a single-label host with a scheme or a port
    r"(?:(?:[a-z0-9-]+\.)+[a-z]{2,}|localhost|\d{1,3}(?:\.\d{1,3}){3}"
    r"|(?<=://)[a-z0-9-]+|[a-z0-9-]+(?=:\d))"
    r"(?::\d+)?(?:/[^\s?#]*)?)"
    r"(?P<query>\?[^\s#]*)?(?P<frag>#\S*)?", re.I)
# What the address rule cannot recognise as a host (``intranet/hr/case?employee=jane``) still loses
# its query: any word with a slash before a question mark is treated as an address.
_SLASHED_QUERY = re.compile(r"(?P<path>[^\s?#]*/[^\s?#]*)\?[^\s#]+")
# A single-page app's route: ``#/`` (or ``#!/``) and path-like segments, nothing else. ``#/planner``
# and ``#/summary`` are how such an app's screens are told apart, where the path stays one for the
# whole session (``docs/design-screens-lens.md`` §4.1: the German planner was one path for 13
# minutes). Anything else after ``#`` — an in-page anchor, an OAuth ``#access_token=…`` — is not
# a route and is never kept; a route's own query is dropped (``#/reset?token=…`` keeps ``#/reset``).
# No ``%``: a percent-encoded value in a route is data, not a path (``#/invite/jane%40example.com``
# is an email address), and a route carrying one is not kept.
_ROUTE = re.compile(r"^#!?/[A-Za-z0-9._~/-]*$")
_TOKEN = re.compile(r"[A-Za-z0-9_-]{16,}")
#: What an identifier in a kept route becomes: the mark ``url_norm`` already puts on digit runs,
#: so a masked route keys the same screen it did before it was masked.
MASK = "#"


def _opaque(token: str) -> bool:
    """A long token that is an identifier, not a word: it carries a digit or mixed case. A route
    named in words (``account-settings-overview``) is lower case with no digits, and is kept."""
    return any(c.isdigit() for c in token) or (token.lower() != token and token.upper() != token)


def _route(frag: str) -> str:
    """The fragment to keep: an SPA route with its identifiers masked, else nothing."""
    route = frag.split("?", 1)[0]
    if not _ROUTE.match(route):
        return ""
    route = _TOKEN.sub(lambda m: MASK if _opaque(m.group()) else m.group(), route)
    return re.sub(r"\d{4,}", MASK, route)


def minimise(text: str) -> str:
    """*text* with each address's query string dropped, and its fragment dropped unless it is a
    route (kept, identifiers masked). Text with no address carrying either is returned as is."""
    def one(m: re.Match[str]) -> str:
        query, frag = m.group("query") or "", m.group("frag") or ""
        if len(query) <= 1 and len(frag) <= 1:
            return m.group(0)
        return m.group("base") + _route(frag)
    return _SLASHED_QUERY.sub(lambda m: m.group("path"), _ADDRESS.sub(one, text))
