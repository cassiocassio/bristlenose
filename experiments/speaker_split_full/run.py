"""Speaker splitting: sampled window (shipped) vs whole transcript.

The shipped ``split_single_speaker_llm`` shows the LLM only the opening
5-8 minutes and propagates the last label to the rest of the session.
This re-runs the same prompt over the WHOLE transcript, then the same
role pass, and writes a per-segment comparison for hand-labelling.

Reads a project's cached ``speaker-info/<sid>.json`` (the shipped result)
and never writes into the project. Real LLM calls, ~$0.05 per session.

    .venv/bin/python experiments/speaker_split_full/run.py \
        "<project>/bristlenose-output" trial-runs/speaker-split/<name>.json
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from bristlenose.config import load_settings
from bristlenose.llm.boundary import wrap_untrusted
from bristlenose.llm.client import LLMClient
from bristlenose.llm.prompts import get_prompt_template
from bristlenose.llm.structured import SpeakerSplitAssignment
from bristlenose.models import TranscriptSegment
from bristlenose.stages.s05b_identify_speakers import identify_speaker_roles_llm


def _role(seg: TranscriptSegment) -> str:
    return {"researcher": "M", "participant": "P", "observer": "O"}.get(
        seg.speaker_role.value, "?"
    )


async def split_whole(segments: list[TranscriptSegment], client: LLMClient) -> dict:
    """The shipped prompt, with every segment in the sample."""
    tmpl = get_prompt_template("speaker-splitting")
    lines = "\n".join(f"[{i}] {s.text}" for i, s in enumerate(segments))
    user = tmpl.user.replace("(opening minutes, ", "(whole session, ").format(
        transcript_sample=wrap_untrusted("transcript", lines),
        segment_count=len(segments),
    )
    result = await client.analyze(
        system_prompt=tmpl.system,
        user_prompt=user,
        response_model=SpeakerSplitAssignment,
        prompt_template=tmpl,
    )
    bounds = sorted(result.boundaries, key=lambda b: b.segment_index)
    label, j = bounds[0].speaker_id, 1
    for i, seg in enumerate(segments):
        while j < len(bounds) and i >= bounds[j].segment_index:
            label = bounds[j].speaker_id
            j += 1
        seg.speaker_label = label
    return result.model_dump()


async def main(output_dir: Path, out: Path) -> None:
    settings = load_settings()
    client = LLMClient(settings)
    info_dir = output_dir / ".bristlenose" / "intermediate" / "speaker-info"
    sessions = []
    for path in sorted(info_dir.glob("s*.json")):
        shipped = json.loads(path.read_text())["segments_with_roles"]
        if not shipped:
            continue
        before = [TranscriptSegment.model_validate(s) for s in shipped]
        after = [TranscriptSegment.model_validate(s) for s in shipped]
        for s in after:
            s.speaker_label = None
            s.speaker_role = s.speaker_role.__class__("unknown")
        raw = await split_whole(after, client)
        infos = await identify_speaker_roles_llm(after, client)
        sessions.append({
            "session_id": path.stem,
            "model": settings.llm_model,
            "split_raw": raw,
            "roles": [i.__dict__ | {"role": i.role.value} for i in infos],
            "segments": [
                {
                    "i": i,
                    "start": b.start_time,
                    "end": b.end_time,
                    "text": b.text,
                    "sampled": _role(b),
                    "whole": _role(a),
                }
                for i, (b, a) in enumerate(zip(before, after))
            ],
        })
        agree = sum(s["sampled"] == s["whole"] for s in sessions[-1]["segments"])
        print(f"{path.stem}: {agree}/{len(before)} agree, "
              f"{len(raw['boundaries'])} boundaries")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"output_dir": str(output_dir), "sessions": sessions}, indent=1))
    print(f"wrote {out}")


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1]), Path(sys.argv[2])))
