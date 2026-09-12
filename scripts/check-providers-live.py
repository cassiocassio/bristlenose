#!/usr/bin/env python3
"""Live check of every shipped (provider, model): alive, exists, right shape.

Three questions, asked twice per model: first by preflight's own one-token call --
the request ``bristlenose run`` makes before anything else -- then by a real stage
call through the actual ``LLMClient.analyze()``:

  i.   alive   — the key is accepted at all
  ii.  exists  — the model id still resolves (vendors soft-retire without notice:
                 "no longer available to new users" carries no shutdown date)
  iii. shape   — the call accepts our request and returns something that
                 validates as ``QuoteExtractionResult``

The mocked suite cannot ask any of these. On 4 Sep 2026 this found, in one run:
the new Claude default double-encoding its tool input, both Gemini picker
models retired for new users, and the ChatGPT modern-parameter path working.
The app's Settings "Online" light validates only the key, with a fixed cheap
model, so it cannot see ii or iii.

The list under test is DERIVED — the registry default plus the models the macOS
picker offers, read from LLMProvider.swift — so it tests what ships and cannot
drift from it. Keys are read exactly as the app reads them (keychain / env /
.env). Nothing here prints a key. One tiny prompt per call; a full run is pence.

    .venv/bin/python scripts/check-providers-live.py            # everything
    .venv/bin/python scripts/check-providers-live.py --provider anthropic

Exit 0 = every shipped model passed all three. Exit 1 = at least one failed.
Exit 2 = could not enumerate (a parse or key-presence problem, not a model one).
Not a CI gate — CI has no keys. Run it before a release, or on a cadence.

TWO KNOWN BLIND SPOTS (5 Sep 2026):
  - CLOSED 12 Sep 2026. This used to call ``LLMClient.analyze()`` directly and
    SKIP ``preflight/api_key.py``, which has its own request builder. The night
    the ChatGPT default moved, preflight sent ``max_tokens=1`` to a GPT-5-class
    model and every run aborted there with a 400 -- and this script said 7/7.
    ``run_preflight`` now asks preflight's own ``_validate_<provider>`` first,
    with the same key and the model under test, before the client is built;
    ``test-providers-live.py`` proves the order offline. The two request
    builders are checked together, not unified -- that is still owed.
  - CLOSED 5 Sep 2026. The hand-written USER prompt is gone; every call now uses
    a real stage template from ``bristlenose/llm/prompts/`` via
    ``get_prompt_template``, the real ``wrap_untrusted`` envelope and the real
    response model (``scripts/live_check_fixture.py``). The old invented prompt
    reproduced a Sonnet 5 double-encoding on quote-extraction that the REAL
    extraction prompt does not, and was blind to the failures that actually
    stopped the move, at quote-clustering and thematic-grouping.

ONE PASS IS STILL NOT A RUN. Clustering and grouping vary most between identical
calls, so green here means "the shape came back right once". The stability corpus
remains separate and owed.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

sys.path.insert(0, str(ROOT / "scripts"))

from live_check_fixture import BY_KEY, STAGES  # noqa: E402

from bristlenose.config import BristlenoseSettings, load_settings  # noqa: E402
from bristlenose.llm.client import LLMClient  # noqa: E402
from bristlenose.preflight import api_key as preflight  # noqa: E402
from bristlenose.providers import PROVIDERS  # noqa: E402

SWIFT = ROOT / "desktop/Bristlenose/Bristlenose/LLMProvider.swift"
SWIFT_CASE = {"anthropic": "claude", "openai": "chatGPT", "google": "gemini"}
PROVIDER_ORDER = ("anthropic", "openai", "google")

# The DEFAULT set: the two stages that actually broke on Sonnet 5. Both hand the
# model the whole quote set at once and both nest a list inside each item, which
# is the shape the double-encoding appeared on -- and they are the two smallest
# prompts of the six, so the honest default is also the cheap one. `--stages`
# runs all six.
DEFAULT_STAGES = ("s10:clusters", "s11:themes")


def shipped_models(provider: str) -> list[str]:
    """Registry default first, then the macOS picker's list, de-duplicated."""
    models = [PROVIDERS[provider].default_model]
    src = SWIFT.read_text(encoding="utf-8")
    block = re.search(r"var availableModels: \[String\] \{(.*?)\n    \}", src, re.S)
    if not block:
        raise RuntimeError(f"could not find availableModels in {SWIFT}")
    m = re.search(rf'case \.{SWIFT_CASE[provider]}:[^\[]*\[([^\]]*)\]', block.group(1))
    if not m:
        # Not `if m:`. A miss here used to fall through to the registry default
        # alone, so one `return` added to a Swift case dropped two of Claude's
        # three models and the run still printed "N/N passed" and exited 0 --
        # the same green-light-that-is-a-lie this script exists to catch, one
        # layer up. Enumeration is all-or-nothing; a partial list is exit 2.
        raise RuntimeError(
            f"could not find the .{SWIFT_CASE[provider]} case inside availableModels "
            f"in {SWIFT} -- refusing to test a partial list"
        )
    models += re.findall(r'"([^"]+)"', m.group(1))
    seen: list[str] = []
    for x in models:
        if x and x not in seen:
            seen.append(x)
    return seen


def classify(exc: Exception) -> str:
    """Which of the three questions failed, from the error text."""
    text = str(exc).lower()
    if any(k in text for k in ("api key not valid", "authentication", "invalid_api_key",
                                "401", "incorrect api key", "permission")):
        return "i.alive"
    if any(k in text for k in ("no longer available", "not found", "404",
                                "does not exist", "not_found", "unknown model")):
        return "ii.exists"
    return "iii.shape"


# Preflight's own buckets, mapped onto the three questions. Anything outside the
# map (network, an unbucketed status) falls through to classify() on the raw text,
# whose default arm is the one that fails loudest.
_PREFLIGHT_QUESTION = {
    "invalid_key": "i.alive",
    "billing_empty": "i.alive",
    "rate_limit": "i.alive",
    "model_unavailable": "ii.exists",
}


async def run_preflight(
    provider: str, model: str, settings: BristlenoseSettings
) -> tuple[str, str, int]:
    """Ask preflight's own request builder first.

    This is the call ``bristlenose run`` makes before any stage, and the one that
    broke alone on 4 Sep 2026 while ``analyze()`` passed. Same key, same model,
    same ``_validate_<provider>`` function the CLI resolves -- looked up by name at
    call time for the reason the CLI does it that way (a patched name must win).
    Returns (verdict, detail, elapsed_ms); a FAIL detail carries ``preflight`` in
    the stage slot so the column contract below holds.
    """
    api_key, _source = preflight._api_key_for(settings)
    if not api_key:
        return ("FAIL",
                f"{'i.alive':<10} preflight no key configured for {provider} (keychain / env / .env)",
                0)
    validator = getattr(preflight, f"_validate_{provider}")
    t0 = time.perf_counter()
    result = await asyncio.to_thread(validator, api_key, model)
    ms = int((time.perf_counter() - t0) * 1000)
    if result.ok:
        return "PASS", "", ms
    raw = re.sub(r"\s+", " ", result.raw_message)[:120]
    question = _PREFLIGHT_QUESTION.get(result.error_class or "") or classify(
        Exception(result.raw_message)
    )
    return "FAIL", f"{question:<10} preflight {result.error_class or 'unclassified'}: {raw}", ms


async def check(provider: str, model: str, stage_keys: tuple[str, ...] = ()) -> tuple[str, str]:
    """Preflight first, then the chosen stages, against one (provider, model).
    First failure wins.

    Column contract, relied on by check-release-ready.sh's awk: provider, model,
    verdict, question. Anything about WHICH stage goes after those four.
    """
    settings = load_settings(llm_provider=provider, llm_model=model)
    verdict, detail, total_ms = await run_preflight(provider, model, settings)
    if verdict == "FAIL":
        return verdict, detail
    notes: list[str] = ["preflight"]
    client = LLMClient(settings)
    stages = [BY_KEY[k] for k in (stage_keys or DEFAULT_STAGES)]
    for stage in stages:
        system_prompt, user_prompt = stage.prompts()
        t0 = time.perf_counter()
        try:
            result = await client.analyze(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=stage.model,
            )
        except Exception as exc:  # noqa: BLE001 -- the point is to report it
            detail = re.sub(r"\s+", " ", str(exc))[:120]
            return "FAIL", f"{classify(exc):<10} {stage.key} {type(exc).__name__}: {detail}"
        total_ms += int((time.perf_counter() - t0) * 1000)
        # Validating is not the same as answering. A model can return an empty
        # list and satisfy every schema here -- and an empty list is exactly how
        # a stage produces a report with nothing in it, which is the failure a
        # researcher actually sees. So a vacuous PASS is a FAIL.
        if not stage.substantive(result):
            return "FAIL", f"{'iii.shape':<10} {stage.key} validated but returned nothing usable"
        notes.append(stage.key.split(":")[-1])
    return "PASS", f"{'':<10} {'+'.join(notes)}, {total_ms} ms"


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", choices=PROVIDER_ORDER, help="check one provider only")
    ap.add_argument("--stages", action="store_true",
                    help="all six pipeline stages, not just the two that broke (~4c/model)")
    ap.add_argument("--stage", action="append", choices=[st.key for st in STAGES],
                    help="one named stage; repeatable")
    args = ap.parse_args()
    providers = [args.provider] if args.provider else list(PROVIDER_ORDER)
    if args.stage:
        stage_keys = tuple(args.stage)
    elif args.stages:
        stage_keys = tuple(st.key for st in STAGES)
    else:
        stage_keys = DEFAULT_STAGES

    plan: list[tuple[str, str]] = []
    for p in providers:
        try:
            plan += [(p, m) for m in shipped_models(p)]
        except Exception as exc:  # noqa: BLE001
            print(f"error: cannot enumerate {p}: {exc}", file=sys.stderr)
            return 2
    if not plan:
        print("error: enumerated zero models — that is a tool failure, not a pass", file=sys.stderr)
        return 2

    print(f"stages: {', '.join(stage_keys)}  "
          f"({len(plan)} model(s) x (preflight + {len(stage_keys)}) = "
          f"{len(plan) * (len(stage_keys) + 1)} live calls)")
    print(f"{'provider':<10} {'model':<26} {'result':<6} question   detail")
    print("-" * 96)
    failures = 0
    for provider, model in plan:
        verdict, detail = await check(provider, model, stage_keys)
        failures += verdict == "FAIL"
        print(f"{provider:<10} {model:<26} {verdict:<6} {detail}")
    print("-" * 96)
    print(f"{len(plan) - failures}/{len(plan)} shipped models passed all three questions")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
