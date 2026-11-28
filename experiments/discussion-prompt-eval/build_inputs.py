"""Freeze each study's classify inputs (spine + askable moderator turns) once,
so every arm sees byte-identical prompts.

Turns are built exactly as ``bristlenose/discussion/stage.py`` step 2a builds
them (same loader as ``analyze``, same moderator check, same turn ids, same
askable-length filter). Output goes to the private eval folder, because turn
text is participants' sessions.

    .venv/bin/python experiments/discussion-prompt-eval/build_inputs.py OUT_DIR
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from bristlenose.discussion.moderator import (
    is_askable_length,
    moderator_turns,
    whole_transcript_split,
)
from bristlenose.discussion.stage import _turn_id
from bristlenose.models import SpeakerRole
from bristlenose.pipeline import load_transcripts_from_dir

REPO = Path(__file__).resolve().parents[2]
TR = REPO / "trial-runs"


def record_spine(path: Path) -> list[dict]:
    rec = json.loads(path.read_text(encoding="utf-8"))
    return [{"id": s["id"], "title": s["title"], "kind": s["kind"],
             "items": [{"id": it["id"], "text": it["text"]} for it in s["items"]]}
            for s in rec["spine"]]


def gold_spine_and_labels(gold_path: Path) -> tuple[list[dict], dict, dict]:
    """The synthetic corpus's gold uses g0.. ids; the stage numbers s1.. in guide order."""
    g = json.loads(gold_path.read_text(encoding="utf-8"))
    remap: dict[str, str] = {}
    spine = []
    for i, (gid, sec) in enumerate(g["spine"].items(), 1):
        sid = f"s{i}"
        remap[gid] = sid
        items = []
        for j, (iid, text) in enumerate(sec["items"].items(), 1):
            remap[iid] = f"{sid}.{j}"
            items.append({"id": f"{sid}.{j}", "text": text})
        spine.append({"id": sid, "title": sec["title"], "kind": sec["kind"], "items": items})
    gold = {}
    for tid, lb in g["turns"].items():
        kind = {"instr": "instruction"}.get(lb["kind"], lb["kind"])
        gold[tid] = {"kind": kind, "item_id": remap.get(lb.get("item", ""), ""),
                     "section_id": remap.get(lb.get("section", ""), "")}
    return spine, gold, remap


def askable_turns(transcripts_dir: Path) -> dict[str, list[dict]]:
    ts = load_transcripts_from_dir(transcripts_dir, labels_from=transcripts_dir.parent)
    split = whole_transcript_split(transcripts_dir.parent / ".bristlenose" / "intermediate"
                                   / "speaker-info", [t.session_id for t in ts])
    out: dict[str, list[dict]] = {}
    for t in ts:
        sid = t.session_id
        mt = moderator_turns(t, whole_split=sid in split)
        if not mt.reliable:
            print(f"  {transcripts_dir.parent.parent.name} {sid}: moderator {mt.reason}, skipped")
            continue
        seen: set[str] = set()
        for seg in t.segments:
            if not (seg.speaker_role == SpeakerRole.RESEARCHER
                    or (seg.speaker_role == SpeakerRole.UNKNOWN and seg.speaker_code.startswith("m"))):
                continue
            if seg.inaudible:
                continue
            tid = _turn_id(sid, seg.start_time, seen)
            text = seg.text.strip()
            if is_askable_length(text):
                out.setdefault(sid, []).append({"id": tid, "text": text})
    return out


def main(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    tal_spine = record_spine(TR / "talismanic-fresh/bristlenose-output/.bristlenose/intermediate/discussion.json")
    studies = {
        # real, owner moderating, the study's own guide
        "talismanic": (TR / "talismanic-fresh/bristlenose-output/transcripts-raw", tal_spine,
                       "real · guide · 3 sessions, owner moderating (public test data)"),
        # the same real turns without the guide: the condition the Gemma
        # failure was measured on (27 Nov 2026, Talismanic s2, no guide).
        # "IKEA with uxfriends" and speaker-split/p3-run are these same
        # recordings diarised differently, so they are not further studies.
        "talismanic-noguide": (TR / "talismanic-fresh/bristlenose-output/transcripts-raw", [],
                               "real · no guide · the same 3 sessions"),
        # real, public oral-history archive, other interviewers, no guide
        "fossda": (TR / "fossda-opensource/bristlenose-output/transcripts-raw", [],
                   "real · no guide · FOSSDA oral histories, several interviewers (public)"),
        # synthetic controls
        "rockclimbing": (TR / "rockclimbing-fresh/bristlenose-output/transcripts-raw", [],
                         "synthetic · no guide · scripted VTT"),
    }
    syn_spine, gold, _ = gold_spine_and_labels(REPO / "experiments/discussion-lens/synthetic/gold.json")
    studies["synthetic-gold"] = (REPO / "experiments/discussion-lens/synthetic/transcripts", syn_spine,
                                 "synthetic · guide · hand-labelled gold")

    manifest = {}
    tal_texts: set[str] = set()
    for name, (tdir, spine, desc) in studies.items():
        turns = askable_turns(tdir)
        if name == "talismanic":
            tal_texts = {t["text"][:80] for ts in turns.values() for t in ts}
        if name == "fossda":  # diarisation folded the interviewer into a couple of turns
            for sid in [k for k, v in turns.items() if len(v) < 5]:
                print(f"  fossda {sid}: {len(turns[sid])} turns, dropped")
                del turns[sid]
        if name == "ikea-ux":  # the same recordings as Talismanic's are not a second study
            for sid in list(turns):
                ts = turns[sid]
                same = sum(t["text"][:80] in tal_texts for t in ts)
                if same > len(ts) / 3:
                    print(f"  ikea-ux {sid}: {same}/{len(ts)} turns match Talismanic, dropped")
                    del turns[sid]
        data = {"study": name, "desc": desc, "spine": spine, "sessions": turns}
        if name == "synthetic-gold":
            data["gold"] = gold
        (out_dir / f"inputs-{name}.json").write_text(json.dumps(data, indent=1, ensure_ascii=False),
                                                     encoding="utf-8")
        manifest[name] = {s: len(v) for s, v in turns.items()}
        print(name, manifest[name], "spine sections:", len(spine))
    (out_dir / "inputs-manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
