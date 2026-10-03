"""Score speaker splitting against a platform transcript's named turns.

A Teams recording that came with its .docx transcript gives free ground truth:
transcribe the video with Whisper (no names), run each splitting method on
those segments, and check every segment against the speaker the platform
named for the same stretch of time.

    .venv/bin/python experiments/speaker_split_full/eval_platform.py \
        <whisper session_segments.json> <whisper session id> \
        <docx session_segments.json> <docx session id> \
        "<moderator name>" <out.json> [--whole-runs N]

Truth per Whisper segment: the docx speaker covering >= 75% of its time (turn
intervals run from one turn's start to the next), else "B" (both voices).
A truth label only counts as VERIFIED when at least half the segment's words
appear in that speaker's nearby docx text — this drops stretches where the
platform's timing and Whisper's disagree (Teams writes whole seconds, and
can open with a long untranscribed gap). Unverified segments are reported,
not scored.

Real LLM calls: one shipped split plus N whole-transcript splits, each with
the role pass, on one session — roughly $0.05 per method run.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from collections import Counter
from pathlib import Path

from run import split_whole  # noqa: E402  (sibling experiment module)

from bristlenose.config import load_settings
from bristlenose.llm.client import LLMClient
from bristlenose.models import SpeakerRole, TranscriptSegment
from bristlenose.stages.s05b_identify_speakers import (
    identify_speaker_roles_heuristic,
    identify_speaker_roles_llm,
    split_single_speaker_llm,
)

_WORD = re.compile(r"[a-z']+")


def _words(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def _role(seg: TranscriptSegment) -> str:
    return {SpeakerRole.RESEARCHER: "M", SpeakerRole.PARTICIPANT: "P"}.get(seg.speaker_role, "?")


def ground_truth(
    whisper: list[dict], turns: list[dict], moderator: str, min_recall: float = 0.5
) -> list[dict]:
    """One truth record per Whisper segment."""
    spans = []
    for i, t in enumerate(turns):
        end = turns[i + 1]["start_time"] if i + 1 < len(turns) else t["start_time"] + 30.0
        spans.append((t["start_time"], end, "M" if t["speaker_label"] == moderator else "P", t["text"]))
    out = []
    for s in whisper:
        a, b = s["start_time"], max(s["end_time"], s["start_time"] + 0.01)
        cover: Counter[str] = Counter()
        for lo, hi, who, _ in spans:
            ov = min(b, hi) - max(a, lo)
            if ov > 0:
                cover[who] += ov
        dur = b - a
        if not cover:
            truth = "?"
        else:
            who, ov = cover.most_common(1)[0]
            truth = who if ov / dur >= 0.75 else "B"
        verified = False
        words = _words(s["text"])
        if truth in ("M", "P") and words:
            near = " ".join(
                text for lo, hi, w, text in spans
                if w == truth and hi >= a - 5 and lo <= b + 5
            )
            vocab = set(_words(near))
            verified = sum(w in vocab for w in words) / len(words) >= min_recall
        out.append({"truth": truth, "verified": verified, "words": len(words)})
    return out


def text_truth(whisper: list[dict], turns: list[dict], moderator: str) -> list[dict]:
    """A second truth that uses no interval maths (added after review, 3 Oct 2026).

    Teams turn starts often come late, so the timing rule above swaps short
    moderator turns into the participant's interval and the verify filter then
    keeps 47% of moderator segments but 81% of participant ones. Here a segment
    is labelled by which speaker's nearby text (turn starts within +/-5 s of
    any turn touching the segment) holds its words: one speaker >= 0.7 of
    them and the other < 0.4, else unscored.
    """
    spans = []
    for i, t in enumerate(turns):
        end = turns[i + 1]["start_time"] if i + 1 < len(turns) else t["start_time"] + 30.0
        spans.append((t["start_time"], end, "M" if t["speaker_label"] == moderator else "P", t["text"]))
    out = []
    for s in whisper:
        a, b = s["start_time"], max(s["end_time"], s["start_time"] + 0.01)
        words = _words(s["text"])
        rec = {}
        for who in ("M", "P"):
            vocab = set(_words(" ".join(
                text for lo, hi, w, text in spans if w == who and hi >= a - 5 and lo <= b + 5
            )))
            rec[who] = sum(w in vocab for w in words) / len(words) if words else 0.0
        truth = "?"
        for who, other in (("M", "P"), ("P", "M")):
            if rec[who] >= 0.7 and rec[other] < 0.4:
                truth = who
        out.append({"truth": truth, "verified": truth in ("M", "P"), "words": len(words)})
    return out


async def run_method(name: str, base: list[dict], client: LLMClient) -> list[str]:
    segs = [TranscriptSegment.model_validate(s) for s in base]
    for s in segs:
        s.speaker_label = None
        s.speaker_role = SpeakerRole.UNKNOWN
    if name in ("sampled", "production"):
        # "sampled" was the opening-window splitter; from 3 Oct 2026 the same
        # production function reads the whole transcript in chunks.
        await split_single_speaker_llm(segs, client)
    else:
        await split_whole(segs, client)
    identify_speaker_roles_heuristic(segs)
    await identify_speaker_roles_llm(segs, client)
    return [_role(s) for s in segs]


def score(pred: list[str], truth: list[dict]) -> dict:
    n = ok = wn = wok = 0
    for p, t in zip(pred, truth):
        if not t["verified"]:
            continue
        n += 1
        wn += t["words"]
        if p == t["truth"]:
            ok += 1
            wok += t["words"]
    # Same population as the truth's share: verified segments only.
    mod_words = sum(t["words"] for p, t in zip(pred, truth) if t["verified"] and p == "M")

    def recall(c: str) -> str:
        idx = [i for i, t in enumerate(truth) if t["verified"] and t["truth"] == c]
        return f"{sum(pred[i] == c for i in idx)}/{len(idx)}"

    return {
        "segments_scored": n,
        "accuracy": round(ok / n, 3) if n else None,
        "word_accuracy": round(wok / wn, 3) if wn else None,
        "moderator_recall": recall("M"),
        "participant_recall": recall("P"),
        "moderator_word_share": round(mod_words / wn, 3) if wn else None,
    }


async def main(args: argparse.Namespace) -> None:
    whisper = json.loads(Path(args.whisper).read_text())[args.whisper_sid]
    turns = json.loads(Path(args.docx).read_text())[args.docx_sid]
    truth = ground_truth(whisper, turns, args.moderator, args.verify_threshold)
    tc = Counter(t["truth"] for t in truth)
    verified = sum(t["verified"] for t in truth)
    true_mod = sum(t["words"] for t in truth if t["truth"] == "M" and t["verified"])
    true_all = sum(t["words"] for t in truth if t["verified"])
    print(f"{len(whisper)} whisper segments; truth {dict(tc)}; {verified} verified; "
          f"true moderator word share {true_mod / true_all:.3f}")

    if args.rescore:
        # Re-score saved predictions against the current truth rules; no LLM calls.
        runs = json.loads(Path(args.out).read_text())["runs"]
    else:
        client = LLMClient(load_settings())
        runs = {}
        for i in range(args.production_runs):
            runs[f"production_{i + 1}"] = await run_method("production", whisper, client)
        for i in range(args.whole_runs):
            runs[f"whole_{i + 1}"] = await run_method("whole", whisper, client)

    ttruth = text_truth(whisper, turns, args.moderator)
    results = {name: score(pred, truth) for name, pred in runs.items()}
    results.update({f"{name}@text": score(pred, ttruth) for name, pred in runs.items()})
    wholes = [runs[k] for k in runs if k.startswith("whole_")]
    if len(wholes) > 1:
        same = sum(len(set(col)) == 1 for col in zip(*wholes))
        results["whole_runs_identical_segments"] = f"{same}/{len(whisper)}"
    for k, v in results.items():
        print(f"{k:12} {v}")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({
        "truth": truth,
        "text_truth": ttruth,
        "runs": runs,
        "results": results,
        "segments": [{"start": s["start_time"], "end": s["end_time"], "text": s["text"]}
                     for s in whisper],
    }, indent=1))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("whisper")
    p.add_argument("whisper_sid")
    p.add_argument("docx")
    p.add_argument("docx_sid")
    p.add_argument("moderator")
    p.add_argument("out")
    p.add_argument("--whole-runs", type=int, default=3)
    p.add_argument("--production-runs", type=int, default=1,
                   help="runs of the shipped split_single_speaker_llm (chunked since 3 Oct 2026)")
    p.add_argument("--verify-threshold", type=float, default=0.5)
    p.add_argument("--rescore", action="store_true",
                   help="re-score the runs already saved in OUT; makes no LLM calls")
    asyncio.run(main(p.parse_args()))
