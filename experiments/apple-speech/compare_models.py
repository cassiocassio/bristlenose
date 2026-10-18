"""A smaller Whisper model against large-v3-turbo, as a stopgap before turbo arrives.

Same measures as analyse.py, with the smaller model in Apple's place: words, how far
it is from turbo, one-sided stretches, sound without words, visible loops, inaudible
gaps, real-time factor. Both through the product's own stage-5 path (run_whisper.py).
Turbo is the fresh run where one exists, else the 13 Oct trial output of the same code.

    .venv/bin/python experiments/apple-speech/compare_models.py small|base

Writes trial-runs/apple-speech/results-<model>.json; prints a line a file. Numbers only.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import analyse as A  # noqa: E402
from run_apple import OUT, corpus  # noqa: E402

from bristlenose.stages.s06_merge_transcript import reading_length  # noqa: E402


def main(model: str) -> int:
    rows = {}
    for item in corpus():
        p = OUT / f"whisper-{model}" / f"{item['id']}.whisper.json"
        turbo = A.whisper_for(item)
        if not p.exists() or turbo is None:
            continue
        lang = item["lang"]
        small = json.loads(p.read_text())
        levels, total = A.levels_of(item["wav"])
        s_text = [s["text"] for s in small["segments"] if not s.get("inaudible")]
        t_text = [s["text"] for s in turbo["segments"] if not s.get("inaudible")]
        dist, _ = A.wer(A.tokens(" ".join(t_text), lang), A.tokens(" ".join(s_text), lang))
        s_words = A.visible_words(small, lang)
        row = {
            "lang": lang, "audio_s": round(total),
            "words_small": round(sum(reading_length(t) for t in s_text)),
            "words_turbo": round(sum(reading_length(t) for t in t_text)),
            "small_vs_turbo": round(dist, 3),
            "rtf_small": round(small["wall_s"] / total, 4),
            "rtf_turbo": round(turbo["wall_s"] / total, 4) if turbo.get("wall_s") else None,
            "debris_small": A.debris(small["segments"]) + A.lone_long(small["segments"]),
            "debris_turbo": A.debris(turbo["segments"]) + A.lone_long(turbo["segments"]),
            "inaudible_small_s": round(sum(s["end"] - s["start"] for s in small["segments"]
                                           if s.get("inaudible"))),
            "sound_without_words_small_s": round(A.sound_without_words(s_words, levels, total)),
        }
        if turbo.get("words"):
            t_words = A.visible_words(turbo, lang)
            row["sound_without_words_turbo_s"] = round(A.sound_without_words(t_words, levels, total))
            row["only_turbo_s"] = sum(j - i for i, j in A.one_sided(t_words, s_words, total))
            row["only_small_s"] = sum(j - i for i, j in A.one_sided(s_words, t_words, total))
        rows[item["id"]] = row
        print(f"{item['id']:16} {lang} {total / 60:5.1f}m words {model} {row['words_small']:5} "
              f"turbo {row['words_turbo']:5}  dist {dist:6.1%}  RTF {row['rtf_small']:.4f}/"
              f"{row['rtf_turbo'] or 0:.4f}  only-T {row.get('only_turbo_s', '-')}s "
              f"only-S {row.get('only_small_s', '-')}s  swW S {row['sound_without_words_small_s']}s "
              f"T {row.get('sound_without_words_turbo_s', '-')}s  debris {row['debris_small']}/"
              f"{row['debris_turbo']}", flush=True)
    if rows:
        print(f"median distance from turbo: "
              f"{statistics.median(r['small_vs_turbo'] for r in rows.values()):.1%}; "
              f"median RTF {statistics.median(r['rtf_small'] for r in rows.values()):.4f}")
    (OUT / f"results-{model}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "small"))
