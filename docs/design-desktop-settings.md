---
status: current
last-trued: 2026-04-29
trued-against: HEAD@first-run on 2026-04-29 (uncommitted Beat 3)
---

## Changelog

- _2026-04-29_ — Beat 3 reconciled: round-trip credential validation now shipped via new `LLMValidator.swift`. ProviderStatus table augmented to cover Azure 404 → `.invalid` and Anthropic forward-compat (any 4xx ≠ 401/403/402/429 → `.online`, robust against haiku-model deprecation). New §"Validation flow" subsection documents the verdict cache (SHA256-prefix keyed, UserDefaults), 60s TTL gate, offline survival via cache fallback on transient `.unavailable`, `.checking` rendered as `ProgressView` (Mail-style spinner), animated dot transitions, and the "Last verified Xm ago" line. Tightened Ollama line to specify HTTP probe target (`<url>/api/tags`). Anchors: `desktop/Bristlenose/Bristlenose/LLMValidator.swift`, `desktop/Bristlenose/Bristlenose/LLMSettingsView.swift`, `desktop/Bristlenose/Bristlenose/LLMProvider.swift`.
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

Right detail pane shows the selected provider's settings: API key (`SecureField` → Keychain via `KeychainHelper`), model picker (per-provider known models + "Custom…"), temperature slider, concurrency slider. Azure adds endpoint/deployment/version fields. Ollama shows URL instead of API key (no key injection — status derives from an HTTP probe to `<url>/api/tags`, parsing the models list to distinguish "not running" from "running but no models pulled"; see `LLMValidator.probeOllama`).

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

`ProviderStatus` in `LLMProvider.swift` — normalised account status. Mapping
from HTTP response → status lives in `LLMValidator.classify(provider:status:)`.

| Status | Dot | Detection |
|--------|-----|-----------|
| `.online` | Green | 2xx from test call; OR cached `.ok` verdict for current key; OR Anthropic 4xx ≠ 401/403/402/429 (auth-before-payload, robust against haiku-model deprecation); OR Ollama reachable with at least one model pulled |
| `.notSetUp` | Grey | No key in Keychain (or empty Ollama URL) |
| `.invalid` | Red | 401/403 from test call; OR Azure 404 (endpoint/deployment not found — message points at endpoint, not key); OR Azure URL missing https:// scheme |
| `.unavailable` | Orange | 402/429/network error/timeout; OR Azure key entered but endpoint blank (started-but-incomplete) |
| `.checking` | Spinner | Validation in progress — rendered as `ProgressView().controlSize(.small)` in both sidebar and detail pane (Mail "Status: Connecting…" pattern) |

Only `.online` allows the radio to activate. `.invalid` is the lone "key
present" state that blocks activation — confirmed-bad credentials must not
be activatable. `.unavailable` (transient or unverified) blocks too;
previously-validated keys survive offline because the cache fallback
promotes them back to `.online` (see Validation flow below).

## Validation flow (Beat 3)

`LLMValidator` does round-trip credential validation natively in Swift —
not via the sidecar — so Settings works before any project is loaded.
URLSession.ephemeral, 5s timeout, per-provider auth-check endpoints
(Anthropic POST `/v1/messages` `max_tokens=1`, OpenAI GET `/v1/models`,
Azure GET `/openai/deployments`, Gemini GET `/v1beta/models`,
Ollama GET `/api/tags`).

**Verdict cache.** Per-provider entries in `UserDefaults` keyed by truncated
SHA-256 of the credential (8 bytes, ~5×10⁻¹⁰ collision rate at single-entry
scale). Stores three fields: `_keyHash`, `_status` (`ok` / `invalid`),
`_lastCheckedAt` (ISO 8601). Only definitive verdicts (`.online`,
`.invalid`) write the cache; transient `.unavailable` never overwrites.
The full credential lives in Keychain — UserDefaults stores opaque
identity, not secret material. (Threat-model: a same-UID process can
fingerprint provider config + rotation history but cannot recover the key.)

**Offline survival.** When validation returns `.unavailable` (timeout,
no connectivity, 402/429) AND the cache holds a definitive verdict for
this exact key, the cache wins: `.online` from cache survives a flaky café
connection; `.invalid` from cache survives an offline relaunch. The user
keeps the radio activatable on a previously-good key without a fresh
network round-trip. Net guarantee: the dot reflects last-known-truth, not
"can we reach the network right now."

**TTL gating.** `LLMSettingsView.cacheTTL = 60s`. `revalidateAll()` skips
`kickOffValidation` for cloud providers whose cache entry is younger
than the TTL — opening Settings 20×/day to tweak temperature doesn't
hammer four LLM APIs. Ollama is exempt (localhost is cheap, always
probed).

**`.checking` is always shown during validation.** `kickOffValidation`
synchronously sets `statuses[provider] = .checking` before the await.
SwiftUI batches state writes within the same tick, so even when the cache
pre-set the dot to `.online`, the rendered transition is dot → spinner →
settled — never a misleading green-flash-red on a rotated key.

**"Last verified" UI.** Detail pane shows a `.tertiary`-coloured "Last
verified Xm ago" line under the status row when a definitive verdict
exists. `RelativeDateTimeFormatter` for the relative string; a 30s ticker
keeps the label honest as time passes.

**Coverage gap (parked).** `LLMValidator` runs only when Settings is open
or on Save. There's no app-wide background revalidation — a key rotated
server-side while the user is offline isn't detected until they next open
Settings. Future work would add `NWPathMonitor` to fire validation on
wifi-reconnect and post a toast on cached-`.ok` → fresh-`.invalid`
transitions ("Claude key was rejected — open Settings to update"). Tracked
as a follow-up dependency for that toast affordance.

Status is orthogonal to active selection. Providers don't expose balance, free-tier, or trial status via API — we report only what we can detect.
