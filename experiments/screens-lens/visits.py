"""Cut a session's dense screen-text sweep into visits, and read each visit's identity signals.

    <venv>/bin/python experiments/screens-lens/visits.py <private screen-text dir>/<tag> [--sheets]

Input is the screen-text spike's dense sweep: ocr/vision_accurate-dense.json (Apple Vision accurate on
one frame every 2 s, frame n at (n-1)*2 s) and dense/<n>.jpg. Output, private, beside the input:
screens/visits.json, and with --sheets numbered contact sheets for hand-labelling.

Per frame:
- **share or not.** A frame is a share frame when the share area (left of the video filmstrip) holds at
  least 8 OCR lines or an address-bar URL. Call-only stretches (gallery view) have no screen.
- **address-bar URL**: an OCR line in the top 15% of the share area that looks like a host/path.
  A URL at the bottom of the window is the browser's link-hover preview, kept apart as `hover`.
- **content lines**: folded lines in the share area below the browser chrome, with the screen-text
  doc's word-at-position stickiness rule applied (a word at the same 2% place on half the share frames
  is chrome).
- **dHash**: a 64-bit difference hash of the share area at 9x8, grey.

A **visit** is a run of share frames whose content-line set stays within Jaccard 0.6 of the visit's
first kept frame (the screen-text doc's text-diff rule), so a new visit starts when the text visibly
changes. Prints aggregates only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parents[1] / "screen-text"))
from score import fold  # noqa: E402

STEP = 2.0
SHARE_X = 0.865          # filmstrip starts right of this in both Teams layouts measured
CHROME_Y = 0.14          # browser chrome (tabs, address bar, bookmarks) above this
JACCARD = 0.6
HOST = re.compile(r"((?:[a-z0-9-]+\.)+(?:com|co\.uk|de|org|net|io|app|uk|eu|fr|es|it)(?:/[^\s]*)?)", re.I)


def url_norm(text: str) -> dict | None:
    # The address bar is one token (a leading favicon or lock glyph aside). A bookmark title that
    # names a host ("Bookfeed.io - Favourite Authors") is not an address, measured on the UK session.
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
    path, _, _query = path.partition("?")
    host, _, p = path.partition("/")
    p = "/" + p.rstrip("/")
    # template: product slugs and long digit runs become placeholders
    tmpl = re.sub(r"/p/[^/]+", "/p/*", p)
    tmpl = re.sub(r"\d{4,}", "#", tmpl)
    frag_route = re.sub(r"\d{4,}", "#", frag.split("?")[0]) if frag else ""
    return {"raw_host": host, "page": host + p, "template": host + tmpl, "frag": frag_route}


def dhash(img: Image.Image) -> int:
    g = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    px = list(g.tobytes())
    bits = 0
    for r in range(8):
        for c in range(8):
            bits = (bits << 1) | (px[r * 9 + c] > px[r * 9 + c + 1])
    return bits


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--sheets", action="store_true")
    args = ap.parse_args()
    ocr = json.loads((args.root / "ocr" / "vision_accurate-dense.json").read_text())
    names = sorted(ocr)
    frames = []
    for i, name in enumerate(names):
        lines = [ln for ln in ocr[name]["lines"] if ln["conf"] >= 0.5]
        share = [ln for ln in lines if ln["box"][0] < SHARE_X]
        addr, hover = None, None
        for ln in share:
            u = url_norm(ln["text"])
            if not u:
                continue
            y = ln["box"][1]
            if y < 0.15 and "cookies" not in ln["text"].lower() and (addr is None or len(u["page"]) > len(addr["page"])):
                addr = u
            elif y > 0.9:
                hover = u
        frames.append({"i": i, "t": i * STEP, "name": name, "share": share, "addr": addr, "hover": hover})
    for f in frames:
        f["is_share"] = len(f["share"]) >= 8 or f["addr"] is not None

    # word-at-position stickiness over share frames (the screen-text doc, §3.5 item 3)
    sf = [f for f in frames if f["is_share"]]
    place = Counter()
    for f in sf:
        seen = set()
        for ln in f["share"]:
            x, y, w, h = ln["box"]
            words = fold(ln["text"]).split()
            for k, wd in enumerate(words):
                cx = x + w * (k + 0.5) / max(len(words), 1)
                seen.add((wd, int(cx * 50), int(y * 50)))
        place.update(seen)
    sticky = {k for k, c in place.items() if c >= 0.5 * len(sf)}

    def is_sticky(wd: str, cx: float, y: float) -> bool:
        bx, by = int(cx * 50), int(y * 50)
        return any((wd, bx + dx, by + dy) in sticky for dx in (-1, 0, 1) for dy in (-1, 0, 1))

    for f in frames:
        content = []
        for ln in f["share"]:
            x, y, w, h = ln["box"]
            if y < CHROME_Y:
                continue
            words = fold(ln["text"]).split()
            kept = [wd for k, wd in enumerate(words)
                    if not is_sticky(wd, x + w * (k + 0.5) / max(len(words), 1), y)]
            s = " ".join(kept)
            if len(s) >= 3 and re.search(r"[a-z]", s):
                content.append({"text": s, "y": y, "h": h, "x": x})
        f["content"] = content

    # visits
    visits, cur, anchor = [], None, None
    for f in frames:
        if not f["is_share"]:
            if cur:
                visits.append(cur)
            cur, anchor = None, None
            continue
        body = {c["text"] for c in f["content"]}
        if cur is None or (body | anchor and len(body & anchor) / len(body | anchor) < JACCARD):
            if cur:
                visits.append(cur)
            cur, anchor = {"frames": []}, body
        cur["frames"].append(f["i"])
    if cur:
        visits.append(cur)

    root_img = args.root / "dense"
    out = []
    for v, vis in enumerate(visits):
        fr = [frames[i] for i in vis["frames"]]
        mid = fr[len(fr) // 2]
        lines = Counter(c["text"] for f in fr for c in f["content"])
        tokens = Counter(w for f in fr for c in f["content"] for w in c["text"].split() if len(w) >= 3)
        # heading: tallest content line in the frame nearest the middle, upper 60% of the share area
        cands = [c for c in mid["content"] if c["y"] < 0.6 and len(c["text"]) >= 4]
        head = max(cands, key=lambda c: c["h"])["text"] if cands else ""
        addrs = Counter(f["addr"]["page"] for f in fr if f["addr"])
        tmpls = Counter(f["addr"]["template"] for f in fr if f["addr"])
        frags = Counter(f["addr"]["frag"] for f in fr if f["addr"])
        hovers = [f["hover"]["page"] for f in fr if f["hover"]]
        hashes = []
        for f in (fr[0], mid, fr[-1]):
            im = Image.open(root_img / f["name"])
            W, H = im.size
            hashes.append(dhash(im.crop((0, int(H * CHROME_Y), int(W * SHARE_X), int(H * 0.97)))))
        out.append({"v": v, "t0": fr[0]["t"], "t1": fr[-1]["t"] + STEP, "n": len(fr), "mid": mid["name"],
                    "lines": sorted(lines), "tokens": sorted(tokens), "head": head,
                    "page": addrs.most_common(1)[0][0] if addrs else None,
                    "template": tmpls.most_common(1)[0][0] if tmpls else None,
                    "frag": frags.most_common(1)[0][0] if frags else None,
                    "hover": hovers[-1] if hovers else None, "dhash": hashes,
                    "first": [[c["text"], round(c["x"], 3), round(c["y"], 3), round(c["h"], 4)] for c in fr[0]["content"]],
                    "last": [[c["text"], round(c["x"], 3), round(c["y"], 3), round(c["h"], 4)] for c in fr[-1]["content"]]})
    (args.root / "screens").mkdir(exist_ok=True)
    (args.root / "screens" / "visits.json").write_text(json.dumps(out, ensure_ascii=False, indent=0))

    durs = [v["t1"] - v["t0"] for v in out]
    print(json.dumps({
        "frames": len(frames), "share_frames": len(sf), "share_min": round(len(sf) * STEP / 60, 1),
        "frames_with_addr_url": sum(1 for f in sf if f["addr"]),
        "frames_with_hover_url": sum(1 for f in sf if f["hover"]),
        "sticky_word_places": len(sticky), "visits": len(out),
        "visit_s_median": sorted(durs)[len(durs) // 2] if durs else 0,
        "visits_ge_6s": sum(1 for d in durs if d >= 6),
        "distinct_pages": len({v["page"] for v in out if v["page"]}),
        "distinct_templates": len({v["template"] for v in out if v["template"]}),
        "distinct_page_frag": len({(v["page"], v["frag"]) for v in out if v["page"]}),
        "visits_without_url": sum(1 for v in out if not v["page"]),
    }, indent=1))

    if args.sheets:
        per, cols, tw, th = 20, 5, 384, 216
        for s in range(0, len(out), per):
            chunk = out[s:s + per]
            sheet = Image.new("RGB", (cols * tw, ((len(chunk) + cols - 1) // cols) * (th + 18)), "white")
            d = ImageDraw.Draw(sheet)
            for k, v in enumerate(chunk):
                im = Image.open(root_img / v["mid"]).convert("RGB")
                W, H = im.size
                im = im.crop((0, 0, int(W * SHARE_X), H)).resize((tw, th))
                x, y = (k % cols) * tw, (k // cols) * (th + 18)
                sheet.paste(im, (x, y + 18))
                d.text((x + 4, y + 2), f"v{v['v']}  {int(v['t0'])//60}:{int(v['t0'])%60:02d}  {int(v['t1']-v['t0'])}s", fill="black")
            sheet.save(args.root / "screens" / f"sheet-{s // per:02d}.jpg", quality=80)


if __name__ == "__main__":
    main()
