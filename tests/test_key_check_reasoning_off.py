"""The ChatGPT key check asks the model not to reason (N34, owner call 9 Nov 2026).

The check sends the run's own request with the prompt ``.``. For a GPT-5-class model that request
carried no ``reasoning_effort``, so the model reasoned by default and the output was capped only by
``max_completion_tokens`` (64,000): a worst case of about 64,000 billed tokens for a "~$0.0001" check.
Now the check sends ``reasoning_effort`` ``"none"``, then ``"minimal"`` if the model refuses the first,
then none at all if it refuses both (the same refusal-and-resend the any-llm route uses), and remembers
nothing: it is one call at setup. Only the KEY CHECK changes; the run's own requests are not touched,
because that would change quote extraction and wants a measurement first.

The fake client records the keyword arguments of every request, so the request SHAPE is what is
asserted (a bare mock accepts any keyword, which is how the shape went unseen on 4 Sep 2026).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import httpx
import openai
import pytest

from bristlenose.preflight.api_key import _validate_openai

_MODEL = "gpt-5.6-terra"


def _bad_request(param: str | None, message: str) -> openai.BadRequestError:
    body: dict[str, Any] = {"error": {"message": message, "param": param}}
    response = httpx.Response(400, request=httpx.Request("POST", "https://api.openai.com/v1"))
    return openai.BadRequestError(f"Error code: 400 - {body}", response=response, body=body)


def _auth_error() -> openai.AuthenticationError:
    response = httpx.Response(401, request=httpx.Request("POST", "https://api.openai.com/v1"))
    return openai.AuthenticationError("Error code: 401", response=response, body=None)


@pytest.fixture
def fake_openai(monkeypatch):
    """A fake openai.OpenAI whose create() plays a script of outcomes and records each request."""
    calls: list[dict[str, Any]] = []
    script: list[Any] = []

    def create(**kwargs: Any) -> Any:
        calls.append(kwargs)
        outcome = script.pop(0) if script else SimpleNamespace(ok=True)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    class _Client:
        def __init__(self, **_: Any) -> None:
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))

    monkeypatch.setattr(openai, "OpenAI", _Client)
    return calls, script


def _refuses(value: str) -> openai.BadRequestError:
    return _bad_request("reasoning_effort", f"Unsupported value: '{value}' is not supported with this model.")


def test_a_gpt5_class_check_asks_for_no_reasoning(fake_openai) -> None:
    calls, _ = fake_openai
    assert _validate_openai("sk-key", _MODEL).ok
    assert len(calls) == 1
    assert calls[0]["reasoning_effort"] == "none"
    assert calls[0]["max_completion_tokens"] > 1, "the run's own cap is still what is sent"


def test_a_model_that_refuses_none_is_asked_for_minimal(fake_openai) -> None:
    calls, script = fake_openai
    script.append(_refuses("none"))
    assert _validate_openai("sk-key", _MODEL).ok
    assert [c.get("reasoning_effort") for c in calls] == ["none", "minimal"]


def test_a_model_that_refuses_both_is_asked_with_its_own_default(fake_openai) -> None:
    calls, script = fake_openai
    script.extend([_refuses("none"), _refuses("minimal")])
    assert _validate_openai("sk-key", _MODEL).ok
    assert [c.get("reasoning_effort", "absent") for c in calls] == ["none", "minimal", "absent"]


def test_a_legacy_model_is_never_sent_reasoning_effort(fake_openai) -> None:
    calls, _ = fake_openai
    assert _validate_openai("sk-key", "gpt-4o-mini").ok
    assert len(calls) == 1 and "reasoning_effort" not in calls[0]


def test_a_refusal_that_is_not_about_reasoning_is_not_retried(fake_openai) -> None:
    calls, script = fake_openai
    script.append(_bad_request("max_completion_tokens", "max_completion_tokens is too large"))
    result = _validate_openai("sk-key", _MODEL)
    assert not result.ok
    assert len(calls) == 1, "a different 400 must not be mistaken for the reasoning refusal"


def test_a_rejected_key_is_reported_on_the_first_call(fake_openai) -> None:
    calls, script = fake_openai
    script.append(_auth_error())
    result = _validate_openai("sk-key", _MODEL)
    assert not result.ok and result.error_class == "invalid_key"
    assert len(calls) == 1, "a bad key must not be tried again with another effort"


def test_the_caller_s_params_are_not_changed(fake_openai) -> None:
    calls, _ = fake_openai
    mine = {"max_completion_tokens": 123}
    _validate_openai("sk-key", _MODEL, params=mine)
    assert mine == {"max_completion_tokens": 123}
    assert calls[0]["max_completion_tokens"] == 123
