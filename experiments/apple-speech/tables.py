"""Markdown tables for the README from results-<engine>.json (numbers only, no text).

    .venv/bin/python experiments/apple-speech/tables.py speech
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from run_apple import OUT  # noqa: E402

#: What each recording is, so the extremes never reach a headline number.
GROUPS = {
    "Interviews and podcasts": ["es-2", "es-3", "fr-1", "fr-2", "de-1", "de-2", "de-3", "it-1",
                                "it-2", "pt-br-1", "pt-ao-1", "ko-2"],
    "Group talk (meeting, press conference, family meal, chat)": ["pt-pt-1", "ko-1", "ko-3",
                                                                  "fr-3", "fr-4"],
    "English (oral histories, research calls)": None,  # every en-* file
    "Japanese and Chinese": ["ja-1", "zh-1", "zh-2"],
    "Extreme (stress tests, not the yardstick)": ["es-1", "es-4", "es-5", "es-6", "it-3", "pt-pt-2"],
}


#: Public names for the research-call recordings, whose file names come from private
#: test folders.
DISPLAY = {"en-ikea-1": "en-call-1", "en-ikea-2": "en-call-2", "en-ikea-3": "en-call-3",
           "en-ikea-teams": "en-call-4", "en-zoom-sunday": "en-call-5"}


def pct(x):
    return "–" if x is None else f"{x:.0%}" if x >= 0.995 else f"{x:.1%}"


def row(sid, r):
    a, w, t = r["apple"], r["whisper"], r.get("timing", {})
    ref = ""
    if "ref_apple" in r:
        ra, rw = r["ref_apple"], r["ref_whisper"]
        ref = (f"{pct(ra['wer'])} (ins {ra['ins']}) / {pct(rw['wer'])} (ins {rw['ins']})")
    return (f"| {DISPLAY.get(sid, sid)} | {r['audio_s'] / 60:.0f} | {a['words']} / {w['words']} | "
            f"{pct(r['apple_vs_whisper_wer'])} | "
            f"{r.get('only_whisper_s', '–')} / {r.get('only_apple_s', '–')} | "
            f"{a['sound_without_words_s']} / {w.get('sound_without_words_s', '–')} | "
            f"{a['looped_segments'] + a['debris_segments'] + a['lone_long_segments']} / "
            f"{w['looped_segments'] + w['debris_segments'] + w['lone_long_segments']} | "
            f"{w['inaudible_s']} | "
            f"{a['sentences']} / {w['sentences']} | {a['fillers']} / {w['fillers']} | "
            f"{t.get('abs_median_ms', '–')} / {t.get('abs_p90_ms', '–')} | "
            f"{a['rtf']:.3f} / {w['rtf']:.3f} | {ref} |")


HEAD = ("| file | min | words A / W | A vs W | only-W s / only-A s | sound, no words A / W (s) "
        "| debris A / W | W inaudible s | sentences A / W | fillers A / W | Δ start med / p90 ms "
        "| RTF A / W | ref WER A / W |\n|" + "---|" * 13)


def main(engine: str) -> int:
    rows = json.loads((OUT / f"results-{engine}.json").read_text())
    calib = ["de-1", "fr-1", "it-1", "en-ikea-teams", "es-5", "es-6"]
    groups = GROUPS if engine == "speech" else {
        "Calibration: files SpeechTranscriber also ran": calib,
        "Languages SpeechTranscriber lacks": [k for k in rows if k not in calib]}
    for title, ids in groups.items():
        if ids is None:
            ids = sorted(k for k in rows if (k.startswith("en-") if engine == "speech" else True))
        ids = [i for i in ids if i in rows]
        if not ids:
            continue
        print(f"\n**{title}**\n\n{HEAD}")
        for sid in ids:
            print(row(sid, rows[sid]))
        sel = [rows[i] for i in ids]
        tot_a = sum(r["apple"]["words"] for r in sel)
        tot_w = sum(r["whisper"]["words"] for r in sel)
        aud = sum(r["audio_s"] for r in sel)
        only_w = sum(r.get("only_whisper_s", 0) for r in sel)
        only_a = sum(r.get("only_apple_s", 0) for r in sel)
        agree = statistics.median(r["apple_vs_whisper_wer"] for r in sel)
        print(f"\n_{len(ids)} files, {aud / 3600:.1f} h: Apple {tot_a} words, Whisper {tot_w} "
              f"({tot_a / max(1, tot_w):.0%}); median disagreement {agree:.1%}; one-sided "
              f"{only_w} s Whisper-only, {only_a} s Apple-only._")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "speech"))
