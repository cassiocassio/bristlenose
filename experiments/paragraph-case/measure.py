"""Rule C on real transcripts: which paragraphs would get a capital, and where it goes wrong.

Owner's choice (6 Oct 2026): draw a paragraph's first letter as a capital where a
sentence begins — the first paragraph, a new speaker's turn, or after a
paragraph (same speaker) whose stored text ended a sentence. Display only.

This reads every trial run the way the page does: a copy of the project (no
media) imported by serve in-process, then GET /transcripts/{sid}, so the "drawn"
first word is the word timing's when the paragraph has them, else the text's.
It never writes inside a trial run. Participant text stays out of git: the report
goes to the directory given on the command line.

    .venv/bin/python experiments/paragraph-case/measure.py <scratch-dir> [project ...]
"""

from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bristlenose.server.app import create_app  # noqa: E402
from tests.conftest import AuthTestClient  # noqa: E402

DEFAULT = [
    "Fishkeeping", "IKEA with uxfriends", "Ikea dick", "Ikea tom", "Rockclimbing",
    "demo-escuela-gastronomica", "demo-sapporo-guide", "foo", "foobar",
    "fossda-opensource", "fossda-opensource-test1", "project-ikea", "stress-test-100",
]
MEDIA = ["*.mov", "*.mp4", "*.m4a", "*.wav", "*.mp3", "*.webm", "*.mkv", "*.aac", "*.m4v", "bristlenose.db*"]

# The rule, as frontend/src/utils/sentenceStart.ts has it.
SENTENCE_END = re.compile(r"[.?!…。？！][\"'”’)\]]*\s*$")
# Things that end in a full stop without ending a sentence.
ABBREV = re.compile(r"\b(?:mr|mrs|ms|dr|st|vs|etc|e\.g|i\.e|approx|no|p\.s)\.\s*$", re.I)
DECIMAL_TAIL = re.compile(r"\d\.\s*$")
# A first word whose lowercase start is its spelling, which a capital would break.
INTENTIONAL_LOWER = re.compile(r"^(?:i[A-Z]\w*|e[A-Z]\w*|x[A-Z]\w*|[a-z]+[A-Z]\w*|[a-z0-9]+\.(?:com|org|net|io|app|co)\b)")


def starts_sentence(segs: list[dict], i: int) -> bool:
    if i == 0:
        return True
    prev, here = segs[i - 1], segs[i]
    if prev["speaker_code"] != here["speaker_code"]:
        return True
    return bool(SENTENCE_END.search(prev["text"]))


def first_word(seg: dict) -> str:
    words = seg.get("words") or []
    if words:
        return words[0]["text"].strip()
    parts = seg["text"].split()
    return parts[0] if parts else ""


def first_letter(word: str) -> str:
    m = re.search(r"\w", word)
    return m.group(0) if m else ""


def copy_project(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    cmd = ["rsync", "-a"] + [f"--exclude={p}" for p in MEDIA] + [f"{src}/", f"{dst}/"]
    subprocess.run(cmd, check=True)


def measure(project: str, scratch: Path) -> dict:
    src = ROOT / "trial-runs" / project
    dst = scratch / "copies" / project
    copy_project(src, dst)
    client = AuthTestClient(create_app(project_dir=dst, dev=True, db_url="sqlite://"))
    sessions = client.get("/api/projects/1/sessions").json().get("sessions", [])
    rows = []
    for s in sessions:
        sid = s["session_id"]
        t = client.get(f"/api/projects/1/transcripts/{sid}").json()
        segs = t.get("segments", [])
        lang = t.get("language")
        for i, g in enumerate(segs):
            word = first_word(g)
            letter = first_letter(word)
            start = starts_sentence(segs, i)
            prev = segs[i - 1]["text"] if i else ""
            row = {
                "project": project, "session": sid, "i": i, "lang": lang,
                "code": g["speaker_code"], "drawn_from": "words" if g.get("words") else "text",
                "first": word, "start": start, "text": g["text"][:160],
                "prev_tail": prev[-80:], "speaker_change": i == 0 or segs[i - 1]["speaker_code"] != g["speaker_code"],
            }
            # What the reader would see change.
            if not letter or not letter.isalpha() or letter.upper() == letter.lower():
                row["kind"] = "no case (digit, punctuation or a caseless script)"
            elif start and letter.islower():
                row["kind"] = "CAPITALISED by the rule"
                if INTENTIONAL_LOWER.match(word.lstrip("(\"'¿¡…-–—")):
                    row["risk"] = "intentional lowercase (brand / url)"
            elif start:
                row["kind"] = "already a capital at a sentence start"
            elif letter.islower():
                row["kind"] = "kept lower: carries on mid-sentence"
            else:
                row["kind"] = "capital where the rule sees no sentence start"
            if start and not row["speaker_change"]:
                if ABBREV.search(prev):
                    row["risk"] = "false sentence end (abbreviation)"
                elif DECIMAL_TAIL.search(prev):
                    row["risk"] = "false sentence end (number)"
            if not start and not SENTENCE_END.search(prev) and letter.isupper() and word not in ("I", "I'm", "I've", "I'll", "I'd"):
                row["risk"] = row.get("risk") or "missed start? previous text has no punctuation"
            if word[:1] in "([" and row["kind"] == "CAPITALISED by the rule":
                row["note"] = "starts with a bracket: ::first-letter takes it with the letter"
            rows.append(row)
    return {"project": project, "rows": rows}


def report(results: list[dict], out: Path) -> None:
    allrows = [r for res in results for r in res["rows"]]
    by_proj: dict[str, Counter] = defaultdict(Counter)
    for r in allrows:
        by_proj[r["project"]][r["kind"]] += 1
        by_proj[r["project"]]["total"] += 1
        by_proj[r["project"]]["drawn from words"] += r["drawn_from"] == "words"
        if r.get("risk"):
            by_proj[r["project"]]["risk: " + r["risk"]] += 1
    kinds = sorted({r["kind"] for r in allrows})
    risks = sorted({r["risk"] for r in allrows if r.get("risk")})
    cols = ["total", "drawn from words"] + kinds + ["risk: " + k for k in risks]
    out.mkdir(parents=True, exist_ok=True)
    (out / "rows.json").write_text(json.dumps(allrows, ensure_ascii=False, indent=1), encoding="utf-8")
    e = html.escape
    parts = ["<!doctype html><meta charset=utf-8><title>Paragraph case — rule C on real transcripts</title>",
             "<style>body{font:14px/1.45 -apple-system,sans-serif;margin:24px;max-width:1300px}"
             "table{border-collapse:collapse;font-size:12px}td,th{border:1px solid #ccc;padding:3px 6px;text-align:right}"
             "th{background:#f4f4f4}td:first-child{text-align:left}.ex{font-family:ui-monospace,monospace;font-size:12px}"
             ".cap{background:#fff3b0}.prev{color:#888}h3{margin-top:28px}</style>",
             "<h1>Rule C on real transcripts</h1><p>Private: participant text. Not for git.</p><table><tr><th>project</th>"]
    parts += [f"<th>{e(c)}</th>" for c in cols] + ["</tr>"]
    tot: Counter = Counter()
    for p, c in by_proj.items():
        parts.append(f"<tr><td>{e(p)}</td>" + "".join(f"<td>{c.get(k, 0)}</td>" for k in cols) + "</tr>")
        tot.update(c)
    parts.append("<tr><th>all</th>" + "".join(f"<th>{tot.get(k, 0)}</th>" for k in cols) + "</tr></table>")
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in allrows:
        groups["kind: " + r["kind"]].append(r)
        if r.get("risk"):
            groups["risk: " + r["risk"]].append(r)
    for g, rs in sorted(groups.items()):
        parts.append(f"<h3>{e(g)} — {len(rs)}</h3><ol>")
        step = max(1, len(rs) // 25)
        for r in rs[::step][:25]:
            first = r["first"]
            parts.append(f"<li class=ex>{e(r['project'])} {e(r['session'])}#{r['i']} [{e(r['code'])}] "
                         f"<span class=prev>…{e(r['prev_tail'])}</span> ⏎ <span class=cap>{e(first)}</span> "
                         f"{e(r['text'][len(first):100])} <i>({r['drawn_from']}{', ' + e(r['lang']) if r['lang'] else ''})</i></li>")
        parts.append("</ol>")
    (out / "report.html").write_text("".join(parts), encoding="utf-8")


def main() -> None:
    scratch = Path(sys.argv[1])
    projects = sys.argv[2:] or DEFAULT
    results = []
    for p in projects:
        try:
            results.append(measure(p, scratch))
            print(f"{p}: {len(results[-1]['rows'])} paragraphs", flush=True)
        except Exception as exc:  # one broken project should not sink the survey
            print(f"{p}: FAILED {type(exc).__name__}: {exc}", flush=True)
    report(results, scratch / "report")
    print(scratch / "report" / "report.html")


if __name__ == "__main__":
    main()
