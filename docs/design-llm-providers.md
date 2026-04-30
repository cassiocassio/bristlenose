---
status: current
last-trued: 2026-04-30
trued-against: HEAD@first-run on 2026-04-30
---

## Changelog

- _2026-04-30_ — All five providers shipped end-to-end. Phase 4 Gemini done (`LLMProvider.gemini`, `LLMValidator.validateGemini` round-trip, default `gemini-2.0-flash`); Phase 5 Provider documentation partial-shipped (README, `.env.example`, `bristlenose configure gemini`). Beyond original scope: round-trip credential validation in `LLMValidator.swift` (Beat 3, commit `d336607`); curated RAM-tiered local-model picker via `OllamaCatalog` (Beat 3b, commit `07ee058`); per-provider link surface (`ProviderLinks` struct in `LLMProvider.swift`); Ollama URL hardwired in desktop GUI as a trust-boundary closure (`dbd54ec`).

# LLM Provider Roadmap

Goal: support whatever LLM your organisation has access to.

**Detailed implementation records** (Ollama, Azure, Keychain — all shipped) are archived in the "LLM Provider Roadmap" section of `docs/design-cli-improvements.md`. This document tracks the overall roadmap and status.

---

## Status

| Phase | Provider | Status | Notes |
|-------|----------|--------|-------|
| 1 | **Ollama** (Local) | ✅ Done | Zero-friction entry point. No signup, no payment, no API key. Interactive first-run prompt, auto-install, auto-start, model auto-pull, retry logic for JSON failures, doctor integration |
| 2 | **Azure OpenAI** | ✅ Done | Enterprise demand. Config: `BRISTLENOSE_AZURE_ENDPOINT`, `BRISTLENOSE_AZURE_KEY`, `BRISTLENOSE_AZURE_DEPLOYMENT` |
| 3 | **Keychain integration** | ✅ Done | `bristlenose configure claude`/`chatgpt`. Native CLI tools (no `keyring` library). Priority: keychain → env var → .env. Doctor shows "(Keychain)" suffix |
| 4 | **Gemini** | ✅ Done | `LLMProvider.gemini` enum case, `LLMValidator.validateGemini` (GET `/v1beta/models`), default model `gemini-2.0-flash`. `_analyze_gemini()` in sidecar uses `google-genai` SDK |
| 5 | **Provider documentation** | ✅ Partial | README section, `.env.example`, `bristlenose configure gemini` shipped. Man page updates pending |
| — | **Round-trip validation** | ✅ Done (beyond original scope) | `LLMValidator.swift` (Beat 3, `d336607`) does Swift-side native auth-checks per provider, with a verdict cache + 60s TTL gate. See `design-desktop-settings.md` §Validation flow |
| — | **Curated local-model picker** | ✅ Done (beyond original scope) | `OllamaCatalog` (Beat 3b, `07ee058`) ships 4 RAM-tiered models with auto-recommendation. `OllamaSetupSheet.swift` first-run install + model-pull flow. See `design-gemma4-local-models.md` |
| — | **Per-provider key/pricing/console links** | ✅ Done | `ProviderLinks` struct on `LLMProvider`. Bare-domain labels in Settings detail pane |

---

## Phase 4: Gemini (~3h) — shipped

- ✅ `google-genai` dependency added (~15 MB)
- ✅ Gemini in provider registry — native JSON schema support
- ✅ `_analyze_gemini()` method (different SDK pattern from OpenAI-compatible providers)
- ✅ Default model `gemini-2.0-flash` (5–7× cheaper than Claude/GPT-4o)
- ✅ Native Swift validation: `LLMValidator.validateGemini` (GET `/v1beta/models`)

**Why Gemini:** Budget users and organisations that already have Google Cloud accounts.

## Phase 5: Provider documentation (~2h) — partial

- ✅ README section: "Choosing an LLM provider" (also `docs/design-cli-improvements.md`)
- ⬜ Man page updates for all providers (pending)
- ✅ `.env.example` with all provider env vars
- ✅ `bristlenose configure gemini` CLI

---

## Not supported

**GitHub Copilot:** NOT supported. Copilot ≠ Azure OpenAI. There is no public inference API. Point enterprise users to Azure instead.
