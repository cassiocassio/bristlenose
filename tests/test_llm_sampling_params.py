"""Sampling parameters must only reach Claude models that accept them.

Anthropic removed ``temperature`` / ``top_p`` / ``top_k`` from Opus 4.7 and
Sonnet 5 onward: a non-default value is a **400**, not a silently-ignored
field. Bristlenose sends ``temperature=0.1`` (never the API default), so any
call to a post-4.6 Claude model fails outright — the researcher sees only
"The AI provider rejected the request." and has no route to the cause.

The Mac model picker already offers one such model (``claude-opus-4-8``), so
this is a live path, not a hypothetical one. These tests pin the request
*shape* — what actually reaches ``messages.create`` — rather than the contents
of the capability set, and they pin the picker against the client so adding a
model to one without teaching the other fails here instead of in a run.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import anthropic
import pytest
from anthropic.resources.messages import AsyncMessages

from bristlenose.config import BristlenoseSettings
from bristlenose.llm.client import _ANTHROPIC_ACCEPTS_SAMPLING, LLMClient
from bristlenose.llm.structured import QuoteExtractionResult

_SWIFT_PROVIDER = (
    Path(__file__).parent.parent / "desktop/Bristlenose/Bristlenose/LLMProvider.swift"
)


def _make_settings(model: str, temperature: float = 0.1) -> BristlenoseSettings:
    return BristlenoseSettings(  # type: ignore[arg-type]
        llm_provider="anthropic",
        anthropic_api_key="sk-ant-test-key",
        llm_model=model,
        llm_max_tokens=8192,
        llm_temperature=temperature,
    )


async def _capture_create_kwargs(model: str, temperature: float = 0.1) -> dict[str, object]:
    """Run one analyze() against a mocked SDK and return the create() kwargs."""
    client = LLMClient(_make_settings(model, temperature))
    mock_response = SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="tool_use", name="structured_output", input={"quotes": []})],
        usage=SimpleNamespace(input_tokens=100, output_tokens=5),
        model=model,
    )
    mock_anthropic = AsyncMock()
    mock_anthropic.messages.create = AsyncMock(return_value=mock_response)
    client._anthropic_client = mock_anthropic

    await client.analyze(
        system_prompt="sys",
        user_prompt="usr",
        response_model=QuoteExtractionResult,
    )
    return dict(mock_anthropic.messages.create.await_args.kwargs)


def _picker_claude_models() -> list[str]:
    """The Claude models the macOS picker offers, read from the Swift source."""
    src = _SWIFT_PROVIDER.read_text(encoding="utf-8")
    match = re.search(r"case \.claude:\s*\[([^\]]*)\]", src)
    assert match, f"could not find the .claude model list in {_SWIFT_PROVIDER}"
    models = re.findall(r'"([^"]+)"', match.group(1))
    # Guard against a parse that silently finds nothing — an empty list would
    # make every assertion below vacuously true.
    assert models, f"parsed zero Claude models from {_SWIFT_PROVIDER}"
    return models


class TestSamplingParamsByModel:
    @pytest.mark.asyncio
    async def test_rejecting_model_gets_no_temperature(self) -> None:
        """claude-opus-4-8 rejects sampling params with a 400 — don't send one."""
        kwargs = await _capture_create_kwargs("claude-opus-4-8")
        assert not kwargs["extra_body"]
        assert "temperature" not in kwargs
        assert "top_p" not in kwargs
        assert "top_k" not in kwargs

    @pytest.mark.asyncio
    async def test_unknown_model_gets_no_temperature(self) -> None:
        """Unknown models fail closed. Every future Claude model rejects sampling,
        so an omitted parameter (a working call at the API default) beats a 400."""
        kwargs = await _capture_create_kwargs("claude-sonnet-5")
        assert not kwargs["extra_body"]
        assert "temperature" not in kwargs

    @pytest.mark.asyncio
    async def test_accepting_model_still_gets_temperature(self) -> None:
        """The default model accepts it and is tuned to 0.1 — dropping the kwarg
        there would move it to the API default of 1.0 and silently retune every
        analysis, invalidating the Jul 2026 quote-stability baseline."""
        kwargs = await _capture_create_kwargs("claude-sonnet-4-6")
        assert kwargs["extra_body"] == {"temperature": 0.1}

    @pytest.mark.asyncio
    async def test_accepting_model_honours_a_custom_value(self) -> None:
        kwargs = await _capture_create_kwargs("claude-sonnet-4-6", temperature=0.7)
        assert kwargs["extra_body"] == {"temperature": 0.7}

    @pytest.mark.asyncio
    async def test_request_is_otherwise_unchanged(self) -> None:
        """Gating temperature must not disturb the rest of the request."""
        kwargs = await _capture_create_kwargs("claude-opus-4-8")
        assert kwargs["model"] == "claude-opus-4-8"
        assert kwargs["max_tokens"] == 8192
        assert kwargs["tool_choice"] == {"type": "tool", "name": "structured_output"}
        assert kwargs["timeout"] == 600.0
        assert kwargs["system"] == "sys"


class TestRequestMatchesInstalledSDK:
    """The gap Entry 6 was lost in: every other test here mocks
    ``messages.create``, and **a mock accepts any keyword argument**. 4246 tests
    passed against an ``anthropic`` major that had removed ``temperature`` and
    declared no ``**kwargs``, so every Claude call raised ``TypeError`` before
    reaching the network and nothing was red. This class asks the one question a
    mock cannot: does the *installed* SDK actually accept what we send?
    """

    @pytest.mark.asyncio
    async def test_every_kwarg_we_send_exists_on_the_installed_sdk(self) -> None:
        sig = inspect.signature(AsyncMessages.create)
        accepts_var_kwargs = any(
            param.kind is inspect.Parameter.VAR_KEYWORD for param in sig.parameters.values()
        )
        # A signature with **kwargs would swallow anything and make this test
        # vacuous — the whole point is that anthropic's does not have one.
        assert not accepts_var_kwargs, "messages.create grew **kwargs; this test is now vacuous"

        for model in ("claude-sonnet-4-6", "claude-opus-4-8"):
            kwargs = await _capture_create_kwargs(model)
            unknown = set(kwargs) - set(sig.parameters)
            assert not unknown, f"{model}: SDK {anthropic.__version__} rejects {sorted(unknown)}"

    @pytest.mark.asyncio
    async def test_temperature_is_never_a_named_kwarg(self) -> None:
        """It rides in ``extra_body`` instead. The API still takes the field for
        sunset-list models; only the SDK stopped surfacing it, and anthropic 1.x
        has no ``temperature`` parameter at all."""
        for model in ("claude-sonnet-4-6", "claude-opus-4-8", "claude-sonnet-5"):
            kwargs = await _capture_create_kwargs(model)
            assert "temperature" not in kwargs, model


class TestPickerClientCoherence:
    """Hold the invariant across the models the macOS picker actually offers.

    The original defect was a model reaching the picker that the client could
    not build a valid request for, with nothing connecting the two lists. The
    fail-closed default now handles that case on its own — an unrecognised
    model simply loses the parameter — so this is not a test that a *new*
    picker entry stays safe; it is a test that the gate is still applied at
    all, and it names the offending model when someone removes or bypasses it.

    What no offline test can catch: a model wrongly ADDED to
    _ANTHROPIC_ACCEPTS_SAMPLING that in fact rejects sampling. That needs a
    live call — see preflight/api_key.py::_validate_anthropic.
    """

    @pytest.mark.asyncio
    async def test_gate_is_applied_across_every_offered_model(self) -> None:
        for model in _picker_claude_models():
            kwargs = await _capture_create_kwargs(model)
            if model in _ANTHROPIC_ACCEPTS_SAMPLING:
                assert kwargs["extra_body"] == {"temperature": 0.1}, (
                    f"{model} should carry temperature"
                )
            else:
                assert not kwargs["extra_body"], (
                    f"{model} is offered in the macOS picker but is not in "
                    f"_ANTHROPIC_ACCEPTS_SAMPLING, yet a sampling parameter was sent. "
                    f"Post-4.6 Claude models reject it with a 400."
                )

    def test_sunset_set_only_names_models_we_could_offer(self) -> None:
        """The set only ever shrinks. An entry that names nothing real is dead
        weight that will outlive whoever can remember why it was added."""
        assert _ANTHROPIC_ACCEPTS_SAMPLING, "empty set means the kwarg can be deleted outright"
        for model in _ANTHROPIC_ACCEPTS_SAMPLING:
            assert model.startswith("claude-"), model
