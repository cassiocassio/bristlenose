"""The provider-signature gate and the NETWORK path of the shared LLM-failure classifier.

A proxy's block page must not read as the provider's answer: a bare 401/403 is "key
rejected" only when the reply is not known to be someone else's. ``None`` (unknown) keeps
today's behaviour for everything that carries no body.
"""

from __future__ import annotations

import httpx
import pytest

from bristlenose.llm.failure_classifier import (
    LLMFailureKind,
    classify_fields,
    classify_llm_failure,
    extract_provider_signature,
)


class _ReplyError(Exception):
    def __init__(self, status, body=None, content_type=None):
        super().__init__(f"HTTP {status}")
        self.status_code = status
        self.body = body
        self.response = type("R", (), {"headers": {"content-type": content_type or ""}})()


class TestGate:
    @pytest.mark.parametrize("status,kind", [
        (401, LLMFailureKind.UNKNOWN),
        (403, LLMFailureKind.UNKNOWN),
        (429, LLMFailureKind.UNKNOWN),
        (502, LLMFailureKind.UNKNOWN),
        (400, LLMFailureKind.UNKNOWN),
    ])
    def test_an_unsigned_status_says_nothing_about_the_provider(self, status, kind):
        assert classify_llm_failure(
            "anthropic", status=status, provider_signature=False) is kind

    @pytest.mark.parametrize("sig", [None, True])
    def test_unknown_and_signed_keep_the_status_rules(self, sig):
        assert classify_llm_failure(
            "anthropic", status=401, provider_signature=sig) is LLMFailureKind.INVALID_KEY
        assert classify_llm_failure(
            "anthropic", status=502, provider_signature=sig) is LLMFailureKind.SERVER_ERROR

    def test_an_unsigned_reply_still_reads_the_providers_own_words(self):
        # A rule that reads the provider's code or message is not a status guess.
        assert classify_llm_failure(
            "anthropic", status=400, message="Your credit balance is too low",
            provider_signature=False) is LLMFailureKind.OUT_OF_CREDIT

    def test_a_bare_message_only_401_is_unchanged(self):
        # test_llm_failure_classifier pins Azure this way: no body, so no signature.
        assert classify_llm_failure("azure", status=401) is LLMFailureKind.INVALID_KEY


class TestExtract:
    def test_the_provider_json_shape_is_a_signature(self):
        assert extract_provider_signature(
            _ReplyError(401, {"type": "error", "error": {"type": "authentication_error"}}), 401) is True
        assert extract_provider_signature(_ReplyError(429, {"error": {"code": "x"}}), 429) is True

    def test_an_html_page_is_positive_evidence_of_another_sender(self):
        assert extract_provider_signature(_ReplyError(403, None, "text/html"), 403) is False
        assert extract_provider_signature(_ReplyError(502, "<html>Bad Gateway</html>"), 502) is False

    def test_a_request_id_header_alone_is_not_a_signature(self):
        e = _ReplyError(403)
        e.response = type("R", (), {"headers": {"x-request-id": "abc"}})()
        assert extract_provider_signature(e, 403) is None

    def test_no_status_no_signature(self):
        assert extract_provider_signature(RuntimeError("x"), None) is None


class TestClassifyFields:
    def test_a_proxy_403_page_is_not_a_rejected_key(self):
        exc = _ReplyError(403, "<html>Blocked</html>", "text/html")
        assert classify_fields("anthropic", exc) is LLMFailureKind.UNKNOWN

    def test_a_real_401_still_is(self):
        exc = _ReplyError(401, {"type": "error", "error": {"type": "authentication_error"}})
        assert classify_fields("anthropic", exc) is LLMFailureKind.INVALID_KEY


class TestNetwork:
    def test_a_dropped_connection_is_network_for_a_builtin_provider(self):
        exc = httpx.ConnectError("boom")
        assert classify_fields("anthropic", exc) is LLMFailureKind.NETWORK
        assert classify_fields("openai", exc) is LLMFailureKind.NETWORK

    def test_a_reply_with_a_status_is_never_network(self):
        assert classify_fields("anthropic", _ReplyError(503, {"error": {}})) is LLMFailureKind.SERVER_ERROR

    def test_an_ordinary_exception_is_unknown(self):
        assert classify_fields("anthropic", ValueError("x")) is LLMFailureKind.UNKNOWN


class TestBuildCauseCarriesTheStatus:
    def test_the_http_status_lands_in_cause_code(self):
        from bristlenose.run_lifecycle import _build_cause

        exc = _ReplyError(429, {"error": {"type": "rate_limit_error"}})
        assert _build_cause(exc, stage="topic_segmentation", provider="anthropic").code == "429"

    def test_no_status_no_code(self):
        from bristlenose.run_lifecycle import _build_cause

        cause = _build_cause(httpx.ConnectError("x"), stage="s", provider="anthropic")
        assert cause.code is None
        assert cause.category.value == "network"
