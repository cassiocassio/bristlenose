"""Ollama is asked on its native /api/chat: the window, thinking off, and the MLX refusal (27 Nov 2026).

Measured on Ollama 0.40.18 (docs/research/local-models-2026-11.md):

- The client sent no context size, so Ollama picked one from GPU memory: 4,096 tokens on
  Macs with 16 GB or less. A 60-minute transcript is 9–14k tokens, and the GGUF runner kept
  its last ~2,000 and answered 200. Only the native API takes ``options.num_ctx``.
- On a Mac, ``gemma4:e4b`` arrives as an MLX build whose runner answers any structured-output
  request with 501 "structured output is unavailable", so the analysis ended in 8 seconds.

The wire is real: an ``httpx.MockTransport`` behind the openai SDK's client, so the body is
what Ollama would receive and an error status is the SDK's own exception. No Ollama needed.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import openai
import pytest

from bristlenose.config import BristlenoseSettings
from bristlenose.llm import telemetry
from bristlenose.llm.client import LLMClient, TruncatedResponseError
from bristlenose.llm.structured import QuoteExtractionResult
from bristlenose.ollama import ollama_root
from bristlenose.preflight.api_key import _validate_local

GOOD = json.dumps({"quotes": []})
REFUSAL = {"error": "structured output is unavailable"}


def _settings() -> BristlenoseSettings:
    return BristlenoseSettings(
        llm_provider="local", local_model="gemma4:e4b", llm_max_tokens=8192,
        llm_temperature=0.1,
    )


def _answer(content: str, done_reason: str = "stop") -> httpx.Response:
    return httpx.Response(200, json={
        "model": "gemma4:e4b", "message": {"role": "assistant", "content": content},
        "done": True, "done_reason": done_reason, "prompt_eval_count": 50, "eval_count": 10,
    })


Handler = Callable[[dict], httpx.Response]


def _client(
    chat: Handler, version: httpx.Response | None = None, retries: int = 0,
) -> tuple[LLMClient, list[dict]]:
    """A client whose Ollama answers ``/api/version`` with ``version`` and ``/api/chat`` with ``chat``.

    ``retries`` 0 by default, so a test counts the requests it caused; production
    keeps the SDK's 2 (test_the_refusal_survives_the_sdks_own_retries).
    """
    sent: list[dict] = []

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/version":
            return version or httpx.Response(200, json={"version": "0.40.18"})
        assert request.url.path == "/api/chat", request.url
        body = json.loads(request.content)
        sent.append(body)
        return chat(body)

    client = LLMClient(_settings())
    client._ollama_client = openai.AsyncOpenAI(
        base_url="http://localhost:11434", api_key="ollama", max_retries=retries,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)),
    )
    return client, sent


async def _analyze(client: LLMClient) -> QuoteExtractionResult:
    return await client.analyze(
        system_prompt="sys", user_prompt="usr", response_model=QuoteExtractionResult,
    )


# --- 1. The context window --------------------------------------------------------------


@pytest.mark.asyncio
async def test_ollama_is_asked_for_a_32k_window_and_no_silent_truncation() -> None:
    client, sent = _client(lambda body: _answer(GOOD))
    await _analyze(client)
    body = sent[0]
    assert body["options"] == {"num_ctx": 32768, "num_predict": 8192, "temperature": 0.1}
    # Off, so a prompt over the window is refused rather than cut to its tail, and an
    # answer that fills it ends "length" rather than shifting the prompt out.
    assert body["truncate"] is False
    assert body["shift"] is False
    assert body["stream"] is False
    assert body["format"] == QuoteExtractionResult.model_json_schema()
    assert body["model"] == "gemma4:e4b"


def test_the_native_api_is_at_local_urls_root() -> None:
    assert ollama_root("http://localhost:11434/v1") == "http://localhost:11434"
    assert ollama_root("http://192.168.1.20:11434/v1/") == "http://192.168.1.20:11434"
    client = LLMClient(_settings())
    assert str(client._ensure_ollama_client().base_url).rstrip("/") == "http://localhost:11434"


@pytest.mark.asyncio
async def test_an_answer_that_fills_the_window_is_a_truncation_that_names_it() -> None:
    client, _ = _client(lambda body: _answer('{"quotes": [', done_reason="length"))
    with pytest.raises(TruncatedResponseError, match="context=32768"):
        await _analyze(client)


@pytest.mark.asyncio
async def test_a_prompt_over_the_window_is_a_truncation_not_an_answer(tmp_path) -> None:
    # Ollama's GGUF runner with truncate: false (llm/llama_server.go, v0.40.18). Before
    # 27 Nov 2026 it kept the prompt's tail and answered 200; now it says so, and a
    # truncation is what quote extraction splits the session on.
    too_long = {"error": "the prompt is longer than the context length currently available "
                         "to the model; shorten the prompt, adjust the context length in "
                         "settings, or use a model with a longer context length"}
    client, sent = _client(lambda body: httpx.Response(400, json=too_long))
    run_dir = tmp_path / ".bristlenose"
    tokens = telemetry.set_run_context("run-over-window", run_dir)
    try:
        with telemetry.stage("s09_quote_extraction"), pytest.raises(
            TruncatedResponseError, match="context window.*context=32768",
        ):
            await _analyze(client)
    finally:
        telemetry.reset_run_context(tokens)
    assert len(sent) == 1, "neither resent nor retried"
    assert [r["outcome"] for r in telemetry.iter_rows(run_dir)] == ["truncated"]


@pytest.mark.asyncio
async def test_any_other_400_is_not_a_full_window() -> None:
    client, _ = _client(lambda body: httpx.Response(400, json={"error": "invalid options"}))
    with pytest.raises(openai.BadRequestError):
        await _analyze(client)


# --- 2. The MLX runner's refusal ---------------------------------------------------------


@pytest.mark.asyncio
async def test_the_mlx_refusal_is_asked_again_in_plain_text_once_and_remembered(
    tmp_path, caplog,
) -> None:
    def chat(body: dict) -> httpx.Response:
        if "format" in body:
            return httpx.Response(501, json=REFUSAL)
        # No grammar: the model may say something around the JSON.
        return _answer(f"Here is the JSON:\n```json\n{GOOD}\n```\nDone.")

    client, sent = _client(chat)
    run_dir = tmp_path / ".bristlenose"
    tokens = telemetry.set_run_context("run-mlx-plain", run_dir)
    try:
        with telemetry.stage("s09_quote_extraction"), caplog.at_level(logging.WARNING):
            first = await _analyze(client)
            await _analyze(client)
    finally:
        telemetry.reset_run_context(tokens)

    assert first == QuoteExtractionResult(quotes=[])
    assert ["format" in b for b in sent] == [True, False, False]
    # The schema still reaches the model, in the system prompt.
    assert "matching this schema" in sent[1]["messages"][0]["content"]
    assert "local_structured_output_refused" in caplog.text
    rows = list(telemetry.iter_rows(run_dir))
    assert [(r["outcome"], r["retry_count"]) for r in rows] == [("ok", 0), ("ok", 0)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "error"),
    [(501, "not implemented"), (500, "structured output is unavailable"),
     (503, "server busy")],
    ids=["501-other-words", "500-same-words", "503"],
)
async def test_only_that_501_is_a_refusal(status: int, error: str) -> None:
    client, sent = _client(lambda body: httpx.Response(status, json={"error": error}))
    with pytest.raises(openai.APIStatusError):
        await _analyze(client)
    assert len(sent) == 1
    assert client._local_plain is False


@pytest.mark.asyncio
async def test_three_first_calls_at_once_all_fall_back() -> None:
    # llm_concurrency is 3: all three first calls go out with a format before any 501
    # comes back, so the second and third refusals arrive after the first has set the flag.
    client, sent = _client(
        lambda body: httpx.Response(501, json=REFUSAL) if "format" in body else _answer(GOOD),
    )
    real_post = client._ollama_client.post  # type: ignore[union-attr]
    in_flight: list[None] = []
    all_sent = asyncio.Event()

    async def post(*args, **kwargs):  # type: ignore[no-untyped-def]
        if "format" in kwargs["body"]:
            in_flight.append(None)
            if len(in_flight) == 3:
                all_sent.set()
            await all_sent.wait()
        return await real_post(*args, **kwargs)

    client._ollama_client.post = post  # type: ignore[method-assign,union-attr]
    results = await asyncio.wait_for(
        asyncio.gather(*(_analyze(client) for _ in range(3))), timeout=5,
    )
    assert results == [QuoteExtractionResult(quotes=[])] * 3
    assert ["format" in b for b in sent].count(True) == 3
    assert ["format" in b for b in sent].count(False) == 3


@pytest.mark.asyncio
async def test_the_refusal_survives_the_sdks_own_retries() -> None:
    # The client the run builds keeps the SDK's max_retries (2), which retries any 5xx:
    # the 501 is sent three times before the fallback sees it, once per client.
    def chat(body: dict) -> httpx.Response:
        return httpx.Response(501, json=REFUSAL) if "format" in body else _answer(GOOD)

    client, sent = _client(chat, retries=2)
    assert await _analyze(client) == QuoteExtractionResult(quotes=[])
    assert ["format" in b for b in sent] == [True, True, True, False]


@pytest.mark.asyncio
async def test_a_plain_reply_that_does_not_parse_is_retried_with_what_was_wrong() -> None:
    replies = iter([httpx.Response(501, json=REFUSAL), _answer("I could not do that."),
                    _answer(GOOD)])
    client, sent = _client(lambda body: next(replies))
    assert await _analyze(client) == QuoteExtractionResult(quotes=[])
    assert len(sent) == 3
    assert "did not match the schema" in sent[2]["messages"][-1]["content"]


# --- 3. Thinking off ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_thinking_is_off() -> None:
    # Ollama maps /v1's reasoning_effort "none" to this (openai/openai.go); a model that
    # cannot think accepts false (server/routes.go refuses only true).
    client, sent = _client(lambda body: _answer(GOOD))
    await _analyze(client)
    assert sent[0]["think"] is False


# --- Which API: Ollama, or another OpenAI-compatible server ------------------------------


@pytest.mark.asyncio
async def test_a_server_that_is_not_ollama_keeps_the_v1_request() -> None:
    client, sent = _client(lambda body: _answer(GOOD),
                           version=httpx.Response(404, json={"error": "Unexpected endpoint"}))
    reply = SimpleNamespace(
        choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=GOOD))],
        usage=SimpleNamespace(prompt_tokens=50, completion_tokens=10), model="x",
    )
    create = AsyncMock(return_value=reply)
    client._local_client = SimpleNamespace(  # type: ignore[assignment]
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
    )
    await _analyze(client)
    await _analyze(client)
    assert sent == []
    assert client._local_native is False
    kwargs = create.await_args_list[0].kwargs
    # Exactly the request it got before: no window, no thinking switch.
    assert set(kwargs) == {"model", "max_tokens", "temperature", "response_format", "messages"}
    assert kwargs["response_format"]["type"] == "json_schema"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [500, 401, 503])
async def test_a_probe_that_fails_otherwise_is_the_calls_error_and_not_remembered(
    status: int,
) -> None:
    # Remembering it would send the run to /v1 at Ollama's own small window.
    client, sent = _client(lambda body: _answer(GOOD),
                           version=httpx.Response(status, json={"error": "no"}))
    with pytest.raises(openai.APIStatusError):
        await _analyze(client)
    assert client._local_native is None
    assert sent == []


@pytest.mark.asyncio
async def test_ollama_down_is_a_connection_error_and_is_asked_again_next_time() -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused", request=request)

    client = LLMClient(_settings())
    client._ollama_client = openai.AsyncOpenAI(
        base_url="http://localhost:11434", api_key="ollama", max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(down)),
    )
    with pytest.raises(openai.APIConnectionError):
        await _analyze(client)
    assert client._local_native is None


# --- The preflight sends the run's request ----------------------------------------------


def _patch_sync_openai(monkeypatch, handle: Callable[[httpx.Request], httpx.Response]) -> None:
    real = openai.OpenAI

    def make(**kw):  # type: ignore[no-untyped-def]
        return real(**kw, max_retries=0,
                    http_client=httpx.Client(transport=httpx.MockTransport(handle)))

    monkeypatch.setattr(openai, "OpenAI", make)


def test_the_preflight_loads_the_model_at_the_runs_window(monkeypatch) -> None:
    sent: list[dict] = []

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.40.18"})
        assert request.url.path == "/api/chat"
        sent.append(json.loads(request.content))
        return _answer("ok")

    _patch_sync_openai(monkeypatch, handle)
    assert _validate_local("http://localhost:11434/v1", "gemma4:e4b").ok
    assert sent[0]["options"]["num_ctx"] == 32768
    assert sent[0]["options"]["num_predict"] == 1
    assert "format" not in sent[0]


def test_the_preflight_names_a_model_ollama_does_not_have(monkeypatch) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.40.18"})
        return httpx.Response(404, json={"error": "model 'gemma4:e4b' not found"})

    _patch_sync_openai(monkeypatch, handle)
    result = _validate_local("http://localhost:11434/v1", "gemma4:e4b")
    assert (result.ok, result.error_class) == (False, "model_unavailable")


# --- Reading past what a model writes around the JSON -----------------------------------

ONE_QUOTE = {"quotes": [{"verbatim_excerpt": "it was fine", "start_timecode": 1.0}]}


@pytest.mark.parametrize(
    "reply",
    [
        # Gemma 4 12B and up emit an empty thought block with thinking off (model card).
        "<|channel>thought\n<channel|>" + GOOD,
        "<|channel>thought\n<channel|>\n```json\n" + GOOD + "\n```",
        "```json\n" + GOOD + "\n```",
        "Here is the JSON you asked for:\n\n" + GOOD + "\n\nLet me know if you need more.",
    ],
    ids=["thought-block", "thought-block-then-fence", "fence", "prose-around"],
)
def test_a_reply_is_read_past_a_preamble_and_a_fence(reply: str) -> None:
    from bristlenose.llm.client import _local_json

    assert _local_json(reply) == json.loads(GOOD)


def test_a_broken_outer_object_is_a_bad_reply_not_its_first_quote() -> None:
    # Reading from each "{" in turn would return the quote inside as the answer.
    from bristlenose.llm.client import _local_json

    broken = 'Sure: {"quotes": [' + json.dumps(ONE_QUOTE["quotes"][0]) + ", {"
    with pytest.raises(json.JSONDecodeError):
        _local_json(broken)


@pytest.mark.asyncio
async def test_the_fallbacks_reply_is_validated_after_its_preamble() -> None:
    def chat(body: dict) -> httpx.Response:
        if "format" in body:
            return httpx.Response(501, json=REFUSAL)
        return _answer("<|channel>thought\n<channel|>```json\n" + GOOD + "\n```")

    client, sent = _client(chat)
    assert await _analyze(client) == QuoteExtractionResult(quotes=[])
    assert len(sent) == 2, "read on the first plain reply, no retry"


# --- Values outside an enum, with no grammar ---------------------------------------------


def _labels(*kinds: str) -> str:
    return json.dumps({"labels": [
        {"turn_id": f"s1-t{i}", "kind": k} for i, k in enumerate(kinds)
    ]})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kinds", "kept"),
    [(("new", "chat", "core"), ["s1-t0", "s1-t1"]), (("core", "core", "new"), None)],
    ids=["one-label-out-of-three", "most-labels-out"],
)
async def test_a_kind_outside_the_enum_costs_that_turn_never_its_meaning(
    kinds: tuple[str, ...], kept: list[str] | None, caplog,
) -> None:
    # Measured 27 Nov 2026 on gemma4:e4b without a grammar: it wrote the `role` value
    # "core" into `kind` on every attempt, and one such label in 29 (or 64) failed the
    # whole session. "core" means no kind, so it is never mapped onto one: each
    # attempt is a validation failure, and the last keeps the labels that validate
    # (the turn left out reads "unclassified" in the record), or, when most are
    # wrong, fails as before.
    from bristlenose.discussion.models import SessionLabelsOut

    def chat(body: dict) -> httpx.Response:
        if "format" in body:
            return httpx.Response(501, json=REFUSAL)
        return _answer(_labels(*kinds))

    client, sent = _client(chat)

    async def classify() -> SessionLabelsOut:
        return await client.analyze(
            system_prompt="sys", user_prompt="usr", response_model=SessionLabelsOut,
        )

    with caplog.at_level(logging.WARNING):
        if kept is None:
            with pytest.raises(RuntimeError, match="after 3 attempts"):
                await classify()
        else:
            result = await classify()
            assert [lb.turn_id for lb in result.labels] == kept
            assert result._dropped_items == 1
            assert "repair=dropped 1 of 3 items | fields=kind" in caplog.text
    assert ["format" in b for b in sent] == [True, False, False, False]
