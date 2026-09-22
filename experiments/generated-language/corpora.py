#!/usr/bin/env python3
"""Load the spike's corpora, translating and caching the two derived ones.

Three corpora, per the README:

  escuela     native es-MX, already on disk, 18 general_context quotes plus
              Spanish transcripts (so it can exercise s08 as well)
  ikea-es     project-ikea's 33 quotes translated to Spanish
  ikea-mixed  the same quotes, s1 Spanish / s2 Catalan / s3 left English

Translation is data preparation, not a condition — it runs once, on whichever
provider you point it at, and caches to `corpora/`. The analysis passes never
re-translate, so the corpus is identical across every provider and condition
being compared. Re-running with the cache present makes no calls.

`topic_label` is translated along with `text`: s10 and s11 hand it to the model
as a hint, and an English hint on a Spanish quote leaks the answer into the
thing being measured. `verbatim_excerpt` is set equal to the translated text —
nothing downstream of s09 reads it, and leaving the Spanish quote sitting beside
its English original inside the same record invites a later reader to think one
of them is ground truth.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pydantic import BaseModel, Field  # noqa: E402

from bristlenose.config import load_settings  # noqa: E402
from bristlenose.llm.client import LLMClient  # noqa: E402
from bristlenose.models import (  # noqa: E402
    ExtractedQuote,
    PiiCleanTranscript,
    SessionTopicMap,
)

HERE = Path(__file__).resolve().parent
CACHE = HERE / "corpora"
TRIALS = ROOT / "trial-runs"

ESCUELA = TRIALS / "demo-escuela-gastronomica/bristlenose-output/.bristlenose/intermediate"
IKEA = TRIALS / "project-ikea/bristlenose-output/.bristlenose/intermediate"

#: Which language each ikea session becomes in the mixed corpus. English is a
#: deliberate third of the corpus: the V1 decision forces one output language
#: over a study whose sessions disagree, and a corpus where every session needs
#: translating would not test that.
MIXED_PLAN = {"s1": "Spanish", "s2": "Catalan", "s3": None}

LANGUAGE_NOTE = {
    "Spanish": "Latin American Spanish (es-MX), as a participant would speak it",
    "Catalan": "Catalan (ca-ES), as a participant in Barcelona would speak it",
}


class TranslatedQuote(BaseModel):
    index: int = Field(description="The index of the quote being translated")
    text: str = Field(description="The quote, translated, keeping its register and hesitations")
    topic_label: str = Field(description="The topic label, translated")


class TranslationResult(BaseModel):
    quotes: list[TranslatedQuote] = Field(description="Every quote, translated, in order")


def _load_quotes(path: Path) -> list[ExtractedQuote]:
    raw = json.loads((path / "extracted_quotes.json").read_text(encoding="utf-8"))
    items = raw if isinstance(raw, list) else next(v for v in raw.values() if isinstance(v, list))
    return [ExtractedQuote.model_validate(q) for q in items]


def load_transcripts(path: Path) -> tuple[list[PiiCleanTranscript], list[SessionTopicMap]]:
    """Rehydrate cached transcripts + topic maps, for the s08 cells.

    Same reconstruction as `quote-stability/run.py`: `source_file`,
    `session_date` and `duration_seconds` are required by the model, are not
    carried in `session_segments.json`, and never reach the prompt — so they are
    rebuilt from the data rather than faked from somewhere that looks authoritative.
    """
    segs = json.loads((path / "session_segments.json").read_text(encoding="utf-8"))
    tmaps = {t["session_id"]: t for t in json.loads((path / "topic_boundaries.json").read_text(encoding="utf-8"))}

    transcripts, topic_maps = [], []
    for sid, rows in segs.items():
        if sid not in tmaps:
            continue
        transcripts.append(PiiCleanTranscript.model_validate({
            "session_id": sid,
            "participant_id": tmaps[sid]["participant_id"],
            "source_file": f"{sid}.mp4",
            "session_date": "2026-01-01T00:00:00",
            "duration_seconds": max((r.get("end_time") or 0) for r in rows) if rows else 0,
            "segments": rows,
        }))
        topic_maps.append(SessionTopicMap.model_validate(tmaps[sid]))
    return transcripts, topic_maps


async def _translate(quotes: list[ExtractedQuote], language: str,
                     provider: str, model: str) -> list[ExtractedQuote]:
    """One call, all quotes, so the vocabulary stays consistent across them."""
    payload = [
        {"index": i, "text": q.text, "topic_label": q.topic_label}
        for i, q in enumerate(quotes)
    ]
    system = (
        "You translate user-research interview quotes for a test corpus. You "
        "preserve register, hesitation and informality exactly — a participant "
        "who trails off still trails off. You do not tidy, summarise or "
        "improve. Product names, brand names and on-screen UI labels stay as "
        "they appear."
    )
    user = (
        f"Translate every quote and its topic label into {LANGUAGE_NOTE[language]}.\n\n"
        "Return one entry per input index, all of them, in order.\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=1)
    )
    client = LLMClient(load_settings(llm_provider=provider, llm_model=model))
    result = await client.analyze(
        system_prompt=system, user_prompt=user, response_model=TranslationResult,
    )
    by_index = {t.index: t for t in result.quotes}
    missing = [i for i in range(len(quotes)) if i not in by_index]
    if missing:
        raise SystemExit(
            f"error: translation dropped {len(missing)} of {len(quotes)} quotes "
            f"(indices {missing[:8]}…). A short corpus is a different corpus — "
            f"fix or re-run rather than analysing the remainder."
        )

    out = []
    for i, q in enumerate(quotes):
        t = by_index[i]
        out.append(q.model_copy(update={
            "text": t.text,
            "verbatim_excerpt": t.text,
            "topic_label": t.topic_label,
        }))
    return out


async def build(provider: str, model: str, force: bool) -> None:
    CACHE.mkdir(exist_ok=True)
    ikea = _load_quotes(IKEA)
    print(f"ikea: {len(ikea)} quotes, {len({q.session_id for q in ikea})} sessions")

    es_path = CACHE / "ikea-es.json"
    if es_path.exists() and not force:
        print(f"  ikea-es: cached ({es_path.name}) — no calls")
    else:
        print("  ikea-es: translating (1 call)…")
        out = await _translate(ikea, "Spanish", provider, model)
        es_path.write_text(json.dumps([q.model_dump(mode="json") for q in out],
                                      ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  ikea-es: wrote {len(out)} quotes")

    mixed_path = CACHE / "ikea-mixed.json"
    if mixed_path.exists() and not force:
        print(f"  ikea-mixed: cached ({mixed_path.name}) — no calls")
        return

    merged: list[ExtractedQuote] = []
    for sid, language in MIXED_PLAN.items():
        part = [q for q in ikea if q.session_id == sid]
        if not part:
            print(f"  ikea-mixed: no session {sid} — skipped", file=sys.stderr)
            continue
        if language is None:
            print(f"  ikea-mixed: {sid} stays English ({len(part)} quotes)")
            merged.extend(part)
            continue
        print(f"  ikea-mixed: {sid} → {language} ({len(part)} quotes, 1 call)…")
        merged.extend(await _translate(part, language, provider, model))
    mixed_path.write_text(json.dumps([q.model_dump(mode="json") for q in merged],
                                     ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  ikea-mixed: wrote {len(merged)} quotes")


def load(corpus: str) -> list[ExtractedQuote]:
    """The quotes for a corpus id. Raises if a derived one has not been built."""
    if corpus == "escuela":
        return _load_quotes(ESCUELA)
    path = CACHE / f"{corpus}.json"
    if not path.exists():
        raise SystemExit(f"error: {corpus} not built — run `corpora.py --build` first")
    return [ExtractedQuote.model_validate(q) for q in json.loads(path.read_text(encoding="utf-8"))]


CORPORA = ("escuela", "ikea-es", "ikea-mixed")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", action="store_true", help="translate and cache the derived corpora")
    ap.add_argument("--force", action="store_true", help="re-translate even if cached (costs money)")
    ap.add_argument("--provider", default="anthropic")
    ap.add_argument("--model", default="claude-sonnet-4-6")
    args = ap.parse_args()

    if args.build:
        asyncio.run(build(args.provider, args.model, args.force))
        return 0

    for c in CORPORA:
        try:
            quotes = load(c)
        except SystemExit as exc:
            print(f"{c:12} {exc}")
            continue
        kinds = {}
        for q in quotes:
            kinds[q.quote_type.value] = kinds.get(q.quote_type.value, 0) + 1
        print(f"{c:12} {len(quotes):3} quotes  {kinds}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
