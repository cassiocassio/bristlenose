"""Word error rate of trial transcripts against a corpus's reference transcript.

For the Ameresco Spanish conversations, whose reference transcripts are
conversation-analysis markup: overlaps in [ ], uncertain words in (( )),
<ininteligible/>, <risas/>, pauses as / and (5.8), latching §, and
<fsr t="pronounced">standard</fsr>. The standard form is kept, everything else
is stripped. Overlapping speech stays in the reference, so the score counts
what is lost when people talk over each other.

Caveat for absolute numbers: the reference spells numbers out ("noventa") and
Whisper writes digits ("90"), so every condition pays the same small penalty.
Compare conditions with each other, not with published WERs.

    .venv/bin/python experiments/transcript-readability/score_wer.py ROOT
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np

REFERENCES = {"es-5": "LPA_002_04_18", "es-6": "BUE_24_05_21"}


def _words(text: str) -> list[str]:
    text = unicodedata.normalize("NFC", text.lower())
    text = re.sub(r"[^\w\s']", " ", text)
    return [w for w in text.split() if not w.isdigit() or len(w) < 6]


def reference_words(path: Path) -> list[str]:
    out: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t", 2)
        if len(parts) < 3:
            continue
        utt = re.sub(r"^[^:]{1,40}:\s*", "", parts[2])           # speaker label
        utt = re.sub(r'<fsr t="[^"]*">(.*?)</fsr>', r"\1", utt)    # keep standard form
        utt = re.sub(r'<extranjero t="[^"]*">(.*?)</extranjero>', r"\1", utt)
        utt = re.sub(r"<cita>(.*?)</cita>", r"\1", utt)
        utt = re.sub(r"<[^>]+/>", " ", utt)                       # <risas/>, <ininteligible/>
        utt = re.sub(r"<[^>]+>", " ", utt)
        utt = re.sub(r"\(\d+(\.\d+)?\)", " ", utt)                # (5.8) pauses
        utt = utt.replace("((", " ").replace("))", " ").replace("§", " ")
        out.extend(_words(utt))
    return out


def wer(ref: list[str], hyp: list[str]) -> tuple[float, int]:
    """Word error rate and edit distance (substitutions + deletions + insertions)."""
    vocab: dict[str, int] = {}
    r = np.array([vocab.setdefault(w, len(vocab)) for w in ref])
    h = np.array([vocab.setdefault(w, len(vocab)) for w in hyp])
    idx = np.arange(len(h) + 1)
    prev = idx.copy()
    for i in range(1, len(r) + 1):
        cost = (h != r[i - 1]).astype(np.int64)
        cur = np.empty_like(prev)
        cur[0] = i
        cur[1:] = np.minimum(prev[1:] + 1, prev[:-1] + cost)
        cur = np.minimum.accumulate(cur - idx) + idx           # insertions, left to right
        prev = cur
    return float(prev[-1]) / max(1, len(r)), int(prev[-1])


def main(root: str) -> int:
    base = Path(root)
    results = {}
    for sid, ref_name in REFERENCES.items():
        ref = reference_words(base / "es" / "reference" / f"{ref_name}.txt")
        for path in sorted((base / "trials").glob(f"{sid}.*.json")):
            cond = path.name[len(sid) + 1:-len(".json")]
            hyp = _words(" ".join(s["text"] for s in json.loads(path.read_text())["segments"]))
            score, edits = wer(ref, hyp)
            results[f"{sid}.{cond}"] = {"wer": round(score, 3), "ref_words": len(ref),
                                        "hyp_words": len(hyp), "edits": edits}
            print(f"{sid} {cond:16} WER {score:6.1%}  reference {len(ref)} words, transcript {len(hyp)}")
    (base / "trials" / "wer.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
