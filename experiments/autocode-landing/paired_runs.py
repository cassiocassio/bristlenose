"""Phase 0b and 0c of docs/design-autocode-landing-plan.md: two small paid tests (owner-approved
23 Nov 2026, well under £1), through AutoCode's own prompt, taxonomy and client.

    .venv/bin/python experiments/autocode-landing/paired_runs.py [--db <bristlenose.db>] -o <results.json>

0b  Batch size against time to answer: batches of 5, 10 and 25 quotes, two calls each, one at a
    time, timed end to end.
0c  Does the order of quotes in a batch change the answers? 50 quotes (a block from session 1 and
    a block from session 3) coded in stored order, in stored order again (the model's own
    run-to-run noise), and shuffled across the two sessions; compared quote by quote.

Stops before a call that would take the running cost past --cap (USD), priced by
bristlenose.llm.pricing. Writes quote ids, tags, confidences and timings: no quote text.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sqlite3
import statistics
import time
from pathlib import Path

from bristlenose.config import load_settings
from bristlenose.llm.boundary import wrap_untrusted
from bristlenose.llm.client import LLMClient
from bristlenose.llm.pricing import estimate_cost
from bristlenose.llm.prompts import get_prompt_template
from bristlenose.llm.structured import AutoCodeBatchResult
from bristlenose.server.autocode import QuoteBatchItem, build_quote_batch, build_tag_taxonomy
from bristlenose.server.codebook import get_template

REPO = Path(__file__).resolve().parents[2]
PRIVATE_RUNS = REPO / "trial-runs"  # gitignored
DEFAULT_DB = PRIVATE_RUNS / "again" / "bristlenose-output" / ".bristlenose" / "bristlenose.db"


def load_quotes(db_path: Path) -> list[QuoteBatchItem]:
    db = sqlite3.connect("file:" + str(db_path) + "?mode=ro", uri=True)
    rows = db.execute(
        "select id, text, session_id, participant_id, topic_label, coalesce(sentiment, '') "
        "from quotes order by id"
    ).fetchall()
    return [QuoteBatchItem(db_id=r[0], text=r[1], session_id=r[2], participant_id=r[3],
                           topic_label=r[4] or "", sentiment=r[5]) for r in rows]


class Runner:
    def __init__(self, cap: float) -> None:
        self.settings = load_settings()
        self.client = LLMClient(self.settings)
        self.template = get_template("uxr")
        self.taxonomy = build_tag_taxonomy(self.template)
        self.prompt = get_prompt_template("autocode")
        self.model = self.settings.llm_model
        self.cap = cap
        self.spent = 0.0
        self.last_cost = 0.0

    async def call(self, batch: list[QuoteBatchItem]) -> dict:
        if self.spent + max(self.last_cost, 0.06) > self.cap:
            raise SystemExit("stopping: the next call could pass the cap of $" + str(self.cap))
        user = self.prompt.user.format(
            codebook_title=self.template.title,
            codebook_preamble=self.template.preamble,
            formatted_tag_taxonomy=self.taxonomy,
            formatted_quotes=wrap_untrusted("quotes", build_quote_batch(batch)),
        )
        tr = self.client.tracker
        in0, out0 = tr.input_tokens, tr.output_tokens
        t0 = time.perf_counter()
        result = await self.client.analyze(
            system_prompt=self.prompt.system, user_prompt=user,
            response_model=AutoCodeBatchResult, prompt_template=self.prompt,
        )
        secs = time.perf_counter() - t0
        tin, tout = tr.input_tokens - in0, tr.output_tokens - out0
        cost = estimate_cost(self.model, tin, tout) or 0.0
        self.spent += cost
        self.last_cost = cost
        answers = {}
        for a in result.assignments:
            if 0 <= a.quote_index < len(batch):
                answers[batch[a.quote_index].db_id] = [a.tag_name, a.confidence]
        print(f"  {len(batch):>2} quotes  {secs:5.1f} s  in {tin:>6}  out {tout:>5}  ${cost:.3f}  "
              f"(total ${self.spent:.3f})", flush=True)
        return {"n": len(batch), "secs": secs, "in": tin, "out": tout, "cost": cost, "answers": answers}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--cap", type=float, default=1.10)
    args = ap.parse_args()

    quotes = load_quotes(args.db)
    r = Runner(args.cap)
    print("model", r.model, "| quotes", len(quotes), "| cap $" + str(args.cap), flush=True)
    results: dict = {"model": r.model, "b": [], "c": {}}

    print("0b: batch size against time", flush=True)
    for rep, start in enumerate((30, 60)):
        for n in (5, 10, 25):
            res = await r.call(quotes[start:start + n])
            results["b"].append({"rep": rep, **{k: v for k, v in res.items() if k != "answers"}})

    print("0c: stored order, stored again, shuffled", flush=True)
    s1 = [q for q in quotes if q.session_id == "s1"][:25]
    s3 = [q for q in quotes if q.session_id == "s3"][:25]
    pool = s1 + s3
    shuffled = pool[:]
    random.Random(7).shuffle(shuffled)
    plans = {"stored": [s1, s3], "stored_again": [s1, s3], "shuffled": [shuffled[:25], shuffled[25:]]}
    for name, batches in plans.items():
        merged: dict = {}
        for b in batches:
            merged.update((await r.call(b))["answers"])
        results["c"][name] = {str(k): v for k, v in merged.items()}

    def compare(a: str, b: str) -> dict:
        x, y = results["c"][a], results["c"][b]
        both = [k for k in x if k in y]
        same_tag = sum(x[k][0] == y[k][0] for k in both)
        deltas = [abs(x[k][1] - y[k][1]) for k in both if x[k][0] == y[k][0]]
        return {"quotes": len(both), "same_tag": same_tag,
                "mean_abs_conf_change_same_tag": round(statistics.mean(deltas), 3) if deltas else None,
                "max_abs_conf_change_same_tag": round(max(deltas), 3) if deltas else None}

    results["c_compare"] = {
        "stored vs stored_again (noise)": compare("stored", "stored_again"),
        "stored vs shuffled": compare("stored", "shuffled"),
        "stored_again vs shuffled": compare("stored_again", "shuffled"),
    }
    results["spent_usd"] = round(r.spent, 3)
    args.out.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(json.dumps(results["c_compare"], indent=1))
    by = {}
    for row in results["b"]:
        by.setdefault(row["n"], []).append(row["secs"])
    print("0b mean seconds:", {n: round(statistics.mean(v), 1) for n, v in by.items()})
    print("spent $" + str(results["spent_usd"]))


if __name__ == "__main__":
    asyncio.run(main())
