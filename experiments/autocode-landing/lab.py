"""Build the AutoCode landing lab from a real study and real call timings.

    .venv/bin/python experiments/autocode-landing/lab.py [--db <bristlenose.db>] [-o landing-lab.html]

Reads one study's quotes and the proposals of one AutoCode job (confidence, tag, group colour),
and every logged AutoCode call time found under ``--calls`` (``llm-calls.jsonl`` files,
``stage == "serve_autocode"``, ``elapsed_ms`` only). Writes a self-contained page that replays a
simulated run with the playback queue, pacing controllers and display rules as handles.

Default data: the ``again`` trial run, which is the Talismanic study (all three sessions match
the public Talismanic quotes, checked 23 Nov 2026). Talismanic quotes may appear in tracked
mockups with participants' agreement; codes only, never names, and no file names are read.
Another study carries real participants: write its page to a private folder, never here.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parent.parent
THEME = REPO / "bristlenose" / "theme"
CSS_FILES = [
    "tokens.css",
    "tokens-typography.css",
    "colors/palette-default.css",
    "atoms/badge.css",
    "atoms/shimmer.css",
    "atoms/activity-chip.css",
]
PRIVATE_RUNS = REPO / "trial-runs"  # gitignored
DEFAULT_DB = PRIVATE_RUNS / "again" / "bristlenose-output" / ".bristlenose" / "bristlenose.db"


def read_css() -> str:
    blocks = []
    for rel in CSS_FILES:
        text = (THEME / rel).read_text(encoding="utf-8")
        n = text.count("\n") + 1
        blocks.append(f"/* ════ bristlenose/theme/{rel} — lines 1–{n} ════ */\n{text}")
    return "\n".join(blocks)


def read_study(db_path: Path, framework: str) -> dict:
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    groups = db.execute(
        "select id, name, colour_set from codebook_groups where framework_id=? order by sort_order",
        (framework,),
    ).fetchall()
    tags, tag_by_id = [], {}
    for gid, gname, cset in groups:
        rows = db.execute(
            "select id, name from tag_definitions where codebook_group_id=? order by id", (gid,)
        ).fetchall()
        for idx, (tid, tname) in enumerate(rows):
            tag = {"name": tname, "group": gname, "set": cset, "idx": idx}
            tags.append(tag)
            tag_by_id[tid] = len(tags) - 1
    job = db.execute(
        "select id, total_quotes from autocode_jobs where framework_id=? order by id desc limit 1",
        (framework,),
    ).fetchone()
    quotes = [
        {"id": qid, "s": s, "p": p, "tc": int(tc), "text": text, "topic": topic}
        for qid, s, p, tc, text, topic in db.execute(
            "select id, session_id, participant_id, start_timecode, text, topic_label "
            "from quotes order by id"
        )
    ]
    props = {}
    for qid, tid, conf in db.execute(
        "select quote_id, tag_definition_id, confidence from proposed_tags where job_id=?",
        (job[0],),
    ):
        if tid in tag_by_id:
            props[str(qid)] = {"t": tag_by_id[tid], "c": round(conf, 3)}
    return {
        "framework": framework,
        "groups": [{"name": g[1], "set": g[2]} for g in groups],
        "tags": tags,
        "quotes": quotes,
        "props": props,
    }


def read_calls(root: Path) -> list[int]:
    out: list[int] = []
    for path in root.rglob("llm-calls.jsonl"):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if '"serve_autocode"' not in line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            ms = rec.get("elapsed_ms")
            # A call with no output tokens failed (sub-second refusals): not a call time.
            answered = (rec.get("gen_ai.usage.output_tokens") or 0) > 0
            if rec.get("stage") == "serve_autocode" and answered and isinstance(ms, (int, float)):
                out.append(int(ms))
    return sorted(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--framework", default="uxr")
    ap.add_argument("--calls", type=Path, default=PRIVATE_RUNS)
    ap.add_argument("-o", "--out", type=Path, default=HERE / "landing-lab.html")
    args = ap.parse_args()

    data = read_study(args.db, args.framework)
    data["calls_ms"] = read_calls(args.calls)
    if not data["calls_ms"]:
        data["calls_ms"] = [28000]
    payload = json.dumps(data, ensure_ascii=True).replace("<", "\\u003c")
    page = (HERE / "template.html").read_text(encoding="utf-8")
    page = page.replace("/*__CSS__*/", read_css()).replace("/*__DATA__*/null", payload)
    args.out.write_text(page, encoding="utf-8")
    print(
        f"wrote {args.out}: {len(data['quotes'])} quotes, {len(data['props'])} proposals, "
        f"{len(data['calls_ms'])} call timings"
    )


if __name__ == "__main__":
    main()
