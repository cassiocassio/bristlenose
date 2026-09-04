"""OpenAI and Azure must use Structured Outputs, not JSON mode.

JSON mode guarantees only that the response *parses*; it matches the supplied
schema roughly 80% of the time. This path has no repair step — ``json.loads``
then ``model_validate`` is the first and only check — so every miss became a
``ValidationError`` that failed the run. Structured Outputs constrains decoding
and the shape is guaranteed.

These tests pin the request shape and the round trip, because the SDK is mocked
everywhere else and a mock accepts any ``response_format`` you hand it. The
change that added Structured Outputs passed 4362 existing tests without one of
them noticing.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bristlenose.config import BristlenoseSettings
from bristlenose.llm import structured as st
from bristlenose.llm.client import LLMClient
from bristlenose.llm.structured import (
    ExtractedQuoteItem,
    QuoteExtractionResult,
    drop_nulls,
    openai_strict_schema,
)


def _settings(provider: str) -> BristlenoseSettings:
    kw: dict[str, object] = {"llm_provider": provider, "llm_model": "gpt-4o"}
    if provider == "openai":
        kw["openai_api_key"] = "sk-test"
    else:
        kw |= {
            "azure_api_key": "az-test",
            "azure_endpoint": "https://example.openai.azure.com/",
            "azure_deployment": "my-deployment",
        }
    return BristlenoseSettings(**kw)  # type: ignore[arg-type]


async def _capture(provider: str, content: str) -> dict[str, object]:
    """Run one analyze() against a mocked SDK; return the create() kwargs."""
    client = LLMClient(_settings(provider))
    response = SimpleNamespace(
        choices=[SimpleNamespace(
            finish_reason="stop", message=SimpleNamespace(content=content),
        )],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
        model="gpt-4o",
    )
    mock = AsyncMock()
    mock.chat.completions.create = AsyncMock(return_value=response)
    if provider == "openai":
        client._openai_client = mock
    else:
        client._azure_client = mock
    await client.analyze(
        system_prompt="sys", user_prompt="usr",
        response_model=QuoteExtractionResult,
    )
    return dict(mock.chat.completions.create.await_args.kwargs)


class TestStrictSchema:
    def test_every_response_model_survives_the_rewrite(self) -> None:
        """Strict mode has two hard rules Pydantic does not satisfy: every
        object needs ``additionalProperties: false``, and every property must
        be in ``required``. A model that breaks either is rejected outright."""
        models = [
            getattr(st, n) for n in dir(st)
            if isinstance(getattr(st, n), type)
            and hasattr(getattr(st, n), "model_json_schema")
            and getattr(st, n).__module__ == st.__name__
        ]
        assert len(models) > 15, "found suspiciously few response models"

        def check(node: object, path: str = "$") -> list[str]:
            bad: list[str] = []
            if isinstance(node, dict):
                if "default" in node:
                    bad.append(f"{path}: `default` is not an accepted keyword")
                if "properties" in node:
                    if node.get("additionalProperties") is not False:
                        bad.append(f"{path}: additionalProperties must be false")
                    if set(node["properties"]) != set(node.get("required", [])):
                        bad.append(f"{path}: every property must be required")
                for k, v in node.items():
                    bad += check(v, f"{path}.{k}")
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    bad += check(v, f"{path}[{i}]")
            return bad

        for model in models:
            assert not check(openai_strict_schema(model)), model.__name__

    def test_defaulted_fields_become_nullable(self) -> None:
        """Forcing a defaulted field into ``required`` means the model must emit
        something; ``null`` is the honest something."""
        schema = openai_strict_schema(QuoteExtractionResult)
        item = schema["$defs"]["ExtractedQuoteItem"]["properties"]
        assert {"type": "null"} in item["verbatim_excerpt"]["anyOf"]
        # A field that was already required must NOT gain a null option.
        assert "anyOf" not in item["text"]


class TestNullRoundTrip:
    def test_nulls_resolve_to_pydantic_defaults(self) -> None:
        """The whole point of the round trip: a null comes back, is dropped,
        and Pydantic supplies the default it already had."""
        raw = {
            "start_timecode": "00:00:01", "end_timecode": "00:00:09",
            "text": "a quote", "topic_label": "onboarding",
            "quote_type": "pain_point",
            "verbatim_excerpt": None, "sentiment": None, "intensity": None,
        }
        item = ExtractedQuoteItem.model_validate(drop_nulls(raw))
        assert item.verbatim_excerpt == ""      # str default, not None
        assert item.sentiment is None           # str | None default
        assert item.intensity == 1              # int default

    def test_without_dropping_nulls_it_would_fail(self) -> None:
        """Proves the helper is load-bearing rather than decorative."""
        raw = {
            "start_timecode": "00:00:01", "end_timecode": "00:00:09",
            "text": "a quote", "topic_label": "onboarding",
            "quote_type": "pain_point", "verbatim_excerpt": None,
        }
        with pytest.raises(Exception):
            ExtractedQuoteItem.model_validate(raw)


class TestRequestShape:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("provider", ["openai", "azure"])
    async def test_sends_strict_json_schema(self, provider: str) -> None:
        kwargs = await _capture(provider, '{"quotes": []}')
        fmt = kwargs["response_format"]
        assert fmt["type"] == "json_schema", provider
        assert fmt["json_schema"]["strict"] is True, provider
        assert fmt["json_schema"]["name"] == "QuoteExtractionResult"
        assert fmt["json_schema"]["schema"]["additionalProperties"] is False

    @pytest.mark.asyncio
    async def test_null_bearing_response_still_validates(self) -> None:
        """End to end: a strict-mode response carrying nulls for defaulted
        fields must not fail the run."""
        content = (
            '{"quotes": [{"start_timecode": "00:00:01", '
            '"end_timecode": "00:00:09", "text": "t", "topic_label": "l", '
            '"quote_type": "pain_point", "verbatim_excerpt": null, '
            '"sentiment": null}]}'
        )
        kwargs = await _capture("openai", content)
        assert kwargs["response_format"]["type"] == "json_schema"
