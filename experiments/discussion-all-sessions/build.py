"""Build docs/mockups/discussion-all-sessions.html — Discussion lens, option A.

Option A: the session bar gains an "All" choice in front of the sessions. All is
the by-question view: each normalised question once, then one block per session
that asked it (the unit is the SESSION; a group session's block holds several
participants' quotes). Picking a session is today's view.

Iteration 2 (18 Oct 2026): the navigator's session chips are replaced by a
MEASURE that grows with the guide's width — bar + count (the tags sidebar's) →
a strip of one cell per session → a grid with session column headers. And a
compact number-only badge, shared with the Signals participant chips, in four
states: present, absent, selected, and All selected (two variants).

Every frame is drawn from the tables below with the lens's own markup
(DiscussionLens.tsx), and styled by the shipped theme (load_default_css(), the
same concatenation serve and export use) plus discussion.css verbatim. What is
proposed is in ONE separate <style> block, every rule commented "PROPOSED".

    .venv/bin/python experiments/discussion-all-sessions/build.py
"""

from __future__ import annotations

import html
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bristlenose.stages.s12_render.theme_assets import load_default_css  # noqa: E402

DISCUSSION_CSS = ROOT / "frontend/src/islands/discussion/discussion.css"
OUT = ROOT / "docs/mockups/discussion-all-sessions.html"

e = html.escape


# ── the cast ──────────────────────────────────────────────────────────────────


@dataclass
class P:
    code: str
    name: str = ""


@dataclass
class Sess:
    n: int
    people: list[P]
    duration: str = "18:12"
    mod: str = "m1"
    study: str = "12"


def names_of(s: Sess) -> str:
    """capNames (model.ts) with the en strings: two names joined, else "X and N others"."""
    names = [p.name for p in s.people if p.name]
    if len(names) <= 2:
        return " and ".join(names)
    rest = len(names) - 1
    return f"{names[0]} and {rest} other{'s' if rest != 1 else ''}"


THREE = [
    Sess(1, [P("p1", "Simon")], "18:12", study="3"),
    Sess(2, [P("p2", "Sarah")], "41:05", study="3"),
    Sess(3, [P("p3", "Bettina")], "31:40", study="3"),
]

TWELVE = [
    Sess(1, [P("p1", "Simon")], "18:12"),
    Sess(2, [P("p2", "Sarah"), P("p3", "Mike")], "41:05"),
    Sess(3, [P("p4", "Bettina"), P("p5", "Kwame"), P("p6", "Ana"), P("p7", "Joe"), P("p8", "Priya")],
         "58:20", "m2"),
    Sess(4, [P("p9")], "22:47"),
    Sess(5, [P("p10", "Maria-Fernanda Albuquerque-Santos")], "35:02"),
    Sess(6, [P("p11", "Tom")], "27:15", "m2"),
    Sess(7, [P("p12"), P("p13")], "44:30"),
    Sess(8, [P("p14", "Yui")], "29:58"),
    Sess(9, [P("p15", "Dev"), P("p16", "Ola")], "39:11", "m2"),
    Sess(10, [P("p17", "Hannah")], "24:06"),
    Sess(11, [P("p18")], "31:44"),
    Sess(12, [P("p19", "Grace")], "26:39"),
]

# An anonymised export: the same twelve, every name blanked.
ANON = [Sess(s.n, [P(p.code) for p in s.people], s.duration, s.mod) for s in TWELVE]

# The typical study: eight sessions (the first eight of the twelve).
EIGHT = TWELVE[:8]

# A large study: thirty one-to-ones, codes only.
THIRTY = [Sess(i, [P(f"p{i}")], "30:00", study="30") for i in range(1, 31)]


# ── the guide (normalised questions) ─────────────────────────────────────────


@dataclass
class Item:
    id: str
    text: str
    mark: str  # dot | hollow | plus
    asked3: list[int] = field(default_factory=list)
    asked12: list[int] = field(default_factory=list)


# Twelve: #7 reached the first two sections and never the third (ran out of
# time), so its column empties at the foot of the grid.
SECTIONS: list[tuple[str, list[Item]]] = [
    ("tell me about one of your favourite object", [
        Item("fav", "Favourite object", "dot", [1, 2, 3], [1, 2, 3, 5, 6, 7, 8, 9, 10, 12]),
        Item("house", "Household object", "dot", [2], [2, 3, 6, 7, 9]),
        Item("room", "Room location", "hollow"),
        Item("tech", "Steer away from tech", "plus", [1], [1, 5, 7, 10]),
        Item("like", "What do you like about it?", "plus", [1, 3], [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12]),
    ]),
    ("can you tell me a trip to ikea?", [
        Item("trip", "IKEA trip memory", "dot", [1, 2, 3], list(range(1, 13))),
        Item("walk", "Walk through visit sequence", "plus", [2], [2, 3, 7, 9, 11]),
        Item("feel", "How did that feel?", "plus", [3], [3, 6, 7, 12]),
    ]),
    ("let's go to ikea.com", [
        Item("first", "First impressions", "dot", [1, 2, 3], [1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12]),
        Item("replace", "Replace at ikea.com", "dot", [1, 3], [1, 3, 5, 8, 12]),
    ]),
]


def asked(it: Item, sessions: list[Sess]) -> list[int]:
    if it.mark == "hollow":
        return []
    study = sessions[0].study
    if study == "3":
        return it.asked3
    if study == "12":
        present = {s.n for s in sessions}
        return [n for n in it.asked12 if n in present]
    return [s.n for s in sessions if (s.n * 13 + len(it.id) * 7) % 5 != 0]


# ── what was said: (study, session, item) → [ask, answers…] ──────────────────

SAID: dict[tuple[str, int, str], list[tuple[str, str, list[tuple[str, str, str]]]]] = {
    ("12", 1, "fav"): [("00:28", "Okay. Tell me about one of your favourite objects, a household object, an "
                        "object in your house. Something kind of everyday, but that you love.", [
        ("00:55", "p1", "… let’s say I’ve got a… a Ninja Foodie? It’s… one of these all-in-one… "
                        "pressure cookers, air fryers type thing. Is that the right thing?"),
        ("01:32", "p1", "… I’ve got… one of those old style crock pots that you use for fermentation. "
                        "… it’s good because it’s… a practical thing. But it’s designed to… be emotive, I guess."),
    ])],
    ("12", 2, "fav"): [("01:10", "So to start, could you tell me about an object at home that you really love?", [
        ("01:31", "p2", "Honestly? The kitchen table. We’ve had it since our first flat and it’s been "
                        "painted three times."),
        ("02:02", "p3", "I was going to say the record player, but yeah, the table. Everything happens there."),
    ])],
    ("12", 3, "fav"): [("02:40", "Let’s go round the room. One object at home you love, and why.", [
        ("02:58", "p4", "My grandmother’s sewing box. It doesn’t really work any more but it sits on the shelf."),
        ("03:20", "p5", "A lamp. A really basic paper lamp. It makes the evening feel different."),
        ("03:41", "p7", "Mine is boring — my desk chair. I sit in it ten hours a day."),
        ("04:05", "p8", "The bread bin! I know. It was a wedding present and it’s the only thing that matches."),
    ])],
    ("12", 5, "fav"): [("00:44", "Tell me about one of your favourite objects at home.", [
        ("01:15", "p10", "There’s a ceramic bowl I bought in Lisbon. I use it for keys, so I touch it every day."),
    ])],
    ("12", 6, "fav"): [("01:02", "What’s one object at home you couldn’t do without?", [])],
    ("12", 8, "fav"): [("00:39", "Could you tell me about a favourite object in your home?", [
        ("00:58", "p14", "My rice cooker. It plays a little song when it’s done."),
    ])],
    ("12", 9, "fav"): [("01:20", "One object each, at home, that you love.", [
        ("01:40", "p15", "Bike. Does a bike count? It lives in the hall."),
        ("01:52", "p16", "Then mine is the hook the bike hangs on, because it’s finally out of the way."),
    ])],
    ("12", 10, "fav"): [("00:51", "Tell me about an everyday object you really like.", [
        ("01:13", "p17", "A big wooden chopping board. It’s scarred all over and I love that."),
    ])],
    ("12", 12, "fav"): [("00:35", "Tell me about one of your favourite objects, something everyday.", [
        ("00:57", "p19", "The blanket on the sofa. Everyone fights over it."),
    ])],
}
SAID[("3", 1, "fav")] = SAID[("12", 1, "fav")]
SAID[("3", 2, "fav")] = [("01:10", SAID[("12", 2, "fav")][0][1], SAID[("12", 2, "fav")][0][2][:1])]
SAID[("3", 3, "fav")] = [("02:40", "Tell me about one object at home you love, and why.", [
    ("02:58", "p3", "My grandmother’s sewing box. It doesn’t really work any more but it sits on the shelf."),
    ("03:30", "p3", "It’s the one thing I’d grab. Everything else from IKEA I could replace tomorrow."),
])]

FALLBACK = [
    "Yeah, I suppose it’s the way it fits into the day without me noticing it.",
    "It was cheap, which I liked, but it’s lasted longer than anything expensive I own.",
    "I don’t think about it at all, which is probably the compliment.",
    "We moved it from the old place. It’s the first thing I unpacked.",
    "My partner hates it. I keep it anyway.",
    "It’s the one thing people ask about when they come round.",
    "Going there is a day out. You don’t go to IKEA for one thing.",
]


def said(s: Sess, item: str):
    if (s.study, s.n, item) in SAID:
        return SAID[(s.study, s.n, item)]
    h = (s.n * 31 + sum(map(ord, item))) % 7
    q = [1, 1, 2, 2, 3, 4, 6][h]
    k = len(s.people)
    ppl = min(q, k, 1 + h % k)
    answers = []
    for i in range(q):
        secs = 330 + i * 41
        answers.append((f"{secs // 60:02d}:{secs % 60:02d}", s.people[i % ppl].code,
                        FALLBACK[(h + i) % len(FALLBACK)]))
    return [("05:12", "And what about that one — tell me a bit more?", answers)]


def yield_of(s: Sess, item: str) -> tuple[int, int]:
    """(quotes, people who said something quoted) for one session on one item."""
    q, who = 0, set()
    for _t, _w, answers in said(s, item):
        q += len(answers)
        who.update(code or s.people[0].code for _qt, code, _x in answers)
    return q, len(who)


# ── markup: the lens's own (DiscussionLens.tsx) ──────────────────────────────


def badge(code: str, name: str = "", extra: str = "") -> str:
    nm = f'<span class="bn-speaker-badge-name">{e(name)}</span>' if name else ""
    return (f'<span class="bn-person-badge{extra}"><span class="bn-speaker-badge--split">'
            f'<span class="bn-speaker-badge-code">{e(code)}</span>{nm}</span></span>')


def cbadge(code: str, state: str = "present") -> str:
    """PROPOSED compact number-only badge. state: present | absent | here."""
    extra = " bn-person-badge-compact" + (" bn-person-badge-absent" if state == "absent" else "")
    b = badge(code, "", extra)
    return f'<span class="bn-person-badge-here">{b}</span>' if state == "here" else b


def here(inner: str, on: bool) -> str:
    return f'<span class="bn-person-badge-here">{inner}</span>' if on else f"<span>{inner}</span>"


def sess_btn(code: str, name: str, on: bool, title: str = "") -> str:
    t = f' title="{e(title)}"' if title else ""
    return (f'<button type="button" role="radio" aria-checked="{str(on).lower()}" class="dl-sess"{t}>'
            f"{here(badge(code, name), on)}</button>")


def session_bar(sessions: list[Sess], current: int | None, tier: str = "names") -> str:
    """tier: names | codes (selected keeps its name) | pick (All + a pull-down)."""
    out = []
    if len(sessions) > 1:
        # PROPOSED: All, in front, then a keyline (dl-sep) — All is a different kind of choice.
        out.append(sess_btn("All", "", current is None, "All sessions"))
        out.append('<span class="dl-sep" aria-hidden="true"></span>')
    if tier == "pick":
        shown = next((s for s in sessions if s.n == current), None)
        label = f"#{shown.n} ▾" if shown else "Sessions ▾"
        name = names_of(shown) if shown else ""
        out.append(f'<span class="dl-sess dl-bar-pick">{here(badge(label, name), shown is not None)}'
                   f'<select aria-label="Sessions"><option>{e(label)}</option></select></span>')
    else:
        for s in sessions:
            on = s.n == current
            nm = names_of(s)
            show = nm if (tier == "names" or on) else ""
            title = f"Session {s.n}: {nm}" if nm else f"Session {s.n}"
            out.append(sess_btn(f"#{s.n}", show, on, title))
    nav = ('<span class="dimension-toggle" role="radiogroup" aria-label="Show">'
           '<button type="button" role="radio" aria-checked="true" class="dimension-btn active">'
           "Normalised questions</button>"
           '<button type="button" role="radio" aria-checked="false" class="dimension-btn">Your guide</button>'
           "</span>")
    return (f'<div class="dl-bar"><div class="dl-bar-nav">{nav}</div>'
            f'<div class="dl-sessions" role="radiogroup" aria-label="Sessions">{"".join(out)}</div></div>')


def swatch(cls: str) -> str:
    return f'<span class="dl-cell {cls}" aria-hidden="true"></span>'


def key(all_view: bool) -> str:
    grey = "" if all_view else (
        '<div class="bn-pipeline-key-group"><span class="bn-pipeline-key-item dl-key-grey">'
        "Grey: not asked in this session</span></div>")
    # PROPOSED: the measure's three swatches join the key; they show only when cells do.
    cells = ('<div class="bn-pipeline-key-group dl-key-cells">'
             f'<span class="bn-pipeline-key-item">{swatch("off")}Not asked</span>'
             f'<span class="bn-pipeline-key-item">{swatch("s1")}{swatch("s2")}{swatch("s3")}'
             "Less → more, for this study</span>"
             "</div>")
    return ('<div class="bn-pipeline-key dl-key" role="note" aria-label="Key">'
            '<div class="bn-pipeline-key-group">'
            '<span class="bn-pipeline-key-item"><span class="dl-mk"><span class="dl-dot"></span></span>'
            "Asked as planned</span>"
            '<span class="bn-pipeline-key-item"><span class="dl-mk"><span class="dl-dot hollow"></span></span>'
            "Planned, never asked</span>"
            '<span class="bn-pipeline-key-item"><span class="dl-mk">+</span>Not in your guide</span>'
            f"</div>{cells}{grey}</div>")


def cuts(sessions: list[Sess]) -> tuple[int, int]:
    """PROPOSED: the study's thirds. Every asked cell that drew quotes, ranked by its quote
    count; the light/medium/dark steps are the lower, middle and upper third."""
    vals = sorted(q for _t, items in SECTIONS for it in items for s in sessions
                  if s.n in asked(it, sessions) and (q := yield_of(s, it.id)[0]) > 0)
    if not vals:
        return (0, 0)
    n = len(vals)
    return (vals[-(-n // 3) - 1], vals[-(-2 * n // 3) - 1])


def max_quotes(sessions: list[Sess]) -> int:
    best = 1
    for _t, items in SECTIONS:
        for it in items:
            best = max(best, sum(yield_of(s, it.id)[0] for s in sessions if s.n in asked(it, sessions)))
    return best


def bar_pct(q: int, qmax: int) -> int:
    """PROPOSED: a LOGARITHMIC bar — the first quote is the biggest step. 1 of a maximum 10
    fills ~30%, not 10%, so a question that drew one quote never looks like one that drew none."""
    return round(100 * math.log1p(q) / math.log1p(max(qmax, 1))) if q else 0


def measure(it: Item, sessions: list[Sess], current: int | None, qmax: int,
            thirds: tuple[int, int]) -> str:
    """PROPOSED: the row's measure. All three tiers are in the markup; the lens's
    tier class (dl-m-bar | dl-m-strip | dl-m-grid), set by measuring, shows one."""
    sids = asked(it, sessions)
    total_q = sum(yield_of(s, it.id)[0] for s in sessions if s.n in sids)
    cells = []
    for s in sessions:
        cls = ["dl-cell"]
        if s.n not in sids:
            cls.append("off")
            tip = f"#{s.n} · not asked"
        else:
            q, ppl = yield_of(s, it.id)
            cls.append("z" if q == 0 else "s1" if q <= thirds[0] else "s2" if q <= thirds[1] else "s3")
            nm = names_of(s)
            qs = f"{q} quote{'s' if q != 1 else ''}"
            who = f" from {ppl} of {len(s.people)} people" if len(s.people) > 1 else ""
            tip = f"#{s.n}{' ' + nm if nm else ''} · " + (f"{qs}{who}" if q else "asked, no quotes")
        if s.n == current:
            cls.append("here")
        cells.append(f'<button type="button" class="{" ".join(cls)}" title="{e(tip)}"></button>')
    bar = ('<span class="tag-bar-area">'
           + (f'<span class="tag-micro-bar" role="img" style="width:{bar_pct(total_q, qmax)}%;'
              f'background-color:var(--dl-bar)"></span>' if total_q else "")
           + f'<span class="tag-count">{total_q}</span></span>')
    sr = f'<span class="bn-sr-only">, asked in {len(sids)} of {len(sessions)} sessions, {total_q} quotes</span>'
    return f'<span class="dl-measure"><span class="dl-cells">{"".join(cells)}</span>{bar}{sr}</span>'


def nav_row(it: Item, sessions: list[Sess], current: int | None, focus: str | None, qmax: int,
            thirds: tuple[int, int]) -> str:
    sids = asked(it, sessions)
    cls = ["toc-link", "dl-row"]
    if current is not None and current not in sids:
        cls.append("ghost" if sids else "dim")
    if current is None and not sids:
        cls.append("dim")
    if it.mark == "hollow":
        cls.append("unasked")
    if focus == it.id:
        cls.append("active")
    mk = "+" if it.mark == "plus" else f'<span class="dl-dot{" hollow" if it.mark == "hollow" else ""}"></span>'
    body = (f'<button type="button" class="dl-row-btn"><span class="dl-mk">{mk}</span>'
            f'<span class="dl-tx">{e(it.text)}</span></button>')
    return f'<div class="{" ".join(cls)}" data-id="{it.id}">{body}{measure(it, sessions, current, qmax, thirds)}</div>'


def grid_head(sessions: list[Sess], current: int | None, all_lit: bool) -> str:
    """PROPOSED: column heads for the grid tier — compact badges, sticky under the bar."""
    heads = []
    for s in sessions:
        if current is None:
            state = "here" if all_lit else "present"
        else:
            state = "here" if s.n == current else "present"
        b = (f'<span class="bn-person-badge bn-person-badge-compact"><span class="bn-speaker-badge--split">'
             f'<span class="bn-speaker-badge-code{" dl-h-wide" if s.n >= 10 else ""}">'
             f'<span class="dl-h-n"><span class="dl-h-hash">#</span>{s.n}</span></span></span></span>')
        if state == "here":
            b = f'<span class="bn-person-badge-here">{b}</span>'
        heads.append(f'<span class="dl-head-cell" title="Session {s.n}">{b}</span>')
    return (f'<div class="dl-grid-head" aria-hidden="true"><span class="dl-grid-head-l">Sessions</span>'
            f'<span class="dl-cells">{"".join(heads)}</span><span class="dl-head-bar"></span></div>')


def navigator(sessions, current, focus, all_view, all_lit=False) -> str:
    qmax, thirds = max_quotes(sessions), cuts(sessions)
    parts = [key(all_view), grid_head(sessions, current, all_lit)]
    for title, items in SECTIONS:
        parts.append(f'<div role="group"><h2 class="toc-heading">{e(title)}</h2>'
                     + "".join(nav_row(it, sessions, current, focus, qmax, thirds) for it in items) + "</div>")
    return f'<nav class="dl-nav toc-sidebar-body" aria-label="Discussion guide">{"".join(parts)}</nav>'


def quote(time: str, code: str, text: str, people: dict[str, str]) -> str:
    return (f'<blockquote class="quote-card"><div class="quote-row"><span class="timecode">[{time}]</span>'
            f'<div class="quote-body"><span class="quote-text-wrapper"><span class="smart-quote">“</span>'
            f'<span class="quote-text">{e(text)}</span><span class="smart-quote">”</span></span> '
            f'<span class="speaker">{badge(code, people.get(code, ""))}</span></div></div></blockquote>')


def ask(time: str, text: str, mod: str, item: str, hot: bool, noans: bool) -> str:
    na = '<span class="dl-noans">No quotes from this question</span>' if noans else ""
    return (f'<blockquote class="quote-card dl-ask{" hot" if hot else ""}" data-item="{item}">'
            f'<div class="quote-row"><span class="timecode">[{time}]</span><div class="quote-body">'
            f'<button type="button" class="dl-ask-btn"><span class="moderator-question-text">{e(text)}</span>'
            f'</button><span class="speaker">{badge(mod)}</span>{na}</div></div></blockquote>')


def session_block(s: Sess, it: Item, lead: bool, focus: str | None) -> str:
    """One session's ask(s) and answers for one item. lead = the All view's session lead-in."""
    pp = {p.code: p.name for p in s.people}
    out = []
    if lead:
        # PROPOSED: the session lead-in — the bar's own badge, a button that opens this session here.
        nm = names_of(s)
        out.append(f'<button type="button" class="dl-from" title="Show session {s.n}">'
                   f'{badge(f"#{s.n}", nm)}</button>')
    for t, wording, answers in said(s, it.id):
        out.append(ask(t, wording, s.mod, it.id, focus == it.id and not lead, not answers))
        for qt, code, text in answers:
            out.append(quote(qt, code or s.people[0].code, text, pp))
    return f'<div class="dl-group">{"".join(out)}</div>'


def content_session(sessions: list[Sess], current: int, focus: str | None) -> str:
    s = next(x for x in sessions if x.n == current)
    groups = [session_block(s, it, False, focus)
              for _t, items in SECTIONS for it in items if current in asked(it, sessions)]
    nq = sum(yield_of(s, it.id)[0] for _t, items in SECTIONS for it in items if current in asked(it, sessions))
    badges = "".join(badge(p.code, p.name) for p in s.people)
    meta = (f'<div class="dl-meta">{badges}<span class="dl-stats">{s.duration} · '
            f'{len(groups)} questions · {nq} quotes</span></div>')
    return (f'<div class="dl-content"><section><div class="section-heading"><h1>Session {s.n}</h1></div>'
            f"{meta}{''.join(groups)}</section></div>")


def not_asked(sids: list[int], sessions: list[Sess]) -> str:
    missing = [s.n for s in sessions if s.n not in sids]
    if not missing:
        return ""
    # PROPOSED: absence is information — one line, the sessions as compact absent badges.
    codes = " ".join(cbadge(f"#{n}", "absent") for n in missing)
    return f'<p class="dl-before dl-notasked">Not asked in {codes}</p>'


def content_all(sessions: list[Sess], focus: str | None, only: list[str] | None, total: str) -> str:
    parts = []
    nq_all = 0
    for title, items in SECTIONS:
        body = []
        for it in items:
            sids = asked(it, sessions)
            nq_all += sum(yield_of(s, it.id)[0] for s in sessions if s.n in sids)
            if only and it.id not in only:
                continue
            blocks = "".join(session_block(s, it, True, None) for s in sessions if s.n in sids)
            if not sids:
                blocks = '<p class="dl-before">Planned, never asked</p>'
            body.append(f'<div class="dl-item"><h3>{e(it.text)}</h3>'
                        f"{blocks}{not_asked(sids, sessions) if sids else ''}</div>")
        if body:
            parts.append(f'<h2 class="dl-part">{e(title)}</h2>{"".join(body)}')
    n_q = sum(1 for _t, items in SECTIONS for it in items if asked(it, sessions))
    meta = f'<div class="dl-meta"><span class="dl-stats">{total} · {n_q} questions · {nq_all} quotes</span></div>'
    return (f'<div class="dl-content"><section><div class="section-heading"><h1>All sessions</h1></div>'
            f"{meta}{''.join(parts)}</section></div>")


def lens(sessions, current, focus=None, nav_w=300, tier="names", only=None, total="1h 31m",
         all_lit=False, lid="", hsize="regular", hhash="off") -> str:
    all_view = current is None
    content = (content_all(sessions, focus, only, total) if all_view
               else content_session(sessions, current, focus))
    gut = ('<div class="dl-gut"><svg class="dl-wires" aria-hidden="true"></svg>'
           '<div class="drag-handle dl-split" role="separator"></div></div>')
    cls = "dl-lens" + (" has-focus" if focus else "")
    idattr = f' id="{lid}"' if lid else ""
    return (f'<div class="{cls}"{idattr} style="--dl-nav-w:{nav_w}px" data-all="{str(all_view).lower()}" '
            f'data-n="{len(sessions)}" data-hsize="{hsize}" data-hhash="{hhash}">'
            f"{session_bar(sessions, current, tier)}{navigator(sessions, current, focus, all_view, all_lit)}"
            f"{gut}{content}</div>")


# ── page chrome (never inside a frame) ───────────────────────────────────────


def frame(label: str, art: str, width: int, height: int | None = 620, flags: str = "",
          note: str = "", inactive: bool = False, ctl: str = "") -> str:
    fl = f'<span class="m-flag">{flags}</span>' if flags else ""
    h = f"height:{height}px" if height else ""
    win = f'<div class="m-window{" bn-window-inactive" if inactive else ""}" style="width:{width}px;{h}">{art}</div>'
    n = f'<div class="m-note"><span class="m-note-label">Commentary</span>{note}</div>' if note else ""
    return (f'<figure class="m-frame"><figcaption class="m-chrome"><span class="m-dots"><i></i><i></i><i></i></span>'
            f"<span>{label}</span>{ctl}{fl}</figcaption>{win}</figure>{n}")


def bar_only(sessions, current, tier, width, label, flags="") -> str:
    art = f'<div class="dl-lens m-baronly" style="--dl-nav-w:240px">{session_bar(sessions, current, tier)}</div>'
    return frame(label, art, width, None, flags)


def scale_specimen() -> str:
    """The owner's case: one question drew 10 quotes, six drew 1, three drew 0 — linear vs log."""
    case = [("Favourite object", 10)] + [(f"Question {c}", 1) for c in "BCDEFG"] + \
           [(f"Question {c}", 0) for c in "HIJ"]
    def col(title: str, log: bool, old_cells: bool) -> str:
        rows = []
        for text, q in case:
            w = bar_pct(q, 10) if log else round(10 * q)
            bar = (f'<span class="tag-micro-bar" style="width:{w}%;background-color:var(--dl-bar)"></span>'
                   if q else "")
            cell = "z" if q == 0 else ("s3" if q == 10 else ("m-old-s1" if old_cells else "s1"))
            rows.append(f'<div class="toc-link dl-row"><span class="dl-row-btn"><span class="dl-mk">'
                        f'<span class="dl-dot"></span></span><span class="dl-tx">{text}</span></span>'
                        f'<span class="dl-measure"><span class="dl-cells"><span class="dl-cell {cell}"></span>'
                        f'<span class="dl-cell off"></span></span><span class="tag-bar-area">{bar}'
                        f'<span class="tag-count">{q}</span></span></span></div>')
        return (f'<div class="m-scale-col"><div class="m-bs-h">{title}</div>'
                f'<nav class="dl-nav toc-sidebar-body m-spec-nav">{"".join(rows)}</nav></div>')
    return ('<div class="dl-lens dl-m-strip m-scale" data-n="2" style="--dl-nav-w:300px">'
            + col("before: linear bar, light first shade", False, True)
            + col("now: log bar, first shade well off the paper", True, False) + "</div>")


def lead_specimen() -> str:
    it = SECTIONS[0][1][0]
    rows = "".join(session_block(s, it, True, None) for s in [TWELVE[i] for i in (0, 1, 2, 3, 4, 6)])
    return ('<div class="dl-lens m-baronly" style="--dl-nav-w:0px"><div class="dl-content m-solo"><section>'
            f"<h3>Favourite object</h3>{rows}</section></div></div>")


def badge_states() -> str:
    """The compact badge in its four states, in the three places it lives."""
    def line(label: str, states: list[tuple[str, str]], note: str = "") -> str:
        cells = "".join(f'<span class="m-bs">{cbadge(c, st)}</span>' for c, st in states)
        return (f'<div class="m-bs-row"><span class="m-bs-l">{label}</span><span class="m-bs-c">{cells}</span>'
                f'<span class="m-bs-n">{note}</span></div>')
    sess = lambda st_of: [(f"#{n}", st_of(n)) for n in range(1, 9)]  # noqa: E731
    asked_in = {1, 2, 3, 5, 6, 8}
    return (
        '<div class="m-bs-wrap">'
        '<div class="m-bs-h">One badge, four states</div>'
        + line("present", [("#1", "present"), ("p1", "present")], "got asked / spoke")
        + line("absent", [("#4", "absent"), ("p2", "absent")], "not asked in this session / did not speak")
        + line("selected", [("#3", "here"), ("p3", "here")], "this session is selected (the shipped here mark)")
        + '<div class="m-bs-h">A row of sessions for one question (asked in #1 #2 #3 #5 #6 #8)</div>'
        + line("#3 selected", sess(lambda n: "here" if n == 3 else ("present" if n in asked_in else "absent")))
        + line("All · A: nothing lit", sess(lambda n: "present" if n in asked_in else "absent"),
               "All is lit in the bar; the badges say only asked / not asked")
        + line("All · B: every present lit", sess(lambda n: "here" if n in asked_in else "absent"),
               "everything in view is selected, so every asked session takes the mark")
        + '<div class="m-bs-h">Signals participant chips: shipped vs this badge</div>'
        + '<div class="m-bs-row"><span class="m-bs-l">shipped .p-box</span><span class="m-bs-c m-card">'
          '<span class="participant-grid" style="--card-accent:var(--bn-emo-1-bg)">'
          '<span class="participant-count">2/3</span><span class="p-box p-present">p1</span>'
          '<span class="p-box">p2</span><span class="p-box p-present">p3</span></span></span>'
          '<span class="m-bs-n">no keyline; absent at opacity .6 = 2.0:1</span></div>'
        + '<div class="m-bs-row"><span class="m-bs-l">compact badge</span><span class="m-bs-c m-card">'
          '<span class="participant-grid"><span class="participant-count">2/3</span>'
          + cbadge("p1") + cbadge("p2", "absent") + cbadge("p3") +
          '</span></span><span class="m-bs-n">keyline back; absent = outline, muted, no fill (4.8:1)</span></div>'
        + "</div>"
    )


CHROME_CSS = r"""
/* ── mockup chrome: m- prefixed, never inside a frame ── */
body.m-page { margin: 0; padding: 32px 24px 80px; background: light-dark(#e9e9ec, #0d0d0f);
  font-family: var(--bn-font-body); color: var(--bn-colour-text); }
.m-page h1.m-title { font-size: 22px; margin: 0 0 4px; }
.m-page .m-sub { color: var(--bn-colour-muted); margin: 0 0 18px; max-width: 900px; }
.m-ctl { display: flex; gap: 18px; flex-wrap: wrap; margin: 0 0 18px; font: 12px var(--bn-font-mono); }
.m-ctl label { display: inline-flex; gap: 6px; align-items: center; }
.m-keyrow { display: flex; gap: 12px; margin: 0 0 28px; font: 12px var(--bn-font-mono); }
.m-keyrow span { padding: 4px 10px; border-radius: 6px; }
.m-k-art { background: var(--bn-colour-bg); border: 1px solid var(--bn-colour-border); }
.m-k-com { background: repeating-linear-gradient(135deg, light-dark(#fff8e1,#2a2618) 0 8px, light-dark(#fff3cd,#302a1a) 8px 16px);
  border-left: 3px solid #d4a017; }
.m-part { font: 600 15px var(--bn-font-body); margin: 44px 0 14px; padding-top: 14px;
  border-top: 2px solid light-dark(#c9c9ce, #333); max-width: 1180px; }
.m-frame { margin: 0 0 10px; display: inline-block; vertical-align: top; }
.m-chrome { display: flex; gap: 10px; align-items: center; padding: 6px 10px; font: 11px var(--bn-font-mono);
  background: light-dark(#dcdce0, #26262a); color: light-dark(#444, #bbb); border-radius: 8px 8px 0 0; }
.m-chrome input[type=range] { width: 260px; }
.m-chrome label { display: inline-flex; gap: 4px; align-items: center; }
.m-readout table td:nth-child(n+2), .m-readout table th:nth-child(n+2) { text-align: right; font-variant-numeric: tabular-nums; }
.m-readout tr.m-cur td { font-weight: 700; }
.m-dots { display: inline-flex; gap: 4px; } .m-dots i { width: 8px; height: 8px; border-radius: 50%; background: light-dark(#bbb,#555); }
.m-flag { margin-left: auto; color: light-dark(#8a5a00, #e0b050); }
.m-window { background: var(--bn-colour-bg); color: var(--bn-colour-text); overflow: auto; position: relative;
  border: 1px solid light-dark(#cfcfd4, #333); border-top: 0; border-radius: 0 0 8px 8px; }
.m-note { max-width: 1100px; margin: 0 0 30px; padding: 10px 14px; font-size: 13px; line-height: 1.5;
  background: repeating-linear-gradient(135deg, light-dark(#fff8e1,#2a2618) 0 8px, light-dark(#fff3cd,#302a1a) 8px 16px);
  border-left: 3px solid #d4a017; color: light-dark(#3a3000, #eadfb8); }
.m-note-label { display: block; font: 600 10px var(--bn-font-mono); letter-spacing: .08em; text-transform: uppercase;
  margin-bottom: 4px; opacity: .7; }
.m-note p { margin: 0 0 6px; } .m-note ul { margin: 0 0 6px; padding-left: 18px; }
.m-note code { font-size: 12px; }
.m-note table { border-collapse: collapse; font-size: 12px; margin-top: 6px; }
.m-note td, .m-note th { border: 1px solid light-dark(#d9c98a,#4a4228); padding: 3px 8px; text-align: left; vertical-align: top; }
.m-pair { display: flex; gap: 16px; flex-wrap: wrap; align-items: flex-start; }

/* Frame plumbing — makes the real sticky panes work inside a fixed-height frame
   instead of the browser window. Mockup-only; the shipped rules are untouched. */
.m-window .dl-lens .dl-nav, .m-window .dl-lens .dl-gut { height: calc(var(--m-win-h, 620px) - var(--dl-bar-h, 0px)); }
.m-window .dl-lens .dl-nav { scrollbar-width: thin; }
.m-baronly { display: grid; }
.m-solo { grid-column: 1 / -1; padding-left: var(--bn-gutter-left); }
/* badge-state specimen */
.m-bs-wrap { padding: 14px 18px 18px; }
.m-bs-h { font: 600 12px var(--bn-font-body); margin: 14px 0 6px; color: var(--bn-colour-muted); }
.m-bs-h:first-child { margin-top: 0; }
.m-bs-row { display: grid; grid-template-columns: 170px auto 1fr; gap: 14px; align-items: center; padding: 4px 0; }
.m-bs-l { font: 11px var(--bn-font-mono); color: var(--bn-colour-muted); }
.m-bs-c { display: inline-flex; gap: 3px; align-items: center; }
.m-bs-n { font-size: 12px; color: var(--bn-colour-muted); }
.m-scale { display: flex; gap: 24px; padding: 12px; }
.m-scale-col { width: 400px; }
.m-scale .dl-nav { width: 400px; height: auto !important; }
.m-scale .dl-row { display: flex; }
.m-old-s1 { background: color-mix(in srgb, var(--bn-colour-text) 20%, var(--bn-colour-bg)); }
.m-card { padding: 8px 10px; border-radius: var(--bn-radius-md); background: var(--bn-emo-1-bg); }
"""

PROPOSED_CSS = r"""
/* ════ PROPOSED — option A, iteration 2. Nothing below is shipped. Each rule says what it is. ════ */

/* PROPOSED: the keyline between All and the sessions — All is a different kind of choice. */
.dl-sessions .dl-sep { width: 1px; align-self: stretch; margin: var(--bn-space-xs) 0;
  background: var(--bn-colour-border); }
/* PROPOSED: the bar's pull-down when even the codes do not fit (the navigator rows' .dl-pick, in the bar). */
.dl-bar-pick { position: relative; }
.dl-bar-pick select { position: absolute; inset: 0; opacity: 0; width: 100%; height: 100%; cursor: pointer; }

/* PROPOSED: the compact number-only person badge. The code half as shipped — keyline and all —
   with the line height and padding the Signals .p-box already uses. Type stays at badge size. */
.bn-person-badge-compact .bn-speaker-badge-code { line-height: 1; padding: 2px 0.3rem; }
/* PROPOSED: absent — outline only. Muted ink on the page, no fill, the keyline kept; never opacity. */
.bn-person-badge-absent .bn-speaker-badge-code { background: transparent; color: var(--bn-colour-muted); }
.participant-grid .bn-person-badge-compact .bn-speaker-badge-code:not(.bn-person-badge-absent *) {
  background: color-mix(in srgb, var(--bn-colour-bg) 70%, transparent); color: var(--bn-colour-text); }

/* PROPOSED: All view headings. The guide's section (h2) above its questions (the shipped h3). */
.dl-content .dl-part { font-size: var(--bn-text-label); font-weight: var(--bn-weight-emphasis);
  color: var(--bn-colour-muted); margin: var(--bn-space-xl) 0 0; padding-bottom: .25rem;
  border-bottom: 1px solid var(--bn-colour-border); max-width: var(--bn-max-width); }
.dl-content .dl-item > h3 { max-width: var(--bn-max-width); margin-top: var(--bn-space-lg); }
.dl-content .dl-item > h3 + .dl-group { border-top-color: transparent; margin-top: 0; padding-top: var(--bn-space-xs); }
/* PROPOSED: the session lead-in — the bar's badge as a button that opens this session at this question. */
.dl-from { display: inline-flex; align-items: center; margin: 0 0 var(--bn-space-xs) calc(-1 * var(--bn-space-xs));
  padding: var(--bn-space-xs); background: none; border: 0; border-radius: var(--bn-radius-md); font: inherit; cursor: pointer; }
.dl-from:hover { background: var(--bn-colour-hover); }
.dl-from .bn-speaker-badge-name { max-width: 16em; overflow: hidden; text-overflow: ellipsis; }
/* PROPOSED: "Not asked in #4 #11" — the shipped .dl-before line, holding compact absent badges. */
.dl-notasked { display: flex; flex-wrap: wrap; gap: 3px; align-items: center; margin-top: var(--bn-space-sm); }

/* ── PROPOSED: the navigator measure. Replaces the row's session chips and #N ▾ pull-down. ──
   Three tiers, one chosen per lens by measuring the guide's width (never by a session count):
     dl-m-bar   — the tags sidebar's bar + count (MicroBar, .tag-bar-area/.tag-count, shipped)
     dl-m-strip — one thin cell per session, then the count
     dl-m-grid  — wide cells under sticky session heads, then the bar + count
   Cell fill is a NEUTRAL ramp of the ink into the paper (no new colour; follows light/dark):
     off = not asked (keyline only — the absent badge's outline) ·
     z = asked, no quotes (rare; drawn exactly as not asked, the tooltip says which) ·
     s1–s3 = the cell's quote count in the study's lower, middle and upper third. One measure,
     normalised to the study: more people talking and more said both raise it. */
.dl-lens { --dl-bar: color-mix(in srgb, var(--bn-colour-text) 40%, var(--bn-colour-bg));
  --dl-pitch: 8px; --dl-cell-w: 6px; --dl-cell-h: 12px; }
.dl-lens.dl-m-grid { --dl-pitch: var(--dl-grid-pitch, 30px); --dl-cell-w: calc(var(--dl-grid-pitch, 30px) - 6px);
  --dl-cell-h: 14px; }
/* PROPOSED (lab option): micro heads — the micro type size, tighter padding. Sets the grid's pitch. */
.dl-lens[data-hsize="micro"] .dl-grid-head .bn-speaker-badge-code { font-size: var(--bn-text-micro);
  padding: 1px 0.2rem; }
/* PROPOSED (lab option): heads without the # — the column header already says Sessions. */
.dl-lens[data-hhash="off"] .dl-h-hash { display: none; }
.dl-nav .dl-row { align-items: center; }
.dl-measure { display: inline-flex; align-items: center; gap: var(--bn-space-sm); flex: none; }
.dl-cells { display: inline-grid; grid-auto-flow: column; grid-auto-columns: var(--dl-pitch);
  justify-items: center; align-items: center; }
.dl-cell { appearance: none; padding: 0; margin: 0; border: 0; cursor: pointer;
  width: var(--dl-cell-w); height: var(--dl-cell-h); border-radius: 2px; }
.dl-cell.off { background: transparent; box-shadow: inset 0 0 0 1px var(--bn-colour-border); cursor: default; }
/* Asked, no quotes: drawn as not asked — it might as well not have been (owner, 18 Oct). The
   tooltip still says which. A separate look is a parked edge case. */
.dl-cell.z { background: transparent; box-shadow: inset 0 0 0 1px var(--bn-colour-border); }
/* Not linear: the ramp STARTS well off the paper. Any quote is a clearly filled cell — the big
   step is none → some; medium and dark are smaller steps above it. */
.dl-cell.s1 { background: color-mix(in srgb, var(--bn-colour-text) 38%, var(--bn-colour-bg)); }
.dl-cell.s2 { background: color-mix(in srgb, var(--bn-colour-text) 56%, var(--bn-colour-bg)); }
.dl-cell.s3 { background: color-mix(in srgb, var(--bn-colour-text) 76%, var(--bn-colour-bg)); }
/* the selected session's column: the accent ring, the "you are here" of a cell */
.dl-cell.here { outline: 1.5px solid var(--bn-colour-accent); outline-offset: 1px; }
.dl-cell:not(.off):hover { outline: 1px solid var(--bn-colour-text); outline-offset: 1px; }
.dl-measure .tag-bar-area { display: inline-flex; align-items: center; justify-content: flex-end;
  gap: var(--bn-space-xs); width: 72px; }
.dl-measure .tag-count { font-size: var(--bn-text-caption); color: var(--bn-colour-muted);
  min-width: 16px; text-align: right; font-variant-numeric: tabular-nums; }
.dl-measure .tag-micro-bar { display: inline-block; max-width: 48px; }
.dl-m-bar .dl-cells, .dl-m-bar .dl-key-cells { display: none; }
.dl-m-strip .dl-measure .tag-bar-area { width: auto; }
.dl-m-strip .dl-measure .tag-micro-bar { display: none; }
.dl-row.active .dl-cell.off { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--bn-colour-text) 25%, transparent); }
/* the grid's heads — compact badges on the cell pitch, sticky under the bar */
.dl-grid-head { display: none; }
.dl-m-grid .dl-grid-head { display: flex; align-items: center; gap: var(--bn-space-sm);
  position: sticky; top: calc(-1 * var(--bn-space-sm)); z-index: 1; margin: 0 0 var(--bn-space-sm);
  padding: var(--bn-space-xs) var(--bn-space-sm); background: var(--bn-colour-inspector-bg);
  border-bottom: 1px solid var(--bn-colour-border); }
.dl-grid-head-l { flex: 1; font-size: var(--bn-text-caption); color: var(--bn-colour-muted); }
.dl-head-cell { display: inline-flex; justify-content: center; }
/* PROPOSED: the single-digit badge sets the grid's pitch for every study. Two-digit labels are
   squeezed into the same box — no side padding, tighter tracking, and a horizontal squash
   (--dl-sq, measured to fit). Some squished numbers beat a grid too wide to be seen. */
.dl-grid-head .bn-speaker-badge-code.dl-h-wide { box-sizing: border-box; width: var(--dl-head-w, auto);
  padding-inline: 0; display: inline-flex; justify-content: center; }
.dl-h-wide .dl-h-n { display: inline-block; letter-spacing: -0.04em; transform: scaleX(var(--dl-sq, 0.8)); }
.dl-head-bar { width: 72px; flex: none; }
.dl-key-cells .dl-cell { display: inline-block; vertical-align: -2px; margin-right: 4px; width: 10px; height: 10px; }

/* PROPOSED FIX to shipped discussion.css: the question's timecode sat on the question's LAST line.
   .quote-row aligns on baseline, and the question is a <button> — inline-block, whose baseline is
   its last line. Top-aligning the button puts the line's baseline back on its first line, as a
   quote's is. */
.dl-ask-btn { vertical-align: top; }

/* PROPOSED: selection follows the Mac rule — solid accent only while the guide has keyboard focus
   (the grid makes ↑/↓ and ←/→ real). .m-focus stands in for :focus-within in the mockup. */
.dl-nav:focus-within .toc-link.active, .dl-nav.m-focus .toc-link.active {
  background: var(--bn-colour-accent); color: #fff; }
/* PROPOSED: window in the background — the selection keeps its fill, loses its colour. */
.bn-window-inactive .dl-nav .toc-link.active { color: var(--bn-colour-text); }
.bn-window-inactive .bn-person-badge-here .bn-speaker-badge-code,
.bn-window-inactive .bn-person-badge-here .bn-speaker-badge-name { color: var(--bn-colour-text); }
.bn-window-inactive .dl-cell.here { outline-color: var(--bn-colour-muted); }
"""

SCRIPT = r"""
// Mockup only. (1) Measure the bar for the sticky panes. (2) Choose each lens's measure
// tier by MEASURING the guide — the rule the lens would ship. (3) Draw the wires the way
// DiscussionLens does (wirePath in model.ts) in the session view; the All view has none.
const TEXT_MIN = 130, BAR_W = 72, GAP = 8;
// The grid's pitch is the SINGLE-DIGIT head badge plus 4px — measured. Two-digit heads are
// squeezed into that box: --dl-head-w is its width, --dl-sq the squash that fits them.
function headPitch(lens) {
  const cells = lens.querySelectorAll('.dl-grid-head .dl-head-cell');
  if (!cells.length) return 30;
  const probe = document.createElement('div');
  probe.className = 'dl-grid-head';
  probe.style.cssText = 'display:flex;position:absolute;visibility:hidden;left:-9999px';
  probe.innerHTML = cells[0].innerHTML + cells[cells.length - 1].innerHTML;
  lens.querySelector('.dl-nav').appendChild(probe);
  const w1 = probe.children[0].getBoundingClientRect().width;
  lens.style.setProperty('--dl-head-w', w1 + 'px');
  const wide = probe.querySelector('.dl-h-wide .dl-h-n');
  if (wide) {
    const inner = w1 - 2 - 2;                      // the keyline both sides, a pixel of air each side
    lens.style.setProperty('--dl-sq', Math.min(1, inner / wide.offsetWidth).toFixed(3));
  }
  probe.remove();
  return Math.ceil(w1) + 4;
}
function needs(n, pitch) {                       // the guide width each tier needs, in px
  const fixed = 16 + 22 + TEXT_MIN + GAP;
  return { strip: fixed + n * 8 + 28, grid: fixed + n * pitch + BAR_W };
}
function tier(lens) {
  const nav = lens.querySelector('.dl-nav'); if (!nav) return;
  const n = +lens.dataset.n;
  const pitch = headPitch(lens);
  lens.style.setProperty('--dl-grid-pitch', pitch + 'px');
  const room = nav.clientWidth - 16 - 22 - TEXT_MIN;      // padding, the mark column, the shortest text
  const grid = n * pitch + GAP + BAR_W, strip = n * 8 + GAP + 28;
  lens.classList.remove('dl-m-bar', 'dl-m-strip', 'dl-m-grid');
  lens.classList.add(n > 1 && room >= grid ? 'dl-m-grid' : n > 1 && room >= strip ? 'dl-m-strip' : 'dl-m-bar');
  const out = lens.closest('.m-frame')?.querySelector('.m-tier');
  if (out) out.textContent = `guide ${nav.clientWidth}px → ${[...lens.classList].find(c => c.startsWith('dl-m-')).slice(5)} · pitch ${pitch}px`;
  const ro = document.querySelector(`.m-readout[data-lens="${lens.id}"]`);
  if (ro) readout(ro, lens);
}
// The lab's table: for the current badge options, how wide the guide must be for 6, 8 and 12.
function readout(ro, lens) {
  const save = [lens.dataset.hsize, lens.dataset.hhash];
  const rows = [];
  for (const [hs, hh, label] of [['regular','on','regular · #8'], ['regular','off','regular · 8'],
                                 ['micro','on','micro · #8'], ['micro','off','micro · 8']]) {
    lens.dataset.hsize = hs; lens.dataset.hhash = hh;
    const p = headPitch(lens);
    const cur = hs === save[0] && hh === save[1] ? ' class="m-cur"' : '';
    rows.push(`<tr${cur}><td>${label}</td><td>${p}px</td>` +
      [6, 8, 12].map(n => `<td>${needs(n, p).grid}px</td>`).join('') + '</tr>');
  }
  [lens.dataset.hsize, lens.dataset.hhash] = save;
  ro.innerHTML = '<table><tr><th>grid heads</th><th>pitch</th><th>6 sessions</th><th>8 sessions</th>' +
    '<th>12 sessions</th></tr>' + rows.join('') +
    `<tr><td>strip (no heads)</td><td>8px</td>${[6, 8, 12].map(n => `<td>${needs(n, 8).strip}px</td>`).join('')}</tr>` +
    '<tr><td>bar + count</td><td>—</td><td colspan="3">any width</td></tr></table>' +
    '<p>The guide opens at 300px (the shared sidebar default) and drags to 60% of the lens.</p>';
}
function fit() {
  document.querySelectorAll('.m-window').forEach(win => {
    win.style.setProperty('--m-win-h', win.clientHeight + 'px');
    win.querySelectorAll('.dl-lens').forEach(lens => {
      const bar = lens.querySelector('.dl-bar');
      if (bar) lens.style.setProperty('--dl-bar-h', bar.offsetHeight + 'px');
      tier(lens); wires(lens);
    });
  });
}
function wires(lens) {
  const svg = lens.querySelector('.dl-wires');
  if (!svg) return;
  svg.innerHTML = '';
  if (lens.dataset.all === 'true') return;
  const gut = lens.querySelector('.dl-gut').getBoundingClientRect();
  const w = gut.width, focus = lens.querySelector('.dl-row.active')?.dataset.id;
  lens.querySelectorAll('.dl-ask[data-item]').forEach(a => {
    const row = lens.querySelector(`.dl-row[data-id="${a.dataset.item}"]`);
    if (!row) return;
    const y1 = row.getBoundingClientRect().top + row.offsetHeight / 2 - gut.top;
    const y2 = a.getBoundingClientRect().top + 14 - gut.top;
    if (y2 < 0 || y2 > gut.height) return;
    const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    p.setAttribute('d', `M0,${y1} h8 L${w - 8},${y2} h8`);
    p.setAttribute('class', 'dl-wire' + (focus === a.dataset.item ? ' hot' : ''));
    svg.appendChild(p);
  });
}
document.querySelectorAll('.m-window').forEach(w => w.addEventListener('scroll', fit, { passive: true }));
document.querySelectorAll('.m-hsize').forEach(c => c.addEventListener('change', ev => {
  document.getElementById(ev.target.dataset.lens).dataset.hsize = ev.target.value; fit(); }));
document.querySelectorAll('.m-hhash').forEach(c => c.addEventListener('change', ev => {
  document.getElementById(ev.target.dataset.lens).dataset.hhash = ev.target.checked ? 'on' : 'off'; fit(); }));
document.querySelectorAll('.m-nav-w').forEach(r => r.addEventListener('input', ev => {
  const lens = document.getElementById(ev.target.dataset.lens);
  lens.style.setProperty('--dl-nav-w', ev.target.value + 'px'); fit(); }));
addEventListener('resize', fit);
document.getElementById('m-palette').addEventListener('change', ev => {
  document.documentElement.dataset.colorTheme = ev.target.value; fit(); });
document.getElementById('m-scheme').addEventListener('change', ev => {
  const v = ev.target.value;
  if (v === 'auto') delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = v;
  document.documentElement.style.colorScheme = v === 'auto' ? 'light dark' : v; });
document.getElementById('m-platform').addEventListener('change', ev => {
  if (ev.target.checked) document.documentElement.dataset.platform = 'desktop';
  else delete document.documentElement.dataset.platform; fit(); });
document.fonts?.ready.then(fit); fit();
"""


def lab_ctl(lid: str) -> str:
    return (f'<label>heads <select class="m-hsize" data-lens="{lid}"><option value="regular">regular</option>'
            f'<option value="micro">micro</option></select></label>'
            f'<label><input type="checkbox" class="m-hhash" data-lens="{lid}"> #</label>')


def slider(lid: str, lo: int, hi: int, val: int) -> str:
    return (f'<input type="range" class="m-nav-w" data-lens="{lid}" min="{lo}" max="{hi}" value="{val}">'
            '<span class="m-tier"></span>')


def build() -> str:
    theme = load_default_css()
    disc = DISCUSSION_CSS.read_text(encoding="utf-8")
    F: list[str] = []

    F.append('<div class="m-part">1 · The width lab: a typical eight-session study</div>')
    F.append(frame("All · 8 sessions · lab", lens(EIGHT, None, focus="fav", nav_w=420, tier="codes",
                                                   only=["fav"], total="4h 37m", lid="lab8"),
                   1180, 600, "lab: head size, #, width",
                   ctl=slider("lab8", 220, 700, 420) + lab_ctl("lab8"),
                   note="<p><b>How wide must the guide be to show the grid for a typical 6–8 session study?</b> "
                   "The heads set the grid's pitch, so they set the answer: switch <i>heads</i> between the regular "
                   "compact badge and micro type, and turn the <i>#</i> off, then drag. The table is measured "
                   "live from the badges as drawn, in the palette and type you have selected:</p>"
                   '<div class="m-readout" data-lens="lab8"></div>'
                   "<p>Below the grid's width the measure collapses to the <b>strip</b> (8px a session, no heads; "
                   "hover a cell for its session), and below that to the <b>bar + count</b>, which fits any width. "
                   "So nothing has to be designed for the narrow case: the strip is the narrow grid.</p>"))
    F.append(frame("your case: 10, six at 1, three at 0", scale_specimen(), 900, None, "proposed: not linear",
                   "<p>Left, the scales as they were: one quote is a 10% sliver of bar and a cell barely darker "
                   "than nothing, so the six one-quote questions look almost as bad as the three that drew none. "
                   "Right: the bar is logarithmic (one quote fills about a third), and the first filled shade is "
                   "already a clear grey. <b>None → some</b> is now the biggest step on both scales.</p>"))
    F.append('<div class="m-part">2 · The navigator measure: drag the guide wider (twelve sessions)</div>')
    F.append(frame("All · 12 sessions · live", lens(TWELVE, None, focus="fav", nav_w=300, tier="codes",
                                                     only=["fav"], total="7h 18m", lid="live12"),
                   1180, 680, "new: dl-measure, dl-cell, dl-grid-head", ctl=slider("live12", 220, 700, 300),
                   note="<p><b>Drag the slider</b> (it stands in for the guide's drag handle). Each row's measure "
                   "is chosen by measuring the guide, the same way the session chips fold today:</p><ul>"
                   "<li><b>Bar</b>, narrow: the tags sidebar's bar and count, as shipped. Read down the guide, "
                   "it's a histogram of which questions drew quotes. The count is quotes, as in tags: a number of "
                   "things, not a score.</li>"
                   "<li><b>Strip</b>, once one thin cell per session fits: the count stays, and the bar gives way to "
                   "the cells. Coverage and yield in one glance: an outline cell was not asked, and the darker the "
                   "cell, the more that session gave on that question.</li>"
                   "<li><b>Grid</b>, once you've dragged it wide: the cells grow onto a 30px pitch under sticky "
                   "session heads (the compact badge), with the bar and count back at the end. Now it reads by "
                   "column as well: <b>#7 empties at ikea.com</b>, it ran out of time.</li></ul>"
                   "<p><b>One shade, normalised to the study: did this question get more or less here?</b> A cell's "
                   "shade is its quote count ranked against every other asked cell in the study, in thirds: light, "
                   "medium, dark. More people talking and more said both raise it, so nothing separate is needed "
                   "for groups. Read a row for the questions that worked, and a column for the sessions to read in "
                   "full. A zero is rare and not interesting, so it's drawn as not asked; only the tooltip tells them apart. "
                   "In a mixed study the groups lean dark, which is true: they gave more. The tooltip says how many "
                   "people that was (<i>#3 Bettina and 4 others · 4 quotes from 4 of 5 people</i>). The thirds move "
                   "as sessions are added. The ramp is the ink mixed into the paper, so there's no new colour.</p>"
                   "<p><b>Not linear.</b> Some data is much better than none, so the biggest visual step is from "
                   "nothing to one quote: the lightest filled cell is already well off the paper, and the row's bar "
                   "is logarithmic (one quote against a maximum of ten fills about a third of it, not a tenth). "
                   "The exact count is the number at the end of the row.</p>"
                   "<p><b>The cells replace the chips and the <code>#N ▾</code> pull-down.</b> Clicking a cell opens that "
                   "session at that question, which is the chips' job. At the bar tier the drill-in is the "
                   "session lead-in in the column.</p>"))

    F.append('<div class="m-part">3 · All selected: do the session heads light up?</div>')
    pair = (frame("All · grid · A: heads not lit · DECIDED",
                  lens(TWELVE, None, focus="fav", nav_w=640, tier="codes", only=["fav"], total="7h 18m"),
                  1180, 520, "decided 18 Oct 2026")
            + frame("All · grid · B: every head lit · not chosen",
                    lens(TWELVE, None, focus="fav", nav_w=640, tier="codes", only=["fav"], total="7h 18m",
                         all_lit=True), 1180, 520, "not chosen"))
    F.append(f'<div class="m-pair">{pair}</div>')
    F.append('<div class="m-note"><span class="m-note-label">Commentary</span>'
             "<p><b>Decided 18 Oct 2026: A, nothing lit; heads without the #; regular badge size.</b> <b>A</b>: the bar already says <i>All</i> in accent. The heads stay "
             "neutral, so the accent appears only once, on the choice you made. <b>B, every head lit</b> is "
             "literally true (every session is selected), but twelve accent marks in the guide plus <i>All</i> in "
             "the bar make the accent mean “everything”, and it stops pointing at anything. B has one "
             "thing going for it: switching to <code>#3</code> then visibly takes the mark away from the other "
             "eleven, which explains the change. A gets the same from the accent ring moving onto #3's "
             "column of cells (part 4).</p></div>")

    F.append('<div class="m-part">4 · One session selected: the column is “you are here”</div>')
    F.append(frame("#3 · a focus group · grid", lens(TWELVE, 3, focus="fav", nav_w=640, tier="codes",
                                                     total="7h 18m"), 1180, 620,
                   "new: dl-cell.here",
                   "<p>The selected session's head takes the shipped here mark, and its column of cells takes the "
                   "accent ring. Reading down the ring answers <i>what did this session cover</i>. Rows this "
                   "session never asked are grey (shipped), and their cell in the ring is an outline. The wires are back, "
                   "because this is the conversation order again.</p>"))
    F.append(frame("#1 · three sessions · strip", lens(THREE, 1, focus="fav", nav_w=320), 1000, 560,
                   "three sessions",
                   "<p>With three sessions the grid fits early (3 × 30px), so most guides will show it at "
                   "their default width. Drag narrower and it falls back to strip, then bar.</p>"))
    F.append(frame("All · three sessions", lens(THREE, None, focus="fav", nav_w=360), 1000, 600, "three sessions"))

    F.append('<div class="m-part">5 · The compact badge: present, absent, selected, All</div>')
    F.append(frame("compact number-only badge · states", badge_states(), 900, None,
                   "new: bn-person-badge-compact, -absent",
                   "<p>The code half of the shipped <code>PersonBadge</code> with its keyline. Only the line height "
                   "and padding tighten (the Signals <code>.p-box</code>'s, which got that part right); the type "
                   "stays at badge size. <b>Present</b> is the badge as shipped. <b>Absent</b> is the outline only: "
                   "muted ink, no fill, keyline kept, 4.8:1 on its own, never opacity. <b>Selected</b> is the "
                   "shipped <code>.bn-person-badge-here</code>. One badge for <code>#N</code> sessions and "
                   "<code>pN</code> participants, in the guide's heads, “Not asked in”, and Signals cards. "
                   "The grid's outline cell and the absent badge are the same idea, so the chip and the grid "
                   "agree.</p>"))

    F.append('<div class="m-part">6 · Big studies</div>')
    F.append(frame("All · 30 sessions · live", lens(THIRTY, None, focus="fav", nav_w=320, tier="pick",
                                                     only=["fav"], total="15h 00m", lid="live30"),
                   1180, 560, "30 one-to-ones", ctl=slider("live30", 220, 700, 320),
                   note="<p>Thirty sessions: the bar holds at the default width, the strip arrives at about "
                   "430px, and the grid needs about 1,000px, more than 60% of most lenses, so in practice "
                   "the strip is the most it shows. That's the right ceiling: a 30-column grid is a "
                   "spreadsheet, and the place for that is an export.</p>"))

    F.append('<div class="m-part">7 · The session bar, tier by tier (unchanged from iteration 1)</div>')
    F.append("".join([
        bar_only(THREE, None, "names", 1000, "3 sessions · All · names fit"),
        bar_only(TWELVE[:6], 2, "names", 1180, "6 sessions · #2 a pair · names fit"),
        bar_only(TWELVE, None, "codes", 1180, "12 · All · codes only", "new"),
        bar_only(TWELVE, 5, "codes", 1180, "12 · #5 · selected keeps its (long) name", "new"),
        bar_only(ANON, 3, "codes", 1180, "12 · anonymised export · nothing but codes", "new"),
        bar_only(TWELVE, None, "pick", 620, "12 · narrow · All + Sessions ▾", "new"),
        bar_only(TWELVE, 7, "pick", 620, "12 · narrow · #7 an unnamed pair", "new"),
        bar_only(THREE[:1], 1, "names", 620, "1 session · no All"),
    ]))

    F.append('<div class="m-part">8 · The session lead-in in the All column</div>')
    F.append(frame("lead-ins in the All view", lead_specimen(), 900, None, "new: dl-from",
                   "<p>Single named, a pair, a group capped to <i>Bettina and 4 others</i>, unnamed, a long name "
                   "truncated at 16em, an unnamed pair. The same badge and names as the bar.</p>"))

    F.append('<div class="m-part">9 · Selection and the window</div>')
    F.append(frame("window inactive", lens(THREE, 1, focus="fav", nav_w=320), 1000, 420, "proposed",
                   "<p>In a background window the accent goes to ink: the guide row, the session badge, and the "
                   "ring on the selected column. That uses the existing <code>.bn-window-inactive</code> class. "
                   "The grid gives the guide real arrow-key movement (↑/↓ between questions, ←/→ between "
                   "sessions), which is what would earn the solid-blue focused selection.</p>", inactive=True))

    F.append('<div class="m-part">10 · What is new</div>')
    F.append('<div class="m-note"><span class="m-note-label">Commentary · inventory</span>'
             "<table><tr><th>Strings (owner writes)</th><th>en draft</th><th>where</th></tr>"
             "<tr><td><code>discussion.all</code></td><td>All</td><td>bar</td></tr>"
             "<tr><td><code>discussion.allSessions</code></td><td>All sessions</td><td>All view heading; the All "
             "badge's tooltip</td></tr>"
             "<tr><td><code>discussion.notAskedIn</code></td><td>Not asked in</td><td>foot of a question</td></tr>"
             "<tr><td><code>discussion.showSession</code></td><td>Show session {{n}}</td><td>lead-in tooltip</td></tr>"
             "<tr><td><code>discussion.cellTip</code> (+ plural forms)</td><td>#{{n}} {{names}} · {{people}} of "
             "{{size}} people, {{count}} quotes / asked, no quotes / not asked</td><td>cell tooltip</td></tr>"
             "<tr><td><code>discussion.rowMeasure</code></td><td>asked in {{asked}} of {{total}} sessions, "
             "{{count}} quotes</td><td>screen readers only</td></tr>"
             "<tr><td><code>discussion.keyNotAsked</code> / <code>keyQuoted</code></td>"
             "<td>Not asked / Less → more, for this study</td><td>key, when cells "
             "show</td></tr><tr><td><code>discussion.sessionsHead</code></td><td>Sessions</td><td>grid heads "
             "(could reuse <code>sessions</code>)</td></tr></table>"
             "<p><b>Reused:</b> <code>MicroBar</code> + <code>.tag-bar-area</code>/<code>.tag-count</code> from the "
             "tags sidebar; <code>PersonBadge</code>; <code>.bn-person-badge-here</code>; "
             "<code>.bn-window-inactive</code>. <b>Retired:</b> the rows' <code>.dl-chips</code> and "
             "<code>.dl-pick</code>, and Signals' <code>.p-box</code> (it becomes the compact badge).</p>"
             "<p><b>Data:</b> nothing new. Each quote already carries its session, item and speaker, so a cell is a "
             "count, and the export embed already holds it.</p>"
             "<p><b>Still open:</b> A or B for All (frame 2); whether the count in the bar tier is quotes (as "
             "drawn, like tags) or people; whether the strip shows on the Your guide tab too (it should: same "
             "rows).</p></div>")

    return f"""<!DOCTYPE html>
<html lang="en" data-color-theme="default" data-platform="desktop" style="color-scheme: light dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Discussion · All sessions · Bristlenose mockups</title>
<style>
/* ════ SHIPPED: bristlenose/theme via load_default_css() — the concatenation serve and export use ════ */
{theme}
/* ════ SHIPPED: frontend/src/islands/discussion/discussion.css — verbatim ════ */
{disc}
</style>
<style>{PROPOSED_CSS}</style>
<style>{CHROME_CSS}</style>
</head>
<body class="m-page">
<h1 class="m-title">Discussion lens · option A, iteration 2: All first, and a guide that measures</h1>
<p class="m-sub">“Everything everyone said in answer to question X” — and, as you drag the guide wider, which
questions drew it out and which sessions never got there. Generated by
<code>experiments/discussion-all-sessions/build.py</code> from the lens's own markup; real pixels.</p>
<div class="m-ctl">
<label>palette <select id="m-palette"><option value="default">default</option><option value="edo">edo</option></select></label>
<label>scheme <select id="m-scheme"><option value="auto">auto</option><option value="light">light</option><option value="dark">dark</option></select></label>
<label><input type="checkbox" id="m-platform" checked> desktop type (SF Pro)</label>
</div>
<div class="m-keyrow"><span class="m-k-art">artefact: shipped classes; new parts listed in the frame's bar</span>
<span class="m-k-com">commentary: not the product</span></div>
{"".join(F)}
<script>{SCRIPT}</script>
</body>
</html>
"""


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")
