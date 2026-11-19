"""The codebook builder refuses a call its provider cannot answer, as AutoCode does.

Until 19 Nov 2026 the three builder routes that reach a model (synthesize, candidates,
decisions-with-refine) had no readiness check: an Azure key with no endpoint or
deployment raised ``ValueError`` inside ``LLMClient`` and came back as a bare 500
naming nothing. They now share AutoCode's keyed check (``require_provider_callable``)
and answer with the same refusal shape, ``{"detail", "reason"}``.
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from bristlenose.config import BristlenoseSettings
from bristlenose.server.models import QuoteTag
from tests.test_codebook_builder import (
    _patch_llm,
    _synth_result,
    client_with_coded_tag,  # noqa: F401  (fixture)
)

ROUTES = Path(__file__).parents[1] / "bristlenose/server/routes/codebook_builder.py"

_AZURE_NO_ENDPOINT = {"llm_provider": "azure", "azure_api_key": "k", "azure_deployment": "d"}
_AZURE_NO_DEPLOYMENT = {"llm_provider": "azure", "azure_api_key": "k",
                        "azure_endpoint": "https://r.openai.azure.com"}
_NO_KEY = {"llm_provider": "anthropic", "anthropic_api_key": ""}


def _seed_prompt(client, tag_id: int) -> None:
    with _patch_llm(AsyncMock(return_value=_synth_result())):
        resp = client.post(f"/api/projects/1/codebook/tags/{tag_id}/builder/synthesize")
    assert resp.status_code == 200


def _call(client, tag_id: int, route: str):
    base = f"/api/projects/1/codebook/tags/{tag_id}/builder"
    if route == "synthesize":
        return client.post(f"{base}/synthesize")
    if route == "candidates":
        return client.post(f"{base}/candidates", json={"min_confidence": 0.5})
    return client.post(f"{base}/decisions", json={"decisions": [], "refine": True})


@pytest.mark.parametrize("route", ["synthesize", "candidates", "decisions"])
@pytest.mark.parametrize(
    ("fields", "reason"),
    [(_AZURE_NO_ENDPOINT, "provider_ambiguous"), (_AZURE_NO_DEPLOYMENT, "provider_ambiguous"),
     (_NO_KEY, "no_api_key")],
)
def test_an_unready_provider_is_refused_not_a_500(client_with_coded_tag, route, fields, reason) -> None:  # noqa: F811
    client, tag_id = client_with_coded_tag
    _seed_prompt(client, tag_id)  # candidates and refine need a prompt to exist
    client.app.state.settings = BristlenoseSettings(**fields)
    llm = AsyncMock(return_value=_synth_result())
    with _patch_llm(llm):
        resp = _call(client, tag_id, route)
    assert resp.status_code == 503, resp.text
    assert resp.json()["reason"] == reason
    llm.assert_not_called()


def test_a_refused_refine_records_nothing(client_with_coded_tag) -> None:  # noqa: F811
    # The check runs before the decisions are written: a refusal must not leave
    # tags applied behind an answer that says the request failed.
    client, tag_id = client_with_coded_tag
    _seed_prompt(client, tag_id)
    db = client.app.state.db_factory()
    try:
        before = db.query(QuoteTag).filter_by(tag_definition_id=tag_id).count()
        coded = {r[0] for r in db.query(QuoteTag.quote_id).filter_by(tag_definition_id=tag_id)}
        from bristlenose.server.models import Quote
        from bristlenose.server.routes.data import _quote_dom_id

        uncoded = next(q for q in db.query(Quote).filter_by(project_id=1) if q.id not in coded)
        dom = _quote_dom_id(uncoded)
    finally:
        db.close()
    client.app.state.settings = BristlenoseSettings(**_AZURE_NO_ENDPOINT)
    resp = client.post(
        f"/api/projects/1/codebook/tags/{tag_id}/builder/decisions",
        json={"decisions": [{"quote_id": dom, "decision": "accept", "reason": "r"}], "refine": True},
    )
    assert resp.status_code == 503
    db = client.app.state.db_factory()
    try:
        assert db.query(QuoteTag).filter_by(tag_definition_id=tag_id).count() == before
    finally:
        db.close()


def test_a_local_model_is_not_refused(client_with_coded_tag) -> None:  # noqa: F811
    # AutoCode refuses local models (context window); the builder never did.
    client, tag_id = client_with_coded_tag
    client.app.state.settings = BristlenoseSettings(llm_provider="local")
    with _patch_llm(AsyncMock(return_value=_synth_result())):
        resp = client.post(f"/api/projects/1/codebook/tags/{tag_id}/builder/synthesize")
    assert resp.status_code == 200


def test_every_route_that_awaits_the_engine_is_guarded() -> None:
    # A new builder route that calls the model without the check would be a 500 again.
    tree = ast.parse(ROUTES.read_text(encoding="utf-8"))
    awaiting = []
    for fn in tree.body:
        if not isinstance(fn, ast.AsyncFunctionDef):
            continue
        calls_engine = any(
            isinstance(n, ast.Await) and isinstance(n.value, ast.Call)
            and isinstance(n.value.func, ast.Attribute)
            and isinstance(n.value.func.value, ast.Name) and n.value.func.value.id == "cb"
            for n in ast.walk(fn)
        )
        if not calls_engine:
            continue
        awaiting.append(fn.name)
        guarded = any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "require_provider_callable"
            for n in ast.walk(fn)
        )
        assert guarded, f"{fn.name} awaits the builder engine without require_provider_callable"
    assert len(awaiting) == 3, awaiting


def test_decisions_with_no_prompt_yet_are_not_refused(client_with_coded_tag) -> None:  # noqa: F811
    # refine defaults to true, but with no prompt row the route returns before any
    # model call, so an unready provider must not block recording the decisions
    # (code review, 19 Nov 2026).
    client, tag_id = client_with_coded_tag
    client.app.state.settings = BristlenoseSettings(**_AZURE_NO_ENDPOINT)
    resp = client.post(
        f"/api/projects/1/codebook/tags/{tag_id}/builder/decisions", json={"decisions": []},
    )
    assert resp.status_code == 200, resp.text


def test_two_keys_and_no_choice_is_refused_not_billed_to_a_default(client_with_coded_tag, monkeypatch) -> None:  # noqa: F811
    # With two providers keyed and none chosen, the field default ("anthropic") would be
    # billed for a vendor nobody picked; AutoCode refuses this with 409 and so does the
    # builder (silent-failure review, 19 Nov 2026).
    from bristlenose.config import ProviderResolution

    client, tag_id = client_with_coded_tag
    client.app.state.settings = BristlenoseSettings(
        llm_provider="anthropic", anthropic_api_key="k1", openai_api_key="k2")
    monkeypatch.setattr(
        "bristlenose.config.provider_resolution_for",
        lambda _s: ProviderResolution(status="ambiguous", provider="anthropic", configured=("anthropic", "openai"), source=""),
    )
    llm = AsyncMock(return_value=_synth_result())
    with _patch_llm(llm):
        resp = client.post(f"/api/projects/1/codebook/tags/{tag_id}/builder/synthesize")
    assert resp.status_code == 409, resp.text
    assert resp.json()["reason"] == "provider_ambiguous"
    llm.assert_not_called()
