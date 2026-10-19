"""Build docs/mockups/discussion-quote-parity.html — Discussion lens quotes that work like every other quote.

A playable mockup of the Discussion lens with the Quotes lens's own card (QuoteCard) in place of the
lens's read-only one: the timecode opens the player, the speaker badge opens the transcript at that
moment, and the card stars, hides, tags, edits, drops its sentiment and takes AutoCode proposals.
The moderator's question rows keep their own shape and gain only the two links.

What is shipped and inlined verbatim: the theme (load_default_css(), the concatenation serve and
export use), frontend/src/islands/discussion/discussion.css, the lens's markup (DiscussionLens.tsx:
session bar, strip-tier navigator, All view with lead-ins, ask rows), and the card's markup as the
live SPA renders it (QuoteCard, TimecodeLink, PersonBadge, Badge, TagInput, Counter — the DOM
captured for docs/mockups/tag-hang-catalogue.html). What is proposed sits in ONE <style> block,
every rule commented PROPOSED. Every word inside the frame is a shipped en locale string.

The cast and the conversation are build.py's eight-session study, retimed so each session runs
forward in guide order and every quote has its own report id (q-<code>-<seconds>).

    .venv/bin/python experiments/discussion-all-sessions/quote_parity.py
"""

from __future__ import annotations

import json
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import build as B  # noqa: E402  (the overnight mockup's study data)

from bristlenose.stages.s12_render.theme_assets import load_default_css  # noqa: E402

OUT = ROOT / "docs/mockups/discussion-quote-parity.html"
DISCUSSION_CSS = ROOT / "frontend/src/islands/discussion/discussion.css"

SESSIONS = B.EIGHT

# The UXR codebook's tags (bristlenose/server/codebook/uxr.yaml), with the colour each takes
# (getTagBg: the set's slot by the tag's place in its group).
VOCAB = [
    ("Behaviour", "ux", ["workaround", "habit", "avoidance", "say-do gap", "error recovery", "exploration"]),
    ("Pain points", "emo", ["friction", "dead end", "abandonment", "lost my place"]),
    ("Needs and desires", "emo", ["unmet need", "feature request", "desire path", "expectation mismatch"]),
    ("Mental models", "task", ["mental model", "assumption", "prior experience", "misconception"]),
    ("Motivation", "task", ["goal", "trigger", "barrier", "job-to-be-done"]),
    ("Emotion and trust", "trust", ["anxiety", "trust", "distrust"]),
]
SLOTS = {"ux": 5, "emo": 6, "task": 5, "trust": 5}
SENTIMENTS = ["frustration", "confusion", "doubt", "surprise", "satisfaction", "delight", "confidence"]


def h(s: str) -> int:
    return zlib.crc32(s.encode("utf-8"))


def mmss(sec: int) -> str:
    return f"{sec // 60:02d}:{sec % 60:02d}"


def secs(dur: str) -> int:
    m, s = dur.split(":")
    return int(m) * 60 + int(s)


def study() -> dict:
    vocab = [{"group": g, "set": cs, "tags": [{"name": t, "bg": f"var(--bn-{cs}-{i % SLOTS[cs] + 1}-bg)"}
                                              for i, t in enumerate(tags)]} for g, cs, tags in VOCAB]
    flat = [t for g in vocab for t in g["tags"]]
    sessions = [{"id": f"s{s.n}", "n": s.n, "people": [{"code": p.code, "name": p.name} for p in s.people],
                 "duration": s.duration, "seconds": secs(s.duration), "mod": s.mod} for s in SESSIONS]
    sections, turns, quotes = [], [], []
    clock = {s.n: 28 for s in SESSIONS}
    for si, (title, items) in enumerate(B.SECTIONS):
        sec_items = []
        for it in items:
            asked = B.asked(it, SESSIONS)
            sec_items.append({"id": it.id, "text": it.text, "mark": it.mark, "sessions": [f"s{n}" for n in asked]})
            for s in SESSIONS:
                if s.n not in asked:
                    continue
                for _t, wording, answers in B.said(s, it.id):
                    t = clock[s.n]
                    tid = f"s{s.n}@{mmss(t)}"
                    turns.append({"id": tid, "session": f"s{s.n}", "item": it.id, "sec": t, "text": wording,
                                  "speaker": s.mod})
                    t += 14 + len(wording) // 9
                    for _qt, code, text in answers:
                        code = code or s.people[0].code
                        qid = f"q-{code}-{t}"
                        k = h(qid + text)
                        sent = SENTIMENTS[k % len(SENTIMENTS)] if k % 10 < 7 else None
                        tags = [flat[(k >> 4) % len(flat)]["name"]] if k % 5 == 0 else []
                        prop = []
                        if k % 3 == 0:
                            cand = flat[(k >> 9) % len(flat)]["name"]
                            if cand not in tags:
                                prop = [cand]
                        quotes.append({"id": qid, "session": f"s{s.n}", "participant": code, "sec": t,
                                       "end": t + max(4, len(text) // 14), "text": text, "turn": tid,
                                       "sentiment": sent, "tags": tags, "proposed": prop})
                        t += 9 + len(text) // 6
                    clock[s.n] = t + 35
        sections.append({"id": f"sec{si}", "title": title, "items": sec_items})
    # A starting state, so the first look shows every kind of card: two stars, one hidden.
    state = {"starred": [quotes[1]["id"], quotes[9]["id"]], "hidden": [quotes[4]["id"]]}
    total = sum(s["seconds"] for s in sessions)
    return {"sessions": sessions, "sections": sections, "turns": turns, "quotes": quotes, "vocab": vocab,
            "state": state, "total": f"{total // 3600}h {total % 3600 // 60}m"}


PROPOSED_CSS = r"""
/* ════ PROPOSED — what the lens adds to host the shared card. Nothing below is shipped. ════ */

/* PROPOSED: each card sits in a wrapper the lens owns (as .screens-card does on Screens). The
   wrapper carries the lens's own marks (data-for, the question it answers) so QuoteCard's root
   stays QuoteCard's; and it is the positioned box the star and hide buttons hang from. */
.dl-card { position: relative; scroll-margin-top: calc(var(--dl-bar-h, 0px) + var(--bn-space-md)); }
/* PROPOSED: the same right-hand room the Quotes lens gives its cards (.quote-group .quote-card),
   so the star and hide buttons never sit on the words. Ask rows take it too, so a question and its
   answers keep one measure. */
.dl-group blockquote.quote-card { padding-right: 4.5rem; }
.dl-group .dl-card + .dl-card blockquote.quote-card { margin-top: 0.8rem; }
.dl-group blockquote.dl-ask + .dl-card blockquote.quote-card { margin-top: var(--bn-space-xs); }

/* PROPOSED: where the hidden-quotes counter (the shipped Counter) lands, one rule per option. */
/* (a) beside the question — All: the question's heading becomes the Quotes lens's group header. */
.dl-content .dl-item > .bn-group-header { max-width: var(--bn-max-width); margin-top: var(--bn-space-lg); }
.dl-content .dl-item > .bn-group-header > h3 { margin: 0; overflow-wrap: anywhere; }
.dl-content .dl-item > .bn-group-header + .dl-group { border-top-color: transparent; margin-top: 0; padding-top: var(--bn-space-xs); }
/* (a, in a session) and (b) under a session's answers: the counter ends the block, right-aligned. */
.dl-hidden-foot { display: flex; justify-content: flex-end; max-width: var(--bn-max-width); margin-top: var(--bn-space-xs); }
/* (c) one for the lens: in the section heading's own action slot (SectionHeading's `action`). */

/* PROPOSED (decided 19 Oct 2026): a question with no quote to show — not asked, asked with nothing
   quotable, or every answer hidden — is its heading alone, in the guide's grey. The heading stays
   because the guide's row lands on it and the hidden-quotes counter hangs from it. */
.dl-content .dl-item.empty > h3,
.dl-content .dl-item.empty > .bn-group-header > h3 { color: var(--bn-colour-muted); }
"""

CHROME_CSS = r"""
/* ── mockup chrome: m- prefixed, never inside the frame ── */
body.m-page { margin: 0; padding: 28px 24px 80px; background: light-dark(#e9e9ec, #0d0d0f);
  font-family: var(--bn-font-body); color: var(--bn-colour-text); }
.m-title { font-size: 22px; margin: 0 0 4px; }
.m-sub { color: var(--bn-colour-muted); margin: 0 0 14px; max-width: 1000px; line-height: 1.5; }
.m-keyrow { display: flex; gap: 12px; margin: 0 0 16px; font: 12px var(--bn-font-mono); }
.m-keyrow span { padding: 4px 10px; border-radius: 6px; }
.m-k-art { background: var(--bn-colour-bg); border: 1px solid var(--bn-colour-border); }
.m-k-com, .m-note, .m-ctl { background: repeating-linear-gradient(135deg, light-dark(#fff8e1,#2a2618) 0 8px, light-dark(#fff3cd,#302a1a) 8px 16px);
  border-left: 3px solid #d4a017; color: light-dark(#3a3000, #eadfb8); }
.m-ctl { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px 22px; padding: 10px 14px;
  margin: 0 0 14px; max-width: 1280px; box-sizing: border-box; font-size: 12.5px; }
.m-ctl fieldset { border: 0; margin: 0; padding: 0; min-width: 0; }
.m-ctl legend { font: 600 10px var(--bn-font-mono); letter-spacing: .08em; text-transform: uppercase; opacity: .75; padding: 0; margin-bottom: 3px; }
.m-ctl label { display: flex; gap: 6px; align-items: baseline; line-height: 1.45; cursor: pointer; }
.m-frame { margin: 0; width: 1280px; max-width: 100%; }
.m-chrome { display: flex; gap: 10px; align-items: center; padding: 6px 10px; font: 11px var(--bn-font-mono);
  background: light-dark(#dcdce0, #26262a); color: light-dark(#444, #bbb); border-radius: 8px 8px 0 0; min-height: 16px; }
.m-dots { display: inline-flex; gap: 4px; } .m-dots i { width: 8px; height: 8px; border-radius: 50%; background: light-dark(#bbb,#555); }
.m-status { margin-left: auto; color: light-dark(#8a5a00, #e0b050); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 70%; }
.m-window { --m-win-h: 780px; height: var(--m-win-h); background: var(--bn-colour-bg); color: var(--bn-colour-text);
  overflow: auto; position: relative; border: 1px solid light-dark(#cfcfd4, #333); border-top: 0; border-radius: 0 0 8px 8px; }
.m-note { max-width: 1280px; box-sizing: border-box; margin: 14px 0 0; padding: 10px 16px; font-size: 13px; line-height: 1.55; }
.m-note-label { display: block; font: 600 10px var(--bn-font-mono); letter-spacing: .08em; text-transform: uppercase; margin-bottom: 4px; opacity: .7; }
.m-note h3 { font-size: 13px; margin: 12px 0 4px; } .m-note h3:first-of-type { margin-top: 4px; }
.m-note p { margin: 0 0 6px; } .m-note ul { margin: 0 0 6px; padding-left: 18px; } .m-note li { margin: 2px 0; }
.m-note code, .m-note kbd { font: 12px var(--bn-font-mono); }
.m-note kbd { padding: 0 4px; border: 1px solid light-dark(#d9c98a,#4a4228); border-radius: 3px; }
.m-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 0 28px; }

/* Frame plumbing — the real sticky panes, pinned to the frame instead of the window, and every
   card painted (content-visibility skips off-screen ones, which a mockup must not). Mockup-only. */
.m-window .dl-lens { margin: 0; min-height: 100%; }
.m-window .dl-lens .dl-nav, .m-window .dl-lens .dl-gut { height: calc(var(--m-win-h) - var(--dl-bar-h, 0px)); }
.m-window .dl-lens .dl-nav { scrollbar-width: thin; }
.m-window .dl-lens[data-all="true"] .dl-content .dl-group { content-visibility: visible; }
"""

SCRIPT = r"""
const D = __DATA__;
const NS = "http://www.w3.org/2000/svg";
const svg = (cls, paths, size) => `<svg xmlns="${NS}" width="${size || "1em"}" height="${size || "1em"}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linecap="round" stroke-linejoin="round" class="${cls}" focusable="false" aria-hidden="true">${paths.map((d) => `<path vector-effect="non-scaling-stroke" d="${d}"></path>`).join("")}</svg>`;
const I = {
  close: svg("lucide lucide-x bn-icon bn-icon-close", ["M18 6 6 18", "m6 6 12 12"]),
  check: svg("lucide lucide-check bn-icon bn-icon-check", ["M20 6 9 17l-5-5"]),
  add: svg("lucide lucide-plus bn-icon bn-icon-add", ["M5 12h14", "M12 5v14"]),
  revert: svg("lucide lucide-undo-2 bn-icon bn-icon-revert", ["M9 14 4 9l5-5", "M4 9h10.5a5.5 5.5 0 0 1 5.5 5.5a5.5 5.5 0 0 1-5.5 5.5H11"]),
  caret: svg("lucide lucide-chevron-down bn-icon bn-icon-caret", ["m6 9 6 6 6-6"]),
  hide: svg("lucide lucide-eye-off bn-icon bn-icon-hide bn-icon--px", ["M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49", "M14.084 14.158a3 3 0 0 1-4.242-4.242", "M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143", "m2 2 20 20"], 14),
};
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const tc = (sec) => `${String(Math.floor(sec / 60)).padStart(2, "0")}:${String(sec % 60).padStart(2, "0")}`;
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const plural = (n, one, other) => (n === 1 ? one : other).replace("{{count}}", n);

// ── the record, indexed ──
const byS = new Map(D.sessions.map((s) => [s.id, s]));
const byT = new Map(D.turns.map((t) => [t.id, t]));
const byQ = new Map(D.quotes.map((q) => [q.id, q]));
const tagBg = new Map(D.vocab.flatMap((g) => g.tags.map((t) => [t.name.toLowerCase(), t.bg])));
const nameOf = (sid, code) => (byS.get(sid).people.find((p) => p.code === code) || {}).name || "";
const namesOf = (s) => { const n = s.people.map((p) => p.name).filter(Boolean);
  return n.length <= 2 ? n.join(" and ") : `${n[0]} and ${n.length - 1} others`; };
const items = D.sections.flatMap((sec) => sec.items);
const itemOf = new Map(items.map((it) => [it.id, it]));
const turnsAt = (item, sid) => D.turns.filter((t) => t.item === item && t.session === sid);
const answersTo = (tid) => D.quotes.filter((q) => q.turn === tid);

// ── the store: one copy of every quote's state, whichever view draws it ──
const st = {
  session: "all", focus: null, card: null, sel: new Set(), anchor: null,
  starred: new Set(D.state.starred), hidden: new Set(D.state.hidden),
  tags: new Map(D.quotes.map((q) => [q.id, [...q.tags]])), proposed: new Map(D.quotes.map((q) => [q.id, [...q.proposed]])),
  aiGone: new Set(), edits: new Map(), editing: null, tagFor: null, tagVal: "", tagIdx: -1, flash: new Set(),
  counter: null, playing: null, lastTag: null, guideHidden: false,
  opt: { land: "question", counts: "follow", proposals: "on", asks: "links", esc: "card", empty: "quiet" },
};

// ── the navigator's arithmetic (model.ts: cellQuotes, yieldThirds, shadeStep, barShare) ──
const counted = (q) => st.opt.counts === "ignore" || !st.hidden.has(q.id);
const cellQ = (item, sid) => turnsAt(item, sid).reduce((n, t) => n + answersTo(t.id).filter(counted).length, 0);
const rowTotal = (it) => it.sessions.reduce((n, sid) => n + cellQ(it.id, sid), 0);
function thirds() {
  const v = items.flatMap((it) => it.sessions.map((sid) => cellQ(it.id, sid))).filter((q) => q > 0).sort((a, b) => a - b);
  if (!v.length) return [0, 0, 0];
  return [v[Math.ceil(v.length / 3) - 1], v[Math.ceil(2 * v.length / 3) - 1], v[v.length - 1]];
}
const shade = (q, [lo, mid, mx]) => (q <= 0 ? 0 : mx === lo ? 2 : q >= mx ? 3 : q <= lo ? 1 : q <= mid ? 2 : 3);
const share = (q, mx) => (q && mx ? Math.round(100 * Math.log1p(q) / Math.log1p(mx)) : 0);

// ── markup: the product's own ──
function badge(code, name, o = {}) {
  const cls = `bn-person-badge${o.compact ? " bn-person-badge-compact" : ""}${o.absent ? " bn-person-badge-absent" : ""}`;
  const b = `<span class="${cls}"><span class="bn-speaker-badge--split"><span class="bn-speaker-badge-code">${esc(code)}</span>${name ? `<span class="bn-speaker-badge-name">${esc(name)}</span>` : ""}</span></span>`;
  return o.href ? `<a href="${o.href}" class="speaker-link">${b}</a>` : b;
}
const here = (inner, on) => (on ? `<span class="bn-person-badge-here">${inner}</span>` : `<span>${inner}</span>`);
const timecodeLink = (key, code, sec, end) =>
  `<a class="timecode${st.playing === key ? " bn-timecode-glow bn-timecode-playing" : ""}" href="#t=${sec}" data-play="${key}" data-participant="${code}" data-seconds="${sec}" data-end-seconds="${end}"><span class="timecode-bracket">[</span>${tc(sec)}<span class="timecode-bracket">]</span></a>`;

function tagInput(q) {
  const have = new Set(st.tags.get(q.id).map((t) => t.toLowerCase()));
  const v = st.tagVal.trim().toLowerCase();
  const rows = [];
  let n = 0, ghost = "";
  for (const g of D.vocab) {
    const hits = g.tags.filter((t) => !have.has(t.name) && (!v || t.name.includes(v)));
    if (!hits.length) continue;
    rows.push(`<div class="tag-suggest-header" style="background: var(--bn-group-${g.set});" aria-hidden="true">${esc(g.group)}</div>`);
    for (const t of hits) {
      if (!ghost && v && t.name.startsWith(v)) ghost = t.name.slice(v.length);
      rows.push(`<div class="tag-suggest-item${n === st.tagIdx ? " active" : ""}" data-suggest="${esc(t.name)}" data-group="${esc(g.group)}"><span class="tag-suggest-pill" style="background: ${t.bg};">${esc(t.name)}</span></div>`);
      n++;
    }
  }
  return `<span class="tag-input-wrap"><span class="tag-input-box"><input class="tag-input" type="text" placeholder="tag" value="${esc(st.tagVal)}"><span class="tag-ghost-layer"><span class="tag-ghost-spacer">${esc(st.tagVal)}</span><span class="tag-ghost">${esc(ghost)}</span></span></span><span class="tag-sizer"></span>${n ? `<div class="tag-suggest">${rows.join("")}</div>` : ""}</span>`;
}

function card(q, forTurn) {
  if (st.hidden.has(q.id)) return "";  // QuoteCard returns null for a hidden quote
  const text = st.edits.has(q.id) ? st.edits.get(q.id) : q.text;
  const edited = st.edits.has(q.id) && st.edits.get(q.id) !== q.text;
  const starred = st.starred.has(q.id);
  const cls = `quote-card${starred ? " starred" : ""}${st.editing === q.id ? " editing" : ""}${st.card === q.id ? " bn-focused" : ""}${st.sel.has(q.id) ? " bn-selected" : ""}`;
  const name = nameOf(q.session, q.participant);
  const ai = q.sentiment && !st.aiGone.has(q.id)
    ? `<span class="badge badge-ai badge-${q.sentiment}" role="button" tabindex="0" data-act="ai">${cap(q.sentiment)}</span>` : "";
  const user = st.tags.get(q.id).map((t) => `<span class="badge badge-user${st.flash.has(`${q.id}:${t}`) ? " badge-accept-flash" : ""}" style="background-color: ${tagBg.get(t.toLowerCase()) || "var(--bn-custom-bg)"};">${esc(t)}<button class="badge-delete" aria-label="Delete ${esc(t)}" data-act="untag" data-tag="${esc(t)}">${I.close}</button></span>`).join("");
  const prop = st.opt.proposals === "on" ? st.proposed.get(q.id).map((t) => `<span class="badge badge-proposed" style="background-color: ${tagBg.get(t) || "var(--bn-custom-bg)"};">${esc(t)}<span class="badge-action-pill"><span class="badge-action-deny" role="button" tabindex="0" aria-label="Deny" data-act="deny" data-tag="${esc(t)}">${I.close}</span><span class="badge-action-accept" role="button" tabindex="0" aria-label="Accept" data-act="accept" data-tag="${esc(t)}">${I.check}</span></span></span>`).join("") : "";
  const add = st.tagFor === q.id ? tagInput(q) : `<span class="badge badge-add" role="button" tabindex="0" aria-label="Add tag" data-act="add">${I.add}</span>`;
  const restore = q.sentiment && st.aiGone.has(q.id) ? `<button class="badge-restore" aria-label="Restore tags" title="Restore tags" data-act="restore">${I.revert}</button>` : "";
  return `<div class="dl-card" data-for="${forTurn}"><blockquote id="${q.id}" data-timecode="${tc(q.sec)}" data-participant="${q.participant}" class="${cls}"><div class="quote-row">${timecodeLink(q.id, q.participant, q.sec, q.end)}<div class="quote-body"><span class="quote-text-wrapper"><span class="smart-quote">“</span><span class="quote-text" data-edit-key="${q.id}:text" style="cursor: text;"${st.editing === q.id ? ' contenteditable="true"' : ""}>${esc(text)}</span><span class="smart-quote">”</span></span> <span class="speaker">${badge(q.participant, name, { href: `/report/sessions/${q.session}#t-${q.sec}` })}</span><div class="badges">${ai}${user}${prop}${add}${restore}</div></div></div><button class="hide-btn" aria-label="Hide this quote" aria-pressed="false" data-act="hide">${I.hide}</button><button class="action-btn undo-btn${edited ? " visible" : ""}" aria-label="Revert to original" title="Revert to original" data-act="undo">${I.revert}</button><button class="star-btn${starred ? " starred" : ""}" aria-label="Star this quote" aria-pressed="${starred}" data-act="star">★</button></blockquote></div>`;
}

function lit() {
  if (!st.focus) return new Set();
  if (st.focus.turn) return new Set([st.focus.turn]);
  return new Set(D.turns.filter((t) => t.item === st.focus.item).map((t) => t.id));
}

function askRow(t, noAns, hot) {
  const links = st.opt.asks === "links";
  const time = links ? timecodeLink(t.id, t.speaker, t.sec, t.sec + 5) : `<span class="timecode">[${tc(t.sec)}]</span>`;
  const who = badge(t.speaker, "", links ? { href: `/report/sessions/${t.session}#t-${t.sec}` } : {});
  return `<blockquote class="quote-card dl-ask${hot.has(t.id) ? " hot" : ""}" data-item="${t.item}" data-turn="${t.id}"><div class="quote-row">${time}<div class="quote-body"><button type="button" class="dl-ask-btn" aria-pressed="${!!st.focus && st.focus.turn === t.id}" data-ask="${t.id}"><span class="moderator-question-text">${esc(t.text)}</span></button><span class="speaker">${who}</span>${noAns ? '<span class="dl-noans">No quotes from this question</span>' : ""}</div></div></blockquote>`;
}

function counter(key, ids) {
  if (!ids.length) return "";
  const open = st.counter === key;
  const list = ids.map((id) => { const q = byQ.get(id);
    return `<div class="bn-hidden-item" data-quote-id="${id}"><a class="timecode" href="#" role="button" tabindex="0" data-play="${id}" data-participant="${q.participant}" data-seconds="${q.sec}" data-end-seconds="${q.end}" title="Play video">[${tc(q.sec)}]</a><span class="bn-hidden-preview" role="button" tabindex="0" title="Unhide" data-unhide="${id}">${esc(q.text.length > 80 ? q.text.slice(0, 80) + "…" : q.text)}</span><span class="speaker-link">${q.participant}</span></div>`; }).join("");
  return `<div class="bn-hidden-badge"><button class="bn-hidden-toggle" aria-expanded="${open}" data-counter="${key}">${plural(ids.length, "{{count}} hidden quote", "{{count}} hidden quotes")} <span class="bn-hidden-chevron">${I.caret}</span></button>${open ? `<div class="bn-hidden-dropdown"><div class="bn-hidden-header"><span>Unhide:</span>${ids.length > 1 ? `<a href="#" class="bn-unhide-all" role="button" tabindex="0" data-unhide-all="${ids.join(" ")}">Unhide all</a>` : ""}</div><div class="bn-hidden-list">${list}</div></div>` : ""}</div>`;
}
const hiddenIn = (turnIds) => turnIds.flatMap((tid) => answersTo(tid).filter((q) => st.hidden.has(q.id)).map((q) => q.id));

const shown = (tid) => answersTo(tid).filter((q) => !st.hidden.has(q.id));
const quiet = () => st.opt.empty === "quiet";

// One session's block for one question in All: lead-in, ask(s), answers, and — option (b) — the
// counter at its foot. Quiet (decided 19 Oct 2026): a session with no quote to show has no block.
function block(sid, item, hot) {
  const ts = turnsAt(item, sid);
  const s = byS.get(sid);
  const hid = hiddenIn(ts.map((t) => t.id));
  const foot = st.opt.land === "session" ? counter(`${sid}|${item}`, hid) : "";
  const leadIn = `<button type="button" class="dl-from" title="Show session ${s.n}" data-from="${sid}" data-item="${item}">${badge(`#${s.n}`, namesOf(s))}</button>`;
  const body = ts.map((t) => { const a = answersTo(t.id);
    return askRow(t, !quiet() && shown(t.id).length === 0, hot) + a.map((q) => card(q, t.id)).join(""); }).join("");
  return `<div class="dl-group">${leadIn}${body}${foot ? `<div class="dl-hidden-foot">${foot}</div>` : ""}</div>`;
}

// A session's own view: the conversation in order. Questions that drew nothing to show fold forward
// into the next one that did (as shipped); the last run of them closes the column. The counter ends
// each group. Quiet drops "No quotes from this question" from that last run.
function sessionGroups(sid, its, hot) {
  const groups = [];
  let pending = [];
  for (const it of its) {
    for (const t of turnsAt(it.id, sid)) {
      pending.push(t);
      if (shown(t.id).length) { groups.push(pending); pending = []; }
    }
  }
  if (pending.length) groups.push(pending);
  return groups.map((g, gi) => {
    const last = gi === groups.length - 1 && !shown(g[g.length - 1].id).length;
    const body = g.map((t) => askRow(t, !quiet() && last && t === g[g.length - 1], hot)
      + answersTo(t.id).map((q) => card(q, t.id)).join("")).join("");
    const hid = hiddenIn(g.map((t) => t.id));
    const foot = st.opt.land !== "lens" ? counter(`${sid}|${g[0].id}`, hid) : "";
    return `<div class="dl-group">${body}${foot ? `<div class="dl-hidden-foot">${foot}</div>` : ""}</div>`;
  }).join("");
}

function heading(text, allHidden) {
  const act = st.opt.land === "lens" ? counter("lens", allHidden) : "";
  return `<div class="section-heading"><h1>${esc(text)}</h1>${act ? `<div class="section-heading-action">${act}</div>` : ""}</div>`;
}

function content() {
  const hot = lit();
  const visible = (sids) => D.quotes.filter((q) => sids.includes(q.session));
  if (st.session === "all") {
    const asks = D.turns.length;
    const nq = D.quotes.filter((q) => !st.hidden.has(q.id)).length;
    const parts = D.sections.map((sec) => {
      const rows = sec.items.filter((it) => it.sessions.length).map((it) => {
        const missing = D.sessions.filter((s) => !it.sessions.includes(s.id));
        const tids = D.turns.filter((t) => t.item === it.id).map((t) => t.id);
        const hid = st.opt.land === "question" ? hiddenIn(tids) : [];
        const head = hid.length ? `<div class="bn-group-header"><h3>${esc(it.text)}</h3>${counter(`q|${it.id}`, hid)}</div>` : `<h3>${esc(it.text)}</h3>`;
        const sids = quiet() ? it.sessions.filter((sid) => turnsAt(it.id, sid).some((t) => shown(t.id).length)) : it.sessions;
        const absent = !quiet() && missing.length ? `<p class="dl-before dl-notasked"><span>Not asked in</span>${missing.map((s) => badge(`#${s.n}`, "", { compact: true, absent: true })).join("")}</p>` : "";
        return `<div class="dl-item${quiet() && !sids.length ? " empty" : ""}" data-item="${it.id}">${head}${sids.map((sid) => block(sid, it.id, hot)).join("")}${absent}</div>`;
      }).join("");
      return rows ? `<div class="dl-part-group"><h2 class="dl-part">${esc(sec.title)}</h2>${rows}</div>` : "";
    }).join("");
    return `<section>${heading("All sessions", [...st.hidden])}<div class="dl-meta"><span class="dl-stats">${D.total} · ${plural(asks, "{{count}} question", "{{count}} questions")} · ${plural(nq, "{{count}} quote", "{{count}} quotes")}</span></div>${parts}</section>`;
  }
  const s = byS.get(st.session);
  const its = items.filter((it) => it.sessions.includes(s.id));
  const nq = visible([s.id]).filter((q) => !st.hidden.has(q.id)).length;
  const hidAll = visible([s.id]).filter((q) => st.hidden.has(q.id)).map((q) => q.id);
  return `<section>${heading(`Session ${s.n}`, hidAll)}<div class="dl-meta">${s.people.map((p) => badge(p.code, p.name)).join("")}<span class="dl-stats">${s.duration} · ${plural(its.length, "{{count}} question", "{{count}} questions")} · ${plural(nq, "{{count}} quote", "{{count}} quotes")}</span></div>${sessionGroups(s.id, its, hot)}</section>`;
}

function nav() {
  const th = thirds();
  const mx = Math.max(1, ...items.map(rowTotal));
  const all = st.session === "all";
  const at = D.sessions.findIndex((s) => s.id === st.session);
  const strip = (inner) => `<span class="dl-cells${at >= 0 ? " lit" : ""}"${at >= 0 ? ` style="--dl-here: ${at};"` : ""}>${inner}</span>`;
  const key = `<div class="bn-pipeline-key dl-key" role="note" aria-label="Key"><div class="bn-pipeline-key-group"><span class="bn-pipeline-key-item"><span class="dl-mk" aria-hidden="true"><span class="dl-dot"></span></span>Asked as planned</span><span class="bn-pipeline-key-item"><span class="dl-mk" aria-hidden="true"><span class="dl-dot hollow"></span></span>Planned, never asked</span><span class="bn-pipeline-key-item"><span class="dl-mk" aria-hidden="true">+</span>Not in your guide</span></div><div class="bn-pipeline-key-group"><span class="bn-pipeline-key-item"><span class="dl-cell s0" aria-hidden="true"></span>Not asked</span><span class="bn-pipeline-key-item"><span class="dl-cell s1" aria-hidden="true"></span><span class="dl-cell s2" aria-hidden="true"></span><span class="dl-cell s3" aria-hidden="true"></span>Fewer → more quotes</span></div>${all || quiet() ? "" : '<div class="bn-pipeline-key-group"><span class="bn-pipeline-key-item dl-key-grey">Grey: not asked in this session</span></div>'}</div>`;
  const groups = D.sections.map((sec) => `<div role="group"><h2 class="toc-heading">${esc(sec.title)}</h2>${sec.items.map((it) => {
    const asked = all || it.sessions.includes(st.session);
    const cls = ["toc-link", "dl-row"];
    const empty = quiet() && (all ? rowTotal(it) === 0 : cellQ(it.id, st.session) === 0);
    if (!it.sessions.length) cls.push("dim"); else if (!asked || empty) cls.push("ghost");
    if (it.mark === "hollow") cls.push("unasked");
    if (st.focus && st.focus.item === it.id) cls.push("active");
    const mk = it.mark === "plus" ? "+" : `<span class="${it.mark === "hollow" ? "dl-dot hollow" : "dl-dot"}"></span>`;
    const cells = strip(D.sessions.map((s) => { const a = it.sessions.includes(s.id); const q = a ? cellQ(it.id, s.id) : 0;
      const label = `#${s.n}${namesOf(s) ? " " + namesOf(s) : ""} · ${!a ? "Not asked" : q === 0 ? "Asked, no quotes" : plural(q, "{{count}} quote", "{{count}} quotes")}`;
      return `<button type="button" tabindex="-1" title="${esc(label)}" aria-label="${esc(label)}"${a ? "" : ' aria-disabled="true"'} class="dl-cell s${shade(q, th)}${s.id === st.session ? " here" : ""}" data-cell="${s.id}" data-item="${it.id}"></button>`; }).join(""));
    const tot = rowTotal(it);
    return `<div class="${cls.join(" ")}" data-id="${it.id}"><button type="button" class="dl-row-btn" title="${esc(it.text)}" data-row="${it.id}" aria-pressed="${!!st.focus && st.focus.item === it.id}"${it.sessions.length ? "" : ' aria-disabled="true"'}><span class="dl-mk" aria-hidden="true">${mk}</span><span class="dl-tx">${esc(it.text)}</span></button><span class="dl-measure">${cells}<span class="tag-bar-area"><span class="dl-bar-box" aria-hidden="true">${tot ? `<span class="tag-micro-bar" role="img" style="width: ${share(tot, mx)}%; background-color: var(--dl-bar);"></span>` : ""}</span><span class="tag-count" aria-hidden="true">${tot}</span></span></span></div>`;
  }).join("")}</div>`).join("");
  return `<nav id="dl-nav" class="dl-nav toc-sidebar-body" aria-label="Discussion guide">${key}${groups}</nav>`;
}

function bar() {
  const all = st.session === "all";
  const sess = D.sessions.map((s) => `<button type="button" role="radio" aria-checked="${s.id === st.session}" class="dl-sess" title="Session ${s.n}${namesOf(s) ? ": " + esc(namesOf(s)) : ""}" data-sess="${s.id}">${here(badge(`#${s.n}`, namesOf(s)), s.id === st.session)}</button>`).join("");
  return `<div class="dl-bar"><div class="dl-bar-nav"><span class="dimension-toggle" role="radiogroup" aria-label="Show"><button type="button" role="radio" aria-checked="true" class="dimension-btn active">Normalised questions</button><button type="button" role="radio" aria-checked="false" class="dimension-btn">Your guide</button></span></div><div class="dl-sessions" role="radiogroup" aria-label="Sessions"><button type="button" role="radio" aria-checked="${all}" class="dl-sess" aria-label="All sessions" title="All sessions" data-sess="all">${here(badge("All", ""), all)}</button><span class="dl-sep" aria-hidden="true"></span>${sess}</div></div>`;
}

const win = document.getElementById("m-win");
const lens = document.getElementById("m-lens");
function render() {
  const navTop = lens.querySelector(".dl-nav")?.scrollTop || 0;
  lens.className = `dl-lens dl-m-strip${st.focus ? " has-focus" : ""}${st.guideHidden ? " guide-hidden" : ""}`;
  lens.dataset.all = String(st.session === "all");
  lens.innerHTML = `${bar()}${nav()}<div class="dl-gut"><svg class="dl-wires" aria-hidden="true"></svg><div class="drag-handle dl-split" role="separator" aria-orientation="vertical" aria-label="Resize the discussion guide" tabindex="0"></div></div><div class="dl-content">${content()}</div>`;
  lens.style.setProperty("--dl-bar-h", `${lens.querySelector(".dl-bar").getBoundingClientRect().height}px`);
  const n = lens.querySelector(".dl-nav"); if (n) n.scrollTop = navTop;
  if (st.tagFor) { const i = lens.querySelector(".tag-input"); if (i) { i.focus(); i.setSelectionRange(i.value.length, i.value.length); } }
  if (st.editing) { const t = lens.querySelector(`#${CSS.escape(st.editing)} .quote-text`); if (t) { t.focus(); const r = document.createRange(); r.selectNodeContents(t); r.collapse(false); const s = getSelection(); s.removeAllRanges(); s.addRange(r); } }
  st.flash.clear();
}
const status = (msg) => { document.getElementById("m-status").textContent = msg; };

// ── actions: the shared store's bulk rule — act on the selection when the target is in it ──
const targets = (id) => (st.sel.has(id) && st.sel.size ? [...st.sel] : [id]);
const order = () => [...lens.querySelectorAll(".dl-content blockquote.quote-card:not(.dl-ask)")].map((b) => b.id);
function star(id) { const ids = targets(id); const on = ids.some((x) => !st.starred.has(x)); ids.forEach((x) => (on ? st.starred.add(x) : st.starred.delete(x))); }
function hide(id) {
  const ids = targets(id); const o = order(); const after = o.slice(o.indexOf(id) + 1).find((x) => !ids.includes(x));
  ids.forEach((x) => st.hidden.add(x)); st.sel.clear(); if (ids.includes(st.card)) st.card = after || null;
}
function addTag(id, name) {
  name = name.trim(); if (!name) return;
  for (const x of targets(id)) { const t = st.tags.get(x);
    if (!t.some((y) => y.toLowerCase() === name.toLowerCase())) { t.push(name); st.flash.add(`${x}:${name}`); }
    st.proposed.set(x, st.proposed.get(x).filter((p) => p !== name.toLowerCase())); }
  st.lastTag = name;
}
function closeTag() { st.tagFor = null; st.tagVal = ""; st.tagIdx = -1; }
function play(key) {
  st.playing = key; const q = byQ.get(key), t = byT.get(key), x = q || t;
  status(`▶ the player opens: session ${x.session.slice(1)}, ${q ? q.participant : t.speaker}, at ${tc(x.sec)}`);
}
function focusQuestion(item, turn) {
  const same = st.focus && st.focus.item === item && (st.focus.turn || null) === (turn || null);
  st.focus = same ? null : { item, turn: turn || null };
}

lens.addEventListener("click", (e) => {
  const el = e.target.closest("[data-act],[data-play],a.speaker-link,[data-sess],[data-row],[data-cell],[data-from],[data-ask],[data-counter],[data-unhide],[data-unhide-all],.tag-suggest-item,.quote-text,blockquote.quote-card");
  if (!el || el.closest(".tag-input-box")) return;
  const bq = el.closest("blockquote.quote-card:not(.dl-ask)");
  const id = bq && bq.id;
  if (el.matches("a")) e.preventDefault();
  if (el.dataset.play) { play(el.dataset.play); if (id) st.card = id; return render(); }
  if (el.matches("a.speaker-link")) {
    status(`→ the transcript opens: ${el.getAttribute("href")}`); if (id) st.card = id; return render(); }
  if (el.dataset.sess) { st.session = el.dataset.sess; st.card = null; st.sel.clear(); st.counter = null; win.scrollTop = 0; return render(); }
  if (el.dataset.row) { if (el.getAttribute("aria-disabled")) return; focusQuestion(el.dataset.row); render(); return land(el.dataset.row); }
  if (el.dataset.cell) { if (el.getAttribute("aria-disabled")) return; st.session = el.dataset.cell; st.focus = { item: el.dataset.item, turn: null }; render(); return land(el.dataset.item); }
  if (el.dataset.from) { st.session = el.dataset.from; st.focus = { item: el.dataset.item, turn: null }; render(); return land(el.dataset.item); }
  if (el.dataset.ask) { const t = byT.get(el.dataset.ask); focusQuestion(t.item, t.id); return render(); }
  if (el.dataset.counter) { st.counter = st.counter === el.dataset.counter ? null : el.dataset.counter; return render(); }
  if (el.dataset.unhide) { st.hidden.delete(el.dataset.unhide); st.card = el.dataset.unhide; st.counter = null; return render(); }
  if (el.dataset.unhideAll) { el.dataset.unhideAll.split(" ").forEach((x) => st.hidden.delete(x)); st.counter = null; return render(); }
  if (el.dataset.suggest) { addTag(st.tagFor, el.dataset.suggest); closeTag(); return render(); }
  const act = el.dataset.act;
  if (act && id) {
    st.card = id;
    if (act === "star") star(id);
    else if (act === "hide") hide(id);
    else if (act === "add") { st.tagFor = id; st.tagVal = ""; st.tagIdx = -1; }
    else if (act === "untag") st.tags.set(id, st.tags.get(id).filter((t) => t !== el.dataset.tag));
    else if (act === "accept") addTag(id, el.dataset.tag);
    else if (act === "deny") st.proposed.set(id, st.proposed.get(id).filter((t) => t !== el.dataset.tag));
    else if (act === "ai") st.aiGone.add(id);
    else if (act === "restore") st.aiGone.delete(id);
    else if (act === "undo") st.edits.delete(id);
    return render();
  }
  if (el.matches(".quote-text") && id && st.editing !== id) { st.card = id; st.editing = id; return render(); }
  if (id) {
    if (e.shiftKey && st.anchor) { const o = order(); const [a, b] = [o.indexOf(st.anchor), o.indexOf(id)].sort((x, y) => x - y); o.slice(a, b + 1).forEach((x) => st.sel.add(x)); }
    else if (e.metaKey || e.ctrlKey) { st.sel.has(id) ? st.sel.delete(id) : st.sel.add(id); st.anchor = id; }
    else { st.sel.clear(); st.anchor = id; }
    st.card = id; return render();
  }
});
function land(item) {
  requestAnimationFrame(() => {
    const to = lens.querySelector(st.session === "all" ? `.dl-item[data-item="${item}"]` : `.dl-ask[data-item="${item}"]`);
    if (to) to.scrollIntoView({ block: "start", behavior: "smooth" });
  });
}
lens.addEventListener("input", (e) => {
  if (!e.target.matches(".tag-input")) return;
  st.tagVal = e.target.value; st.tagIdx = -1;
  const wrap = e.target.closest(".tag-input-wrap");
  const tmp = document.createElement("span"); tmp.innerHTML = tagInput(byQ.get(st.tagFor));
  wrap.querySelector(".tag-ghost-layer").replaceWith(tmp.querySelector(".tag-ghost-layer"));
  wrap.querySelector(".tag-suggest")?.remove(); const sug = tmp.querySelector(".tag-suggest"); if (sug) wrap.append(sug);
});
lens.addEventListener("focusout", (e) => {
  // TagInput's handleBlur: commit what was typed, else cancel (after 150 ms, so a suggestion click lands first).
  if (e.target.matches(".tag-input")) { const id = st.tagFor, v = e.target.value.trim();
    setTimeout(() => { if (st.tagFor === id && e.target.isConnected && document.activeElement !== e.target) { if (v) addTag(id, v); closeTag(); render(); } }, 150); }
  if (e.target.matches(".quote-text[contenteditable]")) commitEdit(e.target);
});
function commitEdit(t) {
  const id = st.editing; if (!id) return; st.editing = null;
  const v = t.textContent.trim(); if (v && v !== byQ.get(id).text) st.edits.set(id, v); else if (v === byQ.get(id).text) st.edits.delete(id);
  render();
}

document.addEventListener("keydown", (e) => {
  const tgt = e.target;
  if (tgt.matches && tgt.matches(".tag-input")) {
    const items = [...lens.querySelectorAll(".tag-suggest-item")];
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); st.tagIdx = Math.max(-1, Math.min(items.length - 1, st.tagIdx + (e.key === "ArrowDown" ? 1 : -1))); items.forEach((x, i) => x.classList.toggle("active", i === st.tagIdx)); return; }
    // TagInput's resolveValue: an arrowed suggestion, else the typed text plus its ghost, else the text.
    const ghost = lens.querySelector(".tag-ghost")?.textContent || "";
    const val = st.tagIdx >= 0 ? items[st.tagIdx].dataset.suggest : ghost ? tgt.value + ghost : tgt.value.trim();
    if (e.key === "ArrowRight" && ghost) { e.preventDefault(); tgt.value += ghost; tgt.dispatchEvent(new Event("input", { bubbles: true })); return; }
    if (e.key === "Enter" || e.key === "Tab") {
      e.preventDefault(); e.stopPropagation(); const id = st.tagFor;
      if (val) addTag(id, val); closeTag();
      if (val && e.key === "Tab") st.tagFor = id;  // commit and reopen
      return render();
    }
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); closeTag(); return render(); }
    return;
  }
  if (tgt.matches && tgt.matches(".quote-text[contenteditable]")) {
    if (e.key === "Enter") { e.preventDefault(); e.stopPropagation(); commitEdit(tgt); }
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); st.editing = null; render(); }
    return;
  }
  if (tgt.matches && tgt.matches("input:not([type=radio]), textarea, select")) return;
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  const o = order();
  const move = (d) => { const i = o.indexOf(st.card); const n = o[i < 0 ? (d > 0 ? 0 : o.length - 1) : Math.max(0, Math.min(o.length - 1, i + d))]; return n; };
  const show = () => requestAnimationFrame(() => lens.querySelector(`#${CSS.escape(st.card)}`)?.closest(".dl-card").scrollIntoView({ block: "nearest" }));
  if (e.key === "j" || e.key === "k") { e.preventDefault(); st.card = move(e.key === "j" ? 1 : -1); st.anchor = st.card; render(); return show(); }
  if (e.key === "J" || e.key === "K") { e.preventDefault(); if (st.card) st.sel.add(st.card); st.card = move(e.key === "J" ? 1 : -1); st.sel.add(st.card); render(); return show(); }
  if (e.key === "[") { e.preventDefault(); st.guideHidden = !st.guideHidden; return render(); }
  if (e.key === "Escape") {
    if (st.counter) { st.counter = null; return render(); }
    const cardFirst = st.opt.esc === "card";
    if (cardFirst ? (st.sel.size || st.card) : !st.focus) { if (st.sel.size) st.sel.clear(); else st.card = null; return render(); }
    if (st.focus) { st.focus = null; return render(); }
    if (st.sel.size) st.sel.clear(); else st.card = null; return render();
  }
  if (!st.card) return;
  if (e.key === "x") { e.preventDefault(); st.sel.has(st.card) ? st.sel.delete(st.card) : st.sel.add(st.card); return render(); }
  if (e.key === "s") { e.preventDefault(); star(st.card); return render(); }
  if (e.key === "h") { e.preventDefault(); hide(st.card); return render(); }
  if (e.key === "t") { e.preventDefault(); st.tagFor = st.card; st.tagVal = ""; st.tagIdx = -1; return render(); }
  if (e.key === "r" && st.lastTag) { e.preventDefault(); addTag(st.card, st.lastTag); return render(); }
  if (e.key === "Enter") { e.preventDefault(); play(st.card); return render(); }
});

// ── the decisions, and the page's own light/dark and palette ──
document.querySelectorAll(".m-ctl input").forEach((i) => i.addEventListener("change", () => {
  if (i.name === "scheme") { document.documentElement.style.colorScheme = i.value === "auto" ? "light dark" : i.value;
    if (i.value === "auto") document.documentElement.removeAttribute("data-theme"); else document.documentElement.dataset.theme = i.value; }
  else if (i.name === "palette") document.documentElement.dataset.colorTheme = i.value;
  else { st.opt[i.name] = i.value; st.counter = null; }
  i.blur();  // so the report's own keys keep working
  render();
}));
render();
"""


def control(name: str, legend: str, options: list[tuple[str, str]], default: str) -> str:
    rows = "".join(f'<label><input type="radio" name="{name}" value="{v}"{" checked" if v == default else ""}>'
                   f"<span>{label}</span></label>" for v, label in options)
    return f"<fieldset><legend>{legend}</legend>{rows}</fieldset>"


def build() -> str:
    theme = load_default_css()
    disc = DISCUSSION_CSS.read_text(encoding="utf-8")
    data = json.dumps(study(), ensure_ascii=True).replace("</", "<\\/")
    controls = "".join([
        control("land", "1 · A hidden quote is counted…", [
            ("question", "beside its question (the Quotes lens's group header)"),
            ("session", "under each session's answers"),
            ("lens", "once, beside the lens heading")], "question"),
        control("counts", "2 · The guide's counts and shading…", [
            ("follow", "follow hiding (a hidden quote stops counting)"),
            ("ignore", "ignore hiding (counts are what was said)")], "follow"),
        control("proposals", "3 · AutoCode proposals on cards", [
            ("on", "shown, as on Quotes and Screens"), ("off", "not shown here")], "on"),
        control("asks", "4 · The moderator's question rows", [
            ("links", "timecode plays, badge opens the transcript"),
            ("plain", "as shipped: plain text")], "links"),
        control("esc", "5 · Esc clears…", [
            ("card", "the card (selection, then focus), then the question"),
            ("question", "the question, then the card")], "card"),
        control("empty", "6 · A question with nothing to show", [
            ("quiet", "its heading alone, grey; grey in the guide"),
            ("shipped", "as shipped: every session, “No quotes…”, “Not asked in”")], "quiet"),
        control("scheme", "Appearance", [("auto", "system"), ("light", "light"), ("dark", "dark")], "auto")
        + control("palette", "Palette", [("default", "default"), ("edo", "edo")], "default"),
    ])
    return f"""<!DOCTYPE html>
<html lang="en" data-color-theme="default" data-platform="desktop" style="color-scheme: light dark">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Discussion · quotes like everywhere else · Bristlenose mockups</title>
<!-- Generated by experiments/discussion-all-sessions/quote_parity.py. Inlined: the shipped theme
     (load_default_css()), discussion.css verbatim, then ONE block of PROPOSED rules, then chrome. -->
<style>
/* ════ SHIPPED: bristlenose/theme via load_default_css() ════ */
{theme}
/* ════ SHIPPED: frontend/src/islands/discussion/discussion.css — verbatim ════ */
{disc}
</style>
<style>{PROPOSED_CSS}</style>
<style>{CHROME_CSS}</style>
</head>
<body class="m-page">
<h1 class="m-title">Discussion lens · quotes that work like every other quote</h1>
<p class="m-sub">The shipped lens (eight sessions, strip navigator) with the Quotes lens's own card in place of
its read-only one. Try it: hover a card for star and hide, click <b>+</b> to tag, click the words to edit, click a
timecode or a speaker badge, accept or deny a dashed proposal, and use <kbd>j</kbd> <kbd>k</kbd> <kbd>s</kbd>
<kbd>h</kbd> <kbd>t</kbd> <kbd>r</kbd> <kbd>x</kbd> <kbd>⇧J</kbd>/<kbd>⇧K</kbd> <kbd>Enter</kbd> <kbd>Esc</kbd>
<kbd>[</kbd>. Star or hide a quote in All, then open its session: it is one store.</p>
<div class="m-keyrow"><span class="m-k-art">Artefact — the product's pixels and words</span>
<span class="m-k-com">Commentary and controls — not the product</span></div>
<form class="m-ctl" onsubmit="return false">{controls}</form>
<figure class="m-frame"><figcaption class="m-chrome"><span class="m-dots"><i></i><i></i><i></i></span>
<span>Discussion · 8 sessions · 1280 × 780</span><span class="m-status" id="m-status" aria-live="polite"></span></figcaption>
<div class="m-window" id="m-win"><div class="dl-lens dl-m-strip" id="m-lens" style="--dl-nav-w: 330px;"></div></div></figure>

<div class="m-note"><span class="m-note-label">Commentary</span>
<div class="m-cols"><div>
<h3>What is shipped here, and what is proposed</h3>
<ul>
<li><b>Shipped, verbatim:</b> the theme and <code>discussion.css</code>; the lens's markup (session bar, strip
navigator with the selected-column wash, All with lead-ins and “Not asked in”, the ask rows); and the card exactly
as the SPA renders it — <code>QuoteCard</code>, <code>TimecodeLink</code>, <code>PersonBadge</code> with its
transcript link, sentiment, tag, proposed and add badges, hide / revert / star, the <code>TagInput</code> and the
hidden-quotes <code>Counter</code>. Every word in the frame is a shipped English string.</li>
<li><b>Proposed</b> (one style block, each rule commented): a <code>.dl-card</code> wrapper per card, as Screens
has, holding the lens's own marks and positioning star and hide; the Quotes lens's right-hand room on cards; and
the three places the counter can go. The ask rows' two links reuse the card's own link markup.</li>
<li><b>Drawn approximately:</b> editing is plain in-place editing (the product's crop brackets aren't drawn);
the player and transcript are stubs that report to the frame's title bar; the wires in the gutter aren't drawn;
“Your guide” doesn't switch.</li>
</ul>
<h3>Things to notice</h3>
<ul>
<li><b>Two kinds of focus at once.</b> Click a question (or a guide row) and then <kbd>j</kbd>: the question
stays lit while the card focus moves. Option 5 decides which one <kbd>Esc</kbd> clears first.</li>
<li><b>Hiding moves numbers.</b> With option 2 on “follow”, hide the only answer to a question in a session: its
cell in the strip empties and reads “Asked, no quotes”, the same as a question that drew nothing.</li>
<li><b>One store.</b> Starring, tagging and hiding in All show in the session view and back. In the product
they would also show on Quotes and Screens.</li>
<li><b>Badges that look alike, act differently.</b> <code>#3</code> in the session bar and a lead-in switches the
lens to that session; <code>p3</code> on a card opens the transcript. The bar's badges sit inside buttons, and the
codes differ (session number vs participant), but you should check it reads.</li>
</ul>
</div><div>
<h3>The decisions — settled 19 Oct 2026 (the controls' defaults)</h3>
<ul>
<li><b>1 · Beside its question.</b> In All the question heading becomes the Quotes lens's group header with the
counter on the right; in a session view, where a question is one block, the counter ends the block. The other two
options stay switchable for comparison.</li>
<li><b>2 · A hidden quote stops counting.</b> Hiding means the researcher finds it unconvincing as evidence, and
the strip is evidence, not a tally of what was said.</li>
<li><b>3 · Proposals shown</b>, as on Quotes and Screens. A global show/hide for proposals in every lens is a
separate item (100days § 8).</li>
<li><b>4 · Question rows link like quotes:</b> the timecode plays, the badge opens the transcript at that turn.
Never star, hide or tag.</li>
<li><b>5 · Esc:</b> selection, then card focus, then the question.</li>
<li><b>6 · Nothing to show is quiet.</b> Not asked, asked with nothing quotable, or every answer hidden: the guide
row is grey, and in All the question is its heading alone, in the same grey, with the hidden-quotes link if there
is one. In All a session appears under a question only when it has a quote to show, and “Not asked in” goes. No key
line explains the grey: empty space reads as empty. A session's own view keeps its questions, folded forward as
shipped, and drops “No quotes from this question”.</li>
</ul>
<p>Recorded in <code>docs/design-discussion-lens-plan.md</code> §3. Not built.</p>
<h3>Keys (the report's own)</h3>
<p><kbd>j</kbd>/<kbd>k</kbd> move · <kbd>⇧J</kbd>/<kbd>⇧K</kbd> extend · <kbd>x</kbd> select · ⇧-click range ·
⌘-click toggle · <kbd>s</kbd> star · <kbd>h</kbd> hide · <kbd>t</kbd> tag · <kbd>r</kbd> repeat last tag ·
<kbd>Enter</kbd> play · <kbd>[</kbd> guide · <kbd>Esc</kbd>. With a selection, star, hide and tag act on all of it
— try selecting every answer to one question in All and tagging them at once.</p>
</div></div></div>
<script>{SCRIPT.replace("__DATA__", data)}</script>
</body></html>
"""


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")
