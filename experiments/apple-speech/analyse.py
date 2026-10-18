"""Compare Apple's transcribers with Bristlenose's Whisper path, file by file.

For every file with an Apple output (speech or dictation) and a Whisper output:

- words, sentence ends per 100 words, longest unpunctuated run (trial_prompts.metrics)
- speed: real-time factor (processing seconds / audio seconds)
- honesty, measured the same way on both engines, from word timings and the
  audio's 100 ms levels (s05's own helpers):
    * sound without words: stretches >= 8 s with sound (s05.find_skipped_stretches,
      the net's own rule) and fewer than 0.3 words a second
    * words over silence: words whose span never rises 10 dB above the noise floor
    * loops: segments in runs s05.find_segment_loops would remove
    * one-sided stretches: >= 8 s where one engine has >= 1 word/s and the other
      < 0.3 words/s (dropped by one, or invented by the other: read to adjudicate)
    * marked inaudible: Whisper's inaudible gaps (Apple has no marker)
- agreement: word error rate of Apple against Whisper (characters for CJK)
- true WER against a reference where one exists (es-5, es-6: Ameresco)
- timing: for words both engines agree on (matching runs of 3+), the start-time
  difference, its median and 90th percentile, and its slope over the file (drift)

    .venv/bin/python experiments/apple-speech/analyse.py [speech|dictation]

Writes trial-runs/apple-speech/results-<engine>.json; prints a table. Numbers only.
"""

from __future__ import annotations

import difflib
import json
import re
import sys
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "transcript-readability"))
from run_apple import OUT, corpus  # noqa: E402
from score_wer import REFERENCES, _words, reference_words, wer  # noqa: E402
from trial_prompts import metrics  # noqa: E402

from bristlenose.stages import s05_transcribe as s05  # noqa: E402
from bristlenose.stages.s06_merge_transcript import reading_length  # noqa: E402

CJK = {"ja", "zh", "ko"}  # ko has spaces, but WER on eojeol is harsh; use characters
TRIALS = Path("trial-runs/whisper-prompt-samples/trials")
REF_DIR = Path("trial-runs/whisper-prompt-samples/es/reference")

#: Conditions shipped per language (STYLE_PROMPTS as of 13 Oct 2026), for the
#: languages only DictationTranscriber covers, where the earlier trial outputs of
#: the same code stand in for a fresh Whisper run.
SHIPPED = {"ca": "prompt-v2", "sv": "prompt", "da": "prompt", "no": "prompt",
           "tr": "prompt-v2", "nl": "none", "pl": "none", "cs": "none", "ru": "none",
           "uk": "none", "fi": "none"}


def levels_of(wav_path: str) -> tuple[np.ndarray, float]:
    with wave.open(wav_path, "rb") as w:
        assert w.getframerate() == 16000 and w.getnchannels() == 1
        raw = w.readframes(w.getnframes())
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return np.asarray(s05.window_levels_dbfs(audio)), len(audio) / 16000


def tokens(text: str, lang: str) -> list[str]:
    if lang in CJK:
        return [c for c in re.sub(r"[^\w]", "", text.lower()) if not c.isdigit()]
    return _words(text)


def wer_sdi(ref: list[str], hyp: list[str]) -> dict:
    """WER with substitutions, deletions and insertions (full matrix; references only).

    Insertions are words the transcript has and the reference does not: the
    nearest thing to invented text a word count can show.
    """
    vocab: dict[str, int] = {}
    r = np.array([vocab.setdefault(w, len(vocab)) for w in ref])
    h = np.array([vocab.setdefault(w, len(vocab)) for w in hyp])
    n, m = len(r), len(h)
    idx = np.arange(m + 1)
    rows = np.empty((n + 1, m + 1), dtype=np.int32)
    rows[0] = idx
    for i in range(1, n + 1):
        prev = rows[i - 1]
        cost = (h != r[i - 1]).astype(np.int32)
        cur = np.empty(m + 1, dtype=np.int32)
        cur[0] = i
        cur[1:] = np.minimum(prev[1:] + 1, prev[:-1] + cost)
        rows[i] = np.minimum.accumulate(cur - idx) + idx
    s = d = ins = 0
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and rows[i, j] == rows[i - 1, j - 1] + (r[i - 1] != h[j - 1]):
            s += int(r[i - 1] != h[j - 1])
            i, j = i - 1, j - 1
        elif i > 0 and rows[i, j] == rows[i - 1, j] + 1:
            d, i = d + 1, i - 1
        else:
            ins, j = ins + 1, j - 1
    return {"wer": round((s + d + ins) / max(1, n), 3), "sub": s, "del": d, "ins": ins,
            "ref_words": n, "hyp_words": m}


def word_spans(words: list[dict]) -> list[tuple[float, float, float]]:
    return [(w["start"], max(w["end"], w["start"] + 0.05), max(reading_length(w["text"]), 0.4))
            for w in words if w["text"].strip()]


def sound_without_words(words, levels, total) -> float:
    return sum(b - a for a, b in s05.find_skipped_stretches(word_spans(words), levels, total))


def words_over_silence(words, levels) -> int:
    finite = levels[np.isfinite(levels)]
    floor = float(np.percentile(finite, 10)) if finite.size else -90.0
    n = 0
    for w in words:
        i0 = max(0, int(w["start"] * 10))
        i1 = min(len(levels), int(np.ceil(w["end"] * 10)) + 1)
        if i1 > i0 and float(np.max(levels[i0:i1])) < floor + 10:
            n += 1
    return n


def looped(segs) -> int:
    runs = s05.find_segment_loops([(s["start"], s["end"], s["text"]) for s in segs])
    return sum(j - i for i, j in runs)


def rate(words, total) -> np.ndarray:
    """Words per second in each 1 s bin."""
    r = np.zeros(int(total) + 1)
    for w in words:
        r[min(int(w["start"]), len(r) - 1)] += reading_length(w["text"]) or 0.4
    return r


def one_sided(a_words, b_words, total) -> list[tuple[int, int]]:
    """Stretches >= 8 s where A has >= 1 word/s and B < 0.3 (8 s moving means)."""
    ra, rb = rate(a_words, total), rate(b_words, total)
    k = np.ones(8) / 8
    ma, mb = np.convolve(ra, k, "same"), np.convolve(rb, k, "same")
    flag = (ma >= 1.0) & (mb < 0.3)
    out, i = [], 0
    while i < len(flag):
        if flag[i]:
            j = i
            while j < len(flag) and flag[j]:
                j += 1
            if j - i >= 4:  # a flagged 8 s mean centred on >= 4 bins: a stretch of ~8 s+
                out.append((max(0, i - 4), min(len(flag), j + 4)))
            i = j
        else:
            i += 1
    return out


def timing(a_words, b_words, lang) -> dict:
    def norm(w):
        t = tokens(w["text"], lang)
        return "".join(t)
    a = [(norm(w), w) for w in a_words]
    b = [(norm(w), w) for w in b_words]
    a = [x for x in a if x[0]]
    b = [x for x in b if x[0]]
    sm = difflib.SequenceMatcher(None, [x[0] for x in a], [x[0] for x in b], autojunk=False)
    d, t = [], []
    for blk in sm.get_matching_blocks():
        if blk.size >= 3:
            for k in range(blk.size):
                wa, wb = a[blk.a + k][1], b[blk.b + k][1]
                d.append(wa["start"] - wb["start"])
                t.append(wb["start"])
    if len(d) < 20:
        return {"matched": len(d)}
    d_arr, t_arr = np.array(d), np.array(t)
    slope = float(np.polyfit(t_arr / 3600, d_arr, 1)[0]) if np.ptp(t_arr) > 60 else float("nan")
    return {"matched": len(d), "median_ms": round(float(np.median(d_arr)) * 1000),
            "abs_median_ms": round(float(np.median(np.abs(d_arr))) * 1000),
            "abs_p90_ms": round(float(np.percentile(np.abs(d_arr), 90)) * 1000),
            "over_1s": int(np.sum(np.abs(d_arr) > 1.0)),
            "drift_ms_per_hour": round(slope * 1000) if slope == slope else None}


_RUN_ON = re.compile(r"(\w{2,6}?)\1{4,}")


def visible_words(rec: dict, lang: str) -> list[dict]:
    """The words a reader actually gets: Whisper's word list keeps the raw decode, but
    stage 5 collapses repeats in the segment TEXT ("Tr Tr Tr ..." becomes "Tr"), so a
    word counts only if it aligns to a token of its segment's text."""
    if rec.get("engine") != "whisper":
        return rec["words"]
    if lang in ("ja", "zh"):
        # No spaces to align on: drop consecutive repeats, as the text collapse does.
        kept: list[dict] = []
        for w in rec["words"]:
            if not kept or "".join(tokens(w["text"], lang)) != "".join(tokens(kept[-1]["text"], lang)):
                kept.append(w)
        return kept
    out = []
    by_seg = sorted(rec["words"], key=lambda w: w["start"])
    k = 0
    for seg in rec["segments"]:
        if seg.get("inaudible"):
            continue
        inside = []
        while k < len(by_seg) and by_seg[k]["start"] < seg["end"] + 0.01:
            if by_seg[k]["start"] >= seg["start"] - 0.01:
                inside.append(by_seg[k])
            k += 1
        keys = ["".join(tokens(w["text"], lang)) for w in inside]
        text_keys = ["".join(tokens(t, lang)) for t in seg["text"].split()]
        sm = difflib.SequenceMatcher(None, keys, text_keys, autojunk=False)
        for blk in sm.get_matching_blocks():
            out.extend(inside[blk.a:blk.a + blk.size])
    return out


def _repeats(toks: list[str]) -> int:
    """Most consecutive repeats of any phrase of 1-4 words ("es muy divertido" x 10)."""
    best = 1
    for n in range(1, 5):
        for i in range(len(toks) - n):
            k, j = 1, i + n
            while toks[j:j + n] == toks[i:i + n]:
                k, j = k + 1, j + n
            best = max(best, k)
    return best


def debris(segs: list[dict]) -> int:
    """Segments whose visible text still carries a loop: a phrase of 1-4 words repeated 8+ times in a
    row, or a run-on syllable ("cipcipcipcip"). Real speech rarely does either."""
    n = 0
    for s in segs:
        if s.get("inaudible"):
            continue
        toks = [re.sub(r"\W", "", t.lower()) for t in s["text"].split()]
        toks = [t for t in toks if t]
        if _RUN_ON.search(s["text"].lower()) or _repeats(toks) >= 8:
            n += 1
    return n


def lone_long(segs: list[dict]) -> int:
    """Segments of 15 s or more holding fewer than 4 words: a long stretch handed back
    as a fragment ("Tr" over 30 s), which reads as if almost nothing was said."""
    return sum(1 for s in segs if not s.get("inaudible") and s["end"] - s["start"] >= 15
               and reading_length(s["text"]) < 4)


def whisper_for(item) -> dict | None:
    p = OUT / "whisper" / f"{item['id']}.whisper.json"
    if p.exists():
        return json.loads(p.read_text())
    lang = item["lang"]
    if lang in SHIPPED:
        q = TRIALS / f"{item['id']}.{SHIPPED[lang]}+net+inaudible.json"
        if q.exists():
            d = json.loads(q.read_text())
            d["words"] = None  # the trial files kept no word timings
            d["wall_s"] = d.get("secs")
            d["from_trials"] = True
            return d
    return None


def main(engine: str) -> int:
    rows = {}
    for item in corpus():
        ap = OUT / "apple" / f"{item['id']}.{engine}.json"
        wh = whisper_for(item)
        if not ap.exists() or wh is None:
            continue
        a = json.loads(ap.read_text())
        lang = item["lang"]
        levels, total = levels_of(item["wav"])
        a_text = [s["text"] for s in a["segments"]]
        w_text = [s["text"] for s in wh["segments"] if not s.get("inaudible")]
        a_tok, w_tok = tokens(" ".join(a_text), lang), tokens(" ".join(w_text), lang)
        agree, _ = wer(w_tok, a_tok) if w_tok else (float("nan"), 0)
        row = {
            "lang": lang, "audio_s": round(total),
            "apple": {"words": round(sum(reading_length(t) for t in a_text)),
                      "rtf": round(a["analyse_s"] / total, 4), "prepare_s": round(a["prepare_s"], 2),
                      "sound_without_words_s": round(sound_without_words(a["words"], levels, total)),
                      "words_over_silence": words_over_silence(a["words"], levels),
                      "looped_segments": looped(a["segments"]),
                      "debris_segments": debris(a["segments"]),
                      "lone_long_segments": lone_long(a["segments"]),
                      **{k: v for k, v in metrics(a_text, lang).items()
                         if k in ("sentences", "longest_unpunctuated", "fillers")}},
            "whisper": {"words": round(sum(reading_length(t) for t in w_text)),
                        "rtf": round(wh["wall_s"] / total, 4) if wh.get("wall_s") else None,
                        "cold": wh.get("cold"),
                        "inaudible_s": round(sum(s["end"] - s["start"] for s in wh["segments"]
                                                 if s.get("inaudible"))),
                        "looped_segments": looped([s for s in wh["segments"] if not s.get("inaudible")]),
                        "debris_segments": debris(wh["segments"]),
                        "lone_long_segments": lone_long(wh["segments"]),
                        "from_trials": bool(wh.get("from_trials")),
                        **{k: v for k, v in metrics(w_text, lang).items()
                           if k in ("sentences", "longest_unpunctuated", "fillers")}},
            "apple_vs_whisper_wer": round(agree, 3),
        }
        if wh.get("words"):
            wh["words"] = visible_words(wh, lang)
            row["whisper"]["sound_without_words_s"] = round(sound_without_words(wh["words"], levels, total))
            row["whisper"]["words_over_silence"] = words_over_silence(wh["words"], levels)
            only_w = one_sided(wh["words"], a["words"], total)
            only_a = one_sided(a["words"], wh["words"], total)
            row["only_whisper_s"] = sum(j - i for i, j in only_w)
            row["only_apple_s"] = sum(j - i for i, j in only_a)
            row["only_whisper_spans"] = only_w
            row["only_apple_spans"] = only_a
            row["timing"] = timing(a["words"], wh["words"], lang)
        if item["id"] in REFERENCES:
            ref = reference_words(REF_DIR / f"{REFERENCES[item['id']]}.txt")
            row["ref_apple"] = wer_sdi(ref, _words(" ".join(a_text)))
            row["ref_whisper"] = wer_sdi(ref, _words(" ".join(w_text)))
            row["ref_wer_apple"] = row["ref_apple"]["wer"]
            row["ref_wer_whisper"] = row["ref_whisper"]["wer"]
        rows[item["id"]] = row
        t = row.get("timing", {})
        print(f"{item['id']:16} {lang} {total/60:5.1f}m  words A {row['apple']['words']:5} W {row['whisper']['words']:5}"
              f"  A~W {agree:6.1%}  RTF A {row['apple']['rtf']:.4f} W {row['whisper']['rtf'] or 0:.4f}"
              f"  swW A {row['apple']['sound_without_words_s']:4}s W {row['whisper'].get('sound_without_words_s', '-')!s:>4}s"
              f"  only W {row.get('only_whisper_s', '-')!s:>4}s A {row.get('only_apple_s', '-')!s:>4}s"
              f"  loops A {row['apple']['looped_segments']} W {row['whisper']['looped_segments']}"
              f"  debris A {row['apple']['debris_segments']} W {row['whisper']['debris_segments']}"
              f"  lone A {row['apple']['lone_long_segments']} W {row['whisper']['lone_long_segments']}"
              f"  silent-words A {row['apple']['words_over_silence']} W {row['whisper'].get('words_over_silence', '-')}"
              f"  dt {t.get('abs_median_ms', '-')}/{t.get('abs_p90_ms', '-')}ms drift {t.get('drift_ms_per_hour', '-')}"
              + (f"  refWER A {row['ref_wer_apple']:.1%} W {row['ref_wer_whisper']:.1%}" if "ref_wer_apple" in row else ""),
              flush=True)
    (OUT / f"results-{engine}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "speech"))
