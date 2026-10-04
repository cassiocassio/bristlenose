"""Discussion lens — the pipeline stage: the four-step design, behind its off switch.

  1. PARSE the guide once into a frozen spine (sections → planned items; ids by code)
  2. CLASSIFY each session's moderator turns against it (one call per session),
     then CONSOLIDATE the unplanned residue across sessions (one small call)
  3. STRUCTURE in code (``structure.py``): promotion rule, ordering, flow placement
  4. ROUTE quotes: the conversational anchor (code) + the topic (batched call)

Built from the Phase 1a spike (``experiments/discussion-lens/``), which passed
its exit criteria on a synthetic answer key; the reviews of 3 Oct 2026 are
folded in (plan §9): failure is recorded per session and never read as "no
questions asked", skipped turns are counted and kept visible, quotes are keyed
by (session, participant, start), the record carries codes not names, prompts
are assembled with ``.format`` on ``wrap_untrusted`` blocks, and model output
fed to the next step stays wrapped.

OPTIONAL: it never abandons the run. A failure shows on the lens (the record's
``status`` and per-session ``state``), not as a run bucket that would turn a
good project Partial (§9.A).
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from collections.abc import Collection, Sequence
from pathlib import Path

from bristlenose.discussion import structure as st
from bristlenose.discussion.guide import NO_GUIDE_SHA, Guide, find_guide
from bristlenose.discussion.models import (
    ConsolidateOut,
    DiscussionRecord,
    RecordAsk,
    RecordItem,
    RecordQuote,
    RecordSection,
    RecordSession,
    RecordSpineItem,
    RecordSpineSection,
    RecordTurn,
    RouteBatchOut,
    RouteOut,
    SessionLabelsOut,
    SessionState,
    SpineOut,
)
from bristlenose.discussion.moderator import MIN_WORDS, moderator_turns
from bristlenose.events import StageFailure, StageOutcome
from bristlenose.llm import telemetry as _llm_telemetry
from bristlenose.llm.boundary import wrap_untrusted
from bristlenose.llm.client import LLMClient
from bristlenose.llm.output_language import output_language_steer
from bristlenose.llm.prompts import get_prompt_template
from bristlenose.models import ExtractedQuote, FullTranscript, SpeakerRole
from bristlenose.run_lifecycle import _build_cause
from bristlenose.utils.timecodes import format_timecode

logger = logging.getLogger(__name__)

STAGE_ID = "discussion"                         # manifest / Cause.stage vocabulary
TELEMETRY_ID = "s11b_discussion"                # per-run calls: parse, consolidate, route
TELEMETRY_CLASSIFY_ID = "s11c_discussion_classify"  # one call per session (pricing: per-session)
ROUTE_BATCH = 25
_PROGRAMMING_ERRORS = (TypeError, KeyError, AttributeError, NameError, AssertionError, IndexError)


def quotes_sha(quotes: list[ExtractedQuote]) -> str:
    """What the record was built from, so a stale record is refused at import."""
    h = hashlib.sha256()
    for q in sorted(quotes, key=lambda q: (q.session_id, q.participant_id, q.start_timecode)):
        h.update(f"{q.session_id}|{q.participant_id}|{q.start_timecode:.2f}|{q.text}\n".encode())
    return h.hexdigest()


def _turn_id(sid: str, sec: float, seen: set[str]) -> str:
    tid = f"{sid}@{format_timecode(sec)}"
    while tid in seen:  # two turns in one second: keep both
        tid += "'"
    seen.add(tid)
    return tid


def _session_number(sid: str) -> int:
    m = re.search(r"\d+", sid)
    return int(m.group()) if m else 0


# ── the four LLM steps ───────────────────────────────────────────────────────


async def _parse_guide(client: LLMClient, guide: Guide) -> list[st.Section]:
    tmpl = get_prompt_template("discussion-parse-guide")
    out = await client.analyze(
        system_prompt=tmpl.system,  # transcribes the guide: no language steer
        user_prompt=tmpl.user.format(guide=wrap_untrusted("guide", guide.text)),
        response_model=SpineOut, prompt_template=tmpl,
    )
    spine: list[st.Section] = []
    for i, sec in enumerate(out.sections, 1):  # ids by CODE, in guide order
        spine.append(st.Section(f"s{i}", sec.title, sec.kind, "planned", sec.title,
                                [st.Item(f"s{i}.{j}", it.terse or it.text[:24], it.text)
                                 for j, it in enumerate(sec.items, 1)]))
    return spine


def _spine_block(spine: list[st.Section]) -> str:
    lines: list[str] = []
    for s in spine:
        lines.append(f"{s.id} [{s.kind}] {s.title}")
        lines += [f"  {it.id} {it.verbatim}" for it in s.items]
    return "\n".join(lines) or "(no guide — there are no planned sections; every question is `new`)"


async def _classify(client: LLMClient, spine: list[st.Section], turns: list[st.Turn]) -> list[st.Label]:
    tmpl = get_prompt_template("discussion-classify-turns")
    out = await client.analyze(
        system_prompt=tmpl.system + output_language_steer(),
        user_prompt=tmpl.user.format(
            spine=wrap_untrusted("spine", _spine_block(spine)),
            turns=wrap_untrusted("turns", "\n".join(f"{t.id} | {t.text}" for t in turns))),
        response_model=SessionLabelsOut, prompt_template=tmpl,
    )
    return [st.Label(lb.turn_id, lb.kind, lb.item_id, lb.section_id, lb.cluster, lb.role, lb.terse)
            for lb in out.labels]


async def _consolidate(client: LLMClient, labels: list[st.Label], turns: dict[str, st.Turn],
                       spine: list[st.Section]) -> tuple[list[st.Consolidated], list[st.Topic]]:
    rows = [f"{lb.turn_id} | {lb.section_id if lb.kind == 'adlib' else 'new: ' + (lb.cluster or '?')} "
            f"| {turns[lb.turn_id].text}"
            for lb in labels if lb.kind in ("adlib", "new") and lb.turn_id in turns]
    if not rows:
        return [], []
    tmpl = get_prompt_template("discussion-consolidate")
    planned = "\n".join(f"{x.id} {x.title}" for x in spine if x.kind != "instruction") or "(no guide)"
    out = await client.analyze(
        system_prompt=tmpl.system + output_language_steer(),
        user_prompt=tmpl.user.format(planned=wrap_untrusted("planned", planned),
                                     questions=wrap_untrusted("questions", "\n".join(rows))),
        response_model=ConsolidateOut, prompt_template=tmpl,
    )
    return ([st.Consolidated(c.turn_ids, c.terse, c.where) for c in out.items],
            [st.Topic(t.name, t.nav or t.name, t.heading or t.name) for t in out.topics])


async def _route(client: LLMClient, sections: list[st.Section],
                 keyed: list[tuple[str, ExtractedQuote]]) -> dict[str, RouteOut]:
    tmpl = get_prompt_template("discussion-route-quotes")
    block = "\n".join(f"{s.id} | {s.heading or s.title} | " + "; ".join(it.terse for it in s.items if it.turns)
                      for s in sections if s.kind != "instruction")

    async def one(batch: list[tuple[str, ExtractedQuote]]) -> RouteBatchOut:
        qb = "\n".join(f"{k} | {q.text}" for k, q in batch)
        return await client.analyze(
            system_prompt=tmpl.system,
            user_prompt=tmpl.user.format(sections=wrap_untrusted("sections", block),
                                         quotes=wrap_untrusted("quotes", qb)),
            response_model=RouteBatchOut, prompt_template=tmpl,
        )
    outs = await asyncio.gather(*(one(keyed[i:i + ROUTE_BATCH]) for i in range(0, len(keyed), ROUTE_BATCH)),
                                return_exceptions=True)
    failures = [o for o in outs if isinstance(o, BaseException)]
    routed = {r.quote_id: r for o in outs if isinstance(o, RouteBatchOut) for r in o.routes}
    if failures:  # one bad batch does not discard the others; the caller records it
        raise _PartialRouteError(routed, failures[0])
    return routed


class _PartialRouteError(Exception):
    def __init__(self, routed: dict[str, RouteOut], cause: BaseException) -> None:
        super().__init__(type(cause).__name__)
        self.routed, self.cause = routed, cause


# ── the stage ────────────────────────────────────────────────────────────────


async def run_discussion(
    transcripts: Sequence[FullTranscript],
    quotes: list[ExtractedQuote],
    project_dir: Path,
    llm_client: LLMClient,
    concurrency: int = 3,
    whole_split: Collection[str] = frozenset(),
) -> tuple[DiscussionRecord, StageOutcome]:
    """Build the discussion record. Never raises for an LLM failure: each one is
    a ``StageFailure`` on the outcome and a degraded state on the record.

    ``whole_split``: sessions whose speakers were split over the whole
    transcript (``moderator.whole_transcript_split``); the under-attribution
    check is skipped for them."""
    outcome = StageOutcome(attempted=len(transcripts))
    record = DiscussionRecord()
    stats: dict[str, int] = {}

    def fail(exc: BaseException, session_id: str | None = None) -> None:
        # The exception TYPE only: a ValidationError's message can echo guide text (§9.D).
        # A programming error keeps its traceback (source lines, never values),
        # or it reads as one more provider hiccup in the log.
        logger.log(logging.ERROR if isinstance(exc, _PROGRAMMING_ERRORS) else logging.WARNING,
                   "discussion: %s failed: %s", session_id or "stage", type(exc).__name__,
                   exc_info=isinstance(exc, _PROGRAMMING_ERRORS))
        outcome.failed.append(StageFailure(session_id=session_id, cause=_build_cause(
            exc, stage=STAGE_ID, provider=llm_client.provider, session_id=session_id)))

    # 1. the guide → frozen spine
    guide = find_guide(project_dir)
    spine: list[st.Section] = []
    record.guide_sha = guide.sha if guide else NO_GUIDE_SHA
    if guide is not None:
        stats["guide_files_ignored"] = len(guide.ignored)
        # A guide that is there but unused is said so, never read as "no guide".
        record.guide_problem = guide.problem
        if guide.text:
            try:
                with _llm_telemetry.stage(TELEMETRY_ID):
                    spine = await _parse_guide(llm_client, guide)
                if not spine:  # read, but the model found no structure in it
                    record.guide_problem = "empty_parse"
            except Exception as exc:  # noqa: BLE001 — optional stage: record, never abandon
                fail(exc)
                stats["guide_parse_failed"] = 1
        if record.guide_problem:
            stats[f"guide_{record.guide_problem}"] = 1
    record.guide = bool(spine)

    # 2a. moderator turns per session, with the reliability checks
    every: dict[str, list[st.Turn]] = {}
    askable: dict[str, list[st.Turn]] = {}
    speaker_of: dict[str, str] = {}
    lengths: dict[str, float] = {}
    for t in transcripts:
        sid = t.session_id
        mt = moderator_turns(t, whole_split=sid in whole_split)
        lengths[sid] = max(t.duration_seconds, (t.segments[-1].end_time if t.segments else 0.0), 1.0)
        seen: set[str] = set()
        all_mod = [s for s in t.segments if s.speaker_role == SpeakerRole.RESEARCHER
                   or (s.speaker_role == SpeakerRole.UNKNOWN and s.speaker_code.startswith("m"))]
        for seg in all_mod:
            tid = _turn_id(sid, seg.start_time, seen)
            turn = st.Turn(tid, sid, seg.start_time, seg.text.strip())
            speaker_of[tid] = seg.speaker_code or mt.code
            every.setdefault(sid, []).append(turn)
            if mt.reliable and len(turn.text.split()) >= MIN_WORDS:
                askable.setdefault(sid, []).append(turn)
        participants = sorted({s.speaker_code for s in t.segments
                               if s.speaker_role == SpeakerRole.PARTICIPANT and s.speaker_code})
        state: SessionState = ("ok" if mt.reliable else
                               "no_moderator" if mt.reason == "no_moderator" else "moderator_unreliable")
        if not mt.reliable:
            stats[mt.reason] = stats.get(mt.reason, 0) + 1
        record.sessions.append(RecordSession(
            id=sid, number=_session_number(sid), participants=participants or [t.participant_id],
            duration=format_timecode(lengths[sid]), seconds=lengths[sid], state=state))
    turns = {x.id: x for ts in askable.values() for x in ts}

    # 2b. classify each reliable session (bounded concurrency), per-session failure
    sem = asyncio.Semaphore(concurrency)

    async def classify_one(sid: str, ts: list[st.Turn]) -> tuple[str, list[st.Label] | None]:
        async with sem:
            try:
                with _llm_telemetry.stage(TELEMETRY_CLASSIFY_ID), _llm_telemetry.session(sid):
                    got = await _classify(llm_client, spine, ts)
                sent = {t.id for t in ts}
                if not any(lb.turn_id in sent for lb in got):
                    # an empty reply must not read as "no questions asked"
                    raise ValueError("classify labelled none of the turns it was sent")
                return sid, got
            except Exception as exc:  # noqa: BLE001
                fail(exc, sid)
                return sid, None

    results = await asyncio.gather(*(classify_one(sid, ts) for sid, ts in askable.items()))
    labels: list[st.Label] = []
    failed_turns: set[str] = set()  # asked in a session whose call failed: shown, never hidden as chat
    for sid, ls in results:
        if ls is None:
            next(s for s in record.sessions if s.id == sid).state = "failed"
            for x in askable[sid]:
                turns.pop(x.id, None)
                failed_turns.add(x.id)
            continue
        labels.extend(ls)
    outcome.succeeded = sum(1 for s in record.sessions if s.state == "ok")

    # 2c. consolidate (one call); a failure leaves each unplanned turn its own item
    cons: list[st.Consolidated] = []
    topics: list[st.Topic] = []
    try:
        with _llm_telemetry.stage(TELEMETRY_ID):
            cons, topics = await _consolidate(llm_client, labels, turns, spine)
    except Exception as exc:  # noqa: BLE001
        fail(exc)
        stats["consolidate_failed"] = 1

    # 3. structure in code
    sections, standalone, sstats = st.build_structure(spine, labels, cons, topics, turns, lengths)
    for k, v in sstats.items():
        stats[k] = stats.get(k, 0) + int(v)

    # 4. quotes: anchor (code) + topic (model) → decide_route
    sec_of = st.section_of_item(sections)
    asked = st.asked_index(sections, standalone, turns)
    keyed = [(f"q{i}", q) for i, q in enumerate(quotes)]  # call-local key only; the record keys by identity
    topical: dict[str, RouteOut] = {}
    if sections and keyed:
        try:
            with _llm_telemetry.stage(TELEMETRY_ID):
                topical = await _route(llm_client, sections, keyed)
        except _PartialRouteError as part:  # anchor-only for the failed batches
            topical = part.routed
            fail(part.cause)
            stats["route_failed"] = 1
        except Exception as exc:  # noqa: BLE001
            fail(exc)
            stats["route_failed"] = 1
    valid = {s.id for s in sections if s.kind != "instruction"}
    for k, q in keyed:
        before = [(at, iid) for at, iid in asked.get(q.session_id, []) if at <= q.start_timecode]
        a_item = st.anchor(q.session_id, q.start_timecode, asked.get(q.session_id, []))
        a_sec = sec_of.get(a_item) if a_item else None
        r = topical.get(k)
        t_sec = r.section_id if r and r.section_id in valid else None
        if r is None or (r.section_id != "UNROUTED" and t_sec is None):
            stats["route_missing_or_invalid"] = stats.get("route_missing_or_invalid", 0) + 1
        section, how = st.decide_route(a_sec, t_sec, r.confidence if r else 0.0)
        record.quotes.append(RecordQuote(
            session=q.session_id, participant=q.participant_id, sec=q.start_timecode,
            time=format_timecode(q.start_timecode), text=q.text,
            after_item=before[-1][1] if before else None, section=section, how=how,
            sentiment=q.sentiment.value if q.sentiment else None))
    routed = sum(1 for q in record.quotes if q.section)
    stats["quotes_routed"], stats["quotes_unrouted"] = routed, len(record.quotes) - routed

    # the record
    def item_json(it: st.Item) -> RecordItem:
        return RecordItem(id=it.id, terse=it.terse, verbatim=it.verbatim, source=it.source,  # type: ignore[arg-type]
                          placed=it.placed, role=it.role,  # type: ignore[arg-type]
                          asks=[RecordAsk(turn=x, session=turns[x].session, sec=turns[x].sec) for x in it.turns])

    record.spine = [RecordSpineSection(
        id=s.id, title=s.title, kind=s.kind,  # type: ignore[arg-type]
        # instruction sections keep their title only — not evidence, not exported (§9.C)
        items=[] if s.kind == "instruction" else [RecordSpineItem(id=i.id, terse=i.terse, text=i.verbatim)
                                                  for i in s.items])
        for s in spine]
    record.sections = [RecordSection(id=s.id, title=s.title, heading=s.heading, kind=s.kind,  # type: ignore[arg-type]
                                     origin=s.origin, items=[item_json(i) for i in s.items])  # type: ignore[arg-type]
                       for s in sections]
    record.standalone = [item_json(i) for i in standalone]
    item_of = {x: it.id for s in sections for it in s.items for x in it.turns}
    item_of.update({x: it.id for it in standalone for x in it.turns})
    kind_of = {lb.turn_id: lb.kind for lb in labels}
    state_of = {s.id: s.state for s in record.sessions}
    for sid, ts in every.items():
        for x in ts:
            # never read as chat: a turn we could not classify, including every
            # askable-length turn of a session whose moderator we could not trust
            unread = (x.id in turns or x.id in failed_turns
                      or (state_of.get(sid) != "ok" and len(x.text.split()) >= MIN_WORDS))
            kind = kind_of.get(x.id, "unclassified" if unread else "chat")
            record.turns.append(RecordTurn(id=x.id, session=sid, sec=x.sec, time=format_timecode(x.sec),
                                           text=x.text, kind=kind, item=item_of.get(x.id),  # type: ignore[arg-type]
                                           speaker=speaker_of.get(x.id, "")))
    record.quotes_sha = quotes_sha(quotes)
    record.stats = stats
    ok = sum(1 for s in record.sessions if s.state == "ok")
    record.status = ("failed" if ok == 0 and record.sessions else
                     "partial" if outcome.failed or ok < len(record.sessions) or record.guide_problem
                     else "complete")
    return record, outcome
