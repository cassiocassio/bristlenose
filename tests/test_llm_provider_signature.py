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

    def test_an_unsigned_reply_is_unknown_even_if_its_text_quotes_the_provider(self):
        # A proxy page that says "credit balance is too low" is still the proxy's.
        assert classify_llm_failure(
            "anthropic", status=400, message="Your credit balance is too low",
            provider_signature=False) is LLMFailureKind.UNKNOWN

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

    def test_a_non_http_exception_with_an_int_code_attribute_is_not_a_status(self):
        from bristlenose.run_lifecycle import _build_cause

        class _OsError(Exception):
            code = 2

        assert _build_cause(_OsError("x"), stage="s", provider="anthropic").code is None


class TestRealSdkExceptions:
    """Exceptions built by the SDKs themselves, not by a fake with the attributes we expect."""

    def _err(self, mod, status, **kw):
        import anthropic
        import openai

        client = anthropic.AsyncAnthropic(api_key="x") if mod == "anthropic" \
            else openai.AsyncOpenAI(api_key="x")
        req = httpx.Request("POST", "https://example.invalid/v1")
        return client._make_status_error_from_response(httpx.Response(status, request=req, **kw))

    @pytest.mark.parametrize("mod", ["anthropic", "openai"])
    @pytest.mark.parametrize("status", [401, 403, 502])
    def test_an_html_block_page_is_unknown_and_unsigned(self, mod, status):
        exc = self._err(mod, status, headers={"content-type": "text/html"},
                        text="<html><body>Blocked by proxy</body></html>")
        assert classify_fields(mod, exc) is LLMFailureKind.UNKNOWN
        assert extract_provider_signature(exc, status) is False

    def test_openais_own_401_is_still_a_rejected_key(self):
        exc = self._err("openai", 401, json={"error": {
            "message": "Incorrect API key provided", "type": "invalid_request_error",
            "code": "invalid_api_key"}})
        assert classify_fields("openai", exc) is LLMFailureKind.INVALID_KEY
        assert extract_provider_signature(exc, 401) is True

    @pytest.mark.parametrize("provider,status,kind", [
        ("openai", 401, LLMFailureKind.INVALID_KEY),
        ("local", 500, LLMFailureKind.SERVER_ERROR),
    ])
    def test_a_reply_whose_error_is_a_bare_string_is_not_called_someone_elses(
            self, provider, status, kind):
        # The openai SDK unwraps {"error": "text"} to the str "text"; that is the server's reply.
        exc = self._err("openai", status, json={"error": "Invalid token"})
        assert classify_fields(provider, exc) is kind

    def test_a_json_proxy_body_without_the_providers_shape_is_not_a_signature(self):
        exc = self._err("anthropic", 403, json={"message": "Forbidden"})
        assert extract_provider_signature(exc, 403) is not True
        exc = self._err("openai", 403, json={"code": 403})
        assert extract_provider_signature(exc, 403) is not True
