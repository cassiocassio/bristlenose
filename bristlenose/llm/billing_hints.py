"""Per-provider URLs, minimums, and recovery copy for the API-key preflight.

Code-owned (English) per finding 31 design call: URLs, billing-minimum dollar
amounts, and the "auto-recharge vs. consume-credit" semantics are factual
provider properties — they shouldn't be translated. Translatable chrome
(intro line, "Bristlenose will wait here", per-step verbs) goes through
``i18n.t()`` in :mod:`bristlenose.preflight.api_key`.

Drift is policed by the quarterly-drift cron (`trig_01BtVXKG5hBnhPF4bGwR78CR`)
which walks these URLs and confirms the minimums + flow descriptions still
hold. The cron is already armed; it activates when this module exists.

Coverage scope (finding 24): only ``anthropic`` and ``openai`` get rich
error-class translations and recovery copy. Azure and Gemini fall through
to the generic ``"Provider says: <message>."`` path because their billing
models are more variable (subscription-tied, enterprise contracts) and the
prescriptive copy would mislead more than it helps.
"""

from __future__ import annotations

from dataclasses import dataclass

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
    interpolated. Falls through to :data:`GENERIC_RECOVERY` for non-(anthropic|openai)
    providers or unknown error classes.
    """
    # ``network`` errors are provider-agnostic (TLS / proxy / DNS).
    if error_class == "network":
        return t("preflight.api_key.network", message=raw_message or "no message")

    facts = billing_for(provider)
    if facts is None or error_class not in {
        "invalid_key", "billing_empty", "model_unavailable", "rate_limit",
    }:
        return t("preflight.api_key.generic", message=raw_message or "no message")

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
