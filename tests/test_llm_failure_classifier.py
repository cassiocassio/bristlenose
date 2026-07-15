"""Tests for the shared LLM-failure classifier against real 2025-2026 payloads.

Each case encodes an actually-observed or documented provider error shape (see
the source citations in the research summary + `failure_classifier.py`). The
value is proving the tricky discriminations hold: Anthropic's out-of-credit is
a 400 (not 402), OpenAI's billing vs rate-limit share 429 and split on
`error.code`, and Azure/Gemini "walls" are honestly rate-limited (no faked
credit story).
"""

from __future__ import annotations

import pytest

from bristlenose.llm.failure_classifier import (
    LLMFailureKind,
    classify_exception,
    classify_llm_failure,
)


class TestAnthropic:
    def test_out_of_credit_is_a_400_not_402(self) -> None:
        # The REAL observed path (our pytest + continuedev#5499 + litellm#24320).
        kind = classify_llm_failure(
            "anthropic",
            status=400,
            error_code="invalid_request_error",
            message="Your credit balance is too low to access the Anthropic API. "
            "Please go to Plans & Billing to upgrade or purchase credits.",
        )
        assert kind == LLMFailureKind.OUT_OF_CREDIT

    def test_documented_402_billing_error(self) -> None:
        kind = classify_llm_failure(
            "anthropic", status=402, error_code="billing_error",
            message="There was an issue with your billing or payment information.",
        )
        assert kind == LLMFailureKind.OUT_OF_CREDIT

    def test_plain_400_bad_request_is_not_credit(self) -> None:
        # A malformed request / deprecated model id must NOT read as billing.
        kind = classify_llm_failure(
            "anthropic", status=400, error_code="invalid_request_error",
            message="model: claude-nonexistent-1 not found",
        )
        assert kind == LLMFailureKind.BAD_REQUEST

    def test_rate_limit(self) -> None:
        kind = classify_llm_failure(
            "anthropic", status=429, error_code="rate_limit_error",
            message="Number of requests has hit a rate limit.",
        )
        assert kind == LLMFailureKind.RATE_LIMITED

    def test_invalid_key(self) -> None:
        kind = classify_llm_failure(
            "anthropic", status=401, error_code="authentication_error",
            message="There was an issue with your API key.",
        )
        assert kind == LLMFailureKind.INVALID_KEY

    def test_overloaded_is_server_error(self) -> None:
        kind = classify_llm_failure(
            "anthropic", status=529, error_code="overloaded_error",
            message="Anthropic's API is temporarily overloaded.",
        )
        assert kind == LLMFailureKind.SERVER_ERROR


class TestOpenAI:
    def test_insufficient_quota_is_out_of_credit_despite_429(self) -> None:
        # Shares 429 with rate-limiting; the code is the discriminator.
        kind = classify_llm_failure(
            "openai", status=429, error_code="insufficient_quota",
            message="You exceeded your current quota, please check your plan and "
            "billing details.",
        )
        assert kind == LLMFailureKind.OUT_OF_CREDIT

    def test_rate_limit_exceeded_is_transient(self) -> None:
        kind = classify_llm_failure(
            "openai", status=429, error_code="rate_limit_exceeded",
            message="Rate limit reached for gpt-4o. Please retry after 1s.",
        )
        assert kind == LLMFailureKind.RATE_LIMITED

    def test_bare_429_without_code_defaults_to_rate_limited(self) -> None:
        # Don't cry "out of credit" without the discriminating code.
        kind = classify_llm_failure("openai", status=429)
        assert kind == LLMFailureKind.RATE_LIMITED

    def test_invalid_key_by_code(self) -> None:
        # type is invalid_request_error; the code is the real discriminator.
        kind = classify_llm_failure(
            "openai", status=401, error_code="invalid_api_key",
            message="Incorrect API key provided: sk-abc***.",
        )
        assert kind == LLMFailureKind.INVALID_KEY


class TestAzure:
    def test_tpm_rate_limit_is_rate_limited(self) -> None:
        kind = classify_llm_failure(
            "azure", status=429, error_code="429",
            message="Requests to the ... exceeded token rate limit of your "
            "current OpenAI S0 pricing tier. Please retry after 26 seconds.",
        )
        assert kind == LLMFailureKind.RATE_LIMITED

    def test_azure_has_no_out_of_credit(self) -> None:
        # Azure quota exhaustion is not a top-up-able "credit" — stays rate.
        kind = classify_llm_failure(
            "azure", status=429, error_code="insufficient_quota",
            message="exceeded call rate limit",
        )
        # insufficient_quota is only OUT_OF_CREDIT for OpenAI, not Azure.
        assert kind == LLMFailureKind.RATE_LIMITED

    def test_invalid_key(self) -> None:
        kind = classify_llm_failure(
            "azure", status=401,
            message="Access denied due to invalid subscription key or wrong API "
            "endpoint.",
        )
        assert kind == LLMFailureKind.INVALID_KEY


class TestGemini:
    def test_resource_exhausted_is_rate_limited_not_credit(self) -> None:
        # Gemini folds billing + rate + free-cap into one signal — honest = rate.
        kind = classify_llm_failure(
            "google", status=429, error_code="RESOURCE_EXHAUSTED",
            message="Resource has been exhausted (e.g. check quota).",
        )
        assert kind == LLMFailureKind.RATE_LIMITED

    def test_malformed_key_400(self) -> None:
        kind = classify_llm_failure(
            "google", status=400, error_code="INVALID_ARGUMENT API_KEY_INVALID",
            message="API key not valid. Please pass a valid API key.",
        )
        assert kind == LLMFailureKind.INVALID_KEY

    def test_leaked_key_403(self) -> None:
        kind = classify_llm_failure(
            "google", status=403, error_code="PERMISSION_DENIED",
            message="Your API key has been reported as leaked.",
        )
        assert kind == LLMFailureKind.INVALID_KEY


class TestProviderAgnostic:
    """The generic path (provider unknown) still matches distinctive signals."""

    def test_credit_message_without_provider(self) -> None:
        kind = classify_llm_failure(
            message="Your credit balance is too low to access the Anthropic API."
        )
        # Provider-scoped rule still fires when provider is unknown (best-effort).
        assert kind == LLMFailureKind.OUT_OF_CREDIT

    def test_insufficient_quota_code_without_provider(self) -> None:
        kind = classify_llm_failure(error_code="insufficient_quota")
        assert kind == LLMFailureKind.OUT_OF_CREDIT

    def test_unknown_when_no_signal(self) -> None:
        assert classify_llm_failure("openai") == LLMFailureKind.UNKNOWN
        assert classify_llm_failure(message="something odd happened") == (
            LLMFailureKind.UNKNOWN
        )


class TestClassifyException:
    """Field extraction from SDK-exception-shaped objects."""

    def test_anthropic_bad_request_shape(self) -> None:
        class FakeAnthropicError(Exception):
            status_code = 400
            body = {"type": "error", "error": {"type": "invalid_request_error",
                    "message": "Your credit balance is too low"}}

            def __str__(self) -> str:
                return "Error code: 400 - Your credit balance is too low"

        assert classify_exception("anthropic", FakeAnthropicError()) == (
            LLMFailureKind.OUT_OF_CREDIT
        )

    def test_openai_insufficient_quota_shape(self) -> None:
        class FakeOpenAIError(Exception):
            status_code = 429
            code = "insufficient_quota"
            type = "insufficient_quota"

            def __str__(self) -> str:
                return "You exceeded your current quota"

        assert classify_exception("openai", FakeOpenAIError()) == (
            LLMFailureKind.OUT_OF_CREDIT
        )

    def test_gemini_permission_denied_shape(self) -> None:
        class FakeGeminiError(Exception):
            status_code = 403
            body = {"error": {"status": "PERMISSION_DENIED",
                    "details": [{"reason": "API_KEY_INVALID"}]}}

            def __str__(self) -> str:
                return "reported as leaked"

        assert classify_exception("google", FakeGeminiError()) == (
            LLMFailureKind.INVALID_KEY
        )

    def test_string_only_exception_falls_back_to_message(self) -> None:
        exc = RuntimeError("Your credit balance is too low to access the API")
        assert classify_exception("anthropic", exc) == LLMFailureKind.OUT_OF_CREDIT


@pytest.mark.parametrize(
    "provider,status,code,message,expected",
    [
        ("anthropic", 400, None, "credit balance is too low", LLMFailureKind.OUT_OF_CREDIT),
        ("openai", 429, "insufficient_quota", None, LLMFailureKind.OUT_OF_CREDIT),
        ("openai", 429, "rate_limit_exceeded", None, LLMFailureKind.RATE_LIMITED),
        ("azure", 429, None, "exceeded token rate limit", LLMFailureKind.RATE_LIMITED),
        ("google", 429, "RESOURCE_EXHAUSTED", None, LLMFailureKind.RATE_LIMITED),
        ("anthropic", 401, "authentication_error", None, LLMFailureKind.INVALID_KEY),
        (None, 500, None, None, LLMFailureKind.SERVER_ERROR),
    ],
)
def test_matrix(provider, status, code, message, expected) -> None:  # type: ignore[no-untyped-def]
    assert classify_llm_failure(
        provider, status=status, error_code=code, message=message
    ) == expected
