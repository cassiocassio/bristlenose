"""Read stored signal-elaboration assertions (read-only) and measure highlight coverage.

    .venv/bin/python experiments/signal-highlight-lab/extract.py [--db PATH ...]

Writes data/assertions.json (gitignored: participant words) and prints the
baseline distribution. No LLM call. Databases are opened mode=ro.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
from pathlib import Path

HERE = Path(__file__).parent
HOME = Path.home()
DEFAULT_DBS = {
    "ikea": "trial-runs/project-ikea/bristlenose-output/.bristlenose/bristlenose.db",
    "talismanic": str(HOME / "Documents/Talismanic/bristlenose-output/.bristlenose/bristlenose.db"),
    "ikea-videos": str(HOME / "Documents/ikea research videos/bristlenose-output/.bristlenose/bristlenose.db"),
    "talismanic-ur": str(HOME / "Documents/User research/Talismanic/bristlenose-output/.bristlenose/bristlenose.db"),
}


def words(s: str) -> int:
    return len(s.split())


def load(label: str, path: str) -> list[dict]:
    root = Path(__file__).resolve().parents[2]
    p = Path(path) if Path(path).is_absolute() else root / path
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    rows = con.execute(
        "select signal_key, signal_name, pattern, evidence_assertions, elaboration from elaboration_caches"
    ).fetchall()
    # quote texts from the latest snapshot give us the full quote for each id
    quotes: dict[str, str] = {}
    try:
        for (payload,) in con.execute("select payload from signal_snapshots order by id"):
            d = json.loads(payload)
            for cb in d.get("codebooks", []):
                for sig in cb.get("signals", []):
                    for q in sig.get("quotes", []):
                        quotes[q["quote_id"]] = q["text"]
    except sqlite3.Error:
        pass
    # the Signals page reads the snapshot, so its assertions are the ones the owner sees
    snap_rows = []
    try:
        for (payload,) in con.execute("select payload from signal_snapshots order by id"):
            for cb in json.loads(payload).get("codebooks", []):
                for sig in cb.get("signals", []):
                    snap_rows.append((
                        f"{sig.get('source_type')}|{sig.get('location')}|{sig.get('group_name')}",
                        sig.get("signal_name", ""), sig.get("pattern", ""),
                        json.dumps(sig.get("evidence_assertions", [])),
                        sig.get("elaboration", ""),
                    ))
    except sqlite3.Error:
        pass
    out = []
    for src, key, name, pattern, ev, elab in [("cache", *r) for r in rows] + [("snapshot", *r) for r in snap_rows]:
        for a in json.loads(ev or "[]"):
            frag = a.get("intervention_fragment")
            out.append({
                "project": label, "from": src, "card": key, "claim": elab.split("||")[0].strip(), "card_name": name, "pattern": pattern,
                "id": a["id"], "text": a["text"], "quote_id": a["source_quote_id"],
                "quote": quotes.get(a["source_quote_id"]) or a.get("source_excerpt", ""),
                "fragment": frag,
            })
    return out


def share(a: dict) -> tuple[float, float] | None:
    f = a["fragment"]
    if not f:
        return None
    return words(f["text"]) / words(a["text"]), len(f["text"]) / len(a["text"])


def pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))]


def report(rows: list[dict]) -> dict:
    withf = [(a, share(a)) for a in rows if a["fragment"]]
    ws = [s[0] for _, s in withf]
    cs = [s[1] for _, s in withf]
    return {
        "assertions": len(rows), "with_highlight": len(withf),
        "words_median": statistics.median(ws), "words_p90": pct(ws, .9), "words_max": max(ws),
        "chars_median": statistics.median(cs), "chars_p90": pct(cs, .9), "chars_max": max(cs),
        "over_50_words": sum(w > .5 for w in ws), "over_50_chars": sum(c > .5 for c in cs),
        "frag_words_median": statistics.median(words(a["fragment"]["text"]) for a, _ in withf),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", action="append", help="label=path")
    args = ap.parse_args()
    dbs = dict(x.split("=", 1) for x in args.db) if args.db else DEFAULT_DBS
    allrows: list[dict] = []
    for label, path in dbs.items():
        try:
            allrows += load(label, path)
        except (sqlite3.Error, OSError) as e:
            print(f"skip {label}: {e}")
    # Several snapshots (and the cache) hold successive wordings of the same bullet. `load`
    # yields snapshots in id order and the cache last, so the LAST yielded is not the newest:
    # keep, per (project, card, quote), the latest snapshot's version.
    latest: dict[tuple, dict] = {}
    for a in allrows:
        if a["from"] == "snapshot" or (a["project"], a["card"], a["quote_id"]) not in latest:
            latest[(a["project"], a["card"], a["quote_id"])] = a
    # Different project copies of one study share quotes; count each bullet once.
    seen, rows = set(), []
    for a in latest.values():
        k = (a["quote_id"], a["text"])
        if k not in seen:
            seen.add(k)
            rows.append(a)
    (HERE / "data").mkdir(exist_ok=True)
    (HERE / "data/assertions.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    for label in dict.fromkeys(a["project"] for a in rows):
        print(label, len([a for a in rows if a["project"] == label]))
    r = report(rows)
    print(json.dumps(r, indent=1))
    print("\nworst ten by word share:")
    worst = sorted((a for a in rows if a["fragment"]), key=lambda a: -share(a)[0])[:10]
    for a in worst:
        w, c = share(a)
        t, f = a["text"], a["fragment"]["text"]
        print(f"{w:.0%} words {c:.0%} chars | {t.replace(f, '[[' + f + ']]')}")
