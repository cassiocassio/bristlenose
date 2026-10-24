"""The local (Ollama) path asks for the schema and retries with what was wrong (RE#R105).

Measured 24 Oct 2026 on Ollama 0.20.7: llama3.2:3b, the default local model,
finished 0 of 13 runs cleanly. Asked for plain JSON with the schema pasted in
the prompt, it answered with the schema itself; the retry resent the identical
request and got the identical echo, rescuing 2 of 32 calls. Ollama's own schema
mode (``response_format: json_schema``) fixed every replayed failure, and a
retry that names the bad fields fixed most of the rest.

The HTTP layer is mocked (``client._local_client``), so these are free and
need no Ollama.
"""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import openai
import pytest

from bristlenose.config import BristlenoseSettings
from bristlenose.llm import telemetry
from bristlenose.llm.client import LLMClient
from bristlenose.llm.structured import QuoteExtractionResult

# Short on purpose: pydantic abbreviates a long input_value, so a long one
# would pass with the leak still in place (bristlenose/llm/CLAUDE.md).
NEEDLE = "needle-pz"

GOOD = json.dumps({"quotes": []})


def _settings() -> BristlenoseSettings:
    return BristlenoseSettings(
        llm_provider="local", local_model="llama3.2:3b", llm_max_tokens=8192,
        llm_temperature=0.1,
    )


def _reply(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=50, completion_tokens=10),
        model="llama3.2:3b",
    )


def _client(*replies: object) -> tuple[LLMClient, AsyncMock]:
    client = LLMClient(_settings())
    create = AsyncMock(side_effect=list(replies))
    client._local_client = SimpleNamespace(  # type: ignore[assignment]
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
    )
    return client, create


def _bad_request(message: str) -> openai.BadRequestError:
    body = {"error": {"message": message}}
    response = httpx.Response(400, request=httpx.Request("POST", "http://localhost:11434/v1"))
    return openai.BadRequestError(f"Error code: 400 - {body}", response=response, body=body)


async def _analyze(client: LLMClient) -> QuoteExtractionResult:
    return await client.analyze(
        system_prompt="sys", user_prompt="usr", response_model=QuoteExtractionResult,
    )


def _sent(create: AsyncMock, n: int) -> dict:
    return create.await_args_list[n].kwargs


@pytest.mark.asyncio
async def test_the_request_carries_the_schema() -> None:
    client, create = _client(_reply(GOOD))
    await _analyze(client)
    assert _sent(create, 0)["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "QuoteExtractionResult",
            # The plain schema, $defs and all: Ollama takes it as it is, and
            # openai_strict_schema's rewrites are OpenAI's strict mode, not Ollama's.
            "schema": QuoteExtractionResult.model_json_schema(),
        },
    }


@pytest.mark.asyncio
async def test_a_refused_schema_falls_back_to_plain_json_once_and_remembers(
    tmp_path, caplog,
) -> None:
    refusal = _bad_request("response_format type json_schema is not supported")
    client, create = _client(refusal, _reply(GOOD), _reply(GOOD))
    run_dir = tmp_path / ".bristlenose"
    tokens = telemetry.set_run_context("run-local-fallback", run_dir)
    try:
        with telemetry.stage("s09_quote_extraction"), caplog.at_level(logging.WARNING):
            await _analyze(client)
            await _analyze(client)
    finally:
        telemetry.reset_run_context(tokens)

    formats = [c.kwargs["response_format"]["type"] for c in create.await_args_list]
    # The refusal is resent at once as plain JSON, and the next call starts there.
    assert formats == ["json_schema", "json_object", "json_object"]
    assert "local_json_schema_refused" in caplog.text
    rows = list(telemetry.iter_rows(run_dir))
    assert [(r["outcome"], r["retry_count"]) for r in rows] == [("ok", 0), ("ok", 0)]


@pytest.mark.asyncio
async def test_a_400_about_something_else_is_not_a_refusal() -> None:
    client, create = _client(_bad_request("model 'llama3.2:3b' not found"))
    with pytest.raises(openai.BadRequestError):
        await _analyze(client)
    assert create.await_count == 1


@pytest.mark.asyncio
async def test_the_retry_says_what_was_wrong_instead_of_asking_again() -> None:
    echoed_schema = json.dumps(QuoteExtractionResult.model_json_schema())
    client, create = _client(_reply(echoed_schema), _reply(GOOD))
    result = await _analyze(client)
    assert result.quotes == []

    first, second = _sent(create, 0)["messages"], _sent(create, 1)["messages"]
    assert second != first, "the retry resent the identical request"
    # The same conversation, plus one turn that names the bad field. Never the
    # model's reply: it goes nowhere but back to the model, and a long one would
    # push the system prompt out of a small context window.
    assert second[: len(first)] == first
    assert len(second) == len(first) + 1
    turn = second[-1]
    assert turn["role"] == "user"
    assert "quotes (missing)" in turn["content"]
    assert "$defs" not in turn["content"]


@pytest.mark.asyncio
async def test_each_retry_is_built_from_the_first_request_not_stacked() -> None:
    bad = json.dumps({"quotes": [{"text": NEEDLE}]})
    client, create = _client(_reply(bad), _reply(bad), _reply(GOOD))
    await _analyze(client)
    first = _sent(create, 0)["messages"]
    assert [len(c.kwargs["messages"]) for c in create.await_args_list] == [
        len(first), len(first) + 1, len(first) + 1,
    ]


@pytest.mark.asyncio
async def test_a_reply_that_is_not_json_is_named_by_position_not_content() -> None:
    client, create = _client(_reply(f"Sure! {NEEDLE} said hello"), _reply(GOOD))
    await _analyze(client)
    turn = _sent(create, 1)["messages"][-1]["content"]
    assert "Expecting value" in turn
    assert NEEDLE not in turn


@pytest.mark.asyncio
async def test_the_failure_names_fields_never_the_reply(caplog) -> None:
    # A reply quoting the participant, three times: it must not reach the
    # error (terminal, log, stage error list), the DEBUG log or the retry turns.
    bad = json.dumps({"quotes": [{"text": NEEDLE}]})
    client, create = _client(_reply(bad), _reply(bad), _reply(bad))
    with caplog.at_level(logging.DEBUG), pytest.raises(RuntimeError) as raised:
        await _analyze(client)

    message = str(raised.value)
    assert message.startswith("Local model failed to produce valid JSON after 3 attempts.")
    assert "quotes.0.start_timecode (missing)" in message
    assert NEEDLE not in message
    assert NEEDLE not in caplog.text
    for call in create.await_args_list[1:]:
        assert NEEDLE not in call.kwargs["messages"][-1]["content"]
