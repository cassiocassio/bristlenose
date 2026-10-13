"""Three participants, one set of screens: can each quote float beside exactly the right element?

    <ocr-venv>/bin/python experiments/screen-text/screens_board.py <config.json> -o <private>/screens.html [--labels <private>/labels.json]

The owner's test, 13 Oct 2026 (docs/design-screens.md): take three IKEA sessions (one on the UK site,
one on the German site, one on an iPad), cut each into screens by the address bar, put every quote on the
screen it was said on by timecode, then pin each quote to the screen element it talks about, by shared
words or by meaning, and stack the same screen across participants (tab-flippable) with their quotes
combined.

config.json lists sessions: {"tag", "label", "index", "quotes", "session", "video"}, optionally
"code" (p1…), "name", and "crop" ([x0, y0, x1, y1], the web page inside the recording). The index is
pipeline_spike.py's output (episodes with on-screen runs, every 4 s).

Steps, all measured and printed as aggregates:
1. **Visits.** At each 4 s sample, the address-bar URL on screen (an OCR line in the top 15% of the
   share area that is a single host/path token — `url_norm`, after experiments/screens-lens/visits.py),
   reduced to a cross-locale **template** (`template`, after experiments/screens-lens/flows.py: locale
   prefix dropped, product/category slugs masked). Consecutive samples with one template are a visit.
2. **Quotes on screens.** A quote belongs to the visit its interval overlaps most (± 4 s).
3. **Shared screens.** Templates visited by 2+ participants.
4. **Stills.** Per (screen, participant): the visit sample at which the most of that participant's
   quote phrases are readable, OCR'd afresh (positions belong to a moment).
5. **Anchors.** Per quote, against its still's own OCR lines: *lexical* (anchor_spike's rule: a 2+ word
   phrase with content words, or a rare 6+ letter word) and *semantic* (a local multilingual sentence
   embedding, LaBSE, quote vs each line; best cosine above a threshold). Lexical wins when both fire.
6. **Cross-participant elements.** For a shared screen, each anchored line on one participant's still is
   mapped to the most similar line (same embedding) on the others' stills, so a quote can be shown on
   every tab of the stack.

--labels reads a private file of hand judgements ({tag: {quote_start: "right"|"wrong"|"none"}}) and
prints precision against them. The HTML carries participants' screens and speech: write it privately.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from anchor_spike import STOP, content, matches, tc_to_s  # noqa: E402
from score import fold  # noqa: E402

WINDOW = 4.0
SHARE_X = 0.865
HOST = re.compile(r"((?:[a-z0-9-]+\.)+(?:com|co\.uk|de|org|net|io|app|uk|eu|fr|es|it)(?:/[^\s]*)?)", re.I)
SEM_THRESHOLD = 0.40  # quote ↔ element, LaBSE; calibrated against hand labels
SAME_ELEMENT = 0.70   # element ↔ element across stills (translation pairs 0.73+, non-pairs ≤ 0.65)


def url_norm(text: str) -> dict | None:
    t = re.sub(r"^[^a-z0-9]+", "", text.strip().lower())
    t = re.sub(r"^https?://", "", t).rstrip("|/ ") + "/"
    t = re.sub(r"^(?:[^\s]{1,2}\s+)", "", t) if " " in t else t
    if " " in t.strip():
        return None
    m = HOST.search(t)
    if not m or m.start() > 0:
        return None
    u = m.group(1).lower().replace("productld", "productid")
    u = re.sub(r"^www\.", "", u)
    path, _, frag = u.partition("#")
    path = path.partition("?")[0]
    host, _, p = path.partition("/")
    return {"host": host, "path": "/" + p.rstrip("/"), "frag": re.sub(r"\d{4,}", "#", frag.split("?")[0])}


def template(path: str, frag: str) -> str:
    p = re.sub(r"^/[a-z]{2}/[a-z]{2}(?=/|$)", "", path)
    p = re.sub(r"/p/[^/]+", "/p/*", p)
    p = re.sub(r"/cat/[^/]+", "/cat/*", p)
    p = re.sub(r"/addon-app/.*", "/planner-app", p)
    p = re.sub(r"\d{4,}", "#", p)
    return (p or "/") + (("#" + re.sub(r"/[#\d]+$", "", frag)) if frag else "")


def title_norm(text: str) -> str | None:
    """A browser tab title, reduced to compare across sessions: favicon misreads at the front dropped
    ("1 ", "Es ", "•"), the site suffix ("- IKEA UK") dropped, quoted search terms masked."""
    t = text.strip()
    m = re.match(r"^(?:[^A-Za-z0-9]+|[A-Za-z0-9&]{1,2}\s)?\s*(.+?)\s+[-|–]\s+([A-Z][\w .]{1,20})\s*[.…]*$", t)
    if not m or len(m.group(1)) < 4:
        return None
    core = re.sub(r"[\"“”'‘’].*?[\"“”'‘’]", "*", m.group(1))
    return fold(core) or None


def title_suffix(text: str) -> str:
    m = re.search(r"\s[-|–]\s+([A-Z][\w .]{1,20}?)\s*[.…]*$", text.strip())
    return m.group(1).strip() if m else ""


def is_url(text: str) -> bool:
    return url_norm(text) is not None


def good(phrase: str) -> bool:
    w = phrase.split()
    if len(w) >= 3:
        return any(content(x) for x in w)
    if len(w) == 2:
        return all(x not in STOP and len(x) >= 3 for x in w)
    return True


class Session:
    def __init__(self, cfg: dict) -> None:
        self.tag, self.label, self.video = cfg["tag"], cfg["label"], Path(cfg["video"])
        self.code, self.name = cfg.get("code", "p1"), cfg.get("name", "")
        # The web page inside the recording: no call tiles, no browser chrome. Pins may only land in
        # here — a browser's restore-tabs bar or a translate popup is not the screen being tested.
        self.crop = cfg.get("crop", [0.0, 0.1, SHARE_X, 1.0])
        idx = json.loads(Path(cfg["index"]).read_text())
        self.every = idx["every"]
        self.eps = idx["episodes"]
        self.content_eps = [e for e in self.eps if not e["sticky"] and not is_url(e["text"])]
        qs = [q for q in json.loads(Path(cfg["quotes"]).read_text()) if q.get("session_id") == cfg["session"]]
        self.quotes = [{"t0": tc_to_s(q["start_timecode"]), "t1": tc_to_s(q["end_timecode"]),
                        "who": q.get("participant_id", ""), "sent": q.get("sentiment") or "",
                        "text": q.get("verbatim_excerpt") or q["text"]} for q in qs]
        self.visits = self._visits()
        # Page furniture: a line flagged sticky (same words, same place, most of the session) or on
        # screen during visits to 5+ different screens is not about any one of them (the site's
        # search placeholder, a cart badge). Measured on 27 hand-labelled pins: this drops 3 wrong
        # and 0 right; a 3-screen bar dropped 4 right ("Continue to checkout", nav items) as well.
        seen: dict[str, set] = defaultdict(set)
        for e in self.eps:
            for v in self.visits:
                if any(r[0] <= v["t1"] + self.every and r[1] >= v["t0"] for r in e["runs"]):
                    seen[fold(e["text"])].add(v["tp"])
        self.furniture = {k for k, v in seen.items() if len(v) >= 5} | {fold(e["text"]) for e in self.eps if e["sticky"]}

    def _visits(self) -> list[dict]:
        # Two screen keys per sample. The address bar's URL template when it shows a path; Safari's
        # default shows only the bare host (measured: the iPad session read "ikea.com" throughout), so
        # the active tab's title is the second key — the most recently appeared title-shaped line in
        # the browser chrome. Both are kept as aliases so sessions keyed differently can be linked.
        urls, titles = [], []
        for e in self.eps:
            x, y, w, h = e["box"]
            if y > 0.16 or x > SHARE_X:
                continue
            u = url_norm(e["text"])
            if u and y <= 0.15:
                urls.append((e, template(u["path"], u["frag"]) if u["path"] != "/" or u["frag"] else None))
            elif not e["sticky"] and (tt := title_norm(e["text"])):
                titles.append((e, tt, title_suffix(e["text"])))
        # Only titles carrying the session's dominant site suffix ("IKEA UK"): a bookmark such as
        # pointing at another site has the same shape and chained unrelated pages together (measured).
        # Dominant suffix by DISTINCT titles: a bookmark is one title seen on every frame, a site's tabs
        # are many titles sharing one suffix (a bookmark won by frequency, measured).
        by_sfx: dict[str, set] = defaultdict(set)
        for _, tt, sx in titles:
            by_sfx[sx].add(tt)
        sfx = max(by_sfx, key=lambda k: len(by_sfx[k]), default=None)
        titles = [(e, tt) for e, tt, sx in titles if sx == sfx and len(by_sfx[sx]) >= 2]
        # Titles key a session only when its address bar shows no paths (Safari's default); where URL
        # paths exist they are the key, and titles only link screens across sessions.
        path_samples = sum(1 for _, tp in urls if tp)
        titles_key = path_samples < 0.2 * max(len(urls), 1)
        samples = sorted({r[0] + k * self.every for e, _ in urls + titles for r in e["runs"]
                          for k in range(int((r[1] - r[0]) / self.every) + 1)})
        visits: list[dict] = []
        for t in samples:
            def on(e): return any(r[0] <= t <= r[1] for r in e["runs"])
            tps = [tp for e, tp in urls if tp and on(e)]
            tts = sorted(((min(r[0] for r in e["runs"] if r[0] <= t), tt) for e, tt in titles if on(e)), reverse=True)
            tp = Counter(tps).most_common(1)[0][0] if tps else None
            # As a KEY, the most recently appeared title is the active tab's. As an ALIAS that links a
            # URL-keyed screen to a title-keyed one, only an unambiguous title: with several tabs on
            # screen a wrong guess chains unrelated pages together (measured).
            key_tt = tts[0][1] if tts else None
            tt = key_tt if len({x[1] for x in tts}) == 1 else None
            key = ("url:" + tp) if tp else (("title:" + key_tt) if key_tt and titles_key else None)
            if not key:
                continue
            if visits and visits[-1]["tp"] == key and t - visits[-1]["t1"] <= 3 * self.every:
                visits[-1]["t1"] = t
                visits[-1]["aliases"].update(a for a in (("url:" + tp) if tp else None, ("title:" + tt) if tt else None) if a)
            else:
                visits.append({"tp": key, "t0": t, "t1": t,
                               "aliases": {key} | {a for a in (("url:" + tp) if tp else None, ("title:" + tt) if tt else None) if a}})
        return visits

    def screen_of(self, q: dict) -> str | None:
        best, score = None, 0.0
        for v in self.visits:
            ov = min(q["t1"] + WINDOW, v["t1"] + self.every) - max(q["t0"] - WINDOW, v["t0"])
            if ov > score:
                best, score = v["tp"], ov
        return best

    def lines_at(self, t: float, read) -> list[dict]:
        full = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(self.video),
                               "-frames:v", "1", "-q:v", "2", "-f", "mjpeg", "-"], capture_output=True, check=True).stdout
        tmp = Path(f"/tmp/screens-board-{self.tag}.jpg")
        tmp.write_bytes(full)
        out = [ln for ln in read(tmp) if ln["conf"] >= 0.5 and not is_url(ln["text"])
               and self.inside(ln["box"]) and fold(ln["text"]) not in self.furniture]
        tmp.unlink()
        return out

    def inside(self, box: list[float]) -> bool:
        x0, y0, x1, y1 = self.crop
        cx, cy = box[0] + box[2] / 2, box[1] + box[3] / 2
        return x0 <= cx <= x1 and y0 <= cy <= y1

    def to_crop(self, box: list[float]) -> list[float]:
        x0, y0, x1, y1 = self.crop
        w, h = x1 - x0, y1 - y0
        return [round((box[0] - x0) / w, 4), round((box[1] - y0) / h, 4), round(box[2] / w, 4), round(box[3] / h, 4)]

    def frame_b64(self, t: float, width: int, cropped: bool = False) -> str:
        vf = f"scale={width}:-2"
        if cropped:
            x0, y0, x1, y1 = self.crop
            vf = f"crop=iw*{x1 - x0:.4f}:ih*{y1 - y0:.4f}:iw*{x0:.4f}:ih*{y0:.4f}," + vf
        jpg = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(self.video),
                              "-frames:v", "1", "-vf", vf, "-q:v", "3", "-f", "mjpeg", "-"],
                             capture_output=True, check=True).stdout
        return "data:image/jpeg;base64," + base64.b64encode(jpg).decode()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("config", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--labels", type=Path)
    ap.add_argument("--dump", type=Path, help="write per-quote decisions (private) for labelling")
    ap.add_argument("--style", choices=["rough", "lens"], default="lens",
                    help="lens: the design-system page (screens_lens.html + the shipped theme CSS)")
    args = ap.parse_args()
    sessions = [Session(c) for c in json.loads(args.config.read_text())]

    # Link screen keys: a URL template and a tab title seen in one visit are one screen, in every
    # session. Union-find over the aliases; a screen is named by its title alias when it has one.
    parent: dict[str, str] = {}

    def find(a: str) -> str:
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    # A page title maps to one URL. A title seen with two or more URL templates in a session is
    # chrome (a bookmark, a pinned tab), not a title, and must not link anything (measured: the
    # one bookmark chained every page of the German session into one screen).
    for s in sessions:
        urls_per_title: dict[str, set] = defaultdict(set)
        for v in s.visits:
            for a in v["aliases"]:
                if a.startswith("title:"):
                    urls_per_title[a] |= {b for b in v["aliases"] if b.startswith("url:")}
        bad = {a for a, us in urls_per_title.items() if len(us) >= 2}
        for v in s.visits:
            v["aliases"] -= bad
            if not v["aliases"]:
                v["aliases"] = {v["tp"]}
    for s in sessions:
        for v in s.visits:
            al = sorted(v["aliases"])
            for a in al[1:]:
                parent[find(a)] = find(al[0])
    names: dict[str, Counter] = defaultdict(Counter)
    for s in sessions:
        for v in s.visits:
            for a in v["aliases"]:
                names[find(a)][a] += 1
    def display(root: str) -> str:
        c = names[root]
        titles = [a for a, _ in c.most_common() if a.startswith("title:")]
        return titles[0][6:] if titles else c.most_common(1)[0][0][4:]
    for s in sessions:
        for v in s.visits:
            v["tp"] = display(find(v["tp"]))

    # 1–3: visits, quotes on screens, shared screens
    by_screen: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    print("== visits and quotes on screens")
    for s in sessions:
        placed = 0
        for q in s.quotes:
            q["screen"] = s.screen_of(q)
            if q["screen"]:
                placed += 1
                by_screen[q["screen"]][s.tag].append(q)
        tps = Counter(v["tp"] for v in s.visits)
        print(f"{s.label}: {len(s.visits)} visits over {len(tps)} screens; {len(s.quotes)} quotes, "
              f"{placed} on a screen by timecode")
    visited = defaultdict(set)
    for s in sessions:
        for v in s.visits:
            visited[v["tp"]].add(s.tag)
    shared = {tp for tp, who in visited.items() if len(who) >= 2}
    q_on_shared = sum(len(qs) for tp in shared for qs in by_screen[tp].values())
    q_placed = sum(len(qs) for d in by_screen.values() for qs in d.values())
    print(f"screens: {len(visited)} distinct templates, {len(shared)} visited by 2+ participants "
          f"({sum(1 for w in visited.values() if len(w) == 3)} by all three); "
          f"{q_on_shared} of {q_placed} placed quotes are on a shared screen")

    # 4–5: stills and anchors
    from ocr_bench import vision
    from sentence_transformers import SentenceTransformer
    read = vision(0)
    model = SentenceTransformer("sentence-transformers/LaBSE")
    cache: dict[tuple[str, float], list[dict]] = {}

    def ocr(s: Session, t: float) -> list[dict]:
        if (s.tag, t) not in cache:
            cache[(s.tag, t)] = s.lines_at(t, read)
        return cache[(s.tag, t)]

    def anchor(q: dict, lines: list[dict], rare: set[str]) -> dict | None:
        lex = [(p, ln) for p, ln in matches(q["text"], lines, rare) if good(p)]
        if lex:
            p, ln = max(lex, key=lambda m: (len(m[0].split()), m[1]["box"][2] * m[1]["box"][3]))
            return {"how": "words", "phrase": p, "line": ln, "score": 1.0}
        # By meaning only against a line that says something: a word of 4+ letters (not "120.0")
        cand = [ln for ln in lines if any(len(w) >= 4 and w.isalpha() for w in fold(ln["text"]).split())]
        if not cand:
            return None
        qe = model.encode([q["text"]], normalize_embeddings=True)
        le = model.encode([ln["text"] for ln in cand], normalize_embeddings=True)
        sims = (le @ qe.T).ravel()
        i = int(sims.argmax())
        if sims[i] >= SEM_THRESHOLD:
            return {"how": "meaning", "phrase": "", "line": cand[i], "score": round(float(sims[i]), 2)}
        return None

    boards = []
    stats = Counter()
    decisions = []
    for tp in sorted(by_screen, key=lambda tp: -sum(len(v) for v in by_screen[tp].values())):
        tabs = []
        for s in sessions:
            vs = [v for v in s.visits if v["tp"] == tp]
            if not vs:
                continue
            qs = by_screen[tp].get(s.tag, [])
            freq = Counter(w for e in s.content_eps for w in set(fold(e["text"]).split()))
            rare = {w for w, c in freq.items() if c <= 3}
            cands = sorted({v["t0"] + k * s.every for v in vs for k in range(int((v["t1"] - v["t0"]) / s.every) + 1)})
            if len(cands) > 12:  # bound the OCR work: spread 12 candidates over the visits
                cands = [cands[round(i * (len(cands) - 1) / 11)] for i in range(12)]

            def score(t: float) -> tuple[int, int]:
                lines = ocr(s, t)
                return (sum(anchor(q, lines, rare) is not None for q in qs), len(lines))

            best = max(cands, key=score) if qs else max(cands, key=lambda t: len(ocr(s, t)))
            lines = ocr(s, best)
            pins = []
            for q in qs:
                a = anchor(q, lines, rare)
                stats["quotes"] += 1
                if a:
                    stats["anchored_" + a["how"]] += 1
                    pins.append({"q": q, **a})
                decisions.append({"tag": s.tag, "screen": tp, "t0": round(q["t0"], 1), "still": best,
                                  "text": q["text"], "how": a["how"] if a else None,
                                  "line": a["line"]["text"] if a else None, "score": a["score"] if a else None})
            tabs.append({"s": s, "t": best, "lines": lines, "pins": pins, "qs": qs})
        boards.append({"tp": tp, "tabs": tabs})

    print(f"== anchors: {stats['quotes']} placed quotes; {stats['anchored_words']} by shared words, "
          f"{stats['anchored_meaning']} by meaning, {stats['quotes'] - stats['anchored_words'] - stats['anchored_meaning']} not anchored")

    # 6: cross-participant element mapping on shared screens
    mapped = 0
    for b in boards:
        if len(b["tabs"]) < 2:
            continue
        embs = {id(tab): (model.encode([ln["text"] for ln in tab["lines"]], normalize_embeddings=True)
                          if tab["lines"] else None) for tab in b["tabs"]}
        for tab in b["tabs"]:
            for p in tab["pins"]:
                p["elsewhere"] = {}
                pe = model.encode([p["line"]["text"]], normalize_embeddings=True)
                for other in b["tabs"]:
                    if other is tab or embs[id(other)] is None:
                        continue
                    sims = (embs[id(other)] @ pe.T).ravel()
                    i = int(sims.argmax())
                    # same element: similar text AND a similar place on the page
                    ob = other["lines"][i]["box"]
                    near = abs(ob[1] - p["line"]["box"][1]) < 0.15 and abs(ob[0] - p["line"]["box"][0]) < 0.25
                    if sims[i] >= SAME_ELEMENT and near:
                        p["elsewhere"][other["s"].tag] = {"box": ob, "text": other["lines"][i]["text"],
                                                         "score": round(float(sims[i]), 2)}
                        mapped += 1
    print(f"== cross-participant: {mapped} pin placements carried onto another participant's still")

    if args.dump:
        args.dump.write_text(json.dumps(decisions, ensure_ascii=False, indent=1))
    if args.labels and args.labels.exists():
        labels = json.loads(args.labels.read_text())
        c = Counter()
        for d in decisions:
            lab = labels.get(d["tag"], {}).get(str(d["t0"]))
            if lab is None:
                continue
            # a label judges one pin; if the pin moved to another line it needs judging again
            fate = "kept" if d["line"] == lab["line"] else ("dropped" if d["line"] is None else "moved")
            c[f'{lab["verdict"]} pin {fate}' + (f' ({d["how"]})' if fate == "kept" else "")] += 1
        print("== against hand labels:", dict(c))

    if args.style == "lens":
        write_lens(args.out, boards, stats)
    else:
        write_html(args.out, boards, sessions)
    print(args.out)


def write_html(out: Path, boards: list, sessions: list) -> None:
    data = []
    for b in boards:
        tabs = []
        for tab in b["tabs"]:
            s = tab["s"]
            tabs.append({
                "tag": s.tag, "label": s.label, "t": int(tab["t"]), "src": s.frame_b64(tab["t"], 1600),
                "thumb": s.frame_b64(tab["t"], 220),
                "pins": [{"box": p["line"]["box"], "how": p["how"], "phrase": p["phrase"], "line": p["line"]["text"],
                          "score": p["score"], "who": s.label, "tc": int(p["q"]["t0"]), "sent": p["q"]["sent"],
                          "text": p["q"]["text"], "elsewhere": p.get("elsewhere", {})} for p in tab["pins"]],
                "loose": [{"who": s.label, "tc": int(q["t0"]), "sent": q["sent"], "text": q["text"]}
                          for q in tab["qs"] if not any(p["q"] is q for p in tab["pins"])],
            })
        data.append({"tp": b["tp"], "tabs": tabs})
    blob = json.dumps({"boards": data}, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(TEMPLATE.replace("/*DATA*/null", blob))


HERE = Path(__file__).parent
THEME = HERE.parent.parent / "bristlenose" / "theme"
# The shipped stylesheets the lens page is drawn with, in index.css order. Inlined at generation time
# so the page cannot drift from the tree: each block is headed by its path.
THEME_FILES = ["tokens.css", "tokens-typography.css", "colors/palette-default.css", "colors/palette-edo.css",
               "atoms/badge.css", "atoms/timecode.css", "atoms/interactive.css", "atoms/section-heading.css",
               "molecules/person-badge.css", "organisms/blockquote.css"]
REPORT_RULES = ["html {", "body {", "h1, h2, h3, .description {", "h1 {", "h2 {", "h3 {"]


def rule(path: Path, start: str) -> str:
    """One rule from a stylesheet, located by a line that STARTS with its selector."""
    lines = path.read_text().splitlines()
    i = next(n for n, ln in enumerate(lines) if ln.startswith(start))
    depth, out = 0, []
    for ln in lines[i:]:
        out.append(ln)
        depth += ln.count("{") - ln.count("}")
        if depth == 0:
            break
    return f"/* ════ bristlenose/theme/{path.relative_to(THEME)} — line {i + 1} ════ */\n" + "\n".join(out)


def theme_css() -> str:
    parts = [f"/* ════ bristlenose/theme/{f} ════ */\n" + (THEME / f).read_text() for f in THEME_FILES]
    parts += [rule(THEME / "templates" / "report.css", r) for r in REPORT_RULES]
    return "\n\n".join(parts)


HEADING_NOISE = re.compile(r"^(?:[^\w\s]+|\w(?=\s))\s*")  # a bullet, an asterisk, an icon read as one letter


def page_heading(s: Session, lines: list[dict]) -> str:
    """The page's own heading on a still: the tallest line of words in the top half of the page
    (the topmost of near-equal heights). Prices, counts and single letters are not headings."""
    x0, y0, x1, y1 = s.crop
    cands = []
    for ln in lines:
        t = HEADING_NOISE.sub("", ln["text"].strip()).strip()
        letters = sum(c.isalpha() for c in t)
        if (len(t) <= 40 and letters >= 4 and letters >= 0.6 * len(t.replace(" ", ""))
                and not re.search(r"[$£€]|\d", t) and ln["box"][1] <= y0 + 0.55 * (y1 - y0)):
            cands.append((t, ln["box"]))
    if not cands:
        return ""
    tallest = max(b[3] for _, b in cands)
    return min(((t, b) for t, b in cands if b[3] >= 0.95 * tallest), key=lambda c: c[1][1])[0]


def write_lens(out: Path, boards: list, stats: Counter) -> None:
    data = []
    for b in boards:
        tabs = []
        for tab in b["tabs"]:
            s = tab["s"]

            def quote(q: dict) -> dict:
                return {"tc": int(q["t0"]), "sent": q["sent"], "text": q["text"]}
            pins = []
            for p in tab["pins"]:
                pins.append({**quote(p["q"]), "box": s.to_crop(p["line"]["box"]), "how": p["how"],
                             "phrase": p["phrase"], "line": p["line"]["text"], "score": p["score"],
                             "elsewhere": {k: {**v, "box": next(o["s"] for o in b["tabs"] if o["s"].tag == k)
                                               .to_crop(v["box"])} for k, v in p.get("elsewhere", {}).items()}})
            tabs.append({"tag": s.tag, "code": s.code, "name": s.name, "t": int(tab["t"]),
                         "heading": page_heading(s, tab["lines"]),
                         "src": s.frame_b64(tab["t"], 1600, cropped=True),
                         "thumb": s.frame_b64(tab["t"], 240, cropped=True), "pins": pins,
                         "loose": [quote(q) for q in tab["qs"] if not any(p["q"] is q for p in tab["pins"])]})
        tabs.sort(key=lambda t: t["code"])
        data.append({"name": b["tp"].split(":", 1)[-1], "tabs": tabs})
    meta = {"placed": stats["quotes"], "words": stats["anchored_words"], "meaning": stats["anchored_meaning"]}
    blob = json.dumps({"boards": data, "meta": meta}, ensure_ascii=False)
    blob = blob.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    page = (HERE / "screens_lens.html").read_text()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page.replace("/*THEME*/", theme_css()).replace("/*DATA*/null", blob))


TEMPLATE = (Path(__file__).parent / "screens_board.html").read_text() if (Path(__file__).parent / "screens_board.html").exists() else ""

if __name__ == "__main__":
    main()
