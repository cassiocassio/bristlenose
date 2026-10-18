"""Run Bristlenose's shipped Whisper path over the same files as run_apple.py.

Uses `s05._init_mlx_backend` exactly as the pipeline does: large-v3-turbo,
language auto-detected, the shipped style prompts, the signal gate, loop removal,
the skipped-window net and the inaudible marker. Keeps word timings and the
repair counts the backend leaves in the quality sink, and times each file
(the first file of a process includes loading the model: "cold").

    .venv/bin/python experiments/apple-speech/run_whisper.py [ids or langs...]

Outputs: trial-runs/apple-speech/whisper/<id>.whisper.json. Local compute only.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from run_apple import OUT, corpus  # noqa: E402

from bristlenose.stages import s05_transcribe as s05  # noqa: E402


def main(only: list[str]) -> int:
    (OUT / "whisper").mkdir(parents=True, exist_ok=True)
    settings = type("S", (), {"whisper_model": "large-v3-turbo", "whisper_language": "auto"})()
    fn = s05._init_mlx_backend(settings)
    first = True
    for item in corpus():
        if only and item["id"] not in only and item["lang"] not in only:
            continue
        out = OUT / "whisper" / f"{item['id']}.whisper.json"
        if out.exists():
            continue
        sink: dict = {}
        token = s05._QUALITY_SINK.set(sink)
        try:
            t0 = time.time()
            segs, detected = fn(Path(item["wav"]), settings)
            secs = time.time() - t0
        finally:
            s05._QUALITY_SINK.reset(token)
        audio_s = sink.get("duration_s")
        rec = {
            "engine": "whisper", "id": item["id"], "lang": item["lang"], "detected": detected,
            "cold": first, "wall_s": round(secs, 2), "audio_s": audio_s,
            "repair": sink.get("repair"), "recognition": sink.get("recognition"),
            "segments": [
                {"start": s.start_time, "end": s.end_time, "text": s.text,
                 **({"inaudible": True} if s.inaudible else {})}
                for s in segs
            ],
            "words": [
                {"start": w.start_time, "end": w.end_time, "text": w.text, "conf": w.confidence}
                for s in segs for w in s.words
            ],
        }
        out.write_text(json.dumps(rec, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        rtf = secs / audio_s if audio_s else float("nan")
        print(f"{item['id']} {detected} audio {audio_s or 0:.0f}s wall {secs:.1f}s RTF {rtf:.4f}"
              f"{' cold' if first else ''}", flush=True)
        first = False
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
