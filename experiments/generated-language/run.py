#!/usr/bin/env python3
"""Run the generated-language cells and write one JSON per pass.

    ./run.py --plan                            # cost estimate, makes no calls
    ./run.py --yes                             # everything
    ./run.py --yes --corpus ikea-es --provider anthropic --condition steered

A cell is (corpus, provider, condition, stage, pass). Output lands at
`out/<corpus>/<provider>/<condition>/<stage>_pass<n>.json` and a pass already
on disk is never re-run — passes are paid for, and the 3 Jul 2026 double-spend
came from re-running a step whose guard had quietly failed.

HOW THE STEER IS APPLIED, AND WHY NOT BY EDITING THE PROMPT

The shipped `.md` files carry a `sha` that telemetry and cohort baselines key
on, so editing one to try a sentence churns `cohort-baselines.json` for an
experiment. Instead the harness builds a variant `PromptTemplate` with the
steer appended to `system` and rebinds the name **in the stage module** —
`s11_thematic_grouping.get_prompt_template`, not the loader's own attribute,
because the stage did `from … import get_prompt_template` at module load and
holds its own reference. Patching the loader would change nothing and every
steered cell would silently be a second unsteered one.

The variant's `id` is suffixed (`thematic-grouping+steer`) rather than left
alone: no telemetry row can land here (`record_call` needs a bound run context
and this harness binds none), but a row that did must not claim to be the
shipped prompt.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import corpora as corpus_lib  # noqa: E402

from bristlenose.config import load_settings  # noqa: E402
from bristlenose.llm.client import LLMClient  # noqa: E402
from bristlenose.llm.prompts import get_prompt_template  # noqa: E402
from bristlenose.providers import PROVIDERS  # noqa: E402
from bristlenose.stages import (  # noqa: E402
    s08_topic_segmentation,
    s10_quote_clustering,
    s11_thematic_grouping,
)

OUT = HERE / "out"

#: The steer. One sentence appended to the shipped system prompt. The last
#: clause is the V1 decision's known cost made explicit — it tells the model
#: that an on-screen label may stay as the participant said it, which is the
#: thing `ikea-mixed` exists to test. Change this and you are measuring a
#: different experiment: record it as a new condition, never edit in place.
STEER = (
    "\n\nWrite every generated label, name, title, subtitle and description in "
    "Spanish (es). Do not translate or alter the quotes themselves. Keep product "
    "names, brand names and on-screen UI labels as the participants said them."
)

CONDITIONS = ("unsteered", "steered")

#: stage id → (module, prompt name, what it needs)
STAGES = {
    "s10": (s10_quote_clustering, "quote-clustering", "quotes"),
    "s11": (s11_thematic_grouping, "thematic-grouping", "quotes"),
    "s08": (s08_topic_segmentation, "topic-segmentation", "transcripts"),
}

#: Which stages each corpus can fill. `escuela` has no screen_specific quotes,
#: so s10 would return an empty list without making a call — an empty cell that
#: looks like a measurement. The ikea transcripts are English, so s08 there
#: would measure translation of a corpus we never translated.
CORPUS_STAGES = {
    "escuela": ("s11", "s08"),
    "ikea-es": ("s10", "s11"),
    "ikea-mixed": ("s10", "s11"),
}


def _steered(name: str):
    """A variant of the shipped template with the steer appended."""
    tmpl = get_prompt_template(name)
    return dataclasses.replace(tmpl, id=f"{tmpl.id}+steer", system=tmpl.system + STEER)


class patched_prompt:
    """Rebind a stage module's `get_prompt_template` for the duration of a call."""

    def __init__(self, module, name: str, condition: str) -> None:
        self.module, self.name, self.condition = module, name, condition

    def __enter__(self):
        if self.condition == "unsteered":
            return self
        variant = _steered(self.name)
        self.original = self.module.get_prompt_template
        self.module.get_prompt_template = lambda n: variant if n == self.name else self.original(n)
        return self

    def __exit__(self, *exc) -> None:
        if self.condition != "unsteered":
            self.module.get_prompt_template = self.original


async def run_cell(corpus: str, stage: str, provider: str, model: str,
                   condition: str) -> dict:
    module, prompt_name, needs = STAGES[stage]
    client = LLMClient(load_settings(llm_provider=provider, llm_model=model))

    with patched_prompt(module, prompt_name, condition):
        if needs == "transcripts":
            transcripts, _ = corpus_lib.load_transcripts(corpus_lib.ESCUELA)
            maps, outcome = await module.segment_topics(
                transcripts=transcripts, llm_client=client, concurrency=1,
            )
            payload = [m.model_dump(mode="json") for m in maps]
        else:
            quotes = corpus_lib.load(corpus)
            fn = module.cluster_by_screen if stage == "s10" else module.group_by_theme
            groups, outcome = await fn(quotes, client)
            payload = [g.model_dump(mode="json") for g in groups]

    return {
        "corpus": corpus, "stage": stage, "provider": provider,
        "model": model, "condition": condition,
        "attempted": outcome.attempted, "succeeded": outcome.succeeded,
        "failed": [f.model_dump(mode="json") for f in outcome.failed],
        "result": payload,
    }


def cells(corpora: list[str], providers: list[str], conditions: list[str],
          passes: int) -> list[tuple]:
    out = []
    for c in corpora:
        for stage in CORPUS_STAGES[c]:
            for p in providers:
                for cond in conditions:
                    for n in range(1, passes + 1):
                        out.append((c, stage, p, cond, n))
    return out


def path_for(corpus: str, provider: str, condition: str, stage: str, n: int) -> Path:
    return OUT / corpus / provider / condition / f"{stage}_pass{n}.json"


def plan(todo: list[tuple], models: dict[str, str]) -> str:
    """An estimate in dollars from the repo's own price table, not arithmetic in
    a comment. Spending someone's API credit is a thing to show before doing."""
    from bristlenose.llm.pricing import PRICING

    # Measured from the June escuela run and the ikea intermediates: a clustering
    # or grouping call is ~2-3k tokens in and ~400 out; a segmentation call ~1.9k
    # in and ~100 out. Deliberately coarse — it prices the decision, not the bill.
    SIZE = {"s08": (1900, 100), "s10": (3000, 500), "s11": (2500, 400)}
    # s08 fans out one call PER SESSION inside a single cell, so a cell is not a
    # call. escuela has two sessions; counting cells here would under-price every
    # s08 row by half and the plan would be a number rather than an estimate.
    CALLS_PER_CELL = {"s08": 2, "s10": 1, "s11": 1}
    lines, total, unknown = [], 0.0, set()
    by_provider: dict[str, list] = {}
    for cell in todo:
        by_provider.setdefault(cell[2], []).append(cell)

    for provider, group in sorted(by_provider.items()):
        model = models[provider]
        calls = sum(CALLS_PER_CELL[c[1]] for c in group)
        tin = sum(SIZE[c[1]][0] * CALLS_PER_CELL[c[1]] for c in group)
        tout = sum(SIZE[c[1]][1] * CALLS_PER_CELL[c[1]] for c in group)
        if model in PRICING:
            pin, pout = PRICING[model]
            cost = tin / 1e6 * pin + tout / 1e6 * pout
            total += cost
            lines.append(f"  {provider:10} {model:22} {calls:3} calls  "
                         f"{tin:7,} in / {tout:6,} out   ${cost:.2f}")
        else:
            unknown.add(model)
            lines.append(f"  {provider:10} {model:22} {calls:3} calls  "
                         f"{tin:7,} in / {tout:6,} out   (not in PRICING)")
    total_calls = sum(CALLS_PER_CELL[c[1]] for c in todo)
    head = [f"{len(todo)} cell(s) to run = {total_calls} LLM call(s)"]
    tail = [f"  {'':10} {'':22} {'':3}        estimated total   ${total:.2f}"]
    if unknown:
        tail.append(f"  …plus {', '.join(sorted(unknown))}, absent from the price table")
    return "\n".join(head + lines + tail)


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", nargs="+", default=list(corpus_lib.CORPORA),
                    choices=corpus_lib.CORPORA)
    ap.add_argument("--provider", nargs="+", default=["anthropic", "openai", "google"])
    ap.add_argument("--condition", nargs="+", default=list(CONDITIONS), choices=CONDITIONS)
    ap.add_argument("--passes", type=int, default=3)
    ap.add_argument("--model", help="override the provider default (single provider only)")
    ap.add_argument("--plan", action="store_true", help="print the estimate, make no calls")
    ap.add_argument("--yes", action="store_true", help="make the calls")
    args = ap.parse_args()

    models = {p: PROVIDERS[p].default_model for p in args.provider}
    if args.model:
        if len(args.provider) != 1:
            raise SystemExit("error: --model applies to one provider; name it with --provider")
        models[args.provider[0]] = args.model

    everything = cells(args.corpus, args.provider, args.condition, args.passes)
    todo = [c for c in everything
            if not path_for(c[0], c[2], c[3], c[1], c[4]).exists()]
    done = len(everything) - len(todo)
    if done:
        print(f"{done} cell(s) already on disk — not re-run")

    print(plan(todo, models))
    if args.plan or not todo:
        return 0
    if not args.yes:
        print("\nrefusing to spend without --yes")
        return 1

    for i, (corpus, stage, provider, condition, n) in enumerate(todo, 1):
        out = path_for(corpus, provider, condition, stage, n)
        print(f"[{i}/{len(todo)}] {corpus} {stage} {provider} {condition} pass {n}… ",
              end="", flush=True)
        try:
            record = await run_cell(corpus, stage, provider, models[provider], condition)
        except Exception as exc:                      # noqa: BLE001 — a spike records, never swallows
            print(f"FAILED: {type(exc).__name__}: {exc}")
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        n_groups = len(record["result"])
        flag = "" if record["succeeded"] else "  (stage reported failure — fallback output)"
        print(f"{n_groups} group(s){flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
