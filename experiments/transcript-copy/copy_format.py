"""What a drag-select copy of transcript paragraphs should put on the clipboard.

Two flavours, written together:
  text/plain — Markdown in the house transcript format (`**[mm:ss] p1** text`)
  text/html  — the same structure, for Word / Pages / Google Docs

The question this answers: transcript text is speech, and speech contains
characters Markdown reads as syntax (`*`, `_`, backticks, `[x](y)`, `<b>`,
`&copy;`, `~~`). Escape them all, and every paste into a plain editor is
littered with backslashes. Escape none, and a paste into iA Writer renders
italics, links and HTML the participant never said.

So: escape ONLY what would actually change the rendering, then prove it by
rendering the result with a real CommonMark parser and comparing the visible
text against the words. Every case below is synthetic — no participant text.

    .venv/bin/python experiments/transcript-copy/copy_format.py

Shipped 8 Oct 2026 as `escape_markdown_speech` (bristlenose/utils/markdown.py)
and `escapeMarkdownSpeech` (frontend/src/utils/transcriptCopy.ts). Those, not this
file, are the rule: review tightened `~` to escape every tilde (GitHub and Slack
strike through on one), and the speaker label is escaped in the export too.
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

from markdown_it import MarkdownIt

OUT = Path(__file__).parent / "out"

# (timecode, code, text). A selection that starts or ends mid-paragraph keeps
# only the selected words; that is modelled by the first and last rows.
CASES: list[tuple[str, str, str]] = [
    ("00:42", "p1", "price was the thing, # of people who asked was maybe five"),
    ("00:49", "m1", "- like, which one? 1. the price 2. the colour > the size"),
    ("01:03", "p1", "the file was called snake_case_name and it cost 2*3*4 pounds, *really*"),
    ("01:15", "p1", "[laughs] I typed [the brand](which one?) into the box, then ![image] and [1]"),
    ("01:31", "m1", "it said <b>error</b> and <https://example.com> &copy; AT&T &amp; co"),
    ("01:40", "p1", r"saved it to C:\Users\me\Desktop\*final* and typed \n by mistake"),
    ("01:52", "p1", "use `npm` ~~not~~ yarn | a pipe | here, __bold__ claim, 50% off_peak"),
    ("02:05", "p2", "我觉得这个*价格*有点贵。それは「_いい_」ですね 👍🏽 — honestly…"),
    ("02:20", "m1", "ok... so    three spaces, a trailing backslash \\"),
]

# CommonMark's ASCII punctuation set: a backslash escapes exactly these.
_PUNCT = set("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")


def escape_minimal(text: str) -> str:
    """Escape only the characters that would change how the text renders.

    The text never starts a line (the bold prefix comes first), so block
    syntax — `#`, `-`, `>`, `1.` — is inert and left alone.
    """
    out: list[str] = []
    n = len(text)
    for i, ch in enumerate(text):
        prev = text[i - 1] if i else " "
        nxt = text[i + 1] if i + 1 < n else " "
        esc = False
        if ch == "\\":
            # A backslash is only an escape before punctuation (or a hard
            # break at end of line).
            esc = nxt in _PUNCT or i == n - 1
        elif ch in "*`":
            esc = True
        elif ch == "_":
            # Intraword underscores never emphasise in CommonMark.
            esc = not (prev.isalnum() and nxt.isalnum())
        elif ch == "~":
            esc = nxt == "~" or prev == "~"  # GFM strikethrough
        elif ch == "[":
            esc = False  # inert unless a "](" follows, and that "]" is escaped
        elif ch == "]":
            esc = nxt == "("  # a link destination; no copy carries a definition
        elif ch == "<":
            esc = bool(re.match(r"[A-Za-z/!?]", nxt))  # tag or autolink
        elif ch == "&":
            esc = bool(re.match(r"&(#\d+|#x[0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);", text[i:]))
        out.append("\\" + ch if esc else ch)
    return "".join(out)


def escape_everything(text: str) -> str:
    """The safe-but-ugly alternative: backslash every ASCII punctuation mark."""
    return "".join("\\" + c if c in _PUNCT else c for c in text)


def as_markdown(rows, escape, mono=False) -> str:
    # mono: the timecode as a code span, so a renderer sets it in monospace.
    stamp = "`[{tc}]`" if mono else "[{tc}]"
    return "\n\n".join(
        f"**{stamp.format(tc=tc)} {code}** {escape(text)}" for tc, code, text in rows
    ) + "\n"


def as_html(rows) -> str:
    paras = "".join(
        f'<p><b><span style="font-family:Menlo,Consolas,monospace">[{tc}]</span> {code}</b> '
        f"{html.escape(text, quote=False)}</p>"
        for tc, code, text in rows
    )
    return f'<meta charset="utf-8">{paras}'


def visible_text(md_source: str) -> list[str]:
    """Render with CommonMark (+ strikethrough, as iA Writer does) and strip tags."""
    md = MarkdownIt("commonmark").enable("strikethrough")
    rendered = md.render(md_source)
    paras = re.findall(r"<p>(.*?)</p>", rendered, flags=re.S)
    return [html.unescape(re.sub(r"<[^>]+>", "", p)) for p in paras], rendered


def main() -> int:
    OUT.mkdir(exist_ok=True)
    failures = 0
    for name, esc in (("minimal", escape_minimal), ("everything", escape_everything),
                      ("none", lambda s: s)):
        src = as_markdown(CASES, esc)
        texts, rendered = visible_text(src)
        want = [f"[{tc}] {code} {text}" for tc, code, text in CASES]
        bad = [(w, g) for w, g in zip(want, texts) if w != g]
        extra_tags = sorted(set(re.findall(r"<(em|strong|a|code|s|del|img|b)\b", rendered)) - {"strong"})
        slashes = src.count("\\")
        (OUT / f"copy-{name}.md").write_text(src)
        print(f"{name:>10}: {len(want) - len(bad)}/{len(want)} paragraphs read back as spoken; "
              f"{slashes} backslashes; stray markup: {extra_tags or 'none'}")
        for w, g in bad:
            print(f"            said: {w}\n            read: {g}")
        if name == "minimal":
            failures = len(bad) + len(extra_tags)
    mono = as_markdown(CASES, escape_minimal, mono=True)
    texts, rendered = visible_text(mono)
    ok = texts == [f"[{tc}] {code} {text}" for tc, code, text in CASES]
    print(f"      mono: {'9/9' if ok else 'FAIL'}; timecodes in <code>: {rendered.count('<code>')}")
    (OUT / "copy-minimal-mono.md").write_text(mono)
    (OUT / "copy.html").write_text(as_html(CASES))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
