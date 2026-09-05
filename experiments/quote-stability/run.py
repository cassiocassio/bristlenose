#!/usr/bin/env python3
"""Re-extract the same transcripts N times and record what changes.

WHY THIS EXISTS AGAIN

The Jul 2026 validation (`docs/design-incremental-analysis.md` § Validation) ran
on a **private** corpus with `claude-sonnet-4` at temperature 0.1, and its
harness was deliberately kept out of the public tree because the data was
participants'. Two things have since changed underneath its numbers:

  - the ChatGPT and Gemini defaults moved model FAMILY (`gpt-5.6-terra`,
    `gemini-3.8-flash`), and
  - the temperature pin is gone from the Claude path entirely — sampling
    parameters are refused on every Claude model after 4.6.

So the recovery rates the incremental-analysis merge rule is built on (~81%
single-match, ~95% union, a ~9% fragile tail) are measurements of a
configuration we no longer ship. This re-runs the measurement on the corpus we
can publish: FOSSDA, open-source interviews, already transcribed.

WHAT IT DOES NOT DO

Transcribe. It rehydrates the cached `session_segments.json` and
`topic_boundaries.json` from an existing run and calls the real
`extract_quotes` stage, so every pass costs one LLM call per session and
nothing else. The reference run in that same directory is pass 0.

    ./run.py --model claude-sonnet-4-6 --sessions s1 s4 s9 s10 --passes 5
    ./run.py --plan ...                 # cost estimate, makes no calls

Output: `out/<provider>_<model>/pass_<n>.json`, one file per pass, each a list
of extracted quotes. `analyse.py` reads them.
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

from bristlenose.config import load_settings  # noqa: E402
from bristlenose.llm.client import LLMClient  # noqa: E402
from bristlenose.models import (  # noqa: E402
    PiiCleanTranscript,
    SessionTopicMap,
)
from bristlenose.stages.s09_quote_extraction import extract_quotes  # noqa: E402

CORPUS = ROOT / "trial-runs/fossda-opensource/bristlenose-output/.bristlenose/intermediate"
OUT = Path(__file__).resolve().parent / "out"


def load_corpus(session_ids: list[str]) -> tuple[list, list]:
    """Rehydrate the cached transcripts and topic maps for the chosen sessions."""
    segs = json.loads((CORPUS / "session_segments.json").read_text())
    tmaps = {t["session_id"]: t for t in json.loads((CORPUS / "topic_boundaries.json").read_text())}

    transcripts, topic_maps = [], []
    for sid in session_ids:
        if sid not in segs:
            raise SystemExit(f"error: no session {sid!r} in {CORPUS} (have: {', '.join(segs)})")
        rows = segs[sid]
        # source_file / session_date / duration_seconds are required by the model
        # but are not carried in session_segments.json. None of them reaches the
        # extraction prompt -- it sees the segment text and the topic boundaries
        # and nothing else -- so they are reconstructed rather than faked from
        # somewhere misleading: the duration is the transcript's own last
        # end_time, and the filename is the session id.
        transcripts.append(
            PiiCleanTranscript.model_validate({
                "session_id": sid,
                "participant_id": tmaps[sid]["participant_id"],
                "source_file": f"{sid}.mp4",
                "session_date": "2026-01-01T00:00:00",
                "duration_seconds": max((r.get("end_time") or 0.0) for r in rows),
                "segments": rows,
            })
        )
        topic_maps.append(SessionTopicMap.model_validate(tmaps[sid]))
    return transcripts, topic_maps


def plan(transcripts: list, passes: int, model: str) -> str:
    """An estimate in dollars, from the repo's own price table -- not arithmetic
    in a comment. Spending someone's API credit is a thing to show before doing."""
    from bristlenose.llm.pricing import PRICING

    chars = sum(len(s.text) for t in transcripts for s in t.segments)
    calls = len(transcripts) * passes
    # ~4 chars/token, plus ~1.5k tokens of prompt template per call.
    in_tok = int(chars / 4) * passes + 1500 * calls
    # The reference run produced ~1 quote per 1,200 transcript chars, and a
    # serialised quote with its metadata runs ~200 tokens.
    out_tok = int(chars / 1200) * 200 * passes
    lines = [f"{len(transcripts)} session(s) x {passes} pass(es) = {calls} calls",
             f"  transcript chars per pass : {chars:,}",
             f"  estimated tokens          : {in_tok:,} in / {out_tok:,} out"]
    if model in PRICING:
        pin, pout = PRICING[model]
        cost = in_tok / 1e6 * pin + out_tok / 1e6 * pout
        lines.append(f"  estimated cost           : ${cost:.2f} on {model}")
    else:
        lines.append(f"  estimated cost           : unknown -- {model} is not in PRICING")
    return "\n".join(lines)


async def one_pass(transcripts, topic_maps, provider: str, model: str) -> list[dict]:
    settings = load_settings(llm_provider=provider, llm_model=model)
    client = LLMClient(settings)
    quotes, outcome = await extract_quotes(
        transcripts=transcripts, topic_maps=topic_maps,
        llm_client=client, concurrency=2,
    )
    if outcome.failed:
        print(f"    (stage reported {len(outcome.failed)} session failure(s))", file=sys.stderr)
    return [q.model_dump(mode="json") for q in quotes]


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", default="anthropic")
    ap.add_argument("--model", required=True)
    ap.add_argument("--sessions", nargs="+", default=["s1", "s4", "s9", "s10"],
                    help="default is four mid-sized sessions, ~91k chars total")
    ap.add_argument("--passes", type=int, default=5)
    ap.add_argument("--plan", action="store_true", help="print the cost estimate, make no calls")
    args = ap.parse_args()

    transcripts, topic_maps = load_corpus(args.sessions)
    print(plan(transcripts, args.passes, args.model))
    if args.plan:
        return 0

    outdir = OUT / f"{args.provider}_{args.model}"
    outdir.mkdir(parents=True, exist_ok=True)
    for n in range(1, args.passes + 1):
        target = outdir / f"pass_{n}.json"
        if target.exists():
            # Never silently re-spend. A pass already on disk is a pass paid for;
            # the 3 Jul double-spend came from re-running a step whose guard had
            # quietly failed.
            print(f"  pass {n}: already on disk, skipping")
            continue
        t0 = time.perf_counter()
        quotes = await one_pass(transcripts, topic_maps, args.provider, args.model)
        target.write_text(json.dumps(quotes, indent=1))
        print(f"  pass {n}: {len(quotes):>4} quotes  {time.perf_counter() - t0:6.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
