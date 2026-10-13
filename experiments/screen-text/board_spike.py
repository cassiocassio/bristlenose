"""The annotated screen: one large still with every quote pinned to the element it is about.

    python3 experiments/screen-text/board_spike.py <index.json> <quotes.json> <session_id> <video> -o <private>/board.html [--t SECONDS]

The owner's idea (13 Oct 2026): the Screens lens as a Miro board, a big screenshot with the quotes
densely arranged around the screen elements they talk about, connected directly. This prototype does
it from real data. Anchors come from anchor_spike.py's rule (a 2+ word phrase with a content word, or
a rare 6+ letter word, shared by the quote and a screen line on screen within ±4 s), with two
filters measured there: address-bar lines are never anchors (they key screens, they are not
elements), and a two-word match must hold two content words. Each quote keeps its best anchor: the
longest phrase, then the larger box.

The still is the moment (sampled every 4 s, or --t) at which the most anchored quotes have their
anchor line on screen. The still is then OCR'd itself (Vision, so run this with the scratch venv that
has pyobjc), and each anchored quote is pinned to wherever its phrase appears on the still, with a
leader line to that box, outlined in blue. The rest are listed under the board.
The page carries a participant's screen and speech: write it to the private trial-data folder.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from anchor_spike import STOP, content, matches, tc_to_s  # noqa: E402
from score import fold  # noqa: E402

WINDOW = 4.0


def is_url(text: str) -> bool:
    t = text.strip().lower()
    return t.startswith(("www.", "http")) or ".com/" in t or ".co.uk" in t and " " not in t


def good(phrase: str) -> bool:
    w = phrase.split()
    if len(w) >= 3:
        return any(content(x) for x in w)
    if len(w) == 2:
        return all(x not in STOP and len(x) >= 3 for x in w)
    return True  # a rare single word already passed anchor_spike's rarity test


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("index", type=Path)
    ap.add_argument("quotes", type=Path)
    ap.add_argument("session")
    ap.add_argument("video", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--t", type=float, default=None)
    args = ap.parse_args()
    index = json.loads(args.index.read_text())
    every = index["every"]
    eps = [e for e in index["episodes"] if not e["sticky"] and not is_url(e["text"])]
    from collections import Counter
    freq: Counter[str] = Counter()
    for e in eps:
        for w in set(fold(e["text"]).split()):
            freq[w] += 1
    rare = {w for w, c in freq.items() if c <= 3}

    def on_screen(a: float, b: float) -> list[dict]:
        return [e for e in eps if any(r[0] <= b + WINDOW and r[1] + every >= a - WINDOW for r in e["runs"])]

    quotes = [q for q in json.loads(args.quotes.read_text()) if q.get("session_id") == args.session]
    anchored = []
    for q in quotes:
        a, b = tc_to_s(q["start_timecode"]), tc_to_s(q["end_timecode"])
        text = q.get("verbatim_excerpt") or q["text"]
        ms = [(p, ln) for p, ln in matches(text, on_screen(a, b), rare) if good(p)]
        if ms:
            p, ln = max(ms, key=lambda m: (len(m[0].split()), m[1]["box"][2] * m[1]["box"][3]))
            anchored.append({"q": q, "t0": a, "text": text, "phrase": p, "line": ln})

    def visible(ln: dict, t: float) -> bool:
        return any(r[0] - 0.01 <= t <= r[1] + every for r in ln["runs"])

    from ocr_bench import vision
    read = vision(0)

    def still_ocr(t: float) -> list[dict]:
        full = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(args.video),
                               "-frames:v", "1", "-q:v", "2", "-f", "mjpeg", "-"], capture_output=True, check=True).stdout
        tmp = args.out.with_suffix(".still.jpg")
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(full)
        lines = [ln for ln in read(tmp) if ln["conf"] >= 0.5 and not is_url(ln["text"])]
        tmp.unlink()
        return lines

    def on_still(lines: list[dict]) -> int:
        texts = [" " + fold(ln["text"]) + " " for ln in lines]
        return sum(any(" " + x["phrase"] + " " in t for t in texts) for x in anchored)

    cache: dict[float, list[dict]] = {}

    def ocr_at(t: float) -> list[dict]:
        if t not in cache:
            cache[t] = still_ocr(t)
        return cache[t]

    def pins_on(t: float, pool: list[dict]) -> list[dict]:
        texts = [(" " + fold(ln["text"]) + " ", ln) for ln in ocr_at(t)]
        out = []
        for x in pool:
            hits = [ln for tx, ln in texts if " " + x["phrase"] + " " in tx]
            if hits:
                out.append(dict(x, box=max(hits, key=lambda ln: ln["box"][2] * ln["box"][3])["box"]))
        return out

    # One board per screen, greedily: the still that carries the most remaining quote phrases, then
    # the next still for whatever is left. A stand-in for the screens derivation (design-screens.md
    # §3.1), good enough to judge the board.
    boards, remaining = [], list(anchored)
    while remaining:
        cands = sorted({r[0] + k * every for x in remaining for r in x["line"]["runs"]
                        for k in range(int((r[1] - r[0]) / every) + 1)})
        if args.t is not None:
            cands = [args.t]
        best = max(cands, key=lambda t: (len(pins_on(t, remaining)), -t))
        pins = pins_on(best, remaining)
        if not pins:
            break
        boards.append((best, pins))
        ids = {id(x["q"]) for x in pins}
        remaining = [x for x in remaining if id(x["q"]) not in ids]
        if args.t is not None:
            break
    others = remaining

    def frame_b64(t: float, width: int) -> str:
        jpg = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(args.video),
                              "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "3", "-f", "mjpeg", "-"],
                             capture_output=True, check=True).stdout
        return "data:image/jpeg;base64," + base64.b64encode(jpg).decode()

    out_boards = []
    for t, pins in sorted(boards):
        out_pins = []
        for x in sorted(pins, key=lambda x: x["box"][1]):
            bx = x["box"]
            out_pins.append({"box": bx, "side": "left" if bx[0] + bx[2] / 2 < 0.5 else "right",
                             "who": x["q"].get("participant_id", ""), "tc": int(x["t0"]),
                             "sent": x["q"].get("sentiment") or "", "phrase": x["phrase"], "text": x["text"]})
        out_boards.append({"t": int(t), "src": frame_b64(t, 1600), "thumb": frame_b64(t, 240), "pins": out_pins})
    data = json.dumps({"boards": out_boards}).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    rest = "".join(f"<li><b>{html.escape(x['q'].get('participant_id',''))} {int(x['t0'])//60}:{int(x['t0'])%60:02d}</b> "
                   f"{html.escape(x['text'][:220])} <i>(“{html.escape(x['phrase'])}” not found on any chosen still)</i></li>"
                   for x in others)
    page = TEMPLATE.replace("/*DATA*/null", data).replace("<!--REST-->", rest or "<li>none</li>")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(page)
    print(f"{args.out}: {len(quotes)} quotes, {len(anchored)} anchored, {len(boards)} boards "
          f"{[len(p) for _, p in sorted(boards)]}, {len(others)} anchored but unplaced")


TEMPLATE = """<!doctype html><meta charset=utf-8><title>Screens board (private prototype)</title>
<style>
:root{--blue:#3b82f6;--ink:#1f2328;--muted:#6b7280;--bg:#f4f5f7}
body{margin:0;font:13px/1.35 -apple-system,system-ui,sans-serif;color:var(--ink);background:var(--bg)}
header{padding:12px 20px 6px;color:var(--muted)} header b{color:var(--ink)}
nav{display:flex;gap:10px;padding:8px 20px 14px;overflow-x:auto;position:sticky;top:0;background:var(--bg);z-index:5;border-bottom:1px solid #e3e5e8}
nav a{display:block;flex:0 0 auto;text-decoration:none;color:var(--muted);font-size:11px}
nav img{width:160px;display:block;border-radius:4px;border:2px solid transparent;box-shadow:0 1px 3px rgba(0,0,0,.15)}
nav a:hover img{border-color:var(--blue)} nav span{display:block;margin-top:3px}
h2{font-size:13px;color:var(--muted);font-weight:600;margin:22px 20px 8px}
.board{position:relative;display:grid;grid-template-columns:260px minmax(0,1fr) 260px;gap:0 18px;padding:0 20px 10px}
.col{position:relative} .shot{position:relative} .shot img{width:100%;display:block;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.18)}
.hl{position:absolute;border:2px solid var(--blue);border-radius:4px;background:rgba(59,130,246,.10);box-shadow:0 0 0 3px rgba(59,130,246,.18)}
.note{position:absolute;left:0;right:0;background:#fff8c5;border-left:3px solid #e3b341;border-radius:4px;padding:6px 8px;box-shadow:0 1px 3px rgba(0,0,0,.15);font-size:12px}
.note.neg{border-left-color:#e5534b}.note.pos{border-left-color:#3fb950}
.note .meta{color:var(--muted);font-size:11px;margin-bottom:2px}
.note mark{background:rgba(59,130,246,.22);color:inherit;border-radius:2px;padding:0 1px}
svg.lines{position:absolute;inset:0;pointer-events:none;overflow:visible}
section.rest{padding:0 20px 30px;color:var(--muted)} section.rest li{margin:4px 0}
</style>
<header><b>Screens board</b> — private prototype from a real session · each screen a still, each quote pinned to the screen text it reads or mentions</header>
<nav id=nav></nav><div id=boards></div>
<section class=rest><h2>Anchored, but not placed</h2><ul><!--REST--></ul></section>
<script>
const D=/*DATA*/null;
function esc(s){return s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function mmss(t){return Math.floor(t/60)+':'+String(t%60).padStart(2,'0')}
function markup(text,phrase){const t=esc(text.length>260?text.slice(0,257)+'…':text);const w=phrase.split(' ').filter(Boolean);if(!w.length)return t;
 const re=new RegExp(w.map(x=>x.replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&')).join('[^\\\\w]+'),'i');return t.replace(re,m=>'<mark>'+m+'</mark>')}
const nav=document.getElementById('nav'),host=document.getElementById('boards');
D.boards.forEach((b,i)=>{
 nav.insertAdjacentHTML('beforeend','<a href="#b'+i+'"><img src="'+b.thumb+'"><span>'+mmss(b.t)+' · '+b.pins.length+' quote'+(b.pins.length>1?'s':'')+'</span></a>');
 host.insertAdjacentHTML('beforeend','<h2 id="b'+i+'">Screen at '+mmss(b.t)+'</h2><div class=board><div class=col></div><div class=shot><img src="'+b.src+'"></div><div class=col></div><svg class=lines></svg></div>');
});
function layout(){
 [...host.querySelectorAll('.board')].forEach((board,bi)=>{
  const b=D.boards[bi],[L,S,R]=board.querySelectorAll('.col,.shot'),img=S.querySelector('img'),svg=board.querySelector('svg');
  const cols=board.querySelectorAll('.col');const Lc=cols[0],Rc=cols[1];
  S.querySelectorAll('.hl').forEach(n=>n.remove());Lc.innerHTML='';Rc.innerHTML='';svg.innerHTML='';
  const W=img.clientWidth,H=img.clientHeight;if(!W)return;const bb=board.getBoundingClientRect(),sb=S.getBoundingClientRect();const used={left:[],right:[]};
  for(const p of b.pins){const [x,y,w,h]=p.box;const hl=document.createElement('div');hl.className='hl';
   Object.assign(hl.style,{left:(x*W-3)+'px',top:(y*H-3)+'px',width:(w*W+6)+'px',height:(h*H+6)+'px'});S.appendChild(hl);
   const col=p.side==='left'?Lc:Rc;const n=document.createElement('div');
   n.className='note '+(/(frustrat|confus|neg|annoy|disappoint)/i.test(p.sent)?'neg':/(delight|satisf|pos|happy)/i.test(p.sent)?'pos':'');
   n.innerHTML='<div class=meta>'+esc(p.who)+' · '+mmss(p.tc)+(p.sent?' · '+esc(p.sent):'')+'</div>'+markup(p.text,p.phrase);col.appendChild(n);
   let top=Math.max(0,y*H+h*H/2-30);for(const [a,c] of used[p.side]){if(top<c&&top+10>a-10)top=c+6}
   n.style.top=top+'px';used[p.side].push([top,top+n.offsetHeight]);const cb=col.getBoundingClientRect();
   const nx=p.side==='left'?cb.right-bb.left:cb.left-bb.left,ny=top+18+(cb.top-bb.top);
   const hx=sb.left-bb.left+(p.side==='left'?x*W:(x+w)*W),hy=sb.top-bb.top+(y+h/2)*H;
   svg.insertAdjacentHTML('beforeend','<path d="M'+nx+','+ny+' C'+(nx+(hx-nx)/2)+','+ny+' '+(nx+(hx-nx)/2)+','+hy+' '+hx+','+hy+'" stroke="#3b82f6" stroke-width="1.5" fill="none" opacity=".7"/><circle cx="'+hx+'" cy="'+hy+'" r="3" fill="#3b82f6"/>')}
  const m=Math.max(H,...used.left.map(u=>u[1]),...used.right.map(u=>u[1]));Lc.style.height=Rc.style.height=m+'px'});
}
Promise.all([...document.images].map(i=>i.complete?1:new Promise(r=>i.onload=r))).then(layout);addEventListener('resize',layout);
</script>"""


if __name__ == "__main__":
    main()
