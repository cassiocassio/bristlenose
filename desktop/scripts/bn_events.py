"""bn_events — the one parser for the `@bn` report protocol.

Read by two consumers: `build_report.py` (the live renderer, which imports
Rich) and `scripts/release-board.py` (the board, stdlib only). It lives in its
own module so the board can import it without Rich, and so a quoting change in
`report.sh`/`sink.sh` has exactly one reader to keep in step with.

A sink file (`.release/<v>/bn-events.log`, written by `sink.sh`) holds the
same lines as the live stream plus `ts=` and `run=`; `parse_stream` reads it
and COUNTS what it could not parse, because a line silently dropped is the
board reporting "no data" over a fact that was written (measured 5 Sep 2026:
`printf %q` + `shlex.split` on a value with a newline and an apostrophe).

stdlib only. No imports beyond shlex.
"""

from __future__ import annotations

import re
import shlex

PROTOCOL_VERSION = 1

# `printf %q` renders control bytes — and, under a C locale, every non-ASCII
# byte — in ANSI-C quoting: $'notarised \342\200\224 stapled'. shlex does not
# speak it: it strips the quotes and leaves `$notarised \342\200\224 stapled`,
# a plausible-looking wrong value, or raises on an escaped apostrophe and the
# whole line vanished (measured 5 Sep 2026). sink.sh normalises control bytes
# before quoting, but the locale case is the writer's environment, not its
# choice — so the ONE parser decodes the form itself, before shlex sees it.
# (?<!\\): printf %q renders a literal $ as \$, so a value `cost $'5'` arrives as
# `cost\ \$'5'` — that is data, not quoting, and must not be decoded.
_ANSI_C = re.compile(r"(?<!\\)\$'((?:[^'\\]|\\.)*)'")
_ESC = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", "'": "'", '"': '"', "a": "\a", "b": "\b", "f": "\f", "v": "\v", "e": "\x1b", "E": "\x1b"}


def _decode_ansi_c(body: str) -> str:
    """Byte-level: bash 3.2 under a UTF-8 locale writes a multibyte character as
    its lead byte RAW plus the continuation bytes as octal (`\xe2\200\224` for an
    em dash). The raw byte survives the file read only if the reader used
    surrogateescape — see parse_stream — and is re-encoded here the same way, so
    the sequence reassembles before the single UTF-8 decode at the end."""
    out = bytearray()
    i = 0
    while i < len(body):
        c = body[i]
        if c != "\\" or i + 1 >= len(body):
            out += c.encode("utf-8", errors="surrogateescape")
            i += 1
            continue
        n = body[i + 1]
        if n in "01234567":
            j = i + 1
            while j < len(body) and j < i + 4 and body[j] in "01234567":
                j += 1
            out.append(int(body[i + 1:j], 8) & 0xFF)
            i = j
            continue
        if n == "x":
            j = i + 2
            while j < len(body) and j < i + 4 and body[j] in "0123456789abcdefABCDEF":
                j += 1
            if j > i + 2:
                out.append(int(body[i + 2:j], 16))
                i = j
                continue
        out += _ESC.get(n, "\\" + n).encode("utf-8", errors="surrogateescape")
        i += 2
    return out.decode("utf-8", errors="replace")


def _unquote_ansi_c(line: str) -> str:
    return _ANSI_C.sub(lambda m: shlex.quote(_decode_ansi_c(m.group(1))), line)


def parse_event(line: str) -> tuple[str, dict[str, str]] | None:
    """`@bn <kind> k=v k="v w/ spaces" …` → (kind, fields). None if not an event."""
    if not line.startswith("@bn "):
        return None
    try:
        toks = shlex.split(_unquote_ansi_c(line[4:].strip()))
    except ValueError:
        return None
    if not toks:
        return None
    kind, rest = toks[0], toks[1:]
    fields: dict[str, str] = {}
    for tok in rest:
        if "=" in tok:
            k, _, v = tok.partition("=")
            fields[k] = v
    return kind, fields


def read_sink_text(path) -> str:
    """Read a sink file for parse_stream: bytes, decoded with surrogateescape so an
    invalid byte (bash 3.2's raw lead byte) reaches the ANSI-C decoder intact
    instead of becoming U+FFFD on the way in."""
    with open(path, "rb") as fh:
        return fh.read().decode("utf-8", errors="surrogateescape")


def parse_stream(text: str) -> tuple[list[tuple[int, str, dict[str, str]]], list[tuple[int, str]], bool]:
    """Parse a whole sink file (text from read_sink_text, or any str).

    Returns (events, unparsed, partial):
      events   — [(line_no, kind, fields)] for every complete `@bn` line that parsed
      unparsed — [(line_no, raw)] for every `@bn`-prefixed complete line that did not
      partial  — True when the final line has no trailing newline (a write in
                 progress); that line is excluded from both lists rather than
                 read as a truncated event.
    Non-`@bn` lines (there should be none in a sink) are ignored, not counted.
    """
    events: list[tuple[int, str, dict[str, str]]] = []
    unparsed: list[tuple[int, str]] = []
    partial = bool(text) and not text.endswith("\n")
    lines = text.split("\n")
    if partial:
        lines = lines[:-1]
    elif lines and lines[-1] == "":
        lines = lines[:-1]
    for no, raw in enumerate(lines, 1):
        if not raw.startswith("@bn "):
            continue
        parsed = parse_event(raw)
        if parsed is None:
            unparsed.append((no, raw))
            continue
        kind, fields = parsed
        fields = {k: v.encode("utf-8", errors="surrogateescape").decode("utf-8", errors="replace") for k, v in fields.items()}
        events.append((no, kind, fields))
    return events, unparsed, partial
