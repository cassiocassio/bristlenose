#!/usr/bin/env python3
"""Run stage 8 (topic segmentation) live, padded vs unpadded, and audit the result.

WHY THIS EXISTS

`run.py` rehydrates CACHED topic boundaries and only exercises s09, so the
minutes-as-hours defect was measured on quotes alone. s08 has the same exposure
-- it feeds the same `full_text()` into the same kind of prompt and parses the
answer back with the same `parse_timecode` -- and unlike s09 it has NO range
guard, so a mangled boundary is corrected nowhere and reported nowhere.

The cached corpus already shows it: 38 of 133 boundaries out of range, every one
of them resolving under /60 with the exact-minute signature. That is evidence the
defect reached s08, but not proof the padding fixes it, and not proof of which
model produced the cache. This runs both arms live.

    ./run_s08.py --provider openai --model gpt-5.6-terra --arm both

Output: out_s08/<provider>_<model>__<arm>/boundaries.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import bristlenose.models as bn_models  # noqa: E402
from bristlenose.config import load_settings  # noqa: E402
from bristlenose.llm.client import LLMClient  # noqa: E402
from bristlenose.models import PiiCleanTranscript  # noqa: E402
from bristlenose.stages.s08_topic_segmentation import segment_topics  # noqa: E402
from bristlenose.utils.timecodes import format_timecode  # noqa: E402

CORPUS = ROOT / "trial-runs/fossda-opensource/bristlenose-output/.bristlenose/intermediate"
OUT = Path(__file__).resolve().parent / "out_s08"


def load_corpus(session_ids: list[str]) -> list[PiiCleanTranscript]:
    segs = json.loads((CORPUS / "session_segments.json").read_text())
    tmaps = {t["session_id"]: t for t in json.loads((CORPUS / "topic_boundaries.json").read_text())}
    out = []
    for sid in session_ids:
        rows = segs[sid]
        out.append(PiiCleanTranscript.model_validate({
            "session_id": sid,
            "participant_id": tmaps[sid]["participant_id"],
            "source_file": f"{sid}.mp4",
            "session_date": "2026-01-01T00:00:00",
            "duration_seconds": max((r.get("end_time") or 0.0) for r in rows),
            "segments": rows,
        }))
    return out


async def one_arm(transcripts, provider: str, model: str, padded: bool) -> list[dict]:
    """Run s08 once. `padded=False` restores the PRE-FIX rendering by pointing
    models.full_text's helper back at `format_timecode` -- a monkeypatch in the
    harness, so production code carries no switch for a behaviour we removed."""
    original = bn_models.format_timecode_prompt
    if not padded:
        bn_models.format_timecode_prompt = format_timecode
    try:
        client = LLMClient(load_settings(llm_provider=provider, llm_model=model))
        maps, outcome = await segment_topics(transcripts, client, concurrency=2)
        if outcome.failed:
            print(f"    (stage reported {len(outcome.failed)} failure(s))", file=sys.stderr)
        return [m.model_dump(mode="json") for m in maps]
    finally:
        bn_models.format_timecode_prompt = original


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", default="openai")
    ap.add_argument("--model", default="gpt-5.6-terra")
    ap.add_argument("--sessions", nargs="+", default=["s1", "s4", "s9", "s10"])
    ap.add_argument("--arm", choices=["padded", "unpadded", "both"], default="both")
    args = ap.parse_args()

    transcripts = load_corpus(args.sessions)
    chars = sum(len(s.text) for t in transcripts for s in t.segments)
    arms = ["unpadded", "padded"] if args.arm == "both" else [args.arm]
    print(f"{len(transcripts)} session(s) x {len(arms)} arm(s) = "
          f"{len(transcripts) * len(arms)} calls, {chars:,} transcript chars per arm")

    for arm in arms:
        outdir = OUT / f"{args.provider}_{args.model}__{arm}"
        outdir.mkdir(parents=True, exist_ok=True)
        target = outdir / "boundaries.json"
        if target.exists():
            print(f"  {arm}: already on disk, skipping")
            continue
        t0 = time.perf_counter()
        maps = await one_arm(transcripts, args.provider, args.model, arm == "padded")
        n = sum(len(m["boundaries"]) for m in maps)
        if n == 0:
            # A stage that failed every call still returns a well-formed list of
            # empty maps. Writing that produces a valid-looking boundaries.json
            # which the skip-if-exists guard above would then honour forever --
            # a failed arm that can never be re-run. Measured: an exhausted API
            # credit did exactly this. Refuse to record an empty arm.
            print(f"  {arm}: NO boundaries from any session -- not recorded "
                  f"(check the log for call failures)", file=sys.stderr)
            continue
        target.write_text(json.dumps(maps, indent=1))
        print(f"  {arm}: {n:>4} boundaries  {time.perf_counter() - t0:6.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
