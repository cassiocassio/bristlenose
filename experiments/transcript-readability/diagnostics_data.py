"""Gather per-session transcription-quality numbers for the diagnostics mockup.

Runs the shipped stage-5 mlx path (style prompt, skipped-window net) on each
listed recording and writes ``<out>/<id>.json`` with numbers and time series
only — the transcript text is used to count, never stored. Local compute only.

    .venv/bin/python experiments/transcript-readability/diagnostics_data.py OUT_DIR \
        ID=LANG=PATH.wav [ID=LANG=PATH.wav ...]
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
import wave
from pathlib import Path

import numpy as np

from bristlenose.stages import s05_transcribe as s05

# The prompt each language would ship with, from the batch 1 trials.
PROMPTS = {
    "en": s05.STYLE_PROMPTS["en"],
    "es": "Eeh, pues, mm, la verdad es que sí, ¿no? Eh, más o menos, porque, mm, depende.",
    "pt": "Ahn, então, hum, na verdade é isso, né? Eh, mais ou menos, porque, ahn, depende.",
    "it": "Ehm, allora, mh, in realtà sì, no? Eh, più o meno, perché, ehm, dipende.",
    "fr": "Euh, bon, je pense que oui. Mais ça dépend, hein. Et alors ? Je ne sais pas trop.",
    "de": "Ähm, ja. Also, ich denke schon, äh, und dann? Genau.",
}
FILLERS = {
    "en": ["um", "uh", "erm", "er", "hmm", "mm"],
    "es": ["eh", "eeh", "mm", "em", "este"],
    "fr": ["euh", "heu", "hum", "mh", "hein", "ben"],
    "de": ["äh", "ähm", "öh", "hm", "äm"],
    "it": ["ehm", "eh", "mh", "uhm", "mm"],
    "pt": ["ahn", "hum", "né", "eh", "uhn"],
}
BIN_S = 10


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(record.getMessage())


def _audio(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0


def run(sid: str, lang: str, wav: Path) -> dict[str, object]:
    import mlx_whisper

    audio = _audio(wav)
    levels = s05.window_levels_dbfs(audio)
    finite = levels[np.isfinite(levels)]
    floor = float(np.percentile(finite, 10))
    duration = len(audio) / 16000

    calls: list[list[dict[str, object]]] = []
    real = mlx_whisper.transcribe

    def spy(a, **kw):
        r = real(a, **kw)
        calls.append(r.get("segments", []))
        return r

    mlx_whisper.transcribe = spy
    saved = dict(s05.STYLE_PROMPTS)
    s05.STYLE_PROMPTS.clear()
    s05.STYLE_PROMPTS[lang] = PROMPTS[lang]
    s05.SKIP_NET_ENABLED = True
    cap = _Capture()
    logging.getLogger("bristlenose.stages.s05_transcribe").addHandler(cap)
    logging.getLogger("bristlenose.stages.s05_transcribe").setLevel(logging.INFO)
    settings = type("S", (), {"whisper_model": "large-v3-turbo", "whisper_language": "auto"})()
    try:
        t0 = time.time()
        segs, detected = s05._init_mlx_backend(settings)(wav, settings)
        secs = time.time() - t0
    finally:
        mlx_whisper.transcribe = real
        s05.STYLE_PROMPTS.clear()
        s05.STYLE_PROMPTS.update(saved)

    log = "\n".join(cap.lines)
    num = lambda pat: int(m.group(1)) if (m := re.search(pat, log)) else 0  # noqa: E731
    main = calls[0] if calls else []
    # What the net saw: Whisper's segments after the two filters, as in stage 5,
    # so found, recovered and still empty all describe one transcript.
    prompt = PROMPTS[lang]
    seen = [x for x in main
            if s05.segment_has_signal(float(x["start"]), float(x["end"]), levels)
            and not s05.is_prompt_echo(str(x["text"]), prompt)]
    spans = [(float(x["start"]), float(x["end"]),
              len(s05.collapse_adjacent_repeats(str(x["text"]).strip()).split())) for x in seen]
    stretches = s05.find_skipped_stretches(spans, levels, duration)
    final_spans = [(s.start_time, s.end_time, len(s.text.split())) for s in segs]
    still_empty = s05.find_skipped_stretches(final_spans, levels, duration)

    words = [w for s in segs for w in s.words]
    toks = " ".join(s.text for s in segs).split()
    clean = [re.sub(r"[^\w']", "", t.lower()) for t in toks]
    fillers = {f: clean.count(f) for f in FILLERS[lang] if clean.count(f)}
    ends = sum(1 for t in toks if re.search(r"[.?!…][\"'”»)]*$", t))
    runs, cur = [], 0
    for t in toks:
        cur += 1
        if re.search(r"[.,?!;:…][\"'”»)]*$", t):
            runs.append(cur)
            cur = 0
    runs.append(cur)
    conf = np.array([w.confidence for w in words]) if words else np.array([1.0])

    nbins = int(np.ceil(duration / BIN_S))
    level_bins, wpm_bins, low_bins = [], [], []
    for i in range(nbins):
        lv = levels[i * BIN_S * 10:(i + 1) * BIN_S * 10]
        lv = lv[np.isfinite(lv)]
        level_bins.append(round(float(np.percentile(lv, 90)), 1) if lv.size else None)
        ws = [w for w in words if i * BIN_S <= w.start_time < (i + 1) * BIN_S]
        wpm_bins.append(round(len(ws) * 60 / BIN_S))
        low_bins.append(round(sum(w.confidence < 0.5 for w in ws) / len(ws), 2) if ws else None)

    return {
        "id": sid, "lang": lang, "detected": detected, "secs": round(secs),
        "duration_s": round(duration, 1),
        "audio": {
            "floor_dbfs": round(floor, 1),
            "peak_dbfs": round(float(finite.max()), 1),
            "active_share": round(float(np.mean(levels > min(floor, -45.0) + 15)), 3),
            "clipped_share": round(float(np.mean(np.abs(audio) >= 0.999)), 5),
        },
        "recognition": {
            "prompt": PROMPTS[lang],
            "decode_segments": len(main),
            "fallback_segments": sum(1 for x in main if float(x.get("temperature", 0)) > 0),
            "redecode_calls": max(0, len(calls) - 1),
            "mean_confidence": round(float(conf.mean()), 3),
            "low_confidence_words": int((conf < 0.5).sum()),
            "confidence_hist": np.histogram(conf, bins=10, range=(0, 1))[0].tolist(),
        },
        "repair": {
            "skipped_found": len(stretches),
            "skipped_seconds": round(sum(b - a for a, b in stretches)),
            "skipped_recovered": num(r"(\d+) recovered"),
            "recovered_words": num(r"recovered \((\d+) words"),
            "still_empty": [[round(a), round(b)] for a, b in still_empty],
            "found": [[round(a), round(b)] for a, b in stretches],
            "echoes_dropped": num(r"dropped (\d+) segment\(s\) that repeat"),
            "silent_dropped": num(r"dropped (\d+) segment\(s\) with no signal"),
        },
        "text": {
            "words": len(toks),
            "wpm": round(len(toks) / max(duration / 60, 0.01)),
            "sentence_ends": ends,
            "longest_unpunctuated": max(runs) if toks else 0,
            "fillers": fillers,
            "segments": len(segs),
        },
        "series": {"bin_s": BIN_S, "level_p90": level_bins, "wpm": wpm_bins, "low_conf": low_bins},
    }


def main(out: str, specs: list[str]) -> int:
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for spec in specs:
        sid, lang, path = spec.split("=", 2)
        dest = out_dir / f"{sid}.json"
        if dest.exists():
            continue
        r = run(sid, lang, Path(path))
        dest.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
        print(sid, json.dumps({k: r[k] for k in ("repair", "text")}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2:]))
