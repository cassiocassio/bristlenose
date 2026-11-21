"""The provider-links register (bristlenose/data/provider-links.json) and its gate.

Links we send people to, and claims that rest on a provider's page, are declared once in
the register; every file that carries a copy is listed as a mirror. These tests run offline
(the live fetch is ``scripts/check-provider-links.py --live``, never part of a test run).
They fail when a provider URL appears that is not registered, when a listed mirror stops
carrying its URL, when a retired URL comes back, or when a claim's wording leaves a file.
The website repo's docs are swept too when it is checked out (BN_WEBSITE_REPO, default
~/Code/bristlenose-website) and skipped quietly when it is not.
"""

from __future__ import annotations

import copy
import importlib.util
import re
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "check_provider_links", ROOT / "scripts" / "check-provider-links.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_provider_links"] = mod
    spec.loader.exec_module(mod)
    return mod


cpl = _load()


def test_the_tree_agrees_with_the_register() -> None:
    problems = cpl.check(cpl.website_root())
    assert not problems, "\n" + "\n".join(problems)


def test_register_is_well_formed() -> None:
    reg = cpl.load_register()
    links = cpl.all_links(reg)
    ids = [x["id"] for x in links] + [c["id"] for c in reg["claims"]]
    assert len(ids) == len(set(ids)), "duplicate id in the register"
    norms = [cpl.normalise(x["url"]) for x in links]
    assert len(norms) == len(set(norms)), "the same URL is registered twice"
    for link in links:
        assert link["url"].startswith("https://"), link["id"]
        assert link["mirrors"], f"{link['id']} lists no mirror, so nothing points at its copies"
        date.fromisoformat(link["verified"])
        assert link["purpose"].strip()
    for claim in reg["claims"]:
        date.fromisoformat(claim["verified"])
        assert claim["mirrors"] and claim["source"] and claim["claim"]
    for pat in reg["ignore_patterns"] + [r["pattern"] for r in reg["retired"]]:
        re.compile(pat)


def test_every_provider_the_app_names_is_registered() -> None:
    keys = set(cpl.load_register()["providers"])
    assert {"claude", "chatgpt", "gemini", "azure", "ollama"} <= keys


# ---- the gate can fail --------------------------------------------------------------


def _with_register(monkeypatch: pytest.MonkeyPatch, mutate) -> list[str]:
    reg = copy.deepcopy(cpl.load_register())
    mutate(reg)
    monkeypatch.setattr(cpl, "load_register", lambda *a, **k: reg)
    return cpl.check(cpl.website_root())


def test_an_unregistered_url_is_reported_with_its_file_and_line(
        monkeypatch: pytest.MonkeyPatch) -> None:
    def drop(reg: dict) -> None:
        reg["providers"]["claude"]["links"] = [
            x for x in reg["providers"]["claude"]["links"] if x["id"] != "claude.keys"]

    problems = _with_register(monkeypatch, drop)
    assert any("platform.claude.com/settings/keys is not in the provider-links register" in p
               and re.search(r":\d+:", p) for p in problems), problems


def test_a_mirror_that_lost_its_url_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    def retarget(reg: dict) -> None:
        for x in reg["providers"]["claude"]["links"]:
            if x["id"] == "claude.keys":
                x["url"] = "https://platform.claude.com/settings/keys-moved"

    problems = _with_register(monkeypatch, retarget)
    assert any("claude.keys" in p and "no longer carries" in p for p in problems), problems


def test_a_file_not_listed_as_a_mirror_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    def unlist(reg: dict) -> None:
        for x in reg["providers"]["claude"]["links"]:
            if x["id"] == "claude.keys":
                x["mirrors"] = [m for m in x["mirrors"]
                                if (m if isinstance(m, str) else m["file"]) != "bristlenose/cli.py"]

    problems = _with_register(monkeypatch, unlist)
    assert any("bristlenose/cli.py" in p and "not one of its mirrors" in p for p in problems)


def test_a_claim_that_left_its_file_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    def reword(reg: dict) -> None:
        reg["claims"][0]["mirrors"][0]["contains"] = "a sentence nobody wrote"

    problems = _with_register(monkeypatch, reword)
    assert any(p.startswith("claim ") and "no longer says" in p for p in problems), problems


@pytest.mark.parametrize("url", [
    "console.anthropic.com/settings/keys",
    "docs.anthropic.com/en/docs/about-claude/models",
    "ai.google.dev/pricing",
    "aistudio.google.com/app/apikey",
    "platform.openai.com/account/billing",
    "platform.openai.com/settings/organization/billing",
    "openai.com/api/pricing",
])
def test_retired_urls_are_caught(url: str) -> None:
    assert cpl.retired_hit(url, cpl.load_register()), url


@pytest.mark.parametrize("url", [
    "platform.openai.com/settings/organization/billing/overview",
    "platform.claude.com/settings/billing",
])
def test_current_urls_are_not_retired(url: str) -> None:
    assert cpl.retired_hit(url, cpl.load_register()) is None


def test_protocol_constants_are_ignored_but_links_are_not() -> None:
    reg = cpl.load_register()
    assert cpl.is_ignored("api.anthropic.com/v1/models", reg)
    assert cpl.is_ignored("your-resource.openai.azure.com", reg)
    assert cpl.is_ignored("graph.microsoft.com/v1.0/me", reg)
    assert not cpl.is_ignored("platform.claude.com/settings/keys", reg)
    assert not cpl.is_ignored("openai.com/api/pricing", reg)


def test_normalise() -> None:
    n = cpl.normalise
    assert n("https://www.anthropic.com/") == "anthropic.com"
    assert n("https://Platform.Claude.com/settings/keys).") == "platform.claude.com/settings/keys"
    assert n("platform.claude.com/") == "platform.claude.com"


# ---- the live half's judgement, with no network ------------------------------------


def _link(login: bool = False) -> dict:
    return {"id": "x", "url": "https://a.example/x", "login": login, "mirrors": []}


def test_judge_ok_moved_login_blocked_broken() -> None:
    j = cpl.judge
    assert j(_link(), [("https://a.example/x", 200)])[0] == "ok"
    moved = j(_link(), [("https://a.example/x", 301), ("https://b.example/y", 200)])
    assert moved[0] == "moved" and "permanent" in moved[1]
    assert j(_link(True), [("https://a.example/x", 302),
                           ("https://accounts.google.com/signin", 200)])[0] == "login"
    assert j(_link(), [("https://a.example/x", 403)])[0] == "blocked"
    assert j(_link(), [("https://a.example/x", 404)])[0] == "broken"
    assert j(_link(), [("https://a.example/x", "error: timed out")])[0] == "broken"


def test_the_normal_run_makes_no_network_call(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*a, **k):
        raise AssertionError("the offline check must not touch the network")

    monkeypatch.setattr(cpl, "fetch_chain", boom)
    monkeypatch.setattr(cpl.urllib.request, "build_opener", boom)
    assert cpl.check(cpl.website_root()) == []
