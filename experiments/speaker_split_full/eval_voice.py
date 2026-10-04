"""Score the voice pass against the shipped text splitter on platform ground truth.

Same truths as eval_platform.py (text truth primary, timing truth second),
same Whisper segments for every method. Methods:

- text: the shipped `split_single_speaker_llm` (chunked, since 3 Oct 2026)
  plus the heuristic and LLM role passes.
- voice: voice.py's clusters, labelled "Speaker A/B", roles from the shipped
  LLM role pass on those labels — what the product would do. Segments too
  short to embed borrow the previous segment's cluster.
- voice+text: voice where it has a verdict, the text label where it has none.

Also prints the oracle mapping (best cluster->role permutation against the
truth) so a role-pass mistake is visible as a gap, not hidden in the total.

    .venv/bin/python experiments/speaker_split_full/eval_voice.py \
        <segments-with-words.json> <sid> <voice.json> <docx session_segments.json> <docx sid> \
        "<moderator name>" <out.json> [--text-runs N]

Real LLM calls: N text runs (split + roles) and one role pass per voice
labelling — roughly $0.05 per text run, $0.01 per role pass.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from eval_platform import _role, ground_truth, run_method, score, text_truth

from bristlenose.config import load_settings
from bristlenose.llm.client import LLMClient
from bristlenose.models import SpeakerRole, TranscriptSegment
from bristlenose.stages.s05b_identify_speakers import identify_speaker_roles_llm


async def pipeline_method(
    base: list[dict], client: LLMClient, audio: Path, model: Path,
) -> tuple[list[str], dict]:
    """The shipped stage 5b order: text split, voice pass, heuristic, role pass."""
    from bristlenose.stages.s05b_identify_speakers import (
        identify_speaker_roles_heuristic,
        split_single_speaker_llm,
    )
    from bristlenose.stages.s05b_voice import refine_speakers_by_voice

    segs = [TranscriptSegment.model_validate(s) for s in base]
    for s in segs:
        s.speaker_label = None
        s.speaker_role = SpeakerRole.UNKNOWN
    await split_single_speaker_llm(segs, client)
    rec = refine_speakers_by_voice(segs, audio, model)
    identify_speaker_roles_heuristic(segs)
    await identify_speaker_roles_llm(segs, client)
    return [_role(s) for s in segs], rec.to_dict()


async def voice_roles(base: list[dict], clusters: list[int | None], client: LLMClient) -> list[str]:
    segs = [TranscriptSegment.model_validate(s) for s in base]
    last = next((c for c in clusters if c is not None), 0)
    for seg, c in zip(segs, clusters):
        last = c if c is not None else last
        seg.speaker_label = "Speaker A" if last == 0 else "Speaker B"
        seg.speaker_role = SpeakerRole.UNKNOWN
    await identify_speaker_roles_llm(segs, client)
    return [_role(s) for s in segs]


def oracle(clusters: list[int | None], truth: list[dict]) -> list[str]:
    best = None
    for mp in ({0: "M", 1: "P"}, {0: "P", 1: "M"}):
        pred = [mp[c] if c is not None else "?" for c in clusters]
        ok = sum(p == t["truth"] for p, t in zip(pred, truth) if t["verified"])
        if best is None or ok > best[0]:
            best = (ok, pred)
    return best[1]


async def main(args: argparse.Namespace) -> None:
    segs = json.loads(Path(args.segments).read_text())[args.sid]
    vrows = json.loads(Path(args.voice).read_text())["rows"]
    assert len(vrows) == len(segs)
    clusters = [r["cluster"] for r in vrows]
    turns = json.loads(Path(args.docx).read_text())[args.docx_sid]
    truths = {"text": text_truth(segs, turns, args.moderator),
              "timing": ground_truth(segs, turns, args.moderator)}

    client = LLMClient(load_settings())
    runs: dict[str, list[str]] = {}
    records: dict[str, dict] = {}
    if args.audio:
        from bristlenose.stages.s05b_voice import resolve_voice_model

        model, why = resolve_voice_model(allow_fetch=True)
        assert model is not None, why
        for i in range(args.pipeline_runs):
            runs[f"pipeline_{i + 1}"], records[f"pipeline_{i + 1}"] = await pipeline_method(
                segs, client, Path(args.audio), model)
            print(f"pipeline_{i + 1} record: {records[f'pipeline_{i + 1}']}")
    for i in range(args.text_runs):
        runs[f"text_{i + 1}"] = await run_method("production", segs, client)
    v = await voice_roles(segs, clusters, client)
    runs["voice"] = v
    for i in range(args.text_runs):
        runs[f"voice+text_{i + 1}"] = [
            vv if c is not None else tt for vv, c, tt in zip(v, clusters, runs[f"text_{i + 1}"])
        ]

    results = {}
    for tname, truth in truths.items():
        for name, pred in runs.items():
            results[f"{name}@{tname}"] = score(pred, truth)
        results[f"voice_oracle@{tname}"] = score(oracle(clusters, truth), truth)
    for k, val in results.items():
        wrong = val["segments_scored"] - round(val["accuracy"] * val["segments_scored"])
        print(f"{k:24} wrong {wrong:3}/{val['segments_scored']}  {val}")
    Path(args.out).write_text(json.dumps(
        {"runs": runs, "records": records, "results": results, "truths": truths}, indent=1))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for a in ("segments", "sid", "voice", "docx", "docx_sid", "moderator", "out"):
        p.add_argument(a)
    p.add_argument("--text-runs", type=int, default=2)
    p.add_argument("--audio", help="16 kHz WAV: also run the shipped stage 5b (text split + voice pass)")
    p.add_argument("--pipeline-runs", type=int, default=2)
    asyncio.run(main(p.parse_args()))
