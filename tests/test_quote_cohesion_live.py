"""Stage 9 keeps a think-aloud passage together, on Claude and on ChatGPT. **Paid.**

``@pytest.mark.slow``, so the everyday ``pytest tests/`` never runs it. Run with
``pytest tests/test_quote_cohesion_live.py -m slow``: one quote-extraction call per
provider on the lab's synthetic fixture, about a cent each.

Why it exists: prompt 0.2.0 asked for quotes of "typically 1-5 sentences", and
ChatGPT read that literally on think-aloud. It returned one quote per transcript
line (24 quotes from 24 lines on this fixture, 21 Nov 2026), and project-ikea's
quotes came back too short for the report to break into paragraphs. Prompt 0.3.0
makes a quote one passage on one point. The verdict is the lab's
(``experiments/quote-cohesion/score.py``): every task quoted, no more than 3
quotes per task, none running into the next task, and coverage kept.

A model can still answer differently from one run to the next. 0.3.0 passed four
runs of four (two per provider); a failure here is a reading to repeat and look
at in the lab, not proof on its own.

A provider with no key, no credit, or no reachable service skips with a message
saying it never ran. Any other failure is a failure.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from bristlenose.events import CauseCategoryEnum

LAB = Path(__file__).resolve().parent.parent / "experiments" / "quote-cohesion"
FIXTURE = LAB / "fixture"

# The account or the network could not run the call: not a verdict on the prompt.
_ENVIRONMENTAL = {
    CauseCategoryEnum.AUTH,
    CauseCategoryEnum.OUT_OF_CREDIT,
    CauseCategoryEnum.QUOTA,
    CauseCategoryEnum.API_SERVER,
    CauseCategoryEnum.NETWORK,
}


def _load_scorer():
    spec = importlib.util.spec_from_file_location("quote_cohesion_score", LAB / "score.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.slow
@pytest.mark.parametrize("provider", ["anthropic", "openai"])
def test_one_passage_stays_one_quote(provider: str) -> None:
    from bristlenose.config import _CLOUD_KEY_FIELDS, load_settings
    from bristlenose.llm.client import LLMClient
    from bristlenose.models import SessionTopicMap
    from bristlenose.pipeline import load_transcripts_from_dir
    from bristlenose.stages.s09_quote_extraction import extract_quotes

    settings = load_settings(llm_provider=provider)
    if not getattr(settings, _CLOUD_KEY_FIELDS[provider]):
        pytest.skip(f"SKIPPED, NOT PASSED — no {provider} key configured; this check never ran")

    transcripts = load_transcripts_from_dir(FIXTURE / "transcripts")
    raw = json.loads((FIXTURE / "topic_boundaries.json").read_text(encoding="utf-8"))
    topic_maps = [SessionTopicMap.model_validate(x) for x in raw]
    quotes, outcome = asyncio.run(
        extract_quotes(
            transcripts,
            topic_maps,
            LLMClient(settings),
            min_quote_words=settings.min_quote_words,
        )
    )
    for failure in outcome.failed:
        if failure.cause.category in _ENVIRONMENTAL:
            pytest.skip(
                f"SKIPPED, NOT PASSED — {provider} returned {failure.cause.category.value}; "
                f"this check never ran. {failure.cause.message or ''}"
            )
    assert not outcome.failed, [f.cause for f in outcome.failed]

    score = _load_scorer()
    as_dicts = [q.model_dump(mode="json") for q in quotes]
    tasks = json.loads((FIXTURE / "tasks.json").read_text(encoding="utf-8"))
    cohesion = score.cohesion(tasks, as_dicts)
    coverage = score.fragmentation(FIXTURE / "transcripts", as_dicts).coverage
    words = [len(q["text"].split()) for q in as_dicts]
    summary = (
        f"{settings.llm_model}: {len(quotes)} quotes, per task {cohesion.per_task}, "
        f"crossing {cohesion.crossing}, unquoted {cohesion.unquoted_tasks}, "
        f"coverage {coverage}, words {words}"
    )
    assert cohesion.passed, summary
    assert coverage >= 0.9, summary
