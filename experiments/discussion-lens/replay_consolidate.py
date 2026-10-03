#!/usr/bin/env python3
"""Replay ONLY the consolidate step on saved runs' labels, N times each.

Classification is per-session and was stable across runs; the variance in
emergent-topic granularity comes from consolidation. Replaying that one call on
fixed labels isolates it, at about a cent a call, instead of paying for full runs.

    .venv/bin/python experiments/discussion-lens/replay_consolidate.py \
        experiments/discussion-lens/runs/synthetic/run-*.json --repeats 3
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spike import consolidate, load_transcripts  # noqa: E402
from structure import Item, Label, Section, build_structure  # noqa: E402

from bristlenose.config import load_settings  # noqa: E402
from bristlenose.llm.client import LLMClient  # noqa: E402
from bristlenose.llm.pricing import estimate_cost  # noqa: E402

HERE = Path(__file__).resolve().parent


async def main_async(a: argparse.Namespace) -> None:
    gold = json.loads((HERE / "synthetic" / "gold.json").read_text(encoding="utf-8"))
    budget = {t for t, g in gold["turns"].items() if g.get("section") == "new:budget"}
    _, askable, lengths, _ = load_transcripts(HERE / "synthetic" / "transcripts")
    turns = {t.id: t for ts in askable.values() for t in ts}
    client = LLMClient(load_settings())
    ok = total = 0
    for path in a.runs:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        spine = [Section(s["id"], s["title"], s["kind"], "planned", s["title"],
                         [Item(i["id"], i["terse"], i["text"]) for i in s["items"]]) for s in d["spine"]]
        for r in range(a.repeats):
            labels = [Label(**lb) for lb in d["_labels"]]
            cons, topics = await consolidate(client, labels, turns, spine)
            sections, standalone, _ = build_structure(spine, labels, cons, topics, turns, lengths)
            home = {t: s.title for s in sections for it in s.items for t in it.turns}
            homes = [home.get(t, "standalone") for t in sorted(budget)]
            emergent = [s.title for s in sections if s.origin == "emergent"]
            whole = len(set(homes)) == 1 and homes[0] in emergent
            ok += whole
            total += 1
            print(f"{Path(path).stem} #{r + 1}: emergent {emergent} · budget turns → "
                  f"{sorted(set(homes))} {'✓ one section' if whole else '✗'}")
    tr = client.tracker
    usd = estimate_cost(client.settings.llm_model, tr.input_tokens, tr.output_tokens)
    print(f"\nbudget as exactly one promoted section: {ok}/{total} · {tr.calls} calls · ${usd:.4f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--repeats", type=int, default=3)
    asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    main()
