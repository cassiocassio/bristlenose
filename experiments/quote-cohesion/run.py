"""Run the real stage-9 quote extraction on a study, with a chosen prompt.

Calls ``extract_quotes`` exactly as the pipeline does: one LLM call per session,
nothing else (no transcription, PII, clustering or theming). **This spends money**:
about a cent per run on the synthetic fixture, more on a real study.

Usage::

    python run.py --provider anthropic --out results/v0.3.0-claude-3.json
    python run.py --provider openai --out results/v0.2.0-openai-3.json \
        --prompt ../../bristlenose/llm/prompts-archive/prompts_2026-11-21_quote-extraction-v0.2.0-one-to-five-sentences.md
    python run.py --study ~/some-copy --provider openai --out /elsewhere/x.json

``--prompt current`` (the default) uses ``bristlenose/llm/prompts/`` as it stands.
``--prompt <file.md>`` (an archived version, or a draft) is copied over
``quote-extraction.md`` in a temporary copy of that folder, so only the
quote-extraction prompt changes.

A study folder holds ``transcripts/<session>.txt`` (the pipeline's
``transcripts-raw`` format) and ``topic_boundaries.json`` (the pipeline's
intermediate file). The default is the synthetic fixture. Point ``--study`` at a
copy of a real project only with ``--out`` outside this folder: real quotes are
participants' words and do not belong in the public tree.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import tempfile
from pathlib import Path

import bristlenose.llm.prompts as prompts
from bristlenose.config import load_settings
from bristlenose.llm.client import LLMClient
from bristlenose.models import SessionTopicMap
from bristlenose.pipeline import load_transcripts_from_dir
from bristlenose.stages.s09_quote_extraction import extract_quotes

HERE = Path(__file__).resolve().parent


def _prompt_dir(name: str, scratch: Path) -> Path:
    repo = Path(prompts.__file__).resolve().parent
    if name == "current":
        return repo
    candidate = Path(name).expanduser()
    if not candidate.is_file():
        sys.exit(f"no prompt file {candidate}")
    target = scratch / "prompts"
    shutil.copytree(repo, target, ignore=shutil.ignore_patterns("__pycache__", "*.py"))
    shutil.copy2(candidate, target / "quote-extraction.md")
    return target


async def _run(args: argparse.Namespace) -> None:
    study = Path(args.study).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()
    if study != (HERE / "fixture").resolve() and out.is_relative_to(HERE):
        sys.exit("a real study's quotes go outside experiments/: pass --out elsewhere")
    with tempfile.TemporaryDirectory() as tmp:
        prompts._PROMPTS_DIR = _prompt_dir(args.prompt, Path(tmp))
        prompts._load_template.cache_clear()
        template = prompts.get_prompt_template("quote-extraction")
        settings = load_settings(llm_provider=args.provider, llm_model=args.model)
        print(f"prompt {template.version}  provider {settings.llm_provider}  model {settings.llm_model}")
        transcripts = load_transcripts_from_dir(study / "transcripts")
        raw = json.loads((study / "topic_boundaries.json").read_text(encoding="utf-8"))
        topic_maps = [SessionTopicMap.model_validate(x) for x in raw]
        errors: list[str] = []
        quotes, outcome = await extract_quotes(
            transcripts,
            topic_maps,
            LLMClient(settings),
            min_quote_words=settings.min_quote_words,
            concurrency=3,
            errors=errors,
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps([q.model_dump(mode="json") for q in quotes], ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"{out.name}: {len(quotes)} quotes, {outcome.succeeded}/{outcome.attempted} sessions")
    for e in errors:
        print("error:", e[:200])


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--study", default=str(HERE / "fixture"))
    p.add_argument("--provider", required=True, help="anthropic, openai, azure, google, local")
    p.add_argument("--model", default=None, help="default: the provider's configured model")
    p.add_argument("--prompt", default="current", help="current, or a quote-extraction .md file")
    p.add_argument("--out", required=True)
    asyncio.run(_run(p.parse_args()))


if __name__ == "__main__":
    main()
