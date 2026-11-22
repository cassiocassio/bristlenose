# Billing hints audit — 2026-10

**Date:** 2026-10-01  
**Source file audited:** `bristlenose/llm/billing_hints.py`  
**Triggered by:** quarterly drift cron `trig_01BtVXKG5hBnhPF4bGwR78CR`

---

## Audit limitation — cloud VM egress proxy

This audit ran inside a Claude Code Cloud VM. The egress proxy blocks all
provider domains (console, docs, help, support). **No live URL could be
fetched.** The console billing URLs all returned connection-level 000 (blocked);
portal.azure.com returned 403 (login redirect). `docs.anthropic.com`,
`platform.openai.com`, `help.openai.com`, `aistudio.google.com`, and
`console.cloud.google.com` are all blocked.

**The live-URL verification step requires a machine without these restrictions.**
Run from the dev Mac or manually open each URL in a browser.

---

## Code-analysis findings

### Anthropic — `billing_hints.py` row

| Field | Current value |
|---|---|
| `billing_url` | `https://console.anthropic.com/settings/billing` |
| `minimum_usd` | `5.0` |
| `minimum_note` | `"$5 minimum credit purchase. A separate Claude.ai Pro/Max subscription does NOT fund API usage…"` |

**Status:** Cannot verify live. URL is structurally the stable console path.
`Pro/Max` mention is consistent with Anthropic's current plan names (Max was
introduced in early 2025). No change recommended without live verification.

---

### OpenAI — `billing_hints.py` row

| Field | Current value |
|---|---|
| `billing_url` | `https://platform.openai.com/account/billing` |
| `minimum_usd` | `5.0` |
| `minimum_note` | `"$5 minimum credit purchase. A ChatGPT Plus/Pro subscription does NOT fund API usage…"` |

**⚠ FLAG FOR HUMAN REVIEW:** OpenAI restructured their platform UI in
mid-2024/2025. The `/account/billing` path has historically redirected to
`/settings/organization/billing`. Cannot confirm from this VM whether the old
path still resolves. **Please open the URL in a browser and confirm it doesn't
404 or produce a dead redirect.**

If it has moved: update `billing_url` to `https://platform.openai.com/settings/organization/billing`
(or whatever the redirect target is) and update the `minimum_note`'s navigation
hint from `"Billing → Add to credit balance"` to match the current UI label.

Note: `minimum_note` mentions "Plus/Pro" but the design doc also listed
"Team / Enterprise" as subscription-confusion candidates. Minor omission;
worth adding if the copy is being touched anyway.

---

### Google — `billing_hints.py` row

| Field | Current value |
|---|---|
| `keys_url` | `https://aistudio.google.com/apikey` |
| `billing_url` | `https://console.cloud.google.com/billing` |
| `minimum_usd` | `0.0` |
| `minimum_note` | `"Gemini is billed through Google Cloud (post-paid), not a credit balance…"` |

**⚠ FLAG FOR HUMAN REVIEW:** The `minimum_note` says nothing about the AI Studio
free tier. The design doc specifies: *"Two-mode — AI Studio free tier, then
Google Cloud billing."* A user hitting a rate-limit or quota error on an AI
Studio key would benefit from knowing the free tier exists and the GCP upgrade
path. Suggest adding a sentence:

```
"Gemini is billed through Google Cloud (post-paid), not a credit balance.
AI Studio offers a free tier with rate limits; upgrade via the Google Cloud
Console for higher quotas."
```

Cannot confirm whether AI Studio's free tier or URL has changed. Please verify
`https://aistudio.google.com/apikey` resolves and that the free tier is still
available before updating copy.

---

### Azure — `billing_hints.py` row

| Field | Current value |
|---|---|
| `billing_url` | `https://portal.azure.com/` |
| `minimum_usd` | `0.0` |
| `minimum_note` | `"Azure OpenAI is billed through your Azure subscription…"` |

The design doc lists the more specific blade URL
`https://portal.azure.com/#blade/Microsoft_Azure_Billing/SubscriptionsBlade`
but the simplified root URL is fine — Azure redirects to the appropriate
pane after login. No change needed.

**Status:** No drift detected from code analysis.

---

## New providers worth flagging

These have launched or matured since the last audit and are worth considering
for a future `billing_hints.py` addition. **Do not add without human review —
listed here for the quarterly decision.**

| Provider | API URL | Shape |
|---|---|---|
| xAI (Grok) | `https://console.x.ai/` | Prepay credit, similar to Anthropic/OpenAI. Launched widely in 2024–25. |
| Mistral La Plateforme | `https://console.mistral.ai/` | Prepay credit, €5–10 minimum. Strong EU adoption. |
| DeepSeek | `https://platform.deepseek.com/` | Prepay credit. Rapidly growing research/cost-sensitive user base. |
| Cohere | `https://dashboard.cohere.com/` | Trial credits then pay-as-you-go. Established; primarily enterprise. |

---

## Recommended actions

1. **Human: open each billing URL in a browser and confirm it resolves** (takes ~2 min).
2. **Especially check:** `https://platform.openai.com/account/billing` — most likely to have moved.
3. **Consider:** updating Google's `minimum_note` to mention the AI Studio free tier.
4. **Consider:** adding xAI / Mistral to `billing_hints.py` if Bristlenose user interest warrants.

---

## Audit trail

- Cron trigger: `trig_01BtVXKG5hBnhPF4bGwR78CR`
- Cloud VM egress blocked live URL verification (see above)
- No changes made to `billing_hints.py` — requires human sign-off on copy
- Branch: `audit/billing-hints-2026-10`
