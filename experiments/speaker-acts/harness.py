"""Drive every act the speaker menus permit, and record what each does.

Run from the repo root:  .venv/bin/python experiments/speaker-acts/harness.py

For each scenario, on a fresh copy of the synthetic study (``world.py``):

    baseline -> act -> [snapshot] -> re-import -> [snapshot] -> undo -> [snapshot]

The acts go through the real HTTP routes with the payloads the picker sends
(``frontend/src/utils/speakerNames.ts``, ``personPicker.ts``). A snapshot is
every project GET the API has, plus database row counts and the session
registry. ``facts()`` reduces a snapshot to the handful of things a researcher
can see; the rules in ``judge()`` are the desired end state, written before
the actuals were read. Output: ``results.json`` and ``report.html`` here.
"""

from __future__ import annotations

import html
import json
import re
import sys
import tempfile
import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent))

import world  # noqa: E402


def _isolate() -> None:
    """No key, no .env, no keychain: the suite's own isolation, applied here because
    this runs outside pytest. Without it a snapshot's GET /signals/elaborations
    makes a real, paid LLM call (it did, on the first run: 28 of them)."""
    from _pytest.monkeypatch import MonkeyPatch

    from tests.conftest import _isolate_machine_config

    base = Path(tempfile.mkdtemp(prefix="speaker-acts-iso-"))

    class _Factory:
        def getbasetemp(self) -> Path:
            return base

        def mktemp(self, name: str) -> Path:
            return Path(tempfile.mkdtemp(prefix=name + "-", dir=base))

    mp = MonkeyPatch()
    for var in list(__import__("os").environ):
        if var.startswith("BRISTLENOSE_") or var.endswith("_API_KEY"):
            mp.delenv(var)
    _isolate_machine_config(mp, _Factory())  # type: ignore[arg-type]


_isolate()

from bristlenose.server.app import create_app  # noqa: E402
from tests.conftest import AuthTestClient  # noqa: E402

P = "/api/projects/1"
ALL_QUOTES = {world.quote_id(s, start) for s, start, *_ in world.QUOTES}
KIND = {"researcher": "moderator", "observer": "observer", "participant": "participant"}


# --------------------------------------------------------------------------- world


class Study:
    """One fresh study and its client."""

    def __init__(self) -> None:
        self.root = world.build(Path(tempfile.mkdtemp(prefix="speaker-acts-")))
        self.client = AuthTestClient(create_app(project_dir=self.root, dev=True, db_url="sqlite://"))
        self.log: list[tuple[str, str, int, str]] = []
        # A researcher's own work, so a lost quote takes something with it.
        self.client.put(f"{P}/starred", json={"q-p1-10": True, "q-p2-10": True})
        tags = self.client.get(f"{P}/tags").json()  # PUT replaces the whole map
        tags["q-p1-30"] = [*tags.get("q-p1-30", []), "slow"]
        tags["q-p3-20"] = [*tags.get("q-p3-20", []), "trust"]
        self.client.put(f"{P}/tags", json=tags)
        self.client.put(f"{P}/edits", json={"q-p1-50": "So I dragged it again and had two copies."})

    # -- reads

    def get(self, path: str) -> Any:
        resp = self.client.get(P + path)
        if resp.status_code != 200:
            return {"__status__": resp.status_code}
        return resp.json() if "json" in resp.headers.get("content-type", "") else resp.text

    def slots(self, sid: str) -> dict[str, dict]:
        sessions = self.get("/sessions")["sessions"]
        return {sp["slot_code"]: sp for s in sessions if s["session_id"] == sid for sp in s["speakers"]}

    def state(self, sid: str, slot: str) -> dict:
        """The slot as the picker holds it (``SpeakerNameState``)."""
        sp = self.slots(sid)[slot]
        return {"person": sp["person"], "full_name": sp["full_name"], "short_name": sp["short_name"],
                "confirmed": sp["name_confirmed"], "kind": KIND[sp["role"]]}

    def paragraph(self, sid: str, position: int) -> dict:
        return self.get(f"/transcripts/{sid}")["segments"][position]

    # -- writes, as the client sends them

    def send(self, method: str, path: str, body: dict | None = None) -> Any:
        resp = self.client.request(method, P + path, json=body)
        self.log.append((method, path, resp.status_code, json.dumps(body) if body else ""))
        try:
            return resp.json()
        except ValueError:
            return None

    def put_slot(self, sid: str, slot: str, body: dict) -> Any:
        return self.send("PUT", f"/sessions/{sid}/speakers/{slot}", body)

    def write_state(self, sid: str, slot: str, state: dict, other: dict) -> None:
        """``writeSlot``: one request carries the whole state."""
        team_code = slot[:1] in ("m", "o")
        via_slot = team_code or state["kind"] != "participant" or state["kind"] != other["kind"]
        if not via_slot:
            people = self.get("/people")
            entry = people.get(slot, {"full_name": "", "short_name": "", "role": ""})
            if (entry["full_name"], entry["short_name"]) != (state["full_name"], state["short_name"]):
                self.send("PUT", "/people", {**people, slot: {
                    **entry, "full_name": state["full_name"], "short_name": state["short_name"]}})
            self.put_slot(sid, slot, {"confirmed": state["confirmed"]})
            return
        # The picker sends ``kind`` on every pick, the slot's own role included.
        kind = {"kind": state["kind"]}
        if state["person"]:
            body = {"person": state["person"], **({"create": True} if state.get("create") else {}),
                    **kind, "full_name": state["full_name"], "short_name": state["short_name"],
                    "confirmed": state["confirmed"]}
        elif state["kind"] == "participant":
            body = {"kind": "participant", "full_name": state["full_name"],
                    "short_name": state["short_name"], "confirmed": state["confirmed"]}
        else:
            body = {"clear": True, **kind}
        self.put_slot(sid, slot, body)

    def move_paragraph(self, sid: str, position: int, *, slot: str = "", new: str | None = None) -> int | None:
        seg = self.paragraph(sid, position)
        verify = " ".join(seg["text"].split()[:6])
        body: dict = {"position": position, "verify": verify}
        body.update({"new": new} if new else {"slot": slot})
        out = self.send("POST", f"/transcripts/{sid}/reassign", body)
        return out.get("id") if isinstance(out, dict) else None

    def reimport(self) -> None:
        from bristlenose.server.importer import import_project

        db = self.client.app.state.db_factory()
        try:
            import_project(db, self.root)
            db.commit()
        finally:
            db.close()

    # -- the snapshot

    def snapshot(self) -> dict:
        snap: dict[str, Any] = {}
        spec = self.client.app.openapi()
        for path, item in sorted(spec["paths"].items()):
            if "get" not in item or not path.startswith("/api/projects/{project_id}"):
                continue
            params = set(re.findall(r"\{(\w+)\}", path)) - {"project_id"}
            if params - {"session_id"} or any(x in path for x in ("/export", "/miro", "/screens/still")):
                continue
            for sid in (list(world.TRANSCRIPTS) if params else [""]):
                url = path.replace("/api/projects/{project_id}", "").replace("{session_id}", sid)
                snap[url] = self.get(url)
        snap["/export/quotes.csv"] = self.get("/export/quotes.csv")
        db = self.client.app.state.db_factory()
        try:
            from sqlalchemy import text

            snap["db"] = {t: db.execute(text(f"select count(*) from {t}")).scalar() for t in (
                "quotes", "quote_tags", "quote_states", "quote_edits", "cluster_quotes",
                "theme_quotes", "persons", "session_speakers", "transcript_segments",
                "transcript_layout_edits")}
        finally:
            db.close()
        registry = json.loads((self.root / "bristlenose-output/.bristlenose/sessions.json").read_text("utf-8"))
        snap["registry"] = {"pins": {s: {label: pin.get("role") for label, pin in pins.items()}
                                     for s, pins in registry.get("pins", {}).items()},
                            "speakers": registry.get("speakers", {})}
        return snap


def _lens_ids(body: dict, group: str) -> set[str]:
    return {q["dom_id"] for g in body.get(group, []) for q in g["quotes"]}


def facts(snap: dict) -> dict:
    """What a researcher can see, surface by surface."""
    quotes = snap["/quotes"]
    out: dict[str, Any] = {
        "lens.sections": sorted(_lens_ids(quotes, "sections")),
        "lens.themes": sorted(_lens_ids(quotes, "themes")),
        "lens.uncategorised": sorted(q["dom_id"] for q in quotes.get("uncategorised", [])),
        "lens.credit": {q["dom_id"]: f'{q["participant_id"]} {q["speaker_name"]}'
                        for grp in ("sections", "themes") for g in quotes.get(grp, []) for q in g["quotes"]},
        "dashboard.quotes": snap["/dashboard"]["stats"]["quotes_count"],
        "info.participants": snap["/info"]["participant_count"],
        "signals.count": sum(s["count"] for s in snap["/signals/sentiment"]["signals"]),
        "signals.quotes": sorted({f'q-{q["pid"]}-{int(q["startSeconds"])}'
                                  for s in snap["/signals/sentiment"]["signals"] for q in s["quotes"]}),
        "dashboard.featured": sorted(q["dom_id"] for q in snap["/dashboard"]["featured_quotes"]),
        "signals.participants": sorted({p for s in snap["/signals/sentiment"]["signals"]
                                        for p in s["participants"]}),
        "csv.rows": Counter(line.rsplit(",", 2)[-2] for line in snap["/export/quotes.csv"].splitlines()[1:]),
        "csv.codes": sorted({m for m in re.findall(r",([pmo][0-9A-Z?]+),", snap["/export/quotes.csv"])}),
        "people": {code: p["short_name"] for code, p in snap["/people"].items()},
        "starred": snap["/starred"], "tags": snap["/tags"], "edits": snap["/edits"],
        "db": snap["db"], "registry.pins": snap["registry"]["pins"],
        "registry.speakers": snap["registry"]["speakers"],
    }
    tapestry = {s["session_id"]: s for s in snap["/tapestry"]["sessions"]}
    for s in snap["/sessions"]["sessions"]:
        sid = s["session_id"]
        transcript = snap[f"/transcripts/{sid}"]
        out[sid] = {
            "speakers": [f'{sp["slot_code"]}>{sp["speaker_code"]} {sp["role"]} "{sp["name"]}"'
                         f'{"" if sp["name_confirmed"] else " ?"}' for sp in s["speakers"]],
            "owed": s["needs_reanalysis"],
            "grid.sentiment": sum(s["sentiment_counts"].values()),
            "grid.journey": s["journey_labels"],
            "timeline.quotes": len(tapestry[sid]["quotes"]),
            "timeline.sections": len(tapestry[sid]["sections"]),
            "timeline.turns": [f'{t["speaker"]}{"*" if t["team"] else ""}' for t in tapestry[sid]["turns"]],
            "transcript.codes": [seg["speaker_code"] for seg in transcript["segments"]],
            "transcript.moderator": [int(seg["is_moderator"]) for seg in transcript["segments"]],
            "transcript.quoted": sorted({q for seg in transcript["segments"] for q in seg["quote_ids"]}),
            "transcript.speakers": [f'{sp["code"]} {sp["name"]}' for sp in transcript["speakers"]],
        }
    return out


def evidence(f: dict) -> dict[str, set[str] | int]:
    """The same question asked of each evidence surface: which quotes count."""
    return {"lens.sections": set(f["lens.sections"]), "lens.themes": set(f["lens.themes"]),
            "dashboard": f["dashboard.quotes"], "signals": set(f["signals.quotes"]),
            "featured": set(f["dashboard.featured"]),
            "csv": sum(f["csv.rows"].values()),
            "grid": sum(f[s]["grid.sentiment"] for s in world.TRANSCRIPTS)}


def flat(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            out.update(flat(v, f"{prefix}.{k}" if prefix else str(k)))
        return out
    return {prefix: value}


def changed(a: dict, b: dict) -> dict[str, tuple[Any, Any]]:
    fa, fb = flat(a), flat(b)
    return {k: (fa.get(k), fb.get(k)) for k in sorted(set(fa) | set(fb)) if fa.get(k) != fb.get(k)}


# --------------------------------------------------------------------------- scenarios


@dataclass
class Scenario:
    key: str
    family: str
    menu: str                      # what the researcher did, in the menu's words
    session: str
    act: Callable[[Study], Any]    # returns what undo needs
    undo: Callable[[Study, Any], None]
    #: Desired: quotes that should stop counting as evidence.
    out: set[str] = field(default_factory=set)
    #: Desired: whether the session is owed a re-analysis afterwards.
    owed: bool = False
    #: Offered by the picker today (False: the route accepts it, the menu does not offer it).
    offered: bool = True
    #: A change to a person, meant to show wherever they appear.
    spreads: bool = False
    note: str = ""


def _slot_act(sid: str, slot: str, change: Callable[[Study, dict], dict]) -> tuple[Callable, Callable]:
    """An act that is one ``SpeakerNameState`` write, undone by writing the old state."""
    def act(st: Study) -> Any:
        before = st.state(sid, slot)
        after = change(st, dict(before))
        st.write_state(sid, slot, after, before)
        return before, after

    def undo(st: Study, memo: Any) -> None:
        before, after = memo
        st.write_state(sid, slot, before, after)
    return act, undo


def _person(st: Study, sid: str, slot: str) -> str:
    return st.slots(sid)[slot]["person"]


def _paragraph_act(sid: str, position: int, **target: Any) -> tuple[Callable, Callable]:
    def act(st: Study) -> Any:
        return st.move_paragraph(sid, position, **target)

    def undo(st: Study, edit: Any) -> None:
        st.send("DELETE", f"/transcripts/{sid}/layout-edits/{edit}")
    return act, undo


def _swap(sid: str, a: str, b: str) -> tuple[Callable, Callable]:
    def act(st: Study) -> Any:
        return st.put_slot(sid, a, {"swap_with": b})
    return act, lambda st, _memo: act(st)


def _chain(*steps: tuple[Callable, Callable]) -> tuple[Callable, Callable]:
    def act(st: Study) -> Any:
        return [a(st) for a, _ in steps]

    def undo(st: Study, memos: Any) -> None:
        for (_, u), memo in reversed(list(zip(steps, memos))):
            u(st, memo)
    return act, undo


def _new(name: str, kind: str | None = None) -> Callable[[Study, dict], dict]:
    def change(_st: Study, s: dict) -> dict:
        s.update(person=str(uuid.uuid4()), create=True, full_name=name, short_name=name, confirmed=True)
        if kind:
            s["kind"] = kind
        return s
    return change


def _pick(of: tuple[str, str], kind: str | None = None) -> Callable[[Study, dict], dict]:
    def change(st: Study, s: dict) -> dict:
        row = st.slots(of[0])[of[1]]
        s.update(person=row["person"], full_name=row["full_name"], short_name=row["short_name"], confirmed=True)
        if kind:
            s["kind"] = kind
        return s
    return change


def _own(kind: str) -> Callable[[Study, dict], dict]:
    def change(_st: Study, s: dict) -> dict:
        s.update(kind=kind, confirmed=True)
        return s
    return change


def _set(**fields: Any) -> Callable[[Study, dict], dict]:
    def change(_st: Study, s: dict) -> dict:
        s.update(fields)
        return s
    return change


S1_QUOTES = {q for q in ALL_QUOTES if q.startswith("q-p1-")}
S3_QUOTES = {q for q in ALL_QUOTES if q.startswith("q-p3-")}


def scenarios() -> list[Scenario]:
    def sc(key: str, family: str, menu: str, sid: str, pair: tuple[Callable, Callable], **kw: Any) -> Scenario:
        return Scenario(key, family, menu, sid, pair[0], pair[1], **kw)

    return [
        # ---- A. Names: who the speaker is, same role. Nothing about evidence should move.
        sc("A1", "A name", "Confirm the proposed moderator name (Return)", "s1",
           _slot_act("s1", "m1", _set(confirmed=True))),
        sc("A2", "A name", "Rename the moderator in place (Marcus -> Markus)", "s1",
           _slot_act("s1", "m1", _set(full_name="Markus Stone", short_name="Markus", confirmed=True)),
           spreads=True, note="Marcus moderates s2 too: a spelling fix is meant to reach both."),
        sc("A3", "A name", "Rename the participant (Rosalind -> Ros)", "s1",
           _slot_act("s1", "p1", _set(full_name="Ros", short_name="Ros", confirmed=True))),
        sc("A4", "A name", "Moderator is that other known person (s3: Kerri -> Marcus)", "s3",
           _slot_act("s3", "m1", _pick(("s1", "m1")))),
        sc("A5", "A name", "Moderator is someone new (s1: type 'Priya')", "s1",
           _slot_act("s1", "m1", _new("Priya"))),
        sc("A6", "A name", "Not this person (clear s1's moderator)", "s1",
           _slot_act("s1", "m1", _set(person="", full_name="", short_name="", confirmed=False))),
        sc("A7", "A name", "Observer is someone new (s3: type 'Sam')", "s3",
           _slot_act("s3", "o1", _new("Sam"))),
        # ---- B. Team recode: moderator <-> observer. Still not evidence.
        sc("B1", "B team recode", "Moderator was an observer (same person)", "s3",
           _slot_act("s3", "m1", _own("observer"))),
        sc("B2", "B team recode", "Observer was a moderator (same person)", "s3",
           _slot_act("s3", "o1", _own("moderator"))),
        sc("B3", "B team recode", "Observer was the moderator Marcus (pick under Moderator)", "s3",
           _slot_act("s3", "o1", _pick(("s1", "m1"), "moderator"))),
        # ---- C. Out of participant: the whole speaker was never a participant.
        sc("C1", "C out of participant", "Participant was the moderator Marcus (p1 -> Marcus)", "s1",
           _slot_act("s1", "p1", _pick(("s1", "m1"), "moderator")), out=S1_QUOTES, owed=True),
        sc("C2", "C out of participant", "Participant was a new moderator (p1 -> 'Priya')", "s1",
           _slot_act("s1", "p1", _new("Priya", "moderator")), out=S1_QUOTES, owed=True),
        sc("C3", "C out of participant", "Participant was an observer (p3 -> Olu)", "s3",
           _slot_act("s3", "p3", _pick(("s3", "o1"), "observer")), out=S3_QUOTES, owed=True),
        sc("C4", "C out of participant", "Participant was an unknown moderator (p1 -> m?)", "s1",
           _slot_act("s1", "p1", _set(person="", full_name="", short_name="", confirmed=False, kind="moderator")),
           out=S1_QUOTES, owed=True),
        # ---- D. Into participant: a team speaker was a participant all along.
        sc("D1", "D into participant", "Moderator was a participant (same person, s3 Kerri)", "s3",
           _slot_act("s3", "m1", _own("participant")), owed=True,
           note="Their words were never quote-mined; existing quotes should be untouched."),
        sc("D2", "D into participant", "Observer was a participant (same person, s3 Olu)", "s3",
           _slot_act("s3", "o1", _own("participant")), owed=True),
        sc("D3", "D into participant", "Moderator was a new participant (s1 m1 -> 'Zed')", "s1",
           _slot_act("s1", "m1", _new("Zed", "participant")), owed=True),
        # ---- E. Swap.
        sc("E1", "E swap", "Swap with m1 (s1: participant <-> moderator)", "s1",
           _swap("s1", "p1", "m1"), out=S1_QUOTES, owed=True,
           note="The incident of 14 Nov. One row in the name list."),
        sc("E2", "E swap", "Swap, from the moderator's badge", "s1",
           _swap("s1", "m1", "p1"), out=S1_QUOTES, owed=True),
        sc("E3", "E swap", "Swap participant with the observer (s3)", "s3",
           _swap("s3", "p3", "o1"), out=S3_QUOTES, owed=True, offered=False),
        # ---- F. Paragraph scope: this one speech was someone else's.
        sc("F1", "F paragraph", "Quoted participant paragraph was the moderator's (s1 #1 -> m1)", "s1",
           _paragraph_act("s1", 1, slot="m1"), out={"q-p1-10"}),
        sc("F2", "F paragraph", "Moderator's 'Yes that is true' was the participant's (s1 #4 -> p1)", "s1",
           _paragraph_act("s1", 4, slot="p1"),
           note="The everyday fix. Nothing was quoted from it, so no evidence should move."),
        sc("F3", "F paragraph", "Unquoted moderator opener was the participant's (s1 #0 -> p1)", "s1",
           _paragraph_act("s1", 0, slot="p1")),
        sc("F4", "F paragraph", "Quoted paragraph was a new unknown moderator's (s1 #3 -> new)", "s1",
           _paragraph_act("s1", 3, new="moderator"), out={"q-p1-30"}),
        sc("F5", "F paragraph", "Participant paragraph was the observer's (s3 #2 -> o1)", "s3",
           _paragraph_act("s3", 2, slot="o1"), out={"q-p3-20"}),
        sc("F6", "F paragraph", "Observer's line was the participant's (s3 #5 -> p3)", "s3",
           _paragraph_act("s3", 5, slot="p3")),
        sc("F7", "F paragraph", "Observer's line was the moderator's (s3 #1 -> m1)", "s3",
           _paragraph_act("s3", 1, slot="m1")),
        # ---- G. Sequences a real correction pass makes.
        sc("G1", "G sequences", "Three quick paragraph fixes in s1 (#4 -> p1, #1 -> m1, #6 -> p1)", "s1",
           _chain(_paragraph_act("s1", 4, slot="p1"), _paragraph_act("s1", 1, slot="m1"),
                  _paragraph_act("s1", 6, slot="p1")), out={"q-p1-10"}),
        sc("G2", "G sequences", "Every participant paragraph moved to m1, one at a time (s2)", "s2",
           _chain(_paragraph_act("s2", 1, slot="m1"), _paragraph_act("s2", 3, slot="m1"),
                  _paragraph_act("s2", 5, slot="m1")),
           out={"q-p2-10", "q-p2-30", "q-p2-50"}),
        sc("G3", "G sequences", "Swap, then fix one paragraph the other way", "s1",
           _chain(_swap("s1", "p1", "m1"), _paragraph_act("s1", 4, slot="p1")),
           out=S1_QUOTES, owed=True),
        sc("G4", "G sequences", "Paragraph fix, then a swap on top of it", "s1",
           _chain(_paragraph_act("s1", 1, slot="m1"), _swap("s1", "p1", "m1")),
           out=S1_QUOTES, owed=True),
        sc("G5", "G sequences", "Rename the moderator, then recode the participant as them", "s1",
           _chain(_slot_act("s1", "m1", _set(full_name="Markus Stone", short_name="Markus", confirmed=True)),
                  _slot_act("s1", "p1", _pick(("s1", "m1"), "moderator"))),
           out=S1_QUOTES, owed=True, spreads=True),
    ]


# --------------------------------------------------------------------------- the oracle

RULES = {
    "R1 accepted": "The write is accepted (2xx) or refused whole (4xx). Never a 5xx.",
    "R2 evidence": "Exactly the expected quotes leave the evidence; no others.",
    "R3 agree": "Every evidence surface gives the same answer (lens, themes, dashboard, signals, CSV, grid).",
    "R4 record": "The record keeps the session's quotes: transcript marks and timeline still show them.",
    "R5 isolated": "Other sessions read exactly as before.",
    "R6 codes": "Nobody's code changes unless their own role did.",
    "R7 kept": "Nothing is deleted: quotes, tags, stars and edits are all still stored.",
    "R8 owed": "The session says it needs re-analysis exactly when a whole speaker changed sides.",
    "R9 re-import": "A re-import (the next run) leaves the result as it was.",
    "R10 undo": "Undo puts every surface back exactly.",
    "R11 late undo": "Undo still puts everything back after the next run or a relaunch.",
}


def seen(diff: dict) -> dict:
    """Drop what no researcher can see and the design keeps on purpose: a person
    no slot points at is kept, hidden; a code once issued is never reissued."""
    return {k: v for k, v in diff.items()
            if k not in ("db.persons",) and "retired" not in k}


def judge(sc: Scenario, base: dict, after: dict, again: dict, undone: dict, late: dict, log: list) -> dict[str, tuple[bool, str]]:
    out: dict[str, tuple[bool, str]] = {}
    bad = [f"{m} {p} -> {code}" for m, p, code, _ in log if code >= 500]
    refused = [f"{m} {p} -> {code}" for m, p, code, _ in log if 400 <= code < 500]
    out["R1 accepted"] = (not bad and not refused, "; ".join(bad + refused))

    want = ALL_QUOTES - sc.out
    ev = evidence(after)
    got = ev["lens.sections"]
    assert isinstance(got, set)
    extra_lost, not_lost = sorted(want - got), sorted(got - want)
    detail = []
    if extra_lost:
        detail.append(f"lost but should count: {', '.join(extra_lost)}")
    if not_lost:
        detail.append(f"still counted but should not: {', '.join(not_lost)}")
    out["R2 evidence"] = (not detail, "; ".join(detail))

    n = len(got)
    counts = {"themes": len(ev["lens.themes"]), "dashboard": ev["dashboard"],  # type: ignore[arg-type]
              "csv": ev["csv"], "grid": ev["grid"]}
    off = {k: v for k, v in counts.items() if v != n}
    msgs = [f"{k} says {v}" for k, v in off.items()]
    for name in ("signals", "featured"):
        stray = sorted(ev[name] - got)  # type: ignore[operator]
        if stray:
            msgs.append(f"{name} still cites {', '.join(stray)}")
    out["R3 agree"] = (not msgs, f"lens says {n}; " + ", ".join(msgs) if msgs else "")

    sid = sc.session
    kept = base[sid]["timeline.quotes"] == after[sid]["timeline.quotes"] and \
        base[sid]["transcript.quoted"] == after[sid]["transcript.quoted"]
    out["R4 record"] = (kept, "" if kept else
                        f'timeline {base[sid]["timeline.quotes"]} -> {after[sid]["timeline.quotes"]} quotes, '
                        f'transcript marks {len(base[sid]["transcript.quoted"])} -> {len(after[sid]["transcript.quoted"])}')

    others = [s for s in world.TRANSCRIPTS if s != sid]
    leak = {s: changed(base[s], after[s]) for s in others if base[s] != after[s]}
    if sc.spreads:  # a spelling fix is meant to reach the person's other sessions
        leak = {s: {k: v for k, v in d.items() if k not in ("speakers", "transcript.speakers")}
                for s, d in leak.items()}
        leak = {s: d for s, d in leak.items() if d}
    out["R5 isolated"] = (not leak, "; ".join(
        f"{s}: " + ", ".join(f"{k} {a!r}->{b!r}" for k, (a, b) in list(d.items())[:3]) for s, d in leak.items()))

    moved = []
    for s in world.TRANSCRIPTS:
        before_codes = dict(x.split(" ", 1)[0].split(">") for x in base[s]["speakers"])
        after_codes = dict(x.split(" ", 1)[0].split(">") for x in after[s]["speakers"])
        role_before = {x.split(">")[0]: x.split(" ")[1] for x in base[s]["speakers"]}
        role_after = {x.split(">")[0]: x.split(" ")[1] for x in after[s]["speakers"]}
        name_before = {x.split(">")[0]: x.split('"')[1] for x in base[s]["speakers"]}
        name_after = {x.split(">")[0]: x.split('"')[1] for x in after[s]["speakers"]}
        for slot, code in before_codes.items():
            if slot in after_codes and after_codes[slot] != code and role_before[slot] == role_after.get(slot) \
                    and name_before[slot] == name_after.get(slot):
                moved.append(f"{s} {name_before[slot] or slot}: {code} -> {after_codes[slot]}")
    out["R6 codes"] = (not moved, "; ".join(moved))

    lost = {k: (base["db"][k], after["db"][k]) for k in ("quotes", "quote_tags", "quote_states", "quote_edits",
                                                          "cluster_quotes", "theme_quotes")
            if after["db"][k] < base["db"][k]}
    out["R7 kept"] = (not lost, ", ".join(f"{k} {a}->{b}" for k, (a, b) in lost.items()))

    owed = after[sid]["owed"]
    out["R8 owed"] = (owed == sc.owed, "" if owed == sc.owed else f"needs_reanalysis is {owed}, wanted {sc.owed}")

    drift = seen(changed(after, again))
    out["R9 re-import"] = (not drift, "; ".join(f"{k}: {a!r} -> {b!r}" for k, (a, b) in list(drift.items())[:4]))

    left = seen(changed(base, undone))
    out["R10 undo"] = (not left, "; ".join(f"{k}: {a!r} -> {b!r}" for k, (a, b) in list(left.items())[:4]))
    left = seen(changed(base, late))
    out["R11 late undo"] = (not left, "; ".join(f"{k}: {a!r} -> {b!r}" for k, (a, b) in list(left.items())[:4]))
    return out


def run() -> list[dict]:
    results = []
    for sc in scenarios():
        st = Study()
        base = facts(st.snapshot())
        st.log.clear()
        try:
            memo = sc.act(st)
            after = facts(st.snapshot())
            act_log = list(st.log)
            sc.undo(st, memo)
            undone = facts(st.snapshot())
            # The same act on a second study, with the next run (or a relaunch,
            # which re-imports) between the act and its undo.
            st2 = Study()
            memo2 = sc.act(st2)
            st2.reimport()
            again = facts(st2.snapshot())
            sc.undo(st2, memo2)
            late = facts(st2.snapshot())
            verdict = judge(sc, base, after, again, undone, late, act_log)
            error = ""
        except Exception as exc:  # a scenario that cannot run is a finding, not a crash
            after = again = undone = late = base
            act_log = list(st.log)
            verdict = dict.fromkeys(RULES, (False, "did not run"))
            error = f"{type(exc).__name__}: {exc}"
        results.append({
            "key": sc.key, "family": sc.family, "menu": sc.menu, "session": sc.session,
            "offered": sc.offered, "note": sc.note, "want_out": sorted(sc.out), "want_owed": sc.owed,
            "requests": [f"{m} {p} {body} -> {code}" for m, p, code, body in act_log],
            "error": error,
            "verdict": {r: {"ok": ok, "detail": d} for r, (ok, d) in verdict.items()},
            "changes": {k: [a, b] for k, (a, b) in changed(base, after).items()},
            "undo_left": {k: [a, b] for k, (a, b) in changed(base, undone).items()},
        })
        print(sc.key, "".join("." if v[0] else "X" for v in verdict.values()), sc.menu, error)
    return results


# --------------------------------------------------------------------------- the report


def report(results: list[dict]) -> str:
    e = html.escape
    rules = list(RULES)
    head = "".join(f'<th title="{e(RULES[r])}">{e(r.split(" ", 1)[0])}<span>{e(r.split(" ", 1)[1])}</span></th>'
                   for r in rules)
    rows, family = [], ""
    for r in results:
        if r["family"] != family:
            family = r["family"]
            rows.append(f'<tr class="fam"><td colspan="{len(rules) + 2}">{e(family)}</td></tr>')
        cells = "".join(
            f'<td class="{"ok" if v["ok"] else "bad"}" title="{e(v["detail"])}">{"" if v["ok"] else "✕"}</td>'
            for v in (r["verdict"][x] for x in rules))
        fails = "".join(f"<li><b>{e(x)}</b> {e(r['verdict'][x]['detail'])}</li>"
                        for x in rules if not r["verdict"][x]["ok"])
        reqs = "".join(f"<li><code>{e(q)}</code></li>" for q in r["requests"])
        chg = "".join(f"<li><code>{e(k)}</code>: {e(json.dumps(a))} → {e(json.dumps(b))}</li>"
                      for k, (a, b) in r["changes"].items())
        tag = "" if r["offered"] else ' <em class="tag">route only</em>'
        rows.append(
            f'<tr><td class="k">{e(r["key"])}</td><td class="m"><details><summary>{e(r["menu"])}{tag}</summary>'
            f'{"<p>" + e(r["note"]) + "</p>" if r["note"] else ""}'
            f'{"<p class=err>" + e(r["error"]) + "</p>" if r["error"] else ""}'
            f'<h4>Sent</h4><ul>{reqs}</ul>'
            f'{"<h4>Rules broken</h4><ul>" + fails + "</ul>" if fails else ""}'
            f'<h4>Everything that changed</h4><ul class="chg">{chg}</ul></details></td>{cells}</tr>')
    total = sum(1 for r in results for v in r["verdict"].values())
    broken = sum(1 for r in results for v in r["verdict"].values() if not v["ok"])
    legend = "".join(f"<li><b>{e(k)}</b> {e(v)}</li>" for k, v in RULES.items())
    return f"""<!doctype html><meta charset="utf-8"><title>Speaker acts</title>
<style>
:root{{--bg:#fff;--fg:#1c1c1e;--mute:#6b6b70;--line:#e3e3e6;--ok:#e7f4ea;--bad:#d93025;--badbg:#fde8e6;--fam:#f4f4f6}}
@media(prefers-color-scheme:dark){{:root{{--bg:#1c1c1e;--fg:#f2f2f4;--mute:#a0a0a6;--line:#38383c;--ok:#1f3326;--bad:#ff6b5e;--badbg:#45211e;--fam:#28282b}}}}
body{{font:14px/1.45 -apple-system,system-ui,sans-serif;background:var(--bg);color:var(--fg);margin:24px auto;max-width:1180px;padding:0 16px}}
h1{{font-size:20px;margin:0 0 4px}} .sub{{color:var(--mute);margin:0 0 16px}}
table{{border-collapse:collapse;width:100%}} th,td{{border-bottom:1px solid var(--line);padding:6px 8px;vertical-align:top;text-align:left}}
th{{font-size:12px;white-space:nowrap}} th span{{display:block;font-weight:400;color:var(--mute)}}
td.ok{{background:var(--ok)}} td.bad{{background:var(--badbg);color:var(--bad);text-align:center;font-weight:700}}
td.k{{color:var(--mute);white-space:nowrap}} tr.fam td{{background:var(--fam);font-weight:600}}
summary{{cursor:pointer}} details ul{{margin:4px 0 8px;padding-left:18px}} h4{{margin:10px 0 2px;font-size:12px;color:var(--mute)}}
code{{font:12px ui-monospace,Menlo,monospace}} .chg li{{word-break:break-word}} .tag{{color:var(--mute);font-size:12px}} .err{{color:var(--bad)}}
ol.legend{{color:var(--mute);font-size:13px;padding-left:18px;columns:2;list-style:none}}
</style>
<h1>Speaker acts: what each menu act does to the study</h1>
<p class="sub">{len(results)} scenarios × {len(rules)} rules on a synthetic three-session study.
{broken} of {total} checks fail. A red cell is where the product does something other than the desired end state;
hover it for the detail, open a row for the requests sent and every value that changed.</p>
<table><tr><th></th><th>What the researcher did</th>{head}</tr>{"".join(rows)}</table>
<h4>The desired end state, as rules</h4><ol class="legend">{legend}</ol>
"""


if __name__ == "__main__":
    res = run()
    (HERE / "results.json").write_text(json.dumps(res, indent=1, default=sorted), encoding="utf-8")
    (HERE / "report.html").write_text(report(res), encoding="utf-8")
    print("wrote", HERE / "report.html")
