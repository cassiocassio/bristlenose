"""A provider's own words live in the SDK error's body, not always its message.

openai 3.26 built ``str(exc)`` as "Error code: 404 - {body}"; 3.60 builds
"Error code: 404" alone and keeps the words in ``exc.body`` (a string when the
envelope's ``error`` is one, as Ollama's is). CI, which installs the newest
SDK, failed nine Ollama tests on 28 Nov 2026 while this venv's 3.26 passed
them. These tests build the 3.60 shape directly, so they hold on either SDK.
"""

from __future__ import annotations

import httpx
import openai

from bristlenose.llm import client
from bristlenose.llm.failure_classifier import LLMFailureKind, classify_exception, sdk_error_text

_REQ = httpx.Request("POST", "http://localhost:11434/api/chat")


def _sdk_360(cls: type[openai.APIStatusError], status: int, body: object) -> openai.APIStatusError:
    """An error as openai 3.60 builds it from a response: the status alone in the message."""
    return cls(f"Error code: {status}", response=httpx.Response(status, request=_REQ), body=body)


def test_the_body_words_are_read_when_the_message_lacks_them() -> None:
    err = _sdk_360(openai.NotFoundError, 404, "model 'gemma4:e4b' not found")
    assert str(err) == "Error code: 404"
    assert "model 'gemma4:e4b' not found" in sdk_error_text(err)


def test_a_dict_body_gives_its_message_and_an_old_style_message_is_not_doubled() -> None:
    err = _sdk_360(openai.BadRequestError, 400, {"error": {"message": "max_tokens is too large"}})
    assert sdk_error_text(err).endswith("max_tokens is too large")
    old = openai.NotFoundError(
        "Error code: 404 - model 'x' not found", response=httpx.Response(404, request=_REQ),
        body="model 'x' not found",
    )
    assert sdk_error_text(old).count("not found") == 1


def test_ollama_model_not_found_is_classified_on_the_newer_sdk() -> None:
    err = _sdk_360(openai.NotFoundError, 404, "model 'gemma4:e4b' not found, try pulling it first")
    assert classify_exception("local", err) is LLMFailureKind.MODEL_UNAVAILABLE


def test_the_mlx_501_and_the_window_400_are_recognised_on_the_newer_sdk() -> None:
    refused = _sdk_360(
        openai.InternalServerError, 501, "structured output is unavailable for this model"
    )
    assert client._refuses_structured_output(refused) is True
    over = _sdk_360(
        openai.BadRequestError, 400, "the prompt is longer than the context length (40000 > 32768)"
    )
    assert client._prompt_exceeds_window(over) is True
