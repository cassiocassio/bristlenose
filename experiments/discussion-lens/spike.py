#!/usr/bin/env python3
"""Discussion lens — Phase 1a spike: the four-step design, end to end.

  1. PARSE the guide once into a frozen spine (sections → planned items, ids by code)
  2. CLASSIFY each session's moderator turns against the spine (one call per session)
     then CONSOLIDATE the unplanned residue across sessions (one small call)
  3. STRUCTURE in code (structure.py): promotion rule, ordering, flow placement
  4. ROUTE quotes: the conversational anchor (code) + the topic (one batched call),
     combined by decide_route()

Writes one JSON per run in the lens data contract (`version: 1`) — the shape the
SPA lens reads — and prints a summary. Nothing here imports from or writes to
the product beyond reusing LLMClient and the boundary helper.

Usage (synthetic corpus, three runs):
    .venv/bin/python experiments/discussion-lens/spike.py \
        --corpus experiments/discussion-lens/synthetic --runs 3 \
        --out experiments/discussion-lens/runs/synthetic

    --no-guide            ignore the guide (Merged-only mode)
    --guide/--transcripts/--quotes/--names   point at another corpus instead of --corpus
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))
from structure import (  # noqa: E402
    ASKED_KINDS,
    Consolidated,
    Item,
    Label,
    Section,
    Topic,
    Turn,
    anchor,
    asked_index,
    build_structure,
    decide_route,
    section_of_item,
    tc_seconds,
)

from bristlenose.config import load_settings  # noqa: E402
from bristlenose.llm.boundary import wrap_untrusted  # noqa: E402
from bristlenose.llm.client import LLMClient  # noqa: E402
from bristlenose.llm.pricing import estimate_cost  # noqa: E402

HERE = Path(__file__).resolve().parent
PROMPTS = HERE / "prompts"
MIN_WORDS = 3          # shorter moderator turns are never questions
ROUTE_BATCH = 25


# ── response models ──────────────────────────────────────────────────────────


class SpineItemOut(BaseModel):
    text: str
    terse: str = Field(default="", max_length=40)


class SpineSectionOut(BaseModel):
    title: str
    kind: Literal["questions", "task", "instruction"] = "questions"
    items: list[SpineItemOut] = Field(default_factory=list)


class SpineOut(BaseModel):
    sections: list[SpineSectionOut]


class TurnLabelOut(BaseModel):
    turn_id: str
    kind: Literal["planned", "adlib", "new", "instruction", "chat"]
    item_id: str = ""
    section_id: str = ""
    cluster: str = ""
    role: Literal["opening", "core", "closing"] = "core"
    terse: str = Field(default="", max_length=40)


class SessionLabelsOut(BaseModel):
    labels: list[TurnLabelOut]


class ConsolidatedItemOut(BaseModel):
    turn_ids: list[str]
    terse: str = Field(max_length=40)
    where: str


class TopicOut(BaseModel):
    name: str
    nav: str = Field(max_length=30)
    heading: str = Field(max_length=60)


class ConsolidateOut(BaseModel):
    # topics FIRST: the model settles the lines of enquiry, then assigns questions to them
    topics: list[TopicOut] = Field(default_factory=list)
    items: list[ConsolidatedItemOut] = Field(default_factory=list)


class RouteOut(BaseModel):
    quote_id: str
    section_id: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class RouteBatchOut(BaseModel):
    routes: list[RouteOut]


# ── inputs ───────────────────────────────────────────────────────────────────


_LINE = re.compile(r"^\[([\d:]+)\] \[([a-z]+\d+)\](?: \([^)]*\))? (.*)$")


def fmt_tc(sec: float) -> str:
    s = int(sec)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"


def load_transcripts(folder: Path) -> tuple[dict[str, list[Turn]], dict[str, list[Turn]],
                                            dict[str, float], dict[str, str]]:
    """Moderator turns (all, for the session column), the askable subset, lengths, durations."""
    every: dict[str, list[Turn]] = {}
    askable: dict[str, list[Turn]] = {}
    lengths: dict[str, float] = {}
    durations: dict[str, str] = {}
    for f in sorted(folder.glob("s*.txt")):
        sid, last = f.stem, 0.0
        text = f.read_text(encoding="utf-8")
        m = re.search(r"^# Duration: (.+)$", text, re.M)
        durations[sid] = m.group(1).strip() if m else ""
        seen: set[str] = set()
        for raw in text.splitlines():
            m = _LINE.match(raw)
            if not m:
                continue
            sec = tc_seconds(m.group(1))
            last = sec
            if not m.group(2).startswith("m"):
                continue
            tid = f"{sid}@{m.group(1)}"
            while tid in seen:  # two turns in one second: keep both
                tid += "'"
            seen.add(tid)
            t = Turn(tid, sid, sec, m.group(3).strip())
            every.setdefault(sid, []).append(t)
            if len(t.text.split()) >= MIN_WORDS:
                askable.setdefault(sid, []).append(t)
        lengths[sid] = max(last, 1.0)
    return every, askable, lengths, durations


def load_prompt(name: str) -> tuple[str, str]:
    text = (PROMPTS / name).read_text(encoding="utf-8")
    text = re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.DOTALL)
    sys_m = re.search(r"\n## System\n(.*?)(?=\n## User\n)", text, flags=re.DOTALL)
    usr_m = re.search(r"\n## User\n(.*)$", text, flags=re.DOTALL)
    assert sys_m and usr_m, name
    return sys_m.group(1).strip(), usr_m.group(1).strip()


def fill(template: str, **vars: str) -> str:
    for k, v in vars.items():
        template = template.replace("{" + k + "}", v)
    return template


# ── the four steps ───────────────────────────────────────────────────────────


async def parse_guide(client: LLMClient, guide_text: str) -> list[Section]:
    s, u = load_prompt("parse-guide.md")
    out = await client.analyze(system_prompt=s, user_prompt=fill(u, guide=wrap_untrusted("guide", guide_text)),
                               response_model=SpineOut, max_tokens=8000)
    spine = []
    for i, sec in enumerate(out.sections, 1):  # ids by CODE, in guide order
        spine.append(Section(f"s{i}", sec.title, sec.kind, "planned", sec.title,
                             [Item(f"s{i}.{j}", it.terse or it.text[:24], it.text)
                              for j, it in enumerate(sec.items, 1)]))
    return spine


def spine_block(spine: list[Section]) -> str:
    lines = []
    for s in spine:
        lines.append(f"{s.id} [{s.kind}] {s.title}")
        lines += [f"  {it.id} {it.verbatim}" for it in s.items]
    return "\n".join(lines) or "(no guide — there are no planned sections; every question is `new`)"


async def classify(client: LLMClient, spine: list[Section], turns: list[Turn]) -> list[Label]:
    s, u = load_prompt("classify-turns.md")
    out = await client.analyze(
        system_prompt=s,
        user_prompt=fill(u, spine=wrap_untrusted("spine", spine_block(spine)),
                         turns=wrap_untrusted("turns", "\n".join(f"{t.id} | {t.text}" for t in turns))),
        response_model=SessionLabelsOut, max_tokens=8000)
    return [Label(lb.turn_id, lb.kind, lb.item_id, lb.section_id, lb.cluster, lb.role, lb.terse)
            for lb in out.labels]


async def consolidate(client: LLMClient, labels: list[Label], turns: dict[str, Turn],
                      spine: list[Section]) -> tuple[list[Consolidated], list[Topic]]:
    rows = [f"{lb.turn_id} | {lb.section_id if lb.kind == 'adlib' else 'new: ' + (lb.cluster or '?')} "
            f"| {turns[lb.turn_id].text}"
            for lb in labels if lb.kind in ("adlib", "new") and lb.turn_id in turns]
    if not rows:
        return [], []
    s, u = load_prompt("consolidate.md")
    planned = "\n".join(f"{x.id} {x.title}" for x in spine if x.kind != "instruction") or "(no guide)"
    out = await client.analyze(system_prompt=s,
                               user_prompt=fill(u, planned=wrap_untrusted("planned", planned),
                                                questions=wrap_untrusted("questions", "\n".join(rows))),
                               response_model=ConsolidateOut, max_tokens=8000)
    return ([Consolidated(c.turn_ids, c.terse, c.where) for c in out.items],
            [Topic(t.name, t.nav, t.heading) for t in out.topics])


async def route(client: LLMClient, sections: list[Section], quotes: list[dict]) -> dict[str, RouteOut]:
    s, u = load_prompt("route-quotes.md")
    block = "\n".join(f"{sec.id} | {sec.heading or sec.title} | "
                      + "; ".join(it.terse for it in sec.items if it.turns)
                      for sec in sections if sec.kind != "instruction")
    sec_wrapped = wrap_untrusted("sections", block)

    async def one(batch: list[dict]) -> RouteBatchOut:
        qb = "\n".join(f"{q['key']} | {q['text']}" for q in batch)
        return await client.analyze(system_prompt=s,
                                    user_prompt=fill(u, sections=sec_wrapped, quotes=wrap_untrusted("quotes", qb)),
                                    response_model=RouteBatchOut, max_tokens=4000)
    outs = await asyncio.gather(*(one(quotes[i:i + ROUTE_BATCH]) for i in range(0, len(quotes), ROUTE_BATCH)))
    return {r.quote_id: r for o in outs for r in o.routes}


# ── one run → the lens data contract ─────────────────────────────────────────


async def run_once(client: LLMClient, guide_text: str | None, every: dict[str, list[Turn]],
                   askable: dict[str, list[Turn]], lengths: dict[str, float], durations: dict[str, str],
                   quotes_in: list[dict], names: dict[str, dict],
                   spine: list[Section] | None) -> tuple[dict, list[Section]]:
    t0 = time.monotonic()
    tr0 = (client.tracker.input_tokens, client.tracker.output_tokens, client.tracker.calls)
    if spine is None:
        spine = await parse_guide(client, guide_text) if guide_text else []
    frozen = [Section(s.id, s.title, s.kind, s.origin, s.heading,
                      [Item(i.id, i.terse, i.verbatim) for i in s.items]) for s in spine]
    turns = {t.id: t for ts in askable.values() for t in ts}
    per_session = await asyncio.gather(*(classify(client, spine, ts) for ts in askable.values()))
    labels = [lb for ls in per_session for lb in ls]
    cons, topics = await consolidate(client, labels, turns, spine)
    sections, standalone, stats = build_structure(spine, labels, cons, topics, turns, lengths)

    # quotes: anchor (code) + topic (model) → decide_route
    sec_of = section_of_item(sections)
    asked = asked_index(sections, standalone, turns)
    keyed = [dict(q, key=f"q{i}") for i, q in enumerate(quotes_in)]
    topical = await route(client, sections, keyed) if sections else {}
    valid_sections = {s.id for s in sections if s.kind != "instruction"}
    quotes = []
    for q in keyed:
        before = [(at, iid) for at, iid in asked.get(q["session_id"], []) if at <= q["start"]]
        after_item = before[-1][1] if before else None
        a_item = anchor(q["session_id"], q["start"], asked.get(q["session_id"], []))
        a_sec = sec_of.get(a_item) if a_item else None
        r = topical.get(q["key"])
        t_sec = r.section_id if r and r.section_id in valid_sections else None
        stats["route_invalid_or_missing"] += int(r is None or (r.section_id != "UNROUTED" and t_sec is None))
        section, how = decide_route(a_sec, t_sec, r.confidence if r else 0.0)
        quotes.append({"key": q["key"], "session": q["session_id"], "participant": q["participant_id"],
                       "name": q.get("name", ""), "sec": q["start"], "time": fmt_tc(q["start"]),
                       "text": q["text"], "after_item": after_item, "anchor_section": a_sec,
                       "topic_section": t_sec, "confidence": r.confidence if r else None,
                       "section": section, "how": how, "sentiment": q.get("sentiment")})

    item_of_turn = {t: it.id for s in sections for it in s.items for t in it.turns}
    item_of_turn.update({t: it.id for it in standalone for t in it.turns})
    label_kind = {lb.turn_id: lb.kind for lb in labels}

    def item_json(it: Item) -> dict:
        return {"id": it.id, "terse": it.terse, "verbatim": it.verbatim, "source": it.source,
                "placed": it.placed, "role": it.role,
                "asks": [{"turn": t, "session": turns[t].session, "sec": turns[t].sec} for t in it.turns]}

    tr = client.tracker
    din, dout, dcalls = tr.input_tokens - tr0[0], tr.output_tokens - tr0[1], tr.calls - tr0[2]
    model = client.settings.llm_model
    return {
        "version": 1,
        "guide": bool(spine),
        "sessions": [{"id": sid, "number": int(re.sub(r"\D", "", sid) or 0),
                      "participants": names.get(sid, {}).get("participants", []),
                      "duration": durations.get(sid, ""), "seconds": lengths[sid]} for sid in every],
        "spine": [{"id": s.id, "title": s.title, "kind": s.kind,
                   "items": [{"id": it.id, "terse": it.terse, "text": it.verbatim} for it in s.items]}
                  for s in spine],
        "sections": [{"id": s.id, "title": s.title, "heading": s.heading, "kind": s.kind,
                      "origin": s.origin, "items": [item_json(it) for it in s.items]} for s in sections],
        "standalone": [item_json(it) for it in standalone],
        "turns": [{"id": t.id, "session": t.session, "sec": t.sec, "time": fmt_tc(t.sec), "text": t.text,
                   "kind": label_kind.get(t.id, "chat"), "item": item_of_turn.get(t.id)}
                  for ts in every.values() for t in ts],
        "quotes": quotes,
        "stats": dict(stats),
        "cost": {"model": model, "input_tokens": din, "output_tokens": dout, "calls": dcalls,
                 "usd": estimate_cost(model, din, dout), "seconds": round(time.monotonic() - t0, 1)},
        "_labels": [lb.__dict__ for lb in labels],
        "_consolidated": [c.__dict__ for c in cons],
    }, frozen


def summary(d: dict) -> str:
    asked = [t for t in d["turns"] if t["kind"] in ASKED_KINDS]
    unplanned = [t for t in asked if t["kind"] != "planned"]
    hows = {}
    for q in d["quotes"]:
        hows[q["how"]] = hows.get(q["how"], 0) + 1
    lines = [f"sections {len([s for s in d['sections'] if s['kind'] != 'instruction'])}: "
             + " | ".join(("✦ " if s["origin"] == "emergent" else "") + s["title"]
                          for s in d["sections"] if s["kind"] != "instruction"),
             f"asked {len(asked)} · unplanned {len(unplanned)} ({100 * len(unplanned) // max(len(asked), 1)}%) · "
             f"standalone {len(d['standalone'])} · quotes {hows}",
             f"stats {d['stats']}",
             f"cost {d['cost']['calls']} calls · {d['cost']['input_tokens']} in / "
             f"{d['cost']['output_tokens']} out · ${(d['cost']['usd'] or 0):.4f} · {d['cost']['seconds']}s"]
    return "\n".join(lines)


async def main_async(a: argparse.Namespace) -> None:
    corpus = Path(a.corpus) if a.corpus else None
    guide_p = Path(a.guide) if a.guide else (corpus / "guide.md" if corpus else None)
    tx = Path(a.transcripts) if a.transcripts else corpus / "transcripts"
    quotes_p = Path(a.quotes) if a.quotes else corpus / "gold.json"
    data = json.loads(quotes_p.read_text(encoding="utf-8"))
    quotes = [{k: q[k] for k in ("session_id", "participant_id", "start", "text") if k in q}
              | ({"sentiment": q["sentiment"]} if q.get("sentiment") else {})
              for q in (data["quotes"] if isinstance(data, dict) else data)]
    names: dict[str, dict] = {}
    if isinstance(data, dict) and "sessions" in data:  # the synthetic gold carries names
        for sid, s in data["sessions"].items():
            names[sid] = {"participants": [{"code": s["participant_id"], "name": s["name"]}]}
    if a.names:
        names = json.loads(Path(a.names).read_text(encoding="utf-8"))
    pname = {p["code"]: p["name"] for v in names.values() for p in v.get("participants", [])}
    for q in quotes:
        q["name"] = pname.get(q["participant_id"], "")
    every, askable, lengths, durations = load_transcripts(tx)
    guide_text = None if a.no_guide or not guide_p else guide_p.read_text(encoding="utf-8")

    client = LLMClient(load_settings())
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    frozen: list[Section] | None = None   # the spine: parsed once per guide, unless --reparse
    for n in range(1, a.runs + 1):
        d, spine = await run_once(client, guide_text, every, askable, lengths, durations, quotes,
                                  names, None if a.reparse else frozen)
        frozen = spine
        path = out / f"run-{n}.json"
        path.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"── run {n} → {path}\n{summary(d)}\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--corpus", default="", help="folder with guide.md, transcripts/, gold.json")
    ap.add_argument("--guide", default="")
    ap.add_argument("--transcripts", default="")
    ap.add_argument("--quotes", default="", help="JSON list (or {quotes:[…]}) with session_id, participant_id, start, text")
    ap.add_argument("--names", default="", help='JSON {sid: {"participants": [{"code","name"}]}}')
    ap.add_argument("--no-guide", action="store_true")
    ap.add_argument("--reparse", action="store_true", help="re-parse the guide every run (default: once)")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--out", required=True)
    asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    main()
