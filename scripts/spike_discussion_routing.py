#!/usr/bin/env python3
"""SPIKE — Discussion lens routing de-risk (Phase A).

Backend-only proof for docs/design-discussion-lens.md. Given a project's
extracted quotes and a discussion guide, it:

  1. parses the guide into ~5-12 TERRITORIES (LLM, parse-discussion-guide.md),
  2. routes each quote to a territory or UNROUTED (LLM, batched,
     route-quotes-to-territories.md), matching on each territory's whole field,
  3. prints a report: distilled territories, routed X of Y, per-territory
     density (signal-bar sketch), a sample of routed quotes, and the token/cost
     footprint.

It answers the only real unknown before building the lens: does real evidence
land in the right territory, at what cost, and does conservative-omission read
as honest or broken. NOT wired into the pipeline or the app — a throwaway
harness. Reuses the real LLMClient, so provider/model/keys come from your
environment exactly as the CLI/app resolve them.

Usage:
    .venv/bin/python scripts/spike_discussion_routing.py \
        --project trial-runs/project-ikea/bristlenose-output \
        --guide /path/to/discussion-guide.txt \
        [--batch 25] [--limit 0] [--out spike-report.md]

The guide may be .txt or .md (read directly) or .docx (needs python-docx).
Keep private data private: point --project at whatever you're comfortable
running through your configured provider (Ollama keeps it local).
"""

import argparse
import asyncio
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from bristlenose.config import load_settings
from bristlenose.llm.client import LLMClient
from bristlenose.llm.pricing import estimate_cost

PROMPTS = Path(__file__).resolve().parent.parent / "bristlenose" / "llm" / "prompts"


# ── Structured-output models (spike-local; graduate to models.py if this ships) ──


# Length budgets are a CONTRACT, not a hope — the ≤2-screen sidebar depends on it.
# max_length carries into the provider's structured-output schema (maxLength) and
# validation catches violations; caps have headroom over the prompt's asks
# (terse ≤28, scaffold.terse ≤34, intent ≤100) so normal output passes but a
# runaway string is caught rather than silently blowing the sidebar.


# One over-long label must not sink a whole-guide call (a detailed guide failed
# twice on 'Size/colour/price/material priority', 35 chars). Clip and count.
CLIPPED: list[str] = []


def _clip(v: object, cap: int) -> object:
    if isinstance(v, str) and len(v) > cap:
        CLIPPED.append(v)
        return v[: cap - 1].rstrip() + "…"
    return v


class ScaffoldItem(BaseModel):
    terse: str = Field(max_length=34)  # sidebar disclosure sub-label (prompt: ≤24)

    @field_validator("terse", mode="before")
    @classmethod
    def _clip_terse(cls, v: object) -> object:
        return _clip(v, 34)
    verbatim: str = ""                 # hidden match material — uncapped
    # Reconcile mode only (planned guide ⋈ questions actually asked):
    source: Literal["planned", "asked", "both"] = "planned"
    turns: list[str] = Field(default_factory=list)  # "s3@05:19" — where it was asked
    role: Literal["opening", "core", "closing"] = "core"
    placed: str = ""  # set by CODE, never the model: "flow" = placed by timing


class Territory(BaseModel):
    nav_terse: str = Field(max_length=26)  # sidebar row — orientation (prompt: ≤18)
    heading: str = Field(max_length=56)    # content heading — fuller (prompt: ≤40)
    intent: str = Field(max_length=140)    # content one-liner (prompt: ≤100); match = intent + scaffold
    kind: Literal["questions", "task", "instruction"] = "questions"
    stance_axis: Literal["opinion", "pattern", "none"] = "pattern"
    origin: Literal["planned", "emergent"] = "planned"
    scaffold: list[ScaffoldItem] = Field(default_factory=list)

    @field_validator("nav_terse", mode="before")
    @classmethod
    def _clip_nav(cls, v: object) -> object:
        return _clip(v, 26)

    @field_validator("heading", mode="before")
    @classmethod
    def _clip_heading(cls, v: object) -> object:
        return _clip(v, 56)


class ParsedGuide(BaseModel):
    territories: list[Territory]
    homeless: list[ScaffoldItem] = Field(default_factory=list)  # reconcile: no topical home



class QuoteRoute(BaseModel):
    id: str
    territory_id: str  # "t3" or "UNROUTED"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    margin: float = Field(default=0.0, ge=0.0, le=1.0)


class RouteBatch(BaseModel):
    routes: list[QuoteRoute]


# ── Prompt loading (house format: frontmatter + ## System / ## User) ──────────


def load_prompt(name: str) -> tuple[str, str]:
    """Return (system_prompt, user_template) from a house-format prompt file."""
    text = (PROMPTS / name).read_text(encoding="utf-8")
    # strip YAML frontmatter
    text = re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.DOTALL)
    sys_m = re.search(r"\n## System\n(.*?)(?=\n## User\n)", text, flags=re.DOTALL)
    usr_m = re.search(r"\n## User\n(.*)$", text, flags=re.DOTALL)
    if not sys_m or not usr_m:
        raise SystemExit(f"prompt {name}: missing ## System / ## User sections")
    return sys_m.group(1).strip(), usr_m.group(1).strip()


def fill(template: str, **vars: str) -> str:
    for k, v in vars.items():
        template = template.replace("{" + k + "}", v)
    return template


# ── Guide + quotes loading ────────────────────────────────────────────────────


def load_guide_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in (".txt", ".md"):
        return path.read_text(encoding="utf-8")
    if suffix == ".docx":
        try:
            import docx  # python-docx
        except ImportError:
            raise SystemExit("docx guide needs python-docx (pip install python-docx), "
                             "or export the guide to .txt/.md")
        return "\n".join(p.text for p in docx.Document(str(path)).paragraphs)
    raise SystemExit(f"unsupported guide format: {suffix} (use .txt/.md/.docx)")


_TURN_RE = re.compile(r"^\[([\d:]+)\] \[([a-z]+\d+)\](?: \([^)]*\))? (.*)$")


def load_moderator_turns(transcripts: Path, min_words: int = 3, cap: int = 280) -> str:
    """Moderator turns from transcripts-raw/*.txt as `session@timecode | text` lines.

    Speaker codes live only in the rendered transcripts (session_segments.json
    carries none), so read those. Short turns are dropped; long ones capped.
    """
    lines = []
    for f in sorted(transcripts.glob("s*.txt")):
        sid = f.stem
        for raw in f.read_text(encoding="utf-8").splitlines():
            m = _TURN_RE.match(raw)
            if not m or not m.group(2).startswith("m"):
                continue
            text = m.group(3).strip()
            if len(text.split()) < min_words:
                continue
            lines.append(f"{sid}@{m.group(1)} | {text[:cap]}")
    if not lines:
        raise SystemExit(f"no moderator turns found under {transcripts}")
    return "\n".join(lines)


def load_quotes(project: Path) -> list[dict]:
    candidates = [
        project / ".bristlenose" / "intermediate" / "extracted_quotes.json",
        project / "intermediate" / "extracted_quotes.json",
        project,  # allow passing the json file directly
    ]
    for c in candidates:
        if c.is_file():
            data = json.loads(c.read_text(encoding="utf-8"))
            quotes = data.get("quotes", data) if isinstance(data, dict) else data
            if isinstance(quotes, list) and quotes:
                return quotes
    raise SystemExit(
        f"no extracted_quotes.json under {project} — run analysis first, or pass "
        "the json path directly to --project"
    )


# ── Rendering ─────────────────────────────────────────────────────────────────


def territories_block(guide: ParsedGuide) -> str:
    lines = []
    for i, t in enumerate(guide.territories):
        scaf = " · ".join(s.terse for s in t.scaffold)
        asked = " / ".join(s.verbatim[:90] for s in t.scaffold if s.source != "planned")
        lines.append(
            f"t{i} [{t.kind}/{t.stance_axis}] {t.heading}\n"
            f"    intent: {t.intent}\n"
            f"    covers: {scaf or '(none)'}"
            + (f"\n    asked as: {asked}" if asked else "")
        )
    return "\n".join(lines)


def quotes_block(batch: list[dict], ids: list[str]) -> str:
    out = []
    for qid, q in zip(ids, batch):
        text = (q.get("text") or q.get("verbatim_excerpt") or "").replace("\n", " ").strip()
        out.append(f'{qid} | {q.get("participant_id", "?")} | "{text}"')
    return "\n".join(out)


def bar(n: int, peak: int, width: int = 18) -> str:
    if peak <= 0:
        return ""
    filled = round(width * n / peak)
    return "▓" * filled + "░" * (width - filled)


def tc_seconds(tc: str) -> float:
    total = 0.0
    for part in tc.split(":"):
        total = total * 60 + float(part)
    return total


def session_lengths(transcripts: Path) -> dict[str, float]:
    """Last timecode per session — the denominator for relative position."""
    out = {}
    for f in transcripts.glob("s*.txt"):
        last = 0.0
        for raw in f.read_text(encoding="utf-8").splitlines():
            m = _TURN_RE.match(raw)
            if m:
                last = tc_seconds(m.group(1))
        out[f.stem] = max(last, 1.0)
    return out


# The promotion rule: an emergent section stands alone only if it recurs.
MIN_SESSIONS, MIN_ITEMS = 2, 3


def structure(guide: ParsedGuide, valid_turns: set[str],
              lengths: dict[str, float]) -> tuple[list[ScaffoldItem], Counter]:
    """Code, not the model, decides structure — so it is repeatable.

    1. drop turn ids the model invented; 2. dissolve emergent sections that
    fail the promotion rule (their items become homeless); 3. order emergent
    sections by median relative time among the planned ones; 4. place each
    homeless question by FLOW — the section the session was in when it was
    asked (openers take the next section, closers the previous one); a
    question the timeline cannot place is STANDALONE.
    """
    stats: Counter = Counter()
    every = [it for t in guide.territories for it in t.scaffold] + guide.homeless
    for it in every:
        kept = [x for x in it.turns if x in valid_turns]
        stats["invented_turn_ids"] += len(it.turns) - len(kept)
        it.turns = kept
        it.placed = ""

    has_plan = any(t.origin == "planned" and t.kind != "instruction"
                   for t in guide.territories)
    kept_t: list[Territory] = []
    for t in guide.territories:
        if t.origin == "emergent" and t.kind != "instruction":
            sess = {x.split("@")[0] for it in t.scaffold for x in it.turns}
            if len(sess) < MIN_SESSIONS or len(t.scaffold) < MIN_ITEMS:
                stats["dissolved"] += 1
                stats[f"dissolved: {t.nav_terse} ({len(sess)} sess, {len(t.scaffold)} items)"] += 1
                guide.homeless.extend(t.scaffold)
                continue
        kept_t.append(t)
    if not any(t.kind != "instruction" for t in kept_t):  # nothing survived — keep all
        kept_t = guide.territories

    def rel(turn: str) -> float:
        sid, _, tc = turn.partition("@")
        return tc_seconds(tc) / lengths.get(sid, 1.0)

    def median_pos(t: Territory) -> float:
        xs = sorted(rel(x) for it in t.scaffold for x in it.turns)
        return xs[len(xs) // 2] if xs else 1.0

    head = [t for t in kept_t if t.kind == "instruction" and t is kept_t[0]]
    rest = [t for t in kept_t if t not in head]
    if has_plan:
        ordered = [t for t in rest if t.origin == "planned"]
        for e in sorted((t for t in rest if t.origin == "emergent"), key=median_pos):
            m = median_pos(e)
            at = next((i for i, t in enumerate(ordered)
                       if t.kind != "instruction" and t.origin == "planned"
                       and median_pos(t) > m), len(ordered))
            ordered.insert(at, e)
    else:
        ordered = sorted(rest, key=median_pos)
    guide.territories = head + ordered

    timeline: dict[str, list[tuple[float, int]]] = {}
    for i, t in enumerate(guide.territories):
        if t.kind == "instruction":
            continue
        for it in t.scaffold:
            for x in it.turns:
                sid, _, tc = x.partition("@")
                timeline.setdefault(sid, []).append((tc_seconds(tc), i))
    for v in timeline.values():
        v.sort()

    standalone: list[ScaffoldItem] = []
    for it in guide.homeless:
        votes: Counter = Counter()
        for x in it.turns:
            sid, _, tc = x.partition("@")
            sec = tc_seconds(tc)
            tl = timeline.get(sid, [])
            prev = next((e for e in reversed(tl) if e[0] <= sec), None)
            nxt = next((e for e in tl if e[0] > sec), None)
            if it.role == "opening":
                pick = nxt or prev
            elif it.role == "closing":
                pick = prev or nxt
            elif prev and nxt:
                pick = prev if (prev[1] == nxt[1] or sec - prev[0] <= nxt[0] - sec) else nxt
            else:
                pick = prev or nxt
            if pick:
                votes[pick[1]] += 1
        top = votes.most_common(2)
        if not top or (len(top) == 2 and top[0][1] == top[1][1]):
            standalone.append(it)
            stats["standalone"] += 1
            continue
        it.placed = "flow"
        scaf = guide.territories[top[0][0]].scaffold
        if it.role == "opening":
            scaf.insert(0, it)
        else:
            scaf.append(it)
        stats["placed_by_flow"] += 1
    guide.homeless = []
    return standalone, stats


def emit_guide_tree(emit, guide: ParsedGuide, standalone: list[ScaffoldItem]) -> None:
    """The tight summary — the navigation the lens would show."""
    emit("## The guide as planned and as run")
    emit("   ● asked as planned · ○ planned, never asked · + ad-lib on topic · "
         "↦ placed by flow · ✦ new section · ⌃ opener · ⌄ closer")
    for t in guide.territories:
        tag = "  (instruction)" if t.kind == "instruction" else ""
        new = "✦ " if t.origin == "emergent" else ""
        emit(f"  {new}{t.nav_terse}{tag}")
        for it in t.scaffold:
            sym = "↦" if it.placed == "flow" else {"both": "●", "planned": "○", "asked": "+"}[it.source]
            role = {"opening": " ⌃", "closing": " ⌄"}.get(it.role, "")
            sessions = sorted({x.split("@")[0] for x in it.turns})
            where = f"  {','.join(sessions)}" if sessions else ""
            emit(f"     {sym} {it.terse}{role}{where}")
    if standalone:
        emit("  Standalone — asked, not placeable")
        for it in standalone:
            sessions = sorted({x.split("@")[0] for x in it.turns})
            emit(f"     · {it.terse}  {','.join(sessions)}")
    emit()


def emit_fate_counts(emit, guide: ParsedGuide, standalone: list[ScaffoldItem],
                     stats: Counter) -> None:
    items: Counter = Counter()
    turns: Counter = Counter()
    for t in guide.territories:
        if t.kind == "instruction":
            continue
        for it in t.scaffold:
            if it.placed == "flow":
                fate = "placed by flow"
            elif it.source == "planned":
                fate = "planned, never asked"
            elif it.source == "both":
                fate = "asked as planned"
            elif t.origin == "emergent":
                fate = "ad-lib, new section"
            else:
                fate = "ad-lib on topic"
            items[fate] += 1
            turns[fate] += len(it.turns)
    for it in standalone:
        items["standalone"] += 1
        turns["standalone"] += len(it.turns)
    asked_turns = sum(v for k, v in turns.items())
    unplanned = asked_turns - turns["asked as planned"]
    emit("## Placement — items (question-turns)")
    for fate in ("asked as planned", "planned, never asked", "ad-lib on topic",
                 "ad-lib, new section", "placed by flow", "standalone"):
        emit(f"  {items[fate]:>3} ({turns[fate]:>3})  {fate}")
    emit(f"  → {unplanned} of {asked_turns} asked question-turns were not in the guide "
         f"({100 * unplanned // max(asked_turns, 1)}%)")
    for k, v in sorted(stats.items()):
        emit(f"  · {k}: {v}")
    if CLIPPED:
        emit(f"  · labels over budget, clipped: {len(CLIPPED)} — {'; '.join(CLIPPED)}")
    sig = " | ".join(t.nav_terse for t in guide.territories if t.kind != "instruction")
    emit(f"  signature: {sig}")
    emit()


def emit_anchor_agreement(emit, guide: ParsedGuide, rows) -> None:
    """Second, independent signal: the last reconciled question asked before
    the quote in the same session. Compare it with the semantic route."""
    anchors: dict[str, list[tuple[float, str]]] = {}
    for i, t in enumerate(guide.territories):
        for it in t.scaffold:
            for turn in it.turns:
                sid, _, tc = turn.partition("@")
                anchors.setdefault(sid, []).append((tc_seconds(tc), f"t{i}"))
    for v in anchors.values():
        v.sort()
    agree = disagree = no_anchor = 0
    diffs = []
    for dest, q, _r in rows:
        start = q.get("start_timecode")
        prior = [tid for sec, tid in anchors.get(q.get("session_id", ""), [])
                 if start is not None and sec <= float(start)]
        anchor = prior[-1] if prior else None
        if anchor is None:
            no_anchor += 1
        elif anchor == dest:
            agree += 1
        else:
            disagree += 1
            text = (q.get("text") or "").replace("\n", " ")[:90]
            diffs.append(f"  route {dest:>8} · anchor {anchor:>3} · {q.get('participant_id')} "
                         f"@{int(float(start))//60:02d}:{int(float(start))%60:02d} · {text}")
    emit(f"## Semantic route vs conversational anchor — agree {agree} · disagree "
         f"{disagree} · no anchor {no_anchor}")
    for d in diffs:
        emit(d)
    emit()


# ── Orchestration ─────────────────────────────────────────────────────────────


async def run(args: argparse.Namespace) -> str:
    settings = load_settings()  # CLI resolution: --llm → env → current provider → keychain
    client = LLMClient(settings)
    report: list[str] = []

    def emit(line: str = "") -> None:
        print(line)
        report.append(line)

    emit(f"# Discussion-routing spike — {args.project}")
    emit(f"provider={settings.llm_provider}  guide={Path(args.guide).name if args.guide else 'NONE'}")
    emit()

    # 1. parse the guide -------------------------------------------------------
    guide_text = (load_guide_text(Path(args.guide)) if args.guide
                  else "(no guide was supplied — build the guide from the questions asked)")
    if args.transcripts:
        asked = load_moderator_turns(Path(args.transcripts))
        emit(f"reconcile mode: {asked.count(chr(10)) + 1} moderator turns from {args.transcripts}")
        p_sys, p_usr = load_prompt("reconcile-discussion-guide.md")
        user = fill(p_usr, guide_text=guide_text, asked_block=asked)
    else:
        p_sys, p_usr = load_prompt("parse-discussion-guide.md")
        user = fill(p_usr, guide_text=guide_text)
    t0 = time.monotonic()
    guide = await client.analyze(
        system_prompt=p_sys,
        user_prompt=user,
        response_model=ParsedGuide,
        max_tokens=12000,
    )
    parse_s = time.monotonic() - t0
    routable = [i for i, t in enumerate(guide.territories) if t.kind != "instruction"]
    emit(f"## Distilled guide — {len(guide.territories)} territories "
         f"({len(routable)} routable) in {parse_s:.1f}s")
    for i, t in enumerate(guide.territories):
        tag = "  (instruction — quarantined)" if t.kind == "instruction" else ""
        emit(f"  t{i}  {t.heading}  [{t.kind}/{t.stance_axis}]  ·{len(t.scaffold)} folded{tag}")
    emit()
    standalone: list[ScaffoldItem] = []
    if args.transcripts:
        valid = {ln.split(" | ", 1)[0] for ln in asked.splitlines()}
        standalone, stats = structure(guide, valid, session_lengths(Path(args.transcripts)))
        routable = [i for i, t in enumerate(guide.territories) if t.kind != "instruction"]
        emit_guide_tree(emit, guide, standalone)
        emit_fate_counts(emit, guide, standalone, stats)

    # 2. route quotes in batches ----------------------------------------------
    quotes = load_quotes(Path(args.project))
    if args.limit:
        quotes = quotes[: args.limit]
    r_sys, r_usr = load_prompt("route-quotes-to-territories.md")
    tblock = territories_block(guide)
    ids = [f"q{i}" for i in range(len(quotes))]

    counts: dict[str, int] = {f"t{i}": 0 for i in range(len(guide.territories))}
    counts["UNROUTED"] = 0
    routed_samples: dict[str, list[str]] = {}
    low_margin = 0
    # A quote the model skipped, or routed to an id that doesn't exist (or to a
    # quarantined instruction territory), is NOT the same as a considered
    # UNROUTED — count them apart so a collapse can't hide as conservatism.
    missing = invalid = to_instruction = 0
    table: list[str] = []
    routed_rows: list[tuple[str, dict, object]] = []  # (dest, quote, route)

    t0 = time.monotonic()
    batches = [
        (ids[i : i + args.batch], quotes[i : i + args.batch])
        for i in range(0, len(quotes), args.batch)
    ]
    for n, (bids, bq) in enumerate(batches, 1):
        result: RouteBatch = await client.analyze(
            system_prompt=r_sys,
            user_prompt=fill(r_usr, territories_block=tblock, quotes_block=quotes_block(bq, bids)),
            response_model=RouteBatch,
            max_tokens=4000,
        )
        by_id = {r.id: r for r in result.routes}
        for qid, q in zip(bids, bq):
            r = by_id.get(qid)
            if r is None:
                missing += 1
                dest = "UNROUTED"
            elif r.territory_id not in counts:
                invalid += 1
                dest = "UNROUTED"
            elif (r.territory_id != "UNROUTED"
                  and guide.territories[int(r.territory_id[1:])].kind == "instruction"):
                to_instruction += 1
                dest = "UNROUTED"
            else:
                dest = r.territory_id
            routed_rows.append((dest, q, r))
            text = (q.get("text") or "").replace("\n", " ").strip()
            conf = f"{r.confidence:.2f}/{r.margin:.2f}" if r else "—"
            table.append(f"| {dest} | {conf} | {q.get('participant_id', '?')} | {text[:110]} |")
            counts[dest] += 1
            if r and dest != "UNROUTED" and r.margin and r.margin < 0.15:
                low_margin += 1
            if dest != "UNROUTED":
                routed_samples.setdefault(dest, [])
                if len(routed_samples[dest]) < 3:
                    routed_samples[dest].append(f'{q.get("participant_id","?")}: "{text[:120]}"')
        print(f"  … routed batch {n}/{len(batches)}", file=sys.stderr)
    route_s = time.monotonic() - t0

    # 3. report ---------------------------------------------------------------
    total = len(quotes)
    unrouted = counts["UNROUTED"]
    routed = total - unrouted
    peak = max((counts[f"t{i}"] for i in routable), default=0)
    emit(f"## Routing — {routed} of {total} quotes routed "
         f"({100*routed//max(total,1)}%), {unrouted} UNROUTED, in {route_s:.1f}s")
    emit(f"   near-ties (margin<0.15): {low_margin}   ·   batches: {len(batches)}")
    emit(f"   of the UNROUTED: skipped by model {missing} · unknown id {invalid} "
         f"· sent to an instruction territory {to_instruction}")
    emit()
    emit("## Evidence density by territory (the signal bars)")
    for i, t in enumerate(guide.territories):
        if t.kind == "instruction":
            continue
        c = counts[f"t{i}"]
        emit(f"  {c:>4}  {bar(c, peak)}  {t.heading}")
    emit(f"  {unrouted:>4}  {'·'*0}  UNROUTED (stay in the Quotes lens)")
    emit()
    emit("## Sample routed quotes (eyeball precision — are these in-territory?)")
    for i, t in enumerate(guide.territories):
        s = routed_samples.get(f"t{i}")
        if not s:
            continue
        emit(f"### t{i} {t.heading}")
        for line in s:
            emit(f"  - {line}")
    emit()
    if args.transcripts:
        emit_anchor_agreement(emit, guide, routed_rows)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps({
            "guide": guide.model_dump(),
            "standalone": [it.model_dump() for it in standalone],
            "routes": [{"dest": d, "session_id": q.get("session_id"),
                        "participant_id": q.get("participant_id"),
                        "start": q.get("start_timecode"), "text": q.get("text"),
                        "confidence": getattr(r, "confidence", None),
                        "margin": getattr(r, "margin", None)} for d, q, r in routed_rows],
        }, ensure_ascii=False, indent=1), encoding="utf-8")
    emit("## Every routing (dest | confidence/margin | participant | quote)")
    emit("| dest | c/m | pid | quote |")
    emit("|---|---|---|---|")
    for row in table:
        emit(row)
    emit()
    tr = client.tracker
    usd = estimate_cost(settings.llm_model, tr.input_tokens, tr.output_tokens)
    emit(f"## Cost footprint\n  {settings.llm_model}: {tr.input_tokens} in / "
         f"{tr.output_tokens} out tokens over {tr.calls} calls"
         + (f" ≈ ${usd:.4f}" if usd is not None else " (model not in pricing table)"))
    emit(f"  parse {parse_s:.1f}s · route {route_s:.1f}s · {len(batches)+1} LLM calls")

    return "\n".join(report)


def main() -> None:
    ap = argparse.ArgumentParser(description="Discussion lens routing spike")
    ap.add_argument("--project", required=True,
                    help="path to <project>/bristlenose-output (or an extracted_quotes.json)")
    ap.add_argument("--guide", default="",
                    help="discussion guide .txt/.md/.docx (omit with --transcripts: no-guide mode)")
    ap.add_argument("--transcripts", default="",
                    help="transcripts-raw/ dir: reconcile the guide with the questions actually asked")
    ap.add_argument("--json-out", default="", help="write the guide + every route as JSON")
    ap.add_argument("--batch", type=int, default=25, help="quotes per routing call")
    ap.add_argument("--limit", type=int, default=0, help="cap number of quotes (0 = all)")
    ap.add_argument("--out", default="", help="write the full report to this markdown file")
    args = ap.parse_args()

    report = asyncio.run(run(args))
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"\nreport → {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
