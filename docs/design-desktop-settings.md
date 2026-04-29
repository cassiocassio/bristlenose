---
status: current
last-trued: 2026-04-21
trued-against: HEAD@sidecar-signing on 2026-04-21
---

## Changelog

- _2026-04-21_ — trued up, minor additions: noted Ollama status derives from URL reachability (no key-injection); noted `overlayPreferences` don't-override-default guard (only explicitly-set values get emitted); noted `KeychainStore` protocol + `InMemoryKeychain` test shim; promoted threat-model rationale (env-vars vs keychain-access-groups residual-risk delta) from `ServeManager.swift:366-371` comment; added cross-ref to `design-settings-ui.md` for the serve-mode web-UI path (complement, not competitor) and `design-keychain.md` §Desktop credential path.
- _2026-04-20_ — trued in C3 closeout pass; structural accuracy confirmed against `SettingsView.swift`, `ServeManager.swift`, `LLMProvider.swift`.

# Desktop Settings Window (Cmd+,)

Apple canonical `Settings` scene with 3 icon tabs. Constant width (660pt) across all tabs, height animates to fit content. Working context lives in `desktop/CLAUDE.md`. Related: `design-settings-ui.md` (serve-mode web UI — complementary, not competing: web UI is the CLI/serve path; this is the embedded-alpha path), `design-keychain.md` §Desktop (sandboxed) credential path (canonical home for the Swift→env-var→Python architecture).

## Tab 1: Appearance (paintbrush)

Theme radio group (auto/light/dark) + language dropdown (6 locales). `@AppStorage("appearance")` drives `.preferredColorScheme` on both the main window and Settings window. Appearance is also synced to the web layer via `BridgeHandler.syncAppearance()` on `ready` — native wins, web Settings modal hides its appearance picker in embedded mode.

## Tab 2: LLM (brain) — Mail Accounts pattern

Left sidebar list of 5 pre-populated providers (Claude, ChatGPT, Gemini, Azure, Ollama) with two orthogonal indicators per row:
- **Radio/checkmark** — which provider is active (user choice, `@AppStorage("activeProvider")`)
- **Status dot** — whether the provider is configured (green "Online" / grey "Not set up" / red "Invalid" / orange "Unavailable")

Right detail pane shows the selected provider's settings: API key (`SecureField` → Keychain via `KeychainHelper`), model picker (per-provider known models + "Custom…"), temperature slider, concurrency slider. Azure adds endpoint/deployment/version fields. Ollama shows URL instead of API key (no key injection — status derives from URL reachability via health check, not keychain presence).

**Activation guard**: a provider cannot be activated (radio or toggle) unless its status is `.online`. You can select a provider in the sidebar to set it up, but the radio stays greyed out until a valid key is entered. One provider must always be active.

**Per-provider model storage**: `UserDefaults` key `llmModel_{provider}` stores each provider's selected model. When a provider becomes active, its model is written to the global `llmModel` key for ServeManager.

## Tab 3: Transcription (waveform)

Whisper backend picker (Auto/MLX/faster-whisper) + model picker (large-v3-turbo through tiny). `@AppStorage` for both.

## Preferences → serve process

`ServeManager.overlayPreferences()` reads `UserDefaults` and injects values as environment variables into the `Process.environment` dictionary before launching `bristlenose serve`. **Don't-override-default guard**: `overlayPreferences` only emits an env var when the user has explicitly set the value (e.g. `BRISTLENOSE_WHISPER_LANGUAGE` only set when `lang != "en"`; temperature and concurrency only set when the user has touched the slider). This lets Python-side defaults stay authoritative when the user hasn't expressed a preference. See `ServeManager.swift:307-355`.

API keys are injected via `ServeManager.overlayAPIKeys()` (C3, Apr 2026) — Swift reads Keychain via `Security.framework` (through the `KeychainStore` protocol; tests use `InMemoryKeychain`) and sets `BRISTLENOSE_<PROVIDER>_API_KEY` on the same env dict. Python never touches Keychain in this deployment; pydantic-settings reads the env vars directly. **Threat-model rationale** (from `ServeManager.swift:366-371` comment): env vars are visible to same-UID attackers via `ps -E`, but a same-UID attacker can already call `SecItemCopyMatching` directly; the net delta is small. Sandbox protects against *other* UIDs, not same-UID code execution. Documenting the residual risk honestly beats security theatre (keychain-access-groups wouldn't raise the bar against the real threat model). Full credential-flow discussion in `design-keychain.md` §Desktop (sandboxed) credential path.

`ServeManager` subscribes to `Notification.Name.bristlenosePrefsChanged`. When any settings view posts this notification and a serve process is running, `restartIfRunning()` stops and re-starts with the new environment.

| Setting | UserDefaults key | Env var |
|---------|-----------------|---------|
| Active provider | `activeProvider` | `BRISTLENOSE_LLM_PROVIDER` |
| Model | `llmModel` | `BRISTLENOSE_LLM_MODEL` |
| Temperature | `llmTemperature` | `BRISTLENOSE_LLM_TEMPERATURE` |
| Concurrency | `llmConcurrency` | `BRISTLENOSE_LLM_CONCURRENCY` |
| Whisper backend | `whisperBackend` | `BRISTLENOSE_WHISPER_BACKEND` |
| Whisper model | `whisperModel` | `BRISTLENOSE_WHISPER_MODEL` |
| Language | `language` | `BRISTLENOSE_WHISPER_LANGUAGE` |
| Azure endpoint | `azureEndpoint` | `BRISTLENOSE_AZURE_ENDPOINT` |
| Azure deployment | `azureDeployment` | `BRISTLENOSE_AZURE_DEPLOYMENT` |
| Azure API version | `azureAPIVersion` | `BRISTLENOSE_AZURE_API_VERSION` |
| Ollama URL | `localURL` | `BRISTLENOSE_LOCAL_URL` |
| Appearance | `appearance` | *(bridge, not env)* |
| API keys | **Keychain** | *(Python reads directly)* |

## Provider status model

`ProviderStatus` in `LLMProvider.swift` — normalised account status:

| Status | Dot | Detection |
|--------|-----|-----------|
| `.online` | Green | Key valid (2xx test call) or Ollama reachable |
| `.notSetUp` | Grey | No key in Keychain |
| `.invalid` | Red | 401/403 from test call |
| `.unavailable` | Orange | 402/429/network error |
| `.checking` | Grey | Validation in progress |

Status is orthogonal to active selection. Providers don't expose balance, free-tier, or trial status via API — we report only what we can detect.
