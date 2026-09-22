#!/usr/bin/env python
"""Run quotes through a codebook exactly as AutoCode would, and write what
came back. The tool the Norman decision register was built with.

    .venv/bin/python scripts/codebook-harness.py norman quotes.txt out.json
    .venv/bin/python scripts/codebook-harness.py path/to/draft.yaml tests/fixtures/codebook-golden/norman.json out.json
    .venv/bin/python scripts/codebook-harness.py --compare a.json b.json

The first argument is a shipped codebook id or a path to a draft YAML — a
draft is parsed by the real loader, so a malformed one fails here rather than
in serve. Quotes come from a golden fixture (``.json`` with a ``quotes`` list)
or a text file, one quote per line, ``#`` lines ignored. Each result row
carries the tag, the confidence and the model's rationale; the fixture's
``accept`` and ``decision`` fields are carried through so ``--compare`` can
say which decisions moved.

``--compare`` prints a per-quote diff of two result files: tag changed,
crossed the 0.7 accept line, or correctness changed against ``accept``.

Paid: one LLM call per 25 quotes on the configured provider. A fixture of
125 quotes is five calls, roughly ten pence on Sonnet.
"""

from __future__ import annotations

import asyncio
import json
import sys
import textwrap
from pathlib import Path

import yaml

from bristlenose.config import load_settings
from bristlenose.llm.client import LLMClient
from bristlenose.llm.prompts import get_prompt
from bristlenose.llm.structured import AutoCodeBatchResult
from bristlenose.server.autocode import (
    BATCH_SIZE,
    QuoteBatchItem,
    build_quote_batch,
    build_tag_taxonomy,
)
from bristlenose.server.codebook import CodebookTemplate, _parse_template, get_template


def _load_template(spec: str) -> CodebookTemplate:
    path = Path(spec)
    if path.suffix in (".yaml", ".yml") and path.exists():
        return _parse_template(yaml.safe_load(path.read_text(encoding="utf-8")), path.name)
    template = get_template(spec)
    if template is None:
        sys.exit(f"no codebook {spec!r} and no such file")
    return template


def _load_quotes(spec: str) -> list[dict]:
    path = Path(spec)
    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return list(data["quotes"])
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()]
    return [
        {"id": f"line-{i + 1}", "kind": "real", "text": ln, "accept": None}
        for i, ln in enumerate(lines) if ln and not ln.startswith("#")
    ]


def run(template_spec: str, quotes_spec: str, out: str) -> None:
    settings = load_settings()
    template = _load_template(template_spec)
    quotes = _load_quotes(quotes_spec)
    taxonomy = build_tag_taxonomy(template)
    prompt_pair = get_prompt("autocode")
    client = LLMClient(settings)
    group_of = {t.name: g.name for g in template.groups for t in g.tags}

    async def batch(items: list[dict]) -> list[dict]:
        qs = [
            QuoteBatchItem(db_id=i, text=q["text"], session_id="s1", participant_id="p1",
                           topic_label="", sentiment="")
            for i, q in enumerate(items)
        ]
        user_prompt = prompt_pair.user.format(
            codebook_title=template.title, codebook_preamble=template.preamble,
            formatted_tag_taxonomy=taxonomy, formatted_quotes=build_quote_batch(qs),
        )
        res: AutoCodeBatchResult = await client.analyze(
            system_prompt=prompt_pair.system, user_prompt=user_prompt,
            response_model=AutoCodeBatchResult,
        )
        amap = {a.quote_index: a for a in res.assignments}
        rows = []
        for i, q in enumerate(items):
            a = amap.get(i)
            tag = a.tag_name.lower().strip() if a else ""
            rows.append({**q, "tag": tag, "group": group_of.get(tag, "?"),
                         "conf": a.confidence if a else 0.0, "rationale": a.rationale if a else ""})
        return rows

    async def go() -> list[dict]:
        results: list[dict] = []
        for i in range(0, len(quotes), BATCH_SIZE):
            results.extend(await batch(quotes[i:i + BATCH_SIZE]))
        return results

    results = asyncio.run(go())
    Path(out).write_text(json.dumps({
        "codebook": template.id, "version": template.version, "model": settings.llm_model,
        "provider": settings.llm_provider, "results": results,
    }, indent=1, ensure_ascii=False), encoding="utf-8")
    scored = [r for r in results if r.get("accept")]
    hi = [r for r in results if r["conf"] >= 0.7]
    print(f"{template.id} {template.version or ''} on {settings.llm_model}: n={len(results)}, "
          f"at or above 0.7: {len(hi)}"
          + (f", correct: {sum(r['tag'] in r['accept'] for r in scored)}/{len(scored)}" if scored else "")
          + f" -> {out}")


def compare(a_path: str, b_path: str) -> None:
    a = json.loads(Path(a_path).read_text(encoding="utf-8"))
    b = json.loads(Path(b_path).read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in b["results"]}
    print(f"{a['codebook']} {a.get('version', '')} -> {b['codebook']} {b.get('version', '')}\n")
    n = 0
    for x in a["results"]:
        y = by_id.get(x["id"])
        if y is None:
            continue
        crossed = (x["conf"] >= 0.7) != (y["conf"] >= 0.7)
        acc = x.get("accept")
        ok_x = (x["tag"] in acc) if acc else None
        ok_y = (y["tag"] in acc) if acc else None
        if x["tag"] != y["tag"] or crossed or ok_x != ok_y:
            n += 1
            verdict = {(False, True): "FIXES", (True, False): "BREAKS"}.get((ok_x, ok_y), "")
            print(f"[{x['id']}] {x.get('decision', '')} {'THRESHOLD ' if crossed else ''}{verdict}")
            print("  Q:", textwrap.shorten(x["text"], 160))
            if acc:
                print("  want:", acc)
            print(f"  a: {x['tag']} @{x['conf']:.2f} — {textwrap.shorten(x['rationale'], 140)}")
            print(f"  b: {y['tag']} @{y['conf']:.2f} — {textwrap.shorten(y['rationale'], 140)}\n")
    print(f"{n} quotes differ")


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 3 and args[0] == "--compare":
        compare(args[1], args[2])
    elif len(args) == 3:
        run(*args)
    else:
        sys.exit(__doc__)
