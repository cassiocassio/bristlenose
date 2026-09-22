"""Every authored codebook against its decision register, its golden fixture,
and the other codebooks it points at.

Three gates, all CI-safe (no LLM):

1. **Register integrity** — for each codebook with a register doc and a golden
   fixture: every settled decision that cites fixture evidence (E1) names a
   witness quote; every witness names a decision that exists; every accept
   tag exists; the fixture's version matches the YAML's.

2. **Cross-reference resolution** — a ``not_this`` that names a tag in
   ANOTHER codebook must name one that exists. Every audit on 22 Sep 2026
   found dangling pointers: the Norman rewording left five in Nielsen; Yablonski
   pointed at four Nielsen tags that never existed. A discrimination hint the
   model cannot follow is worse than none. The parser is deliberately narrow:
   it only checks a phrase immediately followed by a parenthesised codebook
   name — ``guardrail (Nielsen H5)``, ``missing signifier (Norman →
   Affordances and signifiers)``, ``social influence (UXR)`` — and accepts a
   tag name, a group name, or a Nielsen heuristic number.

3. **Renames never collide** — no ``renamed_from`` names a live tag in the
   same codebook, in any codebook.

The live layer (``-m slow``) runs each fixture through the real prompt and
asserts the golden floor and that out-of-scope quotes stay low; Norman keeps
its own per-pair tests in ``test_norman_codebook.py``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from bristlenose.server.codebook import get_template, load_all_templates

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "tests" / "fixtures" / "codebook-golden"
DOCS = REPO / "docs"

#: Codebooks that carry a register and a fixture. Norman's own module covers
#: its vocabulary; the generic gates here run on it too.
REGISTERED = {
    "norman": ("design-codebook-norman.md", "N"),
    "garrett": ("design-codebook-garrett.md", "G"),
    "morville": ("design-codebook-morville.md", "M"),
    "nielsen": ("design-codebook-nielsen-register.md", "NL"),
    "yablonski": ("design-codebook-yablonski.md", "Y"),
}

#: How a not_this names another codebook. Nielsen refs often carry only a
#: heuristic number ("(H6)"), which is Nielsen's.
CODEBOOK_ALIASES = {
    "norman": "norman", "nielsen": "nielsen", "garrett": "garrett",
    "morville": "morville", "yablonski": "yablonski", "uxr": "uxr",
}
_REF = re.compile(
    r"([A-Za-z][A-Za-z0-9'’:\- ]{2,60}?)\s*\((?:in the )?(Norman|Nielsen|Garrett|Morville|Yablonski|UXR)"
    r"(?:'s)?(?:\s*(?:→|->)\s*([A-Za-z ]+?))?(?:\s*H(\d{1,2}))?\)|"
    r"([A-Za-z][A-Za-z0-9'’:\- ]{2,60}?)\s*\((H\d{1,2})\)"
)


def _fixture(cid: str) -> dict:
    return json.loads((FIXTURES / f"{cid}.json").read_text(encoding="utf-8"))


def _register_entries(cid: str) -> dict[str, str]:
    doc, prefix = REGISTERED[cid]
    text = (DOCS / doc).read_text(encoding="utf-8")
    pat = re.compile(
        rf"^- \*\*({prefix}-\d\d) · ([^\n]*?)\*\* —\s+(.*?)(?=^- \*\*{prefix}-\d\d|^## )",
        re.M | re.S,
    )
    entries = {m.group(1): m.group(2) + " " + m.group(3) for m in pat.finditer(text)}
    assert entries, f"{doc}: register not parsed"
    return entries


def _names(cid: str) -> tuple[set[str], set[str]]:
    t = get_template(cid)
    assert t is not None
    return ({x.name.lower() for g in t.groups for x in g.tags}, {g.name.lower() for g in t.groups})


# ---------------------------------------------------------------------------
# 1. Register integrity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cid", sorted(REGISTERED))
class TestRegisterIntegrity:
    def test_fixture_and_register_exist(self, cid: str) -> None:
        assert (FIXTURES / f"{cid}.json").exists(), cid
        assert (DOCS / REGISTERED[cid][0]).exists(), cid

    def test_fixture_matches_yaml_version(self, cid: str) -> None:
        t = get_template(cid)
        assert t is not None and t.version, f"{cid}: YAML carries no version"
        assert _fixture(cid)["version"] == t.version

    def test_fixture_accept_tags_exist(self, cid: str) -> None:
        tags, _ = _names(cid)
        for q in _fixture(cid)["quotes"]:
            for a in q["accept"]:
                assert a.lower() in tags, (cid, q["id"], a)

    def test_every_fixture_decision_exists(self, cid: str) -> None:
        entries = _register_entries(cid)
        for q in _fixture(cid)["quotes"]:
            if q.get("decision"):
                assert q["decision"] in entries, (cid, q["id"], q["decision"])

    def test_every_settled_decision_with_fixture_evidence_has_a_witness(self, cid: str) -> None:
        entries = _register_entries(cid)
        witnessed = {q["decision"] for q in _fixture(cid)["quotes"] if q.get("decision")}
        missing = [
            nid for nid, body in entries.items()
            if "settled" in body.split("**")[0].lower() and "E1" in body and nid not in witnessed
        ]
        assert not missing, (cid, missing)

    def test_fixture_covers_every_tag(self, cid: str) -> None:
        tags, _ = _names(cid)
        covered = {a.lower() for q in _fixture(cid)["quotes"] for a in q["accept"]}
        allowed_gaps = set(_fixture(cid).get("uncovered_by_decision", []))
        missing = tags - covered - {a.lower() for a in allowed_gaps}
        assert not missing, (cid, sorted(missing))

    def test_every_tag_has_full_prompts(self, cid: str) -> None:
        t = get_template(cid)
        assert t is not None
        for g in t.groups:
            for x in g.tags:
                assert x.definition and x.apply_when and x.not_this, (cid, x.name)


# ---------------------------------------------------------------------------
# 2. Cross-reference resolution — across ALL shipped codebooks
# ---------------------------------------------------------------------------


def _all_names() -> dict[str, tuple[set[str], set[str]]]:
    return {t.id: _names(t.id) for t in load_all_templates()}


def _resolve(phrase: str, target: str, group: str | None, names: dict) -> bool:
    tags, groups = names[target]
    # Yablonski's house prefix ("Sweller: cognitive overload") is dropped by
    # other codebooks when they point at the law; accept the part after it.
    tags = tags | {n.split(": ", 1)[1] for n in tags if ": " in n}
    p = phrase.lower().strip(" ,.;:'’\"")
    # A group arrow does not excuse a retired tag name: "grouping (Norman → Mapping)"
    # is dangling even though Mapping exists. The phrase itself must resolve.
    # The phrase may carry lead-in words ("that's", "consider", "or"); accept a suffix match.
    return any(p == n or p.endswith(" " + n) for n in tags | groups)


def _crossrefs(cid: str) -> list[tuple[str, str, str, str | None]]:
    """(tag, phrase, target codebook id, group) for every parenthesised reference."""
    t = get_template(cid)
    assert t is not None
    out = []
    for g in t.groups:
        for x in g.tags:
            for m in _REF.finditer(x.not_this):
                if m.group(6):  # bare (H6) — Nielsen
                    out.append((x.name, m.group(5), "nielsen", None))
                else:
                    target = CODEBOOK_ALIASES[m.group(2).lower()]
                    out.append((x.name, m.group(1), target, m.group(3)))
    return out


@pytest.mark.parametrize("cid", [t.id for t in load_all_templates()])
def test_cross_references_name_real_tags(cid: str) -> None:
    names = _all_names()
    dangling = []
    for tag, phrase, target, group in _crossrefs(cid):
        if target == cid:
            continue  # self-references are the ordinary sibling case
        if not _resolve(phrase, target, group, names):
            dangling.append(f"{tag}: '{phrase}' -> {target}" + (f" → {group}" if group else ""))
    assert not dangling, f"{cid}: not_this names tags that do not exist:\n  " + "\n  ".join(dangling)


# ---------------------------------------------------------------------------
# 3. Renames never collide
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cid", [t.id for t in load_all_templates()])
def test_renamed_from_never_names_a_live_tag(cid: str) -> None:
    t = get_template(cid)
    assert t is not None
    live = {x.name.lower() for g in t.groups for x in g.tags}
    for g in t.groups:
        for x in g.tags:
            for old in x.renamed_from:
                assert old.lower() not in live, (cid, x.name, old)
        for old in g.renamed_from:
            assert old.lower() not in {gg.name.lower() for gg in t.groups}, (cid, g.name, old)


# ---------------------------------------------------------------------------
# Live layer — every registered fixture through the real prompt
# ---------------------------------------------------------------------------

def _run_live(cid: str) -> dict[str, tuple[str, float]]:
    """Every fixture quote of one codebook through the real autocode prompt."""
    import asyncio

    from bristlenose.config import load_settings
    from bristlenose.llm.client import LLMClient
    from bristlenose.llm.failure_classifier import LLMFailureKind, classify_exception
    from bristlenose.llm.prompts import get_prompt
    from bristlenose.llm.structured import AutoCodeBatchResult
    from bristlenose.server.autocode import (
        BATCH_SIZE,
        QuoteBatchItem,
        build_quote_batch,
        build_tag_taxonomy,
    )

    environmental = {
        LLMFailureKind.OUT_OF_CREDIT, LLMFailureKind.INVALID_KEY,
        LLMFailureKind.NETWORK, LLMFailureKind.RATE_LIMITED, LLMFailureKind.SERVER_ERROR,
    }
    settings = load_settings()
    if settings.llm_provider == "local":
        pytest.skip("AutoCode requires a cloud provider (not Ollama)")
    template = get_template(cid)
    assert template is not None
    taxonomy = build_tag_taxonomy(template)
    prompt_pair = get_prompt("autocode")
    client = LLMClient(settings)
    quotes = _fixture(cid)["quotes"]

    async def batch(items: list[dict]) -> dict[str, tuple[str, float]]:
        qs = [QuoteBatchItem(db_id=i, text=q["text"], session_id="s1", participant_id="p1",
                             topic_label="", sentiment="") for i, q in enumerate(items)]
        user_prompt = prompt_pair.user.format(
            codebook_title=template.title, codebook_preamble=template.preamble,
            formatted_tag_taxonomy=taxonomy, formatted_quotes=build_quote_batch(qs),
        )
        res: AutoCodeBatchResult = await client.analyze(
            system_prompt=prompt_pair.system, user_prompt=user_prompt, response_model=AutoCodeBatchResult,
        )
        amap = {a.quote_index: a for a in res.assignments}
        return {q["id"]: ((amap[i].tag_name.lower().strip(), amap[i].confidence) if i in amap else ("", 0.0))
                for i, q in enumerate(items)}

    async def go() -> dict[str, tuple[str, float]]:
        out: dict[str, tuple[str, float]] = {}
        for i in range(0, len(quotes), BATCH_SIZE):
            out.update(await batch(quotes[i:i + BATCH_SIZE]))
        return out

    try:
        return asyncio.run(go())
    except Exception as exc:
        if classify_exception(settings.llm_provider, exc) in environmental:
            pytest.skip(f"SKIPPED, NOT PASSED — {settings.llm_provider}: {exc}")
        raise


_LIVE_CACHE: dict[str, dict[str, tuple[str, float]]] = {}


@pytest.mark.slow
@pytest.mark.parametrize("cid", [c for c in sorted(REGISTERED) if c != "norman"])  # norman has its own module
class TestLiveRegistered:
    @pytest.fixture()
    def results(self, cid: str) -> dict[str, tuple[str, float]]:
        if cid not in _LIVE_CACHE:
            _LIVE_CACHE[cid] = _run_live(cid)
        return _LIVE_CACHE[cid]

    def test_golden_floor(self, cid: str, results: dict[str, tuple[str, float]]) -> None:
        """One quote per tag, written to the wording: ≥ 80% correct is the floor."""
        rows = [q for q in _fixture(cid)["quotes"] if q["kind"] == "golden"]
        ok = sum(1 for q in rows if results[q["id"]][0] in {a.lower() for a in q["accept"]})
        wrong = [(q["text"][:60], results[q["id"]]) for q in rows if results[q["id"]][0] not in {a.lower() for a in q["accept"]}]
        assert ok / len(rows) >= 0.8, f"{cid}: {ok}/{len(rows)}; wrong: {wrong}"

    def test_out_of_scope_stays_low(self, cid: str, results: dict[str, tuple[str, float]]) -> None:
        leaks = [(q["text"], results[q["id"]]) for q in _fixture(cid)["quotes"]
                 if q["kind"] == "oos" and results[q["id"]][1] >= 0.4]
        assert not leaks, leaks

    def test_retired_traps_are_not_confident(self, cid: str, results: dict[str, tuple[str, float]]) -> None:
        """A quote whose only v1 home was retired must not land above the accept line."""
        hot = [(q["text"][:60], results[q["id"]]) for q in _fixture(cid)["quotes"]
               if q["kind"] == "trap" and results[q["id"]][1] >= 0.7]
        assert not hot, f"{cid}: {hot}"
