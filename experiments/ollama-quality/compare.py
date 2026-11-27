"""Compare three analyze runs of the same transcripts: counts, verbatim rate, calls, timings."""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(sys.argv[1])
RUNS = sys.argv[2:] or ["claude", "gemma", "llama"]


def norm(s: str) -> str:
    s = s.lower().replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # Fillers the prompt allows the model to drop, removed from both sides.
    s = re.sub(r"\b(um+|uh+|er+|erm|hmm+|like|you know|i mean|kind of|sort of|so|well|yeah|okay|ok|just|actually|basically|right)\b", " ", s)
    s = re.sub(r"\b(\w+)( \1\b)+", r"\1", s)  # stutters: "it's it's"
    return re.sub(r"\s+", " ", s).strip()


def transcript_text(run: str) -> dict[str, str]:
    out = {}
    for f in sorted((ROOT / run / "transcripts-raw").glob("s*.txt")):
        body = []
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.startswith("#"):
                continue
            line = re.sub(r"^\[\d\d:\d\d(:\d\d)?\]\s*\[\w+\]\s*(\(Speaker \w+\)\s*)?", "", line)
            body.append(line)
        out[f.stem] = norm(" ".join(body))
    return out


def fragments(excerpt: str) -> list[str]:
    # The prompt lets the model cut filler to "..." and add "[clarifying words]":
    # drop bracketed insertions, split on ellipses, check each fragment.
    s = re.sub(r"\[[^\]]*\]", " ", excerpt)
    parts = re.split(r"\.\.\.|…|\n\s*\n", s)
    return [norm(p) for p in parts if norm(p)]


def verbatim(excerpt: str, text: str) -> str:
    frags = fragments(excerpt)
    if not frags:
        return "empty"
    if all(f in text for f in frags):
        return "exact"
    grams = []
    for f in frags:
        w = f.split()
        if len(w) < 5:
            grams.append((" ".join(w), " ".join(w) in text))
        else:
            grams += [(g, g in text) for g in (" ".join(w[i:i + 5]) for i in range(len(w) - 4))]
    share = sum(ok for _, ok in grams) / len(grams)
    return "joined" if share >= 0.9 else ("altered" if share >= 0.5 else "invented")


for run in RUNS:
    inter = ROOT / run / ".bristlenose" / "intermediate"
    print(f"\n===== {run}")
    texts = transcript_text(run)
    try:
        quotes = json.loads((inter / "extracted_quotes.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        print("no extracted_quotes.json")
        continue
    per_session = Counter(q["session_id"] for q in quotes)
    per_pid = Counter(q["participant_id"] for q in quotes)
    vb = Counter()
    bad = []
    words = []
    for q in quotes:
        v = verbatim(q.get("verbatim_excerpt") or q["text"], texts.get(q["session_id"], ""))
        vb[v] += 1
        words.append(len((q.get("verbatim_excerpt") or q["text"]).split()))
        if v in ("altered", "invented"):
            bad.append((v, q["session_id"], q["participant_id"], (q.get("verbatim_excerpt") or "")[:160]))
    words.sort()
    print("quotes", len(quotes), dict(per_session), "by speaker", dict(per_pid))
    print("verbatim", dict(vb), "median words", words[len(words) // 2] if words else None)
    print("quote types", dict(Counter(q.get("quote_type") for q in quotes)))
    distinct = len({norm(q["text"])[:120] for q in quotes})
    with_sent = sum(1 for q in quotes if q.get("sentiment"))
    print("distinct quotes", distinct, "with sentiment", with_sent)
    for b in bad[:6]:
        print("  ", b)
    for name in ("theme_groups.json", "screen_clusters.json"):
        p = inter / name
        if p.exists():
            groups = json.loads(p.read_text(encoding="utf-8"))
            label = "theme_label" if "theme" in name else "screen_label"
            print(name, len(groups))
            for g in groups:
                print("   -", g.get(label) or g.get("label"), f"({len(g.get('quotes', []))})")
    calls = [json.loads(line) for line in (ROOT / run / ".bristlenose" / "llm-calls.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    by_stage = defaultdict(lambda: [0, 0, 0, 0, 0, 0])  # calls, retries, ms, in, out, not-ok
    for c in calls:
        s = by_stage[c["stage"]]
        s[0] += 1
        s[1] += c.get("retry_count") or 0
        s[2] += c.get("elapsed_ms") or 0
        s[3] += c.get("gen_ai.usage.input_tokens") or 0
        s[4] += c.get("gen_ai.usage.output_tokens") or 0
        s[5] += c.get("outcome") != "ok"
    tot = [sum(v[i] for v in by_stage.values()) for i in range(6)]
    print("calls by stage: calls retries secs in_tok out_tok not_ok")
    for k, v in by_stage.items():
        print(f"   {k:28} {v[0]:3} {v[1]:3} {v[2]/1000:7.1f} {v[3]:7} {v[4]:6} {v[5]}")
    print(f"   {'TOTAL':28} {tot[0]:3} {tot[1]:3} {tot[2]/1000:7.1f} {tot[3]:7} {tot[4]:6} {tot[5]}")
    print("max input tokens in one call", max((c.get("gen_ai.usage.input_tokens") or 0) for c in calls))
    print("outcomes", dict(Counter(c.get("outcome") for c in calls)), "finish", dict(Counter(c.get("finish_reason") for c in calls)))
