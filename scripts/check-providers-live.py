#!/usr/bin/env python3
"""Live check of every shipped (provider, model): alive, exists, right shape.

Three questions, one real call each, through the actual ``LLMClient.analyze()``:

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

from bristlenose.config import load_settings  # noqa: E402
from bristlenose.llm.client import LLMClient  # noqa: E402
from bristlenose.llm.structured import QuoteExtractionResult  # noqa: E402
from bristlenose.providers import PROVIDERS  # noqa: E402

SWIFT = ROOT / "desktop/Bristlenose/Bristlenose/LLMProvider.swift"
SWIFT_CASE = {"anthropic": "claude", "openai": "chatGPT", "google": "gemini"}
PROVIDER_ORDER = ("anthropic", "openai", "google")

SYSTEM = "You extract short verbatim quotes from user-research transcripts."
# Deliberately a *natural* transcript, not a terse one: the Sonnet 5
# double-encoding only reproduced on natural phrasing.
USER = (
    "Extract up to 2 quotes from this transcript. Use the given timecodes.\n\n"
    "[00:00:04] P1: Honestly the onboarding was fine until the password step. "
    "It rejected mine three times with no reason given, I nearly gave up. "
    "[00:00:19] P1: Once I was in, the dashboard was actually pretty clear."
)


def shipped_models(provider: str) -> list[str]:
    """Registry default first, then the macOS picker's list, de-duplicated."""
    models = [PROVIDERS[provider].default_model]
    src = SWIFT.read_text(encoding="utf-8")
    block = re.search(r"var availableModels: \[String\] \{(.*?)\n    \}", src, re.S)
    if not block:
        raise RuntimeError(f"could not find availableModels in {SWIFT}")
    m = re.search(rf'case \.{SWIFT_CASE[provider]}: \[([^\]]*)\]', block.group(1))
    if m:
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


async def check(provider: str, model: str) -> tuple[str, str]:
    settings = load_settings(llm_provider=provider, llm_model=model)
    client = LLMClient(settings)
    t0 = time.perf_counter()
    try:
        result = await client.analyze(
            system_prompt=SYSTEM, user_prompt=USER, response_model=QuoteExtractionResult,
        )
    except Exception as exc:  # noqa: BLE001 — the point is to report it
        detail = re.sub(r"\s+", " ", str(exc))[:140]
        return "FAIL", f"{classify(exc):<10} {type(exc).__name__}: {detail}"
    ms = int((time.perf_counter() - t0) * 1000)
    return "PASS", f"{'':<10} {len(result.quotes)} quote(s), {ms} ms"


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", choices=PROVIDER_ORDER, help="check one provider only")
    args = ap.parse_args()
    providers = [args.provider] if args.provider else list(PROVIDER_ORDER)

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

    print(f"{'provider':<10} {'model':<26} {'result':<6} question   detail")
    print("-" * 96)
    failures = 0
    for provider, model in plan:
        verdict, detail = await check(provider, model)
        failures += verdict == "FAIL"
        print(f"{provider:<10} {model:<26} {verdict:<6} {detail}")
    print("-" * 96)
    print(f"{len(plan) - failures}/{len(plan)} shipped models passed all three questions")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
