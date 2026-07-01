"""Per-provider URLs, minimums, and recovery copy for the API-key preflight.

Code-owned (English) per finding 31 design call: URLs, billing-minimum dollar
amounts, and the "auto-recharge vs. consume-credit" semantics are factual
provider properties — they shouldn't be translated. Translatable chrome
(intro line, "Bristlenose will wait here", per-step verbs) goes through
``i18n.t()`` in :mod:`bristlenose.preflight.api_key`.

Drift is policed by the quarterly-drift cron (`trig_01BtVXKG5hBnhPF4bGwR78CR`)
which walks these URLs and confirms the minimums + flow descriptions still
hold. The cron is already armed; it activates when this module exists.

Coverage scope: all five providers (anthropic, openai, azure, google,
local) get rich error-class translations. Azure / Google / Local don't
have credit-balance billing (subscription / GCP-billed / free) so their
``billing_url`` and ``minimum_note`` are honest about that rather than
faking a top-up flow.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.markup import escape as _rich_escape

from bristlenose.i18n import t


@dataclass(frozen=True)
class ProviderBilling:
    """Static per-provider billing facts referenced by recovery copy."""

    display_name: str
    console_url: str
    keys_url: str
    billing_url: str
    minimum_usd: float
    minimum_note: str  # e.g. "auto-recharge off by default; manual top-up funds the credit balance"


_BILLING: dict[str, ProviderBilling] = {
    "anthropic": ProviderBilling(
        display_name="Claude",
        console_url="https://console.anthropic.com/",
        keys_url="https://console.anthropic.com/settings/keys",
        billing_url="https://console.anthropic.com/settings/billing",
        minimum_usd=5.0,
        minimum_note=(
            "$5 minimum credit purchase. A separate Claude.ai Pro/Max "
            "subscription does NOT fund API usage — the API has its own "
            "credit balance, refilled at Settings → Billing."
        ),
    ),
    "openai": ProviderBilling(
        display_name="ChatGPT",
        console_url="https://platform.openai.com/",
        keys_url="https://platform.openai.com/api-keys",
        billing_url="https://platform.openai.com/account/billing",
        minimum_usd=5.0,
        minimum_note=(
            "$5 minimum credit purchase. A ChatGPT Plus/Pro subscription "
            "does NOT fund API usage — the API has its own credit balance, "
            "refilled at Billing → Add to credit balance."
        ),
    ),
    "azure": ProviderBilling(
        display_name="Azure OpenAI",
        console_url="https://portal.azure.com/",
        keys_url="https://portal.azure.com/",
        billing_url="https://portal.azure.com/",
        minimum_usd=0.0,
        minimum_note=(
            "Azure OpenAI is billed through your Azure subscription, not a "
            "credit balance. Check usage and quotas in the Azure portal."
        ),
    ),
    "google": ProviderBilling(
        display_name="Gemini",
        console_url="https://console.cloud.google.com/",
        keys_url="https://aistudio.google.com/apikey",
        billing_url="https://console.cloud.google.com/billing",
        minimum_usd=0.0,
        minimum_note=(
            "Gemini offers a free tier (Flash models only, rate-limited). "
            "Paid usage is billed through Google Cloud — either via Prepay "
            "($10 minimum credit purchase, required for new accounts since "
            "March 2026) or post-paid GCP billing. Google AI Pro/Ultra "
            "subscription credits can fund API usage; Google One, Workspace, "
            "and Gemini Advanced subscriptions cannot."
        ),
    ),
    "local": ProviderBilling(
        display_name="Local",
        console_url="https://ollama.com/",
        keys_url="https://ollama.com/",
        billing_url="https://ollama.com/",
        minimum_usd=0.0,
        minimum_note="Local models run via Ollama on this machine — no billing.",
    ),
}


def billing_for(provider: str) -> ProviderBilling | None:
    """Return the billing facts for a provider, or None if no rich support."""
    return _BILLING.get(provider)


# Error-class catalogue — single source of truth for the recovery messages
# the preflight emits when an LLM provider call fails during validation.
#
# Keys are the four buckets finding 24 calls out:
#   - "invalid_key"       — auth failure (bad key, deleted key, wrong project)
#   - "billing_empty"     — key valid, balance zero (provider-specific status codes)
#   - "model_unavailable" — key valid, requested model not enabled for this org
#   - "rate_limit"        — too many requests; retry later
#
# Generic message returned for unknown / fall-through cases.
GENERIC_RECOVERY = (
    "Provider says: {message}.\n"
    "If this looks like a credit-balance issue, top up at the provider's "
    "billing console and re-run."
)


def recovery_message(provider: str, error_class: str, raw_message: str = "") -> str:
    """Return the recovery copy for a (provider, error_class) tuple.

    Translatable prose comes from ``preflight.api_key.*`` via :mod:`bristlenose.i18n`;
    URLs and the ``minimum_note`` are code-owned in :data:`_BILLING` and
    interpolated. Falls through to a generic key for unknown error classes.

    Per-provider override keys (Azure deployment-name copy, Local
    server-down / model-not-pulled, Google Cloud-console copy) take
    precedence over the four-bucket defaults when present.
    """
    facts = billing_for(provider)

    # raw_message is provider-controlled text (``str(exc)`` from an SDK
    # exception). Escape Rich markup before interpolating: a hostile or
    # MITM'd provider response can embed ``[link=…]`` OSC-8 hyperlinks
    # or other markup that Rich would render in the user's terminal.
    safe_message = _rich_escape(raw_message) if raw_message else "no message"

    # ``network`` errors are provider-agnostic except for local Ollama,
    # where "connect refused" is "ollama isn't running" with a specific fix.
    if error_class == "network":
        if provider == "local":
            return t(
                "preflight.api_key.local_server_down",
                message=safe_message,
            )
        return t("preflight.api_key.network", message=safe_message)

    if facts is None or error_class not in {
        "invalid_key", "billing_empty", "model_unavailable", "rate_limit",
    }:
        return t("preflight.api_key.generic", message=safe_message)

    # Per-provider overrides — Azure portal deployment-name, Google
    # Cloud-console for tier-gate / billing-disabled, Local pull copy.
    override_key: str | None = None
    if provider == "azure" and error_class == "model_unavailable":
        override_key = "preflight.api_key.azure_deployment_unavailable"
    elif provider == "google" and error_class == "model_unavailable":
        override_key = "preflight.api_key.google_model_unavailable"
    elif provider == "local" and error_class == "model_unavailable":
        override_key = "preflight.api_key.local_model_not_pulled"

    if override_key is not None:
        return t(
            override_key,
            provider_display=facts.display_name,
            keys_url=facts.keys_url,
            billing_url=facts.billing_url,
            console_url=facts.console_url,
            minimum_note=facts.minimum_note,
            message=safe_message,
        )

    # Note: Azure never produces ``billing_empty`` — Azure OpenAI is billed
    # through the Azure subscription, not a credit pool (the validator
    # routes 429s to ``rate_limit`` unconditionally). The mapping is kept
    # complete for symmetry; the Azure branch is unreachable in practice.
    key = {
        "invalid_key": "preflight.api_key.rejected_invalid_key",
        "billing_empty": "preflight.api_key.no_credit",
        "model_unavailable": "preflight.api_key.model_unavailable",
        "rate_limit": "preflight.api_key.rate_limit",
    }[error_class]
    return t(
        key,
        provider_display=facts.display_name,
        keys_url=facts.keys_url,
        billing_url=facts.billing_url,
        console_url=facts.console_url,
        minimum_note=facts.minimum_note,
    )


# Legacy export kept for tests that asserted the literal default template.
# New code should call ``recovery_message`` which routes through i18n.
