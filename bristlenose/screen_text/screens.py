"""Screen-text indexes and quotes in, screens out. Pure functions; no I/O.

The rules are the measured ones (``docs/design-screens.md`` §3.5–3.6,
``experiments/screen-text/README.md`` fourth pass):

- **A screen's key** is the address bar's path with the locale prefix dropped and each slug cut to
  the ID at its end (``/gb/en/cat/jars-tins-15950`` → ``/cat/15950``), which matches the same page
  across languages and keeps different products and categories apart. Where the address bar shows
  no path (Safari's default), the active tab's title is the key. Otherwise a session's moments have
  no screen: v1 does not guess, and the researcher can say which pages are one screen (later).
- **Furniture** — a line flagged sticky, or on screen during visits to five or more screens of a
  session — is never a pin target. Browser chrome above the page is cut by position.
- **A quote is placed** on the screen its time overlaps most (±4 s), and **pinned** to one line on
  that screen's still when it shares a run of two or more words with it (with a content word), or
  one rare long word. By words only: the sentence model that also matched by meaning is 1.8 GB and
  does not ship. Measured precision for word pins: 13 right of 16.
- **The still** for each screen and session is the moment, among those the session spent on it, that
  pins the most of that session's quotes there.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from bristlenose.screen_text.address import url_norm
from bristlenose.screen_text.index import fold

WINDOW = 4.0
ID = re.compile(r"(?:^|-)((?:[a-z]{1,3})?\d{3,})$")
STOP = set("""a an and are as at be but by for from has have i if in into is it its just like me my no not of on
or our so that the their them then there they this to was we what when where which who will with you your
yeah okay ok um uh oh well right yes really think know want would could should can also very here
der die das und ist ein eine nicht mit für auf zu den dem des sie ich wir oder""".split())
FURNITURE_SCREENS = 5


# ── Addresses and titles ─────────────────────────────────────────────────


def id_key(path: str, frag: str) -> str:
    """The address keyed to survive translation: locale prefix dropped, each slug cut to its ID."""
    p = re.sub(r"^/[a-z]{2}/[a-z]{2}(?=/|$)", "", path)
    segs = []
    for seg in p.strip("/").split("/"):
        m = ID.search(seg)
        segs.append(m.group(1) if m else seg)
    p = "/" + "/".join(x for x in segs if x)
    return p + (("#" + re.sub(r"/[#\d]+$", "", frag)) if frag else "")


def title_norm(text: str) -> str | None:
    """A browser tab title reduced to compare: favicon misreads and the site suffix dropped."""
    m = re.match(r"^(?:[^A-Za-z0-9]+|[A-Za-z0-9&]{1,2}\s)?\s*(.+?)\s+[-|–]\s+([A-Z][\w .]{1,20})\s*[.…]*$", text.strip())
    if not m or len(m.group(1)) < 4:
        return None
    core = re.sub(r"[\"“”'‘’].*?[\"“”'‘’]", "*", m.group(1))
    return fold(core) or None


def title_suffix(text: str) -> str:
    m = re.search(r"\s[-|–]\s+([A-Z][\w .]{1,20}?)\s*[.…]*$", text.strip())
    return m.group(1).strip() if m else ""


# ── One session ──────────────────────────────────────────────────────────


@dataclass
class Visit:
    key: str
    t0: float
    t1: float
    aliases: set[str] = field(default_factory=set)


@dataclass
class SessionInput:
    session_id: str
    code: str
    index: dict[str, Any]
    quotes: list[dict[str, Any]]  # dom_id, start, end, text


def _on(e: dict, t: float, slack: float = 0.0) -> bool:
    return any(r[0] - slack <= t <= r[1] + slack for r in e["runs"])


def page_top(index: dict[str, Any]) -> float:
    """Where the web page starts: below the address bar (and a bookmarks bar under it), else 0."""
    ys = [e["box"][1] + e["box"][3] for e in index["episodes"] if url_norm(e["text"]) and e["box"][1] <= 0.2]
    return min(0.3, max(ys) + 0.035) if ys else 0.0


def content_crop(index: dict[str, Any]) -> list[float]:
    """The page inside the recording: below the browser chrome, within the non-sticky lines' spread
    (which leaves call tiles, whose names are sticky, outside). Padded, clamped to the frame."""
    top = page_top(index)
    xs0, xs1, ys1 = [], [], []
    for e in index["episodes"]:
        x, y, w, h = e["box"]
        if e["sticky"] or y < top or url_norm(e["text"]):
            continue
        xs0.append(x)
        xs1.append(x + w)
        ys1.append(y + h)
    if len(xs0) < 10:
        return [0.0, top, 1.0, 1.0]
    xs0.sort()
    xs1.sort()
    ys1.sort()
    q = lambda v, p: v[min(len(v) - 1, max(0, int(p * (len(v) - 1))))]  # noqa: E731
    x0, x1, y1 = q(xs0, 0.02) - 0.02, q(xs1, 0.98) + 0.02, q(ys1, 0.99) + 0.02
    return [round(max(0.0, x0), 4), round(top, 4), round(min(1.0, x1), 4), round(min(1.0, y1), 4)]


def visits_of(index: dict[str, Any]) -> list[Visit]:
    """Runs of samples on one screen key (address with IDs, else the active tab's title)."""
    every = float(index.get("every", 4.0))
    urls, titles = [], []
    for e in index["episodes"]:
        x, y, w, h = e["box"]
        if y > 0.2:
            continue
        u = url_norm(e["text"])
        if u:
            urls.append((e, id_key(u["path"], u["frag"]) if u["path"] != "/" or u["frag"] else None))
        elif not e["sticky"] and (tt := title_norm(e["text"])):
            titles.append((e, tt, title_suffix(e["text"])))
    # Only titles carrying the session's dominant site suffix, counted by distinct titles: a
    # bookmark has a title's shape and chained unrelated pages together (measured).
    by_sfx: dict[str, set] = defaultdict(set)
    for _, tt, sx in titles:
        by_sfx[sx].add(tt)
    sfx = max(by_sfx, key=lambda k: len(by_sfx[k]), default=None)
    titles2 = [(e, tt) for e, tt, sx in titles if sx == sfx and len(by_sfx[sx]) >= 2]
    path_samples = sum(1 for _, k in urls if k)
    titles_key = path_samples < 0.2 * max(len(urls), 1)
    samples = sorted({r[0] + k * every for e, _ in urls + titles2 for r in e["runs"]
                      for k in range(int((r[1] - r[0]) / every) + 1)})
    out: list[Visit] = []
    for t in samples:
        keys = [k for e, k in urls if k and _on(e, t)]
        tts = sorted(((min(r[0] for r in e["runs"] if r[0] <= t), tt) for e, tt in titles2 if _on(e, t)), reverse=True)
        uk = Counter(keys).most_common(1)[0][0] if keys else None
        key_tt = tts[0][1] if tts else None
        alias_tt = key_tt if len({x[1] for x in tts}) == 1 else None
        key = ("url:" + uk) if uk else (("title:" + key_tt) if key_tt and titles_key else None)
        if not key:
            continue
        al = {a for a in (("url:" + uk) if uk else None, ("title:" + alias_tt) if alias_tt else None) if a}
        if out and out[-1].key == key and t - out[-1].t1 <= 3 * every:
            out[-1].t1 = t
            out[-1].aliases |= al
        else:
            out.append(Visit(key, t, t, {key} | al))
    return out


# ── Pinning ──────────────────────────────────────────────────────────────


def _content(tok: str) -> bool:
    return len(tok) >= 4 and tok not in STOP and not tok.isdigit()


def _good(phrase: str) -> bool:
    w = phrase.split()
    if len(w) >= 3:
        return any(_content(x) for x in w)
    if len(w) == 2:
        return all(x not in STOP and len(x) >= 3 for x in w)
    return True


def match(spoken: str, lines: list[dict], rare: set[str],
          tokens: dict[int, list[str]] | None = None) -> tuple[str, dict] | None:
    """The best on-screen line for *spoken*: the longest shared run of words (2+, one a content
    word), else one rare 6+ letter word; ties go to the larger line. None when nothing matches.

    *tokens* maps ``id(line)`` to its folded words, so a caller matching many quotes against the
    same lines folds each line once."""
    s = fold(spoken).split()
    best: tuple[str, dict] | None = None
    best_rank = (0, 0.0)
    for ln in lines:
        t = tokens[id(ln)] if tokens is not None and id(ln) in tokens else fold(ln["text"]).split()
        phrase = ""
        for i in range(len(s)):
            for j in range(len(t)):
                k = 0
                while i + k < len(s) and j + k < len(t) and s[i + k] == t[j + k]:
                    k += 1
                if k >= 2 and any(_content(x) for x in s[i:i + k]) and k > len(phrase.split()):
                    phrase = " ".join(s[i:i + k])
        if not phrase:
            hit = [w for w in set(s) & set(t) if len(w) >= 6 and w not in STOP and w in rare]
            if hit:
                phrase = max(hit, key=len)
        if not phrase or not _good(phrase):
            continue
        rank = (len(phrase.split()), ln["box"][2] * ln["box"][3])
        if rank > best_rank:
            best, best_rank = (phrase, ln), rank
    return best


# ── Across sessions ──────────────────────────────────────────────────────


def _heading(lines: list[dict], top: float, bottom: float) -> str:
    """The page's own heading: the tallest line of words in the top half of the page."""
    cands = []
    for ln in lines:
        t = re.sub(r"^(?:[^\w\s]+|\w(?=\s))\s*", "", ln["text"].strip()).strip()
        letters = sum(c.isalpha() for c in t)
        if (len(t) <= 40 and letters >= 4 and letters >= 0.6 * len(t.replace(" ", ""))
                and not re.search(r"[$£€]|\d", t) and ln["box"][1] <= top + 0.55 * (bottom - top)):
            cands.append((t, ln["box"]))
    if not cands:
        return ""
    tallest = max(b[3] for _, b in cands)
    return min(((t, b) for t, b in cands if b[3] >= 0.95 * tallest), key=lambda c: c[1][1])[0]


Linker = Callable[[list[dict[str, Any]]], list[dict[str, Any]]]


def _session_tabs(
    s: SessionInput, visits: list[Visit],
) -> tuple[dict[str, dict[str, Any]], dict[str, tuple[list[dict[str, Any]], Linker]]]:
    """One session's still, pins and unpinned quotes for each screen it visited, and for each
    screen its quotes and a linker: which of any quotes (anyone's) find their line on this still."""
    idx = s.index
    every = float(idx.get("every", 4.0))
    crop = content_crop(idx)
    top = crop[1]
    # Furniture: sticky, or on screen during visits to FURNITURE_SCREENS or more screens.
    seen: dict[str, set] = defaultdict(set)
    for e in idx["episodes"]:
        for v in visits:
            if any(r[0] <= v.t1 + every and r[1] >= v.t0 for r in e["runs"]):
                seen[fold(e["text"])].add(v.key)
    furniture = {k for k, ks in seen.items() if len(ks) >= FURNITURE_SCREENS}
    furniture |= {fold(e["text"]) for e in idx["episodes"] if e["sticky"]}

    def inside(box: list[float]) -> bool:
        cx, cy = box[0] + box[2] / 2, box[1] + box[3] / 2
        return crop[0] <= cx <= crop[2] and crop[1] <= cy <= crop[3]

    content = [e for e in idx["episodes"] if not url_norm(e["text"]) and inside(e["box"])
               and fold(e["text"]) not in furniture and len(fold(e["text"])) >= 2]
    tokens = {id(e): fold(e["text"]).split() for e in content}
    freq = Counter(w for e in content for w in set(tokens[id(e)]))
    rare = {w for w, c in freq.items() if c <= 3}
    # Memoised: a still is chosen by asking what is on screen at each candidate several times, and
    # an hour of browsing has thousands of lines (measured 3 s a session unmemoised, 14 Oct 2026).
    on_at: dict[float, list[dict]] = {}

    def lines_at(t: float) -> list[dict]:
        # Exactly what the still shows: a line seen up to a sample before is not on it.
        if t not in on_at:
            on_at[t] = [e for e in content if _on(e, t, 0.05)]
        return on_at[t]

    def screen_of(q: dict) -> str | None:
        best, score = None, 0.0
        for v in visits:
            ov = min(q["end"] + WINDOW, v.t1 + every) - max(q["start"] - WINDOW, v.t0)
            if ov > score:
                best, score = v.key, ov
        return best

    pinned_at: dict[tuple[str, float], list[tuple[dict, tuple[str, dict]]]] = {}

    def pins_at(t: float, qs: list[dict], key: str) -> list[tuple[dict, tuple[str, dict]]]:
        if (key, t) not in pinned_at:
            ls = lines_at(t)
            pinned_at[(key, t)] = [(q, m) for q in qs if (m := match(q["text"], ls, rare, tokens))]
        return pinned_at[(key, t)]

    w, h = crop[2] - crop[0], crop[3] - crop[1]

    def to_crop(b: list[float]) -> list[float]:
        return [round((b[0] - crop[0]) / w, 4), round((b[1] - crop[1]) / h, 4),
                round(b[2] / w, 4), round(b[3] / h, 4)]

    by_screen: dict[str, list[dict]] = defaultdict(list)
    for q in s.quotes:
        k = screen_of(q)
        if k:
            by_screen[k].append(q)
    tabs: dict[str, dict[str, Any]] = {}
    extra: dict[str, tuple[list[dict[str, Any]], Linker]] = {}

    def pin_dicts(found: list[tuple[dict, tuple[str, dict]]]) -> list[dict[str, Any]]:
        return [{"dom_id": q["dom_id"], "box": to_crop(m[1]["box"]), "phrase": m[0], "line": m[1]["text"]}
                for q, m in found]

    for key in sorted({v.key for v in visits}):
        qs = sorted(by_screen.get(key, []), key=lambda q: q["start"])
        vs = [v for v in visits if v.key == key]
        cands = sorted({round(v.t0 + k * every, 2) for v in vs for k in range(int((v.t1 - v.t0) / every) + 1)})
        cands = [t for t in cands if lines_at(t)]
        if not cands:
            continue
        if len(cands) > 24:
            cands = [cands[round(i * (len(cands) - 1) / 23)] for i in range(24)]
        # A still is a moment the page is drawn: among moments showing at least 60% of the most
        # lines seen on this screen (a loading page has few), the one pinning the most quotes.
        most = max(len(lines_at(t)) for t in cands)
        drawn = [t for t in cands if len(lines_at(t)) >= 0.6 * most]
        still = max(drawn, key=lambda t, qs=qs, k=key: (len(pins_at(t, qs, k)), len(lines_at(t))))
        pins = pins_at(still, qs, key)
        pinned = {q["dom_id"] for q, _ in pins}
        tabs[key] = {
            "session_id": s.session_id, "code": s.code, "t": still, "crop": crop,
            "heading": _heading(lines_at(still), top, crop[3]),
            "visits": [[v.t0, v.t1] for v in vs],
            "pins": pin_dicts(pins),
            "loose": [q["dom_id"] for q in qs if q["dom_id"] not in pinned],
        }

        def link(others: list[dict[str, Any]], t: float = still) -> list[dict[str, Any]]:
            ls = lines_at(t)
            return pin_dicts([(q, m) for q in others if (m := match(q["text"], ls, rare, tokens))])

        extra[key] = (qs, link)
    return tabs, extra


def derive_screens(sessions: Iterable[SessionInput]) -> list[dict[str, Any]]:
    """Every screen any session was on, with each session's still, pins and unpinned quotes.

    Boxes are in the still's crop coordinates (0–1 of the cropped page)."""
    sessions = list(sessions)
    per: dict[str, dict[str, Any]] = {}
    parent: dict[str, str] = {}

    def find(a: str) -> str:
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for s in sessions:
        visits = visits_of(s.index)
        # A title seen with two or more addresses in one session is chrome (a bookmark), not a title.
        urls_per_title: dict[str, set] = defaultdict(set)
        for v in visits:
            for a in v.aliases:
                if a.startswith("title:"):
                    urls_per_title[a] |= {b for b in v.aliases if b.startswith("url:")}
        bad = {a for a, us in urls_per_title.items() if len(us) >= 2}
        for v in visits:
            v.aliases -= bad
            if not v.aliases:
                v.aliases = {v.key}
            al = sorted(v.aliases)
            for a in al[1:]:
                parent[find(a)] = find(al[0])
            find(al[0])
        per[s.session_id] = {"s": s, "visits": visits}

    names: dict[str, Counter] = defaultdict(Counter)
    for d in per.values():
        for v in d["visits"]:
            for a in v.aliases:
                names[find(a)][a] += 1

    def display(root: str) -> str:
        c = names[root]
        urls = [a for a, _ in c.most_common() if a.startswith("url:")]
        return urls[0][4:] if urls else c.most_common(1)[0][0][6:]

    out: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    said: dict[str, list[dict[str, Any]]] = defaultdict(list)
    linkers: dict[str, list[tuple[dict[str, Any], Linker]]] = defaultdict(list)
    for d in per.values():
        visits: list[Visit] = d["visits"]
        for v in visits:
            v.key = find(sorted(v.aliases)[0])
        tabs, extra = _session_tabs(d["s"], visits)
        for key, tab in tabs.items():
            if key not in out:
                out[key] = {"key": key, "name": display(key), "tabs": []}
                order.append(key)
            out[key]["tabs"].append(tab)
            qs, link = extra[key]
            said[key].extend(qs)
            linkers[key].append((tab, link))
    # A screen is one place for everything said about it: each version's still links every
    # participant's quote whose words it shows, not only its own participant's.
    for key, pairs in linkers.items():
        for tab, link in pairs:
            own = {p["dom_id"] for p in tab["pins"]}
            tab["pins"] += [p for p in link([q for q in said[key] if q["dom_id"] not in own])]
    screens = [out[k] for k in order]
    for sc in screens:
        sc["tabs"].sort(key=lambda t: (t["code"], t["t"]))
        # The version shown first: the one on which the most quotes find their line.
        sc["default_tab"] = max(range(len(sc["tabs"])), key=lambda j: (len(sc["tabs"][j]["pins"]), -j))
        sc["quotes"] = len(said[sc["key"]])
    # Most-said-about first; a screen nobody spoke on still appears, last, so the map is whole.
    screens.sort(key=lambda sc: (-sc["quotes"], -len(sc["tabs"]), min(t["visits"][0][0] for t in sc["tabs"])))
    return screens
