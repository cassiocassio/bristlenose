"""Collect per-segment evidence for the [inaudible] net.

Runs the shipped stage-5 mlx path (each language's trial prompt, the net on) and
writes every segment with its word confidences to ``<out>/<id>.segments.json``
in the gitignored trial folder. Local compute only.

    .venv/bin/python experiments/transcript-readability/calibrate_inaudible.py OUT \
        ID=LANG=PATH.wav [...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from bristlenose.stages import s05_transcribe as s05

sys.path.insert(0, str(Path(__file__).parent))
from diagnostics_data import PROMPTS  # noqa: E402


def main(out: str, specs: list[str]) -> int:
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for spec in specs:
        sid, lang, path = spec.split("=", 2)
        dest = out_dir / f"{sid}.segments.json"
        if dest.exists():
            continue
        saved = dict(s05.STYLE_PROMPTS)
        s05.STYLE_PROMPTS.clear()
        s05.STYLE_PROMPTS[lang] = PROMPTS[lang]
        s05.SKIP_NET_ENABLED = True
        settings = type("S", (), {"whisper_model": "large-v3-turbo", "whisper_language": "auto"})()
        try:
            segs, detected = s05._init_mlx_backend(settings)(Path(path), settings)
        finally:
            s05.STYLE_PROMPTS.clear()
            s05.STYLE_PROMPTS.update(saved)
        rows = [{
            "start": s.start_time, "end": s.end_time, "text": s.text,
            "probs": [round(w.confidence, 3) for w in s.words],
        } for s in segs]
        dest.write_text(json.dumps({"id": sid, "lang": lang, "detected": detected,
                                    "prompt": PROMPTS[lang], "segments": rows},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
        print(sid, len(rows), "segments", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2:]))
