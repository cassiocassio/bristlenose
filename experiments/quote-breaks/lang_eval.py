"""How well long quotes break, per language, on real Whisper transcripts.

The gold is each transcript's own punctuation: strip it (as Whisper does on a bad run), split
quote-sized runs with `board_layout.split_quote`, and count how often a break lands where a mark
was — a sentence end, or any mark. Run with and without the pause at each segment join.
docs/research/board-quote-breaks.md § Measured has the results.

Reads (gitignored, on the maintainer's machine): trial-runs/whisper-prompt-samples (19 languages,
from the Whisper style-prompt research), the fossda trial's punctuated sessions for English, and
the Sapporo demo for Japanese. Extra `{"segments": [{"start", "end", "text"}]}` files can be named
as `lang=path` arguments.

    .venv/bin/python experiments/quote-breaks/lang_eval.py [--half tune|held] [--why LANG] [ja=extra.segments.json …]

``--half`` scores one half of each language's recordings: sorted, alternating, fixed before
any tuning looked at the data, so the rules are tuned on ``tune`` and judged on ``held``.
``--why LANG`` lists the words either side of each break that missed a mark, on the half given.
"""

from __future__ import annotations

import collections
import glob
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from bristlenose import board_layout as bl  # noqa: E402

TRIALS = "trial-runs/whisper-prompt-samples"
MARKS = re.compile(r"[.?!…;:,—–。！？、，；：「」『』“”„\"«»¿¡()（）]")


def trial(stem: str) -> list[dict]:
    for cond in ("prompt-v2+net+inaudible", "prompt+net+inaudible", "none+net+inaudible"):
        f = Path(f"{TRIALS}/trials/{stem}.{cond}.json")
        if f.exists():
            return json.loads(f.read_text())["segments"]
    return []


def english() -> list[list[dict]]:
    out = [json.loads(Path(f"{TRIALS}/calib/ikea-s1.segments.json").read_text())["segments"]]
    fossda = Path("trial-runs/fossda-opensource/bristlenose-output/.bristlenose/intermediate/"
                  "session_segments.json")
    for segs in json.loads(fossda.read_text()).values():
        text = " ".join(s["text"] for s in segs)
        if len(text.split()) / max(len(re.findall(r"[.?!]", text)), 1) < 25:  # punctuated
            out.append([{"start": s["start_time"], "end": s["end_time"], "text": s["text"]}
                        for s in segs if s.get("speaker_role") != "researcher"])
    return out


def japanese() -> list[list[dict]]:
    out = []
    for md in sorted(glob.glob("trial-runs/demo-sapporo-guide/bristlenose-output/transcripts-raw/*.md")):
        out.append([{"start": 0, "end": 0, "text": m[1].strip()} for m in
                    re.finditer(r"\*\*\[[\d:]+\] p\d+\*\* \([^)]*\) (.+)", Path(md).read_text())])
    return out


def runs(segs: list[dict], lo: int, hi: int) -> list[tuple[list[str], list[float]]]:
    """Consecutive segments joined into quote-sized runs, with the silence at each join."""
    out, cur, gaps = [], [], []
    for a, b in zip(segs, [*segs[1:], None], strict=True):
        cur.append(a["text"].strip())
        width = bl.text_width(" ".join(cur))
        if width >= lo:
            if width <= hi:
                out.append((cur[:], gaps[:]))
            cur, gaps = [], []
        elif b is not None:
            gaps.append(max(0.0, b["start"] - a["end"]))
    return out


def strip_spaced(text: str) -> tuple[str, dict[int, str]]:
    kinds, words, pos = {}, [], 0
    for tok in text.split():
        core = MARKS.sub("", tok)
        if not core:
            continue
        pos += (1 if words else 0) + len(core)
        words.append(core)
        if re.search(r"[.?!…。！？]", tok[-3:]):
            kinds[pos] = "sentence"
        elif re.search(r"[;:,—–，、；：]", tok[-2:]):
            kinds[pos] = "mark"
    return " ".join(words), kinds


def strip_spaceless(text: str) -> tuple[str, dict[int, str]]:
    out: list[str] = []
    kinds: dict[int, str] = {}
    for ch in text:
        if MARKS.match(ch) or ch.isspace():
            if out and ch in "。！？":
                kinds[len(out)] = "sentence"
            elif out and ch in "、，；：":
                kinds.setdefault(len(out), "mark")
            continue
        out.append(ch)
    return "".join(out), kinds


def score(lang: str, sessions: list[list[dict]], pauses_on: bool,
          why: collections.Counter | None = None) -> tuple[int, float, float]:
    c: collections.Counter[str] = collections.Counter()
    spaceless = lang in ("ja", "zh")
    for segs in sessions:
        for texts, gaps in runs(segs, int(bl.SPLIT_AT * 1.2), int(bl.SPLIT_AT * 2.8)):
            raw = " ".join(texts)
            text, kinds = strip_spaceless(raw) if spaceless else strip_spaced(raw)
            pauses = None
            if pauses_on and not spaceless:
                pauses, at = {}, 0
                for t, g in zip(texts, gaps, strict=False):
                    seg = " ".join(w for w in (MARKS.sub("", x) for x in t.split()) if w)
                    if not seg:  # a segment of marks alone adds no word and no gap
                        continue
                    at += len(seg)
                    pauses[at] = g
                    at += 1
            parts = bl.split_quote(text, pauses=pauses, language=lang)
            at = 0
            for part in parts[:-1]:
                core = part.removeprefix("…").removesuffix("…")
                found = text.find(core, at)
                assert found >= 0, f"a part not found in its quote: {core[:40]!r}"
                at = found + len(core)
                c[kinds.get(at, "none")] += 1
                if why is not None and at not in kinds and not spaceless:
                    left, right = text[:at].split()[-1:], text[at:].split()[:1]
                    why[f"{bl._word(left[0]) if left else ''} | {bl._word(right[0]) if right else ''}"] += 1
    total = sum(c.values()) or 1
    return total, c["sentence"] / total, (c["sentence"] + c["mark"]) / total


def main() -> None:
    args = sys.argv[1:]
    half = args[args.index("--half") + 1] if "--half" in args else None
    why_lang = args[args.index("--why") + 1] if "--why" in args else None
    corpus: dict[str, list[list[dict]]] = {"en": english(), "ja": japanese()}
    stems = sorted({Path(f).name.split(".")[0] for f in glob.glob(f"{TRIALS}/trials/*-[0-9]*.json")})
    for stem in stems:
        lang = re.sub(r"-\d+$", "", stem)
        lang = "pt" if lang.startswith("pt-") else lang  # Whisper says "pt"; one language here
        corpus.setdefault(lang, []).append(trial(stem))
    for arg in args:
        if "=" in arg:
            lang, path = arg.split("=", 1)
            corpus.setdefault(lang, []).append(json.loads(Path(path).read_text())["segments"])
    if half:
        corpus = {lang: sessions[(0 if half == "tune" else 1)::2] for lang, sessions in corpus.items()}
    if why_lang:
        why: collections.Counter[str] = collections.Counter()
        score(why_lang, corpus[why_lang], False, why)
        for pair, n in why.most_common(40):
            print(f"{n:3d}  {pair}")
        return
    print(f"{'lang':6} {'breaks':>6} | no pauses: sentence  any mark | with pauses: sentence  any mark")
    for lang, sessions in corpus.items():
        if not sessions:
            continue
        n, s0, m0 = score(lang, sessions, False)
        _, s1, m1 = score(lang, sessions, True)
        print(f"{lang:6} {n:6d} | {s0:17.0%} {m0:8.0%} | {s1:19.0%} {m1:8.0%}")


if __name__ == "__main__":
    main()
