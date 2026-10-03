"""Discussion lens — the code half of the four-step design (Phase 1a spike).

The model judges MEANING (which planned item a turn asks, which unplanned
questions are the same question, what a quote is about). Everything here is
deterministic and decides STRUCTURE, so the same labels always give the same
lens: which sections exist, their order, where a homeless question goes, and
which question a quote answers.

Pure functions over plain dataclasses — no I/O, no model calls — so each rule
is tested on its own (test_structure.py).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

# The promotion rule: a new line of enquiry becomes its own section only if it
# recurs — asked in at least MIN_SESSIONS sessions, at least MIN_ASKS times in
# all. Anything less is a tangent, placed by flow instead. It counts ASKS, not
# distinct questions: how finely the model merges questions is a judgement that
# varies run to run (the spike measured one topic as 4, 2 and 2+2 items over three
# runs), while how often the topic was asked is a fact of the transcripts.
MIN_SESSIONS, MIN_ASKS = 2, 3

# A quote answers the last question asked before it in the same session —
# provided that question was asked recently. Beyond this window the anchor is
# stale (the conversation has moved on) and only the topic can place it.
ANCHOR_WINDOW_S = 240.0

ASKED_KINDS = ("planned", "adlib", "new")


@dataclass
class Turn:
    id: str          # "s1@04:12"
    session: str
    sec: float
    text: str


@dataclass
class Label:
    turn_id: str
    kind: str                  # planned | adlib | new | instruction | chat
    item_id: str = ""          # planned
    section_id: str = ""       # adlib
    cluster: str = ""          # new
    role: str = "core"         # opening | core | closing
    terse: str = ""


@dataclass
class Item:
    id: str
    terse: str
    verbatim: str = ""
    source: str = "planned"    # planned (never asked) | asked (not in guide) | both
    role: str = "core"
    turns: list[str] = field(default_factory=list)
    placed: str = ""           # "flow" when code placed a homeless question


@dataclass
class Section:
    id: str
    title: str
    kind: str = "questions"    # questions | task | instruction
    origin: str = "planned"    # planned | emergent
    heading: str = ""
    items: list[Item] = field(default_factory=list)

    def sessions(self) -> set[str]:
        return {t.split("@")[0] for it in self.items for t in it.turns}


@dataclass
class Consolidated:
    """One unplanned question across sessions, from the consolidate step."""
    turn_ids: list[str]
    terse: str
    where: str                 # a planned section id, or a canonical topic name


@dataclass
class Topic:
    name: str
    nav: str
    heading: str


def tc_seconds(tc: str) -> float:
    total = 0.0
    for part in tc.split(":"):
        total = total * 60 + float(part)
    return total


def turn_session(turn_id: str) -> str:
    return turn_id.split("@")[0]


# ── 1. labels → sections ─────────────────────────────────────────────────────


def apply_labels(spine: list[Section], labels: list[Label], consolidated: list[Consolidated],
                 topics: list[Topic], turns: dict[str, Turn]) -> tuple[list[Section], Counter]:
    """Attach every asked turn to the frozen spine, plus emergent sections.

    Invalid ids from the model are counted and degraded, never trusted: a
    planned label naming an item that does not exist, an ad-lib naming an
    unknown section, a turn id that was never in the input. An unplanned turn
    the consolidate step dropped still appears, as an item of its own.
    """
    stats: Counter = Counter()
    sections = [Section(s.id, s.title, s.kind, "planned", s.heading or s.title,
                        [Item(i.id, i.terse, i.verbatim) for i in s.items]) for s in spine]
    by_item = {it.id: (s, it) for s in sections for it in s.items}
    by_section = {s.id: s for s in sections}
    label_of = {lb.turn_id: lb for lb in labels if lb.turn_id in turns}
    stats["invented_turn_ids"] = sum(1 for lb in labels if lb.turn_id not in turns)

    for lb in label_of.values():
        if lb.kind == "planned":
            hit = by_item.get(lb.item_id)
            if hit is None:
                stats["planned_unknown_item"] += 1
                lb.kind, lb.cluster = "new", lb.cluster or "unplaced"
                continue
            hit[1].turns.append(lb.turn_id)
    for s in sections:
        for it in s.items:
            it.turns.sort(key=lambda t: (turn_session(t), turns[t].sec))
            if it.turns:
                it.source = "both"

    topic_of = {t.name: t for t in topics}
    emergent: dict[str, Section] = {}
    covered: set[str] = set()
    n = 0
    for c in consolidated:
        ids = [t for t in c.turn_ids if t in label_of and label_of[t].kind in ("adlib", "new")
               and t not in covered]
        stats["consolidate_dropped_ids"] += len(c.turn_ids) - len(ids)
        if not ids:
            continue
        covered.update(ids)
        n += 1
        roles = Counter(label_of[t].role for t in ids)
        item = Item(f"a{n}", c.terse, turns[ids[0]].text, "asked", roles.most_common(1)[0][0],
                    sorted(ids, key=lambda t: (turn_session(t), turns[t].sec)))
        if c.where in by_section and by_section[c.where].kind != "instruction":
            by_section[c.where].items.append(item)
        else:
            t = topic_of.get(c.where)
            sec = emergent.setdefault(c.where, Section(
                f"e{len(emergent) + 1}", t.nav if t else c.where, "questions", "emergent",
                t.heading if t else c.where))
            sec.items.append(item)
    for lb in label_of.values():  # unplanned turns the consolidate step never mentioned
        if lb.kind in ("adlib", "new") and lb.turn_id not in covered:
            stats["unconsolidated_turns"] += 1
            n += 1
            item = Item(f"a{n}", lb.terse or turns[lb.turn_id].text[:24], turns[lb.turn_id].text,
                        "asked", lb.role, [lb.turn_id])
            if lb.kind == "adlib" and lb.section_id in by_section:
                by_section[lb.section_id].items.append(item)
            else:
                key = lb.cluster or "unplaced"
                emergent.setdefault(key, Section(f"e{len(emergent) + 1}", key, "questions",
                                                 "emergent", key)).items.append(item)
    return sections + list(emergent.values()), stats


# ── 2. the promotion rule ────────────────────────────────────────────────────


def promote(sections: list[Section], min_sessions: int = MIN_SESSIONS,
            min_asks: int = MIN_ASKS) -> tuple[list[Section], list[Item], list[str]]:
    """Keep an emergent section only if it recurs; return (kept, homeless, dissolved names)."""
    kept: list[Section] = []
    homeless: list[Item] = []
    dissolved: list[str] = []
    for s in sections:
        if s.origin == "emergent" and (len(s.sessions()) < min_sessions
                                       or sum(len(it.turns) for it in s.items) < min_asks):
            homeless.extend(s.items)
            dissolved.append(s.title)
        else:
            kept.append(s)
    return kept, homeless, dissolved


# ── 3. ordering ──────────────────────────────────────────────────────────────


def median_position(section: Section, turns: dict[str, Turn], lengths: dict[str, float]) -> float:
    """Median of the section's ask-sites, each as a fraction of its session."""
    xs = sorted(turns[t].sec / max(lengths.get(turns[t].session, 1.0), 1.0)
                for it in section.items for t in it.turns)
    return xs[len(xs) // 2] if xs else 1.0


def order_sections(sections: list[Section], turns: dict[str, Turn],
                   lengths: dict[str, float]) -> list[Section]:
    """Planned sections keep guide order; each emergent one is inserted before the
    first planned section whose median position comes after its own. With no
    guide every section is emergent and they sort by median position. A leading
    instruction section stays first."""
    head = [s for s in sections[:1] if s.kind == "instruction"]
    rest = [s for s in sections if s not in head]
    planned = [s for s in rest if s.origin == "planned"]
    emergent = sorted((s for s in rest if s.origin == "emergent"),
                      key=lambda s: median_position(s, turns, lengths))
    if not planned:
        return head + emergent
    ordered = list(planned)
    for e in emergent:
        m = median_position(e, turns, lengths)
        at = next((i for i, s in enumerate(ordered) if s.origin == "planned"
                   and s.kind != "instruction" and s.sessions()
                   and median_position(s, turns, lengths) > m), len(ordered))
        ordered.insert(at, e)
    return head + ordered


# ── 4. homeless questions, placed by flow ────────────────────────────────────


def place_by_flow(sections: list[Section], homeless: list[Item],
                  turns: dict[str, Turn]) -> list[Item]:
    """Place each homeless question in the section the session was in when it
    was asked: an opener joins the next section, a closer the previous one, a
    core question the nearer of the two. Votes across ask-sites; a tie, or no
    neighbour at all, leaves it STANDALONE. Returns the standalone items."""
    timeline: dict[str, list[tuple[float, int]]] = {}
    for i, s in enumerate(sections):
        if s.kind == "instruction":
            continue
        for it in s.items:
            for t in it.turns:
                timeline.setdefault(turns[t].session, []).append((turns[t].sec, i))
    for v in timeline.values():
        v.sort()

    standalone: list[Item] = []
    for it in homeless:
        votes: Counter = Counter()
        for t in it.turns:
            sec, tl = turns[t].sec, timeline.get(turns[t].session, [])
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
            continue
        it.placed = "flow"
        target = sections[top[0][0]].items
        target.insert(0, it) if it.role == "opening" else target.append(it)
    return standalone


def build_structure(spine: list[Section], labels: list[Label], consolidated: list[Consolidated],
                    topics: list[Topic], turns: dict[str, Turn],
                    lengths: dict[str, float]) -> tuple[list[Section], list[Item], Counter]:
    """Steps 1–4 in order. Returns (sections, standalone, stats)."""
    sections, stats = apply_labels(spine, labels, consolidated, topics, turns)
    sections, homeless, dissolved = promote(sections)
    for name in dissolved:
        stats[f"dissolved: {name}"] += 1
    sections = order_sections(sections, turns, lengths)
    standalone = place_by_flow(sections, homeless, turns)
    stats["placed_by_flow"] = len(homeless) - len(standalone)
    stats["standalone"] = len(standalone)
    return sections, standalone, stats


# ── quotes: the conversational anchor ────────────────────────────────────────


def anchor(session: str, sec: float, asked: list[tuple[float, str]],
           window: float = ANCHOR_WINDOW_S) -> str | None:
    """The question (item id) a quote answers: the last asked turn at or before it
    in its session, if within the window. `asked` is that session's
    (seconds, item_id) list, sorted."""
    prev = None
    for at, item_id in asked:
        if at > sec:
            break
        prev = (at, item_id)
    if prev is None or sec - prev[0] > window:
        return None
    return prev[1]


def asked_index(sections: list[Section], standalone: list[Item],
                turns: dict[str, Turn]) -> dict[str, list[tuple[float, str]]]:
    """Per session, every asked turn as (seconds, item_id), sorted — the anchors."""
    out: dict[str, list[tuple[float, str]]] = {}
    for it in [it for s in sections for it in s.items] + standalone:
        for t in it.turns:
            out.setdefault(turns[t].session, []).append((turns[t].sec, it.id))
    for v in out.values():
        v.sort()
    return out


def section_of_item(sections: list[Section]) -> dict[str, str]:
    return {it.id: s.id for s in sections for it in s.items}


def decide_route(anchor_section: str | None, semantic_section: str | None,
                 confidence: float, threshold: float = 0.75) -> tuple[str | None, str]:
    """Combine the two signals. Agreement wins outright. On disagreement the topic
    wins only when the model is confident — a participant drifting onto another
    subject is real, but a low-confidence topic call should not override where
    the conversation actually was. Returns (section, how)."""
    if anchor_section and anchor_section == semantic_section:
        return anchor_section, "agree"
    if semantic_section and (anchor_section is None or confidence >= threshold):
        return semantic_section, "topic"
    if anchor_section:
        return anchor_section, "anchor"
    return None, "unrouted"
