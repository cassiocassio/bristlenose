"""Run one arm (prompt version × provider/model) over frozen study inputs.

Calls the stage's own ``_classify`` (same system prompt, language steer,
untrusted envelopes, response model and client) with only the prompt FILE
swapped, and records every attempt's raw reply before validation, so a
first-attempt failure the salvage hides is still counted.

    .venv/bin/python experiments/discussion-prompt-eval/run_arm.py \
        EVAL_DIR ARM_NAME --prompt 1.1.0 --llm anthropic [--model M] [--studies a,b]

Sessions run one at a time. A local arm refuses to start while another
``bristlenose analyze`` is running on this Mac (ollama-catalog's measurements).
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import subprocess
import sys
import time
from pathlib import Path

import bristlenose.discussion.stage as stage
import bristlenose.llm.client as client_mod
import bristlenose.llm.prompts as prompts_mod
from bristlenose.config import load_settings
from bristlenose.discussion import structure as st
from bristlenose.llm.client import LLMClient

HERE = Path(__file__).resolve().parent
NAME = "discussion-classify-turns"
# Sonnet 4.6 list price per million tokens (price table 2026-11-16 in llm-calls.jsonl)
PRICE = {"claude-sonnet-4-6": (3.0, 15.0)}

RAW: list[dict] = []


def template_for(variant: str) -> prompts_mod.PromptTemplate:
    """The arm's prompt file (prompts/v<variant>/), parsed by the product's own loader."""
    old = prompts_mod._PROMPTS_DIR
    try:
        prompts_mod._PROMPTS_DIR = HERE / "prompts" / f"v{variant}"
        prompts_mod._load_template.cache_clear()
        t = prompts_mod._load_template(NAME)
    finally:
        prompts_mod._PROMPTS_DIR = old
        prompts_mod._load_template.cache_clear()
    assert variant.startswith(t.version), (t.version, variant)
    return t


def install_recorders() -> None:
    orig_local_json = client_mod._local_json
    orig_repair = client_mod._validate_repairing

    def local_json(content):  # every local attempt, before validation
        try:
            data = orig_local_json(content)
        except Exception as exc:  # an unparseable reply is an attempt too
            RAW.append({"via": "local", "data": None, "parse_error": type(exc).__name__,
                        "chars": len(content or ""), "content": content})
            raise
        RAW.append({"via": "local", "data": copy.deepcopy(data)})
        return data

    def repairing(data, response_model, *, provider, model):
        if provider != "local":  # local attempts are recorded above
            RAW.append({"via": provider, "data": copy.deepcopy(data)})
        return orig_repair(data, response_model, provider=provider, model=model)

    client_mod._local_json = local_json
    client_mod._validate_repairing = repairing


def other_analyze_running() -> bool:
    """Another Ollama workload on this Mac: an analyze run or a model pull."""
    # By the binary's path: a shell whose command line merely MENTIONS the
    # words (another session's `pgrep -f "bristlenose analyze"` heartbeat)
    # would otherwise match forever.
    for pat in ("bin/bristlenose analyze", "(^|/)ollama pull"):
        out = subprocess.run(["pgrep", "-f", pat], capture_output=True, text=True)
        if out.stdout.strip():
            return True
    return False


def wait_for_quiet(done_flag: Path | None, state: Path, quiet_s: int = 600) -> None:
    """Hold until nothing else runs; unless the other session flagged its queue
    done, also hold until it has been quiet for *quiet_s* (a pull or the next
    run usually follows within minutes). A quiet spell once proven is kept in
    *state* (shared by the arms, refreshed each session), so the next session
    only needs nothing running; any other workload resets it."""
    quiet_since: float | None = None
    while True:
        if other_analyze_running():
            quiet_since = None
            state.unlink(missing_ok=True)
        else:
            fresh = state.exists() and time.time() - state.stat().st_mtime < 900
            if fresh or (done_flag is not None and done_flag.exists()):
                state.touch()
                return
            quiet_since = quiet_since or time.time()
            if time.time() - quiet_since >= quiet_s:
                state.touch()
                return
        print(f"  waiting for Ollama to be free ({time.strftime('%H:%M')})", flush=True)
        time.sleep(60)


async def run(args: argparse.Namespace) -> None:
    eval_dir = Path(args.eval_dir)
    tmpl = template_for(args.prompt)
    stage.get_prompt_template = lambda name: tmpl if name == NAME else prompts_mod.get_prompt_template(name)
    install_recorders()

    kw: dict[str, object] = {"llm_provider": args.llm}
    if args.llm == "local":
        kw["local_model"] = args.model
    elif args.model:
        kw["llm_model"] = args.model
    settings = load_settings(**kw)
    client = LLMClient(settings)
    model = args.model or settings.llm_model

    out_path = eval_dir / f"arm-{args.arm}.json"
    result = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {
        "arm": args.arm, "prompt": args.prompt, "prompt_sha": tmpl.sha, "llm": args.llm,
        "model": model, "studies": {}}
    studies = args.studies.split(",") if args.studies else [
        p.stem.removeprefix("inputs-") for p in sorted(eval_dir.glob("inputs-*.json"))
        if p.stem != "inputs-manifest"]
    for name in studies:
        inp = json.loads((eval_dir / f"inputs-{name}.json").read_text(encoding="utf-8"))
        spine = [st.Section(s["id"], s["title"], s["kind"], "planned", s["title"],
                            [st.Item(it["id"], it["text"][:24], it["text"]) for it in s["items"]])
                 for s in inp["spine"]]
        done = result["studies"].setdefault(name, {})
        for sid, ts in inp["sessions"].items():
            if sid in done and not args.redo:
                continue
            if args.llm == "local":
                wait_for_quiet(Path(args.done_flag) if args.done_flag else None,
                               eval_dir / ".ollama-quiet")
            turns = [st.Turn(t["id"], sid, 0.0, t["text"]) for t in ts]
            RAW.clear()
            tin0, tout0 = client.tracker.input_tokens, client.tracker.output_tokens
            t0 = time.perf_counter()
            rec: dict[str, object] = {"n_turns": len(turns)}
            try:
                labels, dropped = await stage._classify(client, spine, turns)
                rec["labels"] = [lb.__dict__ for lb in labels]
                rec["dropped"] = dropped
                rec["error"] = None
            except Exception as exc:  # noqa: BLE001 — a failed session is a result
                rec["labels"], rec["dropped"], rec["error"] = [], None, f"{type(exc).__name__}: {str(exc)[:200]}"
            rec["elapsed_s"] = round(time.perf_counter() - t0, 1)
            rec["attempts"] = len(RAW)
            rec["raw"] = [r["data"] for r in RAW]
            rec["parse_errors"] = [r.get("chars") for r in RAW if "parse_error" in r]
            rec["unparsed"] = [r["content"] for r in RAW if "parse_error" in r][:1]
            tin = client.tracker.input_tokens - tin0
            tout = client.tracker.output_tokens - tout0
            rec["tokens"] = [tin, tout]
            p = PRICE.get(model)
            rec["cost_usd"] = round((tin * p[0] + tout * p[1]) / 1e6, 4) if p else 0.0
            done[sid] = rec
            out_path.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
            print(f"{args.arm} {name} {sid}: {len(turns)} turns, attempts={rec['attempts']} "
                  f"dropped={rec['dropped']} err={rec['error']} {rec['elapsed_s']}s "
                  f"${rec['cost_usd']}", flush=True)
    total = sum(r.get("cost_usd", 0) for s in result["studies"].values() for r in s.values())
    print(f"{args.arm}: total ${total:.3f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("eval_dir")
    ap.add_argument("arm")
    ap.add_argument("--prompt", required=True, choices=["1.0.0", "1.1.0", "1.1.0b"])
    ap.add_argument("--llm", required=True)
    ap.add_argument("--model", default="")
    ap.add_argument("--studies", default="")
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--done-flag", default="", help="a file whose presence means the other queue is done")
    args = ap.parse_args()
    if args.llm == "local" and other_analyze_running():
        print("another bristlenose analyze is running; will wait before each session", file=sys.stderr)
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
