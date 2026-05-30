"""Tests for bristlenose.llm.billing_hints."""

from __future__ import annotations

import pytest

from bristlenose.llm.billing_hints import (
    GENERIC_RECOVERY,
    billing_for,
    recovery_message,
)


class TestBillingFor:
    def test_anthropic_facts_present(self):
        facts = billing_for("anthropic")
        assert facts is not None
        assert facts.display_name == "Claude"
        assert "console.anthropic.com" in facts.console_url
        assert "console.anthropic.com" in facts.keys_url
        assert "console.anthropic.com" in facts.billing_url
        assert facts.minimum_usd == 5.0
        assert "subscription" in facts.minimum_note.lower()

    def test_openai_facts_present(self):
        facts = billing_for("openai")
        assert facts is not None
        assert facts.display_name == "ChatGPT"
        assert "platform.openai.com" in facts.keys_url
        assert "subscription" in facts.minimum_note.lower()

    def test_all_five_providers_have_facts(self):
        # Azure, Google, Local were added on the
        # llm-error-distinguishability-all-providers branch.
        for provider in ("anthropic", "openai", "azure", "google", "local"):
            assert billing_for(provider) is not None

    def test_unknown_provider_returns_none(self):
        assert billing_for("nonsense-provider") is None


class TestRecoveryMessage:
    @pytest.mark.parametrize(
        "error_class", ["invalid_key", "billing_empty", "model_unavailable", "rate_limit"],
    )
    def test_anthropic_all_classes_have_rich_copy(self, error_class):
        msg = recovery_message("anthropic", error_class, "raw")
        assert "Claude" in msg or "claude" in msg.lower() or "anthropic" in msg.lower()

    @pytest.mark.parametrize(
        "error_class", ["invalid_key", "billing_empty", "model_unavailable", "rate_limit"],
    )
    def test_openai_all_classes_have_rich_copy(self, error_class):
        msg = recovery_message("openai", error_class, "raw")
        assert "ChatGPT" in msg

    def test_invalid_key_mentions_keys_url(self):
        msg = recovery_message("anthropic", "invalid_key", "401")
        assert "settings/keys" in msg

    def test_billing_empty_mentions_billing_url(self):
        msg = recovery_message("anthropic", "billing_empty", "low credit")
        assert "settings/billing" in msg

    def test_unknown_class_falls_through_to_generic(self):
        msg = recovery_message("anthropic", "weird-thing", "raw msg")
        assert msg == GENERIC_RECOVERY.format(message="raw msg")

    def test_unknown_provider_falls_through_to_generic(self):
        msg = recovery_message("nonsense-provider", "invalid_key", "raw msg")
        assert "raw msg" in msg

    def test_azure_deployment_unavailable_has_portal_copy(self):
        # Headline Azure foot-gun — recovery copy must name the
        # deployment-name distinction so users don't mistake it for a model id.
        msg = recovery_message(
            "azure", "model_unavailable", "DeploymentNotFound: foo",
        )
        assert "deployment" in msg.lower()

    def test_local_server_down_recovery_mentions_ollama(self):
        msg = recovery_message("local", "network", "Connection refused")
        assert "ollama" in msg.lower()

    def test_local_model_unavailable_recovery_mentions_pull(self):
        msg = recovery_message("local", "model_unavailable", "not found")
        assert "ollama pull" in msg.lower()

    def test_google_model_unavailable_mentions_cloud_console(self):
        msg = recovery_message("google", "model_unavailable", "permission denied")
        assert "console.cloud.google.com" in msg
