"""Score how well an extraction run keeps quotes together.

Two kinds of measure:

* **Fragmentation** (any study): quote count, median and p90 length, coverage of
  participant words, and *touching pairs* — two quotes from the same speaker whose
  source passages sit side by side in the transcript, separated by at most GAP
  participant words and no researcher words. A touching pair on the same topic is
  one passage cut in two.
* **Task cohesion** (studies with a ``tasks.json``, such as the synthetic fixture):
  quotes per task, quotes that span two tasks, tasks with no quote, and a verdict.

Usage::

    python score.py fixture results/current-openai-1.json results/v3-openai-1.json

The first argument is a study folder holding ``transcripts/<session>.txt`` and,
optionally, ``tasks.json``. No LLM calls, no network.
"""

from __future__ import annotations

import json
import re
import statistics
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

GAP = 4  # participant words ("Okay, um") that may sit between two halves of one passage
_LINE_RE = re.compile(r"^\[[\d:]+\]\s+\[(\w+)\]\s*(.*)$")


def norm(word: str) -> str:
    word = unicodedata.normalize("NFKD", word.lower()).replace("’", "'")
    return re.sub(r"[^\w]", "", word)


def transcript_words(path: Path) -> list[tuple[str, str]]:
    """Every word of a transcript ``.txt`` as (normalised form, speaker code)."""
    out: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _LINE_RE.match(line)
        if not m:
            continue
        for w in m.group(2).split():
            f = norm(w)
            if f:
                out.append((f, m.group(1)))
    return out


def locate(forms: list[str], want: list[str]) -> tuple[int, int] | None:
    """Word span of a quote's ``verbatim_excerpt`` in the transcript.

    Exact match first; failing that, the first four and last four words, which
    survives the model's own small slips inside a long excerpt.
    """
    n = len(want)
    if not n:
        return None
    for k in range(len(forms) - n + 1):
        if forms[k : k + n] == want:
            return (k, k + n - 1)
    anchor = 4
    if n <= anchor:
        return None
    head, tail = want[:anchor], want[-anchor:]
    for a in range(len(forms) - anchor + 1):
        if forms[a : a + anchor] != head:
            continue
        for b in range(a + n // 2 - anchor, min(len(forms) - anchor, a + 2 * n) + 1):
            if b >= a and forms[b : b + anchor] == tail:
                return (a, b + anchor - 1)
    return None


def is_researcher(code: str) -> bool:
    return code.startswith("m")


@dataclass
class Fragmentation:
    quotes: int
    median_words: float
    p90_words: int
    max_words: int
    located: int
    touching: int
    same_topic_touching: int
    coverage: float


def fragmentation(transcripts: Path, quotes: list[dict]) -> Fragmentation:
    lens = sorted(len(q["text"].split()) for q in quotes) or [0]
    located = touching = same = covered = participant_words = 0
    for sid in sorted({q["session_id"] for q in quotes}):
        words = transcript_words(transcripts / f"{sid}.txt")
        forms = [f for f, _ in words]
        spans = []
        for q in quotes:
            if q["session_id"] != sid:
                continue
            want = [norm(w) for w in q["verbatim_excerpt"].split() if norm(w)]
            span = locate(forms, want)
            if span:
                spans.append((span, q.get("participant_id"), q.get("topic_label")))
                located += 1
        spans.sort()
        cov: set[int] = set()
        for (a, b), _, _ in spans:
            cov.update(range(a, b + 1))
        covered += sum(1 for i in cov if not is_researcher(words[i][1]))
        participant_words += sum(1 for _, s in words if not is_researcher(s))
        for (a, pa, ta), (b, pb, tb) in zip(spans, spans[1:]):
            if pa != pb or b[0] <= a[1]:
                continue
            gap = [s for _, s in words[a[1] + 1 : b[0]]]
            if len(gap) <= GAP and not any(is_researcher(s) for s in gap):
                touching += 1
                same += ta == tb
    return Fragmentation(
        quotes=len(quotes),
        median_words=statistics.median(lens),
        p90_words=lens[int(0.9 * (len(lens) - 1))],
        max_words=lens[-1],
        located=located,
        touching=touching,
        same_topic_touching=same,
        coverage=round(covered / max(1, participant_words), 2),
    )


@dataclass
class Cohesion:
    per_task: list[int]
    crossing: int
    unquoted_tasks: list[str] = field(default_factory=list)
    passed: bool = False


def cohesion(tasks: dict, quotes: list[dict]) -> Cohesion:
    """Quotes per task, by time. A quote counts for every task its span overlaps
    by more than a second; overlapping two or more is a crossing."""
    spans = tasks["tasks"]
    per = [0] * len(spans)
    crossing = 0
    for q in quotes:
        if q["session_id"] != tasks["session_id"]:
            continue
        hit = [
            i
            for i, t in enumerate(spans)
            if q["start_timecode"] < t["end"] and q["end_timecode"] > t["start"] + 1
        ]
        if len(hit) > 1:
            crossing += 1
        if hit:
            per[hit[0]] += 1
    unquoted = [t["label"] for t, n in zip(spans, per) if n == 0]
    cap = tasks["max_quotes_per_task"]
    passed = crossing == 0 and not unquoted and all(n <= cap for n in per)
    return Cohesion(per_task=per, crossing=crossing, unquoted_tasks=unquoted, passed=passed)


def load_quotes(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else data["quotes"]


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    study = Path(argv[0])
    tasks_path = study / "tasks.json"
    tasks = json.loads(tasks_path.read_text(encoding="utf-8")) if tasks_path.exists() else None
    for name in argv[1:]:
        quotes = load_quotes(Path(name))
        f = fragmentation(study / "transcripts", quotes)
        line = (
            f"{Path(name).name:28} quotes {f.quotes:3}  median {f.median_words:5.1f}  "
            f"p90 {f.p90_words:3}  max {f.max_words:3}  same-topic touching "
            f"{f.same_topic_touching:2}  coverage {f.coverage:.2f}  located {f.located}/{f.quotes}"
        )
        if tasks:
            c = cohesion(tasks, quotes)
            line += f"  per task {c.per_task}  crossing {c.crossing}  {'PASS' if c.passed else 'FAIL'}"
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
