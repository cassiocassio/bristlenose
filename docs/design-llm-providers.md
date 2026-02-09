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
| 4 | **Gemini** | Next (issue #37) | Budget option — Gemini Flash is 5–7× cheaper than Claude/GPT-4o |
| 5 | **Provider documentation** | Next (issue #38) | README section, man page updates, `.env.example` |

---

## Phase 4: Gemini (~3h)

- Add `google-genai` dependency (~15 MB)
- Add Gemini to provider registry — native JSON schema support
- `_analyze_gemini()` method (different SDK pattern from OpenAI-compatible providers)
- Pricing: Gemini Flash is 5–7× cheaper than Claude/GPT-4o

**Why Gemini:** Budget users and organisations that already have Google Cloud accounts.

## Phase 5: Provider documentation (~2h)

- README section: "Choosing an LLM provider" (draft in `docs/design-cli-improvements.md`)
- Man page updates for all providers
- `.env.example` with all provider env vars

---

## Not supported

**GitHub Copilot:** NOT supported. Copilot ≠ Azure OpenAI. There is no public inference API. Point enterprise users to Azure instead.
