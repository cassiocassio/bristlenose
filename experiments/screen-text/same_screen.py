"""Are two participants looking at the same screen? Measure the signals before choosing a rule.

    <ocr-venv>/bin/python experiments/screen-text/same_screen.py <config.json> [--show] [--dump <private>.json]

screens_board.py keys a screen by its address-bar URL with the product and category slug masked
(`/p/*`, `/cat/*`), which puts every category page into one screen: a UK "Jars & tins" page and a
German welcome banner were stacked as one screen and their quotes combined. That is a template,
not a screen. This script asks what else distinguishes "the same page" from "the same kind of page"
and from "a different page", using only what the screen-text index already holds.

A *view* is a maximal run of samples with one exact address (path and fragment, slug kept) or, where
the address bar shows only the host (Safari), one tab title. For each view:

- **words**: the folded words of its content lines (non-sticky, inside the web page, not the URL),
  minus the session's site furniture (words on at least half the session's views).
- **lines**: the folded content lines themselves.
- **layout**: an 8×12 grid of where text sits on the page — language-blind.
- **picture**: a 32×20 greyscale thumbnail of the page at the view's middle — language-blind.
- **meaning**: LaBSE embeddings of its lines, compared as a set (best match per line, averaged) —
  language-blind for the words, and the only signal that can say a German page and an English page
  carry the same text.

Pairs are labelled where the label is not a judgement: within one session, two views with the same
exact address are the SAME page; same template but different address is SAME KIND (two products,
two categories); different templates are DIFFERENT. Across sessions there is no such oracle, so the
script prints the scores for every cross pair on a shared template and the user's eye is the label.

Aggregates only by default. --show prints view keys and top words (screen text from participants'
sessions: private, never paste into tracked files).
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from score import fold  # noqa: E402
from screens_board import Session, id_key, template, title_norm, title_suffix, url_norm  # noqa: E402

GRID = (12, 8)  # columns, rows
def views_of(s: Session) -> list[dict]:
    """Maximal runs of one exact address (or one tab title where the bar shows only the host)."""
    urls, titles = [], []
    for e in s.eps:
        x, y, w, h = e["box"]
        if y > 0.16 or x > 0.865:
            continue
        u = url_norm(e["text"])
        if u and y <= 0.15:
            urls.append((e, u))
        elif not e["sticky"] and title_norm(e["text"]):
            titles.append((e, title_norm(e["text"]), title_suffix(e["text"])))
    by_sfx: dict[str, set] = defaultdict(set)
    for _, tt, sx in titles:
        by_sfx[sx].add(tt)
    sfx = max(by_sfx, key=lambda k: len(by_sfx[k]), default=None)
    titles = [(e, tt) for e, tt, sx in titles if sx == sfx and len(by_sfx[sx]) >= 2]
    has_paths = sum(1 for _, u in urls if u["path"] != "/" or u["frag"]) >= 0.2 * max(len(urls), 1)
    samples = sorted({r[0] + k * s.every for e, _ in urls + titles for r in e["runs"]
                      for k in range(int((r[1] - r[0]) / s.every) + 1)})
    out: list[dict] = []
    for t in samples:
        def on(e): return any(r[0] <= t <= r[1] for r in e["runs"])
        if has_paths:
            us = [u for e, u in urls if on(e)]
            if not us:
                continue
            u = Counter((x["path"], x["frag"]) for x in us).most_common(1)[0][0]
            key, tpl = "url:" + u[0] + ("#" + u[1] if u[1] else ""), "url:" + template(*u)
            idk = "url:" + id_key(*u)
        else:
            tts = sorted(((min(r[0] for r in e["runs"] if r[0] <= t), tt) for e, tt in titles if on(e)), reverse=True)
            if not tts:
                continue
            key = tpl = idk = "title:" + tts[0][1]
        if out and out[-1]["key"] == key and t - out[-1]["t1"] <= 3 * s.every:
            out[-1]["t1"] = t
        else:
            out.append({"key": key, "tpl": tpl, "idk": idk, "t0": t, "t1": t})
    return [v for v in out if v["t1"] - v["t0"] >= s.every]   # at least two samples: a glimpse is not a view


def content_lines(s: Session, v: dict) -> list[dict]:
    return [e for e in s.eps if not e["sticky"] and not url_norm(e["text"]) and s.inside(e["box"])
            and any(r[0] <= v["t1"] + s.every and r[1] >= v["t0"] for r in e["runs"])]


def heading_of(s: Session, lines: list[dict]) -> str:
    """The page's own heading: the tallest line of words in the top half of the page, where only the
    line seen longest among near-equal heights wins (a heading stays on screen; a carousel does not)."""
    x0, y0, x1, y1 = s.crop
    c = [e for e in lines if sum(ch.isalpha() for ch in e["text"]) >= 4 and len(e["text"]) <= 40
         and not re.search(r"[$£€]|\d", e["text"]) and e["box"][1] <= y0 + 0.55 * (y1 - y0)]
    if not c:
        return ""
    tallest = max(e["box"][3] for e in c)
    top = [e for e in c if e["box"][3] >= 0.9 * tallest]
    return fold(max(top, key=lambda e: sum(r[1] - r[0] for r in e["runs"]))["text"])


def layout(s: Session, lines: list[dict]) -> np.ndarray:
    x0, y0, x1, y1 = s.crop
    g = np.zeros(GRID[::-1], bool)
    for ln in lines:
        x, y, w, h = s.to_crop(ln["box"])
        for cx in range(int(x * GRID[0]), min(GRID[0], int((x + w) * GRID[0]) + 1)):
            g[min(GRID[1] - 1, max(0, int((y + h / 2) * GRID[1]))), max(0, cx)] = True
    return g


def picture(s: Session, t: float) -> np.ndarray:
    x0, y0, x1, y1 = s.crop
    vf = f"crop=iw*{x1 - x0:.4f}:ih*{y1 - y0:.4f}:iw*{x0:.4f}:ih*{y0:.4f},scale=32:20,format=gray"
    raw = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(s.video),
                          "-frames:v", "1", "-vf", vf, "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.uint8).astype(float)
    return (a - a.mean()) / (a.std() + 1e-6)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("config", type=Path)
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--dump", type=Path)
    args = ap.parse_args()
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("sentence-transformers/LaBSE")

    allv = []
    for cfg in json.loads(args.config.read_text()):
        s = Session(cfg)
        vs = views_of(s)
        df = Counter(w for v in vs for w in {w for e in content_lines(s, v) for w in fold(e["text"]).split()})
        chrome = {w for w, c in df.items() if c >= 0.5 * len(vs)}
        for v in vs:
            lines = content_lines(s, v)
            texts = sorted({fold(e["text"]) for e in lines if len(fold(e["text"])) >= 4})
            v.update(s=s, lines=set(texts), heading=heading_of(s, lines),
                     words={w for t in texts for w in t.split() if len(w) >= 3 and not w.isdigit() and w not in chrome},
                     grid=layout(s, lines), pic=picture(s, (v["t0"] + v["t1"]) / 2),
                     emb=model.encode(texts[:80], normalize_embeddings=True) if texts else None)
            allv.append(v)
        print(f"{cfg['label']}: {len(vs)} views, {len({v['key'] for v in vs})} distinct addresses or titles")

    # Rarity across every view of every session: a word on a quarter of all pages is the site's
    # template vocabulary ("compare", "add to bag"), not evidence that two pages are one.
    vdf = Counter(w for v in allv for w in v["words"])
    n_views = len(allv)
    idf = {w: math.log(n_views / c) for w, c in vdf.items() if c <= 0.25 * n_views}

    def rare_overlap(wa: set, wb: set) -> float:
        a, b = {w for w in wa if w in idf}, {w for w in wb if w in idf}
        small = a if sum(idf[w] for w in a) <= sum(idf[w] for w in b) else b
        return sum(idf[w] for w in a & b) / max(1e-9, sum(idf[w] for w in small))

    def scores(a: dict, b: dict) -> dict:
        wa, wb = a["words"], b["words"]
        ga, gb = a["grid"], b["grid"]
        sem = None
        if a["emb"] is not None and b["emb"] is not None:
            m = a["emb"] @ b["emb"].T
            sem = float((m.max(1).mean() + m.max(0).mean()) / 2)
        return {
            "words": len(wa & wb) / max(1, min(len(wa), len(wb))),
            "rare": rare_overlap(wa, wb),
            "idkey": a["idk"] == b["idk"],
            "heading": bool(a["heading"]) and a["heading"] == b["heading"],
            "lines": len(a["lines"] & b["lines"]) / max(1, min(len(a["lines"]), len(b["lines"]))),
            "layout": float((ga & gb).sum() / max(1, (ga | gb).sum())),
            "picture": float(np.mean(a["pic"] * b["pic"])),
            "meaning": sem,
        }

    rows = []
    for a, b in combinations(allv, 2):
        same_session = a["s"] is b["s"]
        if same_session and a["key"] == b["key"]:
            label = "same page"
        elif same_session and a["tpl"] == b["tpl"]:
            label = "same kind"
        elif same_session:
            label = "different"
        else:
            label = "cross: " + ("same template" if a["tpl"] == b["tpl"] else "other")
        rows.append({"label": label, "a": a["s"].tag, "b": b["s"].tag, "ka": a["key"], "kb": b["key"], **scores(a, b)})

    print("\nWithin one session, by label (median [10th–90th percentile]):")
    for label in ("same page", "same kind", "different"):
        rs = [r for r in rows if r["label"] == label]
        if not rs:
            continue
        cells = []
        for m in ("words", "rare", "lines", "meaning"):
            xs = np.array([r[m] for r in rs if r[m] is not None])
            cells.append(f"{m} {np.median(xs):.2f} [{np.percentile(xs, 10):.2f}–{np.percentile(xs, 90):.2f}]")
        print(f"  {label:<10} n={len(rs):<4} " + "  ".join(cells))

    print("\nThe page heading as a key, within one session (no address used):")
    for label in ("same page", "same kind", "different"):
        rs = [r for r in rows if r["label"] == label]
        print(f"  {label:<10} headings equal on {sum(r['heading'] for r in rs)}/{len(rs)}")
    xs = [r for r in rows if r["label"].startswith("cross")]
    print(f"  across sessions: headings equal on {sum(r['heading'] for r in xs)}/{len(xs)} pairs"
          + ("".join(f"\n    {r['a']}×{r['b']} {r['ka']} | {r['kb']}" for r in xs if r["heading"]) if args.show else ""))
    print("\nAcross sessions, pairs on one template (the cases the board stacked):")
    for r in sorted((r for r in rows if r["label"] == "cross: same template"), key=lambda r: (r["ka"], -r["words"])):
        tail = f"  {r['ka']} | {r['kb']}" if args.show else ""
        print(f"  {r['a']}×{r['b']}  id-key {'SAME' if r['idkey'] else 'diff'}  words {r['words']:.2f}  rare {r['rare']:.2f}  "
              f"meaning {r['meaning'] if r['meaning'] is None else round(r['meaning'], 2)}{tail}")
    print("\nAcross sessions, the twelve highest rare-word-overlap pairs on different templates:")
    for r in sorted((r for r in rows if r["label"] == "cross: other"), key=lambda r: -r["rare"])[:12]:
        tail = f"  {r['ka']} | {r['kb']}" if args.show else ""
        print(f"  {r['a']}×{r['b']}  id-key {'SAME' if r['idkey'] else 'diff'}  words {r['words']:.2f}  rare {r['rare']:.2f}  "
              f"meaning {r['meaning'] if r['meaning'] is None else round(r['meaning'], 2)}{tail}")
    if args.dump:
        args.dump.write_text(json.dumps(rows, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
